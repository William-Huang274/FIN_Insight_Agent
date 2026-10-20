"""Replay accepted local reviews into native Lead handoff; no model or network.

Input is a private run directory containing parent-entry, convergence-state,
review-entry and confirmation-result. Output is a separate private directory.
The original accepted review is reused verbatim, never regenerated or graded.
"""
import argparse
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
from types import SimpleNamespace
from unittest.mock import patch

from langgraph.checkpoint.memory import InMemorySaver
from sec_agent.agent_runtime.research_convergence import build_research_convergence_graph
from sec_agent.agent_runtime.research_session import current_task_artifacts, responsible_author_feedback
from sec_agent.agent_runtime.case_review_agent import case_review_scope_digest
from sec_agent.agent_runtime.review_recovery import public_review


class LeadBoundary(Exception):
    pass


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


async def run(run_dir, output):
    assert not output.resolve().is_relative_to(run_dir.resolve()), "Keep output outside original records"
    assert not output.exists(), "Use a new output directory; preserve prior replay."
    output.mkdir(parents=True)
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in run_dir.rglob("*") if p.is_file()}
    parent = load(run_dir / "parent-entry.private.json")
    saved = load(run_dir / "convergence-state.private.json")
    entry = load(run_dir / "review-entry.private.json")
    accepted = load(run_dir / "confirmation-result.private.json")
    artifacts = current_task_artifacts(parent)
    current = artifacts.with_revisions(saved["revisions"])
    assert accepted["scope_digest"] == case_review_scope_digest(current, entry["question"])
    assert accepted["phase"] == "case_review_ready_for_convergence"
    try:
        responsible_author_feedback(accepted, current, include_advisory=True)
    except ValueError as exc:
        assert str(exc) == "research_review_paper_scope_mismatch"
    else:
        raise AssertionError("Fixture no longer reproduces the old full-scope mismatch")
    captured = {}
    reused = []

    class CaptureLead:
        async def aget_state(self, config):
            return SimpleNamespace(values={}, next=())

        async def ainvoke(self, value, config):
            captured["input"] = json.loads(value["messages"][0].content)
            raise LeadBoundary("Native Lead input assembled; no agent/model executed")

    def make_agent(role, actual, **kwargs):
        assert role == "lead_decision", "No specialist, reviewer or writer replay"
        assert actual.catalog() == current.catalog()
        captured["role"] = role
        captured["feedback"] = deepcopy(kwargs["feedback"])
        return CaptureLead()

    async def reuse(actual, context, config):
        assert context == entry["confirmation"], "Assignment drift; do not infer scope from review"
        assert actual.catalog() == current.catalog()
        reused.append("accepted_confirmation")
        return deepcopy(accepted)

    prior = parent.get("case_review", {})
    review_context = {
        **{r: public_review(prior[r].get("review") or {}) for r in ("counter", "verifier") if r in prior},
        "lead_handoff": parent.get("research_handoff"),
        "incomplete_review_records": {
            r: {k: prior[r].get(k) for k in ("status", "recorded_findings", "incomplete_output")}
            for r in ("counter", "verifier")
            if prior.get(r, {}).get("status") not in (None, "review_submitted")},
    }
    graph = build_research_convergence_graph(artifacts=artifacts, question=entry["question"],
        feedback={}, research_review_context=review_context, max_correction_rounds=2,
        make_agent=make_agent, review_revisions=reuse, hierarchical=True,
        execution_plan=(parent.get("research_handoff") or {}).get("execution_plan")
        ).compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "offline-confirmation-feedback"}, "recursion_limit": 20}
    seed = deepcopy(saved)
    seed["stop_reason"] = None
    # All authors already completed this correction round. Re-enter the native
    # route before confirmation so its existing version/closure checks execute.
    with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
        await graph.aupdate_state(config, seed, as_node="responsible_author")
        try:
            await graph.ainvoke(None, config)
        except LeadBoundary:
            pass
        else:
            raise AssertionError("Did not stop at native Lead boundary")
    snapshot = await graph.aget_state(config)
    result = snapshot.values
    assert snapshot.next == ("lead_decision",)
    assert reused == ["accepted_confirmation"]
    assert result["workpaper_confirmation"]["review"] == accepted
    assert result["revisions"] == saved["revisions"]
    assert result["author_completed"] == saved["author_completed"]
    assert captured["input"]["findings_to_handle"] == result["pending_feedback"]
    original = [f for role in ("counter", "verifier") for f in accepted[role]["review"]["findings"]]
    routed = [f for rows in result["pending_feedback"].values() for f in rows]
    assert len(original) == len(routed)
    for finding in routed:
        raw = next(f for f in accepted[finding["reviewer"]]["review"]["findings"]
                   if f["finding_id"] == finding["original_finding_id"])
        assert all(finding[k] == v for k, v in raw.items() if k != "finding_id")
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items())
    for name, value in (("lead-handoff.private.json", captured),
                        ("convergence-state.private.json", result)):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"provider_calls": 0, "reviewer_calls": 0, "author_calls": 0,
        "native_lead_input_reached": True, "lead_decision_executed": False,
        "next_node": "lead_decision", "resume_after_node": "confirm_workpapers",
        "accepted_reviews_unchanged": True, "revisions_unchanged": True,
        "source_files_unchanged": len(hashes), "paper_count": len(current.catalog()["papers"]),
        "assigned_papers": sorted(entry["confirmation"]["findings_to_confirm"]),
        "routed_findings": len(routed), "financial_conclusions_verified": False}
    (output / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.run_dir, args.output))
