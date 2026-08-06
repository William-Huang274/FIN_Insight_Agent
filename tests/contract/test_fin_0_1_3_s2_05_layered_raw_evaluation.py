from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sec_agent.s2_same_evidence_experiment_runtime import (
    SECTION_IDS,
    load_frozen_blind_inputs,
    load_runtime_policy,
)
from sec_agent.s2_same_evidence_layered_evaluation import (
    allowed_numeric_surfaces,
    compile_output_contract,
    evaluate_raw_chain,
)
from sec_agent.s2_same_evidence_supervision import compile_supervision_boundary


ROOT = Path(__file__).resolve().parents[2]


def _case_and_policy() -> tuple[dict[str, Any], dict[str, Any]]:
    policy = load_runtime_policy(ROOT)
    case = load_frozen_blind_inputs(ROOT, policy)["cases"][0]
    return case, policy


def _chain(case: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    evidence_ids = [row["evidence_id"] for row in case["evidence_items"]]
    gap_ids = [row["gap_id"] for row in case["explicit_gaps"]]
    units = []
    specialists = []
    for index, family in enumerate(policy["mandatory_research_families"]):
        unit_id = f"{case['case_key']}_RU0{index + 1}"
        assigned_evidence = evidence_ids[index::6]
        assigned_gaps = gap_ids[index::6]
        units.append(
            {
                "unit_id": unit_id, "family": family,
                "question": "What does the assigned evidence support?",
                "why_material": "The answer changes the bounded judgment.",
                "evidence_ids": assigned_evidence, "gap_ids": assigned_gaps,
                "stop_condition": "If a hypothetical threshold is crossed, reassess.",
            }
        )
        specialists.append(
            {
                "case_key": case["case_key"], "as_of": case["as_of"], "unit_id": unit_id,
                "epistemic_state": "mixed", "judgment": "The evidence is mixed.",
                "mechanism": "The operating mechanism remains bounded.",
                "financial_or_valuation_link": "No unsupported valuation bridge is used.",
                "evidence_ids": assigned_evidence, "counterevidence_ids": [],
                "gap_ids": assigned_gaps,
                "what_would_change": "If a hypothetical 20% threshold is crossed, reassess.",
            }
        )
    sections = [
        {
            "section_id": section_id, "heading": section_id,
            "narrative": "The evidence supports a bounded conclusion.",
            "evidence_ids": evidence_ids if index == 0 else [evidence_ids[0]],
            "unit_ids": [row["unit_id"] for row in units],
            "gap_ids": gap_ids if index == 0 else [gap_ids[0]],
        }
        for index, section_id in enumerate(SECTION_IDS)
    ]
    return {
        "lead": {"case_key": case["case_key"], "as_of": case["as_of"], "research_units": units},
        "specialists": specialists,
        "synthesis": {
            "case_key": case["case_key"], "as_of": case["as_of"], "thesis": "The thesis is bounded.",
            "confidence": "moderate", "unit_ids": [row["unit_id"] for row in units],
            "dependencies": [], "conflicts": [], "material_gap_ids": gap_ids,
            "counter_thesis": "The counter-thesis remains plausible.",
            "what_would_change": "If a hypothetical threshold is crossed, reassess.",
        },
        "writer": {
            "case_key": case["case_key"], "as_of": case["as_of"], "title": case["case_key"] + " raw report",
            "sections": sections, "overall_boundary": "This is not investment advice.",
        },
        "verifier": {
            "case_key": case["case_key"], "as_of": case["as_of"],
            "decision": "accept_raw_candidate", "material_failure": False,
            "findings": [], "checked_unit_ids": [row["unit_id"] for row in units],
            "checked_section_ids": list(SECTION_IDS),
        },
    }


def test_compiled_contract_makes_previously_drifting_types_explicit() -> None:
    _, policy = _case_and_policy()
    synthesis = compile_output_contract("cross_cell_synthesis", policy, SECTION_IDS)
    writer = compile_output_contract("writer", policy, SECTION_IDS)
    verifier = compile_output_contract("verifier", policy, SECTION_IDS)
    assert synthesis["properties"]["dependencies"]["items"]["type"] == "object"
    assert synthesis["properties"]["conflicts"]["items"]["properties"]["unit_ids"]["minItems"] == 2
    assert writer["properties"]["overall_boundary"]["type"] == "string"
    assert verifier["properties"]["material_failure"]["type"] == "boolean"


def test_numeric_compiler_accepts_source_bound_suffix_unit_and_rounding() -> None:
    case, _ = _case_and_policy()
    allowed = allowed_numeric_surfaces(case)
    assert {"51.3b", "24.4b", "36.7%", "55.5%", "10.5%", "9.3%"} <= allowed


def test_layered_evaluation_keeps_hypothesis_as_quality_finding_not_material() -> None:
    case, policy = _case_and_policy()
    result = evaluate_raw_chain(_chain(case, policy), case_input=case, policy=policy, section_ids=SECTION_IDS)
    assert result["raw_chain_complete"] is True
    assert result["hidden_scoring_eligible"] is True
    assert result["material_failure"] is False
    assert any(row["code"] == "hypothetical_planning_threshold" for row in result["findings"])
    assert all(row["severity"] != "L1" for row in result["findings"])


def test_layered_evaluation_blocks_business_promotion_for_financial_semantic_bridge() -> None:
    case, policy = _case_and_policy()
    chain = _chain(case, policy)
    chain["writer"]["sections"][0]["narrative"] = (
        "Operating cash flow margin is used as net income margin to infer EPS and P/E. "
        "A backlog cancellation scenario implies stock downside."
    )
    result = evaluate_raw_chain(chain, case_input=case, policy=policy, section_ids=SECTION_IDS)
    codes = {row["code"] for row in result["findings"]}
    assert "cash_flow_margin_used_in_earnings_or_valuation_bridge" in codes
    assert "unsupported_backlog_to_eps_or_price_bridge" in codes
    assert "verifier_missed_material_financial_semantics" in codes
    assert "verifier_missed_material_failure" in codes
    assert result["hidden_scoring_eligible"] is True
    assert result["business_promotable"] is False
    assert result["status"] == "complete_with_material_findings"


def test_layered_evaluation_reports_schema_drift_without_stopping_chain() -> None:
    case, policy = _case_and_policy()
    chain = _chain(case, policy)
    chain["synthesis"]["dependencies"] = ["RU01 depends on RU02"]
    chain["writer"]["overall_boundary"] = {"boundary": "wrong type"}
    chain["verifier"]["material_failure"] = "false"
    result = evaluate_raw_chain(chain, case_input=case, policy=policy, section_ids=SECTION_IDS)
    codes = {row["code"] for row in result["findings"]}
    assert "synthesis_dependencies_not_typed_rows" in codes
    assert "writer_overall_boundary_not_string" in codes
    assert "verifier_material_failure_not_boolean" in codes
    assert result["raw_chain_complete"] is True
    assert result["hidden_scoring_eligible"] is True


def test_layered_evaluation_full_fake_is_case_local_for_dell_mu_nvda() -> None:
    policy = load_runtime_policy(ROOT)
    cases = load_frozen_blind_inputs(ROOT, policy)["cases"]
    for case in cases:
        result = evaluate_raw_chain(
            _chain(case, policy), case_input=case, policy=policy, section_ids=SECTION_IDS
        )
        assert result["case_key"] == case["case_key"]
        assert result["raw_chain_complete"] is True
        assert result["hidden_scoring_eligible"] is True
        assert result["business_promotion_gate_pass"] is True
        assert result["business_promotable"] is False


def test_document_form_and_cross_section_terms_do_not_create_numeric_or_semantic_false_positive() -> None:
    case, policy = _case_and_policy()
    chain = _chain(case, policy)
    chain["specialists"][0]["mechanism"] = "The 10-K describes working-capital risk."
    chain["writer"]["sections"][2]["narrative"] = "Operating cash flow may be pressured by working capital."
    chain["writer"]["sections"][3]["narrative"] = "The trailing P/E is only a static market boundary."
    result = evaluate_raw_chain(chain, case_input=case, policy=policy, section_ids=SECTION_IDS)
    codes = {row["code"] for row in result["findings"]}
    assert "unbound_material_numeric_surface" not in codes
    assert "cash_flow_margin_used_in_earnings_or_valuation_bridge" not in codes
    assert result["material_failure"] is False


def test_conditional_threshold_outside_dedicated_field_remains_L3() -> None:
    case, policy = _case_and_policy()
    chain = _chain(case, policy)
    chain["writer"]["sections"][4]["narrative"] = (
        "A sequential decline or a greater than 10% backlog drop would trigger reassessment."
    )
    result = evaluate_raw_chain(chain, case_input=case, policy=policy, section_ids=SECTION_IDS)
    matching = [row for row in result["findings"] if "10%" in row.get("tokens", [])]
    assert matching
    assert all(row["severity"] == "L3" for row in matching)
    assert result["material_failure"] is False


def test_directional_margin_cannot_be_sharpened_into_invented_percent_range() -> None:
    case, policy = _case_and_policy()
    chain = _chain(case, policy)
    chain["specialists"][3]["judgment"] = (
        "Management's mid-single-digit statement implies a 4-6% AI server operating margin."
    )
    result = evaluate_raw_chain(chain, case_input=case, policy=policy, section_ids=SECTION_IDS)
    codes = {row["code"] for row in result["findings"]}
    assert "directional_margin_sharpened_to_unsupported_range" in codes
    assert "verifier_missed_material_failure" in codes
    assert result["material_failure"] is True


def test_unrelated_conditional_percent_range_is_not_misattributed_to_directional_margin() -> None:
    case, policy = _case_and_policy()
    chain = _chain(case, policy)
    chain["writer"]["sections"][4]["narrative"] = (
        "If a hypothetical backlog cancellation range reaches 4-6%, reassess demand quality."
    )
    result = evaluate_raw_chain(chain, case_input=case, policy=policy, section_ids=SECTION_IDS)
    matching = [row for row in result["findings"] if set(row.get("tokens", [])) == {"4", "6%"}]
    assert matching
    assert all(row["code"] == "hypothetical_planning_threshold" for row in matching)
    assert all(row["severity"] == "L3" for row in matching)
    assert result["material_failure"] is False


def test_s2_06_boundary_separates_raw_correction_and_next_case_authority() -> None:
    case, policy = _case_and_policy()
    chain = _chain(case, policy)
    chain["specialists"][3]["judgment"] = "Mid-single-digit profitability was sharpened to a 4-6% margin."
    result = evaluate_raw_chain(chain, case_input=case, policy=policy, section_ids=SECTION_IDS)
    boundary = compile_supervision_boundary(
        result,
        raw_run_id="immutable-DELL-run",
        raw_terminal_digest="a" * 64,
    )
    assert boundary["raw_binding"]["raw_model_only_immutable"] is True
    assert boundary["capability_attribution"]["autonomous_model_result"] == "raw_complete_quality_fail"
    assert boundary["campaign_boundary"]["automatic_next_case"] is False
    assert boundary["campaign_boundary"]["next_case_may_be_considered_by_separate_authority"] is True
    assert boundary["campaign_boundary"]["corrected_DELL_required_before_MU_raw_measurement"] is False
    assert all(row["hidden_gold_visible"] is False for row in boundary["corrections"])
    precision = next(
        row for row in boundary["corrections"]
        if row["source_finding"]["code"] == "directional_margin_sharpened_to_unsupported_range"
    )
    assert precision["deterministic_correction_allowed"] is True
    assert precision["new_model_call_required"] is False
