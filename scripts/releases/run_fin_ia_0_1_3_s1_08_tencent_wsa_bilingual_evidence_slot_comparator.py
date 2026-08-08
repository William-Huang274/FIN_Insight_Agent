from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.releases.run_fin_ia_0_1_3_s1_08_tencent_wsa_query_only_replacement_diagnostic import (
    _git,
    _load_sdk,
    _sdk_error_projection,
    _sha256,
    _write_json_atomic,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.project_os_preflight import run_project_os_preflight
from sec_agent.s1_08_tencent_wsa_bilingual_evidence_slot_comparator import (
    RUN_SCOPE,
    TencentWSABilingualComparatorError,
    build_comparator_terminal_result,
    load_comparator_authority,
    load_query_plan,
)
from sec_agent.s1_08_tencent_wsa_candidate_diagnostic import (
    load_tencent_wsa_candidate_profile,
    normalize_search_pro_response,
    redact_runtime_value,
)
from sec_agent.s1_08_tencent_wsa_query_only_replacement import (
    build_safe_request_capture,
    compile_query_only_request,
)


class TencentWSABilingualComparatorRunnerError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _validate_authority_bindings(
    authority: Mapping[str, Any],
    *,
    authority_path: Path,
    profile_path: Path,
    query_plan_path: Path,
) -> None:
    bindings = authority.get("immutable_bindings") or {}
    required = {
        "provider_profile_sha256": profile_path,
        "query_plan_sha256": query_plan_path,
        "runner_sha256": Path(__file__).resolve(),
        "evaluator_sha256": ROOT
        / "scripts/releases/evaluate_fin_ia_0_1_3_s1_08_tencent_wsa_bilingual_evidence_slot_comparator.py",
        "support_sha256": ROOT
        / "src/sec_agent/s1_08_tencent_wsa_bilingual_evidence_slot_comparator.py",
        "normalizer_sha256": ROOT
        / "src/sec_agent/s1_08_tencent_wsa_candidate_diagnostic.py",
        "query_only_support_sha256": ROOT
        / "src/sec_agent/s1_08_tencent_wsa_query_only_replacement.py",
        "runner_helpers_sha256": ROOT
        / "scripts/releases/run_fin_ia_0_1_3_s1_08_tencent_wsa_query_only_replacement_diagnostic.py",
        "R4_result_sha256": ROOT
        / "configs/releases/fin_ia_0_1_3_s1_08_tencent_wsa_standard_tier_r4_result_v1_0.json",
        "R4_assessment_sha256": ROOT
        / "configs/releases/fin_ia_0_1_3_s1_08_tencent_wsa_standard_tier_r4_quality_assessment_v1_0.json",
        "scoring_contract_sha256": ROOT
        / "configs/eval/fin_ia_0_1_3_s1_08_tencent_wsa_bilingual_evidence_slot_scoring_contract_v1_0.json",
        "zero_call_proof_sha256": ROOT
        / "configs/releases/fin_ia_0_1_3_s1_08_tencent_wsa_bilingual_evidence_slot_comparator_zero_call_proof_v1_0.json",
    }
    for field, path in required.items():
        if not path.is_file() or bindings.get(field) != _sha256(path):
            raise TencentWSABilingualComparatorRunnerError(
                "tencent_wsa_bilingual_authority_binding_invalid"
            )
    plan = load_query_plan(query_plan_path)
    if bindings.get("query_plan_digest") != canonical_digest(plan):
        raise TencentWSABilingualComparatorRunnerError(
            "tencent_wsa_bilingual_query_plan_digest_invalid"
        )
    proof = json.loads(required["zero_call_proof_sha256"].read_text(encoding="utf-8"))
    proof_body = dict(proof)
    proof_digest = proof_body.pop("proof_digest", None)
    if (
        proof_digest != canonical_digest(proof_body)
        or bindings.get("zero_call_proof_digest") != proof_digest
        or authority_path.resolve() == required["zero_call_proof_sha256"].resolve()
    ):
        raise TencentWSABilingualComparatorRunnerError(
            "tencent_wsa_bilingual_zero_call_proof_binding_invalid"
        )


def _relative_runtime_ref(runtime_root: Path, path: Path) -> str:
    return path.resolve().relative_to(runtime_root.resolve()).as_posix()


def run_comparator(
    *,
    authority_path: Path,
    profile_path: Path,
    query_plan_path: Path,
    sdk_path: Path,
    runtime_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    terminal_path = runtime_root / "terminal-result.json"
    if output_path.exists() or terminal_path.exists():
        raise TencentWSABilingualComparatorRunnerError(
            "tencent_wsa_bilingual_exact_once_result_already_exists"
        )
    if _git("status", "--porcelain"):
        raise TencentWSABilingualComparatorRunnerError(
            "tencent_wsa_bilingual_clean_worktree_required"
        )
    source_commit = _git("rev-parse", "HEAD")
    authority = load_comparator_authority(authority_path)
    query_plan = load_query_plan(query_plan_path)
    profile = load_tencent_wsa_candidate_profile(profile_path)
    _validate_authority_bindings(
        authority,
        authority_path=authority_path,
        profile_path=profile_path,
        query_plan_path=query_plan_path,
    )
    if (
        canonical_digest(profile)
        != (authority.get("immutable_bindings") or {}).get("provider_profile_digest")
        or canonical_digest(query_plan)
        != (authority.get("immutable_bindings") or {}).get("query_plan_digest")
    ):
        raise TencentWSABilingualComparatorRunnerError(
            "tencent_wsa_bilingual_runtime_identity_invalid"
        )
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise TencentWSABilingualComparatorRunnerError(
            "tencent_wsa_bilingual_project_os_preflight_failed"
        )

    runtime_root.mkdir(parents=True, exist_ok=True)
    secret_id = getpass.getpass("Tencent SecretId (hidden): ").strip()
    secret_key = getpass.getpass("Tencent SecretKey (hidden): ").strip()
    if not secret_id or not secret_key:
        raise TencentWSABilingualComparatorRunnerError(
            "tencent_wsa_bilingual_runtime_credentials_missing"
        )
    secrets = (secret_id, secret_key)
    credential, ClientProfile, HttpProfile, sdk, sdk_version = _load_sdk(sdk_path)
    models, wsa_client = sdk
    http_profile = HttpProfile()
    http_profile.endpoint = profile["api_contract"]["endpoint"]
    http_profile.protocol = "https"
    http_profile.reqMethod = "POST"
    http_profile.reqTimeout = int(query_plan["budget"]["timeout_seconds_per_call"])
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client_profile.signMethod = "TC3-HMAC-SHA256"
    client_profile.retryer = None
    client = wsa_client.WsaClient(
        credential.Credential(secret_id, secret_key), "", client_profile
    )

    whole_started = perf_counter()
    call_results: list[dict[str, Any]] = []
    for ordinal, query in enumerate(query_plan["query_rows"], start=1):
        query_id = str(query["query_id"])
        call_root = runtime_root / "calls" / f"{ordinal:02d}-{query_id.lower()}"
        request_body = compile_query_only_request(
            {
                "query_id": query_id,
                "case_key": query["case_key"],
                "semantic_intent_ref": (
                    f"{query['case_key']}:{query['slot_id']}:{query['language']}"
                ),
                "query_text": query["query_text"],
                "request_body_fields": ["Query"],
                "optional_fields": [],
                "result_ceiling": 10,
            }
        )
        request_capture = build_safe_request_capture(
            endpoint=profile["api_contract"]["endpoint"], request_body=request_body
        )
        safe_request_path = call_root / "safe-request.json"
        _write_json_atomic(safe_request_path, request_capture)
        request = models.SearchProRequest()
        request.from_json_string(json.dumps(request_body))
        call_started = perf_counter()
        try:
            response = client.SearchPro(request)
            raw_payload = json.loads(response.to_json_string())
            safe_raw = redact_runtime_value(raw_payload, secrets)
            raw_path = call_root / "raw-response.json"
            _write_json_atomic(raw_path, safe_raw)
            projection = normalize_search_pro_response(safe_raw, result_ceiling=10)
            call_result = {
                "ordinal": ordinal,
                "query_id": query_id,
                "case_key": query["case_key"],
                "slot_id": query["slot_id"],
                "language": query["language"],
                "status": "completed",
                "terminal_code": "tencent_wsa_bilingual_query_response_materialized",
                "network_call_attempted": True,
                "request_capture": request_capture,
                "provider_projection": projection,
                "failure": {},
                "elapsed_ms": int(round((perf_counter() - call_started) * 1000)),
                "capture_refs": {
                    "safe_request": _relative_runtime_ref(runtime_root, safe_request_path),
                    "safe_request_sha256": _sha256(safe_request_path),
                    "raw_response": _relative_runtime_ref(runtime_root, raw_path),
                    "raw_response_sha256": _sha256(raw_path),
                },
            }
        except Exception as exc:
            failure = redact_runtime_value(_sdk_error_projection(exc), secrets)
            failure_path = call_root / "raw-failure.json"
            _write_json_atomic(failure_path, failure)
            call_result = {
                "ordinal": ordinal,
                "query_id": query_id,
                "case_key": query["case_key"],
                "slot_id": query["slot_id"],
                "language": query["language"],
                "status": "failed",
                "terminal_code": "tencent_wsa_bilingual_query_typed_failure",
                "network_call_attempted": True,
                "request_capture": request_capture,
                "provider_projection": {},
                "failure": failure,
                "elapsed_ms": int(round((perf_counter() - call_started) * 1000)),
                "capture_refs": {
                    "safe_request": _relative_runtime_ref(runtime_root, safe_request_path),
                    "safe_request_sha256": _sha256(safe_request_path),
                    "raw_failure": _relative_runtime_ref(runtime_root, failure_path),
                    "raw_failure_sha256": _sha256(failure_path),
                },
            }
        safe_call_result = redact_runtime_value(call_result, secrets)
        call_terminal_path = call_root / "terminal.json"
        _write_json_atomic(call_terminal_path, safe_call_result)
        safe_call_result["capture_refs"]["call_terminal"] = _relative_runtime_ref(
            runtime_root, call_terminal_path
        )
        safe_call_result["capture_refs"]["call_terminal_sha256"] = _sha256(
            call_terminal_path
        )
        call_results.append(safe_call_result)

    terminal = build_comparator_terminal_result(
        admission_id=str(authority["admission_id"]),
        source_commit=source_commit,
        query_plan_digest=canonical_digest(query_plan),
        call_results=call_results,
        elapsed_ms=int(round((perf_counter() - whole_started) * 1000)),
        sdk_version=sdk_version,
    )
    safe_terminal = redact_runtime_value(terminal, secrets)
    serialized = json.dumps(safe_terminal, ensure_ascii=False)
    if secret_id in serialized or secret_key in serialized:
        raise TencentWSABilingualComparatorRunnerError(
            "tencent_wsa_bilingual_secret_redaction_failed"
        )
    _write_json_atomic(terminal_path, safe_terminal)
    _write_json_atomic(output_path, safe_terminal)
    return safe_terminal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--query-plan", required=True)
    parser.add_argument(
        "--sdk-path", default=str(ROOT / ".codex_runtime/tencent-wsa-sdk")
    )
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = run_comparator(
            authority_path=Path(args.authority).resolve(),
            profile_path=Path(args.profile).resolve(),
            query_plan_path=Path(args.query_plan).resolve(),
            sdk_path=Path(args.sdk_path).resolve(),
            runtime_root=Path(args.runtime_root).resolve(),
            output_path=Path(args.output).resolve(),
        )
    except (
        TencentWSABilingualComparatorRunnerError,
        TencentWSABilingualComparatorError,
    ) as exc:
        print(json.dumps({"status": "blocked", "terminal_code": exc.code}))
        return 2
    projection = {
        "status": result["status"],
        "terminal_code": result["terminal_code"],
        "terminalized_queries": result["observed_counts"]["terminalized_queries"],
        "successful_calls": result["observed_counts"]["successful_calls"],
        "typed_failed_calls": result["observed_counts"]["typed_failed_calls"],
        "documented_cost_cny": result["documented_cost_cny"],
        "elapsed_ms": result["elapsed_ms"],
    }
    print(json.dumps(projection, ensure_ascii=True, indent=2))
    return 0 if result["observed_counts"]["terminalized_queries"] == 24 else 3


if __name__ == "__main__":
    raise SystemExit(main())
