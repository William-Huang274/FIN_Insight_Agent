from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from sec_agent.agent_contracts import SCHEMA_VERSION as ACTIVATION_PLAN_SCHEMA_VERSION
from sec_agent.agent_contracts import validate_agent_activation_plan
from sec_agent.agent_registry import agent_registry_by_id, allowed_source_families, known_agent_ids
from sec_agent.industry_playbooks import selected_playbook_policy
from sec_agent.tool_call_ledger import LoopBudget


ROUTER_SCHEMA_VERSION = "sec_agent_multi_agent_router_v0.1"
ROUTER_SOURCE = "deterministic_research_lead_mock_v0.1"

SPECIALIST_AGENT_IDS = {
    "fundamental_analyst",
    "product_technology_analyst",
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
    "web_evidence_operator",
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
        context = dict(payload.get("context") or {})
        for key in (
            "query_contract",
            "task_type",
            "source_tiers",
            "source_families",
            "metric_families",
            "required_dimension_ids",
            "eval_focus",
            "required_agents",
            "expected_specialist_agents",
            "expected_paid_specialist_agents",
            "expected_paid_specialist_priorities",
            "execution_mode",
            "expected_execution_mode",
        ):
            if key in payload and key not in context:
                context[key] = payload.get(key)
        return cls(
            user_query=str(payload.get("user_query") or payload.get("prompt") or ""),
            focus_tickers=_unique_upper(payload.get("focus_tickers")),
            search_scope_tickers=_unique_upper(payload.get("search_scope_tickers")),
            source_inventory=dict(payload.get("source_inventory") or {}),
            context=context,
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
    plan = _apply_playbook_policy(plan, route_request)
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
    market_intent = _market_or_valuation_intent(request)
    market_source_requested = _source_family_requested(request, "market_snapshot")
    if market_intent or market_source_requested:
        active.insert(3 if "eight_k_operator" in active else 2, "market_operator")
    if market_intent:
        active.insert(active.index("judgment_plan_aggregator"), "market_valuation_analyst")
    if _product_technology_intent(request) or any(
        _source_family_requested(request, family)
        for family in ("company_product_evidence_graph", "public_source_context", "live_public_web_context")
    ):
        active.insert(active.index("judgment_plan_aggregator"), "product_technology_analyst")
    if _industry_context_intent(request) or _source_family_requested(request, "industry_snapshot"):
        active.insert(active.index("coverage_reflection"), "industry_operator")
        active.insert(active.index("judgment_plan_aggregator"), "industry_supply_chain_analyst")
    if _risk_or_counterevidence_intent(request):
        active.insert(active.index("judgment_plan_aggregator"), "risk_counterevidence_analyst")
    scope_tickers = search_scope_tickers or focus_tickers
    allowed_sources = ["primary_sec_filing", "company_authored_unaudited_sec_filing"]
    if "market_operator" in active or "market_valuation_analyst" in active:
        allowed_sources.append("market_snapshot")
    if "product_technology_analyst" in active:
        allowed_sources.append("company_product_evidence_graph")
        if _source_family_requested(request, "public_source_context"):
            allowed_sources.append("public_source_context")
        if _source_family_requested(request, "live_public_web_context"):
            allowed_sources.append("live_public_web_context")
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
            **({"product_technology_analyst": "balanced"} if "product_technology_analyst" in active else {}),
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
        "risk_counterevidence_analyst",
        "judgment_plan_aggregator",
        "memo_writer",
        "verifier",
        "renderer",
    ]
    market_intent = _market_or_valuation_intent(request)
    market_source_requested = _source_family_requested(request, "market_snapshot")
    if market_intent or market_source_requested:
        active.insert(active.index("industry_operator"), "market_operator")
    if market_intent:
        active.insert(active.index("judgment_plan_aggregator"), "market_valuation_analyst")
    if _product_technology_intent(request) or any(
        _source_family_requested(request, family)
        for family in ("company_product_evidence_graph", "public_source_context", "live_public_web_context")
    ):
        active.insert(active.index("judgment_plan_aggregator"), "product_technology_analyst")
    scope_tickers = search_scope_tickers or focus_tickers
    return _plan(
        execution_mode="deep_research",
        activate_agents=active,
        skip_reason="Deep research keeps relationship, industry, and risk/counterevidence lenses active; market remains conditional on request or source availability.",
        allowed_source_families=[
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            *(["company_product_evidence_graph"] if "product_technology_analyst" in active else []),
            *(["public_source_context"] if "product_technology_analyst" in active and _source_family_requested(request, "public_source_context") else []),
            *(["live_public_web_context"] if "product_technology_analyst" in active and _source_family_requested(request, "live_public_web_context") else []),
            *(["market_snapshot"] if "market_operator" in active or "market_valuation_analyst" in active else []),
            "industry_snapshot",
            "relationship_graph",
        ],
        model_policy_hint={
            "research_lead": "strong",
            "universe_relationship": "balanced",
            "fundamental_analyst": "balanced",
            **({"product_technology_analyst": "balanced"} if "product_technology_analyst" in active else {}),
            "industry_supply_chain_analyst": "balanced",
            **({"market_valuation_analyst": "balanced"} if "market_valuation_analyst" in active else {}),
            "risk_counterevidence_analyst": "strong",
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


def _apply_playbook_policy(plan: Mapping[str, Any], request: MultiAgentRouteRequest) -> dict[str, Any]:
    normalized = dict(plan or {})
    mode = str(normalized.get("execution_mode") or "")
    if mode not in {"standard_memo", "deep_research"}:
        return normalized
    policy = selected_playbook_policy(request.source_inventory)
    if not policy:
        return normalized

    active = _dedupe([str(agent) for agent in normalized.get("activate_agents") or []])
    allowed_sources = _dedupe([str(source) for source in normalized.get("allowed_source_families") or []])
    source_policy = policy.get("source_family_policy") if isinstance(policy.get("source_family_policy"), Mapping) else {}
    default_sources = _dedupe([*list(policy.get("default_source_families") or []), *list(source_policy)])
    added_agents: list[str] = []
    added_sources: list[str] = []
    for family in default_sources:
        if family == "relationship_graph" and mode != "deep_research":
            continue
        if family == "live_public_web_context" and not _source_family_requested(request, "live_public_web_context"):
            continue
        if not _playbook_source_family_available(request, family):
            continue
        if family not in allowed_sources:
            allowed_sources.append(family)
            added_sources.append(family)
        for agent_id in _agents_for_playbook_source_family(family, policy, mode):
            if agent_id not in active:
                active = _insert_before(active, agent_id, "judgment_plan_aggregator")
                added_agents.append(agent_id)

    if "market_snapshot" in allowed_sources and "market_operator" not in active:
        active = _insert_before(active, "market_operator", "coverage_reflection")
        added_agents.append("market_operator")
    if "industry_snapshot" in allowed_sources and "industry_operator" not in active:
        active = _insert_before(active, "industry_operator", "coverage_reflection")
        added_agents.append("industry_operator")
    if "live_public_web_context" in allowed_sources and "web_evidence_operator" not in active:
        active = _insert_before(active, "web_evidence_operator", "coverage_reflection")
        added_agents.append("web_evidence_operator")

    priorities = dict(normalized.get("agent_priorities") or {})
    model_policy = dict(normalized.get("model_policy_hint") or {})
    routing = dict(policy.get("specialist_routing") or {})
    for agent_id in _dedupe(added_agents):
        if agent_id.endswith("_operator") or agent_id in EVIDENCE_OPERATOR_AGENT_IDS:
            priorities.setdefault(agent_id, "supporting")
            model_policy.setdefault(agent_id, "none")
        else:
            weight = str(routing.get(agent_id) or "").lower()
            priorities.setdefault(agent_id, "primary" if weight == "high" and mode == "deep_research" else "supporting")
            model_policy.setdefault(agent_id, "balanced")

    metadata = dict(normalized.get("metadata") or {})
    metadata["selected_playbook_ids"] = policy.get("selected_playbook_ids") or []
    schemas = [str(item) for item in policy.get("industry_schemas") or [] if str(item)]
    if schemas:
        metadata["industry_schema"] = schemas[0]
    metadata["playbook_policy"] = {
        "schema_version": policy.get("schema_version"),
        "selected_playbook_ids": policy.get("selected_playbook_ids") or [],
        "industry_schemas": policy.get("industry_schemas") or [],
        "default_source_families": policy.get("default_source_families") or [],
        "source_family_policy": source_policy,
        "forbidden_claims": policy.get("forbidden_claims") or [],
        "commercial_gap_policy": policy.get("commercial_gap_policy") or {},
        "web_scope_policy_ids": policy.get("web_scope_policy_ids") or [],
    }
    if added_sources:
        metadata["playbook_added_source_families"] = _dedupe(added_sources)
    if added_agents:
        metadata["playbook_added_agents"] = _dedupe(added_agents)
    if "live_public_web_context" in allowed_sources and policy.get("web_scope_policy_ids"):
        normalized["web_scope_policy_ids"] = _dedupe(
            [*list(normalized.get("web_scope_policy_ids") or []), *list(policy.get("web_scope_policy_ids") or [])]
        )

    normalized["activate_agents"] = active
    normalized["allowed_source_families"] = _dedupe(allowed_sources)
    normalized["agent_priorities"] = priorities
    normalized["model_policy_hint"] = model_policy
    normalized["skip_agents"] = [
        dict(item)
        for item in normalized.get("skip_agents") or []
        if isinstance(item, Mapping) and str(item.get("agent_id") or item.get("agent") or "") not in set(active)
    ]
    normalized["metadata"] = metadata
    return normalized


def _playbook_source_family_available(request: MultiAgentRouteRequest, family: str) -> bool:
    inventory = request.source_inventory if isinstance(request.source_inventory, Mapping) else {}
    availability = inventory.get("source_family_availability") if isinstance(inventory.get("source_family_availability"), Mapping) else {}
    item = availability.get(family) if isinstance(availability.get(family), Mapping) else {}
    if item:
        return item.get("available") is not False and str(item.get("status") or "") not in {"unavailable", "policy_not_loaded"}
    if family == "milvus_semantic":
        milvus = inventory.get("milvus_runtime") if isinstance(inventory.get("milvus_runtime"), Mapping) else {}
        if milvus:
            status = str(milvus.get("status") or "").strip()
            if status == "unavailable":
                return False
            if "available" in milvus:
                return bool(milvus.get("available"))
            return False
        if inventory:
            return False
    families = set(_unique_strings(inventory.get("available_source_families") or inventory.get("source_families")))
    if families:
        return family in families
    return family in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}


def _agents_for_playbook_source_family(family: str, policy: Mapping[str, Any], mode: str) -> list[str]:
    routing = {str(key): str(value).lower() for key, value in dict(policy.get("specialist_routing") or {}).items()}
    agents: list[str] = []
    if family in {"company_product_evidence_graph", "public_source_context", "live_public_web_context"}:
        if routing.get("product_technology_analyst") in {"high", "medium"}:
            agents.append("product_technology_analyst")
    if family == "market_snapshot" and routing.get("market_valuation_analyst") in {"high", "medium", "conditional"}:
        agents.append("market_valuation_analyst")
    if family in {"industry_snapshot", "relationship_graph"} and (
        mode == "deep_research" or routing.get("industry_supply_chain_analyst") == "high"
    ):
        agents.append("industry_supply_chain_analyst")
    if routing.get("risk_counterevidence_analyst") == "high":
        agents.append("risk_counterevidence_analyst")
    return _dedupe(agents)


def _insert_before(items: list[str], item: str, before: str) -> list[str]:
    values = [value for value in items if value != item]
    try:
        index = values.index(before)
    except ValueError:
        values.append(item)
    else:
        values.insert(index, item)
    return _dedupe(values)


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
            "product_technology_analyst",
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
            "product_technology_analyst",
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
    context_mode = str(request.context.get("execution_mode") or request.context.get("expected_execution_mode") or "").strip()
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
        "product_technology_intent": _product_technology_intent(request),
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
            "没有证据",
            "无证据",
            "未证实",
            "证据不足",
            "缺证",
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


def _product_technology_intent(request: MultiAgentRouteRequest) -> bool:
    text = _text_with_context(request)
    return any(
        term in text
        for term in (
            "product",
            "product revenue",
            "product kpi",
            "product spec",
            "spec",
            "sku",
            "platform",
            "architecture",
            "benchmark",
            "generation",
            "gpu",
            "accelerator",
            "ai server",
            "server oem",
            "data center gpu",
            "blackwell",
            "hopper",
            "h100",
            "h200",
            "b200",
            "gb200",
            "mi300",
            "tpu",
            "customer deployment",
            "deployment",
            "developer",
            "app download",
            "clinical",
            "trial",
            "regulatory",
            "openfda",
            "nhtsa",
            "public proxy",
            "commercial tracker",
            "产品",
            "产品线",
            "产品收入",
            "产品指标",
            "产品规格",
            "规格",
            "架构",
            "代际",
            "基准测试",
            "显卡",
            "加速卡",
            "加速器",
            "服务器",
            "客户部署",
            "部署",
            "竞品",
            "竞争产品",
            "主业",
            "临床",
            "监管",
            "公开代理",
            "商业tracker",
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
    query_contract = request.context.get("query_contract") if isinstance(request.context, Mapping) else {}
    return " ".join(
        [
            _text(request),
            str(request.context.get("task_type") or "").lower(),
            " ".join(_unique_strings(request.context.get("source_tiers") or request.context.get("source_families"))).lower(),
            " ".join(_unique_strings(request.context.get("metric_families"))).lower(),
            " ".join(_unique_strings(request.context.get("required_dimension_ids"))).lower(),
            " ".join(_unique_strings(request.context.get("eval_focus"))).lower(),
            " ".join(_unique_strings(query_contract.get("metric_families") if isinstance(query_contract, Mapping) else [])).lower(),
            " ".join(_unique_strings(query_contract.get("source_tiers") if isinstance(query_contract, Mapping) else [])).lower(),
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
