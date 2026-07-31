from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s4_case_runtime import S4SourceGroundedInputPack  # noqa: E402


OUTPUT = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_source_grounded_input_pack_v1_0.json"
)
FROZEN_AT = "2026-07-29T10:30:00+08:00"
AS_OF = "2026-07-26T00:00:00Z"
DEMAND = "demand_authenticity_and_sustainability"
VALUE = "value_and_profit_capture"
RISK = "bottleneck_counterevidence_and_what_would_change"


def _stable_ref(prefix: str, payload: dict[str, Any]) -> str:
    return f"{prefix}_{canonical_digest(payload)[:24]}"


def _snapshot(
    source_id: str,
    *,
    source_url: str,
    title: str,
    published_at: str,
    retrieval_channel: str,
    locator: str,
    normalized_extract: str,
    full_document_sha256: str | None = None,
) -> dict[str, Any]:
    payload = {
        "source_id": source_id,
        "source_url": source_url,
        "title": title,
        "published_at": published_at,
        "retrieval_channel": retrieval_channel,
        "fetch_status": "success",
        "locator": locator,
        "normalized_extract": normalized_extract,
        "full_document_sha256": full_document_sha256,
    }
    digest = canonical_digest(payload)
    return {
        **payload,
        "source_snapshot_ref": f"s4_mu_source_snapshot_{digest[:24]}",
        "normalized_locator_snapshot_digest": digest,
    }


def _evidence(
    snapshots: dict[str, dict[str, Any]],
    source_id: str,
    *,
    cells: tuple[str, ...],
    role: str,
    statement: str,
    period_or_version: str,
    authority_scope: str,
    claim_boundary: str,
    local_id: str,
) -> dict[str, Any]:
    source = snapshots[source_id]
    payload = {
        "entity_ref": "MU",
        "program_cell_ids": list(cells),
        "evidence_role": role,
        "statement": statement,
        "period_or_version": period_or_version,
        "source_url": source["source_url"],
        "citation": source["locator"],
        "parser_lineage": {
            "source_snapshot_ref": source["source_snapshot_ref"],
            "adapter": source["retrieval_channel"],
            "normalized_extract_digest": source[
                "normalized_locator_snapshot_digest"
            ],
        },
        "authority_scope": authority_scope,
        "claim_boundary": claim_boundary,
    }
    return {
        **payload,
        "evidence_ref": _stable_ref(
            f"s4_mu_evidence_{local_id}", payload
        ),
    }


def _numeric(
    snapshots: dict[str, dict[str, Any]],
    evidence_ref: str,
    source_id: str,
    *,
    cells: tuple[str, ...],
    metric_family: str,
    value: str,
    period: str,
    segment_ref: str = "__company_total__",
    comparison_operator: str = "equal",
    currency: str | None = "USD",
    unit: str = "USD_millions",
    scale_multiplier: int = 1_000_000,
    cannot_support: tuple[str, ...] = (
        "HBM_specific_revenue_or_profit",
        "named_customer_allocation_or_concentration",
    ),
) -> dict[str, Any]:
    source = snapshots[source_id]
    payload = {
        "entity_ref": "MU",
        "segment_ref": segment_ref,
        "program_cell_ids": list(cells),
        "metric_family": metric_family,
        "value": value,
        "comparison_operator": comparison_operator,
        "currency": currency,
        "unit": unit,
        "scale_multiplier": scale_multiplier,
        "period": period,
        "source_ref": evidence_ref,
        "source_url": source["source_url"],
        "source_coordinate": source["locator"],
        "parser_lineage": {
            "source_snapshot_ref": source["source_snapshot_ref"],
            "adapter": source["retrieval_channel"],
        },
        "exact_value_authority": True,
        "cannot_support": list(cannot_support),
    }
    return {
        **payload,
        "numeric_ref": _stable_ref(
            f"s4_mu_numeric_{metric_family}", payload
        ),
    }


def _route(
    snapshots: dict[str, dict[str, Any]],
    source_id: str,
    *,
    route_name: str,
    adapter: str,
    cells: tuple[str, ...],
    parser_status: str,
    row_count: int,
) -> dict[str, Any]:
    source = snapshots[source_id]
    payload = {
        "route_id": f"p34_route::mu_{route_name}::01::{adapter}",
        "program_cell_ids": list(cells),
        "attempted_url_or_query": source["source_url"],
        "fetch_status": source["fetch_status"],
        "parser_status": parser_status,
        "row_count": row_count,
        "failure_reason": None,
        "source_snapshot_ref": source["source_snapshot_ref"],
        "route_execution_status": parser_status,
        "promotion_without_execution_allowed": False,
        "executed_at": FROZEN_AT,
    }
    return {
        **payload,
        "route_receipt_ref": _stable_ref(
            "s4_mu_route_receipt", payload
        ),
    }


def _graph(
    snapshots: dict[str, dict[str, Any]],
    source_id: str,
    *,
    cells: tuple[str, ...],
    from_ref: str,
    to_ref: str,
    edge_semantics: str,
    boundary: str,
) -> dict[str, Any]:
    source = snapshots[source_id]
    payload = {
        "entity_ref": "MU",
        "program_cell_ids": list(cells),
        "from_ref": from_ref,
        "to_ref": to_ref,
        "edge_semantics": edge_semantics,
        "direction": "from_to",
        "as_of": "2026-07-26",
        "source_ref": source["source_snapshot_ref"],
        "source_url": source["source_url"],
        "boundary": boundary,
        "graph_edge_is_direct_evidence": False,
        "inferred_edge": False,
    }
    return {
        **payload,
        "graph_edge_ref": _stable_ref("s4_mu_graph_edge", payload),
    }


def _gap(
    *,
    cells: tuple[str, ...],
    code: str,
    gap_type: str,
    reason: str,
    followup_ref: str,
) -> dict[str, Any]:
    payload = {
        "program_cell_ids": list(cells),
        "gap_code": code,
        "gap_type": gap_type,
        "reason": reason,
        "followup_ref": followup_ref,
        "terminal_for_truthful_boundary": True,
    }
    return {
        **payload,
        "gap_ref": _stable_ref("s4_mu_gap", payload),
    }


def build_source_pack() -> dict[str, Any]:
    source_rows = [
        _snapshot(
            "mu_q3_fy26_results_release",
            source_url=(
                "https://investors.micron.com/news-releases/"
                "news-release-details/micron-technology-inc-reports-"
                "record-results-third-quarter"
            ),
            title=(
                "Micron Technology, Inc. Reports Record Results for the "
                "Third Quarter of Fiscal 2026"
            ),
            published_at="2026-06-24",
            retrieval_channel="official_ir_html_table_and_statement_parser",
            locator=(
                "lines 285-310, 298-346 and GAAP/non-GAAP financial tables"
            ),
            normalized_extract=(
                "FQ3-26 revenue USD41,456m, GAAP gross profit USD35,056m, "
                "GAAP operating income USD33,318m, GAAP net income "
                "USD28,243m and operating cash flow USD25,388m. Net capital "
                "expenditures were USD7,084m and adjusted free cash flow was "
                "USD18,304m. HBM4 was in high-volume shipment for a lead "
                "customer platform with qualification samples to multiple "
                "end-customers."
            ),
        ),
        _snapshot(
            "mu_q3_fy26_prepared_remarks",
            source_url=(
                "https://investors.micron.com/static-files/"
                "631b1a32-5537-46ae-8f40-82e42fc79dfe"
            ),
            title="Micron Fiscal Q3 2026 Earnings Call Prepared Remarks",
            published_at="2026-06-24",
            retrieval_channel="direct_http_pdf_text_and_page_locator",
            locator=(
                "PDF pages 1-10; SCA pages 1-3, supply pages 4-5, "
                "financials pages 7-9"
            ),
            normalized_extract=(
                "Micron disclosed 16 strategic customer agreements, usually "
                "five-year terms, tight DRAM and NAND conditions beyond "
                "calendar 2027, FQ3 DRAM revenue about USD31.3bn, company "
                "and business-unit results, USD8.6bn ending inventory and "
                "120 inventory days."
            ),
            full_document_sha256=(
                "a3ce62b84a059e35fae80c2bfd5c89f9"
                "af334193fd6aceff698fc3008e7d4c27"
            ),
        ),
        _snapshot(
            "mu_q3_fy26_earnings_deck",
            source_url=(
                "https://investors.micron.com/static-files/"
                "2354ecda-77a0-4ddd-8462-a631eb491356"
            ),
            title="Micron Fiscal Q3 2026 Earnings Presentation",
            published_at="2026-06-24",
            retrieval_channel="direct_http_pdf_text_and_page_locator",
            locator=(
                "PDF pages 3-7 and financial appendix; demand, supply and "
                "HBM trade-ratio statements"
            ),
            normalized_extract=(
                "The deck states DRAM and NAND demand exceeded supply, "
                "tightness was expected beyond 2027, greenfield constraints "
                "limit supply, and each HBM generation increases trade ratio "
                "and pressure on non-HBM supply."
            ),
            full_document_sha256=(
                "29468a786fa4a9c7728735ea8e3ad5853"
                "bb1375a297c636e86e6a4dd3b155929"
            ),
        ),
        _snapshot(
            "mu_q3_fy26_10q",
            source_url=(
                "https://investors.micron.com/static-files/"
                "e18b3c93-8b84-411b-94eb-517b018d9dab"
            ),
            title="Micron Technology Fiscal Q3 2026 Form 10-Q",
            published_at="2026-06-30",
            retrieval_channel="official_filing_pdf_table_and_risk_parser",
            locator=(
                "PDF consolidated statements and risk factors, especially "
                "page 6 HBM demand and manufacturing intensity"
            ),
            normalized_extract=(
                "The filing provides issuer GAAP statements and cautions "
                "that long-term generative-AI/HBM demand may fluctuate; HBM "
                "requires more wafers and cleanroom space per bit than "
                "conventional DRAM and capacity can be shifted if HBM demand "
                "weakens."
            ),
            full_document_sha256=(
                "713a12cd52689640bcc0df9e131d31c3"
                "db8c26b794cd2e8219fd727cf4cbd45a"
            ),
        ),
        _snapshot(
            "mu_hbm4_high_volume_release",
            source_url=(
                "https://investors.micron.com/news-releases/"
                "news-release-details/micron-high-volume-production-hbm4-"
                "designed-nvidia-vera-rubin"
            ),
            title=(
                "Micron in High-Volume Production of HBM4 Designed for "
                "NVIDIA Vera Rubin"
            ),
            published_at="2026-03-16",
            retrieval_channel="official_ir_product_release_html_parser",
            locator="lines 285-300 and footnotes 327-333",
            normalized_extract=(
                "Micron began volume shipment of HBM4 36GB 12H in calendar "
                "Q1 2026, designed for NVIDIA Vera Rubin, with over 11 Gb/s "
                "pin speed, more than 2.8 TB/s bandwidth and greater than "
                "20% power-efficiency improvement versus HBM3E under the "
                "stated test boundary."
            ),
        ),
        _snapshot(
            "mu_hbm_product_page",
            source_url="https://www.micron.com/products/memory/hbm",
            title="Micron High-Bandwidth Memory Product Page",
            published_at="2026-07-26",
            retrieval_channel="official_product_page_context_parser",
            locator="HBM4 high-volume-production section, lines 332-348",
            normalized_extract=(
                "The product page identifies HBM4 36GB 12H as in high-volume "
                "production and states more than 11 Gb/s pin speed, greater "
                "than 2.8 TB/s bandwidth and greater than 20% power "
                "efficiency improvement versus HBM3E."
            ),
        ),
    ]
    snapshots = {row["source_id"]: row for row in source_rows}

    routes = [
        _route(
            snapshots,
            "mu_q3_fy26_results_release",
            route_name="hbm4_shipment_and_qualification",
            adapter="issuer_earnings_release_statement_adapter",
            cells=(DEMAND, RISK),
            parser_status="executed_promoted_issuer_evidence",
            row_count=1,
        ),
        _route(
            snapshots,
            "mu_hbm4_high_volume_release",
            route_name="hbm4_product_generation_and_platform",
            adapter="official_product_release_adapter",
            cells=(DEMAND, RISK),
            parser_status="executed_promoted_issuer_evidence_and_context",
            row_count=3,
        ),
        _route(
            snapshots,
            "mu_q3_fy26_prepared_remarks",
            route_name="strategic_customer_agreements_and_supply",
            adapter="official_prepared_remarks_adapter",
            cells=(DEMAND, RISK),
            parser_status="executed_promoted_issuer_evidence",
            row_count=2,
        ),
        _route(
            snapshots,
            "mu_q3_fy26_results_release",
            route_name="gaap_company_and_business_unit_financials",
            adapter="issuer_earnings_release_table_adapter",
            cells=(VALUE, RISK),
            parser_status="executed_promoted_issuer_evidence_and_numeric",
            row_count=14,
        ),
        _route(
            snapshots,
            "mu_q3_fy26_prepared_remarks",
            route_name="pricing_mix_inventory_and_cash",
            adapter="official_prepared_remarks_numeric_adapter",
            cells=(VALUE, RISK),
            parser_status="executed_promoted_issuer_evidence_and_numeric",
            row_count=4,
        ),
        _route(
            snapshots,
            "mu_q3_fy26_10q",
            route_name="gaap_filing_and_hbm_risk",
            adapter="official_filing_table_and_risk_adapter",
            cells=(DEMAND, VALUE, RISK),
            parser_status="executed_promoted_issuer_evidence_and_counterevidence",
            row_count=2,
        ),
        _route(
            snapshots,
            "mu_q3_fy26_earnings_deck",
            route_name="memory_supply_constraints_and_hbm_trade_ratio",
            adapter="official_earnings_deck_statement_adapter",
            cells=(DEMAND, RISK),
            parser_status="executed_promoted_issuer_counterevidence",
            row_count=1,
        ),
        _route(
            snapshots,
            "mu_hbm_product_page",
            route_name="hbm4_product_context",
            adapter="official_product_page_context_adapter",
            cells=(DEMAND, RISK),
            parser_status="executed_context_only_product_scope",
            row_count=1,
        ),
    ]

    evidence_rows = [
        _evidence(
            snapshots,
            "mu_q3_fy26_results_release",
            cells=(DEMAND, RISK),
            role="issuer_HBM_shipment_and_qualification_signal",
            statement=(
                "Micron stated that HBM4 was in high-volume shipments for "
                "its lead customer's platform and that qualification samples "
                "had shipped to multiple end-customers."
            ),
            period_or_version="2026-06-24",
            authority_scope="issuer_product_status_statement",
            claim_boundary=(
                "Supports shipment and qualification status only; no named "
                "customer, HBM revenue, margin or customer share."
            ),
            local_id="hbm4_shipment_qualification",
        ),
        _evidence(
            snapshots,
            "mu_hbm4_high_volume_release",
            cells=(DEMAND, RISK),
            role="official_HBM_product_generation_and_platform_signal",
            statement=(
                "Micron stated that it began volume shipment of HBM4 36GB "
                "12H in calendar Q1 2026 and that the product was designed "
                "for NVIDIA Vera Rubin."
            ),
            period_or_version="calendar_Q1_2026",
            authority_scope="issuer_product_release",
            claim_boundary=(
                "Product and platform context only; does not prove NVIDIA "
                "purchase volume, revenue attribution or exclusivity."
            ),
            local_id="hbm4_volume_vera_rubin",
        ),
        _evidence(
            snapshots,
            "mu_q3_fy26_prepared_remarks",
            cells=(DEMAND, RISK),
            role="issuer_customer_commitment_and_supply_signal",
            statement=(
                "Micron disclosed 16 strategic customer agreements, "
                "typically with five-year terms through calendar 2030, to "
                "provide customers contracted supply assurance."
            ),
            period_or_version="FQ3_2026",
            authority_scope="issuer_company_level_customer_agreement_statement",
            claim_boundary=(
                "The agreements are company-level and cannot be attributed "
                "to HBM, a named customer, product generation or margin."
            ),
            local_id="company_sca_supply_assurance",
        ),
        _evidence(
            snapshots,
            "mu_q3_fy26_earnings_deck",
            cells=(DEMAND, RISK),
            role="memory_cycle_supply_counterevidence",
            statement=(
                "Micron stated that DRAM and NAND demand exceeded supply, "
                "tight conditions were expected beyond calendar 2027, and "
                "HBM trade-ratio growth pressures non-HBM supply."
            ),
            period_or_version="2026-06-24",
            authority_scope="issuer_industry_outlook_and_supply_statement",
            claim_boundary=(
                "Forward-looking issuer outlook; does not establish realized "
                "future pricing, HBM demand durability or competitor supply."
            ),
            local_id="memory_supply_cycle",
        ),
        _evidence(
            snapshots,
            "mu_q3_fy26_results_release",
            cells=(VALUE, RISK),
            role="issuer_financial_statement",
            statement=(
                "Micron reported FQ3-26 company GAAP revenue, gross profit, "
                "operating income, net income and operating cash flow, plus "
                "business-unit revenue and margin tables."
            ),
            period_or_version="FQ3_2026",
            authority_scope="issuer_exact_financial_table",
            claim_boundary=(
                "Company and disclosed business-unit scope only; none is an "
                "HBM-specific revenue or profit row."
            ),
            local_id="gaap_and_business_unit_financials",
        ),
        _evidence(
            snapshots,
            "mu_q3_fy26_prepared_remarks",
            cells=(VALUE, RISK),
            role="official_pricing_mix_inventory_and_cash_disclosure",
            statement=(
                "Micron attributed FQ3 DRAM and business-unit changes to "
                "pricing, bit shipments and mix, and disclosed USD8.6bn "
                "ending inventory with 120 inventory days."
            ),
            period_or_version="FQ3_2026",
            authority_scope="issuer_prepared_remarks_with_scope_labels",
            claim_boundary=(
                "Does not permit an HBM-specific price-volume-mix "
                "decomposition or product profit allocation."
            ),
            local_id="pricing_mix_inventory",
        ),
        _evidence(
            snapshots,
            "mu_q3_fy26_10q",
            cells=(DEMAND, RISK),
            role="official_HBM_demand_and_manufacturing_counterevidence",
            statement=(
                "Micron cautioned that the long-term trajectory of "
                "generative-AI/HBM demand is unknown and may fluctuate, while "
                "HBM requires more wafers and cleanroom space per bit than "
                "conventional DRAM."
            ),
            period_or_version="FQ3_2026_10Q",
            authority_scope="issuer_regulatory_filing_risk_factor",
            claim_boundary=(
                "Risk mechanism and uncertainty boundary; it does not "
                "quantify probability, impact, yield or future capacity."
            ),
            local_id="hbm_demand_manufacturing_risk",
        ),
    ]
    evidence_by_id = {
        row["evidence_role"]: row["evidence_ref"] for row in evidence_rows
    }
    financial_ref = evidence_by_id["issuer_financial_statement"]
    pricing_ref = evidence_by_id[
        "official_pricing_mix_inventory_and_cash_disclosure"
    ]

    numeric_rows = [
        _numeric(
            snapshots,
            financial_ref,
            "mu_q3_fy26_results_release",
            cells=(VALUE, RISK),
            metric_family=metric,
            value=value,
            period="FQ3_2026",
        )
        for metric, value in (
            ("revenue", "41456"),
            ("gross_profit", "35056"),
            ("operating_income", "33318"),
            ("net_income", "28243"),
            ("operating_cash_flow", "25388"),
        )
    ]
    numeric_rows.extend(
        [
            _numeric(
                snapshots,
                financial_ref,
                "mu_q3_fy26_results_release",
                cells=(VALUE, RISK),
                metric_family="gaap_gross_margin",
                value="84.6",
                period="FQ3_2026",
                currency=None,
                unit="percent",
                scale_multiplier=1,
            ),
            _numeric(
                snapshots,
                financial_ref,
                "mu_q3_fy26_results_release",
                cells=(VALUE, RISK),
                metric_family="capital_expenditures_net",
                value="7084",
                period="FQ3_2026",
                cannot_support=(
                    "gross_PPE_additions_without_reconciliation",
                    "HBM_specific_capex",
                    "HBM_specific_free_cash_flow",
                ),
            ),
            _numeric(
                snapshots,
                financial_ref,
                "mu_q3_fy26_results_release",
                cells=(VALUE, RISK),
                metric_family="adjusted_free_cash_flow",
                value="18304",
                period="FQ3_2026",
                cannot_support=(
                    "GAAP_free_cash_flow_label",
                    "HBM_specific_cash_flow",
                ),
            ),
            _numeric(
                snapshots,
                pricing_ref,
                "mu_q3_fy26_prepared_remarks",
                cells=(VALUE, RISK),
                metric_family="inventory",
                value="8567",
                period="2026-05-28",
            ),
            _numeric(
                snapshots,
                pricing_ref,
                "mu_q3_fy26_prepared_remarks",
                cells=(VALUE, RISK),
                metric_family="inventory_days",
                value="120",
                period="FQ3_2026",
                currency=None,
                unit="days",
                scale_multiplier=1,
            ),
            _numeric(
                snapshots,
                financial_ref,
                "mu_q3_fy26_results_release",
                cells=(VALUE, RISK),
                metric_family="revenue",
                value="13769",
                period="FQ3_2026",
                segment_ref="Cloud_Memory_Business_Unit",
            ),
            _numeric(
                snapshots,
                financial_ref,
                "mu_q3_fy26_results_release",
                cells=(VALUE, RISK),
                metric_family="gross_margin",
                value="83",
                period="FQ3_2026",
                segment_ref="Cloud_Memory_Business_Unit",
                currency=None,
                unit="percent",
                scale_multiplier=1,
            ),
            _numeric(
                snapshots,
                financial_ref,
                "mu_q3_fy26_results_release",
                cells=(VALUE, RISK),
                metric_family="revenue",
                value="11524",
                period="FQ3_2026",
                segment_ref="Core_Data_Center_Business_Unit",
            ),
            _numeric(
                snapshots,
                financial_ref,
                "mu_q3_fy26_results_release",
                cells=(VALUE, RISK),
                metric_family="gross_margin",
                value="87",
                period="FQ3_2026",
                segment_ref="Core_Data_Center_Business_Unit",
                currency=None,
                unit="percent",
                scale_multiplier=1,
            ),
            _numeric(
                snapshots,
                pricing_ref,
                "mu_q3_fy26_prepared_remarks",
                cells=(VALUE, RISK),
                metric_family="dram_revenue",
                value="31300",
                period="FQ3_2026",
                segment_ref="DRAM",
                comparison_operator="approximately_equal",
            ),
            _numeric(
                snapshots,
                pricing_ref,
                "mu_q3_fy26_prepared_remarks",
                cells=(VALUE, RISK),
                metric_family="dram_revenue_share",
                value="76",
                period="FQ3_2026",
                segment_ref="DRAM",
                currency=None,
                unit="percent",
                scale_multiplier=1,
            ),
        ]
    )
    numeric_index = {
        (row["metric_family"], row["segment_ref"]): row["numeric_ref"]
        for row in numeric_rows
    }

    derived_specs = [
        {
            "metric": "gaap_gross_margin_recomputed",
            "value": "84.56",
            "unit": "percent",
            "formula": "gross_profit/revenue*100",
            "input_numeric_refs": [
                numeric_index[("gross_profit", "__company_total__")],
                numeric_index[("revenue", "__company_total__")],
            ],
            "program_cell_ids": [VALUE, RISK],
            "scope": "MU_company_FQ3_2026_GAAP",
            "cannot_support": ["HBM_specific_gross_margin"],
        },
        {
            "metric": "gaap_operating_margin_recomputed",
            "value": "80.37",
            "unit": "percent",
            "formula": "operating_income/revenue*100",
            "input_numeric_refs": [
                numeric_index[("operating_income", "__company_total__")],
                numeric_index[("revenue", "__company_total__")],
            ],
            "program_cell_ids": [VALUE, RISK],
            "scope": "MU_company_FQ3_2026_GAAP",
            "cannot_support": ["HBM_specific_operating_margin"],
        },
        {
            "metric": "adjusted_free_cash_flow_recomputed",
            "value": "18304",
            "unit": "USD_millions",
            "formula": "operating_cash_flow-capital_expenditures_net",
            "input_numeric_refs": [
                numeric_index[
                    ("operating_cash_flow", "__company_total__")
                ],
                numeric_index[
                    ("capital_expenditures_net", "__company_total__")
                ],
            ],
            "program_cell_ids": [VALUE, RISK],
            "scope": "MU_company_FQ3_2026_non_GAAP_reconciliation",
            "cannot_support": [
                "GAAP_free_cash_flow_label",
                "HBM_specific_cash_flow",
            ],
        },
        {
            "metric": "net_capital_intensity_recomputed",
            "value": "17.09",
            "unit": "percent",
            "formula": "capital_expenditures_net/revenue*100",
            "input_numeric_refs": [
                numeric_index[
                    ("capital_expenditures_net", "__company_total__")
                ],
                numeric_index[("revenue", "__company_total__")],
            ],
            "program_cell_ids": [VALUE, RISK],
            "scope": "MU_company_FQ3_2026",
            "cannot_support": ["HBM_specific_capital_intensity"],
        },
    ]
    derived_metrics = [
        {
            **row,
            "derived_metric_ref": _stable_ref("s4_mu_derived", row),
        }
        for row in derived_specs
    ]

    graph_edges = [
        _graph(
            snapshots,
            "mu_hbm4_high_volume_release",
            cells=(DEMAND, RISK),
            from_ref="MU",
            to_ref="HBM4_36GB_12H",
            edge_semantics="product_platform",
            boundary="Issuer product context; no HBM financial attribution.",
        ),
        _graph(
            snapshots,
            "mu_hbm4_high_volume_release",
            cells=(DEMAND, RISK),
            from_ref="HBM4_36GB_12H",
            to_ref="NVIDIA_Vera_Rubin",
            edge_semantics="designed_for_platform",
            boundary=(
                "Designed-for relationship only; no named purchase volume, "
                "revenue, exclusivity or qualification conclusion."
            ),
        ),
        _graph(
            snapshots,
            "mu_q3_fy26_results_release",
            cells=(DEMAND, RISK),
            from_ref="MU_HBM4",
            to_ref="anonymous_lead_customer_platform",
            edge_semantics="high_volume_shipment_status",
            boundary=(
                "Customer remains unnamed; no identity, concentration, "
                "volume or economics may be inferred."
            ),
        ),
        _graph(
            snapshots,
            "mu_q3_fy26_results_release",
            cells=(DEMAND, RISK),
            from_ref="MU_HBM4",
            to_ref="multiple_unnamed_end_customers",
            edge_semantics="qualification_sample_status",
            boundary=(
                "Qualification-sample context only; no conversion, timing, "
                "share or revenue inference."
            ),
        ),
    ]

    typed_gaps = [
        _gap(
            cells=(DEMAND, VALUE),
            code="cannot_infer_HBM_specific_revenue",
            gap_type="issuer_scope_not_disclosed",
            reason=(
                "Company, DRAM and business-unit revenue are not HBM "
                "product revenue."
            ),
            followup_ref="issuer_disclosed_HBM_revenue_with_period_and_scope",
        ),
        _gap(
            cells=(VALUE, RISK),
            code="cannot_infer_HBM_specific_gross_or_operating_profit",
            gap_type="issuer_scope_not_disclosed",
            reason=(
                "Company and business-unit margins do not identify HBM "
                "revenue, cost or profit."
            ),
            followup_ref="issuer_disclosed_HBM_profitability_bridge",
        ),
        _gap(
            cells=(DEMAND, RISK),
            code="cannot_infer_customer_identity_or_concentration",
            gap_type="customer_identity_withheld",
            reason=(
                "The lead platform and multiple end-customers are not named "
                "in the shipment and qualification statement."
            ),
            followup_ref="issuer_or_customer_named_HBM_contract_disclosure",
        ),
        _gap(
            cells=(DEMAND, RISK),
            code="cannot_infer_SCA_HBM_attribution",
            gap_type="scope_bridge_absent",
            reason=(
                "Sixteen strategic customer agreements are company-level "
                "and are not identified as HBM agreements."
            ),
            followup_ref="issuer_SCA_product_scope_and_value_bridge",
        ),
        _gap(
            cells=(VALUE, RISK),
            code="cannot_infer_HBM_price_volume_mix_decomposition",
            gap_type="product_inputs_absent",
            reason=(
                "DRAM pricing, bits and mix do not isolate HBM price, volume "
                "or mix."
            ),
            followup_ref="issuer_HBM_price_volume_mix_inputs",
        ),
        _gap(
            cells=(DEMAND, RISK),
            code="cannot_infer_HBM_demand_durability",
            gap_type="forward_demand_uncertain",
            reason=(
                "The 10-Q explicitly states that long-term AI/HBM demand may "
                "fluctuate."
            ),
            followup_ref="period_comparable_HBM_shipments_and_inventory",
        ),
        _gap(
            cells=(DEMAND, RISK),
            code="cannot_infer_HBM_capacity_yield_probability_and_impact",
            gap_type="quantified_capacity_inputs_absent",
            reason=(
                "Manufacturing intensity is disclosed, but capacity, yield, "
                "probability and financial impact are not quantified."
            ),
            followup_ref="issuer_HBM_capacity_yield_and_capex_bridge",
        ),
        _gap(
            cells=(RISK,),
            code="cannot_infer_export_control_impact",
            gap_type="case_specific_regulatory_bridge_absent",
            reason=(
                "The selected source set does not quantify HBM-specific "
                "export-control exposure or financial impact."
            ),
            followup_ref="official_case_specific_export_control_assessment",
        ),
        _gap(
            cells=(RISK,),
            code="cannot_infer_independent_counterevidence",
            gap_type="independent_official_followup_pending",
            reason=(
                "Current accepted fact authority is issuer-official; an "
                "independent official customer, supplier or regulator "
                "followup remains absent."
            ),
            followup_ref="independent_official_HBM_counterevidence_route",
        ),
    ]

    payload = {
        "schema_version": (
            "fin_ia_0_1_s4_t04_source_grounded_input_pack_v1_0"
        ),
        "contract_ref": "fin01.s4.source_grounded_case_input:v1",
        "pack_id": "FIN-IA-0.1-S4-T06-MU-SOURCE-GROUNDED-INPUT-R1",
        "frozen_at": FROZEN_AT,
        "status": "source_routes_executed_issuer_bound_input_head_ready",
        "case_ticker": "MU",
        "legal_name": "Micron Technology, Inc.",
        "issuer_identifier": "CIK0000723125",
        "as_of": AS_OF,
        "source_snapshots": source_rows,
        "route_execution_receipts": routes,
        "evidence_rows": evidence_rows,
        "numeric_rows": numeric_rows,
        "derived_metrics": derived_metrics,
        "graph_edges": graph_edges,
        "typed_gaps": typed_gaps,
        "cannot_infer_boundaries": [
            "No company, DRAM, CMBU or CDBU revenue or profit is allocated to HBM.",
            "No strategic customer agreement is attributed to HBM or a named customer.",
            "No HBM customer identity, concentration, share, revenue or margin is inferred.",
            "No forward supply, pricing, demand durability, capacity or yield probability is promoted as realized fact.",
            "Product and platform graph rows are context-only and never direct Evidence.",
        ],
        "authority_boundary": {
            "evidence": (
                "issuer filing, earnings release, prepared remarks or "
                "official product release with exact locator and lineage"
            ),
            "numeric": (
                "exact issuer, disclosed segment, period, currency, unit "
                "and source coordinate"
            ),
            "graph": "context_only_not_direct_evidence",
            "model_output_is_source_authority": False,
            "HBM_economics_require_exact_issuer_product_rows": True,
            "quality_findings_are_nonterminal_unless_truth_or_lineage_breaks": True,
        },
        "observed_counts": {
            "source_snapshots": len(source_rows),
            "route_execution_receipts": len(routes),
            "evidence_rows": len(evidence_rows),
            "numeric_rows": len(numeric_rows),
            "derived_metrics": len(derived_metrics),
            "graph_edges": len(graph_edges),
            "typed_gaps": len(typed_gaps),
            "source_network_calls": 14,
            "model_calls": 0,
            "provider_calls": 0,
            "paid_calls": 0,
        },
    }
    payload["source_pack_digest"] = canonical_digest(payload)
    validated = S4SourceGroundedInputPack.model_validate(payload)
    return validated.model_dump(mode="json")


def main() -> int:
    payload = build_source_pack()
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "pass",
                "output": OUTPUT.relative_to(ROOT).as_posix(),
                "source_pack_digest": payload["source_pack_digest"],
                "counts": payload["observed_counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
