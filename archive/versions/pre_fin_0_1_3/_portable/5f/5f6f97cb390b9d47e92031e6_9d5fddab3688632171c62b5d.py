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
    "configs/releases/fin_ia_0_1_s4_t06_mu_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_r5_exact_live_execution_and_"
    "success_only_paired_assessment_authority_decision_v1_0.json"
)
ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_fresh_exact_admission_r5.json"
)
ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_fresh_exact_admission_r5_"
    "issuance_v1_0.json"
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
ROOT_CAUSE_LEDGER = (
    ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
)
EXPECTED_ADMISSION_SHA256 = (
    "1f49070ddce794ebf097abed4cd07cec2675d85822a0d7a8547236460c5fbff7"
)
EXPECTED_ISSUANCE_SHA256 = (
    "c91136b3478fe04a1e2a3ca7e863ac8cbb9d3f99446a0c6b0db884fa3a59fe05"
)
EXPECTED_ADMISSION_DIGEST = (
    "3457fded0bd72b4df5d1fd6a1529bf7bfb8055681c388808b5d3e01a5dbbd6e8"
)
NEXT = (
    "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-R5-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-"
    "ASSESSMENT"
)
CURRENT_DISPOSITION = (
    "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
    "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)
ALLOWED_SCOPE = (
    "S4_T06_MU_RUNTIME_AUDIT_EVIDENCE_V2_AND_MATERIAL_NUMERIC_"
    "CLASSIFIER_R5_EXACT_LIVE_EXECUTION_AND_SUCCESS_ONLY_PAIRED_"
    "ASSESSMENT"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _latest_issue(prefix: str) -> dict:
    rows = [
        json.loads(line)
        for line in ROOT_CAUSE_LEDGER.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    return next(
        row
        for row in reversed(rows)
        if row["issue_id"].startswith(prefix)
    )


def test_authority_binds_issued_unconsumed_R5_admission() -> None:
    decision = _load(DECISION)
    admission_payload = _load(ADMISSION)
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        admission_payload
    )
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


def test_authority_binds_current_runtime_and_supervision_code() -> None:
    decision = _load(DECISION)
    bindings = decision["pre_execution_verification"][
        "exact_code_bindings"
    ]
    assert len(bindings) == 9
    for relative_path, digest in bindings.items():
        assert _sha256(ROOT / relative_path) == digest

    host_ref = ROOT / decision["source_authority"][
        "host_capability_receipt_ref"
    ]
    assert _sha256(host_ref) == decision["source_authority"][
        "host_capability_receipt_sha256"
    ]
    supervision_root = ROOT / decision["exact_execution_target"][
        "supervision_root"
    ]
    if supervision_root.exists():
        assert (supervision_root / "launch_receipt.json").is_file()
        assert (supervision_root / "exit_receipt.json").is_file()
    else:
        assert not supervision_root.exists()


def test_authority_preflight_is_zero_call_and_fresh_identity_absent() -> None:
    decision = _load(DECISION)
    verification = decision["pre_execution_verification"]
    observed = decision["observed_counts"]
    target = decision["exact_execution_target"]

    assert verification["project_os_scope_preflight"] == "pass"
    assert verification["open_full_chain_blocker_count_for_exact_scope"] == 0
    assert verification["exact_runner_zero_call_preflight"] == (
        "pass_exact_zero_call_execution_preflight"
    )
    assert verification["credential_present"] is True
    assert verification["credential_value_read_output_or_persisted"] is False
    assert verification["provider_health_probe_performed"] is False
    assert verification[
        "canonical_same_case_work_unit_attempt_run_artifact_counts_before"
    ] == verification[
        "canonical_same_case_work_unit_attempt_run_artifact_counts_after"
    ]
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
            if detailed := _load(S4_BACKLOG):
                if detailed["current_next_action"] == CURRENT_DISPOSITION:
                    assert count > 0
                    assert connection.execute(
                        f"""
                        SELECT current_status FROM {table}
                        WHERE logical_id = ?
                        ORDER BY row_id DESC LIMIT 1
                        """,
                        (logical_id,),
                    ).fetchone()[0] == "failed"
                else:
                    assert count == 0
    finally:
        connection.close()


def test_authority_preserves_success_and_stop_contracts() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]
    target = decision["exact_execution_target"]
    success = decision["success_contract"]
    stop = decision["stop_contract"]
    boundary = decision["decision_boundary"]

    assert authority[
        "future_R5_admission_exact_once_consumption_authorized"
    ] is True
    assert authority["future_R5_exact_live_execution_authorized"] is True
    assert authority[
        "current_turn_admission_consumption_or_execution_authorized"
    ] is False
    assert authority["automatic_R6_authorized"] is False
    assert target["transport_retry_count"] == 0
    assert target["maximum_provider_calls"] == 12
    assert target["maximum_output_tokens"] == 16800
    assert target["output_only_cost_ceiling_usd"] < (
        target["maximum_total_cost_usd"]
    )
    assert success["provider_interaction_audit_capture_v2_count"] == 12
    assert success["artifact_count"] == 9
    assert success["independent_final_artifact_L1_required"] is True
    assert stop["automatic_second_execution_allowed"] is False
    assert stop["automatic_R6_allowed"] is False
    assert set(boundary.values()) == {False}


def test_project_state_advances_only_to_exact_execution() -> None:
    decision = _load(DECISION)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(S4_BACKLOG)
    task = next(
        item for item in detailed["tasks"] if item["item_id"] == "S4-T06"
    )

    assert decision["next_action"] == NEXT
    assert decision["next_action_authorized"] is True
    assert program["next_action"]["item_id"] in {NEXT, CURRENT_DISPOSITION}
    assert detailed["current_next_action"] in {NEXT, CURRENT_DISPOSITION}
    assert program["next_action"][
        "runtime_audit_classifier_fresh_R5_execution_authorized"
    ] is True
    assert program["next_action"][
        "runtime_audit_classifier_fresh_R5_execution_started"
    ] is (program["next_action"]["item_id"] == CURRENT_DISPOSITION)
    assert task[
        "runtime_audit_classifier_fresh_R5_execution_authorized"
    ] is True
    assert task["runtime_audit_classifier_fresh_R5_execution_started"] is (
        program["next_action"]["item_id"] == CURRENT_DISPOSITION
    )
    for prefix in (
        "RC-P36-067",
        "RC-P36-068",
        "RC-P36-080",
        "RC-P36-081",
    ):
        issue = _latest_issue(prefix)
        if prefix == "RC-P36-081" and (
            program["next_action"]["item_id"] == CURRENT_DISPOSITION
        ):
            assert issue["status"].startswith("closed_")
        else:
            assert issue["status"] == "open"
        if program["next_action"]["item_id"] == CURRENT_DISPOSITION:
            expected_scopes = (
                ["repository_and_git_hygiene"]
                if prefix == "RC-P36-081"
                else [
                    CURRENT_DISPOSITION.replace("-", "_"),
                    "repository_and_git_hygiene",
                ]
            )
            assert issue["allowed_run_scopes"] == expected_scopes
        else:
            assert issue["allowed_run_scopes"] == [
                ALLOWED_SCOPE,
                "repository_and_git_hygiene",
            ]
