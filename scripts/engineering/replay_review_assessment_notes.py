"""Offline replay of an unchanged review proposal through native tools.

All inputs are private saved records. No model transport, new source selection,
manual classification, or automatic promotion into a live continuation.
"""
import argparse
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
from unittest.mock import patch

from replay_review_argument_recovery import load, restored, SavedResponse
from langchain_core.messages import AIMessage, ToolMessage
from sec_agent.agent_runtime.case_review_agent import build_case_reviewer
from sec_agent.agent_runtime.research_session import current_task_artifacts
from sec_agent.agent_runtime.review_recovery import public_review, public_confirmation
from sec_agent.agent_runtime.review_submission_notes import preserve_assessment_notes


async def run(args):
    h, out = args.run_dir, args.output
    assert not out.exists(), "Use a fresh output directory."
    assert not out.resolve().is_relative_to(h.resolve()), "Do not overwrite original records."
    index = f"{args.call_index:03d}"
    paths = [h/"parent-entry.private.json", h/"convergence-state.private.json",
        h/"review-entry.private.json", h/f"request-states/{index}.private.json",
        h/f"model-responses/{index}.private.json", h/f"actor-states/confirmation_{args.role}.private.json"]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    seed = restored(load(paths[3])["state"])
    original = AIMessage.model_validate(load(paths[4])["raw_response"])
    assert len(original.tool_calls) == 1 and original.tool_calls[0]["name"] == "submit_case_review"
    original_args = deepcopy(original.tool_calls[0]["args"])
    normalized, records = preserve_assessment_notes(original_args)
    assert records and preserve_assessment_notes(normalized) == (normalized, [])
    artifacts = current_task_artifacts(load(paths[0])).with_revisions(load(paths[1])["revisions"])
    original_papers = {p["paper_id"]: artifacts.read_paper(p["paper_id"])
        for p in artifacts.catalog()["papers"]}
    entry = load(paths[2])
    model = SavedResponse(response=original)
    agent = build_case_reviewer(role=args.role, model=model, artifacts=artifacts, tools=[],
        confirmation=entry["confirmation"], require_inspection=entry["require_inspection"],
        max_model_calls=1)
    inputs = {k: v for k, v in seed.items() if k in ("messages", "recorded_findings",
        "recorded_inspections", "request_summary", "request_summary_failure", "author_change_projection")}
    state = None
    async for value in agent.astream(inputs, stream_mode="values"):
        receipts = {m.tool_call_id: m for m in value["messages"] if isinstance(m, ToolMessage)}
        if original.tool_calls[0]["id"] in receipts:
            state = value
            break
    assert state is not None and model.replay_count == 1
    assert original.tool_calls[0]["args"] == original_args
    prior_tools = [m for m in seed["messages"] if isinstance(m, ToolMessage)]
    for m in prior_tools:
        assert receipts[m.tool_call_id] == m
    emitted = next(m for m in reversed(state["messages"]) if isinstance(m, AIMessage))
    assert emitted.tool_calls[0]["args"] == normalized
    assert emitted.response_metadata["tool_argument_recovery"][-1]["original_arguments"] == original_args
    # Normalization must not touch any research decision, source or calculation.
    for key, value in original_args["review"].items():
        if key != "assessments":
            assert normalized["review"][key] == value
    for old, new in zip(original_args["review"]["assessments"], normalized["review"]["assessments"]):
        assert new["paper_id"] == old["paper_id"] and new["assessment"] == old["assessment"]
        if "verdict_note" in old:
            assert any(n["text"] == old["verdict_note"] and n["original_field"] == "verdict_note"
                for n in new["supplemental_notes"])
    receipt = receipts[original.tool_calls[0]["id"]]
    accepted = bool(state.get("review"))
    if accepted:
        assert receipt.status == "success"
        delivered = public_review(state["review"])
        assert delivered["assessments"] == normalized["review"]["assessments"]
        public_handoff = public_confirmation({"review": {args.role: {
            "status": "review_submitted", "review": state["review"],
            "runtime_parsing": state.get("runtime_parsing", [])}}})
        annotation = public_handoff["review"][args.role]["annotation_preservation"]
        assert len(annotation) == len(records)
        for old, new in zip(original_args["review"].get("finding_checks", []),
                            state["review"].get("finding_checks", [])):
            for key, val in old.items():
                if key != "source_checks":
                    assert new[key] == val
            for source in old.get("source_checks", []):
                assert any(all(bound.get(k) == v for k, v in source.items())
                    for bound in new.get("source_checks", []))
        for old, new in zip(original_args["review"].get("inspection_checks", []),
                            state["review"].get("inspection_checks", [])):
            assert new["result"] == old["result"]
            assert new.get("calculation_ids", []) == old.get("calculation_ids", [])
    else:
        assert receipt.status != "success" or "selection_required" in receipt.content
        delivered = None
        public_handoff = None
    assert {pid: artifacts.read_paper(pid) for pid in original_papers} == original_papers
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == sha for p, sha in hashes.items())
    out.mkdir(parents=True)
    def save(name, obj):
        (out/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2,
            default=lambda x: x.model_dump(mode="json")), encoding="utf-8")
    save("normalized-proposal.private.json", emitted)
    save("submission-receipt.private.json", receipt)
    save("review-for-lead.private.json", delivered)
    save("public-confirmation.private.json", public_handoff)
    save("runtime-parsing.private.json", state.get("runtime_parsing", []))
    # Preserve real usage counters; this replay is not another provider request.
    observed = load(paths[5])
    for key in ("thread_model_call_count", "run_model_call_count", "thread_tool_call_count", "run_tool_call_count"):
        if key in observed:
            state[key] = observed[key]
    save("replayed-state.private.json", state)
    result = {"provider_calls": 0, "network_calls": 0, "review_accepted": accepted,
        "original_proposal_unchanged": True, "normalization_idempotent": True,
        "original_hashes": hashes, "papers_unchanged": len(original_papers),
        "prior_successful_receipts_preserved": sum(m.status == "success" for m in prior_tools),
        "annotation_records": records, "tool_status": receipt.status, "tool_feedback": receipt.content,
        "lead_public_review_preserves_notes": accepted, "lead_called": False,
        "live_checkpoint_updated": False, "host_changed_decisions": False,
        "financial_quality_pass": False, "remaining_paid_calls": 0}
    save("result.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("annotation_records", "original_hashes")},
        ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--call-index", type=int, default=3)
    parser.add_argument("--role", choices=("verifier", "counter"), default="verifier")
    args = parser.parse_args()
    async def offline():
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Offline replay forbids network")):
            await run(args)
    asyncio.run(offline())
