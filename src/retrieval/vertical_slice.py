from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

from retrieval.artifact_spine import (
    ArtifactEnvelope,
    ArtifactScope,
    ArtifactSpinePolicy,
    build_artifact_envelope,
    canonical_json_digest,
    validate_artifact_chain,
    validate_inline_payload_refs,
)


VS1_RESULT_SCHEMA_VERSION = "fin_ia_s1_vs1_vertical_slice_result_v1_0"
VS1_RESULT_RESOURCE_ID = "application.result.current_s1_vs1_vertical_slice"
VS1_DECISION_LEDGER_SCHEMA_VERSION = (
    "fin_ia_s1_candidate_decision_ledger_v1_0"
)
VS1_COVERAGE_SCHEMA_VERSION = "fin_ia_s1_evidence_coverage_state_v1_0"
VS1_READINESS_SCHEMA_VERSION = "fin_ia_s1_evidence_pack_readiness_v1_0"
VS1_WORKBENCH_SCHEMA_VERSION = "fin_ia_s1_workbench_lineage_projection_v1_0"

_DIGEST_FIELDS = {
    "candidate_decision_ledger_digest",
    "coverage_state_digest",
    "readiness_digest",
    "workbench_projection_digest",
    "frozen_consumer_probe_digest",
    "result_digest",
}
_REQUIRED_ARTIFACT_TYPES = {
    "source_route_decision",
    "raw_source_capture",
    "parsed_document",
    "financial_evidence_object",
    "object_manifest",
    "index_snapshot",
    "evidence_request",
    "query_facet_plan",
    "candidate_set",
    "candidate_ranking",
    "candidate_decision",
    "evidence_coverage_state",
    "evidence_pack_readiness",
    "workbench_projection",
    "frozen_consumer_probe",
}


class S1VerticalSliceError(ValueError):
    """A VS1 artifact or product seam lost financial-research authority."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S1VerticalSliceError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _case_scope(case_key: str, research_as_of: str) -> ArtifactScope:
    return ArtifactScope(
        binding_state="case_bound",
        case_key=case_key,
        subject_ticker=case_key,
        research_as_of=research_as_of,
    )


def _source_scope(
    *,
    case_key: str | None,
    source_owner_ticker: str | None,
    research_as_of: str,
) -> ArtifactScope:
    if case_key and source_owner_ticker:
        return ArtifactScope(
            binding_state="case_and_source_bound",
            case_key=case_key,
            subject_ticker=case_key,
            source_owner_ticker=source_owner_ticker,
            research_as_of=research_as_of,
        )
    if source_owner_ticker:
        return ArtifactScope(
            binding_state="source_only",
            source_owner_ticker=source_owner_ticker,
            research_as_of=research_as_of,
        )
    return ArtifactScope(
        binding_state="aggregate",
        research_as_of=research_as_of,
    )


def _candidate_rows(request_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for raw_lane in request_result.get("lanes") or ():
        lane = _mapping(raw_lane, "vs1_request_lane_invalid")
        _require(
            lane.get("candidate_state") == "candidate_not_evidence",
            "vs1_candidate_state_invalid",
        )
        for raw in lane.get("candidates") or ():
            candidate = deepcopy(dict(_mapping(raw, "vs1_candidate_invalid")))
            source_id = str(candidate.get("source_record_id") or "")
            _require(source_id, "vs1_candidate_source_id_missing")
            rows.setdefault(source_id, candidate)
    return list(rows.values())


def _request_slots(request_result: Mapping[str, Any]) -> set[str]:
    plan = _mapping(request_result.get("query_plan"), "vs1_query_plan_missing")
    lanes = plan.get("lanes")
    _require(isinstance(lanes, list) and lanes, "vs1_query_lanes_missing")
    slots = {
        str(_mapping(row, "vs1_query_lane_invalid").get("slot_id") or "")
        for row in lanes
    }
    _require("" not in slots, "vs1_query_slot_missing")
    return slots


def _item_gate_reason(
    item: Mapping[str, Any],
    source: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
    request_slots: set[str],
) -> str | None:
    case_key = str(request.get("case_key") or "").upper()
    if str(item.get("case_key") or "").upper() != case_key:
        return "cross_case_reviewed_item"
    if item.get("writer_citable") is not True:
        return "reviewed_item_not_writer_citable"
    targets = {str(value).upper() for value in request.get("target_entities") or ()}
    if str(source.get("evidence_owner_ticker") or "").upper() not in targets:
        return "reviewed_item_owner_outside_request"
    if str(source.get("source_type") or "") not in set(
        request.get("acceptable_sources") or ()
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
        raise S1VerticalSliceError("vs1_reviewed_item_date_invalid") from exc
    period = _mapping(request.get("period"), "vs1_request_period_invalid")
    period_end = str(
        item.get("source_reporting_period_end")
        or source.get("period_end")
        or ""
    )
    start = str(period.get("start_date") or "")
    end = str(period.get("end_date") or "")
    if start and (not period_end or period_end < start):
        return "reviewed_item_before_request_period"
    if end and (not period_end or period_end > end):
        return "reviewed_item_after_request_period"
    item_slots = {
        str(_mapping(row, "vs1_slot_binding_invalid").get("slot_id") or "")
        for row in item.get("slot_bindings") or ()
    }
    if not item_slots.intersection(request_slots):
        return "reviewed_item_outside_request_slot"
    return None


def _candidate_gate_reason(
    candidate: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
) -> str | None:
    case_key = str(request.get("case_key") or "").upper()
    if str(candidate.get("subject_ticker") or "").upper() != case_key:
        return "candidate_subject_case_mismatch"
    targets = {str(value).upper() for value in request.get("target_entities") or ()}
    if str(candidate.get("evidence_owner_ticker") or "").upper() not in targets:
        return "candidate_owner_outside_request"
    if str(candidate.get("source_type") or "") not in set(
        request.get("acceptable_sources") or ()
    ):
        return "candidate_source_type_outside_request"
    publication_date = str(candidate.get("publication_date") or "")
    research_as_of = str(request.get("research_as_of") or "")
    try:
        if not publication_date or date.fromisoformat(publication_date) > date.fromisoformat(
            research_as_of
        ):
            return "candidate_after_research_as_of"
    except ValueError as exc:
        raise S1VerticalSliceError("vs1_candidate_date_invalid") from exc
    return None


def compile_candidate_decision_ledger(
    *,
    request_result: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    request = _mapping(request_result.get("request"), "vs1_request_missing")
    case_key = str(request.get("case_key") or "").upper()
    _require(
        case_key
        and str(evidence_pack.get("case_key") or "").upper() == case_key,
        "vs1_pack_request_case_mismatch",
    )
    request_slots = _request_slots(request_result)
    materials = {
        str(row.get("material_ref") or ""): dict(row)
        for row in evidence_pack.get("source_materials") or ()
        if isinstance(row, Mapping)
    }
    reviewed_by_source: dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {}
    for raw in evidence_pack.get("evidence_items") or ():
        item = _mapping(raw, "vs1_reviewed_item_invalid")
        source_id = str(item.get("source_record_id") or "")
        projected_source = item.get("source")
        material = (
            dict(projected_source)
            if isinstance(projected_source, Mapping)
            else materials.get(str(item.get("source_material_ref") or ""))
        )
        _require(source_id and material is not None, "vs1_reviewed_source_binding_missing")
        reviewed_by_source.setdefault(source_id, []).append((item, material))

    decisions: list[dict[str, Any]] = []
    accepted_digests: set[str] = set()
    for rank, candidate in enumerate(_candidate_rows(request_result), start=1):
        source_id = str(candidate["source_record_id"])
        lineage = {
            source_id,
            *(str(value) for value in candidate.get("lineage_source_record_ids") or ()),
        }
        matches = [
            pair
            for lineage_id in lineage
            for pair in reviewed_by_source.get(lineage_id, ())
        ]
        candidate_ref = "CAND::" + canonical_json_digest(
            {
                "request_id": request.get("request_id"),
                "source_record_id": source_id,
                "compiled_object_id": candidate.get("compiled_object_id"),
            }
        )[:24].upper()
        accepted: list[str] = []
        candidate_gate_reason = _candidate_gate_reason(
            candidate,
            request=request,
        )
        rejected_reasons: list[str] = (
            [candidate_gate_reason] if candidate_gate_reason is not None else []
        )
        capture_bound = False
        for item, source in matches if candidate_gate_reason is None else ():
            reason = _item_gate_reason(
                item,
                source,
                request=request,
                request_slots=request_slots,
            )
            if reason is not None:
                rejected_reasons.append(reason)
                continue
            digest = str(item.get("evidence_item_digest") or "")
            _require(digest, "vs1_reviewed_evidence_digest_missing")
            accepted.append(digest)
            accepted_digests.add(digest)
            capture_bound = capture_bound or bool(source.get("raw_capture_sha256"))

        if accepted:
            state = "accepted"
            reason_codes = [
                "exact_reviewed_pack_lineage_match",
                "case_owner_source_period_slot_gate_passed",
            ]
            authority = (
                "capture_bound_reviewed_evidence_gate_reused"
                if capture_bound
                else "immutable_reviewed_pack_reselection"
            )
        elif matches or candidate_gate_reason is not None:
            state = "rejected"
            reason_codes = sorted(set(rejected_reasons))
            authority = "reviewed_binding_gate_rejection"
        else:
            state = "needs_review"
            reason_codes = ["candidate_not_present_in_reviewed_pack"]
            authority = "candidate_only_no_evidence_authority"
        decision_body = {
            "candidate_ref": candidate_ref,
            "source_record_id": source_id,
            "rank": rank,
            "score": candidate.get("final_score"),
            "evidence_owner_ticker": candidate.get("evidence_owner_ticker"),
            "source_type": candidate.get("source_type"),
            "publication_date": candidate.get("publication_date"),
            "decision_state": state,
            "reason_codes": reason_codes,
            "decision_authority": authority,
            "accepted_evidence_item_digests": sorted(set(accepted)),
            "model_decision_used": False,
            "candidate_text_promoted": False,
        }
        decisions.append(
            {
                **decision_body,
                "decision_digest": canonical_json_digest(decision_body),
            }
        )
    counts = Counter(row["decision_state"] for row in decisions)
    body = {
        "schema_version": VS1_DECISION_LEDGER_SCHEMA_VERSION,
        "status": "persistent_candidate_decisions_materialized",
        "recorded_at": recorded_at,
        "case_key": case_key,
        "research_as_of": request.get("research_as_of"),
        "request_id": request.get("request_id"),
        "request_digest": request_result.get("request_digest"),
        "request_slot_ids": sorted(request_slots),
        "candidate_count": len(decisions),
        "decision_counts": {
            state: counts.get(state, 0)
            for state in ("accepted", "rejected", "unjudged", "needs_review")
        },
        "accepted_evidence_item_digests": sorted(accepted_digests),
        "decisions": decisions,
        "authority": {
            "candidate_is_not_evidence": True,
            "rank_never_grants_evidence_authority": True,
            "reviewed_binding_or_separate_capture_gate_required": True,
            "numeric_authority_remains_s2": True,
        },
    }
    return {
        **body,
        "candidate_decision_ledger_digest": canonical_json_digest(body),
    }


def compile_evidence_coverage_state(
    *,
    request_result: Mapping[str, Any],
    decision_ledger: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    request = _mapping(request_result.get("request"), "vs1_request_missing")
    request_slots = _request_slots(request_result)
    relevant_items = [
        dict(row)
        for row in evidence_pack.get("evidence_items") or ()
        if any(
            str(binding.get("slot_id") or "") in request_slots
            for binding in row.get("slot_bindings") or ()
            if isinstance(binding, Mapping)
        )
    ]
    relevant_digests = {
        str(row.get("evidence_item_digest") or "") for row in relevant_items
    }
    accepted = set(decision_ledger.get("accepted_evidence_item_digests") or ())
    _require(accepted <= relevant_digests, "vs1_accepted_evidence_scope_drift")
    gaps = [
        deepcopy(dict(row))
        for row in evidence_pack.get("residual_gaps") or ()
        if str(row.get("slot_id") or "") in request_slots
    ]
    gap_receipts = []
    for gap in gaps:
        receipt_body = {
            "gap_id": str(gap.get("gap_id") or ""),
            "gap_code": str(gap.get("gap_code") or ""),
            "owning_stage": "S1",
            "classification": "declared_pack_gap_not_public_information_absence",
            "eligible_as_true_public_information_gap": False,
            "checks": {
                "local_object_and_index_checked": True,
                "request_scoped_retrieval_executed": True,
                "candidate_decisions_materialized": True,
                "official_supplement_route_executed_for_this_gap": False,
                "external_supplement_route_executed_for_this_gap": False,
                "required_route_budget_proven_sufficient": False,
            },
            "disposition": "supplement_route_not_yet_executed",
            "last_checked_at": recorded_at,
        }
        gap_receipts.append(
            {**receipt_body, "receipt_digest": canonical_json_digest(receipt_body)}
        )
    decision_counts = _mapping(
        decision_ledger.get("decision_counts"), "vs1_decision_counts_missing"
    )
    state = (
        "bounded_evidence_with_unresolved_gaps"
        if accepted and gaps
        else "evidence_available"
        if accepted
        else "insufficient_evidence"
    )
    body = {
        "schema_version": VS1_COVERAGE_SCHEMA_VERSION,
        "status": "proposition_level_coverage_materialized",
        "recorded_at": recorded_at,
        "case_key": request.get("case_key"),
        "research_as_of": request.get("research_as_of"),
        "proposition_id": "PROP::" + canonical_json_digest(
            {
                "request_id": request.get("request_id"),
                "slot_ids": sorted(request_slots),
                "metric_intents": request.get("metric_intents") or [],
                "product_intents": request.get("product_intents") or [],
            }
        )[:24].upper(),
        "research_question": request.get("stop_condition"),
        "request_id": request.get("request_id"),
        "slot_ids": sorted(request_slots),
        "coverage_state": state,
        "accepted_evidence_item_digests": sorted(accepted),
        "reviewed_evidence_not_recalled_digests": sorted(
            relevant_digests - accepted
        ),
        "candidate_decision_counts": deepcopy(dict(decision_counts)),
        "gap_eligibility_receipts": gap_receipts,
        "known": [
            "Current reviewed issuer evidence supports a bounded pricing/mix and profitability assessment.",
            "Accepted evidence remains non-causal unless separately authorized.",
        ],
        "unknown": [str(row.get("business_reason_zh") or "") for row in gaps],
        "why_unknown": [
            "The current local route and reviewed Pack do not provide the missing formula inputs.",
            "Official and external supplement routes have not yet been executed for these gaps.",
        ] if gaps else [],
    }
    return {**body, "coverage_state_digest": canonical_json_digest(body)}


def compile_evidence_pack_readiness(
    *,
    coverage: Mapping[str, Any],
    decision_ledger: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
    pack_artifact_digest: str,
    recorded_at: str,
) -> dict[str, Any]:
    decision_counts = _mapping(
        decision_ledger.get("decision_counts"), "vs1_decision_counts_missing"
    )
    decided = sum(int(value) for value in decision_counts.values())
    candidate_count = int(decision_ledger.get("candidate_count") or 0)
    accepted_count = len(coverage.get("accepted_evidence_item_digests") or ())
    _require(decided == candidate_count, "vs1_candidate_decision_ledger_incomplete")
    body = {
        "schema_version": VS1_READINESS_SCHEMA_VERSION,
        "status": "task_relative_evidence_pack_readiness_materialized",
        "recorded_at": recorded_at,
        "case_key": coverage.get("case_key"),
        "research_as_of": coverage.get("research_as_of"),
        "proposition_id": coverage.get("proposition_id"),
        "readiness_state": (
            "ready_for_bounded_research_not_complete_conclusion"
            if accepted_count
            else "not_ready_no_accepted_evidence"
        ),
        "pack_binding": {
            "case_key": evidence_pack.get("case_key"),
            "artifact_digest": pack_artifact_digest,
            "pack_payload_digest": evidence_pack.get("pack_payload_digest"),
        },
        "checks": {
            "all_retrieved_candidates_have_persistent_decisions": True,
            "accepted_evidence_is_writer_citable": accepted_count > 0,
            "capture_bound_promotion_lineage_visible": any(
                row.get("decision_authority")
                == "capture_bound_reviewed_evidence_gate_reused"
                for row in decision_ledger.get("decisions") or ()
            ),
            "false_public_gap_prevented": all(
                receipt.get("eligible_as_true_public_information_gap") is False
                for receipt in coverage.get("gap_eligibility_receipts") or ()
            ),
            "complete_product_conclusion_ready": False,
            "S1_qualified_stable": False,
        },
        "accepted_evidence_count": accepted_count,
        "unresolved_gap_count": len(coverage.get("gap_eligibility_receipts") or ()),
        "known_boundary": (
            "VS1 proves one current digital-native DELL vertical through the shared "
            "artifact spine. It permits bounded research on this proposition only; "
            "it does not qualify S1, close unexecuted supplement routes or authorize "
            "a complete financial conclusion."
        ),
    }
    return {**body, "readiness_digest": canonical_json_digest(body)}


def build_vs1_artifact_chain(
    *,
    policy: ArtifactSpinePolicy,
    source_manifest: Mapping[str, Any],
    source_results: Sequence[Mapping[str, Any]],
    source_payload_bindings: Mapping[str, Mapping[str, Any]],
    object_manifest_ref: str,
    object_manifest_sha256: str,
    index_snapshot_ref: str,
    index_snapshot_sha256: str,
    request_result: Mapping[str, Any],
    decision_ledger: Mapping[str, Any],
    coverage: Mapping[str, Any],
    readiness: Mapping[str, Any],
    workbench_projection: Mapping[str, Any],
    frozen_consumer_probe: Mapping[str, Any],
    inline_payload_ref_prefix: str,
) -> tuple[ArtifactEnvelope, ...]:
    request = _mapping(request_result.get("request"), "vs1_request_missing")
    case_key = str(request.get("case_key") or "").upper()
    research_as_of = str(request.get("research_as_of") or "")
    sources_by_id = {
        str(row.get("source_id") or ""): row
        for row in source_manifest.get("sources") or ()
        if isinstance(row, Mapping)
    }
    source_result_by_id = {
        str(row.get("source_id") or ""): row for row in source_results
    }
    financial_objects: list[ArtifactEnvelope] = []
    envelopes: list[ArtifactEnvelope] = []
    for source_id in sorted(source_result_by_id):
        source = _mapping(sources_by_id.get(source_id), "vs1_manifest_source_missing")
        result = _mapping(source_result_by_id[source_id], "vs1_source_result_invalid")
        binding = _mapping(
            source_payload_bindings.get(source_id), "vs1_source_payload_binding_missing"
        )
        owner = str(source.get("ticker") or "").upper() or None
        scope = _source_scope(
            case_key=case_key if owner == case_key else None,
            source_owner_ticker=owner,
            research_as_of=research_as_of,
        )
        route_payload = {
            "source_id": source_id,
            "input_kind": source.get("input_kind"),
            "source_url": source.get("source_url"),
            "route_id": source.get("route_id"),
            "expected_sha256": source.get("expected_sha256"),
            "required": source.get("required"),
        }
        route = build_artifact_envelope(
            artifact_type="source_route_decision",
            artifact_version="v1.0",
            producer_id="current_source_object_manifest_adapter",
            payload_schema_version="fin_ia_vs1_source_route_receipt_v1_0",
            payload_ref=f"{inline_payload_ref_prefix}/source_routes/{source_id}",
            payload_sha256=canonical_json_digest(route_payload),
            lifecycle_state="materialized",
            scope=scope,
        )
        capture = build_artifact_envelope(
            artifact_type="raw_source_capture",
            artifact_version="v1.0",
            producer_id="existing_capture_first_source_adapter",
            payload_schema_version=str(binding["capture_schema_version"]),
            payload_ref=str(binding["capture_ref"]),
            payload_sha256=str(binding["capture_sha256"]),
            lifecycle_state="materialized",
            scope=scope,
            parent_refs=(route.as_ref("bound_to"),),
        )
        parsed = build_artifact_envelope(
            artifact_type="parsed_document",
            artifact_version="v1.0",
            producer_id="existing_parser_thin_adapter",
            payload_schema_version=str(binding["parsed_schema_version"]),
            payload_ref=str(binding["parsed_ref"]),
            payload_sha256=str(binding["parsed_sha256"]),
            lifecycle_state="materialized",
            scope=scope,
            parent_refs=(capture.as_ref("derived_from"),),
        )
        object_payload = {
            "source_id": source_id,
            "document_parents_added": result.get("document_parents_added"),
            "retrieval_children_added": result.get("retrieval_children_added"),
            "invalid_records_excluded": result.get("invalid_records_excluded"),
            "source_sha256": result.get("source_sha256"),
        }
        financial_object = build_artifact_envelope(
            artifact_type="financial_evidence_object",
            artifact_version="v1.0",
            producer_id="current_financial_object_store_adapter",
            payload_schema_version="fin_ia_vs1_financial_object_receipt_v1_0",
            payload_ref=f"{inline_payload_ref_prefix}/financial_objects/{source_id}",
            payload_sha256=canonical_json_digest(object_payload),
            lifecycle_state="materialized",
            scope=scope,
            parent_refs=(parsed.as_ref("derived_from"),),
        )
        envelopes.extend((route, capture, parsed, financial_object))
        financial_objects.append(financial_object)

    aggregate_scope = ArtifactScope(
        binding_state="aggregate", research_as_of=research_as_of
    )
    manifest = build_artifact_envelope(
        artifact_type="object_manifest",
        artifact_version="v1.0",
        producer_id="current_financial_object_store_adapter",
        payload_schema_version=str(source_manifest.get("schema_version") or "unknown"),
        payload_ref=object_manifest_ref,
        payload_sha256=object_manifest_sha256,
        lifecycle_state="materialized",
        scope=aggregate_scope,
        parent_refs=tuple(row.as_ref("consumes") for row in financial_objects),
    )
    index = build_artifact_envelope(
        artifact_type="index_snapshot",
        artifact_version="v1.0",
        producer_id="current_retrieval_snapshot_adapter",
        payload_schema_version="fin_ia_current_retrieval_snapshot_v1_0",
        payload_ref=index_snapshot_ref,
        payload_sha256=index_snapshot_sha256,
        lifecycle_state="materialized",
        scope=aggregate_scope,
        parent_refs=(manifest.as_ref("derived_from"),),
    )
    case_scope = _case_scope(case_key, research_as_of)
    request_payload = deepcopy(dict(request))
    request_envelope = build_artifact_envelope(
        artifact_type="evidence_request",
        artifact_version="v1.0",
        producer_id="research_retrieval_service",
        payload_schema_version=str(request.get("schema_version") or "unknown"),
        payload_ref=f"{inline_payload_ref_prefix}/evidence_request",
        payload_sha256=canonical_json_digest(request_payload),
        lifecycle_state="materialized",
        scope=case_scope,
    )
    query_plan = _mapping(request_result.get("query_plan"), "vs1_query_plan_missing")
    query_envelope = build_artifact_envelope(
        artifact_type="query_facet_plan",
        artifact_version="v1.0",
        producer_id="query_facet_plan_compiler",
        payload_schema_version=str(query_plan.get("schema_version") or "unknown"),
        payload_ref=f"{inline_payload_ref_prefix}/query_facet_plan",
        payload_sha256=canonical_json_digest(query_plan),
        lifecycle_state="materialized",
        scope=case_scope,
        parent_refs=(request_envelope.as_ref("derived_from"),),
    )
    candidates = _candidate_rows(request_result)
    candidate_set_payload = {
        "candidate_state": "candidate_not_evidence",
        "request_id": request.get("request_id"),
        "source_record_ids": [row["source_record_id"] for row in candidates],
    }
    candidate_set = build_artifact_envelope(
        artifact_type="candidate_set",
        artifact_version="v1.0",
        producer_id="research_retrieval_service",
        payload_schema_version="fin_ia_vs1_candidate_set_v1_0",
        payload_ref=f"{inline_payload_ref_prefix}/candidate_set",
        payload_sha256=canonical_json_digest(candidate_set_payload),
        lifecycle_state="materialized",
        scope=case_scope,
        parent_refs=(
            query_envelope.as_ref("derived_from"),
            index.as_ref("consumes"),
        ),
    )
    ranking_payload = {
        "ranking_contract": "current_typed_financial_candidate_order",
        "candidate_state": "candidate_not_evidence",
        "rows": [
            {
                "rank": rank,
                "source_record_id": row["source_record_id"],
                "score": row.get("final_score"),
            }
            for rank, row in enumerate(candidates, start=1)
        ],
    }
    ranking = build_artifact_envelope(
        artifact_type="candidate_ranking",
        artifact_version="v1.0",
        producer_id="financial_candidate_ranking_adapter",
        payload_schema_version="fin_ia_vs1_candidate_ranking_v1_0",
        payload_ref=f"{inline_payload_ref_prefix}/candidate_ranking",
        payload_sha256=canonical_json_digest(ranking_payload),
        lifecycle_state="materialized",
        scope=case_scope,
        parent_refs=(candidate_set.as_ref("derived_from"),),
    )
    decision = build_artifact_envelope(
        artifact_type="candidate_decision",
        artifact_version="v1.0",
        producer_id="s1_candidate_decision_ledger",
        payload_schema_version=VS1_DECISION_LEDGER_SCHEMA_VERSION,
        payload_ref=f"{inline_payload_ref_prefix}/candidate_decision_ledger",
        payload_sha256=canonical_json_digest(decision_ledger),
        lifecycle_state="materialized",
        scope=case_scope,
        parent_refs=(ranking.as_ref("consumes"),),
    )
    coverage_envelope = build_artifact_envelope(
        artifact_type="evidence_coverage_state",
        artifact_version="v1.0",
        producer_id="s1_evidence_coverage_compiler",
        payload_schema_version=VS1_COVERAGE_SCHEMA_VERSION,
        payload_ref=f"{inline_payload_ref_prefix}/evidence_coverage_state",
        payload_sha256=canonical_json_digest(coverage),
        lifecycle_state="materialized",
        scope=case_scope,
        parent_refs=(
            request_envelope.as_ref("consumes"),
            decision.as_ref("consumes"),
        ),
    )
    readiness_envelope = build_artifact_envelope(
        artifact_type="evidence_pack_readiness",
        artifact_version="v1.0",
        producer_id="s1_evidence_pack_readiness_compiler",
        payload_schema_version=VS1_READINESS_SCHEMA_VERSION,
        payload_ref=f"{inline_payload_ref_prefix}/evidence_pack_readiness",
        payload_sha256=canonical_json_digest(readiness),
        lifecycle_state="materialized",
        scope=case_scope,
        parent_refs=(coverage_envelope.as_ref("derived_from"),),
    )
    workbench_envelope = build_artifact_envelope(
        artifact_type="workbench_projection",
        artifact_version="v1.0",
        producer_id="research_workbench_vs1_projection",
        payload_schema_version=VS1_WORKBENCH_SCHEMA_VERSION,
        payload_ref=f"{inline_payload_ref_prefix}/workbench_projection",
        payload_sha256=canonical_json_digest(workbench_projection),
        lifecycle_state="materialized",
        scope=case_scope,
        parent_refs=(readiness_envelope.as_ref("projects"),),
    )
    frozen_envelope = build_artifact_envelope(
        artifact_type="frozen_consumer_probe",
        artifact_version="v1.0",
        producer_id="vs1_frozen_consumer_probe",
        payload_schema_version="fin_ia_s1_frozen_consumer_probe_v1_0",
        payload_ref=f"{inline_payload_ref_prefix}/frozen_consumer_probe",
        payload_sha256=canonical_json_digest(frozen_consumer_probe),
        lifecycle_state="materialized",
        scope=case_scope,
        parent_refs=(readiness_envelope.as_ref("consumes"),),
    )
    envelopes.extend(
        (
            manifest,
            index,
            request_envelope,
            query_envelope,
            candidate_set,
            ranking,
            decision,
            coverage_envelope,
            readiness_envelope,
            workbench_envelope,
            frozen_envelope,
        )
    )
    validate_artifact_chain(envelopes, policy)
    return tuple(envelopes)


def compile_workbench_projection(
    *,
    decision_ledger: Mapping[str, Any],
    coverage: Mapping[str, Any],
    readiness: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    body = {
        "schema_version": VS1_WORKBENCH_SCHEMA_VERSION,
        "status": "canonical_s1_lineage_ready",
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
            "accepted_evidence_count": len(
                coverage.get("accepted_evidence_item_digests") or ()
            ),
            "reviewed_not_recalled_count": len(
                coverage.get("reviewed_evidence_not_recalled_digests") or ()
            ),
            "unresolved_gap_count": len(
                coverage.get("gap_eligibility_receipts") or ()
            ),
            "true_public_information_gap_count": sum(
                receipt.get("eligible_as_true_public_information_gap") is True
                for receipt in coverage.get("gap_eligibility_receipts") or ()
            ),
        },
        "decision_rows": [
            {
                key: deepcopy(row.get(key))
                for key in (
                    "candidate_ref",
                    "source_record_id",
                    "rank",
                    "evidence_owner_ticker",
                    "source_type",
                    "publication_date",
                    "decision_state",
                    "reason_codes",
                    "decision_authority",
                    "accepted_evidence_item_digests",
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
            "unexecuted_route_is_not_public_information_gap": True,
            "complete_product_conclusion_ready": False,
            "S1_qualified_stable": False,
        },
    }
    return {**body, "workbench_projection_digest": canonical_json_digest(body)}


def load_s1_vs1_vertical_slice_result(
    payload: Mapping[str, Any],
    *,
    policy: ArtifactSpinePolicy,
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    _require(
        value.get("schema_version") == VS1_RESULT_SCHEMA_VERSION,
        "vs1_result_schema_invalid",
    )
    _require(
        value.get("status") == "vs1_current_digital_native_vertical_integrated",
        "vs1_result_status_invalid",
    )
    envelopes = tuple(
        ArtifactEnvelope.model_validate(row) for row in value.get("envelopes") or ()
    )
    _require(envelopes, "vs1_result_envelopes_missing")
    _require(
        _REQUIRED_ARTIFACT_TYPES <= {row.artifact_type for row in envelopes},
        "vs1_result_artifact_coverage_missing",
    )
    validate_artifact_chain(envelopes, policy)
    validate_inline_payload_refs(
        value,
        envelopes,
        resource_id=VS1_RESULT_RESOURCE_ID,
    )
    cases = value.get("cases")
    _require(isinstance(cases, Mapping) and set(cases) == {"DELL"}, "vs1_result_case_scope_invalid")
    case = _mapping(cases["DELL"], "vs1_result_case_invalid")
    for field in _DIGEST_FIELDS - {"result_digest"}:
        if field in case:
            _require(
                str(case[field]) == canonical_json_digest(
                    {
                        key: val
                        for key, val in _mapping(
                            case[field.removesuffix("_digest")],
                            "vs1_result_payload_missing",
                        ).items()
                        if key != field
                    }
                ),
                f"vs1_result_payload_digest_invalid:{field}",
            )
    unsigned = {key: val for key, val in value.items() if key != "result_digest"}
    _require(
        value.get("result_digest") == canonical_json_digest(unsigned),
        "vs1_result_digest_invalid",
    )
    return value


def project_s1_vs1_case(
    payload: Mapping[str, Any],
    *,
    case_key: str,
) -> dict[str, Any] | None:
    case = (payload.get("cases") or {}).get(str(case_key).strip().upper())
    if not isinstance(case, Mapping):
        return None
    return deepcopy(dict(case["workbench_projection"]))


__all__ = [
    "S1VerticalSliceError",
    "VS1_COVERAGE_SCHEMA_VERSION",
    "VS1_DECISION_LEDGER_SCHEMA_VERSION",
    "VS1_READINESS_SCHEMA_VERSION",
    "VS1_RESULT_SCHEMA_VERSION",
    "VS1_RESULT_RESOURCE_ID",
    "VS1_WORKBENCH_SCHEMA_VERSION",
    "build_vs1_artifact_chain",
    "compile_candidate_decision_ledger",
    "compile_evidence_coverage_state",
    "compile_evidence_pack_readiness",
    "compile_workbench_projection",
    "load_s1_vs1_vertical_slice_result",
    "project_s1_vs1_case",
]
