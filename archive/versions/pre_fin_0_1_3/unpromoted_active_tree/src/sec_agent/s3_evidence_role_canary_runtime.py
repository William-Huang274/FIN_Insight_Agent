from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s3_evidence_role_contract import (
    CONTRACT_REF,
    S3EvidenceRoleContractError,
    consume_s3_evidence_selection_output,
    normalize_s3_evidence_selection_output,
    validate_s3_evidence_selection_output,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


ADMISSION_SCHEMA = "fin_ia_0_1_3_s3_evidence_role_canary_admission_v1_0"
TERMINAL_SCHEMA = "fin_ia_0_1_3_s3_evidence_role_canary_terminal_v1_0"
SCOPE = "FIN_0_1_3_S3_DELL_DEMAND_EVIDENCE_ROLE_V2_NATURAL_CANARY"


class S3EvidenceRoleCanaryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


ProviderCall = Callable[..., Mapping[str, Any]]


def issue_evidence_role_canary_admission(
    *,
    execution_git_commit: str,
    runner_sha256: str,
    context_source_sha256: str,
    policy_sha256: str,
    request_binding: Mapping[str, str],
    issued_at: str,
    expires_at: str,
    run_nonce: str,
    credential_present: bool,
    provider: Mapping[str, Any],
    budget: Mapping[str, Any],
) -> dict[str, Any]:
    if not _git_id(execution_git_commit):
        raise S3EvidenceRoleCanaryError("s3_evidence_canary_git_invalid")
    for value in (
        runner_sha256,
        context_source_sha256,
        policy_sha256,
        request_binding.get("request_digest"),
        request_binding.get("context_digest"),
    ):
        if not _digest(value):
            raise S3EvidenceRoleCanaryError("s3_evidence_canary_binding_digest_invalid")
    _assert_provider_budget(provider=provider, budget=budget, credential_present=credential_present)
    if _time(expires_at) <= _time(issued_at):
        raise S3EvidenceRoleCanaryError("s3_evidence_canary_expiry_invalid")
    run_id = "fin013_s3_evidence_role_canary_" + canonical_digest(
        {"nonce": run_nonce, "git": execution_git_commit}
    )[:20]
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "admission_id": "admission::" + run_id,
        "scope": SCOPE,
        "contract_ref": CONTRACT_REF,
        "run_id": run_id,
        "attempt_id": run_id + "::attempt_1",
        "runtime_identity": run_id + "::runtime_1",
        "execution_git_commit": execution_git_commit,
        "runner_sha256": runner_sha256,
        "context_source_sha256": context_source_sha256,
        "policy_sha256": policy_sha256,
        "request_binding": deepcopy(dict(request_binding)),
        "provider": deepcopy(dict(provider)),
        "budget": deepcopy(dict(budget)),
        "credential_present": True,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "run_nonce_digest": canonical_digest(run_nonce),
        "state": "issued_unconsumed",
    }
    return {**body, "admission_digest": canonical_digest(body)}


def execute_evidence_role_canary(
    *,
    admission: Mapping[str, Any],
    request: Mapping[str, Any],
    compiled: Mapping[str, Any],
    execution_git_commit: str,
    runner_sha256: str,
    context_source_sha256: str,
    policy_sha256: str,
    runtime_root: Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    provider_call: ProviderCall,
    observed_at: str,
) -> dict[str, Any]:
    _validate_admission(
        admission=admission,
        request=request,
        compiled=compiled,
        execution_git_commit=execution_git_commit,
        runner_sha256=runner_sha256,
        context_source_sha256=context_source_sha256,
        policy_sha256=policy_sha256,
        observed_at=observed_at,
    )
    root = runtime_root.resolve()
    ledger_path = shared_ledger.path.resolve()
    if ledger_path == root or root in ledger_path.parents:
        raise S3EvidenceRoleCanaryError("s3_evidence_canary_shared_ledger_inside_runtime_root")
    root.mkdir(parents=True, exist_ok=False)
    (root / "captures").mkdir()
    receipt = shared_ledger.reserve(
        admission_digest=str(admission["admission_digest"]),
        admission_id=str(admission["admission_id"]),
        scope=str(admission["scope"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        runtime_identity=str(admission["runtime_identity"]),
        reserved_at=observed_at,
    )
    kwargs = _provider_kwargs(compiled=compiled, admission=admission)
    try:
        result = dict(provider_call(**kwargs))
    except Exception as exc:
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
        "schema_version": "fin_ia_0_1_3_s3_evidence_role_canary_capture_v1_0",
        "request_id": request["request_id"],
        "request_digest": request["request_digest"],
        "context_digest": compiled["context_digest"],
        "provider_request": {key: deepcopy(value) for key, value in kwargs.items() if key != "api_key_env"},
        "gateway_result": result,
    }
    capture_digest = canonical_digest(capture)
    capture_ref = f"captures/01_{capture_digest}.json"
    _write(root / capture_ref, capture)
    output: dict[str, Any] | None = None
    claim: dict[str, Any] | None = None
    normalization_receipt: dict[str, Any] | None = None
    failure: str | None = None
    if result.get("status") != "ok":
        failure = "s3_evidence_canary_provider_transport_or_status_failure"
    else:
        try:
            parsed = json.loads(str(result.get("content") or ""))
            if not isinstance(parsed, Mapping):
                raise ValueError("output_not_object")
            output = dict(parsed)
            output, normalization_receipt = normalize_s3_evidence_selection_output(
                output, compiled=compiled
            )
            validate_s3_evidence_selection_output(output, compiled=compiled)
            claim = consume_s3_evidence_selection_output(
                request=request, compiled=compiled, provider_output=output
            )
        except (S3EvidenceRoleContractError, KeyError) as exc:
            failure = "s3_evidence_canary_output_contract_invalid:" + str(
                getattr(exc, "code", type(exc).__name__)
            )
        except (json.JSONDecodeError, ValueError):
            failure = "s3_evidence_canary_output_json_invalid"
    status = "terminal_succeeded_exact_once" if failure is None else "terminal_failed_no_retry"
    terminal_body = {
        "schema_version": TERMINAL_SCHEMA,
        "admission_digest": admission["admission_digest"],
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "status": status,
        "terminal_phase": "s3_evidence_role_v2_single_node_natural_canary",
        "terminal_code": failure or "s3_evidence_role_v2_single_node_pass",
        "request_id": request["request_id"],
        "request_digest": request["request_digest"],
        "context_digest": compiled["context_digest"],
        "capture_digest": capture_digest,
        "capture_ref": capture_ref,
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
        "local_claim": claim,
        "normalization_receipt": normalization_receipt,
        "completed_calls": 1,
        "retry_count": 0,
        "fallback_count": 0,
        "business_artifact_promotions": 0,
        "observed_at": observed_at,
        "reservation_digest": receipt.reservation_digest,
    }
    terminal = {**terminal_body, "terminal_result_digest": canonical_digest(terminal_body)}
    _write(root / "terminal_result.json", terminal)
    final_receipt = shared_ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status=status,
        terminal_phase=str(terminal["terminal_phase"]),
        terminal_code=str(terminal["terminal_code"]),
        terminal_result_digest=str(terminal["terminal_result_digest"]),
        finalized_at=observed_at,
    )
    return {**terminal, "shared_admission_receipt": final_receipt.as_dict()}


def _validate_admission(**values: Any) -> None:
    admission = values["admission"]
    body = {key: deepcopy(value) for key, value in admission.items() if key != "admission_digest"}
    if (
        admission.get("schema_version") != ADMISSION_SCHEMA
        or admission.get("scope") != SCOPE
        or admission.get("contract_ref") != CONTRACT_REF
        or admission.get("state") != "issued_unconsumed"
        or admission.get("admission_digest") != canonical_digest(body)
    ):
        raise S3EvidenceRoleCanaryError("s3_evidence_canary_admission_invalid")
    request = values["request"]
    compiled = values["compiled"]
    binding = admission.get("request_binding") or {}
    if binding != {
        "request_id": request.get("request_id"),
        "request_digest": request.get("request_digest"),
        "context_digest": compiled.get("context_digest"),
    }:
        raise S3EvidenceRoleCanaryError("s3_evidence_canary_request_binding_invalid")
    if (
        admission.get("execution_git_commit") != values["execution_git_commit"]
        or admission.get("runner_sha256") != values["runner_sha256"]
        or admission.get("context_source_sha256") != values["context_source_sha256"]
        or admission.get("policy_sha256") != values["policy_sha256"]
    ):
        raise S3EvidenceRoleCanaryError("s3_evidence_canary_execution_binding_invalid")
    if _time(values["observed_at"]) > _time(str(admission.get("expires_at") or "")):
        raise S3EvidenceRoleCanaryError("s3_evidence_canary_expired")
    _assert_provider_budget(
        provider=admission.get("provider") or {},
        budget=admission.get("budget") or {},
        credential_present=admission.get("credential_present") is True,
    )


def _provider_kwargs(*, compiled: Mapping[str, Any], admission: Mapping[str, Any]) -> dict[str, Any]:
    provider = admission["provider"]
    budget = admission["budget"]
    return {
        "llm_backend": provider["backend"],
        "base_url": provider["base_url"],
        "chat_completions_path": provider["chat_completions_path"],
        "model": provider["model"],
        "messages": [
            {"role": "system", "content": "You are a bounded financial-research evidence selector. Return one JSON object only. Use request-local aliases and enums. Select relevant observations without claiming they prove the thesis; local code assigns evidence roles. Do not add fields, prose, numbers, dates, identity, or explanations."},
            {"role": "user", "content": json.dumps(compiled["model_context"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))},
        ],
        "response_format": {"type": "json_object"},
        "api_key_env": provider["api_key_env"],
        "temperature": 0.0,
        "max_tokens": int(budget["maximum_output_tokens"]),
        "timeout_s": int(budget["timeout_seconds"]),
        "stream": False,
        "enable_thinking": False,
        "role": "fin013_s3_evidence_role_v2_canary",
        "profile": str(compiled["model_context"]["program_cell_id"]),
        "trace_tags": {"run_id": admission["run_id"], "request_id": compiled["request_id"], "context_digest": compiled["context_digest"]},
        "max_transport_attempts": 1,
    }


def _assert_provider_budget(*, provider: Mapping[str, Any], budget: Mapping[str, Any], credential_present: bool) -> None:
    if credential_present is not True:
        raise S3EvidenceRoleCanaryError("s3_evidence_canary_credential_missing")
    if (
        provider.get("backend") != "deepseek"
        or provider.get("model") != "deepseek-v4-pro"
        or provider.get("base_url") != "https://api.deepseek.com/beta"
        or provider.get("chat_completions_path") != "/chat/completions"
        or provider.get("api_key_env") != "DEEPSEEK_API_KEY"
    ):
        raise S3EvidenceRoleCanaryError("s3_evidence_canary_provider_invalid")
    if dict(budget) != {"maximum_provider_calls": 1, "retry_count": 0, "fallback_count": 0, "maximum_output_tokens": 900, "timeout_seconds": 180}:
        raise S3EvidenceRoleCanaryError("s3_evidence_canary_budget_invalid")


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise S3EvidenceRoleCanaryError("s3_evidence_canary_time_invalid") from exc
    if parsed.tzinfo is None:
        raise S3EvidenceRoleCanaryError("s3_evidence_canary_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _digest(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _git_id(value: Any) -> bool:
    text = str(value or "")
    return len(text) in {40, 64} and all(char in "0123456789abcdef" for char in text)


__all__ = ["S3EvidenceRoleCanaryError", "execute_evidence_role_canary", "issue_evidence_role_canary_admission"]
