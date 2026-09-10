"""Native configuration consumption, isolation and public persistence checks."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from sec_agent.agent_runtime.studio_configuration import default_configuration, StudioConfiguration
from sec_agent.agent_runtime.dell_case_review_agent import build_case_review_graph
from apps.workbench.backend.api.v1.report_sessions import build_report_sessions_router
from apps.workbench.backend.api.v1.research_studio import STUDIO_SURFACE, run_configuration


@pytest.mark.parametrize("order,expected", [("parallel",None),("counter_first",["counter","verifier"]),("verifier_first",["verifier","counter"])])
def test_native_review_order_keeps_independent_messages(order,expected):
    visited=[]
    def reviewer(role):
        def call(state):
            assert len(state["messages"])==1
            assert f'"role": "{role}"' in state["messages"][0].content
            visited.append(role)
            return {"messages":[AIMessage(content="synthetic only")],"review":{"findings":[]}}
        return RunnableLambda(call)
    graph=build_case_review_graph(reviewers={r:reviewer(r) for r in ("counter","verifier")},
        artifacts=SimpleNamespace(catalog=lambda:{"papers":[]}),question="Synthetic configuration test",run_id="r",run_invocation_id="i",review_order=order).compile()
    result=graph.invoke({"run_id":"r","run_invocation_id":"i"})
    assert result["phase"]=="case_review_ready_for_convergence"
    assert set(visited)=={"counter","verifier"}
    if expected: assert visited==expected


def test_configuration_scope_and_run_isolation():
    base=default_configuration(); body=base.model_dump()
    body["methods"]["writer"] += "\nSTUDIO_TEST_METHOD_MARKER"
    body["max_parallel_tasks"]=1
    edited=StudioConfiguration.model_validate(body)
    assert "STUDIO_TEST_METHOD_MARKER" in edited.instructions("quick_writer")
    assert "STUDIO_TEST_METHOD_MARKER" not in base.instructions("quick_writer")
    profile={"max_parallel_tasks":2,"nodes":{"budget":"unchanged"}}
    assert edited.apply_profile(profile)=={"max_parallel_tasks":1,"nodes":{"budget":"unchanged"}}
    assert profile["max_parallel_tasks"]==2
    assert edited.method("writer")["configuration_digest"]==edited.digest
    for invalid in ({**body,"max_parallel_tasks":3},{**body,"bindings":{}},{**body,"review_order":"skip"},{**body,"model_budget":10}):
        with pytest.raises(ValidationError): StudioConfiguration.model_validate(invalid)


@pytest.mark.parametrize("revision_target", [None, {"paper_id": "P-development", "changed_claim_ids": []}])
def test_selected_method_reaches_native_agent_system_prompt(monkeypatch, revision_target):
    from sec_agent.agent_runtime import dell_case_convergence_agent as output
    from sec_agent.agent_runtime import dell_case_review_agent as review
    config=default_configuration()
    config.methods["writer"] += "\nSTUDIO_WRITER_CONSUMPTION_MARKER"
    config.methods["verifier"] += "\nSTUDIO_REVIEW_CONSUMPTION_MARKER"
    monkeypatch.setattr(output,"create_agent",lambda **kwargs:kwargs)
    class CapturedAgent(dict):
        output_channels = []
    monkeypatch.setattr(review,"create_agent",lambda **kwargs:CapturedAgent(kwargs))
    writer=output.build_case_output_agent(role="writer",model=None,tools=[],artifacts=None,
        limits={"model_calls":10,"tool_calls":32},method_instructions=config.instructions("quick_writer"),
        allow_answers=True,answer_only=True)
    from types import SimpleNamespace
    from sec_agent.agent_runtime.dell_reference_vertical_contracts import canonical_sha256
    artifacts = SimpleNamespace(read_paper=lambda _: {})
    if revision_target:
        revision_target = {**revision_target, "kind": "revision_only", "current_digest": canonical_sha256({})}
    verifier=review.build_case_reviewer(role="verifier",model=None,tools=[],artifacts=artifacts,
        method_instructions=config.instructions("verifier"), revision_target=revision_target)
    assert "STUDIO_WRITER_CONSUMPTION_MARKER" in writer["system_prompt"]
    assert "STUDIO_REVIEW_CONSUMPTION_MARKER" in verifier["system_prompt"]
    assert "STUDIO_WRITER_CONSUMPTION_MARKER" not in verifier["system_prompt"]
    assert any(t.name=="submit_case_answer" for t in writer["tools"])


def test_native_mcp_reads_run_bound_method_not_packaged_old_text():
    from mcp import Client
    from sec_agent.research_foundation.mcp_server import build_research_data_mcp_server, ResearchDataMCPDependencies
    config=default_configuration(); config.methods["finance"] += "\nRUN_SPECIFIC_METHOD"
    dependencies=ResearchDataMCPDependencies(method_reader=None,local_knowledge_reader=None,reviewed_evidence_search_reader=None,
        reviewed_evidence_reader=None,financial_fact_reader=None,external_discovery=None,external_capture=None)
    async def exercise():
        async with Client(build_research_data_mcp_server(dependencies,role_method_reader=config.method),raise_exceptions=False) as client:
            result=await client.call_tool("get_research_method",{"method_id":"finance"})
            assert not result.is_error
            assert "RUN_SPECIFIC_METHOD" in result.structured_content["content"]
            assert result.structured_content["configuration_digest"]==config.digest
    asyncio.run(exercise())


def test_specialist_method_is_inside_original_receipted_request():
    import json
    from test_dell_specialist_agentic_graph import _input, _action, _model_turn_receipt, _ToolPorts
    from sec_agent.agent_runtime.dell_specialist_agentic_graph import SpecialistAgenticInput, DellSpecialistAgenticDependencies, build_dell_specialist_agentic_state_graph
    from sec_agent.agent_runtime.studio_configuration import bind_specialist_method
    config=default_configuration();config.methods["finance"] += "\nSPECIALIST_INPUT_MARKER"
    original=SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    bound=bind_specialist_method(original,config.method("finance"))
    assert "SPECIALIST_INPUT_MARKER" not in original.model_dump_json()
    seen=[]
    def turn(request):
        seen.append(request)
        assert "SPECIALIST_INPUT_MARKER" in json.dumps(request,ensure_ascii=False)
        action={**_action("request_human_review",blocker_code="explicit_owner_review")(request), "context_digest":request["context_digest"]}
        receipt=_model_turn_receipt(request,action,kind="host",actor="dell_specialist_saved_response_replay",
            input_tokens=0,output_tokens=0,total_tokens=0,usage_reported=None)
        return {"action":action,"runtime_receipt":receipt}
    ports=_ToolPorts()
    graph=build_dell_specialist_agentic_state_graph(dependencies=DellSpecialistAgenticDependencies(
        model_turn=turn,evidence_tool=ports.evidence,finance_tool=ports.finance,turn_source="saved_response_replay")).compile()
    result=graph.invoke(bound.model_dump(mode="json"))
    assert result["phase"]=="specialist_human_review_handoff_emitted"
    assert len(seen)==1 and not ports.calls


def test_native_assistant_save_apply_and_run_snapshot():
    config=default_configuration(); aid=str(uuid4()); tid=str(uuid4())
    row={"assistant_id":aid,"graph_id":"research_session","config":{"configurable":{"finsight_studio":config.model_dump()}},
        "metadata":{"surface":STUDIO_SURFACE,"configuration_digest":config.digest}}
    thread={"thread_id":tid,"status":"interrupted","metadata":{"surface":"dell_report_workbench","graph":"research_session"}}
    assistants=SimpleNamespace(create=AsyncMock(return_value=row),get=AsyncMock(return_value=row),search=AsyncMock(return_value=[]))
    update=AsyncMock(); runs=SimpleNamespace(create=AsyncMock())
    service=SimpleNamespace(sdk=SimpleNamespace(assistants=assistants,threads=SimpleNamespace(update=update),runs=runs),owned_thread=AsyncMock(return_value=thread))
    app=FastAPI();app.include_router(build_report_sessions_router(service))
    with TestClient(app) as client:
        assert client.post("/research-studio/configurations",json=config.model_dump()).status_code==403
        headers={"X-Workbench-Request":"1"}
        saved=client.post("/research-studio/configurations",json=config.model_dump(),headers=headers)
        assert saved.status_code==200
        assert client.post(f"/research-studio/configurations/{aid}/apply",json={"thread_id":tid},headers=headers).status_code==200
        update.assert_awaited_once()
        thread["metadata"]["studio_assistant_id"]=aid
        snapshot=asyncio.run(run_configuration(service,thread))
        assert snapshot["configurable"]["finsight_studio"]==config.model_dump()
        thread["status"]="busy"
        assert client.post(f"/research-studio/configurations/{aid}/apply",json={"thread_id":tid},headers=headers).status_code==409
        runs.create.assert_not_awaited()
        row["config"]["configurable"]["finsight_studio"]["title"]="external mutation"
        assert client.get(f"/research-studio/configurations/{aid}").status_code==409
