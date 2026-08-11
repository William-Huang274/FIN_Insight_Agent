from __future__ import annotations

import json
from pathlib import Path

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "configs/releases/fin_ia_0_1_3_s2_05_nvda_raw_r1_terminal_and_numeric_scale_disposition_v1_0.json"


def test_nvda_r1_result_is_digest_bound_failed_and_non_promotable() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    body = {key: value for key, value in result.items() if key != "result_digest"}
    assert result["result_digest"] == canonical_digest(body)
    execution = result["execution"]
    assert execution["provider_calls"] == execution["captures"] == 1
    assert execution["retry_count"] == execution["fallback_count"] == 0
    assert execution["terminal_status"] == "terminal_failed_no_retry"
    assert result["root_cause"]["runtime_false_positive"] is True
    assert result["root_cause"]["model_authored_unbound_financial_value"] is False
    assert result["campaign_disposition"]["business_promotion"] is False


def test_nvda_r1_result_preserves_consumed_failure_and_requires_new_authority() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    campaign = result["campaign_disposition"]
    assert result["research_quality"]["raw_chain_complete"] is False
    assert result["research_quality"]["formal_score"] is False
    assert campaign["NVDA_raw_measurement"] == "incomplete_project_gate_false_positive"
    assert campaign["automatic_replacement_or_rerun"] is False
    assert campaign["replacement_authority_may_be_considered_separately"] is True
    assert result["pre_execution_invocation_disposition"]["admission_consumed"] is False
