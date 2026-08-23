from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.session import (
    canonical_digest,
    validate_runtime_artifact,
)
from sec_agent.research.dynamic_research_runtime import (
    compile_dynamic_research_input_projection,
)


POLICY_SCHEMA_VERSION = "fin_ia_s3_dynamic_single_unit_loop_policy_v1_0"
REQUEST_TOOL_NAME = "request_research_evidence"
REFLECTION_TOOL_NAME = "submit_research_reflection"
REQUEST_PAYLOAD_SCHEMA_VERSION = "fin_ia_dynamic_research_request_selection_v1_0"
REFLECTION_PAYLOAD_SCHEMA_VERSION = "fin_ia_dynamic_research_reflection_v1_0"
ROUND_RESPONSE_SCHEMA_VERSION = "fin_ia_dynamic_research_round_response_v1_0"
WORKPAPER_CONTEXT_SCHEMA_VERSION = "fin_ia_dynamic_single_unit_workpaper_context_v1_0"


class DynamicSingleUnitLoopError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DynamicSingleUnitLoopError(code)


def _mapping(value: object, code: str) -> dict[str, Any]:
    _require(isinstance(value, Mapping), code)
    return deepcopy(dict(value))


def _strings(
    value: object,
    code: str,
    *,
    minimum: int = 0,
    maximum: int | None = None,
) -> list[str]:
    _require(isinstance(value, (list, tuple)), code)
    rows = [str(item).strip() for item in value]
    _require(
        len(rows) >= minimum
        and (maximum is None or len(rows) <= maximum)
        and all(rows)
        and len(rows) == len(set(rows)),
        code,
    )
    return rows


def load_dynamic_single_unit_policy(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    _require(
        value.get("schema_version") == POLICY_SCHEMA_VERSION
        and value.get("status")
        == "bounded_current_runtime_dynamic_single_unit_candidate",
        "dynamic_single_unit_policy_identity_invalid",
    )
    identity = _mapping(
        value.get("case_identity"), "dynamic_single_unit_policy_case_invalid"
    )
    objective = _mapping(
        value.get("objective"), "dynamic_single_unit_policy_objective_invalid"
    )
    limits = _mapping(
        value.get("loop_limits"), "dynamic_single_unit_policy_limits_invalid"
    )
    coverage = _mapping(
        value.get("coverage_groups"),
        "dynamic_single_unit_policy_coverage_invalid",
    )
    authority = _mapping(
        value.get("authority"), "dynamic_single_unit_policy_authority_invalid"
    )
    _require(
        identity.get("case_key") == "DELL"
        and identity.get("subject_ticker") == "DELL"
        and identity.get("research_as_of") == "2026-08-06"
        and objective.get("cell_id") == "value_capture"
        and objective.get("agent_id") == "AGENT::VALUE_CAPTURE",
        "dynamic_single_unit_policy_scope_invalid",
    )
    _require(
        isinstance(limits.get("maximum_retrieval_rounds"), int)
        and 1 <= limits["maximum_retrieval_rounds"] <= 3
        and isinstance(limits.get("maximum_request_ids_per_round"), int)
        and 1 <= limits["maximum_request_ids_per_round"] <= 12
        and isinstance(limits.get("maximum_total_request_ids"), int)
        and limits["maximum_total_request_ids"] <= 12
        and limits.get("repeated_request_forbidden") is True
        and limits.get("candidate_text_model_visibility") is False,
        "dynamic_single_unit_policy_limits_invalid",
    )
    _require(
        set(coverage)
        == {
            "price_and_configuration",
            "unit_volume",
            "pvm",
            "customer_demand",
            "supply_chain",
            "value_pool",
            "counterevidence",
        }
        and all(
            isinstance(request_ids, list)
            and bool(request_ids)
            and len(request_ids) == len(set(request_ids))
            for request_ids in coverage.values()
        ),
        "dynamic_single_unit_policy_coverage_invalid",
    )
    _require(
        authority.get("initial_message_may_contain_evidence_or_numeric_facts")
        is False
        and authority.get("model_selects_research_actions") is True
        and authority.get("candidate_rank_grants_evidence") is False
        and authority.get("model_may_self_authorize_public_information_gap")
        is False
        and authority.get("graph_hypothesis_grants_fact_authority") is False,
        "dynamic_single_unit_policy_authority_invalid",
    )
    token_bases = _mapping(
        value.get("token_budget_bases"),
        "dynamic_single_unit_policy_token_bases_invalid",
    )
    _require(
        set(token_bases)
        == {
            "request_planning",
            "reflection_and_plan_delta",
            "specialist_workpaper",
        }
        and all(
            isinstance(row, Mapping)
            and int(row.get("maximum_completion_tokens") or 0) >= 8000
            and bool(str(row.get("node_purpose") or "").strip())
            and bool(row.get("required_outputs"))
            and bool(str(row.get("materiality_and_quality_risk") or "").strip())
            and bool(str(row.get("comparable_run_evidence") or "").strip())
            and bool(str(row.get("stop_or_truncation_behavior") or "").strip())
            for row in token_bases.values()
        ),
        "dynamic_single_unit_policy_token_bases_invalid",
    )
    return value


def compile_request_catalog(
    *,
    policy: Mapping[str, Any],
    program: Mapping[str, Any],
    task_readiness: Mapping[str, Any],
) -> dict[str, Any]:
    trusted = load_dynamic_single_unit_policy(policy)
    identity = trusted["case_identity"]
    _require(
        str(program.get("case_key") or "").upper() == identity["case_key"]
        and str(program.get("research_as_of") or "")
        == identity["research_as_of"]
        and str(task_readiness.get("case_key") or "").upper()
        == identity["case_key"]
        and str(task_readiness.get("cell_id") or "") == "value_capture",
        "dynamic_single_unit_catalog_case_or_date_invalid",
    )
    requests = {
        str(row.get("request_id") or ""): deepcopy(dict(row))
        for row in program.get("evidence_requests") or ()
        if isinstance(row, Mapping)
    }
    _require(
        len(requests) == 12 and all(requests),
        "dynamic_single_unit_catalog_request_set_invalid",
    )
    covered_ids = {
        str(request_id)
        for request_ids in trusted["coverage_groups"].values()
        for request_id in request_ids
    }
    _require(
        covered_ids == set(requests),
        "dynamic_single_unit_catalog_coverage_set_invalid",
    )
    request_states = {
        str(row.get("request_id") or ""): deepcopy(dict(row))
        for row in task_readiness.get("request_states") or ()
        if isinstance(row, Mapping)
    }
    _require(
        set(request_states) == set(requests),
        "dynamic_single_unit_catalog_readiness_set_invalid",
    )
    actionable = {
        str(row.get("request_id") or ""): deepcopy(dict(row))
        for row in (
            task_readiness.get("task_pack_readiness", {}).get(
                "actionable_gap_requests", ()
            )
        )
        if isinstance(row, Mapping)
    }
    proposition_by_request: dict[str, dict[str, str]] = {}
    for raw in program.get("propositions") or ():
        proposition = _mapping(
            raw, "dynamic_single_unit_catalog_proposition_invalid"
        )
        for request_id in proposition.get("request_ids") or ():
            _require(
                str(request_id) in requests
                and str(request_id) not in proposition_by_request,
                "dynamic_single_unit_catalog_proposition_binding_invalid",
            )
            proposition_by_request[str(request_id)] = {
                "proposition_id": str(proposition.get("proposition_id") or ""),
                "business_question_zh": str(
                    proposition.get("business_question_zh") or ""
                ),
            }
    rows: list[dict[str, Any]] = []
    for request_id, request in requests.items():
        proposition = proposition_by_request.get(request_id)
        _require(
            proposition is not None
            and proposition["proposition_id"]
            and proposition["business_question_zh"],
            "dynamic_single_unit_catalog_proposition_missing",
        )
        group_ids = sorted(
            group_id
            for group_id, group_requests in trusted["coverage_groups"].items()
            if request_id in group_requests
        )
        _require(group_ids, "dynamic_single_unit_catalog_group_missing")
        state = request_states[request_id]
        rows.append(
            {
                "request_id": request_id,
                "proposition_id": proposition["proposition_id"],
                "coverage_group_ids": group_ids,
                "business_question_zh": proposition["business_question_zh"],
                "facet_ids": list(request.get("requested_facet_ids") or ()),
                "metric_intents": list(request.get("metric_intents") or ()),
                "product_intents": list(request.get("product_intents") or ()),
                "target_entities": list(request.get("target_entities") or ()),
                "task_readiness_state": str(state.get("state") or ""),
                "actionable_gap_ids": list(
                    actionable.get(request_id, {}).get(
                        "required_open_gap_ids", ()
                    )
                ),
                "request_payload": request,
            }
        )
    body = {
        "schema_version": "fin_ia_dynamic_single_unit_request_catalog_v1_0",
        "case_key": identity["case_key"],
        "research_as_of": identity["research_as_of"],
        "requests": sorted(rows, key=lambda row: row["request_id"]),
    }
    return {**body, "catalog_digest": canonical_digest(body)}


def compile_material_requirement_blueprints(
    *,
    program: Mapping[str, Any],
    request_ids: Sequence[str],
) -> dict[str, dict[str, Any]]:
    contract = _mapping(
        program.get("material_scope_blueprint"),
        "dynamic_single_unit_material_scope_missing",
    )
    _require(
        contract.get("mode")
        == "explicit_all_visible_product_intents_hard_material_axes",
        "dynamic_single_unit_material_scope_invalid",
    )
    roles_by_request = _mapping(
        contract.get("required_roles_by_request"),
        "dynamic_single_unit_material_roles_invalid",
    )
    metric_roles = {
        str(value) for value in contract.get("metric_binding_roles") or ()
    }
    requests = {
        str(row.get("request_id") or ""): deepcopy(dict(row))
        for row in program.get("evidence_requests") or ()
        if isinstance(row, Mapping)
    }
    selected = _strings(
        request_ids,
        "dynamic_single_unit_material_request_ids_invalid",
        minimum=1,
    )
    _require(
        set(selected).issubset(requests),
        "dynamic_single_unit_material_request_unknown",
    )
    blueprints: dict[str, dict[str, Any]] = {}
    for request_id in selected:
        request = requests[request_id]
        facets = _strings(
            request.get("requested_facet_ids"),
            "dynamic_single_unit_material_facet_invalid",
            minimum=1,
            maximum=1,
        )
        products = _strings(
            request.get("product_intents"),
            "dynamic_single_unit_material_products_invalid",
            minimum=1,
        )
        entities = _strings(
            request.get("target_entities"),
            "dynamic_single_unit_material_entities_invalid",
            minimum=1,
        )
        metrics = _strings(
            request.get("metric_intents"),
            "dynamic_single_unit_material_metrics_invalid",
        )
        roles = _strings(
            roles_by_request.get(request_id),
            "dynamic_single_unit_material_roles_invalid",
            minimum=1,
        )
        blueprints[request_id] = {
            "material_requirements": [
                {
                    "facet_id": facets[0],
                    "role": role,
                    "metric_ids": metrics if role in metric_roles else [],
                    "product_ids": products,
                    "target_entities": entities,
                    "period_mode": "any",
                    "fiscal_years": [],
                    "minimum_candidates": 1,
                    "coverage_mode": "collective_axes",
                    "metric_coverage_mode": "retrieval_context_only",
                    "product_coverage_mode": "all_of",
                }
                for role in roles
            ]
        }
    return blueprints


def compile_initial_messages(
    *,
    policy: Mapping[str, Any],
    request_catalog: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    trusted = load_dynamic_single_unit_policy(policy)
    _require(
        request_catalog.get("case_key") == trusted["case_identity"]["case_key"]
        and request_catalog.get("research_as_of")
        == trusted["case_identity"]["research_as_of"],
        "dynamic_single_unit_initial_catalog_binding_invalid",
    )
    identity = trusted["case_identity"]
    objective = trusted["objective"]
    user_payload = {
        "question": objective["question_zh"],
        "company_identity": {
            "ticker": identity["subject_ticker"],
            "legal_name": identity["subject_legal_name"],
        },
        "research_as_of": identity["research_as_of"],
        "authorized_capabilities": [
            "select bounded research requests through the provided tool",
            "read only reviewed Evidence and typed NumericFacts returned by tools",
            "reflect on FeedbackReceipts and modify the bounded plan",
            "submit one source-bound specialist workpaper after stopping research",
        ],
    }
    return (
        {
            "role": "system",
            "content": (
                "You are the DELL value-capture research specialist in a bounded "
                "financial research session. Start from the user question, identity, "
                "as-of date and available tools only. Select research actions, inspect "
                "reviewed Evidence and typed facts returned by tools, then explicitly "
                "reflect on missing bridges, contradictions, counterevidence and "
                "whether another search round is useful. Candidate rank is not "
                "Evidence. A failed route or empty result is not public non-disclosure. "
                "Graph hypotheses are query guidance only. Do not rely on memory for "
                "facts, numbers, dates, sources or citations."
            ),
        },
        {
            "role": "user",
            "content": __import__("json").dumps(
                user_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    )


def request_evidence_tool(
    *,
    policy: Mapping[str, Any],
    request_catalog: Mapping[str, Any],
    executed_request_ids: Sequence[str] = (),
    round_index: int,
) -> dict[str, Any]:
    trusted = load_dynamic_single_unit_policy(policy)
    executed = set(str(value) for value in executed_request_ids)
    available = [
        row
        for row in request_catalog.get("requests") or ()
        if str(row.get("request_id") or "") not in executed
    ]
    _require(available, "dynamic_single_unit_request_tool_no_available_requests")
    rows = [
        {
            "request_id": str(row["request_id"]),
            "research_question": str(row["business_question_zh"]),
            "coverage_groups": list(row["coverage_group_ids"]),
            "facets": list(row["facet_ids"]),
            "metrics": list(row["metric_intents"]),
            "products": list(row["product_intents"]),
        }
        for row in available
    ]
    maximum = min(
        int(trusted["loop_limits"]["maximum_request_ids_per_round"]),
        len(rows),
    )
    description = (
        "Select the next proposition-bound S1/S2 requests. The catalog describes "
        "questions and routes, not answers or Evidence. Request catalog: "
        + __import__("json").dumps(
            rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    )
    return {
        "type": "function",
        "function": {
            "name": REQUEST_TOOL_NAME,
            "description": description,
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "schema_version",
                    "round_id",
                    "request_ids",
                    "research_rationale",
                    "expected_information_gain",
                ],
                "properties": {
                    "schema_version": {
                        "type": "string",
                        "enum": [REQUEST_PAYLOAD_SCHEMA_VERSION],
                    },
                    "round_id": {
                        "type": "string",
                        "enum": [f"ROUND::{round_index}"],
                    },
                    "request_ids": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": maximum,
                        "uniqueItems": True,
                        "items": {
                            "type": "string",
                            "enum": [row["request_id"] for row in rows],
                        },
                    },
                    "research_rationale": {
                        "type": "string",
                        "minLength": 30,
                        "maxLength": 1600,
                    },
                    "expected_information_gain": {
                        "type": "string",
                        "minLength": 20,
                        "maxLength": 1200,
                    },
                },
            },
        },
    }


def validate_request_selection(
    payload: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    request_catalog: Mapping[str, Any],
    executed_request_ids: Sequence[str],
    round_index: int,
) -> dict[str, Any]:
    trusted = load_dynamic_single_unit_policy(policy)
    value = deepcopy(dict(payload))
    _require(
        set(value)
        == {
            "schema_version",
            "round_id",
            "request_ids",
            "research_rationale",
            "expected_information_gain",
        }
        and value.get("schema_version") == REQUEST_PAYLOAD_SCHEMA_VERSION
        and value.get("round_id") == f"ROUND::{round_index}",
        "dynamic_single_unit_request_selection_shape_invalid",
    )
    request_ids = _strings(
        value.get("request_ids"),
        "dynamic_single_unit_request_selection_ids_invalid",
        minimum=1,
        maximum=int(trusted["loop_limits"]["maximum_request_ids_per_round"]),
    )
    catalog_ids = {
        str(row.get("request_id") or "")
        for row in request_catalog.get("requests") or ()
    }
    executed = set(str(value) for value in executed_request_ids)
    _require(
        set(request_ids).issubset(catalog_ids)
        and not set(request_ids).intersection(executed)
        and len(executed) + len(request_ids)
        <= int(trusted["loop_limits"]["maximum_total_request_ids"]),
        "dynamic_single_unit_request_selection_scope_invalid",
    )
    rationale = str(value.get("research_rationale") or "").strip()
    gain = str(value.get("expected_information_gain") or "").strip()
    _require(
        30 <= len(rationale) <= 1600 and 20 <= len(gain) <= 1200,
        "dynamic_single_unit_request_selection_text_invalid",
    )
    return {
        **value,
        "request_ids": request_ids,
        "selection_digest": canonical_digest(value),
    }


def compile_controlled_batch_projection(
    *,
    policy: Mapping[str, Any],
    selected_requests: Sequence[Mapping[str, Any]],
    batch_result: Mapping[str, Any],
) -> dict[str, Any]:
    trusted = load_dynamic_single_unit_policy(policy)
    request_rows = [deepcopy(dict(row)) for row in selected_requests]
    result_rows = [
        deepcopy(dict(row)) for row in batch_result.get("request_results") or ()
    ]
    _require(
        request_rows
        and [row.get("request_id") for row in request_rows]
        == [row.get("request", {}).get("request_id") for row in result_rows],
        "dynamic_single_unit_batch_request_binding_invalid",
    )
    planner_atoms = [
        {
            "facet_id": str(request["requested_facet_ids"][0]),
            "target_entity": str(request["subject_ticker"]),
            "metric_ids": list(request.get("metric_intents") or ()),
            "product_intents": list(request.get("product_intents") or ()),
        }
        for request in request_rows
    ]
    compiled_plan_body = {
        "planner_atoms": planner_atoms,
        "evidence_requests": request_rows,
    }
    compiled_plan = {
        **compiled_plan_body,
        "plan_digest": canonical_digest(compiled_plan_body),
    }
    body = {
        "status": "controlled_research_plan_zero_call_executed",
        "objective": {
            "objective_id": trusted["objective"]["objective_id"],
            "case_key": trusted["case_identity"]["case_key"],
            "subject_ticker": trusted["case_identity"]["subject_ticker"],
            "subject_legal_name": trusted["case_identity"][
                "subject_legal_name"
            ],
            "research_as_of": trusted["case_identity"]["research_as_of"],
        },
        "compiled_plan": compiled_plan,
        "request_results": result_rows,
    }
    return {**body, "projection_digest": canonical_digest(body)}


def _compact_evidence_card(
    row: Mapping[str, Any], *, maximum_excerpt_chars: int
) -> dict[str, Any]:
    excerpt = str(row.get("source_visible_fact_excerpt") or "")
    return {
        "evidence_ref": str(row.get("evidence_ref") or ""),
        "evidence_role": str(row.get("evidence_role") or ""),
        "evidence_owner_ticker": str(row.get("evidence_owner_ticker") or ""),
        "source_type": str(row.get("source_type") or ""),
        "source_tier": str(row.get("source_tier") or ""),
        "source_url": str(row.get("source_url") or ""),
        "publication_date": str(row.get("publication_date") or ""),
        "source_reporting_period_end": str(
            row.get("source_reporting_period_end") or ""
        ),
        "relationship_directions": list(
            row.get("relationship_directions") or ()
        ),
        "slot_bindings": deepcopy(list(row.get("slot_bindings") or ())),
        "source_visible_fact_excerpt": excerpt[:maximum_excerpt_chars],
        "excerpt_truncated_for_round_response": len(excerpt)
        > maximum_excerpt_chars,
        "numeric_use_boundary": str(row.get("numeric_use_boundary") or ""),
    }


def _compact_numeric_card(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(row.get(key))
        for key in (
            "numeric_ref",
            "ticker",
            "metric_id",
            "value_decimal",
            "unit",
            "period_start",
            "period_end",
            "fiscal_year",
            "fiscal_period",
            "authority_mode",
            "formula_trace",
            "citation_urls",
        )
        if key in row
    }


def _compact_relation_card(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(row.get(key))
        for key in (
            "numeric_relation_ref",
            "metric_id",
            "relation_type",
            "current_numeric_ref",
            "comparison_numeric_ref",
            "current_period",
            "comparison_period",
            "change_decimal",
            "change_unit",
        )
        if key in row
    }


def _task_quantitative_projection(
    task_quantitative_result: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "research_estimates": deepcopy(
            list(task_quantitative_result.get("research_estimates") or ())
        ),
        "scenarios": deepcopy(
            list(task_quantitative_result.get("scenarios") or ())
        ),
        "typed_gap_dispositions": deepcopy(
            list(task_quantitative_result.get("typed_gap_dispositions") or ())
        ),
        "authority": deepcopy(dict(task_quantitative_result.get("authority") or {})),
    }


def compile_round_response(
    *,
    policy: Mapping[str, Any],
    controlled_plan: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
    truth_spine_policy: Mapping[str, Any],
    consumer_policy: Mapping[str, Any],
    task_quantitative_result: Mapping[str, Any],
    round_index: int,
) -> dict[str, Any]:
    trusted = load_dynamic_single_unit_policy(policy)
    projection = compile_dynamic_research_input_projection(
        truth_spine_policy=truth_spine_policy,
        consumer_policy=consumer_policy,
        controlled_plan=controlled_plan,
        evidence_pack=evidence_pack,
    )
    dynamic_input = _mapping(
        projection.get("dynamic_research_input"),
        "dynamic_single_unit_round_no_reviewed_evidence",
    )
    response_by_id = {
        str(row.get("request_id") or ""): deepcopy(dict(row))
        for row in projection["evidence_responses"].get("responses") or ()
        if isinstance(row, Mapping)
    }
    dynamic_card_by_request_id = {
        str(row.get("request_id") or ""): deepcopy(dict(row))
        for row in dynamic_input.get("dynamic_evidence_response_cards") or ()
        if isinstance(row, Mapping)
    }
    request_receipts = []
    for result in controlled_plan.get("request_results") or ():
        request_id = str(result.get("request", {}).get("request_id") or "")
        response = response_by_id.get(request_id) or {}
        dynamic_card = dynamic_card_by_request_id.get(request_id) or {}
        request_receipts.append(
            {
                "request_id": request_id,
                "accepted_reviewed_evidence_refs": list(
                    dynamic_card.get("accepted_evidence_refs") or ()
                ),
                "accepted_reviewed_evidence_count": len(
                    response.get("accepted") or ()
                ),
                "model_visible_accepted_evidence_count": len(
                    dynamic_card.get("accepted_evidence_refs") or ()
                ),
                "reviewed_but_not_model_visible_count": int(
                    dynamic_card.get(
                        "reviewed_but_not_model_visible_count", 0
                    )
                    or 0
                ),
                "unreviewed_candidate_count": len(
                    response.get("needs_human_review") or ()
                ),
                "rejected_reviewed_binding_count": len(
                    response.get("rejected") or ()
                ),
                "typed_gap_codes": [
                    str(row.get("gap", {}).get("gap_code") or "")
                    for row in response.get("typed_gaps") or ()
                ],
                "candidate_rank_grants_evidence": False,
            }
        )
    maximum_excerpt = int(
        trusted["loop_limits"]["reviewed_evidence_excerpt_maximum_chars"]
    )
    body = {
        "schema_version": ROUND_RESPONSE_SCHEMA_VERSION,
        "round_id": f"ROUND::{round_index}",
        "case_identity": deepcopy(trusted["case_identity"]),
        "request_receipts": request_receipts,
        "reviewed_evidence": [
            _compact_evidence_card(row, maximum_excerpt_chars=maximum_excerpt)
            for row in dynamic_input.get("evidence_cards") or ()
        ],
        "numeric_facts": [
            _compact_numeric_card(row)
            for row in dynamic_input.get("numeric_fact_cards") or ()
        ],
        "numeric_relations": [
            _compact_relation_card(row)
            for row in dynamic_input.get("numeric_relation_cards") or ()
        ],
        "residual_gaps": deepcopy(
            list(dynamic_input.get("residual_gap_cards") or ())
        ),
        "task_quantitative_context": _task_quantitative_projection(
            task_quantitative_result
        ),
        "dynamic_evidence_response_cards": deepcopy(
            list(dynamic_input.get("dynamic_evidence_response_cards") or ())
        ),
        "authority": {
            "candidate_text_visible": False,
            "candidate_promotions": int(projection.get("candidate_promotions") or 0),
            "reviewed_evidence_only": True,
            "numeric_authority_owned_by_S2": True,
            "task_estimates_and_scenarios_are_not_reported_facts": True,
            "failed_route_is_not_public_non_disclosure": True,
        },
    }
    return {
        **body,
        "round_response_digest": canonical_digest(body),
        "_dynamic_research_input": dynamic_input,
    }


def _feedback_receipt(
    *,
    session_id: str,
    request_id: str,
    failure_code: str,
    failure_class: str,
    owning_plane: str,
    owning_stage: str,
    target_node_id: str,
    summary: str,
    actions: Sequence[str],
    created_at: str,
    round_response_digest: str,
) -> dict[str, Any]:
    identity = {
        "session_id": session_id,
        "request_id": request_id,
        "failure_code": failure_code,
        "round_response_digest": round_response_digest,
    }
    body = {
        "feedback_id": "FEEDBACK::" + canonical_digest(identity)[:24].upper(),
        "session_id": session_id,
        "source_node_id": "S1S2.DynamicEvidenceTool",
        "target_node_id": target_node_id,
        "failure_class": failure_class,
        "failure_code": failure_code,
        "owning_plane": owning_plane,
        "owning_stage": owning_stage,
        "artifact_refs": [
            f"round-response://{round_response_digest}",
            f"request://{request_id}",
        ],
        "model_visible_summary": summary,
        "permitted_next_actions": list(actions),
        "forbidden_interpretations": [
            "不得把未审 Candidate、排名或摘要当作 Evidence",
            "不得把未执行、失败或无结果路线解释为公开信息不存在",
            "不得用模型记忆补写事实、数字、期间、来源或引用",
        ],
        "created_at": created_at,
    }
    validated = validate_runtime_artifact("FeedbackReceipt", body)
    return {**validated, "feedback_digest": canonical_digest(validated)}


def compile_round_feedback_receipts(
    *,
    session_id: str,
    round_response: Mapping[str, Any],
    request_catalog: Mapping[str, Any],
    created_at: str,
) -> list[dict[str, Any]]:
    catalog = {
        str(row.get("request_id") or ""): row
        for row in request_catalog.get("requests") or ()
    }
    receipts: list[dict[str, Any]] = []
    digest = str(round_response.get("round_response_digest") or "")
    for raw in round_response.get("request_receipts") or ():
        row = _mapping(raw, "dynamic_single_unit_round_receipt_invalid")
        request_id = str(row.get("request_id") or "")
        _require(
            request_id in catalog,
            "dynamic_single_unit_round_receipt_request_unknown",
        )
        current = catalog[request_id]
        if int(row.get("unreviewed_candidate_count") or 0) > 0:
            receipts.append(
                _feedback_receipt(
                    session_id=session_id,
                    request_id=request_id,
                    failure_code="candidate_requires_review_not_evidence",
                    failure_class="candidate_decision_or_evidence_admission_pending",
                    owning_plane="harness_control_plane",
                    owning_stage="S1",
                    target_node_id="S1.EvidenceGate",
                    summary=(
                        f"{request_id} 找到新的候选，但其中至少一条尚未完成命题、来源、期间和 Evidence Role 审核；"
                        "当前回合只能使用已审 Evidence。"
                    ),
                    actions=(
                        "继续使用已审 Evidence形成当前判断",
                        "若该候选可能改变结论，提交后续 Evidence admission 请求",
                    ),
                    created_at=created_at,
                    round_response_digest=digest,
                )
            )
        if int(row.get("accepted_reviewed_evidence_count") or 0) == 0:
            receipts.append(
                _feedback_receipt(
                    session_id=session_id,
                    request_id=request_id,
                    failure_code="no_reviewed_evidence_reselected",
                    failure_class="query_recall_or_reviewed_binding_not_resolved",
                    owning_plane="infrastructure_and_tool_plane",
                    owning_stage="S1",
                    target_node_id="S1.QueryRecallOrRouteOwner",
                    summary=(
                        f"{request_id} 本轮没有重新选中可用的 reviewed Evidence；这只证明当前工具路径未解决该命题，"
                        "不证明公开资料不存在。"
                    ),
                    actions=(
                        "换用尚未执行的同命题来源或反方请求",
                        "保留明确缺口并避免生成伪精确结论",
                    ),
                    created_at=created_at,
                    round_response_digest=digest,
                )
            )
        actionable_gaps = list(current.get("actionable_gap_ids") or ())
        if actionable_gaps:
            receipts.append(
                _feedback_receipt(
                    session_id=session_id,
                    request_id=request_id,
                    failure_code="task_material_gap_remains_actionable",
                    failure_class="material_gap_without_public_boundary_authority",
                    owning_plane="harness_control_plane",
                    owning_stage="S1",
                    target_node_id="S1.GapEligibilityOrAlternativeRoute",
                    summary=(
                        f"{request_id} 仍绑定材料缺口 {', '.join(actionable_gaps)}。它可以限制结论或触发换路线，"
                        "但当前没有公共信息边界权威。"
                    ),
                    actions=(
                        "检查其他已授权请求是否可提供区间、旁证或反方",
                        "若两轮内无新增权威，保留 typed gap 并说明对判断的具体影响",
                    ),
                    created_at=created_at,
                    round_response_digest=digest,
                )
            )
    unique = {str(row["feedback_id"]): row for row in receipts}
    return [unique[key] for key in sorted(unique)]


def reflection_tool(
    *,
    policy: Mapping[str, Any],
    request_catalog: Mapping[str, Any],
    feedback_receipts: Sequence[Mapping[str, Any]],
    accepted_evidence_refs: Sequence[str],
    executed_request_ids: Sequence[str],
    round_index: int,
) -> dict[str, Any]:
    trusted = load_dynamic_single_unit_policy(policy)
    maximum_rounds = int(trusted["loop_limits"]["maximum_retrieval_rounds"])
    all_ids = {
        str(row.get("request_id") or "")
        for row in request_catalog.get("requests") or ()
    }
    available = sorted(all_ids - set(executed_request_ids))
    feedback_refs = sorted(str(row["feedback_id"]) for row in feedback_receipts)
    evidence_refs = sorted(set(str(value) for value in accepted_evidence_refs))
    final_round = round_index >= maximum_rounds or not available
    allowed_decisions = (
        ["stop_sufficient", "stop_no_progress"]
        if final_round
        else ["continue", "stop_sufficient", "stop_no_progress"]
    )
    next_maximum = min(
        int(trusted["loop_limits"]["maximum_request_ids_per_round"]),
        len(available),
    )
    return {
        "type": "function",
        "function": {
            "name": REFLECTION_TOOL_NAME,
            "description": (
                "Reflect on exact EvidenceResponse and FeedbackReceipt objects, then "
                "submit a bounded plan change or stop decision. Public-information "
                "boundary is not an available self-authorized decision."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "schema_version",
                    "round_id",
                    "reflection_summary",
                    "answered_questions",
                    "unresolved_questions",
                    "feedback_refs",
                    "next_request_ids",
                    "graph_hypotheses",
                    "proposed_stop_decision",
                    "reason_codes",
                ],
                "properties": {
                    "schema_version": {
                        "type": "string",
                        "enum": [REFLECTION_PAYLOAD_SCHEMA_VERSION],
                    },
                    "round_id": {
                        "type": "string",
                        "enum": [f"ROUND::{round_index}"],
                    },
                    "reflection_summary": {
                        "type": "string",
                        "minLength": 50,
                        "maxLength": 2200,
                    },
                    "answered_questions": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 12,
                        "uniqueItems": True,
                        "items": {"type": "string", "minLength": 8, "maxLength": 500},
                    },
                    "unresolved_questions": {
                        "type": "array",
                        "maxItems": 12,
                        "uniqueItems": True,
                        "items": {"type": "string", "minLength": 8, "maxLength": 500},
                    },
                    "feedback_refs": {
                        "type": "array",
                        "minItems": 1 if feedback_refs else 0,
                        "maxItems": len(feedback_refs),
                        "uniqueItems": True,
                        "items": {
                            "type": "string",
                            "enum": feedback_refs or ["FEEDBACK::NONE"],
                        },
                    },
                    "next_request_ids": {
                        "type": "array",
                        "maxItems": next_maximum,
                        "uniqueItems": True,
                        "items": {
                            "type": "string",
                            "enum": available or ["REQUEST::NONE"],
                        },
                    },
                    "graph_hypotheses": {
                        "type": "array",
                        "maxItems": 6,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "source_entity",
                                "relationship_direction",
                                "target_entity",
                                "evidence_refs",
                                "research_use",
                            ],
                            "properties": {
                                "source_entity": {"type": "string", "minLength": 2, "maxLength": 80},
                                "relationship_direction": {"type": "string", "minLength": 3, "maxLength": 120},
                                "target_entity": {"type": "string", "minLength": 2, "maxLength": 80},
                                "evidence_refs": {
                                    "type": "array",
                                    "maxItems": len(evidence_refs),
                                    "uniqueItems": True,
                                    "items": {
                                        "type": "string",
                                        "enum": evidence_refs or ["EVIDENCE::NONE"],
                                    },
                                },
                                "research_use": {"type": "string", "minLength": 12, "maxLength": 500},
                            },
                        },
                    },
                    "proposed_stop_decision": {
                        "type": "string",
                        "enum": allowed_decisions,
                    },
                    "reason_codes": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 8,
                        "uniqueItems": True,
                        "items": {"type": "string", "minLength": 3, "maxLength": 120},
                    },
                },
            },
        },
    }


def validate_reflection_payload(
    payload: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    request_catalog: Mapping[str, Any],
    feedback_receipts: Sequence[Mapping[str, Any]],
    accepted_evidence_refs: Sequence[str],
    executed_request_ids: Sequence[str],
    round_index: int,
) -> dict[str, Any]:
    trusted = load_dynamic_single_unit_policy(policy)
    value = deepcopy(dict(payload))
    expected = {
        "schema_version",
        "round_id",
        "reflection_summary",
        "answered_questions",
        "unresolved_questions",
        "feedback_refs",
        "next_request_ids",
        "graph_hypotheses",
        "proposed_stop_decision",
        "reason_codes",
    }
    _require(
        set(value) == expected
        and value.get("schema_version") == REFLECTION_PAYLOAD_SCHEMA_VERSION
        and value.get("round_id") == f"ROUND::{round_index}",
        "dynamic_single_unit_reflection_shape_invalid",
    )
    summary = str(value.get("reflection_summary") or "").strip()
    _require(
        50 <= len(summary) <= 2200,
        "dynamic_single_unit_reflection_summary_invalid",
    )
    value["answered_questions"] = _strings(
        value.get("answered_questions"),
        "dynamic_single_unit_reflection_answered_invalid",
        minimum=1,
        maximum=12,
    )
    value["unresolved_questions"] = _strings(
        value.get("unresolved_questions"),
        "dynamic_single_unit_reflection_unresolved_invalid",
        maximum=12,
    )
    value["reason_codes"] = _strings(
        value.get("reason_codes"),
        "dynamic_single_unit_reflection_reasons_invalid",
        minimum=1,
        maximum=8,
    )
    allowed_feedback = {str(row["feedback_id"]) for row in feedback_receipts}
    value["feedback_refs"] = _strings(
        value.get("feedback_refs"),
        "dynamic_single_unit_reflection_feedback_invalid",
        minimum=1 if allowed_feedback else 0,
        maximum=len(allowed_feedback),
    )
    _require(
        set(value["feedback_refs"]).issubset(allowed_feedback),
        "dynamic_single_unit_reflection_feedback_out_of_scope",
    )
    catalog_ids = {
        str(row.get("request_id") or "")
        for row in request_catalog.get("requests") or ()
    }
    executed = set(str(value) for value in executed_request_ids)
    value["next_request_ids"] = _strings(
        value.get("next_request_ids"),
        "dynamic_single_unit_reflection_next_requests_invalid",
        maximum=int(trusted["loop_limits"]["maximum_request_ids_per_round"]),
    )
    _require(
        set(value["next_request_ids"]).issubset(catalog_ids - executed)
        and len(executed) + len(value["next_request_ids"])
        <= int(trusted["loop_limits"]["maximum_total_request_ids"]),
        "dynamic_single_unit_reflection_next_requests_out_of_scope",
    )
    allowed_evidence = set(str(value) for value in accepted_evidence_refs)
    hypotheses = value.get("graph_hypotheses")
    _require(
        isinstance(hypotheses, list) and len(hypotheses) <= 6,
        "dynamic_single_unit_reflection_graph_invalid",
    )
    normalized_hypotheses = []
    for raw in hypotheses:
        row = _mapping(raw, "dynamic_single_unit_reflection_graph_invalid")
        _require(
            set(row)
            == {
                "source_entity",
                "relationship_direction",
                "target_entity",
                "evidence_refs",
                "research_use",
            }
            and 2 <= len(str(row.get("source_entity") or "").strip()) <= 80
            and 2 <= len(str(row.get("target_entity") or "").strip()) <= 80
            and 3
            <= len(str(row.get("relationship_direction") or "").strip())
            <= 120
            and 12 <= len(str(row.get("research_use") or "").strip()) <= 500,
            "dynamic_single_unit_reflection_graph_invalid",
        )
        refs = _strings(
            row.get("evidence_refs"),
            "dynamic_single_unit_reflection_graph_refs_invalid",
            maximum=len(allowed_evidence),
        )
        _require(
            set(refs).issubset(allowed_evidence),
            "dynamic_single_unit_reflection_graph_refs_out_of_scope",
        )
        normalized_hypotheses.append({**row, "evidence_refs": refs})
    value["graph_hypotheses"] = normalized_hypotheses
    decision = str(value.get("proposed_stop_decision") or "")
    maximum_rounds = int(trusted["loop_limits"]["maximum_retrieval_rounds"])
    if decision == "continue":
        _require(
            round_index < maximum_rounds and bool(value["next_request_ids"]),
            "dynamic_single_unit_reflection_continue_invalid",
        )
    else:
        _require(
            decision in {"stop_sufficient", "stop_no_progress"}
            and not value["next_request_ids"],
            "dynamic_single_unit_reflection_stop_invalid",
        )
    return {**value, "reflection_digest": canonical_digest(value)}


def coverage_state(
    *, policy: Mapping[str, Any], executed_request_ids: Sequence[str]
) -> dict[str, Any]:
    trusted = load_dynamic_single_unit_policy(policy)
    executed = set(str(value) for value in executed_request_ids)
    groups = {
        group_id: {
            "covered": bool(executed.intersection(request_ids)),
            "executed_request_ids": sorted(executed.intersection(request_ids)),
        }
        for group_id, request_ids in trusted["coverage_groups"].items()
    }
    body = {
        "groups": groups,
        "all_required_groups_covered": all(
            row["covered"] for row in groups.values()
        ),
    }
    return {**body, "coverage_digest": canonical_digest(body)}


def compile_reflection_artifacts(
    *,
    policy: Mapping[str, Any],
    reflection: Mapping[str, Any],
    session_id: str,
    agent_id: str,
    base_plan: Mapping[str, Any],
    base_graph_digest: str,
    executed_request_ids: Sequence[str],
    open_gap_refs: Sequence[str],
    model_calls_used: int,
) -> dict[str, Any]:
    trusted = load_dynamic_single_unit_policy(policy)
    value = deepcopy(dict(reflection))
    _require(
        str(value.get("reflection_digest") or "")
        == canonical_digest(
            {
                key: item
                for key, item in value.items()
                if key != "reflection_digest"
            }
        ),
        "dynamic_single_unit_reflection_digest_invalid",
    )
    base_plan_body = {
        key: deepcopy(item)
        for key, item in base_plan.items()
        if key != "plan_digest"
    }
    base_plan_digest = canonical_digest(base_plan_body)
    if base_plan.get("plan_digest") is not None:
        _require(
            str(base_plan.get("plan_digest") or "") == base_plan_digest,
            "dynamic_single_unit_base_plan_digest_invalid",
        )
    feedback_refs = list(value["feedback_refs"])
    next_request_ids = list(value["next_request_ids"])
    plan_delta_body = {
        "plan_delta_id": "PLANDELTA::"
        + canonical_digest(
            {
                "session_id": session_id,
                "reflection_digest": value["reflection_digest"],
            }
        )[:24].upper(),
        "session_id": session_id,
        "base_plan_digest": base_plan_digest,
        "proposed_by_agent_id": agent_id,
        "reason_feedback_refs": feedback_refs,
        "add_actions": [
            {
                "action_ref": f"research-request://{request_id}",
                "request_id": request_id,
                "owner_stage": "S1_S2_runtime",
            }
            for request_id in next_request_ids
        ],
        "modify_actions": [],
        "defer_actions": [
            {"gap_ref": str(gap_ref), "reason": "preserve_until_resolved"}
            for gap_ref in open_gap_refs
        ],
        "cancel_actions": [],
        "expected_information_gain": str(value["reflection_summary"]),
        "budget_impact": {
            "model_calls_used": model_calls_used,
            "next_provider_step_authorized": bool(next_request_ids),
            "next_request_count": len(next_request_ids),
        },
        "validation_status": "accepted",
    }
    validated_delta = validate_runtime_artifact("PlanDelta", plan_delta_body)
    plan_delta = {
        **validated_delta,
        "plan_delta_digest": canonical_digest(validated_delta),
    }
    accepted_plan = {
        **base_plan_body,
        "executed_request_ids": sorted(set(executed_request_ids)),
        "next_request_ids": next_request_ids,
        "latest_reflection_digest": value["reflection_digest"],
        "latest_feedback_refs": feedback_refs,
    }
    accepted_plan_digest = canonical_digest(accepted_plan)
    graph_hypotheses = deepcopy(list(value["graph_hypotheses"]))
    supporting_refs = sorted(
        {
            str(ref)
            for row in graph_hypotheses
            for ref in row.get("evidence_refs") or ()
        }
    )
    graph_delta_body = {
        "graph_delta_id": "GRAPHDELTA::"
        + canonical_digest(
            {
                "session_id": session_id,
                "reflection_digest": value["reflection_digest"],
            }
        )[:24].upper(),
        "session_id": session_id,
        "base_graph_digest": base_graph_digest,
        "proposed_by_agent_id": agent_id,
        "edge_additions": [],
        "edge_corrections": [],
        "edge_retractions": [],
        "supporting_evidence_refs": supporting_refs,
        "hypothesis_only_edges": graph_hypotheses,
        "validation_status": "accepted",
    }
    validated_graph = validate_runtime_artifact("GraphDelta", graph_delta_body)
    graph_delta = {
        **validated_graph,
        "graph_delta_digest": canonical_digest(validated_graph),
        "fact_authority_granted": False,
    }
    state = coverage_state(
        policy=trusted, executed_request_ids=executed_request_ids
    )
    decision = str(value["proposed_stop_decision"])
    if decision == "stop_sufficient":
        _require(
            state["all_required_groups_covered"],
            "dynamic_single_unit_stop_sufficient_coverage_incomplete",
        )
    stop_body = {
        "stop_decision_id": "STOP::"
        + canonical_digest(
            {
                "session_id": session_id,
                "reflection_digest": value["reflection_digest"],
                "decision": decision,
            }
        )[:24].upper(),
        "session_id": session_id,
        "decided_by_agent_id": agent_id,
        "decision": decision,
        "reason_codes": list(value["reason_codes"]),
        "coverage_state_refs": [
            f"COVERAGE::{group_id.upper()}"
            for group_id, row in state["groups"].items()
            if row["covered"]
        ],
        "unresolved_feedback_refs": feedback_refs,
        "remaining_gap_refs": sorted(set(str(ref) for ref in open_gap_refs)),
        "budget_state": {
            "model_calls_used": model_calls_used,
            "maximum_provider_steps": trusted["loop_limits"][
                "maximum_provider_steps"
            ],
            "required_actions_silently_dropped": False,
        },
        "quality_risk": (
            "bounded_material_gaps_remain_explicit"
            if open_gap_refs
            else "current_task_material_coverage_complete"
        ),
        "harness_validation_status": "accepted",
    }
    validated_stop = validate_runtime_artifact("StopDecision", stop_body)
    stop_decision = {
        **validated_stop,
        "stop_decision_digest": canonical_digest(validated_stop),
    }
    return {
        "plan_delta": plan_delta,
        "accepted_plan": {
            **accepted_plan,
            "plan_digest": accepted_plan_digest,
        },
        "accepted_plan_ref": "PLAN::" + accepted_plan_digest[:24].upper(),
        "graph_delta": graph_delta,
        "stop_decision": stop_decision,
        "coverage_state": state,
    }


def compile_workpaper_context(
    *,
    policy: Mapping[str, Any],
    round_responses: Sequence[Mapping[str, Any]],
    feedback_receipts: Sequence[Mapping[str, Any]],
    reflections: Sequence[Mapping[str, Any]],
    stop_decision: Mapping[str, Any],
) -> dict[str, Any]:
    trusted = load_dynamic_single_unit_policy(policy)
    _require(round_responses, "dynamic_single_unit_workpaper_rounds_missing")
    evidence: dict[str, dict[str, Any]] = {}
    numeric: dict[str, dict[str, Any]] = {}
    relations: dict[str, dict[str, Any]] = {}
    gaps: dict[str, dict[str, Any]] = {}
    estimates: dict[str, dict[str, Any]] = {}
    scenarios: dict[str, dict[str, Any]] = {}
    method_pack: dict[str, Any] | None = None
    graph_packs: list[dict[str, Any]] = []
    for response in round_responses:
        for row in response.get("reviewed_evidence") or ():
            evidence[str(row["evidence_ref"])] = deepcopy(dict(row))
        for row in response.get("numeric_facts") or ():
            numeric[str(row["numeric_ref"])] = deepcopy(dict(row))
        for row in response.get("numeric_relations") or ():
            relations[str(row["numeric_relation_ref"])] = deepcopy(dict(row))
        for row in response.get("residual_gaps") or ():
            gaps[str(row["gap_ref"])] = deepcopy(dict(row))
        task = response.get("task_quantitative_context") or {}
        for row in task.get("research_estimates") or ():
            estimates[str(row["estimate_id"])] = deepcopy(dict(row))
        for row in task.get("scenarios") or ():
            scenarios[str(row["scenario_id"])] = deepcopy(dict(row))
        dynamic = response.get("_dynamic_research_input") or {}
        for cell in dynamic.get("cells") or ():
            if str(cell.get("cell_id") or "") == "CELL::value_capture":
                method_pack = deepcopy(dict(cell.get("role_method_pack") or {}))
                graph = cell.get("graph_context_pack")
                if isinstance(graph, Mapping):
                    graph_packs.append(deepcopy(dict(graph)))
    _require(method_pack is not None, "dynamic_single_unit_workpaper_method_pack_missing")
    numeric_authorities = {**numeric, **estimates}
    cell_view = {
        "cell": {
            "cell_id": "CELL::value_capture",
            "cell_evidence_views": [evidence[key] for key in sorted(evidence)],
            "allowed_numeric_refs": sorted(numeric_authorities),
            "allowed_numeric_relation_refs": sorted(relations),
            "residual_gap_cards": [gaps[key] for key in sorted(gaps)],
            "role_method_pack": method_pack,
        },
        "evidence_fact_catalog": [evidence[key] for key in sorted(evidence)],
        "numeric_fact_catalog": [
            numeric_authorities[key] for key in sorted(numeric_authorities)
        ],
        "numeric_relation_catalog": [
            relations[key] for key in sorted(relations)
        ],
    }
    model_context = {
        "schema_version": WORKPAPER_CONTEXT_SCHEMA_VERSION,
        "agent": {
            "agent_id": trusted["objective"]["agent_id"],
            "cell_id": "CELL::value_capture",
            "responsibility": (
                "Evaluate how DELL AI-server demand, price/configuration, volume, "
                "mix, supply constraints and counterparty economics translate into "
                "gross profit, operating profit and cash, without inventing a "
                "product-level causal bridge."
            ),
        },
        "objective": deepcopy(trusted["objective"]),
        "case_identity": deepcopy(trusted["case_identity"]),
        "cell_analysis_view": cell_view,
        "task_scenarios": [scenarios[key] for key in sorted(scenarios)],
        "graph_context_packs": graph_packs,
        "feedback_receipts": [deepcopy(dict(row)) for row in feedback_receipts],
        "reflection_history": [deepcopy(dict(row)) for row in reflections],
        "stop_decision": deepcopy(dict(stop_decision)),
        "rules": [
            "Lead with the useful judgment; consolidate limitations under the exact affected proposition instead of repeating generic disclaimers.",
            "Distinguish issuer facts, counterparty context, deterministic derived values, research estimates and scenarios.",
            "Do not turn industry shipment growth into DELL units or channel price into DELL ASP.",
            "Do not equate ISG profit with AI-server profit without a direct bridge.",
            "Translate every material remaining gap into its decision impact and an observable what-would-change condition.",
        ],
        "authority": {
            "model_owns_judgment": True,
            "harness_owns_refs_identity_dates_and_numeric_rendering": True,
            "candidate_or_graph_hypothesis_is_not_evidence": True,
            "working_draft_not_business_truth": True,
        },
    }
    return {
        **model_context,
        "context_digest": canonical_digest(model_context),
    }


def compile_workpaper_submission_view(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Project a complete workpaper context into one non-duplicative model view.

    The complete context remains the local validation authority.  The model view
    carries every reviewed Evidence, numeric authority, relation, gap, scenario,
    method and reflection once, rather than repeating the same Evidence inside
    both ``cell_evidence_views`` and ``evidence_fact_catalog``.  This is transport
    compaction, not evidence selection or deterministic research writing.
    """

    trusted_context = deepcopy(dict(context))
    context_digest = str(trusted_context.pop("context_digest", ""))
    _require(
        trusted_context.get("schema_version") == WORKPAPER_CONTEXT_SCHEMA_VERSION
        and context_digest == canonical_digest(trusted_context),
        "dynamic_single_unit_workpaper_submission_context_invalid",
    )
    analysis_view = context.get("cell_analysis_view")
    _require(
        isinstance(analysis_view, Mapping)
        and isinstance(analysis_view.get("cell"), Mapping),
        "dynamic_single_unit_workpaper_submission_context_invalid",
    )
    cell = analysis_view["cell"]
    evidence = [
        deepcopy(dict(row))
        for row in analysis_view.get("evidence_fact_catalog") or ()
    ]
    numeric = [
        deepcopy(dict(row))
        for row in analysis_view.get("numeric_fact_catalog") or ()
    ]
    relations = [
        deepcopy(dict(row))
        for row in analysis_view.get("numeric_relation_catalog") or ()
    ]
    gaps = [
        deepcopy(dict(row)) for row in cell.get("residual_gap_cards") or ()
    ]
    evidence_refs = [str(row.get("evidence_ref") or "") for row in evidence]
    numeric_refs = [
        str(row.get("numeric_ref") or row.get("estimate_id") or "")
        for row in numeric
    ]
    relation_refs = [
        str(row.get("numeric_relation_ref") or "") for row in relations
    ]
    gap_refs = [str(row.get("gap_ref") or "") for row in gaps]
    _require(
        evidence_refs
        and all(evidence_refs)
        and len(evidence_refs) == len(set(evidence_refs))
        and all(numeric_refs)
        and len(numeric_refs) == len(set(numeric_refs))
        and all(relation_refs)
        and len(relation_refs) == len(set(relation_refs))
        and all(gap_refs)
        and len(gap_refs) == len(set(gap_refs))
        and set(evidence_refs)
        == {
            str(row.get("evidence_ref") or "")
            for row in cell.get("cell_evidence_views") or ()
        }
        and set(numeric_refs) == set(cell.get("allowed_numeric_refs") or ())
        and set(relation_refs)
        == set(cell.get("allowed_numeric_relation_refs") or ()),
        "dynamic_single_unit_workpaper_submission_authority_drift",
    )
    unique_graphs: dict[str, dict[str, Any]] = {}
    for raw in context.get("graph_context_packs") or ():
        row = deepcopy(dict(raw))
        digest = str(row.get("graph_context_digest") or canonical_digest(row))
        unique_graphs.setdefault(digest, row)
    feedback_index = [
        {
            key: deepcopy(row.get(key))
            for key in (
                "feedback_id",
                "failure_class",
                "failure_code",
                "model_visible_summary",
                "forbidden_interpretations",
                "permitted_next_actions",
            )
        }
        for row in context.get("feedback_receipts") or ()
    ]
    reflection_analysis = [
        {
            key: deepcopy(row.get(key))
            for key in (
                "round_id",
                "reflection_summary",
                "answered_questions",
                "unresolved_questions",
                "graph_hypotheses",
                "reason_codes",
                "proposed_stop_decision",
                "reflection_digest",
            )
        }
        for row in context.get("reflection_history") or ()
    ]
    body = {
        "schema_version": "fin_ia_dynamic_single_unit_workpaper_submission_view_v1_0",
        "source_context_digest": context_digest,
        "agent": deepcopy(context.get("agent") or {}),
        "objective": deepcopy(context.get("objective") or {}),
        "case_identity": deepcopy(context.get("case_identity") or {}),
        "reviewed_evidence": evidence,
        "numeric_authorities": numeric,
        "numeric_relations": relations,
        "residual_gaps": gaps,
        "task_scenarios": deepcopy(context.get("task_scenarios") or []),
        "role_method_pack": deepcopy(cell.get("role_method_pack") or {}),
        "graph_context_packs": [unique_graphs[key] for key in sorted(unique_graphs)],
        "feedback_index": feedback_index,
        "model_authored_reflection_analysis": reflection_analysis,
        "stop_decision": deepcopy(context.get("stop_decision") or {}),
        "rules": deepcopy(context.get("rules") or []),
        "authority": deepcopy(context.get("authority") or {}),
    }
    return {**body, "submission_view_digest": canonical_digest(body)}


def public_round_response(round_response: Mapping[str, Any]) -> dict[str, Any]:
    value = {
        key: deepcopy(item)
        for key, item in round_response.items()
        if key != "_dynamic_research_input"
    }
    return value


__all__ = [
    "DynamicSingleUnitLoopError",
    "POLICY_SCHEMA_VERSION",
    "REFLECTION_PAYLOAD_SCHEMA_VERSION",
    "REFLECTION_TOOL_NAME",
    "REQUEST_PAYLOAD_SCHEMA_VERSION",
    "REQUEST_TOOL_NAME",
    "compile_controlled_batch_projection",
    "compile_initial_messages",
    "compile_material_requirement_blueprints",
    "compile_reflection_artifacts",
    "compile_request_catalog",
    "compile_round_feedback_receipts",
    "compile_round_response",
    "compile_workpaper_context",
    "compile_workpaper_submission_view",
    "coverage_state",
    "load_dynamic_single_unit_policy",
    "public_round_response",
    "reflection_tool",
    "request_evidence_tool",
    "validate_reflection_payload",
    "validate_request_selection",
]
