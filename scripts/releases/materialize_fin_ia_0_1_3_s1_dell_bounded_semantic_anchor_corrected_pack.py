from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_dell_bounded_semantic_anchor_replay import (  # noqa: E402
    execute_dell_bounded_semantic_anchor_replay,
    load_dell_bounded_semantic_anchor_replay_policy,
    validate_dell_bounded_semantic_anchor_clean_proof,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_dell_bounded_semantic_anchor_replay_policy_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_dell_bounded_semantic_anchor_replay_clean_proof_v1_0.json"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_dell_bounded_semantic_anchor_replay_result_v1_0.json"
)
DEFAULT_RUNTIME = ROOT / (
    "data/workbench_private/fin_0_1_3_s1_dell_bounded_semantic_anchor_replay/"
    "corrected_pack"
)


class DellBoundedSemanticAnchorMaterializerError(RuntimeError):
    pass


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _require_clean_synced() -> str:
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise DellBoundedSemanticAnchorMaterializerError(
            "bounded_semantic_anchor_materializer_requires_clean_worktree"
        )
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "@{upstream}"):
        raise DellBoundedSemanticAnchorMaterializerError(
            "bounded_semantic_anchor_materializer_requires_synced_head"
        )
    return head


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME)
    args = parser.parse_args()
    if args.output.exists() or args.runtime_root.exists():
        raise DellBoundedSemanticAnchorMaterializerError(
            "bounded_semantic_anchor_materializer_output_already_exists"
        )
    head = _require_clean_synced()
    policy = load_dell_bounded_semantic_anchor_replay_policy(
        POLICY_PATH, repo_root=ROOT
    )
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    validate_dell_bounded_semantic_anchor_clean_proof(proof)
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", proof["implementation_commit"], head],
        cwd=ROOT,
        check=False,
    )
    if ancestor.returncode != 0:
        raise DellBoundedSemanticAnchorMaterializerError(
            "bounded_semantic_anchor_proof_implementation_not_ancestor"
        )
    result = execute_dell_bounded_semantic_anchor_replay(
        policy=policy,
        repo_root=ROOT,
        runtime_root=args.runtime_root,
        observed_at="2026-08-10T21:00:00Z",
        execution_commit=head,
        clean_proof_digest=str(proof["proof_digest"]),
    )
    if (
        result["corrected_pack_payload_digest"]
        != proof["corrected_pack_payload_digest"]
    ):
        raise DellBoundedSemanticAnchorMaterializerError(
            "bounded_semantic_anchor_corrected_pack_digest_drift"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["gate_status"]["core_research_ready"] is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
