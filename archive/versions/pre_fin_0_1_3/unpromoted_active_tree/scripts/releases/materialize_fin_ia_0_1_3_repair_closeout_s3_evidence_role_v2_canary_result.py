from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_result_and_replacement_authority_v1_0.json"
ACTIVE = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_result_active_test_suite_successor_v1_0.json"


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal", type=Path, required=True)
    args = parser.parse_args()
    terminal = json.loads(args.terminal.read_text(encoding="utf-8"))
    output = terminal["provider_output"]
    roles = terminal["local_claim"]["evidence_role_projection"]
    if (
        terminal.get("status") != "terminal_succeeded_exact_once"
        or terminal.get("completed_calls") != 1
        or terminal.get("retry_count") != 0
        or terminal.get("fallback_count") != 0
        or terminal.get("business_artifact_promotions") != 0
        or roles.get("thesis_support")
        or roles.get("observation_support")
        or roles.get("boundary_only") != ["DELL_E01"]
    ):
        raise RuntimeError("s3_evidence_role_canary_terminal_not_eligible")
    body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_result_and_replacement_authority_v1_0",
        "status": "single_node_natural_canary_pass_closed_one_nine_call_replacement_authorized",
        "execution": {
            "execution_git_commit": "cd041665cbf20cf7c5fded8ca44b26320792fd90",
            "run_id": terminal["run_id"],
            "attempt_id": terminal["attempt_id"],
            "request_id": terminal["request_id"],
            "completed_calls": 1,
            "capture_digest": terminal["capture_digest"],
            "terminal_result_digest": terminal["terminal_result_digest"],
            "finish_reason": terminal["finish_reason"],
            "usage": terminal["usage"],
            "retry_count": 0,
            "fallback_count": 0,
            "business_artifact_promotions": 0
        },
        "safe_natural_output": output,
        "local_evidence_role_projection": roles,
        "result_disposition": {
            "renamed_schema_natural_adherence": "pass_one_DELL_demand_request",
            "cannot_infer_typed_gap_retained": True,
            "observation_promoted_to_thesis_support": False,
            "broad_nine_request_model_quality_proven": False,
            "formal_content_quality_proven": False
        },
        "authority": {
            "canary": "pass_closed",
            "one_fresh_nine_call_v2_replacement_admission": True,
            "maximum_replacement_admissions": 1,
            "automatic_retry_or_R3": False,
            "success_only_successor_materialization": True,
            "first_credible_failure_stops": True
        },
        "stage_boundary": {
            "formal_anchor_R1": "terminal_failed_preserved",
            "v2_single_node_canary": "pass_closed",
            "v2_nine_call_replacement": "authorized_not_executed",
            "formal_case_scores": 0,
            "paired": 0,
            "human_acceptance": 0,
            "S3_product_proof": False,
            "S4_entry": False,
            "release": False
        },
        "next_action": "COMMIT_PUSH_THEN_ISSUE_ONE_FRESH_S3_FORMAL_ANCHOR_V2_NINE_CALL_REPLACEMENT_ADMISSION_AND_EXECUTE_EXACT_ONCE"
    }
    record = {**body, "record_digest": canonical(body)}
    OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    previous = json.loads((ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_readiness_active_test_suite_successor_v1_0.json").read_text(encoding="utf-8"))
    suite_body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_result_active_suite_v1_0",
        "suite_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S3-EVIDENCE-ROLE-V2-CANARY-RESULT-R23",
        "decision_ref": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "decision_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "selected_test_files": previous["selected_test_files"],
        "historical_event_time_deselections": previous["historical_event_time_deselections"],
        "observed_result": "249 passed / 1 historical assertion deselected",
        "status": "current_v2_canary_pass_one_nine_call_replacement_authorized_not_executed",
        "stage_boundary": body["stage_boundary"]
    }
    ACTIVE.write_text(json.dumps({**suite_body, "suite_digest": canonical(suite_body)}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
