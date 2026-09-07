"""One isolated Writer comparison using native create_agent and existing FIN tools.

Preparation reads a single FIN PostgreSQL checkpoint, never Codex state. Paid
execution needs --execute and an existing prepared directory. No server restart,
research DAG, automatic retry, report promotion or replacement of old artifacts.
"""
from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from uuid import UUID, uuid4

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langsmith import Client as LangSmithClient, tracing_context
from mcp import Client
from pydantic import Field, SecretStr

from sec_agent.agent_runtime.deepseek_structured_agents import (
    DeepSeekModelProfile, TokenBudgetBasis, load_deepseek_structured_agent_config,
)
from sec_agent.agent_runtime.dell_agent_server_data_composition import open_dell_approved_data_composition
from sec_agent.agent_runtime.dell_case_artifacts import DellCaseArtifacts
from sec_agent.agent_runtime.dell_case_convergence_agent import build_case_output_agent, report_model_view
from sec_agent.agent_runtime.dell_case_review_agent import CaseModelAudit, case_chat_model, case_mcp_tools
from sec_agent.agent_runtime.dell_report_session import session_audit_sinks
from sec_agent.agent_runtime.research_session_runtime import load_research_runtime_profile
from scripts.qualification.dell_q1_specialist_paid_shadow.audit_token_cost import cost_parts, peak_multiplier


THREAD = "01a077d8-a47c-7280-98f5-3df94b219488"
PG_CONTAINER = "finsight-dell-report-workbench-langgraph-postgres-1"
API_CONTAINER = "finsight-dell-report-workbench-langgraph-api-1"
QUESTION = """这是一项已有报告的局部修订，不是新的整案研究：报告不同段落对AI服务器“中个位数营业利润率”、管理层目标和实际盈利的描述不一致。请核对相关现有底稿/来源，修正受影响的表述，不预设开头或任何现有段落就是正确参照。保留其他研究判断、全部数字/引用和三张图，不处理其他既有争议、不重启九个研究面。若核查发现关联的原文或原稿问题，明确说明，不能为了局部一致性传播错误。不要把措辞修订当作整份报告验收；如现有材料不足，明确说明需要补核什么，不编造来源。提交修订后的研究报告或局部替换，不只回复修订建议。"""
LIMITS = {"model_calls": 4, "tool_calls": 16}


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def capture_checkpoint():
    UUID(THREAD)
    sql = f"""with latest as (
      select checkpoint_ns, checkpoint_id, run_id, checkpoint from checkpoints
      where thread_id='{THREAD}' and checkpoint_ns='' order by checkpoint_id desc limit 1
    ) select json_agg(json_build_object('checkpoint_id',c.checkpoint_id,'run_id',c.run_id,
      'inline',c.checkpoint->'channel_values',
      'channel',v.key,'type',b.type,'blob',encode(b.blob,'hex')))
    from latest c cross join lateral jsonb_each_text(c.checkpoint->'channel_versions') v
    join checkpoint_blobs b on b.thread_id='{THREAD}' and b.checkpoint_ns=c.checkpoint_ns
      and b.channel=v.key and b.version=v.value
    where v.key in ('question','report','report_version','phase','case_papers','revisions','synthesis');"""
    raw = subprocess.run(["docker", "exec", "-e", "PGOPTIONS=-c default_transaction_read_only=on",
        PG_CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
        check=True, capture_output=True, timeout=30).stdout
    rows, serde = json.loads(raw), JsonPlusSerializer()
    state = {k: v for k, v in rows[0]["inline"].items() if k in {"question", "report_version", "phase"}}
    state.update({r["channel"]: serde.loads_typed((r["type"], bytes.fromhex(r["blob"]))) for r in rows})
    if state["report_version"] != 3 or len(state["report"]["narrative_markdown"]) != 7281 or len(state["case_papers"]) != 9:
        raise ValueError("prepared_snapshot_is_not_the_disclosed_v3_case")
    return {"thread_id": THREAD, "checkpoint_id": rows[0]["checkpoint_id"], "run_id": rows[0]["run_id"], "state": state}


def host_data_environment():
    """Resolve the exact existing read-only data mounts; never print credentials."""
    container = json.loads(subprocess.run(["docker", "inspect", API_CONTAINER], check=True,
        capture_output=True, timeout=15).stdout)[0]
    env = dict(os.environ)
    keys = {"FINSIGHT_DELL_S1_NODES_PATH", "FINSIGHT_DELL_REVIEWED_BASE_PACK_PATH",
        "FINSIGHT_DELL_REVIEWED_OVERLAY_PATH", "FINSIGHT_DELL_S2_RESULT_PATH",
        "FINSIGHT_COMPANY_FINANCIAL_FACT_MART_PATH", "FINSIGHT_DELL_EXTERNAL_MANIFEST_PATH"}
    mounts = sorted(container["Mounts"], key=lambda m: len(m["Destination"]), reverse=True)
    for entry in container["Config"]["Env"]:
        key, _, value = entry.partition("=")
        if key not in keys:
            continue
        mount = next(m for m in mounts if value == m["Destination"] or value.startswith(m["Destination"] + "/"))
        env[key] = str(Path(mount["Source"]) / value[len(mount["Destination"]):].lstrip("/"))
    return env


def model_settings(root):
    runtime, case = load_research_runtime_profile(root)
    node = runtime["nodes"]["writer"]
    basis = TokenBudgetBasis.model_validate_json(json.dumps({**node["budget"],
        "node_purpose": "One existing v3 report target-versus-realized-margin qualifier correction; full submission versus local edits.",
        "input_scale": "7281-character v3, compact nine-paper catalog, same case sources on demand. No prior private model conversation or giant citation seed.",
        "required_outputs": ["Source-supported qualifier correction with unchanged unrelated prose, figures and citations"],
        "comparable_run_evidence": "Prior Writer local revision: four calls, inputs 21726 through 69779 tokens, output total 27523, modeled CNY 0.6420216 off-peak. Development n=1, not whole-report cost.",
        "max_input_characters": 180000, "max_output_tokens": 16000, "timeout_seconds": 480}))
    return (DeepSeekModelProfile.model_validate(node["profile"]), basis,
        load_deepseek_structured_agent_config(root / runtime["model_config"]), case)


def input_state(snapshot, artifacts):
    state = snapshot["state"]
    body = {"question": state["question"], "revision_request": QUESTION,
        "report": report_model_view(state["report"]),
        "catalog": artifacts.with_revisions(state["revisions"]).catalog()}
    return {**{k: deepcopy(state[k]) for k in ("report", "revisions", "synthesis")},
        "request_action": "revise", "messages": [HumanMessage(content=json.dumps(body, ensure_ascii=False))]}


class SourceProbe(BaseChatModel):
    """Zero-provider native tool probe; exact original report submission, no finding."""
    report: dict
    contexts: list = Field(default_factory=list)
    tool_schemas: list = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "zero-provider-report-input-probe"

    def bind_tools(self, tools, **kwargs):
        self.tool_schemas = [convert_to_openai_tool(t) for t in tools]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.contexts.append(messages)
        if len(self.contexts) == 1:
            name, args = "read_current_source", {"source_id": "P01:C14"}
        elif len(self.contexts) == 2:
            name, args = "submit_case_report", {"report": self.report}
        else:
            raise ValueError("offline_source_or_submission_probe_failed")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[{
            "id": f"probe-{len(self.contexts)}", "name": name, "args": args, "type": "tool_call"}],
            additional_kwargs={"reasoning_content": "Protocol fixture only, not financial analysis."}))])


class ComparisonAudit(CaseModelAudit):
    """Budget check on the existing audit hook, not another model runner."""
    def __init__(self, *, shared, model, **kwargs):
        super().__init__(**kwargs)
        self.shared, self.model = shared, model

    async def awrap_model_call(self, request, handler):
        messages = ([request.system_message] if request.system_message else []) + list(request.messages)
        payload = self.model._get_request_payload(messages, tools=[convert_to_openai_tool(t) for t in request.tools])
        # Conservative byte bound, not claimed to be the provider tokenizer.
        byte_bound = len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 4096
        reserve = (byte_bound * 9 + self.basis.max_output_tokens * 27) / 1_000_000
        if self.shared["unknown"] or self.shared["spent"] + reserve > 3:
            raise ValueError("comparison_budget_reserve_insufficient_before_transport")
        return await super().awrap_model_call(request, handler)


async def run_comparison(root, out, execute):
    profile, basis, config, case = model_settings(root)
    snapshot = json.loads((out / "snapshot.private.json").read_text(encoding="utf-8"))
    if snapshot["thread_id"] != THREAD or snapshot["state"]["report_version"] != 3:
        raise ValueError("comparison_snapshot_identity_mismatch")
    original, artifacts = deepcopy(snapshot["state"]), DellCaseArtifacts(snapshot["state"]["case_papers"])
    env, shared = {**host_data_environment(), "FIN_REPO_ROOT": str(root)}, {"spent": 0.0, "unknown": False}
    if execute:
        # Exclusive create is only output-overwrite protection; no retries/resume.
        write_new(out / "execution.json", {"started_at": datetime.now(timezone.utc).isoformat(),
            "budget_cny": 3, "owner_approval": "2026-09-07 continue after explicit up-to-CNY3 comparison proposal",
            "basis": basis.model_dump(mode="json"), "profile": profile.model_dump(mode="json"), "limits": LIMITS})
        for name in ("DEEPSEEK_API_KEY", "LANGSMITH_API_KEY"):
            if not os.environ.get(name):
                raise ValueError("missing_credential:" + name)
    model = case_chat_model(profile, basis, config, SecretStr(os.environ.get("DEEPSEEK_API_KEY", "unused-offline")))
    summary = []
    for variant, edits in (("full_submission", False), ("local_edits", True)):
        invocation = f"report-revision-comparison:{out.name}:{variant}"
        with open_dell_approved_data_composition(run_invocation_id=invocation, environment=env,
                source_read_enabled=True, live_web_read_enabled=False, case_artifacts=artifacts) as data:
            if any(a != b for a, b in ((artifacts.case_id, data.foundation_binding.case_id),
                    (artifacts.snapshot_id, data.foundation_binding.snapshot_id),
                    (artifacts.foundation_digest, data.foundation_binding.foundation_digest),
                    (artifacts.owner_data_gate_decision_digest, data.decision_digest),
                    (artifacts.inventory_snapshot_digest, data.inventory_snapshot_digest),
                    (artifacts.source_route_catalog_digest, data.source_route_catalog_digest))):
                raise ValueError("comparison_case_data_binding_mismatch")
            async with Client(data.mcp_server, raise_exceptions=False, read_timeout_seconds=120) as client:
                bound = await client.call_tool("get_dell_research_method", {"branch_ids": [b["branch_id"] for b in case["branch_topics"]],
                    "research_as_of": artifacts.research_as_of, "data_snapshot_id": artifacts.snapshot_id,
                    "execution_attempt_id": invocation})
                if bound.is_error:
                    raise ValueError("comparison_read_only_method_binding_failed")
                tools = await case_mcp_tools(client, run_scope=bound.structured_content["run_scope"])
                public, private = session_audit_sinks(out / "calls" / variant) if execute else (None, None)
                outcomes = []
                def public_sink(event):
                    public(event)
                    if event.get("event") == "outcome":
                        outcomes.append(event)
                        if not event.get("usage_reported"):
                            shared["unknown"] = True
                        else:
                            hit, inp, output = event.get("cache_hit_tokens"), event["input_tokens"], event["output_tokens"]
                            if hit is None:
                                shared["unknown"] = True
                            else:
                                shared["spent"] += sum(cost_parts(profile.model, hit, inp-hit, output, peak_multiplier(event["recorded_at"])).values())
                        print(json.dumps({"variant": variant, "event": "model_outcome", "status": event["status"],
                            "input_tokens": event.get("input_tokens"), "output_tokens": event.get("output_tokens"),
                            "batch_modeled_cny": round(shared["spent"], 7), "unknown_usage": shared["unknown"]}), flush=True)
                audit = ComparisonAudit(shared=shared, model=model, actor=variant, profile=profile, basis=basis,
                    public_sink=public_sink, private_sink=private) if execute else None
                probe = SourceProbe(report={k: v for k, v in report_model_view(original["report"]).items() if k != "chart_display_values"})
                active_model = model if execute else probe
                agent = build_case_output_agent(role="writer", model=active_model, tools=tools, artifacts=artifacts,
                    limits=LIMITS, audit=audit, report_revision=True, allow_report_edits=edits)
                run_id = uuid4()
                try:
                    result = await agent.ainvoke(input_state(snapshot, artifacts), {"run_id": run_id,
                        "run_name": "report_revision_comparison_" + variant, "recursion_limit": 40,
                        "tags": ["bounded-development-comparison", out.name]})
                    if execute:
                        write_new(out / (variant + ".candidate.private.json"), result["output"])
                        write_new(out / (variant + ".messages.private.json"), [m.model_dump(mode="json") for m in result["messages"]])
                    row = {"variant": variant, "status": "candidate_produced" if execute else "offline_source_and_submission_pass",
                        "trace_id": str(run_id) if execute else None, "model_calls": len(outcomes) if execute else 0,
                        "output_characters": len(result["output"]["narrative_markdown"]),
                        "citations": len(result["output"]["citations"]), "charts": len(result["output"].get("charts", []))}
                    if not execute:
                        if any(m.type == "tool" and m.status != "success" for m in result["messages"]):
                            raise ValueError("offline_source_or_submission_tool_error")
                        payload = model._get_request_payload(probe.contexts[0], tools=probe.tool_schemas)
                        row.update(first_request_utf8_bytes=len(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
                            first_request_message_characters=sum(len(str(m.content)) for m in probe.contexts[0]),
                            tool_count=len(probe.tool_schemas))
                        # Store only the actual read-tool response; no dummy private reasoning.
                        write_new(out / (variant + ".source-probe.private.json"), [m.content for m in result["messages"] if m.type == "tool" and m.name == "read_current_source"])
                except Exception as exc:
                    row = {"variant": variant, "status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:600],
                        "trace_id": str(run_id) if execute else None}
                    summary.append(row)
                    write_new(out / ("result.json" if execute else "preparation.json"), {"variants": summary, "modeled_cny": shared["spent"]})
                    raise
                summary.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
        if original != snapshot["state"]:
            raise ValueError("comparison_original_snapshot_changed")
    write_new(out / ("result.json" if execute else "preparation.json"), {"variants": summary,
        "modeled_cny": shared["spent"], "unknown_usage": shared["unknown"], "product_acceptance": False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--snapshot", type=Path, help="Reuse an existing read-only export for a fresh local preparation.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env", override=False)
    if not args.execute:
        args.output.mkdir(parents=True, exist_ok=True)
        if (args.output / "execution.json").exists() or (args.output / "preparation.json").exists():
            raise ValueError("comparison_output_already_used")
        if not (args.output / "snapshot.private.json").exists():
            snapshot = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot else capture_checkpoint()
            write_new(args.output / "snapshot.private.json", snapshot)
        with tracing_context(enabled=False):
            asyncio.run(run_comparison(root, args.output, False))
        return
    if not (args.output / "preparation.json").is_file():
        raise ValueError("offline_preparation_required")
    preparation = json.loads((args.output / "preparation.json").read_text(encoding="utf-8"))
    if len(preparation["variants"]) != 2 or any(v["status"] != "offline_source_and_submission_pass" for v in preparation["variants"]):
        raise ValueError("successful_offline_preparation_required")
    ls = LangSmithClient(api_key=os.environ.get("LANGSMITH_API_KEY"), hide_inputs=True, hide_outputs=True)
    project = ls.read_project(project_name="fin-insight-dell-reference-vertical")
    with tracing_context(enabled=True, project_name=project.name, client=ls):
        try:
            asyncio.run(run_comparison(root, args.output, True))
        finally:
            from langchain_core.tracers.langchain import wait_for_all_tracers
            wait_for_all_tracers()


if __name__ == "__main__":
    main()
