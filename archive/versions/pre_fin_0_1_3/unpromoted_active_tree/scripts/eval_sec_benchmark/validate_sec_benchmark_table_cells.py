from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate SEC benchmark metric-table answers against reviewed Exact-Value Ledger cells."
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--cases-path", default="eval/sec_cases/test_cases_v1.jsonl")
    parser.add_argument(
        "--ledger-path",
        default="reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json",
    )
    parser.add_argument("--output-path", default="")
    parser.add_argument("--relative-tolerance", type=float, default=0.000001)
    parser.add_argument("--absolute-tolerance", type=float, default=0.000001)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = _resolve(args.run_dir)
    cases = {str(row.get("case_id") or ""): row for row in _read_jsonl(_resolve(args.cases_path))}
    ledger = _read_json(_resolve(args.ledger_path))
    rows_by_case: dict[str, list[dict[str, Any]]] = {}
    for row in ledger.get("rows") or []:
        rows_by_case.setdefault(str(row.get("case_id") or ""), []).append(row)

    results = [
        _validate_agent_row(
            agent,
            cases.get(str(agent.get("case_id") or ""), {}),
            rows_by_case.get(str(agent.get("case_id") or ""), []),
            relative_tolerance=args.relative_tolerance,
            absolute_tolerance=args.absolute_tolerance,
        )
        for agent in _read_jsonl(run_dir / "agent_outputs.jsonl")
    ]
    failure_counts = Counter(
        failure.get("type")
        for result in results
        for failure in result.get("failures") or []
    )
    warning_counts = Counter(
        warning.get("type")
        for result in results
        for warning in result.get("warnings") or []
    )
    fail_by_case = Counter(result.get("case_id") for result in results if result.get("status") == "fail")
    report = {
        "schema_version": "sec_benchmark_table_cell_gate_v0.1",
        "run_dir": str(run_dir.resolve()),
        "cases_path": str(_resolve(args.cases_path).resolve()),
        "ledger_path": str(_resolve(args.ledger_path).resolve()),
        "can_enter_gate": not failure_counts,
        "summary": {
            "case_count": len(results),
            "pass_count": sum(result.get("status") == "pass" for result in results),
            "fail_count": sum(result.get("status") == "fail" for result in results),
            "skip_count": sum(result.get("status") == "skipped" for result in results),
            "expected_cell_count": sum(int(result.get("expected_cell_count") or 0) for result in results),
            "reported_cell_count": sum(int(result.get("reported_cell_count") or 0) for result in results),
            "valid_cell_count": sum(int(result.get("valid_cell_count") or 0) for result in results),
            "failure_types": dict(sorted(failure_counts.items())),
            "warning_types": dict(sorted(warning_counts.items())),
            "fail_by_case": dict(sorted(fail_by_case.items())),
        },
        "case_results": results,
    }
    output_path = _resolve(args.output_path) if args.output_path else run_dir / "table_cell_gate.json"
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


def _validate_agent_row(
    agent: dict[str, Any],
    case: dict[str, Any],
    ledger_rows: list[dict[str, Any]],
    *,
    relative_tolerance: float,
    absolute_tolerance: float,
) -> dict[str, Any]:
    case_id = str(agent.get("case_id") or "")
    mode = str(agent.get("mode") or "")
    if not _requires_table_gate(case):
        return {
            "case_id": case_id,
            "mode": mode,
            "status": "skipped",
            "reason": "case_does_not_require_metric_table_cell_validator",
            "expected_cell_count": 0,
            "reported_cell_count": 0,
            "valid_cell_count": 0,
            "failures": [],
            "warnings": [],
        }
    if str(agent.get("status") or "") != "answered" or not isinstance(agent.get("answer"), dict):
        return _failed(case_id, mode, ledger_rows, [], [{"type": "agent_output_not_answered"}])
    answer = agent.get("answer") or {}
    cell_table = answer.get("cell_table")
    cells = cell_table.get("cells") if isinstance(cell_table, dict) else None
    if not isinstance(cells, list):
        return _failed(case_id, mode, ledger_rows, [], [{"type": "missing_cell_table"}])

    expected_by_metric = {
        str(row.get("metric_id") or ""): row
        for row in ledger_rows
        if str(row.get("metric_id") or "")
    }
    cells_by_metric: dict[str, list[dict[str, Any]]] = {}
    unsupported_cells: list[dict[str, Any]] = []
    for cell in cells:
        if not isinstance(cell, dict):
            unsupported_cells.append({"metric_id": "", "reason": "cell_not_object"})
            continue
        metric_id = str(cell.get("metric_id") or "")
        if metric_id not in expected_by_metric:
            unsupported_cells.append({"metric_id": metric_id, "reason": "metric_id_not_in_case_ledger"})
            continue
        cells_by_metric.setdefault(metric_id, []).append(cell)

    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    valid_count = 0
    cell_reports: list[dict[str, Any]] = []
    for metric_id, row in expected_by_metric.items():
        matches = cells_by_metric.get(metric_id) or []
        if not matches:
            failures.append({"type": "missing_metric_cell", "metric_id": metric_id})
            cell_reports.append({"metric_id": metric_id, "status": "missing"})
            continue
        if len(matches) > 1:
            failures.append({"type": "duplicate_metric_cell", "metric_id": metric_id, "count": len(matches)})
        cell = matches[0]
        cell_failures = _cell_failures(
            cell,
            row,
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        )
        failures.extend(cell_failures)
        valid = not cell_failures
        valid_count += int(valid)
        cell_reports.append(
            {
                "metric_id": metric_id,
                "status": "valid" if valid else "invalid",
                "failures": cell_failures,
            }
        )
    for cell in unsupported_cells:
        failures.append({"type": "unsupported_metric_cell", **cell})

    return {
        "case_id": case_id,
        "mode": mode,
        "status": "fail" if failures else "pass",
        "answer_status": agent.get("answer_status"),
        "expected_cell_count": len(expected_by_metric),
        "reported_cell_count": len(cells),
        "valid_cell_count": valid_count,
        "failures": failures,
        "warnings": warnings,
        "cells": cell_reports,
    }


def _cell_failures(
    cell: dict[str, Any],
    row: dict[str, Any],
    *,
    relative_tolerance: float,
    absolute_tolerance: float,
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    metric_id = str(row.get("metric_id") or "")
    checks = {
        "ticker": str(row.get("ticker") or ""),
        "metric_family": str(row.get("metric_family") or ""),
        "metric_name": str(row.get("metric_name") or ""),
        "unit": str(row.get("unit") or ""),
        "display_value_zh": str(row.get("display_value_zh") or ""),
    }
    for key, expected in checks.items():
        actual = str(cell.get(key) or "")
        if actual != expected:
            failures.append(
                {"type": f"{key}_mismatch", "metric_id": metric_id, "expected": expected, "actual": actual}
            )
    fiscal_year = _to_int(cell.get("fiscal_year"))
    expected_year = _to_int(row.get("fiscal_year"))
    if fiscal_year != expected_year:
        failures.append(
            {"type": "fiscal_year_mismatch", "metric_id": metric_id, "expected": expected_year, "actual": fiscal_year}
        )
    value = _to_float(cell.get("value"))
    expected_value = _to_float(row.get("value"))
    if value is None or expected_value is None or not _close(value, expected_value, relative_tolerance, absolute_tolerance):
        failures.append({"type": "value_mismatch", "metric_id": metric_id, "expected": expected_value, "actual": value})
    if str(cell.get("status") or "") != "reported":
        failures.append({"type": "cell_status_not_reported", "metric_id": metric_id, "actual": cell.get("status")})
    evidence_ids = {str(item) for item in cell.get("evidence_ids") or [] if str(item)}
    expected_evidence_id = str(row.get("source_evidence_id") or "")
    if expected_evidence_id and expected_evidence_id not in evidence_ids:
        failures.append(
            {
                "type": "source_evidence_id_missing",
                "metric_id": metric_id,
                "expected": expected_evidence_id,
                "actual": sorted(evidence_ids),
            }
        )
    return failures


def _requires_table_gate(case: dict[str, Any]) -> bool:
    return str(case.get("task_type") or "") == "metric_table_stability" or (
        "metric_table_cell_validator" in set(case.get("hard_gates") or [])
    )


def _failed(
    case_id: str,
    mode: str,
    ledger_rows: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "mode": mode,
        "status": "fail",
        "expected_cell_count": len(ledger_rows),
        "reported_cell_count": 0,
        "valid_cell_count": 0,
        "failures": failures,
        "warnings": warnings,
        "cells": [],
    }


def _close(actual: float, expected: float, relative_tolerance: float, absolute_tolerance: float) -> bool:
    return math.isclose(actual, expected, rel_tol=relative_tolerance, abs_tol=absolute_tolerance)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(str(value).strip()))
    except ValueError:
        return None


def _resolve(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    main()
