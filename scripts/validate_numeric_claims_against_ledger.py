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

RELATION_VALUE_PATTERN = (
    r"\d+(?:,\d{3})*(?:\.\d+)?\s*(?:%|亿美元|百万美元|万美元|美元|亿|million|billion)"
)
TREND_RELATION_PATTERN = re.compile(
    rf"从[^。；;]{{0,80}}?(?P<start>{RELATION_VALUE_PATTERN})"
    rf"[^。；;]{{0,100}}?(?P<verb>增长至|增长到|增至|增加至|增加到|提升至|提升到|升至|上升至|"
    rf"下降至|下降到|降至|减少至|减少到|下滑至|降低至|微降至)"
    rf"[^。；;]{{0,80}}?(?P<end>{RELATION_VALUE_PATTERN})",
    flags=re.I,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate synthesis numeric_claims against an Exact-Value Ledger.")
    parser.add_argument(
        "--synthesis-path",
        default="reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v3_numeric_safe_patch_8500_repaired.json",
    )
    parser.add_argument(
        "--ledger-path",
        default="reports/exact_value_ledgers/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger.json",
    )
    parser.add_argument(
        "--output-path",
        default="reports/quality/qwen9b_longctx_128k_contract_v3_numeric_claims_vs_exact_ledger.json",
    )
    parser.add_argument("--require-metric-id", action="store_true")
    parser.add_argument("--scan-prose", action="store_true")
    parser.add_argument("--scan-relations", action="store_true")
    parser.add_argument("--validate-ledger-context", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    synthesis = _read_json(REPO_ROOT / args.synthesis_path)
    ledger = _read_json(REPO_ROOT / args.ledger_path)
    ledger_rows = ledger.get("rows") or []
    ledger_by_query = {}
    ledger_by_metric_id = {}
    for row in ledger_rows:
        ledger_by_query.setdefault(str(row.get("query_id")), []).append(row)
        ledger_by_metric_id[str(row.get("metric_id"))] = row

    claim_reports = []
    prose_reports = []
    relation_reports = []
    for result in synthesis.get("results") or []:
        query_id = str(result.get("query_id") or "")
        authorized_metric_ids = set(str(item) for item in (result.get("package_metrics") or {}).get("input_authorized_metric_ids") or [])
        claims = (result.get("synthesis") or {}).get("numeric_claims") or []
        query_claim_reports = []
        for index, claim in enumerate(claims, start=1):
            query_claim_reports.append(
                _validate_claim(
                    query_id,
                    index,
                    claim,
                    ledger_by_query.get(query_id, []),
                    ledger_by_metric_id,
                    authorized_metric_ids,
                    require_metric_id=args.require_metric_id,
                    validate_ledger_context=args.validate_ledger_context,
                )
            )
        claim_reports.extend(query_claim_reports)
        if args.scan_prose:
            prose_reports.extend(
                _validate_prose_values(
                    query_id,
                    result.get("synthesis") or {},
                    _authorized_display_values(query_claim_reports, ledger_by_metric_id),
                )
            )
        if args.scan_relations:
            relation_reports.extend(
                _validate_prose_relations(
                    query_id,
                    result.get("synthesis") or {},
                    _authorized_rows_from_claims(query_id, claims, ledger_by_metric_id, authorized_metric_ids),
                )
            )

    hard_failure_types = Counter(
        item.get("failure_type") or item.get("type")
        for item in claim_reports + prose_reports + relation_reports
        if item.get("status") != "pass"
    )
    report = {
        "schema_version": "numeric_claims_vs_exact_ledger_v0.1",
        "synthesis_path": str((REPO_ROOT / args.synthesis_path).resolve()),
        "ledger_path": str((REPO_ROOT / args.ledger_path).resolve()),
        "require_metric_id": args.require_metric_id,
        "scan_prose": args.scan_prose,
        "scan_relations": args.scan_relations,
        "validate_ledger_context": args.validate_ledger_context,
        "summary": {
            "numeric_claim_count": len(claim_reports),
            "pass_count": sum(item.get("status") == "pass" for item in claim_reports),
            "fail_count": sum(item.get("status") != "pass" for item in claim_reports),
            "pass_rate": _ratio(sum(item.get("status") == "pass" for item in claim_reports), len(claim_reports)),
            "prose_exact_value_count": len(prose_reports),
            "prose_fail_count": sum(item.get("status") != "pass" for item in prose_reports),
            "prose_relation_count": len(relation_reports),
            "prose_relation_fail_count": sum(item.get("status") != "pass" for item in relation_reports),
            "failure_types": dict(sorted(hard_failure_types.items())),
            "fail_by_query": dict(
                sorted(
                    Counter(
                        item.get("query_id")
                        for item in claim_reports + prose_reports + relation_reports
                        if item.get("status") != "pass"
                    ).items()
                )
            ),
        },
        "claims": claim_reports,
        "prose_values": prose_reports,
        "prose_relations": relation_reports,
    }
    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_path": str(output_path), **report["summary"]}, ensure_ascii=False, indent=2))


def _validate_claim(
    query_id: str,
    index: int,
    claim: dict[str, Any],
    ledger_rows: list[dict[str, Any]],
    ledger_by_metric_id: dict[str, dict[str, Any]],
    authorized_metric_ids: set[str],
    *,
    require_metric_id: bool,
    validate_ledger_context: bool,
) -> dict[str, Any]:
    cited_ids = [str(item) for item in claim.get("cited_object_ids") or []]
    metric_id = str(claim.get("metric_id") or "").strip()
    if metric_id:
        row = ledger_by_metric_id.get(metric_id)
        if not row or str(row.get("query_id")) != query_id:
            return _claim_failure(query_id, index, "metric_id_not_in_query_ledger", claim, cited_ids, [])
        if authorized_metric_ids and metric_id not in authorized_metric_ids:
            return _claim_failure(query_id, index, "metric_id_not_authorized_by_prompt", claim, cited_ids, [row])
        if validate_ledger_context:
            context_issue = _ledger_context_issue(row)
            if context_issue:
                return {
                    "query_id": query_id,
                    "claim_index": index,
                    "status": "fail",
                    "failure_type": "metric_family_table_context_conflict",
                    "metric_id": metric_id,
                    "raw_value_text": claim.get("raw_value_text"),
                    "display_value_zh": claim.get("display_value_zh"),
                    "metric_role": claim.get("metric_role"),
                    "cited_object_ids": cited_ids,
                    "ledger_row": _ledger_preview(row),
                    "context_issue": context_issue,
                }
        mismatches = []
        for claim_key, row_key in (
            ("raw_value_text", "raw_value_text"),
            ("display_value_zh", "display_value_zh"),
            ("unit", "unit"),
            ("metric_role", "metric_role"),
        ):
            if str(claim.get(claim_key) or "") != str(row.get(row_key) or ""):
                mismatches.append(
                    {
                        "field": claim_key,
                        "claim_value": claim.get(claim_key),
                        "ledger_value": row.get(row_key),
                    }
                )
        allowed_cited_ids = {str(row.get("object_id"))} | {str(item) for item in row.get("supporting_contract_ids") or []}
        if not set(cited_ids) & allowed_cited_ids:
            mismatches.append(
                {
                    "field": "cited_object_ids",
                    "claim_value": cited_ids,
                    "ledger_value": sorted(allowed_cited_ids),
                }
            )
        if mismatches:
            return {
                "query_id": query_id,
                "claim_index": index,
                "status": "fail",
                "failure_type": "metric_id_fields_not_copied_from_ledger",
                "metric_id": metric_id,
                "mismatches": mismatches,
                "raw_value_text": claim.get("raw_value_text"),
                "display_value_zh": claim.get("display_value_zh"),
                "metric_role": claim.get("metric_role"),
                "cited_object_ids": cited_ids,
                "ledger_row": _ledger_preview(row),
            }
        return {
            "query_id": query_id,
            "claim_index": index,
            "status": "pass",
            "matched_metric_ids": [metric_id],
            "metric_id": metric_id,
            "raw_value_text": claim.get("raw_value_text"),
            "display_value_zh": claim.get("display_value_zh"),
            "metric_role": claim.get("metric_role"),
            "cited_object_ids": cited_ids,
        }
    if require_metric_id:
        return _claim_failure(query_id, index, "numeric_claim_missing_metric_id", claim, cited_ids, [])

    candidate_rows = [row for row in ledger_rows if str(row.get("object_id")) in set(cited_ids)]
    raw = _norm_value(claim.get("raw_value_text"))
    display = str(claim.get("display_value_zh") or "")
    role = str(claim.get("metric_role") or "")
    raw_display_matches = [
        row
        for row in candidate_rows
        if _norm_value(row.get("raw_value_text")) == raw or str(row.get("display_value_zh") or "") == display
    ]
    role_matches = [row for row in raw_display_matches if not role or str(row.get("metric_role")) == role]
    if role_matches:
        return {
            "query_id": query_id,
            "claim_index": index,
            "status": "pass",
            "matched_metric_ids": [row.get("metric_id") for row in role_matches[:5]],
            "raw_value_text": claim.get("raw_value_text"),
            "display_value_zh": display,
            "metric_role": role,
            "cited_object_ids": cited_ids,
        }
    failure_type = "numeric_claim_not_in_ledger"
    if raw_display_matches:
        failure_type = "metric_role_not_allowed_by_ledger"
    elif not candidate_rows:
        failure_type = "cited_object_has_no_ledger_rows"
    return {
        "query_id": query_id,
        "claim_index": index,
        "status": "fail",
        "failure_type": failure_type,
        "raw_value_text": claim.get("raw_value_text"),
        "display_value_zh": display,
        "metric_role": role,
        "cited_object_ids": cited_ids,
        "ledger_candidate_count_for_cited_objects": len(candidate_rows),
        "ledger_candidate_preview": [
            {
                "metric_id": row.get("metric_id"),
                "raw_value_text": row.get("raw_value_text"),
                "display_value_zh": row.get("display_value_zh"),
                "metric_role": row.get("metric_role"),
                "metric_family": row.get("metric_family"),
            }
            for row in candidate_rows[:8]
        ],
    }


def _claim_failure(
    query_id: str,
    index: int,
    failure_type: str,
    claim: dict[str, Any],
    cited_ids: list[str],
    candidate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "query_id": query_id,
        "claim_index": index,
        "status": "fail",
        "failure_type": failure_type,
        "metric_id": claim.get("metric_id"),
        "raw_value_text": claim.get("raw_value_text"),
        "display_value_zh": claim.get("display_value_zh"),
        "metric_role": claim.get("metric_role"),
        "cited_object_ids": cited_ids,
        "ledger_candidate_count": len(candidate_rows),
        "ledger_candidate_preview": [_ledger_preview(row) for row in candidate_rows[:8]],
    }


def _ledger_preview(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "metric_id": row.get("metric_id"),
        "raw_value_text": row.get("raw_value_text"),
        "display_value_zh": row.get("display_value_zh"),
        "unit": row.get("unit"),
        "metric_role": row.get("metric_role"),
        "metric_family": row.get("metric_family"),
        "object_id": row.get("object_id"),
    }


def _authorized_display_values(
    query_claim_reports: list[dict[str, Any]],
    ledger_by_metric_id: dict[str, dict[str, Any]],
) -> set[str]:
    displays = set()
    for report in query_claim_reports:
        if report.get("status") != "pass":
            continue
        for metric_id in report.get("matched_metric_ids") or []:
            row = ledger_by_metric_id.get(str(metric_id))
            if row and row.get("display_value_zh"):
                displays.add(str(row.get("display_value_zh")))
    return displays


def _authorized_rows_from_claims(
    query_id: str,
    claims: list[dict[str, Any]],
    ledger_by_metric_id: dict[str, dict[str, Any]],
    authorized_metric_ids: set[str],
) -> list[dict[str, Any]]:
    rows = []
    seen: set[str] = set()
    for claim in claims:
        metric_id = str(claim.get("metric_id") or "")
        row = ledger_by_metric_id.get(metric_id)
        if not row or str(row.get("query_id")) != query_id:
            continue
        if authorized_metric_ids and metric_id not in authorized_metric_ids:
            continue
        if metric_id in seen:
            continue
        seen.add(metric_id)
        rows.append(row)
    return rows


def _validate_prose_values(query_id: str, synthesis: dict[str, Any], authorized_displays: set[str]) -> list[dict[str, Any]]:
    text_by_location = _prose_text_by_location(synthesis)
    reports = []
    for location, text in text_by_location:
        for value in _exact_value_hits(text):
            status = "pass" if any(value in display or display in value for display in authorized_displays) else "fail"
            report = {
                "query_id": query_id,
                "location": location,
                "value": value,
                "status": status,
            }
            if status != "pass":
                report["type"] = "prose_exact_value_not_authorized_by_metric_id"
            reports.append(report)
    return reports


def _validate_prose_relations(
    query_id: str,
    synthesis: dict[str, Any],
    authorized_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    authorized_displays = {_compact_display(row.get("display_value_zh")) for row in authorized_rows if row.get("display_value_zh")}
    reports = []
    for location, text in _prose_text_by_location(synthesis):
        for match in TREND_RELATION_PATTERN.finditer(text):
            start_text = match.group("start").strip()
            end_text = match.group("end").strip()
            verb = match.group("verb")
            start = _parse_relation_value(start_text)
            end = _parse_relation_value(end_text)
            report = {
                "query_id": query_id,
                "location": location,
                "relation_text": match.group(0),
                "start_value": start_text,
                "end_value": end_text,
                "verb": verb,
                "status": "pass",
            }
            if start is None or end is None:
                report.update({"status": "fail", "type": "prose_numeric_relation_unparseable"})
            elif start["unit_kind"] != end["unit_kind"]:
                report.update(
                    {
                        "status": "fail",
                        "type": "prose_numeric_relation_unit_mismatch",
                        "start_unit_kind": start["unit_kind"],
                        "end_unit_kind": end["unit_kind"],
                    }
                )
            elif _compact_display(start_text) not in authorized_displays or _compact_display(end_text) not in authorized_displays:
                report.update({"status": "fail", "type": "prose_numeric_relation_value_not_authorized"})
            else:
                direction = _trend_direction(verb)
                if direction == "increase" and end["value"] < start["value"]:
                    report.update(
                        {
                            "status": "fail",
                            "type": "prose_numeric_relation_direction_mismatch",
                            "expected": "end >= start",
                            "start_numeric": start["value"],
                            "end_numeric": end["value"],
                        }
                    )
                elif direction == "decrease" and end["value"] > start["value"]:
                    report.update(
                        {
                            "status": "fail",
                            "type": "prose_numeric_relation_direction_mismatch",
                            "expected": "end <= start",
                            "start_numeric": start["value"],
                            "end_numeric": end["value"],
                        }
                    )
            reports.append(report)
    return reports


def _prose_text_by_location(synthesis: dict[str, Any]) -> list[tuple[str, str]]:
    rows = [
        ("answer_zh", str(synthesis.get("answer_zh") or "")),
        ("thesis_zh", str(synthesis.get("thesis_zh") or "")),
        ("evidence_use_notes_zh", str(synthesis.get("evidence_use_notes_zh") or "")),
    ]
    for index, item in enumerate(synthesis.get("decision_drivers") or [], start=1):
        rows.append((f"decision_drivers[{index}]", " ".join(str(item.get(key) or "") for key in ("driver_zh", "decision_impact_zh"))))
    for index, item in enumerate(synthesis.get("secondary_context") or [], start=1):
        rows.append((f"secondary_context[{index}]", " ".join(str(item.get(key) or "") for key in ("context_zh", "why_secondary_zh"))))
    for index, item in enumerate(synthesis.get("limiting_caveats") or [], start=1):
        rows.append((f"limiting_caveats[{index}]", " ".join(str(item.get(key) or "") for key in ("caveat_zh", "impact_on_thesis_zh"))))
    for index, item in enumerate(synthesis.get("facet_findings") or [], start=1):
        rows.append((f"facet_findings[{index}]", str(item.get("takeaway_zh") or "")))
    return rows


def _exact_value_hits(text: str) -> list[str]:
    patterns = [
        r"\$[\s\d,.]+(?:million|billion)?",
        r"\b\d+(?:\.\d+)?%",
        r"\d+(?:\.\d+)?\s*(?:亿美元|百万美元|万美元|美元|亿|million|billion)",
        r"\b\d{1,3},\d{3}(?:,\d{3})*\b",
    ]
    hits = []
    for pattern in patterns:
        hits.extend(re.findall(pattern, text, flags=re.I))
    return sorted(set(hit.strip() for hit in hits if hit.strip()))


def _ledger_context_issue(row: dict[str, Any]) -> dict[str, Any] | None:
    context_families = row.get("source_context_metric_families") or _context_metric_families(row)
    if not context_families:
        return None
    family = str(row.get("metric_family") or "")
    if family in {str(item) for item in context_families}:
        return None
    return {
        "metric_family": family,
        "source_context_metric_families": context_families,
        "source_statement": row.get("source_statement"),
    }


def _context_metric_families(row: dict[str, Any]) -> list[str]:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("source_statement", "metric_label", "row_label", "segment")
    ).lower()
    families = []
    for family, pattern in CONTEXT_FAMILY_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            families.append(family)
    row_families = [str(item) for item in row.get("metric_families") or []]
    if str(row.get("metric_family") or ""):
        row_families.append(str(row.get("metric_family")))
    if re.search(r"\bnet revenue\b|\brevenues?\b|\bsales\b", text, flags=re.I):
        families.extend(family for family in row_families if family in REVENUE_FAMILIES)
    return list(dict.fromkeys(families))


def _parse_relation_value(text: str) -> dict[str, Any] | None:
    match = re.search(r"\d+(?:,\d{3})*(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0).replace(",", ""))
    lower = text.lower()
    if "%" in text:
        return {"value": number, "unit_kind": "percent"}
    if "亿美元" in text or re.search(r"\b亿\b", text):
        return {"value": number * 100_000_000, "unit_kind": "usd"}
    if "百万美元" in text or "million" in lower:
        return {"value": number * 1_000_000, "unit_kind": "usd"}
    if "万美元" in text:
        return {"value": number * 10_000, "unit_kind": "usd"}
    if "billion" in lower:
        return {"value": number * 1_000_000_000, "unit_kind": "usd"}
    if "美元" in text:
        return {"value": number, "unit_kind": "usd"}
    return None


def _trend_direction(verb: str) -> str:
    if re.search(r"下降|降至|减少|下滑|降低|微降", verb):
        return "decrease"
    return "increase"


def _compact_display(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").replace(",", "")).lower()


def _norm_value(value: Any) -> str:
    text = str(value or "").lower()
    text = text.replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
    return re.sub(r"\s+", "", text)


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
