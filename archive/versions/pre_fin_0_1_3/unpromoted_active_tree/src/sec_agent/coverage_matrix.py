from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any


SCHEMA_VERSION = "sec_agent_evidence_coverage_matrix_v0.1"
MARKET_SOURCE_TIER = "market_snapshot"
INDUSTRY_SOURCE_TIER = "industry_snapshot"
MARKET_TASK_TERMS = (
    "market",
    "price",
    "stock",
    "return",
    "valuation",
    "multiple",
    "priced in",
    "drawdown",
    "reaction",
    "relative",
    "股价",
    "市场",
    "估值",
    "收益",
    "回撤",
    "反应",
    "相对",
)
INDUSTRY_TASK_TERMS = (
    "industry",
    "sector",
    "macro",
    "rate",
    "credit cycle",
    "commodity",
    "oil",
    "gas",
    "consumer demand",
    "housing",
    "regulatory",
    "manufacturing",
    "orders",
    "行业",
    "板块",
    "宏观",
    "利率",
    "信用周期",
    "大宗商品",
    "油价",
    "天然气",
    "消费需求",
    "住房",
    "监管",
    "制造业",
    "订单",
)

METRIC_FAMILY_ALIASES: dict[str, tuple[str, ...]] = {
    "advertising_revenue": ("advertising revenue", "ads revenue", "广告收入"),
    "arr_or_recurring_proxy": ("arr", "annual recurring", "recurring revenue", "经常性收入"),
    "asset_quality": ("asset quality", "nonperforming", "charge-off", "credit quality", "资产质量", "不良"),
    "allowance_for_credit_losses": ("allowance for credit losses", "allowance for loan losses", "allowance for expected credit losses", "信用损失准备"),
    "capex": ("capital expenditure", "capex", "property and equipment", "资本开支"),
    "capital_expenditure_proxy": ("capital expenditure", "capex", "property and equipment", "资本开支"),
    "capital_ratio": ("cet1", "common equity tier 1", "tier 1 capital", "capital ratio", "资本充足率"),
    "cloud_revenue": ("cloud revenue", "aws", "azure", "google cloud", "cloud services", "云收入", "云业务"),
    "credit_quality": ("credit quality", "asset quality", "credit risk", "credit losses", "信用质量", "信用风险"),
    "credit_risk": ("credit risk", "credit losses", "allowance for credit losses", "net charge-offs", "信用风险"),
    "customer_concentration": ("customer concentration", "major customer", "客户集中"),
    "data_center_revenue": ("data center", "datacenter", "compute & networking", "数据中心"),
    "deferred_revenue": ("deferred revenue", "unearned revenue", "递延收入"),
    "deposits": ("deposits", "average deposits", "total deposits", "存款"),
    "free_cash_flow_proxy": ("free cash flow", "operating cash flow", "capital expenditure", "自由现金流"),
    "gross_margin": ("gross margin", "毛利率", "gross profit"),
    "infrastructure_software": ("infrastructure software", "基础设施软件"),
    "net_interest_income": ("net interest income", "净利息收入"),
    "net_interest_margin": ("net interest margin", "nim", "净息差", "净利息收益率"),
    "net_charge_offs": ("net charge-off", "net charge offs", "charge-offs", "charge offs", "净核销"),
    "nonperforming_assets": ("nonperforming assets", "non-performing assets", "nonaccrual assets", "不良资产"),
    "nonperforming_loans": ("nonperforming loans", "non-performing loans", "nonaccrual loans", "不良贷款"),
    "operating_cash_flow": ("operating cash flow", "cash provided by operating", "经营现金流"),
    "operating_income": ("operating income", "income from operations", "营业利润", "经营利润"),
    "pipeline": ("pipeline", "clinical", "trial", "regulatory", "管线", "临床"),
    "product_revenue": ("product revenue", "产品收入"),
    "provision_for_credit_losses": (
        "provision for credit losses",
        "credit loss provision",
        "provision for loan losses",
        "provision for loan lease and other losses",
        "信用损失准备金",
        "信贷损失拨备",
    ),
    "research_and_development": ("research and development", "r&d", "研发", "研发支出"),
    "revenue": ("revenue", "net sales", "sales and revenues", "收入"),
    "loans": ("loans", "average loans", "total loans", "loan portfolio", "贷款"),
    "rpo": ("remaining performance obligation", "rpo", "剩余履约义务"),
    "segment_growth": ("segment", "growth", "分部", "增长"),
    "semiconductor_solutions": ("semiconductor solutions", "半导体解决方案"),
    "semiconductor_systems": ("semiconductor systems", "半导体系统"),
    "services_revenue": ("services revenue", "服务收入"),
    "subscription_revenue": ("subscription revenue", "订阅收入"),
    "total_assets": ("total assets", "assets", "总资产"),
    "total_revenue": ("total revenue", "revenue", "net sales", "总收入"),
}

PEER_TASK_TERMS = (
    "competitor",
    "competition",
    "competitive",
    "peer",
    "compare",
    "comparison",
    "vs",
    "versus",
    "竞争",
    "竞品",
    "同行",
    "对手",
    "对比",
    "比较",
)


def build_coverage_matrix(
    *,
    case: dict[str, Any] | None,
    query_contract: dict[str, Any],
    context_rows: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
    run_id: str = "",
) -> dict[str, Any]:
    case = case or {}
    tasks = [task for task in query_contract.get("decomposed_tasks") or [] if isinstance(task, dict)]
    if not tasks:
        tasks = [_fallback_task(query_contract)]

    focus_tickers = _unique_upper(query_contract.get("focus_tickers") or (query_contract.get("scope") or {}).get("focus_tickers") or [])
    search_tickers = _unique_upper(
        query_contract.get("search_scope_tickers") or (query_contract.get("scope") or {}).get("universe_tickers") or focus_tickers
    )
    years = _unique_ints(query_contract.get("years") or (query_contract.get("scope") or {}).get("years") or case.get("years") or [])
    filing_types = _unique_form_types(query_contract.get("filing_types") or (query_contract.get("scope") or {}).get("filing_types") or [])
    source_tiers = _unique_strings(query_contract.get("source_tiers") or (query_contract.get("scope") or {}).get("source_tiers") or [])
    source_coverage_gaps = [
        gap for gap in query_contract.get("source_coverage_gaps") or [] if isinstance(gap, dict)
    ]
    market_contract = query_contract.get("market_snapshot") if isinstance(query_contract.get("market_snapshot"), dict) else {}
    industry_contract = query_contract.get("industry_snapshot") if isinstance(query_contract.get("industry_snapshot"), dict) else {}
    market_summary = _market_coverage_summary(market_contract, context_rows)
    industry_summary = _industry_coverage_summary(industry_contract, context_rows)
    matrix_rows = [
        _task_coverage_row(
            task,
            idx,
            query_contract,
            focus_tickers,
            search_tickers,
            years,
            filing_types,
            source_tiers,
            market_contract,
            industry_contract,
            context_rows,
            ledger_rows,
        )
        for idx, task in enumerate(tasks, start=1)
    ]

    support_counts = Counter(str(row.get("support_level") or "unknown") for row in matrix_rows)
    primary_rows = [row for row in matrix_rows if row.get("priority") == "primary"]
    primary_complete = all(row.get("support_level") in {"strong", "medium"} for row in primary_rows) if primary_rows else False
    answer_status = "complete" if primary_complete else ("partial" if any(row.get("support_level") != "insufficient" for row in primary_rows or matrix_rows) else "insufficient")
    covered_metric_families = sorted({family for row in matrix_rows for family in row.get("covered_metric_families") or []})
    missing_metric_families = sorted({family for row in matrix_rows for family in row.get("missing_metric_families") or []})
    covered_focus_tickers = sorted({ticker for row in matrix_rows for ticker in row.get("covered_focus_tickers") or []})
    covered_filing_types = sorted({form for row in matrix_rows for form in row.get("covered_filing_types") or []})
    covered_source_tiers = sorted({tier for row in matrix_rows for tier in row.get("covered_source_tiers") or []})
    missing_filing_types = sorted({form for row in matrix_rows for form in row.get("missing_filing_types") or []})
    missing_source_tiers = sorted({tier for row in matrix_rows for tier in row.get("missing_source_tiers") or []})

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "case_id": case.get("case_id") or query_contract.get("case_id") or run_id,
        "run_id": run_id,
        "source": "query_contract_plus_retrieved_context_plus_runtime_ledger",
        "source_policy": query_contract.get("source_policy"),
        "filing_types": filing_types,
        "source_tiers": source_tiers,
        "task_type": query_contract.get("task_type"),
        "focus_tickers": focus_tickers,
        "search_scope_tickers": search_tickers,
        "years": years,
        "tasks": matrix_rows,
        "source_coverage_gaps": source_coverage_gaps,
        "market_snapshot_coverage": market_summary,
        "industry_snapshot_coverage": industry_summary,
        "summary": {
            "task_count": len(matrix_rows),
            "primary_task_count": len(primary_rows),
            "support_counts": dict(sorted(support_counts.items())),
            "primary_task_support_complete": primary_complete,
            "coverage_complete": primary_complete and not any(row.get("support_level") == "insufficient" for row in matrix_rows),
            "answer_status": answer_status,
            "covered_focus_tickers": covered_focus_tickers,
            "covered_metric_families": covered_metric_families,
            "missing_metric_families": missing_metric_families,
            "covered_filing_types": covered_filing_types,
            "covered_source_tiers": covered_source_tiers,
            "missing_filing_types": missing_filing_types,
            "missing_source_tiers": missing_source_tiers,
            "market_snapshot_requested": market_summary.get("market_snapshot_requested"),
            "market_snapshot_support_complete": market_summary.get("market_snapshot_support_complete"),
            "required_market_fields": market_summary.get("required_market_fields") or [],
            "covered_market_fields": market_summary.get("covered_market_fields") or [],
            "missing_market_fields": market_summary.get("missing_market_fields") or [],
            "market_snapshot_as_of_dates": market_summary.get("market_snapshot_as_of_dates") or [],
            "market_snapshot_ids": market_summary.get("market_snapshot_ids") or [],
            "market_context_row_count": market_summary.get("market_context_row_count"),
            "industry_snapshot_requested": industry_summary.get("industry_snapshot_requested"),
            "industry_snapshot_support_complete": industry_summary.get("industry_snapshot_support_complete"),
            "required_industry_source_families": industry_summary.get("required_industry_source_families") or [],
            "covered_industry_source_families": industry_summary.get("covered_industry_source_families") or [],
            "missing_industry_source_families": industry_summary.get("missing_industry_source_families") or [],
            "industry_snapshot_as_of_dates": industry_summary.get("industry_snapshot_as_of_dates") or [],
            "industry_context_row_count": industry_summary.get("industry_context_row_count"),
            "source_coverage_gap_count": len(source_coverage_gaps),
            "ledger_row_count": len(ledger_rows),
            "context_row_count": len(context_rows),
        },
    }


def _task_coverage_row(
    task: dict[str, Any],
    idx: int,
    query_contract: dict[str, Any],
    focus_tickers: list[str],
    search_tickers: list[str],
    years: list[int],
    filing_types: list[str],
    source_tiers: list[str],
    market_contract: dict[str, Any],
    industry_contract: dict[str, Any],
    context_rows: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    task_id = str(task.get("task_id") or f"task_{idx}").strip() or f"task_{idx}"
    task_text = _task_text(task)
    priority = str(task.get("priority") or "supporting").strip().lower()
    if priority not in {"primary", "supporting", "caveat"}:
        priority = "supporting"

    required_metric_families = _unique_strings(task.get("required_metric_families") or query_contract.get("metric_families") or [])
    if not required_metric_families:
        required_metric_families = _unique_strings((query_contract.get("metric_families") or [])[:4])

    explicit_required_tickers = [ticker for ticker in _unique_upper(task.get("required_tickers") or []) if ticker in set(search_tickers)]
    explicit_peer_tickers = [
        ticker
        for ticker in _unique_upper(task.get("peer_tickers") or [])
        if ticker in set(search_tickers) and ticker not in set(explicit_required_tickers)
    ]
    mentioned_tickers = [ticker for ticker in search_tickers if _ticker_mentioned(task_text, ticker)]
    is_peer_task = _contains_any(task_text, PEER_TASK_TERMS)
    task_requires_market = _task_requires_market(task, market_contract)
    task_requires_industry = _task_requires_industry(task, industry_contract)
    if explicit_required_tickers:
        required_tickers = explicit_required_tickers
    elif mentioned_tickers:
        required_tickers = mentioned_tickers
    elif is_peer_task and focus_tickers:
        required_tickers = focus_tickers[:1]
    else:
        required_tickers = focus_tickers

    peer_tickers = explicit_peer_tickers
    if not peer_tickers and is_peer_task and len(focus_tickers) > 1:
        peer_tickers = [ticker for ticker in focus_tickers if ticker not in set(required_tickers)]
        if not peer_tickers and len(focus_tickers) > 1:
            peer_tickers = focus_tickers[1:]

    relevant_ledger = [
        row
        for row in ledger_rows
        if _row_matches_task(
            row,
            required_tickers,
            peer_tickers,
            years,
            filing_types,
            source_tiers,
            task_requires_market,
            task_requires_industry,
            required_metric_families,
        )
    ]
    relevant_context = [
        row
        for row in context_rows
        if _context_matches_task(
            row,
            required_tickers,
            peer_tickers,
            years,
            filing_types,
            source_tiers,
            task_requires_market,
            task_requires_industry,
            required_metric_families,
            task_text,
        )
    ]

    ledger_tickers = _row_tickers(relevant_ledger)
    context_tickers = _row_tickers(relevant_context)
    covered_tickers = sorted((ledger_tickers | context_tickers) & set(required_tickers or focus_tickers))
    covered_peer_tickers = sorted((ledger_tickers | context_tickers) & set(peer_tickers))
    covered_focus_tickers = sorted((ledger_tickers | context_tickers) & set(focus_tickers))
    ledger_years = _row_years(relevant_ledger)
    context_years = _row_years(relevant_context)
    covered_years = sorted(ledger_years | context_years)
    actual_metric_families = _ledger_metric_families(relevant_ledger) | _context_metric_families(relevant_context, required_metric_families)
    covered_metric_families = sorted(actual_metric_families | _matched_required_families(actual_metric_families, required_metric_families))
    covered_filing_types = sorted(_row_filing_types(relevant_ledger) | _row_filing_types(relevant_context))
    covered_source_tiers = sorted(_row_source_tiers(relevant_ledger) | _row_source_tiers(relevant_context))
    required_market_fields = _market_contract_fields(market_contract) if task_requires_market else []
    required_market_tools = _market_contract_tools(market_contract) if task_requires_market else []
    covered_market_fields = sorted(_market_fields_from_rows(relevant_context))
    covered_market_tools = _covered_market_tools(required_market_tools, covered_market_fields)
    required_industry_families = _industry_contract_source_families(industry_contract) if task_requires_industry else []
    covered_industry_families = sorted(_industry_source_families_from_rows(relevant_context))

    missing_tickers = sorted(set(required_tickers) - set(covered_tickers))
    missing_peer_tickers = sorted(set(peer_tickers) - set(covered_peer_tickers))
    missing_metric_families = sorted(
        required
        for required in set(required_metric_families)
        if not _family_matches_required(required, list(actual_metric_families))
    )
    missing_years = sorted(set(years) - set(covered_years))
    missing_filing_types = sorted(set(filing_types) - set(covered_filing_types))
    required_source_tiers = []
    for tier in source_tiers:
        if tier == MARKET_SOURCE_TIER and not task_requires_market:
            continue
        if tier == INDUSTRY_SOURCE_TIER and not task_requires_industry:
            continue
        required_source_tiers.append(tier)
    missing_source_tiers = sorted(set(required_source_tiers) - set(covered_source_tiers))
    missing_market_fields = sorted(set(required_market_fields) - set(covered_market_fields))
    missing_market_tools = sorted(set(required_market_tools) - set(covered_market_tools))
    missing_industry_families = sorted(set(required_industry_families) - set(covered_industry_families))
    support_level = _support_level(
        priority=priority,
        required_tickers=required_tickers,
        peer_tickers=peer_tickers,
        required_metric_families=required_metric_families,
        covered_tickers=covered_tickers,
        covered_peer_tickers=covered_peer_tickers,
        covered_metric_families=covered_metric_families,
        required_market_fields=required_market_fields,
        covered_market_fields=covered_market_fields,
        required_industry_families=required_industry_families,
        covered_industry_families=covered_industry_families,
        covered_years=covered_years,
        ledger_row_count=len(relevant_ledger),
        context_row_count=len(relevant_context),
    )

    return {
        "task_id": task_id,
        "question_zh": str(task.get("question_zh") or task.get("question") or "").strip(),
        "priority": priority,
        "required_tickers": required_tickers,
        "peer_tickers": peer_tickers,
        "required_metric_families": required_metric_families,
        "covered_tickers": covered_tickers,
        "covered_peer_tickers": covered_peer_tickers,
        "covered_focus_tickers": covered_focus_tickers,
        "covered_years": covered_years,
        "covered_metric_families": covered_metric_families,
        "covered_filing_types": covered_filing_types,
        "covered_source_tiers": covered_source_tiers,
        "required_market_fields": required_market_fields,
        "covered_market_fields": covered_market_fields,
        "missing_market_fields": missing_market_fields,
        "required_market_tools": required_market_tools,
        "covered_market_tools": covered_market_tools,
        "missing_market_tools": missing_market_tools,
        "required_industry_source_families": required_industry_families,
        "covered_industry_source_families": covered_industry_families,
        "missing_industry_source_families": missing_industry_families,
        "industry_snapshot_as_of_dates": sorted(_industry_as_of_dates(relevant_context)),
        "market_snapshot_ids": sorted(_market_snapshot_ids(relevant_context)),
        "market_snapshot_as_of_dates": sorted(_market_as_of_dates(relevant_context)),
        "missing_tickers": missing_tickers,
        "missing_peer_tickers": missing_peer_tickers,
        "missing_metric_families": missing_metric_families,
        "missing_years": missing_years,
        "missing_filing_types": missing_filing_types,
        "missing_source_tiers": missing_source_tiers,
        "context_row_count": len(relevant_context),
        "ledger_row_count": len(relevant_ledger),
        "support_level": support_level,
        "allowed_answer_strength": _allowed_answer_strength(support_level),
        "must_caveat": _must_caveats(
            support_level=support_level,
            missing_tickers=missing_tickers,
            missing_peer_tickers=missing_peer_tickers,
            missing_metric_families=missing_metric_families,
            missing_years=missing_years,
            missing_filing_types=missing_filing_types,
            missing_source_tiers=missing_source_tiers,
            missing_market_fields=missing_market_fields,
            missing_market_tools=missing_market_tools,
            missing_industry_source_families=missing_industry_families,
        ),
        "sample_metric_ids": _unique_strings([row.get("metric_id") for row in relevant_ledger])[:8],
        "sample_evidence_ids": _unique_strings(
            [row.get("source_evidence_id") or row.get("evidence_id") for row in relevant_ledger]
            + [row.get("evidence_id") or row.get("source_evidence_id") for row in relevant_context]
        )[:10],
        "sample_market_field_refs": _market_field_refs_from_rows(relevant_context)[:10],
        "sample_industry_evidence_ids": _industry_evidence_ids(relevant_context)[:10],
    }


def _support_level(
    *,
    priority: str,
    required_tickers: list[str],
    peer_tickers: list[str],
    required_metric_families: list[str],
    covered_tickers: list[str],
    covered_peer_tickers: list[str],
    covered_metric_families: list[str],
    required_market_fields: list[str],
    covered_market_fields: list[str],
    required_industry_families: list[str],
    covered_industry_families: list[str],
    covered_years: list[int],
    ledger_row_count: int,
    context_row_count: int,
) -> str:
    if ledger_row_count == 0 and context_row_count == 0:
        return "insufficient"
    market_ratio = _coverage_ratio(covered_market_fields, required_market_fields)
    if required_market_fields and market_ratio == 0:
        return "partial"
    industry_ratio = _coverage_ratio(covered_industry_families, required_industry_families)
    if required_industry_families and industry_ratio == 0:
        return "partial"
    if priority == "primary" and required_metric_families and ledger_row_count == 0:
        return "partial"
    ticker_ratio = _coverage_ratio(covered_tickers, required_tickers)
    family_ratio = _coverage_ratio(covered_metric_families, required_metric_families)
    peer_ok = True
    if peer_tickers:
        peer_ok = len(covered_peer_tickers) >= min(2, len(peer_tickers))
    two_years = len(set(covered_years)) >= 2
    one_year = bool(covered_years)
    market_ok = not required_market_fields or market_ratio >= 0.6
    industry_ok = not required_industry_families or industry_ratio >= 0.5

    if priority == "primary" and ticker_ratio >= 0.8 and family_ratio >= 0.7 and two_years and peer_ok and market_ok and industry_ok:
        return "strong"
    if ticker_ratio > 0 and family_ratio > 0 and one_year and (not peer_tickers or covered_peer_tickers) and market_ok and industry_ok:
        return "medium"
    return "partial"


def _allowed_answer_strength(support_level: str) -> str:
    if support_level == "strong":
        return "strong"
    if support_level == "medium":
        return "medium"
    if support_level == "partial":
        return "weak_or_medium_with_caveat"
    return "insufficient_or_refusal"


def _must_caveats(
    *,
    support_level: str,
    missing_tickers: list[str],
    missing_peer_tickers: list[str],
    missing_metric_families: list[str],
    missing_years: list[int],
    missing_filing_types: list[str],
    missing_source_tiers: list[str],
    missing_market_fields: list[str],
    missing_market_tools: list[str],
    missing_industry_source_families: list[str],
) -> list[str]:
    caveats = []
    if support_level in {"partial", "insufficient"}:
        caveats.append("This task is not fully covered by the current retrieved SEC evidence.")
    if missing_tickers:
        caveats.append(f"Missing required ticker coverage: {', '.join(missing_tickers)}.")
    if missing_peer_tickers:
        caveats.append(f"Peer coverage is partial; missing peers: {', '.join(missing_peer_tickers)}.")
    if missing_metric_families:
        caveats.append(f"Missing required metric-family coverage: {', '.join(missing_metric_families)}.")
    if missing_years:
        caveats.append(f"Missing requested fiscal-year coverage: {', '.join(str(year) for year in missing_years)}.")
    if missing_filing_types:
        caveats.append(f"Missing requested filing-type coverage: {', '.join(missing_filing_types)}.")
    if missing_source_tiers:
        caveats.append(f"Missing requested source-tier coverage: {', '.join(missing_source_tiers)}.")
    if missing_market_fields:
        caveats.append(f"Missing requested market snapshot fields: {', '.join(missing_market_fields)}.")
    if missing_market_tools:
        caveats.append(f"Missing requested market analysis tools: {', '.join(missing_market_tools)}.")
    if missing_industry_source_families:
        caveats.append(f"Missing requested industry source-family coverage: {', '.join(missing_industry_source_families)}.")
    return caveats[:6]


def _row_matches_task(
    row: dict[str, Any],
    required_tickers: list[str],
    peer_tickers: list[str],
    years: list[int],
    filing_types: list[str],
    source_tiers: list[str],
    task_requires_market: bool,
    task_requires_industry: bool,
    required_metric_families: list[str],
) -> bool:
    ticker = str(row.get("ticker") or "").upper()
    if required_tickers or peer_tickers:
        if ticker not in set(required_tickers) | set(peer_tickers):
            return False
    is_market = _is_market_row(row)
    year = _int_or_none(row.get("fiscal_year"))
    if years and not is_market and year not in set(years):
        return False
    if not _row_matches_source_scope(row, filing_types, source_tiers):
        return False
    if is_market:
        return task_requires_market
    if _is_industry_row(row):
        return task_requires_industry
    family = str(row.get("metric_family") or "")
    return not required_metric_families or _family_matches_required(family, required_metric_families)


def _context_matches_task(
    row: dict[str, Any],
    required_tickers: list[str],
    peer_tickers: list[str],
    years: list[int],
    filing_types: list[str],
    source_tiers: list[str],
    task_requires_market: bool,
    task_requires_industry: bool,
    required_metric_families: list[str],
    task_text: str,
) -> bool:
    ticker = str(row.get("ticker") or "").upper()
    is_industry = _is_industry_row(row)
    if is_industry:
        if not (task_requires_industry or _task_text_has_industry_intent(task_text)):
            return False
        return _row_matches_source_scope(row, [], source_tiers)
    if required_tickers or peer_tickers:
        if ticker not in set(required_tickers) | set(peer_tickers):
            return False
    is_market = _is_market_row(row)
    year = _int_or_none(row.get("fiscal_year"))
    if years and not is_market and year not in set(years):
        return False
    if not _row_matches_source_scope(row, filing_types, source_tiers):
        return False
    if is_market:
        return task_requires_market or _task_text_has_market_intent(task_text)
    text = _row_text(row)
    if not required_metric_families:
        return True
    if _contains_family_alias(text, required_metric_families):
        return True
    if _contains_family_alias(task_text + "\n" + text, required_metric_families):
        return True
    return False


def _context_metric_families(rows: list[dict[str, Any]], required_metric_families: list[str]) -> set[str]:
    out = set()
    for row in rows:
        text = _row_text(row)
        for family in required_metric_families:
            if _contains_family_alias(text, [family]):
                out.add(family)
    return out


def _ledger_metric_families(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("metric_family") or "") for row in rows if row.get("metric_family")}


def _matched_required_families(actual_families: set[str], required_metric_families: list[str]) -> set[str]:
    matched = set()
    for required in required_metric_families:
        if _family_matches_required(required, list(actual_families)):
            matched.add(required)
    return matched


def _family_matches_required(family: str, required_metric_families: list[str]) -> bool:
    family_set = _family_equivalence_set(family)
    for required in required_metric_families:
        if family_set & _family_equivalence_set(required):
            return True
    return False


def _family_equivalence_set(family: str) -> set[str]:
    value = str(family or "")
    groups = (
        {"capex", "capital_expenditure_proxy", "ppe_purchases"},
        {"cash_flow", "operating_cash_flow", "free_cash_flow_proxy"},
        {"arr_or_recurring_proxy", "rpo", "deferred_revenue", "subscription_revenue"},
    )
    for group in groups:
        if value in group:
            return set(group)
    return {value}


def _contains_family_alias(text: str, families: list[str]) -> bool:
    lowered = str(text or "").lower()
    for family in families:
        probes = []
        for equivalent in sorted(_family_equivalence_set(family)):
            probes.extend(METRIC_FAMILY_ALIASES.get(equivalent, (equivalent.replace("_", " "),)))
        if any(str(probe).lower() in lowered for probe in probes):
            return True
    return False


def _task_text(task: dict[str, Any]) -> str:
    return " ".join(str(task.get(key) or "") for key in ("task_id", "question_zh", "question", "description"))


def _fallback_task(query_contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": "general_sec_evidence_coverage",
        "question_zh": "Evaluate whether retrieved SEC evidence covers the user query.",
        "priority": "primary",
        "required_metric_families": query_contract.get("metric_families") or [],
    }


def _ticker_mentioned(text: str, ticker: str) -> bool:
    return bool(re.search(rf"(?<![A-Z0-9]){re.escape(ticker)}(?![A-Z0-9])", str(text or ""), re.I))


def _contains_any(text: str, probes: tuple[str, ...]) -> bool:
    lowered = str(text or "").lower()
    return any(probe.lower() in lowered for probe in probes)


def _row_tickers(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}


def _row_years(rows: list[dict[str, Any]]) -> set[int]:
    return {year for row in rows if (year := _int_or_none(row.get("fiscal_year"))) is not None}


def _row_filing_types(rows: list[dict[str, Any]]) -> set[str]:
    return {form for row in rows if (form := _row_filing_type(row))}


def _row_source_tiers(rows: list[dict[str, Any]]) -> set[str]:
    return {_row_source_tier(row) or "primary_sec_filing" for row in rows}


def _row_matches_source_scope(row: dict[str, Any], filing_types: list[str], source_tiers: list[str]) -> bool:
    if _is_market_row(row):
        return not source_tiers or MARKET_SOURCE_TIER in set(source_tiers)
    if _is_industry_row(row):
        return not source_tiers or INDUSTRY_SOURCE_TIER in set(source_tiers)
    if filing_types:
        form_type = _row_filing_type(row)
        if not form_type or form_type not in set(filing_types):
            return False
    if source_tiers:
        source_tier = _row_source_tier(row) or "primary_sec_filing"
        if source_tier not in set(source_tiers):
            return False
    return True


def _row_filing_type(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    for key in ("form_type", "source_type", "filing_type"):
        value = _normalize_form_type(row.get(key) or metadata.get(key))
        if value:
            return value
    source_id = " ".join(
        str(row.get(key) or "")
        for key in ("source_evidence_id", "evidence_id", "object_id")
    )
    match = re.search(r"_(10K|10Q)_", source_id, flags=re.I)
    if match:
        return _normalize_form_type(match.group(1))
    return ""


def _row_source_tier(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    source_tier = str(row.get("source_tier") or metadata.get("source_tier") or "").strip()
    source_type = str(row.get("source_type") or row.get("source_kind") or metadata.get("source_type") or "").strip()
    if not source_tier and source_type == MARKET_SOURCE_TIER:
        return MARKET_SOURCE_TIER
    if not source_tier and source_type == INDUSTRY_SOURCE_TIER:
        return INDUSTRY_SOURCE_TIER
    return source_tier


def _row_text(row: dict[str, Any]) -> str:
    return "\n".join(
        str(row.get(key) or "")
        for key in ("text", "preview", "section", "subsection", "metric_name", "row_label", "table_title", "source_text", "source_boundary")
    )


def _is_market_row(row: dict[str, Any]) -> bool:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    values = {
        str(row.get("source_tier") or "").strip(),
        str(row.get("source_type") or "").strip(),
        str(row.get("source_kind") or "").strip(),
        str(metadata.get("source_tier") or "").strip(),
        str(metadata.get("source_type") or "").strip(),
    }
    if MARKET_SOURCE_TIER in values:
        return True
    evidence_id = " ".join(str(row.get(key) or "") for key in ("evidence_id", "source_evidence_id", "object_id"))
    return "MARKET_SNAPSHOT::" in evidence_id or evidence_id.startswith("MARKET::")


def _is_industry_row(row: dict[str, Any]) -> bool:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    values = {
        str(row.get("source_tier") or "").strip(),
        str(row.get("source_type") or "").strip(),
        str(row.get("source_kind") or "").strip(),
        str(metadata.get("source_tier") or "").strip(),
        str(metadata.get("source_type") or "").strip(),
    }
    if INDUSTRY_SOURCE_TIER in values:
        return True
    evidence_id = " ".join(str(row.get(key) or "") for key in ("evidence_id", "source_evidence_id", "object_id"))
    return "INDUSTRY::" in evidence_id


def _task_requires_market(task: dict[str, Any], market_contract: dict[str, Any]) -> bool:
    if not market_contract:
        return False
    if task.get("required_market_fields") or task.get("market_fields"):
        return True
    return _task_text_has_market_intent(_task_text(task))


def _task_requires_industry(task: dict[str, Any], industry_contract: dict[str, Any]) -> bool:
    if not industry_contract:
        return False
    if task.get("required_industry_source_families") or task.get("source_families"):
        return True
    return _task_text_has_industry_intent(_task_text(task))


def _task_text_has_market_intent(text: str) -> bool:
    return _contains_any(text, MARKET_TASK_TERMS)


def _task_text_has_industry_intent(text: str) -> bool:
    return _contains_any(text, INDUSTRY_TASK_TERMS)


def _market_contract_fields(market_contract: dict[str, Any]) -> list[str]:
    return _unique_strings(market_contract.get("fields") or market_contract.get("market_fields") or [])


def _market_contract_tools(market_contract: dict[str, Any]) -> list[str]:
    return _unique_strings(market_contract.get("analysis_tools") or market_contract.get("market_analysis_tools") or [])


def _market_coverage_summary(market_contract: dict[str, Any], context_rows: list[dict[str, Any]]) -> dict[str, Any]:
    requested = bool(market_contract)
    market_rows = [row for row in context_rows if isinstance(row, dict) and _is_market_row(row)]
    required_fields = _market_contract_fields(market_contract)
    required_tools = _market_contract_tools(market_contract)
    covered_fields = sorted(_market_fields_from_rows(market_rows))
    covered_tools = _covered_market_tools(required_tools, covered_fields)
    return {
        "market_snapshot_requested": requested,
        "market_snapshot_support_complete": (not requested) or (bool(market_rows) and not (set(required_fields) - set(covered_fields))),
        "required_market_fields": required_fields,
        "covered_market_fields": covered_fields,
        "missing_market_fields": sorted(set(required_fields) - set(covered_fields)),
        "required_market_tools": required_tools,
        "covered_market_tools": covered_tools,
        "missing_market_tools": sorted(set(required_tools) - set(covered_tools)),
        "market_snapshot_ids": sorted(_market_snapshot_ids(market_rows)),
        "market_snapshot_as_of_dates": sorted(_market_as_of_dates(market_rows)),
        "market_context_row_count": len(market_rows),
        "sample_evidence_ids": _unique_strings(
            [row.get("evidence_id") or row.get("object_id") or row.get("source_evidence_id") for row in market_rows]
        )[:10],
        "sample_market_field_refs": _market_field_refs_from_rows(market_rows)[:20],
    }


def _industry_coverage_summary(industry_contract: dict[str, Any], context_rows: list[dict[str, Any]]) -> dict[str, Any]:
    requested = bool(industry_contract)
    industry_rows = [row for row in context_rows if isinstance(row, dict) and _is_industry_row(row)]
    required_families = _industry_contract_source_families(industry_contract)
    covered_families = sorted(_industry_source_families_from_rows(industry_rows))
    return {
        "industry_snapshot_requested": requested,
        "industry_snapshot_support_complete": (not requested)
        or (bool(industry_rows) and not (set(required_families) - set(covered_families))),
        "required_industry_source_families": required_families,
        "covered_industry_source_families": covered_families,
        "missing_industry_source_families": sorted(set(required_families) - set(covered_families)),
        "industry_snapshot_as_of_dates": sorted(_industry_as_of_dates(industry_rows)),
        "industry_context_row_count": len(industry_rows),
        "sample_evidence_ids": _industry_evidence_ids(industry_rows)[:10],
    }


def _industry_contract_source_families(industry_contract: dict[str, Any]) -> list[str]:
    return _unique_strings(
        industry_contract.get("source_families")
        or industry_contract.get("required_source_families")
        or industry_contract.get("industry_source_families")
        or []
    )


def _industry_source_families_from_rows(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("source_family") or "") for row in rows if row.get("source_family")}


def _industry_as_of_dates(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("as_of_date") or "") for row in rows if row.get("as_of_date")}


def _industry_evidence_ids(rows: list[dict[str, Any]]) -> list[str]:
    return _unique_strings(
        [row.get("evidence_id") or row.get("object_id") or row.get("source_evidence_id") for row in rows]
    )


def _market_fields_from_rows(rows: list[dict[str, Any]]) -> set[str]:
    fields: set[str] = set()
    for row in rows:
        for ref in row.get("field_refs") or []:
            if isinstance(ref, dict) and ref.get("field_name"):
                fields.add(str(ref.get("field_name")))
        for group_name in ("market_reaction", "valuation_context", "event_window"):
            group = row.get(group_name)
            if isinstance(group, dict):
                fields.update(str(key) for key, value in group.items() if value is not None)
        for field in ("close_price", "market_cap", "enterprise_value", "pe_ttm", "ev_sales_ttm", "ev_ebitda_ttm"):
            if row.get(field) is not None:
                fields.add(field)
    return fields


def _covered_market_tools(required_tools: list[str], covered_fields: list[str] | set[str]) -> list[str]:
    fields = set(covered_fields)
    tool_requirements = {
        "return_summary": {"return_1d", "return_5d", "return_1m", "return_3m", "return_ytd"},
        "peer_relative_return": {"relative_return_vs_benchmark_3m"},
        "valuation_peer_rank": {"peer_ev_sales_rank", "peer_ev_sales_bucket", "ev_sales_ttm"},
        "post_filing_event_return": {"return_1d", "return_3d", "return_5d", "return_10d"},
        "fundamental_market_divergence": {"return_3m", "relative_return_vs_benchmark_3m", "ev_sales_ttm"},
    }
    covered = []
    for tool in required_tools:
        needed = tool_requirements.get(tool)
        if not needed or fields & needed:
            covered.append(tool)
    return covered


def _market_snapshot_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("snapshot_id") or "") for row in rows if row.get("snapshot_id")}


def _market_as_of_dates(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("as_of_date") or "") for row in rows if row.get("as_of_date")}


def _market_field_refs_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for row in rows:
        for ref in row.get("field_refs") or []:
            if isinstance(ref, dict) and ref.get("field_ref"):
                refs.append(str(ref.get("field_ref")))
    return _unique_strings(refs)


def _coverage_ratio(covered: list[Any], required: list[Any]) -> float:
    if not required:
        return 1.0 if covered else 0.0
    return min(1.0, len(set(covered)) / len(set(required)))


def _unique_upper(values: Any) -> list[str]:
    out = []
    for item in values or []:
        value = str(item or "").upper().strip()
        if value and value not in out:
            out.append(value)
    return out


def _unique_form_types(values: Any) -> list[str]:
    out = []
    for item in values or []:
        value = _normalize_form_type(item)
        if value and value not in out:
            out.append(value)
    return out


def _normalize_form_type(value: Any) -> str:
    return str(value or "").upper().strip().replace("10K", "10-K").replace("10Q", "10-Q")


def _unique_strings(values: Any) -> list[str]:
    out = []
    for item in values or []:
        value = str(item or "").strip()
        if value and value not in out:
            out.append(value)
    return out


def _unique_ints(values: Any) -> list[int]:
    out = []
    for item in values or []:
        value = _int_or_none(item)
        if value is not None and value not in out:
            out.append(value)
    return out


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value))
    except Exception:
        return None
