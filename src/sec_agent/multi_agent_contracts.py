from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping


SPECIALIST_MEMOLET_SCHEMA_VERSION = "sec_agent_specialist_memolet_v0.1"
UNIVERSE_RELATIONSHIP_PLAN_SCHEMA_VERSION = "sec_agent_universe_relationship_plan_v0.1"
JUDGMENT_PLAN_SCHEMA_VERSION = "sec_agent_multi_agent_judgment_plan_v0.1"
SPECIALIST_VERIFICATION_SCHEMA_VERSION = "sec_agent_specialist_verification_v0.1"
MEMO_DRAFT_SCHEMA_VERSION = "sec_agent_multi_agent_memo_draft_v0.1"
MEMO_VERIFICATION_SCHEMA_VERSION = "sec_agent_multi_agent_memo_verification_v0.1"
RELATIONSHIP_EDGE_SCHEMA_VERSION = "sec_agent_relationship_edge_v0.3"
MEMO_THESIS_PACK_SCHEMA_VERSION = "sec_agent_memo_thesis_pack_v0.1"
ECONOMIC_LINK_MAP_SCHEMA_VERSION = "sec_agent_economic_link_map_v0.1"

SPECIALIST_AGENT_IDS = {
    "fundamental_analyst",
    "industry_supply_chain_analyst",
    "market_valuation_analyst",
    "risk_counterevidence_analyst",
}

SPECIALIST_STATUSES = {"pass", "partial", "blocked", "stubbed"}
CONFIDENCE_LEVELS = {"unknown", "low", "medium", "high"}
RELATIONSHIP_TYPES = {"peer", "competitor", "customer", "supplier", "sector", "macro_sensitive", "other"}
ECONOMIC_LINK_TYPES = {
    "direct_customer_supplier",
    "peer",
    "demand_driver",
    "second_order_beneficiary",
    "substitution",
    "macro_regulatory",
    "sector_hypothesis",
    "unknown",
}
ECONOMIC_DIRECTIONS = {"positive", "negative", "mixed", "neutral", "unknown"}
RELATIONSHIP_EVIDENCE_SOURCES = {
    "primary_sec_filing",
    "company_authored_unaudited_sec_filing",
    "market_snapshot",
    "industry_snapshot",
    "relationship_graph",
}
CONTEXT_ONLY_SOURCE_FAMILIES = {"market_snapshot", "industry_snapshot", "relationship_graph"}
SOURCE_FAMILY_CLAIM_SCOPE = {
    "primary_sec_filing": "company_reported_financial_fact",
    "company_authored_unaudited_sec_filing": "management_commentary_or_unaudited_company_context",
    "market_snapshot": "market_or_valuation_context_only",
    "industry_snapshot": "industry_context_only",
    "relationship_graph": "research_scope_or_hypothesis_only",
    "run_artifact": "audit_summary_only",
}
RELATIONSHIP_GRAPH_ALLOWED_CLAIM_TYPES = {
    "relationship_hypothesis",
    "scope_hypothesis",
    "industry_context_only",
    "investment_thesis_synthesis",
}
UNSUPPORTED_CLAIM_CAP_PER_AGENT = 2
FOCUSED_ANSWER_SYNTHESIZER_AGENT_ID = "focused_answer_synthesizer"
AMOUNT_METRIC_TERMS = {
    "revenue",
    "sales",
    "net sales",
    "product_revenue",
    "data_center_revenue",
    "segment_revenue",
    "operating_income",
    "operating income",
    "net_income",
    "net income",
    "gross_profit",
    "gross profit",
    "rd_expense",
    "r&d",
    "research_and_development",
    "research and development",
    "capex",
    "capital_expenditure",
    "capital expenditures",
    "free_cash_flow",
    "free cash flow",
    "operating_cash_flow",
    "operating cash flow",
    "cash_flow",
    "cash flow",
}
RATE_METRIC_TERMS = {
    "margin",
    "rate",
    "ratio",
    "percentage",
    "growth",
    "yield",
    "ev/sales",
    "gross_margin",
    "operating_margin",
}
RATE_ROLE_TERMS = {"percentage_rate", "rate", "ratio", "margin", "growth_rate", "percentage"}
AMOUNT_ROLE_TERMS = {"total_value", "amount", "period_change_amount", "current_value", "value"}


def normalize_specialist_memolet(payload: Mapping[str, Any] | None = None, *, agent_id: str = "") -> dict[str, Any]:
    raw = dict(payload or {})
    resolved_agent_id = str(raw.get("agent_id") or agent_id or "").strip()
    observations = [_normalize_observation(item) for item in raw.get("observations") or [] if isinstance(item, Mapping)]
    unsupported_claims = [_normalize_claim_item(item) for item in raw.get("unsupported_claims") or []]
    conflicts = [_normalize_claim_item(item) for item in raw.get("conflicts") or []]
    status = str(raw.get("status") or ("partial" if unsupported_claims else "pass")).strip()
    if status not in SPECIALIST_STATUSES:
        status = "partial"
    return {
        "schema_version": SPECIALIST_MEMOLET_SCHEMA_VERSION,
        "agent_id": resolved_agent_id,
        "status": status,
        "evidence_boundary": str(raw.get("evidence_boundary") or "bounded_rows_only").strip(),
        "summary": str(raw.get("summary") or "").strip(),
        "observations": observations,
        "unsupported_claims": unsupported_claims,
        "conflicts": conflicts,
        "confidence": _normalize_confidence(raw.get("confidence")),
        "metadata": dict(raw.get("metadata") or {}),
    }


def validate_specialist_memolet(
    payload: Mapping[str, Any] | None = None,
    *,
    known_evidence_refs: set[str] | None = None,
) -> dict[str, Any]:
    raw = dict(payload or {})
    memolet = normalize_specialist_memolet(raw)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    agent_id = str(memolet.get("agent_id") or "")
    refs = set(known_evidence_refs or set())

    if agent_id not in SPECIALIST_AGENT_IDS:
        errors.append({"type": "invalid_specialist_agent", "agent_id": agent_id})
    if memolet["evidence_boundary"] != "bounded_rows_only":
        errors.append({"type": "invalid_evidence_boundary", "agent_id": agent_id, "value": memolet["evidence_boundary"]})
    if raw.get("tool_calls") or raw.get("tool_observations"):
        errors.append({"type": "specialist_tool_calls_forbidden", "agent_id": agent_id})

    for index, observation in enumerate(memolet["observations"]):
        evidence_refs = set(observation["evidence_refs"])
        if not observation["unsupported"] and not evidence_refs:
            errors.append({"type": "supported_claim_without_evidence_refs", "agent_id": agent_id, "index": index})
        if refs:
            unknown = sorted(evidence_refs - refs)
            if unknown:
                errors.append({"type": "unknown_evidence_ref", "agent_id": agent_id, "index": index, "evidence_refs": unknown})
        if not observation["source_families"]:
            warnings.append({"type": "observation_source_family_missing", "agent_id": agent_id, "index": index})

    for index, item in enumerate(memolet["unsupported_claims"]):
        if not item.get("claim"):
            errors.append({"type": "unsupported_claim_text_required", "agent_id": agent_id, "index": index})

    return {
        "status": "fail" if errors else "pass",
        "schema_version": SPECIALIST_MEMOLET_SCHEMA_VERSION,
        "memolet": memolet,
        "errors": errors,
        "warnings": warnings,
    }


def build_stub_specialist_memolets(agent_ids: list[str]) -> list[dict[str, Any]]:
    memolets = []
    for agent_id in agent_ids:
        memolets.append(
            normalize_specialist_memolet(
                {
                    "agent_id": agent_id,
                    "status": "stubbed",
                    "summary": "No real specialist LLM was run in this graph smoke.",
                    "observations": [],
                    "unsupported_claims": [],
                    "conflicts": [],
                    "confidence": "unknown",
                    "metadata": {"stubbed": True},
                }
            )
        )
    return memolets


def normalize_universe_relationship_plan(payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    raw = dict(payload or {})
    relationships = [_normalize_relationship(item) for item in raw.get("relationships") or [] if isinstance(item, Mapping)]
    unsupported = [_normalize_claim_item(item) for item in raw.get("unsupported_relationships") or []]
    focus_tickers = _unique_upper(raw.get("focus_tickers"))
    expanded_tickers = _unique_upper(raw.get("expanded_tickers"))
    included_tickers = _unique_upper(raw.get("included_tickers")) or expanded_tickers or focus_tickers
    excluded_tickers = _unique_upper(raw.get("excluded_tickers"))
    budget = _relationship_budget(raw.get("budget") if isinstance(raw.get("budget"), Mapping) else {})
    return {
        "schema_version": UNIVERSE_RELATIONSHIP_PLAN_SCHEMA_VERSION,
        "agent_id": "universe_relationship",
        "scope_mode": str(raw.get("scope_mode") or "").strip(),
        "focus_tickers": focus_tickers,
        "expanded_tickers": expanded_tickers or included_tickers,
        "included_tickers": included_tickers,
        "excluded_tickers": excluded_tickers,
        "relationship_scope_rationale": str(raw.get("relationship_scope_rationale") or "").strip(),
        "scope_guard": _relationship_scope_guard(raw.get("scope_guard") if isinstance(raw.get("scope_guard"), Mapping) else {}, budget),
        "budget": budget,
        "relationships": relationships,
        "economic_link_map": normalize_economic_link_map(
            raw.get("economic_link_map") if isinstance(raw.get("economic_link_map"), Mapping) else {},
            relationships=relationships,
            focus_tickers=focus_tickers,
        ),
        "unsupported_relationships": unsupported,
        "evidence_requirements": evidence_requirements_from_universe_relationship_plan({"relationships": relationships, "focus_tickers": focus_tickers}),
        "source_family": str(raw.get("source_family") or "relationship_graph").strip(),
        "metadata": dict(raw.get("metadata") or {}),
    }


def validate_universe_relationship_plan(
    payload: Mapping[str, Any] | None = None,
    *,
    known_evidence_refs: set[str] | None = None,
    source_inventory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    plan = normalize_universe_relationship_plan(payload)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    refs = set(known_evidence_refs or set())
    inventory_tickers = _inventory_tickers(source_inventory or {})
    budget = plan.get("budget") if isinstance(plan.get("budget"), Mapping) else {}
    max_expanded_tickers = int(budget.get("max_expanded_tickers") or 12)
    max_relationships = int(budget.get("max_relationships") or 24)

    if plan["source_family"] != "relationship_graph":
        errors.append({"type": "invalid_relationship_source_family", "value": plan["source_family"]})
    if plan["scope_mode"] in {"full_universe", "sector_representative"} and not plan["relationship_scope_rationale"]:
        errors.append({"type": "relationship_scope_rationale_required", "scope_mode": plan["scope_mode"]})
    if len(plan["expanded_tickers"]) > max_expanded_tickers:
        errors.append(
            {
                "type": "relationship_expansion_budget_exceeded",
                "expanded_ticker_count": len(plan["expanded_tickers"]),
                "max_expanded_tickers": max_expanded_tickers,
            }
        )
    if len(plan["relationships"]) > max_relationships:
        errors.append(
            {
                "type": "relationship_count_budget_exceeded",
                "relationship_count": len(plan["relationships"]),
                "max_relationships": max_relationships,
            }
        )
    if inventory_tickers:
        unavailable = sorted(set(plan["included_tickers"]) - inventory_tickers)
        if unavailable:
            errors.append({"type": "relationship_ticker_not_in_source_inventory", "tickers": unavailable})
    related_with_evidence = {
        item["related_ticker"]
        for item in plan["relationships"]
        if item.get("related_ticker") and item.get("evidence_refs")
    } | {
        item["ticker"]
        for item in plan["relationships"]
        if item.get("ticker") and item.get("evidence_refs")
    }
    for ticker in sorted(set(plan["included_tickers"]) - set(plan["focus_tickers"])):
        if ticker not in related_with_evidence:
            errors.append({"type": "expanded_ticker_without_relationship_evidence", "ticker": ticker})
    for index, relationship in enumerate(plan["relationships"]):
        if relationship["edge_schema_version"] != RELATIONSHIP_EDGE_SCHEMA_VERSION:
            warnings.append(
                {
                    "type": "relationship_edge_schema_version_normalized",
                    "index": index,
                    "value": relationship["edge_schema_version"],
                }
            )
        if not relationship["edge_id"]:
            errors.append({"type": "relationship_edge_id_required", "index": index})
        if not relationship["from_ticker"] or not relationship["to_ticker"]:
            errors.append({"type": "relationship_edge_endpoints_required", "index": index})
        if not relationship["mechanism"]:
            warnings.append({"type": "relationship_mechanism_missing", "index": index})
        if relationship["relationship_type"] not in RELATIONSHIP_TYPES:
            errors.append({"type": "invalid_relationship_type", "index": index, "value": relationship["relationship_type"]})
        if not relationship["evidence_refs"]:
            errors.append({"type": "relationship_without_evidence_refs", "index": index})
        if not relationship["inclusion_rationale"]:
            errors.append({"type": "relationship_inclusion_rationale_required", "index": index})
        if relationship["claim_scope"] != "scope_or_hypothesis_only":
            errors.append({"type": "relationship_claim_scope_must_be_hypothesis_only", "index": index, "value": relationship["claim_scope"]})
        if relationship["inference_level"] in {"sector_inferred", "category_inferred"}:
            if relationship["confirmation_status"] != "no_confirmed_direct_edge":
                errors.append(
                    {
                        "type": "inferred_relationship_must_not_be_confirmed_direct",
                        "index": index,
                        "confirmation_status": relationship["confirmation_status"],
                    }
                )
            if not relationship["missing_confirmations"]:
                errors.append({"type": "inferred_relationship_missing_confirmation_gaps", "index": index})
        invalid_sources = sorted(set(relationship["evidence_source_needed"]) - RELATIONSHIP_EVIDENCE_SOURCES)
        if invalid_sources:
            errors.append({"type": "invalid_relationship_evidence_source_needed", "index": index, "source_families": invalid_sources})
        if refs:
            unknown = sorted(set(relationship["evidence_refs"]) - refs)
            if unknown:
                errors.append({"type": "unknown_relationship_evidence_ref", "index": index, "evidence_refs": unknown})
        if not relationship["metrics_to_check"]:
            warnings.append({"type": "relationship_metrics_to_check_missing", "index": index})
    if _economic_link_map_has_content(plan.get("economic_link_map")):
        link_validation = validate_economic_link_map(
            plan["economic_link_map"],
            known_evidence_refs=refs,
            allowed_tickers=set(plan["included_tickers"]) | set(plan["focus_tickers"]),
        )
        if link_validation["status"] != "pass":
            for error in link_validation["errors"]:
                errors.append({"type": "economic_link_map_invalid", **error})
        warnings.extend({"type": "economic_link_map_warning", **warning} for warning in link_validation["warnings"])
    return {
        "status": "fail" if errors else "pass",
        "schema_version": UNIVERSE_RELATIONSHIP_PLAN_SCHEMA_VERSION,
        "plan": plan,
        "errors": errors,
        "warnings": warnings,
    }


def _economic_link_map_has_content(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    return any(value.get(key) for key in ("entities", "links", "mechanisms", "investment_implications"))


def normalize_economic_link_map(
    payload: Mapping[str, Any] | None = None,
    *,
    relationships: list[Mapping[str, Any]] | None = None,
    focus_tickers: list[str] | None = None,
) -> dict[str, Any]:
    raw = dict(payload or {})
    entities = [
        _normalize_economic_entity(item)
        for item in raw.get("entities") or []
        if isinstance(item, Mapping)
    ]
    links = [
        _normalize_economic_link(item)
        for item in raw.get("links") or []
        if isinstance(item, Mapping)
    ]
    mechanisms = [
        _normalize_economic_mechanism(item)
        for item in raw.get("mechanisms") or []
        if isinstance(item, Mapping)
    ]
    implications = [
        _normalize_investment_implication(item)
        for item in raw.get("investment_implications") or []
        if isinstance(item, Mapping)
    ]
    return {
        "schema_version": ECONOMIC_LINK_MAP_SCHEMA_VERSION,
        "map_scope": str(raw.get("map_scope") or "relationship_hypothesis").strip(),
        "focus_tickers": _unique_upper(raw.get("focus_tickers") or focus_tickers),
        "entities": entities,
        "links": links,
        "mechanisms": mechanisms,
        "investment_implications": implications,
        "boundary_notes": [
            _normalize_boundary_note(item)
            for item in raw.get("boundary_notes") or []
            if isinstance(item, Mapping)
        ],
        "source_boundary": str(raw.get("source_boundary") or "relationship_graph_hypothesis_only").strip(),
        "map_policy": str(raw.get("map_policy") or "universe_relationship_economic_link_map_v0_1").strip(),
        "metadata": {
            **(dict(raw.get("metadata") or {}) if isinstance(raw.get("metadata"), Mapping) else {}),
            "relationship_count": len(relationships or []),
        },
    }


def validate_economic_link_map(
    payload: Mapping[str, Any] | None = None,
    *,
    known_evidence_refs: set[str] | None = None,
    allowed_tickers: set[str] | None = None,
) -> dict[str, Any]:
    link_map = normalize_economic_link_map(payload)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    known_refs = set(known_evidence_refs or set())
    allowed = {str(item).upper().strip() for item in allowed_tickers or set() if str(item).strip()}

    if link_map["source_boundary"] != "relationship_graph_hypothesis_only":
        errors.append({"type": "economic_link_map_source_boundary_invalid", "value": link_map["source_boundary"]})
    if not link_map["entities"]:
        errors.append({"type": "economic_link_map_entities_required"})
    if not link_map["links"]:
        errors.append({"type": "economic_link_map_links_required"})
    if not link_map["mechanisms"]:
        errors.append({"type": "economic_link_map_mechanisms_required"})
    if not link_map["investment_implications"]:
        errors.append({"type": "economic_link_map_investment_implications_required"})

    for index, entity in enumerate(link_map["entities"]):
        ticker = entity["ticker"]
        if not ticker:
            errors.append({"type": "economic_entity_ticker_required", "index": index})
        if ticker and allowed and ticker not in allowed:
            errors.append({"type": "economic_entity_ticker_not_allowed", "index": index, "ticker": ticker})
        if not entity["role"]:
            errors.append({"type": "economic_entity_role_required", "index": index, "ticker": ticker})
        _validate_refs(
            entity["evidence_refs"],
            known_refs=known_refs,
            errors=errors,
            error_type="economic_entity_unknown_evidence_ref",
            index=index,
        )

    for index, link in enumerate(link_map["links"]):
        if not link["source"] or not link["target"]:
            errors.append({"type": "economic_link_endpoints_required", "index": index})
        if link["link_type"] not in ECONOMIC_LINK_TYPES:
            errors.append({"type": "economic_link_type_invalid", "index": index, "value": link["link_type"]})
        if link["direction"] not in ECONOMIC_DIRECTIONS:
            errors.append({"type": "economic_link_direction_invalid", "index": index, "value": link["direction"]})
        if not link["mechanism"]:
            errors.append({"type": "economic_link_mechanism_required", "index": index})
        if not link["evidence_refs"]:
            errors.append({"type": "economic_link_evidence_refs_required", "index": index})
        if link["claim_scope"] != "economic_mechanism_hypothesis_only":
            errors.append({"type": "economic_link_claim_scope_invalid", "index": index, "value": link["claim_scope"]})
        for endpoint_key in ("source", "target"):
            endpoint = str(link.get(endpoint_key) or "").upper().strip()
            if _looks_like_ticker(endpoint) and allowed and endpoint not in allowed:
                errors.append({"type": "economic_link_endpoint_not_allowed", "index": index, "endpoint": endpoint})
        _validate_refs(
            link["evidence_refs"],
            known_refs=known_refs,
            errors=errors,
            error_type="economic_link_unknown_evidence_ref",
            index=index,
        )
        if link["link_type"] == "direct_customer_supplier" and not link["missing_confirmations"]:
            warnings.append({"type": "direct_link_without_missing_confirmation_note", "index": index})

    for index, mechanism in enumerate(link_map["mechanisms"]):
        if not mechanism["driver"]:
            errors.append({"type": "economic_mechanism_driver_required", "index": index})
        if not mechanism["affected_entities"]:
            errors.append({"type": "economic_mechanism_affected_entities_required", "index": index})
        if not mechanism["metric_implications"]:
            errors.append({"type": "economic_mechanism_metric_implications_required", "index": index})
        _validate_refs(
            mechanism["evidence_refs"],
            known_refs=known_refs,
            errors=errors,
            error_type="economic_mechanism_unknown_evidence_ref",
            index=index,
        )

    for index, implication in enumerate(link_map["investment_implications"]):
        if not implication["claim"]:
            errors.append({"type": "investment_implication_claim_required", "index": index})
        if not implication["so_what"]:
            errors.append({"type": "investment_implication_so_what_required", "index": index})
        if not implication["supporting_refs"]:
            errors.append({"type": "investment_implication_supporting_refs_required", "index": index})
        _validate_refs(
            implication["supporting_refs"],
            known_refs=known_refs,
            errors=errors,
            error_type="investment_implication_unknown_supporting_ref",
            index=index,
        )

    return {
        "schema_version": ECONOMIC_LINK_MAP_SCHEMA_VERSION,
        "status": "fail" if errors else "pass",
        "economic_link_map": link_map,
        "errors": errors,
        "warnings": warnings,
    }


def evidence_requirements_from_universe_relationship_plan(payload: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    raw = dict(payload or {})
    requirements = []
    focus_tickers = _unique_upper(raw.get("focus_tickers"))
    for index, relationship in enumerate(raw.get("relationships") or [], start=1):
        if not isinstance(relationship, Mapping):
            continue
        ticker = str(relationship.get("ticker") or "").upper().strip()
        related = str(relationship.get("related_ticker") or "").upper().strip()
        tickers = _unique_upper([ticker, related])
        source_families = _unique_strings(relationship.get("evidence_source_needed")) or ["primary_sec_filing"]
        metrics = _unique_strings(relationship.get("metrics_to_check")) or ["relationship_mechanism"]
        requirements.append(
            {
                "requirement_id": f"req_relationship_{index}_{ticker or 'focus'}_{related or 'related'}".lower(),
                "task_id": f"relationship_{index}_{ticker or 'focus'}_{related or 'related'}".lower(),
                "question_zh": str(relationship.get("inclusion_rationale") or relationship.get("notes") or "Verify relationship hypothesis with bounded evidence."),
                "priority": "supporting",
                "analysis_intent": "relationship_hypothesis_verification",
                "tickers": tickers or focus_tickers,
                "source_families": source_families,
                "metric_families": metrics,
                "relationship_type": str(relationship.get("relationship_type") or "other"),
                "relationship_direction": str(relationship.get("direction") or "unknown"),
                "planner_boundary": "business_need_only_no_physical_paths",
                "claim_scope": "relationship_hypothesis_not_financial_fact",
            }
        )
    return requirements


def aggregate_specialist_judgment_plan(
    memolets: list[Mapping[str, Any]],
    *,
    reflection_report: Mapping[str, Any] | None = None,
    evidence_requirement_plan: Mapping[str, Any] | None = None,
    source_gaps: list[Mapping[str, Any]] | None = None,
    tool_ledger_summary: Mapping[str, Any] | None = None,
    verifier_constraints: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    validations = [validate_specialist_memolet(item) for item in memolets]
    normalized = [item["memolet"] for item in validations]
    errors = [error for result in validations for error in result["errors"]]
    supported_claims: list[dict[str, Any]] = []
    unsupported_claims: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    blocked_specialist_agents: list[str] = []

    for memolet in normalized:
        agent_id = memolet["agent_id"]
        metadata = memolet.get("metadata") if isinstance(memolet.get("metadata"), Mapping) else {}
        if memolet.get("status") == "blocked" or metadata.get("route_failure"):
            blocked_specialist_agents.append(agent_id)
        for observation_index, observation in enumerate(memolet["observations"]):
            item = {
                **observation,
                "agent_id": agent_id,
                "claim_card_version": "v0.3",
                "claim_id": f"{agent_id}_claim_{len(supported_claims) + len(unsupported_claims) + 1}",
            }
            if observation["unsupported"]:
                unsupported_claims.append({"agent_id": agent_id, "claim": observation["claim"], "reason": "marked_unsupported"})
            else:
                item.update(_claim_card_rank_annotation(item, observation_index))
                supported_claims.append(item)
        for item in memolet["unsupported_claims"]:
            unsupported_claims.append({"agent_id": agent_id, **item})
        for item in memolet["conflicts"]:
            conflicts.append({"agent_id": agent_id, **item})

    supported_claims = _rank_supported_claims(supported_claims)
    unsupported_claims, unsupported_overflow = _cap_unsupported_claims_by_agent(unsupported_claims)
    supported_claims, thesis_synthesis = _with_synthesized_thesis_claim(supported_claims)
    memo_outline = _memo_outline_from_claims(
        supported_claims,
        source_agent_ids=[item["agent_id"] for item in normalized],
        blocked_specialist_agents=blocked_specialist_agents,
    )
    source_boundary_notes = _source_boundary_notes(
        evidence_requirement_plan=evidence_requirement_plan,
        reflection_report=reflection_report,
        source_gaps=source_gaps or [],
        memolets=normalized,
    )
    memo_thesis_plan = _memo_thesis_plan_from_claims(
        supported_claims=supported_claims,
        memo_outline=memo_outline,
        conflicts=conflicts,
        unsupported_claims=unsupported_claims,
        source_boundary_notes=source_boundary_notes,
    )
    memo_thesis_pack = _memo_thesis_pack_from_claims(
        supported_claims=supported_claims,
        memo_outline=memo_outline,
        memo_thesis_plan=memo_thesis_plan,
        conflicts=conflicts,
        unsupported_claims=unsupported_claims,
        source_boundary_notes=source_boundary_notes,
    )
    memo_constraints = _memo_constraints(
        validation_errors=errors,
        supported_claims=supported_claims,
        unsupported_claims=unsupported_claims,
        conflicts=conflicts,
        blocked_specialist_agents=blocked_specialist_agents,
        reflection_report=reflection_report,
        source_boundary_notes=source_boundary_notes,
        tool_ledger_summary=tool_ledger_summary,
        verifier_constraints=verifier_constraints,
        unsupported_claim_overflow=unsupported_overflow,
        thesis_synthesis=thesis_synthesis,
    )
    return {
        "schema_version": JUDGMENT_PLAN_SCHEMA_VERSION,
        "status": "fail" if errors else "partial" if unsupported_claims or conflicts else "pass",
        "specialist_output_count": len(normalized),
        "source_agent_ids": [item["agent_id"] for item in normalized],
        "supported_claims": supported_claims,
        "unsupported_claims": unsupported_claims,
        "conflicts": conflicts,
        "blocked_specialist_agents": blocked_specialist_agents,
        "source_boundary_notes": source_boundary_notes,
        "memo_outline": memo_outline,
        "memo_thesis_plan": memo_thesis_plan,
        "memo_thesis_pack": memo_thesis_pack,
        "claim_card_stats": _claim_card_stats(supported_claims, memo_outline),
        "thesis_synthesis": thesis_synthesis,
        "unsupported_claim_policy": {
            "policy": "cap_memo_facing_unsupported_claims_by_agent_preserve_overflow_count",
            "cap_per_agent": UNSUPPORTED_CLAIM_CAP_PER_AGENT,
            "visible_unsupported_claim_count": len(unsupported_claims),
            "overflow_unsupported_claim_count": int(unsupported_overflow.get("overflow_count") or 0),
            "overflow_by_agent": dict(unsupported_overflow.get("by_agent") or {}),
        },
        "memo_constraints": memo_constraints,
        "memo_writer_allowed": bool(memo_constraints.get("memo_writer_allowed")),
        "aggregation_policy": "rank_supported_claim_cards_preserve_conflicts_no_average",
        "validation_errors": errors,
    }


def aggregate_focused_answer_judgment_plan(
    *,
    context_rows: list[Mapping[str, Any]] | None = None,
    runtime_ledger_rows: list[Mapping[str, Any]] | None = None,
    reflection_report: Mapping[str, Any] | None = None,
    evidence_requirement_plan: Mapping[str, Any] | None = None,
    source_gaps: list[Mapping[str, Any]] | None = None,
    tool_ledger_summary: Mapping[str, Any] | None = None,
    verifier_constraints: Mapping[str, Any] | None = None,
    response_language: str = "en-US",
) -> dict[str, Any]:
    """Build a compact Judgment Plan for focused answers that deliberately skip specialists."""
    supported_claims = _focused_answer_supported_claims(
        context_rows=context_rows or [],
        runtime_ledger_rows=runtime_ledger_rows or [],
        evidence_requirement_plan=evidence_requirement_plan or {},
        response_language=response_language,
    )
    errors: list[dict[str, Any]] = []
    unsupported_claims: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    blocked_specialist_agents: list[str] = []
    source_agent_ids = [FOCUSED_ANSWER_SYNTHESIZER_AGENT_ID] if supported_claims else []
    memo_outline = _memo_outline_from_claims(
        supported_claims,
        source_agent_ids=source_agent_ids,
        blocked_specialist_agents=blocked_specialist_agents,
    )
    source_boundary_notes = _source_boundary_notes(
        evidence_requirement_plan=evidence_requirement_plan,
        reflection_report=reflection_report,
        source_gaps=source_gaps or [],
        memolets=[],
    )
    memo_thesis_plan = _memo_thesis_plan_from_claims(
        supported_claims=supported_claims,
        memo_outline=memo_outline,
        conflicts=conflicts,
        unsupported_claims=unsupported_claims,
        source_boundary_notes=source_boundary_notes,
    )
    memo_thesis_pack = _memo_thesis_pack_from_claims(
        supported_claims=supported_claims,
        memo_outline=memo_outline,
        memo_thesis_plan=memo_thesis_plan,
        conflicts=conflicts,
        unsupported_claims=unsupported_claims,
        source_boundary_notes=source_boundary_notes,
    )
    memo_constraints = _memo_constraints(
        validation_errors=errors,
        supported_claims=supported_claims,
        unsupported_claims=unsupported_claims,
        conflicts=conflicts,
        blocked_specialist_agents=blocked_specialist_agents,
        reflection_report=reflection_report,
        source_boundary_notes=source_boundary_notes,
        tool_ledger_summary=tool_ledger_summary,
        verifier_constraints=verifier_constraints,
        unsupported_claim_overflow={},
        thesis_synthesis={"status": "focused_bridge", "policy": "focused_answer_claim_cards_from_bounded_rows_v0_1"},
    )
    return {
        "schema_version": JUDGMENT_PLAN_SCHEMA_VERSION,
        "status": "pass" if supported_claims else "partial",
        "specialist_output_count": 0,
        "source_agent_ids": source_agent_ids,
        "supported_claims": supported_claims,
        "unsupported_claims": unsupported_claims,
        "conflicts": conflicts,
        "blocked_specialist_agents": blocked_specialist_agents,
        "source_boundary_notes": source_boundary_notes,
        "memo_outline": memo_outline,
        "memo_thesis_plan": memo_thesis_plan,
        "memo_thesis_pack": memo_thesis_pack,
        "claim_card_stats": _claim_card_stats(supported_claims, memo_outline),
        "thesis_synthesis": {
            "status": "focused_bridge",
            "policy": "focused_answer_claim_cards_from_bounded_rows_v0_1",
            "supported_claim_count": len(supported_claims),
        },
        "unsupported_claim_policy": {
            "policy": "not_applicable_no_specialist_outputs",
            "cap_per_agent": UNSUPPORTED_CLAIM_CAP_PER_AGENT,
            "visible_unsupported_claim_count": 0,
            "overflow_unsupported_claim_count": 0,
            "overflow_by_agent": {},
        },
        "memo_constraints": memo_constraints,
        "memo_writer_allowed": bool(memo_constraints.get("memo_writer_allowed")),
        "aggregation_policy": "focused_answer_claim_cards_from_bounded_rows_v0_1",
        "focused_answer_bridge": {
            "status": "used" if supported_claims else "no_rows",
            "runtime_ledger_row_count": len([row for row in runtime_ledger_rows or [] if isinstance(row, Mapping)]),
            "context_row_count": len([row for row in context_rows or [] if isinstance(row, Mapping)]),
            "policy": "no_specialist_llm_claim_synthesis_from_bounded_rows_only",
        },
        "validation_errors": errors,
    }


def verify_specialist_outputs_for_memo(
    memolets: list[Mapping[str, Any]],
    *,
    judgment_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    judgment = dict(judgment_plan or aggregate_specialist_judgment_plan(memolets))
    unsupported = list(judgment.get("unsupported_claims") or [])
    errors = list(judgment.get("validation_errors") or [])
    constraints = judgment.get("memo_constraints") if isinstance(judgment.get("memo_constraints"), Mapping) else {}
    memo_writer_allowed = bool(constraints.get("memo_writer_allowed", not errors and not unsupported))
    return {
        "schema_version": SPECIALIST_VERIFICATION_SCHEMA_VERSION,
        "status": "pass" if memo_writer_allowed else "fail",
        "memo_writer_allowed": memo_writer_allowed,
        "unsupported_claim_count": len(unsupported),
        "unsupported_claims": unsupported,
        "validation_errors": errors,
        "blocked_reasons": list(constraints.get("blocked_reasons") or []),
        "verified_judgment_plan": judgment,
        "policy": "unsupported_specialist_claims_do_not_enter_memo_writer",
    }


def _rank_supported_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = list(enumerate(claims))
    ranked = sorted(indexed, key=lambda item: _claim_rank_key(item[1], item[0]))
    return [claim for _, claim in ranked]


def _focused_answer_supported_claims(
    *,
    context_rows: list[Mapping[str, Any]],
    runtime_ledger_rows: list[Mapping[str, Any]],
    evidence_requirement_plan: Mapping[str, Any],
    response_language: str,
) -> list[dict[str, Any]]:
    ledger_rows = [dict(row) for row in runtime_ledger_rows if isinstance(row, Mapping)]
    text_rows = [dict(row) for row in context_rows if isinstance(row, Mapping)]
    selected_ledger = _focused_select_ledger_rows(ledger_rows, max_rows=3)
    selected_text = _focused_select_context_rows(text_rows, max_rows=2)
    all_selected = [*selected_ledger, *selected_text]
    if not all_selected:
        return []

    tickers = _focused_tickers(all_selected, evidence_requirement_plan)
    metrics = _unique_strings(
        [
            _focused_metric(row)
            for row in all_selected
            if _focused_metric(row)
        ]
    )
    refs = _unique_strings([_focused_evidence_ref(row, index) for index, row in enumerate(all_selected, start=1)])
    families = _unique_strings([_focused_source_family(row) for row in all_selected])
    thesis = {
        "claim": _focused_thesis_claim_text(tickers=tickers, metrics=metrics, row_count=len(all_selected), response_language=response_language),
        "claim_type": "investment_thesis_synthesis",
        "ticker_scope": tickers,
        "metric_scope": metrics,
        "memo_slot": "thesis",
        "materiality": "high",
        "direction": "mixed",
        "evidence_refs": refs[:8],
        "source_families": families,
        "confidence": "medium",
        "unsupported": False,
        "caveats": [_focused_bridge_caveat(response_language)],
        "missing_confirmations": [],
        "agent_id": FOCUSED_ANSWER_SYNTHESIZER_AGENT_ID,
        "claim_card_version": "v0.3",
        "claim_id": "focused_answer_synthesizer_thesis_1",
        "synthesis_policy": "focused_answer_claim_cards_from_bounded_rows_v0_1",
    }
    thesis.update(_claim_card_rank_annotation(thesis, -1))

    claims = [thesis]
    if selected_ledger:
        claim = _focused_ledger_claim(selected_ledger, tickers=tickers, response_language=response_language)
        claim.update(_claim_card_rank_annotation(claim, 0))
        claims.append(claim)
    if selected_text:
        claim = _focused_context_claim(selected_text, tickers=tickers, response_language=response_language)
        claim.update(_claim_card_rank_annotation(claim, 1))
        claims.append(claim)
    return _rank_supported_claims(claims)


def _focused_select_ledger_rows(rows: list[dict[str, Any]], *, max_rows: int) -> list[dict[str, Any]]:
    preferred_terms = (
        "margin",
        "operating_income",
        "operating income",
        "gross",
        "revenue",
        "sales",
        "cash_flow",
        "free_cash_flow",
    )
    scored: list[tuple[int, int, dict[str, Any]]] = []
    seen_metrics: set[str] = set()
    for index, row in enumerate(rows):
        metric = _focused_metric(row).lower()
        ref = _focused_evidence_ref(row, index + 1)
        if not ref:
            continue
        score = 0
        if _ledger_metric_value_is_mismatched(row):
            score -= 200
        for offset, term in enumerate(preferred_terms):
            if term in metric:
                score += 50 - offset
        role = _ledger_metric_role(row)
        if role in AMOUNT_ROLE_TERMS:
            score += 20
        if role in RATE_ROLE_TERMS and _ledger_metric_is_amount(row):
            score -= 80
        if str(row.get("period_role") or "").lower() in {"qtd", "ytd"}:
            score += 5
        if str(row.get("source_tier") or "") == "primary_sec_filing":
            score += 5
        scored.append((-score, index, row))
    selected: list[dict[str, Any]] = []
    has_compatible_amount_rows = any(not _ledger_metric_value_is_mismatched(row) for _, _, row in scored)
    for _, _, row in sorted(scored):
        if has_compatible_amount_rows and _ledger_metric_value_is_mismatched(row):
            continue
        metric = _focused_metric(row).lower()
        metric_key = metric or _focused_evidence_ref(row, len(selected) + 1)
        if metric_key in seen_metrics and len(selected) >= 1:
            continue
        selected.append(row)
        seen_metrics.add(metric_key)
        if len(selected) >= max_rows:
            break
    return selected


def _focused_select_context_rows(rows: list[dict[str, Any]], *, max_rows: int) -> list[dict[str, Any]]:
    preferred: list[tuple[int, int, dict[str, Any]]] = []
    for index, row in enumerate(rows):
        family = _focused_source_family(row)
        text = " ".join(
            str(row.get(key) or "")
            for key in ("summary", "snippet", "text", "preview", "section", "source_type", "form_type")
        ).lower()
        score = 0
        if family == "company_authored_unaudited_sec_filing":
            score += 30
        if family == "primary_sec_filing":
            score += 15
        if any(term in text for term in ("margin", "operating income", "profitability", "management", "explained", "cost")):
            score += 20
        if _focused_evidence_ref(row, index + 1):
            score += 5
        preferred.append((-score, index, row))
    return [row for _, _, row in sorted(preferred)[:max_rows] if _focused_evidence_ref(row, 1)]


def _focused_ledger_claim(rows: list[dict[str, Any]], *, tickers: list[str], response_language: str) -> dict[str, Any]:
    fragments = []
    for row in rows[:3]:
        metric = _focused_metric_label(row, response_language=response_language) or "reported metric"
        value = ledger_metric_display_value(row)
        period = " ".join(str(row.get(key) or "").strip() for key in ("fiscal_year", "period_role") if str(row.get(key) or "").strip())
        fragments.append(f"{metric}={value or 'disclosed'} ({period.strip() or 'current filing period'})")
    ticker_text = ", ".join(tickers) or ("目标公司" if _focused_is_zh(response_language) else "The company")
    if _focused_is_zh(response_language):
        claim_text = f"本轮主要 SEC 披露证据为 {ticker_text} 的利润率分析提供了关键数值锚点：" + "；".join(fragments) + "。"
        caveats = ["不要在没有相同期间和相同口径对比时，把这些数值外推为完整的利润率扩张或收缩结论。"]
    else:
        claim_text = f"Primary SEC filing evidence anchors {ticker_text}'s margin analysis with these reported values: " + "; ".join(fragments) + "."
        caveats = ["Do not infer full margin expansion or compression without comparing the exact period and metric definitions."]
    return {
        "claim": claim_text,
        "claim_type": "company_reported_financial_fact",
        "ticker_scope": tickers,
        "metric_scope": _unique_strings([_focused_metric(row) for row in rows]),
        "memo_slot": "fundamentals",
        "materiality": "high",
        "direction": "mixed",
        "evidence_refs": _unique_strings([_focused_evidence_ref(row, index) for index, row in enumerate(rows, start=1)])[:6],
        "source_families": _unique_strings([_focused_source_family(row) for row in rows]),
        "confidence": "high",
        "unsupported": False,
        "caveats": caveats,
        "missing_confirmations": [],
        "agent_id": FOCUSED_ANSWER_SYNTHESIZER_AGENT_ID,
        "claim_card_version": "v0.3",
        "claim_id": "focused_answer_synthesizer_fundamentals_1",
    }


def _focused_context_claim(rows: list[dict[str, Any]], *, tickers: list[str], response_language: str) -> dict[str, Any]:
    refs = _unique_strings([_focused_evidence_ref(row, index) for index, row in enumerate(rows, start=1)])[:6]
    families = _unique_strings([_focused_source_family(row) for row in rows])
    forms = _unique_strings([row.get("form_type") or row.get("source_type") for row in rows])
    ticker_text = ", ".join(tickers) or ("目标公司" if _focused_is_zh(response_language) else "The company")
    if _focused_is_zh(response_language):
        claim_text = f"本轮公司披露或管理层评论为 {ticker_text} 的利润率变化提供解释语境，但只能作为管理层表述使用，不能改写为新增审计财务事实。"
        caveat_text = f"来源表单：{', '.join(forms)}。" if forms else "评论证据只限于本轮检索到的内容。"
    else:
        claim_text = f"{ticker_text} has bounded filing or company-authored commentary rows that can explain the margin movement, but those rows should be used as management context rather than as new audited financial facts."
        caveat_text = f"Source forms: {', '.join(forms)}." if forms else "Commentary evidence is bounded to retrieved rows."
    return {
        "claim": claim_text,
        "claim_type": "business_observation",
        "ticker_scope": tickers,
        "metric_scope": _unique_strings([_focused_metric(row) for row in rows if _focused_metric(row)] or ["margin"]),
        "memo_slot": "fundamentals",
        "materiality": "medium",
        "direction": "mixed",
        "evidence_refs": refs,
        "source_families": families,
        "confidence": "medium",
        "unsupported": False,
        "caveats": [caveat_text],
        "missing_confirmations": [],
        "agent_id": FOCUSED_ANSWER_SYNTHESIZER_AGENT_ID,
        "claim_card_version": "v0.3",
        "claim_id": "focused_answer_synthesizer_context_1",
    }


def _focused_thesis_claim_text(*, tickers: list[str], metrics: list[str], row_count: int, response_language: str) -> str:
    if _focused_is_zh(response_language):
        ticker_text = ", ".join(tickers) or "目标公司"
        metric_text = ", ".join(_localized_metric_labels(metrics[:5], response_language=response_language)) or "请求指标"
        return (
            f"{ticker_text} 的回答应限定在本轮检索到的 {row_count} 条证据内：这些证据覆盖 {metric_text}；"
            "足以支持初步判断，但不支持超出披露口径的趋势外推。"
        )
    ticker_text = ", ".join(tickers) or "The requested company"
    metric_text = ", ".join(metrics[:5]) or "the requested metrics"
    return (
        f"{ticker_text} can receive a bounded focused answer because {row_count} retrieved evidence rows cover {metric_text}; "
        "the conclusion should stay tied to those rows and preserve source-boundary caveats."
    )


def _focused_bridge_caveat(response_language: str) -> str:
    if _focused_is_zh(response_language):
        return "本次快速回答只使用本轮已检索的有界证据；由于按成本控制策略未激活专家分析，结论应保持来源和口径边界。"
    return "Focused answer bridge uses bounded retrieved rows because specialist analysts were intentionally skipped."


def _focused_is_zh(response_language: str) -> bool:
    return str(response_language or "").strip().lower().replace("_", "-") in {"zh", "zh-cn", "zh-hans", "chinese", "中文", "简体中文"}


def _focused_tickers(rows: list[dict[str, Any]], evidence_requirement_plan: Mapping[str, Any]) -> list[str]:
    tickers = _unique_upper([row.get("ticker") or row.get("company") for row in rows])
    if tickers:
        return tickers
    planned: list[Any] = []
    for req in evidence_requirement_plan.get("requirements") or []:
        if isinstance(req, Mapping):
            planned.extend(req.get("tickers") or req.get("required_tickers") or [])
    return _unique_upper(planned)


def _focused_metric(row: Mapping[str, Any]) -> str:
    return str(row.get("metric_family") or row.get("metric_name") or row.get("metric") or row.get("field") or "").strip()


def ledger_metric_display_value(row: Mapping[str, Any]) -> str:
    display = str(row.get("display_value_zh") or "").strip()
    raw = str(row.get("raw_value_text") or "").strip()
    value = str(row.get("value") or "").strip()
    if _ledger_metric_is_amount(row) and _value_or_role_looks_rate(row, display):
        if raw and not _looks_rate_value(raw):
            return raw
        if value and not _looks_rate_value(value):
            return value
    return str(display or raw or value).strip()


def _ledger_metric_value_is_mismatched(row: Mapping[str, Any]) -> bool:
    return _ledger_metric_is_amount(row) and _value_or_role_looks_rate(
        row,
        str(row.get("display_value_zh") or row.get("raw_value_text") or row.get("value") or ""),
    )


def _ledger_metric_is_amount(row: Mapping[str, Any]) -> bool:
    metric_text = " ".join(
        str(row.get(key) or "")
        for key in ("metric_family", "metric_name", "metric", "field")
    ).strip().lower()
    if not metric_text:
        return False
    if any(term in metric_text for term in RATE_METRIC_TERMS):
        return False
    return any(term in metric_text for term in AMOUNT_METRIC_TERMS)


def _ledger_metric_role(row: Mapping[str, Any]) -> str:
    role = str(row.get("metric_role") or row.get("role") or "").strip().lower()
    if role:
        return role
    ref = str(row.get("metric_id") or row.get("source_evidence_id") or row.get("evidence_ref") or "").lower()
    for term in [*RATE_ROLE_TERMS, *AMOUNT_ROLE_TERMS]:
        if f"::{term}::" in ref or ref.endswith(f"::{term}") or f":{term}:" in ref:
            return term
    return ""


def _value_or_role_looks_rate(row: Mapping[str, Any], value_text: str) -> bool:
    role = _ledger_metric_role(row)
    return role in RATE_ROLE_TERMS or _looks_rate_value(value_text)


def _looks_rate_value(value_text: str) -> bool:
    text = str(value_text or "").strip().lower()
    return bool(text) and any(marker in text for marker in ("%", "percent", "percentage", "百分比", "百分率"))


def _focused_metric_label(row: Mapping[str, Any], *, response_language: str) -> str:
    metric = str(row.get("metric_name") or row.get("metric_family") or row.get("metric") or row.get("field") or "").strip()
    labels = _localized_metric_labels([metric], response_language=response_language)
    return labels[0] if labels else metric


def _localized_metric_labels(metrics: list[str], *, response_language: str) -> list[str]:
    if not _focused_is_zh(response_language):
        return metrics
    mapping = {
        "operating_income": "营业利润",
        "operating income": "营业利润",
        "revenue": "营收",
        "net sales": "营收",
        "sales": "营收",
        "net_income": "净利润",
        "net income": "净利润",
        "gross_margin": "毛利率",
        "gross margin": "毛利率",
        "operating_margin": "营业利润率",
        "operating margin": "营业利润率",
        "capex": "资本开支",
        "capital expenditures": "资本开支",
        "free_cash_flow": "自由现金流",
        "free cash flow": "自由现金流",
    }
    labels: list[str] = []
    for metric in metrics:
        raw = str(metric or "").strip()
        if not raw:
            continue
        labels.append(mapping.get(raw.lower(), raw))
    return labels


def _focused_evidence_ref(row: Mapping[str, Any], index: int) -> str:
    return str(
        row.get("evidence_ref")
        or row.get("evidence_id")
        or row.get("metric_id")
        or row.get("source_evidence_id")
        or row.get("object_id")
        or row.get("source_id")
        or row.get("id")
        or f"focused_evidence_row_{index}"
    ).strip()


def _focused_source_family(row: Mapping[str, Any]) -> str:
    family = str(row.get("source_family") or "").strip()
    if family:
        return family
    tier = str(row.get("source_tier") or "").strip()
    if tier in SOURCE_FAMILY_CLAIM_SCOPE:
        return tier
    form = str(row.get("form_type") or row.get("source_type") or "").strip().upper()
    if form in {"8-K", "6-K"}:
        return "company_authored_unaudited_sec_filing"
    if form in {"10-K", "10-Q", "20-F", "40-F"}:
        return "primary_sec_filing"
    return "primary_sec_filing"


def _claim_card_rank_annotation(claim: Mapping[str, Any], index: int) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []
    evidence_refs = _unique_strings(claim.get("evidence_refs") or claim.get("refs"))
    source_families = _unique_strings(claim.get("source_families") or claim.get("source_family"))
    agent_id = str(claim.get("agent_id") or "")
    claim_text = str(claim.get("claim") or "")
    claim_type = str(claim.get("claim_type") or "business_observation")
    memo_slot = _normalize_memo_slot(claim.get("memo_slot"))

    if evidence_refs:
        score += min(30, 18 + 3 * len(evidence_refs))
        reasons.append("has_evidence_refs")
    else:
        score -= 30
        reasons.append("missing_evidence_refs")

    source_strength = _source_strength_score(source_families)
    if source_strength:
        score += source_strength * 5
        reasons.append("source_strength")

    materiality_score = _materiality_score(claim.get("materiality"))
    confidence_score = _confidence_score(claim.get("confidence"))
    score += materiality_score * 7
    score += confidence_score * 6
    if materiality_score >= 3:
        reasons.append("high_materiality")
    if confidence_score >= 2:
        reasons.append("usable_confidence")

    expected_slot = _agent_expected_memo_slot(agent_id)
    if expected_slot and memo_slot == expected_slot:
        score += 12
        reasons.append("role_slot_match")
    elif memo_slot == "thesis":
        score += 3
    elif expected_slot:
        score -= 8
        reasons.append("role_slot_mismatch")

    has_ticker_scope = bool(_unique_upper(claim.get("ticker_scope") or claim.get("tickers") or claim.get("ticker")))
    has_metric_scope = bool(_unique_strings(claim.get("metric_scope") or claim.get("metrics") or claim.get("metric")))
    if has_ticker_scope:
        score += 5
    else:
        score -= 4
        reasons.append("missing_ticker_scope")
    if has_metric_scope:
        score += 5
    else:
        score -= 3
        reasons.append("missing_metric_scope")
    if _normalize_direction(claim.get("direction")) not in {"unknown", "neutral"}:
        score += 5
        reasons.append("directional")

    scope_penalty = _claim_source_scope_penalty(claim_type, source_families)
    if scope_penalty:
        score -= scope_penalty
        reasons.append("source_claim_scope_penalty")
    else:
        score += 4

    implication_score, implication_reason = _claim_implication_score(claim_text)
    score += implication_score
    if implication_reason:
        reasons.append(implication_reason)

    if agent_id == "risk_counterevidence_analyst" and _normalize_direction(claim.get("direction")) in {"negative", "mixed"}:
        score += 5
        reasons.append("risk_direction_fit")
    if agent_id == "market_valuation_analyst" and "market_snapshot" in set(source_families) and str(claim.get("as_of_date") or ""):
        score += 5
        reasons.append("market_timestamped")
    if agent_id == "industry_supply_chain_analyst" and set(source_families) & {"relationship_graph", "industry_snapshot"}:
        score += 5
        reasons.append("industry_relationship_source_fit")

    gap_like = _claim_text_is_gap_like(claim_text)
    if gap_like:
        score -= 18
        reasons.append("gap_like_supported_claim")

    bounded_score = max(0, min(100, score))
    memo_ready_shape = has_ticker_scope and has_metric_scope and "investment_implication" in reasons
    if evidence_refs and not gap_like and memo_ready_shape and bounded_score >= 70:
        bucket = "memo_ready"
    elif evidence_refs and bounded_score >= 45:
        bucket = "usable_with_caveat"
    else:
        bucket = "evidence_summary_or_gap"
    return {
        "claim_rank_score": bounded_score,
        "claim_rank_bucket": bucket,
        "memo_readiness": bucket,
        "claim_rank_reasons": reasons[:6],
        "claim_rank_policy": "specialist_claim_card_ranker_v0_3",
        "claim_rank_input_index": index,
    }


def _agent_expected_memo_slot(agent_id: str) -> str:
    return {
        "fundamental_analyst": "fundamentals",
        "industry_supply_chain_analyst": "industry_relationship",
        "market_valuation_analyst": "market_valuation",
        "risk_counterevidence_analyst": "risk_counterevidence",
        FOCUSED_ANSWER_SYNTHESIZER_AGENT_ID: "fundamentals",
    }.get(str(agent_id or ""), "")


def _claim_source_scope_penalty(claim_type: str, source_families: list[str]) -> int:
    families = set(source_families)
    normalized_type = str(claim_type or "").strip()
    if normalized_type in {"reported_financial_fact", "company_reported_financial_fact"} and families & CONTEXT_ONLY_SOURCE_FAMILIES:
        return 24
    if "relationship_graph" in families and normalized_type not in RELATIONSHIP_GRAPH_ALLOWED_CLAIM_TYPES:
        return 20
    if "market_snapshot" in families and normalized_type in {"company_reported_financial_fact", "reported_financial_fact"}:
        return 20
    return 0


def _claim_implication_score(claim_text: str) -> tuple[int, str]:
    text = str(claim_text or "").strip().lower()
    if not text:
        return -20, "empty_claim"
    score = 0
    if 45 <= len(text) <= 320:
        score += 4
    elif len(text) < 24:
        score -= 8
    elif len(text) > 520:
        score -= 6
    implication_terms = (
        "supports",
        "weakens",
        "implies",
        "suggests",
        "therefore",
        "because",
        "driver",
        "risk",
        "pressure",
        "upside",
        "downside",
        "thesis",
        "估值",
        "风险",
        "压力",
        "支撑",
        "削弱",
        "意味着",
        "因此",
        "驱动",
        "反证",
    )
    row_summary_terms = (
        "row shows",
        "table shows",
        "evidence shows",
        "reported",
        "disclosed",
        "the row",
        "the table",
        "表格",
        "披露",
        "显示",
    )
    has_implication = any(term in text for term in implication_terms)
    has_summary = any(term in text for term in row_summary_terms)
    if has_implication:
        score += 10
    if has_summary and not has_implication:
        score -= 8
        return score, "row_summary_without_implication"
    return score, "investment_implication" if has_implication else ""


def _claim_text_is_gap_like(claim_text: str) -> bool:
    text = str(claim_text or "").lower()
    return any(
        term in text
        for term in (
            "not found",
            "not available",
            "insufficient evidence",
            "no bounded evidence",
            "cannot determine",
            "missing evidence",
            "缺少",
            "未找到",
            "证据不足",
            "无法判断",
        )
    )


def _cap_unsupported_claims_by_agent(claims: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    by_agent_count: dict[str, int] = {}
    overflow_by_agent: dict[str, int] = {}
    for claim in claims:
        agent_id = str(claim.get("agent_id") or "unknown")
        count = by_agent_count.get(agent_id, 0)
        if count < UNSUPPORTED_CLAIM_CAP_PER_AGENT:
            visible.append(claim)
            by_agent_count[agent_id] = count + 1
            continue
        overflow_by_agent[agent_id] = overflow_by_agent.get(agent_id, 0) + 1
    return visible, {
        "cap_per_agent": UNSUPPORTED_CLAIM_CAP_PER_AGENT,
        "overflow_count": sum(overflow_by_agent.values()),
        "by_agent": overflow_by_agent,
    }


def _with_synthesized_thesis_claim(claims: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not claims:
        return claims, {"status": "skipped", "reason": "no_supported_claims"}
    existing = [claim for claim in claims if _normalize_memo_slot(claim.get("memo_slot")) == "thesis"]
    if existing:
        return claims, {
            "status": "not_needed",
            "reason": "existing_thesis_claim_present",
            "claim_ids": [str(item.get("claim_id") or "") for item in existing if str(item.get("claim_id") or "")],
        }
    business_slots = {"fundamentals", "industry_relationship", "market_valuation", "risk_counterevidence"}
    slot_claims = [
        claim
        for claim in claims
        if _normalize_memo_slot(claim.get("memo_slot")) in business_slots
        and _unique_strings(claim.get("evidence_refs") or claim.get("refs"))
    ]
    slot_count = len({_normalize_memo_slot(claim.get("memo_slot")) for claim in slot_claims})
    if slot_count < 2:
        return claims, {
            "status": "skipped",
            "reason": "insufficient_supported_business_slots",
            "supported_business_slot_count": slot_count,
        }

    selected = _select_thesis_source_claims(slot_claims)
    if len(selected) < 2:
        return claims, {
            "status": "skipped",
            "reason": "insufficient_source_claims_after_selection",
            "supported_business_slot_count": slot_count,
        }

    claim_id = "judgment_plan_aggregator_thesis_1"
    source_claim_ids = [str(item.get("claim_id") or "") for item in selected if str(item.get("claim_id") or "")]
    thesis_claim = {
        "claim": _synthesized_thesis_text(selected),
        "claim_type": "investment_thesis_synthesis",
        "ticker_scope": _unique_upper([ticker for item in selected for ticker in _unique_upper(item.get("ticker_scope") or item.get("tickers") or item.get("ticker"))]),
        "metric_scope": _unique_strings([metric for item in selected for metric in _unique_strings(item.get("metric_scope") or item.get("metrics") or item.get("metric"))]),
        "memo_slot": "thesis",
        "materiality": "high",
        "direction": _synthesized_direction(selected),
        "evidence_refs": _unique_strings([ref for item in selected for ref in _unique_strings(item.get("evidence_refs") or item.get("refs"))])[:8],
        "source_families": _unique_strings([family for item in selected for family in _unique_strings(item.get("source_families") or item.get("source_family"))]),
        "confidence": _synthesized_confidence(selected),
        "unsupported": False,
        "caveats": _unique_strings([caveat for item in selected for caveat in _unique_strings(item.get("caveats"))])[:4],
        "missing_confirmations": _unique_strings([gap for item in selected for gap in _unique_strings(item.get("missing_confirmations"))])[:4],
        "agent_id": "judgment_plan_aggregator",
        "claim_card_version": "v0.3",
        "claim_id": claim_id,
        "derived_from_claim_ids": source_claim_ids,
        "synthesis_policy": "no_new_facts_combine_existing_supported_claim_cards_only",
    }
    thesis_claim.update(_claim_card_rank_annotation(thesis_claim, -1))
    synthesis = {
        "status": "synthesized",
        "claim_id": claim_id,
        "derived_from_claim_ids": source_claim_ids,
        "supported_business_slot_count": slot_count,
        "policy": thesis_claim["synthesis_policy"],
    }
    return [thesis_claim, *claims], synthesis


def _select_thesis_source_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_slots: set[str] = set()
    slot_order = ["fundamentals", "industry_relationship", "market_valuation", "risk_counterevidence"]
    for slot in slot_order:
        for claim in claims:
            if _normalize_memo_slot(claim.get("memo_slot")) != slot or slot in seen_slots:
                continue
            selected.append(claim)
            seen_slots.add(slot)
            break
        if len(selected) >= 4:
            break
    return selected


def _synthesized_thesis_text(claims: list[dict[str, Any]]) -> str:
    parts = [str(item.get("claim") or "").strip() for item in claims if str(item.get("claim") or "").strip()]
    if not parts:
        return "The thesis is bounded by verified specialist claims and current source limitations."
    return " ".join(part.rstrip(".") + "." for part in parts[:4])


def _synthesized_direction(claims: list[dict[str, Any]]) -> str:
    directions = [_normalize_direction(item.get("direction")) for item in claims]
    material = [direction for direction in directions if direction not in {"unknown", "neutral"}]
    if not material:
        return "unknown"
    return material[0] if len(set(material)) == 1 else "mixed"


def _synthesized_confidence(claims: list[dict[str, Any]]) -> str:
    scores = [_confidence_score(item.get("confidence")) for item in claims]
    if not scores:
        return "unknown"
    min_score = min(scores)
    if min_score >= 3:
        return "high"
    if min_score >= 2:
        return "medium"
    if min_score >= 1:
        return "low"
    return "unknown"


def _claim_rank_key(claim: Mapping[str, Any], index: int) -> tuple[int, int, int, int, int, int]:
    bucket_priority = {"memo_ready": 3, "usable_with_caveat": 2, "evidence_summary_or_gap": 1}
    return (
        -bucket_priority.get(str(claim.get("claim_rank_bucket") or ""), 0),
        -_bounded_int(claim.get("claim_rank_score"), default=0, minimum=0, maximum=100),
        -_materiality_score(claim.get("materiality")),
        -_confidence_score(claim.get("confidence")),
        -_source_strength_score(claim.get("source_families") or claim.get("source_family")),
        index,
    )


def _memo_outline_from_claims(
    claims: list[Mapping[str, Any]],
    *,
    source_agent_ids: list[str],
    blocked_specialist_agents: list[str],
) -> list[dict[str, Any]]:
    slots = _expected_memo_slots(source_agent_ids)
    by_slot: dict[str, list[Mapping[str, Any]]] = {slot: [] for slot in slots}
    for claim in claims:
        slot = _normalize_memo_slot(claim.get("memo_slot"))
        by_slot.setdefault(slot, []).append(claim)
    outline = []
    for slot in slots:
        slot_claims = by_slot.get(slot) or []
        agent_id = _slot_agent(slot)
        missing_reason = ""
        if not slot_claims:
            missing_reason = "specialist_blocked" if agent_id in blocked_specialist_agents else "no_supported_claim_from_active_specialist"
        outline.append(
            {
                "memo_slot": slot,
                "section_title": _memo_slot_title(slot),
                "status": "supported" if slot_claims else "missing_or_partial",
                "claim_ids": [str(item.get("claim_id") or "") for item in slot_claims if str(item.get("claim_id") or "")],
                "primary_evidence_refs": _unique_strings(
                    [ref for item in slot_claims[:3] for ref in _unique_strings(item.get("evidence_refs"))]
                ),
                "supported_claim_count": len(slot_claims),
                "missing_reason": missing_reason,
            }
        )
    return outline


def _memo_thesis_plan_from_claims(
    *,
    supported_claims: list[dict[str, Any]],
    memo_outline: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    unsupported_claims: list[dict[str, Any]],
    source_boundary_notes: list[dict[str, Any]],
) -> dict[str, Any]:
    thesis_claim = _primary_thesis_claim(supported_claims)
    business_claims = [claim for claim in supported_claims if _normalize_memo_slot(claim.get("memo_slot")) != "thesis"]
    supported_slots = [row for row in memo_outline if row.get("status") == "supported"]
    status = "ready" if thesis_claim and len(supported_slots) >= 2 else "partial" if supported_claims else "blocked"
    sections = []
    for row in memo_outline:
        slot = str(row.get("memo_slot") or "")
        slot_claims = [claim for claim in supported_claims if _normalize_memo_slot(claim.get("memo_slot")) == slot]
        sections.append(
            {
                "memo_slot": slot,
                "section_title": str(row.get("section_title") or _memo_slot_title(slot)),
                "status": str(row.get("status") or ""),
                "objective": _memo_slot_objective(slot),
                "claim_ids": [str(item.get("claim_id") or "") for item in slot_claims[:3] if str(item.get("claim_id") or "")],
                "primary_evidence_refs": _unique_strings([ref for item in slot_claims[:3] for ref in _unique_strings(item.get("evidence_refs"))])[:8],
                "required_caveats": _unique_strings([caveat for item in slot_claims[:3] for caveat in _unique_strings(item.get("caveats"))])[:4],
                "missing_reason": str(row.get("missing_reason") or ""),
            }
        )
    return {
        "schema_version": "sec_agent_memo_thesis_plan_v0.1",
        "status": status,
        "primary_thesis_claim_id": str((thesis_claim or {}).get("claim_id") or ""),
        "primary_thesis": str((thesis_claim or {}).get("claim") or ""),
        "thesis_direction": _normalize_direction((thesis_claim or {}).get("direction")),
        "thesis_evidence_refs": _unique_strings((thesis_claim or {}).get("evidence_refs"))[:8],
        "supporting_claim_ids": [str(item.get("claim_id") or "") for item in business_claims[:8] if str(item.get("claim_id") or "")],
        "risk_or_counter_claim_ids": [
            str(item.get("claim_id") or "")
            for item in business_claims
            if _normalize_memo_slot(item.get("memo_slot")) == "risk_counterevidence" and str(item.get("claim_id") or "")
        ][:4],
        "section_sequence": sections,
        "conflict_count": len(conflicts),
        "unsupported_claim_count": len(unsupported_claims),
        "source_boundary_note_count": len(source_boundary_notes),
        "plan_policy": "claim_card_ranked_thesis_first_no_new_facts_v0_1",
    }


def _primary_thesis_claim(claims: list[dict[str, Any]]) -> dict[str, Any] | None:
    for claim in claims:
        if _normalize_memo_slot(claim.get("memo_slot")) == "thesis":
            return claim
    return claims[0] if claims else None


def _memo_thesis_pack_from_claims(
    *,
    supported_claims: list[dict[str, Any]],
    memo_outline: list[dict[str, Any]],
    memo_thesis_plan: Mapping[str, Any],
    conflicts: list[dict[str, Any]],
    unsupported_claims: list[dict[str, Any]],
    source_boundary_notes: list[dict[str, Any]],
) -> dict[str, Any]:
    thesis_claim = _primary_thesis_claim(supported_claims) or {}
    supporting_drivers = []
    for slot in ("fundamentals", "industry_relationship", "market_valuation", "risk_counterevidence"):
        slot_claims = [claim for claim in supported_claims if _normalize_memo_slot(claim.get("memo_slot")) == slot]
        if not slot_claims:
            continue
        supporting_drivers.append(
            {
                "memo_slot": slot,
                "section_title": _memo_slot_title(slot),
                "driver": _memo_pack_claim(slot_claims[0]),
                "supporting_claim_count": len(slot_claims),
            }
        )
    counterarguments = [
        _memo_pack_claim(claim)
        for claim in supported_claims
        if _normalize_memo_slot(claim.get("memo_slot")) == "risk_counterevidence"
    ][:3]
    counterarguments.extend(
        {
            "claim_id": "",
            "memo_slot": "risk_counterevidence",
            "claim": str(item.get("claim") or ""),
            "reason": str(item.get("reason") or ""),
            "evidence_refs": _unique_strings(item.get("evidence_refs"))[:4],
            "source_families": _unique_strings(item.get("source_families"))[:4],
        }
        for item in conflicts[:2]
    )
    source_claim_refs = _unique_strings(
        [
            ref
            for claim in [thesis_claim, *[row.get("driver") or {} for row in supporting_drivers], *counterarguments]
            if isinstance(claim, Mapping)
            for ref in _unique_strings(claim.get("evidence_refs"))
        ]
    )
    supported_slots = [
        str(row.get("memo_slot") or "")
        for row in memo_outline
        if isinstance(row, Mapping) and str(row.get("status") or "") == "supported"
    ]
    source_family_counts: dict[str, int] = {}
    for claim in supported_claims:
        for family in _unique_strings(claim.get("source_families")):
            source_family_counts[family] = source_family_counts.get(family, 0) + 1
    return {
        "schema_version": MEMO_THESIS_PACK_SCHEMA_VERSION,
        "status": str(memo_thesis_plan.get("status") or ("ready" if thesis_claim else "blocked")),
        "core_thesis": _memo_pack_claim(thesis_claim),
        "supporting_drivers": supporting_drivers[:4],
        "counterarguments": counterarguments[:4],
        "watch_items": _memo_thesis_pack_watch_items(
            supported_claims=supported_claims,
            unsupported_claims=unsupported_claims,
            source_boundary_notes=source_boundary_notes,
        ),
        "evidence_strength_map": {
            "supported_claim_count": len(supported_claims),
            "supported_memo_slots": supported_slots,
            "source_family_counts": source_family_counts,
            "source_boundary_note_count": len(source_boundary_notes),
        },
        "source_boundary": "verified ClaimCards only; relationship and industry rows are scope/context evidence, not reported financial facts",
        "source_claim_refs": source_claim_refs[:12],
        "pack_policy": "deterministic_thesis_pack_from_verified_claim_cards_v0_1",
    }


def _memo_pack_claim(claim: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(claim.get("claim_id") or ""),
        "memo_slot": _normalize_memo_slot(claim.get("memo_slot")),
        "claim": str(claim.get("claim") or ""),
        "claim_type": str(claim.get("claim_type") or ""),
        "direction": _normalize_direction(claim.get("direction")),
        "materiality": _normalize_materiality(claim.get("materiality")),
        "ticker_scope": _unique_upper(claim.get("ticker_scope"))[:6],
        "metric_scope": _unique_strings(claim.get("metric_scope"))[:6],
        "evidence_refs": _unique_strings(claim.get("evidence_refs"))[:6],
        "source_families": _unique_strings(claim.get("source_families"))[:5],
        "caveats": _unique_strings(claim.get("caveats"))[:3],
        "missing_confirmations": _unique_strings(claim.get("missing_confirmations"))[:3],
        "claim_rank_score": _bounded_int(claim.get("claim_rank_score"), default=0, minimum=0, maximum=100),
        "claim_rank_bucket": str(claim.get("claim_rank_bucket") or ""),
    }


def _memo_thesis_pack_watch_items(
    *,
    supported_claims: list[dict[str, Any]],
    unsupported_claims: list[dict[str, Any]],
    source_boundary_notes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(kind: str, text: str, *, claim_id: str = "", agent_id: str = "") -> None:
        clean = str(text or "").strip()
        key = f"{kind}:{claim_id}:{clean}".lower()
        if not clean or key in seen or len(items) >= 8:
            return
        seen.add(key)
        items.append({"type": kind, "claim_id": claim_id, "agent_id": agent_id, "text": clean})

    for claim in supported_claims:
        for item in _unique_strings(claim.get("missing_confirmations"))[:2]:
            add("missing_confirmation", item, claim_id=str(claim.get("claim_id") or ""), agent_id=str(claim.get("agent_id") or ""))
    for item in unsupported_claims[:3]:
        add("unsupported_excluded", str(item.get("reason") or item.get("claim") or ""), agent_id=str(item.get("agent_id") or ""))
    for note in source_boundary_notes[:3]:
        add(
            "source_boundary",
            str(note.get("reason") or note.get("note") or note.get("source_family") or ""),
            agent_id=str(note.get("agent_id") or ""),
        )
    return items


def _memo_slot_objective(slot: str) -> str:
    return {
        "thesis": "State the bounded investment thesis using verified ClaimCards only.",
        "fundamentals": "Explain company-reported financial evidence and what it implies for the thesis.",
        "industry_relationship": "Use relationship or industry evidence as scope and mechanism context, not as reported financial fact.",
        "market_valuation": "Add timestamped market or valuation context without overwriting SEC facts.",
        "risk_counterevidence": "Present downside evidence, conflicts, and missing confirmations that constrain the thesis.",
        "evidence_gap": "Name missing evidence that prevents stronger claims.",
        "caveat": "Preserve source and comparability caveats.",
    }.get(slot, "Use the verified ClaimCards for this memo section.")


def _expected_memo_slots(agent_ids: list[str]) -> list[str]:
    slots = ["thesis"]
    agent_slot = {
        "fundamental_analyst": "fundamentals",
        "industry_supply_chain_analyst": "industry_relationship",
        "market_valuation_analyst": "market_valuation",
        "risk_counterevidence_analyst": "risk_counterevidence",
        FOCUSED_ANSWER_SYNTHESIZER_AGENT_ID: "fundamentals",
    }
    for agent_id in agent_ids:
        slot = agent_slot.get(agent_id)
        if slot and slot not in slots:
            slots.append(slot)
    return slots


def _slot_agent(slot: str) -> str:
    return {
        "fundamentals": "fundamental_analyst",
        "industry_relationship": "industry_supply_chain_analyst",
        "market_valuation": "market_valuation_analyst",
        "risk_counterevidence": "risk_counterevidence_analyst",
    }.get(slot, "")


def _memo_slot_title(slot: str) -> str:
    return {
        "thesis": "Thesis",
        "fundamentals": "Fundamentals",
        "industry_relationship": "Industry and Relationship Evidence",
        "market_valuation": "Market and Valuation Context",
        "risk_counterevidence": "Risks and Counterevidence",
        "evidence_gap": "Evidence Gaps",
        "caveat": "Caveats",
    }.get(slot, slot.replace("_", " ").title())


def _claim_card_stats(claims: list[Mapping[str, Any]], memo_outline: list[Mapping[str, Any]]) -> dict[str, Any]:
    rank_scores = [_bounded_int(item.get("claim_rank_score"), default=0, minimum=0, maximum=100) for item in claims]
    return {
        "supported_claim_count": len(claims),
        "high_materiality_claim_count": sum(1 for item in claims if _normalize_materiality(item.get("materiality")) == "high"),
        "memo_ready_claim_count": sum(1 for item in claims if str(item.get("claim_rank_bucket") or "") == "memo_ready"),
        "usable_with_caveat_claim_count": sum(1 for item in claims if str(item.get("claim_rank_bucket") or "") == "usable_with_caveat"),
        "evidence_summary_or_gap_claim_count": sum(1 for item in claims if str(item.get("claim_rank_bucket") or "") == "evidence_summary_or_gap"),
        "avg_claim_rank_score": round(sum(rank_scores) / len(rank_scores), 2) if rank_scores else 0.0,
        "memo_slot_count": len(memo_outline),
        "supported_memo_slot_count": sum(1 for item in memo_outline if item.get("status") == "supported"),
        "synthesized_thesis_claim_count": sum(
            1
            for item in claims
            if str(item.get("agent_id") or "") == "judgment_plan_aggregator"
            and _normalize_memo_slot(item.get("memo_slot")) == "thesis"
        ),
    }


def _claim_type_for_source_scope(claim_type: Any, source_families: Any) -> str:
    normalized = str(claim_type or "business_observation").strip()
    families = set(_unique_strings(source_families))
    if "relationship_graph" in families and normalized not in RELATIONSHIP_GRAPH_ALLOWED_CLAIM_TYPES:
        return "relationship_hypothesis"
    return normalized


def _materiality_score(value: Any) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(_normalize_materiality(value), 0)


def _confidence_score(value: Any) -> int:
    return {"high": 3, "medium": 2, "low": 1, "unknown": 0}.get(_normalize_confidence(value), 0)


def _source_strength_score(value: Any) -> int:
    families = set(_unique_strings(value))
    if "primary_sec_filing" in families:
        return 4
    if "company_authored_unaudited_sec_filing" in families:
        return 3
    if "market_snapshot" in families:
        return 2
    if "industry_snapshot" in families:
        return 2
    if "relationship_graph" in families:
        return 1
    return 0


def build_multi_agent_memo_draft(
    judgment_plan: Mapping[str, Any] | None = None,
    *,
    specialist_verification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    judgment = dict(judgment_plan or {})
    verification = dict(specialist_verification or {})
    constraints = judgment.get("memo_constraints") if isinstance(judgment.get("memo_constraints"), Mapping) else {}
    supported = [dict(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)]
    conflicts = [dict(item) for item in judgment.get("conflicts") or [] if isinstance(item, Mapping)]
    unsupported = [dict(item) for item in judgment.get("unsupported_claims") or [] if isinstance(item, Mapping)]
    allowed = bool(judgment.get("memo_writer_allowed", True)) and bool(verification.get("memo_writer_allowed", True))
    common = {
        "schema_version": MEMO_DRAFT_SCHEMA_VERSION,
        "memo_writer_allowed": allowed,
        "consumed_input_views": ["verified_judgment_plan", "verified_summary"],
        "raw_rows_consumed": False,
        "tool_calls_requested": [],
        "source_boundary": _source_boundary_text(judgment),
        "source_boundary_notes": [dict(item) for item in judgment.get("source_boundary_notes") or [] if isinstance(item, Mapping)],
        "evidence_strength": _evidence_strength_summary(supported),
        "counterevidence": conflicts,
        "missing_evidence": list(constraints.get("missing_evidence") or []),
        "unsupported_claims_excluded": unsupported,
        "memo_constraints": dict(constraints),
        "memo_outline": [dict(item) for item in judgment.get("memo_outline") or [] if isinstance(item, Mapping)],
        "memo_thesis_plan": dict(judgment.get("memo_thesis_plan") or {}) if isinstance(judgment.get("memo_thesis_plan"), Mapping) else {},
        "memo_thesis_pack": dict(judgment.get("memo_thesis_pack") or {}) if isinstance(judgment.get("memo_thesis_pack"), Mapping) else {},
        "claim_card_stats": dict(judgment.get("claim_card_stats") or {}),
    }
    if not allowed:
        return {
            **common,
            "answer_status": "blocked_by_specialist_verification" if unsupported else "blocked_by_judgment_plan",
            "direct_answer": "Evidence constraints blocked full memo generation; only a bounded answer is allowed.",
            "supported_claims": [],
            "memo_claims": [],
            "caveats": _required_caveats(judgment),
            "bounded_answer_allowed": True,
        }
    memo_claims = [_memo_claim_from_supported_claim(item) for item in supported]
    return {
        **common,
        "answer_status": "draft",
        "direct_answer": _direct_answer_from_judgment(judgment, supported),
        "supported_claims": supported,
        "memo_claims": memo_claims,
        "caveats": _required_caveats(judgment),
        "bounded_answer_allowed": False,
        "memo_generation_policy": "thesis_led_claim_cards_v0_1",
    }


def verify_multi_agent_memo_draft(
    memo_draft: Mapping[str, Any] | None = None,
    judgment_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    memo = dict(memo_draft or {})
    judgment = dict(judgment_plan or {})
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if memo.get("raw_rows_consumed") or "bounded_evidence_rows" in memo or "context_rows" in memo:
        errors.append({"type": "memo_writer_raw_rows_forbidden"})
    if memo.get("tool_calls") or memo.get("tool_calls_requested"):
        errors.append({"type": "memo_writer_tool_calls_forbidden"})

    quality_errors, quality_warnings = _memo_quality_gate_findings(memo, judgment)
    errors.extend(quality_errors)
    warnings.extend(quality_warnings)

    rendered_text = _rendered_memo_text(memo)
    for item in judgment.get("unsupported_claims") or []:
        claim = str((item or {}).get("claim") if isinstance(item, Mapping) else item or "").strip()
        if claim and claim.lower() in rendered_text.lower():
            errors.append({"type": "unsupported_claim_entered_memo", "claim": claim})

    known_refs = _known_judgment_evidence_refs(judgment)
    supported_by_id = {
        str(claim.get("claim_id") or ""): claim
        for claim in judgment.get("supported_claims") or []
        if isinstance(claim, Mapping) and str(claim.get("claim_id") or "")
    }
    supported_numeric_scope = " ".join(_claim_scope_text(claim) for claim in supported_by_id.values())
    unknown_direct_tokens = sorted(_unknown_numeric_tokens(str(memo.get("direct_answer") or ""), supported_numeric_scope)) if supported_numeric_scope else []
    hard_unknown_direct_tokens = [token for token in unknown_direct_tokens if _is_material_numeric_token(token)]
    soft_unknown_direct_tokens = [token for token in unknown_direct_tokens if token not in hard_unknown_direct_tokens]
    if hard_unknown_direct_tokens:
        errors.append({"type": "memo_direct_answer_numeric_token_not_in_source_claims", "numeric_tokens": hard_unknown_direct_tokens[:8]})
    if soft_unknown_direct_tokens:
        warnings.append({"type": "memo_direct_answer_numeric_token_not_in_source_claims", "numeric_tokens": soft_unknown_direct_tokens[:8]})
    for index, claim in enumerate(_memo_claims(memo), start=1):
        refs = _unique_strings(claim.get("evidence_refs") or claim.get("refs"))
        if not refs and str(memo.get("answer_status") or "") != "blocked_by_specialist_verification":
            errors.append({"type": "memo_claim_without_evidence_refs", "index": index})
        unknown = sorted(set(refs) - known_refs) if known_refs else []
        if unknown:
            errors.append({"type": "memo_claim_unknown_evidence_refs", "index": index, "evidence_refs": unknown})
        claim_id = str(claim.get("claim_id") or "")
        source_claim = supported_by_id.get(claim_id)
        if source_claim:
            unknown_numeric_tokens = sorted(_unknown_numeric_tokens(str(claim.get("claim") or ""), _claim_scope_text(source_claim)))
            hard_unknown_tokens = [token for token in unknown_numeric_tokens if _is_material_numeric_token(token)]
            soft_unknown_tokens = [token for token in unknown_numeric_tokens if token not in hard_unknown_tokens]
            if hard_unknown_tokens:
                errors.append(
                    {
                        "type": "memo_claim_numeric_token_not_in_source_claim",
                        "index": index,
                        "claim_id": claim_id,
                        "numeric_tokens": hard_unknown_tokens[:8],
                    }
                )
            if soft_unknown_tokens:
                warnings.append(
                    {
                        "type": "memo_claim_numeric_token_not_in_source_claim",
                        "index": index,
                        "claim_id": claim_id,
                        "numeric_tokens": soft_unknown_tokens[:8],
                    }
                )
        source_families = set(_unique_strings(claim.get("source_families") or claim.get("source_family")))
        claim_type = str(claim.get("claim_type") or "").strip()
        if claim_type in {"reported_financial_fact", "company_reported_financial_fact"} and source_families & CONTEXT_ONLY_SOURCE_FAMILIES:
            errors.append(
                {
                    "type": "context_source_used_as_reported_financial_fact",
                    "index": index,
                    "source_families": sorted(source_families & CONTEXT_ONLY_SOURCE_FAMILIES),
                }
            )
        if (
            "market_snapshot" in source_families
            and (claim_type in {"market_context", "valuation_context"} or source_families <= {"market_snapshot"})
            and not str(claim.get("as_of_date") or "")
            and not _refs_contain_iso_date(refs)
        ):
            errors.append({"type": "market_claim_missing_as_of_date", "index": index})
        if "relationship_graph" in source_families and claim_type not in RELATIONSHIP_GRAPH_ALLOWED_CLAIM_TYPES:
            errors.append({"type": "relationship_graph_used_beyond_hypothesis", "index": index, "claim_type": claim_type})

    repair_instruction = _repair_instruction(errors)
    return {
        "schema_version": MEMO_VERIFICATION_SCHEMA_VERSION,
        "status": "fail" if errors else "pass",
        "unsupported_claim_count": len([item for item in errors if item.get("type") == "unsupported_claim_entered_memo"]),
        "errors": errors,
        "warnings": warnings,
        "repair_instruction": repair_instruction,
        "bounded_answer_allowed": bool(errors),
        "policy": "verifier_quality_gate_v0_2_inspect_only_no_new_facts_no_retrieval",
    }


def _memo_quality_gate_findings(
    memo: Mapping[str, Any],
    judgment: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    answer_status = str(memo.get("answer_status") or "")
    if answer_status.startswith("blocked_"):
        return errors, warnings

    supported_claims = [dict(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)]
    if not supported_claims:
        return errors, warnings

    thesis_plan = judgment.get("memo_thesis_plan") if isinstance(judgment.get("memo_thesis_plan"), Mapping) else {}
    memo_thesis_plan = memo.get("memo_thesis_plan") if isinstance(memo.get("memo_thesis_plan"), Mapping) else {}
    stats = judgment.get("claim_card_stats") if isinstance(judgment.get("claim_card_stats"), Mapping) else {}
    if not thesis_plan:
        warnings.append({"type": "memo_thesis_plan_missing_for_supported_claims"})
    elif not memo_thesis_plan:
        errors.append({"type": "memo_writer_did_not_carry_memo_thesis_plan"})
    else:
        expected_id = str(thesis_plan.get("primary_thesis_claim_id") or "")
        actual_id = str(memo_thesis_plan.get("primary_thesis_claim_id") or "")
        if expected_id and actual_id and expected_id != actual_id:
            errors.append(
                {
                    "type": "memo_primary_thesis_claim_id_mismatch",
                    "expected": expected_id,
                    "actual": actual_id,
                }
            )

    if thesis_plan and answer_status == "draft" and str(memo.get("memo_generation_policy") or "") != "thesis_led_claim_cards_v0_1":
        errors.append({"type": "memo_generation_policy_not_thesis_led"})

    memo_ready_count = int(stats.get("memo_ready_claim_count") or 0)
    if answer_status == "draft" and memo_ready_count == 0:
        warnings.append({"type": "memo_verified_but_no_memo_ready_claim_cards"})
    direct_answer = str(memo.get("direct_answer") or "")
    direct_answer_lower = direct_answer.lower()
    if any(marker in direct_answer_lower for marker in ("synthesized thesis", "bounded claimcards", "claimcard")):
        errors.append({"type": "memo_direct_answer_contains_internal_claimcard_language"})
    if direct_answer.count(" | ") >= 2:
        errors.append({"type": "memo_direct_answer_pipe_joined_claims"})
    duplicate_sentences = _duplicate_direct_answer_sentences(direct_answer)
    if duplicate_sentences:
        errors.append({"type": "memo_direct_answer_repeats_sentences", "duplicate_count": len(duplicate_sentences)})
    response_language = _memo_response_language(memo)
    if response_language == "zh-CN":
        offenders = _memo_non_chinese_user_facing_fields(memo)
        if offenders:
            errors.append(
                {
                    "type": "memo_zh_response_field_not_chinese",
                    "response_language": response_language,
                    "fields": offenders[:10],
                }
            )
    memo_profile = memo.get("memo_profile") if isinstance(memo.get("memo_profile"), Mapping) else {}
    profile = str(memo_profile.get("profile") or "compact")
    if profile in {"standard", "expanded", "deep_research"}:
        if not _memo_loose_items(memo.get("investment_implications")):
            errors.append({"type": "memo_profile_missing_investment_implications", "profile": profile})
        if not _memo_loose_items(memo.get("what_would_change_view")):
            errors.append({"type": "memo_profile_missing_what_would_change_view", "profile": profile})
        if not _memo_loose_items(memo.get("monitoring_items")):
            errors.append({"type": "memo_profile_missing_monitoring_items", "profile": profile})
    minimum_claim_count = 3 if len(supported_claims) >= 3 else 1
    actual_claim_count = len(_memo_claims(memo))
    if answer_status == "draft" and minimum_claim_count > 1 and actual_claim_count < minimum_claim_count:
        errors.append(
            {
                "type": "memo_too_few_claims_for_ready_thesis_pack",
                "minimum_claim_count": minimum_claim_count,
                "actual_claim_count": actual_claim_count,
            }
        )

    high_rank_claims = [
        claim
        for claim in supported_claims
        if str(claim.get("claim_rank_bucket") or "") == "memo_ready"
        or _bounded_int(claim.get("claim_rank_score"), default=0, minimum=0, maximum=100) >= 70
    ]
    if high_rank_claims:
        memo_refs = {
            ref
            for claim in _memo_claims(memo)
            for ref in _unique_strings(claim.get("evidence_refs") or claim.get("refs"))
        }
        high_rank_refs = {
            ref
            for claim in high_rank_claims[:4]
            for ref in _unique_strings(claim.get("evidence_refs") or claim.get("refs"))
        }
        if high_rank_refs and not (memo_refs & high_rank_refs):
            warnings.append(
                {
                    "type": "memo_does_not_surface_high_rank_claim_refs",
                    "high_rank_claim_count": len(high_rank_claims),
                }
            )
    return errors, warnings


def _duplicate_direct_answer_sentences(value: str) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", str(value or "")):
        normalized = re.sub(r"\s+", " ", sentence.strip().lower())
        if len(normalized) < 40:
            continue
        if normalized in seen:
            duplicates.append(sentence.strip())
        seen.add(normalized)
    return duplicates


def _memo_loose_items(value: Any) -> list[str]:
    items: list[str] = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, Mapping):
            text = str(item.get("text") or item.get("claim") or item.get("reason") or "").strip()
        else:
            text = str(item or "").strip()
        if text:
            items.append(text)
    return items


def _memo_response_language(memo: Mapping[str, Any]) -> str:
    value = memo.get("response_language")
    if isinstance(value, Mapping):
        return _normalize_response_language(value.get("language"))
    return _normalize_response_language(value)


def _normalize_response_language(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("_", "-")
    if raw in {"zh", "zh-cn", "zh-hans", "chinese", "simplified-chinese", "simplified chinese", "中文", "简体中文"}:
        return "zh-CN"
    if raw in {"en", "en-us", "en-gb", "english", "英文"}:
        return "en-US"
    return ""


def _memo_non_chinese_user_facing_fields(memo: Mapping[str, Any]) -> list[str]:
    offenders: list[str] = []
    fields: list[tuple[str, Any]] = [
        ("direct_answer", memo.get("direct_answer")),
        ("source_boundary", memo.get("source_boundary")),
    ]
    for index, claim in enumerate(_memo_claims(memo), start=1):
        if isinstance(claim, Mapping):
            fields.append((f"memo_claims[{index}].claim", claim.get("claim") or claim.get("text")))
    for key in (
        "investment_implications",
        "what_would_change_view",
        "monitoring_items",
        "evidence_gaps_but_actionable",
        "caveats",
        "unsupported_claims_excluded",
        "source_boundary_notes",
    ):
        for index, text in enumerate(_memo_loose_items(memo.get(key)), start=1):
            fields.append((f"{key}[{index}]", text))
    for field, text in fields:
        if _requires_chinese_text(text) and not _looks_chinese_user_text(str(text or "")):
            offenders.append(field)
    return offenders


def _requires_chinese_text(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    stripped = re.sub(r"\[[^\]]+\]", " ", text)
    stripped = re.sub(r"\b(?:[A-Z]{1,6}|10-[KQ]|8-K|GAAP|SEC|FY\d{2,4}|Q[1-4])\b", " ", stripped)
    return len(stripped.strip()) >= 16


def _looks_chinese_user_text(value: str) -> bool:
    text = str(value or "")
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    if cjk_count >= 8:
        return True
    latin_text = re.sub(r"\b(?:[A-Z]{1,6}|10-[KQ]|8-K|GAAP|SEC|FY\d{2,4}|Q[1-4])\b", " ", text)
    latin_words = len(re.findall(r"[A-Za-z]{3,}", latin_text))
    return cjk_count >= 4 and cjk_count >= latin_words


def _claim_scope_text(claim: Mapping[str, Any]) -> str:
    return " ".join(
        [
            str(claim.get("claim") or ""),
            " ".join(_unique_strings(claim.get("caveats"))),
            " ".join(_unique_strings(claim.get("missing_confirmations"))),
        ]
    )


def _unknown_numeric_tokens(candidate_text: str, source_text: str) -> set[str]:
    source_tokens = _numeric_token_details(source_text)
    source_strings = {item[0] for item in source_tokens}
    unknown: set[str] = set()
    for token, value, unit in _numeric_token_details(candidate_text):
        if token in source_strings:
            continue
        if any(_numeric_values_close(value, unit, source_value, source_unit) for _, source_value, source_unit in source_tokens):
            continue
        unknown.add(token)
    return unknown


def _numeric_tokens(text: str) -> set[str]:
    return {token for token, _, _ in _numeric_token_details(text)}


def _numeric_token_details(text: str) -> list[tuple[str, float, str]]:
    tokens: list[tuple[str, float, str]] = []
    expanded_text = _expand_numeric_ranges(str(text or ""))
    for match in re.finditer(
        r"(?<![A-Za-z0-9])[-+]?\$?\d+(?:,\d{3})*(?:\.\d+)?\s*(?:percentage\s+points?|个百分点|亿美元|百万美元|万美元|%|x|X|倍|M|B|K|bn|mn|million|billion|ppt)?",
        expanded_text,
    ):
        token = match.group(0).strip().lower().replace("$", "").replace(",", "")
        token = re.sub(r"\s+", " ", token).strip()
        parsed = re.match(r"([-+]?\d+(?:\.\d+)?)\s*(.*)", token)
        if token and parsed:
            value, unit = _normalize_numeric_value_and_unit(float(parsed.group(1)), str(parsed.group(2) or ""))
            tokens.append((token.replace(" ", ""), value, unit))
    return tokens


def _expand_numeric_ranges(text: str) -> str:
    unit_pattern = r"(percentage\s+points?|个百分点|亿美元|百万美元|万美元|%|x|X|倍|M|B|K|bn|mn|million|billion|ppt)"

    def _replace(match: re.Match[str]) -> str:
        left = match.group("left")
        right = match.group("right")
        unit = match.group("unit")
        return f"{left}{unit} {right}{unit}"

    return re.sub(
        rf"(?P<left>\$?\d+(?:,\d{{3}})*(?:\.\d+)?)\s*[-–]\s*(?P<right>\$?\d+(?:,\d{{3}})*(?:\.\d+)?)\s*(?P<unit>{unit_pattern})",
        _replace,
        str(text or ""),
        flags=re.IGNORECASE,
    )


def _normalize_numeric_value_and_unit(value: float, unit: str) -> tuple[float, str]:
    normalized = str(unit or "").strip().lower().replace(" ", "")
    if normalized in {"b", "bn", "billion"}:
        return value, "b"
    if normalized in {"m", "mn", "million"}:
        return value / 1000.0, "b"
    if normalized == "k":
        return value / 1_000_000.0, "b"
    if normalized == "亿美元":
        return value / 10.0, "b"
    if normalized == "百万美元":
        return value / 1000.0, "b"
    if normalized == "万美元":
        return value / 100000.0, "b"
    if normalized in {"x", "倍"}:
        return value, "x"
    if normalized in {"%", "percentagepoint", "percentagepoints", "ppt", "个百分点"}:
        return value, "pp" if normalized != "%" else "%"
    return value, normalized


def _numeric_values_close(left_value: float, left_unit: str, right_value: float, right_unit: str) -> bool:
    if left_unit != right_unit:
        return False
    diff = abs(left_value - right_value)
    return diff <= max(0.5, abs(right_value) * 0.005)


def _is_material_numeric_token(token: str) -> bool:
    parsed = re.match(r"([-+]?\d+(?:\.\d+)?)\s*(.*)", str(token or "").strip().lower())
    if not parsed:
        return False
    value = abs(float(parsed.group(1)))
    _, unit = _normalize_numeric_value_and_unit(value, str(parsed.group(2) or ""))
    if unit in {"%", "pp", "x", "b"}:
        return True
    return False


def _refs_contain_iso_date(refs: list[str]) -> bool:
    return any(re.search(r"\b20\d{2}-\d{2}-\d{2}\b", str(ref or "")) for ref in refs)


def repair_multi_agent_memo_draft(
    memo_draft: Mapping[str, Any] | None = None,
    verification_report: Mapping[str, Any] | None = None,
    judgment_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    memo = dict(memo_draft or {})
    report = dict(verification_report or {})
    judgment = dict(judgment_plan or {})
    errors = [dict(item) for item in report.get("errors") or [] if isinstance(item, Mapping)]
    if not errors:
        return memo

    repaired = dict(memo)
    repaired["raw_rows_consumed"] = False
    repaired["tool_calls_requested"] = []
    repaired.pop("tool_calls", None)
    repaired.pop("context_rows", None)
    repaired.pop("bounded_evidence_rows", None)
    if isinstance(judgment.get("memo_thesis_plan"), Mapping):
        repaired["memo_thesis_plan"] = dict(judgment.get("memo_thesis_plan") or {})
    if str(repaired.get("answer_status") or "") == "draft":
        repaired["memo_generation_policy"] = "thesis_led_claim_cards_v0_1"
    repaired["repair_policy"] = "bounded_deterministic_remove_or_downgrade_only"
    repaired["repair_source"] = "verifier_repair_loop"

    unsupported_texts = {
        str((item or {}).get("claim") or "").strip().lower()
        for item in judgment.get("unsupported_claims") or []
        if isinstance(item, Mapping) and str(item.get("claim") or "").strip()
    }
    known_refs = _known_judgment_evidence_refs(judgment)
    filtered_claims: list[dict[str, Any]] = []
    removed_claims: list[dict[str, Any]] = []
    for claim in _memo_claims(repaired):
        text = str(claim.get("claim") or "").strip()
        refs = _unique_strings(claim.get("evidence_refs") or claim.get("refs"))
        source_families = set(_unique_strings(claim.get("source_families") or claim.get("source_family")))
        claim_type = str(claim.get("claim_type") or "").strip()
        remove_reason = ""
        if not refs:
            remove_reason = "missing_evidence_refs"
        elif known_refs and sorted(set(refs) - known_refs):
            remove_reason = "unknown_evidence_refs"
        elif text.lower() in unsupported_texts:
            remove_reason = "unsupported_claim_text"
        elif claim_type in {"reported_financial_fact", "company_reported_financial_fact"} and source_families & CONTEXT_ONLY_SOURCE_FAMILIES:
            remove_reason = "context_source_used_as_financial_fact"
        elif "market_snapshot" in source_families and not str(claim.get("as_of_date") or "") and not _refs_contain_iso_date(refs):
            remove_reason = "market_claim_missing_as_of_date"

        if remove_reason:
            removed_claims.append({"claim": text, "reason": remove_reason})
            continue
        filtered_claims.append(dict(claim))

    repaired["memo_claims"] = filtered_claims
    repaired["supported_claims"] = filtered_claims
    repaired["removed_claims"] = removed_claims

    direct_answer = str(repaired.get("direct_answer") or "")
    for text in unsupported_texts:
        if text and text in direct_answer.lower():
            direct_answer = "Evidence constraints required removing unsupported text; use the supported claims and caveats only."
            break
    if not filtered_claims and str(repaired.get("answer_status") or "") == "draft":
        repaired["answer_status"] = "blocked_by_verifier_repair"
        repaired["bounded_answer_allowed"] = True
        repaired["direct_answer"] = "Evidence constraints blocked full memo generation after verifier repair."
    else:
        repaired["direct_answer"] = direct_answer
    repaired["verifier_repair_attempted"] = True
    return repaired


def _source_boundary_notes(
    *,
    evidence_requirement_plan: Mapping[str, Any] | None,
    reflection_report: Mapping[str, Any] | None,
    source_gaps: list[Mapping[str, Any]],
    memolets: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    families: list[str] = []
    plan = dict(evidence_requirement_plan or {})
    for requirement in plan.get("requirements") or []:
        if not isinstance(requirement, Mapping):
            continue
        families.extend(_unique_strings(requirement.get("source_families") or requirement.get("source_tiers")))
    reflection = dict(reflection_report or {})
    for item in reflection.get("source_family_gaps") or []:
        if isinstance(item, Mapping):
            families.extend(_unique_strings(item.get("source_family") or item.get("source_families")))
    for gap in source_gaps:
        families.extend(_unique_strings(gap.get("source_family") or gap.get("source_families") or gap.get("source_tier") or gap.get("source_tiers")))
    for memolet in memolets:
        for observation in memolet.get("observations") or []:
            if isinstance(observation, Mapping):
                families.extend(_unique_strings(observation.get("source_families") or observation.get("source_family")))

    notes = []
    for family in _unique_strings(families or ["primary_sec_filing"]):
        notes.append(
            {
                "source_family": family,
                "allowed_claim_scope": SOURCE_FAMILY_CLAIM_SCOPE.get(family, "bounded_context_only"),
                "prohibited_use": _source_prohibited_use(family),
            }
        )
    missing = [dict(item) for item in reflection.get("missing_requirements") or [] if isinstance(item, Mapping)]
    if missing:
        notes.append(
            {
                "source_family": "coverage_gap",
                "allowed_claim_scope": "must_caveat_missing_evidence",
                "missing_requirement_count": len(missing),
                "prohibited_use": "do_not_present_missing_evidence_as_supported",
            }
        )
    return notes


def _memo_constraints(
    *,
    validation_errors: list[dict[str, Any]],
    supported_claims: list[dict[str, Any]],
    unsupported_claims: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    blocked_specialist_agents: list[str],
    reflection_report: Mapping[str, Any] | None,
    source_boundary_notes: list[dict[str, Any]],
    tool_ledger_summary: Mapping[str, Any] | None,
    verifier_constraints: Mapping[str, Any] | None,
    unsupported_claim_overflow: Mapping[str, Any] | None = None,
    thesis_synthesis: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    reflection = dict(reflection_report or {})
    verifier = dict(verifier_constraints or {})
    blocked_reasons: list[str] = []
    if validation_errors:
        blocked_reasons.append("specialist_validation_errors")
    if unsupported_claims and not supported_claims:
        blocked_reasons.append("unsupported_specialist_claims_without_supported_claims")
    if verifier.get("memo_writer_allowed") is False:
        blocked_reasons.append("verifier_constraints_block_memo")
    missing_evidence = [dict(item) for item in reflection.get("missing_requirements") or [] if isinstance(item, Mapping)]
    required_caveats = []
    if blocked_specialist_agents:
        required_caveats.append("state_failed_specialist_and_partial_scope")
    if unsupported_claims:
        required_caveats.append("exclude_unsupported_specialist_claims_and_render_as_limitations")
    if conflicts:
        required_caveats.append("preserve_counterevidence_and_conflicts")
    if missing_evidence:
        required_caveats.append("state_missing_evidence_and_bounded_answer_scope")
    if reflection.get("bounded_answer_allowed"):
        required_caveats.append("bounded_answer_only_until_gaps_close")
    overflow = dict(unsupported_claim_overflow or {})
    if int(overflow.get("overflow_count") or 0) > 0:
        required_caveats.append("additional_unsupported_claims_summarized_not_expanded")
    return {
        "memo_writer_allowed": not blocked_reasons,
        "blocked_reasons": blocked_reasons,
        "allowed_input_views": ["verified_judgment_plan", "verified_summary"],
        "forbidden_inputs": ["raw_rows", "physical_paths", "tool_calls", "retrieval_requests"],
        "required_caveats": required_caveats,
        "missing_evidence": missing_evidence,
        "conflict_count": len(conflicts),
        "unsupported_claim_count": len(unsupported_claims),
        "unsupported_claim_overflow_count": int(overflow.get("overflow_count") or 0),
        "unsupported_claim_overflow_by_agent": dict(overflow.get("by_agent") or {}),
        "blocked_specialist_agents": list(blocked_specialist_agents),
        "source_boundary_count": len(source_boundary_notes),
        "tool_ledger_summary": dict(tool_ledger_summary or {}),
        "thesis_synthesis": dict(thesis_synthesis or {}),
        "repair_policy": "repair_only_against_existing_verified_plan_no_new_facts",
    }


def _source_prohibited_use(source_family: str) -> str:
    if source_family == "market_snapshot":
        return "do_not_use_as_company_reported_financial_fact"
    if source_family == "industry_snapshot":
        return "do_not_use_as_company_specific_reported_fact"
    if source_family == "relationship_graph":
        return "do_not_use_as_financial_fact_or_confirmed_customer_supplier_claim"
    if source_family == "company_authored_unaudited_sec_filing":
        return "do_not_restate_as_audited_financial_statement"
    return "do_not_exceed_bounded_evidence"


def _source_boundary_text(judgment: Mapping[str, Any]) -> str:
    notes = [dict(item) for item in judgment.get("source_boundary_notes") or [] if isinstance(item, Mapping)]
    if not notes:
        return "bounded verified judgment plan only"
    return "; ".join(
        f"{item.get('source_family')}: {item.get('allowed_claim_scope')}"
        for item in notes[:6]
    )


def _evidence_strength_summary(supported_claims: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    for item in supported_claims:
        confidence = _normalize_confidence(item.get("confidence"))
        counts[confidence] = counts.get(confidence, 0) + 1
    return counts


def _required_caveats(judgment: Mapping[str, Any]) -> list[dict[str, Any]]:
    constraints = judgment.get("memo_constraints") if isinstance(judgment.get("memo_constraints"), Mapping) else {}
    caveats = [{"type": "source_boundary", "text": _source_boundary_text(judgment)}]
    caveats.extend({"type": "required", "text": str(item)} for item in constraints.get("required_caveats") or [])
    for agent_id in _unique_strings(judgment.get("blocked_specialist_agents") or constraints.get("blocked_specialist_agents")):
        caveats.append(
            {
                "type": "specialist_route_failed",
                "agent_id": agent_id,
                "text": f"{agent_id} did not produce accepted specialist output; treat that analytical lens as partial.",
            }
        )
    for unsupported in judgment.get("unsupported_claims") or []:
        if isinstance(unsupported, Mapping):
            caveats.append(
                {
                    "type": "unsupported_excluded",
                    "text": str(unsupported.get("claim") or ""),
                    "reason": str(unsupported.get("reason") or ""),
                }
            )
    for conflict in judgment.get("conflicts") or []:
        if isinstance(conflict, Mapping):
            caveats.append({"type": "counterevidence", "text": str(conflict.get("claim") or ""), "reason": str(conflict.get("reason") or "")})
    return caveats


def _memo_claim_from_supported_claim(item: Mapping[str, Any]) -> dict[str, Any]:
    source_families = _unique_strings(item.get("source_families") or item.get("source_family"))
    return {
        "claim_id": str(item.get("claim_id") or ""),
        "claim": str(item.get("claim") or ""),
        "claim_type": _claim_type_for_source_scope(item.get("claim_type"), source_families),
        "evidence_refs": _unique_strings(item.get("evidence_refs") or item.get("refs")),
        "source_families": source_families,
        "confidence": _normalize_confidence(item.get("confidence")),
        "agent_id": str(item.get("agent_id") or ""),
        "ticker_scope": _unique_upper(item.get("ticker_scope") or item.get("tickers") or item.get("ticker")),
        "metric_scope": _unique_strings(item.get("metric_scope") or item.get("metrics") or item.get("metric")),
        "memo_slot": _normalize_memo_slot(item.get("memo_slot")),
        "materiality": _normalize_materiality(item.get("materiality")),
        "direction": _normalize_direction(item.get("direction")),
        "missing_confirmations": _unique_strings(item.get("missing_confirmations")),
        "snapshot_id": str(item.get("snapshot_id") or ""),
        "as_of_date": str(item.get("as_of_date") or ""),
        "period_role": str(item.get("period_role") or ""),
        "derived_from_claim_ids": _unique_strings(item.get("derived_from_claim_ids")),
        "synthesis_policy": str(item.get("synthesis_policy") or ""),
    }


def _direct_answer_from_supported_claims(supported_claims: list[dict[str, Any]]) -> str:
    if not supported_claims:
        return "No supported specialist claim is available; provide only bounded source limitations."
    claims = [str(item.get("claim") or "").strip() for item in supported_claims if str(item.get("claim") or "").strip()]
    return " ".join(claims[:3]) if claims else "Supported evidence exists, but no concise claim text was provided."


def _direct_answer_from_judgment(judgment: Mapping[str, Any], supported_claims: list[dict[str, Any]]) -> str:
    plan = judgment.get("memo_thesis_plan") if isinstance(judgment.get("memo_thesis_plan"), Mapping) else {}
    primary = str(plan.get("primary_thesis") or "").strip()
    if primary:
        return _clean_synthesized_thesis_prefix(primary)
    return _direct_answer_from_supported_claims(supported_claims)


def _clean_synthesized_thesis_prefix(value: str) -> str:
    cleaned = str(value or "").replace("Synthesized thesis from bounded ClaimCards: ", "").strip()
    return cleaned.replace(" | ", " ")


def _known_judgment_evidence_refs(judgment: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    for key in ("supported_claims", "conflicts"):
        for item in judgment.get(key) or []:
            if isinstance(item, Mapping):
                refs.update(_unique_strings(item.get("evidence_refs") or item.get("refs")))
    return refs


def _memo_claims(memo: Mapping[str, Any]) -> list[dict[str, Any]]:
    claims = []
    for key in ("memo_claims", "supported_claims"):
        for item in memo.get(key) or []:
            if isinstance(item, Mapping):
                claims.append(dict(item))
    return claims


def _rendered_memo_text(memo: Mapping[str, Any]) -> str:
    parts = [
        memo.get("direct_answer"),
        memo.get("thesis"),
        memo.get("memo_text"),
    ]
    for key in ("sections", "supported_claims", "memo_claims"):
        for item in memo.get(key) or []:
            if isinstance(item, Mapping):
                parts.append(item.get("title"))
                parts.append(item.get("claim"))
                parts.append(item.get("text"))
            else:
                parts.append(str(item or ""))
    return "\n".join(str(item or "") for item in parts)


def _repair_instruction(errors: list[dict[str, Any]]) -> str:
    if not errors:
        return ""
    types = {str(item.get("type") or "") for item in errors}
    if "unsupported_claim_entered_memo" in types:
        return "Remove unsupported claim text from user-facing memo and keep it only in excluded/blocked metadata."
    if "context_source_used_as_reported_financial_fact" in types:
        return "Downgrade market/industry/relationship content to context or hypothesis; do not use it as company reported financial fact."
    if "market_claim_missing_as_of_date" in types:
        return "Add market snapshot as_of_date or remove the market claim."
    if "memo_writer_tool_calls_forbidden" in types or "memo_writer_raw_rows_forbidden" in types:
        return "Regenerate memo from verified_judgment_plan only; do not include raw rows or tool calls."
    if types & {"memo_thesis_plan_missing_for_supported_claims", "memo_writer_did_not_carry_memo_thesis_plan", "memo_generation_policy_not_thesis_led"}:
        return "Regenerate memo as a thesis-led ClaimCard memo and carry memo_thesis_plan from the verified judgment plan."
    if types & {"memo_direct_answer_contains_internal_claimcard_language", "memo_direct_answer_pipe_joined_claims"}:
        return "Rewrite direct_answer as a natural user-facing investment paragraph; do not copy internal ClaimCard labels or pipe-joined claim text."
    if "memo_direct_answer_repeats_sentences" in types:
        return "Rewrite direct_answer once without repeated sentences; keep the same supported facts and evidence boundary."
    if "memo_zh_response_field_not_chinese" in types:
        return "Rewrite all user-facing memo prose in Simplified Chinese while preserving tickers, numbers, metric identifiers, form names, and evidence_refs."
    if types & {
        "memo_profile_missing_investment_implications",
        "memo_profile_missing_what_would_change_view",
        "memo_profile_missing_monitoring_items",
    }:
        return "Fill the required memo profile fields: investment_implications, what_would_change_view, and monitoring_items using only verified memo claims."
    return "Regenerate memo within verified judgment plan constraints."


def _normalize_observation(payload: Mapping[str, Any]) -> dict[str, Any]:
    source_families = _unique_strings(payload.get("source_families") or payload.get("source_family"))
    return {
        "claim": str(payload.get("claim") or "").strip(),
        "claim_type": _claim_type_for_source_scope(payload.get("claim_type"), source_families),
        "evidence_refs": _unique_strings(payload.get("evidence_refs") or payload.get("refs")),
        "source_families": source_families,
        "confidence": _normalize_confidence(payload.get("confidence")),
        "unsupported": bool(payload.get("unsupported")),
        "caveats": _unique_strings(payload.get("caveats")),
        "ticker_scope": _unique_upper(payload.get("ticker_scope") or payload.get("tickers") or payload.get("ticker")),
        "metric_scope": _unique_strings(payload.get("metric_scope") or payload.get("metrics") or payload.get("metric")),
        "memo_slot": _normalize_memo_slot(payload.get("memo_slot")),
        "materiality": _normalize_materiality(payload.get("materiality")),
        "direction": _normalize_direction(payload.get("direction")),
        "missing_confirmations": _unique_strings(payload.get("missing_confirmations")),
        "period_role": str(payload.get("period_role") or "").strip(),
        "snapshot_id": str(payload.get("snapshot_id") or "").strip(),
        "as_of_date": str(payload.get("as_of_date") or "").strip(),
    }


def _normalize_relationship(payload: Mapping[str, Any]) -> dict[str, Any]:
    ticker = str(payload.get("ticker") or payload.get("from_ticker") or "").upper().strip()
    related = str(payload.get("related_ticker") or payload.get("to_ticker") or payload.get("counterparty") or "").upper().strip()
    relationship_type = str(payload.get("relationship_type") or payload.get("type") or "other").strip()
    direction = str(payload.get("direction") or payload.get("edge_direction") or "unknown").strip()
    evidence_refs = _unique_strings(payload.get("evidence_refs") or payload.get("refs"))
    edge_id = str(payload.get("edge_id") or _relationship_edge_id(ticker, related, relationship_type, direction, evidence_refs)).strip()
    metrics = _unique_strings(payload.get("metrics_to_check") or payload.get("metric_links") or payload.get("required_metrics"))
    return {
        "edge_schema_version": str(payload.get("edge_schema_version") or RELATIONSHIP_EDGE_SCHEMA_VERSION).strip(),
        "edge_id": edge_id,
        "ticker": ticker,
        "related_ticker": related,
        "from_ticker": str(payload.get("from_ticker") or ticker).upper().strip(),
        "to_ticker": str(payload.get("to_ticker") or related).upper().strip(),
        "relationship_type": relationship_type,
        "direction": direction,
        "edge_direction": direction,
        "financial_link_type": str(payload.get("financial_link_type") or "").strip(),
        "mechanism": str(payload.get("mechanism") or payload.get("financial_link_type") or relationship_type).strip(),
        "metrics_to_check": metrics,
        "metric_links": metrics,
        "evidence_source_needed": _unique_strings(payload.get("evidence_source_needed") or payload.get("source_families_needed")),
        "evidence_refs": evidence_refs,
        "source_record_ref": str(payload.get("source_record_ref") or (evidence_refs[0] if evidence_refs else "")).strip(),
        "source_pack_id": str(payload.get("source_pack_id") or "").strip(),
        "confidence": _normalize_confidence(payload.get("confidence")),
        "inference_level": _normalize_relationship_inference_level(payload.get("inference_level")),
        "confirmation_status": str(payload.get("confirmation_status") or "no_confirmed_direct_edge").strip(),
        "evidence_basis": _unique_strings(payload.get("evidence_basis")),
        "missing_confirmations": _unique_strings(payload.get("missing_confirmations")),
        "source_limitations": _unique_strings(payload.get("source_limitations")),
        "inclusion_rationale": str(payload.get("inclusion_rationale") or payload.get("rationale") or "").strip(),
        "claim_scope": str(payload.get("claim_scope") or "scope_or_hypothesis_only").strip(),
        "notes": str(payload.get("notes") or "").strip(),
    }


def _normalize_economic_entity(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ticker": str(payload.get("ticker") or payload.get("entity") or "").upper().strip(),
        "role": str(payload.get("role") or "").strip(),
        "evidence_refs": _unique_strings(payload.get("evidence_refs") or payload.get("refs")),
        "source_families": _unique_strings(payload.get("source_families") or payload.get("source_family")),
        "confidence": _normalize_confidence(payload.get("confidence")),
        "materiality": _normalize_materiality(payload.get("materiality")),
        "missing_confirmations": _unique_strings(payload.get("missing_confirmations")),
        "notes": str(payload.get("notes") or "").strip(),
    }


def _normalize_economic_link(payload: Mapping[str, Any]) -> dict[str, Any]:
    source = str(payload.get("source") or payload.get("source_entity") or payload.get("from") or "").strip()
    target = str(payload.get("target") or payload.get("target_entity") or payload.get("to") or "").strip()
    link_type = str(payload.get("link_type") or payload.get("type") or "unknown").strip()
    if link_type == "sector":
        link_type = "sector_hypothesis"
    return {
        "link_id": str(payload.get("link_id") or _economic_link_id(source, target, link_type, payload.get("evidence_refs"))).strip(),
        "source": source.upper() if _looks_like_ticker(source) else source,
        "target": target.upper() if _looks_like_ticker(target) else target,
        "link_type": link_type,
        "mechanism": str(payload.get("mechanism") or "").strip(),
        "direction": _normalize_economic_direction(payload.get("direction")),
        "materiality": _normalize_materiality(payload.get("materiality")),
        "confidence": _normalize_confidence(payload.get("confidence")),
        "metric_implications": _unique_strings(payload.get("metric_implications") or payload.get("metrics_to_check")),
        "evidence_refs": _unique_strings(payload.get("evidence_refs") or payload.get("refs")),
        "source_families": _unique_strings(payload.get("source_families") or payload.get("source_family")),
        "claim_scope": str(payload.get("claim_scope") or "economic_mechanism_hypothesis_only").strip(),
        "missing_confirmations": _unique_strings(payload.get("missing_confirmations")),
    }


def _normalize_economic_mechanism(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "driver": str(payload.get("driver") or "").strip(),
        "affected_entities": _unique_upper(payload.get("affected_entities") or payload.get("entities")),
        "metric_implications": _unique_strings(payload.get("metric_implications") or payload.get("metrics_to_check")),
        "confirming_indicators": _unique_strings(payload.get("confirming_indicators")),
        "disconfirming_indicators": _unique_strings(payload.get("disconfirming_indicators")),
        "evidence_refs": _unique_strings(payload.get("evidence_refs") or payload.get("refs")),
        "confidence": _normalize_confidence(payload.get("confidence")),
    }


def _normalize_investment_implication(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "claim": str(payload.get("claim") or "").strip(),
        "so_what": str(payload.get("so_what") or payload.get("investment_use") or "").strip(),
        "entity_scope": _unique_upper(payload.get("entity_scope") or payload.get("tickers")),
        "confidence": _normalize_confidence(payload.get("confidence")),
        "supporting_refs": _unique_strings(payload.get("supporting_refs") or payload.get("evidence_refs") or payload.get("refs")),
        "limiting_refs": _unique_strings(payload.get("limiting_refs")),
        "missing_confirmations": _unique_strings(payload.get("missing_confirmations")),
    }


def _normalize_boundary_note(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "type": str(payload.get("type") or "source_boundary").strip(),
        "severity": str(payload.get("severity") or "confidence_caveat").strip(),
        "note": str(payload.get("note") or payload.get("text") or "").strip(),
        "evidence_refs": _unique_strings(payload.get("evidence_refs") or payload.get("refs")),
    }


def _normalize_economic_direction(value: Any) -> str:
    direction = str(value or "unknown").strip().lower()
    return direction if direction in ECONOMIC_DIRECTIONS else "unknown"


def _normalize_relationship_inference_level(value: Any) -> str:
    text = str(value or "curated_input_unverified").strip().lower()
    allowed = {
        "confirmed_direct",
        "disclosed_indirect",
        "curated_input_unverified",
        "sector_inferred",
        "category_inferred",
        "user_scope_unverified",
        "unknown",
    }
    return text if text in allowed else "unknown"


def _economic_link_id(source: str, target: str, link_type: str, evidence_refs: Any) -> str:
    seed = "|".join([str(source or ""), str(target or ""), str(link_type or ""), ",".join(_unique_strings(evidence_refs))])
    return "econ_link_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _validate_refs(
    refs: list[str],
    *,
    known_refs: set[str],
    errors: list[dict[str, Any]],
    error_type: str,
    index: int,
) -> None:
    if not known_refs:
        return
    unknown = sorted(set(refs) - known_refs)
    if unknown:
        errors.append({"type": error_type, "index": index, "evidence_refs": unknown})


def _looks_like_ticker(value: Any) -> bool:
    text = str(value or "").strip()
    return text.isascii() and 1 <= len(text) <= 8 and text.replace(".", "").isalpha()


def _relationship_edge_id(
    ticker: str,
    related: str,
    relationship_type: str,
    direction: str,
    evidence_refs: list[str],
) -> str:
    seed = "|".join([ticker, related, relationship_type, direction, ",".join(evidence_refs)])
    return "rel_edge_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _normalize_claim_item(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {
            "type": str(value.get("type") or "").strip(),
            "claim": str(value.get("claim") or value.get("text") or "").strip(),
            "reason": str(value.get("reason") or "").strip(),
            "evidence_refs": _unique_strings(value.get("evidence_refs") or value.get("refs")),
        }
    return {"claim": str(value or "").strip(), "reason": "", "evidence_refs": []}


def _relationship_budget(payload: Mapping[str, Any]) -> dict[str, int]:
    return {
        "max_expanded_tickers": _bounded_int(payload.get("max_expanded_tickers"), default=12, minimum=1, maximum=50),
        "max_relationships": _bounded_int(payload.get("max_relationships"), default=24, minimum=1, maximum=100),
        "max_evidence_requirements": _bounded_int(payload.get("max_evidence_requirements"), default=24, minimum=1, maximum=100),
    }


def _relationship_scope_guard(payload: Mapping[str, Any], budget: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "relationship_evidence_required": bool(payload.get("relationship_evidence_required", True)),
        "source_inventory_required": bool(payload.get("source_inventory_required", True)),
        "financial_fact_policy": str(payload.get("financial_fact_policy") or "relationship_graph_hypothesis_only"),
        "max_expanded_tickers": int(budget.get("max_expanded_tickers") or 12),
        "physical_route_selection": "forbidden_for_universe_agent",
    }


def _inventory_tickers(source_inventory: Mapping[str, Any]) -> set[str]:
    candidates: list[Any] = []
    for key in ("available_tickers", "inventory_tickers", "covered_tickers", "universe_tickers"):
        value = source_inventory.get(key)
        if isinstance(value, Mapping):
            candidates.extend(value.keys())
        else:
            candidates.extend(_unique_strings(value))
    companies = source_inventory.get("companies")
    if isinstance(companies, Mapping):
        candidates.extend(companies.keys())
    elif isinstance(companies, list):
        for company in companies:
            if isinstance(company, Mapping):
                candidates.append(company.get("ticker") or company.get("symbol") or company.get("company_ticker"))
            else:
                candidates.append(company)
    if isinstance(source_inventory.get("source_inventory"), Mapping):
        candidates.extend(_inventory_tickers(source_inventory["source_inventory"]))
    return set(_unique_upper(candidates))


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def _normalize_confidence(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric >= 0.75:
            return "high"
        if numeric >= 0.4:
            return "medium"
        return "low"
    text = str(value or "").strip().lower()
    return text if text in CONFIDENCE_LEVELS else "unknown"


def _normalize_materiality(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"high", "medium", "low"}:
        return text
    if any(marker in text for marker in ("critical", "major", "primary", "thesis")):
        return "high"
    if any(marker in text for marker in ("moderate", "supporting", "secondary")):
        return "medium"
    if text:
        return "low"
    return "medium"


def _normalize_direction(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"positive", "negative", "mixed", "neutral", "unknown"}:
        return text
    if any(marker in text for marker in ("upside", "benefit", "improve", "growth", "favorable")):
        return "positive"
    if any(marker in text for marker in ("downside", "pressure", "decline", "risk", "adverse")):
        return "negative"
    if any(marker in text for marker in ("conflict", "offset", "mixed")):
        return "mixed"
    return "unknown"


def _normalize_memo_slot(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    allowed = {
        "thesis",
        "fundamentals",
        "industry_relationship",
        "market_valuation",
        "risk_counterevidence",
        "evidence_gap",
        "caveat",
    }
    return text if text in allowed else "thesis"


def _unique_strings(value: Any) -> list[str]:
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
    return [item.upper() for item in _unique_strings(value)]
