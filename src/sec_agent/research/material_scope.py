from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import re
from typing import Any

from retrieval.contracts import EvidenceRequest
from retrieval.evidence_set_coverage import canonical_digest
from retrieval.financial_intent import concept_aliases


MATERIAL_SCOPE_POLICY_SCHEMA = "fin_ia_research_material_scope_policy_v1_0"
MATERIAL_SCOPE_OUTPUT_SCHEMA = "fin_ia_research_material_scope_atoms_v1_0"
MATERIAL_SCOPE_COMPILATION_SCHEMA = (
    "fin_ia_research_material_scope_compilation_v1_0"
)

_DISPOSITIONS = frozenset(
    {"hard_material_axis", "contextual_retrieval_only", "temporal_directive"}
)
_PERIOD_MODES = frozenset({"any", "all_periods_same_basis"})
_COVERAGE_MODES = frozenset({"single_binding", "collective_axes"})
_MATERIAL_ROLES = frozenset({"direct", "bridge", "context", "counter"})


class ResearchMaterialScopeError(ValueError):
    """A natural scope proposal weakened or expanded its EvidenceRequest."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ResearchMaterialScopeError(code)


def _indices(value: Any, *, upper_bound: int, code: str) -> tuple[int, ...]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes)),
        code,
    )
    output: list[int] = []
    for raw in value:
        _require(isinstance(raw, int) and not isinstance(raw, bool), code)
        _require(0 <= raw < upper_bound, code)
        _require(raw not in output, code)
        output.append(raw)
    _require(output == sorted(output), code)
    return tuple(output)


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _is_period_only_product_intent(value: str) -> bool:
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
        token.isdigit() or re.fullmatch(r"fy\d{4}", token)
        for token in tokens
    )


def _fixed_product_disposition(
    value: str,
    *,
    material_runtime_policy: Mapping[str, Any],
    intent_ontology: Mapping[str, Any],
) -> str | None:
    if _is_period_only_product_intent(value):
        return "temporal_directive"
    concept_id = concept_aliases(
        value,
        family="product_concepts",
        ontology=intent_ontology,
    )[0]
    axis = material_runtime_policy["material_intent_axis_contract"]
    if concept_id in set(axis["hard_product_concept_ids"]):
        return "hard_material_axis"
    if concept_id in set(axis["contextual_topic_concept_ids"]):
        return "contextual_retrieval_only"
    return None


def validate_material_scope_policy(
    policy: Mapping[str, Any], material_runtime_policy: Mapping[str, Any]
) -> None:
    _require(
        policy.get("schema_version") == MATERIAL_SCOPE_POLICY_SCHEMA,
        "research_material_scope_policy_schema_invalid",
    )
    _require(
        set(policy)
        == {
            "schema_version",
            "status",
            "maximum_scope_atoms_per_request",
            "allowed_intent_dispositions",
            "allowed_period_modes",
            "allowed_coverage_modes",
            "authority",
            "token_budget_basis",
            "known_boundary",
        },
        "research_material_scope_policy_fields_invalid",
    )
    _require(
        policy.get("status")
        == "provider_neutral_request_visible_material_scope_control_plane",
        "research_material_scope_policy_status_invalid",
    )
    maximum = policy.get("maximum_scope_atoms_per_request")
    _require(
        isinstance(maximum, int) and 1 <= maximum <= 64,
        "research_material_scope_policy_budget_invalid",
    )
    _require(
        set(policy.get("allowed_intent_dispositions") or ()) == _DISPOSITIONS
        and set(policy.get("allowed_period_modes") or ()) == _PERIOD_MODES
        and set(policy.get("allowed_coverage_modes") or ()) == _COVERAGE_MODES,
        "research_material_scope_policy_enum_invalid",
    )
    authority = policy.get("authority")
    _require(
        isinstance(authority, Mapping)
        and authority.get("model_selects_request_visible_indices_only") is True
        and authority.get("harness_owns_identity_dates_sources_roles_ids_and_capacity")
        is True
        and authority.get("candidate_qrel_reference_or_url_visible") is False
        and authority.get("candidate_is_not_evidence") is True
        and authority.get("numeric_authority") is False,
        "research_material_scope_policy_authority_invalid",
    )
    budget_basis = policy.get("token_budget_basis")
    _require(
        isinstance(budget_basis, Mapping)
        and set(budget_basis)
        == {
            "node_purpose",
            "input_scale",
            "required_outputs",
            "schema_burden",
            "materiality_and_quality_risk",
            "comparable_run_evidence",
            "reasoning_profile",
            "stop_and_truncation",
        }
        and all(budget_basis.get(key) for key in budget_basis),
        "research_material_scope_token_budget_basis_invalid",
    )
    facet_roles = material_runtime_policy.get("facet_required_roles")
    role_axes = material_runtime_policy.get("material_role_axis_contract")
    _require(
        isinstance(facet_roles, Mapping)
        and isinstance(role_axes, Mapping)
        and set(role_axes) == _MATERIAL_ROLES,
        "research_material_scope_runtime_policy_invalid",
    )


def _request_public_view(
    request: EvidenceRequest,
    *,
    material_runtime_policy: Mapping[str, Any],
    intent_ontology: Mapping[str, Any],
) -> dict[str, Any]:
    facet_id = request.requested_facet_ids[0]
    roles = list(
        material_runtime_policy.get("facet_required_roles", {}).get(facet_id) or ()
    )
    _require(bool(roles), f"research_material_scope_facet_roles_missing:{facet_id}")
    return {
        "request_id": request.request_id,
        "facet_id": facet_id,
        "metric_intents": [
            {"index": index, "value": value}
            for index, value in enumerate(request.metric_intents)
        ],
        "product_intents": [
            {
                "index": index,
                "value": value,
                "deterministic_temporal_directive": (
                    _is_period_only_product_intent(value)
                ),
                "fixed_disposition": _fixed_product_disposition(
                    value,
                    material_runtime_policy=material_runtime_policy,
                    intent_ontology=intent_ontology,
                ),
            }
            for index, value in enumerate(request.product_intents)
        ],
        "fiscal_years": list(request.period.fiscal_years),
        "required_material_roles": roles,
        "role_axis_contract": {
            role: dict(material_runtime_policy["material_role_axis_contract"][role])
            for role in roles
        },
    }


def _model_visible_output_contract(
    *,
    research_plan_digest: str,
    required_request_ids: Sequence[str],
    requests: Sequence[EvidenceRequest],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile the model contract from the same vocabulary the validator uses."""

    facets = sorted({request.requested_facet_ids[0] for request in requests})
    # Per-request role membership is exposed in each request view; the schema
    # carries the validator's provider-neutral closed role vocabulary.
    roles = sorted(_MATERIAL_ROLES)
    disposition_values = list(policy["allowed_intent_dispositions"])
    period_values = list(policy["allowed_period_modes"])
    coverage_values = list(policy["allowed_coverage_modes"])
    return {
        "top_level_fields_exact": [
            "schema_version",
            "research_plan_digest",
            "request_scopes",
        ],
        "schema_version": MATERIAL_SCOPE_OUTPUT_SCHEMA,
        "research_plan_digest": research_plan_digest,
        "json_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "schema_version",
                "research_plan_digest",
                "request_scopes",
            ],
            "properties": {
                "schema_version": {"const": MATERIAL_SCOPE_OUTPUT_SCHEMA},
                "research_plan_digest": {"const": research_plan_digest},
                "request_scopes": {
                    "type": "array",
                    "minItems": len(required_request_ids),
                    "maxItems": len(required_request_ids),
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "request_id",
                            "product_intent_dispositions",
                            "requirement_atoms",
                        ],
                        "properties": {
                            "request_id": {
                                "enum": list(required_request_ids),
                            },
                            "product_intent_dispositions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": [
                                        "product_intent_index",
                                        "disposition",
                                    ],
                                    "properties": {
                                        "product_intent_index": {
                                            "type": "integer",
                                            "minimum": 0,
                                        },
                                        "disposition": {
                                            "enum": disposition_values,
                                        },
                                    },
                                },
                            },
                            "requirement_atoms": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": policy[
                                    "maximum_scope_atoms_per_request"
                                ],
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": [
                                        "facet_id",
                                        "role",
                                        "metric_intent_indices",
                                        "product_intent_indices",
                                        "period_mode",
                                        "coverage_mode",
                                    ],
                                    "properties": {
                                        "facet_id": {"enum": facets},
                                        "role": {"enum": roles},
                                        "metric_intent_indices": {
                                            "type": "array",
                                            "items": {"type": "integer", "minimum": 0},
                                        },
                                        "product_intent_indices": {
                                            "type": "array",
                                            "items": {"type": "integer", "minimum": 0},
                                        },
                                        "period_mode": {"enum": period_values},
                                        "coverage_mode": {"enum": coverage_values},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "enum_semantics": {
            "hard_material_axis": (
                "The Evidence must explicitly bind this product intent; only "
                "indices with this disposition may appear in material atoms."
            ),
            "contextual_retrieval_only": (
                "The intent may guide retrieval context but must not be required "
                "as an explicit Evidence binding."
            ),
            "temporal_directive": (
                "Use only when deterministic_temporal_directive is true."
            ),
            "any": (
                "No same-basis multi-period bundle is required; use "
                "coverage_mode collective_axes."
            ),
            "all_periods_same_basis": (
                "Require the same metric across all listed fiscal years; use "
                "coverage_mode single_binding with exactly one metric index and "
                "at most one product index per atom."
            ),
            "collective_axes": (
                "Several candidates may collectively cover the selected axes."
            ),
            "single_binding": (
                "One correlated metric/product binding defines the temporal group."
            ),
        },
        "cross_field_rules": [
            "Use the exact key request_scopes (plural), never request_scope.",
            "Return every required request_id exactly once and no other request_id.",
            "Classify every product_intent_index exactly once; preserve any non-null fixed_disposition.",
            "Use the request's exact facet_id and only its required_material_roles.",
            "All index arrays must be sorted, unique and within that request's visible indices.",
            "Only hard_material_axis product indices may appear in requirement atoms.",
            "For each role with bind_requested_metrics=true, collectively cover every metric index; otherwise metric_intent_indices must be empty.",
            "For each role with bind_hard_product_intents=true, collectively cover every hard_material_axis product index; otherwise product_intent_indices must be empty.",
            "period_mode any requires coverage_mode collective_axes.",
            "period_mode all_periods_same_basis requires at least two fiscal years, coverage_mode single_binding, exactly one metric index and at most one product index.",
            "Do not paraphrase field names or enum values and do not add any field.",
        ],
        "maximum_scope_atoms_per_request": policy[
            "maximum_scope_atoms_per_request"
        ],
    }


def compile_research_material_scope_messages(
    *,
    research_plan_digest: str,
    requests: Sequence[EvidenceRequest],
    required_request_ids: Sequence[str],
    policy: Mapping[str, Any],
    material_runtime_policy: Mapping[str, Any],
    intent_ontology: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    """Build a candidate-blind prompt for only the requests needing natural scope."""

    validate_material_scope_policy(policy, material_runtime_policy)
    request_by_id = {request.request_id: request for request in requests}
    required = tuple(dict.fromkeys(str(value) for value in required_request_ids))
    _require(bool(required), "research_material_scope_required_requests_empty")
    _require(
        len(required) == len(tuple(required_request_ids))
        and set(required).issubset(request_by_id),
        "research_material_scope_required_requests_invalid",
    )
    visible = {
        "research_plan_digest": research_plan_digest,
        "purpose": (
            "Classify request-visible intent surfaces and select bounded material "
            "scope atoms. Do not invent aliases, facts, entities, sources, URLs, "
            "candidate IDs, object IDs, qrels or reference identities."
        ),
        "requests": [
            _request_public_view(
                request_by_id[request_id],
                material_runtime_policy=material_runtime_policy,
                intent_ontology=intent_ontology,
            )
            for request_id in required
        ],
        "output_contract": _model_visible_output_contract(
            research_plan_digest=research_plan_digest,
            required_request_ids=required,
            requests=[request_by_id[request_id] for request_id in required],
            policy=policy,
        ),
        "authority": dict(policy["authority"]),
        "token_budget_basis": dict(policy["token_budget_basis"]),
    }
    system = {
        "role": "system",
        "content": (
            "You are a financial-research material-scope planner. Return one exact "
            "JSON object matching the supplied contract. You may only select indices "
            "and enums shown in the request. Every product intent must be classified. "
            "Every required material role must be covered. Use the exact top-level "
            "key request_scopes (plural), exact field names and exact enum values; "
            "never paraphrase them. Do not write analysis, citations, candidate "
            "identities, URLs or markdown."
        ),
    }
    return system, {
        "role": "user",
        "content": json.dumps(visible, ensure_ascii=False, sort_keys=True),
    }


def parse_research_material_scope_output(content: str) -> dict[str, Any]:
    stripped = str(content).strip()
    _require(
        stripped.startswith("{") and stripped.endswith("}"),
        "research_material_scope_output_not_exact_json",
    )
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ResearchMaterialScopeError(
            "research_material_scope_output_json_invalid"
        ) from exc
    _require(
        isinstance(value, dict), "research_material_scope_output_shape_invalid"
    )
    return value


def _expand_atom(
    *,
    atom: Mapping[str, Any],
    request: EvidenceRequest,
    hard_product_indices: set[int],
    role_axis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    metric_indices = _indices(
        atom.get("metric_intent_indices"),
        upper_bound=len(request.metric_intents),
        code="research_material_scope_metric_indices_invalid",
    )
    product_indices = _indices(
        atom.get("product_intent_indices"),
        upper_bound=len(request.product_intents),
        code="research_material_scope_product_indices_invalid",
    )
    _require(
        set(product_indices).issubset(hard_product_indices),
        "research_material_scope_non_hard_product_bound",
    )
    bind_metrics = bool(role_axis.get("bind_requested_metrics"))
    bind_products = bool(role_axis.get("bind_hard_product_intents"))
    _require(
        bind_metrics or not metric_indices,
        "research_material_scope_role_metric_axis_forbidden",
    )
    _require(
        bind_products or not product_indices,
        "research_material_scope_role_product_axis_forbidden",
    )
    period_mode = str(atom.get("period_mode") or "")
    coverage_mode = str(atom.get("coverage_mode") or "")
    _require(
        period_mode in _PERIOD_MODES and coverage_mode in _COVERAGE_MODES,
        "research_material_scope_atom_mode_invalid",
    )
    if period_mode == "all_periods_same_basis":
        _require(
            coverage_mode == "single_binding"
            and len(request.period.fiscal_years) >= 2
            and len(metric_indices) == 1
            and len(product_indices) <= 1,
            "research_material_scope_temporal_atom_invalid",
        )
    else:
        _require(
            coverage_mode == "collective_axes",
            "research_material_scope_non_temporal_atom_invalid",
        )

    metrics: tuple[int | None, ...] = metric_indices or (None,)
    products: tuple[int | None, ...] = product_indices or (None,)
    groups: list[dict[str, Any]] = []
    for metric_index in metrics:
        for product_index in products:
            group = {
                "facet_id": atom["facet_id"],
                "role": atom["role"],
                "metric_ids": (
                    [request.metric_intents[metric_index]]
                    if metric_index is not None
                    else []
                ),
                "product_ids": (
                    [request.product_intents[product_index]]
                    if product_index is not None
                    else []
                ),
                "target_entities": list(request.target_entities),
                "period_mode": period_mode,
                "fiscal_years": (
                    list(request.period.fiscal_years)
                    if period_mode == "all_periods_same_basis"
                    else []
                ),
                "minimum_candidates": 1,
                "coverage_mode": coverage_mode,
            }
            groups.append(group)
    return groups


def compile_research_material_scope(
    payload: Mapping[str, Any],
    *,
    research_plan_digest: str,
    requests: Sequence[EvidenceRequest],
    required_request_ids: Sequence[str],
    policy: Mapping[str, Any],
    material_runtime_policy: Mapping[str, Any],
    intent_ontology: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile bounded natural scope atoms into explicit runtime requirements."""

    validate_material_scope_policy(policy, material_runtime_policy)
    _require(
        set(payload) == {"schema_version", "research_plan_digest", "request_scopes"},
        "research_material_scope_output_fields_invalid",
    )
    _require(
        payload.get("schema_version") == MATERIAL_SCOPE_OUTPUT_SCHEMA,
        "research_material_scope_output_schema_invalid",
    )
    _require(
        payload.get("research_plan_digest") == research_plan_digest,
        "research_material_scope_plan_binding_invalid",
    )
    raw_scopes = payload.get("request_scopes")
    _require(
        isinstance(raw_scopes, Sequence)
        and not isinstance(raw_scopes, (str, bytes)),
        "research_material_scope_requests_invalid",
    )
    request_by_id = {request.request_id: request for request in requests}
    required = tuple(dict.fromkeys(str(value) for value in required_request_ids))
    _require(bool(required), "research_material_scope_required_requests_empty")
    scope_by_id: dict[str, Mapping[str, Any]] = {}
    for row in raw_scopes:
        _require(
            isinstance(row, Mapping)
            and set(row)
            == {
                "request_id",
                "product_intent_dispositions",
                "requirement_atoms",
            },
            "research_material_scope_request_fields_invalid",
        )
        request_id = str(row.get("request_id") or "")
        _require(
            request_id in request_by_id and request_id not in scope_by_id,
            "research_material_scope_request_binding_invalid",
        )
        scope_by_id[request_id] = row
    _require(
        set(scope_by_id) == set(required),
        "research_material_scope_required_request_coverage_invalid",
    )

    compiled_rows: list[dict[str, Any]] = []
    for request_id in required:
        request = request_by_id[request_id]
        row = scope_by_id[request_id]
        raw_dispositions = row.get("product_intent_dispositions")
        _require(
            isinstance(raw_dispositions, Sequence)
            and not isinstance(raw_dispositions, (str, bytes)),
            "research_material_scope_dispositions_invalid",
        )
        disposition_by_index: dict[int, str] = {}
        for item in raw_dispositions:
            _require(
                isinstance(item, Mapping)
                and set(item) == {"product_intent_index", "disposition"},
                "research_material_scope_disposition_fields_invalid",
            )
            index = item.get("product_intent_index")
            disposition = str(item.get("disposition") or "")
            _require(
                isinstance(index, int)
                and not isinstance(index, bool)
                and 0 <= index < len(request.product_intents)
                and index not in disposition_by_index
                and disposition in _DISPOSITIONS,
                "research_material_scope_disposition_invalid",
            )
            period_only = _is_period_only_product_intent(
                request.product_intents[index]
            )
            fixed_disposition = _fixed_product_disposition(
                request.product_intents[index],
                material_runtime_policy=material_runtime_policy,
                intent_ontology=intent_ontology,
            )
            _require(
                (period_only and disposition == "temporal_directive")
                or (not period_only and disposition != "temporal_directive"),
                "research_material_scope_temporal_disposition_invalid",
            )
            _require(
                fixed_disposition is None or disposition == fixed_disposition,
                "research_material_scope_fixed_disposition_changed",
            )
            disposition_by_index[index] = disposition
        _require(
            set(disposition_by_index) == set(range(len(request.product_intents))),
            "research_material_scope_product_disposition_coverage_invalid",
        )
        hard_product_indices = {
            index
            for index, disposition in disposition_by_index.items()
            if disposition == "hard_material_axis"
        }

        raw_atoms = row.get("requirement_atoms")
        _require(
            isinstance(raw_atoms, Sequence)
            and not isinstance(raw_atoms, (str, bytes))
            and bool(raw_atoms)
            and len(raw_atoms) <= int(policy["maximum_scope_atoms_per_request"]),
            "research_material_scope_atom_budget_invalid",
        )
        facet_id = request.requested_facet_ids[0]
        required_roles = tuple(
            material_runtime_policy["facet_required_roles"].get(facet_id) or ()
        )
        _require(bool(required_roles), "research_material_scope_facet_roles_missing")
        normalized_atoms: list[dict[str, Any]] = []
        role_metric_coverage: dict[str, set[int]] = {
            role: set() for role in required_roles
        }
        role_product_coverage: dict[str, set[int]] = {
            role: set() for role in required_roles
        }
        seen_roles: set[str] = set()
        requirements: list[dict[str, Any]] = []
        seen_groups: set[str] = set()
        for raw_atom in raw_atoms:
            _require(
                isinstance(raw_atom, Mapping)
                and set(raw_atom)
                == {
                    "facet_id",
                    "role",
                    "metric_intent_indices",
                    "product_intent_indices",
                    "period_mode",
                    "coverage_mode",
                },
                "research_material_scope_atom_fields_invalid",
            )
            atom = dict(raw_atom)
            role = str(atom.get("role") or "")
            _require(
                atom.get("facet_id") == facet_id and role in required_roles,
                "research_material_scope_atom_boundary_invalid",
            )
            seen_roles.add(role)
            metric_indices = _indices(
                atom.get("metric_intent_indices"),
                upper_bound=len(request.metric_intents),
                code="research_material_scope_metric_indices_invalid",
            )
            product_indices = _indices(
                atom.get("product_intent_indices"),
                upper_bound=len(request.product_intents),
                code="research_material_scope_product_indices_invalid",
            )
            role_metric_coverage[role].update(metric_indices)
            role_product_coverage[role].update(product_indices)
            normalized_atoms.append(atom)
            for group in _expand_atom(
                atom=atom,
                request=request,
                hard_product_indices=hard_product_indices,
                role_axis=material_runtime_policy["material_role_axis_contract"][
                    role
                ],
            ):
                signature = canonical_digest(group)
                if signature not in seen_groups:
                    seen_groups.add(signature)
                    requirements.append(group)
        _require(
            seen_roles == set(required_roles)
            and all(
                role_metric_coverage[role] == set(range(len(request.metric_intents)))
                if material_runtime_policy["material_role_axis_contract"][role][
                    "bind_requested_metrics"
                ]
                else not role_metric_coverage[role]
                for role in required_roles
            ),
            "research_material_scope_metric_coverage_invalid",
        )
        _require(
            all(
                role_product_coverage[role] == hard_product_indices
                for role in required_roles
            ),
            "research_material_scope_hard_product_coverage_invalid",
        )
        _require(
            bool(requirements), "research_material_scope_requirements_empty"
        )
        compiled_rows.append(
            {
                "request_id": request_id,
                "product_intent_dispositions": [
                    {
                        "product_intent_index": index,
                        "product_intent": request.product_intents[index],
                        "disposition": disposition_by_index[index],
                    }
                    for index in sorted(disposition_by_index)
                ],
                "requirement_atoms": normalized_atoms,
                "research_blueprint": {
                    "material_requirements": requirements,
                },
                "explicit_scope_ready": True,
                "candidate_or_reference_inputs_read": False,
                "candidate_is_not_evidence": True,
                "numeric_authority": False,
            }
        )

    body = {
        "schema_version": MATERIAL_SCOPE_COMPILATION_SCHEMA,
        "research_plan_digest": research_plan_digest,
        "required_request_ids": list(required),
        "request_scopes": compiled_rows,
        "summary": {
            "required_request_count": len(required),
            "compiled_request_count": len(compiled_rows),
            "requirement_atom_count": sum(
                len(row["requirement_atoms"]) for row in compiled_rows
            ),
            "material_requirement_count": sum(
                len(row["research_blueprint"]["material_requirements"])
                for row in compiled_rows
            ),
            "candidate_or_reference_inputs_read": False,
            "generation_model_calls_recorded_by_compiler": 0,
        },
        "authority": dict(policy["authority"]),
    }
    return {**body, "compilation_digest": canonical_digest(body)}


__all__ = [
    "MATERIAL_SCOPE_COMPILATION_SCHEMA",
    "MATERIAL_SCOPE_OUTPUT_SCHEMA",
    "MATERIAL_SCOPE_POLICY_SCHEMA",
    "ResearchMaterialScopeError",
    "compile_research_material_scope",
    "compile_research_material_scope_messages",
    "parse_research_material_scope_output",
    "validate_material_scope_policy",
]
