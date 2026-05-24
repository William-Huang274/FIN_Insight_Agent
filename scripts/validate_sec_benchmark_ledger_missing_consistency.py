from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


TICKER_ALIASES = {
    "AAPL": ["AAPL", "Apple", "苹果"],
    "AMZN": ["AMZN", "Amazon", "AWS", "亚马逊"],
    "GOOGL": ["GOOGL", "Google", "Alphabet", "Google Cloud"],
    "MSFT": ["MSFT", "Microsoft", "Microsoft Cloud", "微软"],
    "NVDA": ["NVDA", "NVIDIA", "Nvidia", "英伟达"],
    "PANW": ["PANW", "Palo Alto", "Palo Alto Networks"],
    "SNOW": ["SNOW", "Snowflake"],
}


METRIC_FAMILY_ALIASES = {
    "cloud_revenue": ["cloud revenue", "云业务收入", "云收入"],
    "cloud_revenue_proxy": ["cloud revenue proxy", "收入 proxy", "收入proxy", "广义收入"],
    "data_center_revenue": ["data center revenue", "Data Center", "数据中心收入"],
    "gross_margin": ["gross margin", "毛利率"],
    "operating_income": ["operating income", "operating profit", "经营利润", "营业利润"],
    "rpo": ["RPO", "剩余履约义务"],
    "services_revenue": ["services revenue", "服务收入"],
    "subscription_revenue": ["subscription revenue", "订阅收入"],
}


MISSING_CLAIM_MARKERS = (
    "缺失",
    "缺少",
    "未披露",
    "没有",
    "未提供",
    "无法提供",
    "仅披露",
    "not disclosed",
    "not found",
    "missing",
    "only disclosed",
)
GENERIC_DATA_MISSING_MARKERS = ("完整数据", "complete data", "all data")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate that answer missing-evidence statements do not contradict the Exact-Value Ledger."
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--ledger-path",
        default="reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json",
    )
    parser.add_argument("--output-path", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = _resolve(args.run_dir)
    ledger = _read_json(_resolve(args.ledger_path))
    available_by_case: dict[str, set[tuple[str, int, str]]] = {}
    for row in ledger.get("rows") or []:
        case_id = str(row.get("case_id") or "")
        ticker = str(row.get("ticker") or "").upper()
        year = _int_or_none(row.get("fiscal_year"))
        metric_family = str(row.get("metric_family") or "")
        if case_id and ticker and year is not None and metric_family:
            available_by_case.setdefault(case_id, set()).add((ticker, year, metric_family))

    case_results = [
        _validate_agent_row(row, available_by_case.get(str(row.get("case_id") or ""), set()))
        for row in _read_jsonl(run_dir / "agent_outputs.jsonl")
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
    report = {
        "schema_version": "sec_benchmark_ledger_missing_consistency_gate_v0.1",
        "run_dir": str(run_dir.resolve()),
        "ledger_path": str(_resolve(args.ledger_path).resolve()),
        "can_enter_gate": not failure_counts,
        "summary": {
            "case_count": len(case_results),
            "pass_count": sum(result.get("status") == "pass" for result in case_results),
            "fail_count": sum(result.get("status") == "fail" for result in case_results),
            "skip_count": sum(result.get("status") == "skipped" for result in case_results),
            "missing_statement_count": sum(int(result.get("missing_statement_count") or 0) for result in case_results),
            "false_missing_statement_count": sum(
                int(result.get("false_missing_statement_count") or 0) for result in case_results
            ),
            "failure_types": dict(sorted(failure_counts.items())),
            "fail_by_case": dict(sorted(fail_by_case.items())),
        },
        "case_results": case_results,
    }
    output_path = _resolve(args.output_path) if args.output_path else run_dir / "ledger_missing_consistency_gate.json"
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


def _validate_agent_row(row: dict[str, Any], available: set[tuple[str, int, str]]) -> dict[str, Any]:
    case_id = str(row.get("case_id") or "")
    mode = str(row.get("mode") or "")
    if str(row.get("status") or "") != "answered" or not isinstance(row.get("answer"), dict):
        return {
            "case_id": case_id,
            "mode": mode,
            "status": "skipped",
            "reason": "agent_output_not_answered_or_answer_not_object",
            "missing_statement_count": 0,
            "false_missing_statement_count": 0,
            "failures": [],
        }
    answer = row.get("answer") or {}
    locations = _missing_statement_locations(answer)
    failures = []
    for location in locations:
        false_matches = _false_missing_matches(location["text"], available)
        if false_matches:
            failures.append(
                {
                    "type": "missing_statement_contradicts_ledger",
                    "location": location["location"],
                    "text": location["text"],
                    "matched_available_ledger_keys": [
                        {"ticker": ticker, "fiscal_year": year, "metric_family": family}
                        for ticker, year, family in false_matches
                    ],
                }
            )
    return {
        "case_id": case_id,
        "mode": mode,
        "answer_status": row.get("answer_status"),
        "status": "fail" if failures else "pass",
        "missing_statement_count": len(locations),
        "false_missing_statement_count": len(failures),
        "failures": failures,
    }


def _missing_statement_locations(answer: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key in ("not_found", "limitations"):
        for index, item in enumerate(answer.get(key) or [], start=1):
            text = str(item or "")
            if _looks_like_missing_statement(text):
                rows.append({"location": f"{key}[{index}]", "text": text})
    return rows


def _false_missing_matches(text: str, available: set[tuple[str, int, str]]) -> list[tuple[str, int, str]]:
    raw = str(text or "")
    lowered = raw.lower()
    years = {int(match.group(0)) for match in re.finditer(r"\b20\d{2}\b", raw)}
    if not years:
        return []
    tickers = [
        ticker
        for ticker, aliases in TICKER_ALIASES.items()
        if any(alias.lower() in lowered for alias in aliases)
    ]
    metric_families = [
        family
        for family, aliases in METRIC_FAMILY_ALIASES.items()
        if any(alias.lower() in lowered for alias in aliases)
    ]
    if not metric_families and any(marker.lower() in lowered for marker in GENERIC_DATA_MISSING_MARKERS):
        matches = [
            (ticker, year, family)
            for ticker in tickers
            for year in years
            for family in {item[2] for item in available}
            if (ticker, year, family) in available
        ]
        return list(dict.fromkeys(matches))
    matches = [
        (ticker, year, family)
        for ticker in tickers
        for year in years
        for family in metric_families
        if (ticker, year, family) in available
    ]
    return list(dict.fromkeys(matches))


def _looks_like_missing_statement(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(marker.lower() in lowered for marker in MISSING_CLAIM_MARKERS)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _resolve(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


if __name__ == "__main__":
    main()
