from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


POLICIES = (
    "qwen_direct_highest_confidence",
    "qwen_direct_highest_rerank",
    "qwen_direct_highest_rerank_conf90",
)
RELEVANT = {"direct", "partial"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate per-aspect direct evidence selection policies on human-reviewed gold rows."
    )
    parser.add_argument(
        "--gold-path",
        default="eval_sets/sec_tech_10k_aspect_policy_human_gold_v0_1.jsonl",
    )
    parser.add_argument(
        "--aspect-pool-path",
        default="reports/evidence_pool/sec_tech_10k_bge_top10_aspect_evidence_pool.jsonl",
    )
    parser.add_argument(
        "--report-path",
        default="reports/metrics/sec_tech_10k_aspect_policy_human_gold_v0_1_metrics.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gold_rows = _read_jsonl(REPO_ROOT / args.gold_path)
    aspect_meta = _all_aspects(REPO_ROOT / args.aspect_pool_path)
    report = evaluate(gold_rows, aspect_meta)
    report["gold_path"] = str(REPO_ROOT / args.gold_path)
    report["aspect_pool_path"] = str(REPO_ROOT / args.aspect_pool_path)

    report_path = REPO_ROOT / args.report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def evaluate(gold_rows: list[dict[str, Any]], aspect_meta: dict[tuple[str, str, str], dict[str, Any]]) -> dict[str, Any]:
    aspect_keys = set(aspect_meta)
    rows_by_policy = _rows_by_policy(gold_rows)
    policy_reports = {}
    for policy in POLICIES:
        rows = rows_by_policy.get(policy, [])
        selected_aspects = {_aspect_key(row) for row in rows}
        direct_aspects = {_aspect_key(row) for row in rows if row["human_label"] == "direct"}
        relevant_aspects = {_aspect_key(row) for row in rows if row["human_label"] in RELEVANT}
        policy_reports[policy] = {
            "selected_rows": len(rows),
            "selected_aspects": len(selected_aspects),
            "missing_aspects": len(aspect_keys - selected_aspects),
            "label_counts": _counts(row["human_label"] for row in rows),
            "citation_precision": _ratio(sum(row["human_label"] == "direct" for row in rows), len(rows)),
            "broad_relevance_precision": _ratio(sum(row["human_label"] in RELEVANT for row in rows), len(rows)),
            "reject_rate": _ratio(sum(row["human_label"] == "false" for row in rows), len(rows)),
            "citation_aspect_coverage": _ratio(len(direct_aspects), len(aspect_keys)),
            "relevant_aspect_coverage": _ratio(len(relevant_aspects), len(aspect_keys)),
            "selected_aspect_coverage": _ratio(len(selected_aspects), len(aspect_keys)),
            "missing_aspect_examples": [
                aspect_meta[key]
                for key in sorted(aspect_keys - selected_aspects)
            ],
            "background_rows": [
                _compact_row(row)
                for row in rows
                if row["human_label"] == "partial"
            ],
            "reject_rows": [
                _compact_row(row)
                for row in rows
                if row["human_label"] == "false"
            ],
        }

    disagreement = _weak_label_disagreement(gold_rows)
    return {
        "mode": "aspect_policy_human_gold_eval",
        "reviewed_rows": len(gold_rows),
        "all_aspects": len(aspect_keys),
        "reviewed_label_counts": _counts(row["human_label"] for row in gold_rows),
        "policy_reports": policy_reports,
        "weak_label_disagreement": disagreement,
    }


def _rows_by_policy(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for policy in row.get("selected_by_policies") or []:
            grouped[policy].append(row)
    return grouped


def _weak_label_disagreement(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = _counts(
        f"{row.get('weak_aspect_reference_label')}->{row.get('human_label')}"
        for row in rows
    )
    changed = [
        _compact_row(row)
        for row in rows
        if row.get("weak_aspect_reference_label") != row.get("human_label")
    ]
    return {
        "pair_counts": pairs,
        "changed_rows": len(changed),
        "changed_examples": changed[:30],
    }


def _compact_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_id": row.get("query_id"),
        "facet": row.get("facet"),
        "aspect": row.get("aspect"),
        "object_id": row.get("object_id"),
        "weak": row.get("weak_aspect_reference_label"),
        "human": row.get("human_label"),
        "policies": row.get("selected_by_policies"),
        "notes": row.get("human_notes"),
    }


def _all_aspects(path: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    aspects = {}
    for row in _read_jsonl(path):
        key = (row["query_id"], row["facet"], row["aspect_id"])
        aspects.setdefault(
            key,
            {
                "query_id": row.get("query_id"),
                "facet": row.get("facet"),
                "aspect_id": row.get("aspect_id"),
                "aspect": row.get("aspect"),
            },
        )
    return aspects


def _aspect_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (row["query_id"], row["facet"], row["aspect_id"])


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return dict(sorted(counts.items()))


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


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
