from __future__ import annotations

import json
from pathlib import Path

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "configs/releases/fin_ia_0_1_3_s2_05_nvda_raw_replacement_r2_and_three_case_boundary_result_v1_0.json"


def test_nvda_r2_result_is_digest_bound_complete_and_non_promotable() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    body = {key: value for key, value in result.items() if key != "result_digest"}
    assert result["result_digest"] == canonical_digest(body)
    execution = result["execution"]
    assert execution["provider_calls"] == execution["captures"] == execution["logical_nodes"] == 10
    assert execution["retry_count"] == execution["fallback_count"] == 0
    assert execution["terminal_status"] == "terminal_completed_layered_raw_evaluation"
    assert result["numeric_scale_reproof"]["R1_project_false_positive_recurred"] is False
    assert result["numeric_scale_reproof"]["RC_P36_144_numeric_scale_repair_live_proven"] is True
    assert result["campaign_disposition"]["business_promotion"] is False


def test_three_case_v1_4_replay_preserves_quality_failures_and_no_raw_mutation() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    replay = result["evaluator_disposition"]["three_case_v1_4_replay"]
    assert replay["raw_mutations"] == 0
    assert replay["DELL"]["breakdown"] == {"L1": 3, "L2": 1, "L3": 23, "L4": 0}
    assert replay["MU"]["breakdown"] == {"L1": 8, "L2": 2, "L3": 14, "L4": 0}
    assert replay["NVDA"]["breakdown"] == {"L1": 4, "L2": 1, "L3": 27, "L4": 0}
    campaign = result["campaign_disposition"]
    assert campaign["S2_05_three_case_raw_campaign_complete"] is True
    assert campaign["S2_06_three_case_deterministic_boundaries_materialized"] is True
    assert campaign["S2_06_supervisor_recoverability_complete"] is False
    assert campaign["automatic_R3_or_raw_rerun"] is False
    assert campaign["unified_supervisor_authority_issued"] is False


def test_nvda_r2_result_keeps_execution_time_and_posthoc_evaluators_separate() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    disposition = result["evaluator_disposition"]
    assert disposition["execution_time_v1_3"]["breakdown"] == {
        "L1": 5,
        "L2": 2,
        "L3": 27,
        "L4": 0,
    }
    assert disposition["final_v1_4"]["breakdown"] == {
        "L1": 4,
        "L2": 1,
        "L3": 27,
        "L4": 0,
    }
    assert result["research_quality"]["formal_hidden_score"] is False
    assert result["supervision_boundaries"]["supervisor_model_correction_performed"] is False
    assert result["supervision_boundaries"]["corrected_candidates_created"] == 0
