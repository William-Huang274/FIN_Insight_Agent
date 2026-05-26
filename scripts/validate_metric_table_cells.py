from __future__ import annotations

import argparse
import json
import math
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
        description="Validate metric/table synthesis cell_table output against MetricObject/TableObject JSONL."
    )
    parser.add_argument(
        "--eval-path",
        default="eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl",
    )
    parser.add_argument(
        "--synthesis-path",
        default="reports/demo/qwen9b_expanded_v0_2_cell_vllm_synthesis_demo_16k_shortjson.json",
    )
    parser.add_argument(
        "--metrics-path",
        default="data/processed_private/structured_objects/sec_tech_10k_metrics.jsonl",
    )
    parser.add_argument(
        "--tables-path",
        default="data/processed_private/structured_objects/sec_tech_10k_tables.jsonl",
    )
    parser.add_argument(
        "--claims-path",
        default="data/processed_private/structured_objects/sec_tech_10k_claims.jsonl",
    )
    parser.add_argument(
        "--output-path",
        default="reports/quality/sec_tech_10k_expanded_v0_2_cell_vllm_metric_cell_validation.json",
    )
    parser.add_argument("--relative-tolerance", type=float, default=0.001)
    parser.add_argument("--absolute-tolerance", type=float, default=0.01)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    eval_rows = {row["query_id"]: row for row in _read_jsonl(REPO_ROOT / args.eval_path)}
    synthesis = _read_json(REPO_ROOT / args.synthesis_path)
    object_index = _load_object_index(
        REPO_ROOT / args.metrics_path,
        REPO_ROOT / args.tables_path,
        REPO_ROOT / args.claims_path,
    )

    query_reports = [
        _validate_query(
            result,
            eval_rows.get(str(result.get("query_id")), {}),
            object_index,
            relative_tolerance=args.relative_tolerance,
            absolute_tolerance=args.absolute_tolerance,
        )
        for result in synthesis.get("results", [])
    ]
    report = _summarize(query_reports)
    report.update(
        {
            "mode": "metric_table_cell_validation",
            "schema_version": "metric_table_cell_validation_v0.1",
            "eval_path": str(REPO_ROOT / args.eval_path),
            "synthesis_path": str(REPO_ROOT / args.synthesis_path),
            "metrics_path": str(REPO_ROOT / args.metrics_path),
            "tables_path": str(REPO_ROOT / args.tables_path),
            "claims_path": str(REPO_ROOT / args.claims_path),
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
    eval_row: dict[str, Any],
    object_index: dict[str, dict[str, Any]],
    *,
    relative_tolerance: float,
    absolute_tolerance: float,
) -> dict[str, Any]:
    query_id = str(result.get("query_id") or "")
    profile = eval_row.get("scoring_profile") or result.get("mode") or "unknown"
    is_table_query = profile == "metric_table_stability"
    synthesis = result.get("synthesis") or {}
    cell_table = synthesis.get("cell_table")
    cells = cell_table.get("cells") if isinstance(cell_table, dict) else None
    cell_reports: list[dict[str, Any]] = []

    if is_table_query and not isinstance(cells, list):
        return {
            "query_id": query_id,
            "profile": profile,
            "parse_status": result.get("parse_status"),
            "is_table_query": is_table_query,
            "cell_table_present": False,
            "cell_count": 0,
            "reported_cell_count": 0,
            "missing_cell_count": 0,
            "unsupported_cell_count": 0,
            "valid_cell_count": 0,
            "valid_reported_cell_count": 0,
            "exact_cell_count": 0,
            "unit_matched_cell_count": 0,
            "invalid_cell_count": 1,
            "source_traceability_rate": 0.0,
            "reported_cell_exact_rate": 0.0,
            "unit_match_rate": 0.0,
            "cell_json_validity": 0.0,
            "hard_failures": [{"type": "missing_cell_table"}],
            "cells": [],
        }

    if isinstance(cells, list):
        for index, cell in enumerate(cells, start=1):
            cell_reports.append(
                _validate_cell(
                    cell,
                    index,
                    object_index,
                    relative_tolerance=relative_tolerance,
                    absolute_tolerance=absolute_tolerance,
                )
            )

    reported = [row for row in cell_reports if row.get("status") == "reported"]
    missing = [row for row in cell_reports if row.get("status") == "missing"]
    unsupported = [row for row in cell_reports if row.get("status") == "unsupported"]
    valid = [row for row in cell_reports if row.get("valid")]
    valid_reported = [row for row in reported if row.get("valid")]
    exact = [row for row in reported if row.get("value_match")]
    unit_matched = [row for row in reported if row.get("unit_match")]
    traced = [row for row in reported if row.get("citation_valid")]
    hard_failures = []
    warnings = []
    for row in cell_reports:
        for issue in row.get("issues") or []:
            item = {"type": issue, "cell_index": row.get("cell_index"), "citation_object_id": row.get("citation_object_id")}
            if _is_hard_cell_issue(issue, row):
                hard_failures.append(item)
            else:
                warnings.append(item)
    invalid_count = len([row for row in cell_reports if not row.get("valid")])
    return {
        "query_id": query_id,
        "profile": profile,
        "parse_status": result.get("parse_status"),
        "is_table_query": is_table_query,
        "cell_table_present": isinstance(cells, list),
        "cell_count": len(cell_reports),
        "reported_cell_count": len(reported),
        "missing_cell_count": len(missing),
        "unsupported_cell_count": len(unsupported),
        "valid_cell_count": len(valid),
        "valid_reported_cell_count": len(valid_reported),
        "exact_cell_count": len(exact),
        "unit_matched_cell_count": len(unit_matched),
        "invalid_cell_count": invalid_count,
        "source_traceability_rate": _ratio(len(traced), len(reported)),
        "reported_cell_exact_rate": _ratio(len(exact), len(reported)),
        "unit_match_rate": _ratio(len(unit_matched), len(reported)),
        "cell_json_validity": _ratio(len(valid), len(cell_reports)) if cell_reports else (0.0 if is_table_query else 1.0),
        "hard_failures": hard_failures,
        "warnings": warnings,
        "cells": cell_reports,
    }


def _is_hard_cell_issue(issue: str, row: dict[str, Any]) -> bool:
    if issue == "metric_label_low_overlap" and row.get("valid"):
        return False
    if row.get("status") in {"missing", "unsupported"}:
        return issue in {"bad_cell_status", "unsupported_cell_has_value", "missing_cell_has_value"}
    return True


def _validate_cell(
    cell: dict[str, Any],
    cell_index: int,
    object_index: dict[str, dict[str, Any]],
    *,
    relative_tolerance: float,
    absolute_tolerance: float,
) -> dict[str, Any]:
    issues: list[str] = []
    status = str(cell.get("status") or "").lower()
    if status not in {"reported", "missing", "unsupported"}:
        issues.append("bad_cell_status")
    value = _to_float(cell.get("value"))
    citation_object_ids = _citation_object_ids(cell)
    citation_object_id = citation_object_ids[0] if citation_object_ids else ""
    unit_key = _unit_key(str(cell.get("unit") or ""))
    qualitative_reported = status == "reported" and value is None and unit_key in {
        "qualitative",
        "text",
        "disclosure_text",
        "claim",
    }
    if status in {"missing", "unsupported"}:
        if value is not None:
            issues.append(f"{status}_cell_has_value")
        if not str(cell.get("note") or "").strip():
            issues.append(f"{status}_cell_missing_note")
        return _cell_report(
            cell,
            cell_index,
            issues=issues,
            citation_valid=not citation_object_id,
            ticker_match=True,
            year_match=True,
            value_match=value is None,
            unit_match=True,
            matched_object_type=None,
            matched_detail=None,
        )

    if value is None and not qualitative_reported:
        issues.append("reported_cell_missing_value")
    if not citation_object_ids:
        issues.append("reported_cell_missing_citation")
    objects = [object_index.get(item) for item in citation_object_ids]
    missing_ids = [citation_object_ids[index] for index, obj in enumerate(objects) if obj is None]
    if missing_ids:
        issues.append("citation_object_not_found")
    objects = [obj for obj in objects if obj is not None]
    if not objects:
        return _cell_report(
            cell,
            cell_index,
            issues=issues,
            citation_valid=False,
            ticker_match=False,
            year_match=False,
            value_match=False,
            unit_match=False,
            matched_object_type=None,
            matched_detail=None,
        )

    ticker_match = all(_ticker_matches(cell.get("ticker"), obj) for obj in objects)
    if not ticker_match:
        issues.append("ticker_mismatch")
    if len(objects) > 1 and _is_yoy_growth_cell(cell):
        match = _match_yoy_growth_objects(
            cell,
            objects,
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        )
        issues.extend(match.get("issues") or [])
        return _cell_report(
            cell,
            cell_index,
            issues=issues,
            citation_valid=not missing_ids,
            ticker_match=ticker_match,
            year_match=bool(match.get("year_match")),
            value_match=bool(match.get("value_match")),
            unit_match=bool(match.get("unit_match")),
            matched_object_type="derived",
            matched_detail=match.get("matched_detail"),
        )

    obj = objects[0]
    if obj.get("object_type") == "metric":
        match = _match_metric_object(
            cell,
            obj,
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        )
    elif obj.get("object_type") == "table":
        match = _match_table_object(
            cell,
            obj,
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        )
    elif obj.get("object_type") == "claim":
        match = _match_claim_object(
            cell,
            obj,
            qualitative_reported=qualitative_reported,
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        )
    else:
        match = {
            "year_match": False,
            "value_match": False,
            "unit_match": False,
            "metric_match": False,
            "matched_detail": None,
            "issues": ["unsupported_citation_object_type"],
        }
    issues.extend(match.get("issues") or [])
    return _cell_report(
        cell,
        cell_index,
        issues=issues,
        citation_valid=True,
        ticker_match=ticker_match,
        year_match=bool(match.get("year_match")),
        value_match=bool(match.get("value_match")),
        unit_match=bool(match.get("unit_match")),
        matched_object_type=obj.get("object_type"),
        matched_detail=match.get("matched_detail"),
    )


def _match_metric_object(
    cell: dict[str, Any],
    obj: dict[str, Any],
    *,
    relative_tolerance: float,
    absolute_tolerance: float,
) -> dict[str, Any]:
    issues: list[str] = []
    year_match = _year_matches(cell.get("fiscal_year"), obj.get("period")) or _year_matches(
        cell.get("fiscal_year"), obj.get("fiscal_year")
    )
    if not year_match:
        issues.append("year_mismatch")
    value_match, unit_match = _value_unit_matches(
        cell.get("value"),
        cell.get("unit"),
        obj.get("value"),
        obj.get("unit"),
        obj.get("raw_value"),
        relative_tolerance=relative_tolerance,
        absolute_tolerance=absolute_tolerance,
    )
    sign_policy = None
    if not value_match and _cash_outflow_magnitude_allowed(cell, obj):
        value_match, unit_match = _cash_outflow_magnitude_matches(
            cell.get("value"),
            cell.get("unit"),
            obj.get("value"),
            obj.get("unit"),
            obj.get("raw_value"),
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        )
        if value_match:
            sign_policy = "cash_outflow_magnitude_normalized"
    if not value_match:
        issues.append("value_mismatch")
    if not unit_match:
        issues.append("unit_mismatch")
    metric_match = _metric_text_matches(
        cell.get("metric"),
        " ".join(str(part or "") for part in [obj.get("metric_name"), obj.get("row_label"), obj.get("column_label"), obj.get("segment")]),
    )
    if not metric_match:
        issues.append("metric_label_low_overlap")
    return {
        "year_match": year_match,
        "value_match": value_match,
        "unit_match": unit_match,
        "metric_match": metric_match,
        "matched_detail": {
            "object_value": obj.get("value"),
            "object_unit": obj.get("unit"),
            "raw_value": obj.get("raw_value"),
            "metric_name": obj.get("metric_name"),
            "period": obj.get("period"),
            "sign_policy": sign_policy,
        },
        "issues": issues,
    }


def _match_table_object(
    cell: dict[str, Any],
    obj: dict[str, Any],
    *,
    relative_tolerance: float,
    absolute_tolerance: float,
) -> dict[str, Any]:
    best = None
    for table_cell in obj.get("cells") or []:
        year_match = _year_matches(cell.get("fiscal_year"), table_cell.get("period")) or _year_matches(
            cell.get("fiscal_year"), obj.get("fiscal_year")
        )
        value_match, unit_match = _value_unit_matches(
            cell.get("value"),
            cell.get("unit"),
            table_cell.get("value"),
            table_cell.get("unit"),
            table_cell.get("raw_value"),
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        )
        sign_policy = None
        if not value_match and _cash_outflow_magnitude_allowed_for_text(
            cell,
            " ".join(str(part or "") for part in [table_cell.get("row_label"), table_cell.get("column_label")]),
            table_cell.get("raw_value"),
        ):
            value_match, unit_match = _cash_outflow_magnitude_matches(
                cell.get("value"),
                cell.get("unit"),
                table_cell.get("value"),
                table_cell.get("unit"),
                table_cell.get("raw_value"),
                relative_tolerance=relative_tolerance,
                absolute_tolerance=absolute_tolerance,
            )
            if value_match:
                sign_policy = "cash_outflow_magnitude_normalized"
        metric_match = _metric_text_matches(
            cell.get("metric"),
            " ".join(
                str(part or "")
                for part in [table_cell.get("row_label"), table_cell.get("column_label"), obj.get("title")]
            ),
        )
        score = sum([year_match, value_match, unit_match, metric_match])
        candidate = {
            "score": score,
            "year_match": year_match,
            "value_match": value_match,
            "unit_match": unit_match,
            "metric_match": metric_match,
            "matched_detail": {
                "cell_key": table_cell.get("cell_key"),
                "row_label": table_cell.get("row_label"),
                "column_label": table_cell.get("column_label"),
                "period": table_cell.get("period"),
                "raw_value": table_cell.get("raw_value"),
                "value": table_cell.get("value"),
                "unit": table_cell.get("unit"),
                "sign_policy": sign_policy,
            },
        }
        if best is None or candidate["score"] > best["score"]:
            best = candidate
    if best is None:
        return {
            "year_match": False,
            "value_match": False,
            "unit_match": False,
            "metric_match": False,
            "matched_detail": None,
            "issues": ["table_has_no_numeric_cells"],
        }
    issues = []
    if not best["year_match"]:
        issues.append("year_mismatch")
    if not best["value_match"]:
        issues.append("value_mismatch")
    if not best["unit_match"]:
        issues.append("unit_mismatch")
    if not best["metric_match"]:
        issues.append("metric_label_low_overlap")
    return {**best, "issues": issues}


def _match_claim_object(
    cell: dict[str, Any],
    obj: dict[str, Any],
    *,
    qualitative_reported: bool,
    relative_tolerance: float,
    absolute_tolerance: float,
) -> dict[str, Any]:
    issues: list[str] = []
    year_match = _year_matches(cell.get("fiscal_year"), obj.get("fiscal_year"))
    if not year_match:
        issues.append("year_mismatch")
    claim_text = str(obj.get("claim_text") or "")
    metric_context = " ".join(
        str(part or "")
        for part in [
            claim_text,
            obj.get("claim_type"),
            " ".join(str(item) for item in obj.get("metrics_mentioned") or []),
            " ".join(str(item) for item in obj.get("entities") or []),
        ]
    )
    metric_match = _metric_text_matches(cell.get("metric"), metric_context)
    if not metric_match:
        issues.append("metric_label_low_overlap")

    if qualitative_reported:
        value_match = True
        unit_match = True
        matched_detail = {
            "claim_type": obj.get("claim_type"),
            "polarity": obj.get("polarity"),
            "claim_text": claim_text,
            "match_policy": "qualitative_claim",
        }
    else:
        value_match, unit_match, number_detail = _claim_number_matches(
            cell.get("value"),
            cell.get("unit"),
            claim_text,
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        )
        if not value_match:
            issues.append("value_mismatch")
        if not unit_match:
            issues.append("unit_mismatch")
        matched_detail = {
            "claim_type": obj.get("claim_type"),
            "polarity": obj.get("polarity"),
            "claim_text": claim_text,
            "matched_number": number_detail,
            "match_policy": "claim_numeric_text",
        }
    return {
        "year_match": year_match,
        "value_match": value_match,
        "unit_match": unit_match,
        "metric_match": metric_match,
        "matched_detail": matched_detail,
        "issues": issues,
    }


def _match_yoy_growth_objects(
    cell: dict[str, Any],
    objects: list[dict[str, Any]],
    *,
    relative_tolerance: float,
    absolute_tolerance: float,
) -> dict[str, Any]:
    target_year = _extract_year(cell.get("fiscal_year"))
    if target_year is None:
        return {
            "year_match": False,
            "value_match": False,
            "unit_match": False,
            "metric_match": False,
            "matched_detail": None,
            "issues": ["year_mismatch"],
        }
    values_by_year: dict[int, list[dict[str, Any]]] = {}
    for obj in objects:
        values_by_year.setdefault(_object_year(obj), []).extend(_object_numeric_candidates(obj))
    current = _best_numeric_candidate(values_by_year.get(target_year, []))
    prior = _best_numeric_candidate(values_by_year.get(target_year - 1, []))
    issues: list[str] = []
    year_match = current is not None and prior is not None
    if not year_match:
        issues.append("year_mismatch")
    if not current or not prior or not prior.get("canonical_value"):
        issues.extend(["value_mismatch", "unit_mismatch"])
        return {
            "year_match": year_match,
            "value_match": False,
            "unit_match": False,
            "metric_match": True,
            "matched_detail": {
                "formula": "current/prior - 1",
                "target_year": target_year,
                "current": current,
                "prior": prior,
            },
            "issues": sorted(set(issues)),
        }
    unit_match = current.get("kind") == prior.get("kind") or _compatible_unknown_units(
        str(current.get("kind")),
        str(prior.get("kind")),
    )
    derived = (float(current["canonical_value"]) / float(prior["canonical_value"]) - 1.0) * 100.0
    cell_num = _to_float(cell.get("value"))
    value_match = cell_num is not None and _numbers_close(
        cell_num,
        derived,
        max(relative_tolerance, 0.02),
        max(absolute_tolerance, 0.75),
    )
    if not value_match:
        issues.append("value_mismatch")
    if not unit_match:
        issues.append("unit_mismatch")
    return {
        "year_match": year_match,
        "value_match": value_match,
        "unit_match": unit_match,
        "metric_match": True,
        "matched_detail": {
            "formula": "current/prior - 1",
            "target_year": target_year,
            "derived_percent": round(derived, 4),
            "current": current,
            "prior": prior,
            "derivation": cell.get("derivation"),
        },
        "issues": sorted(set(issues)),
    }


def _object_numeric_candidates(obj: dict[str, Any]) -> list[dict[str, Any]]:
    if obj.get("object_type") == "metric":
        candidate = _numeric_candidate(
            obj.get("value"),
            obj.get("unit"),
            obj.get("raw_value"),
            label=" ".join(str(part or "") for part in [obj.get("metric_name"), obj.get("row_label"), obj.get("column_label")]),
        )
        return [candidate] if candidate else []
    if obj.get("object_type") == "table":
        return [
            candidate
            for cell in obj.get("cells") or []
            for candidate in [
                _numeric_candidate(
                    cell.get("value"),
                    cell.get("unit"),
                    cell.get("raw_value"),
                    label=" ".join(str(part or "") for part in [cell.get("row_label"), cell.get("column_label")]),
                )
            ]
            if candidate
        ]
    if obj.get("object_type") == "claim":
        return [
            candidate
            for item in _number_candidates(str(obj.get("claim_text") or ""))
            for candidate in [_numeric_candidate(item.get("value"), item.get("unit"), item.get("raw_value"), label=obj.get("claim_text"))]
            if candidate
        ]
    return []


def _numeric_candidate(value: Any, unit: Any, raw_value: Any, *, label: Any) -> dict[str, Any] | None:
    number = _to_float(value)
    if number is None:
        return None
    kind, canonical = _canonical_value(number, str(unit or ""), str(raw_value or ""))
    return {
        "value": number,
        "unit": unit,
        "raw_value": raw_value,
        "kind": kind,
        "canonical_value": canonical,
        "label": label,
    }


def _best_numeric_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    revenue_like = [item for item in candidates if "revenue" in str(item.get("label") or "").lower()]
    usd_like = [item for item in (revenue_like or candidates) if str(item.get("kind")) in {"usd_millions", "usd_unscaled", "unitless"}]
    return (usd_like or revenue_like or candidates)[0]


def _object_year(obj: dict[str, Any]) -> int:
    return _extract_year(obj.get("period")) or _extract_year(obj.get("fiscal_year")) or -1


def _claim_number_matches(
    cell_value: Any,
    cell_unit: Any,
    claim_text: str,
    *,
    relative_tolerance: float,
    absolute_tolerance: float,
) -> tuple[bool, bool, dict[str, Any] | None]:
    cell_num = _to_float(cell_value)
    if cell_num is None:
        return False, False, None
    candidates = _number_candidates(claim_text)
    for candidate in candidates:
        value_match, unit_match = _value_unit_matches(
            cell_num,
            cell_unit,
            candidate["value"],
            candidate["unit"],
            candidate["raw_value"],
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        )
        if value_match and unit_match:
            return True, True, candidate
    if candidates:
        return False, any(
            _value_unit_matches(
                cell_num,
                cell_unit,
                candidate["value"],
                candidate["unit"],
                candidate["raw_value"],
                relative_tolerance=relative_tolerance,
                absolute_tolerance=absolute_tolerance,
            )[1]
            for candidate in candidates
        ), candidates[0]
    return False, False, None


def _value_unit_matches(
    cell_value: Any,
    cell_unit: Any,
    object_value: Any,
    object_unit: Any,
    object_raw_value: Any,
    *,
    relative_tolerance: float,
    absolute_tolerance: float,
) -> tuple[bool, bool]:
    cell_num = _to_float(cell_value)
    object_num = _to_float(object_value)
    if cell_num is None or object_num is None:
        return False, False
    direct_unit_match = _unit_key(str(cell_unit or "")) == _unit_key(str(object_unit or ""))
    if direct_unit_match and _numbers_close(cell_num, object_num, relative_tolerance, absolute_tolerance):
        return True, True
    cell_kind, cell_canonical = _canonical_value(cell_num, str(cell_unit or ""), "")
    object_kind, object_canonical = _canonical_value(object_num, str(object_unit or ""), str(object_raw_value or ""))
    unit_match = cell_kind == object_kind or _compatible_unknown_units(cell_kind, object_kind)
    if unit_match:
        if _numbers_close(cell_canonical, object_canonical, relative_tolerance, absolute_tolerance):
            return True, True
        if _numbers_close(cell_canonical, object_canonical / 1000.0, relative_tolerance, absolute_tolerance) and _sec_table_thousands_scale_allowed(
            cell_kind,
            object_kind,
            object_num,
        ):
            return True, True
        return False, True
    return _numbers_close(cell_num, object_num, relative_tolerance, absolute_tolerance), False


def _canonical_value(value: float, unit: str, raw_value: str) -> tuple[str, float]:
    text = f"{unit} {raw_value}".lower()
    if "%" in text or "percent" in text or "percentage" in text or "pct" in text:
        return "percent", value
    if "bps" in text or "basis point" in text:
        return "basis_points", value
    if "usd_thousands" in text or "in thousands" in text or "thousand" in text:
        return "usd_millions", value / 1000.0
    if "usd_millions" in text or "in millions" in text or "million" in text or "millions" in text:
        return "usd_millions", value
    if "usd_billions" in text or "billion" in text or "billions" in text or "bn" in text:
        return "usd_millions", value * 1000.0
    if "亿美元" in text:
        return "usd_millions", value * 100.0
    if "usd" in text or "$" in text or "dollar" in text:
        return "usd_unscaled", value
    if "share" in text or "per diluted" in text:
        return "per_share", value
    return _unit_key(unit), value


def _sec_table_thousands_scale_allowed(cell_kind: str, object_kind: str, object_value: float) -> bool:
    return (
        cell_kind == "usd_millions"
        and object_kind in {"usd_unscaled", "unitless"}
        and abs(object_value) >= 1000.0
    )


def _compatible_unknown_units(left: str, right: str) -> bool:
    return {left, right} <= {"usd_unscaled", "usd_millions", "unitless"}


def _number_candidates(text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    pattern = re.compile(r"(?P<raw>[$(]?\s*-?\d[\d,]*(?:\.\d+)?\s*(?:%|million|billion)?\)?)", re.I)
    for match in pattern.finditer(text):
        raw_value = match.group("raw").strip()
        if _extract_year(raw_value):
            continue
        value = _to_float(raw_value)
        if value is None:
            continue
        raw_lower = raw_value.lower()
        if "%" in raw_lower:
            unit = "percent"
        elif "billion" in raw_lower:
            unit = "usd_billions"
        elif "million" in raw_lower:
            unit = "usd_millions"
        elif "$" in raw_lower:
            unit = "usd"
        else:
            unit = None
        candidates.append({"raw_value": raw_value, "value": value, "unit": unit})
    return candidates


def _cash_outflow_magnitude_allowed(cell: dict[str, Any], obj: dict[str, Any]) -> bool:
    evidence_text = " ".join(
        str(part or "")
        for part in [obj.get("metric_name"), obj.get("row_label"), obj.get("column_label"), obj.get("raw_value")]
    )
    return _cash_outflow_magnitude_allowed_for_text(cell, evidence_text, obj.get("raw_value"))


def _cash_outflow_magnitude_allowed_for_text(cell: dict[str, Any], evidence_text: str, raw_value: Any) -> bool:
    text = f"{cell.get('metric') or ''} {evidence_text}".lower()
    if "(" not in str(raw_value or ""):
        return False
    return any(term in text for term in ("capex", "capital expenditure", "property and equipment", "pp&e", "ppe"))


def _cash_outflow_magnitude_matches(
    cell_value: Any,
    cell_unit: Any,
    object_value: Any,
    object_unit: Any,
    object_raw_value: Any,
    *,
    relative_tolerance: float,
    absolute_tolerance: float,
) -> tuple[bool, bool]:
    cell_num = _to_float(cell_value)
    object_num = _to_float(object_value)
    if cell_num is None or object_num is None:
        return False, False
    cell_kind, cell_canonical = _canonical_value(cell_num, str(cell_unit or ""), "")
    object_kind, object_canonical = _canonical_value(object_num, str(object_unit or ""), str(object_raw_value or ""))
    unit_match = cell_kind == object_kind or _compatible_unknown_units(cell_kind, object_kind)
    if not unit_match:
        return False, False
    return _numbers_close(abs(cell_canonical), abs(object_canonical), relative_tolerance, absolute_tolerance), True


def _unit_key(unit: str) -> str:
    text = str(unit or "").strip().lower()
    text = re.sub(r"[^a-z0-9_%]+", "_", text).strip("_")
    return text or "unitless"


def _citation_object_ids(cell: dict[str, Any]) -> list[str]:
    ids = [str(item).strip() for item in cell.get("citation_object_ids") or [] if str(item).strip()]
    legacy = str(cell.get("citation_object_id") or "").strip()
    if legacy:
        ids.append(legacy)
    deduped = []
    for object_id in ids:
        if object_id not in deduped:
            deduped.append(object_id)
    return deduped


def _is_yoy_growth_cell(cell: dict[str, Any]) -> bool:
    text = f"{cell.get('metric') or ''} {cell.get('derivation') or ''}".lower()
    return any(term in text for term in ("yoy", "year over year", "growth")) and _unit_key(str(cell.get("unit") or "")) in {
        "percent",
        "%",
    }


def _numbers_close(left: float, right: float, relative_tolerance: float, absolute_tolerance: float) -> bool:
    return math.isclose(left, right, rel_tol=relative_tolerance, abs_tol=absolute_tolerance)


def _ticker_matches(cell_ticker: Any, obj: dict[str, Any]) -> bool:
    ticker = str(cell_ticker or "").upper().strip()
    object_ticker = str(obj.get("ticker") or "").upper().strip()
    return not ticker or not object_ticker or ticker == object_ticker


def _year_matches(cell_year: Any, object_period: Any) -> bool:
    cell = _extract_year(cell_year)
    period = _extract_year(object_period)
    return cell is not None and period is not None and cell == period


def _extract_year(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"(?:19|20)\d{2}", str(value))
    return int(match.group(0)) if match else None


def _metric_text_matches(cell_metric: Any, evidence_text: str) -> bool:
    tokens = [token for token in _tokens(str(cell_metric or "")) if token not in {"fy", "year", "metric", "value"}]
    if not tokens:
        return True
    evidence_tokens = set(_tokens(evidence_text))
    hits = sum(token in evidence_tokens for token in tokens)
    return hits / len(tokens) >= 0.4


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text.lower())


def _cell_report(
    cell: dict[str, Any],
    cell_index: int,
    *,
    issues: list[str],
    citation_valid: bool,
    ticker_match: bool,
    year_match: bool,
    value_match: bool,
    unit_match: bool,
    matched_object_type: str | None,
    matched_detail: dict[str, Any] | None,
) -> dict[str, Any]:
    status = str(cell.get("status") or "").lower()
    if status == "reported":
        valid = citation_valid and ticker_match and year_match and value_match and unit_match
    else:
        valid = value_match and not issues
    return {
        "cell_index": cell_index,
        "ticker": cell.get("ticker"),
        "fiscal_year": cell.get("fiscal_year"),
        "metric": cell.get("metric"),
        "value": cell.get("value"),
        "unit": cell.get("unit"),
        "status": status,
        "citation_object_id": cell.get("citation_object_id"),
        "citation_object_ids": _citation_object_ids(cell),
        "derivation": cell.get("derivation"),
        "citation_valid": citation_valid,
        "ticker_match": ticker_match,
        "year_match": year_match,
        "value_match": value_match,
        "unit_match": unit_match,
        "matched_object_type": matched_object_type,
        "matched_detail": matched_detail,
        "issues": sorted(set(issues)),
        "valid": valid,
    }


def _summarize(query_reports: list[dict[str, Any]]) -> dict[str, Any]:
    table_reports = [row for row in query_reports if row.get("is_table_query")]
    reported = sum(int(row.get("reported_cell_count") or 0) for row in table_reports)
    exact = sum(int(row.get("exact_cell_count") or 0) for row in table_reports)
    unit = sum(int(row.get("unit_matched_cell_count") or 0) for row in table_reports)
    valid_reported = sum(int(row.get("valid_reported_cell_count") or 0) for row in table_reports)
    issue_counts = Counter(
        failure["type"]
        for row in table_reports
        for failure in row.get("hard_failures") or []
    )
    warning_counts = Counter(
        warning["type"]
        for row in table_reports
        for warning in row.get("warnings") or []
    )
    return {
        "query_count": len(query_reports),
        "table_query_count": len(table_reports),
        "cell_json_query_count": sum(bool(row.get("cell_table_present")) for row in table_reports),
        "reported_cells": reported,
        "missing_cells": sum(int(row.get("missing_cell_count") or 0) for row in table_reports),
        "unsupported_cells": sum(int(row.get("unsupported_cell_count") or 0) for row in table_reports),
        "valid_reported_cells": valid_reported,
        "exact_cells": exact,
        "unit_matched_cells": unit,
        "invalid_cells": sum(int(row.get("invalid_cell_count") or 0) for row in table_reports),
        "source_traceability_rate": _ratio(valid_reported, reported),
        "exact_rate": _ratio(exact, reported),
        "unit_rate": _ratio(unit, reported),
        "mean_cell_json_validity": round(
            sum(float(row.get("cell_json_validity") or 0.0) for row in table_reports) / len(table_reports),
            4,
        )
        if table_reports
        else 0.0,
        "hard_failure_types": dict(sorted(issue_counts.items())),
        "warning_types": dict(sorted(warning_counts.items())),
    }


def _load_object_index(metrics_path: Path, tables_path: Path, claims_path: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for path in (metrics_path, tables_path, claims_path):
        for row in _read_jsonl(path):
            index[str(row.get("object_id"))] = row
    return index


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(max(0.0, min(1.0, float(numerator) / float(denominator))), 4)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    main()
