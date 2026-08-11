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
from scripts.releases.issue_fin_ia_0_1_s4_t06_mu_claim_support_role_v2_fresh_exact_admission_r7 import (
    ADMISSION,
    AUTHORITY,
    CANARY_RESULT,
    EXPECTED_ADMISSION_DIGEST,
    EXPECTED_AUTHORITY_SHA256,
    EXPECTED_CANARY_RESULT_SHA256,
    EXPECTED_PROOF_SHA256,
    ISSUANCE,
    NEXT_ACTION,
    PROOF_DECISION,
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
    "S4-T06-MU-CLAIM-EPISTEMIC-SUPPORT-ROLE-COMPILED-CONTRACT-V2-"
    "FRESH-EXACT-ADMISSION-R7-ISSUANCE"
)
EXACT_EXECUTION = (
    "S4-T06-MU-CLAIM-EPISTEMIC-SUPPORT-ROLE-COMPILED-CONTRACT-V2-"
    "R7-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT"
)
FAILURE_DISPOSITION = (
    "S4-T06-MU-R7-FIRST-CREDIBLE-FAILURE-PROJECT-BLOCK-OR-"
    "DETERMINISTIC-PLANNER-SCOPE-DISPOSITION-DECISION"
)
AFTER_DISPOSITION = (
    "S4-T06-MU-WWC-PROVIDER-CANDIDATE-VALIDATION-AND-DETERMINISTIC-"
    "FINAL-SELECTION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)
EXECUTION_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_claim_support_role_v2_r7_"
    "exact_live_execution_failure_result_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_issued_R7_admission_is_exact_frozen_payload() -> None:
    authority = _load(AUTHORITY)
    proof = _load(PROOF_DECISION)
    payload = _load(ADMISSION)
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)

    admission.assert_profile_admissible()
    assert payload == proof["prospective_R7_admission"]["payload"]
    assert canonical_digest(admission.digest_payload()) == (
        EXPECTED_ADMISSION_DIGEST
    )
    assert _sha256(AUTHORITY) == EXPECTED_AUTHORITY_SHA256
    assert _sha256(PROOF_DECISION) == EXPECTED_PROOF_SHA256
    assert _sha256(CANARY_RESULT) == EXPECTED_CANARY_RESULT_SHA256
    assert issuance["source_authority_sha256"] == EXPECTED_AUTHORITY_SHA256
    assert issuance["source_proof_decision_sha256"] == EXPECTED_PROOF_SHA256
    assert authority["frozen_R7_admission"]["admission_digest"] == (
        EXPECTED_ADMISSION_DIGEST
    )


def test_issuance_verifier_and_runner_prove_unconsumed_state() -> None:
    target = load_execution_target(ISSUANCE)
    admission = _load_admission(ADMISSION, target)

    if EXECUTION_RESULT.exists():
        result = _load(EXECUTION_RESULT)
        assert result["status"] == (
            "terminal_failed_admission_consumed_exactly_once_no_retry_"
            "no_artifact"
        )
        assert result["source_authority"]["admission_digest"] == (
            EXPECTED_ADMISSION_DIGEST
        )
        assert result["stop_contract_observation"][
            "admission_consumed_exactly_once"
        ] is True
    else:
        result = verify_issued_admission()
        assert result["status"] == (
            "issued_unconsumed_zero_call_preflight_pass"
        )
        assert result["admission_digest"] == EXPECTED_ADMISSION_DIGEST
        assert set(result["fresh_identity_rows"].values()) == {0}
        assert result["claim_compiled_contract_v2_bound"] is True
        assert result["credential_checked"] is False
        assert result["provider_calls"] == 0
        assert result["next_action"] == NEXT_ACTION
    assert target.admission_digest == EXPECTED_ADMISSION_DIGEST
    assert admission.admission_id == target.admission_id
    assert target.maximum_output_tokens == 16800


def test_R7_fresh_identity_is_absent_from_target_runtime() -> None:
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
            if EXECUTION_RESULT.exists():
                assert count > 0
                latest = connection.execute(
                    f"SELECT payload_json FROM {table} "
                    "WHERE logical_id = ? ORDER BY row_id DESC LIMIT 1",
                    (logical_id,),
                ).fetchone()
                assert json.loads(latest[0])["state"] == "failed"
            else:
                assert count == 0
    finally:
        connection.close()


def test_issuance_boundary_excludes_execution_credentials_and_R8() -> None:
    issuance = _load(ISSUANCE)
    authority = issuance["authority"]
    boundary = issuance["issuance_boundary"]
    counts = issuance["observed_counts"]

    assert authority["fresh_exact_R7_admission_issuance_authorized"] is True
    assert authority[
        "admission_consumption_or_exact_live_execution_authorized"
    ] is False
    assert authority["credential_presence_or_value_read_authorized"] is False
    assert authority[
        "model_provider_or_execution_network_calls_authorized"
    ] is False
    assert authority["second_claim_family_canary_authorized"] is False
    assert boundary["admission_issued"] is True
    assert boundary["admission_consumed"] is False
    assert boundary["execution_started"] is False
    assert boundary["supervisor_launched"] is False
    assert counts["new_admissions"] == 1
    assert set(
        value for key, value in counts.items() if key != "new_admissions"
    ) == {0}


def test_project_state_advances_only_to_R7_execution_authority() -> None:
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)

    assert program["next_action"]["item_id"] in {
        CURRENT_ISSUANCE,
        NEXT_ACTION,
        EXACT_EXECUTION,
        FAILURE_DISPOSITION,
        AFTER_DISPOSITION,
    }
    assert detailed["current_next_action"] in {
        CURRENT_ISSUANCE,
        NEXT_ACTION,
        EXACT_EXECUTION,
        FAILURE_DISPOSITION,
        AFTER_DISPOSITION,
    }
