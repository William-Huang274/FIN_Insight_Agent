from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.product_family_source_routes import load_jsonl_rows  # noqa: E402


SCHEMA_VERSION = "finsight_sec_product_taxonomy_context_rows_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_sec_product_taxonomy_context_summary_v0_1"

DEFAULT_INPUT = REPO_ROOT / "data/manifests/company_product_slots_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data/manifests/sec_product_taxonomy_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data/manifests/sec_product_taxonomy_context_summary_v0_1.json"

GENERIC_PRODUCT_LABEL_PATTERNS = (
    "annual report",
    "business model",
    "corporate history",
    "customers choice",
    "customers and consumers",
    "durable and resilient",
    "government regulation",
    "product design and development",
    "sourcing and manufacturing",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project SEC-derived company product slots into L1 product taxonomy context rows.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    slot_rows = load_jsonl_rows(args.input)
    rows = build_sec_product_taxonomy_context_rows(slot_rows, generated_at=generated_at)
    summary = build_summary(slot_rows=slot_rows, rows=rows, generated_at=generated_at)
    _write_jsonl(args.output_rows, rows)
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and not rows:
        return 1
    return 0


def build_sec_product_taxonomy_context_rows(
    slot_rows: Iterable[Mapping[str, Any]],
    *,
    generated_at: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in slot_rows:
        row = dict(raw)
        if "sec_product_taxonomy_normalized" not in {str(item) for item in row.get("slot_source_ids") or []}:
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        company = str(row.get("company_name") or row.get("issuer_name") or "").strip()
        product = _taxonomy_product_label(row)
        source_url = _first_sec_or_public_url(row.get("sample_urls") or [])
        if not ticker or not product or not source_url:
            continue
        evidence_ref = _stable_ref("sec_product_taxonomy_context", [ticker, product, source_url])
        if evidence_ref in seen:
            continue
        seen.add(evidence_ref)
        out.append(
            {
                "schema_version": SCHEMA_VERSION,
                "ticker": ticker,
                "company": company,
                "company_name": company,
                "source_id": "sec_product_taxonomy_normalized",
                "underlying_source_id": "sec_product_taxonomy_normalized",
                "source_layer_id": "L1",
                "source_layer": "L1",
                "layer_id": "L1",
                "source_url": source_url,
                "citation": {"url": source_url, "title": f"SEC product taxonomy: {product}"},
                "source_title": f"SEC product taxonomy: {product}",
                "product_or_segment": product,
                "product_family": str(row.get("family_name") or row.get("family_id") or "").strip(),
                "family_id": str(row.get("family_id") or "").strip(),
                "fact_label": product,
                "topic": product,
                "parser_status": "source_specific_context_parser_pass",
                "structured_fact_status": "bounded_context_fact_materialized",
                "runtime_ready_context": True,
                "evidence_graph_status": "runtime_ready_context",
                "issuer_binding_status": "issuer_mentioned_in_snapshot",
                "product_binding_status": "product_mentioned_in_snapshot",
                "counterparty_binding_status": "not_bound",
                "can_support_company_exact_fact": False,
                "exact_value_authority": False,
                "context_only": True,
                "allowed_claims": ["official_product_surface", "product_taxonomy_context"],
                "forbidden_claims": ["company_sales", "market_share", "product_revenue", "ASP", "inventory", "sell_through"],
                "claim_boundary": "SEC-derived product taxonomy context only; no sales, share, ASP, inventory, sell-through, or product KPI authority.",
                "authority_boundary": "Company filing product taxonomy; context only unless separate product KPI value/unit/period/citation parser passes.",
                "source_claim_strength": "L1_product_taxonomy_context",
                "as_of_datetime": generated_at,
                "evidence_ref": evidence_ref,
                "evidence_id": evidence_ref,
                "slot_status": row.get("slot_status") or "",
                "product_slot_id": row.get("product_slot_id") or "",
            }
        )
    return sorted(out, key=lambda item: (item["ticker"], item["product_or_segment"], item["source_url"]))


def build_summary(*, slot_rows: list[Mapping[str, Any]], rows: list[Mapping[str, Any]], generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "input_slot_count": len(slot_rows),
        "context_row_count": len(rows),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows}),
        "family_count": len({str(row.get("family_id") or "") for row in rows}),
        "rows_by_family_top20": dict(Counter(str(row.get("family_id") or "") for row in rows).most_common(20)),
        "boundary": "SEC taxonomy rows satisfy official product surface only as product taxonomy context, not sales/share/ASP/inventory/sell-through authority.",
        "outputs": {"rows": str(DEFAULT_OUTPUT_ROWS)},
    }


def _taxonomy_product_label(row: Mapping[str, Any]) -> str:
    label = str(row.get("product_slot_name") or "").strip()
    family = str(row.get("family_name") or row.get("family_id") or "").strip()
    if _label_is_generic(label) and family:
        return family
    return label or family


def _label_is_generic(label: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(label or "").strip().lower())
    return not normalized or any(pattern in normalized for pattern in GENERIC_PRODUCT_LABEL_PATTERNS)


def _first_sec_or_public_url(urls: Iterable[Any]) -> str:
    values = [str(url or "").strip() for url in urls if str(url or "").strip().startswith(("http://", "https://"))]
    for url in values:
        if "sec.gov/Archives/" in url:
            return url
    for url in values:
        if "api." not in url and "sec.gov" not in url:
            return url
    return values[0] if values else ""


def _stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    text = "|".join(str(part or "") for part in parts)
    import hashlib

    return f"{prefix}:{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
