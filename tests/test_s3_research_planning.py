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

from retrieval.contracts import load_financial_research_kernel
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


KERNEL_PATH = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_0.json"
)
ROUTE_POLICY_PATH = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_0.json"
)
PLANNING_POLICY_PATH = (
    ROOT
    / "configs/research/fin_ia_0_1_3_s3_research_planning_policy_v1_0.json"
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
    with pytest.raises(ResearchPlanningError, match="compiled_request_invalid"):
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
    assert projection["summary"]["unique_narrative_candidates"] == 19
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
