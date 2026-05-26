from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a reviewed-style object-level gold draft from evidence-level eval labels."
    )
    parser.add_argument(
        "--eval-path",
        default="eval_sets/sec_tech_10k_agent_reasoning_eval.jsonl",
    )
    parser.add_argument(
        "--structured-dir",
        default="data/processed_private/structured_objects",
    )
    parser.add_argument("--prefix", default="sec_tech_10k")
    parser.add_argument(
        "--output-path",
        default="eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_draft.jsonl",
    )
    parser.add_argument("--top-objects-per-facet", type=int, default=12)
    parser.add_argument("--min-score", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    eval_path = REPO_ROOT / args.eval_path
    structured_dir = REPO_ROOT / args.structured_dir
    output_path = REPO_ROOT / args.output_path

    objects_by_evidence = _load_structured_objects(structured_dir, args.prefix)
    rows = list(_read_jsonl(eval_path))
    output_rows = [
        _convert_query(row, objects_by_evidence, args.top_objects_per_facet, args.min_score)
        for row in rows
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in output_rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")

    summary = _summarize(output_rows)
    summary["output_path"] = str(output_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _load_structured_objects(
    structured_dir: Path,
    prefix: str,
) -> dict[str, list[dict[str, Any]]]:
    objects_by_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for suffix in ("tables", "metrics", "claims"):
        path = structured_dir / f"{prefix}_{suffix}.jsonl"
        for obj in _read_jsonl(path):
            obj["_object_text"] = _object_text(obj)
            objects_by_evidence[obj["source_evidence_id"]].append(obj)
    return objects_by_evidence


def _convert_query(
    row: dict[str, Any],
    objects_by_evidence: dict[str, list[dict[str, Any]]],
    top_objects_per_facet: int,
    min_score: float,
) -> dict[str, Any]:
    object_needs = []
    for need in row.get("evidence_needs", []):
        target_evidence_ids = need.get("target_evidence_ids", [])
        candidate_objects = [
            obj
            for evidence_id in target_evidence_ids
            for obj in objects_by_evidence.get(evidence_id, [])
        ]
        scored = _score_objects(candidate_objects, need, min_score)
        object_needs.append(
            {
                "facet": need.get("facet"),
                "target_evidence_ids": target_evidence_ids,
                "acceptable_sections": need.get("acceptable_sections", []),
                "evidence_types": need.get("evidence_types", []),
                "must_find": need.get("must_find", []),
                "target_object_refs": scored[:top_objects_per_facet],
                "candidate_object_counts": _object_counts(candidate_objects),
                "label_status": "auto_mapped_from_evidence_needs_human_review_required",
            }
        )

    return {
        "schema_version": "agent_reasoning_object_gold_v0.1",
        "label_status": "draft_auto_mapped_needs_human_review",
        "query_id": row.get("query_id"),
        "mode": row.get("mode"),
        "query": row.get("query"),
        "ticker": row.get("ticker"),
        "fiscal_year": row.get("fiscal_year"),
        "difficulty": row.get("difficulty"),
        "ideal_facets": row.get("ideal_facets", []),
        "object_evidence_needs": object_needs,
        "reference_answer_points": row.get("reference_answer_points", []),
        "required_caveats": row.get("missing_evidence_expectations", []),
        "common_wrong_conclusions": row.get("agent_reasoning_rubric", {}).get("failure_modes", []),
        "planner_rubric": row.get("agent_reasoning_rubric", {}).get("planner_should_cover", []),
        "synthesis_rubric": row.get("agent_reasoning_rubric", {}).get("synthesis_should_do", []),
    }


def _score_objects(
    objects: list[dict[str, Any]],
    need: dict[str, Any],
    min_score: float,
) -> list[dict[str, Any]]:
    search_phrases = list(need.get("must_find", [])) or [need.get("facet", "")]
    scored = []
    for obj in objects:
        score, matched_terms = _match_score(obj["_object_text"], search_phrases)
        if score < min_score and not matched_terms:
            continue
        scored.append(
            {
                "object_id": obj.get("object_id"),
                "object_type": obj.get("object_type"),
                "source_evidence_id": obj.get("source_evidence_id"),
                "match_score": round(score, 4),
                "matched_terms": matched_terms[:8],
                "preview": _preview(obj),
                "review_label": "candidate_must_have_or_partial",
            }
        )
    scored.sort(key=lambda item: (-item["match_score"], item["object_type"], item["object_id"]))
    return scored


def _match_score(text: str, phrases: list[str]) -> tuple[float, list[str]]:
    norm_text = _normalize_text(text)
    object_tokens = set(_tokens(norm_text))
    score = 0.0
    matched_terms = []
    for phrase in phrases:
        norm_phrase = _normalize_text(str(phrase))
        if not norm_phrase:
            continue
        phrase_tokens = [token for token in _tokens(norm_phrase) if len(token) > 1]
        if not phrase_tokens:
            continue
        overlap = [token for token in phrase_tokens if token in object_tokens]
        numeric_overlap = [token for token in overlap if any(char.isdigit() for char in token)]
        coverage = len(overlap) / max(len(phrase_tokens), 1)
        if norm_phrase in norm_text:
            score += 5.0
            matched_terms.append(str(phrase))
        if overlap:
            score += coverage
        if not any(any(char.isdigit() for char in token) for token in phrase_tokens) and coverage >= 0.6 and len(overlap) >= 2:
            score += 2.0
            matched_terms.append(f"partial:{phrase}")
        if numeric_overlap:
            score += 2.0 * len(numeric_overlap)
            matched_terms.extend(numeric_overlap)
    return score, list(dict.fromkeys(matched_terms))


def _object_text(obj: dict[str, Any]) -> str:
    object_type = obj.get("object_type")
    if object_type == "table":
        row_text = " ".join(" ".join(row) for row in obj.get("rows", []))
        return " ".join(
            str(value)
            for value in [
                obj.get("title"),
                obj.get("text_before"),
                row_text,
                obj.get("text_after"),
            ]
            if value
        )
    if object_type == "metric":
        return " ".join(
            str(value)
            for value in [
                obj.get("metric_name"),
                obj.get("raw_value"),
                obj.get("value"),
                obj.get("unit"),
                obj.get("period"),
                obj.get("segment"),
                obj.get("row_label"),
                obj.get("column_label"),
                obj.get("context"),
            ]
            if value is not None
        )
    if object_type == "claim":
        return " ".join(
            str(value)
            for value in [
                obj.get("claim_text"),
                obj.get("claim_type"),
                " ".join(obj.get("entities", [])),
                " ".join(obj.get("metrics_mentioned", [])),
                obj.get("context"),
            ]
            if value
        )
    return json.dumps(obj, ensure_ascii=False)


def _preview(obj: dict[str, Any]) -> str:
    if obj.get("object_type") == "metric":
        parts = [
            obj.get("metric_name"),
            obj.get("segment"),
            obj.get("period"),
            obj.get("raw_value"),
            obj.get("unit"),
        ]
        return " | ".join(str(part) for part in parts if part is not None)
    if obj.get("object_type") == "claim":
        return str(obj.get("claim_text", ""))[:260]
    if obj.get("object_type") == "table":
        return str(obj.get("title") or obj.get("rows", [])[:2])[:260]
    return str(obj.get("object_id"))


def _object_counts(objects: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"table": 0, "metric": 0, "claim": 0}
    for obj in objects:
        object_type = obj.get("object_type")
        if object_type in counts:
            counts[object_type] += 1
    return counts


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    facet_count = 0
    facets_with_objects = 0
    empty_facets = []
    for row in rows:
        for need in row.get("object_evidence_needs", []):
            facet_count += 1
            if need.get("target_object_refs"):
                facets_with_objects += 1
            else:
                empty_facets.append({"query_id": row.get("query_id"), "facet": need.get("facet")})
    return {
        "query_count": len(rows),
        "facet_count": facet_count,
        "facets_with_object_refs": facets_with_objects,
        "facets_without_object_refs": empty_facets,
    }


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


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().replace(",", "")).strip()


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", value)


if __name__ == "__main__":
    main()
