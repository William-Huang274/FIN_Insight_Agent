from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate object-level target coverage for planner/retriever/verifier outputs."
    )
    parser.add_argument(
        "--gold-path",
        default="eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_draft.jsonl",
    )
    parser.add_argument(
        "--predictions-path",
        default=None,
        help="Optional JSONL predictions with query_id and candidate/selected/cited object ID lists.",
    )
    parser.add_argument(
        "--report-path",
        default=None,
        help="Optional path to write the JSON report.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gold_rows = list(_read_jsonl(REPO_ROOT / args.gold_path))
    if args.predictions_path:
        predictions = {
            row["query_id"]: row
            for row in _read_jsonl(REPO_ROOT / args.predictions_path)
        }
        report = _evaluate_predictions(gold_rows, predictions)
    else:
        report = _gold_readiness(gold_rows)
    if args.report_path:
        report_path = REPO_ROOT / args.report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _gold_readiness(gold_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    total_facets = 0
    facets_with_targets = 0
    for row in gold_rows:
        query_facets = 0
        query_facets_with_targets = 0
        empty_facets = []
        for need in row.get("object_evidence_needs", []):
            query_facets += 1
            total_facets += 1
            target_ids = _target_object_ids(need)
            if target_ids:
                query_facets_with_targets += 1
                facets_with_targets += 1
            else:
                empty_facets.append(need.get("facet"))
        rows.append(
            {
                "query_id": row.get("query_id"),
                "facet_count": query_facets,
                "facets_with_object_targets": query_facets_with_targets,
                "facets_without_object_targets": empty_facets,
            }
        )
    return {
        "mode": "gold_readiness",
        "query_count": len(gold_rows),
        "facet_count": total_facets,
        "facets_with_object_targets": facets_with_targets,
        "facet_target_coverage": _ratio(facets_with_targets, total_facets),
        "queries": rows,
    }


def _evaluate_predictions(
    gold_rows: list[dict[str, Any]],
    predictions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    query_reports = []
    totals = {
        "facets": 0,
        "candidate_hit": 0,
        "selected_hit": 0,
        "cited_hit": 0,
        "missing_predictions": 0,
        "candidate_objects": 0,
        "candidate_target_objects": 0,
        "selected_objects": 0,
        "selected_target_objects": 0,
        "cited_objects": 0,
        "cited_target_objects": 0,
    }
    for row in gold_rows:
        query_id = row.get("query_id")
        pred = predictions.get(query_id)
        if pred is None:
            totals["missing_predictions"] += 1
        facet_predictions = _facet_prediction_map(pred)
        global_candidate_ids = set(_object_id_list(pred, "candidate_object_ids"))
        global_selected_ids = set(_object_id_list(pred, "selected_object_ids"))
        global_cited_ids = set(_object_id_list(pred, "cited_object_ids"))
        facet_reports = []
        for need in row.get("object_evidence_needs", []):
            target_ids = set(_target_object_ids(need))
            if not target_ids:
                continue
            facet_pred = facet_predictions.get(need.get("facet"), {})
            candidate_ids = set(_object_id_list(facet_pred, "candidate_object_ids")) or global_candidate_ids
            selected_ids = set(_object_id_list(facet_pred, "selected_object_ids")) or global_selected_ids
            cited_ids = set(_object_id_list(facet_pred, "cited_object_ids")) or global_cited_ids
            totals["facets"] += 1
            candidate_hit = bool(candidate_ids & target_ids)
            selected_hit = bool(selected_ids & target_ids)
            cited_hit = bool(cited_ids & target_ids)
            totals["candidate_hit"] += int(candidate_hit)
            totals["selected_hit"] += int(selected_hit)
            totals["cited_hit"] += int(cited_hit)
            totals["candidate_objects"] += len(candidate_ids)
            totals["candidate_target_objects"] += len(candidate_ids & target_ids)
            totals["selected_objects"] += len(selected_ids)
            totals["selected_target_objects"] += len(selected_ids & target_ids)
            totals["cited_objects"] += len(cited_ids)
            totals["cited_target_objects"] += len(cited_ids & target_ids)
            facet_reports.append(
                {
                    "facet": need.get("facet"),
                    "target_count": len(target_ids),
                    "candidate_hit": candidate_hit,
                    "selected_hit": selected_hit,
                    "cited_hit": cited_hit,
                    "candidate_target_count": len(candidate_ids & target_ids),
                    "selected_target_count": len(selected_ids & target_ids),
                    "cited_target_count": len(cited_ids & target_ids),
                }
            )
        query_reports.append({"query_id": query_id, "facets": facet_reports})
    return {
        "mode": "prediction_coverage",
        "query_count": len(gold_rows),
        "missing_predictions": totals["missing_predictions"],
        "facet_count": totals["facets"],
        "candidate_facet_coverage": _ratio(totals["candidate_hit"], totals["facets"]),
        "selected_facet_coverage": _ratio(totals["selected_hit"], totals["facets"]),
        "cited_facet_coverage": _ratio(totals["cited_hit"], totals["facets"]),
        "candidate_object_precision": _ratio(
            totals["candidate_target_objects"], totals["candidate_objects"]
        ),
        "selected_object_precision": _ratio(
            totals["selected_target_objects"], totals["selected_objects"]
        ),
        "cited_object_precision": _ratio(
            totals["cited_target_objects"], totals["cited_objects"]
        ),
        "candidate_objects": totals["candidate_objects"],
        "candidate_target_objects": totals["candidate_target_objects"],
        "selected_objects": totals["selected_objects"],
        "selected_target_objects": totals["selected_target_objects"],
        "cited_objects": totals["cited_objects"],
        "cited_target_objects": totals["cited_target_objects"],
        "queries": query_reports,
    }


def _target_object_ids(need: dict[str, Any]) -> list[str]:
    return [
        ref["object_id"]
        for ref in need.get("target_object_refs", [])
        if ref.get("object_id")
    ]


def _object_id_list(row: dict[str, Any] | None, key: str) -> list[str]:
    if not row:
        return []
    value = row.get(key, [])
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _facet_prediction_map(row: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not row:
        return {}
    return {
        item.get("facet"): item
        for item in row.get("facet_predictions", [])
        if item.get("facet")
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
