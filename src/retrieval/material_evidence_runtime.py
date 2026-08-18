from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

from .evidence_set_coverage import (
    PLAN_SCHEMA_V1_2,
    canonical_digest,
    compile_requirement_plan,
)
from .financial_intent import concept_aliases


POLICY_SCHEMA_V1_0 = "fin_ia_s1_material_evidence_runtime_policy_v1_0"
POLICY_SCHEMA_V1_1 = "fin_ia_s1_material_evidence_runtime_policy_v1_1"
POLICY_SCHEMAS = frozenset({POLICY_SCHEMA_V1_0, POLICY_SCHEMA_V1_1})
# Backward-compatible aliases remain bound to the historical schemas.  New
# callers should use the versioned names instead of relabelling old receipts.
POLICY_SCHEMA = POLICY_SCHEMA_V1_0
CANDIDATE_SCHEMA = "fin_ia_material_candidate_metadata_v1_1"
COMPILER_RECEIPT_SCHEMA_V1_1 = "fin_ia_material_requirement_compiler_receipt_v1_1"
COMPILER_RECEIPT_SCHEMA_V1_2 = "fin_ia_material_requirement_compiler_receipt_v1_2"
COMPILER_RECEIPT_SCHEMA = COMPILER_RECEIPT_SCHEMA_V1_1


class MaterialEvidenceRuntimeError(ValueError):
    """A request or candidate cannot be projected without weakening meaning."""


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            output.append(value)
    return tuple(output)


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _is_period_only_intent(value: str) -> bool:
    normalized = _normalize(value)
    if not normalized:
        return False
    tokens = normalized.split()
    temporal = {
        "compare",
        "compared",
        "comparison",
        "fiscal",
        "fy",
        "period",
        "to",
        "versus",
        "vs",
        "year",
        "yoy",
    }
    return all(
        token in temporal
        or token.isdigit()
        or bool(re.fullmatch(r"fy\d{4}", token))
        for token in tokens
    ) and any(
        token.isdigit() or re.fullmatch(r"fy\d{4}", token) for token in tokens
    )


def _validate_policy(policy: Mapping[str, Any]) -> None:
    schema_version = str(policy.get("schema_version") or "")
    if schema_version not in POLICY_SCHEMAS:
        raise MaterialEvidenceRuntimeError("material_runtime_policy_schema_invalid")
    authority = policy.get("authority")
    if not (
        isinstance(authority, Mapping)
        and authority.get("provider_neutral") is True
        and authority.get("candidate_is_not_evidence") is True
        and authority.get("numeric_fact_authority") is False
        and authority.get("qrel_or_reference_visible") is False
        and authority.get("generation_model_calls") == 0
    ):
        raise MaterialEvidenceRuntimeError("material_runtime_policy_authority_invalid")
    review_k = policy.get("review_k")
    if not isinstance(review_k, int) or review_k <= 0:
        raise MaterialEvidenceRuntimeError("material_runtime_policy_review_k_invalid")
    role_map = policy.get("evidence_role_to_material_roles")
    facet_roles = policy.get("facet_required_roles")
    axis_contract = policy.get("material_intent_axis_contract")
    role_axis_contract = policy.get("material_role_axis_contract")
    if (
        not isinstance(role_map, Mapping)
        or not isinstance(facet_roles, Mapping)
        or not isinstance(axis_contract, Mapping)
        or not isinstance(role_axis_contract, Mapping)
    ):
        raise MaterialEvidenceRuntimeError("material_runtime_policy_role_map_invalid")
    hard = set(_strings(axis_contract.get("hard_product_concept_ids")))
    contextual = set(_strings(axis_contract.get("contextual_topic_concept_ids")))
    if (
        not hard
        or hard.intersection(contextual)
        or axis_contract.get("fallback_collective_axis_coverage") is not True
        or axis_contract.get("unmapped_product_intent_mode")
        != "context_only_and_require_explicit_blueprint_for_hard_scope"
    ):
        raise MaterialEvidenceRuntimeError("material_runtime_policy_axis_invalid")
    if schema_version == POLICY_SCHEMA_V1_1:
        decomposition = axis_contract.get("proposition_decomposition")
        if not (
            isinstance(decomposition, Mapping)
            and decomposition.get("fallback_non_temporal_mode")
            == "one_product_axis_per_role"
            and isinstance(
                decomposition.get("facet_promoted_contextual_concept_ids"),
                Mapping,
            )
        ):
            raise MaterialEvidenceRuntimeError(
                "material_runtime_policy_proposition_decomposition_invalid"
            )
        promoted_by_facet = decomposition[
            "facet_promoted_contextual_concept_ids"
        ]
        for facet_id, concept_ids in promoted_by_facet.items():
            concepts = set(_strings(concept_ids))
            if (
                facet_id not in facet_roles
                or not concepts
                or not concepts.issubset(contextual)
            ):
                raise MaterialEvidenceRuntimeError(
                    "material_runtime_policy_promoted_contextual_axis_invalid:"
                    f"{facet_id}"
                )
    if set(role_axis_contract) != {"direct", "bridge", "context", "counter"}:
        raise MaterialEvidenceRuntimeError("material_runtime_policy_role_axis_invalid")
    for role, row in role_axis_contract.items():
        if not (
            isinstance(row, Mapping)
            and isinstance(row.get("bind_requested_metrics"), bool)
            and row.get("bind_hard_product_intents") is True
        ):
            raise MaterialEvidenceRuntimeError(
                f"material_runtime_policy_role_axis_invalid:{role}"
            )


def _concept_id(
    value: str, *, family: str, ontology: Mapping[str, Any]
) -> str:
    return concept_aliases(value, family=family, ontology=ontology)[0]


def _align_to_request(
    values: Sequence[str],
    *,
    request_values: Sequence[str],
    family: str,
    ontology: Mapping[str, Any],
) -> tuple[str, ...]:
    """Return request spellings for blueprint concepts without inventing scope."""

    output: list[str] = []
    for value in values:
        exact = [
            request_value
            for request_value in request_values
            if _normalize(request_value) == _normalize(value)
        ]
        if len(exact) == 1:
            output.append(exact[0])
            continue
        concept = _concept_id(value, family=family, ontology=ontology)
        matches = [
            request_value
            for request_value in request_values
            if _concept_id(request_value, family=family, ontology=ontology)
            == concept
        ]
        if len(matches) != 1:
            raise MaterialEvidenceRuntimeError(
                f"material_requirement_intent_outside_or_ambiguous:{family}:{value}"
            )
        output.append(matches[0])
    return _unique(tuple(output))


def _classify_product_intents(
    values: Sequence[str],
    *,
    policy: Mapping[str, Any],
    ontology: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    contract = policy["material_intent_axis_contract"]
    hard_concepts = set(_strings(contract.get("hard_product_concept_ids")))
    contextual_concepts = set(
        _strings(contract.get("contextual_topic_concept_ids"))
    )
    hard: list[str] = []
    contextual: list[str] = []
    unclassified: list[str] = []
    for value in values:
        concept = _concept_id(
            value, family="product_concepts", ontology=ontology
        )
        if concept in hard_concepts:
            hard.append(value)
        elif concept in contextual_concepts:
            contextual.append(value)
        else:
            unclassified.append(value)
    return _unique(hard), _unique(contextual), _unique(unclassified)


def _atomic_proposition_policy(policy: Mapping[str, Any]) -> bool:
    return str(policy.get("schema_version") or "") == POLICY_SCHEMA_V1_1


def _facet_material_product_intents(
    values: Sequence[str],
    *,
    facet_id: str,
    policy: Mapping[str, Any],
    ontology: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return hard request spellings plus facet-promoted material propositions.

    A topic can remain contextual for most research facets yet become a material
    proposition for a facet whose business meaning requires it.  For example,
    an executed customer commitment is material to orders/durability but should
    not become a universal hard product axis for every financial query.
    """

    hard, contextual, _ = _classify_product_intents(
        values,
        policy=policy,
        ontology=ontology,
    )
    if not _atomic_proposition_policy(policy):
        return hard, ()
    contract = policy["material_intent_axis_contract"][
        "proposition_decomposition"
    ]
    promoted_concepts = set(
        _strings(
            contract["facet_promoted_contextual_concept_ids"].get(facet_id)
        )
    )
    promoted = tuple(
        value
        for value in contextual
        if _concept_id(
            value,
            family="product_concepts",
            ontology=ontology,
        )
        in promoted_concepts
    )
    return _unique((*hard, *promoted)), _unique(promoted)


def _non_temporal_product_axes(
    values: Sequence[str], *, policy: Mapping[str, Any]
) -> tuple[tuple[str, ...], ...]:
    unique = _unique(values)
    if not unique:
        return ((),)
    if _atomic_proposition_policy(policy):
        return tuple((value,) for value in unique)
    return (unique,)


def _requirement_id(group: Mapping[str, Any]) -> str:
    identity = {
        key: value
        for key, value in group.items()
        if key not in {"requirement_id", "priority"}
    }
    return f"MER::{canonical_digest(identity)[:20]}"


def _blueprint_requirements(runtime_input: Mapping[str, Any]) -> list[dict[str, Any]]:
    for container_key in ("research_blueprint", "material_requirement_blueprint"):
        container = runtime_input.get(container_key)
        if isinstance(container, Mapping):
            rows = container.get("material_requirements")
            if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)):
                return [dict(row) for row in rows if isinstance(row, Mapping)]
    return []


def compile_material_requirement_plan_from_runtime_input(
    *,
    runtime_input: Mapping[str, Any],
    policy: Mapping[str, Any],
    ontology: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compile a public request/blueprint into a v1.1 material-set plan.

    A natural ResearchBlueprint may submit explicit material requirements.  The
    deterministic fallback consumes the current narrative execution plan and
    fails closed when product scope is too broad for an atomic temporal group.
    Neither path sees candidates, qrels, references, URLs or ranking scores.
    """

    _validate_policy(policy)
    request = runtime_input.get("evidence_request")
    if not isinstance(request, Mapping):
        raise MaterialEvidenceRuntimeError("material_requirement_request_missing")
    request_facets = set(_strings(request.get("requested_facet_ids")))
    request_metrics = _strings(request.get("metric_intents"))
    request_products = _strings(request.get("product_intents"))
    request_entities = _strings(request.get("target_entities"))
    period = request.get("period") or {}
    if not isinstance(period, Mapping):
        raise MaterialEvidenceRuntimeError("material_requirement_period_invalid")
    years = tuple(sorted({int(value) for value in period.get("fiscal_years") or ()}))
    if not request_facets or not request_entities:
        raise MaterialEvidenceRuntimeError("material_requirement_request_scope_empty")

    explicit = _blueprint_requirements(runtime_input)
    compiler_mode = "explicit_research_blueprint"
    temporal_directives = tuple(
        value for value in request_products if _is_period_only_intent(value)
    )
    non_temporal_request_products = tuple(
        value for value in request_products if value not in temporal_directives
    )
    (
        hard_request_products,
        contextual_request_products,
        unclassified_request_products,
    ) = _classify_product_intents(
        non_temporal_request_products,
        policy=policy,
        ontology=ontology,
    )
    if explicit:
        requirements = explicit
    else:
        compiler_mode = "deterministic_narrative_plan_fallback"
        execution_plan = runtime_input.get("retrieval_execution_plan") or {}
        narratives = (
            execution_plan.get("narrative_requests")
            if isinstance(execution_plan, Mapping)
            else None
        )
        if not isinstance(narratives, Sequence) or isinstance(
            narratives, (str, bytes)
        ) or not narratives:
            narratives = [
                {
                    "facet_ids": sorted(request_facets),
                    "metric_context_ids": list(request_metrics),
                    "product_intents": list(request_products),
                }
            ]
        explicit_temporal = bool(temporal_directives and len(years) >= 2)
        requirements = []
        seen: set[str] = set()
        promoted_contextual_by_facet: dict[str, tuple[str, ...]] = {}
        for narrative in narratives:
            if not isinstance(narrative, Mapping):
                raise MaterialEvidenceRuntimeError(
                    "material_requirement_narrative_invalid"
                )
            facets = _strings(narrative.get("facet_ids"))
            if not facets or not set(facets).issubset(request_facets):
                raise MaterialEvidenceRuntimeError(
                    "material_requirement_narrative_facet_outside_request"
                )
            metric_values = _align_to_request(
                _strings(narrative.get("metric_context_ids")),
                request_values=request_metrics,
                family="metric_concepts",
                ontology=ontology,
            )
            narrative_products = tuple(
                value
                for value in _strings(narrative.get("product_intents"))
                if not _is_period_only_intent(value)
            )
            aligned_narrative_products = _align_to_request(
                narrative_products,
                request_values=non_temporal_request_products,
                family="product_concepts",
                ontology=ontology,
            ) if narrative_products else ()
            for facet_id in facets:
                if facet_id not in policy["facet_required_roles"]:
                    raise MaterialEvidenceRuntimeError(
                        f"material_requirement_facet_policy_missing:{facet_id}"
                    )
                roles = _strings(policy["facet_required_roles"][facet_id])
                if not roles:
                    raise MaterialEvidenceRuntimeError(
                        f"material_requirement_facet_roles_empty:{facet_id}"
                    )
                product_values, promoted_contextual = (
                    _facet_material_product_intents(
                        aligned_narrative_products,
                        facet_id=facet_id,
                        policy=policy,
                        ontology=ontology,
                    )
                )
                if promoted_contextual:
                    promoted_contextual_by_facet[facet_id] = _unique(
                        (
                            *promoted_contextual_by_facet.get(facet_id, ()),
                            *promoted_contextual,
                        )
                    )
                if explicit_temporal:
                    if not metric_values:
                        raise MaterialEvidenceRuntimeError(
                            "material_requirement_temporal_metric_missing"
                        )
                    if len(product_values) > 1:
                        raise MaterialEvidenceRuntimeError(
                            "material_requirement_temporal_product_scope_requires_blueprint"
                        )
                    for metric in metric_values:
                        for role in roles:
                            role_axis = policy["material_role_axis_contract"][role]
                            temporal_axis = bool(
                                role_axis["bind_requested_metrics"]
                            )
                            group = {
                                "facet_id": facet_id,
                                "role": role,
                                "metric_ids": (
                                    [metric]
                                    if role_axis["bind_requested_metrics"]
                                    else []
                                ),
                                "product_ids": (
                                    list(product_values)
                                    if role_axis["bind_hard_product_intents"]
                                    else []
                                ),
                                "target_entities": list(request_entities),
                                "period_mode": (
                                    "all_periods_same_basis"
                                    if temporal_axis
                                    else "any"
                                ),
                                "fiscal_years": (
                                    list(years) if temporal_axis else []
                                ),
                                "minimum_candidates": 1,
                                "coverage_mode": (
                                    "single_binding"
                                    if temporal_axis
                                    else "collective_axes"
                                ),
                            }
                            signature = canonical_digest(group)
                            if signature not in seen:
                                seen.add(signature)
                                requirements.append(group)
                else:
                    for product_axis in _non_temporal_product_axes(
                        product_values,
                        policy=policy,
                    ):
                        for role in roles:
                            role_axis = policy["material_role_axis_contract"][role]
                            group = {
                                "facet_id": facet_id,
                                "role": role,
                                "metric_ids": (
                                    list(metric_values)
                                    if role_axis["bind_requested_metrics"]
                                    else []
                                ),
                                "product_ids": (
                                    list(product_axis)
                                    if role_axis["bind_hard_product_intents"]
                                    else []
                                ),
                                "target_entities": list(request_entities),
                                "period_mode": "any",
                                "fiscal_years": [],
                                "minimum_candidates": 1,
                                "coverage_mode": "collective_axes",
                            }
                            signature = canonical_digest(group)
                            if signature not in seen:
                                seen.add(signature)
                                requirements.append(group)

    if explicit:
        promoted_contextual_by_facet = {}

    normalized_requirements: list[dict[str, Any]] = []
    for priority, raw in enumerate(requirements, 1):
        group = dict(raw)
        group.setdefault("priority", priority)
        group.setdefault(
            "coverage_mode",
            "single_binding"
            if group.get("period_mode") == "all_periods_same_basis"
            else "collective_axes",
        )
        group.setdefault(
            "metric_coverage_mode",
            "all_of"
            if group.get("period_mode") == "all_periods_same_basis"
            else "retrieval_context_only",
        )
        group.setdefault("product_coverage_mode", "all_of")
        group.setdefault("requirement_id", _requirement_id(group))
        normalized_requirements.append(group)
    plan = compile_requirement_plan(
        evidence_request=request,
        material_requirements=normalized_requirements,
        review_k=int(policy["review_k"]),
        schema_version=PLAN_SCHEMA_V1_2,
    )
    receipt = {
        "schema_version": (
            COMPILER_RECEIPT_SCHEMA_V1_2
            if _atomic_proposition_policy(policy)
            else COMPILER_RECEIPT_SCHEMA_V1_1
        ),
        "request_id": request.get("request_id"),
        "compiler_mode": compiler_mode,
        "temporal_directives_excluded_from_product_scope": list(
            temporal_directives
        ),
        "hard_product_intents": list(hard_request_products),
        "contextual_product_intents_excluded_from_hard_material_scope": list(
            contextual_request_products
        ),
        "unclassified_product_intents_excluded_from_hard_material_scope": list(
            unclassified_request_products
        ),
        "explicit_blueprint_required_for_full_product_scope": bool(
            compiler_mode == "deterministic_narrative_plan_fallback"
            and unclassified_request_products
        ),
        "requirement_group_count": len(plan["requirement_groups"]),
        "maximum_reserved_capacity": plan["maximum_reserved_capacity"],
        "review_k": plan["review_k"],
        "metric_authority_boundary": (
            "non_temporal_metric_intents_guide_retrieval_but_do_not_duplicate_"
            "S2_NumericFact_completeness"
        ),
        "product_axis_default": (
            "one_product_proposition_per_role_collective_within_axis"
            if _atomic_proposition_policy(policy)
            else "all_of_with_explicit_reserved_capacity"
        ),
        "candidate_or_reference_inputs_read": False,
        "generation_model_calls": 0,
        "plan_digest": plan["plan_digest"],
    }
    if _atomic_proposition_policy(policy):
        receipt["promoted_contextual_intents_by_facet"] = {
            facet_id: list(values)
            for facet_id, values in sorted(
                promoted_contextual_by_facet.items()
            )
        }
    receipt["receipt_digest"] = canonical_digest(receipt)
    return plan, receipt


def _need_intents(
    best_need: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
    ontology: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    kind = str(best_need.get("need_kind") or "")
    terms = _strings(best_need.get("intent_terms"))
    metrics: tuple[str, ...] = ()
    products: tuple[str, ...] = ()
    if kind == "metric_product":
        metrics, products = terms[:1], terms[1:2]
    elif kind == "metric":
        metrics = terms
    elif kind == "product":
        products = terms
    elif kind == "exact_phrase" and terms:
        metric_concept = _concept_id(
            terms[0], family="metric_concepts", ontology=ontology
        )
        request_metric_concepts = {
            _concept_id(value, family="metric_concepts", ontology=ontology)
            for value in _strings(request.get("metric_intents"))
        }
        if metric_concept in request_metric_concepts:
            metrics = terms[:1]
        else:
            product_concept = _concept_id(
                terms[0], family="product_concepts", ontology=ontology
            )
            request_product_concepts = {
                _concept_id(value, family="product_concepts", ontology=ontology)
                for value in _strings(request.get("product_intents"))
                if not _is_period_only_intent(value)
            }
            if product_concept in request_product_concepts:
                products = terms[:1]
    return metrics, products


def _candidate_years(
    object_row: Mapping[str, Any], *, request: Mapping[str, Any]
) -> tuple[int, ...]:
    base = object_row.get("base_object_view") or {}
    projection = object_row.get("structured_projection") or {}
    surfaces: list[str] = [str(object_row.get("model_text") or "")]
    if isinstance(projection, Mapping):
        for key in ("period_hints", "header_lines"):
            surfaces.extend(_strings(projection.get(key)))
    found = {
        int(value)
        for surface in surfaces
        for value in re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", surface)
    }
    fiscal_year = base.get("fiscal_year") if isinstance(base, Mapping) else None
    if fiscal_year not in (None, ""):
        found.add(int(fiscal_year))
    request_period = request.get("period") or {}
    requested = {
        int(value)
        for value in (
            request_period.get("fiscal_years") or ()
            if isinstance(request_period, Mapping)
            else ()
        )
    }
    return tuple(sorted(found.intersection(requested) if requested else found))


def _basis_key(
    *,
    case_key: str,
    entity: str,
    metric_ids: Sequence[str],
    product_ids: Sequence[str],
    request: Mapping[str, Any],
    object_row: Mapping[str, Any],
    accounting_basis: str,
) -> str:
    if len(metric_ids) != 1:
        return ""
    base = object_row.get("base_object_view") or {}
    source_type = str(base.get("source_type") or "") if isinstance(base, Mapping) else ""
    cadence = (
        "annual"
        if source_type in {"10-K", "20-F", "annual_report"}
        else "quarterly"
        if source_type in {"10-Q", "6-K"}
        else "event_or_unknown"
    )
    payload = {
        "case_key": case_key,
        "entity": entity,
        "metric_id": metric_ids[0],
        "product_id": product_ids[0] if len(product_ids) == 1 else None,
        "accounting_basis": accounting_basis,
        "requested_unit": str(request.get("unit") or ""),
        "source_type": source_type,
        "cadence": cadence,
        "candidate_comparability_only": True,
        "numeric_relation_authority": False,
    }
    return f"BASIS::{canonical_digest(payload)[:24]}"


def adapt_material_candidate_from_feature_views(
    *,
    case_key: str,
    candidate_row: Mapping[str, Any],
    object_row: Mapping[str, Any],
    feature_views: Sequence[Mapping[str, Any]],
    evidence_request: Mapping[str, Any],
    accounting_basis: str,
    policy: Mapping[str, Any],
    ontology: Mapping[str, Any],
) -> dict[str, Any]:
    """Project current shortlist features into correlated material bindings."""

    _validate_policy(policy)
    object_id = str(candidate_row.get("compiled_object_id") or "")
    if not object_id or object_id != str(object_row.get("compiled_object_id") or ""):
        raise MaterialEvidenceRuntimeError("material_candidate_object_join_invalid")
    try:
        base_rank = int(candidate_row.get("rank") or candidate_row.get("base_rank"))
        score = float(candidate_row.get("score") or 0.0)
    except (TypeError, ValueError) as exc:
        raise MaterialEvidenceRuntimeError("material_candidate_rank_invalid") from exc
    if base_rank <= 0:
        raise MaterialEvidenceRuntimeError("material_candidate_rank_invalid")
    base = object_row.get("base_object_view") or {}
    if not isinstance(base, Mapping):
        raise MaterialEvidenceRuntimeError("material_candidate_base_object_invalid")
    entity = str(base.get("ticker") or "")
    if not entity:
        raise MaterialEvidenceRuntimeError("material_candidate_entity_missing")
    years = _candidate_years(object_row, request=evidence_request)
    bindings: list[dict[str, Any]] = []
    seen: set[str] = set()
    role_map = policy["evidence_role_to_material_roles"]
    request_metrics = _strings(evidence_request.get("metric_intents"))
    request_products = tuple(
        value
        for value in _strings(evidence_request.get("product_intents"))
        if not _is_period_only_intent(value)
    )
    for view in feature_views:
        if not isinstance(view, Mapping):
            continue
        facet_id = str(view.get("facet_id") or "")
        feature = view.get("feature") if isinstance(view.get("feature"), Mapping) else view
        if str(feature.get("compiled_object_id") or "") != object_id:
            raise MaterialEvidenceRuntimeError(
                "material_candidate_feature_object_join_invalid"
            )
        role = feature.get("evidence_role") or {}
        intent = feature.get("financial_intent") or {}
        best_need = feature.get("best_retrieval_need") or {}
        if not facet_id or str(role.get("compatibility") or "") != "compatible":
            continue
        facet_material_products, _ = _facet_material_product_intents(
            request_products,
            facet_id=facet_id,
            policy=policy,
            ontology=ontology,
        )
        raw_metrics, raw_products = _need_intents(
            best_need, request=evidence_request, ontology=ontology
        )
        metric_ids = (
            _align_to_request(
                raw_metrics,
                request_values=request_metrics,
                family="metric_concepts",
                ontology=ontology,
            )
            if raw_metrics
            and str(intent.get("metric_compatibility") or "") == "compatible"
            else ()
        )
        aligned_raw_products = (
            _align_to_request(
                raw_products,
                request_values=request_products,
                family="product_concepts",
                ontology=ontology,
            )
            if raw_products
            else ()
        )
        material_raw_products = tuple(
            value
            for value in aligned_raw_products
            if value in facet_material_products
        )
        metric_axis_compatible = (
            not raw_metrics
            or str(intent.get("metric_compatibility") or "") == "compatible"
        )
        product_axis_compatible = (
            not material_raw_products
            or str(intent.get("product_compatibility") or "") == "compatible"
        )
        product_ids = material_raw_products
        material_roles = _unique(
            tuple(
                material_role
                for label in _strings(role.get("labels"))
                for material_role in _strings(role_map.get(label))
            )
        )
        for material_role in material_roles:
            role_axis = policy["material_role_axis_contract"][material_role]
            if (
                role_axis["bind_requested_metrics"]
                and not metric_axis_compatible
            ) or (
                role_axis["bind_hard_product_intents"]
                and not product_axis_compatible
            ):
                continue
            role_metric_ids = (
                metric_ids if role_axis["bind_requested_metrics"] else ()
            )
            role_product_ids = (
                product_ids
                if role_axis["bind_hard_product_intents"]
                else ()
            )
            binding = {
                "facet_id": facet_id,
                "role": material_role,
                "metric_ids": list(role_metric_ids),
                "product_ids": list(role_product_ids),
                "fiscal_years": list(years),
                "same_basis_key": _basis_key(
                    case_key=case_key,
                    entity=entity,
                    metric_ids=role_metric_ids,
                    product_ids=role_product_ids,
                    request=evidence_request,
                    object_row=object_row,
                    accounting_basis=accounting_basis,
                ),
                "evidence_role_labels": list(_strings(role.get("labels"))),
                "financial_intent_compatibility": str(
                    intent.get("compatibility") or ""
                ),
                "candidate_comparability_only": True,
                "numeric_relation_authority": False,
                "contextual_or_unclassified_need_product_intents": [
                    value
                    for value in aligned_raw_products
                    if value not in material_raw_products
                ],
            }
            signature = canonical_digest(binding)
            if signature not in seen:
                seen.add(signature)
                bindings.append(binding)
    bindings.sort(
        key=lambda value: (
            value["facet_id"],
            value["role"],
            tuple(value["metric_ids"]),
            tuple(value["product_ids"]),
            value["same_basis_key"],
        )
    )
    result = {
        "schema_version": CANDIDATE_SCHEMA,
        "compiled_object_id": object_id,
        "base_rank": base_rank,
        "score": score,
        "case_key": case_key,
        "target_entities": [entity],
        "object_kind": str(object_row.get("object_kind") or ""),
        "source_type": str(base.get("source_type") or ""),
        "publication_date": str(base.get("publication_date") or ""),
        "material_bindings": bindings,
        "facet_ids": sorted({value["facet_id"] for value in bindings}),
        "roles": sorted({value["role"] for value in bindings}),
        "metric_ids": sorted(
            {item for value in bindings for item in value["metric_ids"]}
        ),
        "product_ids": sorted(
            {item for value in bindings for item in value["product_ids"]}
        ),
        "fiscal_years": list(years),
        "candidate_is_not_evidence": True,
        "numeric_fact_authority": False,
    }
    result["metadata_digest"] = canonical_digest(result)
    return result


__all__ = [
    "CANDIDATE_SCHEMA",
    "COMPILER_RECEIPT_SCHEMA",
    "COMPILER_RECEIPT_SCHEMA_V1_1",
    "COMPILER_RECEIPT_SCHEMA_V1_2",
    "MaterialEvidenceRuntimeError",
    "POLICY_SCHEMA",
    "POLICY_SCHEMA_V1_0",
    "POLICY_SCHEMA_V1_1",
    "adapt_material_candidate_from_feature_views",
    "compile_material_requirement_plan_from_runtime_input",
]
