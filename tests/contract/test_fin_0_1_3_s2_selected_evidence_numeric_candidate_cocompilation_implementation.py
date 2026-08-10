from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_six_case_local_evidence_pack import (  # noqa: E402
    compile_six_case_local_evidence_packs,
    load_six_case_local_evidence_pack_policy,
)
from sec_agent.s2_dell_changed_input_model_comparison import (  # noqa: E402
    compile_changed_input_case,
    load_changed_input_comparison_contract,
)
from sec_agent.s2_selected_evidence_numeric_cocompilation import (  # noqa: E402
    AUTHORIZED_STATUSES,
    SelectedEvidenceNumericCocompilationError,
    canonical_digest,
    compile_numeric_cocompilation_successor_input,
    compile_selected_evidence_numeric_cocompilation,
    evaluate_delivery_numeric_authority,
    load_numeric_cocompilation_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_"
    "cocompilation_policy_v1_0.json"
)
SIX_CASE_POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_six_case_local_evidence_pack_policy_v1_0.json"
)
DELL_CONTRACT_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_contract_v1_0.json"
)


@pytest.fixture(scope="module")
def compiled():
    policy = load_numeric_cocompilation_policy(POLICY_PATH)
    dell_contract = load_changed_input_comparison_contract(
        DELL_CONTRACT_PATH,
        repo_root=ROOT,
    )
    dell_material = compile_changed_input_case(
        contract=dell_contract,
        repo_root=ROOT,
    )
    six_case_policy = load_six_case_local_evidence_pack_policy(
        SIX_CASE_POLICY_PATH,
        repo_root=ROOT,
    )
    six_packs, _six_result = compile_six_case_local_evidence_packs(
        policy=six_case_policy,
        repo_root=ROOT,
    )
    packs = {row["case_key"]: row for row in six_packs}
    packs["DELL"] = dell_material["pack"]
    results = {
        case_key: compile_selected_evidence_numeric_cocompilation(
            pack=pack,
            policy=policy,
        )
        for case_key, pack in packs.items()
    }
    return policy, dell_material, packs, results


def _facts(result: dict) -> list[dict]:
    return list(result["presentation_program"]["stable_numeric_facts"])


def _metric_facts(result: dict, metric: str) -> list[dict]:
    return [row for row in _facts(result) if row["semantic_metric_key"] == metric]


def _candidate(result: dict, surface: str) -> list[dict]:
    return [
        row
        for row in result["candidate_inventory"]["candidates"]
        if row["source_surface"] == surface
    ]


def test_policy_is_provider_neutral_zero_call_and_capacity_bounded(compiled) -> None:
    policy, _dell_material, _packs, results = compiled
    assert policy["provider_neutral"] is True
    assert policy["case_specific_value_whitelists"] is False
    assert policy["full_source_regex_all_promotion"] is False
    assert policy["hard_boundaries"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "automatic_rerun": False,
        "source_presence_bypasses_authority": False,
        "semantic_verifier_can_override_local_guard": False,
        "market_pit_authorizes_valuation_or_recommendation": False,
    }
    for result in results.values():
        assert result["model_calls"] == result["provider_calls"] == 0
        assert result["network_calls"] == result["source_calls"] == 0
        capacity = result["node_views"]["capacity_receipt"]
        assert capacity["all_views_within_compiled_limits"] is True
        assert all(
            capacity["view_char_counts"][key]
            <= capacity["hard_char_limits"][key]
            for key in capacity["view_char_counts"]
        )


def test_dell_selected_evidence_compiles_business_correct_numeric_authority(compiled) -> None:
    _policy, _dell_material, _packs, results = compiled
    result = results["DELL"]
    program = result["presentation_program"]

    assert program["conflicts"] == []
    assert {
        "ai_orders",
        "ai_server_revenue",
        "ai_backlog",
        "customer_count",
        "ai_gpu_product_revenue_growth",
        "operating_cash_flow",
        "accounts_receivable",
        "inventory",
        "accounts_payable",
        "supply_tightness_horizon",
        "capacity_release_timing",
        "total_revenue_guidance_midpoint",
    } <= {row["semantic_metric_key"] for row in _facts(result)}

    total_revenue = _metric_facts(result, "total_revenue")
    assert [(row["period_or_as_of"], row["authoritative_value"]["base_value"]) for row in total_revenue] == [
        ("FY2027_Q1", "43842000000")
    ]
    cash_flow_surface = _candidate(result, "$4.1 billion")
    assert cash_flow_surface
    assert all(
        row["adjudication_status"] == "context_only_do_not_output"
        and row["semantic_metric_key"] == "unresolved_numeric_context"
        for row in cash_flow_surface
    )

    ai_server = _metric_facts(result, "ai_server_revenue")[0]
    server_surfaces = {
        receipt["source_surface"]
        for receipt in ai_server["presentation_receipts"]
    }
    assert {"16,132", "$16.1 billion"} <= server_surfaces
    assert ai_server["authoritative_value"]["base_value"] == "16132000000"

    formula_outputs = {
        row["semantic_metric_key"]: row["rendered"]
        for row in program["formula_traces"]
    }
    assert formula_outputs == {
        "adjusted_free_cash_flow_share_of_operating_cash_flow": "77.55%",
        "free_cash_flow_share_of_operating_cash_flow": "76.4%",
        "isg_operating_margin": "10.53%",
        "ai_server_revenue_share_of_isg": "55.61%",
    }


def test_relative_periods_and_metric_kinds_do_not_collapse(compiled) -> None:
    _policy, _dell_material, _packs, results = compiled
    mu = results["MU"]
    gross_margin = {
        (row["period_or_as_of"], row["authoritative_value"]["value"])
        for row in _metric_facts(mu, "consolidated_gross_margin")
    }
    assert {
        ("FY2026_Q3", "85"),
        ("FY2026_Q2", "74"),
        ("FY2025_Q3", "38"),
        ("9M2026", "77"),
        ("9M2025", "38"),
    } <= gross_margin
    reported_revenue = {
        (row["period_or_as_of"], row["authoritative_value"]["base_value"])
        for row in _metric_facts(mu, "reported_revenue")
    }
    assert reported_revenue == {
        ("FY2026_Q3", "41460000000"),
        ("FY2026_Q2", "23860000000"),
        ("FY2025_Q3", "9300000000"),
    }
    assert _metric_facts(mu, "hbm_volume_production_timing")
    assert _metric_facts(mu, "dram_average_selling_price_change")
    assert _metric_facts(mu, "nand_average_selling_price_change")


def test_six_case_currency_period_and_held_out_paths_remain_generic(compiled) -> None:
    _policy, _dell_material, _packs, results = compiled
    expected_metrics = {
        "NVDA": {"total_revenue", "data_center_revenue", "gross_margin"},
        "ORCL": {"total_revenues", "capital_expenditures", "property_plant_and_equipment_net"},
        "ASML": {"total_net_sales", "gross_margin", "new_lithography_systems_sold_units"},
        "ANET": {"total_revenue", "gross_margin", "cash_provided_by_operating_activities"},
    }
    for case_key, required in expected_metrics.items():
        result = results[case_key]
        assert result["presentation_program"]["conflicts"] == []
        assert required <= {row["semantic_metric_key"] for row in _facts(result)}

    asml = results["ASML"]
    assert {row["canonical_unit"] for row in _facts(asml)} >= {"EUR", "percent", "count"}
    assert {row["period_or_as_of"] for row in _facts(asml)} >= {"Q1 2026", "Q2 2026"}

    anet_margin_periods = {
        row["period_or_as_of"]
        for row in _metric_facts(results["ANET"], "gross_margin")
    }
    assert {
        "Three Months Ended June 30, 2026",
        "Six Months Ended June 30, 2026",
    } <= anet_margin_periods


def test_order_changes_are_digest_stable(compiled) -> None:
    policy, _dell_material, packs, results = compiled
    changed = deepcopy(packs["DELL"])
    changed["evidence_items"].reverse()
    changed["source_materials"].reverse()
    replay = compile_selected_evidence_numeric_cocompilation(
        pack=changed,
        policy=policy,
    )
    assert replay["result_digest"] == results["DELL"]["result_digest"]
    assert replay["co_compilation_transaction_digest"] == results["DELL"][
        "co_compilation_transaction_digest"
    ]


def test_cross_case_and_missing_structured_authority_fail_closed(compiled) -> None:
    policy, _dell_material, packs, _results = compiled
    cross_case = deepcopy(packs["DELL"])
    cross_case["evidence_items"][0]["case_key"] = "MU"
    with pytest.raises(SelectedEvidenceNumericCocompilationError) as exc:
        compile_selected_evidence_numeric_cocompilation(
            pack=cross_case,
            policy=policy,
        )
    assert exc.value.code == "numeric_cocompilation_selected_evidence_identity_invalid"

    missing_parent = deepcopy(packs["ORCL"])
    metric = next(
        row
        for row in missing_parent["evidence_items"]
        if row.get("structured_metric")
    )
    metric["structured_metric"].pop("table_path", None)
    with pytest.raises(SelectedEvidenceNumericCocompilationError) as exc:
        compile_selected_evidence_numeric_cocompilation(
            pack=missing_parent,
            policy=policy,
        )
    assert exc.value.code == "numeric_cocompilation_structured_metric_authority_invalid"


def test_dates_rules_and_product_tokens_never_become_authorized(compiled) -> None:
    policy, _dell_material, packs, _results = compiled
    source_pack = packs["DELL"]
    evidence = deepcopy(
        next(
            row
            for row in source_pack["evidence_items"]
            if row.get("source_material_ref") and not row.get("structured_metric")
        )
    )
    old_material_ref = evidence["source_material_ref"]
    material = deepcopy(
        next(
            row
            for row in source_pack["source_materials"]
            if row["material_ref"] == old_material_ref
        )
    )
    text = (
        "Product identifiers GeForce RTX 4090, 256GB DDR5 and advanced 3D stacking. "
        "Filed on 2026-06-30 under Form 10-K."
    )
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    material["source_text"] = text
    material["source_text_digest"] = digest
    evidence["source_content_digest"] = digest
    fixture_pack = {
        "case_key": "DELL",
        "evidence_items": [evidence],
        "source_materials": [material],
        "pack_payload_digest": canonical_digest({"fixture": text}),
    }
    result = compile_selected_evidence_numeric_cocompilation(
        pack=fixture_pack,
        policy=policy,
    )
    candidates = result["candidate_inventory"]["candidates"]
    assert not any(
        row["adjudication_status"] in AUTHORIZED_STATUSES for row in candidates
    )
    decisions = {row["decision_code"] for row in candidates}
    assert {
        "date_token_not_financial_fact",
        "filing_or_rule_identifier_not_financial_fact",
        "product_or_technical_identifier_not_financial_fact",
    } <= decisions
    assert any(
        row["source_surface"] == "RTX 4090"
        and row["adjudication_status"] == "forbidden_or_ambiguous"
        for row in candidates
    )


def test_local_guard_allows_bound_surface_and_rejects_context_or_unit_mutation(compiled) -> None:
    _policy, _dell_material, _packs, results = compiled
    result = results["DELL"]
    total_revenue = _metric_facts(result, "total_revenue")[0]
    rendered = total_revenue["presentation_receipts"][0]["rendered"]
    good = evaluate_delivery_numeric_authority(
        delivery_text=f"本季净收入为 {rendered}。",
        used_numeric_refs=[total_revenue["numeric_ref"]],
        used_formula_refs=[],
        inventory=result["candidate_inventory"],
        presentation_program=result["presentation_program"],
        semantic_verifier_pass=True,
    )
    assert good["status"] == "pass"

    for bad_surface in ("$4.1 billion", "$43,842 million"):
        bad = evaluate_delivery_numeric_authority(
            delivery_text=f"错误输出 {bad_surface}。",
            used_numeric_refs=[total_revenue["numeric_ref"]],
            used_formula_refs=[],
            inventory=result["candidate_inventory"],
            presentation_program=result["presentation_program"],
            semantic_verifier_pass=True,
        )
        assert bad["status"] == "hard_fail"
        assert bad["local_numeric_gate_pass"] is False
        assert bad["semantic_verifier_overrode_local_gate"] is False


def test_model_views_mask_raw_numbers_and_successor_preserves_private_audit(compiled) -> None:
    _policy, dell_material, packs, results = compiled
    result = results["DELL"]
    views = result["node_views"]
    assert views["research_view"]["numeric_facts"] == views["writer_view"]["numeric_facts"]
    assert views["writer_view"]["numeric_facts"] == views["verifier_view"]["numeric_facts"]
    serialized_views = json.dumps(views, ensure_ascii=False)
    assert '"source_text"' not in serialized_views
    assert "$4.1 billion" not in serialized_views
    assert "[CONTEXT_ONLY_NUMERIC_DO_NOT_OUTPUT]" in serialized_views

    base_input = dell_material["case_input"]
    before = canonical_digest(base_input)
    successor = compile_numeric_cocompilation_successor_input(
        base_case_input=base_input,
        pack=packs["DELL"],
        result=result,
    )
    assert canonical_digest(base_input) == before
    assert successor["private_audit_binding"]["raw_source_material_count"] == 27
    assert successor["private_audit_binding"]["raw_source_content_in_successor_model_input"] is False
    assert all(
        "source_text" not in row
        for row in successor["model_input"]["selected_evidence"]
    )
    assert "We booked $24.4 billion" not in json.dumps(
        successor["model_input"],
        ensure_ascii=False,
    )


def test_market_close_does_not_authorize_target_price(compiled) -> None:
    policy, _dell_material, _packs, results = compiled
    result = results["DELL"]
    close = _metric_facts(result, "raw_daily_close")[0]
    assert policy["hard_boundaries"][
        "market_pit_authorizes_valuation_or_recommendation"
    ] is False
    assert not any(
        "valuation" in row["semantic_metric_key"]
        or "target_price" in row["semantic_metric_key"]
        for row in result["presentation_program"]["formula_traces"]
    )
    target_price = evaluate_delivery_numeric_authority(
        delivery_text="目标价 $437.65。",
        used_numeric_refs=[close["numeric_ref"]],
        used_formula_refs=[],
        inventory=result["candidate_inventory"],
        presentation_program=result["presentation_program"],
        semantic_verifier_pass=True,
    )
    assert target_price["status"] == "hard_fail"
