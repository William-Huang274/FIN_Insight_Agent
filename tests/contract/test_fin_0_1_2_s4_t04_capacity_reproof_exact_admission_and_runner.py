from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests/contract")]

from apps.workbench.backend.application.bounded_agent_executor import (
    S4_T04_CURRENT_EVIDENCE_VERIFIER_MODEL_VIEW_CONTRACT_REF,
)
from scripts.releases.issue_fin_ia_0_1_2_s4_t04_nvda_current_evidence_capacity_reproof_exact_admission import (
    ADMISSION_REF,
    EXECUTION_IDENTITY,
    ISSUANCE_REF,
    render_capacity_reproof_issuance,
)
from scripts.releases.run_fin_ia_0_1_2_s4_t04_nvda_current_evidence_capacity_reproof_exact_live import (
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


def test_R3_admission_is_fresh_deterministic_and_capacity_bound() -> None:
    admission, issuance = render_capacity_reproof_issuance()
    assert (admission, issuance) == render_capacity_reproof_issuance()
    assert admission == _load(ADMISSION_REF)
    assert issuance == _load(ISSUANCE_REF)
    assert canonical_digest(admission) == EXPECTED_ADMISSION_DIGEST
    assert issuance["issuance_digest"] == EXPECTED_ISSUANCE_DIGEST
    assert issuance["issued_admission"]["execution_identity"] == EXECUTION_IDENTITY
    assert issuance["exact_binding"]["verifier_input_contract_ref"] == (
        S4_T04_CURRENT_EVIDENCE_VERIFIER_MODEL_VIEW_CONTRACT_REF
    )
    envelope = issuance["execution_envelope"]
    assert envelope["hard_budget"]["maximum_input_tokens"] == 108000
    assert envelope["input_capacity_contract"][
        "cost_derived_absolute_maximum_input_tokens"
    ] == 117931


def test_R3_preflight_and_full_fake_materialize_nine_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    preflight = zero_call_preflight()
    assert preflight["status"] == (
        "pass_exact_input_admission_transport_wiring_zero_call"
    )
    assert preflight["execution_identity"] == EXECUTION_IDENTITY
    assert preflight["maximum_input_tokens"] == 108000
    assert preflight["model_provider_network_calls"] == [0, 0, 0]

    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    fake = _CurrentS3ProductionFake(safe_lead=True)
    result = execute_exact_once(tmp_path / "runtime", completion=fake)
    assert result["status"] == "success"
    assert [
        len(result["capture_objects"]),
        len(result["terminal"]["local_fact_receipts"]),
        len(result["artifacts"]),
    ] == [9, 3, 9]
    assert result["business_promotable"] is True
    verifier = fake.calls[-1]["request"]
    assert verifier["analysis_input"]["model_view_contract_ref"] == (
        S4_T04_CURRENT_EVIDENCE_VERIFIER_MODEL_VIEW_CONTRACT_REF
    )
    assert "specialist_claim_cards" not in verifier["analysis_input"]
