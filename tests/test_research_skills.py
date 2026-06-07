from __future__ import annotations

import pytest

from sec_agent.agent_registry import list_agent_registry
from sec_agent.research_skills import list_research_skills, load_research_skill, research_skill_prompt


def test_role_specific_multi_agent_skills_are_listed_and_loadable() -> None:
    inventory = list_research_skills()

    for skill_id in [
        "shared_evidence_boundary",
        "research_lead_planning",
        "coverage_reflection",
        "memo_writer",
        "verification",
        "fundamental_analysis",
        "industry_supply_chain_analysis",
        "market_valuation_analysis",
        "risk_counterevidence",
        "relationship_universe",
        "evidence_operator_tool_use",
        "judgment_plan_aggregation",
        "renderer",
    ]:
        assert skill_id in inventory["skill_files"]
        assert load_research_skill(skill_id)

    for role in [
        "research_lead",
        "coverage_reflection",
        "memo_writer",
        "verifier",
        "universe_relationship",
        "sec_operator",
        "eight_k_operator",
        "market_operator",
        "industry_operator",
        "fundamental_analyst",
        "industry_supply_chain_analyst",
        "market_valuation_analyst",
        "risk_counterevidence_analyst",
        "judgment_plan_aggregator",
        "renderer",
    ]:
        assert role in inventory["role_skills"]
        assert "Shared Evidence Boundary Skill" in research_skill_prompt(role)


def test_agent_registry_skill_ids_are_loadable_and_role_mapped() -> None:
    inventory = list_research_skills()
    skill_ids = set(inventory["skill_files"])
    role_ids = set(inventory["role_skills"])

    for agent in list_agent_registry():
        assert agent["agent_id"] in role_ids
        for skill_id in agent["skill_ids"]:
            assert skill_id in skill_ids
            assert load_research_skill(skill_id)


def test_role_specific_skill_prompts_truncate_and_fail_closed() -> None:
    prompt = research_skill_prompt("research_lead", max_chars=120)

    assert "Shared Evidence" in prompt
    assert prompt.endswith("[skill truncated by runtime budget]")

    with pytest.raises(KeyError):
        load_research_skill("not_registered")
    with pytest.raises(KeyError):
        research_skill_prompt("not_a_role")


def test_research_lead_planning_skill_has_cost_aware_route_policy() -> None:
    prompt = load_research_skill("research_lead_planning")

    assert "Route Selection Policy" in prompt
    assert "route_selection_reason" in prompt
    assert "route_cost_tier" in prompt
    assert "milvus_semantic" in prompt
    assert "cannot prove exact values" in prompt


def test_market_and_industry_skills_use_source_family_bundle_boundaries() -> None:
    market = load_research_skill("market_valuation_analysis")
    industry = load_research_skill("industry_supply_chain_analysis")

    for prompt in (market, industry):
        assert "source_family_bundle" in prompt
        assert "selected_source_families" in prompt
        assert "forbidden_claim_scopes" in prompt

    assert "market rows cannot prove company-reported revenue" in market
    assert "Industry and relationship evidence can support scope, context, and hypotheses" in industry


def test_specialist_role_specific_skills_use_v0_2_or_later_quality_contracts() -> None:
    for skill_id in [
        "fundamental_analysis",
        "industry_supply_chain_analysis",
        "market_valuation_analysis",
        "risk_counterevidence",
    ]:
        prompt = load_research_skill(skill_id)

        assert any(version in prompt for version in ("Skill v0.2", "Skill v0.3"))
        assert "Required Input Fields" in prompt
        assert "Analysis Steps" in prompt
        assert "Required Output Structure" in prompt
        assert "Failure / Evidence Gap Handling" in prompt
        assert "Quality Rubric" in prompt
