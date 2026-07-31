from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_specialist_v7_"
    "fresh_exact_proof_decision_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_"
    "specialist_v7_research_lead_v3_writer_v2_exact_admission_v1_0.json"
)
ISSUANCE = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_specialist_v7_"
    "fresh_exact_admission_issuance_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v7_issued_admission_is_exact_frozen_decision_payload() -> None:
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


def test_v7_issuance_constructs_factory_without_provider_call() -> None:
    from apps.workbench.backend.application.bounded_agent_executor import (
        S3ThreeCellBoundedAgentAdmission,
        build_s3_three_cell_bounded_agent_executor_for_admission,
    )

    callback_calls = 0

    def _must_not_call_provider(**_: object) -> dict:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider_callback_forbidden_in_issuance_test")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        S3ThreeCellBoundedAgentAdmission.model_validate(_load(ADMISSION)),
        chat_completion_fn=_must_not_call_provider,
    )
    assert callback_calls == 0


def test_v7_issuance_is_unconsumed_and_records_zero_execution() -> None:
    issuance = _load(ISSUANCE)

    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False
    assert issuance["authority"][
        "admission_consumption_or_exact_live_execution_authorized"
    ] is False
    assert issuance["zero_call_preflight"]["provider_callback_invoked"] is False
    assert issuance["zero_call_preflight"]["target_execution_counts"] == [
        13,
        13,
        13,
        13,
    ]
    observed = issuance["observed_counts"]
    assert observed["new_admissions"] == 1
    assert set(
        value
        for key, value in observed.items()
        if key != "new_admissions"
    ) == {0}


def test_v7_issuance_keeps_live_execution_precondition_explicit() -> None:
    issuance = _load(ISSUANCE)
    envelope = issuance["execution_envelope"]

    assert issuance["zero_call_preflight"][
        "exact_live_execution_precondition"
    ] == "LLM_GATEWAY_TRANSPORT_RETRIES must equal 0"
    assert envelope["maximum_semantic_model_calls"] == 12
    assert envelope["maximum_provider_calls"] == 12
    assert envelope["maximum_network_calls"] == 12
    assert envelope["maximum_output_tokens_total"] == 16800
    assert envelope["maximum_total_cost_usd"] == 0.1
    assert envelope["retry_budget"] == 0
    assert envelope["automatic_retry_repair_fallback_or_rerun_allowed"] is False


def test_v7_issuance_advances_only_to_separate_exact_live_gate() -> None:
    issuance = _load(ISSUANCE)
    next_action = _load(BACKLOG)["next_action"]

    assert issuance["next_action"] == (
        "S3-T09-OWNER-GRADE-SPECIALIST-V7-FRESH-EXACT-LIVE-EXECUTION"
    )
    assert next_action[
        "S3_T09_specialist_v7_fresh_exact_admission_issuance_ref"
    ] == ISSUANCE.relative_to(ROOT).as_posix()
    assert next_action["specialist_v7_exact_admission_issuance_authorized"] is True
    assert next_action["specialist_v7_exact_admission_issued"] is True
