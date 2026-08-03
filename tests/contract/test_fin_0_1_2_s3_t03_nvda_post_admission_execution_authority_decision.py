from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
)
from sec_agent.canonical_runtime.models import canonical_digest


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_post_admission_"
    "exact_live_execution_authority_decision_v1_0.json"
)
ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_fresh_exact_"
    "admission_r1.json"
)
ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_fresh_exact_"
    "admission_issuance_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_26.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
NEXT = (
    "FIN-0.1.2-S3-T03-NVDA-BOUND-EXECUTION-LAUNCHER-PARENT-"
    "SUPERVISOR-AND-ZERO-CALL-PREFLIGHT-MINIMUM-IMPLEMENTATION"
)
IMPLEMENTATION_PASS_NEXT = (
    "FIN-0.1.2-S3-T03-NVDA-EXACT-LIVE-EXECUTION-AUTHORITY-DECISION-R2"
)
R2_EXECUTION_NEXT = (
    "FIN-0.1.2-S3-T03-NVDA-EXACT-LIVE-EXECUTION-AND-TERMINAL-"
    "MATERIALIZATION"
)
FAILURE_NEXT = (
    "FIN-0.1.2-S3-T03-NVDA-RESEARCH-LEAD-LOCAL-FACT-PRESENCE-AND-"
    "CLAIM-ALIAS-SEMANTIC-OWNERSHIP-REGRESSION-DISPOSITION-DECISION"
)
TERMINAL_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_exact_live_execution_"
    "terminal_failure_result_v1_0.json"
)
EXPECTED_ADMISSION_SHA = (
    "89254b2246ee8cced822edb93f4b5d9a3a4b6adc7f0223f1edade53d188d1720"
)
EXPECTED_ISSUANCE_SHA = (
    "41db08cb6fc08ceb6210ceffbaae15c19ea73502b0ff8c895c1d9d2f75b787dd"
)
EXPECTED_ADMISSION_DIGEST = (
    "eed177b1124c8db930193196f71eb653b85a2b24d9c92a192251984def4fd1c8"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_decision_preserves_exact_issued_unconsumed_admission() -> None:
    decision = _load(DECISION)
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(_load(ADMISSION))
    admission.assert_profile_admissible()

    assert _sha256(ADMISSION) == EXPECTED_ADMISSION_SHA
    assert _sha256(ISSUANCE) == EXPECTED_ISSUANCE_SHA
    assert canonical_digest(admission.digest_payload()) == EXPECTED_ADMISSION_DIGEST
    assert decision["source_authority"]["admission_file_sha256"] == EXPECTED_ADMISSION_SHA
    assert decision["source_authority"]["issuance_file_sha256"] == EXPECTED_ISSUANCE_SHA
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False


def test_authority_fails_closed_on_missing_real_execution_entrypoint() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]
    audit = decision["entrypoint_audit"]

    assert decision["status"].startswith("blocked_before_exact_live")
    assert authority["current_zero_call_execution_authority_decision_authorized"]
    assert not authority["future_exact_live_execution_authorized_by_this_decision"]
    assert not authority["current_turn_admission_consumption_or_execution_authorized"]
    assert audit["library_execute_function_present"]
    assert audit["library_terminal_recovery_function_present"]
    assert not audit["command_main_entrypoint_present"]
    assert not audit["admission_bound_child_process_entrypoint_present"]
    assert not audit["deepseek_transport_assembly_present"]
    assert not audit["parent_process_launch_wait_timeout_and_exit_supervision_present"]
    assert audit["non_test_runtime_references_to_execute_or_finalize_functions"] == 0


def test_zero_call_decision_records_presence_only_and_no_execution() -> None:
    decision = _load(DECISION)
    verification = decision["pre_execution_verification"]
    counts = decision["decision_boundary"]

    assert verification["project_os_scope_preflight"] == "pass"
    assert verification["open_full_chain_blocker_count_before_entrypoint_audit"] == 0
    assert verification["credential_presence_checked"]
    assert verification["credential_present"]
    assert not verification["credential_value_read_output_or_persisted"]
    assert not verification["provider_health_probe_performed"]
    assert counts["credential_presence_checks"] == 1
    assert set(value for key, value in counts.items() if key != "credential_presence_checks") == {0}


def test_gap_stays_in_s3_t03_and_does_not_expand_product_scope() -> None:
    decision = _load(DECISION)
    disposition = decision["issue_disposition"]

    assert disposition["issue_id"].startswith("RC-P36-107-")
    assert disposition["owned_by_stage"] == "S3-T03"
    assert not disposition["model_or_provider_fault_established"]
    assert not disposition["financial_truth_or_business_input_failure_established"]
    assert not disposition["S0_S1_or_S2_reopened"]
    assert not disposition["admission_invalidated"]
    assert disposition["maximum_implementation_bundles"] == 1
    assert not disposition["automatic_second_implementation_bundle"]


def test_projection_and_backlog_stop_before_live_execution() -> None:
    decision = _load(DECISION)
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)["next_action"]

    assert decision["next_action"] == NEXT
    assert not decision["next_action_authorized"]
    assert projection["decision_binding"]["sha256"] == _sha256(DECISION)
    assert projection["decision_binding"]["bytes"] == DECISION.stat().st_size
    assert projection["current_truth"]["current_next_action"] == NEXT
    assert backlog["item_id"] in {
        NEXT,
        IMPLEMENTATION_PASS_NEXT,
        R2_EXECUTION_NEXT,
        FAILURE_NEXT,
    }
    if backlog["item_id"] == NEXT:
        assert backlog["current_projection_sha256"] == _sha256(PROJECTION)
        assert backlog["S3_T03_bound_launcher_parent_supervisor_missing"] is True
    elif backlog["item_id"] == IMPLEMENTATION_PASS_NEXT:
        current = ROOT / backlog["current_projection_ref"]
        assert current.name == "fin_ia_0_1_2_current_program_projection_v2_27.json"
        assert backlog["current_projection_sha256"] == _sha256(current)
        assert backlog["S3_T03_bound_launcher_parent_supervisor_missing"] is False
    elif backlog["item_id"] == R2_EXECUTION_NEXT:
        current = ROOT / backlog["current_projection_ref"]
        assert current.name == "fin_ia_0_1_2_current_program_projection_v2_28.json"
        assert backlog["current_projection_sha256"] == _sha256(current)
        assert backlog["S3_T03_exact_live_execution_authorized_now"] is True
    else:
        current = ROOT / backlog["current_projection_ref"]
        assert current.name == "fin_ia_0_1_2_current_program_projection_v2_29.json"
        assert backlog["current_projection_sha256"] == _sha256(current)
        assert backlog["S3_T03_exact_live_execution_authorized_now"] is False
        assert backlog["S3_T03_execution_result_sha256"] == _sha256(
            TERMINAL_RESULT
        )
    if backlog["item_id"] == FAILURE_NEXT:
        assert backlog["S3_T03_fresh_admission_consumed"] is True
        assert backlog["S3_T03_execution_started"] is True
    else:
        assert backlog["S3_T03_fresh_admission_consumed"] is False
        assert backlog["S3_T03_execution_started"] is False


def test_project_os_records_the_new_owned_blocker() -> None:
    decision = _load(DECISION)
    issue_id = decision["issue_disposition"]["issue_id"]
    capability = (ROOT / "docs/project_os/capability_status_ledger.jsonl").read_text(
        encoding="utf-8"
    )
    root_cause = (ROOT / "docs/project_os/root_cause_issue_ledger.jsonl").read_text(
        encoding="utf-8"
    )
    context = (ROOT / "docs/project_os/current_context_pack.zh-CN.md").read_text(
        encoding="utf-8"
    )

    assert issue_id in capability
    assert issue_id in root_cause
    assert NEXT in context
