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

SUMMARY_SCHEMA_VERSION = "fin_agent_product_kpi_quality_filter_summary_v0.1"
SUPPRESSION_SCHEMA_VERSION = "fin_agent_product_kpi_quality_suppression_v0.1"

DEFAULT_INPUT_FACTS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_with_monotonic_repair_v0_5.jsonl"
)
DEFAULT_OUTPUT_DIR = Path("Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1")
DEFAULT_FILTERED_FACTS_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_kpi_facts_parser_verified_with_quality_filter_v0_1.jsonl"
DEFAULT_SUPPRESSIONS_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_kpi_quality_suppressions_v0_1.jsonl"
DEFAULT_SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_kpi_quality_filter_summary_v0_1.json"
DEFAULT_REPORT_OUTPUT = Path(
    "Z:/FIN_Insight_Agent/docs/internal/vnext_20260610/product_kpi_quality_filter_v0_1_execution.zh-CN.md"
)

SUBSCRIBER_CONTEXT_RE = re.compile(r"subscriber|subscribers|arpu|average revenue per user", re.IGNORECASE)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove high-confidence false positives from accepted product KPI fact layer.")
    parser.add_argument("--input-facts", type=Path, default=DEFAULT_INPUT_FACTS)
    parser.add_argument("--filtered-facts-output", type=Path, default=DEFAULT_FILTERED_FACTS_OUTPUT)
    parser.add_argument("--suppressions-output", type=Path, default=DEFAULT_SUPPRESSIONS_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).isoformat()
    rows = list(_iter_jsonl(_resolve(args.input_facts)))
    filtered_rows, suppression_rows = quality_filter_facts(rows, generated_at)
    summary = build_summary(
        input_rows=rows,
        filtered_rows=filtered_rows,
        suppression_rows=suppression_rows,
        generated_at=generated_at,
        paths={
            "input_facts": _repo_path(_resolve(args.input_facts)),
            "filtered_facts": _repo_path(_resolve(args.filtered_facts_output)),
            "suppressions": _repo_path(_resolve(args.suppressions_output)),
            "summary": _repo_path(_resolve(args.summary_output)),
            "report": _repo_path(_resolve(args.report_output)),
        },
    )
    _write_jsonl(_resolve(args.filtered_facts_output), filtered_rows)
    _write_jsonl(_resolve(args.suppressions_output), suppression_rows)
    _write_json(_resolve(args.summary_output), summary)
    report_output = _resolve(args.report_output)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def quality_filter_facts(
    rows: list[dict[str, Any]], generated_at: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    filtered_rows: list[dict[str, Any]] = []
    suppression_rows: list[dict[str, Any]] = []
    for row in rows:
        reason = suppression_reason(row)
        if reason:
            suppression_rows.append(suppression_row(row, reason, generated_at))
            continue
        filtered_rows.append(row)
    return filtered_rows, suppression_rows


def suppression_reason(row: dict[str, Any]) -> str:
    if is_ed_gas_delivered_unrepaired_unit_row(row):
        return "ed_gas_delivered_requires_mdt_source_specific_repair"
    if row.get("metric_family") != "product_revenue":
        return ""
    if normalized_value(row.get("value")) <= 0:
        return "non_positive_product_revenue_level_invalid"
    text = " ".join(
        str(row.get(key) or "")
        for key in ("metric_name", "product_or_segment", "row_label", "column_label", "citation_span")
    )
    if SUBSCRIBER_CONTEXT_RE.search(text):
        return "subscriber_metric_misclassified_as_product_revenue"
    return ""


def is_ed_gas_delivered_unrepaired_unit_row(row: dict[str, Any]) -> bool:
    row_label = str(row.get("row_label") or "")
    citation = str(row.get("citation_span") or "")
    return (
        row.get("ticker") == "ED"
        and row.get("metric_family") == "unit_sales_or_deliveries"
        and str(row.get("unit") or "").lower() in {"units", "systems"}
        and "total gas delivered to cecony customers" in row_label.lower()
        and "gas delivered" in citation.lower()
    )


def suppression_row(row: dict[str, Any], reason: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": SUPPRESSION_SCHEMA_VERSION,
        "suppression_id": stable_id("PRODUCTKPIQUALITYSUPPRESS", row.get("fact_id"), reason),
        "generated_at": generated_at,
        "suppression_reason": reason,
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
        "source_id": row.get("source_id"),
        "source_document_id": row.get("source_document_id"),
        "runtime_boundary": "Suppressed from runtime fact layer; keep only as parser quality audit evidence.",
    }


def build_summary(
    *,
    input_rows: list[dict[str, Any]],
    filtered_rows: list[dict[str, Any]],
    suppression_rows: list[dict[str, Any]],
    generated_at: str,
    paths: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "pass",
        "generated_at": generated_at,
        "input_fact_count": len(input_rows),
        "filtered_fact_count": len(filtered_rows),
        "suppressed_fact_count": len(suppression_rows),
        "input_ticker_count": count_tickers(input_rows),
        "filtered_ticker_count": count_tickers(filtered_rows),
        "suppressed_ticker_count": count_tickers(suppression_rows),
        "suppression_reason_counts": dict(
            sorted(Counter(str(row.get("suppression_reason") or "") for row in suppression_rows).items())
        ),
        "suppressed_ticker_counts": dict(Counter(str(row.get("ticker") or "") for row in suppression_rows).most_common(25)),
        "outputs": paths,
        "boundary": [
            "This filter removes only high-confidence false positives; it does not rewrite source baseline files.",
            "ED CECONY Gas Delivered rows with unrepaired units/systems are suppressed here and can re-enter only through the MDt source-specific operating repair gate.",
            "Positive percent-of-revenue rows are not bulk-suppressed in this pass because some are valid product revenue mix disclosures and need a separate schema.",
            "Suppressed rows must not be used as runtime product KPI facts.",
        ],
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Product KPI Quality Filter v0.1 执行报告",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- Input facts：`{summary['input_fact_count']}` / tickers `({summary['input_ticker_count']})`",
        f"- Filtered facts：`{summary['filtered_fact_count']}` / tickers `({summary['filtered_ticker_count']})`",
        f"- Suppressed facts：`{summary['suppressed_fact_count']}` / tickers `({summary['suppressed_ticker_count']})`",
        f"- Suppression reasons：`{json.dumps(summary['suppression_reason_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Suppressed tickers：`{json.dumps(summary['suppressed_ticker_counts'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Boundary",
        "",
    ]
    lines.extend(f"- {item}" for item in summary["boundary"])
    return "\n".join(lines) + "\n"


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
