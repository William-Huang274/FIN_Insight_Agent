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
        description="Evaluate aspect-level verifier predictions against weak aspect labels."
    )
    parser.add_argument(
        "--predictions-path",
        default="reports/verifier/sec_tech_10k_qwen35_4b_aspect_compact_full.jsonl",
    )
    parser.add_argument(
        "--report-path",
        default="reports/metrics/sec_tech_10k_qwen35_4b_aspect_compact_full_metrics.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    predictions = list(_read_jsonl(REPO_ROOT / args.predictions_path))
    report = evaluate(predictions)
    report["predictions_path"] = str(REPO_ROOT / args.predictions_path)

    report_path = REPO_ROOT / args.report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def evaluate(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for pred in predictions:
        gold = _normalize_gold_label(pred.get("aspect_reference_label"))
        predicted = _normalize_pred_label(pred.get("verifier_label"))
        rows.append(
            {
                "key": _row_key(pred),
                "aspect_key": _aspect_key(pred),
                "facet_key": _facet_key(pred),
                "gold": gold,
                "predicted": predicted,
                "row": pred,
            }
        )

    evaluated_rows = [row for row in rows if row["gold"] in GOLD_LABELS]
    class_metrics = {label: _class_metrics(evaluated_rows, label) for label in GOLD_LABELS}
    macro_f1 = _ratio(sum(item["f1"] for item in class_metrics.values()), len(class_metrics))
    accuracy = _ratio(sum(row["gold"] == row["predicted"] for row in evaluated_rows), len(evaluated_rows))
    aspect_reports = _aspect_reports(rows)
    facet_reports = _facet_reports(aspect_reports)

    return {
        "mode": "aspect_verifier_eval",
        "row_count": len(rows),
        "evaluated_row_count": len(evaluated_rows),
        "facet_count": len(facet_reports),
        "aspect_count": len(aspect_reports),
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "class_metrics": class_metrics,
        "gold_label_counts": _label_counts(row["gold"] for row in rows),
        "predicted_label_counts": _label_counts(row["predicted"] for row in rows),
        "confusion_matrix": _confusion(rows),
        "bge_top10_aspect_pool": _pool_metrics(rows),
        "policy_keep_direct": _policy_metrics(rows, keep_labels={"direct"}),
        "policy_keep_relevant": _policy_metrics(rows, keep_labels={"direct", "partial"}),
        "parse_status_counts": _label_counts(str(row["row"].get("parse_status") or "missing") for row in rows),
        "facet_reports": facet_reports,
        "aspect_reports": aspect_reports,
    }


def _class_metrics(rows: list[dict[str, Any]], label: str) -> dict[str, float]:
    tp = sum(row["gold"] == label and row["predicted"] == label for row in rows)
    fp = sum(row["gold"] != label and row["predicted"] == label for row in rows)
    fn = sum(row["gold"] == label and row["predicted"] != label for row in rows)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = _ratio(2 * precision * recall, precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def _pool_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [row for row in rows if row["gold"] in GOLD_LABELS]
    aspect_groups = _group_by(evaluated, key_name="aspect_key")
    gold_direct_aspects = {
        aspect_key
        for aspect_key, group in aspect_groups.items()
        if any(row["gold"] == "direct" for row in group)
    }
    gold_relevant_aspects = {
        aspect_key
        for aspect_key, group in aspect_groups.items()
        if any(row["gold"] in RELEVANT for row in group)
    }
    return {
        "objects": len(evaluated),
        "direct_precision": _ratio(sum(row["gold"] == "direct" for row in evaluated), len(evaluated)),
        "relevant_precision": _ratio(sum(row["gold"] in RELEVANT for row in evaluated), len(evaluated)),
        "false_rate": _ratio(sum(row["gold"] == "false" for row in evaluated), len(evaluated)),
        "gold_direct_aspects": len(gold_direct_aspects),
        "gold_relevant_aspects": len(gold_relevant_aspects),
        "direct_aspect_coverage": _ratio(
            sum(any(row["gold"] == "direct" for row in group) for group in aspect_groups.values()),
            len(aspect_groups),
        ),
        "relevant_aspect_coverage": _ratio(
            sum(any(row["gold"] in RELEVANT for row in group) for group in aspect_groups.values()),
            len(aspect_groups),
        ),
        "direct_aspect_recall_on_gold_direct_aspects": 1.0,
        "relevant_aspect_recall_on_gold_relevant_aspects": 1.0,
    }


def _policy_metrics(rows: list[dict[str, Any]], keep_labels: set[str]) -> dict[str, Any]:
    evaluated = [row for row in rows if row["gold"] in GOLD_LABELS]
    kept = [row for row in evaluated if row["predicted"] in keep_labels]
    aspect_groups = _group_by(evaluated, key_name="aspect_key")
    kept_by_aspect = _group_by(kept, key_name="aspect_key")
    facet_groups = _group_by(evaluated, key_name="facet_key")
    kept_by_facet = _group_by(kept, key_name="facet_key")
    gold_direct_aspects = {
        aspect_key
        for aspect_key, group in aspect_groups.items()
        if any(row["gold"] == "direct" for row in group)
    }
    gold_relevant_aspects = {
        aspect_key
        for aspect_key, group in aspect_groups.items()
        if any(row["gold"] in RELEVANT for row in group)
    }
    return {
        "keep_labels": sorted(keep_labels),
        "kept_objects": len(kept),
        "avg_kept_per_aspect": _ratio(len(kept), len(aspect_groups)),
        "avg_kept_per_facet": _ratio(len(kept), len(facet_groups)),
        "kept_precision_direct": _ratio(sum(row["gold"] == "direct" for row in kept), len(kept)),
        "kept_precision_relevant": _ratio(sum(row["gold"] in RELEVANT for row in kept), len(kept)),
        "kept_false_rate": _ratio(sum(row["gold"] == "false" for row in kept), len(kept)),
        "direct_aspect_coverage": _ratio(
            sum(any(row["gold"] == "direct" for row in group) for group in kept_by_aspect.values()),
            len(aspect_groups),
        ),
        "relevant_aspect_coverage": _ratio(
            sum(any(row["gold"] in RELEVANT for row in group) for group in kept_by_aspect.values()),
            len(aspect_groups),
        ),
        "direct_aspect_recall_on_gold_direct_aspects": _ratio(
            sum(
                any(row["gold"] == "direct" for row in kept_by_aspect.get(aspect_key, []))
                for aspect_key in gold_direct_aspects
            ),
            len(gold_direct_aspects),
        ),
        "relevant_aspect_recall_on_gold_relevant_aspects": _ratio(
            sum(
                any(row["gold"] in RELEVANT for row in kept_by_aspect.get(aspect_key, []))
                for aspect_key in gold_relevant_aspects
            ),
            len(gold_relevant_aspects),
        ),
        "facet_all_aspects_with_kept_direct": _ratio(
            sum(_all_aspects_covered(facet_group, kept_by_aspect, target="direct") for facet_group in facet_groups.values()),
            len(facet_groups),
        ),
        "facet_all_gold_direct_aspects_covered": _ratio(
            sum(_all_gold_aspects_covered(facet_group, kept_by_aspect, target="direct") for facet_group in facet_groups.values()),
            len(facet_groups),
        ),
        "facet_all_gold_relevant_aspects_covered": _ratio(
            sum(_all_gold_aspects_covered(facet_group, kept_by_aspect, target="relevant") for facet_group in facet_groups.values()),
            len(facet_groups),
        ),
        "facet_any_aspect_with_kept_direct": _ratio(
            sum(any(row["gold"] == "direct" for row in kept_by_facet.get(facet_key, [])) for facet_key in facet_groups),
            len(facet_groups),
        ),
    }


def _aspect_reports(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = _group_by([row for row in rows if row["gold"] in GOLD_LABELS], key_name="aspect_key")
    reports = []
    for aspect_key, group in sorted(grouped.items()):
        query_id, facet, aspect_id = aspect_key
        direct_hits = [row for row in group if row["predicted"] == "direct"]
        reports.append(
            {
                "query_id": query_id,
                "facet": facet,
                "aspect_id": aspect_id,
                "aspect": group[0]["row"].get("aspect"),
                "objects": len(group),
                "gold_label_counts": _label_counts(row["gold"] for row in group),
                "predicted_label_counts": _label_counts(row["predicted"] for row in group),
                "has_gold_direct": any(row["gold"] == "direct" for row in group),
                "has_gold_relevant": any(row["gold"] in RELEVANT for row in group),
                "has_predicted_direct_gold_direct": any(
                    row["predicted"] == "direct" and row["gold"] == "direct" for row in group
                ),
                "has_predicted_relevant_gold_relevant": any(
                    row["predicted"] in RELEVANT and row["gold"] in RELEVANT for row in group
                ),
                "predicted_direct_ids": [row["key"][3] for row in direct_hits],
                "predicted_direct_false_ids": [
                    row["key"][3]
                    for row in direct_hits
                    if row["gold"] == "false"
                ],
            }
        )
    return reports


def _facet_reports(aspect_reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for report in aspect_reports:
        grouped[(report["query_id"], report["facet"])].append(report)
    reports = []
    for (query_id, facet), group in sorted(grouped.items()):
        reports.append(
            {
                "query_id": query_id,
                "facet": facet,
                "aspects": len(group),
                "aspects_with_gold_direct": sum(item["has_gold_direct"] for item in group),
                "aspects_with_predicted_direct_gold_direct": sum(
                    item["has_predicted_direct_gold_direct"] for item in group
                ),
                "aspects_with_predicted_relevant_gold_relevant": sum(
                    item["has_predicted_relevant_gold_relevant"] for item in group
                ),
                "all_gold_direct_aspects_covered": all(
                    item["has_predicted_direct_gold_direct"]
                    for item in group
                    if item["has_gold_direct"]
                ),
                "all_gold_relevant_aspects_covered": all(
                    item["has_predicted_relevant_gold_relevant"]
                    for item in group
                    if item["has_gold_relevant"]
                ),
                "missing_direct_aspects": [
                    item["aspect"]
                    for item in group
                    if item["has_gold_direct"] and not item["has_predicted_direct_gold_direct"]
                ],
            }
        )
    return reports


def _all_aspects_covered(
    facet_group: list[dict[str, Any]],
    kept_by_aspect: dict[tuple[str, str, str], list[dict[str, Any]]],
    *,
    target: str,
) -> bool:
    aspect_keys = {row["aspect_key"] for row in facet_group}
    for aspect_key in aspect_keys:
        kept = kept_by_aspect.get(aspect_key, [])
        if target == "direct" and not any(row["gold"] == "direct" for row in kept):
            return False
    return True


def _all_gold_aspects_covered(
    facet_group: list[dict[str, Any]],
    kept_by_aspect: dict[tuple[str, str, str], list[dict[str, Any]]],
    *,
    target: str,
) -> bool:
    aspect_keys = {row["aspect_key"] for row in facet_group}
    has_target_aspect = False
    for aspect_key in aspect_keys:
        aspect_rows = [row for row in facet_group if row["aspect_key"] == aspect_key]
        if target == "direct":
            if not any(row["gold"] == "direct" for row in aspect_rows):
                continue
            has_target_aspect = True
            if not any(row["gold"] == "direct" for row in kept_by_aspect.get(aspect_key, [])):
                return False
        elif target == "relevant":
            if not any(row["gold"] in RELEVANT for row in aspect_rows):
                continue
            has_target_aspect = True
            if not any(row["gold"] in RELEVANT for row in kept_by_aspect.get(aspect_key, [])):
                return False
    return has_target_aspect


def _confusion(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    confusion = {gold: {pred: 0 for pred in PRED_LABELS} for gold in (*GOLD_LABELS, "unlabeled")}
    for row in rows:
        gold = row["gold"] if row["gold"] in confusion else "unlabeled"
        pred = row["predicted"] if row["predicted"] in PRED_LABELS else "invalid"
        confusion[gold][pred] += 1
    return confusion


def _group_by(rows: list[dict[str, Any]], *, key_name: str) -> dict[Any, list[dict[str, Any]]]:
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row[key_name]].append(row)
    return grouped


def _normalize_gold_label(value: Any) -> str:
    label = str(value or "unlabeled").strip().lower()
    return label if label in (*GOLD_LABELS, "unlabeled") else "unlabeled"


def _normalize_pred_label(value: Any) -> str:
    label = str(value or "unlabeled").strip().lower()
    return label if label in PRED_LABELS else "invalid"


def _row_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("query_id") or ""),
        str(row.get("facet") or ""),
        str(row.get("aspect_id") or ""),
        str(row.get("object_id") or ""),
    )


def _aspect_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("query_id") or ""),
        str(row.get("facet") or ""),
        str(row.get("aspect_id") or ""),
    )


def _facet_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("query_id") or ""), str(row.get("facet") or ""))


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
