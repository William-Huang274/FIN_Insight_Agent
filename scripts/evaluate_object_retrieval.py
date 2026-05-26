from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.object_bm25_retriever import ObjectBM25Retriever  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate object-level BM25 candidate coverage against object gold draft."
    )
    parser.add_argument(
        "--gold-path",
        default="eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_draft.jsonl",
    )
    parser.add_argument("--index-dir", default="data/indexes/bm25/sec_tech_10k_objects")
    parser.add_argument("--top-k", type=int, default=25)
    parser.add_argument(
        "--variant-top-k",
        type=int,
        default=25,
        help="Per-variant retrieval depth before RRF fusion.",
    )
    parser.add_argument(
        "--selected-top-n",
        type=int,
        default=0,
        help="Optional lexical selection baseline: mark top N fused candidates as selected.",
    )
    parser.add_argument(
        "--predictions-path",
        default="reports/retrieval_eval/sec_tech_10k_object_bm25_predictions.jsonl",
    )
    parser.add_argument(
        "--report-path",
        default="reports/retrieval_eval/sec_tech_10k_object_bm25_eval.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gold_rows = list(_read_jsonl(REPO_ROOT / args.gold_path))
    retriever = ObjectBM25Retriever(REPO_ROOT / args.index_dir)
    prediction_rows = [
        _predict_query(row, retriever, args.top_k, args.variant_top_k, args.selected_top_n)
        for row in gold_rows
    ]

    predictions_path = REPO_ROOT / args.predictions_path
    predictions_path.parent.mkdir(parents=True, exist_ok=True)
    with predictions_path.open("w", encoding="utf-8") as f:
        for row in prediction_rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")

    report = _evaluate(gold_rows, prediction_rows, args.top_k, args.selected_top_n)
    report["predictions_path"] = str(predictions_path)
    report_path = REPO_ROOT / args.report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _predict_query(
    row: dict[str, Any],
    retriever: ObjectBM25Retriever,
    top_k: int,
    variant_top_k: int,
    selected_top_n: int,
) -> dict[str, Any]:
    facet_predictions = []
    all_candidate_ids = []
    for need in row.get("object_evidence_needs", []):
        query = _facet_query(row, need)
        filters = _query_filters(row, need)
        query_variants = _facet_query_variants(row, need)
        hits = _fused_search(retriever, query_variants, filters, top_k=top_k, variant_top_k=variant_top_k)
        object_ids = [hit["object_id"] for hit in hits]
        selected_object_ids = object_ids[:selected_top_n] if selected_top_n > 0 else []
        all_candidate_ids.extend(object_ids)
        facet_predictions.append(
            {
                "facet": need.get("facet"),
                "parent_facet": need.get("parent_facet") or need.get("facet"),
                "aspect_label": need.get("aspect_label") or (need.get("must_find") or [None])[0],
                "must_find": need.get("must_find", []),
                "query": query,
                "query_variants": query_variants,
                "candidate_object_ids": object_ids,
                "selected_object_ids": selected_object_ids,
                "cited_object_ids": [],
                "hits": [
                    {
                        "rank": hit["rank"],
                        "score": hit["score"],
                        "object_id": hit["object_id"],
                        "object_type": hit["object_type"],
                        "source_evidence_id": hit["source_evidence_id"],
                        "preview": hit["preview"],
                    }
                    for hit in hits
                ],
            }
        )
    return {
        "query_id": row.get("query_id"),
        "cohort": row.get("cohort"),
        "mode": row.get("mode"),
        "difficulty": row.get("difficulty"),
        "scoring_profile": row.get("scoring_profile"),
        "query": row.get("query"),
        "query_en": row.get("query_en"),
        "query_zh": row.get("query_zh"),
        "ticker": row.get("ticker"),
        "tickers": row.get("tickers"),
        "fiscal_year": row.get("fiscal_year"),
        "fiscal_years": row.get("fiscal_years"),
        "ideal_facets": row.get("ideal_facets", []),
        "candidate_object_ids": list(dict.fromkeys(all_candidate_ids)),
        "selected_object_ids": [],
        "cited_object_ids": [],
        "facet_predictions": facet_predictions,
    }


def _facet_query(row: dict[str, Any], need: dict[str, Any]) -> str:
    parts = [
        row.get("query"),
        need.get("parent_facet") or need.get("facet"),
        " ".join(need.get("must_find", [])),
    ]
    return " ".join(str(part) for part in parts if part)


def _facet_query_variants(row: dict[str, Any], need: dict[str, Any]) -> list[str]:
    must_find = [str(item) for item in need.get("must_find", []) if str(item).strip()]
    parent_facet = need.get("parent_facet") or need.get("facet")
    variants = [
        " ".join(must_find),
        " ".join(str(part) for part in [parent_facet, " ".join(must_find)] if part),
        _facet_query(row, need),
    ]
    return list(dict.fromkeys(variant for variant in variants if variant.strip()))


def _fused_search(
    retriever: ObjectBM25Retriever,
    query_variants: list[str],
    filters: dict[str, Any],
    top_k: int,
    variant_top_k: int,
) -> list[dict[str, Any]]:
    fused: dict[str, dict[str, Any]] = {}
    for query in query_variants:
        hits = retriever.search(query, top_k=variant_top_k, filters=filters)
        for hit in hits:
            object_id = hit["object_id"]
            entry = fused.setdefault(
                object_id,
                {
                    **hit,
                    "score": 0.0,
                    "best_bm25_score": hit["score"],
                    "matched_variants": [],
                },
            )
            entry["score"] += 1.0 / (60.0 + hit["rank"])
            entry["best_bm25_score"] = max(entry["best_bm25_score"], hit["score"])
            entry["matched_variants"].append({"query": query, "rank": hit["rank"], "score": hit["score"]})
    ranked = sorted(
        fused.values(),
        key=lambda item: (-item["score"], -item["best_bm25_score"], item["object_id"]),
    )[:top_k]
    for rank, hit in enumerate(ranked, start=1):
        hit["rank"] = rank
    return ranked


def _query_filters(row: dict[str, Any], need: dict[str, Any]) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    must_text = " ".join(str(item) for item in need.get("must_find", [])).lower()
    ticker = row.get("ticker")
    targeted_ticker = _targeted_ticker(must_text, ticker)
    if targeted_ticker:
        filters["ticker"] = targeted_ticker
    elif isinstance(ticker, list):
        filters["ticker"] = [str(item).upper() for item in ticker]
    elif ticker:
        filters["ticker"] = str(ticker).upper()
    targeted_year = _targeted_year(must_text, row.get("fiscal_year"))
    if targeted_year:
        filters["fiscal_year"] = targeted_year
    elif row.get("fiscal_year"):
        filters["fiscal_year"] = row["fiscal_year"]
    return filters


def _targeted_ticker(must_text: str, tickers: Any) -> str | None:
    if not isinstance(tickers, list):
        return None
    for ticker in [str(item).upper() for item in tickers]:
        if ticker.lower() in must_text:
            return ticker
    aliases = {
        "MSFT": ("microsoft", "azure"),
        "AAPL": ("apple",),
        "NVDA": ("nvidia",),
        "GOOGL": ("alphabet", "google"),
        "META": ("meta", "family of apps", "reality labs"),
        "AMZN": ("amazon", "aws"),
        "AMD": ("amd",),
        "ADBE": ("adobe",),
        "PANW": ("palo alto",),
        "SNOW": ("snowflake",),
    }
    for ticker in [str(item).upper() for item in tickers]:
        if any(alias in must_text for alias in aliases.get(ticker, ())):
            return ticker
    return None


def _targeted_year(must_text: str, fiscal_years: Any) -> int | None:
    allowed = set(int(item) for item in fiscal_years) if isinstance(fiscal_years, list) else set()
    for match in re.finditer(r"\b(?:19|20)\d{2}\b", must_text):
        year = int(match.group(0))
        if not allowed or year in allowed:
            return year
    return None


def _evaluate(
    gold_rows: list[dict[str, Any]],
    prediction_rows: list[dict[str, Any]],
    top_k: int,
    selected_top_n: int,
) -> dict[str, Any]:
    predictions = {row["query_id"]: row for row in prediction_rows}
    query_reports = []
    totals = {
        "facets": 0,
        "candidate_hit": 0,
        "selected_hit": 0,
        "cited_hit": 0,
        "selected_objects": 0,
        "selected_target_objects": 0,
    }
    for row in gold_rows:
        query_id = row.get("query_id")
        pred = predictions.get(query_id, {})
        facet_map = {
            item.get("facet"): item
            for item in pred.get("facet_predictions", [])
        }
        facet_reports = []
        for need in row.get("object_evidence_needs", []):
            target_ids = set(_target_object_ids(need))
            if not target_ids:
                continue
            facet = need.get("facet")
            facet_pred = facet_map.get(facet, {})
            candidate_ids = set(facet_pred.get("candidate_object_ids", []))
            selected_ids = set(facet_pred.get("selected_object_ids", []))
            cited_ids = set(facet_pred.get("cited_object_ids", []))
            candidate_hit = bool(candidate_ids & target_ids)
            selected_hit = bool(selected_ids & target_ids)
            cited_hit = bool(cited_ids & target_ids)
            totals["facets"] += 1
            totals["candidate_hit"] += int(candidate_hit)
            totals["selected_hit"] += int(selected_hit)
            totals["cited_hit"] += int(cited_hit)
            totals["selected_objects"] += len(selected_ids)
            totals["selected_target_objects"] += len(selected_ids & target_ids)
            facet_reports.append(
                {
                    "facet": facet,
                    "target_count": len(target_ids),
                    "candidate_hit": candidate_hit,
                    "selected_hit": selected_hit,
                    "cited_hit": cited_hit,
                    "candidate_hit_object_ids": sorted(candidate_ids & target_ids),
                    "top_hit_ids": facet_pred.get("candidate_object_ids", [])[:5],
                }
            )
        query_reports.append(
            {
                "query_id": query_id,
                "facet_count": len(facet_reports),
                "candidate_hits": sum(1 for item in facet_reports if item["candidate_hit"]),
                "facets": facet_reports,
            }
        )
    return {
        "mode": "object_bm25_candidate_coverage",
        "top_k": top_k,
        "selected_top_n": selected_top_n,
        "query_count": len(gold_rows),
        "facet_count": totals["facets"],
        "candidate_facet_coverage": _ratio(totals["candidate_hit"], totals["facets"]),
        "selected_facet_coverage": _ratio(totals["selected_hit"], totals["facets"]),
        "cited_facet_coverage": _ratio(totals["cited_hit"], totals["facets"]),
        "selected_object_precision": _ratio(totals["selected_target_objects"], totals["selected_objects"]),
        "selected_objects": totals["selected_objects"],
        "selected_target_objects": totals["selected_target_objects"],
        "queries": query_reports,
    }


def _target_object_ids(need: dict[str, Any]) -> list[str]:
    return [
        ref["object_id"]
        for ref in need.get("target_object_refs", [])
        if ref.get("object_id")
    ]


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


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
