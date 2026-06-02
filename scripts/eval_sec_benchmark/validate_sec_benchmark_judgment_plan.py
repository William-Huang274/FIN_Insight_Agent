from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


PROFITABILITY_FAMILIES = {"operating_income", "gross_margin", "operating_margin"}
PROXY_CAVEAT_TERMS = ("proxy", "代理", "口径", "not directly comparable", "不能直接", "不可直接", "not directly")
DEFAULT_ALLOW_NEAR_NEGATIONS = (
    "not",
    "do not",
    "does not",
    "cannot",
    "no direct",
    "未",
    "并未",
    "未证明",
    "未将",
    "没有",
    "并没有",
    "不能",
    "无法",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate SEC benchmark Judgment Plan support and downgrade contracts."
    )
    parser.add_argument("--plan-path", required=True)
    parser.add_argument(
        "--ledger-path",
        default="reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json",
    )
    parser.add_argument("--cases-path", default="eval/sec_cases/test_cases_v1.jsonl")
    parser.add_argument(
        "--rubric-path",
        default="eval/sec_cases/abstract_judgment_rubric_v0_1.json",
    )
    parser.add_argument("--trace-run-dir", action="append", default=[])
    parser.add_argument("--output-path", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plan_payload = _read_json(_resolve(args.plan_path))
    ledger = _read_json(_resolve(args.ledger_path))
    cases = {str(row.get("case_id") or ""): row for row in _read_jsonl(_resolve(args.cases_path))}
    rubric = _read_json(_resolve(args.rubric_path)) if _resolve(args.rubric_path).exists() else {}
    trace_ids = _load_trace_ids(args.trace_run_dir)

    ledger_rows_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ledger.get("rows") or []:
        ledger_rows_by_case[str(row.get("case_id") or "")].append(row)

    case_results = [
        _validate_plan(
            plan=plan,
            case=cases.get(str(plan.get("case_id") or ""), {}),
            case_rubric=(rubric.get("cases") or {}).get(str(plan.get("case_id") or ""), {}) or {},
            ledger_rows=ledger_rows_by_case.get(str(plan.get("case_id") or ""), []),
            trace_ids=trace_ids.get(str(plan.get("case_id") or ""), {"evidence_ids": set(), "object_ids": set()}),
        )
        for plan in plan_payload.get("plans") or []
        if isinstance(plan, dict)
    ]
    failure_counts = Counter(
        failure.get("type")
        for result in case_results
        for failure in result.get("failures") or []
    )
    warning_counts = Counter(
        warning.get("type")
        for result in case_results
        for warning in result.get("warnings") or []
    )
    fail_by_case = Counter(
        result.get("case_id")
        for result in case_results
        if result.get("status") == "fail"
    )
    report = {
        "schema_version": "sec_benchmark_judgment_plan_gate_v0.1",
        "plan_path": str(_resolve(args.plan_path).resolve()),
        "ledger_path": str(_resolve(args.ledger_path).resolve()),
        "cases_path": str(_resolve(args.cases_path).resolve()),
        "rubric_path": str(_resolve(args.rubric_path).resolve()),
        "trace_run_dirs": [str(_resolve(path).resolve()) for path in args.trace_run_dir],
        "can_enter_gate": not failure_counts,
        "summary": {
            "case_count": len(case_results),
            "pass_count": sum(result.get("status") == "pass" for result in case_results),
            "fail_count": sum(result.get("status") == "fail" for result in case_results),
            "driver_count": sum(int(result.get("driver_count") or 0) for result in case_results),
            "failure_types": dict(sorted(failure_counts.items())),
            "warning_types": dict(sorted(warning_counts.items())),
            "fail_by_case": dict(sorted(fail_by_case.items())),
        },
        "case_results": case_results,
    }
    output_path = _resolve(args.output_path) if args.output_path else _resolve(args.plan_path).with_name("judgment_plan_gate.json")
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


def _validate_plan(
    *,
    plan: dict[str, Any],
    case: dict[str, Any],
    case_rubric: dict[str, Any],
    ledger_rows: list[dict[str, Any]],
    trace_ids: dict[str, set[str]],
) -> dict[str, Any]:
    case_id = str(plan.get("case_id") or "")
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not case:
        failures.append({"type": "case_not_found", "case_id": case_id})
    if not ledger_rows:
        failures.append({"type": "ledger_rows_not_found", "case_id": case_id})

    metric_index = {str(row.get("metric_id") or ""): row for row in ledger_rows if row.get("metric_id")}
    ledger_evidence_ids = {
        str(row.get(key) or "")
        for row in ledger_rows
        for key in ("source_evidence_id", "object_id")
        if row.get(key)
    }
    trace_evidence_ids = set(trace_ids.get("evidence_ids") or set()) | set(trace_ids.get("object_ids") or set())
    required_groups_by_company = _required_metric_groups_by_company(case)
    main_judgment = plan.get("main_judgment") if isinstance(plan.get("main_judgment"), dict) else {}
    drivers = [driver for driver in plan.get("drivers") or [] if isinstance(driver, dict)]
    if not drivers:
        failures.append({"type": "no_drivers"})
    _validate_main_judgment(
        main_judgment=main_judgment,
        plan=plan,
        failures=failures,
    )

    seen_ranks = set()
    for index, driver in enumerate(drivers, start=1):
        _validate_driver(
            driver=driver,
            driver_index=index,
            metric_index=metric_index,
            ledger_evidence_ids=ledger_evidence_ids,
            trace_evidence_ids=trace_evidence_ids,
            trace_ids=trace_ids,
            required_groups_by_company=required_groups_by_company,
            case=case,
            failures=failures,
            warnings=warnings,
        )
        rank = driver.get("rank")
        if not isinstance(rank, int) or rank <= 0:
            failures.append({"type": "driver_rank_invalid", "driver_index": index, "rank": rank})
        elif rank in seen_ranks:
            failures.append({"type": "driver_rank_duplicate", "driver_index": index, "rank": rank})
        seen_ranks.add(rank)

    text = _plan_text(plan)
    for forbidden in case_rubric.get("forbidden_claims") or []:
        if isinstance(forbidden, dict):
            failures.extend(_forbidden_claim_failures(forbidden, text))

    return {
        "case_id": case_id,
        "status": "fail" if failures else "pass",
        "driver_count": len(drivers),
        "failures": failures,
        "warnings": warnings,
    }


def _validate_main_judgment(
    *,
    main_judgment: dict[str, Any],
    plan: dict[str, Any],
    failures: list[dict[str, Any]],
) -> None:
    strength = str(main_judgment.get("strength") or "")
    claim_type = str(main_judgment.get("claim_type") or "")
    if strength not in {"strong", "medium", "weak"}:
        failures.append({"type": "main_judgment_strength_invalid", "strength": strength})
    if claim_type not in {"ranking", "comparison", "caveated_comparison", "insufficient_evidence"}:
        failures.append({"type": "main_judgment_claim_type_invalid", "claim_type": claim_type})
    if strength == "strong" and plan.get("must_downgrade_because"):
        failures.append({"type": "main_judgment_strong_despite_downgrades"})
    if claim_type == "ranking" and plan.get("must_downgrade_because"):
        failures.append({"type": "ranking_claim_despite_downgrades"})


def _validate_driver(
    *,
    driver: dict[str, Any],
    driver_index: int,
    metric_index: dict[str, dict[str, Any]],
    ledger_evidence_ids: set[str],
    trace_evidence_ids: set[str],
    trace_ids: dict[str, set[str]],
    required_groups_by_company: dict[str, list[set[str]]],
    case: dict[str, Any],
    failures: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    metric_ids = _string_list(driver.get("supporting_metric_ids"))
    evidence_ids = _string_list(driver.get("supporting_evidence_ids"))
    if not metric_ids and not evidence_ids:
        failures.append({"type": "driver_without_support", "driver_index": driver_index})

    rows = []
    for metric_id in metric_ids:
        row = metric_index.get(metric_id)
        if not row:
            failures.append(
                {"type": "supporting_metric_id_not_in_case_ledger", "driver_index": driver_index, "metric_id": metric_id}
            )
        else:
            rows.append(row)
    allowed_evidence_ids = ledger_evidence_ids | trace_evidence_ids
    for evidence_id in evidence_ids:
        if evidence_id not in allowed_evidence_ids:
            failures.append(
                {
                    "type": "supporting_evidence_id_not_in_case_ledger_or_trace",
                    "driver_index": driver_index,
                    "evidence_id": evidence_id,
                }
            )
        if (trace_ids.get("evidence_ids") or trace_ids.get("object_ids")) and evidence_id not in trace_ids["evidence_ids"] and evidence_id not in trace_ids["object_ids"]:
            warnings.append(
                {"type": "supporting_evidence_id_not_seen_in_trace", "driver_index": driver_index, "evidence_id": evidence_id}
            )

    supported_companies = {str(row.get("ticker") or "") for row in rows if row.get("ticker")}
    supported_years = {int(row.get("fiscal_year")) for row in rows if _is_int_like(row.get("fiscal_year"))}
    supported_families = {str(row.get("metric_family") or "") for row in rows if row.get("metric_family")}
    declared_companies = set(_string_list(driver.get("covered_companies")))
    declared_years = {int(item) for item in driver.get("covered_years") or [] if _is_int_like(item)}
    declared_families = set(_string_list(driver.get("metric_families")))

    if rows and not declared_companies.issubset(supported_companies):
        failures.append(
            {
                "type": "driver_declares_unsupported_companies",
                "driver_index": driver_index,
                "declared": sorted(declared_companies),
                "supported": sorted(supported_companies),
            }
        )
    if rows and not declared_years.issubset(supported_years):
        failures.append(
            {
                "type": "driver_declares_unsupported_years",
                "driver_index": driver_index,
                "declared": sorted(declared_years),
                "supported": sorted(supported_years),
            }
        )
    if rows and not declared_families.issubset(supported_families):
        failures.append(
            {
                "type": "driver_declares_unsupported_metric_families",
                "driver_index": driver_index,
                "declared": sorted(declared_families),
                "supported": sorted(supported_families),
            }
        )

    strength = str(driver.get("conclusion_strength") or "")
    if strength not in {"strong", "medium", "weak"}:
        failures.append({"type": "driver_conclusion_strength_invalid", "driver_index": driver_index, "strength": strength})
    caveat_text = " ".join(str(item) for item in driver.get("caveats") or [])
    has_proxy = any("proxy" in family.lower() for family in supported_families | declared_families)
    if has_proxy:
        if strength == "strong":
            failures.append({"type": "proxy_driver_marked_strong", "driver_index": driver_index})
        if not _contains_any(caveat_text, PROXY_CAVEAT_TERMS):
            failures.append({"type": "proxy_driver_missing_caveat", "driver_index": driver_index})

    prompt_text = _case_contract_text(case).lower()
    needs_profitability = any(token in prompt_text for token in ["operating income", "margin", "profitability", "毛利", "利润"])
    has_profitability = bool((supported_families | declared_families) & PROFITABILITY_FAMILIES)
    if needs_profitability and not has_profitability:
        if strength == "strong":
            failures.append({"type": "missing_profitability_driver_marked_strong", "driver_index": driver_index})
        if not caveat_text:
            failures.append({"type": "missing_profitability_driver_missing_caveat", "driver_index": driver_index})

    for company in supported_companies | declared_companies:
        missing_groups = [
            sorted(group)
            for group in required_groups_by_company.get(company, [])
            if group and not ((supported_families | declared_families) & group)
        ]
        if missing_groups:
            if strength == "strong":
                failures.append(
                    {
                        "type": "missing_required_metric_family_driver_marked_strong",
                        "driver_index": driver_index,
                        "company": company,
                        "missing_groups": missing_groups,
                    }
                )
            if not caveat_text:
                failures.append(
                    {
                        "type": "missing_required_metric_family_driver_missing_caveat",
                        "driver_index": driver_index,
                        "company": company,
                        "missing_groups": missing_groups,
                    }
                )


def _required_metric_groups_by_company(case: dict[str, Any]) -> dict[str, list[set[str]]]:
    groups_by_company: dict[str, list[set[str]]] = defaultdict(list)
    for check in case.get("numeric_checks") or []:
        if not isinstance(check, dict):
            continue
        families = {str(item) for item in check.get("metric_families") or [] if item}
        if not families:
            continue
        for company in check.get("companies") or []:
            groups_by_company[str(company)].append(families)
    return groups_by_company


def _forbidden_claim_failures(forbidden: dict[str, Any], text: str) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    patterns = [str(pattern) for pattern in forbidden.get("patterns") or []]
    allow_any = [str(pattern) for pattern in forbidden.get("allow_if_any") or []]
    allow_near = [str(pattern) for pattern in forbidden.get("allow_if_any_near") or []]
    if allow_near:
        allow_near = list(dict.fromkeys([*allow_near, *DEFAULT_ALLOW_NEAR_NEGATIONS]))
    window = int(forbidden.get("near_window_chars", 80))
    for pattern in patterns:
        for match in _pattern_finditer(pattern, text):
            if allow_any and any(_pattern_matches(allow, text) for allow in allow_any):
                continue
            near_text = text[max(0, match.start() - window) : min(len(text), match.end() + window)]
            if allow_near and any(_pattern_matches(allow, near_text) for allow in allow_near):
                continue
            failures.append(
                {
                    "type": "forbidden_claim_in_judgment_plan",
                    "claim_id": str(forbidden.get("id") or ""),
                    "pattern": pattern,
                    "near_text": near_text,
                }
            )
    return failures


def _pattern_matches(pattern: str, text: str) -> bool:
    return next(_pattern_finditer(pattern, text), None) is not None


def _pattern_finditer(pattern: str, text: str) -> Any:
    if pattern.startswith("re:"):
        try:
            yield from re.finditer(pattern[3:], text, flags=re.I)
        except re.error:
            return
    else:
        escaped = re.escape(pattern)
        yield from re.finditer(escaped, text, flags=re.I)


def _load_trace_ids(trace_run_dirs: list[str]) -> dict[str, dict[str, set[str]]]:
    ids_by_case: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"evidence_ids": set(), "object_ids": set()})
    for run_dir in trace_run_dirs:
        trace_path = _resolve(run_dir) / "trace_logs.jsonl"
        if not trace_path.exists():
            continue
        for row in _read_jsonl(trace_path):
            case_id = str(row.get("case_id") or "")
            for context in row.get("context_rows") or []:
                if not isinstance(context, dict):
                    continue
                evidence_id = str(context.get("evidence_id") or "")
                object_id = str(context.get("object_id") or "")
                if evidence_id:
                    ids_by_case[case_id]["evidence_ids"].add(evidence_id)
                if object_id:
                    ids_by_case[case_id]["object_ids"].add(object_id)
    return ids_by_case


def _plan_text(plan: dict[str, Any]) -> str:
    fragments = []

    def walk(value: Any, key: str = "") -> None:
        if key in {"do_not_overstate", "plan_validator_expectations", "must_downgrade_because"}:
            return
        if isinstance(value, dict):
            for child_key, child in value.items():
                walk(child, str(child_key))
        elif isinstance(value, list):
            for child in value:
                walk(child, key)
        else:
            fragments.append(str(value))

    walk(plan)
    return "\n".join(fragments)


def _case_contract_text(case: dict[str, Any]) -> str:
    return " ".join(
        [
            str(case.get("prompt") or ""),
            str(case.get("task_type") or ""),
            " ".join(str(item) for item in case.get("gold_points") or []),
            " ".join(str(item) for item in case.get("hallucination_traps") or []),
        ]
    )


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if value:
        return [str(value)]
    return []


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _resolve(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def _is_int_like(value: Any) -> bool:
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    main()
