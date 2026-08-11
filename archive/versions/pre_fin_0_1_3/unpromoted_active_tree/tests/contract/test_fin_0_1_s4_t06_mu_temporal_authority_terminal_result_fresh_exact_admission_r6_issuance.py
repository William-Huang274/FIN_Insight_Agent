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
from scripts.releases.issue_fin_ia_0_1_s4_t06_mu_temporal_authority_terminal_result_fresh_exact_admission_r6 import (
    ADMISSION,
    AUTHORITY,
    EXPECTED_ADMISSION_DIGEST,
    EXPECTED_AUTHORITY_SHA256,
    EXPECTED_PROOF_SHA256,
    ISSUANCE,
    NEXT_ACTION,
    PROOF_DECISION,
    R5_ADMISSION,
    R5_FAILURE,
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
CURRENT_ISSUANCE = (
    "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
    "TERMINAL-RESULT-MATERIALIZATION-FRESH-EXACT-ADMISSION-R6-ISSUANCE"
)
EXPECTED_R5_ADMISSION_SHA256 = (
    "1f49070ddce794ebf097abed4cd07cec2675d85822a0d7a8547236460c5fbff7"
)
EXPECTED_R5_FAILURE_SHA256 = (
    "9662458edd0cfcddd4c999bbd2cb6374ade88b20fad473c7d432697a2ef6790f"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_issued_R6_admission_is_exact_frozen_payload() -> None:
    authority = _load(AUTHORITY)
    proof = _load(PROOF_DECISION)
    payload = _load(ADMISSION)
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)

    admission.assert_profile_admissible()
    assert payload == proof["prospective_R6_admission"]["payload"]
    assert canonical_digest(admission.digest_payload()) == (
        EXPECTED_ADMISSION_DIGEST
    )
    assert _sha256(AUTHORITY) == EXPECTED_AUTHORITY_SHA256
    assert _sha256(PROOF_DECISION) == EXPECTED_PROOF_SHA256
    assert issuance["source_authority_sha256"] == EXPECTED_AUTHORITY_SHA256
    assert issuance["source_proof_decision_sha256"] == EXPECTED_PROOF_SHA256
    assert authority["frozen_R6_admission"]["admission_digest"] == (
        EXPECTED_ADMISSION_DIGEST
    )


def test_issuance_verifier_and_runner_prove_unconsumed_state() -> None:
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


def test_R6_fresh_identity_is_absent_from_target_runtime() -> None:
    identity = _load(PROOF_DECISION)["fresh_identity"]
    database_path = RUNTIME_ROOT / "canonical-runtime/canonical.sqlite"
    connection = sqlite3.connect(
        f"file:{database_path.resolve().as_posix()}?mode=ro",
        uri=True,
    )
    try:
        checks = (
            ("canonical_work_units", identity["work_unit_id"]),
            ("canonical_attempts", identity["attempt_id"]),
            ("canonical_research_run_versions", identity["research_run_id"]),
        )
        for table, logical_id in checks:
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE logical_id = ?",
                (logical_id,),
            ).fetchone()[0]
            assert count == 0
    finally:
        connection.close()


def test_issuance_boundary_excludes_execution_credentials_and_deferred_work() -> None:
    issuance = _load(ISSUANCE)
    authority = issuance["authority"]
    boundary = issuance["issuance_boundary"]
    counts = issuance["observed_counts"]

    assert authority["fresh_exact_R6_admission_issuance_authorized"] is True
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
    assert _sha256(R5_ADMISSION) == EXPECTED_R5_ADMISSION_SHA256
    assert _sha256(R5_FAILURE) == EXPECTED_R5_FAILURE_SHA256


def test_project_state_advances_only_to_R6_execution_authority() -> None:
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)

    assert program["next_action"]["item_id"] in {
        CURRENT_ISSUANCE,
        NEXT_ACTION,
    }
    assert detailed["current_next_action"] in {
        CURRENT_ISSUANCE,
        NEXT_ACTION,
    }
    if program["next_action"]["item_id"] == NEXT_ACTION:
        assert program["next_action"][
            "runtime_audit_classifier_fresh_R6_admission_issued"
        ] is True
