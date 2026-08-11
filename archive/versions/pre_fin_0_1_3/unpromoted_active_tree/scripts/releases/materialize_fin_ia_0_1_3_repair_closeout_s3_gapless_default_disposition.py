from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_gapless_local_default_and_raw_terminal_disposition_v1_0.json"
ACTIVE = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_gapless_local_default_active_test_suite_successor_v1_0.json"
SOURCES = [
    "src/sec_agent/s3_evidence_role_contract.py",
    "src/sec_agent/s3_formal_anchor_runtime.py",
    "src/sec_agent/s3_evidence_role_canary_runtime.py",
    "tests/contract/test_fin_0_1_3_repair_closeout_s3_evidence_role_v2_and_formal_anchor.py",
]


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s3_gapless_local_default_and_raw_terminal_disposition_v1_0",
        "status": "zero_call_structural_repair_pass_R3_authority_decision_next",
        "historical_R2_ref": "configs/releases/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_v2_r2_terminal_failure_v1_0.json",
        "repair": {
            "local_default_gap_condition": "provider_cannot_infer_and_zero_upstream_gap_options_only",
            "default_gap_bound_to": ["request_id", "decision_question", "compiled_context_digest"],
            "provider_authored_default_gap": False,
            "upstream_has_gap_but_provider_omits_it": "still_hard_fail",
            "typed_gap_requirement_relaxed": False,
            "model_visible_context_changed": False,
            "parsed_raw_output_saved_before_validation": True,
            "normalization_receipt_digest_bound": True
        },
        "verification": {
            "R2_MU_value_profit_raw_replay": "pass_with_one_local_default_gap",
            "existing_gap_omission_mutation": "fail_closed",
            "alias_overlap_mutation": "fail_closed",
            "nine_node_full_fake": "pass_to_Claim_Lead_Workpaper_quality_entry",
            "focused": "15 passed",
            "canonical": "249 passed / 1 historical assertion deselected",
            "model_provider_network_source_business_runs": [0, 0, 0, 0, 0]
        },
        "source_sha256": {
            ref: hashlib.sha256((ROOT / ref).read_bytes()).hexdigest()
            for ref in SOURCES
        },
        "authority": {
            "engineering_disposition": "pass",
            "R2_reclassified_or_replayed": False,
            "R3_admission_authorized": False,
            "automatic_retry": False,
            "formal_case_scores": 0,
            "paired": 0,
            "human_acceptance": 0
        },
        "stage_boundary": {
            "S3_formal_anchor_v2_R2": "terminal_failed_preserved",
            "gapless_local_default_successor": "zero_call_engineering_pass",
            "S3_product_proof": False,
            "S4_entry": False,
            "release": False
        },
        "next_action": "S3_FORMAL_ANCHOR_V2_R3_FRESH_ADMISSION_AUTHORITY_DECISION"
    }
    record = {**body, "record_digest": canonical(body)}
    OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    previous = json.loads((ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_v2_r2_failure_active_test_suite_successor_v1_0.json").read_text(encoding="utf-8"))
    suite_body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s3_gapless_local_default_active_suite_v1_0",
        "suite_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S3-GAPLESS-LOCAL-DEFAULT-R25",
        "decision_ref": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "decision_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "selected_test_files": previous["selected_test_files"],
        "historical_event_time_deselections": previous["historical_event_time_deselections"],
        "observed_result": "249 passed / 1 historical assertion deselected",
        "status": "current_gapless_local_default_zero_call_pass_R3_authority_decision_next",
        "stage_boundary": body["stage_boundary"]
    }
    ACTIVE.write_text(json.dumps({**suite_body, "suite_digest": canonical(suite_body)}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
