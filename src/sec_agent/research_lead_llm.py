from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from sec_agent.agent_contracts import SCHEMA_VERSION as ACTIVATION_PLAN_SCHEMA_VERSION
from sec_agent.agent_contracts import validate_agent_activation_plan
from sec_agent.agent_registry import agent_registry_by_id, allowed_source_families, known_agent_ids, list_agent_registry
from sec_agent.llm_gateway import chat_completion
from sec_agent.lead_supervision import build_research_objective_contract
from sec_agent.method_runtime import build_method_runtime_pack, compact_method_runtime_pack_for_prompt
from sec_agent.multi_agent_runtime import (
    ROUTE_OPERATOR_TOOL,
    ROUTE_SOURCE_FAMILY,
    build_multi_agent_evidence_requirement_plan,
    validate_multi_agent_evidence_requirement_plan,
)
from sec_agent.multi_agent_router import MultiAgentRouteRequest, _apply_playbook_policy, route_multi_agent_activation
from sec_agent.research_skills import research_skill_prompt
from sec_agent.tool_call_ledger import LoopBudget


ROUTE_SCHEMA_VERSION = "sec_agent_research_lead_llm_route_v0.1"
ROUTE_SOURCE = "research_lead_llm_v0.1"
LEAD_ROUTER_ENV = "SEC_AGENT_MULTI_AGENT_LEAD_ROUTER"
RESEARCH_LEAD_INPUT_PACK_FINGERPRINT_SCHEMA_VERSION = "sec_agent_research_lead_input_pack_fingerprint_v0_1"

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
    input_pack_fingerprint = _research_lead_input_pack_fingerprint(route_request, loop_budget=loop_budget)

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
                "input_pack_fingerprint": input_pack_fingerprint,
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
            "input_pack_fingerprint": input_pack_fingerprint,
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
        "input_pack_fingerprint": input_pack_fingerprint,
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
    evidence_requirement_schema_hint = {
        "preferred_shape": {
            "thesis_path": {
                "initial_view": "bounded initial analyst view, not final recommendation",
                "required_items": [
                    "product_architecture_competition",
                    "customer_deployment_adoption",
                    "supply_chain_readthrough",
                    "fundamental_financial_bridge",
                    "capital_market_price_in",
                    "risk_and_counterevidence",
                ],
                "evidence_role_plan": {"required_item": "what evidence role can support it and what it cannot infer"},
                "specialist_assignment": {"agent_id": "required item and why activated"},
                "missing_but_retrievable": ["public/local evidence that should trigger targeted repair"],
                "bounded_or_commercial_gap": ["evidence that cannot be filled with current public/free sources"],
                "writer_order": ["dimension order for final workpaper"],
            },
            "evidence_requirements": [
                {
                    "requirement_id": "req_reported_fundamentals",
                    "task_id": "fundamental",
                    "question": "business evidence need",
                    "priority": "primary | supporting",
                    "tickers": ["TICKER"],
                    "source_tiers": ["primary_sec_filing"],
                    "evidence_routes": ["ledger_first | filing_text | 8k_commentary | market_snapshot | industry_snapshot | relationship_graph"],
                    "route_cost_tier": "low | medium | high",
                    "route_selection_reason": "short reason",
                }
            ]
        },
        "allowed_requirement_fields": [
            "requirement_id",
            "task_id",
            "question",
            "priority",
            "tickers",
            "source_tiers",
            "evidence_routes",
            "metric_families",
            "period_roles",
            "route_cost_tier",
            "route_selection_reason",
        ],
        "legacy_full_shape_accepted_but_not_preferred": [
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
                    "ledger_first | filing_text | 8k_commentary | milvus_semantic | market_snapshot | industry_snapshot | relationship_graph | live_public_web_context | risk_text | run_artifact"
                ],
                "route_selection_reason": "why this route set is the narrowest sufficient source mix",
                "route_cost_tier": "low | medium | high",
                "route_selection_policy": "cost_and_query_type_aware_v0_1",
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
            "Activate product_technology_analyst only when product taxonomy, company-disclosed product KPI, public proxy, "
            "developer/app/clinical/regulatory context, or commercial tracker gaps are explicitly requested. "
            "Activate risk_counterevidence_analyst for risk-balanced investment memos, market reaction/valuation "
            "memos, evidence gaps, margin or cash-flow pressure, bear/downside/uncertainty/credit-risk/conflict "
            "questions; otherwise skip it with a short reason. "
            "Set max_tool_calls_total <= 10, max_second_pass_rounds <= 1, "
            "and max_repair_rounds <= 1."
        ),
        "deep_research": (
            "Use only for supply chain, customers, suppliers, sector readthrough, cross-industry transmission, "
            "sector-depth packs, relationship_graph source requests, or full universe scope. "
            "Activate universe_relationship and include relationship_scope_rationale. "
            "Activate industry_supply_chain_analyst. Add product_technology_analyst when product cycle, product KPI, "
            "public proxy, developer/app/clinical/regulatory context, or commercial tracker gaps are in scope. "
            "Set max_tool_calls_total <= 12, max_second_pass_rounds <= 2, "
            "and max_repair_rounds <= 2. Keep evidence requirements compact; do not create one requirement per ticker."
        ),
    }
    return "\n\n".join(
        [
            "You are the Research Lead Agent for a SEC investment research multi-agent graph.",
            research_skill_prompt("research_lead", max_chars=900),
            "Return exactly one JSON object. Do not wrap it in prose. Do not call tools.",
            (
                "Default output mode is evidence-overlay only. The JSON object should contain evidence_requirement_plan "
                "or, preferably, a top-level evidence_requirements array, and must omit activation_plan unless the supplied deterministic_activation_scaffold violates the user's "
                "scope or required execution mode. The runtime owns activation state, agent registry, skip defaults, and "
                "relationship edge completion. You own business questions, required evidence, and thesis-path intent. "
                "If an emergency activation_plan override is unavoidable, include only changed fields: execution_mode, "
                "activate_agents, allowed_source_families, agent_priorities, model_policy_hint, scope_mode, metadata. "
                "Do not enumerate default inactive registry agents in skip_agents. evidence_requirement_plan must express "
                "business evidence needs only; do not include BM25 paths, DuckDB paths, index paths, raw file paths, "
                "or tool-call arguments. Include skip_agents only inside an emergency activation_plan override and only for "
                "high-cost or expected analyst/operator agents that you deliberately prune because they are not needed. "
                "Keep output compact: "
                "at most 5 evidence requirements, one requirement per source family or business question, each question/reason <= 18 words, "
                "Every evidence requirement should include route_selection_reason and route_cost_tier. Choose the narrowest "
                "route set that can answer the business need; add high-cost semantic, industry, market, or relationship routes "
                "only when query intent requires them. Use playbook_candidates as routing context when supplied, and preserve "
                "forbidden_claims as boundaries rather than conclusions."
            ),
            f"EvidenceRequirementPlan schema hint:\n{_json_for_prompt(evidence_requirement_schema_hint)}",
            f"Route choice policy:\n{_json_for_prompt(_route_choice_policy_prompt())}",
            f"Mode rules:\n{_json_for_prompt(mode_rules)}",
            (
                "Budget limits: "
                f"max_tool_calls_total <= {loop_budget.max_tool_calls_total}; "
                f"max_second_pass_rounds <= {loop_budget.max_second_pass_rounds}; "
                f"max_repair_rounds <= {loop_budget.max_repair_rounds}."
            ),
        ]
    )


def _route_choice_policy_prompt() -> dict[str, Any]:
    return {
        "schema_version": "sec_agent_research_lead_route_choice_policy_v0.1",
        "default": "Use the cheapest route set that can prove the requested claim; do not add broad context routes by default.",
        "routes": {
            "ledger_first": {
                "cost_tier": "low",
                "use_when": "exact reported numeric facts, period-specific metrics, capex, cash flow, margin, RPO, banking ratios",
                "boundary": "primary exact-value authority; use before semantic/text routes for numeric claims",
            },
            "filing_text": {
                "cost_tier": "medium",
                "use_when": "10-K/10-Q management discussion, business explanation, segment commentary, text support for ledger facts",
                "boundary": "company filing text; not a substitute for exact ledger when exact values are requested",
            },
            "8k_commentary": {
                "cost_tier": "medium",
                "use_when": "earnings release, Exhibit 99, company-authored guidance or management commentary",
                "boundary": "company-authored unaudited SEC filing context",
            },
            "milvus_semantic": {
                "cost_tier": "high",
                "use_when": "typed SEC semantic recall for paraphrase, relationship-context, sector-depth, or hard-to-keyword filing text needs",
                "boundary": "semantic recall supplement only; never exact-value authority and never a replacement for ledger_first",
            },
            "market_snapshot": {
                "cost_tier": "medium",
                "use_when": "market reaction, valuation, relative return, drawdown, priced-in or divergence questions",
                "boundary": "context-only market/valuation evidence; cannot overwrite SEC fundamentals",
            },
            "industry_snapshot": {
                "cost_tier": "medium",
                "use_when": "macro, commodity, interest-rate, demand environment, regulatory or sector context",
                "boundary": "context-only industry evidence; cannot prove company-level reported facts",
            },
            "relationship_graph": {
                "cost_tier": "high",
                "use_when": "explicit supply-chain, customer/supplier, relationship, sector readthrough, cross-industry transmission questions",
                "boundary": "scope or hypothesis context only unless confirmed by cited company filings",
            },
            "risk_text": {
                "cost_tier": "medium",
                "use_when": "risk-factor text, counterevidence, downside, uncertainty, conflict or source-gap checks",
                "boundary": "risk/counterevidence support; cite bounded evidence only",
            },
            "run_artifact": {
                "cost_tier": "low",
                "use_when": "inspect existing run artifacts without new retrieval",
                "boundary": "artifact inspection only; do not claim new source evidence",
            },
        },
    }


def _compact_agent_registry_for_prompt() -> list[dict[str, Any]]:
    registry: list[dict[str, Any]] = []
    for entry in list_agent_registry():
        registry.append(
            {
                "agent_id": entry["agent_id"],
                "allowed_tools": entry["allowed_tools"],
                "source_families": entry["source_families"],
                "max_tool_calls": entry.get("max_tool_calls"),
            }
        )
    return registry


def _user_prompt(request: MultiAgentRouteRequest) -> str:
    deterministic_scaffold = route_multi_agent_activation(request).get("activation_plan") or {}
    method_runtime_pack = build_method_runtime_pack(
        request.context,
        user_query=request.user_query,
        focus_tickers=request.focus_tickers,
    )
    payload = {
        "user_query": request.user_query,
        "focus_tickers": request.focus_tickers,
        "search_scope_tickers": request.search_scope_tickers,
        "method_runtime_pack": compact_method_runtime_pack_for_prompt(method_runtime_pack),
        "deterministic_activation_scaffold": _compact_activation_scaffold_for_prompt(deterministic_scaffold),
        "source_inventory": _compact_source_inventory_for_prompt(request.source_inventory),
        "context": _compact_context_for_prompt(request.context),
    }
    return (
        "Classify this request and output a compact ResearchLeadOutput. "
        "Use deterministic_activation_scaffold unless you must change the route; do not repeat it just to confirm it. "
        "Use only supplied tickers and scope; do not add named facts from memory. "
        "For evidence_requirements, select routes by query type and cost: exact values use ledger_first first; "
        "market/valuation use market_snapshot; industry/macro use industry_snapshot; relationship readthrough uses relationship_graph; "
        "milvus_semantic is only typed SEC semantic recall supplement for paraphrase/relationship/sector-depth needs. "
        "Use method_runtime_pack as a hard planning contract: produce thesis-path intent, required-item coverage, "
        "evidence-role plan, specialist assignment rationale, missing-but-retrievable items, typed gaps, and writer order. "
        "Do not treat method_runtime_pack as evidence; it defines how to turn bounded evidence into analyst judgment.\n\n"
        f"Request JSON:\n{_json_for_prompt(payload)}"
    )


def _compact_activation_scaffold_for_prompt(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        key: value.get(key)
        for key in (
            "execution_mode",
            "activate_agents",
            "allowed_source_families",
            "agent_priorities",
            "model_policy_hint",
            "scope_mode",
            "focus_tickers",
            "search_scope_tickers",
            "max_tool_calls_total",
            "max_second_pass_rounds",
            "max_repair_rounds",
            "relationship_scope_rationale",
        )
        if value.get(key) not in (None, "", [], {})
    }


def _json_for_prompt(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _compact_source_inventory_for_prompt(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    allowed_keys = (
        "source_families",
        "source_tiers",
        "filing_types",
        "years",
        "fiscal_years",
        "ticker_count",
        "company_count",
        "available_tickers",
        "available_source_families",
        "source_family_availability",
        "source_family_authority",
        "source_boundaries",
        "playbook_registry",
        "playbook_candidates",
        "market_snapshot",
        "industry_snapshot",
        "product_evidence_graph",
        "public_source_context",
        "live_public_web_context",
        "milvus_runtime",
        "relationship_graph",
        "digest",
        "project_inventory_digest",
        "inventory_digest",
    )
    compact: dict[str, Any] = {}
    for key in allowed_keys:
        if key in value and value.get(key) not in (None, "", [], {}):
            compact[key] = _bounded_prompt_value(value.get(key), max_items=24, max_chars=600)
    source_counts = value.get("source_counts") if isinstance(value.get("source_counts"), Mapping) else {}
    if source_counts:
        compact["source_counts"] = {str(key): source_counts[key] for key in list(source_counts)[:12]}
    if not compact:
        compact["summary"] = _truncate(json.dumps(value, ensure_ascii=False, default=str), 900)
    return compact


def _compact_context_for_prompt(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    compact: dict[str, Any] = {}
    for key in (
        "execution_mode",
        "query_contract",
        "previous_turn_summary",
        "response_language",
        "evidence_operator_mode",
    ):
        if key in value and value.get(key) not in (None, "", [], {}):
            compact[key] = _bounded_prompt_value(value.get(key), max_items=24, max_chars=1200)
    return compact


def _bounded_prompt_value(value: Any, *, max_items: int, max_chars: int) -> Any:
    if isinstance(value, Mapping):
        clean = {}
        for key, item in list(value.items())[:max_items]:
            text_key = str(key)
            if "path" in text_key.lower() or "private" in text_key.lower():
                continue
            clean[text_key] = _bounded_prompt_value(item, max_items=max_items, max_chars=max_chars)
        return clean
    if isinstance(value, list):
        return [_bounded_prompt_value(item, max_items=max_items, max_chars=max_chars) for item in value[:max_items]]
    if isinstance(value, tuple):
        return [_bounded_prompt_value(item, max_items=max_items, max_chars=max_chars) for item in list(value)[:max_items]]
    if isinstance(value, str):
        return _truncate(value, max_chars)
    return value


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
    evidence_payload = _normalize_live_web_evidence_payload_for_policy(_evidence_requirement_payload(payload), route_request)
    evidence_payload = _normalize_milvus_evidence_payload_for_availability(evidence_payload, route_request)
    evidence_payload = _normalize_relationship_evidence_payload_for_scope(evidence_payload, route_request)
    evidence_payload = _normalize_required_role_evidence_payload(evidence_payload, route_request)
    activation_payload = _normalize_activation_for_source_contract(
        _activation_plan_payload(payload, route_request=route_request, loop_budget=loop_budget),
        route_request,
    )
    activation_payload = _align_activation_with_evidence_payload(activation_payload, evidence_payload)
    activation_payload = _normalize_relationship_activation_for_scope(activation_payload, route_request)
    activation_payload = _normalize_live_web_activation_for_policy(activation_payload, route_request)
    activation_payload = _normalize_milvus_activation_for_availability(activation_payload, route_request)
    activation_payload = _apply_playbook_policy(activation_payload, route_request)
    activation_payload = _normalize_milvus_activation_for_availability(activation_payload, route_request)
    activation_payload = _sanitize_activation_policy_maps(activation_payload)
    activation_payload = _normalize_plan_reflection_contract(activation_payload, route_request, evidence_payload)
    activation_payload = _normalize_milvus_activation_for_availability(activation_payload, route_request)
    activation_payload = _attach_supervising_analyst_contract(
        activation_payload,
        payload,
        route_request,
        evidence_payload,
    )
    validation = _validate_plan(activation_payload, loop_budget)
    if validation["status"] != "pass":
        return validation

    source = ""
    if evidence_payload:
        source = "llm_output"

    if evidence_payload and source == "llm_output":
        pre_validation = validate_multi_agent_evidence_requirement_plan(
            {
                "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
                "requirements": list(evidence_payload.get("requirements") or []),
            },
            activation_plan=validation["plan"],
        )
        if pre_validation["status"] != "pass":
            issue = {
                "type": "evidence_requirement_plan_validation_failed",
                "errors": pre_validation.get("errors") or [],
            }
            if require_evidence_requirements:
                validation["status"] = "fail"
                validation["evidence_requirement_validation"] = pre_validation
                validation.setdefault("errors", []).append(issue)
                return validation
            validation.setdefault("warnings", []).append(
                {
                    **issue,
                    "fallback": "deterministic_compiler_fallback",
                    "reason": "activation_plan_passed_but_llm_evidence_requirement_plan_failed_optional_validation",
                }
            )
            evidence_payload = {}
            source = ""

    if not evidence_payload:
        if require_evidence_requirements:
            validation["status"] = "fail"
            validation.setdefault("errors", []).append({"type": "evidence_requirement_plan_required"})
            return validation
        context_contract = _context_query_contract(route_request)
        if context_contract:
            evidence_payload = {"requirements": context_contract.get("evidence_requirements") or []}
            source = "deterministic_compiler_fallback"

    if evidence_payload:
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
                if require_evidence_requirements:
                    validation["status"] = "fail"
                    validation.setdefault("errors", []).append(issue)
                else:
                    fallback_payload = {"requirements": (_context_query_contract(route_request).get("evidence_requirements") or [])}
                    fallback_contract = _query_contract_for_evidence(route_request, validation["plan"], fallback_payload)
                    fallback_plan = build_multi_agent_evidence_requirement_plan(
                        fallback_contract,
                        activation_plan=validation["plan"],
                        case={
                            "case_id": route_request.context.get("case_id") or "research_lead_llm",
                            "prompt": route_request.user_query,
                        },
                    )
                    fallback_validation = fallback_plan.get("multi_agent_evidence_requirement_validation") or {}
                    validation["evidence_requirement_plan"] = fallback_plan
                    validation["evidence_requirement_validation"] = fallback_validation
                    validation["evidence_requirements_source"] = "deterministic_compiler_fallback"
                    validation.setdefault("warnings", []).append(
                        {
                            **issue,
                            "fallback": "deterministic_compiler_fallback",
                            "reason": "llm_evidence_requirement_plan_build_failed_optional_validation",
                        }
                    )
                    if fallback_validation.get("status") != "pass":
                        validation["status"] = "fail"
                        validation.setdefault("errors", []).append(
                            {
                                "type": "deterministic_evidence_requirement_plan_validation_failed",
                                "errors": fallback_validation.get("errors") or [],
                            }
                        )
            else:
                validation.setdefault("warnings", []).append(issue)
    return validation


SUPERVISING_ANALYST_CONTRACT_SCHEMA_VERSION = "fin_insight_research_lead_supervising_contract_v0_1"

REQUIRED_ITEM_DIMENSION_MAP = {
    "product_architecture_competition": "product_architecture",
    "customer_deployment_adoption": "customer_deployment",
    "supply_chain_readthrough": "industry_supply_chain",
    "fundamental_financial_bridge": "fundamentals",
    "capital_market_price_in": "capital_market_feedback",
    "risk_and_counterevidence": "counter_thesis_and_what_would_change",
}

REQUIRED_ITEM_SOURCE_FAMILIES = {
    "product_architecture_competition": ["company_product_evidence_graph", "public_source_context", "primary_sec_filing"],
    "customer_deployment_adoption": ["relationship_graph", "public_source_context", "company_authored_unaudited_sec_filing"],
    "supply_chain_readthrough": ["relationship_graph", "industry_snapshot", "public_source_context"],
    "fundamental_financial_bridge": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
    "capital_market_price_in": ["market_snapshot", "primary_sec_filing"],
    "risk_and_counterevidence": ["primary_sec_filing", "relationship_graph", "industry_snapshot", "market_snapshot"],
}

REQUIRED_ITEM_QUERY_MARKERS = {
    "product_architecture_competition": ("product", "architecture", "accelerator", "gpu", "tpu", "blackwell", "产品", "架构"),
    "customer_deployment_adoption": ("customer", "deployment", "adoption", "ordered", "configured", "客户", "部署", "订单"),
    "supply_chain_readthrough": ("supply", "chain", "read-through", "supplier", "bottleneck", "供应链", "传导", "瓶颈"),
    "fundamental_financial_bridge": ("margin", "cash flow", "working capital", "revenue", "backlog", "毛利", "现金流", "收入"),
    "capital_market_price_in": ("market", "valuation", "price", "capital", "expectation", "估值", "预期", "股价"),
    "risk_and_counterevidence": ("risk", "counter", "wrong", "uncertainty", "what would change", "风险", "反证", "推翻"),
}

REQUIRED_ITEM_REQUIREMENT_ID_MARKERS = {
    "product_architecture_competition": ("product", "architecture", "accelerator", "technical", "spec"),
    "customer_deployment_adoption": ("customer", "deployment", "adoption", "configured", "channel"),
    "supply_chain_readthrough": ("supply", "chain", "supplier", "readthrough", "read_through", "semicap", "foundry", "hbm", "cowos"),
    "fundamental_financial_bridge": ("fundamental", "financial", "margin", "cash", "working_capital", "dell_margin", "revenue_quality"),
    "capital_market_price_in": ("market", "price", "priced", "price_in", "valuation", "capital"),
    "risk_and_counterevidence": ("risk", "counter", "counterevidence", "downside", "what_would_change"),
}


def _attach_supervising_analyst_contract(
    activation_plan: Mapping[str, Any],
    payload: Mapping[str, Any],
    route_request: MultiAgentRouteRequest,
    evidence_payload: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = dict(activation_plan or {})
    method_pack = build_method_runtime_pack(
        route_request.context,
        user_query=route_request.user_query,
        focus_tickers=list(route_request.focus_tickers),
    )
    model_fields = _extract_supervising_analyst_fields(payload)
    compiled_fields = _compile_supervising_analyst_fields(
        route_request,
        activation_plan=normalized,
        evidence_payload=evidence_payload,
        method_pack=method_pack,
    )
    field_sources: dict[str, str] = {}
    for key, compiled_value in compiled_fields.items():
        model_value = model_fields.get(key)
        normalized_model_value, normalized_model_source = _normalize_supervising_model_field(
            key,
            model_value,
            compiled_value,
        )
        if _supervising_field_is_present(normalized_model_value):
            normalized[key] = normalized_model_value
            field_sources[key] = normalized_model_source
        elif not _supervising_field_is_present(normalized.get(key)):
            normalized[key] = compiled_value
            field_sources[key] = "deterministic_supervising_plan_compiler_v0_1"

    metadata = dict(normalized.get("metadata") or {})
    metadata["supervising_analyst_contract_schema_version"] = SUPERVISING_ANALYST_CONTRACT_SCHEMA_VERSION
    metadata["supervising_analyst_contract_policy"] = "research_lead_must_emit_or_compile_thesis_path_v0_1"
    metadata["supervising_analyst_field_sources"] = field_sources
    metadata["method_runtime_pack_status"] = method_pack.get("status") or ""
    metadata["method_runtime_lane"] = method_pack.get("lane") or ""
    normalized["metadata"] = metadata
    return normalized


def _extract_supervising_analyst_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    thesis_path = payload.get("thesis_path") if isinstance(payload.get("thesis_path"), Mapping) else {}
    for key in (
        "research_objective_contract",
        "thesis_path",
        "evidence_role_plan",
        "specialist_assignment",
        "missing_but_retrievable",
        "bounded_or_commercial_gap",
        "writer_order",
    ):
        if key in payload:
            fields[key] = payload.get(key)
        elif isinstance(thesis_path, Mapping) and key in thesis_path:
            fields[key] = thesis_path.get(key)
    if thesis_path and "thesis_path" not in fields:
        fields["thesis_path"] = dict(thesis_path)
    return fields


def _normalize_supervising_model_field(key: str, model_value: Any, compiled_value: Any) -> tuple[Any, str]:
    if not _supervising_field_is_present(model_value):
        return None, ""
    if key == "thesis_path":
        if not isinstance(model_value, Mapping):
            return None, ""
        compiled = dict(compiled_value or {}) if isinstance(compiled_value, Mapping) else {}
        result = dict(compiled)
        for text_key in ("initial_view", "primary_question"):
            text = str(model_value.get(text_key) or "").strip()
            if text:
                result[text_key] = text
        if _list_of_mapping(model_value.get("path_nodes")):
            result["path_nodes"] = _list_of_mapping(model_value.get("path_nodes"))
        if _list_of_mapping(model_value.get("required_items")):
            result["required_items"] = _list_of_mapping(model_value.get("required_items"))
        result["model_supplied_shape"] = _summarize_supervising_model_shape(model_value)
        result["source"] = "llm_output_normalized_with_deterministic_structure_v0_1"
        return result, "llm_output_normalized_with_deterministic_structure_v0_1"
    if key == "evidence_role_plan":
        compiled_rows = _list_of_mapping(compiled_value)
        normalized_rows = _normalize_evidence_role_plan_model_value(model_value, compiled_rows)
        if normalized_rows:
            return normalized_rows, "llm_output_normalized_with_deterministic_structure_v0_1"
        return None, ""
    if key == "specialist_assignment":
        if isinstance(model_value, Mapping):
            compiled_assignment = dict(compiled_value or {}) if isinstance(compiled_value, Mapping) else {}
            result = dict(compiled_assignment)
            for agent_id, value in model_value.items():
                agent = str(agent_id or "").strip()
                if not agent:
                    continue
                if isinstance(value, Mapping):
                    row = dict(result.get(agent) or {})
                    row.update(dict(value))
                    result[agent] = row
                else:
                    row = dict(result.get(agent) or {"agent_id": agent, "required_items": []})
                    row["model_assignment_reason"] = str(value or "").strip()
                    result[agent] = row
            return result, "llm_output_normalized_with_deterministic_structure_v0_1"
        return None, ""
    if key in {"missing_but_retrievable", "bounded_or_commercial_gap"}:
        rows = _normalize_gap_list_model_value(model_value, key=key)
        if rows:
            return rows, "llm_output_normalized_with_typed_rows_v0_1"
        return None, ""
    if key == "writer_order":
        order = _normalize_writer_order_model_value(model_value, compiled_value)
        if order:
            return order, "llm_output_normalized_with_dimension_order_v0_1"
        return None, ""
    if _supervising_field_is_present(model_value):
        return model_value, "llm_output"
    return None, ""


def _normalize_evidence_role_plan_model_value(model_value: Any, compiled_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    role_map: dict[str, Any] = {}
    if isinstance(model_value, Mapping):
        role_map = dict(model_value)
    elif isinstance(model_value, list):
        for item in model_value:
            if isinstance(item, Mapping) and "required_item" in item:
                role = str(item.get("required_item") or "").strip()
                if role:
                    role_map[role] = dict(item)
            elif isinstance(item, Mapping):
                for role, value in item.items():
                    role_map[str(role)] = value
    rows: list[dict[str, Any]] = []
    for compiled in compiled_rows:
        role = str(compiled.get("required_item") or "").strip()
        if not role:
            continue
        row = dict(compiled)
        model_role_value = role_map.get(role)
        if isinstance(model_role_value, Mapping):
            row.update(dict(model_role_value))
            row.setdefault("required_item", role)
        elif str(model_role_value or "").strip():
            row["model_evidence_role"] = str(model_role_value or "").strip()
            row["evidence_role"] = str(model_role_value or "").strip()
        row["model_shape_normalized"] = True
        rows.append(row)
    return rows


def _normalize_gap_list_model_value(model_value: Any, *, key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _list_value(model_value):
        if isinstance(item, Mapping):
            row = dict(item)
        else:
            text = str(item or "").strip()
            if not text:
                continue
            row = {
                "reason" if key == "missing_but_retrievable" else "boundary": text,
                "source": "llm_output_normalized_text_row",
            }
        if key == "missing_but_retrievable":
            row.setdefault("gap_attribution", "retrievable_gap_until_attempted")
        else:
            row.setdefault("gap_type", "bounded_or_commercial_gap")
        rows.append(row)
    return rows


def _normalize_writer_order_model_value(model_value: Any, compiled_value: Any) -> list[str]:
    compiled_order = _string_list(compiled_value)
    result: list[str] = []
    for item in _string_list(model_value):
        dimension = REQUIRED_ITEM_DIMENSION_MAP.get(item, item)
        if dimension not in result:
            result.append(dimension)
    if result and "opening_thesis" in compiled_order and "opening_thesis" not in result:
        result.insert(0, "opening_thesis")
    known_dimensions = set(compiled_order) | {"opening_thesis"} | set(REQUIRED_ITEM_DIMENSION_MAP.values())
    return [item for item in result if item in known_dimensions] or compiled_order


def _summarize_supervising_model_shape(model_value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "has_initial_view": bool(str(model_value.get("initial_view") or "").strip()),
        "required_items_type": type(model_value.get("required_items")).__name__,
        "path_nodes_count": len(_list_of_mapping(model_value.get("path_nodes"))),
        "has_nested_evidence_role_plan": isinstance(model_value.get("evidence_role_plan"), Mapping),
        "has_nested_specialist_assignment": isinstance(model_value.get("specialist_assignment"), Mapping),
    }


def _list_of_mapping(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _list_value(value):
        if isinstance(item, Mapping):
            rows.append(dict(item))
    return rows


def _compile_supervising_analyst_fields(
    route_request: MultiAgentRouteRequest,
    *,
    activation_plan: Mapping[str, Any],
    evidence_payload: Mapping[str, Any],
    method_pack: Mapping[str, Any],
) -> dict[str, Any]:
    contract = _context_query_contract(route_request)
    required_items = _supervising_required_items(route_request, method_pack, contract)
    dimensions = _supervising_writer_order(contract, required_items)
    evidence_requirements = [
        dict(item)
        for item in (evidence_payload.get("requirements") if isinstance(evidence_payload, Mapping) else []) or []
        if isinstance(item, Mapping)
    ]
    evidence_role_plan = [
        _compile_evidence_role_item(item, evidence_requirements=evidence_requirements)
        for item in required_items
    ]
    specialist_assignment = _compile_specialist_assignment(
        required_items,
        activation_plan=activation_plan,
        method_pack=method_pack,
    )
    research_objective_contract = build_research_objective_contract(
        query=str(route_request.user_query or ""),
        required_dimensions=dimensions,
        minimum_evidence_requirements={
            row["required_item"]: {
                "question": row.get("question") or "",
                "minimum_role": REQUIRED_ITEM_DIMENSION_MAP.get(str(row.get("required_item") or ""), ""),
            }
            for row in required_items
        },
        source_family_plan={
            "allowed_source_families": _dedupe(_string_list(activation_plan.get("allowed_source_families"))),
            "focus_tickers": list(route_request.focus_tickers),
            "search_scope_tickers": list(route_request.search_scope_tickers),
        },
        forbidden_claims=[
            "Do not infer SKU revenue, shipment, market share, backlog, customer order value, or margin quality from product existence, cloud capex, or deployment proxy alone.",
            "Do not treat relationship_graph or public_source_context as exact reported financial authority.",
        ],
        mandatory_second_pass_triggers=["retrievable_gap", "parser_gap", "evidence_role_uncovered"],
    )
    thesis_path = {
        "schema_version": "fin_insight_research_lead_thesis_path_v0_1",
        "thesis_path_id": _fingerprint_digest(
            {
                "query": route_request.user_query,
                "required_items": [row.get("required_item") for row in required_items],
                "focus_tickers": list(route_request.focus_tickers),
            }
        )[:32],
        "source": "deterministic_supervising_plan_compiler_v0_1",
        "initial_view": (
            "Form a bounded analyst thesis by linking product/architecture, customer deployment, "
            "supply-chain transmission, financial quality, capital-market price-in, and counterevidence."
        ),
        "primary_question": str(route_request.user_query or ""),
        "required_items": [dict(row) for row in required_items],
        "path_nodes": [
            {
                "required_item": row.get("required_item") or "",
                "dimension": REQUIRED_ITEM_DIMENSION_MAP.get(str(row.get("required_item") or ""), ""),
                "question": row.get("question") or "",
                "primary_agents": row.get("primary_agents") or [],
                "writer_role": row.get("writer_role") or "",
            }
            for row in required_items
        ],
        "writer_order": dimensions,
    }
    return {
        "research_objective_contract": research_objective_contract,
        "thesis_path": thesis_path,
        "evidence_role_plan": evidence_role_plan,
        "specialist_assignment": specialist_assignment,
        "missing_but_retrievable": _compile_missing_but_retrievable(required_items, evidence_role_plan),
        "bounded_or_commercial_gap": _compile_bounded_or_commercial_gap(route_request, required_items),
        "writer_order": dimensions,
    }


def _supervising_required_items(
    route_request: MultiAgentRouteRequest,
    method_pack: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    method_items = [
        dict(item)
        for item in method_pack.get("research_lead_required_items") or []
        if isinstance(item, Mapping)
    ]
    if not method_items:
        return []
    required_dimensions = set(_string_list(contract.get("required_dimensions")))
    if not required_dimensions:
        return method_items
    selected: list[dict[str, Any]] = []
    for item in method_items:
        item_id = str(item.get("required_item") or "")
        dimension = REQUIRED_ITEM_DIMENSION_MAP.get(item_id, "")
        if dimension in required_dimensions or item_id in required_dimensions:
            selected.append(item)
    return selected or method_items


def _supervising_writer_order(contract: Mapping[str, Any], required_items: list[Mapping[str, Any]]) -> list[str]:
    requested = _string_list(contract.get("required_dimensions"))
    if requested:
        return requested
    ordered = ["opening_thesis"]
    for item in required_items:
        dimension = REQUIRED_ITEM_DIMENSION_MAP.get(str(item.get("required_item") or ""), "")
        if dimension and dimension not in ordered:
            ordered.append(dimension)
    return ordered


def _compile_evidence_role_item(
    item: Mapping[str, Any],
    *,
    evidence_requirements: list[Mapping[str, Any]],
) -> dict[str, Any]:
    required_item = str(item.get("required_item") or "").strip()
    matched = [
        req
        for req in evidence_requirements
        if _requirement_matches_required_item(req, required_item)
    ]
    source_families = _dedupe(
        [
            *REQUIRED_ITEM_SOURCE_FAMILIES.get(required_item, []),
            *[
                source
                for req in matched
                for source in _string_list(req.get("source_families") or req.get("source_tiers") or req.get("source_family"))
            ],
        ]
    )
    routes = _dedupe(
        [
            route
            for req in matched
            for route in _string_list(req.get("evidence_routes") or req.get("retrieval_routes"))
        ]
    )
    return {
        "required_item": required_item,
        "dimension": REQUIRED_ITEM_DIMENSION_MAP.get(required_item, ""),
        "question": item.get("question") or "",
        "must_answer": _dedupe(
            [
                *_string_list(item.get("must_answer")),
                str(item.get("question") or "").strip(),
            ]
        ),
        "primary_agents": list(item.get("primary_agents") or []),
        "evidence_role": item.get("writer_role") or "",
        "required_source_families": source_families,
        "route_intents": routes,
        "matched_requirement_ids": [str(req.get("requirement_id") or "") for req in matched if str(req.get("requirement_id") or "")],
        "can_support": _can_support_for_required_item(required_item),
        "cannot_infer": _cannot_infer_for_required_item(required_item),
        "status": "planned" if matched else "planned_without_specific_requirement",
    }


def _compile_specialist_assignment(
    required_items: list[Mapping[str, Any]],
    *,
    activation_plan: Mapping[str, Any],
    method_pack: Mapping[str, Any],
) -> dict[str, Any]:
    active = set(_string_list(activation_plan.get("activate_agents")))
    rubrics = method_pack.get("specialist_task_rubric") if isinstance(method_pack.get("specialist_task_rubric"), Mapping) else {}
    assignments: dict[str, Any] = {}
    for item in required_items:
        item_id = str(item.get("required_item") or "").strip()
        for agent_id in _string_list(item.get("primary_agents")):
            row = assignments.setdefault(
                agent_id,
                {
                    "agent_id": agent_id,
                    "activation_state": "active" if agent_id in active else "inactive_or_deterministic_pack",
                    "required_items": [],
                    "rubric_present": isinstance(rubrics.get(agent_id), Mapping),
                    "reason": "",
                },
            )
            row["required_items"].append(item_id)
    for agent_id, row in assignments.items():
        row["required_items"] = _dedupe(row.get("required_items") or [])
        row["reason"] = _specialist_assignment_reason(agent_id, row["required_items"])
    return assignments


def _compile_missing_but_retrievable(
    required_items: list[Mapping[str, Any]],
    evidence_role_plan: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in evidence_role_plan:
        if row.get("status") != "planned_without_specific_requirement":
            continue
        item_id = str(row.get("required_item") or "")
        rows.append(
            {
                "required_item": item_id,
                "reason": "No explicit evidence requirement matched this required item; Research Lead must repair before bounded gap.",
                "candidate_source_families": list(row.get("required_source_families") or []),
                "gap_attribution": "method_to_runtime_gap_or_retrievable_gap_until_attempted",
            }
        )
    required_item_ids = {str(item.get("required_item") or "") for item in required_items}
    if "risk_and_counterevidence" in required_item_ids and not any(row.get("required_item") == "risk_and_counterevidence" for row in rows):
        rows.append(
            {
                "required_item": "risk_and_counterevidence",
                "reason": "Counterevidence can be compiled from deterministic packs if paid risk specialist is pruned; verify traceable counter ids before writer.",
                "candidate_source_families": REQUIRED_ITEM_SOURCE_FAMILIES["risk_and_counterevidence"],
                "gap_attribution": "retrievable_gap_until_counter_ids_verified",
            }
        )
    return rows


def _compile_bounded_or_commercial_gap(
    route_request: MultiAgentRouteRequest,
    required_items: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    text = str(route_request.user_query or "").lower()
    required_item_ids = {str(item.get("required_item") or "") for item in required_items}
    rows: list[dict[str, Any]] = []
    if (
        "product_architecture_competition" in required_item_ids
        or "sku revenue" in text
        or "sku" in text
        or "product" in text
        or "产品" in text
    ):
        rows.append(
            {
                "gap_type": "product_kpi_exact_gap",
                "boundary": "Absent issuer-disclosed product KPI or commercial tracker, product/spec/deployment evidence supports bounded product judgment but not SKU revenue, shipment, ASP, share, or backlog.",
                "applies_to_required_items": ["product_architecture_competition", "customer_deployment_adoption", "fundamental_financial_bridge"],
            }
        )
    if "capex" in text or "deployment" in text or "客户" in text or "部署" in text:
        rows.append(
            {
                "gap_type": "proxy_to_exact_financial_boundary",
                "boundary": "Cloud capex or customer deployment can support demand validation/read-through, but cannot be supplier exact revenue, customer order value, or backlog without direct disclosure.",
                "applies_to_required_items": ["customer_deployment_adoption", "supply_chain_readthrough", "capital_market_price_in"],
            }
        )
    if not rows and required_items:
        rows.append(
            {
                "gap_type": "bounded_public_source_gap",
                "boundary": "Proxy/context evidence may support direction and mechanism, but exact operating facts require issuer disclosure, official source, or commercial tracker.",
                "applies_to_required_items": [str(item.get("required_item") or "") for item in required_items],
            }
        )
    return rows


def _requirement_matches_required_item(requirement: Mapping[str, Any], required_item: str) -> bool:
    markers = REQUIRED_ITEM_REQUIREMENT_ID_MARKERS.get(required_item, (required_item,))
    requirement_id = str(requirement.get("requirement_id") or "").lower()
    if any(marker in requirement_id for marker in markers):
        return True
    question = str(requirement.get("question") or requirement.get("question_zh") or requirement.get("analysis_intent") or "").lower()
    if question and any(marker in question for marker in REQUIRED_ITEM_QUERY_MARKERS.get(required_item, markers)):
        return True
    routes = set(_string_list(requirement.get("evidence_routes") or requirement.get("retrieval_routes")))
    sources = set(_string_list(requirement.get("source_families") or requirement.get("source_tiers") or requirement.get("source_family")))
    if required_item == "capital_market_price_in" and ("market_snapshot" in routes or "market_snapshot" in sources):
        return True
    if required_item == "supply_chain_readthrough" and "industry_snapshot" in routes and any(
        marker in requirement_id for marker in ("supply", "chain", "semicap", "foundry", "hbm", "cowos")
    ):
        return True
    if required_item == "customer_deployment_adoption" and any(marker in requirement_id for marker in ("customer", "deployment", "adoption")):
        return True
    if required_item == "product_architecture_competition" and any(marker in requirement_id for marker in ("product", "architecture", "accelerator", "spec")):
        return True
    return False


def _can_support_for_required_item(required_item: str) -> list[str]:
    mapping = {
        "product_architecture_competition": ["product capability", "generation transition", "competitive/substitution context"],
        "customer_deployment_adoption": ["adoption signal", "demand validation", "deployment/channel context"],
        "supply_chain_readthrough": ["read-through mechanism", "bottleneck/constraint context", "peer-cycle framing"],
        "fundamental_financial_bridge": ["revenue exposure", "margin/cash-flow/working-capital bridge", "peer/period financial quality"],
        "capital_market_price_in": ["price-in context", "liquidity/positioning/valuation boundary", "capital feedback signal"],
        "risk_and_counterevidence": ["counter-thesis", "what-would-change view", "boundary/gap attribution"],
    }
    return mapping.get(required_item, ["bounded analyst judgment"])


def _cannot_infer_for_required_item(required_item: str) -> list[str]:
    common = ["unbounded investment recommendation"]
    mapping = {
        "product_architecture_competition": ["SKU revenue", "shipment/share", "customer order value"],
        "customer_deployment_adoption": ["exact sales", "backlog", "margin improvement"],
        "supply_chain_readthrough": ["direct customer relationship from peer group membership", "exact orders/backlog", "company revenue"],
        "fundamental_financial_bridge": ["product success from revenue growth alone", "margin quality without mix/cost bridge"],
        "capital_market_price_in": ["company operating fact from price action", "real-time fund flow without source"],
        "risk_and_counterevidence": ["generic risk list without thesis constraint"],
    }
    return [*mapping.get(required_item, []), *common]


def _specialist_assignment_reason(agent_id: str, required_items: list[str]) -> str:
    if agent_id == "product_technology_analyst":
        return "Owns product/spec/deployment evidence translation into bounded product judgment."
    if agent_id == "fundamental_analyst":
        return "Owns product-to-financial bridge across three-statement, margin, cash-flow and peer metrics."
    if agent_id == "industry_supply_chain_analyst":
        return "Owns demand/supply-chain read-through and customer/supplier mechanism."
    if agent_id == "market_valuation_analyst":
        return "Owns market expectation, price-in and capital feedback boundary."
    if agent_id == "risk_counterevidence_analyst":
        return "Owns thesis-specific counter-read and what-would-change conditions."
    return f"Assigned for {', '.join(required_items)}."


def _supervising_field_is_present(value: Any) -> bool:
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, (list, tuple, set)):
        return bool(value)
    return bool(str(value or "").strip())


def _normalize_activation_for_source_contract(plan: Mapping[str, Any], route_request: MultiAgentRouteRequest) -> dict[str, Any]:
    normalized = dict(plan or {})
    if route_request.focus_tickers:
        normalized["focus_tickers"] = list(route_request.focus_tickers)
    if route_request.search_scope_tickers:
        normalized["search_scope_tickers"] = list(route_request.search_scope_tickers)
    if not _requires_sector_depth_relationship_route(route_request):
        normalized = _normalize_non_relationship_activation(normalized, route_request)
        return _normalize_cost_aware_activation(normalized, route_request)

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
            *_product_technology_optional_agents(route_request),
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
            *(["company_product_evidence_graph"] if "product_technology_analyst" in active else []),
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
    return _normalize_cost_aware_activation(normalized, route_request)


def _align_activation_with_evidence_payload(plan: Mapping[str, Any], evidence_payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence_payload, Mapping) or not evidence_payload.get("requirements"):
        return dict(plan or {})
    normalized = dict(plan or {})
    active = _dedupe([str(agent) for agent in normalized.get("activate_agents") or []])
    allowed_sources = _dedupe([str(source) for source in normalized.get("allowed_source_families") or []])
    added_agents: list[str] = []
    added_sources: list[str] = []
    known_sources = set(allowed_source_families())
    for requirement in evidence_payload.get("requirements") or []:
        if not isinstance(requirement, Mapping):
            continue
        requirement_sources = set(
            _string_list(
                requirement.get("source_families")
                or requirement.get("source_tiers")
                or requirement.get("source_family")
            )
        )
        for source in sorted(requirement_sources):
            if source in known_sources and source != "live_public_web_context" and source not in allowed_sources:
                allowed_sources.append(source)
                added_sources.append(source)
        requirement_routes = _dedupe(
            [
                *_string_list(requirement.get("evidence_routes") or requirement.get("retrieval_routes")),
                *_implied_activation_routes_for_requirement(requirement, requirement_sources),
            ]
        )
        for route in requirement_routes:
            source_family = ROUTE_SOURCE_FAMILY.get(route, "")
            owner = ROUTE_OPERATOR_TOOL.get(route, ("", ""))[0]
            if source_family:
                requirement_sources.add(source_family)
            if source_family and source_family not in allowed_sources:
                allowed_sources.append(source_family)
                added_sources.append(source_family)
            if owner and owner not in active:
                active = _insert_before(active, owner, "coverage_reflection")
                added_agents.append(owner)
        if (
            str(normalized.get("execution_mode") or "") in {"standard_memo", "deep_research"}
            and _requirement_requires_product_technology(requirement, requirement_sources)
            and "product_technology_analyst" not in active
        ):
            active = _insert_before(active, "product_technology_analyst", "judgment_plan_aggregator")
            added_agents.append("product_technology_analyst")
            if "company_product_evidence_graph" not in allowed_sources:
                allowed_sources.append("company_product_evidence_graph")
                added_sources.append("company_product_evidence_graph")
    if not added_agents and not added_sources:
        return normalized
    normalized["activate_agents"] = active
    normalized["allowed_source_families"] = allowed_sources
    priorities = dict(normalized.get("agent_priorities") or {})
    model_policy = dict(normalized.get("model_policy_hint") or {})
    for agent_id in added_agents:
        priorities.setdefault(agent_id, "supporting")
        model_policy.setdefault(agent_id, "none" if agent_id.endswith("_operator") or agent_id in {"sec_operator", "eight_k_operator"} else "balanced")
    normalized["agent_priorities"] = priorities
    normalized["model_policy_hint"] = model_policy
    normalized["skip_agents"] = _sync_skip_agents(normalized.get("skip_agents"), active, [])
    metadata = dict(normalized.get("metadata") or {})
    metadata["evidence_route_source_alignment_policy"] = "llm_evidence_routes_extend_activation_sources_v0_1"
    metadata["evidence_route_source_alignment_added_sources"] = _dedupe(added_sources)
    metadata["evidence_route_source_alignment_added_agents"] = _dedupe(added_agents)
    normalized["metadata"] = metadata
    return normalized


def _implied_activation_routes_for_requirement(requirement: Mapping[str, Any], source_families: set[str]) -> list[str]:
    """Mirror deterministic compiler route implications that affect activation validation."""
    routes: list[str] = []
    if "market_snapshot" in source_families:
        routes.append("market_snapshot")
    if "industry_snapshot" in source_families:
        routes.append("industry_snapshot")
    if "relationship_graph" in source_families:
        routes.append("relationship_graph")
    if "run_artifact" in source_families:
        routes.append("run_artifact")
    if "live_public_web_context" in source_families:
        routes.append("live_public_web_context")
    if "public_source_context" in source_families and _requirement_implies_market_snapshot(requirement):
        routes.append("market_snapshot")
    return _dedupe(routes)


def _requirement_implies_market_snapshot(requirement: Mapping[str, Any]) -> bool:
    market_fields = _string_list(requirement.get("market_fields") or requirement.get("required_market_fields"))
    if market_fields:
        return True
    text = " ".join(
        [
            str(requirement.get("task_id") or ""),
            str(requirement.get("question_zh") or requirement.get("question") or ""),
            str(requirement.get("analysis_intent") or ""),
            " ".join(_string_list(requirement.get("metric_families") or requirement.get("required_metric_families"))),
        ]
    ).lower()
    return any(
        marker in text
        for marker in (
            "market",
            "share",
            "valuation",
            "multiple",
            "stock",
            "price",
            "return",
            "proxy",
            "traffic",
            "download",
            "ranking",
            "rank",
            "市场",
            "份额",
            "估值",
            "股价",
            "代理",
        )
    )


def _requirement_requires_product_technology(requirement: Mapping[str, Any], source_families: set[str]) -> bool:
    if "company_product_evidence_graph" in source_families:
        return True
    if not (source_families & {"public_source_context", "live_public_web_context"}):
        return False
    return _requirement_mentions_product_technology(requirement)


def _requirement_mentions_product_technology(requirement: Mapping[str, Any]) -> bool:
    text = " ".join(
        [
            str(requirement.get("task_id") or ""),
            str(requirement.get("question_zh") or requirement.get("question") or ""),
            str(requirement.get("analysis_intent") or ""),
            " ".join(_string_list(requirement.get("metric_families") or requirement.get("required_metric_families"))),
        ]
    ).lower()
    return _text_mentions_product_technology(text)


def _normalize_non_relationship_activation(plan: Mapping[str, Any], route_request: MultiAgentRouteRequest) -> dict[str, Any]:
    normalized = dict(plan or {})
    mode = str(normalized.get("execution_mode") or "").strip()
    active = _dedupe([str(agent) for agent in normalized.get("activate_agents") or []])
    allowed_sources = _dedupe([str(source) for source in normalized.get("allowed_source_families") or []])
    removed: list[tuple[str, str]] = []
    relationship_overroute = (
        mode == "deep_research"
        or "universe_relationship" in active
        or "relationship_graph" in allowed_sources
    )
    policy_adjusted = relationship_overroute

    if relationship_overroute:
        fallback_mode = _non_relationship_execution_mode(route_request)
        normalized["execution_mode"] = fallback_mode
        active = [agent for agent in active if agent != "universe_relationship"]
        allowed_sources = [source for source in allowed_sources if source != "relationship_graph"]
        normalized["relationship_scope_rationale"] = ""
        normalized["scope_mode"] = (
            "sector_representative"
            if fallback_mode == "standard_memo" and len(route_request.search_scope_tickers or []) > len(route_request.focus_tickers or [])
            else "focused_peer"
        )
        removed.append(
            (
                "universe_relationship",
                "No relationship_graph source or explicit relationship expansion intent was requested; industry snapshot remains context-only.",
            )
        )
        metadata = dict(normalized.get("metadata") or {})
        metadata["relationship_overroute_pruned"] = True
        metadata["relationship_overroute_policy"] = "explicit_relationship_source_or_intent_required_v0_2"
        normalized["metadata"] = metadata

    if (
        str(normalized.get("execution_mode") or "") == "standard_memo"
        and "industry_supply_chain_analyst" in active
        and not _route_request_mentions_relationship_expansion(route_request)
    ):
        policy_adjusted = True
        active = [agent for agent in active if agent != "industry_supply_chain_analyst"]
        removed.append(
            (
                "industry_supply_chain_analyst",
                "Industry or commodity snapshot was requested as context, but no supply-chain/customer/supplier relationship analysis was requested.",
            )
        )
        metadata = dict(normalized.get("metadata") or {})
        metadata["industry_supply_chain_pruned"] = True
        metadata["industry_supply_chain_prune_policy"] = "relationship_or_supply_chain_intent_required_v0_2"
        normalized["metadata"] = metadata

    normalized["activate_agents"] = active
    normalized["allowed_source_families"] = _non_relationship_allowed_sources(allowed_sources, route_request)
    normalized = _align_non_relationship_source_operators(normalized, route_request)
    normalized = _prune_non_requested_product_technology(normalized, route_request)
    normalized["scope_mode"] = _non_relationship_scope_mode(normalized, route_request)
    priorities = dict(normalized.get("agent_priorities") or {})
    model_policy = dict(normalized.get("model_policy_hint") or {})
    for agent_id, _reason in removed:
        priorities.pop(agent_id, None)
        model_policy.pop(agent_id, None)
    normalized["agent_priorities"] = priorities
    normalized["model_policy_hint"] = model_policy
    if policy_adjusted and str(normalized.get("execution_mode") or "") == "standard_memo":
        normalized["max_tool_calls_total"] = min(
            11 if "industry_snapshot" in set(normalized.get("allowed_source_families") or []) else 10,
            _int_value(normalized.get("max_tool_calls_total"), default=10),
        )
        normalized["max_second_pass_rounds"] = min(1, _int_value(normalized.get("max_second_pass_rounds"), default=1))
        normalized["max_repair_rounds"] = min(1, _int_value(normalized.get("max_repair_rounds"), default=1))
    if removed:
        normalized["skip_agents"] = _sync_skip_agents(normalized.get("skip_agents"), active, removed)
    return normalized


def _non_relationship_scope_mode(plan: Mapping[str, Any], route_request: MultiAgentRouteRequest) -> str:
    mode = str(plan.get("execution_mode") or "").strip()
    scope = str(plan.get("scope_mode") or "").strip()
    if mode in {"deterministic_lookup", "focused_answer"}:
        return "focused_peer"
    if mode != "standard_memo":
        return scope
    expanded_scope = len(route_request.search_scope_tickers or []) > len(route_request.focus_tickers or [])
    if scope in {"", "full_universe"}:
        return "sector_representative" if expanded_scope else "focused_peer"
    return scope


def _sanitize_activation_policy_maps(plan: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(plan or {})
    active = set(_string_list(normalized.get("activate_agents")))
    known = set(known_agent_ids())
    removed: dict[str, list[str]] = {"model_policy_hint": [], "agent_priorities": []}
    model_policy: dict[str, str] = {}
    for agent_id, profile in dict(normalized.get("model_policy_hint") or {}).items():
        key = str(agent_id or "").strip()
        if key not in known:
            removed["model_policy_hint"].append(key)
            continue
        model_policy[key] = str(profile or "").strip()
    priorities: dict[str, str] = {}
    for agent_id, priority in dict(normalized.get("agent_priorities") or {}).items():
        key = str(agent_id or "").strip()
        if key not in known or key not in active:
            removed["agent_priorities"].append(key)
            continue
        priorities[key] = str(priority or "").strip()
    normalized["model_policy_hint"] = model_policy
    normalized["agent_priorities"] = priorities
    if removed["model_policy_hint"] or removed["agent_priorities"]:
        metadata = dict(normalized.get("metadata") or {})
        metadata["policy_map_placeholder_pruned"] = True
        metadata["policy_map_placeholder_prune_policy"] = "drop_unknown_or_inactive_policy_keys_v0_1"
        metadata["policy_map_placeholder_pruned_keys"] = {
            key: [item for item in values if item]
            for key, values in removed.items()
            if values
        }
        normalized["metadata"] = metadata
    return normalized


def _normalize_plan_reflection_contract(
    plan: Mapping[str, Any],
    route_request: MultiAgentRouteRequest,
    evidence_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Make post-Lead hard-gate inputs explicit after route/evidence alignment.

    The model can supply a partial activation plan while its evidence requirements
    imply relationship routes or source-family requirements. This normalizer keeps
    the hard gate intact by fixing the earliest owned contract: activation metadata
    and relationship scope must be coherent before retrieval starts.
    """
    normalized = dict(plan or {})
    active = _dedupe(_string_list(normalized.get("activate_agents")))
    allowed_sources = _dedupe(_string_list(normalized.get("allowed_source_families")))
    metadata = dict(normalized.get("metadata") or {})

    known_sources = set(allowed_source_families())
    required_sources = _dedupe(
        [
            *_string_list(normalized.get("required_source_families")),
            *_string_list(metadata.get("required_source_families")),
            *_string_list(metadata.get("required_source_family")),
            *_string_list(metadata.get("required_sources")),
        ]
    )
    valid_required_sources = [source for source in required_sources if source in known_sources]
    pruned_required_sources = [source for source in required_sources if source and source not in known_sources]
    if required_sources:
        metadata["required_source_families"] = valid_required_sources
        metadata.pop("required_source_family", None)
        metadata.pop("required_sources", None)
    if pruned_required_sources:
        metadata["plan_reflection_required_source_families_pruned"] = pruned_required_sources
        metadata["plan_reflection_required_source_prune_policy"] = "drop_unknown_llm_required_source_families_v0_1"

    relationship_needed = "universe_relationship" in active or "relationship_graph" in allowed_sources
    if not relationship_needed and isinstance(evidence_payload, Mapping):
        for requirement in evidence_payload.get("requirements") or []:
            if not isinstance(requirement, Mapping):
                continue
            route_sources = set(
                _string_list(requirement.get("source_families") or requirement.get("source_tiers") or requirement.get("source_family"))
            )
            routes = set(_string_list(requirement.get("evidence_routes") or requirement.get("retrieval_routes")))
            if "relationship_graph" in route_sources or "relationship_graph" in routes:
                relationship_needed = True
                break

    mode = str(normalized.get("execution_mode") or "").strip()
    if relationship_needed and mode == "standard_memo":
        normalized["execution_mode"] = "deep_research"
        mode = "deep_research"
        metadata["plan_reflection_execution_mode_promoted"] = True
        metadata["plan_reflection_execution_mode_policy"] = "relationship_route_requires_deep_research_v0_1"
    if relationship_needed:
        for agent_id in ["research_lead", "universe_relationship", "coverage_reflection", "memo_writer", "verifier", "renderer"]:
            if agent_id not in active:
                active.append(agent_id)
        if "relationship_graph" not in allowed_sources:
            allowed_sources.append("relationship_graph")
        if mode == "deep_research" and not str(normalized.get("relationship_scope_rationale") or "").strip():
            normalized["relationship_scope_rationale"] = (
                "The evidence plan requires relationship_graph / supply-chain read-through, "
                "so relationship expansion is required before specialist synthesis."
            )
            metadata["relationship_scope_rationale_filled"] = True
            metadata["relationship_scope_rationale_policy"] = "relationship_graph_requires_explicit_scope_v0_1"

    normalized["activate_agents"] = active
    normalized["allowed_source_families"] = allowed_sources
    normalized["skip_agents"] = _sync_skip_agents(normalized.get("skip_agents"), active, [])
    normalized["metadata"] = metadata
    return normalized


def _align_non_relationship_source_operators(plan: Mapping[str, Any], route_request: MultiAgentRouteRequest) -> dict[str, Any]:
    normalized = dict(plan or {})
    mode = str(normalized.get("execution_mode") or "").strip()
    active = _dedupe([str(agent) for agent in normalized.get("activate_agents") or []])
    allowed_sources = set(_context_source_families(route_request)) | set(_string_list(normalized.get("allowed_source_families")))
    added: list[str] = []

    if "company_authored_unaudited_sec_filing" in allowed_sources and mode in {"focused_answer", "standard_memo"}:
        if "eight_k_operator" not in active:
            active = _insert_before(active, "eight_k_operator", "coverage_reflection")
            added.append("eight_k_operator")
    market_intent = _route_request_mentions_market_or_valuation(route_request)
    if "market_snapshot" in allowed_sources and mode in {"focused_answer", "standard_memo"}:
        if "market_operator" not in active:
            active = _insert_before(active, "market_operator", "coverage_reflection")
            added.append("market_operator")
        if mode == "standard_memo" and market_intent and "market_valuation_analyst" not in active:
            active = _insert_before(active, "market_valuation_analyst", "judgment_plan_aggregator")
            added.append("market_valuation_analyst")
    if "industry_snapshot" in allowed_sources and mode == "standard_memo" and "industry_operator" not in active:
        active = _insert_before(active, "industry_operator", "coverage_reflection")
        added.append("industry_operator")
    if (
        mode == "standard_memo"
        and _route_request_requires_product_technology(route_request, allowed_sources)
        and "product_technology_analyst" not in active
    ):
        active = _insert_before(active, "product_technology_analyst", "judgment_plan_aggregator")
        added.append("product_technology_analyst")

    if not added:
        return normalized

    normalized["activate_agents"] = active
    normalized["allowed_source_families"] = _dedupe([*list(normalized.get("allowed_source_families") or []), *sorted(allowed_sources)])
    priorities = dict(normalized.get("agent_priorities") or {})
    model_policy = dict(normalized.get("model_policy_hint") or {})
    for agent_id in added:
        priorities.setdefault(agent_id, "supporting")
        model_policy.setdefault(agent_id, "none" if agent_id.endswith("_operator") else "balanced")
    normalized["agent_priorities"] = priorities
    normalized["model_policy_hint"] = model_policy
    normalized["skip_agents"] = _sync_skip_agents(normalized.get("skip_agents"), active, [])
    metadata = dict(normalized.get("metadata") or {})
    metadata["source_operator_alignment_added"] = added
    metadata["source_operator_alignment_policy"] = "contract_source_family_operator_alignment_v0_1"
    normalized["metadata"] = metadata
    if mode == "focused_answer" and "market_operator" in added:
        normalized["max_tool_calls_total"] = max(8, _int_value(normalized.get("max_tool_calls_total"), default=6))
    return normalized


def _prune_non_requested_product_technology(plan: Mapping[str, Any], route_request: MultiAgentRouteRequest) -> dict[str, Any]:
    normalized = dict(plan or {})
    mode = str(normalized.get("execution_mode") or "").strip()
    active = _dedupe([str(agent) for agent in normalized.get("activate_agents") or []])
    allowed_sources = _dedupe([str(source) for source in normalized.get("allowed_source_families") or []])
    if mode != "standard_memo" or "product_technology_analyst" not in active:
        return normalized
    if _route_request_requires_product_technology(route_request, set(allowed_sources)):
        return normalized
    active = [agent for agent in active if agent != "product_technology_analyst"]
    context_sources = set(_context_source_families(route_request))
    allowed_sources = [
        source
        for source in allowed_sources
        if source != "company_product_evidence_graph" or source in context_sources
    ]
    normalized["activate_agents"] = active
    normalized["allowed_source_families"] = _dedupe(allowed_sources)
    priorities = dict(normalized.get("agent_priorities") or {})
    priorities.pop("product_technology_analyst", None)
    normalized["agent_priorities"] = priorities
    model_policy = dict(normalized.get("model_policy_hint") or {})
    model_policy.pop("product_technology_analyst", None)
    normalized["model_policy_hint"] = model_policy
    normalized["skip_agents"] = _sync_skip_agents(
        normalized.get("skip_agents"),
        active,
        [
            (
                "product_technology_analyst",
                "Public source context alone is not a product-technology task without product KPI, product taxonomy, or product adoption intent.",
            )
        ],
    )
    metadata = dict(normalized.get("metadata") or {})
    metadata["product_technology_pruned"] = True
    metadata["product_technology_prune_policy"] = "public_context_alone_is_not_product_lens_v0_1"
    normalized["metadata"] = metadata
    return normalized


def _route_request_requires_product_technology(
    route_request: MultiAgentRouteRequest,
    candidate_sources: set[str] | None = None,
) -> bool:
    context_sources = set(_context_source_families(route_request))
    if "company_product_evidence_graph" in context_sources:
        return True
    if _route_request_mentions_product_technology(route_request):
        return True
    source_set = set(candidate_sources or set())
    return bool("company_product_evidence_graph" in source_set and _route_request_mentions_product_technology(route_request))


def _non_relationship_execution_mode(route_request: MultiAgentRouteRequest) -> str:
    context_mode = str(route_request.context.get("execution_mode") or "").strip()
    if context_mode in {"focused_answer", "standard_memo"}:
        return context_mode
    contract = _context_query_contract(route_request)
    task_type = str(contract.get("task_type") or route_request.context.get("task_type") or "").strip()
    if task_type == "open_analysis" or _route_request_standard_memo_shape(route_request):
        return "standard_memo"
    return "focused_answer"


def _non_relationship_allowed_sources(sources: list[str], route_request: MultiAgentRouteRequest) -> list[str]:
    allowed = [source for source in sources if source != "relationship_graph"]
    context_sources = [source for source in _context_source_families(route_request) if source != "relationship_graph"]
    if not allowed:
        allowed = ["primary_sec_filing", "company_authored_unaudited_sec_filing"]
    return _dedupe([*allowed, *context_sources])


def _normalize_cost_aware_activation(plan: Mapping[str, Any], route_request: MultiAgentRouteRequest) -> dict[str, Any]:
    normalized = dict(plan or {})
    mode = str(normalized.get("execution_mode") or "").strip()
    if mode not in {"focused_answer", "standard_memo", "deep_research"}:
        return normalized
    metadata = dict(normalized.get("metadata") or {})
    metadata.setdefault("route_selection_policy", "cost_and_query_type_aware_v0_1")
    metadata.setdefault("route_cost_policy", "cheapest_sufficient_route_set_with_explicit_high_cost_semantic_context")
    normalized["metadata"] = metadata
    risk_required = _route_request_requires_risk_lens(route_request, normalized)

    active = _dedupe([str(agent) for agent in normalized.get("activate_agents") or []])
    if risk_required:
        if "risk_counterevidence_analyst" not in active and mode in {"standard_memo", "deep_research"}:
            active = _insert_before(active, "risk_counterevidence_analyst", "judgment_plan_aggregator")
            normalized["activate_agents"] = active
            priorities = dict(normalized.get("agent_priorities") or {})
            priorities["risk_counterevidence_analyst"] = "supporting"
            normalized["agent_priorities"] = priorities
            model_policy = dict(normalized.get("model_policy_hint") or {})
            model_policy["risk_counterevidence_analyst"] = "balanced" if mode == "standard_memo" else "strong"
            normalized["model_policy_hint"] = model_policy
            normalized["skip_agents"] = _sync_skip_agents(
                normalized.get("skip_agents"),
                active,
                [],
            )
            metadata = dict(normalized.get("metadata") or {})
            metadata["risk_counterevidence_added"] = True
            metadata["risk_counterevidence_policy"] = "standard_memo_balanced_risk_lens_v0_2"
            normalized["metadata"] = metadata
        elif "risk_counterevidence_analyst" in active:
            priorities = dict(normalized.get("agent_priorities") or {})
            priorities["risk_counterevidence_analyst"] = (
                "supporting" if mode == "standard_memo" else priorities.get("risk_counterevidence_analyst", "supporting")
            )
            normalized["agent_priorities"] = priorities
        return _apply_paid_specialist_whitelist(normalized, route_request)

    if "risk_counterevidence_analyst" not in active:
        return _apply_paid_specialist_whitelist(normalized, route_request)

    normalized["activate_agents"] = [agent for agent in active if agent != "risk_counterevidence_analyst"]
    priorities = dict(normalized.get("agent_priorities") or {})
    priorities.pop("risk_counterevidence_analyst", None)
    normalized["agent_priorities"] = priorities
    model_policy = dict(normalized.get("model_policy_hint") or {})
    model_policy.pop("risk_counterevidence_analyst", None)
    normalized["model_policy_hint"] = model_policy

    skip_agents = [dict(item) for item in normalized.get("skip_agents") or [] if isinstance(item, Mapping)]
    if not any(str(item.get("agent_id") or "") == "risk_counterevidence_analyst" for item in skip_agents):
        skip_agents.append(
            {
                "agent_id": "risk_counterevidence_analyst",
                "reason": "No explicit risk, counterevidence, credit, downside, or uncertainty intent in the user request.",
            }
        )
    normalized["skip_agents"] = skip_agents
    metadata = dict(normalized.get("metadata") or {})
    metadata["risk_counterevidence_pruned"] = True
    metadata["risk_counterevidence_prune_policy"] = "balanced_risk_or_pressure_intent_required_v0_2"
    normalized["metadata"] = metadata
    return _apply_paid_specialist_whitelist(normalized, route_request)


def _apply_paid_specialist_whitelist(plan: Mapping[str, Any], route_request: MultiAgentRouteRequest) -> dict[str, Any]:
    allowed = _paid_specialist_whitelist(route_request)
    if not allowed:
        return dict(plan or {})
    specialist_agents = {
        "fundamental_analyst",
        "product_technology_analyst",
        "industry_supply_chain_analyst",
        "market_valuation_analyst",
        "risk_counterevidence_analyst",
    }
    normalized = dict(plan or {})
    active = _dedupe([str(agent) for agent in normalized.get("activate_agents") or []])
    removed = [agent for agent in active if agent in specialist_agents and agent not in allowed]
    if not removed:
        metadata = dict(normalized.get("metadata") or {})
        metadata.setdefault("paid_specialist_whitelist_policy", "runtime_paid_specialist_budget_whitelist_v0_1")
        metadata.setdefault("paid_specialist_whitelist", sorted(allowed))
        normalized["metadata"] = metadata
        return normalized
    active = [agent for agent in active if agent not in set(removed)]
    normalized["activate_agents"] = active
    priorities = {
        str(agent): priority
        for agent, priority in dict(normalized.get("agent_priorities") or {}).items()
        if str(agent) not in set(removed)
    }
    normalized["agent_priorities"] = priorities
    model_policy = {
        str(agent): policy
        for agent, policy in dict(normalized.get("model_policy_hint") or {}).items()
        if str(agent) not in set(removed)
    }
    normalized["model_policy_hint"] = model_policy
    skip_agents = [dict(item) for item in normalized.get("skip_agents") or [] if isinstance(item, Mapping)]
    existing = {str(item.get("agent_id") or "") for item in skip_agents}
    for agent_id in removed:
        if agent_id not in existing:
            skip_agents.append(
                {
                    "agent_id": agent_id,
                    "reason": "Pruned by paid specialist whitelist for this run; use deterministic packs, bounded gap, or a targeted follow-up if the required item cannot be answered.",
                }
            )
    normalized["skip_agents"] = _sync_skip_agents(skip_agents, active, [])
    metadata = dict(normalized.get("metadata") or {})
    metadata["paid_specialist_whitelist_policy"] = "runtime_paid_specialist_budget_whitelist_v0_1"
    metadata["paid_specialist_whitelist"] = sorted(allowed)
    metadata["paid_specialist_pruned_agents"] = removed
    normalized["metadata"] = metadata
    return normalized


def _paid_specialist_whitelist(route_request: MultiAgentRouteRequest) -> set[str]:
    context = route_request.context if isinstance(route_request.context, Mapping) else {}
    contract = _context_query_contract(route_request)
    allowed = _string_list(
        context.get("expected_paid_specialist_agents")
        or context.get("paid_specialist_agents")
        or contract.get("expected_paid_specialist_agents")
        or contract.get("paid_specialist_agents")
    )
    agents = {agent for agent in allowed if agent}
    if agents and _route_request_mentions_risk_or_counterevidence(route_request):
        agents.add("risk_counterevidence_analyst")
    return agents


def _sector_depth_agent_priorities(active: list[str]) -> dict[str, str]:
    primary = {
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
    optional.extend(_product_technology_optional_agents(route_request))
    if _route_request_mentions_market_or_valuation(route_request):
        optional.extend(["market_operator", "market_valuation_analyst"])
    elif "market_snapshot" in set(_context_source_families(route_request)):
        optional.append("market_operator")
    if _route_request_mentions_risk_or_counterevidence(route_request):
        optional.append("risk_counterevidence_analyst")
    return optional


def _product_technology_optional_agents(route_request: MultiAgentRouteRequest) -> list[str]:
    sources = set(_context_source_families(route_request))
    if _route_request_mentions_product_technology(route_request) or "company_product_evidence_graph" in sources:
        return ["product_technology_analyst"]
    return []


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


def _route_request_mentions_product_technology(route_request: MultiAgentRouteRequest) -> bool:
    text = _route_request_product_intent_text(route_request)
    return _text_mentions_product_technology(text)


def _text_mentions_product_technology(text: str) -> bool:
    normalized = str(text or "").lower()
    word_patterns = (
        r"\bproducts?\b",
        r"\bproduct\s+(revenue|kpi|metric|metrics|line|lines|cycle|adoption|traction)\b",
        r"\bsku(s)?\b",
        r"\bplatform(s)?\b",
        r"\bdeveloper(s)?\b",
        r"\bapp\s+download(s)?\b",
        r"\bclinical\b",
        r"\btrial(s)?\b",
        r"\bregulatory\b",
        r"\bopenfda\b",
        r"\bnhtsa\b",
        r"\bsubscriber(s)?\b",
        r"\brpo\b",
        r"\bremaining\s+performance\s+obligation(s)?\b",
        r"\bpublic\s+proxy\b",
    )
    if any(re.search(pattern, normalized) for pattern in word_patterns):
        return True
    return any(
        term in normalized
        for term in (
            "产品",
            "产品线",
            "产品收入",
            "产品指标",
            "主业",
            "平台",
            "订阅",
            "剩余履约义务",
            "临床",
            "监管",
            "公开代理",
        )
    )


def _route_request_product_intent_text(route_request: MultiAgentRouteRequest) -> str:
    contract = _context_query_contract(route_request)
    inventory = route_request.source_inventory if isinstance(route_request.source_inventory, Mapping) else {}
    inventory_sources = _string_list(inventory.get("source_families") or inventory.get("source_tiers") or inventory.get("available_source_families"))
    return " ".join(
        [
            str(route_request.user_query or ""),
            str(route_request.context.get("task_type") or contract.get("task_type") or ""),
            " ".join(_string_list(contract.get("source_tiers") or route_request.context.get("source_tiers"))),
            " ".join(_string_list(contract.get("source_families") or route_request.context.get("source_families"))),
            " ".join(_string_list(contract.get("metric_families"))),
            " ".join(inventory_sources),
        ]
    ).lower()


def _route_request_mentions_risk_or_counterevidence(route_request: MultiAgentRouteRequest) -> bool:
    text = _route_request_intent_text(route_request)
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


def _route_request_text(route_request: MultiAgentRouteRequest) -> str:
    return " ".join(
        [
            str(route_request.user_query or ""),
            json.dumps(route_request.context, ensure_ascii=False, default=str),
        ]
    ).lower()


def _route_request_intent_text(route_request: MultiAgentRouteRequest) -> str:
    contract = _context_query_contract(route_request)
    compact_context = {
        "execution_mode": route_request.context.get("execution_mode") or "",
        "task_type": route_request.context.get("task_type") or contract.get("task_type") or "",
        "expected_relationship_pack_ids": route_request.context.get("expected_relationship_pack_ids") or [],
        "source_tiers": contract.get("source_tiers") or route_request.context.get("source_tiers") or [],
        "source_families": contract.get("source_families") or route_request.context.get("source_families") or [],
        "metric_families": contract.get("metric_families") or [],
    }
    inventory = route_request.source_inventory if isinstance(route_request.source_inventory, Mapping) else {}
    compact_inventory = {
        "source_families": inventory.get("source_families") or inventory.get("source_tiers") or [],
        "company_product_evidence_graph": bool(inventory.get("company_product_evidence_graph")),
        "public_source_context": bool(inventory.get("public_source_context")),
        "relationship_graph": bool(inventory.get("relationship_graph")),
        "industry_snapshot": bool(inventory.get("industry_snapshot")),
    }
    return " ".join(
        [
            str(route_request.user_query or ""),
            json.dumps(compact_context, ensure_ascii=False, default=str),
            json.dumps(compact_inventory, ensure_ascii=False, default=str),
        ]
    ).lower()


def _route_request_requires_risk_lens(route_request: MultiAgentRouteRequest, activation_plan: Mapping[str, Any]) -> bool:
    if _route_request_mentions_risk_or_counterevidence(route_request):
        return True
    mode = str(activation_plan.get("execution_mode") or "").strip()
    if mode == "deep_research":
        return True
    if mode != "standard_memo":
        return False
    return _route_request_standard_memo_shape(route_request) and _standard_memo_balance_intent(route_request)


def _standard_memo_balance_intent(route_request: MultiAgentRouteRequest) -> bool:
    text = str(route_request.user_query or "").lower()
    return any(
        term in text
        for term in (
            "evidence gaps",
            "evidence gap",
            "balanced",
            "pressure",
            "downside",
            "bear case",
            "uncertainty",
            "valuation divergence",
            "multiple divergence",
            "风险平衡",
            "压力",
            "证据缺口",
            "没有证据",
            "无证据",
            "未证实",
            "证据不足",
            "缺证",
            "下行",
            "不确定",
            "估值分歧",
        )
    )


def _route_request_standard_memo_shape(route_request: MultiAgentRouteRequest) -> bool:
    text = _route_request_intent_text(route_request)
    ticker_count = len(route_request.search_scope_tickers or route_request.focus_tickers or [])
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


def _route_request_mentions_relationship_expansion(route_request: MultiAgentRouteRequest) -> bool:
    return _text_mentions_relationship_expansion(_route_request_intent_text(route_request))


def _requirement_mentions_relationship_expansion(requirement: Mapping[str, Any]) -> bool:
    text = " ".join(
        [
            str(requirement.get("task_id") or ""),
            str(requirement.get("question_zh") or requirement.get("question") or ""),
            str(requirement.get("analysis_intent") or ""),
            str(requirement.get("route_selection_reason") or ""),
            " ".join(_string_list(requirement.get("metric_families") or requirement.get("required_metric_families"))),
        ]
    )
    return _text_mentions_relationship_expansion(text)


def _text_mentions_relationship_expansion(text: str) -> bool:
    normalized = str(text or "").lower()
    return any(
        term in text
        for term in (
            "supply chain",
            "supply-chain",
            "customer",
            "supplier",
            "readthrough",
            "read-through",
            "cross-industry",
            "industry chain",
            "sector transmission",
            "demand transmission",
            "capex to",
            "deployment",
            "deployed",
            "adoption",
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
            "需求传导",
            "关系图",
            "关系证据",
        )
    )


def _requires_sector_depth_relationship_route(route_request: MultiAgentRouteRequest) -> bool:
    forced_mode = str(route_request.context.get("execution_mode") or route_request.context.get("expected_execution_mode") or "").strip()
    if forced_mode == "deep_research":
        return True
    sources = set(_context_source_families(route_request))
    if "relationship_graph" in sources:
        return True
    if route_request.context.get("expected_relationship_pack_ids"):
        return True
    if _route_request_mentions_relationship_expansion(route_request):
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
    return _dedupe(
        [
            source
            for source in sources
            if _source_family_not_explicitly_unavailable(route_request, source)
        ]
    )


def _source_family_not_explicitly_unavailable(route_request: MultiAgentRouteRequest, source_family: str) -> bool:
    family = str(source_family or "").strip()
    if not family:
        return False
    inventory = route_request.source_inventory if isinstance(route_request.source_inventory, Mapping) else {}
    availability = inventory.get("source_family_availability") if isinstance(inventory.get("source_family_availability"), Mapping) else {}
    item = availability.get(family) if isinstance(availability.get(family), Mapping) else {}
    if item and (item.get("available") is False or str(item.get("status") or "").strip() in {"unavailable", "policy_not_loaded"}):
        return False
    if family == "milvus_semantic" and not _milvus_semantic_available(route_request):
        return False
    return True


def _activation_plan_payload(
    payload: Mapping[str, Any],
    *,
    route_request: MultiAgentRouteRequest | None = None,
    loop_budget: LoopBudget | None = None,
) -> dict[str, Any]:
    if isinstance(payload.get("activation_plan"), Mapping):
        return dict(payload["activation_plan"])  # type: ignore[index]
    activation_keys = {
        "schema_version",
        "execution_mode",
        "activate_agents",
        "allowed_source_families",
        "model_policy_hint",
        "agent_priorities",
        "scope_mode",
    }
    if any(key in payload for key in activation_keys):
        return dict(payload)
    if route_request is not None:
        scaffold = route_multi_agent_activation(route_request, budget=loop_budget or LoopBudget()).get("activation_plan") or {}
        activation = dict(scaffold)
        metadata = dict(activation.get("metadata") or {})
        metadata["activation_scaffold_source"] = "deterministic_router_when_llm_omits_activation_plan"
        activation["metadata"] = metadata
        return activation
    return dict(payload)


def _evidence_requirement_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    evidence_payload: dict[str, Any]
    if isinstance(payload.get("evidence_requirement_plan"), Mapping):
        evidence_payload = dict(payload["evidence_requirement_plan"])  # type: ignore[index]
    elif isinstance(payload.get("evidence_requirements"), list):
        evidence_payload = {"requirements": list(payload.get("evidence_requirements") or [])}
    else:
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
        if isinstance(metadata.get("evidence_requirement_plan"), Mapping):
            evidence_payload = dict(metadata["evidence_requirement_plan"])  # type: ignore[index]
        elif isinstance(metadata.get("evidence_requirements"), list):
            evidence_payload = {"requirements": list(metadata.get("evidence_requirements") or [])}
        else:
            evidence_payload = {}
    return _normalize_evidence_requirement_payload_routes(evidence_payload)


def _normalize_evidence_requirement_payload_routes(evidence_payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence_payload, Mapping) or not isinstance(evidence_payload.get("requirements"), list):
        return dict(evidence_payload or {})
    known_routes = set(ROUTE_SOURCE_FAMILY)
    source_family_names = set(allowed_source_families())
    normalized_requirements: list[dict[str, Any]] = []
    normalized_count = 0
    for requirement in evidence_payload.get("requirements") or []:
        if not isinstance(requirement, Mapping):
            continue
        req = dict(requirement)
        routes = _string_list(req.get("evidence_routes") or req.get("retrieval_routes"))
        source_families = _dedupe(
            [
                *_string_list(req.get("source_families") or req.get("source_family")),
                *_string_list(req.get("source_tiers")),
            ]
        )
        kept_routes: list[str] = []
        moved_source_families: list[str] = []
        for route in routes:
            if route in known_routes:
                kept_routes.append(route)
            elif route in source_family_names:
                moved_source_families.append(route)
            else:
                kept_routes.append(route)
        if moved_source_families:
            normalized_count += 1
            req["source_families"] = _dedupe([*source_families, *moved_source_families])
            req["evidence_routes"] = _dedupe(kept_routes)
            req["retrieval_routes"] = _dedupe(kept_routes)
            normalizations = [dict(item) for item in req.get("normalizations") or [] if isinstance(item, Mapping)]
            normalizations.append(
                {
                    "field": "evidence_routes",
                    "action": "moved_source_family_names_to_source_families",
                    "source_families": moved_source_families,
                    "policy": "research_lead_evidence_route_source_family_normalization_v0_1",
                }
            )
            req["normalizations"] = normalizations
        normalized_requirements.append(req)
    result = dict(evidence_payload)
    result["requirements"] = normalized_requirements
    if normalized_count:
        metadata = dict(result.get("metadata") or {}) if isinstance(result.get("metadata"), Mapping) else {}
        metadata["route_source_family_normalization_count"] = normalized_count
        metadata["route_source_family_normalization_policy"] = "research_lead_evidence_route_source_family_normalization_v0_1"
        result["metadata"] = metadata
    return result


def _normalize_live_web_evidence_payload_for_policy(
    evidence_payload: Mapping[str, Any],
    route_request: MultiAgentRouteRequest,
) -> dict[str, Any]:
    if _live_web_scope_policy_allowed(route_request):
        return dict(evidence_payload or {})
    if not isinstance(evidence_payload, Mapping) or not isinstance(evidence_payload.get("requirements"), list):
        return dict(evidence_payload or {})
    normalized_requirements: list[dict[str, Any]] = []
    normalized_count = 0
    for requirement in evidence_payload.get("requirements") or []:
        if not isinstance(requirement, Mapping):
            continue
        req = dict(requirement)
        routes = _string_list(req.get("evidence_routes") or req.get("retrieval_routes"))
        source_families = _dedupe(
            [
                *_string_list(req.get("source_families") or req.get("source_family")),
                *_string_list(req.get("source_tiers")),
            ]
        )
        has_live_route = "live_public_web_context" in routes
        has_live_source = "live_public_web_context" in source_families
        if has_live_route or has_live_source:
            normalized_count += 1
            kept_routes = [route for route in routes if route != "live_public_web_context"]
            req["evidence_routes"] = kept_routes
            req["retrieval_routes"] = kept_routes
            replacement_sources = ["public_source_context" if source == "live_public_web_context" else source for source in source_families]
            req["source_families"] = _dedupe(replacement_sources)
            req["source_tiers"] = _dedupe(["public_source_context" if source == "live_public_web_context" else source for source in _string_list(req.get("source_tiers"))])
            if not req["source_tiers"] and "public_source_context" in req["source_families"]:
                req["source_tiers"] = ["public_source_context"]
            normalizations = [dict(item) for item in req.get("normalizations") or [] if isinstance(item, Mapping)]
            normalizations.append(
                {
                    "field": "live_public_web_context",
                    "action": "downgraded_to_public_source_context_without_web_scope_policy",
                    "policy": "research_lead_live_web_requires_explicit_scope_policy_v0_1",
                }
            )
            req["normalizations"] = normalizations
        normalized_requirements.append(req)
    result = dict(evidence_payload)
    result["requirements"] = normalized_requirements
    if normalized_count:
        metadata = dict(result.get("metadata") or {}) if isinstance(result.get("metadata"), Mapping) else {}
        metadata["live_web_downgrade_count"] = normalized_count
        metadata["live_web_downgrade_policy"] = "research_lead_live_web_requires_explicit_scope_policy_v0_1"
        result["metadata"] = metadata
    return result


def _normalize_live_web_activation_for_policy(
    plan: Mapping[str, Any],
    route_request: MultiAgentRouteRequest,
) -> dict[str, Any]:
    if _live_web_scope_policy_allowed(route_request, plan):
        return dict(plan or {})
    normalized = dict(plan or {})
    active = _dedupe([str(agent) for agent in normalized.get("activate_agents") or []])
    allowed_sources = _dedupe([str(source) for source in normalized.get("allowed_source_families") or []])
    if "web_evidence_operator" not in active and "live_public_web_context" not in allowed_sources:
        return normalized
    active = [agent for agent in active if agent != "web_evidence_operator"]
    allowed_sources = ["public_source_context" if source == "live_public_web_context" else source for source in allowed_sources]
    normalized["activate_agents"] = _dedupe(active)
    normalized["allowed_source_families"] = _dedupe(allowed_sources)
    priorities = dict(normalized.get("agent_priorities") or {})
    priorities.pop("web_evidence_operator", None)
    normalized["agent_priorities"] = priorities
    model_policy = dict(normalized.get("model_policy_hint") or {})
    model_policy.pop("web_evidence_operator", None)
    normalized["model_policy_hint"] = model_policy
    metadata = dict(normalized.get("metadata") or {})
    metadata["live_web_downgraded"] = True
    metadata["live_web_downgrade_policy"] = "research_lead_live_web_requires_explicit_scope_policy_v0_1"
    normalized["metadata"] = metadata
    normalized["skip_agents"] = _sync_skip_agents(
        normalized.get("skip_agents"),
        normalized["activate_agents"],
        [
            (
                "web_evidence_operator",
                "Live public web requires explicit web_scope_policy_ids; public source context remains bounded context only.",
            )
        ],
    )
    return normalized


def _normalize_milvus_evidence_payload_for_availability(
    evidence_payload: Mapping[str, Any],
    route_request: MultiAgentRouteRequest,
) -> dict[str, Any]:
    if _milvus_semantic_available(route_request):
        return dict(evidence_payload or {})
    if not isinstance(evidence_payload, Mapping) or not isinstance(evidence_payload.get("requirements"), list):
        return dict(evidence_payload or {})
    normalized_requirements: list[dict[str, Any]] = []
    normalized_count = 0
    for requirement in evidence_payload.get("requirements") or []:
        if not isinstance(requirement, Mapping):
            continue
        req = dict(requirement)
        routes = _string_list(req.get("evidence_routes") or req.get("retrieval_routes"))
        source_families = _dedupe(
            [
                *_string_list(req.get("source_families") or req.get("source_family")),
                *_string_list(req.get("source_tiers")),
            ]
        )
        if "milvus_semantic" in routes or "milvus_semantic" in source_families:
            normalized_count += 1
            kept_routes = [route for route in routes if route != "milvus_semantic"]
            req["evidence_routes"] = kept_routes
            req["retrieval_routes"] = kept_routes
            req["source_families"] = [source for source in source_families if source != "milvus_semantic"]
            req["source_tiers"] = [source for source in _string_list(req.get("source_tiers")) if source != "milvus_semantic"]
            normalizations = [dict(item) for item in req.get("normalizations") or [] if isinstance(item, Mapping)]
            normalizations.append(
                {
                    "field": "milvus_semantic",
                    "action": "removed_when_runtime_unavailable",
                    "policy": "research_lead_milvus_semantic_requires_available_runtime_v0_1",
                }
            )
            req["normalizations"] = normalizations
        normalized_requirements.append(req)
    result = dict(evidence_payload)
    result["requirements"] = normalized_requirements
    if normalized_count:
        metadata = dict(result.get("metadata") or {}) if isinstance(result.get("metadata"), Mapping) else {}
        metadata["milvus_semantic_removed_count"] = normalized_count
        metadata["milvus_semantic_removed_policy"] = "research_lead_milvus_semantic_requires_available_runtime_v0_1"
        result["metadata"] = metadata
    return result


def _normalize_milvus_activation_for_availability(
    plan: Mapping[str, Any],
    route_request: MultiAgentRouteRequest,
) -> dict[str, Any]:
    if _milvus_semantic_available(route_request):
        return dict(plan or {})
    normalized = dict(plan or {})
    allowed_sources = _dedupe([str(source) for source in normalized.get("allowed_source_families") or []])
    if "milvus_semantic" not in allowed_sources:
        return normalized
    normalized["allowed_source_families"] = [source for source in allowed_sources if source != "milvus_semantic"]
    metadata = dict(normalized.get("metadata") or {})
    metadata["milvus_semantic_removed"] = True
    metadata["milvus_semantic_removed_policy"] = "research_lead_milvus_semantic_requires_available_runtime_v0_1"
    metadata["milvus_semantic_gap_boundary"] = "semantic_recall_supplement_unavailable_do_not_use_as_exact_value_authority"
    normalized["metadata"] = metadata
    return normalized


def _normalize_relationship_evidence_payload_for_scope(
    evidence_payload: Mapping[str, Any],
    route_request: MultiAgentRouteRequest,
) -> dict[str, Any]:
    if _requires_sector_depth_relationship_route(route_request):
        return dict(evidence_payload or {})
    if not isinstance(evidence_payload, Mapping) or not isinstance(evidence_payload.get("requirements"), list):
        return dict(evidence_payload or {})
    normalized_requirements: list[dict[str, Any]] = []
    normalized_count = 0
    for requirement in evidence_payload.get("requirements") or []:
        if not isinstance(requirement, Mapping):
            continue
        req = dict(requirement)
        routes = _string_list(req.get("evidence_routes") or req.get("retrieval_routes"))
        sources = _dedupe(
            [
                *_string_list(req.get("source_families") or req.get("source_family")),
                *_string_list(req.get("source_tiers")),
            ]
        )
        if ("relationship_graph" in routes or "relationship_graph" in sources) and not _requirement_mentions_relationship_expansion(req):
            normalized_count += 1
            kept_routes = [route for route in routes if route != "relationship_graph"]
            req["evidence_routes"] = kept_routes
            req["retrieval_routes"] = kept_routes
            req["source_families"] = [source for source in sources if source != "relationship_graph"]
            req["source_tiers"] = [source for source in _string_list(req.get("source_tiers")) if source != "relationship_graph"]
            normalizations = [dict(item) for item in req.get("normalizations") or [] if isinstance(item, Mapping)]
            normalizations.append(
                {
                    "field": "relationship_graph",
                    "action": "removed_without_relationship_scope_intent",
                    "policy": "research_lead_relationship_graph_requires_scope_intent_v0_1",
                }
            )
            req["normalizations"] = normalizations
        normalized_requirements.append(req)
    result = dict(evidence_payload)
    result["requirements"] = normalized_requirements
    if normalized_count:
        metadata = dict(result.get("metadata") or {}) if isinstance(result.get("metadata"), Mapping) else {}
        metadata["relationship_graph_removed_count"] = normalized_count
        metadata["relationship_graph_removed_policy"] = "research_lead_relationship_graph_requires_scope_intent_v0_1"
        result["metadata"] = metadata
    return result


def _normalize_required_role_evidence_payload(
    evidence_payload: Mapping[str, Any],
    route_request: MultiAgentRouteRequest,
) -> dict[str, Any]:
    if not isinstance(evidence_payload, Mapping) or not isinstance(evidence_payload.get("requirements"), list):
        return dict(evidence_payload or {})
    normalized_requirements: list[dict[str, Any]] = []
    normalized_count = 0
    relationship_scope_allowed = _requires_sector_depth_relationship_route(route_request)
    for requirement in evidence_payload.get("requirements") or []:
        if not isinstance(requirement, Mapping):
            continue
        req = dict(requirement)
        routes = _dedupe(_string_list(req.get("evidence_routes") or req.get("retrieval_routes")))
        sources = _dedupe(
            [
                *_string_list(req.get("source_families") or req.get("source_family")),
                *_string_list(req.get("source_tiers")),
            ]
        )
        added: list[str] = []
        if _requirement_matches_required_item(req, "product_architecture_competition"):
            for source in ("company_product_evidence_graph", "public_source_context"):
                if source not in sources:
                    sources.append(source)
                    added.append(source)
        if relationship_scope_allowed and (
            _requirement_matches_required_item(req, "customer_deployment_adoption")
            or _requirement_matches_required_item(req, "supply_chain_readthrough")
        ):
            if "relationship_graph" not in routes:
                routes.append("relationship_graph")
                added.append("relationship_graph")
            if "relationship_graph" not in sources:
                sources.append("relationship_graph")
                added.append("relationship_graph")
        if _requirement_matches_required_item(req, "capital_market_price_in"):
            if "market_snapshot" not in routes:
                routes.append("market_snapshot")
                added.append("market_snapshot")
            if "market_snapshot" not in sources:
                sources.append("market_snapshot")
                added.append("market_snapshot")
        if added:
            normalized_count += 1
            req["evidence_routes"] = _dedupe(routes)
            req["retrieval_routes"] = _dedupe(routes)
            req["source_families"] = _dedupe(sources)
            req["source_tiers"] = _dedupe([*_string_list(req.get("source_tiers")), *sources])
            normalizations = [dict(item) for item in req.get("normalizations") or [] if isinstance(item, Mapping)]
            normalizations.append(
                {
                    "field": "evidence_requirement_role_routes",
                    "action": "added_required_role_sources_or_routes",
                    "added": _dedupe(added),
                    "policy": "research_lead_required_item_routes_must_survive_to_runtime_v0_1",
                }
            )
            req["normalizations"] = normalizations
        normalized_requirements.append(req)
    result = dict(evidence_payload)
    result["requirements"] = normalized_requirements
    if normalized_count:
        metadata = dict(result.get("metadata") or {}) if isinstance(result.get("metadata"), Mapping) else {}
        metadata["required_role_route_normalization_count"] = normalized_count
        metadata["required_role_route_normalization_policy"] = "research_lead_required_item_routes_must_survive_to_runtime_v0_1"
        result["metadata"] = metadata
    return result


def _normalize_relationship_activation_for_scope(
    plan: Mapping[str, Any],
    route_request: MultiAgentRouteRequest,
) -> dict[str, Any]:
    if _requires_sector_depth_relationship_route(route_request):
        return dict(plan or {})
    normalized = dict(plan or {})
    active = _dedupe([str(agent) for agent in normalized.get("activate_agents") or []])
    allowed_sources = _dedupe([str(source) for source in normalized.get("allowed_source_families") or []])
    if "universe_relationship" not in active and "relationship_graph" not in allowed_sources:
        return normalized
    active = [agent for agent in active if agent != "universe_relationship"]
    allowed_sources = [source for source in allowed_sources if source != "relationship_graph"]
    normalized["activate_agents"] = active
    normalized["allowed_source_families"] = allowed_sources
    normalized["relationship_scope_rationale"] = ""
    priorities = dict(normalized.get("agent_priorities") or {})
    priorities.pop("universe_relationship", None)
    normalized["agent_priorities"] = priorities
    model_policy = dict(normalized.get("model_policy_hint") or {})
    model_policy.pop("universe_relationship", None)
    normalized["model_policy_hint"] = model_policy
    normalized["skip_agents"] = _sync_skip_agents(
        normalized.get("skip_agents"),
        active,
        [
            (
                "universe_relationship",
                "Relationship graph requires explicit relationship/supply-chain scope intent or relationship_graph source in the user/query contract.",
            )
        ],
    )
    metadata = dict(normalized.get("metadata") or {})
    metadata["relationship_overroute_pruned"] = True
    metadata["relationship_overroute_policy"] = "research_lead_relationship_graph_requires_scope_intent_v0_1"
    normalized["metadata"] = metadata
    return normalized


def _milvus_semantic_available(route_request: MultiAgentRouteRequest) -> bool:
    inventory = route_request.source_inventory if isinstance(route_request.source_inventory, Mapping) else {}
    if not inventory:
        return True
    milvus = inventory.get("milvus_runtime") if isinstance(inventory.get("milvus_runtime"), Mapping) else {}
    availability = inventory.get("source_family_availability") if isinstance(inventory.get("source_family_availability"), Mapping) else {}
    milvus_availability = availability.get("milvus_semantic") if isinstance(availability.get("milvus_semantic"), Mapping) else {}
    if not milvus and not milvus_availability:
        available_families = set(
            _string_list(
                inventory.get("available_source_families")
                or inventory.get("allowed_source_families")
                or inventory.get("source_families")
                or inventory.get("source_tiers")
            )
        )
        return "milvus_semantic" in available_families
    status = str(milvus.get("status") or milvus_availability.get("status") or "").strip()
    if status == "unavailable":
        return False
    if "available" in milvus:
        return bool(milvus.get("available"))
    if "available" in milvus_availability:
        return bool(milvus_availability.get("available"))
    return False


def _live_web_scope_policy_allowed(
    route_request: MultiAgentRouteRequest,
    plan: Mapping[str, Any] | None = None,
) -> bool:
    activation = dict(plan or {})
    metadata = activation.get("metadata") if isinstance(activation.get("metadata"), Mapping) else {}
    contract = _context_query_contract(route_request)
    requested_policy_ids = _string_list(
        activation.get("web_scope_policy_ids")
        or metadata.get("web_scope_policy_ids")
        or metadata.get("web_scope_policy_id")
        or route_request.context.get("web_scope_policy_ids")
        or route_request.context.get("web_scope_policy_id")
        or contract.get("web_scope_policy_ids")
        or contract.get("web_scope_policy_id")
    )
    if not requested_policy_ids:
        return False
    inventory = route_request.source_inventory if isinstance(route_request.source_inventory, Mapping) else {}
    live_web = inventory.get("live_public_web_context") if isinstance(inventory.get("live_public_web_context"), Mapping) else {}
    inventory_policy_ids = set(_string_list(live_web.get("web_scope_policy_ids")))
    return not inventory_policy_ids or set(requested_policy_ids).issubset(inventory_policy_ids)


def _query_contract_for_evidence(
    route_request: MultiAgentRouteRequest,
    activation_plan: Mapping[str, Any],
    evidence_payload: Mapping[str, Any],
) -> dict[str, Any]:
    contract = _context_query_contract(route_request)
    contract["focus_tickers"] = route_request.focus_tickers or contract.get("focus_tickers") or []
    contract["search_scope_tickers"] = route_request.search_scope_tickers or contract.get("search_scope_tickers") or contract["focus_tickers"]
    allowed_sources = set(_string_list(activation_plan.get("allowed_source_families")))
    evidence_sources = _evidence_payload_requested_source_families(evidence_payload)
    if contract.get("source_tiers") and allowed_sources:
        contract["source_tiers"] = _dedupe(
            [
                *[source for source in _string_list(contract.get("source_tiers")) if source in allowed_sources],
                *[source for source in evidence_sources if source in allowed_sources],
            ]
        )
    else:
        contract["source_tiers"] = _dedupe(
            [
                *[source for source in evidence_sources if not allowed_sources or source in allowed_sources],
                *list(activation_plan.get("allowed_source_families") or []),
            ]
        )
    if contract.get("source_families") and allowed_sources:
        contract["source_families"] = _dedupe(
            [
                *[source for source in _string_list(contract.get("source_families")) if source in allowed_sources],
                *[source for source in evidence_sources if source in allowed_sources],
            ]
        )
    elif evidence_sources:
        contract["source_families"] = [source for source in evidence_sources if not allowed_sources or source in allowed_sources]
    if isinstance(evidence_payload.get("requirements"), list) and evidence_payload.get("requirements"):
        contract["evidence_requirement_plan"] = {"requirements": list(evidence_payload.get("requirements") or [])}
    elif isinstance(evidence_payload, Mapping):
        contract["evidence_requirement_plan"] = dict(evidence_payload)
    return contract


def _evidence_payload_requested_source_families(evidence_payload: Mapping[str, Any]) -> list[str]:
    sources: list[str] = []
    requirements = evidence_payload.get("requirements") if isinstance(evidence_payload, Mapping) else []
    for requirement in requirements or []:
        if not isinstance(requirement, Mapping):
            continue
        sources.extend(_string_list(requirement.get("source_families") or requirement.get("source_family")))
        sources.extend(_string_list(requirement.get("source_tiers") or requirement.get("source_tier")))
        for route in _string_list(requirement.get("evidence_routes") or requirement.get("retrieval_routes")):
            source_family = ROUTE_SOURCE_FAMILY.get(route)
            if source_family:
                sources.append(source_family)
    return _dedupe(sources)


def _context_query_contract(route_request: MultiAgentRouteRequest) -> dict[str, Any]:
    contract = route_request.context.get("query_contract") if isinstance(route_request.context.get("query_contract"), Mapping) else {}
    return dict(contract or {})


def _research_lead_input_pack_fingerprint(
    route_request: MultiAgentRouteRequest,
    *,
    loop_budget: LoopBudget,
) -> dict[str, Any]:
    """Persist digest-only Research Lead input lineage for token audits.

    This deliberately does not store prompt text. It records enough component
    shape and evidence-ref lineage for AIE to diagnose overbroad planning
    inputs and repeated context transfer.
    """

    components: dict[str, Any] = {
        "request_scope": {
            "user_query_chars": len(str(route_request.user_query or "")),
            "focus_tickers": list(route_request.focus_tickers),
            "search_scope_tickers": list(route_request.search_scope_tickers),
        },
        "source_inventory": _compact_source_inventory_for_prompt(route_request.source_inventory),
        "context": _compact_context_for_prompt(route_request.context),
        "loop_budget": loop_budget.to_dict(),
        "agent_registry": _compact_agent_registry_for_prompt(),
        "route_choice_policy": _route_choice_policy_prompt(),
    }
    summaries = {
        name: _input_pack_component_summary(component)
        for name, component in components.items()
    }
    known_refs = _dedupe(
        [
            ref
            for component in components.values()
            for ref in _input_pack_evidence_refs(component)
        ]
    )
    digest_payload = {
        "component_digests": {name: summary.get("digest") for name, summary in summaries.items()},
        "focus_tickers": route_request.focus_tickers,
        "search_scope_tickers": route_request.search_scope_tickers,
        "known_evidence_refs": known_refs,
    }
    return {
        "schema_version": RESEARCH_LEAD_INPUT_PACK_FINGERPRINT_SCHEMA_VERSION,
        "agent_id": "research_lead",
        "digest": _fingerprint_digest(digest_payload),
        "component_summaries": summaries,
        "known_evidence_ref_count": len(known_refs),
        "known_evidence_refs": known_refs[:256],
        "known_evidence_refs_truncated": len(known_refs) > 256,
        "approx_prompt_payload_chars": sum(int(summary.get("approx_chars") or 0) for summary in summaries.values()),
        "focus_ticker_count": len(route_request.focus_tickers),
        "search_scope_ticker_count": len(route_request.search_scope_tickers),
        "fingerprint_policy": "fingerprint_only_no_prompt_text_persisted_v0_1",
    }


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


def _input_pack_component_summary(value: Any) -> dict[str, Any]:
    refs = _input_pack_evidence_refs(value)
    return {
        "digest": _fingerprint_digest(value),
        "item_count": _input_pack_item_count(value),
        "evidence_ref_count": len(refs),
        "approx_chars": len(json.dumps(_clean_for_fingerprint(value), ensure_ascii=False, sort_keys=True)),
    }


def _input_pack_item_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, tuple):
        return len(value)
    if isinstance(value, Mapping):
        preferred_keys = (
            "requirements",
            "playbook_candidates",
            "available_tickers",
            "source_families",
            "source_family_availability",
            "companies",
            "agents",
            "routes",
        )
        counts = [
            len(value.get(key) or [])
            for key in preferred_keys
            if isinstance(value.get(key), (list, tuple))
        ]
        return sum(counts) if counts else len(value)
    return 0 if value is None or value == "" else 1


def _input_pack_evidence_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, Mapping):
        for key in (
            "evidence_refs",
            "refs",
            "supporting_evidence_ids",
            "evidence_ref",
            "evidence_id",
            "source_id",
        ):
            refs.extend(_string_list(value.get(key)))
        for item in value.values():
            if isinstance(item, (Mapping, list, tuple)):
                refs.extend(_input_pack_evidence_refs(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            refs.extend(_input_pack_evidence_refs(item))
    return _dedupe(refs)


def _fingerprint_digest(value: Any) -> str:
    text = json.dumps(_clean_for_fingerprint(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _clean_for_fingerprint(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _model_call_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status"),
        "call_id": result.get("call_id"),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "proxy_mode": result.get("proxy_mode"),
        "url": result.get("url"),
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


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [value]


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


def _insert_before(values: list[str], new_value: str, before_value: str) -> list[str]:
    result = [value for value in values if value != new_value]
    try:
        index = result.index(before_value)
    except ValueError:
        result.append(new_value)
    else:
        result.insert(index, new_value)
    return result


def _sync_skip_agents(value: Any, active: list[str], additions: list[tuple[str, str]]) -> list[dict[str, str]]:
    active_set = set(active)
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value or []:
        if not isinstance(item, Mapping):
            continue
        agent_id = str(item.get("agent_id") or item.get("agent") or "").strip()
        if not agent_id or agent_id in active_set or agent_id in seen:
            continue
        reason = str(item.get("reason") or "").strip() or "Inactive under current route policy."
        result.append({"agent_id": agent_id, "reason": reason})
        seen.add(agent_id)
    for agent_id, reason in additions:
        if not agent_id or agent_id in active_set or agent_id in seen:
            continue
        result.append({"agent_id": agent_id, "reason": reason})
        seen.add(agent_id)
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
