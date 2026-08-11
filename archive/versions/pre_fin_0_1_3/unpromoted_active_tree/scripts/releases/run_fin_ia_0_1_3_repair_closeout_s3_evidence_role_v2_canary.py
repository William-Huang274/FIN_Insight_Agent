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

from sec_agent.llm_gateway import chat_completion  # noqa: E402
from sec_agent.s3_evidence_role_canary_runtime import execute_evidence_role_canary, issue_evidence_role_canary_admission  # noqa: E402
from sec_agent.s3_evidence_role_contract import compile_s3_evidence_selection_context  # noqa: E402
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


S2_DECISION = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json"
S2_CONTEXT = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s2_03_context_yield_and_capacity_zero_call_v1_0.json"
POLICY = ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_policy_v1_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _head() -> str:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    upstream = subprocess.check_output(["git", "rev-parse", "@{upstream}"], cwd=ROOT, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    if status or head != upstream:
        raise RuntimeError("s3_evidence_canary_head_not_clean_and_synced")
    return head


def _surface() -> tuple[dict, dict, dict]:
    policy = _load(POLICY)
    request_id = policy["selected_request_id"]
    request = next(row for row in _load(S2_DECISION)["research_question_method_program"]["representative_requests"] if row["request_id"] == request_id)
    old = next(row for row in _load(S2_CONTEXT)["role_scoped_contexts"] if row["request_id"] == request_id)
    compiled = compile_s3_evidence_selection_context(s2_context=old)
    return request, compiled, policy


def prepare(path: Path) -> dict:
    head = _head()
    if path.exists():
        raise RuntimeError("s3_evidence_canary_admission_exists")
    request, compiled, policy = _surface()
    now = datetime.now(timezone.utc)
    admission = issue_evidence_role_canary_admission(
        execution_git_commit=head,
        runner_sha256=_sha(Path(__file__)),
        context_source_sha256=_sha(S2_CONTEXT),
        policy_sha256=_sha(POLICY),
        request_binding={"request_id": request["request_id"], "request_digest": request["request_digest"], "context_digest": compiled["context_digest"]},
        issued_at=now.isoformat().replace("+00:00", "Z"),
        expires_at=(now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        run_nonce=str(uuid.uuid4()),
        credential_present=bool(os.environ.get("DEEPSEEK_API_KEY")),
        provider=policy["provider"],
        budget=policy["budget"],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(admission, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return {"status": "issued_unconsumed", "admission_digest": admission["admission_digest"], "run_id": admission["run_id"], "request_id": request["request_id"], "execution_git_commit": head, "credential_present": True}


def execute(path: Path, runtime_root: Path, ledger_path: Path) -> dict:
    head = _head()
    request, compiled, _ = _surface()
    result = execute_evidence_role_canary(
        admission=_load(path), request=request, compiled=compiled,
        execution_git_commit=head, runner_sha256=_sha(Path(__file__)), context_source_sha256=_sha(S2_CONTEXT), policy_sha256=_sha(POLICY),
        runtime_root=runtime_root, shared_ledger=SharedAdmissionConsumptionLedger(ledger_path), provider_call=chat_completion,
        observed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    return {key: result[key] for key in ("status", "terminal_code", "terminal_result_digest", "request_id", "gateway_status", "finish_reason", "usage", "completed_calls")}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true")
    group.add_argument("--execute", action="store_true")
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
        result = execute(args.admission_path, args.runtime_root, args.shared_ledger)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
