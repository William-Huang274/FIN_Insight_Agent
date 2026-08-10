from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.metadata
import ipaddress
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from typing import Any, Mapping
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.official_source_attempt_program import (  # noqa: E402
    UrllibOfficialSourceTransport,
)
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_residual_gap_external_live import (  # noqa: E402
    AUTHORITY_SCHEMA,
    execute_residual_gap_external_live,
    validate_residual_gap_external_live_authority,
)
from sec_agent.s1_residual_gap_external_supplement import (  # noqa: E402
    CONTRACT_REF,
    RUN_SCOPE,
    canonical_digest,
    file_sha256,
    load_residual_gap_external_supplement_policy,
    validate_residual_gap_external_priority_plan,
)
from sec_agent.s1_residual_gap_tencent_locator import (  # noqa: E402
    TencentSearchProLocatorProvider,
    load_residual_gap_tencent_locator_profile,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
)


DEFAULT_POLICY = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_residual_gap_external_supplement_policy_v1_0.json"
)
DEFAULT_PLAN = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_residual_gap_external_priority_plan_v1_0.json"
)
DEFAULT_PROVIDER_PROFILE = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_residual_gap_tencent_locator_profile_v1_0.json"
)
DEFAULT_AUTHORITY = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_residual_gap_external_live_authority_v1_0.json"
)
DEFAULT_RUNTIME = ROOT / (
    ".codex_runtime/fin013_s1_residual_gap_external_live/r1"
)
DEFAULT_LEDGER = ROOT / (
    ".codex_runtime/shared/fin013_s1_residual_gap_external_admissions.sqlite3"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_residual_gap_external_live_result_v1_0.json"
)
DEFAULT_SDK = ROOT / ".codex_runtime/tencent-wsa-sdk"


class ResidualGapExternalLiveRunnerError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise ResidualGapExternalLiveRunnerError(
            "residual_external_live_git_preflight_failed"
        )
    return completed.stdout.strip()


def _require_clean_synced() -> str:
    if _git("status", "--porcelain"):
        raise ResidualGapExternalLiveRunnerError(
            "residual_external_live_clean_worktree_required"
        )
    head = _git("rev-parse", "HEAD")
    upstream = _git("rev-parse", "@{upstream}")
    if head != upstream:
        raise ResidualGapExternalLiveRunnerError(
            "residual_external_live_synced_head_required"
        )
    return head


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ResidualGapExternalLiveRunnerError(
            "residual_external_live_output_already_exists"
        )
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        with path.open("xb") as destination:
            destination.write(temporary.read_bytes())
            destination.flush()
            os.fsync(destination.fileno())
    finally:
        temporary.unlink(missing_ok=True)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _binding_paths(
    *, policy_path: Path, plan_path: Path, provider_profile_path: Path
) -> tuple[Path, ...]:
    return (
        Path(__file__).resolve(),
        ROOT / "src/sec_agent/s1_residual_gap_external_live.py",
        ROOT / "src/sec_agent/s1_residual_gap_external_supplement.py",
        ROOT / "src/sec_agent/s1_residual_gap_tencent_locator.py",
        ROOT / "src/sec_agent/official_source_attempt_program.py",
        ROOT / "src/sec_agent/s1_08_official_content_tools.py",
        ROOT / "src/sec_agent/s1_08_tencent_wsa_candidate_diagnostic.py",
        policy_path.resolve(),
        plan_path.resolve(),
        provider_profile_path.resolve(),
    )


def preflight(
    *, policy_path: Path, plan_path: Path, provider_profile_path: Path
) -> dict[str, Any]:
    commit = _require_clean_synced()
    policy = load_residual_gap_external_supplement_policy(
        policy_path,
        repo_root=ROOT,
    )
    plan = _load_json(plan_path)
    validate_residual_gap_external_priority_plan(plan, policy=policy)
    profile = load_residual_gap_tencent_locator_profile(provider_profile_path)
    project_os = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if project_os.get("status") != "pass":
        raise ResidualGapExternalLiveRunnerError(
            "residual_external_live_project_os_preflight_failed"
        )
    bindings = {
        _relative(path): file_sha256(path)
        for path in _binding_paths(
            policy_path=policy_path,
            plan_path=plan_path,
            provider_profile_path=provider_profile_path,
        )
    }
    body = {
        "schema_version": "fin_ia_0_1_3_s1_residual_gap_external_live_preflight_v1_0",
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "status": "zero_call_preflight_pass",
        "implementation_commit": commit,
        "priority_plan_digest": plan["plan_digest"],
        "provider_profile_digest": canonical_digest(profile),
        "file_bindings": bindings,
        "project_os": {
            "status": project_os["status"],
            "open_full_chain_blocker_count": project_os[
                "open_full_chain_blocker_count"
            ],
        },
        "observed_counts": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "embedding": 0,
            "rerank": 0,
            "credential_reads": 0,
            "admissions": 0,
        },
        "credential_presence_checked": False,
        "authority_issued": False,
    }
    return {**body, "preflight_digest": canonical_digest(body)}


def issue(
    *,
    policy_path: Path,
    plan_path: Path,
    provider_profile_path: Path,
    authority_path: Path,
) -> dict[str, Any]:
    if authority_path.exists():
        raise ResidualGapExternalLiveRunnerError(
            "residual_external_live_authority_already_exists"
        )
    proof = preflight(
        policy_path=policy_path,
        plan_path=plan_path,
        provider_profile_path=provider_profile_path,
    )
    policy = load_residual_gap_external_supplement_policy(
        policy_path,
        repo_root=ROOT,
    )
    plan = _load_json(plan_path)
    issued = _now()
    seed = canonical_digest(
        {
            "implementation_commit": proof["implementation_commit"],
            "priority_plan_digest": plan["plan_digest"],
            "issued_at": _iso(issued),
            "nonce": uuid4().hex,
        }
    )
    body = {
        "schema_version": AUTHORITY_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "status": "issued_unconsumed",
        "issued_at": _iso(issued),
        "expires_at": _iso(issued + timedelta(hours=24)),
        "implementation_commit": proof["implementation_commit"],
        "admission_id": f"fin013-s1-residual-external-admission-{seed[:20]}",
        "run_id": f"fin013-s1-residual-external-run-{seed[20:40]}",
        "attempt_id": f"fin013-s1-residual-external-attempt-{seed[40:60]}",
        "maximum_executions": 1,
        "automatic_retry": False,
        "evidence_promotion_allowed": False,
        "model_calls_allowed": 0,
        "priority_plan_digest": plan["plan_digest"],
        "local_evidence_pack_result_digest": plan[
            "local_evidence_pack_result_digest"
        ],
        "budget": deepcopy(policy["budget"]),
        "file_bindings": proof["file_bindings"],
        "preflight_digest": proof["preflight_digest"],
        "provider_profile_digest": proof["provider_profile_digest"],
        "stop_rules": [
            "no automatic retry or replacement admission",
            "systemic provider rejection stops later provider calls but preserves official work",
            "provider snippets and dates never become Evidence authority",
            "all captured documents require later local readjudication",
        ],
    }
    authority = {**body, "authority_digest": canonical_digest(body)}
    _write_json_exclusive(authority_path, authority)
    return authority


def execute(
    *,
    policy_path: Path,
    plan_path: Path,
    provider_profile_path: Path,
    authority_path: Path,
    runtime_root: Path,
    ledger_path: Path,
    output_path: Path,
    sdk_path: Path,
) -> dict[str, Any]:
    commit = _require_clean_synced()
    if runtime_root.exists() or output_path.exists():
        raise ResidualGapExternalLiveRunnerError(
            "residual_external_live_exact_once_target_exists"
        )
    policy = load_residual_gap_external_supplement_policy(
        policy_path,
        repo_root=ROOT,
    )
    plan = _load_json(plan_path)
    profile = load_residual_gap_tencent_locator_profile(provider_profile_path)
    authority = _load_json(authority_path)
    observed_at = _iso(_now())
    validate_residual_gap_external_live_authority(
        authority,
        policy=policy,
        plan=plan,
        repo_root=ROOT,
        observed_at=observed_at,
    )
    try:
        _git(
            "merge-base",
            "--is-ancestor",
            str(authority["implementation_commit"]),
            commit,
        )
    except ResidualGapExternalLiveRunnerError as exc:
        raise ResidualGapExternalLiveRunnerError(
            "residual_external_live_implementation_commit_not_ancestor"
        ) from exc
    project_os = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if project_os.get("status") != "pass":
        raise ResidualGapExternalLiveRunnerError(
            "residual_external_live_project_os_preflight_failed"
        )
    auth = profile["authentication"]
    secret_id = str(os.environ.get(str(auth["secret_id_env"])) or "").strip()
    secret_key = str(os.environ.get(str(auth["secret_key_env"])) or "").strip()
    if not secret_id or not secret_key:
        raise ResidualGapExternalLiveRunnerError(
            "residual_external_live_tencent_credentials_missing"
        )
    credential, ClientProfile, HttpProfile, models, wsa_client, sdk_version = _load_sdk(
        sdk_path
    )
    http_profile = HttpProfile()
    http_profile.endpoint = profile["api_contract"]["endpoint"]
    http_profile.protocol = "https"
    http_profile.reqMethod = "POST"
    http_profile.reqTimeout = int(profile["budget"]["timeout_seconds_per_call"])
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client_profile.signMethod = "TC3-HMAC-SHA256"
    client_profile.retryer = None
    provider_client = wsa_client.WsaClient(
        credential.Credential(secret_id, secret_key),
        str(profile["api_contract"]["region"]),
        client_profile,
    )
    locator_provider = TencentSearchProLocatorProvider(
        profile=profile,
        runtime_root=runtime_root,
        models=models,
        client=provider_client,
        secrets=(secret_id, secret_key),
    )
    dns_guard = _synthetic_dns_decision(policy)
    prior_synthetic = os.environ.get("FINSIGHT_ALLOW_SYNTHETIC_DNS")
    if dns_guard["synthetic_allowance_required"]:
        os.environ["FINSIGHT_ALLOW_SYNTHETIC_DNS"] = "1"
    else:
        os.environ.pop("FINSIGHT_ALLOW_SYNTHETIC_DNS", None)
    try:
        terminal = execute_residual_gap_external_live(
            policy=policy,
            plan=plan,
            authority=authority,
            repo_root=ROOT,
            runtime_root=runtime_root,
            observed_at=observed_at,
            execution_commit=commit,
            official_transport=UrllibOfficialSourceTransport(),
            locator_provider=locator_provider,
            shared_admission_ledger=SharedAdmissionConsumptionLedger(ledger_path),
        )
    finally:
        if prior_synthetic is None:
            os.environ.pop("FINSIGHT_ALLOW_SYNTHETIC_DNS", None)
        else:
            os.environ["FINSIGHT_ALLOW_SYNTHETIC_DNS"] = prior_synthetic
    body = deepcopy(terminal)
    body.pop("result_digest", None)
    body.update(
        {
            "execution_environment_guard": dns_guard,
            "provider_sdk": {
                "package": "tencentcloud-sdk-python",
                "version": sdk_version,
            },
            "public_private_separation": {
                "raw_source_and_provider_captures_retained_outside_git": True,
                "runtime_root_ref": runtime_root.relative_to(ROOT).as_posix(),
                "credential_values_persisted": False,
                "provider_snippets_or_dates_promoted": False,
            },
        }
    )
    local_terminal = {**body, "result_digest": canonical_digest(body)}
    terminal_path = runtime_root / "terminal-result.json"
    _write_json_exclusive(terminal_path, local_terminal)
    public_body = deepcopy(body)
    public_body["terminal_capture"] = {
        "runtime_ref": terminal_path.relative_to(ROOT).as_posix(),
        "sha256": file_sha256(terminal_path),
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    serialized = json.dumps(public, ensure_ascii=False)
    if secret_id in serialized or secret_key in serialized:
        raise ResidualGapExternalLiveRunnerError(
            "residual_external_live_secret_redaction_failed"
        )
    _write_json_exclusive(output_path, public)
    return public


def _load_sdk(sdk_path: Path):
    if not sdk_path.is_dir():
        raise ResidualGapExternalLiveRunnerError(
            "residual_external_live_tencent_sdk_missing"
        )
    sys.path.insert(0, str(sdk_path))
    try:
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.wsa.v20250508 import models, wsa_client
    except ImportError as exc:
        raise ResidualGapExternalLiveRunnerError(
            "residual_external_live_tencent_sdk_import_failed"
        ) from exc
    version = importlib.metadata.version("tencentcloud-sdk-python")
    return credential, ClientProfile, HttpProfile, models, wsa_client, version


def _resolve_host(host: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(row[4][0])
                for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            }
        )
    )


def _synthetic_dns_decision(
    policy: Mapping[str, Any], *, resolver=_resolve_host
) -> dict[str, Any]:
    synthetic = ipaddress.ip_network("198.18.0.0/15")
    hosts = sorted(
        {
            str(host).lower()
            for values in policy["official_host_registry"].values()
            for host in values
        }
    )
    if not hosts:
        raise ResidualGapExternalLiveRunnerError(
            "residual_external_live_dns_host_set_empty"
        )
    rows: list[dict[str, Any]] = []
    synthetic_required = False
    for host in hosts:
        try:
            addresses = tuple(
                sorted(
                    {ipaddress.ip_address(value) for value in resolver(host)},
                    key=str,
                )
            )
        except (OSError, ValueError) as exc:
            raise ResidualGapExternalLiveRunnerError(
                "residual_external_live_dns_resolution_invalid"
            ) from exc
        if not addresses:
            raise ResidualGapExternalLiveRunnerError(
                "residual_external_live_dns_resolution_empty"
            )
        forbidden = tuple(
            address
            for address in addresses
            if address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        )
        if forbidden and not all(
            address.version == 4 and address in synthetic for address in forbidden
        ):
            raise ResidualGapExternalLiveRunnerError(
                "residual_external_live_forbidden_non_synthetic_dns_resolution"
            )
        host_uses_synthetic = bool(forbidden)
        synthetic_required = synthetic_required or host_uses_synthetic
        rows.append(
            {
                "host": host,
                "address_digests": [canonical_digest(str(value)) for value in addresses],
                "address_count": len(addresses),
                "controlled_synthetic_range_observed": host_uses_synthetic,
            }
        )
    body = {
        "guard": "public_allowlist_plus_controlled_198_18_0_0_15_proxy_v1",
        "host_count": len(hosts),
        "synthetic_allowance_required": synthetic_required,
        "all_forbidden_addresses_controlled_synthetic": True,
        "resolved_hosts": rows,
    }
    return {**body, "decision_digest": canonical_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--issue", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument(
        "--provider-profile",
        type=Path,
        default=DEFAULT_PROVIDER_PROFILE,
    )
    parser.add_argument("--authority", type=Path, default=DEFAULT_AUTHORITY)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sdk-path", type=Path, default=DEFAULT_SDK)
    args = parser.parse_args()
    if args.preflight:
        result = preflight(
            policy_path=args.policy,
            plan_path=args.plan,
            provider_profile_path=args.provider_profile,
        )
    elif args.issue:
        result = issue(
            policy_path=args.policy,
            plan_path=args.plan,
            provider_profile_path=args.provider_profile,
            authority_path=args.authority,
        )
    else:
        result = execute(
            policy_path=args.policy,
            plan_path=args.plan,
            provider_profile_path=args.provider_profile,
            authority_path=args.authority,
            runtime_root=args.runtime_root,
            ledger_path=args.ledger,
            output_path=args.output,
            sdk_path=args.sdk_path,
        )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
