from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
from sec_agent.agent_runtime.docker_sandbox import DockerPythonSandbox, SandboxResult, sandbox_tool


class Scripted(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


@pytest.mark.parametrize("mode", ["request_standard", "approve_for_me", "full_access"])
def test_native_scope_and_permission_gate_precedes_sandbox_execution(mode):
    calls = []
    def execute(code, *, thread_id):
        calls.append((code, thread_id))
        return SandboxResult("synthetic", 0, False, "2", True, {})
    thread = str(uuid4())
    model = Scripted(responses=[AIMessage(content="", tool_calls=[{
        "name": "run_isolated_python", "args": {"code": "print(1+1)"}, "id": "code-1", "type": "tool_call"}]),
        AIMessage(content="Result")])
    agent = build_conversation_agent(model=model, grants=[sandbox_tool(SimpleNamespace(execute=execute), thread_id=thread)],
        permission_mode=mode, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": thread}}
    result = agent.invoke({"messages": [{"role": "user", "content": "Calculate"}]}, config)
    if mode == "request_standard":
        assert result["__interrupt__"] and calls == []
        agent.invoke(Command(resume={"decisions": [{"type": "reject", "message": "Do not execute"}]}), config)
        assert calls == []
    else:
        assert calls == [("print(1+1)", thread)]


def test_image_and_thread_are_host_authority_not_model_arguments():
    with pytest.raises(ValueError, match="pinned_local_image"):
        DockerPythonSandbox(image_id="python:latest")
    grant = sandbox_tool(SimpleNamespace(), thread_id=str(uuid4()))
    assert set(grant.tool.args) == {"code"}
    with pytest.raises(ValueError):
        sandbox_tool(SimpleNamespace(), thread_id="../../another-user")
