from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import math
from typing import Any


PLAN_SCHEMA_V1_0 = "fin_ia_material_evidence_requirement_plan_v1_0"
PLAN_SCHEMA_V1_1 = "fin_ia_material_evidence_requirement_plan_v1_1"
PLAN_SCHEMAS = {PLAN_SCHEMA_V1_0, PLAN_SCHEMA_V1_1}
PLAN_SCHEMA = PLAN_SCHEMA_V1_0
REFERENCE_SCHEMA_V1_0 = "fin_ia_material_evidence_set_reference_v1_0"
REFERENCE_SCHEMA_V1_1 = "fin_ia_material_evidence_set_reference_v1_1"
REFERENCE_SCHEMAS = {REFERENCE_SCHEMA_V1_0, REFERENCE_SCHEMA_V1_1}
REFERENCE_SCHEMA = REFERENCE_SCHEMA_V1_0
SELECTION_SCHEMA_V1_0 = "fin_ia_request_bound_candidate_review_v1_0"
SELECTION_SCHEMA_V1_1 = "fin_ia_request_bound_candidate_review_v1_1"
SELECTION_SCHEMAS = {SELECTION_SCHEMA_V1_0, SELECTION_SCHEMA_V1_1}
SELECTION_SCHEMA = SELECTION_SCHEMA_V1_0
PERIOD_MODES = {"any", "single_period", "all_periods_same_basis"}
ROLES = {"direct", "counter", "bridge", "context"}
COVERAGE_MODES = {"single_binding", "collective_axes"}
PLAN_FIELDS = {"schema_version", "request_id", "requirement_groups"}
GROUP_FIELDS = {
    "coverage_mode",
    "facet_id",
    "fiscal_years",
    "metric_ids",
    "minimum_candidates",
    "period_mode",
    "priority",
    "product_ids",
    "requirement_id",
    "role",
    "target_entities",
}
FORBIDDEN_PLAN_FIELDS = {
    "answer_url",
    "candidate_id",
    "compiled_object_id",
    "object_id",
    "qrel_id",
    "source_url",
}


class EvidenceSetCoverageError(ValueError):
    pass


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item) for item in value if str(item))


def _ints(value: Any) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(int(item) for item in value)


def _unknown_fields(value: Mapping[str, Any], allowed: set[str]) -> list[str]:
    return sorted(str(key) for key in value if str(key) not in allowed)


def _verify_content_digest(
    value: Mapping[str, Any], *, digest_field: str, error_code: str
) -> None:
    supplied = str(value.get(digest_field) or "")
    if not supplied:
        raise EvidenceSetCoverageError(error_code)
    payload = dict(value)
    payload.pop(digest_field, None)
    if supplied != canonical_digest(payload):
        raise EvidenceSetCoverageError(error_code)


def _find_forbidden_fields(value: Any, *, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            next_path = f"{path}.{key_text}"
            if key_text in FORBIDDEN_PLAN_FIELDS:
                findings.append(next_path)
            findings.extend(_find_forbidden_fields(item, path=next_path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            findings.extend(_find_forbidden_fields(item, path=f"{path}[{index}]"))
    return findings


def validate_requirement_plan(
    *, evidence_request: Mapping[str, Any], plan: Mapping[str, Any], review_k: int
) -> dict[str, Any]:
    unknown_plan_fields = _unknown_fields(plan, PLAN_FIELDS)
    if unknown_plan_fields:
        raise EvidenceSetCoverageError(
            f"material_requirement_plan_field_invalid:{unknown_plan_fields[0]}"
        )
    plan_schema = str(plan.get("schema_version") or "")
    if plan_schema not in PLAN_SCHEMAS:
        raise EvidenceSetCoverageError("material_requirement_plan_schema_invalid")
    request_id = str(evidence_request.get("request_id") or "")
    request_case = str(evidence_request.get("case_key") or "")
    if not request_id or not request_case:
        raise EvidenceSetCoverageError("material_requirement_request_identity_invalid")
    if str(plan.get("request_id") or "") != request_id:
        raise EvidenceSetCoverageError("material_requirement_request_id_mismatch")
    if int(review_k) <= 0:
        raise EvidenceSetCoverageError("material_requirement_review_k_invalid")
    forbidden = _find_forbidden_fields(plan)
    if forbidden:
        raise EvidenceSetCoverageError(
            f"material_requirement_plan_leaks_gold_identity:{forbidden[0]}"
        )

    request_metrics = set(_strings(evidence_request.get("metric_intents")))
    request_products = set(_strings(evidence_request.get("product_intents")))
    request_facets = set(_strings(evidence_request.get("requested_facet_ids")))
    request_entities = set(_strings(evidence_request.get("target_entities")))
    request_period = evidence_request.get("period") or {}
    if not isinstance(request_period, Mapping):
        raise EvidenceSetCoverageError("material_requirement_request_period_invalid")
    request_years = set(_ints(request_period.get("fiscal_years")))
    if not request_entities:
        raise EvidenceSetCoverageError("material_requirement_request_entities_empty")

    groups = list(plan.get("requirement_groups") or ())
    if not groups:
        raise EvidenceSetCoverageError("material_requirement_groups_empty")
    group_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    minimum_capacity = 0
    maximum_reserved_capacity = 0
    for index, raw in enumerate(groups):
        if not isinstance(raw, Mapping):
            raise EvidenceSetCoverageError("material_requirement_group_invalid")
        unknown_group_fields = _unknown_fields(raw, GROUP_FIELDS)
        if unknown_group_fields:
            raise EvidenceSetCoverageError(
                "material_requirement_group_field_invalid:"
                f"{unknown_group_fields[0]}"
            )
        group_id = str(raw.get("requirement_id") or "")
        if not group_id or group_id in group_ids:
            raise EvidenceSetCoverageError("material_requirement_group_id_invalid")
        group_ids.add(group_id)
        facet_id = str(raw.get("facet_id") or "")
        role = str(raw.get("role") or "")
        period_mode = str(raw.get("period_mode") or "")
        coverage_mode = str(raw.get("coverage_mode") or "single_binding")
        metrics = set(_strings(raw.get("metric_ids")))
        products = set(_strings(raw.get("product_ids")))
        entities = set(_strings(raw.get("target_entities")))
        years = set(_ints(raw.get("fiscal_years")))
        minimum_candidates = int(raw.get("minimum_candidates") or 0)
        if facet_id not in request_facets:
            raise EvidenceSetCoverageError(
                f"material_requirement_facet_outside_request:{group_id}"
            )
        if role not in ROLES:
            raise EvidenceSetCoverageError(
                f"material_requirement_role_invalid:{group_id}"
            )
        if period_mode not in PERIOD_MODES:
            raise EvidenceSetCoverageError(
                f"material_requirement_period_mode_invalid:{group_id}"
            )
        if coverage_mode not in COVERAGE_MODES:
            raise EvidenceSetCoverageError(
                f"material_requirement_coverage_mode_invalid:{group_id}"
            )
        if plan_schema == PLAN_SCHEMA_V1_0 and "coverage_mode" in raw:
            raise EvidenceSetCoverageError(
                f"material_requirement_coverage_mode_unsupported:{group_id}"
            )
        if (
            period_mode == "all_periods_same_basis"
            and coverage_mode != "single_binding"
        ):
            raise EvidenceSetCoverageError(
                f"material_requirement_temporal_coverage_mode_invalid:{group_id}"
            )
        if metrics and not metrics.issubset(request_metrics):
            raise EvidenceSetCoverageError(
                f"material_requirement_metric_outside_request:{group_id}"
            )
        if products and not products.issubset(request_products):
            raise EvidenceSetCoverageError(
                f"material_requirement_product_outside_request:{group_id}"
            )
        if not entities or not entities.issubset(request_entities):
            raise EvidenceSetCoverageError(
                f"material_requirement_entity_outside_request:{group_id}"
            )
        if years and not years.issubset(request_years):
            raise EvidenceSetCoverageError(
                f"material_requirement_period_outside_request:{group_id}"
            )
        if period_mode == "all_periods_same_basis" and len(years) < 2:
            raise EvidenceSetCoverageError(
                f"material_requirement_temporal_pair_incomplete:{group_id}"
            )
        temporal_products_valid = (
            len(products) == 1
            if plan_schema == PLAN_SCHEMA_V1_0
            else len(products) <= 1
        )
        if period_mode == "all_periods_same_basis" and (
            len(metrics) != 1
            or not temporal_products_valid
            or len(entities) != 1
        ):
            raise EvidenceSetCoverageError(
                f"material_requirement_temporal_scope_not_atomic:{group_id}"
            )
        if period_mode == "all_periods_same_basis" and minimum_candidates != 1:
            raise EvidenceSetCoverageError(
                f"material_requirement_temporal_minimum_invalid:{group_id}"
            )
        if period_mode == "single_period" and len(years) != 1:
            raise EvidenceSetCoverageError(
                f"material_requirement_single_period_invalid:{group_id}"
            )
        if period_mode == "any" and years:
            raise EvidenceSetCoverageError(
                f"material_requirement_any_period_must_be_empty:{group_id}"
            )
        if minimum_candidates <= 0:
            raise EvidenceSetCoverageError(
                f"material_requirement_minimum_invalid:{group_id}"
            )
        priority = int(raw.get("priority") or index + 1)
        if priority <= 0:
            raise EvidenceSetCoverageError(
                f"material_requirement_priority_invalid:{group_id}"
            )
        if period_mode == "all_periods_same_basis":
            reserved_capacity = len(years)
        elif coverage_mode == "collective_axes":
            axis_count = int(bool(metrics)) + int(bool(products))
            reserved_capacity = max(minimum_candidates, axis_count or 1)
        else:
            reserved_capacity = minimum_candidates
        minimum_capacity += minimum_candidates
        maximum_reserved_capacity += reserved_capacity
        normalized_group = {
                "requirement_id": group_id,
                "facet_id": facet_id,
                "role": role,
                "period_mode": period_mode,
                "metric_ids": sorted(metrics),
                "product_ids": sorted(products),
                "target_entities": sorted(entities),
                "fiscal_years": sorted(years),
                "minimum_candidates": minimum_candidates,
                "reserved_candidate_capacity": reserved_capacity,
                "priority": priority,
            }
        if plan_schema == PLAN_SCHEMA_V1_1:
            normalized_group["coverage_mode"] = coverage_mode
        normalized.append(normalized_group)
    if maximum_reserved_capacity > int(review_k):
        raise EvidenceSetCoverageError("material_requirement_review_capacity_insufficient")
    normalized.sort(key=lambda row: (row["priority"], row["requirement_id"]))
    result = {
        "schema_version": plan_schema,
        "request_id": str(plan["request_id"]),
        "case_key": request_case,
        "evidence_request_digest": canonical_digest(evidence_request),
        "review_k": int(review_k),
        "minimum_required_capacity": minimum_capacity,
        "maximum_reserved_capacity": maximum_reserved_capacity,
        "requirement_groups": normalized,
        "candidate_is_not_evidence": True,
        "numeric_fact_authority": False,
    }
    result["plan_digest"] = canonical_digest(result)
    return result


def compile_requirement_plan(
    *,
    evidence_request: Mapping[str, Any],
    material_requirements: Sequence[Mapping[str, Any]],
    review_k: int,
    schema_version: str = PLAN_SCHEMA_V1_0,
) -> dict[str, Any]:
    """Compile public ResearchBlueprint requirements into a label-free plan.

    ``material_requirements`` is an upstream research-planning surface.  It may
    name only request-visible facets, roles, metrics, products, entities and
    periods.  Candidate or reference identities are rejected by the validator.
    """

    return validate_requirement_plan(
        evidence_request=evidence_request,
        plan={
            "schema_version": schema_version,
            "request_id": str(evidence_request.get("request_id") or ""),
            "requirement_groups": [dict(value) for value in material_requirements],
        },
        review_k=review_k,
    )


def _validate_normalized_plan(plan: Mapping[str, Any]) -> None:
    if plan.get("schema_version") not in PLAN_SCHEMAS:
        raise EvidenceSetCoverageError("material_normalized_plan_schema_invalid")
    _verify_content_digest(
        plan,
        digest_field="plan_digest",
        error_code="material_normalized_plan_digest_invalid",
    )
    requirement_ids = [
        str(group.get("requirement_id") or "")
        for group in plan.get("requirement_groups") or ()
        if isinstance(group, Mapping)
    ]
    if (
        not requirement_ids
        or not all(requirement_ids)
        or len(requirement_ids) != len(set(requirement_ids))
    ):
        raise EvidenceSetCoverageError("material_normalized_plan_groups_invalid")
    if int(plan.get("maximum_reserved_capacity") or 0) > int(
        plan.get("review_k") or 0
    ):
        raise EvidenceSetCoverageError("material_normalized_plan_capacity_invalid")


def _candidate_sort_key(row: Mapping[str, Any]) -> tuple[int, float, str]:
    return (
        int(row.get("base_rank") or 10**9),
        -float(row.get("score") or 0.0),
        str(row.get("compiled_object_id") or ""),
    )


def _validate_candidates(
    candidates: Sequence[Mapping[str, Any]], *, plan_schema: str
) -> None:
    identities: list[str] = []
    for row in candidates:
        if not isinstance(row, Mapping):
            raise EvidenceSetCoverageError("material_candidate_invalid")
        object_id = str(row.get("compiled_object_id") or "")
        case_key = str(row.get("case_key") or "")
        try:
            rank = int(row.get("base_rank"))
            score = float(row.get("score") or 0.0)
        except (TypeError, ValueError) as exc:
            raise EvidenceSetCoverageError("material_candidate_rank_invalid") from exc
        if not object_id or not case_key:
            raise EvidenceSetCoverageError("material_candidate_identity_invalid")
        if rank <= 0 or not math.isfinite(score):
            raise EvidenceSetCoverageError("material_candidate_rank_invalid")
        if plan_schema == PLAN_SCHEMA_V1_1:
            if row.get("schema_version") != "fin_ia_material_candidate_metadata_v1_1":
                raise EvidenceSetCoverageError("material_candidate_schema_invalid")
            bindings = row.get("material_bindings")
            if not isinstance(bindings, Sequence) or isinstance(
                bindings, (str, bytes)
            ):
                raise EvidenceSetCoverageError("material_candidate_bindings_invalid")
            for binding in bindings:
                if not isinstance(binding, Mapping):
                    raise EvidenceSetCoverageError(
                        "material_candidate_binding_invalid"
                    )
                if (
                    not str(binding.get("facet_id") or "")
                    or str(binding.get("role") or "") not in ROLES
                ):
                    raise EvidenceSetCoverageError(
                        "material_candidate_binding_invalid"
                    )
        identities.append(object_id)
    if len(identities) != len(set(identities)):
        raise EvidenceSetCoverageError("material_candidate_identity_invalid")


def _candidate_bindings(
    candidate: Mapping[str, Any], *, plan_schema: str
) -> tuple[Mapping[str, Any], ...]:
    if plan_schema == PLAN_SCHEMA_V1_1:
        return tuple(
            binding
            for binding in candidate.get("material_bindings") or ()
            if isinstance(binding, Mapping)
        )
    return (
        {
            "facet_id": next(iter(_strings(candidate.get("facet_ids"))), ""),
            "facet_ids": list(_strings(candidate.get("facet_ids"))),
            "roles": list(_strings(candidate.get("roles"))),
            "metric_ids": list(_strings(candidate.get("metric_ids"))),
            "product_ids": list(_strings(candidate.get("product_ids"))),
            "fiscal_years": list(_ints(candidate.get("fiscal_years"))),
            "same_basis_key": str(candidate.get("same_basis_key") or ""),
        },
    )


def _binding_matches(
    binding: Mapping[str, Any], group: Mapping[str, Any], *, plan_schema: str
) -> bool:
    binding_facets = (
        {str(binding.get("facet_id") or "")}
        if plan_schema == PLAN_SCHEMA_V1_1
        else set(_strings(binding.get("facet_ids")))
    )
    binding_roles = (
        {str(binding.get("role") or "")}
        if plan_schema == PLAN_SCHEMA_V1_1
        else set(_strings(binding.get("roles")))
    )
    if group["facet_id"] not in binding_facets:
        return False
    if group["role"] not in binding_roles:
        return False
    if group["metric_ids"] and not set(group["metric_ids"]).intersection(
        _strings(binding.get("metric_ids"))
    ):
        return False
    if group["product_ids"] and not set(group["product_ids"]).intersection(
        _strings(binding.get("product_ids"))
    ):
        return False
    return True


def _binding_matches_base(
    binding: Mapping[str, Any], group: Mapping[str, Any], *, plan_schema: str
) -> bool:
    binding_facets = (
        {str(binding.get("facet_id") or "")}
        if plan_schema == PLAN_SCHEMA_V1_1
        else set(_strings(binding.get("facet_ids")))
    )
    binding_roles = (
        {str(binding.get("role") or "")}
        if plan_schema == PLAN_SCHEMA_V1_1
        else set(_strings(binding.get("roles")))
    )
    return (
        group["facet_id"] in binding_facets
        and group["role"] in binding_roles
    )


def _collective_candidate_axes(
    candidate: Mapping[str, Any],
    group: Mapping[str, Any],
    *,
    case_key: str,
    plan_schema: str,
) -> tuple[frozenset[str], frozenset[str]]:
    """Return request-visible axes that make a candidate worth reviewing.

    A v1.1 natural ResearchBlueprint can require a product/topic phrase that is
    deliberately absent from the deterministic product ontology.  The feature
    compiler retains an exact request-visible phrase in
    ``contextual_or_unclassified_need_product_intents``.  That is sufficient to
    reserve the candidate for bounded review, but never to promote it to
    Evidence.  Temporal ``single_binding`` paths do not call this helper and
    therefore continue to require canonical correlated bindings.
    """

    if str(candidate.get("case_key") or "") != case_key:
        return frozenset(), frozenset()
    if not set(group["target_entities"]).intersection(
        _strings(candidate.get("target_entities"))
    ):
        return frozenset(), frozenset()
    metrics: set[str] = set()
    products: set[str] = set()
    required_metrics = set(group["metric_ids"])
    required_products = set(group["product_ids"])
    for binding in _candidate_bindings(candidate, plan_schema=plan_schema):
        if not _binding_matches_base(binding, group, plan_schema=plan_schema):
            continue
        metrics.update(
            required_metrics.intersection(_strings(binding.get("metric_ids")))
        )
        review_product_ids = set(_strings(binding.get("product_ids")))
        if plan_schema == PLAN_SCHEMA_V1_1:
            review_product_ids.update(
                _strings(
                    binding.get(
                        "contextual_or_unclassified_need_product_intents"
                    )
                )
            )
        products.update(required_products.intersection(review_product_ids))
    return frozenset(metrics), frozenset(products)


def _matching_bindings(
    candidate: Mapping[str, Any],
    group: Mapping[str, Any],
    *,
    case_key: str,
    plan_schema: str,
) -> tuple[Mapping[str, Any], ...]:
    if str(candidate.get("case_key") or "") != case_key:
        return ()
    if not set(group["target_entities"]).intersection(
        _strings(candidate.get("target_entities"))
    ):
        return ()
    return tuple(
        binding
        for binding in _candidate_bindings(candidate, plan_schema=plan_schema)
        if _binding_matches(binding, group, plan_schema=plan_schema)
    )


def _candidate_matches(
    candidate: Mapping[str, Any],
    group: Mapping[str, Any],
    *,
    case_key: str,
    plan_schema: str,
) -> bool:
    return bool(
        _matching_bindings(
            candidate,
            group,
            case_key=case_key,
            plan_schema=plan_schema,
        )
    )


def _candidate_contributes(
    candidate: Mapping[str, Any],
    group: Mapping[str, Any],
    *,
    case_key: str,
    plan_schema: str,
) -> bool:
    if group.get("coverage_mode") != "collective_axes":
        return _candidate_matches(
            candidate,
            group,
            case_key=case_key,
            plan_schema=plan_schema,
        )
    metric_required = bool(group["metric_ids"])
    product_required = bool(group["product_ids"])
    if not metric_required and not product_required:
        if str(candidate.get("case_key") or "") != case_key or not set(
            group["target_entities"]
        ).intersection(_strings(candidate.get("target_entities"))):
            return False
        return any(
            _binding_matches_base(binding, group, plan_schema=plan_schema)
            for binding in _candidate_bindings(candidate, plan_schema=plan_schema)
        )
    metrics, products = _collective_candidate_axes(
        candidate,
        group,
        case_key=case_key,
        plan_schema=plan_schema,
    )
    return bool(metrics or products)


def _collective_bundle(
    candidates: Sequence[Mapping[str, Any]],
    group: Mapping[str, Any],
    *,
    case_key: str,
    plan_schema: str,
) -> list[Mapping[str, Any]]:
    """Choose the smallest stable set whose correlated bindings cover axes."""

    ordered = sorted(candidates, key=_candidate_sort_key)
    required_metrics = set(group["metric_ids"])
    required_products = set(group["product_ids"])
    capacity = int(group.get("reserved_candidate_capacity") or 0)
    selected: list[Mapping[str, Any]] = []
    covered_metrics: set[str] = set()
    covered_products: set[str] = set()
    while not (
        required_metrics.issubset(covered_metrics)
        and required_products.issubset(covered_products)
    ):
        best: Mapping[str, Any] | None = None
        best_gain = 0
        for candidate in ordered:
            if candidate in selected:
                continue
            metrics, products = _collective_candidate_axes(
                candidate,
                group,
                case_key=case_key,
                plan_schema=plan_schema,
            )
            gain = len(metrics.difference(covered_metrics)) + len(
                products.difference(covered_products)
            )
            if gain > best_gain:
                best = candidate
                best_gain = gain
        if best is None or len(selected) >= capacity:
            return []
        selected.append(best)
        metrics, products = _collective_candidate_axes(
            best,
            group,
            case_key=case_key,
            plan_schema=plan_schema,
        )
        covered_metrics.update(metrics)
        covered_products.update(products)
    required = int(group["minimum_candidates"])
    for candidate in ordered:
        if len(selected) >= required:
            break
        if candidate not in selected:
            if len(selected) >= capacity:
                return []
            selected.append(candidate)
    return selected


def _temporal_bundle(
    candidates: Sequence[Mapping[str, Any]],
    group: Mapping[str, Any],
    *,
    case_key: str,
    plan_schema: str,
) -> list[Mapping[str, Any]]:
    required_years = set(int(value) for value in group["fiscal_years"])
    by_basis: dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {}
    for candidate in candidates:
        for binding in _matching_bindings(
            candidate,
            group,
            case_key=case_key,
            plan_schema=plan_schema,
        ):
            basis = str(binding.get("same_basis_key") or "")
            if basis:
                by_basis.setdefault(basis, []).append((candidate, binding))
    bundles: list[list[Mapping[str, Any]]] = []
    for basis_rows in by_basis.values():
        ordered = sorted(basis_rows, key=lambda value: _candidate_sort_key(value[0]))
        for candidate, binding in ordered:
            if required_years.issubset(set(_ints(binding.get("fiscal_years")))):
                bundles.append([candidate])
        per_year: list[Mapping[str, Any]] = []
        for year in sorted(required_years):
            match = next(
                (
                    candidate
                    for candidate, binding in ordered
                    if year in set(_ints(binding.get("fiscal_years")))
                ),
                None,
            )
            if match is None:
                per_year = []
                break
            if match not in per_year:
                per_year.append(match)
        if per_year:
            bundles.append(per_year)
    if not bundles:
        return []
    bundles.sort(
        key=lambda bundle: (
            max(_candidate_sort_key(row)[0] for row in bundle),
            sum(_candidate_sort_key(row)[0] for row in bundle),
            len(bundle),
            tuple(str(row["compiled_object_id"]) for row in bundle),
        )
    )
    return bundles[0]


def select_request_bound_review(
    *, candidates: Sequence[Mapping[str, Any]], plan: Mapping[str, Any]
) -> dict[str, Any]:
    _validate_normalized_plan(plan)
    review_k = int(plan.get("review_k") or 0)
    plan_schema = str(plan.get("schema_version") or "")
    if review_k <= 0:
        raise EvidenceSetCoverageError("material_review_k_invalid")
    _validate_candidates(candidates, plan_schema=plan_schema)
    all_ordered = sorted(candidates, key=_candidate_sort_key)
    case_key = str(plan.get("case_key") or "")
    allowed_entities = {
        entity
        for group in plan.get("requirement_groups") or ()
        for entity in _strings(group.get("target_entities"))
    }
    ordered = [
        row
        for row in all_ordered
        if str(row.get("case_key") or "") == case_key
        and (
            plan_schema == PLAN_SCHEMA_V1_0
            or bool(
                allowed_entities.intersection(
                    _strings(row.get("target_entities"))
                )
            )
        )
    ]
    hard_boundary_rejected = [
        str(row["compiled_object_id"])
        for row in all_ordered
        if str(row.get("case_key") or "") != case_key
        or (
            plan_schema == PLAN_SCHEMA_V1_1
            and not allowed_entities.intersection(
                _strings(row.get("target_entities"))
            )
        )
    ]
    request_aligned = [
        row
        for row in ordered
        if plan_schema == PLAN_SCHEMA_V1_0
        or any(
            _candidate_contributes(
                row,
                group,
                case_key=case_key,
                plan_schema=plan_schema,
            )
            for group in plan.get("requirement_groups") or ()
        )
    ]
    request_alignment_excluded = [
        str(row["compiled_object_id"])
        for row in ordered
        if row not in request_aligned
    ]
    selected: list[Mapping[str, Any]] = []
    selected_ids: set[str] = set()
    met: list[str] = []
    unmet: list[str] = []
    receipts: list[dict[str, Any]] = []
    for group in plan.get("requirement_groups") or ():
        eligible = [
            row
            for row in request_aligned
            if _candidate_contributes(
                row,
                group,
                case_key=case_key,
                plan_schema=plan_schema,
            )
        ]
        if group.get("coverage_mode") == "collective_axes":
            bundle = _collective_bundle(
                eligible,
                group,
                case_key=case_key,
                plan_schema=plan_schema,
            )
        elif group["period_mode"] == "all_periods_same_basis":
            bundle = _temporal_bundle(
                eligible,
                group,
                case_key=case_key,
                plan_schema=plan_schema,
            )
        else:
            years = set(int(value) for value in group["fiscal_years"])
            if years:
                eligible = [
                    row
                    for row in eligible
                    if any(
                        years.intersection(_ints(binding.get("fiscal_years")))
                        for binding in _matching_bindings(
                            row,
                            group,
                            case_key=case_key,
                            plan_schema=plan_schema,
                        )
                    )
                ]
            bundle = eligible[: int(group["minimum_candidates"])]
        required = int(group["minimum_candidates"])
        complete = bool(bundle) and (
            group["period_mode"] == "all_periods_same_basis"
            or group.get("coverage_mode") == "collective_axes"
            or len(bundle) >= required
        )
        if complete:
            for row in bundle:
                object_id = str(row["compiled_object_id"])
                if object_id not in selected_ids:
                    selected.append(row)
                    selected_ids.add(object_id)
            met.append(str(group["requirement_id"]))
        else:
            unmet.append(str(group["requirement_id"]))
        receipt = {
            "requirement_id": group["requirement_id"],
            "complete": complete,
            "selected_candidate_ids": [
                str(row["compiled_object_id"]) for row in bundle
            ],
        }
        if plan_schema == PLAN_SCHEMA_V1_1:
            receipt["coverage_mode"] = group.get(
                "coverage_mode", "single_binding"
            )
        receipts.append(receipt)
    if len(selected) > review_k:
        raise EvidenceSetCoverageError("material_review_capacity_exceeded")
    for row in request_aligned:
        if len(selected) >= review_k:
            break
        object_id = str(row["compiled_object_id"])
        if object_id not in selected_ids:
            selected.append(row)
            selected_ids.add(object_id)
    result = {
        "schema_version": (
            SELECTION_SCHEMA_V1_1
            if plan_schema == PLAN_SCHEMA_V1_1
            else SELECTION_SCHEMA_V1_0
        ),
        "request_id": plan.get("request_id"),
        "case_key": case_key,
        "evidence_request_digest": plan.get("evidence_request_digest"),
        "requirement_plan_digest": plan.get("plan_digest"),
        "review_k": review_k,
        "input_candidate_count": len(all_ordered),
        "case_eligible_candidate_count": len(ordered),
        "hard_boundary_rejected_candidate_ids": hard_boundary_rejected,
        "requirement_ids": [
            str(group["requirement_id"])
            for group in plan.get("requirement_groups") or ()
        ],
        "selected_candidate_ids": [
            str(row["compiled_object_id"]) for row in selected
        ],
        "met_requirement_ids": met,
        "unmet_requirement_ids": unmet,
        "requirement_receipts": receipts,
        "candidate_is_not_evidence": True,
        "numeric_fact_authority": False,
    }
    if plan_schema == PLAN_SCHEMA_V1_1:
        result["request_alignment_excluded_candidate_ids"] = (
            request_alignment_excluded
        )
    result["selection_digest"] = canonical_digest(result)
    return result


def _validate_selection(selection: Mapping[str, Any]) -> None:
    if selection.get("schema_version") not in SELECTION_SCHEMAS:
        raise EvidenceSetCoverageError("material_selection_schema_invalid")
    _verify_content_digest(
        selection,
        digest_field="selection_digest",
        error_code="material_selection_digest_invalid",
    )
    requirement_ids = _strings(selection.get("requirement_ids"))
    met = set(_strings(selection.get("met_requirement_ids")))
    unmet = set(_strings(selection.get("unmet_requirement_ids")))
    if (
        not requirement_ids
        or len(requirement_ids) != len(set(requirement_ids))
        or met.intersection(unmet)
        or met.union(unmet) != set(requirement_ids)
    ):
        raise EvidenceSetCoverageError("material_selection_requirement_state_invalid")
    selected = _strings(selection.get("selected_candidate_ids"))
    if len(selected) != len(set(selected)):
        raise EvidenceSetCoverageError("material_selection_candidate_identity_invalid")
    receipts = list(selection.get("requirement_receipts") or ())
    receipt_ids = [
        str(receipt.get("requirement_id") or "")
        for receipt in receipts
        if isinstance(receipt, Mapping)
    ]
    if set(receipt_ids) != set(requirement_ids) or len(receipt_ids) != len(
        requirement_ids
    ):
        raise EvidenceSetCoverageError("material_selection_receipts_invalid")


def evaluate_material_reference(
    *, selection: Mapping[str, Any], reference: Mapping[str, Any]
) -> dict[str, Any]:
    _validate_selection(selection)
    reference_schema = str(reference.get("schema_version") or "")
    selection_schema = str(selection.get("schema_version") or "")
    expected_reference_schema = (
        REFERENCE_SCHEMA_V1_1
        if selection_schema == SELECTION_SCHEMA_V1_1
        else REFERENCE_SCHEMA_V1_0
    )
    if reference_schema != expected_reference_schema:
        raise EvidenceSetCoverageError("material_reference_schema_invalid")
    if str(reference.get("request_id") or "") != str(
        selection.get("request_id") or ""
    ):
        raise EvidenceSetCoverageError("material_reference_request_mismatch")
    if str(reference.get("requirement_plan_digest") or "") != str(
        selection.get("requirement_plan_digest") or ""
    ):
        raise EvidenceSetCoverageError("material_reference_plan_mismatch")
    selected = set(_strings(selection.get("selected_candidate_ids")))
    requirement_ids = set(_strings(selection.get("requirement_ids")))
    runtime_complete_ids = set(_strings(selection.get("met_requirement_ids")))
    groups = list(reference.get("material_reference_groups") or ())
    if not groups:
        raise EvidenceSetCoverageError("material_reference_groups_empty")
    rows: list[dict[str, Any]] = []
    canonical_positive_ids: set[str] = set()
    reference_requirement_ids: list[str] = []
    for raw in groups:
        if not isinstance(raw, Mapping):
            raise EvidenceSetCoverageError("material_reference_group_invalid")
        requirement_id = str(raw.get("requirement_id") or "")
        alternatives = [
            set(_strings(value)) for value in raw.get("acceptable_candidate_sets") or ()
        ]
        canonical_ids = set(_strings(raw.get("canonical_positive_ids")))
        if (
            not requirement_id
            or not alternatives
            or any(not value for value in alternatives)
            or not canonical_ids
            or not canonical_ids.issubset(set().union(*alternatives))
        ):
            raise EvidenceSetCoverageError("material_reference_group_invalid")
        reference_requirement_ids.append(requirement_id)
        canonical_positive_ids.update(canonical_ids)
        satisfied_by = next(
            (sorted(value) for value in alternatives if value.issubset(selected)), None
        )
        runtime_complete = requirement_id in runtime_complete_ids
        rows.append(
            {
                "requirement_id": requirement_id,
                "runtime_requirement_complete": runtime_complete,
                "satisfied": runtime_complete and satisfied_by is not None,
                "satisfied_by_candidate_ids": satisfied_by or [],
            }
        )
    if (
        len(reference_requirement_ids) != len(set(reference_requirement_ids))
        or set(reference_requirement_ids) != requirement_ids
    ):
        raise EvidenceSetCoverageError("material_reference_requirement_mismatch")
    satisfied_count = sum(1 for row in rows if row["satisfied"])
    exact_recall = (
        len(canonical_positive_ids.intersection(selected)) / len(canonical_positive_ids)
        if canonical_positive_ids
        else None
    )
    result = {
        "schema_version": (
            "fin_ia_material_evidence_set_evaluation_v1_1"
            if selection_schema == SELECTION_SCHEMA_V1_1
            else "fin_ia_material_evidence_set_evaluation_v1_0"
        ),
        "request_id": reference["request_id"],
        "required_group_count": len(rows),
        "satisfied_group_count": satisfied_count,
        "required_group_coverage": satisfied_count / len(rows),
        "required_group_gate_pass": satisfied_count == len(rows),
        "exact_object_recall_diagnostic": exact_recall,
        "groups": rows,
        "candidate_is_not_evidence": True,
        "numeric_fact_authority": False,
        "s1_qualified": False,
    }
    result["evaluation_digest"] = canonical_digest(result)
    return result


__all__ = [
    "EvidenceSetCoverageError",
    "PLAN_SCHEMA_V1_0",
    "PLAN_SCHEMA_V1_1",
    "REFERENCE_SCHEMA_V1_0",
    "REFERENCE_SCHEMA_V1_1",
    "SELECTION_SCHEMA_V1_0",
    "SELECTION_SCHEMA_V1_1",
    "canonical_digest",
    "compile_requirement_plan",
    "evaluate_material_reference",
    "select_request_bound_review",
    "validate_requirement_plan",
]
