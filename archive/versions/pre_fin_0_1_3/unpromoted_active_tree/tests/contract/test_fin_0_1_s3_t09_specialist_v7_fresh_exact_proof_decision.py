from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s3_t09_owner_grade_specialist_v7_"
    "fresh_exact_proof_decision_v1_0.json"
)
BACKLOG = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_program_release_backlog_v2_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v7_decision_binds_exact_profile_transport_and_digest() -> None:
    from apps.workbench.backend.application.bounded_agent_contract_policies import (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF,
    )
    from apps.workbench.backend.application.bounded_agent_executor import (
        S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF,
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF,
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        S3ThreeCellBoundedAgentAdmission,
    )
    from sec_agent.canonical_runtime.models import canonical_digest

    prospective = _load(DECISION)["prospective_admission"]
    payload = prospective["payload"]
    admission = S3ThreeCellBoundedAgentAdmission(**payload)
    admission.assert_profile_admissible()

    assert canonical_digest(admission.digest_payload()) == prospective["digest"]
    assert payload["research_profile_ref"] == S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF
    assert payload["transport_ref"] == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
    )
    assert payload["research_lead_transport_ref"] == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF
    )
    assert payload["memo_writer_transport_ref"] == (
        S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF
    )


def test_v7_decision_factory_construction_is_zero_call() -> None:
    from apps.workbench.backend.application.bounded_agent_executor import (
        S3ThreeCellBoundedAgentAdmission,
        build_s3_three_cell_bounded_agent_executor_for_admission,
    )

    payload = _load(DECISION)["prospective_admission"]["payload"]
    callback_calls = 0

    def _must_not_call_provider(**_: object) -> dict:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider_callback_forbidden_in_decision_test")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        S3ThreeCellBoundedAgentAdmission(**payload),
        chat_completion_fn=_must_not_call_provider,
    )
    assert callback_calls == 0


def test_v7_decision_freezes_budget_stop_and_audit_boundaries() -> None:
    decision = _load(DECISION)
    budget = decision["budget_and_stop_contract"]
    audit = decision["audit_contract"]
    governance = decision["experiment_governance"]

    assert budget["semantic_model_calls"] == 12
    assert budget["provider_calls"] == 12
    assert budget["network_calls"] == 12
    assert budget["aggregate_max_output_tokens"] == 16800
    assert budget["max_total_cost_usd"] == 0.1
    assert budget["retry_budget"] == 0
    assert budget["automatic_repair_fallback_or_rerun"] is False
    assert audit["target_service_initialization_allowed"] is False
    assert audit["target_SQLite_access"] == "direct_mode_ro_or_digest_only"
    assert audit["service_backed_preparation"] == "disposable_clone_only"
    assert governance["admission_issuance_authorized"] is False
    assert governance["live_execution_authorized"] is False


def test_v7_decision_records_fresh_double_prepare_and_no_execution() -> None:
    decision = _load(DECISION)
    double_prepare = decision["double_prepare"]
    prospective = decision["prospective_admission"]

    assert double_prepare["equal"] is True
    assert double_prepare["clone_execution_counts_before"] == {
        "canonical_artifact_versions": 13,
        "canonical_attempts": 13,
        "canonical_research_run_versions": 13,
        "canonical_work_units": 13,
    }
    assert (
        double_prepare["clone_execution_counts_after"]
        == double_prepare["clone_execution_counts_before"]
    )
    assert decision["target_read_only_audit"]["canonical_database_file_unchanged"]
    assert decision["target_read_only_audit"]["canonical_object_tree_unchanged"]
    assert prospective["admission_issued"] is False
    assert prospective["admission_consumed"] is False
    assert prospective["execution_started"] is False
    assert set(decision["observed_counts"].values()) == {0}


def test_v7_decision_advances_only_to_separate_issuance_gate() -> None:
    decision = _load(DECISION)
    backlog = _load(BACKLOG)
    next_action = backlog["next_action"]

    assert decision["next_action"] == (
        "S3-T09-OWNER-GRADE-SPECIALIST-V7-FRESH-EXACT-ADMISSION-ISSUANCE"
    )
    assert next_action[
        "S3_T09_specialist_v7_fresh_exact_proof_decision_ref"
    ] == DECISION.relative_to(ROOT).as_posix()
    assert next_action["specialist_v7_fresh_agent_proof_decision_authorized"] is True
