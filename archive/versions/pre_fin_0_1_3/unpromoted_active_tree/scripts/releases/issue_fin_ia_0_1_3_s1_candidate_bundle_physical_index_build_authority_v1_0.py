from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_candidate_bundle_physical_index import (  # noqa: E402
    AUTHORITY_SCHEMA,
    canonical_digest,
    load_bound_private_manifest,
    load_physical_index_policy,
    normalized_sha256,
    validate_build_authority,
)


POLICY_REF = (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_build_policy_v1_0.json"
)
OUTPUT_REF = (
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_build_authority_v1_0.json"
)
IMPLEMENTATION_BINDINGS = (
    POLICY_REF,
    "configs/runtime/fin_ia_project_os_run_scope_registry_v1_0.json",
    "configs/releases/fin_ia_0_1_3_s1_candidate_bundle_physical_index_implementation_proof_v1_0.json",
    "configs/releases/fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_r4_zero_call_proof_v1_0.json",
    "configs/releases/fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_r4_clean_independent_proof_v1_0.json",
    "src/sec_agent/s1_candidate_bundle_physical_index.py",
    "scripts/releases/run_fin_ia_0_1_3_s1_candidate_bundle_physical_index_r1.py",
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
    status = _git("status", "--porcelain", "--untracked-files=all")
    upstream = _git("rev-parse", "--abbrev-ref", "@{upstream}")
    ahead = int(_git("rev-list", "--count", "@{upstream}..HEAD") or 0)
    behind = int(_git("rev-list", "--count", "HEAD..@{upstream}") or 0)
    state = {
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("branch", "--show-current"),
        "upstream": upstream,
        "clean": status == "",
        "ahead": ahead,
        "behind": behind,
        "synced": ahead == 0 and behind == 0,
    }
    if not state["clean"] or not state["synced"]:
        raise RuntimeError("candidate_bundle_physical_authority_requires_clean_synced_git")
    return state


def _inspect_wsl(policy: dict[str, Any]) -> dict[str, Any]:
    runtime = dict(policy["runtime_contract"])
    repo = str(runtime["repository_root"])
    worker = f"{repo}/scripts/releases/run_fin_ia_0_1_3_s1_candidate_bundle_physical_index_r1.py"
    policy_ref = f"{repo}/{POLICY_REF}"
    command = [
        "wsl",
        "-d",
        str(runtime["distribution"]),
        "--",
        "env",
        *[f"{key}={value}" for key, value in runtime["offline_environment"].items()],
        str(runtime["python_executable"]),
        worker,
        "--repo-root",
        repo,
        "--policy",
        policy_ref,
        "--inspect-only",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )
    return json.loads(completed.stdout)


def main() -> int:
    output = ROOT / OUTPUT_REF
    if output.exists():
        raise RuntimeError("candidate_bundle_physical_authority_already_exists")
    policy = load_physical_index_policy(ROOT / POLICY_REF, repo_root=ROOT)
    implementation_proof_ref = ROOT / IMPLEMENTATION_BINDINGS[2]
    implementation_proof = json.loads(implementation_proof_ref.read_text(encoding="utf-8"))
    if (
        implementation_proof.get("schema_version")
        != policy["implementation_proof_schema"]
        or implementation_proof.get("status")
        != "terminal_succeeded_full_fake_physical_index_implementation"
        or implementation_proof.get("stage_acceptance", {}).get(
            "clean_commit_authority_issuance"
        )
        is not True
    ):
        raise RuntimeError("candidate_bundle_physical_implementation_proof_invalid")
    git_state = _clean_synced_git()
    _manifest, specs = load_bound_private_manifest(policy, repo_root=ROOT)
    environment = _inspect_wsl(policy)
    preflight = run_project_os_preflight(ROOT, run_scope=str(policy["run_scope"]))
    if preflight.get("status") != "pass":
        raise RuntimeError("candidate_bundle_physical_project_os_preflight_failed")
    target = dict(environment["target"])
    body = {
        "schema_version": AUTHORITY_SCHEMA,
        "decision_id": "FIN-0.1.3-S1-CANDIDATE-BUNDLE-PHYSICAL-INDEX-R1-AUTHORITY",
        "recorded_at": policy["recorded_at"],
        "status": "issued_unconsumed",
        "run_scope": policy["run_scope"],
        "attempt_id": policy["attempt_id"],
        "user_authority": "User approved the frozen sequence through real index build; authority remains exact-once and bounded by this artifact.",
        "policy_digest": canonical_digest(policy),
        "implementation": {
            **git_state,
            "bindings": [
                {"ref": ref, "sha256": normalized_sha256(ROOT / ref)}
                for ref in IMPLEMENTATION_BINDINGS
            ],
            "implementation_proof_digest": implementation_proof["proof_digest"],
        },
        "manifest_binding": {
            "spec_count": len(specs),
            "spec_digest": policy["immutable_inputs"]["manifest_spec_digest"],
            "private_manifest_file_sha256": policy["immutable_inputs"][
                "private_manifest_file_sha256"
            ],
            "candidate_state": "candidate_only_not_evidence",
        },
        "environment_qualification": {
            "qualified": True,
            **environment,
        },
        "project_os_preflight": {
            "status": preflight["status"],
            "run_scope": preflight["run_scope"],
            "open_full_chain_blocker_count": preflight[
                "open_full_chain_blocker_count"
            ],
        },
        "private_target": {
            "working_root": target["working_root"],
            "working_root_absent": target["working_root_absent"],
            "final_root": target["final_root"],
            "final_root_absent": target["final_root_absent"],
            "disk_free_bytes": target["disk_free_bytes"],
        },
        "execution_ceiling": policy["execution_ceiling"],
        "maximum_executions": 1,
        "automatic_retry": False,
        "preserved_boundaries": policy["stage_boundaries"],
        "known_boundary": (
            "This authority permits one local CPU BGE-M3 load plus one fresh ObjectBM25/Milvus "
            "build from 93 CandidateBundle specs. It permits no network, model API, vector search, "
            "rerank, Evidence promotion, external supplement, Workbench acceptance or release."
        ),
    }
    authority = {**body, "authority_digest": canonical_digest(body)}
    validate_build_authority(authority, policy=policy, repo_root=ROOT)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(authority, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(output)
    print(
        json.dumps(
            {
                "status": authority["status"],
                "attempt_id": authority["attempt_id"],
                "implementation_commit": authority["implementation"]["commit"],
                "environment": {
                    "python": environment["python"],
                    "packages": environment["packages"],
                    "pip_freeze_sha256": environment["pip_freeze_sha256"],
                    "disk_free_bytes": target["disk_free_bytes"],
                },
                "authority_digest": authority["authority_digest"],
                "output": output.as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
