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
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_exact_r2_execution_and_"
    "paired_assessment_authority_decision_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_t05_authority_is_exact_once_and_conditionally_allows_comparison() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]
    stop = decision["stop_contract"]

    assert decision["status"] == (
        "authorized_exact_once_and_conditional_read_only_paired_assessment"
    )
    assert authority["admission_exact_once_consumption_authorized"] is True
    assert authority["DELL_exact_live_execution_authorized"] is True
    assert authority[
        "paired_assessment_authorized_only_after_coherent_terminal_success"
    ] is True
    assert authority[
        "automatic_retry_fallback_replay_relaunch_patch_or_rerun_authorized"
    ] is False
    assert authority["Human_review_or_owner_acceptance_authorized"] is False
    assert authority["S4_T06_or_later_authorized"] is False
    assert stop["paired_assessment_after_failure_allowed"] is False
    assert stop["automatic_second_execution_allowed"] is False


def test_t05_authority_binds_the_issued_admission_and_current_bytes() -> None:
    decision = _load(DECISION)
    source = decision["source_authority"]
    admission_path = ROOT / source["admission_ref"]
    issuance_path = ROOT / source["issuance_ref"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(admission_path)
    )
    target = load_execution_target(issuance_path)

    assert _sha256(admission_path) == source["admission_file_sha256"]
    assert _sha256(issuance_path) == source["issuance_file_sha256"]
    assert _sha256(ROOT / source["host_capability_receipt_ref"]) == (
        source["host_capability_receipt_sha256"]
    )
    assert canonical_digest(admission.digest_payload()) == (
        source["admission_digest"]
    )
    assert _load_admission(admission_path, target) == admission


def test_t05_execution_target_and_preflight_are_closed_and_bounded() -> None:
    decision = _load(DECISION)
    target = decision["exact_execution_target"]
    verification = decision["pre_execution_verification"]
    success = decision["success_contract"]

    assert target["maximum_semantic_model_calls"] == 12
    assert target["maximum_provider_calls"] == 12
    assert target["maximum_network_calls"] == 12
    assert target["maximum_output_tokens"] == 16800
    assert target["maximum_total_cost_usd"] == 0.1
    assert target["transport_retry_count"] == 0
    assert target["source_network_calls_allowed"] is False
    assert target["external_tool_calls_allowed"] is False
    assert target["live_business_case_head_writes_allowed"] is False
    assert verification["project_os_full_chain_preflight"] == "pass"
    assert verification["open_full_chain_blocker_count"] == 0
    assert verification["exact_runner_zero_call_preflight"] == (
        "pass_exact_zero_call_execution_preflight"
    )
    assert verification["credential_value_read_output_or_persisted"] is False
    assert verification["exact_code_bindings_match"] is True
    assert verification[
        "canonical_work_unit_attempt_run_artifact_counts_before"
    ] == [0, 0, 0, 0]
    assert success["artifact_count"] == 9
    assert success["semantic_model_call_count"] == 12
