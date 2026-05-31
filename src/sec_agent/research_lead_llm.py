from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from sec_agent.agent_contracts import SCHEMA_VERSION as ACTIVATION_PLAN_SCHEMA_VERSION
from sec_agent.agent_contracts import validate_agent_activation_plan
from sec_agent.agent_registry import agent_registry_by_id, allowed_source_families, known_agent_ids, list_agent_registry
from sec_agent.llm_gateway import chat_completion
from sec_agent.multi_agent_runtime import build_multi_agent_evidence_requirement_plan, validate_multi_agent_evidence_requirement_plan
from sec_agent.multi_agent_router import MultiAgentRouteRequest, route_multi_agent_activation
from sec_agent.research_skills import research_skill_prompt
from sec_agent.tool_call_ledger import LoopBudget


ROUTE_SCHEMA_VERSION = "sec_agent_research_lead_llm_route_v0.1"
ROUTE_SOURCE = "research_lead_llm_v0.1"
LEAD_ROUTER_ENV = "SEC_AGENT_MULTI_AGENT_LEAD_ROUTER"

ChatCompletionFunc = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class ResearchLeadLLMConfig:
    llm_backend: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    chat_completions_path: str = "/chat/completions"
    model: str = "deepseek-v4-pro"
    api_key_env: str = "DEEPSEEK_API_KEY"
    temperature: float = 0.0
    max_tokens: int = 2400
    timeout_s: int = 180
    max_repair_attempts: int = 2
    allow_deterministic_fallback: bool = False
    require_evidence_requirements: bool = False


def research_lead_llm_config_from_env(env: Mapping[str, str] | None = None) -> ResearchLeadLLMConfig:
    values = dict(os.environ if env is None else env)
    return ResearchLeadLLMConfig(
        llm_backend=values.get("LLM_BACKEND", "deepseek"),
        base_url=values.get("BASE_URL", "https://api.deepseek.com"),
        chat_completions_path=values.get("CHAT_COMPLETIONS_PATH", "/chat/completions"),
        model=values.get("MODEL_NAME", "deepseek-v4-pro"),
        api_key_env=values.get("API_KEY_ENV", "DEEPSEEK_API_KEY"),
        temperature=_float_env(values.get("RESEARCH_LEAD_TEMPERATURE"), default=0.0),
        max_tokens=_int_env(values.get("RESEARCH_LEAD_MAX_TOKENS"), default=2400),
        timeout_s=_int_env(values.get("RESEARCH_LEAD_TIMEOUT_S"), default=180),
        max_repair_attempts=_int_env(values.get("RESEARCH_LEAD_MAX_REPAIR_ATTEMPTS"), default=2),
        allow_deterministic_fallback=_bool_env(values.get("RESEARCH_LEAD_ALLOW_DETERMINISTIC_FALLBACK")),
        require_evidence_requirements=_bool_env(values.get("RESEARCH_LEAD_REQUIRE_EVIDENCE_REQUIREMENTS")),
    )


def route_activation_from_env(
    env: Mapping[str, str] | None = None,
    *,
    call_chat_completion: ChatCompletionFunc = chat_completion,
) -> Callable[[Mapping[str, Any]], dict[str, Any]] | None:
    values = dict(os.environ if env is None else env)
    mode = str(values.get(LEAD_ROUTER_ENV) or "deterministic").strip().lower()
    if mode in {"", "deterministic", "mock", "off", "false", "0"}:
        return None
    if mode not in {"llm", "deepseek", "api"}:
        raise ValueError(f"unsupported {LEAD_ROUTER_ENV}: {mode}")
    config = research_lead_llm_config_from_env(values)

    def _route(state: Mapping[str, Any]) -> dict[str, Any]:
        contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
        return route_research_lead_activation_llm(
            {
                "prompt": state.get("user_query") or "",
                "focus_tickers": contract.get("focus_tickers") or state.get("selected_tickers") or [],
                "search_scope_tickers": contract.get("search_scope_tickers") or state.get("selected_tickers") or [],
                "source_inventory": state.get("project_inventory") or {},
                "context": {**dict(state.get("multi_agent_context") or {}), "query_contract": dict(contract)},
            },
            config=config,
            call_chat_completion=call_chat_completion,
        )

    return _route


def route_research_lead_activation_llm(
    request: MultiAgentRouteRequest | Mapping[str, Any] | str,
    *,
    config: ResearchLeadLLMConfig | None = None,
    budget: LoopBudget | None = None,
    call_chat_completion: ChatCompletionFunc = chat_completion,
) -> dict[str, Any]:
    route_request = _coerce_request(request)
    route_config = config or ResearchLeadLLMConfig()
    loop_budget = budget or LoopBudget()
    max_repair_attempts = max(0, min(int(route_config.max_repair_attempts), loop_budget.max_repair_rounds))

    model_calls: list[dict[str, Any]] = []
    last_failure: dict[str, Any] = {"type": "not_run"}
    last_validation: dict[str, Any] | None = None
    previous_content = ""

    for attempt_index in range(max_repair_attempts + 1):
        messages = _build_messages(
            route_request,
            loop_budget=loop_budget,
            prior_failure=last_failure if attempt_index else None,
            prior_content=previous_content if attempt_index else "",
        )
        llm_result = call_chat_completion(
            llm_backend=route_config.llm_backend,
            base_url=route_config.base_url,
            chat_completions_path=route_config.chat_completions_path,
            model=route_config.model,
            messages=messages,
            response_format={"type": "json_object"},
            api_key_env=route_config.api_key_env,
            temperature=route_config.temperature,
            max_tokens=route_config.max_tokens,
            timeout_s=route_config.timeout_s,
            stream=False,
            enable_thinking=False,
            role="research_lead",
            profile="balanced",
            trace_tags={
                "route_source": ROUTE_SOURCE,
                "repair_attempt": attempt_index,
                "schema_version": ACTIVATION_PLAN_SCHEMA_VERSION,
            },
        )
        model_calls.append(_model_call_summary(llm_result))
        previous_content = str(llm_result.get("content") or "")

        if llm_result.get("status") != "ok":
            last_failure = {
                "type": "provider_error",
                "status": llm_result.get("status"),
                "reason": str(llm_result.get("failure_reason") or ""),
            }
            break

        if llm_result.get("tool_calls"):
            last_failure = {
                "type": "direct_tool_call_forbidden",
                "detail": "Research Lead may request evidence needs only; direct tool calls are forbidden.",
            }
            continue

        parsed = extract_activation_plan_json(previous_content)
        if parsed is None:
            if str(llm_result.get("finish_reason") or "") == "length":
                last_failure = {
                    "type": "model_output_truncated",
                    "detail": (
                        "The model hit max_tokens before returning valid JSON. Return a much shorter "
                        "ResearchLeadOutput: <=5 evidence requirements, concise skip reasons, no prose."
                    ),
                }
                continue
            last_failure = {
                "type": "json_parse_failed",
                "detail": "No JSON object matching ResearchLeadOutput was found in model output.",
            }
            continue

        validation = _validate_research_lead_output(
            parsed,
            route_request,
            loop_budget,
            require_evidence_requirements=route_config.require_evidence_requirements,
        )
        last_validation = validation
        if validation["status"] == "pass":
            return {
                "schema_version": ROUTE_SCHEMA_VERSION,
                "source": ROUTE_SOURCE,
                "status": "pass",
                "activation_plan": validation["plan"],
                "evidence_requirement_plan": validation.get("evidence_requirement_plan") or {},
                "validation": validation,
                "routing_trace": {
                    "mode": validation["plan"].get("execution_mode"),
                    "attempt_count": len(model_calls),
                    "repair_attempts": attempt_index,
                    "fallback_used": False,
                    "evidence_requirements_source": validation.get("evidence_requirements_source") or "",
                    "input_focus_tickers": route_request.focus_tickers,
                    "input_search_scope_tickers": route_request.search_scope_tickers,
                },
                "model_diagnostics": _aggregate_model_calls(model_calls),
                "failure_reason": "",
                "loop_budget": loop_budget.to_dict(),
            }

        last_failure = {
            "type": "validation_failed",
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        }

    if route_config.allow_deterministic_fallback:
        fallback = route_multi_agent_activation(route_request, budget=loop_budget)
        return {
            "schema_version": ROUTE_SCHEMA_VERSION,
            "source": f"{ROUTE_SOURCE}+deterministic_fallback",
            "status": "fallback",
            "activation_plan": fallback["activation_plan"],
            "evidence_requirement_plan": {},
            "validation": fallback["validation"],
            "rejected_plan": (last_validation or {}).get("plan") or {},
            "routing_trace": {
                "attempt_count": len(model_calls),
                "repair_attempts": max(0, len(model_calls) - 1),
                "fallback_used": True,
                "fallback_source": fallback.get("source"),
            },
            "model_diagnostics": _aggregate_model_calls(model_calls),
            "failure_reason": _format_failure_reason(last_failure),
            "loop_budget": loop_budget.to_dict(),
        }

    return {
        "schema_version": ROUTE_SCHEMA_VERSION,
        "source": ROUTE_SOURCE,
        "status": "fail",
        "activation_plan": {},
        "evidence_requirement_plan": {},
        "validation": last_validation or _failed_validation(last_failure),
        "rejected_plan": (last_validation or {}).get("plan") or {},
        "routing_trace": {
            "attempt_count": len(model_calls),
            "repair_attempts": max(0, len(model_calls) - 1),
            "fallback_used": False,
        },
        "model_diagnostics": _aggregate_model_calls(model_calls),
        "failure_reason": _format_failure_reason(last_failure),
        "loop_budget": loop_budget.to_dict(),
    }


def extract_activation_plan_json(text: str) -> dict[str, Any] | None:
    for candidate in _json_candidates(str(text or "")):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _build_messages(
    request: MultiAgentRouteRequest,
    *,
    loop_budget: LoopBudget,
    prior_failure: Mapping[str, Any] | None,
    prior_content: str,
) -> list[dict[str, str]]:
    system = _system_prompt(loop_budget)
    user = _user_prompt(request)
    if prior_failure:
        user = (
            f"{user}\n\nRepair the previous output. It failed this diagnostic:\n"
            f"{json.dumps(_clean_for_prompt(prior_failure), ensure_ascii=False, sort_keys=True)}\n\n"
            "Previous output excerpt:\n"
            f"{_truncate(prior_content, 1800)}\n\n"
            "Return one corrected ResearchLeadOutput JSON object only."
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _system_prompt(loop_budget: LoopBudget) -> str:
    registry = [
        {
            "agent_id": entry["agent_id"],
            "role": entry["role"],
            "tool_permission": entry["tool_permission"],
            "allowed_tools": entry["allowed_tools"],
            "route_authority": entry["route_authority"],
            "source_families": entry["source_families"],
            "model_profile": entry["model_profile"],
        }
        for entry in list_agent_registry()
    ]
    schema_hint = {
        "schema_version": ACTIVATION_PLAN_SCHEMA_VERSION,
        "execution_mode": "deterministic_lookup | focused_answer | standard_memo | deep_research",
        "activate_agents": ["agent_id"],
        "skip_agents": [{"agent_id": "inactive_agent_id", "reason": "short reason"}],
        "allowed_source_families": sorted(allowed_source_families()),
        "model_policy_hint": {"agent_id": "none | fast | balanced | strong"},
        "agent_priorities": {"agent_id": "primary | supporting | conditional | low"},
        "max_tool_calls_total": loop_budget.max_tool_calls_total,
        "max_second_pass_rounds": loop_budget.max_second_pass_rounds,
        "max_repair_rounds": loop_budget.max_repair_rounds,
        "reasoning_summary": "short routing rationale, no chain-of-thought",
        "scope_mode": "focused_peer | sector_representative | full_universe",
        "focus_tickers": ["TICKER"],
        "search_scope_tickers": ["TICKER"],
        "relationship_scope_rationale": "",
        "metadata": {},
    }
    evidence_requirement_schema_hint = {
        "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
        "requirements": [
            {
                "requirement_id": "req_reported_fundamentals",
                "task_id": "fundamental",
                "question": "business evidence need, not a physical route",
                "priority": "primary | supporting",
                "tickers": ["TICKER"],
                "years": [2026],
                "filing_types": ["10-K | 10-Q | 8-K"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["revenue | margin | capex | cash_flow"],
                "period_roles": ["ANNUAL | QTD | YTD | TTM"],
                "evidence_routes": [
                    "ledger_first | filing_text | 8k_commentary | market_snapshot | industry_snapshot | relationship_graph | risk_text | run_artifact"
                ],
                "reason": "why this evidence is needed for the investment question",
            }
        ],
    }
    mode_rules = {
        "deterministic_lookup": (
            "Use for one exact metric or existing run inspection. For SEC lookup activate sec_operator and renderer; "
            "for run artifact inspection activate coverage_reflection and renderer. Do not activate memo_writer or specialists. "
            "Set max_tool_calls_total <= 2, max_second_pass_rounds = 0, and max_repair_rounds = 0. "
            "For run artifact inspection use allowed_source_families ['run_artifact'] and evidence_routes ['run_artifact']."
        ),
        "focused_answer": (
            "Use for one-company short analysis. Activate research_lead, sec_operator, coverage_reflection, "
            "memo_writer, verifier, renderer; add eight_k_operator when management commentary or guidance is requested. "
            "Set max_tool_calls_total <= 6, max_second_pass_rounds <= 1, and max_repair_rounds <= 1."
        ),
        "standard_memo": (
            "Use for peer comparison, memo, market reaction, valuation, or multi-company investment analysis. "
            "Activate sec_operator, eight_k_operator, market_operator, specialists, judgment_plan_aggregator, "
            "memo_writer, verifier, renderer; activate industry_operator only when macro, sector, commodity, "
            "or regulatory context is explicitly requested. Do not activate universe_relationship unless relationship "
            "expansion is explicitly requested. Do not activate industry_supply_chain_analyst unless supply chain, "
            "sector, industry, macro, regulatory, customer, supplier, or relationship readthrough is explicit. "
            "Market reaction and valuation alone use market_valuation_analyst, not industry_supply_chain_analyst. "
            "Set max_tool_calls_total <= 10, max_second_pass_rounds <= 1, "
            "and max_repair_rounds <= 1."
        ),
        "deep_research": (
            "Use only for supply chain, customers, suppliers, sector readthrough, cross-industry transmission, "
            "sector-depth packs, relationship_graph source requests, or full universe scope. "
            "Activate universe_relationship and include relationship_scope_rationale. "
            "Activate industry_supply_chain_analyst. Set max_tool_calls_total <= 12, max_second_pass_rounds <= 2, "
            "and max_repair_rounds <= 2. Keep evidence requirements compact; do not create one requirement per ticker."
        ),
    }
    return "\n\n".join(
        [
            "You are the Research Lead Agent for a SEC investment research multi-agent graph.",
            research_skill_prompt("research_lead", max_chars=3500),
            "Return exactly one JSON object. Do not wrap it in prose. Do not call tools.",
            (
                "The JSON object should contain activation_plan and evidence_requirement_plan. "
                "activation_plan must conform to AgentActivationPlan. evidence_requirement_plan must express "
                "business evidence needs only; do not include BM25 paths, DuckDB paths, index paths, raw file paths, "
                "or tool-call arguments. Include skip_agents for inactive registry agents. Keep output compact: "
                "at most 5 evidence requirements, one requirement per source family or business question, short skip reasons, "
                "and agent_priorities for every active analyst/operator so all-specialist routes are not treated as equal priority."
            ),
            f"AgentActivationPlan schema hint:\n{json.dumps(schema_hint, ensure_ascii=False, indent=2)}",
            f"EvidenceRequirementPlan schema hint:\n{json.dumps(evidence_requirement_schema_hint, ensure_ascii=False, indent=2)}",
            f"Static agent registry:\n{json.dumps(registry, ensure_ascii=False, indent=2)}",
            f"Mode rules:\n{json.dumps(mode_rules, ensure_ascii=False, indent=2)}",
            (
                "Budget limits: "
                f"max_tool_calls_total <= {loop_budget.max_tool_calls_total}; "
                f"max_second_pass_rounds <= {loop_budget.max_second_pass_rounds}; "
                f"max_repair_rounds <= {loop_budget.max_repair_rounds}."
            ),
        ]
    )


def _user_prompt(request: MultiAgentRouteRequest) -> str:
    payload = {
        "user_query": request.user_query,
        "focus_tickers": request.focus_tickers,
        "search_scope_tickers": request.search_scope_tickers,
        "source_inventory": request.source_inventory,
        "context": request.context,
    }
    return (
        "Classify this request and output the bounded activation plan. "
        "Use only supplied tickers and scope; do not add named facts from memory.\n\n"
        f"Request JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _validate_plan(plan: Mapping[str, Any], loop_budget: LoopBudget) -> dict[str, Any]:
    return validate_agent_activation_plan(
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


def _validate_research_lead_output(
    payload: Mapping[str, Any],
    route_request: MultiAgentRouteRequest,
    loop_budget: LoopBudget,
    *,
    require_evidence_requirements: bool,
) -> dict[str, Any]:
    activation_payload = _normalize_activation_for_source_contract(_activation_plan_payload(payload), route_request)
    validation = _validate_plan(activation_payload, loop_budget)
    if validation["status"] != "pass":
        return validation

    evidence_payload = _evidence_requirement_payload(payload)
    source = ""
    if evidence_payload:
        source = "llm_output"
    elif require_evidence_requirements:
        validation["status"] = "fail"
        validation.setdefault("errors", []).append({"type": "evidence_requirement_plan_required"})
        return validation
    else:
        context_contract = _context_query_contract(route_request)
        if context_contract:
            evidence_payload = {"requirements": context_contract.get("evidence_requirements") or []}
            source = "deterministic_compiler_fallback"

    if evidence_payload:
        if source == "llm_output":
            pre_validation = validate_multi_agent_evidence_requirement_plan(
                {
                    "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
                    "requirements": list(evidence_payload.get("requirements") or []),
                },
                activation_plan=validation["plan"],
            )
            if pre_validation["status"] != "pass":
                validation["status"] = "fail"
                validation["evidence_requirement_validation"] = pre_validation
                validation.setdefault("errors", []).append(
                    {
                        "type": "evidence_requirement_plan_validation_failed",
                        "errors": pre_validation.get("errors") or [],
                    }
                )
                return validation
        contract = _query_contract_for_evidence(route_request, validation["plan"], evidence_payload)
        evidence_plan = build_multi_agent_evidence_requirement_plan(
            contract,
            activation_plan=validation["plan"],
            case={"case_id": route_request.context.get("case_id") or "research_lead_llm", "prompt": route_request.user_query},
        )
        evidence_validation = evidence_plan.get("multi_agent_evidence_requirement_validation") or {}
        validation["evidence_requirement_plan"] = evidence_plan
        validation["evidence_requirement_validation"] = evidence_validation
        validation["evidence_requirements_source"] = source
        if evidence_validation.get("status") != "pass":
            issue = {
                "type": "evidence_requirement_plan_validation_failed",
                "errors": evidence_validation.get("errors") or [],
            }
            if source == "llm_output" or require_evidence_requirements:
                validation["status"] = "fail"
                validation.setdefault("errors", []).append(issue)
            else:
                validation.setdefault("warnings", []).append(issue)
    return validation


def _normalize_activation_for_source_contract(plan: Mapping[str, Any], route_request: MultiAgentRouteRequest) -> dict[str, Any]:
    normalized = dict(plan or {})
    if not _requires_sector_depth_relationship_route(route_request):
        return normalized

    context_sources = _context_source_families(route_request)
    active = _dedupe(
        [
            *[str(agent) for agent in normalized.get("activate_agents") or []],
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
            *_sector_depth_optional_agents(route_request),
        ]
    )
    allowed_sources = _dedupe(
        [
            *[str(source) for source in normalized.get("allowed_source_families") or []],
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "market_snapshot",
            "industry_snapshot",
            "relationship_graph",
            *context_sources,
        ]
    )
    normalized.update(
        {
            "execution_mode": "deep_research",
            "activate_agents": active,
            "allowed_source_families": allowed_sources,
            "max_tool_calls_total": max(12, _int_value(normalized.get("max_tool_calls_total"), default=0)),
            "max_second_pass_rounds": max(2, _int_value(normalized.get("max_second_pass_rounds"), default=0)),
            "max_repair_rounds": max(2, _int_value(normalized.get("max_repair_rounds"), default=0)),
            "scope_mode": normalized.get("scope_mode") or "sector_representative",
            "relationship_scope_rationale": normalized.get("relationship_scope_rationale")
            or "The request includes relationship_graph or sector-depth evidence, so universe expansion is required before specialist synthesis.",
        }
    )
    priorities = dict(normalized.get("agent_priorities") or {})
    for agent_id, priority in _sector_depth_agent_priorities(active).items():
        priorities[agent_id] = priority
    normalized["agent_priorities"] = priorities
    skipped = []
    active_set = set(active)
    for item in normalized.get("skip_agents") or []:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("agent_id") or "") not in active_set:
            skipped.append(dict(item))
    normalized["skip_agents"] = skipped
    return normalized


def _sector_depth_agent_priorities(active: list[str]) -> dict[str, str]:
    primary = {
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
    }
    supporting = {"eight_k_operator", "market_operator", "market_valuation_analyst", "risk_counterevidence_analyst"}
    result: dict[str, str] = {}
    for agent_id in active:
        if agent_id in primary:
            result[agent_id] = "primary"
        elif agent_id in supporting:
            result[agent_id] = "supporting"
        else:
            result[agent_id] = "conditional"
    return result


def _sector_depth_optional_agents(route_request: MultiAgentRouteRequest) -> list[str]:
    optional: list[str] = []
    if _route_request_mentions_market_or_valuation(route_request) or "market_snapshot" in set(_context_source_families(route_request)):
        optional.extend(["market_operator", "market_valuation_analyst"])
    if _route_request_mentions_risk_or_counterevidence(route_request):
        optional.append("risk_counterevidence_analyst")
    return optional


def _route_request_mentions_market_or_valuation(route_request: MultiAgentRouteRequest) -> bool:
    text = _route_request_text(route_request)
    return any(
        term in text
        for term in (
            "market reaction",
            "valuation",
            "multiple",
            "share price",
            "stock price",
            "市场反应",
            "估值",
            "倍数",
            "股价",
        )
    )


def _route_request_mentions_risk_or_counterevidence(route_request: MultiAgentRouteRequest) -> bool:
    text = _route_request_text(route_request)
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
            "风险",
            "反证",
            "下行",
            "不确定",
            "分歧",
        )
    )


def _route_request_text(route_request: MultiAgentRouteRequest) -> str:
    return " ".join(
        [
            str(route_request.user_query or ""),
            json.dumps(route_request.context, ensure_ascii=False, default=str),
        ]
    ).lower()


def _requires_sector_depth_relationship_route(route_request: MultiAgentRouteRequest) -> bool:
    sources = set(_context_source_families(route_request))
    text = " ".join(
        [
            route_request.user_query,
            json.dumps(route_request.context, ensure_ascii=False, default=str),
            json.dumps(route_request.source_inventory, ensure_ascii=False, default=str),
        ]
    ).lower()
    if "relationship_graph" in sources:
        return True
    if "industry_snapshot" in sources and any(
        marker in text
        for marker in (
            "sector-depth",
            "sector depth",
            "sector_depth",
            "sector pack",
            "industry pack",
            "产业链",
            "上下游",
            "传导",
        )
    ):
        return True
    return False


def _context_source_families(route_request: MultiAgentRouteRequest) -> list[str]:
    sources: list[str] = []
    contract = _context_query_contract(route_request)
    for key in ("source_families", "source_tiers", "allowed_source_families", "available_source_families"):
        sources.extend(_string_list(contract.get(key)))
        sources.extend(_string_list(route_request.context.get(key)))
    inventory = route_request.source_inventory if isinstance(route_request.source_inventory, Mapping) else {}
    for key in ("source_families", "source_tiers", "allowed_source_families", "available_source_families"):
        sources.extend(_string_list(inventory.get(key)))
    return _dedupe(sources)


def _activation_plan_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("activation_plan"), Mapping):
        return dict(payload["activation_plan"])  # type: ignore[index]
    return dict(payload)


def _evidence_requirement_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("evidence_requirement_plan"), Mapping):
        return dict(payload["evidence_requirement_plan"])  # type: ignore[index]
    if isinstance(payload.get("evidence_requirements"), list):
        return {"requirements": list(payload.get("evidence_requirements") or [])}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
    if isinstance(metadata.get("evidence_requirement_plan"), Mapping):
        return dict(metadata["evidence_requirement_plan"])  # type: ignore[index]
    if isinstance(metadata.get("evidence_requirements"), list):
        return {"requirements": list(metadata.get("evidence_requirements") or [])}
    return {}


def _query_contract_for_evidence(
    route_request: MultiAgentRouteRequest,
    activation_plan: Mapping[str, Any],
    evidence_payload: Mapping[str, Any],
) -> dict[str, Any]:
    contract = _context_query_contract(route_request)
    contract["focus_tickers"] = route_request.focus_tickers or contract.get("focus_tickers") or []
    contract["search_scope_tickers"] = route_request.search_scope_tickers or contract.get("search_scope_tickers") or contract["focus_tickers"]
    if not contract.get("source_tiers"):
        contract["source_tiers"] = list(activation_plan.get("allowed_source_families") or [])
    if isinstance(evidence_payload.get("requirements"), list) and evidence_payload.get("requirements"):
        contract["evidence_requirement_plan"] = {"requirements": list(evidence_payload.get("requirements") or [])}
    elif isinstance(evidence_payload, Mapping):
        contract["evidence_requirement_plan"] = dict(evidence_payload)
    return contract


def _context_query_contract(route_request: MultiAgentRouteRequest) -> dict[str, Any]:
    contract = route_request.context.get("query_contract") if isinstance(route_request.context.get("query_contract"), Mapping) else {}
    return dict(contract or {})


def _coerce_request(request: MultiAgentRouteRequest | Mapping[str, Any] | str) -> MultiAgentRouteRequest:
    if isinstance(request, MultiAgentRouteRequest):
        return request
    if isinstance(request, Mapping):
        return MultiAgentRouteRequest.from_dict(request)
    return MultiAgentRouteRequest(user_query=str(request or ""))


def _json_candidates(text: str) -> list[str]:
    stripped = text.strip()
    candidates: list[str] = []
    if stripped:
        candidates.append(stripped)
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fence:
        candidates.append(fence.group(1).strip())
    balanced = _first_balanced_json_object(stripped)
    if balanced:
        candidates.append(balanced)
    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            result.append(candidate)
            seen.add(candidate)
    return result


def _first_balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _model_call_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status"),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "finish_reason": result.get("finish_reason"),
        "latency_ms": result.get("latency_ms"),
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "total_tokens": result.get("total_tokens"),
        "failure_reason": _truncate(str(result.get("failure_reason") or ""), 500),
        "tool_call_count": len(result.get("tool_calls") or []),
        "transport_attempt_count": result.get("transport_attempt_count"),
        "transport_failures": result.get("transport_failures") or [],
    }


def _aggregate_model_calls(calls: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "call_count": len(calls),
        "provider": next((call.get("provider") for call in calls if call.get("provider")), ""),
        "model": next((call.get("model") for call in calls if call.get("model")), ""),
        "latency_ms": _sum_optional_int(calls, "latency_ms"),
        "input_tokens": _sum_optional_int(calls, "input_tokens"),
        "output_tokens": _sum_optional_int(calls, "output_tokens"),
        "total_tokens": _sum_optional_int(calls, "total_tokens"),
        "finish_reasons": [call.get("finish_reason") for call in calls],
        "calls": calls,
        "raw_response_saved": False,
    }


def _sum_optional_int(rows: list[dict[str, Any]], key: str) -> int | None:
    values = [row.get(key) for row in rows if row.get(key) is not None]
    if not values:
        return None
    return sum(int(value) for value in values)


def _failed_validation(failure: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": "fail",
        "schema_version": ACTIVATION_PLAN_SCHEMA_VERSION,
        "plan": {},
        "errors": [dict(failure)],
        "warnings": [],
    }


def _format_failure_reason(failure: Mapping[str, Any]) -> str:
    failure_type = str(failure.get("type") or "unknown_failure")
    if failure_type == "validation_failed":
        errors = failure.get("errors") or []
        return f"validation_failed: {json.dumps(errors, ensure_ascii=False)[:700]}"
    reason = failure.get("reason") or failure.get("detail") or ""
    return f"{failure_type}: {reason}".strip()


def _clean_for_prompt(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars)].rstrip() + "...[truncated]"


def _string_list(value: Any) -> list[str]:
    if value is None:
        items: list[Any] = []
    elif isinstance(value, str):
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


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _int_value(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _int_env(value: str | None, *, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _float_env(value: str | None, *, default: float) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def _bool_env(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}
