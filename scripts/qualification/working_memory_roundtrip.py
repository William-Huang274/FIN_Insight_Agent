"""Explicit <=5-call working-memory roundtrip; no full research or financial pass."""
import argparse
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langsmith import tracing_context
from pydantic import SecretStr

from sec_agent.agent_runtime.conversation_agent import build_conversation_agent, GrantedTool
from sec_agent.agent_runtime.working_memory import WorkingMemory
from sec_agent.agent_runtime.working_memory_tools import working_memory_tools
from sec_agent.agent_runtime.deepseek_structured_agents import TokenBudgetBasis, DeepSeekModelProfile
from sec_agent.agent_runtime.dell_case_review_agent import CaseModelAudit, case_chat_model
from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _dotenv


async def run(output, live):
    output.mkdir(parents=True, exist_ok=False)
    basis=TokenBudgetBasis.model_validate_json(json.dumps({
        "node_role":"specialist", "node_purpose":"Two-turn natural working-note save/read/revise after closing and reopening native SQLite checkpoint; <=5 total requests.",
        "input_scale":"Three small tools, synthetic Chinese task, one note and short two-turn history; actual SDK input checked before each call.",
        "required_outputs":["Save readable interim working note", "Read and revise that note following explicit user correction after checkpoint reopen"],
        "schema_burden":"Native tool title/body plus runtime version only; no finance schema or mandatory prose sections.",
        "materiality_quality_risk":"Memory/revision proof, not financial reasoning acceptance. Old prose and version remain available; unknown result stops, no retry.",
        "comparable_run_evidence":"9 working-memory offline tests including native interrupt/reopen, specialist/lead tools and BFF. Earlier short Flash 2209tokens recognized financial boundaries; not a saving forecast.",
        "reasoning_profile":"agentic_message_history_thinking_enabled", "max_input_characters":20000,
        "max_output_tokens":2000, "timeout_seconds":90, "max_transport_attempts":1,
        "retry_policy":"none", "truncation_stop_behavior":"fail_closed_no_partial_promotion", "input_ceiling_behavior":"fail_before_transport"}))
    (output/"TokenBudgetBasis.json").write_text(basis.model_dump_json(indent=2),encoding="utf-8")
    first="这是虚构公司的工作底稿测试，无须联网或研究。请先建立标题为‘现金流研究记录’的自然语言底稿：已观察到净利润和经营现金流同向增加；暂时还想研究是否能据此支持‘利润并非纯账面增长’；下一步可能查看营运资本调节项。自由写几句话即可，不要表单。保存后简短告诉我。"
    (output/"first-question.txt").write_text(first,encoding="utf-8")
    if not live:
        print("Prepared only; no provider calls.");return
    os.environ["FINSIGHT_WORKING_MEMORY_PATH"]=str(output/"notes.sqlite")
    profile=DeepSeekModelProfile(model="deepseek-flash",thinking="enabled",reasoning_effort="low")
    model=case_chat_model(profile,basis,SimpleNamespace(base_url="https://api.deepseek.com"),SecretStr(_dotenv()["DEEPSEEK_API_KEY"]))
    def sink(name):
        def append(event):
            with (output/name).open("a",encoding="utf-8") as f:f.write(json.dumps(event,ensure_ascii=False,default=str)+"\n")
        return append
    audit=CaseModelAudit(actor="working-note-pilot",profile=profile,basis=basis,
                         public_sink=sink("events.jsonl"),private_sink=sink("responses.private.jsonl"))
    grants=[GrantedTool(t,"working_note_write" if t.name=="WriteWorkingNote" else "read","此测试自己的工作底稿")
            for t in working_memory_tools("analyst",owner="pilot",workspace="roundtrip")]
    memory=WorkingMemory(output/"notes.sqlite",owner="pilot",workspace="roundtrip",actor="analyst")
    outcome={"financial_quality_accepted":False,"full_report_accepted":False,"max_model_calls":5}
    try:
        with tracing_context(enabled=False):
            async with AsyncSqliteSaver.from_conn_string(str(output/"checkpoint.sqlite")) as saver:
                graph=build_conversation_agent(model=model,grants=grants,permission_mode="request_standard",checkpointer=saver,
                                                middleware=[audit],model_calls=2,tool_calls=2)
                state=await graph.ainvoke({"messages":[HumanMessage(content=first)]},{"configurable":{"thread_id":"roundtrip"}})
                (output/"first-result.private.json").write_text(json.dumps(state,default=lambda x:x.model_dump(mode="json"),ensure_ascii=False,indent=2),encoding="utf-8")
            rows=memory.search()["items"]
            if not rows:raise ValueError("first_note_not_saved_no_retry")
            note=rows[0]
            correction=f"针对底稿 {note['id']} 的 v{note['version']}，请先读回正文，再修改同一底稿：不要继续论证‘非纯账面’，只描述两者同向增长；将其余归因标为本轮不判断。取消原来准备追加调节项研究的下一步。原始观察保留。请保存修改，简短说明改动。"
            (output/"correction.txt").write_text(correction,encoding="utf-8")
            async with AsyncSqliteSaver.from_conn_string(str(output/"checkpoint.sqlite")) as saver:
                graph=build_conversation_agent(model=model,grants=grants,permission_mode="request_standard",checkpointer=saver,
                                                middleware=[audit],model_calls=3,tool_calls=3)
                state=await graph.ainvoke({"messages":[HumanMessage(content=correction)]},{"configurable":{"thread_id":"roundtrip"}})
                (output/"second-result.private.json").write_text(json.dumps(state,default=lambda x:x.model_dump(mode="json"),ensure_ascii=False,indent=2),encoding="utf-8")
            saved=memory.export_markdown(note["id"])
            (output/"working-note.md").write_text(saved["markdown"],encoding="utf-8")
            outcome.update(status="completed_pending_human_assessment",note_id=note["id"],version=saved["version"])
    except Exception as exc:
        outcome.update(status="stopped_no_retry",error_type=type(exc).__name__)
    outcome["provider_requests"]=sum(e.get("event")=="started" for e in audit.events)
    outcome["known_tokens"]=sum(e.get("total_tokens") or 0 for e in audit.events if e.get("event")=="outcome")
    outcome["unknown_usage_requests"]=outcome["provider_requests"]-sum(
        e.get("event")=="outcome" and e.get("usage_reported") is True for e in audit.events)
    (output/"outcome.json").write_text(json.dumps(outcome,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(outcome,ensure_ascii=False))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",required=True,type=Path)
    parser.add_argument("--live",action="store_true",help="Explicitly send at most five paid model requests; no retry.")
    args=parser.parse_args()
    asyncio.run(run(args.output_dir,args.live))
