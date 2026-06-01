from __future__ import annotations

import os
from typing import Any, Callable, Mapping

from sec_agent.agent_registry import agent_registry_by_id
from sec_agent.mcp_tool_registry import invoke_mcp_tool
from sec_agent.multi_agent_contracts import evidence_requirements_from_universe_relationship_plan
from sec_agent.retrieval_plan import EVIDENCE_REQUIREMENT_SCHEMA_VERSION, build_evidence_requirement_plan, build_retrieval_plan
from sec_agent.tool_call_ledger import ToolCallLedger


RUNTIME_SCHEMA_VERSION = "sec_agent_multi_agent_runtime_v0.1"
AGENT_DATA_VIEW_SCHEMA_VERSION = "sec_agent_agent_data_view_v0.2"
SPECIALIST_TASK_CARD_SCHEMA_VERSION = "sec_agent_specialist_task_card_v0.1"
SPECIALIST_CLAIM_SLOT_SCHEMA_VERSION = "sec_agent_specialist_claim_slot_v0.1"
AGENT_DATA_VIEW_MAX_ROWS = 16
AGENT_DATA_VIEW_STANDARD_MEMO_MAX_ROWS = 24
AGENT_DATA_VIEW_DEEP_RESEARCH_MAX_ROWS = 32
AGENT_DATA_VIEW_SUPPORTING_DEEP_RESEARCH_MAX_ROWS = 20
AGENT_DATA_VIEW_SUPPORTING_STANDARD_MEMO_MAX_ROWS = 16
AGENT_DATA_VIEW_CONDITIONAL_MAX_ROWS = 12
AGENT_DATA_VIEW_LOW_MAX_ROWS = 8
INDUSTRY_RELATIONSHIP_MIN_ROWS = 3
INDUSTRY_RELATIONSHIP_STANDARD_MIN_ROWS = 4
INDUSTRY_RELATIONSHIP_DEEP_MIN_ROWS = 6
RELATIONSHIP_SUMMARY_MAX_ROWS = 16
RELATIONSHIP_SUMMARY_DEEP_RESEARCH_MAX_ROWS = 24
SEC_SEARCH_RUNTIME_POLICY_SCHEMA_VERSION = "sec_agent_sec_search_runtime_policy_v0.1"

ROUTE_OPERATOR_TOOL: dict[str, tuple[str, str]] = {
    "ledger_first": ("sec_operator", "sec_query_exact_value_ledger"),
    "filing_text": ("sec_operator", "sec_search_filings"),
    "risk_text": ("sec_operator", "sec_search_filings"),
    "8k_commentary": ("eight_k_operator", "sec_search_filings"),
    "market_snapshot": ("market_operator", "market_get_snapshot"),
    "industry_snapshot": ("industry_operator", "industry_get_snapshot"),
    "relationship_graph": ("universe_relationship", "relationship_graph_lookup"),
    "run_artifact": ("coverage_reflection", "run_inspect_artifacts"),
}

ROUTE_SOURCE_FAMILY: dict[str, str] = {
    "ledger_first": "primary_sec_filing",
    "filing_text": "primary_sec_filing",
    "risk_text": "primary_sec_filing",
    "8k_commentary": "company_authored_unaudited_sec_filing",
    "market_snapshot": "market_snapshot",
    "industry_snapshot": "industry_snapshot",
    "relationship_graph": "relationship_graph",
    "run_artifact": "run_artifact",
}

SEC_SEARCH_SOURCE_TIERS = {"primary_sec_filing", "company_authored_unaudited_sec_filing"}
SPECIALIST_EXECUTION_ORDER = (
    "fundamental_analyst",
    "industry_supply_chain_analyst",
    "market_valuation_analyst",
    "risk_counterevidence_analyst",
)


ToolExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]


def build_multi_agent_evidence_requirement_plan(
    query_contract: Mapping[str, Any],
    *,
    activation_plan: Mapping[str, Any] | None = None,
    case: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize business evidence needs and attach multi-agent ownership metadata."""
    plan = build_evidence_requirement_plan(dict(query_contract or {}), case=dict(case or {}))
    enriched_requirements = [_enrich_evidence_requirement(req) for req in plan.get("requirements") or [] if isinstance(req, Mapping)]
    enriched = {
        **plan,
        "requirements": enriched_requirements,
        "multi_agent_contract": {
            "schema_version": "sec_agent_multi_agent_evidence_requirement_contract_v0.1",
            "planner_boundary": "business_need_only_no_physical_paths",
            "route_compiler": "deterministic_retrieval_plan_compiler",
            "operator_owner_source": "route_intent_mapping",
        },
    }
    validation = validate_multi_agent_evidence_requirement_plan(enriched, activation_plan=activation_plan)
    enriched["multi_agent_evidence_requirement_validation"] = validation
    return enriched


def validate_multi_agent_evidence_requirement_plan(
    plan: Mapping[str, Any],
    *,
    activation_plan: Mapping[str, Any] | None = None,
    registry: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    active_registry = dict(registry or agent_registry_by_id())
    activation = dict(activation_plan or {})
    allowed_sources = set(_string_list(activation.get("allowed_source_families")))
    requirements = [dict(item) for item in plan.get("requirements") or [] if isinstance(item, Mapping)]

    if str(plan.get("schema_version") or "") != EVIDENCE_REQUIREMENT_SCHEMA_VERSION:
        warnings.append({"type": "schema_version_normalized", "value": str(plan.get("schema_version") or "")})
    if not requirements:
        errors.append({"type": "missing_evidence_requirements"})

    for index, requirement in enumerate(requirements, start=1):
        requirement_id = str(requirement.get("requirement_id") or f"req_{index}")
        routes = _string_list(requirement.get("evidence_routes") or requirement.get("retrieval_routes"))
        expected_sources: set[str] = set()
        expected_owners: set[str] = set()
        for route in routes:
            source_family = ROUTE_SOURCE_FAMILY.get(route)
            owner = ROUTE_OPERATOR_TOOL.get(route, ("", ""))[0]
            if not source_family or not owner:
                errors.append({"type": "unknown_evidence_route", "requirement_id": requirement_id, "route": route})
                continue
            expected_sources.add(source_family)
            expected_owners.add(owner)
            entry = dict(active_registry.get(owner) or {})
            if not entry:
                errors.append({"type": "operator_owner_missing_from_registry", "requirement_id": requirement_id, "operator_owner": owner})
                continue
            owner_sources = set(_string_list(entry.get("source_families")))
            if source_family not in owner_sources:
                errors.append(
                    {
                        "type": "operator_source_family_mismatch",
                        "requirement_id": requirement_id,
                        "operator_owner": owner,
                        "source_family": source_family,
                    }
                )
        explicit_sources = set(
            _string_list(
                requirement.get("planner_source_families")
                or requirement.get("source_families")
                or requirement.get("source_family")
            )
        )
        explicit_owners = set(
            _string_list(
                requirement.get("planner_operator_owners")
                or requirement.get("operator_owners")
                or requirement.get("operator_owner")
            )
        )
        if explicit_sources and expected_sources and not explicit_sources.issubset(expected_sources):
            errors.append(
                {
                    "type": "source_family_mismatch",
                    "requirement_id": requirement_id,
                    "source_families": sorted(explicit_sources),
                    "expected_source_families": sorted(expected_sources),
                }
            )
        if explicit_owners and expected_owners and not explicit_owners.issubset(expected_owners):
            errors.append(
                {
                    "type": "operator_owner_mismatch",
                    "requirement_id": requirement_id,
                    "operator_owners": sorted(explicit_owners),
                    "expected_operator_owners": sorted(expected_owners),
                }
            )
        if allowed_sources:
            disallowed = sorted(expected_sources - allowed_sources)
            if disallowed:
                errors.append(
                    {
                        "type": "source_family_not_allowed_for_activation",
                        "requirement_id": requirement_id,
                        "source_families": disallowed,
                        "allowed_source_families": sorted(allowed_sources),
                    }
                )

    return {
        "schema_version": "sec_agent_multi_agent_evidence_requirement_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def compile_multi_agent_retrieval_plan(
    evidence_requirement_plan: Mapping[str, Any],
    *,
    query_contract: Mapping[str, Any] | None = None,
    case: Mapping[str, Any] | None = None,
    activation_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    contract = dict(query_contract or {})
    if "evidence_requirements" not in contract and evidence_requirement_plan.get("requirements"):
        contract["evidence_requirements"] = list(evidence_requirement_plan.get("requirements") or [])
    plan = build_retrieval_plan(contract, case=dict(case or {}))
    return _cap_retrieval_plan_routes(plan, activation_plan or {})


def merge_universe_relationship_evidence_requirements(
    evidence_requirement_plan: Mapping[str, Any],
    universe_relationship_plan: Mapping[str, Any] | None = None,
    *,
    activation_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    base = dict(evidence_requirement_plan or {})
    relationship_plan = dict(universe_relationship_plan or {})
    relationship_requirements = evidence_requirements_from_universe_relationship_plan(relationship_plan)
    if not relationship_requirements:
        return base
    scope = base.get("scope") if isinstance(base.get("scope"), Mapping) else {}
    years = _int_list(scope.get("years"))
    filing_types = _string_list(scope.get("filing_types"))
    source_tiers = _string_list(scope.get("source_tiers"))
    existing_ids = {str(req.get("requirement_id") or "") for req in base.get("requirements") or [] if isinstance(req, Mapping)}
    compiled_relationship_requirements = []
    max_added_routes = _relationship_route_budget(base, activation_plan or {})
    added_route_count = 0
    for req in relationship_requirements:
        compiled = _compile_relationship_requirement_for_retrieval(
            req,
            years=years,
            filing_types=filing_types,
            source_tiers=source_tiers,
        )
        if str(compiled.get("requirement_id") or "") in existing_ids:
            continue
        routes = _string_list(compiled.get("evidence_routes"))
        if max_added_routes >= 0 and added_route_count + len(routes) > max_added_routes:
            routes = routes[: max(0, max_added_routes - added_route_count)]
            if not routes:
                break
            pruned = {**compiled, "evidence_routes": routes}
            for key in ("planner_source_families", "planner_operator_owners", "source_families", "operator_owners", "route_intents", "claim_families"):
                pruned.pop(key, None)
            compiled = _enrich_evidence_requirement(pruned)
        compiled_relationship_requirements.append(compiled)
        added_route_count += len(_string_list(compiled.get("evidence_routes")))
    merged = {
        **base,
        "source": str(base.get("source") or "multi_agent_evidence_requirements") + "+universe_relationship",
        "requirements": [*(base.get("requirements") or []), *compiled_relationship_requirements],
        "relationship_evidence_requirement_policy": {
            "planner_boundary": "universe_business_need_only_routes_compiled_deterministically",
            "relationship_source_family": "relationship_graph",
            "relationship_claim_scope": "hypothesis_not_financial_fact",
            "route_budget_policy": "relationship_requirements_capped_by_activation_tool_budget",
            "added_route_count": added_route_count,
            "max_added_routes": max_added_routes,
        },
    }
    merged["summary"] = {
        **dict(base.get("summary") or {}),
        "requirement_count": len(merged["requirements"]),
        "relationship_requirement_count": len(compiled_relationship_requirements),
    }
    merged["multi_agent_evidence_requirement_validation"] = validate_multi_agent_evidence_requirement_plan(
        merged,
        activation_plan=activation_plan,
    )
    return merged


def _relationship_route_budget(
    evidence_requirement_plan: Mapping[str, Any],
    activation_plan: Mapping[str, Any],
) -> int:
    max_total = _bounded_positive_int(activation_plan.get("max_tool_calls_total"), default=-1)
    if max_total < 0:
        return -1
    base_route_count = 0
    for req in evidence_requirement_plan.get("requirements") or []:
        if not isinstance(req, Mapping):
            continue
        base_route_count += len([route for route in _string_list(req.get("evidence_routes") or req.get("retrieval_routes")) if route != "relationship_graph"])
    relationship_lookup_reserve = 1 if "universe_relationship" in set(_string_list(activation_plan.get("activate_agents"))) else 0
    return max(0, max_total - base_route_count - relationship_lookup_reserve)


def _cap_retrieval_plan_routes(plan: Mapping[str, Any], activation_plan: Mapping[str, Any]) -> dict[str, Any]:
    if not activation_plan:
        return dict(plan or {})
    capped = dict(plan or {})
    routes = [dict(route) for route in capped.get("routes") or [] if isinstance(route, Mapping)]
    max_total = _bounded_positive_int(activation_plan.get("max_tool_calls_total"), default=-1)
    registry = agent_registry_by_id()
    per_agent_limits = {
        agent_id: int(entry.get("max_tool_calls") or 0)
        for agent_id, entry in registry.items()
        if int(entry.get("max_tool_calls") or 0) > 0
    }
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    counts_by_agent: dict[str, int] = {}
    for route in routes:
        route_name = str(route.get("retrieval_route") or "")
        agent_id = ROUTE_OPERATOR_TOOL.get(route_name, ("", ""))[0]
        if max_total >= 0 and len(kept) >= max_total:
            dropped.append({"route_id": route.get("route_id") or "", "retrieval_route": route_name, "reason": "max_tool_calls_total"})
            continue
        agent_limit = per_agent_limits.get(agent_id, 0)
        if agent_limit and counts_by_agent.get(agent_id, 0) >= agent_limit:
            dropped.append(
                {
                    "route_id": route.get("route_id") or "",
                    "retrieval_route": route_name,
                    "agent_id": agent_id,
                    "reason": "max_tool_calls_per_agent",
                }
            )
            continue
        kept.append(route)
        if agent_id:
            counts_by_agent[agent_id] = counts_by_agent.get(agent_id, 0) + 1
    if len(kept) == len(routes):
        return capped
    capped["routes"] = kept
    capped["summary"] = {
        **dict(capped.get("summary") or {}),
        "route_count": len(kept),
        "route_budget_dropped_count": len(dropped),
    }
    capped["route_budget_pruning"] = {
        "policy": "compiled_routes_capped_by_agent_permission_matrix",
        "max_tool_calls_total": max_total,
        "per_agent_limits": per_agent_limits,
        "kept_route_count": len(kept),
        "dropped_route_count": len(dropped),
        "dropped_routes": dropped,
    }
    return capped


def second_pass_evidence_requirement_plan_from_reflection(
    reflection_report: Mapping[str, Any],
    base_evidence_requirement_plan: Mapping[str, Any] | None = None,
    *,
    activation_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert Reflection's business second-pass requests back into a compiler input."""
    report = normalize_reflection_report(reflection_report)
    base_plan = dict(base_evidence_requirement_plan or {})
    requirements = [
        _enrich_evidence_requirement(_second_pass_request_as_requirement(request, index))
        for index, request in enumerate(report.get("second_pass_requests") or [], start=1)
        if isinstance(request, Mapping)
    ]
    plan = {
        "schema_version": EVIDENCE_REQUIREMENT_SCHEMA_VERSION,
        "source": "reflection_second_pass_requests",
        "case_id": str(base_plan.get("case_id") or ""),
        "scope": dict(base_plan.get("scope") or {}),
        "requirements": requirements,
        "summary": {
            "requirement_count": len(requirements),
            "source_family_gaps": _dedupe(
                [
                    family
                    for requirement in requirements
                    for family in _string_list(requirement.get("source_family_gaps") or requirement.get("source_families"))
                ]
            ),
            "parent_requirement_ids": _dedupe([str(req.get("parent_requirement_id") or "") for req in requirements]),
        },
        "multi_agent_contract": {
            "schema_version": "sec_agent_multi_agent_evidence_requirement_contract_v0.1",
            "planner_boundary": "reflection_business_need_only_no_physical_paths",
            "route_compiler": "deterministic_retrieval_plan_compiler",
            "operator_owner_source": "route_intent_mapping",
        },
    }
    plan["multi_agent_evidence_requirement_validation"] = validate_multi_agent_evidence_requirement_plan(
        plan,
        activation_plan=activation_plan,
    )
    return plan


def compile_second_pass_retrieval_plan(
    reflection_report: Mapping[str, Any],
    base_evidence_requirement_plan: Mapping[str, Any] | None = None,
    *,
    query_contract: Mapping[str, Any] | None = None,
    case: Mapping[str, Any] | None = None,
    activation_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile Reflection second-pass requests through the deterministic retrieval compiler."""
    second_pass_plan = second_pass_evidence_requirement_plan_from_reflection(
        reflection_report,
        base_evidence_requirement_plan,
        activation_plan=activation_plan,
    )
    contract = _query_contract_with_plan_scope(query_contract or {}, base_evidence_requirement_plan or {})
    retrieval_plan = compile_multi_agent_retrieval_plan(second_pass_plan, query_contract=contract, case=case)
    retrieval_plan["second_pass_evidence_requirement_plan"] = second_pass_plan
    return retrieval_plan


def build_agent_data_view(agent_id: str, state: Mapping[str, Any]) -> dict[str, Any]:
    """Build the bounded role input allowed by the static agent registry."""
    registry = agent_registry_by_id()
    entry = dict(registry.get(str(agent_id or "")) or {})
    if not entry:
        return {
            "schema_version": AGENT_DATA_VIEW_SCHEMA_VERSION,
            "status": "fail",
            "agent_id": str(agent_id or ""),
            "errors": [{"type": "unknown_agent", "agent_id": str(agent_id or "")}],
        }

    allowed_views = _string_list(entry.get("allowed_data_views"))
    view: dict[str, Any] = {
        "schema_version": AGENT_DATA_VIEW_SCHEMA_VERSION,
        "status": "pass",
        "agent_id": entry["agent_id"],
        "allowed_data_views": allowed_views,
        "payload_policy": {
            "raw_evidence": "not_included",
            "private_paths": "stripped",
            "internal_reasoning": "not_included",
        },
        "summary": _state_summary_for_data_view(state),
        "input_budget": _data_view_input_budget(entry["agent_id"], state),
    }

    allowed = set(allowed_views)
    if "source_inventory" in allowed or "summary_only" in allowed:
        view["source_inventory"] = _sanitize_payload(state.get("project_inventory") or state.get("source_inventory") or {})
    if "artifact_ref" in allowed:
        view["artifact_refs"] = _artifact_ref_summary(state.get("artifact_refs") or {})
    if "bounded_rows" in allowed:
        view["bounded_evidence_rows"] = _bounded_rows_for_agent_data_view(entry["agent_id"], state)
    if "coverage_summary" in allowed:
        view["coverage_summary"] = _coverage_summary_view(state)
    if "tool_trace_summary" in allowed:
        view["tool_trace_summary"] = _tool_trace_summary_view(state)
    if "relationship_graph_summary" in allowed or "relationship_summary" in allowed:
        view["relationship_summary"] = _relationship_summary_view(state)
    if "verified_summary" in allowed:
        view["verified_summary"] = _verified_summary_view(state)
    if "database_query" in allowed:
        view["database_query_boundary"] = "available_only_inside_bounded_operator_tool"
    if entry["agent_id"] in SPECIALIST_EXECUTION_ORDER:
        task_card = _assigned_task_card_for_specialist(entry["agent_id"], state)
        view["assigned_task_card"] = task_card
        view["required_claim_slots"] = _required_claim_slots_for_specialist(
            entry["agent_id"],
            state,
            task_card=task_card,
        )
        view["counterclaim_slots"] = _counterclaim_slots_for_specialist(
            entry["agent_id"],
            state,
            task_card=task_card,
        )

    return _sanitize_payload(view)


def _assigned_task_card_for_specialist(agent_id: str, state: Mapping[str, Any]) -> dict[str, Any]:
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    requirements = _requirements_for_specialist(agent_id, state)
    compact_requirements = [_compact_task_card_requirement(item, index) for index, item in enumerate(requirements[:8], start=1)]
    execution_mode = _execution_mode_from_state(state)
    focus_tickers = _focus_tickers_from_state(state)
    search_scope_tickers = _search_scope_tickers_from_state(state, focus_tickers=focus_tickers)
    priority = str(dict(activation.get("agent_priorities") or {}).get(agent_id) or "primary")
    required_source_families = _specialist_required_source_families(agent_id)
    available_source_families = _available_source_families_for_specialist(agent_id, state)
    return {
        "schema_version": SPECIALIST_TASK_CARD_SCHEMA_VERSION,
        "agent_id": agent_id,
        "execution_mode": execution_mode,
        "priority": priority,
        "analyst_lens": _specialist_lens(agent_id),
        "assigned_memo_slot": _specialist_memo_slot(agent_id),
        "user_query": str(state.get("user_query") or query_contract.get("user_query") or "")[:500],
        "focus_tickers": focus_tickers,
        "search_scope_tickers": search_scope_tickers,
        "required_source_families": required_source_families,
        "available_source_families": available_source_families,
        "relevant_requirements": compact_requirements,
        "relevant_requirement_count": len(requirements),
        "task_policy": "role_specific_task_card_v0_1_use_slots_not_row_summaries",
        "failure_policy": "if_slot_not_supported_add_missing_confirmation_or_top_material_unsupported_claim_only",
    }


def _required_claim_slots_for_specialist(
    agent_id: str,
    state: Mapping[str, Any],
    *,
    task_card: Mapping[str, Any],
) -> list[dict[str, Any]]:
    mode = str(task_card.get("execution_mode") or _execution_mode_from_state(state))
    target = "2-4" if mode == "deep_research" else "1-3"
    if agent_id == "fundamental_analyst":
        return [
            _claim_slot(
                agent_id,
                slot_id="fundamentals_reported_fact",
                memo_slot="fundamentals",
                target_claim_count=target,
                claim_type_allowlist=["company_reported_financial_fact", "reported_financial_fact", "business_observation"],
                required_source_families=["primary_sec_filing", "company_authored_unaudited_sec_filing"],
                instruction="Select the most decision-useful filed metric or company-authored commentary and state the investment implication, preserving period role.",
            ),
            _claim_slot(
                agent_id,
                slot_id="fundamentals_quality_or_pressure",
                memo_slot="fundamentals",
                target_claim_count="0-2",
                claim_type_allowlist=["business_observation"],
                required_source_families=["primary_sec_filing", "company_authored_unaudited_sec_filing"],
                instruction="Explain whether the bounded facts imply growth quality, margin pressure, capital intensity, liquidity, or demand strength.",
            ),
        ]
    if agent_id == "industry_supply_chain_analyst":
        relationship_required = bool(_relationship_rows_from_state(state))
        slots = [
            _claim_slot(
                agent_id,
                slot_id="industry_transmission_mechanism",
                memo_slot="industry_relationship",
                target_claim_count=target,
                claim_type_allowlist=["industry_context_only", "relationship_hypothesis", "scope_hypothesis"],
                required_source_families=["industry_snapshot", "relationship_graph"],
                instruction="Convert bounded sector or relationship evidence into a transmission mechanism and the company metric that should confirm it.",
            )
        ]
        if relationship_required:
            slots.append(
                _claim_slot(
                    agent_id,
                    slot_id="relationship_graph_hypothesis",
                    memo_slot="industry_relationship",
                    target_claim_count="1-2",
                    claim_type_allowlist=["relationship_hypothesis", "scope_hypothesis"],
                    required_source_families=["relationship_graph"],
                    instruction="Use at least one relationship_graph ref as hypothesis/scope evidence only; do not treat it as confirmed revenue, customer, or supplier fact.",
                )
            )
        return slots
    if agent_id == "market_valuation_analyst":
        return [
            _claim_slot(
                agent_id,
                slot_id="market_reaction_or_valuation_context",
                memo_slot="market_valuation",
                target_claim_count=target,
                claim_type_allowlist=["market_context", "valuation_context", "market_or_valuation_context", "business_observation"],
                required_source_families=["market_snapshot"],
                instruction="State the timestamped market reaction, valuation context, or expectation mismatch without treating it as proof of fundamentals.",
            )
        ]
    if agent_id == "risk_counterevidence_analyst":
        return [
            _claim_slot(
                agent_id,
                slot_id="direct_risk_or_counterevidence",
                memo_slot="risk_counterevidence",
                target_claim_count="2-3" if mode in {"standard_memo", "deep_research"} else "0-2",
                claim_type_allowlist=["risk_or_counterevidence", "source_gap", "business_observation"],
                required_source_families=["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot", "industry_snapshot", "run_artifact"],
                instruction="Stress-test the strongest supported thesis components with bounded risks, gaps, or conflicts; do not make a generic risk list.",
            )
        ]
    return []


def _counterclaim_slots_for_specialist(
    agent_id: str,
    state: Mapping[str, Any],
    *,
    task_card: Mapping[str, Any],
) -> list[dict[str, Any]]:
    mode = str(task_card.get("execution_mode") or _execution_mode_from_state(state))
    common_cap = "0-1" if mode == "focused_answer" else "0-2"
    if agent_id == "risk_counterevidence_analyst":
        return [
            _claim_slot(
                agent_id,
                slot_id="unsupported_thesis_component",
                memo_slot="risk_counterevidence",
                target_claim_count=common_cap,
                claim_type_allowlist=["unsupported_claim", "source_gap"],
                required_source_families=["run_artifact", "primary_sec_filing", "company_authored_unaudited_sec_filing"],
                instruction="Name only the top material thesis component that bounded evidence fails to support.",
                slot_kind="counterclaim_or_gap",
            ),
            _claim_slot(
                agent_id,
                slot_id="direct_conflict",
                memo_slot="risk_counterevidence",
                target_claim_count=common_cap,
                claim_type_allowlist=["risk_or_counterevidence", "business_observation"],
                required_source_families=["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot", "industry_snapshot"],
                instruction="Use conflicts only when bounded evidence directly opposes the thesis or another bounded ClaimCard.",
                slot_kind="counterclaim_or_gap",
            ),
        ]
    return [
        _claim_slot(
            agent_id,
            slot_id=f"{_specialist_memo_slot(agent_id)}_material_gap",
            memo_slot=_specialist_memo_slot(agent_id),
            target_claim_count=common_cap,
            claim_type_allowlist=["source_gap", "business_observation"],
            required_source_families=_specialist_required_source_families(agent_id),
            instruction="If a required slot is not supported, state one material missing confirmation; do not enumerate non-material gaps.",
            slot_kind="counterclaim_or_gap",
        )
    ]


def _claim_slot(
    agent_id: str,
    *,
    slot_id: str,
    memo_slot: str,
    target_claim_count: str,
    claim_type_allowlist: list[str],
    required_source_families: list[str],
    instruction: str,
    slot_kind: str = "required_claim",
) -> dict[str, Any]:
    return {
        "schema_version": SPECIALIST_CLAIM_SLOT_SCHEMA_VERSION,
        "agent_id": agent_id,
        "slot_id": slot_id,
        "slot_kind": slot_kind,
        "memo_slot": memo_slot,
        "target_claim_count": target_claim_count,
        "claim_type_allowlist": claim_type_allowlist,
        "required_source_families": required_source_families,
        "evidence_ref_policy": "supported_claims_must_cite_known_evidence_refs",
        "instruction": instruction,
    }


def _requirements_for_specialist(agent_id: str, state: Mapping[str, Any]) -> list[dict[str, Any]]:
    requirements = _state_evidence_requirements(state)
    matched = [req for req in requirements if _requirement_matches_specialist(agent_id, req)]
    if agent_id == "risk_counterevidence_analyst" and not matched:
        matched = [
            req
            for req in requirements
            if str(req.get("priority") or "supporting") in {"primary", "supporting"}
        ][:6]
    return _dedupe_requirements(matched or requirements[:4])


def _state_evidence_requirements(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    plans = []
    if isinstance(state.get("evidence_requirement_plan"), Mapping):
        plans.append(state.get("evidence_requirement_plan"))
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    if isinstance(query_contract.get("evidence_requirement_plan"), Mapping):
        plans.append(query_contract.get("evidence_requirement_plan"))
    if isinstance(query_contract.get("evidence_requirements"), list):
        plans.append({"requirements": query_contract.get("evidence_requirements")})
    for plan in plans:
        candidates.extend(dict(item) for item in (plan or {}).get("requirements") or [] if isinstance(item, Mapping))
    for task in query_contract.get("decomposed_tasks") or []:
        if isinstance(task, Mapping):
            candidates.append(_requirement_from_decomposed_task(task, query_contract))
    return _dedupe_requirements(candidates)


def _requirement_from_decomposed_task(task: Mapping[str, Any], query_contract: Mapping[str, Any]) -> dict[str, Any]:
    source_tiers = _string_list(task.get("required_source_tiers") or task.get("source_tiers") or query_contract.get("source_tiers"))
    metric_families = _string_list(task.get("required_metric_families") or task.get("metric_families") or query_contract.get("metric_families"))
    tickers = _unique_upper(task.get("required_tickers") or task.get("tickers") or query_contract.get("focus_tickers"))
    return {
        "requirement_id": str(task.get("requirement_id") or task.get("task_id") or "decomposed_task"),
        "task_id": str(task.get("task_id") or task.get("requirement_id") or "decomposed_task"),
        "question_zh": str(task.get("question_zh") or task.get("question") or ""),
        "priority": str(task.get("priority") or "supporting"),
        "tickers": tickers,
        "source_tiers": source_tiers,
        "source_families": source_tiers,
        "metric_families": metric_families,
        "evidence_routes": _routes_for_source_families(source_tiers),
        "analysis_intent": str(task.get("analysis_intent") or ""),
    }


def _compact_task_card_requirement(requirement: Mapping[str, Any], index: int) -> dict[str, Any]:
    evidence_routes = _string_list(requirement.get("evidence_routes") or requirement.get("retrieval_routes"))
    source_families = _requirement_source_families(requirement)
    claim_families = _string_list(requirement.get("claim_families")) or _claim_families_for_requirement({"evidence_routes": evidence_routes})
    return {
        "requirement_id": str(requirement.get("requirement_id") or requirement.get("evidence_requirement_id") or f"req_{index}"),
        "task_id": str(requirement.get("task_id") or f"task_{index}"),
        "priority": str(requirement.get("priority") or "supporting"),
        "question_zh": str(requirement.get("question_zh") or requirement.get("question") or "")[:300],
        "analysis_intent": str(requirement.get("analysis_intent") or "")[:120],
        "tickers": _unique_upper(requirement.get("tickers") or requirement.get("required_tickers"))[:12],
        "peer_tickers": _unique_upper(requirement.get("peer_tickers"))[:12],
        "years": _int_list(requirement.get("years"))[:6],
        "filing_types": _string_list(requirement.get("filing_types"))[:8],
        "source_families": source_families[:8],
        "evidence_routes": evidence_routes[:8],
        "metric_families": _string_list(requirement.get("metric_families") or requirement.get("required_metric_families"))[:12],
        "claim_families": claim_families[:8],
    }


def _requirement_matches_specialist(agent_id: str, requirement: Mapping[str, Any]) -> bool:
    routes = set(_string_list(requirement.get("evidence_routes") or requirement.get("retrieval_routes")))
    families = set(_requirement_source_families(requirement))
    owners = set(_string_list(requirement.get("operator_owners") or requirement.get("operator_owner")))
    text = " ".join(
        str(requirement.get(key) or "").lower()
        for key in ("analysis_intent", "question_zh", "question", "task_id", "requirement_id")
    )
    if agent_id == "fundamental_analyst":
        return bool(families & {"primary_sec_filing", "company_authored_unaudited_sec_filing"} or routes & {"ledger_first", "filing_text", "8k_commentary"} or owners & {"sec_operator", "eight_k_operator"})
    if agent_id == "industry_supply_chain_analyst":
        return bool(families & {"industry_snapshot", "relationship_graph"} or routes & {"industry_snapshot", "relationship_graph"} or any(term in text for term in ("industry", "supply", "relationship", "sector", "chain", "readthrough")))
    if agent_id == "market_valuation_analyst":
        return bool("market_snapshot" in families or "market_snapshot" in routes or any(term in text for term in ("market", "valuation", "multiple", "return", "price", "reaction")))
    if agent_id == "risk_counterevidence_analyst":
        return bool("run_artifact" in families or "risk_text" in routes or any(term in text for term in ("risk", "counter", "gap", "unsupported", "conflict", "caveat", "downside")))
    return False


def _requirement_source_families(requirement: Mapping[str, Any]) -> list[str]:
    families = _string_list(
        requirement.get("source_families")
        or requirement.get("source_family")
        or requirement.get("planner_source_families")
        or requirement.get("source_tiers")
    )
    route_families = _source_families_for_routes(_string_list(requirement.get("evidence_routes") or requirement.get("retrieval_routes")))
    return _dedupe([*families, *route_families])


def _dedupe_requirements(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for index, req in enumerate(requirements, start=1):
        key = (
            str(req.get("requirement_id") or req.get("evidence_requirement_id") or f"req_{index}"),
            str(req.get("task_id") or f"task_{index}"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(req)
    return out


def _specialist_lens(agent_id: str) -> str:
    return {
        "fundamental_analyst": "company_reported_fundamentals_and_management_commentary",
        "industry_supply_chain_analyst": "industry_supply_chain_relationship_hypotheses_and_transmission",
        "market_valuation_analyst": "timestamped_market_reaction_and_valuation_context",
        "risk_counterevidence_analyst": "risks_counterevidence_source_gaps_and_boundary_misuse",
    }.get(agent_id, "bounded_specialist_analysis")


def _specialist_memo_slot(agent_id: str) -> str:
    return {
        "fundamental_analyst": "fundamentals",
        "industry_supply_chain_analyst": "industry_relationship",
        "market_valuation_analyst": "market_valuation",
        "risk_counterevidence_analyst": "risk_counterevidence",
    }.get(agent_id, "thesis")


def _specialist_required_source_families(agent_id: str) -> list[str]:
    return {
        "fundamental_analyst": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
        "industry_supply_chain_analyst": ["industry_snapshot", "relationship_graph"],
        "market_valuation_analyst": ["market_snapshot"],
        "risk_counterevidence_analyst": [
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "market_snapshot",
            "industry_snapshot",
            "run_artifact",
        ],
    }.get(agent_id, [])


def _available_source_families_for_specialist(agent_id: str, state: Mapping[str, Any]) -> list[str]:
    families: list[str] = []
    for key in ("runtime_ledger_rows", "context_rows", "market_snapshot_rows", "industry_snapshot_rows"):
        families.extend(_row_source_family(row) for row in _row_dicts(state.get(key)))
    if _relationship_rows_from_state(state):
        families.append("relationship_graph")
    required = set(_specialist_required_source_families(agent_id))
    return [family for family in _dedupe(families) if not required or family in required]


def _focus_tickers_from_state(state: Mapping[str, Any]) -> list[str]:
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    scope = query_contract.get("scope") if isinstance(query_contract.get("scope"), Mapping) else {}
    return _unique_upper(
        state.get("focus_tickers")
        or query_contract.get("focus_tickers")
        or scope.get("focus_tickers")
    )


def _search_scope_tickers_from_state(state: Mapping[str, Any], *, focus_tickers: list[str]) -> list[str]:
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    scope = query_contract.get("scope") if isinstance(query_contract.get("scope"), Mapping) else {}
    return _unique_upper(
        state.get("search_scope_tickers")
        or query_contract.get("search_scope_tickers")
        or scope.get("search_scope_tickers")
        or scope.get("universe_tickers")
        or focus_tickers
    )


def active_specialists_for_state(state: Mapping[str, Any]) -> list[str]:
    return [
        row["agent_id"]
        for row in specialist_activation_decisions(state)
        if row.get("decision") == "run"
    ]


def specialist_activation_decisions(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    active = set(_string_list(activation.get("activate_agents")))
    priorities = {str(agent): str(priority) for agent, priority in dict(activation.get("agent_priorities") or {}).items()}
    decisions: list[dict[str, Any]] = []
    for agent_id in SPECIALIST_EXECUTION_ORDER:
        if agent_id not in active:
            continue
        priority = priorities.get(agent_id) or "primary"
        signal = _specialist_evidence_signal(agent_id, state)
        should_run = priority in {"primary", "supporting"} or (priority == "conditional" and signal["signal_count"] > 0)
        if priority == "low":
            should_run = bool(signal["explicit_intent"] and signal["signal_count"] > 0)
        decisions.append(
            {
                "agent_id": agent_id,
                "priority": priority,
                "decision": "run" if should_run else "skipped",
                "reason": "priority_allows_run" if should_run and priority in {"primary", "supporting"} else signal["reason"],
                "signal_count": signal["signal_count"],
                "explicit_intent": bool(signal["explicit_intent"]),
                "policy": "cost_aware_specialist_activation_v0_1",
            }
        )
    return decisions


def execute_evidence_operator_plan(
    retrieval_plan: Mapping[str, Any],
    *,
    turn_id: str,
    ledger: ToolCallLedger | None = None,
    state_context: Mapping[str, Any] | None = None,
    tool_executor: ToolExecutor | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    active_ledger = ledger or ToolCallLedger()
    context = dict(state_context or {})
    executor = tool_executor or invoke_mcp_tool
    observations: list[dict[str, Any]] = []
    context_rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    market_rows: list[dict[str, Any]] = []
    industry_rows: list[dict[str, Any]] = []
    source_gaps: list[dict[str, Any]] = []
    artifact_refs: list[dict[str, Any]] = []

    for route in retrieval_plan.get("routes") or []:
        if not isinstance(route, Mapping):
            continue
        route_name = str(route.get("retrieval_route") or "")
        agent_id, tool_name = ROUTE_OPERATOR_TOOL.get(route_name, ("", ""))
        if not agent_id:
            observations.append(_observation(route, "", "", "blocked", error="unsupported_retrieval_route"))
            continue
        permission = validate_operator_tool_call(agent_id=agent_id, tool_name=tool_name)
        if permission["status"] != "pass":
            observations.append(_observation(route, agent_id, tool_name, "blocked", error=permission["error"]))
            continue
        arguments = tool_arguments_from_route(route, user_query=str(context.get("user_query") or ""), state_context=context)
        if route_name == "ledger_first" and not str(arguments.get("ledger_store_path") or "").strip():
            gap = {
                "source_family": "primary_sec_filing",
                "reason_code": "ledger_store_path_unavailable",
                "reason": "ledger_first route skipped because no ledger_store_path was configured for this run.",
                "source_available": False,
                "route_id": str(route.get("route_id") or ""),
            }
            observations.append(
                _observation(
                    route,
                    agent_id,
                    tool_name,
                    "skipped",
                    error="ledger_store_path_unavailable",
                    arguments=arguments,
                    row_count=0,
                    source_gap_count=1,
                )
            )
            source_gaps.append(gap)
            continue
        decision = active_ledger.can_call_tool(
            turn_id=turn_id,
            agent_id=agent_id,
            tool_name=tool_name,
            arguments=arguments,
        )
        if not decision["allowed"]:
            observations.append(_observation(route, agent_id, tool_name, "blocked", error=decision["reason"], arguments=arguments))
            continue
        result = _dry_run_result(tool_name, route) if dry_run else executor(tool_name, arguments)
        boundary = validate_tool_observation_boundary(tool_name, result)
        rows = _rows_from_result(tool_name, result)
        runtime_summary = _tool_runtime_summary(tool_name, result)
        gaps = _source_gaps_from_result(result)
        refs = [dict(item) for item in result.get("artifact_refs") or [] if isinstance(item, Mapping)]
        active_ledger.record_tool_call(
            turn_id=turn_id,
            agent_id=agent_id,
            tool_name=tool_name,
            arguments=arguments,
            output_artifact_digest=_first_artifact_digest(refs),
            row_count=len(rows),
            source_gap_count=len(gaps),
            coverage_delta={"closed_gaps": int(result.get("closed_gaps") or 0)},
            elapsed_ms=int(result.get("elapsed_ms") or 0),
            status=str(result.get("status") or "ok"),
            metadata={
                "route_id": route.get("route_id") or "",
                "retrieval_route": route_name,
                "boundary": boundary,
                "runtime_summary": runtime_summary,
                "error": str(result.get("error") or result.get("failure_reason") or "")[:500],
                "argument_summary": _tool_argument_summary(arguments),
            },
        )
        observations.append(
            _observation(
                route,
                agent_id,
                tool_name,
                str(result.get("status") or "ok"),
                arguments=arguments,
                row_count=len(rows),
                source_gap_count=len(gaps),
                boundary=boundary,
                runtime_summary=runtime_summary,
            )
        )
        if tool_name == "sec_search_filings":
            context_rows.extend(rows)
            ledger_rows.extend(dict(item) for item in result.get("runtime_ledger_rows") or [] if isinstance(item, Mapping))
        elif tool_name == "sec_query_exact_value_ledger":
            ledger_rows.extend(rows)
        elif tool_name == "market_get_snapshot":
            market_rows.extend(rows)
        elif tool_name == "industry_get_snapshot":
            industry_rows.extend(rows)
        elif tool_name == "relationship_graph_lookup":
            context_rows.extend(rows)
        source_gaps.extend(gaps)
        artifact_refs.extend(refs)

    return {
        "schema_version": RUNTIME_SCHEMA_VERSION,
        "tool_observations": observations,
        "tool_call_ledger": active_ledger.to_dict(),
        "context_rows": context_rows,
        "runtime_ledger_rows": ledger_rows,
        "market_snapshot_rows": market_rows,
        "industry_snapshot_rows": industry_rows,
        "source_gaps": source_gaps,
        "artifact_refs": artifact_refs,
        "loop_break_reason": active_ledger.loop_break_reason,
        "bounded_answer_allowed": active_ledger.bounded_answer_allowed,
    }


def validate_operator_tool_call(*, agent_id: str, tool_name: str) -> dict[str, Any]:
    registry = agent_registry_by_id()
    entry = registry.get(agent_id)
    if not entry:
        return {"status": "fail", "error": f"unknown_agent:{agent_id}"}
    if agent_id == "universe_relationship" and tool_name == "relationship_graph_lookup":
        allowed = set(entry.get("allowed_tools") or [])
        if tool_name not in allowed:
            return {"status": "fail", "error": f"tool_not_allowed_for_agent:{agent_id}:{tool_name}"}
        if "relationship_graph" not in set(entry.get("source_families") or []):
            return {"status": "fail", "error": f"source_family_not_allowed_for_agent:{agent_id}:relationship_graph"}
        return {"status": "pass", "permission_boundary": "bounded_relationship_lookup"}
    if str(entry.get("tool_permission") or "") != "bounded_execute":
        return {"status": "fail", "error": f"agent_not_bounded_execute:{agent_id}"}
    allowed = set(entry.get("allowed_tools") or [])
    if tool_name not in allowed:
        return {"status": "fail", "error": f"tool_not_allowed_for_agent:{agent_id}:{tool_name}"}
    return {"status": "pass"}


def tool_arguments_from_route(
    route: Mapping[str, Any],
    *,
    user_query: str,
    state_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    context = dict(state_context or {})
    route_name = str(route.get("retrieval_route") or "")
    coverage = route.get("coverage_requirements") if isinstance(route.get("coverage_requirements"), Mapping) else {}
    args: dict[str, Any] = {
        "tickers": list(route.get("tickers") or coverage.get("tickers") or []),
        "years": list(route.get("years") or coverage.get("years") or []),
        "filing_types": list(route.get("filing_types") or coverage.get("filing_types") or []),
        "source_tiers": list(route.get("source_tiers") or coverage.get("source_tiers") or []),
        "metric_families": list(route.get("metric_families") or coverage.get("metric_families") or []),
        "period_roles": list(route.get("period_roles") or coverage.get("period_roles") or []),
        "evidence_requirement_id": str(route.get("evidence_requirement_id") or ""),
        "limit": int(route.get("limit") or context.get("limit") or 120),
    }
    if route_name == "ledger_first":
        if context.get("ledger_store_path"):
            args["ledger_store_path"] = context["ledger_store_path"]
        return args
    if route_name in {"filing_text", "risk_text", "8k_commentary"}:
        args["source_tiers"] = _sec_search_source_tiers_for_route(route_name, _string_list(args.get("source_tiers")))
        args.update(
            {
                "query": str(route.get("query") or user_query or route.get("task_id") or ""),
                "retrieval_route": route_name,
                "candidate_budget": int(route.get("candidate_budget") or 0),
                "rerank_budget": int(route.get("rerank_budget") or 0),
                "sections": list(route.get("section_hints") or []),
            }
        )
        args.update(_sec_search_runtime_args(context, route))
        return args
    if route_name == "market_snapshot":
        market = context.get("market_snapshot") if isinstance(context.get("market_snapshot"), Mapping) else {}
        args.update(
            {
                "fields": list(coverage.get("market_fields") or route.get("market_fields") or []),
                "analysis_tools": list(coverage.get("market_analysis_tools") or route.get("analysis_tools") or []),
                "snapshot_id": str(context.get("market_snapshot_id") or market.get("snapshot_id") or ""),
                "as_of_date": str(context.get("market_as_of_date") or market.get("as_of_date") or ""),
                "market_evidence_path": str(context.get("market_evidence_path") or ""),
            }
        )
        return args
    if route_name == "industry_snapshot":
        args.update(
            {
                "source_families": _industry_source_families_for_route(route, context=context, user_query=user_query),
                "providers": list(route.get("providers") or []),
                "datasets": list(route.get("datasets") or []),
                "facets": dict(route.get("facets") or {}),
                "industry_evidence_path": str(context.get("industry_evidence_path") or ""),
                "industry_snapshot_db_path": str(context.get("industry_snapshot_db_path") or ""),
            }
        )
        return args
    if route_name == "relationship_graph":
        args.update(
            {
                "focus_tickers": list(context.get("focus_tickers") or route.get("focus_tickers") or route.get("tickers") or coverage.get("tickers") or []),
                "search_scope_tickers": list(
                    context.get("search_scope_tickers") or route.get("search_scope_tickers") or route.get("tickers") or coverage.get("tickers") or []
                ),
                "user_query": user_query,
                "relationship_graph_path": str(context.get("relationship_graph_path") or ""),
                "sector_depth_pack_path": str(context.get("sector_depth_pack_path") or ""),
                "expected_relationship_pack_ids": list(context.get("expected_relationship_pack_ids") or []),
                "max_relationships": int(route.get("max_relationships") or context.get("max_relationships") or 24),
                "max_expanded_tickers": int(route.get("max_expanded_tickers") or context.get("max_expanded_tickers") or 12),
                "include_sector_depth": _bool_value(context.get("include_sector_depth", True)),
            }
        )
        return args
    return args


def _sec_search_source_tiers_for_route(route_name: str, source_tiers: list[str]) -> list[str]:
    valid = [tier for tier in source_tiers if tier in SEC_SEARCH_SOURCE_TIERS]
    if valid:
        return _dedupe(valid)
    if route_name == "8k_commentary":
        return ["company_authored_unaudited_sec_filing"]
    return ["primary_sec_filing", "company_authored_unaudited_sec_filing"]


def _industry_source_families_for_route(
    route: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
    user_query: str,
) -> list[str]:
    explicit = _string_list(route.get("source_families"))
    explicit = [family for family in explicit if family != "industry_snapshot"]
    if explicit:
        return explicit
    configured = _string_list(context.get("industry_source_families"))
    configured = [family for family in configured if family != "industry_snapshot"]
    if configured:
        return configured
    text = " ".join(
        [
            user_query,
            str(route.get("task_id") or ""),
            str(route.get("sector") or ""),
            " ".join(str(item) for item in route.get("metric_families") or []),
            " ".join(str(item) for item in route.get("tickers") or []),
        ]
    ).lower()
    families: list[str] = []
    if _contains_any(text, ("bank", "credit", "deposit", "nii", "net_interest", "rates", "rate", "jpm", "wfc", "gs")):
        families.append("industry_macro_rates_credit")
    if _contains_any(text, ("health", "drug", "hospital", "procedure", "clinical", "pfe", "bmy", "amgn", "hca")):
        families.append("industry_healthcare_regulatory")
    if _contains_any(text, ("energy", "oil", "gas", "commodity", "production", "oxy", "hal", "lng", "wmb")):
        families.append("industry_energy_commodities")
    if _contains_any(text, ("utility", "utilities", "power", "electric", "load", "rate base", "sre", "xel", "ed", "exc")):
        families.extend(["industry_housing_real_estate_power", "industry_utilities_power_demand"])
    if _contains_any(text, ("ai", "gpu", "data center", "datacenter", "infrastructure", "capex", "nvda", "dell", "anet", "vrt")):
        families.extend(["industry_housing_real_estate_power", "industry_utilities_power_demand", "industry_industrial_macro"])
    return _dedupe(families)


def _sec_search_runtime_args(context: Mapping[str, Any], route: Mapping[str, Any]) -> dict[str, Any]:
    args: dict[str, Any] = {}
    for key in (
        "manifest_path",
        "source_gap_path",
        "market_evidence_path",
        "industry_evidence_path",
        "bm25_index_dir",
        "object_bm25_index_dir",
        "bge_model",
        "context_runner",
        "ledger_store_path",
        "llm_backend",
        "base_url",
        "chat_completions_path",
        "model",
        "api_key_env",
    ):
        value = context.get(key)
        if value not in (None, ""):
            args[key] = value

    runtime_policy = derive_sec_search_runtime_policy(context, route)
    for key in (
        "candidate_budget",
        "rerank_budget",
        "evidence_top_k",
        "object_top_k",
        "reranker_candidate_limit",
        "reranker_top_k",
        "reranker_batch_size",
        "reranker_max_length",
        "reranker_doc_max_chars",
    ):
        if runtime_policy.get(key) not in (None, ""):
            args[key] = int(runtime_policy[key])
    args["bge_device"] = str(runtime_policy.get("bge_device") or "cpu")
    args["bge_first"] = bool(runtime_policy.get("bge_first"))
    args["retrieval_runtime_policy"] = {
        "schema_version": SEC_SEARCH_RUNTIME_POLICY_SCHEMA_VERSION,
        "policy_name": runtime_policy.get("policy_name") or "",
        "execution_mode": runtime_policy.get("execution_mode") or "",
        "retrieval_route": runtime_policy.get("retrieval_route") or "",
        "sector_depth_expected": bool(runtime_policy.get("sector_depth_expected")),
        "bge_device_policy": runtime_policy.get("bge_device_policy") or "",
        "cuda_available": runtime_policy.get("cuda_available"),
    }
    if context.get("build_runtime_ledger") is not None:
        args["build_runtime_ledger"] = _bool_value(context.get("build_runtime_ledger"))
    if context.get("output_dir"):
        args["output_dir"] = _route_output_dir(str(context.get("output_dir") or ""), str(route.get("route_id") or "route"))
    if context.get("run_id"):
        args["run_id"] = f"{context.get('run_id')}_{_slug(route.get('route_id') or route.get('retrieval_route') or 'route')}"
    return args


def derive_sec_search_runtime_policy(context: Mapping[str, Any], route: Mapping[str, Any]) -> dict[str, Any]:
    route_name = str(route.get("retrieval_route") or "")
    execution_mode = str(context.get("execution_mode") or context.get("multi_agent_execution_mode") or "").strip() or "focused_answer"
    coverage = route.get("coverage_requirements") if isinstance(route.get("coverage_requirements"), Mapping) else {}
    tickers = _unique_upper(route.get("tickers") or coverage.get("tickers") or context.get("search_scope_tickers"))
    source_families = set(_string_list(route.get("source_families") or route.get("source_tiers") or context.get("source_tiers")))
    sector_depth_expected = bool(
        source_families & {"industry_snapshot", "relationship_graph"}
        or context.get("sector_depth_pack_path")
        or context.get("expected_relationship_pack_ids")
        or len(tickers) >= 4
    )
    profile = _retrieval_policy_profile(execution_mode, route_name=route_name, sector_depth_expected=sector_depth_expected, ticker_count=len(tickers))
    policy = {
        "policy_name": profile["policy_name"],
        "execution_mode": execution_mode,
        "retrieval_route": route_name,
        "sector_depth_expected": sector_depth_expected,
        "candidate_budget": max(_positive_int(route.get("candidate_budget")), profile["candidate_budget"]),
        "rerank_budget": max(_positive_int(route.get("rerank_budget")), profile["rerank_budget"]),
        "evidence_top_k": profile["evidence_top_k"],
        "object_top_k": profile["object_top_k"],
        "reranker_candidate_limit": profile["reranker_candidate_limit"],
        "reranker_top_k": profile["reranker_top_k"],
        "reranker_batch_size": profile["reranker_batch_size"],
        "reranker_max_length": profile["reranker_max_length"],
        "reranker_doc_max_chars": profile["reranker_doc_max_chars"],
        "bge_device": _resolve_bge_device(context, execution_mode=execution_mode),
        "bge_first": _bool_value(context.get("bge_first")) if context.get("bge_first") is not None else True,
    }
    policy["bge_device_policy"] = _bge_device_policy_label(context, str(policy["bge_device"]))
    policy["cuda_available"] = _cuda_available() if str(policy["bge_device"]).lower().startswith("cuda") else None
    for key in (
        "evidence_top_k",
        "object_top_k",
        "reranker_candidate_limit",
        "reranker_top_k",
        "reranker_batch_size",
        "reranker_max_length",
        "reranker_doc_max_chars",
    ):
        override_value = _positive_int(context.get(key))
        if override_value > 0:
            policy[key] = override_value
    if context.get("candidate_budget") not in (None, ""):
        override_value = _positive_int(context.get("candidate_budget"))
        if override_value > 0:
            policy["candidate_budget"] = override_value
    if context.get("rerank_budget") not in (None, ""):
        override_value = _positive_int(context.get("rerank_budget"))
        if override_value > 0:
            policy["rerank_budget"] = override_value
    return policy


def _retrieval_policy_profile(
    execution_mode: str,
    *,
    route_name: str,
    sector_depth_expected: bool,
    ticker_count: int,
) -> dict[str, Any]:
    if execution_mode == "deep_research":
        profile = {
            "policy_name": "deep_research_sector_depth" if sector_depth_expected else "deep_research",
            "candidate_budget": 360,
            "rerank_budget": 96,
            "evidence_top_k": 8,
            "object_top_k": 8,
            "reranker_candidate_limit": 360,
            "reranker_top_k": 96,
            "reranker_batch_size": 8,
            "reranker_max_length": 512,
            "reranker_doc_max_chars": 2400,
        }
    elif execution_mode == "standard_memo":
        profile = {
            "policy_name": "standard_memo_balanced",
            "candidate_budget": 240,
            "rerank_budget": 64,
            "evidence_top_k": 6,
            "object_top_k": 6,
            "reranker_candidate_limit": 240,
            "reranker_top_k": 64,
            "reranker_batch_size": 8,
            "reranker_max_length": 512,
            "reranker_doc_max_chars": 2200,
        }
    else:
        profile = {
            "policy_name": "focused_answer_compact",
            "candidate_budget": 160,
            "rerank_budget": 40,
            "evidence_top_k": 4,
            "object_top_k": 4,
            "reranker_candidate_limit": 160,
            "reranker_top_k": 40,
            "reranker_batch_size": 8,
            "reranker_max_length": 512,
            "reranker_doc_max_chars": 1800,
        }
    if sector_depth_expected or ticker_count >= 4:
        profile["candidate_budget"] = max(int(profile["candidate_budget"]), 480)
        profile["rerank_budget"] = max(int(profile["rerank_budget"]), 120)
        profile["evidence_top_k"] = max(int(profile["evidence_top_k"]), 10)
        profile["object_top_k"] = max(int(profile["object_top_k"]), 8)
        profile["reranker_candidate_limit"] = max(int(profile["reranker_candidate_limit"]), 480)
        profile["reranker_top_k"] = max(int(profile["reranker_top_k"]), 120)
        profile["reranker_doc_max_chars"] = max(int(profile["reranker_doc_max_chars"]), 2400)
        if execution_mode != "deep_research":
            profile["policy_name"] = f"{profile['policy_name']}_sector_depth"
    if route_name == "risk_text":
        profile["policy_name"] = f"{profile['policy_name']}_risk"
        profile["evidence_top_k"] = max(int(profile["evidence_top_k"]), 8)
        profile["reranker_top_k"] = max(int(profile["reranker_top_k"]), 80)
    if route_name == "8k_commentary":
        profile["policy_name"] = f"{profile['policy_name']}_8k"
        profile["evidence_top_k"] = max(int(profile["evidence_top_k"]), 6)
    return profile


def _resolve_bge_device(context: Mapping[str, Any], *, execution_mode: str) -> str:
    requested = str(context.get("bge_device") or os.environ.get("BGE_DEVICE") or "").strip().lower()
    if requested and requested not in {"auto", "default"}:
        return requested
    if _cuda_available():
        return "cuda"
    return "cpu"


def _bge_device_policy_label(context: Mapping[str, Any], resolved_device: str) -> str:
    requested = str(context.get("bge_device") or os.environ.get("BGE_DEVICE") or "").strip().lower()
    if requested and requested not in {"auto", "default"}:
        return "explicit"
    if resolved_device == "cuda":
        return "auto_cuda_available"
    return "auto_cpu_fallback"


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        return False


def _route_output_dir(base_output_dir: str, route_id: str) -> str:
    base = str(base_output_dir or "").rstrip("/\\")
    suffix = _slug(route_id)
    if not base:
        return ""
    return f"{base}/mcp_retrieval/{suffix}"


def _tool_runtime_summary(tool_name: str, result: Mapping[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"tool_name": tool_name}
    if tool_name == "sec_search_filings":
        candidate_counts = result.get("candidate_counts") if isinstance(result.get("candidate_counts"), Mapping) else {}
        context_runtime = result.get("context_runtime") if isinstance(result.get("context_runtime"), Mapping) else {}
        summary.update(
            {
                "context_row_count": len(result.get("context_rows") or []),
                "runtime_ledger_row_count": len(result.get("runtime_ledger_rows") or []),
                "candidate_counts": _sanitize_runtime_mapping(candidate_counts),
                "context_runtime": _sanitize_runtime_mapping(context_runtime),
            }
        )
    elif tool_name == "market_get_snapshot":
        summary.update(
            {
                "market_row_count": len(result.get("market_rows") or []),
                "snapshot_id": str(result.get("snapshot_id") or ""),
                "as_of_date": str(result.get("as_of_date") or ""),
            }
        )
    elif tool_name == "industry_get_snapshot":
        summary.update({"industry_row_count": len(result.get("industry_rows") or [])})
    elif tool_name == "relationship_graph_lookup":
        summary.update(
            {
                "relationship_row_count": len(result.get("relationship_rows") or []),
                "expanded_ticker_count": len(result.get("expanded_tickers") or []),
            }
        )
    return summary


def _tool_argument_summary(arguments: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "retrieval_route",
        "tickers",
        "years",
        "filing_types",
        "source_tiers",
        "metric_families",
        "period_roles",
        "candidate_budget",
        "rerank_budget",
        "evidence_top_k",
        "object_top_k",
        "reranker_candidate_limit",
        "reranker_top_k",
        "reranker_batch_size",
        "reranker_doc_max_chars",
        "source_families",
        "providers",
        "datasets",
        "fields",
        "limit",
        "bge_device",
        "bge_first",
        "context_runner",
        "build_runtime_ledger",
        "retrieval_runtime_policy",
    }
    return {key: arguments.get(key) for key in allowed if key in arguments}


def _specialist_evidence_signal(agent_id: str, state: Mapping[str, Any]) -> dict[str, Any]:
    query_text = _state_query_text(state)
    if agent_id == "fundamental_analyst":
        count = len(state.get("runtime_ledger_rows") or []) + len(
            [row for row in _row_dicts(state.get("context_rows")) if _row_source_family(row) in {"", "primary_sec_filing", "company_authored_unaudited_sec_filing"}]
        )
        explicit = _contains_any(query_text, ("fundamental", "revenue", "margin", "capex", "cash flow", "基本面", "收入", "利润率", "资本开支"))
        return _signal(count, explicit, "fundamental_evidence_rows_or_explicit_fundamental_intent")
    if agent_id == "industry_supply_chain_analyst":
        count = len(state.get("industry_snapshot_rows") or []) + len(_relationship_rows_from_state(state))
        explicit = _contains_any(query_text, ("industry", "sector", "supply chain", "customer", "supplier", "relationship", "行业", "产业链", "上下游", "供应链", "客户", "供应商", "关系"))
        return _signal(count, explicit, "industry_or_relationship_rows_or_explicit_readthrough_intent")
    if agent_id == "market_valuation_analyst":
        count = len(state.get("market_snapshot_rows") or []) + len(
            [row for row in _row_dicts(state.get("context_rows")) if _row_source_family(row) == "market_snapshot"]
        )
        explicit = _contains_any(query_text, ("market", "valuation", "multiple", "share price", "return", "市场", "估值", "倍数", "股价"))
        return _signal(count, explicit, "market_snapshot_rows_or_explicit_market_intent")
    if agent_id == "risk_counterevidence_analyst":
        count = (
            len(state.get("source_gaps") or [])
            + len(state.get("runtime_ledger_rows") or [])
            + len(state.get("context_rows") or [])
            + len(state.get("market_snapshot_rows") or [])
            + len(state.get("industry_snapshot_rows") or [])
        )
        explicit = _contains_any(query_text, ("risk", "counterevidence", "downside", "uncertainty", "conflict", "风险", "反证", "下行", "不确定", "分歧"))
        return _signal(count if explicit else len(state.get("source_gaps") or []), explicit, "risk_intent_or_source_gaps")
    return _signal(0, False, "unknown_specialist")


def _signal(count: int, explicit_intent: bool, reason: str) -> dict[str, Any]:
    signal_count = int(count or 0)
    return {
        "signal_count": signal_count + (1 if explicit_intent else 0),
        "explicit_intent": explicit_intent,
        "reason": reason if signal_count or explicit_intent else "conditional_specialist_without_matching_evidence_or_intent",
    }


def _state_query_text(state: Mapping[str, Any]) -> str:
    contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    return " ".join(
        [
            str(state.get("user_query") or ""),
            " ".join(_string_list(contract.get("metric_families") or contract.get("source_tiers") or [])),
            " ".join(_string_list(activation.get("allowed_source_families") or [])),
        ]
    ).lower()


def _sanitize_runtime_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, item in value.items():
        key_text = str(key)
        if key_text.endswith("_path") or "path" in key_text.lower():
            continue
        if isinstance(item, Mapping):
            clean[key_text] = _sanitize_runtime_mapping(item)
        elif isinstance(item, list):
            clean[key_text] = [
                _sanitize_runtime_mapping(row) if isinstance(row, Mapping) else row
                for row in item[:20]
            ]
        else:
            clean[key_text] = item
    return clean


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def validate_tool_observation_boundary(tool_name: str, result: Mapping[str, Any]) -> dict[str, Any]:
    if tool_name == "market_get_snapshot":
        missing = []
        if not str(result.get("snapshot_id") or ""):
            missing.append("snapshot_id")
        if not str(result.get("as_of_date") or ""):
            missing.append("as_of_date")
        return {
            "status": "fail" if missing else "pass",
            "allowed_claim_scope": "market_or_valuation_context",
            "missing": missing,
        }
    if tool_name == "industry_get_snapshot":
        return {
            "status": "pass",
            "allowed_claim_scope": "industry_context_only",
            "prohibited_claim_scope": "company_reported_financial_fact",
        }
    if tool_name == "relationship_graph_lookup":
        return {
            "status": "pass",
            "allowed_claim_scope": "research_scope_or_hypothesis_only",
            "prohibited_claim_scope": "company_reported_financial_fact",
        }
    if tool_name == "sec_query_exact_value_ledger":
        return {"status": "pass", "allowed_claim_scope": "reported_financial_fact"}
    return {"status": "pass", "allowed_claim_scope": "filing_text_or_management_context"}


def normalize_reflection_report(payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(payload or {})
    level = str(payload.get("sufficiency_level") or "partial")
    if level not in {"sufficient", "partial", "insufficient"}:
        level = "partial"
    return {
        "schema_version": "sec_agent_multi_agent_reflection_report_v0.1",
        "sufficiency_level": level,
        "missing_requirements": [dict(item) for item in payload.get("missing_requirements") or [] if isinstance(item, Mapping)],
        "source_available": bool(payload.get("source_available")),
        "second_pass_requests": [dict(item) for item in payload.get("second_pass_requests") or [] if isinstance(item, Mapping)],
        "source_family_gaps": [dict(item) for item in payload.get("source_family_gaps") or [] if isinstance(item, Mapping)],
        "tool_ledger_summary": dict(payload.get("tool_ledger_summary") or {}),
        "needs_user_clarification": bool(payload.get("needs_user_clarification")),
        "bounded_answer_allowed": bool(payload.get("bounded_answer_allowed")),
        "confidence_by_claim_type": dict(payload.get("confidence_by_claim_type") or {}),
        "trigger": str(payload.get("trigger") or "coverage_reflection"),
        "quality_gaps": [dict(item) for item in payload.get("quality_gaps") or [] if isinstance(item, Mapping)],
    }


def reflection_report_from_coverage(
    coverage_matrix: Mapping[str, Any] | None,
    *,
    source_available: bool = True,
    evidence_requirement_plan: Mapping[str, Any] | None = None,
    source_gaps: list[Mapping[str, Any]] | None = None,
    tool_ledger_summary: Mapping[str, Any] | None = None,
    available_source_families: set[str] | list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    coverage = dict(coverage_matrix or {})
    summary = coverage.get("summary") if isinstance(coverage.get("summary"), Mapping) else {}
    tasks = [dict(item) for item in coverage.get("tasks") or [] if isinstance(item, Mapping)]
    requirement_index = _evidence_requirements_by_task(evidence_requirement_plan)
    source_gaps_list = [dict(item) for item in (source_gaps or coverage.get("source_coverage_gaps") or []) if isinstance(item, Mapping)]
    available_sources = set(_string_list(available_source_families)) if available_source_families is not None else None
    missing = []
    second_pass_requests = []
    source_family_gaps = []
    for index, task in enumerate(tasks, start=1):
        if str(task.get("support_level") or "").lower() in {"strong", "sufficient"}:
            continue
        requirement = requirement_index.get(str(task.get("evidence_requirement_id") or "")) or requirement_index.get(str(task.get("task_id") or ""))
        missing_item = _missing_requirement_from_coverage_task(
            task,
            requirement=requirement,
            source_gaps=source_gaps_list,
            available_source_families=available_sources,
        )
        missing.append(missing_item)
        source_family_gaps.extend(_source_family_gap_items(missing_item))
        if missing_item.get("source_available", True):
            second_pass_requests.append(_second_pass_request_from_missing(missing_item, index))
    complete = bool(summary.get("coverage_complete") and summary.get("primary_task_support_complete"))
    all_missing_sources_available = all(bool(item.get("source_available", True)) for item in missing)
    report_source_available = bool(source_available and all_missing_sources_available)
    level = "sufficient" if complete else "partial" if report_source_available else "insufficient"
    return normalize_reflection_report(
        {
            "sufficiency_level": level,
            "missing_requirements": missing,
            "source_available": report_source_available,
            "second_pass_requests": second_pass_requests if report_source_available and not complete else [],
            "source_family_gaps": source_family_gaps,
            "tool_ledger_summary": dict(tool_ledger_summary or {}),
            "needs_user_clarification": not report_source_available and not complete,
            "bounded_answer_allowed": not complete,
            "confidence_by_claim_type": {},
        }
    )


def reflection_report_from_tool_observations(
    retrieval_plan: Mapping[str, Any] | None,
    *,
    evidence_requirement_plan: Mapping[str, Any] | None = None,
    tool_observations: list[Mapping[str, Any]] | None = None,
    source_gaps: list[Mapping[str, Any]] | None = None,
    tool_ledger_summary: Mapping[str, Any] | None = None,
    available_source_families: set[str] | list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Derive a conservative coverage reflection when no explicit coverage matrix exists."""
    plan = evidence_requirement_plan if isinstance(evidence_requirement_plan, Mapping) else {}
    routes = [dict(item) for item in (retrieval_plan or {}).get("routes") or [] if isinstance(item, Mapping)]
    observations = [dict(item) for item in tool_observations or [] if isinstance(item, Mapping)]
    if not routes and not (plan.get("requirements") if isinstance(plan, Mapping) else []):
        return normalize_reflection_report(
            {
                "sufficiency_level": "sufficient",
                "source_available": True,
                "tool_ledger_summary": dict(tool_ledger_summary or {}),
                "trigger": "coverage_reflection_tool_observations",
            }
        )

    tasks = _coverage_tasks_from_tool_observations(routes, observations, plan)
    coverage_complete = len(tasks) == 0
    coverage_matrix = {
        "summary": {
            "coverage_complete": coverage_complete,
            "primary_task_support_complete": not any(str(task.get("priority") or "") in {"primary", "critical"} for task in tasks),
        },
        "tasks": tasks,
        "source_coverage_gaps": [
            *[dict(item) for item in source_gaps or [] if isinstance(item, Mapping)],
            *_source_gaps_from_blocked_observations(routes, observations),
        ],
    }
    report = reflection_report_from_coverage(
        coverage_matrix,
        source_available=True,
        evidence_requirement_plan=plan,
        source_gaps=coverage_matrix["source_coverage_gaps"],
        tool_ledger_summary=tool_ledger_summary,
        available_source_families=available_source_families,
    )
    report["trigger"] = "coverage_reflection_tool_observations"
    return report


def should_execute_second_pass(report: Mapping[str, Any], ledger: ToolCallLedger) -> dict[str, Any]:
    normalized = normalize_reflection_report(report)
    if normalized["sufficiency_level"] == "sufficient":
        return {"allowed": False, "reason": "evidence_sufficient"}
    if not normalized["source_available"]:
        ledger.bounded_answer_allowed = True
        return {"allowed": False, "reason": "source_not_available", "bounded_answer_allowed": True}
    if not normalized["second_pass_requests"]:
        return {"allowed": False, "reason": "no_second_pass_requests"}
    decision = ledger.can_start_second_pass()
    if not decision["allowed"]:
        ledger.bounded_answer_allowed = True
        return {**decision, "bounded_answer_allowed": True}
    return {
        "allowed": True,
        "reason": "",
        "request_count": len(normalized["second_pass_requests"]),
        "trigger": normalized.get("trigger") or "coverage_reflection",
    }


def quality_reflection_report_from_judgment(
    judgment_plan: Mapping[str, Any] | None,
    *,
    state: Mapping[str, Any] | None = None,
    evidence_requirement_plan: Mapping[str, Any] | None = None,
    source_gaps: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create one bounded second-pass request set from post-specialist quality gaps."""
    graph_state = dict(state or {})
    activation = graph_state.get("agent_activation_plan") if isinstance(graph_state.get("agent_activation_plan"), Mapping) else {}
    mode = str(activation.get("execution_mode") or graph_state.get("execution_mode") or "").strip()
    if mode not in {"standard_memo", "deep_research"}:
        return normalize_reflection_report({"sufficiency_level": "sufficient", "source_available": True, "trigger": "quality_second_pass"})

    specialists = [dict(item) for item in graph_state.get("specialist_outputs") or [] if isinstance(item, Mapping)]
    if specialists and all(str(item.get("status") or "") == "stubbed" for item in specialists):
        return normalize_reflection_report({"sufficiency_level": "sufficient", "source_available": True, "trigger": "quality_second_pass"})

    plan = evidence_requirement_plan if evidence_requirement_plan is not None else graph_state.get("evidence_requirement_plan")
    judgment = dict(judgment_plan or {})
    gaps = [dict(item) for item in (source_gaps if source_gaps is not None else graph_state.get("source_gaps") or []) if isinstance(item, Mapping)]
    supported_claims = [dict(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)]
    quality_gaps: list[dict[str, Any]] = []
    second_pass_requests: list[dict[str, Any]] = []

    for gap in gaps:
        if not _source_gap_marks_unavailable(gap):
            quality_gap = _quality_gap_from_source_gap(gap, plan, len(quality_gaps) + 1)
            if _string_list(quality_gap.get("evidence_routes")):
                quality_gaps.append(quality_gap)

    if mode == "deep_research":
        missing_tickers = _required_tickers_missing_supported_claims(plan, supported_claims, graph_state)
        if missing_tickers:
            quality_gaps.append(_quality_gap_missing_ticker_cards(missing_tickers, plan))
        if _numeric_metric_requested_without_ledger(plan, graph_state):
            quality_gaps.append(_quality_gap_missing_numeric_ledger(plan, graph_state))
        if _relationship_evidence_expected_without_claim_ref(plan, supported_claims, graph_state):
            quality_gaps.append(_quality_gap_missing_relationship_ref(plan, graph_state))

    for index, gap in enumerate(quality_gaps[:4], start=1):
        second_pass_requests.append(_second_pass_request_from_missing(gap, index))

    return normalize_reflection_report(
        {
            "sufficiency_level": "partial" if second_pass_requests else "sufficient",
            "missing_requirements": quality_gaps,
            "source_available": True,
            "second_pass_requests": second_pass_requests,
            "source_family_gaps": [item for gap in quality_gaps for item in _source_family_gap_items(gap)],
            "tool_ledger_summary": dict(judgment.get("memo_constraints", {}).get("tool_ledger_summary") or {}),
            "bounded_answer_allowed": bool(quality_gaps),
            "trigger": "quality_second_pass",
            "quality_gaps": quality_gaps,
        }
    )


def record_second_pass_outcome(
    ledger: ToolCallLedger,
    *,
    added_row_count: int,
    coverage_delta: Mapping[str, Any] | None = None,
    source_gap_delta: int = 0,
) -> dict[str, Any]:
    return ledger.record_second_pass_result(
        added_row_count=added_row_count,
        coverage_delta=coverage_delta or {},
        source_gap_delta=source_gap_delta,
    )


def _quality_gap_from_source_gap(
    gap: Mapping[str, Any],
    plan: Mapping[str, Any] | None,
    index: int,
) -> dict[str, Any]:
    families = _string_list(gap.get("source_families") or gap.get("source_family") or gap.get("source_tiers") or gap.get("source_tier"))
    if not families:
        families = ["primary_sec_filing"]
    routes = _routes_for_source_families(families)
    return {
        "requirement_id": str(gap.get("requirement_id") or f"quality_source_gap_{index}"),
        "task_id": str(gap.get("task_id") or f"quality_source_gap_{index}"),
        "question_zh": str(gap.get("question_zh") or gap.get("reason") or "Close source gap before memo writing."),
        "priority": "primary",
        "analysis_intent": "quality_source_gap_second_pass",
        "tickers": _string_list(gap.get("tickers") or gap.get("ticker")) or _required_tickers_from_plan(plan),
        "years": _years_from_plan(plan),
        "filing_types": _filing_types_from_plan(plan),
        "source_family_gaps": families,
        "source_families": families,
        "source_tiers": [family for family in families if family in SEC_SEARCH_SOURCE_TIERS],
        "metric_families": _metric_families_from_plan(plan),
        "evidence_routes": routes,
        "operator_owners": _operator_owners_for_routes(routes),
        "route_intents": _route_intents_for_routes(routes),
        "claim_families": _claim_families_for_requirement({"evidence_routes": routes}),
        "source_available": True,
        "support_level": "insufficient",
        "reason": str(gap.get("reason") or gap.get("reason_code") or "source_gap_without_second_pass"),
        "quality_gap_type": "source_gap_without_second_pass",
    }


def _quality_gap_missing_ticker_cards(
    tickers: list[str],
    plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    routes = ["ledger_first", "filing_text"]
    return {
        "requirement_id": "quality_missing_required_ticker_claim_cards",
        "task_id": "quality_missing_required_ticker_claim_cards",
        "question_zh": "Fetch company-reported evidence for required tickers that have no supported claim cards.",
        "priority": "primary",
        "analysis_intent": "missing_required_ticker_claim_card_second_pass",
        "tickers": tickers,
        "years": _years_from_plan(plan),
        "filing_types": _filing_types_from_plan(plan),
        "source_family_gaps": ["primary_sec_filing"],
        "source_families": ["primary_sec_filing"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": _metric_families_from_plan(plan),
        "evidence_routes": routes,
        "operator_owners": _operator_owners_for_routes(routes),
        "route_intents": _route_intents_for_routes(routes),
        "claim_families": ["reported_financial_fact"],
        "source_available": True,
        "support_level": "insufficient",
        "reason": "required_ticker_without_supported_claim_card",
        "quality_gap_type": "missing_required_ticker_claim_card",
    }


def _quality_gap_missing_numeric_ledger(plan: Mapping[str, Any] | None, state: Mapping[str, Any]) -> dict[str, Any]:
    routes = ["ledger_first", "filing_text"]
    return {
        "requirement_id": "quality_missing_numeric_runtime_ledger",
        "task_id": "quality_missing_numeric_runtime_ledger",
        "question_zh": "Fetch numeric company-reported ledger or filing text evidence for requested metrics.",
        "priority": "primary",
        "analysis_intent": "missing_numeric_ledger_second_pass",
        "tickers": _required_tickers_from_plan(plan) or _string_list((state.get("query_contract") or {}).get("search_scope_tickers")),
        "years": _years_from_plan(plan),
        "filing_types": _filing_types_from_plan(plan),
        "source_family_gaps": ["primary_sec_filing"],
        "source_families": ["primary_sec_filing"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": _metric_families_from_plan(plan),
        "evidence_routes": routes,
        "operator_owners": _operator_owners_for_routes(routes),
        "route_intents": _route_intents_for_routes(routes),
        "claim_families": ["reported_financial_fact"],
        "source_available": True,
        "support_level": "insufficient",
        "reason": "numeric_metric_requested_but_runtime_ledger_rows_zero",
        "quality_gap_type": "missing_numeric_runtime_ledger",
    }


def _quality_gap_missing_relationship_ref(plan: Mapping[str, Any] | None, state: Mapping[str, Any]) -> dict[str, Any]:
    routes = ["relationship_graph"]
    return {
        "requirement_id": "quality_missing_relationship_claim_ref",
        "task_id": "quality_missing_relationship_claim_ref",
        "question_zh": "Refresh relationship graph evidence so sector-depth relationship claims cite bounded relationship refs.",
        "priority": "supporting",
        "analysis_intent": "missing_relationship_claim_ref_second_pass",
        "tickers": _required_tickers_from_plan(plan) or _string_list((state.get("query_contract") or {}).get("search_scope_tickers")),
        "years": _years_from_plan(plan),
        "filing_types": _filing_types_from_plan(plan),
        "source_family_gaps": ["relationship_graph"],
        "source_families": ["relationship_graph"],
        "metric_families": _metric_families_from_plan(plan) or ["relationship_mechanism"],
        "evidence_routes": routes,
        "operator_owners": _operator_owners_for_routes(routes),
        "route_intents": _route_intents_for_routes(routes),
        "claim_families": ["relationship_hypothesis"],
        "source_available": True,
        "support_level": "insufficient",
        "reason": "relationship_case_without_supported_relationship_ref",
        "quality_gap_type": "missing_relationship_claim_ref",
    }


def _required_tickers_missing_supported_claims(
    plan: Mapping[str, Any] | None,
    supported_claims: list[Mapping[str, Any]],
    state: Mapping[str, Any],
) -> list[str]:
    required = set(_required_tickers_from_plan(plan))
    if not required:
        query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
        required = set(_string_list(query_contract.get("focus_tickers") or query_contract.get("search_scope_tickers")))
    if not required:
        return []
    supported: set[str] = set()
    for claim in supported_claims:
        supported.update(_unique_upper(claim.get("ticker_scope") or claim.get("tickers") or claim.get("ticker")))
    return sorted(required - supported)


def _required_tickers_from_plan(plan: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(plan, Mapping):
        return []
    scope = plan.get("scope") if isinstance(plan.get("scope"), Mapping) else {}
    tickers: list[str] = []
    tickers.extend(_string_list(scope.get("focus_tickers") or scope.get("search_scope_tickers") or scope.get("universe_tickers")))
    for requirement in plan.get("requirements") or []:
        if isinstance(requirement, Mapping) and str(requirement.get("priority") or "").lower() in {"primary", "critical", ""}:
            tickers.extend(_string_list(requirement.get("tickers")))
    return _unique_upper(tickers)


def _years_from_plan(plan: Mapping[str, Any] | None) -> list[int]:
    if not isinstance(plan, Mapping):
        return []
    scope = plan.get("scope") if isinstance(plan.get("scope"), Mapping) else {}
    years: list[Any] = list(scope.get("years") or [])
    for requirement in plan.get("requirements") or []:
        if isinstance(requirement, Mapping):
            years.extend(requirement.get("years") or [])
    return _int_list(years)


def _filing_types_from_plan(plan: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(plan, Mapping):
        return []
    scope = plan.get("scope") if isinstance(plan.get("scope"), Mapping) else {}
    values: list[Any] = list(scope.get("filing_types") or [])
    for requirement in plan.get("requirements") or []:
        if isinstance(requirement, Mapping):
            values.extend(requirement.get("filing_types") or [])
    return _string_list(values)


def _metric_families_from_plan(plan: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(plan, Mapping):
        return []
    scope = plan.get("scope") if isinstance(plan.get("scope"), Mapping) else {}
    values: list[Any] = list(scope.get("metric_families") or [])
    for requirement in plan.get("requirements") or []:
        if isinstance(requirement, Mapping):
            values.extend(requirement.get("metric_families") or [])
    return _string_list(values)


def _numeric_metric_requested_without_ledger(plan: Mapping[str, Any] | None, state: Mapping[str, Any]) -> bool:
    if state.get("runtime_ledger_rows"):
        return False
    metrics = {item.lower() for item in _metric_families_from_plan(plan)}
    numeric_markers = {
        "revenue",
        "margin",
        "capex",
        "cash_flow",
        "free_cash_flow",
        "orders_backlog",
        "rpo_deferred_revenue",
        "net_interest_income",
        "net_interest_margin",
        "deposits",
        "provision_for_credit_losses",
        "net_charge_offs",
        "capital_ratio",
        "product_revenue",
        "segment_revenue",
        "gross_margin",
        "operating_margin",
        "rd_expense",
        "medical_loss_ratio",
        "production",
        "realized_price",
        "electric_load",
        "regulated_rate_base",
    }
    return bool(metrics & numeric_markers)


def _relationship_evidence_expected_without_claim_ref(
    plan: Mapping[str, Any] | None,
    supported_claims: list[Mapping[str, Any]],
    state: Mapping[str, Any],
) -> bool:
    families = set(_string_list((state.get("query_contract") or {}).get("source_tiers")))
    if isinstance(plan, Mapping):
        for requirement in plan.get("requirements") or []:
            if isinstance(requirement, Mapping):
                families.update(_string_list(requirement.get("source_families") or requirement.get("source_tiers")))
                families.update(_source_families_for_routes(_string_list(requirement.get("evidence_routes"))))
    if "relationship_graph" not in families:
        return False
    for claim in supported_claims:
        sources = set(_string_list(claim.get("source_families") or claim.get("source_family")))
        refs = _string_list(claim.get("evidence_refs") or claim.get("refs"))
        if "relationship_graph" in sources and refs:
            return False
    return True


def _coverage_tasks_from_tool_observations(
    routes: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for requirement in _requirements_for_observation_coverage(routes, plan):
        req_routes = _routes_for_requirement(routes, requirement)
        expected_routes = _expected_routes_for_requirement(requirement, req_routes)
        source_families = _source_families_for_routes(expected_routes) or _string_list(
            requirement.get("source_families") or requirement.get("source_tiers")
        )
        missing_families: list[str] = []
        route_reasons: list[str] = []
        for family in source_families:
            family_routes = [route for route in expected_routes if ROUTE_SOURCE_FAMILY.get(route) == family]
            if not family_routes:
                family_routes = _routes_for_source_families([family])
            family_success = any(
                _route_has_successful_observation(route_name, req_routes, observations)
                for route_name in family_routes
            )
            if not family_success:
                missing_families.append(family)
                route_reasons.extend(_route_gap_reasons(family_routes, req_routes, observations))
        if missing_families:
            tasks.append(_coverage_task_from_requirement_gap(requirement, missing_families, route_reasons))
    return tasks


def _requirements_for_observation_coverage(routes: list[dict[str, Any]], plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    seen: set[str] = set()
    for requirement in plan.get("requirements") or []:
        if not isinstance(requirement, Mapping):
            continue
        enriched = _enrich_evidence_requirement(requirement)
        key = _requirement_key(enriched)
        if key and key not in seen:
            seen.add(key)
        requirements.append(enriched)
    for route in routes:
        key = _route_requirement_key(route) or str(route.get("route_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        requirements.append(_requirement_from_route(route))
    return requirements


def _requirement_from_route(route: Mapping[str, Any]) -> dict[str, Any]:
    coverage = route.get("coverage_requirements") if isinstance(route.get("coverage_requirements"), Mapping) else {}
    route_name = str(route.get("retrieval_route") or "")
    source_family = ROUTE_SOURCE_FAMILY.get(route_name, "")
    requirement = {
        "requirement_id": _route_requirement_key(route) or str(route.get("route_id") or route_name),
        "task_id": str(route.get("task_id") or route.get("route_id") or route_name),
        "question_zh": str(route.get("query") or route.get("task_id") or route_name),
        "priority": str(route.get("priority") or "supporting"),
        "analysis_intent": str(route.get("analysis_intent") or route_name),
        "tickers": _string_list(route.get("tickers") or coverage.get("tickers")),
        "years": _int_list(route.get("years") or coverage.get("years")),
        "filing_types": _string_list(route.get("filing_types") or coverage.get("filing_types")),
        "source_tiers": _string_list(route.get("source_tiers") or coverage.get("source_tiers")),
        "metric_families": _string_list(route.get("metric_families") or coverage.get("metric_families")),
        "period_roles": _string_list(route.get("period_roles") or coverage.get("period_roles")),
        "evidence_routes": [route_name] if route_name else [],
        "source_families": [source_family] if source_family else [],
    }
    return _enrich_evidence_requirement(requirement)


def _routes_for_requirement(routes: list[dict[str, Any]], requirement: Mapping[str, Any]) -> list[dict[str, Any]]:
    keys = _requirement_keys(requirement)
    if not keys:
        return []
    matched = []
    for route in routes:
        route_keys = _requirement_keys(route)
        if keys & route_keys:
            matched.append(route)
    return matched


def _expected_routes_for_requirement(requirement: Mapping[str, Any], routes: list[dict[str, Any]]) -> list[str]:
    expected = _string_list(requirement.get("evidence_routes") or requirement.get("retrieval_routes"))
    expected.extend(str(route.get("retrieval_route") or "") for route in routes)
    if not expected:
        expected.extend(_routes_for_source_families(_string_list(requirement.get("source_families") or requirement.get("source_tiers"))))
    return _dedupe(expected)


def _route_has_successful_observation(route_name: str, routes: list[dict[str, Any]], observations: list[dict[str, Any]]) -> bool:
    return any(_observation_has_rows(observation) for observation in _observations_for_named_route(route_name, routes, observations))


def _observations_for_named_route(
    route_name: str,
    routes: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    route_ids = {str(route.get("route_id") or "") for route in routes if str(route.get("retrieval_route") or "") == route_name}
    route_ids.discard("")
    matched = []
    for observation in observations:
        if route_ids and str(observation.get("route_id") or "") in route_ids:
            matched.append(observation)
        elif not route_ids and str(observation.get("retrieval_route") or "") == route_name:
            matched.append(observation)
    return matched


def _observation_has_rows(observation: Mapping[str, Any]) -> bool:
    status = str(observation.get("status") or "").lower()
    if status in {"blocked", "skipped", "fail", "failed", "error"}:
        return False
    try:
        return int(observation.get("row_count") or 0) > 0
    except (TypeError, ValueError):
        return False


def _route_gap_reasons(
    route_names: list[str],
    routes: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> list[str]:
    reasons: list[str] = []
    for route_name in route_names:
        route_observations = _observations_for_named_route(route_name, routes, observations)
        if not route_observations:
            reasons.append(f"{route_name}:route_not_observed")
            continue
        for observation in route_observations:
            status = str(observation.get("status") or "")
            error = str(observation.get("error") or "")
            try:
                row_count = int(observation.get("row_count") or 0)
            except (TypeError, ValueError):
                row_count = 0
            if status.lower() in {"blocked", "skipped", "fail", "failed", "error"}:
                reasons.append(f"{route_name}:{error or status}")
            elif row_count <= 0:
                reasons.append(f"{route_name}:no_rows")
    return _dedupe(reasons)


def _coverage_task_from_requirement_gap(
    requirement: Mapping[str, Any],
    missing_families: list[str],
    route_reasons: list[str],
) -> dict[str, Any]:
    sec_families = [family for family in missing_families if family in SEC_SEARCH_SOURCE_TIERS]
    industry_families = [
        family
        for family in missing_families
        if family not in SEC_SEARCH_SOURCE_TIERS and family != "market_snapshot"
    ]
    return {
        "task_id": str(requirement.get("task_id") or requirement.get("requirement_id") or ""),
        "question_zh": str(requirement.get("question_zh") or requirement.get("question") or ""),
        "priority": str(requirement.get("priority") or "supporting"),
        "support_level": "insufficient",
        "missing_tickers": _string_list(requirement.get("tickers")),
        "missing_years": _int_list(requirement.get("years")),
        "missing_filing_types": _string_list(requirement.get("filing_types")),
        "missing_source_tiers": sec_families,
        "missing_metric_families": _string_list(requirement.get("metric_families")),
        "missing_market_fields": _string_list(requirement.get("market_fields")) if "market_snapshot" in missing_families else [],
        "missing_market_tools": _string_list(requirement.get("market_analysis_tools")) if "market_snapshot" in missing_families else [],
        "missing_industry_source_families": industry_families,
        "period_roles": _string_list(requirement.get("period_roles")),
        "must_caveat": ";".join(route_reasons[:6]) or "tool_observation_gap",
    }


def _source_gaps_from_blocked_observations(
    routes: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    route_index = {str(route.get("route_id") or ""): route for route in routes if str(route.get("route_id") or "")}
    gaps = []
    for observation in observations:
        status = str(observation.get("status") or "").lower()
        if status not in {"blocked", "skipped", "fail", "failed", "error"}:
            continue
        route = route_index.get(str(observation.get("route_id") or "")) or observation
        route_name = str(route.get("retrieval_route") or observation.get("retrieval_route") or "")
        source_family = ROUTE_SOURCE_FAMILY.get(route_name, "")
        if not source_family:
            continue
        error = str(observation.get("error") or status)
        gaps.append(
            {
                "source_family": source_family,
                "reason_code": error,
                "reason": error,
                "source_available": not _observation_error_is_non_retriable(error),
                "route_id": str(observation.get("route_id") or ""),
                "requirement_id": _route_requirement_key(route),
                "task_id": str(route.get("task_id") or ""),
            }
        )
    return gaps


def _observation_error_is_non_retriable(error: str) -> bool:
    text = str(error or "").lower()
    return any(
        marker in text
        for marker in (
            "agent_not_bounded_execute",
            "tool_not_allowed",
            "unsupported_retrieval_route",
            "ledger_store_path_unavailable",
            "duplicate_tool_call",
            "max_tool_calls",
            "budget",
        )
    )


def _requirement_key(value: Mapping[str, Any]) -> str:
    for key in ("requirement_id", "evidence_requirement_id", "parent_requirement_id", "task_id"):
        text = str(value.get(key) or "").strip()
        if text:
            return text
    return ""


def _route_requirement_key(route: Mapping[str, Any]) -> str:
    for key in ("evidence_requirement_id", "requirement_id", "parent_requirement_id", "task_id"):
        text = str(route.get(key) or "").strip()
        if text:
            return text
    return ""


def _requirement_keys(value: Mapping[str, Any]) -> set[str]:
    return {
        text
        for text in (
            str(value.get("requirement_id") or "").strip(),
            str(value.get("evidence_requirement_id") or "").strip(),
            str(value.get("parent_requirement_id") or "").strip(),
            str(value.get("task_id") or "").strip(),
        )
        if text
    }


def _evidence_requirements_by_task(plan: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    requirements = [dict(item) for item in (plan or {}).get("requirements") or [] if isinstance(item, Mapping)]
    index: dict[str, dict[str, Any]] = {}
    for requirement in requirements:
        enriched = _enrich_evidence_requirement(requirement)
        keys = [
            requirement.get("requirement_id"),
            requirement.get("evidence_requirement_id"),
            requirement.get("task_id"),
        ]
        for key in keys:
            text = str(key or "").strip()
            if text:
                index[text] = enriched
    return index


def _missing_requirement_from_coverage_task(
    task: Mapping[str, Any],
    *,
    requirement: Mapping[str, Any] | None,
    source_gaps: list[dict[str, Any]],
    available_source_families: set[str] | None,
) -> dict[str, Any]:
    req = dict(requirement or {})
    source_family_gaps = _source_family_gaps_for_task(task, req)
    evidence_routes = _routes_for_source_family_gaps(_string_list(req.get("evidence_routes") or req.get("retrieval_routes")), source_family_gaps)
    if not evidence_routes:
        evidence_routes = _routes_for_source_families(source_family_gaps)
    source_families = _source_families_for_routes(evidence_routes) or source_family_gaps
    operator_owners = _operator_owners_for_routes(evidence_routes)
    matched_source_gaps = _matching_source_gaps(source_families, source_gaps)
    source_available = _source_families_available(source_families, available_source_families) and not any(
        _source_gap_marks_unavailable(item) for item in matched_source_gaps
    )
    task_id = str(task.get("task_id") or req.get("task_id") or "")
    requirement_id = str(req.get("requirement_id") or req.get("evidence_requirement_id") or "")
    return {
        "requirement_id": requirement_id,
        "task_id": task_id,
        "question_zh": str(task.get("question_zh") or req.get("question_zh") or req.get("question") or ""),
        "priority": str(task.get("priority") or req.get("priority") or "supporting"),
        "analysis_intent": str(req.get("analysis_intent") or ""),
        "tickers": _string_list(
            task.get("missing_focus_tickers")
            or task.get("missing_tickers")
            or task.get("required_tickers")
            or req.get("tickers")
        ),
        "peer_tickers": _string_list(task.get("missing_peer_tickers") or req.get("peer_tickers")),
        "years": _int_list(task.get("missing_years") or req.get("years")),
        "filing_types": _string_list(task.get("missing_filing_types") or req.get("filing_types")),
        "source_tiers": _string_list(task.get("missing_source_tiers") or req.get("source_tiers")),
        "metric_families": _string_list(task.get("missing_metric_families") or task.get("required_metric_families") or req.get("metric_families")),
        "period_roles": _string_list(task.get("period_roles") or req.get("period_roles")),
        "market_fields": _string_list(task.get("missing_market_fields") or req.get("market_fields")),
        "market_analysis_tools": _string_list(task.get("missing_market_tools") or req.get("market_analysis_tools")),
        "industry_source_families": _string_list(task.get("missing_industry_source_families") or []),
        "source_family_gaps": source_family_gaps,
        "source_families": source_families,
        "operator_owners": operator_owners,
        "evidence_routes": evidence_routes,
        "route_intents": _route_intents_for_routes(evidence_routes),
        "claim_families": _string_list(req.get("claim_families")) or _claim_families_for_requirement({"evidence_routes": evidence_routes}),
        "source_available": source_available,
        "matched_source_gaps": matched_source_gaps,
        "support_level": str(task.get("support_level") or ""),
        "reason": str(task.get("must_caveat") or "coverage_gap"),
    }


def _second_pass_request_from_missing(missing: Mapping[str, Any], index: int) -> dict[str, Any]:
    parent_requirement_id = str(missing.get("requirement_id") or "")
    task_id = str(missing.get("task_id") or f"task_{index}")
    request_stem = parent_requirement_id or task_id or f"req_{index}"
    request_id = f"second_pass_{request_stem}_{index}"
    coverage_requirements = {
        "tickers": _string_list(missing.get("tickers")),
        "years": _int_list(missing.get("years")),
        "filing_types": _string_list(missing.get("filing_types")),
        "source_tiers": _string_list(missing.get("source_tiers")),
        "metric_families": _string_list(missing.get("metric_families")),
        "period_roles": _string_list(missing.get("period_roles")),
        "market_fields": _string_list(missing.get("market_fields")),
        "market_analysis_tools": _string_list(missing.get("market_analysis_tools")),
    }
    return {
        "request_id": request_id,
        "requirement_id": f"{request_stem}_second_pass_{index}",
        "parent_requirement_id": parent_requirement_id,
        "task_id": task_id,
        "question_zh": str(missing.get("question_zh") or ""),
        "priority": str(missing.get("priority") or "supporting"),
        "analysis_intent": str(missing.get("analysis_intent") or "coverage_gap_second_pass"),
        "tickers": coverage_requirements["tickers"],
        "peer_tickers": _string_list(missing.get("peer_tickers")),
        "years": coverage_requirements["years"],
        "filing_types": coverage_requirements["filing_types"],
        "source_tiers": coverage_requirements["source_tiers"],
        "metric_families": coverage_requirements["metric_families"],
        "period_roles": coverage_requirements["period_roles"],
        "market_fields": coverage_requirements["market_fields"],
        "source_family_gaps": _string_list(missing.get("source_family_gaps")),
        "source_families": _string_list(missing.get("source_families")),
        "operator_owners": _string_list(missing.get("operator_owners")),
        "evidence_routes": _string_list(missing.get("evidence_routes")),
        "route_intents": [dict(item) for item in missing.get("route_intents") or [] if isinstance(item, Mapping)],
        "claim_families": _string_list(missing.get("claim_families")),
        "source_available": bool(missing.get("source_available", True)),
        "coverage_requirements": coverage_requirements,
        "trigger": "coverage_gap",
        "compile_policy": "deterministic_compiler_required",
        "planner_boundary": "business_need_only_no_physical_paths",
    }


def _second_pass_request_as_requirement(request: Mapping[str, Any], index: int) -> dict[str, Any]:
    coverage = request.get("coverage_requirements") if isinstance(request.get("coverage_requirements"), Mapping) else {}
    return {
        "requirement_id": str(request.get("requirement_id") or request.get("request_id") or f"second_pass_req_{index}"),
        "parent_requirement_id": str(request.get("parent_requirement_id") or ""),
        "request_id": str(request.get("request_id") or f"second_pass_{index}"),
        "task_id": str(request.get("task_id") or request.get("request_id") or f"second_pass_task_{index}"),
        "question_zh": str(request.get("question_zh") or request.get("question") or ""),
        "priority": str(request.get("priority") or "supporting"),
        "analysis_intent": str(request.get("analysis_intent") or "coverage_gap_second_pass"),
        "tickers": _string_list(request.get("tickers") or coverage.get("tickers")),
        "peer_tickers": _string_list(request.get("peer_tickers")),
        "years": _int_list(request.get("years") or coverage.get("years")),
        "filing_types": _string_list(request.get("filing_types") or coverage.get("filing_types")),
        "source_tiers": _string_list(request.get("source_tiers") or coverage.get("source_tiers")),
        "metric_families": _string_list(request.get("metric_families") or coverage.get("metric_families")),
        "period_roles": _string_list(request.get("period_roles") or coverage.get("period_roles")),
        "evidence_routes": _string_list(request.get("evidence_routes") or request.get("retrieval_routes")),
        "market_fields": _string_list(request.get("market_fields") or coverage.get("market_fields")),
        "coverage_requirements": dict(coverage),
        "candidate_budget": int(request.get("candidate_budget") or 0),
        "rerank_budget": int(request.get("rerank_budget") or 0),
        "second_pass_policy": {"enabled": True, "max_passes": 1, "trigger": "reflection_coverage_gap", "external_gap_behavior": "report_boundary_without_autosearch"},
        "source_family_gaps": _string_list(request.get("source_family_gaps") or request.get("source_families")),
        "source_families": _string_list(request.get("source_families")),
        "operator_owners": _string_list(request.get("operator_owners")),
    }


def _query_contract_with_plan_scope(query_contract: Mapping[str, Any], base_evidence_requirement_plan: Mapping[str, Any]) -> dict[str, Any]:
    contract = dict(query_contract or {})
    scope = base_evidence_requirement_plan.get("scope") if isinstance(base_evidence_requirement_plan.get("scope"), Mapping) else {}
    focus_tickers = _string_list(contract.get("focus_tickers") or (contract.get("scope") or {}).get("focus_tickers") or scope.get("focus_tickers"))
    search_scope_tickers = _string_list(
        contract.get("search_scope_tickers")
        or (contract.get("scope") or {}).get("universe_tickers")
        or scope.get("search_scope_tickers")
        or scope.get("universe_tickers")
        or focus_tickers
    )
    years = _int_list(contract.get("years") or (contract.get("scope") or {}).get("years") or scope.get("years"))
    filing_types = _string_list(contract.get("filing_types") or (contract.get("scope") or {}).get("filing_types") or scope.get("filing_types"))
    source_tiers = _string_list(contract.get("source_tiers") or (contract.get("scope") or {}).get("source_tiers") or scope.get("source_tiers"))
    if focus_tickers:
        contract["focus_tickers"] = focus_tickers
    if search_scope_tickers:
        contract["search_scope_tickers"] = search_scope_tickers
    if years:
        contract["years"] = years
    if filing_types:
        contract["filing_types"] = filing_types
    if source_tiers:
        contract["source_tiers"] = source_tiers
    return contract


def _source_family_gaps_for_task(task: Mapping[str, Any], requirement: Mapping[str, Any]) -> list[str]:
    families: list[str] = []
    families.extend(_string_list(task.get("missing_source_tiers")))
    if _string_list(task.get("missing_market_fields")) or _string_list(task.get("missing_market_tools")):
        families.append("market_snapshot")
    families.extend(_string_list(task.get("missing_industry_source_families")))
    if not families:
        families.extend(_string_list(requirement.get("source_families") or requirement.get("planner_source_families")))
    return _dedupe(families)


def _routes_for_source_family_gaps(routes: list[str], source_family_gaps: list[str]) -> list[str]:
    if not routes:
        return []
    gap_set = set(source_family_gaps)
    if not gap_set:
        return routes
    filtered = [route for route in routes if ROUTE_SOURCE_FAMILY.get(route) in gap_set]
    return filtered or routes


def _routes_for_source_families(source_families: list[str]) -> list[str]:
    source_set = set(source_families)
    routes: list[str] = []
    if "primary_sec_filing" in source_set:
        routes.extend(["ledger_first", "filing_text"])
    if "company_authored_unaudited_sec_filing" in source_set:
        routes.append("8k_commentary")
    if "market_snapshot" in source_set:
        routes.append("market_snapshot")
    if "industry_snapshot" in source_set:
        routes.append("industry_snapshot")
    if "relationship_graph" in source_set:
        routes.append("relationship_graph")
    return _dedupe(routes)


def _compile_relationship_requirement_for_retrieval(
    requirement: Mapping[str, Any],
    *,
    years: list[int],
    filing_types: list[str],
    source_tiers: list[str],
) -> dict[str, Any]:
    req = dict(requirement)
    source_families = _string_list(req.get("source_families") or req.get("evidence_source_needed"))
    executable_sources = [family for family in source_families if family != "relationship_graph"]
    if not executable_sources:
        executable_sources = ["primary_sec_filing"]
    sec_source_tiers = [tier for tier in source_tiers if tier in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}]
    routes = _routes_for_source_families(executable_sources)
    req["source_families"] = source_families
    req["evidence_routes"] = routes
    req["source_tiers"] = _dedupe(
        [
            *[family for family in executable_sources if family in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}],
            *sec_source_tiers,
        ]
    )
    req["years"] = _int_list(req.get("years")) or years
    req["filing_types"] = _string_list(req.get("filing_types")) or filing_types
    req["metric_families"] = _string_list(req.get("metric_families")) or ["relationship_mechanism"]
    req["planner_boundary"] = "business_need_only_routes_compiled_deterministically"
    return _enrich_evidence_requirement(req)


def _source_families_for_routes(routes: list[str]) -> list[str]:
    return _dedupe([ROUTE_SOURCE_FAMILY.get(route, "") for route in routes])


def _operator_owners_for_routes(routes: list[str]) -> list[str]:
    return _dedupe([ROUTE_OPERATOR_TOOL.get(route, ("", ""))[0] for route in routes])


def _route_intents_for_routes(routes: list[str]) -> list[dict[str, Any]]:
    intents = []
    for route in routes:
        source_family = ROUTE_SOURCE_FAMILY.get(route, "")
        owner, tool_name = ROUTE_OPERATOR_TOOL.get(route, ("", ""))
        intents.append(
            {
                "evidence_route": route,
                "source_family": source_family,
                "operator_owner": owner,
                "tool_name": tool_name,
                "route_authority": "deterministic_compiler",
            }
        )
    return intents


def _matching_source_gaps(source_families: list[str], source_gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not source_families:
        return []
    source_set = set(source_families)
    matches = []
    for gap in source_gaps:
        families = _string_list(gap.get("source_family") or gap.get("source_families") or gap.get("source_tier") or gap.get("source_tiers"))
        if source_set & set(families):
            matches.append(_sanitize_payload(gap))
    return matches


def _source_families_available(source_families: list[str], available_source_families: set[str] | None) -> bool:
    if available_source_families is None or not source_families:
        return True
    return set(source_families).issubset(available_source_families)


def _source_gap_marks_unavailable(gap: Mapping[str, Any]) -> bool:
    for key in ("source_available", "available", "exists"):
        if key in gap and gap.get(key) is False:
            return True
    reason = str(gap.get("reason") or gap.get("reason_code") or "").lower()
    return any(marker in reason for marker in ("not_available", "unavailable", "missing_source", "not_in_inventory"))


def _source_family_gap_items(missing: Mapping[str, Any]) -> list[dict[str, Any]]:
    requirement_id = str(missing.get("requirement_id") or "")
    task_id = str(missing.get("task_id") or "")
    return [
        {
            "requirement_id": requirement_id,
            "task_id": task_id,
            "source_family": family,
            "source_available": bool(missing.get("source_available", True)),
        }
        for family in _string_list(missing.get("source_family_gaps") or missing.get("source_families"))
    ]


def _rows_from_result(tool_name: str, result: Mapping[str, Any]) -> list[dict[str, Any]]:
    keys = {
        "sec_search_filings": "context_rows",
        "sec_query_exact_value_ledger": "ledger_rows",
        "market_get_snapshot": "market_rows",
        "industry_get_snapshot": "industry_rows",
        "relationship_graph_lookup": "relationship_rows",
    }
    rows = result.get(keys.get(tool_name, "rows")) or []
    return [dict(item) for item in rows if isinstance(item, Mapping)]


def _source_gaps_from_result(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    gaps = []
    for key in ("source_gaps", "field_gaps", "source_family_gaps", "missing_dimensions"):
        gaps.extend(dict(item) for item in result.get(key) or [] if isinstance(item, Mapping))
    return gaps


def _enrich_evidence_requirement(requirement: Mapping[str, Any]) -> dict[str, Any]:
    req = dict(requirement)
    planner_source_families = _string_list(req.get("source_families") or req.get("source_family"))
    planner_operator_owners = _string_list(req.get("operator_owners") or req.get("operator_owner"))
    route_intents = []
    source_families: list[str] = []
    operator_owners: list[str] = []
    for route in _string_list(req.get("evidence_routes") or req.get("retrieval_routes")):
        source_family = ROUTE_SOURCE_FAMILY.get(route, "")
        owner, tool_name = ROUTE_OPERATOR_TOOL.get(route, ("", ""))
        if source_family:
            source_families.append(source_family)
        if owner:
            operator_owners.append(owner)
        route_intents.append(
            {
                "evidence_route": route,
                "source_family": source_family,
                "operator_owner": owner,
                "tool_name": tool_name,
                "route_authority": "deterministic_compiler",
            }
        )
    req["route_intents"] = route_intents
    if planner_source_families:
        req["planner_source_families"] = planner_source_families
    if planner_operator_owners:
        req["planner_operator_owners"] = planner_operator_owners
    req["source_families"] = _dedupe(source_families)
    req["operator_owners"] = _dedupe(operator_owners)
    req["claim_families"] = _claim_families_for_requirement(req)
    req["planner_boundary"] = "business_need_only_no_physical_paths"
    return req


def _claim_families_for_requirement(requirement: Mapping[str, Any]) -> list[str]:
    routes = set(_string_list(requirement.get("evidence_routes") or requirement.get("retrieval_routes")))
    families: list[str] = []
    if routes & {"ledger_first", "filing_text"}:
        families.append("reported_financial_fact")
    if "8k_commentary" in routes:
        families.append("management_commentary")
    if "risk_text" in routes:
        families.append("risk_or_counterevidence")
    if "market_snapshot" in routes:
        families.append("market_or_valuation_context")
    if "industry_snapshot" in routes:
        families.append("industry_context_only")
    if "relationship_graph" in routes:
        families.append("relationship_hypothesis")
    if not families:
        families.append(str(requirement.get("analysis_intent") or "business_observation"))
    return _dedupe(families)


def _bounded_rows_for_agent_data_view(agent_id: str, state: Mapping[str, Any]) -> list[dict[str, Any]]:
    max_rows = _data_view_max_rows_for_agent(agent_id, state)
    rows: list[dict[str, Any]] = []
    if agent_id == "fundamental_analyst":
        rows.extend(_row_dicts(state.get("runtime_ledger_rows")))
        rows.extend(
            row
            for row in _row_dicts(state.get("context_rows"))
            if _row_source_family(row) in {"", "primary_sec_filing", "company_authored_unaudited_sec_filing"}
        )
    elif agent_id == "market_valuation_analyst":
        rows.extend(_row_dicts(state.get("market_snapshot_rows")))
        rows.extend(row for row in _row_dicts(state.get("context_rows")) if _row_source_family(row) == "market_snapshot")
    elif agent_id == "industry_supply_chain_analyst":
        rows.extend(_row_dicts(state.get("industry_snapshot_rows")))
        rows.extend(row for row in _row_dicts(state.get("context_rows")) if _row_source_family(row) in {"industry_snapshot", "relationship_graph"})
        rows.extend(_relationship_rows_from_state(state))
        rows = _balanced_industry_relationship_rows(
            rows,
            max_rows=max_rows,
            min_relationship_rows=_industry_relationship_min_rows(state, max_rows=max_rows),
        )
    elif agent_id == "memo_writer":
        rows = []
    elif agent_id in {"risk_counterevidence_analyst", "verifier", "coverage_reflection", "judgment_plan_aggregator"}:
        rows.extend(_row_dicts(state.get("runtime_ledger_rows")))
        rows.extend(_row_dicts(state.get("context_rows")))
        rows.extend(_row_dicts(state.get("market_snapshot_rows")))
        rows.extend(_row_dicts(state.get("industry_snapshot_rows")))
        if agent_id != "risk_counterevidence_analyst":
            rows.extend(_relationship_rows_from_state(state))
    else:
        rows.extend(_row_dicts(state.get("context_rows")))
    if agent_id == "risk_counterevidence_analyst":
        rows = _balanced_rows_by_source(
            rows,
            source_order=[
                "primary_sec_filing",
                "company_authored_unaudited_sec_filing",
                "market_snapshot",
                "industry_snapshot",
                "run_artifact",
                "",
            ],
            max_rows=max_rows,
        )
    return [_bounded_row(row, index) for index, row in enumerate(rows[:max_rows], start=1)]


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
        "source_family": _row_source_family(row),
        "ticker": str(row.get("ticker") or row.get("company") or ""),
        "period_role": str(row.get("period_role") or row.get("period") or ""),
        "metric": str(row.get("metric") or row.get("metric_name") or row.get("field") or ""),
        "value": _scalar_or_blank(row.get("value") or row.get("numeric_value") or row.get("display_value")),
        "summary": _truncate(str(row.get("summary") or row.get("text") or row.get("snippet") or row.get("description") or ""), 900),
        "snapshot_id": str(row.get("snapshot_id") or ""),
        "as_of_date": str(row.get("as_of_date") or ""),
    }
    if _row_source_family(row) == "relationship_graph":
        bounded.update(
            {
                "edge_schema_version": str(row.get("edge_schema_version") or "sec_agent_relationship_edge_v0.2"),
                "edge_id": str(row.get("edge_id") or ""),
                "related_ticker": str(row.get("related_ticker") or row.get("to_ticker") or ""),
                "from_ticker": str(row.get("from_ticker") or row.get("ticker") or ""),
                "to_ticker": str(row.get("to_ticker") or row.get("related_ticker") or ""),
                "relationship_type": str(row.get("relationship_type") or row.get("metric") or ""),
                "direction": str(row.get("direction") or row.get("edge_direction") or ""),
                "mechanism": str(row.get("mechanism") or ""),
                "metric_links": _string_list(row.get("metric_links") or row.get("metrics_to_check")),
                "source_pack_id": str(row.get("source_pack_id") or ""),
                "claim_scope": "scope_or_hypothesis_only",
            }
        )
    return bounded


def _relationship_rows(plan: Any) -> list[dict[str, Any]]:
    if not isinstance(plan, Mapping):
        return []
    rows = []
    for index, relationship in enumerate(plan.get("relationships") or [], start=1):
        if not isinstance(relationship, Mapping):
            continue
        refs = _string_list(relationship.get("evidence_refs") or relationship.get("refs"))
        rows.append(
            {
                "evidence_ref": ",".join(refs) or f"relationship_ref_{index}",
                "edge_schema_version": relationship.get("edge_schema_version") or "sec_agent_relationship_edge_v0.2",
                "edge_id": relationship.get("edge_id") or "",
                "source_family": "relationship_graph",
                "ticker": relationship.get("ticker") or "",
                "related_ticker": relationship.get("related_ticker") or "",
                "from_ticker": relationship.get("from_ticker") or relationship.get("ticker") or "",
                "to_ticker": relationship.get("to_ticker") or relationship.get("related_ticker") or "",
                "metric": relationship.get("relationship_type") or relationship.get("type") or "relationship",
                "relationship_type": relationship.get("relationship_type") or relationship.get("type") or "relationship",
                "direction": relationship.get("direction") or relationship.get("edge_direction") or "",
                "mechanism": relationship.get("mechanism") or relationship.get("financial_link_type") or "",
                "metric_links": relationship.get("metric_links") or relationship.get("metrics_to_check") or [],
                "source_pack_id": relationship.get("source_pack_id") or "",
                "summary": relationship.get("inclusion_rationale")
                or relationship.get("notes")
                or relationship.get("reason")
                or relationship.get("relationship_scope_rationale")
                or "",
            }
        )
    return rows


def _relationship_rows_from_state(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(_relationship_rows(state.get("universe_relationship_plan")))
    lookup = state.get("relationship_graph_observation") if isinstance(state.get("relationship_graph_observation"), Mapping) else {}
    rows.extend(_relationship_observation_rows(lookup))
    return _dedupe_relationship_rows(rows)


def _relationship_observation_rows(lookup: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for index, row in enumerate(lookup.get("relationship_rows") or [], start=1):
        if not isinstance(row, Mapping):
            continue
        clean = dict(row)
        clean["source_family"] = "relationship_graph"
        if not clean.get("evidence_ref"):
            clean["evidence_ref"] = f"relationship_lookup_ref_{index}"
        rows.append(clean)
    if rows:
        return rows
    return _relationship_rows({"relationships": lookup.get("relationships") or []})


def _dedupe_relationship_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = (
            str(row.get("evidence_ref") or ""),
            str(row.get("ticker") or ""),
            str(row.get("related_ticker") or ""),
            str(row.get("metric") or row.get("relationship_type") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _balanced_rows_by_source(rows: list[dict[str, Any]], *, source_order: list[str], max_rows: int) -> list[dict[str, Any]]:
    if len(rows) <= max_rows:
        return rows
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        buckets.setdefault(_row_source_family(row), []).append(row)
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    while len(selected) < max_rows:
        added = False
        for family in source_order:
            bucket = buckets.get(family) or []
            while bucket and id(bucket[0]) in selected_ids:
                bucket.pop(0)
            if not bucket:
                continue
            item = bucket.pop(0)
            selected.append(item)
            selected_ids.add(id(item))
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


def _balanced_industry_relationship_rows(
    rows: list[dict[str, Any]],
    *,
    max_rows: int,
    min_relationship_rows: int,
) -> list[dict[str, Any]]:
    if len(rows) <= max_rows:
        return rows
    selected = _balanced_rows_by_source(
        rows,
        source_order=[
            "industry_snapshot",
            "relationship_graph",
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "",
        ],
        max_rows=max_rows,
    )
    relationship_rows = [row for row in rows if _row_source_family(row) == "relationship_graph"]
    required_count = min(max(0, min_relationship_rows), len(relationship_rows), max_rows)
    selected_relationship_count = sum(1 for row in selected if _row_source_family(row) == "relationship_graph")
    if selected_relationship_count >= required_count:
        return selected

    selected_ids = {id(row) for row in selected}
    replacement_indexes = [
        index
        for index in range(len(selected) - 1, -1, -1)
        if _row_source_family(selected[index]) != "relationship_graph"
    ]
    for relationship_row in relationship_rows:
        if selected_relationship_count >= required_count or not replacement_indexes:
            break
        if id(relationship_row) in selected_ids:
            continue
        replacement_index = replacement_indexes.pop(0)
        selected_ids.discard(id(selected[replacement_index]))
        selected[replacement_index] = relationship_row
        selected_ids.add(id(relationship_row))
        selected_relationship_count += 1
    return selected


def _state_summary_for_data_view(state: Mapping[str, Any]) -> dict[str, Any]:
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    evidence_plan = state.get("evidence_requirement_plan") if isinstance(state.get("evidence_requirement_plan"), Mapping) else {}
    return {
        "run_id": state.get("run_id") or "",
        "execution_mode": _execution_mode_from_state(state),
        "allowed_source_families": list(activation.get("allowed_source_families") or []),
        "evidence_requirement_count": len(evidence_plan.get("requirements") or []) if isinstance(evidence_plan, Mapping) else 0,
        "context_row_count": len(state.get("context_rows") or []),
        "ledger_row_count": len(state.get("runtime_ledger_rows") or []),
        "market_row_count": len(state.get("market_snapshot_rows") or []),
        "industry_row_count": len(state.get("industry_snapshot_rows") or []),
        "default_bounded_evidence_row_budget": _data_view_max_rows_for_mode(_execution_mode_from_state(state)),
        "relationship_summary_row_budget": _relationship_summary_max_rows(state),
    }


def _artifact_ref_summary(value: Any) -> list[dict[str, Any]]:
    refs = []
    if isinstance(value, Mapping):
        iterator = value.items()
    elif isinstance(value, list):
        iterator = ((item.get("artifact_id") or item.get("key") or f"artifact_{index}", item) for index, item in enumerate(value, start=1) if isinstance(item, Mapping))
    else:
        iterator = []
    for key, item in iterator:
        payload = dict(item) if isinstance(item, Mapping) else {"path": str(item or "")}
        refs.append(
            {
                "artifact_id": str(payload.get("artifact_id") or payload.get("key") or key),
                "schema_version": str(payload.get("schema_version") or ""),
                "row_count": payload.get("row_count"),
                "digest": str(payload.get("digest") or payload.get("output_artifact_digest") or ""),
                "path_boundary": "path_not_exposed_in_agent_data_view",
            }
        )
    return refs


def _coverage_summary_view(state: Mapping[str, Any]) -> dict[str, Any]:
    coverage = state.get("coverage_matrix") if isinstance(state.get("coverage_matrix"), Mapping) else {}
    reflection = state.get("multi_agent_reflection_report") if isinstance(state.get("multi_agent_reflection_report"), Mapping) else {}
    sufficiency = state.get("evidence_sufficiency_report") if isinstance(state.get("evidence_sufficiency_report"), Mapping) else {}
    return {
        "coverage_summary": _sanitize_payload(coverage.get("summary") if isinstance(coverage.get("summary"), Mapping) else {}),
        "sufficiency_level": reflection.get("sufficiency_level") or sufficiency.get("sufficiency_level") or "",
        "missing_requirements": _sanitize_payload(reflection.get("missing_requirements") or sufficiency.get("missing_requirements") or []),
        "source_gaps": _sanitize_payload(state.get("source_gaps") or []),
        "bounded_answer_allowed": bool(reflection.get("bounded_answer_allowed") or sufficiency.get("bounded_answer_allowed") or state.get("bounded_answer_allowed")),
    }


def _tool_trace_summary_view(state: Mapping[str, Any]) -> dict[str, Any]:
    ledger = state.get("tool_call_ledger") if isinstance(state.get("tool_call_ledger"), Mapping) else {}
    records = [dict(item) for item in ledger.get("records") or [] if isinstance(item, Mapping)]
    observations = [dict(item) for item in state.get("tool_observations") or [] if isinstance(item, Mapping)]
    return {
        "tool_calls": [
            {
                "agent_id": record.get("agent_id") or "",
                "tool_name": record.get("tool_name") or "",
                "status": record.get("status") or "",
                "row_count": int(record.get("row_count") or 0),
                "source_gap_count": int(record.get("source_gap_count") or 0),
                "coverage_delta": record.get("coverage_delta") or {},
                "elapsed_ms": int(record.get("elapsed_ms") or 0),
            }
            for record in records
        ],
        "tool_observations": [
            {
                "agent_id": item.get("agent_id") or "",
                "tool_name": item.get("tool_name") or "",
                "status": item.get("status") or "",
                "row_count": int(item.get("row_count") or 0),
                "source_gap_count": int(item.get("source_gap_count") or 0),
                "boundary": item.get("boundary") or {},
            }
            for item in observations
        ],
        "loop_break_reason": ledger.get("loop_break_reason") or state.get("loop_break_reason") or "",
    }


def _relationship_summary_view(state: Mapping[str, Any]) -> dict[str, Any]:
    plan = state.get("universe_relationship_plan") if isinstance(state.get("universe_relationship_plan"), Mapping) else {}
    relationship_rows = _relationship_rows_from_state(state)
    max_rows = _relationship_summary_max_rows(state)
    return {
        "scope_mode": plan.get("scope_mode") or "",
        "focus_tickers": list(plan.get("focus_tickers") or []),
        "expanded_tickers": list(plan.get("expanded_tickers") or []),
        "relationship_scope_rationale": str(plan.get("relationship_scope_rationale") or "")[:500],
        "relationships": [_bounded_row(row, index) for index, row in enumerate(relationship_rows[:max_rows], start=1)],
    }


def _data_view_input_budget(agent_id: str, state: Mapping[str, Any]) -> dict[str, Any]:
    max_rows = _data_view_max_rows_for_agent(agent_id, state)
    priority = _agent_priority_from_state(agent_id, state)
    payload = {
        "execution_mode": _execution_mode_from_state(state),
        "agent_priority": priority,
        "bounded_evidence_row_budget": max_rows,
        "relationship_summary_row_budget": _relationship_summary_max_rows(state),
        "budget_policy": "execution_mode_and_priority_tiered_bounded_rows_only",
    }
    if agent_id == "industry_supply_chain_analyst":
        payload["min_relationship_rows"] = _industry_relationship_min_rows(state, max_rows=max_rows)
    if agent_id == "market_valuation_analyst":
        payload["market_snapshot_policy"] = "compact_rows_preserve_snapshot_id_and_as_of_date"
    if agent_id == "risk_counterevidence_analyst":
        payload["selection_policy"] = "source_balanced_without_relationship_graph"
    return payload


def _data_view_max_rows_for_agent(agent_id: str, state: Mapping[str, Any]) -> int:
    mode = _execution_mode_from_state(state)
    default = _data_view_max_rows_for_mode(mode)
    priority = _agent_priority_from_state(agent_id, state)
    if priority == "supporting":
        if mode == "deep_research":
            default = min(
                default,
                _positive_int_env(
                    "AGENT_DATA_VIEW_SUPPORTING_DEEP_RESEARCH_MAX_ROWS",
                    default=AGENT_DATA_VIEW_SUPPORTING_DEEP_RESEARCH_MAX_ROWS,
                ),
            )
        elif mode == "standard_memo":
            default = min(
                default,
                _positive_int_env(
                    "AGENT_DATA_VIEW_SUPPORTING_STANDARD_MEMO_MAX_ROWS",
                    default=AGENT_DATA_VIEW_SUPPORTING_STANDARD_MEMO_MAX_ROWS,
                ),
            )
    elif priority == "conditional":
        default = min(
            default,
            _positive_int_env(
                "AGENT_DATA_VIEW_CONDITIONAL_MAX_ROWS",
                default=AGENT_DATA_VIEW_CONDITIONAL_MAX_ROWS,
            ),
        )
    elif priority == "low":
        default = min(
            default,
            _positive_int_env("AGENT_DATA_VIEW_LOW_MAX_ROWS", default=AGENT_DATA_VIEW_LOW_MAX_ROWS),
        )
    if agent_id == "market_valuation_analyst":
        market_default = min(default, 16)
        return _positive_int_env("AGENT_DATA_VIEW_MARKET_MAX_ROWS", default=market_default)
    return default


def _agent_priority_from_state(agent_id: str, state: Mapping[str, Any]) -> str:
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    priorities = activation.get("agent_priorities") if isinstance(activation.get("agent_priorities"), Mapping) else {}
    priority = str(priorities.get(agent_id) or "primary").strip().lower()
    return priority if priority in {"primary", "supporting", "conditional", "low"} else "primary"


def _data_view_max_rows_for_mode(mode: str) -> int:
    normalized = str(mode or "").strip()
    if normalized == "deep_research":
        return _positive_int_env("AGENT_DATA_VIEW_DEEP_RESEARCH_MAX_ROWS", default=AGENT_DATA_VIEW_DEEP_RESEARCH_MAX_ROWS)
    if normalized == "standard_memo":
        return _positive_int_env("AGENT_DATA_VIEW_STANDARD_MEMO_MAX_ROWS", default=AGENT_DATA_VIEW_STANDARD_MEMO_MAX_ROWS)
    return _positive_int_env("AGENT_DATA_VIEW_MAX_ROWS", default=AGENT_DATA_VIEW_MAX_ROWS)


def _industry_relationship_min_rows(state: Mapping[str, Any], *, max_rows: int) -> int:
    mode = _execution_mode_from_state(state)
    if mode == "deep_research":
        default = INDUSTRY_RELATIONSHIP_DEEP_MIN_ROWS
        env_name = "INDUSTRY_RELATIONSHIP_DEEP_MIN_ROWS"
    elif mode == "standard_memo":
        default = INDUSTRY_RELATIONSHIP_STANDARD_MIN_ROWS
        env_name = "INDUSTRY_RELATIONSHIP_STANDARD_MIN_ROWS"
    else:
        default = INDUSTRY_RELATIONSHIP_MIN_ROWS
        env_name = "INDUSTRY_RELATIONSHIP_MIN_ROWS"
    return min(max_rows, _positive_int_env(env_name, default=default))


def _relationship_summary_max_rows(state: Mapping[str, Any]) -> int:
    if _execution_mode_from_state(state) == "deep_research":
        return _positive_int_env(
            "RELATIONSHIP_SUMMARY_DEEP_RESEARCH_MAX_ROWS",
            default=RELATIONSHIP_SUMMARY_DEEP_RESEARCH_MAX_ROWS,
        )
    return _positive_int_env("RELATIONSHIP_SUMMARY_MAX_ROWS", default=RELATIONSHIP_SUMMARY_MAX_ROWS)


def _execution_mode_from_state(state: Mapping[str, Any]) -> str:
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    return str(activation.get("execution_mode") or state.get("execution_mode") or "").strip()


def _positive_int_env(name: str, *, default: int) -> int:
    try:
        value = int(os.environ.get(name, ""))
    except (TypeError, ValueError):
        value = default
    return max(1, value)


def _verified_summary_view(state: Mapping[str, Any]) -> dict[str, Any]:
    judgment = state.get("judgment_plan") if isinstance(state.get("judgment_plan"), Mapping) else {}
    verification = state.get("specialist_verification") if isinstance(state.get("specialist_verification"), Mapping) else {}
    claim_verification = state.get("claim_verification") if isinstance(state.get("claim_verification"), Mapping) else {}
    return {
        "judgment_plan": _sanitize_payload(judgment),
        "specialist_verification": _sanitize_payload(verification),
        "claim_verification": _sanitize_payload(claim_verification),
        "memo_constraints": _sanitize_payload(judgment.get("memo_constraints") or {}),
        "memo_writer_allowed": bool(verification.get("memo_writer_allowed", True)),
    }


def _row_dicts(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, Mapping)]


def _row_source_family(row: Mapping[str, Any]) -> str:
    family = str(row.get("source_family") or "").strip()
    tier = str(row.get("source_tier") or "").strip()
    if tier == "industry_snapshot" or family.startswith("industry_"):
        return "industry_snapshot"
    return family or tier


def _sanitize_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        clean = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_private_or_raw_key(key_text):
                continue
            clean[key_text] = _sanitize_payload(item)
        return clean
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, str):
        return "" if _looks_like_private_path(value) else value
    return value


def _is_private_or_raw_key(key: str) -> bool:
    lowered = key.lower()
    if any(marker in lowered for marker in ("private_path", "raw_path", "raw_text", "full_text", "absolute_path")):
        return True
    if lowered.endswith("_path") or lowered in {"path", "local_path", "filesystem_path"}:
        return True
    return False


def _looks_like_private_path(value: str) -> bool:
    text = value.replace("\\", "/").lower()
    return any(marker in text for marker in ("data/raw_private", "data/processed_private", "data/indexes", "/.env", "begin private key"))


def _scalar_or_blank(value: Any) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        return ""
    return str(value or "")


def _truncate(text: str, limit: int) -> str:
    value = str(text or "")
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def _slug(value: Any) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or ""))
    return "_".join(part for part in slug.split("_") if part)[:96] or "route"


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


def _unique_upper(value: Any) -> list[str]:
    return [item.upper() for item in _string_list(value)]


def _int_list(value: Any) -> list[int]:
    if value is None:
        items: list[Any] = []
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    result: list[int] = []
    seen: set[int] = set()
    for item in items:
        try:
            number = int(item)
        except (TypeError, ValueError):
            continue
        if number in seen:
            continue
        seen.add(number)
        result.append(number)
    return result


def _bounded_positive_int(value: Any, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number >= 0 else default


def _positive_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


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


def _first_artifact_digest(refs: list[dict[str, Any]]) -> str:
    for ref in refs:
        digest = str(ref.get("digest") or "")
        if digest:
            return digest
    return ""


def _observation(
    route: Mapping[str, Any],
    agent_id: str,
    tool_name: str,
    status: str,
    *,
    error: str = "",
    arguments: Mapping[str, Any] | None = None,
    row_count: int = 0,
    source_gap_count: int = 0,
    boundary: Mapping[str, Any] | None = None,
    runtime_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "route_id": route.get("route_id") or "",
        "retrieval_route": route.get("retrieval_route") or "",
        "agent_id": agent_id,
        "tool_name": tool_name,
        "status": status,
        "error": error,
        "arguments": dict(arguments or {}),
        "row_count": row_count,
        "source_gap_count": source_gap_count,
        "boundary": dict(boundary or {}),
        "runtime_summary": dict(runtime_summary or {}),
    }


def _dry_run_result(tool_name: str, route: Mapping[str, Any]) -> dict[str, Any]:
    row = {"route_id": route.get("route_id") or "", "retrieval_route": route.get("retrieval_route") or ""}
    if tool_name == "sec_search_filings":
        return {"status": "dry_run", "context_rows": [row], "artifact_refs": []}
    if tool_name == "sec_query_exact_value_ledger":
        return {"status": "dry_run", "ledger_rows": [row], "artifact_refs": []}
    if tool_name == "market_get_snapshot":
        return {"status": "dry_run", "market_rows": [row], "snapshot_id": "dry_run", "as_of_date": "dry_run", "artifact_refs": []}
    if tool_name == "industry_get_snapshot":
        return {"status": "dry_run", "industry_rows": [row], "artifact_refs": []}
    return {"status": "dry_run", "rows": [row], "artifact_refs": []}
