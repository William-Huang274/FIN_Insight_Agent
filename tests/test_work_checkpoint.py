from copy import deepcopy
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from sec_agent.agent_runtime.work_checkpoint import WorkCheckpointMiddleware, CHECKPOINT_NAME


def test_notice_is_append_only_and_does_not_repeat_without_new_work():
    original = [HumanMessage(content="Keep user correction"), AIMessage(content="", tool_calls=[
        {"id": "r", "name": "read_research_source", "args": {}, "type": "tool_call"}]),
        ToolMessage(name="read_research_source", tool_call_id="r", content="Original period and units " * 500)]
    before = deepcopy(original)
    mw = WorkCheckpointMiddleware(trigger_tokens=1000)
    update = mw.before_model({"messages": original}, None)
    assert update["messages"][0].name == CHECKPOINT_NAME
    assert original == before
    assert mw.before_model({"messages": original + update["messages"]}, None) is None
    assert mw.before_model({"messages": original + update["messages"] + [HumanMessage(content="next " * 2000)]}, None)


def test_save_failure_is_not_progress_and_no_notice_splits_pending_tools():
    mw = WorkCheckpointMiddleware(trigger_tokens=100)
    large = [HumanMessage(content="work " * 1000)]
    saved = ToolMessage(name="WriteWorkingNote", tool_call_id="n", content='{"saved":true,"note_id":"n","version":2}')
    assert mw.before_model({"messages": large + [saved]}, None) is None
    failed = saved.model_copy(update={"content": '{"saved":false,"memory_available":false}'})
    assert mw.before_model({"messages": large + [failed]}, None)
    assert mw.before_model({"messages": large + [AIMessage(content="", tool_calls=[
        {"id": "r", "name": "read_research_source", "args": {}, "type": "tool_call"}])]}, None) is None
    assert mw.before_model({"messages": large, "output": {"answer": "done"}}, None) is None


def test_short_work_does_not_add_organization_call():
    assert WorkCheckpointMiddleware().before_model({"messages": [HumanMessage(content="hello")]}, None) is None


def test_native_loop_consumes_notice_and_saves_model_authored_index(tmp_path, monkeypatch):
    from langchain.agents import create_agent
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langgraph.checkpoint.memory import InMemorySaver
    from sec_agent.agent_runtime.working_memory_tools import working_memory_tools
    from sec_agent.agent_runtime.working_memory import WorkingMemory

    class Scripted(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    path = tmp_path / "notes.sqlite"
    monkeypatch.setenv("FINSIGHT_WORKING_MEMORY_PATH", str(path))
    model = Scripted(responses=[AIMessage(content="", tool_calls=[{
        "id": "save", "name": "WriteWorkingNote", "args": {"title": "ACME cash check", "body":
            "Checked CFO; source SRC1. Unresolved tax classification. Next read SRC2.", "base_version": 0}, "type": "tool_call"}]),
        AIMessage(content="Cash check saved; tax classification remains unresolved.")])
    agent = create_agent(model=model, tools=working_memory_tools("test", owner="test", workspace="case"),
        middleware=[WorkCheckpointMiddleware(trigger_tokens=100)], checkpointer=InMemorySaver())
    cfg = {"configurable": {"thread_id": "case"}}
    user = HumanMessage(content="Keep the tax question open. " * 200)
    result = agent.invoke({"messages": [user]}, cfg)
    assert result["messages"][0].content == user.content
    assert sum(m.name == CHECKPOINT_NAME for m in result["messages"]) == 1
    saved = WorkingMemory(path, owner="test", workspace="case", actor="test").search("ACME")
    assert saved["items"][0]["title"] == "ACME cash check"
