from __future__ import annotations

import json
from pathlib import Path

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "configs/releases/fin_ia_0_1_3_s2_05_mu_raw_exact_live_and_s2_06_boundary_result_v1_0.json"


def test_mu_raw_result_is_digest_bound_complete_failed_and_non_promotable() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    body = {key: value for key, value in result.items() if key != "result_digest"}
    assert result["result_digest"] == canonical_digest(body)
    assert result["execution"]["logical_nodes"] == 10
    assert result["execution"]["provider_calls"] == 10
    assert result["execution"]["captures"] == 10
    assert result["execution"]["retry_count"] == 0
    assert result["execution"]["fallback_count"] == 0
    assert result["evaluator_disposition"]["final_v1_3"]["breakdown"] == {"L1": 6, "L2": 2, "L3": 14}
    assert result["campaign_disposition"]["MU_raw_measurement"] == "complete_quality_fail"
    assert result["campaign_disposition"]["business_promotion"] is False


def test_mu_result_preserves_raw_first_campaign_and_no_automatic_nvda() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    campaign = result["campaign_disposition"]
    assert campaign["DELL_raw_measurement"] == "complete_quality_fail"
    assert campaign["MU_raw_measurement"] == "complete_quality_fail"
    assert campaign["NVDA_raw_measurement"] == "not_started"
    assert campaign["automatic_next_case"] is False
    assert campaign["NVDA_raw_authority_may_be_considered_separately"] is True
    assert campaign["supervisor_model_correction_before_three_case_raw_complete"] is False
    assert result["supervision_boundary"]["hidden_gold_visible_to_correction"] is False
    assert result["research_quality"]["hidden_gold_diagnostic_only"]["formal_score"] is False
