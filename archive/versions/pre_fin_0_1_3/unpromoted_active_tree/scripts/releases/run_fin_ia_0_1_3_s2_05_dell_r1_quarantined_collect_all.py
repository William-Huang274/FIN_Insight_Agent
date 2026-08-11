from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.llm_gateway import chat_completion  # noqa: E402
from sec_agent.s2_same_evidence_collect_all_diagnostic import (  # noqa: E402
    execute_quarantined_collect_all,
    issue_diagnostic_admission,
)
from sec_agent.s2_same_evidence_experiment_runtime import (  # noqa: E402
    POLICY_REF,
    load_frozen_blind_inputs,
    load_runtime_policy,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


RUNTIME_REF = "src/sec_agent/s2_same_evidence_collect_all_diagnostic.py"
SOURCE_CAPTURE = ROOT / ".codex_runtime/fin013_s2_05/runs/fin013_s2_05_exp_a_dell_9af8699f8f545103d2be/raw_model_only/captures/01_lead_planning_710ad12542688379acd3767e39c012d34b78e2401f01ddee73c3db7fb9abbe5a.json"
ORIGINAL_ADMISSION_DIGEST = "de2ae5a5f9a4847784245457c00ab4ee7a46ab538a7d0d54b858e68c10bfe1d0"
ORIGINAL_CAPTURE_DIGEST = "710ad12542688379acd3767e39c012d34b78e2401f01ddee73c3db7fb9abbe5a"
AUTHORITY_ROOT = ROOT / ".codex_runtime/fin013_s2_05/authorities/DELL_DIAGNOSTIC"


def main() -> int:
    parser = argparse.ArgumentParser(description="Quarantined DELL R1 downstream collect-all diagnostic")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--issue", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--observed-at")
    args = parser.parse_args()

    policy = load_runtime_policy(ROOT)
    blind = load_frozen_blind_inputs(ROOT, policy)
    case = next(row for row in blind["cases"] if row["case_key"] == "DELL")
    bindings = _bindings()
    _validate_source_capture()

    if args.preflight_only:
        print(json.dumps({
            "status": "quarantined_collect_all_zero_call_ready",
            "case_key": "DELL",
            "reused_lead_calls": 1,
            "maximum_new_provider_calls": 9,
            "business_promotable": False,
            "formal_raw_candidate": False,
            "bindings": bindings,
        }, indent=2, sort_keys=True))
        return 0

    if args.issue:
        _require_clean_synced()
        if not os.environ.get(str(policy["provider"]["api_key_env"]), "").strip():
            raise RuntimeError("collect_all_credential_missing")
        AUTHORITY_ROOT.mkdir(parents=True, exist_ok=True)
        if list(AUTHORITY_ROOT.glob("*.json")):
            raise RuntimeError("collect_all_admission_already_exists")
        issued = datetime.now(timezone.utc).replace(microsecond=0)
        admission = issue_diagnostic_admission(
            execution_git_commit=bindings["git_commit"],
            runtime_sha256=bindings["runtime_sha256"],
            policy_sha256=bindings["policy_sha256"],
            original_admission_digest=ORIGINAL_ADMISSION_DIGEST,
            original_lead_capture_sha256=bindings["original_lead_capture_sha256"],
            original_lead_capture_digest=ORIGINAL_CAPTURE_DIGEST,
            issued_at=issued.isoformat().replace("+00:00", "Z"),
            expires_at=(issued + timedelta(hours=4)).isoformat().replace("+00:00", "Z"),
            nonce=secrets.token_hex(32),
        )
        path = AUTHORITY_ROOT / f"{admission['run_id']}.json"
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(admission, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        print(json.dumps({
            "status": "issued_unconsumed_quarantined",
            "admission_ref": path.relative_to(ROOT).as_posix(),
            "admission_digest": admission["admission_digest"],
            "run_id": admission["run_id"],
            "provider_calls": 0,
            "network_calls": 0,
        }, indent=2, sort_keys=True))
        return 0

    missing = [name for name, value in (
        ("--admission", args.admission), ("--runtime-root", args.runtime_root),
        ("--ledger", args.ledger), ("--observed-at", args.observed_at),
    ) if value is None]
    if missing:
        parser.error("--execute requires " + ", ".join(missing))
    admission = _read_json(args.admission.resolve())
    result = execute_quarantined_collect_all(
        admission=admission,
        original_lead_capture=SOURCE_CAPTURE,
        case_input=case,
        policy=policy,
        execution_git_commit=bindings["git_commit"],
        runtime_sha256=bindings["runtime_sha256"],
        policy_sha256=bindings["policy_sha256"],
        runtime_root=args.runtime_root,
        shared_ledger=SharedAdmissionConsumptionLedger(args.ledger),
        provider_call=chat_completion,
        observed_at=args.observed_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _bindings() -> dict[str, str]:
    return {
        "git_commit": _git("rev-parse", "HEAD"),
        "runtime_sha256": _sha(ROOT / RUNTIME_REF),
        "policy_sha256": _sha(ROOT / POLICY_REF),
        "original_lead_capture_sha256": _sha(SOURCE_CAPTURE),
    }


def _validate_source_capture() -> None:
    capture = _read_json(SOURCE_CAPTURE)
    body = dict(capture)
    if (
        capture.get("case_key") != "DELL"
        or capture.get("node_type") != "lead_planning"
        or capture.get("call_index") != 1
        or _canonical(body) != ORIGINAL_CAPTURE_DIGEST
    ):
        raise RuntimeError("collect_all_original_lead_capture_invalid")


def _require_clean_synced() -> None:
    if _git("status", "--porcelain"):
        raise RuntimeError("collect_all_repository_not_clean")
    upstream = _git("rev-parse", "--abbrev-ref", "@{upstream}")
    if _git("rev-list", "--left-right", "--count", f"{upstream}...HEAD").split() != ["0", "0"]:
        raise RuntimeError("collect_all_repository_not_synced")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("collect_all_json_object_required")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> str:
    from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
    return canonical_digest(value)


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


if __name__ == "__main__":
    raise SystemExit(main())
