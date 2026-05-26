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


TICKER_NAMES = {
    "MSFT": ["microsoft", "微软", "azure"],
    "AAPL": ["apple", "苹果"],
    "NVDA": ["nvidia", "英伟达"],
    "GOOGL": ["alphabet", "google", "谷歌"],
    "META": ["meta"],
    "AMZN": ["amazon", "aws", "亚马逊"],
    "AMD": ["amd"],
    "ADBE": ["adobe"],
    "PANW": ["palo alto", "palo alto networks"],
    "SNOW": ["snowflake"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score expanded synthesis outputs with diagnostic insight/table profiles."
    )
    parser.add_argument(
        "--eval-path",
        default="eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl",
    )
    parser.add_argument(
        "--synthesis-path",
        default="reports/demo/qwen9b_expanded_v0_2_synthesis_demo.json",
    )
    parser.add_argument(
        "--citation-validation-path",
        default="reports/quality/sec_tech_10k_expanded_v0_2_citation_validation.json",
    )
    parser.add_argument(
        "--cell-validation-path",
        default="reports/quality/sec_tech_10k_expanded_v0_2_cell_vllm_metric_cell_validation.json",
    )
    parser.add_argument(
        "--output-path",
        default="reports/quality/sec_tech_10k_expanded_v0_2_answer_quality.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    eval_rows = {row["query_id"]: row for row in _read_jsonl(REPO_ROOT / args.eval_path)}
    synthesis = _read_json(REPO_ROOT / args.synthesis_path)
    validation = _read_json(REPO_ROOT / args.citation_validation_path)
    cell_validation = _read_json_if_exists(REPO_ROOT / args.cell_validation_path)
    validation_by_query = {row["query_id"]: row for row in validation.get("queries", [])}
    cell_validation_by_query = {row["query_id"]: row for row in cell_validation.get("queries", [])}

    query_scores = [
        _score_query(
            result,
            eval_rows.get(str(result.get("query_id")), {}),
            validation_by_query,
            cell_validation_by_query,
        )
        for result in synthesis.get("results", [])
    ]
    report = {
        "mode": "expanded_answer_quality_scoring",
        "schema_version": "answer_quality_scoring_v0.3",
        "status": "strict_diagnostic_not_teacher",
        "eval_path": str(REPO_ROOT / args.eval_path),
        "synthesis_path": str(REPO_ROOT / args.synthesis_path),
        "citation_validation_path": str(REPO_ROOT / args.citation_validation_path),
        "cell_validation_path": str(REPO_ROOT / args.cell_validation_path),
        "output_path": str(REPO_ROOT / args.output_path),
        "summary": _summarize(query_scores),
        "queries": query_scores,
        "limitations": [
            "This report is a strict gate report, not a teacher label source.",
            "Metric/table numeric_exactness depends on machine-readable cell-level JSON with value/unit/citation per cell.",
            "Lexical facet checks are only coverage alarms; they cannot prove financial correctness.",
            "Teacher-ready status requires parse validity, citation pass, no hard citation failures, no numeric blocker, and high coverage.",
        ],
    }
    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _score_query(
    result: dict[str, Any],
    eval_row: dict[str, Any],
    validation_by_query: dict[str, dict[str, Any]],
    cell_validation_by_query: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    profile = eval_row.get("scoring_profile") or result.get("mode") or "unknown"
    text = _answer_text(result)
    validation = validation_by_query.get(str(result.get("query_id")), {})
    cell_validation = cell_validation_by_query.get(str(result.get("query_id")), {})
    base = {
        "query_id": result.get("query_id"),
        "profile": profile,
        "parse_status": result.get("parse_status"),
        "model_quality": result.get("synthesis", {}).get("conclusion_quality"),
        "citation_status": validation.get("status"),
        "hard_failure_count": validation.get("hard_failure_count", 0),
        "warning_count": validation.get("warning_count", 0),
    }
    if profile == "metric_table_stability":
        scores = _score_metric_table(result, eval_row, validation, cell_validation, text)
    else:
        scores = _score_insight(result, eval_row, validation, text)
    overall = _overall(scores, validation, result)
    blockers = _blocking_issues(scores, validation, result, eval_row)
    return {
        **base,
        "scores": scores,
        "overall": overall,
        "teacher_ready": not blockers and overall >= 0.85,
        "blocking_issues": blockers,
        "notes": _notes(result, eval_row, validation, cell_validation),
    }


def _score_insight(
    result: dict[str, Any],
    eval_row: dict[str, Any],
    validation: dict[str, Any],
    text: str,
) -> dict[str, float]:
    ideal_facets = [str(item) for item in eval_row.get("ideal_facets") or []]
    tickers = [str(item).upper() for item in eval_row.get("tickers") or []]
    years = [str(item) for item in eval_row.get("fiscal_years") or []]
    synthesis = result.get("synthesis", {}) or {}
    key_findings = synthesis.get("key_findings") or []
    facet_findings = synthesis.get("facet_findings") or []
    decision_drivers = synthesis.get("decision_drivers") or []
    secondary_context = synthesis.get("secondary_context") or []
    limiting_caveats = synthesis.get("limiting_caveats") or []
    numeric_claims = synthesis.get("numeric_claims") or []
    claim_records = _claim_records(synthesis)
    cited_findings = sum(bool(item.get("cited_object_ids")) for item in claim_records)
    missing_count = int(result.get("package_metrics", {}).get("missing_aspect_count") or 0)
    aspect_count = int(result.get("package_metrics", {}).get("aspect_count") or 0)
    citation_count = int(result.get("package_metrics", {}).get("citation_evidence_count") or 0)
    model_missing = int(result.get("output_metrics", {}).get("model_missing_or_uncertain_count") or 0)
    cited_citations = int(result.get("output_metrics", {}).get("cited_citation_object_count") or 0)
    return {
        "format_validity": 1.0 if result.get("parse_status") == "parsed" else 0.0,
        "facet_coverage": _coverage(ideal_facets, text),
        "company_year_coverage": _company_year_coverage(tickers, years, text),
        "input_evidence_completeness": _ratio(citation_count, aspect_count),
        "evidence_grounding": _ratio(cited_findings, len(claim_records)),
        "decision_priority_discipline": _decision_priority_discipline(synthesis),
        "numeric_claim_discipline": _numeric_claim_discipline(validation, numeric_claims),
        "citation_use_rate": _ratio(cited_citations, citation_count),
        "counter_evidence_use": _keyword_score(text, ["risk", "风险", "cost", "成本", "capex", "资本开支", "caveat", "不确定", "不可比", "margin", "利润率"]),
        "comparability_discipline": _keyword_score(text, ["不可比", "口径", "segment", "披露", "definition", "定义"]),
        "missing_calibration": 1.0 if missing_count == 0 or model_missing > 0 else 0.0,
        "citation_validity": 1.0 if validation.get("status") == "pass" else 0.0,
        "synthesis_quality": {"good": 1.0, "mixed": 0.6, "weak": 0.25}.get(
            result.get("synthesis", {}).get("conclusion_quality"), 0.0
        ),
    }


def _score_metric_table(
    result: dict[str, Any],
    eval_row: dict[str, Any],
    validation: dict[str, Any],
    cell_validation: dict[str, Any],
    text: str,
) -> dict[str, float | None]:
    table_requirements = eval_row.get("table_requirements") or {}
    requested_columns = [str(item) for item in table_requirements.get("columns") or []]
    requested_rows = [str(item) for item in table_requirements.get("rows") or []]
    package = result.get("package_metrics", {})
    output = result.get("output_metrics", {})
    aspect_count = int(package.get("aspect_count") or 0)
    available_or_missing = int(package.get("citation_evidence_count") or 0) + int(package.get("missing_aspect_count") or 0)
    model_missing = int(output.get("model_missing_or_uncertain_count") or 0)
    cited_objects = int(output.get("cited_object_count") or 0)
    cited_citations = int(output.get("cited_citation_object_count") or 0)
    citation_count = int(package.get("citation_evidence_count") or 0)
    has_cell_validation = bool(cell_validation)
    source_traceability = (
        float(cell_validation.get("source_traceability_rate") or 0.0)
        if has_cell_validation
        else _ratio(cited_objects, max(len(result.get("synthesis", {}).get("key_findings") or []), 1))
    )
    return {
        "format_validity": 1.0 if result.get("parse_status") == "parsed" else 0.0,
        "requested_cell_coverage_proxy": _ratio(available_or_missing, aspect_count),
        "table_shape_coverage": (_coverage(requested_rows, text) + _coverage(requested_columns, text)) / 2.0
        if requested_columns or requested_rows
        else 0.0,
        "source_traceability": source_traceability,
        "citation_use_rate": _ratio(cited_citations, citation_count),
        "na_handling": 1.0 if int(package.get("missing_aspect_count") or 0) == 0 or model_missing > 0 else 0.0,
        "citation_validity": 1.0 if validation.get("status") == "pass" else 0.0,
        "numeric_exactness": float(cell_validation.get("reported_cell_exact_rate") or 0.0) if has_cell_validation else 0.0,
        "unit_scale_correctness": float(cell_validation.get("unit_match_rate") or 0.0) if has_cell_validation else 0.0,
        "cell_json_validity": float(cell_validation.get("cell_json_validity") or 0.0) if has_cell_validation else 0.0,
        "synthesis_quality": {"good": 1.0, "mixed": 0.6, "weak": 0.25}.get(
            result.get("synthesis", {}).get("conclusion_quality"), 0.0
        ),
    }


def _overall(scores: dict[str, float | None], validation: dict[str, Any], result: dict[str, Any]) -> float:
    numeric = [float(value) for value in scores.values() if isinstance(value, (int, float))]
    score = sum(numeric) / len(numeric) if numeric else 0.0
    warning_count = int(validation.get("warning_count") or 0)
    hard_failure_count = int(validation.get("hard_failure_count") or 0)
    score = max(0.0, score - 0.04 * warning_count - 0.12 * hard_failure_count)
    if result.get("parse_status") != "parsed":
        score = min(score, 0.25)
    if validation.get("status") == "repair_required":
        score = min(score * 0.75, 0.55)
    if scores.get("numeric_exactness") == 0.0 or scores.get("cell_json_validity") == 0.0:
        score = min(score, 0.55)
    return round(max(0.0, min(1.0, score)), 4)


def _blocking_issues(
    scores: dict[str, float | None],
    validation: dict[str, Any],
    result: dict[str, Any],
    eval_row: dict[str, Any],
) -> list[str]:
    blockers = []
    if result.get("parse_status") != "parsed":
        blockers.append("invalid_or_repaired_json")
    if validation.get("status") != "pass":
        blockers.append("citation_validation_not_pass")
    if int(validation.get("hard_failure_count") or 0) > 0:
        blockers.append("hard_citation_failure")
    if int(validation.get("warning_count") or 0) > 0:
        blockers.append("citation_or_number_warning")
    if _score_value(scores, "facet_coverage", _score_value(scores, "table_shape_coverage", 0.0)) < 0.7:
        blockers.append("low_required_coverage")
    if _score_value(scores, "decision_priority_discipline", 1.0) < 0.8:
        blockers.append("weak_decision_priority")
    if _score_value(scores, "numeric_claim_discipline", 1.0) < 0.7:
        blockers.append("numeric_claim_discipline_warning")
    if eval_row.get("scoring_profile") == "metric_table_stability":
        cell_json_score = float(scores.get("cell_json_validity") or 0.0)
        numeric_score = float(scores.get("numeric_exactness") or 0.0)
        unit_score = float(scores.get("unit_scale_correctness") or 0.0)
        if cell_json_score <= 0.0:
            blockers.append("missing_machine_readable_cell_json")
        elif cell_json_score < 0.9:
            blockers.append("cell_json_validation_failed")
        if numeric_score < 0.95:
            blockers.append("numeric_validation_failed")
        if unit_score < 0.95:
            blockers.append("unit_scale_validation_failed")
    if _score_value(scores, "citation_use_rate", 0.0) < 0.5:
        blockers.append("low_citation_use_rate")
    return blockers


def _score_value(scores: dict[str, float | None], key: str, default: float) -> float:
    value = scores.get(key)
    return default if value is None else float(value)


def _notes(
    result: dict[str, Any],
    eval_row: dict[str, Any],
    validation: dict[str, Any],
    cell_validation: dict[str, Any],
) -> list[str]:
    notes = []
    if result.get("parse_status") != "parsed":
        notes.append("format repair required before final scoring")
    if validation.get("status") == "repair_required":
        notes.append("citation validator requires repair")
    if eval_row.get("scoring_profile") == "metric_table_stability":
        if not cell_validation:
            notes.append("numeric exactness requires metric-table cell validation output")
        elif not cell_validation.get("cell_table_present"):
            notes.append("metric/table query did not emit cell_table")
        elif int(cell_validation.get("invalid_cell_count") or 0) > 0:
            notes.append("metric/table cell validator found invalid cells")
    return notes


def _answer_text(result: dict[str, Any]) -> str:
    synthesis = result.get("synthesis") or {}
    parts = [str(synthesis.get("answer_zh") or ""), str(synthesis.get("thesis_zh") or "")]
    for finding in synthesis.get("decision_drivers") or []:
        parts.append(str(finding.get("driver_zh") or ""))
        parts.append(str(finding.get("decision_impact_zh") or ""))
    for finding in synthesis.get("secondary_context") or []:
        parts.append(str(finding.get("context_zh") or ""))
        parts.append(str(finding.get("why_secondary_zh") or ""))
    for finding in synthesis.get("limiting_caveats") or []:
        parts.append(str(finding.get("caveat_zh") or ""))
        parts.append(str(finding.get("impact_on_thesis_zh") or ""))
    for finding in synthesis.get("key_findings") or []:
        parts.append(str(finding.get("claim_zh") or ""))
    for finding in synthesis.get("facet_findings") or []:
        parts.append(str(finding.get("facet_zh") or ""))
        parts.append(str(finding.get("coverage_status") or ""))
        parts.append(str(finding.get("takeaway_zh") or ""))
    parts.extend(str(item) for item in synthesis.get("comparability_caveats_zh") or [])
    for item in synthesis.get("missing_evidence_by_facet") or []:
        parts.append(str(item.get("facet_zh") or ""))
        parts.append(str(item.get("missing_or_uncertain_zh") or ""))
    parts.extend(str(item) for item in synthesis.get("missing_or_uncertain_zh") or [])
    for item in synthesis.get("numeric_claims") or []:
        parts.append(str(item.get("metric_label_zh") or ""))
        parts.append(str(item.get("raw_value_text") or ""))
        parts.append(str(item.get("display_value_zh") or ""))
        parts.append(str(item.get("metric_role") or ""))
        parts.append(str(item.get("role_check_zh") or ""))
    parts.append(str(synthesis.get("evidence_use_notes_zh") or ""))
    return "\n".join(parts).lower()


def _claim_records(synthesis: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for section in ("decision_drivers", "secondary_context", "limiting_caveats", "key_findings", "facet_findings"):
        records.extend(synthesis.get(section) or [])
    return records


def _decision_priority_discipline(synthesis: dict[str, Any]) -> float:
    thesis = str(synthesis.get("thesis_zh") or "").strip()
    drivers = synthesis.get("decision_drivers") or []
    secondary = synthesis.get("secondary_context") or []
    score = 0.0
    if thesis:
        score += 0.35
    if 1 <= len(drivers) <= 3:
        score += 0.3
    ranks = [item.get("rank") for item in drivers]
    if ranks and ranks == sorted(ranks) and len(set(ranks)) == len(ranks):
        score += 0.2
    if len(secondary) <= 3:
        score += 0.15
    return round(min(1.0, score), 4)


def _numeric_claim_discipline(validation: dict[str, Any], numeric_claims: list[dict[str, Any]]) -> float:
    numeric_warning_count = sum(
        1
        for warning in validation.get("warnings") or []
        if str(warning.get("type") or "").startswith(("number_", "numeric_", "metric_role_"))
    )
    if not numeric_claims and numeric_warning_count:
        return 0.0
    denominator = max(len(numeric_claims), 1)
    return round(max(0.0, 1.0 - min(1.0, numeric_warning_count / denominator)), 4)


def _coverage(items: list[str], text: str) -> float:
    if not items:
        return 0.0
    hits = sum(_item_hit(item, text) for item in items)
    return round(hits / len(items), 4)


def _item_hit(item: str, text: str) -> bool:
    item_text = item.lower()
    if item_text in text:
        return True
    tokens = [token for token in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", item_text) if len(token) > 1]
    if not tokens:
        return False
    hits = sum(token in text for token in tokens)
    return hits / len(tokens) >= 0.5


def _company_year_coverage(tickers: list[str], years: list[str], text: str) -> float:
    if not tickers and not years:
        return 0.0
    ticker_hits = []
    for ticker in tickers:
        aliases = [ticker.lower(), *TICKER_NAMES.get(ticker, [])]
        ticker_hits.append(any(alias.lower() in text for alias in aliases))
    year_hits = [year in text for year in years]
    return _ratio(sum(ticker_hits) + sum(year_hits), len(ticker_hits) + len(year_hits))


def _keyword_score(text: str, keywords: list[str]) -> float:
    return 1.0 if any(keyword.lower() in text for keyword in keywords) else 0.0


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(max(0.0, min(1.0, float(numerator) / float(denominator))), 4)


def _summarize(query_scores: list[dict[str, Any]]) -> dict[str, Any]:
    profile_counts = Counter(row.get("profile") for row in query_scores)
    parse_counts = Counter(row.get("parse_status") for row in query_scores)
    citation_counts = Counter(row.get("citation_status") for row in query_scores)
    overall_values = [float(row.get("overall") or 0.0) for row in query_scores]
    blocker_counts = Counter(
        issue
        for row in query_scores
        for issue in row.get("blocking_issues") or []
    )
    return {
        "query_count": len(query_scores),
        "profile_counts": dict(sorted(profile_counts.items())),
        "parse_status_counts": dict(sorted(parse_counts.items())),
        "citation_status_counts": dict(sorted(citation_counts.items())),
        "teacher_ready_count": sum(bool(row.get("teacher_ready")) for row in query_scores),
        "blocking_issue_counts": dict(sorted(blocker_counts.items())),
        "mean_overall": round(sum(overall_values) / len(overall_values), 4) if overall_values else 0.0,
        "min_overall": round(min(overall_values), 4) if overall_values else 0.0,
        "max_overall": round(max(overall_values), 4) if overall_values else 0.0,
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json(path)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    main()
