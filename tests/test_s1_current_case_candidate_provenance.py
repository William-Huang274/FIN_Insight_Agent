from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from retrieval.contracts import load_financial_research_kernel
from retrieval.material_evidence_runtime import (
    compile_material_requirement_plan_from_runtime_input,
)
from retrieval.route_compiler import load_query_object_fact_route_policy
from scripts.research.run_s3_material_scope_canary import (
    _public_product_replay_projection,
)
from sec_agent.research.planning import (
    compile_research_objective,
    compile_research_plan,
    load_research_planning_policy,
)


def _json(ref: str) -> dict:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


KERNEL_REF = (
    "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_2.json"
)
ROUTE_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_2.json"
)
PLANNING_REF = (
    "configs/research/fin_ia_0_1_3_s3_research_planning_policy_v1_1.json"
)
RUNTIME_POLICY_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_product_material_evidence_runtime_policy_v1_0.json"
)
ONTOLOGY_REF = (
    "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_2.json"
)


def _compiled(case_key: str):
    case = case_key.casefold()
    kernel = load_financial_research_kernel(_json(KERNEL_REF))
    route = load_query_object_fact_route_policy(_json(ROUTE_REF), kernel)
    planning = load_research_planning_policy(_json(PLANNING_REF), route)
    objective_payload = _json(
        "configs/research/evals/"
        f"fin_ia_0_1_3_s1_{case}_current_candidate_provenance_"
        "objective_v1_0.json"
    )
    atom_payload = _json(
        "configs/research/evals/"
        f"fin_ia_0_1_3_s1_{case}_current_candidate_provenance_atoms_v1_0.json"
    )
    objective = compile_research_objective(
        objective_payload, kernel=kernel, policy=planning
    )
    plan = compile_research_plan(
        atom_payload,
        objective=objective,
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
    )
    return objective_payload, atom_payload, plan


def test_mu_and_nvda_current_inputs_are_zero_model_case_bound_and_split_safe() -> None:
    for case_key in ("MU", "NVDA"):
        objective, atoms, plan = _compiled(case_key)
        serialized = json.dumps(
            {"objective": objective, "atoms": atoms},
            ensure_ascii=False,
        ).casefold()
        assert objective["budget"]["max_model_calls"] == 0
        assert objective["case_key"] == case_key
        assert all(row.target_entity == case_key for row in plan.proposed_atoms)
        assert len(plan.proposed_atoms) == 10
        assert len(plan.planner_atoms) == 8
        assert len(plan.deferred_atoms) == 2
        assert "qrel" not in serialized
        assert "gold" not in serialized
        assert "hidden" not in serialized


def test_mu_and_nvda_selected_requests_have_deterministic_material_scope() -> None:
    runtime_policy = _json(RUNTIME_POLICY_REF)
    ontology = _json(ONTOLOGY_REF)
    for case_key in ("MU", "NVDA"):
        _, _, plan = _compiled(case_key)
        for request in plan.evidence_requests:
            payload = request.as_dict()
            runtime_input = {
                "evidence_request": payload,
                "retrieval_execution_plan": {
                    "narrative_requests": [
                        {
                            "facet_ids": payload["requested_facet_ids"],
                            "metric_context_ids": payload["metric_intents"],
                            "product_intents": payload["product_intents"],
                        }
                    ]
                },
            }
            requirement_plan, receipt = (
                compile_material_requirement_plan_from_runtime_input(
                    runtime_input=runtime_input,
                    policy=runtime_policy,
                    ontology=ontology,
                )
            )
            assert receipt["compiler_mode"] == (
                "deterministic_narrative_plan_fallback"
            )
            assert receipt[
                "explicit_blueprint_required_for_full_product_scope"
            ] is False
            assert receipt["candidate_or_reference_inputs_read"] is False
            assert receipt["generation_model_calls"] == 0
            assert requirement_plan["requirement_groups"]


def test_public_projection_treats_deterministic_scope_as_executed_scope() -> None:
    projection = {
        "case_key": "MU",
        "projection_digest": "projection",
        "compiled_plan": {"plan_digest": "plan"},
        "material_scope": {
            "mode": "deterministic_scope_ready",
            "required_request_ids": [],
            "fallback_compiler_receipts": [
                {"receipt_digest": "a" * 64}
            ],
        },
        "summary": {
            "evidence_request_count": 1,
            "material_scope_required_request_count": 0,
            "material_scope_ready_request_count": 1,
            "material_set_complete_request_count": 0,
        },
        "request_results": [],
    }
    public = _public_product_replay_projection(projection)
    assert public["status"] == "completed_scope_ready_material_sets_incomplete"
    assert public["fallback_compiler_receipt_digests"] == ["a" * 64]
