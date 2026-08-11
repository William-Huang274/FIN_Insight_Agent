from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402
from sec_agent.s2_context_yield_program import S2ContextYieldError, validate_compact_provider_output  # noqa: E402


DEFAULT_RUNTIME = ROOT / ".codex_runtime/fin013-s3-formal-anchor-r1/execution"
DEFAULT_ADMISSION = ROOT / ".codex_runtime/fin013-s3-formal-anchor-r1/admission.json"
CONTEXT_PROGRAM = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s2_03_context_yield_and_capacity_zero_call_v1_0.json"
OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_r1_terminal_failure_v1_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--admission", type=Path, default=DEFAULT_ADMISSION)
    args = parser.parse_args()
    terminal = _load(args.runtime_root / "terminal_result.json")
    admission = _load(args.admission)
    captures = sorted((args.runtime_root / "captures").glob("*.json"))
    if terminal.get("status") != "terminal_failed_no_retry" or terminal.get("completed_calls") != 1 or len(captures) != 1:
        raise RuntimeError("s3_formal_r1_failure_surface_invalid")
    capture = _load(captures[0])
    output = json.loads(capture["gateway_result"]["content"])
    contexts = {row["request_id"]: row for row in _load(CONTEXT_PROGRAM)["role_scoped_contexts"]}
    actual_code = None
    try:
        validate_compact_provider_output(output, compiled=contexts[capture["request_id"]])
    except S2ContextYieldError as exc:
        actual_code = exc.code
    if actual_code != "s2_compact_output_cannot_infer_support":
        raise RuntimeError("s3_formal_r1_actual_failure_not_reproduced")
    record = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s3_formal_anchor_r1_terminal_failure_v1_0",
        "recorded_at": "2026-08-06T19:35:00+08:00",
        "status": "terminal_failed_no_retry_preserved",
        "authority": {
            "execution_git_commit": admission["execution_git_commit"],
            "admission_digest": admission["admission_digest"],
            "run_id": admission["run_id"],
            "attempt_id": admission["attempt_id"],
            "replacement_or_second_run_authorized": False,
        },
        "execution": {
            "provider": admission["provider"]["backend"],
            "model": admission["provider"]["model"],
            "completed_calls": terminal["completed_calls"],
            "skipped_requests": len(terminal["skipped_request_ids"]),
            "retry_count": terminal["retry_count"],
            "fallback_count": terminal["fallback_count"],
            "terminal_result_digest": terminal["terminal_result_digest"],
            "raw_capture_digest": capture["capture_digest"] if "capture_digest" in capture else canonical_digest(capture),
            "finish_reason": capture["gateway_result"]["finish_reason"],
            "usage": {
                "input_tokens": capture["gateway_result"]["input_tokens"],
                "output_tokens": capture["gateway_result"]["output_tokens"],
                "total_tokens": capture["gateway_result"]["total_tokens"],
                "transport_attempt_count": capture["gateway_result"]["transport_attempt_count"],
            },
        },
        "safe_provider_output": output,
        "classification_correction": {
            "immutable_terminal_code": terminal["terminal_code"],
            "actual_failure_family": "valid_JSON_but_semantically_inconsistent_bounded_judgment",
            "actual_failure_code": actual_code,
            "detail": "Provider selected cannot_infer while retaining a non-empty support_aliases list. The original runtime caught S2ContextYieldError through ValueError and mislabeled it as JSON invalid; the historical terminal remains immutable and the successor classifier is corrected.",
            "model_or_provider_contract_adherence_failure_established": True,
            "project_runtime_error_classification_defect_established": True,
        },
        "promotion_boundary": {
            "claims_materialized": 0,
            "lead_workpaper_or_quality_scores_materialized": 0,
            "business_artifacts_promoted": 0,
            "qualified_human_acceptance": False,
            "S3_product_proof": False,
        },
        "model_provider_network_source_business_runs": [1, 1, 1, 0, 0],
        "known_boundary": "The first formal Anchor attempt is a valid failed proof. It establishes one bounded semantic contract failure and one local error-classification defect; it does not establish that all DeepSeek requests fail, and it does not authorize an automatic replacement run.",
        "current_next": "S3_FORMAL_ANCHOR_R1_FIRST_CREDIBLE_FAILURE_ROOT_CAUSE_AND_REPLACEMENT_DISPOSITION_DECISION",
    }
    record["record_digest"] = canonical_digest(record)
    OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": record["status"], "output": str(OUTPUT), "record_digest": record["record_digest"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
