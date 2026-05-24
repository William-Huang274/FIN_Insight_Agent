from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

SOURCE_ALIASES = {
    "stock_price": ("stock price", "share price", "股价", "股票价格"),
    "valuation": ("valuation", "估值", "valuation multiple", "P/E", "price-to-earnings"),
    "analyst_consensus": ("analyst consensus", "consensus", "分析师", "一致预期", "市场预期"),
    "earnings_call": ("earnings call", "电话会", "业绩会"),
    "news": ("news", "新闻"),
    "10-Q": ("10-Q", "10Q", "quarterly report", "季报"),
    "8-K": ("8-K", "8K", "current report"),
    "macro": ("macro", "美联储", "降息", "利率预测", "宏观"),
    "2026_forecast": ("2026 forecast", "2026预测", "2026 年预测", "2026年预测"),
}

NEGATED_SOURCE_TERMS = (
    "do not",
    "not use",
    "outside",
    "unsupported",
    "not supported",
    "forbidden",
    "不要",
    "不能",
    "不支持",
    "缺失",
    "没有",
    "不含",
    "不可",
    "无法",
    "无",
    "仅包含",
    "only",
    "limited to",
    "not available",
    "超出",
)

BOUNDARY_SAFE_TERMS = ("10-k", "sec", "filing", "披露", "文件", "材料", "证据边界")

NON_TICKER_ACRONYMS = {
    "AI",
    "API",
    "CPU",
    "GPU",
    "SEC",
    "RAG",
    "RPO",
    "ARR",
    "AWS",
    "KPI",
    "US",
    "GAAP",
    "K",
    "MD",
    "HPC",
    "QCT",
}

METRIC_FAMILY_EQUIVALENTS = {
    "revenue": {"revenue", "total_revenue"},
    "total_revenue": {"total_revenue", "revenue"},
    "capex": {"capex", "capital_expenditure_proxy"},
    "capital_expenditure_proxy": {"capital_expenditure_proxy", "capex"},
    "operating_cash_flow": {"operating_cash_flow", "free_cash_flow_proxy"},
    "free_cash_flow_proxy": {"free_cash_flow_proxy", "operating_cash_flow"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate free-query SEC planner Query Contracts against semantic expectations."
    )
    parser.add_argument("--eval-path", default="eval_sets/sec_free_query_planner_eval_v1.jsonl")
    parser.add_argument(
        "--contracts-path",
        default="reports/query_contracts/planner_eval_v1/current_planner_contracts.jsonl",
        help="JSON/JSONL rows with case_id and query_contract/contract. Missing rows are reported as failures.",
    )
    parser.add_argument(
        "--output-path",
        default="reports/query_contracts/planner_eval_v1/current_planner_eval_report.json",
    )
    parser.add_argument("--fail-on-threshold", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    eval_path = _resolve(args.eval_path)
    contracts_path = _resolve(args.contracts_path)
    output_path = _resolve(args.output_path)

    eval_rows = _read_jsonl(eval_path)
    contracts = _load_contract_rows(contracts_path) if contracts_path.exists() else []
    contracts_by_case = _contracts_by_case(contracts)

    results = []
    for eval_row in eval_rows:
        case_id = str(eval_row.get("case_id") or "")
        contract_row = contracts_by_case.get(case_id)
        if not contract_row:
            results.append(_missing_contract_result(eval_row))
            continue
        contract = _extract_contract(contract_row)
        results.append(_evaluate_case(eval_row, contract, contract_row))

    summary = _summarize(results)
    report = {
        "schema_version": "sec_free_query_planner_eval_v1_report",
        "eval_path": str(eval_path.resolve()),
        "contracts_path": str(contracts_path.resolve()),
        "output_path": str(output_path.resolve()),
        "acceptance_targets": {
            "task_type_accuracy": 0.85,
            "primary_ticker_recall": 0.95,
            "peer_ticker_recall_any_of": 0.75,
            "required_task_coverage": 0.85,
            "metric_family_recall": 0.75,
            "year_compliance": 1.0,
            "source_boundary_violation_rate": 0.0,
            "schema_validation_pass_rate": 1.0,
        },
        "summary": summary,
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "output_path": str(output_path)}, ensure_ascii=False, indent=2))
    if args.fail_on_threshold and not _meets_thresholds(summary):
        raise SystemExit(1)


def _evaluate_case(eval_row: dict[str, Any], contract: dict[str, Any], contract_row: dict[str, Any]) -> dict[str, Any]:
    expected = eval_row.get("expected") or {}
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    task_type_ok = _task_type_ok(contract, expected)
    if not task_type_ok:
        failures.append(
            {
                "type": "wrong_task_type",
                "expected_any_of": expected.get("task_type_any_of") or [],
                "actual": contract.get("task_type"),
            }
        )

    planned_tickers = _contract_tickers(contract, include_search_scope=False)
    actual_tickers = _contract_tickers(contract, include_search_scope=True)
    focus_tickers = _upper_set(contract.get("focus_tickers") or [])
    primary_expected = _upper_set(expected.get("primary_tickers") or [])
    primary_hits = primary_expected & (focus_tickers or planned_tickers)
    primary_recall = _ratio(len(primary_hits), len(primary_expected), empty_value=1.0)
    if primary_expected and primary_hits != primary_expected:
        failures.append(
            {
                "type": "missing_primary_ticker",
                "expected": sorted(primary_expected),
                "actual_focus_tickers": sorted(focus_tickers),
                "actual_planned_tickers": sorted(planned_tickers),
                "actual_all_tickers": sorted(actual_tickers),
            }
        )

    peer_expected = _upper_set(expected.get("peer_tickers_any_of") or [])
    min_peer_hits = int(expected.get("min_peer_ticker_hits") or 0)
    peer_hits = peer_expected & planned_tickers
    peer_target = min(min_peer_hits, len(peer_expected)) if peer_expected else 0
    peer_recall = _ratio(len(peer_hits), peer_target, empty_value=1.0)
    if peer_target and len(peer_hits) < peer_target:
        failures.append(
            {
                "type": "missing_peer_ticker",
                "expected_any_of": sorted(peer_expected),
                "min_hits": peer_target,
                "actual_hits": sorted(peer_hits),
                "actual_planned_tickers": sorted(planned_tickers),
                "actual_all_tickers": sorted(actual_tickers),
            }
        )

    expected_years = _int_set(expected.get("years") or [])
    actual_years = _int_set(contract.get("years") or (contract.get("scope") or {}).get("years") or [])
    year_compliance = 1.0
    missing_years = expected_years - actual_years
    extra_years = actual_years - expected_years
    if missing_years:
        year_compliance = 0.0
        failures.append({"type": "missing_required_year", "missing": sorted(missing_years), "actual": sorted(actual_years)})
    if extra_years:
        year_compliance = 0.0
        failures.append({"type": "unsupported_year_or_form", "extra_years": sorted(extra_years)})

    task_hits, missing_task_terms = _required_task_hits(contract, expected)
    task_coverage = _ratio(task_hits, len(expected.get("required_task_terms") or []), empty_value=1.0)
    for terms in missing_task_terms:
        failures.append({"type": "missing_required_task", "terms_any": terms})

    family_expected = set(str(item) for item in expected.get("required_metric_families") or [])
    family_actual = _contract_metric_families(contract)
    family_hits = _metric_family_hits(family_expected, family_actual)
    family_recall = _ratio(len(family_hits), len(family_expected), empty_value=1.0)
    if family_expected and family_recall < 0.75:
        failures.append(
            {
                "type": "bad_metric_family",
                "expected": sorted(family_expected),
                "actual": sorted(family_actual),
                "missing": sorted(family_expected - family_hits),
            }
        )
    elif family_expected - family_hits:
        warnings.append({"type": "partial_metric_family_coverage", "missing": sorted(family_expected - family_hits)})

    source_violations = _source_boundary_violations(contract, expected)
    failures.extend(source_violations)

    missing_gap_terms = _missing_required_gap_terms(contract, expected)
    for term in missing_gap_terms:
        failures.append({"type": "missing_required_evidence_gap", "term": term})

    schema_pass = _schema_validation_pass(contract)
    if not schema_pass:
        failures.append({"type": "schema_validation_failed", "report": (contract.get("query_contract_validation") or {})})

    return {
        "case_id": eval_row.get("case_id"),
        "category": eval_row.get("category"),
        "query": eval_row.get("query"),
        "status": "pass" if not failures else "fail",
        "metrics": {
            "task_type_ok": task_type_ok,
            "primary_ticker_recall": primary_recall,
            "peer_ticker_recall_any_of": peer_recall,
            "year_compliance": year_compliance,
            "required_task_coverage": task_coverage,
            "metric_family_recall": family_recall,
            "schema_validation_pass": schema_pass,
            "source_boundary_violation": bool(source_violations),
        },
        "actual": {
            "task_type": contract.get("task_type"),
            "focus_tickers": sorted(focus_tickers),
            "planned_tickers": sorted(planned_tickers),
            "all_tickers": sorted(actual_tickers),
            "years": sorted(actual_years),
            "metric_families": sorted(family_actual),
            "planner_status": contract.get("planner_status"),
            "planner_backend": contract.get("planner_backend"),
        },
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
        "contract_row_status": contract_row.get("status") or contract_row.get("planner_status"),
    }


def _missing_contract_result(eval_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": eval_row.get("case_id"),
        "category": eval_row.get("category"),
        "query": eval_row.get("query"),
        "status": "fail",
        "metrics": {
            "task_type_ok": False,
            "primary_ticker_recall": 0.0,
            "peer_ticker_recall_any_of": 0.0,
            "year_compliance": 0.0,
            "required_task_coverage": 0.0,
            "metric_family_recall": 0.0,
            "schema_validation_pass": False,
            "source_boundary_violation": False,
        },
        "actual": {},
        "failure_count": 1,
        "warning_count": 0,
        "failures": [{"type": "missing_contract"}],
        "warnings": [],
    }


def _summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(results)
    failure_types = Counter(
        failure.get("type") for result in results for failure in result.get("failures") or []
    )
    warning_types = Counter(
        warning.get("type") for result in results for warning in result.get("warnings") or []
    )

    def mean_metric(name: str) -> float:
        if not results:
            return 0.0
        return round(sum(float((result.get("metrics") or {}).get(name) or 0.0) for result in results) / len(results), 4)

    source_violation_count = sum(1 for result in results if (result.get("metrics") or {}).get("source_boundary_violation"))
    summary = {
        "case_count": count,
        "pass_count": sum(1 for result in results if result.get("status") == "pass"),
        "fail_count": sum(1 for result in results if result.get("status") != "pass"),
        "task_type_accuracy": mean_metric("task_type_ok"),
        "primary_ticker_recall": mean_metric("primary_ticker_recall"),
        "peer_ticker_recall_any_of": mean_metric("peer_ticker_recall_any_of"),
        "required_task_coverage": mean_metric("required_task_coverage"),
        "metric_family_recall": mean_metric("metric_family_recall"),
        "year_compliance": mean_metric("year_compliance"),
        "source_boundary_violation_rate": round(_ratio(source_violation_count, count, empty_value=0.0), 4),
        "schema_validation_pass_rate": mean_metric("schema_validation_pass"),
        "failure_types": dict(sorted(failure_types.items())),
        "warning_types": dict(sorted(warning_types.items())),
    }
    summary["meets_step1_acceptance"] = _meets_thresholds(summary)
    return summary


def _meets_thresholds(summary: dict[str, Any]) -> bool:
    return (
        _float_metric(summary, "task_type_accuracy", 0.0) >= 0.85
        and _float_metric(summary, "primary_ticker_recall", 0.0) >= 0.95
        and _float_metric(summary, "peer_ticker_recall_any_of", 0.0) >= 0.75
        and _float_metric(summary, "required_task_coverage", 0.0) >= 0.85
        and _float_metric(summary, "metric_family_recall", 0.0) >= 0.75
        and _float_metric(summary, "year_compliance", 0.0) >= 1.0
        and _float_metric(summary, "source_boundary_violation_rate", 1.0) == 0.0
        and _float_metric(summary, "schema_validation_pass_rate", 0.0) >= 1.0
    )


def _float_metric(summary: dict[str, Any], key: str, default: float) -> float:
    value = summary.get(key)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _task_type_ok(contract: dict[str, Any], expected: dict[str, Any]) -> bool:
    allowed = {str(item) for item in expected.get("task_type_any_of") or []}
    return not allowed or str(contract.get("task_type") or "") in allowed


def _contract_tickers(contract: dict[str, Any], *, include_search_scope: bool) -> set[str]:
    scope = contract.get("scope") or {}
    tickers = set()
    if include_search_scope:
        for key in ("search_scope_tickers",):
            tickers.update(_upper_set(contract.get(key) or []))
        for key in ("universe_tickers",):
            tickers.update(_upper_set(scope.get(key) or []))
    for key in ("focus_tickers",):
        tickers.update(_upper_set(contract.get(key) or []))
    for key in ("focus_tickers",):
        tickers.update(_upper_set(scope.get(key) or []))
    for task in contract.get("decomposed_tasks") or []:
        if isinstance(task, dict):
            tickers.update(_ticker_mentions(_task_text(task)))
    return tickers - NON_TICKER_ACRONYMS


def _contract_metric_families(contract: dict[str, Any]) -> set[str]:
    families = set(str(item) for item in contract.get("metric_families") or [] if str(item))
    for task in contract.get("decomposed_tasks") or []:
        if isinstance(task, dict):
            families.update(str(item) for item in task.get("required_metric_families") or [] if str(item))
    return families


def _metric_family_hits(expected: set[str], actual: set[str]) -> set[str]:
    hits = set()
    for family in expected:
        accepted = METRIC_FAMILY_EQUIVALENTS.get(family, {family})
        if accepted & actual:
            hits.add(family)
    return hits


def _required_task_hits(contract: dict[str, Any], expected: dict[str, Any]) -> tuple[int, list[list[str]]]:
    tasks = contract.get("decomposed_tasks") or []
    task_texts = [_task_text(task).lower() for task in tasks if isinstance(task, dict)]
    missing: list[list[str]] = []
    hits = 0
    for terms in expected.get("required_task_terms") or []:
        term_list = [str(term) for term in terms]
        if any(_contains_term(text, term) for text in task_texts for term in term_list):
            hits += 1
        else:
            missing.append(term_list)
    return hits, missing


def _source_boundary_violations(contract: dict[str, Any], expected: dict[str, Any]) -> list[dict[str, Any]]:
    violations = []
    disallowed = [str(item) for item in expected.get("disallowed_sources") or []]
    filing_types = {str(item).upper() for item in contract.get("filing_types") or []}
    for source in disallowed:
        if source.upper() in {"10-Q", "8-K"} and source.upper() in filing_types:
            violations.append({"type": "unsupported_year_or_form", "source": source, "actual_filing_types": sorted(filing_types)})

    request_texts = _contract_request_texts(contract)
    for source in disallowed:
        aliases = SOURCE_ALIASES.get(source, (source,))
        for text in request_texts:
            lowered = text.lower()
            safe_boundary = _contains_any_alias(lowered, NEGATED_SOURCE_TERMS) or (
                _contains_any_alias(lowered, BOUNDARY_SAFE_TERMS)
                and _contains_any_alias(lowered, ("not", "no", "不得", "不", "无", "无法", "不能", "only", "仅"))
            )
            if _contains_any_alias(lowered, aliases) and not safe_boundary:
                violations.append({"type": "source_boundary_violation", "source": source, "near_text": text[:240]})
                break
    return violations


def _missing_required_gap_terms(contract: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    required = [str(item) for item in expected.get("must_have_evidence_gap_terms") or []]
    if not required:
        return []
    caveat_text = "\n".join(
        [
            json.dumps(contract.get("required_caveats") or [], ensure_ascii=False),
            json.dumps(contract.get("forbidden_claims") or [], ensure_ascii=False),
            json.dumps(contract.get("evidence_gaps") or [], ensure_ascii=False),
        ]
    ).lower()
    return [term for term in required if str(term).lower() not in caveat_text]


def _schema_validation_pass(contract: dict[str, Any]) -> bool:
    report = contract.get("query_contract_validation") or {}
    if report:
        return str(report.get("status") or "") == "pass"
    required = {"task_type", "focus_tickers", "years", "decomposed_tasks", "metric_families"}
    return not (required - set(contract))


def _contract_request_texts(contract: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("metric_queries", "qualitative_queries", "analysis_axes", "facets"):
        values.extend(str(item) for item in contract.get(key) or [])
    for task in contract.get("decomposed_tasks") or []:
        if isinstance(task, dict):
            values.append(_task_text(task))
    return [value for value in values if value.strip()]


def _task_text(task: dict[str, Any]) -> str:
    return " ".join(
        str(task.get(key) or "")
        for key in ("task_id", "question_zh", "question", "description")
    )


def _contracts_by_case(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {}
    for row in rows:
        case_id = str(
            row.get("case_id")
            or row.get("query_id")
            or (_extract_contract(row).get("case_id") if isinstance(_extract_contract(row), dict) else "")
            or (_extract_contract(row).get("contract_id") if isinstance(_extract_contract(row), dict) else "")
        )
        if case_id:
            out[case_id] = row
    return out


def _extract_contract(row: dict[str, Any]) -> dict[str, Any]:
    for key in ("query_contract", "contract", "planner_contract"):
        value = row.get(key)
        if isinstance(value, dict):
            return value
    return row


def _load_contract_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return _read_jsonl(path)
    payload = _read_json(path)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    for key in ("results", "rows", "contracts"):
        value = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def _ratio(numerator: int, denominator: int, *, empty_value: float) -> float:
    if denominator <= 0:
        return empty_value
    return min(1.0, numerator / denominator)


def _upper_set(values: Any) -> set[str]:
    return {str(item).upper().strip() for item in values or [] if str(item).strip()}


def _int_set(values: Any) -> set[int]:
    out = set()
    for item in values or []:
        try:
            out.add(int(str(item)))
        except Exception:
            pass
    return out


def _ticker_mentions(text: str) -> set[str]:
    return set(re.findall(r"\b[A-Z]{1,5}\b", str(text or "")))


def _contains_term(text: str, term: str) -> bool:
    probe = str(term or "").lower()
    if not probe:
        return False
    return probe in text


def _contains_any_alias(text: str, aliases: tuple[str, ...]) -> bool:
    lowered = str(text or "").lower()
    return any(str(alias).lower() in lowered for alias in aliases)


if __name__ == "__main__":
    main()
