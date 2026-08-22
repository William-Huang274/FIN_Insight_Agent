from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from retrieval.query_plan import canonical_digest


REVIEW_SUCCESSOR_PROGRAM_SCHEMA_VERSION = (
    "fin_ia_s1_requirement_review_successor_program_v1_0"
)
TASK_PACK_READINESS_SCHEMA_VERSION = "fin_ia_s1_s2_task_pack_readiness_v1_0"


class TaskPackReadinessError(ValueError):
    """Raised when a task readiness projection hides a source or authority gap."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise TaskPackReadinessError(code)


def _mapping(value: object, code: str) -> dict[str, Any]:
    _require(isinstance(value, Mapping), code)
    return deepcopy(dict(value))


def _rows(value: object, code: str) -> list[dict[str, Any]]:
    _require(isinstance(value, list), code)
    return [_mapping(row, code) for row in value]


def _strings(value: object, code: str, *, allow_empty: bool = False) -> list[str]:
    _require(isinstance(value, list), code)
    rows = [str(row).strip() for row in value]
    _require(
        (allow_empty or bool(rows))
        and all(rows)
        and len(rows) == len(set(rows)),
        code,
    )
    return rows


def _binding_key(binding: Mapping[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    return (
        str(binding.get("evidence_item_digest") or ""),
        str(binding.get("required_slot_id") or ""),
        tuple(sorted(str(value) for value in binding.get("required_facet_ids") or ())),
    )


def compile_requirement_review_successor(
    *,
    program: Mapping[str, Any],
    predecessor_review_plan: Mapping[str, Any],
    predecessor_polarity_plan: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    """Apply a reviewed, digest-bound delta without copying two large plans."""

    payload = deepcopy(dict(program))
    _require(
        payload.get("schema_version") == REVIEW_SUCCESSOR_PROGRAM_SCHEMA_VERSION
        and payload.get("status") == "approved_zero_call_review_successor",
        "task_pack_review_successor_header_invalid",
    )
    case_key = str(payload.get("case_key") or "").upper()
    target_pack_digest = str(evidence_pack.get("pack_payload_digest") or "")
    predecessor = _mapping(
        payload.get("predecessor_bindings"),
        "task_pack_predecessor_bindings_missing",
    )
    _require(
        case_key
        and str(evidence_pack.get("case_key") or "").upper() == case_key
        and target_pack_digest == payload.get("target_pack_payload_digest")
        and canonical_digest(dict(predecessor_review_plan))
        == predecessor.get("review_plan_digest")
        and canonical_digest(dict(predecessor_polarity_plan))
        == predecessor.get("polarity_plan_digest")
        and predecessor_review_plan.get("evidence_pack_payload_digest")
        == predecessor.get("pack_payload_digest")
        and predecessor_polarity_plan.get("evidence_pack_payload_digest")
        == predecessor.get("pack_payload_digest"),
        "task_pack_predecessor_binding_invalid",
    )
    pack_digests = {
        str(row.get("evidence_item_digest") or "")
        for row in evidence_pack.get("evidence_items") or ()
        if isinstance(row, Mapping)
    }
    expected_new = set(
        _strings(
            payload.get("expected_new_evidence_item_digests"),
            "task_pack_expected_new_evidence_invalid",
        )
    )
    _require(
        expected_new.issubset(pack_digests),
        "task_pack_expected_new_evidence_missing",
    )

    review = deepcopy(dict(predecessor_review_plan))
    polarity = deepcopy(dict(predecessor_polarity_plan))
    review["schema_version"] = str(payload.get("review_schema_version") or "")
    review["status"] = "provisional_project_audit_current_pack_successor"
    review["recorded_at"] = str(recorded_at)
    review["evidence_pack_payload_digest"] = target_pack_digest
    polarity["schema_version"] = str(payload.get("polarity_schema_version") or "")
    polarity["status"] = "provisional_project_audit_current_pack_successor"
    polarity["recorded_at"] = str(recorded_at)
    polarity["evidence_pack_payload_digest"] = target_pack_digest
    _require(
        review["schema_version"] and polarity["schema_version"],
        "task_pack_successor_schema_missing",
    )

    review_rows = {
        str(row.get("requirement_id") or ""): row
        for row in review.get("requirement_reviews") or ()
        if isinstance(row, dict)
    }
    polarity_rows = {
        str(row.get("requirement_id") or ""): row
        for row in polarity.get("requirement_polarity_reviews") or ()
        if isinstance(row, dict)
    }
    review_updates = _rows(
        payload.get("review_updates"), "task_pack_review_updates_invalid"
    )
    polarity_updates = _rows(
        payload.get("polarity_updates"), "task_pack_polarity_updates_invalid"
    )
    _require(
        len({str(row.get("requirement_id") or "") for row in review_updates})
        == len(review_updates)
        and len({str(row.get("requirement_id") or "") for row in polarity_updates})
        == len(polarity_updates),
        "task_pack_duplicate_requirement_update",
    )
    referenced_new: set[str] = set()
    allowed_review_fields = {
        "decision_state",
        "supported_product_ids",
        "unsupported_product_ids",
        "decision_reason_zh",
        "claim_boundary_zh",
    }
    for update in review_updates:
        requirement_id = str(update.get("requirement_id") or "")
        row = review_rows.get(requirement_id)
        _require(row is not None, "task_pack_review_update_requirement_unknown")
        set_fields = _mapping(
            update.get("set_fields") or {}, "task_pack_review_set_fields_invalid"
        )
        _require(
            set(set_fields).issubset(allowed_review_fields),
            "task_pack_review_set_field_forbidden",
        )
        row.update(deepcopy(set_fields))
        bindings = list(row.get("evidence_bindings") or ())
        keys = {_binding_key(binding) for binding in bindings}
        for binding in _rows(
            update.get("append_evidence_bindings") or [],
            "task_pack_review_binding_invalid",
        ):
            digest = str(binding.get("evidence_item_digest") or "")
            key = _binding_key(binding)
            _require(
                digest in pack_digests and key not in keys,
                "task_pack_review_binding_invalid",
            )
            bindings.append(binding)
            keys.add(key)
            if digest in expected_new:
                referenced_new.add(digest)
        row["evidence_bindings"] = bindings

    allowed_axis_fields = {
        "coverage_state",
        "evidence_polarity",
        "decision_reason_zh",
        "claim_boundary_zh",
        "scope_boundary_codes",
    }
    for update in polarity_updates:
        requirement_id = str(update.get("requirement_id") or "")
        row = polarity_rows.get(requirement_id)
        _require(row is not None, "task_pack_polarity_update_requirement_unknown")
        axes = {
            str(axis.get("product_id") or ""): axis
            for axis in row.get("product_axis_decisions") or ()
            if isinstance(axis, dict)
        }
        for axis_update in _rows(
            update.get("axis_updates"), "task_pack_axis_updates_invalid"
        ):
            product_id = str(axis_update.get("product_id") or "")
            axis = axes.get(product_id)
            _require(axis is not None, "task_pack_axis_update_product_unknown")
            set_fields = _mapping(
                axis_update.get("set_fields") or {},
                "task_pack_axis_set_fields_invalid",
            )
            _require(
                set(set_fields).issubset(allowed_axis_fields),
                "task_pack_axis_set_field_forbidden",
            )
            axis.update(deepcopy(set_fields))
            evidence = list(axis.get("evidence_item_digests") or ())
            for digest in _strings(
                axis_update.get("add_evidence_item_digests") or [],
                "task_pack_axis_evidence_invalid",
                allow_empty=True,
            ):
                _require(
                    digest in pack_digests and digest not in evidence,
                    "task_pack_axis_evidence_invalid",
                )
                evidence.append(digest)
                if digest in expected_new:
                    referenced_new.add(digest)
            axis["evidence_item_digests"] = evidence

    _require(
        referenced_new == expected_new,
        "task_pack_expected_new_evidence_not_exhaustively_reviewed",
    )
    review["known_boundary"] = str(payload.get("known_boundary") or "")
    review_digest = canonical_digest(review)
    polarity["predecessor_review_plan_digest"] = review_digest
    polarity["known_boundary"] = str(payload.get("known_boundary") or "")
    unsigned = {
        "schema_version": "fin_ia_s1_requirement_review_successor_v1_0",
        "status": "current_pack_review_successor_compiled",
        "case_key": case_key,
        "recorded_at": str(recorded_at),
        "target_pack_payload_digest": target_pack_digest,
        "expected_new_evidence_item_digests": sorted(expected_new),
        "review_plan": review,
        "review_plan_digest": review_digest,
        "polarity_plan": polarity,
        "polarity_plan_digest": canonical_digest(polarity),
        "authority": {
            "candidate_text_promoted": False,
            "new_evidence_created": False,
            "numeric_authority_granted": False,
            "public_information_gap_claimed": False,
            "owner_or_qualified_human_acceptance_claimed": False,
        },
    }
    return {**unsigned, "successor_digest": canonical_digest(unsigned)}


def compile_task_pack_readiness(
    *,
    program: Mapping[str, Any],
    integrated_readiness: Mapping[str, Any],
    quantitative_projection: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    """Qualify one dynamic task while keeping unresolved requests actionable."""

    payload = deepcopy(dict(program))
    _require(
        payload.get("schema_version") == TASK_PACK_READINESS_SCHEMA_VERSION
        and payload.get("status") == "approved_zero_call_task_pack_readiness",
        "task_pack_readiness_program_invalid",
    )
    case_key = str(payload.get("case_key") or "").upper()
    pack_digest = str(evidence_pack.get("pack_payload_digest") or "")
    _require(
        case_key
        and str(evidence_pack.get("case_key") or "").upper() == case_key
        and integrated_readiness.get("case_key") == case_key
        and integrated_readiness.get("evidence_pack_payload_digest") == pack_digest
        and quantitative_projection.get("case_key") == case_key
        and quantitative_projection.get("evidence_pack_binding", {}).get(
            "pack_payload_digest"
        )
        == pack_digest,
        "task_pack_readiness_binding_invalid",
    )
    request_rows = {
        str(row.get("request_id") or ""): row
        for row in integrated_readiness.get("requests") or ()
        if isinstance(row, Mapping)
    }
    required_consumable = set(
        _strings(
            payload.get("required_research_consumable_request_ids"),
            "task_pack_required_consumable_invalid",
        )
    )
    actionable_specs = _rows(
        payload.get("actionable_gap_requests"),
        "task_pack_actionable_gap_requests_invalid",
    )
    actionable_ids = {str(row.get("request_id") or "") for row in actionable_specs}
    _require(
        len(actionable_ids) == len(actionable_specs)
        and required_consumable.isdisjoint(actionable_ids)
        and required_consumable.union(actionable_ids) == set(request_rows),
        "task_pack_request_partition_invalid",
    )
    consumable_states = {"ready", "research_consumable_with_boundaries_or_s2_gaps"}
    _require(
        all(request_rows[request_id].get("state") in consumable_states for request_id in required_consumable),
        "task_pack_required_request_not_consumable",
    )
    gap_rows = {
        str(row.get("gap_id") or ""): row
        for row in quantitative_projection.get("typed_gap_dispositions") or ()
        if isinstance(row, Mapping)
    }
    actionable = []
    for spec in actionable_specs:
        request_id = str(spec.get("request_id") or "")
        gap_ids = _strings(
            spec.get("required_open_gap_ids"),
            "task_pack_actionable_gap_ids_invalid",
        )
        _require(
            request_rows[request_id].get("state") == "not_ready"
            and all(
                gap_id in gap_rows
                and gap_rows[gap_id].get("closed") is False
                and gap_rows[gap_id].get("public_information_gap_authority") is False
                for gap_id in gap_ids
            ),
            "task_pack_actionable_gap_not_preserved",
        )
        actionable.append(
            {
                "request_id": request_id,
                "required_open_gap_ids": gap_ids,
                "next_action": str(spec.get("next_action") or ""),
                "public_information_gap_authority": False,
            }
        )
    summary = _mapping(
        integrated_readiness.get("summary"), "task_pack_integrated_summary_missing"
    )
    expected = _mapping(
        payload.get("expected_integrated_summary"),
        "task_pack_expected_summary_missing",
    )
    _require(
        all(summary.get(key) == value for key, value in expected.items()),
        "task_pack_integrated_summary_unexpected",
    )
    quantitative_summary = _mapping(
        quantitative_projection.get("quantitative_authority", {}).get("summary"),
        "task_pack_quantitative_summary_missing",
    )
    checks = {
        "required_requests_research_consumable": True,
        "only_declared_requests_remain_not_ready": {
            request_id
            for request_id, row in request_rows.items()
            if row.get("state") == "not_ready"
        }
        == actionable_ids,
        "all_not_ready_requests_have_open_actionable_gaps": len(actionable)
        == len(actionable_specs),
        "task_quantitative_projection_ready": quantitative_projection.get(
            "task_readiness", {}
        ).get("ready")
        is True,
        "typed_conflicts_absent": int(
            quantitative_summary.get("typed_conflict_count") or 0
        )
        == 0,
        "all_pack_gaps_remain_explicit": len(gap_rows)
        == int(payload.get("expected_open_gap_count") or 0),
        "current_pack_evidence_count": len(evidence_pack.get("evidence_items") or ())
        == int(payload.get("expected_evidence_count") or 0),
        "no_public_information_gap_authority": all(
            row.get("public_information_gap_authority") is False
            for row in gap_rows.values()
        ),
    }
    _require(all(checks.values()), "task_pack_readiness_checks_failed")
    unsigned = {
        "schema_version": TASK_PACK_READINESS_SCHEMA_VERSION,
        "status": "ready_for_bounded_dynamic_single_unit_with_actionable_gaps",
        "case_key": case_key,
        "cell_id": str(payload.get("cell_id") or ""),
        "recorded_at": str(recorded_at),
        "evidence_pack_payload_digest": pack_digest,
        "integrated_readiness_digest": integrated_readiness.get("result_digest"),
        "task_quantitative_projection_digest": quantitative_projection.get(
            "task_quantitative_projection_digest"
        ),
        "required_research_consumable_request_ids": sorted(required_consumable),
        "actionable_gap_requests": actionable,
        "checks": checks,
        "authority": {
            "task_relative_readiness_only": True,
            "all_S1_requests_ready": False,
            "S1_qualified": False,
            "S2_stage_qualified": False,
            "dynamic_agent_executed": False,
            "public_information_gap_claimed": False,
        },
        "known_boundary": str(payload.get("task_known_boundary") or ""),
    }
    _require(unsigned["cell_id"], "task_pack_readiness_cell_missing")
    return {**unsigned, "task_pack_readiness_digest": canonical_digest(unsigned)}


__all__ = [
    "REVIEW_SUCCESSOR_PROGRAM_SCHEMA_VERSION",
    "TASK_PACK_READINESS_SCHEMA_VERSION",
    "TaskPackReadinessError",
    "compile_requirement_review_successor",
    "compile_task_pack_readiness",
]
