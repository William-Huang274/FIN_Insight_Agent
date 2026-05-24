from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


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
        description="Apply a deterministic object verifier baseline to candidate predictions."
    )
    parser.add_argument(
        "--gold-path",
        default="eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_draft.jsonl",
    )
    parser.add_argument(
        "--predictions-path",
        default="reports/retrieval_eval/sec_tech_10k_object_bm25_variant_predictions.jsonl",
    )
    parser.add_argument(
        "--structured-dir",
        default="data/processed_private/structured_objects",
    )
    parser.add_argument("--prefix", default="sec_tech_10k")
    parser.add_argument(
        "--output-path",
        default="reports/retrieval_eval/sec_tech_10k_object_rule_verifier_predictions.jsonl",
    )
    parser.add_argument("--max-selected-per-facet", type=int, default=5)
    parser.add_argument("--max-partial-per-facet", type=int, default=1)
    parser.add_argument("--min-partial-score", type=float, default=4.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gold_rows = list(read_jsonl(REPO_ROOT / args.gold_path))
    predictions = {
        row["query_id"]: row
        for row in read_jsonl(REPO_ROOT / args.predictions_path)
    }
    object_map = load_structured_object_map(REPO_ROOT / args.structured_dir, args.prefix)
    output_rows = [
        _verify_query(row, predictions.get(row.get("query_id"), {}), object_map, args)
        for row in gold_rows
    ]

    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in output_rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")

    report = _summarize(output_rows)
    report["output_path"] = str(output_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _verify_query(
    gold_row: dict[str, Any],
    prediction_row: dict[str, Any],
    object_map: dict[str, dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    facet_predictions = {
        item.get("facet"): item
        for item in prediction_row.get("facet_predictions", [])
        if item.get("facet")
    }
    output_facets = []
    all_candidate_ids: list[str] = []
    all_selected_ids: list[str] = []

    for need in gold_row.get("object_evidence_needs", []):
        facet = need.get("facet")
        facet_pred = facet_predictions.get(facet, {})
        candidate_ids = list(facet_pred.get("candidate_object_ids", []))
        all_candidate_ids.extend(candidate_ids)
        decisions = []
        for rank, object_id in enumerate(candidate_ids, start=1):
            obj = object_map.get(object_id)
            if not obj:
                continue
            decision = verify_object_against_need(obj, need)
            decision["candidate_rank"] = rank
            decision["bm25_score"] = _hit_score(facet_pred, object_id)
            decisions.append(decision)

        selected_ids = _select_objects(
            decisions,
            max_selected=args.max_selected_per_facet,
            max_partial=args.max_partial_per_facet,
            min_partial_score=args.min_partial_score,
        )
        all_selected_ids.extend(selected_ids)
        output_facets.append(
            {
                **facet_pred,
                "selected_object_ids": selected_ids,
                "cited_object_ids": [],
                "verifier": {
                    "type": "deterministic_rule_baseline",
                    "label_space": ["direct", "partial", "false"],
                    "max_selected_per_facet": args.max_selected_per_facet,
                    "max_partial_per_facet": args.max_partial_per_facet,
                    "min_partial_score": args.min_partial_score,
                },
                "verifier_decisions": decisions,
            }
        )

    return {
        "query_id": gold_row.get("query_id"),
        "candidate_object_ids": list(dict.fromkeys(all_candidate_ids)),
        "selected_object_ids": list(dict.fromkeys(all_selected_ids)),
        "cited_object_ids": [],
        "facet_predictions": output_facets,
    }


def _select_objects(
    decisions: list[dict[str, Any]],
    max_selected: int,
    max_partial: int,
    min_partial_score: float,
) -> list[str]:
    direct = [item for item in decisions if item["label"] == "direct"]
    partial = [
        item
        for item in decisions
        if item["label"] == "partial" and item["score"] >= min_partial_score
    ]
    direct.sort(key=_decision_sort_key)
    partial.sort(key=_decision_sort_key)
    selected: list[str] = []
    for item in direct:
        if len(selected) >= max_selected:
            break
        selected.append(item["object_id"])
    partial_budget = min(max_partial, max_selected - len(selected))
    for item in partial[:partial_budget]:
        selected.append(item["object_id"])
    return list(dict.fromkeys(selected))


def _decision_sort_key(item: dict[str, Any]) -> tuple[float, int, str]:
    return (-float(item.get("score", 0.0)), int(item.get("candidate_rank", 9999)), str(item.get("object_id")))


def _hit_score(facet_pred: dict[str, Any], object_id: str) -> float | None:
    for hit in facet_pred.get("hits", []):
        if hit.get("object_id") == object_id:
            return hit.get("score")
    return None


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    label_counts = {"direct": 0, "partial": 0, "false": 0}
    facet_count = 0
    selected_count = 0
    for row in rows:
        for facet in row.get("facet_predictions", []):
            facet_count += 1
            selected_count += len(facet.get("selected_object_ids", []))
            for decision in facet.get("verifier_decisions", []):
                label_counts[decision["label"]] += 1
    return {
        "query_count": len(rows),
        "facet_count": facet_count,
        "selected_objects": selected_count,
        "decision_labels": label_counts,
    }


if __name__ == "__main__":
    main()
