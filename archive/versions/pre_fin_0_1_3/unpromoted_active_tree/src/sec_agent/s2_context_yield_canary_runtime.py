from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s2_context_yield_program import (
    S2ContextYieldError,
    validate_compact_provider_output,
)
from sec_agent.s2_representative_node_program import (
    S2RepresentativeNodeError,
    consume_representative_specialist_output,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


ADMISSION_SCHEMA = "fin_ia_0_1_3_s2_03_context_yield_canary_admission_v1_0"
TERMINAL_SCHEMA = "fin_ia_0_1_3_s2_03_context_yield_canary_terminal_v1_0"
SCOPE = "FIN_0_1_3_S2_03_COMPACT_CONTEXT_NATURAL_REPROOF"


class S2ContextYieldCanaryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


ProviderCall = Callable[..., Mapping[str, Any]]


def issue_context_yield_admission(
    *,
    execution_git_commit: str,
    runner_sha256: str,
    program_sha256: str,
    policy_sha256: str,
    request_binding: Mapping[str, str],
    issued_at: str,
    expires_at: str,
    run_nonce: str,
    credential_present: bool,
    provider: Mapping[str, Any],
    budget: Mapping[str, Any],
) -> dict[str, Any]:
    if not _is_git_object_id(execution_git_commit):
        raise S2ContextYieldCanaryError("context_canary_git_commit_invalid")
    for value, code in (
        (runner_sha256, "context_canary_runner_sha_invalid"),
        (program_sha256, "context_canary_program_sha_invalid"),
        (policy_sha256, "context_canary_policy_sha_invalid"),
        (request_binding.get("request_digest"), "context_canary_request_digest_invalid"),
        (request_binding.get("context_digest"), "context_canary_context_digest_invalid"),
    ):
        if not _is_digest(value):
            raise S2ContextYieldCanaryError(code)
    _assert_provider_budget_credential(
        provider=provider,
        budget=budget,
        credential_present=credential_present,
    )
    issued = _parse_time(issued_at)
    expires = _parse_time(expires_at)
    if expires <= issued:
        raise S2ContextYieldCanaryError("context_canary_expiry_invalid")
    run_id = "fin013_s2_03_context_canary_" + canonical_digest(
        {"nonce": run_nonce, "git": execution_git_commit}
    )[:20]
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "admission_id": "admission::" + run_id,
        "scope": SCOPE,
        "run_id": run_id,
        "attempt_id": run_id + "::attempt_1",
        "runtime_identity": run_id + "::runtime_1",
        "execution_git_commit": execution_git_commit,
        "runner_sha256": runner_sha256,
        "program_sha256": program_sha256,
        "policy_sha256": policy_sha256,
        "request_binding": deepcopy(dict(request_binding)),
        "provider": deepcopy(dict(provider)),
        "budget": deepcopy(dict(budget)),
        "credential_present": True,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "run_nonce_digest": hashlib.sha256(run_nonce.encode("utf-8")).hexdigest(),
        "state": "issued_unconsumed",
    }
    return {**body, "admission_digest": canonical_digest(body)}


def validate_context_yield_admission(
    admission: Mapping[str, Any],
    *,
    execution_git_commit: str,
    runner_sha256: str,
    program_sha256: str,
    policy_sha256: str,
    request: Mapping[str, Any],
    compiled: Mapping[str, Any],
    observed_at: str,
) -> None:
    body = {key: deepcopy(value) for key, value in admission.items() if key != "admission_digest"}
    if (
        admission.get("schema_version") != ADMISSION_SCHEMA
        or admission.get("scope") != SCOPE
        or admission.get("state") != "issued_unconsumed"
        or admission.get("admission_digest") != canonical_digest(body)
    ):
        raise S2ContextYieldCanaryError("context_canary_admission_digest_or_state_invalid")
    binding = admission.get("request_binding") or {}
    if (
        binding.get("request_id") != request.get("request_id")
        or binding.get("request_digest") != request.get("request_digest")
        or binding.get("context_digest") != compiled.get("context_digest")
    ):
        raise S2ContextYieldCanaryError("context_canary_request_binding_invalid")
    compiled_body = {
        key: deepcopy(value)
        for key, value in compiled.items()
        if key not in {"context_digest", "capacity"}
    }
    if compiled.get("context_digest") != canonical_digest(compiled_body):
        raise S2ContextYieldCanaryError("context_canary_compact_context_digest_invalid")
    if (
        admission.get("execution_git_commit"),
        admission.get("runner_sha256"),
        admission.get("program_sha256"),
        admission.get("policy_sha256"),
    ) != (execution_git_commit, runner_sha256, program_sha256, policy_sha256):
        raise S2ContextYieldCanaryError("context_canary_execution_binding_invalid")
    if _parse_time(observed_at) > _parse_time(str(admission.get("expires_at") or "")):
        raise S2ContextYieldCanaryError("context_canary_admission_expired")
    _assert_provider_budget_credential(
        provider=admission.get("provider") or {},
        budget=admission.get("budget") or {},
        credential_present=admission.get("credential_present") is True,
    )


def execute_context_yield_canary(
    *,
    admission: Mapping[str, Any],
    request: Mapping[str, Any],
    compiled: Mapping[str, Any],
    execution_git_commit: str,
    runner_sha256: str,
    program_sha256: str,
    policy_sha256: str,
    runtime_root: Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    provider_call: ProviderCall,
    observed_at: str,
) -> dict[str, Any]:
    validate_context_yield_admission(
        admission,
        execution_git_commit=execution_git_commit,
        runner_sha256=runner_sha256,
        program_sha256=program_sha256,
        policy_sha256=policy_sha256,
        request=request,
        compiled=compiled,
        observed_at=observed_at,
    )
    root = runtime_root.resolve()
    ledger_path = shared_ledger.path.resolve()
    if ledger_path == root or root in ledger_path.parents:
        raise S2ContextYieldCanaryError("context_canary_shared_ledger_inside_runtime_root")
    root.mkdir(parents=True, exist_ok=False)
    captures = root / "captures"
    captures.mkdir()
    receipt = shared_ledger.reserve(
        admission_digest=str(admission["admission_digest"]),
        admission_id=str(admission["admission_id"]),
        scope=str(admission["scope"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        runtime_identity=str(admission["runtime_identity"]),
        reserved_at=observed_at,
    )
    kwargs = _provider_kwargs(
        compiled=compiled,
        provider=admission["provider"],
        budget=admission["budget"],
        run_id=str(admission["run_id"]),
    )
    try:
        result = dict(provider_call(**kwargs))
    except Exception as exc:  # provider boundary must still materialize a terminal result
        result = {
            "status": "gateway_exception",
            "content": "",
            "finish_reason": "",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "transport_attempt_count": 1,
            "exception_type": type(exc).__name__,
        }
    capture = {
        "schema_version": "fin_ia_0_1_3_s2_03_context_yield_provider_capture_v1_0",
        "request_id": request["request_id"],
        "request_digest": request["request_digest"],
        "context_digest": compiled["context_digest"],
        "provider_request": {key: deepcopy(value) for key, value in kwargs.items() if key != "api_key_env"},
        "gateway_result": result,
    }
    capture_digest = canonical_digest(capture)
    capture_path = captures / f"01_{capture_digest}.json"
    _write_exclusive(capture_path, capture)
    failure_code: str | None = None
    output: dict[str, Any] | None = None
    claim: dict[str, Any] | None = None
    if result.get("status") != "ok":
        failure_code = "context_canary_provider_transport_or_status_failure"
    else:
        try:
            parsed = json.loads(str(result.get("content") or ""))
            if not isinstance(parsed, Mapping):
                raise ValueError("output_not_object")
            output = dict(parsed)
            validate_compact_provider_output(output, compiled=compiled)
            claim = consume_representative_specialist_output(
                request=request,
                provider_output=output,
            )
        except (S2RepresentativeNodeError, S2ContextYieldError, KeyError) as exc:
            failure_code = "context_canary_provider_output_contract_invalid:" + str(
                getattr(exc, "code", type(exc).__name__)
            )
        except (json.JSONDecodeError, ValueError):
            failure_code = "context_canary_provider_output_json_invalid"
    passed = failure_code is None and output is not None and claim is not None
    terminal_status = "terminal_succeeded_exact_once" if passed else "terminal_failed_no_retry"
    terminal_body = {
        "schema_version": TERMINAL_SCHEMA,
        "admission_digest": admission["admission_digest"],
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "status": terminal_status,
        "terminal_phase": "compact_context_natural_reproof",
        "terminal_code": failure_code or "compact_context_natural_reproof_pass",
        "request_id": request["request_id"],
        "request_digest": request["request_digest"],
        "context_digest": compiled["context_digest"],
        "capture_digest": capture_digest,
        "capture_ref": capture_path.relative_to(root).as_posix(),
        "gateway_status": result.get("status"),
        "finish_reason": result.get("finish_reason"),
        "usage": {
            "input_tokens": int(result.get("input_tokens") or 0),
            "output_tokens": int(result.get("output_tokens") or 0),
            "total_tokens": int(result.get("total_tokens") or 0),
            "transport_attempt_count": int(result.get("transport_attempt_count") or 0),
        },
        "provider_output": output,
        "provider_output_digest": canonical_digest(output) if output else None,
        "claim": claim,
        "completed_calls": 1,
        "retry_count": 0,
        "fallback_count": 0,
        "business_artifact_promotions": 0,
        "observed_at": observed_at,
        "reservation_digest": receipt.reservation_digest,
    }
    terminal = {**terminal_body, "terminal_result_digest": canonical_digest(terminal_body)}
    _write_exclusive(root / "terminal_result.json", terminal)
    final_receipt = shared_ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status=terminal_status,
        terminal_phase="compact_context_natural_reproof",
        terminal_code=str(terminal["terminal_code"]),
        terminal_result_digest=str(terminal["terminal_result_digest"]),
        finalized_at=observed_at,
    )
    return {**terminal, "shared_admission_receipt": final_receipt.as_dict()}


def _provider_kwargs(
    *, compiled: Mapping[str, Any], provider: Mapping[str, Any], budget: Mapping[str, Any], run_id: str
) -> dict[str, Any]:
    return {
        "llm_backend": provider["backend"],
        "base_url": provider["base_url"],
        "chat_completions_path": provider["chat_completions_path"],
        "model": provider["model"],
        "messages": [
            {
                "role": "system",
                "content": "You are a bounded financial-research judgment selector. Return one JSON object only. Use only request-local aliases and enum values. Do not add fields, prose, markdown, numbers, dates, identities, or explanations.",
            },
            {
                "role": "user",
                "content": json.dumps(compiled["model_context"], ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            },
        ],
        "response_format": {"type": "json_object"},
        "api_key_env": provider["api_key_env"],
        "temperature": 0.0,
        "max_tokens": int(budget["maximum_output_tokens"]),
        "timeout_s": int(budget["timeout_seconds"]),
        "stream": False,
        "enable_thinking": False,
        "role": "fin013_s2_compact_context_judgment_selector",
        "profile": str(compiled["model_context"]["program_cell_id"]),
        "trace_tags": {
            "run_id": run_id,
            "request_id": compiled["request_id"],
            "context_digest": compiled["context_digest"],
        },
        "max_transport_attempts": 1,
    }


def _write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise S2ContextYieldCanaryError("context_canary_time_invalid") from exc
    if parsed.tzinfo is None:
        raise S2ContextYieldCanaryError("context_canary_time_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _is_digest(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _is_git_object_id(value: Any) -> bool:
    text = str(value or "")
    return len(text) in {40, 64} and all(char in "0123456789abcdef" for char in text)


def _assert_provider_budget_credential(
    *,
    provider: Mapping[str, Any],
    budget: Mapping[str, Any],
    credential_present: bool,
) -> None:
    if credential_present is not True:
        raise S2ContextYieldCanaryError("context_canary_credential_missing")
    if (
        provider.get("backend") != "deepseek"
        or provider.get("model") != "deepseek-v4-pro"
        or provider.get("api_key_env") != "DEEPSEEK_API_KEY"
        or provider.get("base_url") != "https://api.deepseek.com/beta"
        or provider.get("chat_completions_path") != "/chat/completions"
    ):
        raise S2ContextYieldCanaryError("context_canary_provider_route_invalid")
    expected_budget = {
        "maximum_provider_calls": 1,
        "retry_count": 0,
        "fallback_count": 0,
        "maximum_output_tokens": 900,
        "timeout_seconds": 180,
    }
    if dict(budget) != expected_budget:
        raise S2ContextYieldCanaryError("context_canary_budget_invalid")


__all__ = [
    "S2ContextYieldCanaryError",
    "execute_context_yield_canary",
    "issue_context_yield_admission",
    "validate_context_yield_admission",
]
