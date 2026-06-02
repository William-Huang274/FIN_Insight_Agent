from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from sec_agent.agent_contracts import SCHEMA_VERSION as ACTIVATION_PLAN_SCHEMA_VERSION
from sec_agent.agent_contracts import validate_agent_activation_plan
from sec_agent.agent_registry import agent_registry_by_id, allowed_source_families, known_agent_ids
from sec_agent.tool_call_ledger import LoopBudget


ROUTER_SCHEMA_VERSION = "sec_agent_multi_agent_router_v0.1"
ROUTER_SOURCE = "deterministic_research_lead_mock_v0.1"

SPECIALIST_AGENT_IDS = {
    "fundamental_analyst",
    "industry_supply_chain_analyst",
    "market_valuation_analyst",
    "risk_counterevidence_analyst",
    "judgment_plan_aggregator",
}

EVIDENCE_OPERATOR_AGENT_IDS = {
    "sec_operator",
    "eight_k_operator",
    "market_operator",
    "industry_operator",
}

ALL_ROUTABLE_AGENT_IDS = tuple(sorted(known_agent_ids()))


@dataclass
class MultiAgentRouteRequest:
    user_query: str
    focus_tickers: list[str] = field(default_factory=list)
    search_scope_tickers: list[str] = field(default_factory=list)
    source_inventory: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MultiAgentRouteRequest":
        return cls(
            user_query=str(payload.get("user_query") or payload.get("prompt") or ""),
            focus_tickers=_unique_upper(payload.get("focus_tickers")),
            search_scope_tickers=_unique_upper(payload.get("search_scope_tickers")),
            source_inventory=dict(payload.get("source_inventory") or {}),
            context=dict(payload.get("context") or {}),
        )


def route_multi_agent_activation(
    request: MultiAgentRouteRequest | Mapping[str, Any] | str,
    *,
    budget: LoopBudget | None = None,
) -> dict[str, Any]:
    route_request = _coerce_request(request)
    loop_budget = budget or LoopBudget()
    mode = _execution_mode(route_request)
    focus_tickers = route_request.focus_tickers or _extract_tickers(route_request.user_query)
    search_scope_tickers = route_request.search_scope_tickers or focus_tickers
    plan = _activation_plan_for_mode(
        mode,
        route_request,
        focus_tickers=focus_tickers,
        search_scope_tickers=search_scope_tickers,
        budget=loop_budget,
    )
    validation = validate_agent_activation_plan(
        plan,
        known_agent_ids=known_agent_ids(),
        allowed_source_families=allowed_source_families(),
        agent_registry=agent_registry_by_id(),
        global_limits={
            "max_tool_calls_total": loop_budget.max_tool_calls_total,
            "max_second_pass_rounds": loop_budget.max_second_pass_rounds,
            "max_repair_rounds": loop_budget.max_repair_rounds,
        },
    )
    return {
        "schema_version": ROUTER_SCHEMA_VERSION,
        "source": ROUTER_SOURCE,
        "activation_plan": validation["plan"],
        "validation": validation,
        "routing_trace": {
            "mode": mode,
            "heuristics": _heuristic_trace(route_request, mode),
            "focus_tickers": focus_tickers,
            "search_scope_tickers": search_scope_tickers,
        },
        "loop_budget": loop_budget.to_dict(),
    }


def _coerce_request(request: MultiAgentRouteRequest | Mapping[str, Any] | str) -> MultiAgentRouteRequest:
    if isinstance(request, MultiAgentRouteRequest):
        return request
    if isinstance(request, Mapping):
        return MultiAgentRouteRequest.from_dict(request)
    return MultiAgentRouteRequest(user_query=str(request or ""))


def _activation_plan_for_mode(
    mode: str,
    request: MultiAgentRouteRequest,
    *,
    focus_tickers: list[str],
    search_scope_tickers: list[str],
    budget: LoopBudget,
) -> dict[str, Any]:
    if mode == "deterministic_lookup":
        return _deterministic_lookup_plan(request, focus_tickers, search_scope_tickers, budget)
    if mode == "focused_answer":
        return _focused_answer_plan(request, focus_tickers, search_scope_tickers, budget)
    if mode == "standard_memo":
        return _standard_memo_plan(request, focus_tickers, search_scope_tickers, budget)
    return _deep_research_plan(request, focus_tickers, search_scope_tickers, budget)


def _deterministic_lookup_plan(
    request: MultiAgentRouteRequest,
    focus_tickers: list[str],
    search_scope_tickers: list[str],
    budget: LoopBudget,
) -> dict[str, Any]:
    run_artifact = _run_artifact_intent(request)
    active = ["coverage_reflection", "renderer"] if run_artifact else ["sec_operator", "renderer"]
    source_families = ["run_artifact"] if run_artifact else ["primary_sec_filing"]
    return _plan(
        execution_mode="deterministic_lookup",
        activate_agents=active,
        skip_reason="Deterministic lookup does not need research planning, specialist analysis, or memo synthesis.",
        allowed_source_families=source_families,
        model_policy_hint={"renderer": "none"},
        max_tool_calls_total=min(2, budget.max_tool_calls_total),
        max_second_pass_rounds=0,
        max_repair_rounds=0,
        scope_mode="focused_peer",
        focus_tickers=focus_tickers,
        search_scope_tickers=search_scope_tickers,
        reasoning_summary="Single lookup or run-artifact inspection route.",
    )


def _focused_answer_plan(
    request: MultiAgentRouteRequest,
    focus_tickers: list[str],
    search_scope_tickers: list[str],
    budget: LoopBudget,
) -> dict[str, Any]:
    active = ["research_lead", "sec_operator", "coverage_reflection", "memo_writer", "verifier", "renderer"]
    if _management_commentary_intent(request) or _source_family_requested(request, "company_authored_unaudited_sec_filing"):
        active.insert(2, "eight_k_operator")
    if _source_family_requested(request, "market_snapshot"):
        active.insert(3 if "eight_k_operator" in active else 2, "market_operator")
    allowed_sources = ["primary_sec_filing", "company_authored_unaudited_sec_filing"]
    if "market_operator" in active:
        allowed_sources.append("market_snapshot")
    return _plan(
        execution_mode="focused_answer",
        activate_agents=active,
        skip_reason="Focused answer stays inside the requested company scope and does not need universe expansion or specialist map-reduce.",
        allowed_source_families=allowed_sources,
        model_policy_hint={"research_lead": "balanced", "memo_writer": "strong", "verifier": "strong", "renderer": "none"},
        max_tool_calls_total=min(8 if "market_operator" in active else 6, budget.max_tool_calls_total),
        max_second_pass_rounds=min(1, budget.max_second_pass_rounds),
        max_repair_rounds=min(1, budget.max_repair_rounds),
        scope_mode="focused_peer",
        focus_tickers=focus_tickers,
        search_scope_tickers=search_scope_tickers or focus_tickers,
        reasoning_summary="Focused company-level research answer.",
    )


def _standard_memo_plan(
    request: MultiAgentRouteRequest,
    focus_tickers: list[str],
    search_scope_tickers: list[str],
    budget: LoopBudget,
) -> dict[str, Any]:
    active = [
        "research_lead",
        "sec_operator",
        "coverage_reflection",
        "fundamental_analyst",
        "judgment_plan_aggregator",
        "memo_writer",
        "verifier",
        "renderer",
    ]
    if _management_commentary_intent(request):
        active.insert(2, "eight_k_operator")
    if _market_or_valuation_intent(request) or _source_family_requested(request, "market_snapshot"):
        active.insert(3 if "eight_k_operator" in active else 2, "market_operator")
        active.insert(active.index("judgment_plan_aggregator"), "market_valuation_analyst")
    if _industry_context_intent(request) or _source_family_requested(request, "industry_snapshot"):
        active.insert(active.index("coverage_reflection"), "industry_operator")
        active.insert(active.index("judgment_plan_aggregator"), "industry_supply_chain_analyst")
    if _risk_or_counterevidence_intent(request):
        active.insert(active.index("judgment_plan_aggregator"), "risk_counterevidence_analyst")
    scope_tickers = search_scope_tickers or focus_tickers
    allowed_sources = ["primary_sec_filing", "company_authored_unaudited_sec_filing"]
    if "market_operator" in active or "market_valuation_analyst" in active:
        allowed_sources.append("market_snapshot")
    if "industry_operator" in active or "industry_supply_chain_analyst" in active:
        allowed_sources.append("industry_snapshot")
    return _plan(
        execution_mode="standard_memo",
        activate_agents=active,
        skip_reason="Cost-aware standard memo activates only the requested specialist lenses and keeps relationship expansion off.",
        allowed_source_families=allowed_sources,
        model_policy_hint={
            "research_lead": "balanced",
            "fundamental_analyst": "balanced",
            **({"industry_supply_chain_analyst": "balanced"} if "industry_supply_chain_analyst" in active else {}),
            **({"market_valuation_analyst": "balanced"} if "market_valuation_analyst" in active else {}),
            **({"risk_counterevidence_analyst": "balanced"} if "risk_counterevidence_analyst" in active else {}),
            "memo_writer": "strong",
            "verifier": "strong",
            "renderer": "none",
        },
        max_tool_calls_total=min(10, budget.max_tool_calls_total),
        max_second_pass_rounds=min(1, budget.max_second_pass_rounds),
        max_repair_rounds=min(1, budget.max_repair_rounds),
        scope_mode="sector_representative" if len(scope_tickers) > len(focus_tickers or []) else "focused_peer",
        focus_tickers=focus_tickers,
        search_scope_tickers=scope_tickers,
        reasoning_summary="Peer or market-aware standard memo route.",
    )


def _deep_research_plan(
    request: MultiAgentRouteRequest,
    focus_tickers: list[str],
    search_scope_tickers: list[str],
    budget: LoopBudget,
) -> dict[str, Any]:
    active = [
        "research_lead",
        "universe_relationship",
        "sec_operator",
        "eight_k_operator",
        "industry_operator",
        "coverage_reflection",
        "fundamental_analyst",
        "industry_supply_chain_analyst",
        "judgment_plan_aggregator",
        "memo_writer",
        "verifier",
        "renderer",
    ]
    if _market_or_valuation_intent(request) or _source_family_requested(request, "market_snapshot"):
        active.insert(active.index("industry_operator"), "market_operator")
        active.insert(active.index("judgment_plan_aggregator"), "market_valuation_analyst")
    if _risk_or_counterevidence_intent(request):
        active.insert(active.index("judgment_plan_aggregator"), "risk_counterevidence_analyst")
    scope_tickers = search_scope_tickers or focus_tickers
    return _plan(
        execution_mode="deep_research",
        activate_agents=active,
        skip_reason="Cost-aware deep research keeps relationship and industry primary, while market/risk lenses run only when requested or sourced.",
        allowed_source_families=[
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            *(["market_snapshot"] if "market_operator" in active or "market_valuation_analyst" in active else []),
            "industry_snapshot",
            "relationship_graph",
        ],
        model_policy_hint={
            "research_lead": "strong",
            "universe_relationship": "balanced",
            "fundamental_analyst": "balanced",
            "industry_supply_chain_analyst": "balanced",
            **({"market_valuation_analyst": "balanced"} if "market_valuation_analyst" in active else {}),
            **({"risk_counterevidence_analyst": "strong"} if "risk_counterevidence_analyst" in active else {}),
            "memo_writer": "strong",
            "verifier": "strong",
            "renderer": "none",
        },
        max_tool_calls_total=min(12, budget.max_tool_calls_total),
        max_second_pass_rounds=min(2, budget.max_second_pass_rounds),
        max_repair_rounds=min(2, budget.max_repair_rounds),
        scope_mode="full_universe",
        focus_tickers=focus_tickers,
        search_scope_tickers=scope_tickers,
        relationship_scope_rationale="The query asks for supply-chain, sector, or cross-industry readthrough, so relationship expansion is required.",
        reasoning_summary="Relationship-aware deep research route.",
    )


def _plan(
    *,
    execution_mode: str,
    activate_agents: list[str],
    skip_reason: str,
    allowed_source_families: list[str],
    model_policy_hint: dict[str, str],
    max_tool_calls_total: int,
    max_second_pass_rounds: int,
    max_repair_rounds: int,
    scope_mode: str,
    focus_tickers: list[str],
    search_scope_tickers: list[str],
    reasoning_summary: str,
    relationship_scope_rationale: str = "",
) -> dict[str, Any]:
    active = _dedupe(activate_agents)
    priorities = _agent_priorities(execution_mode, active)
    skipped = [
        {"agent": agent_id, "reason": skip_reason}
        for agent_id in ALL_ROUTABLE_AGENT_IDS
        if agent_id not in active
    ]
    return {
        "schema_version": ACTIVATION_PLAN_SCHEMA_VERSION,
        "execution_mode": execution_mode,
        "activate_agents": active,
        "skip_agents": skipped,
        "allowed_source_families": allowed_source_families,
        "model_policy_hint": model_policy_hint,
        "agent_priorities": priorities,
        "max_tool_calls_total": max_tool_calls_total,
        "max_second_pass_rounds": max_second_pass_rounds,
        "max_repair_rounds": max_repair_rounds,
        "reasoning_summary": reasoning_summary,
        "scope_mode": scope_mode,
        "focus_tickers": focus_tickers,
        "search_scope_tickers": search_scope_tickers,
        "relationship_scope_rationale": relationship_scope_rationale,
        "metadata": {
            "cost_aware_activation": {
                "policy": "specialist_lenses_are_primary_supporting_or_conditional_v0_1",
                "active_agent_count": len(active),
                "active_specialist_count": len([agent for agent in active if agent in SPECIALIST_AGENT_IDS]),
                "agent_roles": [{"agent_id": agent, "priority": priorities.get(agent, "conditional")} for agent in active],
            }
        },
    }


def _agent_priorities(execution_mode: str, active: list[str]) -> dict[str, str]:
    primary_by_mode = {
        "deterministic_lookup": {"sec_operator", "coverage_reflection", "renderer"},
        "focused_answer": {"research_lead", "sec_operator", "eight_k_operator", "coverage_reflection", "memo_writer", "verifier", "renderer"},
        "standard_memo": {
            "research_lead",
            "sec_operator",
            "eight_k_operator",
            "market_operator",
            "coverage_reflection",
            "fundamental_analyst",
            "market_valuation_analyst",
            "risk_counterevidence_analyst",
            "judgment_plan_aggregator",
            "memo_writer",
            "verifier",
            "renderer",
        },
        "deep_research": {
            "research_lead",
            "universe_relationship",
            "sec_operator",
            "industry_operator",
            "coverage_reflection",
            "fundamental_analyst",
            "industry_supply_chain_analyst",
            "judgment_plan_aggregator",
            "memo_writer",
            "verifier",
            "renderer",
        },
    }
    primary = primary_by_mode.get(execution_mode, set())
    supporting = {
        "deep_research": {"eight_k_operator", "market_operator", "market_valuation_analyst", "risk_counterevidence_analyst"},
    }.get(execution_mode, set())
    priorities: dict[str, str] = {}
    for agent_id in active:
        if agent_id in primary:
            priorities[agent_id] = "primary"
        elif agent_id in supporting:
            priorities[agent_id] = "supporting"
        else:
            priorities[agent_id] = "conditional"
    return priorities


def _execution_mode(request: MultiAgentRouteRequest) -> str:
    context_mode = str(request.context.get("execution_mode") or "").strip()
    if context_mode in {"deterministic_lookup", "focused_answer", "standard_memo", "deep_research"}:
        return context_mode
    if _run_artifact_intent(request) or _deterministic_lookup_intent(request):
        return "deterministic_lookup"
    if _deep_research_intent(request):
        return "deep_research"
    if _standard_memo_intent(request):
        return "standard_memo"
    return "focused_answer"


def _heuristic_trace(request: MultiAgentRouteRequest, mode: str) -> dict[str, bool]:
    return {
        "forced_mode": str(request.context.get("execution_mode") or "") == mode,
        "run_artifact_intent": _run_artifact_intent(request),
        "deterministic_lookup_intent": _deterministic_lookup_intent(request),
        "management_commentary_intent": _management_commentary_intent(request),
        "standard_memo_intent": _standard_memo_intent(request),
        "deep_research_intent": _deep_research_intent(request),
    }


def _run_artifact_intent(request: MultiAgentRouteRequest) -> bool:
    text = _text(request)
    return bool(request.context.get("run_dir")) or (
        any(term in text for term in ("run artifact", "artifact", "coverage", "state", "inspect", "查看", "覆盖"))
        and any(term in text for term in ("run", "已有", "existing", "saved"))
    )


def _deterministic_lookup_intent(request: MultiAgentRouteRequest) -> bool:
    text = _text(request)
    lookup_terms = ("how much", "what was", "是多少", "多少", "lookup", "single metric", "capex")
    analysis_terms = ("why", "compare", "versus", "vs", "outlook", "memo", "分析", "比较", "前景", "估值", "产业链")
    return any(term in text for term in lookup_terms) and not any(term in text for term in analysis_terms)


def _management_commentary_intent(request: MultiAgentRouteRequest) -> bool:
    text = _text(request)
    return any(term in text for term in ("management", "commentary", "guidance", "demand", "解释", "管理层", "指引", "需求"))


def _standard_memo_intent(request: MultiAgentRouteRequest) -> bool:
    text = _text(request)
    ticker_count = len(request.search_scope_tickers or _extract_tickers(request.user_query))
    return ticker_count >= 2 or any(
        term in text
        for term in (
            "peer",
            "compare",
            "versus",
            " vs ",
            "market reaction",
            "valuation",
            "memo",
            "同业",
            "比较",
            "市场反应",
            "估值",
            "投研",
        )
    )


def _deep_research_intent(request: MultiAgentRouteRequest) -> bool:
    text = _text(request)
    return any(
        term in text
        for term in (
            "supply chain",
            "customer",
            "supplier",
            "readthrough",
            "cross-industry",
            "industry chain",
            "sector transmission",
            "sector-depth",
            "sector depth",
            "relationship graph",
            "relationship evidence",
            "产业链",
            "上下游",
            "供应链",
            "客户",
            "供应商",
            "跨行业",
            "传导",
            "关系图",
            "关系证据",
        )
    )


def _market_or_valuation_intent(request: MultiAgentRouteRequest) -> bool:
    text = _text_with_context(request)
    return any(
        term in text
        for term in (
            "market reaction",
            "valuation",
            "multiple",
            "share price",
            "stock price",
            "event window",
            "return",
            "市场反应",
            "估值",
            "倍数",
            "股价",
            "市值",
        )
    )


def _risk_or_counterevidence_intent(request: MultiAgentRouteRequest) -> bool:
    text = _text_with_context(request)
    return any(
        term in text
        for term in (
            "risk",
            "counterevidence",
            "counter-evidence",
            "downside",
            "bear case",
            "uncertainty",
            "conflict",
            "evidence gap",
            "evidence gaps",
            "gap",
            "margin pressure",
            "cash-flow pressure",
            "cash flow pressure",
            "pressure",
            "headwind",
            "stress",
            "credit risk",
            "risk-balanced",
            "risk balanced",
            "风险",
            "风险平衡",
            "反证",
            "下行",
            "不确定",
            "分歧",
            "证据缺口",
            "缺口",
            "压力",
            "逆风",
            "信用风险",
        )
    )


def _industry_context_intent(request: MultiAgentRouteRequest) -> bool:
    text = _text_with_context(request)
    return any(
        term in text
        for term in (
            "industry",
            "sector",
            "macro",
            "regulatory",
            "commodity",
            "power",
            "electric",
            "rates",
            "credit",
            "行业",
            "板块",
            "宏观",
            "监管",
            "商品",
            "电力",
            "利率",
            "信用",
        )
    )


def _source_family_requested(request: MultiAgentRouteRequest, source_family: str) -> bool:
    needle = str(source_family or "").strip()
    if not needle:
        return False
    payloads: list[Any] = [request.context, request.source_inventory]
    query_contract = request.context.get("query_contract") if isinstance(request.context, Mapping) else {}
    if isinstance(query_contract, Mapping):
        payloads.append(query_contract)
    for payload in payloads:
        if not isinstance(payload, Mapping):
            continue
        if needle in set(_unique_strings(payload.get("source_tiers") or payload.get("source_families") or payload.get("allowed_source_families"))):
            return True
        requirements = list(payload.get("evidence_requirements") or [])
        evidence_plan = payload.get("evidence_requirement_plan")
        if isinstance(evidence_plan, Mapping):
            requirements.extend(evidence_plan.get("requirements") or [])
        for req in requirements:
            if isinstance(req, Mapping) and needle in set(_unique_strings(req.get("source_tiers") or req.get("source_families") or req.get("evidence_routes"))):
                return True
    return needle in _text_with_context(request)


def _text_with_context(request: MultiAgentRouteRequest) -> str:
    return " ".join(
        [
            _text(request),
            str(request.context.get("task_type") or "").lower(),
            " ".join(_unique_strings(request.context.get("source_tiers") or request.context.get("source_families"))).lower(),
        ]
    )


def _extract_tickers(text: str) -> list[str]:
    known = {
        "AAPL",
        "AMD",
        "AMZN",
        "GOOGL",
        "JPM",
        "META",
        "MSFT",
        "NVDA",
        "TSLA",
    }
    return [ticker for ticker in re.findall(r"\b[A-Z]{2,5}\b", text or "") if ticker in known]


def _text(request: MultiAgentRouteRequest) -> str:
    return str(request.user_query or "").lower()


def _unique_upper(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").upper().strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _unique_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
