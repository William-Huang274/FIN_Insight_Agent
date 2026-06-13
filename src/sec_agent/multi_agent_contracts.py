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
THESIS_DRIVER_PACK_SCHEMA_VERSION = "sec_agent_thesis_driver_pack_v0.1"
ANALYST_DEPTH_GATE_SCHEMA_VERSION = "sec_agent_analyst_depth_gate_v0.1"
ECONOMIC_LINK_MAP_SCHEMA_VERSION = "sec_agent_economic_link_map_v0.1"
JUDGMENT_STATE_SCHEMA_VERSION = "sec_agent_judgment_state_v0.1"

SPECIALIST_AGENT_IDS = {
    "fundamental_analyst",
    "product_technology_analyst",
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
ANALYSIS_DIMENSION_ORDER = (
    "fundamentals",
    "product_and_production",
    "capital_and_financing",
    "competition_and_market_position",
    "industry_supply_chain",
    "risk_and_counterevidence",
    "evidence_gap",
)
RELATIONSHIP_EVIDENCE_SOURCES = {
    "primary_sec_filing",
    "company_authored_unaudited_sec_filing",
    "market_snapshot",
    "industry_snapshot",
    "relationship_graph",
}
CONTEXT_ONLY_SOURCE_FAMILIES = {
    "market_snapshot",
    "industry_snapshot",
    "relationship_graph",
    "public_source_context",
    "live_public_web_context",
    "milvus_semantic",
}
SOURCE_FAMILY_CLAIM_SCOPE = {
    "primary_sec_filing": "company_reported_financial_fact",
    "company_authored_unaudited_sec_filing": "management_commentary_or_unaudited_company_context",
    "market_snapshot": "market_or_valuation_context_only",
    "industry_snapshot": "industry_context_only",
    "company_product_evidence_graph": "company_product_evidence_row_level_authority",
    "public_source_context": "public_proxy_context_only",
    "live_public_web_context": "allowlisted_web_context_only",
    "milvus_semantic": "semantic_recall_supplement_only",
    "relationship_graph": "research_scope_or_hypothesis_only",
    "run_artifact": "audit_summary_only",
}
RELATIONSHIP_GRAPH_ALLOWED_CLAIM_TYPES = {
    "relationship_hypothesis",
    "scope_hypothesis",
    "industry_context_only",
    "investment_thesis_synthesis",
}
PRODUCT_KPI_CLAIM_TYPES = {
    "company_disclosed_product_kpi",
    "company_reported_product_fact",
    "product_kpi",
    "product_revenue",
    "product_sales",
    "product_operating_metric",
    "reported_financial_fact",
    "company_reported_financial_fact",
}
PRODUCT_CONTEXT_CLAIM_TYPES = {
    "product_taxonomy_context",
    "public_proxy_context",
    "source_gap",
    "business_observation",
    "unsupported_claim",
}
OWNERSHIP_REALTIME_FLOW_CLAIM_TYPES = {
    "realtime_flow",
    "real_time_flow",
    "fund_flow",
    "money_flow",
    "ownership_purchase_today",
}
MACRO_COMPANY_FACT_CLAIM_TYPES = {
    "company_revenue",
    "company_sales",
    "company_margin",
    "company_reported_macro_fact",
    "commercial_success",
    "product_sales",
    "sell_through",
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
            if observation["unsupported"] or _claim_text_is_source_quality_gap(observation["claim"]):
                unsupported_claims.append(
                    {
                        "agent_id": agent_id,
                        "claim": observation["claim"],
                        "reason": "source_quality_gap_not_supported_claim"
                        if _claim_text_is_source_quality_gap(observation["claim"])
                        else "marked_unsupported",
                        "evidence_refs": list(observation.get("evidence_refs") or []),
                    }
                )
            else:
                item.update(_claim_card_annotations(item, observation_index))
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
    thesis_driver_pack = _thesis_driver_pack_from_claims(
        supported_claims=supported_claims,
        memo_thesis_pack=memo_thesis_pack,
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
        "thesis_driver_pack": thesis_driver_pack,
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
    thesis_driver_pack = _thesis_driver_pack_from_claims(
        supported_claims=supported_claims,
        memo_thesis_pack=memo_thesis_pack,
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
        "thesis_driver_pack": thesis_driver_pack,
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


def refresh_judgment_plan_after_governance_filter(judgment_plan: Mapping[str, Any]) -> dict[str, Any]:
    """Refresh memo-facing plan fields after D-series fact gates filter ClaimCards."""

    judgment = dict(judgment_plan or {})
    supported_claims = [dict(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)]
    unsupported_claims = [dict(item) for item in judgment.get("unsupported_claims") or [] if isinstance(item, Mapping)]
    conflicts = [dict(item) for item in judgment.get("conflicts") or [] if isinstance(item, Mapping)]
    blocked_specialist_agents = _unique_strings(judgment.get("blocked_specialist_agents"))
    source_boundary_notes = [dict(item) for item in judgment.get("source_boundary_notes") or [] if isinstance(item, Mapping)]
    required_dimension_ids = _valid_analysis_dimension_ids(judgment.get("required_dimension_ids"))
    source_agent_ids = _unique_strings(judgment.get("source_agent_ids")) if supported_claims else []
    memo_outline = _memo_outline_from_claims(
        supported_claims,
        source_agent_ids=source_agent_ids,
        blocked_specialist_agents=blocked_specialist_agents,
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
    thesis_driver_pack = _thesis_driver_pack_from_claims(
        supported_claims=supported_claims,
        memo_thesis_pack=memo_thesis_pack,
        memo_thesis_plan=memo_thesis_plan,
        conflicts=conflicts,
        unsupported_claims=unsupported_claims,
        source_boundary_notes=source_boundary_notes,
        required_dimension_ids=required_dimension_ids,
    )
    thesis_synthesis = dict(judgment.get("thesis_synthesis") or {}) if isinstance(judgment.get("thesis_synthesis"), Mapping) else {}
    if thesis_synthesis:
        thesis_synthesis["supported_claim_count"] = len(supported_claims)
    return {
        **judgment,
        "source_agent_ids": source_agent_ids,
        "memo_outline": memo_outline,
        "memo_thesis_plan": memo_thesis_plan,
        "memo_thesis_pack": memo_thesis_pack,
        "thesis_driver_pack": thesis_driver_pack,
        "required_dimension_ids": required_dimension_ids,
        "claim_card_stats": _claim_card_stats(supported_claims, memo_outline),
        "thesis_synthesis": thesis_synthesis,
        "governance_filter_refresh_policy": "refresh_memo_pack_after_pre_memo_fact_selection_v0_1",
    }


def attach_judgment_state(
    judgment_plan: Mapping[str, Any],
    *,
    fundamental_statement_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    judgment = dict(judgment_plan or {})
    judgment["judgment_state"] = build_judgment_state(
        judgment,
        fundamental_statement_pack=fundamental_statement_pack or {},
    )
    return judgment


def build_judgment_state(
    judgment_plan: Mapping[str, Any],
    *,
    fundamental_statement_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    judgment = dict(judgment_plan or {})
    pack = judgment.get("thesis_driver_pack") if isinstance(judgment.get("thesis_driver_pack"), Mapping) else {}
    thesis_cards = [dict(item) for item in pack.get("thesis_cards") or [] if isinstance(item, Mapping)]
    dimensions = _dimension_analyses_from_thesis_driver_pack(pack)
    supported_claims = [dict(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)]
    unsupported_claims = [dict(item) for item in judgment.get("unsupported_claims") or [] if isinstance(item, Mapping)]
    gaps = [dict(item) for item in pack.get("gap_cards") or [] if isinstance(item, Mapping)]
    financial_pack = dict(fundamental_statement_pack or {})
    financial_summary = financial_pack.get("summary") if isinstance(financial_pack.get("summary"), Mapping) else {}
    industry_focus = (
        financial_pack.get("industry_focus_policy")
        if isinstance(financial_pack.get("industry_focus_policy"), Mapping)
        else {}
    )
    dimension_states = []
    for section in dimensions:
        dimension_id = str(section.get("dimension_id") or "")
        related_claim_ids = _unique_strings(section.get("claim_ids"))
        related_claims = [claim for claim in supported_claims if str(claim.get("claim_id") or "") in set(related_claim_ids)]
        dimension_states.append(
            {
                "dimension_id": dimension_id,
                "title": str(section.get("title") or _analysis_dimension_title(dimension_id)),
                "stance": _dimension_judgment_stance(related_claims, section),
                "support_level": _dimension_support_level(related_claims, section),
                "summary": str(section.get("summary") or ""),
                "business_mechanism": str(section.get("business_mechanism") or ""),
                "financial_bridge": str(section.get("financial_bridge") or ""),
                "counter_read": str(section.get("counter_read") or ""),
                "claim_ids": related_claim_ids[:8],
                "evidence_refs": _unique_strings(section.get("evidence_refs"))[:8],
                "gap_ids": _unique_strings(section.get("gap_ids"))[:6],
                "what_would_change_view": _unique_strings(section.get("what_would_change_view"))[:4],
            }
        )
    fundamental_state = _fundamental_judgment_state(financial_pack)
    if fundamental_state and not any(item.get("dimension_id") == "fundamentals" for item in dimension_states):
        dimension_states.insert(0, fundamental_state)
    state = {
        "schema_version": JUDGMENT_STATE_SCHEMA_VERSION,
        "status": "ready" if thesis_cards and dimension_states else "partial" if supported_claims else "blocked",
        "core_thesis": str((thesis_cards[0] if thesis_cards else {}).get("core_thesis") or ""),
        "stance": str((thesis_cards[0] if thesis_cards else {}).get("stance") or "unknown"),
        "confidence": str((thesis_cards[0] if thesis_cards else {}).get("confidence") or _synthesized_confidence(supported_claims)),
        "dimension_judgments": dimension_states[:8],
        "fundamental_statement_summary": {
            "schema_version": financial_pack.get("schema_version") or "",
            "pack_status": financial_summary.get("pack_status") or "",
            "line_item_count": financial_summary.get("line_item_count") or 0,
            "period_change_count": financial_summary.get("period_change_count") or 0,
            "peer_comparison_count": financial_summary.get("peer_comparison_count") or 0,
            "priority_metric_available_count": financial_summary.get("priority_metric_available_count") or 0,
            "priority_metric_missing_count": financial_summary.get("priority_metric_missing_count") or 0,
            "industry_id": industry_focus.get("industry_id") or "",
        },
        "gap_state": {
            "unsupported_claim_count": len(unsupported_claims),
            "gap_card_count": len(gaps),
            "public_or_commercial_gap_count": len(
                [
                    gap
                    for gap in [*gaps, *unsupported_claims]
                    if "gap" in str(gap.get("gap_type") or gap.get("claim_type") or gap.get("reason") or "").lower()
                    or "commercial" in str(gap.get("reason") or gap.get("statement") or "").lower()
                ]
            ),
            "top_gaps": [
                {
                    "gap_id": str(item.get("gap_id") or item.get("claim_id") or ""),
                    "statement": str(item.get("statement") or item.get("reason") or item.get("claim") or "")[:240],
                    "claim_boundary": str(item.get("claim_boundary") or ""),
                }
                for item in [*gaps, *unsupported_claims][:8]
            ],
        },
        "memo_writer_policy": "write_from_dimension_judgments_first_then_claim_cards_no_new_facts_v0_1",
    }
    state["validation"] = _validate_judgment_state(state)
    return state


def _fundamental_judgment_state(fundamental_statement_pack: Mapping[str, Any]) -> dict[str, Any]:
    if not fundamental_statement_pack:
        return {}
    summary = fundamental_statement_pack.get("summary") if isinstance(fundamental_statement_pack.get("summary"), Mapping) else {}
    industry_focus = (
        fundamental_statement_pack.get("industry_focus_policy")
        if isinstance(fundamental_statement_pack.get("industry_focus_policy"), Mapping)
        else {}
    )
    line_items = [dict(item) for item in fundamental_statement_pack.get("statement_line_items") or [] if isinstance(item, Mapping)]
    bridges = [dict(item) for item in fundamental_statement_pack.get("integration_bridges") or [] if isinstance(item, Mapping)]
    gaps = [dict(item) for item in fundamental_statement_pack.get("analysis_gaps") or [] if isinstance(item, Mapping)]
    if not line_items and not gaps:
        return {}
    return {
        "dimension_id": "fundamentals",
        "title": _analysis_dimension_title("fundamentals"),
        "stance": "mixed" if gaps else "supported",
        "support_level": "high" if int(summary.get("line_item_count") or 0) >= 4 else "medium" if line_items else "gap",
        "summary": (
            f"FundamentalStatementPack has {summary.get('line_item_count') or 0} line items, "
            f"{summary.get('period_change_count') or 0} period changes, and "
            f"{summary.get('peer_comparison_count') or 0} peer comparisons for "
            f"{industry_focus.get('industry_id') or 'general'} focus."
        ),
        "business_mechanism": "three_statement_quality_peer_context_and_product_or_capital_bridge",
        "financial_bridge": "income_statement_balance_sheet_cash_flow_statement",
        "counter_read": "missing_priority_metrics_or_peer_rows_limit_the_strength_of_the_financial_judgment" if gaps else "",
        "claim_ids": [],
        "evidence_refs": _unique_strings([ref for item in line_items[:8] for ref in _unique_strings(item.get("evidence_refs"))])[:8],
        "gap_ids": _unique_strings([str(item.get("gap_id") or "") for item in gaps])[:6],
        "what_would_change_view": [
            "Same-period peer rows for priority metrics",
            "Company-disclosed product/segment rows tied to financial statement metrics",
        ][: 1 + bool(bridges)],
    }


def _dimension_judgment_stance(claims: list[Mapping[str, Any]], section: Mapping[str, Any]) -> str:
    directions = {_normalize_direction(claim.get("direction")) for claim in claims}
    directions.discard("unknown")
    if "negative" in directions and "positive" in directions:
        return "mixed"
    if directions:
        return sorted(directions)[0]
    status = str(section.get("status") or "")
    return "supported" if status == "supported" else "gap_or_counter"


def _dimension_support_level(claims: list[Mapping[str, Any]], section: Mapping[str, Any]) -> str:
    if not claims:
        return "gap"
    scores = [_bounded_int(claim.get("claim_rank_score"), default=0, minimum=0, maximum=100) for claim in claims]
    if max(scores or [0]) >= 80 or len(claims) >= 3:
        return "high"
    if max(scores or [0]) >= 55 or len(claims) >= 2:
        return "medium"
    return "low"


def _validate_judgment_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if str(payload.get("schema_version") or "") != JUDGMENT_STATE_SCHEMA_VERSION:
        errors.append({"type": "unexpected_schema_version", "schema_version": payload.get("schema_version")})
    dimensions = [dict(item) for item in payload.get("dimension_judgments") or [] if isinstance(item, Mapping)]
    if not dimensions and str(payload.get("status") or "") != "blocked":
        warnings.append({"type": "judgment_state_without_dimension_judgments"})
    for index, item in enumerate(dimensions):
        if not str(item.get("dimension_id") or ""):
            errors.append({"type": "dimension_id_required", "index": index})
    return {
        "schema_version": "sec_agent_judgment_state_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
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
    thesis.update(_claim_card_annotations(thesis, -1))

    claims = [thesis]
    if selected_ledger:
        claim = _focused_ledger_claim(selected_ledger, tickers=tickers, response_language=response_language)
        claim.update(_claim_card_annotations(claim, 0))
        claims.append(claim)
    if selected_text:
        claim = _focused_context_claim(selected_text, tickers=tickers, response_language=response_language)
        claim.update(_claim_card_annotations(claim, 1))
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


def _claim_card_annotations(claim: Mapping[str, Any], index: int) -> dict[str, Any]:
    annotated = dict(_claim_card_rank_annotation(claim, index))
    annotated.update(_claim_card_depth_annotation({**dict(claim), **annotated}))
    return annotated


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
    if agent_id == "product_technology_analyst" and "company_product_evidence_graph" in set(source_families):
        score += 5
        reasons.append("product_graph_source_fit")
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


def _claim_card_depth_annotation(claim: Mapping[str, Any]) -> dict[str, Any]:
    dimension = _analysis_dimension_for_claim(claim)
    source_families = _unique_strings(claim.get("source_families") or claim.get("source_family"))
    depth = {
        "schema_version": "sec_agent_claim_card_analyst_depth_v0.1",
        "analysis_dimension": dimension,
        "analyst_angle": _analysis_dimension_title(dimension),
        "analysis_lens": _analysis_dimension_lens(dimension),
        "evidence_role": _depth_evidence_role(source_families, str(claim.get("claim_type") or "")),
        "business_mechanism": _business_mechanism_for_dimension(dimension),
        "financial_bridge": _financial_bridge_for_claim(claim, dimension),
        "comparison_basis": _comparison_basis_for_claim(claim),
        "counter_read": _counter_read_for_claim(claim),
    }
    return {
        "analysis_dimension": dimension,
        "analyst_angle": depth["analyst_angle"],
        "analyst_depth": depth,
    }


def _claim_analyst_depth(claim: Mapping[str, Any]) -> dict[str, Any]:
    depth = claim.get("analyst_depth") if isinstance(claim.get("analyst_depth"), Mapping) else None
    if depth is not None:
        return dict(depth)
    annotation = _claim_card_depth_annotation(claim).get("analyst_depth")
    return dict(annotation) if isinstance(annotation, Mapping) else {}


def _analysis_dimension_for_claim(claim: Mapping[str, Any]) -> str:
    slot = _normalize_memo_slot(claim.get("memo_slot"))
    metrics = " ".join(_unique_strings(claim.get("metric_scope") or claim.get("metrics") or claim.get("metric"))).lower()
    claim_type = str(claim.get("claim_type") or "").lower()
    agent_id = str(claim.get("agent_id") or "").lower()
    source_families = set(_unique_strings(claim.get("source_families") or claim.get("source_family")))
    text = f"{metrics} {claim_type} {agent_id} {str(claim.get('claim') or '').lower()}"
    if slot == "thesis":
        return "thesis_synthesis"
    if slot == "risk_counterevidence":
        return "risk_and_counterevidence"
    if slot == "industry_relationship":
        return "industry_supply_chain"
    if slot == "product_technology" or any(term in text for term in ("product", "unit", "shipment", "capacity", "backlog", "usage")):
        return "product_and_production"
    if any(
        term in text
        for term in (
            "capex",
            "capital expenditure",
            "debt",
            "borrow",
            "interest",
            "offering",
            "financing",
            "cash flow",
            "free cash flow",
            "liquidity",
        )
    ):
        return "capital_and_financing"
    if slot == "market_valuation" or any(
        term in text for term in ("valuation", "multiple", "share", "price", "market reaction", "peer", "competitor")
    ):
        return "competition_and_market_position"
    if slot == "industry_relationship" or "industry_snapshot" in source_families or "relationship_graph" in source_families:
        return "industry_supply_chain"
    if any(term in text for term in ("risk", "counter", "constraint", "decline", "pressure")):
        return "risk_and_counterevidence"
    if slot == "evidence_gap":
        return "evidence_gap"
    return "fundamentals"


def _analysis_dimension_title(dimension: str) -> str:
    return {
        "thesis_synthesis": "Synthesis",
        "fundamentals": "Fundamentals and financial quality",
        "product_and_production": "Product and production line evidence",
        "capital_and_financing": "Capital allocation and financing",
        "competition_and_market_position": "Competition and market position",
        "industry_supply_chain": "Industry and supply-chain transmission",
        "risk_and_counterevidence": "Risk and counterevidence",
        "evidence_gap": "Evidence gap",
    }.get(str(dimension or "").strip(), "Analyst dimension")


def _analysis_dimension_lens(dimension: str) -> str:
    return {
        "fundamentals": "Translate reported revenue, margin, cash-flow, and segment facts into earnings-quality support or pressure.",
        "product_and_production": "Connect product, capacity, unit, backlog, usage, or company-disclosed KPI evidence to the business line under analysis.",
        "capital_and_financing": "Bridge capex, debt, offering, cash-flow, and balance-sheet facts to reinvestment capacity and financing risk.",
        "competition_and_market_position": "Use valuation, market reaction, peer, share, and channel context only as market-position evidence within its source boundary.",
        "industry_supply_chain": "Map industry demand, customer/supplier, macro, and supply-chain proxies to company exposure without treating context as reported company fact.",
        "risk_and_counterevidence": "Identify what weakens the thesis, where the evidence is mixed, and what confirmation would change the view.",
        "evidence_gap": "State the missing public evidence that prevents a stronger conclusion.",
    }.get(str(dimension or "").strip(), "Explain the investment mechanism supported by verified evidence.")


def _depth_evidence_role(source_families: list[str], claim_type: str) -> str:
    families = set(source_families)
    if "primary_sec_filing" in families:
        return "reported_company_authority"
    if "company_product_evidence_graph" in families:
        return "company_product_authority"
    if "company_authored_unaudited_sec_filing" in families:
        return "management_commentary_context"
    if families & {"market_snapshot", "industry_snapshot"}:
        return "external_context_or_proxy"
    if families & {"public_source_context", "live_public_web_context", "milvus_semantic"}:
        return "public_proxy_or_recall_context"
    if "relationship_graph" in families or claim_type == "relationship_hypothesis":
        return "relationship_scope_hypothesis"
    return "verified_claim_card_context"


def _business_mechanism_for_dimension(dimension: str) -> str:
    return {
        "fundamentals": "The evidence supports or pressures earnings power through reported growth, margin, cash conversion, or segment mix.",
        "product_and_production": "The evidence links product adoption, capacity, units, backlog, usage, or product mix to the operating line being evaluated.",
        "capital_and_financing": "The evidence links reinvestment, leverage, issuance, or cash generation to future capacity and balance-sheet flexibility.",
        "competition_and_market_position": "The evidence frames relative positioning, market expectations, valuation debate, or competitive pressure.",
        "industry_supply_chain": "The evidence traces external demand or supply-chain exposure to the company's relevant products, segments, or counterparties.",
        "risk_and_counterevidence": "The evidence defines what could offset the thesis or lower confidence in the main business bridge.",
        "evidence_gap": "The evidence is insufficient for a stronger operating or financial conclusion.",
    }.get(str(dimension or "").strip(), "The evidence must be connected to a clear business mechanism before it supports the memo.")


def _financial_bridge_for_claim(claim: Mapping[str, Any], dimension: str) -> str:
    metrics = _unique_strings(claim.get("metric_scope") or claim.get("metrics") or claim.get("metric"))
    metric_text = ", ".join(metrics[:5])
    direction = _normalize_direction(claim.get("direction"))
    if metric_text:
        return f"Bridge the claim through {metric_text}; direction={direction}; do not infer unverified sales, share, or forecast values."
    if dimension == "product_and_production":
        return "Bridge product evidence to revenue, margin, inventory, capacity, or backlog only when the verified ClaimCard states the metric."
    if dimension == "capital_and_financing":
        return "Bridge capital evidence to capex, leverage, liquidity, interest burden, or issuance only when the verified ClaimCard states the metric."
    return "Financial bridge is qualitative unless verified metric_scope or numeric evidence is present."


def _comparison_basis_for_claim(claim: Mapping[str, Any]) -> str:
    tickers = _unique_upper(claim.get("ticker_scope") or claim.get("tickers") or claim.get("ticker"))
    metrics = _unique_strings(claim.get("metric_scope") or claim.get("metrics") or claim.get("metric"))
    period = str(claim.get("period_role") or claim.get("as_of_date") or "").strip()
    parts = []
    if tickers:
        parts.append(f"tickers={','.join(tickers[:6])}")
    if metrics:
        parts.append(f"metrics={','.join(metrics[:5])}")
    if period:
        parts.append(f"period={period}")
    return "; ".join(parts) if parts else "No explicit peer, metric, or period comparison basis supplied."


def _counter_read_for_claim(claim: Mapping[str, Any]) -> str:
    missing = _unique_strings(claim.get("missing_confirmations"))
    caveats = _unique_strings(claim.get("caveats"))
    if missing:
        return "Missing confirmation: " + "; ".join(missing[:2])
    if caveats:
        return "Caveat: " + "; ".join(caveats[:2])
    if _normalize_direction(claim.get("direction")) == "negative":
        return "This claim is counterevidence or risk evidence rather than support for the thesis."
    return "No explicit counter-read supplied; verifier must preserve source boundary."


def _agent_expected_memo_slot(agent_id: str) -> str:
    return {
        "fundamental_analyst": "fundamentals",
        "product_technology_analyst": "product_technology",
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
    if normalized_type in OWNERSHIP_REALTIME_FLOW_CLAIM_TYPES and families & {"public_source_context", "industry_snapshot", "milvus_semantic"}:
        return 32
    if normalized_type in MACRO_COMPANY_FACT_CLAIM_TYPES and families & {"industry_snapshot", "public_source_context", "milvus_semantic"}:
        return 30
    if normalized_type in PRODUCT_KPI_CLAIM_TYPES and families & {"public_source_context", "live_public_web_context", "milvus_semantic"}:
        return 28
    if "company_product_evidence_graph" in families and normalized_type in PRODUCT_CONTEXT_CLAIM_TYPES:
        return 0
    if "relationship_graph" in families and normalized_type not in RELATIONSHIP_GRAPH_ALLOWED_CLAIM_TYPES:
        return 20
    if "market_snapshot" in families and normalized_type in {"company_reported_financial_fact", "reported_financial_fact"}:
        return 20
    return 0


def _claim_type_tokens(claim: Mapping[str, Any]) -> set[str]:
    tokens = {
        str(claim.get("claim_type") or "").strip(),
        str(claim.get("raw_claim_type") or "").strip(),
    }
    for metric in _unique_strings(claim.get("metric_scope") or claim.get("metrics") or claim.get("metric")):
        metric_token = str(metric or "").strip()
        if metric_token in PRODUCT_KPI_CLAIM_TYPES | OWNERSHIP_REALTIME_FLOW_CLAIM_TYPES | MACRO_COMPANY_FACT_CLAIM_TYPES:
            tokens.add(metric_token)
    return {token for token in tokens if token}


def _text_suggests_ownership_realtime_flow(text: str) -> bool:
    value = str(text or "").lower()
    ownership_terms = ("13f", "13d", "13g", "ownership", "holding", "holdings", "持仓", "持有")
    realtime_terms = ("real-time", "realtime", "now buying", "buying today", "flow", "inflow", "outflow", "资金流", "实时", "正在买入")
    return any(term in value for term in ownership_terms) and any(term in value for term in realtime_terms)


def _text_suggests_macro_company_fact(text: str) -> bool:
    value = str(text or "").lower()
    macro_terms = ("macro", "fred", "fed funds", "interest rate", "rates", "oil price", "eia", "census", "宏观", "利率")
    company_fact_terms = (
        "company revenue",
        "reported revenue",
        "sales were",
        "margin was",
        "product sales",
        "commercial success",
        "sell-through",
        "公司收入",
        "公司销售",
        "利润率",
    )
    return any(term in value for term in macro_terms) and any(term in value for term in company_fact_terms)


def _text_suggests_channel_offer_sell_through(text: str) -> bool:
    value = str(text or "").lower()
    channel_terms = ("channel offer", "commerce", "ecommerce", "listing", "price", "availability", "电商", "报价", "渠道")
    sellthrough_terms = ("sell-through", "sell through", "sales volume", "channel inventory", "market share", "售罄率", "销量", "份额", "库存")
    return any(term in value for term in channel_terms) and any(term in value for term in sellthrough_terms)


def _text_suggests_field_inquiry_authority_fact(text: str) -> bool:
    value = str(text or "").lower()
    inquiry_terms = ("field inquiry", "inquiry note", "sales desk", "dealer quote", "询价", "访谈", "经销商")
    authority_terms = ("authority fact", "proves", "confirmed fact", "official fact", "权威事实", "证明", "确认")
    return any(term in value for term in inquiry_terms) and any(term in value for term in authority_terms)


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
            "garbled",
            "truncated",
            "nonsensical",
            "unreadable",
            "cannot be reliably interpreted",
            "cannot reliably interpret",
            "data quality gap",
            "source quality gap",
            "parse failure",
            "parser failed",
            "缺少",
            "未找到",
            "证据不足",
            "无法判断",
            "乱码",
            "截断",
            "无法可靠解读",
        )
    )


def _claim_text_is_source_quality_gap(claim_text: str) -> bool:
    text = str(claim_text or "").lower()
    return any(
        term in text
        for term in (
            "garbled",
            "truncated",
            "nonsensical",
            "unreadable",
            "cannot be reliably interpreted",
            "cannot reliably interpret",
            "data quality gap",
            "source quality gap",
            "parse failure",
            "parser failed",
            "乱码",
            "截断",
            "无法可靠解读",
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
    thesis_claim.update(_claim_card_annotations(thesis_claim, -1))
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
    for claim in claims:
        claim_slot = _normalize_memo_slot(claim.get("memo_slot"))
        if claim_slot and claim_slot not in slots:
            slots.append(claim_slot)
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
        "source_boundary": (
            "verified ClaimCards only; relationship, industry, public-source, and live-web rows are scope/context evidence; "
            "product KPI facts require company_product_evidence_graph exact-authority rows"
        ),
        "source_claim_refs": source_claim_refs[:12],
        "pack_policy": "deterministic_thesis_pack_from_verified_claim_cards_v0_1",
    }


def _thesis_driver_pack_from_claims(
    *,
    supported_claims: list[dict[str, Any]],
    memo_thesis_pack: Mapping[str, Any],
    memo_thesis_plan: Mapping[str, Any],
    conflicts: list[dict[str, Any]],
    unsupported_claims: list[dict[str, Any]],
    source_boundary_notes: list[dict[str, Any]],
    required_dimension_ids: list[str] | None = None,
) -> dict[str, Any]:
    thesis_claim = _primary_thesis_claim(supported_claims) or {}
    driver_cards: list[dict[str, Any]] = []
    counter_driver_cards: list[dict[str, Any]] = []
    gap_cards: list[dict[str, Any]] = []

    for index, claim in enumerate(supported_claims, start=1):
        slot = _normalize_memo_slot(claim.get("memo_slot"))
        if slot == "thesis":
            continue
        card = _thesis_driver_card(claim, index=index)
        if slot == "risk_counterevidence":
            counter_driver_cards.append({**card, "counter_driver_id": f"counter_{card['driver_id']}"})
        else:
            driver_cards.append(card)
        for missing in _unique_strings(claim.get("missing_confirmations"))[:2]:
            gap_cards.append(
                {
                    "gap_id": f"gap_missing_{str(claim.get('claim_id') or index)}_{len(gap_cards) + 1}",
                    "gap_type": "missing_confirmation",
                    "source_claim_id": str(claim.get("claim_id") or ""),
                    "statement": missing,
                    "evidence_refs": _unique_strings(claim.get("evidence_refs"))[:4],
                    "claim_boundary": "gap_only_not_supporting_fact",
                }
            )

    for index, conflict in enumerate(conflicts[:4], start=1):
        counter_driver_cards.append(
            {
                "counter_driver_id": f"counter_conflict_{index}",
                "driver_id": "",
                "source_claim_id": "",
                "agent_id": str(conflict.get("agent_id") or ""),
                "memo_slot": "risk_counterevidence",
                "driver_type": "conflict_or_counterevidence",
                "statement": str(conflict.get("claim") or conflict.get("reason") or ""),
                "direction": "negative",
                "materiality": "medium",
                "confidence": "medium",
                "metric_scope": _unique_strings(conflict.get("metric_scope"))[:6],
                "ticker_scope": _unique_upper(conflict.get("ticker_scope"))[:6],
                "evidence_refs": _unique_strings(conflict.get("evidence_refs"))[:6],
                "source_families": _unique_strings(conflict.get("source_families"))[:5],
                "claim_boundary": "counterevidence_or_conflict_only",
            }
        )

    for index, unsupported in enumerate(unsupported_claims[:6], start=1):
        gap_cards.append(
            {
                "gap_id": f"gap_unsupported_{index}",
                "gap_type": "unsupported_claim_excluded",
                "source_claim_id": str(unsupported.get("claim_id") or ""),
                "agent_id": str(unsupported.get("agent_id") or ""),
                "statement": str(unsupported.get("reason") or unsupported.get("claim") or ""),
                "evidence_refs": _unique_strings(unsupported.get("evidence_refs"))[:4],
                "claim_boundary": "excluded_from_memo_support",
            }
        )
    for index, note in enumerate(source_boundary_notes[:6], start=1):
        gap_cards.append(
            {
                "gap_id": f"gap_boundary_{index}",
                "gap_type": "source_boundary",
                "source_claim_id": "",
                "agent_id": str(note.get("agent_id") or ""),
                "source_family": str(note.get("source_family") or ""),
                "statement": str(note.get("reason") or note.get("note") or note.get("source_family") or ""),
                "evidence_refs": _unique_strings(note.get("evidence_refs"))[:4],
                "claim_boundary": "source_boundary_not_supporting_fact",
            }
        )
    required_dimension_ids = _valid_analysis_dimension_ids(required_dimension_ids)
    if required_dimension_ids:
        required_gaps = _required_dimension_gap_cards(
            required_dimension_ids=required_dimension_ids,
            supported_claims=supported_claims,
            counter_driver_cards=counter_driver_cards,
            gap_cards=gap_cards,
        )
        if required_gaps:
            existing_gap_ids = {str(card.get("gap_id") or "") for card in required_gaps}
            gap_cards = [*required_gaps, *[card for card in gap_cards if str(card.get("gap_id") or "") not in existing_gap_ids]]

    evidence_refs = _unique_strings(
        [
            ref
            for claim in supported_claims
            for ref in _unique_strings(claim.get("evidence_refs") or claim.get("refs"))
        ]
    )
    status = str(memo_thesis_pack.get("status") or memo_thesis_plan.get("status") or "")
    if not status:
        status = "ready" if thesis_claim and driver_cards else "partial" if supported_claims else "blocked"
    driver_ids = [str(card.get("driver_id") or "") for card in driver_cards if str(card.get("driver_id") or "")]
    counter_ids = [
        str(card.get("counter_driver_id") or "")
        for card in counter_driver_cards
        if str(card.get("counter_driver_id") or "")
    ]
    gap_ids = [str(card.get("gap_id") or "") for card in gap_cards if str(card.get("gap_id") or "")]
    core_thesis = memo_thesis_pack.get("core_thesis") if isinstance(memo_thesis_pack.get("core_thesis"), Mapping) else {}
    thesis_text = _clean_synthesized_thesis_prefix(str(core_thesis.get("claim") or thesis_claim.get("claim") or ""))
    if not thesis_text and supported_claims:
        thesis_text = _direct_answer_from_supported_claims(supported_claims)
    thesis_cards = [
        {
            "thesis_id": "thesis_1",
            "source_claim_id": str(thesis_claim.get("claim_id") or memo_thesis_plan.get("primary_thesis_claim_id") or ""),
            "core_thesis": thesis_text,
            "stance": _normalize_direction(thesis_claim.get("direction") or memo_thesis_plan.get("thesis_direction")),
            "confidence": _synthesized_confidence(supported_claims),
            "supporting_driver_ids": driver_ids[:8],
            "counter_driver_ids": counter_ids[:6],
            "gap_ids": gap_ids[:8],
            "evidence_refs": _unique_strings(thesis_claim.get("evidence_refs") or memo_thesis_plan.get("thesis_evidence_refs") or evidence_refs)[:8],
            "source_claim_ids": _unique_strings([str(claim.get("claim_id") or "") for claim in supported_claims])[:12],
            "what_would_change_the_view": _thesis_pack_view_change(counter_driver_cards, gap_cards),
        }
    ]
    dimension_sections = _dimension_sections_from_claims(
        supported_claims=supported_claims,
        counter_driver_cards=counter_driver_cards,
        gap_cards=gap_cards,
        source_boundary_notes=source_boundary_notes,
        required_dimension_ids=required_dimension_ids,
    )
    return {
        "schema_version": THESIS_DRIVER_PACK_SCHEMA_VERSION,
        "status": status,
        "present": bool(supported_claims),
        "thesis_cards": thesis_cards if thesis_text else [],
        "dimension_sections": dimension_sections,
        "required_dimension_ids": required_dimension_ids,
        "driver_cards": driver_cards[:8],
        "counter_driver_cards": counter_driver_cards[:6],
        "gap_cards": gap_cards[:10],
        "source_boundary_cards": _thesis_source_boundary_cards(supported_claims, source_boundary_notes),
        "evidence_ref_count": len(evidence_refs),
        "source_claim_refs": evidence_refs[:12],
        "pack_policy": "deterministic_dimension_driver_pack_from_verified_claim_cards_no_new_facts_v0_2",
    }


def _thesis_driver_card(claim: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    slot = _normalize_memo_slot(claim.get("memo_slot"))
    claim_id = str(claim.get("claim_id") or f"claim_{index}")
    return {
        "driver_id": f"driver_{claim_id}",
        "source_claim_id": claim_id,
        "agent_id": str(claim.get("agent_id") or ""),
        "memo_slot": slot,
        "driver_type": _driver_type_for_memo_slot(slot),
        "statement": str(claim.get("claim") or ""),
        "claim_type": str(claim.get("claim_type") or ""),
        "direction": _normalize_direction(claim.get("direction")),
        "materiality": _normalize_materiality(claim.get("materiality")),
        "confidence": _normalize_confidence(claim.get("confidence")),
        "metric_scope": _unique_strings(claim.get("metric_scope"))[:6],
        "ticker_scope": _unique_upper(claim.get("ticker_scope"))[:6],
        "evidence_refs": _unique_strings(claim.get("evidence_refs") or claim.get("refs"))[:6],
        "source_families": _unique_strings(claim.get("source_families") or claim.get("source_family"))[:5],
        "analysis_dimension": str(claim.get("analysis_dimension") or _analysis_dimension_for_claim(claim)),
        "analyst_angle": str(claim.get("analyst_angle") or _analysis_dimension_title(_analysis_dimension_for_claim(claim))),
        "analyst_depth": _claim_analyst_depth(claim),
        "claim_boundary": SOURCE_FAMILY_CLAIM_SCOPE.get(
            (_unique_strings(claim.get("source_families") or claim.get("source_family")) or [""])[0],
            "verified_claim_card_scope",
        ),
    }


def _driver_type_for_memo_slot(slot: str) -> str:
    return {
        "fundamentals": "fundamental_driver",
        "product_technology": "product_or_technology_driver",
        "industry_relationship": "industry_or_relationship_context_driver",
        "market_valuation": "market_or_valuation_context_driver",
        "risk_counterevidence": "risk_or_counter_driver",
    }.get(slot, "supporting_driver")


def _dimension_sections_from_claims(
    *,
    supported_claims: list[dict[str, Any]],
    counter_driver_cards: list[dict[str, Any]],
    gap_cards: list[dict[str, Any]],
    source_boundary_notes: list[dict[str, Any]],
    required_dimension_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    claim_dimension_by_id: dict[str, str] = {}
    for claim in supported_claims:
        slot = _normalize_memo_slot(claim.get("memo_slot"))
        if slot == "thesis":
            continue
        dimension = str(claim.get("analysis_dimension") or _analysis_dimension_for_claim(claim))
        if dimension == "thesis_synthesis":
            continue
        grouped.setdefault(dimension, []).append(claim)
        claim_id = str(claim.get("claim_id") or "")
        if claim_id:
            claim_dimension_by_id[claim_id] = dimension

    counter_dimensions = {
        _dimension_for_counter_card(card, claim_dimension_by_id)
        for card in counter_driver_cards
        if isinstance(card, Mapping)
    }
    gap_dimensions = {
        _dimension_for_gap_card(gap, claim_dimension_by_id)
        for gap in gap_cards
        if isinstance(gap, Mapping)
    }
    active_dimensions = set(grouped) | counter_dimensions | gap_dimensions
    required_dimensions = set(_valid_analysis_dimension_ids(required_dimension_ids))
    active_dimensions |= required_dimensions
    active_dimensions.discard("")
    dimensions = [item for item in ANALYSIS_DIMENSION_ORDER if item in active_dimensions]
    dimensions.extend(sorted(dimension for dimension in active_dimensions if dimension not in set(dimensions)))
    sections: list[dict[str, Any]] = []
    for dimension in dimensions:
        claims = grouped.get(dimension) or []
        claim_ids = _unique_strings([str(claim.get("claim_id") or "") for claim in claims])[:8]
        claim_id_set = set(claim_ids)
        related_gaps = [
            gap
            for gap in gap_cards
            if isinstance(gap, Mapping) and _dimension_for_gap_card(gap, claim_dimension_by_id) == dimension
        ]
        related_counters = [
            card
            for card in counter_driver_cards
            if isinstance(card, Mapping) and _dimension_for_counter_card(card, claim_dimension_by_id) == dimension
        ]
        if claim_id_set:
            related_gaps = [
                gap
                for gap in related_gaps
                if str(gap.get("source_claim_id") or "") in claim_id_set
                or str(gap.get("source_claim_id") or "") not in claim_dimension_by_id
            ]
            related_counters = [
                card
                for card in related_counters
                if str(card.get("source_claim_id") or "") in claim_id_set
                or str(card.get("source_claim_id") or "") not in claim_dimension_by_id
            ]
        if not claims and not related_gaps and not related_counters:
            continue
        primary = claims[0] if claims else {}
        evidence_refs = _unique_strings(
            [ref for claim in claims for ref in _unique_strings(claim.get("evidence_refs") or claim.get("refs"))]
            + [ref for card in related_counters for ref in _unique_strings(card.get("evidence_refs") or card.get("refs"))]
            + [ref for gap in related_gaps for ref in _unique_strings(gap.get("evidence_refs") or gap.get("refs"))]
        )
        primary_depth = primary.get("analyst_depth") if isinstance(primary.get("analyst_depth"), Mapping) else {}
        section_thesis = _dimension_section_thesis(dimension, claims, related_counters=related_counters, related_gaps=related_gaps)
        comparison_basis = []
        for claim in claims:
            depth = claim.get("analyst_depth") if isinstance(claim.get("analyst_depth"), Mapping) else {}
            comparison_basis.append(str(depth.get("comparison_basis") or ""))
        sections.append(
            {
                "dimension_id": dimension,
                "dimension_title": _analysis_dimension_title(dimension),
                "required_by_user": dimension in required_dimensions,
                "status": "supported" if claims else "gap_or_counterevidence",
                "section_thesis": section_thesis,
                "analysis_lens": str(primary_depth.get("analysis_lens") or _analysis_dimension_lens(dimension)),
                "business_mechanism": str(primary_depth.get("business_mechanism") or _business_mechanism_for_dimension(dimension)),
                "financial_bridge": str(primary_depth.get("financial_bridge") or _financial_bridge_for_claim(primary, dimension)),
                "comparison_basis": _unique_strings(comparison_basis)[:4],
                "competitive_read": _dimension_competitive_read(dimension, claims),
                "primary_claim_ids": claim_ids,
                "counter_claim_ids": _unique_strings([str(card.get("source_claim_id") or "") for card in related_counters])[:4],
                "gap_ids": _unique_strings([str(gap.get("gap_id") or "") for gap in related_gaps])[:5],
                "evidence_refs": evidence_refs[:8],
                "source_families": _unique_strings(
                    [
                        family
                        for claim in claims
                        for family in _unique_strings(claim.get("source_families") or claim.get("source_family"))
                    ]
                    + [
                        family
                        for card in related_counters
                        for family in _unique_strings(card.get("source_families") or card.get("source_family"))
                    ]
                    + [
                        str(gap.get("source_family") or "")
                        for gap in related_gaps
                        if str(gap.get("source_family") or "")
                    ]
                )[:6],
                "source_boundaries": _dimension_source_boundaries(claims, source_boundary_notes),
                "counter_read": _dimension_counter_read(claims, related_counters, related_gaps),
                "what_would_change_view": _dimension_view_change(claims, related_counters, related_gaps),
                "depth_status": (
                    "analysis_ready"
                    if len(claim_ids) >= 1 and evidence_refs
                    else "bounded_gap_or_counterevidence"
                    if related_counters or related_gaps
                    else "insufficient_evidence"
                ),
            }
        )
    return sections[:8]


def _valid_analysis_dimension_ids(values: Any) -> list[str]:
    valid = set(ANALYSIS_DIMENSION_ORDER)
    normalized: list[str] = []
    for item in _unique_strings(values):
        dimension = str(item).strip().lower().replace("-", "_").replace(" ", "_")
        if dimension in valid and dimension not in normalized:
            normalized.append(dimension)
    return normalized


def _required_dimension_gap_cards(
    *,
    required_dimension_ids: list[str],
    supported_claims: list[dict[str, Any]],
    counter_driver_cards: list[dict[str, Any]],
    gap_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    claim_dimension_by_id: dict[str, str] = {}
    active_dimensions: set[str] = set()
    for claim in supported_claims:
        dimension = str(claim.get("analysis_dimension") or _analysis_dimension_for_claim(claim))
        if dimension and dimension != "thesis_synthesis":
            active_dimensions.add(dimension)
        claim_id = str(claim.get("claim_id") or "")
        if claim_id and dimension:
            claim_dimension_by_id[claim_id] = dimension
    for card in counter_driver_cards:
        if isinstance(card, Mapping):
            active_dimensions.add(_dimension_for_counter_card(card, claim_dimension_by_id))
    for gap in gap_cards:
        if isinstance(gap, Mapping):
            active_dimensions.add(_dimension_for_gap_card(gap, claim_dimension_by_id))

    required_gaps: list[dict[str, Any]] = []
    for dimension in required_dimension_ids:
        if dimension in active_dimensions:
            continue
        required_gaps.append(
            {
                "gap_id": f"gap_required_dimension_{dimension}",
                "gap_type": "required_dimension_missing_verified_evidence",
                "source_claim_id": "",
                "agent_id": "",
                "analysis_dimension": dimension,
                "statement": _required_dimension_gap_statement(dimension),
                "evidence_refs": [],
                "claim_boundary": "gap_only_not_supporting_fact",
            }
        )
    return required_gaps


def _required_dimension_gap_statement(dimension: str) -> str:
    title = _analysis_dimension_title(dimension)
    return (
        f"The user requested {title}, but no verified ClaimCard or bounded public evidence gap survived "
        "the current gates for this dimension. Keep it as a visible evidence gap; do not fill it with a proxy fact."
    )


def _dimension_for_counter_card(card: Mapping[str, Any], claim_dimension_by_id: Mapping[str, str]) -> str:
    source_claim_id = str(card.get("source_claim_id") or "")
    if source_claim_id and source_claim_id in claim_dimension_by_id:
        return str(claim_dimension_by_id[source_claim_id])
    return _dimension_from_agent_or_text(
        agent_id=str(card.get("agent_id") or ""),
        memo_slot=str(card.get("memo_slot") or "risk_counterevidence"),
        text=str(card.get("statement") or card.get("claim") or card.get("reason") or ""),
        metric_scope=card.get("metric_scope"),
        default="risk_and_counterevidence",
    )


def _dimension_for_gap_card(gap: Mapping[str, Any], claim_dimension_by_id: Mapping[str, str]) -> str:
    explicit_dimension = str(gap.get("analysis_dimension") or "").strip()
    if explicit_dimension:
        return explicit_dimension
    source_claim_id = str(gap.get("source_claim_id") or "")
    if source_claim_id and source_claim_id in claim_dimension_by_id:
        return str(claim_dimension_by_id[source_claim_id])
    return _dimension_from_agent_or_text(
        agent_id=str(gap.get("agent_id") or ""),
        memo_slot=_agent_expected_memo_slot(str(gap.get("agent_id") or "")),
        text=str(gap.get("statement") or gap.get("claim") or gap.get("reason") or ""),
        metric_scope=gap.get("metric_scope"),
        default="evidence_gap",
    )


def _dimension_from_agent_or_text(
    *,
    agent_id: str,
    memo_slot: str,
    text: str,
    metric_scope: Any,
    default: str,
) -> str:
    slot = _normalize_memo_slot(memo_slot) or _agent_expected_memo_slot(agent_id)
    if slot or text or metric_scope:
        return _analysis_dimension_for_claim(
            {
                "agent_id": agent_id,
                "memo_slot": slot,
                "claim": text,
                "metric_scope": metric_scope,
            }
        )
    return default


def _dimension_section_thesis(
    dimension: str,
    claims: list[Mapping[str, Any]],
    *,
    related_counters: list[Mapping[str, Any]] | None = None,
    related_gaps: list[Mapping[str, Any]] | None = None,
) -> str:
    primary = claims[0] if claims else {}
    claim_text = str(primary.get("claim") or "").strip()
    if not claim_text:
        for item in related_counters or []:
            text = str(item.get("statement") or item.get("claim") or item.get("reason") or "").strip()
            if text:
                return _clean_synthesized_thesis_prefix(text)
        for item in related_gaps or []:
            text = str(item.get("statement") or item.get("claim") or item.get("reason") or "").strip()
            if text:
                return _clean_synthesized_thesis_prefix(text)
        return _analysis_dimension_lens(dimension)
    return _clean_synthesized_thesis_prefix(claim_text)


def _dimension_source_boundaries(
    claims: list[Mapping[str, Any]],
    source_boundary_notes: list[dict[str, Any]],
) -> list[str]:
    boundaries: list[str] = []
    for claim in claims:
        for family in _unique_strings(claim.get("source_families") or claim.get("source_family")):
            scope = SOURCE_FAMILY_CLAIM_SCOPE.get(family)
            if scope:
                boundaries.append(f"{family}: {scope}")
    for note in source_boundary_notes[:2]:
        reason = str(note.get("reason") or note.get("note") or "").strip()
        if reason:
            boundaries.append(reason)
    return _unique_strings(boundaries)[:5]


def _dimension_competitive_read(dimension: str, claims: list[Mapping[str, Any]]) -> str:
    tickers = _unique_upper([ticker for claim in claims for ticker in _unique_upper(claim.get("ticker_scope"))])
    metrics = _unique_strings([metric for claim in claims for metric in _unique_strings(claim.get("metric_scope"))])
    if dimension == "competition_and_market_position":
        basis = []
        if tickers:
            basis.append("ticker scope " + ", ".join(tickers[:6]))
        if metrics:
            basis.append("metrics " + ", ".join(metrics[:4]))
        return "Competitive or market-position read is bounded to " + ("; ".join(basis) if basis else "the verified market/valuation evidence")
    if len(tickers) >= 2:
        return "Peer comparison is available only across the verified ticker scope: " + ", ".join(tickers[:6])
    return "No direct competitive comparison was verified for this dimension."


def _dimension_counter_read(
    claims: list[Mapping[str, Any]],
    related_counters: list[Mapping[str, Any]],
    related_gaps: list[Mapping[str, Any]],
) -> str:
    for card in related_counters:
        text = str(card.get("statement") or "").strip()
        if text:
            return text
    for claim in claims:
        depth = claim.get("analyst_depth") if isinstance(claim.get("analyst_depth"), Mapping) else {}
        text = str(depth.get("counter_read") or "").strip()
        if text and not text.startswith("No explicit"):
            return text
    for gap in related_gaps:
        text = str(gap.get("statement") or "").strip()
        if text:
            return text
    return "No direct counterevidence in this dimension; keep the stated source boundary."


def _dimension_view_change(
    claims: list[Mapping[str, Any]],
    related_counters: list[Mapping[str, Any]],
    related_gaps: list[Mapping[str, Any]],
) -> list[str]:
    items: list[str] = []
    for card in related_counters[:2]:
        text = str(card.get("statement") or "").strip()
        if text:
            items.append(f"Counterevidence becomes more material: {text}")
    for gap in related_gaps[:2]:
        text = str(gap.get("statement") or "").strip()
        if text:
            items.append(f"Missing public confirmation resolves against the thesis: {text}")
    for claim in claims:
        for missing in _unique_strings(claim.get("missing_confirmations"))[:2]:
            items.append(f"Missing public confirmation resolves against the thesis: {missing}")
    return _unique_strings(items)[:4]


def _thesis_pack_view_change(counter_driver_cards: list[dict[str, Any]], gap_cards: list[dict[str, Any]]) -> list[str]:
    items: list[str] = []
    for card in counter_driver_cards[:2]:
        text = str(card.get("statement") or "").strip()
        if text:
            items.append(f"Counterevidence strengthens or invalidates the thesis: {text}")
    for card in gap_cards[:2]:
        text = str(card.get("statement") or "").strip()
        if text:
            items.append(f"Missing confirmation is resolved against the thesis: {text}")
    return items[:4]


def _thesis_source_boundary_cards(
    supported_claims: list[dict[str, Any]],
    source_boundary_notes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_family: dict[str, dict[str, Any]] = {}
    for claim in supported_claims:
        for family in _unique_strings(claim.get("source_families") or claim.get("source_family")):
            row = by_family.setdefault(
                family,
                {
                    "source_family": family,
                    "claim_count": 0,
                    "claim_scope": SOURCE_FAMILY_CLAIM_SCOPE.get(family, "verified_claim_card_scope"),
                    "claim_ids": [],
                },
            )
            row["claim_count"] += 1
            claim_id = str(claim.get("claim_id") or "")
            if claim_id and len(row["claim_ids"]) < 8:
                row["claim_ids"].append(claim_id)
    cards = list(by_family.values())[:8]
    for note in source_boundary_notes[:4]:
        cards.append(
            {
                "source_family": str(note.get("source_family") or ""),
                "claim_count": 0,
                "claim_scope": "boundary_note",
                "note": str(note.get("reason") or note.get("note") or ""),
                "agent_id": str(note.get("agent_id") or ""),
            }
        )
    return cards[:10]


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
        "analysis_dimension": str(claim.get("analysis_dimension") or _analysis_dimension_for_claim(claim)),
        "analyst_angle": str(claim.get("analyst_angle") or _analysis_dimension_title(_analysis_dimension_for_claim(claim))),
        "analyst_depth": _claim_analyst_depth(claim),
    }


def _dimension_analyses_from_thesis_driver_pack(pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    analyses: list[dict[str, Any]] = []
    for section in pack.get("dimension_sections") or []:
        if not isinstance(section, Mapping):
            continue
        dimension_id = str(section.get("dimension_id") or "").strip()
        if not dimension_id:
            continue
        analyses.append(
            {
                "dimension_id": dimension_id,
                "title": str(section.get("dimension_title") or _analysis_dimension_title(dimension_id)),
                "summary": str(section.get("section_thesis") or ""),
                "analysis_lens": str(section.get("analysis_lens") or ""),
                "business_mechanism": str(section.get("business_mechanism") or ""),
                "financial_bridge": str(section.get("financial_bridge") or ""),
                "comparison_basis": _unique_strings(section.get("comparison_basis"))[:4],
                "competitive_read": str(section.get("competitive_read") or ""),
                "counter_read": str(section.get("counter_read") or ""),
                "claim_ids": _unique_strings(section.get("primary_claim_ids"))[:8],
                "counter_claim_ids": _unique_strings(section.get("counter_claim_ids"))[:4],
                "gap_ids": _unique_strings(section.get("gap_ids"))[:5],
                "evidence_refs": _unique_strings(section.get("evidence_refs"))[:8],
                "source_boundaries": _unique_strings(section.get("source_boundaries"))[:5],
                "what_would_change_view": _unique_strings(section.get("what_would_change_view"))[:4],
                "status": str(section.get("status") or ""),
            }
        )
    return analyses[:8]


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
        "product_technology": "Explain product taxonomy, company-disclosed product KPI, public proxy context, and commercial tracker gaps.",
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
        "product_technology_analyst": "product_technology",
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
        "product_technology": "product_technology_analyst",
        "industry_relationship": "industry_supply_chain_analyst",
        "market_valuation": "market_valuation_analyst",
        "risk_counterevidence": "risk_counterevidence_analyst",
    }.get(slot, "")


def _memo_slot_title(slot: str) -> str:
    return {
        "thesis": "Thesis",
        "fundamentals": "Fundamentals",
        "product_technology": "Product and Technology Evidence",
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
    if families & {"public_source_context", "live_public_web_context", "milvus_semantic"} and normalized in PRODUCT_KPI_CLAIM_TYPES:
        return "public_proxy_context"
    if "company_product_evidence_graph" in families and normalized in {"product_kpi", "product_revenue", "product_sales"}:
        return "company_disclosed_product_kpi"
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
    if "company_product_evidence_graph" in families:
        return 3
    if families & {"public_source_context", "live_public_web_context"}:
        return 1
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
    consumed_views = ["verified_judgment_plan", "verified_summary"]
    if isinstance(judgment.get("pre_memo_fact_selection"), Mapping):
        consumed_views.append("pre_memo_fact_selection")
    thesis_driver_pack = dict(judgment.get("thesis_driver_pack") or {}) if isinstance(judgment.get("thesis_driver_pack"), Mapping) else {}
    judgment_state = dict(judgment.get("judgment_state") or {}) if isinstance(judgment.get("judgment_state"), Mapping) else {}
    common = {
        "schema_version": MEMO_DRAFT_SCHEMA_VERSION,
        "memo_writer_allowed": allowed,
        "consumed_input_views": consumed_views,
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
        "thesis_driver_pack": thesis_driver_pack,
        "judgment_state": judgment_state,
        "dimension_analyses": _dimension_analyses_from_thesis_driver_pack(thesis_driver_pack),
        "claim_card_stats": dict(judgment.get("claim_card_stats") or {}),
        "pre_memo_fact_selection": dict(judgment.get("pre_memo_fact_selection") or {})
        if isinstance(judgment.get("pre_memo_fact_selection"), Mapping)
        else {},
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
    analyst_depth_gate = _analyst_depth_gate(memo, judgment)
    errors.extend(analyst_depth_gate["errors"])
    warnings.extend(analyst_depth_gate["warnings"])

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
        claim_type_tokens = _claim_type_tokens(claim)
        if claim_type in {"reported_financial_fact", "company_reported_financial_fact"} and source_families & CONTEXT_ONLY_SOURCE_FAMILIES:
            errors.append(
                {
                    "type": "context_source_used_as_reported_financial_fact",
                    "index": index,
                    "source_families": sorted(source_families & CONTEXT_ONLY_SOURCE_FAMILIES),
                }
            )
        if claim_type_tokens & OWNERSHIP_REALTIME_FLOW_CLAIM_TYPES and source_families & {"public_source_context", "industry_snapshot", "milvus_semantic"}:
            errors.append(
                {
                    "type": "ownership_filing_used_as_realtime_flow",
                    "index": index,
                    "source_families": sorted(source_families & {"public_source_context", "industry_snapshot", "milvus_semantic"}),
                }
            )
        if claim_type_tokens & MACRO_COMPANY_FACT_CLAIM_TYPES and source_families & {"industry_snapshot", "public_source_context", "milvus_semantic"}:
            errors.append(
                {
                    "type": "macro_or_public_context_used_as_company_fact",
                    "index": index,
                    "source_families": sorted(source_families & {"industry_snapshot", "public_source_context", "milvus_semantic"}),
                }
            )
        if claim_type_tokens & PRODUCT_KPI_CLAIM_TYPES and source_families & {"public_source_context", "live_public_web_context", "milvus_semantic"}:
            errors.append(
                {
                    "type": "public_proxy_used_as_product_kpi_fact",
                    "index": index,
                    "source_families": sorted(source_families & {"public_source_context", "live_public_web_context", "milvus_semantic"}),
                }
            )
        claim_text = str(claim.get("claim") or "").lower()
        if source_families & {"public_source_context", "industry_snapshot", "milvus_semantic"} and _text_suggests_ownership_realtime_flow(claim_text):
            errors.append({"type": "ownership_filing_used_as_realtime_flow", "index": index, "source_families": sorted(source_families)})
        if source_families & {"industry_snapshot", "public_source_context", "milvus_semantic"} and _text_suggests_macro_company_fact(claim_text):
            errors.append({"type": "macro_or_public_context_used_as_company_fact", "index": index, "source_families": sorted(source_families)})
        if source_families & {"public_source_context", "live_public_web_context", "milvus_semantic"} and _text_suggests_channel_offer_sell_through(claim_text):
            errors.append({"type": "channel_offer_used_as_sell_through", "index": index, "source_families": sorted(source_families)})
        if source_families & {"public_source_context", "live_public_web_context", "milvus_semantic"} and _text_suggests_field_inquiry_authority_fact(claim_text):
            errors.append({"type": "field_inquiry_note_used_as_authority_fact", "index": index, "source_families": sorted(source_families)})
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
        "analyst_depth_gate": analyst_depth_gate,
        "repair_instruction": repair_instruction,
        "bounded_answer_allowed": bool(errors),
        "policy": "verifier_quality_gate_v0_3_analyst_depth_inspect_only_no_new_facts_no_retrieval",
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
    thesis_ready = (
        isinstance(judgment.get("memo_thesis_pack"), Mapping)
        and str((judgment.get("memo_thesis_pack") or {}).get("status") or "") == "ready"
    ) or (
        isinstance(judgment.get("memo_thesis_plan"), Mapping)
        and str((judgment.get("memo_thesis_plan") or {}).get("status") or "") == "ready"
    )
    profile_min = _bounded_int(
        memo_profile.get("memo_claims_min_when_thesis_ready"),
        default=3,
        minimum=1,
        maximum=8,
    )
    profile_name = str(memo_profile.get("profile") or "compact")
    if profile_name == "compact":
        minimum_claim_count = 3 if len(supported_claims) >= 3 else 1
    else:
        minimum_claim_count = min(profile_min, len(supported_claims)) if thesis_ready else 3 if len(supported_claims) >= 3 else 1
    explicit_memo_claims = [dict(item) for item in memo.get("memo_claims") or [] if isinstance(item, Mapping)]
    actual_claim_count = len(explicit_memo_claims) if explicit_memo_claims else len(_memo_claims(memo))
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


def _analyst_depth_gate(memo: Mapping[str, Any], judgment: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    answer_status = str(memo.get("answer_status") or "")
    if answer_status.startswith("blocked_"):
        return _analyst_depth_gate_result(errors, warnings)

    memo_profile = memo.get("memo_profile") if isinstance(memo.get("memo_profile"), Mapping) else {}
    profile_name = str(memo_profile.get("profile") or "compact")
    if profile_name == "compact":
        return _analyst_depth_gate_result(errors, warnings)

    expected_sections = _judgment_dimension_sections(judgment)
    supported_claims = [dict(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)]
    if not supported_claims:
        return _analyst_depth_gate_result(errors, warnings)
    if not expected_sections:
        warnings.append({"type": "analyst_depth_pack_missing_dimension_sections"})
        return _analyst_depth_gate_result(errors, warnings)

    if "dimension_analyses" in memo:
        memo_dimensions = [dict(item) for item in memo.get("dimension_analyses") or [] if isinstance(item, Mapping)]
    else:
        memo_dimensions = _memo_dimension_analyses(memo)
    required_count = min(3 if profile_name == "deep_research" else 2, len(expected_sections))
    if len(memo_dimensions) < required_count:
        errors.append(
            {
                "type": "analyst_depth_missing_dimension_analyses",
                "minimum_dimension_count": required_count,
                "actual_dimension_count": len(memo_dimensions),
            }
        )

    expected_ids = {str(section.get("dimension_id") or "") for section in expected_sections if str(section.get("dimension_id") or "")}
    memo_ids = {str(section.get("dimension_id") or "") for section in memo_dimensions if str(section.get("dimension_id") or "")}
    missing_ids = sorted(expected_ids - memo_ids)
    if len(expected_ids) >= 2 and len(missing_ids) >= len(expected_ids):
        errors.append({"type": "analyst_depth_dimension_ids_not_carried", "expected_dimension_ids": sorted(expected_ids)[:6]})
    required_ids = {
        str(section.get("dimension_id") or "")
        for section in expected_sections
        if bool(section.get("required_by_user")) and str(section.get("dimension_id") or "")
    }
    missing_required_ids = sorted(required_ids - memo_ids)
    if missing_required_ids:
        errors.append(
            {
                "type": "analyst_depth_required_dimensions_not_carried",
                "missing_dimension_ids": missing_required_ids[:8],
            }
        )

    for index, section in enumerate(memo_dimensions[: max(required_count, 1)], start=1):
        dimension_id = str(section.get("dimension_id") or "").strip()
        summary = str(section.get("summary") or section.get("section_thesis") or section.get("text") or "").strip()
        refs = _unique_strings(section.get("evidence_refs") or section.get("refs"))
        claim_ids = _unique_strings(section.get("claim_ids") or section.get("primary_claim_ids"))
        gap_ids = _unique_strings(section.get("gap_ids"))
        counter_claim_ids = _unique_strings(section.get("counter_claim_ids"))
        if not dimension_id:
            errors.append({"type": "analyst_depth_dimension_missing_id", "index": index})
        if len(summary) < 24:
            errors.append({"type": "analyst_depth_dimension_summary_too_thin", "index": index, "dimension_id": dimension_id})
        if not refs and not claim_ids and not gap_ids and not counter_claim_ids:
            errors.append({"type": "analyst_depth_dimension_missing_traceability", "index": index, "dimension_id": dimension_id})
        if _dimension_depth_signal_count(section) < 2:
            errors.append({"type": "analyst_depth_dimension_missing_mechanism_bridge", "index": index, "dimension_id": dimension_id})

    generic_fields = _generic_template_language_fields(memo)
    if generic_fields:
        errors.append({"type": "analyst_depth_generic_template_language", "fields": generic_fields[:8]})

    direct_answer = str(memo.get("direct_answer") or "").strip()
    if profile_name in {"expanded", "deep_research"} and len(direct_answer) < 120:
        warnings.append({"type": "analyst_depth_direct_answer_may_be_too_thin", "actual_chars": len(direct_answer)})

    return _analyst_depth_gate_result(errors, warnings)


def _analyst_depth_gate_result(errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": ANALYST_DEPTH_GATE_SCHEMA_VERSION,
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "policy": "dimension_led_mechanism_bridge_traceability_gate_v0_1",
    }


def _judgment_dimension_sections(judgment: Mapping[str, Any]) -> list[dict[str, Any]]:
    pack = judgment.get("thesis_driver_pack") if isinstance(judgment.get("thesis_driver_pack"), Mapping) else {}
    return [dict(item) for item in pack.get("dimension_sections") or [] if isinstance(item, Mapping)]


def _memo_dimension_analyses(memo: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(item) for item in memo.get("dimension_analyses") or [] if isinstance(item, Mapping)]
    if rows:
        return rows
    pack = memo.get("thesis_driver_pack") if isinstance(memo.get("thesis_driver_pack"), Mapping) else {}
    return _dimension_analyses_from_thesis_driver_pack(pack)


def _dimension_depth_signal_count(section: Mapping[str, Any]) -> int:
    count = 0
    for key in ("business_mechanism", "financial_bridge", "competitive_read", "counter_read", "analysis_lens"):
        if len(str(section.get(key) or "").strip()) >= 24:
            count += 1
    return count


def _generic_template_language_fields(memo: Mapping[str, Any]) -> list[str]:
    generic_phrases = (
        "把已验证的核心论据作为当前判断依据",
        "用该补充论据交叉验证核心判断",
        "keep this claim in the memo as a bounded verified observation",
        "use the verified core claim as the current judgment basis",
        "use the supporting claim to cross-check the core thesis",
    )
    offenders: list[str] = []
    fields: list[tuple[str, Any]] = [("direct_answer", memo.get("direct_answer"))]
    for key in ("investment_implications", "what_would_change_view", "monitoring_items", "evidence_gaps_but_actionable"):
        for index, item in enumerate(memo.get(key) or [], start=1):
            if isinstance(item, Mapping):
                fields.append((f"{key}[{index}]", item.get("text") or item.get("claim") or item.get("reason")))
            else:
                fields.append((f"{key}[{index}]", item))
    for index, item in enumerate(_memo_dimension_analyses(memo), start=1):
        fields.append((f"dimension_analyses[{index}].summary", item.get("summary") or item.get("section_thesis")))
    for field, value in fields:
        text = str(value or "").lower()
        if any(phrase.lower() in text for phrase in generic_phrases):
            offenders.append(field)
    return offenders


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
    for index, item in enumerate(_memo_dimension_analyses(memo), start=1):
        fields.append((f"dimension_analyses[{index}].summary", item.get("summary") or item.get("section_thesis")))
        fields.append((f"dimension_analyses[{index}].business_mechanism", item.get("business_mechanism")))
        fields.append((f"dimension_analyses[{index}].financial_bridge", item.get("financial_bridge")))
        fields.append((f"dimension_analyses[{index}].counter_read", item.get("counter_read")))
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
        r"(?<![A-Za-z0-9])[-+]?\$?\d+(?:,\d{3})*(?:\.\d+)?\s*(?:percentage\s+points?|usd[_\s-]?billions?|usd[_\s-]?millions?|usd[_\s-]?thousands?|个百分点|十亿美元|亿美元|百万美元|万美元|billion|million|bn|mn|ppt|%|x|X|倍|M|B|K)?",
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
    unit_pattern = r"(percentage\s+points?|usd[_\s-]?billions?|usd[_\s-]?millions?|usd[_\s-]?thousands?|个百分点|十亿美元|亿美元|百万美元|万美元|billion|million|bn|mn|ppt|%|x|X|倍|M|B|K)"

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
    normalized = str(unit or "").strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    if normalized in {"b", "bn", "billion", "usdbillion", "usdbillions", "十亿美元"}:
        return value, "b"
    if normalized in {"m", "mn", "million", "usdmillion", "usdmillions"}:
        return value / 1000.0, "b"
    if normalized in {"k", "usdthousand", "usdthousands"}:
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
        claim_type_tokens = _claim_type_tokens(claim)
        remove_reason = ""
        if not refs:
            remove_reason = "missing_evidence_refs"
        elif known_refs and sorted(set(refs) - known_refs):
            remove_reason = "unknown_evidence_refs"
        elif text.lower() in unsupported_texts:
            remove_reason = "unsupported_claim_text"
        elif claim_type in {"reported_financial_fact", "company_reported_financial_fact"} and source_families & CONTEXT_ONLY_SOURCE_FAMILIES:
            remove_reason = "context_source_used_as_financial_fact"
        elif claim_type_tokens & OWNERSHIP_REALTIME_FLOW_CLAIM_TYPES and source_families & {"public_source_context", "industry_snapshot", "milvus_semantic"}:
            remove_reason = "ownership_filing_used_as_realtime_flow"
        elif claim_type_tokens & MACRO_COMPANY_FACT_CLAIM_TYPES and source_families & {"industry_snapshot", "public_source_context", "milvus_semantic"}:
            remove_reason = "macro_or_public_context_used_as_company_fact"
        elif claim_type_tokens & PRODUCT_KPI_CLAIM_TYPES and source_families & {"public_source_context", "live_public_web_context", "milvus_semantic"}:
            remove_reason = "public_proxy_used_as_product_kpi_fact"
        elif source_families & {"public_source_context", "industry_snapshot", "milvus_semantic"} and _text_suggests_ownership_realtime_flow(text):
            remove_reason = "ownership_filing_used_as_realtime_flow"
        elif source_families & {"industry_snapshot", "public_source_context", "milvus_semantic"} and _text_suggests_macro_company_fact(text):
            remove_reason = "macro_or_public_context_used_as_company_fact"
        elif source_families & {"public_source_context", "live_public_web_context", "milvus_semantic"} and _text_suggests_channel_offer_sell_through(text):
            remove_reason = "channel_offer_used_as_sell_through"
        elif source_families & {"public_source_context", "live_public_web_context", "milvus_semantic"} and _text_suggests_field_inquiry_authority_fact(text):
            remove_reason = "field_inquiry_note_used_as_authority_fact"
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
    if source_family == "company_product_evidence_graph":
        return "require_runtime_fact_allowed_exact_authority_for_product_kpi_claims"
    if source_family == "public_source_context":
        return "do_not_use_as_company_product_sales_share_inventory_margin_or_profitability_fact"
    if source_family == "live_public_web_context":
        return "do_not_use_web_snapshot_as_company_product_kpi_or_financial_fact"
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
        "raw_claim_type": str(item.get("raw_claim_type") or item.get("claim_type") or "").strip(),
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
        "analysis_dimension": str(item.get("analysis_dimension") or _analysis_dimension_for_claim(item)),
        "analyst_angle": str(item.get("analyst_angle") or _analysis_dimension_title(_analysis_dimension_for_claim(item))),
        "analyst_depth": _claim_analyst_depth(item),
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
    for item in memo.get("dimension_analyses") or []:
        if isinstance(item, Mapping):
            parts.extend(
                [
                    item.get("title"),
                    item.get("summary"),
                    item.get("business_mechanism"),
                    item.get("financial_bridge"),
                    item.get("competitive_read"),
                    item.get("counter_read"),
                ]
            )
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
    if any(str(item).startswith("analyst_depth_") for item in types):
        return "Regenerate as a dimension-led analyst memo: include dimension_analyses with summary, business mechanism, financial bridge, counter-read, claim_ids/evidence_refs, and avoid generic template language."
    return "Regenerate memo within verified judgment plan constraints."


def _normalize_observation(payload: Mapping[str, Any]) -> dict[str, Any]:
    source_families = _unique_strings(payload.get("source_families") or payload.get("source_family"))
    raw_claim_type = str(payload.get("claim_type") or "").strip()
    claim_text = str(payload.get("claim") or "").strip()
    claim_type = _claim_type_for_source_scope(payload.get("claim_type"), source_families)
    evidence_refs = _unique_strings(payload.get("evidence_refs") or payload.get("refs"))
    metric_scope = _unique_strings(payload.get("metric_scope") or payload.get("metrics") or payload.get("metric"))
    memo_slot = _normalize_memo_slot(payload.get("memo_slot"))
    if memo_slot == "fundamentals" and _claim_has_product_surface_signal(
        {
            "claim": claim_text,
            "claim_type": claim_type,
            "raw_claim_type": raw_claim_type,
            "evidence_refs": evidence_refs,
            "metric_scope": metric_scope,
            "source_families": source_families,
        }
    ):
        memo_slot = "product_technology"
    return {
        "claim": claim_text,
        "claim_type": claim_type,
        "raw_claim_type": raw_claim_type,
        "evidence_refs": evidence_refs,
        "source_families": source_families,
        "confidence": _normalize_confidence(payload.get("confidence")),
        "unsupported": bool(payload.get("unsupported")),
        "caveats": _unique_strings(payload.get("caveats")),
        "ticker_scope": _unique_upper(payload.get("ticker_scope") or payload.get("tickers") or payload.get("ticker")),
        "metric_scope": metric_scope,
        "memo_slot": memo_slot,
        "materiality": _normalize_materiality(payload.get("materiality")),
        "direction": _normalize_direction(payload.get("direction")),
        "missing_confirmations": _unique_strings(payload.get("missing_confirmations")),
        "period_role": str(payload.get("period_role") or "").strip(),
        "snapshot_id": str(payload.get("snapshot_id") or "").strip(),
        "as_of_date": str(payload.get("as_of_date") or "").strip(),
    }


def _claim_has_product_surface_signal(claim: Mapping[str, Any]) -> bool:
    metrics = " ".join(_unique_strings(claim.get("metric_scope") or claim.get("metrics") or claim.get("metric"))).lower()
    claim_type = str(claim.get("claim_type") or claim.get("raw_claim_type") or "").lower()
    evidence_refs = " ".join(_unique_strings(claim.get("evidence_refs") or claim.get("refs"))).lower()
    text = str(claim.get("claim") or "").lower()
    product_metric_terms = (
        "product_revenue",
        "product revenue",
        "product_kpi",
        "segment_revenue",
        "segment revenue",
        "backlog",
        "shipments",
        "units",
        "capacity",
    )
    product_line_terms = (
        "ai-optimized",
        "ai optimized",
        "ai_optimized",
        "server",
        "servers",
        "isg",
        "infrastructure solutions group",
        "product line",
        "product mix",
    )
    return any(term in metrics or term in claim_type or term in evidence_refs for term in product_metric_terms) or any(
        term in text or term in evidence_refs for term in product_line_terms
    )


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
        "product_technology",
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
