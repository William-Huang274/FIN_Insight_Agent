from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts" / "releases")]

import materialize_fin_ia_0_1_2_s4_t05_d_nvda_agent_exact_live_result_and_assessment as module  # noqa: E402


def test_t05_d_nvda_exact_live_independent_l1_pass() -> None:
    result = module.materialize(recorded_at="2026-08-05T18:05:00+08:00")
    assert module._sha256(module.EXACT_RESULT) == module.EXPECTED_RESULT_SHA256
    assert result["source_exact_result"]["terminal_digest"] == module.EXPECTED_TERMINAL_DIGEST
    assert result["execution"] == {
        "provider_model": "deepseek-v4-pro",
        "provider_calls": 9,
        "local_fact_receipts": 3,
        "captures": 9,
        "business_artifacts": 9,
        "input_tokens": 55060,
        "output_tokens": 3148,
        "estimated_cost_usd": 0.02668987,
        "retry_count": 0,
        "all_finish_reason_stop": True,
        "all_transport_attempt_count_one": True,
    }
    assert result["independent_L1"]["status"] == "pass"
    assert result["independent_L1"]["case_identity_NVDA"] is True
    assert result["product_surface_boundary"]["post_transfer_NVDA_R2"] is False


def test_t05_d_nvda_exact_live_result_digest_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        module,
        "EXPECTED_RESULT_SHA256",
        "0" * 64,
    )
    with pytest.raises(module.T05DNVDAExactAssessmentError, match="exact_result_drift"):
        module.materialize(recorded_at="2026-08-05T18:05:00+08:00")
