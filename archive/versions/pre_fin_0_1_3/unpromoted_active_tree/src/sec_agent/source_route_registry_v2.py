from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


SOURCE_ROUTE_REGISTRY_V2_SCHEMA_VERSION = "finsight_source_route_registry_v2_0"
SIGNAL_AUTHORITY_MAPPER_SCHEMA_VERSION = "finsight_signal_authority_mapper_v0_2"

EXACT_COMPANY_CLAIMS = {
    "reported_financial_fact",
    "company_reported_financial_fact",
    "company_reported_product_kpi",
    "product_revenue",
    "product_sales",
    "sku_revenue",
    "unit_sales",
    "shipments",
    "ASP",
    "market_share",
    "sell_through",
    "channel_inventory",
    "backlog",
    "customer_order_value",
}

COMMON_FORBIDDEN_EXACT_CLAIMS = sorted(
    {
        "product_revenue",
        "product_sales",
        "sku_revenue",
        "unit_sales",
        "shipments",
        "ASP",
        "market_share",
        "sell_through",
        "channel_inventory",
        "backlog",
        "customer_order_value",
        "inventory",
        "order_value",
    }
)


@dataclass(frozen=True)
class SourceRouteContract:
    source_role: str
    support_surface: str
    source_layers: tuple[str, ...]
    claim_scope: str
    authority_mode: str
    signal_authority_type: str
    locator: str
    fetcher: str
    parser: str
    verifier: str
    authority_mapper: str
    runtime_row_type: str
    required_fields: tuple[str, ...]
    entity_binding_keys: tuple[str, ...]
    forbidden_claim_types: tuple[str, ...] = tuple(COMMON_FORBIDDEN_EXACT_CLAIMS)
    not_applicable_rules: tuple[str, ...] = ()
    commercial_gap_boundary: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = SOURCE_ROUTE_REGISTRY_V2_SCHEMA_VERSION
        return payload


SOURCE_ROUTE_CONTRACTS: dict[str, SourceRouteContract] = {
    "primary_company_disclosure": SourceRouteContract(
        source_role="primary_company_disclosure",
        support_surface="fundamental_company_disclosure",
        source_layers=("L1",),
        claim_scope="Company-disclosed financial statement, filing, and product/operating metrics after period/unit/citation gates.",
        authority_mode="exact_company_fact_authority",
        signal_authority_type="company_disclosure_fact",
        locator="sec_fsd_company_ir_local_exchange_locator",
        fetcher="sec_edgar_fsd_ir_local_exchange_fetcher",
        parser="financial_statement_and_company_disclosure_parser",
        verifier="period_unit_currency_citation_exact_fact_verifier",
        authority_mapper="exact_fact_authority_mapper",
        runtime_row_type="ExactFactRow",
        required_fields=("ticker", "company_name", "source_id", "sample_urls_or_refs", "exact_slot_count", "claim_boundary"),
        entity_binding_keys=("ticker", "company_name"),
        forbidden_claim_types=(),
        commercial_gap_boundary="If company does not disclose a metric, do not fill it with public proxy or commercial tracker unless explicitly licensed.",
    ),
    "official_product_surface": SourceRouteContract(
        source_role="official_product_surface",
        support_surface="product_and_technology",
        source_layers=("L1", "L2"),
        claim_scope="Official product existence, taxonomy, specifications, positioning, and company-disclosed product facts.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="technical_fact",
        locator="official_product_surface_locator",
        fetcher="official_product_surface_fetcher",
        parser="official_product_page_datasheet_catalog_parser",
        verifier="issuer_product_binding_and_forbidden_exact_claim_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="ProductSpecOrOfficialProductContextRow",
        required_fields=("ticker", "company_name", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "product_family", "product_binding_statuses"),
    ),
    "trusted_external_context": SourceRouteContract(
        source_role="trusted_external_context",
        support_surface="industry_competition_market_context",
        source_layers=("L2",),
        claim_scope="Trusted publisher, association, or official event context; not company exact values unless separately authoritative.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="market_or_industry_context_signal",
        locator="trusted_external_source_locator",
        fetcher="trusted_external_source_fetcher",
        parser="trusted_external_context_parser",
        verifier="issuer_product_or_industry_binding_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="TrustedExternalContextRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "industry_schema", "product_binding_statuses"),
    ),
    "macro_official_context": SourceRouteContract(
        source_role="macro_official_context",
        support_surface="macro_industry_driver",
        source_layers=("L2",),
        claim_scope="Official macro, industry, demand, price, trade, and rates context via exposure bridge.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="macro_driver_signal",
        locator="macro_official_api_locator",
        fetcher="fred_eia_bls_bea_census_fdic_fetcher",
        parser="macro_official_api_context_parser",
        verifier="industry_exposure_bridge_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="MacroIndustryDriverRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "industry_schema"),
    ),
    "financial_regulatory_context": SourceRouteContract(
        source_role="financial_regulatory_context",
        support_surface="capital_funding_ownership_market_liquidity",
        source_layers=("L2",),
        claim_scope="Regulatory financial context such as banking, credit, rate, or financial-sector exposure; not issuer financial facts unless directly disclosed.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="financial_regulatory_signal",
        locator="financial_regulatory_api_locator",
        fetcher="fdic_fred_regulatory_fetcher",
        parser="financial_regulatory_context_parser",
        verifier="issuer_or_sector_exposure_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="FinancialRegulatoryContextRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "industry_schema"),
    ),
    "energy_utility_context": SourceRouteContract(
        source_role="energy_utility_context",
        support_surface="macro_industry_driver",
        source_layers=("L2",),
        claim_scope="Energy, utility, capacity, demand, fuel, and power-market context for company or industry exposure.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="energy_utility_signal",
        locator="energy_utility_official_api_locator",
        fetcher="eia_fred_utility_regulatory_fetcher",
        parser="energy_utility_context_parser",
        verifier="utility_or_industry_exposure_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="EnergyUtilityContextRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "industry_schema"),
    ),
    "technology_research_proxy": SourceRouteContract(
        source_role="technology_research_proxy",
        support_surface="technology_research_ip",
        source_layers=("L3",),
        claim_scope="Research, patent, standards, or paper signal; not product launch, moat proof, sales, or market share.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="technology_research_signal",
        locator="technology_research_assignee_topic_locator",
        fetcher="openalex_patentsview_uspto_fetcher",
        parser="technology_research_context_parser",
        verifier="assignee_topic_product_family_binding_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="TechnologyResearchProxyRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "product_family", "issuer_binding_statuses"),
    ),
    "public_order_proxy": SourceRouteContract(
        source_role="public_order_proxy",
        support_surface="public_order_supply_chain_proxy",
        source_layers=("L3",),
        claim_scope="Public tender, award, or order-existence proxy; no total company sales, backlog, or revenue inference.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="public_order_signal",
        locator="public_order_tender_award_locator",
        fetcher="usaspending_local_tender_fetcher",
        parser="public_order_award_parser",
        verifier="recipient_supplier_product_binding_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="PublicOrderProxyRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "counterparty_binding_statuses", "product_binding_statuses"),
    ),
    "official_customer_order_or_deployment_event": SourceRouteContract(
        source_role="official_customer_order_or_deployment_event",
        support_surface="official_customer_order_deployment_event",
        source_layers=("L2", "L3"),
        claim_scope=(
            "Official issuer/customer/supplier customer order, agreement, project, deployment, production, or "
            "customer-story event. Supports bounded event facts and thesis drivers, not revenue, backlog, ASP, "
            "shipment volume, sell-through, share, or complete order book."
        ),
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="customer_order_or_deployment_event_signal",
        locator="official_customer_order_deployment_event_locator",
        fetcher="official_news_customer_contract_ir_fetcher",
        parser="official_customer_order_deployment_event_parser",
        verifier="issuer_counterparty_product_event_binding_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="OfficialCustomerOrderDeploymentEventRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "counterparty_binding_statuses", "product_binding_statuses"),
    ),
    "technical_product_spec": SourceRouteContract(
        source_role="technical_product_spec",
        support_surface="product_spec_and_capability",
        source_layers=("L2",),
        claim_scope="Official product specification, architecture, configuration, feature, model, or version facts for product comparison.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="technical_fact",
        locator="official_product_datasheet_spec_locator",
        fetcher="official_product_page_datasheet_fetcher",
        parser="product_spec_slot_parser",
        verifier="issuer_product_spec_binding_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="ProductSpecSlot",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "product_binding_statuses"),
    ),
    "product_generation_edge": SourceRouteContract(
        source_role="product_generation_edge",
        support_surface="product_spec_and_capability",
        source_layers=("L2",),
        claim_scope="Official product-generation or architecture transition edge; supports capability-cycle analysis, not demand or revenue exact.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="product_generation_signal",
        locator="official_product_generation_locator",
        fetcher="official_product_page_datasheet_fetcher",
        parser="product_generation_edge_parser",
        verifier="issuer_product_generation_binding_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="ProductGenerationEdge",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "product_binding_statuses"),
    ),
    "product_benchmark_proxy": SourceRouteContract(
        source_role="product_benchmark_proxy",
        support_surface="product_spec_and_capability",
        source_layers=("L2", "L3"),
        claim_scope="Benchmark/performance proxy for product capability comparison; no revenue, share, adoption, or sales exact.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="product_benchmark_signal",
        locator="official_or_trusted_benchmark_locator",
        fetcher="official_product_benchmark_fetcher",
        parser="benchmark_metric_product_parser",
        verifier="issuer_product_benchmark_binding_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="ProductBenchmarkProxyRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "product_binding_statuses"),
    ),
    "customer_deployment_proxy": SourceRouteContract(
        source_role="customer_deployment_proxy",
        support_surface="official_customer_deployment_signal",
        source_layers=("L2", "L3"),
        claim_scope="Official customer deployment/project context; supports bounded deployment and demand-visibility signals only.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="customer_deployment_signal",
        locator="official_customer_deployment_locator",
        fetcher="official_customer_supplier_news_fetcher",
        parser="customer_deployment_context_parser",
        verifier="issuer_counterparty_product_deployment_binding_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="CustomerDeploymentProxyRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "counterparty_binding_statuses", "product_binding_statuses"),
    ),
    "capital_structure_disclosure": SourceRouteContract(
        source_role="capital_structure_disclosure",
        support_surface="capital_funding_ownership_market_liquidity",
        source_layers=("L1",),
        claim_scope="Company-disclosed debt, credit facility, cash/debt/net-debt, lease, convertible, or offering context from SEC/FSD/IR sources.",
        authority_mode="exact_company_fact_authority",
        signal_authority_type="capital_structure_fact",
        locator="sec_debt_credit_offering_locator",
        fetcher="sec_filing_fsd_fetcher",
        parser="capital_structure_debt_credit_parser",
        verifier="issuer_period_amount_maturity_rate_citation_verifier",
        authority_mapper="exact_fact_authority_mapper",
        runtime_row_type="CapitalStructureDisclosureRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "issuer_binding_statuses"),
        forbidden_claim_types=(
            "undisclosed_financing_terms",
            "market_implied_credit_spread_without_market_source",
            "realtime_refinancing_access_without_source",
        ),
    ),
    "lagged_ownership_context": SourceRouteContract(
        source_role="lagged_ownership_context",
        support_surface="capital_funding_ownership_market_liquidity",
        source_layers=("L3",),
        claim_scope="Lagged 13F/ownership filing context only; not real-time money flow, current buying pressure, or complete ownership.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="lagged_ownership_signal",
        locator="sec_13f_ownership_locator",
        fetcher="sec_13f_bulk_fetcher",
        parser="ownership_position_lagged_context_parser",
        verifier="issuer_security_report_period_lag_policy_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="LaggedOwnershipContextRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "issuer_binding_statuses"),
        forbidden_claim_types=(
            "realtime_flow",
            "current_buying_pressure",
            "complete_ownership",
            "intraday_positioning",
            *COMMON_FORBIDDEN_EXACT_CLAIMS,
        ),
    ),
    "working_capital_liquidity": SourceRouteContract(
        source_role="working_capital_liquidity",
        support_surface="capital_funding_ownership_market_liquidity",
        source_layers=("L1",),
        claim_scope=(
            "Company-reported working-capital and liquidity statement facts including AR, inventory, AP, deferred revenue, "
            "current assets/liabilities, short-term debt, cash, CFO, capex, and financing cash flow."
        ),
        authority_mode="exact_company_fact_authority",
        signal_authority_type="working_capital_liquidity_fact",
        locator="sec_companyfacts_financial_statement_locator",
        fetcher="sec_companyfacts_or_fsd_fetcher",
        parser="working_capital_liquidity_metric_parser",
        verifier="issuer_period_value_unit_statement_metric_verifier",
        authority_mapper="exact_fact_authority_mapper",
        runtime_row_type="WorkingCapitalLiquidityRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "issuer_binding_statuses"),
        forbidden_claim_types=(
            "product_sales_without_product_kpi",
            "market_share",
            "asp",
            "channel_inventory",
            "sell_through",
            "undisclosed_financing_terms",
            "realtime_refinancing_access_without_source",
        ),
    ),
    "securities_offering_filing_event": SourceRouteContract(
        source_role="securities_offering_filing_event",
        support_surface="capital_funding_ownership_market_liquidity",
        source_layers=("L1",),
        claim_scope="SEC submissions metadata proving securities offering or registration filing-event existence and timing only.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="capital_market_event_signal",
        locator="sec_submissions_offering_form_locator",
        fetcher="sec_submissions_metadata_fetcher",
        parser="sec_offering_filing_event_metadata_parser",
        verifier="issuer_form_accession_filing_date_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="SecuritiesOfferingFilingEventRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "issuer_binding_statuses"),
        forbidden_claim_types=("offering_amount_without_filing_text_or_xml", "security_terms_without_filing_text_or_xml", "dilution_without_share_count_parser"),
    ),
    "insider_transaction_filing_event": SourceRouteContract(
        source_role="insider_transaction_filing_event",
        support_surface="capital_funding_ownership_market_liquidity",
        source_layers=("L1",),
        claim_scope="SEC submissions metadata proving Form 3/4/5/144 insider filing-event existence and timing only.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="insider_transaction_event_signal",
        locator="sec_submissions_insider_form_locator",
        fetcher="sec_submissions_metadata_fetcher",
        parser="sec_insider_filing_event_metadata_parser",
        verifier="issuer_form_accession_filing_date_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="InsiderTransactionFilingEventRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "issuer_binding_statuses"),
        forbidden_claim_types=("insider_share_count_without_xml", "transaction_price_without_xml", "management_intent_inference", "realtime_flow"),
    ),
    "beneficial_ownership_filing_event": SourceRouteContract(
        source_role="beneficial_ownership_filing_event",
        support_surface="capital_funding_ownership_market_liquidity",
        source_layers=("L1",),
        claim_scope="SEC submissions metadata proving Schedule 13D/13G filing-event existence and timing only.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="beneficial_ownership_event_signal",
        locator="sec_submissions_schedule_13d_13g_locator",
        fetcher="sec_submissions_metadata_fetcher",
        parser="sec_beneficial_ownership_filing_event_metadata_parser",
        verifier="issuer_form_accession_filing_date_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="BeneficialOwnershipFilingEventRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "issuer_binding_statuses"),
        forbidden_claim_types=("beneficial_ownership_percentage_without_schedule_parser", "activist_thesis_without_text_parser", "current_buying_pressure", "complete_ownership"),
    ),
    "proxy_governance_filing_event": SourceRouteContract(
        source_role="proxy_governance_filing_event",
        support_surface="capital_funding_ownership_market_liquidity",
        source_layers=("L1",),
        claim_scope="SEC submissions metadata proving proxy/governance filing-event existence and timing only.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="proxy_governance_event_signal",
        locator="sec_submissions_proxy_form_locator",
        fetcher="sec_submissions_metadata_fetcher",
        parser="sec_proxy_governance_filing_event_metadata_parser",
        verifier="issuer_form_accession_filing_date_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="ProxyGovernanceFilingEventRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "issuer_binding_statuses"),
        forbidden_claim_types=("actual_repurchase_without_company_disclosure", "compensation_outcome_without_proxy_table_parser", "voting_result_without_text_parser"),
    ),
    "supply_chain_official_relationship": SourceRouteContract(
        source_role="supply_chain_official_relationship",
        support_surface="supply_chain_relationship",
        source_layers=("L2", "L3"),
        claim_scope="Official supplier/customer/partner relationship signal; not revenue dependency, order value, or share.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="supply_chain_signal",
        locator="supplier_customer_official_relationship_locator",
        fetcher="official_news_contract_ir_fetcher",
        parser="supplier_customer_relationship_parser",
        verifier="issuer_counterparty_product_binding_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="SupplyChainRelationshipRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "counterparty_binding_statuses", "product_binding_statuses"),
    ),
    "channel_offer_proxy": SourceRouteContract(
        source_role="channel_offer_proxy",
        support_surface="channel_offer_availability_proxy",
        source_layers=("L3",),
        claim_scope="Channel, distributor, ecommerce, or authorized store availability/offer proxy; no ASP, inventory, sell-through, revenue, or share.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="channel_presence_signal",
        locator="channel_distributor_offer_locator",
        fetcher="channel_ecommerce_browser_or_api_fetcher",
        parser="channel_offer_sku_parser",
        verifier="issuer_product_sku_binding_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="ChannelOfferProxyRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "product_binding_statuses"),
    ),
    "developer_ecosystem_proxy": SourceRouteContract(
        source_role="developer_ecosystem_proxy",
        support_surface="developer_ecosystem_proxy",
        source_layers=("L3",),
        claim_scope="Official docs, GitHub, package, model, or developer ecosystem signal; no revenue, share, or enterprise adoption exact.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="developer_ecosystem_signal",
        locator="developer_official_seed_locator",
        fetcher="github_npm_pypi_huggingface_fetcher",
        parser="developer_ecosystem_artifact_parser",
        verifier="official_seed_publisher_issuer_binding_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="DeveloperEcosystemProxyRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "issuer_binding_statuses", "product_binding_statuses"),
    ),
    "hiring_capacity_proxy": SourceRouteContract(
        source_role="hiring_capacity_proxy",
        support_surface="hiring_capacity_proxy",
        source_layers=("L3",),
        claim_scope="Issuer-bound public job postings or careers signal; no headcount, revenue, order, or demand exact.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="hiring_capacity_signal",
        locator="official_careers_ats_locator",
        fetcher="greenhouse_lever_workday_ats_fetcher",
        parser="job_posting_parser",
        verifier="issuer_job_taxonomy_binding_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="HiringCapacityProxyRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "issuer_binding_statuses"),
    ),
    "regulated_product_context": SourceRouteContract(
        source_role="regulated_product_context",
        support_surface="regulated_product_context",
        source_layers=("L2",),
        claim_scope="Regulatory product, trial, approval, recall, safety, or product-existence context; no sales, prescriptions, or share.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="regulatory_signal",
        locator="regulated_product_api_locator",
        fetcher="clinicaltrials_openfda_nhtsa_cms_fetcher",
        parser="regulated_product_context_parser",
        verifier="sponsor_applicant_product_binding_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="RegulatedProductContextRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "product_binding_statuses"),
    ),
    "auto_product_identity_context": SourceRouteContract(
        source_role="auto_product_identity_context",
        support_surface="regulated_product_identity",
        source_layers=("L2",),
        claim_scope="Vehicle manufacturer, make, model, or VIN identity context; no registration, sales volume, or profitability proof.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="auto_product_identity_signal",
        locator="auto_product_identity_api_locator",
        fetcher="nhtsa_vpic_fetcher",
        parser="vehicle_make_model_identity_parser",
        verifier="manufacturer_model_issuer_binding_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="AutoProductIdentityContextRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "product_binding_statuses"),
    ),
    "app_rank_store_proxy": SourceRouteContract(
        source_role="app_rank_store_proxy",
        support_surface="app_marketplace_review_proxy",
        source_layers=("L3",),
        claim_scope="App listing, ranking, store metadata, or bounded marketplace signal; no downloads, revenue, share, or retention exact.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="app_marketplace_signal",
        locator="app_marketplace_listing_locator",
        fetcher="itunes_google_play_public_fetcher",
        parser="app_marketplace_metadata_parser",
        verifier="seller_app_issuer_binding_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="AppMarketplaceProxyRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "issuer_binding_statuses", "product_binding_statuses"),
    ),
    "platform_review_proxy": SourceRouteContract(
        source_role="platform_review_proxy",
        support_surface="app_marketplace_review_proxy",
        source_layers=("L3",),
        claim_scope="Platform review/rating/listing context; no app revenue, downloads, market share, or retention exact.",
        authority_mode="bounded_thesis_driver_authority",
        signal_authority_type="platform_review_signal",
        locator="platform_review_listing_locator",
        fetcher="public_platform_review_fetcher",
        parser="platform_review_metadata_parser",
        verifier="issuer_product_platform_binding_verifier",
        authority_mapper="non_financial_signal_authority_mapper",
        runtime_row_type="PlatformReviewProxyRow",
        required_fields=("ticker", "source_id", "sample_urls_or_refs", "parser_row_count", "claim_boundary"),
        entity_binding_keys=("ticker", "product_binding_statuses"),
    ),
}


def get_source_route_contract(source_role: str) -> SourceRouteContract | None:
    return SOURCE_ROUTE_CONTRACTS.get(str(source_role or ""))


def source_route_registry_payload(*, observed_source_ids_by_role: Mapping[str, set[str]] | None = None) -> dict[str, Any]:
    observed_source_ids_by_role = observed_source_ids_by_role or {}
    contracts: list[dict[str, Any]] = []
    for source_role in sorted(SOURCE_ROUTE_CONTRACTS):
        contract = SOURCE_ROUTE_CONTRACTS[source_role].to_dict()
        contract["observed_source_ids"] = sorted(observed_source_ids_by_role.get(source_role, set()))
        contracts.append(contract)
    return {
        "schema_version": SOURCE_ROUTE_REGISTRY_V2_SCHEMA_VERSION,
        "source_role_count": len(contracts),
        "contracts": contracts,
    }


def map_signal_authority_from_admission_row(row: Mapping[str, Any]) -> dict[str, Any]:
    source_role = str(row.get("source_role") or "")
    contract = get_source_route_contract(source_role)
    can_enter = bool(row.get("can_enter_evidence_bundle"))
    availability = str(row.get("availability_status") or "")
    parser_status = str(row.get("adapter_parser_status") or "")
    if not contract:
        return {
            "schema_version": SIGNAL_AUTHORITY_MAPPER_SCHEMA_VERSION,
            "source_role": source_role,
            "registered_source_role": False,
            "admission_decision": "blocked_unregistered_source_role",
            "reason": "Source role is not registered in SourceRouteRegistry v2.",
        }
    missing_fields = missing_required_fields_for_contract(row, contract)
    admission_decision = "evidence_bundle_allowed" if can_enter and not missing_fields else "planning_or_gap_only"
    if availability in {"route_or_parser_debt", "attempt_backed_public_boundary"}:
        admission_decision = availability
    return {
        "schema_version": SIGNAL_AUTHORITY_MAPPER_SCHEMA_VERSION,
        "source_role": source_role,
        "source_id": str(row.get("source_id") or ""),
        "registered_source_role": True,
        "support_surface": contract.support_surface,
        "claim_scope": contract.claim_scope,
        "authority_mode": contract.authority_mode,
        "signal_authority_type": contract.signal_authority_type,
        "exact_company_fact_authority": contract.authority_mode == "exact_company_fact_authority" and can_enter,
        "thesis_driver_authority": contract.authority_mode == "bounded_thesis_driver_authority" and can_enter,
        "can_enter_evidence_bundle": can_enter and not missing_fields,
        "admission_decision": admission_decision,
        "missing_required_fields": missing_fields,
        "forbidden_claim_types": list(contract.forbidden_claim_types),
        "required_entity_binding_keys": list(contract.entity_binding_keys),
        "runtime_row_type": contract.runtime_row_type,
        "adapter_parser_status": parser_status,
        "availability_status": availability,
    }


def missing_required_fields_for_contract(row: Mapping[str, Any], contract: SourceRouteContract) -> list[str]:
    missing: list[str] = []
    for field in contract.required_fields:
        if field == "sample_urls_or_refs":
            if not row.get("sample_urls") and not row.get("sample_evidence_refs"):
                missing.append(field)
            continue
        if field == "parser_row_count":
            if int(row.get("parser_row_count") or 0) <= 0 and int(row.get("exact_slot_count") or 0) <= 0:
                missing.append(field)
            continue
        if field == "exact_slot_count":
            if int(row.get("exact_slot_count") or 0) <= 0:
                missing.append(field)
            continue
        value = row.get(field)
        if value in (None, "", [], {}):
            missing.append(field)
    return missing
