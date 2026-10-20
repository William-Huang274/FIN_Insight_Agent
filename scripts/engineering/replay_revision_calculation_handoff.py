"""Offline accepted-decision calculation handoff. No model or source selection."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from sec_agent.agent_runtime.research_session import current_task_artifacts
from sec_agent.agent_runtime.author_revision import current_author_state
from sec_agent.agent_runtime.revision_calculation_handoff import restore_revision_calculations


def main(args):
    paths = [args.parent, args.convergence]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    parent, convergence = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    artifacts = current_task_artifacts(parent).with_revisions(convergence["revisions"])
    state = current_author_state(artifacts, args.paper, convergence["revisions"])
    decision = convergence["lead_decision"]
    before = deepcopy((state, decision))
    restored = restore_revision_calculations(state, decision, artifacts, args.paper)
    assert (state, decision) == before
    assert restored["final_submission"] == state["final_submission"]
    assert restored["notebook"]["model_turn_count"] == state["notebook"]["model_turn_count"]
    receipts = restored["task_context"]["revision_calculation_handoff"]["receipts"]
    for ref, receipt in receipts.items():
        assert receipt["calculation"] == artifacts.source_item(ref)
        assert receipt["financial_semantics_verified"] is False
    assert restore_revision_calculations(restored, decision, artifacts, args.paper) == restored
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in hashes.items())
    args.output.mkdir(parents=True, exist_ok=False)
    result = {"provider_calls": 0, "original_files_unchanged": True,
        "decision_and_submission_unchanged": True, "calculation_receipts_preserved_exactly": True,
        "idempotent": True, "calculations": list(receipts), "financial_quality_pass": False,
        "diagnostic_observations_injected": False}
    (args.output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--convergence", type=Path, required=True)
    parser.add_argument("--paper", required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
