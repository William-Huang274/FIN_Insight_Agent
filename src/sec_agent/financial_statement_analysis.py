from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sec_agent.derived_metric_layer import build_derived_metric_layer


FINANCIAL_STATEMENT_TAXONOMY_SCHEMA_VERSION = "sec_agent_financial_statement_taxonomy_v0.1"
INDUSTRY_FINANCIAL_FOCUS_POLICY_SCHEMA_VERSION = "sec_agent_industry_financial_focus_policy_v0.1"
FUNDAMENTAL_STATEMENT_PACK_SCHEMA_VERSION = "sec_agent_fundamental_statement_pack_v0.1"
FUNDAMENTAL_PEER_STATEMENT_PANEL_SCHEMA_VERSION = "sec_agent_fundamental_peer_statement_panel_v0.1"

COMPANY_TOTAL_KEYS = {"", "__company_total__", "company_total", "total_company", "consolidated"}
PERIOD_CHANGE_EXCLUDED_METRICS = {"yoy_growth"}

STATEMENT_TAXONOMY: dict[str, dict[str, str]] = {
    "financial_metric:revenue": {
        "statement_type": "income_statement",
        "level1": "revenue",
        "level2": "net_sales_or_revenue",
        "level3": "company_or_segment_revenue",
        "analysis_role": "topline",
    },
    "product_kpi:product_revenue": {
        "statement_type": "income_statement",
        "level1": "revenue",
        "level2": "product_or_segment_revenue",
        "level3": "company_disclosed_product_revenue",
        "analysis_role": "product_financial_bridge",
    },
    "financial_metric:cost_of_revenue": {
        "statement_type": "income_statement",
        "level1": "costs",
        "level2": "cost_of_revenue",
        "level3": "product_or_service_delivery_cost",
        "analysis_role": "gross_margin_driver",
    },
    "financial_metric:gross_profit": {
        "statement_type": "income_statement",
        "level1": "profitability",
        "level2": "gross_profit",
        "level3": "gross_profit_dollars",
        "analysis_role": "gross_margin_driver",
    },
    "financial_metric:gross_margin": {
        "statement_type": "income_statement",
        "level1": "profitability",
        "level2": "gross_margin",
        "level3": "reported_gross_margin",
        "analysis_role": "unit_economics_or_mix",
    },
    "financial_metric:operating_income": {
        "statement_type": "income_statement",
        "level1": "profitability",
        "level2": "operating_income",
        "level3": "operating_profit",
        "analysis_role": "operating_leverage",
    },
    "financial_metric:net_income": {
        "statement_type": "income_statement",
        "level1": "profitability",
        "level2": "net_income",
        "level3": "earnings_available_to_common",
        "analysis_role": "bottom_line",
    },
    "financial_metric:eps": {
        "statement_type": "income_statement",
        "level1": "profitability",
        "level2": "earnings_per_share",
        "level3": "per_share_earnings",
        "analysis_role": "per_share_conversion",
    },
    "financial_metric:shares": {
        "statement_type": "income_statement",
        "level1": "capital_base",
        "level2": "share_count",
        "level3": "weighted_average_shares",
        "analysis_role": "dilution_or_buyback",
    },
    "financial_metric:cash": {
        "statement_type": "balance_sheet",
        "level1": "liquidity",
        "level2": "cash_and_equivalents",
        "level3": "cash_balance",
        "analysis_role": "liquidity_buffer",
    },
    "financial_metric:debt": {
        "statement_type": "balance_sheet",
        "level1": "capital_structure",
        "level2": "debt",
        "level3": "debt_principal_or_carrying_value",
        "analysis_role": "leverage",
    },
    "financial_metric:inventory": {
        "statement_type": "balance_sheet",
        "level1": "working_capital",
        "level2": "inventory",
        "level3": "inventory_balance",
        "analysis_role": "demand_or_obsolescence_signal",
    },
    "financial_metric:operating_cash_flow": {
        "statement_type": "cash_flow_statement",
        "level1": "cash_generation",
        "level2": "operating_cash_flow",
        "level3": "cash_from_operations",
        "analysis_role": "earnings_quality",
    },
    "financial_metric:capex": {
        "statement_type": "cash_flow_statement",
        "level1": "reinvestment",
        "level2": "capital_expenditures",
        "level3": "purchases_of_property_and_equipment",
        "analysis_role": "capacity_or_infrastructure_investment",
    },
    "financial_metric:fcf": {
        "statement_type": "cash_flow_statement",
        "level1": "cash_generation",
        "level2": "free_cash_flow",
        "level3": "company_disclosed_or_derived_fcf",
        "analysis_role": "post_investment_cash_generation",
    },
}

DERIVED_METRIC_TAXONOMY: dict[str, dict[str, str]] = {
    "gross_margin": STATEMENT_TAXONOMY["financial_metric:gross_margin"],
    "operating_margin": {
        "statement_type": "income_statement",
        "level1": "profitability",
        "level2": "operating_margin",
        "level3": "derived_operating_margin",
        "analysis_role": "operating_leverage",
    },
    "free_cash_flow": STATEMENT_TAXONOMY["financial_metric:fcf"],
    "free_cash_flow_margin": {
        "statement_type": "cash_flow_statement",
        "level1": "cash_generation",
        "level2": "free_cash_flow_margin",
        "level3": "derived_fcf_margin",
        "analysis_role": "post_investment_cash_conversion",
    },
    "net_debt": {
        "statement_type": "balance_sheet",
        "level1": "capital_structure",
        "level2": "net_debt",
        "level3": "debt_less_cash",
        "analysis_role": "leverage_after_cash",
    },
    "inventory_days": {
        "statement_type": "balance_sheet",
        "level1": "working_capital",
        "level2": "inventory_days",
        "level3": "derived_inventory_days",
        "analysis_role": "working_capital_efficiency",
    },
    "yoy_growth": {
        "statement_type": "income_statement",
        "level1": "revenue",
        "level2": "growth_rate",
        "level3": "derived_same_period_growth",
        "analysis_role": "growth_quality",
    },
    "asp": {
        "statement_type": "income_statement",
        "level1": "revenue",
        "level2": "unit_economics",
        "level3": "average_selling_price_proxy",
        "analysis_role": "product_price_volume_bridge",
    },
    "arpu": {
        "statement_type": "income_statement",
        "level1": "revenue",
        "level2": "unit_economics",
        "level3": "average_revenue_per_user_proxy",
        "analysis_role": "product_price_volume_bridge",
    },
    "take_rate": {
        "statement_type": "income_statement",
        "level1": "revenue",
        "level2": "unit_economics",
        "level3": "platform_take_rate",
        "analysis_role": "monetization_efficiency",
    },
}

INDUSTRY_FOCUS_POLICIES: dict[str, dict[str, Any]] = {
    "semiconductor_hardware": {
        "aliases": ["semiconductor", "hardware", "ai_infrastructure", "gpu", "data_center"],
        "priority_metrics": [
            "financial_metric:revenue",
            "product_kpi:product_revenue",
            "financial_metric:gross_profit",
            "gross_margin",
            "financial_metric:inventory",
            "financial_metric:capex",
            "financial_metric:operating_cash_flow",
            "free_cash_flow",
        ],
        "statement_weights": {"income_statement": 0.45, "balance_sheet": 0.25, "cash_flow_statement": 0.30},
        "analysis_questions": [
            "Is revenue growth matched by gross margin and inventory discipline?",
            "Is capex or supplier exposure needed to sustain product availability?",
        ],
    },
    "software_saas": {
        "aliases": ["software", "saas", "cloud", "developer", "subscription"],
        "priority_metrics": [
            "financial_metric:revenue",
            "gross_margin",
            "operating_margin",
            "financial_metric:operating_cash_flow",
            "free_cash_flow",
            "free_cash_flow_margin",
        ],
        "statement_weights": {"income_statement": 0.50, "balance_sheet": 0.15, "cash_flow_statement": 0.35},
        "analysis_questions": [
            "Is growth converting into operating leverage and cash generation?",
            "Are deferred revenue, RPO, sales efficiency, or churn data missing from public rows?",
        ],
    },
    "consumer_electronics": {
        "aliases": ["consumer_electronics", "smartphone", "device", "hardware_platform"],
        "priority_metrics": [
            "financial_metric:revenue",
            "product_kpi:product_revenue",
            "gross_margin",
            "financial_metric:inventory",
            "financial_metric:operating_cash_flow",
            "free_cash_flow",
        ],
        "statement_weights": {"income_statement": 0.45, "balance_sheet": 0.30, "cash_flow_statement": 0.25},
        "analysis_questions": [
            "Does product mix support margin rather than only reported revenue?",
            "Do inventory and cash flow confirm or weaken product-cycle claims?",
        ],
    },
    "autos_ev": {
        "aliases": ["auto", "automotive", "vehicle", "ev", "mobility"],
        "priority_metrics": [
            "financial_metric:revenue",
            "product_kpi:deliveries",
            "financial_metric:gross_profit",
            "gross_margin",
            "financial_metric:inventory",
            "financial_metric:capex",
            "financial_metric:debt",
            "financial_metric:cash",
        ],
        "statement_weights": {"income_statement": 0.35, "balance_sheet": 0.35, "cash_flow_statement": 0.30},
        "analysis_questions": [
            "Are deliveries or production turning into revenue and gross margin?",
            "Is inventory or leverage signaling demand, pricing, or capacity pressure?",
        ],
    },
    "banks_financials": {
        "aliases": ["bank", "banks", "financial", "credit", "deposit", "broker"],
        "priority_metrics": [
            "financial_metric:revenue",
            "financial_metric:net_income",
            "financial_metric:cash",
            "financial_metric:debt",
        ],
        "statement_weights": {"income_statement": 0.45, "balance_sheet": 0.45, "cash_flow_statement": 0.10},
        "analysis_questions": [
            "Are balance-sheet funding and credit metrics available for the company?",
            "Are net interest income, deposits, provisions, and capital ratios missing from public structured rows?",
        ],
    },
    "pharma_biotech_medtech": {
        "aliases": ["pharma", "biotech", "drug", "medtech", "healthcare"],
        "priority_metrics": [
            "financial_metric:revenue",
            "product_kpi:product_revenue",
            "financial_metric:gross_profit",
            "gross_margin",
            "financial_metric:cash",
            "financial_metric:operating_cash_flow",
        ],
        "statement_weights": {"income_statement": 0.45, "balance_sheet": 0.25, "cash_flow_statement": 0.30},
        "analysis_questions": [
            "Do product revenues and margins support the product-cycle claim?",
            "Are pipeline, trial, prescription, or approval proxies only context rather than sales proof?",
        ],
    },
    "energy_utilities": {
        "aliases": ["energy", "oil", "gas", "utility", "utilities", "power"],
        "priority_metrics": [
            "financial_metric:revenue",
            "financial_metric:operating_cash_flow",
            "financial_metric:capex",
            "free_cash_flow",
            "financial_metric:debt",
            "financial_metric:cash",
        ],
        "statement_weights": {"income_statement": 0.25, "balance_sheet": 0.30, "cash_flow_statement": 0.45},
        "analysis_questions": [
            "Does cash flow fund capex and leverage needs?",
            "Are volumes, rate-base, commodity, or load proxies missing from public evidence?",
        ],
    },
    "retail_cpg": {
        "aliases": ["retail", "consumer", "cpg", "restaurant", "store"],
        "priority_metrics": [
            "financial_metric:revenue",
            "financial_metric:cost_of_revenue",
            "financial_metric:gross_profit",
            "gross_margin",
            "financial_metric:inventory",
            "financial_metric:operating_cash_flow",
        ],
        "statement_weights": {"income_statement": 0.45, "balance_sheet": 0.35, "cash_flow_statement": 0.20},
        "analysis_questions": [
            "Is revenue supported by margin, inventory, and cash conversion?",
            "Are POS, scanner, traffic, or channel inventory tracker gaps material?",
        ],
    },
}

DEFAULT_FOCUS_POLICY = {
    "aliases": ["general"],
    "priority_metrics": [
        "financial_metric:revenue",
        "financial_metric:gross_profit",
        "gross_margin",
        "financial_metric:operating_income",
        "financial_metric:operating_cash_flow",
        "financial_metric:capex",
        "financial_metric:cash",
        "financial_metric:debt",
    ],
    "statement_weights": {"income_statement": 0.40, "balance_sheet": 0.30, "cash_flow_statement": 0.30},
    "analysis_questions": [
        "Do the three statements support the core thesis?",
        "Which peer or product-linked confirmation is still missing?",
    ],
}


def build_financial_statement_taxonomy() -> dict[str, Any]:
    return {
        "schema_version": FINANCIAL_STATEMENT_TAXONOMY_SCHEMA_VERSION,
        "policy": "canonical_metric_to_three_statement_line_item_v0_1",
        "metrics": [
            {"canonical_metric_id": metric_id, **dict(mapping)}
            for metric_id, mapping in sorted(STATEMENT_TAXONOMY.items())
        ],
        "derived_metric_mappings": [
            {"derived_metric_family": family, **dict(mapping)}
            for family, mapping in sorted(DERIVED_METRIC_TAXONOMY.items())
        ],
        "summary": {
            "canonical_metric_count": len(STATEMENT_TAXONOMY),
            "derived_metric_family_count": len(DERIVED_METRIC_TAXONOMY),
            "statement_types": sorted({row["statement_type"] for row in STATEMENT_TAXONOMY.values()}),
        },
    }


def build_industry_financial_focus_policy(state: Mapping[str, Any] | None = None) -> dict[str, Any]:
    state = state or {}
    industry_id, matched_signals = _infer_industry_id(state)
    policy = dict(INDUSTRY_FOCUS_POLICIES.get(industry_id) or DEFAULT_FOCUS_POLICY)
    priority_metrics = _unique_strings(policy.get("priority_metrics")) or _unique_strings(DEFAULT_FOCUS_POLICY["priority_metrics"])
    return {
        "schema_version": INDUSTRY_FINANCIAL_FOCUS_POLICY_SCHEMA_VERSION,
        "industry_id": industry_id,
        "matched_signals": matched_signals[:12],
        "priority_metrics": priority_metrics,
        "statement_weights": dict(policy.get("statement_weights") or DEFAULT_FOCUS_POLICY["statement_weights"]),
        "analysis_questions": _unique_strings(policy.get("analysis_questions"))[:6],
        "commercial_tracker_boundary": (
            "public filings and structured public rows can support financial statement analysis; sell-through, market share, "
            "channel inventory, prescription volume, POS, app revenue, and tracker forecasts remain explicit commercial gaps unless sourced from a permitted tracker"
        ),
        "policy": "industry_weighted_three_statement_focus_no_proxy_promotion_v0_1",
    }


def build_fundamental_statement_pack(state: Mapping[str, Any], *, max_items: int = 80) -> dict[str, Any]:
    derived_layer = (
        state.get("derived_metric_layer")
        if isinstance(state.get("derived_metric_layer"), Mapping)
        else build_derived_metric_layer(state)
    )
    input_facts = [dict(row) for row in derived_layer.get("input_facts") or [] if isinstance(row, Mapping)]
    derived_metrics = [dict(row) for row in derived_layer.get("derived_metrics") or [] if isinstance(row, Mapping)]
    line_items = _statement_line_items(input_facts, derived_metrics)
    focus_policy = build_industry_financial_focus_policy(state)
    focus_tickers = _focus_tickers(state, line_items)
    search_scope_tickers = _search_scope_tickers(state, focus_tickers, line_items)
    filtered_line_items = _prioritized_line_items(line_items, focus_policy=focus_policy, max_items=max_items)
    period_changes = _period_change_items(line_items, focus_tickers=focus_tickers, max_items=max_items)
    peer_comparisons = _peer_comparisons(
        line_items,
        focus_tickers=focus_tickers,
        search_scope_tickers=search_scope_tickers,
        focus_policy=focus_policy,
        max_items=max_items,
    )
    industry_coverage = _industry_focus_coverage(
        line_items,
        focus_policy=focus_policy,
        focus_tickers=focus_tickers,
        search_scope_tickers=search_scope_tickers,
    )
    integration_bridges = _integration_bridges(
        line_items,
        derived_metrics,
        state=state,
        focus_tickers=focus_tickers,
        focus_policy=focus_policy,
    )
    gaps = _analysis_gaps(
        focus_policy=focus_policy,
        industry_coverage=industry_coverage,
        peer_comparisons=peer_comparisons,
        focus_tickers=focus_tickers,
        search_scope_tickers=search_scope_tickers,
    )
    pack = {
        "schema_version": FUNDAMENTAL_STATEMENT_PACK_SCHEMA_VERSION,
        "policy": "three_statement_peer_industry_financial_pack_from_reconciled_public_facts_v0_1",
        "run_id": str(state.get("run_id") or ""),
        "focus_tickers": focus_tickers,
        "search_scope_tickers": search_scope_tickers,
        "taxonomy": build_financial_statement_taxonomy(),
        "industry_focus_policy": focus_policy,
        "statement_line_items": filtered_line_items,
        "period_changes": period_changes,
        "peer_comparisons": peer_comparisons,
        "industry_focus_coverage": industry_coverage,
        "integration_bridges": integration_bridges,
        "analysis_gaps": gaps,
        "source_boundary": {
            "financial_statement_authority": "resolved reconciliation facts and derived metrics whose inputs pass gates",
            "peer_comparison_boundary": "same metric, unit, period key, and comparable company scope only",
            "product_bridge_boundary": "product or segment rows explain financial bridge only when company-disclosed exact rows are present",
            "proxy_boundary": "industry, public web, relationship, and semantic rows are context or gap evidence, not company financial facts",
        },
        "summary": _pack_summary(filtered_line_items, period_changes, peer_comparisons, industry_coverage, gaps),
    }
    pack["validation"] = validate_fundamental_statement_pack(pack)
    return _jsonable(pack)


def compact_fundamental_statement_pack(payload: Mapping[str, Any], *, max_line_items: int = 16) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or not payload:
        return {}
    return {
        "schema_version": payload.get("schema_version") or "",
        "industry_focus_policy": payload.get("industry_focus_policy") or {},
        "summary": payload.get("summary") or {},
        "statement_line_items": [dict(item) for item in payload.get("statement_line_items") or [] if isinstance(item, Mapping)][:max_line_items],
        "period_changes": [dict(item) for item in payload.get("period_changes") or [] if isinstance(item, Mapping)][:12],
        "peer_comparisons": [dict(item) for item in payload.get("peer_comparisons") or [] if isinstance(item, Mapping)][:12],
        "industry_focus_coverage": [dict(item) for item in payload.get("industry_focus_coverage") or [] if isinstance(item, Mapping)][:16],
        "integration_bridges": [dict(item) for item in payload.get("integration_bridges") or [] if isinstance(item, Mapping)][:10],
        "analysis_gaps": [dict(item) for item in payload.get("analysis_gaps") or [] if isinstance(item, Mapping)][:10],
        "source_boundary": payload.get("source_boundary") or {},
    }


def build_fundamental_peer_statement_panel(state: Mapping[str, Any], *, max_items: int = 80) -> dict[str, Any]:
    pack = (
        state.get("fundamental_statement_pack")
        if isinstance(state.get("fundamental_statement_pack"), Mapping)
        else build_fundamental_statement_pack(state, max_items=max_items)
    )
    line_items = [dict(item) for item in pack.get("statement_line_items") or [] if isinstance(item, Mapping)]
    period_changes = [dict(item) for item in pack.get("period_changes") or [] if isinstance(item, Mapping)]
    peer_comparisons = [dict(item) for item in pack.get("peer_comparisons") or [] if isinstance(item, Mapping)]
    integration_bridges = [dict(item) for item in pack.get("integration_bridges") or [] if isinstance(item, Mapping)]
    industry_coverage = [dict(item) for item in pack.get("industry_focus_coverage") or [] if isinstance(item, Mapping)]
    statement_types = {"income_statement", "balance_sheet", "cash_flow_statement"}
    peer_scope_requested = len(_unique_strings(pack.get("search_scope_tickers"))) > len(_unique_strings(pack.get("focus_tickers")))
    product_bridges = [row for row in integration_bridges if str(row.get("bridge_type") or "") in {"product_financial_bridge", "product_demand_quality_bridge"}]
    capital_bridges = [row for row in integration_bridges if str(row.get("bridge_type") or "") == "capital_financing_bridge"]
    derived_rows = [
        row
        for row in line_items
        if str(row.get("source_layer") or "") == "derived_metric"
        or str(row.get("canonical_metric_id") or "") in DERIVED_METRIC_TAXONOMY
    ]
    panel = {
        "schema_version": FUNDAMENTAL_PEER_STATEMENT_PANEL_SCHEMA_VERSION,
        "policy": "three_statement_peer_product_capital_bridge_panel_from_fundamental_statement_pack_v0_1",
        "run_id": str(pack.get("run_id") or state.get("run_id") or ""),
        "focus_tickers": _unique_strings(pack.get("focus_tickers")),
        "search_scope_tickers": _unique_strings(pack.get("search_scope_tickers")),
        "industry_financial_focus_policy": pack.get("industry_focus_policy") or {},
        "three_statement_metric_panel": _three_statement_metric_panel(line_items, period_changes),
        "peer_comparable_metric_panel": {
            "peer_scope_requested": peer_scope_requested,
            "comparison_count": len(peer_comparisons),
            "comparisons": peer_comparisons[: max(8, min(24, max_items // 3))],
            "claim_boundary": "same_metric_period_unit_peer_rows_only",
        },
        "industry_priority_metric_panel": {
            "available_count": len([row for row in industry_coverage if row.get("available")]),
            "missing_count": len([row for row in industry_coverage if not row.get("available")]),
            "coverage": industry_coverage[: max(8, min(24, max_items // 3))],
        },
        "derived_metric_panel": {
            "derived_metric_count": len(derived_rows),
            "rows": derived_rows[: max(8, min(20, max_items // 4))],
            "claim_boundary": "derived metrics require visible source inputs and gate_status pass_or_warn",
        },
        "product_financial_bridge": {
            "available": bool(product_bridges),
            "bridges": product_bridges[:8],
            "claim_boundary": "product bridge supports product/segment-to-financial analysis only when company-disclosed rows exist",
        },
        "capital_funding_bridge": {
            "available": bool(capital_bridges),
            "bridges": capital_bridges[:8],
            "claim_boundary": "capital bridge supports cash/capex/debt/FCF analysis from public financial rows",
        },
        "statement_anomaly_detector": _statement_anomaly_detector(period_changes, peer_comparisons),
        "analysis_gates": {
            "three_statement_coverage": statement_types <= {str(row.get("statement_type") or "") for row in line_items},
            "peer_comparison_ready": bool(peer_comparisons) if peer_scope_requested else True,
            "industry_focus_ready": bool(pack.get("industry_focus_policy")),
            "period_change_ready": bool(period_changes),
            "derived_metric_ready": bool(derived_rows),
            "product_financial_bridge_available": bool(product_bridges),
            "capital_funding_bridge_available": bool(capital_bridges),
        },
        "analysis_gaps": [dict(item) for item in pack.get("analysis_gaps") or [] if isinstance(item, Mapping)][:12],
        "source_boundary": pack.get("source_boundary") or {},
        "summary": {
            "line_item_count": len(line_items),
            "statement_type_counts": dict(sorted(Counter(str(row.get("statement_type") or "") for row in line_items).items())),
            "period_change_count": len(period_changes),
            "peer_comparison_count": len(peer_comparisons),
            "derived_metric_count": len(derived_rows),
            "product_bridge_count": len(product_bridges),
            "capital_bridge_count": len(capital_bridges),
            "anomaly_count": 0,
        },
    }
    panel["summary"]["anomaly_count"] = len(panel["statement_anomaly_detector"].get("items") or [])
    panel["validation"] = validate_fundamental_peer_statement_panel(panel)
    return _jsonable(panel)


def compact_fundamental_peer_statement_panel(payload: Mapping[str, Any], *, max_items: int = 12) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or not payload:
        return {}
    compact = {
        "schema_version": payload.get("schema_version") or "",
        "industry_financial_focus_policy": payload.get("industry_financial_focus_policy") or {},
        "summary": payload.get("summary") or {},
        "analysis_gates": payload.get("analysis_gates") or {},
        "source_boundary": payload.get("source_boundary") or {},
    }
    three_statement = payload.get("three_statement_metric_panel") if isinstance(payload.get("three_statement_metric_panel"), Mapping) else {}
    compact["three_statement_metric_panel"] = {
        "statement_type_counts": three_statement.get("statement_type_counts") or {},
        "statements": [dict(item) for item in three_statement.get("statements") or [] if isinstance(item, Mapping)][:3],
    }
    for key in (
        "peer_comparable_metric_panel",
        "industry_priority_metric_panel",
        "derived_metric_panel",
        "product_financial_bridge",
        "capital_funding_bridge",
    ):
        value = payload.get(key) if isinstance(payload.get(key), Mapping) else {}
        clean = dict(value)
        for row_key in ("comparisons", "coverage", "rows", "bridges"):
            if isinstance(clean.get(row_key), list):
                clean[row_key] = [dict(item) for item in clean.get(row_key) if isinstance(item, Mapping)][:max_items]
        compact[key] = clean
    detector = payload.get("statement_anomaly_detector") if isinstance(payload.get("statement_anomaly_detector"), Mapping) else {}
    compact["statement_anomaly_detector"] = {
        "threshold_policy": detector.get("threshold_policy") or "",
        "items": [dict(item) for item in detector.get("items") or [] if isinstance(item, Mapping)][:max_items],
    }
    compact["analysis_gaps"] = [dict(item) for item in payload.get("analysis_gaps") or [] if isinstance(item, Mapping)][:max_items]
    return compact


def validate_fundamental_peer_statement_panel(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if str(payload.get("schema_version") or "") != FUNDAMENTAL_PEER_STATEMENT_PANEL_SCHEMA_VERSION:
        errors.append({"type": "unexpected_schema_version", "schema_version": payload.get("schema_version")})
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    gates = payload.get("analysis_gates") if isinstance(payload.get("analysis_gates"), Mapping) else {}
    if int(summary.get("line_item_count") or 0) <= 0:
        errors.append({"type": "line_items_required"})
    if not gates.get("three_statement_coverage"):
        warnings.append({"type": "three_statement_coverage_incomplete"})
    if not gates.get("peer_comparison_ready"):
        warnings.append({"type": "peer_comparison_not_ready"})
    if not gates.get("period_change_ready"):
        warnings.append({"type": "period_change_not_ready"})
    if not gates.get("product_financial_bridge_available"):
        warnings.append({"type": "product_financial_bridge_not_available"})
    if not gates.get("capital_funding_bridge_available"):
        warnings.append({"type": "capital_funding_bridge_not_available"})
    return {
        "schema_version": "sec_agent_fundamental_peer_statement_panel_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def validate_fundamental_statement_pack(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if str(payload.get("schema_version") or "") != FUNDAMENTAL_STATEMENT_PACK_SCHEMA_VERSION:
        errors.append({"type": "unexpected_schema_version", "schema_version": payload.get("schema_version")})
    line_items = [item for item in payload.get("statement_line_items") or [] if isinstance(item, Mapping)]
    seen_ids: set[str] = set()
    statement_types = {str(item.get("statement_type") or "") for item in line_items}
    for index, item in enumerate(line_items):
        line_item_id = str(item.get("line_item_id") or "")
        if not line_item_id:
            errors.append({"type": "line_item_id_required", "index": index})
        elif line_item_id in seen_ids:
            errors.append({"type": "duplicate_line_item_id", "line_item_id": line_item_id})
        seen_ids.add(line_item_id)
        for field in ("ticker", "statement_type", "level1", "canonical_metric_id", "period_key", "value", "unit", "evidence_refs"):
            if field == "evidence_refs":
                if not _unique_strings(item.get(field)):
                    errors.append({"type": "line_item_required_field_missing", "line_item_id": line_item_id, "field": field})
            elif not str(item.get(field) or "").strip():
                errors.append({"type": "line_item_required_field_missing", "line_item_id": line_item_id, "field": field})
    missing_statements = {"income_statement", "balance_sheet", "cash_flow_statement"} - statement_types
    if missing_statements:
        warnings.append({"type": "statement_type_missing_from_public_rows", "statement_types": sorted(missing_statements)})
    if payload.get("peer_comparisons"):
        for item in payload.get("peer_comparisons") or []:
            if isinstance(item, Mapping) and not _unique_strings(item.get("peer_values")):
                warnings.append({"type": "peer_comparison_without_peer_values", "comparison_id": item.get("comparison_id")})
    return {
        "schema_version": "sec_agent_fundamental_statement_pack_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def _three_statement_metric_panel(line_items: list[dict[str, Any]], period_changes: list[dict[str, Any]]) -> dict[str, Any]:
    period_change_by_line_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for change in period_changes:
        for line_item_id in _unique_strings(change.get("line_item_ids")):
            period_change_by_line_item[line_item_id].append(change)
    statements: list[dict[str, Any]] = []
    for statement_type in ("income_statement", "balance_sheet", "cash_flow_statement"):
        rows = [row for row in line_items if str(row.get("statement_type") or "") == statement_type]
        metric_counts = Counter(str(row.get("canonical_metric_id") or row.get("metric_family") or "") for row in rows)
        latest_rows = sorted(
            rows,
            key=lambda row: (str(row.get("ticker") or ""), str(row.get("period_sort_key") or ""), str(row.get("canonical_metric_id") or "")),
            reverse=True,
        )[:12]
        statements.append(
            {
                "statement_type": statement_type,
                "line_item_count": len(rows),
                "metric_counts": dict(sorted(metric_counts.items())),
                "latest_rows": latest_rows,
                "period_change_count": sum(len(period_change_by_line_item.get(str(row.get("line_item_id") or ""), [])) for row in rows),
                "claim_boundary": "statement panel rows are public fact/derived metric rows only",
            }
        )
    return {
        "statement_type_counts": dict(sorted(Counter(str(row.get("statement_type") or "") for row in line_items).items())),
        "statements": statements,
    }


def _statement_anomaly_detector(
    period_changes: list[dict[str, Any]],
    peer_comparisons: list[dict[str, Any]],
    *,
    threshold_pct: Decimal = Decimal("20"),
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for row in period_changes:
        pct = _decimal_value(row.get("pct_change"))
        if pct is None or abs(pct) < threshold_pct:
            continue
        items.append(
            {
                "anomaly_id": _stable_id("statement_anomaly", row.get("change_id"), row.get("pct_change")),
                "anomaly_type": "period_change_magnitude",
                "ticker": row.get("ticker"),
                "canonical_metric_id": row.get("canonical_metric_id"),
                "period_key": row.get("current_period_key"),
                "value": row.get("pct_change"),
                "unit": "percent",
                "direction": "positive" if pct > 0 else "negative",
                "evidence_refs": _unique_strings(row.get("evidence_refs"))[:8],
                "line_item_ids": _unique_strings(row.get("line_item_ids"))[:6],
                "claim_boundary": "requires analyst interpretation; detector only flags magnitude",
            }
        )
    for row in peer_comparisons:
        rel = _decimal_value(row.get("relative_to_peer_average"))
        if rel is None or abs(rel) < threshold_pct:
            continue
        items.append(
            {
                "anomaly_id": _stable_id("statement_anomaly", row.get("comparison_id"), row.get("relative_to_peer_average")),
                "anomaly_type": "peer_average_deviation",
                "ticker": row.get("ticker"),
                "canonical_metric_id": row.get("canonical_metric_id"),
                "period_key": row.get("period_key"),
                "value": row.get("relative_to_peer_average"),
                "unit": "percent",
                "direction": "above_peer_average" if rel > 0 else "below_peer_average",
                "evidence_refs": _unique_strings(row.get("evidence_refs"))[:8],
                "line_item_ids": _unique_strings(row.get("line_item_ids"))[:6],
                "claim_boundary": "same metric/period/unit peer comparison; detector only flags deviation",
            }
        )
    return {
        "threshold_policy": f"abs(period_change_or_peer_deviation_pct)>={threshold_pct}",
        "items": items[:24],
    }


def _statement_line_items(input_facts: list[dict[str, Any]], derived_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for fact in input_facts:
        metric_id = str(fact.get("canonical_metric_id") or "")
        mapping = STATEMENT_TAXONOMY.get(metric_id)
        if not mapping:
            continue
        numeric_value = _decimal_value(fact.get("numeric_value") or fact.get("value"))
        if numeric_value is None:
            continue
        period = _period_parts(fact)
        product_key = _product_key(fact)
        item = {
            "line_item_id": _stable_id(
                "statement_line_item",
                fact.get("fact_id"),
                metric_id,
                fact.get("ticker"),
                fact.get("period_key"),
                product_key,
            ),
            "source_layer": "reconciled_fact",
            "source_fact_id": str(fact.get("fact_id") or ""),
            "ticker": str(fact.get("ticker") or "").upper(),
            "canonical_metric_id": metric_id,
            "metric_family": metric_id.split(":", 1)[-1],
            "statement_type": mapping["statement_type"],
            "level1": mapping["level1"],
            "level2": mapping["level2"],
            "level3": mapping["level3"],
            "analysis_role": mapping["analysis_role"],
            "product_or_segment": str(fact.get("product_or_segment") or ""),
            "product_key": product_key,
            "period_key": str(fact.get("period_key") or ""),
            "fiscal_year": period["fiscal_year"],
            "fiscal_period": period["fiscal_period"],
            "period_role": period["period_role"],
            "period_sort_key": period["sort_key"],
            "value": _decimal_text(numeric_value),
            "unit": str(fact.get("unit") or ""),
            "unit_family": str(fact.get("unit_family") or ""),
            "source_family": str(fact.get("source_family") or ""),
            "evidence_refs": _unique_strings([fact.get("evidence_ref"), fact.get("fact_id")])[:3],
            "gate_status": _fact_gate_status(fact),
            "exact_value_authority": True,
            "comparison_scope": "company_total" if product_key in COMPANY_TOTAL_KEYS else "product_or_segment",
        }
        items.append(item)
    for metric in derived_metrics:
        family = str(metric.get("derived_metric_family") or metric.get("formula_id") or "")
        mapping = DERIVED_METRIC_TAXONOMY.get(family)
        if not mapping:
            continue
        numeric_value = _decimal_value(metric.get("value"))
        if numeric_value is None:
            continue
        if str(metric.get("gate_status") or "") not in {"pass", "warn"}:
            continue
        period = _period_parts(metric)
        item = {
            "line_item_id": _stable_id(
                "statement_line_item",
                metric.get("derived_metric_id"),
                family,
                metric.get("ticker"),
                metric.get("period_key"),
                metric.get("product_key"),
            ),
            "source_layer": "derived_metric",
            "source_fact_id": str(metric.get("derived_metric_id") or ""),
            "ticker": str(metric.get("ticker") or "").upper(),
            "canonical_metric_id": family,
            "metric_family": family,
            "statement_type": mapping["statement_type"],
            "level1": mapping["level1"],
            "level2": mapping["level2"],
            "level3": mapping["level3"],
            "analysis_role": mapping["analysis_role"],
            "product_or_segment": str(metric.get("product_or_segment") or ""),
            "product_key": _product_key(metric),
            "period_key": str(metric.get("period_key") or ""),
            "fiscal_year": period["fiscal_year"],
            "fiscal_period": period["fiscal_period"],
            "period_role": period["period_role"],
            "period_sort_key": period["sort_key"],
            "value": _decimal_text(numeric_value),
            "unit": str(metric.get("unit") or ""),
            "unit_family": str(metric.get("unit_family") or ""),
            "source_family": "derived_metric_layer",
            "evidence_refs": _unique_strings(metric.get("source_evidence_refs") or metric.get("input_fact_ids") or metric.get("derived_metric_id"))[:4],
            "gate_status": str(metric.get("gate_status") or ""),
            "exact_value_authority": True,
            "formula": str(metric.get("formula") or ""),
            "input_fact_ids": _unique_strings(metric.get("input_fact_ids"))[:6],
            "comparison_scope": "company_total" if _product_key(metric) in COMPANY_TOTAL_KEYS else "product_or_segment",
        }
        items.append(item)
    return sorted(_dedupe_by_id(items, "line_item_id"), key=_line_item_sort_key)


def _prioritized_line_items(
    line_items: list[dict[str, Any]],
    *,
    focus_policy: Mapping[str, Any],
    max_items: int,
) -> list[dict[str, Any]]:
    priority_metrics = set(_unique_strings(focus_policy.get("priority_metrics")))
    weights = focus_policy.get("statement_weights") if isinstance(focus_policy.get("statement_weights"), Mapping) else {}

    def score(item: Mapping[str, Any]) -> tuple[int, int, str, str, str]:
        priority = 1 if str(item.get("canonical_metric_id") or "") in priority_metrics or str(item.get("metric_family") or "") in priority_metrics else 0
        statement_weight = int(float(weights.get(str(item.get("statement_type") or ""), 0.0) or 0.0) * 100)
        company_total = 1 if str(item.get("comparison_scope") or "") == "company_total" else 0
        return (-priority, -statement_weight, -company_total, str(item.get("ticker") or ""), str(item.get("period_sort_key") or ""))

    return sorted(line_items, key=score)[:max_items]


def _period_change_items(
    line_items: list[dict[str, Any]],
    *,
    focus_tickers: list[str],
    max_items: int,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    focus_set = set(focus_tickers)
    for item in line_items:
        if focus_set and str(item.get("ticker") or "") not in focus_set:
            continue
        if str(item.get("canonical_metric_id") or "") in PERIOD_CHANGE_EXCLUDED_METRICS:
            continue
        if str(item.get("metric_family") or "") in PERIOD_CHANGE_EXCLUDED_METRICS:
            continue
        key = (
            str(item.get("ticker") or ""),
            str(item.get("canonical_metric_id") or ""),
            str(item.get("product_key") or ""),
            str(item.get("fiscal_period") or ""),
            str(item.get("unit") or ""),
        )
        grouped[key].append(item)
    changes: list[dict[str, Any]] = []
    for key, rows in grouped.items():
        comparable = [row for row in rows if _int(row.get("fiscal_year")) is not None]
        comparable = sorted(comparable, key=lambda row: int(row.get("fiscal_year") or 0))
        if len(comparable) < 2:
            continue
        for previous, current in zip(comparable, comparable[1:]):
            prev_value = _decimal_value(previous.get("value"))
            curr_value = _decimal_value(current.get("value"))
            if prev_value is None or curr_value is None:
                continue
            pct_change = _safe_ratio(curr_value - prev_value, abs(prev_value), scale=Decimal("100")) if prev_value != 0 else None
            changes.append(
                {
                    "change_id": _stable_id("period_change", key, previous.get("line_item_id"), current.get("line_item_id")),
                    "ticker": current.get("ticker"),
                    "canonical_metric_id": current.get("canonical_metric_id"),
                    "statement_type": current.get("statement_type"),
                    "product_or_segment": current.get("product_or_segment"),
                    "current_period_key": current.get("period_key"),
                    "prior_period_key": previous.get("period_key"),
                    "period_basis": "same_fiscal_period_yoy" if current.get("fiscal_period") == previous.get("fiscal_period") else "compatible_period_change",
                    "current_value": current.get("value"),
                    "prior_value": previous.get("value"),
                    "absolute_change": _decimal_text(curr_value - prev_value),
                    "pct_change": _decimal_text(pct_change) if pct_change is not None else "",
                    "unit": current.get("unit"),
                    "evidence_refs": _unique_strings([*current.get("evidence_refs", []), *previous.get("evidence_refs", [])])[:6],
                    "line_item_ids": [previous.get("line_item_id"), current.get("line_item_id")],
                    "claim_boundary": "period_change_from_same_metric_unit_and_period_basis",
                }
            )
    return sorted(changes, key=lambda row: (str(row.get("ticker") or ""), str(row.get("canonical_metric_id") or ""), str(row.get("current_period_key") or "")), reverse=True)[:max_items]


def _peer_comparisons(
    line_items: list[dict[str, Any]],
    *,
    focus_tickers: list[str],
    search_scope_tickers: list[str],
    focus_policy: Mapping[str, Any],
    max_items: int,
) -> list[dict[str, Any]]:
    focus_set = set(focus_tickers)
    scope_set = set(search_scope_tickers) - focus_set
    if not focus_set or not scope_set:
        return []
    priority_metrics = set(_unique_strings(focus_policy.get("priority_metrics")))
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in line_items:
        if str(item.get("comparison_scope") or "") != "company_total":
            continue
        key = (
            str(item.get("canonical_metric_id") or ""),
            str(item.get("period_key") or ""),
            str(item.get("unit") or ""),
            str(item.get("statement_type") or ""),
        )
        grouped[key].append(item)
    comparisons: list[dict[str, Any]] = []
    for key, rows in grouped.items():
        focus_rows = [row for row in rows if str(row.get("ticker") or "") in focus_set]
        peer_rows = [row for row in rows if str(row.get("ticker") or "") in scope_set]
        if not focus_rows or not peer_rows:
            continue
        all_values = [(str(row.get("ticker") or ""), _decimal_value(row.get("value")), row) for row in [*focus_rows, *peer_rows]]
        numeric = [(ticker, value, row) for ticker, value, row in all_values if value is not None]
        if len(numeric) < 2:
            continue
        sorted_values = sorted(numeric, key=lambda item: item[1], reverse=True)
        ranks = {id(row): rank for rank, (_, _, row) in enumerate(sorted_values, start=1)}
        for focus_row in focus_rows:
            focus_value = _decimal_value(focus_row.get("value"))
            if focus_value is None:
                continue
            peer_values = []
            for peer_row in peer_rows:
                peer_value = _decimal_value(peer_row.get("value"))
                if peer_value is None:
                    continue
                peer_values.append(
                    {
                        "ticker": peer_row.get("ticker"),
                        "value": peer_row.get("value"),
                        "unit": peer_row.get("unit"),
                        "line_item_id": peer_row.get("line_item_id"),
                        "evidence_refs": _unique_strings(peer_row.get("evidence_refs"))[:4],
                    }
                )
            if not peer_values:
                continue
            avg_peer = sum((_decimal_value(item["value"]) or Decimal("0")) for item in peer_values) / Decimal(len(peer_values))
            comparison = {
                "comparison_id": _stable_id("peer_comparison", key, focus_row.get("line_item_id"), [item["line_item_id"] for item in peer_values]),
                "ticker": focus_row.get("ticker"),
                "canonical_metric_id": focus_row.get("canonical_metric_id"),
                "statement_type": focus_row.get("statement_type"),
                "period_key": focus_row.get("period_key"),
                "focus_value": focus_row.get("value"),
                "peer_average": _decimal_text(avg_peer),
                "relative_to_peer_average": _decimal_text(_safe_ratio(focus_value - avg_peer, abs(avg_peer), scale=Decimal("100"))) if avg_peer else "",
                "rank_within_scope": ranks.get(id(focus_row)),
                "scope_count": len(numeric),
                "peer_values": peer_values[:8],
                "unit": focus_row.get("unit"),
                "evidence_refs": _unique_strings(
                    [*focus_row.get("evidence_refs", []), *[ref for item in peer_values for ref in item.get("evidence_refs", [])]]
                )[:10],
                "line_item_ids": [focus_row.get("line_item_id"), *[item.get("line_item_id") for item in peer_values]],
                "priority_metric": str(focus_row.get("canonical_metric_id") or "") in priority_metrics
                or str(focus_row.get("metric_family") or "") in priority_metrics,
                "claim_boundary": "peer_comparison_same_metric_period_unit_public_rows_only",
            }
            comparisons.append(comparison)
    comparisons = sorted(comparisons, key=lambda row: (not bool(row.get("priority_metric")), str(row.get("ticker") or ""), str(row.get("canonical_metric_id") or "")))
    return comparisons[:max_items]


def _industry_focus_coverage(
    line_items: list[dict[str, Any]],
    *,
    focus_policy: Mapping[str, Any],
    focus_tickers: list[str],
    search_scope_tickers: list[str],
) -> list[dict[str, Any]]:
    focus_set = set(focus_tickers)
    scope_set = set(search_scope_tickers)
    rows_by_metric: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in line_items:
        metric_keys = {str(item.get("canonical_metric_id") or ""), str(item.get("metric_family") or "")}
        for metric in metric_keys:
            if metric:
                rows_by_metric[metric].append(item)
    coverage = []
    for metric in _unique_strings(focus_policy.get("priority_metrics")):
        rows = rows_by_metric.get(metric) or []
        focus_rows = [row for row in rows if str(row.get("ticker") or "") in focus_set]
        peer_rows = [row for row in rows if str(row.get("ticker") or "") in scope_set - focus_set]
        coverage.append(
            {
                "metric_id": metric,
                "available": bool(focus_rows),
                "focus_line_item_count": len(focus_rows),
                "peer_line_item_count": len(peer_rows),
                "latest_focus_periods": _latest_periods(focus_rows)[:4],
                "statement_types": sorted({str(row.get("statement_type") or "") for row in rows if row.get("statement_type")}),
                "coverage_status": "focus_and_peer_available" if focus_rows and peer_rows else "focus_only" if focus_rows else "missing_focus_metric",
                "evidence_refs": _unique_strings([ref for row in focus_rows[:4] for ref in row.get("evidence_refs", [])])[:8],
            }
        )
    return coverage


def _integration_bridges(
    line_items: list[dict[str, Any]],
    derived_metrics: list[dict[str, Any]],
    *,
    state: Mapping[str, Any],
    focus_tickers: list[str],
    focus_policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    bridges: list[dict[str, Any]] = []
    focus_set = set(focus_tickers)
    focus_items = [item for item in line_items if not focus_set or str(item.get("ticker") or "") in focus_set]
    product_rows = [row for row in focus_items if str(row.get("product_key") or "") not in COMPANY_TOTAL_KEYS]
    if product_rows:
        bridges.append(
            {
                "bridge_id": "product_line_to_financial_statement",
                "bridge_type": "product_financial_bridge",
                "status": "available",
                "statement_line_item_ids": [row.get("line_item_id") for row in product_rows[:10]],
                "evidence_refs": _unique_strings([ref for row in product_rows[:10] for ref in row.get("evidence_refs", [])])[:10],
                "claim_boundary": "company_disclosed_product_or_segment_rows_only",
            }
        )
    capital_rows = [
        row
        for row in focus_items
        if str(row.get("canonical_metric_id") or "") in {"financial_metric:capex", "financial_metric:cash", "financial_metric:debt", "free_cash_flow", "net_debt"}
    ]
    if capital_rows:
        bridges.append(
            {
                "bridge_id": "capital_intensity_to_cash_capacity",
                "bridge_type": "capital_financing_bridge",
                "status": "available",
                "statement_line_item_ids": [row.get("line_item_id") for row in capital_rows[:10]],
                "evidence_refs": _unique_strings([ref for row in capital_rows[:10] for ref in row.get("evidence_refs", [])])[:10],
                "claim_boundary": "capital_bridge_requires_cash_capex_debt_or_fcf_public_rows",
            }
        )
    working_capital_rows = [
        row
        for row in focus_items
        if str(row.get("canonical_metric_id") or "") in {"financial_metric:inventory", "inventory_days", "financial_metric:cost_of_revenue"}
    ]
    if working_capital_rows:
        bridges.append(
            {
                "bridge_id": "working_capital_to_demand_quality",
                "bridge_type": "product_demand_quality_bridge",
                "status": "available",
                "statement_line_item_ids": [row.get("line_item_id") for row in working_capital_rows[:10]],
                "evidence_refs": _unique_strings([ref for row in working_capital_rows[:10] for ref in row.get("evidence_refs", [])])[:10],
                "claim_boundary": "working_capital_bridge_requires_inventory_or_cost_rows",
            }
        )
    industry_rows = [
        *[dict(row) for row in state.get("industry_snapshot_rows") or [] if isinstance(row, Mapping)],
        *[dict(row) for row in state.get("public_source_context_rows") or [] if isinstance(row, Mapping)],
    ]
    if industry_rows:
        bridges.append(
            {
                "bridge_id": "industry_proxy_to_financial_driver",
                "bridge_type": "industry_context_bridge",
                "status": "context_only",
                "industry_id": focus_policy.get("industry_id") or "",
                "context_row_count": len(industry_rows),
                "evidence_refs": _unique_strings([row.get("evidence_ref") for row in industry_rows])[:10],
                "claim_boundary": "industry_or_public_rows_support_context_not_company_financial_fact",
            }
        )
    return bridges[:12]


def _analysis_gaps(
    *,
    focus_policy: Mapping[str, Any],
    industry_coverage: list[dict[str, Any]],
    peer_comparisons: list[dict[str, Any]],
    focus_tickers: list[str],
    search_scope_tickers: list[str],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for row in industry_coverage:
        if row.get("coverage_status") == "missing_focus_metric":
            gaps.append(
                {
                    "gap_id": _stable_id("fundamental_gap", focus_policy.get("industry_id"), row.get("metric_id")),
                    "gap_type": "missing_priority_financial_metric",
                    "metric_id": row.get("metric_id"),
                    "focus_tickers": focus_tickers,
                    "reason": "industry_focus_metric_missing_from_reconciled_public_financial_rows",
                    "claim_boundary": "gap_only_do_not_fill_with_proxy",
                }
            )
        elif row.get("coverage_status") == "focus_only" and len(search_scope_tickers) > len(focus_tickers):
            gaps.append(
                {
                    "gap_id": _stable_id("fundamental_peer_gap", focus_policy.get("industry_id"), row.get("metric_id")),
                    "gap_type": "missing_peer_comparison_metric",
                    "metric_id": row.get("metric_id"),
                    "focus_tickers": focus_tickers,
                    "peer_scope": [ticker for ticker in search_scope_tickers if ticker not in focus_tickers],
                    "reason": "focus_metric_available_but_no_same_period_peer_rows",
                    "claim_boundary": "gap_only_do_not_compare_incompatible_periods_or_units",
                }
            )
    if len(search_scope_tickers) > len(focus_tickers) and not peer_comparisons:
        gaps.append(
            {
                "gap_id": _stable_id("fundamental_peer_comparison_absent", focus_tickers, search_scope_tickers),
                "gap_type": "peer_comparison_unavailable",
                "focus_tickers": focus_tickers,
                "peer_scope": [ticker for ticker in search_scope_tickers if ticker not in focus_tickers],
                "reason": "no_same_metric_period_unit_peer_rows_available_after_reconciliation",
                "claim_boundary": "peer_context_gap_only",
            }
        )
    return _dedupe_by_id(gaps, "gap_id")[:20]


def _pack_summary(
    line_items: list[dict[str, Any]],
    period_changes: list[dict[str, Any]],
    peer_comparisons: list[dict[str, Any]],
    industry_coverage: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "line_item_count": len(line_items),
        "statement_type_counts": dict(sorted(Counter(str(row.get("statement_type") or "") for row in line_items).items())),
        "ticker_count": len({str(row.get("ticker") or "") for row in line_items if row.get("ticker")}),
        "period_change_count": len(period_changes),
        "peer_comparison_count": len(peer_comparisons),
        "priority_metric_available_count": len([row for row in industry_coverage if row.get("available")]),
        "priority_metric_missing_count": len([row for row in industry_coverage if not row.get("available")]),
        "gap_count": len(gaps),
        "pack_status": "analysis_ready" if line_items else "no_reconciled_financial_rows",
    }


def _infer_industry_id(state: Mapping[str, Any]) -> tuple[str, list[str]]:
    text_parts: list[str] = []
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    activation_metadata = activation.get("metadata") if isinstance(activation.get("metadata"), Mapping) else {}
    text_parts.extend(
        [
            str(state.get("user_query") or ""),
            str(state.get("industry_schema") or ""),
            str(state.get("sector") or ""),
            str(query_contract.get("sector") or ""),
            str(query_contract.get("industry_schema") or ""),
            str(query_contract.get("industry") or ""),
            str(activation_metadata.get("industry_schema") or ""),
            str(activation.get("industry_schema") or ""),
            " ".join(_unique_strings(query_contract.get("selected_playbook_ids") or query_contract.get("playbook_ids"))),
            " ".join(_unique_strings(activation.get("selected_playbook_ids") or activation.get("playbook_ids"))),
            " ".join(_unique_strings(activation_metadata.get("selected_playbook_ids") or activation_metadata.get("playbook_ids"))),
            " ".join(_unique_strings(query_contract.get("metric_families"))),
            " ".join(_unique_strings(query_contract.get("focus_tickers") or query_contract.get("search_scope_tickers"))),
        ]
    )
    text = " ".join(text_parts).lower()
    matches: list[tuple[str, str]] = []
    for industry_id, policy in INDUSTRY_FOCUS_POLICIES.items():
        for alias in _unique_strings(policy.get("aliases")):
            alias_text = alias.lower().replace("_", " ")
            if _industry_alias_matches(alias_text, text):
                matches.append((industry_id, alias))
    if matches:
        return matches[0][0], [f"{industry}:{alias}" for industry, alias in matches[:12]]
    return "general_industrial", []


def _industry_alias_matches(alias_text: str, text: str) -> bool:
    alias_norm = _industry_signal_text(alias_text)
    if not alias_norm:
        return False
    text_norm = _industry_signal_text(text)
    if not text_norm:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(alias_norm)}(?![a-z0-9])"
    return re.search(pattern, text_norm) is not None


def _industry_signal_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _focus_tickers(state: Mapping[str, Any], line_items: list[dict[str, Any]]) -> list[str]:
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    tickers = _unique_upper(
        state.get("focus_tickers")
        or query_contract.get("focus_tickers")
        or (query_contract.get("scope") or {}).get("focus_tickers")
        or activation.get("focus_tickers")
    )
    return tickers or sorted({str(row.get("ticker") or "") for row in line_items if row.get("ticker")})[:1]


def _search_scope_tickers(state: Mapping[str, Any], focus_tickers: list[str], line_items: list[dict[str, Any]]) -> list[str]:
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    tickers = _unique_upper(
        state.get("search_scope_tickers")
        or query_contract.get("search_scope_tickers")
        or (query_contract.get("scope") or {}).get("universe_tickers")
        or activation.get("search_scope_tickers")
    )
    if tickers:
        return tickers
    observed = sorted({str(row.get("ticker") or "") for row in line_items if row.get("ticker")})
    return _unique_upper([*focus_tickers, *observed])


def _period_parts(row: Mapping[str, Any]) -> dict[str, Any]:
    fiscal_year = str(row.get("fiscal_year") or "")
    fiscal_period = str(row.get("fiscal_period") or "")
    period_key = str(row.get("period_key") or "")
    if (not fiscal_year or not fiscal_period) and period_key.startswith("fiscal:"):
        parts = period_key.split(":")
        if len(parts) >= 3:
            fiscal_year = fiscal_year or parts[1]
            fiscal_period = fiscal_period or parts[2]
    role = str(row.get("period_role") or "")
    if not role and period_key.startswith("fiscal:"):
        parts = period_key.split(":")
        if len(parts) >= 4:
            role = parts[3]
    year_int = _int(fiscal_year)
    sort_key = f"{year_int or 0:04d}:{_period_rank(fiscal_period):02d}:{role}"
    return {
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "period_role": role,
        "sort_key": sort_key,
    }


def _period_rank(value: str) -> int:
    text = str(value or "").strip().upper()
    if text in {"FY", "CY", "YEAR", "ANNUAL"}:
        return 5
    match = re.search(r"Q([1-4])", text)
    if match:
        return int(match.group(1))
    return 0


def _latest_periods(rows: list[dict[str, Any]]) -> list[str]:
    return [
        str(row.get("period_key") or "")
        for row in sorted(rows, key=lambda item: str(item.get("period_sort_key") or ""), reverse=True)
        if str(row.get("period_key") or "")
    ]


def _product_key(row: Mapping[str, Any]) -> str:
    value = str(row.get("product_key") or "").strip()
    if value:
        return value
    segment = str(row.get("product_or_segment") or "").strip()
    return _slug(segment) if segment else "__company_total__"


def _fact_gate_status(fact: Mapping[str, Any]) -> str:
    detail = fact.get("gate_status_detail") if isinstance(fact.get("gate_status_detail"), Mapping) else {}
    return str(detail.get("status") or detail.get("gate_status") or "pass")


def _line_item_sort_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("ticker") or ""),
        str(row.get("statement_type") or ""),
        str(row.get("canonical_metric_id") or ""),
        str(row.get("product_key") or ""),
        str(row.get("period_sort_key") or ""),
    )


def _decimal_value(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _decimal_text(value: Decimal | None) -> str:
    if value is None:
        return ""
    normalized = value.normalize()
    text = format(normalized, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _safe_ratio(numerator: Decimal, denominator: Decimal, *, scale: Decimal = Decimal("1")) -> Decimal | None:
    if denominator == 0:
        return None
    return (numerator / denominator) * scale


def _int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _unique_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Mapping):
        values = [str(value)]
    else:
        try:
            values = list(value)
        except TypeError:
            values = [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _unique_upper(value: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in _unique_strings(value):
        text = item.upper()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _dedupe_by_id(rows: list[dict[str, Any]], id_field: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row.get(id_field) or "")
        if not row_id:
            continue
        if row_id in seen:
            continue
        seen.add(row_id)
        result.append(row)
    return result


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=True)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _slug(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "unknown"


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value
