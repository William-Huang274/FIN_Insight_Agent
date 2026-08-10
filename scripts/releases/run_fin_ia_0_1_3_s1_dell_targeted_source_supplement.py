from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.official_source_attempt_program import (  # noqa: E402
    UrllibOfficialSourceTransport,
)
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_dell_targeted_source_supplement import (  # noqa: E402
    RUN_SCOPE,
    execute_dell_targeted_source_supplement,
    load_dell_targeted_source_policy,
    validate_dell_targeted_source_authority,
    validate_dell_targeted_source_clean_proof,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_dell_targeted_source_supplement_policy_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_dell_targeted_source_supplement_clean_proof_v1_0.json"
)
AUTHORITY_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_dell_targeted_source_supplement_authority_v1_0.json"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_dell_targeted_source_supplement_result_v1_0.json"
)
PRIVATE_ROOT = ROOT / (
    "data/workbench_private/fin_0_1_3_s1_dell_targeted_source_supplement/live"
)
LEDGER_PATH = PRIVATE_ROOT / "shared/admission_consumption.sqlite3"


class DellTargetedSourceRunnerError(RuntimeError):
    pass


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def _validate_repository() -> str:
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise DellTargetedSourceRunnerError(
            "dell_targeted_source_runner_requires_clean_worktree"
        )
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "@{upstream}"):
        raise DellTargetedSourceRunnerError(
            "dell_targeted_source_runner_requires_synced_branch"
        )
    return head


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DellTargetedSourceRunnerError(
            "dell_targeted_source_runner_json_invalid"
        )
    return value


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def preflight() -> dict[str, Any]:
    head = _validate_repository()
    policy = load_dell_targeted_source_policy(POLICY_PATH, repo_root=ROOT)
    proof = _load_json(PROOF_PATH)
    validate_dell_targeted_source_clean_proof(proof)
    authority = _load_json(AUTHORITY_PATH)
    observed_at = _now()
    validate_dell_targeted_source_authority(
        authority,
        policy=policy,
        repo_root=ROOT,
        observed_at=observed_at,
    )
    if authority.get("clean_proof_digest") != proof.get("proof_digest"):
        raise DellTargetedSourceRunnerError(
            "dell_targeted_source_runner_proof_binding_invalid"
        )
    source_commit = str(authority.get("implementation_commit") or "")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, head],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if ancestor.returncode != 0:
        raise DellTargetedSourceRunnerError(
            "dell_targeted_source_runner_implementation_not_ancestor"
        )
    project_os = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if project_os.get("status") != "pass":
        raise DellTargetedSourceRunnerError(
            "dell_targeted_source_runner_project_os_blocked:"
            + json.dumps(project_os.get("errors") or [], ensure_ascii=False)
        )
    runtime = PRIVATE_ROOT / "attempts" / str(authority["run_id"])
    if runtime.exists():
        raise DellTargetedSourceRunnerError(
            "dell_targeted_source_runner_attempt_root_already_exists"
        )
    return {
        "head": head,
        "policy": policy,
        "proof": proof,
        "authority": authority,
        "observed_at": observed_at,
        "runtime_root": runtime,
        "project_os": project_os,
    }


def execute(*, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise DellTargetedSourceRunnerError(
            "dell_targeted_source_runner_output_already_exists"
        )
    state = preflight()
    previous = os.environ.get("FINSIGHT_ALLOW_SYNTHETIC_DNS")
    try:
        os.environ["FINSIGHT_ALLOW_SYNTHETIC_DNS"] = "1"
        result = execute_dell_targeted_source_supplement(
            policy=state["policy"],
            repo_root=ROOT,
            runtime_root=state["runtime_root"],
            transport=UrllibOfficialSourceTransport(),
            observed_at=state["observed_at"],
            execution_commit=state["head"],
            authority=state["authority"],
            shared_admission_ledger=SharedAdmissionConsumptionLedger(
                LEDGER_PATH
            ),
        )
    finally:
        if previous is None:
            os.environ.pop("FINSIGHT_ALLOW_SYNTHETIC_DNS", None)
        else:
            os.environ["FINSIGHT_ALLOW_SYNTHETIC_DNS"] = previous
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.preflight:
        state = preflight()
        print(
            json.dumps(
                {
                    "status": "preflight_pass",
                    "run_scope": RUN_SCOPE,
                    "run_id": state["authority"]["run_id"],
                    "source_network_call_ceiling": state["policy"]["budget"][
                        "source_network_calls"
                    ],
                    "model_calls": 0,
                    "retries": 0,
                    "business_artifact_promotion": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    result = execute(output_path=args.output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "observed_counts": result["observed_counts"],
                "stage_acceptance": result["stage_acceptance"],
                "route_results": [
                    {
                        "route_id": row["route_id"],
                        "status": row["status"],
                        "failure_code": row["failure_code"],
                        "fragments_materialized": row[
                            "fragments_materialized"
                        ],
                    }
                    for row in result["route_results"]
                ],
                "result_digest": result["result_digest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return (
        0
        if result["status"]
        == "terminal_succeeded_targeted_source_successor_pack_ready"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
