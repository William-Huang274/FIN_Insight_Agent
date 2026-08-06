from __future__ import annotations

import json
import os
import re
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from sec_agent.llm_gateway import chat_completion
from sec_agent.method_runtime import (
    build_method_runtime_pack,
    compact_method_runtime_pack_for_prompt,
    specialist_runtime_rubric,
)
from sec_agent.multi_agent_contracts import (
    SPECIALIST_AGENT_IDS,
    _is_material_numeric_token,
    _unknown_numeric_tokens,
    normalize_specialist_memolet,
    validate_specialist_memolet,
)
from sec_agent.multi_agent_runtime import active_specialists_for_state, build_agent_data_view, specialist_activation_decisions
from sec_agent.prompt_metadata_contract import compact_prompt_metadata
from sec_agent.role_evidence_selector import build_role_source_layer_distribution
from sec_agent.research_skills import research_skill_prompt


ROUTE_SCHEMA_VERSION = "sec_agent_specialist_llm_route_v0.1"
ROUTE_SOURCE = "specialist_llm_v0.1"
SPECIALIST_ROUTER_ENV = "SEC_AGENT_MULTI_AGENT_SPECIALIST_ROUTER"
SHARED_SPECIALIST_CONTEXT_SCHEMA_VERSION = "sec_agent_shared_specialist_context_v0.1"
SPECIALIST_FANOUT_BARRIER_SCHEMA_VERSION = "sec_agent_specialist_fanout_barrier_v0.1"

ChatCompletionFunc = Callable[..., dict[str, Any]]

@dataclass(frozen=True)
class SpecialistLLMConfig:
    llm_backend: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    chat_completions_path: str = "/chat/completions"
    model: str = "deepseek-v4-pro"
    api_key_env: str = "DEEPSEEK_API_KEY"
    temperature: float = 0.0
    max_tokens: int = 1600
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
        max_tokens=_int_env(values.get("SPECIALIST_MAX_TOKENS"), default=1600),
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
        fanout_enabled = _bool_env(values.get("SEC_AGENT_SPECIALIST_FANOUT"))
        routed = _route_specialist_requests(
            specialists,
            state,
            shared_context=shared_context,
            config=config,
            call_chat_completion=call_chat_completion,
            fanout_enabled=fanout_enabled,
            max_workers=_int_env(values.get("SEC_AGENT_SPECIALIST_FANOUT_WORKERS"), default=4),
        )
        for item in routed:
            agent_id = str(item.get("agent_id") or "")
            request = item.get("request") if isinstance(item.get("request"), Mapping) else {}
            result = item.get("result") if isinstance(item.get("result"), Mapping) else {}
            summary = _route_result_summary(result)
            summary.update(_request_route_summary(request))
            decision = decision_by_agent.get(agent_id) or {}
            summary["priority"] = decision.get("priority") or ""
            summary["activation_policy"] = decision.get("policy") or ""
            summary["activation_decision"] = decision.get("decision") or "run"
            summary["activation_reason"] = str(decision.get("reason") or "")[:500]
            summary["matched_requirement_count"] = int(decision.get("matched_requirement_count") or 0)
            summary["explicit_intent"] = bool(decision.get("explicit_intent"))
            summary["signal_count"] = int(decision.get("signal_count") or 0)
            route_results.append(summary)
            if result.get("status") == "pass":
                outputs.append(dict(result.get("memolet") or {}))
            else:
                outputs.append(_blocked_memolet(agent_id, result))
        return {
            "shared_specialist_context": shared_context,
            "specialist_outputs": outputs,
            "specialist_activation_decisions": decisions,
            "specialist_route_results": route_results,
            "specialist_fanout_barrier": _specialist_fanout_barrier(
                route_results,
                outputs,
                execution_mode="fanout_parallel" if fanout_enabled else "sequential",
                shared_context=shared_context,
            ),
        }

    return _route


def _route_specialist_requests(
    specialists: list[str],
    state: Mapping[str, Any],
    *,
    shared_context: Mapping[str, Any],
    config: SpecialistLLMConfig,
    call_chat_completion: ChatCompletionFunc,
    fanout_enabled: bool,
    max_workers: int,
) -> list[dict[str, Any]]:
    indexed = list(enumerate(specialists))
    if not fanout_enabled or len(indexed) <= 1:
        return [
            _route_one_specialist_request(index, agent_id, state, shared_context, config, call_chat_completion)
            for index, agent_id in indexed
        ]
    worker_count = max(1, min(max_workers, len(indexed)))
    routed: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(_route_one_specialist_request, index, agent_id, state, shared_context, config, call_chat_completion): (index, agent_id)
            for index, agent_id in indexed
        }
        for future in as_completed(futures):
            index, agent_id = futures[future]
            try:
                routed.append(future.result())
            except Exception as exc:
                routed.append(
                    {
                        "index": index,
                        "agent_id": agent_id,
                        "request": {"agent_id": agent_id},
                        "result": _fail_result(
                            agent_id=agent_id,
                            model_calls=[],
                            failure={"type": "specialist_fanout_exception", "error": str(exc)[:500]},
                            validation={"status": "fail", "errors": [{"type": "specialist_fanout_exception", "error": str(exc)[:500]}]},
                        ),
                    }
                )
    return sorted(routed, key=lambda item: int(item.get("index") or 0))


def _route_one_specialist_request(
    index: int,
    agent_id: str,
    state: Mapping[str, Any],
    shared_context: Mapping[str, Any],
    config: SpecialistLLMConfig,
    call_chat_completion: ChatCompletionFunc,
) -> dict[str, Any]:
    request = build_specialist_request_from_state(agent_id, state, shared_context=shared_context)
    result = route_specialist_memolet_llm(
        agent_id,
        request,
        config=config,
        known_evidence_refs=set(request.get("known_evidence_refs") or []),
        call_chat_completion=call_chat_completion,
    )
    return {"index": index, "agent_id": agent_id, "request": request, "result": result}


def build_shared_specialist_context(state: Mapping[str, Any]) -> dict[str, Any]:
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    reflection = state.get("multi_agent_reflection_report") if isinstance(state.get("multi_agent_reflection_report"), Mapping) else {}
    sufficiency = state.get("evidence_sufficiency_report") if isinstance(state.get("evidence_sufficiency_report"), Mapping) else {}
    relationship_plan = state.get("universe_relationship_plan") if isinstance(state.get("universe_relationship_plan"), Mapping) else {}
    active_specialists = active_specialists_for_state(state)
    source_layer_capability = (
        state.get("source_layer_capability_audit")
        if isinstance(state.get("source_layer_capability_audit"), Mapping)
        else {}
    )
    role_source_layers = build_role_source_layer_distribution(
        source_layer_capability,
        roles=active_specialists,
    ) if active_specialists else {
        "schema_version": "finsight_role_source_layer_distribution_v0_1",
        "role_count": 0,
        "roles": {},
        "failed_roles": [],
        "gap_roles": [],
        "status": "not_applicable",
        "policy": "no_active_specialists",
    }
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
        "role_source_layer_distribution": role_source_layers,
        "prompt_policy": {
            "shared_context_policy": "common_task_coverage_and_boundary_context_v0_1",
            "role_payload_policy": "specialist_receives_only_role_task_and_selected_visible_rows",
            "evidence_ref_policy": "cite evidence_ref values visible in bounded_evidence_rows or relationship_summary; full validator refs are not repeated in prompt",
            "source_layer_policy": (
                "specialists receive source-layer capability distribution for repair/gap reasoning; L2/L3/L4 never become "
                "exact value authority, but rows with non_financial_signal_authority.thesis_driver_authority=true can support "
                "bounded product, technology, supply-chain, industry, macro, or expectation thesis drivers within their claim boundary"
            ),
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
        agent_id=agent_id,
    )
    raw_product_spec_pack = data_view.get("product_spec_pack") if isinstance(data_view.get("product_spec_pack"), Mapping) else {}
    raw_capital_macro_pack = data_view.get("capital_macro_pack") if isinstance(data_view.get("capital_macro_pack"), Mapping) else {}
    raw_fundamental_statement_pack = (
        data_view.get("fundamental_statement_pack_ref")
        if isinstance(data_view.get("fundamental_statement_pack_ref"), Mapping)
        else data_view.get("fundamental_statement_pack") if isinstance(data_view.get("fundamental_statement_pack"), Mapping) else {}
    )
    raw_fundamental_peer_statement_panel = (
        data_view.get("fundamental_peer_statement_panel_ref")
        if isinstance(data_view.get("fundamental_peer_statement_panel_ref"), Mapping)
        else data_view.get("fundamental_peer_statement_panel") if isinstance(data_view.get("fundamental_peer_statement_panel"), Mapping) else {}
    )
    product_spec_pack = _compact_product_spec_pack_for_prompt(raw_product_spec_pack, agent_id=agent_id)
    capital_macro_pack = _compact_capital_macro_pack_for_prompt(raw_capital_macro_pack, agent_id=agent_id)
    fundamental_statement_pack = _compact_fundamental_statement_pack_for_prompt(
        raw_fundamental_statement_pack,
        agent_id=agent_id,
    )
    fundamental_peer_statement_panel = _compact_fundamental_peer_statement_panel_for_prompt(
        raw_fundamental_peer_statement_panel,
        agent_id=agent_id,
    )
    method_runtime_pack = build_method_runtime_pack(
        state,
        user_query=str(state.get("user_query") or ""),
        focus_tickers=_string_list(state.get("focus_tickers") or state.get("tickers") or []),
    )
    role_method_rubric = specialist_runtime_rubric(method_runtime_pack, agent_id)
    refs = _known_evidence_refs_from_request(
        {
            "bounded_evidence_rows": rows,
            "relationship_summary": relationship_summary,
            "product_spec_pack": product_spec_pack,
            "capital_macro_pack": capital_macro_pack,
            "fundamental_statement_pack": fundamental_statement_pack,
            "fundamental_peer_statement_panel": fundamental_peer_statement_panel,
        }
    )
    input_budget = _specialist_input_budget(agent_id, execution_mode, data_view, priority=priority)
    context = dict(shared_context or build_shared_specialist_context(state))
    source_family_bundle = data_view.get("source_family_bundle") if isinstance(data_view.get("source_family_bundle"), Mapping) else {}
    role_source_layers = context.get("role_source_layer_distribution") if isinstance(context.get("role_source_layer_distribution"), Mapping) else {}
    role_source_layer_selection = {}
    if isinstance(role_source_layers.get("roles"), Mapping):
        role_source_layer_selection = role_source_layers.get("roles", {}).get(agent_id) or {}
    return {
        "agent_id": agent_id,
        "execution_mode": execution_mode,
        "user_query": state.get("user_query") or "",
        "agent_data_view_ref": {
            "schema_version": data_view.get("schema_version") or "",
            "context_digest": data_view.get("context_digest") or "",
            "global_context_ref": data_view.get("global_context_ref") or {},
            "private_context_policy": data_view.get("private_context_policy") or "private_operator_context_excluded",
        },
        "role_context": data_view.get("role_context") or {},
        "shared_context": context,
        "assigned_task_card": task_card,
        "required_claim_slots": required_claim_slots,
        "counterclaim_slots": counterclaim_slots,
        "bounded_evidence_rows": rows,
        "prompt_row_distribution": prompt_row_distribution,
        "source_layer_distribution": role_source_layer_selection,
        "source_family_bundle": source_family_bundle,
        "method_runtime_pack": compact_method_runtime_pack_for_prompt(method_runtime_pack, agent_id=agent_id),
        "specialist_runtime_rubric": role_method_rubric,
        "product_spec_pack": product_spec_pack if agent_id == "product_technology_analyst" else {},
        "capital_macro_pack": capital_macro_pack
        if agent_id in {"fundamental_analyst", "industry_supply_chain_analyst", "risk_counterevidence_analyst"}
        else {},
        "fundamental_statement_pack": fundamental_statement_pack if agent_id == "fundamental_analyst" else {},
        "fundamental_peer_statement_panel": fundamental_peer_statement_panel if agent_id == "fundamental_analyst" else {},
        "input_coverage_summary": _specialist_input_coverage_summary(agent_id, rows, state),
        "relationship_summary": relationship_summary,
        "coverage_summary": data_view.get("coverage_summary") or state.get("multi_agent_reflection_report") or state.get("evidence_sufficiency_report") or {},
        "source_boundaries": _source_boundaries_from_state(state),
        "input_budget": input_budget,
        "output_contract": _specialist_output_contract(agent_id, execution_mode, method_runtime_pack=method_runtime_pack),
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
            product_validation = _salvage_product_kpi_authority_violations(
                temporal_validation or salvaged_validation,
                request,
                known_evidence_refs=evidence_refs,
            )
            numeric_validation = _salvage_numeric_fidelity_violations(
                product_validation or temporal_validation or salvaged_validation,
                request,
                known_evidence_refs=evidence_refs,
            )
            effective_validation = numeric_validation or product_validation or temporal_validation or salvaged_validation
            capped_memolet = _apply_specialist_output_contract_caps(effective_validation["memolet"], request)
            capped_validation = validate_specialist_memolet(capped_memolet, known_evidence_refs=evidence_refs)
            capped_validation["warnings"] = [
                *list(effective_validation.get("warnings") or []),
                *list(capped_validation.get("warnings") or []),
            ]
            salvage_policy = "drop_supported_observations_with_missing_or_unknown_evidence_refs"
            if temporal_validation is not None:
                salvage_policy = "demote_single_ref_temporal_observations"
            if product_validation is not None:
                salvage_policy = "demote_product_kpi_without_exact_authority"
            if numeric_validation is not None:
                salvage_policy = "demote_numeric_claim_without_cited_row_support"
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
                    "salvage_policy": salvage_policy,
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
            product_validation = _salvage_product_kpi_authority_violations(
                temporal_validation or validation,
                request,
                known_evidence_refs=evidence_refs,
            )
            numeric_validation = _salvage_numeric_fidelity_violations(
                product_validation or temporal_validation or validation,
                request,
                known_evidence_refs=evidence_refs,
            )
            effective_validation = numeric_validation or product_validation or temporal_validation or validation
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
            if product_validation is not None:
                routing_trace["salvage_policy"] = "demote_product_kpi_without_exact_authority"
            if numeric_validation is not None:
                routing_trace["salvage_policy"] = "demote_numeric_claim_without_cited_row_support"
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
    shared_context = _compact_shared_context_for_prompt(
        request.get("shared_context") if isinstance(request.get("shared_context"), Mapping) else {}
    )
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
        "agent_data_view_ref": request.get("agent_data_view_ref") or {},
        "role_context": _compact_role_context_for_prompt(
            request.get("role_context") if isinstance(request.get("role_context"), Mapping) else {}
        ),
        "agent_id": agent_id,
        "execution_mode": execution_mode,
        "user_query": request.get("user_query") or request.get("prompt") or "",
        "assigned_task_card": _compact_task_card_for_prompt(
            request.get("assigned_task_card") if isinstance(request.get("assigned_task_card"), Mapping) else {}
        ),
        "required_claim_slots": _compact_claim_slots_for_prompt(request.get("required_claim_slots") or [], max_items=4),
        "counterclaim_slots": _compact_claim_slots_for_prompt(request.get("counterclaim_slots") or [], max_items=2),
        "bounded_evidence_rows": bounded_rows,
        "prompt_row_distribution": request.get("prompt_row_distribution") or _prompt_row_distribution(bounded_rows),
        "source_layer_distribution": _compact_source_layer_distribution_for_route(
            request.get("source_layer_distribution") if isinstance(request.get("source_layer_distribution"), Mapping) else {}
        ),
        "source_family_bundle": _compact_source_family_bundle_for_prompt(
            request.get("source_family_bundle") if isinstance(request.get("source_family_bundle"), Mapping) else {}
        ),
        "method_runtime_pack": request.get("method_runtime_pack") or {},
        "specialist_runtime_rubric": request.get("specialist_runtime_rubric") or {},
        "product_spec_pack": request.get("product_spec_pack") or {},
        "capital_macro_pack": request.get("capital_macro_pack") or {},
        "fundamental_statement_pack": request.get("fundamental_statement_pack") or {},
        "fundamental_peer_statement_panel": request.get("fundamental_peer_statement_panel") or {},
        "input_coverage_summary": _compact_input_coverage_summary_for_prompt(
            request.get("input_coverage_summary") if isinstance(request.get("input_coverage_summary"), Mapping) else {}
        ),
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
        "Use source_layer_distribution to understand which L1/L2/L3/L4 sources are available, repairable, or missing for your role; explicit selector gaps should become bounded unsupported_claims, not generic caveats. "
        "Use method_runtime_pack and specialist_runtime_rubric as hard method-to-runtime instructions: answer the role's must_answer items, preserve must_not_infer boundaries, and convert evidence into judgment_candidates. "
        "If product_spec_pack is present, use it as the parser-gated ProductSpecPack for product taxonomy, model/spec, customer deployment, supply-chain, comparable, channel offer, field inquiry, and commercial-gap boundaries. "
        "If capital_macro_pack is present, use it as the parser-gated capital, ownership, macro exposure, and vertical official object boundary; 13F is lagged context and macro drivers need exposure bridges. "
        "If fundamental_statement_pack is present, use it as the parser-gated three-statement, period-change, peer-comparison, industry-focus financial analysis pack; peer claims require same metric, unit, and period in that pack. "
        "If fundamental_peer_statement_panel is present, use it as the primary fundamental-analysis planning surface: organize observations by three-statement quality, peer comparable metrics, industry priority metrics, product-financial bridge, capital-funding bridge, and flagged anomalies instead of listing rows mechanically. "
        "Use non_financial_signal_authority when present: thesis_driver_authority=true rows may support bounded non-financial thesis drivers, product comparisons, deployment/adoption signals, supply-chain validation, industry operating context, or expectation-change analysis; they still cannot support exact revenue, ASP, sales, share, sell-through, backlog, inventory, or order value unless exact financial/product authority is explicitly present. "
        "Use assigned_task_card as your only role task brief; use required_claim_slots and counterclaim_slots to decide what to write. "
        "Inspect bounded_evidence_rows selectively: start with rows whose ticker, metric, source_family, or summary match a required_claim_slot; ignore irrelevant rows even if present. "
        "Treat each observation as a ClaimCard v0.3: include ticker_scope, metric_scope, memo_slot, materiality, direction, evidence_refs, source_families, caveats, and missing_confirmations; when using non-financial signal rows, include signal_authority_type and thesis_driver_authority. "
        "Also include judgment_candidates when a slot can support a writer-ready judgment; each candidate must state judgment, required_item_answered, supported_by_evidence_refs, graph_edge_refs, product_or_financial_bridge, business_mechanism, counter_read, cannot_infer, and what_would_change_view. "
        "Every judgment_candidate must cite at least one supported_by_evidence_refs value copied exactly from known evidence_refs; if no cited evidence_ref supports the judgment, omit the judgment_candidate and write an unsupported_claim instead. "
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
                "Every judgment_candidate must cite supported_by_evidence_refs copied exactly from known evidence_refs; otherwise omit it and write an unsupported_claim. "
                "Start with { and end with }. No markdown, no prose, no copied tables."
            )
        else:
            user = (
                f"{user}\n\nRepair the previous output. It failed this diagnostic:\n"
                f"{_json_for_prompt(cleaned_failure, sort_keys=True)}\n\n"
                f"Previous output excerpt:\n{_truncate(prior_content, 1600)}\n\n"
                "Return one compact corrected SpecialistMemolet JSON object only. Every judgment_candidate must cite supported_by_evidence_refs copied exactly from known evidence_refs; otherwise omit it and write an unsupported_claim. Start with { and end with }."
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
                "memo_slot": "thesis | fundamentals | product_technology | industry_relationship | market_valuation | risk_counterevidence | evidence_gap | caveat",
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
        "judgment_candidates": [
            {
                "judgment": "writer-ready bounded analyst judgment",
                "required_item_answered": "product_architecture_competition | fundamental_financial_bridge | risk_and_counterevidence",
                "supported_by_evidence_refs": ["evidence_ref"],
                "graph_edge_refs": ["relationship_or_product_edge_ref"],
                "product_or_financial_bridge": "how product/customer/supply-chain evidence reaches financial or investment judgment",
                "business_mechanism": "why the evidence matters",
                "counter_read": "what could weaken the judgment",
                "confidence": "low | medium | high",
                "cannot_infer": ["exact revenue/share/order value without exact authority"],
                "what_would_change_view": ["specific confirmation or contradiction"],
            }
        ],
        "confidence": "low | medium | high",
    }
    return "\n\n".join(
        [
            f"You are the {agent_id}.",
            research_skill_prompt(agent_id, max_chars=_specialist_skill_prompt_chars()),
            "Return exactly one JSON object. Do not wrap it in prose. Do not call tools.",
            "Keep output compact enough to fit within max_tokens; prefer role-prioritized observations over exhaustive notes.",
            "You may only use bounded evidence rows, product_spec_pack, capital_macro_pack, fundamental_statement_pack, fundamental_peer_statement_panel, relationship summaries, and shared summaries in the input.",
            "Every supported observation must cite evidence_refs from known_evidence_refs.",
            "Every judgment_candidate must cite supported_by_evidence_refs from known_evidence_refs; uncited judgment_candidates are invalid.",
            "If a named fact, relationship, number, or causal claim is not supported by bounded evidence, put it in unsupported_claims.",
            f"SpecialistMemolet schema hint:\n{_json_for_prompt(schema_hint)}",
        ]
    )


def _specialist_skill_prompt_chars() -> int:
    return max(900, _int_env(os.environ.get("SPECIALIST_SKILL_PROMPT_MAX_CHARS"), default=2200))


def _compact_shared_context_for_prompt(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    coverage = value.get("coverage") if isinstance(value.get("coverage"), Mapping) else {}
    relationship = value.get("relationship_context") if isinstance(value.get("relationship_context"), Mapping) else {}
    prompt_policy = value.get("prompt_policy") if isinstance(value.get("prompt_policy"), Mapping) else {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "user_query": _truncate(str(value.get("user_query") or ""), 180),
        "execution_mode": str(value.get("execution_mode") or ""),
        "focus_tickers": _string_list(value.get("focus_tickers"))[:8],
        "search_scope_tickers": _string_list(value.get("search_scope_tickers"))[:12],
        "coverage": {
            "sufficiency_level": str(coverage.get("sufficiency_level") or ""),
            "missing_requirement_count": coverage.get("missing_requirement_count"),
            "bounded_answer_allowed": bool(coverage.get("bounded_answer_allowed")),
            "second_pass_reason": _truncate(str(coverage.get("second_pass_reason") or ""), 60),
        },
        "relationship_context": {
            "available": bool(relationship.get("available")),
            "relationship_count": relationship.get("relationship_count"),
            "financial_fact_policy": str(relationship.get("financial_fact_policy") or ""),
            "scope_mode": str(relationship.get("scope_mode") or ""),
        },
        "prompt_policy": {
            "role_payload_policy": str(prompt_policy.get("role_payload_policy") or ""),
            "evidence_ref_policy": str(prompt_policy.get("evidence_ref_policy") or ""),
            "source_layer_policy": _compact_policy_statement(
                prompt_policy.get("source_layer_policy"),
                max_words=8,
            ),
        },
        "context_digest": str(value.get("context_digest") or ""),
    }


def _compact_policy_statement(value: Any, *, max_words: int) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip() + f"...[truncated_words={len(words)}]"


def _compact_role_context_for_prompt(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    portfolio = value.get("dimension_evidence_portfolio_ref") if isinstance(value.get("dimension_evidence_portfolio_ref"), Mapping) else {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "agent_id": str(value.get("agent_id") or ""),
        "role_context_type": str(value.get("role_context_type") or ""),
        "analyst_lens": str(value.get("analyst_lens") or ""),
        "assigned_memo_slot": str(value.get("assigned_memo_slot") or ""),
        "selected_source_families": _string_list(value.get("selected_source_families"))[:8],
        "context_only_source_families": _string_list(value.get("context_only_source_families"))[:8],
        "exact_value_authority_source_families": _string_list(value.get("exact_value_authority_source_families"))[:8],
        "required_claim_slot_ids": _string_list(value.get("required_claim_slot_ids"))[:8],
        "bounded_row_count": value.get("bounded_row_count"),
        "claim_card_output_required": bool(value.get("claim_card_output_required")),
        "dimension_evidence_portfolio_ref": _compact_pack_metadata(portfolio, max_items=6, text_limit=70),
        "fundamental_statement_pack_policy": _truncate(str(value.get("fundamental_statement_pack_policy") or ""), 100),
        "capital_macro_pack_policy": _truncate(str(value.get("capital_macro_pack_policy") or ""), 100),
        "product_evidence_pack_policy": _truncate(str(value.get("product_evidence_pack_policy") or ""), 100),
    }


def _compact_task_card_for_prompt(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    requirements = []
    for row in value.get("relevant_requirements") or []:
        if not isinstance(row, Mapping):
            continue
        requirements.append(
            {
                "requirement_id": str(row.get("requirement_id") or ""),
                "task_id": str(row.get("task_id") or ""),
                "priority": str(row.get("priority") or ""),
                "tickers": _string_list(row.get("tickers"))[:4],
                "source_families": _string_list(row.get("source_families"))[:4],
                "metric_families": _string_list(row.get("metric_families"))[:4],
                "question": _truncate(str(row.get("question_zh") or row.get("question") or ""), 90),
            }
        )
        if len(requirements) >= 4:
            break
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "agent_id": str(value.get("agent_id") or ""),
        "priority": str(value.get("priority") or ""),
        "assigned_memo_slot": str(value.get("assigned_memo_slot") or ""),
        "analyst_lens": _truncate(str(value.get("analyst_lens") or ""), 90),
        "focus_tickers": _string_list(value.get("focus_tickers"))[:6],
        "relevant_requirements": requirements,
    }


def _compact_claim_slots_for_prompt(value: Any, *, max_items: int) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, Mapping):
            continue
        slots.append(
            {
                "slot_id": str(item.get("slot_id") or ""),
                "slot_kind": str(item.get("slot_kind") or ""),
                "memo_slot": str(item.get("memo_slot") or ""),
                "metric_families": _string_list(item.get("metric_families"))[:4],
                "source_families": _string_list(item.get("source_families"))[:4],
                "required_tickers": _string_list(item.get("required_tickers") or item.get("tickers"))[:4],
                "description": _truncate(str(item.get("description") or item.get("question") or item.get("claim") or ""), 90),
            }
        )
        if len(slots) >= max_items:
            break
    return slots


def _compact_source_family_bundle_for_prompt(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "agent_id": str(value.get("agent_id") or ""),
        "selected_source_families": _string_list(value.get("selected_source_families"))[:8],
        "row_counts_by_source_family": dict(value.get("row_counts_by_source_family") or {})
        if isinstance(value.get("row_counts_by_source_family"), Mapping)
        else {},
        "context_only_source_families": _string_list(value.get("context_only_source_families"))[:8],
        "exact_value_authority_source_families": _string_list(value.get("exact_value_authority_source_families"))[:8],
        "forbidden_claim_scopes": _string_list(value.get("forbidden_claim_scopes"))[:8],
        "semantic_supplement_row_count": value.get("semantic_supplement_row_count"),
        "semantic_supplement_policy": str(value.get("semantic_supplement_policy") or ""),
    }


def _compact_input_coverage_summary_for_prompt(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    authority = value.get("non_financial_signal_authority") if isinstance(value.get("non_financial_signal_authority"), Mapping) else {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "agent_id": str(value.get("agent_id") or ""),
        "focus_tickers": _string_list(value.get("focus_tickers"))[:8],
        "prompt_row_distribution": value.get("prompt_row_distribution") or {},
        "focus_ticker_primary_row_counts": dict(value.get("focus_ticker_primary_row_counts") or {})
        if isinstance(value.get("focus_ticker_primary_row_counts"), Mapping)
        else {},
        "focus_ticker_source_gap_reasons": dict(value.get("focus_ticker_source_gap_reasons") or {})
        if isinstance(value.get("focus_ticker_source_gap_reasons"), Mapping)
        else {},
        "non_financial_signal_authority": {
            "thesis_driver_authority_row_count": authority.get("thesis_driver_authority_row_count"),
            "by_signal_authority_type": dict(authority.get("by_signal_authority_type") or {})
            if isinstance(authority.get("by_signal_authority_type"), Mapping)
            else {},
            "by_signal_promotion_level": dict(authority.get("by_signal_promotion_level") or {})
            if isinstance(authority.get("by_signal_promotion_level"), Mapping)
            else {},
        },
        "coverage_policy": str(value.get("coverage_policy") or ""),
    }


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
    product_spec_pack = request.get("product_spec_pack")
    if isinstance(product_spec_pack, Mapping):
        for key in (
            "product_families",
            "product_models",
            "product_specs",
            "product_kpi_refs",
            "generation_edges",
            "competitive_comparable_edges",
            "channel_offers",
            "field_inquiry_notes",
            "customer_deployment_signals",
            "supply_chain_signals",
            "commercial_gaps",
        ):
            for item in product_spec_pack.get(key) or []:
                if not isinstance(item, Mapping):
                    continue
                refs.update(_string_list(item.get("evidence_refs")))
                for ref_key in ("evidence_ref", "source_id", "raw_record_ref"):
                    value = str(item.get(ref_key) or "").strip()
                    if value:
                        refs.add(value)
    capital_macro_pack = request.get("capital_macro_pack")
    if isinstance(capital_macro_pack, Mapping):
        for key in (
            "capital_structures",
            "debt_instruments",
            "credit_facilities",
            "equity_offerings",
            "ownership_positions",
            "insider_transactions",
            "macro_drivers",
            "trade_drivers",
            "industry_drivers",
            "company_exposure_edges",
            "vertical_official_objects",
        ):
            for item in capital_macro_pack.get(key) or []:
                if not isinstance(item, Mapping):
                    continue
                refs.update(_string_list(item.get("evidence_refs")))
                for ref_key in ("evidence_ref", "source_id"):
                    value = str(item.get(ref_key) or "").strip()
                    if value:
                        refs.add(value)
    fundamental_statement_pack = request.get("fundamental_statement_pack")
    if isinstance(fundamental_statement_pack, Mapping):
        for key in (
            "statement_line_items",
            "period_changes",
            "peer_comparisons",
            "industry_focus_coverage",
            "integration_bridges",
            "analysis_gaps",
        ):
            for item in fundamental_statement_pack.get(key) or []:
                if not isinstance(item, Mapping):
                    continue
                refs.update(_string_list(item.get("evidence_refs")))
                for ref_key in ("evidence_ref", "source_id", "source_fact_id", "line_item_id", "change_id", "comparison_id"):
                    value = str(item.get(ref_key) or "").strip()
                    if value:
                        refs.add(value)
    fundamental_peer_statement_panel = request.get("fundamental_peer_statement_panel")
    if isinstance(fundamental_peer_statement_panel, Mapping):
        for key in (
            "analysis_gaps",
        ):
            for item in fundamental_peer_statement_panel.get(key) or []:
                if not isinstance(item, Mapping):
                    continue
                refs.update(_string_list(item.get("evidence_refs")))
                for ref_key in ("evidence_ref", "source_id", "source_fact_id", "line_item_id", "gap_id"):
                    value = str(item.get(ref_key) or "").strip()
                    if value:
                        refs.add(value)
        for panel_key, row_keys in (
            ("three_statement_metric_panel", ("statements",)),
            ("peer_comparable_metric_panel", ("comparisons",)),
            ("industry_priority_metric_panel", ("coverage",)),
            ("derived_metric_panel", ("rows",)),
            ("product_financial_bridge", ("bridges",)),
            ("capital_funding_bridge", ("bridges",)),
            ("statement_anomaly_detector", ("items",)),
        ):
            panel = fundamental_peer_statement_panel.get(panel_key)
            if not isinstance(panel, Mapping):
                continue
            for row_key in row_keys:
                for item in panel.get(row_key) or []:
                    if not isinstance(item, Mapping):
                        continue
                    refs.update(_string_list(item.get("evidence_refs")))
                    for ref_key in ("evidence_ref", "source_id", "source_fact_id", "line_item_id", "change_id", "comparison_id"):
                        value = str(item.get(ref_key) or "").strip()
                        if value:
                            refs.add(value)
                    for nested_key in ("latest_rows", "peer_values"):
                        for nested in item.get(nested_key) or []:
                            if not isinstance(nested, Mapping):
                                continue
                            refs.update(_string_list(nested.get("evidence_refs")))
                            for ref_key in ("evidence_ref", "source_id", "source_fact_id", "line_item_id"):
                                value = str(nested.get(ref_key) or "").strip()
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
    agent_id: str = "industry_supply_chain_analyst",
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    max_rows = _relationship_summary_max_rows_for_prompt(execution_mode)
    relationship_rows = [dict(row) for row in value.get("relationships") or [] if isinstance(row, Mapping)]
    focus_tickers = _unique_upper(value.get("focus_tickers") or value.get("expanded_tickers"))
    if agent_id == "product_technology_analyst":
        selected_rows = _product_relationship_summary_rows_for_prompt(
            relationship_rows,
            focus_tickers=focus_tickers,
            max_rows=max(1, max_rows),
        )
    else:
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


def _product_relationship_summary_rows_for_prompt(
    rows: list[dict[str, Any]],
    *,
    focus_tickers: list[str],
    max_rows: int,
) -> list[dict[str, Any]]:
    if not rows or max_rows <= 0:
        return []
    focus = set(_unique_upper(focus_tickers))

    def _score(row: Mapping[str, Any]) -> int:
        ticker = str(row.get("ticker") or "").strip().upper()
        related = str(row.get("related_ticker") or "").strip().upper()
        text = " ".join(
            str(row.get(key) or "").lower()
            for key in ("relationship_type", "edge_type", "evidence_ref", "summary", "source_family")
        )
        score = 0
        if ticker in focus and related in focus:
            score += 14
        elif ticker in focus:
            score += 9
        elif related in focus:
            score += 7
        if any(term in text for term in ("accelerator", "gpu", "tpu", "server", "rack", "cloud", "ai ")):
            score += 6
        if any(term in text for term in ("customer", "deployment", "configured", "adoption", "channel_offer")):
            score += 4
        if any(term in text for term in ("supplier", "supply", "input", "component")):
            score += 3
        if str(row.get("evidence_ref") or "").strip():
            score += 1
        return score

    ranked = [
        row
        for _, row in sorted(
            list(enumerate(rows)),
            key=lambda item: (-_score(item[1]), item[0]),
        )
    ]
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    for ticker in focus_tickers:
        upper = str(ticker or "").strip().upper()
        if not upper:
            continue
        for row in ranked:
            if len(selected) >= max_rows:
                return selected
            if id(row) in selected_ids:
                continue
            if upper not in {
                str(row.get("ticker") or "").strip().upper(),
                str(row.get("related_ticker") or "").strip().upper(),
            }:
                continue
            selected.append(row)
            selected_ids.add(id(row))
            break
    for row in ranked:
        if len(selected) >= max_rows:
            break
        if id(row) in selected_ids:
            continue
        selected.append(row)
        selected_ids.add(id(row))
    return selected


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
        "source_layer_distribution": _compact_source_layer_distribution_for_route(
            payload.get("source_layer_distribution") if isinstance(payload.get("source_layer_distribution"), Mapping) else {}
        ),
        "source_family_bundle": payload.get("source_family_bundle") or {},
        "product_spec_pack": _compact_product_spec_pack_for_repair(payload.get("product_spec_pack")),
        "capital_macro_pack": _compact_capital_macro_pack_for_repair(payload.get("capital_macro_pack")),
        "fundamental_statement_pack": _compact_fundamental_statement_pack_for_repair(
            payload.get("fundamental_statement_pack")
        ),
        "fundamental_peer_statement_panel": _compact_fundamental_peer_statement_panel_for_repair(
            payload.get("fundamental_peer_statement_panel")
        ),
        "relationship_summary": compact_relationship_summary,
        "output_contract": payload.get("output_contract") or _specialist_output_contract(str(payload.get("agent_id") or ""), str(payload.get("execution_mode") or "")),
        "known_evidence_refs": {
            "visible_refs": _repair_known_refs(payload)[:24],
            "policy": "cite only visible refs from bounded_evidence_rows, product_spec_pack, capital_macro_pack, fundamental_peer_statement_panel, or relationship_summary",
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


def _compact_product_spec_pack_for_prompt(value: Any, *, agent_id: str = "") -> dict[str, Any]:
    if agent_id != "product_technology_analyst":
        return {}
    compact = _compact_product_spec_pack(
        value,
        max_items=_prompt_pack_max_items("PRODUCT_SPEC_PACK_PROMPT_MAX_ITEMS", 3),
        section_keys=(
            "product_specs",
            "product_kpi_refs",
            "channel_offers",
            "field_inquiry_notes",
            "commercial_gaps",
            "rejected_objects",
        ),
    )
    if compact:
        compact["role_projection_policy"] = "product_prompt_specs_kpi_channel_only_v0_1"
        compact["excluded_sections"] = ["customer_deployment_signals", "supply_chain_signals"]
    return compact


def _compact_product_spec_pack_for_repair(value: Any) -> dict[str, Any]:
    return _compact_product_spec_pack(value, max_items=4)


def _compact_product_spec_pack(value: Any, *, max_items: int, section_keys: tuple[str, ...] | None = None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    compact = {
        "schema_version": value.get("schema_version") or "",
        "pack_id": value.get("pack_id") or "",
        "status": value.get("status") or "",
        "summary": _compact_pack_metadata(value.get("summary") or {}, max_items=8, text_limit=120),
        "boundary_policy": _compact_pack_metadata(value.get("boundary_policy") or {}, max_items=6, text_limit=140),
    }
    all_keys = (
        "product_specs",
        "product_kpi_refs",
        "channel_offers",
        "field_inquiry_notes",
        "customer_deployment_signals",
        "supply_chain_signals",
        "commercial_gaps",
        "rejected_objects",
    )
    for key in section_keys or all_keys:
        compact[key] = [
            _compact_pack_prompt_row(item)
            for item in value.get(key) or []
            if isinstance(item, Mapping)
        ][:max(1, max_items)]
    for key in all_keys:
        compact.setdefault(key, [])
    return compact


def _compact_capital_macro_pack_for_prompt(value: Any, *, agent_id: str = "") -> dict[str, Any]:
    if agent_id not in {"fundamental_analyst", "industry_supply_chain_analyst", "risk_counterevidence_analyst"}:
        return {}
    return _compact_capital_macro_pack(
        value,
        max_items=_prompt_pack_max_items("CAPITAL_MACRO_PACK_PROMPT_MAX_ITEMS", 5),
        agent_id=agent_id,
    )


def _compact_capital_macro_pack_for_repair(value: Any) -> dict[str, Any]:
    return _compact_capital_macro_pack(value, max_items=4)


def _compact_capital_macro_pack(value: Any, *, max_items: int, agent_id: str = "") -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    section_policy = _capital_macro_prompt_sections(agent_id)
    included_sections = section_policy["included_sections"]
    all_sections = (
        "debt_instruments",
        "ownership_positions",
        "insider_transactions",
        "macro_drivers",
        "company_exposure_edges",
        "vertical_official_objects",
        "rejected_objects",
    )
    compact = {
        "schema_version": value.get("schema_version") or "",
        "pack_id": value.get("pack_id") or "",
        "status": value.get("status") or "",
        "summary": value.get("summary") or {},
        "boundary_policy": value.get("boundary_policy") or {},
        "role_projection_policy": section_policy["policy"],
        "included_sections": included_sections,
        "excluded_sections": [key for key in all_sections if key not in set(included_sections)],
    }
    for key in included_sections:
        compact[key] = [
            _compact_pack_prompt_row(item)
            for item in value.get(key) or []
            if isinstance(item, Mapping)
        ][:max(1, max_items)]
    return compact


def _capital_macro_prompt_sections(agent_id: str) -> dict[str, Any]:
    role = str(agent_id or "").strip()
    if role == "fundamental_analyst":
        return {
            "policy": "role_projected_capital_macro_pack_v0_2_fundamental_capital_structure",
            "included_sections": [
                "debt_instruments",
                "ownership_positions",
                "insider_transactions",
                "company_exposure_edges",
            ],
        }
    if role == "industry_supply_chain_analyst":
        return {
            "policy": "role_projected_capital_macro_pack_v0_2_industry_exposure_edges",
            "included_sections": [
                "macro_drivers",
                "company_exposure_edges",
                "vertical_official_objects",
            ],
        }
    if role == "risk_counterevidence_analyst":
        return {
            "policy": "role_projected_capital_macro_pack_v0_2_risk_counterevidence",
            "included_sections": [
                "debt_instruments",
                "macro_drivers",
                "rejected_objects",
            ],
        }
    return {
        "policy": "role_projected_capital_macro_pack_v0_2_repair_full_boundary",
        "included_sections": [
            "debt_instruments",
            "ownership_positions",
            "insider_transactions",
            "macro_drivers",
            "company_exposure_edges",
            "vertical_official_objects",
            "rejected_objects",
        ],
    }


def _compact_fundamental_statement_pack_for_prompt(value: Any, *, agent_id: str = "") -> dict[str, Any]:
    if agent_id != "fundamental_analyst":
        return {}
    return _compact_fundamental_statement_pack(
        value,
        max_items=_prompt_pack_max_items("FUNDAMENTAL_STATEMENT_PACK_PROMPT_MAX_ITEMS", 6),
    )


def _compact_fundamental_statement_pack_for_repair(value: Any) -> dict[str, Any]:
    return _compact_fundamental_statement_pack(value, max_items=4)


def _compact_fundamental_statement_pack(value: Any, *, max_items: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    compact = {
        "schema_version": value.get("schema_version") or "",
        "industry_focus_policy": _compact_pack_metadata(
            value.get("industry_focus_policy") or {},
            max_items=6,
            text_limit=90,
        ),
        "summary": _compact_pack_metadata(
            value.get("summary") or {},
            max_items=8,
            text_limit=90,
        ),
        "source_boundary": _compact_pack_metadata(
            value.get("source_boundary") or {},
            max_items=6,
            text_limit=90,
        ),
    }
    for key in (
        "statement_line_items",
        "period_changes",
        "peer_comparisons",
        "industry_focus_coverage",
        "integration_bridges",
        "analysis_gaps",
    ):
        compact[key] = [
            _compact_pack_prompt_row(item)
            for item in value.get(key) or []
            if isinstance(item, Mapping)
        ][:max(1, max_items)]
    return compact


def _compact_fundamental_peer_statement_panel_for_prompt(value: Any, *, agent_id: str = "") -> dict[str, Any]:
    if agent_id != "fundamental_analyst":
        return {}
    return _compact_fundamental_peer_statement_panel(
        value,
        max_items=_prompt_pack_max_items("FUNDAMENTAL_PEER_PANEL_PROMPT_MAX_ITEMS", 5),
    )


def _compact_fundamental_peer_statement_panel_for_repair(value: Any) -> dict[str, Any]:
    return _compact_fundamental_peer_statement_panel(value, max_items=4)


def _compact_fundamental_peer_statement_panel(value: Any, *, max_items: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    compact = {
        "schema_version": value.get("schema_version") or "",
        "industry_financial_focus_policy": _compact_pack_metadata(
            value.get("industry_financial_focus_policy") or {},
            max_items=6,
            text_limit=90,
        ),
        "summary": _compact_pack_metadata(
            value.get("summary") or {},
            max_items=8,
            text_limit=90,
        ),
        "analysis_gates": _compact_pack_metadata(
            value.get("analysis_gates") or {},
            max_items=6,
            text_limit=90,
        ),
        "source_boundary": _compact_pack_metadata(
            value.get("source_boundary") or {},
            max_items=6,
            text_limit=90,
        ),
    }
    three_statement = value.get("three_statement_metric_panel") if isinstance(value.get("three_statement_metric_panel"), Mapping) else {}
    compact["three_statement_metric_panel"] = {
        "statement_type_counts": three_statement.get("statement_type_counts") or {},
        "statements": [
            _compact_pack_prompt_row(item)
            for item in three_statement.get("statements") or []
            if isinstance(item, Mapping)
        ][:3],
    }
    for key in (
        "peer_comparable_metric_panel",
        "industry_priority_metric_panel",
        "derived_metric_panel",
        "product_financial_bridge",
        "capital_funding_bridge",
        "statement_anomaly_detector",
    ):
        panel = value.get(key) if isinstance(value.get(key), Mapping) else {}
        compact_panel = _compact_pack_metadata(
            {
                panel_key: panel_value
                for panel_key, panel_value in panel.items()
                if panel_key
                not in {
                    "comparisons",
                    "coverage",
                    "rows",
                    "bridges",
                    "items",
                    "latest_rows",
                    "peer_values",
                }
            },
            max_items=6,
            text_limit=90,
        )
        for row_key in ("comparisons", "coverage", "rows", "bridges", "items"):
            if isinstance(compact_panel.get(row_key), list):
                compact_panel[row_key] = [
                    _compact_pack_prompt_row(item)
                    for item in compact_panel.get(row_key)
                    if isinstance(item, Mapping)
                ][:max(1, max_items)]
            elif isinstance(panel.get(row_key), list):
                compact_panel[row_key] = [
                    _compact_pack_prompt_row(item)
                    for item in panel.get(row_key)
                    if isinstance(item, Mapping)
                ][:max(1, max_items)]
        compact[key] = compact_panel
    compact["analysis_gaps"] = [
        _compact_pack_prompt_row(item)
        for item in value.get("analysis_gaps") or []
        if isinstance(item, Mapping)
    ][:max(1, max_items)]
    return compact


def _prompt_pack_max_items(env_name: str, default: int) -> int:
    return max(1, _int_env(os.environ.get(env_name), default=default))


def _compact_pack_prompt_row(item: Mapping[str, Any]) -> dict[str, Any]:
    clean = dict(item)
    for key, limit in (
        ("summary", 180),
        ("text", 140),
        ("snippet", 140),
        ("description", 140),
        ("notes", 120),
        ("rationale", 120),
        ("authority_boundary", 120),
    ):
        if key in clean:
            clean[key] = _truncate(str(clean.get(key) or ""), limit)
    return _compact_prompt_row(clean)


def _compact_pack_metadata(value: Any, *, max_items: int, text_limit: int) -> dict[str, Any]:
    return compact_prompt_metadata(
        value,
        max_items=max_items,
        text_limit=text_limit,
    )


def _compact_metadata_mapping(value: Mapping[str, Any], *, max_items: int, text_limit: int) -> dict[str, Any]:
    return compact_prompt_metadata(
        value,
        max_items=max_items,
        text_limit=text_limit,
    )


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
    """Project a row into the minimal prompt contract without losing citations."""
    source_family = str(row.get("source_family") or "").strip()
    base_allowlist = {
        "evidence_ref",
        "evidence_refs",
        "evidence_id",
        "ref_id",
        "refs",
        "raw_record_ref",
        "source_fact_id",
        "source_record_ref",
        "line_item_id",
        "change_id",
        "comparison_id",
        "source_family",
        "ticker",
        "related_ticker",
        "summary",
        "text",
        "snippet",
        "description",
        "notes",
        "rationale",
        "authority_boundary",
        "source_role",
        "source_entity_role",
        "claim_scope",
        "context_only",
        "exact_value_authority",
        "gap_only",
        "gap_type",
        "reason_code",
        "reason",
        "confidence",
        "materiality",
        "direction",
        "semantic_supplement",
    }
    numeric_fields = {
        "metric",
        "metric_name",
        "metric_family",
        "value",
        "unit",
        "display_value",
        "display_value_zh",
        "selected_for_display",
        "formatted_value",
        "period",
        "period_end",
        "period_role",
        "fy",
        "fp",
        "form_type",
    }
    product_fields = {
        "product_family",
        "product_or_segment",
        "product",
        "promotion_status",
        "product_binding_status",
        "runtime_contract",
        *numeric_fields,
    }
    public_context_fields = {
        "source_id",
        "underlying_source_family",
        "source_class",
        "structured_context_type",
        "authority_type",
        "signal_authority_type",
        "signal_promotion_level",
        "issuer_binding_status",
        "product_binding_status",
        "counterparty_binding_status",
        "entity_binding",
        "entity_binding_claim_boundary",
    }
    relationship_fields = {
        "from_ticker",
        "to_ticker",
        "relationship_type",
        "edge_type",
        "mechanism",
        "metric_links",
    }
    if source_family == "company_product_evidence_graph":
        allowlist = base_allowlist | product_fields
    elif source_family in {"public_source_context", "live_public_web_context"}:
        allowlist = base_allowlist | public_context_fields
    elif source_family == "relationship_graph":
        allowlist = base_allowlist | relationship_fields
    elif source_family in {"primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot", "industry_snapshot", ""}:
        allowlist = base_allowlist | numeric_fields | {"signal_authority_type", "signal_promotion_level"}
    else:
        allowlist = base_allowlist | numeric_fields | product_fields | public_context_fields | relationship_fields
    text_limits = {
        "summary": 120,
        "reason": 120,
        "entity_binding_claim_boundary": 120,
        "text": 120,
        "snippet": 120,
        "description": 120,
        "notes": 120,
        "rationale": 120,
        "authority_boundary": 120,
        "mechanism": 120,
        "source_url": 180,
        "snapshot_url": 180,
        "url": 180,
    }
    reference_fields = {
        "evidence_ref",
        "evidence_refs",
        "evidence_id",
        "ref_id",
        "refs",
        "raw_record_ref",
        "source_id",
        "source_fact_id",
        "source_record_ref",
        "line_item_id",
        "change_id",
        "comparison_id",
        "metric_id",
        "gap_id",
        "id",
    }
    clean: dict[str, Any] = {}
    for key, value in row.items():
        key_text = str(key)
        if key_text not in allowlist:
            continue
        if _prompt_value_empty(value):
            continue
        if key_text in reference_fields:
            refs = _string_list(value)
            clean[key_text] = refs[:4] if isinstance(value, (list, tuple, set)) else (refs[0] if refs else "")
        elif isinstance(value, (list, tuple, set)):
            clean[key_text] = [_truncate(str(item), 80) for item in list(value)[:4] if not _prompt_value_empty(item)]
        elif isinstance(value, Mapping):
            clean[key_text] = _compact_pack_metadata(
                value,
                max_items=8 if key_text == "entity_binding" else 4,
                text_limit=80,
            )
        elif isinstance(value, str):
            clean[key_text] = _truncate(value, text_limits.get(key_text, 80))
        else:
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


_PRODUCT_PROMPT_TERMS = (
    "product",
    "products",
    "sku",
    "model",
    "spec",
    "specification",
    "architecture",
    "platform",
    "generation",
    "taxonomy",
    "benchmark",
    "performance",
    "developer",
    "api",
    "software",
    "semiconductor",
    "gpu",
    "cpu",
    "accelerator",
    "hbm",
    "server",
    "segment",
    "kpi",
    "revenue",
    "margin",
    "gross margin",
    "shipment",
    "delivery",
    "capacity",
    "utilization",
    "channel_offer",
    "field_inquiry",
    "field_inquiry_note",
    "company_official_product_surface",
    "commerce_product_surface",
    "pricing",
    "availability",
)

_PRODUCT_PROMPT_EXCLUSION_TERMS = (
    "customer_deployment",
    "customer_deployment_signal",
    "official_customer_deployment_surface",
    "deployment",
    "deployed_by",
    "adopted_by",
    "ordered_by",
    "customer",
    "counterparty",
    "supply_chain",
    "supply_chain_signal",
    "supplier",
    "partner",
    "relationship",
    "component_input_to",
    "public_order",
    "contract award",
)

_INDUSTRY_PROMPT_TERMS = (
    "relationship",
    "supplier",
    "supply",
    "supply chain",
    "component",
    "customer",
    "deployment",
    "deployed",
    "adoption",
    "ordered",
    "order",
    "backlog",
    "booking",
    "capex",
    "demand",
    "cycle",
    "industry",
    "sector",
    "fab",
    "wafer",
    "foundry",
    "memory",
    "logic",
    "export",
    "restriction",
    "competitive",
    "competes",
    "substitute",
    "downstream",
    "upstream",
    "channel",
    "distributor",
    "sold_through",
)

_INDUSTRY_PRODUCT_CONTEXT_TERMS = (
    "relationship",
    "supplier",
    "supply",
    "supply chain",
    "component",
    "customer",
    "deployment",
    "deployed",
    "adoption",
    "adopted",
    "ordered",
    "order",
    "backlog",
    "booking",
    "downstream",
    "upstream",
    "channel",
    "distributor",
    "sold_through",
    "configured_in",
)

_RISK_PROMPT_TERMS = (
    "risk",
    "risks",
    "decline",
    "pressure",
    "gap",
    "missing",
    "weak",
    "uncertain",
    "uncertainty",
    "constraint",
    "caveat",
    "lawsuit",
    "litigation",
    "regulatory",
    "export",
    "export control",
    "restriction",
    "china",
    "sanction",
    "tariff",
    "concentration",
    "dependency",
    "dependence",
    "bottleneck",
    "shortage",
    "cyclical",
    "cycle",
    "downturn",
    "inventory",
    "cancellation",
    "delay",
    "impairment",
    "debt",
    "liquidity",
    "cash burn",
    "margin pressure",
    "cost pressure",
    "competition",
    "competitive",
    "loss",
    "adverse",
    "exposure",
    "limited",
    "fail",
    "conflict",
    "counter",
    "counterevidence",
)


def _role_filtered_prompt_rows(
    agent_id: str,
    rows: list[dict[str, Any]],
    *,
    task_card: Mapping[str, Any],
    required_claim_slots: list[Any],
    counterclaim_slots: list[Any],
) -> list[dict[str, Any]]:
    if agent_id not in {"product_technology_analyst", "industry_supply_chain_analyst", "risk_counterevidence_analyst"}:
        return rows
    selected = [
        row
        for row in rows
        if _row_allowed_for_role_prompt(
            agent_id,
            row,
            task_card=task_card,
            required_claim_slots=required_claim_slots,
            counterclaim_slots=counterclaim_slots,
        )
    ]
    return selected


def _row_allowed_for_role_prompt(
    agent_id: str,
    row: Mapping[str, Any],
    *,
    task_card: Mapping[str, Any],
    required_claim_slots: list[Any],
    counterclaim_slots: list[Any],
) -> bool:
    family = str(row.get("source_family") or "")
    text = _row_role_prompt_text(row)
    if agent_id == "product_technology_analyst":
        if _has_any_prompt_term(text, _PRODUCT_PROMPT_EXCLUSION_TERMS):
            # Deployment, customer, and supply-chain rows are intentionally handled by
            # the industry/supply-chain lens so the same evidence is not reread by
            # both specialists.
            return False
        if family == "company_product_evidence_graph":
            if str(row.get("promotion_status") or "") == "runtime_fact_allowed":
                return True
            return _has_any_prompt_term(text, _PRODUCT_PROMPT_TERMS)
        if family in {"public_source_context", "live_public_web_context"}:
            return _has_any_prompt_term(text, _PRODUCT_PROMPT_TERMS)
        return _has_any_prompt_term(text, _PRODUCT_PROMPT_TERMS)
    if agent_id == "industry_supply_chain_analyst":
        if family in {"relationship_graph", "industry_snapshot"}:
            return True
        if family in {"company_product_evidence_graph", "public_source_context", "live_public_web_context"}:
            return _has_any_prompt_term(text, _INDUSTRY_PRODUCT_CONTEXT_TERMS)
        return _has_any_prompt_term(text, _INDUSTRY_PROMPT_TERMS)
    if agent_id == "risk_counterevidence_analyst":
        if _has_any_prompt_term(text, _RISK_PROMPT_TERMS):
            return True
        if _risk_relevant_financial_row_for_prompt(row):
            return True
        if family == "relationship_graph":
            return True
        if family in {"market_snapshot", "industry_snapshot"} and _matches_claim_slot_terms(row, [task_card]):
            return True
        return False
    return True


def _row_role_prompt_text(row: Mapping[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "").lower()
        for key in (
            "evidence_ref",
            "source_family",
            "source_role",
            "source_class",
            "structured_context_type",
            "runtime_contract",
            "signal_authority_type",
            "signal_promotion_level",
            "authority_type",
            "claim_scope",
            "metric",
            "metric_name",
            "period_role",
            "product_family",
            "product_or_segment",
            "model_name",
            "spec_name",
            "current_model",
            "prior_model",
            "channel_name",
            "inquiry_target",
            "relationship_type",
            "edge_type",
            "direction",
            "source_entity_role",
            "entity_binding_claim_boundary",
            "summary",
        )
    )


def _has_any_prompt_term(text: str, terms: tuple[str, ...]) -> bool:
    for term in terms:
        if not term:
            continue
        if " " in term:
            if term in text:
                return True
            continue
        if re.search(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", text):
            return True
    return False


def _matches_claim_slot_terms(row: Mapping[str, Any], slots: list[Any]) -> bool:
    if not slots:
        return False
    text = _row_role_prompt_text(row)
    terms: set[str] = set()
    for slot in slots:
        for term in _terms_from_value(slot):
            if len(term) >= 3:
                terms.add(term)
    return any(term in text for term in terms)


def _risk_relevant_financial_row_for_prompt(row: Mapping[str, Any]) -> bool:
    family = str(row.get("source_family") or "")
    if family not in {"primary_sec_filing", "company_authored_unaudited_sec_filing", "derived_metric_layer"}:
        return False
    requirement_ids: set[str] = set()
    requirement_ids.update(_string_list(row.get("evidence_requirement_id")))
    requirement_ids.update(_string_list(row.get("evidence_requirement_ids")))
    requirement_ids.update(_string_list(row.get("selection_task_ids")))
    if requirement_ids & {
        "req_dell_margin_quality",
        "req_hyperscaler_capex",
        "req_supply_chain",
        "req_customer_deployment",
        "req_accelerator_architecture",
    }:
        return True
    text = _row_metric_text(row)
    return any(
        term in text
        for term in (
            "capex",
            "capital expenditure",
            "property and equipment",
            "gross margin",
            "margin",
            "operating income",
            "cash flow",
            "inventory",
            "backlog",
            "debt",
            "cash",
        )
    )


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
    rows = _role_filtered_prompt_rows(
        agent_id,
        rows,
        task_card=task_card,
        required_claim_slots=required_claim_slots,
        counterclaim_slots=counterclaim_slots,
    )
    if not rows:
        return []
    terms = _selection_terms(task_card, required_claim_slots, counterclaim_slots, agent_id=agent_id)
    ranked = _rank_rows_for_prompt(rows, terms, agent_id=agent_id)
    if agent_id == "industry_supply_chain_analyst":
        return _relationship_preserving_selection(ranked, max_rows=max_rows)
    if agent_id == "product_technology_analyst":
        focus_tickers = _unique_upper(task_card.get("focus_tickers") or task_card.get("search_scope_tickers"))
        if len(focus_tickers) >= 2:
            return _focus_ticker_balanced_prompt_rows(
                ranked,
                focus_tickers=focus_tickers,
                max_rows=max_rows,
                source_families={"company_product_evidence_graph", "public_source_context", "live_public_web_context"},
            )
        return _balanced_rows_by_source_for_prompt(ranked, max_rows=max_rows)
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
                    "relationship_graph",
                    "run_artifact",
                }
                return _risk_counterevidence_prompt_rows(
                    ranked,
                    focus_tickers=focus_tickers,
                    max_rows=max_rows,
                    source_families=source_families,
                )
            return _fundamental_prompt_rows(
                ranked,
                focus_tickers=focus_tickers,
                max_rows=max_rows,
                source_families=source_families,
            )
    if agent_id == "risk_counterevidence_analyst":
        return _balanced_rows_by_source_for_prompt(ranked, max_rows=max_rows)
    return ranked[:max_rows]


def _fundamental_prompt_rows(
    rows: list[dict[str, Any]],
    *,
    focus_tickers: list[str],
    max_rows: int,
    source_families: set[str],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()

    def add(row: dict[str, Any]) -> None:
        if len(selected) >= max_rows or id(row) in selected_ids:
            return
        selected.append(row)
        selected_ids.add(id(row))

    for requirement_id, limit in (("req_dell_margin_quality", 3), ("req_hyperscaler_capex", 3)):
        count = 0
        for row in rows:
            if count >= limit:
                break
            if _row_has_prompt_requirement(row, {requirement_id}):
                add(row)
                count += 1
        if requirement_id == "req_hyperscaler_capex":
            for row in _requirement_rows_by_distinct_ticker(rows, requirement_id=requirement_id, limit=2):
                add(row)

    for row in _focus_ticker_balanced_prompt_rows(
        rows,
        focus_tickers=focus_tickers,
        max_rows=max_rows,
        source_families=source_families,
        priority_source_families=("primary_sec_filing", "company_authored_unaudited_sec_filing"),
    ):
        add(row)
    return selected[:max_rows]


def _risk_counterevidence_prompt_rows(
    rows: list[dict[str, Any]],
    *,
    focus_tickers: list[str],
    max_rows: int,
    source_families: set[str],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()

    def add(row: dict[str, Any]) -> None:
        if len(selected) >= max_rows or id(row) in selected_ids:
            return
        selected.append(row)
        selected_ids.add(id(row))

    for requirement_id, limit in (
        ("req_dell_margin_quality", 2),
        ("req_hyperscaler_capex", 2),
        ("req_supply_chain", 1),
        ("req_customer_deployment", 1),
    ):
        count = 0
        for row in rows:
            if count >= limit:
                break
            if _row_has_prompt_requirement(row, {requirement_id}):
                add(row)
                count += 1
        if requirement_id == "req_hyperscaler_capex":
            for row in _requirement_rows_by_distinct_ticker(rows, requirement_id=requirement_id, limit=2):
                add(row)

    for family, limit in (("relationship_graph", 2), ("market_snapshot", 1), ("industry_snapshot", 1)):
        count = 0
        for row in rows:
            if count >= limit:
                break
            if str(row.get("source_family") or "") == family:
                add(row)
                count += 1

    for row in _focus_ticker_balanced_prompt_rows(
        rows,
        focus_tickers=focus_tickers,
        max_rows=max_rows,
        source_families=source_families,
        priority_source_families=(
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "relationship_graph",
            "market_snapshot",
            "industry_snapshot",
        ),
    ):
        add(row)
    return selected[:max_rows]


def _row_has_prompt_requirement(row: Mapping[str, Any], requirement_ids: set[str]) -> bool:
    values: list[str] = []
    values.extend(_string_list(row.get("evidence_requirement_id")))
    values.extend(_string_list(row.get("evidence_requirement_ids")))
    values.extend(_string_list(row.get("selection_task_ids")))
    values.extend(_string_list(row.get("task_id")))
    return bool(set(values) & requirement_ids)


def _requirement_rows_by_distinct_ticker(
    rows: list[dict[str, Any]],
    *,
    requirement_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_tickers: set[str] = set()
    for row in rows:
        if len(selected) >= limit:
            break
        ticker = _row_ticker(row)
        if not ticker or ticker in seen_tickers or not _row_has_prompt_requirement(row, {requirement_id}):
            continue
        selected.append(row)
        seen_tickers.add(ticker)
    return selected


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
            "source_role",
            "runtime_contract",
            "signal_authority_type",
            "signal_promotion_level",
            "product_family",
            "product_or_segment",
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
    elif agent_id == "product_technology_analyst" and family == "company_product_evidence_graph":
        score += 6 if str(row.get("promotion_status") or "") == "runtime_fact_allowed" else 4
    elif agent_id == "product_technology_analyst" and family in {"public_source_context", "live_public_web_context"}:
        score += 3
        if bool(row.get("thesis_driver_authority")):
            score += 5
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
        "product_technology_analyst": ["product", "segment", "sku", "taxonomy", "platform", "developer", "clinical", "regulatory", "proxy", "gap"],
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
        "company_product_evidence_graph",
        "public_source_context",
        "live_public_web_context",
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
    bounded = {
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
    for key in (
        "source_class",
        "structured_context_type",
        "product_family",
        "product_or_segment",
        "issuer_binding_status",
        "product_binding_status",
        "counterparty_binding_status",
        "entity_binding_claim_boundary",
        "source_role",
        "runtime_contract",
        "signal_authority_type",
        "signal_promotion_level",
        "claim_boundary",
    ):
        value = str(row.get(key) or "").strip()
        if value:
            bounded[key] = value
    if "thesis_driver_authority" in row:
        bounded["thesis_driver_authority"] = bool(row.get("thesis_driver_authority"))
    allowed_signal_claims = _string_list(row.get("allowed_non_financial_claims"))[:8]
    if allowed_signal_claims:
        bounded["allowed_non_financial_claims"] = allowed_signal_claims
    signal_authority = row.get("non_financial_signal_authority")
    if isinstance(signal_authority, Mapping):
        bounded["non_financial_signal_authority"] = {
            "signal_authority_type": str(signal_authority.get("signal_authority_type") or ""),
            "promotion_level": str(signal_authority.get("promotion_level") or ""),
            "thesis_driver_authority": bool(signal_authority.get("thesis_driver_authority")),
            "exact_financial_fact_authority": bool(signal_authority.get("exact_financial_fact_authority")),
            "claim_boundary": str(signal_authority.get("claim_boundary") or "")[:240],
            "allowed_claim_types": _string_list(signal_authority.get("allowed_claim_types"))[:6],
            "forbidden_claim_types": _string_list(signal_authority.get("forbidden_claim_types"))[:8],
        }
    entity_binding = row.get("entity_binding") if isinstance(row.get("entity_binding"), Mapping) else {}
    if entity_binding:
        source_entity_role = str(entity_binding.get("source_entity_role") or row.get("source_entity_role") or "").strip()
        if source_entity_role:
            bounded["source_entity_role"] = source_entity_role
        bounded["entity_binding"] = {
            "issuer_binding_status": row.get("issuer_binding_status") or entity_binding.get("issuer_binding_status") or "",
            "product_binding_status": row.get("product_binding_status") or entity_binding.get("product_binding_status") or "",
            "counterparty_binding_status": row.get("counterparty_binding_status") or entity_binding.get("counterparty_binding_status") or "",
            "source_entity_role": source_entity_role,
            "issuer_matched_terms": _string_list(entity_binding.get("issuer_matched_terms"))[:6],
            "product_matched_terms": _string_list(entity_binding.get("product_matched_terms"))[:6],
            "counterparty_matched_terms": _string_list(entity_binding.get("counterparty_matched_terms"))[:6],
            "binding_claim_boundary": entity_binding.get("binding_claim_boundary") or row.get("entity_binding_claim_boundary") or "",
        }
    elif str(row.get("source_entity_role") or "").strip():
        bounded["source_entity_role"] = str(row.get("source_entity_role") or "").strip()
    return bounded


def _source_boundaries_from_state(state: Mapping[str, Any]) -> dict[str, Any]:
    plan = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    fused_counts = _fusion_source_family_counts(state)
    return {
        "execution_mode": str(plan.get("execution_mode") or state.get("execution_mode") or ""),
        "allowed_source_families": list(plan.get("allowed_source_families") or []),
        "context_row_count": len(state.get("context_rows") or [])
        or sum(fused_counts.get(family, 0) for family in ("company_authored_unaudited_sec_filing", "relationship_graph")),
        "ledger_row_count": len(state.get("runtime_ledger_rows") or []) or fused_counts.get("primary_sec_filing", 0),
        "market_row_count": len(state.get("market_snapshot_rows") or []) or fused_counts.get("market_snapshot", 0),
        "industry_row_count": len(state.get("industry_snapshot_rows") or []) or fused_counts.get("industry_snapshot", 0),
        "fusion_authority_row_count": sum(fused_counts.values()),
    }


def _fusion_source_family_counts(state: Mapping[str, Any]) -> dict[str, int]:
    bundle = state.get("evidence_fusion_bundle") if isinstance(state.get("evidence_fusion_bundle"), Mapping) else {}
    rows = [dict(item) for item in bundle.get("authority_rows") or [] if isinstance(item, Mapping)]
    counts: dict[str, int] = {}
    for row in rows:
        family = str(row.get("source_family") or row.get("runtime_source_family") or row.get("source_tier") or "").strip()
        if not family:
            continue
        counts[family] = counts.get(family, 0) + 1
    return counts


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
    restored_memolet, restored_count = _restore_truncated_evidence_refs_in_memolet(
        memolet,
        known_evidence_refs=known_evidence_refs,
    )
    if restored_count:
        restored_validation = validate_specialist_memolet(restored_memolet, known_evidence_refs=known_evidence_refs)
        if restored_validation.get("status") == "pass":
            restored_validation["warnings"] = [
                *list(validation.get("warnings") or []),
                *list(restored_validation.get("warnings") or []),
                {
                    "type": "truncated_evidence_refs_restored_from_known_refs",
                    "restored_count": restored_count,
                    "policy": "repair_machine_ref_lineage_before_demoting_supported_observations",
                },
            ]
            return restored_validation
        memolet = restored_memolet
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
    if not removed:
        return None
    agent_id = str(memolet.get("agent_id") or "").strip()
    if not kept and agent_id != "risk_counterevidence_analyst":
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


def _restore_truncated_evidence_refs_in_memolet(
    memolet: Mapping[str, Any],
    *,
    known_evidence_refs: set[str],
) -> tuple[dict[str, Any], int]:
    if not known_evidence_refs:
        return dict(memolet), 0
    known = sorted(str(ref) for ref in known_evidence_refs if str(ref).strip())
    restored = dict(memolet)
    restored_count = 0
    for key in ("observations", "unsupported_claims"):
        rows: list[dict[str, Any]] = []
        for item in restored.get(key) or []:
            if not isinstance(item, Mapping):
                continue
            row = dict(item)
            refs, count = _restore_truncated_evidence_ref_list(
                _string_list(row.get("evidence_refs") or row.get("refs")),
                known_refs=known,
            )
            if count:
                row["evidence_refs"] = refs
                restored_count += count
            rows.append(row)
        if rows:
            restored[key] = rows
    return restored, restored_count


def _restore_truncated_evidence_ref_list(refs: list[str], *, known_refs: list[str]) -> tuple[list[str], int]:
    restored: list[str] = []
    restored_count = 0
    for ref in refs:
        new_ref = _restore_truncated_evidence_ref(ref, known_refs=known_refs)
        if new_ref != ref:
            restored_count += 1
        restored.append(new_ref)
    return _dedupe_strings(restored), restored_count


def _restore_truncated_evidence_ref(ref: str, *, known_refs: list[str]) -> str:
    text = str(ref or "").strip()
    marker = "...[truncated]"
    if marker not in text:
        return text
    prefix = text.split(marker, 1)[0].rstrip()
    if not prefix:
        return text
    matches = [known for known in known_refs if known.startswith(prefix) and marker not in known]
    return matches[0] if len(matches) == 1 else text


def _salvage_product_kpi_authority_violations(
    validation: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    known_evidence_refs: set[str],
) -> dict[str, Any] | None:
    memolet = dict(validation.get("memolet") or {})
    if str(memolet.get("agent_id") or "") != "product_technology_analyst":
        return None
    row_by_ref = _row_by_known_ref_from_request(request)
    observations = [dict(item) for item in memolet.get("observations") or [] if isinstance(item, Mapping)]
    kept: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for observation in observations:
        if not _is_product_kpi_observation(observation):
            kept.append(observation)
            continue
        refs = _string_list(observation.get("evidence_refs") or observation.get("refs"))
        rows = [row_by_ref.get(ref) or {} for ref in refs]
        if refs and rows and all(_row_has_product_kpi_exact_authority(row) for row in rows):
            kept.append(observation)
            continue
        removed.append(
            {
                "claim": _truncate(str(observation.get("claim") or "Unsupported product KPI claim."), 240),
                "reason": "demoted_product_kpi_without_company_disclosed_exact_authority",
                "evidence_refs": refs,
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
    metadata["salvage_policy"] = "demote_product_kpi_without_exact_authority_v0_1"
    metadata["salvaged_observation_count"] = int(metadata.get("salvaged_observation_count") or 0) + len(removed)
    repaired["metadata"] = metadata
    salvaged = validate_specialist_memolet(repaired, known_evidence_refs=known_evidence_refs)
    if salvaged.get("status") != "pass":
        return None
    salvaged["warnings"] = [
        *list(validation.get("warnings") or []),
        *list(salvaged.get("warnings") or []),
        {
            "type": "product_kpi_observation_demoted",
            "removed_count": len(removed),
            "policy": "product_kpi_claims_require_company_product_evidence_graph_runtime_fact_allowed_exact_authority",
        },
    ]
    return salvaged


def _is_product_kpi_observation(observation: Mapping[str, Any]) -> bool:
    claim_type = str(observation.get("claim_type") or "").strip()
    if claim_type in {
        "company_disclosed_product_kpi",
        "company_reported_product_fact",
        "product_kpi",
        "product_revenue",
        "product_sales",
        "reported_financial_fact",
        "company_reported_financial_fact",
    }:
        return True
    metric_text = " ".join(_string_list(observation.get("metric_scope") or observation.get("metrics") or observation.get("metric"))).lower()
    return any(term in metric_text for term in ("product_revenue", "product_sales", "sell_through", "prescription_volume"))


def _row_has_product_kpi_exact_authority(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("source_family") or "").strip() == "company_product_evidence_graph"
        and str(row.get("promotion_status") or "").strip() == "runtime_fact_allowed"
        and bool(row.get("exact_value_authority"))
        and not bool(row.get("context_only"))
    )


def _salvage_numeric_fidelity_violations(
    validation: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    known_evidence_refs: set[str],
) -> dict[str, Any] | None:
    memolet = dict(validation.get("memolet") or {})
    row_by_ref = _row_by_known_ref_from_request(request)
    if not row_by_ref:
        return None
    observations = [dict(item) for item in memolet.get("observations") or [] if isinstance(item, Mapping)]
    kept: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for observation in observations:
        refs = _string_list(observation.get("evidence_refs") or observation.get("refs"))
        if not refs or sorted(set(refs) - known_evidence_refs):
            kept.append(observation)
            continue
        source_text = " ".join(_row_numeric_scope_text(row_by_ref.get(ref) or {}) for ref in refs)
        if not source_text.strip():
            kept.append(observation)
            continue
        unknown = sorted(_unknown_numeric_tokens(str(observation.get("claim") or ""), source_text))
        hard_unknown = [token for token in unknown if _is_material_numeric_token(token)]
        if not hard_unknown:
            kept.append(observation)
            continue
        removed.append(
            {
                "claim": _truncate(str(observation.get("claim") or "Unsupported numeric specialist observation."), 260),
                "reason": "demoted_numeric_claim_without_cited_row_support",
                "evidence_refs": refs,
                "numeric_tokens": hard_unknown[:8],
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
    metadata["salvage_policy"] = "demote_numeric_claim_without_cited_row_support_v0_1"
    metadata["salvaged_observation_count"] = int(metadata.get("salvaged_observation_count") or 0) + len(removed)
    repaired["metadata"] = metadata
    salvaged = validate_specialist_memolet(repaired, known_evidence_refs=known_evidence_refs)
    if salvaged.get("status") != "pass":
        return None
    salvaged["warnings"] = [
        *list(validation.get("warnings") or []),
        *list(salvaged.get("warnings") or []),
        {
            "type": "numeric_observation_demoted",
            "removed_count": len(removed),
            "policy": "supported_numeric_claims_must_match_cited_bounded_rows",
        },
    ]
    return salvaged


def _row_numeric_scope_text(row: Mapping[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in (
            "value",
            "numeric_value",
            "display_value",
            "unit",
            "metric",
            "metric_name",
            "metric_family",
            "summary",
            "text",
            "snippet",
            "as_of_date",
            "period_role",
            "period",
        )
    )


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
    validation = result.get("validation") if isinstance(result.get("validation"), Mapping) else {}
    rejected = result.get("rejected_memolet") if isinstance(result.get("rejected_memolet"), Mapping) else {}
    return {
        "agent_id": result.get("agent_id"),
        "status": result.get("status"),
        "failure_reason": str(result.get("failure_reason") or "")[:500],
        "validation_status": str(validation.get("status") or ""),
        "validation_error_types": [
            str(row.get("type") or "")
            for row in validation.get("errors") or []
            if isinstance(row, Mapping) and str(row.get("type") or "").strip()
        ][:12],
        "validation_warning_types": [
            str(row.get("type") or "")
            for row in validation.get("warnings") or []
            if isinstance(row, Mapping) and str(row.get("type") or "").strip()
        ][:12],
        "rejected_memolet_observation_count": len(rejected.get("observations") or []),
        "rejected_memolet_judgment_candidate_count": len(rejected.get("judgment_candidates") or []),
        "rejected_memolet_unsupported_claim_count": len(rejected.get("unsupported_claims") or []),
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
    agent_data_view_ref = request.get("agent_data_view_ref") if isinstance(request.get("agent_data_view_ref"), Mapping) else {}
    relationship_summary = request.get("relationship_summary") if isinstance(request.get("relationship_summary"), Mapping) else {}
    source_family_bundle = request.get("source_family_bundle") if isinstance(request.get("source_family_bundle"), Mapping) else {}
    source_layer_distribution = (
        request.get("source_layer_distribution")
        if isinstance(request.get("source_layer_distribution"), Mapping)
        else {}
    )
    rows = [dict(row) for row in request.get("bounded_evidence_rows") or [] if isinstance(row, Mapping)]
    return {
        "task_card_schema_version": str(task_card.get("schema_version") or ""),
        "assigned_memo_slot": str(task_card.get("assigned_memo_slot") or ""),
        "task_relevant_requirement_count": int(task_card.get("relevant_requirement_count") or 0),
        "required_claim_slot_count": len(request.get("required_claim_slots") or []),
        "counterclaim_slot_count": len(request.get("counterclaim_slots") or []),
        "available_source_families": _string_list(task_card.get("available_source_families"))[:8],
        "shared_context_digest": str(shared_context.get("context_digest") or ""),
        "agent_data_view_digest": str(agent_data_view_ref.get("context_digest") or ""),
        "agent_data_view_schema_version": str(agent_data_view_ref.get("schema_version") or ""),
        "prompt_bounded_evidence_row_count": len(request.get("bounded_evidence_rows") or []),
        "prompt_relationship_summary_row_count": len(relationship_summary.get("relationships") or []),
        "prompt_row_distribution": request.get("prompt_row_distribution") or _prompt_row_distribution(rows),
        "input_pack_fingerprint": _request_input_pack_fingerprint(request),
        "source_layer_distribution": _compact_source_layer_distribution_for_route(source_layer_distribution),
        "selected_source_families": _string_list(source_family_bundle.get("selected_source_families"))[:8],
        "semantic_supplement_row_count": int(source_family_bundle.get("semantic_supplement_row_count") or 0),
        "input_coverage_summary": request.get("input_coverage_summary") or {},
    }


def _specialist_fanout_barrier(
    route_results: Any,
    outputs: Any,
    *,
    execution_mode: str,
    shared_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    routes = [dict(item) for item in route_results or [] if isinstance(item, Mapping)]
    output_rows = [dict(item) for item in outputs or [] if isinstance(item, Mapping)]
    context = dict(shared_context or {})
    source_layer_distribution = (
        context.get("role_source_layer_distribution")
        if isinstance(context.get("role_source_layer_distribution"), Mapping)
        else {}
    )
    failed = [
        row
        for row in routes
        if str(row.get("status") or "") not in {"pass", "run", "stubbed", "skipped"}
    ]
    supporting_without_match = [
        str(row.get("agent_id") or "")
        for row in routes
        if str(row.get("agent_id") or "")
        and str(row.get("status") or "").strip().lower() != "skipped"
        and str(row.get("activation_decision") or "").strip().lower() != "skipped"
        and str(row.get("priority") or "").strip().lower() in {"supporting", "conditional", "low"}
        and int(row.get("matched_requirement_count") or 0) == 0
        and not bool(row.get("explicit_intent"))
    ]
    return {
        "schema_version": SPECIALIST_FANOUT_BARRIER_SCHEMA_VERSION,
        "barrier_id": "specialist_fanout_barrier",
        "execution_mode": execution_mode,
        "deterministic_merge_policy": "active_specialist_order",
        "specialist_count": len(output_rows),
        "route_result_count": len(routes),
        "failed_route_count": len(failed),
        "failed_agents": [str(row.get("agent_id") or "") for row in failed if str(row.get("agent_id") or "")],
        "supporting_run_without_required_item_match_count": len(supporting_without_match),
        "supporting_run_without_required_item_match_agents": supporting_without_match[:8],
        "source_layer_distribution": _compact_fanout_source_layer_distribution(source_layer_distribution),
        "output_schema": {
            "specialist_outputs": "append_only_claim_card_memolets",
            "specialist_route_results": "append_only_route_summaries",
        },
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
        "activation_decision": decision.get("decision") or "skipped",
        "activation_reason": str(decision.get("reason") or "")[:500],
        "matched_requirement_count": int(decision.get("matched_requirement_count") or 0),
        "explicit_intent": bool(decision.get("explicit_intent")),
        "signal_count": int(decision.get("signal_count") or 0),
        "task_card_schema_version": "",
        "assigned_memo_slot": "",
        "task_relevant_requirement_count": 0,
        "required_claim_slot_count": 0,
        "counterclaim_slot_count": 0,
        "available_source_families": [],
        "shared_context_digest": "",
        "agent_data_view_digest": "",
        "agent_data_view_schema_version": "",
        "prompt_bounded_evidence_row_count": 0,
        "prompt_relationship_summary_row_count": 0,
        "prompt_row_distribution": _prompt_row_distribution([]),
        "input_pack_fingerprint": _empty_input_pack_fingerprint(str(decision.get("agent_id") or "")),
        "source_layer_distribution": {},
        "input_coverage_summary": {},
    }


def _request_input_pack_fingerprint(request: Mapping[str, Any]) -> dict[str, Any]:
    component_keys = (
        "shared_context",
        "role_context",
        "assigned_task_card",
        "required_claim_slots",
        "counterclaim_slots",
        "bounded_evidence_rows",
        "source_layer_distribution",
        "source_family_bundle",
        "relationship_summary",
        "product_spec_pack",
        "capital_macro_pack",
        "fundamental_statement_pack",
        "fundamental_peer_statement_panel",
        "input_coverage_summary",
    )
    component_summaries: dict[str, dict[str, Any]] = {}
    component_digests: dict[str, str] = {}
    approx_chars = 0
    for key in component_keys:
        value = request.get(key)
        if _prompt_value_empty(value):
            component_summaries[key] = _empty_component_fingerprint()
            continue
        refs = sorted(_nested_prompt_evidence_refs(value))
        digest = _payload_digest({"component": key, "payload": value})
        chars = len(_json_for_prompt(value))
        approx_chars += chars
        component_digests[key] = digest
        component_summaries[key] = {
            "digest": digest,
            "item_count": _component_item_count(value),
            "evidence_ref_count": len(refs),
            "evidence_refs_sample": refs[:24],
            "approx_chars": chars,
        }
    known_refs = sorted(_known_evidence_refs_from_request(request))
    visible_refs = known_refs[:256]
    return {
        "schema_version": "sec_agent_specialist_input_pack_fingerprint_v0_1",
        "agent_id": str(request.get("agent_id") or ""),
        "digest": _payload_digest(
            {
                "agent_id": str(request.get("agent_id") or ""),
                "component_digests": component_digests,
                "known_evidence_refs": visible_refs,
            }
        ),
        "known_evidence_ref_count": len(known_refs),
        "known_evidence_refs": visible_refs,
        "known_evidence_refs_truncated": len(known_refs) > len(visible_refs),
        "component_summaries": component_summaries,
        "approx_prompt_payload_chars": approx_chars,
        "policy": "fingerprint_only_no_prompt_text_persisted_v0_1",
    }


def _empty_input_pack_fingerprint(agent_id: str = "") -> dict[str, Any]:
    return {
        "schema_version": "sec_agent_specialist_input_pack_fingerprint_v0_1",
        "agent_id": agent_id,
        "digest": "",
        "known_evidence_ref_count": 0,
        "known_evidence_refs": [],
        "known_evidence_refs_truncated": False,
        "component_summaries": {},
        "approx_prompt_payload_chars": 0,
        "policy": "fingerprint_only_no_prompt_text_persisted_v0_1",
    }


def _empty_component_fingerprint() -> dict[str, Any]:
    return {
        "digest": "",
        "item_count": 0,
        "evidence_ref_count": 0,
        "evidence_refs_sample": [],
        "approx_chars": 0,
    }


def _component_item_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if not isinstance(value, Mapping):
        return int(not _prompt_value_empty(value))
    count = 0
    for item in value.values():
        if isinstance(item, list):
            count += len(item)
        elif isinstance(item, Mapping):
            count += _component_item_count(item)
    return count or int(bool(value))


def _nested_prompt_evidence_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, Mapping):
        for key in (
            "evidence_refs",
            "refs",
            "supporting_evidence_ids",
            "known_evidence_refs",
            "evidence_ref",
            "evidence_id",
            "ref_id",
            "id",
            "metric_id",
            "source_id",
            "source_fact_id",
            "line_item_id",
            "change_id",
            "comparison_id",
            "raw_record_ref",
        ):
            refs.update(_string_list(value.get(key)))
        for nested in value.values():
            if isinstance(nested, (Mapping, list)):
                refs.update(_nested_prompt_evidence_refs(nested))
    elif isinstance(value, list):
        for item in value:
            refs.update(_nested_prompt_evidence_refs(item))
    return {ref for ref in refs if ref}


def _compact_source_layer_distribution_for_route(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        return {}
    return {
        "schema_version": value.get("schema_version") or "",
        "role": value.get("role") or "",
        "coverage_status": value.get("coverage_status") or "",
        "candidate_count": int(value.get("candidate_count") or 0),
        "selected_count": int(value.get("selected_count") or 0),
        "repairable_candidate_count": int(value.get("repairable_candidate_count") or 0),
        "not_registered_count": int(value.get("not_registered_count") or 0),
        "required_layers": list(value.get("required_layers") or []),
        "selected_by_layer": dict(value.get("selected_by_layer") or {}),
        "selected_by_evidence_graph_status": dict(value.get("selected_by_evidence_graph_status") or {}),
        "missing_required_layers": list(value.get("missing_required_layers") or []),
        "selected_missing_required_layers": list(value.get("selected_missing_required_layers") or []),
        "exact_authority_violation_sources": list(value.get("exact_authority_violation_sources") or []),
        "selected_sources": [
            {
                "source_id": str(row.get("source_id") or ""),
                "layer_id": str(row.get("layer_id") or ""),
                "evidence_graph_status": str(row.get("evidence_graph_status") or ""),
                "claim_scope": str(row.get("claim_scope") or ""),
                "source_entity_role": str(row.get("source_entity_role") or ""),
                "issuer_binding_status": str(row.get("issuer_binding_status") or ""),
                "product_binding_status": str(row.get("product_binding_status") or ""),
                "counterparty_binding_status": str(row.get("counterparty_binding_status") or ""),
            }
            for row in value.get("selected_sources") or []
            if isinstance(row, Mapping)
        ][:8],
    }


def _compact_fanout_source_layer_distribution(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        return {}
    roles = value.get("roles") if isinstance(value.get("roles"), Mapping) else {}
    return {
        "schema_version": value.get("schema_version") or "",
        "status": value.get("status") or "",
        "role_count": int(value.get("role_count") or len(roles)),
        "failed_roles": list(value.get("failed_roles") or []),
        "gap_roles": list(value.get("gap_roles") or []),
        "roles": {
            str(role): {
                "coverage_status": row.get("coverage_status") or "",
                "candidate_count": int(row.get("candidate_count") or 0),
                "selected_count": int(row.get("selected_count") or 0),
                "repairable_candidate_count": int(row.get("repairable_candidate_count") or 0),
                "not_registered_count": int(row.get("not_registered_count") or 0),
                "selected_by_layer": dict(row.get("selected_by_layer") or {}),
                "selected_missing_required_layers": list(row.get("selected_missing_required_layers") or []),
                "exact_authority_violation_sources": list(row.get("exact_authority_violation_sources") or []),
            }
            for role, row in roles.items()
            if isinstance(row, Mapping)
        },
        "policy": value.get("policy") or "",
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


def _bool_env(value: str | None) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


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
        if agent_id in {"fundamental_analyst", "product_technology_analyst"}:
            default = 16
        elif agent_id == "industry_supply_chain_analyst":
            default = 12
        else:
            default = 8
        value = _int_env(os.environ.get("SPECIALIST_DEEP_RESEARCH_INPUT_MAX_ROWS") or generic, default=default)
    elif mode == "standard_memo" and normalized_priority == "supporting":
        value = _int_env(
            os.environ.get("SPECIALIST_STANDARD_MEMO_SUPPORTING_INPUT_MAX_ROWS")
            or os.environ.get("SPECIALIST_SUPPORTING_INPUT_MAX_ROWS")
            or generic,
            default=8,
        )
    elif mode == "standard_memo":
        default = 16 if agent_id in {"fundamental_analyst", "product_technology_analyst"} else 12
        value = _int_env(os.environ.get("SPECIALIST_STANDARD_MEMO_INPUT_MAX_ROWS") or generic, default=default)
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
        if agent_id == "product_technology_analyst":
            return "produce 2-3 product ClaimCards when exact product KPI or proxy context supports them; expose commercial tracker gaps instead of filling them"
        if agent_id == "fundamental_analyst":
            return "produce 2-3 supported fundamental ClaimCards when evidence supports them; prioritize investment implications over row summaries; keep unsupported_claims/conflicts to the top 2 each"
        return "produce 2-3 supported observations when evidence supports them; keep unsupported_claims/conflicts to the top 2 each"
    if mode == "standard_memo":
        if agent_id == "risk_counterevidence_analyst":
            return "produce 2-3 supported risk ClaimCards when evidence supports them; use at most 2 unsupported_claims and at most 2 conflicts"
        if agent_id == "product_technology_analyst":
            return "produce 1-3 product ClaimCards when evidence supports them; expose at most 2 commercial tracker gaps"
        return "produce 3-6 supported observations when evidence supports them; keep unsupported_claims/conflicts to the top 3 each"
    return "at most 3 observations, 3 unsupported_claims, and 3 conflicts"


def _specialist_output_contract(
    agent_id: str,
    execution_mode: str,
    *,
    method_runtime_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    mode = str(execution_mode or "").strip()
    role_rubric = specialist_runtime_rubric(method_runtime_pack or {}, agent_id)
    judgment_candidate_contract = (
        method_runtime_pack.get("judgment_candidate_contract")
        if isinstance(method_runtime_pack, Mapping) and isinstance(method_runtime_pack.get("judgment_candidate_contract"), Mapping)
        else {
            "required_fields": [
                "judgment",
                "required_item_answered",
                "supported_by_evidence_refs",
                "graph_edge_refs",
                "product_or_financial_bridge",
                "business_mechanism",
                "counter_read",
                "confidence",
                "cannot_infer",
                "what_would_change_view",
            ],
            "policy": "specialists produce writer-ready judgment candidates, not row summaries",
        }
    )
    if agent_id == "risk_counterevidence_analyst":
        return {
            "policy": "risk_compact_schema_v0_3",
            "supported_observation_target": "2-3" if mode in {"standard_memo", "deep_research"} else "0-2",
            "unsupported_claim_cap": 2,
            "conflict_cap": 2,
            "required_outputs": ["judgment_candidates", "bounded risk/counterevidence ClaimCards"],
            "judgment_candidate_contract": judgment_candidate_contract,
            "specialist_runtime_rubric": role_rubric,
            "memo_ready_requirement": "each risk must be a downside driver, evidence weakness, or confirmation need",
        }
    if agent_id == "product_technology_analyst":
        return {
            "policy": "product_technology_product_spec_pack_claim_cards_v0_2",
            "supported_observation_target": "2-4" if mode == "deep_research" else "1-3",
            "unsupported_claim_cap": 2,
            "conflict_cap": 1,
            "required_structured_inputs": ["ProductSpecPack", "ProductIntelligenceGraph company pack"],
            "required_outputs": ["judgment_candidates", "ProductSpecPack", "bounded product/technology ClaimCards"],
            "judgment_candidate_contract": judgment_candidate_contract,
            "specialist_runtime_rubric": role_rubric,
            "product_spec_pack_policy": "ChannelOffer, FieldInquiryNote, CustomerDeploymentSignal, and ProductSupplyChainSignal are context or lead objects only; they cannot support sales, sell-through, market share, company ASP, channel inventory, order value, backlog, shipment, or allocation claims",
            "memo_ready_requirement": (
                "product KPI facts require company_product_evidence_graph runtime_fact_allowed exact authority; public proxy rows "
                "cannot become exact KPI, but thesis_driver_authority signal rows must be converted into bounded product/technology "
                "or demand-proxy insight rather than generic gap prose"
            ),
        }
    if agent_id == "fundamental_analyst" and mode == "deep_research":
        return {
            "policy": "fundamental_statement_pack_claim_cards_v0_4",
            "supported_observation_target": "3-5",
            "unsupported_claim_cap": 1,
            "conflict_cap": 2,
            "required_structured_inputs": ["FundamentalStatementPack"],
            "required_outputs": ["judgment_candidates", "bounded fundamental ClaimCards"],
            "judgment_candidate_contract": judgment_candidate_contract,
            "specialist_runtime_rubric": role_rubric,
            "memo_ready_requirement": "connect three statements, peer context, industry priority metrics, and product/capital bridges when supported",
        }
    return {
        "policy": "role_specific_claim_cards_v0_3",
        "supported_observation_target": "3-5" if mode == "deep_research" else "0-3" if mode not in {"standard_memo"} else "3-6",
        "unsupported_claim_cap": 1,
        "conflict_cap": 2,
        "required_outputs": ["judgment_candidates", "bounded role-specific ClaimCards"],
        "judgment_candidate_contract": judgment_candidate_contract,
        "specialist_runtime_rubric": role_rubric,
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
        default = 160 if mode == "deep_research" else 240
        if agent_id == "fundamental_analyst":
            default = 150 if mode == "deep_research" else 220
        return _int_env(os.environ.get("SPECIALIST_SEC_SUMMARY_CHARS"), default=default)
    if family == "market_snapshot":
        return _int_env(os.environ.get("SPECIALIST_MARKET_SUMMARY_CHARS"), default=140)
    if family == "industry_snapshot":
        return _int_env(os.environ.get("SPECIALIST_INDUSTRY_SUMMARY_CHARS"), default=160)
    if family == "relationship_graph":
        return _relationship_summary_chars(execution_mode)
    if family in {"company_product_evidence_graph", "public_source_context", "live_public_web_context"}:
        return _int_env(os.environ.get("SPECIALIST_PRODUCT_SUMMARY_CHARS"), default=140 if mode == "deep_research" else 220)
    return _int_env(os.environ.get("SPECIALIST_OTHER_SUMMARY_CHARS"), default=150 if mode == "deep_research" else 220)


def _relationship_summary_chars(execution_mode: str = "") -> int:
    generic = os.environ.get("SPECIALIST_INPUT_SUMMARY_CHARS")
    if generic not in {None, ""}:
        return _int_env(generic, default=520)
    default = 180 if str(execution_mode or "").strip() == "deep_research" else 260
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
        if _suppress_source_gap_for_specialist(
            agent_id=agent_id,
            gap=gap,
            ticker=ticker,
            primary_by_ticker=primary_by_ticker,
            rows=rows,
        ):
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
        "non_financial_signal_authority": {
            "thesis_driver_authority_row_count": sum(1 for row in rows if bool(row.get("thesis_driver_authority"))),
            "by_signal_authority_type": _count_by_key(rows, "signal_authority_type"),
            "by_signal_promotion_level": _count_by_key(rows, "signal_promotion_level"),
            "policy": "non-financial signal authority supports bounded thesis drivers but not exact financial/product KPI claims",
        },
        "coverage_policy": "comparative_focus_tickers_must_have_visible_primary_rows_or_ticker_source_gap",
    }


def _suppress_source_gap_for_specialist(
    *,
    agent_id: str,
    gap: Mapping[str, Any],
    ticker: str,
    primary_by_ticker: Mapping[str, int],
    rows: list[Mapping[str, Any]],
) -> bool:
    reason = str(gap.get("reason_code") or gap.get("quality_gap_type") or gap.get("reason") or "")
    gap_source_family = str(gap.get("source_family") or "").strip()
    sec_source_families = {"", "primary_sec_filing", "company_authored_unaudited_sec_filing"}
    if reason == "not_in_manifest_for_mcp_route_scope" and int(primary_by_ticker.get(ticker, 0) or 0) > 0:
        return True
    if gap_source_family in sec_source_families and agent_id not in {
        "fundamental_analyst",
        "risk_counterevidence_analyst",
    }:
        role_row_families = {str(row.get("source_family") or "").strip() for row in rows}
        if not (role_row_families & sec_source_families):
            return True
    return False


def _prompt_row_distribution(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "sec_agent_prompt_row_distribution_v0.1",
        "row_count": len(rows),
        "by_ticker": _count_by_key(rows, "ticker"),
        "by_source_family": _count_by_key(rows, "source_family"),
        "by_ticker_source_family": _count_by_composite(rows, ("ticker", "source_family")),
        "by_form_type": _count_by_key(rows, "form_type"),
        "by_metric": _count_by_key(rows, "metric"),
        "by_source_entity_role": _count_by_key(rows, "source_entity_role"),
        "by_signal_authority_type": _count_by_key(rows, "signal_authority_type"),
        "by_signal_promotion_level": _count_by_key(rows, "signal_promotion_level"),
        "by_issuer_binding_status": _count_by_key(rows, "issuer_binding_status"),
        "by_product_binding_status": _count_by_key(rows, "product_binding_status"),
        "by_counterparty_binding_status": _count_by_key(rows, "counterparty_binding_status"),
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


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
