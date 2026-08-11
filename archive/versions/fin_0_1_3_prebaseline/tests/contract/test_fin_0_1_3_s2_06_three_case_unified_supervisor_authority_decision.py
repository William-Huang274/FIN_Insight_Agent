from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "configs/releases/fin_ia_0_1_3_s2_06_three_case_unified_supervisor_authority_decision_v1_0.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load() -> dict:
    return json.loads(DECISION.read_text(encoding="utf-8"))


def test_decision_is_digest_bound_and_binds_immutable_three_case_result() -> None:
    decision = _load()
    body = {key: value for key, value in decision.items() if key != "decision_digest"}
    assert decision["decision_digest"] == canonical_digest(body)
    result = decision["baseline_binding"]["three_case_result"]
    result_path = ROOT / result["ref"]
    assert _sha(result_path) == result["sha256"]
    result_payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert result_payload["result_digest"] == result["result_digest"]


def test_unified_means_one_protocol_with_physically_isolated_case_views() -> None:
    decision = _load()
    protocol = decision["selected_protocol"]
    assert set(decision["baseline_binding"]["cases"]) == {"DELL", "MU", "NVDA"}
    assert "three physically isolated case executions" in protocol["campaign_semantics"]
    forbidden = " ".join(protocol["supervisor_forbidden_inputs"]).lower()
    assert "hidden gold" in forbidden
    assert "another case" in forbidden
    assert protocol["correction_execution"]["raw_candidate_mutation_allowed"] is False
    assert protocol["correction_execution"]["corrected_run_attempt_and_capture_identity_fresh"] is True


def test_call_and_cost_envelope_is_topology_bound_with_no_retry_or_fallback() -> None:
    envelope = _load()["selected_protocol"]["call_envelope"]
    assert envelope["maximum_supervisor_planner_calls_per_case"] == 1
    assert envelope["maximum_corrected_graph_calls_per_case"] == 10
    assert envelope["maximum_provider_calls_per_case"] == 11
    assert envelope["maximum_provider_calls_campaign"] == 33
    assert envelope["retry_count"] == envelope["fallback_count"] == 0
    assert envelope["provider_hopping"] is False
    assert envelope["admission_time_capacity_proof_required"] is True


def test_acceptance_keeps_autonomous_and_supervised_attribution_separate() -> None:
    decision = _load()
    gates = decision["acceptance_gates"]
    assert "evaluator v1.4 L1 equals 0 and L2 equals 0" in gates["per_case"]
    assert gates["formal_hidden_score_before_L1_L2_pass"] is False
    assert gates["business_promotion"] is False
    labels = gates["supervised_recoverability_labels"]
    assert "all three cases" in labels["proven"]
    assert "not all cases" in labels["partial"]


def test_decision_does_not_issue_or_execute_and_names_one_zero_call_package() -> None:
    decision = _load()
    authority = decision["authority"]
    assert authority["decision_authorized"] is True
    assert authority["implementation_authorized"] is False
    assert authority["admission_issuance_authorized"] is False
    assert authority["provider_execution_authorized"] is False
    assert len(decision["owned_blockers_before_issuance"]) == 4
    package = decision["only_allowed_next_package"]
    assert package["maximum_implementation_packages"] == 1
    assert package["model_provider_network_calls"] == [0, 0, 0]
    assert decision["verification"]["admissions_issued"] == 0
    assert decision["verification"]["corrected_candidates_created"] == 0
