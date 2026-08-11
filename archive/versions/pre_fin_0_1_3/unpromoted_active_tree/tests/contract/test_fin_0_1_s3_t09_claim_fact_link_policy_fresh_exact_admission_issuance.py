from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_claim_fact_link_policy_"
    "fresh_agent_proof_decision_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_"
    "claim_fact_link_policy_exact_admission_r1.json"
)
ISSUANCE = RELEASES / (
    "fin_ia_0_1_s3_t09_claim_fact_link_policy_"
    "fresh_exact_admission_issuance_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_issued_admission_is_exact_frozen_policy_payload() -> None:
    from apps.workbench.backend.application.bounded_agent_contract_policies import (
        S3_CLAIM_FACT_LINK_POLICY_REF,
    )
    from apps.workbench.backend.application.bounded_agent_executor import (
        S3ThreeCellBoundedAgentAdmission,
    )
    from sec_agent.canonical_runtime.models import canonical_digest

    decision = _load(DECISION)
    payload = _load(ADMISSION)
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()

    assert payload == decision["prospective_admission"]["payload"]
    digest = canonical_digest(admission.digest_payload())
    assert digest == decision["prospective_admission"]["digest"]
    assert digest == issuance["issued_admission"]["admission_digest"]
    assert digest == (
        "65bcbedfa6d68f6932130aaffdddec5580abc8c4e683e0e5523e1da49b0b128d"
    )
    assert admission.claim_fact_link_policy_ref == (
        S3_CLAIM_FACT_LINK_POLICY_REF
    )


def test_issuance_factory_and_runner_load_are_zero_call() -> None:
    from apps.workbench.backend.application.bounded_agent_executor import (
        S3ThreeCellBoundedAgentAdmission,
        build_s3_three_cell_bounded_agent_executor_for_admission,
    )
    from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
        _load_admission,
        load_execution_target,
    )

    callback_calls = 0

    def _must_not_call_provider(**_: object) -> dict:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider_callback_forbidden_in_issuance_test")

    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(ADMISSION)
    )
    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    target = load_execution_target(ISSUANCE)
    loaded = _load_admission(ADMISSION, target)

    assert callback_calls == 0
    assert loaded.admission_id == admission.admission_id
    assert target.research_run_id == (
        "research_run_fin01_0c4247687b5e4ee13c352d11"
    )


def test_issuance_records_read_only_freshness_snapshot() -> None:
    issuance = _load(ISSUANCE)
    preflight = issuance["zero_call_preflight"]

    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False
    assert issuance["authority"][
        "admission_consumption_or_exact_live_execution_authorized"
    ] is False
    assert preflight["fresh_predicted_work_unit_attempt_run_absent"]
    assert preflight["target_execution_counts"] == {
        "canonical_artifact_versions": 13,
        "canonical_attempts": 18,
        "canonical_research_run_versions": 18,
        "canonical_work_units": 18,
    }
    assert preflight["canonical_database_sha256"] == (
        "88dec30df4fe30aed9f76dc3eec1dbbef7bd0a2fd32a043c968db64c16f0cf03"
    )
    assert preflight["canonical_object_tree_sha256"] == (
        "23852c76f26a2749a59cdab150944fa761b4820ff2ca44baf3b39ca7b0d610db"
    )
    observed = issuance["observed_counts"]
    assert observed["new_admissions"] == 1
    assert set(
        value for key, value in observed.items() if key != "new_admissions"
    ) == {0}


def test_issuance_preserves_policy_product_and_stop_boundaries() -> None:
    issuance = _load(ISSUANCE)
    envelope = issuance["execution_envelope"]
    link = issuance["claim_fact_link_live_acceptance_contract"]
    product = issuance["artifact_acceptance_contract"]

    assert envelope["maximum_semantic_model_calls"] == 12
    assert envelope["maximum_provider_calls"] == 12
    assert envelope["maximum_network_calls"] == 12
    assert envelope["maximum_output_tokens_total"] == 16800
    assert envelope["retry_budget"] == 0
    assert envelope["first_credible_failure"] == "terminal_fail_closed_stop"
    assert link["provider_response_support_field"] == "support_fact_aliases"
    assert link["provider_support_fact_ids_when_policy_active_allowed"] is False
    assert link["persisted_alias_residue_required"] == 0
    assert link["persisted_source_ref_as_claim_support_required"] == 0
    assert product["success_requires_terminal_state"] == "succeeded"
    assert product["success_requires_logical_nodes"] == 6
    assert product["success_requires_provider_calls"] == 12
    assert product["success_requires_artifact_families"] == 9
    assert product["transport_or_specialist_only_green_is_success"] is False


def test_issuance_remains_traced_after_exact_live_execution_gate() -> None:
    issuance = _load(ISSUANCE)
    next_action = _load(BACKLOG)["next_action"]

    assert issuance["next_action"] == (
        "S3-T09-GENERALIZED-CLAIM-FACT-LINK-POLICY-"
        "FRESH-EXACT-LIVE-EXECUTION"
    )
    assert issuance["authority"][
        "admission_consumption_or_exact_live_execution_authorized"
    ] is False
    assert next_action["item_id"]
    assert next_action[
        "S3_T09_claim_fact_link_policy_fresh_exact_admission_issuance_ref"
    ] == ISSUANCE.relative_to(ROOT).as_posix()
    assert next_action[
        "claim_fact_link_exact_admission_issuance_authorized"
    ] is True
    assert next_action["claim_fact_link_exact_admission_issued"] is True
    assert next_action["claim_fact_link_exact_admission_consumed"] is True
    assert next_action["claim_fact_link_live_execution_authorized"] is True
    assert next_action["claim_fact_link_second_execution_authorized"] is False
    assert next_action["agent_execution_authorized"] is False
