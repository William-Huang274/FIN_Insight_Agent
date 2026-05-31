from __future__ import annotations

import json
from typing import Any

from sec_agent.agent_registry import agent_registry_by_id
from sec_agent.multi_agent_router import route_multi_agent_activation
from sec_agent.research_lead_llm import (
    ROUTE_SOURCE,
    ResearchLeadLLMConfig,
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
    assert "risk_counterevidence_analyst" not in result["activation_plan"]["activate_agents"]


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
