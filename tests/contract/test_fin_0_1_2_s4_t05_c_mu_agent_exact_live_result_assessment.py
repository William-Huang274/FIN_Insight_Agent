from __future__ import annotations

import copy
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts" / "releases")]

import materialize_fin_ia_0_1_2_s4_t05_c_mu_agent_exact_live_result_and_assessment as module  # noqa: E402


def test_mu_exact_live_is_independently_L1_valid_and_not_owner_accepted() -> None:
    result = module.materialize(recorded_at="2026-08-05T06:45:00Z")
    assert result["status"] == "exact_live_success_independent_L1_pass_product_surface_pending"
    assert result["execution"] == {
        "provider_model": "deepseek-v4-pro",
        "provider_calls": 9,
        "local_fact_receipts": 3,
        "captures": 9,
        "business_artifacts": 9,
        "input_tokens": 56762,
        "output_tokens": 3162,
        "estimated_cost_usd": 0.02744241,
        "retry_count": 0,
        "all_finish_reason_stop": True,
        "all_transport_attempt_count_one": True,
    }
    assert result["independent_L1"]["status"] == "pass"
    assert result["agent_output_counts"] == {
        "claims": 6,
        "what_would_change": 9,
        "dependencies": 1,
        "conflicts": 3,
        "gaps": 4,
    }
    assert result["product_surface_boundary"]["MU_current_R2"] is False
    assert result["operational_finding"]["rerun_required"] is False


def test_result_hash_mutation_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "EXPECTED_RESULT_SHA256", "0" * 64)
    with pytest.raises(module.T05CMUExactAssessmentError, match="exact_result_drift"):
        module.materialize(recorded_at="2026-08-05T06:45:00Z")
