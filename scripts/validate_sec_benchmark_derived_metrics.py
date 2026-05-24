from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


SCHEMA_VERSION = "sec_benchmark_derived_metric_gate_v0.1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate deterministic derived metric rows in an SEC benchmark exact-value ledger."
    )
    parser.add_argument(
        "--ledger-path",
        default="reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json",
    )
    parser.add_argument(
        "--output-path",
        default="reports/quality/sec_benchmark_derived_metric_gate.json",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Optional case_id filter. Repeat for multiple cases.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.001,
        help="Absolute tolerance for derived value comparisons.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ledger_path = _resolve(args.ledger_path)
    ledger = _read_json(ledger_path)
    requested_cases = {str(case_id) for case_id in args.case_id}
    rows = [
        row
        for row in ledger.get("rows") or []
        if not requested_cases or str(row.get("case_id") or "") in requested_cases
    ]
    report = _validate_ledger(
        rows=rows,
        ledger_path=ledger_path,
        requested_cases=requested_cases,
        tolerance=args.tolerance,
    )
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


def _validate_ledger(
    *,
    rows: list[dict[str, Any]],
    ledger_path: Path,
    requested_cases: set[str],
    tolerance: float,
) -> dict[str, Any]:
    rows_by_key: dict[tuple[str, str, int, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = _row_key(row)
        if key:
            rows_by_key[key].append(row)

    case_results = [
        _validate_free_cash_flow_proxy(row, rows_by_key, tolerance)
        for row in rows
        if row.get("metric_family") == "free_cash_flow_proxy"
        and row.get("metric_role") == "derived_value"
    ]
    failure_counts = Counter(
        failure.get("type")
        for result in case_results
        for failure in result.get("failures") or []
    )
    fail_by_case = Counter(
        result.get("case_id")
        for result in case_results
        if result.get("status") == "fail"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "ledger_path": str(ledger_path.resolve()),
        "case_filter": sorted(requested_cases),
        "formula_policy": {
            "free_cash_flow_proxy": "cash_flow.total_value + capex_or_ppe_purchases.total_value",
            "note": "SEC cash-flow tables usually encode capex/PPE purchases as negative cash outflows.",
        },
        "tolerance": tolerance,
        "can_enter_gate": not failure_counts,
        "summary": {
            "derived_row_count": len(case_results),
            "pass_count": sum(result.get("status") == "pass" for result in case_results),
            "fail_count": sum(result.get("status") == "fail" for result in case_results),
            "failure_types": dict(sorted(failure_counts.items())),
            "fail_by_case": dict(sorted(fail_by_case.items())),
        },
        "case_results": case_results,
    }


def _validate_free_cash_flow_proxy(
    row: dict[str, Any],
    rows_by_key: dict[tuple[str, str, int, str, str], list[dict[str, Any]]],
    tolerance: float,
) -> dict[str, Any]:
    case_id = str(row.get("case_id") or "")
    ticker = str(row.get("ticker") or "")
    year = _int_or_none(row.get("fiscal_year"))
    value = _float_or_none(row.get("value"))
    failures: list[dict[str, Any]] = []
    if not case_id or not ticker or year is None or value is None:
        failures.append({"type": "derived_row_key_or_value_missing"})
        return _derived_result(row, status="fail", failures=failures)

    cash_flow_rows = rows_by_key.get((case_id, ticker, year, "cash_flow", "total_value"), [])
    capex_rows = rows_by_key.get((case_id, ticker, year, "ppe_purchases", "total_value"), [])
    if not capex_rows:
        capex_rows = rows_by_key.get((case_id, ticker, year, "capex", "total_value"), [])
    if len(cash_flow_rows) != 1:
        failures.append(
            {
                "type": "cash_flow_input_count_not_one",
                "count": len(cash_flow_rows),
            }
        )
    if len(capex_rows) != 1:
        failures.append(
            {
                "type": "capex_input_count_not_one",
                "count": len(capex_rows),
            }
        )
    if failures:
        return _derived_result(row, status="fail", failures=failures)

    cash_flow_value = _float_or_none(cash_flow_rows[0].get("value"))
    capex_value = _float_or_none(capex_rows[0].get("value"))
    if cash_flow_value is None or capex_value is None:
        failures.append(
            {
                "type": "input_value_missing",
                "cash_flow_value": cash_flow_rows[0].get("value"),
                "capex_value": capex_rows[0].get("value"),
            }
        )
        return _derived_result(row, status="fail", failures=failures)
    expected = cash_flow_value + capex_value
    if capex_value > 0:
        failures.append(
            {
                "type": "capex_input_not_negative_outflow",
                "capex_value": capex_value,
            }
        )
    if not math.isclose(value, expected, abs_tol=tolerance):
        failures.append(
            {
                "type": "derived_value_mismatch",
                "actual": value,
                "expected": expected,
                "cash_flow_value": cash_flow_value,
                "capex_value": capex_value,
            }
        )
    return _derived_result(
        row,
        status="fail" if failures else "pass",
        failures=failures,
        expected_value=expected,
        input_metric_ids=[
            str(cash_flow_rows[0].get("metric_id") or ""),
            str(capex_rows[0].get("metric_id") or ""),
        ],
    )


def _derived_result(
    row: dict[str, Any],
    *,
    status: str,
    failures: list[dict[str, Any]],
    expected_value: float | None = None,
    input_metric_ids: list[str] | None = None,
) -> dict[str, Any]:
    result = {
        "case_id": row.get("case_id"),
        "ticker": row.get("ticker"),
        "fiscal_year": row.get("fiscal_year"),
        "metric_id": row.get("metric_id"),
        "metric_family": row.get("metric_family"),
        "metric_role": row.get("metric_role"),
        "value": row.get("value"),
        "status": status,
        "failures": failures,
    }
    if expected_value is not None:
        result["expected_value"] = expected_value
    if input_metric_ids:
        result["input_metric_ids"] = input_metric_ids
    return result


def _row_key(row: dict[str, Any]) -> tuple[str, str, int, str, str] | None:
    case_id = str(row.get("case_id") or "")
    ticker = str(row.get("ticker") or "")
    year = _int_or_none(row.get("fiscal_year"))
    metric_family = str(row.get("metric_family") or "")
    metric_role = str(row.get("metric_role") or "")
    if not case_id or not ticker or year is None or not metric_family or not metric_role:
        return None
    return (case_id, ticker, year, metric_family, metric_role)


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


if __name__ == "__main__":
    main()
