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
from sec_agent.s2_natural_canary_runtime import (
    execute_natural_canary,
    issue_canary_admission,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


DECISION = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_02_"
    "representative_node_context_precedence_and_canary_entry_v1_0.json"
)
POLICY = ROOT / "configs" / "runtime" / (
    "fin_ia_0_1_3_repair_closeout_s2_"
    "representative_node_and_natural_canary_policy_v1_0.json"
)
S2_01_DECISION = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_01_"
    "research_question_method_contract_translation_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _assert_clean_synced() -> str:
    head = _git_head()
    upstream = subprocess.check_output(
        ["git", "rev-parse", "@{upstream}"], cwd=ROOT, text=True
    ).strip()
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    ).strip()
    if status or head != upstream:
        raise RuntimeError("canary_execution_head_not_clean_and_synced")
    return head


def _requests() -> tuple[dict[str, dict], list[dict[str, str]]]:
    decision = _load(DECISION)
    policy = _load(POLICY)
    s2 = _load(S2_01_DECISION)
    all_requests = {
        row["request_id"]: row
        for row in s2["research_question_method_program"]["representative_requests"]
    }
    selected_ids = decision["natural_canary_entry"]["selected_request_ids"]
    policy_ids = [
        row["request_id"] for row in policy["natural_canary"]["selected_requests"]
    ]
    if selected_ids != policy_ids:
        raise RuntimeError("canary_selected_request_policy_drift")
    selected = {request_id: all_requests[request_id] for request_id in selected_ids}
    bindings = [
        {
            "request_id": request_id,
            "request_digest": selected[request_id]["request_digest"],
        }
        for request_id in selected_ids
    ]
    return selected, bindings


def prepare(admission_path: Path) -> dict:
    head = _assert_clean_synced()
    if admission_path.exists():
        raise RuntimeError("canary_admission_path_already_exists")
    _, bindings = _requests()
    now = datetime.now(timezone.utc)
    admission = issue_canary_admission(
        execution_git_commit=head,
        runner_sha256=_sha(Path(__file__)),
        decision_sha256=_sha(DECISION),
        policy_sha256=_sha(POLICY),
        request_bindings=bindings,
        issued_at=now.isoformat().replace("+00:00", "Z"),
        expires_at=(now + timedelta(minutes=30)).isoformat().replace(
            "+00:00", "Z"
        ),
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
            "maximum_provider_calls": 3,
            "maximum_calls_per_family": 1,
            "retry_count": 0,
            "fallback_count": 0,
            "maximum_output_tokens_per_call": 900,
            "timeout_seconds_per_call": 180,
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
        "request_count": len(bindings),
        "credential_present": True,
    }


def execute(
    *, admission_path: Path, runtime_root: Path, shared_ledger_path: Path
) -> dict:
    head = _assert_clean_synced()
    admission = _load(admission_path)
    requests, _ = _requests()
    result = execute_natural_canary(
        admission=admission,
        requests=requests,
        execution_git_commit=head,
        runner_sha256=_sha(Path(__file__)),
        decision_sha256=_sha(DECISION),
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
        "skipped_request_ids": result["skipped_request_ids"],
        "family_results": [
            {
                "request_id": row["request_id"],
                "status": row["status"],
                "gateway_status": row["gateway_status"],
                "finish_reason": row["finish_reason"],
                "usage": row["usage"],
                "rubric": row.get("rubric"),
                "failure_code": row.get("failure_code"),
            }
            for row in result["family_results"]
        ],
        "shared_admission_receipt_state": result["shared_admission_receipt"][
            "state"
        ],
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
