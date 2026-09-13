"""Delegation uses real shared tools; fixtures never imply autonomous Lead proof."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.agent_runtime.specialist_composition import (
    SpecialistAgenticCompositionError, _bind_research_task,
    open_specialist_scripted_qualification_composition,
)
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticInput
from sec_agent.agent_runtime.deepseek_structured_agents import _project_agentic_specialist_request
from test_specialist_graph import _input
from test_workpaper_review_graph import _seed


def _assignment(branch="Q1_ISSUER_TRUTH", dependencies=(), capability="capability:dell:reviewed-evidence"):
    return {"task_id": "task:dell:price-financial-transmission", "owner_role": "supply_price_analyst",
            "objective": "核查供给和价格变化传导到 Dell 财务兑现的机制，明确观测与推断的界线。",
            "dependency_ids": list(dependencies), "coverage_obligation_ids": [branch],
            "success_criteria": ["结合上游底稿，自主读取来源；不将其他 Agent 的断言当成事实。"],
            "requested_capability_refs": [capability], "expected_output_kinds": ["branch_notebook", "claim_ledger"],
            "materiality": "high", "status": "planned"}


def test_assignment_is_bound_without_inheriting_authority_counts_or_source_observations():
    base = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    seed = _seed()
    original = deepcopy(seed)
    dep = seed["task"]["task_id"]
    assignment = _assignment(dependencies=(dep,))
    assignment["objective"] += "核查" * 1100  # Valid canonical TaskSpec must not be silently truncated.
    bound = _bind_research_task(base, assignment, {dep: seed})
    assert bound.task.objective == assignment["objective"]
    assert bound.task.task_id == assignment["task_id"] and bound.agent_id != base.agent_id
    assert bound.task.evidence_requests == base.task.evidence_requests
    assert bound.required_route_obligation_ids == base.required_route_obligation_ids
    assert bound.l0_context == base.l0_context
    assert bound.task_context["dependency_workpapers"][0]["workpaper"] == seed["final_submission"]
    assert "notebook" not in bound.task_context["dependency_workpapers"][0]
    assert seed == original


@pytest.mark.parametrize("defect", ["scope", "status", "missing_dependency", "identity", "as_of", "capability", "authority", "unfinished"])
def test_invalid_assignment_fails_before_model_or_data_tools(defect):
    base = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    seed = _seed()
    dep = seed["task"]["task_id"]
    task, dependencies = _assignment(dependencies=(dep,)), {dep: seed}
    if defect == "scope":
        task["coverage_obligation_ids"] = ["Q5_SUPPLY_AND_PRICE"]
    elif defect == "status":
        task["status"] = "completed"
    elif defect == "missing_dependency":
        dependencies = {}
    elif defect == "identity":
        task["dependency_ids"] = ["task:invented"]
        dependencies = {"task:invented": seed}
    elif defect == "as_of":
        seed["task"]["research_as_of"] = "2027-01-01T00:00:00Z"
    elif defect == "capability":
        task["requested_capability_refs"] = ["capability:arbitrary-shell"]
    elif defect == "authority":
        task["required_authority_refs"] = ["authority:admin"]
    else:
        seed["phase"] = "ready_for_model_decision"
    with pytest.raises((ValueError, SpecialistAgenticCompositionError)):
        _bind_research_task(base, task, dependencies)
