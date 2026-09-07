from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Mapping, Sequence

from .candidate_decision import (
    _as_date,
    _direction_family,
    _pack_items_by_source,
)
from .query_plan import canonical_digest


PRODUCT_DECISION_LEDGER_SCHEMA_VERSION = (
    "fin_ia_s1_product_candidate_decision_ledger_v1_2"
)
PRODUCT_DECISION_STATES = (
    "accepted",
    "rejected",
    "unjudged",
    "needs_human_review",
)
PRODUCT_PACK_READINESS_SCHEMA_VERSION = (
    "fin_ia_s1_product_pack_readiness_v1_2"
)
GAP_ELIGIBILITY_RECEIPT_SCHEMA_VERSION = (
    "fin_ia_s1_gap_eligibility_receipt_v1_0"
)

READINESS_STATES = (
    "ready_for_current_scope",
    "partial_with_material_gaps",
    "blocked_by_source_access",
    "blocked_by_local_data_materialization",
    "blocked_by_candidate_coverage",
    "blocked_by_retrieval_quality",
    "blocked_by_evidence_admission",
    "blocked_by_numeric_or_bridge_authority",
    "candidate_audit_only_explicit_scope_pending",
)


class ProductPackReadinessError(ValueError):
    """Raised when S1 product readiness cannot be traced without ambiguity."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ProductPackReadinessError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _product_lane(request_result: Mapping[str, Any]) -> Mapping[str, Any]:
    lanes = list(request_result.get("lanes") or ())
    _require(len(lanes) == 1, "product_candidate_decision_lane_count_invalid")
    lane = _mapping(
        _mapping(lanes[0], "product_candidate_decision_lane_projection_invalid").get(
            "lane"
        ),
        "product_candidate_decision_lane_missing",
    )
    _require(
        str(lane.get("slot_id") or "") and str(lane.get("facet_id") or ""),
        "product_candidate_decision_lane_identity_missing",
    )
    return lane


def _product_pack_item_gate_reasons(
    item: Mapping[str, Any],
    material: Mapping[str, Any],
    *,
    seed: Mapping[str, Any],
    request: Mapping[str, Any],
    lane: Mapping[str, Any],
) -> tuple[str, ...]:
    reasons: list[str] = []
    object_id = str(seed.get("compiled_object_id") or "")
    if str(item.get("compiled_object_id") or "") != object_id:
        reasons.append("reviewed_item_not_bound_to_exact_compiled_object")
    if str(item.get("case_key") or "").upper() != str(
        request.get("case_key") or ""
    ).upper():
        reasons.append("cross_case_reviewed_item")
    if item.get("writer_citable") is not True:
        reasons.append("reviewed_item_not_writer_citable")
    if not str(item.get("disposition") or "").startswith("accepted_"):
        reasons.append("reviewed_item_not_accepted")
    owner = str(seed.get("ticker") or "").upper()
    allowed_owners = {
        str(value).upper() for value in lane.get("evidence_owner_tickers") or ()
    }
    if owner not in allowed_owners or str(
        material.get("evidence_owner_ticker") or ""
    ).upper() != owner:
        reasons.append("reviewed_item_owner_outside_compiled_lane")
    if str(material.get("source_type") or "") != str(
        seed.get("source_type") or ""
    ):
        reasons.append("reviewed_item_source_type_mismatch")
    if str(material.get("source_type") or "") not in {
        str(value) for value in lane.get("source_types") or ()
    }:
        reasons.append("reviewed_item_source_type_outside_compiled_lane")
    if _as_date(
        item.get("publication_date"), "product_reviewed_item_publication_date_invalid"
    ) > _as_date(
        request.get("research_as_of"), "product_reviewed_item_research_as_of_invalid"
    ):
        reasons.append("reviewed_item_after_research_as_of")
    matching_slots = [
        binding
        for binding in item.get("slot_bindings") or ()
        if isinstance(binding, Mapping)
        and str(binding.get("slot_id") or "") == str(lane.get("slot_id") or "")
    ]
    if not matching_slots:
        reasons.append("reviewed_item_outside_compiled_slot")
    elif str(lane.get("facet_id") or "") not in {
        str(facet)
        for binding in matching_slots
        for facet in binding.get("facet_ids") or ()
    }:
        reasons.append("reviewed_item_facet_not_bound_to_current_request")
    relationship_by_owner = {
        str(row.get("evidence_owner_ticker") or "").upper(): _direction_family(
            str(row.get("relationship_direction") or "")
        )
        for row in lane.get("owner_queries") or ()
        if isinstance(row, Mapping)
    }
    expected_direction = relationship_by_owner.get(owner)
    observed_directions = {
        _direction_family(str(value))
        for value in item.get("relationship_directions") or ()
    }
    if (
        expected_direction
        and observed_directions
        and expected_direction not in observed_directions
    ):
        reasons.append("reviewed_item_relationship_direction_mismatch")
    period = _mapping(
        request.get("period"), "product_candidate_decision_request_period_invalid"
    )
    period_end = str(
        item.get("source_reporting_period_end")
        or material.get("period_end")
        or ""
    )
    start = str(period.get("start_date") or "")
    end = str(period.get("end_date") or "")
    if start and (not period_end or period_end < start):
        reasons.append("reviewed_item_before_request_period")
    if end and (not period_end or period_end > end):
        reasons.append("reviewed_item_after_request_period")
    return tuple(sorted(set(reasons)))


def _reviewed_item_requirement_binding(
    item: Mapping[str, Any],
    *,
    lane: Mapping[str, Any],
    selected_requirement_ids: Sequence[str],
    request_requirement_ids: frozenset[str],
) -> tuple[tuple[str, ...], str]:
    """Resolve one reviewed Evidence item to the propositions it can satisfy.

    A slot/facet match is necessary but no longer sufficient when a candidate is
    reserved for several material requirements.  New successor packs name the
    exact requirement IDs on their slot binding.  That reviewed binding may
    correct the automatic selector, but only within the current request's
    declared requirement set.  The legacy fallback is intentionally limited to
    one automatically selected requirement; a multi-requirement candidate
    without an explicit binding fails closed for Evidence reuse.
    """

    selected = {str(value) for value in selected_requirement_ids if str(value)}
    matching_bindings = [
        binding
        for binding in item.get("slot_bindings") or ()
        if isinstance(binding, Mapping)
        and str(binding.get("slot_id") or "") == str(lane.get("slot_id") or "")
        and str(lane.get("facet_id") or "")
        in {str(value) for value in binding.get("facet_ids") or ()}
    ]
    explicit = {
        str(requirement_id)
        for binding in matching_bindings
        for requirement_id in binding.get("requirement_ids") or ()
        if str(requirement_id)
    }
    if explicit:
        _require(
            explicit <= request_requirement_ids,
            "reviewed_item_requirement_outside_current_request",
        )
        return tuple(sorted(explicit)), "explicit_requirement_binding"
    if len(selected) == 1:
        return tuple(sorted(selected)), "legacy_single_requirement_unambiguous"
    return (), "missing_or_ambiguous_requirement_binding"


def _request_material_requirement_ids(
    hybrid: Mapping[str, Any],
    *,
    seeds: Sequence[Mapping[str, Any]],
) -> frozenset[str]:
    material = hybrid.get("material_evidence")
    if isinstance(material, Mapping):
        plan = _mapping(
            material.get("requirement_plan"),
            "product_candidate_decision_requirement_plan_missing",
        )
        requirement_ids = frozenset(
            str(row.get("requirement_id") or "")
            for row in plan.get("requirement_groups") or ()
            if isinstance(row, Mapping)
        )
    else:
        requirement_ids = frozenset(
            str(requirement_id)
            for seed in seeds
            for requirement_id in seed.get("selected_requirement_ids") or ()
            if str(requirement_id)
        )
    _require(
        bool(requirement_ids) and all(requirement_ids),
        "product_candidate_decision_requirement_set_invalid",
    )
    return requirement_ids


def _candidate_adjudications_by_object(
    evidence_pack: Mapping[str, Any], *, request_id: str
) -> dict[str, Mapping[str, Any]]:
    output: dict[str, Mapping[str, Any]] = {}
    for raw_receipt in evidence_pack.get("candidate_adjudication_receipts") or ():
        receipt = _mapping(
            raw_receipt, "product_candidate_adjudication_receipt_invalid"
        )
        if str(receipt.get("request_id") or "") != request_id:
            continue
        body = dict(receipt)
        digest = str(body.pop("decision_receipt_digest", ""))
        object_id = str(receipt.get("compiled_object_id") or "")
        action = str(receipt.get("action") or "")
        _require(
            digest == canonical_digest(body)
            and object_id
            and object_id not in output
            and action
            in {
                "accept_for_requirements",
                "accept_for_request_context",
                "reject_for_current_scope",
                "delegate_to_s2_numeric_authority",
            }
            and receipt.get("candidate_text_promoted") is False
            and receipt.get("numeric_authority_granted") is False
            and receipt.get("S1_qualification_authorized") is False,
            "product_candidate_adjudication_receipt_binding_invalid",
        )
        output[object_id] = receipt
    return output


def compile_product_candidate_decision_ledger(
    *,
    request_result: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    """Decide the full product candidate union without promoting new text."""

    request = _mapping(
        request_result.get("request"), "product_candidate_decision_request_missing"
    )
    hybrid = _mapping(
        request_result.get("hybrid_object_retrieval"),
        "product_candidate_decision_hybrid_result_missing",
    )
    lane = _product_lane(request_result)
    case_key = str(request.get("case_key") or "").upper()
    _require(
        case_key and str(evidence_pack.get("case_key") or "").upper() == case_key,
        "product_candidate_decision_pack_case_mismatch",
    )
    seeds = list(hybrid.get("candidate_decision_seed") or ())
    expected_count = int(
        _mapping(
            hybrid.get("summary"), "product_candidate_decision_summary_missing"
        ).get("union_count_before_source_quota")
        or 0
    )
    _require(
        seeds and len(seeds) == expected_count,
        "product_candidate_decision_seed_cardinality_invalid",
    )
    request_requirement_ids = _request_material_requirement_ids(
        hybrid, seeds=seeds
    )
    adjudications_by_object = _candidate_adjudications_by_object(
        evidence_pack, request_id=str(request.get("request_id") or "")
    )
    seed_ids = [
        str(
            _mapping(row, "product_candidate_decision_seed_invalid").get(
                "compiled_object_id"
            )
            or ""
        )
        for row in seeds
    ]
    _require(
        all(seed_ids) and len(seed_ids) == len(set(seed_ids)),
        "product_candidate_decision_seed_identity_invalid",
    )
    items_by_source, _ = _pack_items_by_source(evidence_pack)
    decisions: list[dict[str, Any]] = []
    accepted_evidence: set[str] = set()
    accepted_objects: set[str] = set()
    accepted_evidence_by_requirement: dict[str, set[str]] = {}
    for raw_seed in seeds:
        seed = _mapping(raw_seed, "product_candidate_decision_seed_invalid")
        object_id = str(seed.get("compiled_object_id") or "")
        _require(
            seed.get("candidate_not_evidence") is True
            and seed.get("candidate_text_included") is False
            and seed.get("evidence_promoted") is False
            and seed.get("numeric_authority") is False,
            "product_candidate_decision_seed_authority_invalid",
        )
        lineage = {
            str(seed.get("source_record_id") or ""),
            *(str(value) for value in seed.get("lineage_source_record_ids") or ()),
        }
        lineage.discard("")
        matches = [
            pair
            for source_id in lineage
            for pair in items_by_source.get(source_id, ())
        ]
        match_reviews = [
            (
                item,
                material,
                _product_pack_item_gate_reasons(
                    item,
                    material,
                    seed=seed,
                    request=request,
                    lane=lane,
                ),
            )
            for item, material in matches
        ]
        eligible_matches = [
            (item, material)
            for item, material, reasons in match_reviews
            if not reasons
        ]
        alignment_state = str(seed.get("material_alignment_state") or "")
        _require(
            alignment_state
            in {
                "selected_for_material_review",
                "excluded_by_material_requirement_alignment",
                "eligible_not_selected",
            },
            "product_candidate_decision_alignment_state_invalid",
        )
        selected_requirement_ids = sorted(
            str(value) for value in seed.get("selected_requirement_ids") or ()
        )
        accepted_by_requirement: dict[str, set[str]] = {}
        accepted_context_digests: set[str] = set()
        requirement_binding_modes: set[str] = set()
        for item, _ in eligible_matches:
            requirement_ids, binding_mode = _reviewed_item_requirement_binding(
                item,
                lane=lane,
                selected_requirement_ids=selected_requirement_ids,
                request_requirement_ids=request_requirement_ids,
            )
            requirement_binding_modes.add(binding_mode)
            digest = str(item.get("evidence_item_digest") or "")
            for requirement_id in requirement_ids:
                accepted_by_requirement.setdefault(requirement_id, set()).add(digest)
            if any(
                isinstance(binding, Mapping)
                and binding.get("binding_kind") == "request_context"
                and str(binding.get("slot_id") or "")
                == str(lane.get("slot_id") or "")
                and str(lane.get("facet_id") or "")
                in {str(value) for value in binding.get("facet_ids") or ()}
                for binding in item.get("slot_bindings") or ()
            ):
                accepted_context_digests.add(digest)
        accepted_digests = sorted(
            {
                digest
                for digests in accepted_by_requirement.values()
                for digest in digests
            }
        )
        adjudication = adjudications_by_object.get(object_id)
        adjudication_action = str(
            (adjudication or {}).get("action") or ""
        )
        if adjudication_action in {
            "reject_for_current_scope",
            "delegate_to_s2_numeric_authority",
        }:
            state = "rejected"
            reasons = sorted(
                {
                    *(
                        str(value)
                        for value in (adjudication or {}).get("reason_codes") or ()
                    ),
                    (
                        "candidate_delegated_to_S2_numeric_authority"
                        if adjudication_action
                        == "delegate_to_s2_numeric_authority"
                        else "candidate_rejected_by_bound_internal_adjudication"
                    ),
                }
            )
            authority = "bound_internal_engineering_candidate_adjudication"
            accepted_by_requirement = {}
            accepted_digests = []
        elif adjudication_action == "accept_for_requirements":
            _require(
                bool(accepted_by_requirement),
                "accepted_candidate_receipt_without_requirement_bound_evidence",
            )
            state = "accepted"
            reasons = [
                "existing_reviewed_evidence_reuse",
                "exact_object_case_slot_facet_period_relationship_gate_passed",
                "reviewed_evidence_resolved_to_material_requirement",
                "accepted_by_bound_internal_adjudication",
            ]
            authority = "bound_internal_engineering_evidence_adjudication"
            accepted_evidence.update(accepted_digests)
            accepted_objects.add(object_id)
            for requirement_id, digests in accepted_by_requirement.items():
                accepted_evidence_by_requirement.setdefault(
                    requirement_id, set()
                ).update(digests)
        elif adjudication_action == "accept_for_request_context":
            _require(
                bool(accepted_context_digests),
                "accepted_context_receipt_without_request_context_evidence",
            )
            state = "accepted"
            accepted_digests = sorted(accepted_context_digests)
            reasons = [
                "existing_reviewed_request_context_reuse",
                "exact_object_case_slot_facet_period_relationship_gate_passed",
                "request_context_does_not_satisfy_material_requirement",
                "accepted_by_bound_internal_adjudication",
            ]
            authority = "bound_internal_engineering_request_context_adjudication"
            accepted_evidence.update(accepted_digests)
            accepted_objects.add(object_id)
        elif accepted_by_requirement:
            state = "accepted"
            reasons = [
                "existing_reviewed_evidence_reuse",
                "exact_object_case_slot_facet_period_relationship_gate_passed",
                "reviewed_evidence_resolved_to_material_requirement",
            ]
            if alignment_state != "selected_for_material_review":
                reasons.append(
                    "explicit_reviewed_evidence_rebound_within_current_request"
                )
            if set(selected_requirement_ids) - set(accepted_by_requirement):
                reasons.append(
                    "one_or_more_selected_requirements_not_bound_to_this_evidence"
                )
            authority = (
                "current_reviewed_pack_exact_object_reuse"
                if set(accepted_by_requirement) <= set(selected_requirement_ids)
                else "current_reviewed_pack_explicit_request_requirement_rebinding"
            )
            accepted_evidence.update(accepted_digests)
            accepted_objects.add(object_id)
            for requirement_id, digests in accepted_by_requirement.items():
                accepted_evidence_by_requirement.setdefault(
                    requirement_id, set()
                ).update(digests)
        elif eligible_matches:
            state = "needs_human_review"
            if alignment_state == "selected_for_material_review":
                reasons = [
                    "reviewed_evidence_requirement_binding_missing_or_ambiguous",
                    "query_or_material_binding_requires_adjudication",
                ]
                authority = "reviewed_evidence_not_proposition_bound"
            else:
                reasons = [
                    "reviewed_evidence_recalled_outside_current_material_review",
                    "query_or_material_binding_requires_adjudication",
                ]
                authority = "reviewed_evidence_not_currently_requirement_bound"
        elif alignment_state == "selected_for_material_review":
            state = "needs_human_review"
            reasons = sorted(
                {
                    reason
                    for _, _, gate_reasons in match_reviews
                    for reason in gate_reasons
                }
            ) or ["new_candidate_requires_evidence_gate"]
            authority = "candidate_only_no_product_evidence_authority"
        elif alignment_state == "excluded_by_material_requirement_alignment":
            state = "rejected"
            reasons = ["candidate_outside_current_material_requirement_alignment"]
            authority = "deterministic_material_alignment_rejection"
        else:
            state = "unjudged"
            reasons = ["candidate_inside_bounded_union_not_selected_for_review"]
            authority = "bounded_union_unjudged"

        rank_trace = _mapping(
            seed.get("rank_trace"), "product_candidate_decision_rank_trace_missing"
        )
        body = {
            "candidate_ref": "CANDOBJ::"
            + canonical_digest(
                {
                    "request_id": request.get("request_id"),
                    "compiled_object_id": object_id,
                }
            )[:24].upper(),
            "compiled_object_id": object_id,
            "source_record_id": seed.get("source_record_id"),
            "lineage_source_record_ids": sorted(lineage),
            "subject_ticker": request.get("subject_ticker"),
            "evidence_owner_ticker": seed.get("ticker"),
            "source_type": seed.get("source_type"),
            "publication_date": seed.get("publication_date"),
            "period_end": seed.get("period_end"),
            "object_kind": seed.get("object_kind"),
            "rank_trace": deepcopy(dict(rank_trace)),
            "route_membership": list(seed.get("route_membership") or ()),
            "material_alignment_state": alignment_state,
            "material_reserved_for_requirement": seed.get(
                "material_reserved_for_requirement"
            )
            is True,
            "selected_requirement_ids": selected_requirement_ids,
            "advisory_evidence_role": deepcopy(seed.get("evidence_role")),
            "decision_state": state,
            "reason_codes": reasons,
            "decision_authority": authority,
            "accepted_evidence_item_digests": accepted_digests,
            "accepted_evidence_by_requirement": {
                requirement_id: sorted(digests)
                for requirement_id, digests in sorted(
                    accepted_by_requirement.items()
                )
            },
            "requirement_binding_modes": sorted(requirement_binding_modes),
            "candidate_adjudication_receipt_digest": (
                (adjudication or {}).get("decision_receipt_digest")
            ),
            "candidate_text_promoted": False,
            "new_evidence_created": False,
            "numeric_authority": False,
            "runtime_evidence_promotion": False,
        }
        decisions.append({**body, "decision_digest": canonical_digest(body)})

    counts = Counter(row["decision_state"] for row in decisions)
    ledger_body = {
        "schema_version": PRODUCT_DECISION_LEDGER_SCHEMA_VERSION,
        "status": "product_candidate_decisions_materialized_no_new_promotion",
        "recorded_at": recorded_at,
        "case_key": case_key,
        "research_as_of": request.get("research_as_of"),
        "request_id": request.get("request_id"),
        "request_digest": request_result.get("request_digest"),
        "slot_id": lane.get("slot_id"),
        "facet_id": lane.get("facet_id"),
        "candidate_count": len(decisions),
        "decision_counts": {
            state: counts.get(state, 0) for state in PRODUCT_DECISION_STATES
        },
        "accepted_compiled_object_ids": sorted(accepted_objects),
        "accepted_evidence_item_digests": sorted(accepted_evidence),
        "accepted_evidence_by_requirement": {
            requirement_id: sorted(digests)
            for requirement_id, digests in sorted(
                accepted_evidence_by_requirement.items()
            )
        },
        "decisions": decisions,
        "source_result_digest": hybrid.get("result_digest"),
        "pack_payload_digest": evidence_pack.get("pack_payload_digest"),
        "authority": {
            "every_bounded_union_candidate_decided_exactly_once": True,
            "rank_never_grants_evidence_authority": True,
            "reviewed_source_alone_cannot_authorize_child_object": True,
            "ambiguous_multi_requirement_evidence_reuse": False,
            "accepted_evidence_resolved_per_requirement": True,
            "existing_reviewed_evidence_reuse_only": True,
            "candidate_text_promoted": False,
            "new_evidence_created": False,
            "numeric_authority": False,
            "runtime_evidence_promotion": False,
        },
    }
    return {
        **ledger_body,
        "candidate_decision_ledger_digest": canonical_digest(ledger_body),
    }


def _request_lane(request_result: Mapping[str, Any]) -> Mapping[str, Any]:
    lanes = list(request_result.get("lanes") or ())
    _require(len(lanes) == 1, "product_readiness_lane_count_invalid")
    return _mapping(
        _mapping(lanes[0], "product_readiness_lane_projection_invalid").get("lane"),
        "product_readiness_lane_missing",
    )


def _accepted_digests_for_requirement(
    decision: Mapping[str, Any], requirement_id: str
) -> tuple[str, ...]:
    """Read v1.1 proposition binding with a narrow legacy compatibility path."""

    binding = decision.get("accepted_evidence_by_requirement")
    if isinstance(binding, Mapping):
        return tuple(
            sorted(str(value) for value in binding.get(requirement_id) or ())
        )
    selected = tuple(
        str(value) for value in decision.get("selected_requirement_ids") or ()
    )
    if selected == (requirement_id,):
        return tuple(
            sorted(
                str(value)
                for value in decision.get("accepted_evidence_item_digests") or ()
            )
        )
    return ()


def _decision_mentions_requirement(
    decision: Mapping[str, Any], requirement_id: str
) -> bool:
    binding = decision.get("accepted_evidence_by_requirement")
    return requirement_id in set(
        str(value) for value in decision.get("selected_requirement_ids") or ()
    ) or (isinstance(binding, Mapping) and requirement_id in binding)


def _numeric_state(request_result: Mapping[str, Any]) -> dict[str, Any]:
    rows = [
        _mapping(row, "product_readiness_typed_fact_result_invalid")
        for row in request_result.get("typed_fact_results") or ()
    ]
    states = Counter(str(row.get("status") or "") for row in rows)
    allowed = {"resolved", "typed_gap", "typed_conflict"}
    _require(set(states).issubset(allowed), "product_readiness_typed_fact_state_invalid")
    fact_ids: list[str] = []
    metrics: list[dict[str, Any]] = []
    for row in rows:
        facts = [
            _mapping(value, "product_readiness_numeric_fact_invalid")
            for value in row.get("facts") or ()
        ]
        status = str(row.get("status") or "")
        if status == "resolved":
            _require(
                facts
                and all(value.get("numeric_fact_authority") is True for value in facts),
                "product_readiness_resolved_numeric_authority_missing",
            )
        fact_ids.extend(
            str(value.get("numeric_fact_id") or "") for value in facts
        )
        metrics.append(
            {
                "fact_request_id": row.get("fact_request_id"),
                "metric_id": row.get("metric_id"),
                "state": status,
                "numeric_fact_ids": sorted(
                    str(value.get("numeric_fact_id") or "") for value in facts
                ),
                "numeric_authority": status == "resolved",
            }
        )
    if states["typed_conflict"]:
        overall = "typed_conflict"
    elif states["typed_gap"] and states["resolved"]:
        overall = "partial_with_typed_gaps"
    elif states["typed_gap"]:
        overall = "typed_gap"
    elif states["resolved"]:
        overall = "resolved"
    else:
        overall = "not_requested"
    return {
        "state": overall,
        "request_count": len(rows),
        "resolved_count": states["resolved"],
        "typed_gap_count": states["typed_gap"],
        "typed_conflict_count": states["typed_conflict"],
        "numeric_fact_ids": sorted(value for value in fact_ids if value),
        "metrics": metrics,
        "authority_remains_independent_from_narrative_evidence": True,
    }


def _route_state(request_result: Mapping[str, Any]) -> dict[str, Any]:
    truth = _mapping(
        request_result.get("route_execution_truth"),
        "product_readiness_route_truth_missing",
    )
    routes = [
        _mapping(route, "product_readiness_route_row_invalid")
        for request in truth.get("narrative_route_requests") or ()
        for route in _mapping(
            request, "product_readiness_route_request_invalid"
        ).get("routes")
        or ()
    ]
    states = Counter(str(route.get("execution_state") or "") for route in routes)
    executed = [
        str(route.get("declared_route") or "")
        for route in routes
        if str(route.get("execution_state") or "") == "executed"
    ]
    unexecuted = [
        str(route.get("declared_route") or "")
        for route in routes
        if str(route.get("execution_state") or "") != "executed"
    ]
    required_routes = [
        route
        for route in routes
        if (
            route.get("required_for_current_runtime") is True
            or (
                "required_for_current_runtime" not in route
                and str(route.get("capability_state") or "") != "not_configured"
            )
        )
    ]
    required_unexecuted = [
        str(route.get("declared_route") or "")
        for route in required_routes
        if str(route.get("execution_state") or "") != "executed"
    ]
    source_truth = request_result.get("source_route_execution_truth")
    source_summary: Mapping[str, Any] = {}
    source_truth_bound = False
    if isinstance(source_truth, Mapping):
        _require(
            source_truth.get("schema_version")
            == "fin_ia_s1_source_route_execution_truth_v1_0"
            and str(source_truth.get("request_id") or "")
            == str(request_result.get("request", {}).get("request_id") or ""),
            "product_readiness_source_route_truth_invalid",
        )
        source_summary = _mapping(
            source_truth.get("summary"),
            "product_readiness_source_route_summary_invalid",
        )
        source_truth_bound = True
    return {
        "declared_route_count": len(routes),
        "execution_state_counts": dict(sorted(states.items())),
        "executed_routes": sorted(set(executed)),
        "unexecuted_or_unavailable_routes": sorted(set(unexecuted)),
        "all_declared_routes_executed": bool(routes) and not unexecuted,
        "required_candidate_routes": sorted(
            {
                str(route.get("declared_route") or "")
                for route in required_routes
            }
        ),
        "required_candidate_routes_all_executed": bool(required_routes)
        and not required_unexecuted,
        "required_candidate_routes_unexecuted": sorted(set(required_unexecuted)),
        "source_route_execution_truth_bound": source_truth_bound,
        "source_supplement_route_required": bool(
            source_truth.get("supplement_route_required")
            if isinstance(source_truth, Mapping)
            else False
        ),
        "source_route_execution_state_counts": dict(
            source_summary.get("route_execution_state_counts") or {}
        ),
        "official_or_external_supplement_route_exhausted": bool(
            source_summary.get("official_or_external_supplement_route_exhausted")
        ),
        "source_non_disclosure_adjudicated": bool(
            source_truth_bound
            and source_truth.get("requirements")
            and all(
                row.get("source_non_disclosure_adjudicated") is True
                for row in source_truth.get("requirements") or ()
            )
        ),
    }


def _gap_receipt(
    *,
    request_result: Mapping[str, Any],
    ledger: Mapping[str, Any],
    requirement: Mapping[str, Any],
    requirement_receipt: Mapping[str, Any],
    requirement_state: str,
    recorded_at: str,
) -> dict[str, Any]:
    provenance = _mapping(
        request_result.get("candidate_ceiling_provenance"),
        "product_readiness_candidate_provenance_missing",
    )
    source_state = _mapping(
        provenance.get("source_object_index_state"),
        "product_readiness_source_object_index_state_missing",
    )
    ceiling = _mapping(
        provenance.get("hybrid_candidate_ceiling"),
        "product_readiness_candidate_ceiling_missing",
    )
    route = _route_state(request_result)
    requirement_id = str(requirement.get("requirement_id") or "")
    decisions = [
        row
        for row in ledger.get("decisions") or ()
        if _decision_mentions_requirement(row, requirement_id)
    ]
    decision_counts = Counter(
        str(row.get("decision_state") or "") for row in decisions
    )
    if requirement_state == "candidate_audit_only_explicit_scope_pending":
        earliest = "S3_research_scope"
        next_action = "bind_a_valid_explicit_material_scope_then_replay_same_S1_runtime"
    elif requirement_state == "blocked_by_candidate_coverage":
        earliest = "S1_query_candidate_coverage_or_evidence_role_binding"
        next_action = "inspect_query_role_and_bounded_union_before_any_external_gap_claim"
    elif requirement_state == "blocked_by_evidence_admission":
        earliest = "S1_evidence_admission"
        next_action = "review_selected_candidates_or_correct_pack_slot_facet_object_binding"
    else:
        earliest = "S1_pack_readiness"
        next_action = "resolve_current_requirement_state"
    blockers = []
    if not source_state.get("all_source_records_lineage_bound"):
        blockers.append("local_source_object_lineage_not_complete")
    if not route["required_candidate_routes_all_executed"]:
        blockers.append("one_or_more_required_candidate_routes_not_executed")
    if ceiling.get("union_ceiling_reached") is True:
        blockers.append("bounded_candidate_union_ceiling_reached")
    if requirement_receipt.get("complete") is not True:
        blockers.append("material_requirement_incomplete_in_bounded_union")
    if decision_counts["unjudged"] or decision_counts["needs_human_review"]:
        blockers.append("candidate_decisions_not_terminally_adjudicated")
    if requirement_state == "blocked_by_candidate_coverage":
        if not route["source_route_execution_truth_bound"]:
            blockers.append("source_route_execution_truth_missing")
        if not route["official_or_external_supplement_route_exhausted"]:
            blockers.append("official_or_external_supplement_route_not_exhausted")
        if not route["source_non_disclosure_adjudicated"]:
            blockers.append("source_non_disclosure_not_adjudicated")
    body = {
        "schema_version": GAP_ELIGIBILITY_RECEIPT_SCHEMA_VERSION,
        "recorded_at": recorded_at,
        "case_key": ledger.get("case_key"),
        "request_id": ledger.get("request_id"),
        "slot_id": ledger.get("slot_id"),
        "facet_id": requirement.get("facet_id"),
        "requirement_id": requirement_id,
        "requirement_role": requirement.get("role"),
        "readiness_state": requirement_state,
        "candidate_set_complete_in_bounded_union": requirement_receipt.get(
            "complete"
        )
        is True,
        "selected_candidate_count": len(
            requirement_receipt.get("selected_candidate_ids") or ()
        ),
        "candidate_decision_counts": {
            key: decision_counts.get(key, 0)
            for key in (
                "accepted",
                "rejected",
                "unjudged",
                "needs_human_review",
            )
        },
        "checks": {
            "all_source_records_lineage_bound": source_state.get(
                "all_source_records_lineage_bound"
            )
            is True,
            "compiled_object_count": int(
                source_state.get("compiled_object_count") or 0
            ),
            "candidate_runtime_executed": ceiling.get("execution_state")
            == "executed",
            "declared_routes_all_executed": route["all_declared_routes_executed"],
            "required_candidate_routes_all_executed": route[
                "required_candidate_routes_all_executed"
            ],
            "source_route_execution_truth_bound": route[
                "source_route_execution_truth_bound"
            ],
            "official_or_external_supplement_route_exhausted": route[
                "official_or_external_supplement_route_exhausted"
            ],
            "source_non_disclosure_adjudicated": route[
                "source_non_disclosure_adjudicated"
            ],
            "candidate_union_ceiling_reached": ceiling.get(
                "union_ceiling_reached"
            )
            is True,
        },
        "blockers": sorted(set(blockers)),
        "earliest_responsible_layer": earliest,
        "next_legal_action": next_action,
        "eligible_as_true_public_information_gap": False,
        "public_information_gap_authority": False,
    }
    return {**body, "receipt_digest": canonical_digest(body)}


def _declared_pack_gap_receipts(
    *,
    evidence_pack: Mapping[str, Any],
    request_rows: Sequence[Mapping[str, Any]],
    recorded_at: str,
) -> list[dict[str, Any]]:
    slots_with_requests = {
        str(row.get("slot_id") or "") for row in request_rows
    }
    receipts = []
    for raw in evidence_pack.get("residual_gaps") or ():
        gap = _mapping(raw, "product_readiness_declared_pack_gap_invalid")
        slot_id = str(gap.get("slot_id") or "")
        body = {
            "schema_version": GAP_ELIGIBILITY_RECEIPT_SCHEMA_VERSION,
            "recorded_at": recorded_at,
            "case_key": evidence_pack.get("case_key"),
            "gap_id": gap.get("gap_id"),
            "gap_code": gap.get("gap_code"),
            "slot_id": slot_id,
            "business_reason_zh": gap.get("business_reason_zh"),
            "attempted_lane_ids": list(gap.get("attempted_lane_ids") or ()),
            "matching_current_request_exists": slot_id in slots_with_requests,
            "earliest_responsible_layer": (
                "S1_gap_route_adjudication"
                if slot_id in slots_with_requests
                else "S1_or_S3_request_planning"
            ),
            "blockers": [
                "current_product_route_exhaustion_not_bound_to_declared_pack_gap",
                "official_or_external_supplement_route_not_exhausted",
                "source_non_disclosure_not_adjudicated",
            ],
            "eligible_as_true_public_information_gap": False,
            "public_information_gap_authority": False,
        }
        receipts.append({**body, "receipt_digest": canonical_digest(body)})
    return receipts


def compile_product_pack_readiness(
    *,
    product_projection: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
    candidate_decision_ledgers: Sequence[Mapping[str, Any]],
    recorded_at: str,
) -> dict[str, Any]:
    """Combine S1 candidate/Evidence decisions with independent S2 authority."""

    case_key = str(product_projection.get("case_key") or "").upper()
    _require(
        case_key and str(evidence_pack.get("case_key") or "").upper() == case_key,
        "product_readiness_pack_case_mismatch",
    )
    request_results = [
        _mapping(row, "product_readiness_request_result_invalid")
        for row in product_projection.get("request_results") or ()
    ]
    ledger_by_request = {
        str(row.get("request_id") or ""): row
        for row in candidate_decision_ledgers
    }
    _require(
        len(request_results) == len(ledger_by_request),
        "product_readiness_ledger_cardinality_mismatch",
    )
    request_rows: list[dict[str, Any]] = []
    gap_receipts: list[dict[str, Any]] = []
    all_accepted_evidence: set[str] = set()
    total_candidates = 0
    for request_result in request_results:
        request = _mapping(
            request_result.get("request"), "product_readiness_request_missing"
        )
        request_id = str(request.get("request_id") or "")
        ledger = _mapping(
            ledger_by_request.get(request_id),
            f"product_readiness_ledger_missing:{request_id}",
        )
        _require(
            ledger.get("schema_version") == PRODUCT_DECISION_LEDGER_SCHEMA_VERSION,
            "product_readiness_ledger_schema_invalid",
        )
        hybrid = _mapping(
            request_result.get("hybrid_object_retrieval"),
            "product_readiness_hybrid_result_missing",
        )
        material = _mapping(
            hybrid.get("material_evidence"),
            "product_readiness_material_evidence_missing",
        )
        plan = _mapping(
            material.get("requirement_plan"),
            "product_readiness_requirement_plan_missing",
        )
        selection = _mapping(
            material.get("selection"),
            "product_readiness_material_selection_missing",
        )
        requirements = {
            str(row.get("requirement_id") or ""): _mapping(
                row, "product_readiness_requirement_invalid"
            )
            for row in plan.get("requirement_groups") or ()
        }
        receipts = {
            str(row.get("requirement_id") or ""): _mapping(
                row, "product_readiness_requirement_receipt_invalid"
            )
            for row in selection.get("requirement_receipts") or ()
        }
        _require(
            requirements and set(requirements) == set(receipts),
            "product_readiness_requirement_receipt_set_invalid",
        )
        decisions = list(ledger.get("decisions") or ())
        requirement_rows = []
        requirement_states = []
        scope_ready = material.get("runtime_scope_ready") is True
        for requirement_id, requirement in requirements.items():
            receipt = receipts[requirement_id]
            bound_decisions = [
                row
                for row in decisions
                if _decision_mentions_requirement(row, requirement_id)
            ]
            accepted_digests = sorted(
                {
                    str(digest)
                    for row in bound_decisions
                    if row.get("decision_state") == "accepted"
                    for digest in _accepted_digests_for_requirement(
                        row, requirement_id
                    )
                }
            )
            if not scope_ready:
                state = "candidate_audit_only_explicit_scope_pending"
            elif receipt.get("complete") is not True:
                state = "blocked_by_candidate_coverage"
            elif not accepted_digests:
                state = "blocked_by_evidence_admission"
            else:
                state = "ready_for_current_scope"
            requirement_states.append(state)
            requirement_rows.append(
                {
                    "requirement_id": requirement_id,
                    "facet_id": requirement.get("facet_id"),
                    "role": requirement.get("role"),
                    "candidate_set_complete_in_bounded_union": receipt.get(
                        "complete"
                    )
                    is True,
                    "selected_candidate_ids": list(
                        receipt.get("selected_candidate_ids") or ()
                    ),
                    "accepted_reviewed_evidence_digests": accepted_digests,
                    "readiness_state": state,
                    "candidate_text_promoted": False,
                    "numeric_authority": False,
                }
            )
            if state != "ready_for_current_scope":
                gap_receipts.append(
                    _gap_receipt(
                        request_result=request_result,
                        ledger=ledger,
                        requirement=requirement,
                        requirement_receipt=receipt,
                        requirement_state=state,
                        recorded_at=recorded_at,
                    )
                )
        numeric = _numeric_state(request_result)
        if "candidate_audit_only_explicit_scope_pending" in requirement_states:
            request_state = "candidate_audit_only_explicit_scope_pending"
        elif "blocked_by_candidate_coverage" in requirement_states:
            request_state = "blocked_by_candidate_coverage"
        elif "blocked_by_evidence_admission" in requirement_states:
            request_state = "blocked_by_evidence_admission"
        elif numeric["state"] == "typed_conflict":
            request_state = "blocked_by_numeric_or_bridge_authority"
        elif numeric["state"] in {"typed_gap", "partial_with_typed_gaps"}:
            request_state = "partial_with_material_gaps"
        else:
            request_state = "ready_for_current_scope"
        _require(request_state in READINESS_STATES, "product_readiness_state_invalid")
        all_accepted_evidence.update(
            str(value) for value in ledger.get("accepted_evidence_item_digests") or ()
        )
        total_candidates += int(ledger.get("candidate_count") or 0)
        lane = _request_lane(request_result)
        request_rows.append(
            {
                "request_id": request_id,
                "slot_id": lane.get("slot_id"),
                "facet_id": lane.get("facet_id"),
                "business_question_zh": lane.get("business_question_zh"),
                "material_scope_ready": scope_ready,
                "readiness_state": request_state,
                "requirements": requirement_rows,
                "candidate_decision_counts": deepcopy(
                    ledger.get("decision_counts") or {}
                ),
                "numeric_authority_state": numeric,
                "route_execution_state": _route_state(request_result),
                "candidate_decision_ledger_digest": ledger.get(
                    "candidate_decision_ledger_digest"
                ),
            }
        )

    request_state_counts = Counter(row["readiness_state"] for row in request_rows)
    if request_state_counts["candidate_audit_only_explicit_scope_pending"]:
        aggregate_state = "candidate_audit_only_explicit_scope_pending"
    elif request_state_counts["blocked_by_local_data_materialization"]:
        aggregate_state = "blocked_by_local_data_materialization"
    elif request_state_counts["blocked_by_candidate_coverage"]:
        aggregate_state = "blocked_by_candidate_coverage"
    elif request_state_counts["blocked_by_retrieval_quality"]:
        aggregate_state = "blocked_by_retrieval_quality"
    elif request_state_counts["blocked_by_evidence_admission"]:
        aggregate_state = "blocked_by_evidence_admission"
    elif request_state_counts["blocked_by_numeric_or_bridge_authority"]:
        aggregate_state = "blocked_by_numeric_or_bridge_authority"
    elif request_state_counts["partial_with_material_gaps"]:
        aggregate_state = "partial_with_material_gaps"
    else:
        aggregate_state = "ready_for_current_scope"
    declared_gap_receipts = _declared_pack_gap_receipts(
        evidence_pack=evidence_pack,
        request_rows=request_rows,
        recorded_at=recorded_at,
    )
    body = {
        "schema_version": PRODUCT_PACK_READINESS_SCHEMA_VERSION,
        "status": "current_product_pack_readiness_materialized",
        "recorded_at": recorded_at,
        "case_key": case_key,
        "research_as_of": product_projection.get("objective", {}).get(
            "research_as_of"
        ),
        "readiness_state": aggregate_state,
        "request_count": len(request_rows),
        "request_state_counts": {
            state: request_state_counts.get(state, 0) for state in READINESS_STATES
        },
        "candidate_count": total_candidates,
        "accepted_reviewed_evidence_digests": sorted(all_accepted_evidence),
        "requests": request_rows,
        "gap_eligibility_receipts": gap_receipts,
        "declared_pack_gap_receipts": declared_gap_receipts,
        "pack_binding": {
            "pack_payload_digest": evidence_pack.get("pack_payload_digest"),
            "retrieval_result_digest": evidence_pack.get("retrieval_result_digest"),
        },
        "checks": {
            "all_candidates_have_exactly_one_persistent_decision": True,
            "accepted_evidence_resolved_per_requirement": True,
            "ambiguous_multi_requirement_evidence_reuse": False,
            "candidate_text_promoted": False,
            "new_evidence_created": False,
            "narrative_evidence_and_numeric_authority_separated": True,
            "unexecuted_route_treated_as_public_information_gap": False,
            "S1_qualified_stable": False,
            "complete_product_conclusion_ready": False,
        },
        "authority": {
            "candidate_is_not_evidence": True,
            "numeric_fact_authority_remains_with_S2": True,
            "public_information_gap_authority": False,
            "S1_qualification_claimed": False,
            "product_publication": False,
        },
    }
    return {**body, "readiness_digest": canonical_digest(body)}


__all__ = [
    "GAP_ELIGIBILITY_RECEIPT_SCHEMA_VERSION",
    "PRODUCT_DECISION_LEDGER_SCHEMA_VERSION",
    "PRODUCT_DECISION_STATES",
    "PRODUCT_PACK_READINESS_SCHEMA_VERSION",
    "ProductPackReadinessError",
    "READINESS_STATES",
    "compile_product_candidate_decision_ledger",
    "compile_product_pack_readiness",
]
