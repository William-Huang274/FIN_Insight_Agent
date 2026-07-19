from __future__ import annotations

import hashlib
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
UNIVERSE_RELATIONSHIP_INPUT_PACK_FINGERPRINT_SCHEMA_VERSION = "sec_agent_universe_relationship_input_pack_fingerprint_v0_1"
DEFAULT_UNIVERSE_MAX_TOKENS = 500
DEFAULT_UNIVERSE_TIMEOUT_S = 90

ChatCompletionFunc = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class UniverseRelationshipLLMConfig:
    llm_backend: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    chat_completions_path: str = "/chat/completions"
    model: str = "deepseek-v4-pro"
    api_key_env: str = "DEEPSEEK_API_KEY"
    temperature: float = 0.0
    max_tokens: int = DEFAULT_UNIVERSE_MAX_TOKENS
    timeout_s: int = DEFAULT_UNIVERSE_TIMEOUT_S
    max_repair_attempts: int = 0
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
        max_tokens=_int_env(values.get("UNIVERSE_MAX_TOKENS"), default=DEFAULT_UNIVERSE_MAX_TOKENS),
        timeout_s=_int_env(values.get("UNIVERSE_TIMEOUT_S"), default=DEFAULT_UNIVERSE_TIMEOUT_S),
        max_repair_attempts=_int_env(values.get("UNIVERSE_MAX_REPAIR_ATTEMPTS"), default=0),
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
    prompt_lookup = _relationship_lookup_prompt_view(lookup)
    focus = _string_list(activation.get("focus_tickers") or lookup.get("focus_tickers"))
    known_refs = _known_relationship_refs(lookup)
    max_repair_attempts = max(0, int(route_config.max_repair_attempts))
    prompt_request = {**dict(request), "relationship_lookup": prompt_lookup}
    input_pack_fingerprint = _universe_relationship_input_pack_fingerprint(
        prompt_request,
        known_refs=known_refs,
        source_inventory=source_inventory,
    )

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
        completed = _complete_plan_from_lookup(
            parsed,
            lookup=lookup,
            scope_mode=str(activation.get("scope_mode") or "focused_peer"),
            focus_tickers=focus,
            relationship_scope_rationale=str(activation.get("relationship_scope_rationale") or ""),
        )
        completed = _complete_economic_link_map_from_lookup(completed, lookup=lookup, focus_tickers=focus)
        validation = validate_universe_relationship_plan(completed, known_evidence_refs=known_refs, source_inventory=source_inventory)
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
                "input_pack_fingerprint": input_pack_fingerprint,
                "failure_reason": "",
            }
        last_failure = {"type": "validation_failed", "errors": validation["errors"], "warnings": validation["warnings"]}

    fallback = relationship_plan_from_lookup(
        lookup,
        scope_mode=str(activation.get("scope_mode") or "focused_peer"),
        focus_tickers=focus,
        relationship_scope_rationale=str(activation.get("relationship_scope_rationale") or ""),
    )
    fallback_plan = normalize_universe_relationship_plan(fallback)
    fallback_plan = _complete_economic_link_map_from_lookup(fallback_plan, lookup=lookup, focus_tickers=focus)
    fallback_validation = validate_universe_relationship_plan(
        fallback_plan,
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
        "input_pack_fingerprint": input_pack_fingerprint,
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
        "Return one compact UniverseRelationshipPlan JSON object as a mechanism overlay. "
        "The runtime, not you, is responsible for preserving who is related to whom. "
        "Do not add named companies or relationships from memory. "
        "included_tickers may contain only focus_tickers and tickers that have relationship evidence_refs in the input. "
        "Search-scope tickers without input relationship rows must be excluded or listed as unsupported_relationships. "
        "Return only the minimal top-level keys needed for a merge overlay: relationship_scope_rationale, economic_link_map, unsupported_relationships. "
        "Set relationships to [] if you include the key at all; the runtime will deterministically preserve every bounded lookup relationship in the final plan. "
        "Spend tokens only on economic_link_map: why the relationship matters, transmission mechanism, metric implications, risks, and missing confirmations. "
        "Keep economic_link_map compact: at most 4 entities, 3 economic links, 2 mechanisms, and 2 investment_implications. "
        "Use short strings; do not narrate evidence rows; keep the whole JSON concise. "
        "Every sector_inferred relationship is not a confirmed direct commercial edge and must carry missing_confirmations.\n\n"
        f"Input JSON:\n{_json_for_prompt(user_payload)}"
    )
    if prior_failure:
        user = (
            f"{user}\n\nRepair the previous output. It failed this diagnostic:\n"
            f"{_json_for_prompt(_clean_for_prompt(prior_failure), sort_keys=True)}\n\n"
            f"Previous output excerpt:\n{_truncate(prior_content, 1600)}\n\n"
            "Return one corrected merge overlay JSON object only."
        )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _system_prompt() -> str:
    schema_hint = {
        "relationship_scope_rationale": "one short sentence",
        "relationships": [],
        "economic_link_map": {
            "entities": [{"ticker": "TICKER", "role": "short role", "evidence_refs": ["ref"], "confidence": "low|medium|high"}],
            "links": [
                {
                    "source": "TICKER or economic driver",
                    "target": "TICKER",
                    "link_type": "demand_driver | substitution | peer | sector_hypothesis",
                    "mechanism": "one short economic transmission mechanism",
                    "direction": "positive | negative | mixed | unknown",
                    "metric_implications": ["metric"],
                    "evidence_refs": ["ref"],
                    "claim_scope": "economic_mechanism_hypothesis_only",
                    "missing_confirmations": ["missing confirmation"],
                }
            ],
            "mechanisms": [{"driver": "driver", "affected_entities": ["TICKER"], "metric_implications": ["metric"], "evidence_refs": ["ref"]}],
            "investment_implications": [
                {
                    "claim": "bounded implication",
                    "so_what": "why this matters",
                    "entity_scope": ["TICKER"],
                    "confidence": "low | medium | high",
                    "supporting_refs": ["ref"],
                    "missing_confirmations": ["missing confirmation"],
                }
            ],
        },
        "unsupported_relationships": [],
    }
    return "\n\n".join(
        [
            "You are the Universe / Relationship Agent for a SEC investment research multi-agent graph.",
            research_skill_prompt("universe_relationship", max_chars=1600),
            "Return exactly one JSON object. Do not wrap it in prose. Do not call tools.",
            "You are not the graph builder. The program owns relationship edges, confidence, boundary, and evidence refs.",
            "Your only value-add is compact economic mechanism interpretation over bounded graph refs.",
            "Relationship evidence can support scope and hypotheses only, never company financial facts.",
            "Return a merge overlay, not a full plan. Fill economic_link_map from bounded relationship refs and keep relationships empty.",
            f"Minimal overlay schema hint:\n{_json_for_prompt(schema_hint)}",
        ]
    )


def _known_relationship_refs(lookup: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    for relationship in lookup.get("relationships") or []:
        if isinstance(relationship, Mapping):
            refs.update(_string_list(relationship.get("evidence_refs") or relationship.get("refs")))
    return refs


def _complete_plan_from_lookup(
    parsed: Mapping[str, Any],
    *,
    lookup: Mapping[str, Any],
    scope_mode: str,
    focus_tickers: list[str],
    relationship_scope_rationale: str,
) -> dict[str, Any]:
    """Preserve every bounded lookup edge even when the LLM summarizes relationships.

    The LLM is useful for economic mechanisms; the deterministic lookup is the
    source of truth for edge coverage.
    """
    raw = dict(parsed or {})
    lookup_relationships = [
        dict(item)
        for item in lookup.get("relationships") or []
        if isinstance(item, Mapping)
    ]
    raw_model_relationships = [
        dict(item)
        for item in raw.get("relationships") or []
        if isinstance(item, Mapping)
    ]
    lookup_keys = {_relationship_completion_key(item) for item in lookup_relationships}
    model_relationships = [
        item
        for item in raw_model_relationships
        if _relationship_completion_key(item) in lookup_keys
    ]
    seen = {_relationship_completion_key(item) for item in model_relationships}
    completed = list(model_relationships)
    added = 0
    for relationship in lookup_relationships:
        key = _relationship_completion_key(relationship)
        if key in seen:
            continue
        completed.append(dict(relationship))
        seen.add(key)
        added += 1

    relationship_tickers = set(
        _unique_upper(
            [
                *focus_tickers,
                *(lookup.get("included_tickers") or []),
                *[
                    ticker
                    for relationship in completed
                    for ticker in (relationship.get("ticker"), relationship.get("related_ticker"))
                    if ticker
                ],
            ]
        )
    )
    included = _unique_upper(
        [
            *focus_tickers,
            *(lookup.get("included_tickers") or []),
            *[
                ticker
                for relationship in completed
                for ticker in (relationship.get("ticker"), relationship.get("related_ticker"))
                if ticker
            ],
            *[ticker for ticker in _string_list(raw.get("included_tickers")) if str(ticker).upper().strip() in relationship_tickers],
        ]
    )
    expanded = _unique_upper(
        [
            *(lookup.get("expanded_tickers") or []),
            *[ticker for ticker in included if ticker not in set(_unique_upper(focus_tickers))],
            *[ticker for ticker in _string_list(raw.get("expanded_tickers")) if str(ticker).upper().strip() in relationship_tickers],
        ]
    )
    budget = dict(raw.get("budget") or {}) if isinstance(raw.get("budget"), Mapping) else {}
    budget["max_relationships"] = max(int(budget.get("max_relationships") or 0), len(completed), 1)
    budget["max_evidence_requirements"] = max(int(budget.get("max_evidence_requirements") or 0), len(completed), 1)
    budget["max_expanded_tickers"] = max(int(budget.get("max_expanded_tickers") or 0), len(expanded), 1)
    metadata = dict(raw.get("metadata") or {}) if isinstance(raw.get("metadata"), Mapping) else {}
    metadata.update(
        {
            "relationship_completion_policy": "deterministic_lookup_edge_completion_v0_1",
            "graph_completion_mode": "program_owns_edges_model_owns_mechanism_overlay",
            "lookup_relationship_count": len(lookup_relationships),
            "model_relationship_count": len(raw_model_relationships),
            "model_relationship_accepted_count": len(model_relationships),
            "model_relationship_rejected_count": max(0, len(raw_model_relationships) - len(model_relationships)),
            "deterministic_completed_relationship_count": added,
            "direct_commercial_edge_boundary": "sector-depth relationship rows remain inference-only unless source evidence marks confirmed_direct.",
        }
    )
    raw.update(
        {
            "scope_mode": raw.get("scope_mode") or scope_mode,
            "focus_tickers": _unique_upper(raw.get("focus_tickers") or focus_tickers),
            "expanded_tickers": expanded,
            "included_tickers": included,
            "relationship_scope_rationale": raw.get("relationship_scope_rationale")
            or relationship_scope_rationale
            or "Relationship lookup rows are preserved as bounded research-scope hypotheses.",
            "budget": budget,
            "relationships": completed,
            "metadata": metadata,
            "source_family": raw.get("source_family") or "relationship_graph",
        }
    )
    return raw


def _complete_economic_link_map_from_lookup(
    parsed: Mapping[str, Any],
    *,
    lookup: Mapping[str, Any],
    focus_tickers: list[str],
) -> dict[str, Any]:
    """Fill mechanical economic-map requirements from bounded lookup rows.

    The model should spend tokens on economic interpretation, not remembering
    source-boundary boilerplate. This completion keeps model-authored map rows
    when present and supplies missing sections from lookup evidence.
    """
    raw = dict(parsed or {})
    relationships = [dict(item) for item in raw.get("relationships") or lookup.get("relationships") or [] if isinstance(item, Mapping)]
    existing = raw.get("economic_link_map") if isinstance(raw.get("economic_link_map"), Mapping) else {}
    completed = dict(existing or {})
    completed["schema_version"] = "sec_agent_economic_link_map_v0.1"
    completed["map_scope"] = "relationship_hypothesis"
    completed["source_boundary"] = "relationship_graph_hypothesis_only"
    completed["focus_tickers"] = _unique_upper(completed.get("focus_tickers") or focus_tickers or lookup.get("focus_tickers"))

    top_relationships = _priority_economic_relationships(relationships, focus_tickers=completed["focus_tickers"])
    allowed_tickers = set(
        _unique_upper(
            [
                *completed["focus_tickers"],
                *(lookup.get("included_tickers") or []),
                *[ticker for row in top_relationships for ticker in (row.get("ticker"), row.get("related_ticker")) if ticker],
            ]
        )
    )
    existing_entities = [
        dict(row)
        for row in completed.get("entities") or []
        if isinstance(row, Mapping) and _economic_entity_allowed(row, allowed_tickers)
    ]
    if not existing_entities:
        completed["entities"] = _economic_entities_from_relationships(top_relationships, focus_tickers=completed["focus_tickers"])
    else:
        completed["entities"] = [_complete_economic_entity_defaults(row, top_relationships) for row in existing_entities]
    existing_links = [
        dict(row)
        for row in completed.get("links") or []
        if isinstance(row, Mapping) and _economic_link_allowed(row, allowed_tickers)
    ]
    if not existing_links:
        completed["links"] = _economic_links_from_relationships(top_relationships)
    else:
        completed["links"] = [_complete_economic_link_defaults(row, top_relationships) for row in existing_links]
    if not completed.get("mechanisms"):
        completed["mechanisms"] = _economic_mechanisms_from_relationships(top_relationships, focus_tickers=completed["focus_tickers"])
    else:
        completed["mechanisms"] = [
            _complete_economic_mechanism_defaults(row, top_relationships, allowed_tickers=allowed_tickers)
            for row in completed.get("mechanisms") or []
            if isinstance(row, Mapping)
        ]
    if not completed.get("investment_implications"):
        completed["investment_implications"] = _investment_implications_from_relationships(top_relationships, focus_tickers=completed["focus_tickers"])
    else:
        completed["investment_implications"] = [
            _complete_investment_implication_defaults(row, top_relationships, allowed_tickers=allowed_tickers)
            for row in completed.get("investment_implications") or []
            if isinstance(row, Mapping)
        ]
    completed["boundary_notes"] = [
        *[dict(item) for item in completed.get("boundary_notes") or [] if isinstance(item, Mapping)],
        {
            "type": "source_boundary",
            "severity": "required",
            "note": "Relationship rows are bounded sector/category inferences unless separately confirmed by direct customer/supplier, contract, order, or revenue exposure evidence.",
            "evidence_refs": _economic_refs(top_relationships)[:6],
        },
    ]
    metadata = dict(completed.get("metadata") or {}) if isinstance(completed.get("metadata"), Mapping) else {}
    metadata.update(
        {
            "completion_policy": "deterministic_economic_link_map_completion_v0_1",
            "relationship_count": len(relationships),
            "completed_from_lookup_relationship_count": len(top_relationships),
        }
    )
    completed["metadata"] = metadata
    raw["economic_link_map"] = completed
    return raw


def _economic_entity_allowed(entity: Mapping[str, Any], allowed_tickers: set[str]) -> bool:
    ticker = str(entity.get("ticker") or "").upper().strip()
    return bool(ticker and (not allowed_tickers or ticker in allowed_tickers))


def _economic_link_allowed(link: Mapping[str, Any], allowed_tickers: set[str]) -> bool:
    source = str(link.get("source") or "").strip()
    target = str(link.get("target") or "").strip()
    if not source or not target:
        return False
    return _economic_endpoint_allowed(source, allowed_tickers) and _economic_endpoint_allowed(target, allowed_tickers)


def _economic_endpoint_allowed(value: Any, allowed_tickers: set[str]) -> bool:
    text = str(value or "").upper().strip()
    if not text:
        return False
    if text in allowed_tickers:
        return True
    return not _looks_like_ticker_token(text)


def _looks_like_ticker_token(value: Any) -> bool:
    text = str(value or "").upper().strip()
    return bool(re.fullmatch(r"[A-Z][A-Z0-9]{0,5}(?:[.-][A-Z])?", text))


def _priority_economic_relationships(relationships: list[dict[str, Any]], *, focus_tickers: list[str]) -> list[dict[str, Any]]:
    focus = set(_unique_upper(focus_tickers))

    def key(row: Mapping[str, Any]) -> tuple[int, int, str]:
        ticker = str(row.get("ticker") or "").upper().strip()
        related = str(row.get("related_ticker") or "").upper().strip()
        has_focus = int(ticker in focus or related in focus)
        has_refs = int(bool(_string_list(row.get("evidence_refs") or row.get("refs"))))
        return (-has_focus, -has_refs, f"{ticker}:{related}")

    return sorted([dict(row) for row in relationships if isinstance(row, Mapping)], key=key)[:6]


def _economic_entities_from_relationships(relationships: list[dict[str, Any]], *, focus_tickers: list[str]) -> list[dict[str, Any]]:
    refs_by_ticker: dict[str, list[str]] = {}
    for row in relationships:
        refs = _string_list(row.get("evidence_refs") or row.get("refs"))
        for ticker in (row.get("ticker"), row.get("related_ticker")):
            ticker_text = str(ticker or "").upper().strip()
            if ticker_text:
                refs_by_ticker.setdefault(ticker_text, []).extend(refs)
    focus = set(_unique_upper(focus_tickers))
    entities = []
    for ticker, refs in refs_by_ticker.items():
        entities.append(
            {
                "ticker": ticker,
                "role": "focus_company" if ticker in focus else "relationship_scope_entity",
                "evidence_refs": _dedupe(refs)[:4],
                "confidence": "medium",
                "materiality": "medium" if ticker not in focus else "high",
                "missing_confirmations": [
                    "direct customer/supplier filing confirmation",
                    "contract/order/revenue exposure evidence",
                ],
            }
        )
        if len(entities) >= 8:
            break
    return entities


def _economic_links_from_relationships(relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    links = []
    for row in relationships[:6]:
        ticker = str(row.get("ticker") or "").upper().strip()
        related = str(row.get("related_ticker") or "").upper().strip()
        if not ticker or not related:
            continue
        link_type = _economic_link_type_from_relationship(row)
        refs = _string_list(row.get("evidence_refs") or row.get("refs"))[:4]
        metrics = _string_list(row.get("metrics_to_check") or row.get("metric_links"))[:5]
        mechanism = str(row.get("financial_link_type") or row.get("direction") or row.get("relationship_type") or "sector relationship hypothesis")
        links.append(
            {
                "source": ticker,
                "target": related,
                "link_type": link_type,
                "mechanism": f"{ticker} to {related}: {mechanism}",
                "direction": "mixed" if link_type in {"peer", "substitution"} else "positive",
                "materiality": "medium",
                "confidence": str(row.get("confidence") or "medium"),
                "metric_implications": metrics or ["revenue", "margin"],
                "evidence_refs": refs,
                "claim_scope": "economic_mechanism_hypothesis_only",
                "missing_confirmations": _string_list(row.get("missing_confirmations"))
                or ["direct customer/supplier filing confirmation", "contract/order/revenue exposure evidence"],
            }
        )
    return links


def _complete_economic_entity_defaults(entity: Mapping[str, Any], relationships: list[dict[str, Any]]) -> dict[str, Any]:
    clean = dict(entity)
    clean["evidence_refs"] = _valid_or_fallback_refs(clean.get("evidence_refs") or clean.get("refs"), relationships)
    clean["missing_confirmations"] = _string_list(clean.get("missing_confirmations")) or [
        "direct customer/supplier filing confirmation",
        "contract/order/revenue exposure evidence",
    ]
    if not str(clean.get("role") or "").strip():
        clean["role"] = "relationship_scope_entity"
    return clean


def _complete_economic_link_defaults(link: Mapping[str, Any], relationships: list[dict[str, Any]]) -> dict[str, Any]:
    clean = dict(link)
    clean["evidence_refs"] = _valid_or_fallback_refs(clean.get("evidence_refs") or clean.get("refs"), relationships)
    clean["claim_scope"] = "economic_mechanism_hypothesis_only"
    clean["missing_confirmations"] = _string_list(clean.get("missing_confirmations")) or [
        "direct customer/supplier filing confirmation",
        "contract/order/revenue exposure evidence",
    ]
    if not str(clean.get("mechanism") or "").strip():
        clean["mechanism"] = "Bounded relationship evidence supports an economic transmission hypothesis only."
    if not _string_list(clean.get("metric_implications")):
        clean["metric_implications"] = ["revenue", "margin"]
    return clean


def _complete_economic_mechanism_defaults(
    mechanism: Mapping[str, Any],
    relationships: list[dict[str, Any]],
    *,
    allowed_tickers: set[str],
) -> dict[str, Any]:
    clean = dict(mechanism)
    clean["evidence_refs"] = _valid_or_fallback_refs(clean.get("evidence_refs") or clean.get("refs"), relationships)
    if not _string_list(clean.get("metric_implications")):
        clean["metric_implications"] = ["revenue", "margin", "capex"]
    affected_entities = [
        item
        for item in _string_list(clean.get("affected_entities"))
        if str(item).upper().strip() in allowed_tickers or not _looks_like_ticker_token(item)
    ]
    if affected_entities:
        clean["affected_entities"] = affected_entities
    else:
        clean["affected_entities"] = _unique_upper([ticker for row in relationships for ticker in (row.get("ticker"), row.get("related_ticker")) if ticker])[:8]
    if not str(clean.get("driver") or "").strip():
        clean["driver"] = "sector relationship read-through"
    return clean


def _complete_investment_implication_defaults(
    implication: Mapping[str, Any],
    relationships: list[dict[str, Any]],
    *,
    allowed_tickers: set[str],
) -> dict[str, Any]:
    clean = dict(implication)
    clean["supporting_refs"] = _valid_or_fallback_refs(clean.get("supporting_refs") or clean.get("evidence_refs") or clean.get("refs"), relationships)
    entity_scope = [
        item
        for item in _string_list(clean.get("entity_scope"))
        if str(item).upper().strip() in allowed_tickers or not _looks_like_ticker_token(item)
    ]
    if entity_scope:
        clean["entity_scope"] = entity_scope
    clean["missing_confirmations"] = _string_list(clean.get("missing_confirmations")) or [
        "direct commercial edge confirmation",
        "contract/order/revenue exposure evidence",
    ]
    if not str(clean.get("so_what") or "").strip():
        clean["so_what"] = "Use as a bounded research hypothesis until company filings and exact evidence verify it."
    return clean


def _valid_or_fallback_refs(value: Any, relationships: list[dict[str, Any]]) -> list[str]:
    known = set(_economic_refs(relationships))
    refs = [ref for ref in _string_list(value) if not known or ref in known]
    return refs or _economic_refs(relationships)[:2]


def _economic_mechanisms_from_relationships(relationships: list[dict[str, Any]], *, focus_tickers: list[str]) -> list[dict[str, Any]]:
    refs = _economic_refs(relationships)[:6]
    affected = _unique_upper(
        [
            *focus_tickers,
            *[ticker for row in relationships for ticker in (row.get("ticker"), row.get("related_ticker")) if ticker],
        ]
    )[:8]
    metrics = _dedupe([metric for row in relationships for metric in _string_list(row.get("metrics_to_check") or row.get("metric_links"))])[:6]
    return [
        {
            "driver": "sector relationship read-through",
            "affected_entities": affected,
            "metric_implications": metrics or ["revenue", "margin", "capex"],
            "confirming_indicators": ["company-reported revenue or capex movement", "management commentary aligned with the relationship hypothesis"],
            "disconfirming_indicators": ["no matching company disclosure", "margin or demand signal moves against the hypothesis"],
            "evidence_refs": refs,
            "confidence": "medium",
        }
    ] if refs else []


def _investment_implications_from_relationships(relationships: list[dict[str, Any]], *, focus_tickers: list[str]) -> list[dict[str, Any]]:
    refs = _economic_refs(relationships)[:6]
    scope = _unique_upper(
        [
            *focus_tickers,
            *[ticker for row in relationships for ticker in (row.get("ticker"), row.get("related_ticker")) if ticker],
        ]
    )[:8]
    return [
        {
            "claim": "The relationship map identifies a bounded research scope and economic transmission hypothesis.",
            "so_what": "Specialists should verify the hypothesis with company filings, exact-value ledger rows, market data, and source-gap caveats before memo claims are upgraded.",
            "entity_scope": scope,
            "confidence": "medium",
            "supporting_refs": refs,
            "missing_confirmations": ["direct commercial edge confirmation", "contract/order/revenue exposure evidence"],
        }
    ] if refs else []


def _economic_link_type_from_relationship(row: Mapping[str, Any]) -> str:
    text = " ".join(str(row.get(key) or "").lower() for key in ("relationship_type", "direction", "financial_link_type"))
    if "compet" in text or "substitut" in text:
        return "substitution"
    if "peer" in text:
        return "peer"
    if "customer" in text or "supplier" in text:
        return "demand_driver"
    if "macro" in text or "regulat" in text:
        return "macro_regulatory"
    return "sector_hypothesis"


def _economic_refs(relationships: list[dict[str, Any]]) -> list[str]:
    return _dedupe([ref for row in relationships for ref in _string_list(row.get("evidence_refs") or row.get("refs"))])


def _relationship_completion_key(relationship: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    refs = _string_list(relationship.get("evidence_refs") or relationship.get("refs"))
    return (
        str(relationship.get("ticker") or relationship.get("from_ticker") or "").upper().strip(),
        str(relationship.get("related_ticker") or relationship.get("to_ticker") or "").upper().strip(),
        str(relationship.get("relationship_type") or relationship.get("type") or "").strip(),
        str(relationship.get("direction") or relationship.get("edge_direction") or "").strip(),
        ",".join(refs),
    )


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
            "inference_level": str(relationship.get("inference_level") or "unknown"),
            "confirmation_status": str(relationship.get("confirmation_status") or ""),
            "evidence_basis": _string_list(relationship.get("evidence_basis"))[:4],
            "missing_confirmations": _string_list(relationship.get("missing_confirmations"))[:4],
            "source_limitations": _string_list(relationship.get("source_limitations"))[:3],
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


def _relationship_lookup_prompt_view(lookup: Mapping[str, Any]) -> dict[str, Any]:
    """Build a compact relationship view for the LLM prompt.

    The full compact lookup remains the source for deterministic completion.
    This view keeps all refs visible but prevents the model from spending its
    response budget reproducing full edge rows.
    """
    relationships = [dict(item) for item in lookup.get("relationships") or [] if isinstance(item, Mapping)]
    prompt_rows: list[dict[str, Any]] = []
    for relationship in relationships:
        prompt_rows.append(
            {
                "ticker": relationship.get("ticker") or "",
                "related_ticker": relationship.get("related_ticker") or "",
                "relationship_type": relationship.get("relationship_type") or "",
                "direction": relationship.get("direction") or "",
                "evidence_refs": _string_list(relationship.get("evidence_refs"))[:2],
                "metrics_to_check": _string_list(relationship.get("metrics_to_check"))[:4],
                "inference_level": relationship.get("inference_level") or "",
                "confirmation_status": relationship.get("confirmation_status") or "",
                "missing_confirmations": _string_list(relationship.get("missing_confirmations"))[:2],
            }
        )
    return {
        "status": lookup.get("status") or "",
        "focus_tickers": lookup.get("focus_tickers") or [],
        "expanded_tickers": lookup.get("expanded_tickers") or [],
        "included_tickers": lookup.get("included_tickers") or [],
        "relationships": prompt_rows,
        "relationship_refs": sorted({ref for row in prompt_rows for ref in _string_list(row.get("evidence_refs"))}),
        "source_gaps": lookup.get("source_gaps") or [],
        "summary": {
            **dict(lookup.get("summary") or {}),
            "prompt_view_policy": "compact_relationship_refs_only_full_edges_completed_deterministically",
            "relationship_output_instruction": "do_not_copy_relationship_rows_use_relationships_empty_or_top_3_examples",
        },
    }


def _universe_relationship_input_pack_fingerprint(
    prompt_request: Mapping[str, Any],
    *,
    known_refs: set[str],
    source_inventory: Mapping[str, Any],
) -> dict[str, Any]:
    components: dict[str, Any] = {
        "request_scope": {
            "user_query_chars": len(str(prompt_request.get("user_query") or "")),
        },
        "activation_plan": prompt_request.get("activation_plan") if isinstance(prompt_request.get("activation_plan"), Mapping) else {},
        "relationship_lookup_prompt_view": prompt_request.get("relationship_lookup")
        if isinstance(prompt_request.get("relationship_lookup"), Mapping)
        else {},
        "known_relationship_refs": sorted(known_refs),
        "source_inventory_summary": _source_inventory_fingerprint_summary(source_inventory),
    }
    summaries = {
        name: _input_pack_component_summary(component)
        for name, component in components.items()
    }
    refs = _dedupe(
        [
            ref
            for component in components.values()
            for ref in _input_pack_evidence_refs(component)
        ]
    )
    digest_payload = {
        "component_digests": {name: summary.get("digest") for name, summary in summaries.items()},
        "known_relationship_refs": sorted(set(known_refs)),
        "component_ref_count": len(refs),
    }
    return {
        "schema_version": UNIVERSE_RELATIONSHIP_INPUT_PACK_FINGERPRINT_SCHEMA_VERSION,
        "agent_id": "universe_relationship",
        "digest": _fingerprint_digest(digest_payload),
        "component_summaries": summaries,
        "known_evidence_ref_count": len(refs),
        "known_evidence_refs": refs[:256],
        "known_evidence_refs_truncated": len(refs) > 256,
        "approx_prompt_payload_chars": sum(int(summary.get("approx_chars") or 0) for summary in summaries.values()),
        "fingerprint_policy": "fingerprint_only_no_prompt_text_persisted_v0_1",
    }


def _source_inventory_fingerprint_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_inventory_keys": sorted(str(key) for key in value.keys())[:32],
        "inventory_ticker_count": len(_inventory_tickers(value)),
        "available_tickers_sample": _unique_upper(value.get("available_tickers") or value.get("tickers"))[:12],
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


def _dedupe(value: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
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
            "relationships",
            "relationship_refs",
            "source_gaps",
            "included_tickers",
            "expanded_tickers",
            "known_relationship_refs",
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
            "relationship_refs",
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


def _json_for_prompt(value: Any, *, sort_keys: bool = False) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=sort_keys, separators=(",", ":"), default=str)


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
