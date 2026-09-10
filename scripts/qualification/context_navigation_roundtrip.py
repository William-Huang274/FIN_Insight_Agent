"""Bounded normal/lossy-view context retrieval comparison; <=6 provider calls."""
import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langsmith import tracing_context
from pydantic import SecretStr

from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
from sec_agent.agent_runtime.conversation_tools import conversation_tools
from sec_agent.agent_runtime.deepseek_structured_agents import TokenBudgetBasis, DeepSeekModelProfile
from sec_agent.agent_runtime.dell_case_review_agent import CaseModelAudit, case_chat_model
from sec_agent.agent_runtime.model_context import RequestSummaryMiddleware
from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _dotenv


def fixture():
    return [HumanMessage(id="original-task", content="虚构公司Acme的上下文恢复测试。比较FY2024和FY2025的经营现金流，只使用已经保存的观察；不需要联网或重查数据库。"),
        AIMessage(id="query", content="", tool_calls=[{"id":"receipt-73ab", "name":"query_financial_data", "type":"tool_call",
            "args":{"ticker":"ACME", "metric_id":"operating_cash_flow", "fiscal_years":[2024,2025]}}]),
        ToolMessage(id="numbers", name="query_financial_data", tool_call_id="receipt-73ab", content=json.dumps({
            "synthetic":True, "company":"Acme", "metric":"经营现金流 CFO", "unit":"百万美元",
            "observations":[{"fiscal_year":2024,"value":100,"source_id":"fixture:2024"},
                            {"fiscal_year":2025,"value":80,"source_id":"fixture:2025"}]} ,ensure_ascii=False)),
        AIMessage(id="wrong-old-text", content="旧候选说法：现金减少20%，下一步需要继续查询原因。"),
        HumanMessage(id="user-correction", content="纠正：这里是经营现金流，不是现金余额。不要继续研究下降原因，只按已经查询的数字描述变化。"),
        AIMessage(id="ack", content="收到，待整理结果。"),
        HumanMessage(id="resume", content="继续刚才未完成的工作，给我一个简短结果，说明依据和这次不判断的部分。")]


def recovery_grants(thread_id):
    # The production factory also provides a calculator. This experiment tests
    # retrieval only, so qualify the advertised set before any provider call.
    names = {"browse_context", "read_context_turn", "read_saved_result"}
    grants = [g for g in conversation_tools(thread_id=thread_id) if g.tool.name in names]
    if {g.tool.name for g in grants} != names:
        raise ValueError("recovery_tool_surface_changed")
    return grants


async def run(output, live):
    output.mkdir(parents=True, exist_ok=False)
    basis = TokenBudgetBasis.model_validate_json(json.dumps({
        "node_role":"specialist", "node_purpose":"Two synthetic context-recovery arms: full checkpoint view and deliberately lossy request summary. Maximum three requests each, six total; no full research.",
        "input_scale":"Seven seed turns, one synthetic two-year CFO receipt, three read-only checkpoint tools and context guidance; capped on actual SDK request.",
        "required_outputs":["Use original values and latest user correction", "Recover omitted receipt via native checkpoint without new SQL/web", "State limits of the observation"],
        "schema_burden":"Only tool region/key/offset; final output is free prose.",
        "materiality_quality_risk":"Synthetic recovery proof, not financial quality or compaction-model accuracy. Deliberately lossy abstract tests fallback; originals retained.",
        "comparable_run_evidence":"47 offline checks passed. a1 found original receipt in both arms but accidentally exposed calculator and exceeded completion budget: six calls/18072 tokens. a2 limits tools to the originally intended three readers and clarifies visible context need not be reread. Not a pure single-variable ablation.",
        "reasoning_profile":"agentic_message_history_thinking_enabled", "max_input_characters":20000,
        "max_output_tokens":1200, "timeout_seconds":90, "max_transport_attempts":1,
        "retry_policy":"none", "truncation_stop_behavior":"fail_closed_no_partial_promotion", "input_ceiling_behavior":"fail_before_transport"}))
    (output/"TokenBudgetBasis.json").write_text(basis.model_dump_json(indent=2),encoding="utf-8")
    (output/"qualification-scope.json").write_text(json.dumps({"maximum_requests":6,"synthetic_fixture":True,
        "summary_deliberately_lossy":True,"tests_actual_summarizer_quality":False,"retries":0},indent=2),encoding="utf-8")
    if not live:
        print("Prepared only; no provider calls.")
        return
    profile=DeepSeekModelProfile(model="deepseek-flash",thinking="enabled",reasoning_effort="low")
    model=case_chat_model(profile,basis,SimpleNamespace(base_url="https://api.deepseek.com"),SecretStr(_dotenv()["DEEPSEEK_API_KEY"]))
    outcomes=[]
    def forbidden_summary(_):
        raise RuntimeError("No additional summarizer call authorized in this fixture")
    for arm in ["normal", "lossy"]:
        directory=output/arm
        directory.mkdir()
        def sink(name):
            def append(event):
                with (directory/name).open("a",encoding="utf-8") as f:
                    f.write(json.dumps(event,ensure_ascii=False,default=str)+"\n")
            return append
        audit=CaseModelAudit(actor="context-recovery-"+arm,profile=profile,basis=basis,
            public_sink=sink("events.jsonl"),private_sink=sink("responses.private.jsonl"))
        projection=RequestSummaryMiddleware(model=model,audited_model=RunnableLambda(forbidden_summary),
                                            trigger_tokens=100000,keep_tokens=1000)
        rows=fixture()
        initial={"messages":rows}
        if arm=="lossy":
            initial["request_summary"]={"prefix_end":6,"first_original_id":rows[0].id,
                "last_original_id":rows[5].id,"count":1,"message":HumanMessage(content=
                    "UNTRUSTED historical abstract: 旧候选称现金减少，准备继续查询原因。数字、来源ID和工具ID已省略；需从原始记录核对。").model_dump(mode="json")}
        outcome={"arm":arm,"status":"not_started","financial_quality_accepted":False}
        try:
            with tracing_context(enabled=False):
                async with AsyncSqliteSaver.from_conn_string(str(directory/"checkpoint.sqlite")) as saver:
                    graph=build_conversation_agent(model=model,grants=recovery_grants(arm),
                        permission_mode="request_standard",checkpointer=saver,middleware=[projection,audit],model_calls=3,tool_calls=4)
                    config={"configurable":{"thread_id":arm}}
                    try:
                        result=await graph.ainvoke(initial,config)
                    except Exception:
                        partial=await graph.aget_state(config)
                        (directory/"partial-state.private.json").write_text(json.dumps(partial.values,ensure_ascii=False,indent=2,
                            default=lambda x:x.model_dump(mode="json")),encoding="utf-8")
                        raise
                    (directory/"result.private.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,
                        default=lambda x:x.model_dump(mode="json")),encoding="utf-8")
                    new=result["messages"][len(rows):]
                    outcome.update(status="completed_pending_assessment",public_output=result["messages"][-1].content,
                        tool_calls=[{"name":c["name"],"args":c["args"]} for m in new if isinstance(m,AIMessage) for c in m.tool_calls])
        except Exception as exc:
            outcome.update(status="stopped_no_retry",error_type=type(exc).__name__)
        outcome["provider_requests"]=sum(e.get("event")=="started" for e in audit.events)
        outcome["known_tokens"]=sum(e.get("total_tokens") or 0 for e in audit.events if e.get("event")=="outcome")
        outcome["unknown_usage_requests"]=outcome["provider_requests"]-sum(e.get("event")=="outcome" and e.get("usage_reported") is True for e in audit.events)
        outcomes.append(outcome)
        (output/"outcomes.json").write_text(json.dumps(outcomes,ensure_ascii=False,indent=2),encoding="utf-8")
    # Windows redirected consoles may still use GBK; artifacts above are UTF-8.
    print(json.dumps(outcomes,ensure_ascii=True))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",required=True,type=Path)
    parser.add_argument("--live",action="store_true",help="At most six paid requests; no retry.")
    args=parser.parse_args()
    asyncio.run(run(args.output_dir,args.live))
