from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


RELEVANT_LABELS = {"direct", "partial"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a calibrated per-aspect evidence pool with citation/background/reject roles."
    )
    parser.add_argument(
        "--predictions-path",
        default="reports/verifier/sec_tech_10k_qwen35_4b_aspect_compact_full730.jsonl",
    )
    parser.add_argument(
        "--pool-path",
        default="reports/evidence_pool/sec_tech_10k_bge_top10_aspect_evidence_pool.jsonl",
    )
    parser.add_argument(
        "--human-gold-path",
        default="",
        help="Optional reviewed labels for audit fields only; never changes model-selected roles.",
    )
    parser.add_argument(
        "--output-path",
        default="reports/evidence_pool/sec_tech_10k_calibrated_evidence_pool.jsonl",
    )
    parser.add_argument(
        "--grouped-output-path",
        default="reports/evidence_pool/sec_tech_10k_calibrated_evidence_pool_grouped.json",
    )
    parser.add_argument(
        "--report-path",
        default="reports/metrics/sec_tech_10k_calibrated_evidence_pool_report.json",
    )
    parser.add_argument("--citation-confidence-min", type=float, default=0.90)
    parser.add_argument(
        "--citation-selector",
        choices=("confidence_then_rerank", "confidence_plus_rerank"),
        default="confidence_plus_rerank",
    )
    parser.add_argument("--rerank-weight", type=float, default=0.20)
    parser.add_argument("--max-citations-per-aspect", type=int, default=3)
    parser.add_argument("--max-background-per-aspect", type=int, default=5)
    parser.add_argument("--include-rejects", action="store_true")
    parser.add_argument("--max-rejects-per-aspect", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pool = _pool_map(REPO_ROOT / args.pool_path)
    predictions = list(_read_jsonl(REPO_ROOT / args.predictions_path))
    human_gold = _human_gold_map(REPO_ROOT / args.human_gold_path) if args.human_gold_path else {}
    aspect_rows = export_aspect_rows(
        predictions=predictions,
        pool=pool,
        human_gold=human_gold,
        citation_confidence_min=args.citation_confidence_min,
        citation_selector=args.citation_selector,
        rerank_weight=args.rerank_weight,
        max_citations_per_aspect=args.max_citations_per_aspect,
        max_background_per_aspect=args.max_background_per_aspect,
        include_rejects=args.include_rejects,
        max_rejects_per_aspect=args.max_rejects_per_aspect,
    )

    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in aspect_rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")

    grouped = _grouped_output(aspect_rows)
    grouped_output_path = REPO_ROOT / args.grouped_output_path
    grouped_output_path.parent.mkdir(parents=True, exist_ok=True)
    grouped_output_path.write_text(json.dumps(grouped, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = _report(
        aspect_rows=aspect_rows,
        args=args,
        output_path=output_path,
        grouped_output_path=grouped_output_path,
    )
    report_path = REPO_ROOT / args.report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def export_aspect_rows(
    *,
    predictions: list[dict[str, Any]],
    pool: dict[tuple[str, str, str, str], dict[str, Any]],
    human_gold: dict[tuple[str, str, str, str], dict[str, Any]],
    citation_confidence_min: float,
    citation_selector: str,
    rerank_weight: float,
    max_citations_per_aspect: int,
    max_background_per_aspect: int,
    include_rejects: bool,
    max_rejects_per_aspect: int,
) -> list[dict[str, Any]]:
    grouped = _group_by_aspect(predictions)
    aspect_rows = []
    for aspect_key, rows in sorted(grouped.items()):
        rows = [row for row in rows if _prediction_pool_key(row) in pool]
        if not rows:
            continue
        meta = _aspect_meta(rows[0], pool[_prediction_pool_key(rows[0])])
        citations = _select_diverse_rows(
            _citation_rows(
            rows,
            citation_confidence_min=citation_confidence_min,
            citation_selector=citation_selector,
            rerank_weight=rerank_weight,
            ),
            max_rows=max_citations_per_aspect,
        )
        citation_ids = {row["object_id"] for row in citations}
        background = _select_diverse_rows(
            [
                row
                for row in _background_rows(rows)
                if row["object_id"] not in citation_ids
            ],
            max_rows=max_background_per_aspect,
        )
        reject_rows = [
            row
            for row in _reject_rows(rows)
            if row["object_id"] not in citation_ids
        ][:max_rejects_per_aspect]
        aspect_rows.append(
            {
                "schema_version": "calibrated_aspect_evidence_pool_v0.1",
                **meta,
                "policy": {
                    "citation_selector": f"qwen_direct_{citation_selector}",
                    "citation_confidence_min": citation_confidence_min,
                    "rerank_weight": rerank_weight if citation_selector == "confidence_plus_rerank" else None,
                    "max_citations_per_aspect": max_citations_per_aspect,
                    "max_background_per_aspect": max_background_per_aspect,
                    "background_labels": ["direct", "partial"],
                },
                "citation_evidence": [
                    _evidence_record(row, pool, human_gold, evidence_role="citation")
                    for row in citations
                ],
                "background_evidence": [
                    _evidence_record(row, pool, human_gold, evidence_role="background")
                    for row in background
                ],
                "reject_evidence": [
                    _evidence_record(row, pool, human_gold, evidence_role="reject")
                    for row in reject_rows
                ]
                if include_rejects
                else [],
                "missing_aspect": not citations,
                "missing_reason": _missing_reason(rows, citation_confidence_min) if not citations else None,
                "candidate_counts": _candidate_counts(rows, citation_confidence_min),
            }
        )
    return aspect_rows


def _citation_rows(
    rows: list[dict[str, Any]],
    *,
    citation_confidence_min: float,
    citation_selector: str,
    rerank_weight: float,
) -> list[dict[str, Any]]:
    candidates = [
        row
        for row in rows
        if row.get("verifier_label") == "direct"
        and float(row.get("verifier_confidence") or 0.0) >= citation_confidence_min
    ]
    if citation_selector == "confidence_plus_rerank":
        return sorted(
            candidates,
            key=lambda row: _citation_weighted_sort_key(row, rerank_weight=rerank_weight),
            reverse=True,
        )
    return sorted(candidates, key=_citation_sort_key, reverse=True)


def _select_diverse_rows(rows: list[dict[str, Any]], *, max_rows: int) -> list[dict[str, Any]]:
    if max_rows <= 0:
        return []
    selected: list[dict[str, Any]] = []
    seen_full_keys: set[tuple[str, str, str]] = set()
    seen_ticker_year: set[tuple[str, str]] = set()
    for row in rows:
        key = _diversity_key(row)
        if key not in seen_full_keys:
            selected.append(row)
            seen_full_keys.add(key)
            seen_ticker_year.add((key[0], key[1]))
        if len(selected) >= max_rows:
            return selected
    for row in rows:
        key = _diversity_key(row)
        ticker_year = (key[0], key[1])
        if row in selected or ticker_year in seen_ticker_year:
            continue
        selected.append(row)
        seen_ticker_year.add(ticker_year)
        if len(selected) >= max_rows:
            return selected
    for row in rows:
        if row not in selected:
            selected.append(row)
        if len(selected) >= max_rows:
            break
    return selected


def _diversity_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("object_ticker") or row.get("ticker") or ""),
        str(row.get("object_fiscal_year") or row.get("fiscal_year") or ""),
        str(row.get("object_type") or ""),
    )


def _background_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [
        row
        for row in rows
        if row.get("verifier_label") in RELEVANT_LABELS
    ]
    return sorted(candidates, key=_background_sort_key, reverse=True)


def _reject_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [
        row
        for row in rows
        if row.get("verifier_label") == "false"
    ]
    return sorted(candidates, key=_rerank_sort_key, reverse=True)


def _candidate_counts(rows: list[dict[str, Any]], citation_confidence_min: float) -> dict[str, int]:
    return {
        "total": len(rows),
        "qwen_direct": sum(row.get("verifier_label") == "direct" for row in rows),
        "qwen_direct_confident": sum(
            row.get("verifier_label") == "direct"
            and float(row.get("verifier_confidence") or 0.0) >= citation_confidence_min
            for row in rows
        ),
        "qwen_partial": sum(row.get("verifier_label") == "partial" for row in rows),
        "qwen_false": sum(row.get("verifier_label") == "false" for row in rows),
        "parsed": sum(row.get("parse_status") == "parsed" for row in rows),
    }


def _missing_reason(rows: list[dict[str, Any]], citation_confidence_min: float) -> str:
    if not any(row.get("verifier_label") == "direct" for row in rows):
        return "no_qwen_direct_candidate"
    return f"qwen_direct_below_confidence_{citation_confidence_min:.2f}"


def _evidence_record(
    row: dict[str, Any],
    pool: dict[tuple[str, str, str, str], dict[str, Any]],
    human_gold: dict[tuple[str, str, str, str], dict[str, Any]],
    *,
    evidence_role: str,
) -> dict[str, Any]:
    pool_row = pool[_prediction_pool_key(row)]
    gold_row = human_gold.get(_prediction_pool_key(row), {})
    record = {
        "evidence_role": evidence_role,
        "object_id": row.get("object_id"),
        "object_type": row.get("object_type"),
        "source_evidence_id": row.get("source_evidence_id"),
        "section": row.get("section"),
        "subsection": row.get("subsection"),
        "source_url": pool_row.get("source_url"),
        "local_path": pool_row.get("local_path"),
        "pool_rank": row.get("pool_rank"),
        "rerank_score": row.get("rerank_score"),
        "bm25_rank": row.get("bm25_rank"),
        "bm25_score": row.get("bm25_score"),
        "verifier_label": row.get("verifier_label"),
        "verifier_confidence": row.get("verifier_confidence"),
        "usable_for_synthesis": row.get("usable_for_synthesis"),
        "preview": row.get("preview"),
        "object_text": pool_row.get("object_text"),
        "object_text_chars": pool_row.get("object_text_chars"),
        "object_text_truncated": pool_row.get("object_text_truncated"),
    }
    if gold_row:
        record.update(
            {
                "audit_human_label": gold_row.get("human_label"),
                "audit_evidence_role": gold_row.get("evidence_role"),
                "audit_human_notes": gold_row.get("human_notes"),
            }
        )
    return record


def _aspect_meta(prediction: dict[str, Any], pool_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_id": prediction.get("query_id"),
        "cohort": prediction.get("cohort"),
        "mode": prediction.get("mode"),
        "difficulty": prediction.get("difficulty"),
        "scoring_profile": prediction.get("scoring_profile"),
        "ticker": prediction.get("ticker"),
        "tickers": prediction.get("tickers"),
        "fiscal_year": prediction.get("fiscal_year"),
        "fiscal_years": prediction.get("fiscal_years"),
        "query": pool_row.get("query"),
        "facet": prediction.get("facet"),
        "parent_facet": prediction.get("parent_facet") or pool_row.get("parent_facet") or prediction.get("facet"),
        "aspect_label": prediction.get("aspect_label") or pool_row.get("aspect_label"),
        "facet_must_find": prediction.get("facet_must_find") or pool_row.get("facet_must_find") or [],
        "aspect_id": prediction.get("aspect_id"),
        "aspect_index": prediction.get("aspect_index"),
        "aspect": prediction.get("aspect"),
    }


def _grouped_output(aspect_rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in aspect_rows:
        query = grouped.setdefault(
            str(row["query_id"]),
            {
                "query_id": row["query_id"],
                "cohort": row.get("cohort"),
                "mode": row.get("mode"),
                "difficulty": row.get("difficulty"),
                "scoring_profile": row.get("scoring_profile"),
                "ticker": row.get("ticker"),
                "tickers": row.get("tickers"),
                "fiscal_year": row.get("fiscal_year"),
                "fiscal_years": row.get("fiscal_years"),
                "query": row.get("query"),
                "facets": {},
            },
        )
        facet_key = str(row.get("parent_facet") or row["facet"])
        facet = query["facets"].setdefault(
            facet_key,
            {
                "facet": facet_key,
                "source_facets": [],
                "facet_must_find": row.get("facet_must_find") or [],
                "aspects": [],
                "missing_aspects": [],
            },
        )
        if row.get("facet") not in facet["source_facets"]:
            facet["source_facets"].append(row.get("facet"))
        aspect_entry = {
            "aspect_id": row.get("aspect_id"),
            "aspect_index": row.get("aspect_index"),
            "aspect": row.get("aspect"),
            "source_facet": row.get("facet"),
            "aspect_label": row.get("aspect_label"),
            "citation_evidence": row.get("citation_evidence") or [],
            "background_evidence": row.get("background_evidence") or [],
            "missing_aspect": row.get("missing_aspect"),
            "missing_reason": row.get("missing_reason"),
        }
        facet["aspects"].append(aspect_entry)
        if row.get("missing_aspect"):
            facet["missing_aspects"].append(
                {
                    "aspect_id": row.get("aspect_id"),
                    "aspect": row.get("aspect"),
                    "missing_reason": row.get("missing_reason"),
                }
            )
    queries = []
    for query in grouped.values():
        query["facets"] = list(query["facets"].values())
        queries.append(query)
    return {
        "schema_version": "calibrated_grouped_evidence_pool_v0.1",
        "queries": queries,
    }


def _report(
    *,
    aspect_rows: list[dict[str, Any]],
    args: argparse.Namespace,
    output_path: Path,
    grouped_output_path: Path,
) -> dict[str, Any]:
    citation_rows = [
        evidence
        for row in aspect_rows
        for evidence in row.get("citation_evidence") or []
    ]
    background_rows = [
        evidence
        for row in aspect_rows
        for evidence in row.get("background_evidence") or []
    ]
    missing_rows = [row for row in aspect_rows if row.get("missing_aspect")]
    facets = {(row["query_id"], row["facet"]) for row in aspect_rows}
    queries = {row["query_id"] for row in aspect_rows}
    return {
        "mode": "calibrated_evidence_pool_export",
        "schema_version": "calibrated_aspect_evidence_pool_v0.1",
        "predictions_path": str(REPO_ROOT / args.predictions_path),
        "pool_path": str(REPO_ROOT / args.pool_path),
        "human_gold_path": str(REPO_ROOT / args.human_gold_path) if args.human_gold_path else None,
        "output_path": str(output_path),
        "grouped_output_path": str(grouped_output_path),
        "citation_confidence_min": args.citation_confidence_min,
        "citation_selector": args.citation_selector,
        "rerank_weight": args.rerank_weight,
        "max_citations_per_aspect": args.max_citations_per_aspect,
        "max_background_per_aspect": args.max_background_per_aspect,
        "queries": len(queries),
        "facets": len(facets),
        "aspects": len(aspect_rows),
        "citation_evidence": len(citation_rows),
        "background_evidence": len(background_rows),
        "missing_aspects": len(missing_rows),
        "citation_object_type_counts": _counts(row.get("object_type") for row in citation_rows),
        "background_object_type_counts": _counts(row.get("object_type") for row in background_rows),
        "missing_aspect_examples": [
            {
                "query_id": row.get("query_id"),
                "facet": row.get("facet"),
                "aspect_id": row.get("aspect_id"),
                "aspect": row.get("aspect"),
                "missing_reason": row.get("missing_reason"),
            }
            for row in missing_rows
        ],
    }


def _group_by_aspect(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                str(row.get("query_id") or ""),
                str(row.get("facet") or ""),
                str(row.get("aspect_id") or ""),
            )
        ].append(row)
    return grouped


def _pool_map(path: Path) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    return {
        (row["query_id"], row["facet"], row["aspect_id"], row["object_id"]): row
        for row in _read_jsonl(path)
    }


def _human_gold_map(path: Path) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    return {
        (row["query_id"], row["facet"], row["aspect_id"], row["object_id"]): row
        for row in _read_jsonl(path)
    }


def _prediction_pool_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("query_id") or ""),
        str(row.get("facet") or ""),
        str(row.get("aspect_id") or ""),
        str(row.get("object_id") or ""),
    )


def _citation_sort_key(row: dict[str, Any]) -> tuple[float, float, int]:
    return (
        float(row.get("verifier_confidence") or 0.0),
        float(row.get("rerank_score") or 0.0),
        -int(row.get("pool_rank") or 999),
    )


def _citation_weighted_sort_key(row: dict[str, Any], *, rerank_weight: float) -> tuple[float, float, float, int]:
    confidence = float(row.get("verifier_confidence") or 0.0)
    rerank_score = float(row.get("rerank_score") or 0.0)
    return (
        confidence + rerank_weight * rerank_score,
        confidence,
        rerank_score,
        -int(row.get("pool_rank") or 999),
    )


def _background_sort_key(row: dict[str, Any]) -> tuple[int, float, float, int]:
    label_priority = 2 if row.get("verifier_label") == "direct" else 1
    return (
        label_priority,
        float(row.get("verifier_confidence") or 0.0),
        float(row.get("rerank_score") or 0.0),
        -int(row.get("pool_rank") or 999),
    )


def _rerank_sort_key(row: dict[str, Any]) -> tuple[float, float, int]:
    return (
        float(row.get("rerank_score") or 0.0),
        float(row.get("verifier_confidence") or 0.0),
        -int(row.get("pool_rank") or 999),
    )


def _counts(values: Iterable[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    input_path = Path(path)
    rows = []
    with input_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {input_path}:{line_number}") from exc
    return rows


if __name__ == "__main__":
    main()
