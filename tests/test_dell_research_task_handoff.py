"""Delegation uses real shared tools; fixtures never imply autonomous Lead proof."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.agent_runtime.dell_specialist_agentic_composition import (
    DellSpecialistAgenticCompositionError, _bind_research_task,
    open_dell_specialist_scripted_qualification_composition,
)
from sec_agent.agent_runtime.dell_specialist_agentic_graph import SpecialistAgenticInput
from sec_agent.agent_runtime.deepseek_structured_agents import _project_agentic_specialist_request
from test_dell_specialist_agentic_graph import _input
from test_dell_workpaper_review_graph import _seed


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
    with pytest.raises((ValueError, DellSpecialistAgenticCompositionError)):
        _bind_research_task(base, task, dependencies)


@pytest.mark.local_data_integration
def test_actual_a5_issuer_artifact_to_delegated_supply_agent_real_mcp_no_model():
    from test_dell_specialist_agentic_composition import RUNTIME_ENVIRONMENT, _assert_assets
    _assert_assets()
    path = Path("Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/"
                "20260906-dell-q1-agentic-review-repair-a5/specialist-final-state.private.json")
    if not path.exists():
        pytest.skip("accepted A5 artifact unavailable")
    original = path.read_bytes()
    seed = json.loads(original)["values"]["target_state"]
    dep, seen = seed["task"]["task_id"], []
    task = _assignment("Q5_SUPPLY_AND_PRICE", (dep,), "capability:dell:source-document-read")

    def scripted(request):
        seen.append(request)
        if len(seen) == 1:
            return {"action": "request_source", "context_digest": request["context_digest"],
                    "reason_summary": "Zero-model delegated task qualification: inspect existing source catalog.",
                    "selection": {"operation": "catalog"}}
        if len(seen) == 2:
            return {"action": "request_finance", "context_digest": request["context_digest"],
                    "reason_summary": "Zero-model delegated task qualification: verify real S2 tool binding.",
                    "intent": {"ticker": "DELL", "metric_ids": ["revenue"], "granularity": "quarter_discrete",
                               "selection_mode": "exact_period_end", "period_end": "2026-05-01"}}
        return {"action": "request_human_review", "context_digest": request["context_digest"],
                "reason_summary": "Scripted MCP qualification completed; no financial or Lead verdict produced.",
                "blocker_code": "scripted_task_handoff_qualification_complete"}

    with open_dell_specialist_scripted_qualification_composition(
        run_id="task-handoff-qualification", run_invocation_id="task-handoff-qualification-1",
        branch_id="Q5_SUPPLY_AND_PRICE", environment=RUNTIME_ENVIRONMENT, source_read_enabled=True,
        scripted_model_turn=scripted, research_task=task, dependency_workpapers={dep: seed}) as opened:
        result = opened.graph.invoke(opened.graph_input.model_dump(mode="json"))
    assert len(seen) == 3 and result["notebook"]["tool_action_count"] == 2
    assert len(result["notebook"]["observations"]) == 2  # Not the inherited source notebook's 9 observations.
    assert all(row["status"] == "success" for row in result["notebook"]["observations"]), [
        (row["status"], row["failure"], [item.get("typed_gap") for item in row["content"]])
        for row in result["notebook"]["observations"] if row["status"] != "success"]
    assert all(not row["model_execution_evidence"] for row in result["notebook"]["model_turn_records"])
    view = _project_agentic_specialist_request(seen[0])
    assert view["task_context"]["assignment"]["task_id"] == task["task_id"]
    assert view["task_context"]["dependency_workpapers"][0]["task_id"] == dep
    assert view["task_context"]["dependency_workpapers"][0]["workpaper"]["claims"] == seed["final_submission"]["claims"]
    assert "reasoning_content" not in json.dumps(view) and "model_turn_records" not in json.dumps(view)
    assert result["final_submission"] is None and path.read_bytes() == original
