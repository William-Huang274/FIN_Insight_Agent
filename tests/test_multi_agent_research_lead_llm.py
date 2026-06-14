from __future__ import annotations

import json
from typing import Any

from sec_agent.agent_registry import agent_registry_by_id
from sec_agent.industry_playbooks import load_playbook_registry, match_playbook_candidates
from sec_agent.multi_agent_router import route_multi_agent_activation
from sec_agent.research_lead_llm import (
    ROUTE_SOURCE,
    ResearchLeadLLMConfig,
    _normalize_evidence_requirement_payload_routes,
    extract_activation_plan_json,
    research_lead_llm_config_from_env,
    route_activation_from_env,
    route_research_lead_activation_llm,
)


def test_research_lead_llm_accepts_valid_activation_plan_json() -> None:
    request = _case("Analyze AMZN margins with management commentary.", "focused_answer", ["AMZN"], ["AMZN"])
    plan = route_multi_agent_activation(request)["activation_plan"]
    fake = _FakeChat([json.dumps(plan)])

    result = route_research_lead_activation_llm(request, config=_config(), call_chat_completion=fake)

    assert result["source"] == ROUTE_SOURCE
    assert result["status"] == "pass"
    assert result["activation_plan"]["execution_mode"] == "focused_answer"
    assert result["validation"]["status"] == "pass"
    assert result["routing_trace"]["repair_attempts"] == 0
    assert fake.calls[0]["response_format"] == {"type": "json_object"}
    assert "tools" not in fake.calls[0]
    assert "Do not call tools" in fake.calls[0]["messages"][0]["content"]


def test_research_lead_llm_accepts_activation_plus_evidence_requirement_plan() -> None:
    request = _case("Analyze AMZN margins with management commentary.", "focused_answer", ["AMZN"], ["AMZN"])
    request["context"]["query_contract"] = _query_contract(["AMZN"])
    activation_plan = route_multi_agent_activation(request)["activation_plan"]
    fake = _FakeChat([json.dumps({"activation_plan": activation_plan, "evidence_requirement_plan": _evidence_plan(["AMZN"])})])

    result = route_research_lead_activation_llm(
        request,
        config=ResearchLeadLLMConfig(
            llm_backend="unit",
            base_url="http://unit.test",
            chat_completions_path="/chat/completions",
            model="unit-model",
            api_key_env="UNIT_API_KEY",
            require_evidence_requirements=True,
        ),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["activation_plan"]["execution_mode"] == "focused_answer"
    assert result["evidence_requirement_plan"]["multi_agent_evidence_requirement_validation"]["status"] == "pass"
    assert result["evidence_requirement_plan"]["requirements"][0]["operator_owners"] == ["sec_operator"]
    assert result["routing_trace"]["evidence_requirements_source"] == "llm_output"
    assert "EvidenceRequirementPlan schema hint" in fake.calls[0]["messages"][0]["content"]


def test_research_lead_prompt_exposes_cost_aware_route_selection_policy() -> None:
    request = _case("Compare NVDA and AMD with valuation, industry context, and semantic filing recall.", "standard_memo", ["NVDA", "AMD"], ["NVDA", "AMD"])
    plan = route_multi_agent_activation(request)["activation_plan"]
    fake = _FakeChat([json.dumps(plan)])

    result = route_research_lead_activation_llm(request, config=_config(), call_chat_completion=fake)

    system_prompt = fake.calls[0]["messages"][0]["content"]
    user_prompt = fake.calls[0]["messages"][1]["content"]
    assert result["status"] == "pass"
    assert result["activation_plan"]["metadata"]["route_selection_policy"] == "cost_and_query_type_aware_v0_1"
    assert "Route choice policy" in system_prompt
    assert "route_selection_reason" in system_prompt
    assert "route_cost_tier" in system_prompt
    assert "milvus_semantic" in system_prompt
    assert "semantic recall supplement only" in system_prompt
    assert "exact values use ledger_first first" in user_prompt


def test_research_lead_llm_repairs_invalid_evidence_requirement_owner() -> None:
    request = _case("Analyze AMZN margins with management commentary.", "focused_answer", ["AMZN"], ["AMZN"])
    request["context"]["query_contract"] = _query_contract(["AMZN"])
    activation_plan = route_multi_agent_activation(request)["activation_plan"]
    invalid_evidence = _evidence_plan(["AMZN"])
    invalid_evidence["requirements"][0]["operator_owners"] = ["market_operator"]
    valid_evidence = _evidence_plan(["AMZN"])
    fake = _FakeChat(
        [
            json.dumps({"activation_plan": activation_plan, "evidence_requirement_plan": invalid_evidence}),
            json.dumps({"activation_plan": activation_plan, "evidence_requirement_plan": valid_evidence}),
        ]
    )

    result = route_research_lead_activation_llm(
        request,
        config=ResearchLeadLLMConfig(
            llm_backend="unit",
            base_url="http://unit.test",
            chat_completions_path="/chat/completions",
            model="unit-model",
            api_key_env="UNIT_API_KEY",
            max_repair_attempts=1,
            require_evidence_requirements=True,
        ),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["routing_trace"]["repair_attempts"] == 1
    assert len(fake.calls) == 2
    assert "evidence_requirement_plan_validation_failed" in fake.calls[1]["messages"][1]["content"]


def test_research_lead_llm_uses_evidence_fallback_without_repair_when_optional() -> None:
    request = _case("Analyze AMZN margins with management commentary.", "focused_answer", ["AMZN"], ["AMZN"])
    request["context"]["query_contract"] = _query_contract(["AMZN"])
    activation_plan = route_multi_agent_activation(request)["activation_plan"]
    invalid_evidence = _evidence_plan(["AMZN"])
    invalid_evidence["requirements"][0]["operator_owners"] = ["market_operator"]
    fake = _FakeChat([json.dumps({"activation_plan": activation_plan, "evidence_requirement_plan": invalid_evidence})])

    result = route_research_lead_activation_llm(
        request,
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert result["routing_trace"]["repair_attempts"] == 0
    assert result["routing_trace"]["evidence_requirements_source"] == "deterministic_compiler_fallback"
    assert result["validation"]["warnings"][0]["fallback"] == "deterministic_compiler_fallback"
    assert len(fake.calls) == 1


def test_research_lead_llm_parses_fenced_json() -> None:
    request = _case("MSFT capex only.", "deterministic_lookup", ["MSFT"], ["MSFT"])
    plan = route_multi_agent_activation(request)["activation_plan"]
    fake = _FakeChat([f"```json\n{json.dumps(plan)}\n```"])

    result = route_research_lead_activation_llm(request, config=_config(), call_chat_completion=fake)

    assert extract_activation_plan_json(f"```json\n{json.dumps(plan)}\n```") == plan
    assert result["status"] == "pass"
    assert result["activation_plan"]["execution_mode"] == "deterministic_lookup"


def test_research_lead_llm_repairs_invalid_json_then_passes() -> None:
    request = _case("Compare NVDA and AMD with market reaction.", "standard_memo", ["NVDA", "AMD"], ["NVDA", "AMD"])
    plan = route_multi_agent_activation(request)["activation_plan"]
    fake = _FakeChat(["not json", json.dumps(plan)])

    result = route_research_lead_activation_llm(request, config=_config(), call_chat_completion=fake)

    assert result["status"] == "pass"
    assert result["routing_trace"]["repair_attempts"] == 1
    assert len(fake.calls) == 2
    assert "Repair the previous output" in fake.calls[1]["messages"][1]["content"]
    assert result["activation_plan"]["execution_mode"] == "standard_memo"


def test_research_lead_llm_prunes_risk_specialist_without_explicit_risk_intent() -> None:
    request = _case(
        "Compare NVDA and AMD reported revenue and gross margin disclosures only.",
        "standard_memo",
        ["NVDA", "AMD"],
        ["NVDA", "AMD"],
    )
    plan = route_multi_agent_activation(
        _case(
            "Compare NVDA and AMD fundamentals, management commentary, market reaction, and downside risk.",
            "standard_memo",
            ["NVDA", "AMD"],
            ["NVDA", "AMD"],
        )
    )["activation_plan"]
    assert "risk_counterevidence_analyst" in plan["activate_agents"]
    fake = _FakeChat([json.dumps(plan)])

    result = route_research_lead_activation_llm(request, config=_config(), call_chat_completion=fake)

    assert result["status"] == "pass"
    assert "risk_counterevidence_analyst" not in result["activation_plan"]["activate_agents"]
    assert result["activation_plan"]["metadata"]["risk_counterevidence_pruned"] is True
    assert any(item["agent_id"] == "risk_counterevidence_analyst" for item in result["activation_plan"]["skip_agents"])


def test_research_lead_llm_prunes_risk_for_plain_market_reaction_memo() -> None:
    request = _case(
        "先比较 NVDA 和 AMD 的基本面、管理层解释和市场反应，给出一段中文投研 memo。",
        "standard_memo",
        ["NVDA", "AMD"],
        ["NVDA", "AMD"],
    )
    request["context"]["query_contract"] = {
        **_query_contract(["NVDA", "AMD"]),
        "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot"],
    }
    plan = route_multi_agent_activation(
        _case(
            "Compare NVDA and AMD fundamentals, management commentary, market reaction, and downside risk.",
            "standard_memo",
            ["NVDA", "AMD"],
            ["NVDA", "AMD"],
        )
    )["activation_plan"]
    assert "risk_counterevidence_analyst" in plan["activate_agents"]
    fake = _FakeChat([json.dumps(plan)])

    result = route_research_lead_activation_llm(request, config=_config(), call_chat_completion=fake)

    assert result["status"] == "pass"
    assert "market_operator" in result["activation_plan"]["activate_agents"]
    assert "market_valuation_analyst" in result["activation_plan"]["activate_agents"]
    assert "risk_counterevidence_analyst" not in result["activation_plan"]["activate_agents"]
    assert result["activation_plan"]["metadata"]["risk_counterevidence_pruned"] is True


def test_research_lead_llm_keeps_risk_specialist_with_explicit_risk_intent() -> None:
    request = _case(
        "Compare NVDA and AMD fundamentals, market reaction, and downside risk.",
        "standard_memo",
        ["NVDA", "AMD"],
        ["NVDA", "AMD"],
    )
    plan = route_multi_agent_activation(request)["activation_plan"]
    assert "risk_counterevidence_analyst" in plan["activate_agents"]
    fake = _FakeChat([json.dumps(plan)])

    result = route_research_lead_activation_llm(request, config=_config(), call_chat_completion=fake)

    assert result["status"] == "pass"
    assert "risk_counterevidence_analyst" in result["activation_plan"]["activate_agents"]
    assert not result["activation_plan"].get("metadata", {}).get("risk_counterevidence_pruned")


def test_research_lead_llm_adds_risk_lens_for_pressure_and_evidence_gap_memo() -> None:
    request = _case(
        "Write an English investment memo comparing MSFT and GOOGL AI capex monetization, margin pressure, and evidence gaps.",
        "standard_memo",
        ["MSFT", "GOOGL"],
        ["MSFT", "GOOGL"],
    )
    request["context"]["query_contract"] = _query_contract(["MSFT", "GOOGL"])
    plan = route_multi_agent_activation(request)["activation_plan"]
    plan["activate_agents"] = [agent for agent in plan["activate_agents"] if agent != "risk_counterevidence_analyst"]
    plan["agent_priorities"].pop("risk_counterevidence_analyst", None)
    plan["model_policy_hint"].pop("risk_counterevidence_analyst", None)
    fake = _FakeChat([json.dumps(plan)])

    result = route_research_lead_activation_llm(request, config=_config(), call_chat_completion=fake)

    assert result["status"] == "pass"
    assert "risk_counterevidence_analyst" in result["activation_plan"]["activate_agents"]
    assert result["activation_plan"]["agent_priorities"]["risk_counterevidence_analyst"] == "supporting"
    assert result["activation_plan"]["metadata"]["risk_counterevidence_added"] is True


def test_research_lead_llm_aligns_focused_followup_market_and_8k_sources() -> None:
    request = _case(
        "接上一轮，只看 BAC 的信用风险和资本缓冲，不要继续分析 JPM；如果证据不足，说明缺什么。",
        "focused_answer",
        ["BAC"],
        ["BAC"],
    )
    request["context"]["previous_turn_summary"] = {
        "previous_case_id": "fin_full_mt_banking_t1",
        "previous_execution_mode": "standard_memo",
        "previous_focus_tickers": ["JPM", "BAC"],
        "previous_search_scope_tickers": ["JPM", "BAC"],
    }
    request["context"]["query_contract"] = {
        **_query_contract(["BAC"]),
        "focus_tickers": ["BAC"],
        "search_scope_tickers": ["BAC"],
        "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot"],
        "metric_families": ["provision_for_credit_losses", "net_charge_offs", "capital_ratio", "deposits"],
    }
    plan = route_multi_agent_activation(_case("BAC credit risk only.", "focused_answer", ["BAC"], ["BAC"]))["activation_plan"]
    plan["activate_agents"] = [agent for agent in plan["activate_agents"] if agent not in {"eight_k_operator", "market_operator"}]
    plan["allowed_source_families"] = ["primary_sec_filing"]
    narrow_evidence_plan = {
        "requirements": [
            {
                "requirement_id": "bac_credit_capital",
                "task_id": "bac_credit_capital",
                "question_zh": "BAC 2026年一季度信贷损失拨备、净核销、资本比率和存款数据",
                "priority": "primary",
                "tickers": ["BAC"],
                "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
                "source_families": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
                "evidence_routes": ["ledger_first", "filing_text", "8k_commentary"],
                "metric_families": ["provision_for_credit_losses", "net_charge_offs", "capital_ratio", "deposits"],
            }
        ]
    }
    fake = _FakeChat([json.dumps({"activation_plan": plan, "evidence_requirement_plan": narrow_evidence_plan})])

    result = route_research_lead_activation_llm(request, config=_config(), call_chat_completion=fake)

    assert result["status"] == "pass"
    assert result["activation_plan"]["execution_mode"] == "focused_answer"
    assert result["activation_plan"]["focus_tickers"] == ["BAC"]
    assert result["activation_plan"]["search_scope_tickers"] == ["BAC"]
    assert "eight_k_operator" in result["activation_plan"]["activate_agents"]
    assert "market_operator" in result["activation_plan"]["activate_agents"]
    assert "market_snapshot" in result["activation_plan"]["allowed_source_families"]
    assert result["activation_plan"]["max_tool_calls_total"] >= 8
    requirements = result["evidence_requirement_plan"]["requirements"]
    assert any("market_snapshot" in requirement.get("evidence_routes", []) for requirement in requirements)
    assert any("market_operator" in requirement.get("operator_owners", []) for requirement in requirements)


def test_research_lead_llm_preserves_cost_aware_route_metadata_for_mixed_sources() -> None:
    request = _case(
        "Compare NVDA and AMD fundamentals, market valuation reaction, industry power context, and hard-to-keyword filing themes.",
        "standard_memo",
        ["NVDA", "AMD"],
        ["NVDA", "AMD"],
    )
    request["context"]["query_contract"] = {
        **_query_contract(["NVDA", "AMD"]),
        "source_tiers": [
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "market_snapshot",
            "industry_snapshot",
        ],
        "metric_families": ["revenue", "gross_margin", "capex"],
    }
    plan = route_multi_agent_activation(request)["activation_plan"]
    plan["allowed_source_families"] = ["primary_sec_filing", "company_authored_unaudited_sec_filing"]
    fake = _FakeChat([json.dumps({"activation_plan": plan, "evidence_requirement_plan": _mixed_route_evidence_plan(["NVDA", "AMD"])})])

    result = route_research_lead_activation_llm(request, config=_config(), call_chat_completion=fake)

    assert result["status"] == "pass"
    assert result["activation_plan"]["metadata"]["route_selection_policy"] == "cost_and_query_type_aware_v0_1"
    assert {"market_operator", "industry_operator"} <= set(result["activation_plan"]["activate_agents"])
    assert {"market_snapshot", "industry_snapshot"} <= set(result["activation_plan"]["allowed_source_families"])
    by_id = {req["requirement_id"]: req for req in result["evidence_requirement_plan"]["requirements"]}
    assert by_id["req_exact"]["route_cost_tier"] == "low"
    assert by_id["req_semantic"]["route_cost_tier"] == "high"
    assert by_id["req_semantic"]["route_selection_policy"] == "cost_and_query_type_aware_v0_1"
    assert "semantic supplement" in by_id["req_semantic"]["route_selection_reason"]
    assert by_id["req_semantic"]["coverage_requirements"]["vector_kinds"] == ["paraphrase_context"]
    assert by_id["req_semantic"]["route_intents"][0]["route_cost_tier"] == "high"
    assert by_id["req_market"]["operator_owners"] == ["market_operator"]
    assert result["evidence_requirement_plan"]["multi_agent_contract"]["route_selection_policy"] == "cost_and_query_type_aware_v0_1"


def test_research_lead_llm_demotes_default_sector_pack_path_without_relationship_intent() -> None:
    request = _case(
        "比较 XOM 和 CVX 的 capex、现金流、管理层对 commodity 环境的表述和市场反应，输出风险平衡的投研 memo。",
        "standard_memo",
        ["XOM", "CVX"],
        ["XOM", "CVX"],
    )
    request["context"] = {
        "sector_depth_pack_path": "configs/sector_depth_packs_v0_1.yaml",
        "query_contract": {
            **_query_contract(["XOM", "CVX"]),
            "source_tiers": [
                "primary_sec_filing",
                "company_authored_unaudited_sec_filing",
                "market_snapshot",
                "industry_snapshot",
            ],
            "metric_families": ["capex", "free_cash_flow", "production", "realized_price"],
        },
    }
    deep_plan = route_multi_agent_activation(
        _case("Use sector-depth relationship evidence for NVDA supply-chain readthrough.", "deep_research", ["NVDA"], ["NVDA", "DELL"])
    )["activation_plan"]
    fake = _FakeChat([json.dumps(deep_plan)])

    result = route_research_lead_activation_llm(request, config=_config(), call_chat_completion=fake)

    assert result["status"] == "pass"
    assert result["activation_plan"]["execution_mode"] == "standard_memo"
    assert "universe_relationship" not in result["activation_plan"]["activate_agents"]
    assert "relationship_graph" not in result["activation_plan"]["allowed_source_families"]
    assert "industry_snapshot" in result["activation_plan"]["allowed_source_families"]
    assert "industry_supply_chain_analyst" not in result["activation_plan"]["activate_agents"]
    assert "risk_counterevidence_analyst" in result["activation_plan"]["activate_agents"]
    assert result["activation_plan"]["metadata"]["relationship_overroute_pruned"] is True


def test_research_lead_llm_promotes_relationship_source_to_deep_research() -> None:
    request = _case(
        "Use a sector-depth pack to compare banking peers with relationship evidence.",
        "standard_memo",
        ["JPM", "C"],
        ["JPM", "C", "WFC", "GS"],
    )
    request["context"]["query_contract"] = {
        **_query_contract(["JPM", "C"]),
        "search_scope_tickers": ["JPM", "C", "WFC", "GS"],
        "source_tiers": [
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "market_snapshot",
            "industry_snapshot",
            "relationship_graph",
        ],
    }
    standard_plan = route_multi_agent_activation(_case("Compare banks.", "standard_memo", ["JPM", "C"], ["JPM", "C"]))["activation_plan"]
    fake = _FakeChat([json.dumps(standard_plan)])

    result = route_research_lead_activation_llm(request, config=_config(), call_chat_completion=fake)

    assert result["status"] == "pass"
    assert result["activation_plan"]["execution_mode"] == "deep_research"
    assert "universe_relationship" in result["activation_plan"]["activate_agents"]
    assert "relationship_graph" in result["activation_plan"]["allowed_source_families"]
    assert result["activation_plan"]["relationship_scope_rationale"]
    assert result["activation_plan"]["agent_priorities"]["industry_supply_chain_analyst"] == "primary"
    assert "risk_counterevidence_analyst" in result["activation_plan"]["activate_agents"]
    assert result["activation_plan"]["agent_priorities"]["risk_counterevidence_analyst"] == "supporting"
    assert result["activation_plan"]["model_policy_hint"]["risk_counterevidence_analyst"] == "strong"


def test_research_lead_llm_fails_closed_after_repair_budget_without_fallback() -> None:
    request = _case("Compare NVDA and AMD with market reaction.", "standard_memo", ["NVDA", "AMD"], ["NVDA", "AMD"])
    invalid_plan = dict(route_multi_agent_activation(request)["activation_plan"])
    invalid_plan["max_tool_calls_total"] = 999
    fake = _FakeChat([json.dumps(invalid_plan), json.dumps(invalid_plan)])

    result = route_research_lead_activation_llm(
        request,
        config=ResearchLeadLLMConfig(max_repair_attempts=1, allow_deterministic_fallback=False),
        call_chat_completion=fake,
    )

    assert result["status"] == "fail"
    assert result["activation_plan"] == {}
    assert result["rejected_plan"]["max_tool_calls_total"] == 999
    assert result["routing_trace"]["fallback_used"] is False
    assert result["routing_trace"]["repair_attempts"] == 1
    assert "validation_failed" in result["failure_reason"]


def test_research_lead_llm_prunes_schema_hint_policy_placeholders_and_focused_scope_drift() -> None:
    request = _case(
        "用本地披露证据分析 LLY 最近研发投入和产品证据缺口。",
        "focused_answer",
        ["LLY"],
        ["LLY"],
    )
    plan = route_multi_agent_activation(request)["activation_plan"]
    plan["scope_mode"] = "full_universe"
    plan["model_policy_hint"]["agent_id"] = "none | fast | balanced | strong"
    plan["agent_priorities"]["agent_id"] = "primary | supporting | conditional | low"
    fake = _FakeChat([json.dumps(plan)])

    result = route_research_lead_activation_llm(request, config=_config(), call_chat_completion=fake)

    assert result["status"] == "pass"
    assert result["activation_plan"]["scope_mode"] == "focused_peer"
    assert "agent_id" not in result["activation_plan"]["model_policy_hint"]
    assert "agent_id" not in result["activation_plan"]["agent_priorities"]
    assert result["activation_plan"]["metadata"]["policy_map_placeholder_pruned"] is True


def test_research_lead_llm_rejects_direct_tool_calls_before_plan_validation() -> None:
    request = _case("MSFT capex only.", "deterministic_lookup", ["MSFT"], ["MSFT"])
    plan = route_multi_agent_activation(request)["activation_plan"]
    fake = _FakeChat(
        [
            {
                "content": "",
                "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "sec_search_filings"}}],
            },
            json.dumps(plan),
        ]
    )

    result = route_research_lead_activation_llm(request, config=_config(), call_chat_completion=fake)

    assert result["status"] == "pass"
    assert result["routing_trace"]["repair_attempts"] == 1
    assert agent_registry_by_id()["research_lead"]["allowed_tools"] == ["run_inspect_artifacts"]


def test_research_lead_alignment_adds_product_specialist_from_evidence_sources() -> None:
    request = _case(
        "Compare product revenue and commercial tracker gaps.",
        "standard_memo",
        ["AAPL", "MSFT"],
        ["AAPL", "MSFT"],
    )
    request["context"]["query_contract"] = {
        "focus_tickers": ["AAPL", "MSFT"],
        "search_scope_tickers": ["AAPL", "MSFT"],
        "source_tiers": ["primary_sec_filing", "company_product_evidence_graph"],
        "metric_families": ["product_revenue"],
    }
    plan = route_multi_agent_activation(request)["activation_plan"]
    plan["activate_agents"] = [agent for agent in plan["activate_agents"] if agent != "product_technology_analyst"]
    plan["allowed_source_families"] = ["primary_sec_filing", "company_authored_unaudited_sec_filing"]
    plan["agent_priorities"].pop("product_technology_analyst", None)
    evidence_plan = {
        "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
        "requirements": [
            {
                "requirement_id": "req_product",
                "task_id": "product_kpi",
                "question": "Need company-disclosed product KPI evidence.",
                "tickers": ["AAPL", "MSFT"],
                "source_tiers": ["company_product_evidence_graph"],
                "source_families": ["company_product_evidence_graph"],
                "metric_families": ["product_revenue"],
                "evidence_routes": [],
            }
        ],
    }
    fake = _FakeChat([json.dumps({"activation_plan": plan, "evidence_requirement_plan": evidence_plan})])

    result = route_research_lead_activation_llm(
        request,
        config=ResearchLeadLLMConfig(
            llm_backend="unit",
            base_url="http://unit.test",
            chat_completions_path="/chat/completions",
            model="unit-model",
            api_key_env="UNIT_API_KEY",
            require_evidence_requirements=True,
        ),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert "product_technology_analyst" in result["activation_plan"]["activate_agents"]
    assert "company_product_evidence_graph" in result["activation_plan"]["allowed_source_families"]
    assert result["activation_plan"]["agent_priorities"]["product_technology_analyst"] == "supporting"


def test_research_lead_normalizes_source_family_names_out_of_evidence_routes() -> None:
    request = _case(
        "Compare AAPL product evidence and public proxy gaps.",
        "standard_memo",
        ["AAPL"],
        ["AAPL"],
    )
    request["context"]["query_contract"] = {
        "focus_tickers": ["AAPL"],
        "search_scope_tickers": ["AAPL"],
        "source_tiers": ["primary_sec_filing", "company_product_evidence_graph", "public_source_context"],
        "metric_families": ["product_revenue"],
    }
    plan = route_multi_agent_activation(request)["activation_plan"]
    evidence_plan = {
        "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
        "requirements": [
            {
                "requirement_id": "req_product_evidence_graph",
                "task_id": "product_kpi",
                "source_tiers": ["company_product_evidence_graph"],
                "evidence_routes": ["company_product_evidence_graph"],
                "metric_families": ["product_revenue"],
            },
            {
                "requirement_id": "req_public_source_context",
                "task_id": "public_proxy_context",
                "source_tiers": ["public_source_context"],
                "evidence_routes": ["public_source_context"],
                "metric_families": ["market_share"],
            },
        ],
    }
    fake = _FakeChat([json.dumps({"activation_plan": plan, "evidence_requirement_plan": evidence_plan})])

    result = route_research_lead_activation_llm(
        request,
        config=ResearchLeadLLMConfig(
            llm_backend="unit",
            base_url="http://unit.test",
            chat_completions_path="/chat/completions",
            model="unit-model",
            api_key_env="UNIT_API_KEY",
            require_evidence_requirements=True,
        ),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    normalized_payload = _normalize_evidence_requirement_payload_routes(evidence_plan)
    normalized_requirements = {row["requirement_id"]: row for row in normalized_payload["requirements"]}
    assert normalized_requirements["req_product_evidence_graph"]["evidence_routes"] == []
    assert "company_product_evidence_graph" in normalized_requirements["req_product_evidence_graph"]["source_families"]
    assert normalized_requirements["req_public_source_context"]["evidence_routes"] == []
    assert "public_source_context" in normalized_requirements["req_public_source_context"]["source_families"]
    assert "market_operator" in result["activation_plan"]["activate_agents"]
    assert "market_snapshot" in result["activation_plan"]["allowed_source_families"]
    requirements = result["evidence_requirement_plan"]["requirements"]
    by_id = {row["requirement_id"]: row for row in requirements}
    assert by_id["req_public_source_context"]["evidence_routes"] == ["market_snapshot"]
    assert "market_snapshot" in by_id["req_public_source_context"]["source_families"]


def test_research_lead_downgrades_live_web_without_scope_policy() -> None:
    request = _case(
        "Compare CRM and SNOW product traction using public context if available.",
        "standard_memo",
        ["CRM", "SNOW"],
        ["CRM", "SNOW"],
    )
    request["context"]["query_contract"] = {
        "focus_tickers": ["CRM", "SNOW"],
        "search_scope_tickers": ["CRM", "SNOW"],
        "source_tiers": [
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "company_product_evidence_graph",
            "public_source_context",
        ],
        "metric_families": ["revenue", "rpo_deferred_revenue", "market_share"],
    }
    plan = route_multi_agent_activation(request)["activation_plan"]
    plan["activate_agents"] = [*plan["activate_agents"], "web_evidence_operator"]
    plan["allowed_source_families"] = [*plan["allowed_source_families"], "live_public_web_context"]
    plan["agent_priorities"]["web_evidence_operator"] = "supporting"
    plan["model_policy_hint"]["web_evidence_operator"] = "none"
    evidence_plan = {
        "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
        "requirements": [
            {
                "requirement_id": "req_live_web_context",
                "task_id": "public_proxy_context",
                "source_tiers": ["live_public_web_context"],
                "evidence_routes": ["live_public_web_context"],
                "metric_families": ["market_share"],
            }
        ],
    }
    fake = _FakeChat([json.dumps({"activation_plan": plan, "evidence_requirement_plan": evidence_plan})])

    result = route_research_lead_activation_llm(
        request,
        config=ResearchLeadLLMConfig(
            llm_backend="unit",
            base_url="http://unit.test",
            chat_completions_path="/chat/completions",
            model="unit-model",
            api_key_env="UNIT_API_KEY",
            require_evidence_requirements=True,
        ),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert "web_evidence_operator" not in result["activation_plan"]["activate_agents"]
    assert "live_public_web_context" not in result["activation_plan"]["allowed_source_families"]
    assert "public_source_context" in result["activation_plan"]["allowed_source_families"]
    assert result["activation_plan"]["metadata"]["live_web_downgraded"] is True
    requirements = result["evidence_requirement_plan"]["requirements"]
    assert requirements[0]["evidence_routes"] == ["market_snapshot"]
    assert "market_snapshot" in result["activation_plan"]["allowed_source_families"]


def test_research_lead_prunes_product_agent_for_public_context_without_product_intent() -> None:
    request = _case(
        "比较 WMT 和 TGT 的收入、利润率、库存或消费者需求风险，并说明 POS/panel/渠道库存这类缺口是否只能靠商业 tracker。",
        "standard_memo",
        ["WMT", "TGT"],
        ["WMT", "TGT"],
    )
    request["context"]["query_contract"] = {
        "focus_tickers": ["WMT", "TGT"],
        "search_scope_tickers": ["WMT", "TGT"],
        "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot", "public_source_context"],
        "metric_families": ["revenue", "gross_margin", "inventory", "cash_flow", "valuation"],
    }
    plan = route_multi_agent_activation(request)["activation_plan"]
    plan["activate_agents"] = [*plan["activate_agents"], "product_technology_analyst"]
    plan["allowed_source_families"] = [*plan["allowed_source_families"], "company_product_evidence_graph"]
    plan["agent_priorities"]["product_technology_analyst"] = "supporting"
    plan["model_policy_hint"]["product_technology_analyst"] = "balanced"
    evidence_plan = {
        "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
        "requirements": [
            {
                "requirement_id": "req_bank_public_context",
                "task_id": "market_public_context",
                "source_tiers": ["market_snapshot"],
                "evidence_routes": ["market_snapshot"],
                "metric_families": ["inventory", "gross_margin"],
            }
        ],
    }
    fake = _FakeChat([json.dumps({"activation_plan": plan, "evidence_requirement_plan": evidence_plan})])

    result = route_research_lead_activation_llm(
        request,
        config=ResearchLeadLLMConfig(
            llm_backend="unit",
            base_url="http://unit.test",
            chat_completions_path="/chat/completions",
            model="unit-model",
            api_key_env="UNIT_API_KEY",
            require_evidence_requirements=True,
        ),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert "product_technology_analyst" not in result["activation_plan"]["activate_agents"]
    assert "company_product_evidence_graph" not in result["activation_plan"]["allowed_source_families"]
    assert "public_source_context" in result["activation_plan"]["allowed_source_families"]
    assert result["activation_plan"]["metadata"]["product_technology_pruned"] is True


def test_research_lead_removes_milvus_semantic_when_runtime_unavailable() -> None:
    request = _case(
        "从 AI infrastructure sector-depth pack 出发，分析 NVDA、DELL、ANET、VRT 的需求传导和反证风险。",
        "deep_research",
        ["NVDA", "DELL"],
        ["NVDA", "DELL", "ANET", "VRT"],
    )
    request["context"]["query_contract"] = {
        "focus_tickers": ["NVDA", "DELL"],
        "search_scope_tickers": ["NVDA", "DELL", "ANET", "VRT"],
        "source_tiers": [
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "market_snapshot",
            "industry_snapshot",
            "relationship_graph",
            "company_product_evidence_graph",
            "public_source_context",
            "milvus_semantic",
        ],
        "metric_families": ["revenue", "orders_backlog", "capex", "rpo_deferred_revenue"],
    }
    request["source_inventory"] = {
        "source_families": [
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "market_snapshot",
            "industry_snapshot",
            "relationship_graph",
            "company_product_evidence_graph",
            "public_source_context",
            "milvus_semantic",
        ],
        "milvus_runtime": {"available": False, "status": "unavailable"},
        "source_family_availability": {"milvus_semantic": {"available": False, "status": "unavailable"}},
    }
    plan = route_multi_agent_activation(request)["activation_plan"]
    plan["allowed_source_families"] = [*plan["allowed_source_families"], "milvus_semantic"]
    evidence_plan = {
        "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
        "requirements": [
            {
                "requirement_id": "req_semantic_recall",
                "task_id": "filing_theme_recall",
                "source_tiers": ["milvus_semantic", "primary_sec_filing"],
                "evidence_routes": ["milvus_semantic", "filing_text"],
                "metric_families": ["orders_backlog"],
            }
        ],
    }
    fake = _FakeChat([json.dumps({"activation_plan": plan, "evidence_requirement_plan": evidence_plan})])

    result = route_research_lead_activation_llm(
        request,
        config=ResearchLeadLLMConfig(
            llm_backend="unit",
            base_url="http://unit.test",
            chat_completions_path="/chat/completions",
            model="unit-model",
            api_key_env="UNIT_API_KEY",
            require_evidence_requirements=True,
        ),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert "milvus_semantic" not in result["activation_plan"]["allowed_source_families"]
    assert result["activation_plan"]["metadata"]["milvus_semantic_removed"] is True
    assert "milvus_semantic" not in result["evidence_requirement_plan"]["scope"]["source_tiers"]
    for requirement in result["evidence_requirement_plan"]["requirements"]:
        assert "milvus_semantic" not in requirement["evidence_routes"]


def test_research_lead_prunes_relationship_route_without_scope_intent_after_alignment() -> None:
    request = _case(
        "比较 AAPL 的 iPhone、Mac、Services 相关产品证据与财务表现。",
        "standard_memo",
        ["AAPL"],
        ["AAPL"],
    )
    request["context"]["query_contract"] = {
        "focus_tickers": ["AAPL"],
        "search_scope_tickers": ["AAPL"],
        "source_tiers": [
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "market_snapshot",
            "company_product_evidence_graph",
            "public_source_context",
        ],
        "metric_families": ["revenue", "segment_revenue", "product_revenue", "gross_margin", "valuation"],
    }
    plan = route_multi_agent_activation(request)["activation_plan"]
    plan["activate_agents"] = [*plan["activate_agents"], "universe_relationship"]
    plan["allowed_source_families"] = [*plan["allowed_source_families"], "relationship_graph"]
    plan["agent_priorities"]["universe_relationship"] = "supporting"
    plan["model_policy_hint"]["universe_relationship"] = "balanced"
    evidence_plan = {
        "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
        "requirements": [
            {
                "requirement_id": "req_relationship_overroute",
                "task_id": "product_peer_context",
                "source_tiers": ["relationship_graph", "primary_sec_filing"],
                "evidence_routes": ["relationship_graph", "filing_text"],
                "metric_families": ["product_revenue"],
            }
        ],
    }
    fake = _FakeChat([json.dumps({"activation_plan": plan, "evidence_requirement_plan": evidence_plan})])

    result = route_research_lead_activation_llm(
        request,
        config=ResearchLeadLLMConfig(
            llm_backend="unit",
            base_url="http://unit.test",
            chat_completions_path="/chat/completions",
            model="unit-model",
            api_key_env="UNIT_API_KEY",
            require_evidence_requirements=True,
        ),
        call_chat_completion=fake,
    )

    assert result["status"] == "pass"
    assert "universe_relationship" not in result["activation_plan"]["activate_agents"]
    assert "relationship_graph" not in result["activation_plan"]["allowed_source_families"]
    assert result["activation_plan"]["metadata"]["relationship_overroute_pruned"] is True
    for requirement in result["evidence_requirement_plan"]["requirements"]:
        assert "relationship_graph" not in requirement["evidence_routes"]


def test_research_lead_alignment_applies_playbook_policy_from_inventory() -> None:
    registry = load_playbook_registry()
    request = _case(
        "Compare these peers' business drivers for a standard memo.",
        "standard_memo",
        ["AAPL", "MSFT"],
        ["AAPL", "MSFT"],
    )
    request["source_inventory"] = {
        "playbook_candidates": match_playbook_candidates({"consumer electronics hardware": {"AAPL", "MSFT"}}, registry),
        "available_source_families": [
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "company_product_evidence_graph",
            "public_source_context",
        ],
        "source_family_availability": {
            "primary_sec_filing": {"status": "available", "available": True},
            "company_authored_unaudited_sec_filing": {"status": "available", "available": True},
            "company_product_evidence_graph": {"status": "available", "available": True},
            "public_source_context": {"status": "available", "available": True},
        },
    }
    plan = route_multi_agent_activation({**request, "source_inventory": {}})["activation_plan"]
    plan["activate_agents"] = [agent for agent in plan["activate_agents"] if agent != "product_technology_analyst"]
    plan["allowed_source_families"] = ["primary_sec_filing", "company_authored_unaudited_sec_filing"]
    plan["agent_priorities"].pop("product_technology_analyst", None)
    fake = _FakeChat([json.dumps(plan)])

    result = route_research_lead_activation_llm(request, config=_config(), call_chat_completion=fake)

    assert result["status"] == "pass"
    assert result["activation_plan"]["metadata"]["selected_playbook_ids"] == ["consumer_electronics"]
    assert result["activation_plan"]["metadata"]["industry_schema"] == "consumer_electronics"
    assert "product_technology_analyst" in result["activation_plan"]["activate_agents"]
    assert "company_product_evidence_graph" in result["activation_plan"]["allowed_source_families"]
    assert "sell_through_without_tracker" in result["activation_plan"]["metadata"]["playbook_policy"]["forbidden_claims"]


def test_route_activation_from_env_returns_none_for_deterministic_default() -> None:
    assert route_activation_from_env({}) is None
    assert route_activation_from_env({"SEC_AGENT_MULTI_AGENT_LEAD_ROUTER": "deterministic"}) is None


def test_route_activation_from_env_builds_llm_route_with_non_secret_profile_values() -> None:
    request = _case("MSFT capex only.", "deterministic_lookup", ["MSFT"], ["MSFT"])
    plan = route_multi_agent_activation(request)["activation_plan"]
    fake = _FakeChat([json.dumps(plan)])
    route = route_activation_from_env(
        {
            "SEC_AGENT_MULTI_AGENT_LEAD_ROUTER": "llm",
            "LLM_BACKEND": "unit",
            "BASE_URL": "http://unit.test",
            "CHAT_COMPLETIONS_PATH": "/chat/completions",
            "MODEL_NAME": "unit-model",
            "API_KEY_ENV": "UNIT_API_KEY",
            "RESEARCH_LEAD_MAX_REPAIR_ATTEMPTS": "1",
        },
        call_chat_completion=fake,
    )

    assert route is not None
    result = route({"user_query": request["prompt"], "query_contract": request})

    assert result["status"] == "pass"
    assert fake.calls[0]["api_key_env"] == "UNIT_API_KEY"
    assert fake.calls[0]["model"] == "unit-model"


def test_research_lead_llm_config_from_env_parses_feature_profile() -> None:
    config = research_lead_llm_config_from_env(
        {
            "LLM_BACKEND": "deepseek",
            "BASE_URL": "https://api.deepseek.com",
            "MODEL_NAME": "deepseek-v4-pro",
            "API_KEY_ENV": "DEEPSEEK_API_KEY",
            "RESEARCH_LEAD_MAX_TOKENS": "900",
            "RESEARCH_LEAD_TIMEOUT_S": "30",
            "RESEARCH_LEAD_ALLOW_DETERMINISTIC_FALLBACK": "true",
        }
    )

    assert config.max_tokens == 900
    assert config.timeout_s == 30
    assert config.allow_deterministic_fallback is True


class _FakeChat:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        response = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        if isinstance(response, dict):
            content = str(response.get("content") or "")
            tool_calls = response.get("tool_calls") or []
        else:
            content = str(response)
            tool_calls = []
        return {
            "status": "ok",
            "provider": kwargs["llm_backend"],
            "model": kwargs["model"],
            "role": kwargs["role"],
            "profile": kwargs["profile"],
            "content": content,
            "message": {"content": content, "tool_calls": tool_calls},
            "tool_calls": tool_calls,
            "finish_reason": "stop",
            "latency_ms": 1,
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
            "cost_estimate": None,
            "failure_reason": "",
            "trace_tags": kwargs.get("trace_tags") or {},
            "raw_response": {},
        }


def _config() -> ResearchLeadLLMConfig:
    return ResearchLeadLLMConfig(
        llm_backend="unit",
        base_url="http://unit.test",
        chat_completions_path="/chat/completions",
        model="unit-model",
        api_key_env="UNIT_API_KEY",
    )


def _case(prompt: str, mode: str, focus: list[str], scope: list[str]) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "focus_tickers": focus,
        "search_scope_tickers": scope,
        "context": {"execution_mode": mode},
    }


def _query_contract(tickers: list[str]) -> dict[str, Any]:
    return {
        "focus_tickers": tickers,
        "search_scope_tickers": tickers,
        "years": [2026],
        "filing_types": ["10-Q", "8-K"],
        "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
        "metric_families": ["margin", "capex"],
    }


def _evidence_plan(tickers: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
        "requirements": [
            {
                "requirement_id": "req_margins",
                "task_id": "fundamental",
                "question": "Need reported margin evidence.",
                "tickers": tickers,
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["margin"],
                "period_roles": ["QTD", "YTD"],
                "evidence_routes": ["ledger_first", "filing_text"],
            }
        ],
    }


def _mixed_route_evidence_plan(tickers: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
        "requirements": [
            {
                "requirement_id": "req_exact",
                "task_id": "reported_fundamentals",
                "question": "Need exact reported revenue and margin evidence.",
                "priority": "primary",
                "tickers": tickers,
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["revenue", "gross_margin"],
                "evidence_routes": ["ledger_first"],
                "route_selection_reason": "Exact values require the low-cost ledger authority first.",
                "route_cost_tier": "low",
                "route_selection_policy": "cost_and_query_type_aware_v0_1",
            },
            {
                "requirement_id": "req_semantic",
                "task_id": "semantic_theme_recall",
                "question": "Need semantic supplement for hard-to-keyword filing themes.",
                "priority": "supporting",
                "tickers": tickers,
                "years": [2026],
                "filing_types": ["10-Q", "10-K"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["capex"],
                "evidence_routes": ["milvus_semantic"],
                "coverage_requirements": {"vector_kinds": ["paraphrase_context"]},
                "route_selection_reason": "Use Milvus as a typed SEC semantic supplement after exact/text routes.",
                "route_cost_tier": "high",
                "route_selection_policy": "cost_and_query_type_aware_v0_1",
            },
            {
                "requirement_id": "req_market",
                "task_id": "market_reaction",
                "question": "Need market valuation and reaction context.",
                "priority": "supporting",
                "tickers": tickers,
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["market_snapshot"],
                "metric_families": ["valuation"],
                "evidence_routes": ["market_snapshot"],
                "market_fields": ["return_3m", "ev_sales_ttm"],
                "route_selection_reason": "Market and valuation claims require stamped market snapshot context.",
                "route_cost_tier": "medium",
                "route_selection_policy": "cost_and_query_type_aware_v0_1",
            },
            {
                "requirement_id": "req_industry",
                "task_id": "industry_context",
                "question": "Need industry power-demand context.",
                "priority": "supporting",
                "tickers": tickers,
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["industry_snapshot"],
                "metric_families": ["power_demand"],
                "evidence_routes": ["industry_snapshot"],
                "route_selection_reason": "Industry context is needed for demand environment but cannot prove company facts.",
                "route_cost_tier": "medium",
                "route_selection_policy": "cost_and_query_type_aware_v0_1",
            },
        ],
    }
