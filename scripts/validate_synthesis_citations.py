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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate final synthesis citations against the calibrated evidence pool."
    )
    parser.add_argument(
        "--synthesis-path",
        default="reports/demo/qwen9b_expanded_v0_2_synthesis_demo.json",
    )
    parser.add_argument(
        "--grouped-pool-path",
        default="reports/evidence_pool/sec_tech_10k_expanded_v0_2_calibrated_evidence_pool_grouped.json",
    )
    parser.add_argument(
        "--output-path",
        default="reports/quality/sec_tech_10k_expanded_v0_2_citation_validation.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    synthesis = _read_json(REPO_ROOT / args.synthesis_path)
    grouped_pool = _read_json(REPO_ROOT / args.grouped_pool_path)
    evidence_index = _evidence_index(grouped_pool)
    pool_scope = _pool_scope(grouped_pool)

    query_reports = [
        _validate_query(result, evidence_index, pool_scope.get(str(result.get("query_id")), {}))
        for result in synthesis.get("results", [])
    ]
    report = _summarize(query_reports)
    report.update(
        {
            "mode": "synthesis_citation_validation",
            "schema_version": "citation_validation_v0.1",
            "synthesis_path": str(REPO_ROOT / args.synthesis_path),
            "grouped_pool_path": str(REPO_ROOT / args.grouped_pool_path),
            "output_path": str(REPO_ROOT / args.output_path),
            "queries": query_reports,
        }
    )

    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _validate_query(
    result: dict[str, Any],
    evidence_index: dict[str, dict[str, Any]],
    scope: dict[str, Any],
) -> dict[str, Any]:
    query_id = str(result.get("query_id") or "")
    synthesis = result.get("synthesis") or {}
    package_metrics = result.get("package_metrics") or {}
    output_metrics = result.get("output_metrics") or {}
    hard_failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if result.get("parse_status") != "parsed":
        hard_failures.append(
            {
                "type": "invalid_json",
                "detail": f"parse_status={result.get('parse_status')}",
            }
        )

    input_citation_ids = set(package_metrics.get("input_citation_object_ids") or [])
    input_background_ids = set(package_metrics.get("input_background_object_ids") or [])
    valid_input_ids = input_citation_ids | input_background_ids
    cited_ids = _cited_ids(synthesis)

    for object_id in cited_ids:
        if object_id not in valid_input_ids:
            hard_failures.append({"type": "invalid_object_id", "object_id": object_id})
            continue
        if object_id in input_background_ids and object_id not in input_citation_ids:
            hard_failures.append({"type": "background_cited_as_fact", "object_id": object_id})
        evidence = evidence_index.get(object_id, {})
        if not evidence.get("source_evidence_id"):
            hard_failures.append({"type": "missing_source_trace", "object_id": object_id})
        scope_issue = _scope_issue(object_id, evidence, scope)
        if scope_issue:
            warnings.append(scope_issue)

    missing_count = int(package_metrics.get("missing_aspect_count") or 0)
    model_missing_count = max(
        int(output_metrics.get("model_missing_or_uncertain_count") or 0),
        _missing_signal_count(synthesis),
    )
    if missing_count > 0 and model_missing_count == 0:
        hard_failures.append(
            {
                "type": "missing_aspects_not_acknowledged",
                "missing_aspect_count": missing_count,
            }
        )

    warnings.extend(_number_support_warnings(synthesis, evidence_index))
    warnings.extend(_numeric_claim_warnings(synthesis, evidence_index))
    warnings.extend(_metric_role_narrative_warnings(synthesis))

    return {
        "query_id": query_id,
        "parse_status": result.get("parse_status"),
        "conclusion_quality": synthesis.get("conclusion_quality"),
        "input_citation_count": len(input_citation_ids),
        "input_background_count": len(input_background_ids),
        "cited_object_count": len(set(cited_ids)),
        "invalid_cited_object_ids": output_metrics.get("invalid_cited_object_ids") or [],
        "hard_failure_count": len(hard_failures),
        "warning_count": len(warnings),
        "hard_failures": hard_failures,
        "warnings": warnings,
        "status": "pass" if not hard_failures else "repair_required",
    }


def _scope_issue(object_id: str, evidence: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any] | None:
    tickers = set(str(item).upper() for item in scope.get("tickers") or [] if item)
    fiscal_years = set(int(item) for item in scope.get("fiscal_years") or [] if item)
    object_ticker = str(evidence.get("object_ticker") or evidence.get("ticker") or "").upper()
    object_year = evidence.get("object_fiscal_year") or evidence.get("fiscal_year")
    if tickers and object_ticker and object_ticker not in tickers:
        return {
            "type": "ticker_scope_mismatch",
            "object_id": object_id,
            "object_ticker": object_ticker,
            "allowed_tickers": sorted(tickers),
        }
    try:
        object_year_int = int(object_year) if object_year is not None else None
    except (TypeError, ValueError):
        object_year_int = None
    if fiscal_years and object_year_int is not None and object_year_int not in fiscal_years:
        return {
            "type": "year_scope_mismatch",
            "object_id": object_id,
            "object_fiscal_year": object_year_int,
            "allowed_fiscal_years": sorted(fiscal_years),
        }
    return None


def _number_support_warnings(
    synthesis: dict[str, Any],
    evidence_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    warnings = []
    for finding_index, finding in enumerate(_claim_records(synthesis), start=1):
        claim = str(
            finding.get("claim_text")
            or finding.get("claim_zh")
            or finding.get("takeaway_zh")
            or finding.get("driver_zh")
            or finding.get("context_zh")
            or finding.get("caveat_zh")
            or ""
        )
        numbers = _numbers(claim)
        if not numbers:
            continue
        cited_ids = [str(item) for item in finding.get("cited_object_ids") or []]
        cited_text = " ".join(str(evidence_index.get(object_id, {}).get("object_text") or "") for object_id in cited_ids)
        normalized_text = _normalize_number_text(cited_text)
        unsupported = [number for number in numbers if number not in normalized_text]
        if unsupported:
            warnings.append(
                {
                    "type": "number_not_verbatim_in_cited_text",
                    "finding_index": finding_index,
                    "numbers": unsupported,
                    "cited_object_ids": cited_ids,
                    "note": "diagnostic only; Chinese unit conversion can make this conservative",
                }
            )
    return warnings


def _numeric_claim_warnings(
    synthesis: dict[str, Any],
    evidence_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    warnings = []
    for claim_index, claim in enumerate(synthesis.get("numeric_claims") or [], start=1):
        cited_ids = [str(item) for item in claim.get("cited_object_ids") or [] if str(item).strip()]
        cited_text = " ".join(str(evidence_index.get(object_id, {}).get("object_text") or "") for object_id in cited_ids)
        normalized_text = _normalize_number_text(cited_text).lower()
        raw_value = str(claim.get("raw_value_text") or "").strip()
        metric_role = str(claim.get("metric_role") or "")
        if not cited_ids:
            warnings.append({"type": "numeric_claim_missing_citation", "claim_index": claim_index})
            continue
        if not raw_value:
            warnings.append(
                {
                    "type": "numeric_claim_missing_raw_value",
                    "claim_index": claim_index,
                    "cited_object_ids": cited_ids,
                }
            )
        elif _normalize_number_text(raw_value).lower() not in normalized_text:
            warnings.append(
                {
                    "type": "numeric_claim_raw_value_not_in_cited_text",
                    "claim_index": claim_index,
                    "raw_value_text": raw_value,
                    "cited_object_ids": cited_ids,
                }
            )
        inferred_roles = {_infer_metric_role_from_text(str(evidence_index.get(object_id, {}).get("object_text") or "")) for object_id in cited_ids}
        if "period_change_amount" in inferred_roles and metric_role == "total_value":
            warnings.append(
                {
                    "type": "metric_role_mismatch_period_change_as_total",
                    "claim_index": claim_index,
                    "raw_value_text": raw_value,
                    "cited_object_ids": cited_ids,
                }
            )
        if "percentage_rate" in inferred_roles and metric_role not in {"percentage_rate", "ratio"}:
            warnings.append(
                {
                    "type": "metric_role_mismatch_rate_as_amount",
                    "claim_index": claim_index,
                    "raw_value_text": raw_value,
                    "cited_object_ids": cited_ids,
                }
            )
        if metric_role == "unknown" and raw_value:
            warnings.append(
                {
                    "type": "numeric_claim_unknown_metric_role",
                    "claim_index": claim_index,
                    "raw_value_text": raw_value,
                    "cited_object_ids": cited_ids,
                }
            )
        display_value = str(claim.get("display_value_zh") or "")
        unit = str(claim.get("unit") or "").lower()
        role_check = str(claim.get("role_check_zh") or "").lower()
        if "million" in unit and "亿" in display_value and not any(
            marker in role_check for marker in ("换算", "million", "百万", "billion")
        ):
            warnings.append(
                {
                    "type": "numeric_conversion_without_role_check",
                    "claim_index": claim_index,
                    "raw_value_text": raw_value,
                    "display_value_zh": display_value,
                    "cited_object_ids": cited_ids,
                }
            )
    return warnings


def _metric_role_narrative_warnings(synthesis: dict[str, Any]) -> list[dict[str, Any]]:
    warnings = []
    narrative_records = _narrative_records(synthesis)
    for claim_index, claim in enumerate(synthesis.get("numeric_claims") or [], start=1):
        metric_role = str(claim.get("metric_role") or "")
        if metric_role != "period_change_amount":
            continue
        markers = _value_markers(claim)
        if not markers:
            continue
        for record_index, record in enumerate(narrative_records, start=1):
            text = _compact_text(str(record.get("text") or ""))
            if not text:
                continue
            for marker in markers:
                if marker not in text:
                    continue
                if _period_change_used_as_total_series(text, marker):
                    warnings.append(
                        {
                            "type": "metric_role_mismatch_period_change_in_narrative",
                            "claim_index": claim_index,
                            "record_index": record_index,
                            "section": record.get("section"),
                            "display_value_zh": claim.get("display_value_zh"),
                            "raw_value_text": claim.get("raw_value_text"),
                        }
                    )
                    break
    return warnings


def _narrative_records(synthesis: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if synthesis.get("answer_zh"):
        records.append({"section": "answer_zh", "text": synthesis.get("answer_zh")})
    if synthesis.get("thesis_zh"):
        records.append({"section": "thesis_zh", "text": synthesis.get("thesis_zh")})
    for section, keys in (
        ("decision_drivers", ("driver_zh", "decision_impact_zh")),
        ("secondary_context", ("context_zh", "why_secondary_zh")),
        ("key_findings", ("claim_zh",)),
        ("facet_findings", ("facet_zh", "takeaway_zh")),
    ):
        for item in synthesis.get(section) or []:
            text = " ".join(str(item.get(key) or "") for key in keys)
            records.append({"section": section, "text": text})
    return records


def _value_markers(claim: dict[str, Any]) -> list[str]:
    markers: list[str] = []
    for key in ("display_value_zh", "raw_value_text"):
        value = _compact_text(str(claim.get(key) or ""))
        if value:
            markers.append(value)
    return list(dict.fromkeys(markers))


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _period_change_used_as_total_series(text: str, marker: str) -> bool:
    total_terms = r"(总收入|总营收|总额|期末余额|收入规模|营收规模|revenue|total|balance)"
    series_terms = r"(至|到|升至|增长至|增至|达到|to)"
    return bool(
        re.search(rf"从[^。；;]*{re.escape(marker)}[^。；;]*{series_terms}", text)
        or re.search(rf"{re.escape(marker)}[^。；;]{{0,40}}{total_terms}", text)
        or re.search(rf"{total_terms}[^。；;]{{0,20}}(为|是|of|was|were)[^。；;]{{0,20}}{re.escape(marker)}", text)
    )


def _numbers(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?%?", text)))


def _normalize_number_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace(",", "")).strip()


def _infer_metric_role_from_text(text: str) -> str:
    lower = text.lower()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    unit = lines[9].lower() if len(lines) > 9 else ""
    raw_value = lines[7] if len(lines) > 7 else ""
    source_statement = " ".join(lines[12:14]) if len(lines) > 12 else text
    raw_lower = raw_value.lower()
    if unit in {"percent", "%"} or "%" in raw_value:
        return "percentage_rate"
    if _raw_value_is_period_change(raw_value, source_statement):
        return "period_change_amount"
    if "$" in raw_value or "usd" in unit or "dollar" in raw_lower:
        return "total_value"
    if any(term in lower for term in ("margin", " rate")):
        return "percentage_rate"
    if any(term in lower for term in ("remaining performance obligations", "revenue", "sales", "income", "cash flow")):
        return "total_value"
    return "unknown"


def _raw_value_is_period_change(raw_value: str, source_statement: str) -> bool:
    number_match = re.search(r"\d+(?:,\d{3})*(?:\.\d+)?", raw_value)
    if not number_match:
        return False
    number = re.escape(number_match.group(0).replace(",", ""))
    normalized_statement = source_statement.replace(",", "").lower()
    return bool(re.search(rf"\b(?:by|or)\s+\$?\s*{number}\b", normalized_statement))


def _cited_ids(synthesis: dict[str, Any]) -> list[str]:
    cited: list[str] = []
    for finding in synthesis.get("decision_drivers") or []:
        cited.extend(str(item) for item in finding.get("cited_object_ids") or [] if str(item).strip())
    for finding in synthesis.get("secondary_context") or []:
        cited.extend(str(item) for item in finding.get("cited_object_ids") or [] if str(item).strip())
    for finding in synthesis.get("limiting_caveats") or []:
        cited.extend(str(item) for item in finding.get("cited_object_ids") or [] if str(item).strip())
    for finding in synthesis.get("key_findings") or []:
        cited.extend(str(item) for item in finding.get("cited_object_ids") or [] if str(item).strip())
    for finding in synthesis.get("facet_findings") or []:
        cited.extend(str(item) for item in finding.get("cited_object_ids") or [] if str(item).strip())
    for finding in synthesis.get("numeric_claims") or []:
        cited.extend(str(item) for item in finding.get("cited_object_ids") or [] if str(item).strip())
    cell_table = synthesis.get("cell_table") or {}
    for cell in cell_table.get("cells") or []:
        object_ids = list(cell.get("citation_object_ids") or [])
        if cell.get("citation_object_id"):
            object_ids.append(cell.get("citation_object_id"))
        for object_id in object_ids:
            if object_id and str(object_id).strip():
                cited.append(str(object_id))
    return cited


def _claim_records(synthesis: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in synthesis.get("decision_drivers") or []:
        records.append(
            item
            | {
                "claim_text": " ".join(
                    str(item.get(key) or "") for key in ("driver_zh", "decision_impact_zh")
                )
            }
        )
    for item in synthesis.get("secondary_context") or []:
        records.append(
            item
            | {
                "claim_text": " ".join(
                    str(item.get(key) or "") for key in ("context_zh", "why_secondary_zh")
                )
            }
        )
    for item in synthesis.get("limiting_caveats") or []:
        records.append(
            item
            | {
                "claim_text": " ".join(
                    str(item.get(key) or "") for key in ("caveat_zh", "impact_on_thesis_zh")
                )
            }
        )
    records.extend(synthesis.get("key_findings") or [])
    records.extend(synthesis.get("facet_findings") or [])
    return records


def _missing_signal_count(synthesis: dict[str, Any]) -> int:
    return (
        len(synthesis.get("missing_or_uncertain_zh") or [])
        + len(synthesis.get("missing_evidence_by_facet") or [])
        + len(synthesis.get("limiting_caveats") or [])
    )


def _evidence_index(grouped_pool: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for query in grouped_pool.get("queries") or []:
        for facet in query.get("facets") or []:
            for role in ("citation_evidence", "background_evidence"):
                for evidence in facet.get(role) or []:
                    index[str(evidence.get("object_id"))] = evidence
            for aspect in facet.get("aspects") or []:
                for role in ("citation_evidence", "background_evidence"):
                    for evidence in aspect.get(role) or []:
                        index[str(evidence.get("object_id"))] = evidence
    return index


def _pool_scope(grouped_pool: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scope = {}
    for query in grouped_pool.get("queries") or []:
        query_id = str(query.get("query_id") or "")
        tickers = query.get("tickers") or query.get("ticker") or []
        fiscal_years = query.get("fiscal_years") or query.get("fiscal_year") or []
        if not isinstance(tickers, list):
            tickers = [tickers]
        if not isinstance(fiscal_years, list):
            fiscal_years = [fiscal_years]
        scope[query_id] = {"tickers": tickers, "fiscal_years": fiscal_years}
    return scope


def _summarize(query_reports: list[dict[str, Any]]) -> dict[str, Any]:
    hard_failure_types = Counter(
        failure["type"]
        for query in query_reports
        for failure in query.get("hard_failures", [])
    )
    warning_types = Counter(
        warning["type"]
        for query in query_reports
        for warning in query.get("warnings", [])
    )
    return {
        "query_count": len(query_reports),
        "pass_count": sum(query.get("status") == "pass" for query in query_reports),
        "repair_required_count": sum(query.get("status") == "repair_required" for query in query_reports),
        "hard_failure_types": dict(sorted(hard_failure_types.items())),
        "warning_types": dict(sorted(warning_types.items())),
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
