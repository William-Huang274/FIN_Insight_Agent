from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.releases.run_fin_ia_0_1_3_s1_08_tencent_wsa_query_only_replacement_diagnostic import (  # noqa: E402
    TencentWSAQueryOnlyRunnerError,
    _git,
    _load_sdk,
    _sdk_error_projection,
    _sha256,
    _write_json_atomic,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_08_firecrawl_semantic_control import load_plan  # noqa: E402
from sec_agent.s1_08_tencent_relationship_aware_semantic_comparator import (  # noqa: E402
    RUN_SCOPE,
    S108TencentSemanticComparatorError,
    build_terminal_result,
    load_authority,
)
from sec_agent.s1_08_tencent_wsa_candidate_diagnostic import (  # noqa: E402
    load_tencent_wsa_candidate_profile,
    normalize_search_pro_response,
    redact_runtime_value,
)
from sec_agent.s1_08_tencent_wsa_query_only_replacement import (  # noqa: E402
    build_safe_request_capture,
    compile_query_only_request,
)


DEFAULT_AUTHORITY = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_authority_v1_0.json"
DEFAULT_PROFILE = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_tencent_wsa_candidate_provider_profile_v1_0.json"
DEFAULT_CONTROL_PLAN = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_plan_v1_0.json"
DEFAULT_RUNTIME = ROOT / "artifacts/runtime/provider_comparators/tencent_relationship_aware_semantic_r1_20260808"
DEFAULT_RESULT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_result_v1_0.json"


class TencentRelationshipAwareSemanticRunnerError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _relative(runtime_root: Path, path: Path) -> str:
    return path.resolve().relative_to(runtime_root.resolve()).as_posix()


def _validate_authority_bindings(
    *,
    authority: Mapping[str, Any],
    authority_path: Path,
    profile_path: Path,
    control_plan_path: Path,
) -> None:
    bindings = authority.get("immutable_bindings") or {}
    required = {
        "runner_sha256": Path(__file__).resolve(),
        "support_sha256": ROOT
        / "src/sec_agent/s1_08_tencent_relationship_aware_semantic_comparator.py",
        "normalizer_sha256": ROOT
        / "src/sec_agent/s1_08_tencent_wsa_candidate_diagnostic.py",
        "query_only_support_sha256": ROOT
        / "src/sec_agent/s1_08_tencent_wsa_query_only_replacement.py",
        "runner_helpers_sha256": ROOT
        / "scripts/releases/run_fin_ia_0_1_3_s1_08_tencent_wsa_query_only_replacement_diagnostic.py",
        "provider_profile_sha256": profile_path,
        "control_plan_sha256": control_plan_path,
        "control_support_sha256": ROOT
        / "src/sec_agent/s1_08_firecrawl_semantic_control.py",
        "scoring_contract_sha256": ROOT
        / "configs/eval/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_scoring_v1_0.json",
        "zero_call_proof_sha256": ROOT
        / "configs/releases/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_zero_call_proof_v1_0.json",
        "wire_policy_sha256": ROOT
        / "configs/runtime/fin_ia_0_1_3_s1_08_domestic_provider_wire_projection_policy_v1_0.json",
        "wire_projection_sha256": ROOT
        / "src/sec_agent/s1_08_provider_wire_projection.py",
        "credential_decision_sha256": ROOT
        / "configs/releases/fin_ia_0_1_3_s1_08_tencent_fresh_credential_and_same_matrix_comparator_decision_v1_0.json",
        "firecrawl_result_sha256": ROOT
        / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_result_v1_0.json",
        "firecrawl_assessment_sha256": ROOT
        / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_assessment_v1_0.json",
    }
    for field, path in required.items():
        if not path.is_file() or bindings.get(field) != _sha256(path):
            raise TencentRelationshipAwareSemanticRunnerError(
                "tencent_semantic_authority_binding_invalid"
            )
    control_plan = load_plan(control_plan_path)
    if bindings.get("control_plan_digest") != control_plan.get("plan_digest"):
        raise TencentRelationshipAwareSemanticRunnerError(
            "tencent_semantic_control_plan_digest_binding_invalid"
        )
    proof = json.loads(required["zero_call_proof_sha256"].read_text(encoding="utf-8"))
    proof_body = dict(proof)
    proof_digest = proof_body.pop("proof_digest", None)
    if (
        proof_digest != canonical_digest(proof_body)
        or bindings.get("zero_call_proof_digest") != proof_digest
    ):
        raise TencentRelationshipAwareSemanticRunnerError(
            "tencent_semantic_zero_call_proof_binding_invalid"
        )
    implementation_commit = str(bindings.get("implementation_commit") or "")
    if not implementation_commit:
        raise TencentRelationshipAwareSemanticRunnerError(
            "tencent_semantic_implementation_commit_missing"
        )
    try:
        _git("merge-base", "--is-ancestor", implementation_commit, "HEAD")
    except Exception as exc:
        raise TencentRelationshipAwareSemanticRunnerError(
            "tencent_semantic_implementation_commit_not_ancestor"
        ) from exc
    if authority_path.resolve() == required["zero_call_proof_sha256"].resolve():
        raise TencentRelationshipAwareSemanticRunnerError(
            "tencent_semantic_authority_path_invalid"
        )


def _safe_failure(
    *, code: str, provider_error: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    error = dict(provider_error or {})
    return {
        "phase": "provider_transport",
        "code": code,
        "provider_error_code": str(error.get("error_code") or ""),
        "provider_message": str(error.get("message") or "")[:500],
        "provider_request_id": error.get("request_id"),
        "retry_allowed": False,
        "credential_material_included": False,
    }


def _is_systemic_stop(error_code: str) -> bool:
    normalized = error_code.casefold()
    return normalized.startswith("authfailure") or normalized in {
        "unauthorizedoperation",
        "resourcenotfound",
        "resourceunavailable",
        "requestlimitexceeded",
    }


def run_comparator(
    *,
    authority_path: Path,
    profile_path: Path,
    control_plan_path: Path,
    sdk_path: Path,
    runtime_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    local_terminal = runtime_root / "terminal-result.json"
    if runtime_root.exists() or output_path.exists() or local_terminal.exists():
        raise TencentRelationshipAwareSemanticRunnerError(
            "tencent_semantic_exact_once_output_already_exists"
        )
    if _git("status", "--porcelain"):
        raise TencentRelationshipAwareSemanticRunnerError(
            "tencent_semantic_clean_worktree_required"
        )
    source_commit = _git("rev-parse", "HEAD")
    authority = load_authority(authority_path)
    control_plan = load_plan(control_plan_path)
    profile = load_tencent_wsa_candidate_profile(profile_path)
    _validate_authority_bindings(
        authority=authority,
        authority_path=authority_path,
        profile_path=profile_path,
        control_plan_path=control_plan_path,
    )
    if canonical_digest(profile) != (
        authority.get("immutable_bindings") or {}
    ).get("provider_profile_digest"):
        raise TencentRelationshipAwareSemanticRunnerError(
            "tencent_semantic_provider_profile_digest_invalid"
        )
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise TencentRelationshipAwareSemanticRunnerError(
            "tencent_semantic_project_os_preflight_failed"
        )
    secret_id = os.environ.get("TENCENTCLOUD_SECRET_ID", "").strip()
    secret_key = os.environ.get("TENCENTCLOUD_SECRET_KEY", "").strip()
    if not secret_id or not secret_key:
        raise TencentRelationshipAwareSemanticRunnerError(
            "tencent_semantic_runtime_credentials_missing"
        )
    secrets = (secret_id, secret_key)
    credential, ClientProfile, HttpProfile, sdk, sdk_version = _load_sdk(sdk_path)
    models, wsa_client = sdk
    http_profile = HttpProfile()
    http_profile.endpoint = profile["api_contract"]["endpoint"]
    http_profile.protocol = "https"
    http_profile.reqMethod = "POST"
    http_profile.reqTimeout = 30
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client_profile.signMethod = "TC3-HMAC-SHA256"
    client_profile.retryer = None
    client = wsa_client.WsaClient(
        credential.Credential(secret_id, secret_key), "", client_profile
    )

    runtime_root.mkdir(parents=True, exist_ok=False)
    _write_json_atomic(
        runtime_root / "attempt-start.json",
        {
            "admission_id": authority["admission_id"],
            "source_commit": source_commit,
            "control_plan_digest": control_plan["plan_digest"],
            "credential_source": "environment_variables_presence_only",
            "credential_values_persisted": False,
        },
    )
    whole_started = perf_counter()
    call_results: list[dict[str, Any]] = []
    systemic_stop = ""
    endpoint = str(profile["api_contract"]["endpoint"])
    for row in control_plan["query_rows"]:
        ordinal = int(row["ordinal"])
        intent_id = str(row["intent_id"])
        safe_name = (
            f"{ordinal:02d}-"
            f"{hashlib.sha256(intent_id.encode('utf-8')).hexdigest()[:12]}"
        )
        call_root = runtime_root / "calls" / safe_name
        request_body = compile_query_only_request(
            {
                "query_id": intent_id,
                "case_key": row["case_key"],
                "semantic_intent_ref": intent_id,
                "query_text": row["query_text"],
                "request_body_fields": ["Query"],
                "optional_fields": [],
                "result_ceiling": 10,
            }
        )
        request_capture = build_safe_request_capture(
            endpoint=endpoint, request_body=request_body
        )
        request_capture.update(
            {
                "provider_id": "tencent_wsa_searchpro_standard",
                "action": "SearchPro",
                "api_version": "2025-05-08",
                "control_intent_id": intent_id,
                "control_intent_digest": row["intent_digest"],
                "firecrawl_query_text_digest": canonical_digest(
                    {"query_text": row["query_text"]}
                ),
                "credential_source": "environment_presence_only",
                "credential_values_included": False,
            }
        )
        safe_request_path = call_root / "safe-request.json"
        _write_json_atomic(safe_request_path, request_capture)
        projection: dict[str, Any] = {}
        failure: dict[str, Any] = {}
        capture_refs: dict[str, Any] = {
            "safe_request": _relative(runtime_root, safe_request_path),
            "safe_request_sha256": _sha256(safe_request_path),
        }
        call_started = perf_counter()
        network_attempted = False
        status = "failed"
        terminal_code = "tencent_semantic_query_typed_failure"
        if systemic_stop:
            failure = _safe_failure(
                code="not_attempted_after_systemic_provider_rejection",
                provider_error={"error_code": systemic_stop},
            )
            terminal_code = "tencent_semantic_query_not_attempted_systemic_stop"
        else:
            network_attempted = True
            request = models.SearchProRequest()
            request.from_json_string(json.dumps(request_body, ensure_ascii=False))
            try:
                response = client.SearchPro(request)
                raw_payload = json.loads(response.to_json_string())
                safe_raw = redact_runtime_value(raw_payload, secrets)
                raw_path = call_root / "raw-response.json"
                _write_json_atomic(raw_path, safe_raw)
                capture_refs.update(
                    {
                        "raw_response": _relative(runtime_root, raw_path),
                        "raw_response_sha256": _sha256(raw_path),
                    }
                )
                projection = normalize_search_pro_response(
                    safe_raw, result_ceiling=10
                )
                status = "completed"
                terminal_code = "tencent_semantic_query_response_materialized"
            except Exception as exc:
                projected_error = redact_runtime_value(
                    _sdk_error_projection(exc), secrets
                )
                failure = _safe_failure(
                    code="provider_sdk_or_transport_error",
                    provider_error=projected_error,
                )
                failure_path = call_root / "raw-failure.json"
                _write_json_atomic(failure_path, failure)
                capture_refs.update(
                    {
                        "raw_failure": _relative(runtime_root, failure_path),
                        "raw_failure_sha256": _sha256(failure_path),
                    }
                )
                error_code = str(projected_error.get("error_code") or "")
                if _is_systemic_stop(error_code):
                    systemic_stop = error_code
        call_result = {
            "ordinal": ordinal,
            "intent_id": intent_id,
            "case_key": row["case_key"],
            "evidence_slot_id": row["evidence_slot_id"],
            "evidence_owner_entity_key": row["evidence_owner_entity_key"],
            "language": row["language"],
            "status": status,
            "terminal_code": terminal_code,
            "network_call_attempted": network_attempted,
            "request_capture": request_capture,
            "provider_projection": projection,
            "failure": failure,
            "elapsed_ms": int(round((perf_counter() - call_started) * 1000)),
            "capture_refs": capture_refs,
        }
        safe_call_result = redact_runtime_value(call_result, secrets)
        call_terminal_path = call_root / "terminal.json"
        _write_json_atomic(call_terminal_path, safe_call_result)
        safe_call_result["capture_refs"].update(
            {
                "call_terminal": _relative(runtime_root, call_terminal_path),
                "call_terminal_sha256": _sha256(call_terminal_path),
            }
        )
        call_results.append(safe_call_result)
    result = build_terminal_result(
        admission_id=str(authority["admission_id"]),
        source_commit=source_commit,
        control_plan_digest=str(control_plan["plan_digest"]),
        call_results=call_results,
        elapsed_ms=int(round((perf_counter() - whole_started) * 1000)),
        sdk_version=sdk_version,
    )
    safe_result = redact_runtime_value(result, secrets)
    serialized = json.dumps(safe_result, ensure_ascii=False)
    if secret_id in serialized or secret_key in serialized:
        raise TencentRelationshipAwareSemanticRunnerError(
            "tencent_semantic_secret_redaction_failed"
        )
    _write_json_atomic(local_terminal, safe_result)
    result_with_capture = dict(safe_result)
    result_with_capture["terminal_capture"] = {
        "runtime_ref": str(local_terminal.relative_to(ROOT)).replace("\\", "/"),
        "sha256": _sha256(local_terminal),
    }
    body = dict(result_with_capture)
    body.pop("result_digest", None)
    result_with_capture["result_digest"] = canonical_digest(body)
    _write_json_atomic(output_path, result_with_capture)
    return result_with_capture


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", type=Path, default=DEFAULT_AUTHORITY)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--control-plan", type=Path, default=DEFAULT_CONTROL_PLAN)
    parser.add_argument(
        "--sdk-path", type=Path, default=ROOT / ".codex_runtime/tencent-wsa-sdk"
    )
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT)
    args = parser.parse_args()
    try:
        result = run_comparator(
            authority_path=args.authority,
            profile_path=args.profile,
            control_plan_path=args.control_plan,
            sdk_path=args.sdk_path,
            runtime_root=args.runtime_root,
            output_path=args.output,
        )
    except (
        TencentRelationshipAwareSemanticRunnerError,
        S108TencentSemanticComparatorError,
        TencentWSAQueryOnlyRunnerError,
    ) as exc:
        print(json.dumps({"status": "blocked", "terminal_code": exc.code}))
        return 2
    print(
        json.dumps(
            {
                "status": result["status"],
                "observed_counts": result["observed_counts"],
                "provider_versions": result["provider_versions"],
                "documented_cost_cny": result["documented_cost_cny"],
                "elapsed_ms": result["elapsed_ms"],
                "result_digest": result["result_digest"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
