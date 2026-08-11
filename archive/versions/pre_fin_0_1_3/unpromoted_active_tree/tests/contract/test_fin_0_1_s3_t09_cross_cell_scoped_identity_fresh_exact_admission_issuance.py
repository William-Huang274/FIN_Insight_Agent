from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_cross_cell_scoped_identity_"
    "fresh_agent_proof_decision_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_cross_cell_"
    "scoped_identity_output_v4_exact_admission_r1.json"
)
ISSUANCE = RELEASES / (
    "fin_ia_0_1_s3_t09_cross_cell_scoped_identity_"
    "fresh_exact_admission_issuance_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
LIVE_RESULT = RELEASES / (
    "fin_ia_0_1_s3_t09_cross_cell_scoped_identity_"
    "fresh_live_execution_result_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_issued_admission_is_exact_frozen_output_v4_payload() -> None:
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
        "ba3642d023209208cb90ebfd4295fe00291fae27cbc382561d81d8a4f0aa8973"
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
        "research_run_fin01_389411049b562ebd57000528"
    )


def test_issuance_snapshot_remains_valid_after_separate_exact_live_consumption() -> None:
    from scripts.releases.issue_fin_ia_0_1_s3_t09_owner_grade_specialist_v7_exact_admission import (
        _target_snapshot,
    )
    from scripts.releases.prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
        _sha256,
        _tree_digest,
    )

    decision = _load(DECISION)
    issuance = _load(ISSUANCE)
    live_result = _load(LIVE_RESULT)
    runtime_root = ROOT / issuance["issued_admission"]["runtime_root"]
    database_path = runtime_root / "canonical-runtime" / "canonical.sqlite"
    object_root = runtime_root / "canonical-runtime" / "objects"
    snapshot = _target_snapshot(database_path, identity=decision["identity"])

    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False
    assert issuance["authority"][
        "admission_consumption_or_exact_live_execution_authorized"
    ] is False
    assert issuance["zero_call_preflight"]["fresh_predicted_work_unit_attempt_run_absent"]
    assert issuance["zero_call_preflight"]["target_execution_counts"] == [
        15,
        15,
        15,
        13,
    ]
    assert snapshot["prospective_identity_rows"] == {
        "canonical_work_units": 3,
        "canonical_attempts": 2,
        "canonical_research_run_versions": 2,
    }
    assert all(
        current >= historical
        for current, historical in zip(
            snapshot["counts"].values(),
            [16, 16, 16, 13],
            strict=True,
        )
    )
    assert len(_sha256(database_path)) == 64
    assert len(_tree_digest(object_root)) == 64
    assert len(
        live_result["runtime_integrity"]["canonical_database_sha256_after"]
    ) == 64
    assert len(
        live_result["runtime_integrity"][
            "canonical_object_tree_sha256_after"
        ]
    ) == 64
    observed = issuance["observed_counts"]
    assert observed["new_admissions"] == 1
    assert set(
        value for key, value in observed.items() if key != "new_admissions"
    ) == {0}


def test_issuance_preserves_execution_and_product_acceptance_boundaries() -> None:
    issuance = _load(ISSUANCE)
    envelope = issuance["execution_envelope"]
    acceptance = issuance["artifact_acceptance_contract"]

    assert issuance["zero_call_preflight"][
        "transport_retry_environment_zero"
    ] is False
    assert issuance["zero_call_preflight"][
        "exact_live_execution_precondition"
    ] == "LLM_GATEWAY_TRANSPORT_RETRIES must equal 0"
    assert envelope["maximum_semantic_model_calls"] == 12
    assert envelope["maximum_provider_calls"] == 12
    assert envelope["maximum_network_calls"] == 12
    assert envelope["maximum_output_tokens_total"] == 16800
    assert envelope["retry_budget"] == 0
    assert acceptance["success_requires_terminal_state"] == "succeeded"
    assert acceptance["success_requires_artifact_families"] == 9
    assert acceptance["transport_only_green_is_success"] is False


def test_issuance_remains_traced_after_exact_live_failure() -> None:
    issuance = _load(ISSUANCE)
    next_action = _load(BACKLOG)["next_action"]

    assert issuance["next_action"] == (
        "S3-T09-OWNER-GRADE-CROSS-CELL-SCOPED-IDENTITY-"
        "FRESH-EXACT-LIVE-EXECUTION"
    )
    assert next_action["item_id"]
    assert next_action[
        "S3_T09_cross_cell_scoped_identity_fresh_exact_admission_issuance_ref"
    ] == ISSUANCE.relative_to(ROOT).as_posix()
    assert next_action[
        "cross_cell_scoped_identity_fresh_exact_admission_issuance_authorized"
    ] is True
    assert next_action[
        "cross_cell_scoped_identity_fresh_exact_admission_issued"
    ] is True
    assert next_action[
        "cross_cell_scoped_identity_fresh_exact_admission_consumed"
    ] is True
    assert next_action[
        "cross_cell_scoped_identity_fresh_live_execution_authorized"
    ] is True
    assert next_action[
        "cross_cell_scoped_identity_research_lead_v4_capacity_recurrence_root_cause_decision_authorized"
    ] is True
    assert next_action["cross_cell_scoped_identity_agent_rerun_authorized"] is False
