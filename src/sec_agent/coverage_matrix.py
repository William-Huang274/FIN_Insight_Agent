from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any


SCHEMA_VERSION = "sec_agent_evidence_coverage_matrix_v0.1"

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
        if _row_matches_task(row, required_tickers, peer_tickers, years, filing_types, source_tiers, required_metric_families)
    ]
    relevant_context = [
        row
        for row in context_rows
        if _context_matches_task(row, required_tickers, peer_tickers, years, filing_types, source_tiers, required_metric_families, task_text)
    ]

    ledger_tickers = _row_tickers(relevant_ledger)
    context_tickers = _row_tickers(relevant_context)
    covered_tickers = sorted((ledger_tickers | context_tickers) & set(required_tickers or focus_tickers))
    covered_peer_tickers = sorted((ledger_tickers | context_tickers) & set(peer_tickers))
    covered_focus_tickers = sorted((ledger_tickers | context_tickers) & set(focus_tickers))
    ledger_years = _row_years(relevant_ledger)
    context_years = _row_years(relevant_context)
    covered_years = sorted(ledger_years | context_years)
    covered_metric_families = sorted(_ledger_metric_families(relevant_ledger) | _context_metric_families(relevant_context, required_metric_families))
    covered_filing_types = sorted(_row_filing_types(relevant_ledger) | _row_filing_types(relevant_context))
    covered_source_tiers = sorted(_row_source_tiers(relevant_ledger) | _row_source_tiers(relevant_context))

    missing_tickers = sorted(set(required_tickers) - set(covered_tickers))
    missing_peer_tickers = sorted(set(peer_tickers) - set(covered_peer_tickers))
    missing_metric_families = sorted(set(required_metric_families) - set(covered_metric_families))
    missing_years = sorted(set(years) - set(covered_years))
    missing_filing_types = sorted(set(filing_types) - set(covered_filing_types))
    missing_source_tiers = sorted(set(source_tiers) - set(covered_source_tiers))
    support_level = _support_level(
        priority=priority,
        required_tickers=required_tickers,
        peer_tickers=peer_tickers,
        required_metric_families=required_metric_families,
        covered_tickers=covered_tickers,
        covered_peer_tickers=covered_peer_tickers,
        covered_metric_families=covered_metric_families,
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
        ),
        "sample_metric_ids": _unique_strings([row.get("metric_id") for row in relevant_ledger])[:8],
        "sample_evidence_ids": _unique_strings(
            [row.get("source_evidence_id") or row.get("evidence_id") for row in relevant_ledger]
            + [row.get("evidence_id") or row.get("source_evidence_id") for row in relevant_context]
        )[:10],
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
    covered_years: list[int],
    ledger_row_count: int,
    context_row_count: int,
) -> str:
    if ledger_row_count == 0 and context_row_count == 0:
        return "insufficient"
    if priority == "primary" and required_metric_families and ledger_row_count == 0:
        return "partial"
    ticker_ratio = _coverage_ratio(covered_tickers, required_tickers)
    family_ratio = _coverage_ratio(covered_metric_families, required_metric_families)
    peer_ok = True
    if peer_tickers:
        peer_ok = len(covered_peer_tickers) >= min(2, len(peer_tickers))
    two_years = len(set(covered_years)) >= 2
    one_year = bool(covered_years)

    if priority == "primary" and ticker_ratio >= 0.8 and family_ratio >= 0.7 and two_years and peer_ok:
        return "strong"
    if ticker_ratio > 0 and family_ratio > 0 and one_year and (not peer_tickers or covered_peer_tickers):
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
    return caveats[:6]


def _row_matches_task(
    row: dict[str, Any],
    required_tickers: list[str],
    peer_tickers: list[str],
    years: list[int],
    filing_types: list[str],
    source_tiers: list[str],
    required_metric_families: list[str],
) -> bool:
    ticker = str(row.get("ticker") or "").upper()
    if required_tickers or peer_tickers:
        if ticker not in set(required_tickers) | set(peer_tickers):
            return False
    year = _int_or_none(row.get("fiscal_year"))
    if years and year not in set(years):
        return False
    if not _row_matches_source_scope(row, filing_types, source_tiers):
        return False
    family = str(row.get("metric_family") or "")
    return not required_metric_families or family in set(required_metric_families)


def _context_matches_task(
    row: dict[str, Any],
    required_tickers: list[str],
    peer_tickers: list[str],
    years: list[int],
    filing_types: list[str],
    source_tiers: list[str],
    required_metric_families: list[str],
    task_text: str,
) -> bool:
    ticker = str(row.get("ticker") or "").upper()
    if required_tickers or peer_tickers:
        if ticker not in set(required_tickers) | set(peer_tickers):
            return False
    year = _int_or_none(row.get("fiscal_year"))
    if years and year not in set(years):
        return False
    if not _row_matches_source_scope(row, filing_types, source_tiers):
        return False
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


def _contains_family_alias(text: str, families: list[str]) -> bool:
    lowered = str(text or "").lower()
    for family in families:
        probes = METRIC_FAMILY_ALIASES.get(family, (family.replace("_", " "),))
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
    return str(row.get("source_tier") or metadata.get("source_tier") or "").strip()


def _row_text(row: dict[str, Any]) -> str:
    return "\n".join(
        str(row.get(key) or "")
        for key in ("text", "preview", "section", "subsection", "metric_name", "row_label", "table_title", "source_text")
    )


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
