from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.llm_gateway import chat_completion  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_six_case_local_evidence_pack import file_sha256  # noqa: E402
from sec_agent.s2_dell_changed_input_model_comparison import (  # noqa: E402
    RUN_SCOPE,
    build_changed_input_public_result,
    compile_changed_input_case,
    load_changed_input_comparison_contract,
    validate_changed_input_clean_proof,
    validate_changed_input_model_authority,
)
from sec_agent.s2_fixed_pack_research_runtime import execute_case  # noqa: E402
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


CONTRACT_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_contract_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_clean_proof_v1_0.json"
)
AUTHORITY_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_authority_v1_0.json"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_result_v1_0.json"
)
PRIVATE_ROOT = ROOT / (
    "data/workbench_private/"
    "fin_0_1_3_s2_dell_changed_input_model_comparison/live"
)
LEDGER_PATH = PRIVATE_ROOT / "shared/admission_consumption.sqlite"


class ChangedInputLiveRunnerError(RuntimeError):
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


def _validate_repository() -> str:
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise ChangedInputLiveRunnerError(
            "changed_input_live_requires_clean_worktree"
        )
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "@{upstream}"):
        raise ChangedInputLiveRunnerError(
            "changed_input_live_requires_synced_head"
        )
    return head


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ChangedInputLiveRunnerError("changed_input_live_json_invalid")
    return value


def _provider(profile: Mapping[str, Any]):
    def call(request: Mapping[str, Any]) -> dict[str, Any]:
        return chat_completion(
            llm_backend=str(profile["provider"]),
            base_url=str(profile["base_url"]),
            chat_completions_path=str(profile["chat_completions_path"]),
            model=str(profile["model"]),
            messages=list(request["messages"]),
            response_format=dict(request["response_format"]),
            api_key_env=str(profile["api_key_env"]),
            temperature=float(request["temperature"]),
            max_tokens=int(request["max_tokens"]),
            timeout_s=int(profile["timeout_seconds_per_call"]),
            stream=bool(request["stream"]),
            enable_thinking=bool(request["enable_thinking"]),
            role=str(request["node_type"]),
            profile=str(profile["profile_ref"]),
            trace_tags={
                "case_key": request["case_key"],
                "node_key": request["node_key"],
                "case_input_digest": request["case_input_digest"],
                "comparison_type": "changed_input_information_increment",
            },
            max_transport_attempts=int(profile["max_transport_attempts"]),
        )

    return call


def preflight() -> dict[str, Any]:
    head = _validate_repository()
    contract = load_changed_input_comparison_contract(
        CONTRACT_PATH, repo_root=ROOT
    )
    proof = _load_json(PROOF_PATH)
    validate_changed_input_clean_proof(proof)
    authority = _load_json(AUTHORITY_PATH)
    material = compile_changed_input_case(contract=contract, repo_root=ROOT)
    profile = material["profile"]
    env_name = str(profile["api_key_env"])
    if not os.environ.get(env_name, "").strip():
        raise ChangedInputLiveRunnerError("changed_input_live_credential_missing")
    implementation_commit = str(authority.get("implementation_commit") or "")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation_commit, head],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if ancestor.returncode != 0:
        raise ChangedInputLiveRunnerError(
            "changed_input_live_implementation_not_ancestor"
        )
    now = datetime.now(timezone.utc).replace(microsecond=0)
    observed_at = now.isoformat().replace("+00:00", "Z")
    validate_changed_input_model_authority(
        authority,
        clean_proof=proof,
        case_input=material["case_input"],
        profile=profile,
        repo_root=ROOT,
        observed_at=observed_at,
    )
    project_os = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if project_os.get("status") != "pass":
        raise ChangedInputLiveRunnerError(
            "changed_input_live_project_os_blocked:"
            + json.dumps(project_os.get("errors") or [], ensure_ascii=False)
        )
    admission = authority["admission"]
    runtime_root = PRIVATE_ROOT / "attempts" / str(admission["run_id"])
    if runtime_root.exists():
        raise ChangedInputLiveRunnerError(
            "changed_input_live_attempt_root_already_exists"
        )
    return {
        "head": head,
        "contract": contract,
        "proof": proof,
        "authority": authority,
        "material": material,
        "observed_at": observed_at,
        "project_os": project_os,
        "runtime_root": runtime_root,
        "credential_present": True,
        "credential_value_read_or_persisted": False,
    }


def execute(*, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise ChangedInputLiveRunnerError("changed_input_live_result_already_exists")
    state = preflight()
    authority = state["authority"]
    admission = authority["admission"]
    material = state["material"]
    profile = material["profile"]
    terminal = execute_case(
        admission=admission,
        case_input=material["case_input"],
        profile=profile,
        execution_git_commit=str(authority["implementation_commit"]),
        runner_sha256=str(admission["runner_sha256"]),
        contract_sha256=str(admission["contract_sha256"]),
        profile_sha256=str(admission["profile_sha256"]),
        runtime_root=state["runtime_root"],
        shared_ledger=SharedAdmissionConsumptionLedger(LEDGER_PATH),
        provider_call=_provider(profile),
        observed_at=state["observed_at"],
    )
    private_terminal = state["runtime_root"] / "terminal_with_receipt.json"
    result = build_changed_input_public_result(
        authority=authority,
        terminal=terminal,
        private_terminal_path=private_terminal,
        comparison_contract=state["contract"],
        recorded_at=state["observed_at"],
    )
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
        authority = state["authority"]
        print(
            json.dumps(
                {
                    "status": "preflight_pass",
                    "run_scope": RUN_SCOPE,
                    "run_id": authority["admission"]["run_id"],
                    "provider": state["material"]["profile"]["model"],
                    "provider_call_ceiling": 13,
                    "source_call_ceiling": 0,
                    "retry_count": 0,
                    "old_model_nodes_reused": 0,
                    "credential_present": True,
                    "credential_value_read_or_persisted": False,
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
                "terminal_phase": result["terminal_phase"],
                "terminal_code": result["terminal_code"],
                "observed_counts": result["observed_counts"],
                "finding_summary": result["finding_summary"],
                "usage": result["usage"],
                "result_digest": result["result_digest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"] in {"completed", "completed_with_findings"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
