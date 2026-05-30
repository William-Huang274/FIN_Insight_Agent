from __future__ import annotations

import re
from typing import Any

from sec_agent.project_inventory import DEFAULT_SECTIONS, inventory_brief


QUERY_TASK_TYPES = {
    "ai_industry_financial_trend",
    "company_comparison",
    "metric_table",
    "risk_summary",
    "open_analysis",
    "general_sec_financial_question",
}

SCOPE_MODES = {"full_universe", "sector_representative", "focused_peer"}

METRIC_FAMILY_ONTOLOGY = sorted(
    {
        "advertising_revenue",
        "arr_or_recurring_proxy",
        "asset_quality",
        "capex",
        "capital_expenditure_proxy",
        "allowance_for_credit_losses",
        "capital_ratio",
        "cloud_revenue",
        "credit_quality",
        "credit_risk",
        "customer_concentration",
        "data_center_revenue",
        "deferred_revenue",
        "deposits",
        "free_cash_flow_proxy",
        "gross_margin",
        "infrastructure_software",
        "net_interest_income",
        "net_interest_margin",
        "net_charge_offs",
        "nonperforming_assets",
        "nonperforming_loans",
        "operating_cash_flow",
        "operating_income",
        "pipeline",
        "product_revenue",
        "provision_for_credit_losses",
        "research_and_development",
        "revenue",
        "loans",
        "rpo",
        "segment_growth",
        "semiconductor_solutions",
        "semiconductor_systems",
        "services_revenue",
        "subscription_revenue",
        "total_assets",
        "total_revenue",
    }
)

DEFAULT_REQUIRED_CAVEATS = (
    "Precise values must come from runtime Exact-Value Ledger only.",
)

DEFAULT_FORBIDDEN_CLAIMS = (
    "Do not use market prices, news, earnings calls, or macro data outside the project inventory.",
    "Do not make a risk or industry claim without retrieved SEC evidence.",
)

MARKET_SOURCE_TIER = "market_snapshot"
INDUSTRY_SOURCE_TIER = "industry_snapshot"
MARKET_SOURCE_POLICY = "SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT"
MARKET_WINDOWS = {"3M", "6M", "YTD", "1Y"}
MARKET_FIELDS = {
    "close_price",
    "market_cap",
    "enterprise_value",
    "return_1d",
    "return_5d",
    "return_1m",
    "return_3m",
    "return_ytd",
    "relative_return_vs_benchmark_3m",
    "max_drawdown_3m",
    "volatility_3m",
    "pe_ttm",
    "ev_sales_ttm",
    "ev_ebitda_ttm",
    "peer_ev_sales_rank",
    "peer_ev_sales_bucket",
}
MARKET_ANALYSIS_TOOLS = {
    "return_summary",
    "peer_relative_return",
    "valuation_peer_rank",
    "post_filing_event_return",
    "fundamental_market_divergence",
}
MARKET_REQUIRED_CAVEATS = (
    "Market snapshot evidence is non-real-time and must carry snapshot_id, as_of_date, and field refs.",
    "Market snapshot values support market/valuation/return claims only; SEC ledger remains authoritative for reported fundamentals.",
)
MARKET_FORBIDDEN_CLAIMS = (
    "Do not make unstamped current/latest market claims without market_snapshot as_of_date.",
    "Do not use market data to overwrite SEC reported financial facts.",
    "Do not infer unavailable market or valuation fields from model memory.",
)
INDUSTRY_REQUIRED_CAVEATS = (
    "Industry snapshot evidence is non-company-filed context and must carry source_family, provider, dataset_id, and as_of_date.",
    "Industry snapshot evidence can explain macro or sector context only; it cannot replace company-filed financial facts.",
)
INDUSTRY_FORBIDDEN_CLAIMS = (
    "Do not use industry snapshot values as company-reported revenue, margin, cash flow, balance-sheet, or segment facts.",
    "Do not treat industry snapshot observations as real-time market prices, news, analyst estimates, or company guidance.",
)

BANKING_METRIC_FAMILIES = {
    "allowance_for_credit_losses",
    "asset_quality",
    "capital_ratio",
    "credit_quality",
    "credit_risk",
    "deposits",
    "loans",
    "net_charge_offs",
    "net_interest_income",
    "net_interest_margin",
    "nonperforming_assets",
    "nonperforming_loans",
    "provision_for_credit_losses",
    "total_assets",
}

BANKING_TASK_TERMS = (
    "bank",
    "banking",
    "deposit",
    "deposits",
    "loan",
    "loans",
    "net interest",
    "credit risk",
    "银行",
    "存款",
    "贷款",
    "净利息",
    "信用风险",
)


def validate_query_contract(
    contract: dict[str, Any],
    *,
    selected_tickers: list[str],
    selected_years: list[int],
    project_inventory: dict[str, Any],
    sections: tuple[str, ...] = DEFAULT_SECTIONS,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    normalizations: list[dict[str, Any]] = []

    selected_tickers_clean = _unique_upper(selected_tickers)
    selected_years_clean = _unique_ints(selected_years)
    allowed_forms = _selected_form_types(project_inventory, selected_tickers_clean, selected_years_clean)
    allowed_source_tiers = _selected_source_tiers(
        project_inventory,
        selected_tickers_clean,
        selected_years_clean,
        allowed_forms,
    )

    clean = dict(contract)
    clean["schema_version"] = "interactive_query_contract_v0.2"

    task_type = str(clean.get("task_type") or "").strip()
    if task_type not in QUERY_TASK_TYPES:
        warnings.append({"type": "invalid_task_type_normalized", "value": task_type})
        task_type = "general_sec_financial_question"
    clean["task_type"] = task_type

    scope_tickers = _clamp_tickers(clean.get("search_scope_tickers"), selected_tickers_clean)
    if not scope_tickers:
        scope_tickers = selected_tickers_clean
        normalizations.append({"field": "search_scope_tickers", "action": "filled_from_selected_scope"})
    clean["search_scope_tickers"] = scope_tickers

    focus_tickers = _clamp_tickers(clean.get("focus_tickers"), scope_tickers)
    if not focus_tickers:
        focus_tickers = scope_tickers
        normalizations.append({"field": "focus_tickers", "action": "filled_from_search_scope"})
    clean["focus_tickers"] = focus_tickers

    years = _clamp_years(clean.get("years"), selected_years_clean)
    if not years:
        years = selected_years_clean
        normalizations.append({"field": "years", "action": "filled_from_selected_scope"})
    clean["years"] = years

    filing_types = _clamp_form_types(clean.get("filing_types"), allowed_forms)
    if not filing_types:
        filing_types = allowed_forms
        normalizations.append({"field": "filing_types", "action": "filled_from_project_inventory"})
    clean["filing_types"] = filing_types

    raw_source_tiers = clean.get("source_tiers") or (clean.get("scope") or {}).get("source_tiers")
    market_requested = _market_snapshot_requested(clean, raw_source_tiers)
    industry_requested = _industry_snapshot_requested(clean, raw_source_tiers)
    allowed_source_tiers_for_contract = list(allowed_source_tiers)
    if market_requested and MARKET_SOURCE_TIER not in allowed_source_tiers_for_contract:
        allowed_source_tiers_for_contract.append(MARKET_SOURCE_TIER)
    if industry_requested and INDUSTRY_SOURCE_TIER not in allowed_source_tiers_for_contract:
        allowed_source_tiers_for_contract.append(INDUSTRY_SOURCE_TIER)
    source_tiers = _clamp_source_tiers(raw_source_tiers, allowed_source_tiers_for_contract)
    if not source_tiers:
        source_tiers = allowed_source_tiers
        normalizations.append({"field": "source_tiers", "action": "filled_from_project_inventory"})
    if market_requested and not [tier for tier in source_tiers if tier != MARKET_SOURCE_TIER]:
        source_tiers = [tier for tier in allowed_source_tiers if tier not in source_tiers] + source_tiers
        normalizations.append({"field": "source_tiers", "action": "added_sec_tiers_for_market_snapshot_contract"})
    if market_requested and MARKET_SOURCE_TIER not in source_tiers:
        source_tiers.append(MARKET_SOURCE_TIER)
        normalizations.append({"field": "source_tiers", "action": "added_market_snapshot_tier"})
    if industry_requested and INDUSTRY_SOURCE_TIER not in source_tiers:
        source_tiers.append(INDUSTRY_SOURCE_TIER)
        normalizations.append({"field": "source_tiers", "action": "added_industry_snapshot_tier"})
    clean["source_tiers"] = source_tiers
    clean["source_policy"] = _source_policy_for_scope(filing_types, source_tiers)

    scope_mode = _scope_mode(clean, scope_tickers, focus_tickers)
    clean["scope_mode"] = scope_mode
    clean["scope"] = {
        "scope_mode": scope_mode,
        "universe_tickers": scope_tickers,
        "focus_tickers": focus_tickers,
        "universe_count": len(scope_tickers),
        "focus_count": len(focus_tickers),
        "years": years,
        "filing_types": filing_types,
        "source_tiers": source_tiers,
        "sec_sections": list(sections),
    }
    if scope_mode == "sector_representative":
        clean["scope"]["representative_tickers"] = focus_tickers

    if market_requested:
        clean["market_snapshot"] = _normalize_market_snapshot_contract(
            clean.get("market_snapshot"),
            warnings,
            normalizations,
        )

    clean["analysis_axes"] = _string_list(clean.get("analysis_axes"), max_items=12, max_chars=80)
    clean["facets"] = _string_list(clean.get("facets"), max_items=12, max_chars=96)
    clean["metric_families"] = _metric_family_list(clean.get("metric_families"), warnings, field="metric_families")
    clean["metric_queries"] = _string_list(clean.get("metric_queries"), max_items=10, max_chars=220)
    clean["qualitative_queries"] = _string_list(clean.get("qualitative_queries"), max_items=10, max_chars=220)
    clean["decomposed_tasks"] = _normalize_decomposed_tasks(clean.get("decomposed_tasks"), clean, warnings)
    banking_tickers = _banking_tickers_for_scope(clean["focus_tickers"], project_inventory)
    if not banking_tickers:
        clean = _drop_nonbank_banking_scope(clean, warnings, normalizations)
    else:
        clean = _scope_mixed_banking_metrics(clean, banking_tickers, warnings, normalizations)
    required_caveats = _normalize_required_caveats(
        _string_list(clean.get("required_caveats"), max_items=12, max_chars=260),
        normalizations,
    )
    if MARKET_SOURCE_TIER in set(source_tiers) or INDUSTRY_SOURCE_TIER in set(source_tiers):
        required_caveats = [caveat for caveat in required_caveats if caveat != "SEC-only evidence boundary."]
    clean["required_caveats"] = _ensure_required_items(
        required_caveats,
        (*DEFAULT_REQUIRED_CAVEATS, *_source_policy_caveats(filing_types, source_tiers)),
        "required_caveats",
        normalizations,
    )
    forbidden_claims = _string_list(clean.get("forbidden_claims"), max_items=12, max_chars=260)
    if MARKET_SOURCE_TIER in set(source_tiers) or INDUSTRY_SOURCE_TIER in set(source_tiers):
        forbidden_claims = [claim for claim in forbidden_claims if claim != DEFAULT_FORBIDDEN_CLAIMS[0]]
    clean["forbidden_claims"] = _ensure_required_items(
        forbidden_claims,
        _forbidden_claims_for_scope(source_tiers),
        "forbidden_claims",
        normalizations,
    )
    clean["evidence_gaps"] = _normalize_evidence_gaps(clean.get("evidence_gaps"))
    source_gap_tickers = _source_gap_tickers(clean, scope_tickers)
    source_coverage_gaps = _source_coverage_gaps(
        project_inventory,
        source_gap_tickers,
        years,
        filing_types,
        source_tiers,
    )
    clean["source_coverage_gaps"] = source_coverage_gaps
    clean["market_source_gaps"] = _market_source_gaps(clean.get("market_snapshot")) if market_requested else []
    if source_coverage_gaps:
        warnings.append(
            {
                "type": "source_coverage_gaps",
                "gap_count": len(source_coverage_gaps),
                "sample": source_coverage_gaps[:5],
            }
        )
    if clean["market_source_gaps"]:
        warnings.append(
            {
                "type": "market_source_gaps",
                "gap_count": len(clean["market_source_gaps"]),
                "sample": clean["market_source_gaps"][:5],
            }
        )
    clean["planner_confidence"] = _planner_confidence(clean.get("planner_confidence"))
    clean["project_inventory"] = inventory_brief(project_inventory)
    clean["project_inventory_digest"] = project_inventory.get("inventory_digest")

    if not clean["search_scope_tickers"]:
        errors.append({"type": "empty_search_scope"})
    if not clean["years"]:
        errors.append({"type": "empty_year_scope"})
    if not clean["filing_types"]:
        errors.append({"type": "empty_filing_type_scope"})
    if not clean["decomposed_tasks"]:
        errors.append({"type": "missing_decomposed_tasks"})
    if str(clean.get("task_type") or "") in {"ai_industry_financial_trend", "open_analysis"} and len(clean["decomposed_tasks"]) < 2:
        errors.append({"type": "broad_task_requires_multiple_decomposed_tasks", "task_count": len(clean["decomposed_tasks"])})
    elif _is_broad_task(clean) and len(clean["decomposed_tasks"]) < 2:
        warnings.append({"type": "broad_task_has_single_decomposed_task", "task_count": len(clean["decomposed_tasks"])})
    if not clean["metric_families"]:
        warnings.append({"type": "missing_metric_families"})

    report = {
        "schema_version": "query_contract_validation_report_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "normalizations": normalizations,
        "selected_scope": {
            "tickers": selected_tickers_clean,
            "years": selected_years_clean,
            "filing_types": allowed_forms,
            "source_tiers": source_tiers,
            "source_policy": clean["source_policy"],
        },
        "source_coverage_gaps": source_coverage_gaps,
        "market_source_gaps": clean["market_source_gaps"],
        "inventory_digest": project_inventory.get("inventory_digest"),
    }
    clean["query_contract_validation"] = report
    return {"contract": clean, "report": report}


def _selected_form_types(project_inventory: dict[str, Any], tickers: list[str], years: list[int]) -> list[str]:
    selected = {ticker.upper() for ticker in tickers}
    selected_years = {int(year) for year in years}
    forms = set()
    for company in project_inventory.get("companies") or []:
        ticker = str(company.get("ticker") or "").upper()
        if selected and ticker not in selected:
            continue
        for filing in company.get("filings") or []:
            year = _int_or_none(filing.get("year"))
            if selected_years and year not in selected_years:
                continue
            form_type = str(filing.get("form_type") or filing.get("source_type") or "").upper().strip()
            if form_type:
                forms.add(form_type)
    for gap in project_inventory.get("source_coverage_gaps") or []:
        if not isinstance(gap, dict):
            continue
        ticker = str(gap.get("ticker") or "").upper()
        if selected and ticker not in selected:
            continue
        year = _int_or_none(gap.get("year") or gap.get("filing_year") or gap.get("fiscal_year"))
        if selected_years and year not in selected_years:
            continue
        form_type = str(gap.get("form_type") or gap.get("source_type") or "").upper().strip()
        if form_type:
            forms.add(form_type)
    return sorted(forms) or ["10-K"]


def _source_gap_tickers(contract: dict[str, Any], scope_tickers: list[str]) -> list[str]:
    """Report inventory gaps for the asked-about company set, not the whole search universe."""
    selected = _unique_upper(contract.get("focus_tickers") or [])
    allowed = set(scope_tickers)
    for task in contract.get("decomposed_tasks") or []:
        if not isinstance(task, dict):
            continue
        selected.extend(
            ticker
            for ticker in _unique_upper([*(task.get("required_tickers") or []), *(task.get("peer_tickers") or [])])
            if ticker in allowed and ticker not in selected
        )
    return [ticker for ticker in selected if ticker in allowed] or scope_tickers


def _selected_source_tiers(
    project_inventory: dict[str, Any],
    tickers: list[str],
    years: list[int],
    form_types: list[str],
) -> list[str]:
    selected = {ticker.upper() for ticker in tickers}
    selected_years = {int(year) for year in years}
    selected_forms = {str(form).upper() for form in form_types}
    tiers = set()
    for company in project_inventory.get("companies") or []:
        ticker = str(company.get("ticker") or "").upper()
        if selected and ticker not in selected:
            continue
        for filing in company.get("filings") or []:
            year = _int_or_none(filing.get("year"))
            if selected_years and year not in selected_years:
                continue
            form_type = str(filing.get("form_type") or filing.get("source_type") or "").upper().strip()
            if selected_forms and form_type not in selected_forms:
                continue
            source_tier = str(filing.get("source_tier") or "primary_sec_filing").strip()
            if source_tier:
                tiers.add(source_tier)
    for gap in project_inventory.get("source_coverage_gaps") or []:
        if not isinstance(gap, dict):
            continue
        ticker = str(gap.get("ticker") or "").upper()
        if selected and ticker not in selected:
            continue
        year = _int_or_none(gap.get("year") or gap.get("filing_year") or gap.get("fiscal_year"))
        if selected_years and year not in selected_years:
            continue
        form_type = str(gap.get("form_type") or gap.get("source_type") or "").upper().strip()
        if selected_forms and form_type not in selected_forms:
            continue
        source_tier = str(gap.get("source_tier") or "").strip()
        if source_tier:
            tiers.add(source_tier)
    return sorted(tiers) or ["primary_sec_filing"]


def _source_policy_for_scope(filing_types: list[str], source_tiers: list[str]) -> str:
    forms = {str(form).upper() for form in filing_types if str(form)}
    tiers = {str(tier) for tier in source_tiers if str(tier)}
    if MARKET_SOURCE_TIER in tiers:
        return MARKET_SOURCE_POLICY
    primary_sec_only = not tiers or tiers <= {"primary_sec_filing"}
    mixed_with_8k = bool(
        "8-K" in forms
        and "company_authored_unaudited_sec_filing" in tiers
        and tiers <= {"primary_sec_filing", "company_authored_unaudited_sec_filing"}
    )
    if mixed_with_8k:
        return "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"
    if primary_sec_only and forms == {"10-K"}:
        return "SEC_ONLY_10K"
    if primary_sec_only and forms and forms <= {"10-K", "10-Q"} and "10-Q" in forms:
        return "SEC_PRIMARY_MIXED_RECENT"
    if primary_sec_only:
        return "SEC_ONLY"
    return "MIXED_SOURCE"


def _source_policy_caveats(filing_types: list[str], source_tiers: list[str]) -> tuple[str, ...]:
    forms = {str(form).upper() for form in filing_types if str(form)}
    tiers = {str(tier) for tier in source_tiers if str(tier)}
    caveats = []
    if MARKET_SOURCE_TIER in tiers and INDUSTRY_SOURCE_TIER in tiers:
        caveats.append("Project evidence boundary includes SEC filings, non-real-time market snapshot, and industry snapshot only.")
    elif MARKET_SOURCE_TIER in tiers:
        caveats.append("Project evidence boundary includes SEC filings and non-real-time market snapshot only.")
    elif INDUSTRY_SOURCE_TIER in tiers and "company_authored_unaudited_sec_filing" in tiers:
        caveats.append("Project evidence boundary includes SEC filings, company-authored 8-K material, and industry snapshot only.")
    elif INDUSTRY_SOURCE_TIER in tiers:
        caveats.append("Project evidence boundary includes SEC filings and industry snapshot only.")
    elif "company_authored_unaudited_sec_filing" in tiers:
        caveats.append("Project evidence boundary includes SEC filings and company-authored 8-K material only.")
    else:
        caveats.append("SEC-only evidence boundary.")
    if "10-Q" in forms:
        caveats.append(
            "10-Q evidence is unaudited quarterly SEC evidence; do not mix quarterly, YTD, and annual values without period caveats."
        )
    if {"10-K", "10-Q"} <= forms:
        caveats.append("When 10-K and 10-Q evidence both appear, label audited annual versus unaudited quarterly boundaries.")
    if "8-K" in forms:
        caveats.append(
            "8-K earnings-release evidence is company-authored unaudited management material; do not treat it as audited financial statement evidence."
        )
    if MARKET_SOURCE_TIER in tiers:
        caveats.extend(MARKET_REQUIRED_CAVEATS)
    if INDUSTRY_SOURCE_TIER in tiers:
        caveats.extend(INDUSTRY_REQUIRED_CAVEATS)
    return tuple(caveats)


def _forbidden_claims_for_scope(source_tiers: list[str]) -> tuple[str, ...]:
    tiers = {str(tier) for tier in source_tiers if str(tier)}
    if MARKET_SOURCE_TIER not in tiers and INDUSTRY_SOURCE_TIER not in tiers:
        return DEFAULT_FORBIDDEN_CLAIMS
    claims = [
        "Do not use news, earnings calls, or macro data outside the project inventory.",
        "Do not make a risk or industry claim without retrieved evidence.",
    ]
    if INDUSTRY_SOURCE_TIER in tiers:
        claims[0] = "Do not use news, earnings calls, or macro data outside retrieved project evidence."
        claims.extend(INDUSTRY_FORBIDDEN_CLAIMS)
    if MARKET_SOURCE_TIER in tiers:
        claims.extend(MARKET_FORBIDDEN_CLAIMS)
    return tuple(claims)


def _market_snapshot_requested(contract: dict[str, Any], raw_source_tiers: Any) -> bool:
    tiers = {str(tier or "").strip() for tier in _list_like(raw_source_tiers) if str(tier or "").strip()}
    market = contract.get("market_snapshot")
    if MARKET_SOURCE_TIER in tiers or str(contract.get("source_policy") or "") == MARKET_SOURCE_POLICY:
        return True
    if isinstance(market, dict):
        return bool(market.get("required") or market.get("snapshot_id") or market.get("as_of_date"))
    return False


def _industry_snapshot_requested(contract: dict[str, Any], raw_source_tiers: Any) -> bool:
    tiers = {str(tier or "").strip() for tier in _list_like(raw_source_tiers) if str(tier or "").strip()}
    if INDUSTRY_SOURCE_TIER in tiers:
        return True
    industry = contract.get("industry_snapshot")
    if isinstance(industry, dict):
        return bool(industry.get("required") or industry.get("source_families") or industry.get("snapshot_id"))
    requirements = contract.get("evidence_requirements") or []
    if isinstance(requirements, list):
        for requirement in requirements:
            if not isinstance(requirement, dict):
                continue
            req_tiers = {str(tier or "").strip() for tier in _list_like(requirement.get("source_tiers")) if str(tier or "").strip()}
            req_routes = {str(route or "").strip() for route in _list_like(requirement.get("evidence_routes")) if str(route or "").strip()}
            if INDUSTRY_SOURCE_TIER in req_tiers or INDUSTRY_SOURCE_TIER in req_routes:
                return True
    return False


def _normalize_market_snapshot_contract(
    value: Any,
    warnings: list[dict[str, Any]],
    normalizations: list[dict[str, Any]],
) -> dict[str, Any]:
    market = dict(value) if isinstance(value, dict) else {}
    if not isinstance(value, dict):
        normalizations.append({"field": "market_snapshot", "action": "created_required_market_snapshot_contract"})

    window = str(market.get("window") or market.get("market_window") or "3M").upper().strip()
    if window not in MARKET_WINDOWS:
        warnings.append({"type": "invalid_market_window_normalized", "value": window})
        window = "3M"

    fields = _market_field_list(market.get("fields") or market.get("market_fields"))
    if not fields:
        fields = [
            "close_price",
            "return_3m",
            "relative_return_vs_benchmark_3m",
            "max_drawdown_3m",
            "ev_sales_ttm",
        ]
        normalizations.append({"field": "market_snapshot.fields", "action": "filled_default_market_fields"})

    tools = _market_tool_list(market.get("analysis_tools") or market.get("market_analysis_tools"))
    if not tools:
        tools = ["return_summary", "peer_relative_return", "valuation_peer_rank"]
        normalizations.append({"field": "market_snapshot.analysis_tools", "action": "filled_default_market_tools"})

    snapshot_id = _short_text(market.get("snapshot_id"), 96)
    as_of_date = _date_text(market.get("as_of_date"))
    provider = _short_text(market.get("provider") or "manual_fixture", 80)
    clean = {
        "required": True,
        "snapshot_id": snapshot_id,
        "as_of_date": as_of_date,
        "window": window,
        "fields": fields,
        "analysis_tools": tools,
        "provider": provider,
    }
    if market.get("benchmark_ticker"):
        clean["benchmark_ticker"] = _short_text(market.get("benchmark_ticker"), 16).upper()
    return clean


def _market_source_gaps(market: Any) -> list[dict[str, Any]]:
    if not isinstance(market, dict) or not market.get("required"):
        return []
    gaps = []
    if not market.get("snapshot_id"):
        gaps.append({"source_tier": MARKET_SOURCE_TIER, "reason": "missing_market_snapshot_id"})
    if not market.get("as_of_date"):
        gaps.append({"source_tier": MARKET_SOURCE_TIER, "reason": "missing_market_snapshot_as_of_date"})
    if not market.get("fields"):
        gaps.append({"source_tier": MARKET_SOURCE_TIER, "reason": "missing_market_fields"})
    if not market.get("analysis_tools"):
        gaps.append({"source_tier": MARKET_SOURCE_TIER, "reason": "missing_market_analysis_tools"})
    return gaps


def _market_field_list(value: Any) -> list[str]:
    out = []
    for item in _list_like(value):
        field = _slug(str(item or ""))
        if field in MARKET_FIELDS and field not in out:
            out.append(field)
        if len(out) >= 16:
            break
    return out


def _market_tool_list(value: Any) -> list[str]:
    out = []
    for item in _list_like(value):
        tool = _slug(str(item or ""))
        if tool in MARKET_ANALYSIS_TOOLS and tool not in out:
            out.append(tool)
        if len(out) >= 5:
            break
    return out


def _date_text(value: Any) -> str:
    text = _short_text(value, 20)
    return text if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else ""


def _list_like(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


def _source_coverage_gaps(
    project_inventory: dict[str, Any],
    tickers: list[str],
    years: list[int],
    filing_types: list[str],
    source_tiers: list[str],
) -> list[dict[str, Any]]:
    lookup: dict[tuple[str, int, str], set[str]] = {}
    available_forms_by_year: dict[int, set[str]] = {}
    selected_tickers = {str(ticker or "").upper() for ticker in tickers if str(ticker or "").strip()}
    selected_years = {int(year) for year in years if _int_or_none(year) is not None}
    for company in project_inventory.get("companies") or []:
        ticker = str(company.get("ticker") or "").upper()
        if not ticker:
            continue
        if selected_tickers and ticker not in selected_tickers:
            continue
        for filing in company.get("filings") or []:
            year = _int_or_none(filing.get("year"))
            form_type = str(filing.get("form_type") or filing.get("source_type") or "").upper().strip()
            if year is None or not form_type:
                continue
            if selected_years and int(year) not in selected_years:
                continue
            available_forms_by_year.setdefault(int(year), set()).add(form_type)
            key = (ticker, int(year), form_type)
            lookup.setdefault(key, set()).add(str(filing.get("source_tier") or "primary_sec_filing"))

    gaps: list[dict[str, Any]] = []
    gap_keys: set[tuple[str, int, str, str]] = set()
    sec_source_tiers = [str(tier) for tier in source_tiers if str(tier) and str(tier) != MARKET_SOURCE_TIER]
    required_tiers = sec_source_tiers or ["primary_sec_filing"]
    selected_forms = {str(form or "").upper().strip() for form in filing_types if str(form or "").strip()}
    for gap in _inventory_source_coverage_gaps(
        project_inventory,
        tickers=tickers,
        years=years,
        filing_types=filing_types,
        source_tiers=sec_source_tiers,
    ):
        key = (
            str(gap.get("ticker") or "").upper(),
            int(gap.get("year") or 0),
            str(gap.get("form_type") or "").upper(),
            str(gap.get("reason") or gap.get("reason_code") or ""),
        )
        if key in gap_keys:
            continue
        gaps.append(gap)
        gap_keys.add(key)
    for ticker in tickers:
        ticker_text = str(ticker or "").upper()
        if not ticker_text:
            continue
        for year in years:
            year_value = _int_or_none(year)
            if year_value is None:
                continue
            year_available_forms = available_forms_by_year.get(int(year_value), set())
            year_required_forms = sorted((selected_forms & year_available_forms) or selected_forms)
            for form_type in year_required_forms:
                form = str(form_type or "").upper().strip()
                if not form:
                    continue
                key = (ticker_text, int(year_value), form)
                available_tiers = lookup.get(key, set())
                if not available_tiers:
                    reason = _missing_form_reason(form)
                    gap_key = (ticker_text, int(year_value), form, reason)
                    if gap_key not in gap_keys:
                        gaps.append(
                            {
                                "ticker": ticker_text,
                                "year": int(year_value),
                                "form_type": form,
                                "period_type": _period_type_for_form(form),
                                "reason": reason,
                            }
                        )
                        gap_keys.add(gap_key)
                    continue
                required_tiers_for_form = _required_source_tiers_for_form(form, required_tiers)
                missing_tiers = sorted(set(required_tiers_for_form) - available_tiers)
                if missing_tiers:
                    reason = "source_tier_not_in_inventory"
                    gap_key = (ticker_text, int(year_value), form, reason)
                    if gap_key not in gap_keys:
                        gaps.append(
                            {
                                "ticker": ticker_text,
                                "year": int(year_value),
                                "form_type": form,
                                "missing_source_tiers": missing_tiers,
                                "available_source_tiers": sorted(available_tiers),
                                "period_type": _period_type_for_form(form),
                                "reason": reason,
                            }
                        )
                        gap_keys.add(gap_key)
                if len(gaps) >= 40:
                    return gaps
    return gaps


def _inventory_source_coverage_gaps(
    project_inventory: dict[str, Any],
    *,
    tickers: list[str],
    years: list[int],
    filing_types: list[str],
    source_tiers: list[str],
) -> list[dict[str, Any]]:
    selected_tickers = {str(ticker or "").upper() for ticker in tickers if str(ticker or "").strip()}
    selected_years = {int(year) for year in years if _int_or_none(year) is not None}
    selected_forms = {str(form or "").upper().strip() for form in filing_types if str(form or "").strip()}
    selected_tiers = {str(tier or "").strip() for tier in source_tiers if str(tier or "").strip()}
    gaps: list[dict[str, Any]] = []
    for row in project_inventory.get("source_coverage_gaps") or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        year = _int_or_none(row.get("year") or row.get("filing_year") or row.get("fiscal_year"))
        form = str(row.get("form_type") or row.get("source_type") or "").upper().strip()
        tier = str(row.get("source_tier") or "").strip()
        if not ticker or year is None or not form:
            continue
        if selected_tickers and ticker not in selected_tickers:
            continue
        if selected_years and int(year) not in selected_years:
            continue
        if selected_forms and form not in selected_forms:
            continue
        if selected_tiers and tier and tier not in selected_tiers:
            continue
        reason = str(row.get("reason_code") or row.get("reason") or "source_gap_in_inventory").strip()
        gap = {
            "ticker": ticker,
            "year": int(year),
            "form_type": form,
            "source_tier": tier or None,
            "period_type": _period_type_for_form(form),
            "reason": reason,
        }
        if row.get("category"):
            gap["category"] = row.get("category")
        if row.get("category_slug"):
            gap["category_slug"] = row.get("category_slug")
        if row.get("source"):
            gap["source"] = row.get("source")
        gaps.append(gap)
    return gaps


def _required_source_tiers_for_form(form_type: str, source_tiers: list[str]) -> list[str]:
    form = str(form_type or "").upper().strip()
    requested = [str(tier) for tier in source_tiers if str(tier)]
    if form in {"10-K", "10-Q"} and "primary_sec_filing" in requested:
        return ["primary_sec_filing"]
    if form == "8-K" and "company_authored_unaudited_sec_filing" in requested:
        return ["company_authored_unaudited_sec_filing"]
    return requested or ["primary_sec_filing"]


def _period_type_for_form(form_type: str) -> str:
    form = str(form_type or "").upper()
    if form == "10-K":
        return "annual"
    if form == "10-Q":
        return "quarterly"
    if form == "8-K":
        return "current_report"
    return "unknown"


def _missing_form_reason(form_type: str) -> str:
    form = str(form_type or "").upper().replace("-", "").lower()
    if form:
        return f"{form}_not_in_inventory"
    return "filing_type_not_in_inventory"


def _normalize_decomposed_tasks(value: Any, contract: dict[str, Any], warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks = []
    allowed_tickers = _unique_upper(contract.get("search_scope_tickers") or contract.get("focus_tickers") or [])
    for idx, item in enumerate(value or [], start=1):
        if not isinstance(item, dict):
            warnings.append({"type": "dropped_non_object_decomposed_task", "index": idx})
            continue
        task_id = _slug(str(item.get("task_id") or f"task_{idx}"))[:64] or f"task_{idx}"
        priority = str(item.get("priority") or "supporting").strip().lower()
        if priority not in {"primary", "supporting", "caveat"}:
            warnings.append({"type": "invalid_task_priority_normalized", "task_id": task_id, "value": priority})
            priority = "supporting"
        families = _metric_family_list(item.get("required_metric_families"), warnings, field=f"decomposed_tasks.{task_id}.required_metric_families")
        if not families:
            families = [str(family) for family in (contract.get("metric_families") or [])[:4]]
        question = _short_text(item.get("question_zh") or item.get("question") or "", 260)
        if not question:
            question = f"Evaluate task {task_id} within the SEC evidence boundary."
            warnings.append({"type": "missing_task_question_filled", "task_id": task_id})
        required_tickers = _clamp_tickers(item.get("required_tickers"), allowed_tickers)
        peer_tickers = [ticker for ticker in _clamp_tickers(item.get("peer_tickers"), allowed_tickers) if ticker not in set(required_tickers)]
        tasks.append(
            {
                "task_id": task_id,
                "question_zh": question,
                "priority": priority,
                "required_metric_families": families,
                "required_tickers": required_tickers,
                "peer_tickers": peer_tickers,
            }
        )
        if len(tasks) >= 10:
            break
    return tasks


def _scope_has_banking_company(focus_tickers: list[str], project_inventory: dict[str, Any]) -> bool:
    return bool(_banking_tickers_for_scope(focus_tickers, project_inventory))


def _banking_tickers_for_scope(focus_tickers: list[str], project_inventory: dict[str, Any]) -> list[str]:
    focus = {str(ticker or "").upper() for ticker in focus_tickers}
    banking: list[str] = []
    for category in (project_inventory.get("categories") or []):
        category_name = str(category.get("category") or "").lower()
        if "bank" not in category_name and "financial" not in category_name:
            continue
        for ticker in category.get("tickers") or []:
            ticker_text = str(ticker or "").upper()
            if ticker_text in focus and ticker_text not in banking:
                banking.append(ticker_text)
    for company in project_inventory.get("companies") or []:
        ticker = str(company.get("ticker") or "").upper()
        if ticker not in focus or ticker in banking:
            continue
        category_name = str(company.get("category") or "").lower()
        if "bank" in category_name or "financial" in category_name:
            banking.append(ticker)
    return [ticker for ticker in focus_tickers if str(ticker).upper() in set(banking)]


def _scope_mixed_banking_metrics(
    contract: dict[str, Any],
    banking_tickers: list[str],
    warnings: list[dict[str, Any]],
    normalizations: list[dict[str, Any]],
) -> dict[str, Any]:
    clean = dict(contract)
    banking_set = {str(ticker).upper() for ticker in banking_tickers}
    focus = _unique_upper(clean.get("focus_tickers") or [])
    mixed_scope = bool(banking_set and set(focus) - banking_set)
    if not mixed_scope:
        rules = clean.get("ledger_rules") if isinstance(clean.get("ledger_rules"), dict) else {}
        rules["banking_metric_tickers"] = [ticker for ticker in focus if ticker in banking_set]
        clean["ledger_rules"] = rules
        return clean

    metric_families = list(clean.get("metric_families") or [])
    filtered_metric_families = [family for family in metric_families if family not in BANKING_METRIC_FAMILIES]
    if len(filtered_metric_families) != len(metric_families):
        normalizations.append({"field": "metric_families", "action": "scoped_banking_families_to_banking_tasks"})
    clean["metric_families"] = filtered_metric_families

    filtered_tasks = []
    for task in clean.get("decomposed_tasks") or []:
        task = dict(task)
        families = list(task.get("required_metric_families") or [])
        banking_families = [family for family in families if family in BANKING_METRIC_FAMILIES]
        if not banking_families:
            filtered_tasks.append(task)
            continue
        task_text = " ".join(str(task.get(key) or "") for key in ("task_id", "question_zh", "question")).lower()
        required_tickers = _clamp_tickers(task.get("required_tickers"), focus)
        scoped_banking_tickers = [ticker for ticker in required_tickers if ticker in banking_set]
        has_banking_terms = _contains_any(task_text, BANKING_TASK_TERMS)
        if has_banking_terms and scoped_banking_tickers:
            if set(required_tickers) - banking_set:
                normalizations.append({"field": "decomposed_tasks.required_tickers", "action": "narrowed_banking_task_to_banking_tickers", "task_id": task.get("task_id")})
            task["required_tickers"] = scoped_banking_tickers
            filtered_tasks.append(task)
            continue
        task["required_metric_families"] = [family for family in families if family not in BANKING_METRIC_FAMILIES]
        warnings.append({"type": "dropped_banking_metric_family_for_mixed_nonbank_task", "task_id": task.get("task_id")})
        if task["required_metric_families"]:
            filtered_tasks.append(task)
    clean["decomposed_tasks"] = filtered_tasks

    rules = clean.get("ledger_rules") if isinstance(clean.get("ledger_rules"), dict) else {}
    rules["banking_metric_tickers"] = [ticker for ticker in focus if ticker in banking_set]
    clean["ledger_rules"] = rules
    return clean


def _drop_nonbank_banking_scope(
    contract: dict[str, Any],
    warnings: list[dict[str, Any]],
    normalizations: list[dict[str, Any]],
) -> dict[str, Any]:
    clean = dict(contract)
    metric_families = [family for family in clean.get("metric_families") or [] if family not in BANKING_METRIC_FAMILIES]
    if len(metric_families) != len(clean.get("metric_families") or []):
        normalizations.append({"field": "metric_families", "action": "dropped_banking_families_for_nonbank_scope"})
    clean["metric_families"] = metric_families

    filtered_tasks = []
    for task in clean.get("decomposed_tasks") or []:
        task_text = " ".join(str(task.get(key) or "") for key in ("task_id", "question_zh", "question")).lower()
        families = list(task.get("required_metric_families") or [])
        has_banking_terms = _contains_any(task_text, BANKING_TASK_TERMS)
        has_banking_families = any(family in BANKING_METRIC_FAMILIES for family in families)
        if has_banking_terms and has_banking_families:
            warnings.append({"type": "dropped_banking_task_for_nonbank_scope", "task_id": task.get("task_id")})
            continue
        filtered_families = [family for family in families if family not in BANKING_METRIC_FAMILIES]
        if len(filtered_families) != len(families):
            warnings.append({"type": "dropped_banking_metric_family_for_nonbank_task", "task_id": task.get("task_id")})
        task = dict(task)
        task["required_metric_families"] = filtered_families or metric_families[:4]
        filtered_tasks.append(task)
    clean["decomposed_tasks"] = filtered_tasks
    return clean


def _normalize_evidence_gaps(value: Any) -> list[dict[str, str]]:
    gaps = []
    for item in value or []:
        if isinstance(item, dict):
            task_id = _slug(str(item.get("task_id") or "gap"))[:64] or "gap"
            gap = _short_text(item.get("gap") or item.get("description") or "", 260)
        else:
            task_id = "gap"
            gap = _short_text(item, 260)
        if gap:
            gaps.append({"task_id": task_id, "gap": gap})
        if len(gaps) >= 10:
            break
    return gaps


def _metric_family_list(value: Any, warnings: list[dict[str, Any]], *, field: str) -> list[str]:
    allowed = set(METRIC_FAMILY_ONTOLOGY)
    out = []
    for item in value or []:
        family = str(item or "").strip()
        if not family:
            continue
        if family not in allowed:
            warnings.append({"type": "unknown_metric_family_dropped", "field": field, "value": family})
            continue
        if family not in out:
            out.append(family)
    return out[:20]


def _ensure_required_items(
    values: list[str],
    required: tuple[str, ...],
    field: str,
    normalizations: list[dict[str, Any]],
) -> list[str]:
    out = list(values)
    lower = " || ".join(item.lower() for item in out)
    for item in required:
        probe = item.lower().rstrip(".")
        if probe not in lower:
            out.append(item)
            normalizations.append({"field": field, "action": "added_required_item", "value": item})
    return out[:16]


def _normalize_required_caveats(values: list[str], normalizations: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for value in values:
        normalized = _normalize_required_caveat_text(value)
        if normalized != value:
            normalizations.append({"field": "required_caveats", "action": "normalized_false_no_number_caveat"})
        if normalized and normalized not in out:
            out.append(normalized)
    return out


def _normalize_required_caveat_text(value: str) -> str:
    text = str(value or "").strip()
    ledger_only_replacement = "精确数值必须从运行时 Exact-Value Ledger 提取；不得使用模型记忆或未授权来源补数。"
    replacements = {
        "精确数值必须从运行时Exact-Value Ledger提取，本协议不包含具体数字。": ledger_only_replacement,
        "精确数值必须从运行时Exact-Value Ledger提取，本协议不包含具体数值。": ledger_only_replacement,
        "精确数值必须从运行时Exact-Value Ledger提取，本协议不包含任何具体数字。": ledger_only_replacement,
        "精确数值必须从运行时Exact-Value Ledger提取，本协议不包含任何具体数值。": ledger_only_replacement,
        "精确数值必须从运行时Exact-Value Ledger提取，当前协议不包含具体数字。": ledger_only_replacement,
        "精确数值必须从运行时Exact-Value Ledger提取，当前协议不包含具体数值。": ledger_only_replacement,
        "精确数值必须从运行时Exact-Value Ledger提取，当前协议不包含任何具体数字。": ledger_only_replacement,
        "精确数值必须从运行时Exact-Value Ledger提取，当前协议不包含任何具体数值。": ledger_only_replacement,
        "所有精确数值必须来自运行时Exact-Value Ledger，本协议不包含具体数字。": ledger_only_replacement,
        "所有精确数值必须来自运行时Exact-Value Ledger，本协议不包含具体数值。": ledger_only_replacement,
        "所有精确数值必须来自运行时Exact-Value Ledger，本协议不包含任何具体数字。": ledger_only_replacement,
        "所有精确数值必须来自运行时Exact-Value Ledger，本协议不包含任何具体数值。": ledger_only_replacement,
        "所有精确数值必须来自运行时Exact-Value Ledger，本协议不提供最终数字。": ledger_only_replacement,
        "所有精确数值必须来自运行时Exact-Value Ledger，本协议不提供最终数值。": ledger_only_replacement,
    }
    if text in replacements:
        return replacements[text]
    if re.search(
        r"精确数值.*(?:运行时)?\s*Exact-Value Ledger.*(?:本|当前)?协议不(?:包含|含有|提供)[^。；,，]*(?:具体|任何|最终)?(?:数字|数值)",
        text,
        flags=re.I,
    ):
        return ledger_only_replacement
    return text


def _is_broad_task(contract: dict[str, Any]) -> bool:
    task_type = str(contract.get("task_type") or "")
    focus_count = len(contract.get("focus_tickers") or [])
    years_count = len(contract.get("years") or [])
    return task_type in {"ai_industry_financial_trend", "open_analysis"} or focus_count >= 5 or years_count >= 3


def _scope_mode(contract: dict[str, Any], scope_tickers: list[str], focus_tickers: list[str]) -> str:
    explicit = str(
        contract.get("scope_mode")
        or (contract.get("scope") if isinstance(contract.get("scope"), dict) else {}).get("scope_mode")
        or ""
    ).strip()
    if explicit in SCOPE_MODES:
        if explicit == "full_universe" and scope_tickers and focus_tickers and set(focus_tickers) < set(scope_tickers):
            return "sector_representative"
        return explicit
    if scope_tickers and focus_tickers and set(focus_tickers) < set(scope_tickers):
        return "sector_representative"
    task_type = str(contract.get("task_type") or "")
    if task_type in {"ai_industry_financial_trend", "open_analysis"} or len(scope_tickers) >= 5:
        return "full_universe"
    return "focused_peer"


def _clamp_tickers(value: Any, allowed: list[str]) -> list[str]:
    allowed_set = {ticker.upper() for ticker in allowed}
    out = []
    for item in value or []:
        ticker = str(item or "").upper().strip()
        if ticker in allowed_set and ticker not in out:
            out.append(ticker)
    return out


def _clamp_years(value: Any, allowed: list[int]) -> list[int]:
    allowed_set = {int(year) for year in allowed}
    out = []
    for item in value or []:
        year = _int_or_none(item)
        if year in allowed_set and year not in out:
            out.append(int(year))
    return out


def _clamp_form_types(value: Any, allowed: list[str]) -> list[str]:
    allowed_set = {str(item).upper() for item in allowed}
    out = []
    for item in value or []:
        form_type = str(item or "").upper().strip()
        if form_type in allowed_set and form_type not in out:
            out.append(form_type)
    return out


def _clamp_source_tiers(value: Any, allowed: list[str]) -> list[str]:
    allowed_set = {str(item) for item in allowed}
    out = []
    for item in value or []:
        source_tier = str(item or "").strip()
        if source_tier in allowed_set and source_tier not in out:
            out.append(source_tier)
    return out


def _string_list(value: Any, *, max_items: int, max_chars: int = 80) -> list[str]:
    out = []
    for item in value or []:
        text = _short_text(item, max_chars)
        if text and text not in out:
            out.append(text)
        if len(out) >= max_items:
            break
    return out


def _unique_upper(value: list[str]) -> list[str]:
    out = []
    for item in value:
        text = str(item or "").upper().strip()
        if text and text not in out:
            out.append(text)
    return out


def _unique_ints(value: list[int]) -> list[int]:
    out = []
    for item in value:
        number = _int_or_none(item)
        if number is not None and number not in out:
            out.append(number)
    return sorted(out)


def _planner_confidence(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"high", "medium", "low"} else "medium"


def _short_text(value: Any, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:max_chars]


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _contains_any(text: str, probes: tuple[str, ...]) -> bool:
    lowered = str(text or "").lower()
    return any(str(probe).lower() in lowered for probe in probes)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value))
    except Exception:
        return None
