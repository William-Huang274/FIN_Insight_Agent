"""Fixed-case data and summary/reader compatibility before the paid matrix."""
import asyncio
from copy import deepcopy
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda

from scripts.qualification.context_recovery_cases import cases, append_after_first_compaction, seed_notes
from scripts.qualification.context_recovery_matrix import budget, tool_metrics
from sec_agent.agent_runtime.context_navigation import browse_checkpoint
from sec_agent.agent_runtime.model_context import RequestSummaryMiddleware
from sec_agent.agent_runtime.working_memory import WorkingMemory
from sec_agent.agent_runtime.working_memory_tools import execute_memory_tool
from test_conversation_agent import ScriptedTools


def test_case_receipt_targets_and_missing_record_are_not_guessed():
    for case in cases():
        rows=case["messages"]
        gold=case["gold"]
        if case.get("expected_key"):
            result=next(m for m in rows if isinstance(m,ToolMessage) and m.tool_call_id==case["expected_key"])
            body=json.loads(result.content)
            assert body["value"]==gold["value"] and body["company"]==gold["company"] and body["fiscal_year"]==gold["year"]
            assert case["expected_key"] in [r["key"] for r in browse_checkpoint(rows,"numbers",gold["company"])["items"]]
        if case["id"]=="absent_record":
            assert browse_checkpoint(rows,"numbers","ORION")["total_matches"]==0
        assert budget(case["id"]).max_transport_attempts==1


def test_two_actual_native_cutoffs_still_allow_original_receipt_and_correction_reads():
    async def run():
        case=next(c for c in cases() if c["summary_rounds"]==2)
        state={"messages":deepcopy(case["messages"])}
        policy=RequestSummaryMiddleware(model=ScriptedTools(responses=[AIMessage(content="unused")]),
            audited_model=RunnableLambda(lambda _:AIMessage(content="Lossy abstract.")),trigger_tokens=800,keep_tokens=200,max_summaries=2)
        ends=[]
        for i in range(2):
            state.update(await policy.abefore_model(state,None))
            ends.append(state["request_summary"]["prefix_end"])
            if i==0: append_after_first_compaction(state)
        assert ends[1]>ends[0]
        assert state["request_summary"]["count"]==2
        projected=policy.projected_messages(state)
        assert any(m.id=="scope-confirm" for m in projected)
        assert not any(isinstance(m,ToolMessage) and m.tool_call_id=="r-91c" for m in projected)
        assert "r-91c" in [r["key"] for r in browse_checkpoint(state["messages"],"numbers","NOVA")["items"]]
    asyncio.run(run())


def test_current_working_note_tools_return_v2_and_keep_v1(tmp_path,monkeypatch):
    path=tmp_path/"notes.sqlite"
    monkeypatch.setenv("FINSIGHT_WORKING_MEMORY_PATH",str(path))
    monkeypatch.setenv("FINSIGHT_WORKING_MEMORY_SEMANTIC","0")
    memory=WorkingMemory(path,owner="pilot",workspace="fixture",actor="analyst")
    note_id=seed_notes(memory)
    found=execute_memory_tool("SearchWorkingNotes",{"query":"NOVA"},{},"analyst",owner="pilot",workspace="fixture")
    assert found["items"][0]["version"]==2
    current=execute_memory_tool("ReadWorkingNote",{"note_id":note_id},{},"analyst",owner="pilot",workspace="fixture")
    assert current["version"]==2
    assert memory.read(note_id,version=1)["version"]==1
    assert "已取消" in json.dumps(current,ensure_ascii=False)


def test_metrics_count_new_redundant_and_off_target_reads_not_seed_calls():
    old=AIMessage(id="seed",content="",tool_calls=[{"name":"read_saved_result","args":{"tool_call_id":"other"},"id":"old"}])
    new=AIMessage(id="new",content="",tool_calls=[{"name":"read_saved_result","args":{"tool_call_id":key},"id":str(i)}
        for i,key in enumerate(["expected","expected","other"])])
    result=tool_metrics([old,new],{"seed"},"expected")
    assert result["duplicate_receipt_reads"]==1
    assert result["off_target_receipt_reads"]==["other"]


def test_known_summary_truncation_retains_prior_view_and_unknown_errors_propagate():
    async def run():
        case=next(c for c in cases() if c["summary_rounds"]==2)
        state={"messages":deepcopy(case["messages"])}
        model=ScriptedTools(responses=[AIMessage(content="unused")])
        policy=RequestSummaryMiddleware(model=model,audited_model=RunnableLambda(lambda _:AIMessage(content="Prior valid abstract.")),
            trigger_tokens=800,keep_tokens=200)
        state.update(await policy.abefore_model(state,None))
        append_after_first_compaction(state)
        prior=deepcopy(state)
        def truncated(_): raise ValueError("case_review_truncated_no_partial_acceptance")
        policy.native._summary_model=RunnableLambda(truncated)
        state.update(await policy.abefore_model(state,None))
        assert state["request_summary"]==prior["request_summary"]
        assert state["messages"]==prior["messages"]
        assert await policy.abefore_model(state,None) is None
        assert state["request_summary_failure"]["original_history_retained"]
        state["request_summary_failure"]=None
        def bug(_): raise ValueError("unexpected_contract_bug")
        policy.native._summary_model=RunnableLambda(bug)
        import pytest
        with pytest.raises(ValueError,match="unexpected_contract_bug"):
            await policy.abefore_model(state,None)
    asyncio.run(run())
