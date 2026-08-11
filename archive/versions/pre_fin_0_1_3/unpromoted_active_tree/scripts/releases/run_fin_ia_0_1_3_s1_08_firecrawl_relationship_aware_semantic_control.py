from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from typing import Any, Mapping
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_08_firecrawl_semantic_control import (  # noqa: E402
    RUN_SCOPE,
    build_terminal_result,
    load_authority,
    load_plan,
    normalize_firecrawl_response,
)


DEFAULT_AUTHORITY = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_authority_v1_0.json"
DEFAULT_PLAN = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_plan_v1_0.json"
DEFAULT_RUNTIME = ROOT / "artifacts/runtime/provider_market_scan/firecrawl_relationship_aware_semantic_control_20260808_r1"
DEFAULT_RESULT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_result_v1_0.json"


class FirecrawlSemanticControlRunnerError(RuntimeError):
    pass


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _atomic_write_bytes(
        path,
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )


def _relative(runtime_root: Path, path: Path) -> str:
    return path.resolve().relative_to(runtime_root.resolve()).as_posix()


def _validate_authority_bindings(
    *, authority: Mapping[str, Any], authority_path: Path, plan_path: Path
) -> None:
    bindings = authority.get("immutable_bindings") or {}
    required = {
        "runner_sha256": Path(__file__).resolve(),
        "support_sha256": ROOT / "src/sec_agent/s1_08_firecrawl_semantic_control.py",
        "plan_sha256": plan_path,
        "scoring_contract_sha256": ROOT / "configs/eval/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_scoring_v1_0.json",
        "zero_call_proof_sha256": ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_zero_call_proof_v1_0.json",
        "wire_policy_sha256": ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_domestic_provider_wire_projection_policy_v1_0.json",
        "wire_projection_sha256": ROOT / "src/sec_agent/s1_08_provider_wire_projection.py",
    }
    for field, path in required.items():
        if not path.is_file() or bindings.get(field) != _sha256(path):
            raise FirecrawlSemanticControlRunnerError(
                "firecrawl_semantic_authority_binding_invalid"
            )
    plan = load_plan(plan_path)
    if bindings.get("plan_digest") != plan.get("plan_digest"):
        raise FirecrawlSemanticControlRunnerError(
            "firecrawl_semantic_plan_digest_binding_invalid"
        )
    implementation_commit = str(bindings.get("implementation_commit") or "")
    if not implementation_commit:
        raise FirecrawlSemanticControlRunnerError(
            "firecrawl_semantic_implementation_commit_missing"
        )
    try:
        _git("merge-base", "--is-ancestor", implementation_commit, "HEAD")
    except subprocess.CalledProcessError as exc:
        raise FirecrawlSemanticControlRunnerError(
            "firecrawl_semantic_implementation_commit_not_ancestor"
        ) from exc
    if authority_path.resolve() == required["zero_call_proof_sha256"].resolve():
        raise FirecrawlSemanticControlRunnerError(
            "firecrawl_semantic_authority_path_invalid"
        )


def _safe_failure(*, code: str, detail: str = "", http_status: int = 0) -> dict[str, Any]:
    return {
        "phase": "provider_transport",
        "code": code,
        "http_status": int(http_status),
        "detail_class": detail[:200],
        "retry_allowed": False,
        "credential_or_header_material_included": False,
    }


def run_control(
    *,
    authority_path: Path,
    plan_path: Path,
    runtime_root: Path,
    output_path: Path,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    local_terminal = runtime_root / "terminal-result.json"
    if runtime_root.exists() or output_path.exists() or local_terminal.exists():
        raise FirecrawlSemanticControlRunnerError(
            "firecrawl_semantic_exact_once_output_already_exists"
        )
    if _git("status", "--porcelain"):
        raise FirecrawlSemanticControlRunnerError(
            "firecrawl_semantic_clean_worktree_required"
        )
    source_commit = _git("rev-parse", "HEAD")
    authority = load_authority(authority_path)
    plan = load_plan(plan_path)
    _validate_authority_bindings(
        authority=authority,
        authority_path=authority_path,
        plan_path=plan_path,
    )
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise FirecrawlSemanticControlRunnerError(
            "firecrawl_semantic_project_os_preflight_failed"
        )
    runtime_root.mkdir(parents=True, exist_ok=False)
    whole_started = perf_counter()
    call_results: list[dict[str, Any]] = []
    systemic_stop = ""
    endpoint = str(plan["endpoint"])
    for row in plan["query_rows"]:
        ordinal = int(row["ordinal"])
        intent_id = str(row["intent_id"])
        safe_name = f"{ordinal:02d}-{hashlib.sha256(intent_id.encode('utf-8')).hexdigest()[:12]}"
        call_root = runtime_root / "calls" / safe_name
        request_capture = {
            "provider": "firecrawl_keyless_search",
            "endpoint": endpoint,
            "method": "POST",
            "request_body": row["request_body"],
            "request_payload_digest": row["request_payload_digest"],
            "execution_unit_digest": row["execution_unit_digest"],
            "authorization_header_sent": False,
            "cookie_header_sent": False,
        }
        safe_request_path = call_root / "safe-request.json"
        _atomic_write_json(safe_request_path, request_capture)
        call_started = perf_counter()
        projection: dict[str, Any] = {}
        failure: dict[str, Any] = {}
        capture_refs: dict[str, Any] = {
            "safe_request": _relative(runtime_root, safe_request_path),
            "safe_request_sha256": _sha256(safe_request_path),
        }
        network_attempted = False
        status = "failed"
        terminal_code = "firecrawl_semantic_query_typed_failure"
        http_status = 0
        if systemic_stop:
            failure = _safe_failure(
                code="not_attempted_after_systemic_provider_rejection",
                detail=systemic_stop,
            )
            terminal_code = "firecrawl_semantic_query_not_attempted_systemic_stop"
        else:
            network_attempted = True
            request_bytes = json.dumps(
                row["request_body"], ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            request = Request(
                endpoint,
                data=request_bytes,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "FIN-Insight-Agent/0.1.3 diagnostic-control",
                },
            )
            try:
                with urlopen(request, timeout=timeout_seconds) as response:
                    http_status = int(response.status)
                    raw_bytes = response.read()
                raw_path = call_root / "raw-response.json"
                _atomic_write_bytes(raw_path, raw_bytes)
                capture_refs.update(
                    {
                        "raw_response": _relative(runtime_root, raw_path),
                        "raw_response_sha256": _sha256(raw_path),
                    }
                )
                payload = json.loads(raw_bytes.decode("utf-8"))
                projection = normalize_firecrawl_response(payload)
                status = "completed"
                terminal_code = "firecrawl_semantic_query_response_materialized"
            except HTTPError as exc:
                http_status = int(exc.code or 0)
                raw_bytes = exc.read()
                raw_path = call_root / "raw-http-failure.bin"
                _atomic_write_bytes(raw_path, raw_bytes)
                capture_refs.update(
                    {
                        "raw_http_failure": _relative(runtime_root, raw_path),
                        "raw_http_failure_sha256": _sha256(raw_path),
                    }
                )
                failure = _safe_failure(
                    code="provider_http_error",
                    detail=type(exc).__name__,
                    http_status=http_status,
                )
                if http_status in {401, 402, 403}:
                    systemic_stop = f"http_{http_status}"
            except Exception as exc:  # capture every terminal transport shape
                failure = _safe_failure(
                    code="provider_transport_or_parse_error",
                    detail=type(exc).__name__,
                    http_status=http_status,
                )
                failure_path = call_root / "typed-failure.json"
                _atomic_write_json(failure_path, failure)
                capture_refs.update(
                    {
                        "typed_failure": _relative(runtime_root, failure_path),
                        "typed_failure_sha256": _sha256(failure_path),
                    }
                )
        call_result = {
            "ordinal": ordinal,
            "intent_id": intent_id,
            "case_key": row["case_key"],
            "evidence_slot_id": row["evidence_slot_id"],
            "evidence_owner_entity_key": row["evidence_owner_entity_key"],
            "language": row["language"],
            "status": status,
            "terminal_code": terminal_code,
            "network_call_attempted": network_attempted,
            "http_status": http_status,
            "request_capture": request_capture,
            "provider_projection": projection,
            "failure": failure,
            "elapsed_ms": int(round((perf_counter() - call_started) * 1000)),
            "capture_refs": capture_refs,
        }
        call_terminal_path = call_root / "terminal.json"
        _atomic_write_json(call_terminal_path, call_result)
        call_result["capture_refs"].update(
            {
                "call_terminal": _relative(runtime_root, call_terminal_path),
                "call_terminal_sha256": _sha256(call_terminal_path),
            }
        )
        call_results.append(call_result)
    result = build_terminal_result(
        admission_id=str(authority["admission_id"]),
        source_commit=source_commit,
        plan_digest=str(plan["plan_digest"]),
        call_results=call_results,
        elapsed_ms=int(round((perf_counter() - whole_started) * 1000)),
    )
    _atomic_write_json(local_terminal, result)
    result_with_capture = dict(result)
    result_with_capture["terminal_capture"] = {
        "runtime_ref": str(local_terminal.relative_to(ROOT)).replace("\\", "/"),
        "sha256": _sha256(local_terminal),
    }
    result_body = dict(result_with_capture)
    result_body.pop("result_digest", None)
    result_with_capture["result_digest"] = canonical_digest(result_body)
    _atomic_write_json(output_path, result_with_capture)
    return result_with_capture


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", type=Path, default=DEFAULT_AUTHORITY)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    args = parser.parse_args()
    result = run_control(
        authority_path=args.authority,
        plan_path=args.plan,
        runtime_root=args.runtime_root,
        output_path=args.output,
        timeout_seconds=args.timeout_seconds,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "observed_counts": result["observed_counts"],
                "credits_used": result["credits_used"],
                "elapsed_ms": result["elapsed_ms"],
                "result_digest": result["result_digest"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
