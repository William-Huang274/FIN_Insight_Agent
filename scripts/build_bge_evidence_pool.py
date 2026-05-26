from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from eval.object_verifier import load_structured_object_map, read_jsonl  # noqa: E402
from evidence.structured_text import structured_object_preview, structured_object_search_text  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a flat task-specific evidence pool from BGE reranker output."
    )
    parser.add_argument(
        "--reranker-predictions-path",
        default="reports/retrieval_eval/sec_tech_10k_object_bge_reranker_v2_m3_cloud_predictions.jsonl",
    )
    parser.add_argument(
        "--labels-path",
        default="eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates_codex_labeled.jsonl",
    )
    parser.add_argument(
        "--structured-dir",
        default="data/processed_private/structured_objects",
    )
    parser.add_argument("--prefix", default="sec_tech_10k")
    parser.add_argument(
        "--output-path",
        default="reports/evidence_pool/sec_tech_10k_bge_top10_evidence_pool.jsonl",
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--object-max-chars", type=int, default=4000)
    parser.add_argument(
        "--include-reference-labels",
        action="store_true",
        help="Include Codex-assisted labels for audit exports. Do not use these fields in verifier prompts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prediction_rows = list(read_jsonl(REPO_ROOT / args.reranker_predictions_path))
    object_map = load_structured_object_map(REPO_ROOT / args.structured_dir, args.prefix)
    label_rows = list(read_jsonl(REPO_ROOT / args.labels_path)) if args.labels_path else []
    facet_meta = _facet_metadata(label_rows)
    label_map = _label_map(label_rows)

    output_rows = []
    for row in prediction_rows:
        query_id = str(row.get("query_id") or "")
        for facet_pred in row.get("facet_predictions", []):
            facet = str(facet_pred.get("facet") or "")
            meta = _prediction_metadata(row) | facet_meta.get((query_id, facet), {})
            output_rows.extend(
                _pool_rows_for_facet(
                    query_id=query_id,
                    facet=facet,
                    facet_pred=facet_pred,
                    meta=meta,
                    label_map=label_map,
                    object_map=object_map,
                    top_k=args.top_k,
                    object_max_chars=args.object_max_chars,
                    include_reference_labels=args.include_reference_labels,
                )
            )

    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for item in output_rows:
            f.write(json.dumps(item, ensure_ascii=False))
            f.write("\n")

    report = {
        "mode": "bge_evidence_pool_build",
        "schema_version": "task_evidence_pool_v0.1",
        "reranker_predictions_path": str(REPO_ROOT / args.reranker_predictions_path),
        "labels_path": str(REPO_ROOT / args.labels_path) if args.labels_path else None,
        "structured_dir": str(REPO_ROOT / args.structured_dir),
        "top_k": args.top_k,
        "object_max_chars": args.object_max_chars,
        "include_reference_labels": args.include_reference_labels,
        "rows": len(output_rows),
        "facets": len({(row["query_id"], row["facet"]) for row in output_rows}),
        "output_path": str(output_path),
        "object_type_counts": _counts(row["object_type"] for row in output_rows),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _pool_rows_for_facet(
    query_id: str,
    facet: str,
    facet_pred: dict[str, Any],
    meta: dict[str, Any],
    label_map: dict[tuple[str, str, str], dict[str, Any]],
    object_map: dict[str, dict[str, Any]],
    top_k: int,
    object_max_chars: int,
    include_reference_labels: bool,
) -> list[dict[str, Any]]:
    rows = []
    for hit in facet_pred.get("hits", [])[:top_k]:
        object_id = str(hit.get("object_id") or "")
        obj = object_map.get(object_id)
        if not obj:
            continue
        text = structured_object_search_text(obj)
        reference = label_map.get((query_id, facet, object_id), {})
        item = {
            "schema_version": "task_evidence_pool_v0.1",
            "query_id": query_id,
            "cohort": meta.get("cohort"),
            "mode": meta.get("mode"),
            "difficulty": meta.get("difficulty"),
            "scoring_profile": meta.get("scoring_profile"),
            "ticker": meta.get("ticker") or obj.get("ticker"),
            "tickers": meta.get("ticker") if isinstance(meta.get("ticker"), list) else None,
            "fiscal_year": meta.get("fiscal_year") or obj.get("fiscal_year"),
            "fiscal_years": meta.get("fiscal_year") if isinstance(meta.get("fiscal_year"), list) else None,
            "query": meta.get("query") or facet_pred.get("query"),
            "facet": facet,
            "parent_facet": facet_pred.get("parent_facet") or facet,
            "aspect_label": facet_pred.get("aspect_label"),
            "must_find": meta.get("must_find") or facet_pred.get("must_find") or [],
            "query_variants": facet_pred.get("query_variants") or [],
            "pool_source": "bge_reranker",
            "pool_rank": int(hit.get("rank") or 0),
            "pool_top_k": top_k,
            "rerank_rank": int(hit.get("rank") or 0),
            "rerank_score": hit.get("rerank_score", hit.get("score")),
            "bm25_rank": hit.get("bm25_rank"),
            "bm25_score": hit.get("bm25_score"),
            "object_id": object_id,
            "object_type": obj.get("object_type"),
            "source_evidence_id": obj.get("source_evidence_id"),
            "object_ticker": obj.get("ticker"),
            "object_fiscal_year": obj.get("fiscal_year"),
            "section": obj.get("section"),
            "subsection": obj.get("subsection"),
            "source_url": obj.get("source_url"),
            "local_path": obj.get("local_path"),
            "preview": structured_object_preview(obj),
            "object_text": text[:object_max_chars],
            "object_text_chars": min(len(text), object_max_chars),
            "object_text_truncated": len(text) > object_max_chars,
        }
        if include_reference_labels:
            item.update(
                {
                    "reference_label": reference.get("human_label"),
                    "reference_notes": reference.get("human_notes"),
                    "reference_reviewer": reference.get("reviewer"),
                }
            )
        rows.append(item)
    return rows


def _facet_metadata(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    meta: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("query_id") or ""), str(row.get("facet") or ""))
        if key in meta:
            continue
        meta[key] = {
            "mode": row.get("mode"),
            "ticker": row.get("ticker"),
            "fiscal_year": row.get("fiscal_year"),
            "query": row.get("query"),
            "must_find": row.get("must_find") or [],
        }
    return meta


def _prediction_metadata(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "cohort": row.get("cohort"),
        "mode": row.get("mode"),
        "difficulty": row.get("difficulty"),
        "scoring_profile": row.get("scoring_profile"),
        "ticker": row.get("ticker") or row.get("tickers"),
        "fiscal_year": row.get("fiscal_year") or row.get("fiscal_years"),
        "query": row.get("query") or row.get("query_zh") or row.get("query_en"),
    }


def _label_map(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    return {
        (
            str(row.get("query_id") or ""),
            str(row.get("facet") or ""),
            str(row.get("object_id") or ""),
        ): row
        for row in rows
    }


def _counts(values: Iterable[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    main()
