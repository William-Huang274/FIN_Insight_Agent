from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (  # noqa: E402
    _load_admission,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_fresh_exact_live_execution_"
    "and_success_only_paired_assessment_authority_decision_v1_0.json"
)
CANONICAL_DATABASE = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-"
    "live-validation-r1/canonical-runtime/canonical.sqlite"
)
NEXT_ACTION = (
    "S4-T06-MU-FRESH-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-"
    "PAIRED-ASSESSMENT"
)
EXECUTION_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_fresh_exact_live_"
    "execution_failure_result_v1_0.json"
)
CURRENT_RUNTIME_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_minimum_zero_call_"
    "implementation_v1_0.json"
)
CURRENT_IDENTITY_BOUNDARY_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_current_case_aware_"
    "delivery_identity_boundary_scope_replacement_minimum_zero_call_"
    "implementation_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_historical_or_current(
    relative_path: str,
    historical_sha256: str,
) -> None:
    observed = _sha256(ROOT / relative_path)
    if observed == historical_sha256:
        return
    identity_boundary = _load(
        CURRENT_IDENTITY_BOUNDARY_IMPLEMENTATION
    )
    if (
        identity_boundary["exact_code_bindings"].get(relative_path)
        == observed
    ):
        return
    current = _load(CURRENT_RUNTIME_IMPLEMENTATION)
    assert relative_path in current[
        "historical_exact_binding_supersession"
    ]["allowed_changed_paths"]
    assert current["exact_code_bindings"][relative_path] == observed


def _case_rows(table: str, case_id: str) -> list[dict]:
    connection = sqlite3.connect(CANONICAL_DATABASE)
    try:
        return [
            json.loads(payload_json)
            for (payload_json,) in connection.execute(
                f"select payload_json from {table}"
            )
            if json.loads(payload_json).get("case_id") == case_id
        ]
    finally:
        connection.close()


def test_mu_authority_binds_the_exact_issued_fresh_chain() -> None:
    decision = _load(DECISION)
    source = decision["source_authority"]
    admission_path = ROOT / source["admission_ref"]
    issuance_path = ROOT / source["issuance_ref"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(admission_path)
    )
    target = load_execution_target(issuance_path)

    for ref_key, sha_key in (
        ("fresh_proof_ref", "fresh_proof_sha256"),
        ("admission_ref", "admission_file_sha256"),
        ("issuance_ref", "issuance_file_sha256"),
        ("project_os_preflight_ref", "project_os_preflight_sha256"),
        ("runner_preflight_ref", "runner_preflight_sha256"),
        ("host_capability_receipt_ref", "host_capability_receipt_sha256"),
    ):
        assert _sha256(ROOT / source[ref_key]) == source[sha_key]
    assert canonical_digest(admission.digest_payload()) == source[
        "admission_digest"
    ]
    assert _load_admission(admission_path, target) == admission
    exact = decision["exact_execution_target"]
    assert target.work_unit_id == exact["work_unit_id"]
    assert target.attempt_id == exact["attempt_id"]
    assert target.research_run_id == exact["research_run_id"]
    assert admission.input_digest == exact["input_digest"]


def test_mu_authority_is_exact_once_success_conditional_and_zero_call() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]

    assert decision["status"] == (
        "authorized_MU_exact_once_and_conditional_read_only_paired_"
        "assessment_execution_not_started"
    )
    assert authority["MU_admission_exact_once_consumption_authorized"] is True
    assert authority["MU_exact_live_execution_authorized"] is True
    assert authority[
        "paired_assessment_authorized_only_after_coherent_terminal_success"
    ] is True
    assert authority[
        "automatic_retry_fallback_replay_relaunch_patch_or_rerun_authorized"
    ] is False
    assert authority["Human_review_or_owner_acceptance_authorized"] is False
    assert authority["S4_T07_or_later_authorized"] is False
    assert authority["strict_schema_transport_reactivation_authorized"] is False
    assert set(decision["decision_boundary"].values()) == {False}
    assert set(decision["observed_counts"].values()) == {0}


def test_mu_authority_binds_zero_call_preflight_code_budget_and_success() -> None:
    decision = _load(DECISION)
    source = decision["source_authority"]
    verification = decision["pre_execution_verification"]
    target = decision["exact_execution_target"]
    success = decision["success_contract"]
    project_preflight = _load(ROOT / source["project_os_preflight_ref"])
    runner_preflight = _load(ROOT / source["runner_preflight_ref"])

    assert project_preflight["status"] == "pass"
    assert project_preflight["open_full_chain_blockers"] == []
    assert runner_preflight["status"] == (
        "pass_exact_zero_call_execution_preflight"
    )
    assert runner_preflight["execution_state_counts_before"] == (
        runner_preflight["execution_state_counts_after"]
    )
    assert set(runner_preflight["observed_counts"].values()) == {0}
    assert verification["credential_present"] is True
    assert verification["credential_value_read_output_or_persisted"] is False
    assert verification["provider_health_probe_performed"] is False
    assert verification["fresh_identity_absent"] is True
    assert verification["exact_code_binding_count"] == 6
    for relative_path, expected_sha256 in verification[
        "exact_code_bindings"
    ].items():
        _assert_historical_or_current(relative_path, expected_sha256)
    assert (
        target["maximum_semantic_model_calls"],
        target["maximum_provider_calls"],
        target["maximum_network_calls"],
        target["maximum_output_tokens"],
        target["maximum_total_cost_usd"],
        target["transport_retry_count"],
        target["maximum_transport_attempts_per_call"],
    ) == (12, 12, 12, 16800, 0.1, 0, 1)
    assert (
        success["logical_node_count"],
        success["semantic_model_call_count"],
        success["provider_call_count"],
        success["artifact_count"],
    ) == (6, 12, 12, 9)
    assert success["typed_verifier_success_required"] is True
    assert success["paired_assessment_must_remain_read_only"] is True
    assert decision["stop_contract"][
        "paired_assessment_after_failure_allowed"
    ] is False
    assert decision["stop_contract"]["automatic_second_execution_allowed"] is False


def test_mu_execution_identity_is_still_fresh_after_authority_decision() -> None:
    decision = _load(DECISION)
    case_id = decision["exact_execution_target"]["case_id"]
    later_R2_success = ROOT / (
        "configs/releases/fin_ia_0_1_s4_t06_mu_research_lead_"
        "fact_presence_local_materialization_r2_exact_live_"
        "execution_success_result_v1_0.json"
    )

    if later_R2_success.exists():
        assert any(
            row["state"] == "succeeded"
            for row in _case_rows("canonical_work_units", case_id)
        )
        assert any(
            row["state"] == "succeeded"
            for row in _case_rows("canonical_attempts", case_id)
        )
        assert any(
            row["state"] == "succeeded"
            for row in _case_rows("canonical_research_run_versions", case_id)
        )
        assert len(_case_rows("canonical_artifact_versions", case_id)) >= 9
    elif EXECUTION_RESULT.exists():
        result = _load(EXECUTION_RESULT)
        assert result["source_binding"]["case_id"] == case_id
        assert _case_rows("canonical_work_units", case_id)[-1]["state"] == "failed"
        assert _case_rows("canonical_attempts", case_id)[-1]["state"] == "failed"
        assert (
            _case_rows("canonical_research_run_versions", case_id)[-1]["state"]
            == "failed"
        )
    else:
        assert _case_rows("canonical_work_units", case_id) == []
        assert _case_rows("canonical_attempts", case_id) == []
        assert _case_rows("canonical_research_run_versions", case_id) == []
    if not later_R2_success.exists():
        assert _case_rows("canonical_artifact_versions", case_id) == []


def test_mu_authority_advances_only_to_exact_execution_and_success_only_pairing() -> None:
    decision = _load(DECISION)

    assert decision["next_action"] == NEXT_ACTION
    assert decision["conditional_next_action"][
        "on_authority_decision_complete"
    ] == NEXT_ACTION
    assert decision["conditional_next_action"][
        "on_terminal_success_and_paired_assessment_pass"
    ] == "S4-T06-MU-OWNER-ACCEPTANCE-DECISION"
    assert "S4_T07_NVDA_regression" in decision["deferred_out_of_scope"]
    assert (
        "strict_schema_transport_api_handoff_until_a_compatible_standalone_API_is_available"
        in decision["deferred_out_of_scope"]
    )
