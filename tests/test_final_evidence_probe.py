from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from scripts.qualification.ai_memory_final_evidence_probe import paired_messages


def test_pair_restores_only_original_sources_without_mutating_history():
    messages = [HumanMessage(content="fixed question"), AIMessage(content="", tool_calls=[
        {"name": "read_research_source", "args": {"source_id": "P01:S079"}, "id": "old", "type": "tool_call"}]),
        ToolMessage(content="source original " * 7000, name="read_research_source", tool_call_id="old",
                    artifact={"source_id": "P01:S079"}),
        AIMessage(content="", tool_calls=[{"name": "read_research_source", "args": {}, "id": "middle", "type": "tool_call"}]),
        ToolMessage(content="intermediate result", name="read_research_source", tool_call_id="middle"),
        AIMessage(content="", tool_calls=[{"name": "read_research_source", "args": {}, "id": "new", "type": "tool_call"}]),
        ToolMessage(content="fresh result", name="read_research_source", tool_call_id="new")]
    before = [m.model_dump() for m in messages]
    control, restored, changes = paired_messages(messages, "mu")
    assert [c["index"] for c in changes] == [2]
    assert control[2].content != messages[2].content
    assert restored[2].model_dump() == messages[2].model_dump()
    assert [m.model_dump() for m in messages] == before
    assert control[-1].content == restored[-1].content == "fresh result"


def test_native_phase_graph_saves_resumes_and_consumes_note(tmp_path, monkeypatch):
    import asyncio
    import json
    from types import SimpleNamespace
    from scripts.qualification import ai_memory_phase_checkpoint_probe as probe
    source = ToolMessage(content='{"source_id":"S1","text":"Sequentially"}',
        name="read_research_source", tool_call_id="one", artifact={"result_state": "source_bound_passage"})
    monkeypatch.setattr(probe, "archive_messages", lambda *a: ([source], {"call_id": "known"}))
    calls = []
    async def invoke(messages, output, purpose, **kwargs):
        calls.append((output.name, messages))
        return AIMessage(content={"consolidate": "S1已读，期间环比，现金未核。", "review": "删除同比错误，现金仍未核。", "revise": "环比；现金待核。"}[output.name])
    monkeypatch.setattr(probe, "invoke_once", invoke)
    draft = tmp_path / "draft.md"
    draft.write_text("同比", encoding="utf-8")
    args = SimpleNamespace(output=tmp_path / "prep", archives=tmp_path, draft=draft, execute=False)
    asyncio.run(probe.run(args))
    args.preparation, args.output, args.execute = args.output, tmp_path / "paid", True
    asyncio.run(probe.run(args))
    assert [c[0] for c in calls] == ["consolidate", "review", "revise"]
    for _, messages in calls[1:]:
        content = json.loads(messages[-1].content)
        assert content["working_note_unverified"] == "S1已读，期间环比，现金未核。"
        assert content["original_source_records"][0]["content"] == source.content
    assert (args.output / "revision.md").read_text(encoding="utf-8") == "环比；现金待核。"
    assert json.loads((args.output / "phase-boundary.json").read_text(encoding="utf-8"))["next"] == ["review"]
