from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s2_selected_evidence_numeric_cocompilation import (  # noqa: E402
    canonical_digest,
)


DECISION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "zero_call_authority_decision_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_"
    "cocompilation_clean_independent_proof_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_is_zero_call_and_does_not_issue_live_authority() -> None:
    decision = _load(DECISION_PATH)
    assert decision["status"] == (
        "decision_complete_authorize_zero_call_canary_implementation_and_clean_proof_only"
    )
    assert decision["scope"] == {
        "kind": "zero_call_natural_node_canary_authority_decision",
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "retries": 0,
        "canary_live_authorized_by_this_record": False,
        "canary_runner_implemented_by_this_record": False,
        "dell_full_chain_authorized": False,
        "business_artifact_promotion": False,
    }


def test_decision_is_bound_to_the_clean_proof() -> None:
    decision = _load(DECISION_PATH)
    proof = _load(PROOF_PATH)
    assert decision["authority_basis"]["clean_proof_digest"] == proof["result_digest"]
    assert proof["stage_acceptance"]["clean_independent_proof"] is True
    assert proof["stage_acceptance"]["natural_model_canary"] is False


def test_canary_is_one_meaningful_dell_atom_not_a_report_or_model_ab() -> None:
    decision = _load(DECISION_PATH)
    selected = decision["selected_canary"]
    assert selected["case_key"] == "DELL"
    assert selected["provider_profile_ref"].endswith("deepseek_v4_pro.fixed_pack_research:v1")
    assert [row["evidence_alias"] for row in selected["evidence_selection"]] == [
        "E022",
        "E018",
        "E023",
    ]
    chosen = next(
        row
        for row in decision["option_assessment"]
        if row["decision"] == "selected"
    )
    assert chosen["option_id"] == "C_single_DELL_demand_authenticity_numeric_view_atom"
    assert decision["output_atom_contract"]["complete_report_or_recommendation"] == "forbidden"


def test_canary_targets_prior_unbound_surfaces_without_core_whitelisting() -> None:
    surface = _load(DECISION_PATH)["selected_canary"]["numeric_test_surface"]
    assert surface["required_presentations"] == [
        "$16.1 billion",
        "customer count surpassed 5,000",
    ]
    assert surface["required_one_of_presentations"] == [
        "$24.4 billion",
        "$51.3 billion",
    ]
    assert surface["other_material_numeric_surfaces"].startswith("forbidden")
    assert surface["free_arithmetic"] is False
    assert surface["market_price_or_valuation"] is False


def test_later_live_budget_is_exact_once_one_call_and_no_auto_rerun() -> None:
    decision = _load(DECISION_PATH)
    budget = decision["execution_budget_if_later_authorized"]
    assert budget["provider_calls_maximum"] == budget["model_calls_maximum"] == 1
    assert budget["source_calls"] == budget["network_tool_calls"] == 0
    assert budget["retries"] == budget["fallbacks"] == 0
    assert budget["capture_before_parse_or_validation"] is True
    assert budget["exact_once_admission_required"] is True
    assert decision["acceptance"]["pass_disposition"].endswith("Do not auto-run it.")


def test_decision_digest_when_added_is_canonical() -> None:
    decision = _load(DECISION_PATH)
    if "decision_digest" in decision:
        body = {
            key: value for key, value in decision.items() if key != "decision_digest"
        }
        assert decision["decision_digest"] == canonical_digest(body)
