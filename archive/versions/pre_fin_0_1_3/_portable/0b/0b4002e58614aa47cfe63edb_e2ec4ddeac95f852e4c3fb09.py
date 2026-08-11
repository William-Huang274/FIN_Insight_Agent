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
from scripts.releases.issue_fin_ia_0_1_s4_t06_mu_runtime_audit_evidence_v2_and_material_numeric_classifier_fresh_exact_admission_r5 import (
    ADMISSION,
    AUTHORITY,
    EXPECTED_ADMISSION_DIGEST,
    EXPECTED_AUTHORITY_SHA256,
    EXPECTED_PROOF_SHA256,
    ISSUANCE,
    NEXT_ACTION,
    PROOF_DECISION,
    R4_ADMISSION,
    R4_FAILURE,
    RUNTIME_ROOT,
    verify_issued_admission,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
ROOT_CAUSE_LEDGER = (
    ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
)
EXPECTED_R4_ADMISSION_SHA256 = (
    "1d973454c72a47c9b0d86bbc2dd2933e9e79329add4abae313f734fb2cbaa375"
)
EXPECTED_R4_FAILURE_SHA256 = (
    "b49c9c784733e0364a384f8bfa525360321736f352c2cddbe1b6e7fb587bef94"
)
CURRENT_EXECUTION = (
    "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-R5-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-"
    "ASSESSMENT"
)
CURRENT_EXECUTION_SCOPE = (
    "S4_T06_MU_RUNTIME_AUDIT_EVIDENCE_V2_AND_MATERIAL_NUMERIC_"
    "CLASSIFIER_R5_EXACT_LIVE_EXECUTION_AND_SUCCESS_ONLY_PAIRED_"
    "ASSESSMENT"
)
CURRENT_DISPOSITION = (
    "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
    "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)
R5_FAILURE_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_r5_exact_live_execution_failure_"
    "result_v1_0.json"
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


def test_issued_R5_admission_is_exact_frozen_payload() -> None:
    authority = _load(AUTHORITY)
    proof = _load(PROOF_DECISION)
    payload = _load(ADMISSION)
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)

    admission.assert_profile_admissible()
    assert payload == proof["prospective_R5_admission"]["payload"]
    assert canonical_digest(admission.digest_payload()) == (
        EXPECTED_ADMISSION_DIGEST
    )
    assert _sha256(AUTHORITY) == EXPECTED_AUTHORITY_SHA256
    assert _sha256(PROOF_DECISION) == EXPECTED_PROOF_SHA256
    assert issuance["source_authority_sha256"] == EXPECTED_AUTHORITY_SHA256
    assert issuance["source_proof_decision_sha256"] == EXPECTED_PROOF_SHA256
    assert authority["frozen_R5_admission"]["admission_digest"] == (
        EXPECTED_ADMISSION_DIGEST
    )


def test_issuance_verifier_and_runner_prove_unconsumed_state() -> None:
    if R5_FAILURE_RESULT.exists():
        issuance = _load(ISSUANCE)
        assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
        assert issuance["issued_admission"]["admission_digest"] == (
            EXPECTED_ADMISSION_DIGEST
        )
        assert issuance["issued_admission"]["consumed"] is False
        assert _load(R5_FAILURE_RESULT)["stop_contract_observation"][
            "admission_consumed_exactly_once"
        ] is True
        return
    result = verify_issued_admission()
    target = load_execution_target(ISSUANCE)
    admission = _load_admission(ADMISSION, target)

    assert result["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert result["admission_digest"] == EXPECTED_ADMISSION_DIGEST
    assert set(result["fresh_identity_rows"].values()) == {0}
    assert result["credential_checked"] is False
    assert result["provider_calls"] == 0
    assert result["next_action"] == NEXT_ACTION
    assert target.admission_digest == EXPECTED_ADMISSION_DIGEST
    assert admission.admission_id == target.admission_id
    assert target.maximum_output_tokens == 16800


def test_R5_fresh_identity_is_absent_from_target_runtime() -> None:
    proof = _load(PROOF_DECISION)
    identity = proof["fresh_identity"]
    database_path = RUNTIME_ROOT / "canonical-runtime/canonical.sqlite"
    connection = sqlite3.connect(
        f"file:{database_path.resolve().as_posix()}?mode=ro",
        uri=True,
    )
    try:
        checks = (
            (
                "canonical_work_units",
                identity["work_unit_id"],
            ),
            (
                "canonical_attempts",
                identity["attempt_id"],
            ),
            (
                "canonical_research_run_versions",
                identity["research_run_id"],
            ),
        )
        for table, logical_id in checks:
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE logical_id = ?",
                (logical_id,),
            ).fetchone()[0]
            if R5_FAILURE_RESULT.exists():
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


def test_issuance_boundary_excludes_execution_credentials_and_deferred_work() -> None:
    issuance = _load(ISSUANCE)
    authority = issuance["authority"]
    boundary = issuance["issuance_boundary"]
    counts = issuance["observed_counts"]

    assert authority["fresh_exact_R5_admission_issuance_authorized"] is True
    assert authority[
        "admission_consumption_or_exact_live_execution_authorized"
    ] is False
    assert authority["credential_presence_or_value_read_authorized"] is False
    assert authority[
        "model_provider_or_execution_network_calls_authorized"
    ] is False
    assert authority[
        "paired_assessment_or_owner_acceptance_authorized"
    ] is False
    assert boundary["admission_issued"] is True
    assert boundary["admission_consumed"] is False
    assert boundary["execution_started"] is False
    assert boundary["supervisor_launched"] is False
    assert counts["new_admissions"] == 1
    assert set(
        value for key, value in counts.items() if key != "new_admissions"
    ) == {0}
    assert _sha256(R4_ADMISSION) == EXPECTED_R4_ADMISSION_SHA256
    assert _sha256(R4_FAILURE) == EXPECTED_R4_FAILURE_SHA256


def test_project_state_advances_only_to_R5_execution_authority() -> None:
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    task = next(
        item for item in detailed["tasks"] if item["item_id"] == "S4-T06"
    )

    assert program["next_action"]["item_id"] in {
        NEXT_ACTION,
        CURRENT_EXECUTION,
        CURRENT_DISPOSITION,
    }
    assert detailed["current_next_action"] in {
        NEXT_ACTION,
        CURRENT_EXECUTION,
        CURRENT_DISPOSITION,
    }
    assert program["next_action"][
        "runtime_audit_classifier_fresh_R5_admission_issued"
    ] is True
    assert program["next_action"][
        "runtime_audit_classifier_fresh_R5_admission_consumed"
    ] is (program["next_action"]["item_id"] == CURRENT_DISPOSITION)
    assert program["next_action"][
        "runtime_audit_classifier_fresh_R5_execution_authorized"
    ] is True
    assert task["runtime_audit_classifier_fresh_R5_admission_issued"] is True
    assert task[
        "runtime_audit_classifier_fresh_R5_admission_consumed"
    ] is (program["next_action"]["item_id"] == CURRENT_DISPOSITION)
    for issue_prefix in (
        "RC-P36-067",
        "RC-P36-068",
        "RC-P36-080",
        "RC-P36-081",
    ):
        issue = _latest_issue(issue_prefix)
        if issue_prefix == "RC-P36-081" and (
            program["next_action"]["item_id"] == CURRENT_DISPOSITION
        ):
            assert issue["status"].startswith("closed_")
        else:
            assert issue["status"] == "open"
        assert issue["allowed_run_scopes"] in (
            [
                (
                    "S4_T06_MU_RUNTIME_AUDIT_EVIDENCE_V2_AND_MATERIAL_"
                    "NUMERIC_CLASSIFIER_R5_EXACT_LIVE_EXECUTION_AND_"
                    "SUCCESS_ONLY_PAIRED_ASSESSMENT_AUTHORITY_DECISION"
                ),
                "repository_and_git_hygiene",
            ],
            [CURRENT_EXECUTION_SCOPE, "repository_and_git_hygiene"],
            [
                CURRENT_DISPOSITION.replace("-", "_"),
                "repository_and_git_hygiene",
            ],
            ["repository_and_git_hygiene"],
        )
