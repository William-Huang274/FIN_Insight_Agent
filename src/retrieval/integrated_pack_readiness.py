from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any, Mapping, Sequence

from .query_plan import canonical_digest


INTEGRATED_READINESS_SCHEMA_VERSION = (
    "fin_ia_s1_s2_integrated_requirement_readiness_v1_1"
)
REVIEW_STATES = frozenset(
    {"accepted", "accepted_bounded", "partial", "needs_review", "rejected"}
)
AXIS_COVERAGE_STATES = frozenset({"addressed", "unaddressed", "needs_review"})
EVIDENCE_POLARITIES = frozenset(
    {
        "supports",
        "contradicts",
        "mixed",
        "context_only",
        "boundary_only",
        "not_assessed",
    }
)


class IntegratedPackReadinessError(ValueError):
    """Raised when reviewed Evidence and NumericFact readiness cannot be bound."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise IntegratedPackReadinessError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _sequence(value: object, code: str) -> Sequence[Any]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes)), code
    )
    return value


def _as_date(value: object, code: str) -> date:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError as exc:
        raise IntegratedPackReadinessError(code) from exc


def _unique_strings(value: object, code: str) -> tuple[str, ...]:
    rows = tuple(str(row) for row in _sequence(value, code))
    _require(all(rows) and len(rows) == len(set(rows)), code)
    return rows


def _pack_items(evidence_pack: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for raw in evidence_pack.get("evidence_items") or ():
        row = _mapping(raw, "integrated_readiness_pack_item_invalid")
        digest = str(row.get("evidence_item_digest") or "")
        _require(digest and digest not in result, "integrated_readiness_pack_digest_invalid")
        result[digest] = row
    _require(result, "integrated_readiness_pack_empty")
    return result


def _anchor_digests(
    anchor_catalog: Mapping[str, Any], *, case_key: str
) -> frozenset[str]:
    result = {
        str(row.get("evidence_item_digest") or "")
        for row in anchor_catalog.get("entries") or ()
        if isinstance(row, Mapping)
        and str(row.get("case_key") or "").upper() == case_key
        and str(row.get("review_status") or "") == "reviewed_exact_source_surface"
    }
    result.discard("")
    return frozenset(result)


def _binding_gate(
    *,
    binding: Mapping[str, Any],
    pack_items: Mapping[str, Mapping[str, Any]],
    anchor_digests: frozenset[str],
    case_key: str,
    research_as_of: str,
) -> dict[str, Any]:
    digest = str(binding.get("evidence_item_digest") or "")
    item = pack_items.get(digest)
    _require(item is not None, f"integrated_readiness_evidence_not_in_pack:{digest}")
    _require(
        str(item.get("case_key") or "").upper() == case_key,
        "integrated_readiness_cross_case_evidence",
    )
    _require(
        item.get("writer_citable") is True,
        "integrated_readiness_evidence_not_writer_citable",
    )
    _require(
        str(item.get("disposition") or "").startswith("accepted_"),
        "integrated_readiness_evidence_not_accepted",
    )
    _require(
        _as_date(item.get("publication_date"), "integrated_readiness_date_invalid")
        <= _as_date(research_as_of, "integrated_readiness_as_of_invalid"),
        "integrated_readiness_future_evidence",
    )
    slot_id = str(binding.get("required_slot_id") or "")
    facet_ids = frozenset(
        _unique_strings(
            binding.get("required_facet_ids") or (),
            "integrated_readiness_required_facets_invalid",
        )
    )
    matching_slots = [
        row
        for row in item.get("slot_bindings") or ()
        if isinstance(row, Mapping) and str(row.get("slot_id") or "") == slot_id
    ]
    _require(matching_slots, "integrated_readiness_slot_binding_missing")
    available_facets = {
        str(facet)
        for row in matching_slots
        for facet in row.get("facet_ids") or ()
    }
    _require(
        facet_ids.issubset(available_facets),
        "integrated_readiness_facet_binding_missing",
    )
    require_anchor = binding.get("require_exact_anchor") is True
    _require(
        not require_anchor or digest in anchor_digests,
        "integrated_readiness_exact_anchor_missing",
    )
    return {
        "evidence_item_digest": digest,
        "source_record_id": item.get("source_record_id"),
        "target_id": item.get("target_id"),
        "object_type": item.get("object_type"),
        "required_slot_id": slot_id,
        "required_facet_ids": sorted(facet_ids),
        "exact_anchor_verified": digest in anchor_digests,
        "reviewed_pack_item_verified": True,
        "writer_citable": True,
        "numeric_authority": False,
    }


def _numeric_coverage(
    *, requirement: Mapping[str, Any], request_result: Mapping[str, Any]
) -> dict[str, Any]:
    coverage_mode = str(requirement.get("metric_coverage_mode") or "all_of")
    _require(
        coverage_mode in {"all_of", "any_of", "retrieval_context_only"},
        "integrated_readiness_metric_coverage_mode_invalid",
    )
    metric_ids = tuple(str(value) for value in requirement.get("metric_ids") or ())
    if not metric_ids:
        return {
            "state": "not_requested",
            "metric_coverage_mode": coverage_mode,
            "observed_state": "not_requested",
            "metric_count": 0,
            "resolved_metric_count": 0,
            "typed_gap_metric_count": 0,
            "metrics": [],
            "numeric_fact_authority": False,
        }
    typed_results: dict[str, list[Mapping[str, Any]]] = {}
    for raw in request_result.get("typed_fact_results") or ():
        row = _mapping(raw, "integrated_readiness_typed_result_invalid")
        typed_results.setdefault(str(row.get("metric_id") or ""), []).append(row)
    gap_receipts = {
        str(row.get("fact_request_id") or ""): row
        for row in request_result.get("typed_gaps") or ()
        if isinstance(row, Mapping)
    }
    metrics: list[dict[str, Any]] = []
    states: list[str] = []
    for metric_id in metric_ids:
        rows = typed_results.get(metric_id) or []
        _require(
            len(rows) == 1,
            f"integrated_readiness_typed_result_cardinality:{metric_id}",
        )
        row = rows[0]
        state = str(row.get("status") or "")
        facts = [
            _mapping(value, "integrated_readiness_numeric_fact_invalid")
            for value in row.get("facts") or ()
        ]
        if state == "resolved":
            _require(facts, "integrated_readiness_resolved_fact_missing")
            _require(
                all(value.get("numeric_fact_authority") is True for value in facts),
                "integrated_readiness_numeric_authority_missing",
            )
            metric_row = {
                "metric_id": metric_id,
                "state": "resolved",
                "numeric_fact_ids": sorted(
                    str(value.get("numeric_fact_id") or "") for value in facts
                ),
                "fact_count": len(facts),
                "numeric_fact_authority": True,
            }
        elif state == "typed_gap":
            fact_request_id = str(row.get("fact_request_id") or "")
            receipt = gap_receipts.get(fact_request_id)
            _require(
                receipt is not None, "integrated_readiness_typed_gap_receipt_missing"
            )
            metric_row = {
                "metric_id": metric_id,
                "state": "typed_gap",
                "gap_code": receipt.get("gap_code"),
                "owning_stage": receipt.get("owning_stage"),
                "disposition": receipt.get("disposition"),
                "fact_count": 0,
                "numeric_fact_authority": False,
            }
        elif state == "typed_conflict":
            metric_row = {
                "metric_id": metric_id,
                "state": "typed_conflict",
                "fact_count": len(facts),
                "numeric_fact_authority": False,
            }
        else:
            raise IntegratedPackReadinessError(
                f"integrated_readiness_typed_result_state_invalid:{state}"
            )
        states.append(metric_row["state"])
        metrics.append(metric_row)
    resolved = states.count("resolved")
    gaps = states.count("typed_gap")
    conflicts = states.count("typed_conflict")
    if resolved == len(states):
        observed_state = "resolved"
    elif conflicts:
        observed_state = "typed_conflict"
    elif gaps == len(states):
        observed_state = "typed_gap"
    else:
        observed_state = "partial"
    if coverage_mode == "retrieval_context_only":
        overall = "retrieval_context_only"
    elif coverage_mode == "any_of" and resolved:
        overall = "resolved_any_of"
    else:
        overall = observed_state
    return {
        "state": overall,
        "metric_coverage_mode": coverage_mode,
        "observed_state": observed_state,
        "metric_count": len(metric_ids),
        "resolved_metric_count": resolved,
        "typed_gap_metric_count": gaps,
        "metrics": metrics,
        "numeric_fact_authority": overall in {"resolved", "resolved_any_of"},
    }


def compile_integrated_requirement_readiness(
    *,
    product_projection: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
    review_plan: Mapping[str, Any],
    polarity_plan: Mapping[str, Any],
    anchor_catalog: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    """Combine reviewed Evidence and S2 NumericFacts without merging authority.

    The review plan may only map already accepted pack items to an exact material
    requirement. The polarity successor separately records whether each research
    topic is supported, contradicted, mixed, contextual, or only bounded. Neither
    input can promote candidate text, create a NumericFact, or turn a retrieval
    miss into a public-information gap.
    """

    case_key = str(product_projection.get("case_key") or "").upper()
    _require(case_key, "integrated_readiness_case_missing")
    _require(
        str(evidence_pack.get("case_key") or "").upper() == case_key,
        "integrated_readiness_pack_case_mismatch",
    )
    _require(
        str(review_plan.get("case_key") or "").upper() == case_key,
        "integrated_readiness_review_case_mismatch",
    )
    _require(
        str(polarity_plan.get("case_key") or "").upper() == case_key,
        "integrated_readiness_polarity_case_mismatch",
    )
    review_authority = _mapping(
        review_plan.get("review_authority"),
        "integrated_readiness_review_authority_missing",
    )
    for field in (
        "candidate_text_may_be_promoted",
        "new_evidence_may_be_created",
        "numeric_authority_may_be_granted",
        "public_information_gap_may_be_declared",
        "owner_or_qualified_human_acceptance_claimed",
    ):
        _require(
            review_authority.get(field) is False,
            f"integrated_readiness_review_authority_invalid:{field}",
        )
    polarity_authority = _mapping(
        polarity_plan.get("authority"),
        "integrated_readiness_polarity_authority_missing",
    )
    for field in (
        "candidate_text_may_be_promoted",
        "new_evidence_may_be_created",
        "numeric_authority_may_be_granted",
        "public_information_gap_may_be_declared",
        "owner_or_qualified_human_acceptance_claimed",
        "target_entities_may_be_expanded",
    ):
        _require(
            polarity_authority.get(field) is False,
            f"integrated_readiness_polarity_authority_invalid:{field}",
        )
    pack_digest = str(evidence_pack.get("pack_payload_digest") or "")
    _require(
        pack_digest
        and str(review_plan.get("evidence_pack_payload_digest") or "")
        == pack_digest,
        "integrated_readiness_pack_digest_mismatch",
    )
    _require(
        str(polarity_plan.get("evidence_pack_payload_digest") or "")
        == pack_digest,
        "integrated_readiness_polarity_pack_digest_mismatch",
    )
    research_plan_digest = str(product_projection.get("material_scope", {}).get(
        "research_plan_digest"
    ) or "")
    _require(
        research_plan_digest
        and str(review_plan.get("research_plan_digest") or "")
        == research_plan_digest,
        "integrated_readiness_research_plan_digest_mismatch",
    )
    _require(
        str(polarity_plan.get("research_plan_digest") or "")
        == research_plan_digest,
        "integrated_readiness_polarity_research_plan_digest_mismatch",
    )
    scope_compilation = _mapping(
        _mapping(
            product_projection.get("material_scope"),
            "integrated_readiness_material_scope_missing",
        ).get("scope_compilation"),
        "integrated_readiness_scope_compilation_missing",
    )
    _require(
        str(review_plan.get("scope_compilation_digest") or "")
        == str(scope_compilation.get("compilation_digest") or ""),
        "integrated_readiness_scope_digest_mismatch",
    )
    _require(
        str(polarity_plan.get("scope_compilation_digest") or "")
        == str(scope_compilation.get("compilation_digest") or ""),
        "integrated_readiness_polarity_scope_digest_mismatch",
    )
    review_plan_digest = canonical_digest(dict(review_plan))
    _require(
        str(polarity_plan.get("predecessor_review_plan_digest") or "")
        == review_plan_digest,
        "integrated_readiness_polarity_predecessor_digest_mismatch",
    )
    pack_items = _pack_items(evidence_pack)
    anchor_pack_bindings = _mapping(
        anchor_catalog.get("case_pack_bindings"),
        "integrated_readiness_anchor_pack_bindings_missing",
    )
    anchor_case_binding = _mapping(
        anchor_pack_bindings.get(case_key),
        "integrated_readiness_anchor_case_binding_missing",
    )
    _require(
        str(anchor_case_binding.get("pack_payload_digest") or "") == pack_digest,
        "integrated_readiness_anchor_pack_digest_mismatch",
    )
    anchors = _anchor_digests(anchor_catalog, case_key=case_key)
    request_results: dict[str, Mapping[str, Any]] = {}
    for raw in product_projection.get("request_results") or ():
        row = _mapping(raw, "integrated_readiness_request_result_invalid")
        request_id = str(
            _mapping(
                row.get("request"), "integrated_readiness_request_missing"
            ).get("request_id")
            or ""
        )
        _require(
            request_id and request_id not in request_results,
            "integrated_readiness_request_id_invalid",
        )
        request_results[request_id] = row
    requirements: dict[str, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    for request_id, request_result in request_results.items():
        material = _mapping(
            _mapping(
                request_result.get("hybrid_object_retrieval"),
                "integrated_readiness_hybrid_result_missing",
            ).get("material_evidence"),
            "integrated_readiness_material_evidence_missing",
        )
        plan = _mapping(
            material.get("requirement_plan"),
            "integrated_readiness_requirement_plan_missing",
        )
        for raw in plan.get("requirement_groups") or ():
            requirement = _mapping(raw, "integrated_readiness_requirement_invalid")
            requirement_id = str(requirement.get("requirement_id") or "")
            _require(
                requirement_id and requirement_id not in requirements,
                "integrated_readiness_requirement_id_invalid",
            )
            requirements[requirement_id] = (requirement, request_result)
    _require(requirements, "integrated_readiness_requirements_empty")
    review_rows: dict[str, Mapping[str, Any]] = {}
    for raw in review_plan.get("requirement_reviews") or ():
        row = _mapping(raw, "integrated_readiness_review_row_invalid")
        requirement_id = str(row.get("requirement_id") or "")
        _require(
            requirement_id and requirement_id not in review_rows,
            "integrated_readiness_review_requirement_id_invalid",
        )
        review_rows[requirement_id] = row
    _require(
        set(review_rows) == set(requirements),
        "integrated_readiness_review_requirement_set_mismatch",
    )
    polarity_rows: dict[str, Mapping[str, Any]] = {}
    for raw in polarity_plan.get("requirement_polarity_reviews") or ():
        row = _mapping(raw, "integrated_readiness_polarity_row_invalid")
        requirement_id = str(row.get("requirement_id") or "")
        _require(
            requirement_id and requirement_id not in polarity_rows,
            "integrated_readiness_polarity_requirement_id_invalid",
        )
        polarity_rows[requirement_id] = row
    _require(
        set(polarity_rows) == set(requirements),
        "integrated_readiness_polarity_requirement_set_mismatch",
    )

    compiled: list[dict[str, Any]] = []
    for requirement_id, (requirement, request_result) in requirements.items():
        review = review_rows[requirement_id]
        polarity_review = polarity_rows[requirement_id]
        request = _mapping(
            request_result.get("request"), "integrated_readiness_request_missing"
        )
        request_id = str(request.get("request_id") or "")
        state = str(review.get("decision_state") or "")
        _require(state in REVIEW_STATES, "integrated_readiness_review_state_invalid")
        _require(
            str(review.get("review_authority") or ""),
            "integrated_readiness_row_review_authority_missing",
        )
        _require(
            str(review.get("request_id") or "") == request_id,
            "integrated_readiness_review_request_mismatch",
        )
        _require(
            str(review.get("facet_id") or "")
            == str(requirement.get("facet_id") or ""),
            "integrated_readiness_review_facet_mismatch",
        )
        _require(
            str(review.get("role") or "") == str(requirement.get("role") or ""),
            "integrated_readiness_review_role_mismatch",
        )
        for field, expected in (
            ("request_id", request_id),
            ("facet_id", str(requirement.get("facet_id") or "")),
            ("role", str(requirement.get("role") or "")),
        ):
            _require(
                str(polarity_review.get(field) or "") == expected,
                f"integrated_readiness_polarity_{field}_mismatch",
            )
        product_ids = frozenset(
            str(value) for value in requirement.get("product_ids") or ()
        )
        legacy_supported = frozenset(
            str(value) for value in review.get("supported_product_ids") or ()
        )
        legacy_unsupported = frozenset(
            str(value) for value in review.get("unsupported_product_ids") or ()
        )
        _require(
            not legacy_supported.intersection(legacy_unsupported)
            and legacy_supported.union(legacy_unsupported) == product_ids,
            "integrated_readiness_legacy_product_partition_invalid",
        )
        evidence_bindings = [
            _binding_gate(
                binding=_mapping(
                    raw, "integrated_readiness_evidence_binding_invalid"
                ),
                pack_items=pack_items,
                anchor_digests=anchors,
                case_key=case_key,
                research_as_of=str(request.get("research_as_of") or ""),
            )
            for raw in review.get("evidence_bindings") or ()
        ]
        additional_evidence_bindings = [
            _binding_gate(
                binding=_mapping(
                    raw,
                    "integrated_readiness_additional_evidence_binding_invalid",
                ),
                pack_items=pack_items,
                anchor_digests=anchors,
                case_key=case_key,
                research_as_of=str(request.get("research_as_of") or ""),
            )
            for raw in polarity_review.get("additional_evidence_bindings") or ()
        ]
        evidence_binding_keys = [
            (
                str(row.get("evidence_item_digest") or ""),
                str(row.get("required_slot_id") or ""),
                tuple(row.get("required_facet_ids") or ()),
            )
            for row in [*evidence_bindings, *additional_evidence_bindings]
        ]
        _require(
            len(evidence_binding_keys) == len(set(evidence_binding_keys)),
            "integrated_readiness_duplicate_evidence_binding",
        )
        evidence_bindings = [*evidence_bindings, *additional_evidence_bindings]
        if state in {"accepted", "accepted_bounded", "partial"}:
            _require(
                evidence_bindings,
                "integrated_readiness_review_evidence_required",
            )
        bound_evidence_digests = {
            str(row.get("evidence_item_digest") or "") for row in evidence_bindings
        }
        axis_rows: list[dict[str, Any]] = []
        seen_axis_ids: set[str] = set()
        for raw_axis in polarity_review.get("product_axis_decisions") or ():
            axis = _mapping(raw_axis, "integrated_readiness_axis_decision_invalid")
            product_id = str(axis.get("product_id") or "")
            _require(
                product_id
                and product_id in product_ids
                and product_id not in seen_axis_ids,
                "integrated_readiness_axis_product_id_invalid",
            )
            seen_axis_ids.add(product_id)
            coverage_state = str(axis.get("coverage_state") or "")
            evidence_polarity = str(axis.get("evidence_polarity") or "")
            _require(
                coverage_state in AXIS_COVERAGE_STATES,
                "integrated_readiness_axis_coverage_state_invalid",
            )
            _require(
                evidence_polarity in EVIDENCE_POLARITIES,
                "integrated_readiness_axis_polarity_invalid",
            )
            axis_evidence = frozenset(
                _unique_strings(
                    axis.get("evidence_item_digests") or (),
                    "integrated_readiness_axis_evidence_invalid",
                )
            )
            if coverage_state == "addressed":
                _require(
                    evidence_polarity != "not_assessed" and axis_evidence,
                    "integrated_readiness_addressed_axis_requires_evidence_and_polarity",
                )
                _require(
                    axis_evidence.issubset(bound_evidence_digests),
                    "integrated_readiness_axis_evidence_outside_review_binding",
                )
            else:
                _require(
                    evidence_polarity == "not_assessed" and not axis_evidence,
                    "integrated_readiness_unaddressed_axis_must_not_claim_evidence",
                )
            scope_boundary_codes = tuple(
                sorted(
                    _unique_strings(
                        axis.get("scope_boundary_codes") or (),
                        "integrated_readiness_axis_scope_boundaries_invalid",
                    )
                )
            )
            axis_rows.append(
                {
                    "product_id": product_id,
                    "coverage_state": coverage_state,
                    "evidence_polarity": evidence_polarity,
                    "evidence_item_digests": sorted(axis_evidence),
                    "decision_reason_zh": str(axis.get("decision_reason_zh") or ""),
                    "claim_boundary_zh": str(axis.get("claim_boundary_zh") or ""),
                    "scope_boundary_codes": list(scope_boundary_codes),
                }
            )
        _require(
            seen_axis_ids == product_ids,
            "integrated_readiness_axis_decision_set_mismatch",
        )
        addressed = {
            row["product_id"]
            for row in axis_rows
            if row["coverage_state"] == "addressed"
        }
        unaddressed = product_ids - addressed
        if not addressed:
            derived_state = "needs_review"
        elif unaddressed:
            derived_state = "partial"
        elif all(row["evidence_polarity"] == "supports" for row in axis_rows):
            derived_state = "accepted"
        else:
            derived_state = "accepted_bounded"
        _require(
            derived_state != "accepted_bounded"
            or str(review.get("claim_boundary_zh") or "").strip()
            or any(str(row.get("claim_boundary_zh") or "").strip() for row in axis_rows),
            "integrated_readiness_boundary_required",
        )
        numeric = _numeric_coverage(
            requirement=requirement, request_result=request_result
        )
        natural_ready = derived_state in {"accepted", "accepted_bounded"}
        numeric_state = str(numeric["state"])
        if not natural_ready:
            integrated_state = "not_ready_s1_evidence"
            research_consumable = False
        elif (
            numeric_state == "typed_conflict"
            or numeric.get("observed_state") == "typed_conflict"
        ):
            integrated_state = "not_ready_s2_numeric_conflict"
            research_consumable = False
        elif numeric_state == "partial":
            integrated_state = "not_ready_s2_numeric_conflict_or_partial"
            research_consumable = False
        elif numeric_state == "typed_gap":
            integrated_state = "qualitative_ready_s2_numeric_gap"
            research_consumable = True
        elif numeric_state == "retrieval_context_only":
            integrated_state = "ready_s1_numeric_context_only"
            research_consumable = True
        elif derived_state == "accepted_bounded":
            integrated_state = "ready_with_claim_boundary"
            research_consumable = True
        else:
            integrated_state = "ready"
            research_consumable = True
        fully_satisfied = integrated_state in {"ready", "ready_s1_numeric_context_only"}
        body = {
            "requirement_id": requirement_id,
            "request_id": request_id,
            "facet_id": requirement.get("facet_id"),
            "role": requirement.get("role"),
            "target_entities": sorted(
                str(value) for value in requirement.get("target_entities") or ()
            ),
            "metric_ids": sorted(
                str(value) for value in requirement.get("metric_ids") or ()
            ),
            "product_ids": sorted(product_ids),
            "evidence_decision_state": derived_state,
            "legacy_v1_0_evidence_decision_state": state,
            "addressed_product_ids": sorted(addressed),
            "unaddressed_product_ids": sorted(unaddressed),
            "product_axis_decisions": sorted(
                axis_rows, key=lambda row: str(row["product_id"])
            ),
            "evidence_bindings": evidence_bindings,
            "decision_reason_zh": str(review.get("decision_reason_zh") or ""),
            "claim_boundary_zh": str(review.get("claim_boundary_zh") or ""),
            "review_authority": str(review.get("review_authority") or ""),
            "numeric_coverage": numeric,
            "integrated_state": integrated_state,
            "research_consumable": research_consumable,
            "fully_satisfied": fully_satisfied,
            "candidate_text_promoted": False,
            "numeric_authority_merged_into_evidence": False,
        }
        compiled.append(
            {**body, "requirement_readiness_digest": canonical_digest(body)}
        )

    request_rows: list[dict[str, Any]] = []
    for request_id in request_results:
        rows = [row for row in compiled if row["request_id"] == request_id]
        _require(rows, "integrated_readiness_request_has_no_requirement")
        fully = sum(bool(row["fully_satisfied"]) for row in rows)
        consumable = sum(bool(row["research_consumable"]) for row in rows)
        if fully == len(rows):
            state = "ready"
        elif consumable == len(rows):
            state = "research_consumable_with_boundaries_or_s2_gaps"
        else:
            state = "not_ready"
        request_rows.append(
            {
                "request_id": request_id,
                "state": state,
                "requirement_count": len(rows),
                "fully_satisfied_requirement_count": fully,
                "research_consumable_requirement_count": consumable,
                "not_ready_requirement_ids": sorted(
                    row["requirement_id"]
                    for row in rows
                    if not row["research_consumable"]
                ),
            }
        )
    state_counts = Counter(row["integrated_state"] for row in compiled)
    body = {
        "schema_version": INTEGRATED_READINESS_SCHEMA_VERSION,
        "status": "integrated_requirement_readiness_materialized",
        "recorded_at": recorded_at,
        "case_key": case_key,
        "research_plan_digest": research_plan_digest,
        "scope_compilation_digest": scope_compilation.get("compilation_digest"),
        "evidence_pack_payload_digest": pack_digest,
        "review_plan_digest": review_plan_digest,
        "polarity_plan_digest": canonical_digest(dict(polarity_plan)),
        "requirements": compiled,
        "requests": request_rows,
        "summary": {
            "requirement_count": len(compiled),
            "fully_satisfied_requirement_count": sum(
                bool(row["fully_satisfied"]) for row in compiled
            ),
            "research_consumable_requirement_count": sum(
                bool(row["research_consumable"]) for row in compiled
            ),
            "request_count": len(request_rows),
            "ready_request_count": sum(row["state"] == "ready" for row in request_rows),
            "research_consumable_request_count": sum(
                row["state"]
                in {"ready", "research_consumable_with_boundaries_or_s2_gaps"}
                for row in request_rows
            ),
            "integrated_state_counts": dict(sorted(state_counts.items())),
        },
        "authority": {
            "candidate_review_is_not_evidence": True,
            "only_current_reviewed_pack_items_may_be_reused": True,
            "numeric_facts_remain_independent_S2_authority": True,
            "candidate_text_promoted": False,
            "runtime_evidence_promoted": False,
            "numeric_authority_merged_into_evidence": False,
            "public_information_gap_claimed": False,
            "s1_qualification_claimed": False,
            "product_publication": False,
        },
        "known_boundary": (
            "This compiler validates an explicit requirement-to-reviewed-Evidence "
            "mapping and independently consumes same-request S2 NumericFact or typed "
            "gap receipts. It does not judge new candidate text, promote Evidence, "
            "merge numeric authority, prove a public-information gap, or qualify S1."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


__all__ = [
    "INTEGRATED_READINESS_SCHEMA_VERSION",
    "IntegratedPackReadinessError",
    "compile_integrated_requirement_readiness",
]
