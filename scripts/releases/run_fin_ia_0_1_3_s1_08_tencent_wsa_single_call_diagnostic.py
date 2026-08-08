from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from time import perf_counter
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.project_os_preflight import run_project_os_preflight
from sec_agent.s1_08_tencent_wsa_candidate_diagnostic import (
    CONTRACT_REF,
    TencentWSADiagnosticError,
    build_terminal_result,
    load_tencent_wsa_candidate_profile,
    normalize_search_pro_response,
    redact_runtime_value,
)


AUTHORITY_SCHEMA = "fin_ia_0_1_3_s1_08_tencent_wsa_single_call_diagnostic_authority_v1_0"
RUN_SCOPE = "S1_08_PAID_BROAD_SEARCH_TENCENT_WSA_SINGLE_CALL_DIAGNOSTIC"


class TencentWSARunnerError(RuntimeError):
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
        raise TencentWSARunnerError("tencent_wsa_git_preflight_failed")
    return completed.stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)


def load_authority(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    body = dict(payload)
    digest = body.pop("authority_digest", None)
    if (
        body.get("schema_version") != AUTHORITY_SCHEMA
        or body.get("contract_ref") != CONTRACT_REF
        or digest != canonical_digest(body)
        or body.get("status") != "issued_unconsumed"
        or body.get("authorized_scope") != RUN_SCOPE
    ):
        raise TencentWSARunnerError("tencent_wsa_authority_identity_invalid")
    budget = body.get("execution_contract") or {}
    if (
        budget.get("provider_call_ceiling") != 1
        or budget.get("retry_ceiling") != 0
        or budget.get("model_call_ceiling") != 0
        or budget.get("evidence_promotion_allowed") is not False
        or budget.get("production_capability_claim_allowed") is not False
    ):
        raise TencentWSARunnerError("tencent_wsa_authority_boundary_invalid")
    return payload


def _sdk_error_projection(exc: Exception) -> dict[str, Any]:
    code = getattr(exc, "get_code", lambda: exc.__class__.__name__)()
    message = getattr(exc, "get_message", lambda: str(exc))()
    request_id = getattr(exc, "get_request_id", lambda: "")()
    return {
        "error_code": str(code or exc.__class__.__name__),
        "message": str(message or ""),
        "request_id": str(request_id or "") or None,
    }


def _load_sdk(sdk_path: Path) -> tuple[Any, Any, Any, Any, str]:
    sys.path.insert(0, str(sdk_path))
    try:
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.wsa.v20250508 import models, wsa_client
    except ImportError as exc:
        raise TencentWSARunnerError("tencent_wsa_official_sdk_missing") from exc
    version = importlib.metadata.version("tencentcloud-sdk-python")
    return credential, ClientProfile, HttpProfile, (models, wsa_client), version


def run_diagnostic(
    *,
    authority_path: Path,
    profile_path: Path,
    sdk_path: Path,
    runtime_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    terminal_path = runtime_root / "terminal-result.json"
    if output_path.exists() or terminal_path.exists():
        raise TencentWSARunnerError("tencent_wsa_exact_once_result_already_exists")
    if _git("status", "--porcelain"):
        raise TencentWSARunnerError("tencent_wsa_clean_worktree_required")
    source_commit = _git("rev-parse", "HEAD")
    authority = load_authority(authority_path)
    profile = load_tencent_wsa_candidate_profile(profile_path)
    if (
        _sha256(profile_path) != authority.get("provider_profile_sha256")
        or canonical_digest(profile) != authority.get("provider_profile_digest")
        or _sha256(Path(__file__).resolve()) != authority.get("runner_sha256")
    ):
        raise TencentWSARunnerError("tencent_wsa_authority_binding_invalid")
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise TencentWSARunnerError("tencent_wsa_project_os_preflight_failed")

    query = dict(authority["query"])
    request_capture = {
        "schema_version": "fin_ia_0_1_3_s1_08_tencent_wsa_safe_request_capture_v1_0",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": profile["api_contract"]["endpoint"],
        "protocol": "https",
        "method": "POST",
        "action": "SearchPro",
        "version": "2025-05-08",
        "region": "",
        "request_body": {"Query": query["query_text"], "Mode": 0},
        "credential_fields_present": False,
        "authorization_or_signature_present": False,
        "capture_before_transport": True,
    }
    runtime_root.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(runtime_root / "safe-request.json", request_capture)

    secret_id = getpass.getpass("Tencent SecretId (hidden): ").strip()
    secret_key = getpass.getpass("Tencent SecretKey (hidden): ").strip()
    if not secret_id or not secret_key:
        raise TencentWSARunnerError("tencent_wsa_runtime_credentials_missing")
    secrets = (secret_id, secret_key)

    credential, ClientProfile, HttpProfile, sdk, sdk_version = _load_sdk(sdk_path)
    models, wsa_client = sdk
    http_profile = HttpProfile()
    http_profile.endpoint = profile["api_contract"]["endpoint"]
    http_profile.protocol = "https"
    http_profile.reqMethod = "POST"
    http_profile.reqTimeout = int(profile["diagnostic_budget"]["request_timeout_seconds"])
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client_profile.signMethod = "TC3-HMAC-SHA256"
    client_profile.retryer = None
    client = wsa_client.WsaClient(
        credential.Credential(secret_id, secret_key), "", client_profile
    )
    req = models.SearchProRequest()
    req.from_json_string(json.dumps({"Query": query["query_text"], "Mode": 0}))

    started = perf_counter()
    call_attempted = 0
    try:
        call_attempted = 1
        response = client.SearchPro(req)
        raw_payload = json.loads(response.to_json_string())
        safe_raw = redact_runtime_value(raw_payload, secrets)
        _write_json_atomic(runtime_root / "raw-response.json", safe_raw)
        provider_projection = normalize_search_pro_response(
            safe_raw,
            result_ceiling=int(profile["diagnostic_budget"]["result_ceiling"]),
        )
        terminal = build_terminal_result(
            admission_id=str(authority["admission_id"]),
            source_commit=source_commit,
            status="completed",
            terminal_code="tencent_wsa_single_call_response_materialized",
            request_capture=request_capture,
            provider_projection=provider_projection,
            network_call_count=call_attempted,
            elapsed_ms=int(round((perf_counter() - started) * 1000)),
            sdk_version=sdk_version,
        )
    except Exception as exc:
        failure = redact_runtime_value(_sdk_error_projection(exc), secrets)
        _write_json_atomic(runtime_root / "raw-failure.json", failure)
        terminal = build_terminal_result(
            admission_id=str(authority["admission_id"]),
            source_commit=source_commit,
            status="failed",
            terminal_code="tencent_wsa_single_call_typed_failure",
            request_capture=request_capture,
            provider_projection=None,
            network_call_count=call_attempted,
            elapsed_ms=int(round((perf_counter() - started) * 1000)),
            sdk_version=sdk_version,
            failure=failure,
        )
    safe_terminal = redact_runtime_value(terminal, secrets)
    serialized = json.dumps(safe_terminal, ensure_ascii=False)
    if secret_id in serialized or secret_key in serialized:
        raise TencentWSARunnerError("tencent_wsa_secret_redaction_failed")
    _write_json_atomic(terminal_path, safe_terminal)
    _write_json_atomic(output_path, safe_terminal)
    return safe_terminal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--sdk-path", default=str(ROOT / ".codex_runtime/tencent-wsa-sdk"))
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = run_diagnostic(
            authority_path=Path(args.authority).resolve(),
            profile_path=Path(args.profile).resolve(),
            sdk_path=Path(args.sdk_path).resolve(),
            runtime_root=Path(args.runtime_root).resolve(),
            output_path=Path(args.output).resolve(),
        )
    except TencentWSARunnerError as exc:
        print(json.dumps({"status": "blocked", "terminal_code": exc.code}))
        return 2
    projection = {
        "status": result["status"],
        "terminal_code": result["terminal_code"],
        "provider_version": (result.get("provider_projection") or {}).get("provider_version"),
        "locator_count": (result.get("provider_projection") or {}).get(
            "normalized_unique_locator_count", 0
        ),
        "published_date_count": (result.get("provider_projection") or {}).get(
            "published_date_count", 0
        ),
        "error_code": (result.get("failure") or {}).get("error_code"),
    }
    print(json.dumps(projection, ensure_ascii=True, indent=2))
    return 0 if result["status"] == "completed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
