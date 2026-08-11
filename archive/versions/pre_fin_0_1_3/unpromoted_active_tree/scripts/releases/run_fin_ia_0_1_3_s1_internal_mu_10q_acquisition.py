from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
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
from sec_agent.official_source_attempt_program import (  # noqa: E402
    OfficialSourceAttemptError,
    UrllibOfficialSourceTransport,
)
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_internal_mu_10q_acquisition import (  # noqa: E402
    RUN_SCOPE,
    execute_internal_mu_10q_acquisition_guarded,
    issue_internal_mu_10q_acquisition_admission,
    load_internal_mu_10q_acquisition_policy,
    validate_internal_mu_10q_acquisition_admission,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
)


DEFAULT_POLICY = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_"
    "mu_10q_acquisition_policy_v1_0.json"
)
DEFAULT_PROOF = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_"
    "mu_10q_acquisition_zero_call_proof_v1_1.json"
)
DEFAULT_ADMISSION = ROOT / (
    ".codex_runtime/fin013_s1_internal_mu_10q_acquisition/admission.json"
)
DEFAULT_RUNTIME = ROOT / (
    "data/workbench_private/fin_0_1_3_s1_internal_mu_10q_acquisition/live-r1"
)
DEFAULT_LEDGER = ROOT / (
    ".codex_runtime/shared/fin013_s1_internal_mu_10q_acquisitions.sqlite3"
)
DEFAULT_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_"
    "mu_10q_acquisition_result_v1_0.json"
)
MODULE_PATH = ROOT / "src/sec_agent/s1_internal_mu_10q_acquisition.py"
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class InternalMu10QAcquisitionRunnerError(RuntimeError):
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


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise InternalMu10QAcquisitionRunnerError(
            "internal_mu_10q_runner_json_object_required"
        )
    return value


def _write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(
            (
                json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n"
            ).encode("utf-8")
        )


def _require_clean_synced() -> str:
    if _git("status", "--porcelain"):
        raise InternalMu10QAcquisitionRunnerError(
            "internal_mu_10q_clean_worktree_required"
        )
    head = _git("rev-parse", "HEAD")
    upstream = _git("rev-parse", "@{u}")
    if head != upstream:
        raise InternalMu10QAcquisitionRunnerError(
            "internal_mu_10q_synced_head_required"
        )
    return head


def _dns_guard() -> dict[str, Any]:
    host = "www.sec.gov"
    synthetic = ipaddress.ip_network("198.18.0.0/15")
    addresses = sorted(
        {
            str(row[4][0])
            for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        }
    )
    if not addresses:
        raise InternalMu10QAcquisitionRunnerError(
            "internal_mu_10q_dns_empty"
        )
    non_global = [
        ipaddress.ip_address(address)
        for address in addresses
        if not ipaddress.ip_address(address).is_global
    ]
    if any(address not in synthetic for address in non_global):
        raise InternalMu10QAcquisitionRunnerError(
            "internal_mu_10q_dns_forbidden_address"
        )
    body = {
        "guard": "public_allowlist_plus_controlled_198_18_0_0_15_proxy_v1",
        "host": host,
        "address_count": len(addresses),
        "synthetic_allowance_required": bool(non_global),
        "all_non_global_addresses_controlled_synthetic": True,
    }
    return {**body, "decision_digest": canonical_digest(body)}


def _proof_valid(proof: Mapping[str, Any], policy: Mapping[str, Any]) -> bool:
    body = dict(proof)
    supplied = str(body.pop("proof_digest", ""))
    implementation = dict(proof.get("implementation") or {})
    return (
        bool(supplied)
        and supplied == canonical_digest(body)
        and proof.get("status")
        == "zero_call_engineering_pass_live_authority_not_yet_issued"
        and proof.get("policy_digest") == canonical_digest(policy)
        and implementation.get("module_sha256") == _normalized_sha256(MODULE_PATH)
        and implementation.get("policy_sha256") == _normalized_sha256(DEFAULT_POLICY)
        and int((proof.get("authorized_live_shape") or {}).get("network_call_ceiling") or 0)
        == 1
    )


def _preflight(*, policy_path: Path, proof_path: Path) -> dict[str, Any]:
    policy = load_internal_mu_10q_acquisition_policy(policy_path, repo_root=ROOT)
    proof = _read_json(proof_path)
    project_os = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    dns = _dns_guard()
    sec_contact_present = bool(
        _EMAIL_RE.fullmatch(
            str(os.environ.get("FINSIGHT_SEC_CONTACT_EMAIL") or "").strip()
        )
    )
    valid = (
        _proof_valid(proof, policy)
        and project_os.get("status") == "pass"
        and sec_contact_present
        and int(policy["budgets"]["network_call_ceiling"]) == 1
        and int(policy["budgets"]["retry_ceiling"]) == 0
    )
    body = {
        "schema_version": (
            "fin_ia_0_1_3_s1_internal_mu_10q_acquisition_preflight_v1_0"
        ),
        "status": "pass" if valid else "failed",
        "run_scope": RUN_SCOPE,
        "project_os_preflight": project_os,
        "dns_guard": dns,
        "sec_contact_present": sec_contact_present,
        "bindings": {
            "runtime_module_sha256": _normalized_sha256(MODULE_PATH),
            "policy_sha256": _normalized_sha256(policy_path),
            "zero_call_proof_sha256": _normalized_sha256(proof_path),
            "policy_digest": canonical_digest(policy),
        },
        "authorized_ceilings": {
            "executions": 1,
            "network": 1,
            "retry": 0,
            "model": 0,
            "provider": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
    }
    return {**body, "preflight_digest": canonical_digest(body)}


def issue(*, policy_path: Path, proof_path: Path, admission_path: Path) -> dict[str, Any]:
    if admission_path.exists():
        raise InternalMu10QAcquisitionRunnerError(
            "internal_mu_10q_admission_already_exists"
        )
    commit = _require_clean_synced()
    preflight = _preflight(policy_path=policy_path, proof_path=proof_path)
    if preflight["status"] != "pass":
        raise InternalMu10QAcquisitionRunnerError(
            "internal_mu_10q_preflight_failed"
        )
    policy = load_internal_mu_10q_acquisition_policy(policy_path, repo_root=ROOT)
    now = _now()
    admission = issue_internal_mu_10q_acquisition_admission(
        policy=policy,
        implementation_commit=commit,
        implementation_file_sha256=_normalized_sha256(MODULE_PATH),
        policy_file_sha256=_normalized_sha256(policy_path),
        issued_at=_iso(now),
        expires_at=_iso(now + timedelta(hours=2)),
        nonce=uuid.uuid4().hex,
    )
    _write_json_exclusive(admission_path, admission)
    return admission


class _DeadlineTransport:
    live_network = True

    def __init__(self, *, deadline: float) -> None:
        self._delegate = UrllibOfficialSourceTransport()
        self._deadline = deadline

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        allowed_hosts: set[str],
        timeout_seconds: int,
        byte_ceiling: int,
    ):
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise OfficialSourceAttemptError(
                "internal_mu_10q_overall_timeout_exceeded"
            )
        return self._delegate.fetch(
            url=url,
            headers=dict(headers),
            allowed_hosts=allowed_hosts,
            timeout_seconds=min(timeout_seconds, max(1, math.ceil(remaining))),
            byte_ceiling=byte_ceiling,
        )


def execute(
    *,
    policy_path: Path,
    proof_path: Path,
    admission_path: Path,
    runtime_root: Path,
    ledger_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    if runtime_root.exists() or output_path.exists():
        raise InternalMu10QAcquisitionRunnerError(
            "internal_mu_10q_exact_once_output_exists"
        )
    commit = _require_clean_synced()
    preflight = _preflight(policy_path=policy_path, proof_path=proof_path)
    if preflight["status"] != "pass":
        raise InternalMu10QAcquisitionRunnerError(
            "internal_mu_10q_preflight_failed"
        )
    policy = load_internal_mu_10q_acquisition_policy(policy_path, repo_root=ROOT)
    admission = _read_json(admission_path)
    if admission.get("implementation_commit") != commit:
        raise InternalMu10QAcquisitionRunnerError(
            "internal_mu_10q_execution_commit_binding_invalid"
        )
    observed_at = _iso(_now())
    validate_internal_mu_10q_acquisition_admission(
        admission,
        policy=policy,
        implementation_path=MODULE_PATH,
        policy_path=policy_path,
        observed_at=observed_at,
    )
    dns = preflight["dns_guard"]
    previous = os.environ.get("FINSIGHT_ALLOW_SYNTHETIC_DNS")
    if dns["synthetic_allowance_required"]:
        os.environ["FINSIGHT_ALLOW_SYNTHETIC_DNS"] = "1"
    else:
        os.environ.pop("FINSIGHT_ALLOW_SYNTHETIC_DNS", None)
    ledger = SharedAdmissionConsumptionLedger(ledger_path)
    try:
        terminal = execute_internal_mu_10q_acquisition_guarded(
            policy=policy,
            admission=admission,
            runtime_root=runtime_root,
            ledger=ledger,
            transport=_DeadlineTransport(deadline=time.monotonic() + 60),
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
            "runtime_root_ref": str(runtime_root.relative_to(ROOT)).replace("\\", "/"),
            "credentials_authorization_headers_or_cookies_saved": False,
            "captured_source_is_business_evidence": False,
        },
    }
    public["public_record_digest"] = canonical_digest(public)
    _write_json_exclusive(output_path, public)
    return public


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--issue", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--proof", type=Path, default=DEFAULT_PROOF)
    parser.add_argument("--admission", type=Path, default=DEFAULT_ADMISSION)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT)
    args = parser.parse_args()
    if args.preflight:
        result = _preflight(policy_path=args.policy, proof_path=args.proof)
    elif args.issue:
        result = issue(
            policy_path=args.policy,
            proof_path=args.proof,
            admission_path=args.admission,
        )
    else:
        result = execute(
            policy_path=args.policy,
            proof_path=args.proof,
            admission_path=args.admission,
            runtime_root=args.runtime_root,
            ledger_path=args.ledger,
            output_path=args.output,
        )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 1 if result.get("status") in {"failed", "terminal_failed"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
