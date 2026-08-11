from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest
from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
)


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r9_specialist_validated_"
    "segment_union_capacity_exact_live_execution_and_paired_assessment_"
    "authority_decision_v1_0.json"
)
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r9_specialist_validated_"
    "segment_union_capacity_exact_live_execution_failure_result_v1_0.json"
)
DISPOSITION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r9_profile_result_"
    "validation_after_six_node_completion_zero_call_root_cause_"
    "disposition_v1_0.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
NEXT_ACTION = (
    "S4-T05-DELL-R9-SPECIALIST-VALIDATED-SEGMENT-UNION-CAPACITY-"
    "EXACT-LIVE-EXECUTION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_R9_authority_binds_the_exact_issued_fresh_chain() -> None:
    decision = _load(DECISION)
    source = decision["source_authority"]
    admission_path = ROOT / source["admission_ref"]
    issuance_path = ROOT / source["issuance_ref"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(admission_path)
    )
    target = load_execution_target(issuance_path)

    for ref_key, sha_key in (
        ("fresh_proof_ref", "fresh_proof_sha256"),
        ("admission_ref", "admission_file_sha256"),
        ("issuance_ref", "issuance_file_sha256"),
        ("project_os_preflight_ref", "project_os_preflight_sha256"),
        ("runner_preflight_ref", "runner_preflight_sha256"),
        ("host_capability_receipt_ref", "host_capability_receipt_sha256"),
    ):
        assert _sha256(ROOT / source[ref_key]) == source[sha_key]
    assert canonical_digest(admission.digest_payload()) == source[
        "admission_digest"
    ]
    assert target.admission_digest == source["admission_digest"]
    assert target.work_unit_id == decision["exact_execution_target"][
        "work_unit_id"
    ]
    assert target.attempt_id == decision["exact_execution_target"][
        "attempt_id"
    ]
    assert target.research_run_id == decision["exact_execution_target"][
        "research_run_id"
    ]


def test_R9_authority_is_exact_once_success_conditional_and_zero_call() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]

    assert decision["status"] == (
        "authorized_R9_exact_once_and_conditional_read_only_paired_"
        "assessment_execution_not_started"
    )
    assert authority["R9_admission_exact_once_consumption_authorized"] is True
    assert authority["DELL_R9_exact_live_execution_authorized"] is True
    assert authority[
        "paired_assessment_authorized_only_after_coherent_terminal_success"
    ] is True
    assert authority[
        "automatic_retry_fallback_replay_relaunch_patch_or_rerun_authorized"
    ] is False
    assert authority["S4_T06_or_later_authorized"] is False
    assert authority[
        "dependency_conflict_Writer_Verifier_or_all_node_atomization_authorized"
    ] is False
    assert set(decision["decision_boundary"].values()) == {False}
    assert set(decision["observed_counts"].values()) == {0}


def test_R9_authority_binds_zero_call_preflight_code_budget_and_success() -> None:
    decision = _load(DECISION)
    verification = decision["pre_execution_verification"]
    target = decision["exact_execution_target"]
    success = decision["success_contract"]
    project_preflight = _load(
        ROOT / decision["source_authority"]["project_os_preflight_ref"]
    )
    runner_preflight = _load(
        ROOT / decision["source_authority"]["runner_preflight_ref"]
    )

    assert project_preflight["status"] == "pass"
    assert project_preflight["open_full_chain_blockers"] == []
    assert runner_preflight["status"] == (
        "pass_exact_zero_call_execution_preflight"
    )
    assert runner_preflight["execution_state_counts_before"] == (
        runner_preflight["execution_state_counts_after"]
    )
    assert set(runner_preflight["observed_counts"].values()) == {0}
    assert verification["credential_present"] is True
    assert verification["credential_value_read_output_or_persisted"] is False
    assert verification["provider_health_probe_performed"] is False
    assert verification["fresh_identity_absent"] is True
    assert verification["exact_code_binding_count"] == 7
    for relative_path, expected_sha256 in verification[
        "exact_code_bindings"
    ].items():
        assert _sha256(ROOT / relative_path) == expected_sha256
    assert (
        target["maximum_semantic_model_calls"],
        target["maximum_provider_calls"],
        target["maximum_network_calls"],
        target["maximum_output_tokens"],
        target["maximum_total_cost_usd"],
        target["transport_retry_count"],
    ) == (12, 12, 12, 18000, 0.1, 0)
    assert target["provider_local_segment_whole_caps"] == [
        6000,
        8192,
        24576,
    ]
    assert (
        success["logical_node_count"],
        success["semantic_model_call_count"],
        success["artifact_count"],
    ) == (6, 12, 9)
    assert success["typed_verifier_success_required"] is True
    assert decision["stop_contract"][
        "paired_assessment_after_failure_allowed"
    ] is False
    assert decision["stop_contract"]["automatic_second_execution_allowed"] is False


def test_R9_authority_advances_only_to_the_exact_live_execution() -> None:
    decision = _load(DECISION)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    task = next(
        item for item in detailed["tasks"] if item["item_id"] == "S4-T05"
    )

    assert decision["next_action"] == NEXT_ACTION
    assert decision["conditional_next_action"][
        "on_authority_decision_complete"
    ] == NEXT_ACTION
    assert program["next_action"]["item_id"] == detailed["current_next_action"]
    assert task["R9_execution_authorized"] is True
    assert task["R9_paired_assessment_success_only_authorized"] is True
    if RESULT.exists():
        result = _load(RESULT)
        assert task["R9_execution_started"] is True
        assert task["R9_admission_consumed"] is True
        assert task["R9_execution_completed"] is True
        if DISPOSITION.exists():
            assert program["next_action"]["item_id"] == _load(
                DISPOSITION
            )["next_action"]
        else:
            assert program["next_action"]["item_id"] == result["next_action"]
    else:
        assert program["next_action"]["item_id"] == NEXT_ACTION
        assert task["R9_execution_started"] is False
        assert task["R9_admission_consumed"] is False
    assert detailed["non_inflation"]["DELL_R2"] is False
