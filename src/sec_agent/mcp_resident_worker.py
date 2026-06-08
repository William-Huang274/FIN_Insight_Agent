from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


STARTED_AT = datetime.now(timezone.utc).isoformat()
REQUEST_COUNT = 0
REQUEST_LOCK = threading.Lock()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    os.environ["SEC_AGENT_MCP_RESIDENT_BYPASS"] = "1"
    if args.chdir:
        os.chdir(args.chdir)
    _install_signal_handlers()
    if args.warmup_jsonl:
        _run_warmups(args.warmup_jsonl)
    server = ThreadingHTTPServer((args.host, args.port), _Handler)
    server.timeout = 1.0
    print(
        json.dumps(
            {
                "stage": "resident_worker_started",
                "host": args.host,
                "port": args.port,
                "pid": os.getpid(),
                "started_at": STARTED_AT,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    server.serve_forever()
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a resident local MCP worker for high-cost SEC retrieval tools.")
    parser.add_argument("--host", default=os.environ.get("SEC_AGENT_MCP_RESIDENT_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SEC_AGENT_MCP_RESIDENT_PORT", "8765")))
    parser.add_argument("--chdir", default=os.environ.get("SEC_AGENT_MCP_RESIDENT_CWD", ""))
    parser.add_argument("--warmup-jsonl", type=Path, default=None)
    return parser.parse_args(argv)


def _install_signal_handlers() -> None:
    def _stop(_signum: int, _frame: Any) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)


def _run_warmups(path: Path) -> None:
    if not path.exists():
        print(json.dumps({"stage": "resident_worker_warmup_missing", "path": str(path)}, ensure_ascii=False), flush=True)
        return
    from sec_agent.mcp_tool_registry import invoke_mcp_tool

    for ordinal, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        started = time.time()
        try:
            payload = json.loads(line)
            tool_name = str(payload.get("tool_name") or "")
            arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
            result = invoke_mcp_tool(tool_name, arguments)
            print(
                json.dumps(
                    {
                        "stage": "resident_worker_warmup",
                        "ordinal": ordinal,
                        "tool_name": tool_name,
                        "status": result.get("status"),
                        "row_count": result.get("row_count"),
                        "elapsed_ms": int((time.time() - started) * 1000),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            print(
                json.dumps(
                    {
                        "stage": "resident_worker_warmup_error",
                        "ordinal": ordinal,
                        "error": f"{type(exc).__name__}:{exc}"[:500],
                        "elapsed_ms": int((time.time() - started) * 1000),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )


class _Handler(BaseHTTPRequestHandler):
    server_version = "SecAgentResidentMCP/0.1"

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/health":
            self._write_json(
                {
                    "status": "ok",
                    "pid": os.getpid(),
                    "started_at": STARTED_AT,
                    "request_count": REQUEST_COUNT,
                    "cache": _cache_snapshot(),
                }
            )
            return
        self._write_json({"status": "error", "error": "not_found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        global REQUEST_COUNT
        if self.path.rstrip("/") != "/invoke":
            self._write_json({"status": "error", "error": "not_found"}, status=404)
            return
        started = time.time()
        try:
            length = int(self.headers.get("Content-Length") or "0")
            if length <= 0:
                self._write_json({"status": "error", "error": "empty_body"}, status=400)
                return
            if length > int(os.environ.get("SEC_AGENT_MCP_RESIDENT_MAX_BODY_BYTES", "52428800")):
                self._write_json({"status": "error", "error": "body_too_large"}, status=413)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            tool_name = str(payload.get("tool_name") or "")
            arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
            from sec_agent.mcp_tool_registry import invoke_mcp_tool

            result = invoke_mcp_tool(tool_name, arguments)
            if not isinstance(result, dict):
                result = {"status": "error", "error": "tool_returned_non_object", "tool_name": tool_name}
            with REQUEST_LOCK:
                REQUEST_COUNT += 1
                request_count = REQUEST_COUNT
            resident = dict(result.get("resident_worker") or {}) if isinstance(result.get("resident_worker"), dict) else {}
            resident.update(
                {
                    "pid": os.getpid(),
                    "request_count": request_count,
                    "server_elapsed_ms": int((time.time() - started) * 1000),
                    "cache": _cache_snapshot(),
                }
            )
            result["resident_worker"] = resident
            self._write_json(result)
        except Exception as exc:  # noqa: BLE001
            self._write_json(
                {
                    "status": "error",
                    "error": f"{type(exc).__name__}:{exc}",
                    "resident_worker": {"pid": os.getpid(), "server_elapsed_ms": int((time.time() - started) * 1000)},
                },
                status=500,
            )

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        if os.environ.get("SEC_AGENT_MCP_RESIDENT_ACCESS_LOG"):
            super().log_message(format, *args)

    def _write_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _cache_snapshot() -> dict[str, Any]:
    try:
        import sec_agent.mcp_tool_registry as registry

        return {
            "interactive_module_loaded": bool(getattr(registry, "_INTERACTIVE_MODULE", None)),
            "milvus_embedding_model_cache_size": len(getattr(registry, "_MILVUS_EMBEDDING_MODEL_CACHE", {}) or {}),
            "milvus_client_cache_size": len(getattr(registry, "_MILVUS_CLIENT_CACHE", {}) or {}),
            "sec_search_result_cache_size": len(getattr(registry, "_SEC_SEARCH_RESULT_CACHE", {}) or {}),
            "sec_manifest_rows_cache_size": len(getattr(registry, "_SEC_MANIFEST_ROWS_CACHE", {}) or {}),
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}:{exc}"[:500]}


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
