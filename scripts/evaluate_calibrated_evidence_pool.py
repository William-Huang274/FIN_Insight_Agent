from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


RELEVANT = {"direct", "partial"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate calibrated evidence-pool citation/background roles on reviewed human gold."
    )
    parser.add_argument(
        "--evidence-pool-path",
        default="reports/evidence_pool/sec_tech_10k_calibrated_evidence_pool.jsonl",
    )
    parser.add_argument(
        "--human-gold-path",
        default="eval_sets/sec_tech_10k_aspect_policy_human_gold_v0_1.jsonl",
    )
    parser.add_argument(
        "--report-path",
        default="reports/metrics/sec_tech_10k_calibrated_evidence_pool_human_gold_eval.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    aspect_rows = _read_jsonl(REPO_ROOT / args.evidence_pool_path)
    gold = _human_gold_map(REPO_ROOT / args.human_gold_path)
    report = evaluate(aspect_rows, gold)
    report["evidence_pool_path"] = str(REPO_ROOT / args.evidence_pool_path)
    report["human_gold_path"] = str(REPO_ROOT / args.human_gold_path)

    report_path = REPO_ROOT / args.report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def evaluate(aspect_rows: list[dict[str, Any]], gold: dict[tuple[str, str, str, str], dict[str, Any]]) -> dict[str, Any]:
    citation_rows = _role_rows(aspect_rows, "citation_evidence")
    background_rows = _role_rows(aspect_rows, "background_evidence")
    reviewed_citations = [_attach_gold(row, gold) for row in citation_rows if _key(row) in gold]
    reviewed_background = [_attach_gold(row, gold) for row in background_rows if _key(row) in gold]
    missing_rows = [row for row in aspect_rows if row.get("missing_aspect")]

    return {
        "mode": "calibrated_evidence_pool_human_gold_eval",
        "aspects": len(aspect_rows),
        "missing_aspects": len(missing_rows),
        "missing_aspect_examples": [
            {
                "query_id": row.get("query_id"),
                "facet": row.get("facet"),
                "aspect": row.get("aspect"),
                "missing_reason": row.get("missing_reason"),
            }
            for row in missing_rows
        ],
        "citation_evidence": _role_metrics(reviewed_citations),
        "background_evidence": _role_metrics(reviewed_background),
        "reviewed_citation_examples_non_direct": [
            _compact(row)
            for row in reviewed_citations
            if row["human_label"] != "direct"
        ],
        "reviewed_background_examples_human_direct": [
            _compact(row)
            for row in reviewed_background
            if row["human_label"] == "direct"
        ][:30],
    }


def _role_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "reviewed_rows": len(rows),
        "human_label_counts": _counts(row["human_label"] for row in rows),
        "citation_precision": _ratio(sum(row["human_label"] == "direct" for row in rows), len(rows)),
        "broad_relevance_precision": _ratio(sum(row["human_label"] in RELEVANT for row in rows), len(rows)),
        "reject_rate": _ratio(sum(row["human_label"] == "false" for row in rows), len(rows)),
    }


def _role_rows(aspect_rows: list[dict[str, Any]], role_field: str) -> list[dict[str, Any]]:
    rows = []
    for aspect in aspect_rows:
        for evidence in aspect.get(role_field) or []:
            row = {
                "query_id": aspect.get("query_id"),
                "facet": aspect.get("facet"),
                "aspect_id": aspect.get("aspect_id"),
                "aspect": aspect.get("aspect"),
                **evidence,
            }
            rows.append(row)
    return rows


def _attach_gold(row: dict[str, Any], gold: dict[tuple[str, str, str, str], dict[str, Any]]) -> dict[str, Any]:
    return {**row, "human_label": gold[_key(row)].get("human_label"), "human_notes": gold[_key(row)].get("human_notes")}


def _compact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_id": row.get("query_id"),
        "facet": row.get("facet"),
        "aspect": row.get("aspect"),
        "object_id": row.get("object_id"),
        "verifier_label": row.get("verifier_label"),
        "verifier_confidence": row.get("verifier_confidence"),
        "human_label": row.get("human_label"),
        "notes": row.get("human_notes"),
    }


def _human_gold_map(path: Path) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    return {
        (row["query_id"], row["facet"], row["aspect_id"], row["object_id"]): row
        for row in _read_jsonl(path)
    }


def _key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("query_id") or ""),
        str(row.get("facet") or ""),
        str(row.get("aspect_id") or ""),
        str(row.get("object_id") or ""),
    )


def _counts(values: Iterable[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
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
