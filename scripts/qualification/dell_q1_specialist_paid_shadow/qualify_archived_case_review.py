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

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, messages_from_dict
from langgraph.checkpoint.memory import InMemorySaver
from langsmith import tracing_context
from mcp import Client
from mcp.server.mcpserver import MCPServer
from pydantic import SecretStr

from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
from sec_agent.agent_runtime.dell_case_artifacts import DellCaseArtifacts, register_case_artifact_tools, revision_review_target
from sec_agent.agent_runtime.dell_case_review_agent import CaseModelAudit, build_case_reviewer, case_chat_model, case_mcp_tools
from sec_agent.agent_runtime.dell_case_convergence_agent import build_case_output_agent, paper_revision_input
from sec_agent.research_foundation.research_methods import get_research_method
from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _dotenv, _write_new


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--prepare-only", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--author-findings-file", type=Path, help="Repair only saved public findings; an incomplete review stays incomplete.")
    mode.add_argument("--revision-file", type=Path, help="Independently inspect a previously submitted author revision on this archived base.")
    parser.add_argument("--continue-author-state", "--continue-state", dest="continue_author_state", type=Path,
        help="Continue this same actor's archived messages with remaining original call budget; not a live-thread resume.")
    parser.add_argument("--author-output-tokens", type=int, choices=(10000, 16000), default=10000,
        help="Explicitly qualified author output ceiling; does not change reviewer limits.")
    parser.add_argument("--review-output-tokens", type=int, choices=(6000, 12000), default=6000)
    parser.add_argument("--revision-only", action="store_true", help="Bind review to computed changes; cannot count as complete paper acceptance.")
    args = parser.parse_args()
    args.output_dir.mkdir(exist_ok=False)
    raw = args.state_file.read_bytes()
    state = json.loads(raw)
    state = state.get("values", state)
    artifacts = DellCaseArtifacts(state["case_papers"])
    if len(artifacts.catalog()["papers"]) != 1:
        raise ValueError("this_bounded_qualification_requires_one_existing_paper")
    feedback, input_artifact, target = [], None, None
    if args.revision_only and not args.revision_file:
        raise ValueError("revision_only_requires_revision_file")
    paper_id = artifacts.catalog()["papers"][0]["paper_id"]
    if args.author_findings_file or args.revision_file:
        input_path = args.author_findings_file or args.revision_file
        input_raw = input_path.read_bytes()
        prior_manifest = json.loads(input_path.with_name("manifest.json").read_text(encoding="utf-8"))
        if prior_manifest["source_sha256"] != sha256(raw).hexdigest():
            raise ValueError("qualification_input_base_mismatch")
        prior = json.loads(input_raw)
        input_artifact = {"path": str(input_path), "sha256": sha256(input_raw).hexdigest()}
        if args.author_findings_file:
            feedback = list(prior.get("recorded_findings", {}).values())
            if not feedback or any(f["paper_id"] != paper_id for f in feedback):
                raise ValueError("qualification_requires_saved_findings_for_this_paper")
        else:
            if args.revision_only:
                target = revision_review_target(artifacts, paper_id, prior["revision"])
            artifacts = artifacts.with_revisions({paper_id: prior["revision"]})
    repairing = bool(args.author_findings_file)
    restored, continuation = None, None
    model_limit, tool_limit = 6, 16
    if args.continue_author_state:
        parent_path = args.continue_author_state
        parent_raw = parent_path.read_bytes()
        parent_manifest = json.loads(parent_path.with_name("manifest.json").read_text(encoding="utf-8"))
        if (parent_manifest["source_sha256"] != sha256(raw).hexdigest()
                or parent_manifest["input_artifact"] != input_artifact
                or parent_manifest["question"] != args.question
                or parent_manifest["mode"] != ("responsible_author" if repairing else "independent_reviewer")
                or parent_manifest.get("revision_target") != target):
            raise ValueError("continuation_author_input_mismatch")
        restored = json.loads(parent_raw)
        if restored.get("output") or restored.get("review"):
            raise ValueError("cannot_continue_submitted_author")
        restored["messages"] = messages_from_dict([{"type": m["type"], "data": m} for m in restored["messages"]])
        parent_events = [json.loads(line) for line in parent_path.with_name("model-call-events.jsonl").read_text(encoding="utf-8").splitlines()]
        # A truncated provider response may not enter graph state. Count real
        # transports, not AIMessage count, so continuation cannot renew its cost.
        consumed_models = (parent_manifest.get("continuation") or {}).get("consumed_model_calls", 0)
        consumed_models += sum(row.get("event") == "started" and row.get("provider_call_attempted") is True for row in parent_events)
        consumed_tools = sum(isinstance(m, ToolMessage) for m in restored["messages"])
        model_limit -= consumed_models
        tool_limit -= consumed_tools
        if min(model_limit, tool_limit) < 1:
            raise ValueError("original_author_budget_exhausted")
        continuation = {"path": str(parent_path), "sha256": sha256(parent_raw).hexdigest(),
            "consumed_model_calls": consumed_models, "consumed_tool_calls": consumed_tools,
            "projection": "Replace initial author host seed with production paper_revision_input; reviewer seed unchanged. Preserve all original model/tool messages including reasoning. No sibling context and no renewed budget."}
    basis = TokenBudgetBasis(node_role="specialist" if repairing else "counter",
        node_purpose=("Correct the existing responsible paper against saved public findings, preserving unaffected claims and explicit unresolved work."
            if repairing else "Inspect the requested financial bridge in one archived paper and submit actionable findings; no whole-case acceptance."),
        input_scale="One archived submitted paper; source-ID windows default 4000 characters, calculator operands retained. No private sibling history or external retrieval.",
        required_outputs=(("source-bound changed claims and revised prose", "disposition of each finding and unresolved work") if repairing
            else ("paper assessment", "source-bound findings or explicit unresolved checks")),
        schema_burden=("Existing PaperRevision: changed claims only, replacement thesis/mechanism/narrative and finding responses. One paper, not a final report."
            if repairing else "Existing CaseReviewFinding and CaseReview tools; recorded findings merge without retransmission."),
        materiality_quality_risk="Incorrect period/delta or causal attribution can change the thesis. Never hide an unfinished check to fit the limit.",
        comparable_run_evidence="Focused review a1:6 calls/110284 tokens/no finding; a2 saved one financial bridge finding but incomplete. Author repair is a different output workload, not a same-condition saving comparison.",
        reasoning_profile="agentic_message_history_thinking_enabled", max_input_characters=100000,
        max_output_tokens=args.author_output_tokens if repairing else args.review_output_tokens, timeout_seconds=240 if repairing else 180, max_transport_attempts=1, retry_policy="none",
        truncation_stop_behavior="fail_closed_no_partial_promotion", input_ceiling_behavior="fail_before_transport")
    if target:
        basis = TokenBudgetBasis.model_validate_json(json.dumps({**basis.model_dump(mode="json"),
            "node_purpose": "Independently verify actual changed claim/prose against original sources and return a scoped review; unchanged research is not accepted.",
            "input_scale": f"One mechanically computed revision target ({len(json.dumps(target, ensure_ascii=False))} characters); {len(target['changed_claim_ids'])} changed claims. Original source/calculation windows on demand; no full source catalog or sibling history.",
            "required_outputs": ["revision-only assessment with source-grounded public rationale", "valid exact-quote findings or explicit necessary scope expansion"],
            "comparable_run_evidence": "Scoped review a2 used 6 calls / 126018 tokens, submitted prose admitting unfinished checks but omitted the list. Current native submission requires explicit completion and offers FTS5 search over the same saved sources. This is a changed-interface qualification, not a same-condition saving benchmark.",
            "schema_burden": "Native CaseReview tools with required completion/unresolved fields for revision-only submission and host-bound revision_scope. Output ceiling includes reasoning and complete findings; no full report rewrite."}))
    _write_new(args.output_dir / "manifest.json", {"source_sha256": sha256(raw).hexdigest(),
        "source_path": str(args.state_file), "question": args.question, "catalog": artifacts.catalog(), "input_artifact": input_artifact,
        "mode": "responsible_author" if repairing else "independent_reviewer",
        "TokenBudgetBasis": basis.model_dump(mode="json"), "max_model_calls": model_limit, "max_tool_calls": tool_limit,
        "continuation": continuation,
        "revision_target": target,
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
    audit = CaseModelAudit(actor="author:archived-focused-repair" if repairing else "verifier:archived-focused-review", profile=profile, basis=basis,
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
            if repairing:
                agent = build_case_output_agent(role="repair", model=model, tools=tools, artifacts=artifacts,
                    feedback=feedback, paper_id=paper_id, limits={"model_calls": model_limit, "tool_calls": tool_limit}, audit=audit)
            else:
                agent = build_case_reviewer(role="verifier", model=model, tools=tools, artifacts=artifacts,
                    max_model_calls=model_limit, max_tool_calls=tool_limit, audit=audit,
                    method_instructions=json.dumps(get_research_method("verifier"), ensure_ascii=False), revision_target=target)
            # Agent Server owns production persistence; isolated qualification
            # uses its same compiled graph with a native in-memory checkpointer.
            saver = InMemorySaver()
            agent.checkpointer = saver
            config = {"configurable": {"thread_id": args.output_dir.name}, "recursion_limit": 80}
            body = {
                    "question": args.question, "catalog": artifacts.catalog(),
                    "boundary": "Only original archived sources are exposed. If their context is insufficient, report the missing check; do not claim public non-disclosure."}
            if target:
                body.pop("catalog")
                body["review_scope"] = {k: target[k] for k in ("kind", "paper_id", "changed_claim_ids", "boundary")}
            if repairing:
                body.update(**paper_revision_input(artifacts, paper_id, feedback),
                    review_boundary="These saved findings come from an incomplete review. Correct their proved errors; do not presume unreviewed content has passed. Reviewer suggestions may also be wrong.")
            with tracing_context(enabled=False):
                seed = HumanMessage(content=json.dumps(body, ensure_ascii=False))
                value = {"messages": [seed]}
                if restored:
                    if not isinstance(restored["messages"][0], HumanMessage):
                        raise ValueError("continuation_initial_seed_not_human")
                    value = {**restored, "messages": [seed if repairing else restored["messages"][0], *restored["messages"][1:]]}
                result = await agent.ainvoke(value, config)
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        if agent is not None and config is not None:
            result = (await agent.aget_state(config)).values
    if result:
        _write_new(args.output_dir / "state.private.json", {**result,
            "messages": [m.model_dump(mode="json") for m in result.get("messages", [])]})
    public = {"review": result.get("review") if result else None,
        "revision": result.get("output") if repairing and result else None,
        "recorded_findings": result.get("recorded_findings", {}) if result else {},
        "error": error, "accepted": False,
        "model_output": [m.content for m in result.get("messages", []) if isinstance(m, AIMessage) and m.content] if result else []}
    _write_new(args.output_dir / "result.json", public)
    print(json.dumps({"review_submitted": bool(public["review"]),
        "revision_review_completion": (public["review"] or {}).get("completion"),
        "revision_submitted": bool(public["revision"]),
        "recorded_findings": len(public["recorded_findings"]), "error": error}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
