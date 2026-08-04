from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests/contract")]

from scripts.releases.run_fin_ia_0_1_2_s4_t04_nvda_current_evidence_exact_live import (
    execute_exact_once,
    zero_call_preflight,
)
from test_fin_0_1_2_s3_t02_production_runtime_integration import (
    _CurrentS3ProductionFake,
)


def test_zero_call_preflight_rehydrates_exact_admission(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    result = zero_call_preflight()
    assert result["status"] == "pass_exact_input_admission_transport_wiring_zero_call"
    assert result["model_provider_network_calls"] == [0, 0, 0]
    assert result["credential_present"] is False


def test_fake_exact_runner_materializes_nine_captures_and_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    fake = _CurrentS3ProductionFake(safe_lead=True)
    result = execute_exact_once(tmp_path / "runtime", completion=fake)
    assert result["status"] == "success"
    assert result["terminal"]["status"] == "success"
    assert len(result["capture_objects"]) == 9
    assert len(result["artifacts"]) == 9
    assert result["business_promotable"] is True
    text = json.dumps(result["artifacts"], ensure_ascii=False)
    assert "fdc1a10010f0d47ba7be5b420fc5cac860c3044d6690696463865ecce4b7bf65" in text
