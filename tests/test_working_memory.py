import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from sec_agent.agent_runtime.working_memory import WorkingMemory
from sec_agent.agent_runtime.working_memory_tools import execute_memory_tool, working_memory_tools
from sec_agent.agent_runtime.conversation_agent import GrantedTool, build_conversation_agent


def memory(tmp_path, actor="cash", owner="alice", workspace="study"):
    return WorkingMemory(tmp_path / "notes.sqlite", owner=owner, workspace=workspace, actor=actor)


def test_free_prose_survives_reopen_index_failure_and_revision(tmp_path, monkeypatch):
    paper = memory(tmp_path)
    def broken(*args):
        raise sqlite3.OperationalError("missing index")
    monkeypatch.setattr(WorkingMemory, "_index", broken)
    prose = "没按模板写。\n经营现金流增加，但还不能说利润增长全有现金支撑。\n\n|年|CFO|\n|---|---|\n|2025|45|"
    saved = paper.save("现金流判断", prose)
    assert saved["saved"] and not saved["indexed"]
    reopened = memory(tmp_path)
    assert reopened.read(saved["note_id"])["body"] == prose
    assert reopened.search("现金流")["items"][0]["id"] == saved["note_id"]
    assert reopened.search('" OR *')["items"] == []
    updated = reopened.save("现金流判断", "用户要求：删除非纯账面推断，仅保留同向增长。", 1)
    assert updated["version"] == 2
    assert reopened.read(saved["note_id"], version=1)["body"] == prose
    assert not reopened.save("现金流判断", "迟到的旧结论", 1)["saved"]
    assert reopened.search("经营现金流增加")["items"] == []


def test_scopes_peers_and_historical_read(tmp_path):
    note = memory(tmp_path).save("cash note", "CFO 45, Capex 25; FCF 20.")
    assert memory(tmp_path, actor="lead").read(note["note_id"])["found"]
    assert memory(tmp_path, owner="bob").search()["items"] == []
    assert not memory(tmp_path, owner="bob").read(note["note_id"], version=1)["found"]
    assert not memory(tmp_path, workspace="other").read(note["note_id"])["found"]
    assert memory(tmp_path, actor="lead").save("cash note", "another author")["note_id"] != note["note_id"]


def test_parallel_edits_do_not_overwrite_each_other(tmp_path):
    memory(tmp_path).save("current", "initial")
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda text: memory(tmp_path).save("current", text, 1), ["first", "second"]))
    assert sum(r["saved"] for r in results) == 1
    assert memory(tmp_path).search()["items"][0]["version"] == 2


def test_paging_and_export_preserve_all_text(tmp_path):
    prose = "ABC中文\n" * 4000
    paper = memory(tmp_path)
    note = paper.save("long", prose)
    assert paper.read(note["note_id"])["next_offset"] == 6000
    assert paper.export_markdown(note["note_id"])["markdown"] == prose


def test_native_tool_schema_and_errors_do_not_require_financial_form(tmp_path, monkeypatch):
    monkeypatch.setenv("FINSIGHT_WORKING_MEMORY_PATH", str(tmp_path / "notes.sqlite"))
    tools = {t.name:t for t in working_memory_tools("cash", owner="alice", workspace="study")}
    result = tools["WriteWorkingNote"].invoke({"title":"随手记", "body":"可能有关，尚未核实。"})
    assert result["saved"]
    result = tools["ReadWorkingNote"].invoke({"note_id":result["note_id"]})
    assert result["body"] == "可能有关，尚未核实。"
    assert isinstance(tools["WriteWorkingNote"].invoke({"title":"缺正文"}), str)
    monkeypatch.setenv("FINSIGHT_AUTH_MODE", "oidc_conversation_pilot")
    assert execute_memory_tool("WriteWorkingNote", {"title":"bad", "body":"bad"},
                               {"configurable":{"thread_id":"study"}}, "cash")["memory_available"] is False


def test_native_agent_writes_then_interrupts_and_reopens_checkpoint(tmp_path, monkeypatch):
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.tools import tool
    class Model(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self
    @tool
    def change_user_file():
        """Protected action used only to prove a real native interrupt."""
        raise AssertionError("must never execute")
    monkeypatch.setenv("FINSIGHT_WORKING_MEMORY_PATH", str(tmp_path / "notes.sqlite"))
    grants = [GrantedTool(t, "working_note_write" if t.name == "WriteWorkingNote" else "read", "研究工作底稿")
              for t in working_memory_tools("cash", owner="alice", workspace="study")]
    grants.append(GrantedTool(change_user_file, "user_file_change", "test temporary target"))
    responses = [AIMessage(content="", tool_calls=[{"name":"WriteWorkingNote", "args":{"title":"现金判断", "body":"本次只确定CFO增加；非纯账面尚未成立。"}, "id":"w1", "type":"tool_call"}]),
                 AIMessage(content="", tool_calls=[{"name":"change_user_file", "args":{}, "id":"guard", "type":"tool_call"}])]
    config={"configurable":{"thread_id":"study"}}
    with SqliteSaver.from_conn_string(str(tmp_path / "checkpoints.sqlite")) as saver:
        graph = build_conversation_agent(model=Model(responses=responses), grants=grants,
                                         permission_mode="request_standard", checkpointer=saver)
        result=graph.invoke({"messages":[HumanMessage(content="研究现金流并保存工作记录")]}, config)
        assert result.get("__interrupt__")
        assert memory(tmp_path).search()["items"][0]["title"] == "现金判断"
    with SqliteSaver.from_conn_string(str(tmp_path / "checkpoints.sqlite")) as saver:
        graph=build_conversation_agent(model=Model(responses=[AIMessage(content="收到，继续保留底稿。")]),
             grants=grants, permission_mode="request_standard", checkpointer=saver)
        assert graph.get_state(config).tasks[0].interrupts
        from langgraph.types import Command
        result=graph.invoke(Command(resume={"decisions":[{"type":"reject", "message":"不操作文件"}]}), config)
        assert result["messages"][-1].content == "收到，继续保留底稿。"
        assert memory(tmp_path).search("非纯账面")["items"]


def test_specialist_can_save_prose_before_formal_submission(tmp_path, monkeypatch):
    from test_dell_specialist_agentic_graph import _input, _ToolPorts
    from test_dell_specialist_tool_batch import _handoff
    from sec_agent.agent_runtime.dell_specialist_agentic_graph import (
        build_dell_specialist_agentic_state_graph, DellSpecialistAgenticDependencies)
    monkeypatch.setenv("FINSIGHT_WORKING_MEMORY_PATH", str(tmp_path / "notes.sqlite"))
    calls=[]
    def model(request):
        calls.append(request)
        if len(calls)>1:
            assert json.loads(request["tool_results"][0]["content"])["saved"]
            return _handoff(request)
        return {"action":"native_tool_batch", "context_digest":request["context_digest"], "tool_calls":[
            {"name":"WriteWorkingNote", "id":"note-specialist", "args":{"title":"未完成的工作", "body":"先记下来：现金流口径待核实。"}}]}
    ports=_ToolPorts()
    graph=build_dell_specialist_agentic_state_graph(dependencies=DellSpecialistAgenticDependencies(
        model_turn=model,evidence_tool=ports.evidence,finance_tool=ports.finance)).compile()
    result=graph.invoke(_input(), {"configurable":{"thread_id":"study"}})
    assert result["final_submission"] is None
    assert memory(tmp_path, owner="local-pilot").search("现金流")["items"]
    assert result["notebook"]["tool_action_count"] == 1


def test_lead_can_keep_free_notes_without_planning_schema(tmp_path, monkeypatch):
    from test_dell_lead_research_graph import _graph, _stop
    monkeypatch.setenv("FINSIGHT_WORKING_MEMORY_PATH", str(tmp_path / "notes.sqlite"))
    calls=[]
    def model(request):
        calls.append(request)
        if len(calls)>1:
            assert json.loads(request["tool_results"][0]["content"])["saved"]
            return _stop(request)
        return {"action":{"action":"native_tool_batch", "context_digest":request["context_digest"], "tool_calls":[
            {"name":"WriteWorkingNote", "id":"note-lead", "args":{"title":"当前方向", "body":"先看工作底稿，再决定是否补研。"}}]}}
    graph,value=_graph(model,lambda *args: (_ for _ in ()).throw(AssertionError("no workers")))
    graph.invoke(value.model_dump(mode="json"), {"configurable":{"thread_id":"study"}})
    assert memory(tmp_path, owner="local-pilot").search(actor="lead")["items"]


def test_bff_reads_current_history_and_refuses_wrong_owner(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from apps.workbench.backend.api.v1.conversations import build_conversations_router, SURFACE, GRAPH
    tid=str(uuid4())
    monkeypatch.setenv("FINSIGHT_WORKING_MEMORY_PATH", str(tmp_path / "notes.sqlite"))
    paper=memory(tmp_path, owner="local-pilot", workspace=tid)
    note=paper.save("观察", "第一版")
    paper.save("观察", "用户更正后的第二版", 1)
    thread={"metadata":{"surface":SURFACE, "graph":GRAPH, "owner_id":"local-pilot"}}
    async def get(_):return thread
    app=FastAPI();app.include_router(build_conversations_router(SimpleNamespace(sdk=SimpleNamespace(threads=SimpleNamespace(get=get)))))
    with TestClient(app) as client:
        url=f"/conversations/{tid}/working-notes"
        assert client.get(url).json()["items"][0]["version"] == 2
        assert client.get(url,params={"note_id":note["note_id"],"version":1,"download":True}).json()["markdown"] == "第一版"
        thread["metadata"]["owner_id"]="other"
        assert client.get(url).status_code==404


def test_handoff_pins_working_note_version_and_rechecks_owner(tmp_path, monkeypatch):
    import asyncio
    from uuid import uuid4
    from types import SimpleNamespace
    from sec_agent.agent_runtime.conversation_handoff import handoff_tools, SURFACE
    monkeypatch.setenv("FINSIGHT_WORKING_MEMORY_PATH", str(tmp_path / "notes.sqlite"))
    source_id, checkpoint=str(uuid4()), str(uuid4())
    paper=memory(tmp_path, workspace=source_id)
    note=paper.save("工作范围", "按用户意见，只描述同向变化。")
    refs=paper.manifest()
    paper.save("工作范围", "原窗口的后续独立版本", 1)
    source={"metadata":{"surface":SURFACE,"owner_id":"alice"}}
    async def get(_):return source
    async def state(*args, **kwargs):return {"values":{}}
    grants=handoff_tools(reference={"source_thread":source_id,"checkpoint_id":checkpoint,"working_notes":refs},
        sdk=SimpleNamespace(threads=SimpleNamespace(get=get,get_state=state)),owner_id="alice")
    reader=next(g.tool for g in grants if g.tool.name=="read_handoff_working_note")
    async def run():
        assert (await reader.ainvoke({}))["items"][0]["version"]==1
        result=await reader.ainvoke({"note_id":note["note_id"]})
        assert result["body"]=="按用户意见，只描述同向变化。" and not result["is_current"]
        source["metadata"]["owner_id"]="bob"
        assert "不可访问" in await reader.ainvoke({"note_id":note["note_id"]})
    asyncio.run(run())
