from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s3_t09_layered_acceptance_final_"
    "exact_live_execution_result_v1_0.json"
)


def test_layered_final_exact_live_truth_and_stop_contract() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))

    assert result["status"] == (
        "terminal_failed_verifier_typed_ref_representation_drift_"
        "and_semantic_repair_findings_zero_artifacts_no_rerun"
    )
    assert result["provider_execution"]["model_provider_network_calls"] == [
        12,
        12,
        12,
    ]
    assert result["provider_execution"][
        "retry_fallback_replay_relaunch_rerun_counts"
    ] == [0, 0, 0, 0, 0]
    assert result["canonical_terminal_truth"] == {
        "work_unit_state": "failed",
        "attempt_state": "failed",
        "research_run_state": "failed",
        "terminal_consistent": True,
        "orphaned_run": False,
        "artifact_count": 0,
        "artifact_types": [],
    }


def test_layered_runtime_advanced_and_verifier_kept_product_blocked() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    alignment = result["layered_runtime_alignment_observation"]
    verifier = result["verifier_observation"]

    assert alignment["specialist_segments_completed"] == 9
    assert alignment["research_lead_completed"] is True
    assert alignment["memo_writer_completed"] is True
    assert alignment["verifier_completed_and_captured"] is True
    assert alignment["prior_narrative_terminal_failure_recurred"] is False
    assert alignment["research_lead_maximum_narrative_field_characters"] == 394
    assert verifier["artifact_or_claim_ref_observed_representation"] == (
        "typed_scoped_ref_objects"
    )
    assert verifier["local_validator_required_representation"] == (
        "nonblank_strings"
    )
    assert verifier["decision"] == "repair"
    assert verifier["issue_codes"] == [
        "scope_digest_mismatch",
        "unresolved_cross_cell_conflict",
        "unattributed_company_total_margins",
    ]
    assert result["stage_decision"]["nine_artifact_product_created"] is False
    assert result["stage_decision"]["S3_T09"] == "blocked"
