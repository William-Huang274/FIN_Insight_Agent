from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_POST_PROVIDER_FAILURE_ENVELOPE_CONTRACT_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
    _logical_snapshot,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


PROOF = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r8_typed_failure_"
    "envelope_fresh_agent_proof_decision_v1_0.json"
)
ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r8_typed_failure_"
    "envelope_fresh_exact_admission_r8.json"
)
ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r8_typed_failure_"
    "envelope_fresh_exact_admission_issuance_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_typed_post_"
    "provider_failure_envelope_and_canonical_observability_minimum_"
    "zero_call_implementation_v1_0.json"
)
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r8_typed_failure_"
    "envelope_exact_live_execution_failure_result_v1_0.json"
)
CAPACITY_DISPOSITION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r8_specialist_assembled_output_byte_budget_"
    "zero_call_root_cause_disposition_v1_0.json"
)
CAPACITY_IMPLEMENTATION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r8_specialist_validated_segment_union_"
    "capacity_and_safe_byte_telemetry_minimum_zero_call_"
    "implementation_v1_0.json"
)
CAPACITY_FRESH_PROOF = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r8_specialist_validated_segment_union_"
    "capacity_fresh_agent_proof_decision_v1_0.json"
)
CAPACITY_R9_ISSUANCE = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r9_specialist_validated_segment_union_"
    "capacity_fresh_exact_admission_issuance_v1_0.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_r8_proof_and_issuance_bind_fresh_unconsumed_identity() -> None:
    proof = _load(PROOF)
    issuance = _load(ISSUANCE)
    implementation = _load(IMPLEMENTATION)
    target = load_execution_target(ISSUANCE)
    admission = _load_admission(ADMISSION, target)

    assert proof["status"].startswith(
        "pass_zero_call_independent_R8"
    )
    assert issuance["source_proof_decision_sha256"] == _sha256(PROOF)
    assert issuance["issued_admission"]["admission_file_sha256"] == (
        _sha256(ADMISSION)
    )
    admission_digest = canonical_digest(admission.digest_payload())
    assert admission_digest == proof["prospective_admission"]["digest"]
    assert admission_digest == (
        issuance["issued_admission"]["admission_digest"]
    )
    assert implementation["source_disposition"][
        "selected_contract_ref"
    ] == S3_POST_PROVIDER_FAILURE_ENVELOPE_CONTRACT_REF
    assert target.work_unit_id == proof["fresh_identity"]["work_unit_id"]
    assert target.attempt_id == proof["fresh_identity"]["attempt_id"]
    assert target.research_run_id == (
        proof["fresh_identity"]["research_run_id"]
    )

    runtime_root = ROOT / target.runtime_root_ref
    snapshot = _logical_snapshot(
        runtime_root / "canonical-runtime/canonical.sqlite",
        target.case_id,
    )
    if RESULT.exists():
        assert target.work_unit_id in snapshot["work_unit_ids"]
        assert target.attempt_id in snapshot["attempt_ids"]
        assert target.research_run_id in snapshot["research_run_ids"]
        assert _load(RESULT)["admission"]["consumed"] is True
    else:
        assert target.work_unit_id not in snapshot["work_unit_ids"]
        assert target.attempt_id not in snapshot["attempt_ids"]
        assert target.research_run_id not in snapshot["research_run_ids"]


def test_r8_issuance_constructs_executor_without_provider_call() -> None:
    target = load_execution_target(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(ADMISSION)
    )
    admission.assert_profile_admissible()
    assert canonical_digest(admission.digest_payload()) == (
        target.admission_digest
    )
    provider_calls = 0

    def forbidden_provider(**_: Any) -> dict[str, Any]:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider_forbidden_during_R8_issuance")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=forbidden_provider,
    )
    assert provider_calls == 0
    assert _load(ISSUANCE)["issuance_boundary"] == {
        "admission_issued": True,
        "admission_consumed": False,
        "execution_started": False,
        "model_or_provider_call_started": False,
        "paired_assessment_performed": False,
        "S4_T06_entered": False,
    }


def test_r8_terminal_result_preserves_typed_observation_and_stops_sequence() -> None:
    result = _load(RESULT)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    runtime = result["runtime_evidence"]

    assert result["canonical_terminal_truth"]["work_unit_state"] == "failed"
    assert result["canonical_terminal_truth"]["attempt_state"] == "failed"
    assert result["canonical_terminal_truth"]["research_run_state"] == "failed"
    assert result["canonical_terminal_truth"]["artifact_count"] == 0
    assert result["provider_execution"]["model_calls"] == 9
    assert result["provider_execution"]["usage_receipt_count"] == 9
    assert result["provider_execution"]["restricted_capture_count"] == 9
    assert result["typed_failure_envelope_result"]["contract_ref"] == (
        S3_POST_PROVIDER_FAILURE_ENVELOPE_CONTRACT_REF
    )
    assert result["typed_failure_envelope_result"][
        "completed_logical_node_receipts_preserved"
    ] == 2
    assert result["first_credible_failure"]["issue_id"].startswith(
        "RC-P36-065"
    )
    assert result["supervision"][
        "automatic_retry_count"
    ] == result["supervision"]["rerun_count"] == 0
    assert _sha256(ROOT / runtime["result_ref"]) == runtime["result_sha256"]
    assert _sha256(ROOT / runtime["terminal_inspection_ref"]) == (
        runtime["terminal_inspection_sha256"]
    )
    assert result["next_action"].endswith(
        "ZERO-CALL-ROOT-CAUSE-DISPOSITION-DECISION"
    )
    current_next = program["next_action"]["item_id"]
    assert detailed["current_next_action"] == current_next
    assert result["stage_acceptance"]["paired_assessment"].startswith(
        "not_performed"
    )
    assert result["stage_acceptance"]["S4_T06"] == "not_entered"
