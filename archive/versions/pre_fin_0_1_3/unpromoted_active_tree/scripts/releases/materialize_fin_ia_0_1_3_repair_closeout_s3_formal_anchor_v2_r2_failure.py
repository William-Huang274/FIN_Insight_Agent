from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_v2_r2_terminal_failure_v1_0.json"
ACTIVE = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_v2_r2_failure_active_test_suite_successor_v1_0.json"


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal", type=Path, required=True)
    args = parser.parse_args()
    terminal = json.loads(args.terminal.read_text(encoding="utf-8"))
    rows = terminal["family_results"]
    capture_path = args.terminal.parent / rows[-1]["capture_ref"]
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    failed_raw = json.loads(capture["gateway_result"]["content"])
    if (
        terminal.get("status") != "terminal_failed_no_retry"
        or terminal.get("terminal_code") != "s3_formal_provider_output_contract_invalid:s3_evidence_selection_gap_required"
        or len(rows) != 5
        or len(terminal.get("skipped_request_ids") or []) != 4
        or terminal.get("retry_count") != 0
        or terminal.get("fallback_count") != 0
    ):
        raise RuntimeError("s3_formal_v2_r2_failure_shape_invalid")
    body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s3_formal_anchor_v2_r2_terminal_failure_v1_0",
        "status": "formal_anchor_v2_R2_terminal_failed_preserved_R3_not_authorized",
        "execution": {
            "execution_git_commit": "136225a9e5670cde7f984deceb1c53140325676c",
            "run_id": terminal["run_id"],
            "attempt_id": terminal["attempt_id"],
            "completed_calls": 5,
            "passed_calls": 4,
            "failed_call_index": 5,
            "failed_request_id": rows[-1]["request_id"],
            "skipped_request_ids": terminal["skipped_request_ids"],
            "terminal_code": terminal["terminal_code"],
            "terminal_result_digest": terminal["terminal_result_digest"],
            "usage": {
                key: sum(row["usage"][key] for row in rows)
                for key in ("input_tokens", "output_tokens", "total_tokens")
            },
            "retry_count": 0,
            "fallback_count": 0,
            "business_artifact_promotions": 0
        },
        "safe_passed_outputs": [
            {"request_id": row["request_id"], "provider_output": row["provider_output"], "capture_digest": row["capture_digest"]}
            for row in rows[:-1]
        ],
        "safe_failed_raw_output": failed_raw,
        "failed_capture_digest": rows[-1]["capture_digest"],
        "root_cause_disposition": {
            "provider_transport": "pass",
            "json_shape": "pass",
            "renamed_field_contract": "pass",
            "model_research_semantics": "honest_cannot_infer_for_HBM_economics_from_consolidated_facts",
            "upstream_request_gap_options": 0,
            "validator_rule": "cannot_infer_requires_typed_gap",
            "primary": "project_contract_has_no_local_default_typed_gap_when_provider_has_no_gap_option",
            "model_or_provider_incapacity_established": False
        },
        "authority": {
            "R2": "terminal_failed_preserved",
            "R3_or_retry_authorized": False,
            "automatic_replay": False,
            "successor_zero_call_disposition_only": True
        },
        "stage_boundary": {
            "S3_formal_anchor_v2_R2": "terminal_failed_no_retry",
            "formal_case_scores": 0,
            "paired": 0,
            "human_acceptance": 0,
            "S3_product_proof": False,
            "S4_entry": False,
            "release": False
        },
        "next_action": "S3_FORMAL_ANCHOR_V2_GAPLESS_REQUEST_LOCAL_DEFAULT_TYPED_GAP_AND_RAW_TERMINAL_PROJECTION_ZERO_CALL_DISPOSITION"
    }
    record = {**body, "record_digest": canonical(body)}
    OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    previous = json.loads((ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_result_active_test_suite_successor_v1_0.json").read_text(encoding="utf-8"))
    suite_body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s3_formal_anchor_v2_r2_failure_active_suite_v1_0",
        "suite_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S3-FORMAL-ANCHOR-V2-R2-FAILURE-R24",
        "decision_ref": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "decision_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "selected_test_files": previous["selected_test_files"],
        "historical_event_time_deselections": previous["historical_event_time_deselections"],
        "observed_result": "249 passed / 1 historical assertion deselected",
        "status": "current_formal_anchor_v2_R2_failed_zero_call_gap_disposition_next",
        "stage_boundary": body["stage_boundary"]
    }
    ACTIVE.write_text(json.dumps({**suite_body, "suite_digest": canonical(suite_body)}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
