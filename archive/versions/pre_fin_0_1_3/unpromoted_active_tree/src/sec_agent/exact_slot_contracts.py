from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


EXACT_SLOT_CONTRACT_REGISTRY_SCHEMA_VERSION = "finsight_exact_slot_contract_registry_v0_1"
EXACT_SLOT_ROW_SCHEMA_VERSION = "finsight_exact_slot_row_v0_1"
EXACT_SLOT_COVERAGE_MATRIX_SCHEMA_VERSION = "finsight_exact_slot_coverage_matrix_v0_1"
EXACT_SLOT_GAP_LEDGER_SCHEMA_VERSION = "finsight_exact_slot_gap_ledger_v0_1"


PASSING_PARSER_STATUSES = {
    "parser_pass",
    "projector_pass",
    "normalized_record_projector_pass",
    "public_context_probe_parser_pass",
    "source_specific_context_parser_pass",
    "official_product_catalog_parser_pass",
    "value_unit_period_product_citation_parser_pass",
}

PASSING_ISSUER_BINDING_STATUSES = {
    "company_domain_bound",
    "issuer_subsidiary_official_domain_bound",
    "issuer_mentioned_in_snapshot",
    "relationship_context_candidate",
    "counterparty_keyword_context_candidate",
    "macro_exposure_bridge_context",
    "family_assignment_exposure_context",
}

PASSING_PRODUCT_BINDING_STATUSES = {
    "product_mentioned_in_snapshot",
    "technology_topic_bound",
}

PASSING_COUNTERPARTY_BINDING_STATUSES = {
    "counterparty_mentioned_in_snapshot",
    "relationship_context_candidate",
    "counterparty_keyword_context_candidate",
}

AUTO_PRODUCT_PAGE_IDENTITY_TICKERS = {
    "1211.HK",
    "300750.SZ",
    "373220.KS",
    "F",
    "GM",
    "HMC",
    "LCID",
    "LI",
    "NIO",
    "RIVN",
    "TM",
    "TSLA",
    "XPEV",
}


@dataclass(frozen=True)
class ExactSlotContract:
    requirement_id: str
    slot_kind: str
    authority_scope: str
    source_ids: tuple[str, ...]
    layer_ids: tuple[str, ...]
    required_fields: tuple[str, ...]
    any_field_groups: tuple[tuple[str, ...], ...] = ()
    required_binding_kinds: tuple[str, ...] = ()
    exact_company_fact_allowed: bool = False
    allowed_claims: tuple[str, ...] = ()
    forbidden_claims: tuple[str, ...] = ()
    claim_boundary: str = ""

    def to_registry_row(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "slot_kind": self.slot_kind,
            "authority_scope": self.authority_scope,
            "source_ids": list(self.source_ids),
            "layer_ids": list(self.layer_ids),
            "required_fields": list(self.required_fields),
            "any_field_groups": [list(group) for group in self.any_field_groups],
            "required_binding_kinds": list(self.required_binding_kinds),
            "exact_company_fact_allowed": self.exact_company_fact_allowed,
            "allowed_claims": list(self.allowed_claims),
            "forbidden_claims": list(self.forbidden_claims),
            "claim_boundary": self.claim_boundary,
        }


CONTRACTS: tuple[ExactSlotContract, ...] = (
    ExactSlotContract(
        requirement_id="primary_company_disclosure",
        slot_kind="company_reported_product_operating_metric",
        authority_scope="company_disclosed_exact_fact",
        source_ids=("company_reported_product_operating_metrics",),
        layer_ids=("L1",),
        required_fields=("ticker", "source_url", "product_or_segment", "metric_name", "value", "unit", "period", "citation_span"),
        required_binding_kinds=("issuer", "product"),
        exact_company_fact_allowed=True,
        allowed_claims=("company_disclosed_product_kpi", "company_reported_product_operating_fact"),
        forbidden_claims=("market_share", "sell_through", "channel_inventory", "undisclosed_product_revenue"),
        claim_boundary="Company-disclosed product operating metric with value/unit/period/product/citation parser pass.",
    ),
    ExactSlotContract(
        requirement_id="primary_company_disclosure",
        slot_kind="company_reported_financial_statement_metric",
        authority_scope="company_disclosed_financial_statement_exact_fact",
        source_ids=("sec_financial_statement_data_sets", "company_ir_reports"),
        layer_ids=("L1",),
        required_fields=("ticker", "source_url", "metric_name", "value", "unit", "period", "statement_or_section", "citation_span"),
        any_field_groups=(("filing_type", "source_document_id"),),
        required_binding_kinds=("issuer",),
        exact_company_fact_allowed=True,
        allowed_claims=("company_reported_financial_statement_fact", "company_disclosed_fundamental_fact"),
        forbidden_claims=("product_sales_without_product_kpi", "market_share", "sell_through", "channel_inventory", "undisclosed_product_revenue"),
        claim_boundary=(
            "SEC/company-reported structured financial-statement metric with value/unit/period/statement/citation parser pass. "
            "It supports consolidated/statement-level fundamentals, not product-level sales unless a product KPI row exists."
        ),
    ),
    ExactSlotContract(
        requirement_id="official_product_surface",
        slot_kind="official_product_surface",
        authority_scope="official_product_existence_or_spec_context",
        source_ids=("company_product_pages",),
        layer_ids=("L1", "L2"),
        required_fields=("ticker", "source_url", "product_or_segment"),
        any_field_groups=(("source_title", "fact_label", "citation_url"),),
        required_binding_kinds=("issuer", "product"),
        exact_company_fact_allowed=False,
        allowed_claims=("official_product_surface", "product_taxonomy_context", "product_spec_context"),
        forbidden_claims=("company_sales", "product_revenue", "market_share", "asp", "inventory", "sell_through"),
        claim_boundary="Official issuer surface can support product existence/spec/taxonomy context only.",
    ),
    ExactSlotContract(
        requirement_id="official_product_surface",
        slot_kind="sec_product_taxonomy_context",
        authority_scope="company_filing_product_taxonomy_context",
        source_ids=("sec_product_taxonomy_normalized",),
        layer_ids=("L1",),
        required_fields=("ticker", "source_url", "product_or_segment"),
        any_field_groups=(("source_title", "fact_label", "citation_url"),),
        required_binding_kinds=("issuer", "product"),
        exact_company_fact_allowed=False,
        allowed_claims=("official_product_surface", "product_taxonomy_context"),
        forbidden_claims=("company_sales", "product_revenue", "market_share", "asp", "inventory", "sell_through"),
        claim_boundary="SEC/filing product taxonomy can support product existence/taxonomy context only.",
    ),
    ExactSlotContract(
        requirement_id="official_product_surface",
        slot_kind="company_reported_product_kpi_as_official_product_surface",
        authority_scope="company_disclosed_product_kpi_exact_fact",
        source_ids=("company_reported_product_operating_metrics",),
        layer_ids=("L1",),
        required_fields=("ticker", "source_url", "product_or_segment", "metric_name", "value", "unit", "period", "citation_span"),
        required_binding_kinds=("issuer", "product"),
        exact_company_fact_allowed=True,
        allowed_claims=("official_product_surface", "company_disclosed_product_kpi", "company_reported_product_operating_fact"),
        forbidden_claims=("market_share", "sell_through", "channel_inventory", "undisclosed_product_revenue"),
        claim_boundary=(
            "Company-disclosed product KPI also satisfies the official product surface requirement for the disclosed "
            "product/segment and metric, with the same product-KPI boundary."
        ),
    ),
    ExactSlotContract(
        requirement_id="trusted_external_context",
        slot_kind="trusted_external_event_context",
        authority_scope="trusted_external_context",
        source_ids=("mainstream_financial_news", "industry_association_reports", "official_social_accounts"),
        layer_ids=("L2",),
        required_fields=("ticker", "source_url"),
        any_field_groups=(("fact_label", "source_title", "topic"),),
        required_binding_kinds=("issuer",),
        exact_company_fact_allowed=False,
        allowed_claims=("trusted_external_context", "verification_lead", "market_proxy_context"),
        forbidden_claims=("company_exact_value", "sales_volume", "market_share"),
        claim_boundary="Trusted external context can corroborate events or statements but is not company exact-value authority.",
    ),
    ExactSlotContract(
        requirement_id="macro_official_context",
        slot_kind="official_macro_driver_value",
        authority_scope="official_macro_proxy_exact_value",
        source_ids=("fred_api", "fred_graph_csv", "bls_public_api", "bea_data_api", "census_data_api", "eia_open_data"),
        layer_ids=("L2",),
        required_fields=("ticker", "value", "unit", "period"),
        any_field_groups=(("macro_driver_id", "macro_driver_name", "fact_label", "series_id"), ("source_url", "api_url", "url")),
        exact_company_fact_allowed=False,
        allowed_claims=("macro_driver_context", "official_industry_proxy", "verification_lead"),
        forbidden_claims=("issuer_revenue", "issuer_margin", "market_share", "product_sales"),
        claim_boundary="Official macro/industry value can support exposure context only, not issuer economics.",
    ),
    ExactSlotContract(
        requirement_id="supply_chain_official_relationship",
        slot_kind="official_supply_chain_or_order_relationship",
        authority_scope="official_relationship_or_public_order_proxy",
        source_ids=("supplier_customer_official_news", "public_tenders_contracts_orders"),
        layer_ids=("L2", "L3"),
        required_fields=("ticker", "source_url"),
        any_field_groups=(("counterparty", "awarding_agency"), ("fact_label", "award_id", "topic")),
        required_binding_kinds=("issuer", "counterparty"),
        exact_company_fact_allowed=False,
        allowed_claims=("official_supply_chain_relationship_context", "public_tender_contract_context", "verification_lead"),
        forbidden_claims=("total_orders", "backlog", "revenue", "shipment_volume", "market_share"),
        claim_boundary="Official relationship or public order existence proxy only.",
    ),
    ExactSlotContract(
        requirement_id="official_customer_order_or_deployment_event",
        slot_kind="official_customer_order_or_deployment_event",
        authority_scope="official_customer_order_or_deployment_event_fact",
        source_ids=("supplier_customer_official_news",),
        layer_ids=("L2", "L3"),
        required_fields=("ticker", "source_url", "counterparty", "product_or_segment", "fact_label"),
        any_field_groups=(("event_date", "period", "as_of_datetime"), ("event_type", "relationship_label", "topic")),
        required_binding_kinds=("issuer", "counterparty", "product"),
        exact_company_fact_allowed=False,
        allowed_claims=(
            "official_customer_order_or_deployment_event",
            "customer_deployment_signal",
            "customer_adoption_signal",
            "demand_proxy_context",
            "official_supply_chain_relationship_context",
            "verification_lead",
        ),
        forbidden_claims=(
            "issuer_revenue",
            "product_revenue",
            "total_orders",
            "backlog",
            "shipment_volume",
            "market_share",
            "asp",
            "sell_through",
        ),
        claim_boundary=(
            "Official issuer/customer/supplier announcement can support a bounded customer order, agreement, "
            "project, deployment, or production-event fact with cited customer/product/date/scale fields where "
            "present. It remains separate from procurement award exact, revenue exact, backlog exact, ASP, "
            "shipment volume, sell-through, and market-share authority."
        ),
    ),
    ExactSlotContract(
        requirement_id="developer_ecosystem_proxy",
        slot_kind="developer_ecosystem_metric",
        authority_scope="public_developer_proxy_exact_snapshot",
        source_ids=("developer_ecosystem_github_npm_pypi_huggingface",),
        layer_ids=("L3",),
        required_fields=("ticker", "source_url", "fact_label"),
        any_field_groups=(("stars", "forks", "pushed_at", "latest", "modified", "downloads", "likes"),),
        required_binding_kinds=("issuer", "product"),
        exact_company_fact_allowed=False,
        allowed_claims=("developer_ecosystem_context", "market_proxy_context", "verification_lead"),
        forbidden_claims=("issuer_revenue", "market_share", "sales_volume", "durable_moat_proof"),
        claim_boundary="Developer ecosystem snapshot is directional technical attention/activity proxy.",
    ),
    ExactSlotContract(
        requirement_id="channel_offer_proxy",
        slot_kind="public_channel_offer",
        authority_scope="public_channel_offer_exact_snapshot",
        source_ids=("channel_pricing_quotations", "ecommerce_major_platforms"),
        layer_ids=("L3",),
        required_fields=("ticker", "source_url", "channel_product_name", "channel_product_id", "price", "availability"),
        required_binding_kinds=("issuer", "product"),
        exact_company_fact_allowed=False,
        allowed_claims=("channel_offer_context", "market_proxy_context", "verification_lead"),
        forbidden_claims=("asp", "channel_inventory", "sell_through", "sales_volume", "revenue", "market_share"),
        claim_boundary="Public channel offer supports listed SKU/configuration/price/availability snapshot only.",
    ),
    ExactSlotContract(
        requirement_id="channel_offer_proxy",
        slot_kind="public_channel_distributor_locator",
        authority_scope="public_channel_or_distributor_presence_snapshot",
        source_ids=("channel_distributor_locator",),
        layer_ids=("L3",),
        required_fields=("ticker", "source_url", "fact_label", "channel_name", "product_or_segment"),
        required_binding_kinds=("issuer",),
        exact_company_fact_allowed=False,
        allowed_claims=("channel_distributor_locator_context", "channel_offer_context", "market_proxy_context", "verification_lead"),
        forbidden_claims=("asp", "price", "channel_inventory", "sell_through", "sales_volume", "revenue", "market_share"),
        claim_boundary=(
            "Official or issuer-linked dealer/distributor/store locator supports public channel presence only; "
            "it does not prove price, ASP, sell-through, inventory, sales, revenue, or share."
        ),
    ),
    ExactSlotContract(
        requirement_id="app_rank_store_proxy",
        slot_kind="app_marketplace_listing",
        authority_scope="public_app_marketplace_exact_snapshot",
        source_ids=("app_store_rankings",),
        layer_ids=("L3",),
        required_fields=("ticker", "source_url", "fact_label", "rating", "rating_count"),
        any_field_groups=(("version", "release_date"),),
        required_binding_kinds=("issuer", "product"),
        exact_company_fact_allowed=False,
        allowed_claims=("app_store_marketplace_context", "market_proxy_context", "verification_lead"),
        forbidden_claims=("app_revenue", "download_count", "market_share", "sales_volume"),
        claim_boundary="App marketplace listing/rating/version snapshot only; no revenue/download/share promotion.",
    ),
    ExactSlotContract(
        requirement_id="platform_review_proxy",
        slot_kind="platform_review_or_ranking",
        authority_scope="public_platform_review_proxy_snapshot",
        source_ids=("platform_reviews_rankings_downloads",),
        layer_ids=("L3",),
        required_fields=("ticker", "source_url"),
        any_field_groups=(("rating", "rating_count", "review_count", "rank", "downloads", "fact_label"),),
        required_binding_kinds=("issuer", "product"),
        exact_company_fact_allowed=False,
        allowed_claims=("platform_review_context", "market_proxy_context", "verification_lead"),
        forbidden_claims=("revenue", "sales_volume", "market_share", "durable_moat_proof"),
        claim_boundary="Platform review/ranking/download snapshot is directional proxy only.",
    ),
    ExactSlotContract(
        requirement_id="hiring_capacity_proxy",
        slot_kind="public_job_posting",
        authority_scope="public_hiring_proxy_exact_snapshot",
        source_ids=("job_postings_hiring_signals",),
        layer_ids=("L3",),
        required_fields=("ticker", "source_url", "fact_label", "job_location"),
        any_field_groups=(("date", "posted_at", "job_department"),),
        required_binding_kinds=("issuer", "product"),
        exact_company_fact_allowed=False,
        allowed_claims=("hiring_signal_context", "market_proxy_context", "verification_lead"),
        forbidden_claims=("headcount", "revenue", "order_volume", "production_capacity_fact", "demand_proof"),
        claim_boundary="Public job posting supports role/geography/focus signal only.",
    ),
    ExactSlotContract(
        requirement_id="public_order_proxy",
        slot_kind="public_tender_or_award",
        authority_scope="public_order_proxy_exact_snapshot",
        source_ids=("public_tenders_contracts_orders",),
        layer_ids=("L3",),
        required_fields=("ticker", "source_url", "award_id", "award_amount", "award_start_date", "awarding_agency"),
        required_binding_kinds=("issuer", "counterparty"),
        exact_company_fact_allowed=False,
        allowed_claims=("public_tender_contract_context", "market_proxy_context", "verification_lead"),
        forbidden_claims=("total_orders", "backlog", "issuer_revenue", "market_share"),
        claim_boundary="Individual public tender/award snapshot only; no total order/backlog promotion.",
    ),
    ExactSlotContract(
        requirement_id="regulated_product_context",
        slot_kind="regulated_product_record",
        authority_scope="official_regulatory_product_record",
        source_ids=("clinicaltrials_api", "openfda_api", "cms_public_data", "fda_animal_drugs_api"),
        layer_ids=("L2",),
        required_fields=("ticker", "source_url"),
        any_field_groups=(("trial_id", "application_number", "device_id", "procedure_code", "record_id", "fact_label"),),
        required_binding_kinds=("issuer", "product"),
        exact_company_fact_allowed=False,
        allowed_claims=("regulated_product_context", "verification_lead"),
        forbidden_claims=("approval_success", "sales", "market_share", "utilization_share"),
        claim_boundary="Regulatory record supports product/trial/application existence and status context only.",
    ),
    ExactSlotContract(
        requirement_id="auto_product_identity_context",
        slot_kind="official_vehicle_identity_record",
        authority_scope="official_auto_identity_record",
        source_ids=("nhtsa_vpic_api", "company_product_pages"),
        layer_ids=("L2",),
        required_fields=("ticker", "source_url"),
        any_field_groups=(("make", "model", "model_year", "manufacturer", "fact_label"), ("product_or_segment", "product_family", "fact_value")),
        required_binding_kinds=("issuer", "product"),
        exact_company_fact_allowed=False,
        allowed_claims=("auto_product_identity_context", "verification_lead"),
        forbidden_claims=("vehicle_sales", "market_share", "profitability"),
        claim_boundary="NHTSA/vPIC or official issuer model pages support make/model/manufacturer identity context only.",
    ),
    ExactSlotContract(
        requirement_id="financial_regulatory_context",
        slot_kind="financial_regulatory_or_rate_record",
        authority_scope="official_financial_regulatory_context",
        source_ids=("fdic_bankfind_api", "fred_api", "fred_graph_csv"),
        layer_ids=("L2", "L3"),
        required_fields=("ticker", "source_url"),
        any_field_groups=(("value", "institution_id", "rssd_id", "series_id", "macro_driver_id", "fact_label"),),
        required_binding_kinds=("issuer",),
        exact_company_fact_allowed=False,
        allowed_claims=("financial_regulatory_context", "macro_driver_context", "verification_lead"),
        forbidden_claims=("listed_issuer_exact_financials_without_resolver", "market_share", "credit_loss_forecast"),
        claim_boundary="Bank regulatory or rate context; issuer exact fact only if resolver-specific row exists elsewhere.",
    ),
    ExactSlotContract(
        requirement_id="energy_utility_context",
        slot_kind="official_energy_utility_record",
        authority_scope="official_energy_utility_context",
        source_ids=("eia_open_data", "fred_api", "fred_graph_csv"),
        layer_ids=("L2", "L3"),
        required_fields=("ticker", "value", "unit", "period"),
        any_field_groups=(("source_url", "api_url", "url"), ("asset_id", "series_id", "macro_driver_id", "fact_label", "macro_driver_name")),
        required_binding_kinds=("issuer",),
        exact_company_fact_allowed=False,
        allowed_claims=("energy_utility_context", "macro_driver_context", "verification_lead"),
        forbidden_claims=("issuer_revenue", "issuer_margin", "market_share"),
        claim_boundary="Energy/utility official operating context only; no single-company economics promotion.",
    ),
    ExactSlotContract(
        requirement_id="technology_research_proxy",
        slot_kind="public_research_or_ip_signal",
        authority_scope="public_research_ip_proxy_snapshot",
        source_ids=("openalex_api", "patentsview_api", "official_technical_document"),
        layer_ids=("L3",),
        required_fields=("ticker", "source_url"),
        any_field_groups=(("openalex_work_id", "patent_id", "technical_doc_id", "doi", "value", "cited_by_count", "fact_label"),),
        required_binding_kinds=("issuer", "product"),
        exact_company_fact_allowed=False,
        allowed_claims=("technology_research_proxy", "verification_lead"),
        forbidden_claims=("product_sales", "market_share", "durable_moat_proof"),
        claim_boundary="Research/IP signal only; no launch/sales/moat promotion without stronger evidence.",
    ),
)


CONTRACTS_BY_REQUIREMENT_ID: dict[str, tuple[ExactSlotContract, ...]] = defaultdict(tuple)
CONTRACTS_BY_SOURCE_ID: dict[str, tuple[ExactSlotContract, ...]] = defaultdict(tuple)
for _contract in CONTRACTS:
    CONTRACTS_BY_REQUIREMENT_ID[_contract.requirement_id] = CONTRACTS_BY_REQUIREMENT_ID[_contract.requirement_id] + (_contract,)
    for _source_id in _contract.source_ids:
        CONTRACTS_BY_SOURCE_ID[_source_id] = CONTRACTS_BY_SOURCE_ID[_source_id] + (_contract,)


def build_exact_slot_contract_registry(*, generated_at: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": EXACT_SLOT_CONTRACT_REGISTRY_SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now(),
        "contract_count": len(CONTRACTS),
        "contracts": [contract.to_registry_row() for contract in CONTRACTS],
        "policy": (
            "L1 can support company exact facts only when value/unit/period/product/citation gates pass. "
            "L2/L3 slots may be exact snapshots of public records or proxy values, but they remain bounded "
            "and cannot be promoted to revenue, share, shipment, or sales claims."
        ),
    }


def build_exact_slot_rows(
    observed_rows: Iterable[Mapping[str, Any]],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    exact_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    for row in observed_rows:
        if not isinstance(row, Mapping):
            continue
        source_id = _source_id(row)
        contracts = _candidate_contracts_for_row(row, CONTRACTS_BY_SOURCE_ID.get(source_id, ()))
        if not contracts:
            continue
        for contract in contracts:
            audit = audit_row_against_exact_slot_contract(row, contract)
            if audit["status"] == "exact_slot_ready":
                exact_rows.append(_exact_slot_row(row, contract, audit, generated_at=generated_at))
            else:
                rejected_rows.append(_rejected_slot_row(row, contract, audit, generated_at=generated_at))
    exact_rows = _dedupe_rows(exact_rows, key_field="exact_slot_id")
    rejected_rows = _dedupe_rows(rejected_rows, key_field="exact_slot_attempt_id")
    return {
        "schema_version": EXACT_SLOT_ROW_SCHEMA_VERSION,
        "generated_at": generated_at,
        "exact_slot_row_count": len(exact_rows),
        "rejected_slot_attempt_count": len(rejected_rows),
        "exact_rows": exact_rows,
        "rejected_rows": rejected_rows,
        "summary": _slot_rows_summary(exact_rows, rejected_rows),
    }


def _candidate_contracts_for_row(
    row: Mapping[str, Any],
    contracts: Sequence[ExactSlotContract],
) -> list[ExactSlotContract]:
    return [contract for contract in contracts if _contract_applies_to_row(row, contract)]


def _contract_applies_to_row(row: Mapping[str, Any], contract: ExactSlotContract) -> bool:
    if contract.requirement_id == "auto_product_identity_context" and _source_id(row) == "company_product_pages":
        ticker = str(_first_present(row, "ticker", "issuer_ticker", ("entity_binding", "issuer_ticker")) or "").upper()
        return ticker in AUTO_PRODUCT_PAGE_IDENTITY_TICKERS and _row_looks_like_official_auto_identity(row)
    if contract.requirement_id == "official_customer_order_or_deployment_event":
        return _row_looks_like_official_customer_order_or_deployment_event(row)
    return True


def _row_looks_like_official_customer_order_or_deployment_event(row: Mapping[str, Any]) -> bool:
    explicit_role = str(_first_present(row, "source_role", "source_entity_role") or "")
    explicit_event_type = str(_first_present(row, "event_type", "official_event_type") or "").strip()
    if explicit_role == "official_customer_order_or_deployment_event" or explicit_event_type:
        return True
    if explicit_role and explicit_role != "official_customer_order_or_deployment_event":
        return False
    text = " ".join(
        str(_first_present(row, field) or "")
        for field in (
            "fact_label",
            "source_title",
            "product_or_segment",
            "product_family",
            "topic",
            "structured_context_summary",
        )
    ).lower()
    if not text.strip():
        return False
    event_tokens = (
        "order",
        "purchase",
        "customer",
        "deployment",
        "deploy",
        "agreement",
        "contract",
        "supply",
        "power purchase",
        "ppa",
        "project",
        "program",
        "manufacturing",
        "factory",
        "production",
        "collaboration",
        "partnership",
        "customer story",
        "case study",
    )
    return any(token in text for token in event_tokens)


def _row_looks_like_official_auto_identity(row: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(_first_present(row, field) or "")
        for field in (
            "product_or_segment",
            "product_family",
            "fact_label",
            "fact_value",
            "topic",
            "source_title",
            "structured_context_summary",
        )
    ).lower()
    if not text.strip():
        return False
    auto_tokens = (
        "auto",
        "automotive",
        "mobility",
        "vehicle",
        "vehicles",
        "electric vehicle",
        " suv",
        " mpv",
        " sedan",
        " cars",
        " car ",
    )
    if any(token in text for token in auto_tokens):
        return True
    return bool(re.search(r"\bev\b", text))


def audit_row_against_exact_slot_contract(row: Mapping[str, Any], contract: ExactSlotContract) -> dict[str, Any]:
    if _source_id(row) not in contract.source_ids:
        return {"status": "source_mismatch", "missing_fields": [], "missing_field_groups": [], "binding_failures": [], "parser_failures": []}

    layer = _first_present(row, "source_layer_id", "source_layer", "layer_id", "source_layer")
    layer_failure = bool(contract.layer_ids and layer and str(layer) not in contract.layer_ids)
    parser_failures = [] if _parser_passes(row) else ["parser_status_not_pass"]
    binding_failures = _binding_failures(row, contract.required_binding_kinds)
    missing_fields = [field for field in contract.required_fields if not _has_field(row, field)]
    missing_groups = [
        list(group)
        for group in contract.any_field_groups
        if not any(_has_field(row, field) for field in group)
    ]

    status = "exact_slot_ready"
    if parser_failures:
        status = "parser_gap"
    if missing_fields or missing_groups:
        status = "structured_field_gap"
    if binding_failures:
        status = "entity_binding_gap"
    if layer_failure:
        status = "layer_scope_gap"
    if _violates_company_exact_scope(row, contract):
        status = "source_boundary_violation"

    return {
        "status": status,
        "missing_fields": missing_fields,
        "missing_field_groups": missing_groups,
        "binding_failures": binding_failures,
        "parser_failures": parser_failures,
        "layer_failure": layer_failure,
        "virtual_fields": _virtual_fields(row),
    }


def build_exact_slot_coverage_matrix(
    *,
    company_source_matrix_rows: Iterable[Mapping[str, Any]],
    exact_slot_rows: Iterable[Mapping[str, Any]],
    rejected_slot_rows: Iterable[Mapping[str, Any]] | None = None,
    repair_queue_rows: Iterable[Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
    input_paths: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    matrix_rows = [dict(row) for row in company_source_matrix_rows if isinstance(row, Mapping)]
    exact = [dict(row) for row in exact_slot_rows if isinstance(row, Mapping)]
    rejected = [dict(row) for row in rejected_slot_rows or [] if isinstance(row, Mapping)]
    repair_queue = [dict(row) for row in repair_queue_rows or [] if isinstance(row, Mapping)]

    exact_by_company_req: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    exact_by_company_layer: dict[tuple[str, str], int] = Counter()
    for row in exact:
        ticker = str(row.get("ticker") or "").upper()
        requirement_id = str(row.get("requirement_id") or "")
        if ticker and requirement_id:
            exact_by_company_req[(ticker, requirement_id)].append(row)
            layers = row.get("contract_layer_ids") if isinstance(row.get("contract_layer_ids"), list) else []
            if not layers:
                layers = [str(row.get("source_layer_id") or row.get("layer_id") or "")]
            for layer in layers:
                if str(layer or ""):
                    exact_by_company_layer[(ticker, str(layer))] += 1

    rejected_by_company_req: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rejected:
        ticker = str(row.get("ticker") or "").upper()
        requirement_id = str(row.get("requirement_id") or "")
        if ticker and requirement_id:
            rejected_by_company_req[(ticker, requirement_id)].append(row)

    repair_by_company_req = {
        (str(row.get("ticker") or "").upper(), str(row.get("requirement_id") or "")): row
        for row in repair_queue
        if row.get("ticker") and row.get("requirement_id")
    }

    rows = [
        _exact_company_coverage_row(
            company,
            exact_by_company_req=exact_by_company_req,
            rejected_by_company_req=rejected_by_company_req,
            repair_by_company_req=repair_by_company_req,
            exact_by_company_layer=exact_by_company_layer,
            generated_at=generated_at,
        )
        for company in matrix_rows
    ]
    gap_ledger = [gap for row in rows for gap in row.get("exact_slot_gap_ledger", [])]
    summary = _coverage_summary(rows, gap_ledger=gap_ledger, exact_slot_rows=exact)
    status = "pass" if not gap_ledger else "gap"
    return {
        "schema_version": EXACT_SLOT_COVERAGE_MATRIX_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "input_paths": dict(input_paths or {}),
        "company_count": len(rows),
        "summary": summary,
        "rows": rows,
        "gap_ledger": gap_ledger,
        "validation": validate_exact_slot_coverage_matrix(rows, gap_ledger=gap_ledger),
        "boundary": (
            "A requirement passes this matrix only when at least one parser-backed exact slot row exists for the "
            "company and requirement. L2/L3 exact slots are exact snapshots/proxies and remain blocked from "
            "company revenue/share/shipment/sales promotion."
        ),
    }


def write_exact_slot_artifacts(
    *,
    registry: Mapping[str, Any],
    exact_slot_payload: Mapping[str, Any],
    coverage: Mapping[str, Any],
    output_registry_path: str | Path,
    output_exact_rows_path: str | Path,
    output_rejected_rows_path: str | Path,
    output_coverage_json_path: str | Path,
    output_coverage_jsonl_path: str | Path,
    output_gap_ledger_path: str | Path,
    output_report_path: str | Path,
) -> dict[str, str]:
    paths = {
        "registry": Path(output_registry_path),
        "exact_rows": Path(output_exact_rows_path),
        "rejected_rows": Path(output_rejected_rows_path),
        "coverage_json": Path(output_coverage_json_path),
        "coverage_jsonl": Path(output_coverage_jsonl_path),
        "gap_ledger": Path(output_gap_ledger_path),
        "report": Path(output_report_path),
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    paths["registry"].write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_jsonl(paths["exact_rows"], exact_slot_payload.get("exact_rows") or [])
    _write_jsonl(paths["rejected_rows"], exact_slot_payload.get("rejected_rows") or [])
    paths["coverage_json"].write_text(json.dumps(coverage, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_jsonl(paths["coverage_jsonl"], coverage.get("rows") or [])
    _write_jsonl(paths["gap_ledger"], coverage.get("gap_ledger") or [])
    paths["report"].write_text(render_exact_slot_coverage_report(coverage), encoding="utf-8")
    return {key: str(path) for key, path in paths.items()}


def render_exact_slot_coverage_report(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    lines = [
        "# Exact Slot Coverage Matrix",
        "",
        f"- schema_version: `{payload.get('schema_version')}`",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- status: `{payload.get('status')}`",
        f"- company_count: `{payload.get('company_count')}`",
        f"- all_required_exact_ready_company_count: `{summary.get('all_required_exact_ready_company_count')}`",
        f"- partial_exact_ready_company_count: `{summary.get('partial_exact_ready_company_count')}`",
        f"- no_exact_ready_company_count: `{summary.get('no_exact_ready_company_count')}`",
        f"- exact_slot_gap_count: `{summary.get('exact_slot_gap_count')}`",
        "",
        "## Requirement Summary",
        "",
        "| requirement | exact ready | gaps | rejected attempts |",
        "| --- | ---: | ---: | ---: |",
    ]
    for req_id, row in sorted((summary.get("by_requirement") or {}).items()):
        if isinstance(row, Mapping):
            lines.append(
                f"| {req_id} | {row.get('ready_count', 0)} | {row.get('gap_count', 0)} | {row.get('rejected_attempt_count', 0)} |"
            )
    lines.extend(["", "## Gap Class Summary", "", "| gap_class | count |", "| --- | ---: |"])
    for gap_class, count in sorted((summary.get("by_gap_class") or {}).items()):
        lines.append(f"| {gap_class} | {count} |")
    lines.extend(["", "## Boundary", "", str(payload.get("boundary") or "")])
    return "\n".join(lines) + "\n"


def validate_exact_slot_coverage_matrix(rows: Sequence[Mapping[str, Any]], *, gap_ledger: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    seen_gap_ids: set[str] = set()
    for row in rows:
        if not row.get("ticker"):
            errors.append("company row missing ticker")
        for slot in row.get("source_role_exact_slot_matrix") or []:
            if slot.get("status") == "exact_slot_ready" and not slot.get("sample_exact_slot_refs"):
                errors.append(f"{row.get('ticker')}:{slot.get('requirement_id')} ready row missing sample refs")
    for gap in gap_ledger:
        gap_id = str(gap.get("gap_id") or "")
        if not gap_id:
            errors.append("gap ledger row missing gap_id")
            continue
        if gap_id in seen_gap_ids:
            errors.append(f"duplicate gap_id: {gap_id}")
        seen_gap_ids.add(gap_id)
    return {"status": "fail" if errors else "pass", "errors": errors[:50], "error_count": len(errors)}


def load_jsonl_rows(path: str | Path) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if isinstance(value, Mapping):
                rows.append(dict(value))
    return rows


def _exact_company_coverage_row(
    company: Mapping[str, Any],
    *,
    exact_by_company_req: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    rejected_by_company_req: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    repair_by_company_req: Mapping[tuple[str, str], Mapping[str, Any]],
    exact_by_company_layer: Mapping[tuple[str, str], int],
    generated_at: str,
) -> dict[str, Any]:
    ticker = str(company.get("ticker") or "").upper()
    req_rows = []
    gap_rows = []
    for req in company.get("source_role_matrix") or []:
        if not isinstance(req, Mapping):
            continue
        req_id = str(req.get("requirement_id") or "")
        exact_rows = list(exact_by_company_req.get((ticker, req_id), ()))
        rejected_rows = list(rejected_by_company_req.get((ticker, req_id), ()))
        repair_row = repair_by_company_req.get((ticker, req_id), {})
        status = "exact_slot_ready" if exact_rows else "exact_slot_gap"
        gap_class = "pass" if exact_rows else _exact_gap_class(req, rejected_rows=rejected_rows, repair_row=repair_row)
        row = {
            "requirement_id": req_id,
            "dimension": req.get("dimension") or "",
            "target_layer_ids": req.get("layer_ids") or [],
            "target_source_ids": req.get("source_ids") or [],
            "status": status,
            "gap_class": gap_class,
            "source_gate_status": req.get("status") or "",
            "source_gate_gap_class": req.get("gap_class") or "",
            "source_gate_gap_type": req.get("gap_type") or "",
            "exact_slot_count": len(exact_rows),
            "rejected_slot_attempt_count": len(rejected_rows),
            "sample_exact_slot_refs": [row.get("exact_slot_id") for row in exact_rows[:5]],
            "sample_exact_slot_kinds": sorted({str(row.get("slot_kind") or "") for row in exact_rows if row.get("slot_kind")}),
            "sample_urls": [row.get("source_url") or row.get("snapshot_url") for row in exact_rows[:5]],
            "rejected_statuses": dict(sorted(Counter(str(row.get("rejection_status") or "") for row in rejected_rows).items())),
            "repair_seed_status": repair_row.get("repair_seed_status") or "",
            "repair_seed_count": repair_row.get("repair_seed_count") or 0,
            "claim_boundary": req.get("claim_boundary") or "",
        }
        req_rows.append(row)
        if not exact_rows:
            gap = {
                "schema_version": EXACT_SLOT_GAP_LEDGER_SCHEMA_VERSION,
                "generated_at": generated_at,
                "gap_id": _stable_id("exact_slot_gap", [ticker, req_id, gap_class]),
                "ticker": ticker,
                "company_name": company.get("company_name") or "",
                "primary_lane_id": company.get("primary_lane_id") or "",
                "requirement_id": req_id,
                "dimension": req.get("dimension") or "",
                "gap_class": gap_class,
                "source_gate_status": req.get("status") or "",
                "source_gate_gap_type": req.get("gap_type") or "",
                "rejected_statuses": row["rejected_statuses"],
                "repair_seed_status": row["repair_seed_status"],
                "repair_seed_count": row["repair_seed_count"],
                "next_action": req.get("next_action") or repair_row.get("next_action") or "",
                "claim_boundary": req.get("claim_boundary") or repair_row.get("claim_boundary") or "",
            }
            gap_rows.append(gap)

    ready_count = sum(1 for row in req_rows if row["status"] == "exact_slot_ready")
    required_count = len(req_rows)
    exact_layers = {
        layer: count
        for (layer_ticker, layer), count in sorted(exact_by_company_layer.items())
        if layer_ticker == ticker and layer
    }
    return {
        "schema_version": "finsight_exact_slot_company_coverage_row_v0_1",
        "generated_at": generated_at,
        "ticker": ticker,
        "company_name": company.get("company_name") or "",
        "primary_lane_id": company.get("primary_lane_id") or "",
        "primary_lane_name": company.get("primary_lane_name") or "",
        "industry_schema": company.get("industry_schema") or "",
        "coverage_status": (
            "all_required_exact_ready"
            if required_count and ready_count == required_count
            else "partial_exact_ready"
            if ready_count
            else "no_exact_ready"
        ),
        "required_requirement_count": required_count,
        "exact_ready_requirement_count": ready_count,
        "exact_gap_requirement_count": required_count - ready_count,
        "exact_slot_count": sum(len(exact_by_company_req.get((ticker, str(req.get("requirement_id") or "")), ())) for req in req_rows),
        "exact_slot_layers": exact_layers,
        "source_role_exact_slot_matrix": req_rows,
        "exact_slot_gap_ledger": gap_rows,
    }


def _exact_gap_class(
    req: Mapping[str, Any],
    *,
    rejected_rows: Sequence[Mapping[str, Any]],
    repair_row: Mapping[str, Any],
) -> str:
    statuses = {str(row.get("rejection_status") or "") for row in rejected_rows}
    if "structured_field_gap" in statuses:
        return "parser_or_structured_field_gap"
    if "entity_binding_gap" in statuses:
        return "resolver_binding_gap"
    if "parser_gap" in statuses:
        return "parser_gap"
    if str(req.get("status") or "") == "pass":
        return "context_only_not_exact_slot"
    if str(repair_row.get("repair_seed_status") or "") == "seed_available":
        return "seed_available_not_materialized_to_exact_slot"
    source_gap_class = str(req.get("gap_class") or "")
    if source_gap_class and source_gap_class != "pass":
        return source_gap_class
    return "exact_slot_missing"


def _exact_slot_row(row: Mapping[str, Any], contract: ExactSlotContract, audit: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    virtual = dict(audit.get("virtual_fields") or _virtual_fields(row))
    slot_values = _slot_values(row, contract, virtual_fields=virtual)
    ticker = str(_first_present(row, "ticker", "issuer_ticker", ("entity_binding", "issuer_ticker")) or "").upper()
    source_url = str(_get_field(row, "source_url") or "")
    evidence_ref = str(_first_present(row, "evidence_ref", "evidence_id", "snapshot_id", "source_candidate_id") or "")
    slot_id = _stable_id(
        "exact_slot",
        [ticker, contract.requirement_id, contract.slot_kind, source_url, evidence_ref, json.dumps(slot_values, sort_keys=True, ensure_ascii=False)],
    )
    return {
        "schema_version": EXACT_SLOT_ROW_SCHEMA_VERSION,
        "generated_at": generated_at,
        "exact_slot_id": slot_id,
        "ticker": ticker,
        "company": row.get("company") or row.get("company_name") or "",
        "requirement_id": contract.requirement_id,
        "source_role": contract.requirement_id,
        "runtime_contract": contract.slot_kind,
        "slot_kind": contract.slot_kind,
        "authority_scope": contract.authority_scope,
        "source_id": _source_id(row),
        "source_class": row.get("source_class") or "",
        "source_layer_id": _first_present(row, "source_layer_id", "source_layer", "layer_id") or "",
        "contract_layer_ids": list(contract.layer_ids),
        "source_url": source_url,
        "snapshot_url": _first_present(row, "snapshot_url", "url", "api_url", "api_route", ("citation", "url")) or "",
        "evidence_ref": evidence_ref,
        "source_title": _first_present(row, "source_title", ("citation", "title"), "fact_label") or "",
        "product_or_segment": _first_present(row, "product_or_segment", "product_family", "channel_product_name", "fact_label", "topic") or "",
        "metric_name": row.get("metric_name") or row.get("fact_type") or "",
        "period": _first_present(row, "period", "date", "award_start_date", "release_date", "modified", "pushed_at") or "",
        "value": _first_present(row, "value", "award_amount", "price", "rating", "rating_count", "stars", "forks") or "",
        "unit": row.get("unit") or "",
        "slot_values": slot_values,
        "issuer_binding_status": _binding_status(row, "issuer"),
        "product_binding_status": _binding_status(row, "product"),
        "counterparty_binding_status": _binding_status(row, "counterparty"),
        "parser_status": row.get("parser_status") or "",
        "structured_fact_status": row.get("structured_fact_status") or "",
        "can_support_company_exact_fact": contract.exact_company_fact_allowed,
        "exact_company_fact_allowed": contract.exact_company_fact_allowed,
        "allowed_claims": list(contract.allowed_claims),
        "forbidden_claims": list(contract.forbidden_claims),
        "claim_boundary": contract.claim_boundary,
    }


def _rejected_slot_row(row: Mapping[str, Any], contract: ExactSlotContract, audit: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    ticker = str(_first_present(row, "ticker", "issuer_ticker", ("entity_binding", "issuer_ticker")) or "").upper()
    source_url = str(_get_field(row, "source_url") or "")
    evidence_ref = str(_first_present(row, "evidence_ref", "evidence_id", "snapshot_id", "source_candidate_id") or "")
    return {
        "schema_version": "finsight_exact_slot_rejected_attempt_v0_1",
        "generated_at": generated_at,
        "exact_slot_attempt_id": _stable_id("exact_slot_attempt", [ticker, contract.requirement_id, contract.slot_kind, source_url, evidence_ref, str(audit.get("status") or "")]),
        "ticker": ticker,
        "requirement_id": contract.requirement_id,
        "slot_kind": contract.slot_kind,
        "source_id": _source_id(row),
        "source_url": source_url,
        "evidence_ref": evidence_ref,
        "rejection_status": audit.get("status") or "",
        "missing_fields": audit.get("missing_fields") or [],
        "missing_field_groups": audit.get("missing_field_groups") or [],
        "binding_failures": audit.get("binding_failures") or [],
        "parser_failures": audit.get("parser_failures") or [],
    }


def _slot_values(row: Mapping[str, Any], contract: ExactSlotContract, *, virtual_fields: Mapping[str, Any]) -> dict[str, Any]:
    fields = list(contract.required_fields)
    for group in contract.any_field_groups:
        fields.extend(group)
    selected: dict[str, Any] = {}
    for field in fields:
        value = _get_field(row, field)
        if _blank(value):
            value = virtual_fields.get(field)
        if not _blank(value):
            selected[field] = value
    return selected


def _slot_rows_summary(exact_rows: Sequence[Mapping[str, Any]], rejected_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "exact_by_requirement": dict(sorted(Counter(str(row.get("requirement_id") or "") for row in exact_rows).items())),
        "exact_by_source_id": dict(sorted(Counter(str(row.get("source_id") or "") for row in exact_rows).items())),
        "exact_by_slot_kind": dict(sorted(Counter(str(row.get("slot_kind") or "") for row in exact_rows).items())),
        "rejected_by_requirement": dict(sorted(Counter(str(row.get("requirement_id") or "") for row in rejected_rows).items())),
        "rejected_by_status": dict(sorted(Counter(str(row.get("rejection_status") or "") for row in rejected_rows).items())),
        "company_count_with_exact_slot": len({str(row.get("ticker") or "") for row in exact_rows if row.get("ticker")}),
    }


def _coverage_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    gap_ledger: Sequence[Mapping[str, Any]],
    exact_slot_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    coverage_statuses = Counter(str(row.get("coverage_status") or "") for row in rows)
    by_requirement: dict[str, dict[str, int]] = defaultdict(lambda: {"ready_count": 0, "gap_count": 0, "rejected_attempt_count": 0})
    for row in rows:
        for req in row.get("source_role_exact_slot_matrix") or []:
            if not isinstance(req, Mapping):
                continue
            bucket = by_requirement[str(req.get("requirement_id") or "")]
            if req.get("status") == "exact_slot_ready":
                bucket["ready_count"] += 1
            else:
                bucket["gap_count"] += 1
            bucket["rejected_attempt_count"] += int(req.get("rejected_slot_attempt_count") or 0)
    return {
        "company_count": len(rows),
        "all_required_exact_ready_company_count": coverage_statuses.get("all_required_exact_ready", 0),
        "partial_exact_ready_company_count": coverage_statuses.get("partial_exact_ready", 0),
        "no_exact_ready_company_count": coverage_statuses.get("no_exact_ready", 0),
        "exact_slot_row_count": len(exact_slot_rows),
        "exact_slot_company_count": len({str(row.get("ticker") or "") for row in exact_slot_rows if row.get("ticker")}),
        "exact_slot_gap_count": len(gap_ledger),
        "by_requirement": dict(sorted(by_requirement.items())),
        "by_gap_class": dict(sorted(Counter(str(row.get("gap_class") or "") for row in gap_ledger).items())),
        "by_lane": dict(sorted(Counter(str(row.get("primary_lane_id") or "") for row in rows).items())),
    }


def _binding_failures(row: Mapping[str, Any], binding_kinds: Sequence[str]) -> list[str]:
    failures: list[str] = []
    for kind in binding_kinds:
        status = _binding_status(row, kind)
        if kind == "issuer" and status not in PASSING_ISSUER_BINDING_STATUSES:
            failures.append(f"{kind}:{status or 'missing'}")
        elif kind == "product" and status not in PASSING_PRODUCT_BINDING_STATUSES:
            failures.append(f"{kind}:{status or 'missing'}")
        elif kind == "counterparty" and status not in PASSING_COUNTERPARTY_BINDING_STATUSES:
            failures.append(f"{kind}:{status or 'missing'}")
    return failures


def _binding_status(row: Mapping[str, Any], kind: str) -> str:
    field = {
        "issuer": "issuer_binding_status",
        "product": "product_binding_status",
        "counterparty": "counterparty_binding_status",
    }[kind]
    value = _first_present(row, field, ("entity_binding", field))
    return str(value or "")


def _parser_passes(row: Mapping[str, Any]) -> bool:
    status = str(row.get("parser_status") or "")
    if status in PASSING_PARSER_STATUSES:
        return True
    if row.get("runtime_ready_context") and row.get("structured_fact_status"):
        return str(row.get("structured_fact_status")) in {"exact_fact_materialized", "bounded_context_fact_materialized", "context_rows_ready", "candidate_rows_ready"}
    return False


def _violates_company_exact_scope(row: Mapping[str, Any], contract: ExactSlotContract) -> bool:
    if contract.exact_company_fact_allowed:
        return False
    return bool(row.get("can_support_company_exact_fact") or row.get("exact_value_authority_ready")) and str(_first_present(row, "source_layer_id", "source_layer", "layer_id") or "") != "L1"


def _source_id(row: Mapping[str, Any]) -> str:
    return str(_first_present(row, "source_id", "underlying_source_id") or "")


def _has_field(row: Mapping[str, Any], field: str) -> bool:
    value = _get_field(row, field)
    if _blank(value):
        value = _virtual_fields(row).get(field)
    return not _blank(value)


def _get_field(row: Mapping[str, Any], field: str) -> Any:
    direct = _first_present(row, field)
    if not _blank(direct):
        return direct
    if field == "source_url":
        return _first_present(row, "source_url", "snapshot_url", "url", "api_url", "api_route", ("citation", "url"), ("citation", "source_url"))
    if field == "citation_url":
        return _first_present(row, ("citation", "url"), ("citation", "source_url"), "source_url", "snapshot_url", "url", "api_url", "api_route")
    if field == "source_title":
        return _first_present(row, "source_title", ("citation", "title"), "fact_label", "topic")
    if field == "counterparty":
        return _first_present(row, "counterparty", "awarding_agency", ("entity_binding", "counterparty_matched_terms"))
    if field == "date":
        return _first_present(row, "date", "award_start_date", "release_date", "modified", "pushed_at")
    if field == "posted_at":
        return _first_present(row, "posted_at", "date", "as_of_datetime")
    if field == "model":
        return _first_present(row, "model", "product_or_segment", "channel_product_name")
    if field == "make":
        return _first_present(row, "make", "source_entity_name", "company")
    if field == "manufacturer":
        return _first_present(row, "manufacturer", "source_entity_name", "company")
    if field == "record_id":
        return _first_present(row, "record_id", "identifier", "evidence_ref", "evidence_id")
    if field in {"trial_id", "application_number", "procedure_code", "device_id"}:
        identifier_type = str(row.get("identifier_type") or "").upper()
        identifier = _first_present(row, "identifier", "record_id", "evidence_ref")
        if field == "trial_id" and ("NCT" in identifier_type or str(identifier or "").upper().startswith("NCT")):
            return identifier
        if field == "application_number" and ("FDA" in identifier_type or str(identifier or "").upper().startswith(("NDA", "ANDA", "BLA"))):
            return identifier
        if field == "procedure_code" and ("CMS" in identifier_type or "PROCEDURE" in identifier_type):
            return identifier
        if field == "device_id" and ("DEVICE" in identifier_type or "NHTSA" in identifier_type):
            return identifier
    return None


def _virtual_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    values = _parse_key_value_text(row.get("fact_value"))
    if _blank(values.get("source_url")):
        source_url = _get_field(row, "source_url")
        if not _blank(source_url):
            values["source_url"] = source_url
    if not values.get("job_location") and row.get("job_location"):
        values["job_location"] = row.get("job_location")
    if not values.get("date") and row.get("award_start_date"):
        values["date"] = row.get("award_start_date")
    return values


def _parse_key_value_text(value: Any) -> dict[str, Any]:
    if not isinstance(value, str):
        return {}
    if "=" not in value:
        return {}
    result: dict[str, Any] = {}
    for part in re.split(r";\s*", value):
        if "=" not in part:
            continue
        key, raw_val = part.split("=", 1)
        key = _normalize_key(key)
        raw_val = raw_val.strip()
        if not key or not raw_val:
            continue
        result[key] = _coerce_scalar(raw_val)
    return result


def _normalize_key(value: str) -> str:
    key = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    aliases = {
        "sku": "channel_product_id",
        "mpn": "manufacturer_part_number",
        "pushed_at": "pushed_at",
        "release_date": "release_date",
    }
    return aliases.get(key, key)


def _coerce_scalar(value: str) -> Any:
    text = value.strip()
    if re.fullmatch(r"-?\d+", text):
        try:
            return int(text)
        except ValueError:
            return text
    if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        try:
            return float(text)
        except ValueError:
            return text
    return text


def _first_present(row: Mapping[str, Any], *fields: str | tuple[str, str]) -> Any:
    for field in fields:
        if isinstance(field, tuple):
            parent, child = field
            parent_value = row.get(parent)
            if isinstance(parent_value, Mapping) and not _blank(parent_value.get(child)):
                return parent_value.get(child)
            continue
        value = row.get(field)
        if not _blank(value):
            return value
    return None


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _dedupe_rows(rows: Sequence[dict[str, Any]], *, key_field: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get(key_field) or "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _stable_id(prefix: str, parts: Sequence[Any]) -> str:
    digest = hashlib.sha256("||".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
