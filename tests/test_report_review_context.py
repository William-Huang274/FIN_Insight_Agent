import json
from copy import deepcopy

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph.message import add_messages
import pytest

from sec_agent.agent_runtime.report_review_context import (
    project_review_messages, read_review_record, report_change_text, review_message_update,
)


def task(version, **extra):
    return HumanMessage(id=f"task-{version}", content=json.dumps({
        "question": "Explain growth", "review_target": "final_report",
        "report": {"title": "Report", "narrative_markdown": f"version {version}"},
        "previous_review": {"findings": [{"diagnosis": "Prior scoped issue"}]},
        "catalog": {"papers": [{"id": "P01", "source": "PASSAGE::a"}]},
        **extra,
    }))


def reading():
    return [
        AIMessage(id="read", content="", additional_kwargs={"reasoning_content": "PRIVATE"},
                  tool_calls=[{"id": "r", "name": "read_current_source", "args": {"source_id": "CALC::a"}}]),
        ToolMessage(id="receipt", tool_call_id="r", name="read_current_source",
                    content='{"calculation_id":"CALC::a","operands":[1,2],"period":"FY2027"}'),
    ]


def test_same_version_refresh_preserves_reads_errors_and_ids():
    messages = [task(1), *reading(), ToolMessage(id="bad-result", content="rejected", name="submit_report_review", tool_call_id="bad", status="error")]
    before = deepcopy(messages)
    body = json.loads(messages[0].content)
    body["instruction"] = "Current instructions"
    updated = add_messages(messages, review_message_update(body, messages))
    assert len(updated) == len(messages) and updated[0].id == "task-1"
    view, _ = project_review_messages(updated)
    assert view[1:] == messages[1:]
    assert messages == before
    assert json.loads(view[0].content)["instruction"] == "Current instructions"


def test_changed_version_archives_old_task_and_receipts_with_exact_readback():
    messages = [task(1), *reading(), task(2, report_changes_from_previous_review="legacy enormous diff")]
    before = deepcopy(messages)
    view, _ = project_review_messages(messages)
    assert len(view) == 1
    current = json.loads(view[0].content)
    assert current["report"]["narrative_markdown"] == "version 2"
    assert current["previous_review"]["findings"]
    assert "version 1" in current["report_changes_from_previous_review"]
    assert len(current["history"]["records"]) == 3
    for record in current["history"]["records"]:
        result = read_review_record(messages, **record["read"]["arguments"])
        assert result["content"]
        assert "PRIVATE" not in result["content"]
    original = json.loads(read_review_record(messages, 2)["content"])
    assert original["content"] == messages[2].content
    pointer = current["supporting_records"]["catalog"]["read"]["arguments"]
    assert json.loads(read_review_record(messages, **pointer)["content"]) == json.loads(messages[-1].content)["catalog"]
    assert messages == before


def test_multiple_versions_and_current_read_are_not_evicted():
    messages = [task(1), *reading(), task(2), task(3)]
    current_read = ToolMessage(content="current evidence", name="read_review_history", tool_call_id="current")
    messages += [AIMessage(content="", tool_calls=[{"id": "current", "name": "read_review_history", "args": {"message_index": 2}}]), current_read]
    view, _ = project_review_messages(messages)
    assert len(view) == 3 and view[-1] == current_read
    assert json.loads(view[0].content)["report"]["narrative_markdown"] == "version 3"
    assert len(json.loads(view[0].content)["history"]["records"]) == 4


def test_pending_old_tool_batch_is_not_silently_archived():
    messages = [task(1), reading()[0], task(2)]
    assert project_review_messages(messages) == (messages, None)


def test_paginated_exact_readback_and_invalid_bounds():
    messages = [task(1), *reading()]
    whole = read_review_record(messages, 2)["content"]
    page = read_review_record(messages, 2, max_characters=17)
    chunks = [page["content"]]
    while page["next_read"]:
        page = read_review_record(messages, **page["next_read"])
        chunks.append(page["content"])
    assert "".join(chunks) == whole
    with pytest.raises(ValueError):
        read_review_record(messages, 50)
    choice = read_review_record(messages, 2, field="report")
    assert choice["status"] == "record_selection_required" and not choice["accepted"]
    assert choice["candidates"][0]["read"]["arguments"]["message_index"] == 0
    assert "content" not in choice


def test_field_and_record_mismatch_returns_version_choices_without_selecting():
    messages = [task(1, author_responses={"old": "unchanged"}),
                *reading(), task(2, author_responses={"new": "changed"})]
    result = read_review_record(messages, 1, field="author_responses")
    assert [r["message_index"] for r in result["candidates"]] == [0, 3]
    assert len({r["review_basis"] for r in result["candidates"]}) == 2
    assert result["record_type_at_requested_index"] == "ai"
    assert not result["accepted"] and "content" not in result


def test_small_markdown_change_does_not_duplicate_entire_report():
    old = {"narrative_markdown": "\n".join(f"paragraph {i}" for i in range(1000)), "citations": [{"id": "source"}]}
    new = deepcopy(old)
    new["narrative_markdown"] = new["narrative_markdown"].replace("paragraph 500\n", "changed paragraph\n")
    diff = report_change_text(old, new)
    assert "changed paragraph" in diff and len(diff) < 500
    assert "paragraph 100\n" not in diff and "citations" not in diff


def test_native_reviewer_can_read_archived_receipt_and_finish_without_research_replay():
    import asyncio
    from test_research_convergence import artifact_fixture
    from test_report_synthesis_agent import NativeFixtureModel
    from test_case_review_agent import call
    from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent
    messages = [task(1), *reading(), task(2)]
    model = NativeFixtureModel(marker="review-history", replies=[
        [call("read_review_history", {"message_index": 2}, "history")],
        [call("submit_report_review", {"review": {
            "summary": "Synthetic fixture confirms saved record access, not financial correctness.",
            "completion": "complete", "findings": [], "unresolved_data_requests": [],
        }}, "submit")],
    ])
    agent = build_case_output_agent(role="verifier", model=model, tools=[],
        artifacts=artifact_fixture(), limits={"model_calls": 2, "tool_calls": 2})
    result = asyncio.run(agent.ainvoke({"messages": messages, "report": json.loads(messages[-1].content)["report"]}))
    assert result["output"]["findings"] == []
    recovered = next(m for m in result["messages"] if isinstance(m, ToolMessage) and m.name == "read_review_history")
    assert json.loads(json.loads(recovered.content)["content"])["content"] == messages[2].content
    assert len(model.contexts) == 2
    assert len(model.contexts[0]) == 2  # system and current task only
    assert any(isinstance(m, ToolMessage) and m.name == "read_review_history" for m in model.contexts[1])
