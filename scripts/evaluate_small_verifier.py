from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
GOLD_LABELS = ("direct", "partial", "false")
PRED_LABELS = ("direct", "partial", "false", "invalid", "unlabeled")
RELEVANT = {"direct", "partial"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate small verifier direct/partial/false predictions against object review labels."
    )
    parser.add_argument(
        "--labels-path",
        default="eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates_codex_labeled.jsonl",
    )
    parser.add_argument(
        "--predictions-path",
        default="reports/verifier/sec_tech_10k_qwen35_small_verifier_predictions.jsonl",
    )
    parser.add_argument(
        "--report-path",
        default="reports/verifier/sec_tech_10k_qwen35_small_verifier_eval.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    labels = list(_read_jsonl(REPO_ROOT / args.labels_path))
    predictions = list(_read_jsonl(REPO_ROOT / args.predictions_path))
    report = evaluate(labels, predictions)
    report.update(
        {
            "labels_path": str(REPO_ROOT / args.labels_path),
            "predictions_path": str(REPO_ROOT / args.predictions_path),
        }
    )
    report_path = REPO_ROOT / args.report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def evaluate(labels: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    label_map = {
        _row_key(row): str(row.get("human_label") or "unlabeled")
        for row in labels
    }
    rows = []
    for pred in predictions:
        key = _row_key(pred)
        gold = label_map.get(key, "unlabeled")
        predicted = _normalize_pred_label(pred.get("verifier_label"))
        rows.append({"key": key, "gold": gold, "predicted": predicted, "row": pred})

    evaluated_rows = [row for row in rows if row["gold"] in GOLD_LABELS]
    confusion = {
        gold: {pred: 0 for pred in PRED_LABELS}
        for gold in (*GOLD_LABELS, "unlabeled")
    }
    for row in rows:
        gold = row["gold"] if row["gold"] in confusion else "unlabeled"
        pred = row["predicted"] if row["predicted"] in PRED_LABELS else "invalid"
        confusion[gold][pred] += 1

    class_metrics = {
        label: _class_metrics(evaluated_rows, label)
        for label in GOLD_LABELS
    }
    macro_f1 = round(
        sum(item["f1"] for item in class_metrics.values()) / len(class_metrics),
        4,
    )
    accuracy = _ratio(
        sum(row["gold"] == row["predicted"] for row in evaluated_rows),
        len(evaluated_rows),
    )

    facet_reports = _facet_reports(rows)
    return {
        "mode": "small_verifier_eval",
        "row_count": len(rows),
        "evaluated_row_count": len(evaluated_rows),
        "facet_count": len(facet_reports),
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "class_metrics": class_metrics,
        "gold_label_counts": _label_counts(row["gold"] for row in rows),
        "predicted_label_counts": _label_counts(row["predicted"] for row in rows),
        "confusion_matrix": confusion,
        "policy_keep_direct": _policy_metrics(rows, keep_labels={"direct"}),
        "policy_keep_relevant": _policy_metrics(rows, keep_labels={"direct", "partial"}),
        "parse_status_counts": _label_counts(str(row["row"].get("parse_status") or "missing") for row in rows),
        "facets": facet_reports,
    }


def _class_metrics(rows: list[dict[str, Any]], label: str) -> dict[str, float]:
    tp = sum(row["gold"] == label and row["predicted"] == label for row in rows)
    fp = sum(row["gold"] != label and row["predicted"] == label for row in rows)
    fn = sum(row["gold"] == label and row["predicted"] != label for row in rows)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = _ratio(2 * precision * recall, precision + recall)
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def _policy_metrics(rows: list[dict[str, Any]], keep_labels: set[str]) -> dict[str, Any]:
    kept = [row for row in rows if row["predicted"] in keep_labels and row["gold"] in GOLD_LABELS]
    all_facets = {
        (row["key"][0], row["key"][1])
        for row in rows
        if row["gold"] in GOLD_LABELS
    }
    kept_by_facet: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in kept:
        kept_by_facet[(row["key"][0], row["key"][1])].append(row)

    return {
        "keep_labels": sorted(keep_labels),
        "kept_objects": len(kept),
        "kept_precision_direct": _ratio(sum(row["gold"] == "direct" for row in kept), len(kept)),
        "kept_precision_relevant": _ratio(sum(row["gold"] in RELEVANT for row in kept), len(kept)),
        "kept_false_rate": _ratio(sum(row["gold"] == "false" for row in kept), len(kept)),
        "direct_facet_coverage": _ratio(
            sum(any(row["gold"] == "direct" for row in rows_for_facet) for rows_for_facet in kept_by_facet.values()),
            len(all_facets),
        ),
        "relevant_facet_coverage": _ratio(
            sum(any(row["gold"] in RELEVANT for row in rows_for_facet) for rows_for_facet in kept_by_facet.values()),
            len(all_facets),
        ),
    }


def _facet_reports(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["gold"] in GOLD_LABELS:
            grouped[(row["key"][0], row["key"][1])].append(row)
    reports = []
    for (query_id, facet), facet_rows in sorted(grouped.items()):
        reports.append(
            {
                "query_id": query_id,
                "facet": facet,
                "objects": len(facet_rows),
                "gold_label_counts": _label_counts(row["gold"] for row in facet_rows),
                "predicted_label_counts": _label_counts(row["predicted"] for row in facet_rows),
                "has_predicted_direct_gold_direct": any(
                    row["predicted"] == "direct" and row["gold"] == "direct"
                    for row in facet_rows
                ),
                "has_predicted_relevant_gold_relevant": any(
                    row["predicted"] in RELEVANT and row["gold"] in RELEVANT
                    for row in facet_rows
                ),
                "predicted_direct_ids": [
                    row["key"][2]
                    for row in facet_rows
                    if row["predicted"] == "direct"
                ],
                "predicted_false_gold_direct_ids": [
                    row["key"][2]
                    for row in facet_rows
                    if row["predicted"] == "false" and row["gold"] == "direct"
                ],
            }
        )
    return reports


def _normalize_pred_label(value: Any) -> str:
    label = str(value or "unlabeled").strip().lower()
    return label if label in PRED_LABELS else "invalid"


def _row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("query_id") or ""),
        str(row.get("facet") or ""),
        str(row.get("object_id") or ""),
    )


def _label_counts(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


def _read_jsonl(path: str | Path) -> Iterable[dict[str, Any]]:
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {input_path}:{line_number}") from exc


if __name__ == "__main__":
    main()
