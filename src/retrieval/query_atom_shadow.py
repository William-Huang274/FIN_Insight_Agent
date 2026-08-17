from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np

from .contracts import FinancialResearchKernel, load_evidence_request
from .evidence_role import evaluate_evidence_role
from .object_retrieval_comparison import (
    CandidateScore,
    bm25_rank,
    dense_rank,
    union_candidate_ids,
)
from .query_plan import QueryLane, compile_query_facet_plan_for_request
from .route_compiler import QueryObjectFactRoutePolicy


QUERY_ATOM_EVAL_SCHEMA_VERSION = "fin_ia_s1c_runtime_query_atom_eval_v1_0"
QUERY_ATOM_EVAL_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_s1c_runtime_query_atom_eval_v1_1"
)
QUERY_ATOM_EVAL_SENTENCE_OBJECT_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_s1c_runtime_query_atom_eval_v1_2"
)
QUERY_ATOM_EVAL_REVIEWED_LABEL_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_s1c_runtime_query_atom_eval_v1_3"
)
QUERY_ATOM_EVAL_SCHEMA_VERSIONS = frozenset(
    {
        QUERY_ATOM_EVAL_SCHEMA_VERSION,
        QUERY_ATOM_EVAL_SUCCESSOR_SCHEMA_VERSION,
        QUERY_ATOM_EVAL_SENTENCE_OBJECT_SUCCESSOR_SCHEMA_VERSION,
        QUERY_ATOM_EVAL_REVIEWED_LABEL_SUCCESSOR_SCHEMA_VERSION,
    }
)
QUERY_ATOM_LABEL_ADJUDICATION_SCHEMA_VERSION = (
    "fin_ia_query_atom_label_adjudication_v1_0"
)


class QueryAtomShadowError(ValueError):
    """Raised when a runtime-query shadow would weaken a hard boundary."""


@dataclass(frozen=True)
class QueryAtom:
    atom_id: str
    request_payload: Mapping[str, Any]
    positive_object_ids: tuple[str, ...]
    hard_negative_object_ids: tuple[str, ...]
    unjudged_object_ids: tuple[str, ...]
    expected_roles_by_object_id: Mapping[str, tuple[str, ...]]


def load_query_atoms(payload: Mapping[str, Any]) -> tuple[QueryAtom, ...]:
    if payload.get("schema_version") not in QUERY_ATOM_EVAL_SCHEMA_VERSIONS:
        raise QueryAtomShadowError("query_atom_eval_schema_invalid")
    policy = payload.get("policy")
    if not (
        isinstance(policy, Mapping)
        and policy.get("compile_request_before_label_join") is True
        and policy.get("one_facet_and_one_owner_per_atom") is True
        and policy.get("candidate_is_not_evidence") is True
        and policy.get("numeric_authority") is False
    ):
        raise QueryAtomShadowError("query_atom_eval_policy_invalid")
    rows = payload.get("atoms")
    if not isinstance(rows, list) or not rows:
        raise QueryAtomShadowError("query_atom_eval_rows_missing")
    atoms: list[QueryAtom] = []
    identities: set[str] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise QueryAtomShadowError("query_atom_eval_row_invalid")
        atom_id = str(raw.get("atom_id") or "").strip()
        request = raw.get("request")
        labels = raw.get("labels")
        if (
            not atom_id
            or atom_id in identities
            or not isinstance(request, Mapping)
            or not isinstance(labels, Mapping)
        ):
            raise QueryAtomShadowError("query_atom_eval_identity_invalid")
        requested_facets = request.get("requested_facet_ids")
        target_entities = request.get("target_entities")
        if not (
            isinstance(requested_facets, list)
            and len(requested_facets) == 1
            and isinstance(target_entities, list)
            and len(target_entities) == 1
        ):
            raise QueryAtomShadowError("query_atom_eval_not_atomic")
        positives = _unique_ids(labels.get("positive_object_ids") or ())
        negatives = _unique_ids(labels.get("hard_negative_object_ids") or ())
        unjudged = _unique_ids(labels.get("unjudged_object_ids") or ())
        all_labels = (*positives, *negatives, *unjudged)
        if len(all_labels) != len(set(all_labels)):
            raise QueryAtomShadowError("query_atom_eval_label_overlap")
        expected_raw = labels.get("expected_roles_by_object_id") or {}
        if not isinstance(expected_raw, Mapping):
            raise QueryAtomShadowError("query_atom_eval_expected_roles_invalid")
        expected = {
            str(object_id): tuple(str(role) for role in roles)
            for object_id, roles in expected_raw.items()
            if isinstance(roles, list)
        }
        if set(expected) - set(all_labels):
            raise QueryAtomShadowError("query_atom_eval_expected_role_orphan")
        identities.add(atom_id)
        atoms.append(
            QueryAtom(
                atom_id=atom_id,
                request_payload=dict(request),
                positive_object_ids=positives,
                hard_negative_object_ids=negatives,
                unjudged_object_ids=unjudged,
                expected_roles_by_object_id=expected,
            )
        )
    return tuple(atoms)


def apply_query_atom_label_adjudications(
    atoms: Sequence[QueryAtom], payload: Mapping[str, Any]
) -> tuple[QueryAtom, ...]:
    """Apply a reviewed label successor without rewriting the frozen qrel file."""

    if payload.get("schema_version") != QUERY_ATOM_LABEL_ADJUDICATION_SCHEMA_VERSION:
        raise QueryAtomShadowError("query_atom_adjudication_schema_invalid")
    authority = payload.get("authority")
    if not (
        isinstance(authority, Mapping)
        and authority.get("candidate_is_not_evidence") is True
        and authority.get("numeric_authority") is False
        and authority.get("owner_acceptance") is False
    ):
        raise QueryAtomShadowError("query_atom_adjudication_authority_invalid")
    changes = payload.get("adjudications")
    if not isinstance(changes, list) or not changes:
        raise QueryAtomShadowError("query_atom_adjudication_rows_missing")
    by_id = {atom.atom_id: atom for atom in atoms}
    if len(by_id) != len(atoms):
        raise QueryAtomShadowError("query_atom_adjudication_base_identity_invalid")
    touched: set[str] = set()
    for raw in changes:
        if not isinstance(raw, Mapping):
            raise QueryAtomShadowError("query_atom_adjudication_row_invalid")
        atom_id = str(raw.get("atom_id") or "").strip()
        if atom_id not in by_id or atom_id in touched:
            raise QueryAtomShadowError("query_atom_adjudication_atom_invalid")
        added = _unique_ids(raw.get("add_positive_object_ids") or ())
        expected_raw = raw.get("expected_roles_by_object_id")
        if not added or not isinstance(expected_raw, Mapping):
            raise QueryAtomShadowError("query_atom_adjudication_positive_invalid")
        expected = {
            str(object_id): tuple(str(role) for role in roles)
            for object_id, roles in expected_raw.items()
            if isinstance(roles, list) and roles
        }
        if set(expected) != set(added):
            raise QueryAtomShadowError("query_atom_adjudication_role_scope_invalid")
        atom = by_id[atom_id]
        existing = {
            *atom.positive_object_ids,
            *atom.hard_negative_object_ids,
            *atom.unjudged_object_ids,
        }
        if existing.intersection(added):
            raise QueryAtomShadowError("query_atom_adjudication_label_overlap")
        by_id[atom_id] = replace(
            atom,
            positive_object_ids=(*atom.positive_object_ids, *added),
            expected_roles_by_object_id={
                **atom.expected_roles_by_object_id,
                **expected,
            },
        )
        touched.add(atom_id)
    return tuple(by_id[atom.atom_id] for atom in atoms)


def compile_atom_lane(
    atom: QueryAtom,
    kernel: FinancialResearchKernel,
) -> tuple[Any, QueryLane]:
    request = load_evidence_request(atom.request_payload, kernel)
    plan = compile_query_facet_plan_for_request(kernel, request)
    if len(plan.lanes) != 1:
        raise QueryAtomShadowError("query_atom_compiled_lane_count_invalid")
    lane = plan.lanes[0]
    if len(lane.evidence_owner_tickers) != 1:
        raise QueryAtomShadowError("query_atom_compiled_owner_count_invalid")
    joined_query = (lane.lexical_query + "\n" + lane.semantic_query).casefold()
    if any(object_id.casefold() in joined_query for object_id in _all_labels(atom)):
        raise QueryAtomShadowError("query_atom_gold_identity_leaked_into_query")
    return request, lane


def eligible_atom_indices(
    objects: Sequence[Mapping[str, Any]],
    *,
    atom: QueryAtom,
    lane: QueryLane,
    route_policy: QueryObjectFactRoutePolicy,
) -> tuple[np.ndarray, dict[str, int]]:
    family = route_policy.family_by_facet().get(lane.facet_id)
    if family is None:
        raise QueryAtomShadowError("query_atom_facet_unrouted")
    object_kinds = {
        "bounded_parent_context" if form == "bounded_parent_context" else form
        for form in family.allowed_object_forms
    }
    request_period = atom.request_payload.get("period") or {}
    fiscal_years = {
        int(value) for value in request_period.get("fiscal_years") or ()
    }
    as_of = date.fromisoformat(lane.publication_date_lte)
    owner = lane.evidence_owner_tickers[0]
    eligible: list[int] = []
    exclusions: dict[str, int] = {}
    for index, row in enumerate(objects):
        reason = _atom_object_exclusion_reason(
            row,
            owner=owner,
            as_of=as_of,
            source_types=lane.source_types,
            object_kinds=object_kinds,
            fiscal_years=fiscal_years,
        )
        if reason is None:
            eligible.append(index)
        else:
            exclusions[reason] = exclusions.get(reason, 0) + 1
    return np.asarray(eligible, dtype=np.int64), dict(sorted(exclusions.items()))


def eligible_request_indices(
    objects: Sequence[Mapping[str, Any]],
    *,
    request: Any,
    lane: QueryLane,
    route_policy: QueryObjectFactRoutePolicy,
) -> tuple[np.ndarray, dict[str, int]]:
    """Apply the same hard boundary to a product request with one or more owners."""

    family = route_policy.family_by_facet().get(lane.facet_id)
    if family is None:
        raise QueryAtomShadowError("query_atom_facet_unrouted")
    object_kinds = {
        "bounded_parent_context" if form == "bounded_parent_context" else form
        for form in family.allowed_object_forms
    }
    fiscal_years = {int(value) for value in request.period.fiscal_years}
    as_of = date.fromisoformat(lane.publication_date_lte)
    owners = {value.upper() for value in lane.evidence_owner_tickers}
    if not owners:
        raise QueryAtomShadowError("query_request_evidence_owner_missing")
    eligible: list[int] = []
    exclusions: dict[str, int] = {}
    for index, row in enumerate(objects):
        reason = _request_object_exclusion_reason(
            row,
            owners=owners,
            as_of=as_of,
            source_types=lane.source_types,
            object_kinds=object_kinds,
            fiscal_years=fiscal_years,
        )
        if reason is None:
            eligible.append(index)
        else:
            exclusions[reason] = exclusions.get(reason, 0) + 1
    return np.asarray(eligible, dtype=np.int64), dict(sorted(exclusions.items()))


def label_eligibility_rows(
    objects: Sequence[Mapping[str, Any]],
    *,
    atom: QueryAtom,
    lane: QueryLane,
    route_policy: QueryObjectFactRoutePolicy,
) -> list[dict[str, Any]]:
    """Audit pre-registered labels against the same hard candidate boundary.

    Eligible labels may be injected into an explicitly diagnostic judged pool
    to isolate reranker/role quality from first-stage recall.  They never enter
    the natural candidate union and never gain Evidence or numeric authority.
    """

    family = route_policy.family_by_facet().get(lane.facet_id)
    if family is None:
        raise QueryAtomShadowError("query_atom_facet_unrouted")
    object_kinds = {
        "bounded_parent_context" if form == "bounded_parent_context" else form
        for form in family.allowed_object_forms
    }
    request_period = atom.request_payload.get("period") or {}
    fiscal_years = {int(value) for value in request_period.get("fiscal_years") or ()}
    as_of = date.fromisoformat(lane.publication_date_lte)
    owner = lane.evidence_owner_tickers[0]
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    rows: list[dict[str, Any]] = []
    for judgement, object_ids in (
        ("positive", atom.positive_object_ids),
        ("hard_negative", atom.hard_negative_object_ids),
        ("unjudged", atom.unjudged_object_ids),
    ):
        for object_id in object_ids:
            row = objects_by_id.get(object_id)
            reason = (
                "compiled_object_missing"
                if row is None
                else _atom_object_exclusion_reason(
                    row,
                    owner=owner,
                    as_of=as_of,
                    source_types=lane.source_types,
                    object_kinds=object_kinds,
                    fiscal_years=fiscal_years,
                )
            )
            rows.append(
                {
                    "compiled_object_id": object_id,
                    "judgement": judgement,
                    "eligible": reason is None,
                    "exclusion_reason": reason,
                }
            )
    return rows


def evaluate_controlled_reranker(
    *,
    atom: QueryAtom,
    object_ids: Sequence[str],
    scores: Sequence[float],
    top_k: int,
) -> dict[str, Any]:
    """Evaluate an explicitly diagnostic pool with no runtime-candidate status."""

    if len(object_ids) != len(scores):
        raise QueryAtomShadowError("controlled_reranker_score_count_invalid")
    ranking = sorted(
        zip(object_ids, (float(value) for value in scores)),
        key=lambda row: (-row[1], row[0]),
    )
    return {
        **_ranking_evaluation(ranking, atom=atom, top_k=top_k),
        "pool_type": "diagnostic_judged_pool_not_runtime_candidate",
        "candidate_not_evidence": True,
        "numeric_authority": False,
    }


def evaluate_controlled_evidence_roles(
    *,
    atom: QueryAtom,
    lane: QueryLane,
    objects: Sequence[Mapping[str, Any]],
    controlled_object_ids: Sequence[str],
) -> dict[str, Any]:
    """Evaluate Evidence Role only on eligible pre-registered judged objects."""

    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    relationship = lane.relationship_constraints[0]
    owner = lane.evidence_owner_tickers[0]
    rows: list[dict[str, Any]] = []
    for object_id in controlled_object_ids:
        judgement = _judgement(atom, object_id)
        if judgement == "unjudged":
            continue
        row = objects_by_id[object_id]
        base = row["base_object_view"]
        role = evaluate_evidence_role(
            {
                "ticker": base.get("ticker"),
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
            relationship_direction=relationship,
        )
        rows.append(
            {
                "compiled_object_id": object_id,
                "judgement": judgement,
                "expected_roles": list(
                    atom.expected_roles_by_object_id.get(object_id, ())
                ),
                "evaluation": role.as_dict(),
            }
        )
    return {
        "pool_type": "diagnostic_judged_pool_not_runtime_candidate",
        "rows": rows,
        "metrics": aggregate_evidence_role_metrics(rows),
        "candidate_not_evidence": True,
        "numeric_authority": False,
    }


def _atom_object_exclusion_reason(
    row: Mapping[str, Any],
    *,
    owner: str,
    as_of: date,
    source_types: Sequence[str],
    object_kinds: set[str],
    fiscal_years: set[int],
) -> str | None:
    return _request_object_exclusion_reason(
        row,
        owners={owner},
        as_of=as_of,
        source_types=source_types,
        object_kinds=object_kinds,
        fiscal_years=fiscal_years,
    )


def _request_object_exclusion_reason(
    row: Mapping[str, Any],
    *,
    owners: set[str],
    as_of: date,
    source_types: Sequence[str],
    object_kinds: set[str],
    fiscal_years: set[int],
) -> str | None:
    base = row["base_object_view"]
    if str(base.get("ticker") or "").upper() not in owners:
        return "outside_evidence_owner_scope"
    try:
        published = date.fromisoformat(str(base.get("publication_date") or ""))
    except ValueError:
        return "publication_date_invalid"
    if published > as_of:
        return "after_research_as_of"
    if str(base.get("source_type") or "").upper() not in {
        value.upper() for value in source_types
    }:
        return "source_type_not_allowed"
    if str(row.get("object_kind") or "") not in object_kinds:
        return "object_form_not_allowed"
    if fiscal_years and base.get("fiscal_year") not in fiscal_years:
        return "reporting_period_outside_request"
    return None


def evaluate_query_atom(
    *,
    atom: QueryAtom,
    lane: QueryLane,
    route_policy: QueryObjectFactRoutePolicy,
    objects: Sequence[Mapping[str, Any]],
    document_embeddings: np.ndarray,
    query_embedding: np.ndarray,
    additional_dense_routes: Mapping[str, tuple[np.ndarray, np.ndarray]] | None = None,
    reranker_scorers: Mapping[
        str, Callable[[Sequence[tuple[str, str]]], Sequence[float]]
    ],
    first_stage_limit: int,
    candidate_union_limit: int,
    top_k: int,
) -> dict[str, Any]:
    eligible, exclusions = eligible_atom_indices(
        objects,
        atom=atom,
        lane=lane,
        route_policy=route_policy,
    )
    bm25 = bm25_rank(
        objects,
        eligible,
        lane.lexical_query,
        limit=first_stage_limit,
    )
    dense = dense_rank(
        objects,
        eligible,
        document_embeddings,
        query_embedding,
        limit=first_stage_limit,
    )
    dense_routes: dict[str, list[CandidateScore]] = {"bge_m3_dense": dense}
    for route_id, (route_documents, route_query) in (
        additional_dense_routes or {}
    ).items():
        if route_id in dense_routes:
            raise QueryAtomShadowError("query_atom_dense_route_duplicate")
        dense_routes[route_id] = dense_rank(
            objects,
            eligible,
            route_documents,
            route_query,
            limit=first_stage_limit,
        )
    candidate_ids = union_candidate_ids(
        (bm25, *dense_routes.values()), maximum=candidate_union_limit
    )
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    pairs = [
        (lane.semantic_query, str(objects_by_id[object_id]["model_text"]))
        for object_id in candidate_ids
    ]
    reranked: dict[str, Any] = {}
    for route_id, scorer in reranker_scorers.items():
        scores = list(float(value) for value in scorer(pairs))
        if len(scores) != len(candidate_ids):
            raise QueryAtomShadowError("query_atom_reranker_score_count_invalid")
        ranking = sorted(
            zip(candidate_ids, scores), key=lambda row: (-row[1], row[0])
        )
        reranked[route_id] = _ranking_evaluation(
            ranking,
            atom=atom,
            top_k=top_k,
        )
    role_rows = []
    relationship = lane.relationship_constraints[0]
    owner = lane.evidence_owner_tickers[0]
    for object_id in candidate_ids:
        row = objects_by_id[object_id]
        base = row["base_object_view"]
        role = evaluate_evidence_role(
            {
                "ticker": base.get("ticker"),
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
            relationship_direction=relationship,
        )
        judgement = _judgement(atom, object_id)
        role_rows.append(
            {
                "compiled_object_id": object_id,
                "judgement": judgement,
                "expected_roles": list(
                    atom.expected_roles_by_object_id.get(object_id, ())
                ),
                "evaluation": role.as_dict(),
            }
        )
    return {
        "atom_id": atom.atom_id,
        "request_id": str(atom.request_payload.get("request_id") or ""),
        "case_key": str(atom.request_payload.get("case_key") or ""),
        "slot_id": lane.slot_id,
        "facet_id": lane.facet_id,
        "evidence_owner_ticker": owner,
        "relationship_direction": relationship,
        "eligible_object_count": int(eligible.size),
        "exclusion_counts": exclusions,
        "first_stage": {
            "bm25_lexical": _candidate_route_evaluation(bm25, atom, top_k=top_k),
            **{
                route_id: _candidate_route_evaluation(
                    route_rows, atom, top_k=top_k
                )
                for route_id, route_rows in dense_routes.items()
            },
            "shared_candidate_union": _id_set_evaluation(candidate_ids, atom),
        },
        "candidate_union_ids": list(candidate_ids),
        "rerankers": reranked,
        "evidence_role": {
            "rows": role_rows,
            "metrics": aggregate_evidence_role_metrics(role_rows),
        },
        "candidate_not_evidence": True,
        "numeric_authority": False,
    }


def aggregate_query_atom_results(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    route_ids = sorted(
        {
            route_id
            for row in rows
            for route_id in row.get("rerankers") or {}
        }
    )
    rerankers: dict[str, Any] = {}
    for route_id in route_ids:
        values = [row["rerankers"][route_id] for row in rows]
        eligible = [value for value in values if value["pairwise_comparisons"]]
        rerankers[route_id] = {
            "atom_count": len(values),
            "positive_target_in_top_k_count": sum(
                value["positive_target_in_top_k"] for value in values
            ),
            "positive_target_available_count": sum(
                value["positive_target_available"] for value in values
            ),
            "pairwise_wins": sum(value["pairwise_wins"] for value in values),
            "pairwise_comparisons": sum(
                value["pairwise_comparisons"] for value in values
            ),
            "eligible_pairwise_atom_count": len(eligible),
        }
        comparisons = rerankers[route_id]["pairwise_comparisons"]
        rerankers[route_id]["pairwise_accuracy"] = (
            round(rerankers[route_id]["pairwise_wins"] / comparisons, 6)
            if comparisons
            else None
        )
    role_rows = [
        role_row
        for row in rows
        for role_row in row["evidence_role"]["rows"]
        if role_row["judgement"] != "unjudged"
    ]
    return {
        "atom_count": len(rows),
        "case_count": len({str(row["case_key"]) for row in rows}),
        "gap_atom_count": sum(
            not any(
                route["positive_target_available"]
                for route in row["rerankers"].values()
            )
            for row in rows
        ),
        "rerankers": rerankers,
        "evidence_role": aggregate_evidence_role_metrics(role_rows),
    }


def _candidate_route_evaluation(
    rows: Sequence[CandidateScore], atom: QueryAtom, *, top_k: int
) -> dict[str, Any]:
    ranking = [(row.compiled_object_id, float(row.score)) for row in rows]
    return _ranking_evaluation(ranking, atom=atom, top_k=top_k)


def _ranking_evaluation(
    ranking: Sequence[tuple[str, float]], *, atom: QueryAtom, top_k: int
) -> dict[str, Any]:
    rank_by_id = {object_id: rank for rank, (object_id, _) in enumerate(ranking, 1)}
    positives = [
        object_id for object_id in atom.positive_object_ids if object_id in rank_by_id
    ]
    negatives = [
        object_id
        for object_id in atom.hard_negative_object_ids
        if object_id in rank_by_id
    ]
    comparisons = [(positive, negative) for positive in positives for negative in negatives]
    wins = sum(rank_by_id[positive] < rank_by_id[negative] for positive, negative in comparisons)
    best_positive = min((rank_by_id[value] for value in positives), default=None)
    return {
        "positive_target_available": bool(atom.positive_object_ids),
        "positive_target_in_ranking": bool(positives),
        "positive_target_rank": best_positive,
        "positive_target_in_top_k": best_positive is not None and best_positive <= top_k,
        "hard_negative_in_ranking_count": len(negatives),
        "pairwise_wins": wins,
        "pairwise_comparisons": len(comparisons),
        "top_ids": [object_id for object_id, _ in ranking[:top_k]],
    }


def _id_set_evaluation(ids: Sequence[str], atom: QueryAtom) -> dict[str, Any]:
    values = set(ids)
    return {
        "candidate_count": len(ids),
        "positive_target_available": bool(atom.positive_object_ids),
        "positive_target_in_pool": bool(values.intersection(atom.positive_object_ids)),
        "positive_ids_in_pool": sorted(values.intersection(atom.positive_object_ids)),
        "hard_negative_ids_in_pool": sorted(
            values.intersection(atom.hard_negative_object_ids)
        ),
        "unjudged_ids_in_pool": sorted(values.intersection(atom.unjudged_object_ids)),
    }


def aggregate_evidence_role_metrics(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    judged = [row for row in rows if row["judgement"] != "unjudged"]
    positives = [row for row in judged if row["judgement"] == "positive"]
    negatives = [row for row in judged if row["judgement"] == "hard_negative"]
    positive_compatible = sum(
        row["evaluation"]["compatibility"] == "compatible" for row in positives
    )
    negative_not_compatible = sum(
        row["evaluation"]["compatibility"] != "compatible" for row in negatives
    )
    tp = fp = fn = 0
    for row in rows:
        expected = set(row.get("expected_roles") or ())
        if not expected:
            continue
        predicted = set(row["evaluation"]["labels"])
        tp += len(expected & predicted)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    return {
        "positive_count": len(positives),
        "hard_negative_count": len(negatives),
        "positive_compatible_rate": (
            round(positive_compatible / len(positives), 6) if positives else None
        ),
        "hard_negative_suppressed_or_abstained_rate": (
            round(negative_not_compatible / len(negatives), 6) if negatives else None
        ),
        "multilabel_true_positive": tp,
        "multilabel_false_positive": fp,
        "multilabel_false_negative": fn,
        "multilabel_micro_precision": round(precision, 6) if precision is not None else None,
        "multilabel_micro_recall": round(recall, 6) if recall is not None else None,
        "multilabel_micro_f1": round(f1, 6) if f1 is not None else None,
    }


def _judgement(atom: QueryAtom, object_id: str) -> str:
    if object_id in atom.positive_object_ids:
        return "positive"
    if object_id in atom.hard_negative_object_ids:
        return "hard_negative"
    return "unjudged"


def _all_labels(atom: QueryAtom) -> tuple[str, ...]:
    return (
        *atom.positive_object_ids,
        *atom.hard_negative_object_ids,
        *atom.unjudged_object_ids,
    )


def _unique_ids(values: Iterable[object]) -> tuple[str, ...]:
    output = tuple(str(value).strip() for value in values)
    if not all(output) or len(output) != len(set(output)):
        raise QueryAtomShadowError("query_atom_eval_label_identity_invalid")
    return output


__all__ = [
    "QUERY_ATOM_LABEL_ADJUDICATION_SCHEMA_VERSION",
    "QUERY_ATOM_EVAL_SCHEMA_VERSION",
    "QUERY_ATOM_EVAL_SCHEMA_VERSIONS",
    "QUERY_ATOM_EVAL_SENTENCE_OBJECT_SUCCESSOR_SCHEMA_VERSION",
    "QUERY_ATOM_EVAL_SUCCESSOR_SCHEMA_VERSION",
    "QueryAtom",
    "QueryAtomShadowError",
    "apply_query_atom_label_adjudications",
    "aggregate_evidence_role_metrics",
    "aggregate_query_atom_results",
    "compile_atom_lane",
    "eligible_atom_indices",
    "eligible_request_indices",
    "evaluate_controlled_evidence_roles",
    "evaluate_controlled_reranker",
    "evaluate_query_atom",
    "label_eligibility_rows",
    "load_query_atoms",
]
