from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests/contract")]

from scripts.releases.issue_fin_ia_0_1_2_s4_t04_nvda_current_evidence_fresh_exact_admission import (
    render_issuance as render_original_issuance,
)
from scripts.releases.issue_fin_ia_0_1_2_s4_t04_nvda_current_evidence_replacement_exact_admission import (
    ADMISSION_REF,
    EXECUTION_IDENTITY,
    ISSUANCE_REF,
    render_replacement_issuance,
)
from scripts.releases.run_fin_ia_0_1_2_s4_t04_nvda_current_evidence_replacement_exact_live import (
    EXPECTED_ADMISSION_DIGEST,
    EXPECTED_ISSUANCE_DIGEST,
    execute_exact_once,
    zero_call_preflight,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_2_s3_t02_production_runtime_integration import (
    _CurrentS3ProductionFake,
)


def _load(ref: str) -> dict[str, object]:
    value = json.loads((ROOT / ref).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_replacement_admission_is_fresh_deterministic_and_original_is_immutable() -> None:
    admission, issuance = render_replacement_issuance()
    second = render_replacement_issuance()
    assert (admission, issuance) == second
    assert admission == _load(ADMISSION_REF)
    assert issuance == _load(ISSUANCE_REF)
    assert issuance["issued_admission"]["execution_identity"] == EXECUTION_IDENTITY
    assert admission["input_digest"] == issuance["exact_binding"]["complete_input_digest"]
    assert canonical_digest(admission) == EXPECTED_ADMISSION_DIGEST
    assert canonical_digest(
        {
            key: value
            for key, value in issuance.items()
            if key != "issuance_digest"
        }
    ) == EXPECTED_ISSUANCE_DIGEST
    assert issuance["issued_admission"]["admission_digest"] == EXPECTED_ADMISSION_DIGEST
    original_admission, original_issuance = render_original_issuance()
    assert original_admission == _load(
        "configs/releases/fin_ia_0_1_2_s4_t04_nvda_current_evidence_"
        "fresh_exact_admission_r1.json"
    )
    assert original_issuance == _load(
        "configs/releases/fin_ia_0_1_2_s4_t04_nvda_current_evidence_"
        "fresh_exact_admission_issuance_v1_0.json"
    )


def test_replacement_preflight_and_full_fake_are_zero_retry_and_nine_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    preflight = zero_call_preflight()
    assert preflight["status"] == "pass_exact_input_admission_transport_wiring_zero_call"
    assert preflight["execution_identity"] == EXECUTION_IDENTITY
    assert preflight["model_provider_network_calls"] == [0, 0, 0]
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    fake = _CurrentS3ProductionFake(safe_lead=True)
    result = execute_exact_once(tmp_path / "runtime", completion=fake)
    assert result["status"] == "success"
    assert len(result["capture_objects"]) == 9
    assert len(result["terminal"]["local_fact_receipts"]) == 3
    assert len(result["artifacts"]) == 9
    assert result["business_promotable"] is True
