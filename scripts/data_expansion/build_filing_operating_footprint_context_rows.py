"""Project strict operating-footprint rows from annual filing text.

This parser fills CustomerDeployment depth only for issuer-disclosed operating
facts that are not ordinary financial statement rows: customer counts,
production volume, and shipments. It intentionally does not promote revenue,
margin, cash-flow, or generic segment totals.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.layer_acceptance_gates import load_jsonl  # noqa: E402


SCHEMA_VERSION = "finsight_filing_operating_footprint_context_row_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_filing_operating_footprint_context_summary_v0_1"

MANIFEST_DIR = REPO_ROOT / "data" / "manifests"
DEFAULT_DEPTH_MATRIX = MANIFEST_DIR / "second_third_layer_depth_parity_matrix_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = MANIFEST_DIR / "filing_operating_footprint_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_REJECTIONS = MANIFEST_DIR / "filing_operating_footprint_context_rejections_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = MANIFEST_DIR / "filing_operating_footprint_context_summary_v0_1.json"

SOURCE_ID = "sec_or_fpi_annual_operating_footprint_filing"
OUTPUT_SOURCE_FILE = DEFAULT_OUTPUT_ROWS.name

DEFAULT_SEARCH_ROOTS = [
    REPO_ROOT / "data" / "raw_private" / "sec_tier1_sp500_annual",
    REPO_ROOT / "data" / "raw_private" / "sec_tier2_supply_chain_annual",
    REPO_ROOT / "data" / "raw_private" / "sec",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build strict filing operating-footprint context rows.")
    parser.add_argument("--depth-matrix", type=Path, default=DEFAULT_DEPTH_MATRIX)
    parser.add_argument("--ticker", "--tickers", dest="tickers", action="append")
    parser.add_argument("--search-root", dest="search_roots", type=Path, action="append")
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-rejections", type=Path, default=DEFAULT_OUTPUT_REJECTIONS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    target_tickers = _target_tickers(args.depth_matrix, args.tickers)
    documents = list(_load_filing_documents(target_tickers, args.search_roots or DEFAULT_SEARCH_ROOTS))
    result = build_filing_operating_footprint_context_rows(documents=documents, generated_at=generated_at)
    rows = result["rows"]
    rejections = result["rejections"]
    args.output_rows.parent.mkdir(parents=True, exist_ok=True)
    args.output_rows.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    args.output_rejections.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rejections),
        encoding="utf-8",
    )
    summary = _summary(
        rows=rows,
        rejections=rejections,
        target_tickers=target_tickers,
        documents=documents,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_rejections=args.output_rejections,
    )
    args.output_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if rows else 1


def build_filing_operating_footprint_context_rows(
    *,
    documents: Iterable[Mapping[str, Any]],
    generated_at: str,
) -> dict[str, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    for document in documents:
        ticker = str(document.get("ticker") or "").upper().strip()
        text = _normalize_html_text(str(document.get("html") or ""))
        parsed = _parse_document(document, text, generated_at=generated_at)
        if parsed:
            rows.extend(parsed)
        elif ticker:
            rejections.append(
                {
                    "schema_version": "finsight_filing_operating_footprint_context_rejection_v0_1",
                    "generated_at": generated_at,
                    "ticker": ticker,
                    "company": document.get("company") or "",
                    "raw_path": document.get("raw_path") or "",
                    "source_url": document.get("source_url") or "",
                    "rejection_reason": "no_strict_customer_or_operating_footprint_row_found",
                    "parser_scope": "customer_count_or_production_or_shipment_only",
                }
            )
    return {"rows": sorted(rows, key=lambda row: (row["ticker"], row["metric_family"], row["product_or_segment"])), "rejections": rejections}


def _parse_document(document: Mapping[str, Any], text: str, *, generated_at: str) -> list[dict[str, Any]]:
    ticker = str(document.get("ticker") or "").upper().strip()
    if ticker == "LNT":
        return _parse_lnt_customer_counts(document, text, generated_at=generated_at)
    if ticker == "STLD":
        return _parse_stld_production_shipments(document, text, generated_at=generated_at)
    if ticker == "BHP":
        return _parse_bhp_production_table(document, text, generated_at=generated_at)
    return []


def _parse_lnt_customer_counts(document: Mapping[str, Any], text: str, *, generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pattern = re.compile(
        r"At December 31,\s*(?P<year>20\d{2}),\s*(?P<utility>IPL|WPL)\s+supplied electric and natural gas service "
        r"to approximately\s*(?P<electric>[\d,]+)\s+and\s*(?P<gas>[\d,]+)\s+retail customers, respectively, in\s*(?P<state>[^.]+)\.",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        utility = match.group("utility").upper()
        year = match.group("year")
        state = match.group("state").strip()
        for service, group_name in (("electric", "electric"), ("natural gas", "gas")):
            value = _number(match.group(group_name))
            rows.append(
                _runtime_row(
                    document,
                    generated_at=generated_at,
                    metric_family="customer_count",
                    source_role="customer_count",
                    metric_name=f"retail {service} customers",
                    product_or_segment=f"{utility} {service} utility service",
                    value=value,
                    unit="customers",
                    period=f"FY{year}",
                    raw_value_text=match.group(group_name),
                    citation_span=_clip(text, match.start(), match.end()),
                    source_specific_parser="sec_filing_utility_retail_customer_sentence_parser_v0_1",
                    claim_boundary=(
                        f"Annual filing customer-count row for {utility} {service} service in {state}; "
                        "supports only disclosed customer footprint, not revenue, rate base, demand growth, "
                        "market share, or customer wins."
                    ),
                )
            )
    return rows


def _parse_stld_production_shipments(document: Mapping[str, Any], text: str, *, generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    produced_match = re.search(
        r"We produced\s*(?P<value>[\d.]+)\s*million tons of sheet steel at these facilities in\s*(?P<year>20\d{2})",
        text,
        re.IGNORECASE,
    )
    if produced_match:
        rows.append(
            _runtime_row(
                document,
                generated_at=generated_at,
                metric_family="production_or_throughput",
                source_role="production_or_throughput",
                metric_name="sheet steel produced",
                product_or_segment="sheet steel operations",
                value=float(produced_match.group("value")) * 1_000_000,
                unit="tons",
                period=f"FY{produced_match.group('year')}",
                raw_value_text=f"{produced_match.group('value')} million tons",
                citation_span=_clip(text, produced_match.start(), produced_match.end() + 260),
                source_specific_parser="sec_filing_steel_production_sentence_parser_v0_1",
                claim_boundary=(
                    "Annual filing production-volume row for sheet steel operations; supports only disclosed "
                    "production/throughput footprint, not revenue, market share, pricing, or sell-through."
                ),
            )
        )
    shipments_match = re.search(
        r"We shipped the following volumes of sheet steel products \(net tons\):.*?"
        r"Butler, Columbus, and Sinton\s*(?P<butler>[\d,]+).*?"
        r"Steel Processing divisions\s*(?P<processing>[\d,]+)",
        text,
        re.IGNORECASE,
    )
    if shipments_match:
        for label, group_name in (
            ("Butler, Columbus, and Sinton sheet steel products", "butler"),
            ("Steel Processing divisions sheet steel products", "processing"),
        ):
            rows.append(
                _runtime_row(
                    document,
                    generated_at=generated_at,
                    metric_family="shipments",
                    source_role="shipments",
                    metric_name="sheet steel product shipments",
                    product_or_segment=label,
                    value=_number(shipments_match.group(group_name)),
                    unit="net tons",
                    period=f"FY{document.get('fiscal_year') or 2025}",
                    raw_value_text=shipments_match.group(group_name),
                    citation_span=_clip(text, shipments_match.start(), shipments_match.end()),
                    source_specific_parser="sec_filing_steel_shipment_table_text_parser_v0_1",
                    claim_boundary=(
                        f"Annual filing shipment-volume row for {label}; supports only disclosed net tons shipped, "
                        "not revenue, pricing, market share, or inventory."
                    ),
                )
            )
    return rows


def _parse_bhp_production_table(document: Mapping[str, Any], text: str, *, generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    table_patterns = [
        (
            "Total copper production (kt)",
            re.compile(r"Total copper production \(kt\)\s*(?P<current>[\d,]+)\s*(?P<prior>[\d,]+)", re.IGNORECASE),
            "copper",
            1_000.0,
            "tonnes",
            "bhp_20f_copper_production_table_parser_v0_1",
        ),
        (
            "Total iron ore production (Mt)",
            re.compile(r"Total iron ore production \(Mt\)\s*(?P<current>[\d,.]+)\s*(?P<prior>[\d,.]+)", re.IGNORECASE),
            "iron ore",
            1_000_000.0,
            "tonnes",
            "bhp_20f_iron_ore_production_table_parser_v0_1",
        ),
    ]
    for metric_label, pattern, product, multiplier, unit, parser_name in table_patterns:
        match = pattern.search(text)
        if not match:
            continue
        rows.append(
            _runtime_row(
                document,
                generated_at=generated_at,
                metric_family="production_or_throughput",
                source_role="production_or_throughput",
                metric_name=metric_label,
                product_or_segment=product,
                value=_number(match.group("current")) * multiplier,
                unit=unit,
                period=f"FY{document.get('fiscal_year') or 2025}",
                raw_value_text=match.group("current"),
                citation_span=_clip(text, match.start() - 160, match.end() + 180),
                source_specific_parser=parser_name,
                claim_boundary=(
                    f"20-F operating production row for {product}; supports only disclosed production volume, "
                    "not revenue, realized price, market share, customer demand, or sales mix."
                ),
            )
        )
    return rows


def _runtime_row(
    document: Mapping[str, Any],
    *,
    generated_at: str,
    metric_family: str,
    source_role: str,
    metric_name: str,
    product_or_segment: str,
    value: float,
    unit: str,
    period: str,
    raw_value_text: str,
    citation_span: str,
    source_specific_parser: str,
    claim_boundary: str,
) -> dict[str, Any]:
    ticker = str(document.get("ticker") or "").upper().strip()
    evidence_id = _evidence_id(ticker, metric_family, product_or_segment, period, raw_value_text)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "ticker": ticker,
        "company": document.get("company") or "",
        "evidence_id": evidence_id,
        "evidence_ref": evidence_id,
        "source_id": SOURCE_ID,
        "source_role": source_role,
        "source_layer": "L1",
        "source_class": "primary_filing_operating_footprint",
        "source_url": document.get("source_url") or "",
        "raw_path": document.get("raw_path") or "",
        "source_title": document.get("form_type") or "",
        "filing_type": document.get("form_type") or "",
        "fiscal_year": document.get("fiscal_year"),
        "period": period,
        "metric_family": metric_family,
        "metric_name": metric_name,
        "product_or_segment": product_or_segment,
        "product_family": product_or_segment,
        "value": value,
        "unit": unit,
        "raw_value_text": raw_value_text,
        "citation": {
            "source_url": document.get("source_url") or "",
            "span": citation_span,
            "title": document.get("form_type") or "",
        },
        "citation_span": citation_span,
        "claim_boundary": claim_boundary,
        "authority_boundary": claim_boundary,
        "allowed_claims": ["company_disclosed_industry_operating_metric", source_role],
        "claim_types": ["company_disclosed_industry_operating_metric", "company_reported_product_operating_fact"],
        "forbidden_claims": ["revenue", "market_share", "sell_through", "channel_inventory", "ASP", "customer_order_value"],
        "parser_status": "value_unit_period_product_citation_parser_pass",
        "structured_fact_status": "exact_fact_materialized",
        "promotion_status": "runtime_fact_allowed",
        "evidence_graph_status": "exact_authority_ready",
        "source_specific_parser": source_specific_parser,
        "source_specific_resolver": "local_primary_filing_operating_footprint_resolver_v0_1",
        "runtime_ready_context": True,
        "bounded_structured_context": True,
        "exact_value_authority": True,
        "can_support_company_exact_fact": True,
        "runtime_use_boundary": claim_boundary,
        "preview": f"{ticker} {product_or_segment} {metric_name} was {value:g} {unit} for {period}.",
    }


def _load_filing_documents(tickers: set[str], search_roots: list[Path]) -> Iterable[dict[str, Any]]:
    seen: set[str] = set()
    for ticker in sorted(tickers):
        for root in search_roots:
            if not root.exists():
                continue
            for html_path in sorted(root.glob(f"**/{ticker}/*.html")):
                key = str(html_path.resolve()).lower()
                if key in seen:
                    continue
                metadata_path = html_path.with_suffix(".metadata.json")
                if not metadata_path.exists():
                    metadata_path = html_path.with_name(f"{html_path.stem}.metadata.json")
                metadata = _load_metadata(metadata_path)
                fiscal_year = int(metadata.get("fiscal_year") or metadata.get("requested_fiscal_year") or 0)
                if fiscal_year and fiscal_year < 2025:
                    continue
                seen.add(key)
                yield {
                    "ticker": ticker,
                    "company": metadata.get("company") or "",
                    "form_type": metadata.get("form_type") or html_path.stem,
                    "fiscal_year": fiscal_year or None,
                    "source_url": metadata.get("filing_url") or "",
                    "raw_path": str(html_path),
                    "html": html_path.read_text(encoding="utf-8", errors="ignore"),
                }
                break


def _load_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _target_tickers(depth_matrix: Path, tickers: list[str] | None) -> set[str]:
    if tickers:
        return {ticker.upper().strip() for group in tickers for ticker in re.split(r"[\s,]+", group) if ticker.strip()}
    targets: set[str] = set()
    for row in load_jsonl(depth_matrix):
        dimension = ((row.get("dimensions") or {}).get("customer_deployment_depth") or {})
        if dimension.get("target_depth_met"):
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        if ticker:
            targets.add(ticker)
    return targets


def _normalize_html_text(raw_html: str) -> str:
    try:
        from bs4 import BeautifulSoup

        text = BeautifulSoup(raw_html, "html.parser").get_text(" ")
    except Exception:
        text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    text = text.replace("\u200b", " ")
    return re.sub(r"\s+", " ", text).strip()


def _clip(text: str, start: int, end: int, *, before: int = 100, after: int = 180) -> str:
    left = max(0, start - before)
    right = min(len(text), end + after)
    return text[left:right].strip()


def _number(value: str) -> float:
    return float(value.replace(",", "").strip())


def _evidence_id(ticker: str, metric_family: str, product_or_segment: str, period: str, raw_value_text: str) -> str:
    digest = hashlib.sha1(
        f"{ticker}|{metric_family}|{product_or_segment}|{period}|{raw_value_text}".encode("utf-8")
    ).hexdigest()[:16]
    return f"filing_operating_footprint:{digest}"


def _summary(
    *,
    rows: list[Mapping[str, Any]],
    rejections: list[Mapping[str, Any]],
    target_tickers: set[str],
    documents: list[Mapping[str, Any]],
    generated_at: str,
    output_rows: Path,
    output_rejections: Path,
) -> dict[str, Any]:
    row_tickers = sorted({str(row.get("ticker") or "") for row in rows if row.get("ticker")})
    document_tickers = sorted({str(row.get("ticker") or "") for row in documents if row.get("ticker")})
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "fail",
        "target_ticker_count": len(target_tickers),
        "document_ticker_count": len(document_tickers),
        "runtime_row_count": len(rows),
        "runtime_ticker_count": len(row_tickers),
        "runtime_tickers": row_tickers,
        "missing_target_tickers": sorted(target_tickers - set(row_tickers)),
        "rejection_count": len(rejections),
        "outputs": {
            "rows": str(output_rows),
            "rejections": str(output_rejections),
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
