from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
    S3_TYPED_VERIFIER_OUTPUT_CONTRACT_REFS,
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_output_v4_verifier_"
    "schema_drift_zero_call_root_cause_decision_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_output_v4_verifier_"
    "schema_alignment_zero_call_implementation_v1_0.json"
)
FAILED_LIVE = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_claim_fact_link_policy_"
    "fresh_exact_live_execution_result_v1_0.json"
)
PROOF = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_output_v4_verifier_"
    "schema_repair_fresh_exact_proof_decision_v1_0.json"
)
ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_"
    "output_v4_verifier_schema_repair_exact_admission_r1.json"
)
ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_output_v4_verifier_"
    "schema_repair_fresh_exact_admission_issuance_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_attributes_failure_to_project_not_provider() -> None:
    decision = _load(DECISION)
    root = decision["confirmed_project_owned_root_cause"]

    assert root["provider_followed_declared_schema"] is True
    assert root["provider_model_noncompliance_confirmed"] is False
    assert root["provider_request_finding_keys"] == [
        "layer",
        "status",
        "issues",
    ]
    assert set(root["local_validator_required_finding_keys"]) == {
        "layer",
        "status",
        "issue_codes",
        "artifact_or_claim_refs",
        "repair_owner",
    }
    assert set(decision["observed_counts"].values()) == {0}


def test_request_builder_and_validator_share_typed_contract_set() -> None:
    implementation = _load(IMPLEMENTATION)["implementation"]

    assert S3_TYPED_VERIFIER_OUTPUT_CONTRACT_REFS == frozenset(
        {
            S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
            S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
        }
    )
    assert implementation["request_builder_consumes_shared_predicate"] is True
    assert implementation["validator_consumes_shared_predicate"] is True
    assert implementation["validator_relaxed"] is False
    assert implementation["fixture_checks_required_output_schema"] is True


def test_historical_failed_live_truth_remains_immutable() -> None:
    result = _load(FAILED_LIVE)

    assert result["failure"]["provider_observed_finding_keys"] == [
        "issues",
        "layer",
        "status",
    ]
    assert result["canonical_terminal_truth"]["artifact_count"] == 0
    assert result["independent_root_cause_assessment"][
        "project_owned_prompt_validator_schema_drift_confirmed"
    ] is True


def test_repair_does_not_authorize_retry_or_second_replacement_live() -> None:
    decision = _load(DECISION)

    assert decision["authority"][
        "automatic_retry_fallback_or_second_replacement_live_authorized"
    ] is False
    assert decision["selected_minimum_repair_contract"][
        "legacy_output_v1_v2_finding_shape_unchanged"
    ] is True
    assert decision["selected_minimum_repair_contract"][
        "no_normalization_fallback_or_validator_relaxation"
    ] is True


def test_fresh_proof_binds_repair_and_new_exact_identity() -> None:
    proof = _load(PROOF)
    prospective = proof["prospective_admission"]

    assert proof["double_prepare"]["equal"] is True
    assert proof["freshness_and_nonreuse"]["work_unit_absent"] is True
    assert proof["freshness_and_nonreuse"]["attempt_absent"] is True
    assert proof["freshness_and_nonreuse"]["research_run_absent"] is True
    assert proof["target_read_only_audit"]["expected_prior_research_run_count"] == 19
    assert proof["verifier_schema_repair_acceptance_contract"][
        "request_and_validator_shared_typed_contract_set"
    ] is True
    assert prospective["digest"] == (
        "82568169d4bd99b5b65a1ce1993cdb25415168536e2ab3928206458acb62f1c5"
    )
    assert set(proof["observed_counts"].values()) == {0}


def test_issued_admission_is_exact_fresh_and_runner_loadable() -> None:
    proof = _load(PROOF)
    payload = _load(ADMISSION)
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    target = load_execution_target(ISSUANCE)

    admission.assert_profile_admissible()
    assert payload == proof["prospective_admission"]["payload"]
    assert canonical_digest(admission.digest_payload()) == (
        proof["prospective_admission"]["digest"]
    )
    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert issuance["authority"][
        "admission_consumption_or_exact_live_execution_authorized"
    ] is True
    assert issuance["issued_admission"]["consumed"] is False
    assert target.research_run_id == proof["identity"]["research_run_id"]
    assert _load_admission(ADMISSION, target) == admission
