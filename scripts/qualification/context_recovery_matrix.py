"""Five fixed context cases, <=15 answer and <=2 summary calls, no paid retries."""
import argparse
import asyncio
import json
import os
import traceback
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langsmith import tracing_context
from pydantic import SecretStr

from sec_agent.agent_runtime.conversation_agent import build_conversation_agent, GrantedTool
from sec_agent.agent_runtime.dell_case_review_agent import CaseModelAudit, case_chat_model
from sec_agent.agent_runtime.deepseek_structured_agents import TokenBudgetBasis, DeepSeekModelProfile
from sec_agent.agent_runtime.model_context import RequestSummaryMiddleware
from sec_agent.agent_runtime.working_memory import WorkingMemory
from sec_agent.agent_runtime.working_memory_tools import working_memory_tools
from scripts.qualification.context_navigation_roundtrip import recovery_grants
from scripts.qualification.context_recovery_cases import cases, append_after_first_compaction, seed_notes
from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _dotenv


def write(path, data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,
        default=lambda obj: obj.model_dump(mode="json")),encoding="utf-8")


def budget(case_id, summarizer=False):
    return TokenBudgetBasis.model_validate_json(json.dumps({
        "node_role":"specialist", "node_purpose":("Compress original history into a recoverable working abstract, maximum two calls" if summarizer else
            "Recover the fixed context case using existing read-only tools, maximum three calls")+": "+case_id,
        "input_scale":"Synthetic two-company/two-year receipts, original user scope corrections; summary cases include two modest archival blocks. At most five reader tools. Actual payload bounded before transport.",
        "required_outputs":["Retain company, period, unit and locator; distinguish absent record from disclosure gap",
                            "Follow current user scope and current working-note version; final public prose"],
        "schema_burden":"Only existing reader region/ID/version parameters. No financial prose template or extra structured final answer.",
        "materiality_quality_risk":"Development memory qualification, not financial reasoning or production acceptance. Summary and originals retained independently; tool ceilings preserve partial checkpoint.",
        "comparable_run_evidence":"Previous Acme full/lossy a2 each 3calls: 7446/6124 tokens. Both recovered but visible arm redundantly read. New fixed cases avoid fresh calculation or broad research.",
        "reasoning_profile":"agentic_message_history_thinking_enabled", "max_input_characters":24000,
        "max_output_tokens":1600 if summarizer else 1200,"timeout_seconds":90,"max_transport_attempts":1,
        "retry_policy":"none","truncation_stop_behavior":"fail_closed_no_partial_promotion","input_ceiling_behavior":"fail_before_transport"}))


def tool_metrics(messages, initial_ids, expected_key):
    calls=[c for m in messages if isinstance(m,AIMessage) and m.id not in initial_ids for c in m.tool_calls]
    reads=[c["args"].get("tool_call_id") for c in calls if c["name"]=="read_saved_result"]
    return {"tool_calls":[{"name":c["name"],"args":c["args"]} for c in calls],
            "receipt_reads":reads,"off_target_receipt_reads":[k for k in reads if k!=expected_key],
            "duplicate_receipt_reads":len(reads)-len(set(reads)),
            "external_dispatch_possible":False,
            "note":"Off-target read is not by itself a wrong answer; assess public output separately."}


async def run(output,live):
    output.mkdir(parents=True,exist_ok=False)
    suite=cases()
    write(output/"frozen-cases.json",suite)
    for case in suite:
        directory=output/case["id"]
        directory.mkdir()
        write(directory/"TokenBudgetBasis.json",budget(case["id"]))
        if case["summary_rounds"]>0: write(directory/"SummaryTokenBudgetBasis.json",budget(case["id"],True))
    if not live:
        print("Prepared fixed cases; no provider call.")
        return
    profile=DeepSeekModelProfile(model="deepseek-flash",thinking="enabled",reasoning_effort="low")
    key=SecretStr(_dotenv()["DEEPSEEK_API_KEY"])
    outcomes=[]
    for case in suite:
        directory=output/case["id"]
        audits=[]
        def audited(summarizer=False):
            basis=budget(case["id"],summarizer)
            def sink(filename):
                def emit(event):
                    with (directory/filename).open("a",encoding="utf-8") as f:
                        f.write(json.dumps(event,ensure_ascii=False,default=str)+"\n")
                return emit
            audit=CaseModelAudit(actor=("summary:" if summarizer else "answer:")+case["id"],profile=profile,basis=basis,
                public_sink=sink("events.jsonl"),private_sink=sink("responses.private.jsonl"))
            model=case_chat_model(profile,basis,SimpleNamespace(base_url="https://api.deepseek.com"),key)
            audits.append(audit)
            return model,audit
        model,audit=audited()
        def forbidden(_): raise RuntimeError("automatic_extra_summary_not_budgeted")
        projection=RequestSummaryMiddleware(model=model,audited_model=RunnableLambda(forbidden),trigger_tokens=100000,keep_tokens=200)
        state={"messages":case["messages"]}
        outcome={"id":case["id"],"status":"started","synthetic":True,"automatic_quality_pass":False}
        try:
            with tracing_context(enabled=False):
                if case["summary_rounds"]>0:
                    summary_model,summary_audit=audited(True)
                    compressor=RequestSummaryMiddleware(model=summary_model,audited_model=summary_audit.model_runnable(summary_model),
                        trigger_tokens=800,keep_tokens=200,max_summaries=2)
                    for i in range(2):
                        update=await compressor.abefore_model(state,None)
                        if not update: raise RuntimeError("expected_compaction_not_triggered")
                        state.update(update)
                        write(directory/f"summary-{i+1}.json",update)
                        if state.get("request_summary_failure"):
                            outcome["summary_failure"]=state["request_summary_failure"]
                            break  # retain originals and proceed under the same answer budget
                        if i==0: append_after_first_compaction(state)
                    state["messages"].append(HumanMessage(id="final-request",content="继续整理当前范围的那条观察，注明数值、公司、期间、单位和来源。"))
                elif case["summary_rounds"]==-1:
                    end=len(state["messages"])-2
                    state["request_summary"]={"prefix_end":end,"first_original_id":state["messages"][0].id,
                        "last_original_id":state["messages"][end-1].id,"count":1,"message":HumanMessage(content=
                            "UNTRUSTED abstract: 已有ACME/NOVA的历史数字，具体数值和ID省略，按需回读原始记录。").model_dump(mode="json")}
                grants=recovery_grants(case["id"])
                if case["id"]=="working_note_current_version":
                    os.environ["FINSIGHT_WORKING_MEMORY_PATH"]=str(directory/"notes.sqlite")
                    os.environ["FINSIGHT_WORKING_MEMORY_SEMANTIC"]="0"
                    memory=WorkingMemory(directory/"notes.sqlite",owner="pilot",workspace=case["id"],actor="analyst")
                    outcome["note_id"]=seed_notes(memory)
                    grants.extend(GrantedTool(t,"read","current scoped working paper") for t in working_memory_tools(
                        "analyst",owner="pilot",workspace=case["id"]) if t.name in {"ReadWorkingNote","SearchWorkingNotes"})
                assert {g.tool.name for g in grants} <= {"browse_context","read_context_turn","read_saved_result","ReadWorkingNote","SearchWorkingNotes"}
                write(directory/"initial-state.private.json",state)
                ids={m.id for m in state["messages"]}
                async with AsyncSqliteSaver.from_conn_string(str(directory/"checkpoint.sqlite")) as saver:
                    graph=build_conversation_agent(model=model,grants=grants,permission_mode="request_standard",checkpointer=saver,
                        middleware=[projection,audit],model_calls=3,tool_calls=5)
                    config={"configurable":{"thread_id":case["id"]}}
                    try:
                        state=await graph.ainvoke(state,config)
                        outcome.update(status="completed_pending_assessment",public_output=state["messages"][-1].content)
                    finally:
                        saved=await graph.aget_state(config)
                        write(directory/"final-state.private.json",saved.values)
                        outcome.update(tool_metrics(saved.values.get("messages",[]),ids,case.get("expected_key")))
        except Exception as exc:
            outcome.update(status="stopped_no_retry",error_type=type(exc).__name__)
            (directory/"error.private.txt").write_text(traceback.format_exc(),encoding="utf-8")
        events=[e for a in audits for e in a.events]
        outcome.update(provider_requests=sum(e.get("event")=="started" for e in events),
            known_tokens=sum(e.get("total_tokens") or 0 for e in events if e.get("event")=="outcome"))
        outcome["unknown_usage_requests"]=outcome["provider_requests"]-sum(e.get("event")=="outcome" and e.get("usage_reported") is True for e in events)
        outcomes.append(outcome)
        write(output/"outcomes.json",outcomes)
        print(json.dumps(outcome,ensure_ascii=True),flush=True)
    assert sum(o["provider_requests"] for o in outcomes)<=17


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",required=True,type=Path)
    parser.add_argument("--live",action="store_true")
    args=parser.parse_args()
    asyncio.run(run(args.output_dir,args.live))
