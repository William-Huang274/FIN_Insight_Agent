from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.cross_encoder import (  # noqa: E402
    cross_encoder_model_identity,
    load_local_cross_encoder,
    load_local_qwen3_reranker,
    score_cross_encoder_pairs,
    score_qwen3_reranker_pairs,
)
from retrieval.embedding_runtime import (  # noqa: E402
    load_or_build_bge_m3_cache,
    load_or_build_qwen_embedding_cache,
    local_model_identity,
    sha256_file,
)
from retrieval.object_retrieval_comparison import load_compiled_objects  # noqa: E402
from retrieval.query_atom_shadow import (  # noqa: E402
    aggregate_evidence_role_metrics,
    aggregate_query_atom_results,
    compile_atom_lane,
    evaluate_controlled_evidence_roles,
    evaluate_controlled_reranker,
    evaluate_query_atom,
    label_eligibility_rows,
    load_query_atoms,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.route_compiler import load_query_object_fact_route_policy  # noqa: E402


SCHEMA_FAMILIES = {
    "fin_ia_s1c_runtime_query_atom_model_shadow_policy_v1_0": (
        "fin_ia_s1c_runtime_query_atom_model_shadow_result_v1_0",
        "fin_ia_s1c_runtime_query_atom_model_shadow_summary_v1_0",
        False,
    ),
    "fin_ia_s1c_runtime_query_atom_model_shadow_policy_v1_1": (
        "fin_ia_s1c_runtime_query_atom_model_shadow_result_v1_1",
        "fin_ia_s1c_runtime_query_atom_model_shadow_summary_v1_1",
        True,
    ),
}


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"jsonl_object_required:{path.name}:{line_number}")
            rows.append(value)
    return rows


def _sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _validate_bindings(policy: Mapping[str, Any]) -> dict[str, Path]:
    bindings = policy["bound_inputs"]
    paths = {
        "query_atom_eval": _resolve(bindings["query_atom_eval_ref"]),
        "kernel": _resolve(bindings["kernel_ref"]),
        "route_policy": _resolve(bindings["route_policy_ref"]),
        "compiled_objects": _resolve(bindings["compiled_objects_ref"]),
    }
    for key in ("query_atom_eval", "kernel", "route_policy"):
        observed = _sha256_lf(paths[key])
        expected = str(bindings[f"{key}_sha256_lf"])
        if observed != expected:
            raise ValueError(f"runtime_query_atom_shadow_binding_drift:{key}")
    if sha256_file(paths["compiled_objects"]) != str(
        bindings["compiled_objects_sha256"]
    ):
        raise ValueError("runtime_query_atom_shadow_binding_drift:compiled_objects")
    return paths


def _empty_cuda() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def run(*, policy_path: Path, cache_root: Path) -> dict[str, Any]:
    policy = _read_json(policy_path)
    schema_family = SCHEMA_FAMILIES.get(str(policy.get("schema_version") or ""))
    if schema_family is None:
        raise ValueError("runtime_query_atom_shadow_policy_invalid")
    result_schema_version, _, controlled_diagnostic_enabled = schema_family
    paths = _validate_bindings(policy)
    kernel = load_financial_research_kernel(_read_json(paths["kernel"]))
    route_policy = load_query_object_fact_route_policy(
        _read_json(paths["route_policy"]), kernel
    )
    atom_payload = _read_json(paths["query_atom_eval"])
    atoms = load_query_atoms(atom_payload)
    compiled = load_compiled_objects(_read_jsonl(paths["compiled_objects"]))
    objects = list(compiled)
    object_sha256 = sha256_file(paths["compiled_objects"])

    models = policy["models"]
    bge_embedding_dir = _resolve(models["bge_embedding"]["local_directory"])
    qwen_embedding_dir = _resolve(models["qwen_embedding"]["local_directory"])
    bge_reranker_dir = _resolve(models["bge_reranker"]["local_directory"])
    qwen_reranker_dir = _resolve(models["qwen_reranker"]["local_directory"])
    bge_embedding_identity = local_model_identity(bge_embedding_dir, "BAAI/bge-m3")
    qwen_embedding_identity = local_model_identity(
        qwen_embedding_dir, "Qwen/Qwen3-Embedding-0.6B"
    )
    bge_reranker_identity = cross_encoder_model_identity(bge_reranker_dir)
    qwen_reranker_identity = cross_encoder_model_identity(
        qwen_reranker_dir, model_id="Qwen/Qwen3-Reranker-0.6B"
    )
    bindings = policy["bound_inputs"]
    identities = {
        "bge_embedding": bge_embedding_identity,
        "qwen_embedding": qwen_embedding_identity,
        "bge_reranker": bge_reranker_identity,
        "qwen_reranker": qwen_reranker_identity,
    }
    for key, identity in identities.items():
        if identity["model_digest"] != str(bindings[f"{key}_model_digest"]):
            raise ValueError(f"runtime_query_atom_shadow_model_drift:{key}")

    compiled_lanes = [compile_atom_lane(atom, kernel)[1] for atom in atoms]

    bge_dense, _, bge_cache, bge_runtime = load_or_build_bge_m3_cache(
        objects=objects,
        object_sha256=object_sha256,
        model_dir=bge_embedding_dir,
        model_identity=bge_embedding_identity,
        cache_dir=cache_root / "bge_m3_v1",
        maximum_sequence_length=int(models["bge_embedding"]["maximum_sequence_length"]),
        batch_size=int(models["bge_embedding"]["batch_size"]),
    )
    bge_query_started = time.perf_counter()
    bge_query_embeddings = np.asarray(
        bge_runtime.encode(
            [lane.semantic_query for lane in compiled_lanes],
            batch_size=4,
            max_length=int(models["bge_embedding"]["maximum_sequence_length"]),
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )["dense_vecs"],
        dtype=np.float32,
    )
    bge_query_seconds = time.perf_counter() - bge_query_started
    del bge_runtime
    _empty_cuda()

    qwen_dense, qwen_cache, qwen_runtime = load_or_build_qwen_embedding_cache(
        objects=objects,
        object_sha256=object_sha256,
        model_dir=qwen_embedding_dir,
        model_identity=qwen_embedding_identity,
        cache_dir=cache_root / "qwen3_embedding_0_6b_v1",
        maximum_sequence_length=int(models["qwen_embedding"]["maximum_sequence_length"]),
        batch_size=int(models["qwen_embedding"]["batch_size"]),
    )
    qwen_query_started = time.perf_counter()
    qwen_query_embeddings = np.asarray(
        qwen_runtime.encode(
            [lane.semantic_query for lane in compiled_lanes],
            batch_size=8,
            prompt=str(models["qwen_embedding"]["query_instruction"]),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ),
        dtype=np.float32,
    )
    qwen_query_seconds = time.perf_counter() - qwen_query_started
    del qwen_runtime
    _empty_cuda()

    candidate_contract = policy["candidate_contract"]
    # Build the shared candidate unions before either reranker is loaded. This
    # keeps both rerankers blind to labels and guarantees exact pool parity.
    candidate_rows: list[dict[str, Any]] = []
    for index, (atom, lane) in enumerate(zip(atoms, compiled_lanes)):
        row = evaluate_query_atom(
            atom=atom,
            lane=lane,
            route_policy=route_policy,
            objects=objects,
            document_embeddings=bge_dense,
            query_embedding=bge_query_embeddings[index],
            additional_dense_routes={
                "qwen3_embedding_0_6b_dense": (
                    qwen_dense,
                    qwen_query_embeddings[index],
                )
            },
            reranker_scorers={},
            first_stage_limit=max(
                int(candidate_contract["bge_first_stage_limit"]),
                int(candidate_contract["qwen_first_stage_limit"]),
            ),
            candidate_union_limit=int(
                candidate_contract["reranker_candidate_union_limit"]
            ),
            top_k=int(candidate_contract["top_k"]),
        )
        candidate_rows.append(row)

    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    label_audits = [
        label_eligibility_rows(
            objects,
            atom=atom,
            lane=lane,
            route_policy=route_policy,
        )
        for atom, lane in zip(atoms, compiled_lanes)
    ]
    diagnostic_pool_ids: list[list[str]] = []
    for row, audit in zip(candidate_rows, label_audits):
        ids = list(row["candidate_union_ids"])
        if controlled_diagnostic_enabled:
            for label in audit:
                object_id = str(label["compiled_object_id"])
                if (
                    label["judgement"] in {"positive", "hard_negative"}
                    and label["eligible"] is True
                    and object_id not in ids
                ):
                    ids.append(object_id)
        diagnostic_pool_ids.append(ids)
    pair_manifests = [
        [
            (lane.semantic_query, str(objects_by_id[object_id]["model_text"]))
            for object_id in object_ids
        ]
        for object_ids, lane in zip(diagnostic_pool_ids, compiled_lanes)
    ]

    bge_reranker = load_local_cross_encoder(
        bge_reranker_dir,
        maximum_sequence_length=int(models["bge_reranker"]["maximum_sequence_length"]),
    )
    bge_started = time.perf_counter()
    bge_scores = [
        score_cross_encoder_pairs(
            bge_reranker,
            pairs,
            batch_size=int(models["bge_reranker"]["batch_size"]),
            progress_every=None,
        )
        for pairs in pair_manifests
    ]
    bge_rerank_seconds = time.perf_counter() - bge_started
    del bge_reranker
    _empty_cuda()

    qwen_reranker = load_local_qwen3_reranker(
        qwen_reranker_dir,
        maximum_sequence_length=int(models["qwen_reranker"]["maximum_sequence_length"]),
        instruction=str(models["qwen_reranker"]["instruction"]),
    )
    qwen_started = time.perf_counter()
    qwen_scores = [
        score_qwen3_reranker_pairs(
            qwen_reranker,
            pairs,
            batch_size=int(models["qwen_reranker"]["batch_size"]),
        )
        for pairs in pair_manifests
    ]
    qwen_rerank_seconds = time.perf_counter() - qwen_started
    del qwen_reranker
    _empty_cuda()

    results: list[dict[str, Any]] = []
    for index, (atom, lane) in enumerate(zip(atoms, compiled_lanes)):
        natural_count = len(candidate_rows[index]["candidate_union_ids"])
        row = evaluate_query_atom(
                atom=atom,
                lane=lane,
                route_policy=route_policy,
                objects=objects,
                document_embeddings=bge_dense,
                query_embedding=bge_query_embeddings[index],
                additional_dense_routes={
                    "qwen3_embedding_0_6b_dense": (
                        qwen_dense,
                        qwen_query_embeddings[index],
                    )
                },
                reranker_scorers={
                    "bge_reranker_v2_m3": (
                        lambda pairs, scores=bge_scores[index][
                            :natural_count
                        ]: scores
                    ),
                    "qwen3_reranker_0_6b": (
                        lambda pairs, scores=qwen_scores[index][
                            :natural_count
                        ]: scores
                    ),
                },
                first_stage_limit=max(
                    int(candidate_contract["bge_first_stage_limit"]),
                    int(candidate_contract["qwen_first_stage_limit"]),
                ),
                candidate_union_limit=int(
                    candidate_contract["reranker_candidate_union_limit"]
                ),
                top_k=int(candidate_contract["top_k"]),
            )
        row["label_eligibility"] = label_audits[index]
        if controlled_diagnostic_enabled:
            natural_ids = set(row["candidate_union_ids"])
            controlled_ids = diagnostic_pool_ids[index]
            row["diagnostic_judged_pool"] = {
                "pool_contract": (
                    "natural_candidate_union_plus_eligible_pre_registered_"
                    "positive_and_hard_negative_labels"
                ),
                "object_ids": controlled_ids,
                "injected_label_ids": [
                    object_id for object_id in controlled_ids if object_id not in natural_ids
                ],
                "runtime_candidate_pool_unchanged": True,
                "candidate_not_evidence": True,
                "numeric_authority": False,
                "rerankers": {
                    "bge_reranker_v2_m3": evaluate_controlled_reranker(
                        atom=atom,
                        object_ids=controlled_ids,
                        scores=bge_scores[index],
                        top_k=int(candidate_contract["top_k"]),
                    ),
                    "qwen3_reranker_0_6b": evaluate_controlled_reranker(
                        atom=atom,
                        object_ids=controlled_ids,
                        scores=qwen_scores[index],
                        top_k=int(candidate_contract["top_k"]),
                    ),
                },
                "evidence_role": evaluate_controlled_evidence_roles(
                    atom=atom,
                    lane=lane,
                    objects=objects,
                    controlled_object_ids=controlled_ids,
                ),
            }
        results.append(row)
    summary = aggregate_query_atom_results(results)
    summary["first_stage"] = _aggregate_first_stage(results)
    if controlled_diagnostic_enabled:
        controlled_summary = _aggregate_controlled_diagnostic(results)
        summary["controlled_rerankers"] = controlled_summary["rerankers"]
        summary["controlled_evidence_role"] = controlled_summary["evidence_role"]
        summary["label_eligibility"] = controlled_summary["label_eligibility"]
    gates = policy["decision_gates"]
    shared_union_hit_count = sum(
        row["first_stage"]["shared_candidate_union"]["positive_target_in_pool"]
        for row in results
        if row["first_stage"]["shared_candidate_union"]["positive_target_available"]
    )
    positive_atom_count = sum(
        row["first_stage"]["shared_candidate_union"]["positive_target_available"]
        for row in results
    )
    union_rate = (
        shared_union_hit_count / positive_atom_count if positive_atom_count else 0.0
    )
    decision_rerankers = (
        summary["controlled_rerankers"]
        if controlled_diagnostic_enabled
        else summary["rerankers"]
    )
    reranker_credible = {
        route_id: (
            metrics["pairwise_accuracy"] is not None
            and metrics["pairwise_accuracy"]
            >= float(gates["reranker_pairwise_accuracy_minimum"])
        )
        for route_id, metrics in decision_rerankers.items()
    }
    role_metrics = (
        summary["controlled_evidence_role"]
        if controlled_diagnostic_enabled
        else summary["evidence_role"]
    )
    role_credible = (
        role_metrics["positive_compatible_rate"] is not None
        and role_metrics["positive_compatible_rate"]
        >= float(gates["evidence_role_positive_compatibility_minimum"])
        and role_metrics["hard_negative_suppressed_or_abstained_rate"] is not None
        and role_metrics["hard_negative_suppressed_or_abstained_rate"]
        >= float(gates["evidence_role_hard_negative_suppression_minimum"])
    )
    fine_tuning_eligible = (
        role_metrics["positive_count"]
        + role_metrics["hard_negative_count"]
        >= int(gates["minimum_reviewed_relations_before_fine_tuning"])
        and summary["case_count"]
        >= int(gates["minimum_development_cases_before_fine_tuning"])
    )
    unsigned = {
        "schema_version": result_schema_version,
        "status": "runtime_query_atom_model_shadow_complete_no_runtime_promotion",
        "recorded_at": "2026-08-13",
        "experiment_id": str(policy["experiment_id"]),
        "bound_inputs": {
            "policy_ref": _relative(policy_path),
            "policy_sha256_lf": _sha256_lf(policy_path),
            "query_atom_eval_ref": _relative(paths["query_atom_eval"]),
            "query_atom_eval_sha256_lf": _sha256_lf(paths["query_atom_eval"]),
            "kernel_ref": _relative(paths["kernel"]),
            "kernel_sha256_lf": _sha256_lf(paths["kernel"]),
            "route_policy_ref": _relative(paths["route_policy"]),
            "route_policy_sha256_lf": _sha256_lf(paths["route_policy"]),
            "compiled_objects_ref": _relative(paths["compiled_objects"]),
            "compiled_objects_sha256": object_sha256,
        },
        "execution": {
            "model_identities": identities,
            "bge_embedding_cache": bge_cache,
            "qwen_embedding_cache": qwen_cache,
            "bge_query_embedding_seconds": round(bge_query_seconds, 3),
            "qwen_query_embedding_seconds": round(qwen_query_seconds, 3),
            "bge_reranker_seconds": round(bge_rerank_seconds, 3),
            "qwen_reranker_seconds": round(qwen_rerank_seconds, 3),
            "network_calls": 0,
            "generation_model_calls": 0,
            "training_steps": 0,
            "labels_joined_after_candidate_generation_and_scoring": True,
            "same_candidate_union_for_both_rerankers": True,
            "natural_candidate_union_unchanged_by_diagnostic_labels": True,
            "controlled_diagnostic_pool_enabled": controlled_diagnostic_enabled,
        },
        "summary": {
            **summary,
            "positive_target_in_shared_union_rate": round(union_rate, 6),
        },
        "atoms": results,
        "decision": {
            "candidate_union_credible": union_rate
            >= float(gates["positive_target_in_union_minimum_rate"]),
            "reranker_credible": reranker_credible,
            "evidence_role_credible": role_credible,
            "fine_tuning_eligible": fine_tuning_eligible,
            "fine_tuning_authorized": False,
            "runtime_promotion_authorized": False,
            "provisional_first_stage_route": _provisional_first_stage_route(summary),
            "provisional_reranker_route": _provisional_reranker_route(
                summary, reranker_credible
            ),
            "database_lane": {
                "company_financial_fact_mart_built": False,
                "owning_stage": "S2",
                "status": "typed_fact_store_unavailable",
                "hard_gate_before_dell_vertical_slice": True,
                "ranking_model_granted_numeric_authority": False,
            },
        },
        "authority": dict(policy["authority"]),
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def _compact(result: Mapping[str, Any], *, full_path: Path) -> dict[str, Any]:
    compact_atoms = []
    for row in result["atoms"]:
        compact_atoms.append(
            {
                "atom_id": row["atom_id"],
                "case_key": row["case_key"],
                "slot_id": row["slot_id"],
                "facet_id": row["facet_id"],
                "evidence_owner_ticker": row["evidence_owner_ticker"],
                "relationship_direction": row["relationship_direction"],
                "eligible_object_count": row["eligible_object_count"],
                "first_stage": row["first_stage"],
                "rerankers": row["rerankers"],
                "evidence_role_metrics": row["evidence_role"]["metrics"],
                "label_eligibility": row.get("label_eligibility", []),
                "diagnostic_judged_pool": _compact_diagnostic_pool(
                    row.get("diagnostic_judged_pool")
                ),
                "candidate_not_evidence": True,
                "numeric_authority": False,
            }
        )
    unsigned = {
        "schema_version": (
            "fin_ia_s1c_runtime_query_atom_model_shadow_summary_v1_1"
            if result["schema_version"].endswith("v1_1")
            else "fin_ia_s1c_runtime_query_atom_model_shadow_summary_v1_0"
        ),
        "status": result["status"],
        "recorded_at": result["recorded_at"],
        "experiment_id": result["experiment_id"],
        "storage": {
            "full_result_ref": _relative(full_path),
            "full_result_sha256": sha256_file(full_path),
            "full_result_digest": result["result_digest"],
            "tracked_summary_excludes_candidate_union_ids_and_role_rows": True,
        },
        "bound_inputs": result["bound_inputs"],
        "execution": result["execution"],
        "summary": result["summary"],
        "atoms": compact_atoms,
        "decision": result["decision"],
        "authority": result["authority"],
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def _aggregate_first_stage(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    route_ids = sorted(
        {
            route_id
            for row in rows
            for route_id in row["first_stage"]
            if route_id != "shared_candidate_union"
        }
    )
    return {
        route_id: {
            "positive_target_available_count": sum(
                row["first_stage"][route_id]["positive_target_available"]
                for row in rows
            ),
            "positive_target_in_ranking_count": sum(
                row["first_stage"][route_id]["positive_target_in_ranking"]
                for row in rows
            ),
            "positive_target_in_top_k_count": sum(
                row["first_stage"][route_id]["positive_target_in_top_k"]
                for row in rows
            ),
        }
        for route_id in route_ids
    }


def _aggregate_controlled_diagnostic(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    route_ids = sorted(rows[0]["diagnostic_judged_pool"]["rerankers"])
    rerankers: dict[str, Any] = {}
    for route_id in route_ids:
        values = [row["diagnostic_judged_pool"]["rerankers"][route_id] for row in rows]
        comparisons = sum(value["pairwise_comparisons"] for value in values)
        wins = sum(value["pairwise_wins"] for value in values)
        rerankers[route_id] = {
            "atom_count": len(values),
            "positive_target_in_top_k_count": sum(
                value["positive_target_in_top_k"] for value in values
            ),
            "positive_target_available_count": sum(
                value["positive_target_available"] for value in values
            ),
            "pairwise_wins": wins,
            "pairwise_comparisons": comparisons,
            "eligible_pairwise_atom_count": sum(
                bool(value["pairwise_comparisons"]) for value in values
            ),
            "pairwise_accuracy": round(wins / comparisons, 6) if comparisons else None,
        }
    role_rows = [
        item
        for row in rows
        for item in row["diagnostic_judged_pool"]["evidence_role"]["rows"]
    ]
    label_rows = [item for row in rows for item in row["label_eligibility"]]
    return {
        "rerankers": rerankers,
        "evidence_role": aggregate_evidence_role_metrics(role_rows),
        "label_eligibility": {
            "label_count": len(label_rows),
            "eligible_count": sum(item["eligible"] for item in label_rows),
            "excluded_count": sum(not item["eligible"] for item in label_rows),
            "exclusion_reason_counts": {
                reason: sum(item["exclusion_reason"] == reason for item in label_rows)
                for reason in sorted(
                    {
                        str(item["exclusion_reason"])
                        for item in label_rows
                        if item["exclusion_reason"] is not None
                    }
                )
            },
        },
    }


def _provisional_first_stage_route(summary: Mapping[str, Any]) -> str | None:
    values = summary["first_stage"]
    best = max(
        (int(metrics["positive_target_in_top_k_count"]) for metrics in values.values()),
        default=-1,
    )
    winners = sorted(
        route_id
        for route_id, metrics in values.items()
        if int(metrics["positive_target_in_top_k_count"]) == best
    )
    return winners[0] if len(winners) == 1 else None


def _provisional_reranker_route(
    summary: Mapping[str, Any], credible: Mapping[str, bool]
) -> str | None:
    values = summary.get("controlled_rerankers") or summary["rerankers"]
    eligible = [route_id for route_id, accepted in credible.items() if accepted]
    if not eligible:
        return None
    eligible.sort(
        key=lambda route_id: (
            -float(values[route_id]["pairwise_accuracy"]),
            -int(values[route_id]["positive_target_in_top_k_count"]),
            route_id,
        )
    )
    return eligible[0]


def _compact_diagnostic_pool(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return {
        "pool_contract": value["pool_contract"],
        "injected_label_ids": value["injected_label_ids"],
        "runtime_candidate_pool_unchanged": True,
        "candidate_not_evidence": True,
        "numeric_authority": False,
        "rerankers": value["rerankers"],
        "evidence_role_metrics": value["evidence_role"]["metrics"],
    }


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy",
        default="configs/retrieval/fin_ia_0_1_3_s1c_runtime_query_atom_model_shadow_policy_v1_1.json",
    )
    parser.add_argument(
        "--cache-root",
        default="data/workbench_private/fin_0_1_3_s1c_runtime_query_atom_model_shadow/model_cache_v1",
    )
    parser.add_argument(
        "--full-output-root",
        default="data/workbench_private/fin_0_1_3_s1c_runtime_query_atom_model_shadow/v1_1",
    )
    parser.add_argument(
        "--summary-output",
        default="configs/retrieval/fin_ia_0_1_3_s1c_runtime_query_atom_model_shadow_result_v1_1.json",
    )
    args = parser.parse_args()
    result = run(
        policy_path=_resolve(args.policy),
        cache_root=_resolve(args.cache_root),
    )
    full_root = _resolve(args.full_output_root)
    full_path = full_root / f"full_result_{result['result_digest']}.json"
    _write_json(full_path, result)
    summary = _compact(result, full_path=full_path)
    summary_path = _resolve(args.summary_output)
    _write_json(summary_path, summary)
    print(
        json.dumps(
            {
                "summary_output": _relative(summary_path),
                "full_output": _relative(full_path),
                "summary": result["summary"],
                "decision": result["decision"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
