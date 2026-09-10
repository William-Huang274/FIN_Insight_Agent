"""One bounded qualification stage on the production report reviewer/editor.

Host-selected native artifacts only. Separate directories preserve every attempt;
no whole-research rerun, automatic retry, sibling reasoning or data writes.
"""
from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langsmith import tracing_context
from pydantic import SecretStr

from sec_agent.agent_runtime.conversation_handoff import observed_sources
from sec_agent.agent_runtime.dell_case_artifacts import DellCaseArtifacts
from sec_agent.agent_runtime.dell_case_convergence_agent import build_case_output_agent, report_model_view
from sec_agent.agent_runtime.dell_case_review_agent import CaseModelAudit, case_chat_model
from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
from sec_agent.agent_runtime.dell_report_session import session_audit_sinks
from sec_agent.research_foundation.research_methods import get_research_method as read_method


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare(args):
    report, messages = read(args.report), read(args.archive / "messages.json")
    sources = observed_sources({"values": {"messages": messages}})
    artifacts = DellCaseArtifacts.from_observed_sources(sources, case_id=args.archive.name, research_as_of="2026-09-10")
    catalogs = [m["content"] for m in messages if m.get("type") == "tool"
                and m.get("name") == "list_financial_data" and m.get("status", "success") == "success"]
    feedback = read(args.feedback) if args.feedback else None
    if args.role == "writer" and not feedback:
        raise ValueError("writer_requires_saved_review")
    body = {"question": read(args.archive / "question.json")["question"],
            "review_target": "final_report", "report": report_model_view(report),
            "catalog": artifacts.catalog(),
            "boundary": "This is a short saved financial answer with native SQL observations, not a multi-paper case. No research papers exist. Review the supplied question and answer in scope; source records and the actual saved inventory are available on demand. Unqueried or absent from this answer is not absent from the database or public disclosure. Do not demand a full company study for this short question. No outside research is authorized in this stage."}
    if feedback:
        body["independent_review"] = feedback
        body["revision_scope"] = "Assess these fallible findings against sources. Correct justified errors locally, preserve unaffected content and chart values. A reviewer opinion is not evidence."
    if args.baseline:
        baseline = read(args.baseline)
        body["revision_scope"] = "Recheck the actual edits and their meaning in the supplied current report; do not re-open unrelated research. State any indispensable wider check explicitly."
        body["actual_edits"] = report.get("applied_edits", [])
        body["baseline_sha256"] = sha256(args.baseline.read_bytes()).hexdigest()
        if not report.get("applied_edits") or baseline == report:
            raise ValueError("recheck_requires_real_local_edits")

    @tool
    def read_saved_financial_inventory() -> dict:
        """Read the original successful local data catalog observed when this answer was made. Coverage metadata, not proof of a particular value or absence from public disclosure."""
        return {"catalogs": catalogs, "captured": bool(catalogs)}

    @tool
    def get_research_method(method_id: str = "") -> dict:
        """Read the existing research method catalog or selected role method. Guidance only, not case evidence."""
        return read_method(method_id)

    inputs = [args.report, args.archive / "messages.json", args.archive / "question.json"]
    inputs += [p for p in (args.feedback, args.baseline) if p]
    hashes = {str(p.resolve()): sha256(p.read_bytes()).hexdigest() for p in inputs}
    basis = TokenBudgetBasis(node_role="specialist" if args.role == "writer" else "counter",
        node_purpose=("Locally revise a saved answer against fallible independent findings." if args.role == "writer" else "Independently assess financial meaning and materiality in one saved answer or its actual local edits."),
        input_scale=f"One public answer seed, {len(json.dumps(body, ensure_ascii=False))} characters; {len(sources)} native source objects on demand; no sibling model history.",
        required_outputs=("Source-grounded public findings or exact local edits", "Distinguish material errors, advisory edits and indispensable unresolved checks"),
        schema_burden="Existing SubmittedReportReview or ReportTextEdit tools; no new workpaper or source admission.",
        materiality_quality_risk="Correct figures can support a wrong economic conclusion. Reviewer false positives and source coverage overclaims also require checking.",
        comparable_run_evidence="205 MSFT recovery: 2 calls/108069 tokens; MU initial: 5 calls/135962 tokens. Different workloads, not a paired savings baseline. Four calls allow selected source reads, diagnosis, submission and one correction.",
        reasoning_profile="agentic_message_history_thinking_enabled", max_input_characters=100000,
        max_output_tokens=6000, timeout_seconds=240, max_transport_attempts=1, retry_policy="none",
        truncation_stop_behavior="fail_closed_no_partial_promotion", input_ceiling_behavior="fail_before_transport")
    return report, artifacts, body, [read_saved_financial_inventory, get_research_method], hashes, basis


async def run(args):
    report, artifacts, body, tools, hashes, basis = prepare(args)
    args.output.mkdir(parents=True, exist_ok=False)
    profile = DeepSeekModelProfile(model="deepseek-flash", thinking="enabled", reasoning_effort="low")
    method = read_method(args.role)["content"]
    save(args.output / "manifest.json", {"input_sha256": hashes, "role": args.role,
         "model": profile.model_dump(mode="json"), "method": method, "max_model_calls": 4,
         "max_tool_calls": 10, "scope": "known-candidate qualification, not blind or product acceptance"})
    save(args.output / "TokenBudgetBasis.json", basis.model_dump(mode="json"))
    save(args.output / "seed.json", body)
    if not args.execute:
        print(json.dumps({"prepared": True, "paid_calls": 0, "sources": len(artifacts._sources)}))
        return
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _dotenv
        key = _dotenv()["DEEPSEEK_API_KEY"]
    public, private = session_audit_sinks(args.output)
    audit = CaseModelAudit(actor=args.role + ":saved-report", profile=profile, basis=basis,
                           public_sink=public, private_sink=private)
    model = case_chat_model(profile, basis, SimpleNamespace(base_url="https://api.deepseek.com"), SecretStr(key))
    agent = build_case_output_agent(role=args.role, model=model, tools=tools, artifacts=artifacts,
        report_revision=args.role == "writer", require_responsibility=True,
        limits={"model_calls": 4, "tool_calls": 10}, audit=audit, method_instructions=method)
    error, result = None, {}
    async with AsyncSqliteSaver.from_conn_string(str(args.output / "checkpoint.sqlite")) as saver:
        agent.checkpointer = saver
        cfg = {"configurable": {"thread_id": args.output.name}, "recursion_limit": 48}
        try:
            with tracing_context(enabled=False):
                result = await agent.ainvoke({"report": deepcopy(report), "request_action": "revise",
                    "messages": [HumanMessage(content=json.dumps(body, ensure_ascii=False))]}, cfg)
        except Exception as exc:
            error = type(exc).__name__ + ": " + str(exc)[:500]
            result = (await agent.aget_state(cfg)).values
    messages = [m.model_dump(mode="json") for m in result.get("messages", [])]
    save(args.output / "messages.private.json", messages)
    output = result.get("output")
    if output:
        save(args.output / ("report.json" if args.role == "writer" else "review.json"), output)
    outcomes = [e for e in audit.events if e.get("event") == "outcome"]
    summary = {"submitted": bool(output), "error": error,
        "model_calls": len(outcomes), "known_tokens": sum(e.get("total_tokens") or 0 for e in outcomes),
        "unknown_usage_calls": sum(not e.get("usage_reported") for e in outcomes),
        "source_inputs_unchanged": all(sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items()),
        "tools": [{"name": m.get("name"), "status": m.get("status")} for m in messages if m.get("type") == "tool"],
        "financial_acceptance": "pending_human_assessment", "events": outcomes}
    save(args.output / "result.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "events"}), flush=True)
    if error or not output or summary["unknown_usage_calls"] or not summary["source_inputs_unchanged"]:
        raise SystemExit(2)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--feedback", type=Path)
    p.add_argument("--baseline", type=Path)
    p.add_argument("--role", choices=["verifier", "writer"], default="verifier")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--execute", action="store_true")
    asyncio.run(run(p.parse_args()))
