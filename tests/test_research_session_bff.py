"""New-task entry must select the native parent, never an archived report."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from apps.workbench.backend.api.v1.report_sessions import (
    ReportSessionService, build_report_sessions_router, public_event, public_state, GRAPH, RESEARCH_GRAPH,
)
from sec_agent.agent_runtime.research_session_runtime import load_research_runtime_profile, research_session_graph


def _app(*, enabled=True, graph_id=RESEARCH_GRAPH):
    calls = []
    thread_id, run_id = str(uuid4()), str(uuid4())
    thread = {"thread_id": thread_id, "status": "interrupted", "metadata": {"surface": "dell_report_workbench", "graph": graph_id}}
    async def create_thread(**kwargs):
        calls.append(("thread", kwargs))
        thread["metadata"] = kwargs["metadata"]
        return thread
    async def create_run(*args, **kwargs):
        calls.append(("run", args, kwargs))
        return {"run_id": run_id, "status": "pending"}
    async def get_thread(_):
        return thread
    async def get_state(_):
        return {"values": {"phase": "ready_for_human_review"}, "interrupts": [{"value": {"kind": "dell_report_review"}}]}
    service = ReportSessionService("http://127.0.0.1:18165", None, sdk=SimpleNamespace(
        threads=SimpleNamespace(create=create_thread, get=get_thread, get_state=get_state), runs=SimpleNamespace(create=create_run)),
        research_profile={"default_question": "A new bounded Dell growth-quality research question", "title": "New Dell research"} if enabled else None)
    app = FastAPI()
    app.include_router(build_report_sessions_router(service), prefix="/api/v1")
    return app, service, calls, thread_id


def test_new_task_and_review_remain_different_native_entries_and_fresh_has_no_seed():
    app, service, calls, _ = _app()
    with TestClient(app) as client:
        assert client.get("/api/v1/research-session-config").json()["fresh_research_enabled"]
        result = client.post("/api/v1/research-sessions", json={"mode": "research", "question": "A different actual user question about Dell growth quality"}, headers={"x-workbench-request": "1"})
        assert result.status_code == 200
        assert calls[-1][1][1] == RESEARCH_GRAPH
        payload = calls[-1][2]["input"]
        assert set(payload) == {"case_profile", "question"} and payload["question"].startswith("A different")
        assert calls[-1][2]["multitask_strategy"] == "reject"
        result = client.post("/api/v1/research-sessions", json={"mode": "review"}, headers={"x-workbench-request": "1"})
        assert result.status_code == 200 and calls[-1][1][1] == GRAPH and calls[-1][2]["input"] == {"open": True}
    asyncio.run(service.http.aclose())


def test_disabled_fresh_does_not_fallback_or_create_orphan_and_rejects_host_controls():
    app, service, calls, _ = _app(enabled=False)
    with TestClient(app) as client:
        result = client.post("/api/v1/research-sessions", json={"mode": "research"}, headers={"x-workbench-request": "1"})
        assert result.status_code == 503 and not calls
        for body in ({"graph": "arbitrary"}, {"seed_path": "D:/private"}, {"mode": "research", "question": " " * 20}, {"node_budgets": {}}):
            assert client.post("/api/v1/research-sessions", json=body, headers={"x-workbench-request": "1"}).status_code == 422
        assert not calls
    asyncio.run(service.http.aclose())


@pytest.mark.parametrize("graph_id", [GRAPH, RESEARCH_GRAPH])
def test_followup_uses_owned_session_graph_not_legacy_constant(graph_id):
    app, service, calls, thread_id = _app(graph_id=graph_id)
    with TestClient(app) as client:
        result = client.post(f"/api/v1/research-sessions/{thread_id}/actions", json={"action": "ask", "message": "Explain the source"},
                             headers={"x-workbench-request": "1"})
        assert result.status_code == 200 and calls[-1][1][1] == graph_id
        assert "command" in calls[-1][2] and "input" not in calls[-1][2]
    asyncio.run(service.http.aclose())


def test_public_task_projection_has_real_objective_and_dependencies_not_private_history():
    event = public_event({"kind": "task", "task_id": "T2", "actor": "finance", "event": "started", "objective": "Compare margins",
        "dependency_ids": ["T1"], "messages": [{"secret": "no"}], "reasoning_content": "private", "path": "D:/private"})
    assert event["dependency_ids"] == ["T1"] and "messages" not in event and "path" not in event
    projected = public_state({"values": {"question": "Research question", "case_papers": [{"notebook": "private source data"}],
        "research_tasks": [{"task_id": "T2", "objective": "Compare margins", "dependency_ids": ["T1"], "owner_role": "finance",
                            "hidden_reasoning": "private"}], "research_outcomes": [{"task_id": "T2", "status": "submitted"}]}})
    assert projected["research_tasks"][0]["status"] == "submitted"
    assert "case_papers" not in projected and "hidden_reasoning" not in str(projected)
    routed = public_event({"kind": "stage", "actor": "responsibility_router", "event": "handoff",
        "correction_round": 1, "responsible_paper_ids": ["P02", "D:/private"], "messages": ["private"]})
    assert routed["responsible_paper_ids"] == ["P02"] and routed["correction_round"] == 1 and "messages" not in routed
    history = public_state({"values": {"convergence_history": [{"actor": "synthesis", "correction_round": 0,
        "output": {"do_not_dump": "private trace"}}]}})
    assert history["responsibility_history"] == [{"actor": "synthesis", "correction_round": 0}]


def test_native_parent_schema_needs_no_credentials_or_archived_answer_and_role_budgets_are_valid():
    root = Path(__file__).resolve().parents[1]
    profile, case = load_research_runtime_profile(root)
    assert len(case["branch_topics"]) == 9 and profile["nodes"]["lead"]["profile"]["model"] == "deepseek-v4-flash"
    assert profile["nodes"]["specialist"]["profile"]["model"] == "deepseek-v4-pro"
    async def exercise():
        async with research_session_graph({}, SimpleNamespace(execution_runtime=None)) as graph:
            schema = graph.get_input_jsonschema()
            assert set(schema["properties"]) == {"case_profile", "question"}
            assert {"research", "case_review", "convergence", "human_review", "research_revision"}.issubset(graph.nodes)
    asyncio.run(exercise())


def test_direct_passage_and_calculation_operand_sources_remain_session_bound_and_paginated():
    app, service, _, thread_id = _app()
    sources = [{"source_id": "PASSAGE::current", "text": "A" * 17000,
                "source_url": "https://example.com/current", "numeric_fact_authority": False},
               {"source_id": "evidence-from-calculator", "text": "Exact reviewed source operand",
                "source_url": "https://example.com/operand", "numeric_fact_authority": False}]
    async def state(_):
        return {"values": {"research_synthesis": {"citations": {"PASSAGE::current": {"sources": [sources[0]]}}},
            "report": {"citations": {"CALC::current": {"sources": [sources[1]]}}}}}
    service.sdk.threads.get_state = state
    with TestClient(app) as client:
        path = f"/api/v1/research-sessions/{thread_id}/source"
        result = client.get(path, params={"source_id": "PASSAGE::current"})
        assert result.status_code == 200 and len(result.json()["text"]) == 16000
        assert result.json()["next_offset"] == 16000 and not result.json()["numeric_fact_authority"]
        last = client.get(path, params={"source_id": "PASSAGE::current", "offset": 16000}).json()
        assert last["text"] == "A" * 1000 and last["next_offset"] is None
        assert client.get(path, params={"source_id": "evidence-from-calculator"}).status_code == 200
        assert client.get(path, params={"source_id": "PASSAGE::other-task"}).status_code == 404
        assert client.get(path, params={"source_id": "D:/private"}).status_code == 404
        assert client.get(path, params={"source_id": "PASSAGE::current", "offset": -1}).status_code == 422
    asyncio.run(service.http.aclose())
