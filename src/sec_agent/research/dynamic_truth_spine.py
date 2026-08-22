from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, Mapping, Sequence

from sec_agent.research.reviewed_evidence_pack import canonical_digest
from sec_agent.research.claim_authority import (
    CLAIM_AUTHORITY_DYNAMIC_POLICY_SCHEMA_VERSION,
    load_claim_authority_policy,
)
from sec_agent.research.claim_surface_authority import (
    CLAIM_SURFACE_DYNAMIC_RELATION_ALIAS_POLICY_SCHEMA_VERSION,
    CLAIM_SURFACE_RELATION_ALIAS_POLICY_SCHEMA_VERSION,
    load_claim_surface_authority_policy,
)


DYNAMIC_TRUTH_SPINE_POLICY_SCHEMA_VERSION = (
    "fin_ia_dynamic_truth_spine_policy_v1_0"
)
DYNAMIC_TRUTH_SPINE_POLICY_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_dynamic_truth_spine_policy_v1_1"
)
EVIDENCE_RESPONSE_SCHEMA_VERSION = "fin_ia_evidence_response_v1_0"
DYNAMIC_EVIDENCE_RESPONSE_SET_SCHEMA_VERSION = (
    "fin_ia_dynamic_evidence_response_set_v1_0"
)
DYNAMIC_REVIEWED_PACK_VIEW_SCHEMA_VERSION = (
    "fin_ia_dynamic_reviewed_evidence_pack_view_v1_0"
)
DYNAMIC_RESEARCH_INPUT_SCHEMA_VERSION = "fin_ia_dynamic_current_research_input_v1_0"


class DynamicTruthSpineError(ValueError):
    """A dynamic S1/S2 result crossed a financial-truth boundary."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DynamicTruthSpineError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _strings(value: object, code: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    _require(isinstance(value, list), code)
    output = tuple(str(item).strip() for item in value)
    _require(
        (allow_empty or bool(output))
        and all(output)
        and len(output) == len(set(output)),
        code,
    )
    return output


def load_dynamic_truth_spine_policy(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Load the provider-neutral candidate-to-reviewed-Evidence selector policy."""

    schema_version = str(payload.get("schema_version") or "")
    _require(
        schema_version
        in {
            DYNAMIC_TRUTH_SPINE_POLICY_SCHEMA_VERSION,
            DYNAMIC_TRUTH_SPINE_POLICY_SUCCESSOR_SCHEMA_VERSION,
        },
        "dynamic_truth_spine_policy_schema_invalid",
    )
    _require(
        payload.get("status")
        == "provider_neutral_dynamic_reviewed_evidence_reselection",
        "dynamic_truth_spine_policy_status_invalid",
    )
    states = _strings(
        payload.get("allowed_decision_states"),
        "dynamic_truth_spine_decision_states_invalid",
    )
    _require(
        set(states)
        == {"accepted", "rejected", "typed_gap", "needs_human_review"},
        "dynamic_truth_spine_decision_states_invalid",
    )
    matching = _mapping(
        payload.get("reviewed_evidence_matching"),
        "dynamic_truth_spine_matching_policy_invalid",
    )
    route_merge = matching.get("candidate_route_merge")
    if schema_version == DYNAMIC_TRUTH_SPINE_POLICY_SCHEMA_VERSION:
        _require(
            route_merge is None,
            "dynamic_truth_spine_legacy_route_merge_forbidden",
        )
    else:
        _require(
            route_merge == "hybrid_plus_immutable_snapshot_union",
            "dynamic_truth_spine_successor_route_merge_invalid",
        )
    _require(
        matching.get("exact_case_identity_required") is True
        and matching.get("writer_citable_required") is True
        and matching.get("exact_candidate_lineage_required") is True
        and matching.get("request_slot_binding_required") is True
        and matching.get("request_owner_required") is True
        and matching.get("request_source_type_required") is True
        and matching.get("as_of_and_period_required") is True
        and matching.get("rank_never_grants_authority") is True
        and matching.get("advisory_role_never_grants_authority") is True,
        "dynamic_truth_spine_matching_policy_invalid",
    )
    authority = _mapping(
        payload.get("authority"),
        "dynamic_truth_spine_authority_invalid",
    )
    _require(
        authority.get("candidate_is_never_evidence") is True
        and authority.get("already_reviewed_evidence_may_be_reselected") is True
        and authority.get("new_evidence_promotion_requires_separate_gate") is True
        and authority.get("numeric_authority_remains_s2") is True
        and authority.get("model_may_not_promote_or_bind_evidence") is True,
        "dynamic_truth_spine_authority_invalid",
    )
    return {
        **deepcopy(dict(payload)),
        "allowed_decision_states": list(states),
        "reviewed_evidence_matching": deepcopy(dict(matching)),
        "authority": deepcopy(dict(authority)),
    }


def _request_slot_ids(request_result: Mapping[str, Any]) -> set[str]:
    query_plan = _mapping(
        request_result.get("query_plan"),
        "dynamic_truth_spine_query_plan_missing",
    )
    lanes = query_plan.get("lanes")
    _require(isinstance(lanes, list) and bool(lanes), "dynamic_truth_spine_lanes_missing")
    output = {
        str(_mapping(row, "dynamic_truth_spine_lane_invalid").get("slot_id") or "")
        for row in lanes
    }
    _require("" not in output, "dynamic_truth_spine_lane_slot_missing")
    return output


def _request_bindings(
    request_result: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    query_plan = _mapping(
        request_result.get("query_plan"),
        "dynamic_truth_spine_query_plan_missing",
    )
    lanes = query_plan.get("lanes")
    _require(isinstance(lanes, list) and bool(lanes), "dynamic_truth_spine_lanes_missing")
    output: dict[tuple[str, str], dict[str, str]] = {}
    for raw in lanes:
        lane = _mapping(raw, "dynamic_truth_spine_lane_invalid")
        slot_id = str(lane.get("slot_id") or "")
        facet_id = str(lane.get("facet_id") or "")
        _require(slot_id and facet_id, "dynamic_truth_spine_lane_binding_missing")
        output[(slot_id, facet_id)] = {
            "slot_id": slot_id,
            "facet_id": facet_id,
        }
    return tuple(output[key] for key in sorted(output))


def _candidate_identity(candidate: Mapping[str, Any]) -> tuple[str, str]:
    source_id = str(candidate.get("source_record_id") or "")
    _require(source_id, "dynamic_truth_spine_candidate_source_id_missing")
    return source_id, str(candidate.get("compiled_object_id") or "")


def _merge_candidate_rows(
    *candidate_groups: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    """Keep every independently reached candidate without granting authority.

    Hybrid ranking and immutable snapshot lookup are two candidate-producing
    routes.  Neither is Evidence authority.  A ranked hybrid list therefore
    must not erase an exact snapshot hit that may already bind to reviewed
    Evidence.  The union remains candidate-only and is deterministically
    de-duplicated by source/object identity.
    """

    merged: dict[tuple[str, str], dict[str, Any]] = {}
    order: list[tuple[str, str]] = []
    for group in candidate_groups:
        for raw in group:
            candidate = deepcopy(dict(raw))
            key = _candidate_identity(candidate)
            if key not in merged:
                merged[key] = candidate
                order.append(key)
                continue
            existing = merged[key]
            lineage = {
                str(value)
                for value in existing.get("lineage_source_record_ids") or ()
            }
            lineage.update(
                str(value)
                for value in candidate.get("lineage_source_record_ids") or ()
            )
            lineage.discard("")
            if lineage:
                existing["lineage_source_record_ids"] = sorted(lineage)
    return tuple(merged[key] for key in order)


def _snapshot_candidate_rows(
    request_result: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    output: list[dict[str, Any]] = []
    for raw_lane in request_result.get("lanes") or ():
        lane = _mapping(raw_lane, "dynamic_truth_spine_result_lane_invalid")
        _require(
            lane.get("candidate_state") == "candidate_not_evidence",
            "dynamic_truth_spine_candidate_state_invalid",
        )
        raw = lane.get("candidates")
        _require(isinstance(raw, list), "dynamic_truth_spine_candidates_invalid")
        output.extend(
            deepcopy(dict(row)) for row in raw if isinstance(row, Mapping)
        )
    return tuple(output)


def _candidate_rows(
    request_result: Mapping[str, Any],
    *,
    merge_immutable_snapshot: bool,
) -> tuple[dict[str, Any], ...]:
    snapshot = _snapshot_candidate_rows(request_result)
    hybrid = request_result.get("hybrid_object_retrieval")
    if isinstance(hybrid, Mapping):
        _require(
            hybrid.get("candidate_state") == "candidate_not_evidence",
            "dynamic_truth_spine_candidate_state_invalid",
        )
        raw = hybrid.get("candidates")
        _require(isinstance(raw, list), "dynamic_truth_spine_candidates_invalid")
        hybrid_rows = tuple(
            deepcopy(dict(row)) for row in raw if isinstance(row, Mapping)
        )
        return (
            _merge_candidate_rows(hybrid_rows, snapshot)
            if merge_immutable_snapshot
            else hybrid_rows
        )
    return _merge_candidate_rows(snapshot) if merge_immutable_snapshot else snapshot


def _candidate_lineage(candidate: Mapping[str, Any]) -> set[str]:
    source_id = str(candidate.get("source_record_id") or "")
    _require(source_id, "dynamic_truth_spine_candidate_source_id_missing")
    lineage = candidate.get("lineage_source_record_ids")
    if lineage is None:
        return {source_id}
    _require(isinstance(lineage, list), "dynamic_truth_spine_candidate_lineage_invalid")
    output = {source_id, *(str(value) for value in lineage)}
    _require("" not in output, "dynamic_truth_spine_candidate_lineage_invalid")
    return output


def _candidate_source_content_digest(candidate: Mapping[str, Any]) -> str:
    return str(candidate.get("source_content_digest") or "").strip()


def _candidate_owner(candidate: Mapping[str, Any]) -> str:
    return str(
        candidate.get("evidence_owner_ticker")
        or candidate.get("ticker")
        or ""
    ).upper()


def _item_matches_period(
    item: Mapping[str, Any],
    period: Mapping[str, Any],
) -> bool:
    source = _mapping(
        item.get("source"), "dynamic_truth_spine_item_source_invalid"
    )
    period_end = str(
        item.get("source_reporting_period_end")
        or source.get("period_end")
        or ""
    )
    if not period_end and (
        str(source.get("source_type") or "") == "PUBLIC_WEB"
        or str(item.get("claim_use") or "")
        in {
            "bounded_market_context",
            "counterevidence",
            "industry_exact_fact",
            "speaker_attributed_mechanism",
            "speaker_exact_fact",
        }
    ):
        # Point-in-time market and ecosystem read-throughs may not describe a
        # target-company reporting period.  A reviewed PUBLIC_WEB item likewise
        # carries publication-time context even when its role vocabulary evolves
        # (for example channel configuration or trusted analysis).  Its
        # publication date is the appropriate temporal boundary; this never
        # turns it into a target-company fact or NumericFact.
        period_end = str(item.get("publication_date") or "")
    start = str(period.get("start_date") or "")
    end = str(period.get("end_date") or "")
    if start and (not period_end or period_end < start):
        return False
    if end and (not period_end or period_end > end):
        return False
    fiscal_years = period.get("fiscal_years") or []
    if fiscal_years:
        # Reviewed Evidence objects do not all carry a normalized fiscal year.
        # When it is present it must match; otherwise the exact date window and
        # source review remain the fail-closed authority.
        fiscal_year = item.get("fiscal_year")
        if fiscal_year is not None and int(fiscal_year) not in {
            int(value) for value in fiscal_years
        }:
            return False
    return True


def _item_gate_reason(
    item: Mapping[str, Any],
    *,
    case_key: str,
    request: Mapping[str, Any],
    request_slot_ids: set[str],
) -> str | None:
    if str(item.get("case_key") or "").upper() != case_key:
        return "cross_case_reviewed_item"
    if item.get("writer_citable") is not True:
        return "reviewed_item_not_writer_citable"
    source = _mapping(
        item.get("source"), "dynamic_truth_spine_item_source_invalid"
    )
    owner = str(source.get("evidence_owner_ticker") or "").upper()
    target_entities = {str(value).upper() for value in request["target_entities"]}
    if owner not in target_entities:
        return "reviewed_item_owner_outside_request"
    if str(source.get("source_type") or "") not in set(
        request["acceptable_sources"]
    ):
        return "reviewed_item_source_type_outside_request"
    publication_date = str(item.get("publication_date") or "")
    research_as_of = str(request.get("research_as_of") or "")
    try:
        if not publication_date or date.fromisoformat(publication_date) > date.fromisoformat(
            research_as_of
        ):
            return "reviewed_item_after_research_as_of"
    except ValueError as exc:
        raise DynamicTruthSpineError(
            "dynamic_truth_spine_reviewed_item_date_invalid"
        ) from exc
    if not _item_matches_period(item, _mapping(request["period"], "dynamic_truth_spine_period_invalid")):
        return "reviewed_item_outside_request_period"
    item_slots = {
        str(_mapping(row, "dynamic_truth_spine_slot_binding_invalid").get("slot_id") or "")
        for row in item.get("slot_bindings") or ()
    }
    if not item_slots.intersection(request_slot_ids):
        return "reviewed_item_outside_request_slot"
    return None


def compile_dynamic_evidence_responses(
    *,
    policy: Mapping[str, Any],
    controlled_plan: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
) -> dict[str, Any]:
    """Reselect only already-reviewed Evidence reached by real S1 requests.

    This function deliberately cannot promote a new retrieval candidate.  It
    joins candidate lineage to an immutable reviewed Pack, then rechecks case,
    owner, source type, period/as-of and Evidence Slot.  Everything else remains
    candidate-only and is surfaced as a review need or typed gap.
    """

    loaded = load_dynamic_truth_spine_policy(policy)
    _require(
        controlled_plan.get("status")
        == "controlled_research_plan_zero_call_executed",
        "dynamic_truth_spine_controlled_plan_invalid",
    )
    objective = _mapping(
        controlled_plan.get("objective"),
        "dynamic_truth_spine_objective_missing",
    )
    case_key = str(objective.get("case_key") or "").upper()
    _require(
        case_key
        and str(evidence_pack.get("case_key") or "").upper() == case_key,
        "dynamic_truth_spine_case_binding_invalid",
    )
    reviewed_by_source: dict[str, list[Mapping[str, Any]]] = {}
    reviewed_by_digest: dict[str, Mapping[str, Any]] = {}
    source_materials_by_ref = {
        str(material.get("material_ref") or ""): material
        for raw_material in evidence_pack.get("source_materials") or ()
        for material in (
            _mapping(
                raw_material,
                "dynamic_truth_spine_source_material_invalid",
            ),
        )
        if str(material.get("material_ref") or "")
    }
    for raw_item in evidence_pack.get("evidence_items") or ():
        item = _mapping(raw_item, "dynamic_truth_spine_reviewed_item_invalid")
        if not isinstance(item.get("source"), Mapping):
            source_material_ref = str(item.get("source_material_ref") or "")
            source_material = source_materials_by_ref.get(source_material_ref)
            _require(
                source_material is not None,
                "dynamic_truth_spine_item_source_material_missing",
            )
            item = {**dict(item), "source": deepcopy(dict(source_material))}
        source_id = str(item.get("source_record_id") or "")
        digest = str(item.get("evidence_item_digest") or "")
        _require(source_id and digest and digest not in reviewed_by_digest, "dynamic_truth_spine_reviewed_item_identity_invalid")
        reviewed_by_source.setdefault(source_id, []).append(item)
        reviewed_by_digest[digest] = item

    request_results = controlled_plan.get("request_results")
    _require(
        isinstance(request_results, list) and bool(request_results),
        "dynamic_truth_spine_request_results_missing",
    )
    responses: list[dict[str, Any]] = []
    all_accepted_digests: set[str] = set()
    for raw_result in request_results:
        result = _mapping(raw_result, "dynamic_truth_spine_request_result_invalid")
        request = _mapping(
            result.get("request"), "dynamic_truth_spine_request_missing"
        )
        request_id = str(request.get("request_id") or "")
        _require(
            request_id
            and str(request.get("case_key") or "").upper() == case_key
            and str(request.get("subject_ticker") or "").upper() == case_key
            and isinstance(request.get("target_entities"), list)
            and isinstance(request.get("acceptable_sources"), list)
            and isinstance(request.get("period"), Mapping),
            "dynamic_truth_spine_request_identity_invalid",
        )
        request_slots = _request_slot_ids(result)
        request_bindings = _request_bindings(result)
        merge_immutable_snapshot = (
            loaded["reviewed_evidence_matching"].get("candidate_route_merge")
            == "hybrid_plus_immutable_snapshot_union"
        )
        candidates = _candidate_rows(
            result,
            merge_immutable_snapshot=merge_immutable_snapshot,
        )
        accepted: dict[str, dict[str, Any]] = {}
        rejected: dict[tuple[str, str], dict[str, Any]] = {}
        needs_review: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            source_id = str(candidate.get("source_record_id") or "")
            owner = _candidate_owner(candidate)
            source_type = str(candidate.get("source_type") or "")
            source_content_digest = _candidate_source_content_digest(candidate)
            candidate_identity = {
                "request_id": request_id,
                "source_record_id": source_id,
                "compiled_object_id": candidate.get("compiled_object_id"),
            }
            # Preserve every historical SEC candidate receipt byte-for-byte.
            # Exact content-slice identity is an additive requirement only for
            # PUBLIC_WEB successors; an empty field must not rewrite old runs.
            if source_type == "PUBLIC_WEB" or source_content_digest:
                candidate_identity["source_content_digest"] = (
                    source_content_digest
                )
            candidate_ref = canonical_digest(candidate_identity)
            lineage = _candidate_lineage(candidate)
            matched_items = [
                item
                for lineage_id in lineage
                for item in reviewed_by_source.get(lineage_id, ())
                if source_type != "PUBLIC_WEB"
                or (
                    bool(source_content_digest)
                    and str(item.get("source_content_digest") or "")
                    == source_content_digest
                )
            ]
            if not matched_items:
                needs_review.setdefault(
                    candidate_ref,
                    {
                        "decision": "needs_human_review",
                        "candidate_ref": candidate_ref,
                        "candidate_source_record_id_digest": canonical_digest(
                            {"source_record_id": source_id}
                        ),
                        "candidate_owner_ticker": owner,
                        "candidate_source_type": source_type,
                        "reason": (
                            "public_candidate_source_content_digest_missing"
                            if source_type == "PUBLIC_WEB"
                            and not source_content_digest
                            else "candidate_content_slice_not_present_in_reviewed_pack"
                            if source_type == "PUBLIC_WEB"
                            else "candidate_not_present_in_reviewed_pack"
                        ),
                    },
                )
                continue
            for item in matched_items:
                digest = str(item["evidence_item_digest"])
                reason = _item_gate_reason(
                    item,
                    case_key=case_key,
                    request=request,
                    request_slot_ids=request_slots,
                )
                if reason is None:
                    accepted[digest] = {
                        "decision": "accepted",
                        "evidence_item_digest": digest,
                        "source_record_id": str(item["source_record_id"]),
                        "matched_slot_ids": sorted(
                            request_slots.intersection(
                                {
                                    str(binding.get("slot_id") or "")
                                    for binding in item.get("slot_bindings") or ()
                                    if isinstance(binding, Mapping)
                                }
                            )
                        ),
                        "authority": "already_reviewed_writer_citable_evidence",
                    }
                    all_accepted_digests.add(digest)
                else:
                    rejected[(digest, reason)] = {
                        "decision": "rejected",
                        "evidence_item_digest": digest,
                        "source_record_id": str(item["source_record_id"]),
                        "reason": reason,
                    }
        typed_gaps = []
        for raw_gap in result.get("typed_gaps") or ():
            gap = deepcopy(dict(_mapping(raw_gap, "dynamic_truth_spine_typed_gap_invalid")))
            typed_gaps.append(
                {
                    "decision": "typed_gap",
                    "gap": gap,
                    "gap_digest": canonical_digest(gap),
                }
            )
        if not accepted:
            gap = {
                "gap_code": "no_request_matched_reviewed_evidence",
                "request_id": request_id,
                "slot_ids": sorted(request_slots),
                "owning_stage": "S1",
                "disposition": str(request.get("clarification_policy") or "return_typed_gap"),
            }
            typed_gaps.append(
                {
                    "decision": "typed_gap",
                    "gap": gap,
                    "gap_digest": canonical_digest(gap),
                }
            )
        response_body = {
            "schema_version": EVIDENCE_RESPONSE_SCHEMA_VERSION,
            "request_id": request_id,
            "request_digest": str(result.get("request_digest") or canonical_digest(request)),
            "case_key": case_key,
            "request_slot_ids": sorted(request_slots),
            "request_bindings": list(request_bindings),
            "candidate_route": (
                (
                    "hybrid_plus_immutable_snapshot_union"
                    if merge_immutable_snapshot
                    else "hybrid_object_retrieval"
                )
                if isinstance(result.get("hybrid_object_retrieval"), Mapping)
                else "immutable_snapshot_lanes"
            ),
            "candidate_count": len(candidates),
            "accepted": sorted(accepted.values(), key=lambda row: row["evidence_item_digest"]),
            "rejected": sorted(
                rejected.values(),
                key=lambda row: (row["evidence_item_digest"], row["reason"]),
            ),
            "needs_human_review": sorted(
                needs_review.values(), key=lambda row: row["candidate_ref"]
            ),
            "typed_gaps": typed_gaps,
            "numeric_result_digest": canonical_digest(
                result.get("typed_fact_results") or []
            ),
            "authority": {
                "candidate_promoted_to_evidence": False,
                "reviewed_evidence_reselected": bool(accepted),
                "numeric_authority_remains_s2": True,
                "model_decision_used": False,
            },
        }
        responses.append(
            {
                **response_body,
                "evidence_response_digest": canonical_digest(response_body),
            }
        )
    response_set_body = {
        "schema_version": DYNAMIC_EVIDENCE_RESPONSE_SET_SCHEMA_VERSION,
        "status": "dynamic_reviewed_evidence_responses_compiled",
        "case_key": case_key,
        "objective_id": objective.get("objective_id"),
        "research_as_of": objective.get("research_as_of"),
        "controlled_plan_digest": controlled_plan.get("projection_digest"),
        "reviewed_pack_binding": {
            "artifact_digest": evidence_pack.get("artifact_digest"),
            "pack_payload_digest": evidence_pack.get("pack_payload_digest"),
            "projection_digest": evidence_pack.get("projection_digest"),
        },
        "responses": responses,
        "accepted_evidence_item_digests": sorted(all_accepted_digests),
        "summary": {
            "request_count": len(responses),
            "requests_with_accepted_evidence": sum(
                bool(row["accepted"]) for row in responses
            ),
            "accepted_reviewed_evidence_count": len(all_accepted_digests),
            "rejected_reviewed_binding_count": sum(
                len(row["rejected"]) for row in responses
            ),
            "unreviewed_candidate_count": sum(
                len(row["needs_human_review"]) for row in responses
            ),
            "typed_gap_count": sum(len(row["typed_gaps"]) for row in responses),
            "new_evidence_promotions": 0,
            "model_calls": 0,
            "network_calls": 0,
        },
        "policy_digest": canonical_digest(loaded),
        "authority": deepcopy(loaded["authority"]),
        "known_boundary": (
            "An accepted row is not a new Evidence promotion. It is an exact, "
            "request-scoped reselection of an immutable writer-citable item that "
            "already passed the reviewed Evidence Pack gate. Unreviewed candidates "
            "remain needs_human_review and never enter the model fact surface."
        ),
    }
    return {
        **response_set_body,
        "evidence_response_set_digest": canonical_digest(response_set_body),
    }


def compile_dynamic_reviewed_pack_view(
    *,
    evidence_pack: Mapping[str, Any],
    evidence_responses: Mapping[str, Any],
    required_slot_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Materialize the reviewed subset that a dynamic S3 cell may consume."""

    _require(
        evidence_responses.get("schema_version")
        == DYNAMIC_EVIDENCE_RESPONSE_SET_SCHEMA_VERSION
        and evidence_responses.get("status")
        == "dynamic_reviewed_evidence_responses_compiled",
        "dynamic_truth_spine_evidence_response_set_invalid",
    )
    case_key = str(evidence_responses.get("case_key") or "").upper()
    _require(
        case_key
        and str(evidence_pack.get("case_key") or "").upper() == case_key,
        "dynamic_truth_spine_pack_view_case_mismatch",
    )
    binding = _mapping(
        evidence_responses.get("reviewed_pack_binding"),
        "dynamic_truth_spine_pack_binding_missing",
    )
    _require(
        binding.get("artifact_digest") == evidence_pack.get("artifact_digest")
        and binding.get("pack_payload_digest")
        == evidence_pack.get("pack_payload_digest")
        and binding.get("projection_digest") == evidence_pack.get("projection_digest"),
        "dynamic_truth_spine_pack_binding_drift",
    )
    accepted = set(evidence_responses.get("accepted_evidence_item_digests") or ())
    _require(bool(accepted), "dynamic_truth_spine_no_reviewed_evidence_selected")
    selected_items = [
        deepcopy(dict(row))
        for row in evidence_pack.get("evidence_items") or ()
        if str(row.get("evidence_item_digest") or "") in accepted
    ]
    _require(
        len(selected_items) == len(accepted),
        "dynamic_truth_spine_selected_evidence_drift",
    )
    slots = (
        {str(value) for value in required_slot_ids}
        if required_slot_ids is not None
        else {
            str(slot)
            for response in evidence_responses.get("responses") or ()
            for slot in response.get("request_slot_ids") or ()
        }
    )
    _require(bool(slots) and "" not in slots, "dynamic_truth_spine_pack_view_slots_invalid")
    residual_gaps = [
        deepcopy(dict(row))
        for row in evidence_pack.get("residual_gaps") or ()
        if str(row.get("slot_id") or "") in slots
    ]
    # Request-execution gaps remain part of the typed EvidenceResponse.  They
    # must not be relabelled as reviewed-Pack residual gaps because the two
    # facet taxonomies have different authority and route semantics.
    unsigned = {
        key: deepcopy(value)
        for key, value in evidence_pack.items()
        if key not in {"schema_version", "status", "evidence_items", "residual_gaps", "projection_digest"}
    }
    unsigned.update(
        {
            "schema_version": DYNAMIC_REVIEWED_PACK_VIEW_SCHEMA_VERSION,
            "status": "dynamic_request_scoped_reviewed_evidence_pack_ready",
            "evidence_items": selected_items,
            "residual_gaps": residual_gaps,
            "dynamic_selection_binding": {
                "evidence_response_set_digest": evidence_responses[
                    "evidence_response_set_digest"
                ],
                "selected_evidence_item_digests": sorted(accepted),
                "selected_slot_ids": sorted(slots),
                "candidate_promotions": 0,
                "already_reviewed_evidence_reselected": True,
                "typed_evidence_response_gap_count": int(
                    evidence_responses.get("summary", {}).get(
                        "typed_gap_count"
                    )
                    or 0
                ),
            },
            "known_boundary": (
                "This is a request-scoped view over the immutable reviewed Pack. "
                "It contains no newly promoted retrieval candidate."
            ),
        }
    )
    return {**unsigned, "projection_digest": canonical_digest(unsigned)}


def bind_dynamic_evidence_responses_to_research_input(
    *,
    research_input: Mapping[str, Any],
    evidence_responses: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach compact EvidenceResponse receipts to their consuming cells.

    The model sees accepted reviewed-Evidence refs and typed gap codes, never
    raw unreviewed candidate text or rank-based truth claims.
    """

    _require(
        research_input.get("schema_version")
        == "fin_ia_current_research_input_v1_1",
        "dynamic_truth_spine_base_research_input_invalid",
    )
    _require(
        evidence_responses.get("schema_version")
        == DYNAMIC_EVIDENCE_RESPONSE_SET_SCHEMA_VERSION
        and evidence_responses.get("status")
        == "dynamic_reviewed_evidence_responses_compiled",
        "dynamic_truth_spine_evidence_response_set_invalid",
    )
    case_key = str(research_input.get("case_identity", {}).get("case_key") or "")
    _require(
        case_key
        and case_key == str(evidence_responses.get("case_key") or ""),
        "dynamic_truth_spine_research_input_case_mismatch",
    )
    evidence_ref_by_digest = {
        str(row.get("evidence_item_digest") or ""): str(
            row.get("evidence_ref") or ""
        )
        for row in research_input.get("evidence_cards") or ()
        if isinstance(row, Mapping)
    }
    _require(
        "" not in evidence_ref_by_digest,
        "dynamic_truth_spine_research_evidence_identity_invalid",
    )
    cards: list[dict[str, Any]] = []
    for raw in evidence_responses.get("responses") or ():
        response = _mapping(raw, "dynamic_truth_spine_response_invalid")
        accepted_refs = []
        for decision in response.get("accepted") or ():
            digest = str(decision.get("evidence_item_digest") or "")
            _require(
                digest in evidence_ref_by_digest,
                "dynamic_truth_spine_response_evidence_not_in_dynamic_input",
            )
            accepted_refs.append(evidence_ref_by_digest[digest])
        typed_gap_cards = []
        for typed in response.get("typed_gaps") or ():
            gap = _mapping(
                typed.get("gap"), "dynamic_truth_spine_response_gap_invalid"
            )
            typed_gap_cards.append(
                {
                    "gap_code": str(gap.get("gap_code") or ""),
                    "owning_stage": str(gap.get("owning_stage") or "S1"),
                    "disposition": str(
                        gap.get("disposition") or "return_typed_gap"
                    ),
                    "gap_digest": str(typed.get("gap_digest") or ""),
                }
            )
        card_body = {
            "request_id": str(response.get("request_id") or ""),
            "request_bindings": deepcopy(response.get("request_bindings") or []),
            "candidate_route": str(response.get("candidate_route") or ""),
            "candidate_count": int(response.get("candidate_count") or 0),
            "accepted_evidence_refs": sorted(set(accepted_refs)),
            "rejected_reviewed_binding_count": len(response.get("rejected") or ()),
            "unreviewed_candidate_count": len(
                response.get("needs_human_review") or ()
            ),
            "typed_gaps": typed_gap_cards,
            "numeric_result_digest": str(response.get("numeric_result_digest") or ""),
            "authority": deepcopy(response.get("authority") or {}),
        }
        ref = "ER::" + canonical_digest(card_body)[:16].upper()
        cards.append(
            {
                "evidence_response_ref": ref,
                **card_body,
                "evidence_response_card_digest": canonical_digest(card_body),
            }
        )
    _require(cards, "dynamic_truth_spine_response_cards_missing")
    unsigned = deepcopy(dict(research_input))
    unsigned.pop("research_input_digest", None)
    unsigned["schema_version"] = DYNAMIC_RESEARCH_INPUT_SCHEMA_VERSION
    unsigned["dynamic_evidence_response_cards"] = cards
    for cell in unsigned.get("cells") or ():
        cell_slots = {
            str(cell.get("primary_slot_id") or ""),
            *(str(value) for value in cell.get("supplemental_context_slot_ids") or ()),
        }
        cell_cards = [
            card
            for card in cards
            if any(
                str(binding.get("slot_id") or "") in cell_slots
                for binding in card["request_bindings"]
                if isinstance(binding, Mapping)
            )
        ]
        cell["allowed_evidence_response_refs"] = [
            card["evidence_response_ref"] for card in cell_cards
        ]
        request_scoped_evidence_refs = {
            str(ref)
            for card in cell_cards
            for ref in card["accepted_evidence_refs"]
        }
        prior_allowed_evidence_refs = {
            str(ref) for ref in cell.get("allowed_evidence_refs") or ()
        }
        cell["allowed_evidence_refs"] = sorted(
            request_scoped_evidence_refs
            & prior_allowed_evidence_refs
        )

        graph_pack = cell.get("graph_context_pack")
        if isinstance(graph_pack, Mapping):
            graph_body = deepcopy(dict(graph_pack))
            graph_body.pop("graph_context_digest", None)
            graph_body["edges"] = [
                deepcopy(dict(edge))
                for edge in graph_pack.get("edges") or ()
                if isinstance(edge, Mapping)
                and set(str(ref) for ref in edge.get("evidence_refs") or ())
                .issubset(request_scoped_evidence_refs)
            ]
            cell["graph_context_pack"] = {
                **graph_body,
                "graph_context_digest": canonical_digest(graph_body),
            }
            consumption = cell.get("context_consumption_contract")
            if isinstance(consumption, Mapping):
                narrowed_consumption = deepcopy(dict(consumption))
                narrowed_consumption["minimum_graph_edge_refs"] = min(
                    int(
                        narrowed_consumption.get(
                            "minimum_graph_edge_refs", 0
                        )
                        or 0
                    ),
                    len(graph_body["edges"]),
                )
                cell["context_consumption_contract"] = narrowed_consumption
    unsigned["dynamic_truth_spine_contract"] = {
        "evidence_response_set_digest": evidence_responses[
            "evidence_response_set_digest"
        ],
        "candidate_text_exposed_to_model": False,
        "candidate_promotions": 0,
        "accepted_rows_are_previously_reviewed_evidence": True,
        "typed_response_gaps_preserved_separately_from_reviewed_pack_gaps": True,
        "model_may_request_but_not_promote_evidence": True,
        "cell_evidence_is_request_scoped": True,
        "graph_edges_require_request_scoped_evidence": True,
    }
    unsigned["known_boundary"] = (
        str(unsigned.get("known_boundary") or "")
        + " Dynamic EvidenceResponse receipts record which real requests returned "
        "already-reviewed Evidence, typed gaps or unreviewed candidates; candidate "
        "text remains outside the model fact surface."
    )
    return {**unsigned, "research_input_digest": canonical_digest(unsigned)}


def compile_dynamic_claim_authority_policy(
    *,
    research_input: Mapping[str, Any],
    template_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Narrow a reviewed claim policy to authority present after retrieval.

    The template supplies finance semantics and lexical guards.  The dynamic
    compiler may only remove unavailable authority; it never invents a bridge,
    Evidence ref, NumericFact or gap.
    """

    _require(
        research_input.get("schema_version") == DYNAMIC_RESEARCH_INPUT_SCHEMA_VERSION,
        "dynamic_truth_spine_claim_input_invalid",
    )
    template = load_claim_authority_policy(template_policy)
    qualified = template["qualified_scope"]
    case_key = str(research_input.get("case_identity", {}).get("case_key") or "")
    cell_id = str(qualified.get("cell_id") or "")
    _require(
        case_key == str(qualified.get("case_key") or ""),
        "dynamic_truth_spine_claim_case_not_qualified",
    )
    cells = {
        str(row.get("cell_id") or ""): row
        for row in research_input.get("cells") or ()
        if isinstance(row, Mapping)
    }
    _require(cell_id in cells, "dynamic_truth_spine_claim_cell_not_qualified")
    cell = cells[cell_id]
    available_evidence = set(cell.get("allowed_evidence_refs") or ())
    available_gaps = set(cell.get("visible_gap_refs") or ())
    available_numeric = set(cell.get("allowed_numeric_refs") or ())
    filtered_bindings = {
        key: [ref for ref in refs if ref in available_evidence]
        for key, refs in template["evidence_bindings"].items()
    }
    template_bridge_gaps = list(template["bridge_gap_refs"])
    bridge_gaps = [ref for ref in template_bridge_gaps if ref in available_gaps]
    complete_bridge_gap_boundary = (
        bool(template_bridge_gaps)
        and len(bridge_gaps) == len(template_bridge_gaps)
    )

    def combination_available(row: Mapping[str, Any]) -> bool:
        bridge = str(row.get("causal_bridge_authority") or "")
        if bridge == "same_scope_observation_only":
            return bool(available_numeric)
        if bridge == "management_assertion_only":
            return bool(filtered_bindings["management_assertion_evidence_refs"])
        if bridge == "multi_driver_context_only":
            return bool(filtered_bindings["multi_driver_context_evidence_refs"])
        if bridge == "bridge_unavailable":
            return complete_bridge_gap_boundary
        return False

    combinations = [
        deepcopy(dict(row))
        for row in template["allowed_combinations"]
        if combination_available(row)
    ]
    _require(combinations, "dynamic_truth_spine_no_claim_authority_available")
    body = {
        "schema_version": CLAIM_AUTHORITY_DYNAMIC_POLICY_SCHEMA_VERSION,
        "status": "provider_neutral_dynamic_request_claim_authority",
        "qualified_scope": {
            "case_key": case_key,
            "cell_id": cell_id,
            "base_research_input_digest": research_input["research_input_digest"],
            "base_judgment_schema_version": qualified[
                "base_judgment_schema_version"
            ],
        },
        "allowed_claim_scopes": deepcopy(template["allowed_claim_scopes"]),
        "allowed_financial_scopes": deepcopy(
            template["allowed_financial_scopes"]
        ),
        "allowed_causal_bridge_authorities": sorted(
            {
                str(row["causal_bridge_authority"])
                for row in combinations
            }
        ),
        "allowed_combinations": combinations,
        "evidence_bindings": filtered_bindings,
        "bridge_gap_refs": bridge_gaps,
        "cross_scope_language_guard": deepcopy(
            template["cross_scope_language_guard"]
        ),
        "authority": {
            **deepcopy(template["authority"]),
            "dynamic_request_scoped_reselection": True,
            "candidate_promotion_forbidden": True,
        },
    }
    return body


def compile_dynamic_claim_surface_policy(
    *,
    claim_authority_input: Mapping[str, Any],
    template_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Project a fixed relation surface onto dynamic reviewed authority.

    The projection is monotonic: unavailable facts and relations are removed.
    The sole permitted expansion is allowing an already-authorized
    ``bridge_unavailable`` relation to fill ``thesis_atom`` when no positive
    thesis relation survives.  That expansion can only express an explicit
    ``not_inferable`` / ``insufficient_evidence`` abstention and grants no new
    Evidence, NumericFact or causal authority.
    """

    _require(
        claim_authority_input.get("schema_version")
        == "fin_ia_dynamic_current_research_input_v1_1"
        and claim_authority_input.get("model_output_contract", {}).get(
            "payload_schema_version"
        )
        == "fin_ia_current_research_judgment_payload_v1_3"
        and isinstance(
            claim_authority_input.get("claim_authority_contract"), Mapping
        )
        and claim_authority_input["claim_authority_contract"].get(
            "dynamic_retrieval_executed"
        )
        is True
        and claim_authority_input["claim_authority_contract"].get(
            "candidate_promotions"
        )
        == 0,
        "dynamic_truth_spine_claim_surface_input_invalid",
    )
    template = load_claim_surface_authority_policy(template_policy)
    _require(
        template["schema_version"]
        == CLAIM_SURFACE_RELATION_ALIAS_POLICY_SCHEMA_VERSION,
        "dynamic_truth_spine_claim_surface_template_invalid",
    )
    qualified = template["qualified_scope"]
    case_key = str(
        claim_authority_input.get("case_identity", {}).get("case_key") or ""
    )
    cell_id = str(qualified.get("cell_id") or "")
    _require(
        case_key == str(qualified.get("case_key") or ""),
        "dynamic_truth_spine_claim_surface_case_not_qualified",
    )
    cells = {
        str(row.get("cell_id") or ""): row
        for row in claim_authority_input.get("cells") or ()
        if isinstance(row, Mapping)
    }
    _require(
        cell_id in cells,
        "dynamic_truth_spine_claim_surface_cell_not_qualified",
    )
    cell = cells[cell_id]
    available_evidence = set(cell.get("allowed_evidence_refs") or ())
    available_numeric_relations = set(
        cell.get("allowed_numeric_relation_refs") or ()
    )
    available_gaps = set(cell.get("visible_gap_refs") or ())

    facts = [
        deepcopy(dict(row))
        for row in template["source_bound_qualitative_facts"]
        if str(row.get("source_evidence_ref") or "") in available_evidence
    ]
    available_qualitative_facts = {
        str(row["qualitative_fact_ref"]) for row in facts
    }

    combinations = [
        deepcopy(dict(row))
        for row in template["allowed_structured_claim_combinations"]
        if set(row["required_qualitative_fact_refs"]).issubset(
            available_qualitative_facts
        )
        and set(row["required_evidence_refs"]).issubset(available_evidence)
        and set(row["required_numeric_relation_refs"]).issubset(
            available_numeric_relations
        )
        and set(row["required_gap_refs"]).issubset(available_gaps)
    ]
    _require(
        combinations,
        "dynamic_truth_spine_no_claim_surface_authority_available",
    )

    gap_only_thesis_enabled = False
    if not any(
        "thesis_atom" in set(row["allowed_atom_fields"])
        for row in combinations
    ):
        gap_relation = next(
            (
                row
                for row in combinations
                if row["causal_bridge_authority"] == "bridge_unavailable"
                and "not_inferable"
                in set(row["allowed_inference_authorities"])
                and "insufficient_evidence"
                in set(row["allowed_judgment_statuses"])
            ),
            None,
        )
        _require(
            gap_relation is not None,
            "dynamic_truth_spine_no_safe_thesis_surface_available",
        )
        gap_relation["allowed_atom_fields"] = [
            *gap_relation["allowed_atom_fields"],
            "thesis_atom",
        ]
        gap_relation["allowed_inference_authorities"] = ["not_inferable"]
        gap_relation["allowed_judgment_statuses"] = [
            "insufficient_evidence"
        ]
        gap_only_thesis_enabled = True

    body = {
        "schema_version": (
            CLAIM_SURFACE_DYNAMIC_RELATION_ALIAS_POLICY_SCHEMA_VERSION
        ),
        "status": "provider_neutral_dynamic_claim_relation_alias_authority",
        "qualified_scope": {
            "case_key": case_key,
            "cell_id": cell_id,
            "base_claim_authority_input_digest": claim_authority_input[
                "research_input_digest"
            ],
            "base_claim_authority_judgment_schema_version": (
                "fin_ia_current_research_judgment_payload_v1_3"
            ),
        },
        "allowed_claim_subjects": deepcopy(
            template["allowed_claim_subjects"]
        ),
        "allowed_claim_outcomes": deepcopy(
            template["allowed_claim_outcomes"]
        ),
        "allowed_claim_relations": deepcopy(
            template["allowed_claim_relations"]
        ),
        "allowed_attribution_bases": deepcopy(
            template["allowed_attribution_bases"]
        ),
        "source_bound_qualitative_facts": facts,
        "allowed_structured_claim_combinations": combinations,
        "narrative_conflict_guard": deepcopy(
            template["narrative_conflict_guard"]
        ),
        "authority": {
            **deepcopy(template["authority"]),
            "dynamic_request_scoped_reselection": True,
            "candidate_promotion_forbidden": True,
            "gap_only_thesis_may_abstain": True,
        },
    }
    _require(
        gap_only_thesis_enabled
        or any(
            "thesis_atom" in set(row["allowed_atom_fields"])
            for row in combinations
        ),
        "dynamic_truth_spine_thesis_surface_invalid",
    )
    return body


__all__ = [
    "DYNAMIC_EVIDENCE_RESPONSE_SET_SCHEMA_VERSION",
    "DYNAMIC_REVIEWED_PACK_VIEW_SCHEMA_VERSION",
    "DYNAMIC_RESEARCH_INPUT_SCHEMA_VERSION",
    "DYNAMIC_TRUTH_SPINE_POLICY_SCHEMA_VERSION",
    "DYNAMIC_TRUTH_SPINE_POLICY_SUCCESSOR_SCHEMA_VERSION",
    "EVIDENCE_RESPONSE_SCHEMA_VERSION",
    "DynamicTruthSpineError",
    "compile_dynamic_evidence_responses",
    "compile_dynamic_reviewed_pack_view",
    "bind_dynamic_evidence_responses_to_research_input",
    "compile_dynamic_claim_authority_policy",
    "compile_dynamic_claim_surface_policy",
    "load_dynamic_truth_spine_policy",
]
