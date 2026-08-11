from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.llm_gateway import chat_completion
from sec_agent.s2_context_yield_canary_runtime import (
    execute_context_yield_canary,
    issue_context_yield_admission,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


PROGRAM = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_context_yield_and_capacity_zero_call_v1_0.json"
)
POLICY = ROOT / "configs" / "runtime" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_context_yield_policy_v1_0.json"
)
S2_DECISION = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_clean_synced() -> str:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    upstream = subprocess.check_output(["git", "rev-parse", "@{upstream}"], cwd=ROOT, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    if status or head != upstream:
        raise RuntimeError("context_canary_execution_head_not_clean_and_synced")
    return head


def _surface() -> tuple[dict, dict]:
    program = _load(PROGRAM)
    policy = _load(POLICY)
    selected_id = policy["natural_reproof"]["selected_request_id"]
    compiled = next(row for row in program["role_scoped_contexts"] if row["request_id"] == selected_id)
    decision = _load(S2_DECISION)
    request = next(
        row
        for row in decision["research_question_method_program"]["representative_requests"]
        if row["request_id"] == selected_id
    )
    if compiled["source_request_digest"] != request["request_digest"]:
        raise RuntimeError("context_canary_surface_digest_drift")
    return request, compiled


def prepare(admission_path: Path) -> dict:
    head = _assert_clean_synced()
    if admission_path.exists():
        raise RuntimeError("context_canary_admission_path_already_exists")
    request, compiled = _surface()
    now = datetime.now(timezone.utc)
    admission = issue_context_yield_admission(
        execution_git_commit=head,
        runner_sha256=_sha(Path(__file__)),
        program_sha256=_sha(PROGRAM),
        policy_sha256=_sha(POLICY),
        request_binding={
            "request_id": request["request_id"],
            "request_digest": request["request_digest"],
            "context_digest": compiled["context_digest"],
        },
        issued_at=now.isoformat().replace("+00:00", "Z"),
        expires_at=(now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        run_nonce=str(uuid.uuid4()),
        credential_present=bool(os.environ.get("DEEPSEEK_API_KEY")),
        provider={
            "backend": "deepseek",
            "model": "deepseek-v4-pro",
            "model_ref": "deepseek:deepseek-v4-pro",
            "base_url": "https://api.deepseek.com/beta",
            "chat_completions_path": "/chat/completions",
            "api_key_env": "DEEPSEEK_API_KEY",
            "wire_api": "chat_completions_json_object",
        },
        budget={
            "maximum_provider_calls": 1,
            "retry_count": 0,
            "fallback_count": 0,
            "maximum_output_tokens": 900,
            "timeout_seconds": 180,
        },
    )
    admission_path.parent.mkdir(parents=True, exist_ok=True)
    with admission_path.open("x", encoding="utf-8") as handle:
        json.dump(admission, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return {
        "status": "issued_unconsumed",
        "admission_ref": str(admission_path),
        "admission_digest": admission["admission_digest"],
        "run_id": admission["run_id"],
        "execution_git_commit": head,
        "request_id": request["request_id"],
        "credential_present": True,
    }


def execute(*, admission_path: Path, runtime_root: Path, shared_ledger_path: Path) -> dict:
    head = _assert_clean_synced()
    request, compiled = _surface()
    result = execute_context_yield_canary(
        admission=_load(admission_path),
        request=request,
        compiled=compiled,
        execution_git_commit=head,
        runner_sha256=_sha(Path(__file__)),
        program_sha256=_sha(PROGRAM),
        policy_sha256=_sha(POLICY),
        runtime_root=runtime_root,
        shared_ledger=SharedAdmissionConsumptionLedger(shared_ledger_path),
        provider_call=chat_completion,
        observed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    return {
        "status": result["status"],
        "terminal_code": result["terminal_code"],
        "terminal_result_digest": result["terminal_result_digest"],
        "completed_calls": result["completed_calls"],
        "request_id": result["request_id"],
        "gateway_status": result["gateway_status"],
        "finish_reason": result["finish_reason"],
        "usage": result["usage"],
        "shared_admission_receipt_state": result["shared_admission_receipt"]["state"],
        "runtime_root": str(runtime_root),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--admission-path", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--shared-ledger", type=Path)
    args = parser.parse_args()
    if args.prepare:
        result = prepare(args.admission_path)
    else:
        if args.runtime_root is None or args.shared_ledger is None:
            parser.error("--execute requires --runtime-root and --shared-ledger")
        os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = "0"
        result = execute(
            admission_path=args.admission_path,
            runtime_root=args.runtime_root,
            shared_ledger_path=args.shared_ledger,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
