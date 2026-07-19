from __future__ import annotations

from sec_agent.method_runtime import (
    build_method_runtime_pack,
    compact_method_runtime_pack_for_prompt,
    project_graph_edge_investment_role,
    specialist_runtime_rubric,
)


def test_method_runtime_pack_detects_ai_semis_and_exposes_runtime_contract() -> None:
    pack = build_method_runtime_pack(
        {"query_contract": {"focus_tickers": ["NVDA", "DELL"]}},
        user_query="Analyze NVDA Blackwell supply read-through into DELL AI servers.",
        focus_tickers=["NVDA", "DELL"],
    )

    assert pack["status"] == "runtime_injected"
    assert pack["lane"] == "ai_semis"
    assert "p32_product_architecture_competitive_bridge" in pack["active_method_ids"]
    assert "research_lead_thesis_path" in pack["runtime_consumption_required"]
    assert {item["required_item"] for item in pack["research_lead_required_items"]} >= {
        "product_architecture_competition",
        "customer_deployment_adoption",
        "supply_chain_readthrough",
        "fundamental_financial_bridge",
        "risk_and_counterevidence",
    }

    product_rubric = specialist_runtime_rubric(pack, "product_technology_analyst")
    assert "architecture_spec_generation_change" in product_rubric["must_answer"]
    assert "product_revenue_without_exact_kpi" in product_rubric["must_not_infer"]

    compact = compact_method_runtime_pack_for_prompt(pack, agent_id="product_technology_analyst")
    assert compact["specialist_runtime_rubric"]["role_runtime_mission"].startswith("Convert product evidence")
    assert compact["ai_semis_playbook"]["forbidden_shortcut"].startswith("Do not treat peer group")


def test_graph_edge_projection_carries_investment_role_and_boundaries() -> None:
    projection = project_graph_edge_investment_role("supplies", "supply_chain_signal")

    assert projection["edge_investment_role"] == "supply_constraint"
    assert "bottleneck" in projection["supports_judgment"]
    assert "cannot infer exact revenue" in projection["cannot_infer"]
    assert "capacity" in projection["needed_confirmation"] or "allocation" in projection["needed_confirmation"]
