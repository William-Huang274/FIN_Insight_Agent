from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_residual_gap_external_supplement import (  # noqa: E402
    CASES,
    ResidualGapExternalSupplementError,
    canonical_digest,
    compile_residual_gap_external_priority_plan,
    load_bound_local_evidence_packs,
    load_residual_gap_external_supplement_policy,
    validate_residual_gap_external_priority_plan,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_residual_gap_external_supplement_policy_v1_0.json"
)


@pytest.fixture(scope="module")
def compiled():
    policy = load_residual_gap_external_supplement_policy(
        POLICY_PATH,
        repo_root=ROOT,
    )
    local_result, packs = load_bound_local_evidence_packs(
        policy=policy,
        repo_root=ROOT,
    )
    plan = compile_residual_gap_external_priority_plan(
        policy=policy,
        local_result=local_result,
        packs=packs,
    )
    return policy, packs, plan


def _rehash(plan: dict) -> dict:
    body = deepcopy(plan)
    body.pop("plan_digest", None)
    return {**body, "plan_digest": canonical_digest(body)}


def _intent(plan: dict, case_key: str, intent_key: str) -> dict:
    return next(
        row
        for row in plan["selected_intents"]
        if row["case_key"] == case_key and row["intent_key"] == intent_key
    )


def test_all_126_gaps_are_selected_or_typed_deferred(compiled) -> None:
    _policy, packs, plan = compiled
    raw_ids = {
        gap["gap_id"]
        for case_key in CASES
        for gap in packs[case_key]["residual_gaps"]
    }
    selected_ids = {
        gap_id
        for row in plan["selected_intents"]
        for gap_id in row["selected_gap_ids"]
    }
    deferred_ids = {row["gap_id"] for row in plan["deferred_gap_dispositions"]}
    assert len(raw_ids) == 126
    assert selected_ids.isdisjoint(deferred_ids)
    assert selected_ids | deferred_ids == raw_ids
    assert len(plan["selected_intents"]) == 12
    assert all(
        sum(row["case_key"] == case_key for row in plan["selected_intents"]) == 2
        for case_key in CASES
    )


def test_business_priorities_are_queries_not_raw_field_searches(compiled) -> None:
    _policy, _packs, plan = compiled
    dell_demand = _intent(plan, "DELL", "issuer_demand_margin_cash")
    assert "AI server backlog" in dell_demand["official_domain_query"]["en"]
    assert "margin" in dell_demand["official_domain_query"]["en"]
    assert "working capital" in dell_demand["official_domain_query"]["en"]
    assert "site:investors.delltechnologies.com" in dell_demand[
        "official_domain_query"
    ]["en"]

    orcl_demand = _intent(plan, "ORCL", "issuer_cloud_demand_value")
    assert "RPO" in orcl_demand["semantic_locator_query"]["en"]
    assert "OCI revenue" in orcl_demand["semantic_locator_query"]["en"]
    assert "product mix" in orcl_demand["semantic_locator_query"]["en"]


def test_market_formula_threshold_and_private_attribution_stay_deferred(compiled) -> None:
    _policy, _packs, plan = compiled
    deferred = {row["gap_id"]: row for row in plan["deferred_gap_dispositions"]}
    capital_rows = [
        row
        for row in deferred.values()
        if row["slot_id"] == "capital_allocation_and_valuation"
    ]
    assert capital_rows
    assert all(
        row["defer_reason"] == "local_market_pit_or_numeric_program_owned"
        for row in capital_rows
    )
    assert any(
        row["defer_reason"] == "s3_analysis_method_and_user_risk_preference_owned"
        for row in deferred.values()
    )
    assert any(
        row["defer_reason"]
        == "low_public_obtainability_preserve_company_specific_boundary"
        for row in deferred.values()
    )


def test_provider_is_locator_only_and_has_no_evidence_authority(compiled) -> None:
    _policy, _packs, plan = compiled
    assert plan["routing_contract"]["broad_provider_is_locator_only"] is True
    assert plan["routing_contract"]["provider_snippet_is_evidence"] is False
    assert (
        plan["routing_contract"]["provider_reported_date_is_financial_date_authority"]
        is False
    )
    assert plan["stage_acceptance"]["network_authority_issued"] is False
    for row in plan["selected_intents"]:
        assert row["provider_role"] == "locator_only"
        assert row["provider_date_authority"] is False
        assert row["evidence_promotion_allowed"] is False
        assert row["writer_citable"] is False


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("duplicate_gap", "residual_external_selected_gap_duplicate"),
        ("cross_case_gap", "residual_external_selected_gap_unknown_or_cross_case"),
        ("budget_increase", "residual_external_budget_invalid"),
        ("gold_url", "residual_external_gold_leak"),
        ("provider_promotion", "residual_external_plan_intent_boundary_invalid"),
        ("network_authority", "residual_external_plan_authority_boundary_invalid"),
        ("nested_intent_mutation", "residual_external_plan_intent_boundary_invalid"),
    ],
)
def test_mutations_fail_closed(compiled, mutation, expected_code) -> None:
    policy, packs, plan = compiled
    if mutation in {"duplicate_gap", "cross_case_gap"}:
        changed_policy = deepcopy(policy)
        if mutation == "duplicate_gap":
            changed_policy["intent_groups"][1]["selected_gap_ids"].append(
                changed_policy["intent_groups"][0]["selected_gap_ids"][0]
            )
        else:
            changed_policy["intent_groups"][0]["selected_gap_ids"][0] = (
                changed_policy["intent_groups"][2]["selected_gap_ids"][0]
            )
        local_result, _ = load_bound_local_evidence_packs(
            policy=policy,
            repo_root=ROOT,
        )
        with pytest.raises(ResidualGapExternalSupplementError) as exc:
            compile_residual_gap_external_priority_plan(
                policy=changed_policy,
                local_result=local_result,
                packs=packs,
            )
    elif mutation in {"budget_increase", "gold_url"}:
        changed_policy = deepcopy(policy)
        if mutation == "budget_increase":
            changed_policy["budget"]["locator_provider_call_ceiling"] = 13
        else:
            changed_policy["intent_groups"][0]["gold_target"] = (
                "https://example.invalid/answer"
            )
        with pytest.raises(ResidualGapExternalSupplementError) as exc:
            load_residual_gap_external_supplement_policy_from_value(changed_policy)
    else:
        changed_plan = deepcopy(plan)
        if mutation == "provider_promotion":
            changed_plan["selected_intents"][0]["evidence_promotion_allowed"] = True
        elif mutation == "network_authority":
            changed_plan["stage_acceptance"]["network_authority_issued"] = True
        else:
            changed_plan["selected_intents"][0]["decision_surface"] += " mutated"
        changed_plan = _rehash(changed_plan)
        with pytest.raises(ResidualGapExternalSupplementError) as exc:
            validate_residual_gap_external_priority_plan(changed_plan, policy=policy)
    assert exc.value.code == expected_code


def load_residual_gap_external_supplement_policy_from_value(value: dict) -> dict:
    """Exercise file-backed policy validation without weakening the public loader."""
    from tempfile import TemporaryDirectory
    import json

    with TemporaryDirectory() as directory:
        path = Path(directory) / "policy.json"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return load_residual_gap_external_supplement_policy(path, repo_root=ROOT)
