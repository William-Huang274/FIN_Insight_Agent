from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .evidence_role_v3 import evaluate_evidence_role
from .query_plan import canonical_digest
from .supplement_vertical import (
    build_capture_bound_evidence_pair,
    verify_capture_bound_object,
)
from sec_agent.research.reviewed_evidence_pack import (
    validate_reviewed_evidence_pack,
)


ADJUDICATION_PLAN_SCHEMA_VERSION = (
    "fin_ia_s1_product_evidence_adjudication_plan_v1_0"
)
POLICY_SCHEMA_VERSION = "fin_ia_s1_product_evidence_adjudication_policy_v1_1"
RESULT_SCHEMA_VERSION = "fin_ia_s1_product_evidence_successor_result_v1_2"
CURRENT_COMPOSITION_LINEAGE_SCHEMA_VERSION = (
    "fin_ia_current_pack_composition_lineage_v1_3"
)
CURRENT_PRODUCT_READINESS_SCHEMA_VERSION = (
    "fin_ia_s1_current_product_readiness_result_v1_1"
)
DECISION_ACTIONS = (
    "accept_for_requirements",
    "accept_for_request_context",
    "reject_for_current_scope",
    "delegate_to_s2_numeric_authority",
)


class ProductEvidenceSuccessorError(ValueError):
    """A controlled Candidate-to-Evidence successor violated authority."""


def project_current_product_evidence_successor_lineage(
    *,
    historical_projection: Mapping[str, Any] | None,
    current_result: Mapping[str, Any],
    product_readiness: Mapping[str, Any],
    case_key: str,
) -> dict[str, Any] | None:
    """Project a current Pack successor without rewriting its historical producer.

    VS1/VS4 records remain immutable evidence of the Packs that those verticals
    actually produced. When a later, proposition-bound Evidence successor is
    promoted into the current composition, every Workbench consumer must show
    that new Pack binding while retaining the older projection only as historical
    lineage. This function is deliberately shared by Pack and Retrieval views so
    they cannot invent competing definitions of "current".
    """

    result = deepcopy(dict(current_result))
    lineage = _mapping(
        result.get("current_composition_lineage") or {},
        "current_product_successor_lineage_invalid",
    )
    if not (
        lineage.get("schema_version")
        == CURRENT_COMPOSITION_LINEAGE_SCHEMA_VERSION
        and lineage.get("promotion_kind")
        == "three_case_proposition_bound_evidence_successor"
    ):
        return None

    normalized_case = str(case_key or "").strip().upper()
    replacements = {
        str(value or "").strip().upper()
        for value in lineage.get("replacement_case_keys") or ()
    }
    if normalized_case not in replacements:
        return None

    result_body = deepcopy(result)
    result_digest = str(result_body.pop("result_digest", ""))
    _require(
        result.get("schema_version")
        == "fin_ia_current_research_evidence_pack_result_v1_1"
        and result.get("status")
        == "terminal_succeeded_current_pack_composition_with_declared_gaps"
        and result_digest == canonical_digest(result_body),
        "current_product_successor_result_invalid",
    )
    replacement_digests = _mapping(
        lineage.get("replacement_result_digests"),
        "current_product_successor_result_binding_invalid",
    )
    successor_result_digest = str(
        replacement_digests.get(normalized_case) or ""
    )
    artifacts = _mapping(
        result.get("pack_artifacts"),
        "current_product_successor_pack_artifacts_invalid",
    )
    payload_digests = _mapping(
        result.get("pack_payload_digests"),
        "current_product_successor_pack_payload_digests_invalid",
    )
    artifact = _mapping(
        artifacts.get(normalized_case),
        "current_product_successor_pack_artifact_invalid",
    )
    artifact_digest = str(artifact.get("digest") or "")
    pack_payload_digest = str(payload_digests.get(normalized_case) or "")
    summaries = {
        str(row.get("case_key") or "").strip().upper(): row
        for row in result.get("case_summaries") or ()
        if isinstance(row, Mapping)
    }
    summary = _mapping(
        summaries.get(normalized_case),
        "current_product_successor_case_summary_invalid",
    )

    readiness = deepcopy(dict(product_readiness))
    readiness_body = deepcopy(readiness)
    readiness_digest = str(readiness_body.pop("result_digest", ""))
    requests = [
        _mapping(row, "current_product_successor_request_invalid")
        for row in readiness.get("requests") or ()
    ]
    authority = _mapping(
        readiness.get("authority"),
        "current_product_successor_authority_invalid",
    )
    _require(
        successor_result_digest
        and artifact_digest
        and pack_payload_digest
        and readiness.get("schema_version")
        == CURRENT_PRODUCT_READINESS_SCHEMA_VERSION
        and readiness.get("status")
        == "current_product_pack_readiness_materialized"
        and str(readiness.get("case_key") or "").strip().upper()
        == normalized_case
        and readiness_digest == canonical_digest(readiness_body)
        and int(readiness.get("request_count") or -1) == len(requests)
        and authority.get("candidate_is_not_evidence") is True
        and authority.get("S1_qualification_claimed") is False
        and authority.get("product_publication") is False,
        "current_product_successor_readiness_invalid",
    )

    decision_summary = {
        key: sum(
            int(
                _mapping(
                    row.get("candidate_decision_counts") or {},
                    "current_product_successor_candidate_counts_invalid",
                ).get(key)
                or 0
            )
            for row in requests
        )
        for key in ("accepted", "rejected", "unjudged")
    }
    decision_summary["needs_review"] = sum(
        int(
            _mapping(
                row.get("candidate_decision_counts") or {},
                "current_product_successor_candidate_counts_invalid",
            ).get("needs_human_review")
            or 0
        )
        for row in requests
    )
    historical = (
        deepcopy(dict(historical_projection))
        if historical_projection is not None
        else None
    )
    historical_lineage = None
    if historical is not None:
        historical_lineage = {
            "status": str(historical.get("status") or ""),
            "recorded_at": str(historical.get("recorded_at") or ""),
            "pack_binding": deepcopy(dict(historical.get("pack_binding") or {})),
            "workbench_projection_digest": str(
                historical.get("workbench_projection_digest") or ""
            ),
            "not_current_pack_producer": True,
        }

    body = {
        "schema_version": "fin_ia_s1_workbench_lineage_projection_v1_0",
        "status": "canonical_s1_lineage_with_product_evidence_successor",
        "recorded_at": str(readiness.get("recorded_at") or ""),
        "case_key": normalized_case,
        "research_as_of": (
            historical.get("research_as_of") if historical is not None else None
        ),
        "proposition_id": None,
        "proposition_ids": sorted(
            str(row.get("request_id") or "")
            for row in requests
            if str(row.get("request_id") or "")
        ),
        "readiness_state": str(readiness.get("readiness_state") or ""),
        "candidate_decision_summary": decision_summary,
        "coverage_summary": {
            "coverage_state": "current_product_readiness_with_declared_gaps",
            "accepted_evidence_count": int(
                summary.get("accepted_evidence_items") or 0
            ),
            "current_exact_reviewed_evidence_count": int(
                readiness.get("accepted_reviewed_evidence_count") or 0
            ),
            "reviewed_not_recalled_count": None,
            "unresolved_gap_count": int(summary.get("residual_gaps") or 0),
            "true_public_information_gap_count": 0,
        },
        # Prior VS1/VS4 decisions and gap receipts remain historical. They
        # cannot be surfaced as if they adjudicated the successor candidate set.
        "decision_rows": [],
        "gap_eligibility_receipts": [],
        "pack_binding": {
            "case_key": normalized_case,
            "artifact_digest": artifact_digest,
            "pack_payload_digest": pack_payload_digest,
        },
        "evidence_successor": {
            "successor_result_digest": successor_result_digest,
            "product_readiness_result_digest": readiness_digest,
            "candidate_is_not_evidence": True,
            "numeric_fact_authorized": False,
            "complete_s1_qualified": False,
            "qualified_human_review_complete": False,
        },
        "historical_vertical_lineage": historical_lineage,
        "hard_boundaries": {
            "candidate_is_not_evidence": True,
            "rank_never_grants_evidence_authority": True,
            "unexecuted_route_is_not_public_information_gap": True,
            "complete_product_conclusion_ready": False,
            "S1_qualified_stable": False,
            "historical_vs4_summary_not_relabelled_as_successor": True,
        },
    }
    return {**body, "workbench_projection_digest": canonical_digest(body)}


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ProductEvidenceSuccessorError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _review_items_by_ref(packet: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    items = [
        _mapping(item, "product_evidence_review_item_invalid")
        for request in packet.get("requests") or ()
        for item in _mapping(
            request, "product_evidence_review_request_invalid"
        ).get("review_items")
        or ()
    ]
    by_ref = {str(item.get("review_item_ref") or ""): item for item in items}
    _require(
        items
        and all(by_ref)
        and len(items) == len(by_ref)
        and len(items) == int(packet.get("review_item_count") or 0),
        "product_evidence_review_item_identity_invalid",
    )
    return by_ref


def _actionable_review_items_by_ref(
    packet: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    """Return only unresolved rows that the next successor may adjudicate.

    A review packet intentionally includes already accepted Evidence so a human can
    inspect the current answer beside new candidates.  Those informational rows are
    immutable predecessor state, not fresh adjudication work.  Requiring every
    successor to decide them again creates evidence churn and can accidentally retire
    a valid binding when a compact plan only names the new candidates.
    """

    review_by_ref = _review_items_by_ref(packet)
    actionable: dict[str, Mapping[str, Any]] = {}
    for review_ref, review in review_by_ref.items():
        human_review_required = review.get("human_review_required")
        _require(
            isinstance(human_review_required, bool),
            "product_evidence_review_actionability_invalid",
        )
        if human_review_required:
            actionable[review_ref] = review
    _require(actionable, "product_evidence_actionable_review_set_empty")
    return actionable


def _requirement_ids_by_request(
    packet: Mapping[str, Any],
) -> dict[str, frozenset[str]]:
    output: dict[str, frozenset[str]] = {}
    for raw_request in packet.get("requests") or ():
        request = _mapping(
            raw_request, "product_evidence_review_request_invalid"
        )
        request_id = str(request.get("request_id") or "")
        declared = {
            str(value.get("requirement_id") or "")
            for value in request.get("requirements") or ()
            if isinstance(value, Mapping)
        }
        if not declared:
            declared = {
                str(value.get("requirement_id") or "")
                for item in request.get("review_items") or ()
                if isinstance(item, Mapping)
                for value in item.get("requirement_contexts") or ()
                if isinstance(value, Mapping)
            }
        _require(
            bool(request_id)
            and request_id not in output
            and bool(declared)
            and all(declared),
            "product_evidence_request_requirement_identity_invalid",
        )
        output[request_id] = frozenset(declared)
    return output


def compile_product_evidence_adjudication_policy(
    *,
    candidate_review_packet: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Expand a bounded adjudication plan into one decision per review item.

    The tracked plan stays compact: only accepted items need bespoke business
    reasoning.  Every unlisted claim is explicitly rejected for the current
    scope and every metric row is delegated to S2.  The packet digest prevents
    those defaults from silently applying to a different candidate set.
    """

    normalized_plan = deepcopy(dict(plan))
    plan_digest = str(normalized_plan.pop("plan_digest", ""))
    packet_digest = str(candidate_review_packet.get("review_packet_digest") or "")
    case_key = str(plan.get("case_key") or "").upper()
    _require(
        plan.get("schema_version") == ADJUDICATION_PLAN_SCHEMA_VERSION
        and plan.get("status") == "approved_internal_engineering_plan"
        and plan_digest == canonical_digest(normalized_plan)
        and case_key
        and case_key
        == str(candidate_review_packet.get("case_key") or "").upper()
        and str(plan.get("candidate_review_packet_digest") or "")
        == packet_digest
        and str(plan.get("default_claim_action") or "")
        == "reject_for_current_scope"
        and str(plan.get("metric_row_action") or "")
        == "delegate_to_s2_numeric_authority"
        and plan.get("qualified_human_review") is False
        and plan.get("S1_qualification_authorized") is False
        and plan.get("product_publication_authorized") is False,
        "product_evidence_adjudication_plan_invalid",
    )
    all_review_by_ref = _review_items_by_ref(candidate_review_packet)
    review_by_ref = _actionable_review_items_by_ref(candidate_review_packet)
    raw_overrides = [
        _mapping(value, "product_evidence_adjudication_override_invalid")
        for value in plan.get("accepted_items") or ()
    ]
    overrides = {
        str(value.get("review_item_ref") or ""): value for value in raw_overrides
    }
    _require(
        len(raw_overrides) == len(overrides)
        and set(overrides) <= set(review_by_ref)
        and all(overrides),
        "product_evidence_adjudication_override_identity_invalid",
    )
    decisions: list[dict[str, Any]] = []
    for review_ref in sorted(review_by_ref):
        review = review_by_ref[review_ref]
        override = overrides.get(review_ref)
        if override is not None:
            decision = {
                **dict(override),
                "review_item_digest": review.get("review_item_digest"),
            }
        elif review.get("object_kind") == "metric_row":
            decision = {
                "review_item_ref": review_ref,
                "review_item_digest": review.get("review_item_digest"),
                "action": "delegate_to_s2_numeric_authority",
                "requirement_ids": [],
                "reason_codes": ["metric_authority_owned_by_S2"],
            }
        else:
            decision = {
                "review_item_ref": review_ref,
                "review_item_digest": review.get("review_item_digest"),
                "action": "reject_for_current_scope",
                "requirement_ids": [],
                "reason_codes": ["not_selected_for_current_proposition_bound_pack"],
            }
        decisions.append(decision)
    policy_body = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "status": "approved_internal_engineering_adjudication",
        "policy_id": plan.get("plan_id"),
        "case_key": case_key,
        "research_as_of": plan.get("research_as_of"),
        "candidate_review_packet_digest": packet_digest,
        "predecessor_pack_payload_digest": plan.get(
            "predecessor_pack_payload_digest"
        ),
        "qualified_human_review": False,
        "S1_qualification_authorized": False,
        "product_publication_authorized": False,
        "successor_known_boundary": plan.get("successor_known_boundary"),
        "source_plan_id": plan.get("plan_id"),
        "source_plan_digest": plan_digest,
        "review_item_count": len(all_review_by_ref),
        "actionable_review_item_count": len(review_by_ref),
        "informational_review_item_count": len(all_review_by_ref) - len(review_by_ref),
        "decision_coverage": "human_review_required_items_only",
        "decisions": decisions,
    }
    return {**policy_body, "policy_digest": canonical_digest(policy_body)}


def _request_lanes(
    product_projection: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    lanes: dict[str, Mapping[str, Any]] = {}
    for raw_result in product_projection.get("request_results") or ():
        result = _mapping(raw_result, "product_evidence_request_result_invalid")
        request = _mapping(
            result.get("request"), "product_evidence_request_missing"
        )
        request_id = str(request.get("request_id") or "")
        lane_rows = list(result.get("lanes") or ())
        _require(
            request_id and len(lane_rows) == 1 and request_id not in lanes,
            "product_evidence_request_lane_identity_invalid",
        )
        lanes[request_id] = _mapping(
            _mapping(
                lane_rows[0], "product_evidence_lane_projection_invalid"
            ).get("lane"),
            "product_evidence_lane_missing",
        )
    return lanes


def _slot_binding_key(binding: Mapping[str, Any]) -> tuple[str, tuple[str, ...]]:
    return (
        str(binding.get("slot_id") or ""),
        tuple(sorted(str(value) for value in binding.get("facet_ids") or ())),
    )


def _relationship_direction(
    lane: Mapping[str, Any], *, owner: str, subject: str
) -> str:
    directions = {
        str(row.get("evidence_owner_ticker") or "").upper(): str(
            row.get("relationship_direction") or ""
        )
        for row in lane.get("owner_queries") or ()
        if isinstance(row, Mapping)
    }
    direction = directions.get(owner)
    if not direction and owner == subject:
        direction = "subject_self_disclosure"
    _require(bool(direction), "product_evidence_relationship_direction_missing")
    return direction


def build_product_evidence_successor(
    *,
    predecessor: Mapping[str, Any],
    product_projection: Mapping[str, Any],
    candidate_review_packet: Mapping[str, Any],
    policy: Mapping[str, Any],
    compiled_objects_by_id: Mapping[str, Mapping[str, Any]],
    source_records_by_id: Mapping[str, Mapping[str, Any]],
    parent_documents_by_id: Mapping[str, Mapping[str, Any]],
    capture_resolver: Callable[[str], Path],
    recorded_at: str,
    legacy_capture_attestations_by_parent_id: Mapping[
        str, Mapping[str, Any]
    ]
    | None = None,
) -> dict[str, Any]:
    """Materialize an internally reviewed, proposition-bound Evidence Pack.

    The policy must decide every unresolved item in the bounded review packet.
    Already accepted informational rows remain immutable predecessor state and are
    not re-adjudicated. Narrative claims may become capture-bound Evidence only for
    named requirement IDs. Metric rows can only be delegated to S2; this function
    never grants numeric authority or turns a table row into narrative Evidence.
    """

    validate_reviewed_evidence_pack(predecessor)
    normalized_policy = deepcopy(dict(policy))
    policy_digest = str(normalized_policy.pop("policy_digest", ""))
    case_key = str(policy.get("case_key") or "").upper()
    subject = str(product_projection.get("case_key") or "").upper()
    research_as_of = str(policy.get("research_as_of") or "")
    packet_digest = str(candidate_review_packet.get("review_packet_digest") or "")
    predecessor_research_as_of_values = {
        str(value.get("research_as_of") or "")
        for value in predecessor.get("evidence_items") or ()
        if isinstance(value, Mapping) and value.get("research_as_of")
    }
    predecessor_top_level_as_of = str(
        predecessor.get("research_as_of") or ""
    )
    if predecessor_top_level_as_of:
        predecessor_research_as_of_values.add(predecessor_top_level_as_of)
    _require(
        policy.get("schema_version") == POLICY_SCHEMA_VERSION
        and policy.get("status") == "approved_internal_engineering_adjudication"
        and policy_digest == canonical_digest(normalized_policy)
        and case_key
        and case_key == subject
        and case_key == str(predecessor.get("case_key") or "").upper()
        and case_key == str(candidate_review_packet.get("case_key") or "").upper()
        and research_as_of
        == str((product_projection.get("objective") or {}).get("research_as_of") or "")
        and predecessor_research_as_of_values in (set(), {research_as_of})
        and str(policy.get("candidate_review_packet_digest") or "") == packet_digest
        and str(policy.get("predecessor_pack_payload_digest") or "")
        == str(predecessor.get("pack_payload_digest") or ""),
        "product_evidence_policy_binding_invalid",
    )
    _require(
        policy.get("qualified_human_review") is False
        and policy.get("S1_qualification_authorized") is False
        and policy.get("product_publication_authorized") is False,
        "product_evidence_policy_authority_invalid",
    )

    all_review_by_ref = _review_items_by_ref(candidate_review_packet)
    review_by_ref = _actionable_review_items_by_ref(candidate_review_packet)
    requirement_ids_by_request = _requirement_ids_by_request(
        candidate_review_packet
    )
    lanes = _request_lanes(product_projection)
    raw_decisions = [
        _mapping(value, "product_evidence_policy_decision_invalid")
        for value in policy.get("decisions") or ()
    ]
    decision_by_ref = {
        str(value.get("review_item_ref") or ""): value for value in raw_decisions
    }
    _require(
        len(raw_decisions) == len(decision_by_ref)
        and set(decision_by_ref) == set(review_by_ref),
        "product_evidence_policy_decision_coverage_invalid",
    )

    accepted_by_object: dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {}
    adjudicated_binding_keys_by_object: dict[
        str, set[tuple[str, tuple[str, ...]]]
    ] = {}
    decision_receipts: list[dict[str, Any]] = []
    for review_ref in sorted(review_by_ref):
        review = review_by_ref[review_ref]
        decision = decision_by_ref[review_ref]
        action = str(decision.get("action") or "")
        _require(
            action in DECISION_ACTIONS
            and str(decision.get("review_item_digest") or "")
            == str(review.get("review_item_digest") or ""),
            "product_evidence_decision_identity_invalid",
        )
        object_id = str(review.get("compiled_object_id") or "")
        object_kind = str(review.get("object_kind") or "")
        request_id = str(review.get("request_id") or "")
        lane = _mapping(
            lanes.get(request_id), f"product_evidence_lane_missing:{request_id}"
        )
        adjudicated_binding_keys_by_object.setdefault(object_id, set()).add(
            (
                str(lane.get("slot_id") or ""),
                (str(lane.get("facet_id") or ""),),
            )
        )
        allowed_requirement_ids = requirement_ids_by_request.get(
            request_id, frozenset()
        )
        requirement_ids = tuple(
            sorted(str(value) for value in decision.get("requirement_ids") or ())
        )
        if action == "accept_for_requirements":
            _require(
                object_kind == "claim"
                and requirement_ids
                and set(requirement_ids) <= allowed_requirement_ids
                and str(decision.get("business_meaning_zh") or "")
                and str(decision.get("claim_boundary_zh") or ""),
                "product_evidence_acceptance_scope_invalid",
            )
            accepted_by_object.setdefault(object_id, []).append((review, decision))
        elif action == "accept_for_request_context":
            _require(
                object_kind == "claim"
                and not requirement_ids
                and str(decision.get("business_meaning_zh") or "")
                and str(decision.get("claim_boundary_zh") or ""),
                "product_evidence_context_acceptance_scope_invalid",
            )
            accepted_by_object.setdefault(object_id, []).append((review, decision))
        elif action == "delegate_to_s2_numeric_authority":
            _require(
                object_kind == "metric_row" and not requirement_ids,
                "product_evidence_numeric_delegation_invalid",
            )
        else:
            _require(
                not requirement_ids,
                "product_evidence_rejection_requirement_binding_invalid",
            )
        receipt_body = {
            "review_item_ref": review_ref,
            "review_item_digest": review.get("review_item_digest"),
            "request_id": review.get("request_id"),
            "compiled_object_id": object_id,
            "action": action,
            "requirement_ids": list(requirement_ids),
            "reason_codes": sorted(
                str(value) for value in decision.get("reason_codes") or ()
            ),
            "adjudicator_class": "internal_engineering_not_qualified_human",
            "candidate_text_promoted": False,
            "numeric_authority_granted": False,
            "S1_qualification_authorized": False,
        }
        decision_receipts.append(
            {**receipt_body, "decision_receipt_digest": canonical_digest(receipt_body)}
        )

    predecessor_items = [
        deepcopy(dict(value)) for value in predecessor.get("evidence_items") or ()
    ]
    predecessor_materials = [
        deepcopy(dict(value)) for value in predecessor.get("source_materials") or ()
    ]
    accepted_object_ids = set(accepted_by_object)
    retired_items = [
        row
        for row in predecessor_items
        if str(row.get("compiled_object_id") or "") in accepted_object_ids
    ]
    live_items = [
        row
        for row in predecessor_items
        if str(row.get("compiled_object_id") or "") not in accepted_object_ids
    ]
    retired_items_by_object: dict[str, list[Mapping[str, Any]]] = {}
    for row in retired_items:
        retired_items_by_object.setdefault(
            str(row.get("compiled_object_id") or ""), []
        ).append(row)
    live_material_refs = {
        str(row.get("source_material_ref") or "") for row in live_items
    }
    materials = [
        row
        for row in predecessor_materials
        if str(row.get("material_ref") or "") in live_material_refs
    ]

    capture_receipts: list[dict[str, Any]] = []
    added_items: list[dict[str, Any]] = []
    added_materials: list[dict[str, Any]] = []
    for object_id in sorted(accepted_by_object):
        rows = accepted_by_object[object_id]
        compiled = _mapping(
            compiled_objects_by_id.get(object_id),
            f"product_evidence_compiled_object_missing:{object_id}",
        )
        base = _mapping(
            compiled.get("base_object_view"),
            "product_evidence_compiled_base_missing",
        )
        source_id = str(base.get("source_record_id") or "")
        source = _mapping(
            source_records_by_id.get(source_id),
            f"product_evidence_source_record_missing:{source_id}",
        )
        metadata = _mapping(
            source.get("metadata"), "product_evidence_source_metadata_missing"
        )
        parent_id = str(metadata.get("parent_document_id") or "")
        parent = _mapping(
            parent_documents_by_id.get(parent_id),
            f"product_evidence_parent_document_missing:{parent_id}",
        )
        capture = verify_capture_bound_object(
            compiled_object=compiled,
            source_record=source,
            parent_document=parent,
            research_as_of=research_as_of,
            capture_resolver=capture_resolver,
            legacy_capture_attestation=(
                dict(legacy_capture_attestations_by_parent_id or {}).get(parent_id)
            ),
        )
        capture_receipts.append(capture)
        slot_bindings: list[dict[str, Any]] = []
        relationship_directions: set[str] = set()
        for review, decision in sorted(
            rows, key=lambda value: str(value[0].get("request_id") or "")
        ):
            request_id = str(review.get("request_id") or "")
            lane = _mapping(
                lanes.get(request_id),
                f"product_evidence_lane_missing:{request_id}",
            )
            owner = str(review.get("evidence_owner_ticker") or "").upper()
            direction = _relationship_direction(
                lane, owner=owner, subject=subject
            )
            role = evaluate_evidence_role(
                {
                    **dict(base),
                    "document_text": base.get("surface_text"),
                    "object_kind": compiled.get("object_kind"),
                },
                slot_id=str(lane.get("slot_id") or ""),
                facet_id=str(lane.get("facet_id") or ""),
                subject_ticker=subject,
                evidence_owner_ticker=owner,
                relationship_direction=direction,
            )
            _require(
                role.compatibility == "compatible",
                "product_evidence_role_incompatible",
            )
            relationship_directions.add(direction)
            slot_bindings.append(
                {
                    "slot_id": lane.get("slot_id"),
                    "facet_ids": [lane.get("facet_id")],
                    "requirement_ids": sorted(
                        str(value) for value in decision.get("requirement_ids") or ()
                    ),
                    "binding_kind": (
                        "requirement_evidence"
                        if decision.get("action") == "accept_for_requirements"
                        else "request_context"
                    ),
                    "business_meaning_zh": decision.get("business_meaning_zh"),
                    "claim_boundary_zh": decision.get("claim_boundary_zh"),
                    "qualification_id": policy.get("policy_id"),
                }
            )
        new_binding_keys = [_slot_binding_key(row) for row in slot_bindings]
        _require(
            len(new_binding_keys) == len(set(new_binding_keys)),
            "product_evidence_new_slot_binding_duplicate",
        )
        adjudicated_keys = adjudicated_binding_keys_by_object.get(object_id, set())
        for predecessor_item in retired_items_by_object.get(object_id, ()):
            relationship_directions.update(
                str(value)
                for value in predecessor_item.get("relationship_directions") or ()
                if str(value)
            )
            for raw_binding in predecessor_item.get("slot_bindings") or ():
                binding = _mapping(
                    raw_binding, "product_evidence_predecessor_slot_binding_invalid"
                )
                if _slot_binding_key(binding) not in adjudicated_keys:
                    slot_bindings.append(deepcopy(dict(binding)))
        merged_binding_keys = [_slot_binding_key(row) for row in slot_bindings]
        _require(
            all(key[0] and key[1] for key in merged_binding_keys)
            and len(merged_binding_keys) == len(set(merged_binding_keys)),
            "product_evidence_merged_slot_binding_invalid",
        )
        slot_bindings.sort(
            key=lambda row: (
                str(row.get("slot_id") or ""),
                tuple(sorted(str(value) for value in row.get("facet_ids") or ())),
                str(row.get("binding_kind") or ""),
            )
        )
        item, material = build_capture_bound_evidence_pair(
            case_key=case_key,
            research_as_of=research_as_of,
            compiled_object=compiled,
            source_record=source,
            capture_receipt=capture,
            evidence_spec={
                "slot_bindings": slot_bindings,
                "relationship_directions": sorted(relationship_directions),
                "disposition": (
                    "accepted_direct_source_evidence"
                    if str(base.get("ticker") or "").upper() == subject
                    else "accepted_bounded_context_evidence"
                ),
            },
        )
        added_items.append(item)
        added_materials.append(material)

    target_ids = {str(row.get("target_id") or "") for row in live_items}
    material_refs = {str(row.get("material_ref") or "") for row in materials}
    for item, material in zip(added_items, added_materials, strict=True):
        _require(
            str(item.get("target_id") or "") not in target_ids
            and str(material.get("material_ref") or "") not in material_refs,
            "product_evidence_successor_identity_collision",
        )
        target_ids.add(str(item.get("target_id") or ""))
        material_refs.add(str(material.get("material_ref") or ""))
        live_items.append(item)
        materials.append(material)

    action_counts = Counter(
        str(value.get("action") or "") for value in raw_decisions
    )
    successor = deepcopy(dict(predecessor))
    successor.pop("pack_payload_digest", None)
    successor["research_as_of"] = research_as_of
    new_receipt_keys = {
        (str(row.get("request_id") or ""), str(row.get("compiled_object_id") or ""))
        for row in decision_receipts
    }
    retained_receipts = [
        deepcopy(dict(row))
        for row in predecessor.get("candidate_adjudication_receipts") or ()
        if isinstance(row, Mapping)
        and (
            str(row.get("request_id") or ""),
            str(row.get("compiled_object_id") or ""),
        )
        not in new_receipt_keys
    ]
    successor["candidate_adjudication_receipts"] = sorted(
        retained_receipts + decision_receipts,
        key=lambda row: (
            str(row.get("request_id") or ""),
            str(row.get("compiled_object_id") or ""),
        ),
    )
    successor["evidence_items"] = live_items
    successor["source_materials"] = materials
    successor["observed_counts"] = {
        **dict(successor.get("observed_counts") or {}),
        "accepted_evidence_items": len(live_items),
        "direct_evidence_items": sum(
            row.get("disposition") == "accepted_direct_source_evidence"
            for row in live_items
        ),
        "bounded_context_items": sum(
            row.get("disposition") == "accepted_bounded_context_evidence"
            for row in live_items
        ),
        "source_materials": len(materials),
        "residual_gaps": len(successor.get("residual_gaps") or ()),
    }
    successor["content_gate_basis"] = (
        "reviewed_predecessor_plus_proposition_bound_capture_first_adjudication"
    )
    successor["successor_lineage"] = {
        "recorded_at": recorded_at,
        "policy_id": policy.get("policy_id"),
        "policy_digest": policy_digest,
        "candidate_review_packet_digest": packet_digest,
        "predecessor_pack_payload_digest": predecessor.get("pack_payload_digest"),
        "retired_evidence_item_digests": sorted(
            str(row.get("evidence_item_digest") or "") for row in retired_items
        ),
        "added_evidence_item_digests": sorted(
            str(row.get("evidence_item_digest") or "") for row in added_items
        ),
        "decision_receipt_digests": sorted(
            str(row.get("decision_receipt_digest") or "")
            for row in decision_receipts
        ),
        "capture_receipt_digests": sorted(
            str(row.get("receipt_digest") or "") for row in capture_receipts
        ),
    }
    successor["known_boundary"] = str(policy.get("successor_known_boundary") or "")
    successor["pack_payload_digest"] = canonical_digest(successor)
    validate_reviewed_evidence_pack(successor)

    result_body = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "proposition_bound_evidence_successor_materialized",
        "recorded_at": recorded_at,
        "case_key": case_key,
        "research_as_of": research_as_of,
        "policy_id": policy.get("policy_id"),
        "predecessor_pack_payload_digest": predecessor.get("pack_payload_digest"),
        "successor_pack": successor,
        "decision_counts": {
            action: action_counts.get(action, 0) for action in DECISION_ACTIONS
        },
        "review_scope_counts": {
            "review_items": len(all_review_by_ref),
            "actionable_review_items": len(review_by_ref),
            "informational_review_items_preserved": len(all_review_by_ref)
            - len(review_by_ref),
        },
        "decision_receipts": decision_receipts,
        "capture_receipts": capture_receipts,
        "coverage_delta": {
            "predecessor_evidence_count": len(predecessor_items),
            "successor_evidence_count": len(live_items),
            "retired_evidence_count": len(retired_items),
            "added_or_rebound_evidence_count": len(added_items),
            "numeric_rows_delegated_to_S2": action_counts[
                "delegate_to_s2_numeric_authority"
            ],
            "candidate_text_promoted_count": 0,
            "numeric_authority_granted_count": 0,
        },
        "authority": {
            "candidate_is_not_evidence": True,
            "accepted_claims_capture_bound": True,
            "accepted_evidence_proposition_bound": True,
            "metric_row_promoted_as_narrative_evidence": False,
            "numeric_fact_authority": False,
            "qualified_human_review": False,
            "S1_qualification_claimed": False,
            "product_publication": False,
            "network_calls": 0,
            "generation_model_calls": 0,
        },
    }
    return {**result_body, "result_digest": canonical_digest(result_body)}


__all__ = [
    "ADJUDICATION_PLAN_SCHEMA_VERSION",
    "CURRENT_COMPOSITION_LINEAGE_SCHEMA_VERSION",
    "CURRENT_PRODUCT_READINESS_SCHEMA_VERSION",
    "DECISION_ACTIONS",
    "POLICY_SCHEMA_VERSION",
    "RESULT_SCHEMA_VERSION",
    "ProductEvidenceSuccessorError",
    "compile_product_evidence_adjudication_policy",
    "build_product_evidence_successor",
    "project_current_product_evidence_successor_lineage",
]
