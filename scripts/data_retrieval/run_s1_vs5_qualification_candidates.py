from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
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

from retrieval.candidate_ranking import (  # noqa: E402
    NeedRouteRanking,
    fuse_need_rankings_with_route_floors,
    rank_authority_indices,
    rank_need_intent_alias_routes,
    rank_need_lexical_routes,
    rank_need_metric_row_routes,
    role_guarded_primary_ranking,
    route_membership,
)
from retrieval.contracts import load_evidence_request  # noqa: E402
from retrieval.cross_encoder import (  # noqa: E402
    load_local_cross_encoder,
    load_local_qwen3_reranker,
    score_cross_encoder_pairs,
    score_qwen3_reranker_pairs,
)
from retrieval.cuda_execution import required_cuda_fp16_receipt  # noqa: E402
from retrieval.embedding_runtime import (  # noqa: E402
    load_bge_m3_runtime,
    load_or_build_bge_m3_cache,
    load_or_build_qwen_embedding_cache,
    sparse_weight_matrix,
)
from retrieval.evaluation_assets import (  # noqa: E402
    EvaluationInput,
    load_evaluation_program_manifest,
    load_qualification_preregistration,
)
from retrieval.financial_evidence_shortlist import (  # noqa: E402
    rank_financial_evidence_shortlist,
)
from retrieval.object_retrieval_comparison import (  # noqa: E402
    CandidateScore,
    load_compiled_objects,
)
from retrieval.qualification_execution import (  # noqa: E402
    combined_role_evaluation,
    empty_cuda,
    load_policy_lineage,
    load_score_cache,
    model_identities,
    read_json,
    read_jsonl,
    score_cache_key,
    sha256_file,
    write_json,
    write_score_cache,
)
from retrieval.qualification_cuda_ranking import (  # noqa: E402
    multi_vector_rankings_cuda_fp16,
    rank_need_dense_routes_cuda_fp16,
    rank_need_sparse_routes_cuda_fp16,
)
from retrieval.qualification_ranking import (  # noqa: E402
    aggregate_relevant_pair_scores,
    build_relevant_pair_manifest,
)
from retrieval.qualification_runtime import (  # noqa: E402
    load_qualification_runtime_bundle,
)
from retrieval.query_atom_shadow import eligible_request_indices  # noqa: E402
from retrieval.query_plan import (  # noqa: E402
    canonical_digest,
    compile_query_facet_plan_for_request,
)
from retrieval.retrieval_need import compile_retrieval_needs  # noqa: E402


POLICY_SCHEMA = "fin_ia_s1_vs5_candidate_execution_policy_v1_0"
AUTHORITY_SCHEMA = "fin_ia_s1_vs5_candidate_execution_authority_v1_0"
RAW_SCHEMA = "fin_ia_s1_vs5_candidate_execution_raw_v1_0"
RESULT_SCHEMA = "fin_ia_s1_vs5_candidate_execution_result_v1_0"


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _validate_bound_ref(raw: Mapping[str, Any], key: str) -> Path:
    binding = raw.get(key)
    if not isinstance(binding, Mapping):
        raise ValueError(f"qualification_execution_binding_missing:{key}")
    path = _resolve(str(binding.get("ref") or ""))
    if not path.is_file() or sha256_file(path) != str(binding.get("sha256") or ""):
        raise ValueError(f"qualification_execution_binding_drift:{key}")
    return path


def _git_output(*args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _validate_authority(
    *, policy_path: Path, policy: Mapping[str, Any], authority_path: Path
) -> dict[str, Any]:
    authority = read_json(authority_path)
    if (
        authority.get("schema_version") != AUTHORITY_SCHEMA
        or authority.get("status") != "authorized_exact_once_valid_temporal"
        or authority.get("split") != "valid_temporal"
        or authority.get("max_executions") != 1
        or authority.get("cpu_vector_fallback_allowed") is not False
    ):
        raise ValueError("qualification_candidate_authority_invalid")
    if (
        _resolve(str(authority.get("policy_ref") or "")) != policy_path.resolve()
        or str(authority.get("policy_sha256") or "") != sha256_file(policy_path)
    ):
        raise ValueError("qualification_candidate_authority_policy_drift")
    head = _git_output("rev-parse", "HEAD")
    baseline = str(authority.get("design_baseline_commit") or "")
    if head != baseline:
        ancestor = subprocess.run(
            ("git", "merge-base", "--is-ancestor", baseline, head),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        changed = {
            value.strip()
            for value in _git_output("diff", "--name-only", baseline, head).splitlines()
            if value.strip()
        }
        if ancestor.returncode != 0 or changed != {_relative(authority_path)}:
            raise ValueError("qualification_candidate_authority_commit_drift")
    if _git_output("status", "--porcelain"):
        raise ValueError("qualification_candidate_authority_worktree_not_clean")
    if policy.get("status") != "frozen_before_any_qualification_ranking":
        raise ValueError("qualification_candidate_policy_not_frozen")
    for key in ("raw_output_ref", "public_result_ref"):
        output_path = _resolve(str(authority.get(key) or ""))
        if output_path.exists():
            raise ValueError(f"qualification_candidate_exact_once_output_exists:{key}")
    return authority


def _load_split_inputs(
    *, program_path: Path, split: str
) -> list[EvaluationInput]:
    manifest = load_evaluation_program_manifest(program_path)
    catalogs = [
        row for row in manifest.catalogs if row.split == split and row.status == "active"
    ]
    if len(catalogs) != 1 or catalogs[0].input_asset is None:
        raise ValueError("qualification_candidate_split_catalog_invalid")
    asset = catalogs[0].input_asset
    path = ROOT / asset.ref
    if sha256_file(path) != asset.sha256:
        raise ValueError("qualification_candidate_input_digest_drift")
    return [
        EvaluationInput.model_validate(value)
        for value in read_jsonl(path)
    ]


def _rank_scores(candidate_ids: Sequence[str], scores: Sequence[float]) -> tuple[CandidateScore, ...]:
    if len(candidate_ids) != len(scores):
        raise ValueError("qualification_candidate_score_count_mismatch")
    rows = [CandidateScore(value, float(score)) for value, score in zip(candidate_ids, scores)]
    rows.sort(key=lambda value: (-value.score, value.compiled_object_id))
    return tuple(rows)


def _rank_map(rows: Sequence[CandidateScore]) -> dict[str, int]:
    return {row.compiled_object_id: rank for rank, row in enumerate(rows, 1)}


def _candidate_rows(
    rows: Sequence[CandidateScore], *, maximum: int
) -> list[dict[str, Any]]:
    return [
        {
            "rank": rank,
            "compiled_object_id": row.compiled_object_id,
            "score": float(row.score),
        }
        for rank, row in enumerate(rows[:maximum], 1)
    ]


def _run(
    *,
    policy_path: Path,
    authority_path: Path,
    cache_root: Path,
) -> tuple[dict[str, Any], Path, Path]:
    policy = read_json(policy_path)
    if policy.get("schema_version") != POLICY_SCHEMA:
        raise ValueError("qualification_candidate_policy_schema_invalid")
    authority = _validate_authority(
        policy_path=policy_path, policy=policy, authority_path=authority_path
    )
    split = str(authority["split"])
    bound = policy.get("bound_inputs") or {}
    prereg_path = _validate_bound_ref(bound, "preregistration")
    overlay_path = _validate_bound_ref(bound, "runtime_overlay")
    program_path = _validate_bound_ref(bound, "program_manifest")
    compiled_result_path = _validate_bound_ref(bound, "compiled_objects_result")
    preflight_path = _validate_bound_ref(bound, "cuda_preflight")
    candidate_policy_path = _validate_bound_ref(bound, "candidate_ranking_policy")
    need_policy_path = _validate_bound_ref(bound, "retrieval_need_policy")
    intent_path = _validate_bound_ref(bound, "financial_intent_ontology")
    _validate_bound_ref(bound, "qualification_runtime")
    _validate_bound_ref(bound, "embedding_runtime")
    _validate_bound_ref(bound, "cross_encoder_runtime")
    _validate_bound_ref(bound, "qualification_ranking_runtime")
    _validate_bound_ref(bound, "qualification_execution_runtime")
    _validate_bound_ref(bound, "qualification_cuda_ranking_runtime")
    _validate_bound_ref(bound, "qualification_candidate_runner")

    preflight = read_json(preflight_path)
    if (
        preflight.get("status") != "cuda_fp16_eligible_not_execution_authority"
        or preflight["execution_contract"]["cpu_vector_fallback_allowed"] is not False
    ):
        raise ValueError("qualification_candidate_cuda_preflight_invalid")
    receipt = required_cuda_fp16_receipt(
        purpose=f"S1 VS5 {split} embedding and reranking"
    )
    if receipt["device_name"] != preflight["cuda_execution_receipt"]["device_name"]:
        raise ValueError("qualification_candidate_cuda_device_drift")

    prereg = load_qualification_preregistration(prereg_path)
    bundle = load_qualification_runtime_bundle(
        repo_root=ROOT, preregistration=prereg, overlay_path=overlay_path
    )
    inputs = _load_split_inputs(program_path=program_path, split=split)
    compiled_result = read_json(compiled_result_path)
    object_path = _resolve(str(compiled_result["output_binding"]["objects_ref"]))
    if sha256_file(object_path) != str(
        compiled_result["output_binding"]["objects_sha256"]
    ):
        raise ValueError("qualification_candidate_object_digest_drift")
    objects = list(load_compiled_objects(read_jsonl(object_path)))
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    object_digest = sha256_file(object_path)

    base_candidate_policy = load_policy_lineage(candidate_policy_path, repo_root=ROOT)
    model_policy = base_candidate_policy["models"]
    expected_model_digests = {
        key: str(value["model_digest"]) for key, value in preflight["models"].items()
    }
    identities, model_paths = model_identities(
        model_policy=model_policy, expected_digests=expected_model_digests
    )
    need_policy = read_json(need_policy_path)
    intent_ontology = read_json(intent_path)
    contract = policy["candidate_contract"]

    units: list[dict[str, Any]] = []
    propositions: list[dict[str, Any]] = []
    all_needs = []
    input_by_id = {row.example_id: row for row in inputs}
    regenerated = {row.example_id: row for row in bundle.inputs_by_split[split]}
    if set(input_by_id) != set(regenerated):
        raise ValueError("qualification_candidate_runtime_input_join_drift")
    for row in inputs:
        if row.model_dump(mode="json") != regenerated[row.example_id].model_dump(mode="json"):
            raise ValueError(f"qualification_candidate_runtime_input_drift:{row.example_id}")
        runtime = row.runtime_input
        request = load_evidence_request(runtime["evidence_request"], bundle.kernel)
        plan = compile_query_facet_plan_for_request(bundle.kernel, request)
        if plan.plan_digest != str(runtime["query_facet_plan"]["plan_digest"]):
            raise ValueError(f"qualification_candidate_query_plan_drift:{row.example_id}")
        prop_units = []
        start = len(all_needs)
        for lane in plan.lanes:
            lane_request = replace(request, requested_facet_ids=(lane.facet_id,))
            need_set = compile_retrieval_needs(
                request=lane_request,
                lane=lane,
                policy=need_policy,
                intent_ontology=intent_ontology,
            )
            eligible, exclusions = eligible_request_indices(
                objects,
                request=lane_request,
                lane=lane,
                route_policy=bundle.route_policy,
            )
            rankable, projection_only = rank_authority_indices(
                objects,
                eligible,
                allowed_object_kinds=contract["rank_authority_object_kinds"],
            )
            unit = {
                "example_id": row.example_id,
                "request": lane_request,
                "lane": lane,
                "need_set": need_set,
                "eligible": eligible,
                "rankable": rankable,
                "exclusions": exclusions,
                "projection_only": projection_only,
                "query_slice": slice(len(all_needs), len(all_needs) + len(need_set.needs)),
            }
            units.append(unit)
            prop_units.append(unit)
            all_needs.extend(need_set.needs)
        propositions.append(
            {
                "input": row,
                "request": request,
                "units": prop_units,
                "query_slice": slice(start, len(all_needs)),
            }
        )

    maximum_need_count = int(contract["maximum_relevant_needs_per_candidate"])
    predicted_pair_maximum = sum(
        int(contract["reranker_pool_limit"]) * maximum_need_count
        for _ in propositions
    )
    if predicted_pair_maximum > int(
        policy["token_budget_basis"]["reranker_per_model"]["maximum_pair_count"]
    ):
        raise ValueError("qualification_candidate_reranker_budget_understated")
    if predicted_pair_maximum > int(
        authority["maximum_reranker_pairs_per_model"]
    ):
        raise ValueError("qualification_candidate_authority_pair_budget_understated")

    cache_identity = f"{object_digest[:16]}_{identities['bge_embedding']['model_digest'][:16]}"
    bge_dense, bge_sparse, bge_cache, bge_runtime = load_or_build_bge_m3_cache(
        objects=objects,
        object_sha256=object_digest,
        model_dir=model_paths["bge_embedding"],
        model_identity=identities["bge_embedding"],
        cache_dir=cache_root / cache_identity / "bge_m3",
        maximum_sequence_length=int(model_policy["bge_embedding"]["maximum_sequence_length"]),
        batch_size=int(model_policy["bge_embedding"]["batch_size"]),
    )
    started = time.perf_counter()
    bge_queries = bge_runtime.encode(
        [need.semantic_query for need in all_needs],
        batch_size=int(model_policy["bge_embedding"]["batch_size"]),
        max_length=int(model_policy["bge_embedding"]["maximum_sequence_length"]),
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=True,
    )
    bge_query_seconds = time.perf_counter() - started
    bge_query_dense = np.asarray(bge_queries["dense_vecs"], dtype=np.float32)
    bge_query_sparse = sparse_weight_matrix(
        bge_queries["lexical_weights"], width=int(bge_sparse.shape[1])
    )
    bge_query_multi = list(bge_queries["colbert_vecs"])
    del bge_runtime
    empty_cuda()

    qwen_cache_identity = (
        f"{object_digest[:16]}_{identities['qwen_embedding']['model_digest'][:16]}"
    )
    qwen_dense, qwen_cache, qwen_runtime = load_or_build_qwen_embedding_cache(
        objects=objects,
        object_sha256=object_digest,
        model_dir=model_paths["qwen_embedding"],
        model_identity=identities["qwen_embedding"],
        cache_dir=cache_root / qwen_cache_identity / "qwen3_embedding",
        maximum_sequence_length=int(model_policy["qwen_embedding"]["maximum_sequence_length"]),
        batch_size=int(model_policy["qwen_embedding"]["batch_size"]),
    )
    started = time.perf_counter()
    qwen_query_dense = np.asarray(
        qwen_runtime.encode(
            [need.semantic_query for need in all_needs],
            batch_size=int(model_policy["qwen_embedding"]["batch_size"]),
            prompt=str(model_policy["qwen_embedding"]["query_instruction"]),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ),
        dtype=np.float32,
    )
    qwen_query_seconds = time.perf_counter() - started
    del qwen_runtime
    empty_cuda()

    per_need_limit = int(contract["first_stage_per_need_limit"])
    union_limit = int(contract["proposition_candidate_union_limit"])
    floors = contract["candidate_union_route_minimum_per_need"]
    proposition_runtime: list[dict[str, Any]] = []
    for proposition in propositions:
        all_rankings: list[NeedRouteRanking] = []
        lane_rows = []
        for unit in proposition["units"]:
            needs = unit["need_set"].needs
            query_slice = unit["query_slice"]
            rankings = [
                *rank_need_lexical_routes(
                    objects=objects,
                    eligible_indices=unit["rankable"],
                    needs=needs,
                    per_need_limit=per_need_limit,
                ),
                *rank_need_metric_row_routes(
                    objects=objects,
                    eligible_indices=unit["rankable"],
                    needs=needs,
                    per_need_limit=per_need_limit,
                ),
                *rank_need_intent_alias_routes(
                    objects=objects,
                    eligible_indices=unit["rankable"],
                    needs=needs,
                    per_need_limit=per_need_limit,
                ),
                *rank_need_dense_routes_cuda_fp16(
                    route_id="bge_m3_dense",
                    objects=objects,
                    eligible_indices=unit["rankable"],
                    needs=needs,
                    document_embeddings=bge_dense,
                    query_embeddings=bge_query_dense[query_slice],
                    per_need_limit=per_need_limit,
                ),
                *rank_need_sparse_routes_cuda_fp16(
                    route_id="bge_m3_learned_sparse",
                    objects=objects,
                    eligible_indices=unit["rankable"],
                    needs=needs,
                    document_sparse=bge_sparse,
                    query_sparse=bge_query_sparse[query_slice],
                    per_need_limit=per_need_limit,
                ),
                *rank_need_dense_routes_cuda_fp16(
                    route_id="qwen3_embedding_0_6b_dense",
                    objects=objects,
                    eligible_indices=unit["rankable"],
                    needs=needs,
                    document_embeddings=qwen_dense,
                    query_embeddings=qwen_query_dense[query_slice],
                    per_need_limit=per_need_limit,
                ),
            ]
            all_rankings.extend(rankings)
            lane_rows.append(
                {
                    "lane": unit["lane"],
                    "request": unit["request"],
                    "needs": needs,
                    "hard_eligible_object_count": int(unit["eligible"].size),
                    "rank_authority_object_count": int(unit["rankable"].size),
                    "exclusion_counts": unit["exclusions"],
                    "projection_only_counts": unit["projection_only"],
                }
            )
        combined = fuse_need_rankings_with_route_floors(
            all_rankings,
            maximum=union_limit,
            route_minimum_per_need=floors,
            reciprocal_rank_constant=int(contract["reciprocal_rank_constant"]),
        )
        candidate_ids = [value.compiled_object_id for value in combined]
        if not candidate_ids:
            raise ValueError(
                f"qualification_candidate_union_empty:{proposition['input'].example_id}"
            )
        proposition_runtime.append(
            {
                **proposition,
                "lane_rows": lane_rows,
                "first_stage_rankings": all_rankings,
                "combined": combined,
                "candidate_ids": candidate_ids,
            }
        )

    bge_runtime = load_bge_m3_runtime(model_paths["bge_embedding"])
    pair_manifests = []
    pair_bindings = []
    pair_slices = []
    for proposition in proposition_runtime:
        rerank_ids = proposition["candidate_ids"][: int(contract["reranker_pool_limit"])]
        prop_slice = proposition["query_slice"]
        multi_rows = multi_vector_rankings_cuda_fp16(
            runtime=bge_runtime,
            query_vectors=bge_query_multi[prop_slice],
            needs=all_needs[prop_slice],
            candidate_ids=rerank_ids[: int(contract["multi_vector_pool_limit"])],
            objects_by_id=objects_by_id,
            maximum_sequence_length=int(model_policy["bge_embedding"]["maximum_sequence_length"]),
            batch_size=int(model_policy["bge_embedding"]["batch_size"]),
        )
        all_membership_rankings = [*proposition["first_stage_rankings"], *multi_rows]
        membership = route_membership(all_membership_rankings, rerank_ids)
        needs = all_needs[prop_slice]
        needs_by_id = {need.need_id: need for need in needs}
        pairs, bindings = build_relevant_pair_manifest(
            candidate_ids=rerank_ids,
            route_membership_by_id=membership,
            needs_by_id=needs_by_id,
            objects_by_id=objects_by_id,
            maximum_needs_per_candidate=maximum_need_count,
        )
        start = len(pair_manifests)
        pair_manifests.extend(pairs)
        pair_bindings.extend(bindings)
        pair_slices.append(slice(start, len(pair_manifests)))
        proposition.update(
            {
                "rerank_ids": rerank_ids,
                "multi_vector_rankings": multi_rows,
                "route_membership": membership,
                "needs_by_id": needs_by_id,
            }
        )
    del bge_runtime
    empty_cuda()

    if len(pair_manifests) > int(
        policy["token_budget_basis"]["reranker_per_model"]["maximum_pair_count"]
    ):
        raise ValueError("qualification_candidate_actual_pair_budget_exceeded")
    if len(pair_manifests) > int(authority["maximum_reranker_pairs_per_model"]):
        raise ValueError("qualification_candidate_actual_authority_pair_budget_exceeded")
    pair_manifest_digest = canonical_digest(pair_manifests)
    score_root = cache_root / "reranker_scores"

    bge_key = score_cache_key(
        scorer_id="bge_sequence_classification_relevant_need_v1",
        model_digest=identities["bge_reranker"]["model_digest"],
        pair_manifest_digest=pair_manifest_digest,
        maximum_sequence_length=int(model_policy["bge_reranker"]["maximum_sequence_length"]),
    )
    bge_cache_path = score_root / f"bge_{bge_key}.json"
    bge_scores = load_score_cache(
        bge_cache_path, cache_key=bge_key, expected_count=len(pair_manifests)
    )
    bge_reused = bge_scores is not None
    started = time.perf_counter()
    if bge_scores is None:
        runtime = load_local_cross_encoder(
            model_paths["bge_reranker"],
            maximum_sequence_length=int(model_policy["bge_reranker"]["maximum_sequence_length"]),
        )
        bge_scores = score_cross_encoder_pairs(
            runtime,
            pair_manifests,
            batch_size=int(model_policy["bge_reranker"]["batch_size"]),
            progress_every=100,
        )
        write_score_cache(
            bge_cache_path,
            cache_key=bge_key,
            pair_manifest_digest=pair_manifest_digest,
            scores=bge_scores,
        )
        del runtime
        empty_cuda()
    bge_reranker_seconds = time.perf_counter() - started

    qwen_instruction = str(model_policy["qwen_reranker"]["instruction"])
    qwen_key = score_cache_key(
        scorer_id="qwen3_yes_no_relevant_need_v1",
        model_digest=identities["qwen_reranker"]["model_digest"],
        pair_manifest_digest=pair_manifest_digest,
        maximum_sequence_length=int(model_policy["qwen_reranker"]["maximum_sequence_length"]),
        instruction=qwen_instruction,
    )
    qwen_cache_path = score_root / f"qwen_{qwen_key}.json"
    qwen_scores = load_score_cache(
        qwen_cache_path, cache_key=qwen_key, expected_count=len(pair_manifests)
    )
    qwen_reused = qwen_scores is not None
    started = time.perf_counter()
    if qwen_scores is None:
        runtime = load_local_qwen3_reranker(
            model_paths["qwen_reranker"],
            maximum_sequence_length=int(model_policy["qwen_reranker"]["maximum_sequence_length"]),
            instruction=qwen_instruction,
        )
        qwen_scores = score_qwen3_reranker_pairs(
            runtime,
            pair_manifests,
            batch_size=int(model_policy["qwen_reranker"]["batch_size"]),
        )
        write_score_cache(
            qwen_cache_path,
            cache_key=qwen_key,
            pair_manifest_digest=pair_manifest_digest,
            scores=qwen_scores,
        )
        del runtime
        empty_cuda()
    qwen_reranker_seconds = time.perf_counter() - started

    raw_propositions = []
    for proposition, pair_slice in zip(proposition_runtime, pair_slices):
        rerank_ids = proposition["rerank_ids"]
        bindings = pair_bindings[pair_slice]
        bge_rows, bge_best = aggregate_relevant_pair_scores(
            candidate_ids=rerank_ids,
            bindings=bindings,
            scores=bge_scores[pair_slice],
        )
        qwen_rows, qwen_best = aggregate_relevant_pair_scores(
            candidate_ids=rerank_ids,
            bindings=bindings,
            scores=qwen_scores[pair_slice],
        )
        selected_by_candidate: dict[str, list[str]] = {value: [] for value in rerank_ids}
        for binding in bindings:
            selected_by_candidate[binding.candidate_id].append(binding.need_id)
        need_to_lane = {
            need.need_id: lane_row["lane"]
            for lane_row in proposition["lane_rows"]
            for need in lane_row["needs"]
        }
        role_rows = [
            combined_role_evaluation(
                candidate_id=candidate_id,
                selected_need_ids=selected_by_candidate[candidate_id],
                need_to_lane=need_to_lane,
                objects_by_id=objects_by_id,
            )
            for candidate_id in rerank_ids
        ]
        compatibility = {
            row["compiled_object_id"]: row["compatibility"] for row in role_rows
        }
        role_guarded = role_guarded_primary_ranking(
            candidate_ids=rerank_ids,
            primary_rows=qwen_rows,
            shadow_rows=bge_rows,
            compatibility_by_id=compatibility,
        )
        cross_ranks = {
            "bge_reranker_v2_m3": _rank_map(bge_rows),
            "qwen3_reranker_0_6b": _rank_map(qwen_rows),
            "role_guarded_dual_reranker": _rank_map(role_guarded),
        }
        lane_shortlists = []
        lane_outputs = []
        for lane_row in proposition["lane_rows"]:
            lane = lane_row["lane"]
            lane_need_ids = {need.need_id for need in lane_row["needs"]}
            lane_candidate_ids = [
                candidate_id
                for candidate_id in rerank_ids
                if any(
                    str(value.get("need_id") or "") in lane_need_ids
                    for value in proposition["route_membership"].get(candidate_id, ())
                )
            ]
            shortlist = rank_financial_evidence_shortlist(
                union_object_ids=lane_candidate_ids,
                objects_by_id=objects_by_id,
                lane=lane,
                route_membership=proposition["route_membership"],
                cross_encoder_ranks_by_id={
                    candidate_id: {
                        route_id: ranks.get(candidate_id)
                        for route_id, ranks in cross_ranks.items()
                    }
                    for candidate_id in lane_candidate_ids
                },
                request=lane_row["request"].as_dict(),
                intent_ontology=intent_ontology,
                retrieval_needs=[need.as_dict() for need in lane_row["needs"]],
            )
            shortlist_scores = tuple(
                CandidateScore(
                    str(value["compiled_object_id"]), float(len(shortlist) - rank)
                )
                for rank, value in enumerate(shortlist)
            )
            lane_shortlists.append(
                NeedRouteRanking(
                    route_id="financial_evidence_shortlist",
                    need_id=lane.lane_id,
                    rows=shortlist_scores,
                )
            )
            lane_outputs.append(
                {
                    "lane_id": lane.lane_id,
                    "facet_id": lane.facet_id,
                    "need_count": len(lane_row["needs"]),
                    "hard_eligible_object_count": lane_row["hard_eligible_object_count"],
                    "rank_authority_object_count": lane_row["rank_authority_object_count"],
                    "exclusion_counts": lane_row["exclusion_counts"],
                    "projection_only_counts": lane_row["projection_only_counts"],
                    "shortlist_top20": [
                        str(value["compiled_object_id"]) for value in shortlist[:20]
                    ],
                }
            )
        final_rows = fuse_need_rankings_with_route_floors(
            lane_shortlists,
            maximum=len(rerank_ids),
            route_minimum_per_need={
                "financial_evidence_shortlist": int(
                    contract["final_shortlist_minimum_per_lane"]
                )
            },
            reciprocal_rank_constant=int(contract["reciprocal_rank_constant"]),
        )
        raw_propositions.append(
            {
                "example_id": proposition["input"].example_id,
                "case_key": proposition["request"].case_key,
                "question_zh": proposition["input"].runtime_input["question_zh"],
                "need_count": len(proposition["needs_by_id"]),
                "candidate_union_count": len(proposition["candidate_ids"]),
                "reranker_candidate_count": len(rerank_ids),
                "reranker_pair_count_per_model": len(bindings),
                "candidate_union_top20": proposition["candidate_ids"][:20],
                "bge_reranker_top20": [row.compiled_object_id for row in bge_rows[:20]],
                "qwen_reranker_top20": [row.compiled_object_id for row in qwen_rows[:20]],
                "role_guarded_top20": [
                    row.compiled_object_id for row in role_guarded[:20]
                ],
                "final_shortlist": _candidate_rows(final_rows, maximum=len(final_rows)),
                "candidate_review_top20": [
                    row.compiled_object_id
                    for row in final_rows[: int(contract["candidate_review_k"])]
                ],
                "bge_best_need_by_candidate": bge_best,
                "qwen_best_need_by_candidate": qwen_best,
                "role_evaluations": role_rows,
                "lanes": lane_outputs,
                "candidate_is_not_evidence": True,
                "numeric_fact_authority": False,
            }
        )

    raw = {
        "schema_version": RAW_SCHEMA,
        "status": "candidate_generation_complete_labels_not_loaded",
        "recorded_at": "2026-08-18",
        "attempt_id": authority["attempt_id"],
        "split": split,
        "bound_inputs": {
            "policy_ref": _relative(policy_path),
            "policy_sha256": sha256_file(policy_path),
            "authority_ref": _relative(authority_path),
            "authority_sha256": sha256_file(authority_path),
            "compiled_objects_ref": _relative(object_path),
            "compiled_objects_sha256": object_digest,
        },
        "execution": {
            "cuda_execution_receipt": receipt,
            "model_identities": identities,
            "bge_embedding_cache": bge_cache,
            "qwen_embedding_cache": qwen_cache,
            "bge_query_seconds": round(bge_query_seconds, 3),
            "qwen_query_seconds": round(qwen_query_seconds, 3),
            "bge_reranker_seconds": round(bge_reranker_seconds, 3),
            "qwen_reranker_seconds": round(qwen_reranker_seconds, 3),
            "reranker_pair_manifest_digest": pair_manifest_digest,
            "reranker_pair_count_per_model": len(pair_manifests),
            "bge_reranker_cache_reused": bge_reused,
            "qwen_reranker_cache_reused": qwen_reused,
            "network_calls": 0,
            "generation_model_calls": 0,
            "training_steps": 0,
            "labels_loaded": False,
        },
        "summary": {
            "case_count": len({row["case_key"] for row in raw_propositions}),
            "example_count": len(raw_propositions),
            "retrieval_need_count": len(all_needs),
            "candidate_review_k": int(contract["candidate_review_k"]),
            "candidate_is_not_evidence": True,
            "numeric_fact_authority": False,
        },
        "propositions": raw_propositions,
        "authority": {
            "evaluator_reference_loaded": False,
            "qualification_scored": False,
            "evidence_promotion_authorized": False,
            "numeric_fact_authority": False,
            "s1_qualified": False,
        },
    }
    raw["result_digest"] = canonical_digest(raw)
    raw_output_path = _resolve(str(authority["raw_output_ref"]))
    public_result_path = _resolve(str(authority["public_result_ref"]))
    write_json(raw_output_path, raw)
    public = {
        "schema_version": RESULT_SCHEMA,
        "status": "candidate_generation_complete_evaluation_pending",
        "recorded_at": "2026-08-18",
        "attempt_id": authority["attempt_id"],
        "split": split,
        "design_baseline_commit": authority["design_baseline_commit"],
        "raw_output_ref": _relative(raw_output_path),
        "raw_output_sha256": sha256_file(raw_output_path),
        "raw_result_digest": raw["result_digest"],
        "summary": raw["summary"],
        "execution": {
            "cuda_execution_receipt": receipt,
            "model_digests": {
                key: value["model_digest"] for key, value in identities.items()
            },
            "bge_embedding_cache_hit": bool(bge_cache["cache_hit"]),
            "qwen_embedding_cache_hit": bool(qwen_cache["cache_hit"]),
            "reranker_pair_count_per_model": len(pair_manifests),
            "network_calls": 0,
            "model_calls": 0,
            "cpu_vector_fallback_calls": 0,
        },
        "authority": raw["authority"],
    }
    write_json(public_result_path, public)
    return public, raw_output_path, public_result_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run label-blind S1 VS5 qualification candidate generation."
    )
    parser.add_argument("--policy", required=True)
    parser.add_argument("--authority", required=True)
    parser.add_argument(
        "--cache-root",
        default="data/workbench_private/fin_0_1_3_s1_vs5_qualification_cache",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    policy_path = _resolve(args.policy)
    authority_path = _resolve(args.authority)
    try:
        public, _, _ = _run(
            policy_path=policy_path,
            authority_path=authority_path,
            cache_root=_resolve(args.cache_root),
        )
    except Exception as exc:
        authority = read_json(authority_path) if authority_path.is_file() else {}
        public_ref = authority.get("public_result_ref")
        if public_ref:
            write_json(
                _resolve(str(public_ref)),
                {
                    "schema_version": RESULT_SCHEMA,
                    "status": "candidate_generation_failed",
                    "recorded_at": "2026-08-18",
                    "attempt_id": authority.get("attempt_id"),
                    "split": authority.get("split"),
                    "failure": {
                        "phase": "label_blind_candidate_generation",
                        "code": type(exc).__name__,
                        "detail": str(exc),
                        "retry_performed": False,
                    },
                    "authority": {
                        "qualification_scored": False,
                        "s1_qualified": False,
                    },
                },
            )
        raise
    print(json.dumps(public, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
