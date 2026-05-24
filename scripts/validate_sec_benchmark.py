from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


REQUIRED_FIELDS = {
    "schema_version",
    "benchmark_version",
    "case_id",
    "case_group",
    "level",
    "companies",
    "years",
    "filing_types",
    "task_type",
    "prompt",
    "allowed_sources",
    "source_policy",
    "evaluation_modes",
    "expected_sections",
    "gold_points",
    "numeric_checks",
    "hard_gates",
    "hallucination_traps",
    "failure_types",
    "score_weights",
    "gold_context_status",
}

ALLOWED_LEVELS = {"L1", "L2", "L3", "L4", "L5"}
ALLOWED_CASE_GROUPS = {"formal_seed", "project_regression", "diagnostic_stress"}
ALLOWED_MODES = {"gold_context", "pipeline_context"}
ALLOWED_SOURCES = {"SEC"}
EXPECTED_SCORE_KEYS = {"retrieval", "factuality", "coverage", "synthesis", "citation"}
DEFAULT_CANONICAL_COMPANIES = {
    "NVDA",
    "AMD",
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "META",
    "ADBE",
    "SNOW",
    "PANW",
}

SECTION_ALIASES = {
    "item 1 business": ["item 1 business"],
    "item 1a risk factors": ["item 1a risk factors"],
    "item 7 managements discussion and analysis": ["item 7 managements discussion", "item 7 md a"],
    "item 8 financial statements": ["item 8 financial statements", "item 8"],
    "financial statements": ["item 8 financial statements", "item 8"],
    "segment information": ["item 8 financial statements", "item 8", "item 7 managements discussion"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate SEC benchmark v1 readiness.")
    parser.add_argument("--cases-path", default="eval/sec_cases/test_cases_v1.jsonl")
    parser.add_argument("--manifest-path", default="data/processed_private/manifests/sec_tech_10k_manifest.jsonl")
    parser.add_argument("--evidence-path", default="data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl")
    parser.add_argument(
        "--metrics-path",
        default="data/processed_private/structured_objects/sec_tech_10k_metrics.jsonl",
    )
    parser.add_argument("--gold-context-dir", default="eval/sec_cases/gold_context")
    parser.add_argument("--output-path", default="reports/quality/sec_benchmark_v1_step1_readiness.json")
    parser.add_argument("--run-bm25-smoke", action="store_true")
    parser.add_argument("--bm25-index-dir", default="data/indexes/bm25/sec_tech_10k")
    parser.add_argument("--object-bm25-index-dir", default="data/indexes/bm25/sec_tech_10k_objects")
    parser.add_argument("--bm25-top-k", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = _read_jsonl(REPO_ROOT / args.cases_path)
    manifest_rows = _read_jsonl(REPO_ROOT / args.manifest_path)
    evidence_rows = _read_jsonl(REPO_ROOT / args.evidence_path)
    metric_rows = _read_jsonl(REPO_ROOT / args.metrics_path)
    canonical_companies = _load_canonical_companies()

    manifest_index = {
        (str(row.get("ticker")).upper(), int(row.get("fiscal_year")), str(row.get("form_type")).upper())
        for row in manifest_rows
    }
    evidence_index = _index_evidence(evidence_rows)
    metric_index = _index_metrics(metric_rows)
    seen_ids: set[str] = set()
    results = []

    bm25_retriever = None
    object_retriever = None
    bm25_error = None
    if args.run_bm25_smoke:
        try:
            from retrieval.bm25_retriever import BM25Retriever
            from retrieval.object_bm25_retriever import ObjectBM25Retriever

            bm25_retriever = BM25Retriever(REPO_ROOT / args.bm25_index_dir)
            object_retriever = ObjectBM25Retriever(REPO_ROOT / args.object_bm25_index_dir)
        except Exception as exc:  # pragma: no cover - diagnostic path
            bm25_error = repr(exc)

    for case in cases:
        result = _validate_case_schema(case, seen_ids, canonical_companies)
        case_id = str(case.get("case_id") or "")
        companies = [str(item).upper() for item in case.get("companies") or []]
        years = [int(item) for item in case.get("years") or [] if _is_int_like(item)]
        filing_types = [str(item).upper() for item in case.get("filing_types") or []]

        source_failures = _check_source_availability(companies, years, filing_types, manifest_index)
        section_warnings, section_summary = _check_section_coverage(case, evidence_index)
        metric_warnings, metric_summary = _check_metric_readiness(case, metric_index)
        gold_warnings = _check_gold_context(case, REPO_ROOT / args.gold_context_dir)
        result["hard_failures"].extend(source_failures)
        result["warnings"].extend(section_warnings)
        result["warnings"].extend(metric_warnings)
        result["warnings"].extend(gold_warnings)
        result["source_summary"] = {
            "required_filings": len(companies) * len(years) * len(filing_types),
            "missing_filings": len(source_failures),
        }
        result["section_summary"] = section_summary
        result["metric_summary"] = metric_summary

        if args.run_bm25_smoke:
            if bm25_error:
                result["warnings"].append({"type": "bm25_smoke_unavailable", "error": bm25_error})
            else:
                bm25_summary, bm25_warnings = _run_bm25_smoke(
                    case,
                    bm25_retriever,
                    object_retriever,
                    top_k=args.bm25_top_k,
                )
                result["bm25_smoke"] = bm25_summary
                result["warnings"].extend(bm25_warnings)

        result["hard_failure_count"] = len(result["hard_failures"])
        result["warning_count"] = len(result["warnings"])
        result["status"] = "pass" if not result["hard_failures"] else "fail"
        results.append(result)

    failure_types = Counter(
        failure.get("type") for result in results for failure in result.get("hard_failures") or []
    )
    warning_types = Counter(warning.get("type") for result in results for warning in result.get("warnings") or [])
    group_counts = Counter(str(case.get("case_group")) for case in cases)
    level_counts = Counter(str(case.get("level")) for case in cases)
    report = {
        "schema_version": "sec_benchmark_readiness_v0.1",
        "cases_path": str((REPO_ROOT / args.cases_path).resolve()),
        "manifest_path": str((REPO_ROOT / args.manifest_path).resolve()),
        "evidence_path": str((REPO_ROOT / args.evidence_path).resolve()),
        "metrics_path": str((REPO_ROOT / args.metrics_path).resolve()),
        "run_bm25_smoke": bool(args.run_bm25_smoke),
        "summary": {
            "case_count": len(cases),
            "pass_count": sum(result["status"] == "pass" for result in results),
            "fail_count": sum(result["status"] == "fail" for result in results),
            "hard_failure_types": dict(sorted(failure_types.items())),
            "warning_types": dict(sorted(warning_types.items())),
            "case_group_counts": dict(sorted(group_counts.items())),
            "level_counts": dict(sorted(level_counts.items())),
            "gold_context_needed_count": sum(
                str(case.get("gold_context_status")) == "needs_annotation" for case in cases
            ),
        },
        "results": results,
    }
    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "case_count": report["summary"]["case_count"],
                "pass_count": report["summary"]["pass_count"],
                "fail_count": report["summary"]["fail_count"],
                "hard_failure_types": report["summary"]["hard_failure_types"],
                "warning_types": report["summary"]["warning_types"],
                "output_path": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _validate_case_schema(
    case: dict[str, Any],
    seen_ids: set[str],
    canonical_companies: set[str],
) -> dict[str, Any]:
    case_id = str(case.get("case_id") or "")
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    missing = sorted(REQUIRED_FIELDS - set(case))
    for field in missing:
        failures.append({"type": "missing_required_field", "field": field})
    if not case_id:
        failures.append({"type": "missing_case_id"})
    elif case_id in seen_ids:
        failures.append({"type": "duplicate_case_id", "case_id": case_id})
    else:
        seen_ids.add(case_id)
    if case.get("schema_version") != "sec_eval_case_v1":
        failures.append({"type": "invalid_schema_version", "value": case.get("schema_version")})
    if case.get("benchmark_version") != "sec_benchmark_v1":
        failures.append({"type": "invalid_benchmark_version", "value": case.get("benchmark_version")})
    if case.get("case_group") not in ALLOWED_CASE_GROUPS:
        failures.append({"type": "invalid_case_group", "value": case.get("case_group")})
    if case.get("level") not in ALLOWED_LEVELS:
        failures.append({"type": "invalid_level", "value": case.get("level")})
    companies = {str(item).upper() for item in case.get("companies") or []}
    invalid_companies = sorted(companies - canonical_companies)
    if not companies:
        failures.append({"type": "missing_companies"})
    if invalid_companies:
        failures.append({"type": "invalid_company", "values": invalid_companies})
    if not case.get("years"):
        failures.append({"type": "missing_years"})
    if not case.get("filing_types"):
        failures.append({"type": "missing_filing_types"})
    if set(case.get("allowed_sources") or []) - ALLOWED_SOURCES:
        failures.append({"type": "invalid_allowed_source", "values": case.get("allowed_sources")})
    if case.get("source_policy") != "SEC_ONLY":
        failures.append({"type": "invalid_source_policy", "value": case.get("source_policy")})
    modes = {str(item) for item in case.get("evaluation_modes") or []}
    if not modes:
        failures.append({"type": "missing_evaluation_modes"})
    if modes - ALLOWED_MODES:
        failures.append({"type": "invalid_evaluation_mode", "values": sorted(modes - ALLOWED_MODES)})
    if not str(case.get("prompt") or "").strip():
        failures.append({"type": "missing_prompt"})
    if not case.get("gold_points"):
        failures.append({"type": "missing_gold_points"})
    weights = case.get("score_weights") or {}
    if set(weights) != EXPECTED_SCORE_KEYS:
        failures.append({"type": "invalid_score_weight_keys", "keys": sorted(weights)})
    if sum(float(value) for value in weights.values() if _is_number(value)) != 10:
        failures.append({"type": "score_weight_sum_not_10", "score_weights": weights})
    if len(str(case.get("prompt") or "")) < 30:
        warnings.append({"type": "short_prompt"})
    return {
        "case_id": case_id,
        "case_group": case.get("case_group"),
        "level": case.get("level"),
        "task_type": case.get("task_type"),
        "hard_failures": failures,
        "warnings": warnings,
    }


def _load_canonical_companies() -> set[str]:
    config_path = REPO_ROOT / "configs" / "sec_tech_universe.yaml"
    if not config_path.exists():
        return set(DEFAULT_CANONICAL_COMPANIES)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    companies = {
        str(company.get("ticker") or "").upper()
        for company in config.get("companies") or []
        if isinstance(company, dict) and company.get("ticker")
    }
    return companies or set(DEFAULT_CANONICAL_COMPANIES)


def _check_source_availability(
    companies: list[str],
    years: list[int],
    filing_types: list[str],
    manifest_index: set[tuple[str, int, str]],
) -> list[dict[str, Any]]:
    failures = []
    for company in companies:
        for year in years:
            for filing_type in filing_types:
                if (company, year, filing_type) not in manifest_index:
                    failures.append(
                        {
                            "type": "missing_filing",
                            "ticker": company,
                            "year": year,
                            "filing_type": filing_type,
                        }
                    )
    return failures


def _check_section_coverage(
    case: dict[str, Any],
    evidence_index: dict[tuple[str, int], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    warnings = []
    expected_sections = [str(item) for item in case.get("expected_sections") or []]
    companies = [str(item).upper() for item in case.get("companies") or []]
    years = [int(item) for item in case.get("years") or [] if _is_int_like(item)]
    summary: dict[str, Any] = {"expected_sections": expected_sections, "coverage": []}
    if not expected_sections:
        return warnings, summary
    for company in companies:
        for year in years:
            rows = evidence_index.get((company, year), [])
            sections = {str(row.get("section") or "") for row in rows}
            missing_sections = [
                expected for expected in expected_sections if not _has_section_match(expected, sections)
            ]
            summary["coverage"].append(
                {
                    "ticker": company,
                    "year": year,
                    "evidence_count": len(rows),
                    "section_count": len(sections),
                    "missing_expected_sections": missing_sections,
                }
            )
            if not rows:
                warnings.append({"type": "no_evidence_for_company_year", "ticker": company, "year": year})
            for expected in missing_sections:
                warnings.append(
                    {
                        "type": "expected_section_not_seen_in_evidence",
                        "ticker": company,
                        "year": year,
                        "section": expected,
                    }
                )
    return warnings, summary


def _check_metric_readiness(
    case: dict[str, Any],
    metric_index: dict[tuple[str, int], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    warnings = []
    checks = case.get("numeric_checks") or []
    summary: dict[str, Any] = {"numeric_check_count": len(checks), "checks": []}
    for check in checks:
        metric = str(check.get("metric") or "")
        terms = _metric_terms(metric)
        companies = [str(item).upper() for item in check.get("companies") or case.get("companies") or []]
        years = [int(item) for item in check.get("years") or case.get("years") or [] if _is_int_like(item)]
        check_summary = {"metric": metric, "terms": terms, "coverage": []}
        for company in companies:
            for year in years:
                rows = metric_index.get((company, year), [])
                hits = [_metric_row_matches(row, terms) for row in rows]
                hit_count = sum(1 for hit in hits if hit)
                check_summary["coverage"].append(
                    {"ticker": company, "year": year, "metric_object_hits": hit_count}
                )
                if hit_count == 0:
                    warnings.append(
                        {
                            "type": "numeric_check_no_structured_metric_hit",
                            "metric": metric,
                            "ticker": company,
                            "year": year,
                        }
                    )
        summary["checks"].append(check_summary)
    return warnings, summary


def _check_gold_context(case: dict[str, Any], gold_dir: Path) -> list[dict[str, Any]]:
    case_id = str(case.get("case_id") or "")
    if str(case.get("gold_context_status")) != "needs_annotation":
        return []
    candidate = gold_dir / f"{case_id}.jsonl"
    if candidate.exists():
        return []
    return [{"type": "gold_context_missing", "case_id": case_id, "expected_path": str(candidate)}]


def _run_bm25_smoke(
    case: dict[str, Any],
    bm25_retriever: Any,
    object_retriever: Any,
    top_k: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    warnings = []
    prompt = str(case.get("prompt") or "")
    companies = [str(item).upper() for item in case.get("companies") or []]
    years = [int(item) for item in case.get("years") or [] if _is_int_like(item)]
    task_type = str(case.get("task_type") or "")
    evidence_runs = []
    if "anti_hallucination" not in task_type:
        for company in companies:
            for year in years:
                hits = bm25_retriever.search(prompt, top_k=top_k, filters={"ticker": company, "fiscal_year": year})
                compact_hits = [
                    {
                        "rank": hit.get("rank"),
                        "evidence_id": hit.get("evidence_id"),
                        "score": round(float(hit.get("score") or 0.0), 4),
                        "section": hit.get("section"),
                    }
                    for hit in hits[:3]
                ]
                evidence_runs.append({"ticker": company, "year": year, "top_hits": compact_hits})
                if not hits:
                    warnings.append({"type": "bm25_no_evidence_hit", "ticker": company, "year": year})
    object_runs = []
    for check in case.get("numeric_checks") or []:
        metric = str(check.get("metric") or "")
        companies_for_check = [str(item).upper() for item in check.get("companies") or companies]
        years_for_check = [int(item) for item in check.get("years") or years if _is_int_like(item)]
        for company in companies_for_check:
            for year in years_for_check:
                hits = object_retriever.search(
                    metric,
                    top_k=top_k,
                    filters={"ticker": [company], "fiscal_year": year, "object_type": ["metric", "table"]},
                )
                compact_hits = [
                    {
                        "rank": hit.get("rank"),
                        "object_id": hit.get("object_id"),
                        "object_type": hit.get("object_type"),
                        "score": round(float(hit.get("score") or 0.0), 4),
                        "section": hit.get("section"),
                    }
                    for hit in hits[:3]
                ]
                object_runs.append(
                    {"metric": metric, "ticker": company, "year": year, "top_hits": compact_hits}
                )
                if not hits:
                    warnings.append(
                        {
                            "type": "bm25_no_structured_object_hit",
                            "metric": metric,
                            "ticker": company,
                            "year": year,
                        }
                    )
    return {"evidence_runs": evidence_runs, "object_runs": object_runs}, warnings


def _index_evidence(rows: list[dict[str, Any]]) -> dict[tuple[str, int], list[dict[str, Any]]]:
    index: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        try:
            key = (str(row.get("ticker")).upper(), int(row.get("fiscal_year")))
        except (TypeError, ValueError):
            continue
        index[key].append(row)
    return index


def _index_metrics(rows: list[dict[str, Any]]) -> dict[tuple[str, int], list[dict[str, Any]]]:
    index: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        try:
            key = (str(row.get("ticker")).upper(), int(row.get("fiscal_year")))
        except (TypeError, ValueError):
            continue
        index[key].append(row)
    return index


def _metric_row_matches(row: dict[str, Any], terms: list[str]) -> bool:
    if not terms:
        return False
    haystack = " ".join(
        str(row.get(key) or "")
        for key in ("metric_name", "raw_value", "period", "segment", "row_label", "column_label", "context")
    ).lower()
    entity_or_scope_terms = {
        "aws",
        "google",
        "cloud",
        "apple",
        "services",
        "microsoft",
        "adobe",
        "palo",
        "alto",
        "networks",
        "company",
        "total",
    }
    core_terms = [term for term in terms if term not in entity_or_scope_terms]
    if not core_terms:
        core_terms = terms
    # This is a readiness check, not the final numeric validator. A single core
    # metric token is enough to prove structured objects exist for later
    # retrieval/ledger gates.
    return any(term in haystack for term in core_terms)


def _metric_terms(metric: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9]+", metric.lower())
    stop = {"and", "or", "the", "where", "disclosed", "related"}
    aliases = {
        "aws": ["aws"],
        "rpo": ["rpo", "remaining", "performance", "obligations"],
        "cfo": ["operating", "cash"],
    }
    terms: list[str] = []
    for word in words:
        if word in stop:
            continue
        if word in aliases:
            for alias in aliases[word]:
                if alias not in terms:
                    terms.append(alias)
        elif word not in terms:
            terms.append(word)
    return terms[:6]


def _has_section_match(expected: str, actual_sections: set[str]) -> bool:
    expected_norm = _normalize_section(expected)
    aliases = SECTION_ALIASES.get(expected_norm, [expected_norm])
    actual_norms = {_normalize_section(section) for section in actual_sections}
    return any(any(alias in actual for actual in actual_norms) for alias in aliases)


def _normalize_section(text: str) -> str:
    text = text.lower().replace("&", "and")
    text = text.replace("mda", "managements discussion and analysis")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
    return rows


def _is_int_like(value: Any) -> bool:
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    main()
