"""Bounded development continuations of one archived FIN conversation.

No research rerun, report mutation, new memory service, or model retry. Reuses
native create_agent, real read-only FIN tools, audit sinks and existing cost math.
The original historical task was not a blind test; this is retention qualification.
"""
from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, messages_from_dict
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.checkpoint.memory import InMemorySaver
from langsmith import Client as LangSmithClient, tracing_context
from mcp import Client
from pydantic import SecretStr

from sec_agent.agent_runtime.dell_case_review_agent import CaseModelAudit, case_chat_model, case_mcp_tools
from sec_agent.agent_runtime.dell_case_convergence_agent import build_case_output_agent
from sec_agent.agent_runtime.dell_case_artifacts import DellCaseArtifacts
from sec_agent.agent_runtime.dell_agent_server_data_composition import open_dell_approved_data_composition
from sec_agent.agent_runtime.dell_report_session import session_audit_sinks
from sec_agent.agent_runtime.model_context import RequestSummaryMiddleware
from scripts.qualification.report_revision_comparison import SourceProbe, host_data_environment, model_settings, write_new
from scripts.qualification.dell_q1_specialist_paid_shadow.audit_token_cost import audit as cost_audit, cost_parts, peak_multiplier


HISTORY_CALL = "2a142e7d-fc42-41c6-b1be-6f8302dc97a3"
QUESTION = """现在只做这段既有会话的接续检查，不继续整案研究、不提交综合、不改报告。
请沿用会话中已经观察到的 calculate_research_metric 记录，简洁列出其 CALC ID、公式、结果、单位、操作数及来源/期间。
区分算术通过与金融语义通过、S2权威数字与发行人文字数字；不要重新解释整案结论。
还要指出最近 submit_research_synthesis 被拒绝的具体错误，以及后续应该如何补读/纠正，而不是称已成功。
重要结果以现有 CALC/来源 ID 引用。如必要资料在上下文被省略，允许用已有只读工具补读，不要猜造。
这是同一已有历史的隔离开发接续，不是新研究或报告验收。请用 submit_case_answer 保存这份简短答复。"""
SUMMARY = {"trigger_tokens": 80000, "keep_tokens": 24000, "max_summaries": 2}
VARIANTS = ("original", "summary_and_edit", "tool_edit", "flash_short")


class Probe(SourceProbe):
    def bind_tools(self, tools, **kwargs):
        # Audit copies model metadata per call. Preserve the shared capture list
        # so offline request sizing includes schemas bound on that model copy.
        self.tool_schemas[:] = [convert_to_openai_tool(t) for t in tools]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.contexts.append(messages)
        if self.report.get("read_ids") and len(self.contexts) == 1:
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[{
                "id": f"offline-reread-{i}", "type": "tool_call", "name": "read_current_source",
                "args": {"source_id": ref}} for i, ref in enumerate(self.report["read_ids"])]))])
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[{
            "id": "offline-submit", "type": "tool_call", "name": "submit_case_answer",
            "args": {"answer_markdown": self.report["answer"]}}]))])


class BoundedAudit(CaseModelAudit):
    def __init__(self, *, shared, model, reference_messages=(), **kwargs):
        super().__init__(**kwargs)
        self.shared, self.model = shared, model
        self.reference_messages = {json.dumps(m, ensure_ascii=False, sort_keys=True) for m in reference_messages}

    async def awrap_model_call(self, request, handler):
        messages = ([request.system_message] if request.system_message else []) + list(request.messages)
        payload = self.model._get_request_payload(messages, tools=[convert_to_openai_tool(t) for t in request.tools])
        byte_bound = len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 4096
        if self.reference_messages:
            # This exact archived request has provider-reported input=200851.
            # Charge its ENTIRE original token count, even when only a subset is
            # retained, plus a byte upper bound for every new/changed message
            # and every current schema. This is not a guessed chars/token ratio.
            changed = [m for m in payload["messages"]
                if json.dumps(m, ensure_ascii=False, sort_keys=True) not in self.reference_messages]
            incremental = len(json.dumps({"messages": changed, "tools": payload.get("tools", [])}, ensure_ascii=False).encode("utf-8")) + 4096
            byte_bound = min(byte_bound, 200851 + incremental)
        # Byte upper bound is conservative, not claimed tokenizer equivalence.
        miss_price, output_price = (3, 9) if self.profile.model == "deepseek-v4-flash" else (9, 27)
        reserve = (byte_bound * miss_price + self.basis.max_output_tokens * output_price) / 1e6
        if self.shared["unknown"] or self.shared["calls"] >= self.shared.get("max_calls", 8) or self.shared["spent"] + reserve > 5:
            raise ValueError("context_batch_reserve_or_call_limit_before_transport")
        self.shared["calls"] += 1
        return await super().awrap_model_call(request, handler)


def settings(root, *, flash=False, summary=False, postfix=False):
    profile, basis, config, case = model_settings(root)
    if flash:
        profile = profile.model_copy(update={"model": "deepseek-v4-flash", "thinking": "disabled"})
    purpose = "Same-agent historical context retention and actionable source-error continuation; no full financial research or report change."
    if summary:
        purpose = "Native working summary of the same agent's long prefix, not Evidence, report writing, or research judgment."
    basis = basis.model_copy(update={"node_purpose": purpose,
        "input_scale": "One archived 40-message synthesis conversation (original call 2a142e7d, previously about 200k input tokens). Same history and task for three context variants; Flash short uses only the observed calculation and latest rejection, not a long synthesis. Native summary excludes metadata/private reasoning from its prompt and retains the original user task/recent tool batch.",
        "required_outputs": ("Exact retained calculation/operands/period/authority and current unresolved tool error; re-read if needed",),
        "comparable_run_evidence": "Original full session 265 requests, 264 known usage, CNY28.092715; previous local-edit n=1 five requests CNY0.5116455 failed semantic check. This batch is not a same-quality whole-report savings estimate.",
        "reasoning_profile": "agentic_message_history_thinking_" + profile.thinking,
        "max_input_characters": 650000, "max_output_tokens": 6000 if summary else 4500 if flash else 12000, "timeout_seconds": 480})
    if postfix:
        basis = basis.model_copy(update={
            "input_scale": "Same archived 40-message synthesis history, fresh summary plus repaired original-observation reread only. Original input about 200k tokens; prior summarized main input 73990/46553. Retain original task, recent tool pairs and host evidence. No baseline, standalone editing or short-Flash arm.",
            "comparable_run_evidence": "Prior A3: one Flash summary and two Pro calls, 205315 tokens, estimated CNY1.4707206; model requested four historical CALCs but the local resolver failed. Patched four-record reread and actual saved-summary/native-tool replay passed offline. Fresh ceiling CNY5 and five calls: one summary plus up to four continuation rounds for read/answer/actionable feedback; no transport retry or fallback.",
            "required_outputs": (("Working summary preserving original task, exact IDs, source/period/authority distinctions, failures and next reads; never Evidence",) if summary else
                ("Retained CALC ID, formula, result, unit, operands, sources and periods with valid citations", "Distinguish arithmetic verified from financial semantics not verified and non-S2 authority", "Identify the latest unresolved synthesis submission error without inventing its root cause; use existing read tools when needed")),
            "reasoning_profile": "nonthinking_summary" if summary else "thinking_enabled_reasoning_effort_low_with_12000_output_including_reasoning"})
    return profile, basis, config, case


async def run(root, out, execute, remaining_from=None, flash_after=None, *, postfix_summary=False):
    if postfix_summary and (remaining_from or flash_after):
        raise ValueError("fresh_postfix_cannot_reuse_closed_batch_authority")
    prepared = json.loads((out / "input.private.json").read_text(encoding="utf-8"))
    snapshot, raw_history = prepared["snapshot"], prepared["history"]
    artifacts = DellCaseArtifacts(snapshot["state"]["case_papers"])
    env, shared = {**host_data_environment(), "FIN_REPO_ROOT": str(root)}, {"spent": 0.0, "unknown": False, "calls": 0}
    variants = ("summary_and_edit",) if postfix_summary else VARIANTS
    summary_policy = {**SUMMARY, "max_summaries": 1} if postfix_summary else SUMMARY
    limits = {"model_calls": 4, "tool_calls": 12} if postfix_summary else {"model_calls": 2, "tool_calls": 8}
    if postfix_summary:
        shared["max_calls"] = 5
    if remaining_from:
        prior = cost_audit(remaining_from / "calls")["totals"]
        if prior["requests"] != 1 or prior["cost_known_requests"] != 1 or prior["statuses"] != {"truncated": 1}:
            raise ValueError("remaining_scope_does_not_match_disclosed_single_truncated_baseline")
        shared.update(spent=prior["modeled_cost_cny"], calls=prior["requests"])
        variants = ("summary_and_edit", "flash_short")
    if flash_after:
        prior = cost_audit(flash_after / "calls")["totals"]
        if not remaining_from or prior["requests"] != prior["cost_known_requests"]:
            raise ValueError("unstarted_flash_prior_usage_not_fully_known")
        shared["spent"] += prior["modeled_cost_cny"]
        shared["calls"] += prior["requests"]
        variants = ("flash_short",)
    results = []
    if execute:
        write_new(out / "execution.json", {"started_at": datetime.now(timezone.utc).isoformat(),
            "owner_approval": ("Owner explicitly authorized real model calls for repaired long-history continuation on 2026-09-07; agent bounded this fresh slice to CNY5/five calls" if postfix_summary else "Owner explicitly approved this new batch, <=CNY5, <=8 model calls including summary"),
            "budget_cny": 5, "max_calls": shared.get("max_calls", 8), "no_retry_resume_or_promotion": True,
            "variants": variants, "agent_limits": limits,
            "remaining_from": str(remaining_from) if remaining_from else None,
            "flash_after": str(flash_after) if flash_after else None,
            "scope_correction": "Owner explicitly approved only the unstarted summary+edit and Flash-short branches, Pro output up to12000, original CNY5/eight-call cumulative ceiling. Never retry baseline." if remaining_from else None,
            "node_settings": {n: {"profile": settings(root, flash=n in {"flash_short", "summary"}, summary=n == "summary", postfix=postfix_summary)[0].model_dump(mode="json"),
                "basis": settings(root, flash=n in {"flash_short", "summary"}, summary=n == "summary", postfix=postfix_summary)[1].model_dump(mode="json")}
                for n in (("continuation", "summary") if postfix_summary else ("continuation", "flash_short", "summary"))}, "summary_policy": summary_policy})
    for variant in variants:
        profile, basis, config, case = settings(root, flash=variant == "flash_short", postfix=postfix_summary)
        model = case_chat_model(profile, basis, config, SecretStr(os.environ.get("DEEPSEEK_API_KEY", "offline")),
            context_editing={"trigger_tokens": 50000, "keep": 6} if variant in {"tool_edit", "summary_and_edit"} else None)
        history = messages_from_dict([{"type": m["type"], "data": m} for m in raw_history if m["type"] != "system"])
        if variant == "flash_short":
            # New short fact task: source/tool results only, never another role's
            # private reasoning. Same observed CALC, no invented numeric fixture.
            observed = next(i for i, m in enumerate(history) if isinstance(m, ToolMessage) and m.name == "calculate_research_metric")
            call = history[observed - 1].model_copy(deep=True)
            call.additional_kwargs = {}  # short task receives an observation, not another role's reasoning
            history = [HumanMessage(content="Inspect this existing calculation and unresolved error only."),
                call, history[observed], HumanMessage(content=prepared["short_context"]["last_error"])]
        history.append(HumanMessage(content=QUESTION))
        state = {**{k: deepcopy(snapshot["state"][k]) for k in ("report", "revisions", "synthesis")},
            "request_action": "ask", "messages": history}
        invocation = "context-comparison:" + out.name + ":" + variant
        with open_dell_approved_data_composition(run_invocation_id=invocation, environment=env,
                source_read_enabled=True, live_web_read_enabled=False, case_artifacts=artifacts) as data:
            async with Client(data.mcp_server, raise_exceptions=False, read_timeout_seconds=120) as client:
                bound = await client.call_tool("get_dell_research_method", {"branch_ids": [b["branch_id"] for b in case["branch_topics"]],
                    "research_as_of": artifacts.research_as_of, "data_snapshot_id": artifacts.snapshot_id, "execution_attempt_id": invocation})
                if bound.is_error:
                    raise ValueError("context_comparison_data_binding_failed")
                tools = await case_mcp_tools(client, run_scope=bound.structured_content["run_scope"])
                public, private = session_audit_sinks(out / "calls" / variant) if execute else (lambda _: None, lambda _: None)
                def emit(event):
                    public(event)
                    if event.get("event") != "outcome":
                        return
                    if not event.get("usage_reported") or event.get("cache_hit_tokens") is None:
                        shared["unknown"] = True
                    else:
                        hit = event["cache_hit_tokens"]
                        shared["spent"] += sum(cost_parts(event["model"], hit, event["input_tokens"]-hit,
                            event["output_tokens"], peak_multiplier(event["recorded_at"])).values())
                    print(json.dumps({"actor": event["actor"], "status": event["status"], "input": event.get("input_tokens"),
                        "output": event.get("output_tokens"), "batch_cny": shared["spent"], "unknown": shared["unknown"]}), flush=True)
                reference = model.model_copy(update={"tool_context_trigger_tokens": None})._get_request_payload(
                    messages_from_dict([{"type": m["type"], "data": m} for m in raw_history]))["messages"]
                active_audit = (BoundedAudit(shared=shared, model=model, reference_messages=reference, actor=variant, profile=profile, basis=basis,
                    public_sink=emit, private_sink=private) if execute else CaseModelAudit(actor=variant,
                    profile=profile, basis=basis, public_sink=lambda _: None, private_sink=lambda _: None))
                if variant == "summary_and_edit":
                    sp, sb, sc, _ = settings(root, flash=True, summary=True, postfix=postfix_summary)
                    sm = case_chat_model(sp, sb, sc, SecretStr(os.environ.get("DEEPSEEK_API_KEY", "offline")))
                    sa = BoundedAudit(shared=shared, model=sm, actor="context_summary:"+variant, profile=sp, basis=sb,
                        public_sink=emit, private_sink=private)
                    async def fake_summary(value):
                        return AIMessage(content="Offline summary fixture only: " + prepared["expected_answer"])
                    active_audit.context_summary = RequestSummaryMiddleware(model=sm,
                        audited_model=sa.model_runnable(sm) if execute else RunnableLambda(fake_summary), **summary_policy)
                read_ids = [prepared["calculation"]["calculation_id"]]
                if variant != "flash_short":
                    read_ids += ["CALC::0492c9e9171a77ff72e6de2d", "CALC::812f9c41c0d1042fb23e5581", "CALC::1eb8a4e07239c6addbaeeee7"]
                probe = Probe(report={"answer": prepared["expected_answer"], "read_ids": read_ids})
                agent = build_case_output_agent(role="writer", model=model if execute else probe, tools=tools,
                    artifacts=artifacts, limits=limits, audit=active_audit,
                    report_revision=True, allow_answers=True, answer_only=True)
                agent.checkpointer = InMemorySaver()
                run_id = uuid4()
                try:
                    result = await agent.ainvoke(state, {"run_id": run_id, "run_name": "context_continuation_" + variant,
                        "configurable": {"thread_id": str(run_id)}, "recursion_limit": 30,
                        "tags": ["context-retention-development", out.name]})
                    answer = result["output"]["answer_markdown"]
                    if not execute and any(isinstance(m, ToolMessage) and m.status == "error" for m in result["messages"][len(history):]):
                        raise ValueError("offline_reread_or_submission_failed")
                    # Mechanical observations only; a human review must inspect
                    # meaning, units/periods, authority and error handling.
                    row = {"variant": variant, "status": "candidate_produced", "trace_id": str(run_id) if execute else None,
                        "answer_characters": len(answer), "summary_count": result.get("request_summary", {}).get("count", 0),
                        "tool_calls": [c["name"] for m in result["messages"][len(history):] if isinstance(m, AIMessage) for c in m.tool_calls],
                        "expected_calc_id_present": prepared["calculation"]["calculation_id"] in answer,
                        "expected_value_present": str(prepared["calculation"]["value_decimal"]) in answer.replace("−", "-")}
                    if execute:
                        write_new(out / (variant + ".candidate.private.json"), result["output"])
                        write_new(out / (variant + ".messages.private.json"), [m.model_dump(mode="json") for m in result["messages"]])
                        if result.get("request_summary"):
                            write_new(out / (variant + ".summary.private.json"), result["request_summary"])
                    else:
                        payload = model._get_request_payload(probe.contexts[0], tools=probe.tool_schemas)
                        row["first_request_utf8_bytes"] = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
                except Exception as exc:
                    row = {"variant": variant, "status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:500]}
                    results.append(row)
                    write_new(out / ("result.json" if execute else "preparation.json"), {"variants": results, **shared})
                    raise
                results.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
    write_new(out / ("result.json" if execute else "preparation.json"), {"variants": results, **shared, "product_acceptance": False})
    if execute:
        write_new(out / "token-cost-audit.json", cost_audit(out / "calls"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--history", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--remaining-from", type=Path)
    parser.add_argument("--flash-after", type=Path, help="Only the already-approved, unstarted Flash branch; add all prior calls/fees.")
    parser.add_argument("--postfix-summary-from", type=Path, help="Fresh repaired-summary-only qualification; copy this prior attempt's input, never its spent-call authority.")
    args = parser.parse_args()
    if args.postfix_summary_from and (args.remaining_from or args.flash_after):
        parser.error("A fresh repaired-summary run cannot reuse the closed prior batch")
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env", override=False)
    if not args.execute:
        if args.postfix_summary_from:
            args.output.mkdir(parents=True, exist_ok=False)
            write_new(args.output / "input.private.json", json.loads((args.postfix_summary_from / "input.private.json").read_text(encoding="utf-8")))
            with tracing_context(enabled=False):
                asyncio.run(run(root, args.output, False, postfix_summary=True))
            return
        if args.remaining_from:
            args.output.mkdir(parents=True, exist_ok=True)
            write_new(args.output / "input.private.json", json.loads((args.remaining_from / "input.private.json").read_text(encoding="utf-8")))
            with tracing_context(enabled=False):
                asyncio.run(run(root, args.output, False, args.remaining_from, args.flash_after))
            return
        rows = [json.loads(l) for l in args.history.open(encoding="utf-8")]
        record = next(r for r in rows if r.get("call_id") == HISTORY_CALL and r.get("messages"))
        calc = next(json.loads(m["content"]) for m in record["messages"] if m.get("name") == "calculate_research_metric")
        error = next(m["content"] for m in reversed(record["messages"]) if m.get("name") == "submit_research_synthesis")
        expected = f"Offline fixture only: {calc['expression']} = {calc['value_decimal']} {calc.get('unit', '')} [{calc['calculation_id']}]. {error}"
        args.output.mkdir(parents=True, exist_ok=True)
        write_new(args.output / "input.private.json", {"history": record["messages"], "calculation": calc,
            "short_context": {"calculation": calc, "last_error": error}, "expected_answer": expected,
            "snapshot": json.loads(args.snapshot.read_text(encoding="utf-8"))})
        with tracing_context(enabled=False):
            asyncio.run(run(root, args.output, False))
        return
    prep = json.loads((args.output / "preparation.json").read_text(encoding="utf-8"))
    if (len(prep["variants"]) != (1 if args.postfix_summary_from or args.flash_after else 2 if args.remaining_from else 4)
            or any(r["status"] != "candidate_produced" for r in prep["variants"])
            or (args.postfix_summary_from and [r["variant"] for r in prep["variants"]] != ["summary_and_edit"])):
        raise ValueError("offline_preparation_required")
    ls = LangSmithClient(hide_inputs=True, hide_outputs=True)
    project = ls.read_project(project_name="fin-insight-dell-reference-vertical")
    with tracing_context(enabled=True, project_name=project.name, client=ls):
        try:
            asyncio.run(run(root, args.output, True, args.remaining_from, args.flash_after, postfix_summary=bool(args.postfix_summary_from)))
        finally:
            from langchain_core.tracers.langchain import wait_for_all_tracers
            wait_for_all_tracers()


if __name__ == "__main__":
    main()
