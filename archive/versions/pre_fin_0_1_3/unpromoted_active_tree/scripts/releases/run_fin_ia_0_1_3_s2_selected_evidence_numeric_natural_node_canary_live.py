from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s2_selected_evidence_numeric_natural_node_canary import (  # noqa: E402
    compile_canary_material,
    load_canary_policy,
)
from sec_agent.s2_selected_evidence_numeric_natural_node_canary_live import (  # noqa: E402
    LIVE_SCOPE,
    build_no_retry_provider_call,
    credential_presence_only,
    execute_live_canary,
    validate_live_canary_issuance,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "policy_v1_0.json"
)
DECISION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "live_value_cost_risk_authority_decision_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "clean_independent_proof_v1_0.json"
)
ISSUANCE_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "live_admission_issuance_v1_1.json"
)
PRIVATE_ROOT = ROOT / (
    "data/workbench_private/"
    "fin_0_1_3_s2_selected_evidence_numeric_natural_node_canary/live"
)
LEDGER_PATH = PRIVATE_ROOT / "shared/admission_consumption.sqlite"


class LiveCanaryRunnerError(RuntimeError):
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


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LiveCanaryRunnerError("live_canary_runner_json_invalid")
    return value


def _validate_repository() -> str:
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise LiveCanaryRunnerError("live_canary_runner_requires_clean_worktree")
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "@{upstream}"):
        raise LiveCanaryRunnerError("live_canary_runner_requires_synced_head")
    return head


def preflight() -> dict[str, Any]:
    head = _validate_repository()
    policy = load_canary_policy(POLICY_PATH, repo_root=ROOT)
    material = compile_canary_material(policy=policy, repo_root=ROOT)
    decision = _load(DECISION_PATH)
    proof = _load(PROOF_PATH)
    issuance = _load(ISSUANCE_PATH)
    implementation_commit = str(
        dict(issuance.get("authority") or {}).get("implementation_commit") or ""
    )
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation_commit, head],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if ancestor.returncode != 0:
        raise LiveCanaryRunnerError("live_canary_implementation_not_ancestor")
    project_os = run_project_os_preflight(ROOT, run_scope=LIVE_SCOPE)
    if project_os.get("status") != "pass":
        raise LiveCanaryRunnerError(
            "live_canary_runner_project_os_blocked:"
            + json.dumps(project_os.get("errors") or [], ensure_ascii=False)
        )
    credential = credential_presence_only(profile=material["profile"])
    if credential["credential_present"] is not True:
        raise LiveCanaryRunnerError("live_canary_runner_credential_missing")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    observed_at = now.isoformat().replace("+00:00", "Z")
    validate_live_canary_issuance(
        issuance,
        decision=decision,
        clean_proof=proof,
        material=material,
        project_os_preflight=project_os,
        repo_root=ROOT,
        observed_at=observed_at,
    )
    admission = dict(issuance["admission"])
    runtime_root = PRIVATE_ROOT / "attempts" / str(admission["run_id"])
    if runtime_root.exists():
        raise LiveCanaryRunnerError("live_canary_attempt_root_already_exists")
    return {
        "head": head,
        "material": material,
        "decision": decision,
        "proof": proof,
        "issuance": issuance,
        "project_os": project_os,
        "runtime_root": runtime_root,
        "credential": credential,
        "observed_at": observed_at,
    }


def execute(*, execution_authority_path: Path) -> dict[str, Any]:
    if not execution_authority_path.is_file():
        raise LiveCanaryRunnerError(
            "live_canary_separate_execution_authority_missing"
        )
    state = preflight()
    execution_authority = _load(execution_authority_path)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    observed_at = now.isoformat().replace("+00:00", "Z")
    return execute_live_canary(
        issuance=state["issuance"],
        execution_authority=execution_authority,
        decision=state["decision"],
        clean_proof=state["proof"],
        material=state["material"],
        project_os_preflight=state["project_os"],
        repo_root=ROOT,
        provider_call=build_no_retry_provider_call(
            profile=state["material"]["profile"]
        ),
        runtime_root=state["runtime_root"],
        shared_ledger=SharedAdmissionConsumptionLedger(LEDGER_PATH),
        observed_at=observed_at,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--execution-authority", type=Path)
    args = parser.parse_args()
    if args.preflight:
        state = preflight()
        issuance = state["issuance"]
        print(
            json.dumps(
                {
                    "status": "preflight_pass_execution_not_authorized",
                    "run_scope": LIVE_SCOPE,
                    "run_id": issuance["admission"]["run_id"],
                    "admission_consumed": False,
                    "provider_call_ceiling": 1,
                    "model_call_ceiling": 1,
                    "source_call_ceiling": 0,
                    "retry_count": 0,
                    "credential_present": True,
                    "credential_value_read_output_or_persisted": False,
                    "separate_execution_authority_present": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.execution_authority is None:
        raise LiveCanaryRunnerError(
            "live_canary_separate_execution_authority_required"
        )
    terminal = execute(execution_authority_path=args.execution_authority)
    print(
        json.dumps(
            {
                "status": terminal["status"],
                "terminal_phase": terminal["terminal_phase"],
                "terminal_code": terminal["terminal_code"],
                "observed_counts": terminal["observed_counts"],
                "result_digest": terminal["result_digest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if terminal["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
