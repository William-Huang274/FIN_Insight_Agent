from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from .query_plan import canonical_digest


SCHEMA_VERSION = "fin_ia_s1_candidate_ceiling_provenance_v1_0"


class CandidateCeilingProvenanceError(ValueError):
    """Fail-closed error for request-bound candidate loss provenance."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CandidateCeilingProvenanceError(code)


def _positive_int(value: Any, code: str) -> int:
    _require(type(value) is int and value > 0, code)
    return int(value)


def _nonnegative_int(value: Any, code: str) -> int:
    _require(type(value) is int and value >= 0, code)
    return int(value)


def candidate_provenance_scope_mode_valid(
    material_scope: Mapping[str, Any],
) -> bool:
    """Accept auditable candidate runs without granting material readiness."""

    mode = material_scope.get("mode")
    required = material_scope.get("required_request_ids")
    if not isinstance(required, list):
        return False
    if mode == "deterministic_scope_ready":
        return not required
    if mode == "explicit_scope_required":
        return bool(required)
    return False


def _candidate_contract(value: Mapping[str, Any]) -> dict[str, int]:
    required = (
        "first_stage_limit",
        "candidate_union_limit",
        "output_limit",
        "max_candidates_per_source_record",
    )
    _require(
        set(value) == set(required),
        "candidate_ceiling_contract_fields_invalid",
    )
    contract = {
        key: _positive_int(
            value.get(key),
            f"candidate_ceiling_contract_{key}_invalid",
        )
        for key in required
    }
    _require(
        contract["candidate_union_limit"] >= contract["first_stage_limit"]
        >= contract["output_limit"],
        "candidate_ceiling_contract_order_invalid",
    )
    return contract


def _route_summary(route_execution_truth: Mapping[str, Any]) -> dict[str, Any]:
    _require(
        route_execution_truth.get("schema_version")
        == "fin_ia_s1_request_route_execution_truth_v1_0",
        "candidate_ceiling_route_truth_schema_invalid",
    )
    rows = [
        route
        for request in route_execution_truth.get("narrative_route_requests") or ()
        for route in request.get("routes") or ()
    ]
    _require(
        all(isinstance(row, Mapping) for row in rows),
        "candidate_ceiling_route_rows_invalid",
    )
    state_counts = Counter(str(row.get("execution_state") or "") for row in rows)
    return {
        "narrative_route_request_count": len(
            route_execution_truth.get("narrative_route_requests") or ()
        ),
        "typed_fact_sibling_request_count": len(
            route_execution_truth.get("typed_fact_sibling_requests") or ()
        ),
        "route_execution_state_counts": dict(sorted(state_counts.items())),
        "hybrid_candidate_runtime_executed": bool(
            route_execution_truth.get("hybrid_candidate_runtime_executed")
        ),
        "unavailable_or_unexecuted_route_is_not_a_public_information_gap": bool(
            route_execution_truth.get(
                "unavailable_or_unexecuted_route_is_not_a_public_information_gap"
            )
        ),
    }


def _requirement_provenance(
    *,
    material: Mapping[str, Any],
    final_candidate_ids: set[str],
    union_ceiling_reached: bool,
) -> list[dict[str, Any]]:
    plan = material.get("requirement_plan") or {}
    selection = material.get("selection") or {}
    groups = plan.get("requirement_groups") or ()
    receipts = selection.get("requirement_receipts") or ()
    _require(
        isinstance(groups, list)
        and isinstance(receipts, list)
        and len(groups) == len(receipts),
        "candidate_ceiling_requirement_rows_invalid",
    )
    receipts_by_id = {
        str(row.get("requirement_id") or ""): row for row in receipts
    }
    _require(
        len(receipts_by_id) == len(receipts),
        "candidate_ceiling_requirement_receipt_identity_invalid",
    )
    output: list[dict[str, Any]] = []
    for group in groups:
        requirement_id = str(group.get("requirement_id") or "")
        receipt = receipts_by_id.get(requirement_id)
        _require(
            requirement_id and isinstance(receipt, Mapping),
            "candidate_ceiling_requirement_receipt_missing",
        )
        selected_ids = {
            str(value)
            for value in receipt.get("selected_candidate_ids") or ()
            if str(value)
        }
        complete = receipt.get("complete") is True
        preserved = len(selected_ids.intersection(final_candidate_ids))
        if complete and preserved == len(selected_ids):
            observed_loss_stage = "none_observed_through_candidate_review"
        elif complete:
            observed_loss_stage = "post_union_source_quota_or_review_cut"
        elif union_ceiling_reached:
            observed_loss_stage = "at_or_before_bounded_candidate_union_ceiling"
        else:
            observed_loss_stage = "no_complete_set_in_executed_candidate_union"
        output.append(
            {
                "requirement_id": requirement_id,
                "facet_id": str(group.get("facet_id") or ""),
                "role": str(group.get("role") or ""),
                "coverage_mode": str(group.get("coverage_mode") or ""),
                "candidate_set_complete_in_bounded_union": complete,
                "supporting_candidate_count_in_union_bundle": len(selected_ids),
                "supporting_candidate_count_in_final_review": preserved,
                "candidate_set_preserved_to_final_review": bool(
                    complete and preserved == len(selected_ids)
                ),
                "observed_loss_stage": observed_loss_stage,
                "source_disclosure_adjudicated": False,
                "candidate_is_not_evidence": True,
                "public_information_gap_eligible": False,
            }
        )
    return output


def build_candidate_ceiling_provenance(
    *,
    request: Mapping[str, Any],
    request_digest: str,
    static_summary: Mapping[str, Any],
    static_lanes: Sequence[Mapping[str, Any]],
    route_execution_truth: Mapping[str, Any],
    runtime_binding_receipt: Mapping[str, Any],
    candidate_contract: Mapping[str, Any],
    hybrid_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Explain the earliest observed candidate loss without declaring a source gap."""

    request_id = str(request.get("request_id") or "")
    _require(request_id, "candidate_ceiling_request_id_missing")
    _require(
        request_digest == canonical_digest(dict(request)),
        "candidate_ceiling_request_digest_invalid",
    )
    acceptance = runtime_binding_receipt.get("acceptance") or {}
    lineage = runtime_binding_receipt.get("source_object_index_lineage") or {}
    _require(
        runtime_binding_receipt.get("status")
        == "current_product_lineage_bound_with_explicit_open_gates"
        and acceptance.get("source_to_compiled_lineage_complete") is True
        and acceptance.get("s1_qualified_stable") is False,
        "candidate_ceiling_runtime_binding_invalid",
    )
    contract = _candidate_contract(candidate_contract)
    route_summary = _route_summary(route_execution_truth)
    static_candidate_count = _nonnegative_int(
        static_summary.get("unique_candidates"),
        "candidate_ceiling_static_candidate_count_invalid",
    )
    missing_source_roles = sorted(
        {
            str(role)
            for lane in static_lanes
            for role in lane.get("missing_required_source_roles") or ()
            if str(role)
        }
    )

    hybrid_projection: dict[str, Any]
    requirements: list[dict[str, Any]] = []
    if hybrid_result is None:
        hybrid_projection = {
            "execution_state": "not_executed_by_direct_snapshot_endpoint",
            "first_stage_limit": contract["first_stage_limit"],
            "candidate_union_limit": contract["candidate_union_limit"],
            "output_limit": contract["output_limit"],
            "candidate_union_count": None,
            "final_review_count": None,
            "union_ceiling_reached": None,
            "final_review_ceiling_reached": None,
            "material_requirement_evaluation_state": "not_executed",
        }
        earliest = "hybrid_candidate_runtime_not_executed"
    else:
        _require(
            hybrid_result.get("request_id") == request_id
            and hybrid_result.get("candidate_state") == "candidate_not_evidence",
            "candidate_ceiling_hybrid_identity_invalid",
        )
        summary = hybrid_result.get("summary") or {}
        eligible_count = _nonnegative_int(
            summary.get("eligible_object_count"),
            "candidate_ceiling_eligible_count_invalid",
        )
        bm25_count = _nonnegative_int(
            summary.get("bm25_first_stage_count"),
            "candidate_ceiling_bm25_count_invalid",
        )
        dense_count = _nonnegative_int(
            summary.get("qwen_first_stage_count"),
            "candidate_ceiling_dense_count_invalid",
        )
        union_count = _nonnegative_int(
            summary.get("union_count_before_source_quota"),
            "candidate_ceiling_union_count_invalid",
        )
        selected_count = _nonnegative_int(
            summary.get("selected_count"),
            "candidate_ceiling_selected_count_invalid",
        )
        _require(
            union_count <= contract["candidate_union_limit"]
            and selected_count <= contract["output_limit"]
            and bm25_count <= contract["first_stage_limit"]
            and dense_count <= contract["first_stage_limit"],
            "candidate_ceiling_runtime_count_exceeds_contract",
        )
        union_ceiling_reached = union_count == contract["candidate_union_limit"]
        final_ids = {
            str(row.get("compiled_object_id") or "")
            for row in hybrid_result.get("candidates") or ()
        }
        _require(
            len(final_ids) == selected_count and "" not in final_ids,
            "candidate_ceiling_final_candidate_identity_invalid",
        )
        material = hybrid_result.get("material_evidence")
        if isinstance(material, Mapping):
            requirements = _requirement_provenance(
                material=material,
                final_candidate_ids=final_ids,
                union_ceiling_reached=union_ceiling_reached,
            )
            material_state = (
                "all_requirements_complete_in_bounded_union"
                if requirements
                and all(
                    row["candidate_set_complete_in_bounded_union"]
                    for row in requirements
                )
                else "one_or_more_requirements_incomplete_in_bounded_union"
            )
        else:
            material_state = "requirement_plan_not_compiled"
        hybrid_projection = {
            "execution_state": "executed",
            "eligible_object_count": eligible_count,
            "hard_filter_exclusions": dict(
                summary.get("hard_filter_exclusions") or {}
            ),
            "first_stage_limit": contract["first_stage_limit"],
            "bm25_first_stage_count": bm25_count,
            "bm25_first_stage_ceiling_reached": (
                bm25_count == contract["first_stage_limit"]
            ),
            "qwen_first_stage_count": dense_count,
            "qwen_first_stage_ceiling_reached": (
                dense_count == contract["first_stage_limit"]
            ),
            "candidate_union_limit": contract["candidate_union_limit"],
            "candidate_union_count": union_count,
            "union_ceiling_reached": union_ceiling_reached,
            "output_limit": contract["output_limit"],
            "final_review_count": selected_count,
            "final_review_ceiling_reached": (
                selected_count == contract["output_limit"]
            ),
            "max_candidates_per_source_record": contract[
                "max_candidates_per_source_record"
            ],
            "material_reservation_active": bool(
                summary.get("material_reservation_active")
            ),
            "material_requirement_evaluation_state": material_state,
        }
        if eligible_count == 0:
            earliest = "hard_filter_or_upstream_object_eligibility"
        elif union_count == 0:
            earliest = "executed_first_stage_candidate_retrieval"
        elif any(
            row["observed_loss_stage"]
            == "post_union_source_quota_or_review_cut"
            for row in requirements
        ):
            earliest = "post_union_source_quota_or_review_cut"
        elif any(
            not row["candidate_set_complete_in_bounded_union"]
            for row in requirements
        ):
            earliest = "at_or_before_candidate_union"
        elif requirements:
            earliest = "none_observed_through_candidate_review"
        else:
            earliest = "requirement_adjudication_not_compiled"

    blockers = [
        "source_disclosure_not_adjudicated_by_candidate_retrieval",
        "reachable_external_source_route_exhaustion_not_proven",
    ]
    if not route_summary["hybrid_candidate_runtime_executed"]:
        blockers.append("hybrid_candidate_runtime_not_executed")
    if any(
        state.startswith("not_executed")
        for state in route_summary["route_execution_state_counts"]
    ):
        blockers.append("one_or_more_declared_routes_not_executed")
    if requirements and any(
        not row["candidate_set_complete_in_bounded_union"]
        for row in requirements
    ):
        blockers.append("one_or_more_material_requirements_incomplete")

    body = {
        "schema_version": SCHEMA_VERSION,
        "status": "candidate_ceiling_observed_public_gap_not_eligible",
        "request_id": request_id,
        "request_digest": request_digest,
        "runtime_binding_digest": runtime_binding_receipt.get("result_digest"),
        "source_object_index_state": {
            "source_record_count": int(lineage.get("source_record_count") or 0),
            "compiled_object_count": int(
                lineage.get("compiled_object_count") or 0
            ),
            "all_source_records_lineage_bound": bool(
                lineage.get("all_source_records_lineage_bound")
            ),
            "source_disclosure_adjudicated": False,
        },
        "static_snapshot_filter": {
            "execution_state": "executed",
            "lane_count": len(static_lanes),
            "nonempty_lane_count": sum(
                bool(lane.get("candidates")) for lane in static_lanes
            ),
            "unique_source_candidate_count": static_candidate_count,
            "missing_required_source_roles": missing_source_roles,
            "candidate_is_not_evidence": True,
        },
        "route_execution": route_summary,
        "hybrid_candidate_ceiling": hybrid_projection,
        "material_requirements": requirements,
        "earliest_observed_limitation": earliest,
        "gap_eligibility": {
            "status": "not_eligible",
            "blockers": sorted(set(blockers)),
            "public_information_gap_eligible": False,
        },
        "authority": {
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "source_gap_authority": False,
            "evidence_promotion": False,
        },
        "known_boundary": (
            "This receipt localizes the earliest observed loss inside the current "
            "bound candidate pipeline. It cannot prove that a source disclosed or "
            "did not disclose the requested fact, and it cannot turn an unavailable "
            "route, a zero candidate result, a union ceiling or a ranking cut into a "
            "public-information gap or Evidence authority."
        ),
    }
    return {**body, "provenance_digest": canonical_digest(body)}


def validate_candidate_ceiling_provenance(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    value = dict(payload)
    digest = str(value.pop("provenance_digest", ""))
    _require(
        value.get("schema_version") == SCHEMA_VERSION
        and value.get("status")
        == "candidate_ceiling_observed_public_gap_not_eligible"
        and digest == canonical_digest(value),
        "candidate_ceiling_provenance_identity_invalid",
    )
    authority = value.get("authority") or {}
    gap = value.get("gap_eligibility") or {}
    _require(
        authority.get("candidate_is_not_evidence") is True
        and authority.get("numeric_authority") is False
        and authority.get("source_gap_authority") is False
        and authority.get("evidence_promotion") is False
        and gap.get("public_information_gap_eligible") is False,
        "candidate_ceiling_provenance_authority_invalid",
    )
    return {**value, "provenance_digest": digest}


__all__ = [
    "CandidateCeilingProvenanceError",
    "SCHEMA_VERSION",
    "build_candidate_ceiling_provenance",
    "candidate_provenance_scope_mode_valid",
    "validate_candidate_ceiling_provenance",
]
