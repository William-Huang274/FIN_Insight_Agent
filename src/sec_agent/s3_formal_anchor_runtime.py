from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s2_context_yield_program import S2ContextYieldError, validate_compact_provider_output
from sec_agent.s2_representative_node_program import (
    S2RepresentativeNodeError,
    consume_representative_specialist_output,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


ADMISSION_SCHEMA = "fin_ia_0_1_3_s3_formal_anchor_admission_v1_0"
TERMINAL_SCHEMA = "fin_ia_0_1_3_s3_formal_anchor_terminal_v1_0"
SCOPE = "FIN_0_1_3_S3_FORMAL_ANCHOR_NINE_SPECIALIST_EXACT_ONCE"
REQUEST_COUNT = 9


class S3FormalAnchorRuntimeError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


ProviderCall = Callable[..., Mapping[str, Any]]


def issue_formal_anchor_admission(
    *,
    execution_git_commit: str,
    runner_sha256: str,
    s2_decision_sha256: str,
    context_program_sha256: str,
    quality_gate_sha256: str,
    policy_sha256: str,
    request_bindings: list[dict[str, str]],
    issued_at: str,
    expires_at: str,
    run_nonce: str,
    credential_present: bool,
    provider: Mapping[str, Any],
    budget: Mapping[str, Any],
) -> dict[str, Any]:
    if len(request_bindings) != REQUEST_COUNT or len({row.get("request_id") for row in request_bindings}) != REQUEST_COUNT:
        raise S3FormalAnchorRuntimeError("s3_formal_admission_request_surface_invalid")
    if not _git_id(execution_git_commit):
        raise S3FormalAnchorRuntimeError("s3_formal_admission_git_invalid")
    for value in (runner_sha256, s2_decision_sha256, context_program_sha256, quality_gate_sha256, policy_sha256):
        if not _digest(value):
            raise S3FormalAnchorRuntimeError("s3_formal_admission_binding_digest_invalid")
    _assert_provider_budget(provider=provider, budget=budget, credential_present=credential_present)
    if _time(expires_at) <= _time(issued_at):
        raise S3FormalAnchorRuntimeError("s3_formal_admission_expiry_invalid")
    run_id = "fin013_s3_formal_anchor_" + canonical_digest({"nonce": run_nonce, "git": execution_git_commit})[:20]
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "admission_id": "admission::" + run_id,
        "scope": SCOPE,
        "run_id": run_id,
        "attempt_id": run_id + "::attempt_1",
        "runtime_identity": run_id + "::runtime_1",
        "execution_git_commit": execution_git_commit,
        "runner_sha256": runner_sha256,
        "s2_decision_sha256": s2_decision_sha256,
        "context_program_sha256": context_program_sha256,
        "quality_gate_sha256": quality_gate_sha256,
        "policy_sha256": policy_sha256,
        "request_bindings": deepcopy(request_bindings),
        "provider": deepcopy(dict(provider)),
        "budget": deepcopy(dict(budget)),
        "credential_present": True,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "run_nonce_digest": canonical_digest(run_nonce),
        "state": "issued_unconsumed",
    }
    return {**body, "admission_digest": canonical_digest(body)}


def validate_formal_anchor_admission(
    admission: Mapping[str, Any],
    *,
    execution_git_commit: str,
    runner_sha256: str,
    s2_decision_sha256: str,
    context_program_sha256: str,
    quality_gate_sha256: str,
    policy_sha256: str,
    requests: Mapping[str, Mapping[str, Any]],
    contexts: Mapping[str, Mapping[str, Any]],
    observed_at: str,
) -> None:
    body = {key: deepcopy(value) for key, value in admission.items() if key != "admission_digest"}
    if (
        admission.get("schema_version") != ADMISSION_SCHEMA
        or admission.get("scope") != SCOPE
        or admission.get("state") != "issued_unconsumed"
        or admission.get("admission_digest") != canonical_digest(body)
    ):
        raise S3FormalAnchorRuntimeError("s3_formal_admission_digest_or_state_invalid")
    expected_bindings = []
    for request_id in requests:
        request = requests[request_id]
        context = contexts.get(request_id)
        if context is None or context.get("source_request_digest") != request.get("request_digest"):
            raise S3FormalAnchorRuntimeError("s3_formal_context_request_binding_invalid")
        expected_bindings.append(
            {
                "request_id": request_id,
                "request_digest": request["request_digest"],
                "context_digest": context["context_digest"],
            }
        )
    if admission.get("request_bindings") != expected_bindings:
        raise S3FormalAnchorRuntimeError("s3_formal_admission_request_binding_invalid")
    expected = (execution_git_commit, runner_sha256, s2_decision_sha256, context_program_sha256, quality_gate_sha256, policy_sha256)
    actual = tuple(admission.get(key) for key in (
        "execution_git_commit", "runner_sha256", "s2_decision_sha256", "context_program_sha256", "quality_gate_sha256", "policy_sha256"
    ))
    if actual != expected:
        raise S3FormalAnchorRuntimeError("s3_formal_admission_execution_binding_invalid")
    if _time(observed_at) > _time(str(admission.get("expires_at") or "")):
        raise S3FormalAnchorRuntimeError("s3_formal_admission_expired")
    _assert_provider_budget(
        provider=admission.get("provider") or {},
        budget=admission.get("budget") or {},
        credential_present=admission.get("credential_present") is True,
    )


def execute_formal_anchor(
    *,
    admission: Mapping[str, Any],
    requests: Mapping[str, Mapping[str, Any]],
    contexts: Mapping[str, Mapping[str, Any]],
    execution_git_commit: str,
    runner_sha256: str,
    s2_decision_sha256: str,
    context_program_sha256: str,
    quality_gate_sha256: str,
    policy_sha256: str,
    runtime_root: Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    provider_call: ProviderCall,
    observed_at: str,
) -> dict[str, Any]:
    validate_formal_anchor_admission(
        admission,
        execution_git_commit=execution_git_commit,
        runner_sha256=runner_sha256,
        s2_decision_sha256=s2_decision_sha256,
        context_program_sha256=context_program_sha256,
        quality_gate_sha256=quality_gate_sha256,
        policy_sha256=policy_sha256,
        requests=requests,
        contexts=contexts,
        observed_at=observed_at,
    )
    root = runtime_root.resolve()
    ledger_path = shared_ledger.path.resolve()
    if ledger_path == root or root in ledger_path.parents:
        raise S3FormalAnchorRuntimeError("s3_formal_shared_ledger_inside_runtime_root")
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
    rows = []
    failure_code: str | None = None
    for index, binding in enumerate(admission["request_bindings"], start=1):
        request_id = str(binding["request_id"])
        request = requests[request_id]
        context = contexts[request_id]
        kwargs = _provider_kwargs(context=context, admission=admission)
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
            "schema_version": "fin_ia_0_1_3_s3_formal_anchor_capture_v1_0",
            "call_index": index,
            "request_id": request_id,
            "request_digest": request["request_digest"],
            "context_digest": context["context_digest"],
            "provider_request": {key: deepcopy(value) for key, value in kwargs.items() if key != "api_key_env"},
            "gateway_result": result,
        }
        capture_digest = canonical_digest(capture)
        _write(root / "captures" / f"{index:02d}_{capture_digest}.json", capture)
        row: dict[str, Any] = {
            "request_id": request_id,
            "request_digest": request["request_digest"],
            "context_digest": context["context_digest"],
            "case_key": request["case_key"],
            "program_cell_id": request["program_cell_id"],
            "capture_digest": capture_digest,
            "capture_ref": f"captures/{index:02d}_{capture_digest}.json",
            "gateway_status": result.get("status"),
            "finish_reason": result.get("finish_reason"),
            "usage": {
                "input_tokens": int(result.get("input_tokens") or 0),
                "output_tokens": int(result.get("output_tokens") or 0),
                "total_tokens": int(result.get("total_tokens") or 0),
                "transport_attempt_count": int(result.get("transport_attempt_count") or 0),
            },
        }
        if result.get("status") != "ok":
            failure_code = "s3_formal_provider_transport_or_status_failure"
        else:
            try:
                output = json.loads(str(result.get("content") or ""))
                if not isinstance(output, Mapping):
                    raise ValueError("output_not_object")
                validate_compact_provider_output(output, compiled=context)
                claim = consume_representative_specialist_output(request=request, provider_output=output)
                row.update(
                    {
                        "provider_output": deepcopy(dict(output)),
                        "provider_output_digest": canonical_digest(output),
                        "claim_digest": claim["claim_digest"],
                        "status": "passed",
                    }
                )
            except (S2RepresentativeNodeError, S2ContextYieldError, KeyError) as exc:
                failure_code = "s3_formal_provider_output_contract_invalid:" + str(getattr(exc, "code", type(exc).__name__))
            except (json.JSONDecodeError, ValueError):
                failure_code = "s3_formal_provider_output_json_invalid"
        if failure_code:
            row["status"] = "terminal_failed"
            row["failure_code"] = failure_code
        rows.append(row)
        if failure_code:
            break
    status = "terminal_succeeded_exact_once" if failure_code is None and len(rows) == REQUEST_COUNT else "terminal_failed_no_retry"
    terminal_body = {
        "schema_version": TERMINAL_SCHEMA,
        "admission_digest": admission["admission_digest"],
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "status": status,
        "terminal_phase": "s3_formal_anchor_nine_specialist",
        "terminal_code": failure_code or "nine_specialist_exact_once_pass",
        "family_results": rows,
        "completed_calls": len(rows),
        "skipped_request_ids": [row["request_id"] for row in admission["request_bindings"][len(rows):]],
        "retry_count": 0,
        "fallback_count": 0,
        "business_artifact_promotions": 0,
        "observed_at": observed_at,
        "reservation_digest": receipt.reservation_digest,
    }
    terminal = {**terminal_body, "terminal_result_digest": canonical_digest(terminal_body)}
    record = {**terminal, "record_digest": canonical_digest(terminal)}
    _write(root / "terminal_result.json", record)
    final_receipt = shared_ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status=status,
        terminal_phase="s3_formal_anchor_nine_specialist",
        terminal_code=str(record["terminal_code"]),
        terminal_result_digest=str(record["terminal_result_digest"]),
        finalized_at=observed_at,
    )
    return {**record, "shared_admission_receipt": final_receipt.as_dict()}


def _provider_kwargs(*, context: Mapping[str, Any], admission: Mapping[str, Any]) -> dict[str, Any]:
    provider = admission["provider"]
    budget = admission["budget"]
    return {
        "llm_backend": provider["backend"],
        "base_url": provider["base_url"],
        "chat_completions_path": provider["chat_completions_path"],
        "model": provider["model"],
        "messages": [
            {"role": "system", "content": "You are a bounded financial-research judgment selector. Return one JSON object only. Use only request-local aliases and enum values. Do not add fields, prose, markdown, numbers, dates, identities, or explanations."},
            {"role": "user", "content": json.dumps(context["model_context"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))},
        ],
        "response_format": {"type": "json_object"},
        "api_key_env": provider["api_key_env"],
        "temperature": 0.0,
        "max_tokens": int(budget["maximum_output_tokens_per_call"]),
        "timeout_s": int(budget["timeout_seconds_per_call"]),
        "stream": False,
        "enable_thinking": False,
        "role": "fin013_s3_formal_anchor_judgment_selector",
        "profile": str(context["model_context"]["program_cell_id"]),
        "trace_tags": {
            "run_id": admission["run_id"],
            "request_id": context["request_id"],
            "context_digest": context["context_digest"],
        },
        "max_transport_attempts": 1,
    }


def _assert_provider_budget(*, provider: Mapping[str, Any], budget: Mapping[str, Any], credential_present: bool) -> None:
    if credential_present is not True:
        raise S3FormalAnchorRuntimeError("s3_formal_credential_missing")
    if (
        provider.get("backend") != "deepseek"
        or provider.get("model") != "deepseek-v4-pro"
        or provider.get("base_url") != "https://api.deepseek.com/beta"
        or provider.get("chat_completions_path") != "/chat/completions"
        or provider.get("api_key_env") != "DEEPSEEK_API_KEY"
    ):
        raise S3FormalAnchorRuntimeError("s3_formal_provider_invalid")
    if dict(budget) != {
        "maximum_provider_calls": 9,
        "maximum_calls_per_request": 1,
        "retry_count": 0,
        "fallback_count": 0,
        "maximum_output_tokens_per_call": 900,
        "timeout_seconds_per_call": 180,
    }:
        raise S3FormalAnchorRuntimeError("s3_formal_budget_invalid")


def _write(path: Path, value: Mapping[str, Any]) -> None:
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise S3FormalAnchorRuntimeError("s3_formal_time_invalid") from exc
    if parsed.tzinfo is None:
        raise S3FormalAnchorRuntimeError("s3_formal_time_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _digest(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _git_id(value: Any) -> bool:
    text = str(value or "")
    return len(text) in {40, 64} and all(char in "0123456789abcdef" for char in text)
