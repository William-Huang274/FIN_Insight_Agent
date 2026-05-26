from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from eval.object_verifier import (  # noqa: E402
    load_structured_object_map,
    read_jsonl,
    verify_object_against_need,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an object-level review sheet with auto direct/partial/false suggestions."
    )
    parser.add_argument(
        "--gold-path",
        default="eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_draft.jsonl",
    )
    parser.add_argument(
        "--predictions-path",
        default="reports/retrieval_eval/sec_tech_10k_object_bm25_variant_predictions.jsonl",
        help="Optional candidate predictions. Use empty string to export only gold target refs.",
    )
    parser.add_argument(
        "--structured-dir",
        default="data/processed_private/structured_objects",
    )
    parser.add_argument("--prefix", default="sec_tech_10k")
    parser.add_argument(
        "--jsonl-output",
        default="eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates.jsonl",
    )
    parser.add_argument(
        "--csv-output",
        default="reports/retrieval_eval/sec_tech_10k_object_review_candidates.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gold_rows = list(read_jsonl(REPO_ROOT / args.gold_path))
    object_map = load_structured_object_map(REPO_ROOT / args.structured_dir, args.prefix)
    predictions = _load_predictions(args.predictions_path)

    review_rows = []
    for row in gold_rows:
        pred = predictions.get(row.get("query_id"), {})
        facet_predictions = {
            item.get("facet"): item
            for item in pred.get("facet_predictions", [])
            if item.get("facet")
        }
        for need in row.get("object_evidence_needs", []):
            facet = need.get("facet")
            facet_pred = facet_predictions.get(facet, {})
            object_ids = facet_pred.get("candidate_object_ids") or _target_object_ids(need)
            rank_by_id = {
                object_id: rank
                for rank, object_id in enumerate(object_ids, start=1)
            }
            hit_by_id = {
                hit.get("object_id"): hit
                for hit in facet_pred.get("hits", [])
                if hit.get("object_id")
            }
            target_ids = set(_target_object_ids(need))
            for object_id in object_ids:
                obj = object_map.get(object_id)
                if not obj:
                    continue
                decision = verify_object_against_need(obj, need)
                hit = hit_by_id.get(object_id, {})
                review_rows.append(
                    _review_row(
                        row=row,
                        need=need,
                        obj=obj,
                        decision=decision,
                        rank=rank_by_id.get(object_id),
                        bm25_score=hit.get("score"),
                        in_gold_target=object_id in target_ids,
                    )
                )

    jsonl_path = REPO_ROOT / args.jsonl_output
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in review_rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")

    csv_path = REPO_ROOT / args.csv_output
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(review_rows, csv_path)

    report = _summarize(review_rows)
    report["jsonl_output"] = str(jsonl_path)
    report["csv_output"] = str(csv_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _load_predictions(predictions_path: str) -> dict[str, dict[str, Any]]:
    if not predictions_path:
        return {}
    path = REPO_ROOT / predictions_path
    if not path.exists():
        return {}
    return {row["query_id"]: row for row in read_jsonl(path)}


def _review_row(
    row: dict[str, Any],
    need: dict[str, Any],
    obj: dict[str, Any],
    decision: dict[str, Any],
    rank: int | None,
    bm25_score: float | None,
    in_gold_target: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "object_review_candidate_v0.1",
        "label_status": "auto_suggested_needs_human_review",
        "query_id": row.get("query_id"),
        "mode": row.get("mode"),
        "ticker": row.get("ticker"),
        "fiscal_year": row.get("fiscal_year"),
        "query": row.get("query"),
        "facet": need.get("facet"),
        "must_find": need.get("must_find", []),
        "object_id": obj.get("object_id"),
        "object_type": obj.get("object_type"),
        "source_evidence_id": obj.get("source_evidence_id"),
        "candidate_rank": rank,
        "bm25_score": bm25_score,
        "in_gold_target_refs": in_gold_target,
        "auto_label": decision["label"],
        "auto_confidence": decision["confidence"],
        "auto_score": decision["score"],
        "matched_must_find": decision["matched_must_find"],
        "partial_must_find": decision["partial_must_find"],
        "missing_must_find": decision["missing_must_find"],
        "matched_numbers": decision["matched_numbers"],
        "important_token_coverage": decision["important_token_coverage"],
        "preview": decision["preview"],
        "human_label": "",
        "human_notes": "",
    }


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fields = [
        "query_id",
        "mode",
        "ticker",
        "fiscal_year",
        "facet",
        "candidate_rank",
        "bm25_score",
        "in_gold_target_refs",
        "auto_label",
        "auto_confidence",
        "auto_score",
        "matched_must_find",
        "partial_must_find",
        "missing_must_find",
        "matched_numbers",
        "important_token_coverage",
        "object_type",
        "object_id",
        "source_evidence_id",
        "preview",
        "human_label",
        "human_notes",
        "query",
        "must_find",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: _csv_value(row.get(key))
                    for key in fields
                }
            )


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = {"direct": 0, "partial": 0, "false": 0}
    target_rows = 0
    for row in rows:
        labels[row["auto_label"]] += 1
        target_rows += int(bool(row.get("in_gold_target_refs")))
    return {
        "review_rows": len(rows),
        "gold_target_rows": target_rows,
        "auto_labels": labels,
    }


def _target_object_ids(need: dict[str, Any]) -> list[str]:
    return [
        ref["object_id"]
        for ref in need.get("target_object_refs", [])
        if ref.get("object_id")
    ]


def _csv_value(value: Any) -> str:
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    if value is None:
        return ""
    return str(value)


if __name__ == "__main__":
    main()
