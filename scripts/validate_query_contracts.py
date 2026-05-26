from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

METRIC_FAMILY_ALLOWLIST = {
    "advertising_revenue",
    "arr_or_recurring_proxy",
    "billings",
    "capex",
    "cash_flow",
    "cloud_revenue",
    "customer_concentration",
    "customer_retention",
    "datacenter_revenue",
    "deferred_revenue",
    "depreciation_amortization",
    "gross_margin",
    "infrastructure_cost",
    "inventory",
    "operating_income",
    "operating_margin",
    "product_cycle",
    "rpo",
    "services_revenue",
    "subscription_revenue",
    "supply_chain_risk",
}

ALLOWED_STRENGTHS = {
    "strong_with_caveats",
    "moderate_with_caveats",
    "weak_only",
    "disclosure_quality_only",
    "insufficient_evidence",
}
ALLOWED_PRIORITIES = {"primary", "supporting", "caveat"}
ALLOWED_DRIVER_ROLES = {"core_driver", "supporting_context", "caveat_driver"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Query Contract planner outputs.")
    parser.add_argument(
        "--contracts-path",
        default="reports/query_contracts/sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json",
    )
    parser.add_argument("--eval-path", default="eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl")
    parser.add_argument(
        "--output-path",
        default="reports/quality/sec_tech_10k_expanded_v0_2_complex6_query_contract_validation.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    eval_rows = {str(row.get("query_id")): row for row in _read_jsonl(REPO_ROOT / args.eval_path)}
    payload = _read_json(REPO_ROOT / args.contracts_path)
    contracts = _extract_contract_rows(payload)
    results = []
    for row in contracts:
        query_id = str(row.get("query_id") or (row.get("query_contract") or {}).get("query_id"))
        contract = row.get("query_contract") or row.get("contract") or row
        failures, warnings = _validate_contract(contract, eval_rows.get(query_id, {}))
        results.append(
            {
                "query_id": query_id,
                "parse_status": row.get("parse_status"),
                "hard_failure_count": len(failures),
                "warning_count": len(warnings),
                "hard_failures": failures,
                "warnings": warnings,
                "status": "pass" if not failures else "fail",
            }
        )
    failure_types = Counter(
        failure.get("type") for result in results for failure in result.get("hard_failures") or []
    )
    warning_types = Counter(warning.get("type") for result in results for warning in result.get("warnings") or [])
    report = {
        "schema_version": "query_contract_validation_v0.1",
        "contracts_path": str((REPO_ROOT / args.contracts_path).resolve()),
        "eval_path": str((REPO_ROOT / args.eval_path).resolve()),
        "query_count": len(results),
        "pass_count": sum(result.get("status") == "pass" for result in results),
        "fail_count": sum(result.get("status") != "pass" for result in results),
        "hard_failure_types": dict(sorted(failure_types.items())),
        "warning_types": dict(sorted(warning_types.items())),
        "results": results,
    }
    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "query_count": report["query_count"],
                "pass_count": report["pass_count"],
                "fail_count": report["fail_count"],
                "hard_failure_types": report["hard_failure_types"],
                "warning_types": report["warning_types"],
                "output_path": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _validate_contract(contract: dict[str, Any], eval_row: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    required_keys = {
        "query_id",
        "task_profile",
        "target_judgment_zh",
        "required_companies",
        "required_years",
        "allowed_conclusion_strengths",
        "required_metric_families",
        "facets",
        "comparability_rules",
        "planner_confidence",
        "planner_caveats_zh",
    }
    for key in sorted(required_keys - set(contract)):
        failures.append({"type": "missing_required_field", "field": key})
    query_id = str(contract.get("query_id") or "")
    if not eval_row:
        failures.append({"type": "query_id_not_in_eval", "query_id": query_id})
    elif query_id != str(eval_row.get("query_id")):
        failures.append(
            {
                "type": "query_id_mismatch",
                "contract_query_id": query_id,
                "eval_query_id": eval_row.get("query_id"),
            }
        )
    if contract.get("task_profile") != "complex_insight":
        failures.append({"type": "invalid_task_profile", "value": contract.get("task_profile")})

    expected_companies = {str(ticker).upper() for ticker in eval_row.get("tickers") or []}
    actual_companies = {str(ticker).upper() for ticker in contract.get("required_companies") or []}
    if expected_companies and actual_companies != expected_companies:
        failures.append(
            {
                "type": "required_companies_mismatch",
                "expected": sorted(expected_companies),
                "actual": sorted(actual_companies),
            }
        )
    expected_years = {int(year) for year in eval_row.get("fiscal_years") or []}
    actual_years = _int_set(contract.get("required_years") or [])
    if expected_years and actual_years != expected_years:
        failures.append(
            {
                "type": "required_years_mismatch",
                "expected": sorted(expected_years),
                "actual": sorted(actual_years),
            }
        )

    strengths = {str(item) for item in contract.get("allowed_conclusion_strengths") or []}
    invalid_strengths = strengths - ALLOWED_STRENGTHS
    if not strengths:
        failures.append({"type": "missing_allowed_conclusion_strengths"})
    if invalid_strengths:
        failures.append({"type": "invalid_conclusion_strength", "values": sorted(invalid_strengths)})

    families = {str(item) for item in contract.get("required_metric_families") or []}
    invalid_families = families - METRIC_FAMILY_ALLOWLIST
    if not families:
        failures.append({"type": "missing_required_metric_families"})
    if invalid_families:
        failures.append({"type": "invalid_metric_family", "values": sorted(invalid_families)})

    target = str(contract.get("target_judgment_zh") or "")
    if not target.strip():
        failures.append({"type": "missing_target_judgment"})
    if _contains_object_id(contract):
        failures.append({"type": "object_id_leakage"})
    if _contains_forbidden_exact_value(target, expected_years):
        failures.append({"type": "target_judgment_contains_exact_value", "text": target[:220]})

    facets = contract.get("facets") or []
    if not isinstance(facets, list):
        failures.append({"type": "facets_not_array"})
        facets = []
    if not 3 <= len(facets) <= 6:
        failures.append({"type": "invalid_facet_count", "count": len(facets)})
    primary_count = 0
    caveat_count = 0
    facet_ids: list[str] = []
    for idx, facet in enumerate(facets, start=1):
        if not isinstance(facet, dict):
            failures.append({"type": "facet_not_object", "facet_index": idx})
            continue
        facet_ids.append(str(facet.get("facet_id") or ""))
        priority = str(facet.get("priority") or "")
        if priority not in ALLOWED_PRIORITIES:
            failures.append({"type": "invalid_facet_priority", "facet_index": idx, "value": priority})
        if priority == "primary":
            primary_count += 1
        if priority == "caveat":
            caveat_count += 1
        if not str(facet.get("missing_downgrade_rule_zh") or "").strip():
            failures.append({"type": "missing_downgrade_rule", "facet_index": idx})
        roles = {str(role) for role in facet.get("allowed_driver_roles") or []}
        if not roles:
            failures.append({"type": "missing_allowed_driver_roles", "facet_index": idx})
        invalid_roles = roles - ALLOWED_DRIVER_ROLES
        if invalid_roles:
            failures.append(
                {"type": "invalid_allowed_driver_role", "facet_index": idx, "values": sorted(invalid_roles)}
            )
        coverage = facet.get("required_coverage") or {}
        cov_companies = {str(ticker).upper() for ticker in coverage.get("companies") or []}
        if cov_companies - expected_companies:
            failures.append(
                {
                    "type": "facet_company_out_of_scope",
                    "facet_index": idx,
                    "values": sorted(cov_companies - expected_companies),
                }
            )
        cov_years = _int_set(coverage.get("years") or [])
        if cov_years - expected_years:
            failures.append(
                {"type": "facet_year_out_of_scope", "facet_index": idx, "values": sorted(cov_years - expected_years)}
            )
        cov_families = {str(item) for item in coverage.get("metric_families") or []}
        if not cov_families:
            failures.append({"type": "facet_missing_metric_families", "facet_index": idx})
        invalid_cov_families = cov_families - METRIC_FAMILY_ALLOWLIST
        if invalid_cov_families:
            failures.append(
                {
                    "type": "facet_invalid_metric_family",
                    "facet_index": idx,
                    "values": sorted(invalid_cov_families),
                }
            )
        if _contains_forbidden_exact_value(str(facet.get("facet_zh") or ""), expected_years):
            warnings.append({"type": "facet_label_contains_number", "facet_index": idx})
    if primary_count == 0:
        failures.append({"type": "missing_primary_facet"})
    if caveat_count == 0 and not contract.get("comparability_rules"):
        failures.append({"type": "missing_caveat_or_comparability_rule"})
    duplicate_facet_ids = sorted(item for item, count in Counter(facet_ids).items() if item and count > 1)
    if duplicate_facet_ids:
        failures.append({"type": "duplicate_facet_id", "values": duplicate_facet_ids})

    for idx, rule in enumerate(contract.get("comparability_rules") or [], start=1):
        if not isinstance(rule, dict):
            failures.append({"type": "comparability_rule_not_object", "rule_index": idx})
            continue
        rule_families = {str(item) for item in rule.get("metric_families") or []}
        if not rule_families:
            failures.append({"type": "comparability_rule_missing_families", "rule_index": idx})
        invalid_rule_families = rule_families - METRIC_FAMILY_ALLOWLIST
        if invalid_rule_families:
            failures.append(
                {
                    "type": "comparability_rule_invalid_metric_family",
                    "rule_index": idx,
                    "values": sorted(invalid_rule_families),
                }
            )
        if not str(rule.get("rule_zh") or "").strip():
            failures.append({"type": "comparability_rule_missing_text", "rule_index": idx})

    if contract.get("planner_confidence") not in {"high", "medium", "low"}:
        failures.append({"type": "invalid_planner_confidence", "value": contract.get("planner_confidence")})
    if not contract.get("planner_caveats_zh"):
        warnings.append({"type": "missing_planner_caveats"})
    return failures, warnings


def _extract_contract_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            return payload["results"]
        if isinstance(payload.get("contracts"), list):
            return payload["contracts"]
        if payload.get("query_contract") or payload.get("query_id"):
            return [payload]
    return []


def _contains_object_id(value: Any) -> bool:
    return bool(re.search(r"\b[A-Z]{2,6}_\d{4}_10K_", _recursive_text(value)))


def _contains_forbidden_exact_value(text: str, allowed_years: set[int]) -> bool:
    cleaned = text
    for year in allowed_years:
        cleaned = re.sub(rf"\b{year}\b", "", cleaned)
    return bool(
        re.search(r"\$\s*\d", cleaned)
        or re.search(r"\d+(?:\.\d+)?\s*(?:%|billion|million|亿|百万|千万)", cleaned, flags=re.IGNORECASE)
    )


def _recursive_text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_recursive_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_recursive_text(item) for item in value)
    return str(value)


def _int_set(values: list[Any]) -> set[int]:
    ints: set[int] = set()
    for value in values:
        try:
            ints.add(int(value))
        except (TypeError, ValueError):
            continue
    return ints


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    main()
