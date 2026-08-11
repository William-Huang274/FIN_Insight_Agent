from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.releases.prepare_fin_ia_0_1_s4_t06_mu_temporal_authority_terminal_result_fresh_proof import (
    CURRENT_ACTION,
    DECISION,
    IMPLEMENTATION,
    NEXT_ACTION,
    PROSPECTIVE_ADMISSION,
    SOURCE_R5_ADMISSION,
    SOURCE_R5_FAILURE,
    build_decision,
)


PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fresh_proof_reproduces_exactly_without_target_writes() -> None:
    frozen = _load(DECISION)
    assert build_decision() == frozen
    assert frozen["proof_generator"]["independent_invocations"] == 2
    assert frozen["proof_generator"]["independent_outputs_equal"] is True
    assert frozen["double_prepare"]["equal"] is True
    assert frozen["target_read_only_audit"]["target_state_unchanged"] is True
    assert set(frozen["hard_boundaries"].values()) == {0}


def test_fresh_proof_binds_current_implementation_and_three_case_surfaces() -> None:
    proof = _load(DECISION)
    implementation = _load(IMPLEMENTATION)
    assert proof["implementation_reaudit"]["implementation_sha256"] == (
        _sha256(IMPLEMENTATION)
    )
    assert proof["implementation_reaudit"]["exact_code_bindings"] == {
        row["ref"]: row["sha256"]
        for row in implementation["code_bindings"]
    }
    assert proof["implementation_reaudit"][
        "typed_temporal_authority_ref"
    ] == (
        "fin01.s4.specialist_WWC_judgment_atom_deterministic_"
        "temporal_authority:v2"
    )
    fixture = proof["independent_fixture_reproof"]
    assert fixture["provider_authored_calendar_text_allowed"] is False
    assert set(
        tuple(value)
        for value in fixture[
            "three_case_positive_nodes_callbacks_captures_artifacts"
        ].values()
    ) == {(6, 12, 12, 9)}
    assert fixture["unknown_date_alias_typed_failure"] is True
    assert fixture["material_financial_number_L1_failure"] is True
    assert fixture[
        "admission_bound_capture_v2_terminal_result_materialized"
    ] is True
    assert fixture["supervision_final_stderr_digest_match"] is True


def test_R5_history_and_prospective_R6_boundary_remain_fail_closed() -> None:
    proof = _load(DECISION)
    R5_admission = _load(SOURCE_R5_ADMISSION)
    R5_failure = _load(SOURCE_R5_FAILURE)
    assert "wwc_judgment_atom_policy_ref" not in R5_admission
    assert R5_admission["transport_ref"].endswith(":v7")
    assert R5_failure["status"] == (
        "terminal_failed_admission_consumed_no_retry_no_artifact_"
        "runner_result_materialization_failed"
    )
    prospective = proof["prospective_R6_admission"]
    assert prospective["temporal_v2_specialist_v8_task_claim_bound"] is True
    assert prospective["capture_v2_numeric_v2_identity_v2_preserved"] is True
    assert prospective["issued"] is False
    assert prospective["consumed"] is False
    assert prospective["execution_started"] is False
    assert prospective["prospective_admission_file_absent_at_proof"] is True
    assert not PROSPECTIVE_ADMISSION.exists()
    assert proof["next_action"] == NEXT_ACTION
    assert proof["next_action_authorized"] is False
    assert proof["stop_rule"]["automatic_R7"] is False


def test_backlogs_advance_only_to_separate_R6_admission_authority() -> None:
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(S4_BACKLOG)
    assert program["next_action"]["item_id"] in {
        CURRENT_ACTION,
        NEXT_ACTION,
    }
    assert detailed["current_next_action"] in {
        CURRENT_ACTION,
        NEXT_ACTION,
    }
    assert program["next_action"]["automatic_R6"] is False
    assert program["next_action"]["S4_T07_unblocked"] is False
