from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from retrieval.contracts import load_evidence_request, load_financial_research_kernel
from retrieval.route_compiler import (
    compile_retrieval_execution_plan,
    load_query_object_fact_route_policy,
)
from apps.workbench.backend.api.v1.research_retrieval import (
    build_research_retrieval_router,
)
from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from sec_agent.research.planning import (
    ResearchPlanningError,
    compile_research_objective,
    compile_research_planner_messages,
    compile_research_plan,
    load_research_planning_policy,
    parse_research_planner_output,
)
from sec_agent.research.material_scope import (
    compile_research_material_scope_messages,
)
from sec_agent.runtime_resource_registry import resolve_registered_runtime_resource


KERNEL_PATH = resolve_registered_runtime_resource(
    ROOT, "application.config.current_financial_research_kernel"
)
ROUTE_POLICY_PATH = resolve_registered_runtime_resource(
    ROOT, "application.config.current_query_object_fact_route_policy"
)
PLANNING_POLICY_PATH = resolve_registered_runtime_resource(
    ROOT, "application.config.current_research_planning_policy"
)
SUCCESSOR_KERNEL_PATH = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_1.json"
)
SUCCESSOR_ROUTE_POLICY_PATH = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_1.json"
)
SUCCESSOR_PLANNING_POLICY_PATH = (
    ROOT
    / "configs/research/fin_ia_0_1_3_s3_research_planning_policy_v1_2.json"
)
R1_ATOMS_PATH = (
    ROOT
    / "tests/fixtures/research/fin_ia_0_1_3_s3_dell_planner_r1_atoms_v1_0.json"
)


def _contracts():
    kernel = load_financial_research_kernel(
        json.loads(KERNEL_PATH.read_text(encoding="utf-8"))
    )
    route_policy = load_query_object_fact_route_policy(
        json.loads(ROUTE_POLICY_PATH.read_text(encoding="utf-8")),
        kernel,
    )
    planning_policy = load_research_planning_policy(
        json.loads(PLANNING_POLICY_PATH.read_text(encoding="utf-8")),
        route_policy,
    )
    return kernel, route_policy, planning_policy


def _successor_contracts():
    kernel = load_financial_research_kernel(
        json.loads(SUCCESSOR_KERNEL_PATH.read_text(encoding="utf-8"))
    )
    route_policy = load_query_object_fact_route_policy(
        json.loads(SUCCESSOR_ROUTE_POLICY_PATH.read_text(encoding="utf-8")),
        kernel,
    )
    planning_policy = load_research_planning_policy(
        json.loads(SUCCESSOR_PLANNING_POLICY_PATH.read_text(encoding="utf-8")),
        route_policy,
    )
    return kernel, route_policy, planning_policy


def test_successor_planning_policy_covers_new_s1c_facet_without_promoting_runtime() -> None:
    _, route_policy, planning_policy = _successor_contracts()

    assert set(planning_policy.facet_execution_priority) == set(
        route_policy.family_by_facet()
    )
    assert "downstream_demand_context" in planning_policy.facet_execution_priority
    active_policy = json.loads(PLANNING_POLICY_PATH.read_text(encoding="utf-8"))
    assert active_policy["schema_version"] == "fin_ia_research_planning_policy_v1_1"
    assert "downstream_demand_context" not in active_policy["atom_selection"][
        "facet_execution_priority"
    ]


def _objective_draft(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": "fin_ia_research_objective_draft_v1_0",
        "raw_question": (
            "Dell 的 AI 服务器需求是否真实且可持续，新增收入能否转化为利润和现金，"
            "哪些供应约束和反方证据会改变判断？"
        ),
        "task_type": "company_deep_dive",
        "case_key": "DELL",
        "required_slot_ids": [
            "demand_volume_quality",
            "operating_performance",
            "pricing_mix_value_capture",
            "cash_conversion_balance_sheet",
            "counterevidence_and_what_would_change",
        ],
        "allowed_source_types": ["10-K", "10-Q", "8-K"],
        "forbidden_source_types": [],
        "output_format": "investment_research_memo",
        "gap_policy": "return_typed_gap",
        "reviewer_role": "qualified_financial_research_reviewer",
        "period": {
            "start_date": "2025-02-01",
            "fiscal_years": [2026, 2027],
        },
        "budget": {
            "max_evidence_requests": 8,
            "max_metric_intents_per_request": 6,
            "max_product_intents_per_request": 4,
            "max_model_calls": 1,
        },
        "pass_criteria": [
            "identity_and_as_of_bound",
            "required_dimensions_covered",
            "numeric_facts_source_bound",
            "candidate_not_evidence_boundary_preserved",
            "counterevidence_and_what_would_change_present",
            "qualified_human_review_required",
        ],
    }
    value.update(overrides)
    return value


def _planner_atoms(**overrides: object) -> dict[str, object]:
    kernel, route_policy, planning_policy = _contracts()
    objective = compile_research_objective(
        _objective_draft(), kernel=kernel, policy=planning_policy
    )
    value: dict[str, object] = {
        "schema_version": "fin_ia_research_planner_atoms_v1_0",
        "objective_id": objective.objective_id,
        "atoms": [
            {
                "facet_id": "orders_and_backlog",
                "target_entity": "DELL",
                "metric_ids": [],
                "product_intents": ["AI-optimized servers", "orders and backlog"],
            },
            {
                "facet_id": "reported_results",
                "target_entity": "DELL",
                "metric_ids": ["revenue", "operating_income"],
                "product_intents": ["AI-optimized servers"],
            },
            {
                "facet_id": "margin_and_incremental_profit",
                "target_entity": "DELL",
                "metric_ids": ["gross_profit", "gross_margin"],
                "product_intents": ["AI-optimized servers", "ISG operating leverage"],
            },
            {
                "facet_id": "cash_generation",
                "target_entity": "DELL",
                "metric_ids": [
                    "operating_cash_flow",
                    "capital_expenditures",
                    "free_cash_flow",
                ],
                "product_intents": ["AI infrastructure working capital"],
            },
            {
                "facet_id": "issuer_counterevidence",
                "target_entity": "DELL",
                "metric_ids": [],
                "product_intents": [
                    "AI server demand durability",
                    "pricing pressure and customer concentration",
                ],
            },
        ],
    }
    value.update(overrides)
    return value


def _r1_planner_atoms() -> dict[str, object]:
    return json.loads(R1_ATOMS_PATH.read_text(encoding="utf-8"))


def test_objective_binds_identity_as_of_sources_budget_and_database_pass_rule() -> None:
    kernel, _, planning_policy = _contracts()
    objective = compile_research_objective(
        _objective_draft(), kernel=kernel, policy=planning_policy
    )

    assert objective.case_key == "DELL"
    assert objective.subject_ticker == "DELL"
    assert objective.subject_legal_name == "Dell Technologies Inc."
    assert objective.research_as_of.isoformat() == "2026-08-06"
    assert objective.period.end_date == objective.research_as_of
    assert "numeric_facts_source_bound" in objective.pass_criteria
    assert objective.budget.max_model_calls == 1


def test_bounded_atoms_compile_to_canonical_s1_and_s2_requests_deterministically() -> None:
    kernel, route_policy, planning_policy = _contracts()
    objective = compile_research_objective(
        _objective_draft(), kernel=kernel, policy=planning_policy
    )
    payload = _planner_atoms()
    plan = compile_research_plan(
        payload,
        objective=objective,
        kernel=kernel,
        route_policy=route_policy,
        planning_policy=planning_policy,
    )
    permuted = deepcopy(payload)
    permuted["atoms"] = list(reversed(permuted["atoms"]))
    same_plan = compile_research_plan(
        permuted,
        objective=objective,
        kernel=kernel,
        route_policy=route_policy,
        planning_policy=planning_policy,
    )

    assert len(plan.evidence_requests) == 5
    assert plan.plan_digest == same_plan.plan_digest
    assert [row.request_id for row in plan.evidence_requests] == [
        row.request_id for row in same_plan.evidence_requests
    ]
    assert {
        metric
        for request in plan.evidence_requests
        for metric in request.metric_intents
    } == {
        "revenue",
        "operating_income",
        "gross_profit",
        "gross_margin",
        "operating_cash_flow",
        "capital_expenditures",
        "free_cash_flow",
    }
    assert all(request.research_as_of == objective.research_as_of for request in plan.evidence_requests)
    assert all(request.target_entities == ("DELL",) for request in plan.evidence_requests)

    executions = [
        compile_retrieval_execution_plan(
            route_policy,
            request,
            fact_store_availability={"company_financial_fact_mart": True},
        )
        for request in plan.evidence_requests
    ]
    fact_requests = [row for execution in executions for row in execution.typed_fact_requests]
    assert len(fact_requests) == 7
    assert {row.storage_route for row in fact_requests} == {
        "company_financial_fact_mart"
    }
    assert all(row.execution_status == "ready_for_typed_fact_executor" for row in fact_requests)
    assert all(row.numeric_fact_authority is False for row in fact_requests)
    assert planning_policy.authority["database_lane_required_for_exact_numeric_authority"] is True


def test_saved_r1_proposals_are_selected_with_required_slots_and_stable_drop_reasons() -> None:
    kernel, route_policy, planning_policy = _contracts()
    objective = compile_research_objective(
        _objective_draft(), kernel=kernel, policy=planning_policy
    )
    payload = _r1_planner_atoms()
    plan = compile_research_plan(
        payload,
        objective=objective,
        kernel=kernel,
        route_policy=route_policy,
        planning_policy=planning_policy,
    )
    permuted = deepcopy(payload)
    permuted["atoms"] = list(reversed(permuted["atoms"]))
    same_plan = compile_research_plan(
        permuted,
        objective=objective,
        kernel=kernel,
        route_policy=route_policy,
        planning_policy=planning_policy,
    )

    assert len(plan.proposed_atoms) == 10
    assert len(plan.planner_atoms) == 8
    assert len(plan.evidence_requests) == 8
    assert plan.plan_digest == same_plan.plan_digest
    assert plan.selection == same_plan.selection
    assert plan.selection["proposal_ceiling"] == 12
    assert plan.selection["execution_request_budget"] == 8
    assert plan.selection["required_slot_ids_preserved"] == list(
        objective.required_slot_ids
    )
    assert {row.facet_id for row in plan.planner_atoms} == {
        "orders_and_backlog",
        "conversion_and_durability",
        "reported_results",
        "margin_and_incremental_profit",
        "cash_generation",
        "working_capital_risk",
        "issuer_counterevidence",
        "upstream_or_demand_counterevidence",
    }
    assert [row.atom.facet_id for row in plan.deferred_atoms] == [
        "guidance_and_outlook",
        "pricing_and_mix",
    ]
    assert {row.reason for row in plan.deferred_atoms} == {
        "execution_budget_exhausted_after_required_slot_and_"
        "provider_neutral_facet_priority_selection"
    }
    upstream_request = next(
        row
        for row in plan.evidence_requests
        if row.requested_facet_ids == ("upstream_or_demand_counterevidence",)
    )
    assert upstream_request.target_entities == (
        "NVDA",
        "MU",
        "TSM",
        "MSFT",
    )


def test_proposal_ceiling_and_all_proposed_atom_semantics_remain_fail_closed() -> None:
    kernel, route_policy, planning_policy = _contracts()
    objective = compile_research_objective(
        _objective_draft(), kernel=kernel, policy=planning_policy
    )
    excessive = _r1_planner_atoms()
    excessive["atoms"] = excessive["atoms"] + excessive["atoms"][:3]
    with pytest.raises(ResearchPlanningError, match="proposal_budget_invalid"):
        compile_research_plan(
            excessive,
            objective=objective,
            kernel=kernel,
            route_policy=route_policy,
            planning_policy=planning_policy,
        )

    invalid_deferred = _r1_planner_atoms()
    invalid_deferred["atoms"][3]["metric_ids"] = ["invented_metric"]
    with pytest.raises(ResearchPlanningError, match="metric_id_unknown"):
        compile_research_plan(
            invalid_deferred,
            objective=objective,
            kernel=kernel,
            route_policy=route_policy,
            planning_policy=planning_policy,
        )


def test_execution_budget_equal_to_required_slots_keeps_one_atom_per_slot() -> None:
    kernel, route_policy, planning_policy = _contracts()
    objective = compile_research_objective(
        _objective_draft(
            budget={
                "max_evidence_requests": 5,
                "max_metric_intents_per_request": 6,
                "max_product_intents_per_request": 4,
                "max_model_calls": 1,
            }
        ),
        kernel=kernel,
        policy=planning_policy,
    )
    payload = _r1_planner_atoms()
    payload["objective_id"] = objective.objective_id
    plan = compile_research_plan(
        payload,
        objective=objective,
        kernel=kernel,
        route_policy=route_policy,
        planning_policy=planning_policy,
    )

    assert len(plan.planner_atoms) == 5
    assert {
        next(
            slot.slot_id
            for slot in kernel.slots
            if any(facet.facet_id == atom.facet_id for facet in slot.facets)
        )
        for atom in plan.planner_atoms
    } == set(objective.required_slot_ids)


def test_planner_fails_closed_on_alias_unknown_metric_cross_case_and_scope_expansion() -> None:
    kernel, route_policy, planning_policy = _contracts()
    objective = compile_research_objective(
        _objective_draft(), kernel=kernel, policy=planning_policy
    )

    alias = _planner_atoms()
    alias["atoms"][3]["metric_ids"] = ["free cash flow"]
    with pytest.raises(ResearchPlanningError, match="metric_id_unknown"):
        compile_research_plan(
            alias,
            objective=objective,
            kernel=kernel,
            route_policy=route_policy,
            planning_policy=planning_policy,
        )

    cross_case = _planner_atoms()
    cross_case["atoms"][0]["target_entity"] = "ORCL"
    with pytest.raises(ResearchPlanningError, match="target_entity_invalid"):
        compile_research_plan(
            cross_case,
            objective=objective,
            kernel=kernel,
            route_policy=route_policy,
            planning_policy=planning_policy,
        )

    expanded = _planner_atoms()
    expanded["atoms"].append(
        {
            "facet_id": "capital_allocation",
            "target_entity": "DELL",
            "metric_ids": ["total_debt"],
            "product_intents": [],
        }
    )
    with pytest.raises(ResearchPlanningError, match="scope_expansion_forbidden"):
        compile_research_plan(
            expanded,
            objective=objective,
            kernel=kernel,
            route_policy=route_policy,
            planning_policy=planning_policy,
        )


def test_objective_and_plan_reject_future_period_budget_overrun_and_missing_dimension() -> None:
    kernel, route_policy, planning_policy = _contracts()
    future = _objective_draft(
        period={"start_date": "2026-08-07", "fiscal_years": [2027]}
    )
    with pytest.raises(ResearchPlanningError, match="period_invalid"):
        compile_research_objective(future, kernel=kernel, policy=planning_policy)

    excessive = _objective_draft(
        budget={
            "max_evidence_requests": 13,
            "max_metric_intents_per_request": 6,
            "max_product_intents_per_request": 4,
            "max_model_calls": 1,
        }
    )
    with pytest.raises(ResearchPlanningError, match="budget_invalid"):
        compile_research_objective(excessive, kernel=kernel, policy=planning_policy)

    objective = compile_research_objective(
        _objective_draft(), kernel=kernel, policy=planning_policy
    )
    incomplete = _planner_atoms()
    incomplete["atoms"] = incomplete["atoms"][:-1]
    with pytest.raises(ResearchPlanningError, match="required_slot_uncovered"):
        compile_research_plan(
            incomplete,
            objective=objective,
            kernel=kernel,
            route_policy=route_policy,
            planning_policy=planning_policy,
        )


def test_model_atom_cannot_inject_identity_period_source_or_request_id() -> None:
    kernel, route_policy, planning_policy = _contracts()
    objective = compile_research_objective(
        _objective_draft(), kernel=kernel, policy=planning_policy
    )
    injected = _planner_atoms()
    injected["atoms"][0]["research_as_of"] = "2027-01-01"

    with pytest.raises(ResearchPlanningError, match="atom_fields_invalid"):
        compile_research_plan(
            injected,
            objective=objective,
            kernel=kernel,
            route_policy=route_policy,
            planning_policy=planning_policy,
        )


def test_planner_prompt_is_compiled_from_active_facets_and_metric_routes() -> None:
    kernel, route_policy, planning_policy = _contracts()
    objective = compile_research_objective(
        _objective_draft(), kernel=kernel, policy=planning_policy
    )

    messages = compile_research_planner_messages(
        objective=objective,
        kernel=kernel,
        route_policy=route_policy,
        planning_policy=planning_policy,
    )
    visible = json.loads(messages[1]["content"])

    assert [row["slot_id"] for row in visible["allowed_slots_and_facets"]] == list(
        objective.required_slot_ids
    )
    facets = {
        facet["facet_id"]: facet
        for slot in visible["allowed_slots_and_facets"]
        for facet in slot["facets"]
    }
    assert "revenue" in facets["reported_results"]["allowed_metric_ids"]
    assert "free_cash_flow" in facets["cash_generation"]["allowed_metric_ids"]
    assert visible["output_contract"]["objective_id"] == objective.objective_id
    assert visible["objective"]["maximum_proposed_atoms"] == 12
    assert visible["objective"]["maximum_executed_evidence_requests"] == 8
    serialized = json.dumps(visible, ensure_ascii=False)
    assert "source_record_id" not in serialized
    assert "request_id" not in serialized


def test_planner_output_parser_requires_exact_json_before_semantic_compile() -> None:
    parsed = parse_research_planner_output(
        json.dumps(_planner_atoms(), ensure_ascii=False)
    )
    assert parsed["schema_version"] == "fin_ia_research_planner_atoms_v1_0"

    with pytest.raises(ResearchPlanningError, match="not_exact_json"):
        parse_research_planner_output(
            "```json\n" + json.dumps(_planner_atoms()) + "\n```"
        )
    with pytest.raises(ResearchPlanningError, match="json_invalid"):
        parse_research_planner_output("not-json")


def test_controlled_plan_product_surface_keeps_missing_database_as_s2_gaps(
    tmp_path: Path,
) -> None:
    kernel_payload = json.loads(KERNEL_PATH.read_text(encoding="utf-8"))
    route_payload = json.loads(ROUTE_POLICY_PATH.read_text(encoding="utf-8"))
    planning_payload = json.loads(PLANNING_POLICY_PATH.read_text(encoding="utf-8"))
    service = ResearchRetrievalService(
        snapshot=json.loads(
            (
                ROOT
                / "configs/runtime/fin_ia_0_1_3_current_retrieval_snapshot_v1_0.json"
            ).read_text(encoding="utf-8")
        ),
        kernel=kernel_payload,
        route_policy=route_payload,
        planning_policy=planning_payload,
        company_financial_fact_mart_path=tmp_path / "missing.sqlite",
    )
    principal = ResearchRetrievalPrincipal(
        mode="current",
        permissions=frozenset({"current_product:read"}),
    )

    projection = service.execute_controlled_plan(
        "DELL", _objective_draft(), _planner_atoms(), principal
    )

    assert projection["status"] == "controlled_research_plan_zero_call_executed"
    assert projection["summary"]["evidence_request_count"] == 5
    assert projection["summary"]["required_slot_count"] == 5
    assert projection["summary"]["compiled_lane_count"] == 5
    assert projection["summary"]["nonempty_lane_count"] == 5
    assert projection["summary"]["unique_narrative_candidates"] >= projection[
        "summary"
    ]["compiled_lane_count"]
    assert projection["summary"]["typed_fact_request_count"] == 7
    assert projection["summary"]["typed_fact_resolved_count"] == 0
    assert projection["summary"]["typed_fact_gap_count"] == 0
    assert projection["summary"]["typed_fact_conflict_count"] == 0
    assert projection["summary"]["numeric_fact_count"] == 0
    assert projection["summary"]["network_calls"] == 0
    assert projection["summary"]["model_calls"] == 0
    assert sum(
        row["summary"]["typed_gap_count"]
        for row in projection["request_results"]
    ) == 7
    assert all(
        gap["gap_code"] == "typed_fact_store_unavailable"
        for row in projection["request_results"]
        for gap in row["typed_gaps"]
        if gap.get("owning_stage") == "S2"
    )

    app = FastAPI()
    app.include_router(build_research_retrieval_router(service), prefix="/api/v1")
    response = TestClient(app).post(
        "/api/v1/research-cases/DELL/controlled-research-plans",
        json={"objective": _objective_draft(), "planner": _planner_atoms()},
        headers={
            "X-Fin-Product-Mode": "current",
            "X-Fin-Case-Permissions": "current_product:read",
        },
    )
    assert response.status_code == 200
    assert response.headers["etag"].startswith('"controlled-research-plan=')
    assert response.json()["projection_digest"] == projection["projection_digest"]


class _MaterialAwareHybridRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def retrieve_many(self, requests, **kwargs):
        self.calls.append(dict(kwargs))
        inputs = kwargs["material_runtime_inputs"]
        return tuple(
            {
                "request_id": request.request_id,
                "summary": {
                    "selected_count": 0,
                    "material_scope_ready": bool(
                        inputs[request.request_id].get("research_blueprint")
                    ),
                    "material_set_complete": False,
                },
                "candidates": [],
            }
            for request in requests
        )


def test_controlled_plan_material_scope_is_two_step_and_bound_to_current_plan(
    tmp_path: Path,
) -> None:
    kernel_payload = json.loads(KERNEL_PATH.read_text(encoding="utf-8"))
    route_payload = json.loads(ROUTE_POLICY_PATH.read_text(encoding="utf-8"))
    planning_payload = json.loads(PLANNING_POLICY_PATH.read_text(encoding="utf-8"))
    material_scope_policy = json.loads(
        (
            ROOT
            / "configs/research/fin_ia_0_1_3_s3_material_scope_policy_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    material_runtime_policy = json.loads(
        (
            ROOT
            / "configs/retrieval/fin_ia_0_1_3_s1_product_material_evidence_runtime_policy_v1_1.json"
        ).read_text(encoding="utf-8")
    )
    ontology = json.loads(
        (
            ROOT
            / "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_2.json"
        ).read_text(encoding="utf-8")
    )
    need_policy = json.loads(
        (
            ROOT
            / "configs/retrieval/fin_ia_0_1_3_s1_vs5_retrieval_need_compiler_policy_v1_2.json"
        ).read_text(encoding="utf-8")
    )
    hybrid = _MaterialAwareHybridRuntime()
    service = ResearchRetrievalService(
        snapshot=json.loads(
            (
                ROOT
                / "configs/runtime/fin_ia_0_1_3_current_retrieval_snapshot_v1_0.json"
            ).read_text(encoding="utf-8")
        ),
        kernel=kernel_payload,
        route_policy=route_payload,
        planning_policy=planning_payload,
        hybrid_candidate_runtime=hybrid,
        material_scope_policy=material_scope_policy,
        material_runtime_policy=material_runtime_policy,
        financial_intent_ontology=ontology,
        retrieval_need_policy=need_policy,
        company_financial_fact_mart_path=tmp_path / "missing.sqlite",
    )
    principal = ResearchRetrievalPrincipal(
        mode="current",
        permissions=frozenset({"current_product:read"}),
    )

    first = service.execute_controlled_plan(
        "DELL", _objective_draft(), _planner_atoms(), principal
    )
    required_ids = first["material_scope"]["required_request_ids"]
    assert first["schema_version"].endswith("v1_1")
    assert first["material_scope"]["mode"] == "explicit_scope_required"
    assert required_ids
    assert hybrid.calls[0]["material_runtime_inputs"]

    kernel = load_financial_research_kernel(kernel_payload)
    requests = [
        load_evidence_request(row, kernel)
        for row in first["compiled_plan"]["evidence_requests"]
    ]
    _, message = compile_research_material_scope_messages(
        research_plan_digest=first["compiled_plan"]["plan_digest"],
        requests=requests,
        required_request_ids=required_ids,
        policy=material_scope_policy,
        material_runtime_policy=material_runtime_policy,
        intent_ontology=ontology,
    )
    visible = json.loads(message["content"])
    scopes = []
    for row in visible["requests"]:
        dispositions = [
            {
                "product_intent_index": item["index"],
                "disposition": item["fixed_disposition"]
                or "contextual_retrieval_only",
            }
            for item in row["product_intents"]
        ]
        hard_indices = [
            item["product_intent_index"]
            for item in dispositions
            if item["disposition"] == "hard_material_axis"
        ]
        atoms = []
        for role in row["required_material_roles"]:
            axis = row["role_axis_contract"][role]
            atoms.append(
                {
                    "facet_id": row["facet_id"],
                    "role": role,
                    "metric_intent_indices": (
                        list(range(len(row["metric_intents"])))
                        if axis["bind_requested_metrics"]
                        else []
                    ),
                    "product_intent_indices": hard_indices,
                    "period_mode": "any",
                    "coverage_mode": "collective_axes",
                }
            )
        scopes.append(
            {
                "request_id": row["request_id"],
                "product_intent_dispositions": dispositions,
                "requirement_atoms": atoms,
            }
        )
    scope_payload = {
        "schema_version": "fin_ia_research_material_scope_atoms_v1_0",
        "research_plan_digest": first["compiled_plan"]["plan_digest"],
        "request_scopes": scopes,
    }

    second = service.execute_controlled_plan(
        "DELL",
        _objective_draft(),
        _planner_atoms(),
        principal,
        material_scope_payload=scope_payload,
    )

    assert second["material_scope"]["mode"] == (
        "explicit_request_visible_scope_compiled"
    )
    second_inputs = hybrid.calls[1]["material_runtime_inputs"]
    assert all(
        "research_blueprint" in second_inputs[request_id]
        for request_id in required_ids
    )
    assert second["material_scope"]["scope_compilation"]["summary"][
        "candidate_or_reference_inputs_read"
    ] is False
