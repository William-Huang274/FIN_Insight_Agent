from __future__ import annotations

import json
import os
import re
import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from sec_agent.llm_gateway import chat_completion
from sec_agent.multi_agent_contracts import SPECIALIST_AGENT_IDS, normalize_specialist_memolet, validate_specialist_memolet
from sec_agent.multi_agent_runtime import active_specialists_for_state, build_agent_data_view, specialist_activation_decisions
from sec_agent.research_skills import research_skill_prompt


ROUTE_SCHEMA_VERSION = "sec_agent_specialist_llm_route_v0.1"
ROUTE_SOURCE = "specialist_llm_v0.1"
SPECIALIST_ROUTER_ENV = "SEC_AGENT_MULTI_AGENT_SPECIALIST_ROUTER"
SHARED_SPECIALIST_CONTEXT_SCHEMA_VERSION = "sec_agent_shared_specialist_context_v0.1"

ChatCompletionFunc = Callable[..., dict[str, Any]]

@dataclass(frozen=True)
class SpecialistLLMConfig:
    llm_backend: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    chat_completions_path: str = "/chat/completions"
    model: str = "deepseek-v4-pro"
    api_key_env: str = "DEEPSEEK_API_KEY"
    temperature: float = 0.0
    max_tokens: int = 2000
    timeout_s: int = 180
    max_repair_attempts: int = 2


def specialist_llm_config_from_env(env: Mapping[str, str] | None = None) -> SpecialistLLMConfig:
    values = dict(os.environ if env is None else env)
    return SpecialistLLMConfig(
        llm_backend=values.get("LLM_BACKEND", "deepseek"),
        base_url=values.get("BASE_URL", "https://api.deepseek.com"),
        chat_completions_path=values.get("CHAT_COMPLETIONS_PATH", "/chat/completions"),
        model=values.get("MODEL_NAME", "deepseek-v4-pro"),
        api_key_env=values.get("API_KEY_ENV", "DEEPSEEK_API_KEY"),
        temperature=_float_env(values.get("SPECIALIST_TEMPERATURE"), default=0.0),
        max_tokens=_int_env(values.get("SPECIALIST_MAX_TOKENS"), default=2000),
        timeout_s=_int_env(values.get("SPECIALIST_TIMEOUT_S"), default=180),
        max_repair_attempts=_int_env(values.get("SPECIALIST_MAX_REPAIR_ATTEMPTS"), default=2),
    )


def route_specialists_from_env(
    env: Mapping[str, str] | None = None,
    *,
    call_chat_completion: ChatCompletionFunc = chat_completion,
) -> Callable[[Mapping[str, Any]], dict[str, Any]] | None:
    values = dict(os.environ if env is None else env)
    mode = str(values.get(SPECIALIST_ROUTER_ENV) or "mock").strip().lower()
    if mode in {"", "mock", "stub", "off", "false", "0"}:
        return None
    if mode not in {"llm", "deepseek", "api"}:
        raise ValueError(f"unsupported {SPECIALIST_ROUTER_ENV}: {mode}")
    config = specialist_llm_config_from_env(values)

    def _route(state: Mapping[str, Any]) -> dict[str, Any]:
        decisions = specialist_activation_decisions(state)
        specialists = active_specialists_for_state(state)
        shared_context = build_shared_specialist_context(state)
        outputs: list[dict[str, Any]] = []
        route_results: list[dict[str, Any]] = [
            _skipped_route_result_summary(row)
            for row in decisions
            if row.get("decision") == "skipped"
        ]
        decision_by_agent = {str(row.get("agent_id") or ""): row for row in decisions}
        for agent_id in specialists:
            request = build_specialist_request_from_state(agent_id, state, shared_context=shared_context)
            result = route_specialist_memolet_llm(
                agent_id,
                request,
                config=config,
                known_evidence_refs=set(request.get("known_evidence_refs") or []),
                call_chat_completion=call_chat_completion,
            )
            summary = _route_result_summary(result)
            summary.update(_request_route_summary(request))
            decision = decision_by_agent.get(agent_id) or {}
            summary["priority"] = decision.get("priority") or ""
            summary["activation_policy"] = decision.get("policy") or ""
            route_results.append(summary)
            if result.get("status") == "pass":
                outputs.append(dict(result.get("memolet") or {}))
            else:
                outputs.append(_blocked_memolet(agent_id, result))
        return {
            "shared_specialist_context": shared_context,
            "specialist_outputs": outputs,
            "specialist_route_results": route_results,
        }

    return _route


def build_shared_specialist_context(state: Mapping[str, Any]) -> dict[str, Any]:
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    reflection = state.get("multi_agent_reflection_report") if isinstance(state.get("multi_agent_reflection_report"), Mapping) else {}
    sufficiency = state.get("evidence_sufficiency_report") if isinstance(state.get("evidence_sufficiency_report"), Mapping) else {}
    relationship_plan = state.get("universe_relationship_plan") if isinstance(state.get("universe_relationship_plan"), Mapping) else {}
    context = {
        "schema_version": SHARED_SPECIALIST_CONTEXT_SCHEMA_VERSION,
        "user_query": _truncate(str(state.get("user_query") or ""), 480),
        "execution_mode": str(activation.get("execution_mode") or state.get("execution_mode") or ""),
        "focus_tickers": _string_list(activation.get("focus_tickers") or query_contract.get("focus_tickers"))[:12],
        "search_scope_tickers": _string_list(activation.get("search_scope_tickers") or query_contract.get("search_scope_tickers"))[:24],
        "coverage": {
            "sufficiency_level": str(reflection.get("sufficiency_level") or sufficiency.get("sufficiency_level") or ""),
            "missing_requirement_count": len(reflection.get("missing_requirements") or sufficiency.get("missing_requirements") or []),
            "bounded_answer_allowed": bool(reflection.get("bounded_answer_allowed") or sufficiency.get("bounded_answer_allowed")),
            "second_pass_reason": str((state.get("multi_agent_second_pass_decision") or {}).get("reason") or "")
            if isinstance(state.get("multi_agent_second_pass_decision"), Mapping)
            else "",
        },
        "source_boundaries": _source_boundaries_from_state(state),
        "relationship_context": {
            "available": bool(relationship_plan.get("relationships")),
            "relationship_count": len(relationship_plan.get("relationships") or []),
            "financial_fact_policy": "relationship_graph_hypothesis_only" if relationship_plan else "",
            "scope_mode": str(relationship_plan.get("scope_mode") or ""),
        },
        "prompt_policy": {
            "shared_context_policy": "common_task_coverage_and_boundary_context_v0_1",
            "role_payload_policy": "specialist_receives_only_role_task_and_selected_visible_rows",
            "evidence_ref_policy": "cite evidence_ref values visible in bounded_evidence_rows or relationship_summary; full validator refs are not repeated in prompt",
        },
    }
    context["context_digest"] = _payload_digest(context)
    return context


def build_specialist_request_from_state(
    agent_id: str,
    state: Mapping[str, Any],
    *,
    shared_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    data_view = build_agent_data_view(agent_id, state)
    execution_mode = _execution_mode_from_state(state, data_view)
    priority = _specialist_priority_from_data_view(data_view)
    task_card = data_view.get("assigned_task_card") if isinstance(data_view.get("assigned_task_card"), Mapping) else {}
    required_claim_slots = data_view.get("required_claim_slots") or []
    counterclaim_slots = data_view.get("counterclaim_slots") or []
    rows = _compact_bounded_rows_for_prompt(
        agent_id,
        list(data_view.get("bounded_evidence_rows") or _bounded_rows_for_agent(agent_id, state)),
        execution_mode=execution_mode,
        priority=priority,
        task_card=task_card,
        required_claim_slots=required_claim_slots,
        counterclaim_slots=counterclaim_slots,
    )
    prompt_row_distribution = _prompt_row_distribution(rows)
    relationship_summary = _compact_relationship_summary_for_prompt(
        data_view.get("relationship_summary"),
        execution_mode=execution_mode,
        required_claim_slots=required_claim_slots,
    )
    refs = _known_evidence_refs_from_request({"bounded_evidence_rows": rows, "relationship_summary": relationship_summary})
    input_budget = _specialist_input_budget(agent_id, execution_mode, data_view, priority=priority)
    context = dict(shared_context or build_shared_specialist_context(state))
    source_family_bundle = data_view.get("source_family_bundle") if isinstance(data_view.get("source_family_bundle"), Mapping) else {}
    return {
        "agent_id": agent_id,
        "execution_mode": execution_mode,
        "user_query": state.get("user_query") or "",
        "shared_context": context,
        "assigned_task_card": task_card,
        "required_claim_slots": required_claim_slots,
        "counterclaim_slots": counterclaim_slots,
        "bounded_evidence_rows": rows,
        "prompt_row_distribution": prompt_row_distribution,
        "source_family_bundle": source_family_bundle,
        "input_coverage_summary": _specialist_input_coverage_summary(agent_id, rows, state),
        "relationship_summary": relationship_summary,
        "coverage_summary": data_view.get("coverage_summary") or state.get("multi_agent_reflection_report") or state.get("evidence_sufficiency_report") or {},
        "source_boundaries": _source_boundaries_from_state(state),
        "input_budget": input_budget,
        "output_contract": _specialist_output_contract(agent_id, execution_mode),
        "known_evidence_refs": sorted(refs),
        "agent_data_view_status": data_view.get("status") or "pass",
    }


def route_specialist_memolet_llm(
    agent_id: str,
    request: Mapping[str, Any],
    *,
    config: SpecialistLLMConfig | None = None,
    known_evidence_refs: set[str] | None = None,
    call_chat_completion: ChatCompletionFunc = chat_completion,
) -> dict[str, Any]:
    resolved_agent_id = str(agent_id or "").strip()
    route_config = config or SpecialistLLMConfig()
    if resolved_agent_id not in SPECIALIST_AGENT_IDS:
        return _fail_result(
            agent_id=resolved_agent_id,
            model_calls=[],
            failure={"type": "invalid_specialist_agent", "agent_id": resolved_agent_id},
            validation={
                "status": "fail",
                "errors": [{"type": "invalid_specialist_agent", "agent_id": resolved_agent_id}],
                "warnings": [],
                "memolet": {},
            },
        )

    evidence_refs = set(known_evidence_refs or set())
    evidence_refs.update(_known_evidence_refs_from_request(request))
    max_repair_attempts = max(0, int(route_config.max_repair_attempts))
    model_calls: list[dict[str, Any]] = []
    last_failure: dict[str, Any] = {"type": "not_run"}
    last_validation: dict[str, Any] | None = None
    previous_content = ""

    for attempt_index in range(max_repair_attempts + 1):
        messages = _build_messages(
            resolved_agent_id,
            request,
            known_evidence_refs=evidence_refs,
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
            role=resolved_agent_id,
            profile="balanced",
            trace_tags={
                "route_source": ROUTE_SOURCE,
                "repair_attempt": attempt_index,
                "agent_id": resolved_agent_id,
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
            if attempt_index < max_repair_attempts:
                continue
            break
        if llm_result.get("tool_calls"):
            last_failure = {
                "type": "direct_tool_call_forbidden",
                "detail": "Specialist analysts may inspect bounded evidence only; direct tool calls are forbidden.",
            }
            continue

        parsed = extract_specialist_memolet_json(previous_content)
        if parsed is None:
            finish_reason = str(llm_result.get("finish_reason") or "")
            if finish_reason == "length":
                last_failure = {
                    "type": "model_output_truncated",
                    "detail": "The model stopped by max_tokens before returning a complete SpecialistMemolet JSON object.",
                    "finish_reason": finish_reason,
                    "output_tokens": llm_result.get("output_tokens"),
                }
            else:
                last_failure = {
                    "type": "json_parse_failed",
                    "detail": "No SpecialistMemolet JSON object was found.",
                    "finish_reason": finish_reason,
                    "output_tokens": llm_result.get("output_tokens"),
                }
            continue

        validation = validate_specialist_memolet(parsed, known_evidence_refs=evidence_refs)
        last_validation = validation
        salvaged_validation = _salvage_supported_claim_ref_errors(validation, known_evidence_refs=evidence_refs)
        if salvaged_validation is not None:
            temporal_validation = _salvage_temporal_single_ref_observations(
                salvaged_validation,
                request,
                known_evidence_refs=evidence_refs,
            )
            effective_validation = temporal_validation or salvaged_validation
            capped_memolet = _apply_specialist_output_contract_caps(effective_validation["memolet"], request)
            capped_validation = validate_specialist_memolet(capped_memolet, known_evidence_refs=evidence_refs)
            capped_validation["warnings"] = [
                *list(effective_validation.get("warnings") or []),
                *list(capped_validation.get("warnings") or []),
            ]
            return {
                "schema_version": ROUTE_SCHEMA_VERSION,
                "source": ROUTE_SOURCE,
                "status": "pass",
                "agent_id": resolved_agent_id,
                "memolet": capped_validation["memolet"],
                "validation": capped_validation,
                "routing_trace": {
                    "attempt_count": len(model_calls),
                    "repair_attempts": attempt_index,
                    "known_evidence_ref_count": len(evidence_refs),
                    "salvage_policy": "drop_supported_observations_with_missing_or_unknown_evidence_refs",
                },
                "model_diagnostics": _aggregate_model_calls(model_calls),
                "failure_reason": "",
            }
        if validation["status"] == "pass":
            temporal_validation = _salvage_temporal_single_ref_observations(
                validation,
                request,
                known_evidence_refs=evidence_refs,
            )
            effective_validation = temporal_validation or validation
            capped_memolet = _apply_specialist_output_contract_caps(effective_validation["memolet"], request)
            capped_validation = validate_specialist_memolet(capped_memolet, known_evidence_refs=evidence_refs)
            capped_validation["warnings"] = [
                *list(effective_validation.get("warnings") or []),
                *list(capped_validation.get("warnings") or []),
            ]
            routing_trace = {
                "attempt_count": len(model_calls),
                "repair_attempts": attempt_index,
                "known_evidence_ref_count": len(evidence_refs),
            }
            if temporal_validation is not None:
                routing_trace["salvage_policy"] = "demote_single_ref_temporal_observations"
            return {
                "schema_version": ROUTE_SCHEMA_VERSION,
                "source": ROUTE_SOURCE,
                "status": "pass",
                "agent_id": resolved_agent_id,
                "memolet": capped_validation["memolet"],
                "validation": capped_validation,
                "routing_trace": routing_trace,
                "model_diagnostics": _aggregate_model_calls(model_calls),
                "failure_reason": "",
            }
        last_failure = {
            "type": "validation_failed",
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        }

    return _fail_result(
        agent_id=resolved_agent_id,
        model_calls=model_calls,
        failure=last_failure,
        validation=last_validation,
    )


def extract_specialist_memolet_json(text: str) -> dict[str, Any] | None:
    for candidate in _json_candidates(str(text or "")):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _build_messages(
    agent_id: str,
    request: Mapping[str, Any],
    *,
    known_evidence_refs: set[str],
    prior_failure: Mapping[str, Any] | None,
    prior_content: str,
) -> list[dict[str, str]]:
    system = _system_prompt(agent_id)
    shared_context = request.get("shared_context") if isinstance(request.get("shared_context"), Mapping) else {}
    execution_mode = str(request.get("execution_mode") or "")
    bounded_rows = _compact_rows_for_model_payload(
        agent_id,
        request.get("bounded_evidence_rows") or request.get("evidence_rows") or [],
        execution_mode=execution_mode,
    )
    relationship_summary = _compact_relationship_summary_payload(
        request.get("relationship_summary") if isinstance(request.get("relationship_summary"), Mapping) else {},
        execution_mode=execution_mode,
    )
    user_payload = {
        "shared_context": shared_context,
        "agent_id": agent_id,
        "execution_mode": execution_mode,
        "user_query": request.get("user_query") or request.get("prompt") or "",
        "assigned_task_card": request.get("assigned_task_card") or {},
        "required_claim_slots": request.get("required_claim_slots") or [],
        "counterclaim_slots": request.get("counterclaim_slots") or [],
        "bounded_evidence_rows": bounded_rows,
        "prompt_row_distribution": request.get("prompt_row_distribution") or _prompt_row_distribution(bounded_rows),
        "source_family_bundle": request.get("source_family_bundle") or {},
        "input_coverage_summary": request.get("input_coverage_summary") or {},
        "relationship_summary": relationship_summary,
        "coverage_summary": {} if shared_context else request.get("coverage_summary") or {},
        "source_boundaries": {} if shared_context else request.get("source_boundaries") or {},
        "input_budget": request.get("input_budget") or {},
        "output_contract": request.get("output_contract") or _specialist_output_contract(agent_id, execution_mode),
        "known_evidence_refs": {
            "count": len(known_evidence_refs),
            "policy": "cite only evidence_ref values visible in bounded_evidence_rows or relationship_summary",
        },
    }
    observation_budget = _observation_budget_text(
        agent_id,
        execution_mode,
        prior_failure=prior_failure,
    )
    user = (
        "Write one SpecialistMemolet JSON object from the bounded evidence only. "
        "Do not add facts from memory. Supported observations require evidence_refs. "
        "Use shared_context for common scope, coverage, and source-boundary context; do not restate it unless it changes a claim. "
        "Use source_family_bundle to enforce selected source families, context-only families, semantic-supplement limits, and forbidden claim scopes before writing any observation. "
        "Use assigned_task_card as your only role task brief; use required_claim_slots and counterclaim_slots to decide what to write. "
        "Inspect bounded_evidence_rows selectively: start with rows whose ticker, metric, source_family, or summary match a required_claim_slot; ignore irrelevant rows even if present. "
        "Treat each observation as a ClaimCard v0.3: include ticker_scope, metric_scope, memo_slot, materiality, direction, evidence_refs, source_families, caveats, and missing_confirmations. "
        "Prefer memo-ready investment implications over row summaries; downstream will rank ClaimCards by evidence support, role fit, and memo readiness. "
        "Each observation must state the role-specific investment implication, not just restate the row. "
        "Each supported observation should satisfy one required_claim_slot; if a slot is unsupported, add one material missing_confirmation or top unsupported_claim instead of a generic gap list. "
        "Do not infer sequential change, prior-period trend, YoY/QoQ growth, acceleration, deceleration, or trajectory unless the cited evidence_refs include at least two relevant period rows; otherwise write it as an unsupported_claim or caveat. "
        "If relationship_summary is present, treat it as bounded hypothesis context only and cite its evidence_refs. "
        "If the bounded rows do not support your role-specific lens, put the gap in unsupported_claims. "
        "Do not copy raw tables, long snippets, or row-by-row evidence summaries into the output. "
        "Respect output_contract caps exactly; do not fill every gap if it is not material to the memo. "
        f"Keep the JSON compact and follow this case budget: {observation_budget}. "
        "The first character of the response must be { and the last character must be }; no markdown or prose.\n\n"
        f"Input JSON:\n{_json_for_prompt(user_payload)}"
    )
    if prior_failure:
        cleaned_failure = _clean_for_prompt(prior_failure)
        if str(prior_failure.get("type") or "") in {"json_parse_failed", "model_output_truncated"}:
            repair_payload = _compact_user_payload_for_repair(user_payload)
            user = (
                "Repair the previous SpecialistMemolet response. The previous output was not parseable as one complete JSON object.\n"
                f"Diagnostic:\n{_json_for_prompt(cleaned_failure, sort_keys=True)}\n\n"
                f"Use this compact input JSON only:\n{_json_for_prompt(repair_payload)}\n\n"
                "Return exactly one minimal SpecialistMemolet JSON object. "
                "Use at most 2 observations, at most 2 unsupported_claims, and at most 1 conflict. "
                "Every supported observation must cite known evidence_refs. "
                "Start with { and end with }. No markdown, no prose, no copied tables."
            )
        else:
            user = (
                f"{user}\n\nRepair the previous output. It failed this diagnostic:\n"
                f"{_json_for_prompt(cleaned_failure, sort_keys=True)}\n\n"
                f"Previous output excerpt:\n{_truncate(prior_content, 1600)}\n\n"
                "Return one compact corrected SpecialistMemolet JSON object only. Start with { and end with }."
            )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _system_prompt(agent_id: str) -> str:
    schema_hint = {
        "schema_version": "sec_agent_specialist_memolet_v0.1",
        "agent_id": agent_id,
        "status": "pass | partial | blocked",
        "evidence_boundary": "bounded_rows_only",
        "summary": "short local memolet",
        "observations": [
            {
                "claim": "bounded local observation",
                "claim_type": "business_observation",
                "ticker_scope": ["TICKER"],
                "metric_scope": ["metric_family"],
                "memo_slot": "thesis | fundamentals | industry_relationship | market_valuation | risk_counterevidence | evidence_gap | caveat",
                "materiality": "high | medium | low",
                "direction": "positive | negative | mixed | neutral | unknown",
                "evidence_refs": ["evidence_ref"],
                "source_families": ["primary_sec_filing"],
                "confidence": "low | medium | high",
                "unsupported": False,
                "caveats": [],
                "missing_confirmations": [],
            }
        ],
        "unsupported_claims": [{"claim": "unsupported named fact", "reason": "not in bounded evidence"}],
        "conflicts": [{"claim": "conflict or counterevidence", "reason": "why it conflicts"}],
        "confidence": "low | medium | high",
    }
    return "\n\n".join(
        [
            f"You are the {agent_id}.",
            research_skill_prompt(agent_id, max_chars=4500),
            "Return exactly one JSON object. Do not wrap it in prose. Do not call tools.",
            "Keep output compact enough to fit within max_tokens; prefer role-prioritized observations over exhaustive notes.",
            "You may only use bounded evidence rows and summaries in the input.",
            "Every supported observation must cite evidence_refs from known_evidence_refs.",
            "If a named fact, relationship, number, or causal claim is not supported by bounded evidence, put it in unsupported_claims.",
            f"SpecialistMemolet schema hint:\n{_json_for_prompt(schema_hint)}",
        ]
    )


def _known_evidence_refs_from_request(request: Mapping[str, Any]) -> set[str]:
    explicit = request.get("known_evidence_refs")
    refs = set(_string_list(explicit))
    rows = request.get("bounded_evidence_rows") or request.get("evidence_rows") or []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        for key in ("evidence_ref", "evidence_id", "ref_id", "id", "metric_id", "source_id"):
            value = str(row.get(key) or "").strip()
            if value:
                refs.add(value)
    relationship_summary = request.get("relationship_summary")
    if isinstance(relationship_summary, Mapping):
        relationship_rows = relationship_summary.get("relationships") or []
        for row in relationship_rows if isinstance(relationship_rows, list) else []:
            if not isinstance(row, Mapping):
                continue
            for key in ("evidence_ref", "evidence_id", "ref_id", "id", "metric_id", "source_id"):
                value = str(row.get(key) or "").strip()
                if value:
                    refs.add(value)
    return refs


def _compact_bounded_rows_for_prompt(
    agent_id: str,
    rows: list[dict[str, Any]],
    *,
    execution_mode: str = "",
    priority: str = "",
    task_card: Mapping[str, Any] | None = None,
    required_claim_slots: list[Any] | None = None,
    counterclaim_slots: list[Any] | None = None,
) -> list[dict[str, Any]]:
    max_rows = _specialist_input_max_rows(execution_mode, priority=priority, agent_id=agent_id)
    selected = _select_prompt_rows(
        agent_id,
        rows,
        max_rows=max(1, max_rows),
        task_card=task_card or {},
        required_claim_slots=required_claim_slots or [],
        counterclaim_slots=counterclaim_slots or [],
    )
    compact: list[dict[str, Any]] = []
    for row in selected:
        clean = dict(row)
        summary_chars = _specialist_summary_chars_for_row(agent_id, clean, execution_mode=execution_mode)
        clean["summary"] = _truncate(str(clean.get("summary") or ""), summary_chars)
        compact.append(_compact_prompt_row(clean))
    return compact


def _compact_relationship_summary_for_prompt(
    value: Any,
    *,
    execution_mode: str = "",
    required_claim_slots: list[Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    max_rows = _relationship_summary_max_rows_for_prompt(execution_mode)
    relationship_rows = [dict(row) for row in value.get("relationships") or [] if isinstance(row, Mapping)]
    selected_rows = _rank_rows_for_prompt(
        relationship_rows,
        _selection_terms({}, required_claim_slots or [], [], agent_id="industry_supply_chain_analyst"),
        agent_id="industry_supply_chain_analyst",
    )[: max(1, max_rows)]
    relationships = []
    for row in selected_rows:
        if not isinstance(row, Mapping):
            continue
        clean = dict(row)
        summary_chars = _relationship_summary_chars(execution_mode)
        clean["summary"] = _truncate(str(clean.get("summary") or ""), summary_chars)
        relationships.append(_compact_prompt_row(clean))
    return {
        "scope_mode": str(value.get("scope_mode") or ""),
        "focus_tickers": _string_list(value.get("focus_tickers")),
        "expanded_tickers": _string_list(value.get("expanded_tickers")),
        "relationship_scope_rationale": _truncate(str(value.get("relationship_scope_rationale") or ""), _relationship_summary_chars(execution_mode)),
        "relationships": relationships,
        "financial_fact_policy": "relationship_graph_hypothesis_only",
    }


def _compact_user_payload_for_repair(payload: Mapping[str, Any]) -> dict[str, Any]:
    rows = [dict(row) for row in payload.get("bounded_evidence_rows") or [] if isinstance(row, Mapping)]
    relationship_summary = payload.get("relationship_summary") if isinstance(payload.get("relationship_summary"), Mapping) else {}
    compact_relationship_summary = dict(relationship_summary)
    relationships = [dict(row) for row in relationship_summary.get("relationships") or [] if isinstance(row, Mapping)]
    compact_relationship_summary["relationships"] = relationships[:4]
    return {
        "shared_context": payload.get("shared_context") or {},
        "agent_id": payload.get("agent_id") or "",
        "execution_mode": payload.get("execution_mode") or "",
        "user_query": payload.get("user_query") or "",
        "assigned_task_card": payload.get("assigned_task_card") or {},
        "required_claim_slots": [dict(item) for item in payload.get("required_claim_slots") or [] if isinstance(item, Mapping)][:4],
        "counterclaim_slots": [dict(item) for item in payload.get("counterclaim_slots") or [] if isinstance(item, Mapping)][:3],
        "bounded_evidence_rows": rows[:8],
        "source_family_bundle": payload.get("source_family_bundle") or {},
        "relationship_summary": compact_relationship_summary,
        "output_contract": payload.get("output_contract") or _specialist_output_contract(str(payload.get("agent_id") or ""), str(payload.get("execution_mode") or "")),
        "known_evidence_refs": {
            "visible_refs": _repair_known_refs(payload)[:24],
            "policy": "cite only visible refs from bounded_evidence_rows or relationship_summary",
        },
        "required_shape": {
            "schema_version": "sec_agent_specialist_memolet_v0.1",
            "agent_id": payload.get("agent_id") or "",
            "status": "pass | partial | blocked",
            "evidence_boundary": "bounded_rows_only",
            "summary": "one concise sentence",
            "observations": [],
            "unsupported_claims": [],
            "conflicts": [],
            "confidence": "low | medium | high",
        },
    }


def _compact_rows_for_model_payload(agent_id: str, rows: Any, *, execution_mode: str = "") -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        clean = dict(row)
        if "summary" in clean:
            clean["summary"] = _truncate(
                str(clean.get("summary") or ""),
                _specialist_summary_chars_for_row(agent_id, clean, execution_mode=execution_mode),
            )
        compact.append(_compact_prompt_row(clean))
    return compact


def _compact_relationship_summary_payload(value: Mapping[str, Any], *, execution_mode: str = "") -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        return {}
    clean = dict(value)
    relationships: list[dict[str, Any]] = []
    for row in clean.get("relationships") or []:
        if not isinstance(row, Mapping):
            continue
        row_clean = dict(row)
        if "summary" in row_clean:
            row_clean["summary"] = _truncate(str(row_clean.get("summary") or ""), _relationship_summary_chars(execution_mode))
        relationships.append(_compact_prompt_row(row_clean))
    clean["relationships"] = relationships
    if "relationship_scope_rationale" in clean:
        clean["relationship_scope_rationale"] = _truncate(str(clean.get("relationship_scope_rationale") or ""), _relationship_summary_chars(execution_mode))
    return {key: value for key, value in clean.items() if not _prompt_value_empty(value)}


def _compact_prompt_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Drop empty row fields before JSON serialization without removing citation fields."""
    preserve = {"evidence_ref", "source_family", "ticker", "related_ticker", "summary"}
    clean: dict[str, Any] = {}
    for key, value in row.items():
        key_text = str(key)
        if key_text in preserve:
            clean[key_text] = value
            continue
        if _prompt_value_empty(value):
            continue
        clean[key_text] = value
    return clean


def _prompt_value_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _select_prompt_rows(
    agent_id: str,
    rows: list[dict[str, Any]],
    *,
    max_rows: int,
    task_card: Mapping[str, Any],
    required_claim_slots: list[Any],
    counterclaim_slots: list[Any],
) -> list[dict[str, Any]]:
    if not rows:
        return []
    terms = _selection_terms(task_card, required_claim_slots, counterclaim_slots, agent_id=agent_id)
    ranked = _rank_rows_for_prompt(rows, terms, agent_id=agent_id)
    if agent_id == "industry_supply_chain_analyst":
        return _relationship_preserving_selection(ranked, max_rows=max_rows)
    if agent_id in {"fundamental_analyst", "risk_counterevidence_analyst"}:
        focus_tickers = _unique_upper(task_card.get("focus_tickers"))
        if len(focus_tickers) >= 2:
            source_families = {"", "primary_sec_filing", "company_authored_unaudited_sec_filing"}
            if agent_id == "risk_counterevidence_analyst":
                source_families = {
                    "",
                    "primary_sec_filing",
                    "company_authored_unaudited_sec_filing",
                    "market_snapshot",
                    "industry_snapshot",
                    "run_artifact",
                }
            return _focus_ticker_balanced_prompt_rows(
                ranked,
                focus_tickers=focus_tickers,
                max_rows=max_rows,
                source_families=source_families,
                priority_source_families=("market_snapshot", "industry_snapshot") if agent_id == "risk_counterevidence_analyst" else (),
            )
    if agent_id == "risk_counterevidence_analyst":
        return _balanced_rows_by_source_for_prompt(ranked, max_rows=max_rows)
    return ranked[:max_rows]


def _relationship_preserving_selection(rows: list[dict[str, Any]], *, max_rows: int) -> list[dict[str, Any]]:
    relationship_rows = [row for row in rows if str(row.get("source_family") or "") == "relationship_graph"]
    min_relationship_rows = min(len(relationship_rows), max(2, min(6, max_rows // 3)))
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    for row in relationship_rows[:min_relationship_rows]:
        selected.append(row)
        selected_ids.add(id(row))
    for row in rows:
        if len(selected) >= max_rows:
            break
        if id(row) in selected_ids:
            continue
        selected.append(row)
        selected_ids.add(id(row))
    return selected


def _rank_rows_for_prompt(rows: list[dict[str, Any]], terms: set[str], *, agent_id: str) -> list[dict[str, Any]]:
    indexed = list(enumerate(rows))
    return [
        row
        for _, row in sorted(
            indexed,
            key=lambda item: (
                -_row_selection_score(item[1], terms=terms, agent_id=agent_id),
                item[0],
            ),
        )
    ]


def _row_selection_score(row: Mapping[str, Any], *, terms: set[str], agent_id: str) -> int:
    family = str(row.get("source_family") or "")
    text = " ".join(
        str(row.get(key) or "").lower()
        for key in (
            "ticker",
            "related_ticker",
            "metric",
            "metric_name",
            "summary",
            "period_role",
            "source_family",
            "relationship_type",
            "direction",
        )
    )
    score = 0
    for term in terms:
        if term and term in text:
            score += 3 if len(term) > 2 else 1
    if agent_id == "fundamental_analyst" and family in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}:
        score += 4
    elif agent_id == "market_valuation_analyst" and family == "market_snapshot":
        score += 6
    elif agent_id == "industry_supply_chain_analyst" and family == "relationship_graph":
        score += 6
    elif agent_id == "industry_supply_chain_analyst" and family == "industry_snapshot":
        score += 4
    elif agent_id == "risk_counterevidence_analyst":
        risk_terms = ("risk", "decline", "pressure", "gap", "missing", "weak", "uncertain", "constraint", "caveat", "lawsuit")
        if any(term in text for term in risk_terms):
            score += 5
        if family in {"primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot", "industry_snapshot"}:
            score += 2
    if str(row.get("evidence_ref") or "").strip():
        score += 1
    if str(row.get("value") or "").strip():
        score += 1
    return score


def _selection_terms(
    task_card: Mapping[str, Any],
    required_claim_slots: list[Any],
    counterclaim_slots: list[Any],
    *,
    agent_id: str,
) -> set[str]:
    terms: set[str] = set()
    payloads: list[Any] = [
        task_card.get("assigned_memo_slot"),
        task_card.get("tickers"),
        task_card.get("source_families"),
        task_card.get("relevant_requirements"),
        required_claim_slots,
        counterclaim_slots,
    ]
    role_terms = {
        "fundamental_analyst": ["revenue", "margin", "capex", "cash", "backlog", "deposit", "credit", "asset", "income"],
        "market_valuation_analyst": ["return", "valuation", "market", "price", "volume", "multiple", "snapshot"],
        "industry_supply_chain_analyst": ["relationship", "supplier", "customer", "chain", "industry", "sector", "capex", "demand"],
        "risk_counterevidence_analyst": ["risk", "gap", "conflict", "decline", "pressure", "constraint", "missing", "caveat"],
    }
    payloads.extend(role_terms.get(agent_id, []))
    for payload in payloads:
        for term in _terms_from_value(payload):
            if len(term) >= 2:
                terms.add(term)
    return terms


def _terms_from_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        terms: list[str] = []
        for item in value.values():
            terms.extend(_terms_from_value(item))
        return terms
    if isinstance(value, (list, tuple, set)):
        terms = []
        for item in value:
            terms.extend(_terms_from_value(item))
        return terms
    text = str(value or "").lower()
    return [term for term in re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", text) if term not in _STOP_TERMS]


_STOP_TERMS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "when",
    "what",
    "which",
    "evidence",
    "claim",
    "slot",
    "primary",
    "supporting",
}


def _balanced_rows_by_source_for_prompt(rows: list[dict[str, Any]], *, max_rows: int) -> list[dict[str, Any]]:
    order = [
        "primary_sec_filing",
        "company_authored_unaudited_sec_filing",
        "market_snapshot",
        "industry_snapshot",
        "relationship_graph",
        "run_artifact",
        "",
    ]
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        buckets.setdefault(str(row.get("source_family") or ""), []).append(row)
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    while len(selected) < max_rows:
        added = False
        for family in order:
            bucket = buckets.get(family) or []
            while bucket and id(bucket[0]) in selected_ids:
                bucket.pop(0)
            if not bucket:
                continue
            row = bucket.pop(0)
            selected.append(row)
            selected_ids.add(id(row))
            added = True
            if len(selected) >= max_rows:
                break
        if not added:
            break
    for row in rows:
        if len(selected) >= max_rows:
            break
        if id(row) in selected_ids:
            continue
        selected.append(row)
        selected_ids.add(id(row))
    return selected


def _focus_ticker_balanced_prompt_rows(
    rows: list[dict[str, Any]],
    *,
    focus_tickers: list[str],
    max_rows: int,
    source_families: set[str],
    priority_source_families: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    for family in priority_source_families:
        family_rows = [row for row in rows if str(row.get("source_family") or "") == family]
        for row in family_rows[: max(1, min(2, max_rows // 4))]:
            if len(selected) >= max_rows:
                break
            selected.append(row)
            selected_ids.add(id(row))
    per_ticker = max(1, max_rows // max(1, len(focus_tickers)))
    for ticker in focus_tickers:
        bucket = _metric_and_source_diverse_prompt_rows(
            [
                row
                for row in rows
                if _row_ticker(row) == ticker and (not source_families or str(row.get("source_family") or "") in source_families)
            ],
            priority_source_families=priority_source_families,
        )
        for row in bucket[:per_ticker]:
            if len(selected) >= max_rows:
                break
            if id(row) in selected_ids:
                continue
            selected.append(row)
            selected_ids.add(id(row))
    for row in rows:
        if len(selected) >= max_rows:
            break
        if id(row) in selected_ids:
            continue
        selected.append(row)
        selected_ids.add(id(row))
    return selected


def _metric_and_source_diverse_prompt_rows(
    rows: list[dict[str, Any]],
    *,
    priority_source_families: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    for family in priority_source_families:
        for row in rows:
            if id(row) in selected_ids:
                continue
            if str(row.get("source_family") or "") == family:
                selected.append(row)
                selected_ids.add(id(row))
                break
    preferred_metric_terms = (
        ("revenue",),
        ("gross margin", "margin"),
        ("operating income", "operating_income"),
        ("cash flow", "cash", "net cash"),
        ("capex", "capital expenditure", "property and equipment"),
        ("segment", "backlog", "deposit", "credit"),
    )
    for terms in preferred_metric_terms:
        for row in rows:
            if id(row) in selected_ids:
                continue
            text = _row_metric_text(row)
            if any(term in text for term in terms):
                selected.append(row)
                selected_ids.add(id(row))
                break
    for family in ("market_snapshot", "industry_snapshot", "company_authored_unaudited_sec_filing", "primary_sec_filing"):
        for row in rows:
            if id(row) in selected_ids:
                continue
            if str(row.get("source_family") or "") == family:
                selected.append(row)
                selected_ids.add(id(row))
                break
    for row in rows:
        if id(row) in selected_ids:
            continue
        selected.append(row)
        selected_ids.add(id(row))
    return selected


def _row_metric_text(row: Mapping[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "").lower()
        for key in ("metric", "metric_name", "summary", "evidence_ref", "period_role")
    )


def _bounded_rows_for_agent(agent_id: str, state: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if agent_id == "market_valuation_analyst":
        rows.extend(_row_dicts(state.get("market_snapshot_rows")))
        rows.extend(row for row in _row_dicts(state.get("context_rows")) if str(row.get("source_family") or "") == "market_snapshot")
    elif agent_id == "industry_supply_chain_analyst":
        rows.extend(_row_dicts(state.get("industry_snapshot_rows")))
        rows.extend(
            row
            for row in _row_dicts(state.get("context_rows"))
            if str(row.get("source_family") or "") in {"industry_snapshot", "relationship_graph"}
        )
        relationship_plan = state.get("universe_relationship_plan")
        if isinstance(relationship_plan, Mapping):
            for index, relationship in enumerate(relationship_plan.get("relationships") or [], start=1):
                if not isinstance(relationship, Mapping):
                    continue
                rows.append(
                    {
                        "evidence_ref": ",".join(str(ref) for ref in relationship.get("evidence_refs") or []) or f"relationship_ref_{index}",
                        "source_family": "relationship_graph",
                        "ticker": relationship.get("ticker") or "",
                        "metric": relationship.get("relationship_type") or "relationship",
                        "summary": relationship.get("notes") or relationship.get("reason") or "",
                    }
                )
    elif agent_id == "fundamental_analyst":
        rows.extend(_row_dicts(state.get("runtime_ledger_rows")))
        rows.extend(
            row
            for row in _row_dicts(state.get("context_rows"))
            if str(row.get("source_family") or "") in {"primary_sec_filing", "company_authored_unaudited_sec_filing", ""}
        )
    else:
        rows.extend(_row_dicts(state.get("runtime_ledger_rows")))
        rows.extend(_row_dicts(state.get("context_rows")))
        rows.extend(_row_dicts(state.get("market_snapshot_rows")))
        rows.extend(_row_dicts(state.get("industry_snapshot_rows")))
    return [_bounded_row(row, index) for index, row in enumerate(rows[:12], start=1)]


def _row_dicts(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, Mapping)]


def _bounded_row(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    evidence_ref = (
        row.get("evidence_ref")
        or row.get("evidence_id")
        or row.get("metric_id")
        or row.get("source_id")
        or row.get("id")
        or f"bounded_row_{index}"
    )
    return {
        "evidence_ref": str(evidence_ref),
        "source_family": str(row.get("source_family") or row.get("source_tier") or ""),
        "ticker": str(row.get("ticker") or row.get("company") or ""),
        "period_role": str(row.get("period_role") or row.get("period") or ""),
        "metric": str(row.get("metric") or row.get("metric_name") or row.get("field") or ""),
        "value": _scalar_or_blank(row.get("value") or row.get("numeric_value") or row.get("display_value")),
        "summary": _truncate(
            str(row.get("summary") or row.get("text") or row.get("snippet") or row.get("description") or ""),
            900,
        ),
        "snapshot_id": str(row.get("snapshot_id") or ""),
        "as_of_date": str(row.get("as_of_date") or ""),
    }


def _source_boundaries_from_state(state: Mapping[str, Any]) -> dict[str, Any]:
    plan = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    return {
        "execution_mode": str(plan.get("execution_mode") or state.get("execution_mode") or ""),
        "allowed_source_families": list(plan.get("allowed_source_families") or []),
        "context_row_count": len(state.get("context_rows") or []),
        "ledger_row_count": len(state.get("runtime_ledger_rows") or []),
        "market_row_count": len(state.get("market_snapshot_rows") or []),
        "industry_row_count": len(state.get("industry_snapshot_rows") or []),
    }


def _blocked_memolet(agent_id: str, result: Mapping[str, Any]) -> dict[str, Any]:
    reason = str(result.get("failure_reason") or result.get("status") or "unknown_failure")[:500]
    return normalize_specialist_memolet(
        {
            "agent_id": agent_id,
            "status": "blocked",
            "summary": f"{agent_id} did not produce an accepted memolet; downstream memo must treat this lens as partial.",
            "unsupported_claims": [
                {
                    "type": "specialist_route_failed",
                    "claim": f"{agent_id} did not produce accepted specialist output; do not present this lens as fully analyzed.",
                    "reason": reason,
                }
            ],
            "metadata": {
                "route_status": result.get("status"),
                "route_failure": True,
                "failure_reason": reason,
                "diagnostic_only": True,
            },
        },
        agent_id=agent_id,
    )


def _salvage_supported_claim_ref_errors(
    validation: Mapping[str, Any],
    *,
    known_evidence_refs: set[str],
) -> dict[str, Any] | None:
    if validation.get("status") != "fail":
        return None
    error_types = {str(item.get("type") or "") for item in validation.get("errors") or [] if isinstance(item, Mapping)}
    allowed_error_types = {"supported_claim_without_evidence_refs", "unknown_evidence_ref"}
    if not error_types or not error_types <= allowed_error_types:
        return None
    memolet = dict(validation.get("memolet") or {})
    observations = [dict(item) for item in memolet.get("observations") or [] if isinstance(item, Mapping)]
    kept: list[dict[str, Any]] = []
    removed: list[dict[str, str]] = []
    for observation in observations:
        refs = set(_string_list(observation.get("evidence_refs") or observation.get("refs")))
        unknown = sorted(refs - known_evidence_refs) if known_evidence_refs else []
        if refs and not unknown:
            kept.append(observation)
            continue
        removed.append(
            {
                "claim": _truncate(str(observation.get("claim") or "Unsupported specialist observation without valid evidence refs."), 220),
                "reason": "dropped_from_supported_observations_missing_or_unknown_evidence_refs",
            }
        )
    if not removed or not kept:
        return None
    repaired = dict(memolet)
    repaired["status"] = "partial"
    repaired["observations"] = kept
    repaired["unsupported_claims"] = [
        *[dict(item) for item in memolet.get("unsupported_claims") or [] if isinstance(item, Mapping)],
        *removed,
    ]
    metadata = dict(repaired.get("metadata") or {})
    metadata["salvage_policy"] = "drop_supported_observations_with_missing_or_unknown_evidence_refs"
    metadata["salvaged_observation_count"] = len(removed)
    repaired["metadata"] = metadata
    salvaged = validate_specialist_memolet(repaired, known_evidence_refs=known_evidence_refs)
    if salvaged.get("status") != "pass":
        return None
    salvaged["warnings"] = [
        *list(salvaged.get("warnings") or []),
        {
            "type": "supported_observation_dropped_missing_or_unknown_evidence_refs",
            "removed_count": len(removed),
            "policy": "safe_salvage_no_unsupported_claim_enters_supported_plan",
        },
    ]
    return salvaged


def _salvage_temporal_single_ref_observations(
    validation: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    known_evidence_refs: set[str],
) -> dict[str, Any] | None:
    if validation.get("status") != "pass":
        return None
    row_by_ref = _row_by_known_ref_from_request(request)
    if not row_by_ref:
        return None
    memolet = dict(validation.get("memolet") or {})
    observations = [dict(item) for item in memolet.get("observations") or [] if isinstance(item, Mapping)]
    kept: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for observation in observations:
        if not _needs_temporal_single_ref_salvage(observation, row_by_ref=row_by_ref):
            kept.append(observation)
            continue
        removed.append(
            {
                "claim": _truncate(str(observation.get("claim") or "Unsupported temporal specialist observation."), 240),
                "reason": "demoted_single_ref_temporal_observation_without_row_level_comparison_support",
                "evidence_refs": _string_list(observation.get("evidence_refs") or observation.get("refs")),
            }
        )
    if not removed:
        return None
    repaired = dict(memolet)
    repaired["status"] = "partial"
    repaired["observations"] = kept
    repaired["unsupported_claims"] = [
        *[dict(item) for item in memolet.get("unsupported_claims") or [] if isinstance(item, Mapping)],
        *removed,
    ]
    metadata = dict(repaired.get("metadata") or {})
    metadata["salvage_policy"] = "demote_single_ref_temporal_observations_v0_1"
    metadata["salvaged_observation_count"] = len(removed)
    repaired["metadata"] = metadata
    salvaged = validate_specialist_memolet(repaired, known_evidence_refs=known_evidence_refs)
    if salvaged.get("status") != "pass":
        return None
    salvaged["warnings"] = [
        *list(validation.get("warnings") or []),
        *list(salvaged.get("warnings") or []),
        {
            "type": "single_ref_temporal_observation_demoted",
            "removed_count": len(removed),
            "policy": "supported_temporal_claims_require_two_refs_or_row_level_comparison_support",
        },
    ]
    return salvaged


def _needs_temporal_single_ref_salvage(
    observation: Mapping[str, Any],
    *,
    row_by_ref: Mapping[str, Mapping[str, Any]],
) -> bool:
    if observation.get("unsupported"):
        return False
    claim = str(observation.get("claim") or "")
    if not _looks_like_temporal_inference(claim):
        return False
    refs = [str(ref).strip() for ref in observation.get("evidence_refs") or observation.get("refs") or [] if str(ref or "").strip()]
    if len(refs) >= 2:
        return False
    return not _single_ref_temporal_claim_supported_by_row(refs, row_by_ref)


def _single_ref_temporal_claim_supported_by_row(
    refs: list[str],
    row_by_ref: Mapping[str, Mapping[str, Any]],
) -> bool:
    if len(refs) != 1:
        return False
    row = row_by_ref.get(refs[0]) or {}
    text = " ".join(
        str(row.get(key) or "").lower()
        for key in (
            "summary",
            "text",
            "preview",
            "metric",
            "metric_name",
            "metric_family",
            "value",
            "raw_value_text",
            "display_value_zh",
            "period_role",
            "source_statement",
        )
    )
    if not text:
        return False
    comparative_markers = (
        "higher than",
        "lower than",
        "compared with",
        "compared to",
        "versus",
        " vs ",
        "year-over-year",
        "year over year",
        "yoy",
        "quarter-over-quarter",
        "quarter over quarter",
        "qoq",
        "increased",
        "decreased",
        "grew",
        "declined",
        "rose",
        "fell",
        "up ",
        "down ",
        "\u589e\u52a0",
        "\u589e\u957f",
        "\u4e0a\u5347",
        "\u4e0b\u964d",
        "\u51cf\u5c11",
        "\u540c\u6bd4",
        "\u73af\u6bd4",
        "\u8f83",
        "\u9ad8\u4e8e",
        "\u4f4e\u4e8e",
    )
    if not any(marker in text for marker in comparative_markers):
        return False
    return (
        len(re.findall(r"\b20\d{2}\b", text)) >= 2
        or "%" in text
        or "percent" in text
        or any(marker in text for marker in ("\u540c\u6bd4", "\u73af\u6bd4", "yoy", "qoq"))
    )


def _looks_like_temporal_inference(claim: str) -> bool:
    text = claim.lower()
    patterns = (
        "sequential",
        "prior quarter",
        "prior period",
        "previous quarter",
        "previous period",
        "year-over-year",
        "year over year",
        "quarter-over-quarter",
        "quarter over quarter",
        "yoy",
        "qoq",
        "grew from",
        "declined from",
        "increased from",
        "decreased from",
        "acceleration",
        "deceleration",
        "trajectory",
    )
    return any(pattern in text for pattern in patterns)


def _row_by_known_ref_from_request(request: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    rows = request.get("bounded_evidence_rows") or request.get("evidence_rows") or []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        for ref in _row_ref_candidates(row):
            index.setdefault(ref, row)
    relationship_summary = request.get("relationship_summary")
    if isinstance(relationship_summary, Mapping):
        relationship_rows = relationship_summary.get("relationships") or []
        for row in relationship_rows if isinstance(relationship_rows, list) else []:
            if not isinstance(row, Mapping):
                continue
            for ref in _row_ref_candidates(row):
                index.setdefault(ref, row)
    return index


def _row_ref_candidates(row: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("evidence_ref", "evidence_id", "ref_id", "id", "metric_id", "source_id", "object_id"):
        value = str(row.get(key) or "").strip()
        if value and value not in refs:
            refs.append(value)
    return refs


def _route_result_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = result.get("model_diagnostics") if isinstance(result.get("model_diagnostics"), Mapping) else {}
    return {
        "agent_id": result.get("agent_id"),
        "status": result.get("status"),
        "failure_reason": str(result.get("failure_reason") or "")[:500],
        "attempt_count": (result.get("routing_trace") or {}).get("attempt_count") if isinstance(result.get("routing_trace"), Mapping) else None,
        "repair_attempts": (result.get("routing_trace") or {}).get("repair_attempts") if isinstance(result.get("routing_trace"), Mapping) else None,
        "salvage_policy": (result.get("routing_trace") or {}).get("salvage_policy") if isinstance(result.get("routing_trace"), Mapping) else None,
        "latency_ms": diagnostics.get("latency_ms"),
        "input_tokens": diagnostics.get("input_tokens"),
        "output_tokens": diagnostics.get("output_tokens"),
        "total_tokens": diagnostics.get("total_tokens"),
        "finish_reasons": diagnostics.get("finish_reasons") or [],
    }


def _request_route_summary(request: Mapping[str, Any]) -> dict[str, Any]:
    task_card = request.get("assigned_task_card") if isinstance(request.get("assigned_task_card"), Mapping) else {}
    shared_context = request.get("shared_context") if isinstance(request.get("shared_context"), Mapping) else {}
    relationship_summary = request.get("relationship_summary") if isinstance(request.get("relationship_summary"), Mapping) else {}
    source_family_bundle = request.get("source_family_bundle") if isinstance(request.get("source_family_bundle"), Mapping) else {}
    rows = [dict(row) for row in request.get("bounded_evidence_rows") or [] if isinstance(row, Mapping)]
    return {
        "task_card_schema_version": str(task_card.get("schema_version") or ""),
        "assigned_memo_slot": str(task_card.get("assigned_memo_slot") or ""),
        "task_relevant_requirement_count": int(task_card.get("relevant_requirement_count") or 0),
        "required_claim_slot_count": len(request.get("required_claim_slots") or []),
        "counterclaim_slot_count": len(request.get("counterclaim_slots") or []),
        "available_source_families": _string_list(task_card.get("available_source_families"))[:8],
        "shared_context_digest": str(shared_context.get("context_digest") or ""),
        "prompt_bounded_evidence_row_count": len(request.get("bounded_evidence_rows") or []),
        "prompt_relationship_summary_row_count": len(relationship_summary.get("relationships") or []),
        "prompt_row_distribution": request.get("prompt_row_distribution") or _prompt_row_distribution(rows),
        "selected_source_families": _string_list(source_family_bundle.get("selected_source_families"))[:8],
        "semantic_supplement_row_count": int(source_family_bundle.get("semantic_supplement_row_count") or 0),
        "input_coverage_summary": request.get("input_coverage_summary") or {},
    }


def _skipped_route_result_summary(decision: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "agent_id": decision.get("agent_id") or "",
        "status": "skipped",
        "failure_reason": str(decision.get("reason") or "")[:500],
        "attempt_count": 0,
        "repair_attempts": 0,
        "salvage_policy": None,
        "latency_ms": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "finish_reasons": [],
        "priority": decision.get("priority") or "",
        "activation_policy": decision.get("policy") or "",
        "task_card_schema_version": "",
        "assigned_memo_slot": "",
        "task_relevant_requirement_count": 0,
        "required_claim_slot_count": 0,
        "counterclaim_slot_count": 0,
        "available_source_families": [],
        "shared_context_digest": "",
        "prompt_bounded_evidence_row_count": 0,
        "prompt_relationship_summary_row_count": 0,
        "prompt_row_distribution": _prompt_row_distribution([]),
        "input_coverage_summary": {},
    }


def _scalar_or_blank(value: Any) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        return ""
    return str(value or "")


def _int_env(value: str | None, *, default: int) -> int:
    try:
        return int(value) if value not in {None, ""} else default
    except (TypeError, ValueError):
        return default


def _specialist_input_max_rows(execution_mode: str, *, priority: str = "", agent_id: str = "") -> int:
    generic = os.environ.get("SPECIALIST_INPUT_MAX_ROWS")
    mode = str(execution_mode or "").strip()
    normalized_priority = _normalize_specialist_priority(priority)
    if mode == "deep_research" and normalized_priority == "supporting":
        value = _int_env(
            os.environ.get("SPECIALIST_DEEP_RESEARCH_SUPPORTING_INPUT_MAX_ROWS")
            or os.environ.get("SPECIALIST_SUPPORTING_INPUT_MAX_ROWS")
            or generic,
            default=12,
        )
    elif mode == "deep_research" and normalized_priority in {"conditional", "low"}:
        value = _int_env(
            os.environ.get("SPECIALIST_DEEP_RESEARCH_CONDITIONAL_INPUT_MAX_ROWS")
            or os.environ.get("SPECIALIST_CONDITIONAL_INPUT_MAX_ROWS")
            or generic,
            default=8,
        )
    elif mode == "deep_research":
        default = 18 if agent_id == "industry_supply_chain_analyst" else 16
        value = _int_env(os.environ.get("SPECIALIST_DEEP_RESEARCH_INPUT_MAX_ROWS") or generic, default=default)
    elif mode == "standard_memo" and normalized_priority == "supporting":
        value = _int_env(
            os.environ.get("SPECIALIST_STANDARD_MEMO_SUPPORTING_INPUT_MAX_ROWS")
            or os.environ.get("SPECIALIST_SUPPORTING_INPUT_MAX_ROWS")
            or generic,
            default=8,
        )
    elif mode == "standard_memo":
        value = _int_env(os.environ.get("SPECIALIST_STANDARD_MEMO_INPUT_MAX_ROWS") or generic, default=12)
    else:
        value = _int_env(generic, default=10)
    return max(1, value)


def _relationship_summary_max_rows_for_prompt(execution_mode: str) -> int:
    generic = os.environ.get("SPECIALIST_RELATIONSHIP_SUMMARY_MAX_ROWS")
    if str(execution_mode or "").strip() == "deep_research":
        value = _int_env(os.environ.get("SPECIALIST_DEEP_RESEARCH_RELATIONSHIP_SUMMARY_MAX_ROWS") or generic, default=8)
    else:
        value = _int_env(generic, default=6)
    return max(1, value)


def _specialist_input_budget(
    agent_id: str,
    execution_mode: str,
    data_view: Mapping[str, Any],
    *,
    priority: str = "",
) -> dict[str, Any]:
    data_view_budget = data_view.get("input_budget") if isinstance(data_view.get("input_budget"), Mapping) else {}
    output_contract = _specialist_output_contract(agent_id, execution_mode)
    effective_priority = _normalize_specialist_priority(priority or str(data_view_budget.get("agent_priority") or ""))
    payload = {
        "execution_mode": execution_mode,
        "agent_priority": effective_priority,
        "prompt_bounded_evidence_row_budget": _specialist_input_max_rows(
            execution_mode,
            priority=effective_priority,
            agent_id=agent_id,
        ),
        "prompt_relationship_summary_row_budget": _relationship_summary_max_rows_for_prompt(execution_mode),
        "prompt_summary_char_policy": "source_family_tiered_v0_2_compact",
        "data_view_bounded_evidence_row_budget": int(data_view_budget.get("bounded_evidence_row_budget") or 0),
        "budget_policy": "shared_context_slot_aware_specialist_prompt_rows_v0_1",
        "selection_policy": "rank_by_required_claim_slots_preserve_relationship_source_balance_and_comparative_focus_ticker_coverage",
        "supported_observation_target": output_contract["supported_observation_target"],
        "unsupported_claim_cap": output_contract["unsupported_claim_cap"],
        "conflict_cap": output_contract["conflict_cap"],
        "output_contract_policy": output_contract["policy"],
    }
    if agent_id == "industry_supply_chain_analyst":
        payload["data_view_min_relationship_rows"] = int(data_view_budget.get("min_relationship_rows") or 0)
    return payload


def _specialist_priority_from_data_view(data_view: Mapping[str, Any]) -> str:
    card = data_view.get("assigned_task_card") if isinstance(data_view.get("assigned_task_card"), Mapping) else {}
    budget = data_view.get("input_budget") if isinstance(data_view.get("input_budget"), Mapping) else {}
    return _normalize_specialist_priority(card.get("priority") or budget.get("agent_priority"))


def _normalize_specialist_priority(value: Any) -> str:
    priority = str(value or "primary").strip().lower()
    return priority if priority in {"primary", "supporting", "conditional", "low"} else "primary"


def _execution_mode_from_state(state: Mapping[str, Any], data_view: Mapping[str, Any]) -> str:
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    summary = data_view.get("summary") if isinstance(data_view.get("summary"), Mapping) else {}
    return str(activation.get("execution_mode") or summary.get("execution_mode") or state.get("execution_mode") or "").strip()


def _observation_budget_text(
    agent_id: str,
    execution_mode: str,
    *,
    prior_failure: Mapping[str, Any] | None = None,
) -> str:
    if prior_failure and str(prior_failure.get("type") or "") in {"json_parse_failed", "model_output_truncated"}:
        return "produce at most 2 supported observations, at most 2 unsupported_claims, and at most 1 conflict"
    mode = str(execution_mode or "").strip()
    if mode == "deep_research":
        if agent_id == "risk_counterevidence_analyst":
            return "produce 2-3 supported risk ClaimCards when evidence supports them; use at most 2 unsupported_claims and at most 2 conflicts"
        if agent_id == "fundamental_analyst":
            return "produce 2-4 supported fundamental ClaimCards when evidence supports them; prioritize investment implications over row summaries; keep unsupported_claims/conflicts to the top 3 each"
        return "produce 3-5 supported observations when evidence supports them; keep unsupported_claims/conflicts to the top 3 each"
    if mode == "standard_memo":
        if agent_id == "risk_counterevidence_analyst":
            return "produce 2-3 supported risk ClaimCards when evidence supports them; use at most 2 unsupported_claims and at most 2 conflicts"
        return "produce 3-6 supported observations when evidence supports them; keep unsupported_claims/conflicts to the top 3 each"
    return "at most 3 observations, 3 unsupported_claims, and 3 conflicts"


def _specialist_output_contract(agent_id: str, execution_mode: str) -> dict[str, Any]:
    mode = str(execution_mode or "").strip()
    if agent_id == "risk_counterevidence_analyst":
        return {
            "policy": "risk_compact_schema_v0_3",
            "supported_observation_target": "2-3" if mode in {"standard_memo", "deep_research"} else "0-2",
            "unsupported_claim_cap": 2,
            "conflict_cap": 2,
            "memo_ready_requirement": "each risk must be a downside driver, evidence weakness, or confirmation need",
        }
    if agent_id == "fundamental_analyst" and mode == "deep_research":
        return {
            "policy": "fundamental_compact_claim_cards_v0_3",
            "supported_observation_target": "2-4",
            "unsupported_claim_cap": 1,
            "conflict_cap": 2,
            "memo_ready_requirement": "prioritize investment implications over row summaries",
        }
    return {
        "policy": "role_specific_claim_cards_v0_3",
        "supported_observation_target": "3-5" if mode == "deep_research" else "0-3" if mode not in {"standard_memo"} else "3-6",
        "unsupported_claim_cap": 1,
        "conflict_cap": 2,
        "memo_ready_requirement": "write only material observations that can support a memo section",
    }


def _apply_specialist_output_contract_caps(
    memolet: Mapping[str, Any],
    request: Mapping[str, Any],
) -> dict[str, Any]:
    capped = dict(memolet or {})
    contract = request.get("output_contract") if isinstance(request.get("output_contract"), Mapping) else {}
    unsupported_cap = max(0, _int_env(str(contract.get("unsupported_claim_cap") or ""), default=3))
    conflict_cap = max(0, _int_env(str(contract.get("conflict_cap") or ""), default=3))
    observations = [dict(item) for item in capped.get("observations") or [] if isinstance(item, Mapping)]
    supported_observations = [item for item in observations if not bool(item.get("unsupported"))]
    unsupported_from_observations = [
        {
            "claim": _truncate(str(item.get("claim") or "Unsupported specialist observation."), 240),
            "reason": "marked_unsupported_observation_moved_to_unsupported_claims",
            "evidence_refs": _string_list(item.get("evidence_refs")),
        }
        for item in observations
        if bool(item.get("unsupported"))
    ]
    unsupported = [
        *[dict(item) for item in capped.get("unsupported_claims") or [] if isinstance(item, Mapping)],
        *unsupported_from_observations,
    ]
    conflicts = [dict(item) for item in capped.get("conflicts") or [] if isinstance(item, Mapping)]
    overflow = {
        "unsupported_claim_overflow_count": max(0, len(unsupported) - unsupported_cap),
        "conflict_overflow_count": max(0, len(conflicts) - conflict_cap),
        "unsupported_observation_moved_count": len(unsupported_from_observations),
    }
    capped["observations"] = supported_observations
    capped["unsupported_claims"] = unsupported[:unsupported_cap]
    capped["conflicts"] = conflicts[:conflict_cap]
    if any(overflow.values()):
        metadata = dict(capped.get("metadata") or {})
        metadata["output_contract_cap_policy"] = "cap_specialist_gap_payload_preserve_overflow_counts_v0_1"
        metadata["output_contract_overflow"] = overflow
        capped["metadata"] = metadata
    return capped


def _specialist_summary_chars_for_row(agent_id: str, row: Mapping[str, Any], *, execution_mode: str = "") -> int:
    generic = os.environ.get("SPECIALIST_INPUT_SUMMARY_CHARS")
    if generic not in {None, ""}:
        return _int_env(generic, default=520)
    family = str(row.get("source_family") or "").strip()
    mode = str(execution_mode or "").strip()
    if family in {"primary_sec_filing", "company_authored_unaudited_sec_filing", ""}:
        default = 240 if mode == "deep_research" else 320
        if agent_id == "fundamental_analyst":
            default = 220 if mode == "deep_research" else 300
        return _int_env(os.environ.get("SPECIALIST_SEC_SUMMARY_CHARS"), default=default)
    if family == "market_snapshot":
        return _int_env(os.environ.get("SPECIALIST_MARKET_SUMMARY_CHARS"), default=220)
    if family == "industry_snapshot":
        return _int_env(os.environ.get("SPECIALIST_INDUSTRY_SUMMARY_CHARS"), default=240)
    if family == "relationship_graph":
        return _relationship_summary_chars(execution_mode)
    return _int_env(os.environ.get("SPECIALIST_OTHER_SUMMARY_CHARS"), default=240 if mode == "deep_research" else 320)


def _relationship_summary_chars(execution_mode: str = "") -> int:
    generic = os.environ.get("SPECIALIST_INPUT_SUMMARY_CHARS")
    if generic not in {None, ""}:
        return _int_env(generic, default=520)
    default = 280 if str(execution_mode or "").strip() == "deep_research" else 360
    return _int_env(os.environ.get("SPECIALIST_RELATIONSHIP_SUMMARY_CHARS"), default=default)


def _float_env(value: str | None, *, default: float) -> float:
    try:
        return float(value) if value not in {None, ""} else default
    except (TypeError, ValueError):
        return default


def _fail_result(
    *,
    agent_id: str,
    model_calls: list[dict[str, Any]],
    failure: Mapping[str, Any],
    validation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    validation_payload = dict(validation or {})
    return {
        "schema_version": ROUTE_SCHEMA_VERSION,
        "source": ROUTE_SOURCE,
        "status": "fail",
        "agent_id": agent_id,
        "memolet": {},
        "rejected_memolet": validation_payload.get("memolet") or {},
        "validation": validation_payload
        or {
            "status": "fail",
            "errors": [dict(failure)],
            "warnings": [],
            "memolet": {},
        },
        "routing_trace": {
            "attempt_count": len(model_calls),
            "repair_attempts": max(0, len(model_calls) - 1),
        },
        "model_diagnostics": _aggregate_model_calls(model_calls),
        "failure_reason": _format_failure_reason(failure),
    }


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


def _format_failure_reason(failure: Mapping[str, Any]) -> str:
    failure_type = str(failure.get("type") or "unknown_failure")
    if failure_type == "validation_failed":
        return f"validation_failed: {json.dumps(failure.get('errors') or [], ensure_ascii=False)[:700]}"
    reason = failure.get("reason") or failure.get("detail") or ""
    return f"{failure_type}: {reason}".strip()


def _specialist_input_coverage_summary(agent_id: str, rows: list[Mapping[str, Any]], state: Mapping[str, Any]) -> dict[str, Any]:
    focus_tickers = _focus_tickers_from_state(state)
    source_gaps = [dict(row) for row in state.get("source_gaps") or [] if isinstance(row, Mapping)]
    primary_rows = [
        row
        for row in rows
        if str(row.get("source_family") or "") in {"", "primary_sec_filing", "company_authored_unaudited_sec_filing"}
    ]
    primary_by_ticker = _count_by_key(primary_rows, "ticker")
    ticker_gap_reasons: dict[str, list[str]] = {}
    for gap in source_gaps:
        ticker = str(gap.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        reason = str(gap.get("reason_code") or gap.get("quality_gap_type") or gap.get("reason") or "source_gap")[:120]
        ticker_gap_reasons.setdefault(ticker, [])
        if reason not in ticker_gap_reasons[ticker]:
            ticker_gap_reasons[ticker].append(reason)
    return {
        "schema_version": "sec_agent_specialist_input_coverage_summary_v0.1",
        "agent_id": agent_id,
        "focus_tickers": focus_tickers,
        "prompt_row_distribution": _prompt_row_distribution(rows),
        "focus_ticker_primary_row_counts": {
            ticker: int(primary_by_ticker.get(ticker, 0))
            for ticker in focus_tickers
        },
        "focus_ticker_source_gap_reasons": {
            ticker: ticker_gap_reasons.get(ticker, [])
            for ticker in focus_tickers
            if ticker_gap_reasons.get(ticker)
        },
        "coverage_policy": "comparative_focus_tickers_must_have_visible_primary_rows_or_ticker_source_gap",
    }


def _prompt_row_distribution(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "sec_agent_prompt_row_distribution_v0.1",
        "row_count": len(rows),
        "by_ticker": _count_by_key(rows, "ticker"),
        "by_source_family": _count_by_key(rows, "source_family"),
        "by_ticker_source_family": _count_by_composite(rows, ("ticker", "source_family")),
        "by_form_type": _count_by_key(rows, "form_type"),
        "by_metric": _count_by_key(rows, "metric"),
    }


def _focus_tickers_from_state(state: Mapping[str, Any]) -> list[str]:
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    scope = query_contract.get("scope") if isinstance(query_contract.get("scope"), Mapping) else {}
    return _unique_upper(
        state.get("focus_tickers")
        or activation.get("focus_tickers")
        or query_contract.get("focus_tickers")
        or scope.get("focus_tickers")
    )


def _row_ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or row.get("company") or "").upper().strip()


def _count_by_key(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "").strip() or "unknown"
        if key == "ticker":
            value = value.upper()
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _count_by_composite(rows: list[Mapping[str, Any]], keys: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        parts = []
        for key in keys:
            value = str(row.get(key) or "").strip() or "unknown"
            if key == "ticker":
                value = value.upper()
            parts.append(value)
        label = "|".join(parts)
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def _unique_upper(value: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in _string_list(value):
        ticker = str(item or "").upper().strip()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        result.append(ticker)
    return result


def _clean_for_prompt(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _json_for_prompt(value: Any, *, sort_keys: bool = False) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=sort_keys, separators=(",", ":"), default=str)


def _payload_digest(value: Mapping[str, Any]) -> str:
    text = json.dumps(_clean_for_prompt(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _repair_known_refs(payload: Mapping[str, Any]) -> list[str]:
    refs: set[str] = set()
    explicit = payload.get("known_evidence_refs")
    if isinstance(explicit, Mapping):
        refs.update(_string_list(explicit.get("visible_refs")))
    else:
        refs.update(_string_list(explicit))
    refs.update(_known_evidence_refs_from_request(payload))
    return sorted(refs)


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
