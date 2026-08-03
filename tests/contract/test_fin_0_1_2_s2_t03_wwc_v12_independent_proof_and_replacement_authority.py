from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from scripts.releases.prepare_fin_ia_0_1_2_s2_t03_wwc_v12_independent_proof_and_replacement_authority import (
    DECISION,
    NEXT_ACTION,
    Fin012S2T03WWCV12IndependentProofError,
    _verify_implementation_bindings,
    build_decision,
)


PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_16.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_persisted_decision_matches_two_fresh_process_proof() -> None:
    assert _load(DECISION) == build_decision()


def test_independent_proof_is_zero_call_equal_and_target_read_only() -> None:
    decision = _load(DECISION)
    proof = decision["independent_proof"]

    assert proof["fresh_processes"] == 2
    assert proof["distinct_disposable_roots"] == 2
    assert proof["normalized_outputs_byte_equal"] is True
    assert proof["credential_environment_scrubbed"] is True
    assert proof["network_guard_installed"] is True
    assert proof["target_binding_state_unchanged"] is True
    assert proof["matrix"]["three_case_full_fake"] == {
        "DELL": [6, 6],
        "MU": [6, 6],
        "NVDA": [6, 6],
    }
    assert proof["matrix"]["model_provider_network_calls"] == [0, 0, 0]


def test_replacement_authority_is_exact_two_call_and_conditional() -> None:
    decision = _load(DECISION)
    authority = decision["replacement_pair_conditional_authority"]
    calls = authority["call_plan"]

    assert authority["exact_call_count"] == len(calls) == 2
    assert authority["Fact_or_Claim_rerun"] is False
    assert {row["candidate_id"] for row in calls} == {
        "flash_stable",
        "pro_preview",
    }
    assert {row["family_id"] for row in calls} == {"what_would_change_atoms"}
    assert len({row["model_visible_request_digest"] for row in calls}) == 1
    assert len({row["request_equivalence_digest"] for row in calls}) == 1
    assert authority["hard_budget"]["semantic_model_calls"] == 2
    assert authority["hard_budget"]["maximum_transport_attempts_per_call"] == 1
    assert authority["hard_budget"]["retry_budget"] == 0
    assert authority["automatic_execution_now"] is False
    assert decision["authority"]["current_replacement_pair_execution_authorized"] is False
    assert decision["next_action"] == NEXT_ACTION
    assert decision["next_action_authorized"] is False


def test_proof_keeps_issues_open_until_fair_natural_measurement() -> None:
    decision = _load(DECISION)

    assert decision["issue_disposition"]["issues_closed_now"] == 0
    assert decision["stage_acceptance"]["S2_T03_WWC_v12_independent_proof"] == "pass"
    assert decision["stage_acceptance"]["S2_T03_fair_WWC_measurement"] == "pending"
    assert decision["stage_acceptance"]["S2_T04"] == "not_entered"
    assert decision["stage_acceptance"]["S2"] == "not_passed"
    assert decision["observed_counts"]["replacement_pair_calls"] == 0


def test_implementation_binding_drift_fails_closed() -> None:
    decision = _load(DECISION)
    implementation = _load(ROOT / decision["source_bindings"]["implementation_ref"])
    implementation["implementation_bindings"][0]["sha256"] = "0" * 64

    with pytest.raises(
        Fin012S2T03WWCV12IndependentProofError,
        match="implementation_binding_digest_drift",
    ):
        _verify_implementation_bindings(implementation)


def test_historical_projection_remains_bound_after_backlog_advances() -> None:
    decision = _load(DECISION)
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)["next_action"]
    decision_ref = DECISION.relative_to(ROOT).as_posix()
    decision_sha = hashlib.sha256(DECISION.read_bytes()).hexdigest()
    projection_ref = PROJECTION.relative_to(ROOT).as_posix()
    projection_sha = hashlib.sha256(PROJECTION.read_bytes()).hexdigest()

    assert projection["decision_binding"]["ref"] == decision_ref
    assert projection["decision_binding"]["sha256"] == decision_sha
    assert projection["current_truth"]["current_next_action"] == NEXT_ACTION
    assert projection["execution_authority"][
        "conditional_replacement_pair_authority_issued"
    ] is True
    assert projection["execution_authority"][
        "replacement_pair_execution_authorized_now"
    ] is False
    assert backlog["item_id"] == (
        "FIN-0.1.2-S2-T03-MU-WWC-V1.2-FLASH-STABLE-VS-PRO-PREVIEW-"
        "REPLACEMENT-PAIR-EXACT-EXECUTION"
    )
    assert backlog["current_projection_ref"] != projection_ref
    assert backlog["current_projection_sha256"] != projection_sha
    assert backlog["S2_T03_independent_zero_call_proof_ref"] == decision_ref
    assert backlog["S2_T03_independent_zero_call_proof_sha256"] == decision_sha
    assert backlog["S2_T03_future_WWC_replacement_pair_authorized"] is True
    assert backlog["S2_T03_replacement_pair_execution_authorized_now"] is False
