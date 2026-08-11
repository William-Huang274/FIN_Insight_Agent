from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.releases.prepare_fin_ia_0_1_s4_t06_runtime_audit_evidence_v2_and_material_numeric_classifier_fresh_proof import (
    DECISION,
    IMPLEMENTATION,
    PROSPECTIVE_ADMISSION,
    SOURCE_R4_ADMISSION,
    SOURCE_R4_FAILURE,
    build_decision,
)


PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
CURRENT_PROOF = (
    "S4-T06-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-FRESH-AGENT-PROOF-DECISION"
)
NEXT_AUTHORITY = (
    "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-FRESH-EXACT-ADMISSION-R5-AUTHORITY-DECISION"
)
NEXT_ISSUANCE = (
    "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-FRESH-EXACT-ADMISSION-R5-ISSUANCE"
)
NEXT_EXECUTION_AUTHORITY = (
    "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-R5-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-"
    "ASSESSMENT-AUTHORITY-DECISION"
)
NEXT_EXECUTION = (
    "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-R5-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-"
    "ASSESSMENT"
)
CURRENT_DISPOSITION = (
    "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
    "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fresh_proof_reproduces_exactly_without_target_writes() -> None:
    frozen = _load(DECISION)
    if _load(PROGRAM_BACKLOG)["next_action"]["item_id"] != CURRENT_DISPOSITION:
        assert build_decision(require_prospective_absent=False) == frozen
    assert frozen["proof_generator"]["independent_invocations"] == 2
    assert frozen["proof_generator"]["independent_outputs_equal"] is True
    assert frozen["double_prepare"]["equal"] is True
    assert frozen["target_read_only_audit"]["target_state_unchanged"] is True
    assert set(frozen["hard_boundaries"].values()) == {0}


def test_fresh_proof_binds_current_implementation_and_expected_surfaces() -> None:
    proof = _load(DECISION)
    implementation = _load(IMPLEMENTATION)
    assert proof["implementation_reaudit"]["implementation_sha256"] == (
        _sha256(IMPLEMENTATION)
    )
    assert proof["implementation_reaudit"]["exact_code_bindings"] == (
        implementation["exact_code_bindings"]
    )
    assert proof["implementation_reaudit"]["capture_v2_ref"] == (
        "fin01.runtime.provider_interaction_audit_capture:v2"
    )
    assert proof["implementation_reaudit"][
        "material_numeric_classifier_v2_ref"
    ] == (
        "fin01.s4.case_numeric_authority_projection_and_"
        "deterministic_rendering:v2"
    )
    fixture = proof["independent_fixture_reproof"]
    assert fixture["R4_safe_paths"] == [
        "$.fact_layer[0].statement",
        "$.explanation_layer[0]",
    ]
    assert fixture["R4_semantic_class"] == "reporting_period_label"
    assert fixture["R4_terminal"] is False
    assert set(
        tuple(value)
        for value in fixture[
            "three_case_positive_nodes_callbacks_captures_artifacts"
        ].values()
    ) == {(6, 12, 12, 9)}
    assert set(
        tuple(value)
        for value in fixture[
            "three_case_negative_callbacks_captures_artifacts"
        ].values()
    ) == {(1, 1, 0)}


def test_R4_history_and_R5_authority_boundary_remain_fail_closed() -> None:
    proof = _load(DECISION)
    R4_admission = _load(SOURCE_R4_ADMISSION)
    R4_failure = _load(SOURCE_R4_FAILURE)
    assert R4_admission["case_numeric_authority_policy_ref"].endswith(":v1")
    assert R4_admission["provider_output_capture_policy_ref"].endswith(":v1")
    assert R4_failure["status"] == (
        "terminal_failed_new_numeric_narrative_L1_no_R5_no_paired_no_owner"
    )
    prospective = proof["prospective_R5_admission"]
    assert prospective["capture_v2_and_numeric_classifier_v2_bound"] is True
    assert prospective["issued"] is False
    assert prospective["consumed"] is False
    assert prospective["execution_started"] is False
    assert prospective["prospective_admission_file_absent_at_proof"] is True
    if PROSPECTIVE_ADMISSION.exists():
        assert _load(PROSPECTIVE_ADMISSION) == prospective["payload"]
    assert proof["next_action"] == NEXT_AUTHORITY
    assert proof["next_action_authorized"] is False
    assert proof["stop_rule"]["automatic_R6"] is False


def test_backlogs_may_advance_only_through_R5_admission_issuance() -> None:
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(S4_BACKLOG)
    assert program["next_action"]["item_id"] in {
        CURRENT_PROOF,
        NEXT_AUTHORITY,
        NEXT_ISSUANCE,
        NEXT_EXECUTION_AUTHORITY,
        NEXT_EXECUTION,
        CURRENT_DISPOSITION,
    }
    assert detailed["current_next_action"] in {
        CURRENT_PROOF,
        NEXT_AUTHORITY,
        NEXT_ISSUANCE,
        NEXT_EXECUTION_AUTHORITY,
        NEXT_EXECUTION,
        CURRENT_DISPOSITION,
    }
    assert program["next_action"]["automatic_R5"] is False
    assert program["next_action"]["S4_T07_unblocked"] is False
