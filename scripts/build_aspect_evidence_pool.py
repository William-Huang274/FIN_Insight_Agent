from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ASPECT_LABEL_FIELDS = (
    ("direct", "matched_must_find"),
    ("partial", "partial_must_find"),
    ("false", "missing_must_find"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Expand a facet-level evidence pool into one verifier task per must_find aspect."
    )
    parser.add_argument(
        "--input-path",
        default="reports/evidence_pool/sec_tech_10k_bge_top10_evidence_pool.jsonl",
    )
    parser.add_argument(
        "--labels-path",
        default="eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates_codex_labeled.jsonl",
    )
    parser.add_argument(
        "--output-path",
        default="reports/evidence_pool/sec_tech_10k_bge_top10_aspect_evidence_pool.jsonl",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_rows = list(_read_jsonl(REPO_ROOT / args.input_path))
    label_rows = list(_read_jsonl(REPO_ROOT / args.labels_path)) if args.labels_path else []
    label_map = _label_map(label_rows)

    output_rows = []
    for row in input_rows:
        output_rows.extend(_aspect_rows(row, label_map))

    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in output_rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")

    report = {
        "mode": "aspect_evidence_pool_build",
        "schema_version": "task_aspect_evidence_pool_v0.1",
        "input_path": str(REPO_ROOT / args.input_path),
        "labels_path": str(REPO_ROOT / args.labels_path) if args.labels_path else None,
        "output_path": str(output_path),
        "source_rows": len(input_rows),
        "aspect_rows": len(output_rows),
        "facets": len({(row["query_id"], row["facet"]) for row in output_rows}),
        "aspects": len({(row["query_id"], row["facet"], row["aspect_id"]) for row in output_rows}),
        "aspect_reference_label_counts": _counts(row.get("aspect_reference_label") for row in output_rows),
        "missing_reference_rows": sum(row.get("aspect_reference_label") == "unlabeled" for row in output_rows),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _aspect_rows(
    row: dict[str, Any],
    label_map: dict[tuple[str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    query_id = str(row.get("query_id") or "")
    facet = str(row.get("facet") or "")
    object_id = str(row.get("object_id") or "")
    label_row = label_map.get((query_id, facet, object_id), {})
    must_find = [str(item) for item in row.get("must_find") or []]
    rows = []
    for index, aspect in enumerate(must_find, start=1):
        aspect_label, aspect_source = _aspect_reference_label(label_row, aspect)
        item = dict(row)
        item.update(
            {
                "schema_version": "task_aspect_evidence_pool_v0.1",
                "facet_must_find": must_find,
                "aspect": aspect,
                "aspect_index": index,
                "aspect_id": f"{facet}__aspect_{index:02d}",
                "must_find": [aspect],
                "aspect_reference_label": aspect_label,
                "aspect_reference_source": aspect_source,
                "object_reference_label": label_row.get("human_label"),
                "object_reference_notes": label_row.get("human_notes"),
            }
        )
        rows.append(item)
    return rows


def _aspect_reference_label(row: dict[str, Any], aspect: str) -> tuple[str, str]:
    for label, field in ASPECT_LABEL_FIELDS:
        if aspect in set(str(item) for item in row.get(field) or []):
            return label, field
    return "unlabeled", "missing_label_row_or_unassigned_aspect"


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
