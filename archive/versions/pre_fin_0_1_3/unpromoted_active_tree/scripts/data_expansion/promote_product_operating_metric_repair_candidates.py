from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]

SUMMARY_SCHEMA_VERSION = "fin_agent_product_operating_metric_repair_summary_v0.1"
REJECTION_SCHEMA_VERSION = "fin_agent_product_operating_metric_repair_rejection_v0.1"

DEFAULT_BASE_FACTS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_with_quality_filter_v0_1.jsonl"
)
DEFAULT_REPAIR_FACTS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_targeted_repair_strict_sentence_v0_1.jsonl"
)
DEFAULT_REVENUE_REJECTIONS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_monotonic_repair_rejections_v0_5.jsonl"
)
DEFAULT_OUTPUT_DIR = Path("Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1")
DEFAULT_COMBINED_FACTS_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_kpi_facts_parser_verified_with_quality_operating_repair_v0_1.jsonl"
DEFAULT_PROMOTED_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_operating_metric_facts_repair_promoted_v0_1.jsonl"
DEFAULT_REJECTIONS_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_operating_metric_repair_rejections_v0_1.jsonl"
DEFAULT_SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_operating_metric_repair_summary_v0_1.json"
DEFAULT_REPORT_OUTPUT = Path(
    "Z:/FIN_Insight_Agent/docs/internal/vnext_20260610/product_operating_metric_repair_v0_1_execution.zh-CN.md"
)

SUBSCRIBER_TABLE_RE = re.compile(r"subscriber information.*\(in millions\)", re.IGNORECASE | re.DOTALL)
GAS_DELIVERED_MDT_RE = re.compile(r"gas delivered\s*\(mdt\)", re.IGNORECASE)
OPERATING_GATE_VERSION = "operating_metric_source_specific_unit_correction_v0_1"
ED_GAS_DELIVERED_MIN_MDT = 100_000


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote high-confidence non-revenue product operating metric repair candidates.")
    parser.add_argument("--base-facts", type=Path, default=DEFAULT_BASE_FACTS)
    parser.add_argument("--repair-facts", type=Path, default=DEFAULT_REPAIR_FACTS)
    parser.add_argument("--revenue-rejections", type=Path, default=DEFAULT_REVENUE_REJECTIONS)
    parser.add_argument("--combined-facts-output", type=Path, default=DEFAULT_COMBINED_FACTS_OUTPUT)
    parser.add_argument("--promoted-output", type=Path, default=DEFAULT_PROMOTED_OUTPUT)
    parser.add_argument("--rejections-output", type=Path, default=DEFAULT_REJECTIONS_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).isoformat()
    base_rows = list(_iter_jsonl(_resolve(args.base_facts)))
    repair_rows = list(_iter_jsonl(_resolve(args.repair_facts)))
    revenue_rejection_rows = list(_iter_jsonl(_resolve(args.revenue_rejections)))
    combined_rows, promoted_rows, rejection_rows, summary = promote_operating_metric_candidates(
        base_rows=base_rows,
        repair_rows=repair_rows,
        revenue_rejection_rows=revenue_rejection_rows,
        generated_at=generated_at,
        paths={
            "base_facts": _repo_path(_resolve(args.base_facts)),
            "repair_facts": _repo_path(_resolve(args.repair_facts)),
            "revenue_rejections": _repo_path(_resolve(args.revenue_rejections)),
            "combined_facts": _repo_path(_resolve(args.combined_facts_output)),
            "promoted": _repo_path(_resolve(args.promoted_output)),
            "rejections": _repo_path(_resolve(args.rejections_output)),
            "summary": _repo_path(_resolve(args.summary_output)),
            "report": _repo_path(_resolve(args.report_output)),
        },
    )
    _write_jsonl(_resolve(args.combined_facts_output), combined_rows)
    _write_jsonl(_resolve(args.promoted_output), promoted_rows)
    _write_jsonl(_resolve(args.rejections_output), rejection_rows)
    _write_json(_resolve(args.summary_output), summary)
    report_output = _resolve(args.report_output)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def promote_operating_metric_candidates(
    *,
    base_rows: list[dict[str, Any]],
    repair_rows: list[dict[str, Any]],
    revenue_rejection_rows: list[dict[str, Any]],
    generated_at: str,
    paths: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rejected_not_revenue_ids = {
        str(row.get("fact_id") or "")
        for row in revenue_rejection_rows
        if row.get("rejection_reason") == "not_product_revenue"
    }
    base_claims = {operating_claim_key(row) for row in base_rows}
    promoted_rows: list[dict[str, Any]] = []
    rejection_rows: list[dict[str, Any]] = []
    seen_claims: set[tuple[Any, ...]] = set()
    for row in repair_rows:
        if str(row.get("fact_id") or "") not in rejected_not_revenue_ids:
            continue
        reason = operating_rejection_reason(row)
        if reason == "promote":
            promoted = corrected_operating_metric_row(row, generated_at)
            key = operating_claim_key(promoted)
            if key in base_claims or key in seen_claims:
                rejection_rows.append(rejection_row(row, "operating_metric_claim_already_covered", generated_at))
                continue
            seen_claims.add(key)
            promoted_rows.append(promoted)
        else:
            rejection_rows.append(rejection_row(row, reason, generated_at))

    combined_rows = [*base_rows, *promoted_rows]
    summary = build_summary(
        base_rows=base_rows,
        promoted_rows=promoted_rows,
        rejection_rows=rejection_rows,
        generated_at=generated_at,
        paths=paths or {},
    )
    return combined_rows, promoted_rows, rejection_rows, summary


def operating_rejection_reason(row: dict[str, Any]) -> str:
    ticker = str(row.get("ticker") or "")
    metric_family = str(row.get("metric_family") or "")
    citation = str(row.get("citation_span") or "")
    row_label = str(row.get("row_label") or "")
    if ticker == "WBD" and metric_family == "subscribers_or_arpu":
        if "total streaming subscribers" in row_label.lower() and SUBSCRIBER_TABLE_RE.search(citation):
            return "promote"
        return "subscriber_table_context_not_verified"
    if ticker == "ED" and metric_family == "unit_sales_or_deliveries":
        if is_ed_cecony_gas_delivered_mdt(row):
            return "promote"
        if "total gas delivered to cecony customers" in row_label.lower() and GAS_DELIVERED_MDT_RE.search(citation):
            return "ed_gas_delivered_customer_count_or_subtotal_not_total_mdt"
        return "public_disclosure_row_subrow_ambiguity"
    return "unsupported_operating_metric_repair_candidate"


def corrected_operating_metric_row(row: dict[str, Any], generated_at: str) -> dict[str, Any]:
    if str(row.get("ticker") or "") == "ED":
        return corrected_ed_gas_delivered_row(row, generated_at)
    return corrected_wbd_streaming_subscribers_row(row, generated_at)


def corrected_wbd_streaming_subscribers_row(row: dict[str, Any], generated_at: str) -> dict[str, Any]:
    promoted = dict(row)
    promoted["source_repair_fact_id"] = row.get("fact_id")
    promoted["metric_family"] = "subscribers_or_arpu"
    promoted["metric_name"] = "streaming_subscribers"
    promoted["unit"] = "subscribers"
    promoted["unit_category"] = "subscribers"
    promoted["repair_promotion_status"] = "operating_metric_repair_promoted"
    promoted["repair_promotion_gate"] = OPERATING_GATE_VERSION
    promoted["repair_promotion_generated_at"] = generated_at
    promoted["repair_claim_scope"] = "company_disclosed_streaming_subscribers"
    promoted["runtime_use_boundary"] = (
        "May support company-disclosed streaming subscriber count; must not be used as revenue, ARPU, market share, "
        "paid net adds, or app usage unless separately disclosed."
    )
    promoted["fact_id"] = stable_id("PRODUCTKPIOPERATINGREPAIR", *operating_claim_key(promoted))
    return promoted


def corrected_ed_gas_delivered_row(row: dict[str, Any], generated_at: str) -> dict[str, Any]:
    promoted = dict(row)
    promoted["source_repair_fact_id"] = row.get("fact_id")
    promoted["metric_family"] = "unit_sales_or_deliveries"
    promoted["metric_name"] = "gas_delivered"
    promoted["unit"] = "MDt"
    promoted["unit_category"] = "thousand_dekatherms"
    promoted["repair_promotion_status"] = "operating_metric_repair_promoted"
    promoted["repair_promotion_gate"] = OPERATING_GATE_VERSION
    promoted["repair_promotion_generated_at"] = generated_at
    promoted["repair_claim_scope"] = "company_disclosed_gas_delivered_mdt"
    promoted["runtime_use_boundary"] = (
        "May support company-disclosed CECONY gas delivered volume in MDt; must not be used as revenue, customer count, "
        "market share, or price unless separately disclosed."
    )
    promoted["fact_id"] = stable_id("PRODUCTKPIOPERATINGREPAIR", *operating_claim_key(promoted))
    return promoted


def is_ed_cecony_gas_delivered_mdt(row: dict[str, Any]) -> bool:
    citation = str(row.get("citation_span") or "")
    row_label = str(row.get("row_label") or "")
    return (
        str(row.get("ticker") or "") == "ED"
        and str(row.get("metric_family") or "") == "unit_sales_or_deliveries"
        and "total gas delivered to cecony customers" in row_label.lower()
        and GAS_DELIVERED_MDT_RE.search(citation) is not None
        and normalized_value(row.get("value")) >= ED_GAS_DELIVERED_MIN_MDT
    )


def rejection_row(row: dict[str, Any], reason: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": REJECTION_SCHEMA_VERSION,
        "rejection_id": stable_id("PRODUCTOPERATINGREPAIRREJECT", row.get("fact_id"), reason),
        "generated_at": generated_at,
        "rejection_reason": reason,
        "ticker": row.get("ticker"),
        "company": row.get("company"),
        "fact_id": row.get("fact_id"),
        "metric_family": row.get("metric_family"),
        "metric_name": row.get("metric_name"),
        "product_or_segment": row.get("product_or_segment"),
        "period": row.get("period"),
        "unit": row.get("unit"),
        "unit_category": row.get("unit_category"),
        "value": row.get("value"),
        "row_label": row.get("row_label"),
        "column_label": row.get("column_label"),
        "source_document_id": row.get("source_document_id"),
        "source_url": row.get("source_url"),
    }


def build_summary(
    *,
    base_rows: list[dict[str, Any]],
    promoted_rows: list[dict[str, Any]],
    rejection_rows: list[dict[str, Any]],
    generated_at: str,
    paths: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "pass",
        "generated_at": generated_at,
        "base_fact_count": len(base_rows),
        "base_ticker_count": count_tickers(base_rows),
        "promoted_fact_count": len(promoted_rows),
        "promoted_ticker_count": count_tickers(promoted_rows),
        "combined_fact_count": len(base_rows) + len(promoted_rows),
        "combined_ticker_count": count_tickers([*base_rows, *promoted_rows]),
        "promoted_metric_family_counts": dict(
            sorted(Counter(str(row.get("metric_family") or "") for row in promoted_rows).items())
        ),
        "promoted_ticker_counts": dict(sorted(Counter(str(row.get("ticker") or "") for row in promoted_rows).items())),
        "rejection_count": len(rejection_rows),
        "rejection_reason_counts": dict(
            sorted(Counter(str(row.get("rejection_reason") or "") for row in rejection_rows).items())
        ),
        "outputs": paths,
        "promotion_boundary": [
            "Operating metric repair facts are not product revenue.",
            "WBD Total Streaming subscribers passes only when the local subscriber table context is verified.",
            "ED CECONY Gas Delivered passes only when the table says Gas Delivered (MDt), the row is Total Gas Delivered to CECONY Customers, and the value is in delivered-volume scale.",
            "ED small values under the same row remain rejected as customer-count/subtotal row-binding failures.",
        ],
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Product Operating Metric Repair v0.1 执行报告",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- Base facts：`{summary['base_fact_count']}` / tickers `({summary['base_ticker_count']})`",
        f"- Promoted operating facts：`{summary['promoted_fact_count']}` / tickers `({summary['promoted_ticker_count']})`",
        f"- Combined facts：`{summary['combined_fact_count']}` / tickers `({summary['combined_ticker_count']})`",
        f"- Rejection reasons：`{json.dumps(summary['rejection_reason_counts'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Boundary",
        "",
    ]
    lines.extend(f"- {item}" for item in summary["promotion_boundary"])
    return "\n".join(lines) + "\n"


def operating_claim_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("ticker"),
        row.get("product_node_id"),
        row.get("metric_family"),
        row.get("period"),
        row.get("unit"),
        normalized_value(row.get("value")),
    )


def normalized_value(value: Any) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def count_tickers(rows: Iterable[dict[str, Any]]) -> int:
    return len({str(row.get("ticker") or "") for row in rows if row.get("ticker")})


def stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha1("||".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:14]
    return f"{prefix}::{digest}"


def _resolve(path: Path) -> Path:
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
