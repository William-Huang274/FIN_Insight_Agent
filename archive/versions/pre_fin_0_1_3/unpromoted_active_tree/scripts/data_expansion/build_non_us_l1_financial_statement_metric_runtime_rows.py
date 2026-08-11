from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "finsight_non_us_l1_financial_statement_metric_runtime_row_v0_1"
REJECTION_SCHEMA_VERSION = "finsight_non_us_l1_financial_statement_metric_runtime_rejection_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_non_us_l1_financial_statement_metric_runtime_summary_v0_1"

DEFAULT_COVERAGE_PATHS = [
    REPO_ROOT / "data" / "manifests" / "non_us_supply_chain_primary_disclosure_coverage_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_jp_company_ir_fallback_download_clean_r6_v0_1.jsonl",
]
DEFAULT_COMPANY_ASSIGNMENTS = REPO_ROOT / "data" / "manifests" / "vertical_source_lane_company_assignments_v0_1.jsonl"
DEFAULT_PRODUCT_KPI_ROWS = REPO_ROOT / "data" / "manifests" / "company_reported_product_operating_metric_runtime_rows_v0_1.jsonl"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/global_public_disclosures/r6_non_us_l1_manual_official")
DEFAULT_PROCESSED_DIR = Path("Z:/FIN_Insight_Agent_data/processed_private/public_sources/global_public_disclosures/r6_non_us_l1_manual_official")
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl"
DEFAULT_OUTPUT_REJECTIONS = REPO_ROOT / "data" / "manifests" / "non_us_l1_financial_statement_metric_runtime_rejections_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "non_us_l1_financial_statement_metric_runtime_summary_v0_1.json"

R6_TARGET_TICKERS = {
    "000660.KS",
    "005930.KS",
    "1211.HK",
    "2308.TW",
    "2317.TW",
    "2382.TW",
    "300750.SZ",
    "3231.TW",
    "373220.KS",
    "6146.T",
    "6723.T",
    "6752.T",
    "6857.T",
    "8035.T",
    "FDXF",
    "IFX.DE",
}

MANUAL_OFFICIAL_REPORTS = {
    "6146.T": [
        {
            "report_type": "financial_results",
            "fiscal_year": 2025,
            "document_url": "https://www.disco.co.jp/eg/ir/library/doc/fr/fr20260422.pdf",
            "source_title": "DISCO consolidated financial results FY2025",
        }
    ],
    "6723.T": [
        {
            "report_type": "official_financial_results_html",
            "fiscal_year": 2025,
            "document_url": "https://www.renesas.com/en/about/newsroom/renesas-reports-financial-results-year-ended-december-31-2025",
            "source_title": "Renesas reports financial results for the year ended December 31, 2025",
        }
    ],
    "6752.T": [
        {
            "report_type": "integrated_report",
            "fiscal_year": 2025,
            "document_url": "https://holdings.panasonic/content/dam/holdings/global/en/corporate/investors/pdf/annual/2025/PHD_IR2025_E.pdf",
            "source_title": "Panasonic Holdings Integrated Report 2025",
        }
    ],
}

METRIC_PATTERNS = {
    "revenue": [
        r"\bRevenue(?:\s+by\s+segment)?\b",
        r"\bNet sales\b",
        r"營業收入",
        r"营业收入",
        r"營業額",
        r"收益",
        r"매출액",
        r"売上高",
    ],
    "gross_profit": [
        r"\bGross profit\b",
        r"營業毛利",
        r"营业毛利",
        r"매출총이익",
        r"売上総利益",
    ],
    "operating_income": [
        r"\bOperating profit\b",
        r"\bOperating income\b",
        r"營業利益",
        r"营业利润",
        r"營業損益",
        r"영업이익",
        r"営業利益",
    ],
    "net_income": [
        r"\bNet income\b",
        r"\bProfit attributable to owners of parent\b",
        r"歸屬母公司淨利",
        r"本期淨利歸屬於母公司業主",
        r"本期净利归属于母公司业主",
        r"归属于上市公司股东的净利润",
        r"归属于上市公司股东\s*的净利润",
        r"淨利潤",
        r"净利润",
        r"당기순이익",
        r"親会社.*当期純利益",
    ],
    "assets": [r"\bTotal assets\b", r"資產總額", r"资产总额", r"資產總計", r"자산총계", r"総資産"],
    "liabilities": [r"\bTotal liabilities\b", r"負債總額", r"负债总额", r"負債總計", r"부채총계"],
    "equity": [r"\bTotal equity\b", r"股東權益總額", r"权益总额", r"자본총계", r"純資産"],
}

STATEMENT_BY_METRIC = {
    "revenue": "income_statement",
    "gross_profit": "income_statement",
    "operating_income": "income_statement",
    "net_income": "income_statement",
    "assets": "balance_sheet",
    "liabilities": "balance_sheet",
    "equity": "balance_sheet",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Project non-US official annual/IR disclosures into L1 financial-statement exact-slot rows."
    )
    parser.add_argument("--coverage-path", dest="coverage_paths", action="append", type=Path, default=None)
    parser.add_argument("--company-assignments", type=Path, default=DEFAULT_COMPANY_ASSIGNMENTS)
    parser.add_argument("--product-kpi-rows", type=Path, default=DEFAULT_PRODUCT_KPI_ROWS)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-rejections", type=Path, default=DEFAULT_OUTPUT_REJECTIONS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--max-metrics-per-ticker", type=int, default=8)
    parser.add_argument("--download-official-reports", action="store_true")
    parser.add_argument("--timeout-s", type=float, default=45.0)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.coverage_paths is None:
        args.coverage_paths = DEFAULT_COVERAGE_PATHS
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    assignments = _load_jsonl(args.company_assignments)
    company_by_ticker = _company_index(assignments)
    target_tickers = _target_tickers(args.tickers)
    coverage_rows = [row for path in args.coverage_paths for row in _load_jsonl(path)]
    candidates = build_disclosure_candidates(
        coverage_rows=coverage_rows,
        company_by_ticker=company_by_ticker,
        target_tickers=target_tickers,
        raw_dir=args.raw_dir,
        processed_dir=args.processed_dir,
        generated_at=generated_at,
        download_official_reports=args.download_official_reports,
        timeout_s=args.timeout_s,
    )
    parsed = build_non_us_l1_financial_statement_metric_runtime_rows(
        candidates=candidates,
        company_by_ticker=company_by_ticker,
        target_tickers=target_tickers,
        generated_at=generated_at,
        max_metrics_per_ticker=args.max_metrics_per_ticker,
    )
    alias_result = build_parent_segment_alias_rows(
        product_kpi_rows=_load_jsonl(args.product_kpi_rows),
        company_by_ticker=company_by_ticker,
        target_tickers=target_tickers,
        generated_at=generated_at,
    )
    rows = _dedupe_rows([*parsed["rows"], *alias_result["rows"]])
    rejections = [*parsed["rejections"], *alias_result["rejections"]]
    summary = build_summary(
        rows=rows,
        rejections=rejections,
        candidates=candidates,
        target_tickers=target_tickers,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_rejections=args.output_rejections,
    )
    _write_jsonl(args.output_rows, rows)
    _write_jsonl(args.output_rejections, rejections)
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["covered_target_ticker_count"] < len(target_tickers):
        return 1
    return 0


def build_disclosure_candidates(
    *,
    coverage_rows: Iterable[Mapping[str, Any]],
    company_by_ticker: Mapping[str, Mapping[str, Any]],
    target_tickers: set[str],
    raw_dir: Path,
    processed_dir: Path,
    generated_at: str,
    download_official_reports: bool,
    timeout_s: float,
) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for row in coverage_rows:
        ticker = _ticker(row)
        if not ticker or ticker not in target_tickers or ticker == "FDXF":
            continue
        cleaned_path = _resolve_path(row.get("cleaned_text_path"))
        if not cleaned_path.exists():
            continue
        candidate = {
            "ticker": ticker,
            "company_name": row.get("company_name") or company_by_ticker.get(ticker, {}).get("company_name") or ticker,
            "cleaned_text_path": str(cleaned_path),
            "document_path": row.get("document_path") or "",
            "document_url": row.get("document_url") or row.get("source_url") or "",
            "source_url": row.get("document_url") or row.get("source_url") or "",
            "source_title": row.get("source_title") or row.get("report_type") or row.get("disclosure_profile") or "official disclosure",
            "source_profile": row.get("disclosure_profile") or row.get("source_family") or "",
            "report_type": row.get("report_type") or "",
            "fiscal_year": _int(row.get("fiscal_year")),
            "candidate_source": "downloaded_global_public_disclosure",
            "generated_at": generated_at,
        }
        key = f"{ticker}:{candidate['cleaned_text_path']}"
        candidates[key] = candidate

    if download_official_reports:
        for ticker, reports in MANUAL_OFFICIAL_REPORTS.items():
            if ticker not in target_tickers:
                continue
            for report in reports:
                candidate = _download_manual_official_report(
                    ticker=ticker,
                    report=report,
                    company_by_ticker=company_by_ticker,
                    raw_dir=raw_dir,
                    processed_dir=processed_dir,
                    timeout_s=timeout_s,
                    generated_at=generated_at,
                )
                if candidate.get("cleaned_text_path"):
                    candidates[f"{ticker}:{candidate['cleaned_text_path']}"] = candidate
                else:
                    candidates[f"{ticker}:manual_gap:{report.get('document_url')}"] = candidate
    return list(candidates.values())


def build_non_us_l1_financial_statement_metric_runtime_rows(
    *,
    candidates: Iterable[Mapping[str, Any]],
    company_by_ticker: Mapping[str, Mapping[str, Any]],
    target_tickers: set[str],
    generated_at: str,
    max_metrics_per_ticker: int = 8,
) -> dict[str, list[dict[str, Any]]]:
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    rejections: list[dict[str, Any]] = []
    for candidate in candidates:
        ticker = _ticker(candidate)
        if not ticker or ticker not in target_tickers:
            continue
        cleaned_path = _resolve_path(candidate.get("cleaned_text_path"))
        if not cleaned_path.exists():
            rejections.append(_rejection(ticker, "cleaned_text_missing", candidate, generated_at))
            continue
        text = cleaned_path.read_text(encoding="utf-8", errors="ignore")
        metrics = parse_financial_metrics(text=text, ticker=ticker, candidate=candidate)
        if not metrics:
            rejections.append(_rejection(ticker, "no_value_unit_period_financial_metric_parsed", candidate, generated_at))
            continue
        for metric in metrics:
            if not metric.get("unit"):
                rejections.append(_rejection(ticker, "metric_unit_missing", {**candidate, **metric}, generated_at))
                continue
            key = (ticker, str(metric.get("metric_family") or ""))
            row = _runtime_row(metric, candidate=candidate, company_by_ticker=company_by_ticker, generated_at=generated_at)
            if key not in selected or _metric_score(row) > _metric_score(selected[key]):
                selected[key] = row

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in selected.values():
        grouped.setdefault(str(row.get("ticker") or ""), []).append(row)
    rows: list[dict[str, Any]] = []
    for ticker, ticker_rows in sorted(grouped.items()):
        ranked = sorted(ticker_rows, key=_metric_rank, reverse=True)[: max(1, max_metrics_per_ticker)]
        rows.extend(ranked)
    return {"rows": rows, "rejections": rejections}


def build_parent_segment_alias_rows(
    *,
    product_kpi_rows: Iterable[Mapping[str, Any]],
    company_by_ticker: Mapping[str, Mapping[str, Any]],
    target_tickers: set[str],
    generated_at: str,
) -> dict[str, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    if "FDXF" not in target_tickers:
        return {"rows": rows, "rejections": rejections}
    for row in product_kpi_rows:
        if str(row.get("ticker") or "").upper() != "FDX":
            continue
        citation = str(row.get("citation_span") or "")
        if "FedEx Freight segment" not in citation:
            continue
        match = re.search(r"FedEx\s+Freight\s+segment\s*\|\s*([\d,.\-()]+)", citation)
        if not match:
            match = re.search(r"FedEx\s+Freight\s+segment\s+([\d,.\-()]+)", citation)
        if not match:
            rejections.append(_rejection("FDXF", "fedex_freight_segment_value_not_parsed", row, generated_at))
            continue
        value = _parse_number(match.group(1))
        if value is None:
            rejections.append(_rejection("FDXF", "fedex_freight_segment_value_not_numeric", row, generated_at))
            continue
        source_url = str(row.get("source_url") or (row.get("citation") or {}).get("url") or "")
        evidence_ref = _stable_ref("parent_segment_alias_l1", ["FDXF", row.get("evidence_ref"), value])
        text = f"FDXF parent segment alias: FedEx 10-K reports FedEx Freight segment operating income of {value} USD millions for FY2025."
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
                "evidence_ref": evidence_ref,
                "evidence_id": evidence_ref,
                "snapshot_id": evidence_ref,
                "source_id": "company_reported_product_operating_metrics",
                "underlying_source_id": "sec_edgar_apis",
                "source_class": "parent_company_segment_disclosure",
                "source_family": "company_reported_structured_fact",
                "runtime_source_family": "company_reported_structured_fact",
                "source_layer_id": "L1",
                "source_layer": "L1",
                "layer_id": "L1",
                "source_specific_parser": "fedex_parent_segment_product_kpi_alias_projector_v0_1",
                "source_specific_resolver": "parent_issuer_segment_to_synthetic_ticker_resolver_v0_1",
                "parser_status": "value_unit_period_product_citation_parser_pass",
                "structured_fact_status": "exact_fact_materialized",
                "runtime_ready_context": True,
                "bounded_structured_context": True,
                "exact_value_authority": True,
                "can_support_company_exact_fact": True,
                "ticker": "FDXF",
                "company": company_by_ticker.get("FDXF", {}).get("company_name") or "FedEx Freight",
                "company_name": company_by_ticker.get("FDXF", {}).get("company_name") or "FedEx Freight",
                "source_url": source_url,
                "snapshot_url": source_url,
                "citation": {"url": source_url, "source_url": source_url, "title": "FedEx Freight segment operating income", "span": citation},
                "source_title": "FedEx parent 10-K segment table: FedEx Freight",
                "source_document_id": row.get("source_document_id") or "",
                "filing_type": row.get("filing_type") or "10-K",
                "period": "FY2025",
                "fiscal_year": 2025,
                "statement_or_section": "segment_operating_results",
                "metric_family": "operating_income",
                "metric_name": "FedEx Freight segment operating income",
                "canonical_metric_id": "product_kpi:segment_operating_income",
                "product_or_segment": "FedEx Freight segment",
                "product_family": "FedEx Freight segment",
                "value": value * 1_000_000,
                "unit": "USD",
                "raw_value_text": f"{value} USD_millions",
                "citation_span": citation,
                "issuer_binding_status": "issuer_mentioned_in_snapshot",
                "product_binding_status": "product_mentioned_in_snapshot",
                "counterparty_binding_status": "not_bound",
                "entity_binding": {
                    "issuer_ticker": "FDXF",
                    "parent_issuer_ticker": "FDX",
                    "issuer_binding_status": "issuer_mentioned_in_snapshot",
                    "product_binding_status": "product_mentioned_in_snapshot",
                    "counterparty_binding_status": "not_bound",
                    "resolver_status": "parent_issuer_segment_disclosure_bound_to_synthetic_segment_ticker",
                    "binding_claim_boundary": "FDXF is a segment/synthetic ticker bound only to FedEx parent segment disclosure.",
                },
                "allowed_claims": ["company_disclosed_product_kpi", "company_reported_product_operating_fact"],
                "forbidden_claims": ["market_share", "channel_inventory", "sell_through", "standalone_segment_full_financials"],
                "claim_boundary": "Parent issuer segment disclosure for FedEx Freight; supports segment operating metric only, not standalone issuer financials.",
                "text": text,
                "preview": text,
            }
        )
        break
    if not rows:
        rejections.append(_rejection("FDXF", "fedex_parent_segment_alias_source_missing", {}, generated_at))
    return {"rows": rows, "rejections": rejections}


def parse_financial_metrics(*, text: str, ticker: str, candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    normalized = _normalize_text(text)
    metrics: list[dict[str, Any]] = []
    for metric_family, patterns in METRIC_PATTERNS.items():
        best = None
        for pattern in patterns:
            parsed = _parse_metric_pattern(normalized, pattern=pattern, metric_family=metric_family, ticker=ticker, candidate=candidate)
            if parsed and (best is None or _candidate_metric_score(parsed) > _candidate_metric_score(best)):
                best = parsed
        if best:
            metrics.append(best)
    return metrics


def _parse_metric_pattern(
    text: str,
    *,
    pattern: str,
    metric_family: str,
    ticker: str,
    candidate: Mapping[str, Any],
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        start = match.start()
        window = text[max(0, start - 900) : min(len(text), start + 900)]
        line = _line_at(text, start)
        local = text[start : min(len(text), start + 450)]
        numbers = _numbers_from_context(line, local)
        value = _select_current_period_value(numbers=numbers, window=window, ticker=ticker)
        if value is None:
            continue
        unit = _infer_unit(window, ticker=ticker)
        if not unit:
            continue
        citation_span = _citation_span(line=line, local=local, unit=unit, value=value)
        metric_name = _metric_name(metric_family, match.group(0))
        fiscal_year = _int(candidate.get("fiscal_year")) or _infer_fiscal_year(window)
        parsed = {
            "ticker": ticker,
            "metric_family": metric_family,
            "metric_name": metric_name,
            "value": _scale_value(value, unit),
            "unit": _canonical_unit(unit),
            "raw_value_text": f"{value} {unit}",
            "period": f"FY{fiscal_year}" if fiscal_year else _infer_period(window),
            "fiscal_year": fiscal_year,
            "statement_or_section": STATEMENT_BY_METRIC.get(metric_family, "financial_statement"),
            "citation_span": citation_span,
            "source_context_rank": _source_context_rank(window),
        }
        if best is None or _candidate_metric_score(parsed) > _candidate_metric_score(best):
            best = parsed
    return best


def _numbers_from_context(line: str, local: str) -> list[dict[str, Any]]:
    span = line
    if len(_extract_number_tokens(span)) < 1:
        span = "\n".join(local.splitlines()[:8])
    tokens = _extract_number_tokens(span)
    return tokens[:12]


def _extract_number_tokens(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for match in re.finditer(r"(?<![A-Za-z])\(?-?\d[\d,]*(?:\.\d+)?\)?%?", text):
        token = match.group(0)
        if re.fullmatch(r"\d{4}", token) and 1900 <= int(token) <= 2099:
            continue
        value = _parse_number(token)
        if value is None:
            continue
        out.append({"raw": token, "value": value, "is_percent": token.endswith("%"), "index": match.start()})
    return out


def _select_current_period_value(*, numbers: list[dict[str, Any]], window: str, ticker: str) -> float | None:
    candidates = [n for n in numbers if not n.get("is_percent")]
    if not candidates:
        return None
    lowered = window.lower()
    if "three months ended" in lowered and "year ended" in lowered and len(candidates) >= 2:
        if len(candidates) >= 4:
            return float(candidates[-2]["value"])
        return float(candidates[-1]["value"])
    if ticker.endswith(".KS") or "제 78 기" in window or "제 57 기" in window:
        return float(candidates[0]["value"])
    if re.search(r"\b110年\b.*\b114年\b", window) or re.search(r"\b2021\b.*\b2025\b", window):
        return float(candidates[-1]["value"])
    if "2025 2024" in window or "2026 2025" in window:
        return float(candidates[0]["value"])
    if len(candidates) >= 4 and any(n.get("is_percent") for n in numbers):
        return float(candidates[-1]["value"])
    return float(candidates[0]["value"])


def _infer_unit(window: str, *, ticker: str) -> str:
    lowered = window.lower()
    if "billion yen" in lowered:
        return "JPY_billions"
    if "millions of yen" in lowered or "million yen" in lowered or "百万円" in window:
        return "JPY_millions"
    if "€ in\nmillions" in lowered or "€ in millions" in lowered or "eur million" in lowered:
        return "EUR_millions"
    if "billion euros" in lowered:
        return "EUR_billions"
    if "백만원" in window:
        return "KRW_millions"
    if "百萬元" in window or "百万元" in window:
        if "人民幣" in window or "rmb" in lowered or "cny" in lowered:
            return "CNY_millions"
        if "新台幣" in window or "新臺幣" in window:
            return "TWD_millions"
    if "單位：百萬新台幣" in window or "單位:百萬新台幣" in window:
        return "TWD_millions"
    if (
        "單位：新台幣仟元" in window
        or "單位:新台幣仟元" in window
        or "新臺幣仟元" in window
        or "新台幣千元" in window
        or "新臺幣千元" in window
    ):
        return "TWD_thousands"
    if ("单位：千元" in window or "单位:千元" in window) and ticker.endswith(".SZ"):
        return "CNY_thousands"
    if "rmb'000" in lowered or "rmb’000" in lowered or "rmb 000" in lowered:
        return "CNY_thousands"
    if "$ in millions" in lowered or "dollars in millions" in lowered:
        return "USD_millions"
    if ticker.endswith(".TW") and "財務數據及獲利能力分析" in window and "百萬新台幣" in window:
        return "TWD_millions"
    return ""


def _scale_value(value: float, unit: str) -> float:
    normalized = unit.lower()
    if normalized.endswith("_billions"):
        return value * 1_000_000_000
    if normalized.endswith("_millions"):
        return value * 1_000_000
    if normalized.endswith("_thousands"):
        return value * 1_000
    return value


def _canonical_unit(unit: str) -> str:
    currency = unit.split("_", 1)[0].upper()
    return currency


def _runtime_row(
    metric: Mapping[str, Any],
    *,
    candidate: Mapping[str, Any],
    company_by_ticker: Mapping[str, Mapping[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    ticker = _ticker(candidate)
    source_url = str(candidate.get("source_url") or candidate.get("document_url") or "").strip()
    period = str(metric.get("period") or "").strip()
    metric_family = str(metric.get("metric_family") or "")
    evidence_ref = _stable_ref("non_us_l1_financial_statement_metric", [ticker, metric_family, source_url, period, metric.get("value")])
    company_name = str(candidate.get("company_name") or company_by_ticker.get(ticker, {}).get("company_name") or ticker)
    citation_span = str(metric.get("citation_span") or "")
    text = f"{ticker} official disclosure reports {metric.get('metric_name')} of {metric.get('value')} {metric.get('unit')} for {period}."
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "snapshot_id": evidence_ref,
        "source_id": "company_ir_reports",
        "underlying_source_id": str(candidate.get("source_profile") or "company_ir_reports"),
        "source_class": "company_ir_material",
        "source_family": "company_reported_structured_fact",
        "runtime_source_family": "company_reported_structured_fact",
        "source_layer_id": "L1",
        "source_layer": "L1",
        "layer_id": "L1",
        "source_specific_parser": "non_us_official_disclosure_financial_statement_metric_parser_v0_1",
        "source_specific_resolver": "official_exchange_ir_issuer_resolver_v0_1",
        "parser_status": "value_unit_period_product_citation_parser_pass",
        "structured_fact_status": "exact_fact_materialized",
        "runtime_ready_context": True,
        "bounded_structured_context": True,
        "exact_value_authority": True,
        "can_support_company_exact_fact": True,
        "ticker": ticker,
        "company": company_name,
        "company_name": company_name,
        "source_url": source_url,
        "snapshot_url": source_url,
        "citation": {"url": source_url, "source_url": source_url, "title": str(candidate.get("source_title") or ""), "span": citation_span},
        "source_title": str(candidate.get("source_title") or f"{ticker} official disclosure"),
        "source_document_id": str(candidate.get("document_path") or candidate.get("cleaned_text_path") or source_url),
        "filing_type": str(candidate.get("report_type") or "official_annual_or_ir_report"),
        "filing_date": "",
        "period": period,
        "fiscal_year": metric.get("fiscal_year") or candidate.get("fiscal_year") or "",
        "statement_or_section": metric.get("statement_or_section") or "financial_statement",
        "metric_family": metric_family,
        "metric_name": metric.get("metric_name") or metric_family,
        "canonical_metric_id": f"financial_metric:{metric_family}",
        "value": metric.get("value"),
        "unit": metric.get("unit") or "",
        "raw_value_text": metric.get("raw_value_text") or "",
        "product_or_segment": "Consolidated company",
        "product_family": "Consolidated company",
        "citation_span": citation_span,
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "not_applicable",
        "counterparty_binding_status": "not_bound",
        "entity_binding": {
            "issuer_ticker": ticker,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "not_applicable",
            "counterparty_binding_status": "not_bound",
            "resolver_status": "official_exchange_or_company_ir_disclosure_bound_to_issuer",
            "binding_claim_boundary": "Official company/local exchange disclosure issuer binding only; product-level claims require product KPI rows.",
        },
        "allowed_claims": ["company_reported_financial_statement_fact", f"financial_metric:{metric_family}"],
        "forbidden_claims": ["product_sales_without_product_kpi", "market_share", "asp", "channel_inventory", "sell_through"],
        "claim_boundary": (
            "Official company/local exchange financial statement fact; supports consolidated financial analysis only. "
            "It cannot be used as product KPI or market-share evidence."
        ),
        "text": text,
        "preview": text,
    }


def build_summary(
    *,
    rows: list[dict[str, Any]],
    rejections: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    target_tickers: set[str],
    generated_at: str,
    output_rows: Path,
    output_rejections: Path,
) -> dict[str, Any]:
    covered = {str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}
    candidate_tickers = {str(row.get("ticker") or "").upper() for row in candidates if row.get("ticker")}
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if target_tickers <= covered else "gap",
        "target_ticker_count": len(target_tickers),
        "covered_target_ticker_count": len(target_tickers & covered),
        "uncovered_target_ticker_count": len(target_tickers - covered),
        "uncovered_target_tickers": sorted(target_tickers - covered),
        "candidate_ticker_count": len(candidate_tickers),
        "candidate_count": len(candidates),
        "runtime_row_count": len(rows),
        "metric_family_counts": dict(sorted(Counter(str(row.get("metric_family") or "") for row in rows).items())),
        "row_source_counts": dict(sorted(Counter(str(row.get("source_id") or "") for row in rows).items())),
        "rejection_count": len(rejections),
        "rejection_reason_counts": dict(sorted(Counter(str(row.get("rejection_reason") or "") for row in rejections).items())),
        "outputs": {"rows": str(output_rows), "rejections": str(output_rejections)},
        "claim_boundary": "Non-US official disclosure rows support consolidated/company financial statement exact facts only.",
    }


def _download_manual_official_report(
    *,
    ticker: str,
    report: Mapping[str, Any],
    company_by_ticker: Mapping[str, Mapping[str, Any]],
    raw_dir: Path,
    processed_dir: Path,
    timeout_s: float,
    generated_at: str,
) -> dict[str, Any]:
    url = str(report.get("document_url") or "")
    suffix = ".pdf" if ".pdf" in url.lower() else ".html"
    digest = _stable_digest(url)
    raw_path = raw_dir / _safe_ticker(ticker) / f"{digest}{suffix}"
    clean_path = processed_dir / _safe_ticker(ticker) / f"{digest}_cleaned_text.txt"
    try:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        clean_path.parent.mkdir(parents=True, exist_ok=True)
        if not raw_path.exists():
            request = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 FIN-Insight-Agent official disclosure parser",
                    "Accept": "application/pdf,text/html,application/xhtml+xml,*/*",
                    "Referer": "https://www.google.com/",
                },
            )
            with urlopen(request, timeout=timeout_s) as response:
                raw_path.write_bytes(response.read())
        payload = raw_path.read_bytes()
        if raw_path.suffix.lower() == ".pdf" or payload.startswith(b"%PDF"):
            cleaned_text = _extract_pdf_text(raw_path)
        else:
            cleaned_text = _clean_html(payload.decode("utf-8", errors="ignore"))
        clean_path.write_text(cleaned_text, encoding="utf-8", newline="\n")
        return {
            "ticker": ticker,
            "company_name": company_by_ticker.get(ticker, {}).get("company_name") or ticker,
            "cleaned_text_path": str(clean_path),
            "document_path": str(raw_path),
            "document_url": url,
            "source_url": url,
            "source_title": report.get("source_title") or "official disclosure",
            "source_profile": "company_ir_reports",
            "report_type": report.get("report_type") or "official_report",
            "fiscal_year": report.get("fiscal_year") or 0,
            "candidate_source": "manual_official_report_download",
            "generated_at": generated_at,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ticker": ticker,
            "company_name": company_by_ticker.get(ticker, {}).get("company_name") or ticker,
            "document_url": url,
            "source_url": url,
            "source_title": report.get("source_title") or "official disclosure",
            "source_profile": "company_ir_reports",
            "report_type": report.get("report_type") or "official_report",
            "fiscal_year": report.get("fiscal_year") or 0,
            "candidate_source": "manual_official_report_download_failed",
            "download_error": f"{type(exc).__name__}:{str(exc)[:220]}",
            "generated_at": generated_at,
        }


def _extract_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    blocks: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        normalized = _normalize_text(text)
        if normalized:
            blocks.append(f"===== page {index} =====\n{normalized}")
    return "\n\n".join(blocks).strip()


def _clean_html(text: str) -> str:
    collector = _TextCollector()
    collector.feed(text)
    collector.close()
    return _normalize_text(html.unescape("\n".join(collector.blocks)))


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[str] = []
        self._current: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "div", "tr", "li", "h1", "h2", "h3", "h4", "br"}:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "tr", "li", "h1", "h2", "h3", "h4"}:
            self._flush()

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._current.append(text)

    def _flush(self) -> None:
        if self._current:
            value = " ".join(self._current).strip()
            if value:
                self.blocks.append(value)
            self._current = []

    def close(self) -> None:
        self._flush()
        super().close()


def _rejection(ticker: str, reason: str, row: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": REJECTION_SCHEMA_VERSION,
        "generated_at": generated_at,
        "ticker": ticker,
        "rejection_reason": reason,
        "source_url": row.get("source_url") or row.get("document_url") or "",
        "cleaned_text_path": row.get("cleaned_text_path") or "",
        "source_title": row.get("source_title") or "",
    }


def _metric_score(row: Mapping[str, Any]) -> tuple[int, int, int, str]:
    return (
        _int(row.get("fiscal_year")),
        2 if str(row.get("source_url") or "").startswith("https://") else 1,
        len(str(row.get("citation_span") or "")),
        str(row.get("evidence_ref") or ""),
    )


def _metric_rank(row: Mapping[str, Any]) -> tuple[int, tuple[int, int, int, str]]:
    order = {"revenue": 100, "gross_profit": 90, "operating_income": 85, "net_income": 80, "assets": 60, "liabilities": 55, "equity": 50}
    return order.get(str(row.get("metric_family") or ""), 0), _metric_score(row)


def _candidate_metric_score(row: Mapping[str, Any]) -> tuple[int, int, float]:
    return (_int(row.get("source_context_rank")), _int(row.get("fiscal_year")), abs(float(row.get("value") or 0)))


def _source_context_rank(window: str) -> int:
    rank = 0
    lowered = window.lower()
    if any(term in lowered for term in ("consolidated", "ifrs", "non-gaap", "the year ended")):
        rank += 3
    if any(term in window for term in ("合併", "連結", "연 결", "연결", "本集團")):
        rank += 3
    if any(term in lowered for term in ("financial statements", "financial results", "summary of consolidated")):
        rank += 2
    return rank


def _line_at(text: str, index: int) -> str:
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    if end < 0:
        end = len(text)
    return text[start:end].strip()


def _citation_span(*, line: str, local: str, unit: str, value: float) -> str:
    base = line.strip() or " ".join(local.splitlines()[:4]).strip()
    base = re.sub(r"\s+", " ", base)
    if len(base) < 40:
        base = re.sub(r"\s+", " ", " ".join(local.splitlines()[:8]).strip())
    return f"{base[:650]} | parsed_value={value} | parsed_unit={unit}"


def _metric_name(metric_family: str, label: str) -> str:
    if label:
        return re.sub(r"\s+", " ", label).strip()
    return metric_family.replace("_", " ").title()


def _parse_number(token: Any) -> float | None:
    text = str(token or "").strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()%").replace(",", "")
    if text in {"", "-", "—"}:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return -value if negative else value


def _infer_fiscal_year(window: str) -> int:
    years = [int(y) for y in re.findall(r"\b(20[12]\d)\b", window)]
    if years:
        return max(years)
    return 0


def _infer_period(window: str) -> str:
    year = _infer_fiscal_year(window)
    return f"FY{year}" if year else ""


def _normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _target_tickers(tickers: Iterable[str]) -> set[str]:
    values = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    return values or set(R6_TARGET_TICKERS)


def _company_index(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = _ticker(row)
        if ticker:
            out[ticker] = dict(row)
    return out


def _ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or "").strip().upper()


def _resolve_path(value: Any) -> Path:
    text = str(value or "").strip()
    if not text:
        return Path("__missing_path__")
    path = Path(text)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if isinstance(value, Mapping):
                rows.append(dict(value))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _dedupe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("evidence_ref") or row.get("evidence_id") or "")
        if not key:
            key = _stable_ref("non_us_l1_row", [row.get("ticker"), row.get("source_url"), row.get("metric_name"), row.get("period"), row.get("value")])
        out.setdefault(key, dict(row))
    return list(out.values())


def _stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    return f"{prefix}:{_stable_digest('||'.join(str(part or '') for part in parts))}"


def _stable_digest(value: Any) -> str:
    return hashlib.sha1(str(value or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _safe_ticker(ticker: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", ticker)


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
