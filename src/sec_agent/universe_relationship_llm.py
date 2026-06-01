from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from sec_agent.llm_gateway import chat_completion
from sec_agent.multi_agent_contracts import (
    validate_economic_link_map,
    normalize_universe_relationship_plan,
    validate_universe_relationship_plan,
)
from sec_agent.relationship_graph import relationship_plan_from_lookup
from sec_agent.research_skills import research_skill_prompt


ROUTE_SCHEMA_VERSION = "sec_agent_universe_relationship_llm_route_v0.1"
ROUTE_SOURCE = "universe_relationship_llm_v0.1"
UNIVERSE_ROUTER_ENV = "SEC_AGENT_MULTI_AGENT_UNIVERSE_ROUTER"

ChatCompletionFunc = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class UniverseRelationshipLLMConfig:
    llm_backend: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    chat_completions_path: str = "/chat/completions"
    model: str = "deepseek-v4-pro"
    api_key_env: str = "DEEPSEEK_API_KEY"
    temperature: float = 0.0
    max_tokens: int = 3000
    timeout_s: int = 180
    max_repair_attempts: int = 2
    input_max_relationships: int = 8
    require_economic_link_map: bool = False


def universe_relationship_llm_config_from_env(env: Mapping[str, str] | None = None) -> UniverseRelationshipLLMConfig:
    values = dict(os.environ if env is None else env)
    return UniverseRelationshipLLMConfig(
        llm_backend=values.get("LLM_BACKEND", "deepseek"),
        base_url=values.get("BASE_URL", "https://api.deepseek.com"),
        chat_completions_path=values.get("CHAT_COMPLETIONS_PATH", "/chat/completions"),
        model=values.get("MODEL_NAME", "deepseek-v4-pro"),
        api_key_env=values.get("API_KEY_ENV", "DEEPSEEK_API_KEY"),
        temperature=_float_env(values.get("UNIVERSE_TEMPERATURE"), default=0.0),
        max_tokens=_int_env(values.get("UNIVERSE_MAX_TOKENS"), default=3000),
        timeout_s=_int_env(values.get("UNIVERSE_TIMEOUT_S"), default=180),
        max_repair_attempts=_int_env(values.get("UNIVERSE_MAX_REPAIR_ATTEMPTS"), default=2),
        input_max_relationships=_int_env(values.get("UNIVERSE_INPUT_MAX_RELATIONSHIPS"), default=8),
        require_economic_link_map=str(values.get("UNIVERSE_REQUIRE_ECONOMIC_LINK_MAP") or "").lower() in {"1", "true", "yes"},
    )


def route_universe_relationship_from_env(
    env: Mapping[str, str] | None = None,
    *,
    call_chat_completion: ChatCompletionFunc = chat_completion,
) -> Callable[[Mapping[str, Any]], dict[str, Any]] | None:
    values = dict(os.environ if env is None else env)
    mode = str(values.get(UNIVERSE_ROUTER_ENV) or "mock").strip().lower()
    if mode in {"", "mock", "deterministic", "off", "false", "0"}:
        return None
    if mode not in {"llm", "deepseek", "api"}:
        raise ValueError(f"unsupported {UNIVERSE_ROUTER_ENV}: {mode}")
    config = universe_relationship_llm_config_from_env(values)

    def _route(state: Mapping[str, Any]) -> dict[str, Any]:
        lookup = state.get("relationship_graph_observation") if isinstance(state.get("relationship_graph_observation"), Mapping) else {}
        activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
        request = {
            "user_query": state.get("user_query") or "",
            "activation_plan": activation,
            "relationship_lookup": lookup,
            "source_inventory": state.get("project_inventory") or state.get("source_inventory") or {},
        }
        return route_universe_relationship_llm(
            request,
            config=config,
            call_chat_completion=call_chat_completion,
        )

    return _route


def route_universe_relationship_llm(
    request: Mapping[str, Any],
    *,
    config: UniverseRelationshipLLMConfig | None = None,
    call_chat_completion: ChatCompletionFunc = chat_completion,
) -> dict[str, Any]:
    route_config = config or UniverseRelationshipLLMConfig()
    raw_lookup = request.get("relationship_lookup") if isinstance(request.get("relationship_lookup"), Mapping) else {}
    activation = request.get("activation_plan") if isinstance(request.get("activation_plan"), Mapping) else {}
    source_inventory = request.get("source_inventory") if isinstance(request.get("source_inventory"), Mapping) else {}
    lookup = _compact_relationship_lookup(
        raw_lookup,
        source_inventory=source_inventory,
        max_relationships=route_config.input_max_relationships,
        priority_tickers=_string_list(activation.get("search_scope_tickers") or activation.get("focus_tickers")),
    )
    focus = _string_list(activation.get("focus_tickers") or lookup.get("focus_tickers"))
    known_refs = _known_relationship_refs(lookup)
    max_repair_attempts = max(0, int(route_config.max_repair_attempts))
    prompt_request = {**dict(request), "relationship_lookup": lookup}

    model_calls: list[dict[str, Any]] = []
    previous_content = ""
    last_failure: dict[str, Any] = {"type": "not_run"}
    last_validation: dict[str, Any] | None = None
    for attempt_index in range(max_repair_attempts + 1):
        messages = _build_messages(
            prompt_request,
            known_refs=known_refs,
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
            role="universe_relationship",
            profile="balanced",
            trace_tags={"route_source": ROUTE_SOURCE, "repair_attempt": attempt_index},
        )
        model_calls.append(_model_call_summary(llm_result))
        previous_content = str(llm_result.get("content") or "")
        if llm_result.get("status") != "ok":
            last_failure = {"type": "provider_error", "reason": str(llm_result.get("failure_reason") or "")}
            break
        if llm_result.get("tool_calls"):
            last_failure = {
                "type": "direct_tool_call_forbidden",
                "detail": "Universe Relationship may use relationship lookup input only; direct tool calls are forbidden.",
            }
            continue
        parsed = extract_universe_relationship_plan_json(previous_content)
        if parsed is None:
            last_failure = {"type": "json_parse_failed", "detail": "No UniverseRelationshipPlan JSON object was found."}
            continue
        validation = validate_universe_relationship_plan(parsed, known_evidence_refs=known_refs, source_inventory=source_inventory)
        last_validation = validation
        if validation["status"] == "pass":
            if _lookup_relationships_present(lookup) and not _plan_relationships_present(validation.get("plan")):
                last_failure = {
                    "type": "relationship_lookup_rows_dropped",
                    "detail": "Relationship lookup returned bounded relationship rows, but the model plan omitted all relationships.",
                }
                continue
            if route_config.require_economic_link_map:
                link_validation = validate_economic_link_map(
                    (validation.get("plan") or {}).get("economic_link_map") if isinstance(validation.get("plan"), Mapping) else {},
                    known_evidence_refs=known_refs,
                    allowed_tickers=set(_string_list((validation.get("plan") or {}).get("included_tickers") if isinstance(validation.get("plan"), Mapping) else [])),
                )
                if link_validation["status"] != "pass":
                    last_failure = {
                        "type": "economic_link_map_validation_failed",
                        "errors": link_validation["errors"],
                        "warnings": link_validation["warnings"],
                    }
                    continue
            return {
                "schema_version": ROUTE_SCHEMA_VERSION,
                "source": ROUTE_SOURCE,
                "status": "pass",
                "universe_relationship_plan": validation["plan"],
                "universe_relationship_validation": validation,
                "routing_trace": {"attempt_count": len(model_calls), "repair_attempts": attempt_index},
                "model_diagnostics": _aggregate_model_calls(model_calls),
                "failure_reason": "",
            }
        last_failure = {"type": "validation_failed", "errors": validation["errors"], "warnings": validation["warnings"]}

    fallback = relationship_plan_from_lookup(
        lookup,
        scope_mode=str(activation.get("scope_mode") or "focused_peer"),
        focus_tickers=focus,
        relationship_scope_rationale=str(activation.get("relationship_scope_rationale") or ""),
    )
    fallback_validation = validate_universe_relationship_plan(
        normalize_universe_relationship_plan(fallback),
        known_evidence_refs=known_refs,
        source_inventory=source_inventory,
    )
    return {
        "schema_version": ROUTE_SCHEMA_VERSION,
        "source": f"{ROUTE_SOURCE}+deterministic_fallback",
        "status": "fallback" if fallback_validation["status"] == "pass" else "fail",
        "universe_relationship_plan": fallback_validation.get("plan") or {},
        "universe_relationship_validation": fallback_validation,
        "rejected_plan": (last_validation or {}).get("plan") or {},
        "routing_trace": {"attempt_count": len(model_calls), "repair_attempts": max(0, len(model_calls) - 1), "fallback_used": True},
        "model_diagnostics": _aggregate_model_calls(model_calls),
        "failure_reason": _format_failure_reason(last_failure),
    }


def _lookup_relationships_present(lookup: Mapping[str, Any]) -> bool:
    return bool(lookup.get("relationships") or lookup.get("relationship_rows"))


def _plan_relationships_present(plan: Any) -> bool:
    return isinstance(plan, Mapping) and bool(plan.get("relationships"))


def extract_universe_relationship_plan_json(text: str) -> dict[str, Any] | None:
    for candidate in _json_candidates(str(text or "")):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _build_messages(
    request: Mapping[str, Any],
    *,
    known_refs: set[str],
    prior_failure: Mapping[str, Any] | None,
    prior_content: str,
) -> list[dict[str, str]]:
    system = _system_prompt()
    activation = request.get("activation_plan") if isinstance(request.get("activation_plan"), Mapping) else {}
    lookup = request.get("relationship_lookup") if isinstance(request.get("relationship_lookup"), Mapping) else {}
    user_payload = {
        "user_query": request.get("user_query") or "",
        "scope_mode": activation.get("scope_mode") or "",
        "focus_tickers": activation.get("focus_tickers") or lookup.get("focus_tickers") or [],
        "search_scope_tickers": activation.get("search_scope_tickers") or lookup.get("included_tickers") or [],
        "relationship_scope_rationale": activation.get("relationship_scope_rationale") or "",
        "relationship_lookup": {
            "status": lookup.get("status") or "",
            "relationships": lookup.get("relationships") or [],
            "source_gaps": lookup.get("source_gaps") or [],
            "summary": lookup.get("summary") or {},
        },
        "known_relationship_refs": sorted(known_refs),
    }
    user = (
        "Return one UniverseRelationshipPlan JSON object from the bounded relationship lookup only. "
        "Do not add named companies or relationships from memory. "
        "included_tickers may contain only focus_tickers and tickers that have relationship evidence_refs in the input. "
        "Search-scope tickers without input relationship rows must be excluded or listed as unsupported_relationships. "
        "Keep the JSON compact: at most 4 relationships, 6 entities, 4 economic links, 2 mechanisms, and 2 investment_implications. "
        "Use short strings; do not narrate evidence rows.\n\n"
        f"Input JSON:\n{json.dumps(user_payload, ensure_ascii=False, indent=2)}"
    )
    if prior_failure:
        user = (
            f"{user}\n\nRepair the previous output. It failed this diagnostic:\n"
            f"{json.dumps(_clean_for_prompt(prior_failure), ensure_ascii=False, sort_keys=True)}\n\n"
            f"Previous output excerpt:\n{_truncate(prior_content, 1600)}\n\n"
            "Return one corrected UniverseRelationshipPlan JSON object only."
        )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _system_prompt() -> str:
    schema_hint = {
        "schema_version": "sec_agent_universe_relationship_plan_v0.1",
        "agent_id": "universe_relationship",
        "scope_mode": "focused_peer | sector_representative | full_universe",
        "focus_tickers": ["TICKER"],
        "expanded_tickers": ["TICKER"],
        "included_tickers": ["TICKER"],
        "excluded_tickers": [],
        "relationship_scope_rationale": "short rationale",
        "relationships": [
            {
                "ticker": "TICKER",
                "related_ticker": "TICKER",
                "relationship_type": "peer | competitor | customer | supplier | sector | macro_sensitive | other",
                "direction": "short direction",
                "financial_link_type": "short link type",
                "metrics_to_check": ["metric"],
                "evidence_source_needed": ["primary_sec_filing | market_snapshot | industry_snapshot | relationship_graph"],
                "evidence_refs": ["relationship evidence ref"],
                "confidence": "low | medium | high",
                "inclusion_rationale": "why included for research scope",
                "claim_scope": "scope_or_hypothesis_only",
            }
        ],
        "economic_link_map": {
            "schema_version": "sec_agent_economic_link_map_v0.1",
            "map_scope": "relationship_hypothesis",
            "focus_tickers": ["TICKER"],
            "entities": [
                {
                    "ticker": "TICKER",
                    "role": "direct_beneficiary | peer | second_order_beneficiary | risk_exposure",
                    "evidence_refs": ["relationship evidence ref"],
                    "confidence": "low | medium | high",
                    "materiality": "low | medium | high",
                    "missing_confirmations": ["missing confirmation"],
                }
            ],
            "links": [
                {
                    "source": "TICKER or economic driver",
                    "target": "TICKER",
                    "link_type": "peer | demand_driver | second_order_beneficiary | substitution | macro_regulatory | sector_hypothesis | unknown",
                    "mechanism": "economic transmission mechanism",
                    "direction": "positive | negative | mixed | neutral | unknown",
                    "materiality": "low | medium | high",
                    "confidence": "low | medium | high",
                    "metric_implications": ["metric"],
                    "evidence_refs": ["relationship evidence ref"],
                    "claim_scope": "economic_mechanism_hypothesis_only",
                    "missing_confirmations": ["missing confirmation"],
                }
            ],
            "mechanisms": [
                {
                    "driver": "economic driver",
                    "affected_entities": ["TICKER"],
                    "metric_implications": ["metric"],
                    "confirming_indicators": ["indicator"],
                    "disconfirming_indicators": ["indicator"],
                    "evidence_refs": ["relationship evidence ref"],
                    "confidence": "low | medium | high",
                }
            ],
            "investment_implications": [
                {
                    "claim": "bounded implication",
                    "so_what": "why this matters for the research memo",
                    "entity_scope": ["TICKER"],
                    "confidence": "low | medium | high",
                    "supporting_refs": ["relationship evidence ref"],
                    "missing_confirmations": ["missing confirmation"],
                }
            ],
            "source_boundary": "relationship_graph_hypothesis_only",
        },
        "unsupported_relationships": [],
        "source_family": "relationship_graph",
    }
    return "\n\n".join(
        [
            "You are the Universe / Relationship Agent for a SEC investment research multi-agent graph.",
            research_skill_prompt("universe_relationship", max_chars=4200),
            "Return exactly one JSON object. Do not wrap it in prose. Do not call tools.",
            "Relationship evidence can support scope and hypotheses only, never company financial facts.",
            "Fill economic_link_map from the same bounded relationship refs. It must explain entity roles, economic links, mechanisms, metrics to verify, missing confirmations, and bounded investment implications.",
            f"UniverseRelationshipPlan schema hint:\n{json.dumps(schema_hint, ensure_ascii=False, indent=2)}",
        ]
    )


def _known_relationship_refs(lookup: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    for relationship in lookup.get("relationships") or []:
        if isinstance(relationship, Mapping):
            refs.update(_string_list(relationship.get("evidence_refs") or relationship.get("refs")))
    return refs


def _compact_relationship_lookup(
    lookup: Mapping[str, Any],
    *,
    source_inventory: Mapping[str, Any],
    max_relationships: int,
    priority_tickers: list[str] | None = None,
) -> dict[str, Any]:
    inventory = _inventory_tickers(source_inventory)
    focus = _unique_upper(lookup.get("focus_tickers"))
    focus_upper = set(focus)
    priority_upper = {ticker.upper().strip() for ticker in _string_list(priority_tickers) if ticker}
    requested_non_focus = priority_upper - focus_upper
    relationships: list[dict[str, Any]] = []
    raw_relationships = [
        item
        for item in lookup.get("relationships") or []
        if isinstance(item, Mapping)
    ]
    prioritized = sorted(
        enumerate(raw_relationships),
        key=lambda item: _relationship_priority_key(
            item[1],
            index=item[0],
            focus_tickers=focus_upper,
            requested_non_focus_tickers=requested_non_focus,
            priority_tickers=priority_upper,
        ),
    )
    for _, relationship in prioritized:
        if not isinstance(relationship, Mapping):
            continue
        ticker = str(relationship.get("ticker") or "").upper().strip()
        related = str(relationship.get("related_ticker") or "").upper().strip()
        if inventory and ((ticker and ticker not in inventory) or (related and related not in inventory)):
            continue
        compact = {
            "ticker": ticker,
            "related_ticker": related,
            "relationship_type": str(relationship.get("relationship_type") or "other"),
            "direction": str(relationship.get("direction") or "unknown"),
            "financial_link_type": str(relationship.get("financial_link_type") or ""),
            "metrics_to_check": _string_list(relationship.get("metrics_to_check"))[:6],
            "evidence_source_needed": _string_list(relationship.get("evidence_source_needed"))[:5],
            "evidence_refs": _string_list(relationship.get("evidence_refs"))[:4],
            "confidence": str(relationship.get("confidence") or "medium"),
            "inclusion_rationale": _truncate(str(relationship.get("inclusion_rationale") or relationship.get("notes") or ""), 260),
            "claim_scope": "scope_or_hypothesis_only",
        }
        relationships.append(compact)
        if len(relationships) >= max(1, max_relationships):
            break
    expanded = _unique_upper(
        [
            ticker
            for row in relationships
            for ticker in (row.get("ticker"), row.get("related_ticker"))
            if ticker and str(ticker).upper() not in focus_upper
        ]
    )
    included = _unique_upper([*focus, *expanded])
    return {
        "status": lookup.get("status") or "",
        "relationships": relationships,
        "source_gaps": lookup.get("source_gaps") or [],
        "summary": {
            **dict(lookup.get("summary") or {}),
            "relationship_count_input": len(relationships),
            "relationship_count_original": len(lookup.get("relationships") or []),
            "source_inventory_pruned": bool(inventory),
        },
        "focus_tickers": _unique_upper(lookup.get("focus_tickers")),
        "expanded_tickers": expanded,
        "included_tickers": included,
    }


def _relationship_priority_key(
    relationship: Mapping[str, Any],
    *,
    index: int,
    focus_tickers: set[str],
    requested_non_focus_tickers: set[str],
    priority_tickers: set[str],
) -> tuple[int, int]:
    ticker = str(relationship.get("ticker") or "").upper().strip()
    related = str(relationship.get("related_ticker") or "").upper().strip()
    endpoints = {item for item in (ticker, related) if item}
    focus_hits = endpoints & focus_tickers
    requested_hits = endpoints & requested_non_focus_tickers
    priority_hits = endpoints & priority_tickers
    if len(focus_hits) >= 2:
        tier = 0
    elif focus_hits and requested_hits:
        tier = 1
    elif requested_hits:
        tier = 2
    elif focus_hits:
        tier = 3
    elif priority_hits:
        tier = 4
    else:
        tier = 5
    return (tier, index)


def _inventory_tickers(source_inventory: Mapping[str, Any]) -> set[str]:
    tickers: list[str] = []
    for key in ("available_tickers", "tickers", "source_inventory_companies"):
        tickers.extend(_string_list(source_inventory.get(key)))
    for company in source_inventory.get("companies") or []:
        if isinstance(company, Mapping):
            tickers.extend(_string_list(company.get("ticker") or company.get("symbol")))
        else:
            tickers.extend(_string_list(company))
    return set(_unique_upper(tickers))


def _unique_upper(value: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in _string_list(value):
        text = item.upper().strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


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
        "calls": calls,
        "raw_response_saved": False,
    }


def _sum_optional_int(rows: list[dict[str, Any]], key: str) -> int | None:
    values = [row.get(key) for row in rows if row.get(key) is not None]
    if not values:
        return None
    return sum(int(value) for value in values)


def _format_failure_reason(failure: Mapping[str, Any]) -> str:
    failure_type = str(failure.get("type") or "unknown_failure")
    if failure_type == "validation_failed":
        return f"validation_failed: {json.dumps(failure.get('errors') or [], ensure_ascii=False)[:700]}"
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
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _int_env(value: str | None, *, default: int) -> int:
    try:
        return int(value) if value not in {None, ""} else default
    except (TypeError, ValueError):
        return default


def _float_env(value: str | None, *, default: float) -> float:
    try:
        return float(value) if value not in {None, ""} else default
    except (TypeError, ValueError):
        return default
