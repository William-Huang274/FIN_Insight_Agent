from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate candidate/selected object IDs against reviewed object labels."
    )
    parser.add_argument(
        "--labels-path",
        default="eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates_codex_labeled.jsonl",
    )
    parser.add_argument(
        "--predictions-path",
        default="reports/retrieval_eval/sec_tech_10k_object_rule_verifier_predictions.jsonl",
    )
    parser.add_argument(
        "--report-path",
        default="reports/retrieval_eval/sec_tech_10k_object_rule_verifier_codex_label_eval.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    labels = list(_read_jsonl(REPO_ROOT / args.labels_path))
    predictions = list(_read_jsonl(REPO_ROOT / args.predictions_path))
    report = evaluate(labels, predictions)
    report["labels_path"] = str(REPO_ROOT / args.labels_path)
    report["predictions_path"] = str(REPO_ROOT / args.predictions_path)

    report_path = REPO_ROOT / args.report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def evaluate(
    labels: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    label_map = {
        (row["query_id"], row["facet"], row["object_id"]): row["human_label"]
        for row in labels
    }
    available_facets = {
        (row["query_id"], row["facet"])
        for row in labels
    }
    facet_predictions = []
    for row in predictions:
        query_id = row.get("query_id")
        for facet_pred in row.get("facet_predictions", []):
            facet = facet_pred.get("facet")
            if (query_id, facet) not in available_facets:
                continue
            facet_predictions.append(
                _evaluate_facet(query_id, facet, facet_pred, label_map)
            )

    totals = {
        "facets": len(facet_predictions),
        "candidate_relevant_hit": 0,
        "candidate_direct_hit": 0,
        "selected_relevant_hit": 0,
        "selected_direct_hit": 0,
        "candidate_objects": 0,
        "selected_objects": 0,
        "candidate_relevant_objects": 0,
        "selected_relevant_objects": 0,
        "selected_direct_objects": 0,
        "selected_partial_objects": 0,
        "selected_false_objects": 0,
    }
    for item in facet_predictions:
        totals["candidate_relevant_hit"] += int(item["candidate_relevant_hit"])
        totals["candidate_direct_hit"] += int(item["candidate_direct_hit"])
        totals["selected_relevant_hit"] += int(item["selected_relevant_hit"])
        totals["selected_direct_hit"] += int(item["selected_direct_hit"])
        totals["candidate_objects"] += item["candidate_objects"]
        totals["selected_objects"] += item["selected_objects"]
        totals["candidate_relevant_objects"] += item["candidate_relevant_objects"]
        totals["selected_relevant_objects"] += item["selected_relevant_objects"]
        totals["selected_direct_objects"] += item["selected_label_counts"]["direct"]
        totals["selected_partial_objects"] += item["selected_label_counts"]["partial"]
        totals["selected_false_objects"] += item["selected_label_counts"]["false"]

    return {
        "mode": "review_label_prediction_eval",
        "facet_count": totals["facets"],
        "candidate_relevant_facet_coverage": _ratio(totals["candidate_relevant_hit"], totals["facets"]),
        "candidate_direct_facet_coverage": _ratio(totals["candidate_direct_hit"], totals["facets"]),
        "selected_relevant_facet_coverage": _ratio(totals["selected_relevant_hit"], totals["facets"]),
        "selected_direct_facet_coverage": _ratio(totals["selected_direct_hit"], totals["facets"]),
        "candidate_object_precision_relevant": _ratio(totals["candidate_relevant_objects"], totals["candidate_objects"]),
        "selected_object_precision_relevant": _ratio(totals["selected_relevant_objects"], totals["selected_objects"]),
        "selected_object_precision_direct": _ratio(totals["selected_direct_objects"], totals["selected_objects"]),
        "candidate_objects": totals["candidate_objects"],
        "candidate_relevant_objects": totals["candidate_relevant_objects"],
        "selected_objects": totals["selected_objects"],
        "selected_relevant_objects": totals["selected_relevant_objects"],
        "selected_label_counts": {
            "direct": totals["selected_direct_objects"],
            "partial": totals["selected_partial_objects"],
            "false": totals["selected_false_objects"],
        },
        "facets": facet_predictions,
    }


def _evaluate_facet(
    query_id: str,
    facet: str,
    facet_pred: dict[str, Any],
    label_map: dict[tuple[str, str, str], str],
) -> dict[str, Any]:
    candidate_ids = list(facet_pred.get("candidate_object_ids", []))
    selected_ids = list(facet_pred.get("selected_object_ids", []))
    candidate_labels = [_label_for(query_id, facet, object_id, label_map) for object_id in candidate_ids]
    selected_labels = [_label_for(query_id, facet, object_id, label_map) for object_id in selected_ids]
    selected_counts = _label_counts(selected_labels)
    candidate_relevant = sum(1 for label in candidate_labels if label in {"direct", "partial"})
    selected_relevant = sum(1 for label in selected_labels if label in {"direct", "partial"})
    return {
        "query_id": query_id,
        "facet": facet,
        "candidate_objects": len(candidate_ids),
        "selected_objects": len(selected_ids),
        "candidate_relevant_objects": candidate_relevant,
        "selected_relevant_objects": selected_relevant,
        "candidate_relevant_hit": any(label in {"direct", "partial"} for label in candidate_labels),
        "candidate_direct_hit": "direct" in candidate_labels,
        "selected_relevant_hit": any(label in {"direct", "partial"} for label in selected_labels),
        "selected_direct_hit": "direct" in selected_labels,
        "selected_label_counts": selected_counts,
        "selected_ids_by_label": {
            label: [
                object_id
                for object_id, object_label in zip(selected_ids, selected_labels)
                if object_label == label
            ]
            for label in ("direct", "partial", "false", "unlabeled")
        },
    }


def _label_for(
    query_id: str,
    facet: str,
    object_id: str,
    label_map: dict[tuple[str, str, str], str],
) -> str:
    return label_map.get((query_id, facet, object_id), "unlabeled")


def _label_counts(labels: list[str]) -> dict[str, int]:
    return {
        label: sum(1 for item in labels if item == label)
        for label in ("direct", "partial", "false", "unlabeled")
    }


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
