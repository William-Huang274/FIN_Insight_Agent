"""Real native graphs, scripted models: zero paid calls, not semantic gold."""
import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from langchain_core.messages import AIMessage

from sec_agent.agent_runtime.dell_case_convergence_agent import CaseReport, report_citations, build_case_output_agent
from sec_agent.agent_runtime.dell_report_session import build_report_session_graph, load_session_materials, ReviewAction
from apps.workbench.backend.api.v1.report_sessions import public_state, public_event, build_report_sessions_router
from test_dell_case_convergence_agent import NativeFixtureModel
from test_dell_case_review_agent import artifacts, call


def setup_session(artifacts):
    ref = "P01:" + artifacts.read_paper("P01", "claims")[0]["claim_id"]
    report = CaseReport(title="Synthetic report", narrative_markdown="Synthetic source-bound report; not real financial analysis. " * 6 + f"[{ref}]")
    review = {"summary": "Synthetic independent review for native graph qualification only.", "findings": [], "unresolved_data_requests": []}
    initial = {"report": {**report.model_dump(), "citations": report_citations(report, artifacts)}, "report_review": review, "revisions": {}}
    models = {role: NativeFixtureModel(marker=role+"-private", replies=[]) for role in ("writer", "verifier")}
    agents = {role: build_case_output_agent(role=role, model=models[role], tools=[], artifacts=artifacts,
        limits={"model_calls": 6, "tool_calls": 12}, report_revision=True, allow_answers=role == "writer") for role in models}
    graph = build_report_session_graph(**agents, artifacts=artifacts, initial=initial).compile(checkpointer=InMemorySaver())
    return graph, models, initial, ref


def test_native_open_question_revision_review_and_accept(artifacts):
    async def run():
        graph, models, initial, ref = setup_session(artifacts)
        config = {"configurable": {"thread_id": str(uuid4())}}
        opened = await graph.ainvoke({"open": True}, config)
        assert opened["__interrupt__"][0].value["kind"] == "dell_report_review"
        assert not models["writer"].contexts and not models["verifier"].contexts
        # Short answers must not inherit the full report's 200-character floor.
        answer = f"Test short source-bound answer. [{ref}]"
        models["writer"].replies = [[call("submit_case_answer", {"answer_markdown": answer}, "a1")]]
        asked = await graph.ainvoke(Command(resume={"action": "ask", "message": "Question about this evidence"}), config)
        assert asked["report"] == initial["report"] and asked["report_version"] == 1
        assert asked["conversation"][-1]["content"] == answer
        assert not models["verifier"].contexts
        new_report = {k: initial["report"][k] for k in ("title", "narrative_markdown")}
        new_report["narrative_markdown"] += " Revised."
        models["writer"].replies = [[call("submit_case_report", {"report": new_report}, "r1")]]
        models["verifier"].replies = [[call("submit_report_review", {"review": initial["report_review"]}, "v1")]]
        events = []
        async for e in graph.astream(Command(resume={"action": "revise", "message": "Explicit public feedback marker"}), config,
                stream_mode="custom", subgraphs=True, version="v2"):
            events.append(e)
        state = (await graph.aget_state(config)).values
        assert state["report_version"] == 2 and state["phase"] == "ready_for_human_review"
        assert state["report"]["narrative_markdown"].endswith("Revised.")
        assert initial["report"]["narrative_markdown"] != state["report"]["narrative_markdown"]
        assert "private" not in json.dumps(events) and len(events) == 4
        verifier_input = json.dumps([m.model_dump(mode="json") for m in models["verifier"].contexts[0]])
        assert "writer-private" not in verifier_input and "Explicit public feedback marker" not in verifier_input
        accepted = await graph.ainvoke(Command(resume={"action": "accept"}), config)
        assert accepted["phase"] == "human_reviewed_not_released"
        assert not (await graph.aget_state(config)).next
    asyncio.run(run())


def test_native_material_finding_remains_at_human_review(artifacts):
    async def run():
        graph, models, initial, ref = setup_session(artifacts)
        initial["report_review"]["findings"] = [{"severity": "material", "finding_id": "M1"}]
        config = {"configurable": {"thread_id": str(uuid4())}}
        await graph.ainvoke({"open": True}, config)
        with pytest.raises(ValueError, match="material_findings"):
            await graph.ainvoke(Command(resume={"action": "accept"}), config)
        assert not models["writer"].contexts
    asyncio.run(run())


def test_browser_projection_omits_private_native_state():
    state = {"values": {"report": {"title": "public"}, "messages": [{"reasoning_content": "PRIVATE"}],
        "phase": "needs_revision", "model_events": [{"event": "outcome", "actor": "writer", "total_tokens": 12, "raw_response": "PRIVATE"}],
        "revisions": {"raw": "PRIVATE"}}, "tasks": [{"state": {"messages": "PRIVATE"}, "interrupts": [
            {"id": "x", "value": {"kind": "dell_report_review"}}]}]}
    result = public_state(state)
    assert "PRIVATE" not in json.dumps(result) and result["can_respond"] and not result["can_accept"]
    assert public_event({"kind": "tool", "tool": "read_current_source", "arguments": "PRIVATE"}) == {"kind": "tool", "tool": "read_current_source"}
    assert public_event({"kind": "messages", "content": "PRIVATE"}) is None


def test_deployment_json_budget_and_schema_cache():
    from pathlib import Path
    from sec_agent.agent_runtime.dell_report_session import _schema_graph
    from sec_agent.agent_runtime.deepseek_structured_agents import TokenBudgetBasis
    path = Path("Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/report-workbench-20260906-a1/host-settings.json")
    if not path.is_file():
        pytest.skip("local deployment settings absent")
    data = json.loads(path.read_text(encoding="utf-8"))
    for value in data["node_budgets"].values():
        assert TokenBudgetBasis.model_validate_json(json.dumps(value)).required_outputs
    assert _schema_graph() is _schema_graph()


@pytest.mark.parametrize("body", [{"action": "shell", "message": "x"}, {"action": "ask", "path": "/secrets"},
    {"action": "revise", "message": "x"*16001}])
def test_only_narrow_human_actions_allowed(body):
    with pytest.raises(ValueError):
        ReviewAction.model_validate(body)


def test_cross_site_and_generic_proxy_rejected_without_sdk_calls():
    app = FastAPI()
    app.include_router(build_report_sessions_router(SimpleNamespace(sdk=None)), prefix="/api/v1")
    with TestClient(app) as client:
        assert client.post("/api/v1/research-sessions", json={}).status_code == 403
        assert client.post("/api/v1/research-sessions", json={}, headers={"x-workbench-request": "1", "origin": "https://evil.example"}).status_code == 403
        assert client.get("/api/v1/agent/threads/other/state").status_code == 404
