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
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "finsight_r17_known_public_product_kpi_repair_row_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_r17_known_public_product_kpi_repair_summary_v0_1"

DEFAULT_DECK_IR_HTML = REPO_ROOT / "data" / "raw_private" / "company_ir" / "deckers" / "fy2025_q4_full_year_results.html"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "r17_known_public_product_kpi_repair_runtime_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "r17_known_public_product_kpi_repair_summary_v0_1.json"

DECK_SOURCE_URL = (
    "https://ir.deckers.com/news-events/press-releases/detail/229/"
    "deckers-brands-reports-fourth-quarter-and-full-fiscal-year-2025-financial-results"
)

BRAND_NET_SALES_RE = re.compile(
    r"(?P<brand>UGG|HOKA|Other brands)(?:®)?(?: brand)? net sales (?P<direction>increased|decreased) "
    r"(?P<growth_pct>[0-9.]+)% to \$(?P<value>[0-9.]+) (?P<unit_scale>billion|million) "
    r"compared to \$(?P<prior_value>[0-9.]+) (?P<prior_unit_scale>billion|million)",
    re.IGNORECASE,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build R17 known-public Product-KPI repair runtime rows.")
    parser.add_argument("--deck-ir-html", type=Path, default=DEFAULT_DECK_IR_HTML)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    rows = build_known_public_product_kpi_repair_rows(deck_ir_html=args.deck_ir_html, generated_at=generated_at)
    summary = build_summary(rows=rows, generated_at=generated_at, output_rows=args.output_rows)
    _write_jsonl(args.output_rows, rows)
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["status"] != "pass":
        return 1
    return 0


def build_known_public_product_kpi_repair_rows(*, deck_ir_html: Path, generated_at: str) -> list[dict[str, Any]]:
    if not deck_ir_html.exists():
        return []
    text = _html_to_text(deck_ir_html.read_text(encoding="utf-8", errors="ignore"))
    return parse_deck_brand_net_sales_rows(text=text, raw_path=deck_ir_html, generated_at=generated_at)


def parse_deck_brand_net_sales_rows(*, text: str, raw_path: Path | str, generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_brands: set[str] = set()
    for match in BRAND_NET_SALES_RE.finditer(text):
        brand = _canonical_brand(match.group("brand"))
        if brand in seen_brands:
            # The release repeats the same brand pattern for Q4 after the FY section; the first block is FY2025.
            continue
        seen_brands.add(brand)
        value_usd = _scaled_usd(match.group("value"), match.group("unit_scale"))
        prior_value_usd = _scaled_usd(match.group("prior_value"), match.group("prior_unit_scale"))
        growth_pct = float(match.group("growth_pct"))
        if match.group("direction").lower() == "decreased":
            growth_pct = -growth_pct
        evidence_ref = f"r17_known_public_product_kpi:{_short_hash('DECK', brand, value_usd, 'FY2025')}"
        citation = _clean_sentence(match.group(0))
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
                "evidence_ref": evidence_ref,
                "fact_id": evidence_ref,
                "ticker": "DECK",
                "company_name": "Deckers Outdoor Corporation",
                "source_family": "company_product_evidence_graph",
                "runtime_source_family": "company_product_evidence_graph",
                "source_layer_id": "L1",
                "source_id": "company_ir_earnings_release",
                "source_role": "primary_company_disclosure",
                "source_url": DECK_SOURCE_URL,
                "raw_path": str(raw_path),
                "product_or_segment": brand,
                "matched_product_alias": brand,
                "row_label": brand,
                "metric_name": "brand net sales",
                "metric_family": "product_revenue",
                "value": value_usd,
                "unit": "USD",
                "unit_category": "currency",
                "period": "FY2025",
                "fiscal_year": 2025,
                "prior_value": prior_value_usd,
                "prior_period": "FY2024",
                "growth_pct": growth_pct,
                "product_node_type": "category_or_brand_family",
                "promotion_status": "runtime_fact_allowed",
                "runtime_action": "promote_product_kpi_exact",
                "claim_types": ["company_disclosed_product_kpi"],
                "allowed_claims": ["company_disclosed_brand_net_sales"],
                "forbidden_claims": [
                    "undisclosed_sku_revenue",
                    "sell_through",
                    "channel_inventory",
                    "market_share",
                    "ASP_without_company_or_tracker_data",
                ],
                "citation_span": citation,
                "claim_boundary": (
                    "Company IR earnings-release brand net sales row; supports cited brand net sales only, "
                    "not SKU revenue, sell-through, ASP, channel inventory, or market share."
                ),
            }
        )
    return rows


def build_summary(*, rows: list[Mapping[str, Any]], generated_at: str, output_rows: Path) -> dict[str, Any]:
    brands = sorted({str(row.get("product_or_segment") or "") for row in rows})
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if len(rows) >= 2 and {"UGG", "HOKA"}.issubset(set(brands)) else "gap",
        "runtime_row_count": len(rows),
        "ticker_count": len({row.get("ticker") for row in rows}),
        "brands": brands,
        "outputs": {"rows": str(output_rows)},
        "policy": "R17 known-public repair rows are company-disclosed L1 Product-KPI exact rows only within cited brand/metric/period boundaries.",
    }


def _html_to_text(value: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|li|tr|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _canonical_brand(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if text.lower() == "other brands":
        return "Other brands"
    return text.upper()


def _scaled_usd(value: str, scale: str) -> float:
    number = float(value)
    multiplier = 1_000_000_000 if scale.lower() == "billion" else 1_000_000
    return number * multiplier


def _clean_sentence(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip().rstrip(".") + "."


def _short_hash(*values: object) -> str:
    digest = hashlib.sha256("|".join(str(value) for value in values).encode("utf-8")).hexdigest()
    return digest[:16]


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
