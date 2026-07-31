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
    "fin_ia_0_1_s4_t05_dell_replacement_exact_r2_execution_and_"
    "paired_assessment_authority_decision_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_replacement_authority_is_exact_once_and_success_conditional() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]
    stop = decision["stop_contract"]

    assert decision["status"] == (
        "authorized_replacement_exact_once_and_"
        "conditional_read_only_paired_assessment"
    )
    assert authority[
        "replacement_admission_exact_once_consumption_authorized"
    ] is True
    assert authority["DELL_replacement_exact_live_execution_authorized"] is True
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


def test_replacement_authority_binds_current_admission_and_preflight() -> None:
    decision = _load(DECISION)
    source = decision["source_authority"]
    admission_path = ROOT / source["admission_ref"]
    issuance_path = ROOT / source["issuance_ref"]
    preflight_path = ROOT / source["preflight_ref"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(admission_path)
    )
    target = load_execution_target(issuance_path)

    assert _sha256(admission_path) == source["admission_file_sha256"]
    assert _sha256(issuance_path) == source["issuance_file_sha256"]
    assert _sha256(preflight_path) == source["preflight_file_sha256"]
    assert _sha256(ROOT / source["host_capability_receipt_ref"]) == (
        source["host_capability_receipt_sha256"]
    )
    assert canonical_digest(admission.digest_payload()) == (
        source["admission_digest"]
    )
    assert _load_admission(admission_path, target) == admission


def test_replacement_execution_target_and_stop_contract_are_bounded() -> None:
    decision = _load(DECISION)
    target = decision["exact_execution_target"]
    verification = decision["pre_execution_verification"]
    success = decision["success_contract"]

    assert target["role_group_mapping_digest"] == (
        "73284fd4fc8ada1e45a44aa1a627d011ea591227842f5172eb6d9ae15f99c812"
    )
    assert target["evidence_alignment_digest"] == (
        "9c35e5345a13ef3a9e8f919c8a6b29016c0ba0961066fdfb06b62317054a9cfb"
    )
    assert target["evidence_dispatch_digest"] == (
        "6b96006f8d19d6ed7ddf59b3dec4b32d33a65ca5ff6516e1c248a6d53f09f9e8"
    )
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
    assert verification["target_work_unit_attempt_run_absent"] is True
    assert success["artifact_count"] == 9
    assert success["semantic_model_call_count"] == 12
