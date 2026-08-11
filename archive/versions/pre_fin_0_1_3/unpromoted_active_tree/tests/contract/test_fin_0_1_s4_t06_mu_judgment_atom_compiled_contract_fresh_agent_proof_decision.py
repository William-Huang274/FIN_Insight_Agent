from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.releases.prepare_fin_ia_0_1_s4_t06_mu_judgment_atom_compiled_contract_fresh_proof import (
    DECISION,
    NEXT_ACTION,
    PROSPECTIVE_ADMISSION,
    build_decision,
)
from sec_agent.canonical_runtime.models import canonical_digest


def test_fresh_proof_is_independent_zero_call_and_freezes_new_identity() -> None:
    result = build_decision()
    assert result["status"] == (
        "pass_zero_call_double_disposable_runtime_fresh_proof_"
        "changed_family_canaries_not_authorized"
    )
    assert result["proof_generator"]["independent_invocations"] == 2
    assert result["proof_generator"]["independent_outputs_equal"] is True
    assert result["double_prepare"]["equal"] is True
    assert result["double_prepare"]["clone_execution_counts_before"] == (
        result["double_prepare"]["clone_execution_counts_after"]
    )
    assert result["target_read_only_audit"]["target_state_unchanged"] is True
    assert result["hard_boundaries"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "admissions_issued": 0,
        "admissions_consumed": 0,
        "target_canonical_writes": 0,
        "target_object_writes": 0,
        "exact_live_runs": 0,
        "paired_assessments": 0,
        "owner_acceptances": 0,
        "T07_entries": 0,
    }
    assert result["prospective_R7_admission"]["issued"] is False
    assert result["prospective_R7_admission"]["compiled_contract_bound"] is True
    payload = result["prospective_R7_admission"]["payload"]
    assert canonical_digest(payload) == (
        result["prospective_R7_admission"]["digest"]
    )
    assert not PROSPECTIVE_ADMISSION.exists()
    assert result["next_action"] == NEXT_ACTION
    assert result["next_action_authorized"] is False


def test_persisted_decision_matches_current_generator() -> None:
    expected = build_decision()
    actual = json.loads(DECISION.read_text(encoding="utf-8"))
    assert actual == expected
