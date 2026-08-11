from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_temporal_authority_terminal_"
    "result_r6_exact_live_execution_and_success_only_paired_assessment_"
    "authority_decision_v1_0.json"
)
ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_action_planning_temporal_"
    "authority_and_capture_v2_terminal_result_materialization_fresh_"
    "exact_admission_r6.json"
)
ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_action_planning_temporal_"
    "authority_and_capture_v2_terminal_result_materialization_fresh_"
    "exact_admission_r6_issuance_v1_0.json"
)
RUNNER_PREFLIGHT = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-"
    "validation-r1/s4_t06_mu_temporal_authority_terminal_result_r6_"
    "authority_preflight_live_execution_preflight.json"
)
RUNTIME_DB = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-"
    "live-validation-r1/canonical-runtime/canonical.sqlite"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
CURRENT_AUTHORITY = (
    "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
    "TERMINAL-RESULT-MATERIALIZATION-R6-EXACT-LIVE-EXECUTION-AND-"
    "SUCCESS-ONLY-PAIRED-ASSESSMENT-AUTHORITY-DECISION"
)
NEXT = (
    "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
    "TERMINAL-RESULT-MATERIALIZATION-R6-EXACT-LIVE-EXECUTION-AND-"
    "SUCCESS-ONLY-PAIRED-ASSESSMENT"
)
EXPECTED_ADMISSION_SHA256 = (
    "f5f031b5a470c6df2ee0aad6496f1277132b175da7ff4ce5c2fcb938ec607e17"
)
EXPECTED_ISSUANCE_SHA256 = (
    "bcdeda07b5798d47e9441e72c25ba21b43647cdb053c4e4bea2ac023c9006cda"
)
EXPECTED_ADMISSION_DIGEST = (
    "a30d6977df984f1002ec95992c3e6d3bf8e7a7271dd54a626bb5271315bb2ac3"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_authority_binds_issued_unconsumed_R6_admission() -> None:
    decision = _load(DECISION)
    payload = _load(ADMISSION)
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()

    assert _sha256(ADMISSION) == EXPECTED_ADMISSION_SHA256
    assert _sha256(ISSUANCE) == EXPECTED_ISSUANCE_SHA256
    assert canonical_digest(admission.digest_payload()) == (
        EXPECTED_ADMISSION_DIGEST
    )
    assert decision["source_authority"]["admission_file_sha256"] == (
        EXPECTED_ADMISSION_SHA256
    )
    assert decision["source_authority"]["issuance_file_sha256"] == (
        EXPECTED_ISSUANCE_SHA256
    )
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False
    target = load_execution_target(ISSUANCE)
    assert _load_admission(ADMISSION, target).admission_id == (
        target.admission_id
    )


def test_authority_binds_current_runtime_supervision_and_preflights() -> None:
    decision = _load(DECISION)
    bindings = decision["pre_execution_verification"][
        "exact_code_bindings"
    ]
    assert len(bindings) == 10
    for relative_path, digest in bindings.items():
        assert _sha256(ROOT / relative_path) == digest

    for ref_key, sha_key in (
        ("project_os_authority_preflight_ref", "project_os_authority_preflight_sha256"),
        ("runner_preflight_ref", "runner_preflight_sha256"),
        ("host_capability_receipt_ref", "host_capability_receipt_sha256"),
    ):
        path = ROOT / decision["source_authority"][ref_key]
        assert _sha256(path) == decision["source_authority"][sha_key]

    supervision_root = ROOT / decision["exact_execution_target"][
        "supervision_root"
    ]
    assert supervision_root.exists() is False


def test_authority_preflight_is_zero_call_and_fresh_identity_absent() -> None:
    decision = _load(DECISION)
    verification = decision["pre_execution_verification"]
    observed = decision["observed_counts"]
    target = decision["exact_execution_target"]
    runner = _load(RUNNER_PREFLIGHT)

    assert verification["project_os_scope_preflight"] == "pass"
    assert verification["open_full_chain_blocker_count_for_exact_scope"] == 0
    assert runner["status"] == "pass_exact_zero_call_execution_preflight"
    assert runner["admission_digest"] == EXPECTED_ADMISSION_DIGEST
    assert runner["credential_present"] is True
    assert runner["credential_value_read_output_or_persisted"] is False
    assert runner["provider_health_probe_performed"] is False
    assert runner["transport_retries"] == 0
    assert runner["execution_state_counts_before"] == (
        runner["execution_state_counts_after"]
    )
    assert observed["credential_presence_checks"] == 1
    assert set(
        value
        for key, value in observed.items()
        if key != "credential_presence_checks"
    ) == {0}

    connection = sqlite3.connect(
        f"file:{RUNTIME_DB.resolve().as_posix()}?mode=ro",
        uri=True,
    )
    try:
        for table, logical_id in (
            ("canonical_work_units", target["work_unit_id"]),
            ("canonical_attempts", target["attempt_id"]),
            (
                "canonical_research_run_versions",
                target["research_run_id"],
            ),
        ):
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE logical_id = ?",
                (logical_id,),
            ).fetchone()[0]
            assert count == 0
    finally:
        connection.close()


def test_authority_preserves_success_stop_and_nonexecution_contracts() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]
    target = decision["exact_execution_target"]
    success = decision["success_contract"]
    stop = decision["stop_contract"]
    boundary = decision["decision_boundary"]

    assert authority[
        "future_R6_admission_exact_once_consumption_authorized"
    ] is True
    assert authority["future_R6_exact_live_execution_authorized"] is True
    assert authority[
        "current_turn_admission_consumption_or_execution_authorized"
    ] is False
    assert authority["automatic_R7_authorized"] is False
    assert target["transport_retry_count"] == 0
    assert target["maximum_provider_calls"] == 12
    assert target["maximum_output_tokens"] == 16800
    assert target["output_only_cost_ceiling_usd"] < (
        target["maximum_total_cost_usd"]
    )
    assert success["provider_interaction_audit_capture_v2_count"] == 12
    assert success["artifact_count"] == 9
    assert success["typed_temporal_authority_v2_compliance_required"] is True
    assert success["independent_final_artifact_L1_required"] is True
    assert stop["automatic_second_execution_allowed"] is False
    assert stop["automatic_R7_allowed"] is False
    assert set(boundary.values()) == {False}


def test_project_state_advances_only_to_exact_execution() -> None:
    decision = _load(DECISION)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(S4_BACKLOG)

    assert decision["next_action"] == NEXT
    assert decision["next_action_authorized"] is True
    assert program["next_action"]["item_id"] in {CURRENT_AUTHORITY, NEXT}
    assert detailed["current_next_action"] in {CURRENT_AUTHORITY, NEXT}
    if program["next_action"]["item_id"] == NEXT:
        assert program["next_action"][
            "runtime_audit_classifier_fresh_R6_execution_authorized"
        ] is True
        assert program["next_action"][
            "runtime_audit_classifier_fresh_R6_execution_started"
        ] is False
