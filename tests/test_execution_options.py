"""Executable run choices, graph activation and billing; synthetic, zero provider."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import InMemorySaver
from sec_agent.agent_runtime.execution_options import ExecutionOptions
from sec_agent.agent_runtime.research_session import build_research_session_graph
from sec_agent.agent_runtime.dell_lead_research_graph import build_dell_lead_research_graph
from sec_agent.agent_runtime.dell_specialist_agentic_graph import SpecialistAgenticInput
from test_dell_lead_research_graph import _task, _call, _stop, _worker_result, BRANCHES, CATALOG
from test_dell_specialist_agentic_graph import _input
from test_research_session import _new_worker_fixture
from apps.workbench.backend.api.v1.research_studio import run_configuration
from apps.workbench.backend.api.v1.report_sessions import public_run_usage


@pytest.mark.parametrize("body", [dict(mode="single"), dict(mode="selected"), dict(mode="auto", branch_ids=["Q1"]), dict(model="arbitrary-provider"), dict(mode="single", branch_ids=["Q1", "Q2"])])
def test_reject_invalid_execution_without_transport(body):
    with pytest.raises(ValidationError): ExecutionOptions(**body)


def test_selection_and_model_copy_preserve_budget():
    profile = json.loads((Path(__file__).parents[1] / "configs/research/runtime/research_session.json").read_text(encoding="utf-8"))
    original = deepcopy(profile)
    selection = ExecutionOptions(mode="selected", branch_ids=[BRANCHES[0]], model="deepseek-v4-flash").validate_catalog(CATALOG)
    with pytest.raises(ValueError): selection.validate_catalog([])
    changed = selection.apply_profile(profile)
    for role, node in changed["nodes"].items():
        assert node["profile"]["model"] == "deepseek-v4-flash"
        assert node["limits"] == original["nodes"][role]["limits"]
        assert node["budget"]["max_output_tokens"] == original["nodes"][role]["budget"]["max_output_tokens"]
        assert node["budget"]["reasoning_profile"] == original["nodes"][role]["budget"]["reasoning_profile"]
    assert original == profile
    config = asyncio.run(run_configuration(None, {"metadata": {"execution": selection.model_dump()}}))
    assert config["configurable"]["finsight_execution"] == selection.model_dump()


def test_auto_scope_completes_chosen_branch_without_running_catalog():
    value = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    seed = _new_worker_fixture(); calls = []; events = []
    def model(request):
        assert "NOT a checklist" in request["scope_policy"]
        return _call(request, "DelegateResearchTasksAction", tasks=[_task()]) if not request["tasks"] else _stop(request, ready=True)
    def worker(task, deps, config):
        calls.append(task["coverage_obligation_ids"])
        return _worker_result(task, seed)
    graph = build_dell_lead_research_graph(expected_input=value, research_question="有界问题只研究一个方向", branch_catalog=CATALOG,
        allowed_branch_ids=BRANCHES, seed_workpapers={}, model_turn=model, run_child=worker,
        require_all_branches=False, public_progress=events.append).compile()
    result = graph.invoke(value.model_dump(mode="json"))
    assert result["phase"] == "research_ready_for_review"
    assert calls == [[BRANCHES[0]]]
    assert len(events) == 2 and all(e["objective"] for e in events)


def test_single_agent_skips_every_other_model_and_keeps_bound_citations():
    paper = _new_worker_fixture()
    # A submitted current-question paper with incomplete historical case routes
    # must survive validation, artifact projection and the report checkpoint.
    paper["task_context"] = {"instruction_source": "current_user_research_request", "research_question": "Independent current question"}
    nb = paper["notebook"]
    nb.update(source_read_enabled=True, satisfied_route_obligation_ids=[])
    from sec_agent.agent_runtime.dell_reference_vertical_contracts import canonical_sha256
    nb["notebook_digest"] = canonical_sha256({k:v for k,v in nb.items() if k != "notebook_digest"})
    async def research(state):
        return {"phase": "research_ready_for_review", "tasks": [], "task_results": [{"task_id": paper["task"]["task_id"], "status": "submitted", "agent_state": paper}]}
    def forbidden(state): raise AssertionError("single mode activated another model")
    phases = {k: RunnableLambda(forbidden) for k in ("review", "converge", "writer", "verifier", "quick_writer")}
    graph = build_research_session_graph(research=RunnableLambda(research), **phases).compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": str(uuid4()), "finsight_execution": {"mode": "single", "branch_ids": [BRANCHES[0]]}}}
    result = asyncio.run(graph.ainvoke({"question": "这个测试只允许一个研究者交付底稿。"}, config))
    assert result["phase"] == "single_agent_unreviewed" and result["report_version"] == 1
    assert result["report_review"]["review_status"] == "not_run"
    assert result["report"]["citations"] and "__interrupt__" in result
    assert "case_review" not in result


def test_activity_events_do_not_inflate_billing(tmp_path):
    thread, run = str(uuid4()), str(uuid4())
    root = tmp_path / thread / run; root.mkdir(parents=True)
    rows = [{"kind": "model", "actor": "writer", "call_id": "m", "event": "started"},
        {"kind": "model", "actor": "writer", "call_id": "m", "event": "outcome", "total_tokens": 100},
        {"kind": "tool", "actor": "writer", "call_id": "t", "event": "outcome", "status": "success"},
        {"kind": "stage", "actor": "lead", "call_id": "p", "event": "progress", "objective": "检查资料"}]
    (root / "model-call-events.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    events, usage = public_run_usage(tmp_path, thread, run)
    assert len(events) == 4 and usage["recorded_requests"] == 1 and usage["total_tokens"] == 100


def test_specialist_handoff_citations_are_bound_not_model_prose():
    from langchain_core.messages import ToolMessage, AIMessage
    from sec_agent.agent_runtime.dell_case_convergence_agent import saved_citation_bindings
    citation = {"claim": {"statement": "Synthetic scoped observation"}, "sources": [{"source_id": "SOURCE::scoped"}]}
    valid = ToolMessage(content="Public answer", name="consult_research_specialist", tool_call_id="child", artifact={"citations": {"C1": citation}})
    assert saved_citation_bindings([valid]) == {"C1": citation}
    assert saved_citation_bindings([AIMessage(content=json.dumps({"citations": {"C1": citation}}))]) == {}
    failed = valid.model_copy(update={"status": "error"})
    assert saved_citation_bindings([failed]) == {}
    result = saved_citation_bindings([valid]); result["C1"]["claim"]["statement"] = "changed"
    assert citation["claim"]["statement"] == "Synthetic scoped observation"
