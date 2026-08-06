from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s2_representative_node_program import (
    S2RepresentativeNodeError,
    consume_representative_specialist_output,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


ADMISSION_SCHEMA = "fin_ia_0_1_3_s2_02_natural_canary_admission_v1_0"
TERMINAL_SCHEMA = "fin_ia_0_1_3_s2_02_natural_canary_terminal_v1_0"
SCOPE = "FIN_0_1_3_S2_02_THREE_FAMILY_NATURAL_OUTPUT_CANARY"


class S2NaturalCanaryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


ProviderCall = Callable[..., Mapping[str, Any]]


def issue_canary_admission(
    *,
    execution_git_commit: str,
    runner_sha256: str,
    decision_sha256: str,
    policy_sha256: str,
    request_bindings: list[dict[str, str]],
    issued_at: str,
    expires_at: str,
    run_nonce: str,
    credential_present: bool,
    provider: Mapping[str, Any],
    budget: Mapping[str, Any],
) -> dict[str, Any]:
    if len(request_bindings) != 3 or len(
        {row.get("request_id") for row in request_bindings}
    ) != 3:
        raise S2NaturalCanaryError("canary_admission_request_surface_invalid")
    if not _is_git_object_id(execution_git_commit):
        raise S2NaturalCanaryError("canary_admission_git_commit_invalid")
    for value, code in (
        (runner_sha256, "canary_admission_runner_sha_invalid"),
        (decision_sha256, "canary_admission_decision_sha_invalid"),
        (policy_sha256, "canary_admission_policy_sha_invalid"),
    ):
        if not _is_digest(value):
            raise S2NaturalCanaryError(code)
    if credential_present is not True:
        raise S2NaturalCanaryError("canary_admission_credential_missing")
    if (
        provider.get("backend") != "deepseek"
        or provider.get("model") != "deepseek-v4-pro"
        or provider.get("api_key_env") != "DEEPSEEK_API_KEY"
        or provider.get("base_url") != "https://api.deepseek.com/beta"
        or provider.get("chat_completions_path") != "/chat/completions"
    ):
        raise S2NaturalCanaryError("canary_admission_provider_route_invalid")
    expected_budget = {
        "maximum_provider_calls": 3,
        "maximum_calls_per_family": 1,
        "retry_count": 0,
        "fallback_count": 0,
        "maximum_output_tokens_per_call": 900,
        "timeout_seconds_per_call": 180,
    }
    if dict(budget) != expected_budget:
        raise S2NaturalCanaryError("canary_admission_budget_invalid")
    issued = _parse_time(issued_at)
    expires = _parse_time(expires_at)
    if expires <= issued:
        raise S2NaturalCanaryError("canary_admission_expiry_invalid")
    run_id = "fin013_s2_02_natural_canary_" + canonical_digest(
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
        "decision_sha256": decision_sha256,
        "policy_sha256": policy_sha256,
        "request_bindings": deepcopy(request_bindings),
        "provider": deepcopy(dict(provider)),
        "budget": deepcopy(dict(budget)),
        "credential_present": True,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "run_nonce_digest": hashlib.sha256(run_nonce.encode("utf-8")).hexdigest(),
        "state": "issued_unconsumed",
    }
    return {**body, "admission_digest": canonical_digest(body)}


def validate_canary_admission(
    admission: Mapping[str, Any],
    *,
    execution_git_commit: str,
    runner_sha256: str,
    decision_sha256: str,
    policy_sha256: str,
    requests: Mapping[str, Mapping[str, Any]],
    observed_at: str,
) -> None:
    body = {
        key: deepcopy(value)
        for key, value in admission.items()
        if key != "admission_digest"
    }
    if (
        admission.get("schema_version") != ADMISSION_SCHEMA
        or admission.get("scope") != SCOPE
        or admission.get("state") != "issued_unconsumed"
        or admission.get("admission_digest") != canonical_digest(body)
    ):
        raise S2NaturalCanaryError("canary_admission_digest_or_state_invalid")
    bindings = admission.get("request_bindings") or []
    if len(bindings) != 3:
        raise S2NaturalCanaryError("canary_admission_request_surface_invalid")
    for binding in bindings:
        request = requests.get(str(binding.get("request_id") or ""))
        if request is None or binding.get("request_digest") != request.get(
            "request_digest"
        ):
            raise S2NaturalCanaryError("canary_admission_request_binding_invalid")
    expected = (
        execution_git_commit,
        runner_sha256,
        decision_sha256,
        policy_sha256,
    )
    observed = (
        admission.get("execution_git_commit"),
        admission.get("runner_sha256"),
        admission.get("decision_sha256"),
        admission.get("policy_sha256"),
    )
    if observed != expected:
        raise S2NaturalCanaryError("canary_admission_execution_binding_invalid")
    if _parse_time(observed_at) > _parse_time(str(admission.get("expires_at") or "")):
        raise S2NaturalCanaryError("canary_admission_expired")
    if admission.get("credential_present") is not True:
        raise S2NaturalCanaryError("canary_admission_credential_missing")


def execute_natural_canary(
    *,
    admission: Mapping[str, Any],
    requests: Mapping[str, Mapping[str, Any]],
    execution_git_commit: str,
    runner_sha256: str,
    decision_sha256: str,
    policy_sha256: str,
    runtime_root: Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    provider_call: ProviderCall,
    observed_at: str,
) -> dict[str, Any]:
    validate_canary_admission(
        admission,
        execution_git_commit=execution_git_commit,
        runner_sha256=runner_sha256,
        decision_sha256=decision_sha256,
        policy_sha256=policy_sha256,
        requests=requests,
        observed_at=observed_at,
    )
    root = runtime_root.resolve()
    ledger_path = shared_ledger.path.resolve()
    if ledger_path == root or root in ledger_path.parents:
        raise S2NaturalCanaryError("canary_shared_ledger_inside_runtime_root")
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
    rows: list[dict[str, Any]] = []
    failure_code: str | None = None
    provider = admission["provider"]
    budget = admission["budget"]
    for index, binding in enumerate(admission["request_bindings"], start=1):
        request = requests[str(binding["request_id"])]
        kwargs = _provider_kwargs(
            request=request,
            provider=provider,
            budget=budget,
            run_id=str(admission["run_id"]),
        )
        result = dict(provider_call(**kwargs))
        capture = {
            "schema_version": "fin_ia_0_1_3_s2_02_provider_capture_v1_0",
            "call_index": index,
            "request_id": request["request_id"],
            "request_digest": request["request_digest"],
            "provider_request": {
                key: deepcopy(value)
                for key, value in kwargs.items()
                if key != "api_key_env"
            },
            "gateway_result": result,
        }
        capture_digest = canonical_digest(capture)
        capture_path = captures / f"{index:02d}_{capture_digest}.json"
        _write_exclusive(capture_path, capture)
        row: dict[str, Any] = {
            "request_id": request["request_id"],
            "request_digest": request["request_digest"],
            "capture_digest": capture_digest,
            "capture_ref": capture_path.relative_to(root).as_posix(),
            "gateway_status": result.get("status"),
            "finish_reason": result.get("finish_reason"),
            "usage": {
                "input_tokens": int(result.get("input_tokens") or 0),
                "output_tokens": int(result.get("output_tokens") or 0),
                "total_tokens": int(result.get("total_tokens") or 0),
                "transport_attempt_count": int(
                    result.get("transport_attempt_count") or 0
                ),
            },
        }
        if result.get("status") != "ok":
            failure_code = "canary_provider_transport_or_status_failure"
        else:
            try:
                output = json.loads(str(result.get("content") or ""))
                if not isinstance(output, Mapping):
                    raise ValueError("output_not_object")
                claim = consume_representative_specialist_output(
                    request=request,
                    provider_output=output,
                )
                rubric = _score_output(output=output, claim=claim)
                row.update(
                    {
                        "provider_output": deepcopy(dict(output)),
                        "provider_output_digest": canonical_digest(output),
                        "claim": claim,
                        "rubric": rubric,
                        "status": "pass" if rubric["pass"] else "fail",
                    }
                )
                if not rubric["pass"]:
                    failure_code = "canary_preregistered_rubric_failed"
            except (json.JSONDecodeError, ValueError):
                failure_code = "canary_provider_output_json_invalid"
            except (S2RepresentativeNodeError, KeyError) as exc:
                failure_code = "canary_provider_output_contract_invalid:" + str(
                    getattr(exc, "code", type(exc).__name__)
                )
        if failure_code:
            row["status"] = "terminal_failed"
            row["failure_code"] = failure_code
        rows.append(row)
        if failure_code:
            break

    terminal_status = (
        "terminal_succeeded_exact_once"
        if failure_code is None and len(rows) == 3
        else "terminal_failed_no_retry"
    )
    terminal_body = {
        "schema_version": TERMINAL_SCHEMA,
        "admission_digest": admission["admission_digest"],
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "status": terminal_status,
        "terminal_phase": "natural_output_canary",
        "terminal_code": failure_code or "three_family_canary_pass",
        "family_results": rows,
        "completed_calls": len(rows),
        "skipped_request_ids": [
            row["request_id"]
            for row in admission["request_bindings"][len(rows) :]
        ],
        "retry_count": 0,
        "fallback_count": 0,
        "business_artifact_promotions": 0,
        "observed_at": observed_at,
        "reservation_digest": receipt.reservation_digest,
    }
    terminal = {
        **terminal_body,
        "terminal_result_digest": canonical_digest(terminal_body),
    }
    _write_exclusive(root / "terminal_result.json", terminal)
    final_receipt = shared_ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status=terminal_status,
        terminal_phase="natural_output_canary",
        terminal_code=str(terminal["terminal_code"]),
        terminal_result_digest=str(terminal["terminal_result_digest"]),
        finalized_at=observed_at,
    )
    return {
        **terminal,
        "shared_admission_receipt": final_receipt.as_dict(),
    }


def _provider_kwargs(
    *,
    request: Mapping[str, Any],
    provider: Mapping[str, Any],
    budget: Mapping[str, Any],
    run_id: str,
) -> dict[str, Any]:
    contract = request["model_visible_request"]["provider_output_contract"]
    system = (
        "You are a bounded financial-research judgment selector. Return one JSON "
        "object only. Use only request-local aliases and enum values. Do not add "
        "fields, prose, markdown, numbers, dates, identities, or explanations."
    )
    user = json.dumps(
        request["model_visible_request"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "llm_backend": provider["backend"],
        "base_url": provider["base_url"],
        "chat_completions_path": provider["chat_completions_path"],
        "model": provider["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "api_key_env": provider["api_key_env"],
        "temperature": 0.0,
        "max_tokens": int(budget["maximum_output_tokens_per_call"]),
        "timeout_s": int(budget["timeout_seconds_per_call"]),
        "stream": False,
        "enable_thinking": False,
        "role": "fin013_s2_representative_judgment_selector",
        "profile": str(request["program_cell_id"]),
        "trace_tags": {
            "run_id": run_id,
            "request_id": request["request_id"],
            "request_digest": request["request_digest"],
            "contract_ref": contract["contract_ref"],
        },
        "max_transport_attempts": 1,
    }


def _score_output(
    *, output: Mapping[str, Any], claim: Mapping[str, Any]
) -> dict[str, Any]:
    scores = {
        "contract_adherence": 2,
        "evidence_selection_relevance": 2
        if claim.get("support_evidence") or claim.get("typed_gaps")
        else 0,
        "epistemic_consistency": 2
        if not (
            output.get("epistemic_state") == "cannot_infer"
            and output.get("support_aliases")
        )
        else 0,
        "company_specific_mechanism_selection": 2
        if claim.get("mechanism_atom")
        else 0,
        "what_would_change_actionability": 2
        if claim.get("what_would_change")
        else 0,
    }
    total = sum(scores.values())
    return {
        "scores": scores,
        "total": total,
        "threshold": 8,
        "contract_adherence_minimum": 2,
        "pass": total >= 8 and scores["contract_adherence"] == 2,
    }


def _write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    data = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise S2NaturalCanaryError("canary_time_invalid") from exc
    if parsed.tzinfo is None:
        raise S2NaturalCanaryError("canary_time_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _is_digest(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _is_git_object_id(value: Any) -> bool:
    text = str(value or "")
    return len(text) in {40, 64} and all(
        char in "0123456789abcdef" for char in text
    )


__all__ = [
    "ADMISSION_SCHEMA",
    "SCOPE",
    "S2NaturalCanaryError",
    "execute_natural_canary",
    "issue_canary_admission",
    "validate_canary_admission",
]
