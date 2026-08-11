from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SOURCE_COVERAGE_GATE_SCHEMA_VERSION = "finsight_source_coverage_gate_v0_1"
SOURCE_COVERAGE_MATRIX_SCHEMA_VERSION = "finsight_source_coverage_matrix_v0_1"


READY_STATUSES = {"exact_authority_ready", "runtime_ready_context"}
ROUTE_CANDIDATE_STATUSES = {
    "exact_authority_ready",
    "runtime_ready_context",
    "structured_not_promoted",
    "staging_parser_gate_pending",
    "crawlable_not_parsed_or_not_routed",
}
NOT_READY_STATUSES = {"not_registered", "missing_runtime_route", "not_connected", "blocked_by_auth_or_policy"}
STRUCTURED_FACT_STATUSES = {"bounded_context_fact_materialized", "context_rows_ready", "candidate_rows_ready"}
STRONG_BINDING_STATUSES = {
    "issuer_mentioned_in_snapshot",
    "company_domain_bound",
    "issuer_subsidiary_official_domain_bound",
    "product_mentioned_in_snapshot",
    "technology_topic_bound",
    "counterparty_mentioned_in_snapshot",
    "relationship_context_candidate",
    "counterparty_keyword_context_candidate",
    "macro_exposure_bridge_context",
    "family_assignment_exposure_context",
}


SOURCE_CLASS_TO_SOURCE_ID = {
    "company_product_page": "company_product_pages",
    "company_product_documentation": "company_product_pages",
    "company_support_documentation": "company_product_pages",
    "company_reported_product_operating_metric": "company_reported_product_operating_metrics",
    "company_reported_structured_financial_fact": "sec_financial_statement_data_sets",
    "company_ir_material": "company_ir_reports",
    "company_earnings_material": "company_ir_reports",
    "local_exchange_filings": "company_ir_reports",
    "regulator_filings": "company_ir_reports",
    "sec_fpi_filings": "sec_edgar_apis",
    "sec_company_submissions": "sec_edgar_apis",
    "sec_offering_filing": "sec_edgar_apis",
    "mainstream_financial_news_article": "mainstream_financial_news",
    "supplier_customer_official_news": "supplier_customer_official_news",
    "company_customer_page": "supplier_customer_official_news",
    "company_supplier_page": "supplier_customer_official_news",
    "official_partner_directory": "supplier_customer_official_news",
    "industry_association_dataset": "industry_association_reports",
    "ecommerce_major_platform": "ecommerce_major_platforms",
    "official_app_store_or_marketplace": "app_store_rankings",
    "developer_ecosystem_snapshot": "developer_ecosystem_github_npm_pypi_huggingface",
    "public_tender_or_contract_portal": "public_tenders_contracts_orders",
    "job_posting_snapshot": "job_postings_hiring_signals",
    "channel_pricing_snapshot": "channel_pricing_quotations",
    "channel_distributor_locator": "channel_distributor_locator",
    "channel_distributor_snapshot": "channel_distributor_locator",
    "platform_review_or_ranking_snapshot": "platform_reviews_rankings_downloads",
    "official_social_account": "official_social_accounts",
}


@dataclass(frozen=True)
class SourceCoverageRequirement:
    requirement_id: str
    dimension: str
    source_ids: tuple[str, ...]
    layer_ids: tuple[str, ...]
    specialist_roles: tuple[str, ...]
    claim_boundary: str
    next_action: str
    min_ready_sources: int = 1
    min_observed_rows: int = 1
    min_parser_rows: int = 1
    min_entity_bound_rows: int = 0
    min_visible_rows: int = 1
    entity_binding_kinds: tuple[str, ...] = ()


def _req(
    requirement_id: str,
    dimension: str,
    source_ids: Sequence[str],
    layer_ids: Sequence[str],
    specialist_roles: Sequence[str],
    claim_boundary: str,
    next_action: str,
    *,
    min_entity_bound_rows: int = 0,
    entity_binding_kinds: Sequence[str] = (),
) -> SourceCoverageRequirement:
    return SourceCoverageRequirement(
        requirement_id=requirement_id,
        dimension=dimension,
        source_ids=tuple(source_ids),
        layer_ids=tuple(layer_ids),
        specialist_roles=tuple(specialist_roles),
        claim_boundary=claim_boundary,
        next_action=next_action,
        min_entity_bound_rows=min_entity_bound_rows,
        entity_binding_kinds=tuple(entity_binding_kinds),
    )


COMMON_REQUIREMENTS = {
    "primary_company_disclosure": _req(
        "primary_company_disclosure",
        "fundamentals",
        ("sec_edgar_apis", "sec_financial_statement_data_sets", "company_ir_reports", "company_reported_product_operating_metrics"),
        ("L1",),
        ("fundamental_analyst", "product_technology_analyst", "capital_ownership_macro_analyst"),
        "Company-disclosed financial, filing, and product operating facts only after parser/period/unit/citation gates.",
        "Use SEC/FSD for US issuers and official IR/local filing route for non-US issuers before exposing a filing gap.",
    ),
    "official_product_surface": _req(
        "official_product_surface",
        "product_and_production",
        ("company_product_pages", "company_reported_product_operating_metrics", "sec_product_taxonomy_normalized"),
        ("L1", "L2"),
        ("product_technology_analyst",),
        "Official product existence, specs, positioning, and company-disclosed product KPIs; no inferred sales/share.",
        "Fetch official product/IR pages, parse product/spec rows, and bind issuer/product before product section judgment.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "product"),
    ),
    "trusted_external_context": _req(
        "trusted_external_context",
        "competition_and_market_position",
        ("mainstream_financial_news", "industry_association_reports", "official_social_accounts"),
        ("L2",),
        ("market_valuation_analyst", "risk_counterevidence_analyst", "industry_supply_chain_analyst"),
        "Trusted event, management-statement, and industry context only; not company exact values unless independently authoritative.",
        "Use trusted publisher or official association routes before declaring external context unavailable.",
    ),
    "macro_official_context": _req(
        "macro_official_context",
        "macro_and_industry",
        ("fred_api", "fred_graph_csv", "bls_public_api", "bea_data_api", "census_data_api", "eia_open_data"),
        ("L2",),
        ("market_valuation_analyst", "capital_ownership_macro_analyst", "industry_supply_chain_analyst"),
        "Official macro/industry context and demand proxy only; no issuer revenue or share inference.",
        "Resolve industry driver/source mapping and keep company exposure bridge explicit.",
    ),
}


REQUIREMENT_TEMPLATES = {
    **COMMON_REQUIREMENTS,
    "supply_chain_official_relationship": _req(
        "supply_chain_official_relationship",
        "industry_supply_chain",
        ("supplier_customer_official_news", "public_tenders_contracts_orders"),
        ("L2", "L3"),
        ("industry_supply_chain_analyst", "product_technology_analyst"),
        "Official supplier/customer/partner or public order existence context; no shipment, allocation, or order-volume promotion.",
        "Fetch supplier/customer official news and public tender/order routes, then bind issuer/counterparty.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "counterparty"),
    ),
    "official_customer_order_or_deployment_event": _req(
        "official_customer_order_or_deployment_event",
        "industry_supply_chain",
        ("supplier_customer_official_news",),
        ("L2", "L3"),
        ("industry_supply_chain_analyst", "product_technology_analyst", "market_valuation_analyst"),
        (
            "Official issuer/customer/supplier announcement event fact: customer/order/project/deployment/agreement "
            "existence, named counterparty, product/project, date/scale fields where present. It is not procurement "
            "award exact, revenue exact, backlog exact, ASP, shipment, sell-through, or share authority."
        ),
        "Fetch company/customer/supplier official announcement pages and bind issuer, counterparty, product/project, and event fields.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "counterparty", "product"),
    ),
    "technical_product_spec": _req(
        "technical_product_spec",
        "product_and_production",
        ("official_product_datasheets", "official_product_spec_pages", "official_nvidia_product_page"),
        ("L2",),
        ("product_technology_analyst", "industry_supply_chain_analyst"),
        "Official product specification, configuration, architecture, model, or feature facts only; no sales, ASP, share, revenue, inventory, or sell-through inference.",
        "Fetch official product pages, datasheets, catalogs, or technical docs; parse spec name/value/unit/model/version and bind issuer/product.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "product"),
    ),
    "product_generation_edge": _req(
        "product_generation_edge",
        "product_and_production",
        ("official_product_datasheets", "official_product_spec_pages", "official_nvidia_product_page"),
        ("L2",),
        ("product_technology_analyst",),
        "Official product-generation or architecture transition context only; no automatic demand, revenue, margin, or share inference.",
        "Parse prior/current product model, generation label, launch/version context, and comparable improvement dimensions.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "product"),
    ),
    "product_benchmark_proxy": _req(
        "product_benchmark_proxy",
        "product_and_production",
        ("official_product_benchmark_page", "trusted_benchmark_database", "official_nvidia_product_page"),
        ("L2", "L3"),
        ("product_technology_analyst", "market_valuation_analyst"),
        "Benchmark or performance proxy context only; supports product capability comparison, not sales, revenue, share, or adoption exact.",
        "Parse benchmark name/version/workload, metric/value/unit, product model, competitor/comparable when present, and citation.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "product"),
    ),
    "customer_deployment_proxy": _req(
        "customer_deployment_proxy",
        "industry_supply_chain",
        ("official_customer_deployment_news", "official_nvidia_customer_deployment_news", "supplier_customer_official_news"),
        ("L2", "L3"),
        ("industry_supply_chain_analyst", "product_technology_analyst", "market_valuation_analyst"),
        "Official customer deployment context only; no order value, revenue contribution, backlog, shipment, ASP, sell-through, or share inference.",
        "Parse customer, supplier, product/family, deployment/project, event date, scale text where present, and citation.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "counterparty", "product"),
    ),
    "capital_structure_disclosure": _req(
        "capital_structure_disclosure",
        "capital_ownership_macro",
        ("sec_annual_debt_footnote_chunk", "sec_financial_statement_data_sets", "sec_offering_filing"),
        ("L1",),
        ("capital_ownership_macro_analyst", "fundamental_analyst", "market_valuation_analyst"),
        "Company-disclosed debt, credit facility, cash/debt/net-debt, lease, convertible, or offering context only; no undisclosed financing terms or market-implied cost inference.",
        "Parse SEC debt footnotes, FSD capital structure rows, offering filings, or company credit agreements with period, amount, maturity/rate/covenant fields where present.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer",),
    ),
    "lagged_ownership_context": _req(
        "lagged_ownership_context",
        "capital_ownership_macro",
        ("sec_ownership_and_13f", "sec_13f_bulk"),
        ("L3",),
        ("capital_ownership_macro_analyst", "market_valuation_analyst", "risk_counterevidence_analyst"),
        "13F/ownership disclosure context only; lagged long-position data cannot be described as real-time fund flow, buying pressure, or current investor demand.",
        "Parse SEC 13F/ownership rows with investor, issuer/security, report period, filing date, lag policy, shares/value, and not-realtime flag.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer",),
    ),
    "working_capital_liquidity": _req(
        "working_capital_liquidity",
        "capital_ownership_macro",
        ("sec_financial_statement_data_sets", "sec_companyfacts_api"),
        ("L1",),
        ("capital_ownership_macro_analyst", "fundamental_analyst", "market_valuation_analyst"),
        "Company-reported working-capital/liquidity statement facts only; no product demand, ASP, market share, channel inventory, sell-through, backlog, or undisclosed financing inference.",
        "Parse SEC CompanyFacts/FSD AR, inventory, AP, deferred revenue, current assets/liabilities, short-term debt, cash, CFO, capex, and financing cash flow with value/unit/period/citation.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer",),
    ),
    "securities_offering_filing_event": _req(
        "securities_offering_filing_event",
        "capital_ownership_macro",
        ("sec_offering_filing_metadata", "sec_submissions_metadata"),
        ("L1",),
        ("capital_ownership_macro_analyst", "market_valuation_analyst", "risk_counterevidence_analyst"),
        "SEC offering/registration filing-event metadata only; no offering amount, security terms, dilution, coupon, maturity, or proceeds without source-specific filing parser.",
        "Parse SEC submissions S-1/S-3/F-1/F-3/424B/FWP filing event with issuer, form, accession, filing date, primary document and citation.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer",),
    ),
    "insider_transaction_filing_event": _req(
        "insider_transaction_filing_event",
        "capital_ownership_macro",
        ("sec_form_3_4_5_metadata", "sec_submissions_metadata"),
        ("L1",),
        ("capital_ownership_macro_analyst", "market_valuation_analyst", "risk_counterevidence_analyst"),
        "SEC Form 3/4/5/144 filing-event metadata only; no insider shares, transaction price, ownership change, or management intent without XML parser.",
        "Parse SEC submissions Form 3/4/5/144 filing event with issuer, form, accession, filing date, primary document and citation.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer",),
    ),
    "beneficial_ownership_filing_event": _req(
        "beneficial_ownership_filing_event",
        "capital_ownership_macro",
        ("sec_schedule_13d_13g_metadata", "sec_submissions_metadata"),
        ("L1",),
        ("capital_ownership_macro_analyst", "market_valuation_analyst", "risk_counterevidence_analyst"),
        "SEC Schedule 13D/13G filing-event metadata only; no beneficial ownership percentage, activist thesis, current buying pressure, or complete ownership without schedule parser.",
        "Parse SEC submissions Schedule 13D/13G filing event with issuer, form, accession, filing date, primary document and citation.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer",),
    ),
    "proxy_governance_filing_event": _req(
        "proxy_governance_filing_event",
        "capital_ownership_macro",
        ("sec_proxy_governance_metadata", "sec_submissions_metadata"),
        ("L1",),
        ("capital_ownership_macro_analyst", "market_valuation_analyst", "risk_counterevidence_analyst"),
        "SEC proxy/governance filing-event metadata only; no buyback amount, compensation outcome, voting result, or governance judgment without text/table parser.",
        "Parse SEC submissions proxy filing event with issuer, form, accession, filing date, primary document and citation.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer",),
    ),
    "developer_ecosystem_proxy": _req(
        "developer_ecosystem_proxy",
        "product_and_production",
        ("developer_ecosystem_github_npm_pypi_huggingface",),
        ("L3",),
        ("product_technology_analyst", "industry_supply_chain_analyst"),
        "Developer ecosystem activity or technical attention proxy only; not product revenue, sales, or moat proof.",
        "Route GitHub/npm/PyPI/HuggingFace through source-specific parser and project-to-issuer resolver.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "product"),
    ),
    "channel_offer_proxy": _req(
        "channel_offer_proxy",
        "product_and_production",
        ("ecommerce_major_platforms", "channel_pricing_quotations", "channel_distributor_locator"),
        ("L3",),
        ("product_technology_analyst", "market_valuation_analyst"),
        "Public channel price/configuration/availability/distributor presence proxy only; no ASP, sell-through, inventory, or market-share inference.",
        "Route e-commerce/channel/distributor snapshots through offer or locator parser and SKU/product resolver.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "product"),
    ),
    "app_rank_store_proxy": _req(
        "app_rank_store_proxy",
        "product_and_production",
        ("app_store_rankings",),
        ("L3",),
        ("product_technology_analyst", "market_valuation_analyst"),
        "App rank/review/download proxy only; not app revenue or company market share.",
        "Resolve app-to-issuer mapping and snapshot ranking/review metadata.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "product"),
    ),
    "platform_review_proxy": _req(
        "platform_review_proxy",
        "product_and_production",
        ("platform_reviews_rankings_downloads",),
        ("L3",),
        ("product_technology_analyst", "market_valuation_analyst", "risk_counterevidence_analyst"),
        "Public review/ranking/download context only; directional attention signal, not sales proof.",
        "Parse platform ranking/review pages with timestamp and entity/product binding.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "product"),
    ),
    "hiring_capacity_proxy": _req(
        "hiring_capacity_proxy",
        "product_and_production",
        ("job_postings_hiring_signals",),
        ("L3",),
        ("product_technology_analyst", "industry_supply_chain_analyst", "risk_counterevidence_analyst"),
        "Hiring/capacity/geography signal only; weak directional evidence unless corroborated.",
        "Parse company/job-board postings and role taxonomy; bind issuer/product/geography.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "product"),
    ),
    "public_order_proxy": _req(
        "public_order_proxy",
        "industry_supply_chain",
        ("public_tenders_contracts_orders",),
        ("L2", "L3"),
        ("industry_supply_chain_analyst", "product_technology_analyst", "capital_ownership_macro_analyst"),
        "Public tender/award/order snapshot only; no total company sales, backlog, shipment, or share inference.",
        "Parse jurisdiction portal awards/status, then bind issuer/counterparty/product and award fields.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "counterparty"),
    ),
    "regulated_product_context": _req(
        "regulated_product_context",
        "product_and_production",
        ("clinicaltrials_api", "openfda_api", "cms_public_data", "fda_animal_drugs_api"),
        ("L2",),
        ("product_technology_analyst", "industry_supply_chain_analyst", "risk_counterevidence_analyst"),
        "Healthcare regulatory, trial, payer, and procedure context only; not approval success, utilization share, or sales proof.",
        "Resolve sponsor/product/condition/application/procedure before promotion to healthcare context.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "product"),
    ),
    "auto_product_identity_context": _req(
        "auto_product_identity_context",
        "product_and_production",
        ("nhtsa_vpic_api", "company_product_pages"),
        ("L2",),
        ("product_technology_analyst", "risk_counterevidence_analyst"),
        "Vehicle manufacturer/make/model/VIN or official model-page identity context only; no sales volume or profitability proof.",
        "Resolve NHTSA manufacturer/make/model-year where applicable; for non-US issuers, use official model/product pages with issuer/product binding.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "product"),
    ),
    "financial_regulatory_context": _req(
        "financial_regulatory_context",
        "macro_and_industry",
        ("fdic_bankfind_api", "fred_api", "fred_graph_csv"),
        ("L2", "L3"),
        ("fundamental_analyst", "capital_ownership_macro_analyst", "industry_supply_chain_analyst"),
        "Bank regulatory and macro context only until institution-to-listed-issuer resolver passes.",
        "Resolve FDIC institution/subsidiary to listed issuer and keep rate/credit context separated from company-reported facts.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer",),
    ),
    "energy_utility_context": _req(
        "energy_utility_context",
        "macro_and_industry",
        ("eia_open_data", "fred_api", "fred_graph_csv"),
        ("L2", "L3"),
        ("industry_supply_chain_analyst", "capital_ownership_macro_analyst", "product_technology_analyst"),
        "Energy/utility official operating context only; no single-company revenue or margin inference.",
        "Resolve route/series/asset mapping and company exposure bridge before using EIA/FRED context.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "product"),
    ),
    "technology_research_proxy": _req(
        "technology_research_proxy",
        "product_and_production",
        ("openalex_api", "patentsview_api", "official_technical_document"),
        ("L3",),
        ("product_technology_analyst",),
        "Research/IP signal only; not product launch, sales, or durable moat proof.",
        "Resolve assignee/institution/topic to issuer/product and keep proxy boundary explicit.",
        min_entity_bound_rows=1,
        entity_binding_kinds=("issuer", "product"),
    ),
}


STRICT_REQUIREMENT_ROLE_MATCH = {
    "technical_product_spec",
    "product_generation_edge",
    "product_benchmark_proxy",
    "customer_deployment_proxy",
    "official_customer_order_or_deployment_event",
    "capital_structure_disclosure",
    "lagged_ownership_context",
    "working_capital_liquidity",
    "securities_offering_filing_event",
    "insider_transaction_filing_event",
    "beneficial_ownership_filing_event",
    "proxy_governance_filing_event",
}


INDUSTRY_REQUIREMENT_IDS = {
    "generic_public_research": (
        "primary_company_disclosure",
        "official_product_surface",
        "trusted_external_context",
        "macro_official_context",
    ),
    "semiconductors_hardware": (
        "primary_company_disclosure",
        "official_product_surface",
        "trusted_external_context",
        "supply_chain_official_relationship",
        "developer_ecosystem_proxy",
        "channel_offer_proxy",
        "public_order_proxy",
        "hiring_capacity_proxy",
        "macro_official_context",
        "technology_research_proxy",
    ),
    "consumer_electronics": (
        "primary_company_disclosure",
        "official_product_surface",
        "trusted_external_context",
        "channel_offer_proxy",
        "app_rank_store_proxy",
        "platform_review_proxy",
        "hiring_capacity_proxy",
        "macro_official_context",
    ),
    "software_saas": (
        "primary_company_disclosure",
        "official_product_surface",
        "trusted_external_context",
        "developer_ecosystem_proxy",
        "public_order_proxy",
        "app_rank_store_proxy",
        "platform_review_proxy",
        "hiring_capacity_proxy",
        "macro_official_context",
    ),
    "healthcare_pharma_medtech": (
        "primary_company_disclosure",
        "official_product_surface",
        "regulated_product_context",
        "trusted_external_context",
        "technology_research_proxy",
        "public_order_proxy",
        "hiring_capacity_proxy",
        "macro_official_context",
    ),
    "auto_mobility": (
        "primary_company_disclosure",
        "official_product_surface",
        "auto_product_identity_context",
        "trusted_external_context",
        "supply_chain_official_relationship",
        "channel_offer_proxy",
        "public_order_proxy",
        "hiring_capacity_proxy",
        "macro_official_context",
    ),
    "financials_banks": (
        "primary_company_disclosure",
        "financial_regulatory_context",
        "trusted_external_context",
        "hiring_capacity_proxy",
        "public_order_proxy",
        "macro_official_context",
    ),
    "energy_utilities": (
        "primary_company_disclosure",
        "energy_utility_context",
        "trusted_external_context",
        "supply_chain_official_relationship",
        "public_order_proxy",
        "hiring_capacity_proxy",
        "macro_official_context",
    ),
    "retail_cpg": (
        "primary_company_disclosure",
        "official_product_surface",
        "trusted_external_context",
        "channel_offer_proxy",
        "platform_review_proxy",
        "hiring_capacity_proxy",
        "macro_official_context",
    ),
}


INDUSTRY_ALIASES = {
    "ai_infra": "semiconductors_hardware",
    "ai_infrastructure": "semiconductors_hardware",
    "cloud_ai_infrastructure": "semiconductors_hardware",
    "semicap": "semiconductors_hardware",
    "semiconductor": "semiconductors_hardware",
    "semiconductors": "semiconductors_hardware",
    "hardware": "semiconductors_hardware",
    "consumer": "consumer_electronics",
    "consumer_electronics_hardware": "consumer_electronics",
    "saas": "software_saas",
    "software": "software_saas",
    "pharma": "healthcare_pharma_medtech",
    "healthcare": "healthcare_pharma_medtech",
    "medtech": "healthcare_pharma_medtech",
    "auto": "auto_mobility",
    "automotive": "auto_mobility",
    "banking": "financials_banks",
    "financials": "financials_banks",
    "banks": "financials_banks",
    "energy": "energy_utilities",
    "utilities": "energy_utilities",
    "retail": "retail_cpg",
    "cpg": "retail_cpg",
}


def build_source_coverage_gate(
    *,
    industry_schema: str = "generic_public_research",
    case_id: str = "",
    phase: str = "registry",
    source_layer_capability: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    observed_rows: Iterable[Mapping[str, Any]] | None = None,
    specialist_visible_rows: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    required_dimensions: Sequence[str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic source coverage gate for an industry/case.

    The gate is intentionally not a crawler. It checks whether required source classes are
    registered, runtime-ready, actually observed/parsed in a case, bound to entities/products,
    and visible to the relevant specialist role.
    """
    normalized_industry = normalize_industry_schema(industry_schema)
    normalized_phase = _normalize_phase(phase)
    generated_at = generated_at or _utc_now()
    source_rows = _source_capability_rows(source_layer_capability)
    observed = [dict(row) for row in (observed_rows or []) if isinstance(row, Mapping)]
    visible_by_role = _visible_rows_by_role(specialist_visible_rows)
    dimensions = {str(item) for item in (required_dimensions or []) if str(item).strip()}
    requirements = _requirements_for_industry(normalized_industry, required_dimensions=dimensions)

    requirement_rows = [
        _evaluate_requirement(
            req,
            phase=normalized_phase,
            source_rows=source_rows,
            observed_rows=observed,
            visible_rows_by_role=visible_by_role,
        )
        for req in requirements
    ]
    exact_violations = _exact_authority_violations(source_rows=source_rows, observed_rows=observed)
    status = "fail" if exact_violations or any(row["status"] == "fail" for row in requirement_rows) else (
        "gap" if any(row["status"] == "gap" for row in requirement_rows) else "pass"
    )
    gaps = [gap for row in requirement_rows for gap in row["gaps"]]
    summary = _summary(requirement_rows, exact_violations=exact_violations)
    validation = validate_source_coverage_gate_requirements(requirement_rows, exact_violations=exact_violations)
    return {
        "schema_version": SOURCE_COVERAGE_GATE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "case_id": case_id,
        "industry_schema": normalized_industry,
        "requested_industry_schema": industry_schema,
        "phase": normalized_phase,
        "status": status,
        "summary": summary,
        "requirements": requirement_rows,
        "gaps": gaps,
        "exact_authority_violations": exact_violations,
        "validation": validation,
        "policy": "registry_then_runtime_case_source_coverage_without_l2_l3_exact_authority_promotion_v0_1",
    }


def build_source_coverage_matrix(
    *,
    industry_schemas: Sequence[str] | None = None,
    phase: str = "registry",
    source_layer_capability: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    observed_rows: Iterable[Mapping[str, Any]] | None = None,
    specialist_visible_rows: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    schemas = [normalize_industry_schema(item) for item in (industry_schemas or sorted(INDUSTRY_REQUIREMENT_IDS))]
    gates = [
        build_source_coverage_gate(
            industry_schema=schema,
            phase=phase,
            source_layer_capability=source_layer_capability,
            observed_rows=observed_rows,
            specialist_visible_rows=specialist_visible_rows,
            generated_at=generated_at,
        )
        for schema in schemas
    ]
    status = "fail" if any(gate["status"] == "fail" for gate in gates) else "gap" if any(gate["status"] == "gap" for gate in gates) else "pass"
    return {
        "schema_version": SOURCE_COVERAGE_MATRIX_SCHEMA_VERSION,
        "generated_at": generated_at,
        "phase": _normalize_phase(phase),
        "status": status,
        "industry_count": len(gates),
        "summary": {
            "by_status": dict(sorted(Counter(gate["status"] for gate in gates).items())),
            "requirement_count": sum(int(gate["summary"]["requirement_count"]) for gate in gates),
            "gap_requirement_count": sum(int(gate["summary"]["gap_requirement_count"]) for gate in gates),
            "fail_requirement_count": sum(int(gate["summary"]["fail_requirement_count"]) for gate in gates),
            "exact_authority_violation_count": sum(int(gate["summary"]["exact_authority_violation_count"]) for gate in gates),
        },
        "gates": gates,
        "validation": {
            "status": "fail" if any(gate["validation"]["status"] == "fail" for gate in gates) else "pass",
            "errors": [error for gate in gates for error in gate["validation"].get("errors", [])],
        },
    }


def write_source_coverage_matrix(
    payload: Mapping[str, Any],
    *,
    output_summary_path: str | Path = "data/manifests/source_coverage_gate_summary_v0_1.json",
    output_report_path: str | Path = "docs/internal/vnext_20260610/source_coverage_gate.zh-CN.md",
) -> dict[str, str]:
    summary_path = Path(output_summary_path)
    report_path = Path(output_report_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_source_coverage_matrix_report(payload), encoding="utf-8")
    return {"summary": str(summary_path), "report": str(report_path)}


def validate_source_coverage_gate_requirements(
    requirements: Iterable[Mapping[str, Any]],
    *,
    exact_violations: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    for row in requirements:
        req_id = str(row.get("requirement_id") or "")
        status = str(row.get("status") or "")
        if status not in {"pass", "gap", "fail"}:
            errors.append({"type": "invalid_requirement_status", "requirement_id": req_id, "status": status})
        if not row.get("source_ids"):
            errors.append({"type": "requirement_missing_source_ids", "requirement_id": req_id})
        if row.get("exact_authority_violation_sources"):
            errors.append(
                {
                    "type": "non_l1_exact_authority_in_requirement",
                    "requirement_id": req_id,
                    "sources": row.get("exact_authority_violation_sources"),
                }
            )
    for violation in exact_violations or []:
        errors.append({"type": "source_coverage_exact_authority_violation", **dict(violation)})
    return {
        "schema_version": "finsight_source_coverage_gate_validation_v0_1",
        "status": "fail" if errors else "pass",
        "errors": errors,
    }


def normalize_industry_schema(value: str) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace("/", "_").replace(" ", "_")
    text = "_".join(part for part in text.split("_") if part)
    return INDUSTRY_ALIASES.get(text, text if text in INDUSTRY_REQUIREMENT_IDS else "generic_public_research")


def render_source_coverage_matrix_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Source Coverage Gate Report",
        "",
        f"- schema_version: `{payload.get('schema_version')}`",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- phase: `{payload.get('phase')}`",
        f"- status: `{payload.get('status')}`",
        "",
        "| industry | status | requirements | gap | fail | exact authority violations |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for gate in payload.get("gates") or []:
        if not isinstance(gate, Mapping):
            continue
        summary = gate.get("summary") if isinstance(gate.get("summary"), Mapping) else {}
        lines.append(
            "| "
            + " | ".join(
                [
                    str(gate.get("industry_schema") or ""),
                    str(gate.get("status") or ""),
                    str(summary.get("requirement_count") or 0),
                    str(summary.get("gap_requirement_count") or 0),
                    str(summary.get("fail_requirement_count") or 0),
                    str(summary.get("exact_authority_violation_count") or 0),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Requirement Gaps", ""])
    for gate in payload.get("gates") or []:
        if not isinstance(gate, Mapping):
            continue
        gaps = [gap for gap in gate.get("gaps") or [] if isinstance(gap, Mapping)]
        if not gaps:
            continue
        lines.append(f"### {gate.get('industry_schema')}")
        lines.append("")
        for gap in gaps[:20]:
            lines.append(
                f"- `{gap.get('requirement_id')}`: `{gap.get('gap_type')}`; "
                f"sources={', '.join(gap.get('source_ids') or [])}; next={gap.get('next_action') or ''}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _requirements_for_industry(
    industry_schema: str,
    *,
    required_dimensions: set[str],
) -> list[SourceCoverageRequirement]:
    ids = INDUSTRY_REQUIREMENT_IDS.get(industry_schema) or INDUSTRY_REQUIREMENT_IDS["generic_public_research"]
    rows = [REQUIREMENT_TEMPLATES[item] for item in ids if item in REQUIREMENT_TEMPLATES]
    if required_dimensions:
        explicit_ids = [item for item in sorted(required_dimensions) if item in REQUIREMENT_TEMPLATES]
        seen_ids = {row.requirement_id for row in rows}
        rows.extend(REQUIREMENT_TEMPLATES[item] for item in explicit_ids if item not in seen_ids)
        rows = [row for row in rows if row.dimension in required_dimensions or row.requirement_id in required_dimensions]
    return rows


def _evaluate_requirement(
    req: SourceCoverageRequirement,
    *,
    phase: str,
    source_rows: list[dict[str, Any]],
    observed_rows: list[dict[str, Any]],
    visible_rows_by_role: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    source_rows_for_req = [row for row in source_rows if str(row.get("source_id") or "") in set(req.source_ids)]
    exact_violations = [
        str(row.get("source_id") or "")
        for row in source_rows_for_req
        if str(row.get("layer_id") or "") in {"L2", "L3", "L4"}
        and (bool(row.get("can_support_company_exact_fact")) or bool(row.get("exact_value_authority_ready")))
    ]
    ready_rows = [row for row in source_rows_for_req if _source_row_ready(row)]
    route_candidate_rows = [row for row in source_rows_for_req if _source_row_route_candidate(row)]
    observed_for_req = [row for row in observed_rows if _row_matches_requirement(row, req)]
    parser_rows = [row for row in observed_for_req if _row_parser_backed(row)]
    entity_bound_rows = [row for row in parser_rows if _row_entity_bound(row, req.entity_binding_kinds)]
    runtime_ready_source_ids = set().union(*[_row_source_ids(row) for row in parser_rows]) if parser_rows else set()
    effective_ready_source_count = max(len(ready_rows), len(runtime_ready_source_ids.intersection(set(req.source_ids))))
    visible_rows = [
        row
        for role in req.specialist_roles
        for row in visible_rows_by_role.get(role, [])
        if _row_matches_requirement(row, req)
    ]
    visible_parser_rows = [row for row in visible_rows if _row_parser_backed(row) or _row_matches_requirement(row, req)]

    gaps: list[dict[str, Any]] = []
    if exact_violations:
        gaps.append(_gap(req, "non_l1_exact_authority_violation", "L2/L3/L4 source is marked as exact authority."))
    if effective_ready_source_count < req.min_ready_sources:
        gap_type = "source_runtime_route_not_ready"
        if not source_rows_for_req:
            gap_type = "source_profile_missing"
        elif route_candidate_rows:
            gap_type = "source_parser_or_mapping_not_runtime_ready"
        elif any(str(row.get("evidence_graph_status") or "") in NOT_READY_STATUSES for row in source_rows_for_req):
            gap_type = "source_not_registered_or_blocked"
        gaps.append(
            _gap(
                req,
                gap_type,
                f"ready={effective_ready_source_count}, registry_ready={len(ready_rows)}, runtime_parser_sources={len(runtime_ready_source_ids)}, required={req.min_ready_sources}; route_candidates={len(route_candidate_rows)}",
            )
        )
    if phase == "runtime_case":
        if len(observed_for_req) < req.min_observed_rows:
            gaps.append(_gap(req, "runtime_case_observed_rows_missing", f"observed={len(observed_for_req)}, required={req.min_observed_rows}"))
        if len(parser_rows) < req.min_parser_rows:
            gaps.append(_gap(req, "runtime_case_parser_rows_missing", f"parser_rows={len(parser_rows)}, required={req.min_parser_rows}"))
        if req.min_entity_bound_rows and len(entity_bound_rows) < req.min_entity_bound_rows:
            gaps.append(
                _gap(
                    req,
                    "runtime_case_entity_binding_missing",
                    f"entity_bound_rows={len(entity_bound_rows)}, required={req.min_entity_bound_rows}, kinds={','.join(req.entity_binding_kinds)}",
                )
            )
        if len(visible_parser_rows) < req.min_visible_rows:
            gaps.append(_gap(req, "runtime_case_specialist_visibility_missing", f"visible_rows={len(visible_parser_rows)}, required={req.min_visible_rows}"))

    status = "fail" if exact_violations else "gap" if gaps else "pass"
    return {
        "schema_version": "finsight_source_coverage_requirement_v0_1",
        "requirement_id": req.requirement_id,
        "dimension": req.dimension,
        "status": status,
        "phase": phase,
        "source_ids": list(req.source_ids),
        "layer_ids": list(req.layer_ids),
        "specialist_roles": list(req.specialist_roles),
        "source_profile_count": len(source_rows_for_req),
        "ready_source_count": len(ready_rows),
        "effective_ready_source_count": effective_ready_source_count,
        "route_candidate_source_count": len(route_candidate_rows),
        "observed_row_count": len(observed_for_req),
        "parser_row_count": len(parser_rows),
        "entity_bound_row_count": len(entity_bound_rows),
        "specialist_visible_row_count": len(visible_parser_rows),
        "by_source_status": dict(sorted(Counter(str(row.get("evidence_graph_status") or "unknown") for row in source_rows_for_req).items())),
        "observed_source_classes": sorted({str(row.get("source_class") or "") for row in observed_for_req if str(row.get("source_class") or "").strip()}),
        "observed_structured_context_types": sorted({str(row.get("structured_context_type") or "") for row in parser_rows if str(row.get("structured_context_type") or "").strip()}),
        "binding_status_distribution": _binding_distribution(parser_rows),
        "exact_authority_violation_sources": exact_violations,
        "gaps": gaps,
        "claim_boundary": req.claim_boundary,
        "next_action": req.next_action,
    }


def _gap(req: SourceCoverageRequirement, gap_type: str, detail: str) -> dict[str, Any]:
    return {
        "gap_type": gap_type,
        "requirement_id": req.requirement_id,
        "dimension": req.dimension,
        "source_ids": list(req.source_ids),
        "detail": detail,
        "next_action": req.next_action,
        "claim_boundary": req.claim_boundary,
    }


def _source_capability_rows(
    source_layer_capability: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    if isinstance(source_layer_capability, Mapping):
        rows = source_layer_capability.get("rows") or []
    else:
        rows = source_layer_capability or []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _source_row_ready(row: Mapping[str, Any]) -> bool:
    status = str(row.get("evidence_graph_status") or "")
    return status in READY_STATUSES or bool(row.get("runtime_ready_context")) or bool(row.get("exact_value_authority_ready"))


def _source_row_route_candidate(row: Mapping[str, Any]) -> bool:
    status = str(row.get("evidence_graph_status") or "")
    return status in ROUTE_CANDIDATE_STATUSES or bool(row.get("can_crawl_or_download")) or bool(row.get("can_structure"))


def _row_matches_sources(row: Mapping[str, Any], source_ids: Sequence[str]) -> bool:
    return not _row_source_ids(row).isdisjoint(set(source_ids))


def _row_matches_requirement(row: Mapping[str, Any], req: SourceCoverageRequirement) -> bool:
    if not _row_matches_sources(row, req.source_ids):
        return False
    if req.requirement_id not in STRICT_REQUIREMENT_ROLE_MATCH:
        return True
    return _row_matches_strict_requirement_role(row, req.requirement_id)


def _row_matches_strict_requirement_role(row: Mapping[str, Any], requirement_id: str) -> bool:
    expected = _normalize_role_token(requirement_id)
    candidates = [
        row.get("source_role"),
        row.get("source_entity_role"),
        row.get("runtime_contract"),
        row.get("structured_context_type"),
        row.get("record_type"),
    ]
    candidates.extend(row.get("claim_types") if isinstance(row.get("claim_types"), list) else [])
    candidates.extend(row.get("allowed_claims") if isinstance(row.get("allowed_claims"), list) else [])
    for candidate in candidates:
        token = _normalize_role_token(candidate)
        if token == expected or expected in token:
            return True
    return False


def _normalize_role_token(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _row_source_ids(row: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    for key in ("source_id", "underlying_source_id", "source_layer_source_id", "provider_source_id"):
        value = str(row.get(key) or "").strip()
        if value:
            values.add(SOURCE_CLASS_TO_SOURCE_ID.get(value, value))
    source_class = str(row.get("source_class") or "").strip()
    if source_class:
        values.add(SOURCE_CLASS_TO_SOURCE_ID.get(source_class, source_class))
    return values


def _row_parser_backed(row: Mapping[str, Any]) -> bool:
    if row.get("bounded_structured_context") or row.get("source_specific_parser") or row.get("structured_context_type"):
        return True
    return str(row.get("structured_fact_status") or "") in STRUCTURED_FACT_STATUSES


def _row_entity_bound(row: Mapping[str, Any], kinds: Sequence[str]) -> bool:
    if not kinds:
        return any(_binding_status_strong(str(row.get(key) or "")) for key in ("issuer_binding_status", "product_binding_status", "counterparty_binding_status"))
    checks = {
        "issuer": str(row.get("issuer_binding_status") or ""),
        "product": str(row.get("product_binding_status") or ""),
        "counterparty": str(row.get("counterparty_binding_status") or ""),
    }
    return all(_binding_status_strong(checks.get(kind, "")) for kind in kinds)


def _binding_status_strong(value: str) -> bool:
    return value in STRONG_BINDING_STATUSES


def _binding_distribution(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        key: dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))
        for key in ("issuer_binding_status", "product_binding_status", "counterparty_binding_status")
    }


def _visible_rows_by_role(
    specialist_visible_rows: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
) -> dict[str, list[dict[str, Any]]]:
    if not specialist_visible_rows:
        return {}
    if isinstance(specialist_visible_rows, Mapping):
        out: dict[str, list[dict[str, Any]]] = {}
        for role, value in specialist_visible_rows.items():
            out[str(role)] = _extract_rows(value)
        return out
    rows = [dict(row) for row in specialist_visible_rows if isinstance(row, Mapping)]
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        role = str(row.get("role") or row.get("agent_id") or row.get("specialist_role") or "unknown")
        out.setdefault(role, []).append(row)
    return out


def _extract_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        for key in ("selected_rows", "visible_rows", "bounded_evidence_rows", "rows", "context_rows"):
            rows = value.get(key)
            if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)):
                return [dict(row) for row in rows if isinstance(row, Mapping)]
        return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _exact_authority_violations(
    *,
    source_rows: Sequence[Mapping[str, Any]],
    observed_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for row in source_rows:
        layer_id = str(row.get("layer_id") or row.get("source_layer_id") or "")
        if layer_id in {"L2", "L3", "L4"} and (bool(row.get("can_support_company_exact_fact")) or bool(row.get("exact_value_authority_ready"))):
            violations.append(
                {
                    "source_id": str(row.get("source_id") or ""),
                    "layer_id": layer_id,
                    "violation_scope": "source_capability",
                }
            )
    for row in observed_rows:
        layer_id = str(row.get("source_layer_id") or row.get("source_layer") or row.get("layer_id") or "")
        if layer_id in {"L2", "L3", "L4"} and (
            bool(row.get("can_support_company_exact_fact"))
            or bool(row.get("exact_value_authority"))
            or bool(row.get("exact_value_authority_ready"))
        ):
            violations.append(
                {
                    "source_id": ",".join(sorted(_row_source_ids(row))),
                    "evidence_ref": str(row.get("evidence_ref") or row.get("evidence_id") or ""),
                    "layer_id": layer_id,
                    "violation_scope": "observed_row",
                }
            )
    return violations


def _summary(requirements: Sequence[Mapping[str, Any]], *, exact_violations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_status = Counter(str(row.get("status") or "unknown") for row in requirements)
    by_dimension = Counter(str(row.get("dimension") or "unknown") for row in requirements)
    return {
        "requirement_count": len(requirements),
        "pass_requirement_count": by_status.get("pass", 0),
        "gap_requirement_count": by_status.get("gap", 0),
        "fail_requirement_count": by_status.get("fail", 0),
        "exact_authority_violation_count": len(exact_violations),
        "by_status": dict(sorted(by_status.items())),
        "by_dimension": dict(sorted(by_dimension.items())),
    }


def _normalize_phase(value: str) -> str:
    text = str(value or "").strip().lower()
    return "runtime_case" if text in {"runtime", "runtime_case", "case"} else "registry"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
