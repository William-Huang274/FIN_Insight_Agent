from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "releases"))

from prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
    BaselineDecisionPreflightError,
    _sha256,
    _tree_digest,
)
from run_fin_ia_0_1_s3_t09_paired_deterministic_baseline_materialization import (
    materialize,
    verify_materialized,
)


RELEASES = ROOT / "configs" / "releases"
DECISION = (
    RELEASES
    / "fin_ia_0_1_s3_t09_paired_deterministic_baseline_materialization_decision_v1_0.json"
)
SOURCE_DECISION = (
    RELEASES
    / "fin_ia_0_1_s3_t09_replacement_live_artifact_paired_baseline_decision_v1_0.json"
)
RESULT = (
    RELEASES
    / "fin_ia_0_1_s3_t09_paired_deterministic_baseline_materialization_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
TARGET_RUNTIME = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)


def test_materialized_baseline_is_exact_and_cannot_be_materialized_twice() -> None:
    target_database = TARGET_RUNTIME / "canonical-runtime" / "canonical.sqlite"
    target_objects = TARGET_RUNTIME / "canonical-runtime" / "objects"
    target_database_before = _sha256(target_database)
    target_objects_before = _tree_digest(target_objects)

    result = verify_materialized(
        runtime_root=TARGET_RUNTIME,
        decision_path=DECISION,
        source_decision_path=SOURCE_DECISION,
    )

    assert result["status"] == "pass_materialized_baseline_read_only_verification"
    assert result["terminal_states"] == {
        "work_unit": "succeeded",
        "attempt": "succeeded",
        "research_run": "succeeded",
        "attempt_no": 1,
        "maximum_attempts": 1,
        "retry_budget": 0,
    }
    assert tuple(result["artifact_manifest"]) == (
        "deterministic_research_result",
        "s3_three_cell_workpaper",
        "s3_three_cell_report",
        "s3_three_cell_trace_review",
    )
    assert result["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "evidence_promotions": 0,
        "agent_reruns": 0,
        "human_review_writes": 0,
    }
    assert result["boundary"]["paired_comparison_performed"] is False

    with pytest.raises(BaselineDecisionPreflightError, match="baseline_work_unit_not_fresh"):
        materialize(
            runtime_root=TARGET_RUNTIME,
            decision_path=DECISION,
            source_decision_path=SOURCE_DECISION,
        )

    assert _sha256(target_database) == target_database_before
    assert _tree_digest(target_objects) == target_objects_before


def test_materialization_result_closes_baseline_gap_without_advancing_authority() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    assert result["status"] == (
        "pass_exact_once_deterministic_baseline_materialized_and_read_only_verified"
    )
    assert result["terminal_truth"]["exact_deterministic_run_cardinality"] == 1
    assert len(result["artifact_manifest"]) == 4
    assert result["stage_decision"]["RC_P36_036"].startswith("closed_")
    assert result["stage_decision"]["RC_P36_037"].endswith("_pending")
    assert result["next_action"] == (
        "S3-T09-OWNER-GRADE-V3-FRESH-AGENT-PROOF-DECISION"
    )
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert backlog["next_action"]["deterministic_baseline_materialization_authorized"] is True
    assert backlog["next_action"]["fresh_v3_agent_proof_decision_authorized"] is True
    assert backlog["next_action"]["fresh_v3_exact_admission_issuance_authorized"] is True
    assert backlog["next_action"]["fresh_v3_exact_admission_issued"] is True
    assert backlog["next_action"]["fresh_v3_exact_live_execution_authorized"] is True
    assert backlog["next_action"]["agent_rerun_authorized"] is False
    assert backlog["next_action"]["owner_review_or_T10_authorized"] is False
