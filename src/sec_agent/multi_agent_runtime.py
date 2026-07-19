from __future__ import annotations

import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlparse

from evidence.schema import EvidenceObject
from evidence.structured_extractor import extract_structured_objects
from sec_agent.agent_registry import agent_registry_by_id
from sec_agent.capital_macro_pack import build_capital_macro_pack, compact_capital_macro_pack
from sec_agent.dimension_evidence_portfolio import (
    build_dimension_evidence_portfolio,
    compact_dimension_evidence_portfolio,
)
from sec_agent.financial_statement_analysis import (
    build_fundamental_peer_statement_panel,
    build_fundamental_statement_pack,
    compact_fundamental_peer_statement_panel,
    compact_fundamental_statement_pack,
)
from sec_agent.industry_playbooks import selected_playbook_policy
from sec_agent.mcp_tool_registry import invoke_mcp_tool
from sec_agent.multi_agent_contracts import evidence_requirements_from_universe_relationship_plan
from sec_agent.product_intelligence_runtime import (
    compact_product_intelligence_pack_refs,
    product_intelligence_context_rows_for_state,
)
from sec_agent.product_intelligence_depth import compact_ai_semis_product_evidence_pack_refs
from sec_agent.product_spec_pack import build_product_spec_pack, compact_product_spec_pack
from sec_agent.project_inventory import inventory_brief
from sec_agent.retrieval_plan import EVIDENCE_REQUIREMENT_SCHEMA_VERSION, build_evidence_requirement_plan, build_retrieval_plan
from sec_agent.tool_call_ledger import ToolCallLedger


RUNTIME_SCHEMA_VERSION = "sec_agent_multi_agent_runtime_v0.1"
AGENT_DATA_VIEW_SCHEMA_VERSION = "sec_agent_agent_data_view_v0.3"
SPECIALIST_TASK_CARD_SCHEMA_VERSION = "sec_agent_specialist_task_card_v0.1"
SPECIALIST_CLAIM_SLOT_SCHEMA_VERSION = "sec_agent_specialist_claim_slot_v0.1"
PLAN_REFLECTION_GATE_SCHEMA_VERSION = "sec_agent_plan_reflection_gate_v0.1"
EVIDENCE_FUSION_BUNDLE_SCHEMA_VERSION = "sec_agent_evidence_fusion_bundle_v0.1"
BOUNDED_GAP_REGISTER_SCHEMA_VERSION = "sec_agent_bounded_gap_register_v0.1"
SECOND_PASS_REFLECTION_DIAGNOSIS_SCHEMA_VERSION = "sec_agent_second_pass_reflection_diagnosis_v0.1"
SECOND_PASS_REPAIR_PLAN_SCHEMA_VERSION = "sec_agent_second_pass_repair_plan_v0.1"
SECOND_PASS_HARD_GATE_SCHEMA_VERSION = "sec_agent_second_pass_hard_gate_v0.1"
SECOND_PASS_DELTA_AUDIT_SCHEMA_VERSION = "sec_agent_second_pass_delta_audit_v0.1"
WEB_SOURCE_SCOPE_REGISTRY_SCHEMA_VERSION = "sec_agent_web_source_scope_registry_v0.1"
WEB_EVIDENCE_REPAIR_REQUEST_SCHEMA_VERSION = "sec_agent_web_repair_request_v0.1"
WEB_EVIDENCE_SNAPSHOT_SCHEMA_VERSION = "sec_agent_web_evidence_snapshot_v0.1"
EVIDENCE_OPERATOR_FANOUT_PLAN_SCHEMA_VERSION = "sec_agent_evidence_operator_fanout_plan_v0.1"
FANOUT_BARRIER_SCHEMA_VERSION = "sec_agent_fanout_barrier_v0.1"
AGENT_DATA_VIEW_MAX_ROWS = 16
AGENT_DATA_VIEW_STANDARD_MEMO_MAX_ROWS = 24
AGENT_DATA_VIEW_DEEP_RESEARCH_MAX_ROWS = 48
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
SEC_SEARCH_TEXT_ROUTES = {"filing_text", "risk_text", "8k_commentary"}
SEC_SEARCH_GROUP_ROUTES = {"ledger_first", *SEC_SEARCH_TEXT_ROUTES}
MILVUS_SEMANTIC_VECTOR_KINDS = {
    "narrative_chunk",
    "table_chunk",
    "metric_row",
    "table_row",
    "claim_row",
    "relationship_context",
    "paraphrase_context",
}
MILVUS_DEFAULT_VECTOR_KINDS = ("narrative_chunk", "table_chunk", "paraphrase_context")

ROUTE_OPERATOR_TOOL: dict[str, tuple[str, str]] = {
    "ledger_first": ("sec_operator", "sec_query_exact_value_ledger"),
    "filing_text": ("sec_operator", "sec_search_filings"),
    "risk_text": ("sec_operator", "sec_search_filings"),
    "8k_commentary": ("eight_k_operator", "sec_search_filings"),
    "milvus_semantic": ("sec_operator", "sec_milvus_semantic_search"),
    "market_snapshot": ("market_operator", "market_get_snapshot"),
    "industry_snapshot": ("industry_operator", "industry_get_snapshot"),
    "relationship_graph": ("universe_relationship", "relationship_graph_lookup"),
    "live_public_web_context": ("web_evidence_operator", "web_evidence_snapshot"),
    "run_artifact": ("coverage_reflection", "run_inspect_artifacts"),
}

ROUTE_SOURCE_FAMILY: dict[str, str] = {
    "ledger_first": "primary_sec_filing",
    "filing_text": "primary_sec_filing",
    "risk_text": "primary_sec_filing",
    "8k_commentary": "company_authored_unaudited_sec_filing",
    "milvus_semantic": "milvus_semantic",
    "market_snapshot": "market_snapshot",
    "industry_snapshot": "industry_snapshot",
    "relationship_graph": "relationship_graph",
    "live_public_web_context": "live_public_web_context",
    "run_artifact": "run_artifact",
}
CONTEXT_ONLY_REQUIREMENT_SOURCE_FAMILIES = {
    "company_product_evidence_graph",
    "public_source_context",
}
ROUTE_BACKED_SOURCE_FAMILY_COMPATIBILITY_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"primary_sec_filing", "company_authored_unaudited_sec_filing"}),
)

ROUTE_COST_TIER: dict[str, str] = {
    "ledger_first": "low",
    "run_artifact": "low",
    "filing_text": "medium",
    "risk_text": "medium",
    "8k_commentary": "medium",
    "market_snapshot": "medium",
    "industry_snapshot": "medium",
    "milvus_semantic": "high",
    "relationship_graph": "high",
    "live_public_web_context": "high",
}
ROUTE_COST_TIER_RANK = {"low": 1, "medium": 2, "high": 3}

SEC_SEARCH_SOURCE_TIERS = {"primary_sec_filing", "company_authored_unaudited_sec_filing"}
SPECIALIST_EXECUTION_ORDER = (
    "fundamental_analyst",
    "product_technology_analyst",
    "industry_supply_chain_analyst",
    "market_valuation_analyst",
    "risk_counterevidence_analyst",
)


ToolExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]


WEB_FINANCIAL_FACT_CLAIM_TYPES = {
    "arr",
    "cash_flow",
    "channel_inventory",
    "company_revenue",
    "customer_count",
    "exact_financial_fact",
    "gross_margin",
    "inventory",
    "market_share",
    "prescription_volume",
    "product_revenue",
    "reported_financial_fact",
    "revenue",
    "sales_uptake",
    "sell_through",
    "shipment_volume",
    "vendor_share",
}
WEB_COMMERCE_ALLOWED_CLAIM_TYPES = {
    "availability",
    "listed_price",
    "official_feature_description",
    "price",
    "product_presence",
    "sku",
    "sku_configuration",
}
WEB_SOURCE_CLASS_CLAIM_SCOPES = {
    "company_official_product_surface": "product_presence_taxonomy_feature_official_pricing",
    "company_ir_material": "company_authored_context_or_management_statement",
    "official_regulatory_page": "regulatory_status_or_registration_context",
    "government_dataset_endpoint": "macro_industry_or_regulatory_context",
    "commerce_product_surface": "sku_price_availability_only",
    "major_financial_news": "event_public_reporting_and_quote_leads",
    "research_developer_signal": "technical_activity_or_developer_adoption_signal",
    "social_official_account": "official_statement_lead_only_requires_account_verification",
    "social_unverified_or_influencer": "lead_only_not_fact_authority",
}


def default_web_source_scope_registry() -> dict[str, Any]:
    """Return the default allowlisted web source policies used by hard gates."""
    policies = {
        "consumer_electronics_commerce": {
            "policy_id": "consumer_electronics_commerce",
            "source_classes": ["commerce_product_surface"],
            "allowed_domains": [
                "amazon.com",
                "jd.com",
                "taobao.com",
                "tmall.com",
                "bestbuy.com",
                "walmart.com",
                "target.com",
                "currys.co.uk",
                "argos.co.uk",
            ],
            "allowed_claim_types": sorted(WEB_COMMERCE_ALLOWED_CLAIM_TYPES),
            "claim_boundary": "commerce_product_surface_supports_sku_price_availability_only",
        },
        "major_financial_news": {
            "policy_id": "major_financial_news",
            "source_classes": ["major_financial_news"],
            "allowed_domains": [
                "ft.com",
                "wsj.com",
                "reuters.com",
                "bloomberg.com",
                "nytimes.com",
                "caixin.com",
                "xinhuanet.com",
            ],
            "allowed_claim_types": ["event", "management_quote_lead", "public_reporting_lead"],
            "claim_boundary": "major_news_supports_event_or_quote_leads_not_company_financial_facts",
        },
        "healthcare_regulatory": {
            "policy_id": "healthcare_regulatory",
            "source_classes": ["official_regulatory_page", "government_dataset_endpoint"],
            "allowed_domains": [
                "clinicaltrials.gov",
                "fda.gov",
                "open.fda.gov",
                "pubmed.ncbi.nlm.nih.gov",
                "cms.gov",
            ],
            "allowed_claim_types": [
                "adverse_event_context",
                "indication",
                "phase",
                "recall_context",
                "regulatory_status_context",
                "sponsor",
                "trial_status",
            ],
            "claim_boundary": "regulatory_healthcare_context_not_prescription_volume_or_sales_uptake",
        },
        "developer_product_signal": {
            "policy_id": "developer_product_signal",
            "source_classes": ["company_official_product_surface", "research_developer_signal"],
            "allowed_domains": [
                "github.com",
                "npmjs.com",
                "pypi.org",
                "huggingface.co",
                "arxiv.org",
                "openalex.org",
                "crossref.org",
                "pubmed.ncbi.nlm.nih.gov",
            ],
            "allowed_claim_types": [
                "developer_adoption_signal",
                "official_feature_description",
                "package_presence",
                "product_presence",
                "research_activity_signal",
            ],
            "claim_boundary": "developer_and_research_surfaces_support_presence_or_activity_signals_not_arr_or_revenue",
        },
        "official_social_account": {
            "policy_id": "official_social_account",
            "source_classes": ["social_official_account"],
            "allowed_domains": ["x.com", "twitter.com", "reddit.com", "youtube.com", "linkedin.com"],
            "allowed_claim_types": ["official_statement_lead"],
            "claim_boundary": "official_social_accounts_are_lead_only_and_cannot_support_financial_facts",
        },
        "company_official_product_surface": {
            "policy_id": "company_official_product_surface",
            "source_classes": ["company_official_product_surface", "company_ir_material"],
            "allowed_domains": [],
            "allowed_claim_types": [
                "official_feature_description",
                "official_pricing",
                "product_presence",
                "product_taxonomy",
                "status_context",
            ],
            "claim_boundary": "company_domains_must_be_preverified_in_request_or_inventory_before_use",
            "requires_verified_company_domain": True,
        },
        "official_issuer_disclosure": {
            "policy_id": "official_issuer_disclosure",
            "source_classes": ["company_ir_material", "government_dataset_endpoint", "official_regulatory_page"],
            "allowed_domains": [
                "sec.gov",
                "www.sec.gov",
                "data.sec.gov",
                "asml.com",
                "www.asml.com",
                "tsmc.com",
                "www.tsmc.com",
                "novonordisk.com",
                "www.novonordisk.com",
            ],
            "allowed_claim_types": [
                "annual_report_context",
                "company_ir_context",
                "issuer_filing_presence",
                "official_disclosure_context",
                "regulatory_filing_context",
            ],
            "claim_boundary": "official_issuer_sources_support_coverage_and_context_until_parser_authority_gate_promotes_exact_facts",
        },
    }
    return {
        "schema_version": WEB_SOURCE_SCOPE_REGISTRY_SCHEMA_VERSION,
        "registry_boundary": "allowlisted_web_repair_requests_only_no_free_search",
        "policies": policies,
    }


def validate_web_evidence_request(
    request: Mapping[str, Any],
    *,
    web_scope_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a structured live-web repair request before any web operator may run."""
    registry = _normalize_web_scope_registry(web_scope_registry)
    policies = registry.get("policies") if isinstance(registry.get("policies"), Mapping) else {}
    policy_ids = _string_list(request.get("web_scope_policy_ids") or request.get("web_scope_policy_id"))
    source_class = str(request.get("source_class") or "").strip()
    claim_types = _web_claim_types(request)
    domain = _normalize_domain(request.get("domain") or _domain_from_url(request.get("url") or request.get("snapshot_url")))
    errors: list[dict[str, Any]] = []

    if not policy_ids:
        errors.append({"type": "web_scope_policy_required"})
    if not source_class:
        errors.append({"type": "web_source_class_required"})
    if not domain:
        errors.append({"type": "web_domain_or_url_required"})
    selected_policies: list[dict[str, Any]] = []
    for policy_id in policy_ids:
        policy = policies.get(policy_id) if isinstance(policies.get(policy_id), Mapping) else None
        if policy is None:
            errors.append({"type": "web_scope_policy_unknown", "web_scope_policy_id": policy_id})
            continue
        selected_policies.append(dict(policy))
    if selected_policies and source_class:
        allowed_classes = {
            source
            for policy in selected_policies
            for source in _string_list(policy.get("source_classes") or policy.get("allowed_source_classes"))
        }
        if allowed_classes and source_class not in allowed_classes:
            errors.append({"type": "web_source_class_not_allowed_by_policy", "source_class": source_class})
    if selected_policies and domain:
        if not _web_domain_allowed(domain, selected_policies, request):
            errors.append({"type": "web_domain_not_allowlisted", "domain": domain})
    if source_class == "commerce_product_surface":
        disallowed = sorted(set(claim_types) - WEB_COMMERCE_ALLOWED_CLAIM_TYPES)
        if disallowed:
            errors.append(
                {
                    "type": "web_commerce_claim_scope_violation",
                    "claim_types": disallowed,
                    "allowed_claim_types": sorted(WEB_COMMERCE_ALLOWED_CLAIM_TYPES),
                }
            )
    if source_class in {"social_official_account", "social_unverified_or_influencer"}:
        financial = sorted(set(claim_types) & WEB_FINANCIAL_FACT_CLAIM_TYPES)
        if financial:
            errors.append({"type": "web_social_financial_fact_forbidden", "claim_types": financial})
    financial_from_non_authority = sorted(
        set(claim_types)
        & WEB_FINANCIAL_FACT_CLAIM_TYPES
        - {"exact_financial_fact", "reported_financial_fact"}
    )
    if source_class in {"major_financial_news", "research_developer_signal", "government_dataset_endpoint"} and financial_from_non_authority:
        errors.append({"type": "web_source_cannot_support_company_financial_fact", "claim_types": financial_from_non_authority})

    normalized = {
        "schema_version": WEB_EVIDENCE_REPAIR_REQUEST_SCHEMA_VERSION,
        "source_family": "live_public_web_context",
        "retrieval_route": "live_public_web_context",
        "url": str(request.get("url") or request.get("snapshot_url") or "").strip(),
        "domain": domain,
        "source_class": source_class,
        "claim_types": claim_types,
        "web_scope_policy_ids": policy_ids,
        "allowed_claim_scope": WEB_SOURCE_CLASS_CLAIM_SCOPES.get(source_class, "allowlisted_web_context_only"),
        "context_only": True,
        "exact_value_authority": False,
        "authority_boundary": "live_web_rows_are_context_only_until_snapshot_parser_and_authority_gate_pass",
    }
    return {
        "status": "fail" if errors else "pass",
        "errors": errors,
        "normalized_request": _sanitize_payload(normalized),
        "web_scope_registry_schema_version": registry.get("schema_version") or WEB_SOURCE_SCOPE_REGISTRY_SCHEMA_VERSION,
    }


def build_multi_agent_evidence_requirement_plan(
    query_contract: Mapping[str, Any],
    *,
    activation_plan: Mapping[str, Any] | None = None,
    case: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize business evidence needs and attach multi-agent ownership metadata."""
    plan = build_evidence_requirement_plan(dict(query_contract or {}), case=dict(case or {}))
    reconciled_requirements = _reconcile_requirements_with_activation_sources(
        [dict(req) for req in plan.get("requirements") or [] if isinstance(req, Mapping)],
        query_contract,
        activation_plan or {},
    )
    enriched_requirements = [_enrich_evidence_requirement(req) for req in reconciled_requirements]
    enriched = {
        **plan,
        "requirements": enriched_requirements,
        "multi_agent_contract": {
            "schema_version": "sec_agent_multi_agent_evidence_requirement_contract_v0.1",
            "planner_boundary": "business_need_only_no_physical_paths",
            "route_compiler": "deterministic_retrieval_plan_compiler",
            "operator_owner_source": "route_intent_mapping",
            "route_selection_policy": "cost_and_query_type_aware_v0_1",
        },
    }
    validation = validate_multi_agent_evidence_requirement_plan(enriched, activation_plan=activation_plan)
    enriched["multi_agent_evidence_requirement_validation"] = validation
    return enriched


def _reconcile_requirements_with_activation_sources(
    requirements: list[dict[str, Any]],
    query_contract: Mapping[str, Any],
    activation_plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not requirements:
        return requirements
    active_agents = set(_string_list(activation_plan.get("activate_agents")))
    allowed_sources = set(_string_list(activation_plan.get("allowed_source_families")))
    contract_sources = set(
        _string_list(query_contract.get("source_tiers"))
        + _string_list(query_contract.get("source_families"))
        + _string_list((query_contract.get("scope") or {}).get("source_tiers") if isinstance(query_contract.get("scope"), Mapping) else [])
    )
    source_scope = allowed_sources | contract_sources
    required_routes: list[str] = []
    if "market_operator" in active_agents and "market_snapshot" in source_scope:
        required_routes.append("market_snapshot")
    if "industry_operator" in active_agents and "industry_snapshot" in source_scope:
        required_routes.append("industry_snapshot")
    if "universe_relationship" in active_agents and "relationship_graph" in source_scope:
        required_routes.append("relationship_graph")
    if not required_routes:
        return requirements

    present_routes = {
        route
        for requirement in requirements
        for route in _string_list(requirement.get("evidence_routes") or requirement.get("retrieval_routes"))
    }
    missing_routes = [route for route in required_routes if route not in present_routes]
    if not missing_routes:
        return requirements

    reconciled = [dict(req) for req in requirements]
    target_index = _primary_requirement_index(reconciled)
    target = dict(reconciled[target_index])
    routes = _dedupe([*_string_list(target.get("evidence_routes") or target.get("retrieval_routes")), *missing_routes])
    source_families = _dedupe([*_string_list(target.get("source_families") or target.get("source_tiers")), *_source_families_for_routes(missing_routes)])
    target["evidence_routes"] = routes
    target["source_tiers"] = _dedupe([*_string_list(target.get("source_tiers")), *source_families])
    target["source_families"] = source_families
    metadata = dict(target.get("metadata") or {})
    metadata["activation_source_reconciliation_added_routes"] = missing_routes
    metadata["activation_source_reconciliation_policy"] = "active_operator_source_family_route_alignment_v0_1"
    target["metadata"] = metadata
    reconciled[target_index] = target
    return reconciled


def _primary_requirement_index(requirements: list[Mapping[str, Any]]) -> int:
    for index, requirement in enumerate(requirements):
        if str(requirement.get("priority") or "").strip().lower() in {"primary", "critical", ""}:
            return index
    return 0


def _route_backed_source_families_compatible(explicit_sources: set[str], expected_sources: set[str]) -> bool:
    if not explicit_sources or not expected_sources:
        return True
    return all(_route_backed_source_family_compatible(source, expected_sources) for source in explicit_sources)


def _route_backed_source_family_compatible(source: str, expected_sources: set[str]) -> bool:
    if source in expected_sources:
        return True
    for group in ROUTE_BACKED_SOURCE_FAMILY_COMPATIBILITY_GROUPS:
        if source in group and expected_sources.intersection(group):
            return True
    return False


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
        context_only_sources = explicit_sources & CONTEXT_ONLY_REQUIREMENT_SOURCE_FAMILIES
        route_backed_explicit_sources = explicit_sources - CONTEXT_ONLY_REQUIREMENT_SOURCE_FAMILIES
        if (
            route_backed_explicit_sources
            and expected_sources
            and not _route_backed_source_families_compatible(route_backed_explicit_sources, expected_sources)
        ):
            errors.append(
                {
                    "type": "source_family_mismatch",
                    "requirement_id": requirement_id,
                    "source_families": sorted(route_backed_explicit_sources),
                    "expected_source_families": sorted(expected_sources),
                    "context_only_source_families": sorted(context_only_sources),
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
            disallowed = sorted((expected_sources | context_only_sources | route_backed_explicit_sources) - allowed_sources)
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


def plan_reflection_gate(
    activation_plan: Mapping[str, Any],
    *,
    activation_validation: Mapping[str, Any] | None = None,
    source_inventory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic post-Lead gate before retrieval or relationship expansion."""
    plan = dict(activation_plan or {})
    validation = dict(activation_validation or {})
    inventory = dict(source_inventory or {})
    metadata = dict(plan.get("metadata") or {}) if isinstance(plan.get("metadata"), Mapping) else {}
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if validation and validation.get("status") != "pass":
        errors.append({"type": "activation_validation_failed", "validation_status": validation.get("status")})

    mode = str(plan.get("execution_mode") or "").strip()
    active_agents = set(_string_list(plan.get("activate_agents")))
    allowed_sources = set(_string_list(plan.get("allowed_source_families")))
    required_sources = set(_string_list(plan.get("required_source_families") or metadata.get("required_source_families")))
    if not required_sources:
        required_sources = set(_string_list(metadata.get("required_source_family") or metadata.get("required_sources")))

    if mode == "focused_answer" and (("universe_relationship" in active_agents) or ("relationship_graph" in allowed_sources)):
        errors.append(
            {
                "type": "focused_answer_deep_research_scope",
                "reason": "focused_answer cannot activate relationship expansion or relationship_graph.",
            }
        )
    if mode == "deep_research" and (("universe_relationship" in active_agents) or ("relationship_graph" in allowed_sources)):
        if not str(plan.get("relationship_scope_rationale") or "").strip():
            errors.append({"type": "relationship_scope_rationale_required_for_deep_research"})

    _check_required_source_family_availability(
        required_sources,
        allowed_sources,
        inventory,
        errors=errors,
        warnings=warnings,
    )
    _check_milvus_plan_boundary(allowed_sources | required_sources, inventory, errors=errors)
    _check_live_web_plan_boundary(plan, metadata, allowed_sources | required_sources, inventory, errors=errors)
    playbook_policy = _check_playbook_plan_boundary(
        plan,
        metadata,
        inventory,
        allowed_sources=allowed_sources,
        errors=errors,
        warnings=warnings,
    )
    _check_supervising_plan_runtime_contract(plan, metadata, active_agents, errors=errors, warnings=warnings)

    repair_requests = [
        {
            "request_id": f"plan_repair_{index}",
            "error_type": error.get("type") or "plan_reflection_error",
            "action": "repair_activation_plan_before_retrieval",
        }
        for index, error in enumerate(errors, start=1)
    ]
    return {
        "schema_version": PLAN_REFLECTION_GATE_SCHEMA_VERSION,
        "status": "fail" if errors else "pass",
        "policy": "deterministic_plan_reflection_hard_gate_v0_1",
        "checked": {
            "execution_mode": mode,
            "active_agent_count": len(active_agents),
            "allowed_source_families": sorted(allowed_sources),
            "required_source_families": sorted(required_sources),
        },
        "errors": errors,
        "warnings": warnings,
        "playbook_policy": playbook_policy,
        "repair_requests": repair_requests,
    }


def _check_supervising_plan_runtime_contract(
    plan: Mapping[str, Any],
    metadata: Mapping[str, Any],
    active_agents: set[str],
    *,
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    if not metadata.get("supervising_analyst_contract_schema_version"):
        return
    evidence_role_plan = [
        dict(item)
        for item in plan.get("evidence_role_plan") or []
        if isinstance(item, Mapping)
    ]
    missing_must_answer = [
        str(item.get("required_item") or "")
        for item in evidence_role_plan
        if str(item.get("required_item") or "").strip() and not _string_list(item.get("must_answer"))
    ]
    if missing_must_answer:
        errors.append(
            {
                "type": "supervising_plan_missing_must_answer",
                "required_items": sorted(set(missing_must_answer)),
                "reason": "Research Lead must turn absorbed methods into explicit questions before retrieval/specialist fanout.",
            }
        )
    required_items = {str(item.get("required_item") or "") for item in evidence_role_plan}
    if "risk_and_counterevidence" in required_items and "risk_counterevidence_analyst" not in active_agents:
        if not metadata.get("risk_counterevidence_deterministic_pack_policy"):
            warnings.append(
                {
                    "type": "required_risk_counterevidence_agent_pruned",
                    "required_item": "risk_and_counterevidence",
                    "reason": "Counter-thesis/what-would-change is required but no active risk analyst or deterministic risk pack policy is present.",
                }
            )
    if not evidence_role_plan:
        warnings.append({"type": "supervising_plan_has_no_evidence_role_plan"})


def _check_required_source_family_availability(
    required_sources: set[str],
    allowed_sources: set[str],
    inventory: Mapping[str, Any],
    *,
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    if not inventory:
        if required_sources:
            warnings.append({"type": "required_source_family_unchecked_no_inventory", "source_families": sorted(required_sources)})
        return
    availability = inventory.get("source_family_availability") if isinstance(inventory.get("source_family_availability"), Mapping) else {}
    available_families = set(_string_list(inventory.get("available_source_families") or inventory.get("source_families")))
    for family in sorted(required_sources):
        item = availability.get(family) if isinstance(availability.get(family), Mapping) else {}
        if item:
            if item.get("available") is False or str(item.get("status") or "").strip() in {"unavailable", "policy_not_loaded"}:
                errors.append({"type": "required_source_family_unavailable", "source_family": family, "status": item.get("status") or ""})
            continue
        if available_families and family not in available_families:
            errors.append({"type": "required_source_family_missing_from_inventory", "source_family": family})
    for family in sorted(allowed_sources - required_sources):
        item = availability.get(family) if isinstance(availability.get(family), Mapping) else {}
        if item and (item.get("available") is False or str(item.get("status") or "").strip() in {"unavailable", "policy_not_loaded"}):
            warnings.append({"type": "allowed_source_family_unavailable", "source_family": family, "status": item.get("status") or ""})


def _check_milvus_plan_boundary(source_families: set[str], inventory: Mapping[str, Any], *, errors: list[dict[str, Any]]) -> None:
    if "milvus_semantic" not in source_families:
        return
    milvus = inventory.get("milvus_runtime") if isinstance(inventory.get("milvus_runtime"), Mapping) else {}
    availability = inventory.get("source_family_availability") if isinstance(inventory.get("source_family_availability"), Mapping) else {}
    milvus_availability = availability.get("milvus_semantic") if isinstance(availability.get("milvus_semantic"), Mapping) else {}
    status = str(milvus.get("status") or milvus_availability.get("status") or "unavailable").strip()
    available = bool(milvus.get("available") if "available" in milvus else milvus_availability.get("available", False))
    if not available or status == "unavailable":
        errors.append({"type": "milvus_semantic_requested_but_unavailable", "status": status or "unavailable"})


def _check_live_web_plan_boundary(
    plan: Mapping[str, Any],
    metadata: Mapping[str, Any],
    source_families: set[str],
    inventory: Mapping[str, Any],
    *,
    errors: list[dict[str, Any]],
) -> None:
    if "live_public_web_context" not in source_families:
        return
    requested_policy_ids = _string_list(plan.get("web_scope_policy_ids") or metadata.get("web_scope_policy_ids") or metadata.get("web_scope_policy_id"))
    live_web = inventory.get("live_public_web_context") if isinstance(inventory.get("live_public_web_context"), Mapping) else {}
    inventory_policy_ids = set(_string_list(live_web.get("web_scope_policy_ids")))
    if not requested_policy_ids:
        errors.append({"type": "live_web_scope_policy_required"})
        return
    if inventory_policy_ids:
        invalid = sorted(set(requested_policy_ids) - inventory_policy_ids)
        if invalid:
            errors.append({"type": "live_web_scope_policy_not_in_inventory", "web_scope_policy_ids": invalid})


def _check_playbook_plan_boundary(
    plan: Mapping[str, Any],
    metadata: Mapping[str, Any],
    inventory: Mapping[str, Any],
    *,
    allowed_sources: set[str],
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    candidates = [dict(item) for item in inventory.get("playbook_candidates") or [] if isinstance(item, Mapping)]
    if not candidates:
        return {}
    candidate_ids = {str(item.get("playbook_id") or "") for item in candidates}
    candidate_schemas = {str(item.get("industry_schema") or "") for item in candidates}
    selected_playbooks = set(_string_list(plan.get("selected_playbooks") or plan.get("selected_playbook_ids") or metadata.get("selected_playbooks") or metadata.get("selected_playbook_ids")))
    industry_schema = str(plan.get("industry_schema") or metadata.get("industry_schema") or "").strip()
    if selected_playbooks:
        invalid = sorted(playbook for playbook in selected_playbooks if playbook not in candidate_ids and playbook != "generic_public_research")
        if invalid:
            errors.append({"type": "selected_playbook_not_in_inventory_candidates", "playbook_ids": invalid})
    elif str(plan.get("execution_mode") or "") in {"standard_memo", "deep_research"}:
        warnings.append({"type": "selected_playbook_missing", "candidate_playbooks": sorted(candidate_ids)})
    if industry_schema and industry_schema not in candidate_schemas and industry_schema != "generic":
        errors.append(
            {
                "type": "industry_schema_not_supported_by_inventory_playbooks",
                "industry_schema": industry_schema,
                "candidate_industry_schemas": sorted(candidate_schemas),
            }
        )
    selected_policy = selected_playbook_policy(inventory, sorted(selected_playbooks) if selected_playbooks else None)
    if not selected_policy:
        return {}
    selected_ids = set(_string_list(selected_policy.get("selected_playbook_ids")))
    if "generic_public_research" in selected_ids:
        fallback_candidates = [item for item in candidates if str(item.get("playbook_id") or "") == "generic_public_research"]
        coverage_gap = next((item.get("coverage_gap") for item in fallback_candidates if isinstance(item.get("coverage_gap"), Mapping)), None)
        warnings.append(
            {
                "type": "generic_playbook_selected_coverage_gap",
                "coverage_gap": dict(coverage_gap or {"gap_type": "industry_playbook_not_matched"}),
            }
        )
    policy_sources = set(_string_list(selected_policy.get("default_source_families"))) | set(
        str(source) for source in dict(selected_policy.get("source_family_policy") or {}) if str(source)
    )
    always_allowed = {
        "primary_sec_filing",
        "company_authored_unaudited_sec_filing",
        "market_snapshot",
        "run_artifact",
    }
    outside_policy = sorted(source for source in allowed_sources if source not in policy_sources and source not in always_allowed)
    if outside_policy and selected_playbooks:
        warnings.append(
            {
                "type": "allowed_source_family_outside_selected_playbook_policy",
                "source_families": outside_policy,
                "selected_playbook_ids": sorted(selected_ids),
            }
        )
    forbidden_claims = _string_list(selected_policy.get("forbidden_claims"))
    if forbidden_claims:
        warnings.append(
            {
                "type": "playbook_forbidden_claims_available_for_verifier",
                "selected_playbook_ids": sorted(selected_ids),
                "forbidden_claims": forbidden_claims[:12],
            }
        )
    return selected_policy


def build_evidence_fusion_bundle(state: Mapping[str, Any]) -> dict[str, Any]:
    """Project runtime evidence rows into claim-authority labels before reflection."""
    candidate_rows = _evidence_fusion_candidate_rows(state)
    authority_rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for index, item in enumerate(candidate_rows, start=1):
        row = item["row"]
        projection = _authority_projection_for_row(
            row,
            row_channel=str(item.get("row_channel") or ""),
            index=index,
        )
        key = (
            str(projection.get("evidence_ref") or ""),
            str(projection.get("source_family") or ""),
            str(projection.get("row_channel") or ""),
            str(projection.get("claim_scope") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        authority_rows.append(projection)

    gap_register = _bounded_gap_register_from_state(state, authority_rows)
    summary = _evidence_fusion_summary(authority_rows, gap_register)
    return _sanitize_payload(
        {
            "schema_version": EVIDENCE_FUSION_BUNDLE_SCHEMA_VERSION,
            "policy": "authority_labeled_evidence_fusion_v0_1",
            "row_count": len(authority_rows),
            "authority_rows": authority_rows,
            "summary": summary,
            "bounded_gap_register": gap_register,
        }
    )


def _evidence_fusion_candidate_rows(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in (
        "runtime_ledger_rows",
        "context_rows",
        "market_snapshot_rows",
        "industry_snapshot_rows",
        "product_evidence_rows",
        "public_source_context_rows",
    ):
        for row in _row_dicts(state.get(key)):
            rows.append({"row_channel": key, "row": row})
    for row in _relationship_rows_from_state(state):
        rows.append({"row_channel": "relationship_graph_rows", "row": row})
    for row in _row_dicts(state.get("source_gaps")):
        rows.append({"row_channel": "source_gaps", "row": row})
    return rows


def _authority_projection_for_row(row: Mapping[str, Any], *, row_channel: str, index: int) -> dict[str, Any]:
    bounded = _bounded_row(row, index)
    family = _fusion_source_family(row, bounded)
    promotion_status = _product_evidence_promotion_status(row)
    gap_only = row_channel == "source_gaps" or _row_is_gap_only(row, promotion_status=promotion_status)
    lead_only = _row_is_lead_only(row, family=family)
    exact_value_authority = _row_has_exact_value_authority(
        row,
        row_channel=row_channel,
        source_family=family,
        promotion_status=promotion_status,
    )
    if gap_only or lead_only:
        exact_value_authority = False
    context_only = _row_is_context_only(
        row,
        source_family=family,
        promotion_status=promotion_status,
        exact_value_authority=exact_value_authority,
        gap_only=gap_only,
        lead_only=lead_only,
    )
    authority_tier = _authority_tier(
        source_family=family,
        exact_value_authority=exact_value_authority,
        context_only=context_only,
        lead_only=lead_only,
        gap_only=gap_only,
        promotion_status=promotion_status,
    )
    claim_scope = _claim_scope_for_authority(
        row,
        source_family=family,
        authority_tier=authority_tier,
        promotion_status=promotion_status,
        exact_value_authority=exact_value_authority,
        lead_only=lead_only,
        gap_only=gap_only,
    )
    projection = {
        **bounded,
        "row_channel": row_channel,
        "source_family": family,
        "authority_tier": authority_tier,
        "claim_scope": claim_scope,
        "exact_value_authority": exact_value_authority,
        "context_only": context_only,
        "lead_only": lead_only,
        "gap_only": gap_only,
        "runtime_fact_allowed": family == "company_product_evidence_graph" and promotion_status == "runtime_fact_allowed",
        "semantic_supplement": family == "milvus_semantic" or bool(bounded.get("semantic_supplement")),
        "authority_policy": "ledger_and_runtime_product_facts_only_for_exact_values",
    }
    if gap_only:
        projection["gap_type"] = _gap_type_for_row(row)
        projection["bounded_gap_reason"] = _bounded_gap_reason(row)
    return projection


def _fusion_source_family(row: Mapping[str, Any], bounded: Mapping[str, Any]) -> str:
    if _row_is_semantic_supplement(row) or bool(bounded.get("semantic_supplement")):
        return "milvus_semantic"
    family = _row_source_family(row) or str(bounded.get("source_family") or "").strip()
    if family:
        return family
    channel = str(row.get("row_channel") or "").strip()
    if channel == "runtime_ledger_rows":
        return "primary_sec_filing"
    return "primary_sec_filing"


def _row_has_exact_value_authority(
    row: Mapping[str, Any],
    *,
    row_channel: str,
    source_family: str,
    promotion_status: str,
) -> bool:
    if source_family in {"public_source_context", "milvus_semantic", "market_snapshot", "industry_snapshot", "relationship_graph", "live_public_web_context"}:
        return False
    if source_family == "company_product_evidence_graph":
        return promotion_status == "runtime_fact_allowed"
    if row_channel == "runtime_ledger_rows":
        return True
    if source_family == "primary_sec_filing" and bool(row.get("exact_value_authority")):
        return True
    if source_family == "company_authored_unaudited_sec_filing" and bool(row.get("exact_value_authority")):
        return True
    return False


def _row_is_context_only(
    row: Mapping[str, Any],
    *,
    source_family: str,
    promotion_status: str,
    exact_value_authority: bool,
    gap_only: bool,
    lead_only: bool,
) -> bool:
    if gap_only or lead_only or exact_value_authority:
        return False
    if bool(row.get("context_only")):
        return True
    if source_family in {
        "public_source_context",
        "milvus_semantic",
        "market_snapshot",
        "industry_snapshot",
        "relationship_graph",
        "live_public_web_context",
    }:
        return True
    if source_family == "company_product_evidence_graph" and promotion_status != "runtime_fact_allowed":
        return True
    return True


def _row_is_lead_only(row: Mapping[str, Any], *, family: str) -> bool:
    if family == "live_public_web_context":
        return True
    text = " ".join(
        str(row.get(key) or "").lower()
        for key in ("authority_tier", "claim_scope", "allowed_claim_scope", "promotion_status", "runtime_use_boundary")
    )
    return "lead_only" in text or "lead-only" in text or "search_lead" in text


def _row_is_gap_only(row: Mapping[str, Any], *, promotion_status: str) -> bool:
    if promotion_status == "gap_exposed_not_fallback":
        return True
    if row.get("gap_type") or row.get("reason") or row.get("reason_code"):
        marker = str(row.get("source_family") or row.get("source_tier") or "").strip()
        return marker in {"", "source_gap", "run_artifact", "company_product_evidence_graph", "public_source_context"}
    return bool(row.get("gap_only"))


def _authority_tier(
    *,
    source_family: str,
    exact_value_authority: bool,
    context_only: bool,
    lead_only: bool,
    gap_only: bool,
    promotion_status: str,
) -> str:
    if gap_only:
        return "gap_only"
    if lead_only:
        return "lead_only"
    if exact_value_authority:
        if source_family == "company_product_evidence_graph" and promotion_status == "runtime_fact_allowed":
            return "company_disclosed_product_kpi_fact"
        return "primary_exact_value"
    if context_only and source_family in {"primary_sec_filing", "company_authored_unaudited_sec_filing", "company_product_evidence_graph"}:
        return "company_disclosed_context"
    if context_only:
        return "context_or_proxy"
    return "context_or_proxy"


def _claim_scope_for_authority(
    row: Mapping[str, Any],
    *,
    source_family: str,
    authority_tier: str,
    promotion_status: str,
    exact_value_authority: bool,
    lead_only: bool,
    gap_only: bool,
) -> str:
    explicit = str(row.get("claim_scope") or row.get("allowed_claim_scope") or "").strip()
    if gap_only:
        return "bounded_gap_only"
    if lead_only:
        return "lead_generation_only"
    if source_family == "company_product_evidence_graph":
        if promotion_status == "runtime_fact_allowed":
            return explicit or "company_disclosed_product_kpi_fact"
        return explicit or "product_taxonomy_or_context_only"
    if source_family == "public_source_context":
        return explicit or "public_context_or_proxy_only"
    if source_family == "milvus_semantic":
        return explicit or "filing_semantic_recall_supplement_only"
    if source_family == "relationship_graph":
        return explicit or "scope_or_hypothesis_only"
    if source_family in {"market_snapshot", "industry_snapshot", "live_public_web_context"}:
        return explicit or "context_or_proxy_only"
    if exact_value_authority:
        return explicit or "reported_financial_fact"
    if authority_tier == "company_disclosed_context":
        return explicit or "company_disclosed_context_only"
    return explicit or "context_or_proxy_only"


def _bounded_gap_register_from_state(state: Mapping[str, Any], authority_rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()
    for index, row in enumerate(_row_dicts(state.get("source_gaps")), start=1):
        entry = _bounded_gap_entry(row, index=index, source="source_gaps")
        key = _bounded_gap_dedupe_key(entry)
        if key not in seen:
            seen.add(key)
            entries.append(entry)
    for row in authority_rows:
        if not bool(row.get("gap_only")):
            continue
        entry = _bounded_gap_entry(row, index=len(entries) + 1, source="evidence_fusion_authority_rows")
        key = _bounded_gap_dedupe_key(entry)
        if key in seen:
            continue
        seen.add(key)
        entries.append(entry)
    return {
        "schema_version": BOUNDED_GAP_REGISTER_SCHEMA_VERSION,
        "policy": "bounded_public_gap_not_fallback_v0_1",
        "gap_count": len(entries),
        "gaps": entries,
        "summary": {
            "by_gap_type": _count_by_key(entries, "gap_type"),
            "by_source_family": _count_by_key(entries, "source_family"),
            "commercial_tracker_gap_count": len([row for row in entries if row.get("gap_type") == "commercial_tracker_gap"]),
            "public_unavailable_gap_count": len([row for row in entries if row.get("gap_type") == "public_unavailable_gap"]),
            "parser_schema_gap_count": len([row for row in entries if row.get("gap_type") == "parser_schema_gap"]),
        },
    }


def _bounded_gap_dedupe_key(entry: Mapping[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        str(entry.get("source_family") or "").strip(),
        str(entry.get("gap_type") or "").strip(),
        str(entry.get("ticker") or "").upper().strip(),
        str(entry.get("metric") or "").strip(),
        str(entry.get("product_or_segment") or "").strip(),
        str(entry.get("bounded_reason") or "").strip(),
    )


def _bounded_gap_entry(row: Mapping[str, Any], *, index: int, source: str) -> dict[str, Any]:
    gap_type = _gap_type_for_row(row)
    evidence_ref = str(
        row.get("gap_id")
        or row.get("evidence_ref")
        or row.get("source_gap_id")
        or row.get("metric_id")
        or f"bounded_gap_{index}"
    )
    source_family = _fusion_source_family(row, row) if str(row.get("source_family") or "") != "source_gap" else ""
    if not source_family:
        source_family = str(row.get("source_family") or row.get("source_tier") or "unknown").strip() or "unknown"
    return {
        "gap_id": evidence_ref,
        "source_family": source_family,
        "gap_type": gap_type,
        "status": str(row.get("status") or row.get("gap_status") or "open").strip() or "open",
        "ticker": str(row.get("ticker") or row.get("company") or "").upper().strip(),
        "metric": str(row.get("metric") or row.get("metric_family") or row.get("field") or "").strip(),
        "product_or_segment": str(row.get("product_or_segment") or row.get("product") or "").strip(),
        "bounded_reason": _bounded_gap_reason(row),
        "repairability": _gap_repairability(gap_type),
        "register_source": source,
        "claim_boundary": "do_not_fill_with_generic_fallback_or_proxy_fact",
    }


def _gap_type_for_row(row: Mapping[str, Any]) -> str:
    explicit = str(row.get("gap_type") or row.get("gap_category") or "").strip()
    if explicit:
        return explicit
    text = " ".join(str(row.get(key) or "").lower() for key in ("reason", "reason_code", "bounded_reason", "bounded_gap_reason", "claim_scope", "summary"))
    if "commercial" in text or "tracker" in text or "consensus" in text:
        return "commercial_tracker_gap"
    if "parser" in text or "schema" in text or "table" in text or "column" in text or "region" in text:
        return "parser_schema_gap"
    if "unavailable" in text or "not_available" in text or "missing_source" in text or "401" in text:
        return "public_unavailable_gap"
    if "mapping" in text or "resolver" in text or "alias" in text:
        return "mapping_or_resolver_gap"
    if "endpoint" in text or "download" in text:
        return "endpoint_or_collector_gap"
    return "retrievable_gap"


def _bounded_gap_reason(row: Mapping[str, Any]) -> str:
    reason = str(row.get("bounded_reason") or row.get("bounded_gap_reason") or row.get("reason") or row.get("reason_code") or row.get("summary") or "").strip()
    return _truncate(reason, 500) if reason else "public_or_runtime_authority_not_available"


def _gap_repairability(gap_type: str) -> str:
    if gap_type == "commercial_tracker_gap":
        return "commercial_tracker_required"
    if gap_type == "public_unavailable_gap":
        return "blocked_until_public_source_available"
    if gap_type in {"parser_schema_gap", "mapping_or_resolver_gap", "endpoint_or_collector_gap", "retrievable_gap"}:
        return "public_repair_candidate"
    return "review_required"


def _evidence_fusion_summary(authority_rows: list[Mapping[str, Any]], gap_register: Mapping[str, Any]) -> dict[str, Any]:
    public_exact_violations = [
        row
        for row in authority_rows
        if row.get("source_family") == "public_source_context" and bool(row.get("exact_value_authority"))
    ]
    semantic_exact_violations = [
        row
        for row in authority_rows
        if row.get("source_family") == "milvus_semantic" and bool(row.get("exact_value_authority"))
    ]
    return {
        "row_count": len(authority_rows),
        "by_source_family": _count_by_key(authority_rows, "source_family"),
        "by_authority_tier": _count_by_key(authority_rows, "authority_tier"),
        "exact_authority_row_count": len([row for row in authority_rows if row.get("exact_value_authority")]),
        "context_only_row_count": len([row for row in authority_rows if row.get("context_only")]),
        "lead_only_row_count": len([row for row in authority_rows if row.get("lead_only")]),
        "gap_only_row_count": len([row for row in authority_rows if row.get("gap_only")]),
        "product_runtime_fact_count": len([row for row in authority_rows if row.get("runtime_fact_allowed")]),
        "semantic_supplement_row_count": len([row for row in authority_rows if row.get("semantic_supplement")]),
        "bounded_gap_count": int(gap_register.get("gap_count") or 0),
        "public_exact_authority_violation_count": len(public_exact_violations),
        "semantic_exact_authority_violation_count": len(semantic_exact_violations),
        "forbidden_claim_scopes": _source_family_forbidden_claim_scopes(
            [str(row.get("source_family") or "") for row in authority_rows],
            semantic_row_count=len([row for row in authority_rows if row.get("semantic_supplement")]),
        ),
    }


def compile_multi_agent_retrieval_plan(
    evidence_requirement_plan: Mapping[str, Any],
    *,
    query_contract: Mapping[str, Any] | None = None,
    case: Mapping[str, Any] | None = None,
    activation_plan: Mapping[str, Any] | None = None,
    used_tool_calls_total: int = 0,
    used_tool_calls_by_agent: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    contract = dict(query_contract or {})
    if "evidence_requirements" not in contract and evidence_requirement_plan.get("requirements"):
        contract["evidence_requirements"] = list(evidence_requirement_plan.get("requirements") or [])
    plan = build_retrieval_plan(contract, case=dict(case or {}))
    plan = _coalesce_retrieval_plan_routes(plan, activation_plan or {})
    return _cap_retrieval_plan_routes(
        plan,
        activation_plan or {},
        used_tool_calls_total=used_tool_calls_total,
        used_tool_calls_by_agent=used_tool_calls_by_agent,
    )


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


def _coalesce_retrieval_plan_routes(plan: Mapping[str, Any], activation_plan: Mapping[str, Any]) -> dict[str, Any]:
    """Merge equivalent compiled routes before budget pruning.

    Research Lead can produce several business requirements that map to the
    same physical SEC/market/industry scope. This keeps the business tasks but
    avoids multiplying identical retrieval work.
    """
    merged_plan = dict(plan or {})
    routes = [dict(route) for route in merged_plan.get("routes") or [] if isinstance(route, Mapping)]
    if len(routes) <= 1 or not _route_coalescing_enabled(activation_plan):
        return merged_plan

    merged_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    merged_route_ids: dict[tuple[Any, ...], list[str]] = {}
    order: list[tuple[Any, ...]] = []
    for route in routes:
        key = _route_coalescing_key(route)
        if key not in merged_by_key:
            merged_by_key[key] = dict(route)
            merged_route_ids[key] = [str(route.get("route_id") or "")]
            order.append(key)
            continue
        base = merged_by_key[key]
        merged_route_ids[key].append(str(route.get("route_id") or ""))
        base["tickers"] = _dedupe([*_string_list(base.get("tickers")), *_string_list(route.get("tickers"))])
        base["years"] = sorted(set(_int_list(base.get("years")) + _int_list(route.get("years"))))
        base["filing_types"] = _dedupe([*_string_list(base.get("filing_types")), *_string_list(route.get("filing_types"))])
        base["source_tiers"] = _dedupe([*_string_list(base.get("source_tiers")), *_string_list(route.get("source_tiers"))])
        base["metric_families"] = _dedupe([*_string_list(base.get("metric_families")), *_string_list(route.get("metric_families"))])
        base["period_roles"] = _dedupe([*_string_list(base.get("period_roles")), *_string_list(route.get("period_roles"))])
        base["section_hints"] = _dedupe([*_string_list(base.get("section_hints")), *_string_list(route.get("section_hints"))])
        base["candidate_budget"] = max(_bounded_positive_int(base.get("candidate_budget"), default=0), _bounded_positive_int(route.get("candidate_budget"), default=0))
        base["rerank_budget"] = max(_bounded_positive_int(base.get("rerank_budget"), default=0), _bounded_positive_int(route.get("rerank_budget"), default=0))
        base["evidence_requirement_id"] = ",".join(
            _dedupe([*_string_list(base.get("evidence_requirement_id")), *_string_list(route.get("evidence_requirement_id"))])
        )
        coverage = dict(base.get("coverage_requirements") or {})
        other_coverage = route.get("coverage_requirements") if isinstance(route.get("coverage_requirements"), Mapping) else {}
        for field in ("tickers", "years", "filing_types", "source_tiers", "metric_families", "period_roles", "market_fields", "market_analysis_tools"):
            if field == "years":
                coverage[field] = sorted(set(_int_list(coverage.get(field)) + _int_list(other_coverage.get(field))))
            else:
                coverage[field] = _dedupe([*_string_list(coverage.get(field)), *_string_list(other_coverage.get(field))])
        base["coverage_requirements"] = {key: value for key, value in coverage.items() if value not in ([], {}, "", None)}

    merged_routes = []
    coalesced_groups = []
    for index, key in enumerate(order, start=1):
        route = dict(merged_by_key[key])
        route = _promote_coverage_scope_to_route(route)
        ids = [item for item in merged_route_ids[key] if item]
        if len(ids) > 1:
            route["route_id"] = f"{str(route.get('task_id') or 'coalesced')}::{route.get('retrieval_route')}::group_{index}"
            route["coalesced_route_ids"] = ids
            route["route_coalescing_policy"] = "same_route_scope_union_metric_families_v0_1"
            coalesced_groups.append(
                {
                    "route_id": route["route_id"],
                    "retrieval_route": route.get("retrieval_route") or "",
                    "source_route_ids": ids,
                }
            )
        merged_routes.append(route)

    if len(merged_routes) == len(routes):
        return merged_plan
    merged_plan["routes"] = merged_routes
    merged_plan["summary"] = _retrieval_plan_summary(merged_routes, task_count=len(merged_plan.get("tasks") or []))
    merged_plan["route_coalescing"] = {
        "policy": "execution_mode_route_scope_coalescing_v0_1",
        "original_route_count": len(routes),
        "coalesced_route_count": len(merged_routes),
        "coalesced_group_count": len(coalesced_groups),
        "groups": coalesced_groups,
    }
    return merged_plan


def _promote_coverage_scope_to_route(route: Mapping[str, Any]) -> dict[str, Any]:
    promoted = dict(route or {})
    coverage = promoted.get("coverage_requirements") if isinstance(promoted.get("coverage_requirements"), Mapping) else {}
    for field in (
        "tickers",
        "filing_types",
        "source_tiers",
        "metric_families",
        "period_roles",
        "section_hints",
        "market_fields",
        "market_analysis_tools",
        "vector_kinds",
    ):
        if not _string_list(promoted.get(field)) and _string_list(coverage.get(field)):
            promoted[field] = _string_list(coverage.get(field))
    if not _int_list(promoted.get("years")) and _int_list(coverage.get("years")):
        promoted["years"] = _int_list(coverage.get("years"))
    return promoted


def _route_coalescing_enabled(activation_plan: Mapping[str, Any]) -> bool:
    mode = str(activation_plan.get("execution_mode") or "").strip()
    if mode in {"focused_answer", "standard_memo", "deep_research"}:
        return True
    return _bool_value(os.environ.get("SEC_AGENT_COALESCE_RETRIEVAL_ROUTES"))


def _route_coalescing_key(route: Mapping[str, Any]) -> tuple[Any, ...]:
    route_name = str(route.get("retrieval_route") or "")
    coverage = route.get("coverage_requirements") if isinstance(route.get("coverage_requirements"), Mapping) else {}
    if route_name == "relationship_graph":
        return (
            route_name,
            tuple(sorted(set(_int_list(route.get("years") or coverage.get("years"))))),
        )
    if route_name == "market_snapshot":
        return (
            route_name,
            tuple(sorted(set(_int_list(route.get("years") or coverage.get("years"))))),
            tuple(sorted(_dedupe(_string_list(route.get("market_fields") or coverage.get("market_fields"))))),
            tuple(sorted(_dedupe(_string_list(route.get("source_families") or coverage.get("source_families"))))),
        )
    return (
        route_name,
        tuple(sorted(_dedupe(_string_list(route.get("tickers") or coverage.get("tickers"))))),
        tuple(sorted(set(_int_list(route.get("years") or coverage.get("years"))))),
        tuple(sorted(_dedupe(_string_list(route.get("filing_types") or coverage.get("filing_types"))))),
        tuple(sorted(_dedupe(_string_list(route.get("source_tiers") or coverage.get("source_tiers"))))),
        tuple(sorted(_dedupe(_string_list(route.get("period_roles") or coverage.get("period_roles"))))),
        tuple(sorted(_dedupe(_string_list(route.get("market_fields") or coverage.get("market_fields"))))),
        tuple(sorted(_dedupe(_string_list(route.get("source_families") or coverage.get("source_families"))))),
        tuple(sorted(_dedupe(_string_list(route.get("vector_kinds") or coverage.get("vector_kinds"))))),
    )


def _retrieval_plan_summary(routes: list[dict[str, Any]], *, task_count: int) -> dict[str, Any]:
    counts: dict[str, int] = {}
    candidate_budget = 0
    rerank_budget = 0
    for route in routes:
        route_name = str(route.get("retrieval_route") or "")
        counts[route_name] = counts.get(route_name, 0) + 1
        candidate_budget += int(route.get("candidate_budget") or 0)
        rerank_budget += int(route.get("rerank_budget") or 0)
    return {
        "task_count": int(task_count),
        "route_count": len(routes),
        "route_counts": dict(sorted(counts.items())),
        "candidate_budget_total": candidate_budget,
        "rerank_budget_total": rerank_budget,
        "second_pass_enabled": any(((route.get("second_pass_policy") or {}).get("enabled")) for route in routes),
    }


def _cap_retrieval_plan_routes(
    plan: Mapping[str, Any],
    activation_plan: Mapping[str, Any],
    *,
    used_tool_calls_total: int = 0,
    used_tool_calls_by_agent: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    if not activation_plan:
        return dict(plan or {})
    capped = dict(plan or {})
    routes = [dict(route) for route in capped.get("routes") or [] if isinstance(route, Mapping)]
    max_total = _bounded_positive_int(activation_plan.get("max_tool_calls_total"), default=-1)
    used_total = max(0, int(used_tool_calls_total or 0))
    remaining_total = max(0, max_total - used_total) if max_total >= 0 else -1
    used_by_agent = {str(agent_id): max(0, int(count or 0)) for agent_id, count in dict(used_tool_calls_by_agent or {}).items()}
    registry = agent_registry_by_id()
    per_agent_limits = {
        agent_id: int(entry.get("max_tool_calls") or 0)
        for agent_id, entry in registry.items()
        if int(entry.get("max_tool_calls") or 0) > 0
    }
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    call_keys_total: set[tuple[str, str]] = set()
    call_keys_by_agent: dict[str, set[tuple[str, str]]] = {}
    for route in routes:
        route_name = str(route.get("retrieval_route") or "")
        agent_id = ROUTE_OPERATOR_TOOL.get(route_name, ("", ""))[0]
        call_key = _route_budget_physical_call_key(route)
        consumes_new_call = call_key not in call_keys_total
        if remaining_total >= 0 and consumes_new_call and len(call_keys_total) >= remaining_total:
            dropped.append(
                {
                    "route_id": route.get("route_id") or "",
                    "retrieval_route": route_name,
                    "reason": "max_tool_calls_total",
                }
            )
            continue
        agent_limit = per_agent_limits.get(agent_id, 0)
        agent_keys = call_keys_by_agent.setdefault(agent_id, set())
        if agent_limit and consumes_new_call and used_by_agent.get(agent_id, 0) + len(agent_keys) >= agent_limit:
            dropped.append(
                {
                    "route_id": route.get("route_id") or "",
                    "retrieval_route": route_name,
                    "agent_id": agent_id,
                    "reason": "max_tool_calls_per_agent",
                    "budget_call_key": "::".join(call_key),
                }
            )
            continue
        kept.append(route)
        if consumes_new_call:
            call_keys_total.add(call_key)
            if agent_id:
                agent_keys.add(call_key)
    if len(kept) == len(routes):
        return capped
    capped["routes"] = kept
    summary = _retrieval_plan_summary(kept, task_count=len(capped.get("tasks") or []))
    capped["summary"] = {
        **summary,
        "route_budget_dropped_count": len(dropped),
        "route_budget_physical_tool_call_count": len(call_keys_total),
    }
    capped["route_budget_pruning"] = {
        "policy": "compiled_routes_capped_by_agent_permission_matrix",
        "counting_policy": "physical_tool_call_count_with_grouped_sec_text_routes_v0_1",
        "max_tool_calls_total": max_total,
        "used_tool_calls_total": used_total,
        "remaining_tool_calls_total": remaining_total,
        "per_agent_limits": per_agent_limits,
        "used_tool_calls_by_agent": used_by_agent,
        "kept_route_count": len(kept),
        "kept_physical_tool_call_count": len(call_keys_total),
        "kept_physical_tool_calls_by_agent": {
            agent: len(keys)
            for agent, keys in sorted(call_keys_by_agent.items())
            if agent
        },
        "dropped_route_count": len(dropped),
        "dropped_routes": dropped,
    }
    return capped


def _route_budget_physical_call_key(route: Mapping[str, Any]) -> tuple[str, str]:
    route_name = str(route.get("retrieval_route") or "")
    agent_id = ROUTE_OPERATOR_TOOL.get(route_name, ("", ""))[0]
    if route_name in SEC_SEARCH_TEXT_ROUTES:
        return (agent_id, "grouped_sec_search_text")
    return (agent_id, _route_identity(route))


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
    used_tool_calls_total: int = 0,
    used_tool_calls_by_agent: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Compile Reflection second-pass requests through the deterministic retrieval compiler."""
    second_pass_plan = second_pass_evidence_requirement_plan_from_reflection(
        reflection_report,
        base_evidence_requirement_plan,
        activation_plan=activation_plan,
    )
    contract = _query_contract_with_plan_scope(query_contract or {}, base_evidence_requirement_plan or {})
    contract["evidence_requirements"] = list(second_pass_plan.get("requirements") or [])
    retrieval_plan = compile_multi_agent_retrieval_plan(
        second_pass_plan,
        query_contract=contract,
        case=case,
        activation_plan=activation_plan,
        used_tool_calls_total=used_tool_calls_total,
        used_tool_calls_by_agent=used_tool_calls_by_agent,
    )
    retrieval_plan["second_pass_evidence_requirement_plan"] = second_pass_plan
    return retrieval_plan


def build_second_pass_reflection_diagnosis(
    reflection_report: Mapping[str, Any],
    *,
    evidence_fusion_bundle: Mapping[str, Any] | None = None,
    bounded_gap_register: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    report = normalize_reflection_report(reflection_report)
    request_by_id = {
        str(item.get("request_id") or item.get("requirement_id") or f"request_{index}"): dict(item)
        for index, item in enumerate(report.get("second_pass_requests") or [], start=1)
        if isinstance(item, Mapping)
    }
    missing_by_parent = {
        str(item.get("requirement_id") or item.get("task_id") or f"missing_{index}"): dict(item)
        for index, item in enumerate(report.get("missing_requirements") or [], start=1)
        if isinstance(item, Mapping)
    }
    bounded_gaps = [dict(item) for item in (bounded_gap_register or {}).get("gaps") or [] if isinstance(item, Mapping)]
    diagnoses: list[dict[str, Any]] = []
    for index, request in enumerate(request_by_id.values(), start=1):
        parent_id = str(request.get("parent_requirement_id") or request.get("requirement_id") or request.get("task_id") or "")
        missing = missing_by_parent.get(parent_id, {})
        source_families = _second_pass_source_families(request, missing)
        evidence_routes = _string_list(request.get("evidence_routes") or request.get("retrieval_routes") or missing.get("evidence_routes"))
        gap_type = _second_pass_gap_type(request, missing, source_families=source_families, evidence_routes=evidence_routes)
        diagnoses.append(
            {
                "diagnosis_id": f"diagnosis_{index}",
                "request_id": str(request.get("request_id") or f"second_pass_{index}"),
                "parent_requirement_id": str(request.get("parent_requirement_id") or ""),
                "task_id": str(request.get("task_id") or ""),
                "trigger": report.get("trigger") or "coverage_reflection",
                "gap_type": gap_type,
                "source_families": source_families,
                "evidence_routes": evidence_routes,
                "operator_owners": _string_list(request.get("operator_owners") or missing.get("operator_owners")) or _operator_owners_for_routes(evidence_routes),
                "tickers": _string_list(request.get("tickers") or missing.get("tickers")),
                "metric_families": _string_list(request.get("metric_families") or missing.get("metric_families")),
                "reason": _bounded_gap_reason({**missing, **request}),
                "original_request": _sanitize_payload(request),
                "matched_bounded_gap_ids": _matching_bounded_gap_ids(request, missing, bounded_gaps),
                "diagnosis_boundary": "diagnosis_only_no_new_facts",
            }
        )
    for gap in bounded_gaps:
        gap_id = str(gap.get("gap_id") or "")
        if not gap_id:
            continue
        if any(gap_id in _string_list(item.get("matched_bounded_gap_ids")) for item in diagnoses):
            continue
        diagnoses.append(
            {
                "diagnosis_id": f"diagnosis_{len(diagnoses) + 1}",
                "request_id": "",
                "parent_requirement_id": "",
                "task_id": "",
                "trigger": report.get("trigger") or "coverage_reflection",
                "gap_type": _gap_type_for_row(gap),
                "source_families": _string_list(gap.get("source_family")),
                "evidence_routes": [],
                "operator_owners": [],
                "tickers": _string_list(gap.get("ticker")),
                "metric_families": _string_list(gap.get("metric")),
                "reason": _bounded_gap_reason(gap),
                "original_request": {},
                "matched_bounded_gap_ids": [gap_id],
                "diagnosis_boundary": "bounded_gap_only_no_repair_request",
            }
        )
    fusion_summary = (evidence_fusion_bundle or {}).get("summary") if isinstance((evidence_fusion_bundle or {}).get("summary"), Mapping) else {}
    return _sanitize_payload(
        {
            "schema_version": SECOND_PASS_REFLECTION_DIAGNOSIS_SCHEMA_VERSION,
            "trigger": report.get("trigger") or "coverage_reflection",
            "diagnosis_count": len(diagnoses),
            "diagnoses": diagnoses,
            "summary": {
                "by_gap_type": _count_by_key(diagnoses, "gap_type"),
                "request_count": len(request_by_id),
                "bounded_gap_reference_count": len([item for item in diagnoses if item.get("matched_bounded_gap_ids")]),
                "pre_second_pass_exact_authority_row_count": int(fusion_summary.get("exact_authority_row_count") or 0),
            },
        }
    )


def build_second_pass_repair_plan(diagnosis: Mapping[str, Any]) -> dict[str, Any]:
    repairs: list[dict[str, Any]] = []
    for index, item in enumerate(diagnosis.get("diagnoses") or [], start=1):
        if not isinstance(item, Mapping):
            continue
        gap_type = str(item.get("gap_type") or "exact_value_missing")
        source_families = _string_list(item.get("source_families"))
        evidence_routes = _string_list(item.get("evidence_routes")) or _routes_for_source_families(source_families)
        action = _repair_action_for_gap(gap_type, source_families=source_families, evidence_routes=evidence_routes)
        repairs.append(
            {
                "repair_id": f"repair_{index}",
                "diagnosis_id": str(item.get("diagnosis_id") or f"diagnosis_{index}"),
                "request_id": str(item.get("request_id") or ""),
                "parent_requirement_id": str(item.get("parent_requirement_id") or ""),
                "trigger": item.get("trigger") or diagnosis.get("trigger") or "coverage_reflection",
                "gap_type": gap_type,
                "repair_action": action,
                "source_families": source_families,
                "evidence_routes": evidence_routes,
                "operator_owners": _string_list(item.get("operator_owners")) or _operator_owners_for_routes(evidence_routes),
                "expected_authority_delta": _expected_authority_delta_for_repair(action, source_families=source_families, evidence_routes=evidence_routes),
                "original_request": dict(item.get("original_request") or {}) if isinstance(item.get("original_request"), Mapping) else {},
                "matched_bounded_gap_ids": _string_list(item.get("matched_bounded_gap_ids")),
                "planner_boundary": "repair_plan_only_no_tool_execution",
            }
        )
    return _sanitize_payload(
        {
            "schema_version": SECOND_PASS_REPAIR_PLAN_SCHEMA_VERSION,
            "trigger": diagnosis.get("trigger") or "coverage_reflection",
            "repair_count": len(repairs),
            "repairs": repairs,
            "summary": {
                "by_repair_action": _count_by_key(repairs, "repair_action"),
                "by_gap_type": _count_by_key(repairs, "gap_type"),
            },
        }
    )


def gate_second_pass_repair_plan(
    repair_plan: Mapping[str, Any],
    *,
    activation_plan: Mapping[str, Any] | None = None,
    ledger: ToolCallLedger | None = None,
    web_scope_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    activation = dict(activation_plan or {})
    allowed_sources = set(_string_list(activation.get("allowed_source_families")))
    budget_decision = ledger.can_start_second_pass() if ledger is not None else {"allowed": True, "reason": ""}
    decisions: list[dict[str, Any]] = []
    executable_requests: list[dict[str, Any]] = []
    bounded_gap_candidates: list[dict[str, Any]] = []
    for index, repair in enumerate(repair_plan.get("repairs") or [], start=1):
        if not isinstance(repair, Mapping):
            continue
        source_families = _string_list(repair.get("source_families"))
        evidence_routes = _string_list(repair.get("evidence_routes"))
        action = str(repair.get("repair_action") or "")
        request = dict(repair.get("original_request") or {}) if isinstance(repair.get("original_request"), Mapping) else {}
        block_reasons: list[str] = []
        if not budget_decision.get("allowed"):
            block_reasons.append(str(budget_decision.get("reason") or "second_pass_budget_exhausted"))
        if allowed_sources:
            disallowed = sorted(set(source_families) - allowed_sources)
            if disallowed:
                block_reasons.append("source_family_not_allowed")
        if action == "route_to_bounded_gap_register":
            block_reasons.append("gap_not_retrievable_under_public_runtime")
        if action == "run_source_specific_parser_repair":
            block_reasons.append("parser_schema_repair_not_runtime_executable")
        web_validation: dict[str, Any] = {}
        if action == "request_live_web_snapshot":
            web_validation = validate_web_evidence_request(request, web_scope_registry=web_scope_registry)
            if web_validation["status"] != "pass":
                block_reasons.extend(
                    _dedupe(
                        [
                            str(error.get("type") or "web_evidence_request_invalid")
                            for error in web_validation.get("errors") or []
                            if isinstance(error, Mapping)
                        ]
                    )
                    or ["web_evidence_request_invalid"]
                )
        if action != "route_to_bounded_gap_register" and not evidence_routes:
            block_reasons.append("no_executable_evidence_routes")
        if _repair_would_use_weak_proxy_for_strong_fact(repair):
            block_reasons.append("weak_proxy_cannot_replace_authority_fact")

        allowed = not block_reasons
        if allowed and request:
            normalized_web_request = (
                dict(web_validation.get("normalized_request") or {})
                if action == "request_live_web_snapshot" and isinstance(web_validation.get("normalized_request"), Mapping)
                else {}
            )
            executable_requests.append(
                {
                    **request,
                    **normalized_web_request,
                    "repair_id": repair.get("repair_id") or f"repair_{index}",
                    "repair_action": action,
                    "expected_authority_delta": repair.get("expected_authority_delta") or "",
                }
            )
        if not allowed:
            bounded_gap_candidates.append(_repair_as_bounded_gap_candidate(repair, block_reasons=block_reasons))
        decisions.append(
            {
                "repair_id": repair.get("repair_id") or f"repair_{index}",
                "diagnosis_id": repair.get("diagnosis_id") or "",
                "request_id": repair.get("request_id") or "",
                "gap_type": repair.get("gap_type") or "",
                "repair_action": action,
                "allowed": allowed,
                "block_reasons": block_reasons,
                "source_families": source_families,
                "evidence_routes": evidence_routes,
                "web_request_validation": web_validation,
            }
        )
    return _sanitize_payload(
        {
            "schema_version": SECOND_PASS_HARD_GATE_SCHEMA_VERSION,
            "status": "pass" if executable_requests else "blocked",
            "trigger": repair_plan.get("trigger") or "coverage_reflection",
            "policy": "second_pass_repair_hard_gate_v0_1",
            "decision_count": len(decisions),
            "decisions": decisions,
            "executable_requests": executable_requests,
            "bounded_gap_candidates": bounded_gap_candidates,
            "summary": {
                "executable_request_count": len(executable_requests),
                "blocked_repair_count": len([item for item in decisions if not item.get("allowed")]),
                "by_block_reason": _count_block_reasons(decisions),
            },
        }
    )


def audit_second_pass_delta(
    before_fusion_bundle: Mapping[str, Any] | None,
    after_fusion_bundle: Mapping[str, Any] | None,
    *,
    hard_gate: Mapping[str, Any] | None = None,
    execution_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    before_rows = [dict(item) for item in (before_fusion_bundle or {}).get("authority_rows") or [] if isinstance(item, Mapping)]
    after_rows = [dict(item) for item in (after_fusion_bundle or {}).get("authority_rows") or [] if isinstance(item, Mapping)]
    before_exact_refs = _authority_refs(before_rows, exact_only=True)
    after_exact_refs = _authority_refs(after_rows, exact_only=True)
    before_authority_refs = _authority_refs(before_rows, exact_only=False)
    after_authority_refs = _authority_refs(after_rows, exact_only=False)
    added_exact_refs = sorted(after_exact_refs - before_exact_refs)
    added_authority_refs = sorted(after_authority_refs - before_authority_refs)
    added_row_count = _second_pass_added_row_count(execution_result or {})
    source_gap_delta = len((execution_result or {}).get("source_gaps") or [])
    executable_decisions = [
        dict(item)
        for item in (hard_gate or {}).get("decisions") or []
        if isinstance(item, Mapping) and item.get("allowed")
    ]
    blocked_decisions = [
        dict(item)
        for item in (hard_gate or {}).get("decisions") or []
        if isinstance(item, Mapping) and not item.get("allowed")
    ]
    closed_gap_ids = [str(item.get("diagnosis_id") or item.get("request_id") or item.get("repair_id") or "") for item in executable_decisions[: len(added_authority_refs)] if str(item.get("diagnosis_id") or item.get("request_id") or item.get("repair_id") or "")]
    open_gap_ids = [
        str(item.get("diagnosis_id") or item.get("request_id") or item.get("repair_id") or "")
        for item in [*executable_decisions[len(closed_gap_ids) :], *blocked_decisions]
        if str(item.get("diagnosis_id") or item.get("request_id") or item.get("repair_id") or "")
    ]
    authority_bearing_delta = len(added_authority_refs)
    stop_reason = "" if authority_bearing_delta else "no_new_authority_bearing_evidence"
    return _sanitize_payload(
        {
            "schema_version": SECOND_PASS_DELTA_AUDIT_SCHEMA_VERSION,
            "status": "pass" if authority_bearing_delta else "no_authority_delta",
            "added_row_count": added_row_count,
            "added_exact_authority_row_count": len(added_exact_refs),
            "added_authority_bearing_row_count": authority_bearing_delta,
            "added_exact_authority_refs": added_exact_refs[:20],
            "added_authority_refs": added_authority_refs[:20],
            "closed_gap_ids": closed_gap_ids,
            "open_gap_ids": open_gap_ids,
            "source_gap_delta": source_gap_delta,
            "bounded_answer_allowed": not bool(authority_bearing_delta),
            "stop_reason": stop_reason,
            "policy": "authority_delta_required_to_continue_second_pass_v0_1",
        }
    )


def _second_pass_source_families(request: Mapping[str, Any], missing: Mapping[str, Any]) -> list[str]:
    families = _string_list(
        request.get("source_families")
        or request.get("source_family_gaps")
        or missing.get("source_families")
        or missing.get("source_family_gaps")
    )
    if families:
        return families
    routes = _string_list(request.get("evidence_routes") or missing.get("evidence_routes"))
    return _source_families_for_routes(routes)


def _second_pass_gap_type(
    request: Mapping[str, Any],
    missing: Mapping[str, Any],
    *,
    source_families: list[str],
    evidence_routes: list[str],
) -> str:
    explicit = str(
        request.get("gap_type")
        or request.get("quality_gap_type")
        or missing.get("gap_type")
        or missing.get("quality_gap_type")
        or ""
    ).strip()
    if explicit:
        if explicit == "missing_numeric_runtime_ledger":
            return "exact_value_missing"
        if explicit == "missing_required_ticker_claim_card":
            return "citation_weak"
        if explicit == "missing_relationship_claim_ref":
            return "relationship_scope_gap"
        return explicit
    combined = {**dict(missing or {}), **dict(request or {})}
    reason = str(combined.get("reason") or combined.get("question_zh") or combined.get("analysis_intent") or "").lower()
    if "region" in reason:
        return "region_schema_gap"
    if "period" in reason or "column" in reason:
        return "period_column_group_gap"
    classified = _gap_type_for_row(combined)
    if classified != "retrievable_gap":
        return classified
    family_set = set(source_families)
    route_set = set(evidence_routes)
    if "parser" in reason or "table" in reason:
        return "product_kpi_parser_gap" if "company_product_evidence_graph" in family_set else "source_specific_table_gate_gap"
    if "commercial" in reason or "tracker" in reason:
        return "commercial_tracker_gap"
    if "milvus_semantic" in family_set or "milvus_semantic" in route_set:
        return "milvus_semantic_recall_gap"
    if "company_product_evidence_graph" in family_set:
        return "product_binding_missing"
    if "relationship_graph" in family_set:
        return "relationship_scope_gap"
    if "ledger_first" in route_set:
        return "exact_value_missing"
    if "risk_text" in route_set or "counter" in reason:
        return "counterevidence_missing"
    return "citation_weak"


def _matching_bounded_gap_ids(
    request: Mapping[str, Any],
    missing: Mapping[str, Any],
    bounded_gaps: list[Mapping[str, Any]],
) -> list[str]:
    if not bounded_gaps:
        return []
    tickers = set(_unique_upper(request.get("tickers") or missing.get("tickers") or []))
    metrics = set(_string_list(request.get("metric_families") or missing.get("metric_families")))
    families = set(_second_pass_source_families(request, missing))
    matches: list[str] = []
    for gap in bounded_gaps:
        gap_id = str(gap.get("gap_id") or "")
        if not gap_id:
            continue
        gap_ticker = str(gap.get("ticker") or "").upper().strip()
        gap_metric = str(gap.get("metric") or "").strip()
        gap_family = str(gap.get("source_family") or "").strip()
        if tickers and gap_ticker and gap_ticker not in tickers:
            continue
        if metrics and gap_metric and gap_metric not in metrics:
            continue
        if families and gap_family and gap_family not in families:
            continue
        matches.append(gap_id)
    return _dedupe(matches)


def _repair_action_for_gap(gap_type: str, *, source_families: list[str], evidence_routes: list[str]) -> str:
    if gap_type in {"commercial_tracker_gap", "public_unavailable_gap"}:
        return "route_to_bounded_gap_register"
    if gap_type in {"product_kpi_parser_gap", "region_schema_gap", "period_column_group_gap", "source_specific_table_gate_gap", "parser_schema_gap"}:
        return "run_source_specific_parser_repair"
    route_set = set(evidence_routes)
    family_set = set(source_families)
    if "ledger_first" in route_set:
        return "query_exact_ledger"
    if route_set & {"filing_text", "risk_text", "8k_commentary", "milvus_semantic"}:
        return "query_sec_table_or_text"
    if "company_product_evidence_graph" in family_set:
        return "query_product_evidence_graph"
    if "public_source_context" in family_set:
        return "query_public_source_context"
    if family_set & {"market_snapshot", "industry_snapshot"}:
        return "query_market_or_industry_snapshot"
    if "relationship_graph" in family_set:
        return "query_relationship_graph"
    if "live_public_web_context" in family_set:
        return "request_live_web_snapshot"
    return "route_to_bounded_gap_register"


def _expected_authority_delta_for_repair(
    action: str,
    *,
    source_families: list[str],
    evidence_routes: list[str],
) -> str:
    if action == "query_exact_ledger" or "ledger_first" in set(evidence_routes):
        return "exact_authority"
    if action == "query_product_evidence_graph":
        return "product_runtime_fact_if_runtime_fact_allowed"
    if action in {"query_sec_table_or_text", "query_relationship_graph"}:
        return "context_or_authority_depending_on_source_row"
    if action in {"query_public_source_context", "query_market_or_industry_snapshot", "request_live_web_snapshot"}:
        return "context_only"
    return "none"


def _repair_would_use_weak_proxy_for_strong_fact(repair: Mapping[str, Any]) -> bool:
    gap_type = str(repair.get("gap_type") or "")
    source_families = set(_string_list(repair.get("source_families")))
    if gap_type in {"exact_value_missing", "product_binding_missing", "product_kpi_parser_gap", "region_schema_gap", "period_column_group_gap"}:
        return bool(source_families & {"public_source_context", "market_snapshot", "industry_snapshot", "live_public_web_context"})
    return False


def _repair_as_bounded_gap_candidate(repair: Mapping[str, Any], *, block_reasons: list[str]) -> dict[str, Any]:
    source_families = _string_list(repair.get("source_families"))
    source_family = source_families[0] if source_families else "unknown"
    original = repair.get("original_request") if isinstance(repair.get("original_request"), Mapping) else {}
    return {
        "gap_id": str(repair.get("diagnosis_id") or repair.get("repair_id") or ""),
        "source_family": source_family,
        "gap_type": str(repair.get("gap_type") or "retrievable_gap"),
        "status": "blocked_by_second_pass_hard_gate",
        "ticker": ",".join(_string_list(original.get("tickers"))),
        "metric": ",".join(_string_list(original.get("metric_families"))),
        "bounded_reason": ",".join(block_reasons) or "second_pass_repair_blocked",
        "repairability": _gap_repairability(str(repair.get("gap_type") or "retrievable_gap")),
        "claim_boundary": "do_not_fill_with_generic_fallback_or_proxy_fact",
    }


def _count_block_reasons(decisions: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for decision in decisions:
        for reason in _string_list(decision.get("block_reasons")):
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def _authority_refs(rows: list[Mapping[str, Any]], *, exact_only: bool) -> set[str]:
    refs: set[str] = set()
    for row in rows:
        if exact_only and not bool(row.get("exact_value_authority")):
            continue
        if not exact_only and not _row_is_authority_bearing(row):
            continue
        ref = str(row.get("evidence_ref") or "")
        if ref:
            refs.add(ref)
    return refs


def _row_is_authority_bearing(row: Mapping[str, Any]) -> bool:
    if bool(row.get("exact_value_authority")):
        return True
    tier = str(row.get("authority_tier") or "")
    return tier in {"primary_exact_value", "company_disclosed_product_kpi_fact", "company_disclosed_context"}


def _second_pass_added_row_count(result: Mapping[str, Any]) -> int:
    return (
        len(result.get("context_rows") or [])
        + len(result.get("runtime_ledger_rows") or [])
        + len(result.get("market_snapshot_rows") or [])
        + len(result.get("industry_snapshot_rows") or [])
        + len(result.get("product_evidence_rows") or [])
        + len(result.get("public_source_context_rows") or [])
    )


def build_agent_data_view(agent_id: str, state: Mapping[str, Any]) -> dict[str, Any]:
    """Build the bounded role input allowed by the static agent registry."""
    registry = agent_registry_by_id()
    entry = dict(registry.get(str(agent_id or "")) or {})
    global_context = _global_context_for_agent_data_view(state)
    global_context_ref = _global_context_ref(global_context)
    dimension_portfolio = build_dimension_evidence_portfolio(
        state,
        tickers=_focus_tickers_from_state(state),
        repo_root=os.getcwd(),
        autoload=_product_intelligence_autoload_arg(state),
    )
    state_for_view = {**dict(state), "_dimension_evidence_portfolio": dimension_portfolio}
    dimension_portfolio_ref = compact_dimension_evidence_portfolio(dimension_portfolio, agent_id=str(agent_id or ""))
    if not entry:
        failed = {
            "schema_version": AGENT_DATA_VIEW_SCHEMA_VERSION,
            "status": "fail",
            "agent_id": str(agent_id or ""),
            "global_context_ref": global_context_ref,
            "dimension_evidence_portfolio_ref": dimension_portfolio_ref,
            "role_context": _role_context_for_agent_data_view(str(agent_id or ""), {}, state_for_view, [], {}, [], []),
            "bounded_evidence_rows": [],
            "source_family_bundle": {},
            "assigned_task_card": {},
            "required_claim_slots": [],
            "forbidden_claim_scopes": [],
            "bounded_gap_refs": _bounded_gap_refs_for_agent_data_view(state, []),
            "private_context_policy": "private_operator_context_excluded",
            "errors": [{"type": "unknown_agent", "agent_id": str(agent_id or "")}],
        }
        failed["context_digest"] = _payload_digest(failed)
        return _sanitize_payload(failed)

    allowed_views = _string_list(entry.get("allowed_data_views"))
    view: dict[str, Any] = {
        "schema_version": AGENT_DATA_VIEW_SCHEMA_VERSION,
        "status": "pass",
        "agent_id": entry["agent_id"],
        "allowed_data_views": allowed_views,
        "global_context_ref": global_context_ref,
        "dimension_evidence_portfolio_ref": compact_dimension_evidence_portfolio(
            dimension_portfolio,
            agent_id=entry["agent_id"],
        ),
        "role_context": {},
        "private_context_policy": "private_operator_context_excluded",
        "payload_policy": {
            "raw_evidence": "not_included",
            "private_paths": "stripped",
            "private_operator_context": "not_included",
            "milvus_handles": "not_included",
            "api_key_env_names": "not_included",
            "internal_reasoning": "not_included",
        },
        "summary": _state_summary_for_data_view(state),
        "input_budget": _data_view_input_budget(entry["agent_id"], state),
        "forbidden_claim_scopes": [],
        "bounded_gap_refs": [],
    }
    if entry["agent_id"] != "memo_writer":
        view["global_context"] = global_context

    allowed = set(allowed_views)
    bounded_rows: list[dict[str, Any]] = []
    source_family_bundle: dict[str, Any] = {}
    task_card: dict[str, Any] = {}
    required_claim_slots: list[dict[str, Any]] = []
    if "source_inventory" in allowed or "summary_only" in allowed:
        view["source_inventory"] = _sanitize_payload(_source_inventory_for_agent_view(state.get("project_inventory") or state.get("source_inventory") or {}))
    if "artifact_ref" in allowed:
        view["artifact_refs"] = _artifact_ref_summary(state.get("artifact_refs") or {})
    if "bounded_rows" in allowed:
        bounded_rows = _bounded_rows_for_agent_data_view(entry["agent_id"], state)
        view["bounded_evidence_rows"] = bounded_rows
        view["bounded_row_distribution"] = _bounded_row_distribution(bounded_rows)
        source_family_bundle = _source_family_bundle_for_agent(entry["agent_id"], bounded_rows, state)
        view["source_family_bundle"] = source_family_bundle
        if entry["agent_id"] == "product_technology_analyst":
            product_intelligence_rows = product_intelligence_context_rows_for_state(
                state,
                tickers=_focus_tickers_from_state(state),
                repo_root=os.getcwd(),
                max_rows=_product_intelligence_context_candidate_budget(
                    max_rows=_data_view_max_rows_for_agent(entry["agent_id"], state),
                    focus_ticker_count=len(_focus_tickers_from_state(state)),
                ),
                autoload=_product_intelligence_autoload_arg(state),
            )
            product_spec_pack = build_product_spec_pack(
                {**dict(state), "product_intelligence_context_rows": product_intelligence_rows},
                max_items=max(8, min(32, _data_view_max_rows_for_agent(entry["agent_id"], state))),
            )
            view["product_spec_pack"] = product_spec_pack
            view["product_spec_pack_ref"] = compact_product_spec_pack(product_spec_pack)
            view["product_intelligence_pack_ref"] = compact_product_intelligence_pack_refs(
                state,
                tickers=_focus_tickers_from_state(state),
                repo_root=os.getcwd(),
                autoload=_product_intelligence_autoload_arg(state),
            )
            view["product_evidence_pack_ref"] = compact_ai_semis_product_evidence_pack_refs(
                state,
                tickers=_focus_tickers_from_state(state),
                repo_root=os.getcwd(),
                autoload=_product_intelligence_autoload_arg(state),
            )
        if entry["agent_id"] in {"fundamental_analyst", "industry_supply_chain_analyst", "risk_counterevidence_analyst"}:
            capital_macro_pack = build_capital_macro_pack(
                state,
                max_items=max(8, min(32, _data_view_max_rows_for_agent(entry["agent_id"], state))),
            )
            if (capital_macro_pack.get("summary") or {}).get("input_row_count"):
                view["capital_macro_pack"] = capital_macro_pack
                view["capital_macro_pack_ref"] = compact_capital_macro_pack(capital_macro_pack)
        if entry["agent_id"] == "fundamental_analyst":
            fundamental_statement_pack = build_fundamental_statement_pack(
                state,
                max_items=max(16, min(80, _data_view_max_rows_for_agent(entry["agent_id"], state) * 2)),
            )
            if (fundamental_statement_pack.get("summary") or {}).get("line_item_count"):
                view["fundamental_statement_pack"] = fundamental_statement_pack
                view["fundamental_statement_pack_ref"] = compact_fundamental_statement_pack(
                    fundamental_statement_pack,
                    max_line_items=max(12, min(24, _data_view_max_rows_for_agent(entry["agent_id"], state))),
                )
                fundamental_peer_statement_panel = build_fundamental_peer_statement_panel(
                    {**dict(state), "fundamental_statement_pack": fundamental_statement_pack},
                    max_items=max(16, min(80, _data_view_max_rows_for_agent(entry["agent_id"], state) * 2)),
                )
                view["fundamental_peer_statement_panel"] = fundamental_peer_statement_panel
                view["fundamental_peer_statement_panel_ref"] = compact_fundamental_peer_statement_panel(
                    fundamental_peer_statement_panel,
                    max_items=max(8, min(16, _data_view_max_rows_for_agent(entry["agent_id"], state))),
                )
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
        required_claim_slots = _required_claim_slots_for_specialist(
            entry["agent_id"],
            state,
            task_card=task_card,
        )
        view["required_claim_slots"] = required_claim_slots
        view["counterclaim_slots"] = _counterclaim_slots_for_specialist(
            entry["agent_id"],
            state,
            task_card=task_card,
        )
    view["forbidden_claim_scopes"] = _string_list(source_family_bundle.get("forbidden_claim_scopes"))[:32]
    view["bounded_gap_refs"] = _bounded_gap_refs_for_agent_data_view(state, bounded_rows)
    view["role_context"] = _role_context_for_agent_data_view(
        entry["agent_id"],
        entry,
        state_for_view,
        bounded_rows,
        source_family_bundle,
        task_card,
        required_claim_slots,
    )
    view["context_digest"] = _payload_digest(
        {
            "schema_version": view["schema_version"],
            "agent_id": view["agent_id"],
            "global_context_ref": view["global_context_ref"],
            "dimension_evidence_portfolio_ref": view.get("dimension_evidence_portfolio_ref") or {},
            "role_context": view["role_context"],
            "bounded_row_distribution": view.get("bounded_row_distribution") or {},
            "source_family_bundle": view.get("source_family_bundle") or {},
            "product_spec_pack_ref": view.get("product_spec_pack_ref") or {},
            "product_intelligence_pack_ref": view.get("product_intelligence_pack_ref") or {},
            "product_evidence_pack_ref": view.get("product_evidence_pack_ref") or {},
            "capital_macro_pack_ref": view.get("capital_macro_pack_ref") or {},
            "fundamental_statement_pack_ref": view.get("fundamental_statement_pack_ref") or {},
            "fundamental_peer_statement_panel_ref": view.get("fundamental_peer_statement_panel_ref") or {},
            "assigned_task_card": view.get("assigned_task_card") or {},
            "required_claim_slots": view.get("required_claim_slots") or [],
            "bounded_gap_refs": view.get("bounded_gap_refs") or [],
        }
    )

    return _sanitize_payload(view)


def _global_context_for_agent_data_view(state: Mapping[str, Any]) -> dict[str, Any]:
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    gap_register = _bounded_gap_register_for_agent_data_view(state)
    return _sanitize_payload(
        {
            "schema_version": "sec_agent_global_context_v0.3",
            "user_query": _truncate(str(state.get("user_query") or query_contract.get("raw_query") or query_contract.get("user_query") or ""), 500),
            "query_contract": {
                "focus_tickers": _string_list(query_contract.get("focus_tickers") or activation.get("focus_tickers"))[:16],
                "search_scope_tickers": _string_list(query_contract.get("search_scope_tickers") or activation.get("search_scope_tickers"))[:32],
                "question_type": str(query_contract.get("question_type") or query_contract.get("intent") or ""),
                "time_horizon": str(query_contract.get("time_horizon") or ""),
                "raw_query_present": bool(query_contract.get("raw_query") or state.get("user_query")),
            },
            "activation_plan": {
                "execution_mode": str(activation.get("execution_mode") or state.get("execution_mode") or ""),
                "activate_agents": _string_list(activation.get("activate_agents"))[:16],
                "allowed_source_families": _string_list(activation.get("allowed_source_families"))[:16],
                "agent_priorities": dict(activation.get("agent_priorities") or {}) if isinstance(activation.get("agent_priorities"), Mapping) else {},
                "max_tool_calls_total": activation.get("max_tool_calls_total"),
            },
            "selected_playbook_ids": _selected_playbook_ids_from_state(state),
            "source_inventory_brief": _source_inventory_brief_for_global_context(state),
            "source_boundary_registry": _source_boundary_registry_for_global_context(state),
            "coverage_summary": _coverage_summary_for_global_context(state),
            "bounded_gap_register": _compact_bounded_gap_register_for_context(gap_register),
            "claim_card_schema": _claim_card_schema_for_global_context(),
            "run_trace_summary": _run_trace_summary_for_global_context(state),
        }
    )


def _global_context_ref(global_context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "sec_agent_global_context_ref_v0.3",
        "context_digest": _payload_digest(global_context),
        "visible_fields": [
            "user_query",
            "query_contract",
            "activation_plan",
            "selected_playbook_ids",
            "source_inventory_brief",
            "source_boundary_registry",
            "coverage_summary",
            "bounded_gap_register",
            "claim_card_schema",
            "run_trace_summary",
        ],
        "private_context_policy": "private_operator_context_excluded",
    }


def _role_context_for_agent_data_view(
    agent_id: str,
    entry: Mapping[str, Any],
    state: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    source_family_bundle: Mapping[str, Any],
    task_card: Mapping[str, Any],
    required_claim_slots: list[Mapping[str, Any]],
) -> dict[str, Any]:
    allowed_views = _string_list(entry.get("allowed_data_views"))
    dimension_portfolio = (
        state.get("_dimension_evidence_portfolio")
        if isinstance(state.get("_dimension_evidence_portfolio"), Mapping)
        else build_dimension_evidence_portfolio(
            state,
            tickers=_focus_tickers_from_state(state),
            repo_root=os.getcwd(),
            autoload=_product_intelligence_autoload_arg(state),
        )
    )
    base = {
        "schema_version": "sec_agent_role_context_v0.3",
        "agent_id": str(agent_id or ""),
        "role_context_type": _role_context_type(agent_id),
        "allowed_data_views": allowed_views,
        "private_context_policy": "private_operator_context_excluded",
        "raw_rows_visible": False,
        "bounded_rows_visible": "bounded_rows" in set(allowed_views),
        "selected_source_families": _string_list(source_family_bundle.get("selected_source_families"))[:16],
        "context_only_source_families": _string_list(source_family_bundle.get("context_only_source_families"))[:16],
        "exact_value_authority_source_families": _string_list(source_family_bundle.get("exact_value_authority_source_families"))[:16],
        "forbidden_claim_scopes": _string_list(source_family_bundle.get("forbidden_claim_scopes"))[:32],
        "bounded_gap_refs": _bounded_gap_refs_for_agent_data_view(state, rows)[:16],
        "dimension_evidence_portfolio_ref": compact_dimension_evidence_portfolio(dimension_portfolio, agent_id=agent_id),
    }
    if agent_id in SPECIALIST_EXECUTION_ORDER:
        base.update(
            {
                "assigned_memo_slot": str(task_card.get("assigned_memo_slot") or _specialist_memo_slot(agent_id)),
                "analyst_lens": str(task_card.get("analyst_lens") or _specialist_lens(agent_id)),
                "required_claim_slot_ids": [
                    str(slot.get("slot_id") or "")
                    for slot in required_claim_slots
                    if isinstance(slot, Mapping) and str(slot.get("slot_id") or "")
                ][:12],
                "bounded_row_count": len(rows),
                "claim_card_output_required": True,
            }
        )
        if agent_id == "product_technology_analyst":
            base.update(
                {
                    "product_spec_pack_required": True,
                    "product_spec_pack_policy": "parser_gated_product_objects_and_boundaries_only_no_public_proxy_financial_promotion",
                    "product_spec_pack_output_required": True,
                    "product_intelligence_graph_allowed": True,
                    "product_intelligence_graph_policy": "company_pack_may_seed taxonomy/spec/deployment/supply-chain/comparable context, but only exact product KPI rows carry exact-value authority",
                    "product_evidence_pack_required": True,
                    "product_evidence_pack_policy": (
                        "ProductEvidencePack v0.2 is the first product-analysis input: specs, deployment/adoption, "
                        "performance proxy, KPI exact, and relationship graph stay separate with source boundaries."
                    ),
                }
            )
        if agent_id in {"fundamental_analyst", "industry_supply_chain_analyst", "risk_counterevidence_analyst"}:
            base.update(
                {
                    "capital_macro_pack_allowed": True,
                    "capital_macro_pack_policy": "capital_ownership_and_macro_edges_require_parser_gates_13f_lag_and_exposure_bridge",
                }
            )
        if agent_id == "fundamental_analyst":
            base.update(
                {
                    "fundamental_statement_pack_required": True,
                    "fundamental_statement_pack_policy": (
                        "three_statement_peer_industry_focus_pack_from_reconciled_public_rows; "
                        "peer comparisons require same metric, period, and unit; proxy rows stay gaps or context"
                    ),
                }
            )
    elif agent_id == "memo_writer":
        base.update(
            {
                "allowed_input_views": ["verified_judgment_plan", "approved_claim_cards", "bounded_gap_register"],
                "bounded_rows_visible": False,
                "memo_writer_policy": "verified_judgment_plan_only_no_raw_or_bounded_rows",
            }
        )
    elif agent_id == "research_lead":
        base.update(
            {
                "planning_inputs": [
                    "source_inventory_brief",
                    "playbook_candidates",
                    "source_boundary_registry",
                    "query_contract",
                    "dimension_evidence_portfolio_ref",
                ],
                "supervising_analyst_role": True,
                "lead_review_checkpoint_required": True,
                "targeted_repair_policy": "only retrievable dimension gaps get targeted repair; bounded/commercial gaps stay explicit",
                "raw_rows_visible": False,
            }
        )
    elif agent_id in {"coverage_reflection", "judgment_plan_aggregator", "verifier"}:
        base.update(
            {
                "review_inputs": allowed_views,
                "bounded_row_count": len(rows),
                "claim_boundary_check_required": True,
            }
        )
    return _sanitize_payload(base)


def _role_context_type(agent_id: str) -> str:
    if agent_id in SPECIALIST_EXECUTION_ORDER:
        return "specialist"
    if agent_id == "memo_writer":
        return "memo_writer"
    if agent_id == "research_lead":
        return "research_lead"
    if agent_id in {"coverage_reflection", "judgment_plan_aggregator", "verifier"}:
        return "review_barrier"
    return "operator_or_support"


def _source_inventory_brief_for_global_context(state: Mapping[str, Any]) -> dict[str, Any]:
    inventory = state.get("project_inventory") if isinstance(state.get("project_inventory"), Mapping) else {}
    if not inventory and isinstance(state.get("source_inventory"), Mapping):
        inventory = state.get("source_inventory")  # type: ignore[assignment]
    if inventory:
        return _sanitize_payload(_source_inventory_for_agent_view(inventory))
    return {
        "schema_version": "inventory_brief_unavailable_v0.1",
        "available_source_families": _available_source_families_from_state(state),
        "source_family_availability": {},
        "milvus_runtime": _milvus_runtime_context_from_state(state),
    }


def _source_boundary_registry_for_global_context(state: Mapping[str, Any]) -> dict[str, Any]:
    inventory = _source_inventory_brief_for_global_context(state)
    return {
        "schema_version": "sec_agent_source_boundary_registry_v0.3",
        "allowed_source_families": _available_source_families_from_state(state),
        "source_family_authority": dict(inventory.get("source_family_authority") or {}) if isinstance(inventory.get("source_family_authority"), Mapping) else {},
        "source_boundaries": dict(inventory.get("source_boundaries") or {}) if isinstance(inventory.get("source_boundaries"), Mapping) else {},
        "milvus_runtime": _milvus_runtime_context_from_state(state),
        "private_operator_context": "excluded",
    }


def _coverage_summary_for_global_context(state: Mapping[str, Any]) -> dict[str, Any]:
    bundle = state.get("evidence_fusion_bundle") if isinstance(state.get("evidence_fusion_bundle"), Mapping) else {}
    fusion_summary = bundle.get("summary") if isinstance(bundle.get("summary"), Mapping) else {}
    coverage_view = _coverage_summary_view(state)
    return {
        "schema_version": "sec_agent_coverage_summary_v0.3",
        "row_counts": {
            "context_rows": len(state.get("context_rows") or []),
            "runtime_ledger_rows": len(state.get("runtime_ledger_rows") or []),
            "market_snapshot_rows": len(state.get("market_snapshot_rows") or []),
            "industry_snapshot_rows": len(state.get("industry_snapshot_rows") or []),
            "product_evidence_rows": len(state.get("product_evidence_rows") or []),
            "public_source_context_rows": len(state.get("public_source_context_rows") or []),
        },
        "fusion_summary": _sanitize_payload(fusion_summary),
        "reflection_summary": coverage_view,
    }


def _compact_bounded_gap_register_for_context(register: Mapping[str, Any]) -> dict[str, Any]:
    gaps = [dict(item) for item in register.get("gaps") or [] if isinstance(item, Mapping)]
    summary = register.get("summary") if isinstance(register.get("summary"), Mapping) else {}
    return _sanitize_payload(
        {
            "schema_version": str(register.get("schema_version") or BOUNDED_GAP_REGISTER_SCHEMA_VERSION),
            "gap_count": int(register.get("gap_count") or len(gaps)),
            "summary": dict(summary),
            "gap_refs": [
                {
                    "gap_id": str(gap.get("gap_id") or ""),
                    "source_family": str(gap.get("source_family") or ""),
                    "gap_type": str(gap.get("gap_type") or ""),
                    "ticker": str(gap.get("ticker") or ""),
                    "metric": str(gap.get("metric") or ""),
                    "repairability": str(gap.get("repairability") or ""),
                    "claim_boundary": str(gap.get("claim_boundary") or "do_not_fill_with_generic_fallback_or_proxy_fact"),
                }
                for gap in gaps[:24]
            ],
        }
    )


def _bounded_gap_register_for_agent_data_view(state: Mapping[str, Any]) -> dict[str, Any]:
    register = state.get("bounded_gap_register") if isinstance(state.get("bounded_gap_register"), Mapping) else {}
    if register:
        return dict(register)
    bundle = state.get("evidence_fusion_bundle") if isinstance(state.get("evidence_fusion_bundle"), Mapping) else {}
    register = bundle.get("bounded_gap_register") if isinstance(bundle.get("bounded_gap_register"), Mapping) else {}
    if register:
        return dict(register)
    return _bounded_gap_register_from_state(state, [])


def _bounded_gap_refs_for_agent_data_view(state: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    register = _bounded_gap_register_for_agent_data_view(state)
    gaps = [dict(item) for item in register.get("gaps") or [] if isinstance(item, Mapping)]
    if not gaps:
        return []
    row_refs = {str(row.get("evidence_ref") or row.get("gap_id") or "") for row in rows if isinstance(row, Mapping)}
    row_tickers = {str(row.get("ticker") or "").upper() for row in rows if isinstance(row, Mapping) and str(row.get("ticker") or "").strip()}
    row_families = {str(row.get("source_family") or "") for row in rows if isinstance(row, Mapping) and str(row.get("source_family") or "").strip()}
    selected: list[dict[str, Any]] = []
    for gap in gaps:
        gap_id = str(gap.get("gap_id") or "")
        ticker = str(gap.get("ticker") or "").upper()
        family = str(gap.get("source_family") or "")
        if rows and gap_id not in row_refs and ticker not in row_tickers and family not in row_families:
            continue
        selected.append(
            {
                "gap_id": gap_id,
                "source_family": family,
                "gap_type": str(gap.get("gap_type") or ""),
                "ticker": ticker,
                "metric": str(gap.get("metric") or ""),
                "repairability": str(gap.get("repairability") or ""),
                "claim_boundary": str(gap.get("claim_boundary") or "do_not_fill_with_generic_fallback_or_proxy_fact"),
            }
        )
    if not selected and not rows:
        selected = [
            {
                "gap_id": str(gap.get("gap_id") or ""),
                "source_family": str(gap.get("source_family") or ""),
                "gap_type": str(gap.get("gap_type") or ""),
                "ticker": str(gap.get("ticker") or "").upper(),
                "metric": str(gap.get("metric") or ""),
                "repairability": str(gap.get("repairability") or ""),
                "claim_boundary": str(gap.get("claim_boundary") or "do_not_fill_with_generic_fallback_or_proxy_fact"),
            }
            for gap in gaps[:12]
        ]
    return _sanitize_payload(selected[:16])


def _claim_card_schema_for_global_context() -> dict[str, Any]:
    return {
        "schema_version": "sec_agent_claim_card_schema_ref_v0.3",
        "required_fields": [
            "claim_id",
            "agent_id",
            "claim",
            "claim_type",
            "memo_slot",
            "evidence_refs",
            "source_families",
            "materiality",
        ],
        "evidence_policy": "supported_claims_must_cite_visible_bounded_evidence_refs",
        "gap_policy": "bounded_gap_refs_can_explain_missing_evidence_but_cannot_substitute_for_facts",
    }


def _run_trace_summary_for_global_context(state: Mapping[str, Any]) -> dict[str, Any]:
    trace = _tool_trace_summary_view(state)
    return {
        "schema_version": "sec_agent_run_trace_summary_v0.3",
        "tool_call_count": len(trace.get("tool_calls") or []),
        "tool_observation_count": len(trace.get("tool_observations") or []),
        "loop_break_reason": str(trace.get("loop_break_reason") or ""),
        "private_query_traces": "excluded",
    }


def _selected_playbook_ids_from_state(state: Mapping[str, Any]) -> list[str]:
    policy = _playbook_policy_from_state(state)
    if policy:
        return _string_list(policy.get("selected_playbook_ids"))[:8]
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    return _string_list(activation.get("selected_playbook_ids"))[:8]


def _available_source_families_from_state(state: Mapping[str, Any]) -> list[str]:
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    families = _string_list(activation.get("allowed_source_families"))
    if families:
        return families[:16]
    return sorted(
        family
        for family in {
            _row_source_family(row)
            for key in (
                "runtime_ledger_rows",
                "context_rows",
                "market_snapshot_rows",
                "industry_snapshot_rows",
                "product_evidence_rows",
                "public_source_context_rows",
            )
            for row in _row_dicts(state.get(key))
        }
        if family
    )


def _milvus_runtime_context_from_state(state: Mapping[str, Any]) -> dict[str, Any]:
    inventory = state.get("project_inventory") if isinstance(state.get("project_inventory"), Mapping) else {}
    runtime = {}
    for source in (
        state.get("milvus_runtime") if isinstance(state.get("milvus_runtime"), Mapping) else {},
        inventory.get("milvus_runtime") if isinstance(inventory.get("milvus_runtime"), Mapping) else {},
    ):
        if isinstance(source, Mapping) and source:
            runtime = dict(source)
            break
    location = str(runtime.get("location") or runtime.get("deployment") or runtime.get("mode") or "")
    available = bool(runtime.get("available")) if "available" in runtime else bool(location)
    return {
        "available": available,
        "location": location or ("cloud_or_local_configured" if available else "unavailable"),
        "semantic_authority_boundary": "semantic_recall_only_not_exact_value_authority",
        "private_handles": "excluded",
    }


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
                slot_id="fundamentals_three_statement_quality",
                memo_slot="fundamentals",
                target_claim_count=target,
                claim_type_allowlist=["company_reported_financial_fact", "reported_financial_fact", "business_observation"],
                required_source_families=["primary_sec_filing", "company_authored_unaudited_sec_filing"],
                instruction=(
                    "Use the FundamentalStatementPack first: connect income statement, balance sheet, and cash flow rows into one financial quality ClaimCard. "
                    "Preserve period role and cite filed/ledger refs only."
                ),
            ),
            _claim_slot(
                agent_id,
                slot_id="fundamentals_peer_comparison",
                memo_slot="fundamentals",
                target_claim_count="0-2",
                claim_type_allowlist=["business_observation"],
                required_source_families=["primary_sec_filing", "company_authored_unaudited_sec_filing"],
                instruction=(
                    "When same metric/period/unit peer rows exist in FundamentalStatementPack.peer_comparisons, state how the focus company compares. "
                    "If peer rows are missing or incompatible, expose the peer-comparison gap instead of making a relative claim."
                ),
            ),
            _claim_slot(
                agent_id,
                slot_id="fundamentals_industry_focus_metric",
                memo_slot="fundamentals",
                target_claim_count="1-2" if mode == "deep_research" else "0-1",
                claim_type_allowlist=["company_reported_financial_fact", "business_observation"],
                required_source_families=["primary_sec_filing", "company_authored_unaudited_sec_filing"],
                instruction=(
                    "Use FundamentalStatementPack.industry_focus_policy and industry_focus_coverage to prioritize the financial metrics that matter for this sector. "
                    "Do not treat unavailable tracker/proxy data as a filed financial fact."
                ),
            ),
            _claim_slot(
                agent_id,
                slot_id="fundamentals_product_or_capital_bridge",
                memo_slot="fundamentals",
                target_claim_count="0-2",
                claim_type_allowlist=["business_observation", "company_reported_financial_fact"],
                required_source_families=["primary_sec_filing", "company_authored_unaudited_sec_filing", "company_product_evidence_graph"],
                instruction=(
                    "Bridge financial statement rows to product/segment performance, working capital, capex, liquidity, or capital structure only when the pack exposes compatible rows. "
                    "Otherwise state the missing confirmation."
                ),
            ),
        ]
    if agent_id == "product_technology_analyst":
        return [
            _claim_slot(
                agent_id,
                slot_id="product_taxonomy_or_surface",
                memo_slot="product_technology",
                target_claim_count="1-2",
                claim_type_allowlist=["product_taxonomy_context", "business_observation"],
                required_source_families=["company_product_evidence_graph", "public_source_context", "live_public_web_context"],
                instruction="Describe the product, segment, SKU, platform, or technology surface. Company product graph rows are primary; public/live rows are enrichment context only.",
            ),
            _claim_slot(
                agent_id,
                slot_id="company_disclosed_product_kpi",
                memo_slot="product_technology",
                target_claim_count=target,
                claim_type_allowlist=["company_disclosed_product_kpi"],
                required_source_families=["company_product_evidence_graph"],
                instruction=(
                    "Write product KPI facts only from company_product_evidence_graph rows with "
                    "promotion_status=runtime_fact_allowed and exact_value_authority=true; include product/segment, value, unit, and period when visible."
                ),
            ),
            _claim_slot(
                agent_id,
                slot_id="public_proxy_or_verification_context",
                memo_slot="product_technology",
                target_claim_count="0-2",
                claim_type_allowlist=["public_proxy_context", "business_observation"],
                required_source_families=["public_source_context", "live_public_web_context"],
                instruction="Use public source and allowlisted web rows only as directional proxy, validation context, or lead evidence; do not convert them into product sales, share, inventory, margin, or profitability facts.",
            ),
            _claim_slot(
                agent_id,
                slot_id="product_relationship_deployment_context",
                memo_slot="product_technology",
                target_claim_count="0-2",
                claim_type_allowlist=["relationship_hypothesis", "business_observation"],
                required_source_families=["relationship_graph"],
                instruction=(
                    "Use ProductIntelligenceGraph or relationship_graph rows to connect product families to customers, suppliers, "
                    "deployment, configured-in, sold-through, or competitive/substitution context. Treat these rows as bounded "
                    "product adoption or transmission evidence only; do not infer exact product revenue, shipment, ASP, backlog, "
                    "order value, market share, gross margin, or inventory unless exact authority rows are present."
                ),
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
    if agent_id == "product_technology_analyst":
        return [
            _claim_slot(
                agent_id,
                slot_id="product_commercial_tracker_gap",
                memo_slot="product_technology",
                target_claim_count=common_cap,
                claim_type_allowlist=["source_gap", "unsupported_claim"],
                required_source_families=["company_product_evidence_graph", "public_source_context", "live_public_web_context"],
                instruction=(
                    "Expose missing sell-through, market share, channel inventory, app revenue, prescriptions, POS, ASP, or tracker forecast data as a commercial tracker gap; "
                    "do not backfill the gap with public proxy rows."
                ),
                slot_kind="counterclaim_or_gap",
            )
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
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
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
    candidates.extend(_requirements_from_research_objective_contract(activation.get("research_objective_contract")))
    thesis_path = activation.get("thesis_path") if isinstance(activation.get("thesis_path"), Mapping) else {}
    candidates.extend(_requirements_from_thesis_path(thesis_path))
    return _dedupe_requirements(candidates)


def _requirements_from_research_objective_contract(contract: Any) -> list[dict[str, Any]]:
    if not isinstance(contract, Mapping):
        return []
    requirements: list[dict[str, Any]] = []
    minimum = contract.get("minimum_evidence_requirements") if isinstance(contract.get("minimum_evidence_requirements"), Mapping) else {}
    required_dimensions = _string_list(contract.get("required_dimensions"))
    for key, payload in minimum.items():
        item = payload if isinstance(payload, Mapping) else {}
        req_id = str(key or item.get("required_item") or item.get("minimum_role") or "").strip()
        if not req_id:
            continue
        requirements.append(
            {
                "requirement_id": req_id,
                "task_id": req_id,
                "question_zh": str(item.get("question") or req_id),
                "priority": "primary",
                "analysis_intent": str(item.get("minimum_role") or req_id),
                "source_families": [],
                "evidence_routes": [],
                "metric_families": [],
                "contract_source": "research_objective_contract",
            }
        )
    for dimension in required_dimensions:
        req_id = str(dimension or "").strip()
        if not req_id:
            continue
        requirements.append(
            {
                "requirement_id": req_id,
                "task_id": req_id,
                "question_zh": req_id,
                "priority": "primary",
                "analysis_intent": req_id,
                "source_families": [],
                "evidence_routes": [],
                "metric_families": [],
                "contract_source": "research_objective_contract_required_dimension",
            }
        )
    return requirements


def _requirements_from_thesis_path(thesis_path: Mapping[str, Any]) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    for item in thesis_path.get("required_items") or thesis_path.get("path_nodes") or []:
        if not isinstance(item, Mapping):
            continue
        req_id = str(item.get("required_item") or item.get("dimension") or item.get("task_id") or "").strip()
        if not req_id:
            continue
        requirements.append(
            {
                "requirement_id": req_id,
                "task_id": req_id,
                "question_zh": str(item.get("question") or req_id),
                "priority": "primary",
                "analysis_intent": str(item.get("dimension") or req_id),
                "primary_agents": _string_list(item.get("primary_agents")),
                "source_families": [],
                "evidence_routes": [],
                "metric_families": [],
                "contract_source": "thesis_path",
            }
        )
    return requirements


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
        "route_selection_reason": str(requirement.get("route_selection_reason") or requirement.get("route_reason") or "")[:240],
        "route_cost_tier": str(requirement.get("route_cost_tier") or "")[:40],
        "route_selection_policy": str(requirement.get("route_selection_policy") or "")[:80],
        "metric_families": _string_list(requirement.get("metric_families") or requirement.get("required_metric_families"))[:12],
        "claim_families": claim_families[:8],
    }


def _requirement_matches_specialist(agent_id: str, requirement: Mapping[str, Any]) -> bool:
    if agent_id in set(_string_list(requirement.get("primary_agents") or requirement.get("assigned_agents"))):
        return True
    routes = set(_string_list(requirement.get("evidence_routes") or requirement.get("retrieval_routes")))
    families = set(_requirement_source_families(requirement))
    owners = set(_string_list(requirement.get("operator_owners") or requirement.get("operator_owner")))
    text = " ".join(
        str(requirement.get(key) or "").lower()
        for key in ("analysis_intent", "question_zh", "question", "task_id", "requirement_id")
    )
    if agent_id == "fundamental_analyst":
        return bool(families & {"primary_sec_filing", "company_authored_unaudited_sec_filing"} or routes & {"ledger_first", "filing_text", "8k_commentary"} or owners & {"sec_operator", "eight_k_operator"})
    if agent_id == "product_technology_analyst":
        return bool(
            families & {"company_product_evidence_graph", "public_source_context", "live_public_web_context"}
            or routes & {"live_public_web_context"}
            or owners & {"web_evidence_operator"}
            or any(
                term in text
                for term in (
                    "product",
                    "sku",
                    "taxonomy",
                    "platform",
                    "developer",
                    "clinical",
                    "trial",
                    "regulatory",
                    "app",
                    "product_kpi",
                    "产品",
                    "产品线",
                    "产品指标",
                    "主业",
                    "临床",
                    "监管",
                )
            )
        )
    if agent_id == "industry_supply_chain_analyst":
        return bool(
            families & {"industry_snapshot", "relationship_graph"}
            or routes & {"industry_snapshot", "relationship_graph"}
            or any(
                term in text
                for term in (
                    "industry",
                    "supply",
                    "relationship",
                    "sector",
                    "chain",
                    "readthrough",
                    "shipment",
                    "backlog",
                    "order",
                    "cycle",
                    "customer concentration",
                    "行业",
                    "供应",
                    "供应链",
                    "关系",
                    "需求传导",
                    "出货",
                    "出货周期",
                    "订单",
                    "积压",
                    "客户集中",
                    "周期",
                    "竞争位置",
                )
            )
        )
    if agent_id == "market_valuation_analyst":
        return bool(
            "market_snapshot" in families
            or "market_snapshot" in routes
            or any(
                term in text
                for term in (
                    "market",
                    "valuation",
                    "multiple",
                    "return",
                    "price",
                    "reaction",
                    "price-in",
                    "liquidity",
                    "short interest",
                    "市场",
                    "估值",
                    "股价",
                    "定价",
                    "资金面",
                    "流动性",
                    "反应",
                    "做空",
                )
            )
        )
    if agent_id == "risk_counterevidence_analyst":
        return bool(
            "run_artifact" in families
            or "risk_text" in routes
            or any(
                term in text
                for term in (
                    "risk",
                    "counter",
                    "gap",
                    "unsupported",
                    "conflict",
                    "caveat",
                    "downside",
                    "export control",
                    "regulatory",
                    "restriction",
                    "sanction",
                    "geopolitical",
                    "风险",
                    "反证",
                    "缺口",
                    "不支持",
                    "冲突",
                    "下行",
                    "出口限制",
                    "出口管制",
                    "监管",
                    "制裁",
                    "地缘",
                    "限制",
                )
            )
        )
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
        "product_technology_analyst": "product_taxonomy_company_disclosed_product_kpi_public_proxy_and_commercial_gap",
        "industry_supply_chain_analyst": "industry_supply_chain_relationship_hypotheses_and_transmission",
        "market_valuation_analyst": "timestamped_market_reaction_and_valuation_context",
        "risk_counterevidence_analyst": "risks_counterevidence_source_gaps_and_boundary_misuse",
    }.get(agent_id, "bounded_specialist_analysis")


def _specialist_memo_slot(agent_id: str) -> str:
    return {
        "fundamental_analyst": "fundamentals",
        "product_technology_analyst": "product_technology",
        "industry_supply_chain_analyst": "industry_relationship",
        "market_valuation_analyst": "market_valuation",
        "risk_counterevidence_analyst": "risk_counterevidence",
    }.get(agent_id, "thesis")


def _specialist_required_source_families(agent_id: str) -> list[str]:
    return {
        "fundamental_analyst": [
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "derived_metric_layer",
            "company_product_evidence_graph",
        ],
        "product_technology_analyst": [
            "company_product_evidence_graph",
            "relationship_graph",
            "public_source_context",
            "live_public_web_context",
        ],
        "industry_supply_chain_analyst": [
            "industry_snapshot",
            "relationship_graph",
            "company_product_evidence_graph",
            "public_source_context",
            "live_public_web_context",
        ],
        "market_valuation_analyst": ["market_snapshot"],
        "risk_counterevidence_analyst": [
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "company_product_evidence_graph",
            "public_source_context",
            "live_public_web_context",
            "market_snapshot",
            "industry_snapshot",
            "derived_metric_layer",
            "run_artifact",
        ],
    }.get(agent_id, [])


def _available_source_families_for_specialist(agent_id: str, state: Mapping[str, Any]) -> list[str]:
    families: list[str] = []
    for key in (
        "runtime_ledger_rows",
        "context_rows",
        "market_snapshot_rows",
        "industry_snapshot_rows",
        "product_evidence_rows",
        "public_source_context_rows",
    ):
        families.extend(_row_source_family(row) for row in _row_dicts(state.get(key)))
    families.extend(_row_source_family(row) for row in _derived_metric_rows_for_agent_data_view(agent_id, state))
    if _relationship_rows_from_state(state):
        families.append("relationship_graph")
    required = set(_specialist_required_source_families(agent_id))
    return [family for family in _dedupe(families) if not required or family in required]


def _focus_tickers_from_state(state: Mapping[str, Any]) -> list[str]:
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    scope = query_contract.get("scope") if isinstance(query_contract.get("scope"), Mapping) else {}
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    activation_contract = activation.get("research_objective_contract") if isinstance(activation.get("research_objective_contract"), Mapping) else {}
    activation_query = activation_contract.get("query_contract") if isinstance(activation_contract.get("query_contract"), Mapping) else {}
    activation_scope = activation_query.get("scope") if isinstance(activation_query.get("scope"), Mapping) else {}
    return _unique_upper(
        state.get("focus_tickers")
        or query_contract.get("focus_tickers")
        or scope.get("focus_tickers")
        or activation.get("focus_tickers")
        or activation_query.get("focus_tickers")
        or activation_scope.get("focus_tickers")
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
    execution_mode = _execution_mode_from_state(state)
    required_item_gate = _specialist_required_item_gate_enabled()
    decisions: list[dict[str, Any]] = []
    for agent_id in SPECIALIST_EXECUTION_ORDER:
        if agent_id not in active:
            continue
        priority = priorities.get(agent_id) or "primary"
        signal = _specialist_evidence_signal(agent_id, state)
        matched_requirement_count = _specialist_required_item_match_count(agent_id, state)
        should_run = priority in {"primary", "supporting"} or (priority == "conditional" and signal["signal_count"] > 0)
        if priority == "low":
            should_run = bool(signal["explicit_intent"] and signal["signal_count"] > 0)
        root_cause_reason = ""
        if required_item_gate:
            gate = _specialist_required_item_activation_gate(
                agent_id,
                state,
                execution_mode=execution_mode,
                priority=priority,
                signal=signal,
                matched_requirement_count=matched_requirement_count,
            )
            should_run = should_run and bool(gate["allowed"])
            root_cause_reason = str(gate.get("reason") or "")
        decisions.append(
            {
                "agent_id": agent_id,
                "priority": priority,
                "decision": "run" if should_run else "skipped",
                "reason": (
                    "priority_and_required_item_gate_allow_run"
                    if should_run and priority in {"primary", "supporting"}
                    else root_cause_reason or signal["reason"]
                ),
                "signal_count": signal["signal_count"],
                "matched_requirement_count": matched_requirement_count,
                "explicit_intent": bool(signal["explicit_intent"]),
                "policy": "cost_aware_required_item_specialist_activation_v0_2",
            }
        )
    return decisions


def _specialist_required_item_gate_enabled() -> bool:
    return str(os.environ.get("SEC_AGENT_SPECIALIST_REQUIRED_ITEM_GATE", "1")).strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }


def _specialist_required_item_match_count(agent_id: str, state: Mapping[str, Any]) -> int:
    requirements = _state_evidence_requirements(state)
    return sum(1 for requirement in requirements if _requirement_matches_specialist(agent_id, requirement))


def _specialist_required_item_activation_gate(
    agent_id: str,
    state: Mapping[str, Any],
    *,
    execution_mode: str,
    priority: str,
    signal: Mapping[str, Any],
    matched_requirement_count: int,
) -> dict[str, Any]:
    if str(execution_mode or "") not in {"standard_memo", "deep_research"}:
        return {"allowed": True, "reason": "non_research_mode_no_required_item_gate"}
    if matched_requirement_count > 0:
        return {"allowed": True, "reason": "matched_required_item"}
    if bool(signal.get("explicit_intent")) and int(signal.get("signal_count") or 0) > 0:
        return {"allowed": True, "reason": "explicit_user_intent_with_role_evidence"}
    if agent_id == "fundamental_analyst" and int(signal.get("signal_count") or 0) > 0:
        return {"allowed": True, "reason": "fundamental_core_financial_rows_visible"}
    if agent_id == "industry_supply_chain_analyst" and _relationship_rows_from_state(state):
        return {"allowed": True, "reason": "relationship_rows_visible_for_industry_lens"}
    if priority in {"supporting", "conditional", "low"}:
        return {
            "allowed": False,
            "reason": "supporting_specialist_skipped_no_matching_required_item_or_explicit_intent",
        }
    if agent_id in {"product_technology_analyst", "market_valuation_analyst", "risk_counterevidence_analyst"}:
        return {
            "allowed": False,
            "reason": "specialist_skipped_no_matching_required_item_or_explicit_intent",
        }
    return {"allowed": True, "reason": "primary_specialist_allowed_by_core_role"}


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
    routes = [dict(route) for route in retrieval_plan.get("routes") or [] if isinstance(route, Mapping)]
    sec_group = _sec_search_execution_group(routes, context=context, dry_run=dry_run)
    sec_group_cache: dict[str, Any] = {}

    for route in routes:
        route_name = str(route.get("retrieval_route") or "")
        original_route = dict(route)
        sec_group_member = _sec_group_member(sec_group, route)
        if sec_group_member and sec_group_cache.get("result") is not None and not sec_group_member.get("is_first"):
            agent_id, tool_name = _sec_search_agent_tool_for_route(original_route, context=context)
            permission = validate_operator_tool_call(agent_id=agent_id, tool_name=tool_name)
            if permission["status"] != "pass":
                observations.append(_observation(original_route, agent_id, tool_name, "blocked", error=permission["error"]))
                continue
            arguments = tool_arguments_from_route(
                _sec_search_member_execution_route(original_route, context=context),
                user_query=str(context.get("user_query") or ""),
                state_context=context,
            )
            cached_result = sec_group_cache["result"]
            boundary = validate_tool_observation_boundary(tool_name, cached_result)
            runtime_summary = {
                **_tool_runtime_summary(tool_name, cached_result),
                "cache_policy": "grouped_sec_search_route_reuse_v0_1",
                "cached_from_route_id": sec_group_cache.get("executed_route_id") or "",
                "grouped_route_count": len(sec_group.get("routes") or []),
            }
            rows_for_route = _sec_search_result_rows_for_route(cached_result, original_route)
            gaps = _source_gaps_from_result(cached_result)
            refs = [dict(item) for item in cached_result.get("artifact_refs") or [] if isinstance(item, Mapping)]
            active_ledger.record_tool_call(
                turn_id=turn_id,
                agent_id=agent_id,
                tool_name=tool_name,
                arguments=arguments,
                output_artifact_digest=_first_artifact_digest(refs),
                row_count=len(rows_for_route),
                source_gap_count=len(gaps),
                elapsed_ms=0,
                status="cached",
                metadata={
                    "route_id": original_route.get("route_id") or "",
                    "retrieval_route": route_name,
                    "boundary": boundary,
                    "runtime_summary": runtime_summary,
                    "argument_summary": _tool_argument_summary(arguments),
                    "grouped_sec_search_cache_hit": True,
                },
            )
            observations.append(
                _observation(
                    original_route,
                    agent_id,
                    tool_name,
                    "cached",
                    error=str(cached_result.get("error") or cached_result.get("failure_reason") or "")[:500],
                    arguments=arguments,
                    row_count=len(rows_for_route),
                    source_gap_count=len(gaps),
                    boundary=boundary,
                    runtime_summary=runtime_summary,
                )
            )
            continue

        if sec_group_member and sec_group_member.get("is_first"):
            route = _sec_search_group_execution_route(
                original_route,
                sec_group.get("routes") or [],
                retrieval_plan=retrieval_plan,
                context=context,
            )
            route_name = str(route.get("retrieval_route") or "")
        agent_id, tool_name = ROUTE_OPERATOR_TOOL.get(route_name, ("", ""))
        if not agent_id:
            observations.append(_observation(route, "", "", "blocked", error="unsupported_retrieval_route"))
            continue
        if route_name == "milvus_semantic":
            capability = milvus_runtime_capability(context)
            if not capability["runtime_bound"]:
                gap = {
                    "source_family": "milvus_semantic",
                    "retrieval_route": "milvus_semantic",
                    "reason_code": "milvus_runtime_unavailable" if not capability["available"] else "milvus_runtime_not_bound",
                    "reason": (
                        "Milvus semantic route was requested, but the current runtime is not bound to a usable "
                        "cloud/local Milvus endpoint and collection."
                    ),
                    "status": capability["status"],
                    "location": capability["location"],
                    "missing": capability["missing_runtime_fields"],
                    "fallback_routes": capability["fallback_routes"],
                    "claim_boundary": "semantic_recall_unavailable_do_not_mock_or_use_as_exact_value_authority",
                }
                observations.append(
                    _observation(
                        route,
                        agent_id,
                        tool_name,
                        "skipped",
                        error=gap["reason_code"],
                        row_count=0,
                        source_gap_count=1,
                        boundary={
                            "status": "fail",
                            "policy": "milvus_runtime_capability_gate_v0_1",
                            "claim_boundary": gap["claim_boundary"],
                        },
                        runtime_summary={"milvus_runtime": _public_milvus_runtime_capability(capability)},
                    )
                )
                source_gaps.append(gap)
                continue
        permission = validate_operator_tool_call(agent_id=agent_id, tool_name=tool_name)
        if permission["status"] != "pass":
            observations.append(_observation(route, agent_id, tool_name, "blocked", error=permission["error"]))
            continue
        arguments = tool_arguments_from_route(route, user_query=str(context.get("user_query") or ""), state_context=context)
        if route_name == "ledger_first" and not str(arguments.get("ledger_store_path") or "").strip():
            if _bool_value(context.get("build_runtime_ledger") or context.get("ledger_first_sec_search_fallback")):
                route = _ledger_first_sec_search_fallback_route(route)
                route_name = str(route.get("retrieval_route") or "")
                agent_id, tool_name = ROUTE_OPERATOR_TOOL.get(route_name, ("", ""))
                permission = validate_operator_tool_call(agent_id=agent_id, tool_name=tool_name)
                if permission["status"] != "pass":
                    observations.append(_observation(route, agent_id, tool_name, "blocked", error=permission["error"]))
                    continue
                arguments = tool_arguments_from_route(route, user_query=str(context.get("user_query") or ""), state_context=context)
            else:
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
        result = _dry_run_result(tool_name, route) if dry_run else _execute_tool_with_resource_retry(tool_name, arguments, executor)
        boundary = validate_tool_observation_boundary(tool_name, result)
        rows = _attach_route_trace_to_rows(_rows_from_result(tool_name, result), route)
        runtime_summary = _tool_runtime_summary(tool_name, result)
        gaps = _attach_route_trace_to_rows(_source_gaps_from_result(result), route)
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
                "fallback_from_retrieval_route": route.get("fallback_from_retrieval_route") or "",
            },
        )
        observations.append(
            _observation(
                route,
                agent_id,
                tool_name,
                str(result.get("status") or "ok"),
                error=str(result.get("error") or result.get("failure_reason") or "")[:500],
                arguments=arguments,
                row_count=len(rows),
                source_gap_count=len(gaps),
                boundary=boundary,
                runtime_summary=runtime_summary,
            )
        )
        if tool_name in {"sec_search_filings", "sec_milvus_semantic_search"}:
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
        elif tool_name == "web_evidence_snapshot":
            context_rows.extend(rows)
        source_gaps.extend(gaps)
        artifact_refs.extend(refs)
        if (
            sec_group_member
            and sec_group_member.get("is_first")
            and tool_name == "sec_search_filings"
            and _sec_search_result_cacheable_for_group(result)
        ):
            sec_group_cache["result"] = result
            sec_group_cache["executed_route_id"] = original_route.get("route_id") or route.get("route_id") or ""

    context_rows = _attach_requirement_trace_to_rows(context_rows, retrieval_plan)
    ledger_rows = _attach_requirement_trace_to_rows(ledger_rows, retrieval_plan)
    market_rows = _attach_requirement_trace_to_rows(market_rows, retrieval_plan)
    industry_rows = _attach_requirement_trace_to_rows(industry_rows, retrieval_plan)
    source_gaps = _attach_requirement_trace_to_rows(source_gaps, retrieval_plan)

    ledger_rows = _merge_runtime_ledger_rows(
        [
            *ledger_rows,
            *_runtime_ledger_rows_from_sec_context(context_rows, state_context=context),
        ]
    )
    ledger_rows = _attach_requirement_trace_to_rows(ledger_rows, retrieval_plan)

    source_gaps.extend(
        _ledger_missing_despite_context_gaps(
            retrieval_plan,
            context_rows=context_rows,
            ledger_rows=ledger_rows,
            state_context=context,
        )
    )
    source_gaps = _attach_requirement_trace_to_rows(source_gaps, retrieval_plan)

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


def build_evidence_operator_fanout_plan(retrieval_plan: Mapping[str, Any]) -> dict[str, Any]:
    routes = [dict(route) for route in retrieval_plan.get("routes") or [] if isinstance(route, Mapping)]
    shards_by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    first_index: dict[tuple[str, str, str], int] = {}
    for index, route in enumerate(routes):
        route_name = str(route.get("retrieval_route") or "")
        source_family = _route_source_family_for_fanout(route)
        agent_id, tool_name = ROUTE_OPERATOR_TOOL.get(route_name, ("", ""))
        key = (source_family, agent_id, tool_name)
        shards_by_key.setdefault(key, []).append(route)
        first_index.setdefault(key, index)
    shards = []
    for shard_index, key in enumerate(sorted(shards_by_key, key=lambda item: first_index[item]), start=1):
        source_family, agent_id, tool_name = key
        shard_routes = shards_by_key[key]
        shards.append(
            {
                "shard_id": f"evidence_shard_{shard_index:02d}_{_slug(source_family or 'unknown')}",
                "shard_index": shard_index,
                "source_family": source_family,
                "operator_owner": agent_id,
                "tool_name": tool_name,
                "route_ids": [_route_identity(route) for route in shard_routes],
                "route_count": len(shard_routes),
                "merge_key": [shard_index, source_family, agent_id, tool_name],
                "routes": shard_routes,
            }
        )
    return {
        "schema_version": EVIDENCE_OPERATOR_FANOUT_PLAN_SCHEMA_VERSION,
        "policy": "source_family_operator_shards_deterministic_merge_v0_1",
        "shard_count": len(shards),
        "route_count": len(routes),
        "shards": shards,
    }


def execute_evidence_operator_fanout_plan(
    retrieval_plan: Mapping[str, Any],
    *,
    turn_id: str,
    ledger: ToolCallLedger | None = None,
    state_context: Mapping[str, Any] | None = None,
    tool_executor: ToolExecutor | None = None,
    dry_run: bool = False,
    max_workers: int = 4,
) -> dict[str, Any]:
    fanout_plan = build_evidence_operator_fanout_plan(retrieval_plan)
    shards = [dict(shard) for shard in fanout_plan.get("shards") or [] if isinstance(shard, Mapping)]
    if not shards:
        base = execute_evidence_operator_plan(
            retrieval_plan,
            turn_id=turn_id,
            ledger=ledger,
            state_context=state_context,
            tool_executor=tool_executor,
            dry_run=dry_run,
        )
        return {
            **base,
            "evidence_operator_fanout_plan": fanout_plan,
            "fanout_barrier": _fanout_barrier_summary(fanout_plan, [], execution_mode="fanout_empty"),
        }

    worker_count = max(1, min(max_workers, len(shards)))
    if worker_count == 1:
        shard_results = [_execute_evidence_fanout_shard(shard, turn_id, state_context, tool_executor, dry_run) for shard in shards]
        execution_mode = "fanout_sequential"
    else:
        shard_results = []
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(_execute_evidence_fanout_shard, shard, turn_id, state_context, tool_executor, dry_run): shard
                for shard in shards
            }
            for future in as_completed(futures):
                try:
                    shard_results.append(future.result())
                except Exception as exc:  # defensive: _execute_evidence_fanout_shard already catches route errors
                    shard = futures[future]
                    shard_results.append(_failed_evidence_fanout_shard(shard, exc))
        execution_mode = "fanout_parallel"
    shard_results = sorted(shard_results, key=lambda item: int(item.get("shard_index") or 0))
    merged = _merge_evidence_fanout_results(shard_results, ledger=ledger)
    return {
        **merged,
        "schema_version": RUNTIME_SCHEMA_VERSION,
        "evidence_operator_fanout_plan": _sanitize_payload(fanout_plan),
        "fanout_barrier": _fanout_barrier_summary(fanout_plan, shard_results, execution_mode=execution_mode),
    }


def _execute_evidence_fanout_shard(
    shard: Mapping[str, Any],
    turn_id: str,
    state_context: Mapping[str, Any] | None,
    tool_executor: ToolExecutor | None,
    dry_run: bool,
) -> dict[str, Any]:
    shard_routes = [dict(route) for route in shard.get("routes") or [] if isinstance(route, Mapping)]
    shard_plan = {
        "schema_version": "sec_agent_retrieval_plan_v0.1",
        "source": "evidence_operator_fanout_shard",
        "tasks": [],
        "routes": shard_routes,
        "summary": _retrieval_plan_summary(shard_routes, task_count=0),
    }
    try:
        result = execute_evidence_operator_plan(
            shard_plan,
            turn_id=f"{turn_id}::{shard.get('shard_id') or 'shard'}",
            ledger=ToolCallLedger(),
            state_context=state_context,
            tool_executor=tool_executor,
            dry_run=dry_run,
        )
        status = "pass"
        error = ""
    except Exception as exc:
        result = _failed_evidence_fanout_shard(shard, exc)
        status = "fail"
        error = str(exc)[:500]
    return {
        **result,
        "shard_id": str(shard.get("shard_id") or ""),
        "shard_index": int(shard.get("shard_index") or 0),
        "source_family": str(shard.get("source_family") or ""),
        "operator_owner": str(shard.get("operator_owner") or ""),
        "tool_name": str(shard.get("tool_name") or ""),
        "route_ids": _string_list(shard.get("route_ids")),
        "status": status,
        "error": error,
    }


def _failed_evidence_fanout_shard(shard: Mapping[str, Any], exc: Exception) -> dict[str, Any]:
    error = str(exc)[:500]
    routes = [dict(route) for route in shard.get("routes") or [] if isinstance(route, Mapping)]
    source_family = str(shard.get("source_family") or "unknown")
    operator_owner = str(shard.get("operator_owner") or "")
    tool_name = str(shard.get("tool_name") or "")
    observations = [
        _observation(
            route,
            operator_owner,
            tool_name,
            "failed",
            error=error,
            source_gap_count=1,
            boundary={
                "status": "fail",
                "policy": "fanout_shard_failure_isolated",
                "source_family": source_family,
            },
        )
        for route in routes
    ]
    return {
        "schema_version": RUNTIME_SCHEMA_VERSION,
        "shard_id": str(shard.get("shard_id") or ""),
        "shard_index": int(shard.get("shard_index") or 0),
        "source_family": source_family,
        "operator_owner": operator_owner,
        "tool_name": tool_name,
        "route_ids": _string_list(shard.get("route_ids")),
        "status": "fail",
        "error": error,
        "tool_observations": observations,
        "tool_call_ledger": ToolCallLedger().to_dict(),
        "context_rows": [],
        "runtime_ledger_rows": [],
        "market_snapshot_rows": [],
        "industry_snapshot_rows": [],
        "source_gaps": [
            {
                "source_family": source_family,
                "gap_type": "operator_shard_failed",
                "reason": error,
                "route_ids": _string_list(shard.get("route_ids")),
                "claim_boundary": "failed_operator_rows_not_available_do_not_fallback",
            }
        ],
        "artifact_refs": [],
        "loop_break_reason": "",
        "bounded_answer_allowed": True,
    }


def _merge_evidence_fanout_results(shard_results: list[Mapping[str, Any]], *, ledger: ToolCallLedger | None) -> dict[str, Any]:
    base_ledger = ToolCallLedger.from_dict((ledger or ToolCallLedger()).to_dict())
    ledger_payload = base_ledger.to_dict()
    merged_records: list[dict[str, Any]] = [
        dict(item) for item in ledger_payload.get("records") or [] if isinstance(item, Mapping)
    ]
    for shard in shard_results:
        shard_ledger = shard.get("tool_call_ledger") if isinstance(shard.get("tool_call_ledger"), Mapping) else {}
        merged_records.extend(dict(item) for item in shard_ledger.get("records") or [] if isinstance(item, Mapping))
    ledger_payload["records"] = merged_records
    if any(bool(shard.get("bounded_answer_allowed")) for shard in shard_results):
        ledger_payload["bounded_answer_allowed"] = True
    loop_break_reason = next((str(shard.get("loop_break_reason") or "") for shard in shard_results if str(shard.get("loop_break_reason") or "")), "")
    return {
        "tool_observations": [dict(row) for shard in shard_results for row in shard.get("tool_observations") or [] if isinstance(row, Mapping)],
        "tool_call_ledger": ledger_payload,
        "context_rows": [dict(row) for shard in shard_results for row in shard.get("context_rows") or [] if isinstance(row, Mapping)],
        "runtime_ledger_rows": [dict(row) for shard in shard_results for row in shard.get("runtime_ledger_rows") or [] if isinstance(row, Mapping)],
        "market_snapshot_rows": [dict(row) for shard in shard_results for row in shard.get("market_snapshot_rows") or [] if isinstance(row, Mapping)],
        "industry_snapshot_rows": [dict(row) for shard in shard_results for row in shard.get("industry_snapshot_rows") or [] if isinstance(row, Mapping)],
        "source_gaps": [dict(row) for shard in shard_results for row in shard.get("source_gaps") or [] if isinstance(row, Mapping)],
        "artifact_refs": [dict(row) for shard in shard_results for row in shard.get("artifact_refs") or [] if isinstance(row, Mapping)],
        "loop_break_reason": loop_break_reason,
        "bounded_answer_allowed": bool(ledger_payload.get("bounded_answer_allowed")),
    }


def _fanout_barrier_summary(plan: Mapping[str, Any], shard_results: list[Mapping[str, Any]], *, execution_mode: str) -> dict[str, Any]:
    completed = [shard for shard in shard_results if str(shard.get("status") or "") == "pass"]
    failed = [shard for shard in shard_results if str(shard.get("status") or "") != "pass"]
    return _sanitize_payload(
        {
            "schema_version": FANOUT_BARRIER_SCHEMA_VERSION,
            "barrier_id": "evidence_operator_fanout_barrier",
            "execution_mode": execution_mode,
            "deterministic_merge_policy": "sort_by_shard_index_then_append_source_family_rows",
            "input_shard_count": int(plan.get("shard_count") or 0),
            "completed_shard_count": len(completed),
            "failed_shard_count": len(failed),
            "failed_shards": [
                {
                    "shard_id": str(shard.get("shard_id") or ""),
                    "source_family": str(shard.get("source_family") or ""),
                    "operator_owner": str(shard.get("operator_owner") or ""),
                    "tool_name": str(shard.get("tool_name") or ""),
                    "error": str(shard.get("error") or "")[:500],
                }
                for shard in failed
            ],
            "output_schema": {
                "context_rows": "append_only",
                "runtime_ledger_rows": "append_only",
                "market_snapshot_rows": "append_only",
                "industry_snapshot_rows": "append_only",
                "source_gaps": "append_only",
                "tool_observations": "append_only",
            },
        }
    )


def _route_source_family_for_fanout(route: Mapping[str, Any]) -> str:
    route_name = str(route.get("retrieval_route") or "")
    family = ROUTE_SOURCE_FAMILY.get(route_name, "")
    if family:
        return family
    families = _string_list(route.get("source_families") or route.get("source_tiers"))
    return families[0] if families else "unknown"


def _ledger_missing_despite_context_gaps(
    retrieval_plan: Mapping[str, Any],
    *,
    context_rows: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
    state_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    routes = [route for route in retrieval_plan.get("routes") or [] if isinstance(route, Mapping)]
    ledger_expected = any(str(route.get("retrieval_route") or "") == "ledger_first" for route in routes)
    if not ledger_expected:
        return []
    focus_tickers = set(_unique_upper(state_context.get("focus_tickers") or state_context.get("tickers")))
    ledger_keys = {
        _row_ticker_year_form(row)
        for row in ledger_rows
        if _row_ticker(row) and _row_source_family(row) in {"", "primary_sec_filing", "company_authored_unaudited_sec_filing"}
    }
    context_keys: list[tuple[str, str, str]] = []
    for row in context_rows:
        if _row_source_family(row) not in {"", "primary_sec_filing"}:
            continue
        key = _row_ticker_year_form(row)
        ticker = key[0]
        if not ticker or (focus_tickers and ticker not in focus_tickers):
            continue
        if not key[1] and not key[2]:
            continue
        context_keys.append(key)
    gaps: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for key in context_keys:
        if key in seen or key in ledger_keys:
            continue
        seen.add(key)
        ticker, fiscal_year, form_type = key
        gaps.append(
            {
                "source_family": "primary_sec_filing",
                "reason_code": "ledger_missing_despite_context",
                "reason": "Primary filing context rows are available, but no exact-value runtime ledger rows were returned for the same ticker/year/form scope.",
                "source_available": True,
                "exact_value_available": False,
                "ticker": ticker,
                "fiscal_year": fiscal_year,
                "form_type": form_type,
                "quality_gap_type": "context_available_exact_value_missing",
            }
        )
    return gaps[:24]


def _row_ticker_year_form(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        _row_ticker(row),
        str(row.get("fiscal_year") or row.get("source_fiscal_year") or row.get("year") or "").strip(),
        str(row.get("form_type") or row.get("source_type") or "").strip(),
    )


def _ledger_first_sec_search_fallback_route(route: Mapping[str, Any]) -> dict[str, Any]:
    """Use SEC text retrieval to build runtime ledger rows when no ledger store is configured."""
    candidate_budget = max(_bounded_positive_int(route.get("candidate_budget"), default=0), 120)
    rerank_budget = max(_bounded_positive_int(route.get("rerank_budget"), default=0), min(64, candidate_budget))
    route_id = str(route.get("route_id") or route.get("task_id") or "ledger_first")
    ledger_route = {
        **dict(route),
        "retrieval_route": "ledger_first",
        "candidate_budget": candidate_budget,
        "rerank_budget": min(64, candidate_budget),
        "section_hints": _dedupe([*_string_list(route.get("section_hints")), "financial_statements", "cash_flow_tables"]),
    }
    task_id = str(route.get("task_id") or "runtime_ledger_search")
    return {
        **dict(route),
        "route_id": f"{route_id}::runtime_ledger_search_fallback",
        "retrieval_route": "filing_text",
        "candidate_budget": candidate_budget,
        "rerank_budget": rerank_budget,
        "section_hints": _dedupe([*_string_list(route.get("section_hints")), "financial_statements", "management_discussion"]),
        "runtime_retrieval_plan": {
            "schema_version": "sec_agent_retrieval_plan_v0.1",
            "source": "ledger_first_sec_search_fallback",
            "tasks": [
                {
                    "task_id": task_id,
                    "question_zh": str(route.get("question_zh") or route.get("query") or ""),
                    "priority": "primary",
                    "tickers": _string_list(route.get("tickers")),
                    "years": _int_list(route.get("years")),
                    "filing_types": _string_list(route.get("filing_types")),
                    "source_tiers": _string_list(route.get("source_tiers")),
                    "metric_families": _string_list(route.get("metric_families")),
                    "retrieval_routes": ["ledger_first"],
                    "evidence_requirement_id": str(route.get("evidence_requirement_id") or ""),
                }
            ],
            "routes": [ledger_route],
            "summary": {"route_count": 1, "route_counts": {"ledger_first": 1}},
        },
        "fallback_from_retrieval_route": "ledger_first",
        "fallback_reason": "ledger_store_path_unavailable_build_runtime_ledger_from_sec_search",
    }


def _sec_search_execution_group(
    routes: list[dict[str, Any]],
    *,
    context: Mapping[str, Any],
    dry_run: bool,
) -> dict[str, Any]:
    if dry_run:
        return {}
    group_routes = [route for route in routes if _route_can_join_sec_search_group(route, context=context)]
    if len(group_routes) <= 1:
        return {}
    first_id = _route_identity(group_routes[0])
    return {
        "schema_version": "sec_agent_grouped_sec_search_execution_v0.1",
        "policy": "single_sec_search_filings_call_per_turn_for_groupable_sec_routes",
        "first_route_id": first_id,
        "routes": group_routes,
        "route_ids": {_route_identity(route) for route in group_routes},
    }


def _route_can_join_sec_search_group(route: Mapping[str, Any], *, context: Mapping[str, Any]) -> bool:
    route_name = str(route.get("retrieval_route") or "")
    if route_name in SEC_SEARCH_TEXT_ROUTES:
        return True
    if route_name != "ledger_first":
        return False
    if str(context.get("ledger_store_path") or "").strip():
        return False
    return _bool_value(context.get("build_runtime_ledger") or context.get("ledger_first_sec_search_fallback"))


def _sec_group_member(group: Mapping[str, Any], route: Mapping[str, Any]) -> dict[str, Any]:
    if not group:
        return {}
    route_id = _route_identity(route)
    if route_id not in set(group.get("route_ids") or set()):
        return {}
    return {"route_id": route_id, "is_first": route_id == str(group.get("first_route_id") or "")}


def _sec_search_group_execution_route(
    route: Mapping[str, Any],
    group_routes: list[dict[str, Any]],
    *,
    retrieval_plan: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    execution_route = _sec_search_member_execution_route(route, context=context)
    grouped_plan = _grouped_sec_search_retrieval_plan(retrieval_plan, group_routes)
    return {
        **execution_route,
        "route_id": str(execution_route.get("route_id") or route.get("route_id") or "sec_search_group") + "::grouped_sec_search",
        "tickers": _dedupe([ticker for item in group_routes for ticker in _string_list(item.get("tickers"))]),
        "years": sorted(set(year for item in group_routes for year in _int_list(item.get("years")))),
        "filing_types": _dedupe([form for item in group_routes for form in _string_list(item.get("filing_types"))]),
        "source_tiers": _dedupe([tier for item in group_routes for tier in _string_list(item.get("source_tiers"))]),
        "metric_families": _dedupe([family for item in group_routes for family in _string_list(item.get("metric_families"))]),
        "period_roles": _dedupe([role for item in group_routes for role in _string_list(item.get("period_roles"))]),
        "section_hints": _dedupe([hint for item in group_routes for hint in _string_list(item.get("section_hints"))]),
        "candidate_budget": max([_bounded_positive_int(item.get("candidate_budget"), default=0) for item in group_routes] or [0]),
        "rerank_budget": max([_bounded_positive_int(item.get("rerank_budget"), default=0) for item in group_routes] or [0]),
        "runtime_retrieval_plan": grouped_plan,
        "grouped_sec_search": {
            "policy": "single_call_grouped_sec_search_v0_1",
            "grouped_route_ids": [_route_identity(item) for item in group_routes],
            "grouped_route_count": len(group_routes),
        },
    }


def _sec_search_member_execution_route(route: Mapping[str, Any], *, context: Mapping[str, Any]) -> dict[str, Any]:
    if str(route.get("retrieval_route") or "") == "ledger_first" and _route_can_join_sec_search_group(route, context=context):
        return _ledger_first_sec_search_fallback_route(route)
    return dict(route)


def _grouped_sec_search_retrieval_plan(
    retrieval_plan: Mapping[str, Any],
    group_routes: list[dict[str, Any]],
) -> dict[str, Any]:
    group_route_ids = {_route_identity(route) for route in group_routes}
    tasks = []
    task_ids = {str(route.get("task_id") or "") for route in group_routes if str(route.get("task_id") or "")}
    for task in retrieval_plan.get("tasks") or []:
        if isinstance(task, Mapping) and str(task.get("task_id") or "") in task_ids:
            tasks.append(dict(task))
    routes = [dict(route) for route in group_routes]
    return {
        **dict(retrieval_plan or {}),
        "source": str(retrieval_plan.get("source") or "query_contract_derived_retrieval_plan") + "+grouped_sec_search_execution",
        "tasks": tasks or [dict(task) for task in retrieval_plan.get("tasks") or [] if isinstance(task, Mapping)],
        "routes": routes,
        "summary": _retrieval_plan_summary(routes, task_count=len(tasks or retrieval_plan.get("tasks") or [])),
        "grouped_sec_search_execution": {
            "policy": "single_sec_search_filings_call_per_turn_for_groupable_sec_routes",
            "grouped_route_ids": sorted(group_route_ids),
            "grouped_route_count": len(routes),
        },
    }


def _sec_search_agent_tool_for_route(route: Mapping[str, Any], *, context: Mapping[str, Any]) -> tuple[str, str]:
    route_name = str(route.get("retrieval_route") or "")
    if route_name == "ledger_first" and _route_can_join_sec_search_group(route, context=context):
        return ("sec_operator", "sec_search_filings")
    return ROUTE_OPERATOR_TOOL.get(route_name, ("", ""))


def _sec_search_result_rows_for_route(result: Mapping[str, Any], route: Mapping[str, Any]) -> list[dict[str, Any]]:
    route_id = _route_identity(route)
    route_name = str(route.get("retrieval_route") or "")
    rows = [row for row in result.get("context_rows") or [] if isinstance(row, Mapping) and _result_row_matches_route(row, route_id)]
    if route_name == "ledger_first":
        rows.extend(dict(item) for item in result.get("runtime_ledger_rows") or [] if isinstance(item, Mapping))
    return [dict(row) for row in rows]


def _attach_route_trace_to_rows(rows: Iterable[Mapping[str, Any]], route: Mapping[str, Any]) -> list[dict[str, Any]]:
    trace = _route_trace_payload(route)
    if not trace:
        return [dict(row) for row in rows if isinstance(row, Mapping)]
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        result.append(_merge_row_trace(row, trace))
    return result


def _attach_requirement_trace_to_rows(rows: Iterable[Mapping[str, Any]], retrieval_plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    trace_index = _route_trace_index(retrieval_plan)
    if not trace_index:
        return [dict(row) for row in rows if isinstance(row, Mapping)]
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        merged = dict(row)
        for route_id in _row_route_ids(row):
            trace = trace_index.get(route_id)
            if trace:
                merged = _merge_row_trace(merged, trace)
        result.append(merged)
    return result


def _route_trace_index(retrieval_plan: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for route in retrieval_plan.get("routes") or []:
        if not isinstance(route, Mapping):
            continue
        trace = _route_trace_payload(route)
        if not trace:
            continue
        for route_id in _dedupe([_route_identity(route), str(route.get("route_id") or "")]):
            if route_id:
                index[route_id] = trace
    return index


def _route_trace_payload(route: Mapping[str, Any]) -> dict[str, Any]:
    route_id = _route_identity(route)
    retrieval_route = str(route.get("retrieval_route") or "").strip()
    requirement_ids = _string_list(route.get("evidence_requirement_id") or route.get("evidence_requirement_ids"))
    selection_task_ids = _string_list(route.get("selection_task_id") or route.get("selection_task_ids") or route.get("task_id"))
    payload: dict[str, Any] = {}
    if route_id:
        payload["selection_route_ids"] = [route_id]
        payload["route_id"] = route_id
    if retrieval_route:
        payload["retrieval_routes"] = [retrieval_route]
        payload["retrieval_route"] = retrieval_route
    if requirement_ids:
        payload["evidence_requirement_ids"] = requirement_ids
        if len(requirement_ids) == 1:
            payload["evidence_requirement_id"] = requirement_ids[0]
    if selection_task_ids:
        payload["selection_task_ids"] = selection_task_ids
        if len(selection_task_ids) == 1:
            payload["selection_task_id"] = selection_task_ids[0]
    return payload


def _row_route_ids(row: Mapping[str, Any]) -> list[str]:
    route_ids: list[str] = []
    for key in ("route_id", "selection_route_id"):
        value = str(row.get(key) or "").strip()
        if value:
            route_ids.append(value)
    route_ids.extend(_string_list(row.get("route_ids")))
    route_ids.extend(_string_list(row.get("selection_route_ids")))
    for ref in row.get("selection_routes") or []:
        if isinstance(ref, Mapping):
            value = str(ref.get("route_id") or "").strip()
            if value:
                route_ids.append(value)
    return _dedupe(route_ids)


def _merge_row_trace(row: Mapping[str, Any], trace: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(row)
    for key in ("evidence_requirement_ids", "selection_task_ids", "selection_route_ids", "retrieval_routes"):
        values = _dedupe([*_string_list(merged.get(key)), *_string_list(trace.get(key))])
        if values:
            merged[key] = values[:12]
    for key in ("evidence_requirement_id", "selection_task_id", "selection_route_id", "route_id", "retrieval_route"):
        value = str(merged.get(key) or trace.get(key) or "").strip()
        if value:
            merged[key] = value
    return merged


def _result_row_matches_route(row: Mapping[str, Any], route_id: str) -> bool:
    if not route_id:
        return False
    route_ids = set(_string_list(row.get("selection_route_ids")))
    route_ids.update(_string_list(row.get("route_ids")))
    for key in ("selection_route_id", "route_id"):
        value = str(row.get(key) or "")
        if value:
            route_ids.add(value)
    for ref in row.get("selection_routes") or []:
        if isinstance(ref, Mapping):
            value = str(ref.get("route_id") or "")
            if value:
                route_ids.add(value)
    return route_id in route_ids


def _route_identity(route: Mapping[str, Any]) -> str:
    return str(route.get("route_id") or f"{route.get('task_id') or 'task'}::{route.get('retrieval_route') or 'route'}")


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
        "route_selection_reason": str(route.get("route_selection_reason") or ""),
        "route_cost_tier": str(route.get("route_cost_tier") or ""),
        "route_selection_policy": str(route.get("route_selection_policy") or ""),
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
        if isinstance(route.get("runtime_retrieval_plan"), Mapping):
            args["retrieval_plan"] = dict(route.get("runtime_retrieval_plan") or {})
        return args
    if route_name == "milvus_semantic":
        milvus_capability = milvus_runtime_capability(context)
        args["source_tiers"] = _sec_search_source_tiers_for_route("filing_text", _string_list(args.get("source_tiers")))
        vector_kinds = _milvus_vector_kinds_for_route(route, context)
        args.update(
            {
                "query": str(route.get("query") or user_query or route.get("task_id") or ""),
                "retrieval_route": route_name,
                "candidate_budget": int(route.get("candidate_budget") or 0),
                "milvus_top_k": int(route.get("milvus_top_k") or context.get("milvus_top_k") or route.get("limit") or 40),
                "vector_kinds": vector_kinds,
                "typed_filter_required": True,
                "milvus_db_path": str(context.get("milvus_db_path") or context.get("milvus_uri") or milvus_capability.get("uri") or ""),
                "milvus_collection_name": str(context.get("milvus_collection_name") or milvus_capability.get("collection") or ""),
                "embedding_model": str(context.get("embedding_model") or context.get("milvus_embedding_model") or ""),
                "milvus_runtime": milvus_capability,
                "milvus_search_policy": {
                    "schema_version": "sec_agent_milvus_semantic_route_policy_v0.1",
                    "route_role": "semantic_recall_supplement",
                    "typed_filter_required": True,
                    "vector_kinds": vector_kinds,
                    "not_exact_value_authority": True,
                    "runtime_status": milvus_capability["status"],
                    "runtime_location": milvus_capability["location"],
                    "runtime_bound": milvus_capability["runtime_bound"],
                },
            }
        )
        return args
    if route_name == "market_snapshot":
        market = context.get("market_snapshot") if isinstance(context.get("market_snapshot"), Mapping) else {}
        args["tickers"] = _market_snapshot_tickers_for_route(args, context)
        args.update(
            {
                "fields": list(coverage.get("market_fields") or route.get("market_fields") or []),
                "analysis_tools": list(coverage.get("market_analysis_tools") or route.get("analysis_tools") or []),
                "snapshot_id": str(context.get("market_snapshot_id") or market.get("snapshot_id") or ""),
                "as_of_date": str(context.get("market_as_of_date") or market.get("as_of_date") or ""),
                "market_evidence_path": str(context.get("market_evidence_path") or ""),
                "market_catalog_path": str(context.get("market_catalog_path") or ""),
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
    if route_name == "live_public_web_context":
        args.update(
            {
                "query": str(route.get("query") or user_query or route.get("task_id") or ""),
                "retrieval_route": route_name,
                "url": str(route.get("url") or coverage.get("url") or ""),
                "domain": str(route.get("domain") or coverage.get("domain") or ""),
                "source_class": str(route.get("source_class") or coverage.get("source_class") or ""),
                "claim_types": _string_list(route.get("claim_types") or coverage.get("claim_types") or route.get("claim_type") or coverage.get("claim_type")),
                "web_scope_policy_ids": _string_list(
                    route.get("web_scope_policy_ids")
                    or coverage.get("web_scope_policy_ids")
                    or context.get("web_scope_policy_ids")
                    or (context.get("agent_activation_plan") or {}).get("web_scope_policy_ids")
                ),
                "snapshot_id": str(route.get("snapshot_id") or coverage.get("snapshot_id") or ""),
                "snapshot_url": str(route.get("snapshot_url") or route.get("url") or coverage.get("snapshot_url") or ""),
                "source_title": str(route.get("source_title") or coverage.get("source_title") or ""),
                "company_domain_verified": _bool_value(route.get("company_domain_verified") or coverage.get("company_domain_verified")),
                "company_domains": _string_list(route.get("company_domains") or coverage.get("company_domains")),
                "web_scope_allowed_domains": _string_list(route.get("web_scope_allowed_domains") or coverage.get("web_scope_allowed_domains")),
                "authority_boundary": "live_web_context_only_no_snippet_claims",
            }
        )
        return args
    return args


def _market_snapshot_tickers_for_route(args: Mapping[str, Any], context: Mapping[str, Any]) -> list[str]:
    base = _string_list(args.get("tickers"))
    mode = str(context.get("execution_mode") or "").strip()
    source_tiers = set(_string_list(context.get("source_tiers") or context.get("source_families")))
    if mode == "deep_research" and "relationship_graph" in source_tiers:
        expanded = _string_list(context.get("search_scope_tickers") or context.get("universe_tickers"))
        if 0 < len(expanded) <= 12:
            return _dedupe([*base, *expanded])
    return base


def milvus_runtime_capability(context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    runtime_context = dict(context or {})
    project_inventory = runtime_context.get("project_inventory") if isinstance(runtime_context.get("project_inventory"), Mapping) else {}
    inventory_runtime = project_inventory.get("milvus_runtime") if isinstance(project_inventory.get("milvus_runtime"), Mapping) else {}
    explicit_runtime = runtime_context.get("milvus_runtime") if isinstance(runtime_context.get("milvus_runtime"), Mapping) else {}
    runtime = {**dict(inventory_runtime), **dict(explicit_runtime)}
    uri = str(
        runtime_context.get("milvus_uri")
        or runtime_context.get("milvus_db_path")
        or runtime.get("uri")
        or runtime.get("endpoint")
        or runtime.get("db_path")
        or ""
    ).strip()
    collection = str(runtime_context.get("milvus_collection_name") or runtime.get("collection") or runtime.get("collection_name") or "").strip()
    status = str(runtime.get("status") or "").strip().lower()
    location = str(runtime_context.get("milvus_runtime_location") or runtime.get("location") or "").strip().lower()
    if not status:
        if uri and collection:
            location = location or ("cloud" if uri.startswith(("http://", "https://", "tcp://")) else "local")
            status = f"{location}_available"
        else:
            status = "unavailable"
    if status in {"available", "enabled"}:
        status = f"{location or 'cloud'}_available"
    if status not in {"cloud_available", "local_available", "unavailable"}:
        status = "unavailable"
    if status == "cloud_available":
        location = "cloud"
    elif status == "local_available":
        location = "local"
    else:
        location = "none"
    available = bool(runtime.get("available")) if "available" in runtime else status in {"cloud_available", "local_available"}
    missing: list[str] = []
    if not uri:
        missing.append("milvus_uri_or_db_path")
    if not collection:
        missing.append("milvus_collection_name")
    runtime_bound = available and not missing
    vector_kinds = _string_list(runtime_context.get("milvus_vector_kinds") or runtime.get("vector_kinds"))
    if not vector_kinds:
        vector_kinds = list(MILVUS_DEFAULT_VECTOR_KINDS)
    return {
        "schema_version": "sec_agent_milvus_runtime_capability_v0.1",
        "status": status,
        "available": available,
        "runtime_bound": runtime_bound,
        "location": location,
        "collection": collection,
        "uri": uri,
        "vector_kinds": vector_kinds,
        "vector_count": runtime.get("vector_count") or runtime.get("row_count"),
        "as_of_date": str(runtime.get("as_of_date") or runtime.get("materialized_at") or "").strip(),
        "schema_digest": str(runtime.get("schema_digest") or runtime.get("digest") or "").strip(),
        "fallback_routes": _string_list(runtime.get("fallback_routes")) or ["bm25", "object_bm25", "exact_value_ledger"],
        "claim_boundary": str(runtime.get("claim_boundary") or "semantic_recall_supplement_not_exact_value_authority"),
        "missing_runtime_fields": missing,
    }


def _public_milvus_runtime_capability(capability: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": str(capability.get("schema_version") or "sec_agent_milvus_runtime_capability_v0.1"),
        "status": str(capability.get("status") or ""),
        "available": bool(capability.get("available")),
        "runtime_bound": bool(capability.get("runtime_bound")),
        "location": str(capability.get("location") or ""),
        "collection": str(capability.get("collection") or ""),
        "vector_kinds": _string_list(capability.get("vector_kinds")),
        "vector_count": capability.get("vector_count"),
        "as_of_date": str(capability.get("as_of_date") or ""),
        "schema_digest": str(capability.get("schema_digest") or ""),
        "fallback_routes": _string_list(capability.get("fallback_routes")),
        "claim_boundary": str(capability.get("claim_boundary") or ""),
        "missing_runtime_fields": _string_list(capability.get("missing_runtime_fields")),
    }


def _milvus_vector_kinds_for_route(route: Mapping[str, Any], context: Mapping[str, Any]) -> list[str]:
    coverage = route.get("coverage_requirements") if isinstance(route.get("coverage_requirements"), Mapping) else {}
    requested = _string_list(route.get("vector_kinds") or coverage.get("vector_kinds") or context.get("milvus_vector_kinds"))
    valid = [kind for kind in requested if kind in MILVUS_SEMANTIC_VECTOR_KINDS]
    if valid:
        return _dedupe(valid)
    source_families = set(_string_list(route.get("source_families") or coverage.get("source_families") or context.get("source_families") or context.get("source_tiers")))
    text = " ".join(
        [
            str(route.get("query") or ""),
            str(route.get("task_id") or ""),
            " ".join(str(item) for item in route.get("metric_families") or coverage.get("metric_families") or []),
        ]
    ).lower()
    defaults = list(MILVUS_DEFAULT_VECTOR_KINDS)
    if "relationship_graph" in source_families or _contains_any(text, ("relationship", "supplier", "customer", "supply chain", "上下游", "供应链")):
        defaults.append("relationship_context")
    if _contains_any(text, ("metric", "table", "margin", "revenue", "capex", "cash flow", "数值", "表格")):
        defaults.extend(["metric_row", "table_row"])
    return _dedupe([kind for kind in defaults if kind in MILVUS_SEMANTIC_VECTOR_KINDS])


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
            "candidate_budget": 180,
            "rerank_budget": 56,
            "evidence_top_k": 5,
            "object_top_k": 4,
            "reranker_candidate_limit": 180,
            "reranker_top_k": 56,
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


def _execute_tool_with_resource_retry(tool_name: str, arguments: Mapping[str, Any], executor: ToolExecutor) -> dict[str, Any]:
    args = dict(arguments or {})
    if tool_name != "sec_search_filings":
        result = executor(tool_name, args)
        if isinstance(result, Mapping):
            return dict(result)
        return {"status": "error", "error": f"invalid_tool_result:{type(result).__name__}", "tool_name": tool_name}

    result = _call_tool_executor(tool_name, args, executor)
    if not _tool_result_is_sec_search_bge_resource_failure(result, args):
        return result

    attempts = [_resource_retry_attempt("initial", args, result)]
    final_result = result
    retry_policy = "sec_search_cuda_oom_retry_v0_1"

    if _sec_search_arg_device_is_cuda(args) and int(args.get("reranker_batch_size") or 0) > 1:
        cuda_retry_args = dict(args)
        cuda_retry_args["reranker_batch_size"] = 1
        final_result = _call_tool_executor(tool_name, cuda_retry_args, executor)
        attempts.append(_resource_retry_attempt("cuda_batch_size_1", cuda_retry_args, final_result))

    if _tool_result_is_sec_search_bge_resource_failure(final_result, args):
        cpu_retry_args = dict(args)
        cpu_retry_args["bge_device"] = "cpu"
        cpu_retry_args["bge_first"] = True
        cpu_retry_args["reranker_batch_size"] = min(max(1, int(args.get("reranker_batch_size") or 1)), 4)
        final_result = _call_tool_executor(tool_name, cpu_retry_args, executor)
        attempts.append(_resource_retry_attempt("cpu_spillover_after_cuda_oom", cpu_retry_args, final_result))

    return _attach_resource_retry_summary(
        final_result,
        retry_policy=retry_policy,
        attempts=attempts,
        original_error=_tool_result_error_text(result),
    )


def _call_tool_executor(tool_name: str, arguments: Mapping[str, Any], executor: ToolExecutor) -> dict[str, Any]:
    try:
        result = executor(tool_name, dict(arguments or {}))
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"{type(exc).__name__}:{exc}", "tool_name": tool_name}
    if isinstance(result, Mapping):
        return dict(result)
    return {"status": "error", "error": f"invalid_tool_result:{type(result).__name__}", "tool_name": tool_name}


def _attach_resource_retry_summary(
    result: Mapping[str, Any],
    *,
    retry_policy: str,
    attempts: list[dict[str, Any]],
    original_error: str,
) -> dict[str, Any]:
    clean = dict(result or {})
    clean["resource_retry"] = {
        "schema_version": "sec_agent_tool_resource_retry_v0.1",
        "policy": retry_policy,
        "retried": len(attempts) > 1,
        "attempt_count": len(attempts),
        "attempts": attempts,
        "original_error": original_error[:500],
        "final_status": str(clean.get("status") or ""),
        "final_error": _tool_result_error_text(clean)[:500],
        "spillover": any(str(item.get("stage") or "") == "cpu_spillover_after_cuda_oom" for item in attempts),
    }
    context_runtime = clean.get("context_runtime") if isinstance(clean.get("context_runtime"), Mapping) else {}
    clean["context_runtime"] = {
        **dict(context_runtime),
        "resource_retry_policy": retry_policy,
        "resource_retry_attempt_count": len(attempts),
        "resource_retry_spillover": clean["resource_retry"]["spillover"],
    }
    return clean


def _resource_retry_attempt(stage: str, arguments: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": str(result.get("status") or ""),
        "error": _tool_result_error_text(result)[:240],
        "bge_device": str(arguments.get("bge_device") or ""),
        "reranker_batch_size": int(arguments.get("reranker_batch_size") or 0),
        "row_count": len(result.get("context_rows") or []),
    }


def _tool_result_error_text(result: Mapping[str, Any]) -> str:
    return str(result.get("error") or result.get("failure_reason") or "")


def _tool_result_is_cuda_oom(result: Mapping[str, Any]) -> bool:
    text = _tool_result_error_text(result).lower()
    return "cuda out of memory" in text or "outofmemoryerror" in text


def _tool_result_is_sec_search_bge_resource_failure(result: Mapping[str, Any], arguments: Mapping[str, Any]) -> bool:
    if _tool_result_is_cuda_oom(result):
        return True
    text = _tool_result_error_text(result).lower()
    if not text:
        return False
    device = str(arguments.get("bge_device") or "").strip().lower()
    if device not in {"auto", "cuda"} and not device.startswith("cuda"):
        return False
    subprocess_crash_markers = (
        "calledprocesserror",
        "non-zero exit status 3221225477",
        "0xc0000005",
        "access violation",
    )
    return any(marker in text for marker in subprocess_crash_markers)


def _sec_search_arg_device_is_cuda(arguments: Mapping[str, Any]) -> bool:
    return str(arguments.get("bge_device") or "").strip().lower().startswith("cuda")


def _sec_search_result_cacheable_for_group(result: Mapping[str, Any]) -> bool:
    status = str(result.get("status") or "ok").strip().lower()
    if status in {"", "ok", "partial"}:
        return not _tool_result_error_text(result)
    return False


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
        if isinstance(result.get("resource_retry"), Mapping):
            summary["resource_retry"] = _sanitize_runtime_mapping(result.get("resource_retry") or {})
    elif tool_name == "sec_milvus_semantic_search":
        summary.update(
            {
                "context_row_count": len(result.get("context_rows") or []),
                "vector_kind_counts": _sanitize_runtime_mapping(result.get("vector_kind_counts") if isinstance(result.get("vector_kind_counts"), Mapping) else {}),
                "collection_name": str(result.get("collection_name") or ""),
                "typed_filter_required": bool(result.get("typed_filter_required", True)),
                "semantic_route_role": str(result.get("semantic_route_role") or "semantic_recall_supplement"),
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
    elif tool_name == "web_evidence_snapshot":
        summary.update(
            {
                "context_row_count": len(result.get("context_rows") or result.get("web_rows") or []),
                "snapshot_id": str(result.get("snapshot_id") or ""),
                "source_class": str(result.get("source_class") or ""),
                "web_scope_policy_ids": _string_list(result.get("web_scope_policy_ids")),
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
        "milvus_top_k",
        "vector_kinds",
        "typed_filter_required",
        "milvus_collection_name",
        "milvus_search_policy",
        "route_selection_reason",
        "route_cost_tier",
        "route_selection_policy",
        "url",
        "domain",
        "source_class",
        "claim_types",
        "web_scope_policy_ids",
        "snapshot_id",
        "snapshot_url",
        "company_domain_verified",
    }
    return {key: arguments.get(key) for key in allowed if key in arguments}


def _specialist_evidence_signal(agent_id: str, state: Mapping[str, Any]) -> dict[str, Any]:
    query_text = _state_query_text(state)
    if agent_id == "fundamental_analyst":
        count = (
            len(state.get("runtime_ledger_rows") or [])
            + len(
                [
                    row
                    for row in _row_dicts(state.get("context_rows"))
                    if _row_source_family(row)
                    in {"", "primary_sec_filing", "company_authored_unaudited_sec_filing", "company_product_evidence_graph"}
                ]
            )
            + len(
                [
                    row
                    for row in _row_dicts(state.get("product_evidence_rows"))
                    if _product_evidence_promotion_status(row) in {"runtime_fact_allowed", "runtime_context_taxonomy_only"}
                ]
            )
        )
        explicit = _contains_any(
            query_text,
            ("fundamental", "revenue", "margin", "capex", "cash flow", "product", "segment", "基本面", "收入", "利润率", "资本开支", "产品", "分部"),
        )
        return _signal(count, explicit, "fundamental_evidence_rows_or_explicit_fundamental_intent")
    if agent_id == "product_technology_analyst":
        count = (
            len(
                [
                    row
                    for row in _row_dicts(state.get("product_evidence_rows"))
                    if _product_evidence_promotion_status(row)
                    in {"runtime_fact_allowed", "runtime_context_taxonomy_only", "context_or_lead_available", "gap_exposed_not_fallback"}
                ]
            )
            + len(state.get("public_source_context_rows") or [])
            + len(
                [
                    row
                    for row in _row_dicts(state.get("context_rows"))
                    if _row_source_family(row) in {"company_product_evidence_graph", "public_source_context", "live_public_web_context"}
                ]
            )
        )
        explicit = _contains_any(
            query_text,
            (
                "product",
                "product kpi",
                "sku",
                "taxonomy",
                "platform",
                "developer",
                "clinical",
                "trial",
                "regulatory",
                "app",
                "openfda",
                "nhtsa",
                "产品",
                "产品线",
                "产品指标",
                "主业",
                "临床",
                "监管",
                "应用",
            ),
        )
        return _signal(count, explicit, "product_evidence_rows_public_proxy_rows_or_explicit_product_intent")
    if agent_id == "industry_supply_chain_analyst":
        count = (
            len(state.get("industry_snapshot_rows") or [])
            + len(state.get("public_source_context_rows") or [])
            + len([row for row in _row_dicts(state.get("context_rows")) if _row_source_family(row) == "live_public_web_context"])
            + len(
                [
                    row
                    for row in _row_dicts(state.get("product_evidence_rows"))
                    if _product_evidence_promotion_status(row) in {"runtime_context_taxonomy_only", "context_or_lead_available", "gap_exposed_not_fallback"}
                ]
            )
            + len(_relationship_rows_from_state(state))
        )
        explicit = _contains_any(
            query_text,
            (
                "industry",
                "sector",
                "supply chain",
                "customer",
                "supplier",
                "relationship",
                "public source",
                "shipment",
                "backlog",
                "order",
                "capex cycle",
                "customer concentration",
                "行业",
                "产业链",
                "上下游",
                "供应链",
                "客户",
                "供应商",
                "关系",
                "公开源",
                "订单",
                "积压",
                "出货",
                "出货周期",
                "客户集中",
                "资本开支周期",
                "竞争位置",
            ),
        )
        return _signal(count, explicit, "industry_or_relationship_rows_or_explicit_readthrough_intent")
    if agent_id == "market_valuation_analyst":
        count = len(state.get("market_snapshot_rows") or []) + len(
            [row for row in _row_dicts(state.get("context_rows")) if _row_source_family(row) == "market_snapshot"]
        )
        explicit = _contains_any(
            query_text,
            (
                "market",
                "valuation",
                "multiple",
                "share price",
                "return",
                "price-in",
                "liquidity",
                "short interest",
                "市场",
                "估值",
                "倍数",
                "股价",
                "定价",
                "资金面",
                "流动性",
                "做空",
            ),
        )
        return _signal(count, explicit, "market_snapshot_rows_or_explicit_market_intent")
    if agent_id == "risk_counterevidence_analyst":
        count = (
            len(state.get("source_gaps") or [])
            + len(state.get("runtime_ledger_rows") or [])
            + len(state.get("context_rows") or [])
            + len(state.get("market_snapshot_rows") or [])
            + len(state.get("industry_snapshot_rows") or [])
            + len(state.get("product_evidence_rows") or [])
            + len(state.get("public_source_context_rows") or [])
        )
        explicit = _contains_any(
            query_text,
            (
                "risk",
                "counterevidence",
                "counter evidence",
                "downside",
                "uncertainty",
                "conflict",
                "export control",
                "regulatory",
                "restriction",
                "sanction",
                "source boundary",
                "gap",
                "caveat",
                "风险",
                "反证",
                "下行",
                "不确定",
                "分歧",
                "出口限制",
                "出口管制",
                "监管",
                "制裁",
                "来源边界",
                "缺口",
                "限制",
            ),
        )
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
            str(state.get("prompt") or ""),
            str(contract.get("user_query") or ""),
            str(contract.get("prompt") or ""),
            " ".join(_string_list(contract.get("metric_families"))),
            " ".join(_string_list(contract.get("source_tiers"))),
            " ".join(_string_list(contract.get("eval_focus") or state.get("eval_focus"))),
            " ".join(_string_list(contract.get("required_dimension_ids") or state.get("required_dimension_ids"))),
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
    if tool_name == "sec_milvus_semantic_search":
        vector_counts = result.get("vector_kind_counts") if isinstance(result.get("vector_kind_counts"), Mapping) else {}
        row_kinds = {
            str(row.get("vector_kind") or "")
            for row in result.get("context_rows") or []
            if isinstance(row, Mapping) and str(row.get("vector_kind") or "")
        }
        missing = []
        if not vector_counts and not row_kinds:
            missing.append("vector_kind_counts")
        if result.get("typed_filter_required") is False:
            missing.append("typed_filter_required")
        return {
            "status": "fail" if missing else "pass",
            "allowed_claim_scope": "filing_semantic_recall_supplement",
            "prohibited_claim_scope": "exact_value_authority",
            "typed_filter_required": True,
            "missing": missing,
        }
    if tool_name == "relationship_graph_lookup":
        return {
            "status": "pass",
            "allowed_claim_scope": "research_scope_or_hypothesis_only",
            "prohibited_claim_scope": "company_reported_financial_fact",
        }
    if tool_name == "web_evidence_snapshot":
        rows = [dict(row) for row in result.get("context_rows") or result.get("web_rows") or [] if isinstance(row, Mapping)]
        missing: list[str] = []
        violations: list[str] = []
        if not str(result.get("snapshot_id") or "") and not any(str(row.get("snapshot_id") or "") for row in rows):
            missing.append("snapshot_id")
        if not str(result.get("as_of_datetime") or result.get("as_of_date") or "") and not any(str(row.get("as_of_datetime") or row.get("as_of_date") or "") for row in rows):
            missing.append("as_of_datetime")
        if not rows:
            missing.append("context_rows")
        for row in rows:
            if str(row.get("source_family") or "") != "live_public_web_context":
                violations.append("source_family_must_be_live_public_web_context")
            if not bool(row.get("context_only", True)):
                violations.append("web_rows_must_be_context_only")
            if bool(row.get("exact_value_authority")):
                violations.append("web_rows_cannot_be_exact_value_authority")
            if not str(row.get("source_class") or ""):
                missing.append("source_class")
            if not str(row.get("snapshot_url") or row.get("url") or ""):
                missing.append("snapshot_url")
            if not (row.get("citation") or row.get("citation_url") or row.get("source_url")):
                missing.append("citation")
            if row.get("search_snippet") and not str(row.get("snapshot_id") or result.get("snapshot_id") or ""):
                violations.append("search_snippet_without_snapshot_forbidden")
            source_class = str(row.get("source_class") or "")
            claim_types = set(_web_claim_types(row))
            if source_class == "commerce_product_surface" and claim_types - WEB_COMMERCE_ALLOWED_CLAIM_TYPES:
                violations.append("commerce_claim_scope_violation")
            if source_class in {"social_official_account", "social_unverified_or_influencer"} and claim_types & WEB_FINANCIAL_FACT_CLAIM_TYPES:
                violations.append("social_financial_fact_forbidden")
        return {
            "status": "fail" if missing or violations else "pass",
            "allowed_claim_scope": "allowlisted_web_snapshot_context_only",
            "prohibited_claim_scope": "company_reported_financial_fact_or_exact_value_authority",
            "missing": _dedupe(missing),
            "violations": _dedupe(violations),
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


def reflection_report_from_evidence_fusion_bundle(
    evidence_fusion_bundle: Mapping[str, Any] | None,
    *,
    evidence_requirement_plan: Mapping[str, Any] | None = None,
    source_gaps: list[Mapping[str, Any]] | None = None,
    tool_ledger_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build coverage reflection from fused rows before inspecting route gaps.

    Coverage is evaluated at the required-item level. A supplemental route with
    zero rows should not trigger second pass when the same required item already
    has fused authority rows from another route with the correct boundary.
    """
    bundle = dict(evidence_fusion_bundle or {})
    rows = [dict(item) for item in bundle.get("authority_rows") or [] if isinstance(item, Mapping)]
    plan = evidence_requirement_plan if isinstance(evidence_requirement_plan, Mapping) else {}
    source_gaps_list = [dict(item) for item in source_gaps or [] if isinstance(item, Mapping)]
    missing: list[dict[str, Any]] = []
    second_pass_requests: list[dict[str, Any]] = []
    source_family_gaps: list[dict[str, Any]] = []
    quality_gaps: list[dict[str, Any]] = []

    for index, requirement in enumerate(plan.get("requirements") or [], start=1):
        if not isinstance(requirement, Mapping):
            continue
        enriched = _enrich_evidence_requirement(requirement)
        req_keys = _requirement_keys(enriched)
        req_rows = [
            row
            for row in rows
            if req_keys & _requirement_keys(row)
            and str(row.get("authority_tier") or "") != "gap_only"
            and str(row.get("claim_scope") or "") != "bounded_gap_only"
            and _row_relevant_for_requirement(enriched, row)
        ]
        if _fused_rows_cover_requirement(enriched, req_rows):
            if _fused_rows_are_bounded_context_only(req_rows):
                quality_gaps.append(_quality_gap_bounded_context_only_requirement(enriched, req_rows))
            continue
        task = _coverage_task_from_requirement_gap(
            enriched,
            _string_list(enriched.get("source_families") or enriched.get("source_tiers")),
            ["fused_evidence:no_authority_rows"],
        )
        missing_item = _missing_requirement_from_coverage_task(
            task,
            requirement=enriched,
            source_gaps=source_gaps_list,
            available_source_families=None,
        )
        missing.append(missing_item)
        source_family_gaps.extend(_source_family_gap_items(missing_item))
        if missing_item.get("source_available", True):
            second_pass_requests.append(_second_pass_request_from_missing(missing_item, index))

    source_available = all(bool(item.get("source_available", True)) for item in missing)
    if missing:
        level = "partial" if source_available else "insufficient"
    else:
        level = "partial" if quality_gaps else "sufficient"
    return normalize_reflection_report(
        {
            "sufficiency_level": level,
            "missing_requirements": missing,
            "source_available": source_available,
            "second_pass_requests": second_pass_requests if missing and source_available else [],
            "source_family_gaps": source_family_gaps,
            "tool_ledger_summary": dict(tool_ledger_summary or {}),
            "needs_user_clarification": bool(missing and not source_available),
            "bounded_answer_allowed": bool(quality_gaps or missing),
            "confidence_by_claim_type": _confidence_by_claim_type_from_fusion_rows(rows),
            "trigger": "coverage_reflection_evidence_fusion_bundle",
            "quality_gaps": quality_gaps,
        }
    )


def _fused_rows_cover_requirement(requirement: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> bool:
    if not rows:
        return False
    strong_tiers = {"primary_exact_value", "company_disclosed_context"}
    if any(str(row.get("authority_tier") or "") in strong_tiers for row in rows):
        return True
    routes = set(_string_list(requirement.get("evidence_routes") or requirement.get("retrieval_routes")))
    source_families = set(_string_list(requirement.get("source_families") or requirement.get("source_tiers")))
    context_sources = {"industry_snapshot", "market_snapshot", "relationship_graph", "company_product_evidence_graph", "public_source_context"}
    if not (routes & {"industry_snapshot", "market_snapshot", "relationship_graph"} or source_families & context_sources):
        return False
    return any(
        str(row.get("authority_tier") or "") == "context_or_proxy"
        or str(row.get("claim_scope") or "") in {"context_or_proxy_only", "scope_or_hypothesis_only"}
        for row in rows
    )


def _fused_rows_are_bounded_context_only(rows: list[Mapping[str, Any]]) -> bool:
    return bool(rows) and not any(
        str(row.get("authority_tier") or "") in {"primary_exact_value", "company_disclosed_context"}
        for row in rows
    )


def _quality_gap_bounded_context_only_requirement(requirement: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "gap_type": "bounded_context_only_requirement",
        "requirement_id": str(requirement.get("requirement_id") or requirement.get("evidence_requirement_id") or ""),
        "task_id": str(requirement.get("task_id") or ""),
        "source_families": _dedupe([str(row.get("source_family") or "") for row in rows if str(row.get("source_family") or "")]),
        "authority_tiers": _dedupe([str(row.get("authority_tier") or "") for row in rows if str(row.get("authority_tier") or "")]),
        "claim_scopes": _dedupe([str(row.get("claim_scope") or "") for row in rows if str(row.get("claim_scope") or "")]),
        "row_count": len(rows),
        "boundary": "covered_for_context_or_proxy_only_not_exact_financial_or_product_kpi",
    }


def _confidence_by_claim_type_from_fusion_rows(rows: list[Mapping[str, Any]]) -> dict[str, str]:
    tiers_by_scope: dict[str, set[str]] = {}
    for row in rows:
        scope = str(row.get("claim_scope") or "")
        if scope:
            tiers_by_scope.setdefault(scope, set()).add(str(row.get("authority_tier") or ""))
    confidence: dict[str, str] = {}
    for scope, tiers in tiers_by_scope.items():
        if "primary_exact_value" in tiers:
            confidence[scope] = "high"
        elif "company_disclosed_context" in tiers:
            confidence[scope] = "medium"
        elif "context_or_proxy" in tiers:
            confidence[scope] = "bounded_low_to_medium"
        else:
            confidence[scope] = "bounded_low"
    return confidence


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
        route_keys = _requirement_keys(route)
        if not route_keys:
            route_id = str(route.get("route_id") or "")
            route_keys = {route_id} if route_id else set()
        if not route_keys or route_keys <= seen:
            continue
        seen.update(route_keys)
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
    for key in ("evidence_requirement_id", "evidence_requirement_ids", "requirement_id", "parent_requirement_id", "task_id"):
        values = _string_list(route.get(key))
        if values:
            return values[0]
    return ""


def _requirement_keys(value: Mapping[str, Any]) -> set[str]:
    keys: set[str] = set()
    for key in ("requirement_id", "evidence_requirement_id", "evidence_requirement_ids", "parent_requirement_id", "task_id"):
        keys.update(_string_list(value.get(key)))
    return keys


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
    if "milvus_semantic" in source_set:
        routes.append("milvus_semantic")
    if "live_public_web_context" in source_set:
        routes.append("live_public_web_context")
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
                "route_cost_tier": ROUTE_COST_TIER.get(route, "medium"),
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


def _runtime_ledger_rows_from_sec_context(
    context_rows: list[dict[str, Any]],
    *,
    state_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    scan_limit = _env_int("MULTI_AGENT_SEC_CONTEXT_LEDGER_SCAN_LIMIT", default=80, minimum=0, maximum=500)
    row_limit = _env_int("MULTI_AGENT_SEC_CONTEXT_LEDGER_ROW_LIMIT", default=160, minimum=0, maximum=1000)
    if scan_limit <= 0 or row_limit <= 0:
        return []
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for context_row in context_rows[:scan_limit]:
        evidence = _context_row_to_runtime_evidence_object(context_row)
        if evidence is None:
            continue
        try:
            extraction = extract_structured_objects(evidence)
        except Exception:  # noqa: BLE001 - extraction is supplemental and must not break retrieval.
            continue
        for metric in extraction.metrics:
            record = metric.model_dump(mode="json")
            if record.get("extraction_method") != "table_row_heuristic":
                continue
            if _runtime_metric_is_change_column(record):
                continue
            ledger_row = _runtime_ledger_row_from_metric(record, context_row=context_row, state_context=state_context)
            if not ledger_row:
                continue
            key = _runtime_ledger_dedupe_key(ledger_row)
            if key in seen:
                continue
            seen.add(key)
            rows.append(ledger_row)
            if len(rows) >= row_limit:
                return rows
    return rows


def _context_row_to_runtime_evidence_object(row: Mapping[str, Any]) -> EvidenceObject | None:
    text = str(row.get("text") or row.get("summary") or row.get("preview") or row.get("content") or "").strip()
    if not text or "[TABLE_START" not in text:
        return None
    source_family = _sec_context_source_family(row)
    if source_family not in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}:
        return None
    source_type = _sec_context_form_type(row, source_family=source_family)
    evidence_id = str(row.get("evidence_id") or row.get("evidence_ref") or row.get("id") or "").strip()
    if not evidence_id:
        evidence_id = "context_evidence::" + hashlib.sha1(text[:2000].encode("utf-8", errors="ignore")).hexdigest()[:12]
    fiscal_year = _year_from_any(row.get("fiscal_year") or row.get("year"))
    return EvidenceObject(
        evidence_id=evidence_id,
        source_type=source_type,  # type: ignore[arg-type]
        source_tier=source_family,  # type: ignore[arg-type]
        ticker=str(row.get("ticker") or row.get("symbol") or "").upper(),
        company=str(row.get("company") or row.get("company_name") or "") or None,
        fiscal_year=fiscal_year,
        period_end=str(row.get("period_end") or row.get("fiscal_period_end") or "") or None,
        period_type=str(row.get("period_type") or "") or None,
        duration_months=_int_or_none(row.get("duration_months")),
        fiscal_period=str(row.get("fiscal_period") or "") or None,
        publication_date=str(row.get("publication_date") or row.get("filing_date") or row.get("accepted_date") or "") or None,
        section=str(row.get("section") or row.get("item") or "") or None,
        subsection=str(row.get("subsection") or row.get("title") or "") or None,
        evidence_type=str(row.get("evidence_type") or row.get("source_kind") or "filing_text"),
        text=text,
        source_url=str(row.get("source_url") or row.get("filing_url") or "") or None,
        local_path=None,
        metadata={
            "form_type": source_type,
            "source_tier": source_family,
            "period_end": str(row.get("period_end") or row.get("fiscal_period_end") or "") or None,
            "period_type": str(row.get("period_type") or "") or None,
            "duration_months": _int_or_none(row.get("duration_months")),
            "fiscal_period": str(row.get("fiscal_period") or "") or None,
            "block_id": row.get("block_id"),
            "context_evidence_ref": evidence_id,
        },
    )


def _runtime_ledger_row_from_metric(
    record: Mapping[str, Any],
    *,
    context_row: Mapping[str, Any],
    state_context: Mapping[str, Any],
) -> dict[str, Any] | None:
    value = record.get("value")
    if value is None:
        return None
    unit = str(record.get("unit") or "").strip()
    if not unit:
        return None
    source_family = _sec_context_source_family(context_row)
    if source_family not in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}:
        return None
    metric_family = _runtime_metric_family(record, context_row=context_row)
    fiscal_year = _runtime_metric_year(record, context_row=context_row)
    fiscal_period = _runtime_metric_fiscal_period(record, context_row=context_row)
    evidence_ref = str(record.get("source_evidence_id") or "")
    object_id = str(record.get("object_id") or "")
    if object_id:
        evidence_ref = f"{evidence_ref}::{object_id}" if evidence_ref else object_id
    product_or_segment = _runtime_metric_product_or_segment(record, metric_family=metric_family)
    return {
        "source_id": str(record.get("source_evidence_id") or context_row.get("source_id") or context_row.get("document_id") or ""),
        "evidence_ref": evidence_ref,
        "ticker": str(record.get("ticker") or context_row.get("ticker") or "").upper(),
        "metric_family": metric_family,
        "metric_name": str(record.get("metric_name") or record.get("row_label") or ""),
        "row_label": str(record.get("row_label") or ""),
        "label": str(record.get("metric_name") or record.get("row_label") or ""),
        "product_or_segment": product_or_segment,
        "value": str(value),
        "numeric_value": str(value),
        "raw_value_text": str(record.get("raw_value") or ""),
        "unit": unit,
        "fiscal_year": str(fiscal_year or ""),
        "fiscal_period": fiscal_period,
        "period": str(record.get("period") or ""),
        "period_role": str(record.get("period_role") or ""),
        "fiscal_period_end": _runtime_metric_period_end(fiscal_year=fiscal_year, fiscal_period=fiscal_period, context_row=context_row),
        "source_family": source_family,
        "form_type": _sec_context_form_type(context_row, source_family=source_family),
        "document_id": str(context_row.get("document_id") or context_row.get("accession_number") or ""),
        "filing_date": str(context_row.get("filing_date") or context_row.get("publication_date") or ""),
        "accepted_date": str(context_row.get("accepted_date") or context_row.get("accepted_at") or ""),
        "source_text": str(record.get("context") or "")[:500],
        "exact_value_authority": True,
        "parser_version": "multi_agent_sec_context_table_structured_extractor_v0_1",
        "ledger_extraction_source": "multi_agent_sec_context_table_structured_extractor",
        "run_id": str(state_context.get("run_id") or ""),
    }


def _runtime_metric_is_change_column(record: Mapping[str, Any]) -> bool:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), Mapping) else {}
    if str(metadata.get("cell_kind") or "") == "change_value":
        return True
    column = str(record.get("column_label") or "").lower()
    return "% change" in column or "percent change" in column or "change" == column.strip()


def _runtime_metric_family(record: Mapping[str, Any], *, context_row: Mapping[str, Any]) -> str:
    row_label = str(record.get("row_label") or record.get("metric_name") or "")
    label = _norm_text(row_label)
    context = _norm_text(" ".join(str(record.get(key) or "") for key in ("context", "metric_name", "row_label")))
    product_revenue_context = (
        "selected revenue highlights" in context
        or "selected products" in context
        or "net product revenue" in label
        or "product revenue" in label
        or "product sales" in label
    )
    if product_revenue_context and "revenue" not in label and label not in {"revenue", "total revenue"}:
        return "product_revenue"
    if product_revenue_context and ("product" in label or label not in {"revenue", "revenues", "total revenue"}):
        return "product_revenue"
    return ""


def _runtime_metric_product_or_segment(record: Mapping[str, Any], *, metric_family: str) -> str:
    if metric_family != "product_revenue":
        return str(record.get("segment") or "")
    label = str(record.get("row_label") or record.get("metric_name") or "").strip()
    normalized = _norm_text(label)
    if normalized in {"net product revenue", "product revenue", "products", "revenue", "total revenue"}:
        return ""
    return label


def _runtime_metric_year(record: Mapping[str, Any], *, context_row: Mapping[str, Any]) -> int | None:
    for value in (record.get("period"), record.get("column_label"), record.get("fiscal_year"), context_row.get("fiscal_year"), context_row.get("year")):
        year = _year_from_any(value)
        if year is not None:
            return year
    return None


def _runtime_metric_fiscal_period(record: Mapping[str, Any], *, context_row: Mapping[str, Any]) -> str:
    explicit = str(record.get("fiscal_period") or context_row.get("fiscal_period") or "").strip()
    if explicit:
        return explicit
    text = _norm_text(" ".join(str(value or "") for value in (context_row.get("text"), record.get("context"), record.get("column_label"))))
    if "first quarter" in text or "first-quarter" in text or "three months ended march 31" in text:
        return "Q1"
    if "six months ended june 30" in text:
        return "Q2_YTD"
    if "nine months ended september 30" in text:
        return "Q3_YTD"
    if "year ended december 31" in text or "twelve months ended december 31" in text:
        return "FY"
    return ""


def _runtime_metric_period_end(*, fiscal_year: int | None, fiscal_period: str, context_row: Mapping[str, Any]) -> str:
    explicit = str(context_row.get("period_end") or context_row.get("fiscal_period_end") or "").strip()
    if explicit:
        return explicit
    if not fiscal_year:
        return ""
    return {
        "Q1": f"{fiscal_year}-03-31",
        "Q2_YTD": f"{fiscal_year}-06-30",
        "Q3_YTD": f"{fiscal_year}-09-30",
        "FY": f"{fiscal_year}-12-31",
    }.get(fiscal_period, "")


def _sec_context_source_family(row: Mapping[str, Any]) -> str:
    family = str(row.get("source_family") or row.get("source_tier") or "").strip()
    if family == "primary_filing":
        return "primary_sec_filing"
    form_type = _sec_context_form_type(row, source_family=family)
    if not family and form_type == "8-K":
        return "company_authored_unaudited_sec_filing"
    return family


def _sec_context_form_type(row: Mapping[str, Any], *, source_family: str) -> str:
    form_type = str(row.get("form_type") or row.get("source_type") or "").strip().upper()
    if form_type in {"10-K", "10-Q", "8-K", "20-F", "40-F"}:
        return form_type
    return "8-K" if source_family == "company_authored_unaudited_sec_filing" else "10-Q"


def _merge_runtime_ledger_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for row in rows:
        key = _runtime_ledger_dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
    return merged


def _runtime_ledger_dedupe_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("ticker") or ""),
        str(row.get("metric_family") or row.get("metric_name") or ""),
        str(row.get("product_or_segment") or ""),
        str(row.get("fiscal_year") or row.get("period") or ""),
        str(row.get("raw_value_text") or row.get("value") or ""),
    )


def _year_from_any(value: Any) -> int | None:
    match = re.search(r"\b(19\d{2}|20\d{2})\b", str(value or ""))
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _env_int(name: str, *, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _norm_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u2011", "-").replace("\u2013", "-").lower()).strip()


def _rows_from_result(tool_name: str, result: Mapping[str, Any]) -> list[dict[str, Any]]:
    keys = {
        "sec_search_filings": "context_rows",
        "sec_milvus_semantic_search": "context_rows",
        "sec_query_exact_value_ledger": "ledger_rows",
        "market_get_snapshot": "market_rows",
        "industry_get_snapshot": "industry_rows",
        "relationship_graph_lookup": "relationship_rows",
        "web_evidence_snapshot": "context_rows",
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
                "route_cost_tier": ROUTE_COST_TIER.get(route, "medium"),
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
    req["route_cost_tier"] = _normalize_route_cost_tier_value(req.get("route_cost_tier") or req.get("cost_tier"), _string_list(req.get("evidence_routes") or req.get("retrieval_routes")))
    req["route_selection_reason"] = str(req.get("route_selection_reason") or req.get("route_reason") or "")[:300]
    req["route_selection_policy"] = str(req.get("route_selection_policy") or "cost_and_query_type_aware_v0_1")[:100]
    req["planner_boundary"] = "business_need_only_no_physical_paths"
    return req


def _normalize_route_cost_tier_value(value: Any, routes: list[str]) -> str:
    text = str(value or "").strip().lower()
    if text in ROUTE_COST_TIER_RANK:
        return text
    tiers = [ROUTE_COST_TIER.get(route, "medium") for route in routes]
    if not tiers:
        return "medium"
    return max(tiers, key=lambda tier: ROUTE_COST_TIER_RANK.get(tier, 2))


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
    if "live_public_web_context" in routes:
        families.append("allowlisted_web_context")
    if not families:
        families.append(str(requirement.get("analysis_intent") or "business_observation"))
    return _dedupe(families)


def _bounded_rows_for_agent_data_view(agent_id: str, state: Mapping[str, Any]) -> list[dict[str, Any]]:
    max_rows = _data_view_max_rows_for_agent(agent_id, state)
    focus_tickers = _focus_tickers_from_state(state)
    fused_role_rows = _fusion_rows_for_agent_data_view(agent_id, state)
    rows: list[dict[str, Any]] = []
    if agent_id == "fundamental_analyst":
        rows.extend(_row_dicts(state.get("runtime_ledger_rows")))
        rows.extend(_derived_metric_rows_for_agent_data_view(agent_id, state))
        rows.extend(
            row
            for row in _row_dicts(state.get("product_evidence_rows"))
            if _product_evidence_promotion_status(row) in {"runtime_fact_allowed", "runtime_context_taxonomy_only"}
        )
        rows.extend(
            row
            for row in _row_dicts(state.get("context_rows"))
            if _row_source_family(row)
            in {"", "primary_sec_filing", "company_authored_unaudited_sec_filing", "company_product_evidence_graph"}
            and (
                _row_source_family(row) != "company_product_evidence_graph"
                or _product_evidence_promotion_status(row) in {"runtime_fact_allowed", "runtime_context_taxonomy_only"}
            )
        )
        if not rows:
            rows.extend(fused_role_rows)
        candidate_rows = list(rows)
        rows = _focus_ticker_balanced_rows(
            rows,
            focus_tickers=focus_tickers,
            max_rows=max_rows,
            source_families={
                "",
                "primary_sec_filing",
                "company_authored_unaudited_sec_filing",
                "derived_metric_layer",
                "company_product_evidence_graph",
            },
            min_rows_per_ticker=_focus_ticker_min_rows(max_rows=max_rows, focus_ticker_count=len(focus_tickers)),
        )
        rows = _ensure_min_requirement_rows(
            rows,
            candidate_rows,
            requirement_id="req_hyperscaler_capex",
            min_rows=min(2, max(1, max_rows // 10)),
            max_rows=max_rows,
        )
        rows = _ensure_min_requirement_ticker_rows(
            rows,
            candidate_rows,
            requirement_id="req_hyperscaler_capex",
            min_distinct_tickers=2,
            max_rows=max_rows,
        )
        rows = _ensure_min_requirement_rows(
            rows,
            candidate_rows,
            requirement_id="req_dell_margin_quality",
            min_rows=min(2, max(1, max_rows // 10)),
            max_rows=max_rows,
        )
    elif agent_id == "market_valuation_analyst":
        rows.extend(_row_dicts(state.get("market_snapshot_rows")))
        rows.extend(row for row in _row_dicts(state.get("context_rows")) if _row_source_family(row) == "market_snapshot")
        if not rows:
            rows.extend(fused_role_rows)
    elif agent_id == "product_technology_analyst":
        rows.extend(
            row
            for row in _row_dicts(state.get("product_evidence_rows"))
            if _product_evidence_promotion_status(row)
            in {
                "runtime_fact_allowed",
                "runtime_context_taxonomy_only",
                "context_or_lead_available",
                "review_queue_not_runtime_fact",
                "gap_exposed_not_fallback",
            }
        )
        rows.extend(_row_dicts(state.get("public_source_context_rows")))
        rows.extend(
            row
            for row in _row_dicts(state.get("context_rows"))
            if _row_source_family(row) in {"company_product_evidence_graph", "public_source_context", "live_public_web_context"}
        )
        rows.extend(
            product_intelligence_context_rows_for_state(
                state,
                tickers=focus_tickers,
                repo_root=os.getcwd(),
                max_rows=_product_intelligence_context_candidate_budget(
                    max_rows=max_rows,
                    focus_ticker_count=len(focus_tickers),
                ),
                autoload=_product_intelligence_autoload_arg(state),
            )
        )
        rows.extend(fused_role_rows)
        if not any(_row_source_family(row) in {"company_product_evidence_graph", "public_source_context", "live_public_web_context"} for row in rows):
            rows.extend(_product_source_gap_rows_for_agent_data_view(state))
        product_source_order = [
            "company_product_evidence_graph",
            "industry_snapshot",
            "relationship_graph",
            "public_source_context",
            "live_public_web_context",
        ]
        if len(focus_tickers) >= 2:
            rows = _product_ticker_balanced_rows(
                rows,
                focus_tickers=focus_tickers,
                max_rows=max_rows,
                source_order=product_source_order,
            )
        else:
            rows = _balanced_rows_by_source(
                rows,
                source_order=product_source_order,
                max_rows=max_rows,
            )
    elif agent_id == "industry_supply_chain_analyst":
        rows.extend(_row_dicts(state.get("industry_snapshot_rows")))
        rows.extend(
            row
            for row in product_intelligence_context_rows_for_state(
                state,
                tickers=focus_tickers,
                repo_root=os.getcwd(),
                max_rows=max(24, max_rows * 2),
                autoload=_product_intelligence_autoload_arg(state),
            )
            if _row_source_family(row) in {"company_product_evidence_graph", "public_source_context", "live_public_web_context"}
            and _contains_any(
                " ".join(
                    str(row.get(key) or "")
                    for key in ("authority_type", "relationship_type", "edge_type", "source_class", "claim_scope", "summary")
                ),
                ("supply", "supplier", "component", "deployment", "customer", "competitive", "competes", "relationship"),
            )
        )
        if not rows:
            rows.extend(fused_role_rows)
        rows.extend(
            row
            for row in _row_dicts(state.get("product_evidence_rows"))
            if _product_evidence_promotion_status(row) in {"runtime_fact_allowed", "runtime_context_taxonomy_only", "context_or_lead_available", "gap_exposed_not_fallback"}
        )
        rows.extend(_row_dicts(state.get("public_source_context_rows")))
        rows.extend(
            row
            for row in _row_dicts(state.get("context_rows"))
            if _row_source_family(row)
            in {"industry_snapshot", "relationship_graph", "company_product_evidence_graph", "public_source_context", "live_public_web_context"}
        )
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
        rows.extend(_derived_metric_rows_for_agent_data_view(agent_id, state))
        rows.extend(_row_dicts(state.get("product_evidence_rows")))
        rows.extend(_row_dicts(state.get("public_source_context_rows")))
        if not rows:
            rows.extend(fused_role_rows)
        if agent_id != "risk_counterevidence_analyst":
            rows.extend(_relationship_rows_from_state(state))
    else:
        rows.extend(_row_dicts(state.get("context_rows")))
    if agent_id == "risk_counterevidence_analyst":
        if len(focus_tickers) >= 2:
            candidate_rows = rows
            rows = _focus_ticker_balanced_rows(
                rows,
                focus_tickers=focus_tickers,
                max_rows=max_rows,
                source_families=None,
                min_rows_per_ticker=_focus_ticker_min_rows(max_rows=max_rows, focus_ticker_count=len(focus_tickers), default=2),
            )
            rows = _ensure_min_source_family_rows(
                rows,
                candidate_rows,
                source_family="market_snapshot",
                min_rows=min(2, max(1, max_rows // 8)),
                max_rows=max_rows,
            )
            rows = _ensure_min_source_family_rows(
                rows,
                candidate_rows,
                source_family="industry_snapshot",
                min_rows=min(2, max(1, max_rows // 8)),
                max_rows=max_rows,
            )
            rows = _ensure_min_requirement_rows(
                rows,
                candidate_rows,
                requirement_id="req_hyperscaler_capex",
                min_rows=min(2, max(1, max_rows // 8)),
                max_rows=max_rows,
            )
            rows = _ensure_min_requirement_ticker_rows(
                rows,
                candidate_rows,
                requirement_id="req_hyperscaler_capex",
                min_distinct_tickers=2,
                max_rows=max_rows,
            )
            rows = _ensure_min_requirement_rows(
                rows,
                candidate_rows,
                requirement_id="req_dell_margin_quality",
                min_rows=min(2, max(1, max_rows // 8)),
                max_rows=max_rows,
            )
        else:
            rows = _balanced_rows_by_source(
                rows,
                source_order=[
                    "primary_sec_filing",
                    "company_authored_unaudited_sec_filing",
                    "company_product_evidence_graph",
                    "derived_metric_layer",
                    "market_snapshot",
                    "industry_snapshot",
                    "public_source_context",
                    "run_artifact",
                    "",
                ],
                max_rows=max_rows,
            )
    return [_bounded_row(row, index) for index, row in enumerate(rows[:max_rows], start=1)]


def _derived_metric_rows_for_agent_data_view(agent_id: str, state: Mapping[str, Any]) -> list[dict[str, Any]]:
    if agent_id not in {"fundamental_analyst", "risk_counterevidence_analyst"}:
        return []
    layer = state.get("derived_metric_layer") if isinstance(state.get("derived_metric_layer"), Mapping) else {}
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(layer.get("derived_metrics") or [], start=1):
        if not isinstance(row, Mapping):
            continue
        evidence_ref = str(row.get("evidence_ref") or row.get("derived_metric_id") or row.get("metric_id") or "").strip()
        if not evidence_ref:
            evidence_ref = f"derived_metric::{index}"
        ticker = str(row.get("ticker") or row.get("company") or "").upper().strip()
        metric_family = str(row.get("derived_metric_family") or row.get("metric_family") or row.get("metric") or "").strip()
        value = _scalar_or_blank(row.get("display_value") or row.get("value") or row.get("numeric_value"))
        unit = str(row.get("unit") or row.get("unit_family") or "").strip()
        period = str(row.get("period_key") or row.get("fiscal_period") or row.get("period") or "").strip()
        product_or_segment = str(row.get("product_or_segment") or row.get("segment") or row.get("product") or "").strip()
        summary_parts = [
            ticker,
            product_or_segment,
            metric_family,
            f"= {value} {unit}".strip() if value else "",
            period,
        ]
        summary = " ".join(part for part in summary_parts if part).strip()
        if summary:
            summary = f"{summary}; derived from reconciled exact public filing facts."
        else:
            summary = "Derived metric from reconciled exact public filing facts."
        rows.append(
            {
                **dict(row),
                "evidence_ref": evidence_ref,
                "source_family": "derived_metric_layer",
                "source_role": "deterministic_derived_financial_metric",
                "ticker": ticker,
                "metric": metric_family or str(row.get("formula_id") or "derived_financial_metric"),
                "metric_family": metric_family,
                "value": value,
                "unit": unit,
                "unit_family": str(row.get("unit_family") or unit).strip(),
                "fiscal_year": _scalar_or_blank(row.get("fiscal_year")),
                "fiscal_period": _scalar_or_blank(row.get("fiscal_period")),
                "period_key": period,
                "product_or_segment": product_or_segment,
                "summary": str(row.get("summary") or summary),
                "source_policy": str(row.get("source_policy") or "derived_from_reconciled_exact_facts_no_proxy"),
                "claim_boundary": str(
                    row.get("claim_boundary")
                    or "Derived metric may support formula-bounded financial observations only when cited with input evidence refs."
                ),
                "allowed_claim_scope": str(row.get("allowed_claim_scope") or "derived_financial_metric_observation"),
                "exact_value_authority": True,
                "context_only": False,
                "promotion_status": "runtime_fact_allowed",
                "input_evidence_refs": _string_list(row.get("input_evidence_refs")),
                "input_fact_ids": _string_list(row.get("input_fact_ids")),
            }
        )
    return rows


def _product_source_gap_rows_for_agent_data_view(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    requested_sources = _requested_product_source_families_from_state(state)
    if not requested_sources:
        return []
    focus_tickers = _focus_tickers_from_state(state)
    if not focus_tickers:
        focus_tickers = _search_scope_tickers_from_state(state, focus_tickers=[])[:2]
    if not focus_tickers:
        focus_tickers = [""]
    metrics = _requested_metric_families_from_state(state)
    metric = ",".join(metrics[:6]) or "product_or_public_proxy_metric"
    rows: list[dict[str, Any]] = []
    for ticker in focus_tickers[:4]:
        for source_family in requested_sources:
            gap_type = (
                "commercial_market_tracker_gap_after_public_source_check"
                if source_family == "public_source_context"
                else "product_kpi_parser_or_source_gap"
            )
            rows.append(
                {
                    "gap_id": f"product_source_gap::{ticker or 'UNKNOWN'}::{source_family}",
                    "evidence_ref": f"product_source_gap::{ticker or 'UNKNOWN'}::{source_family}",
                    "source_family": source_family,
                    "ticker": ticker,
                    "metric": metric,
                    "gap_type": gap_type,
                    "reason": "Requested product/public product evidence is not materialized in the current public-source runtime.",
                    "reason_code": "product_public_source_not_materialized",
                    "promotion_status": "gap_exposed_not_fallback",
                    "claim_scope": "bounded_gap_only",
                    "context_only": True,
                    "exact_value_authority": False,
                    "gap_only": True,
                    "repairability": "requires_company_product_parser_or_commercial_tracker",
                    "summary": (
                        "Bounded product evidence gap: current public/free runtime has no product evidence row for this ticker/source family. "
                        "Do not fill with generic SEC or market proxy facts; expose the missing product KPI/tracker confirmation."
                    ),
                }
            )
    return rows


def _requested_product_source_families_from_state(state: Mapping[str, Any]) -> list[str]:
    sources: list[str] = []
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    sources.extend(_string_list(query_contract.get("source_tiers") or query_contract.get("source_families")))
    evidence_plan = state.get("evidence_requirement_plan") if isinstance(state.get("evidence_requirement_plan"), Mapping) else {}
    scope = evidence_plan.get("scope") if isinstance(evidence_plan.get("scope"), Mapping) else {}
    sources.extend(_string_list(scope.get("source_tiers") or scope.get("source_families")))
    for requirement in evidence_plan.get("requirements") or []:
        if isinstance(requirement, Mapping):
            sources.extend(_string_list(requirement.get("source_tiers") or requirement.get("source_families")))
    return _dedupe([source for source in sources if source in {"company_product_evidence_graph", "public_source_context", "live_public_web_context"}])


def _requested_metric_families_from_state(state: Mapping[str, Any]) -> list[str]:
    metrics: list[str] = []
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    metrics.extend(_string_list(query_contract.get("metric_families")))
    evidence_plan = state.get("evidence_requirement_plan") if isinstance(state.get("evidence_requirement_plan"), Mapping) else {}
    scope = evidence_plan.get("scope") if isinstance(evidence_plan.get("scope"), Mapping) else {}
    metrics.extend(_string_list(scope.get("metric_families")))
    for requirement in evidence_plan.get("requirements") or []:
        if isinstance(requirement, Mapping):
            metrics.extend(_string_list(requirement.get("metric_families")))
    return _dedupe(metrics)


def _bounded_row(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    evidence_ref = (
        row.get("evidence_ref")
        or row.get("evidence_id")
        or row.get("gap_id")
        or row.get("metric_id")
        or row.get("source_id")
        or row.get("id")
        or f"bounded_row_{index}"
    )
    bounded = {
        "evidence_ref": str(evidence_ref),
        "source_family": _row_source_family(row),
        "ticker": str(row.get("ticker") or row.get("company") or ""),
        "fiscal_year": _scalar_or_blank(row.get("fiscal_year") or row.get("source_fiscal_year") or row.get("year")),
        "form_type": str(row.get("form_type") or row.get("source_type") or ""),
        "period_role": str(row.get("period_role") or row.get("period") or ""),
        "metric": str(row.get("metric") or row.get("metric_name") or row.get("field") or ""),
        "value": _scalar_or_blank(row.get("value") or row.get("numeric_value") or row.get("display_value")),
        "raw_value_text": _truncate(str(row.get("raw_value_text") or ""), 300),
        "display_value_zh": _truncate(str(row.get("display_value_zh") or row.get("display_value") or ""), 300),
        "source_statement": _truncate(str(row.get("source_statement") or ""), 500),
        "summary": _truncate(str(row.get("summary") or row.get("text") or row.get("snippet") or row.get("description") or ""), 900),
        "snapshot_id": str(row.get("snapshot_id") or ""),
        "as_of_date": str(row.get("as_of_date") or ""),
    }
    promotion_status = _product_evidence_promotion_status(row)
    if promotion_status:
        bounded["promotion_status"] = promotion_status
    claim_scope = str(row.get("claim_scope") or row.get("allowed_claim_scope") or "").strip()
    if claim_scope:
        bounded["claim_scope"] = claim_scope
    if row.get("context_only") is not None:
        bounded["context_only"] = bool(row.get("context_only"))
    if row.get("exact_value_authority") is not None:
        bounded["exact_value_authority"] = bool(row.get("exact_value_authority"))
    allowed_claims = _string_list(row.get("allowed_claims"))
    forbidden_claims = _string_list(row.get("forbidden_claims"))
    if allowed_claims:
        bounded["allowed_claims"] = allowed_claims[:8]
    if forbidden_claims:
        bounded["forbidden_claims"] = forbidden_claims[:8]
    evidence_layer = str(row.get("evidence_layer") or "").strip()
    if evidence_layer:
        bounded["evidence_layer"] = evidence_layer
    source_id = str(row.get("source_id") or "").strip()
    if source_id:
        bounded["source_id"] = source_id
    for key in (
        "source_class",
        "structured_context_type",
        "product_family",
        "product_or_segment",
        "issuer_binding_status",
        "product_binding_status",
        "counterparty_binding_status",
        "entity_binding_claim_boundary",
    ):
        value = str(row.get(key) or "").strip()
        if value:
            bounded[key] = value
    entity_binding = row.get("entity_binding") if isinstance(row.get("entity_binding"), Mapping) else {}
    if entity_binding:
        source_entity_role = str(entity_binding.get("source_entity_role") or row.get("source_entity_role") or "").strip()
        if source_entity_role:
            bounded["source_entity_role"] = source_entity_role
        bounded["entity_binding"] = _sanitize_payload(
            {
                "issuer_binding_status": row.get("issuer_binding_status") or entity_binding.get("issuer_binding_status") or "",
                "product_binding_status": row.get("product_binding_status") or entity_binding.get("product_binding_status") or "",
                "counterparty_binding_status": row.get("counterparty_binding_status") or entity_binding.get("counterparty_binding_status") or "",
                "source_entity_role": source_entity_role,
                "issuer_matched_terms": _string_list(entity_binding.get("issuer_matched_terms"))[:6],
                "product_matched_terms": _string_list(entity_binding.get("product_matched_terms"))[:6],
                "counterparty_matched_terms": _string_list(entity_binding.get("counterparty_matched_terms"))[:6],
                "binding_claim_boundary": entity_binding.get("binding_claim_boundary") or row.get("entity_binding_claim_boundary") or "",
            }
        )
    elif str(row.get("source_entity_role") or "").strip():
        bounded["source_entity_role"] = str(row.get("source_entity_role") or "").strip()
    retrieval_route = str(row.get("retrieval_route") or "").strip()
    if retrieval_route:
        bounded["retrieval_route"] = retrieval_route
    if _row_is_semantic_supplement(row):
        vector_kind = str(row.get("vector_kind") or "").strip()
        vector_kinds = _string_list(row.get("vector_kinds"))
        if vector_kind and vector_kind not in vector_kinds:
            vector_kinds = [vector_kind, *vector_kinds]
        bounded.update(
            {
                "semantic_supplement": True,
                "semantic_route_role": str(row.get("semantic_route_role") or "semantic_recall_supplement"),
                "semantic_claim_scope": "filing_semantic_recall_supplement_only",
                "exact_value_authority": False,
            }
        )
        if vector_kind:
            bounded["vector_kind"] = vector_kind
        if vector_kinds:
            bounded["vector_kinds"] = vector_kinds
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
    if _row_source_family(row) == "company_product_evidence_graph":
        bounded.update(
            {
                "product_or_segment": str(row.get("product_or_segment") or row.get("product") or ""),
                "metric_family": str(row.get("metric_family") or row.get("metric") or ""),
                "unit": str(row.get("unit") or ""),
                "product_evidence_boundary": str(
                    row.get("runtime_use_boundary")
                    or "Use only rows marked runtime_fact_allowed as company-disclosed product facts; keep context/review/gap rows out of factual claims."
                ),
            }
        )
        if "exact_value_authority" not in bounded:
            bounded["exact_value_authority"] = promotion_status == "runtime_fact_allowed"
        if promotion_status != "runtime_fact_allowed":
            bounded["context_only"] = True
    if _row_source_family(row) == "derived_metric_layer":
        bounded.update(
            {
                "source_role": str(row.get("source_role") or "deterministic_derived_financial_metric"),
                "metric_family": str(row.get("metric_family") or row.get("derived_metric_family") or row.get("metric") or ""),
                "derived_metric_family": str(row.get("derived_metric_family") or row.get("metric_family") or ""),
                "formula_id": str(row.get("formula_id") or ""),
                "unit": str(row.get("unit") or ""),
                "unit_family": str(row.get("unit_family") or row.get("unit") or ""),
                "product_or_segment": str(row.get("product_or_segment") or ""),
                "input_evidence_refs": _string_list(row.get("input_evidence_refs"))[:12],
                "input_fact_ids": _string_list(row.get("input_fact_ids"))[:12],
                "derived_metric_boundary": str(
                    row.get("claim_boundary")
                    or "Derived metric is formula-bounded evidence from reconciled public filing facts; it cannot prove product demand, orders, market share, or customer deployment."
                ),
                "exact_value_authority": True,
                "context_only": False,
            }
        )
    if _row_source_family(row) == "public_source_context":
        bounded.update(
            {
                "underlying_source_id": str(row.get("source_id") or ""),
                "underlying_source_family": str(row.get("underlying_source_family") or row.get("primary_source_family") or ""),
                "public_source_boundary": str(
                    row.get("source_boundary")
                    or "Public source context is resolver/context/lead evidence only; it cannot prove company-reported product or financial facts."
                ),
                "context_only": True,
                "exact_value_authority": False,
            }
        )
    if _row_source_family(row) == "live_public_web_context":
        bounded.update(
            {
                "source_class": str(row.get("source_class") or ""),
                "snapshot_url": str(row.get("snapshot_url") or row.get("url") or ""),
                "web_source_boundary": str(
                    row.get("authority_boundary")
                    or "Allowlisted web snapshot rows are context/proxy evidence only; they cannot prove company product KPI, sales, share, inventory, margin, or profitability."
                ),
                "context_only": True,
                "exact_value_authority": False,
            }
        )
    trace_fields = {
        "evidence_requirement_id": str(row.get("evidence_requirement_id") or "").strip(),
        "selection_task_id": str(row.get("selection_task_id") or "").strip(),
        "selection_route_id": str(row.get("selection_route_id") or "").strip(),
        "route_id": str(row.get("route_id") or "").strip(),
    }
    for key, value in trace_fields.items():
        if value:
            bounded[key] = value
    for key in (
        "evidence_requirement_ids",
        "selection_task_ids",
        "selection_route_ids",
        "retrieval_routes",
        "selection_routes",
    ):
        values = _string_list(row.get(key))
        if values:
            bounded[key] = values[:12]
    return bounded


def _source_family_bundle_for_agent(agent_id: str, rows: list[Mapping[str, Any]], state: Mapping[str, Any]) -> dict[str, Any]:
    selected_families = _ordered_source_families(
        [_row_source_family(row) or str(row.get("source_family") or "") for row in rows],
        preferred_order=_specialist_required_source_families(agent_id),
    )
    counts = _bounded_row_distribution(rows).get("by_source_family") or {}
    semantic_rows = [row for row in rows if _row_is_semantic_supplement(row)]
    semantic_vector_kinds = _semantic_vector_kinds_from_rows(semantic_rows)
    context_only_families = [
        family
        for family in selected_families
        if family in {"market_snapshot", "industry_snapshot", "relationship_graph", "public_source_context", "live_public_web_context"}
        or (
            family == "company_product_evidence_graph"
            and any(_product_evidence_promotion_status(row) != "runtime_fact_allowed" for row in rows if _row_source_family(row) == family)
        )
    ]
    exact_authority_families = [
        family
        for family in selected_families
        if family in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}
        or family == "derived_metric_layer"
        or (
            family == "company_product_evidence_graph"
            and any(_product_evidence_promotion_status(row) == "runtime_fact_allowed" for row in rows if _row_source_family(row) == family)
        )
    ]
    bundle = {
        "schema_version": "sec_agent_source_family_bundle_v0.1",
        "agent_id": agent_id,
        "selection_policy": "specialist_role_source_family_selector_v0_1",
        "allowed_source_families": _specialist_required_source_families(agent_id),
        "available_source_families": _available_source_families_for_specialist(agent_id, state),
        "selected_source_families": selected_families,
        "row_count": len(rows),
        "row_counts_by_source_family": counts,
        "context_only_source_families": context_only_families,
        "exact_value_authority_source_families": exact_authority_families,
        "semantic_supplement_row_count": len(semantic_rows),
        "semantic_vector_kinds": semantic_vector_kinds,
        "forbidden_claim_scopes": _source_family_forbidden_claim_scopes(selected_families, semantic_row_count=len(semantic_rows)),
    }
    playbook_policy = _playbook_policy_from_state(state)
    if playbook_policy:
        bundle["selected_playbook_ids"] = _string_list(playbook_policy.get("selected_playbook_ids"))
        bundle["playbook_forbidden_claims"] = _string_list(playbook_policy.get("forbidden_claims"))[:16]
        bundle["playbook_commercial_gap_policy"] = dict(playbook_policy.get("commercial_gap_policy") or {})
        bundle["forbidden_claim_scopes"] = _dedupe(
            [*bundle["forbidden_claim_scopes"], *_string_list(playbook_policy.get("forbidden_claims"))]
        )
    if semantic_rows:
        bundle["semantic_supplement_policy"] = "typed_milvus_rows_are_sec_recall_supplements_not_exact_value_authority"
    return bundle


def _playbook_policy_from_state(state: Mapping[str, Any]) -> dict[str, Any]:
    reflection = state.get("plan_reflection_report") if isinstance(state.get("plan_reflection_report"), Mapping) else {}
    policy = reflection.get("playbook_policy") if isinstance(reflection.get("playbook_policy"), Mapping) else {}
    if policy:
        return dict(policy)
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    metadata = activation.get("metadata") if isinstance(activation.get("metadata"), Mapping) else {}
    policy = metadata.get("playbook_policy") if isinstance(metadata.get("playbook_policy"), Mapping) else {}
    return dict(policy)


def _ordered_source_families(families: list[str], *, preferred_order: list[str]) -> list[str]:
    unique = [family for family in _dedupe(str(family or "").strip() for family in families) if family]
    preferred = [family for family in preferred_order if family in unique]
    remaining = sorted(family for family in unique if family not in preferred)
    return [*preferred, *remaining]


def _semantic_vector_kinds_from_rows(rows: list[Mapping[str, Any]]) -> list[str]:
    kinds: list[str] = []
    for row in rows:
        vector_kind = str(row.get("vector_kind") or "").strip()
        if vector_kind:
            kinds.append(vector_kind)
        kinds.extend(_string_list(row.get("vector_kinds")))
    return _dedupe(kinds)


def _row_is_semantic_supplement(row: Mapping[str, Any]) -> bool:
    retrieval_route = str(row.get("retrieval_route") or "").strip()
    role = str(row.get("semantic_route_role") or "").strip()
    return (
        retrieval_route == "milvus_semantic"
        or role == "semantic_recall_supplement"
        or bool(str(row.get("vector_kind") or "").strip())
        or bool(_string_list(row.get("vector_kinds")))
    )


def _source_family_forbidden_claim_scopes(families: list[str], *, semantic_row_count: int) -> list[str]:
    forbidden: list[str] = []
    family_set = set(families)
    if "market_snapshot" in family_set:
        forbidden.append("market_snapshot_cannot_prove_company_reported_fundamentals_or_overwrite_sec_facts")
    if "industry_snapshot" in family_set:
        forbidden.append("industry_snapshot_cannot_prove_company_level_revenue_margin_customer_or_supplier_facts")
    if "relationship_graph" in family_set:
        forbidden.append("relationship_graph_is_scope_or_hypothesis_only_not_company_reported_fact")
    if "derived_metric_layer" in family_set:
        forbidden.append("derived_metric_layer_requires_input_refs_and_cannot_prove_product_orders_share_or_deployment")
    if "company_product_evidence_graph" in family_set:
        forbidden.append("company_product_evidence_graph_requires_runtime_fact_allowed_for_product_kpi_claims")
        forbidden.append("company_product_evidence_graph_review_context_and_gap_rows_are_not_facts")
    if "public_source_context" in family_set:
        forbidden.append("public_source_context_cannot_prove_company_reported_product_sales_market_share_or_profitability")
    if "live_public_web_context" in family_set:
        forbidden.append("live_public_web_context_requires_allowlisted_snapshot_and_is_context_only_by_default")
        forbidden.append("live_public_web_context_cannot_overwrite_sec_or_product_runtime_facts")
    if semantic_row_count:
        forbidden.append("milvus_semantic_rows_cannot_prove_exact_values_without_ledger_or_filing_quote")
    return forbidden


def _relationship_rows(plan: Any) -> list[dict[str, Any]]:
    if not isinstance(plan, Mapping):
        return []
    rows = []
    for index, relationship in enumerate(plan.get("relationships") or [], start=1):
        if not isinstance(relationship, Mapping):
            continue
        refs = _string_list(
            relationship.get("evidence_refs")
            or relationship.get("evidence_ref")
            or relationship.get("refs")
        )
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
    rows.extend(row for row in _evidence_fusion_authority_rows(state) if _row_source_family(row) == "relationship_graph")
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


def _focus_ticker_balanced_rows(
    rows: list[dict[str, Any]],
    *,
    focus_tickers: list[str],
    max_rows: int,
    source_families: set[str] | None = None,
    min_rows_per_ticker: int = 2,
) -> list[dict[str, Any]]:
    focus = [ticker.upper() for ticker in focus_tickers if ticker]
    if len(focus) < 2 or max_rows <= 0:
        return rows
    allowed_sources = source_families or set()
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    per_ticker_floor = max(1, min_rows_per_ticker)
    per_ticker_target = max(per_ticker_floor, max_rows // max(1, len(focus)))
    per_ticker_target = min(max_rows, per_ticker_target)
    for ticker in focus:
        ticker_rows = [
            row
            for row in rows
            if _row_ticker(row) == ticker and (not allowed_sources or _row_source_family(row) in allowed_sources)
        ]
        ticker_rows = _metric_and_source_diverse_rows(ticker_rows)
        for row in ticker_rows[:per_ticker_target]:
            if len(selected) >= max_rows:
                break
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


def _row_selection_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("evidence_ref") or row.get("id") or row.get("row_id") or "").strip(),
        _row_ticker(row),
        _row_source_family(row),
        str(row.get("metric") or row.get("metric_name") or "").strip(),
        str(row.get("summary") or "")[:240],
    )


def _product_row_priority(row: Mapping[str, Any]) -> tuple[int, str, str]:
    source_family = _row_source_family(row)
    ticker = _row_ticker(row)
    product_name = str(row.get("product_or_segment") or row.get("product") or "").strip().lower()
    text = " ".join(
        str(row.get(key) or "")
        for key in (
            "authority_type",
            "metric",
            "metric_name",
            "summary",
            "evidence_ref",
            "product",
            "product_family",
            "product_or_segment",
            "relationship_type",
            "edge_type",
            "source_class",
            "claim_scope",
        )
    ).lower()
    product_terms = (
        "accelerator",
        "architecture",
        "ai platform",
        "aiplatform",
        "blackwell",
        "cloud infrastructure",
        "cuda",
        "gemini",
        "gemma",
        "gpu",
        "gb200",
        "b200",
        "h100",
        "h200",
        "mi300",
        "instinct",
        "tpu",
        "ai server",
        "server",
        "product slot",
        "product_or_service_profile",
        "technical",
        "spec",
        "tensor",
        "tpu",
        "generation",
    )
    deployment_terms = (
        "customer",
        "deployment",
        "adoption",
        "configured",
        "distributed",
        "supplier",
        "supply",
        "partner",
        "contract",
        "award",
    )
    if product_name in {"copilot", "microsoft copilot", "github copilot", "copilot pro"} and ticker not in {"MSFT"}:
        return (7, ticker, text)
    if source_family == "company_product_evidence_graph" and any(term in text for term in product_terms):
        return (0, _row_ticker(row), text)
    if source_family == "company_product_evidence_graph":
        return (1, _row_ticker(row), text)
    if source_family in {"public_source_context", "live_public_web_context"} and any(term in text for term in product_terms):
        return (2, _row_ticker(row), text)
    if source_family in {"public_source_context", "live_public_web_context"}:
        return (3, _row_ticker(row), text)
    if source_family == "relationship_graph" and any(term in text for term in deployment_terms):
        return (4, _row_ticker(row), text)
    if source_family == "relationship_graph":
        return (5, _row_ticker(row), text)
    if source_family == "industry_snapshot":
        return (8, _row_ticker(row), text)
    return (9, _row_ticker(row), text)


def _product_ticker_balanced_rows(
    rows: list[dict[str, Any]],
    *,
    focus_tickers: list[str],
    max_rows: int,
    source_order: list[str],
) -> list[dict[str, Any]]:
    focus = [ticker.upper() for ticker in focus_tickers if ticker]
    if len(focus) < 2 or max_rows <= 0:
        return _balanced_rows_by_source(rows, source_order=source_order, max_rows=max_rows)

    source_rank = {source: index for index, source in enumerate(source_order)}
    allowed_sources = set(source_order)
    selected: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str, str, str, str]] = set()

    def add(row: dict[str, Any]) -> bool:
        if len(selected) >= max_rows:
            return False
        key = _row_selection_key(row)
        if key in selected_keys:
            return False
        selected.append(row)
        selected_keys.add(key)
        return True

    def ticker_candidates(ticker: str, sources: set[str] | None = None) -> list[dict[str, Any]]:
        candidates = [
            row
            for row in rows
            if _row_ticker(row) == ticker
            and _row_source_family(row) in allowed_sources
            and (not sources or _row_source_family(row) in sources)
        ]
        return sorted(candidates, key=lambda row: (_product_row_priority(row), source_rank.get(_row_source_family(row), 999)))

    ticker_target = max(3, min(8, max_rows // max(1, len(focus))))
    ticker_cap = max(ticker_target, max_rows // max(1, len(focus)))
    product_sources = {"company_product_evidence_graph", "public_source_context", "live_public_web_context"}

    # First guarantee issuer-specific product context per focus ticker when available.
    for ticker in focus:
        company_rows = ticker_candidates(ticker, {"company_product_evidence_graph"})
        for row in company_rows[: min(3, ticker_target)]:
            add(row)

    # Then add official/product-surface context before relationship/proxy rows.
    for ticker in focus:
        current = sum(1 for row in selected if _row_ticker(row) == ticker)
        for row in ticker_candidates(ticker, product_sources):
            if current >= min(4, ticker_target):
                break
            if add(row):
                current += 1

    # Add a small number of relationship/deployment rows per ticker as graph edges, not as substitutes for product facts.
    for ticker in focus:
        current = sum(1 for row in selected if _row_ticker(row) == ticker)
        relationship_added = 0
        for row in ticker_candidates(ticker, {"relationship_graph"}):
            if current >= ticker_target or relationship_added >= 2:
                break
            if add(row):
                current += 1
                relationship_added += 1

    # Fill each focus ticker up to its target before allowing non-focus rows.
    for ticker in focus:
        current = sum(1 for row in selected if _row_ticker(row) == ticker)
        for row in ticker_candidates(ticker):
            if current >= ticker_target:
                break
            if add(row):
                current += 1

    remaining = sorted(
        [row for row in rows if _row_source_family(row) in allowed_sources],
        key=lambda row: (
            0 if _row_ticker(row) in focus else 1,
            _product_row_priority(row),
            source_rank.get(_row_source_family(row), 999),
        ),
    )
    for row in remaining:
        ticker = _row_ticker(row)
        if ticker in focus and sum(1 for selected_row in selected if _row_ticker(selected_row) == ticker) >= ticker_cap:
            continue
        if not add(row):
            if len(selected) >= max_rows:
                break
    for row in remaining:
        if len(selected) >= max_rows:
            break
        add(row)
    return selected[:max_rows]


def _metric_and_source_diverse_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
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
    for family in (
        "company_product_evidence_graph",
        "market_snapshot",
        "industry_snapshot",
        "public_source_context",
        "company_authored_unaudited_sec_filing",
        "primary_sec_filing",
    ):
        for row in rows:
            if id(row) in selected_ids:
                continue
            if _row_source_family(row) == family:
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


def _focus_ticker_min_rows(*, max_rows: int, focus_ticker_count: int, default: int = 3) -> int:
    if focus_ticker_count <= 1:
        return 0
    return max(1, min(default, max_rows // max(1, focus_ticker_count * 3)))


def _ensure_min_source_family_rows(
    selected: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    source_family: str,
    min_rows: int,
    max_rows: int,
) -> list[dict[str, Any]]:
    if min_rows <= 0 or max_rows <= 0:
        return selected[:max_rows]
    selected = selected[:max_rows]
    current = sum(1 for row in selected if _row_source_family(row) == source_family)
    if current >= min_rows:
        return selected
    selected_ids = {id(row) for row in selected}
    replacement_indexes = [
        index
        for index in range(len(selected) - 1, -1, -1)
        if _row_source_family(selected[index]) != source_family
    ]
    for candidate in candidates:
        if current >= min_rows:
            break
        if _row_source_family(candidate) != source_family or id(candidate) in selected_ids:
            continue
        if len(selected) < max_rows:
            selected.append(candidate)
        elif replacement_indexes:
            replacement_index = replacement_indexes.pop(0)
            selected_ids.discard(id(selected[replacement_index]))
            selected[replacement_index] = candidate
        else:
            break
        selected_ids.add(id(candidate))
        current += 1
    return selected


def _ensure_min_requirement_rows(
    selected: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    requirement_id: str,
    min_rows: int,
    max_rows: int,
) -> list[dict[str, Any]]:
    if min_rows <= 0 or max_rows <= 0 or not requirement_id:
        return selected[:max_rows]
    selected = selected[:max_rows]
    current = sum(1 for row in selected if _row_has_any_requirement(row, {requirement_id}))
    if current >= min_rows:
        return selected
    selected_ids = {id(row) for row in selected}
    replacement_indexes = [
        index
        for index in range(len(selected) - 1, -1, -1)
        if not _row_has_any_requirement(selected[index], {requirement_id})
    ]
    for candidate in candidates:
        if current >= min_rows:
            break
        if not _row_has_any_requirement(candidate, {requirement_id}) or id(candidate) in selected_ids:
            continue
        if len(selected) < max_rows:
            selected.append(candidate)
        elif replacement_indexes:
            replacement_index = replacement_indexes.pop(0)
            selected_ids.discard(id(selected[replacement_index]))
            selected[replacement_index] = candidate
        else:
            break
        selected_ids.add(id(candidate))
        current += 1
    return selected


def _ensure_min_requirement_ticker_rows(
    selected: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    requirement_id: str,
    min_distinct_tickers: int,
    max_rows: int,
) -> list[dict[str, Any]]:
    if min_distinct_tickers <= 0 or max_rows <= 0 or not requirement_id:
        return selected[:max_rows]
    selected = selected[:max_rows]
    selected_tickers = {
        _row_ticker(row)
        for row in selected
        if _row_ticker(row) and _row_has_any_requirement(row, {requirement_id})
    }
    if len(selected_tickers) >= min_distinct_tickers:
        return selected

    selected_ids = {id(row) for row in selected}
    replacement_indexes = [
        index
        for index in range(len(selected) - 1, -1, -1)
        if not _row_has_any_requirement(selected[index], {requirement_id})
    ]
    for candidate in candidates:
        ticker = _row_ticker(candidate)
        if len(selected_tickers) >= min_distinct_tickers:
            break
        if (
            not ticker
            or ticker in selected_tickers
            or id(candidate) in selected_ids
            or not _row_has_any_requirement(candidate, {requirement_id})
        ):
            continue
        if len(selected) < max_rows:
            selected.append(candidate)
        elif replacement_indexes:
            replacement_index = replacement_indexes.pop(0)
            selected_ids.discard(id(selected[replacement_index]))
            selected[replacement_index] = candidate
        else:
            break
        selected_ids.add(id(candidate))
        selected_tickers.add(ticker)
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
            "public_source_context",
            "company_product_evidence_graph",
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
    fused_counts = _fusion_source_family_counts(state)
    return {
        "run_id": state.get("run_id") or "",
        "execution_mode": _execution_mode_from_state(state),
        "allowed_source_families": list(activation.get("allowed_source_families") or []),
        "evidence_requirement_count": len(evidence_plan.get("requirements") or []) if isinstance(evidence_plan, Mapping) else 0,
        "context_row_count": len(state.get("context_rows") or [])
        or sum(fused_counts.get(family, 0) for family in ("company_authored_unaudited_sec_filing", "relationship_graph")),
        "ledger_row_count": len(state.get("runtime_ledger_rows") or []) or fused_counts.get("primary_sec_filing", 0),
        "market_row_count": len(state.get("market_snapshot_rows") or []) or fused_counts.get("market_snapshot", 0),
        "industry_row_count": len(state.get("industry_snapshot_rows") or []) or fused_counts.get("industry_snapshot", 0),
        "fusion_authority_row_count": len(_evidence_fusion_authority_rows(state)),
        "default_bounded_evidence_row_budget": _data_view_max_rows_for_mode(_execution_mode_from_state(state)),
        "relationship_summary_row_budget": _relationship_summary_max_rows(state),
    }


def _evidence_fusion_authority_rows(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    bundle = state.get("evidence_fusion_bundle") if isinstance(state.get("evidence_fusion_bundle"), Mapping) else {}
    return _row_dicts(bundle.get("authority_rows"))


def _fusion_source_family_counts(state: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in _evidence_fusion_authority_rows(state):
        family = _row_source_family(row)
        if not family:
            continue
        counts[family] = counts.get(family, 0) + 1
    return counts


def _fusion_rows_for_agent_data_view(agent_id: str, state: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project compact fused authority rows into role-specific specialist input rows.

    Stepwise P33 artifacts intentionally compact raw context/ledger rows into
    evidence_fusion_bundle.authority_rows. Specialist input views must consume
    that accepted fused bundle instead of treating compact state as empty.
    """
    rows = _evidence_fusion_authority_rows(state)
    if not rows:
        return []
    agent = str(agent_id or "")
    if agent == "fundamental_analyst":
        return [
            row
            for row in rows
            if _row_source_family(row) in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}
            and (
                _row_has_any_requirement(row, {"req_dell_margin_quality", "req_hyperscaler_capex", "req_supply_chain"})
                or str(row.get("claim_scope") or "") in {"reported_financial_fact", "company_disclosed_context_only"}
            )
        ]
    if agent == "product_technology_analyst":
        return [
            row
            for row in rows
            if (
                _row_has_any_requirement(row, {"req_accelerator_architecture", "req_customer_deployment"})
                and _row_relevant_for_requirement({"requirement_id": "req_accelerator_architecture"}, row)
            )
            or _row_source_family(row)
            in {"company_product_evidence_graph", "public_source_context", "live_public_web_context"}
        ]
    if agent == "industry_supply_chain_analyst":
        return [
            row
            for row in rows
            if _row_source_family(row) in {"relationship_graph", "industry_snapshot"}
            or _row_has_any_requirement(row, {"req_supply_chain", "req_customer_deployment"})
        ]
    if agent == "market_valuation_analyst":
        return [
            row
            for row in rows
            if _row_source_family(row) == "market_snapshot"
            or _row_has_any_requirement(row, {"req_hyperscaler_capex"})
        ]
    if agent == "risk_counterevidence_analyst":
        return [
            row
            for row in rows
            if bool(row.get("gap_only"))
            or _row_has_any_requirement(
                row,
                {
                    "req_dell_margin_quality",
                    "req_hyperscaler_capex",
                    "req_supply_chain",
                    "req_customer_deployment",
                    "req_accelerator_architecture",
                },
            )
            or str(row.get("claim_scope") or "") in {"bounded_gap_only", "context_or_proxy_only", "scope_or_hypothesis_only"}
            or _row_source_family(row) in {"market_snapshot", "industry_snapshot", "relationship_graph"}
        ]
    if agent in {"verifier", "coverage_reflection", "judgment_plan_aggregator"}:
        return rows
    return []


def _row_has_any_requirement(row: Mapping[str, Any], requirement_ids: set[str]) -> bool:
    values: list[str] = []
    values.extend(_string_list(row.get("evidence_requirement_ids")))
    values.extend(_string_list(row.get("evidence_requirement_id")))
    values.extend(_string_list(row.get("selection_task_ids")))
    values.extend(_string_list(row.get("task_id")))
    return bool(set(values) & requirement_ids)


def _row_relevant_for_requirement(requirement: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    req_keys = _requirement_keys(requirement) | _requirement_keys(row)
    if "req_accelerator_architecture" not in req_keys:
        return True
    if _row_source_family(row) != "industry_snapshot":
        return True
    return _row_matches_product_architecture_terms(row)


def _row_matches_product_architecture_terms(row: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "").lower()
        for key in (
            "evidence_ref",
            "metric",
            "metric_name",
            "summary",
            "title",
            "source_name",
            "industry",
            "vertical",
            "product_family",
            "claim_scope",
        )
    )
    terms = (
        "accelerator",
        "gpu",
        "tpu",
        "h100",
        "h200",
        "b200",
        "gb200",
        "blackwell",
        "mi300",
        "cuda",
        "ai server",
        "server oem",
        "data center",
        "datacenter",
        "hyperscaler",
        "semiconductor",
        "semi",
        "foundry",
        "tsmc",
        "hbm",
        "cowos",
        "chip",
        "asic",
    )
    return any(term in text for term in terms)


def _source_inventory_for_agent_view(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    schema_version = str(value.get("schema_version") or "")
    if schema_version.startswith("project_source_inventory_"):
        return inventory_brief(dict(value))
    return dict(value)


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
    focus_tickers = _string_list(plan.get("focus_tickers")) or _focus_tickers_from_state(state)
    expanded_tickers = _string_list(plan.get("expanded_tickers")) or _search_scope_tickers_from_state(state, focus_tickers=focus_tickers)
    return {
        "scope_mode": plan.get("scope_mode") or "",
        "focus_tickers": focus_tickers,
        "expanded_tickers": expanded_tickers,
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
        payload["selection_policy"] = "source_and_focus_ticker_balanced_without_relationship_graph"
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


def _product_intelligence_autoload_arg(state: Mapping[str, Any]) -> bool | None:
    if "product_intelligence_runtime_autoload" in state:
        return bool(state.get("product_intelligence_runtime_autoload"))
    return None


def _product_intelligence_context_candidate_budget(*, max_rows: int, focus_ticker_count: int) -> int:
    multiplier = max(4, focus_ticker_count + 2)
    return max(32, max_rows * multiplier)


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
    runtime_family = str(row.get("runtime_source_family") or "").strip()
    tier = str(row.get("source_tier") or "").strip()
    if family in {"company_product_evidence_graph", "public_source_context"}:
        return family
    if runtime_family in {"company_product_evidence_graph", "public_source_context"}:
        return runtime_family
    if tier == "industry_snapshot" or family.startswith("industry_"):
        return "industry_snapshot"
    return family or tier


def _product_evidence_promotion_status(row: Mapping[str, Any]) -> str:
    return str(row.get("promotion_status") or row.get("runtime_promotion_status") or row.get("node_promotion_status") or "").strip()


def _row_ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or row.get("company") or "").upper().strip()


def _bounded_row_distribution(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "sec_agent_bounded_row_distribution_v0.1",
        "row_count": len(rows),
        "by_ticker": _count_by_key(rows, "ticker"),
        "by_source_family": _count_by_key(rows, "source_family"),
        "by_ticker_source_family": _count_by_composite(rows, ("ticker", "source_family")),
        "by_form_type": _count_by_key(rows, "form_type"),
        "by_metric": _count_by_key(rows, "metric"),
        "by_source_entity_role": _count_by_key(rows, "source_entity_role"),
        "by_issuer_binding_status": _count_by_key(rows, "issuer_binding_status"),
        "by_product_binding_status": _count_by_key(rows, "product_binding_status"),
        "by_counterparty_binding_status": _count_by_key(rows, "counterparty_binding_status"),
    }


def _count_by_key(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "").strip() or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _count_by_composite(rows: list[Mapping[str, Any]], keys: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        parts = [str(row.get(key) or "").strip() or "unknown" for key in keys]
        value = "|".join(parts)
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


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


def _payload_digest(value: Mapping[str, Any]) -> str:
    clean = _sanitize_payload(value)
    text = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


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


def _normalize_web_scope_registry(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        return default_web_source_scope_registry()
    if isinstance(value.get("policies"), Mapping):
        policies = {str(policy_id): dict(policy) for policy_id, policy in value.get("policies", {}).items() if isinstance(policy, Mapping)}
    else:
        policies = {}
        for item in value.get("policies") or value.get("web_scope_policies") or []:
            if not isinstance(item, Mapping):
                continue
            policy_id = str(item.get("policy_id") or item.get("web_scope_policy_id") or "").strip()
            if policy_id:
                policies[policy_id] = dict(item)
    if not policies:
        default = default_web_source_scope_registry()
        policies = dict(default["policies"])
    return {
        **dict(value),
        "schema_version": str(value.get("schema_version") or WEB_SOURCE_SCOPE_REGISTRY_SCHEMA_VERSION),
        "policies": policies,
    }


def _web_claim_types(request: Mapping[str, Any]) -> list[str]:
    return [
        item.strip().lower()
        for item in _string_list(
            request.get("claim_types")
            or request.get("claim_type")
            or request.get("allowed_claim_types")
            or request.get("claim_scope")
        )
        if item.strip()
    ]


def _domain_from_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"https://{text}")
    return _normalize_domain(parsed.netloc or parsed.path.split("/")[0])


def _normalize_domain(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "://" in text or "/" in text:
        return _domain_from_url(text)
    text = text.split("@")[-1].split(":")[0].strip(".")
    if text.startswith("www."):
        text = text[4:]
    return text


def _web_domain_allowed(domain: str, policies: list[Mapping[str, Any]], request: Mapping[str, Any]) -> bool:
    domain = _normalize_domain(domain)
    if not domain:
        return False
    allowed_domains: list[str] = []
    for policy in policies:
        allowed_domains.extend(_string_list(policy.get("allowed_domains")))
        if policy.get("requires_verified_company_domain") and _bool_value(request.get("company_domain_verified")):
            allowed_domains.extend(_string_list(request.get("company_domains") or request.get("verified_company_domains") or request.get("allowed_domains")))
    allowed_domains.extend(_string_list(request.get("registry_allowed_domains") or request.get("web_scope_allowed_domains")))
    return any(_domain_matches(domain, allowed) for allowed in allowed_domains)


def _domain_matches(domain: str, allowed_domain: Any) -> bool:
    allowed = _normalize_domain(allowed_domain)
    if not domain or not allowed:
        return False
    return domain == allowed or domain.endswith(f".{allowed}")


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
    if tool_name == "sec_milvus_semantic_search":
        return {
            "status": "dry_run",
            "context_rows": [{**row, "source_family": "primary_sec_filing", "vector_kind": "narrative_chunk"}],
            "vector_kind_counts": {"narrative_chunk": 1},
            "typed_filter_required": True,
            "semantic_route_role": "semantic_recall_supplement",
            "artifact_refs": [],
        }
    if tool_name == "sec_query_exact_value_ledger":
        return {"status": "dry_run", "ledger_rows": [row], "artifact_refs": []}
    if tool_name == "market_get_snapshot":
        return {"status": "dry_run", "market_rows": [row], "snapshot_id": "dry_run", "as_of_date": "dry_run", "artifact_refs": []}
    if tool_name == "industry_get_snapshot":
        return {"status": "dry_run", "industry_rows": [row], "artifact_refs": []}
    if tool_name == "web_evidence_snapshot":
        snapshot_id = f"dry_web_{_slug(route.get('route_id') or route.get('url') or 'snapshot')}"
        return {
            "schema_version": WEB_EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
            "status": "dry_run",
            "snapshot_id": snapshot_id,
            "as_of_datetime": "dry_run",
            "source_class": str(route.get("source_class") or "major_financial_news"),
            "web_scope_policy_ids": _string_list(route.get("web_scope_policy_ids")),
            "context_rows": [
                {
                    **row,
                    "source_family": "live_public_web_context",
                    "source_class": str(route.get("source_class") or "major_financial_news"),
                    "web_scope_policy_ids": _string_list(route.get("web_scope_policy_ids")),
                    "claim_types": _string_list(route.get("claim_types") or route.get("claim_type")) or ["public_reporting_lead"],
                    "snapshot_id": snapshot_id,
                    "snapshot_url": str(route.get("snapshot_url") or route.get("url") or "https://reuters.com"),
                    "citation": {"url": str(route.get("snapshot_url") or route.get("url") or "https://reuters.com"), "title": "dry run web snapshot"},
                    "context_only": True,
                    "exact_value_authority": False,
                }
            ],
            "artifact_refs": [],
        }
    return {"status": "dry_run", "rows": [row], "artifact_refs": []}
