from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


PRIORITY_LIMITS = {
    "primary": {"contracts": 12, "metrics": 12},
    "supporting": {"contracts": 6, "metrics": 8},
    "caveat": {"contracts": 8, "metrics": 6},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact candidates for Decision Driver Evidence Pack planning.")
    parser.add_argument(
        "--query-contract-path",
        default="reports/query_contracts/sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json",
    )
    parser.add_argument(
        "--evidence-contract-path",
        default="reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_evidence_object_contracts.json",
    )
    parser.add_argument(
        "--ledger-path",
        default="reports/exact_value_ledgers/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger.json",
    )
    parser.add_argument(
        "--output-path",
        default="reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidates.json",
    )
    parser.add_argument(
        "--report-path",
        default="reports/quality/sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidate_report.json",
    )
    parser.add_argument("--text-chars", type=int, default=360)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    query_contract_payload = _read_json(REPO_ROOT / args.query_contract_path)
    evidence_payload = _read_json(REPO_ROOT / args.evidence_contract_path)
    ledger_payload = _read_json(REPO_ROOT / args.ledger_path)

    query_contracts = {
        str(row.get("query_id")): row.get("query_contract") or row
        for row in query_contract_payload.get("results") or []
    }
    ledger_by_query_facet = _ledger_by_query_facet(ledger_payload.get("rows") or [])
    query_outputs = []
    for query in evidence_payload.get("queries") or []:
        query_id = str(query.get("query_id"))
        query_contract = query_contracts.get(query_id)
        if not query_contract:
            continue
        query_outputs.append(
            _build_query_candidates(
                query_id,
                query_contract,
                query.get("contracts") or [],
                ledger_by_query_facet,
                text_chars=args.text_chars,
            )
        )

    report = _report(query_outputs, args)
    output = {
        "schema_version": "driver_pack_candidates_v0.1",
        "inputs": {
            "query_contract_path": str((REPO_ROOT / args.query_contract_path).resolve()),
            "evidence_contract_path": str((REPO_ROOT / args.evidence_contract_path).resolve()),
            "ledger_path": str((REPO_ROOT / args.ledger_path).resolve()),
        },
        "policy": {
            "primary_contract_limit": PRIORITY_LIMITS["primary"]["contracts"],
            "supporting_contract_limit": PRIORITY_LIMITS["supporting"]["contracts"],
            "caveat_contract_limit": PRIORITY_LIMITS["caveat"]["contracts"],
            "ranking": "citation role, ledger-backed numeric support, facet priority, verifier confidence, rerank score, company/year diversity",
            "planner_instruction": "Use these candidates to select at most 3 decision drivers; do not write final synthesis here.",
        },
        "summary": report["summary"],
        "queries": query_outputs,
    }
    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report["output_path"] = str(output_path.resolve())
    report_path = REPO_ROOT / args.report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_path": str(output_path), **report["summary"]}, ensure_ascii=False, indent=2))


def _build_query_candidates(
    query_id: str,
    query_contract: dict[str, Any],
    contracts: list[dict[str, Any]],
    ledger_by_query_facet: dict[tuple[str, str], list[dict[str, Any]]],
    *,
    text_chars: int,
) -> dict[str, Any]:
    contracts_by_facet = defaultdict(list)
    for contract in contracts:
        contracts_by_facet[str(contract.get("contract_facet_id"))].append(contract)
    facets = []
    for facet in query_contract.get("facets") or []:
        facet_id = str(facet.get("facet_id"))
        priority = str(facet.get("priority") or "supporting")
        limits = PRIORITY_LIMITS.get(priority, PRIORITY_LIMITS["supporting"])
        facet_contracts = contracts_by_facet.get(facet_id, [])
        ranked_contracts = _select_diverse_contracts(
            facet_contracts,
            required_coverage=facet.get("required_coverage") or {},
            max_items=limits["contracts"],
            text_chars=text_chars,
        )
        ranked_metrics = _select_diverse_metrics(
            ledger_by_query_facet.get((query_id, facet_id), []),
            required_coverage=facet.get("required_coverage") or {},
            max_items=limits["metrics"],
        )
        facets.append(
            {
                "facet_id": facet_id,
                "facet_zh": facet.get("facet_zh"),
                "priority": priority,
                "required_coverage": facet.get("required_coverage") or {},
                "missing_downgrade_rule_zh": facet.get("missing_downgrade_rule_zh"),
                "allowed_driver_roles": facet.get("allowed_driver_roles") or [],
                "coverage_summary": _coverage_summary(facet_contracts),
                "missing_coverage": _missing_coverage(facet.get("required_coverage") or {}, facet_contracts),
                "candidate_contracts": ranked_contracts,
                "candidate_metrics": ranked_metrics,
            }
        )
    return {
        "query_id": query_id,
        "query_contract": {
            "query_id": query_contract.get("query_id"),
            "target_judgment_zh": query_contract.get("target_judgment_zh"),
            "required_companies": query_contract.get("required_companies") or [],
            "required_years": query_contract.get("required_years") or [],
            "allowed_conclusion_strengths": query_contract.get("allowed_conclusion_strengths") or [],
            "required_metric_families": query_contract.get("required_metric_families") or [],
            "comparability_rules": query_contract.get("comparability_rules") or [],
            "planner_caveats_zh": query_contract.get("planner_caveats_zh") or [],
        },
        "candidate_facets": facets,
    }


def _select_diverse_contracts(
    contracts: list[dict[str, Any]],
    *,
    required_coverage: dict[str, Any],
    max_items: int,
    text_chars: int,
) -> list[dict[str, Any]]:
    ranked = sorted(contracts, key=lambda item: _contract_score(item, required_coverage), reverse=True)
    selected = []
    seen_objects = set()
    seen_ticker_year_type = set()
    for contract in ranked:
        key = (contract.get("ticker"), contract.get("fiscal_year"), contract.get("object_type"))
        if contract.get("object_id") in seen_objects:
            continue
        if key in seen_ticker_year_type and len(selected) < max_items // 2:
            continue
        selected.append(_compact_contract(contract, text_chars=text_chars))
        seen_objects.add(contract.get("object_id"))
        seen_ticker_year_type.add(key)
        if len(selected) >= max_items:
            return selected
    for contract in ranked:
        if contract.get("object_id") in seen_objects:
            continue
        selected.append(_compact_contract(contract, text_chars=text_chars))
        seen_objects.add(contract.get("object_id"))
        if len(selected) >= max_items:
            break
    return selected


def _select_diverse_metrics(
    rows: list[dict[str, Any]],
    *,
    required_coverage: dict[str, Any],
    max_items: int,
) -> list[dict[str, Any]]:
    ranked = sorted(rows, key=lambda item: _metric_score(item, required_coverage), reverse=True)
    selected = []
    seen_metric_ids = set()
    seen_ticker_year_family_role = set()
    for row in ranked:
        metric_id = row.get("metric_id")
        key = (row.get("ticker"), row.get("fiscal_year"), row.get("metric_family"), row.get("metric_role"))
        if metric_id in seen_metric_ids:
            continue
        if key in seen_ticker_year_family_role and len(selected) < max_items // 2:
            continue
        selected.append(_compact_metric(row))
        seen_metric_ids.add(metric_id)
        seen_ticker_year_family_role.add(key)
        if len(selected) >= max_items:
            return selected
    for row in ranked:
        metric_id = row.get("metric_id")
        if metric_id in seen_metric_ids:
            continue
        selected.append(_compact_metric(row))
        seen_metric_ids.add(metric_id)
        if len(selected) >= max_items:
            break
    return selected


def _contract_score(contract: dict[str, Any], required_coverage: dict[str, Any]) -> float:
    score = 0.0
    if contract.get("evidence_role") == "citation":
        score += 20.0
    if contract.get("object_type") in {"metric", "table"}:
        score += 5.0
    if contract.get("numeric_candidates"):
        score += 4.0
    if (contract.get("ticker") or "") in set(str(item) for item in required_coverage.get("companies") or []):
        score += 2.0
    if _to_int(contract.get("fiscal_year")) in set(_to_int(item) for item in required_coverage.get("years") or []):
        score += 2.0
    families = set(contract.get("metric_families") or [])
    required_families = set(required_coverage.get("metric_families") or [])
    if families & required_families:
        score += 4.0
    score += min(float(contract.get("verifier_confidence") or 0.0), 1.0) * 2.0
    score += min(float(contract.get("rerank_score") or 0.0), 1.0)
    return score


def _metric_score(row: dict[str, Any], required_coverage: dict[str, Any]) -> float:
    score = 0.0
    if row.get("metric_family") in set(required_coverage.get("metric_families") or []):
        score += 8.0
    if row.get("ticker") in set(required_coverage.get("companies") or []):
        score += 3.0
    if _to_int(row.get("fiscal_year")) in set(_to_int(item) for item in required_coverage.get("years") or []):
        score += 3.0
    if row.get("metric_role") == "total_value":
        score += 2.0
    elif row.get("metric_role") == "percentage_rate":
        score += 1.5
    elif row.get("metric_role") == "period_change_amount":
        score += 1.0
    return score


def _compact_contract(contract: dict[str, Any], *, text_chars: int) -> dict[str, Any]:
    numeric_candidates = contract.get("numeric_candidates") or []
    return {
        "contract_id": contract.get("contract_id"),
        "object_id": contract.get("object_id"),
        "evidence_role": contract.get("evidence_role"),
        "core_fact_allowed": contract.get("core_fact_allowed"),
        "object_type": contract.get("object_type"),
        "ticker": contract.get("ticker"),
        "fiscal_year": contract.get("fiscal_year"),
        "metric_families": contract.get("metric_families") or [],
        "allowed_claim_roles": contract.get("allowed_claim_roles") or [],
        "disallowed_claim_roles": contract.get("disallowed_claim_roles") or [],
        "verifier_confidence": contract.get("verifier_confidence"),
        "rerank_score": contract.get("rerank_score"),
        "numeric_candidate_count": len(numeric_candidates),
        "narrative_allowed_numeric_count": sum(1 for item in numeric_candidates if item.get("allowed_in_narrative")),
        "boundary_notes_zh": contract.get("boundary_notes_zh") or [],
        "source_text_preview": _trim(contract.get("source_text_preview"), text_chars),
    }


def _compact_metric(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "metric_id": row.get("metric_id"),
        "object_id": row.get("object_id"),
        "supporting_contract_ids": row.get("supporting_contract_ids") or [],
        "ticker": row.get("ticker"),
        "fiscal_year": row.get("fiscal_year"),
        "metric_family": row.get("metric_family"),
        "metric_role": row.get("metric_role"),
        "metric_label": row.get("metric_label"),
        "raw_value_text": row.get("raw_value_text"),
        "unit": row.get("unit"),
        "display_value_zh": row.get("display_value_zh"),
        "allowed_claim_roles": row.get("allowed_claim_roles") or [],
        "disallowed_claim_roles": row.get("disallowed_claim_roles") or [],
        "narrative_guard_zh": row.get("narrative_guard_zh"),
    }


def _coverage_summary(contracts: list[dict[str, Any]]) -> dict[str, Any]:
    citation = [contract for contract in contracts if contract.get("evidence_role") == "citation"]
    return {
        "citation_contract_count": len(citation),
        "companies": sorted({str(contract.get("ticker")) for contract in citation if contract.get("ticker")}),
        "years": sorted({_to_int(contract.get("fiscal_year")) for contract in citation if _to_int(contract.get("fiscal_year"))}),
        "metric_families": sorted(
            {
                str(family)
                for contract in citation
                for family in contract.get("metric_families") or []
                if family != "unknown"
            }
        ),
    }


def _missing_coverage(required_coverage: dict[str, Any], contracts: list[dict[str, Any]]) -> dict[str, Any]:
    coverage = _coverage_summary(contracts)
    required_companies = {str(item) for item in required_coverage.get("companies") or []}
    required_years = {_to_int(item) for item in required_coverage.get("years") or [] if _to_int(item)}
    required_families = {str(item) for item in required_coverage.get("metric_families") or []}
    return {
        "companies": sorted(required_companies - set(coverage["companies"])),
        "years": sorted(required_years - set(coverage["years"])),
        "metric_families": sorted(required_families - set(coverage["metric_families"])),
    }


def _ledger_by_query_facet(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped = defaultdict(list)
    for row in rows:
        query_id = str(row.get("query_id"))
        for facet_id in row.get("facet_ids") or []:
            grouped[(query_id, str(facet_id))].append(row)
    return grouped


def _report(query_outputs: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    facet_rows = [facet for query in query_outputs for facet in query.get("candidate_facets") or []]
    contract_counts = [len(facet.get("candidate_contracts") or []) for facet in facet_rows]
    metric_counts = [len(facet.get("candidate_metrics") or []) for facet in facet_rows]
    primary = [facet for facet in facet_rows if facet.get("priority") == "primary"]
    summary = {
        "query_count": len(query_outputs),
        "facet_count": len(facet_rows),
        "candidate_contract_count": sum(contract_counts),
        "candidate_metric_count": sum(metric_counts),
        "avg_contracts_per_facet": round(sum(contract_counts) / len(contract_counts), 4) if contract_counts else 0.0,
        "avg_metrics_per_facet": round(sum(metric_counts) / len(metric_counts), 4) if metric_counts else 0.0,
        "primary_facet_count": len(primary),
        "primary_facet_with_candidates": sum(1 for facet in primary if facet.get("candidate_contracts")),
        "facet_priority_counts": dict(sorted(Counter(str(facet.get("priority")) for facet in facet_rows).items())),
    }
    return {
        "schema_version": "driver_pack_candidate_report_v0.1",
        "inputs": {
            "query_contract_path": str((REPO_ROOT / args.query_contract_path).resolve()),
            "evidence_contract_path": str((REPO_ROOT / args.evidence_contract_path).resolve()),
            "ledger_path": str((REPO_ROOT / args.ledger_path).resolve()),
        },
        "summary": summary,
        "warnings": _warnings(query_outputs),
    }


def _warnings(query_outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    warnings = []
    for query in query_outputs:
        for facet in query.get("candidate_facets") or []:
            if facet.get("priority") == "primary" and not facet.get("candidate_contracts"):
                warnings.append(
                    {
                        "type": "primary_facet_without_candidate_contracts",
                        "query_id": query.get("query_id"),
                        "facet_id": facet.get("facet_id"),
                    }
                )
    return warnings


def _trim(text: Any, max_chars: int) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    return cleaned[:max_chars] + ("..." if len(cleaned) > max_chars else "")


def _to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
