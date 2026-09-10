"""Bounded native-agent method comparison over host-selected existing marts.

No external search, source writes, full research dispatch, or automatic retries.
Use separate output directories for every arm/attempt; raw model traces private.
"""
from __future__ import annotations

import argparse
import asyncio
from hashlib import sha256
import json
import os
import sqlite3
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import SecretStr

from financial_facts import FactLookup, execute_fact_lookup
from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
from sec_agent.agent_runtime.conversation_tools import conversation_tools
from sec_agent.agent_runtime.conversation_handoff import observed_sources, answer_charts
from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
from sec_agent.agent_runtime.dell_case_review_agent import CaseModelAudit, case_chat_model, InvalidToolCallFeedback
from sec_agent.agent_runtime.dell_report_session import session_audit_sinks
from sec_agent.research_foundation.research_methods import get_research_method, METHODS


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


async def run(args):
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if not 1 <= len(cases) <= 4 or not args.output.is_absolute():
        raise ValueError("one_to_four_cases_and_absolute_private_output_required")
    if args.resume_checkpoint and len(cases) != 1:
        raise ValueError("resume_requires_one_case")
    args.output.mkdir(parents=True, exist_ok=False)
    methods = {key: (args.method_directory / (key + ".md")).read_text(encoding="utf-8")
               if args.method_directory else get_research_method(key)["content"] for key in METHODS}
    def method_reader(method_id=""):
        value = get_research_method(method_id)
        if method_id:
            value.update(content=methods[method_id], version=1 if args.method_directory else 2)
        return value
    profile = DeepSeekModelProfile(model=args.model, thinking="enabled", reasoning_effort="low")
    manifest = {"cases": cases, "model": profile.model_dump(mode="json"), "methods": methods,
                "comparison_scope": args.comparison_scope,
                "max_model_calls_per_case": 2 if args.resume_checkpoint else 6,
                "max_tools_per_case": 2 if args.resume_checkpoint else 16, "transport_attempts": 1,
                "resume_checkpoint": str(args.resume_checkpoint) if args.resume_checkpoint else None}
    save(args.output / "manifest.json", manifest)
    prepared = []
    for case in cases:
        path = Path(case["mart"]).resolve(strict=True)
        rows = [execute_fact_lookup(path, FactLookup("preflight-" + metric, case["ticker"], metric, "2026-09-10",
            {"selection_mode": "latest_on_or_before", "fiscal_years": [case["year"]]}, "fiscal_year", "reported_source_unit")).as_dict()
                for metric in case["preflight_metrics"]]
        prepared.append({"case": case["id"], "mart_sha256": sha256(path.read_bytes()).hexdigest(), "results": rows})
        if not all(r["status"] == "resolved" for r in rows):
            save(args.output / "preflight-failed.json", prepared)
            raise ValueError("source_query_preflight_failed_no_model_calls")
    save(args.output / "preflight.json", prepared)
    if not args.execute:
        print("Prepared only; no model calls.")
        return
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _dotenv
        key = _dotenv()["DEEPSEEK_API_KEY"]
    results = []
    for case, receipt in zip(cases, prepared):
        output = args.output / case["id"]
        output.mkdir()
        if args.resume_checkpoint:
            source = sqlite3.connect(args.resume_checkpoint.resolve(strict=True).as_uri() + "?mode=ro", uri=True)
            target = sqlite3.connect(output / "checkpoint.sqlite")
            try:
                source.backup(target)
            finally:
                source.close()
                target.close()
        basis = TokenBudgetBasis(node_role="specialist", node_purpose=case["question"],
            input_scale="One financial question, two fiscal years, existing read-only financial mart and two requested role methods; native tool results retained.",
            required_outputs=("Correct concise Chinese financial conclusion and public evidence-based rationale", "Exact periods, signs, derived metric citations and source-bound chart", "Explicit unresolved checks without invented causes"),
            schema_burden="Native fact/method/calculator/chart tools; prose final answer; no full research workpaper schema.",
            materiality_quality_risk="Profit/loss signs, CFO versus FCF, old guidance, fiscal calendar and unsupported causal conclusions.",
            comparable_run_evidence=("MSFT batch-fix-a2 used 6 model calls/8 tools and stopped on a recoverable chart-unit error. Clone its native checkpoint read-only; allow at most 2 further calls to repair and submit, with no repeated full research. Not a fresh success or pure paired method comparison." if args.resume_checkpoint else "205 historical HPE/MU/MSFT/NVDA errors are development evidence. This paired method qualification is not blind or a whole-runtime acceptance."),
            reasoning_profile="agentic_message_history_thinking_enabled", max_input_characters=180000,
            max_output_tokens=6000, timeout_seconds=240, max_transport_attempts=1, retry_policy="none",
            truncation_stop_behavior="fail_closed_no_partial_promotion", input_ceiling_behavior="fail_before_transport")
        save(output / "TokenBudgetBasis.json", basis.model_dump(mode="json"))
        public, private = session_audit_sinks(output)
        audit = CaseModelAudit(actor="metric-method-" + case["id"], profile=profile, basis=basis,
                               public_sink=public, private_sink=private)
        model = case_chat_model(profile, basis, SimpleNamespace(base_url="https://api.deepseek.com"), SecretStr(key))
        grants = conversation_tools(thread_id=case["id"], fact_mart=Path(case["mart"]), method_reader=method_reader)
        question = (case["question"] + " 信息截止日2026-09-10。仅使用本地已有财务数据，不联网补研。"
                    "先阅读finance和writer方法。使用适用的财务工具，生成一张来源绑定比较图，最后用中文给出约400字的完整答复、关键数据小表、来源引用和简短分析理由。"
                    "本题不要求完整行业研究报告；必要证据不在工具范围时说明具体限制。")
        save(output / "question.json", {"question": question})
        async with AsyncSqliteSaver.from_conn_string(str(output / "checkpoint.sqlite")) as saver:
            agent = build_conversation_agent(model=model, grants=grants, permission_mode="request_standard", checkpointer=saver,
                middleware=[InvalidToolCallFeedback(), audit], model_calls=manifest["max_model_calls_per_case"], tool_calls=manifest["max_tools_per_case"])
            cfg = {"configurable": {"thread_id": case["id"]}, "recursion_limit": 64}
            failure = None
            try:
                result = await agent.ainvoke(None if args.resume_checkpoint else {"messages": [{"role": "user", "content": question}]}, cfg)
            except Exception as exc:
                failure = type(exc).__name__ + ": " + str(exc)[:240]
                result = (await agent.aget_state(cfg)).values
            messages = [m.model_dump(mode="json") for m in result.get("messages", [])]
            save(output / "messages.json", messages)
            sources = observed_sources({"values": {"messages": messages}})
            final = messages[-1] if messages else {}
            complete = not failure and final.get("type") == "ai" and not final.get("tool_calls") and not final.get("invalid_tool_calls") and bool(final.get("content"))
            report = {"title": case["title"], "narrative_markdown": final.get("content", "") if complete else "运行未完成，已执行成果和原始响应保留于本次记录。",
                      "citations": {k: {"sources": [{**v, "source_id": k}]} for k, v in sources.items()},
                      "charts": answer_charts(messages)}
            save(output / "report.json", report)
            export_failure = None
            if complete:
                try:
                    from apps.workbench.backend.application.report_delivery import export_report
                    for fmt in ("md", "pdf", "docx"):
                        body, _ = export_report(report, fmt, review_status="模型候选 · 方法对照，待内容审阅")
                        (output / ("report." + fmt)).write_bytes(body)
                except Exception as exc:
                    export_failure = type(exc).__name__ + ": " + str(exc)[:240]
            outcomes = [e for e in audit.events if e.get("event") == "outcome"]
            summary = {"case": case["id"], "complete_answer": complete, "failure": failure, "export_failure": export_failure,
                "model_calls": len(outcomes), "known_tokens": sum(e.get("total_tokens") or 0 for e in outcomes),
                "unknown_usage_calls": sum(not e.get("usage_reported") for e in outcomes),
                "chart_count": len(report["charts"]), "sources": len(sources),
                "mart_unchanged": sha256(Path(case["mart"]).read_bytes()).hexdigest() == receipt["mart_sha256"],
                "financial_acceptance": "pending_content_review", "events": outcomes}
            save(output / "result.json", summary)
            results.append(summary)
            save(args.output / "results.json", results)
            print(json.dumps({k: v for k, v in summary.items() if k != "events"}), flush=True)
            if summary["unknown_usage_calls"] or not summary["mart_unchanged"]:
                raise RuntimeError("unknown_usage_or_source_drift_stop_no_retry")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--cases", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--method-directory", type=Path)
    p.add_argument("--model", default="deepseek-flash")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--resume-checkpoint", type=Path)
    p.add_argument("--comparison-scope", default="same_current_tools_and_data_only_role_method_content_changes_not_old_runtime_reproduction")
    asyncio.run(run(p.parse_args()))
