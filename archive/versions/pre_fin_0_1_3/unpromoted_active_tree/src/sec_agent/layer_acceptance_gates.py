from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping


R26_SECOND_LAYER_ACCEPTANCE_SCHEMA_VERSION = "finsight_r26_second_layer_acceptance_gate_v0_1"
R26_THIRD_LAYER_ACCEPTANCE_SCHEMA_VERSION = "finsight_r26_third_layer_acceptance_gate_v0_1"
R26_COMBINED_ACCEPTANCE_SCHEMA_VERSION = "finsight_r26_second_third_layer_acceptance_gate_v0_1"
SECOND_THIRD_LAYER_REAL_SOURCE_READINESS_SCHEMA_VERSION = "finsight_second_third_layer_real_source_readiness_gate_v0_1"
SECOND_THIRD_LAYER_REAL_SOURCE_READINESS_COMPANY_SCHEMA_VERSION = (
    "finsight_second_third_layer_real_source_readiness_company_v0_1"
)
SECOND_THIRD_LAYER_DEPTH_PARITY_SCHEMA_VERSION = "finsight_second_third_layer_depth_parity_matrix_v0_1"
SECOND_THIRD_LAYER_DEPTH_PARITY_COMPANY_SCHEMA_VERSION = "finsight_second_third_layer_depth_parity_company_v0_1"
SECOND_THIRD_LAYER_DEPTH_PARITY_BACKFILL_SCHEMA_VERSION = "finsight_second_third_layer_depth_parity_backfill_v0_1"

FORBIDDEN_PRODUCT_EXACT_CLAIMS = {
    "product_revenue",
    "sku_revenue",
    "product_sales",
    "unit_sales",
    "shipments",
    "ASP",
    "asp",
    "average_selling_price",
    "market_share",
    "sell_through",
    "channel_inventory",
    "backlog",
    "customer_order_value",
}

R17_SECOND_LAYER_SOURCE_ROLES = {
    "technical_product_spec",
    "product_generation_edge",
    "product_benchmark_proxy",
    "customer_deployment_proxy",
}

CAPITAL_CONTEXT_REQUIRED_SOURCE_ROLES = {
    "capital_structure_disclosure",
    "lagged_ownership_context",
    "working_capital_liquidity",
}

SEC_EVENT_REQUIRED_SOURCE_ROLES = {
    "securities_offering_filing_event",
    "insider_transaction_filing_event",
    "beneficial_ownership_filing_event",
    "proxy_governance_filing_event",
}

WORKING_CAPITAL_REQUIRED_METRICS = {
    "accounts_receivable",
    "inventory",
    "accounts_payable",
    "deferred_revenue",
    "current_assets",
    "current_liabilities",
    "cash_and_equivalents",
    "short_term_debt",
    "operating_cash_flow",
    "capital_expenditure_proxy",
}

PRODUCT_KPI_ALLOWED_CLOSEOUT_STATUSES = {
    "product_kpi_exact_ready",
    "business_segment_metric_ready",
    "geographic_or_non_product_metric_only",
    "product_kpi_exact_gap",
}

PASSING_PARSER_STATUSES = {
    "parser_pass",
    "projector_pass",
    "source_specific_context_parser_pass",
    "value_unit_period_product_citation_parser_pass",
    "public_context_probe_parser_pass",
    "normalized_record_projector_pass",
    "runtime_fact_allowed",
    "exact_fact_materialized",
    "bounded_context_fact_materialized",
    "context_rows_ready",
}

SECOND_LAYER_SOURCE_FILES = {
    "company_disclosed_product_profile_context_rows_v0_1.jsonl",
    "sec_product_taxonomy_context_rows_v0_1.jsonl",
    "official_product_surface_context_rows_v0_1.jsonl",
    "official_product_catalog_context_rows_v0_1.jsonl",
    "official_product_spec_context_rows_v0_1.jsonl",
    "official_business_asset_profile_context_rows_v0_1.jsonl",
    "company_disclosed_product_business_mix_runtime_rows_v0_1.jsonl",
    "company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
    "industry_operating_metric_slot_rows_v0_1.jsonl",
    "non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl",
    "r16_product_kpi_deep_repair_runtime_rows_v0_1.jsonl",
    "r17_product_family_evidence_runtime_rows_v0_1.jsonl",
    "targeted_official_technology_document_context_rows_v0_1.jsonl",
}

THIRD_LAYER_SOURCE_FILES = {
    "sec_financial_statement_metric_runtime_rows_v0_1.jsonl",
    "non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl",
    "capital_funding_ownership_context_rows_v0_1.jsonl",
    "sec_capital_market_event_context_rows_v0_1.jsonl",
}

PRODUCT_KPI_DEPTH_SOURCE_FILES = {
    "company_disclosed_product_business_mix_runtime_rows_v0_1.jsonl",
    "company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
    "industry_operating_metric_slot_rows_v0_1.jsonl",
    "non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl",
    "r16_product_kpi_deep_repair_runtime_rows_v0_1.jsonl",
    "r17_known_public_product_kpi_repair_runtime_rows_v0_1.jsonl",
}

PRODUCT_SPEC_DEPTH_SOURCE_FILES = {
    "company_disclosed_product_profile_context_rows_v0_1.jsonl",
    "official_product_surface_context_rows_v0_1.jsonl",
    "official_product_catalog_context_rows_v0_1.jsonl",
    "official_product_spec_context_rows_v0_1.jsonl",
    "official_business_asset_profile_context_rows_v0_1.jsonl",
    "r17_product_family_evidence_runtime_rows_v0_1.jsonl",
    "targeted_official_technology_document_context_rows_v0_1.jsonl",
}

CUSTOMER_DEPLOYMENT_DEPTH_SOURCE_FILES = {
    "targeted_supply_chain_official_relationship_context_rows_v0_1.jsonl",
    "public_contract_award_context_rows_v0_1.jsonl",
    "broad_public_contract_award_context_rows_v0_1.jsonl",
    "local_public_tender_context_rows_v0_1.jsonl",
    "r17_product_family_evidence_runtime_rows_v0_1.jsonl",
    "family_channel_distributor_context_rows_v0_1.jsonl",
    "channel_offer_context_rows_v0_1.jsonl",
    "broad_channel_offer_context_rows_v0_1.jsonl",
    "app_marketplace_context_rows_v0_1.jsonl",
    "broad_app_store_platform_context_rows_v0_1.jsonl",
    "official_customer_deployment_surface_context_rows_v0_1.jsonl",
    "official_api_exposure_bridge_context_rows_v0_1.jsonl",
    "public_official_api_context_rows_v0_1.jsonl",
    "targeted_regulated_auto_official_api_context_rows_v0_1.jsonl",
    "sec_financial_statement_metric_runtime_rows_v0_1.jsonl",
    "industry_operating_metric_slot_rows_v0_1.jsonl",
    "company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
    "non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl",
    "customer_operating_footprint_signal_runtime_rows_v0_1.jsonl",
    "filing_operating_footprint_context_rows_v0_1.jsonl",
    "official_business_asset_profile_context_rows_v0_1.jsonl",
}

CAPITAL_MARKET_DETAIL_DEPTH_SOURCE_FILES = {
    "capital_funding_ownership_context_rows_v0_1.jsonl",
    "sec_capital_market_event_context_rows_v0_1.jsonl",
    "non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl",
}

MARKET_LIQUIDITY_DEPTH_SOURCE_FILES = {
    "market_liquidity_driver_context_rows_v0_1.jsonl",
    "market_liquidity_context_rows_v0_1.jsonl",
    "market_price_volume_context_rows_v0_1.jsonl",
    "short_interest_context_rows_v0_1.jsonl",
    "options_liquidity_context_rows_v0_1.jsonl",
    "etf_factor_flow_context_rows_v0_1.jsonl",
    "credit_spread_context_rows_v0_1.jsonl",
}

DEPTH_PARITY_DIMENSIONS = (
    "product_kpi_depth",
    "product_spec_depth",
    "customer_deployment_depth",
    "capital_market_detail_depth",
    "market_liquidity_depth",
)


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    p = Path(path)
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def build_second_layer_acceptance_gate(
    *,
    product_graph_summary: Mapping[str, Any],
    product_slots: Iterable[Mapping[str, Any]],
    product_graph_edges: Iterable[Mapping[str, Any]],
    product_kpi_diagnostic_summary: Mapping[str, Any],
    product_kpi_closeout_rows: Iterable[Mapping[str, Any]],
    r17_product_family_evidence_rows: Iterable[Mapping[str, Any]],
    r17_product_family_evidence_summary: Mapping[str, Any],
    company_count: int = 603,
) -> dict[str, Any]:
    slots = [dict(row) for row in product_slots if isinstance(row, Mapping)]
    edges = [dict(row) for row in product_graph_edges if isinstance(row, Mapping)]
    closeout_rows = [dict(row) for row in product_kpi_closeout_rows if isinstance(row, Mapping)]
    r17_rows = [dict(row) for row in r17_product_family_evidence_rows if isinstance(row, Mapping)]

    slot_tickers = {str(row.get("ticker") or "").upper() for row in slots if row.get("ticker")}
    closeout_tickers = {str(row.get("ticker") or "").upper() for row in closeout_rows if row.get("ticker")}
    slot_status_counts = Counter(str(row.get("slot_status") or "") for row in slots)
    closeout_status_counts = Counter(str(row.get("status") or "") for row in closeout_rows)
    edge_type_counts = Counter(_edge_type(row) for row in edges)
    r17_source_role_counts = Counter(str(row.get("source_role") or "") for row in r17_rows)
    product_slot_count = int(product_graph_summary.get("product_slot_count") or len(slots))
    family_bound_slot_count = max(
        int(product_graph_summary.get("with_family_bound_runtime_slot_count") or 0),
        sum(1 for row in slots if _slot_has_family_binding(row)),
    )
    url_or_raw_ref_slot_count = max(
        int(product_graph_summary.get("with_url_slot_count") or 0),
        sum(1 for row in slots if _slot_has_url_or_raw_ref(row)),
    )

    relationship_coverage = {
        "competes_with": edge_type_counts.get("COMPETES_WITH", 0),
        "supplier_or_input_edge": sum(
            edge_type_counts.get(edge_type, 0)
            for edge_type in (
                "COMPONENT_INPUT_TO",
                "ENABLES_PRODUCTION_FOR",
                "INFRASTRUCTURE_SUPPLIER_TO",
                "MANUFACTURING_DEPENDENCY_FOR",
                "INPUT_OR_COMPLEMENT_TO",
            )
        ),
        "generation_successor_signal": r17_source_role_counts.get("product_generation_edge", 0),
        "customer_deployment_signal": r17_source_role_counts.get("customer_deployment_proxy", 0),
        "benchmark_signal": r17_source_role_counts.get("product_benchmark_proxy", 0),
        "technical_spec_signal": r17_source_role_counts.get("technical_product_spec", 0),
    }

    r17_nonfinancial_violations = [
        _row_id(row)
        for row in r17_rows
        if row.get("source_role") in R17_SECOND_LAYER_SOURCE_ROLES
        and (
            row.get("exact_financial_fact_authority") is True
            or row.get("can_support_company_exact_fact") is True
            or not FORBIDDEN_PRODUCT_EXACT_CLAIMS.intersection({str(item) for item in row.get("forbidden_claims") or []})
        )
    ]

    closeout_invalid_status = [
        str(row.get("ticker") or "")
        for row in closeout_rows
        if str(row.get("status") or "") not in PRODUCT_KPI_ALLOWED_CLOSEOUT_STATUSES
    ]

    checks = {
        "product_graph_summary_pass": (product_graph_summary.get("status") == "pass")
        and ((product_graph_summary.get("validation") or {}).get("status") == "pass"),
        "company_product_slot_coverage": len(slot_tickers) >= company_count,
        "all_slots_family_bound": family_bound_slot_count >= product_slot_count > 0,
        "all_slots_have_url_or_raw_ref": url_or_raw_ref_slot_count >= product_slot_count > 0,
        "product_kpi_closeout_covers_company_universe": len(closeout_tickers) >= company_count,
        "product_kpi_gaps_classified": int(product_kpi_diagnostic_summary.get("unclassified_count") or 0) == 0
        and not closeout_invalid_status,
        "second_layer_signal_roles_present": all(r17_source_role_counts.get(role, 0) > 0 for role in R17_SECOND_LAYER_SOURCE_ROLES),
        "relationship_edge_types_present": all(value > 0 for value in relationship_coverage.values()),
        "nonfinancial_signal_boundary_preserved": not r17_nonfinancial_violations,
    }

    failures = [
        {"check": check, "reason": _second_layer_failure_reason(check, locals())}
        for check, passed in checks.items()
        if not passed
    ]
    return {
        "schema_version": R26_SECOND_LAYER_ACCEPTANCE_SCHEMA_VERSION,
        "status": "pass" if not failures else "fail",
        "policy": (
            "Second-layer acceptance gate: product family slots, Product-KPI closeout, "
            "ProductRelationshipGraph, and R17 strong product signals must be parser-backed, "
            "classified, and boundary-preserving."
        ),
        "company_count": company_count,
        "checks": checks,
        "failures": failures,
        "metrics": {
            "product_slot_count": len(slots),
            "product_graph_summary_slot_count": product_slot_count,
            "family_bound_slot_count": family_bound_slot_count,
            "url_or_raw_ref_slot_count": url_or_raw_ref_slot_count,
            "product_slot_ticker_count": len(slot_tickers),
            "slot_status_counts": dict(sorted(slot_status_counts.items())),
            "relationship_edge_count": len(edges),
            "relationship_edge_type_counts": dict(sorted(edge_type_counts.items())),
            "relationship_coverage": relationship_coverage,
            "product_kpi_closeout_row_count": len(closeout_rows),
            "product_kpi_closeout_status_counts": dict(sorted(closeout_status_counts.items())),
            "product_kpi_diagnostic_status_counts": dict(product_kpi_diagnostic_summary.get("product_kpi_status_counts") or {}),
            "product_kpi_diagnostic_gap_classes": dict(product_kpi_diagnostic_summary.get("gap_diagnostic_class_counts") or {}),
            "r17_product_family_evidence_row_count": len(r17_rows),
            "r17_source_role_counts": dict(sorted(r17_source_role_counts.items())),
            "r17_summary_status": r17_product_family_evidence_summary.get("status"),
            "r17_nonfinancial_boundary_violation_count": len(r17_nonfinancial_violations),
        },
        "boundary": (
            "A pass does not claim every company has SKU revenue or commercial tracker coverage. "
            "It means product/business family coverage, product KPI state classification, relationship graph edges, "
            "and strong product signal rows are available with explicit public/commercial boundaries."
        ),
    }


def build_third_layer_acceptance_gate(
    *,
    sec_financial_statement_summary: Mapping[str, Any],
    non_us_l1_financial_summary: Mapping[str, Any],
    capital_context_summary: Mapping[str, Any],
    sec_capital_event_summary: Mapping[str, Any],
    sec_capital_event_rows: Iterable[Mapping[str, Any]],
    r18_registry_summary: Mapping[str, Any],
    r18_authority_mart_summary: Mapping[str, Any],
    company_count: int = 603,
) -> dict[str, Any]:
    event_rows = [dict(row) for row in sec_capital_event_rows if isinstance(row, Mapping)]
    event_role_counts = Counter(str(row.get("source_role") or "") for row in event_rows)
    event_exact_violations = [
        _row_id(row)
        for row in event_rows
        if row.get("exact_value_authority") is True or row.get("can_support_company_exact_fact") is True
    ]
    event_boundary_missing = [
        _row_id(row)
        for row in event_rows
        if row.get("source_role") in SEC_EVENT_REQUIRED_SOURCE_ROLES
        and (not str(row.get("claim_boundary") or "").strip() or not row.get("forbidden_claims"))
    ]
    sec_covered = int(sec_financial_statement_summary.get("runtime_ticker_count") or 0)
    non_us_covered = int(non_us_l1_financial_summary.get("covered_target_ticker_count") or 0)
    metric_counts = sec_financial_statement_summary.get("metric_family_counts") or {}
    capital_role_counts = capital_context_summary.get("by_source_role") or {}
    mart_role_counts = r18_authority_mart_summary.get("by_source_role") or {}
    mart_signal_counts = r18_authority_mart_summary.get("by_signal_authority_type") or {}

    checks = {
        "financial_statement_company_coverage": sec_covered + non_us_covered >= company_count,
        "working_capital_metrics_present": all(int(metric_counts.get(metric) or 0) > 0 for metric in WORKING_CAPITAL_REQUIRED_METRICS),
        "capital_context_roles_present": all(int(capital_role_counts.get(role) or 0) > 0 for role in CAPITAL_CONTEXT_REQUIRED_SOURCE_ROLES),
        "sec_capital_event_roles_present": all(int(event_role_counts.get(role) or 0) > 0 for role in SEC_EVENT_REQUIRED_SOURCE_ROLES),
        "sec_capital_event_metadata_not_exact": not event_exact_violations,
        "sec_capital_event_boundaries_present": not event_boundary_missing,
        "r18_registry_hard_gate_pass": all(int(value or 0) == 0 for value in (r18_registry_summary.get("hard_gate") or {}).values()),
        "r18_authority_mart_pass": r18_authority_mart_summary.get("status") == "pass"
        and int((r18_authority_mart_summary.get("hard_gate") or {}).get("flag_count") or 0) == 0,
        "capital_roles_enter_mart": all(int(mart_role_counts.get(role) or 0) > 0 for role in CAPITAL_CONTEXT_REQUIRED_SOURCE_ROLES | SEC_EVENT_REQUIRED_SOURCE_ROLES),
        "capital_signal_authority_types_present": all(
            int(mart_signal_counts.get(signal_type) or 0) > 0
            for signal_type in (
                "capital_structure_fact",
                "working_capital_liquidity_fact",
                "lagged_ownership_signal",
                "capital_market_event_signal",
                "insider_transaction_event_signal",
                "beneficial_ownership_event_signal",
                "proxy_governance_event_signal",
            )
        ),
    }
    failures = [
        {"check": check, "reason": _third_layer_failure_reason(check, locals())}
        for check, passed in checks.items()
        if not passed
    ]
    return {
        "schema_version": R26_THIRD_LAYER_ACCEPTANCE_SCHEMA_VERSION,
        "status": "pass" if not failures else "fail",
        "policy": (
            "Third-layer acceptance gate: three-statement/working-capital coverage, capital context rows, "
            "SEC capital-market filing-event metadata, R18 registry, and authority mart must be present while "
            "metadata rows remain bounded context until source-specific exact parsers exist."
        ),
        "company_count": company_count,
        "checks": checks,
        "failures": failures,
        "metrics": {
            "sec_financial_statement_ticker_count": sec_covered,
            "non_us_l1_financial_covered_target_ticker_count": non_us_covered,
            "financial_statement_metric_family_counts": dict(sorted(metric_counts.items())),
            "capital_context_row_count": capital_context_summary.get("row_count"),
            "capital_context_by_source_role": dict(sorted(capital_role_counts.items())),
            "sec_capital_event_row_count": len(event_rows),
            "sec_capital_event_by_source_role": dict(sorted(event_role_counts.items())),
            "sec_capital_event_exact_violation_count": len(event_exact_violations),
            "sec_capital_event_boundary_missing_count": len(event_boundary_missing),
            "r18_registry_source_role_count": r18_registry_summary.get("registry_source_role_count"),
            "r18_authority_mart_row_count": r18_authority_mart_summary.get("row_count"),
            "r18_authority_mart_by_source_role": dict(sorted(mart_role_counts.items())),
        },
        "boundary": (
            "A pass does not mean offering terms, Form 4 shares, 13D/13G percentages, proxy votes, or buyback amounts "
            "are exact. It confirms the event layer is available and bounded while exact parser follow-ups remain explicit."
        ),
    }


def build_combined_layer_acceptance_gate(
    *,
    second_layer_gate: Mapping[str, Any],
    third_layer_gate: Mapping[str, Any],
    fundamental_peer_panel_gate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    gates = {
        "second_layer": second_layer_gate.get("status") == "pass",
        "third_layer": third_layer_gate.get("status") == "pass",
    }
    if fundamental_peer_panel_gate is not None:
        gates["fundamental_peer_statement_panel"] = fundamental_peer_panel_gate.get("status") == "pass"
    return {
        "schema_version": R26_COMBINED_ACCEPTANCE_SCHEMA_VERSION,
        "status": "pass" if all(gates.values()) else "fail",
        "gates": gates,
        "second_layer_summary": {
            "status": second_layer_gate.get("status"),
            "failures": second_layer_gate.get("failures") or [],
            "metrics": second_layer_gate.get("metrics") or {},
        },
        "third_layer_summary": {
            "status": third_layer_gate.get("status"),
            "failures": third_layer_gate.get("failures") or [],
            "metrics": third_layer_gate.get("metrics") or {},
        },
        "fundamental_peer_panel_summary": (
            {
                "status": fundamental_peer_panel_gate.get("status"),
                "failures": fundamental_peer_panel_gate.get("failures") or [],
                "summary": fundamental_peer_panel_gate.get("summary") or {},
            }
            if fundamental_peer_panel_gate is not None
            else {}
        ),
    }


def build_second_third_layer_real_source_readiness_gate(
    *,
    company_universe_rows: Iterable[Mapping[str, Any]],
    second_layer_rows: Iterable[Mapping[str, Any]],
    third_layer_rows: Iterable[Mapping[str, Any]],
    company_count: int = 603,
) -> dict[str, Any]:
    """Verify actual parser-backed L2/L3 source rows exist company by company.

    This is intentionally stricter than the R26 structural gate. Product slot
    assignments and closeout rows are not accepted as data sources here; a row
    must have a ticker, evidence ref, source locator, parser/materialization
    marker, and claim boundary.
    """

    universe = sorted(
        {
            str(row.get("ticker") or row.get("symbol") or "").upper()
            for row in company_universe_rows
            if str(row.get("ticker") or row.get("symbol") or "").strip()
        }
    )
    if not universe:
        universe = sorted(
            {
                str(row.get("ticker") or "").upper()
                for row in [*second_layer_rows, *third_layer_rows]
                if str(row.get("ticker") or "").strip()
            }
        )
    second_by_ticker = _actual_source_rows_by_ticker(second_layer_rows, accepted_source_files=SECOND_LAYER_SOURCE_FILES)
    third_by_ticker = _actual_source_rows_by_ticker(third_layer_rows, accepted_source_files=THIRD_LAYER_SOURCE_FILES)
    company_rows: list[dict[str, Any]] = []
    for ticker in universe:
        second_rows = second_by_ticker.get(ticker, [])
        third_rows = third_by_ticker.get(ticker, [])
        third_exact_rows = [
            row
            for row in third_rows
            if row.get("exact_value_authority") is True
            or row.get("can_support_company_exact_fact") is True
            or str(row.get("structured_fact_status") or "") == "exact_fact_materialized"
        ]
        second_source_files = Counter(str(row.get("_source_file") or row.get("source_id") or "") for row in second_rows)
        third_source_files = Counter(str(row.get("_source_file") or row.get("source_id") or "") for row in third_rows)
        checks = {
            "second_layer_actual_parser_source_present": bool(second_rows),
            "third_layer_actual_parser_source_present": bool(third_rows),
            "third_layer_exact_financial_basis_present": bool(third_exact_rows),
        }
        failures = [check for check, passed in checks.items() if not passed]
        company_rows.append(
            {
                "schema_version": SECOND_THIRD_LAYER_REAL_SOURCE_READINESS_COMPANY_SCHEMA_VERSION,
                "ticker": ticker,
                "status": "pass" if not failures else "fail",
                "checks": checks,
                "failures": failures,
                "second_layer_actual_source_row_count": len(second_rows),
                "third_layer_actual_source_row_count": len(third_rows),
                "third_layer_exact_financial_basis_row_count": len(third_exact_rows),
                "second_layer_source_files": dict(sorted(second_source_files.items())),
                "third_layer_source_files": dict(sorted(third_source_files.items())),
                "sample_second_layer_evidence_refs": _sample_row_refs(second_rows),
                "sample_third_layer_evidence_refs": _sample_row_refs(third_rows),
                "sample_second_layer_source_locators": _sample_row_locators(second_rows),
                "sample_third_layer_source_locators": _sample_row_locators(third_rows),
            }
        )
    failed = [row for row in company_rows if row["status"] != "pass"]
    second_missing = [row["ticker"] for row in company_rows if not row["checks"]["second_layer_actual_parser_source_present"]]
    third_missing = [row["ticker"] for row in company_rows if not row["checks"]["third_layer_actual_parser_source_present"]]
    third_exact_missing = [row["ticker"] for row in company_rows if not row["checks"]["third_layer_exact_financial_basis_present"]]
    second_source_file_company_counts = Counter(
        source_file
        for row in company_rows
        for source_file, count in row["second_layer_source_files"].items()
        if count > 0
    )
    third_source_file_company_counts = Counter(
        source_file
        for row in company_rows
        for source_file, count in row["third_layer_source_files"].items()
        if count > 0
    )
    checks = {
        "company_universe_count": len(universe) >= company_count,
        "second_layer_all_companies_have_actual_parser_source": not second_missing,
        "third_layer_all_companies_have_actual_parser_source": not third_missing,
        "third_layer_all_companies_have_exact_financial_basis": not third_exact_missing,
    }
    failures = [
        {"check": check, "reason": _real_source_failure_reason(check)}
        for check, passed in checks.items()
        if not passed
    ]
    return {
        "schema_version": SECOND_THIRD_LAYER_REAL_SOURCE_READINESS_SCHEMA_VERSION,
        "status": "pass" if not failures and not failed else "fail",
        "policy": (
            "Real source readiness gate: every company must have actual parser-backed L2 product/source rows and "
            "actual parser-backed L3 financial/capital rows with source locator, evidence ref, parser/materialization "
            "status, and claim boundary. Planning-only product slots and closeout rows do not count as data sources."
        ),
        "company_count": len(universe),
        "expected_company_count": company_count,
        "checks": checks,
        "failures": failures,
        "metrics": {
            "pass_company_count": len([row for row in company_rows if row["status"] == "pass"]),
            "fail_company_count": len(failed),
            "second_layer_actual_source_company_count": len(universe) - len(second_missing),
            "third_layer_actual_source_company_count": len(universe) - len(third_missing),
            "third_layer_exact_financial_basis_company_count": len(universe) - len(third_exact_missing),
            "second_layer_missing_companies": second_missing[:100],
            "third_layer_missing_companies": third_missing[:100],
            "third_layer_exact_financial_basis_missing_companies": third_exact_missing[:100],
            "second_layer_source_file_company_counts": dict(sorted(second_source_file_company_counts.items())),
            "third_layer_source_file_company_counts": dict(sorted(third_source_file_company_counts.items())),
        },
        "company_rows": company_rows,
        "boundary": (
            "This gate verifies materialized parser-backed public-source rows, not commercial tracker coverage. "
            "It does not assert SKU revenue, ASP, unit sales, market share, sell-through, backlog, or realtime fund-flow exactness."
        ),
    }


def build_second_third_layer_depth_parity_matrix(
    *,
    company_universe_rows: Iterable[Mapping[str, Any]],
    product_kpi_closeout_rows: Iterable[Mapping[str, Any]],
    product_kpi_rows: Iterable[Mapping[str, Any]],
    product_spec_rows: Iterable[Mapping[str, Any]],
    customer_deployment_rows: Iterable[Mapping[str, Any]],
    capital_market_rows: Iterable[Mapping[str, Any]],
    market_liquidity_rows: Iterable[Mapping[str, Any]] | None = None,
    company_count: int = 603,
) -> dict[str, Any]:
    """Build a strict five-dimension depth-parity audit matrix.

    This is deliberately stricter than real-source readiness. A company can have
    parser-backed L2/L3 rows and still fail depth parity if the rows only prove a
    weak context surface, such as a generic product page or a Schedule 13G filing
    event without parsed ownership percentages.
    """

    product_kpi_runtime = _actual_source_rows_by_ticker(
        product_kpi_rows,
        accepted_source_files=PRODUCT_KPI_DEPTH_SOURCE_FILES,
    )
    product_spec_runtime = _actual_source_rows_by_ticker(
        product_spec_rows,
        accepted_source_files=PRODUCT_SPEC_DEPTH_SOURCE_FILES,
    )
    customer_deployment_runtime = _actual_source_rows_by_ticker(
        customer_deployment_rows,
        accepted_source_files=CUSTOMER_DEPLOYMENT_DEPTH_SOURCE_FILES,
    )
    capital_market_runtime = _actual_source_rows_by_ticker(
        capital_market_rows,
        accepted_source_files=CAPITAL_MARKET_DETAIL_DEPTH_SOURCE_FILES,
    )
    market_liquidity_runtime = _actual_source_rows_by_ticker(
        market_liquidity_rows or [],
        accepted_source_files=MARKET_LIQUIDITY_DEPTH_SOURCE_FILES,
    )

    closeout_by_ticker = {
        str(row.get("ticker") or "").upper().strip(): dict(row)
        for row in product_kpi_closeout_rows
        if isinstance(row, Mapping) and str(row.get("ticker") or "").strip()
    }
    universe = sorted(
        {
            str(row.get("ticker") or row.get("symbol") or "").upper().strip()
            for row in company_universe_rows
            if isinstance(row, Mapping) and str(row.get("ticker") or row.get("symbol") or "").strip()
        }
    )
    if not universe:
        universe = sorted(
            set(product_kpi_runtime)
            | set(product_spec_runtime)
            | set(customer_deployment_runtime)
            | set(capital_market_runtime)
            | set(market_liquidity_runtime)
            | set(closeout_by_ticker)
        )

    company_rows: list[dict[str, Any]] = []
    backfill_queue: list[dict[str, Any]] = []
    for ticker in universe:
        dimensions = {
            "product_kpi_depth": _product_kpi_depth_status(
                ticker=ticker,
                closeout_row=closeout_by_ticker.get(ticker),
                runtime_rows=product_kpi_runtime.get(ticker, []),
            ),
            "product_spec_depth": _product_spec_depth_status(product_spec_runtime.get(ticker, [])),
            "customer_deployment_depth": _customer_deployment_depth_status(
                customer_deployment_runtime.get(ticker, [])
            ),
            "capital_market_detail_depth": _capital_market_detail_depth_status(
                capital_market_runtime.get(ticker, [])
            ),
            "market_liquidity_depth": _market_liquidity_depth_status(
                market_liquidity_runtime.get(ticker, [])
            ),
        }
        missing_dimensions = [
            dimension
            for dimension, payload in dimensions.items()
            if not payload["target_depth_met"]
        ]
        company_row = {
            "schema_version": SECOND_THIRD_LAYER_DEPTH_PARITY_COMPANY_SCHEMA_VERSION,
            "ticker": ticker,
            "parity_status": "pass" if not missing_dimensions else "fail",
            "missing_target_depth_dimensions": missing_dimensions,
            "dimensions": dimensions,
        }
        company_rows.append(company_row)
        for dimension in missing_dimensions:
            payload = dimensions[dimension]
            backfill_queue.append(
                {
                    "schema_version": SECOND_THIRD_LAYER_DEPTH_PARITY_BACKFILL_SCHEMA_VERSION,
                    "ticker": ticker,
                    "dimension": dimension,
                    "status": payload["status"],
                    "gap_class": payload["gap_class"],
                    "reason": payload["reason"],
                    "next_action": payload["next_action"],
                    "runtime_row_count": payload["runtime_row_count"],
                    "sample_evidence_refs": payload["sample_evidence_refs"],
                    "sample_source_locators": payload["sample_source_locators"],
                }
            )

    parity_failed = [row for row in company_rows if row["parity_status"] != "pass"]
    dimension_status_counts = {
        dimension: dict(
            sorted(
                Counter(str(row["dimensions"][dimension]["status"]) for row in company_rows).items()
            )
        )
        for dimension in DEPTH_PARITY_DIMENSIONS
    }
    dimension_gap_class_counts = {
        dimension: dict(
            sorted(
                Counter(str(row["dimensions"][dimension]["gap_class"]) for row in company_rows).items()
            )
        )
        for dimension in DEPTH_PARITY_DIMENSIONS
    }
    dimension_target_met_counts = {
        dimension: sum(1 for row in company_rows if row["dimensions"][dimension]["target_depth_met"])
        for dimension in DEPTH_PARITY_DIMENSIONS
    }
    backfill_counts = Counter(f"{row['dimension']}::{row['gap_class']}" for row in backfill_queue)
    checks = {
        "audit_company_universe_count": len(universe) >= company_count,
        "all_companies_have_dimension_rows": all(
            set(row["dimensions"]) == set(DEPTH_PARITY_DIMENSIONS) for row in company_rows
        ),
        "all_missing_depth_is_classified": all(
            bool(row["gap_class"]) and row["gap_class"] != "unclassified_missing" for row in backfill_queue
        ),
    }
    failures = [
        {"check": check, "reason": _depth_parity_failure_reason(check)}
        for check, passed in checks.items()
        if not passed
    ]
    return {
        "schema_version": SECOND_THIRD_LAYER_DEPTH_PARITY_SCHEMA_VERSION,
        "status": "pass" if not failures else "fail",
        "parity_status": "pass" if not parity_failed else "fail",
        "policy": (
            "Depth parity audit: each company is evaluated across product KPI, product specs, customer deployment, "
            "capital-market detail, and market-liquidity dimensions. Parser-backed generic context is recorded, but "
            "does not satisfy equal-depth targets unless it carries the specific source role and bounded authority."
        ),
        "company_count": len(universe),
        "expected_company_count": company_count,
        "checks": checks,
        "failures": failures,
        "metrics": {
            "full_depth_target_met_company_count": len(company_rows) - len(parity_failed),
            "full_depth_target_gap_company_count": len(parity_failed),
            "dimension_target_met_counts": dimension_target_met_counts,
            "dimension_gap_counts": {
                dimension: len(company_rows) - dimension_target_met_counts[dimension]
                for dimension in DEPTH_PARITY_DIMENSIONS
            },
            "dimension_status_counts": dimension_status_counts,
            "dimension_gap_class_counts": dimension_gap_class_counts,
            "backfill_queue_count": len(backfill_queue),
            "backfill_queue_counts": dict(sorted(backfill_counts.items())),
            "sample_full_depth_gap_companies": [row["ticker"] for row in parity_failed[:50]],
        },
        "company_rows": company_rows,
        "backfill_queue": backfill_queue,
        "boundary": (
            "A generated audit pass means the matrix is complete and gaps are classified. It does not mean depth "
            "parity is achieved; parity_status remains fail until every applicable dimension has exact or strong "
            "runtime rows, or an explicit public-source boundary is accepted by a later release gate."
        ),
    }


def _product_kpi_depth_status(
    *,
    ticker: str,
    closeout_row: Mapping[str, Any] | None,
    runtime_rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    exact_rows = [
        row
        for row in runtime_rows
        if row.get("exact_value_authority") is True
        or row.get("can_support_company_exact_fact") is True
        or str(row.get("structured_fact_status") or "") == "exact_fact_materialized"
        or _row_looks_like_runtime_allowed_product_kpi(row)
    ]
    closeout_status = str((closeout_row or {}).get("status") or "")
    if exact_rows:
        return _depth_payload(
            status="exact_product_or_business_kpi_ready",
            target_depth_met=True,
            gap_class="none",
            reason="Company-disclosed product, product-line, business-segment, or industry operating metric runtime rows are exact-materialized.",
            next_action="Use exact Product/Business KPI rows in product, segment, and operating-performance analysis while preserving row-level claim boundaries.",
            rows=exact_rows,
        )
    if closeout_status == "product_kpi_exact_ready":
        if int((closeout_row or {}).get("runtime_product_kpi_exact_row_count") or 0) <= 0:
            return _depth_payload(
                status="product_kpi_slot_ready_value_runtime_gap",
                target_depth_met=False,
                gap_class="product_kpi_slot_without_value_unit_period_runtime_row",
                reason="Product slot is marked as KPI-relevant, but no value/unit/period product KPI runtime row exists.",
                next_action="Run value/unit/period/product parser on the cited disclosure table or downgrade closeout if no product KPI value is disclosed.",
                rows=runtime_rows,
            )
        return _depth_payload(
            status="exact_closeout_without_runtime_row",
            target_depth_met=False,
            gap_class="parser_or_manifest_join_gap",
            reason="Closeout claims product KPI exact readiness, but no accepted runtime row was supplied to the depth audit.",
            next_action="Repair manifest/source-file join so exact Product-KPI rows enter the audit and runtime store.",
            rows=runtime_rows,
        )
    if closeout_status == "business_segment_metric_ready":
        return _depth_payload(
            status="business_segment_metric_ready_not_product_exact",
            target_depth_met=False,
            gap_class="company_discloses_segment_not_product_kpi",
            reason="Company-disclosed business/segment metric is available, but not product/SKU/product-family KPI exact.",
            next_action="Use segment metrics for business mix; continue IR deck/local filing/table parser search for product-level KPI.",
            rows=runtime_rows,
        )
    if closeout_status == "geographic_or_non_product_metric_only":
        return _depth_payload(
            status="non_product_metric_only",
            target_depth_met=False,
            gap_class="non_product_metric_public_boundary",
            reason="Available rows are geographic or generic non-product metrics and cannot support product KPI analysis.",
            next_action="Do not promote to Product-KPI; search product tables/IR decks or expose commercial tracker gap.",
            rows=runtime_rows,
        )
    if closeout_status == "product_kpi_exact_gap":
        return _depth_payload(
            status="classified_product_kpi_exact_gap",
            target_depth_met=False,
            gap_class=str((closeout_row or {}).get("closeout_reason") or "company_product_kpi_not_publicly_disclosed"),
            reason="No company-disclosed product/product-line KPI exact row is available in accepted public sources.",
            next_action=str((closeout_row or {}).get("next_action") or "Expose Product-KPI exact gap or use commercial tracker if required."),
            rows=runtime_rows,
        )
    return _depth_payload(
        status="missing_product_kpi_classification",
        target_depth_met=False,
        gap_class="unclassified_missing",
        reason=f"{ticker} has no Product-KPI closeout classification or accepted exact runtime row.",
        next_action="Rebuild Product-KPI closeout and source audit before promoting product performance claims.",
        rows=runtime_rows,
    )


def _row_looks_like_runtime_allowed_product_kpi(row: Mapping[str, Any]) -> bool:
    if str(row.get("promotion_status") or "") != "runtime_fact_allowed":
        return False
    if not str(row.get("value") or "").strip():
        return False
    if not str(row.get("unit") or "").strip():
        return False
    if not str(row.get("period") or row.get("fiscal_year") or "").strip():
        return False
    if not str(row.get("product_or_segment") or row.get("matched_product_alias") or "").strip():
        return False
    claim_types = {str(item) for item in row.get("claim_types") or []}
    allowed_claims = {str(item) for item in row.get("allowed_claims") or []}
    metric_family = str(row.get("metric_family") or "")
    return bool(
        claim_types.intersection(
            {
                "company_disclosed_product_kpi",
                "company_reported_product_operating_fact",
                "company_disclosed_industry_operating_metric",
                "company_disclosed_business_segment_revenue",
            }
        )
        or allowed_claims.intersection(
            {
                "company_disclosed_product_kpi",
                "company_disclosed_brand_net_sales",
                "company_disclosed_industry_operating_metric",
                "business_segment_revenue",
            }
        )
        or metric_family
        in {
            "product_revenue",
            "product_volume",
            "product_operating_metric",
            "business_segment_revenue",
            "industry_operating_metric",
            "unit_sales_or_deliveries",
            "processed_transactions",
            "capacity_utilization_or_production_volume",
            "backlog_or_orders",
            "airline_tickets",
            "arpu",
            "arr_or_rpo",
            "aua",
            "same_store_sales_growth",
            "same_store_revenue_growth_component",
            "aum",
            "client_assets",
            "deposits",
            "financial_services_operating_metric",
            "loan_balance",
            "marketplace_gross_order_value",
            "mw_or_generation_capacity",
            "patient_volume",
            "payment_transactions_per_active_account",
            "rental_car_days",
            "revenue_per_occupied_square_foot",
            "room_nights",
            "segment_revenue_growth",
            "shipments",
            "subscriber_count",
            "total_payment_volume",
            "tpv_mix_percent",
            "trading_volume",
        }
    )


def _product_spec_depth_status(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    strong_source_roles = {
        "technical_product_spec",
        "business_asset_profile_spec",
        "official_product_profile_spec",
        "business_service_profile_spec",
    }
    strong_rows = [
        row
        for row in rows
        if str(row.get("source_role") or "") in strong_source_roles
        or str(row.get("structured_context_type") or "") in strong_source_roles
        or row.get("technical_spec_authority") is True
    ]
    if strong_rows:
        return _depth_payload(
            status="product_spec_or_business_profile_ready",
            target_depth_met=True,
            gap_class="none",
            reason=(
                "Official/spec-parser rows provide product parameters, technical attributes, official product/service "
                "profile, or bounded business/asset/operating profile context."
            ),
            next_action=(
                "Use ProductSpecSlot, ProductProfileSlot, or BusinessProfileSlot rows for product, service, "
                "capability, or asset-profile analysis within row-level boundaries."
            ),
            rows=strong_rows,
        )
    bounded_rows = [
        row
        for row in rows
        if str(row.get("structured_context_type") or "").startswith("official_product")
        or "product_taxonomy" in str(row.get("structured_context_type") or "")
        or str(row.get("source_id") or "") in {"company_product_pages", "official_product_catalog"}
    ]
    if bounded_rows:
        return _depth_payload(
            status="official_product_taxonomy_or_catalog_ready",
            target_depth_met=False,
            gap_class="product_spec_parser_depth_gap",
            reason="Official product surface/catalog exists, but no parsed spec_name/value/unit/version row is available.",
            next_action="Run family-specific official spec/datasheet parser for this company/product family.",
            rows=bounded_rows,
        )
    return _depth_payload(
        status="missing_product_spec_source",
        target_depth_met=False,
        gap_class="product_spec_source_or_parser_gap",
        reason="No accepted official product spec/catalog runtime row is available.",
        next_action="Locate official product/catalog/spec pages and materialize parser-backed ProductSpecSlot rows.",
        rows=rows,
    )


def _customer_deployment_depth_status(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    deployment_rows = [
        row
        for row in rows
        if str(row.get("source_role") or row.get("requirement_id") or "")
        in {
            "official_customer_order_or_deployment_event",
            "customer_deployment_proxy",
            "supply_chain_official_relationship",
            "public_order_proxy",
        }
        or str(row.get("event_type") or "")
        in {"customer_order", "customer_deployment", "production_or_manufacturing_plan"}
        or str(row.get("counterparty") or row.get("customer_name") or "").strip()
    ]
    distribution_rows = [
        row
        for row in rows
        if str(row.get("source_role") or row.get("requirement_id") or row.get("source_id") or "")
        in {
            "channel_offer_proxy",
            "channel_pricing_quotations",
            "channel_distributor_locator",
            "app_rank_store_proxy",
            "platform_review_proxy",
            "app_store_rankings",
            "platform_reviews_rankings_downloads",
        }
        or str(row.get("structured_context_type") or "")
        in {
            "channel_offer_context",
            "channel_distributor_locator_context",
            "app_marketplace_context",
            "app_store_marketplace_context",
            "platform_review_context",
            "platform_review_ranking_context",
        }
    ]
    operating_footprint_rows = [
        row
        for row in rows
        if _row_is_operating_footprint_signal(row)
    ]
    regulated_product_rows = [
        row
        for row in rows
        if _row_is_regulated_product_or_identity_signal(row)
    ]
    customer_contract_rows = [
        row
        for row in rows
        if _row_is_customer_contract_liability_signal(row)
    ]
    if deployment_rows:
        return _depth_payload(
            status="customer_deployment_or_public_order_signal_ready",
            target_depth_met=True,
            gap_class="none",
            reason="Parser-backed customer/order/deployment/public-award rows exist with issuer/counterparty or event binding.",
            next_action="Use as bounded demand/deployment signal; do not infer revenue, backlog, ASP, shipment, or share.",
            rows=deployment_rows,
        )
    if distribution_rows:
        return _depth_payload(
            status="customer_distribution_or_adoption_proxy_ready",
            target_depth_met=True,
            gap_class="none",
            reason="Parser-backed public channel/distributor/app-marketplace rows exist with issuer/product binding.",
            next_action="Use as bounded distribution, availability, or adoption proxy; do not infer revenue, backlog, ASP, inventory, sell-through, shipment, or share.",
            rows=distribution_rows,
        )
    if operating_footprint_rows:
        return _depth_payload(
            status="business_operating_footprint_signal_ready",
            target_depth_met=True,
            gap_class="none",
            reason=(
                "Company-disclosed operating-footprint rows exist for lane-specific activity such as AUM, "
                "capacity, production/throughput, deliveries, shipments, same-store activity, or official "
                "asset/business profile."
            ),
            next_action=(
                "Use as bounded operating-footprint/adoption context for industries where customer deployment "
                "pages are not the natural disclosure unit; do not infer revenue, order value, backlog, ASP, "
                "sell-through, inventory, market share, or undisclosed customer wins."
            ),
            rows=operating_footprint_rows,
        )
    if regulated_product_rows:
        return _depth_payload(
            status="regulated_product_or_identity_context_ready",
            target_depth_met=True,
            gap_class="none",
            reason=(
                "Issuer-bound regulatory/API rows exist for clinical trial, FDA application, animal/veterinary "
                "product, or vehicle model identity context."
            ),
            next_action=(
                "Use as bounded product existence, approval/trial/status, or vehicle identity context; do not infer "
                "customer wins, sales, order value, revenue, backlog, ASP, market share, or utilization."
            ),
            rows=regulated_product_rows,
        )
    if customer_contract_rows:
        return _depth_payload(
            status="customer_contract_liability_footprint_ready",
            target_depth_met=True,
            gap_class="none",
            reason=(
                "CompanyFacts exact rows provide deferred revenue or contract-with-customer liability, which is a "
                "bounded customer contract / remaining performance obligation footprint."
            ),
            next_action=(
                "Use as customer-contract/liability context only; do not infer customer names, deployments, order "
                "value, product sales, ASP, market share, sell-through, inventory, or backlog beyond the reported "
                "contract-liability row."
            ),
            rows=customer_contract_rows,
        )
    return _depth_payload(
        status="missing_customer_deployment_signal",
        target_depth_met=False,
        gap_class="customer_deployment_public_source_gap",
        reason="No accepted customer/order/deployment/public-award or bounded distribution/adoption runtime row is available.",
        next_action="Search official customer/supplier news, customer cases, procurement awards, local tenders, cloud/OEM deployment sources, channel/distributor locators, and app marketplace rows where lane-applicable.",
        rows=rows,
    )


def _row_is_operating_footprint_signal(row: Mapping[str, Any]) -> bool:
    source_file = str(row.get("_source_file") or "")
    source_role = str(row.get("source_role") or "")
    structured_context_type = str(row.get("structured_context_type") or "")
    metric_family = str(row.get("metric_family") or "")
    allowed_claims = {str(item) for item in row.get("allowed_claims") or []}
    claim_types = {str(item) for item in row.get("claim_types") or []}
    operating_families = {
        "aum",
        "backlog_or_orders",
        "capacity_utilization_or_production_volume",
        "airline_tickets",
        "arpu",
        "arr_or_rpo",
        "aua",
        "client_assets",
        "customer_count",
        "deposits",
        "financial_services_operating_metric",
        "insurance_premiums_or_policies",
        "loan_balance",
        "marketplace_gross_order_value",
        "mw_or_generation_capacity",
        "patient_volume",
        "payment_transactions_per_active_account",
        "processed_transactions",
        "production_or_throughput",
        "rental_car_days",
        "real_estate_footprint",
        "revenue_per_occupied_square_foot",
        "room_nights",
        "same_store_sales_growth",
        "same_store_revenue_growth_component",
        "shipments",
        "store_or_location_count",
        "subscriber_count",
        "total_payment_volume",
        "tpv_mix_percent",
        "trading_volume",
        "unit_sales_or_deliveries",
    }
    if source_file == "official_business_asset_profile_context_rows_v0_1.jsonl":
        return structured_context_type == "business_asset_profile_spec" or source_role == "business_asset_profile_spec"
    if metric_family in operating_families:
        return True
    if source_role in operating_families or source_role in {"production_or_throughput", "unit_sales_or_deliveries"}:
        return True
    if allowed_claims.intersection({"company_disclosed_industry_operating_metric", "company_reported_product_operating_fact"}):
        return metric_family in operating_families or source_role in operating_families
    if claim_types.intersection({"company_disclosed_industry_operating_metric", "company_reported_product_operating_fact"}):
        return metric_family in operating_families or source_role in operating_families
    return False


def _row_is_regulated_product_or_identity_signal(row: Mapping[str, Any]) -> bool:
    if str(row.get("_source_file") or "") != "targeted_regulated_auto_official_api_context_rows_v0_1.jsonl":
        return False
    if not str(row.get("ticker") or "").strip():
        return False
    if not str(row.get("evidence_ref") or "").strip():
        return False
    if not str(row.get("source_url") or "").strip():
        return False
    requirement = str(row.get("requirement_id") or row.get("source_role") or "")
    context_type = str(row.get("structured_context_type") or "")
    source_id = str(row.get("source_id") or "")
    allowed_claims = {str(item) for item in row.get("allowed_claims") or []}
    regulated_requirements = {"regulated_product_context", "auto_product_identity_context"}
    regulated_contexts = {
        "regulated_product_context",
        "vehicle_model_identity_context",
        "vehicle_manufacturer_identity_context",
    }
    regulated_sources = {"clinicaltrials_api", "openfda_api", "fda_animal_drugs_api", "nhtsa_vpic_api"}
    return bool(
        requirement in regulated_requirements
        or context_type in regulated_contexts
        or source_id in regulated_sources
        or allowed_claims.intersection(regulated_requirements)
    )


def _row_is_customer_contract_liability_signal(row: Mapping[str, Any]) -> bool:
    source_file = str(row.get("_source_file") or "")
    if source_file not in {
        "sec_financial_statement_metric_runtime_rows_v0_1.jsonl",
        "customer_operating_footprint_signal_runtime_rows_v0_1.jsonl",
    }:
        return False
    if not str(row.get("ticker") or "").strip():
        return False
    if not str(row.get("evidence_ref") or "").strip():
        return False
    if not str(row.get("source_url") or "").strip():
        return False
    if not (
        row.get("exact_value_authority") is True
        or row.get("can_support_company_exact_fact") is True
        or str(row.get("structured_fact_status") or "") == "exact_fact_materialized"
    ):
        return False
    metric_family = str(row.get("metric_family") or "")
    metric_name = str(row.get("metric_name") or "")
    source_role = str(row.get("source_role") or "")
    signal_authority_type = str(row.get("signal_authority_type") or "")
    if source_file == "customer_operating_footprint_signal_runtime_rows_v0_1.jsonl":
        return bool(
            metric_family
            in {
                "customer_contract_liability_or_deposit",
                "customer_contract_asset_or_cost",
                "remaining_performance_obligation",
            }
            or source_role in {"customer_contract_liability_footprint", "customer_contract_asset_footprint"}
            or signal_authority_type
            in {
                "customer_contract_liability_footprint",
                "customer_contract_asset_footprint",
                "customer_contract_rpo_footprint",
            }
        )
    if metric_family == "deferred_revenue":
        return True
    return bool(re.search(r"contract with customer, liability|deferred revenue", metric_name, re.IGNORECASE))


def _capital_market_detail_depth_status(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    exact_context_rows = [
        row
        for row in rows
        if (
            (row.get("exact_value_authority") is True or row.get("can_support_company_exact_fact") is True)
            and str(row.get("_source_file") or "") != "non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl"
        )
        or str(row.get("source_role") or "") in {"capital_structure_disclosure", "working_capital_liquidity"}
        or _row_is_non_us_primary_capital_disclosure(row)
    ]
    event_rows = [
        row
        for row in rows
        if str(row.get("source_role") or "")
        in {
            "securities_offering_filing_event",
            "insider_transaction_filing_event",
            "beneficial_ownership_filing_event",
            "proxy_governance_filing_event",
            "lagged_ownership_context",
        }
    ]
    if exact_context_rows and event_rows:
        return _depth_payload(
            status="capital_terms_and_market_event_context_ready",
            target_depth_met=True,
            gap_class="none",
            reason="Company has capital/debt/working-capital details plus capital-market filing or ownership event context.",
            next_action="Use capital detail rows with event metadata boundaries; source-specific parsers still needed for Form 4/13D/offering exact fields.",
            rows=[*exact_context_rows, *event_rows],
        )
    if _has_non_us_primary_capital_detail(exact_context_rows):
        return _depth_payload(
            status="non_us_primary_capital_disclosure_ready",
            target_depth_met=True,
            gap_class="none",
            reason=(
                "Non-US/local-exchange annual-report rows provide exact primary capital, balance-sheet, "
                "liability, equity, or cash-flow disclosure. Local offering/ownership event parsers may still "
                "add depth, but the company no longer has a capital source gap."
            ),
            next_action=(
                "Use only as local primary capital/financial disclosure context; continue separate local "
                "offering, insider, ownership, and proxy parser work where those events are material."
            ),
            rows=exact_context_rows,
        )
    if exact_context_rows:
        return _depth_payload(
            status="capital_primary_disclosure_ready_event_detail_gap",
            target_depth_met=False,
            gap_class="capital_market_event_parser_or_coverage_gap",
            reason="Capital/debt/working-capital exact context exists, but capital-market event detail rows are absent from accepted sources.",
            next_action="Run SEC/local exchange offering, insider, 13D/G, proxy, and ownership event parser routes.",
            rows=exact_context_rows,
        )
    if event_rows:
        return _depth_payload(
            status="capital_event_metadata_ready_primary_detail_gap",
            target_depth_met=False,
            gap_class="capital_primary_disclosure_parser_gap",
            reason="Capital-market filing event metadata exists, but debt/credit/working-capital detail rows are absent.",
            next_action="Run debt footnote, credit facility, and working-capital parsers for primary disclosures.",
            rows=event_rows,
        )
    return _depth_payload(
        status="missing_capital_market_detail",
        target_depth_met=False,
        gap_class="capital_market_detail_source_gap",
        reason="No accepted capital-market detail or event runtime row is available.",
        next_action="Materialize primary disclosure capital rows and SEC/local exchange capital-market event rows.",
        rows=rows,
    )


def _row_is_non_us_primary_capital_disclosure(row: Mapping[str, Any]) -> bool:
    if str(row.get("_source_file") or "") != "non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl":
        return False
    if not (row.get("exact_value_authority") is True or row.get("can_support_company_exact_fact") is True):
        return False
    metric_family = str(row.get("metric_family") or "").lower()
    metric_name = str(row.get("metric_name") or "").lower()
    capital_terms = {
        "assets",
        "liabilities",
        "equity",
        "cash",
        "cash_and_equivalents",
        "current_assets",
        "current_liabilities",
        "debt",
        "short_term_debt",
        "long_term_debt",
        "operating_cash_flow",
        "capital_expenditure_proxy",
        "free_cash_flow",
    }
    if metric_family in capital_terms:
        return True
    return any(term in metric_name for term in ("asset", "liabil", "equity", "cash", "debt", "borrow", "capital"))


def _has_non_us_primary_capital_detail(rows: list[Mapping[str, Any]]) -> bool:
    return any(_row_is_non_us_primary_capital_disclosure(row) for row in rows)


def _market_liquidity_depth_status(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    liquidity_rows = [
        row
        for row in rows
        if str(row.get("source_role") or row.get("signal_authority_type") or "")
        in {
            "market_liquidity_driver",
            "price_volume_liquidity",
            "short_interest",
            "options_signal",
            "etf_factor_flow",
            "credit_spread_context",
        }
        or str(row.get("metric_family") or row.get("metric_name") or "").lower()
        in {"short_interest", "volume", "turnover", "implied_volatility", "credit_spread", "etf_flow"}
    ]
    if liquidity_rows:
        return _depth_payload(
            status="market_liquidity_driver_ready",
            target_depth_met=True,
            gap_class="none",
            reason="Parser-backed market liquidity or positioning driver rows exist.",
            next_action="Use as market-liquidity/positioning driver, not as company operating fact.",
            rows=liquidity_rows,
        )
    return _depth_payload(
        status="missing_market_liquidity_runtime_rows",
        target_depth_met=False,
        gap_class="market_liquidity_source_not_materialized",
        reason="No accepted price/volume/turnover/short-interest/options/ETF-flow/credit-spread runtime rows are materialized.",
        next_action="Add public market-liquidity source adapters and runtime rows; keep them separate from operating fundamentals.",
        rows=rows,
    )


def _depth_payload(
    *,
    status: str,
    target_depth_met: bool,
    gap_class: str,
    reason: str,
    next_action: str,
    rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    source_files = Counter(str(row.get("_source_file") or row.get("source_id") or "") for row in rows)
    return {
        "status": status,
        "target_depth_met": target_depth_met,
        "gap_class": gap_class,
        "reason": reason,
        "next_action": next_action,
        "runtime_row_count": len(rows),
        "source_files": dict(sorted((key, value) for key, value in source_files.items() if key)),
        "sample_evidence_refs": _sample_row_refs([dict(row) for row in rows]),
        "sample_source_locators": _sample_row_locators([dict(row) for row in rows]),
    }


def _row_id(row: Mapping[str, Any]) -> str:
    return str(row.get("evidence_ref") or row.get("fact_id") or row.get("row_id") or row.get("ticker") or "unknown")


def _actual_source_rows_by_ticker(
    rows: Iterable[Mapping[str, Any]],
    *,
    accepted_source_files: set[str],
) -> dict[str, list[dict[str, Any]]]:
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        clean = dict(row)
        source_file = str(clean.get("_source_file") or "")
        if source_file and source_file not in accepted_source_files:
            continue
        ticker = str(clean.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        if not _row_has_parser_materialization_marker(clean):
            continue
        if not _row_has_source_locator(clean):
            continue
        if not str(clean.get("evidence_ref") or clean.get("evidence_id") or clean.get("fact_id") or "").strip():
            continue
        if not str(clean.get("claim_boundary") or clean.get("authority_boundary") or "").strip():
            continue
        by_ticker.setdefault(ticker, []).append(clean)
    return by_ticker


def _row_has_parser_materialization_marker(row: Mapping[str, Any]) -> bool:
    markers = {
        str(row.get("parser_status") or ""),
        str(row.get("promotion_status") or ""),
        str(row.get("structured_fact_status") or ""),
        str(row.get("evidence_graph_status") or ""),
    }
    if PASSING_PARSER_STATUSES.intersection(markers):
        return True
    return bool(str(row.get("source_specific_parser") or row.get("source_specific_resolver") or "").strip())


def _row_has_source_locator(row: Mapping[str, Any]) -> bool:
    citation = row.get("citation") if isinstance(row.get("citation"), Mapping) else {}
    for key in ("source_url", "api_url", "snapshot_url", "raw_path", "local_path", "raw_url", "url"):
        if str(row.get(key) or "").strip():
            return True
    return bool(str(citation.get("source_url") or citation.get("url") or "").strip())


def _slot_has_family_binding(row: Mapping[str, Any]) -> bool:
    return bool(
        str(row.get("family_id") or row.get("family_name") or row.get("product_family_id") or row.get("product_family") or "").strip()
    )


def _slot_has_url_or_raw_ref(row: Mapping[str, Any]) -> bool:
    citation = row.get("citation") if isinstance(row.get("citation"), Mapping) else {}
    return any(
        str(value or "").strip()
        for value in (
            row.get("source_url"),
            row.get("url"),
            row.get("raw_url"),
            row.get("raw_path"),
            row.get("local_path"),
            row.get("source_ref"),
            row.get("source_id"),
            row.get("evidence_ref"),
            citation.get("source_url"),
            citation.get("url"),
        )
    )


def _sample_row_refs(rows: list[Mapping[str, Any]], limit: int = 5) -> list[str]:
    refs = []
    for row in rows:
        value = str(row.get("evidence_ref") or row.get("evidence_id") or row.get("fact_id") or "").strip()
        if value and value not in refs:
            refs.append(value)
        if len(refs) >= limit:
            break
    return refs


def _sample_row_locators(rows: list[Mapping[str, Any]], limit: int = 5) -> list[str]:
    locators = []
    for row in rows:
        citation = row.get("citation") if isinstance(row.get("citation"), Mapping) else {}
        value = str(
            row.get("source_url")
            or row.get("api_url")
            or row.get("snapshot_url")
            or row.get("raw_path")
            or citation.get("source_url")
            or citation.get("url")
            or ""
        ).strip()
        if value and value not in locators:
            locators.append(value)
        if len(locators) >= limit:
            break
    return locators


def _edge_type(row: Mapping[str, Any]) -> str:
    return str(row.get("edge_type") or row.get("relationship_type") or row.get("relation_type") or "")


def _second_layer_failure_reason(check: str, scope: Mapping[str, Any]) -> str:
    reasons = {
        "product_graph_summary_pass": "product relationship graph summary or validation did not pass",
        "company_product_slot_coverage": "not every company has at least one product/business family slot",
        "all_slots_family_bound": "some product slots are not bound to product family assignments",
        "all_slots_have_url_or_raw_ref": "some product slots lack source URL/raw reference",
        "product_kpi_closeout_covers_company_universe": "Product-KPI closeout does not cover the full company universe",
        "product_kpi_gaps_classified": "Product-KPI closeout has invalid/unclassified states",
        "second_layer_signal_roles_present": "R17 strong product signal roles are incomplete",
        "relationship_edge_types_present": "Product relationship graph lacks required competition/supply/deployment/generation/benchmark coverage",
        "nonfinancial_signal_boundary_preserved": "A non-financial product signal is incorrectly marked as exact or lacks forbidden product exact claims",
    }
    return reasons.get(check, "second layer acceptance check failed")


def _third_layer_failure_reason(check: str, scope: Mapping[str, Any]) -> str:
    reasons = {
        "financial_statement_company_coverage": "SEC plus non-US L1 financial statement rows do not cover the company universe",
        "working_capital_metrics_present": "working-capital/liquidity metric families are missing from SEC financial statement rows",
        "capital_context_roles_present": "capital structure, lagged ownership, or working-capital context roles are missing",
        "sec_capital_event_roles_present": "SEC capital-market filing-event source roles are incomplete",
        "sec_capital_event_metadata_not_exact": "SEC filing-event metadata is incorrectly marked as exact company fact",
        "sec_capital_event_boundaries_present": "SEC filing-event rows lack claim boundaries or forbidden claims",
        "r18_registry_hard_gate_pass": "R18 registry hard gate has violations",
        "r18_authority_mart_pass": "R18 source authority mart did not pass",
        "capital_roles_enter_mart": "capital/funding/ownership source roles are not visible in the authority mart",
        "capital_signal_authority_types_present": "required capital signal authority types are absent from the mart",
    }
    return reasons.get(check, "third layer acceptance check failed")


def _real_source_failure_reason(check: str) -> str:
    reasons = {
        "company_universe_count": "company universe is smaller than expected",
        "second_layer_all_companies_have_actual_parser_source": "at least one company lacks parser-backed second-layer product/source rows",
        "third_layer_all_companies_have_actual_parser_source": "at least one company lacks parser-backed third-layer financial/capital rows",
        "third_layer_all_companies_have_exact_financial_basis": "at least one company lacks parser-backed exact financial statement basis",
    }
    return reasons.get(check, "real source readiness check failed")


def _depth_parity_failure_reason(check: str) -> str:
    reasons = {
        "audit_company_universe_count": "company universe is smaller than expected",
        "all_companies_have_dimension_rows": "at least one company is missing a depth-parity dimension payload",
        "all_missing_depth_is_classified": "at least one depth gap is unclassified and must be routed before backfill",
    }
    return reasons.get(check, "depth parity audit check failed")
