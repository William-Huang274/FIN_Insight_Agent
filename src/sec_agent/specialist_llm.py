from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from sec_agent.llm_gateway import chat_completion
from sec_agent.multi_agent_contracts import SPECIALIST_AGENT_IDS, normalize_specialist_memolet, validate_specialist_memolet
from sec_agent.multi_agent_runtime import active_specialists_for_state, build_agent_data_view, specialist_activation_decisions
from sec_agent.research_skills import research_skill_prompt


ROUTE_SCHEMA_VERSION = "sec_agent_specialist_llm_route_v0.1"
ROUTE_SOURCE = "specialist_llm_v0.1"
SPECIALIST_ROUTER_ENV = "SEC_AGENT_MULTI_AGENT_SPECIALIST_ROUTER"

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
        outputs: list[dict[str, Any]] = []
        route_results: list[dict[str, Any]] = [
            _skipped_route_result_summary(row)
            for row in decisions
            if row.get("decision") == "skipped"
        ]
        decision_by_agent = {str(row.get("agent_id") or ""): row for row in decisions}
        for agent_id in specialists:
            request = build_specialist_request_from_state(agent_id, state)
            result = route_specialist_memolet_llm(
                agent_id,
                request,
                config=config,
                known_evidence_refs=set(request.get("known_evidence_refs") or []),
                call_chat_completion=call_chat_completion,
            )
            summary = _route_result_summary(result)
            decision = decision_by_agent.get(agent_id) or {}
            summary["priority"] = decision.get("priority") or ""
            summary["activation_policy"] = decision.get("policy") or ""
            route_results.append(summary)
            if result.get("status") == "pass":
                outputs.append(dict(result.get("memolet") or {}))
            else:
                outputs.append(_blocked_memolet(agent_id, result))
        return {
            "specialist_outputs": outputs,
            "specialist_route_results": route_results,
        }

    return _route


def build_specialist_request_from_state(agent_id: str, state: Mapping[str, Any]) -> dict[str, Any]:
    data_view = build_agent_data_view(agent_id, state)
    execution_mode = _execution_mode_from_state(state, data_view)
    rows = _compact_bounded_rows_for_prompt(
        agent_id,
        list(data_view.get("bounded_evidence_rows") or _bounded_rows_for_agent(agent_id, state)),
        execution_mode=execution_mode,
    )
    relationship_summary = _compact_relationship_summary_for_prompt(
        data_view.get("relationship_summary"),
        execution_mode=execution_mode,
    )
    refs = _known_evidence_refs_from_request({"bounded_evidence_rows": rows, "relationship_summary": relationship_summary})
    input_budget = _specialist_input_budget(agent_id, execution_mode, data_view)
    return {
        "agent_id": agent_id,
        "execution_mode": execution_mode,
        "user_query": state.get("user_query") or "",
        "bounded_evidence_rows": rows,
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
            return {
                "schema_version": ROUTE_SCHEMA_VERSION,
                "source": ROUTE_SOURCE,
                "status": "pass",
                "agent_id": resolved_agent_id,
                "memolet": salvaged_validation["memolet"],
                "validation": salvaged_validation,
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
            return {
                "schema_version": ROUTE_SCHEMA_VERSION,
                "source": ROUTE_SOURCE,
                "status": "pass",
                "agent_id": resolved_agent_id,
                "memolet": validation["memolet"],
                "validation": validation,
                "routing_trace": {
                    "attempt_count": len(model_calls),
                    "repair_attempts": attempt_index,
                    "known_evidence_ref_count": len(evidence_refs),
                },
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
    user_payload = {
        "agent_id": agent_id,
        "execution_mode": request.get("execution_mode") or "",
        "user_query": request.get("user_query") or request.get("prompt") or "",
        "bounded_evidence_rows": request.get("bounded_evidence_rows") or request.get("evidence_rows") or [],
        "relationship_summary": request.get("relationship_summary") or {},
        "coverage_summary": request.get("coverage_summary") or {},
        "source_boundaries": request.get("source_boundaries") or {},
        "input_budget": request.get("input_budget") or {},
        "output_contract": request.get("output_contract") or _specialist_output_contract(agent_id, str(request.get("execution_mode") or "")),
        "known_evidence_refs": sorted(known_evidence_refs),
    }
    observation_budget = _observation_budget_text(
        agent_id,
        str(request.get("execution_mode") or ""),
        prior_failure=prior_failure,
    )
    user = (
        "Write one SpecialistMemolet JSON object from the bounded evidence only. "
        "Do not add facts from memory. Supported observations require evidence_refs. "
        "Treat each observation as a ClaimCard v0.3: include ticker_scope, metric_scope, memo_slot, materiality, direction, evidence_refs, source_families, caveats, and missing_confirmations. "
        "Prefer memo-ready investment implications over row summaries; downstream will rank ClaimCards by evidence support, role fit, and memo readiness. "
        "Each observation must state the role-specific investment implication, not just restate the row. "
        "If relationship_summary is present, treat it as bounded hypothesis context only and cite its evidence_refs. "
        "If the bounded rows do not support your role-specific lens, put the gap in unsupported_claims. "
        "Do not copy raw tables, long snippets, or row-by-row evidence summaries into the output. "
        "Respect output_contract caps exactly; do not fill every gap if it is not material to the memo. "
        f"Keep the JSON compact and follow this case budget: {observation_budget}. "
        "The first character of the response must be { and the last character must be }; no markdown or prose.\n\n"
        f"Input JSON:\n{json.dumps(user_payload, ensure_ascii=False, indent=2)}"
    )
    if prior_failure:
        cleaned_failure = _clean_for_prompt(prior_failure)
        if str(prior_failure.get("type") or "") in {"json_parse_failed", "model_output_truncated"}:
            repair_payload = _compact_user_payload_for_repair(user_payload)
            user = (
                "Repair the previous SpecialistMemolet response. The previous output was not parseable as one complete JSON object.\n"
                f"Diagnostic:\n{json.dumps(cleaned_failure, ensure_ascii=False, sort_keys=True)}\n\n"
                f"Use this compact input JSON only:\n{json.dumps(repair_payload, ensure_ascii=False, indent=2)}\n\n"
                "Return exactly one minimal SpecialistMemolet JSON object. "
                "Use at most 2 observations, at most 2 unsupported_claims, and at most 1 conflict. "
                "Every supported observation must cite known evidence_refs. "
                "Start with { and end with }. No markdown, no prose, no copied tables."
            )
        else:
            user = (
                f"{user}\n\nRepair the previous output. It failed this diagnostic:\n"
                f"{json.dumps(cleaned_failure, ensure_ascii=False, sort_keys=True)}\n\n"
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
            f"SpecialistMemolet schema hint:\n{json.dumps(schema_hint, ensure_ascii=False, indent=2)}",
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
) -> list[dict[str, Any]]:
    max_rows = _specialist_input_max_rows(execution_mode)
    selected = rows[:max(1, max_rows)]
    if agent_id in {"risk_counterevidence_analyst", "industry_supply_chain_analyst"}:
        selected = _balanced_rows_by_source_for_prompt(rows, max_rows=max(1, max_rows))
    compact: list[dict[str, Any]] = []
    for row in selected:
        clean = dict(row)
        summary_chars = _specialist_summary_chars_for_row(agent_id, clean, execution_mode=execution_mode)
        clean["summary"] = _truncate(str(clean.get("summary") or ""), summary_chars)
        compact.append(clean)
    return compact


def _compact_relationship_summary_for_prompt(value: Any, *, execution_mode: str = "") -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    max_rows = _relationship_summary_max_rows_for_prompt(execution_mode)
    relationships = []
    for row in value.get("relationships") or []:
        if not isinstance(row, Mapping):
            continue
        clean = dict(row)
        summary_chars = _relationship_summary_chars(execution_mode)
        clean["summary"] = _truncate(str(clean.get("summary") or ""), summary_chars)
        relationships.append(clean)
        if len(relationships) >= max(1, max_rows):
            break
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
        "agent_id": payload.get("agent_id") or "",
        "execution_mode": payload.get("execution_mode") or "",
        "user_query": payload.get("user_query") or "",
        "bounded_evidence_rows": rows[:8],
        "relationship_summary": compact_relationship_summary,
        "coverage_summary": payload.get("coverage_summary") or {},
        "source_boundaries": payload.get("source_boundaries") or {},
        "output_contract": payload.get("output_contract") or _specialist_output_contract(str(payload.get("agent_id") or ""), str(payload.get("execution_mode") or "")),
        "known_evidence_refs": _string_list(payload.get("known_evidence_refs"))[:32],
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


def _specialist_input_max_rows(execution_mode: str) -> int:
    generic = os.environ.get("SPECIALIST_INPUT_MAX_ROWS")
    mode = str(execution_mode or "").strip()
    if mode == "deep_research":
        value = _int_env(os.environ.get("SPECIALIST_DEEP_RESEARCH_INPUT_MAX_ROWS") or generic, default=24)
    elif mode == "standard_memo":
        value = _int_env(os.environ.get("SPECIALIST_STANDARD_MEMO_INPUT_MAX_ROWS") or generic, default=16)
    else:
        value = _int_env(generic, default=12)
    return max(1, value)


def _relationship_summary_max_rows_for_prompt(execution_mode: str) -> int:
    generic = os.environ.get("SPECIALIST_RELATIONSHIP_SUMMARY_MAX_ROWS")
    if str(execution_mode or "").strip() == "deep_research":
        value = _int_env(os.environ.get("SPECIALIST_DEEP_RESEARCH_RELATIONSHIP_SUMMARY_MAX_ROWS") or generic, default=12)
    else:
        value = _int_env(generic, default=8)
    return max(1, value)


def _specialist_input_budget(agent_id: str, execution_mode: str, data_view: Mapping[str, Any]) -> dict[str, Any]:
    data_view_budget = data_view.get("input_budget") if isinstance(data_view.get("input_budget"), Mapping) else {}
    output_contract = _specialist_output_contract(agent_id, execution_mode)
    payload = {
        "execution_mode": execution_mode,
        "prompt_bounded_evidence_row_budget": _specialist_input_max_rows(execution_mode),
        "prompt_relationship_summary_row_budget": _relationship_summary_max_rows_for_prompt(execution_mode),
        "prompt_summary_char_policy": "source_family_tiered_v0_1",
        "data_view_bounded_evidence_row_budget": int(data_view_budget.get("bounded_evidence_row_budget") or 0),
        "budget_policy": "execution_mode_tiered_specialist_prompt_rows_only",
        "supported_observation_target": output_contract["supported_observation_target"],
        "unsupported_claim_cap": output_contract["unsupported_claim_cap"],
        "conflict_cap": output_contract["conflict_cap"],
        "output_contract_policy": output_contract["policy"],
    }
    if agent_id == "industry_supply_chain_analyst":
        payload["data_view_min_relationship_rows"] = int(data_view_budget.get("min_relationship_rows") or 0)
    return payload


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
            "unsupported_claim_cap": 3,
            "conflict_cap": 3,
            "memo_ready_requirement": "prioritize investment implications over row summaries",
        }
    return {
        "policy": "role_specific_claim_cards_v0_3",
        "supported_observation_target": "3-5" if mode == "deep_research" else "0-3" if mode not in {"standard_memo"} else "3-6",
        "unsupported_claim_cap": 3,
        "conflict_cap": 3,
        "memo_ready_requirement": "write only material observations that can support a memo section",
    }


def _specialist_summary_chars_for_row(agent_id: str, row: Mapping[str, Any], *, execution_mode: str = "") -> int:
    generic = os.environ.get("SPECIALIST_INPUT_SUMMARY_CHARS")
    if generic not in {None, ""}:
        return _int_env(generic, default=520)
    family = str(row.get("source_family") or "").strip()
    mode = str(execution_mode or "").strip()
    if family in {"primary_sec_filing", "company_authored_unaudited_sec_filing", ""}:
        default = 320 if mode == "deep_research" else 420
        if agent_id == "fundamental_analyst":
            default = 300 if mode == "deep_research" else 380
        return _int_env(os.environ.get("SPECIALIST_SEC_SUMMARY_CHARS"), default=default)
    if family == "market_snapshot":
        return _int_env(os.environ.get("SPECIALIST_MARKET_SUMMARY_CHARS"), default=300)
    if family == "industry_snapshot":
        return _int_env(os.environ.get("SPECIALIST_INDUSTRY_SUMMARY_CHARS"), default=340)
    if family == "relationship_graph":
        return _relationship_summary_chars(execution_mode)
    return _int_env(os.environ.get("SPECIALIST_OTHER_SUMMARY_CHARS"), default=320 if mode == "deep_research" else 420)


def _relationship_summary_chars(execution_mode: str = "") -> int:
    generic = os.environ.get("SPECIALIST_INPUT_SUMMARY_CHARS")
    if generic not in {None, ""}:
        return _int_env(generic, default=520)
    default = 420 if str(execution_mode or "").strip() == "deep_research" else 480
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
