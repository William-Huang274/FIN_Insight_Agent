"""Collect accepted workpapers without changing any original run's outcome."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from sec_agent.agent_runtime.dell_case_artifacts import DellCaseArtifacts


BASE = Path("Z:/FIN_Insight_Agent_qualification/dell_reference_vertical")
ATTEMPTS = BASE / "q1_specialist_paid_shadow/attempts"
SOURCES = (
    (ATTEMPTS / "20260906-dell-q1-agentic-review-repair-a5/specialist-final-state.private.json", "reviewed_seed"),
    (ATTEMPTS / "20260906-dell-full-research-web-a2/specialist-final-state.private.json", "accepted_children_of_failed_parent"),
    (BASE / "20260906-full-research-a2-recovery/Q6_MODEL_COMPUTE_DEMAND.private.json", "read_only_native_child_checkpoint_export"),
    (ATTEMPTS / "20260906-dell-q8-targeted-completion-a2/specialist-final-state.private.json", "targeted_research_handoff"),
)


def collect():
    papers, origins = [], []
    for path, role in SOURCES:
        raw = path.read_bytes()
        envelope = json.loads(raw)
        state = envelope.get("values", envelope)
        if role == "reviewed_seed":
            if state["phase"] != "review_cycle_accepted":
                raise ValueError("reviewed_seed_phase_changed")
            selected = [state["target_state"]]
        elif "task_results" in state:
            selected = [row["agent_state"] for row in state["task_results"] if row["status"] == "submitted"]
        else:
            selected = [state]
        for paper in selected:
            papers.append(paper)
            origins.append({"paper_id": f"P{len(papers):02d}", "path": str(path),
                "file_sha256": sha256(raw).hexdigest(), "source_role": role,
                "source_phase": state["phase"], "source_run_outcome_rewritten": False})
    artifacts = DellCaseArtifacts(papers)
    coverage = {paper["task"]["branch_id"] for paper in papers}
    foundation = json.loads(Path("configs/research/fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json").read_text(encoding="utf-8"))
    expected = {row["branch_id"] for row in foundation["question_branches"]}
    if coverage != expected:
        raise ValueError(f"research_bundle_missing_or_extra_branch:{expected ^ coverage}")
    return {"schema_version": "dell_research_bundle_v1", "papers": papers, "origins": origins,
            "catalog": artifacts.catalog(), "financial_or_product_pass": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = collect()
    args.output.mkdir(parents=True, exist_ok=False)
    for filename, value in (("research-bundle.private.json", result), ("catalog.json", result["catalog"])):
        with (args.output / filename).open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"papers": len(result["papers"]), "branches": len({p["task"]["branch_id"] for p in result["papers"]}),
        "output": str(args.output), "financial_or_product_pass": False}))


if __name__ == "__main__":
    main()
