from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


TICKER_ALIASES = {
    "MSFT": ("microsoft", "azure", "microsoft cloud"),
    "AAPL": ("apple", "services"),
    "NVDA": ("nvidia",),
    "GOOGL": ("alphabet", "google", "google cloud", "google advertising"),
    "META": ("meta", "facebook", "family of apps", "reality labs"),
    "AMZN": ("amazon", "aws"),
    "AMD": ("amd",),
    "ADBE": ("adobe",),
    "PANW": ("palo alto", "palo alto networks", "panw"),
    "SNOW": ("snowflake",),
}

CELL_METRIC_TERMS = (
    "revenue",
    "sales",
    "income",
    "margin",
    "profit",
    "expense",
    "cost",
    "cash flow",
    "capex",
    "capital expenditure",
    "property and equipment",
    "purchases of property",
    "headcount",
    "employee",
    "depreciation",
    "arr",
    "rpo",
    "billings",
    "deferred revenue",
    "customer",
    "net revenue retention",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert expanded multi-company/multi-year eval queries into object retrieval tasks."
    )
    parser.add_argument(
        "--eval-path",
        default="eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl",
    )
    parser.add_argument(
        "--output-path",
        default="eval_sets/sec_tech_10k_expanded_eval_v0_2_object_tasks.jsonl",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = list(_read_jsonl(REPO_ROOT / args.eval_path))
    output_rows = [_convert_query(row) for row in rows]

    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in output_rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")

    report = {
        "mode": "expanded_eval_object_task_build",
        "schema_version": "expanded_object_tasks_v0.1",
        "eval_path": str(REPO_ROOT / args.eval_path),
        "output_path": str(output_path),
        "queries": len(output_rows),
        "facets": sum(len(row.get("object_evidence_needs", [])) for row in output_rows),
        "cohort_counts": _counts(row.get("cohort") for row in output_rows),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _convert_query(row: dict[str, Any]) -> dict[str, Any]:
    tickers = [str(item).upper() for item in row.get("tickers") or []]
    fiscal_years = [int(item) for item in row.get("fiscal_years") or []]
    object_needs = _object_needs(row)

    return {
        "schema_version": "expanded_object_tasks_v0.1",
        "label_status": "unlabeled_expanded_eval_retrieval_task",
        "query_id": row.get("query_id"),
        "cohort": row.get("cohort"),
        "mode": row.get("mode"),
        "difficulty": row.get("difficulty"),
        "scoring_profile": row.get("scoring_profile"),
        "query": row.get("query_zh") or row.get("query_en"),
        "query_en": row.get("query_en"),
        "query_zh": row.get("query_zh"),
        "ticker": tickers,
        "tickers": tickers,
        "fiscal_year": fiscal_years,
        "fiscal_years": fiscal_years,
        "ideal_facets": row.get("ideal_facets") or [],
        "object_evidence_needs": object_needs,
        "rough_baseline_points": row.get("rough_baseline_points") or [],
        "required_caveats": row.get("required_caveats") or [],
        "common_failure_modes": row.get("common_failure_modes") or [],
        "table_requirements": row.get("table_requirements") or None,
        "evaluation_intent": row.get("evaluation_intent"),
    }


def _object_needs(row: dict[str, Any]) -> list[dict[str, Any]]:
    tickers = [str(item).upper() for item in row.get("tickers") or []]
    fiscal_years = [int(item) for item in row.get("fiscal_years") or []]
    explicit_needs = row.get("evidence_needs") or []
    if explicit_needs:
        needs = []
        for index, need in enumerate(explicit_needs, start=1):
            facet = str(need.get("facet") or f"facet_{index:02d}")
            must_find = [str(item) for item in need.get("must_find") or [] if str(item).strip()]
            expanded = _expand_must_find_aspects(
                must_find,
                tickers=tickers,
                fiscal_years=fiscal_years,
            )
            needs.extend(
                _need_row(
                    facet=_aspect_facet_name(facet, aspect, aspect_index, len(expanded)),
                    must_find=[aspect],
                    parent_facet=facet,
                    aspect_label=aspect,
                )
                for aspect_index, aspect in enumerate(expanded, start=1)
            )
        return needs

    table_requirements = row.get("table_requirements") or {}
    columns = [str(item) for item in table_requirements.get("columns") or [] if str(item).strip()]
    table_rows = [str(item) for item in table_requirements.get("rows") or [] if str(item).strip()]
    if columns:
        needs = []
        for column_index, column in enumerate(columns, start=1):
            cell_needs = []
            for row_label in table_rows or tickers or ["all_companies"]:
                cell_needs.extend(_table_cell_must_find(row_label, column, fiscal_years))
            parent_facet = _safe_facet_name(column, column_index)
            for aspect_index, aspect in enumerate(cell_needs or [column], start=1):
                needs.append(
                    _need_row(
                        facet=_aspect_facet_name(parent_facet, aspect, aspect_index, len(cell_needs or [column])),
                        must_find=[aspect],
                        parent_facet=parent_facet,
                        aspect_label=aspect,
                    )
                )
        return needs

    return [
        _need_row(
            facet=_safe_facet_name(facet, index),
            must_find=[str(facet)],
        )
        for index, facet in enumerate(row.get("ideal_facets") or [], start=1)
        if str(facet).strip()
    ]


def _need_row(
    facet: str,
    must_find: list[str],
    *,
    parent_facet: str | None = None,
    aspect_label: str | None = None,
) -> dict[str, Any]:
    return {
        "facet": facet,
        "parent_facet": parent_facet or facet,
        "aspect_label": aspect_label or (must_find[0] if must_find else facet),
        "must_find": must_find,
        "target_object_refs": [],
        "label_status": "expanded_eval_unlabeled_retrieval_task",
    }


def _expand_must_find_aspects(
    must_find: list[str],
    *,
    tickers: list[str],
    fiscal_years: list[int],
) -> list[str]:
    expanded = []
    has_expandable_phrase = any(_should_expand_cell_phrase(phrase) for phrase in must_find)
    for phrase in must_find:
        if _is_standalone_year_phrase(phrase):
            if not has_expandable_phrase:
                expanded.append(phrase)
            continue
        target_tickers = _target_tickers_for_phrase(phrase, tickers)
        target_years = _target_years_for_phrase(phrase, fiscal_years)
        if _should_expand_cell_phrase(phrase):
            for ticker in target_tickers or tickers:
                for year in target_years or fiscal_years:
                    expanded.append(_cell_phrase(ticker, year, phrase))
            if not target_tickers and not fiscal_years:
                expanded.append(phrase)
        else:
            expanded.append(phrase)
    return list(dict.fromkeys(expanded))


def _table_cell_must_find(row_label: str, column: str, fiscal_years: list[int]) -> list[str]:
    years = _target_years_for_phrase(column, fiscal_years)
    metric = _metric_from_table_column(column)
    if years:
        return [_cell_phrase(row_label, year, metric) for year in years]
    return [f"{row_label} {column}".strip()]


def _cell_phrase(entity: str, year: int, phrase: str) -> str:
    phrase = _canonical_metric_phrase(phrase)
    return f"{entity} {year} {phrase}".strip()


def _canonical_metric_phrase(phrase: str) -> str:
    lower = phrase.lower().strip()
    if lower == "operating income":
        return "total income from operations operating income"
    if lower == "operating cash flow":
        return "net cash provided by operating activities operating cash flow"
    if lower in {"capex", "capital expenditures"}:
        return "capital expenditures purchases of property and equipment"
    if lower == "advertising revenues":
        return "advertising revenues advertising revenue"
    return phrase


def _metric_from_table_column(column: str) -> str:
    cleaned = str(column)
    cleaned = re.sub(r"\b(?:19|20)\d{2}\b", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or column


def _target_tickers_for_phrase(phrase: str, tickers: list[str]) -> list[str]:
    lower = phrase.lower()
    matched = [
        ticker
        for ticker in tickers
        if ticker.lower() in lower or any(alias in lower for alias in TICKER_ALIASES.get(ticker, ()))
    ]
    return matched or tickers


def _target_years_for_phrase(phrase: str, fiscal_years: list[int]) -> list[int]:
    years = [int(match.group(0)) for match in re.finditer(r"\b(?:19|20)\d{2}\b", phrase)]
    years = [year for year in years if not fiscal_years or year in fiscal_years]
    return years or fiscal_years


def _should_expand_cell_phrase(phrase: str) -> bool:
    lower = phrase.lower()
    if _is_standalone_year_phrase(phrase):
        return False
    return any(term in lower for term in CELL_METRIC_TERMS)


def _is_standalone_year_phrase(phrase: str) -> bool:
    return bool(re.fullmatch(r"\s*(?:19|20)\d{2}\s*", phrase))


def _safe_facet_name(value: str, index: int) -> str:
    chars = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "_":
            chars.append("_")
    name = "".join(chars).strip("_")
    return name[:72] or f"facet_{index:02d}"


def _aspect_facet_name(parent_facet: str, aspect: str, index: int, total: int) -> str:
    if total <= 1:
        return _safe_facet_name(parent_facet, index)
    suffix = _safe_facet_name(aspect, index)
    return f"{_safe_facet_name(parent_facet, index)}__aspect_{index:03d}_{suffix}"[:120]


def _counts(values: Iterable[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc


if __name__ == "__main__":
    main()
