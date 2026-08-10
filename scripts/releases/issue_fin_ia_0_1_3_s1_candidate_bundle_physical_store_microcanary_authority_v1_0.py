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
    canonical_digest,
    normalized_sha256,
)

from run_fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_r1 import (  # noqa: E402
    POLICY_REF,
    load_policy,
    validate_authority,
)


OUTPUT_REF = (
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_authority_v1_0.json"
)
BINDING_REFS = (
    POLICY_REF,
    "configs/runtime/fin_ia_project_os_run_scope_registry_v1_0.json",
    "src/sec_agent/s1_candidate_bundle_physical_index.py",
    "scripts/releases/run_fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_r1.py",
    "scripts/releases/issue_fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_authority_v1_0.py",
    "tests/contract/test_fin_0_1_3_s1_candidate_bundle_physical_index.py",
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
    result = {
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("branch", "--show-current"),
        "upstream": upstream,
        "clean": status == "",
        "synced": ahead == 0 and behind == 0,
        "ahead": ahead,
        "behind": behind,
    }
    if not result["clean"] or not result["synced"]:
        raise RuntimeError("physical_store_microcanary_authority_requires_clean_synced_git")
    return result


def _inspect_wsl(policy: dict[str, Any]) -> dict[str, Any]:
    runtime = dict(policy["runtime"])
    repo = str(runtime["repository_root"])
    runner = (
        f"{repo}/scripts/releases/"
        "run_fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_r1.py"
    )
    policy_ref = f"{repo}/{POLICY_REF}"
    completed = subprocess.run(
        [
            "wsl",
            "-d",
            str(runtime["distribution"]),
            "--",
            str(runtime["python_executable"]),
            runner,
            "--repo-root",
            repo,
            "--policy",
            policy_ref,
            "--inspect-only",
        ],
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
        raise RuntimeError("physical_store_microcanary_authority_already_exists")
    policy = load_policy(ROOT / POLICY_REF)
    git_state = _clean_synced_git()
    environment = _inspect_wsl(policy)
    preflight = run_project_os_preflight(ROOT, run_scope=str(policy["run_scope"]))
    if preflight.get("status") != "pass":
        raise RuntimeError("physical_store_microcanary_project_os_preflight_failed")
    body = {
        "schema_version": "fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_authority_v1_0",
        "decision_id": "FIN-0.1.3-S1-PHYSICAL-STORE-DIRECTORY-MICROCANARY-R1-AUTHORITY",
        "recorded_at": policy["recorded_at"],
        "status": "issued_unconsumed",
        "run_scope": policy["run_scope"],
        "attempt_id": policy["attempt_id"],
        "user_authority": "User approved steps 1-5; this sub-authority is limited to one synthetic local directory-store publication microcanary.",
        "policy_digest": canonical_digest(policy),
        "implementation": {
            **git_state,
            "bindings": [
                {"ref": ref, "sha256": normalized_sha256(ROOT / ref)}
                for ref in BINDING_REFS
            ],
        },
        "environment": environment,
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
    validate_authority(
        authority,
        policy=policy,
        repo_root=ROOT,
        requalify_environment=False,
    )
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(authority, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
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
