from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.contracts import (  # noqa: E402
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.cross_encoder import (  # noqa: E402
    cross_encoder_model_identity,
    load_local_qwen3_reranker,
    score_qwen3_reranker_pairs,
)
from retrieval.financial_candidate_ranking import (  # noqa: E402
    candidate_financial_features,
)
from retrieval.hybrid_candidate_runtime import (  # noqa: E402
    LocalQwenHybridCandidateRuntime,
)
from retrieval.query_atom_shadow import (  # noqa: E402
    compile_atom_lane,
    load_query_atoms,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
)


AUTHORITY_SCHEMA_VERSION = (
    "fin_ia_s1c_cross_encoder_safety_shadow_authority_v1_0"
)
RESULT_SCHEMA_VERSION = "fin_ia_s1c_cross_encoder_safety_shadow_result_v1_0"


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


def _sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def _validate_authority(authority: Mapping[str, Any]) -> dict[str, Path]:
    if authority.get("schema_version") != AUTHORITY_SCHEMA_VERSION:
        raise ValueError("cross_encoder_safety_authority_schema_invalid")
    if authority.get("status") != (
        "zero_call_structural_successor_after_failed_lexicographic_ranker"
    ):
        raise ValueError("cross_encoder_safety_authority_status_invalid")
    expected = {
        "network_calls_authorized": False,
        "generation_model_calls_authorized": False,
        "local_embedding_and_reranker_inference_authorized": True,
        "runtime_promotion_authorized": False,
        "candidate_is_not_evidence": True,
        "numeric_authority": False,
        "s1_complete_claimed": False,
    }
    if authority.get("authority") != expected:
        raise ValueError("cross_encoder_safety_authority_invalid")
    bindings = authority["bound_inputs"]
    paths = {
        key: _resolve(bindings[f"{key}_ref"])
        for key in ("runtime_policy", "qrels", "kernel", "route_policy")
    }
    for key, path in paths.items():
        if _sha256_lf(path) != str(bindings[f"{key}_sha256_lf"]):
            raise ValueError(f"cross_encoder_safety_binding_drift:{key}")
    model = authority["model"]
    identity = cross_encoder_model_identity(
        _resolve(model["local_directory"]),
        model_id=str(model["model_id"]),
    )
    if identity["model_digest"] != str(bindings["qwen_reranker_model_digest"]):
        raise ValueError("cross_encoder_safety_model_drift")
    return paths


def _complete_surface(features: Mapping[str, Any]) -> int:
    return int(features["surface_integrity"]["tier"])


def _label(atom: Any, object_id: str) -> str:
    if object_id in atom.positive_object_ids:
        return "positive"
    if object_id in atom.hard_negative_object_ids:
        return "hard_negative"
    if object_id in atom.unjudged_object_ids:
        return "unjudged"
    return "unlabelled"


def _hard_boundary_violations(
    candidates: Sequence[Mapping[str, Any]], request: Any
) -> int:
    target = request.target_entities[0]
    sources = {value.upper() for value in request.acceptable_sources}
    fiscal_years = set(request.period.fiscal_years)
    count = 0
    for row in candidates:
        count += str(row["ticker"]).upper() != target
        count += date.fromisoformat(str(row["publication_date"])) > request.research_as_of
        count += str(row["source_type"]).upper() not in sources
        count += bool(fiscal_years and row.get("fiscal_year") not in fiscal_years)
    return int(count)


def _evaluate(
    candidates: Sequence[Mapping[str, Any]],
    *,
    atom: Any,
    request: Any,
    top_k: int,
) -> dict[str, Any]:
    positive_ranks = [
        index
        for index, row in enumerate(candidates, start=1)
        if str(row["compiled_object_id"]) in atom.positive_object_ids
    ]
    return {
        "positive_target_available": bool(atom.positive_object_ids),
        "best_positive_rank": min(positive_ranks, default=None),
        "positive_target_in_top_k": bool(
            positive_ranks and min(positive_ranks) <= top_k
        ),
        "reciprocal_rank": round(1.0 / min(positive_ranks), 12)
        if positive_ranks
        else 0.0,
        "hard_negative_in_top5_count": sum(
            str(row["compiled_object_id"]) in atom.hard_negative_object_ids
            for row in candidates[:5]
        ),
        "known_parser_fragment_in_top5_count": sum(
            str(row["model_text"]).lstrip().startswith("-based ")
            for row in candidates[:5]
        ),
        "hard_boundary_violation_count": _hard_boundary_violations(
            candidates, request
        ),
        "candidate_authority_violation_count": sum(
            row.get("candidate_not_evidence") is not True
            or row.get("numeric_authority") is not False
            for row in candidates
        ),
        "top_candidates": [
            {
                "rank": index,
                "compiled_object_id": str(row["compiled_object_id"]),
                "judgement": _label(atom, str(row["compiled_object_id"])),
                "cross_encoder_score": row.get("cross_encoder_score"),
                "ticker": str(row["ticker"]),
                "publication_date": str(row["publication_date"]),
                "source_type": str(row["source_type"]),
                "object_kind": str(row["object_kind"]),
                "text_excerpt": str(row["model_text"])[:280],
                "financial_safety": row.get("financial_safety"),
            }
            for index, row in enumerate(candidates[:top_k], start=1)
        ],
    }


def _aggregate(rows: Sequence[Mapping[str, Any]], route: str) -> dict[str, Any]:
    values = [row[route] for row in rows]
    positives = [row for row in values if row["positive_target_available"]]
    return {
        "positive_atom_count": len(positives),
        "positive_target_in_top10_count": sum(
            row["positive_target_in_top_k"] for row in positives
        ),
        "positive_target_in_top10_rate": round(
            sum(row["positive_target_in_top_k"] for row in positives)
            / len(positives),
            6,
        )
        if positives
        else None,
        "mean_reciprocal_rank": round(
            sum(float(row["reciprocal_rank"]) for row in positives)
            / len(positives),
            6,
        )
        if positives
        else None,
        "hard_negative_in_top5_count": sum(
            int(row["hard_negative_in_top5_count"]) for row in values
        ),
        "known_parser_fragment_in_top5_count": sum(
            int(row["known_parser_fragment_in_top5_count"]) for row in values
        ),
        "hard_boundary_violation_count": sum(
            int(row["hard_boundary_violation_count"]) for row in values
        ),
        "candidate_authority_violation_count": sum(
            int(row["candidate_authority_violation_count"]) for row in values
        ),
    }


def run(authority_path: Path) -> dict[str, Any]:
    authority = _read_json(authority_path)
    paths = _validate_authority(authority)
    kernel = load_financial_research_kernel(_read_json(paths["kernel"]))
    route_policy = load_query_object_fact_route_policy(
        _read_json(paths["route_policy"]), kernel
    )
    atoms = load_query_atoms(_read_json(paths["qrels"]))
    requests = [load_evidence_request(atom.request_payload, kernel) for atom in atoms]
    lanes = [compile_atom_lane(atom, kernel)[1] for atom in atoms]
    runtime = LocalQwenHybridCandidateRuntime.from_policy(
        ROOT, _read_json(paths["runtime_policy"])
    )
    comparisons = runtime.compare_financial_ranking(
        requests,
        kernel=kernel,
        route_policy=route_policy,
    )
    baseline_results = [row["legacy"] for row in comparisons]

    model = authority["model"]
    reranker = load_local_qwen3_reranker(
        _resolve(model["local_directory"]),
        maximum_sequence_length=int(model["maximum_sequence_length"]),
        instruction=str(model["instruction"]),
    )
    all_pairs: list[tuple[str, str]] = []
    offsets: list[tuple[int, int]] = []
    for lane, result in zip(lanes, baseline_results):
        start = len(all_pairs)
        all_pairs.extend(
            (lane.semantic_query, str(row["model_text"]))
            for row in result["candidates"]
        )
        offsets.append((start, len(all_pairs)))
    scores = score_qwen3_reranker_pairs(
        reranker,
        all_pairs,
        batch_size=int(model["batch_size"]),
    )

    rows: list[dict[str, Any]] = []
    top_k = int(authority["ranking_contract"]["top_k"])
    for atom, request, lane, baseline, offset in zip(
        atoms, requests, lanes, baseline_results, offsets
    ):
        candidates = [dict(row) for row in baseline["candidates"]]
        for row, score in zip(candidates, scores[offset[0] : offset[1]]):
            features = candidate_financial_features(
                {
                    "compiled_object_id": row["compiled_object_id"],
                    "object_kind": row["object_kind"],
                    "model_text": row["model_text"],
                    "base_object_view": row,
                },
                lane=lane,
                route_ranks=row["route_ranks"],
            )
            row["cross_encoder_score"] = float(score)
            row["financial_safety"] = features
        reranked = sorted(
            candidates,
            key=lambda row: (
                -_complete_surface(row["financial_safety"]),
                -float(row["cross_encoder_score"]),
                str(row["compiled_object_id"]),
            ),
        )
        rows.append(
            {
                "atom_id": atom.atom_id,
                "case_key": request.case_key,
                "target_entity": request.target_entities[0],
                "facet_id": request.requested_facet_ids[0],
                "baseline": _evaluate(
                    baseline["candidates"],
                    atom=atom,
                    request=request,
                    top_k=top_k,
                ),
                "cross_encoder_safety": _evaluate(
                    reranked,
                    atom=atom,
                    request=request,
                    top_k=top_k,
                ),
            }
        )
    baseline = _aggregate(rows, "baseline")
    successor = _aggregate(rows, "cross_encoder_safety")
    gates = authority["decision_gates"]
    gate_results = {
        "positive_target_in_top10_not_worse": successor[
            "positive_target_in_top10_count"
        ]
        >= baseline["positive_target_in_top10_count"],
        "mean_reciprocal_rank_not_worse": successor["mean_reciprocal_rank"]
        >= baseline["mean_reciprocal_rank"],
        "hard_negative_in_top5_not_worse": successor[
            "hard_negative_in_top5_count"
        ]
        <= baseline["hard_negative_in_top5_count"],
        "known_parser_fragment_in_top5": successor[
            "known_parser_fragment_in_top5_count"
        ]
        <= int(gates["known_parser_fragment_in_top5_maximum"]),
        "hard_filter_boundary": successor["hard_boundary_violation_count"]
        <= int(gates["hard_boundary_violation_maximum"]),
        "candidate_authority_boundary": successor[
            "candidate_authority_violation_count"
        ]
        <= int(gates["candidate_authority_violation_maximum"]),
    }
    decision = (
        "development_pass_requires_observed_validation_and_frozen_test_precut"
        if all(gate_results.values())
        else "development_failed_keep_current_runtime_and_disposition_without_retry"
    )
    unsigned = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "completed_zero_network_local_cross_encoder_shadow",
        "recorded_at": "2026-08-13",
        "experiment_id": str(authority["experiment_id"]),
        "authority_ref": _relative(authority_path),
        "authority_sha256_lf": _sha256_lf(authority_path),
        "summary": {"baseline": baseline, "cross_encoder_safety": successor},
        "gate_results": gate_results,
        "decision": decision,
        "rows": rows,
        "authority": dict(authority["authority"]),
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def _compact(result: Mapping[str, Any], full_path: Path) -> dict[str, Any]:
    return {
        "schema_version": "fin_ia_s1c_cross_encoder_safety_shadow_summary_v1_0",
        "status": result["status"],
        "recorded_at": result["recorded_at"],
        "experiment_id": result["experiment_id"],
        "authority_ref": result["authority_ref"],
        "authority_sha256_lf": result["authority_sha256_lf"],
        "full_result_ref": _relative(full_path),
        "full_result_sha256_lf": _sha256_lf(full_path),
        "summary": result["summary"],
        "gate_results": result["gate_results"],
        "decision": result["decision"],
        "result_digest": result["result_digest"],
        "authority": result["authority"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--authority",
        default="configs/retrieval/fin_ia_0_1_3_s1c_cross_encoder_safety_shadow_authority_v1_0.json",
    )
    parser.add_argument(
        "--full-output-root",
        default="data/workbench_private/fin_0_1_3_s1c_cross_encoder_safety_shadow/v1",
    )
    parser.add_argument(
        "--summary-output",
        default="configs/retrieval/fin_ia_0_1_3_s1c_cross_encoder_safety_shadow_result_v1_0.json",
    )
    args = parser.parse_args()
    result = run(_resolve(args.authority))
    full_root = _resolve(args.full_output_root)
    full_path = full_root / f"full_result_{result['result_digest']}.json"
    _write_json(full_path, result)
    summary = _compact(result, full_path)
    summary_path = _resolve(args.summary_output)
    _write_json(summary_path, summary)
    print(
        json.dumps(
            {
                "summary_output": _relative(summary_path),
                "full_output": _relative(full_path),
                "summary": result["summary"],
                "gate_results": result["gate_results"],
                "decision": result["decision"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
