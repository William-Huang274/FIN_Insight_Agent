"""Bounded context-component rehydration on one archived actor, not a new harness.

LangChain owns the loop; FIN's existing source reader owns exact lookup. Hermes
projection is reused with its original provenance and cost recorded separately.
Full archived messages remain in native state, never replaced by the summary.
"""
import argparse
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, ToolMessage, convert_to_messages, messages_from_dict
from langchain_core.messages.utils import convert_to_openai_messages
from langgraph.checkpoint.memory import InMemorySaver
from langsmith import tracing_context
from mcp import Client
from mcp.server import MCPServer
from pydantic import SecretStr

from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
from sec_agent.agent_runtime.dell_case_artifacts import DellCaseArtifacts, register_case_artifact_tools
from sec_agent.agent_runtime.dell_case_convergence_agent import build_case_output_agent, observed_sources, saved_citation_bindings
from sec_agent.agent_runtime.dell_case_review_agent import CaseModelAudit, case_chat_model, case_mcp_tools
from scripts.qualification.context_transfer_compare import digest
from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _dotenv


class SavedProjection(AgentMiddleware):
    """Request-only replacement of an exact prefix; originals stay in checkpoint."""
    def __init__(self, original, projected):
        self.original, self.projected = deepcopy(original), deepcopy(projected)

    async def awrap_model_call(self, request, handler):
        full = request.state["messages"]
        # Native add_messages assigns IDs; compare payloads without those IDs.
        if [m.model_dump(exclude={"id"}) for m in full[:len(self.original)]] != [m.model_dump(exclude={"id"}) for m in self.original]:
            raise ValueError("archived_projection_prefix_changed")
        return await handler(request.override(messages=[*deepcopy(self.projected), *full[len(self.original):]]))


async def run(args):
    args.output.mkdir(exist_ok=False, parents=True)
    def save(name, value):
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    data = json.loads(args.history.read_text(encoding="utf-8"))
    recorded = next(json.loads(line) for line in args.private_audit.read_text(encoding="utf-8").splitlines()
                    if json.loads(line).get("call_id") == data["source_call_id"] and json.loads(line).get("event") == "request")
    native = messages_from_dict([{"type": m["type"], "data": {**m, "additional_kwargs": {}}} for m in recorded["messages"]])
    if digest(convert_to_openai_messages(native)) != digest(data["messages"]):
        raise ValueError("private_native_history_does_not_match_shared_export")
    original = [m for m in native if m.type != "system"]
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))["snapshot"]["state"]
    artifacts = DellCaseArtifacts(snapshot["case_papers"])
    artifacts = artifacts.with_saved_calculations(saved_citation_bindings(original))
    calculations = {ref: item for ref, item in {**artifacts._sources, **observed_sources(original)}.items() if ref.startswith("CALC::")}
    for message in original:
        if isinstance(message, ToolMessage) and message.name == "read_current_source" and message.status == "success":
            try:
                body = json.loads(message.content)
            except (TypeError, ValueError):
                continue
            if isinstance(body, dict) and str(body.get("citation_id", "")).startswith("CALC::"):
                calculations.setdefault(body["citation_id"], body)
    if not calculations:
        raise ValueError("archived_history_has_no_exact_calculations")
    projection = None
    if args.projection:
        provenance = json.loads(args.projection.with_name("result.json").read_text(encoding="utf-8"))
        if provenance["source_digest"] != digest(data["messages"]):
            raise ValueError("projection_does_not_belong_to_same_history")
        projection = convert_to_messages([m for m in json.loads(args.projection.read_text(encoding="utf-8")) if m["role"] != "system"])
    question = ("只做已保存会话的只读接续，不继续投研或修改报告。请用 read_current_source 回读以下已经观察过的计算记录，"
                "然后列出每条完整 CALC ID、公式、精确结果、结果单位，以及全部操作数的原始值、原始单位、期间、来源 ID。"
                "缺失字段写未记录，不猜测。区分算术验证、金融语义验证和数据权威性；保留此前未解决的提交错误。"
                "不要把摘要当原始依据或把失败说成成功。用 submit_case_answer 保存简洁中文答复。计算记录："
                + ", ".join(calculations))
    basis = TokenBudgetBasis(node_role="specialist", node_purpose="Same archived actor context rehydration with exact calculator operands, not financial acceptance.",
        input_scale=f"{len(original)} messages; {len(json.dumps(data['messages'], ensure_ascii=False))} archived characters; {len(calculations)} actual calculations. Same source tools in both arms.",
        required_outputs=("Exact formula/results/all operand values, source IDs, periods, units and authority distinctions", "Unresolved prior submission error retained; no new research"),
        schema_burden="Existing current source reader and source-bound answer submission; public prose, no summary generation.",
        materiality_quality_risk="A short summary may omit financial operands; exact archived state must remain readable. Unknown is not zero or a public-information gap.",
        comparable_run_evidence="204 same historical Hermes projection lost operands in tool-free retention audit. This qualifies rehydration, not Hermes full runtime or whole-report savings.",
        reasoning_profile="agentic_message_history_thinking_disabled", max_input_characters=650000,
        max_output_tokens=6000, timeout_seconds=180, max_transport_attempts=1, retry_policy="none",
        truncation_stop_behavior="fail_closed_no_partial_promotion", input_ceiling_behavior="fail_before_transport")
    manifest = {"history_digest": digest(data["messages"]), "actor": data["actor"], "source_call_id": data["source_call_id"],
        "projection_path": str(args.projection) if args.projection else None,
        "projection_sha256": hashlib.sha256(args.projection.read_bytes()).hexdigest() if args.projection else None,
        "summary_cost": "No new summary call. Previously incurred Hermes compression cost must be added separately.",
        "TokenBudgetBasis": basis.model_dump(mode="json"), "maximum_model_calls": 3, "maximum_tool_calls": 8,
        "question": question, "execute": args.execute}
    if args.execute:
        if not args.preparation:
            raise ValueError("explicit_offline_preparation_required")
        prepared = json.loads((args.preparation / "preparation.json").read_text(encoding="utf-8"))
        prior = json.loads((args.preparation / "manifest.json").read_text(encoding="utf-8"))
        if prepared["errors"] or prepared["read_results"] != len(calculations) or any(
                prior[k] != manifest[k] for k in ("history_digest", "projection_sha256", "question", "TokenBudgetBasis")):
            raise ValueError("preparation_does_not_match_execution")
    save("manifest.json", manifest)
    # Exact expected records are host-side evaluation evidence, not model input.
    save("original-calculations.private.json", calculations)
    profile = DeepSeekModelProfile(model="deepseek-v4-flash", thinking="disabled", reasoning_effort="low")
    known = {"unknown": False}
    def sink(name):
        def emit(row):
            if row.get("event") == "outcome" and row.get("provider_call_attempted") and not row.get("usage_reported"):
                known["unknown"] = True
            with (args.output / name).open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        return emit
    class BoundedAudit(CaseModelAudit):
        async def awrap_model_call(self, request, handler):
            if known["unknown"]:
                raise ValueError("unknown_prior_usage_no_next_model_call")
            return await super().awrap_model_call(request, handler)
    audit = BoundedAudit(actor="hermes_saved_rehydration" if projection else "native_edit_rehydration", profile=profile, basis=basis,
        public_sink=sink("model-call-events.jsonl"), private_sink=sink("model-context.private.jsonl"))
    if projection:
        audit.extra_middlewares.append(SavedProjection(original, projection))
    if args.execute:
        model = case_chat_model(profile, basis, SimpleNamespace(base_url="https://api.deepseek.com"),
            SecretStr(_dotenv()["DEEPSEEK_API_KEY"]), context_editing=None if projection else {"trigger_tokens": 16000, "keep": 2})
    else:
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        probe_calls = []
        class Probe(FakeListChatModel):
            def bind_tools(self, tools, **kwargs): return self
            def _generate(self, messages, **kwargs):
                calls = ([{"name": "read_current_source", "args": {"source_id": ref}, "id": f"probe-{i}", "type": "tool_call"}
                          for i, ref in enumerate(calculations)] if not probe_calls else [{"name": "submit_case_answer",
                    "args": {"answer_markdown": "Offline original source rehydration fixture only. These retained records do not establish financial correctness. "
                        + " ".join(f"[{ref}]" for ref in calculations)}, "id": "probe-submit", "type": "tool_call"}])
                probe_calls.append(True)
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Offline source rehydration only.", tool_calls=calls))])
        model = Probe(responses=["offline"])
        audit = SimpleNamespace(middlewares=lambda: [SavedProjection(original, projection)] if projection else [])
    server = MCPServer("archived-rehydration")
    register_case_artifact_tools(server, artifacts)
    async with Client(server, raise_exceptions=False) as client:
        tools = await case_mcp_tools(client)
        agent = build_case_output_agent(role="writer", model=model, tools=tools, artifacts=artifacts,
            limits={"model_calls": 3, "tool_calls": 8}, audit=audit,
            report_revision=True, allow_answers=True, answer_only=True)
        agent.checkpointer = InMemorySaver()
        config = {"configurable": {"thread_id": args.output.name}, "recursion_limit": 100}
        state = {**{k: deepcopy(snapshot.get(k, {})) for k in ("report", "revisions", "synthesis")},
                 "request_action": "ask", "messages": [*original, HumanMessage(content=question)]}
        if not args.execute:
            result = await agent.ainvoke(state, config)
            reads = [m for m in result["messages"][len(state["messages"]):] if isinstance(m, ToolMessage) and m.name == "read_current_source"]
            errors = [m.content for m in reads if m.status == "error"]
            save("preparation.json", {"calculation_count": len(calculations), "read_results": len(reads), "errors": errors, "provider_calls": 0})
            if len(reads) != len(calculations): raise ValueError("offline_missing_reads")
            if errors: raise ValueError("offline_original_source_reread_failed")
            return
        error = None
        try:
            with tracing_context(enabled=False):
                result = await agent.ainvoke(state, config)
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
            result = (await agent.aget_state(config)).values
        save("state.private.json", {**result, "messages": [m.model_dump(mode="json") for m in result.get("messages", [])]})
        save("result.json", {"output": result.get("output"), "error": error, "financial_acceptance": False})
        print(json.dumps({"answer_submitted": bool(result.get("output")), "error": error}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--private-audit", type=Path, required=True)
    parser.add_argument("--projection", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--preparation", type=Path)
    asyncio.run(run(parser.parse_args()))
