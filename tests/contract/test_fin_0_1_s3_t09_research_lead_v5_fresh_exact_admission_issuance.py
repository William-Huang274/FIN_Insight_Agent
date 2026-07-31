from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_research_lead_v5_"
    "fresh_agent_proof_decision_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_"
    "research_lead_v5_exact_admission_r1.json"
)
ISSUANCE = RELEASES / (
    "fin_ia_0_1_s3_t09_research_lead_v5_"
    "fresh_exact_admission_issuance_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_issued_admission_is_exact_frozen_lead_v5_payload() -> None:
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
        "ac364bd6fccdd881e47bef72cec19d44b3eadb0c3de40befc041916d6c84e264"
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

    admission = S3ThreeCellBoundedAgentAdmission.model_validate(_load(ADMISSION))
    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    target = load_execution_target(ISSUANCE)
    loaded = _load_admission(ADMISSION, target)

    assert callback_calls == 0
    assert loaded.admission_id == admission.admission_id
    assert target.research_run_id == (
        "research_run_fin01_2aeba4619781fa9a56f55af0"
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
    assert preflight["target_execution_counts"] == [16, 16, 16, 13]
    assert preflight["canonical_database_sha256"] == (
        "3661afa25058ad8d83b86941ae01593c3eb2f53c55d0245fe32c907fd013ece7"
    )
    assert preflight["canonical_object_tree_sha256"] == (
        "c7d7eff7a5b2cf243baac7582a021d40273091a3d4821032799f323ecea206c3"
    )
    observed = issuance["observed_counts"]
    assert observed["new_admissions"] == 1
    assert set(
        value for key, value in observed.items() if key != "new_admissions"
    ) == {0}


def test_issuance_preserves_v5_capacity_and_product_boundaries() -> None:
    issuance = _load(ISSUANCE)
    envelope = issuance["execution_envelope"]
    capacity = issuance["capacity_contract"]
    acceptance = issuance["artifact_acceptance_contract"]

    assert envelope["maximum_semantic_model_calls"] == 12
    assert envelope["maximum_provider_calls"] == 12
    assert envelope["maximum_network_calls"] == 12
    assert envelope["maximum_output_tokens_total"] == 16800
    assert envelope["retry_budget"] == 0
    assert capacity["provider_raw_wire_utf8_byte_maximum"] == 8192
    assert capacity["canonical_alias_segment_utf8_byte_maximum"] == 6000
    assert capacity["local_expanded_hard_utf8_byte_maximum"] == 32768
    assert capacity["token_or_cost_increase_selected"] is False
    assert acceptance["success_requires_terminal_state"] == "succeeded"
    assert acceptance["success_requires_artifact_families"] == 9
    assert acceptance["transport_or_lead_only_green_is_success"] is False
    assert acceptance["complete_product_semantic_review_required_after_live_success"]


def test_issuance_snapshot_and_later_consumption_are_durably_traced() -> None:
    issuance = _load(ISSUANCE)
    next_action = _load(BACKLOG)["next_action"]

    assert issuance["next_action"] == (
        "S3-T09-OWNER-GRADE-RESEARCH-LEAD-V5-FRESH-EXACT-LIVE-EXECUTION"
    )
    assert issuance["authority"][
        "admission_consumption_or_exact_live_execution_authorized"
    ] is False
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False
    assert next_action[
        "S3_T09_research_lead_v5_fresh_exact_admission_issuance_ref"
    ] == ISSUANCE.relative_to(ROOT).as_posix()
    assert next_action[
        "research_lead_v5_fresh_exact_admission_issuance_authorized"
    ] is True
    assert next_action["research_lead_v5_fresh_exact_admission_issued"] is True
    assert next_action["research_lead_v5_fresh_exact_admission_consumed"] is True
    assert next_action["agent_rerun_authorized"] is False
