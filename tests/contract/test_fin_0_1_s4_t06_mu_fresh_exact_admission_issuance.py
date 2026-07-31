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
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from scripts.releases.issue_fin_ia_0_1_s4_t06_mu_fresh_exact_admission import (  # noqa: E402
    ADMISSION,
    EXPECTED_ADMISSION_DIGEST,
    ISSUANCE,
    NEXT_ACTION,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (  # noqa: E402
    _load_admission,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


CANONICAL_DATABASE = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
    / "canonical-runtime"
    / "canonical.sqlite"
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


def _assert_historical_or_current(
    relative_path: str,
    historical_sha256: str,
) -> None:
    observed = hashlib.sha256(
        (ROOT / relative_path).read_bytes()
    ).hexdigest()
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


def test_mu_admission_is_issued_unconsumed_and_digest_bound() -> None:
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(ADMISSION)
    )

    admission.assert_profile_admissible()
    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert canonical_digest(admission.digest_payload()) == (
        EXPECTED_ADMISSION_DIGEST
    )
    assert issuance["issued_admission"]["admission_digest"] == (
        EXPECTED_ADMISSION_DIGEST
    )
    assert admission.company == "MU"
    assert admission.provider == "deepseek"
    assert admission.model == "deepseek-v4-pro"
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False


def test_issuance_reprepared_proof_and_preserved_fresh_identity() -> None:
    issuance = _load(ISSUANCE)
    proof = issuance["proof_reverification"]
    counts = proof["canonical_execution_counts"]

    assert proof["generator_rerun_before_materialization"] is True
    assert proof["frozen_and_regenerated_decision_byte_equal"] is True
    assert proof["double_prepare_equal"] is True
    assert proof["source_pack_digest_equal"] is True
    assert all(proof["freshness_and_nonreuse"].values())
    assert proof["exact_code_binding_count"] == 6
    assert counts["canonical_work_units"] == 0
    assert counts["canonical_attempts"] == 0
    assert counts["canonical_research_run_versions"] == 0
    assert counts["canonical_artifact_versions"] == 0


def test_issued_exact_code_bindings_match_current_bytes() -> None:
    bindings = _load(ISSUANCE)["proof_reverification"]["exact_code_bindings"]
    assert len(bindings) == 6
    for relative_path, expected_sha256 in bindings.items():
        _assert_historical_or_current(relative_path, expected_sha256)


def test_runner_load_and_executor_wiring_are_zero_call() -> None:
    target = load_execution_target(ISSUANCE)
    admission = _load_admission(ADMISSION, target)
    callback_calls = 0

    def _must_not_call_provider(**_: object) -> dict:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider callback invoked during issuance test")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    assert target.case_id == admission.case_id
    assert _load(ISSUANCE)["exact_binding"]["input_digest"] == (
        admission.input_digest
    )
    assert callback_calls == 0


def test_canonical_case_has_no_execution_state_after_issuance() -> None:
    issuance = _load(ISSUANCE)
    case_id = issuance["exact_binding"]["case_id"]
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


def test_authority_stops_before_exact_live_and_later_sequence() -> None:
    issuance = _load(ISSUANCE)
    authority = issuance["authority"]
    boundary = issuance["issuance_boundary"]

    assert authority["fresh_exact_admission_issuance_authorized"] is True
    assert authority[
        "admission_consumption_or_exact_live_execution_authorized"
    ] is False
    assert authority["paired_comparison_or_Human_review_authorized"] is False
    assert authority["S4_T07_or_later_authorized"] is False
    assert boundary["admission_issued"] is True
    assert boundary["admission_consumed"] is False
    assert boundary["execution_started"] is False
    assert boundary["model_or_provider_call_started"] is False
    assert issuance["observed_counts"]["model_calls"] == 0
    assert issuance["observed_counts"]["provider_calls"] == 0
    assert issuance["next_action"] == NEXT_ACTION
