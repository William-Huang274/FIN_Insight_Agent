"""Offline period-check replay: original save, current author and review handoff.

Writes diagnostic observations only; never a recovery state or author edits.
Input paths must identify the original pre-save state and its saved result.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from sec_agent.agent_runtime.author_revision import author_feedback
from sec_agent.agent_runtime.period_relations import workpaper_period_checks
from sec_agent.agent_runtime.research_session import current_task_artifacts
from sec_agent.agent_runtime.specialist_graph import SaveWorkpaperEditsAction
from sec_agent.agent_runtime.workpaper_changes import confirmation_context
from sec_agent.agent_runtime.workpaper_drafts import save_draft


def main(args):
    paths = [args.before, args.saved, args.parent, args.convergence]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before, saved, parent, convergence = [
        json.loads(p.read_text(encoding="utf-8")) for p in paths]
    calls = saved["notebook"]["model_turn_records"][-1]["action"]["tool_calls"]
    calls = [c for c in calls if c["name"] == "SaveWorkpaperEditsAction"]
    if len(calls) != 1:
        raise ValueError("replay_requires_one_original_save_action")
    action = SaveWorkpaperEditsAction.model_validate_json(json.dumps(calls[0]["args"]))
    original = deepcopy((before, saved, convergence))
    with patch("socket.socket.connect", side_effect=AssertionError("offline_replay_network_forbidden")):
        draft, receipt = save_draft(before, action)
        assert draft["arguments"] == saved["workpaper_draft"]["arguments"]
        assert draft["digest"] == saved["workpaper_draft"]["digest"]
        assert receipt["saved"] and not receipt["submitted"] and not receipt["accepted"]
        assert receipt.get("period_relation_checks"), "record has no period-check observation"
        assert receipt["period_relation_checks"] == workpaper_period_checks(draft["arguments"])
        artifacts = current_task_artifacts(parent)
        current = artifacts.with_revisions(convergence["revisions"])
        feedback = convergence["pending_feedback"]
        author = author_feedback(feedback[args.paper], current)
        review = confirmation_context(artifacts, convergence["revisions"], feedback,
            artifact_history=convergence.get("artifact_history", ()),
            confirmation_history=convergence.get("confirmation_history", ()))
        assert review["findings_to_confirm"] == feedback
        assert review["runtime_period_checks"][args.paper] == workpaper_period_checks(
            current.read_paper(args.paper))
        for old, new in zip(feedback[args.paper], author):
            assert old["finding_id"] == new["finding_id"]
            if old.get("lead_requested_change"):
                assert old["lead_requested_change"] == new["lead_requested_change"]
        observations = {
            "original_save_receipt": receipt,
            "current_candidate_checks": workpaper_period_checks(draft["arguments"]),
            "author_remedy_checks": [c for f in author for c in f.get("runtime_period_checks", [])],
            "targeted_review_checks": review["runtime_period_checks"][args.paper],
        }
        assert observations["author_remedy_checks"], "Lead remedy check missing"
    assert (before, saved, convergence) == original
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in hashes.items())
    result = {"provider_calls": 0, "original_file_hashes": hashes,
        "original_save_replayed_without_proposal_edits": True,
        "saved_candidate_and_digest_unchanged": True,
        "original_records_unchanged": True, "review_assignment_unchanged": True,
        "diagnostic_observations_injected": False, "financial_quality_pass": False,
        "check_counts": {k: len(v) for k, v in observations.items() if isinstance(v, list)}}
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in (("result", result), ("observations", observations)):
        (args.output / (name + ".json")).write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("before", "saved", "parent", "convergence", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--paper", required=True)
    main(parser.parse_args())
