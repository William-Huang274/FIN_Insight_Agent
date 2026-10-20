"""Merged review history, organization guards and native checkpoints; no provider."""
import asyncio
from copy import deepcopy
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
import pytest

from sec_agent.agent_runtime.report_review_context import read_review_record
from test_organization_data_composition import organization
from test_model_dispatch_guard import boundary


@pytest.mark.parametrize("reader", ["report", "research"])
def test_public_history_excludes_structured_private_blocks(reader):
    message = AIMessage(content=[
        {"type": "text", "text": "Public observation"},
        {"type": "reasoning", "reasoning": "PRIVATE_REASONING"},
        {"type": "thinking", "thinking": "PRIVATE_THINKING"},
        {"type": "redacted_thinking", "data": "PRIVATE_OPAQUE"}],
        additional_kwargs={"reasoning_content": "PRIVATE_EXTRA"},
        tool_calls=[{"id": "read", "name": "read_source_document", "args": {"node_id": "original"}}])
    original = deepcopy(message)
    if reader == "report":
        result = read_review_record([message], 0)
    else:
        from sec_agent.agent_runtime.review_context import history_page
        result = {"index": history_page([message]), "record": history_page([message], index=0)}
    encoded = json.dumps(result)
    assert "Public observation" in encoded and "PRIVATE_" not in encoded
    assert message == original


@pytest.mark.parametrize("revocation", ["none", "before", "during"])
def test_history_tool_uses_current_organization_guard(organization, boundary, monkeypatch, revocation):
    import sec_agent.agent_runtime.report_review_context as history
    from sec_agent.agent_runtime.case_review_agent import CaseModelAudit
    from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent
    from test_report_review_context import task, reading
    from test_report_synthesis_agent import NativeFixtureModel
    from test_research_convergence import artifact_fixture
    from test_case_review_agent import call
    factory, authority = organization
    records = [task(1), *reading(), task(2)]
    reads = []
    original = history.read_review_record
    def read(*args, **kwargs):
        result = original(*args, **kwargs)
        reads.append(result)
        if revocation == "during":
            authority["status"] = 404
        return result
    monkeypatch.setattr(history, "read_review_record", read)
    model = NativeFixtureModel(marker="history-guard", replies=[
        [call("read_review_history", {"message_index": 2}, "read-history")],
        [call("submit_report_review", {"review": {
            "summary": "Static history qualification, not financial acceptance.",
            "completion": "complete", "findings": [], "unresolved_data_requests": []}}, "submit")]])
    audit = CaseModelAudit(actor="organization-history", profile=boundary.profile,
        basis=boundary.basis.model_copy(update={"max_input_characters": 1000000}),
        public_sink=lambda _: None, private_sink=lambda _: None,
        source_access_check=lambda: factory.reader._after(factory.grant))
    agent = build_case_output_agent(role="verifier", model=model, tools=[],
        artifacts=artifact_fixture(), audit=audit, limits={"model_calls": 3, "tool_calls": 3})
    if revocation == "before":
        authority["status"] = 404
    async def execute():
        return await agent.ainvoke({"messages": records, "report": json.loads(records[-1].content)["report"]})
    if revocation != "none":
        with pytest.raises(Exception) as denied:
            asyncio.run(execute())
        import traceback
        assert "OrganizationExecutionUnavailable" in "".join(traceback.format_exception(denied.value))
        assert len(model.contexts) == (0 if revocation == "before" else 1)
        assert len(reads) == (0 if revocation == "before" else 1)
    else:
        result = asyncio.run(execute())
        assert result["output"]["findings"] == []
        assert len(reads) == 1 and len(model.contexts) == 2
        assert any(isinstance(m, ToolMessage) and m.name == "read_review_history"
                   for m in result["messages"])


@pytest.mark.parametrize("interrupted", [False, True])
def test_native_review_checkpoints_resume_and_keep_three_report_versions(interrupted):
    from langgraph.checkpoint.memory import InMemorySaver
    from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent
    from test_report_review_context import task, reading
    from test_report_synthesis_agent import NativeFixtureModel
    from test_research_convergence import artifact_fixture
    from test_case_review_agent import call
    model = NativeFixtureModel(marker="version-review", replies=[
        [call("read_review_history", {"message_index": 2}, "version-read")],
        [call("submit_report_review", {"review": {
            "summary": "Static current-version checkpoint qualification; no financial conclusion is certified.",
            "completion": "complete", "findings": [], "unresolved_data_requests": []}}, "submit")]])
    built = build_case_output_agent(role="verifier", model=model, tools=[],
        artifacts=artifact_fixture(), limits={"model_calls": 4, "tool_calls": 4})
    # Native checkpoint and interrupt semantics, not a private recovery loader.
    graph = built.builder.compile(checkpointer=InMemorySaver(),
                                  interrupt_after=["tools"] if interrupted else [])
    config = {"configurable": {"thread_id": "static-versioned-review"}}
    historical = [task(1), *reading()]
    async def execute():
        for version in (2, 3, 4):
            current = task(version)
            result = await graph.ainvoke({
                "messages": [*historical, current] if version == 2 else [current],
                "report": json.loads(current.content)["report"], "output": None}, config)
            if interrupted:
                saved = await graph.aget_state(config)
                assert saved.next and not saved.values.get("output")
                before = len([m for m in saved.values["messages"]
                              if isinstance(m, ToolMessage) and m.name == "read_review_history"])
                result = await graph.ainvoke(None, config)
                after = len([m for m in result["messages"]
                             if isinstance(m, ToolMessage) and m.name == "read_review_history"])
                assert before == after == version - 1
            assert result["output"]["findings"] == []
            assert result["report"]["narrative_markdown"] == f"version {version}"
            assert result["messages"][:3] == historical
            first_call = model.contexts[(version - 2) * 2]
            assignment = json.loads(next(m.content for m in first_call if isinstance(m, HumanMessage)))
            assert assignment["report"]["narrative_markdown"] == f"version {version}"
            assert "history" in assignment and not any(isinstance(m, ToolMessage) for m in first_call)
        assert len(model.contexts) == 6
        saved = await graph.aget_state(config)
        assert len([m for m in saved.values["messages"] if isinstance(m, HumanMessage)]) == 4
    asyncio.run(execute())
