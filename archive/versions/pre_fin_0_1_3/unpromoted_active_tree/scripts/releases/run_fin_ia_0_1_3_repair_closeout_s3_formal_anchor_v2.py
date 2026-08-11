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
from sec_agent.s3_evidence_role_contract import compile_s3_evidence_selection_context  # noqa: E402
from sec_agent.s3_formal_anchor_runtime import execute_formal_anchor, issue_formal_anchor_admission  # noqa: E402
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


S2_DECISION = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json"
S2_CONTEXT_PROGRAM = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s2_03_context_yield_and_capacity_zero_call_v1_0.json"
QUALITY_GATE = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_05_research_quality_gate_v1_0.json"
POLICY = ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_execution_policy_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _assert_clean_synced() -> str:
    head = _git_head()
    upstream = subprocess.check_output(["git", "rev-parse", "@{upstream}"], cwd=ROOT, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    if status or head != upstream:
        raise RuntimeError("s3_formal_anchor_v2_head_not_clean_and_synced")
    return head


def _surface() -> tuple[dict[str, dict], dict[str, dict], list[dict[str, str]], dict]:
    decision = _load(S2_DECISION)
    old_program = _load(S2_CONTEXT_PROGRAM)
    policy = _load(POLICY)
    request_map = {row["request_id"]: row for row in decision["research_question_method_program"]["representative_requests"]}
    old_context_map = {row["request_id"]: row for row in old_program["role_scoped_contexts"]}
    order = policy["request_order"]
    if order != list(request_map) or set(old_context_map) != set(request_map):
        raise RuntimeError("s3_formal_anchor_v2_surface_order_or_coverage_drift")
    requests = {request_id: request_map[request_id] for request_id in order}
    contexts = {
        request_id: compile_s3_evidence_selection_context(s2_context=old_context_map[request_id])
        for request_id in order
    }
    bindings = [
        {
            "request_id": request_id,
            "request_digest": requests[request_id]["request_digest"],
            "context_digest": contexts[request_id]["context_digest"],
        }
        for request_id in order
    ]
    return requests, contexts, bindings, policy


def prepare(admission_path: Path) -> dict:
    head = _assert_clean_synced()
    if admission_path.exists():
        raise RuntimeError("s3_formal_anchor_v2_admission_path_already_exists")
    _, contexts, bindings, policy = _surface()
    now = datetime.now(timezone.utc)
    admission = issue_formal_anchor_admission(
        execution_git_commit=head,
        runner_sha256=_sha(Path(__file__)),
        s2_decision_sha256=_sha(S2_DECISION),
        context_program_sha256=_sha(S2_CONTEXT_PROGRAM),
        quality_gate_sha256=_sha(QUALITY_GATE),
        policy_sha256=_sha(POLICY),
        request_bindings=bindings,
        issued_at=now.isoformat().replace("+00:00", "Z"),
        expires_at=(now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        run_nonce=str(uuid.uuid4()),
        credential_present=bool(os.environ.get("DEEPSEEK_API_KEY")),
        provider=policy["provider"],
        budget=policy["budget"],
        contract_version="v2",
    )
    admission_path.parent.mkdir(parents=True, exist_ok=True)
    with admission_path.open("x", encoding="utf-8") as handle:
        json.dump(admission, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    model_contexts = [row["model_context"] for row in contexts.values()]
    sizes = [len(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))) for row in model_contexts]
    return {
        "status": "issued_unconsumed",
        "admission_ref": str(admission_path),
        "admission_digest": admission["admission_digest"],
        "run_id": admission["run_id"],
        "execution_git_commit": head,
        "request_count": len(bindings),
        "aggregate_model_context_characters": sum(sizes),
        "maximum_single_request_model_context_characters": max(sizes),
        "credential_present": True,
    }


def execute(*, admission_path: Path, runtime_root: Path, shared_ledger_path: Path) -> dict:
    head = _assert_clean_synced()
    requests, contexts, _, _ = _surface()
    result = execute_formal_anchor(
        admission=_load(admission_path),
        requests=requests,
        contexts=contexts,
        execution_git_commit=head,
        runner_sha256=_sha(Path(__file__)),
        s2_decision_sha256=_sha(S2_DECISION),
        context_program_sha256=_sha(S2_CONTEXT_PROGRAM),
        quality_gate_sha256=_sha(QUALITY_GATE),
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
        "record_digest": result["record_digest"],
        "completed_calls": result["completed_calls"],
        "skipped_request_ids": result["skipped_request_ids"],
        "usage": {
            field: sum(row["usage"][field] for row in result["family_results"])
            for field in ("input_tokens", "output_tokens", "total_tokens")
        },
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
