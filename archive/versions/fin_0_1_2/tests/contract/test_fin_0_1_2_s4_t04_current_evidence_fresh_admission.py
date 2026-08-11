from __future__ import annotations

from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.releases.issue_fin_ia_0_1_2_s4_t04_nvda_current_evidence_fresh_exact_admission import (
    EXECUTION_IDENTITY,
    render_issuance,
)
from sec_agent.canonical_runtime.models import canonical_digest


def test_fresh_T04_admission_is_deterministic_exact_and_zero_call() -> None:
    admission, issuance = render_issuance()
    second_admission, second_issuance = render_issuance()
    assert admission == second_admission
    assert issuance == second_issuance
    assert issuance["issued_admission"]["execution_identity"] == EXECUTION_IDENTITY
    assert admission["input_digest"] == issuance["exact_binding"]["complete_input_digest"]
    assert admission["model"] == "deepseek-v4-pro"
    assert [
        admission["max_provider_calls"],
        admission["max_semantic_model_calls"],
        admission["max_network_calls"],
    ] == [9, 9, 9]
    assert admission["retry_budget"] == 0
    assert issuance["execution_envelope"]["hard_budget"]["source_network_calls"] == 0
    assert set(issuance["observed_counts"].values()) == {0}
    assert issuance["issuance_digest"] == canonical_digest(
        {key: value for key, value in issuance.items() if key != "issuance_digest"}
    )
    tracked_admission = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_2_s4_t04_nvda_current_evidence_"
            "fresh_exact_admission_r1.json"
        ).read_text(encoding="utf-8")
    )
    tracked_issuance = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_2_s4_t04_nvda_current_evidence_"
            "fresh_exact_admission_issuance_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    assert tracked_admission == admission
    assert tracked_issuance == issuance
