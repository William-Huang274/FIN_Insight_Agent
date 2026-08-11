from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "configs/releases/fin_ia_0_1_3_s2_06_three_case_supervisor_admission_authority_decision_v1_0.json"
PROOF = ROOT / "configs/releases/fin_ia_0_1_3_s2_06_unified_supervisor_independent_fresh_zero_call_proof_result_v1_0.json"
IMPLEMENTATION = ROOT / "configs/releases/fin_ia_0_1_3_s2_06_three_case_unified_supervisor_zero_call_implementation_v1_0.json"
PREDECESSOR = ROOT / "configs/releases/fin_ia_0_1_3_s2_06_three_case_unified_supervisor_authority_decision_v1_0.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest_without_decision_digest(payload: dict) -> str:
    body = {key: value for key, value in payload.items() if key != "decision_digest"}
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_authority_binds_the_closed_implementation_and_independent_fresh_proof() -> None:
    decision = _read(DECISION)
    proof = _read(PROOF)
    implementation = _read(IMPLEMENTATION)

    assert decision["status"] == "authority_pass_bounded_sequential_campaign_approved_admissions_unissued_execution_not_started"
    assert decision["authority"]["decision_outcome"] == "approve_bounded_sequential_three_case_campaign"
    assert decision["evidence_binding"]["predecessor_authority"]["sha256"] == _sha256(PREDECESSOR)
    assert decision["evidence_binding"]["shared_implementation"]["sha256"] == _sha256(IMPLEMENTATION)
    assert decision["evidence_binding"]["shared_implementation"]["implementation_digest"] == implementation["implementation_digest"]
    assert decision["evidence_binding"]["independent_fresh_proof"]["sha256"] == _sha256(PROOF)
    assert decision["evidence_binding"]["independent_fresh_proof"]["result_digest"] == proof["result_digest"]
    assert proof["status"].startswith("pass_")
    assert proof["independent_proof"]["worker_result"]["raw_inputs_unchanged"]
    assert proof["independent_proof"]["worker_result"]["hard_boundaries"]["real_provider_calls"] == 0
    assert decision["decision_digest"] == _digest_without_decision_digest(decision)


def test_campaign_is_three_physical_cases_not_three_provider_calls() -> None:
    decision = _read(DECISION)
    campaign = decision["campaign_contract"]
    capacity = decision["case_capacity"]
    proof_matrix = _read(PROOF)["independent_proof"]["worker_result"]["real_frozen_input_matrix"]

    assert campaign["case_order"] == ["DELL", "MU", "NVDA"]
    assert campaign["expected_provider_calls"] == {"DELL": 8, "MU": 10, "NVDA": 10, "campaign": 28}
    assert campaign["hard_provider_call_ceiling"] == {"per_case": 11, "campaign": 33}
    assert campaign["retry_count"] == 0
    assert campaign["fallback_count"] == 0
    for case_key in campaign["case_order"]:
        assert capacity[case_key]["provider_calls"] == proof_matrix[case_key]["provider_calls"]
        assert capacity[case_key]["supervisor_request_characters"] == proof_matrix[case_key]["supervisor_request_characters"]
        assert capacity[case_key]["pass"]


def test_decision_does_not_issue_execute_score_or_promote() -> None:
    decision = _read(DECISION)
    authority = decision["authority"]
    verification = decision["verification"]

    assert authority["case_admission_issuance_eligible_after_clean_synced_preflight"]
    assert authority["admissions_issued_in_this_decision"] == 0
    assert authority["provider_calls_in_this_decision"] == 0
    assert authority["provider_execution_started"] is False
    assert authority["automatic_execution_from_this_decision"] is False
    activity_fields = [
        "model_calls",
        "provider_calls",
        "network_calls",
        "source_calls",
        "admissions_issued",
        "admissions_consumed",
        "corrected_candidates",
        "hidden_scores",
        "business_promotions",
        "raw_mutations",
    ]
    assert all(verification[field] == 0 for field in activity_fields)
    assert decision["acceptance"]["business_promotion"] is False
    assert decision["acceptance"]["release_qualification"] is False
    assert decision["next_action_authorized_automatically"] is False


def test_failure_isolation_forbids_retry_and_live_patch_loops() -> None:
    decision = _read(DECISION)
    rules = decision["execution_and_stop_rules"]

    assert rules["shared_infrastructure_or_security_failure"].startswith("stop_campaign")
    assert "without_retry_or_prompt_patch" in rules["case_local_model_schema_or_semantic_failure"]
    assert rules["field_by_field_live_patch_loop"] == "forbidden"
    assert rules["maximum_structural_repair_packages_after_campaign"] == 1
    assert decision["portability_boundary"]["same_host_campaign_blocked"] is False
    assert decision["portability_boundary"]["cross_platform_or_release_claim_blocked"] is True
