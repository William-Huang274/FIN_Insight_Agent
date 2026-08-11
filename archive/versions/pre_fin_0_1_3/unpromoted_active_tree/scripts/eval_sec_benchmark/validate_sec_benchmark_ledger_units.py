from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate SEC benchmark ledger units against source table scale markers."
    )
    parser.add_argument(
        "--ledger-path",
        default="reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json",
    )
    parser.add_argument(
        "--metrics-path",
        default="data/processed_private/structured_objects/sec_tech_10k_metrics.jsonl",
    )
    parser.add_argument(
        "--tables-path",
        default="data/processed_private/structured_objects/sec_tech_10k_tables.jsonl",
    )
    parser.add_argument("--output-path", default="reports/quality/sec_benchmark_ledger_unit_gate.json")
    parser.add_argument(
        "--fail-on-source-metric-unit-conflict",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Also fail when the structured MetricObject unit conflicts with the source table scale.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ledger_path = _resolve(args.ledger_path)
    metrics_path = _resolve(args.metrics_path)
    tables_path = _resolve(args.tables_path)
    ledger = _read_json(ledger_path)
    metrics = {str(row.get("object_id") or ""): row for row in _read_jsonl(metrics_path)}
    tables = {str(row.get("object_id") or ""): row for row in _read_jsonl(tables_path)}

    row_reports = [
        _validate_row(
            row,
            metrics.get(str(row.get("object_id") or "")),
            tables,
            fail_on_source_metric_unit_conflict=args.fail_on_source_metric_unit_conflict,
        )
        for row in ledger.get("rows") or []
    ]
    failure_counts = Counter(
        issue.get("type")
        for report in row_reports
        for issue in report.get("failures") or []
    )
    warning_counts = Counter(
        issue.get("type")
        for report in row_reports
        for issue in report.get("warnings") or []
    )
    report = {
        "schema_version": "sec_benchmark_ledger_unit_gate_v0.1",
        "ledger_path": str(ledger_path.resolve()),
        "metrics_path": str(metrics_path.resolve()),
        "tables_path": str(tables_path.resolve()),
        "fail_on_source_metric_unit_conflict": bool(args.fail_on_source_metric_unit_conflict),
        "can_enter_gate": not failure_counts,
        "summary": {
            "ledger_row_count": len(row_reports),
            "pass_count": sum(item.get("status") == "pass" for item in row_reports),
            "fail_count": sum(item.get("status") == "fail" for item in row_reports),
            "failure_types": dict(sorted(failure_counts.items())),
            "warning_types": dict(sorted(warning_counts.items())),
        },
        "rows": row_reports,
    }
    output_path = _resolve(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "can_enter_gate": report["can_enter_gate"],
                **report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _validate_row(
    row: dict[str, Any],
    metric: dict[str, Any] | None,
    tables: dict[str, dict[str, Any]],
    *,
    fail_on_source_metric_unit_conflict: bool,
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    table = None
    if metric:
        table_id = str(metric.get("table_object_id") or "")
        table = tables.get(table_id)
    if table is None:
        table = tables.get(str(row.get("object_id") or ""))
    expected_unit = _expected_unit(row, metric, table)
    ledger_unit = str(row.get("unit") or "")
    source_metric_unit = str((metric or {}).get("unit") or "")
    if metric is None and table is None:
        warnings.append({"type": "source_metric_or_table_object_not_found", "object_id": row.get("object_id")})
    if expected_unit and ledger_unit != expected_unit:
        failures.append(
            {
                "type": "ledger_unit_conflicts_with_source_scale",
                "ledger_unit": ledger_unit,
                "expected_unit": expected_unit,
                "scale_context": _scale_context(row, metric, table),
            }
        )
    if expected_unit and source_metric_unit and source_metric_unit != expected_unit:
        issue = {
            "type": "source_metric_unit_conflicts_with_source_scale",
            "source_metric_unit": source_metric_unit,
            "expected_unit": expected_unit,
            "scale_context": _scale_context(row, metric, table),
        }
        if fail_on_source_metric_unit_conflict:
            failures.append(issue)
        else:
            warnings.append(issue)
    return {
        "metric_id": row.get("metric_id"),
        "case_id": row.get("case_id"),
        "object_id": row.get("object_id"),
        "source_evidence_id": row.get("source_evidence_id"),
        "raw_value_text": row.get("raw_value_text"),
        "display_value_zh": row.get("display_value_zh"),
        "ledger_unit": ledger_unit,
        "source_metric_unit": source_metric_unit or None,
        "expected_unit": expected_unit,
        "status": "fail" if failures else "pass",
        "failures": failures,
        "warnings": warnings,
    }


def _expected_unit(
    row: dict[str, Any],
    metric: dict[str, Any] | None,
    table: dict[str, Any] | None,
) -> str | None:
    raw = str(row.get("raw_value_text") or (metric or {}).get("raw_value") or "")
    if "%" in raw or str(row.get("unit") or "") == "percent":
        return "percent"
    text = _scale_context(row, metric, table).lower()
    if "dollars in billions" in text or "in billions" in text:
        return "usd_billions"
    if "dollars in millions" in text or "in millions" in text:
        return "usd_millions"
    if "in thousands" in text:
        return "usd_thousands"
    if "billion" in raw.lower():
        return "usd_billions"
    if "million" in raw.lower():
        return "usd_millions"
    return None


def _scale_context(
    row: dict[str, Any],
    metric: dict[str, Any] | None,
    table: dict[str, Any] | None,
) -> str:
    parts: list[str] = []
    for source in (row, metric or {}, table or {}):
        if not isinstance(source, dict):
            continue
        for key in ("context", "title", "text_before", "text_after", "row_label", "metric_name"):
            value = source.get(key)
            if value:
                parts.append(str(value))
        rows = source.get("rows")
        if isinstance(rows, list):
            parts.append(" ".join(" ".join(str(cell) for cell in table_row) for table_row in rows[:6]))
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


if __name__ == "__main__":
    main()
