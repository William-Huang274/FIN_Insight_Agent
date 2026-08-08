from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Mapping
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.official_source_attempt_program import (  # noqa: E402
    UrllibOfficialSourceTransport,
)
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_08_external_combined_live import (  # noqa: E402
    EXACT_LIVE_SCOPE,
    compile_external_combined_plan,
    execute_external_combined,
    issue_external_combined_admission,
    load_bound_inputs,
    load_external_combined_policy,
    sha256_file,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


DEFAULT_POLICY = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_external_combined_live_policy_v1_0.json"
DEFAULT_PLAN = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_external_combined_plan_v1_0.json"
DEFAULT_PROOF = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_external_combined_live_zero_call_proof_v1_0.json"
DEFAULT_AUTHORITY = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_external_combined_live_authority_v1_0.json"
DEFAULT_ADMISSION = ROOT / ".codex_runtime/fin013_s1_08/external_combined/admission.json"
DEFAULT_RUNTIME = ROOT / ".codex_runtime/fin013_s1_08/external_combined/live-r1"
DEFAULT_LEDGER = ROOT / ".codex_runtime/shared_admission_consumption_ledger.json"
DEFAULT_RESULT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_external_combined_live_result_v1_0.json"
MODULE_PATH = ROOT / "src/sec_agent/s1_08_external_combined_live.py"
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class ExternalCombinedRunnerError(RuntimeError):
    pass


class _OverallDeadlineTransport:
    live_network = True

    def __init__(self, *, delegate, deadline: float) -> None:
        if delegate.live_network is not True:
            raise ExternalCombinedRunnerError(
                "external_combined_live_official_transport_required"
            )
        self._delegate = delegate
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
            raise ExternalCombinedRunnerError(
                "external_combined_overall_timeout_exceeded"
            )
        return self._delegate.fetch(
            url=url,
            headers=dict(headers),
            allowed_hosts=allowed_hosts,
            timeout_seconds=min(timeout_seconds, max(1, math.ceil(remaining))),
            byte_ceiling=byte_ceiling,
        )


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


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(
            (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )


def _require_clean_synced() -> str:
    if _git("status", "--porcelain"):
        raise ExternalCombinedRunnerError("external_combined_clean_worktree_required")
    head = _git("rev-parse", "HEAD")
    upstream = _git("rev-parse", "@{u}")
    if head != upstream:
        raise ExternalCombinedRunnerError("external_combined_synced_head_required")
    return head


def _validate_authority(
    *,
    authority: Mapping[str, Any],
    execution_commit: str,
    policy_path: Path,
    plan_path: Path,
    proof_path: Path,
) -> None:
    body = dict(authority)
    supplied = body.pop("authority_digest", None)
    bindings = authority.get("immutable_bindings") or {}
    approval = authority.get("exact_live_authority") or {}
    valid = (
        authority.get("schema_version")
        == "fin_ia_0_1_3_s1_08_external_combined_live_authority_v1_0"
        and authority.get("status") == "approved_one_external_combined_exact_live"
        and supplied == canonical_digest(body)
        and bindings.get("execution_git_commit") == execution_commit
        and bindings.get("runner_sha256") == sha256_file(Path(__file__).resolve())
        and bindings.get("runtime_module_sha256") == sha256_file(MODULE_PATH)
        and bindings.get("policy_sha256") == sha256_file(policy_path)
        and bindings.get("plan_sha256") == sha256_file(plan_path)
        and bindings.get("zero_call_proof_sha256") == sha256_file(proof_path)
        and approval.get("scope") == EXACT_LIVE_SCOPE
        and approval.get("maximum_admissions") == 1
        and approval.get("maximum_executions") == 1
        and approval.get("network_call_ceiling") == 72
        and approval.get("retry_ceiling") == 0
        and approval.get("model_call_ceiling") == 0
        and approval.get("automatic_replacement") is False
    )
    if not valid:
        raise ExternalCombinedRunnerError("external_combined_authority_binding_invalid")


def _preflight(
    *, policy_path: Path, plan_path: Path, proof_path: Path, exact_scope: bool
) -> dict[str, Any]:
    policy = load_external_combined_policy(policy_path)
    inputs = load_bound_inputs(repo_root=ROOT, policy=policy)
    compiled = compile_external_combined_plan(policy=policy, bound_inputs=inputs)
    stored = _load_json(plan_path)
    proof = _load_json(proof_path)
    scope = EXACT_LIVE_SCOPE if exact_scope else str(policy["zero_call_run_scope"])
    project_os = run_project_os_preflight(ROOT, run_scope=scope)
    sec_contact_present = bool(
        _EMAIL_RE.fullmatch(str(os.environ.get("FINSIGHT_SEC_CONTACT_EMAIL") or "").strip())
    )
    body = {
        "schema_version": "fin_ia_0_1_3_s1_08_external_combined_preflight_v1_0",
        "scope": scope,
        "status": "pass",
        "bindings": {
            "compiled_plan_digest": compiled["plan_digest"],
            "stored_plan_digest": stored.get("plan_digest"),
            "proof_plan_digest": proof.get("plan_digest"),
            "runner_sha256": sha256_file(Path(__file__).resolve()),
            "runtime_module_sha256": sha256_file(MODULE_PATH),
            "policy_sha256": sha256_file(policy_path),
            "plan_sha256": sha256_file(plan_path),
            "zero_call_proof_sha256": sha256_file(proof_path),
        },
        "project_os_preflight": project_os,
        "sec_contact_present": sec_contact_present,
        "observed_calls": {
            "provider": 0,
            "network": 0,
            "model": 0,
            "document_fetch": 0,
            "evidence_promotion": 0,
        },
    }
    if (
        stored != compiled
        or proof.get("status") != "zero_call_engineering_pass_authority_not_yet_issued"
        or proof.get("plan_digest") != compiled["plan_digest"]
        or project_os.get("status") != "pass"
        or (exact_scope and not sec_contact_present)
    ):
        body["status"] = "failed"
    return {**body, "preflight_digest": canonical_digest(body)}


def issue(
    *,
    policy_path: Path,
    plan_path: Path,
    proof_path: Path,
    authority_path: Path,
    admission_path: Path,
) -> dict[str, Any]:
    if admission_path.exists():
        raise ExternalCombinedRunnerError("external_combined_admission_already_exists")
    commit = _require_clean_synced()
    preflight = _preflight(
        policy_path=policy_path,
        plan_path=plan_path,
        proof_path=proof_path,
        exact_scope=True,
    )
    if preflight["status"] != "pass":
        raise ExternalCombinedRunnerError("external_combined_preflight_failed")
    policy = load_external_combined_policy(policy_path)
    plan = _load_json(plan_path)
    authority = _load_json(authority_path)
    _validate_authority(
        authority=authority,
        execution_commit=commit,
        policy_path=policy_path,
        plan_path=plan_path,
        proof_path=proof_path,
    )
    now = _now()
    admission = issue_external_combined_admission(
        policy=policy,
        plan=plan,
        authority=authority,
        execution_git_commit=commit,
        runner_sha256=sha256_file(Path(__file__).resolve()),
        runtime_module_sha256=sha256_file(MODULE_PATH),
        policy_sha256=sha256_file(policy_path),
        zero_call_proof_sha256=sha256_file(proof_path),
        issued_at=_iso(now),
        expires_at=_iso(now + timedelta(hours=2)),
        run_nonce=uuid.uuid4().hex,
    )
    _write_json(admission_path, admission)
    return admission


def _firecrawl_call(endpoint: str, request_bytes: bytes, timeout: int) -> tuple[int, bytes]:
    request = Request(
        endpoint,
        data=request_bytes,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "FIN-Insight-Agent/0.1.3 combined-shadow",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return int(response.status), response.read()
    except HTTPError as exc:
        return int(exc.code or 0), exc.read()


def execute(
    *,
    policy_path: Path,
    plan_path: Path,
    proof_path: Path,
    authority_path: Path,
    admission_path: Path,
    runtime_root: Path,
    ledger_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    if output_path.exists() or runtime_root.exists():
        raise ExternalCombinedRunnerError("external_combined_exact_once_output_exists")
    commit = _require_clean_synced()
    preflight = _preflight(
        policy_path=policy_path,
        plan_path=plan_path,
        proof_path=proof_path,
        exact_scope=True,
    )
    if preflight["status"] != "pass":
        raise ExternalCombinedRunnerError("external_combined_preflight_failed")
    policy = load_external_combined_policy(policy_path)
    inputs = load_bound_inputs(repo_root=ROOT, policy=policy)
    plan = _load_json(plan_path)
    authority = _load_json(authority_path)
    admission = _load_json(admission_path)
    _validate_authority(
        authority=authority,
        execution_commit=commit,
        policy_path=policy_path,
        plan_path=plan_path,
        proof_path=proof_path,
    )
    if (
        admission.get("authority_digest") != authority.get("authority_digest")
        or admission.get("zero_call_proof_sha256") != sha256_file(proof_path)
        or admission.get("plan_digest") != plan.get("plan_digest")
    ):
        raise ExternalCombinedRunnerError(
            "external_combined_admission_current_authority_binding_invalid"
        )
    deadline = time.monotonic() + int(
        policy["combined_budget"]["overall_timeout_seconds"]
    )
    official_transport = _OverallDeadlineTransport(
        delegate=UrllibOfficialSourceTransport(), deadline=deadline
    )

    def bounded_firecrawl_call(
        endpoint: str, request_bytes: bytes, timeout: int
    ) -> tuple[int, bytes]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ExternalCombinedRunnerError(
                "external_combined_overall_timeout_exceeded"
            )
        return _firecrawl_call(
            endpoint,
            request_bytes,
            min(timeout, max(1, math.ceil(remaining))),
        )

    terminal = execute_external_combined(
        admission=admission,
        policy=policy,
        plan=plan,
        catalog=inputs["source_catalog"],
        execution_git_commit=commit,
        runner_sha256=sha256_file(Path(__file__).resolve()),
        runtime_module_sha256=sha256_file(MODULE_PATH),
        policy_sha256=sha256_file(policy_path),
        runtime_root=runtime_root,
        shared_ledger=SharedAdmissionConsumptionLedger(ledger_path),
        official_transport=official_transport,
        firecrawl_call=bounded_firecrawl_call,
        observed_at=_iso(_now()),
    )
    public = {
        **terminal,
        "public_private_separation": {
            "raw_requests_responses_and_parser_captures_retained_outside_git": True,
            "runtime_root_ref": str(runtime_root.relative_to(ROOT)).replace("\\", "/"),
            "credentials_authorization_headers_or_cookies_saved": False,
            "firecrawl_raw_results_are_business_evidence": False,
        },
    }
    public["public_record_digest"] = canonical_digest(public)
    _write_json(output_path, public)
    return public


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--issue", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--proof", type=Path, default=DEFAULT_PROOF)
    parser.add_argument("--authority", type=Path, default=DEFAULT_AUTHORITY)
    parser.add_argument("--admission", type=Path, default=DEFAULT_ADMISSION)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT)
    args = parser.parse_args()
    if args.preflight:
        result = _preflight(
            policy_path=args.policy,
            plan_path=args.plan,
            proof_path=args.proof,
            exact_scope=False,
        )
    elif args.issue:
        result = issue(
            policy_path=args.policy,
            plan_path=args.plan,
            proof_path=args.proof,
            authority_path=args.authority,
            admission_path=args.admission,
        )
    else:
        result = execute(
            policy_path=args.policy,
            plan_path=args.plan,
            proof_path=args.proof,
            authority_path=args.authority,
            admission_path=args.admission,
            runtime_root=args.runtime_root,
            ledger_path=args.ledger,
            output_path=args.output,
        )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result.get("status") != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
