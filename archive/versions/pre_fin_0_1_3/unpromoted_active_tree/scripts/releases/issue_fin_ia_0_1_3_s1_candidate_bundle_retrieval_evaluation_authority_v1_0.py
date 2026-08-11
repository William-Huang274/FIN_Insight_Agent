from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_candidate_bundle_retrieval_evaluation import (  # noqa: E402
    IMPLEMENTATION_PROOF_SCHEMA,
    load_candidate_bundle_retrieval_evaluation_policy,
    normalized_sha256,
    validate_candidate_bundle_retrieval_evaluation_authority,
)


POLICY_REF = (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_candidate_bundle_retrieval_evaluation_policy_v1_0.json"
)
PROOF_REF = (
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_retrieval_evaluation_implementation_proof_v1_0.json"
)
OUTPUT_REF = (
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_retrieval_evaluation_authority_v1_0.json"
)
RUNNER_REF = (
    "scripts/releases/"
    "run_fin_ia_0_1_3_s1_candidate_bundle_retrieval_evaluation_r1.py"
)
IMPLEMENTATION_BINDINGS = (
    POLICY_REF,
    PROOF_REF,
    "src/sec_agent/s1_candidate_bundle_retrieval_evaluation.py",
    "tests/contract/test_fin_0_1_3_s1_candidate_bundle_retrieval_evaluation.py",
    RUNNER_REF,
    "scripts/releases/issue_fin_ia_0_1_3_s1_candidate_bundle_retrieval_evaluation_authority_v1_0.py",
    "configs/runtime/fin_ia_project_os_run_scope_registry_v1_0.json",
    "configs/releases/fin_ia_0_1_3_s1_to_s3_retrieval_evidence_research_execution_plan_v1_0.json",
)


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


def _clean_synced_git() -> dict[str, Any]:
    upstream = _git("rev-parse", "--abbrev-ref", "@{upstream}")
    ahead = int(_git("rev-list", "--count", "@{upstream}..HEAD") or 0)
    behind = int(_git("rev-list", "--count", "HEAD..@{upstream}") or 0)
    state = {
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("branch", "--show-current"),
        "upstream": upstream,
        "clean": _git("status", "--porcelain", "--untracked-files=all") == "",
        "ahead": ahead,
        "behind": behind,
        "synced": ahead == 0 and behind == 0,
    }
    if not state["clean"] or not state["synced"]:
        raise RuntimeError("candidate_bundle_retrieval_authority_requires_clean_synced_git")
    return state


def _inspect_wsl(policy: dict[str, Any]) -> dict[str, Any]:
    repo = "/mnt/d/FIN_Insight_Agent"
    completed = subprocess.run(
        [
            "wsl",
            "-d",
            "Ubuntu-22.04",
            "--",
            str(policy["runtime_contract"]["python_executable"]),
            f"{repo}/{RUNNER_REF}",
            "--repo-root",
            repo,
            "--policy",
            f"{repo}/{POLICY_REF}",
            "--inspect-only",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    return json.loads(completed.stdout)


def main() -> int:
    output = ROOT / OUTPUT_REF
    if output.exists():
        raise RuntimeError("candidate_bundle_retrieval_authority_already_exists")
    policy = load_candidate_bundle_retrieval_evaluation_policy(
        ROOT / POLICY_REF, repo_root=ROOT
    )
    proof = json.loads((ROOT / PROOF_REF).read_text(encoding="utf-8"))
    proof_body = {key: value for key, value in proof.items() if key != "proof_digest"}
    if (
        proof.get("schema_version") != IMPLEMENTATION_PROOF_SCHEMA
        or proof.get("status") != "pass_zero_model_full_shape_implementation_proof"
        or proof.get("proof_digest") != canonical_digest(proof_body)
        or (proof.get("stage_acceptance") or {}).get(
            "exact_execution_authority_eligible"
        )
        is not True
    ):
        raise RuntimeError("candidate_bundle_retrieval_implementation_proof_invalid")
    git_state = _clean_synced_git()
    environment = _inspect_wsl(policy)
    if environment.get("qualified") is not True:
        raise RuntimeError("candidate_bundle_retrieval_environment_not_qualified")
    preflight = run_project_os_preflight(ROOT, run_scope=str(policy["run_scope"]))
    if preflight.get("status") != "pass":
        raise RuntimeError("candidate_bundle_retrieval_project_os_preflight_failed")
    body = {
        "schema_version": policy["authority_schema"],
        "decision_id": "FIN-0.1.3-S1-SIX-CASE-RETRIEVAL-EVALUATION-R1-AUTHORITY",
        "recorded_at": policy["recorded_at"],
        "status": "issued_unconsumed",
        "run_scope": policy["run_scope"],
        "attempt_id": policy["attempt_id"],
        "user_authority": (
            "User approved steps 1-5 without stepwise reapproval; this authority is "
            "limited to one local six-case sparse/dense/fusion evaluation with no retry."
        ),
        "policy_digest": canonical_digest(policy),
        "implementation": {
            **git_state,
            "bindings": [
                {"ref": ref, "sha256": normalized_sha256(ROOT / ref)}
                for ref in IMPLEMENTATION_BINDINGS
            ],
            "implementation_proof_digest": proof["proof_digest"],
        },
        "environment_qualification": environment,
        "project_os_preflight": {
            "status": preflight["status"],
            "run_scope": preflight["run_scope"],
            "open_full_chain_blocker_count": preflight[
                "open_full_chain_blocker_count"
            ],
        },
        "execution_ceiling": policy["execution_ceiling"],
        "maximum_executions": 1,
        "automatic_retry": False,
        "known_boundary": policy["known_boundary"],
    }
    authority = {**body, "authority_digest": canonical_digest(body)}
    validate_candidate_bundle_retrieval_evaluation_authority(
        authority,
        policy=policy,
        repo_root=ROOT,
    )
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(
        json.dumps(authority, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
    print(
        json.dumps(
            {
                "status": authority["status"],
                "attempt_id": authority["attempt_id"],
                "implementation_commit": authority["implementation"]["commit"],
                "authority_digest": authority["authority_digest"],
                "output": OUTPUT_REF,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
