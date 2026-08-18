from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from retrieval.contracts import load_evidence_request  # noqa: E402
from retrieval.evaluation_assets import (  # noqa: E402
    EvaluationInput,
    load_qualification_preregistration,
)
from retrieval.object_retrieval_comparison import (  # noqa: E402
    bm25_rank,
    load_compiled_objects,
)
from retrieval.qualification_runtime import (  # noqa: E402
    load_qualification_runtime_bundle,
)
from retrieval.query_atom_shadow import eligible_request_indices  # noqa: E402
from retrieval.query_plan import compile_query_facet_plan_for_request  # noqa: E402


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"jsonl_object_required:{path.name}:{line_number}")
            rows.append(value)
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
            )
    temporary.replace(path)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _load_inputs(result: Mapping[str, Any]) -> list[EvaluationInput]:
    output: list[EvaluationInput] = []
    for binding in result.get("outputs") or ():
        path = _resolve(str(binding["ref"]))
        output.extend(EvaluationInput.model_validate(row) for row in _read_jsonl(path))
    return output


def _review_candidates(
    *,
    row: EvaluationInput,
    objects: list[dict[str, Any]],
    objects_by_id: Mapping[str, Mapping[str, Any]],
    kernel: Any,
    route_policy: Any,
    per_lane_limit: int,
    review_limit: int,
) -> dict[str, Any]:
    request = load_evidence_request(row.runtime_input["evidence_request"], kernel)
    plan = compile_query_facet_plan_for_request(kernel, request)
    ranks: dict[str, list[int]] = {}
    scores: dict[str, float] = {}
    lane_membership: dict[str, list[str]] = {}
    exclusion_by_lane: dict[str, Mapping[str, int]] = {}
    for lane in plan.lanes:
        eligible, exclusions = eligible_request_indices(
            objects,
            request=request,
            lane=lane,
            route_policy=route_policy,
        )
        ranked = bm25_rank(
            objects,
            eligible,
            lane.lexical_query,
            limit=per_lane_limit,
        )
        exclusion_by_lane[lane.lane_id] = exclusions
        for rank, candidate in enumerate(ranked, 1):
            object_id = candidate.compiled_object_id
            ranks.setdefault(object_id, []).append(rank)
            lane_membership.setdefault(object_id, []).append(lane.facet_id)
            scores[object_id] = scores.get(object_id, 0.0) + 1.0 / (20.0 + rank)

    # This is an evaluator-only discovery surface, not the production ranking.
    # Add exact intent hits so one blended BM25 query cannot hide a potential
    # gold object before independent source review.
    intents = tuple(
        dict.fromkeys(
            str(value).casefold()
            for value in (
                *request.metric_intents,
                *request.product_intents,
            )
            if str(value).strip()
        )
    )
    for object_value in objects:
        base = object_value["base_object_view"]
        if str(base.get("ticker") or "").upper() != request.subject_ticker:
            continue
        if request.period.fiscal_years and int(base.get("fiscal_year") or 0) not in set(
            request.period.fiscal_years
        ):
            continue
        text = str(object_value.get("model_text") or "").casefold()
        hits = [intent for intent in intents if intent in text]
        if hits:
            object_id = str(object_value["compiled_object_id"])
            scores[object_id] = scores.get(object_id, 0.0) + 0.03 * len(hits)
            lane_membership.setdefault(object_id, []).append("exact_intent_discovery")

    ordered = sorted(
        scores,
        key=lambda object_id: (
            -scores[object_id],
            min(ranks.get(object_id, [10**9])),
            object_id,
        ),
    )[:review_limit]
    candidates = []
    for rank, object_id in enumerate(ordered, 1):
        value = objects_by_id[object_id]
        base = value["base_object_view"]
        candidates.append(
            {
                "review_rank": rank,
                "compiled_object_id": object_id,
                "discovery_score": round(scores[object_id], 8),
                "lane_membership": sorted(set(lane_membership.get(object_id, ()))),
                "bm25_lane_ranks": sorted(ranks.get(object_id, ())),
                "object_kind": value["object_kind"],
                "ticker": base.get("ticker"),
                "source_type": base.get("source_type"),
                "fiscal_year": base.get("fiscal_year"),
                "publication_date": base.get("publication_date"),
                "section": base.get("section"),
                "subsection": base.get("subsection"),
                "source_record_id": base.get("source_record_id"),
                "model_text": value.get("model_text"),
                "candidate_not_evidence": True,
                "numeric_authority": False,
            }
        )
    return {
        "schema_version": "fin_ia_s1_vs5_qualification_review_packet_row_v1_0",
        "example_id": row.example_id,
        "split": row.split,
        "question_zh": row.runtime_input["question_zh"],
        "evidence_request_digest": row.runtime_input["query_facet_plan"]["plan_digest"],
        "candidate_count": len(candidates),
        "candidates": candidates,
        "exclusion_by_lane": exclusion_by_lane,
        "authority": {
            "evaluator_only": True,
            "not_runtime_ranking": True,
            "not_gold_until_source_adjudicated": True,
            "model_calls": 0,
            "learned_vector_calls": 0,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a label-free source-review packet for VS5 adjudication."
    )
    parser.add_argument(
        "--preregistration",
        default="eval_sets/fin_0_1_3_s1/qualification_preregistration_v1_0.json",
    )
    parser.add_argument(
        "--overlay",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_runtime_overlay_v1_0.json",
    )
    parser.add_argument(
        "--runtime-result",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_runtime_inputs_result_v1_0.json",
    )
    parser.add_argument("--per-lane-limit", type=int, default=24)
    parser.add_argument("--review-limit", type=int, default=60)
    parser.add_argument(
        "--private-output",
        default="data/workbench_private/fin_0_1_3_s1_vs5_qualification_review/v1_0/review_packet.jsonl",
    )
    parser.add_argument(
        "--public-result",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_review_packet_result_v1_0.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prereg_path = _resolve(args.preregistration)
    overlay_path = _resolve(args.overlay)
    runtime_result_path = _resolve(args.runtime_result)
    prereg = load_qualification_preregistration(prereg_path)
    bundle = load_qualification_runtime_bundle(
        repo_root=ROOT,
        preregistration=prereg,
        overlay_path=overlay_path,
    )
    runtime_result = _read_json(runtime_result_path)
    inputs = _load_inputs(runtime_result)
    compiled_result = _read_json(
        _resolve(
            str(
                _read_json(overlay_path)["bound_inputs"][
                    "compiled_objects_result_ref"
                ]
            )
        )
    )
    object_path = _resolve(str(compiled_result["output_binding"]["objects_ref"]))
    objects = list(load_compiled_objects(_read_jsonl(object_path)))
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    packet = [
        _review_candidates(
            row=row,
            objects=objects,
            objects_by_id=objects_by_id,
            kernel=bundle.kernel,
            route_policy=bundle.route_policy,
            per_lane_limit=args.per_lane_limit,
            review_limit=args.review_limit,
        )
        for row in inputs
    ]
    output_path = _resolve(args.private_output)
    _write_jsonl(output_path, packet)
    public = {
        "schema_version": "fin_ia_s1_vs5_qualification_review_packet_result_v1_0",
        "status": "evaluator_only_source_review_packet_materialized_not_gold",
        "recorded_at": "2026-08-18",
        "bound_inputs": {
            "preregistration_ref": _relative(prereg_path),
            "preregistration_sha256": _sha256(prereg_path),
            "overlay_ref": _relative(overlay_path),
            "overlay_sha256": _sha256(overlay_path),
            "runtime_result_ref": _relative(runtime_result_path),
            "runtime_result_sha256": _sha256(runtime_result_path),
            "compiled_objects_ref": _relative(object_path),
            "compiled_objects_sha256": _sha256(object_path),
        },
        "private_output": {
            "ref": _relative(output_path),
            "sha256": _sha256(output_path),
            "bytes": output_path.stat().st_size,
        },
        "summary": {
            "example_count": len(packet),
            "review_candidate_count": sum(row["candidate_count"] for row in packet),
            "per_example_limit": args.review_limit,
            "model_calls": 0,
            "learned_vector_calls": 0,
            "network_calls": 0,
            "references_created": 0,
        },
        "authority": {
            "runtime_visible": False,
            "final_gold": False,
            "qualification_execution_authorized": False,
        },
    }
    _write_json(_resolve(args.public_result), public)
    print(json.dumps(public["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
