"""Parent-loop regression: individual reviewer checkpoints alone miss this."""
import asyncio
import json
import runpy
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
import pytest

from test_research_convergence import artifact_fixture


@pytest.mark.parametrize("rebuild", [False, True])
def test_parent_corrections_retain_exact_prior_reviewer_receipt(tmp_path, monkeypatch, rebuild):
    monkeypatch.setenv("FIN_REPORT_REVIEW_PERSISTENCE_QUALIFICATION", "1")
    monkeypatch.setenv("FIN_PROBE_EVIDENCE", str(tmp_path))
    (tmp_path / "convergence-papers.json").write_text(
        json.dumps(list(artifact_fixture()._author_states.values())), encoding="utf-8")
    factory = runpy.run_path(str(Path(__file__).parent /
        "integration/fixtures/report_convergence_persistence_graph.py"))["graph"]
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "parent-review-persistence"}, "recursion_limit": 180}

    def compile_graph():
        return factory(config).builder.compile(checkpointer=saver, interrupt_after=["writer"])

    async def exercise():
        graph = compile_graph()
        for index in range(3):
            await graph.ainvoke({} if index == 0 else None, config)
            saved = await graph.aget_state(config)
            assert saved.next == ("report_verifier",)
            assert f"Revision {index}." in saved.values["report"]["narrative_markdown"]
            if rebuild:
                graph = compile_graph()
        result = await graph.ainvoke(None, config)
        assert result["phase"] == "case_report_ready_for_human_review"
        assert result["report_review"]["findings"] == []
        assert len(result["artifact_history"]) == 6
        turns = list(map(json.loads, (tmp_path / "convergence-turns.jsonl").read_text().splitlines()))
        assert len(turns) == 9
        assert sum(r["phase"] == "read_current_source" for r in turns) == 1
        assert sum(r["phase"] == "read_review_history" for r in turns) == 2
        child = await saver.aget_tuple({"configurable": {
            "thread_id": "parent-review-persistence", "checkpoint_ns": "report_verifier"}})
        assert child is not None
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
        journal = child.checkpoint["channel_values"]["messages"]
        assert len([m for m in journal if isinstance(m, HumanMessage)]) == 3
        calls = [c["id"] for m in journal if isinstance(m, AIMessage) for c in m.tool_calls]
        receipts = [m.tool_call_id for m in journal if isinstance(m, ToolMessage)]
        assert len(calls) == len(set(calls)) == 6
        assert sorted(calls) == sorted(receipts)
        assert all("submit_case_report" != c["name"]
                   for m in journal if isinstance(m, AIMessage) for c in m.tool_calls)
        # A second thread must perform its own source read, never inherit the
        # completed reviewer journal or its previous verdict.
        other = {"configurable": {"thread_id": "separate-review-thread"}, "recursion_limit": 180}
        await graph.ainvoke({}, other)
        await graph.ainvoke(None, other)
        after = list(map(json.loads, (tmp_path / "convergence-turns.jsonl").read_text().splitlines()))
        assert [r["phase"] for r in after[len(turns):]] == [
            "submission", "read_current_source", "submission", "submission"]
    asyncio.run(exercise())
