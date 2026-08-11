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
from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (
    _validate_host_capability_receipt,
)
from sec_agent.canonical_runtime.models import canonical_digest


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_claim_support_role_v2_r7_"
    "exact_live_execution_and_success_only_paired_assessment_authority_"
    "decision_v1_0.json"
)
ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_claim_epistemic_support_role_"
    "compiled_contract_v2_fresh_exact_admission_r7.json"
)
ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_claim_epistemic_support_role_"
    "compiled_contract_v2_fresh_exact_admission_r7_issuance_v1_0.json"
)
RUNNER_PREFLIGHT = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-"
    "validation-r1/s4_t06_mu_claim_support_role_v2_r7_authority_"
    "preflight_live_execution_preflight.json"
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
EXECUTION_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_claim_support_role_v2_r7_"
    "exact_live_execution_failure_result_v1_0.json"
)
CURRENT_AUTHORITY = (
    "S4-T06-MU-CLAIM-EPISTEMIC-SUPPORT-ROLE-COMPILED-CONTRACT-V2-R7-"
    "EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT-"
    "AUTHORITY-DECISION"
)
NEXT = (
    "S4-T06-MU-CLAIM-EPISTEMIC-SUPPORT-ROLE-COMPILED-CONTRACT-V2-R7-"
    "EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT"
)
FAILURE_DISPOSITION = (
    "S4-T06-MU-R7-FIRST-CREDIBLE-FAILURE-PROJECT-BLOCK-OR-"
    "DETERMINISTIC-PLANNER-SCOPE-DISPOSITION-DECISION"
)
AFTER_DISPOSITION = (
    "S4-T06-MU-WWC-PROVIDER-CANDIDATE-VALIDATION-AND-DETERMINISTIC-"
    "FINAL-SELECTION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)
EXPECTED_ADMISSION_SHA256 = (
    "10bb6b6ec2e735e682d190087103f6a8d0a5d403eee69a324dc1842f3c39b91c"
)
EXPECTED_ISSUANCE_SHA256 = (
    "3188366b8c7302a38c547283510edc21f88a2a68567de0c9d47f06789fc9d6cc"
)
EXPECTED_ADMISSION_DIGEST = (
    "4ed2a62d43c4bda4c0a41097b81dfc2dbd71151725fd12c6d1c9112c47077e75"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_authority_binds_issued_unconsumed_R7_admission() -> None:
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

    capability, capability_sha = _validate_host_capability_receipt(
        ROOT / decision["source_authority"]["host_capability_receipt_ref"]
    )
    assert capability["status"] == (
        "pass_direct_runner_survived_launcher_and_self_finalized"
    )
    assert capability_sha == decision["source_authority"][
        "host_capability_receipt_sha256"
    ]
    supervision_root = ROOT / decision["exact_execution_target"][
        "supervision_root"
    ]
    if EXECUTION_RESULT.exists():
        assert supervision_root.exists() is True
        assert (supervision_root / "exit_receipt.json").exists() is True
    else:
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
    assert runner["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
    }
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


def test_authority_preserves_success_stop_and_nonexecution_contracts() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]
    target = decision["exact_execution_target"]
    success = decision["success_contract"]
    stop = decision["stop_contract"]
    boundary = decision["decision_boundary"]

    assert authority[
        "future_R7_admission_exact_once_consumption_authorized"
    ] is True
    assert authority["future_R7_exact_live_execution_authorized"] is True
    assert authority[
        "current_turn_admission_consumption_or_execution_authorized"
    ] is False
    assert authority["automatic_R8_authorized"] is False
    assert authority["second_claim_family_canary_authorized"] is False
    assert target["transport_retry_count"] == 0
    assert target["maximum_provider_calls"] == 12
    assert target["maximum_output_tokens"] == 16800
    assert target["output_only_cost_ceiling_usd"] < (
        target["maximum_total_cost_usd"]
    )
    assert success["provider_interaction_audit_capture_v2_count"] == 12
    assert success["artifact_count"] == 9
    assert success[
        "compiled_claim_support_role_contract_v2_compliance_required"
    ] is True
    assert success["independent_final_artifact_L1_required"] is True
    assert success["paired_assessment_requires_retained_Agent_gain"] is True
    assert stop["automatic_second_execution_allowed"] is False
    assert stop["automatic_R8_allowed"] is False
    assert set(boundary.values()) == {False}


def test_project_state_advances_only_to_R7_exact_execution() -> None:
    decision = _load(DECISION)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(S4_BACKLOG)

    assert decision["next_action"] == NEXT
    assert decision["next_action_authorized"] is True
    assert program["next_action"]["item_id"] in {
        CURRENT_AUTHORITY,
        NEXT,
        FAILURE_DISPOSITION,
        AFTER_DISPOSITION,
    }
    assert detailed["current_next_action"] in {
        CURRENT_AUTHORITY,
        NEXT,
        FAILURE_DISPOSITION,
        AFTER_DISPOSITION,
    }
    if program["next_action"]["item_id"] == NEXT:
        assert program["next_action"][
            "claim_compiled_contract_v2_R7_execution_authorized"
        ] is True
        assert program["next_action"][
            "claim_compiled_contract_v2_R7_execution_started"
        ] is False
