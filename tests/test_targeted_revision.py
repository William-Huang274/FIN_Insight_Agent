"""Native checkpoint and BFF qualification with scripted handlers; no provider calls."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from sec_agent.agent_runtime.report_session import build_report_session_graph, ReviewAction
from sec_agent.agent_runtime.targeted_revision import report_digest, RevisionTarget
from apps.workbench.backend.api.v1.report_sessions import build_report_sessions_router


def material():
    return {"report": {"title": "Synthetic", "narrative_markdown": "Cash conversion [C1]", "citations": {
        "C1": {"claim": {"statement": "Synthetic original claim"}, "sources": [{"source_id": "P01:S001"}]}}},
        "report_review": {"findings": [], "unresolved_data_requests": []}, "revisions": {}}


def target(values, checkpoint):
    return {"request_id": str(uuid4()), "citation_id": "C1", "base_version": values["report_version"],
            "base_digest": report_digest(values["report"]), "base_checkpoint": checkpoint}


@pytest.mark.parametrize("invalid", [None, "digest", "claim", "duplicate"])
def test_native_target_checks_precede_revision_and_old_checkpoint_survives(invalid):
    async def run():
        calls = []
        initial = material()
        async def revise(state):
            calls.append(deepcopy(state))
            return {"report": {**state["report"], "narrative_markdown": "Revised [C1]"}, "report_version": 2,
                    "report_review": initial["report_review"], "phase": "ready_for_human_review"}
        async def unexpected(_): raise AssertionError("wrong runtime entry")
        graph = build_report_session_graph(writer=RunnableLambda(unexpected), verifier=RunnableLambda(unexpected),
            artifacts=None, initial=initial, revision_handler=revise).compile(checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": str(uuid4())}}
        await graph.ainvoke({"open": True}, config)
        before = await graph.aget_state(config)
        data = target(before.values, before.config["configurable"]["checkpoint_id"])
        if invalid == "digest": data["base_digest"] = "0" * 64
        if invalid == "claim": data["citation_id"] = "C999"
        if invalid in {"digest", "claim"}:
            with pytest.raises(ValueError): await graph.ainvoke(Command(resume={"action": "revise", "message": "Review", "target": data}), config)
            assert not calls
        else:
            await graph.ainvoke(Command(resume={"action": "revise", "message": "Review this exact claim", "target": data}), config)
            after = await graph.aget_state(config)
            assert after.values["report_version"] == 2 and len(calls) == 1
            assert "Synthetic original claim" in calls[0]["message"] and "P01:S001" in calls[0]["message"]
            assert calls[0]["revision_target"]["citation_id"] == "C1"
            assert (await graph.aget_state(before.config)).values["report"] == initial["report"]
            if invalid == "duplicate":
                data.update(base_version=2, base_digest=report_digest(after.values["report"]))
                with pytest.raises(ValueError, match="已处理"):
                    await graph.ainvoke(Command(resume={"action": "revise", "message": "Again", "target": data}), config)
                assert len(calls) == 1
    asyncio.run(run())


def test_bff_rejects_stale_and_unknown_target_and_recovers_duplicate_request():
    values = {**material(), "report_version": 1}
    state = {"values": values, "tasks": [{"name": "human_review", "interrupts": [{"value": {"kind": "dell_report_review"}}]}], "next": ["human_review"]}
    checkpoint = str(uuid4()); data = target(values, checkpoint)
    stored, calls = [], []
    async def owned(_): return {"metadata": {"surface": 'research_workbench'}}
    async def get_state(_): return state
    async def report_state(*_): return {"values": values}
    async def all_runs(_): return stored
    async def create(*args, **kwargs):
        calls.append(kwargs)
        row = {"run_id": str(uuid4()), "status": "pending", "metadata": kwargs["metadata"]}
        stored.append(row); return row
    service = SimpleNamespace(owned_thread=owned, state=get_state, report_state=report_state, all_runs=all_runs,
                             sdk=SimpleNamespace(runs=SimpleNamespace(create=create)))
    app = FastAPI(); app.include_router(build_report_sessions_router(service), prefix="/api/v1")
    with TestClient(app) as client:
        path = f"/api/v1/research-sessions/{uuid4()}/actions"; headers = {"x-workbench-request": "1"}
        body = {"action": "revise", "message": "Check the original source", "target": data}
        assert client.post(path, json=body).status_code == 403
        assert client.post(path, json={**body, "target": {**data, "base_digest": "0" * 64}}, headers=headers).status_code == 409
        assert client.post(path, json={**body, "target": {**data, "citation_id": "missing"}}, headers=headers).status_code == 409
        first = client.post(path, json=body, headers=headers)
        assert first.status_code == 200, first.text
        second = client.post(path, json=body, headers=headers)
        assert second.json()["run_id"] == first.json()["run_id"] and second.json()["existing_request"]
        assert client.post(path, json={**body, "message": "Different"}, headers=headers).status_code == 409
        assert len(calls) == 1 and calls[0]["multitask_strategy"] == "reject"
        assert calls[0]["command"]["resume"]["target"] == data


def test_target_cannot_change_action_or_inject_runtime_nodes():
    data = target({**material(), "report_version": 1}, str(uuid4()))
    with pytest.raises(ValueError): ReviewAction(action="ask", target=RevisionTarget(**data))
    with pytest.raises(ValueError): RevisionTarget(**data, goto="writer")
