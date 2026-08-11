from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from typing import Any, Mapping
import uuid


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.financial_research_asml_exhibit_successor import (  # noqa: E402
    execute_asml_exhibit_successor_guarded,
    issue_asml_exhibit_admission,
    load_asml_exhibit_successor_policy,
    validate_asml_exhibit_admission,
)
from sec_agent.financial_research_held_out_current_source_acquisition import RUN_SCOPE, normalized_sha256  # noqa: E402
from sec_agent.official_source_attempt_program import OfficialSourceAttemptError, UrllibOfficialSourceTransport  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_asml_current_exhibit_successor_policy_v1_0.json"
PROOF_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_asml_current_exhibit_successor_zero_call_proof_v1_0.json"
ADMISSION_PATH = ROOT / ".codex_runtime/fin013_s1_asml_current_exhibit_successor/admission.json"
RUNTIME_ROOT = ROOT / "data/workbench_private/fin_0_1_3_s1_asml_current_exhibit_successor/live-r1"
LEDGER_PATH = ROOT / ".codex_runtime/shared/fin013_s1_asml_current_exhibit_successor.sqlite3"
RESULT_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_asml_current_exhibit_successor_result_v1_0.json"
MODULE_PATH = ROOT / "src/sec_agent/financial_research_asml_exhibit_successor.py"
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class ASMLExhibitRunnerError(RuntimeError):
    pass


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def _require_clean_synced() -> str:
    if _git("status", "--porcelain"):
        raise ASMLExhibitRunnerError("asml_exhibit_clean_worktree_required")
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "@{u}"):
        raise ASMLExhibitRunnerError("asml_exhibit_synced_head_required")
    return head


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ASMLExhibitRunnerError("asml_exhibit_json_object_required")
    return value


def _write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _dns_guard() -> dict[str, Any]:
    synthetic = ipaddress.ip_network("198.18.0.0/15")
    addresses = sorted({str(row[4][0]) for row in socket.getaddrinfo("www.sec.gov", 443, type=socket.SOCK_STREAM)})
    forbidden = [ipaddress.ip_address(value) for value in addresses if not ipaddress.ip_address(value).is_global]
    if any(value not in synthetic for value in forbidden):
        raise ASMLExhibitRunnerError("asml_exhibit_dns_forbidden_address")
    body = {
        "guard": "public_allowlist_plus_controlled_198_18_0_0_15_proxy_v1",
        "host": "www.sec.gov",
        "address_count": len(addresses),
        "synthetic_allowance_required": bool(forbidden),
        "all_forbidden_addresses_controlled_synthetic": True,
    }
    return {**body, "decision_digest": canonical_digest(body)}


def preflight() -> dict[str, Any]:
    policy = load_asml_exhibit_successor_policy(POLICY_PATH, repo_root=ROOT)
    proof = _read_json(PROOF_PATH)
    project_os = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    dns = _dns_guard()
    contact = bool(_EMAIL_RE.fullmatch(str(os.environ.get("FINSIGHT_SEC_CONTACT_EMAIL") or "").strip()))
    valid = (
        proof.get("status") == "zero_call_engineering_pass_live_authority_not_yet_issued"
        and proof.get("policy_digest") == canonical_digest(policy)
        and project_os.get("status") == "pass"
        and contact
    )
    body = {
        "schema_version": "fin_ia_0_1_3_s1_asml_current_exhibit_successor_preflight_v1_0",
        "status": "pass" if valid else "failed",
        "run_scope": RUN_SCOPE,
        "project_os_preflight": project_os,
        "dns_guard": dns,
        "sec_contact_present": contact,
        "bindings": {
            "runtime_module_sha256": normalized_sha256(MODULE_PATH),
            "policy_sha256": normalized_sha256(POLICY_PATH),
            "proof_sha256": normalized_sha256(PROOF_PATH),
            "policy_digest": canonical_digest(policy),
        },
        "authorized_ceilings": {"executions": 1, "network": 3, "candidate_documents": 2, "retry": 0, "model": 0, "provider": 0, "embedding": 0, "rerank": 0, "evidence_promotion": 0},
    }
    return {**body, "preflight_digest": canonical_digest(body)}


def issue() -> dict[str, Any]:
    if ADMISSION_PATH.exists():
        raise ASMLExhibitRunnerError("asml_exhibit_admission_already_exists")
    commit = _require_clean_synced()
    check = preflight()
    if check["status"] != "pass":
        raise ASMLExhibitRunnerError("asml_exhibit_preflight_failed")
    policy = load_asml_exhibit_successor_policy(POLICY_PATH, repo_root=ROOT)
    now = _now()
    admission = issue_asml_exhibit_admission(
        policy=policy,
        implementation_commit=commit,
        implementation_file_sha256=normalized_sha256(MODULE_PATH),
        policy_file_sha256=normalized_sha256(POLICY_PATH),
        issued_at=_iso(now),
        expires_at=_iso(now + timedelta(hours=2)),
        nonce=uuid.uuid4().hex,
    )
    _write_json_exclusive(ADMISSION_PATH, admission)
    return admission


class DeadlineTransport:
    live_network = True

    def __init__(self, deadline: float) -> None:
        self.delegate = UrllibOfficialSourceTransport()
        self.deadline = deadline

    def fetch(self, *, url: str, headers: Mapping[str, str], allowed_hosts: set[str], timeout_seconds: int, byte_ceiling: int):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise OfficialSourceAttemptError("asml_exhibit_overall_timeout_exceeded")
        return self.delegate.fetch(url=url, headers=dict(headers), allowed_hosts=allowed_hosts, timeout_seconds=min(timeout_seconds, max(1, math.ceil(remaining))), byte_ceiling=byte_ceiling)


def execute() -> dict[str, Any]:
    if RUNTIME_ROOT.exists() or RESULT_PATH.exists():
        raise ASMLExhibitRunnerError("asml_exhibit_exact_once_output_exists")
    commit = _require_clean_synced()
    check = preflight()
    if check["status"] != "pass":
        raise ASMLExhibitRunnerError("asml_exhibit_preflight_failed")
    policy = load_asml_exhibit_successor_policy(POLICY_PATH, repo_root=ROOT)
    admission = _read_json(ADMISSION_PATH)
    if admission.get("implementation_commit") != commit:
        raise ASMLExhibitRunnerError("asml_exhibit_execution_commit_binding_invalid")
    observed_at = _iso(_now())
    validate_asml_exhibit_admission(admission, policy=policy, implementation_path=MODULE_PATH, policy_path=POLICY_PATH, observed_at=observed_at)
    previous = os.environ.get("FINSIGHT_ALLOW_SYNTHETIC_DNS")
    dns = check["dns_guard"]
    if dns["synthetic_allowance_required"]:
        os.environ["FINSIGHT_ALLOW_SYNTHETIC_DNS"] = "1"
    else:
        os.environ.pop("FINSIGHT_ALLOW_SYNTHETIC_DNS", None)
    ledger = SharedAdmissionConsumptionLedger(LEDGER_PATH)
    try:
        terminal = execute_asml_exhibit_successor_guarded(
            policy=policy,
            admission=admission,
            repo_root=ROOT,
            runtime_root=RUNTIME_ROOT,
            ledger=ledger,
            transport=DeadlineTransport(time.monotonic() + 120),
            observed_at=observed_at,
        )
    finally:
        if previous is None:
            os.environ.pop("FINSIGHT_ALLOW_SYNTHETIC_DNS", None)
        else:
            os.environ["FINSIGHT_ALLOW_SYNTHETIC_DNS"] = previous
    receipt = ledger.read(str(admission["admission_digest"])).as_dict()
    public = {
        **terminal,
        "shared_admission_receipt": receipt,
        "execution_environment_guard": dns,
        "public_private_separation": {
            "raw_requests_responses_and_parsed_text_retained_outside_git": True,
            "runtime_root_ref": str(RUNTIME_ROOT.relative_to(ROOT)).replace("\\", "/"),
            "credentials_authorization_headers_or_cookies_saved": False,
            "captured_document_is_business_evidence": False,
        },
    }
    public["public_record_digest"] = canonical_digest(public)
    _write_json_exclusive(RESULT_PATH, public)
    return public


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--issue", action="store_true")
    modes.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = preflight() if args.preflight else issue() if args.issue else execute()
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 1 if result.get("status") in {"failed", "terminal_failed"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
