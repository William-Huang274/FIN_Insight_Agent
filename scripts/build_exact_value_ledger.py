from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


CONTEXT_FAMILY_PATTERNS: list[tuple[str, str]] = [
    ("operating_income", r"\b(segment\s+)?operating income(?:\s*\(loss\))?\b|\bincome from operations\b"),
    ("operating_margin", r"\boperating margin\b"),
    ("gross_margin", r"\bgross margin\b|\bgross profit\b"),
    ("infrastructure_cost", r"\bcost of revenues?\b|\bcosts and expenses\b|\binfrastructure cost\b"),
    ("cloud_revenue", r"\bcloud revenues?\b|\baws net sales\b|\bgoogle cloud revenues?\b|\bazure.*revenue"),
    ("advertising_revenue", r"\badvertising revenues?\b|\bgoogle advertising\b|\bfamily of apps\b"),
    ("services_revenue", r"\bservices net sales\b|\bservices revenues?\b"),
    ("subscription_revenue", r"\bsubscription revenues?\b|\bsubscription and support\b"),
    ("datacenter_revenue", r"\bdata center revenues?\b|\bdatacenter revenues?\b"),
    ("capex", r"\bcapital expenditures?\b|\bproperty and equipment\b|\bpurchases of property\b"),
    ("cash_flow", r"\bcash flow\b|\bnet cash provided\b"),
]

REVENUE_FAMILIES = {
    "advertising_revenue",
    "cloud_revenue",
    "datacenter_revenue",
    "services_revenue",
    "subscription_revenue",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an Exact-Value Ledger from Evidence Object Contracts.")
    parser.add_argument(
        "--contracts-path",
        default="reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_evidence_object_contracts.json",
    )
    parser.add_argument(
        "--output-path",
        default="reports/exact_value_ledgers/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger.json",
    )
    parser.add_argument(
        "--report-path",
        default="reports/quality/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger_validation.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = _read_json(REPO_ROOT / args.contracts_path)
    rows_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    rejected = []
    input_candidate_count = 0
    for query in payload.get("queries") or []:
        for contract in query.get("contracts") or []:
            for candidate in contract.get("numeric_candidates") or []:
                input_candidate_count += 1
                if not candidate.get("allowed_in_narrative"):
                    rejected.append(_rejection_row(contract, candidate))
                    continue
                row = _ledger_row(contract, candidate)
                key = (
                    row.get("query_id"),
                    row.get("metric_object_id"),
                    row.get("metric_family"),
                    row.get("metric_role"),
                    row.get("raw_value_text"),
                    row.get("unit"),
                )
                if key in rows_by_key:
                    _merge_row(rows_by_key[key], row)
                else:
                    rows_by_key[key] = row

    rows = sorted(rows_by_key.values(), key=lambda item: (str(item.get("query_id")), str(item.get("ticker")), int(item.get("fiscal_year") or 0), str(item.get("metric_family")), str(item.get("metric_id"))))
    for row in rows:
        row["supporting_contract_ids"] = sorted(set(row.get("supporting_contract_ids") or []))
        row["facet_ids"] = sorted(set(row.get("facet_ids") or []))
        row["aspect_ids"] = sorted(set(row.get("aspect_ids") or []))

    report = _report(rows, rejected, input_candidate_count, args=args, contracts_payload=payload)
    output = {
        "schema_version": "exact_value_ledger_v0.1",
        "inputs": {
            "contracts_path": str((REPO_ROOT / args.contracts_path).resolve()),
        },
        "policy": {
            "source": "Evidence Object Contract numeric_candidates with allowed_in_narrative=true",
            "final_synthesis_rule": "Exact numeric values in final prose must come from display_value_zh in this ledger and cite metric_id.",
            "dedupe_key": ["query_id", "metric_object_id", "metric_family", "metric_role", "raw_value_text", "unit"],
        },
        "summary": report["summary"],
        "rows": rows,
        "rejected_numeric_candidates": rejected[:500],
    }
    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_path = REPO_ROOT / args.report_path
    report["output_path"] = str(output_path.resolve())
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_path": str(output_path), **report["summary"]}, ensure_ascii=False, indent=2))


def _ledger_row(contract: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    metric_family = _primary_family(candidate)
    metric_role = str(candidate.get("metric_role") or "unknown")
    metric_id = _metric_id(contract, candidate, metric_family, metric_role)
    raw_value = candidate.get("raw_value_text")
    unit = candidate.get("unit")
    normalized_value, normalized_unit = _normalized_value(candidate.get("value"), unit, raw_value)
    context_families = _context_metric_families(candidate)
    return {
        "metric_id": metric_id,
        "query_id": contract.get("query_id"),
        "contract_id": contract.get("contract_id"),
        "supporting_contract_ids": [contract.get("contract_id")],
        "object_id": contract.get("object_id"),
        "metric_object_id": candidate.get("metric_object_id"),
        "source_trace_type": candidate.get("source_trace_type"),
        "facet_ids": [contract.get("contract_facet_id")],
        "aspect_ids": [contract.get("aspect_id")],
        "ticker": contract.get("ticker"),
        "fiscal_year": contract.get("fiscal_year"),
        "period_year": candidate.get("period_year"),
        "metric_family": metric_family,
        "metric_families": [family for family in candidate.get("metric_families") or [] if family != "unknown"],
        "source_context_metric_families": context_families,
        "metric_role": metric_role,
        "metric_label": candidate.get("metric_label"),
        "row_label": candidate.get("row_label"),
        "column_label": candidate.get("column_label"),
        "segment": candidate.get("segment"),
        "raw_value_text": raw_value,
        "value": candidate.get("value"),
        "unit": unit,
        "normalized_value": normalized_value,
        "normalized_unit": normalized_unit,
        "display_value_zh": candidate.get("display_value_zh"),
        "allowed_claim_roles": candidate.get("allowed_claim_roles") or [],
        "disallowed_claim_roles": candidate.get("disallowed_claim_roles") or [],
        "allowed_in_narrative": True,
        "narrative_guard_zh": candidate.get("narrative_guard_zh"),
        "source_statement": candidate.get("source_statement"),
    }


def _rejection_row(contract: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_id": contract.get("query_id"),
        "contract_id": contract.get("contract_id"),
        "object_id": contract.get("object_id"),
        "metric_object_id": candidate.get("metric_object_id"),
        "ticker": contract.get("ticker"),
        "fiscal_year": contract.get("fiscal_year"),
        "metric_label": candidate.get("metric_label"),
        "raw_value_text": candidate.get("raw_value_text"),
        "unit": candidate.get("unit"),
        "metric_role": candidate.get("metric_role"),
        "metric_families": candidate.get("metric_families"),
        "rejection_reasons": candidate.get("narrative_rejection_reasons") or [],
    }


def _merge_row(existing: dict[str, Any], row: dict[str, Any]) -> None:
    existing.setdefault("supporting_contract_ids", []).extend(row.get("supporting_contract_ids") or [])
    existing.setdefault("facet_ids", []).extend(row.get("facet_ids") or [])
    existing.setdefault("aspect_ids", []).extend(row.get("aspect_ids") or [])
    existing["allowed_claim_roles"] = _unique((existing.get("allowed_claim_roles") or []) + (row.get("allowed_claim_roles") or []))
    existing["disallowed_claim_roles"] = _unique((existing.get("disallowed_claim_roles") or []) + (row.get("disallowed_claim_roles") or []))


def _metric_id(contract: dict[str, Any], candidate: dict[str, Any], metric_family: str, metric_role: str) -> str:
    prefix = "_".join(
        _safe_part(part)
        for part in [
            contract.get("ticker"),
            contract.get("fiscal_year"),
            metric_family,
            metric_role,
        ]
        if part
    )
    digest = hashlib.sha1(
        "||".join(
            str(part)
            for part in [
                contract.get("query_id"),
                contract.get("object_id"),
                candidate.get("metric_object_id"),
                candidate.get("raw_value_text"),
                candidate.get("unit"),
                metric_family,
                metric_role,
            ]
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"{prefix}_{digest}"[:180]


def _primary_family(candidate: dict[str, Any]) -> str:
    families = [family for family in candidate.get("metric_families") or [] if family != "unknown"]
    context_families = _context_metric_families(candidate)
    for family in families:
        if family in context_families:
            return family
    if context_families:
        return context_families[0]
    return families[0] if families else "unknown"


def _context_metric_families(candidate: dict[str, Any]) -> list[str]:
    text = " ".join(
        str(candidate.get(key) or "")
        for key in ("source_statement", "metric_label", "row_label", "segment")
    ).lower()
    families = []
    for family, pattern in CONTEXT_FAMILY_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            families.append(family)
    candidate_families = [family for family in candidate.get("metric_families") or [] if family != "unknown"]
    if re.search(r"\bnet revenue\b|\brevenues?\b|\bsales\b", text, flags=re.I):
        families.extend(family for family in candidate_families if family in REVENUE_FAMILIES)
    return _unique(families)


def _normalized_value(value: Any, unit: Any, raw_value: Any) -> tuple[float | None, str | None]:
    number = _to_float(value)
    if number is None:
        return None, None
    unit_text = str(unit or "").lower()
    raw = str(raw_value or "").lower()
    if unit_text == "percent":
        return number, "percent"
    if unit_text == "usd_millions":
        return number * 1_000_000, "usd"
    if unit_text == "usd_thousands":
        return number * 1_000, "usd"
    if unit_text == "usd_billions" or "billion" in raw:
        return number * 1_000_000_000, "usd"
    if "million" in raw:
        return number * 1_000_000, "usd"
    if unit_text == "usd":
        return number, "usd_source_scale"
    return number, unit_text or None


def _report(
    rows: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    input_candidate_count: int,
    *,
    args: argparse.Namespace,
    contracts_payload: dict[str, Any],
) -> dict[str, Any]:
    rejection_counts = Counter(
        reason for item in rejected for reason in item.get("rejection_reasons") or []
    )
    summary = {
        "query_count": len({row.get("query_id") for row in rows}),
        "ledger_row_count": len(rows),
        "input_numeric_candidate_count": input_candidate_count,
        "rejected_numeric_candidate_count": len(rejected),
        "ledger_accept_rate": _ratio(len(rows), input_candidate_count),
        "query_row_counts": dict(sorted(Counter(str(row.get("query_id")) for row in rows).items())),
        "metric_family_counts": dict(sorted(Counter(str(row.get("metric_family")) for row in rows).items())),
        "metric_role_counts": dict(sorted(Counter(str(row.get("metric_role")) for row in rows).items())),
        "unit_counts": dict(sorted(Counter(str(row.get("unit")) for row in rows).items())),
        "rejection_reason_counts": dict(sorted(rejection_counts.items())),
        "missing_display_value_rows": sum(1 for row in rows if not row.get("display_value_zh")),
        "unknown_metric_role_rows": sum(1 for row in rows if row.get("metric_role") == "unknown"),
        "unknown_metric_family_rows": sum(1 for row in rows if row.get("metric_family") == "unknown"),
        "context_family_override_rows": sum(
            1
            for row in rows
            if row.get("source_context_metric_families")
            and row.get("metric_family") == (row.get("source_context_metric_families") or [None])[0]
            and (row.get("metric_families") or [None])[0] != row.get("metric_family")
        ),
        "context_family_conflict_rows": sum(1 for row in rows if _context_family_conflict(row)),
    }
    hard_failures = []
    if summary["missing_display_value_rows"]:
        hard_failures.append({"type": "ledger_row_missing_display_value", "count": summary["missing_display_value_rows"]})
    if summary["unknown_metric_role_rows"]:
        hard_failures.append({"type": "ledger_row_unknown_metric_role", "count": summary["unknown_metric_role_rows"]})
    if summary["unknown_metric_family_rows"]:
        hard_failures.append({"type": "ledger_row_unknown_metric_family", "count": summary["unknown_metric_family_rows"]})
    if summary["context_family_conflict_rows"]:
        hard_failures.append(
            {
                "type": "metric_family_table_context_conflict",
                "count": summary["context_family_conflict_rows"],
            }
        )
    return {
        "schema_version": "exact_value_ledger_validation_v0.1",
        "contracts_path": str((REPO_ROOT / args.contracts_path).resolve()),
        "contracts_summary": contracts_payload.get("summary"),
        "summary": summary,
        "hard_failures": hard_failures,
        "warnings": _warnings(summary),
    }


def _warnings(summary: dict[str, Any]) -> list[dict[str, Any]]:
    warnings = []
    if summary["ledger_row_count"] == 0:
        warnings.append({"type": "empty_ledger"})
    if summary["ledger_accept_rate"] < 0.2:
        warnings.append({"type": "low_ledger_accept_rate", "value": summary["ledger_accept_rate"]})
    if summary.get("context_family_override_rows"):
        warnings.append(
            {
                "type": "metric_family_selected_from_table_context",
                "count": summary["context_family_override_rows"],
            }
        )
    return warnings


def _context_family_conflict(row: dict[str, Any]) -> bool:
    context_families = [str(item) for item in row.get("source_context_metric_families") or []]
    if not context_families:
        return False
    family = str(row.get("metric_family") or "")
    return family not in context_families


def _safe_part(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _unique(items: list[Any]) -> list[Any]:
    seen = set()
    output = []
    for item in items:
        if item and item not in seen:
            output.append(item)
            seen.add(item)
    return output


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
