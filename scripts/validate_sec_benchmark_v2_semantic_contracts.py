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


V2_FAILURE_TYPES = {
    "decomposed_task_coverage",
    "proxy_as_direct_metric",
    "non_comparable_metric_comparison",
    "prior_period_as_target_value",
    "percentage_change_as_absolute_value",
    "entity_bleed_between_peers",
    "required_not_found_missing",
    "source_policy_violation",
}

PROXY_OR_VISIBILITY_METRIC_FAMILIES = {
    "arr_or_recurring_proxy",
    "billings",
    "capital_expenditure_proxy",
    "cloud_revenue_proxy",
    "deferred_revenue",
    "fcf_proxy",
    "free_cash_flow_proxy",
    "rpo",
}

TICKER_ALIASES = {
    "AAPL": ("AAPL", "Apple", "苹果"),
    "ADBE": ("ADBE", "Adobe"),
    "AMD": ("AMD", "Advanced Micro Devices"),
    "AMZN": ("AMZN", "Amazon", "AWS"),
    "GOOGL": ("GOOGL", "Alphabet", "Google", "YouTube"),
    "META": ("META", "Meta", "Facebook", "Instagram", "Reality Labs", "Family of Apps", "FoA"),
    "MSFT": ("MSFT", "Microsoft", "微软"),
    "NVDA": ("NVDA", "NVIDIA", "Nvidia", "英伟达"),
    "PANW": ("PANW", "Palo Alto", "Palo Alto Networks"),
    "SNOW": ("SNOW", "Snowflake"),
}

OFF_SCOPE_ENTITY_OWNER = {
    "youtube": "GOOGL",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "aws": "AMZN",
    "amazon": "AMZN",
    "instagram": "META",
    "facebook": "META",
}

REFUSAL_TERMS = (
    "not found",
    "not disclosed",
    "cannot",
    "can't",
    "not available",
    "不属于",
    "不是",
    "不能",
    "无法",
    "未披露",
    "未提供",
    "未找到",
)
MISMATCH_TERMS = (
    "wrong attribution",
    "wrong company",
    "not a microsoft",
    "not microsoft",
    "不属于",
    "不是 microsoft",
    "不是 msft",
    "公司不匹配",
    "主体不匹配",
)
PROXY_CAVEAT_TERMS = (
    "proxy",
    "代理",
    "广义",
    "口径",
    "not directly",
    "not equivalent",
    "not the same",
    "separate",
    "different",
    "不能直接",
    "不可直接",
    "不同",
    "不等同",
    "并非",
    "区分",
    "严格区分",
)
NEGATION_TERMS = (
    "not",
    "cannot",
    "can't",
    "do not",
    "does not",
    "不是",
    "不",
    "不能",
    "无法",
    "未",
    "并非",
)
COMPARABILITY_TERMS = (
    "not directly comparable",
    "not comparable",
    "口径",
    "不完全可比",
    "不能直接比较",
    "不可直接比较",
    "definition",
    "changed",
    "recast",
    "合并",
    "变化",
)
DIRECT_COMPARABLE_PATTERNS = (
    r"分部口径完全可比",
    r"segment labels are directly identical",
    r"directly comparable",
    r"直接可比",
)
TREND_LEVEL_TERMS = (
    "from",
    "to",
    "reached",
    "grew to",
    "increased to",
    "decreased to",
    "增长至",
    "增至",
    "降至",
    "达到",
    "为",
)
CHANGE_ROLE_TERMS = (
    "change",
    "% change",
    "increase",
    "decrease",
    "growth",
    "增长",
    "下降",
    "变化",
    "同比",
)
DOLLAR_OR_AMOUNT_TERMS = (
    "$",
    "美元",
    "million",
    "billion",
    "金额",
    "amount",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate v2 SEC benchmark semantic contracts such as peer separation, proxy caveats, and source policy."
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--cases-path", default="eval/sec_cases/test_cases_v1.jsonl")
    parser.add_argument(
        "--ledger-path",
        default="reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json",
    )
    parser.add_argument("--output-path", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = _resolve(args.run_dir)
    cases = {str(row.get("case_id") or ""): row for row in _read_jsonl(_resolve(args.cases_path))}
    ledger_rows = _read_json(_resolve(args.ledger_path)).get("rows") or []
    ledger_by_case: dict[str, list[dict[str, Any]]] = {}
    for row in ledger_rows:
        ledger_by_case.setdefault(str(row.get("case_id") or ""), []).append(row)

    results = [
        _validate_agent_row(
            row,
            cases.get(str(row.get("case_id") or ""), {}),
            ledger_by_case.get(str(row.get("case_id") or ""), []),
        )
        for row in _read_jsonl(run_dir / "agent_outputs.jsonl")
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
    checked = [result for result in results if result.get("status") != "skipped"]
    report = {
        "schema_version": "sec_benchmark_v2_semantic_contract_gate_v0.1",
        "run_dir": str(run_dir.resolve()),
        "cases_path": str(_resolve(args.cases_path).resolve()),
        "ledger_path": str(_resolve(args.ledger_path).resolve()),
        "can_enter_gate": not failure_counts,
        "summary": {
            "case_count": len(results),
            "checked_case_count": len(checked),
            "pass_count": sum(result.get("status") == "pass" for result in results),
            "fail_count": sum(result.get("status") == "fail" for result in results),
            "skip_count": sum(result.get("status") == "skipped" for result in results),
            "active_check_counts": dict(
                sorted(
                    Counter(
                        check
                        for result in checked
                        for check in result.get("active_checks") or []
                    ).items()
                )
            ),
            "failure_types": dict(sorted(failure_counts.items())),
            "warning_types": dict(sorted(warning_counts.items())),
            "fail_by_case": dict(sorted(fail_by_case.items())),
        },
        "case_results": results,
    }
    output_path = _resolve(args.output_path) if args.output_path else run_dir / "v2_semantic_contract_gate.json"
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


def _validate_agent_row(agent: dict[str, Any], case: dict[str, Any], ledger_rows: list[dict[str, Any]]) -> dict[str, Any]:
    case_id = str(agent.get("case_id") or "")
    mode = str(agent.get("mode") or "")
    active_checks = _active_checks(case, ledger_rows)
    if not active_checks:
        return {
            "case_id": case_id,
            "mode": mode,
            "status": "skipped",
            "reason": "no_v2_semantic_contract_checks",
            "active_checks": [],
            "failures": [],
            "warnings": [],
        }
    if str(agent.get("status") or "") != "answered" or not isinstance(agent.get("answer"), dict):
        return {
            "case_id": case_id,
            "mode": mode,
            "answer_status": agent.get("answer_status"),
            "status": "skipped",
            "reason": "agent_output_not_answered_or_answer_not_object",
            "active_checks": sorted(active_checks),
            "failures": [],
            "warnings": [],
        }

    answer = agent.get("answer") or {}
    text = _answer_text(answer)
    locations = _answer_support_locations(answer)
    metric_rows = {
        str(row.get("metric_id") or ""): row
        for row in ledger_rows
        if str(row.get("metric_id") or "")
    }
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if "source_policy_violation" in active_checks:
        _check_source_policy(case, answer, text, failures, warnings)
    if "required_not_found_missing" in active_checks:
        _check_required_not_found(case, text, failures, warnings)
    if "entity_bleed_between_peers" in active_checks:
        _check_peer_entity_separation(case, text, locations, failures, warnings)
    if "decomposed_task_coverage" in active_checks:
        _check_decomposed_task_coverage(case, text, locations, metric_rows, failures, warnings)
    if "proxy_as_direct_metric" in active_checks:
        _check_proxy_as_direct(case, text, locations, metric_rows, failures, warnings)
    if "non_comparable_metric_comparison" in active_checks:
        _check_non_comparable_metric(case, text, failures, warnings)
    if "prior_period_as_target_value" in active_checks or "percentage_change_as_absolute_value" in active_checks:
        _check_metric_role_target_values(locations, metric_rows, active_checks, failures, warnings)

    return {
        "case_id": case_id,
        "mode": mode,
        "answer_status": agent.get("answer_status"),
        "status": "fail" if failures else "pass",
        "active_checks": sorted(active_checks),
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
    }


def _active_checks(case: dict[str, Any], ledger_rows: list[dict[str, Any]]) -> set[str]:
    failures = {str(item) for item in case.get("failure_types") or []}
    active = failures & V2_FAILURE_TYPES
    companies = {str(item).upper() for item in case.get("companies") or []}
    task_type = str(case.get("task_type") or "")
    prompt_blob = _case_policy_text(case).lower()
    query_contract = _query_contract(case)
    if query_contract:
        if _requires_entity_bleed_check(case, query_contract):
            active.add("entity_bleed_between_peers")
        if query_contract.get("decomposed_tasks"):
            active.add("decomposed_task_coverage")
    elif len(companies) >= 2 and re.search(r"peer|comparison|compare|对比|比较", task_type + " " + prompt_blob, re.I):
        active.add("entity_bleed_between_peers")
    if task_type.startswith("anti_hallucination") or "wrong_company" in failures or "wrong attribution" in prompt_blob:
        active.add("source_policy_violation")
    if case.get("required_not_found") or "required_not_found_missing" in failures:
        active.add("required_not_found_missing")
    ledger_families = {str(row.get("metric_family") or "").lower() for row in ledger_rows}
    if (
        "proxy" in prompt_blob
        or any("proxy" in family for family in ledger_families)
        or bool(ledger_families & PROXY_OR_VISIBILITY_METRIC_FAMILIES)
    ):
        active.add("proxy_as_direct_metric")
    if any(str(row.get("metric_role") or "") == "period_change_amount" for row in ledger_rows):
        active.add("prior_period_as_target_value")
    if any(str(row.get("metric_role") or "") == "percentage_rate" for row in ledger_rows):
        active.add("percentage_change_as_absolute_value")
    return active


def _query_contract(case: dict[str, Any]) -> dict[str, Any]:
    contract = case.get("query_contract")
    return contract if isinstance(contract, dict) else {}


def _requires_entity_bleed_check(case: dict[str, Any], query_contract: dict[str, Any]) -> bool:
    gate = query_contract.get("semantic_gate") if isinstance(query_contract.get("semantic_gate"), dict) else {}
    if gate.get("require_company_coverage") is True:
        return True
    if str(gate.get("company_coverage") or "") in {"all_companies", "all_focus", "selected_companies"}:
        return True
    task_type = str(query_contract.get("task_type") or case.get("task_type") or "")
    if task_type.startswith("peer_comparison") or task_type == "company_comparison":
        return True
    focus = [str(item).upper() for item in query_contract.get("focus_tickers") or []]
    prompt_text = str(case.get("prompt") or "")
    if 2 <= len(focus) <= 8 and re.search(r"compare|comparison|versus|\\bvs\\b|对比|比较|相比", prompt_text, re.I):
        return True
    return False


def _company_coverage_mode(case: dict[str, Any]) -> str:
    query_contract = _query_contract(case)
    gate = query_contract.get("semantic_gate") if isinstance(query_contract.get("semantic_gate"), dict) else {}
    return str(gate.get("company_coverage") or "")


def _requires_full_company_coverage(case: dict[str, Any]) -> bool:
    query_contract = _query_contract(case)
    if not query_contract:
        return True
    gate = query_contract.get("semantic_gate") if isinstance(query_contract.get("semantic_gate"), dict) else {}
    if gate.get("require_company_coverage") is True:
        return True
    if not gate.get("company_coverage") and str(query_contract.get("task_type") or case.get("task_type") or "").startswith("peer_comparison"):
        return True
    return _company_coverage_mode(case) in {"all_companies", "all_focus"}


def _semantic_required_companies(case: dict[str, Any]) -> set[str]:
    query_contract = _query_contract(case)
    if query_contract:
        gate = query_contract.get("semantic_gate") if isinstance(query_contract.get("semantic_gate"), dict) else {}
        if str(gate.get("company_coverage") or "") == "all_companies":
            return {str(item).upper() for item in case.get("companies") or []}
        focus = {str(item).upper() for item in query_contract.get("focus_tickers") or []}
        if focus:
            return focus
    return {str(item).upper() for item in case.get("companies") or []}


def _check_source_policy(
    case: dict[str, Any],
    answer: dict[str, Any],
    text: str,
    failures: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    lowered = text.lower()
    prompt = str(case.get("prompt") or "").lower()
    case_companies = {str(item).upper() for item in case.get("companies") or []}
    off_scope_terms = [
        term
        for term, owner in OFF_SCOPE_ENTITY_OWNER.items()
        if term in prompt and owner not in case_companies
    ]
    has_refusal = _contains_any(lowered, REFUSAL_TERMS)
    has_mismatch = _contains_any(lowered, MISMATCH_TERMS)
    if off_scope_terms and not (has_refusal and has_mismatch):
        failures.append(
            {
                "type": "source_policy_violation",
                "reason": "wrong_attribution_trap_without_explicit_refusal",
                "off_scope_terms": off_scope_terms,
            }
        )
    support_tickers = _support_tickers_from_answer(answer)
    outside_support = sorted(support_tickers - case_companies)
    if outside_support:
        failures.append(
            {
                "type": "source_policy_violation",
                "reason": "answer_uses_support_outside_case_companies",
                "outside_support_tickers": outside_support,
            }
        )
    for term in off_scope_terms:
        for match in re.finditer(re.escape(term), lowered):
            near = text[max(0, match.start() - 80) : min(len(text), match.end() + 100)]
            if _has_numeric_amount(near) and not _contains_any(near.lower(), REFUSAL_TERMS):
                failures.append(
                    {
                        "type": "source_policy_violation",
                        "reason": "numeric_amount_near_off_scope_entity",
                        "term": term,
                        "near_text": near,
                    }
                )
    if not off_scope_terms and str(case.get("source_policy") or "") == "SEC_ONLY":
        warnings.append({"type": "source_policy_gate_active_without_detected_off_scope_entity"})


def _check_required_not_found(
    case: dict[str, Any],
    text: str,
    failures: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    specs = [item for item in case.get("required_not_found") or [] if isinstance(item, dict)]
    if not specs:
        warnings.append({"type": "required_not_found_check_active_without_specs"})
        return
    for spec in specs:
        missing_groups = []
        matched_groups = []
        for group in spec.get("all_of_any") or []:
            patterns = [str(item) for item in group]
            matched = [pattern for pattern in patterns if _pattern_present(pattern, text)]
            if matched:
                matched_groups.append({"patterns": patterns, "matched": matched})
            else:
                missing_groups.append(patterns)
        if missing_groups:
            failures.append(
                {
                    "type": "required_not_found_missing",
                    "reason": "required_not_found_statement_not_covered",
                    "required_not_found_id": str(spec.get("id") or ""),
                    "description": str(spec.get("description") or ""),
                    "missing_groups": missing_groups,
                    "matched_groups": matched_groups,
                }
            )


def _check_peer_entity_separation(
    case: dict[str, Any],
    text: str,
    locations: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    case_companies = _semantic_required_companies(case)
    allowed_support_companies = {str(item).upper() for item in case.get("companies") or []}
    if not case_companies:
        warnings.append({"type": "entity_bleed_check_active_without_required_companies"})
        return
    mentioned_in_answer = _mentioned_case_companies(text, case_companies)
    missing_mentions = sorted(case_companies - mentioned_in_answer)
    if _requires_full_company_coverage(case) and missing_mentions:
        failures.append(
            {
                "type": "entity_bleed_between_peers",
                "reason": "peer_case_missing_company_mention",
                "missing_companies": missing_mentions,
            }
        )
    elif missing_mentions:
        warnings.append(
            {
                "type": "selected_company_coverage_not_all_focus_tickers",
                "missing_companies": missing_mentions,
                "company_coverage": _company_coverage_mode(case) or "selected_companies",
            }
        )
    for location in locations:
        support_tickers = set(location.get("support_tickers") or [])
        if not support_tickers:
            continue
        outside_support = sorted(support_tickers - allowed_support_companies)
        if outside_support:
            failures.append(
                {
                    "type": "entity_bleed_between_peers",
                    "reason": "support_ticker_outside_peer_case",
                    "location": location["location"],
                    "outside_support_tickers": outside_support,
                }
            )
        mentioned = _mentioned_case_companies(str(location.get("text") or ""), case_companies)
        if len(mentioned) == 1:
            other_support = sorted(support_tickers - mentioned)
            if other_support:
                failures.append(
                    {
                        "type": "entity_bleed_between_peers",
                        "reason": "single_entity_claim_uses_other_entity_support",
                        "location": location["location"],
                        "mentioned_companies": sorted(mentioned),
                        "support_tickers": sorted(support_tickers),
                        "near_text": str(location.get("text") or "")[:260],
                    }
                )
        if len(mentioned) >= 2 and len(support_tickers & case_companies) == 1:
            warnings.append(
                {
                    "type": "one_sided_peer_comparison_support",
                    "location": location["location"],
                    "mentioned_companies": sorted(mentioned),
                    "support_tickers": sorted(support_tickers),
                    "near_text": str(location.get("text") or "")[:260],
                }
            )


def _check_decomposed_task_coverage(
    case: dict[str, Any],
    text: str,
    locations: list[dict[str, Any]],
    metric_rows: dict[str, dict[str, Any]],
    failures: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    query_contract = _query_contract(case)
    tasks = [task for task in query_contract.get("decomposed_tasks") or [] if isinstance(task, dict)]
    if not tasks:
        warnings.append({"type": "decomposed_task_coverage_active_without_tasks"})
        return
    supported_families = set()
    for location in locations:
        for metric_id in location.get("metric_ids") or []:
            row = metric_rows.get(str(metric_id))
            family = str((row or {}).get("metric_family") or "")
            if family:
                supported_families.add(family)
    covered = []
    missing_primary = []
    for task in tasks:
        families = {str(item) for item in task.get("required_metric_families") or [] if str(item)}
        task_id = str(task.get("task_id") or "")
        if families and supported_families & families:
            covered.append(task_id)
            continue
        item = {
            "task_id": task_id,
            "priority": str(task.get("priority") or ""),
            "required_metric_families": sorted(families),
            "question_zh": str(task.get("question_zh") or "")[:220],
        }
        if str(task.get("priority") or "") == "primary":
            missing_primary.append(item)
    gate = query_contract.get("semantic_gate") if isinstance(query_contract.get("semantic_gate"), dict) else {}
    strict = bool(gate.get("strict_decomposed_task_coverage"))
    if strict and missing_primary:
        failures.append(
            {
                "type": "decomposed_task_coverage",
                "reason": "primary_decomposed_tasks_missing_supported_metric_families",
                "missing_primary_tasks": missing_primary,
                "supported_metric_families": sorted(supported_families),
            }
        )
    elif missing_primary:
        warnings.append(
            {
                "type": "decomposed_task_coverage_missing_primary_tasks",
                "missing_primary_tasks": missing_primary,
                "covered_task_ids": covered,
                "supported_metric_families": sorted(supported_families),
            }
        )
    else:
        warnings.append(
            {
                "type": "decomposed_task_coverage_checked",
                "covered_task_ids": covered,
                "supported_metric_families": sorted(supported_families),
            }
        )


def _check_proxy_as_direct(
    case: dict[str, Any],
    text: str,
    locations: list[dict[str, Any]],
    metric_rows: dict[str, dict[str, Any]],
    failures: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    for location in locations:
        location_text = str(location.get("text") or "")
        caveat_text = location_text + "\n" + _nearby_answer_caveat_text(text)
        for metric_id in location.get("metric_ids") or []:
            row = metric_rows.get(metric_id)
            metric_family = str((row or {}).get("metric_family") or metric_id)
            if "proxy" not in metric_family.lower() and "proxy" not in metric_id.lower():
                continue
            if not _contains_any(caveat_text.lower(), PROXY_CAVEAT_TERMS):
                failures.append(
                    {
                        "type": "proxy_as_direct_metric",
                        "reason": "proxy_metric_used_without_local_caveat",
                        "location": location["location"],
                        "metric_id": metric_id,
                        "near_text": location_text[:260],
                    }
                )
    lower = text.lower()
    risky_patterns = [
        (r"(services revenue|services net sales|服务收入).{0,40}(subscription|订阅)", "services_as_subscription"),
        (r"(gross margin|毛利率).{0,50}(visibility|可见性|contract visibility|合同可见)", "margin_as_visibility"),
        (
            r"(rpo|billings|账单额|deferred revenue|递延收入).{0,40}"
            r"(recognized revenue|已确认收入|确认收入|作为收入|等同于收入|直接收入)",
            "visibility_metric_as_revenue",
        ),
    ]
    for pattern, reason in risky_patterns:
        for match in re.finditer(pattern, lower, flags=re.I | re.S):
            near = text[max(0, match.start() - 80) : min(len(text), match.end() + 120)]
            if not _contains_any(near.lower(), NEGATION_TERMS + PROXY_CAVEAT_TERMS):
                failures.append(
                    {
                        "type": "proxy_as_direct_metric",
                        "reason": reason,
                        "near_text": near,
                    }
                )
    if "proxy_as_direct_metric" in set(case.get("failure_types") or []) and not failures:
        warnings.append({"type": "proxy_direct_contract_checked_no_violation"})


def _check_non_comparable_metric(
    case: dict[str, Any],
    text: str,
    failures: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    lower = text.lower()
    for pattern in DIRECT_COMPARABLE_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.I):
            near = text[max(0, match.start() - 80) : min(len(text), match.end() + 120)]
            if not _contains_any(near.lower(), NEGATION_TERMS):
                failures.append(
                    {
                        "type": "non_comparable_metric_comparison",
                        "reason": "direct_comparability_claim_without_negation",
                        "near_text": near,
                    }
                )
    case_requires_caveat = "non_comparable_metric_comparison" in set(case.get("failure_types") or [])
    has_comparison = bool(re.search(r"compare|comparison|trend|changed|direct|比较|对比|趋势|变化|合并", lower, flags=re.I))
    if case_requires_caveat and has_comparison and not _contains_any(lower, COMPARABILITY_TERMS):
        failures.append(
            {
                "type": "non_comparable_metric_comparison",
                "reason": "comparison_case_missing_comparability_caveat",
            }
        )
    elif case_requires_caveat:
        warnings.append({"type": "non_comparable_metric_contract_checked_no_violation"})


def _check_metric_role_target_values(
    locations: list[dict[str, Any]],
    metric_rows: dict[str, dict[str, Any]],
    active_checks: set[str],
    failures: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    checked_prior = 0
    checked_percent = 0
    for location in locations:
        location_text = str(location.get("text") or "")
        lower = location_text.lower()
        metric_ids = [metric_id for metric_id in location.get("metric_ids") or [] if metric_id in metric_rows]
        has_amount_metric_support = any(
            str(metric_rows[metric_id].get("metric_role") or "") != "percentage_rate"
            and str(metric_rows[metric_id].get("unit") or "") != "percent"
            for metric_id in metric_ids
        )
        for metric_id in metric_ids:
            row = metric_rows[metric_id]
            role = str(row.get("metric_role") or "")
            unit = str(row.get("unit") or "")
            if role == "period_change_amount":
                checked_prior += 1
                if _contains_any(lower, TREND_LEVEL_TERMS) and not _contains_any(lower, CHANGE_ROLE_TERMS):
                    failures.append(
                        {
                            "type": "prior_period_as_target_value",
                            "reason": "period_change_metric_used_as_level_value",
                            "location": location["location"],
                            "metric_id": metric_id,
                            "near_text": location_text[:260],
                        }
                    )
            if role == "percentage_rate" or unit == "percent":
                checked_percent += 1
                metric_near_text = _near_metric_id_text(location_text, metric_id, before=48, after=64)
                metric_near_text = _metric_id_clause_text(metric_near_text, metric_id)
                metric_near_lower = metric_near_text.lower()
                mentions_percentage_metric = (
                    re.search(r"gross margin|毛利率|rate|percentage|percent|%", metric_near_lower) is not None
                )
                if not mentions_percentage_metric:
                    continue
                uses_amount_language = _contains_any(metric_near_lower, DOLLAR_OR_AMOUNT_TERMS) and not _contains_any(
                    metric_near_lower, NEGATION_TERMS
                )
                if uses_amount_language and has_amount_metric_support and _metric_value_text_present(row, location_text):
                    uses_amount_language = False
                if uses_amount_language and re.search(
                    r"net revenue retention|revenue retention rate|net_revenue_retention", metric_near_lower
                ):
                    has_explicit_amount_marker = re.search(
                        r"\$|美元|million|billion|金额|amount|revenue dollars|收入金额",
                        metric_near_lower,
                    ) is not None
                    if not has_explicit_amount_marker:
                        uses_amount_language = False
                if uses_amount_language and not re.search(
                    r"not revenue|not.*amount|不是收入|不能.*收入|不.*金额",
                    metric_near_lower,
                ):
                    failures.append(
                        {
                            "type": "percentage_change_as_absolute_value",
                            "reason": "percentage_metric_used_as_amount",
                            "location": location["location"],
                            "metric_id": metric_id,
                            "near_text": metric_near_text[:260],
                        }
                    )
    if "prior_period_as_target_value" in active_checks and checked_prior == 0:
        warnings.append({"type": "prior_period_target_value_check_active_without_period_change_support"})
    if "percentage_change_as_absolute_value" in active_checks and checked_percent == 0:
        warnings.append({"type": "percentage_change_absolute_value_check_active_without_percentage_support"})


def _metric_value_text_present(row: dict[str, Any], text: str) -> bool:
    haystack = str(text or "")
    candidates = [
        str(row.get("display_value_zh") or ""),
        str(row.get("raw_value_text") or ""),
    ]
    value = row.get("value")
    if value is not None:
        try:
            numeric = float(value)
            candidates.extend(
                [
                    f"{numeric:g}%",
                    f"{numeric:g} %",
                    f"{numeric:.1f}%",
                    f"{numeric:.1f} %",
                ]
            )
        except Exception:
            pass
    return any(candidate and candidate in haystack for candidate in candidates)


def _answer_support_locations(answer: dict[str, Any]) -> list[dict[str, Any]]:
    locations: list[dict[str, Any]] = []
    for index, driver in enumerate(answer.get("decision_drivers") or [], start=1):
        if not isinstance(driver, dict):
            continue
        text = " ".join(
            str(driver.get(key) or "")
            for key in ("driver_claim", "why_it_matters", "caveat", "conclusion_strength")
        )
        metric_ids = _string_list(driver.get("supporting_metric_ids"))
        evidence_ids = _string_list(driver.get("supporting_evidence_ids"))
        locations.append(
            {
                "location": f"decision_drivers[{index}]",
                "text": text,
                "metric_ids": metric_ids,
                "evidence_ids": evidence_ids,
                "support_tickers": sorted(_tickers_from_ids(metric_ids + evidence_ids)),
            }
        )
    for index, point in enumerate(answer.get("key_points") or [], start=1):
        if not isinstance(point, dict):
            continue
        text = str(point.get("point") or "")
        metric_ids = _string_list(point.get("metric_ids"))
        evidence_ids = _string_list(point.get("evidence_ids"))
        locations.append(
            {
                "location": f"key_points[{index}]",
                "text": text,
                "metric_ids": metric_ids,
                "evidence_ids": evidence_ids,
                "support_tickers": sorted(_tickers_from_ids(metric_ids + evidence_ids)),
            }
        )
    return locations


def _answer_text(answer: dict[str, Any]) -> str:
    parts = [str(answer.get("summary") or "")]
    for location in _answer_support_locations(answer):
        parts.append(str(location.get("text") or ""))
    parts.extend(_memo_text_parts(answer))
    parts.extend(str(item) for item in answer.get("not_found") or [])
    parts.extend(str(item) for item in answer.get("limitations") or [])
    parts.extend(str(item) for item in answer.get("source_limitations") or [])
    cell_table = answer.get("cell_table")
    if isinstance(cell_table, dict):
        for cell in cell_table.get("cells") or []:
            if isinstance(cell, dict):
                parts.append(
                    " ".join(
                        str(cell.get(key) or "")
                        for key in ("ticker", "metric_name", "display_value_zh", "metric_id")
                    )
                )
    return "\n".join(part for part in parts if part)


def _memo_text_parts(answer: dict[str, Any]) -> list[str]:
    sections: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("what_changed", ("claim", "confidence")),
        ("why_it_matters", ("insight", "business_implication", "confidence", "caveat")),
        ("peer_readthrough", ("peer_or_group", "role", "readthrough", "caveat")),
        ("counterarguments", ("claim", "why_it_could_weaken_thesis", "confidence", "caveat")),
        ("watch_items", ("item", "why_it_matters", "source_to_watch", "metric_family")),
    )
    parts: list[str] = []
    for section, keys in sections:
        for item in answer.get(section) or []:
            if not isinstance(item, dict):
                continue
            parts.append(" ".join(str(item.get(key) or "") for key in keys))
    return parts


def _case_policy_text(case: dict[str, Any]) -> str:
    chunks = [str(case.get("task_type") or ""), str(case.get("prompt") or ""), str(case.get("test_objective") or "")]
    for key in ("gold_points", "hallucination_traps", "hard_gates", "failure_types"):
        chunks.extend(str(item) for item in case.get(key) or [])
    for caveat in case.get("required_caveats") or []:
        chunks.append(json.dumps(caveat, ensure_ascii=False) if isinstance(caveat, dict) else str(caveat))
    return "\n".join(chunks)


def _mentioned_case_companies(text: str, case_companies: set[str]) -> set[str]:
    lowered = text.lower()
    mentioned = set()
    for ticker in case_companies:
        aliases = TICKER_ALIASES.get(ticker, (ticker,))
        if any(_alias_in_text(alias, lowered) for alias in aliases):
            mentioned.add(ticker)
    return mentioned


def _support_tickers_from_answer(answer: dict[str, Any]) -> set[str]:
    ids: list[str] = []
    for location in _answer_support_locations(answer):
        ids.extend(location.get("metric_ids") or [])
        ids.extend(location.get("evidence_ids") or [])
    cell_table = answer.get("cell_table")
    if isinstance(cell_table, dict):
        for cell in cell_table.get("cells") or []:
            if isinstance(cell, dict):
                ids.append(str(cell.get("metric_id") or ""))
                ids.extend(str(item) for item in cell.get("evidence_ids") or [])
    return _tickers_from_ids(ids)


def _tickers_from_ids(ids: list[str]) -> set[str]:
    tickers = set()
    for value in ids:
        text = str(value or "")
        metric_parts = text.split("::")
        if len(metric_parts) >= 2 and re.fullmatch(r"[A-Z]{1,5}", metric_parts[1].upper()):
            tickers.add(metric_parts[1].upper())
            continue
        evidence_match = re.match(r"^([A-Z]{3,5})_", text)
        if evidence_match:
            tickers.add(evidence_match.group(1).upper())
    return tickers


def _nearby_answer_caveat_text(text: str) -> str:
    lines = [line for line in text.splitlines() if _contains_any(line.lower(), PROXY_CAVEAT_TERMS + COMPARABILITY_TERMS)]
    return "\n".join(lines)


def _near_metric_id_text(text: str, metric_id: str, *, before: int, after: int) -> str:
    lower = text.lower()
    metric_lower = str(metric_id or "").lower()
    index = lower.find(metric_lower)
    if index < 0:
        return text
    return text[max(0, index - before) : min(len(text), index + len(metric_id) + after)]


def _metric_id_clause_text(text: str, metric_id: str) -> str:
    lower = str(text or "").lower()
    metric_lower = str(metric_id or "").lower()
    index = lower.find(metric_lower)
    if index < 0:
        return str(text or "")
    # Percentage-role checks need the local phrase, not the next metric phrase.
    # Broad answer bullets often join "gross margin ... (id)，but operating income ... (id)".
    # Treat commas as phrase boundaries here so amount words in the next metric do not
    # make a percentage metric look like it was used as a dollar value.
    boundaries = (";", "；", "。", "\n", ",", "，")
    start_candidates = [lower.rfind(mark, 0, index) for mark in boundaries]
    end_candidates = [pos for mark in boundaries for pos in [lower.find(mark, index)] if pos >= 0]
    start = max(start_candidates) + 1 if start_candidates else 0
    end = min(end_candidates) if end_candidates else len(text)
    return str(text or "")[start:end]


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = str(text or "").lower()
    return any(str(term).lower() in lowered for term in terms)


def _pattern_present(pattern: str, text: str) -> bool:
    if pattern.startswith("re:"):
        return re.search(pattern[3:], text, flags=re.I | re.S) is not None
    return pattern.lower() in text.lower()


def _alias_in_text(alias: str, lowered_text: str) -> bool:
    alias_lower = alias.lower()
    if re.fullmatch(r"[A-Za-z0-9.]+", alias):
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(alias_lower)}(?![A-Za-z0-9])", lowered_text) is not None
    return alias_lower in lowered_text


def _has_numeric_amount(text: str) -> bool:
    return bool(re.search(r"\$|美元|million|billion|\b\d{2,}(?:\.\d+)?\b", text, flags=re.I))


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if value:
        return [str(value)]
    return []


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
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
