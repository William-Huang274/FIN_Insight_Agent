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


TOP_LEVEL_STRENGTHS = {
    "strong_with_caveats",
    "moderate_with_caveats",
    "weak_only",
    "disclosure_quality_only",
    "insufficient_evidence",
}
DRIVER_STRENGTHS = {"strong", "moderate", "weak", "caveated", "insufficient"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Decision Driver Evidence Packs.")
    parser.add_argument(
        "--driver-pack-path",
        default="reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_packs.json",
    )
    parser.add_argument(
        "--candidate-path",
        default="reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidates.json",
    )
    parser.add_argument(
        "--output-path",
        default="reports/quality/sec_tech_10k_expanded_v0_2_complex6_driver_pack_validation.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    packs_payload = _read_json(REPO_ROOT / args.driver_pack_path)
    candidate_payload = _read_json(REPO_ROOT / args.candidate_path)
    candidate_by_query = {str(query.get("query_id")): query for query in candidate_payload.get("queries") or []}
    rows = []
    for result in packs_payload.get("results") or []:
        query_id = str(result.get("query_id") or (result.get("driver_pack") or {}).get("query_id") or "")
        rows.append(_validate_query(result, candidate_by_query.get(query_id, {})))

    hard_failure_types = Counter(
        failure.get("type") for row in rows for failure in row.get("hard_failures") or []
    )
    warning_types = Counter(warning.get("type") for row in rows for warning in row.get("warnings") or [])
    primary_rates = [row.get("primary_facet_driver_coverage_rate") for row in rows if row.get("primary_facet_driver_coverage_rate") is not None]
    report = {
        "schema_version": "driver_pack_validation_v0.1",
        "driver_pack_path": str((REPO_ROOT / args.driver_pack_path).resolve()),
        "candidate_path": str((REPO_ROOT / args.candidate_path).resolve()),
        "summary": {
            "query_count": len(rows),
            "pass_count": sum(row.get("status") == "pass" for row in rows),
            "fail_count": sum(row.get("status") != "pass" for row in rows),
            "hard_failure_types": dict(sorted(hard_failure_types.items())),
            "warning_types": dict(sorted(warning_types.items())),
            "mean_primary_facet_driver_coverage_rate": round(sum(primary_rates) / len(primary_rates), 4) if primary_rates else 0.0,
        },
        "queries": rows,
    }
    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_path": str(output_path), **report["summary"]}, ensure_ascii=False, indent=2))


def _validate_query(result: dict[str, Any], candidate_query: dict[str, Any]) -> dict[str, Any]:
    pack = result.get("driver_pack") or result.get("pack") or result
    query_id = str(pack.get("query_id") or result.get("query_id") or "")
    contract = candidate_query.get("query_contract") or {}
    contract_index, metric_index, facet_priorities = _candidate_indexes(candidate_query)
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not candidate_query:
        failures.append({"type": "query_missing_from_candidates", "query_id": query_id})
    if query_id != str(candidate_query.get("query_id") or query_id):
        failures.append({"type": "query_id_mismatch", "pack_query_id": query_id, "candidate_query_id": candidate_query.get("query_id")})

    if pack.get("conclusion_strength") not in TOP_LEVEL_STRENGTHS:
        failures.append({"type": "invalid_top_level_conclusion_strength", "value": pack.get("conclusion_strength")})
    allowed = set(contract.get("allowed_conclusion_strengths") or TOP_LEVEL_STRENGTHS)
    if pack.get("conclusion_strength") and pack.get("conclusion_strength") not in allowed:
        failures.append({"type": "top_level_conclusion_strength_not_allowed", "value": pack.get("conclusion_strength"), "allowed": sorted(allowed)})

    drivers = pack.get("decision_drivers") or []
    if not isinstance(drivers, list):
        failures.append({"type": "decision_drivers_not_array"})
        drivers = []
    if not 1 <= len(drivers) <= 3:
        failures.append({"type": "invalid_driver_count", "count": len(drivers)})
    driver_ids = [str(driver.get("driver_id") or "") for driver in drivers if isinstance(driver, dict)]
    duplicate_driver_ids = sorted(item for item, count in Counter(driver_ids).items() if item and count > 1)
    if duplicate_driver_ids:
        failures.append({"type": "duplicate_driver_id", "values": duplicate_driver_ids})

    covered_primary = set()
    explicit_missing = {str(item.get("facet_id")) for item in pack.get("missing_primary_facets") or [] if isinstance(item, dict)}
    driver_reports = []
    all_pack_text = [str(pack.get("thesis_candidate_zh") or "")]
    for index, driver in enumerate(drivers, start=1):
        if not isinstance(driver, dict):
            failures.append({"type": "driver_not_object", "driver_index": index})
            continue
        driver_report, driver_failures, driver_warnings = _validate_driver(
            driver,
            index,
            contract,
            contract_index,
            metric_index,
            facet_priorities,
        )
        driver_reports.append(driver_report)
        failures.extend(driver_failures)
        warnings.extend(driver_warnings)
        covered_primary.update(driver_report.get("covered_primary_facets") or [])
        all_pack_text.extend(
            [
                str(driver.get("driver_claim_zh") or ""),
                str(driver.get("why_it_matters_zh") or ""),
                str(driver.get("counter_evidence_or_caveat_zh") or ""),
            ]
        )
    for item in pack.get("secondary_context") or []:
        all_pack_text.extend([str(item.get("context_zh") or ""), str(item.get("why_secondary_zh") or "")])
        for contract_id in item.get("supporting_contract_ids") or []:
            if str(contract_id) not in contract_index:
                failures.append({"type": "invalid_secondary_context_contract_id", "contract_id": contract_id})
    for item in pack.get("limiting_caveats") or []:
        all_pack_text.extend([str(item.get("caveat_zh") or ""), str(item.get("downgrade_effect_zh") or "")])
        for contract_id in item.get("supporting_contract_ids") or []:
            if str(contract_id) not in contract_index:
                failures.append({"type": "invalid_limiting_caveat_contract_id", "contract_id": contract_id})

    exact_text_hits = _exact_value_text_hits(" ".join(all_pack_text))
    if exact_text_hits:
        failures.append({"type": "exact_value_in_pack_prose", "values": exact_text_hits[:12]})

    primary_facets = {facet_id for facet_id, priority in facet_priorities.items() if priority == "primary"}
    handled_primary = covered_primary | explicit_missing
    primary_coverage_rate = _ratio(len(primary_facets & handled_primary), len(primary_facets))
    if primary_facets and primary_coverage_rate < 0.8:
        failures.append(
            {
                "type": "low_primary_facet_driver_coverage",
                "coverage_rate": primary_coverage_rate,
                "missing": sorted(primary_facets - handled_primary),
            }
        )
    caveat_facets = {facet_id for facet_id, priority in facet_priorities.items() if priority == "caveat"}
    if caveat_facets and not pack.get("limiting_caveats"):
        warnings.append({"type": "query_has_caveat_facets_but_no_limiting_caveats", "facet_ids": sorted(caveat_facets)})

    return {
        "query_id": query_id,
        "parse_status": result.get("parse_status"),
        "driver_count": len(drivers),
        "hard_failure_count": len(failures),
        "warning_count": len(warnings),
        "hard_failures": failures,
        "warnings": warnings,
        "status": "pass" if not failures else "fail",
        "primary_facet_driver_coverage_rate": primary_coverage_rate,
        "driver_reports": driver_reports,
    }


def _validate_driver(
    driver: dict[str, Any],
    index: int,
    contract: dict[str, Any],
    contract_index: dict[str, dict[str, Any]],
    metric_index: dict[str, dict[str, Any]],
    facet_priorities: dict[str, str],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    driver_id = str(driver.get("driver_id") or f"driver_{index}")
    if driver.get("conclusion_strength") not in DRIVER_STRENGTHS:
        failures.append({"type": "invalid_driver_conclusion_strength", "driver_id": driver_id, "value": driver.get("conclusion_strength")})
    if int(driver.get("rank") or 0) != index:
        warnings.append({"type": "driver_rank_not_sequential", "driver_id": driver_id, "rank": driver.get("rank"), "expected": index})

    contract_ids = [str(item) for item in driver.get("supporting_contract_ids") or []]
    metric_ids = [str(item) for item in driver.get("supporting_metric_ids") or []]
    if not contract_ids:
        failures.append({"type": "driver_missing_supporting_contracts", "driver_id": driver_id})
    invalid_contract_ids = [item for item in contract_ids if item not in contract_index]
    if invalid_contract_ids:
        failures.append({"type": "invalid_driver_contract_id", "driver_id": driver_id, "values": invalid_contract_ids})
    invalid_metric_ids = [item for item in metric_ids if item not in metric_index]
    if invalid_metric_ids:
        failures.append({"type": "invalid_driver_metric_id", "driver_id": driver_id, "values": invalid_metric_ids})

    support_contracts = [contract_index[item] for item in contract_ids if item in contract_index]
    support_metrics = [metric_index[item] for item in metric_ids if item in metric_index]
    background_core = [item.get("contract_id") for item in support_contracts if item.get("evidence_role") != "citation"]
    if background_core:
        failures.append({"type": "background_as_core_driver_support", "driver_id": driver_id, "values": background_core})
    actual_companies = sorted({str(item.get("ticker")) for item in support_contracts if item.get("ticker")} | {str(item.get("ticker")) for item in support_metrics if item.get("ticker")})
    actual_years = sorted({_to_int(item.get("fiscal_year")) for item in support_contracts if _to_int(item.get("fiscal_year"))} | {_to_int(item.get("fiscal_year")) for item in support_metrics if _to_int(item.get("fiscal_year"))})
    actual_facets = sorted(
        {str(item.get("facet_id") or item.get("contract_facet_id")) for item in support_contracts if item.get("facet_id") or item.get("contract_facet_id")}
        | {str(facet_id) for metric in support_metrics for facet_id in metric.get("facet_ids") or []}
    )
    actual_families = sorted(
        {str(family) for item in support_contracts for family in item.get("metric_families") or [] if family != "unknown"}
        | {str(item.get("metric_family")) for item in support_metrics if item.get("metric_family")}
    )
    claimed_companies = {str(item) for item in driver.get("covered_companies") or []}
    claimed_years = {_to_int(item) for item in driver.get("covered_years") or [] if _to_int(item)}
    claimed_facets = {str(item) for item in driver.get("covered_facets") or []}
    if claimed_companies - set(actual_companies):
        failures.append({"type": "driver_claimed_company_not_supported", "driver_id": driver_id, "values": sorted(claimed_companies - set(actual_companies))})
    if claimed_years - set(actual_years):
        failures.append({"type": "driver_claimed_year_not_supported", "driver_id": driver_id, "values": sorted(claimed_years - set(actual_years))})
    if claimed_facets - set(actual_facets):
        failures.append({"type": "driver_claimed_facet_not_supported", "driver_id": driver_id, "values": sorted(claimed_facets - set(actual_facets))})
    if driver.get("global_claim_allowed") and not _covers_required(actual_companies, actual_years, contract):
        failures.append(
            {
                "type": "global_claim_allowed_without_required_coverage",
                "driver_id": driver_id,
                "actual_companies": actual_companies,
                "actual_years": actual_years,
                "required_companies": contract.get("required_companies") or [],
                "required_years": contract.get("required_years") or [],
            }
        )
    covered_primary_facets = sorted({facet for facet in actual_facets if facet_priorities.get(facet) == "primary"})
    return (
        {
            "driver_id": driver_id,
            "actual_companies": actual_companies,
            "actual_years": actual_years,
            "actual_facets": actual_facets,
            "actual_metric_families": actual_families,
            "covered_primary_facets": covered_primary_facets,
            "supporting_contract_count": len(support_contracts),
            "supporting_metric_count": len(support_metrics),
        },
        failures,
        warnings,
    )


def _candidate_indexes(candidate_query: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, str]]:
    contract_index: dict[str, dict[str, Any]] = {}
    metric_index: dict[str, dict[str, Any]] = {}
    facet_priorities: dict[str, str] = {}
    for facet in candidate_query.get("candidate_facets") or []:
        facet_id = str(facet.get("facet_id"))
        facet_priorities[facet_id] = str(facet.get("priority") or "")
        for contract in facet.get("candidate_contracts") or []:
            item = dict(contract)
            item["facet_id"] = facet_id
            contract_index[str(item.get("contract_id"))] = item
        for metric in facet.get("candidate_metrics") or []:
            item = dict(metric)
            item.setdefault("facet_ids", [facet_id])
            metric_index[str(item.get("metric_id"))] = item
    return contract_index, metric_index, facet_priorities


def _covers_required(companies: list[str], years: list[int], contract: dict[str, Any]) -> bool:
    required_companies = {str(item) for item in contract.get("required_companies") or []}
    required_years = {_to_int(item) for item in contract.get("required_years") or [] if _to_int(item)}
    return set(companies) >= required_companies and set(years) >= required_years


def _exact_value_text_hits(text: str) -> list[str]:
    hits = []
    patterns = [
        r"\$[\s\d,.]+(?:million|billion)?",
        r"\b\d+(?:\.\d+)?%",
        r"\b\d+(?:\.\d+)?\s*(?:亿美元|亿|million|billion)\b",
        r"\b\d{1,3},\d{3}(?:,\d{3})*\b",
    ]
    for pattern in patterns:
        hits.extend(re.findall(pattern, text, flags=re.I))
    return sorted(set(hit.strip() for hit in hits if hit.strip()))


def _to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
