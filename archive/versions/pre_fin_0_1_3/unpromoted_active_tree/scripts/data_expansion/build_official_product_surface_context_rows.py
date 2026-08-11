from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.public_web_context_parser import parse_public_web_context_rows  # noqa: E402
from sec_agent.source_coverage_gate import build_source_coverage_gate  # noqa: E402


SCHEMA_VERSION = "fin_agent_official_product_surface_context_rows_v0_1"
SUMMARY_SCHEMA_VERSION = "fin_agent_official_product_surface_context_rows_summary_v0_1"

DEFAULT_INPUT = Path("Z:/FIN_Insight_Agent_data/processed_private/public_source_extended_materialization/company_product_pages/company_product_pages.materialized.jsonl")
DEFAULT_SOURCE_LAYER_ROWS = REPO_ROOT / "data" / "manifests" / "source_layer_capability_audit_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "official_product_surface_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "official_product_surface_context_rows_summary_v0_1.json"
DEFAULT_OUTPUT_COVERAGE = REPO_ROOT / "data" / "manifests" / "official_product_surface_runtime_coverage_gate_v0_1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert materialized company product pages into bounded official product surface context rows.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--source-layer-rows", type=Path, default=DEFAULT_SOURCE_LAYER_ROWS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-coverage-gate", type=Path, default=DEFAULT_OUTPUT_COVERAGE)
    parser.add_argument("--max-rows-per-page", type=int, default=12)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if no parser-backed rows are produced.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    page_rows = _load_jsonl(args.input)
    context_rows = build_official_product_surface_context_rows(
        page_rows,
        generated_at=generated_at,
        max_rows_per_page=args.max_rows_per_page,
    )
    source_layer_rows = _load_jsonl(args.source_layer_rows)
    visible_rows = {
        "product_technology_analyst": context_rows,
        "fundamental_analyst": [row for row in context_rows if row.get("source_layer_id") == "L1"],
    }
    coverage_gate = build_source_coverage_gate(
        industry_schema="generic_public_research",
        phase="runtime_case",
        case_id="official_product_surface_context_backfill_smoke",
        source_layer_capability={"rows": source_layer_rows},
        observed_rows=context_rows,
        specialist_visible_rows=visible_rows,
        required_dimensions=["product_and_production"],
        generated_at=generated_at,
    )
    summary = build_summary(
        page_rows=page_rows,
        context_rows=context_rows,
        coverage_gate=coverage_gate,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_coverage=args.output_coverage_gate,
    )
    _write_jsonl(args.output_rows, context_rows)
    _write_json(args.output_summary, summary)
    _write_json(args.output_coverage_gate, coverage_gate)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["parser_backed_row_count"] <= 0:
        return 1
    return 0


def build_official_product_surface_context_rows(
    page_rows: Iterable[Mapping[str, Any]],
    *,
    generated_at: str,
    max_rows_per_page: int = 12,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in page_rows:
        row = dict(page)
        ticker = str(row.get("ticker") or "").strip().upper()
        url = str(row.get("source_url") or row.get("url") or "").strip()
        raw_path = Path(str(row.get("raw_path") or ""))
        clean_path = Path(str(row.get("clean_text_path") or ""))
        body, content_type = _page_body(raw_path=raw_path, clean_path=clean_path)
        if not body.strip() or not ticker or not url:
            continue
        product = str(row.get("product") or "").strip()
        company = str(row.get("company") or "").strip()
        title = str(row.get("title") or product or company or ticker).strip()
        domain = _domain(url)
        parent_ref = _stable_ref("official_product_surface", [ticker, url, product])
        repair = {
            "repair_id": f"official_product_surface_backfill:{ticker.lower()}:{_slug(product or domain)}",
            "repair_type": "product_surface",
            "ticker": ticker,
            "issuer_name": company,
            "company_name": company,
            "company_domains": [domain] if domain else [],
            "official_product_surfaces": [product] if product else [],
            "product_terms": [product] if product else [],
            "official_metric_leads": ["product taxonomy", "product specification", "launch/availability context"],
        }
        parsed = parse_public_web_context_rows(
            ticker=ticker,
            parent_evidence_ref=parent_ref,
            url=url,
            source_class="company_product_page",
            repair_type="product_surface",
            analysis_dimension="product_and_production",
            title=title,
            body=body,
            content_type=content_type,
            as_of_datetime=generated_at,
            citation={"url": url, "title": title},
            source_layer_meta={
                "source_id": "company_product_pages",
                "source_layer_id": "L2",
                "source_layer": "L2",
                "layer_id": "L2",
                "parser_status": "official_product_surface_parser_pass",
                "structured_fact_status": "bounded_context_fact_materialized",
                "evidence_graph_status": "runtime_ready_context",
                "runtime_ready_context": True,
                "can_support_company_exact_fact": False,
            },
            claim_boundary="official product surface context only; no sales, share, ASP, inventory, or product KPI authority",
            authority_boundary="company official product surface; context only until exact product KPI parser/citation gate passes",
            repair=repair,
            max_rows=max_rows_per_page,
        )
        for parsed_row in parsed:
            parsed_row["schema_version"] = SCHEMA_VERSION
            parsed_row["source_id"] = "company_product_pages"
            parsed_row["underlying_source_id"] = "company_product_pages"
            parsed_row["source_family"] = "live_public_web_context"
            parsed_row["runtime_source_family"] = "public_source_context"
            parsed_row["materialized_source_row_ref"] = parent_ref
            parsed_row["company"] = company
            parsed_row["as_of_datetime"] = generated_at
            parsed_row["context_only"] = True
            parsed_row["exact_value_authority"] = False
            parsed_row["allowed_claims"] = ["official_product_surface", "product_taxonomy_context", "product_spec_context"]
            parsed_row["forbidden_claims"] = ["company_sales", "market_share", "product_revenue", "ASP", "inventory", "sell_through"]
            out.append(parsed_row)
    return out


def build_summary(
    *,
    page_rows: list[dict[str, Any]],
    context_rows: list[dict[str, Any]],
    coverage_gate: Mapping[str, Any],
    generated_at: str,
    output_rows: Path,
    output_coverage: Path,
) -> dict[str, Any]:
    parser_rows = [row for row in context_rows if row.get("bounded_structured_context") or row.get("structured_context_type")]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if parser_rows and coverage_gate.get("status") in {"pass", "gap"} else "gap",
        "input_page_count": len(page_rows),
        "context_row_count": len(context_rows),
        "parser_backed_row_count": len(parser_rows),
        "ticker_count": len({str(row.get("ticker") or "") for row in context_rows if str(row.get("ticker") or "")}),
        "tickers": sorted({str(row.get("ticker") or "") for row in context_rows if str(row.get("ticker") or "")}),
        "structured_context_types": sorted({str(row.get("structured_context_type") or "") for row in parser_rows if str(row.get("structured_context_type") or "")}),
        "coverage_gate_status": str(coverage_gate.get("status") or ""),
        "official_product_surface_requirement": _requirement_summary(coverage_gate, "official_product_surface"),
        "outputs": {
            "rows": str(output_rows),
            "coverage_gate": str(output_coverage),
        },
        "boundary": "Official product page rows are bounded product taxonomy/spec context only; not product sales, share, ASP, inventory, sell-through, or product KPI authority.",
    }


def _requirement_summary(payload: Mapping[str, Any], requirement_id: str) -> dict[str, Any]:
    for row in payload.get("requirements") or []:
        if isinstance(row, Mapping) and str(row.get("requirement_id") or "") == requirement_id:
            return {
                "status": str(row.get("status") or ""),
                "observed_row_count": int(row.get("observed_row_count") or 0),
                "parser_row_count": int(row.get("parser_row_count") or 0),
                "entity_bound_row_count": int(row.get("entity_bound_row_count") or 0),
                "specialist_visible_row_count": int(row.get("specialist_visible_row_count") or 0),
                "gaps": list(row.get("gaps") or []),
            }
    return {}


def _page_body(*, raw_path: Path, clean_path: Path) -> tuple[str, str]:
    if raw_path.exists():
        return raw_path.read_text(encoding="utf-8", errors="replace"), "text/html"
    if clean_path.exists():
        return clean_path.read_text(encoding="utf-8", errors="replace"), "text/plain"
    return "", "text/plain"


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
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _stable_ref(prefix: str, parts: Iterable[str]) -> str:
    digest = hashlib.sha1("|".join(str(part or "") for part in parts).encode("utf-8", errors="ignore")).hexdigest()[:14]
    return f"{prefix}:{digest}"


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _slug(value: str) -> str:
    text = "".join(ch.lower() if ch.isalnum() else "_" for ch in value or "")
    return "_".join(part for part in text.split("_") if part)[:48] or "product"


if __name__ == "__main__":
    raise SystemExit(main())
