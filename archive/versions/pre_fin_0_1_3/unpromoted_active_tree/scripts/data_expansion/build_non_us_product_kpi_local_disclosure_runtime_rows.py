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


SCHEMA_VERSION = "finsight_non_us_product_kpi_local_disclosure_runtime_row_v0_1"
REJECTION_SCHEMA_VERSION = "finsight_non_us_product_kpi_local_disclosure_runtime_rejection_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_non_us_product_kpi_local_disclosure_runtime_summary_v0_1"

DEFAULT_DOCKET_PATH = REPO_ROOT / "data" / "manifests" / "company_gap_docket_v0_1.jsonl"
DEFAULT_COVERAGE_PATHS = [
    REPO_ROOT / "data" / "manifests" / "non_us_supply_chain_primary_disclosure_coverage_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_jp_company_ir_fallback_download_clean_r6_v0_1.jsonl",
]
DEFAULT_COMPANY_ASSIGNMENTS = REPO_ROOT / "data" / "manifests" / "vertical_source_lane_company_assignments_v0_1.jsonl"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/global_public_disclosures/r6_non_us_l1_manual_official")
DEFAULT_PROCESSED_DIR = Path(
    "Z:/FIN_Insight_Agent_data/processed_private/public_sources/global_public_disclosures/r6_non_us_l1_manual_official"
)
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl"
DEFAULT_OUTPUT_REJECTIONS = (
    REPO_ROOT / "data" / "manifests" / "non_us_product_kpi_local_disclosure_runtime_rejections_v0_1.jsonl"
)
DEFAULT_OUTPUT_SUMMARY = (
    REPO_ROOT / "data" / "manifests" / "non_us_product_kpi_local_disclosure_runtime_summary_v0_1.json"
)
DEFAULT_OUTPUT_REPORT = (
    REPO_ROOT
    / "docs"
    / "internal"
    / "vnext_20260610"
    / "vertical_lanes"
    / "non_us_product_kpi_local_disclosure_runtime.zh-CN.md"
)

DOCKET_CLUSTER_ID = "product_kpi_non_us_ir_local_exchange_parser"
FALLBACK_TARGET_TICKERS = {
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
    "IFX.DE",
}

# Official reports that were missing or stale in the lane coverage manifest.  These are
# issuer/IR or official results pages, not search-engine snippets.
MANUAL_OFFICIAL_REPORTS = {
    "373220.KS": [
        {
            "report_type": "official_company_news_release",
            "fiscal_year": 2025,
            "document_url": "https://news.lgensol.com/company-news/press-releases/4303/",
            "source_title": "LG Energy Solution releases 2025 third-quarter financial results",
        }
    ],
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
    "8035.T": [
        {
            "report_type": "integrated_report",
            "fiscal_year": 2025,
            "document_url": "https://www.tel.com/ir/library/ar/pjsoh100000000rc-att/ir2025_all_en.pdf",
            "source_title": "Tokyo Electron Integrated Report 2025",
        }
    ],
}

SEGMENT_NODE_TYPE = "business_line"
PRODUCT_NODE_TYPE = "product_family"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Project non-US official/local-exchange disclosures into product/business KPI exact-slot rows."
    )
    parser.add_argument("--docket-path", type=Path, default=DEFAULT_DOCKET_PATH)
    parser.add_argument("--coverage-path", dest="coverage_paths", action="append", type=Path, default=None)
    parser.add_argument("--company-assignments", type=Path, default=DEFAULT_COMPANY_ASSIGNMENTS)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-rejections", type=Path, default=DEFAULT_OUTPUT_REJECTIONS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--max-rows-per-ticker", type=int, default=16)
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
    company_by_ticker = _company_index(_load_jsonl(args.company_assignments))
    target_tickers = _target_tickers(args.tickers, args.docket_path)
    candidates = build_disclosure_candidates(
        coverage_rows=[row for path in args.coverage_paths for row in _load_jsonl(path)],
        company_by_ticker=company_by_ticker,
        target_tickers=target_tickers,
        raw_dir=args.raw_dir,
        processed_dir=args.processed_dir,
        generated_at=generated_at,
        download_official_reports=args.download_official_reports,
        timeout_s=args.timeout_s,
    )
    parsed = build_non_us_product_kpi_local_disclosure_runtime_rows(
        candidates=candidates,
        company_by_ticker=company_by_ticker,
        target_tickers=target_tickers,
        generated_at=generated_at,
        max_rows_per_ticker=args.max_rows_per_ticker,
    )
    rows = _dedupe_rows(parsed["rows"])
    rejections = parsed["rejections"]
    summary = build_summary(
        rows=rows,
        rejections=rejections,
        candidates=candidates,
        target_tickers=target_tickers,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_rejections=args.output_rejections,
        output_report=args.output_report,
    )
    _write_jsonl(args.output_rows, rows)
    _write_jsonl(args.output_rejections, rejections)
    _write_json(args.output_summary, summary)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(render_report(summary), encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["unclassified_rejection_count"]:
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
        if not ticker or ticker not in target_tickers:
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
            "source_title": row.get("source_title") or row.get("report_type") or row.get("disclosure_profile") or "",
            "source_profile": row.get("disclosure_profile") or row.get("source_family") or "",
            "report_type": row.get("report_type") or "",
            "fiscal_year": _int(row.get("fiscal_year")),
            "candidate_source": "lane_coverage_manifest",
            "generated_at": generated_at,
        }
        candidates[f"{ticker}:{cleaned_path}"] = candidate

    for ticker, reports in MANUAL_OFFICIAL_REPORTS.items():
        if ticker not in target_tickers:
            continue
        for report in reports:
            candidate = _manual_official_report_candidate(
                ticker=ticker,
                report=report,
                company_by_ticker=company_by_ticker,
                raw_dir=raw_dir,
                processed_dir=processed_dir,
                generated_at=generated_at,
                download=download_official_reports,
                timeout_s=timeout_s,
            )
            if candidate.get("cleaned_text_path") or candidate.get("download_error"):
                key = f"{ticker}:{candidate.get('cleaned_text_path') or candidate.get('document_url')}"
                candidates[key] = candidate
    return sorted(candidates.values(), key=_candidate_sort_key, reverse=True)


def build_non_us_product_kpi_local_disclosure_runtime_rows(
    *,
    candidates: Iterable[Mapping[str, Any]],
    company_by_ticker: Mapping[str, Mapping[str, Any]],
    target_tickers: set[str],
    generated_at: str,
    max_rows_per_ticker: int = 16,
) -> dict[str, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    candidate_seen: set[str] = set()
    ticker_had_row: set[str] = set()
    for candidate in candidates:
        ticker = _ticker(candidate)
        if not ticker or ticker not in target_tickers:
            continue
        candidate_seen.add(ticker)
        if candidate.get("download_error"):
            rejections.append(_rejection(ticker, "manual_official_report_download_failed", candidate, generated_at))
            continue
        cleaned_path = _resolve_path(candidate.get("cleaned_text_path"))
        if not cleaned_path.exists():
            rejections.append(_rejection(ticker, "cleaned_text_missing", candidate, generated_at))
            continue
        text = cleaned_path.read_text(encoding="utf-8", errors="ignore")
        stale_reason = _stale_document_reason(text, candidate)
        if stale_reason:
            rejections.append(_rejection(ticker, stale_reason, candidate, generated_at))
            continue
        parsed_rows = parse_product_kpi_rows(text=text, ticker=ticker, candidate=candidate, generated_at=generated_at)
        if not parsed_rows:
            rejections.append(_rejection(ticker, _no_parse_reason(text), candidate, generated_at))
            continue
        for row in parsed_rows:
            rows.append(_runtime_row(row, candidate=candidate, company_by_ticker=company_by_ticker, generated_at=generated_at))
            ticker_had_row.add(ticker)

    for ticker in sorted(target_tickers - candidate_seen):
        rejections.append(_rejection(ticker, "no_local_disclosure_text_candidate", {"ticker": ticker}, generated_at))

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in _dedupe_rows(rows):
        grouped.setdefault(_ticker(row), []).append(row)

    selected: list[dict[str, Any]] = []
    for ticker, ticker_rows in sorted(grouped.items()):
        ranked = sorted(ticker_rows, key=_runtime_row_rank, reverse=True)
        selected.extend(ranked[: max(1, max_rows_per_ticker)])
    return {"rows": selected, "rejections": rejections}


def parse_product_kpi_rows(
    *, text: str, ticker: str, candidate: Mapping[str, Any], generated_at: str
) -> list[dict[str, Any]]:
    normalized = _normalize_text(text)
    parser_text = re.sub(r"\s+", " ", normalized).strip()
    parsers = [
        _parse_kr_hynix_segment_revenue,
        _parse_kr_samsung_major_product_sales,
        _parse_byd_segment_revenue,
        _parse_catl_product_revenue_and_margin,
        _parse_infineon_segment_revenue,
        _parse_panasonic_segment_sales,
        _parse_advantest_segment_sales,
        _parse_tw_mops_product_sales_volume_value,
        _parse_quanta_notebook_shipments,
        _parse_lges_official_order_backlog,
        _parse_disco_shipment_value,
        _parse_tokyo_electron_segment_sales,
    ]
    out: list[dict[str, Any]] = []
    for parser in parsers:
        out.extend(parser(parser_text, ticker=ticker, candidate=candidate, generated_at=generated_at))
    return _dedupe_parsed_rows(out)


def _parse_kr_hynix_segment_revenue(
    text: str, *, ticker: str, candidate: Mapping[str, Any], generated_at: str
) -> list[dict[str, Any]]:
    if ticker != "000660.KS":
        return []
    match = re.search(
        r"공시대상\s+사업부문의\s+구분.*?\(단위:\s*백만원\)\s*구분\s+매출액\s+매출액\s+비중\s+주요제품\s+"
        r"(?P<segment>반도체\s*부문)\s+(?P<value>[\d,]+)\s+100\.0%\s+(?P<products>[^|]+?)\s+합계",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []
    segment = " ".join(match.group("segment").split())
    products = " ".join(match.group("products").split())
    value = _parse_number(match.group("value"))
    if value is None:
        return []
    citation = _citation(match.group(0))
    return [
        _parsed_row(
            ticker=ticker,
            product_or_segment=f"{segment} ({products})",
            product_node_type=SEGMENT_NODE_TYPE,
            metric_family="segment_revenue",
            metric_name="segment revenue",
            value=value * 1_000_000,
            unit="KRW",
            raw_value_text=f"{match.group('value')} KRW_millions",
            scale="KRW_millions",
            period=_period(candidate),
            fiscal_year=_int(candidate.get("fiscal_year")),
            citation_span=citation,
            source_specific_parser="kr_dart_semiconductor_business_segment_table_parser_v0_1",
        )
    ]


def _parse_kr_samsung_major_product_sales(
    text: str, *, ticker: str, candidate: Mapping[str, Any], generated_at: str
) -> list[dict[str, Any]]:
    if ticker != "005930.KS":
        return []
    table = _between(text, "(단위 : 억원, %) 부 문 주요 제품 매출액 비중", "※ 각 부문별 매출액")
    if not table:
        return []
    rows: list[dict[str, Any]] = []
    patterns = [
        ("DX 부문", "DS 부문"),
        ("DS 부문", "SDC"),
        ("SDC", "Harman"),
        ("Harman", "기타"),
    ]
    for segment, next_segment in patterns:
        part = _between(f"{table} {next_segment}", segment, next_segment)
        match = re.search(r"(?P<products>.+?)\s+(?P<value>[\d,]+)\s+(?P<pct>\d+(?:\.\d+)?)%", part)
        if not match:
            continue
        products = " ".join(match.group("products").split())
        value = _parse_number(match.group("value"))
        if value is None:
            continue
        citation = _citation(f"{segment} {products} {match.group('value')} {match.group('pct')}%")
        rows.append(
            _parsed_row(
                ticker=ticker,
                product_or_segment=f"{segment} ({products})",
                product_node_type=SEGMENT_NODE_TYPE,
                metric_family="segment_revenue",
                metric_name="major product/segment sales",
                value=value * 100_000_000,
                unit="KRW",
                raw_value_text=f"{match.group('value')} KRW_100_millions",
                scale="KRW_100_millions",
                period=_period(candidate),
                fiscal_year=_int(candidate.get("fiscal_year")),
                citation_span=citation,
                source_specific_parser="kr_dart_major_product_sales_table_parser_v0_1",
            )
        )
    return rows


def _parse_byd_segment_revenue(
    text: str, *, ticker: str, candidate: Mapping[str, Any], generated_at: str
) -> list[dict[str, Any]]:
    if ticker != "1211.HK":
        return []
    match = re.search(
        r"Mobile handset components, assembly and other products\s+Automobiles and related products and other products"
        r".{0,260}?Revenue from external trading\s+對外交易收入\s+"
        r"(?P<mobile>[\d,]+)\s+(?P<auto>[\d,]+)\s+(?P<adjust>[\d,()\-]+)\s+(?P<total>[\d,]+)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []
    specs = [
        ("Mobile handset components, assembly and other products", match.group("mobile")),
        ("Automobiles and related products and other products", match.group("auto")),
    ]
    rows = []
    for product, raw in specs:
        value = _parse_number(raw)
        if value is None:
            continue
        rows.append(
            _parsed_row(
                ticker=ticker,
                product_or_segment=product,
                product_node_type=SEGMENT_NODE_TYPE,
                metric_family="segment_revenue",
                metric_name="revenue from external trading",
                value=value * 1_000,
                unit="CNY",
                raw_value_text=f"{raw} RMB_thousands",
                scale="RMB_thousands",
                period=_period(candidate),
                fiscal_year=_int(candidate.get("fiscal_year")),
                citation_span=_citation(match.group(0)),
                source_specific_parser="hkex_operating_segment_external_revenue_table_parser_v0_1",
            )
        )
    return rows


def _parse_catl_product_revenue_and_margin(
    text: str, *, ticker: str, candidate: Mapping[str, Any], generated_at: str
) -> list[dict[str, Any]]:
    if ticker != "300750.SZ":
        return []
    products = ("动力电池系统", "储能电池系统", "电池材料及回收", "电池矿产资源")
    rows: list[dict[str, Any]] = []
    for product in products:
        match = re.search(
            rf"{re.escape(product)}\s+(?P<revenue>[\d,]+)\s+(?P<share>\d+(?:\.\d+)?)%\s+"
            rf"(?P<prior>[\d,]+)\s+(?P<prior_share>\d+(?:\.\d+)?)%\s+(?P<change>-?\d+(?:\.\d+)?)%",
            text,
        )
        if match:
            value = _parse_number(match.group("revenue"))
            if value is not None:
                rows.append(
                    _parsed_row(
                        ticker=ticker,
                        product_or_segment=product,
                        product_node_type=PRODUCT_NODE_TYPE,
                        metric_family="product_revenue",
                        metric_name="product revenue",
                        value=value * 1_000,
                        unit="CNY",
                        raw_value_text=f"{match.group('revenue')} CNY_thousands",
                        scale="CNY_thousands",
                        period=_period(candidate),
                        fiscal_year=_int(candidate.get("fiscal_year")),
                        citation_span=_citation(match.group(0)),
                        source_specific_parser="szse_cninfo_product_revenue_table_parser_v0_1",
                    )
                )
        margin_match = re.search(
            rf"{re.escape(product)}\s+(?P<revenue>[\d,]+)\s+(?P<cost>[\d,]+)\s+"
            rf"(?P<margin>\d+(?:\.\d+)?)%\s+",
            text,
        )
        if margin_match:
            margin = _parse_number(margin_match.group("margin"))
            if margin is not None:
                rows.append(
                    _parsed_row(
                        ticker=ticker,
                        product_or_segment=product,
                        product_node_type=PRODUCT_NODE_TYPE,
                        metric_family="product_gross_margin",
                        metric_name="product gross margin",
                        value=margin,
                        unit="PERCENT",
                        raw_value_text=f"{margin_match.group('margin')}%",
                        scale="percent",
                        period=_period(candidate),
                        fiscal_year=_int(candidate.get("fiscal_year")),
                        citation_span=_citation(margin_match.group(0)),
                        source_specific_parser="szse_cninfo_product_revenue_cost_margin_table_parser_v0_1",
                    )
                )
    return rows


def _parse_infineon_segment_revenue(
    text: str, *, ticker: str, candidate: Mapping[str, Any], generated_at: str
) -> list[dict[str, Any]]:
    if ticker != "IFX.DE":
        return []
    table = _between(text, "Revenue by segment", "Selected results of operations")
    if not table:
        return []
    rows: list[dict[str, Any]] = []
    for segment in ("Automotive", "Green Industrial Power", "Power & Sensor Systems", "Connected Secure Systems"):
        match = re.search(rf"{re.escape(segment)}\s+(?P<value>[\d,]+)\s+\d+\s+[\d,]+\s+\d+\s+\(?-?\d+\)?", table)
        if not match:
            continue
        value = _parse_number(match.group("value"))
        if value is None:
            continue
        rows.append(
            _parsed_row(
                ticker=ticker,
                product_or_segment=segment,
                product_node_type=SEGMENT_NODE_TYPE,
                metric_family="segment_revenue",
                metric_name="revenue by segment",
                value=value * 1_000_000,
                unit="EUR",
                raw_value_text=f"{match.group('value')} EUR_millions",
                scale="EUR_millions",
                period=_period(candidate),
                fiscal_year=_int(candidate.get("fiscal_year")),
                citation_span=_citation(f"Revenue by segment {match.group(0)}"),
                source_specific_parser="eu_annual_report_segment_revenue_table_parser_v0_1",
            )
        )
    return rows


def _parse_panasonic_segment_sales(
    text: str, *, ticker: str, candidate: Mapping[str, Any], generated_at: str
) -> list[dict[str, Any]]:
    if ticker != "6752.T":
        return []
    match = re.search(
        r"Lifestyle\s+(?P<lifestyle>[\d,.]+)\s+Energy\s+(?P<energy>[\d,.]+)\s+Industry\s+(?P<industry>[\d,.]+)\s+"
        r"Connect\s+(?P<connect>[\d,.]+)\s+Sales\s+¥(?P<total>[\d,.]+)\s+billion",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return []
    rows = []
    for product, group in [
        ("Lifestyle", "lifestyle"),
        ("Energy", "energy"),
        ("Industry", "industry"),
        ("Connect", "connect"),
    ]:
        value = _parse_number(match.group(group))
        if value is None:
            continue
        rows.append(
            _parsed_row(
                ticker=ticker,
                product_or_segment=product,
                product_node_type=SEGMENT_NODE_TYPE,
                metric_family="segment_sales",
                metric_name="segment sales",
                value=value * 1_000_000_000,
                unit="JPY",
                raw_value_text=f"{match.group(group)} JPY_billions",
                scale="JPY_billions",
                period=_period(candidate),
                fiscal_year=_int(candidate.get("fiscal_year")),
                citation_span=_citation(match.group(0)),
                source_specific_parser="jp_ir_integrated_report_segment_sales_panel_parser_v0_1",
            )
        )
    return rows


def _parse_advantest_segment_sales(
    text: str, *, ticker: str, candidate: Mapping[str, Any], generated_at: str
) -> list[dict[str, Any]]:
    if ticker != "6857.T":
        return []
    match = re.search(
        r"Net Sales\s+(?P<total>[\d,.]+)\s+billion yen\s+(?P<test>[\d,.]+)\s+billion yen\s+"
        r"Test System Business\s+(?P<services>[\d,.]+)\s+billion yen\s+Services and Others",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return []
    rows = []
    for product, group in [("Test System Business", "test"), ("Services and Others", "services")]:
        value = _parse_number(match.group(group))
        if value is None:
            continue
        rows.append(
            _parsed_row(
                ticker=ticker,
                product_or_segment=product,
                product_node_type=SEGMENT_NODE_TYPE,
                metric_family="segment_sales",
                metric_name="segment sales",
                value=value * 1_000_000_000,
                unit="JPY",
                raw_value_text=f"{match.group(group)} JPY_billions",
                scale="JPY_billions",
                period=_period(candidate),
                fiscal_year=_int(candidate.get("fiscal_year")),
                citation_span=_citation(match.group(0)),
                source_specific_parser="jp_ir_integrated_report_advantest_segment_sales_panel_parser_v0_1",
            )
        )
    return rows


def _parse_tw_mops_product_sales_volume_value(
    text: str, *, ticker: str, candidate: Mapping[str, Any], generated_at: str
) -> list[dict[str, Any]]:
    if ticker != "3231.TW":
        return []
    if "數量單位：千台/千片/千個" not in text or "金額單位：新台幣千元" not in text:
        return []
    rows: list[dict[str, Any]] = []
    product_specs = [
        ("3C 電子產品", "3C electronic products"),
        ("其他產品", "other products"),
    ]
    for product_text, product_label in product_specs:
        match = re.search(
            rf"{re.escape(product_text)}\s+"
            r"(?P<prior_domestic_volume>[\d,]+)\s+(?P<prior_domestic_value>[\d,]+)\s+"
            r"(?P<prior_export_volume>[\d,]+)\s+(?P<prior_export_value>[\d,]+)\s+"
            r"(?P<domestic_volume>[\d,]+)\s+(?P<domestic_value>[\d,]+)\s+"
            r"(?P<export_volume>[\d,]+)\s+(?P<export_value>[\d,]+)",
            text,
        )
        if not match:
            continue
        citation = _citation(
            "數量單位：千台/千片/千個 金額單位：新台幣千元 "
            f"{product_text} {match.group('domestic_volume')} {match.group('domestic_value')} "
            f"{match.group('export_volume')} {match.group('export_value')}"
        )
        for region_label, volume_group, value_group in [
            ("domestic", "domestic_volume", "domestic_value"),
            ("export", "export_volume", "export_value"),
        ]:
            volume = _parse_number(match.group(volume_group))
            if volume is not None:
                rows.append(
                    _parsed_row(
                        ticker=ticker,
                        product_or_segment=f"{product_label} ({region_label})",
                        product_node_type=PRODUCT_NODE_TYPE,
                        metric_family="shipments",
                        metric_name="product sales volume",
                        value=volume * 1_000,
                        unit="UNITS",
                        raw_value_text=f"{match.group(volume_group)} thousand units/pieces/items",
                        scale="thousand_units_pieces_or_items",
                        period=_period(candidate),
                        fiscal_year=_int(candidate.get("fiscal_year")),
                        citation_span=citation,
                        source_specific_parser="tw_mops_product_sales_volume_value_table_parser_v0_1",
                    )
                )
            value = _parse_number(match.group(value_group))
            if value is not None:
                rows.append(
                    _parsed_row(
                        ticker=ticker,
                        product_or_segment=f"{product_label} ({region_label})",
                        product_node_type=PRODUCT_NODE_TYPE,
                        metric_family="product_revenue",
                        metric_name="product sales value",
                        value=value * 1_000,
                        unit="TWD",
                        raw_value_text=f"{match.group(value_group)} TWD_thousands",
                        scale="TWD_thousands",
                        period=_period(candidate),
                        fiscal_year=_int(candidate.get("fiscal_year")),
                        citation_span=citation,
                        source_specific_parser="tw_mops_product_sales_volume_value_table_parser_v0_1",
                    )
                )
    return rows


def _parse_quanta_notebook_shipments(
    text: str, *, ticker: str, candidate: Mapping[str, Any], generated_at: str
) -> list[dict[str, Any]]:
    if ticker != "2382.TW":
        return []
    match = re.search(
        r"筆記型電腦年出貨量達\s*(?P<value>[\d,.]+)\s*萬台",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return []
    value = _parse_number(match.group("value"))
    if value is None:
        return []
    return [
        _parsed_row(
            ticker=ticker,
            product_or_segment="notebook computers",
            product_node_type=PRODUCT_NODE_TYPE,
            metric_family="shipments",
            metric_name="notebook computer annual shipments",
            value=value * 10_000,
            unit="UNITS",
            raw_value_text=f"{match.group('value')} ten-thousand units",
            scale="ten_thousand_units",
            period=_period(candidate),
            fiscal_year=_int(candidate.get("fiscal_year")),
            citation_span=_citation(match.group(0)),
            source_specific_parser="tw_mops_quanta_notebook_shipment_sentence_parser_v0_1",
        )
    ]


def _parse_disco_shipment_value(
    text: str, *, ticker: str, candidate: Mapping[str, Any], generated_at: str
) -> list[dict[str, Any]]:
    if ticker != "6146.T":
        return []
    if not re.search(r"precision processing equipment.*?precision processing\s+tools", text, flags=re.IGNORECASE):
        return []
    match = re.search(r"Shipment value\s*[–-]\s*(?P<value>[\d,.]+)\s*billion yen", text, flags=re.IGNORECASE)
    if not match:
        return []
    value = _parse_number(match.group("value"))
    if value is None:
        return []
    return [
        _parsed_row(
            ticker=ticker,
            product_or_segment="precision processing equipment and tools",
            product_node_type=PRODUCT_NODE_TYPE,
            metric_family="shipment_value",
            metric_name="shipment value",
            value=value * 1_000_000_000,
            unit="JPY",
            raw_value_text=f"{match.group('value')} JPY_billions",
            scale="JPY_billions",
            period=_period(candidate),
            fiscal_year=_int(candidate.get("fiscal_year")),
            citation_span=_citation(
                "shipments of precision processing equipment and precision processing tools; " + match.group(0)
            ),
            source_specific_parser="jp_ir_disco_shipment_value_sentence_parser_v0_1",
        )
    ]


def _parse_lges_official_order_backlog(
    text: str, *, ticker: str, candidate: Mapping[str, Any], generated_at: str
) -> list[dict[str, Any]]:
    if ticker != "373220.KS":
        return []
    rows: list[dict[str, Any]] = []
    ess_match = re.search(
        r"ESS battery order backlog to approximately\s*(?P<value>[\d,.]+)\s*GWh",
        text,
        flags=re.IGNORECASE,
    )
    if ess_match:
        value = _parse_number(ess_match.group("value"))
        if value is not None:
            rows.append(
                _parsed_row(
                    ticker=ticker,
                    product_or_segment="ESS batteries",
                    product_node_type=PRODUCT_NODE_TYPE,
                    metric_family="backlog_or_orders",
                    metric_name="ESS battery order backlog",
                    value=value,
                    unit="GWH",
                    raw_value_text=f"{ess_match.group('value')} GWh",
                    scale="GWh",
                    period=_period(candidate),
                    fiscal_year=_int(candidate.get("fiscal_year")),
                    citation_span=_citation(ess_match.group(0)),
                    source_specific_parser="official_company_news_lges_product_order_backlog_parser_v0_1",
                )
            )
    cylindrical_match = re.search(
        r"won\s*(?P<value>[\d,.]+)\s*GWh in new contracts for its 46-Series cylindrical batteries",
        text,
        flags=re.IGNORECASE,
    )
    if cylindrical_match:
        value = _parse_number(cylindrical_match.group("value"))
        if value is not None:
            rows.append(
                _parsed_row(
                    ticker=ticker,
                    product_or_segment="46-Series cylindrical batteries",
                    product_node_type=PRODUCT_NODE_TYPE,
                    metric_family="backlog_or_orders",
                    metric_name="new contracts",
                    value=value,
                    unit="GWH",
                    raw_value_text=f"{cylindrical_match.group('value')} GWh",
                    scale="GWh",
                    period=_period(candidate),
                    fiscal_year=_int(candidate.get("fiscal_year")),
                    citation_span=_citation(cylindrical_match.group(0)),
                    source_specific_parser="official_company_news_lges_product_order_backlog_parser_v0_1",
                )
            )
    return rows


def _parse_tokyo_electron_segment_sales(
    text: str, *, ticker: str, candidate: Mapping[str, Any], generated_at: str
) -> list[dict[str, Any]]:
    if ticker != "8035.T":
        return []
    rows: list[dict[str, Any]] = []
    data_window = _window_after(text, "Semiconductor production equipment", 1600)
    if not data_window:
        return []
    match = re.search(
        r"Semiconductor production equipment\s+(?P<values>(?:[\d,]+\s+){2,8})",
        data_window,
        flags=re.IGNORECASE,
    )
    if match:
        values = [_parse_number(token) for token in re.findall(r"[\d,]+", match.group("values"))]
        values = [value for value in values if value is not None]
        # When a USD translation column is present, the first JPY current-year value is the second value.
        value = values[1] if len(values) >= 2 and "Thousands of U.S. dollars" in _window_before(text, match.start(), 500) else values[0]
        rows.append(
            _parsed_row(
                ticker=ticker,
                product_or_segment="Semiconductor production equipment",
                product_node_type=PRODUCT_NODE_TYPE,
                metric_family="product_revenue",
                metric_name="product net sales",
                value=value * 1_000_000,
                unit="JPY",
                raw_value_text=f"{value:g} JPY_millions",
                scale="JPY_millions",
                period=_period(candidate),
                fiscal_year=_int(candidate.get("fiscal_year")),
                citation_span=_citation(match.group(0)),
                source_specific_parser="jp_ir_tokyo_electron_product_net_sales_table_parser_v0_1",
            )
        )
    fpd_match = re.search(r"(FPD|Flat Panel Display).*?\s(?P<value>[\d,]+)\s+[\d,]+", data_window, flags=re.IGNORECASE)
    if fpd_match:
        value = _parse_number(fpd_match.group("value"))
        if value is not None:
            rows.append(
                _parsed_row(
                    ticker=ticker,
                    product_or_segment="FPD production equipment",
                    product_node_type=PRODUCT_NODE_TYPE,
                    metric_family="product_revenue",
                    metric_name="product net sales",
                    value=value * 1_000_000,
                    unit="JPY",
                    raw_value_text=f"{value:g} JPY_millions",
                    scale="JPY_millions",
                    period=_period(candidate),
                    fiscal_year=_int(candidate.get("fiscal_year")),
                    citation_span=_citation(fpd_match.group(0)),
                    source_specific_parser="jp_ir_tokyo_electron_product_net_sales_table_parser_v0_1",
                )
            )
    return rows


def _parsed_row(
    *,
    ticker: str,
    product_or_segment: str,
    product_node_type: str,
    metric_family: str,
    metric_name: str,
    value: float,
    unit: str,
    raw_value_text: str,
    scale: str,
    period: str,
    fiscal_year: int,
    citation_span: str,
    source_specific_parser: str,
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "product_or_segment": product_or_segment,
        "product_family": product_or_segment,
        "product_node_type": product_node_type,
        "metric_family": metric_family,
        "metric_name": metric_name,
        "canonical_metric_id": f"product_kpi:{metric_family}",
        "value": float(value),
        "unit": unit,
        "raw_value_text": raw_value_text,
        "scale": scale,
        "period": period,
        "fiscal_year": fiscal_year,
        "citation_span": citation_span,
        "source_specific_parser": source_specific_parser,
    }


def _runtime_row(
    parsed: Mapping[str, Any],
    *,
    candidate: Mapping[str, Any],
    company_by_ticker: Mapping[str, Mapping[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    ticker = _ticker(parsed)
    product = str(parsed.get("product_or_segment") or "")
    metric_family = str(parsed.get("metric_family") or "")
    value = parsed.get("value")
    source_url = str(candidate.get("source_url") or candidate.get("document_url") or "")
    evidence_ref = _stable_ref(
        "non_us_product_kpi_l1",
        [ticker, source_url, parsed.get("source_specific_parser"), product, metric_family, parsed.get("period"), value],
    )
    boundary = (
        "Non-US local exchange/company IR disclosure exact row; supports only the disclosed product or business segment, "
        "metric, period, unit, value, and cited span. It does not prove market share, sell-through, channel inventory, "
        "undisclosed SKU economics, or commercial tracker estimates."
    )
    text = (
        f"{ticker} {product} {parsed.get('metric_name')} was {value:g} {parsed.get('unit')} "
        f"for {parsed.get('period')} according to non-US official/local disclosure."
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "snapshot_id": evidence_ref,
        "source_id": "company_reported_product_operating_metrics",
        "underlying_source_id": "non_us_local_disclosure_product_kpi",
        "source_class": "non_us_local_exchange_or_ir_product_kpi",
        "source_family": "company_product_evidence_graph",
        "runtime_source_family": "company_product_evidence_graph",
        "source_layer_id": "L1",
        "source_layer": "L1",
        "layer_id": "L1",
        "source_specific_parser": parsed.get("source_specific_parser"),
        "source_specific_resolver": "non_us_local_exchange_company_ir_disclosure_resolver_v0_1",
        "parser_status": "value_unit_period_product_citation_parser_pass",
        "structured_fact_status": "exact_fact_materialized",
        "runtime_ready_context": True,
        "bounded_structured_context": True,
        "evidence_graph_status": "exact_authority_ready",
        "exact_value_authority": True,
        "can_support_company_exact_fact": True,
        "promotion_status": "runtime_fact_allowed",
        "ticker": ticker,
        "company": candidate.get("company_name") or company_by_ticker.get(ticker, {}).get("company_name") or ticker,
        "company_name": candidate.get("company_name") or company_by_ticker.get(ticker, {}).get("company_name") or ticker,
        "source_url": source_url,
        "snapshot_url": source_url,
        "source_title": candidate.get("source_title") or candidate.get("report_type") or "non-US official disclosure",
        "source_document_id": candidate.get("document_path") or candidate.get("cleaned_text_path") or "",
        "source_cleaned_text_path": candidate.get("cleaned_text_path") or "",
        "filing_type": candidate.get("report_type") or "non_us_official_disclosure",
        "period": parsed.get("period"),
        "fiscal_year": parsed.get("fiscal_year"),
        "statement_or_section": "product_or_segment_operating_metric",
        "product_or_segment": product,
        "product_family": product,
        "product_node_type": parsed.get("product_node_type") or "",
        "metric_family": metric_family,
        "metric_name": parsed.get("metric_name"),
        "canonical_metric_id": parsed.get("canonical_metric_id"),
        "value": value,
        "unit": parsed.get("unit"),
        "raw_value_text": parsed.get("raw_value_text"),
        "scale": parsed.get("scale"),
        "citation_span": parsed.get("citation_span"),
        "citation": {"url": source_url, "source_url": source_url, "title": candidate.get("source_title") or "", "span": parsed.get("citation_span")},
        "allowed_claims": ["company_disclosed_product_kpi", metric_family],
        "claim_types": ["company_disclosed_product_kpi", "company_reported_product_operating_fact"],
        "forbidden_claims": [
            "market_share",
            "channel_inventory",
            "sell_through",
            "undisclosed_sku_economics",
            "commercial_tracker_estimate",
        ],
        "authority_boundary": boundary,
        "claim_boundary": boundary,
        "runtime_use_boundary": boundary,
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "counterparty_binding_status": "not_bound",
        "entity_binding": {
            "schema_version": "finsight_public_web_entity_binding_v0_1",
            "issuer_ticker": ticker,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "product_mentioned_in_snapshot",
            "counterparty_binding_status": "not_bound",
            "product_matched_terms": [product],
            "source_entity_role": "non_us_company_disclosed_product_metric",
            "binding_claim_boundary": boundary,
        },
        "text": text,
        "preview": text,
        "as_of_datetime": generated_at,
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
    output_report: Path,
) -> dict[str, Any]:
    row_tickers = {_ticker(row) for row in rows if _ticker(row)}
    candidate_tickers = {_ticker(row) for row in candidates if _ticker(row)}
    rejection_reason_counts = Counter(str(row.get("rejection_reason") or "") for row in rejections)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows and not rejection_reason_counts.get("unclassified") else "gap",
        "target_ticker_count": len(target_tickers),
        "candidate_count": len(candidates),
        "candidate_ticker_count": len(candidate_tickers),
        "runtime_row_count": len(rows),
        "runtime_ticker_count": len(row_tickers),
        "covered_target_ticker_count": len(target_tickers & row_tickers),
        "uncovered_target_ticker_count": len(target_tickers - row_tickers),
        "uncovered_target_tickers": sorted(target_tickers - row_tickers),
        "metric_family_counts": dict(sorted(Counter(str(row.get("metric_family") or "") for row in rows).items())),
        "product_node_type_counts": dict(sorted(Counter(str(row.get("product_node_type") or "") for row in rows).items())),
        "source_specific_parser_counts": dict(sorted(Counter(str(row.get("source_specific_parser") or "") for row in rows).items())),
        "rejection_count": len(rejections),
        "rejection_reason_counts": dict(sorted(rejection_reason_counts.items())),
        "unclassified_rejection_count": rejection_reason_counts.get("unclassified", 0),
        "outputs": {
            "rows": str(output_rows),
            "rejections": str(output_rejections),
            "report": str(output_report),
        },
        "claim_boundary": (
            "Rows are L1 company/local-exchange disclosed exact product or segment metrics. Percentage-only, region-only, "
            "stale document, and text-only product descriptions remain rejected attempts."
        ),
    }


def render_report(summary: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# Non-US Product-KPI Local Disclosure Runtime Rows",
            "",
            f"- Generated at: `{summary.get('generated_at')}`",
            f"- Status: `{summary.get('status')}`",
            f"- Target tickers: `{summary.get('target_ticker_count')}`",
            f"- Runtime rows: `{summary.get('runtime_row_count')}`",
            f"- Runtime ticker coverage: `{summary.get('covered_target_ticker_count')}/{summary.get('target_ticker_count')}`",
            f"- Metric families: `{json.dumps(summary.get('metric_family_counts'), ensure_ascii=False, sort_keys=True)}`",
            f"- Product node types: `{json.dumps(summary.get('product_node_type_counts'), ensure_ascii=False, sort_keys=True)}`",
            f"- Parser counts: `{json.dumps(summary.get('source_specific_parser_counts'), ensure_ascii=False, sort_keys=True)}`",
            f"- Rejection reasons: `{json.dumps(summary.get('rejection_reason_counts'), ensure_ascii=False, sort_keys=True)}`",
            f"- Uncovered tickers: `{json.dumps(summary.get('uncovered_target_tickers'), ensure_ascii=False)}`",
            "",
            "## Boundary",
            "",
            str(summary.get("claim_boundary") or ""),
            "",
        ]
    )


def _manual_official_report_candidate(
    *,
    ticker: str,
    report: Mapping[str, Any],
    company_by_ticker: Mapping[str, Mapping[str, Any]],
    raw_dir: Path,
    processed_dir: Path,
    generated_at: str,
    download: bool,
    timeout_s: float,
) -> dict[str, Any]:
    url = str(report.get("document_url") or "")
    suffix = ".pdf" if ".pdf" in url.lower() else ".html"
    digest = _stable_digest(url)
    raw_path = raw_dir / _safe_ticker(ticker) / f"{digest}{suffix}"
    clean_path = processed_dir / _safe_ticker(ticker) / f"{digest}_cleaned_text.txt"
    if clean_path.exists():
        return _manual_candidate_row(ticker, report, company_by_ticker, raw_path, clean_path, generated_at)
    if not download:
        return {
            "ticker": ticker,
            "company_name": company_by_ticker.get(ticker, {}).get("company_name") or ticker,
            "document_url": url,
            "source_url": url,
            "source_title": report.get("source_title") or "official disclosure",
            "report_type": report.get("report_type") or "official_report",
            "fiscal_year": report.get("fiscal_year") or 0,
            "candidate_source": "manual_official_report_not_downloaded",
            "generated_at": generated_at,
        }
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
        return _manual_candidate_row(ticker, report, company_by_ticker, raw_path, clean_path, generated_at)
    except Exception as exc:  # noqa: BLE001
        return {
            "ticker": ticker,
            "company_name": company_by_ticker.get(ticker, {}).get("company_name") or ticker,
            "document_url": url,
            "source_url": url,
            "source_title": report.get("source_title") or "official disclosure",
            "report_type": report.get("report_type") or "official_report",
            "fiscal_year": report.get("fiscal_year") or 0,
            "candidate_source": "manual_official_report_download_failed",
            "download_error": f"{type(exc).__name__}:{str(exc)[:220]}",
            "generated_at": generated_at,
        }


def _manual_candidate_row(
    ticker: str,
    report: Mapping[str, Any],
    company_by_ticker: Mapping[str, Mapping[str, Any]],
    raw_path: Path,
    clean_path: Path,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "company_name": company_by_ticker.get(ticker, {}).get("company_name") or ticker,
        "cleaned_text_path": str(clean_path),
        "document_path": str(raw_path),
        "document_url": report.get("document_url") or "",
        "source_url": report.get("document_url") or "",
        "source_title": report.get("source_title") or "official disclosure",
        "source_profile": "company_ir_reports",
        "report_type": report.get("report_type") or "official_report",
        "fiscal_year": report.get("fiscal_year") or 0,
        "candidate_source": "manual_official_report_download_or_cache",
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

    def close(self) -> None:
        self._flush()
        super().close()

    def _flush(self) -> None:
        if not self._current:
            return
        value = " ".join(self._current).strip()
        if value:
            self.blocks.append(value)
        self._current = []


def _no_parse_reason(text: str) -> str:
    if re.search(r"營業比重|매출액 비중|Sales by Region|銷售.*比重", text, flags=re.IGNORECASE):
        return "percentage_or_mix_only_no_exact_product_value"
    if re.search(r"分地区|地域|region|geographic|domestic|overseas", text, flags=re.IGNORECASE):
        return "geographic_or_region_only_no_product_kpi"
    if re.search(r"主要產品|주요제품|product|segment|business", text, flags=re.IGNORECASE):
        return "product_or_segment_description_without_exact_value_row"
    return "no_product_kpi_exact_table_pattern"


def _stale_document_reason(text: str, candidate: Mapping[str, Any]) -> str:
    fiscal_year = _int(candidate.get("fiscal_year"))
    if not fiscal_year:
        return ""
    title_match = re.search(r"(?:Integrated Report|Annual Report)\s+(20\d{2})", text, flags=re.IGNORECASE)
    if not title_match:
        return ""
    doc_year = _int(title_match.group(1))
    if doc_year and doc_year < fiscal_year - 1:
        return "stale_document_year_mismatch"
    return ""


def _rejection(ticker: str, reason: str, row: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": REJECTION_SCHEMA_VERSION,
        "generated_at": generated_at,
        "ticker": ticker,
        "rejection_reason": reason or "unclassified",
        "source_url": row.get("source_url") or row.get("document_url") or "",
        "source_title": row.get("source_title") or "",
        "cleaned_text_path": row.get("cleaned_text_path") or "",
        "report_type": row.get("report_type") or "",
        "fiscal_year": row.get("fiscal_year") or 0,
        "candidate_source": row.get("candidate_source") or "",
        "download_error": row.get("download_error") or "",
        "claim_boundary": "Rejected non-US Product-KPI parser attempt; not exact-slot evidence.",
    }


def _target_tickers(explicit_tickers: list[str], docket_path: Path) -> set[str]:
    if explicit_tickers:
        return {ticker.strip().upper() for ticker in explicit_tickers if ticker.strip()}
    rows = _load_jsonl(docket_path)
    targets = {
        str(row.get("ticker") or "").upper()
        for row in rows
        if row.get("cluster_id") == DOCKET_CLUSTER_ID and row.get("ticker")
    }
    return targets or set(FALLBACK_TARGET_TICKERS)


def _company_index(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = _ticker(row)
        if ticker:
            out[ticker] = dict(row)
    return out


def _candidate_sort_key(row: Mapping[str, Any]) -> tuple[int, int, int, str]:
    report_type = str(row.get("report_type") or "").lower()
    priority = 3 if "annual" in report_type else 2 if "integrated" in report_type else 1
    source_priority = 2 if row.get("cleaned_text_path") else 1
    return (_int(row.get("fiscal_year")), priority, source_priority, str(row.get("source_url") or ""))


def _runtime_row_rank(row: Mapping[str, Any]) -> tuple[int, int, int, str]:
    node_rank = 2 if row.get("product_node_type") == PRODUCT_NODE_TYPE else 1
    family_rank = 2 if row.get("metric_family") in {"product_revenue", "segment_revenue", "segment_sales"} else 1
    return (_int(row.get("fiscal_year")), node_rank, family_rank, str(row.get("evidence_ref") or ""))


def _dedupe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("evidence_ref") or row.get("evidence_id") or "")
        if not key:
            key = _stable_ref(
                "non_us_product_kpi_l1",
                [row.get("ticker"), row.get("source_url"), row.get("product_or_segment"), row.get("metric_name"), row.get("period"), row.get("value")],
            )
        out.setdefault(key, dict(row))
    return list(out.values())


def _dedupe_parsed_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = "|".join(
            str(row.get(part) or "")
            for part in ("ticker", "product_or_segment", "metric_family", "metric_name", "period", "value", "unit")
        )
        out.setdefault(key, dict(row))
    return list(out.values())


def _period(candidate: Mapping[str, Any]) -> str:
    fiscal_year = _int(candidate.get("fiscal_year"))
    return f"FY{fiscal_year}" if fiscal_year else "FY_UNKNOWN"


def _between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        return ""
    end = text.find(end_marker, start + len(start_marker))
    if end < 0:
        return text[start : start + 3000]
    return text[start:end]


def _window_after(text: str, marker: str, length: int) -> str:
    start = text.lower().find(marker.lower())
    if start < 0:
        return ""
    return text[start : start + length]


def _window_before(text: str, position: int, length: int) -> str:
    return text[max(0, position - length) : position]


def _citation(text: str, max_len: int = 520) -> str:
    return re.sub(r"\s+", " ", text).strip()[:max_len]


def _parse_number(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    negative = text.startswith("△") or (text.startswith("(") and text.endswith(")"))
    cleaned = text.replace("△", "").replace(",", "").replace("(", "").replace(")", "").replace("%", "").strip()
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return -number if negative else number


def _normalize_text(text: str) -> str:
    text = html.unescape(text or "")
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def _ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or row.get("issuer_ticker") or "").strip().upper()


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
