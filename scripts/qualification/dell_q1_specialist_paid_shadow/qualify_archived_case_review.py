"""Bounded native reviewer qualification against immutable archived papers.

No research rerun, source fetch, report acceptance or live-thread mutation.
Uses the production reviewer, official MCP tools, SDK and native checkpoint.
"""
from __future__ import annotations

import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langsmith import tracing_context
from mcp import Client
from mcp.server.mcpserver import MCPServer
from pydantic import SecretStr

from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
from sec_agent.agent_runtime.dell_case_artifacts import DellCaseArtifacts, register_case_artifact_tools
from sec_agent.agent_runtime.dell_case_review_agent import CaseModelAudit, build_case_reviewer, case_chat_model, case_mcp_tools
from sec_agent.research_foundation.research_methods import get_research_method
from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _dotenv, _write_new


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(exist_ok=False)
    raw = args.state_file.read_bytes()
    state = json.loads(raw)
    state = state.get("values", state)
    artifacts = DellCaseArtifacts(state["case_papers"])
    if len(artifacts.catalog()["papers"]) != 1:
        raise ValueError("this_bounded_qualification_requires_one_existing_paper")
    basis = TokenBudgetBasis(node_role="counter",
        node_purpose="Inspect the requested financial bridge in one archived paper and submit actionable findings; no whole-case acceptance.",
        input_scale="One archived submitted paper; source-ID windows default 4000 characters, calculator operands retained. No private sibling history or external retrieval.",
        required_outputs=("paper assessment", "source-bound findings or explicit unresolved checks"),
        schema_burden="Existing CaseReviewFinding and CaseReview tools; recorded findings merge without retransmission.",
        materiality_quality_risk="Incorrect period/delta or causal attribution can change the thesis. Never hide an unfinished check to fit the limit.",
        comparable_run_evidence="HPE a5: 49 calls,969171 known tokens,1 unknown; not directly comparable to this focused single-reviewer diagnostic.",
        reasoning_profile="agentic_message_history_thinking_enabled", max_input_characters=100000,
        max_output_tokens=6000, timeout_seconds=180, max_transport_attempts=1, retry_policy="none",
        truncation_stop_behavior="fail_closed_no_partial_promotion", input_ceiling_behavior="fail_before_transport")
    _write_new(args.output_dir / "manifest.json", {"source_sha256": sha256(raw).hexdigest(),
        "source_path": str(args.state_file), "question": args.question, "catalog": artifacts.catalog(),
        "TokenBudgetBasis": basis.model_dump(mode="json"), "max_model_calls": 6, "max_tool_calls": 16,
        "model": "deepseek-v4-flash", "reasoning_effort": "low", "automatic_retry": False,
        "scope": "known-problem node qualification, not blind evaluation or product acceptance"})
    if args.prepare_only:
        print(json.dumps({"prepared": True, "paper_count": 1, "paid_calls": 0}))
        return

    def sink(filename):
        def write(row):
            with (args.output_dir / filename).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        return write

    profile = DeepSeekModelProfile(model="deepseek-v4-flash", thinking="enabled", reasoning_effort="low")
    audit = CaseModelAudit(actor="verifier:archived-focused-review", profile=profile, basis=basis,
        public_sink=sink("model-call-events.jsonl"), private_sink=sink("model-context.private.jsonl"))
    server = MCPServer("archived-case-review")
    register_case_artifact_tools(server, artifacts)
    result, error, agent, config = None, None, None, None
    try:
        secrets = _dotenv()
        model = case_chat_model(profile, basis, SimpleNamespace(base_url="https://api.deepseek.com"),
            SecretStr(secrets["DEEPSEEK_API_KEY"]), context_editing={"trigger_tokens": 16000, "keep": 2})
        async with Client(server, raise_exceptions=False) as client:
            tools = await case_mcp_tools(client)
            agent = build_case_reviewer(role="verifier", model=model, tools=tools, artifacts=artifacts,
                max_model_calls=6, max_tool_calls=16, audit=audit,
                method_instructions=json.dumps(get_research_method("verifier"), ensure_ascii=False))
            # Agent Server owns production persistence; isolated qualification
            # uses its same compiled graph with a native in-memory checkpointer.
            saver = InMemorySaver()
            agent.checkpointer = saver
            config = {"configurable": {"thread_id": args.output_dir.name}, "recursion_limit": 80}
            with tracing_context(enabled=False):
                result = await agent.ainvoke({"messages": [HumanMessage(content=json.dumps({
                    "question": args.question, "catalog": artifacts.catalog(),
                    "boundary": "Only original archived sources are exposed. If their context is insufficient, report the missing check; do not claim public non-disclosure."}, ensure_ascii=False))]}, config)
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        if agent is not None and config is not None:
            result = (await agent.aget_state(config)).values
    if result:
        _write_new(args.output_dir / "state.private.json", {**result,
            "messages": [m.model_dump(mode="json") for m in result.get("messages", [])]})
    public = {"review": result.get("review") if result else None,
        "recorded_findings": result.get("recorded_findings", {}) if result else {},
        "error": error, "accepted": False,
        "model_output": [m.content for m in result.get("messages", []) if isinstance(m, AIMessage) and m.content] if result else []}
    _write_new(args.output_dir / "result.json", public)
    print(json.dumps({"review_submitted": bool(public["review"]),
        "recorded_findings": len(public["recorded_findings"]), "error": error}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
