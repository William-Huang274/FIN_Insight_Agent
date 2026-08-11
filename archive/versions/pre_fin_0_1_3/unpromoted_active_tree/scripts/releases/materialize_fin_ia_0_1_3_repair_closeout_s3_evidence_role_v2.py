from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_disposition_v1_0.json"
ACTIVE = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_active_test_suite_successor_v1_0.json"
R1 = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_r1_terminal_failure_v1_0.json"
FILES = [
    "src/sec_agent/s3_evidence_role_contract.py",
    "src/sec_agent/s3_formal_anchor_runtime.py",
    "src/sec_agent/s3_claim_quality_program.py",
    "scripts/releases/run_fin_ia_0_1_3_repair_closeout_s3_formal_anchor_v2.py",
    "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_evidence_role_contract_v2_0.json",
    "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_execution_policy_v2_0.json",
    "tests/contract/test_fin_0_1_3_repair_closeout_s3_evidence_role_v2_and_formal_anchor.py",
]


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    r1 = json.loads(R1.read_text(encoding="utf-8"))
    body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_disposition_v1_0",
        "status": "zero_call_structural_root_cause_repaired_single_node_canary_next",
        "owning_stage": "FIN_0_1_3_S3_FORMAL_ANCHOR",
        "historical_failure_ref": str(R1.relative_to(ROOT)).replace("\\", "/"),
        "historical_failure_record_digest": r1["record_digest"],
        "root_cause_disposition": {
            "primary": "project_contract_conflated_observation_selection_with_thesis_support",
            "R1_output_research_semantics": "plausible_observation_plus_honest_cannot_infer_boundary",
            "broad_DeepSeek_incapacity_established": False,
            "provider_transport_fault_established": False,
            "old_contract_violation_remains_true": True,
            "R1_reclassified_or_promoted": False,
            "successor_contract_changed": True
        },
        "successor_contract": {
            "contract_ref": "fin_0_1_3.S3.evidence_selection_and_local_role_projection:v2",
            "provider_selects": ["evidence_alias", "counterevidence_alias", "gap_alias", "mechanism_alias", "what_would_change_alias"],
            "local_roles": ["observation_support", "thesis_support", "boundary_only", "counterevidence"],
            "cannot_infer_observation_rule": "selected observations are boundary_only and cannot become thesis_support",
            "numbers_dates_identity_lineage_narrative_local": True
        },
        "verification": {
            "R1_shape_replayed_as_v2": "pass_boundary_only",
            "focused_S3_successor": "39 passed",
            "canonical_active_suite": "247 passed / 1 historical assertion deselected",
            "full_fake": {
                "calls": 9,
                "captures": 9,
                "natural_claims": 9,
                "all_natural_leads": 3,
                "all_natural_workpapers": 3,
                "quality_entries": 3
            },
            "mutations": ["missing_gap", "evidence_counterevidence_overlap", "role_projection_tamper", "cross_contract_context"],
            "model_provider_network_source_business_runs": [0, 0, 0, 0, 0]
        },
        "source_sha256": {ref: sha(ROOT / ref) for ref in FILES},
        "authority": {
            "engineering_disposition": "pass",
            "single_node_natural_canary_required": True,
            "single_node_canary_authorized_by_this_record": False,
            "nine_call_replacement_authorized": False,
            "automatic_R2": False,
            "formal_case_scores": 0,
            "paired_assessments": 0,
            "qualified_human_content_acceptances": 0
        },
        "stage_boundary": {
            "S0": "pass_closed",
            "S1": "pass_closed",
            "S2": "pass_closed_immutable_v1",
            "S3_deterministic": "engineering_pass",
            "formal_anchor_R1": "terminal_failed_preserved",
            "evidence_role_v2": "zero_call_engineering_pass",
            "S3_product_proof": False,
            "S4_entry": False,
            "release": False
        },
        "next_action": "ISSUE_ONE_FRESH_DELL_DEMAND_EVIDENCE_ROLE_V2_SINGLE_NODE_NATURAL_CANARY"
    }
    decision = {**body, "record_digest": digest(body)}
    write(DECISION, decision)
    selected = json.loads((ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_r1_failure_active_test_suite_successor_v1_0.json").read_text(encoding="utf-8"))["selected_test_files"]
    selected.append("tests/contract/test_fin_0_1_3_repair_closeout_s3_evidence_role_v2_and_formal_anchor.py")
    suite_body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_active_test_suite_successor_v1_0",
        "suite_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S3-EVIDENCE-ROLE-V2-ACTIVE-SUITE-R21",
        "decision_ref": str(DECISION.relative_to(ROOT)).replace("\\", "/"),
        "decision_sha256": sha(DECISION),
        "selected_test_files": selected,
        "historical_event_time_deselections": ["tests/contract/test_fin_0_1_3_repair_closeout_s0_02_shared_runtime_admission_replay_and_historical_proof_debt.py::test_decision_and_active_suite_are_digest_bound_and_do_not_promote_old_names"],
        "observed_result": "247 passed / 1 historical assertion deselected",
        "status": "current_S3_evidence_role_v2_zero_call_pass_single_node_natural_canary_next",
        "stage_boundary": body["stage_boundary"]
    }
    write(ACTIVE, {**suite_body, "suite_digest": digest(suite_body)})


if __name__ == "__main__":
    main()
