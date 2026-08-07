from __future__ import annotations

import atexit
import json
import multiprocessing as mp
import os
import subprocess
import sys
import threading
import time
import uuid
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE_PATH = REPO_ROOT / "configs" / "mcp" / "sec_agent_mcp_runtime_profile_v0_1.json"


@dataclass(frozen=True)
class McpRuntimeProfile:
    profile_id: str
    profile_path: Path
    resources: dict[str, str]
    tool_timeouts_s: dict[str, float]
    default_timeout_s: float

    @classmethod
    def load(cls, path: str | Path | None = None) -> "McpRuntimeProfile":
        selected = Path(
            path
            or os.environ.get("FINSIGHT_MCP_RUNTIME_PROFILE")
            or DEFAULT_PROFILE_PATH
        ).resolve()
        payload = json.loads(selected.read_text(encoding="utf-8"))
        resources = {
            str(key): str(value)
            for key, value in dict(payload.get("resources") or {}).items()
            if str(value).strip()
        }
        timeouts = {
            str(key): float(value)
            for key, value in dict(payload.get("tool_timeouts_s") or {}).items()
        }
        return cls(
            profile_id=str(payload.get("profile_id") or selected.stem),
            profile_path=selected,
            resources=resources,
            tool_timeouts_s=timeouts,
            default_timeout_s=float(payload.get("default_timeout_s") or 30.0),
        )

    def timeout_for(self, tool_name: str, override: Any = None) -> float:
        if override not in {None, ""}:
            value = float(override)
        else:
            value = float(self.tool_timeouts_s.get(tool_name, self.default_timeout_s))
        return max(0.01, min(value, 900.0))


_RESOURCE_ENV = {
    "manifest_path": "MANIFEST_PATH",
    "bm25_index_dir": "BM25_INDEX_DIR",
    "object_bm25_index_dir": "OBJECT_BM25_INDEX_DIR",
    "ledger_store_path": "LEDGER_STORE_PATH",
    "market_evidence_path": "MARKET_EVIDENCE_PATH",
    "market_catalog_path": "MARKET_CATALOG_PATH",
    "industry_evidence_path": "INDUSTRY_EVIDENCE_PATH",
    "industry_snapshot_db_path": "INDUSTRY_SNAPSHOT_DB_PATH",
    "relationship_graph_path": "RELATIONSHIP_GRAPH_PATH",
    "sector_depth_pack_path": "SECTOR_DEPTH_PACK_PATH",
    "milvus_db_path": "MILVUS_DB_PATH",
    "milvus_collection_name": "MILVUS_COLLECTION_NAME",
    "embedding_model": "MILVUS_EMBEDDING_MODEL",
    "bge_model": "BGE_MODEL",
}

_TOOL_RESOURCES = {
    "sec_search_filings": (
        ("manifest_path", "file", True),
        ("bm25_index_dir", "directory", True),
        ("object_bm25_index_dir", "directory", True),
        ("ledger_store_path", "file", False),
    ),
    "sec_query_exact_value_ledger": (("ledger_store_path", "file", True),),
    "market_get_snapshot": (
        ("market_evidence_path", "file", True),
        ("market_catalog_path", "file", False),
    ),
    "industry_get_snapshot": (
        ("industry_snapshot_db_path", "file", False),
        ("industry_evidence_path", "file", False),
    ),
    "relationship_graph_lookup": (
        ("relationship_graph_path", "file", False),
        ("sector_depth_pack_path", "file", False),
    ),
    "sec_milvus_semantic_search": (
        ("milvus_db_path", "file", False),
        ("embedding_model", "directory", False),
    ),
}


def bind_mcp_resources(
    tool_name: str,
    arguments: dict[str, Any],
    profile: McpRuntimeProfile,
) -> tuple[dict[str, Any], dict[str, Any]]:
    bound = dict(arguments)
    bindings: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    if tool_name == "sec_search_filings":
        rerank_budget = int(bound.get("rerank_budget") or 0)
        requested_reranker = str(bound.get("context_reranker") or "").strip().lower()
        if not requested_reranker:
            requested_reranker = "none" if rerank_budget == 0 else "bge"
        if requested_reranker not in {"none", "bge"}:
            missing.append(
                {
                    "resource": "context_reranker",
                    "reason_code": "unsupported_context_reranker",
                    "value": requested_reranker,
                }
            )
        bound["context_reranker"] = requested_reranker
        bound["allow_bm25_only_pipeline"] = requested_reranker == "none"

    for key, kind, required in _TOOL_RESOURCES.get(tool_name, ()):
        value, source = _resource_value(key, bound, profile)
        if value:
            resolved = _resolve_resource_path(value, kind=kind)
            exists = resolved.is_dir() if kind == "directory" else resolved.is_file()
            bound[key] = str(resolved)
            bindings.append(
                {
                    "resource": key,
                    "source": source,
                    "kind": kind,
                    "path": str(resolved),
                    "exists": exists,
                }
            )
            if not exists and required:
                missing.append(
                    {
                        "resource": key,
                        "reason_code": "canonical_resource_not_found",
                        "path": str(resolved),
                    }
                )
        elif required:
            missing.append(
                {
                    "resource": key,
                    "reason_code": "canonical_resource_not_configured",
                }
            )

    if tool_name == "sec_search_filings" and bound.get("context_reranker") == "bge":
        value, source = _resource_value("bge_model", bound, profile)
        if value:
            resolved = _resolve_resource_path(value, kind="directory")
            exists = resolved.is_dir()
            bound["bge_model"] = str(resolved)
            bindings.append(
                {
                    "resource": "bge_model",
                    "source": source,
                    "kind": "directory",
                    "path": str(resolved),
                    "exists": exists,
                }
            )
            if not exists:
                missing.append(
                    {
                        "resource": "bge_model",
                        "reason_code": "canonical_reranker_not_found",
                        "path": str(resolved),
                    }
                )
        else:
            missing.append(
                {
                    "resource": "bge_model",
                    "reason_code": "canonical_reranker_not_configured",
                }
            )

    receipt = {
        "profile_id": profile.profile_id,
        "profile_path": str(profile.profile_path),
        "bindings": bindings,
        "missing": missing,
        "status": "pass" if not missing else "fail",
    }
    return bound, receipt


def _resource_value(
    key: str,
    arguments: dict[str, Any],
    profile: McpRuntimeProfile,
) -> tuple[str, str]:
    explicit = str(arguments.get(key) or "").strip()
    if explicit:
        return explicit, "request"
    env_name = _RESOURCE_ENV.get(key, "")
    env_value = str(os.environ.get(env_name) or "").strip() if env_name else ""
    if env_value:
        return env_value, f"environment:{env_name}"
    profile_value = str(profile.resources.get(key) or "").strip()
    if profile_value:
        return profile_value, "runtime_profile"
    return "", "unbound"


def _resolve_resource_path(value: str, *, kind: str) -> Path:
    del kind
    path = Path(value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


class McpToolProcessSupervisor:
    def __init__(
        self,
        *,
        profile_path: str | Path | None = None,
        startup_timeout_s: float = 15.0,
        _test_request_delay_s: float = 0.0,
    ) -> None:
        self.profile = McpRuntimeProfile.load(profile_path)
        self.startup_timeout_s = max(1.0, float(startup_timeout_s))
        self._test_request_delay_s = max(0.0, float(_test_request_delay_s))
        self._ctx = mp.get_context("spawn")
        self._process: mp.Process | None = None
        self._connection: Any = None
        self._lock = threading.Lock()
        self._worker_calls = 0
        self._last_terminated_exitcode: int | None = None
        atexit.register(self.close)

    @property
    def worker_pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    @property
    def worker_alive(self) -> bool:
        return bool(self._process is not None and self._process.is_alive())

    @property
    def last_terminated_exitcode(self) -> int | None:
        return self._last_terminated_exitcode

    def invoke(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = dict(arguments or {})
        timeout_s = self.profile.timeout_for(tool_name, args.pop("timeout_s", None))
        invocation_id = f"mcp_{uuid.uuid4().hex}"
        started = time.perf_counter()
        phases: list[dict[str, Any]] = []

        bind_started = time.perf_counter()
        bound_args, binding = bind_mcp_resources(tool_name, args, self.profile)
        phases.append(_phase("resource_binding", bind_started, binding["status"]))
        if binding["status"] != "pass":
            return _operational_failure(
                tool_name=tool_name,
                error="mcp_resource_binding_failed",
                invocation_id=invocation_id,
                timeout_s=timeout_s,
                started=started,
                phases=phases,
                binding=binding,
                worker_pid=self.worker_pid,
                start_kind="not_started",
            )

        with self._lock:
            start_kind = "warm"
            startup_started = time.perf_counter()
            if not self.worker_alive:
                start_kind = "cold"
                try:
                    self._start_worker()
                except Exception as exc:  # noqa: BLE001
                    phases.append(_phase("worker_start", startup_started, "error"))
                    return _operational_failure(
                        tool_name=tool_name,
                        error=f"mcp_worker_start_failed:{type(exc).__name__}",
                        invocation_id=invocation_id,
                        timeout_s=timeout_s,
                        started=started,
                        phases=phases,
                        binding=binding,
                        worker_pid=self.worker_pid,
                        start_kind=start_kind,
                    )
            phases.append(_phase("worker_start", startup_started, "pass"))
            worker_pid = self.worker_pid
            handler_started = time.perf_counter()
            request = {
                "type": "invoke",
                "invocation_id": invocation_id,
                "tool_name": tool_name,
                "arguments": bound_args,
            }
            try:
                self._connection.send(request)
                if not self._connection.poll(timeout_s):
                    phases.append(_phase("handler_execution", handler_started, "timeout"))
                    self._terminate_worker_tree()
                    return _operational_failure(
                        tool_name=tool_name,
                        error="mcp_tool_timeout",
                        invocation_id=invocation_id,
                        timeout_s=timeout_s,
                        started=started,
                        phases=phases,
                        binding=binding,
                        worker_pid=worker_pid,
                        start_kind=start_kind,
                    )
                response = self._connection.recv()
            except (EOFError, BrokenPipeError, OSError) as exc:
                phases.append(_phase("handler_execution", handler_started, "worker_exit"))
                self._terminate_worker_tree()
                return _operational_failure(
                    tool_name=tool_name,
                    error=f"mcp_worker_transport_failed:{type(exc).__name__}",
                    invocation_id=invocation_id,
                    timeout_s=timeout_s,
                    started=started,
                    phases=phases,
                    binding=binding,
                    worker_pid=worker_pid,
                    start_kind=start_kind,
                )
            except KeyboardInterrupt:
                phases.append(_phase("handler_execution", handler_started, "cancelled"))
                self._terminate_worker_tree()
                raise

            self._worker_calls += 1
            result = dict(response.get("result") or {})
            handler_status = "pass" if result.get("status") not in {"error"} else "typed_failure"
            phases.append(_phase("handler_execution", handler_started, handler_status))
            result["operational"] = {
                "schema_version": "fin_insight_mcp_operational_receipt_v0_1",
                "invocation_id": invocation_id,
                "tool_name": tool_name,
                "profile_id": self.profile.profile_id,
                "timeout_s": timeout_s,
                "start_kind": start_kind,
                "worker_pid": worker_pid,
                "worker_call_index": int(response.get("worker_call_index") or self._worker_calls),
                "worker_stdout_chars": int(response.get("stdout_chars") or 0),
                "worker_stderr_chars": int(response.get("stderr_chars") or 0),
                "resource_binding": binding,
                "phases": phases,
                "terminal_status": handler_status,
                "elapsed_ms": int(round((time.perf_counter() - started) * 1000)),
            }
            return result

    def _start_worker(self) -> None:
        parent, child = self._ctx.Pipe(duplex=True)
        process = self._ctx.Process(
            target=_mcp_worker_main,
            args=(child, self._test_request_delay_s),
            name="finsight-mcp-tool-worker",
            daemon=False,
        )
        process.start()
        child.close()
        if not parent.poll(self.startup_timeout_s):
            process.terminate()
            process.join(timeout=5.0)
            raise TimeoutError("MCP worker did not become ready")
        ready = parent.recv()
        if ready.get("status") != "ready":
            process.terminate()
            process.join(timeout=5.0)
            raise RuntimeError("MCP worker returned invalid startup receipt")
        self._process = process
        self._connection = parent
        self._worker_calls = 0

    def _terminate_worker_tree(self) -> None:
        process = self._process
        connection = self._connection
        self._process = None
        self._connection = None
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass
        if process is None:
            return
        if process.is_alive():
            if os.name == "nt" and process.pid:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            if process.is_alive():
                process.terminate()
            process.join(timeout=5.0)
            if process.is_alive():
                process.kill()
                process.join(timeout=5.0)
        self._last_terminated_exitcode = process.exitcode

    def close(self) -> None:
        with self._lock:
            if self._process is None:
                return
            if self.worker_alive and self._connection is not None:
                try:
                    self._connection.send({"type": "shutdown"})
                    if self._connection.poll(2.0):
                        self._connection.recv()
                except (EOFError, BrokenPipeError, OSError):
                    pass
            self._terminate_worker_tree()

    def cancel(self) -> None:
        """Terminate the active handler process tree; the next invocation starts fresh."""
        self._terminate_worker_tree()


def _mcp_worker_main(connection: Any, test_request_delay_s: float) -> None:
    from sec_agent.mcp_tool_registry import invoke_mcp_tool

    connection.send({"status": "ready", "pid": os.getpid()})
    call_index = 0
    while True:
        request = connection.recv()
        if request.get("type") == "shutdown":
            connection.send({"status": "closed", "pid": os.getpid()})
            return
        if request.get("type") != "invoke":
            connection.send({"result": {"status": "error", "error": "invalid_worker_request"}})
            continue
        call_index += 1
        if test_request_delay_s:
            time.sleep(test_request_delay_s)
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = invoke_mcp_tool(
                str(request.get("tool_name") or ""),
                dict(request.get("arguments") or {}),
            )
        connection.send(
            {
                "result": result,
                "worker_call_index": call_index,
                "stdout_chars": len(stdout.getvalue()),
                "stderr_chars": len(stderr.getvalue()),
            }
        )


def _phase(name: str, started: float, status: str) -> dict[str, Any]:
    return {
        "phase": name,
        "status": status,
        "elapsed_ms": int(round((time.perf_counter() - started) * 1000)),
    }


def _operational_failure(
    *,
    tool_name: str,
    error: str,
    invocation_id: str,
    timeout_s: float,
    started: float,
    phases: list[dict[str, Any]],
    binding: dict[str, Any],
    worker_pid: int | None,
    start_kind: str,
) -> dict[str, Any]:
    return {
        "status": "error",
        "error": error,
        "tool_name": tool_name,
        "operational": {
            "schema_version": "fin_insight_mcp_operational_receipt_v0_1",
            "invocation_id": invocation_id,
            "tool_name": tool_name,
            "profile_id": binding.get("profile_id"),
            "timeout_s": timeout_s,
            "start_kind": start_kind,
            "worker_pid": worker_pid,
            "resource_binding": binding,
            "phases": phases,
            "terminal_status": "failed",
            "elapsed_ms": int(round((time.perf_counter() - started) * 1000)),
        },
    }


__all__ = [
    "DEFAULT_PROFILE_PATH",
    "McpRuntimeProfile",
    "McpToolProcessSupervisor",
    "bind_mcp_resources",
]
