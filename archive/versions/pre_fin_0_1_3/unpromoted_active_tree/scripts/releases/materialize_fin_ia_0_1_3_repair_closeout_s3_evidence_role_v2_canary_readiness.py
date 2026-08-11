from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_readiness_v1_0.json"
ACTIVE = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_readiness_active_test_suite_successor_v1_0.json"
SOURCES = [
    "src/sec_agent/s3_evidence_role_canary_runtime.py",
    "scripts/releases/run_fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary.py",
    "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_policy_v1_0.json",
    "tests/contract/test_fin_0_1_3_repair_closeout_s3_evidence_role_v2_and_formal_anchor.py",
]


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha(ref: str) -> str:
    return hashlib.sha256((ROOT / ref).read_bytes()).hexdigest()


def main() -> None:
    body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_readiness_v1_0",
        "status": "single_node_natural_canary_engineering_ready_and_authorized",
        "owning_stage": "FIN_0_1_3_S3_FORMAL_ANCHOR",
        "authority_basis": {
            "user_instruction": "可以的，继续",
            "structural_disposition_ref": "configs/releases/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_disposition_v1_0.json",
            "selected_request_id": "FIN013-S2-DELL-demand_authenticity_and_sustainability",
            "maximum_provider_calls": 1,
            "retry_count": 0,
            "fallback_count": 0,
            "capture_first": True,
            "business_artifact_promotions": 0,
            "nine_call_replacement_authorized": False
        },
        "engineering_proof": {
            "fake_success": "1 call / 1 capture / boundary_only local claim / terminal",
            "same_admission_second_consumption": "fail_closed",
            "focused": "7 passed",
            "canonical": "249 passed / 1 historical assertion deselected",
            "model_provider_network_source_business_runs": [0, 0, 0, 0, 0]
        },
        "source_sha256": {ref: sha(ref) for ref in SOURCES},
        "execution_preconditions": ["clean_synced_git_head", "fresh_unexpired_admission", "credential_present", "shared_ledger_outside_runtime_root"],
        "success_disposition": "materialize_public_safe_result_then_decide_nine_call_replacement",
        "failure_disposition": "preserve_capture_and_terminal_stop_without_retry_or_full_replacement",
        "stage_boundary": {"formal_anchor_R1": "terminal_failed_preserved", "single_node_v2_canary_live": False, "nine_call_replacement": False, "formal_case_scores": 0, "paired": 0, "human_acceptance": 0, "S3_product_proof": False, "S4_entry": False, "release": False}
    }
    record = {**body, "record_digest": canonical(body)}
    OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    previous = json.loads((ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_active_test_suite_successor_v1_0.json").read_text(encoding="utf-8"))
    suite_body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_readiness_active_suite_v1_0",
        "suite_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S3-EVIDENCE-ROLE-V2-CANARY-READINESS-R22",
        "decision_ref": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "decision_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "selected_test_files": previous["selected_test_files"],
        "historical_event_time_deselections": previous["historical_event_time_deselections"],
        "observed_result": "249 passed / 1 historical assertion deselected",
        "status": "current_single_node_v2_natural_canary_authorized_not_executed",
        "stage_boundary": body["stage_boundary"]
    }
    ACTIVE.write_text(json.dumps({**suite_body, "suite_digest": canonical(suite_body)}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
