from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Mapping, Sequence

import numpy as np

from .balanced_lexical_recall import balanced_bm25_rank
from .contracts import EvidenceRequest, FinancialResearchKernel
from .embedding_runtime import (
    load_qwen_embedding_runtime,
    local_model_identity,
    sha256_file,
)
from .financial_candidate_ranking import rank_financial_candidate_union
from .evidence_role import evaluate_evidence_role
from .evidence_set_coverage import select_request_bound_review
from .financial_evidence_shortlist_v2 import candidate_shortlist_features
from .material_evidence_runtime import (
    adapt_material_candidate_from_feature_views,
    compile_material_requirement_plan_from_runtime_input,
)
from .object_retrieval_comparison import (
    CandidateScore,
    bm25_rank,
    dense_rank,
    load_compiled_objects,
    union_candidate_ids,
)
from .query_atom_shadow import eligible_request_indices
from .query_plan import (
    canonical_digest,
    compile_query_facet_plan_for_request as compile_query_facet_plan_for_request_v1,
)
from .query_plan_v3 import (
    compile_query_facet_plan_for_request as compile_query_facet_plan_for_request_v3,
)
from .retrieval_need import compile_retrieval_needs
from .route_compiler import QueryObjectFactRoutePolicy


HYBRID_RUNTIME_POLICY_SCHEMA_VERSION = (
    "fin_ia_s1c_hybrid_candidate_runtime_policy_v1_0"
)
HYBRID_RUNTIME_POLICY_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_s1c_hybrid_candidate_runtime_policy_v1_1"
)
HYBRID_RUNTIME_POLICY_OWNER_BALANCED_SCHEMA_VERSION = (
    "fin_ia_s1c_hybrid_candidate_runtime_policy_v1_2"
)
HYBRID_RUNTIME_POLICY_TYPED_BALANCED_SCHEMA_VERSION = (
    "fin_ia_s1c_hybrid_candidate_runtime_policy_v1_3"
)
HYBRID_RESULT_SCHEMA_VERSION = "fin_ia_s1c_hybrid_candidate_result_v1_0"
HYBRID_RESULT_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_s1c_hybrid_candidate_result_v1_1"
)
HYBRID_RESULT_OWNER_BALANCED_SCHEMA_VERSION = (
    "fin_ia_s1c_hybrid_candidate_result_v1_2"
)
HYBRID_RESULT_MATERIAL_AWARE_SCHEMA_VERSION = (
    "fin_ia_s1c_hybrid_candidate_result_v1_3"
)
HYBRID_RESULT_TYPED_BALANCED_SCHEMA_VERSION = (
    "fin_ia_s1c_hybrid_candidate_result_v1_4"
)
HYBRID_RESULT_PRODUCT_DECISION_SCHEMA_VERSION = (
    "fin_ia_s1c_hybrid_candidate_result_v1_5"
)

_REQUIRED_AUTHORITY = {
    "candidate_is_not_evidence": True,
    "numeric_authority": False,
    "embedding_grants_evidence_authority": False,
    "database_lane_remains_independent": True,
    "generation_model_calls_authorized": False,
}


def _policy_feature_flags(schema_version: str) -> tuple[bool, bool, bool]:
    typed_balanced = (
        schema_version == HYBRID_RUNTIME_POLICY_TYPED_BALANCED_SCHEMA_VERSION
    )
    owner_balanced = schema_version in {
        HYBRID_RUNTIME_POLICY_OWNER_BALANCED_SCHEMA_VERSION,
        HYBRID_RUNTIME_POLICY_TYPED_BALANCED_SCHEMA_VERSION,
    }
    financial_ranking = schema_version in {
        HYBRID_RUNTIME_POLICY_SUCCESSOR_SCHEMA_VERSION,
        HYBRID_RUNTIME_POLICY_OWNER_BALANCED_SCHEMA_VERSION,
        HYBRID_RUNTIME_POLICY_TYPED_BALANCED_SCHEMA_VERSION,
    }
    return financial_ranking, owner_balanced, typed_balanced


class HybridCandidateRuntimeError(ValueError):
    """Fail-closed error for the provisional BM25 + Qwen candidate runtime."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise HybridCandidateRuntimeError(code)


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HybridCandidateRuntimeError(
            f"hybrid_candidate_json_invalid:{path.name}"
        ) from exc
    _require(isinstance(value, dict), f"hybrid_candidate_json_invalid:{path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                _require(
                    isinstance(value, dict),
                    f"hybrid_candidate_jsonl_row_invalid:{line_number}",
                )
                rows.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HybridCandidateRuntimeError(
            f"hybrid_candidate_jsonl_invalid:{path.name}"
        ) from exc
    return rows


def _route_maps(
    rows: Sequence[CandidateScore],
) -> tuple[dict[str, int], dict[str, float]]:
    return (
        {row.compiled_object_id: rank for rank, row in enumerate(rows, start=1)},
        {row.compiled_object_id: float(row.score) for row in rows},
    )


def _owner_lane(lane: Any, owner: str) -> Any:
    try:
        index = lane.evidence_owner_tickers.index(owner)
    except ValueError as exc:
        raise HybridCandidateRuntimeError(
            f"hybrid_material_candidate_owner_outside_lane:{owner}"
        ) from exc
    owner_query = next(
        (
            value
            for value in lane.owner_queries
            if value.evidence_owner_ticker == owner
        ),
        None,
    )
    _require(
        owner_query is not None,
        f"hybrid_material_owner_query_missing:{owner}",
    )
    return replace(
        lane,
        evidence_owner_tickers=(owner,),
        relationship_constraints=(lane.relationship_constraints[index],),
        lexical_query=owner_query.lexical_query,
        lexical_tokens=owner_query.lexical_tokens,
        owner_queries=(owner_query,),
    )


def _material_candidate_metadata(
    *,
    request: EvidenceRequest,
    lane: Any,
    union_ids: Sequence[str],
    objects_by_id: Mapping[str, Mapping[str, Any]],
    route_maps_by_owner: Mapping[
        str,
        tuple[Mapping[str, int], Mapping[str, float], Mapping[str, int], Mapping[str, float]],
    ],
    fallback_route_maps: tuple[
        Mapping[str, int], Mapping[str, float], Mapping[str, int], Mapping[str, float]
    ],
    material_runtime_policy: Mapping[str, Any],
    intent_ontology: Mapping[str, Any],
    retrieval_need_policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project the full first-stage union before any quota or output cut."""

    request_payload = request.as_dict()
    needs_by_owner: dict[str, tuple[Any, tuple[Mapping[str, Any], ...]]] = {}
    for owner in lane.evidence_owner_tickers:
        narrowed_lane = _owner_lane(lane, owner)
        need_set = compile_retrieval_needs(
            request=request,
            lane=narrowed_lane,
            policy=retrieval_need_policy,
            intent_ontology=intent_ontology,
        )
        needs_by_owner[owner] = (
            narrowed_lane,
            tuple(value.as_dict() for value in need_set.needs),
        )

    candidates: list[dict[str, Any]] = []
    for union_rank, object_id in enumerate(union_ids, start=1):
        object_row = objects_by_id[object_id]
        base = object_row["base_object_view"]
        owner = str(base["ticker"])
        narrowed_lane, needs = needs_by_owner[owner]
        bm25_ranks, bm25_scores, qwen_ranks, qwen_scores = (
            route_maps_by_owner.get(owner, fallback_route_maps)
        )
        feature_views: list[dict[str, Any]] = []
        for need in needs:
            route_rows: list[dict[str, Any]] = []
            if object_id in bm25_ranks:
                route_rows.append(
                    {
                        "need_id": need["need_id"],
                        "route_id": "bm25_need_lexical",
                        "rank": bm25_ranks[object_id],
                    }
                )
            if object_id in qwen_ranks:
                route_rows.append(
                    {
                        "need_id": need["need_id"],
                        "route_id": "qwen3_embedding_0_6b_dense",
                        "rank": qwen_ranks[object_id],
                    }
                )
            if not route_rows:
                continue
            feature_views.append(
                {
                    "facet_id": narrowed_lane.facet_id,
                    "feature": candidate_shortlist_features(
                        object_row,
                        lane=narrowed_lane,
                        route_rows=route_rows,
                        union_rank=union_rank,
                        cross_encoder_ranks={},
                        request=request_payload,
                        intent_ontology=intent_ontology,
                        retrieval_needs=(need,),
                    ),
                }
            )
        route_scores = tuple(
            value
            for value in (
                bm25_scores.get(object_id),
                qwen_scores.get(object_id),
            )
            if value is not None
        )
        candidates.append(
            adapt_material_candidate_from_feature_views(
                case_key=request.case_key,
                candidate_row={
                    "compiled_object_id": object_id,
                    "rank": union_rank,
                    "score": max(route_scores, default=0.0),
                },
                object_row=object_row,
                feature_views=feature_views,
                evidence_request=request_payload,
                accounting_basis="issuer_reported_candidate_surface",
                policy=material_runtime_policy,
                ontology=intent_ontology,
            )
        )
    return candidates


def retrieve_hybrid_candidates(
    *,
    request: EvidenceRequest,
    kernel: FinancialResearchKernel,
    route_policy: QueryObjectFactRoutePolicy,
    objects: Sequence[Mapping[str, Any]],
    qwen_document_embeddings: np.ndarray,
    qwen_query_embedding: np.ndarray,
    first_stage_limit: int,
    candidate_union_limit: int,
    output_limit: int,
    max_candidates_per_source_record: int,
    financial_ranking_enabled: bool = False,
    minimum_candidates_per_owner: int = 0,
    evidence_role_advisory_enabled: bool = False,
    material_runtime_input: Mapping[str, Any] | None = None,
    material_runtime_policy: Mapping[str, Any] | None = None,
    intent_ontology: Mapping[str, Any] | None = None,
    retrieval_need_policy: Mapping[str, Any] | None = None,
    typed_balanced_lexical_enabled: bool = False,
) -> dict[str, Any]:
    """Return a hard-filtered, source-diverse BM25 + Qwen candidate union."""

    _require(
        first_stage_limit >= output_limit >= 1
        and candidate_union_limit >= first_stage_limit
        and max_candidates_per_source_record >= 1,
        "hybrid_candidate_limits_invalid",
    )
    _require(
        0 <= minimum_candidates_per_owner <= output_limit,
        "hybrid_candidate_owner_floor_invalid",
    )
    material_contract_inputs = (
        material_runtime_input,
        material_runtime_policy,
        retrieval_need_policy,
    )
    material_aware = all(
        value is not None for value in material_contract_inputs
    ) and intent_ontology is not None
    _require(
        material_aware
        or all(value is None for value in material_contract_inputs),
        "hybrid_material_runtime_inputs_incomplete",
    )
    if material_aware:
        _require(
            material_runtime_input.get("evidence_request") == request.as_dict(),
            "hybrid_material_runtime_request_mismatch",
        )
        _require(
            int(material_runtime_policy.get("review_k") or 0) == output_limit,
            "hybrid_material_runtime_review_capacity_mismatch",
        )
    plan = (
        compile_query_facet_plan_for_request_v3(
            kernel,
            request,
            ontology=intent_ontology,
        )
        if typed_balanced_lexical_enabled
        else compile_query_facet_plan_for_request_v1(kernel, request)
    )
    _require(len(plan.lanes) == 1, "hybrid_candidate_lane_count_invalid")
    lane = plan.lanes[0]
    eligible, exclusions = eligible_request_indices(
        objects,
        request=request,
        lane=lane,
        route_policy=route_policy,
    )
    if typed_balanced_lexical_enabled:
        lexical_recall = balanced_bm25_rank(
            objects,
            eligible,
            lane.lexical_subqueries,
            limit=first_stage_limit,
        )
        bm25 = list(lexical_recall.candidates)
        lexical_recall_trace = dict(lexical_recall.trace)
    else:
        bm25 = bm25_rank(
            objects,
            eligible,
            lane.lexical_query,
            limit=first_stage_limit,
        )
        lexical_recall_trace = {
            "mode": "single_broad_bm25_v1",
            "subquery_count": 1,
            "candidate_count": len(bm25),
            "candidate_not_evidence": True,
        }
    qwen = dense_rank(
        objects,
        eligible,
        qwen_document_embeddings,
        qwen_query_embedding,
        limit=first_stage_limit,
    )
    union_ids = union_candidate_ids(
        (bm25, qwen),
        maximum=candidate_union_limit,
    )
    bm25_ranks, bm25_scores = _route_maps(bm25)
    qwen_ranks, qwen_scores = _route_maps(qwen)
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    owner_route_maps: dict[
        str,
        tuple[dict[str, int], dict[str, float], dict[str, int], dict[str, float]],
    ] = {}
    owner_ordered_ids: dict[str, list[str]] = {}
    owner_balance_active = (
        minimum_candidates_per_owner > 0 and len(lane.evidence_owner_tickers) > 1
    )
    if owner_balance_active or (
        material_aware and len(lane.evidence_owner_tickers) > 1
    ):
        for owner in lane.evidence_owner_tickers:
            owner_eligible = np.asarray(
                [
                    int(index)
                    for index in eligible
                    if str(objects[int(index)]["base_object_view"]["ticker"]) == owner
                ],
                dtype=np.int64,
            )
            owner_bm25 = (
                list(
                    balanced_bm25_rank(
                        objects,
                        owner_eligible,
                        lane.lexical_subqueries,
                        limit=first_stage_limit,
                    ).candidates
                )
                if typed_balanced_lexical_enabled
                else bm25_rank(
                    objects,
                    owner_eligible,
                    lane.lexical_query,
                    limit=first_stage_limit,
                )
            )
            owner_qwen = dense_rank(
                objects,
                owner_eligible,
                qwen_document_embeddings,
                qwen_query_embedding,
                limit=first_stage_limit,
            )
            owner_ordered_ids[owner] = list(
                union_candidate_ids(
                    (owner_bm25, owner_qwen),
                    maximum=candidate_union_limit,
                )
            )
            owner_route_maps[owner] = (
                *_route_maps(owner_bm25),
                *_route_maps(owner_qwen),
            )
    material_compiler_receipt: dict[str, Any] | None = None
    material_requirement_plan: dict[str, Any] | None = None
    material_selection: dict[str, Any] | None = None
    material_candidates: list[dict[str, Any]] = []
    material_candidates_by_id: dict[str, dict[str, Any]] = {}
    material_review_order_ids: list[str] = []
    reserved_material_ids: list[str] = []
    if material_aware:
        material_requirement_plan, material_compiler_receipt = (
            compile_material_requirement_plan_from_runtime_input(
                runtime_input=material_runtime_input,
                policy=material_runtime_policy,
                ontology=intent_ontology,
            )
        )
        material_candidates = _material_candidate_metadata(
            request=request,
            lane=lane,
            union_ids=union_ids,
            objects_by_id=objects_by_id,
            route_maps_by_owner=owner_route_maps,
            fallback_route_maps=(
                bm25_ranks,
                bm25_scores,
                qwen_ranks,
                qwen_scores,
            ),
            material_runtime_policy=material_runtime_policy,
            intent_ontology=intent_ontology,
            retrieval_need_policy=retrieval_need_policy,
        )
        material_candidates_by_id = {
            str(row["compiled_object_id"]): row for row in material_candidates
        }
        material_selection = select_request_bound_review(
            candidates=material_candidates,
            plan=material_requirement_plan,
        )
        material_review_order_ids = list(
            material_selection["selected_candidate_ids"]
        )
        reserved_material_ids = list(
            dict.fromkeys(
                str(object_id)
                for receipt in material_selection["requirement_receipts"]
                for object_id in receipt["selected_candidate_ids"]
            )
        )
    financial_features_by_id: dict[str, dict[str, Any]] = {}
    raw_union_ids = list(union_ids)
    ordered_ids = list(raw_union_ids)
    if financial_ranking_enabled:
        ranked = rank_financial_candidate_union(
            union_object_ids=union_ids,
            objects_by_id=objects_by_id,
            lane=lane,
            route_ranks_by_id={
                object_id: {
                    "bm25_lexical": bm25_ranks.get(object_id),
                    "qwen3_embedding_0_6b_dense": qwen_ranks.get(object_id),
                }
                for object_id in union_ids
            },
        )
        ordered_ids = [str(row["compiled_object_id"]) for row in ranked]
        financial_features_by_id = {
            str(row["compiled_object_id"]): row for row in ranked
        }
    financial_order_ids = list(ordered_ids)
    reserved_material_id_set = set(reserved_material_ids)
    if material_review_order_ids:
        material_review_order_id_set = set(material_review_order_ids)
        ordered_ids = [
            *material_review_order_ids,
            *(
                object_id
                for object_id in ordered_ids
                if object_id not in material_review_order_id_set
            ),
        ]
    review_priority_ids = list(ordered_ids)
    selected_ids: list[str] = []
    source_counts: dict[str, int] = {}
    for object_id in ordered_ids:
        row = objects_by_id[object_id]
        base = row["base_object_view"]
        source_id = str(base["source_record_id"])
        if (
            source_counts.get(source_id, 0)
            >= max_candidates_per_source_record
            and object_id not in reserved_material_id_set
        ):
            continue
        source_counts[source_id] = source_counts.get(source_id, 0) + 1
        selected_ids.append(object_id)
        if len(selected_ids) >= output_limit:
            break

    owner_floor_unmet: list[str] = []
    if owner_balance_active:
        owner_counts = {
            owner: sum(
                str(objects_by_id[object_id]["base_object_view"]["ticker"])
                == owner
                for object_id in selected_ids
            )
            for owner in lane.evidence_owner_tickers
        }
        for owner in lane.evidence_owner_tickers:
            while owner_counts[owner] < minimum_candidates_per_owner:
                replacement = next(
                    (
                        object_id
                        for object_id in owner_ordered_ids.get(owner, ())
                        if object_id not in selected_ids
                        and source_counts.get(
                            str(
                                objects_by_id[object_id]["base_object_view"][
                                    "source_record_id"
                                ]
                            ),
                            0,
                        )
                        < max_candidates_per_source_record
                    ),
                    None,
                )
                if replacement is None:
                    owner_floor_unmet.append(owner)
                    break
                if len(selected_ids) < output_limit:
                    selected_ids.append(replacement)
                else:
                    replace_index = next(
                        (
                            index
                            for index in range(len(selected_ids) - 1, -1, -1)
                            if selected_ids[index] not in reserved_material_id_set
                            and owner_counts[
                                str(
                                    objects_by_id[selected_ids[index]][
                                        "base_object_view"
                                    ]["ticker"]
                                )
                            ]
                            > minimum_candidates_per_owner
                        ),
                        None,
                    )
                    if replace_index is None:
                        owner_floor_unmet.append(owner)
                        break
                    removed = selected_ids[replace_index]
                    removed_base = objects_by_id[removed]["base_object_view"]
                    removed_owner = str(removed_base["ticker"])
                    removed_source = str(removed_base["source_record_id"])
                    source_counts[removed_source] -= 1
                    owner_counts[removed_owner] -= 1
                    selected_ids[replace_index] = replacement
                replacement_source = str(
                    objects_by_id[replacement]["base_object_view"]["source_record_id"]
                )
                source_counts[replacement_source] = (
                    source_counts.get(replacement_source, 0) + 1
                )
                owner_counts[owner] += 1

    raw_union_rank_by_id = {
        object_id: rank for rank, object_id in enumerate(raw_union_ids, start=1)
    }
    financial_rank_by_id = {
        object_id: rank
        for rank, object_id in enumerate(financial_order_ids, start=1)
    }
    review_priority_rank_by_id = {
        object_id: rank
        for rank, object_id in enumerate(review_priority_ids, start=1)
    }
    final_output_rank_by_id = {
        object_id: rank for rank, object_id in enumerate(selected_ids, start=1)
    }
    material_selected_id_set = set(material_review_order_ids)
    material_alignment_excluded_id_set = set(
        (
            material_selection.get("request_alignment_excluded_candidate_ids")
            if material_selection
            else ()
        )
        or ()
    )
    requirement_ids_by_candidate: dict[str, list[str]] = {}
    if material_selection:
        for receipt in material_selection.get("requirement_receipts") or ():
            requirement_id = str(receipt.get("requirement_id") or "")
            for object_id in receipt.get("selected_candidate_ids") or ():
                requirement_ids_by_candidate.setdefault(str(object_id), []).append(
                    requirement_id
                )

    relationship_by_owner = dict(
        zip(lane.evidence_owner_tickers, lane.relationship_constraints)
    )
    candidate_decision_seed: list[dict[str, Any]] = []
    for object_id in raw_union_ids:
        row = objects_by_id[object_id]
        base = row["base_object_view"]
        source_id = str(base["source_record_id"])
        owner = str(base["ticker"])
        owner_maps = owner_route_maps.get(owner)
        effective_bm25_ranks = owner_maps[0] if owner_maps else bm25_ranks
        effective_qwen_ranks = owner_maps[2] if owner_maps else qwen_ranks
        routes = []
        if object_id in effective_bm25_ranks:
            routes.append("bm25_lexical")
        if object_id in effective_qwen_ranks:
            routes.append("qwen3_embedding_0_6b_dense")
        evidence_role = None
        if evidence_role_advisory_enabled:
            evidence_role = {
                **evaluate_evidence_role(
                    {
                        "ticker": owner,
                        "section": base.get("section"),
                        "subsection": base.get("subsection"),
                        "source_type": base.get("source_type"),
                        "object_kind": row.get("object_kind"),
                        "document_text": row.get("model_text"),
                        "structured_projection": row.get("structured_projection"),
                    },
                    slot_id=lane.slot_id,
                    facet_id=lane.facet_id,
                    subject_ticker=lane.subject_ticker,
                    evidence_owner_ticker=owner,
                    relationship_direction=relationship_by_owner.get(owner),
                ).as_dict(),
                "advisory_only": True,
                "decision_authority": False,
            }
        if object_id in material_selected_id_set:
            alignment_state = "selected_for_material_review"
        elif object_id in material_alignment_excluded_id_set:
            alignment_state = "excluded_by_material_requirement_alignment"
        else:
            alignment_state = "eligible_not_selected"
        candidate_decision_seed.append(
            {
                "compiled_object_id": object_id,
                "source_record_id": source_id,
                "lineage_source_record_ids": list(
                    row.get("lineage_source_record_ids") or (source_id,)
                ),
                "ticker": owner,
                "source_type": str(base["source_type"]),
                "source_tier": str(base["source_tier"]),
                "publication_date": str(base["publication_date"]),
                "period_end": str(base.get("period_end") or ""),
                "object_kind": str(row["object_kind"]),
                "rank_trace": {
                    "raw_union_rank": raw_union_rank_by_id[object_id],
                    "financial_rank": financial_rank_by_id[object_id],
                    "review_priority_rank": review_priority_rank_by_id[object_id],
                    "final_output_rank": final_output_rank_by_id.get(object_id),
                },
                "route_membership": routes,
                "route_ranks": {
                    "bm25_lexical": effective_bm25_ranks.get(object_id),
                    "qwen3_embedding_0_6b_dense": effective_qwen_ranks.get(
                        object_id
                    ),
                },
                "material_alignment_state": alignment_state,
                "material_reserved_for_requirement": (
                    object_id in reserved_material_id_set
                ),
                "selected_requirement_ids": sorted(
                    set(requirement_ids_by_candidate.get(object_id, ()))
                ),
                "evidence_role": evidence_role,
                "candidate_not_evidence": True,
                "candidate_text_included": False,
                "evidence_promoted": False,
                "numeric_authority": False,
            }
        )

    selected: list[dict[str, Any]] = []
    for object_id in selected_ids:
        row = objects_by_id[object_id]
        base = row["base_object_view"]
        source_id = str(base["source_record_id"])
        owner = str(base["ticker"])
        owner_maps = owner_route_maps.get(owner)
        effective_bm25_ranks = owner_maps[0] if owner_maps else bm25_ranks
        effective_bm25_scores = owner_maps[1] if owner_maps else bm25_scores
        effective_qwen_ranks = owner_maps[2] if owner_maps else qwen_ranks
        effective_qwen_scores = owner_maps[3] if owner_maps else qwen_scores
        routes = []
        if object_id in effective_bm25_ranks:
            routes.append("bm25_lexical")
        if object_id in effective_qwen_ranks:
            routes.append("qwen3_embedding_0_6b_dense")
        evidence_role = None
        if evidence_role_advisory_enabled:
            evidence_role = {
                **evaluate_evidence_role(
                    {
                        "ticker": owner,
                        "section": base.get("section"),
                        "subsection": base.get("subsection"),
                        "source_type": base.get("source_type"),
                        "object_kind": row.get("object_kind"),
                        "document_text": row.get("model_text"),
                        "structured_projection": row.get("structured_projection"),
                    },
                    slot_id=lane.slot_id,
                    facet_id=lane.facet_id,
                    subject_ticker=lane.subject_ticker,
                    evidence_owner_ticker=owner,
                    relationship_direction=relationship_by_owner.get(owner),
                ).as_dict(),
                "advisory_only": True,
                "ranking_effect": False,
                "hard_drop": False,
            }
        selected.append(
            {
                "rank": len(selected) + 1,
                "compiled_object_id": object_id,
                "source_record_id": source_id,
                "lineage_source_record_ids": list(
                    row.get("lineage_source_record_ids") or (source_id,)
                ),
                "ticker": str(base["ticker"]),
                "company": str(base.get("company") or ""),
                "source_type": str(base["source_type"]),
                "source_tier": str(base["source_tier"]),
                "publication_date": str(base["publication_date"]),
                "period_end": str(base.get("period_end") or ""),
                "fiscal_year": base.get("fiscal_year"),
                "section": str(base.get("section") or ""),
                "subsection": str(base.get("subsection") or ""),
                "object_kind": str(row["object_kind"]),
                "model_text": str(row["model_text"]),
                "route_membership": routes,
                "route_ranks": {
                    "bm25_lexical": effective_bm25_ranks.get(object_id),
                    "qwen3_embedding_0_6b_dense": effective_qwen_ranks.get(object_id),
                },
                "route_scores": {
                    "bm25_lexical": effective_bm25_scores.get(object_id),
                    "qwen3_embedding_0_6b_dense": effective_qwen_scores.get(object_id),
                },
                "financial_ranking": financial_features_by_id.get(object_id),
                "evidence_role": evidence_role,
                "candidate_not_evidence": True,
                "numeric_authority": False,
            }
        )
        if material_aware:
            selected[-1]["material_candidate"] = material_candidates_by_id.get(
                object_id
            )
            selected[-1]["material_reserved"] = (
                object_id in reserved_material_id_set
            )

    both = sum(len(row["route_membership"]) == 2 for row in selected)
    bm25_only = sum(row["route_membership"] == ["bm25_lexical"] for row in selected)
    qwen_only = sum(
        row["route_membership"] == ["qwen3_embedding_0_6b_dense"]
        for row in selected
    )
    material_scope_ready = bool(
        material_aware
        and not material_compiler_receipt[
            "explicit_blueprint_required_for_full_product_scope"
        ]
    )
    material_set_complete = bool(
        material_scope_ready
        and material_selection
        and not material_selection["unmet_requirement_ids"]
    )
    body = {
        "schema_version": (
            HYBRID_RESULT_PRODUCT_DECISION_SCHEMA_VERSION
            if typed_balanced_lexical_enabled
            else HYBRID_RESULT_MATERIAL_AWARE_SCHEMA_VERSION
            if material_aware
            else HYBRID_RESULT_OWNER_BALANCED_SCHEMA_VERSION
            if owner_balance_active or evidence_role_advisory_enabled
            else HYBRID_RESULT_SUCCESSOR_SCHEMA_VERSION
            if financial_ranking_enabled
            else HYBRID_RESULT_SCHEMA_VERSION
        ),
        "request_id": request.request_id,
        "facet_id": lane.facet_id,
        "evidence_owner_tickers": list(lane.evidence_owner_tickers),
        "route_id": (
            "typed_balanced_bm25_qwen_union_with_material_reservation_v2"
            if typed_balanced_lexical_enabled and material_aware
            else "typed_balanced_bm25_qwen_union_v1"
            if typed_balanced_lexical_enabled
            else "bm25_qwen_union_with_request_bound_material_reservation_v1"
            if material_aware
            else "bm25_qwen_owner_balanced_union_with_advisory_evidence_role_v1"
            if owner_balance_active or evidence_role_advisory_enabled
            else
            "bm25_plus_qwen_union_then_financial_structure_rank_v1"
            if financial_ranking_enabled
            else "bm25_lexical_plus_qwen3_embedding_dense_union"
        ),
        "candidate_state": "candidate_not_evidence",
        "query": {
            "lexical": lane.lexical_query,
            "lexical_recall": lexical_recall_trace,
            "semantic": lane.semantic_query,
            "relationship_constraints": list(lane.relationship_constraints),
            "required_source_roles": list(lane.required_source_roles),
            "exact_queries": list(lane.exact_queries),
            "graph_constraints": list(lane.graph_constraints),
            "forbidden_expansions": list(lane.forbidden_expansions),
        },
        "summary": {
            "eligible_object_count": int(eligible.size),
            "bm25_first_stage_count": len(bm25),
            "qwen_first_stage_count": len(qwen),
            "union_count_before_source_quota": len(union_ids),
            "selected_count": len(selected),
            "selected_both_routes": both,
            "selected_bm25_only": bm25_only,
            "selected_qwen_only": qwen_only,
            "max_candidates_per_source_record": max_candidates_per_source_record,
            "financial_ranking_enabled": financial_ranking_enabled,
            "owner_balance_active": owner_balance_active,
            "minimum_candidates_per_owner": minimum_candidates_per_owner,
            "selected_candidate_count_by_owner": {
                owner: sum(row["ticker"] == owner for row in selected)
                for owner in lane.evidence_owner_tickers
            },
            "owner_floor_unmet": sorted(set(owner_floor_unmet)),
            "evidence_role_advisory_enabled": evidence_role_advisory_enabled,
            "typed_balanced_lexical_enabled": typed_balanced_lexical_enabled,
            "material_reservation_active": material_aware,
            "material_scope_ready": material_scope_ready,
            "material_set_complete": material_set_complete,
            "material_reserved_candidate_count": len(reserved_material_ids),
            "material_review_order_candidate_count": len(
                material_review_order_ids
            ),
            "hard_filter_exclusions": exclusions,
        },
        "candidates": selected,
        "authority": dict(_REQUIRED_AUTHORITY),
    }
    if typed_balanced_lexical_enabled:
        body["candidate_decision_seed"] = candidate_decision_seed
    if material_aware:
        body["material_evidence"] = {
            "compiler_receipt": material_compiler_receipt,
            "requirement_plan": material_requirement_plan,
            "selection": material_selection,
            "runtime_scope_ready": material_scope_ready,
            "material_set_complete": material_set_complete,
            "reservation_stage": "before_source_quota_owner_balance_and_output_cut",
            "candidate_is_not_evidence": True,
            "numeric_fact_authority": False,
        }
    return {**body, "result_digest": canonical_digest(body)}


class LocalQwenHybridCandidateRuntime:
    """Local adapter around an immutable object store and Qwen embedding cache."""

    def __init__(
        self,
        *,
        objects: Sequence[Mapping[str, Any]],
        qwen_document_embeddings: np.ndarray,
        qwen_runtime: Any,
        query_instruction: str,
        first_stage_limit: int,
        candidate_union_limit: int,
        output_limit: int,
        max_candidates_per_source_record: int,
        financial_ranking_enabled: bool,
        minimum_candidates_per_owner: int,
        evidence_role_advisory_enabled: bool,
        runtime_identity: Mapping[str, Any],
        typed_balanced_lexical_enabled: bool = False,
    ) -> None:
        self._objects = tuple(objects)
        self._qwen_document_embeddings = qwen_document_embeddings
        self._qwen_runtime = qwen_runtime
        self._query_instruction = query_instruction
        self._first_stage_limit = first_stage_limit
        self._candidate_union_limit = candidate_union_limit
        self._output_limit = output_limit
        self._max_candidates_per_source_record = max_candidates_per_source_record
        self._financial_ranking_enabled = financial_ranking_enabled
        self._minimum_candidates_per_owner = minimum_candidates_per_owner
        self._evidence_role_advisory_enabled = evidence_role_advisory_enabled
        self._typed_balanced_lexical_enabled = typed_balanced_lexical_enabled
        self.runtime_identity = dict(runtime_identity)
        self._inference_lock = Lock()

    @classmethod
    def from_policy(
        cls,
        repository_root: str | Path,
        payload: Mapping[str, Any],
    ) -> "LocalQwenHybridCandidateRuntime":
        root = Path(repository_root).resolve()
        schema_version = str(payload.get("schema_version") or "")
        successor, owner_balanced, typed_balanced = _policy_feature_flags(
            schema_version
        )
        expected_fields = {
            "schema_version",
            "status",
            "object_store",
            "qwen_embedding",
            "candidate_contract",
            "authority",
        }
        if successor:
            expected_fields.add("financial_ranking")
        if owner_balanced:
            expected_fields.update({"owner_balance", "evidence_role"})
        if typed_balanced:
            expected_fields.add("typed_query_recall")
        _require(set(payload) == expected_fields, "hybrid_runtime_policy_fields_invalid")
        _require(
            schema_version
            in {
                HYBRID_RUNTIME_POLICY_SCHEMA_VERSION,
                HYBRID_RUNTIME_POLICY_SUCCESSOR_SCHEMA_VERSION,
                HYBRID_RUNTIME_POLICY_OWNER_BALANCED_SCHEMA_VERSION,
                HYBRID_RUNTIME_POLICY_TYPED_BALANCED_SCHEMA_VERSION,
            },
            "hybrid_runtime_policy_schema_invalid",
        )
        _require(
            payload.get("status")
            == (
                "provisional_typed_balanced_candidate_runtime_not_evidence_authority"
                if typed_balanced
                else "provisional_owner_balanced_candidate_runtime_not_evidence_authority"
                if owner_balanced
                else
                "provisional_financial_structure_ranker_not_evidence_authority"
                if successor
                else "provisional_local_embedding_adapter_not_evidence_authority"
            ),
            "hybrid_runtime_policy_status_invalid",
        )
        _require(
            payload.get("authority") == _REQUIRED_AUTHORITY,
            "hybrid_runtime_policy_authority_invalid",
        )
        object_policy = payload.get("object_store")
        model_policy = payload.get("qwen_embedding")
        candidate_policy = payload.get("candidate_contract")
        financial_ranking = payload.get("financial_ranking")
        owner_balance = payload.get("owner_balance")
        evidence_role = payload.get("evidence_role")
        typed_query_recall = payload.get("typed_query_recall")
        _require(
            isinstance(object_policy, Mapping)
            and isinstance(model_policy, Mapping)
            and isinstance(candidate_policy, Mapping),
            "hybrid_runtime_policy_shape_invalid",
        )
        if successor:
            _require(
                financial_ranking
                == {
                    "enabled": True,
                    "strategy": "lexicographic_financial_structure_v1",
                    "evidence_role_mode": "advisory_with_abstain",
                    "source_quota_after_ranking": True,
                    "candidate_is_not_evidence": True,
                },
                "hybrid_runtime_financial_ranking_policy_invalid",
            )
        if owner_balanced:
            _require(
                owner_balance
                == {
                    "enabled": True,
                    "minimum_candidates_per_owner": 2,
                    "apply_only_to_multi_owner_requests": True,
                    "candidate_is_not_evidence": True,
                }
                and evidence_role
                == {
                    "mode": "advisory_with_abstain",
                    "ranking_effect": False,
                    "hard_drop": False,
                    "evidence_authority": False,
                },
                "hybrid_runtime_owner_balance_policy_invalid",
            )
        if typed_balanced:
            _require(
                typed_query_recall
                == {
                    "enabled": True,
                    "query_plan_schema": "fin_ia_typed_query_facet_plan_v1_2",
                    "strategy": "per_request_metric_product_balanced_bm25_v1",
                    "ontology_expansion_candidate_only": True,
                    "result_or_label_access": False,
                    "candidate_is_not_evidence": True,
                },
                "hybrid_runtime_typed_query_recall_policy_invalid",
            )
        objects_path = _resolve(root, str(object_policy.get("objects_ref") or ""))
        cache_path = _resolve(root, str(model_policy.get("dense_cache_ref") or ""))
        manifest_path = _resolve(root, str(model_policy.get("cache_manifest_ref") or ""))
        _require(
            objects_path.is_file() and cache_path.is_file() and manifest_path.is_file(),
            "hybrid_runtime_required_asset_missing",
        )
        manifest = _read_json(manifest_path)
        _require(
            sha256_file(objects_path) == str(object_policy.get("objects_sha256"))
            == str(manifest.get("object_sha256")),
            "hybrid_runtime_object_store_drift",
        )
        _require(
            sha256_file(cache_path) == str(manifest.get("dense_sha256")),
            "hybrid_runtime_embedding_cache_drift",
        )
        objects = load_compiled_objects(_read_jsonl(objects_path))
        dense = np.load(cache_path, mmap_mode="r")
        _require(
            dense.shape[0] == len(objects)
            and int(manifest.get("object_count") or 0) == len(objects),
            "hybrid_runtime_embedding_shape_drift",
        )
        env_name = str(model_policy.get("local_directory_env") or "").strip()
        configured = os.environ.get(env_name, "") if env_name else ""
        fallback = str(model_policy.get("development_fallback_local_directory") or "")
        model_dir = _resolve(root, configured or fallback)
        identity = local_model_identity(
            model_dir,
            str(model_policy.get("model_id") or ""),
        )
        _require(
            identity["model_digest"] == str(model_policy.get("model_digest"))
            == str(manifest.get("model_digest")),
            "hybrid_runtime_model_identity_drift",
        )
        runtime = load_qwen_embedding_runtime(model_dir)
        maximum_sequence_length = int(model_policy.get("maximum_sequence_length") or 0)
        _require(128 <= maximum_sequence_length <= 2048, "hybrid_runtime_sequence_limit_invalid")
        runtime.max_seq_length = maximum_sequence_length
        runtime_identity = {
            "object_sha256": str(manifest["object_sha256"]),
            "embedding_cache_sha256": str(manifest["dense_sha256"]),
            "model_digest": str(identity["model_digest"]),
            "object_count": len(objects),
        }
        return cls(
            objects=objects,
            qwen_document_embeddings=dense,
            qwen_runtime=runtime,
            query_instruction=str(model_policy.get("query_instruction") or "").strip(),
            first_stage_limit=int(candidate_policy.get("first_stage_limit") or 0),
            candidate_union_limit=int(candidate_policy.get("candidate_union_limit") or 0),
            output_limit=int(candidate_policy.get("output_limit") or 0),
            max_candidates_per_source_record=int(
                candidate_policy.get("max_candidates_per_source_record") or 0
            ),
            financial_ranking_enabled=successor,
            minimum_candidates_per_owner=(2 if owner_balanced else 0),
            evidence_role_advisory_enabled=owner_balanced,
            typed_balanced_lexical_enabled=typed_balanced,
            runtime_identity=runtime_identity,
        )

    def retrieve_many(
        self,
        requests: Sequence[EvidenceRequest],
        *,
        kernel: FinancialResearchKernel,
        route_policy: QueryObjectFactRoutePolicy,
        material_runtime_inputs: Mapping[str, Mapping[str, Any]] | None = None,
        material_runtime_policy: Mapping[str, Any] | None = None,
        intent_ontology: Mapping[str, Any] | None = None,
        retrieval_need_policy: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], ...]:
        lanes, encoded = self._encode_requests(
            requests,
            kernel=kernel,
            intent_ontology=intent_ontology,
        )
        return tuple(
            retrieve_hybrid_candidates(
                request=request,
                kernel=kernel,
                route_policy=route_policy,
                objects=self._objects,
                qwen_document_embeddings=self._qwen_document_embeddings,
                qwen_query_embedding=encoded[index],
                first_stage_limit=self._first_stage_limit,
                candidate_union_limit=self._candidate_union_limit,
                output_limit=self._output_limit,
                max_candidates_per_source_record=(
                    self._max_candidates_per_source_record
                ),
                financial_ranking_enabled=self._financial_ranking_enabled,
                minimum_candidates_per_owner=self._minimum_candidates_per_owner,
                evidence_role_advisory_enabled=(
                    self._evidence_role_advisory_enabled
                ),
                material_runtime_input=(
                    material_runtime_inputs.get(request.request_id)
                    if material_runtime_inputs is not None
                    else None
                ),
                material_runtime_policy=material_runtime_policy,
                intent_ontology=intent_ontology,
                retrieval_need_policy=retrieval_need_policy,
                typed_balanced_lexical_enabled=(
                    self._typed_balanced_lexical_enabled
                ),
            )
            for index, request in enumerate(requests)
        )

    def compare_financial_ranking(
        self,
        requests: Sequence[EvidenceRequest],
        *,
        kernel: FinancialResearchKernel,
        route_policy: QueryObjectFactRoutePolicy,
    ) -> tuple[dict[str, Any], ...]:
        """Compare legacy union order and financial order on one encoded query set."""

        _require(
            self._financial_ranking_enabled,
            "hybrid_runtime_financial_ranking_shadow_not_enabled",
        )
        _, encoded = self._encode_requests(requests, kernel=kernel)
        rows: list[dict[str, Any]] = []
        for index, request in enumerate(requests):
            common = {
                "request": request,
                "kernel": kernel,
                "route_policy": route_policy,
                "objects": self._objects,
                "qwen_document_embeddings": self._qwen_document_embeddings,
                "qwen_query_embedding": encoded[index],
                "first_stage_limit": self._first_stage_limit,
                "candidate_union_limit": self._candidate_union_limit,
                "output_limit": self._output_limit,
                "max_candidates_per_source_record": (
                    self._max_candidates_per_source_record
                ),
            }
            rows.append(
                {
                    "request_id": request.request_id,
                    "legacy": retrieve_hybrid_candidates(
                        **common,
                        financial_ranking_enabled=False,
                    ),
                    "financial": retrieve_hybrid_candidates(
                        **common,
                        financial_ranking_enabled=True,
                    ),
                    "candidate_not_evidence": True,
                    "numeric_authority": False,
                }
            )
        return tuple(rows)

    def _encode_requests(
        self,
        requests: Sequence[EvidenceRequest],
        *,
        kernel: FinancialResearchKernel,
        intent_ontology: Mapping[str, Any] | None = None,
    ) -> tuple[list[Any], np.ndarray]:
        _require(bool(requests), "hybrid_runtime_requests_missing")
        lanes = []
        for request in requests:
            plan = (
                compile_query_facet_plan_for_request_v3(
                    kernel,
                    request,
                    ontology=intent_ontology,
                )
                if self._typed_balanced_lexical_enabled
                else compile_query_facet_plan_for_request_v1(kernel, request)
            )
            _require(len(plan.lanes) == 1, "hybrid_candidate_lane_count_invalid")
            lanes.append(plan.lanes[0])
        with self._inference_lock:
            encoded = np.asarray(
                self._qwen_runtime.encode(
                    [lane.semantic_query for lane in lanes],
                    batch_size=len(lanes),
                    prompt=self._query_instruction,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                ),
                dtype=np.float32,
            )
        _require(
            encoded.shape[0] == len(requests),
            "hybrid_runtime_query_embedding_shape_invalid",
        )
        return lanes, encoded


class LazyLocalQwenHybridCandidateRuntime:
    """Load the local model only when a controlled research plan needs it."""

    def __init__(
        self,
        repository_root: str | Path,
        policy: Mapping[str, Any],
    ) -> None:
        self._repository_root = Path(repository_root).resolve()
        self._policy = dict(policy)
        self._delegate: LocalQwenHybridCandidateRuntime | None = None
        self._load_lock = Lock()

    def _runtime(self) -> LocalQwenHybridCandidateRuntime:
        if self._delegate is None:
            with self._load_lock:
                if self._delegate is None:
                    self._delegate = LocalQwenHybridCandidateRuntime.from_policy(
                        self._repository_root,
                        self._policy,
                    )
        return self._delegate

    def retrieve_many(
        self,
        requests: Sequence[EvidenceRequest],
        *,
        kernel: FinancialResearchKernel,
        route_policy: QueryObjectFactRoutePolicy,
        material_runtime_inputs: Mapping[str, Mapping[str, Any]] | None = None,
        material_runtime_policy: Mapping[str, Any] | None = None,
        intent_ontology: Mapping[str, Any] | None = None,
        retrieval_need_policy: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], ...]:
        return self._runtime().retrieve_many(
            requests,
            kernel=kernel,
            route_policy=route_policy,
            material_runtime_inputs=material_runtime_inputs,
            material_runtime_policy=material_runtime_policy,
            intent_ontology=intent_ontology,
            retrieval_need_policy=retrieval_need_policy,
        )


__all__ = [
    "HYBRID_RESULT_SCHEMA_VERSION",
    "HYBRID_RESULT_MATERIAL_AWARE_SCHEMA_VERSION",
    "HYBRID_RESULT_TYPED_BALANCED_SCHEMA_VERSION",
    "HYBRID_RESULT_PRODUCT_DECISION_SCHEMA_VERSION",
    "HYBRID_RUNTIME_POLICY_SCHEMA_VERSION",
    "HYBRID_RUNTIME_POLICY_SUCCESSOR_SCHEMA_VERSION",
    "HYBRID_RUNTIME_POLICY_OWNER_BALANCED_SCHEMA_VERSION",
    "HYBRID_RUNTIME_POLICY_TYPED_BALANCED_SCHEMA_VERSION",
    "HybridCandidateRuntimeError",
    "LazyLocalQwenHybridCandidateRuntime",
    "LocalQwenHybridCandidateRuntime",
    "retrieve_hybrid_candidates",
]
