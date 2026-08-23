from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from retrieval.contracts import FinancialResearchKernel
from retrieval.route_compiler import QueryObjectFactRoutePolicy

from .dynamic_single_unit_loop import (
    GENERIC_SPECIALIST_POLICY_SCHEMA_VERSION,
    load_dynamic_single_unit_policy,
)
from .multi_agent_preview import (
    SPECIALIST_AGENT_IDS,
    validate_specialist_workpaper,
)
from .planning import (
    ResearchPlanningPolicy,
    compile_research_objective,
    compile_research_plan,
)
from .reviewed_evidence_pack import canonical_digest


MULTI_AGENT_LOOP_POLICY_SCHEMA_VERSION = (
    "fin_ia_s3_current_dynamic_multi_agent_loop_policy_v1_0"
)
MULTI_AGENT_ROLE_PROGRAMS_SCHEMA_VERSION = (
    "fin_ia_s3_current_dynamic_multi_agent_role_programs_v1_0"
)
WORKPAPER_DIGEST_NORMALIZATION_RECEIPT_SCHEMA_VERSION = (
    "fin_ia_s3_specialist_workpaper_digest_normalization_receipt_v1_0"
)


MATERIAL_ROLES_BY_FACET: dict[str, tuple[str, ...]] = {
    "orders_and_backlog": ("direct", "counter"),
    "conversion_and_durability": ("direct", "counter"),
    "reported_results": ("direct", "context"),
    "guidance_and_outlook": ("direct", "counter"),
    "margin_and_incremental_profit": ("bridge", "counter"),
    "pricing_and_mix": ("direct", "context"),
    "cash_generation": ("direct", "counter"),
    "working_capital_risk": ("direct", "counter"),
    "upstream_capacity_context": ("context", "counter"),
    "counterparty_direct_mention": ("direct", "context"),
    "subject_relationship_disclosure": ("direct", "counter"),
    "issuer_counterevidence": ("counter",),
    "upstream_or_demand_counterevidence": ("counter", "context"),
}


class DynamicMultiAgentLoopError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DynamicMultiAgentLoopError(code)


def _strings(
    value: object,
    code: str,
    *,
    minimum: int = 0,
    maximum: int | None = None,
) -> list[str]:
    _require(isinstance(value, (list, tuple)), code)
    rows = [str(row).strip() for row in value]
    _require(
        len(rows) >= minimum
        and (maximum is None or len(rows) <= maximum)
        and all(rows)
        and len(rows) == len(set(rows)),
        code,
    )
    return rows


def load_dynamic_multi_agent_loop_policy(
    payload: Mapping[str, Any],
    *,
    topology: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    expected = {
        "schema_version",
        "status",
        "case_identity",
        "objective_ref",
        "source_refs",
        "specialist_roles",
        "loop_limits",
        "token_budget_policy",
        "authority",
    }
    _require(
        set(value) == expected
        and value.get("schema_version")
        == MULTI_AGENT_LOOP_POLICY_SCHEMA_VERSION
        and value.get("status")
        == "zero_call_contract_candidate_live_not_authorized",
        "dynamic_multi_agent_policy_identity_invalid",
    )
    identity = value.get("case_identity")
    _require(
        isinstance(identity, Mapping)
        and str(identity.get("case_key") or "") == "DELL"
        and str(identity.get("subject_ticker") or "") == "DELL"
        and str(identity.get("research_as_of") or "") == "2026-08-06",
        "dynamic_multi_agent_policy_case_invalid",
    )
    topology_agents = {
        str(row.get("agent_id") or ""): row
        for row in topology.get("preview_agents") or ()
        if isinstance(row, Mapping)
    }
    raw_roles = value.get("specialist_roles")
    _require(
        isinstance(raw_roles, list)
        and [str(row.get("agent_id") or "") for row in raw_roles]
        == list(SPECIALIST_AGENT_IDS),
        "dynamic_multi_agent_policy_role_order_invalid",
    )
    seen_facets: set[str] = set()
    for raw in raw_roles:
        _require(isinstance(raw, Mapping), "dynamic_multi_agent_policy_role_invalid")
        agent_id = str(raw.get("agent_id") or "")
        topology_row = topology_agents.get(agent_id)
        facets = _strings(
            raw.get("facet_ids"),
            "dynamic_multi_agent_policy_role_facets_invalid",
            minimum=1,
            maximum=4,
        )
        _require(
            set(raw)
            == {
                "agent_id",
                "cell_id",
                "facet_ids",
                "quantitative_slot_ids",
            }
            and topology_row is not None
            and str(raw.get("cell_id") or "")
            == str(topology_row.get("cell_id") or "")
            and set(facets)
            == set(topology_row.get("allowed_facet_ids") or ())
            and not seen_facets.intersection(facets),
            "dynamic_multi_agent_policy_role_invalid",
        )
        _strings(
            raw.get("quantitative_slot_ids"),
            "dynamic_multi_agent_policy_role_quantitative_scope_invalid",
            maximum=4,
        )
        seen_facets.update(facets)
    _require(
        seen_facets == set(topology.get("facet_catalog") or {}),
        "dynamic_multi_agent_policy_facet_partition_invalid",
    )
    limits = value.get("loop_limits")
    _require(
        isinstance(limits, Mapping)
        and set(limits)
        == {
            "maximum_retrieval_rounds_per_specialist",
            "maximum_request_ids_per_round",
            "maximum_total_request_ids_per_specialist",
            "maximum_provider_steps_per_specialist",
            "maximum_lead_coordination_rounds",
            "maximum_role_repairs_per_lead_round",
            "reviewed_evidence_excerpt_maximum_chars",
            "repeated_request_forbidden",
            "candidate_text_model_visibility",
        }
        and 1 <= int(limits["maximum_retrieval_rounds_per_specialist"]) <= 3
        and 1 <= int(limits["maximum_request_ids_per_round"]) <= 4
        and 1 <= int(limits["maximum_total_request_ids_per_specialist"]) <= 6
        and int(limits["maximum_provider_steps_per_specialist"])
        >= int(limits["maximum_retrieval_rounds_per_specialist"]) + 2
        and 1 <= int(limits["maximum_lead_coordination_rounds"]) <= 2
        and 1 <= int(limits["maximum_role_repairs_per_lead_round"]) <= 3
        and 600
        <= int(limits["reviewed_evidence_excerpt_maximum_chars"])
        <= 4000
        and limits["repeated_request_forbidden"] is True
        and limits["candidate_text_model_visibility"] is False,
        "dynamic_multi_agent_policy_limits_invalid",
    )
    token_policy = value.get("token_budget_policy")
    _require(
        isinstance(token_policy, Mapping)
        and token_policy.get("task_specific_basis_required_per_attempt") is True
        and token_policy.get("cost_or_latency_may_silently_drop_work") is False
        and token_policy.get("comparable_run_evidence_required") is True
        and token_policy.get("truncation_is_terminal") is True,
        "dynamic_multi_agent_policy_token_budget_invalid",
    )
    authority = value.get("authority")
    _require(
        isinstance(authority, Mapping)
        and authority.get("specialists_have_independent_sessions") is True
        and authority.get("model_selects_research_actions") is True
        and authority.get("lead_may_route_feedback_but_not_author_research_facts")
        is True
        and authority.get("candidate_rank_grants_evidence") is False
        and authority.get("graph_hypothesis_grants_fact_authority") is False
        and authority.get("public_information_gap_requires_GapEligibilityReceipt")
        is True
        and authority.get("live_execution_requires_separate_signed_authority")
        is True,
        "dynamic_multi_agent_policy_authority_invalid",
    )
    return value


def _role_workpaper_rules(*, agent_id: str) -> list[str]:
    common = [
        "Lead with the useful judgment and attach each limitation only to the proposition it changes; do not repeat generic boundary prose.",
        "Distinguish issuer facts, counterparty context, deterministic NumericFacts, research estimates, scenarios and unresolved hypotheses.",
        "A related-company disclosure is not a DELL fact unless the reviewed Evidence directly binds that relationship.",
        "Translate every material gap into decision impact, the next feasible action and an observable what-would-change condition.",
    ]
    role_rule = {
        "AGENT::DEMAND_QUALITY": "Keep orders, backlog, shipments, recognized revenue and end demand separate; test pull-forward and cancellation alternatives.",
        "AGENT::OPERATING_PERFORMANCE": "Use like-for-like periods and scopes; keep realized results separate from management guidance.",
        "AGENT::VALUE_CAPTURE": "Do not infer AI product profit from ISG or consolidated profit without a product-to-segment-to-company bridge.",
        "AGENT::CASH_CONVERSION": "Do not infer AI-specific cash contribution from consolidated cash flow; separate working-capital financing effects.",
        "AGENT::SUPPLY_RELATIONSHIP": "Preserve speaker, relationship direction and supply-chain layer; capacity expansion is not DELL allocation or delivery proof.",
        "AGENT::COUNTEREVIDENCE": "Actively test the strongest issuer and ecosystem alternative explanation and route material challenges to the owning role.",
    }[agent_id]
    return [*common, role_rule]


def _token_bases(*, agent_id: str, responsibility: str) -> dict[str, Any]:
    return {
        "request_planning": {
            "node_purpose": f"Let {agent_id} choose proposition-bound S1/S2 actions for {responsibility}",
            "required_outputs": [
                "request_ids",
                "research_rationale",
                "expected_information_gain",
            ],
            "schema_burden": "small strict request-selection tool over a role-local catalog",
            "materiality_and_quality_risk": "high because omitting a role-owned facet can bias the final cross-role synthesis",
            "comparable_run_evidence": "DELL value_capture R3 showed that natural request selection and two-round adaptation are feasible when exact tool feedback is returned.",
            "reasoning_profile": "DeepSeek GA thinking=max for research action selection",
            "maximum_completion_tokens": 16000,
            "stop_or_truncation_behavior": "non-tool, empty or truncated output is a terminal failed attempt and does not silently remove the role task",
        },
        "reflection_and_plan_delta": {
            "node_purpose": f"Let {agent_id} consume exact EvidenceResponse and FeedbackReceipt objects, then continue or stop with a bounded PlanDelta.",
            "required_outputs": [
                "feedback_refs",
                "next_request_ids",
                "graph_hypotheses",
                "proposed_stop_decision",
            ],
            "schema_burden": "strict reflection, PlanDelta, GraphDelta and StopDecision surfaces",
            "materiality_and_quality_risk": "high because a false sufficient stop or a false information boundary would suppress necessary research",
            "comparable_run_evidence": "DELL value_capture R3 consumed local feedback and changed its plan; R5-R7 showed semantic feedback must remain actionable and role-bound.",
            "reasoning_profile": "DeepSeek GA thinking=max for reflection and plan change",
            "maximum_completion_tokens": 16000,
            "stop_or_truncation_behavior": "invalid feedback coverage, unauthorized graph authority or incomplete stop coverage fails closed",
        },
        "specialist_workpaper": {
            "node_purpose": f"Produce the independent {agent_id} workpaper after role-local research and reflection.",
            "required_outputs": [
                "thesis",
                "sourced_claims",
                "mechanism",
                "alternative_explanations",
                "counterarguments",
                "what_would_change",
            ],
            "schema_burden": "large strict workpaper tool with role-local Evidence, NumericFact, Relation and gap enums",
            "materiality_and_quality_risk": "very high because unsupported causal attribution or disclaimer-heavy prose directly degrades the research product",
            "comparable_run_evidence": "DELL value_capture R7 required a non-thinking submission surface plus independent semantic L1/L2 assessment after a thinking-heavy research loop.",
            "reasoning_profile": "analysis is preserved from prior reflections; final tool submission uses a separately qualified low-thinking profile",
            "maximum_completion_tokens": 12000,
            "stop_or_truncation_behavior": "truncated, unbound or unauthorized claims are terminal and remain available for FeedbackReceipt repair",
        },
    }


def compile_dynamic_multi_agent_role_programs(
    *,
    policy: Mapping[str, Any],
    topology: Mapping[str, Any],
    objective_payload: Mapping[str, Any],
    planner_compilation: Mapping[str, Any],
    kernel: FinancialResearchKernel,
    route_policy: QueryObjectFactRoutePolicy,
    planning_policy: ResearchPlanningPolicy,
) -> dict[str, Any]:
    trusted = load_dynamic_multi_agent_loop_policy(policy, topology=topology)
    atoms = [
        deepcopy(dict(row))
        for row in planner_compilation.get("planner_payload", {}).get("atoms") or ()
        if isinstance(row, Mapping)
    ]
    atom_by_facet = {str(row.get("facet_id") or ""): row for row in atoms}
    _require(
        len(atom_by_facet) == len(atoms),
        "dynamic_multi_agent_atom_facet_duplicate",
    )
    binding_by_facet = {
        str(row.get("facet_id") or ""): list(
            row.get("proposing_agent_ids") or ()
        )
        for row in planner_compilation.get("role_facet_bindings") or ()
        if isinstance(row, Mapping)
    }
    configured_facets = {
        str(facet)
        for role in trusted["specialist_roles"]
        for facet in role["facet_ids"]
    }
    _require(
        set(atom_by_facet) == configured_facets == set(binding_by_facet)
        and all(len(agent_ids) == 1 for agent_ids in binding_by_facet.values()),
        "dynamic_multi_agent_atom_partition_invalid",
    )
    topology_by_agent = {
        str(row.get("agent_id") or ""): row
        for row in topology.get("preview_agents") or ()
        if isinstance(row, Mapping)
    }
    facet_to_slot = {
        facet.facet_id: slot.slot_id
        for slot in kernel.slots
        for facet in slot.facets
    }
    programs: list[dict[str, Any]] = []
    all_request_ids: set[str] = set()
    for role in trusted["specialist_roles"]:
        agent_id = str(role["agent_id"])
        facets = list(role["facet_ids"])
        _require(
            all(binding_by_facet[facet] == [agent_id] for facet in facets),
            "dynamic_multi_agent_role_binding_invalid",
        )
        role_atoms = [deepcopy(atom_by_facet[facet]) for facet in facets]
        role_slots = list(dict.fromkeys(facet_to_slot[facet] for facet in facets))
        role_objective_payload = deepcopy(dict(objective_payload))
        role_objective_payload["raw_question"] = (
            str(objective_payload["raw_question"])
            + " 当前专业角色为 "
            + agent_id
            + "，只处理分配给该角色的命题。"
        )
        role_objective_payload["required_slot_ids"] = role_slots
        role_objective_payload["budget"] = deepcopy(
            dict(role_objective_payload["budget"])
        )
        role_objective_payload["budget"]["max_evidence_requests"] = len(
            role_atoms
        )
        objective = compile_research_objective(
            role_objective_payload,
            kernel=kernel,
            policy=planning_policy,
        )
        planner_payload = {
            "schema_version": "fin_ia_research_planner_atoms_v1_0",
            "objective_id": objective.objective_id,
            "atoms": role_atoms,
        }
        plan = compile_research_plan(
            planner_payload,
            objective=objective,
            kernel=kernel,
            route_policy=route_policy,
            planning_policy=planning_policy,
        )
        selected_facets = {
            str(facet)
            for request in plan.evidence_requests
            for facet in request.requested_facet_ids
        }
        _require(
            selected_facets == set(facets)
            and not plan.deferred_atoms
            and len(plan.evidence_requests) == len(facets),
            "dynamic_multi_agent_role_plan_dropped_facet",
        )
        requests = [request.as_dict() for request in plan.evidence_requests]
        request_ids = [str(row["request_id"]) for row in requests]
        _require(
            not all_request_ids.intersection(request_ids),
            "dynamic_multi_agent_request_id_cross_role_duplicate",
        )
        all_request_ids.update(request_ids)
        catalog_rows = []
        request_ids_by_facet: dict[str, list[str]] = {facet: [] for facet in facets}
        for request in requests:
            request_facets = list(request.get("requested_facet_ids") or ())
            _require(
                len(request_facets) == 1 and request_facets[0] in facets,
                "dynamic_multi_agent_request_facet_invalid",
            )
            facet_id = str(request_facets[0])
            request_ids_by_facet[facet_id].append(str(request["request_id"]))
            catalog_rows.append(
                {
                    "request_id": str(request["request_id"]),
                    "proposition_id": "PROPOSITION::" + facet_id.upper(),
                    "coverage_group_ids": [facet_id],
                    "business_question_zh": str(
                        topology["facet_catalog"][facet_id]["business_scope_zh"]
                    ),
                    "facet_ids": request_facets,
                    "metric_intents": list(request.get("metric_intents") or ()),
                    "product_intents": list(request.get("product_intents") or ()),
                    "target_entities": list(request.get("target_entities") or ()),
                    "task_readiness_state": "current_runtime_request_not_yet_executed",
                    "actionable_gap_ids": [],
                    "request_payload": request,
                }
            )
        catalog_body = {
            "schema_version": "fin_ia_dynamic_specialist_request_catalog_v1_1",
            "case_key": str(trusted["case_identity"]["case_key"]),
            "research_as_of": str(trusted["case_identity"]["research_as_of"]),
            "agent_id": agent_id,
            "requests": sorted(catalog_rows, key=lambda row: row["request_id"]),
        }
        catalog = {
            **catalog_body,
            "catalog_digest": canonical_digest(catalog_body),
        }
        topology_role = topology_by_agent[agent_id]
        responsibility = " ".join(
            str(row) for row in topology_role.get("responsibilities") or ()
        )
        role_policy = {
            "schema_version": GENERIC_SPECIALIST_POLICY_SCHEMA_VERSION,
            "status": "current_runtime_dynamic_specialist_candidate",
            "case_identity": deepcopy(dict(trusted["case_identity"])),
            "objective": {
                "objective_id": objective.objective_id,
                "cell_id": str(role["cell_id"]),
                "agent_id": agent_id,
                "question_zh": str(role_objective_payload["raw_question"]),
            },
            "role_contract": {
                "agent_id": agent_id,
                "cell_id": str(role["cell_id"]),
                "responsibility": responsibility,
                "workpaper_rules": _role_workpaper_rules(agent_id=agent_id),
            },
            "source_refs": deepcopy(dict(trusted["source_refs"])),
            "loop_limits": {
                "maximum_retrieval_rounds": int(
                    trusted["loop_limits"][
                        "maximum_retrieval_rounds_per_specialist"
                    ]
                ),
                "maximum_request_ids_per_round": min(
                    int(trusted["loop_limits"]["maximum_request_ids_per_round"]),
                    len(requests),
                ),
                "maximum_total_request_ids": len(requests),
                "maximum_provider_steps": int(
                    trusted["loop_limits"]["maximum_provider_steps_per_specialist"]
                ),
                "repeated_request_forbidden": True,
                "candidate_text_model_visibility": False,
                "reviewed_evidence_excerpt_maximum_chars": int(
                    trusted["loop_limits"][
                        "reviewed_evidence_excerpt_maximum_chars"
                    ]
                ),
            },
            "coverage_groups": request_ids_by_facet,
            "token_budget_bases": _token_bases(
                agent_id=agent_id,
                responsibility=responsibility,
            ),
            "authority": {
                "initial_message_may_contain_evidence_or_numeric_facts": False,
                "model_selects_research_actions": True,
                "harness_owns_identity_dates_sources_budgets_and_request_compilation": True,
                "candidate_rank_grants_evidence": False,
                "model_may_self_authorize_public_information_gap": False,
                "graph_hypothesis_grants_fact_authority": False,
                "failed_attempts_are_immutable": True,
                "natural_model_authority_requires_separate_signed_run": True,
                "single_unit_success_does_not_claim_S1_or_S3_pass": True,
            },
        }
        load_dynamic_single_unit_policy(role_policy)
        program_body = {
            "agent_id": agent_id,
            "cell_id": str(role["cell_id"]),
            "facet_ids": facets,
            "quantitative_slot_ids": list(role["quantitative_slot_ids"]),
            "objective": objective.as_dict(),
            "planner_payload": planner_payload,
            "plan_digest": plan.plan_digest,
            "requests": requests,
            "request_catalog": catalog,
            "loop_policy": role_policy,
            "global_execution_ceiling_bypassed": False,
            "role_partition_precedes_request_execution": True,
        }
        programs.append(
            {**program_body, "role_program_digest": canonical_digest(program_body)}
        )
    _require(
        len(all_request_ids) == len(configured_facets),
        "dynamic_multi_agent_request_count_invalid",
    )
    body = {
        "schema_version": MULTI_AGENT_ROLE_PROGRAMS_SCHEMA_VERSION,
        "case_key": str(trusted["case_identity"]["case_key"]),
        "research_as_of": str(trusted["case_identity"]["research_as_of"]),
        "role_programs": programs,
        "summary": {
            "specialist_role_count": len(programs),
            "assigned_facet_count": len(configured_facets),
            "compiled_request_count": len(all_request_ids),
            "deferred_facet_count": 0,
            "independent_session_required_count": len(programs),
            "model_calls": 0,
            "network_calls": 0,
        },
        "authority": {
            "role_partition_occurs_before_execution_ceiling": True,
            "no_role_facet_silently_dropped": True,
            "request_catalog_contains_questions_not_answers": True,
            "live_execution_authorized": False,
        },
    }
    return {**body, "role_programs_digest": canonical_digest(body)}


def role_program_by_agent(
    role_programs: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    rows = {
        str(row.get("agent_id") or ""): deepcopy(dict(row))
        for row in role_programs.get("role_programs") or ()
        if isinstance(row, Mapping)
    }
    _require(
        list(rows) == list(SPECIALIST_AGENT_IDS),
        "dynamic_multi_agent_role_program_order_invalid",
    )
    return rows


def compile_role_material_requirement_blueprints(
    role_program: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Compile explicit, role-local material axes for current S1 retrieval.

    The model may choose *which* precompiled request to execute, but it cannot
    weaken the direct/bridge/context/counter evidence roles needed to answer the
    assigned financial proposition.  This also prevents the runtime fallback
    from silently treating a semantically related candidate as a complete set.
    """

    program = deepcopy(dict(role_program))
    agent_id = str(program.get("agent_id") or "")
    facet_scope = set(str(value) for value in program.get("facet_ids") or ())
    _require(
        agent_id in SPECIALIST_AGENT_IDS and bool(facet_scope),
        "dynamic_multi_agent_material_role_program_invalid",
    )
    blueprints: dict[str, dict[str, Any]] = {}
    for raw in program.get("requests") or ():
        request = deepcopy(dict(raw))
        request_id = str(request.get("request_id") or "")
        facets = _strings(
            request.get("requested_facet_ids"),
            "dynamic_multi_agent_material_request_facet_invalid",
            minimum=1,
            maximum=1,
        )
        facet_id = facets[0]
        roles = MATERIAL_ROLES_BY_FACET.get(facet_id)
        products = _strings(
            request.get("product_intents"),
            "dynamic_multi_agent_material_request_products_invalid",
            minimum=1,
        )
        entities = _strings(
            request.get("target_entities"),
            "dynamic_multi_agent_material_request_entities_invalid",
            minimum=1,
        )
        metrics = _strings(
            request.get("metric_intents"),
            "dynamic_multi_agent_material_request_metrics_invalid",
        )
        _require(
            bool(request_id)
            and facet_id in facet_scope
            and roles is not None
            and request_id not in blueprints,
            "dynamic_multi_agent_material_request_scope_invalid",
        )
        blueprints[request_id] = {
            "material_requirements": [
                {
                    "facet_id": facet_id,
                    "role": role,
                    "metric_ids": metrics if role in {"direct", "bridge"} else [],
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
    _require(
        len(blueprints) == len(facet_scope),
        "dynamic_multi_agent_material_request_set_invalid",
    )
    return blueprints


def compile_role_stop_decision(
    *,
    next_request_ids: Sequence[str],
    open_gap_refs: Sequence[str],
    feedback_refs: Sequence[str],
) -> str:
    """Separate catalog exhaustion from actual evidence sufficiency."""

    if next_request_ids:
        return "continue"
    if open_gap_refs or feedback_refs:
        return "stop_no_progress"
    return "stop_sufficient"


def normalize_bound_specialist_workpaper(
    payload: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
    expected_agent_id: str,
    allow_legacy_double_hash: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Revalidate a persisted workpaper and normalize one known digest defect.

    The canonical workpaper digest is produced by ``validate_specialist_workpaper``.
    An early zero-call runner then hashed that already-digested payload once more.
    This helper accepts that legacy value only when it is exactly reproducible from
    otherwise valid content.  It never repairs content, refs, identity, or context.
    """

    raw = deepcopy(dict(payload))
    supplied_digest = str(raw.pop("workpaper_digest", ""))
    supplied_context_digest = str(raw.pop("context_digest", ""))
    _require(
        bool(supplied_digest) and bool(supplied_context_digest),
        "dynamic_multi_agent_bound_workpaper_digest_missing",
    )
    validated = validate_specialist_workpaper(
        raw,
        context=context,
        expected_agent_id=expected_agent_id,
    )
    _require(
        supplied_context_digest == validated["context_digest"],
        "dynamic_multi_agent_bound_workpaper_context_invalid",
    )
    canonical_workpaper_digest = str(validated["workpaper_digest"])
    legacy_double_hash = canonical_digest(validated)
    if supplied_digest == canonical_workpaper_digest:
        digest_mode = "canonical"
    elif allow_legacy_double_hash and supplied_digest == legacy_double_hash:
        digest_mode = "legacy_double_hash_normalized"
    else:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_bound_workpaper_digest_invalid"
        )
    receipt_body = {
        "schema_version": WORKPAPER_DIGEST_NORMALIZATION_RECEIPT_SCHEMA_VERSION,
        "status": digest_mode,
        "agent_id": expected_agent_id,
        "context_digest": validated["context_digest"],
        "input_workpaper_digest": supplied_digest,
        "canonical_workpaper_digest": canonical_workpaper_digest,
        "legacy_double_hash_reproduced": supplied_digest == legacy_double_hash,
        "content_revalidated": True,
        "content_changed": False,
        "authority_refs_changed": False,
        "model_calls": 0,
        "network_calls": 0,
    }
    receipt = {
        **receipt_body,
        "receipt_digest": canonical_digest(receipt_body),
    }
    return validated, receipt


__all__ = [
    "DynamicMultiAgentLoopError",
    "MULTI_AGENT_LOOP_POLICY_SCHEMA_VERSION",
    "MULTI_AGENT_ROLE_PROGRAMS_SCHEMA_VERSION",
    "MATERIAL_ROLES_BY_FACET",
    "WORKPAPER_DIGEST_NORMALIZATION_RECEIPT_SCHEMA_VERSION",
    "compile_role_material_requirement_blueprints",
    "compile_role_stop_decision",
    "compile_dynamic_multi_agent_role_programs",
    "load_dynamic_multi_agent_loop_policy",
    "normalize_bound_specialist_workpaper",
    "role_program_by_agent",
]
