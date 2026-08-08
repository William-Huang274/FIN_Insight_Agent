from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from time import perf_counter
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_08_searxng_diagnostic_adapter import (
    SearXNGDiagnosticAdapter,
    SearXNGDiagnosticError,
    SearXNGDiagnosticQuery,
    UrllibSearXNGDiagnosticTransport,
    load_searxng_diagnostic_policy,
)


AUTHORITY_SCHEMA = "fin_ia_0_1_3_s1_08_searxng_bounded_diagnostic_baseline_authority_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_08_searxng_bounded_diagnostic_baseline_result_v1_0"
AUTHORITY_CONTRACT = "fin_0_1_3.S1_08.searxng_bounded_diagnostic_baseline_authority:v1"


class DiagnosticBaselineError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise DiagnosticBaselineError("diagnostic_baseline_git_preflight_failed")
    return completed.stdout.strip()


def load_authority(path: str | Path) -> dict[str, Any]:
    authority_path = Path(path).resolve()
    payload = json.loads(authority_path.read_text(encoding="utf-8"))
    body = dict(payload)
    digest = body.pop("authority_digest", None)
    if (
        body.get("schema_version") != AUTHORITY_SCHEMA
        or body.get("contract_ref") != AUTHORITY_CONTRACT
        or digest != canonical_digest(body)
    ):
        raise DiagnosticBaselineError("diagnostic_baseline_authority_identity_invalid")
    if payload.get("status") != "issued_unconsumed":
        raise DiagnosticBaselineError("diagnostic_baseline_authority_not_issued")
    execution = payload.get("execution_contract") or {}
    if (
        execution.get("fin_to_searxng_query_call_ceiling") != 3
        or execution.get("retry_ceiling") != 0
        or execution.get("model_call_ceiling") != 0
        or execution.get("public_instance_fallback_allowed") is not False
        or execution.get("evidence_promotion_allowed") is not False
        or execution.get("production_capability_claim_allowed") is not False
    ):
        raise DiagnosticBaselineError("diagnostic_baseline_authority_boundary_invalid")
    queries = payload.get("queries") or []
    if len(queries) != 3 or [row.get("case_key") for row in queries] != ["DELL", "MU", "NVDA"]:
        raise DiagnosticBaselineError("diagnostic_baseline_authority_query_set_invalid")
    return payload


def run_baseline(
    *,
    authority_path: Path,
    policy_path: Path,
    proof_path: Path,
    runtime_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    if output_path.exists() or (runtime_root / "execution-result.json").exists():
        raise DiagnosticBaselineError("diagnostic_baseline_exact_once_result_already_exists")
    if _git("status", "--porcelain"):
        raise DiagnosticBaselineError("diagnostic_baseline_clean_worktree_required")
    source_commit = _git("rev-parse", "HEAD")
    authority = load_authority(authority_path)
    policy = load_searxng_diagnostic_policy(policy_path)
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    if (
        proof.get("proof_digest") != authority.get("adapter_proof_digest")
        or _sha256(proof_path) != authority.get("adapter_proof_file_sha256")
        or canonical_digest(policy) != authority.get("policy_digest")
        or _sha256(policy_path) != authority.get("policy_file_sha256")
        or _sha256(Path(__file__).resolve()) != authority.get("runner_sha256")
    ):
        raise DiagnosticBaselineError("diagnostic_baseline_authority_binding_invalid")
    if proof.get("acceptance", {}).get("adapter_zero_call_engineering_pass") is not True:
        raise DiagnosticBaselineError("diagnostic_baseline_adapter_proof_not_passed")

    runtime_root.mkdir(parents=True, exist_ok=True)
    adapter = SearXNGDiagnosticAdapter(
        policy=policy,
        runtime_root=runtime_root,
        transport=UrllibSearXNGDiagnosticTransport(base_url=str(policy["base_url"])),
    )
    case_results: list[dict[str, Any]] = []
    for row in authority["queries"]:
        query = SearXNGDiagnosticQuery.create(
            query_id=str(row["query_id"]),
            case_key=str(row["case_key"]),
            evidence_slot_id=str(row["evidence_slot_id"]),
            query_text=str(row["query_text"]),
            language=str(row["language"]),
            time_range=str(row["time_range"]),
            categories=tuple(row["categories"]),
            result_ceiling=int(row["result_ceiling"]),
        )
        started = perf_counter()
        try:
            result = adapter.search(query)
        except SearXNGDiagnosticError as exc:
            result = {
                "schema_version": "runner_terminal_exception_v1_0",
                "query": {**query.digest_body(), "query_digest": query.query_digest},
                "status": "failed",
                "terminal_code": exc.code,
                "locators": [],
                "unresponsive_engines": [],
                "observed_counts": {
                    "upstream_raw_results": 0,
                    "normalized_locators": 0,
                    "evidence_promotions": 0,
                },
            }
        case_results.append(
            {
                "case_key": query.case_key,
                "query_id": query.query_id,
                "elapsed_ms": int(round((perf_counter() - started) * 1000)),
                "result": result,
            }
        )

    engine_locator_counts: dict[str, int] = {}
    for case in case_results:
        for locator in case["result"].get("locators") or []:
            for engine in locator.get("source_engines") or []:
                engine_locator_counts[str(engine)] = engine_locator_counts.get(str(engine), 0) + 1
    terminal_statuses = [str(case["result"].get("status") or "failed") for case in case_results]
    total_raw = sum(
        int((case["result"].get("observed_counts") or {}).get("upstream_raw_results", 0))
        for case in case_results
    )
    total_normalized = sum(
        int((case["result"].get("observed_counts") or {}).get("normalized_locators", 0))
        for case in case_results
    )
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": AUTHORITY_CONTRACT,
        "admission_id": authority["admission_id"],
        "admission_digest": authority["authority_digest"],
        "admission_consumed": True,
        "source_commit": source_commit,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "runtime_root": str(runtime_root.relative_to(ROOT)).replace("\\", "/"),
        "provider_kind": "self_hosted_searxng_diagnostic_locator",
        "case_results": case_results,
        "summary": {
            "formal_case_queries": len(case_results),
            "fin_to_searxng_query_calls": adapter.query_calls,
            "adapter_observed_network_calls": adapter.network_calls,
            "configured_metasearch_engine_ceiling_per_query": int(
                policy["budgets"]["configured_engine_ceiling_per_query"]
            ),
            "searxng_to_upstream_http_request_count_exactly_known": False,
            "model_calls": 0,
            "retry_calls": 0,
            "raw_locator_rows": total_raw,
            "normalized_unique_locators": total_normalized,
            "canonical_duplicate_rows_removed": max(0, total_raw - total_normalized),
            "engine_locator_counts": dict(sorted(engine_locator_counts.items())),
            "case_terminal_statuses": terminal_statuses,
            "evidence_promotions": sum(
                int((case["result"].get("observed_counts") or {}).get("evidence_promotions", 0))
                for case in case_results
            ),
            "capture_count": len(adapter.capture_refs),
        },
        "acceptance": {
            "bounded_diagnostic_execution_materialized": (
                len(case_results) == 3
                and adapter.query_calls == 3
                and adapter.network_calls == 3
                and all(status in {"completed", "completed_empty", "failed"} for status in terminal_statuses)
            ),
            "diagnostic_locator_recall_sufficient": None,
            "production_search_capability_proven": False,
            "evidence_retrieval_quality_proven": False,
            "financial_research_quality_proven": False,
        },
        "hard_boundary": {
            "promotion_status": "diagnostic_locator_only",
            "evidence_promotion_allowed": False,
            "writer_citable": False,
            "numeric_authority": "none",
            "public_instance_fallback_used": False,
            "paid_search_provider_selected": False,
        },
    }
    result = {**body, "result_digest": canonical_digest(body)}
    _write_json_atomic(runtime_root / "execution-result.json", result)
    _write_json_atomic(output_path, result)
    return result


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--proof", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = run_baseline(
            authority_path=Path(args.authority).resolve(),
            policy_path=Path(args.policy).resolve(),
            proof_path=Path(args.proof).resolve(),
            runtime_root=Path(args.runtime_root).resolve(),
            output_path=Path(args.output).resolve(),
        )
    except DiagnosticBaselineError as exc:
        print(json.dumps({"status": "blocked", "terminal_code": exc.code}))
        return 2
    # Windows PowerShell may expose a GBK stdout even though the result file is UTF-8.
    # Escaping non-ASCII here keeps post-terminal display from changing the process code.
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
