from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s2_t03_wwc_contract_parity_row_local_"
    "claim_binding_and_replacement_pair_disposition_decision_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_14.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_disposition_corrects_capability_interpretation_without_history_rewrite() -> None:
    decision = _load(DECISION)
    interpretation = decision["corrected_measurement_interpretation"]

    assert decision["authority"]["runtime_implementation_authorized_in_this_turn"] is False
    assert decision["authority"]["model_provider_network_calls_authorized"] == 0
    assert interpretation["immutable_terminal_statuses_rewritten"] is False
    assert interpretation["historical_terminal_pass_failed_counts"] == [5, 1]
    assert interpretation["fair_capability_evidence_call_count"] == 4
    assert interpretation["WWC_fair_capability_evidence_call_count"] == 0
    assert interpretation["Flash_noncompliance_established"] is False
    assert interpretation["Pro_superiority_established"] is False


def test_single_repair_owns_date_parity_and_row_local_claim_binding() -> None:
    decision = _load(DECISION)
    repair = decision["selected_consolidated_repair"]
    reproduction = decision["sanitized_zero_call_reproduction"]

    assert repair["maximum_zero_call_implementation_bundles"] == 1
    assert repair["automatic_second_implementation_bundle"] == 0
    assert repair["date_binding_rule"]["bound_date"].startswith(
        "review_date_alias must be"
    )
    assert repair["date_binding_rule"]["all_other_review_cadences"] == (
        "review_date_alias must be exactly NONE"
    )
    assert repair["claim_binding_rule"]["source"] == (
        "each selected normalized atom"
    )
    assert reproduction["pro_WWC"]["raw_claim_aliases"] == [
        "Q001",
        "Q002",
        "Q001",
    ]
    assert reproduction["pro_WWC"]["expected_unique_claim_id_count"] == 2
    assert reproduction["pro_WWC"]["observed_unique_claim_id_count"] == 1
    assert reproduction["pro_WWC"]["terminal_status"] == (
        "pass_false_green_for_semantic_binding"
    )


def test_replacement_pair_remains_separately_authorized_and_bounded() -> None:
    decision = _load(DECISION)
    replacement = decision["affected_family_replacement_pair_disposition"]

    assert replacement["eligible_after_consolidated_implementation_and_independent_zero_call_proof"] is True
    assert replacement["authorized_now"] is False
    assert replacement["separate_authority_required"] is True
    assert replacement["maximum_calls"] == 2
    assert replacement["family"] == "what_would_change_atoms"
    assert replacement["Fact_or_Claim_rerun"] is False
    assert replacement["retry_fallback_provider_hopping_prompt_only_retry"] == [
        0,
        0,
        0,
        0,
    ]


def test_projection_and_backlog_advance_only_to_zero_call_implementation() -> None:
    decision = _load(DECISION)
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)
    decision_ref = DECISION.relative_to(ROOT).as_posix()
    decision_sha = hashlib.sha256(DECISION.read_bytes()).hexdigest()

    assert projection["decision_binding"] == {
        "ref": decision_ref,
        "sha256": decision_sha,
        "binding_role": (
            "S2_T03_WWC_two_project_defects_one_repair_and_replacement_pair_disposition"
        ),
    }
    truth = projection["current_truth"]
    assert truth["fair_capability_evidence_calls"] == 4
    assert truth["WWC_fair_capability_evidence_calls"] == 0
    assert truth["current_next_action"] == decision["next_action"]
    authority = projection["execution_authority"]
    assert authority["consolidated_zero_call_implementation_authorized"] is False
    assert authority["replacement_pair_authorized"] is False
    assert authority["model_provider_network_calls_authorized"] == 0

    current = backlog["next_action"]
    assert current["item_id"] != decision["next_action"]
    assert current["S2_T03_disposition_ref"] == decision_ref
    assert current["S2_T03_disposition_sha256"] == decision_sha
    assert current["S2_T03_fair_Fact_Claim_WWC_outcome_counts"] == [4, 0]
    assert current["S2_T03_consolidated_zero_call_implementation_authorized"] is True
    assert current["S2_T03_future_WWC_replacement_pair_authorized"] is True
    assert current["S2_T03_replacement_pair_execution_authorized_now"] is False
