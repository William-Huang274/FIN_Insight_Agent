from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import date
from typing import Any, Mapping, Sequence

from .query_plan import QueryLane, canonical_digest


OBJECT_DECISION_LEDGER_SCHEMA_VERSION = (
    "fin_ia_s1_object_candidate_decision_ledger_v1_0"
)
OBJECT_COVERAGE_SCHEMA_VERSION = "fin_ia_s1_object_coverage_state_v1_0"
OBJECT_READINESS_SCHEMA_VERSION = "fin_ia_s1_object_pack_readiness_v1_0"
OBJECT_WORKBENCH_SCHEMA_VERSION = "fin_ia_s1_object_workbench_projection_v1_0"

DECISION_STATES = ("accepted", "rejected", "unjudged", "needs_review")
REVIEW_JUDGEMENTS = frozenset({"positive", "hard_negative", "unjudged"})


class ObjectCandidateDecisionError(ValueError):
    """Raised when object-level decision lineage or authority is ambiguous."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ObjectCandidateDecisionError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _as_date(value: object, code: str) -> date:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError as exc:
        raise ObjectCandidateDecisionError(code) from exc


def _candidate_gate_reason(
    row: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
    lane: QueryLane,
) -> str | None:
    base = _mapping(row.get("base_object_view"), "object_decision_base_view_missing")
    if row.get("candidate_not_evidence") is not True:
        return "candidate_authority_boundary_invalid"
    if row.get("evidence_promoted") is not False:
        return "candidate_was_already_promoted"
    if row.get("numeric_authority") is not False:
        return "candidate_numeric_authority_invalid"
    if str(base.get("ticker") or "").upper() not in set(lane.evidence_owner_tickers):
        return "candidate_owner_outside_compiled_lane"
    if str(base.get("source_type") or "") not in set(lane.source_types):
        return "candidate_source_type_outside_compiled_lane"
    if _as_date(base.get("publication_date"), "candidate_publication_date_invalid") > _as_date(
        request.get("research_as_of"), "candidate_research_as_of_invalid"
    ):
        return "candidate_after_research_as_of"
    if str(request.get("case_key") or "").upper() != str(
        request.get("subject_ticker") or ""
    ).upper():
        return "request_case_subject_mismatch"
    return None


def _pack_items_by_source(
    evidence_pack: Mapping[str, Any],
) -> tuple[dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]], dict[str, Any]]:
    materials = {
        str(row.get("material_ref") or ""): dict(row)
        for row in evidence_pack.get("source_materials") or ()
        if isinstance(row, Mapping)
    }
    by_source: dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {}
    by_digest: dict[str, Any] = {}
    for raw in evidence_pack.get("evidence_items") or ():
        item = _mapping(raw, "object_decision_pack_item_invalid")
        digest = str(item.get("evidence_item_digest") or "")
        source_id = str(item.get("source_record_id") or "")
        source = item.get("source")
        material = (
            dict(source)
            if isinstance(source, Mapping)
            else materials.get(str(item.get("source_material_ref") or ""))
        )
        _require(digest and source_id and material is not None, "object_decision_pack_lineage_missing")
        by_source.setdefault(source_id, []).append((item, material))
        by_digest[digest] = item
    return by_source, by_digest


def _pack_item_gate_reason(
    item: Mapping[str, Any],
    material: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
    lane: QueryLane,
) -> str | None:
    if str(item.get("case_key") or "").upper() != str(
        request.get("case_key") or ""
    ).upper():
        return "cross_case_reviewed_item"
    if item.get("writer_citable") is not True:
        return "reviewed_item_not_writer_citable"
    if str(material.get("evidence_owner_ticker") or "").upper() not in set(
        lane.evidence_owner_tickers
    ):
        return "reviewed_item_owner_outside_compiled_lane"
    if str(material.get("source_type") or "") not in set(lane.source_types):
        return "reviewed_item_source_type_outside_compiled_lane"
    if _as_date(item.get("publication_date"), "reviewed_item_publication_date_invalid") > _as_date(
        request.get("research_as_of"), "reviewed_item_research_as_of_invalid"
    ):
        return "reviewed_item_after_research_as_of"
    item_slots = {
        str(binding.get("slot_id") or "")
        for binding in item.get("slot_bindings") or ()
        if isinstance(binding, Mapping)
    }
    if lane.slot_id not in item_slots:
        return "reviewed_item_outside_compiled_slot"
    directions = {
        _direction_family(str(value))
        for value in item.get("relationship_directions") or ()
    }
    lane_direction = _direction_family(lane.relationship_constraints[0])
    if directions and lane_direction not in directions:
        return "reviewed_item_relationship_direction_mismatch"
    period = _mapping(request.get("period"), "object_decision_request_period_invalid")
    period_end = str(
        item.get("source_reporting_period_end")
        or material.get("period_end")
        or ""
    )
    start = str(period.get("start_date") or "")
    end = str(period.get("end_date") or "")
    if start and (not period_end or period_end < start):
        return "reviewed_item_before_request_period"
    if end and (not period_end or period_end > end):
        return "reviewed_item_after_request_period"
    return None


def _direction_family(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized == "subject_self_disclosure":
        return "subject_self_disclosure"
    if normalized in {
        "customer_or_demand_signal_to_subject",
        "customer_or_ecosystem_to_subject",
        "customer_to_subject",
        "end_demand_context",
        "evidence_owner_own_infrastructure_demand",
        "consumer_case_ecosystem_readthrough_only",
    }:
        return "downstream_or_demand_context"
    if normalized in {
        "supplier_to_subject",
        "upstream_foundry_context",
        "upstream_supplier_to_subject",
        "evidence_owner_own_supply_capacity_or_constraint",
    }:
        return "upstream_or_supply_context"
    return normalized


def _review_relation(
    reviewed_relations: Mapping[str, Mapping[str, Any]], object_id: str
) -> Mapping[str, Any] | None:
    relation = reviewed_relations.get(object_id)
    if relation is None:
        return None
    judgement = str(relation.get("judgement") or "")
    _require(judgement in REVIEW_JUDGEMENTS, "object_decision_review_judgement_invalid")
    return relation


def compile_object_candidate_decision_ledger(
    *,
    request: Mapping[str, Any],
    lane: QueryLane,
    ranked_object_ids: Sequence[str],
    objects_by_id: Mapping[str, Mapping[str, Any]],
    reviewed_relations: Mapping[str, Mapping[str, Any]],
    evidence_pack: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    """Decide candidates only after ranking, at compiled-object granularity.

    A reviewed source segment alone is insufficient. Reuse of existing Evidence
    additionally requires a positive review relation for this exact compiled
    object. Development labels may prove the seam but never promote candidate
    text or grant runtime Evidence authority.
    """

    ids = tuple(str(value) for value in ranked_object_ids)
    _require(ids and len(ids) == len(set(ids)), "object_decision_candidate_ids_invalid")
    case_key = str(request.get("case_key") or "").upper()
    _require(
        case_key and str(evidence_pack.get("case_key") or "").upper() == case_key,
        "object_decision_pack_case_mismatch",
    )
    items_by_source, _ = _pack_items_by_source(evidence_pack)
    decisions: list[dict[str, Any]] = []
    accepted_evidence: set[str] = set()
    accepted_objects: set[str] = set()
    for rank, object_id in enumerate(ids, start=1):
        row = objects_by_id.get(object_id)
        _require(row is not None, f"object_decision_candidate_missing:{object_id}")
        base = _mapping(row.get("base_object_view"), "object_decision_base_view_missing")
        lineage = {
            str(base.get("source_record_id") or ""),
            *(str(value) for value in row.get("lineage_source_record_ids") or ()),
        }
        lineage.discard("")
        matches = [
            pair for source_id in lineage for pair in items_by_source.get(source_id, ())
        ]
        eligible_matches = [
            (item, material)
            for item, material in matches
            if _pack_item_gate_reason(
                item, material, request=request, lane=lane
            )
            is None
        ]
        candidate_reason = _candidate_gate_reason(row, request=request, lane=lane)
        relation = _review_relation(reviewed_relations, object_id)
        judgement = str(relation.get("judgement")) if relation is not None else None
        accepted_digests: list[str] = []

        if candidate_reason is not None:
            state = "rejected"
            reasons = [candidate_reason]
            authority = "hard_candidate_boundary"
        elif judgement == "hard_negative":
            state = "rejected"
            reasons = ["exact_object_reviewed_hard_negative"]
            authority = "development_object_relation_review"
        elif judgement == "unjudged":
            state = "unjudged"
            reasons = ["exact_object_relation_requires_further_review"]
            authority = "development_object_relation_review"
        elif judgement == "positive" and eligible_matches:
            state = "accepted"
            accepted_digests = sorted(
                {
                    str(item.get("evidence_item_digest") or "")
                    for item, _ in eligible_matches
                }
            )
            reasons = [
                "exact_compiled_object_positive_relation",
                "reviewed_pack_source_slot_period_relationship_gate_passed",
            ]
            authority = "capture_bound_reviewed_evidence_gate_reused"
            accepted_evidence.update(accepted_digests)
            accepted_objects.add(object_id)
        elif judgement == "positive":
            state = "needs_review"
            reasons = ["positive_development_object_not_bound_to_current_reviewed_pack"]
            authority = "development_relation_without_product_pack_authority"
        elif eligible_matches:
            state = "needs_review"
            reasons = ["reviewed_source_lineage_without_object_relation"]
            authority = "source_review_does_not_authorize_child_object"
        elif matches:
            state = "rejected"
            reasons = sorted(
                {
                    reason
                    for item, material in matches
                    if (
                        reason := _pack_item_gate_reason(
                            item, material, request=request, lane=lane
                        )
                    )
                    is not None
                }
            ) or ["reviewed_source_binding_gate_failed"]
            authority = "reviewed_pack_binding_gate_rejection"
        else:
            state = "needs_review"
            reasons = ["candidate_not_present_in_current_reviewed_pack"]
            authority = "candidate_only_no_evidence_authority"

        decision_body = {
            "candidate_ref": "CANDOBJ::" + canonical_digest(
                {
                    "request_id": request.get("request_id"),
                    "compiled_object_id": object_id,
                }
            )[:24].upper(),
            "compiled_object_id": object_id,
            "source_record_id": str(base.get("source_record_id") or ""),
            "lineage_source_record_ids": sorted(lineage),
            "rank": rank,
            "subject_ticker": request.get("subject_ticker"),
            "evidence_owner_ticker": base.get("ticker"),
            "source_type": base.get("source_type"),
            "publication_date": base.get("publication_date"),
            "object_kind": row.get("object_kind"),
            "review_judgement": judgement,
            "decision_state": state,
            "reason_codes": reasons,
            "decision_authority": authority,
            "accepted_evidence_item_digests": accepted_digests,
            "candidate_text_promoted": False,
            "numeric_authority": False,
            "runtime_evidence_promotion": False,
        }
        decisions.append(
            {**decision_body, "decision_digest": canonical_digest(decision_body)}
        )

    counts = Counter(row["decision_state"] for row in decisions)
    body = {
        "schema_version": OBJECT_DECISION_LEDGER_SCHEMA_VERSION,
        "status": "object_level_candidate_decisions_materialized",
        "recorded_at": recorded_at,
        "case_key": case_key,
        "research_as_of": request.get("research_as_of"),
        "request_id": request.get("request_id"),
        "request_digest": canonical_digest(dict(request)),
        "slot_id": lane.slot_id,
        "facet_id": lane.facet_id,
        "candidate_count": len(decisions),
        "decision_counts": {state: counts.get(state, 0) for state in DECISION_STATES},
        "accepted_compiled_object_ids": sorted(accepted_objects),
        "accepted_evidence_item_digests": sorted(accepted_evidence),
        "decisions": decisions,
        "authority": {
            "rank_never_grants_evidence_authority": True,
            "reviewed_source_alone_cannot_authorize_child_object": True,
            "exact_object_relation_and_reviewed_pack_binding_required": True,
            "development_labels_joined_after_ranking": True,
            "candidate_text_promoted": False,
            "numeric_authority": False,
            "runtime_evidence_promotion": False,
        },
    }
    return {**body, "candidate_decision_ledger_digest": canonical_digest(body)}


def compile_object_coverage_state(
    *,
    request: Mapping[str, Any],
    lane: QueryLane,
    decision_ledger: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    accepted_objects = list(decision_ledger.get("accepted_compiled_object_ids") or ())
    accepted_evidence = list(decision_ledger.get("accepted_evidence_item_digests") or ())
    counts = _mapping(decision_ledger.get("decision_counts"), "object_coverage_counts_missing")
    relevant_items = [
        row
        for row in evidence_pack.get("evidence_items") or ()
        if isinstance(row, Mapping)
        and any(
            isinstance(binding, Mapping)
            and str(binding.get("slot_id") or "") == lane.slot_id
            for binding in row.get("slot_bindings") or ()
        )
    ]
    relevant_digests = {
        str(row.get("evidence_item_digest") or "") for row in relevant_items
    }
    gap_rows = [
        deepcopy(dict(row))
        for row in evidence_pack.get("residual_gaps") or ()
        if isinstance(row, Mapping)
        and str(row.get("slot_id") or "") == lane.slot_id
    ]
    gap_receipts = []
    for gap in gap_rows:
        receipt_body = {
            "gap_id": str(gap.get("gap_id") or ""),
            "gap_code": str(gap.get("gap_code") or ""),
            "owning_stage": "S1",
            "classification": "declared_pack_gap_not_public_information_absence",
            "eligible_as_true_public_information_gap": False,
            "checks": {
                "local_objects_checked": True,
                "request_scoped_candidate_generation_executed": True,
                "object_level_candidate_decisions_materialized": True,
                "official_supplement_route_executed_for_this_gap": False,
                "external_supplement_route_executed_for_this_gap": False,
                "route_budget_sufficiency_proven": False,
            },
            "disposition": "supplement_or_object_review_still_required",
            "last_checked_at": recorded_at,
        }
        gap_receipts.append(
            {**receipt_body, "receipt_digest": canonical_digest(receipt_body)}
        )
    coverage_state = (
        "accepted_object_evidence_with_unresolved_gaps"
        if accepted_objects and gap_receipts
        else "accepted_object_evidence"
        if accepted_objects
        else "object_relation_review_required"
        if int(counts.get("needs_review") or 0) or int(counts.get("unjudged") or 0)
        else "no_accepted_object_evidence"
    )
    body = {
        "schema_version": OBJECT_COVERAGE_SCHEMA_VERSION,
        "status": "object_level_proposition_coverage_materialized",
        "recorded_at": recorded_at,
        "case_key": request.get("case_key"),
        "research_as_of": request.get("research_as_of"),
        "proposition_id": "PROP::" + canonical_digest(
            {
                "request_id": request.get("request_id"),
                "slot_id": lane.slot_id,
                "facet_id": lane.facet_id,
                "metric_intents": request.get("metric_intents") or [],
                "product_intents": request.get("product_intents") or [],
            }
        )[:24].upper(),
        "research_question": request.get("stop_condition"),
        "request_id": request.get("request_id"),
        "slot_id": lane.slot_id,
        "facet_id": lane.facet_id,
        "coverage_state": coverage_state,
        "accepted_compiled_object_ids": accepted_objects,
        "accepted_evidence_item_digests": accepted_evidence,
        "reviewed_evidence_not_recalled_digests": sorted(
            relevant_digests - set(accepted_evidence)
        ),
        "candidate_decision_counts": dict(counts),
        "gap_eligibility_receipts": gap_receipts,
        "known": {
            "accepted_object_ids": accepted_objects,
            "accepted_reviewed_evidence_digests": accepted_evidence,
        },
        "unknown": [str(row.get("business_reason_zh") or "") for row in gap_rows],
        "why_unknown": (
            [
                "Object-level review or a bounded supplement route remains incomplete.",
                "No retrieval miss is treated as proof that public information does not exist.",
            ]
            if gap_rows or not accepted_objects
            else []
        ),
    }
    return {**body, "coverage_state_digest": canonical_digest(body)}


def compile_object_pack_readiness(
    *,
    coverage: Mapping[str, Any],
    decision_ledger: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
    pack_artifact_digest: str,
    recorded_at: str,
) -> dict[str, Any]:
    counts = _mapping(decision_ledger.get("decision_counts"), "object_readiness_counts_missing")
    _require(
        sum(int(value) for value in counts.values())
        == int(decision_ledger.get("candidate_count") or 0),
        "object_readiness_decision_ledger_incomplete",
    )
    accepted = len(coverage.get("accepted_compiled_object_ids") or ())
    needs_review = int(counts.get("needs_review") or 0) + int(counts.get("unjudged") or 0)
    state = (
        "ready_for_development_replay_not_runtime_promotion"
        if accepted
        else "not_ready_object_relation_review_required"
        if needs_review
        else "not_ready_no_accepted_object_evidence"
    )
    body = {
        "schema_version": OBJECT_READINESS_SCHEMA_VERSION,
        "status": "object_level_pack_readiness_materialized",
        "recorded_at": recorded_at,
        "case_key": coverage.get("case_key"),
        "research_as_of": coverage.get("research_as_of"),
        "proposition_id": coverage.get("proposition_id"),
        "readiness_state": state,
        "pack_binding": {
            "case_key": evidence_pack.get("case_key"),
            "artifact_digest": pack_artifact_digest,
            "pack_payload_digest": evidence_pack.get("pack_payload_digest"),
        },
        "checks": {
            "all_candidates_have_persistent_object_decisions": True,
            "source_only_false_accept_prevented": True,
            "hard_negative_candidate_promoted": False,
            "candidate_text_promoted": False,
            "false_public_gap_prevented": True,
            "runtime_evidence_promotion_authorized": False,
            "complete_product_conclusion_ready": False,
            "S1_qualified_stable": False,
        },
        "accepted_object_count": accepted,
        "object_relation_review_queue_count": needs_review,
        "unresolved_gap_count": len(coverage.get("gap_eligibility_receipts") or ()),
        "known_boundary": (
            "This development projection proves object-level decision lineage against "
            "the current reviewed Pack. It does not turn qrel labels into runtime "
            "Evidence authority or qualify S1."
        ),
    }
    return {**body, "readiness_digest": canonical_digest(body)}


def compile_object_workbench_projection(
    *,
    decision_ledger: Mapping[str, Any],
    coverage: Mapping[str, Any],
    readiness: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    body = {
        "schema_version": OBJECT_WORKBENCH_SCHEMA_VERSION,
        "status": "object_level_s1_lineage_ready",
        "recorded_at": recorded_at,
        "case_key": readiness.get("case_key"),
        "research_as_of": readiness.get("research_as_of"),
        "proposition_id": readiness.get("proposition_id"),
        "readiness_state": readiness.get("readiness_state"),
        "candidate_decision_summary": deepcopy(
            decision_ledger.get("decision_counts") or {}
        ),
        "coverage_summary": {
            "coverage_state": coverage.get("coverage_state"),
            "accepted_object_count": len(
                coverage.get("accepted_compiled_object_ids") or ()
            ),
            "reviewed_not_recalled_count": len(
                coverage.get("reviewed_evidence_not_recalled_digests") or ()
            ),
            "unresolved_gap_count": len(
                coverage.get("gap_eligibility_receipts") or ()
            ),
        },
        "decision_rows": [
            {
                key: deepcopy(row.get(key))
                for key in (
                    "candidate_ref",
                    "compiled_object_id",
                    "source_record_id",
                    "rank",
                    "evidence_owner_ticker",
                    "source_type",
                    "publication_date",
                    "object_kind",
                    "review_judgement",
                    "decision_state",
                    "reason_codes",
                    "decision_authority",
                    "accepted_evidence_item_digests",
                    "candidate_text_promoted",
                    "runtime_evidence_promotion",
                    "decision_digest",
                )
            }
            for row in decision_ledger.get("decisions") or ()
        ],
        "gap_eligibility_receipts": deepcopy(
            coverage.get("gap_eligibility_receipts") or []
        ),
        "pack_binding": deepcopy(readiness.get("pack_binding") or {}),
        "hard_boundaries": {
            "candidate_is_not_evidence": True,
            "rank_never_grants_evidence_authority": True,
            "reviewed_source_alone_cannot_authorize_child_object": True,
            "unexecuted_route_is_not_public_information_gap": True,
            "runtime_evidence_promotion_authorized": False,
            "complete_product_conclusion_ready": False,
            "S1_qualified_stable": False,
        },
    }
    return {**body, "workbench_projection_digest": canonical_digest(body)}


__all__ = [
    "DECISION_STATES",
    "OBJECT_COVERAGE_SCHEMA_VERSION",
    "OBJECT_DECISION_LEDGER_SCHEMA_VERSION",
    "OBJECT_READINESS_SCHEMA_VERSION",
    "OBJECT_WORKBENCH_SCHEMA_VERSION",
    "ObjectCandidateDecisionError",
    "compile_object_candidate_decision_ledger",
    "compile_object_coverage_state",
    "compile_object_pack_readiness",
    "compile_object_workbench_projection",
]
