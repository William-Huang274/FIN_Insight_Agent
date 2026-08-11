from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s3_dell_value_profit_repair_canary import _normalized_text_sha256
from sec_agent.s3_dell_value_profit_repair_canary_live import (
    build_no_retry_provider_call,
    credential_presence_only,
)
from sec_agent.s3_small_judgment_atom_projection import (
    S3SmallJudgmentAtomProjectionError,
    project_small_judgment_output,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


LIVE_SCOPE = "FIN_0_1_3_S3_DELL_VALUE_PROFIT_SMALL_JUDGMENT_ATOM_CANARY_LIVE"
LIVE_AUTHORITY_SCHEMA = "fin_ia_0_1_3_s3_small_judgment_atom_live_authority_v1_0"
LIVE_ADMISSION_SCHEMA = "fin_ia_0_1_3_s3_small_judgment_atom_live_admission_v1_0"
LIVE_ISSUANCE_SCHEMA = "fin_ia_0_1_3_s3_small_judgment_atom_live_issuance_v1_0"
LIVE_EXECUTION_AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s3_small_judgment_atom_live_execution_authority_v1_0"
)
LIVE_CAPTURE_SCHEMA = "fin_ia_0_1_3_s3_small_judgment_atom_live_capture_v1_0"
LIVE_TERMINAL_SCHEMA = "fin_ia_0_1_3_s3_small_judgment_atom_live_terminal_v1_0"
ProviderCall = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class S3SmallJudgmentAtomLiveError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S3SmallJudgmentAtomLiveError(code)


def _parse_time(value: Any, code: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise S3SmallJudgmentAtomLiveError(code) from exc
    _require(parsed.tzinfo is not None, code)
    return parsed.astimezone(timezone.utc)


def _decision_valid(
    decision: Mapping[str, Any], *, clean_proof: Mapping[str, Any]
) -> bool:
    body = {
        key: value for key, value in decision.items() if key != "decision_digest"
    }
    binding = dict(decision.get("immutable_basis", {}).get("clean_proof") or {})
    authority = dict(decision.get("authority_boundary") or {})
    cost = dict(decision.get("cost") or {})
    return (
        decision.get("decision_digest") == canonical_digest(body)
        and decision.get("status")
        == (
            "decision_complete_authorize_successor_live_path_and_one_fresh_"
            "admission_execution_separate"
        )
        and binding.get("expected_result_digest") == clean_proof.get("result_digest")
        and authority.get("this_decision_authorizes_one_fresh_admission_issuance")
        is True
        and authority.get("this_decision_authorizes_provider_execution") is False
        and cost.get("provider_calls_maximum") == 1
        and cost.get("model_calls_maximum") == 1
        and cost.get("maximum_output_tokens") == 1200
        and all(cost.get(key) == 0 for key in ("source_calls", "retries", "fallbacks"))
    )


def _proof_valid(clean_proof: Mapping[str, Any]) -> bool:
    body = {
        key: value for key, value in clean_proof.items() if key != "result_digest"
    }
    calls = dict(clean_proof.get("observed_calls") or {})
    return (
        clean_proof.get("result_digest") == canonical_digest(body)
        and clean_proof.get("status")
        == "pass_two_clean_archives_replay_projection_and_mutation_zero_external_call"
        and clean_proof.get("clean_git_archives") == 2
        and clean_proof.get("fresh_python_processes") == 2
        and clean_proof.get("workers_byte_equivalent") is True
        and all(
            calls.get(key) == 0
            for key in (
                "model_calls",
                "provider_calls",
                "network_calls",
                "source_calls",
                "retries",
            )
        )
    )


def _validate_source_bindings(
    bindings: Sequence[Mapping[str, Any]], *, repo_root: Path
) -> None:
    _require(bool(bindings), "s3_small_atom_live_source_bindings_empty")
    refs: list[str] = []
    for binding in bindings:
        ref = str(binding.get("ref") or "")
        expected = str(binding.get("normalized_text_sha256") or "")
        path = (repo_root / ref).resolve()
        _require(
            bool(ref)
            and path.is_file()
            and _normalized_text_sha256(path) == expected,
            "s3_small_atom_live_source_binding_drift",
        )
        refs.append(ref)
    _require(len(refs) == len(set(refs)), "s3_small_atom_live_source_binding_duplicate")


def issue_successor_live_admission(
    *,
    decision: Mapping[str, Any],
    clean_proof: Mapping[str, Any],
    material: Mapping[str, Any],
    implementation_commit: str,
    source_bindings: Sequence[Mapping[str, Any]],
    project_os_preflight: Mapping[str, Any],
    credential_preflight: Mapping[str, Any],
    issued_at: str,
    expires_at: str,
    run_nonce: str,
    user_authority: str,
) -> dict[str, Any]:
    _require(_proof_valid(clean_proof), "s3_small_atom_live_clean_proof_invalid")
    _require(
        _decision_valid(decision, clean_proof=clean_proof),
        "s3_small_atom_live_decision_invalid",
    )
    _require(
        project_os_preflight.get("status") == "pass"
        and project_os_preflight.get("run_scope") == LIVE_SCOPE
        and not project_os_preflight.get("errors"),
        "s3_small_atom_live_project_os_preflight_invalid",
    )
    _require(
        credential_preflight.get("credential_present") is True
        and credential_preflight.get("credential_value_read_output_or_persisted")
        is False,
        "s3_small_atom_live_credential_preflight_invalid",
    )
    issued = _parse_time(issued_at, "s3_small_atom_live_issued_at_invalid")
    expires = _parse_time(expires_at, "s3_small_atom_live_expires_at_invalid")
    _require(expires > issued, "s3_small_atom_live_expiry_invalid")
    _require(
        len(implementation_commit) == 40
        and len(run_nonce) == 32
        and bool(user_authority.strip()),
        "s3_small_atom_live_issuance_identity_invalid",
    )
    compiled = dict(material["compiled_input"])
    request = dict(material["provider_request"])
    profile = dict(material["predecessor"]["profile"])
    cost = dict(decision["cost"])
    source_rows = [deepcopy(dict(row)) for row in source_bindings]
    run_id = "fin013_s3_small_atom_" + canonical_digest(
        {
            "nonce": run_nonce,
            "input": compiled["compiled_input_digest"],
            "request": request["request_digest"],
            "commit": implementation_commit,
        }
    )[:20]
    attempt_id = f"attempt_{run_id}_r1"
    authority_body = {
        "schema_version": LIVE_AUTHORITY_SCHEMA,
        "status": "issued_live_path_execution_separate",
        "run_scope": LIVE_SCOPE,
        "implementation_commit": implementation_commit,
        "decision_digest": decision["decision_digest"],
        "clean_proof_digest": clean_proof["result_digest"],
        "compiled_input_digest": compiled["compiled_input_digest"],
        "request_digest": request["request_digest"],
        "source_bindings": source_rows,
        "provider": profile["provider"],
        "model": profile["model"],
        "provider_calls_maximum": cost["provider_calls_maximum"],
        "model_calls_maximum": cost["model_calls_maximum"],
        "maximum_output_tokens": cost["maximum_output_tokens"],
        "source_calls": 0,
        "network_tool_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "business_artifact_promotion": False,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "user_authority": user_authority,
        "execute_provider_call": False,
    }
    authority = {
        **authority_body,
        "authority_digest": canonical_digest(authority_body),
    }
    admission_body = {
        "schema_version": LIVE_ADMISSION_SCHEMA,
        "admission_id": f"admission::{run_id}::{attempt_id}",
        "run_scope": LIVE_SCOPE,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "case_key": compiled["case_key"],
        "node_id": compiled["node_id"],
        "compiled_input_digest": compiled["compiled_input_digest"],
        "request_digest": request["request_digest"],
        "profile_ref": profile["profile_ref"],
        "provider": profile["provider"],
        "model": profile["model"],
        "provider_calls_maximum": 1,
        "model_calls_maximum": 1,
        "source_calls": 0,
        "network_tool_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "execution_authorized": False,
        "business_artifact_promotion": False,
        "authority_digest": authority["authority_digest"],
    }
    admission = {
        **admission_body,
        "admission_digest": canonical_digest(admission_body),
    }
    issuance_body = {
        "schema_version": LIVE_ISSUANCE_SCHEMA,
        "status": "issued_unconsumed_execution_not_authorized",
        "authority": authority,
        "admission": admission,
        "credential_preflight": deepcopy(dict(credential_preflight)),
        "project_os_preflight": {
            "status": project_os_preflight["status"],
            "run_scope": project_os_preflight["run_scope"],
            "errors": list(project_os_preflight.get("errors") or ()),
        },
        "observed_counts": {
            "provider_calls": 0,
            "model_calls": 0,
            "source_calls": 0,
            "network_tool_calls": 0,
            "retries": 0,
            "fallbacks": 0,
        },
        "business_artifact_promotion": False,
    }
    return {**issuance_body, "issuance_digest": canonical_digest(issuance_body)}


def validate_successor_live_issuance(
    issuance: Mapping[str, Any],
    *,
    decision: Mapping[str, Any],
    clean_proof: Mapping[str, Any],
    material: Mapping[str, Any],
    project_os_preflight: Mapping[str, Any],
    repo_root: str | Path,
    observed_at: str,
) -> None:
    body = {
        key: value for key, value in issuance.items() if key != "issuance_digest"
    }
    _require(
        issuance.get("schema_version") == LIVE_ISSUANCE_SCHEMA
        and issuance.get("issuance_digest") == canonical_digest(body)
        and issuance.get("status") == "issued_unconsumed_execution_not_authorized",
        "s3_small_atom_live_issuance_invalid",
    )
    _require(_proof_valid(clean_proof), "s3_small_atom_live_clean_proof_invalid")
    _require(
        _decision_valid(decision, clean_proof=clean_proof),
        "s3_small_atom_live_decision_invalid",
    )
    authority = dict(issuance.get("authority") or {})
    authority_body = {
        key: value for key, value in authority.items() if key != "authority_digest"
    }
    admission = dict(issuance.get("admission") or {})
    admission_body = {
        key: value for key, value in admission.items() if key != "admission_digest"
    }
    compiled = dict(material["compiled_input"])
    request = dict(material["provider_request"])
    _require(
        authority.get("schema_version") == LIVE_AUTHORITY_SCHEMA
        and authority.get("authority_digest") == canonical_digest(authority_body)
        and authority.get("run_scope") == LIVE_SCOPE
        and authority.get("decision_digest") == decision.get("decision_digest")
        and authority.get("clean_proof_digest") == clean_proof.get("result_digest")
        and authority.get("compiled_input_digest")
        == compiled.get("compiled_input_digest")
        and authority.get("request_digest") == request.get("request_digest")
        and authority.get("execute_provider_call") is False,
        "s3_small_atom_live_authority_invalid",
    )
    _require(
        admission.get("schema_version") == LIVE_ADMISSION_SCHEMA
        and admission.get("admission_digest") == canonical_digest(admission_body)
        and admission.get("run_scope") == LIVE_SCOPE
        and admission.get("authority_digest") == authority.get("authority_digest")
        and admission.get("compiled_input_digest")
        == compiled.get("compiled_input_digest")
        and admission.get("request_digest") == request.get("request_digest")
        and admission.get("execution_authorized") is False
        and admission.get("business_artifact_promotion") is False,
        "s3_small_atom_live_admission_invalid",
    )
    _require(
        project_os_preflight.get("status") == "pass"
        and project_os_preflight.get("run_scope") == LIVE_SCOPE
        and not project_os_preflight.get("errors"),
        "s3_small_atom_live_project_os_preflight_invalid",
    )
    observed = _parse_time(observed_at, "s3_small_atom_live_observed_at_invalid")
    issued = _parse_time(admission.get("issued_at"), "s3_small_atom_live_issued_at_invalid")
    expires = _parse_time(
        admission.get("expires_at"), "s3_small_atom_live_expires_at_invalid"
    )
    _require(
        issued <= observed < expires,
        "s3_small_atom_live_admission_expired_or_not_yet_valid",
    )
    _validate_source_bindings(
        list(authority.get("source_bindings") or ()),
        repo_root=Path(repo_root).resolve(),
    )
    credential = dict(issuance.get("credential_preflight") or {})
    _require(
        credential.get("credential_present") is True
        and credential.get("credential_value_read_output_or_persisted") is False,
        "s3_small_atom_live_credential_preflight_invalid",
    )


def validate_successor_execution_authority(
    authority: Mapping[str, Any], *, issuance: Mapping[str, Any]
) -> None:
    body = {
        key: value
        for key, value in authority.items()
        if key != "execution_authority_digest"
    }
    _require(
        authority.get("schema_version") == LIVE_EXECUTION_AUTHORITY_SCHEMA
        and authority.get("execution_authority_digest") == canonical_digest(body)
        and authority.get("status")
        == "authorized_single_exact_once_successor_natural_canary_execution"
        and authority.get("issuance_digest") == issuance.get("issuance_digest")
        and authority.get("admission_digest")
        == issuance.get("admission", {}).get("admission_digest")
        and authority.get("execute_provider_call") is True
        and authority.get("provider_calls_maximum") == 1
        and authority.get("model_calls_maximum") == 1
        and authority.get("retries") == 0
        and authority.get("fallbacks") == 0
        and authority.get("business_artifact_promotion") is False,
        "s3_small_atom_live_execution_authority_invalid",
    )


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _terminalize(
    *,
    admission: Mapping[str, Any],
    request: Mapping[str, Any],
    capture: Mapping[str, Any],
    runtime_root: Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    status: str,
    phase: str,
    code: str,
    observed_at: str,
    output: Mapping[str, Any] | None,
    projection: Mapping[str, Any] | None,
    successor_program: Mapping[str, Any] | None,
) -> dict[str, Any]:
    body = {
        "schema_version": LIVE_TERMINAL_SCHEMA,
        "run_scope": admission["run_scope"],
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "case_key": admission["case_key"],
        "node_id": admission["node_id"],
        "status": status,
        "terminal_phase": phase,
        "terminal_code": code,
        "observed_counts": {
            "provider_calls": 1,
            "model_calls": 1,
            "source_calls": 0,
            "network_tool_calls": 0,
            "retries": 0,
            "fallbacks": 0,
        },
        "request_ref": "raw_model_only/calls/call_01/request.json",
        "request_digest": request["request_digest"],
        "capture_ref": "raw_model_only/calls/call_01/capture.json",
        "capture_digest": capture["capture_digest"],
        "parsed_output_ref": (
            "parsed/small_judgment_output.json"
            if output is not None
            and (runtime_root / "parsed/small_judgment_output.json").is_file()
            else None
        ),
        "validated_output_ref": (
            "validated/small_judgment_output.json"
            if projection is not None
            and (runtime_root / "validated/small_judgment_output.json").is_file()
            else None
        ),
        "projection_ref": (
            "validated/projection.json"
            if projection is not None
            and (runtime_root / "validated/projection.json").is_file()
            else None
        ),
        "output_digest": canonical_digest(output) if output is not None else None,
        "projection_digest": (
            projection.get("projection_digest") if projection is not None else None
        ),
        "successor_program_digest": (
            successor_program.get("program_digest")
            if successor_program is not None
            else None
        ),
        "business_artifact_promotion": False,
        "observed_at": observed_at,
    }
    terminal_digest = canonical_digest(body)
    terminal = {**body, "terminal_result_digest": terminal_digest}
    _atomic_json(runtime_root / "terminal.json", terminal)
    receipt = shared_ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status=status,
        terminal_phase=phase,
        terminal_code=code,
        terminal_result_digest=terminal_digest,
        finalized_at=observed_at,
    ).as_dict()
    public_body = {**terminal, "admission_consumption_receipt": receipt}
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _atomic_json(runtime_root / "terminal_with_receipt.json", public)
    return public


def execute_successor_live_canary(
    *,
    issuance: Mapping[str, Any],
    execution_authority: Mapping[str, Any],
    decision: Mapping[str, Any],
    clean_proof: Mapping[str, Any],
    material: Mapping[str, Any],
    project_os_preflight: Mapping[str, Any],
    repo_root: str | Path,
    provider_call: ProviderCall,
    runtime_root: str | Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    observed_at: str,
) -> dict[str, Any]:
    validate_successor_live_issuance(
        issuance,
        decision=decision,
        clean_proof=clean_proof,
        material=material,
        project_os_preflight=project_os_preflight,
        repo_root=repo_root,
        observed_at=observed_at,
    )
    validate_successor_execution_authority(
        execution_authority, issuance=issuance
    )
    admission = dict(issuance["admission"])
    root = Path(runtime_root).resolve()
    _require(not root.exists(), "s3_small_atom_live_attempt_root_exists")
    shared_ledger.reserve(
        admission_digest=str(admission["admission_digest"]),
        admission_id=str(admission["admission_id"]),
        scope=str(admission["run_scope"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        runtime_identity=(
            "fin_0_1_3.S3.small_judgment_atom_deterministic_cell_projection:live:v1"
        ),
        reserved_at=observed_at,
    )
    request = deepcopy(dict(material["provider_request"]))
    call_root = root / "raw_model_only/calls/call_01"
    _atomic_json(
        call_root / "request.json",
        {
            "schema_version": request["schema_version"],
            "observed_at": observed_at,
            "request": request,
            "request_digest": request["request_digest"],
        },
    )
    try:
        response = dict(provider_call(request))
    except Exception as exc:
        response = {
            "status": "provider_error",
            "failure_reason": f"{type(exc).__name__}: {str(exc)[:1000]}",
            "content": "",
            "finish_reason": None,
        }
    capture_body = {
        "schema_version": LIVE_CAPTURE_SCHEMA,
        "call_id": "call_01",
        "request_digest": request["request_digest"],
        "request": request,
        "provider_response": deepcopy(response),
        "observed_at": observed_at,
    }
    capture = {**capture_body, "capture_digest": canonical_digest(capture_body)}
    _atomic_json(call_root / "capture.json", capture)

    terminal_args = {
        "admission": admission,
        "request": request,
        "capture": capture,
        "runtime_root": root,
        "shared_ledger": shared_ledger,
        "observed_at": observed_at,
    }
    if str(response.get("status") or "") != "ok":
        return _terminalize(
            **terminal_args,
            status="failed",
            phase="provider_transport",
            code="s3_small_atom_live_provider_failure:"
            + str(response.get("status") or "unknown"),
            output=None,
            projection=None,
            successor_program=None,
        )
    finish_reason = str(response.get("finish_reason") or "").casefold()
    if finish_reason != "stop":
        return _terminalize(
            **terminal_args,
            status="failed",
            phase="provider_output",
            code=(
                "s3_small_atom_live_incomplete_finish_reason_length"
                if finish_reason == "length"
                else "s3_small_atom_live_finish_reason_invalid"
            ),
            output=None,
            projection=None,
            successor_program=None,
        )
    content = str(response.get("content") or "")
    if not content.strip():
        return _terminalize(
            **terminal_args,
            status="failed",
            phase="provider_output",
            code="s3_small_atom_live_empty_output",
            output=None,
            projection=None,
            successor_program=None,
        )
    try:
        output = json.loads(content)
    except json.JSONDecodeError:
        return _terminalize(
            **terminal_args,
            status="failed",
            phase="provider_output",
            code="s3_small_atom_live_invalid_json",
            output=None,
            projection=None,
            successor_program=None,
        )
    if not isinstance(output, dict):
        return _terminalize(
            **terminal_args,
            status="failed",
            phase="provider_output",
            code="s3_small_atom_live_json_object_required",
            output=None,
            projection=None,
            successor_program=None,
        )
    _atomic_json(root / "parsed/small_judgment_output.json", output)
    try:
        projected = project_small_judgment_output(
            output=output,
            material=material,
            capture_ref="raw_model_only/calls/call_01/capture.json",
            capture_digest=str(capture["capture_digest"]),
        )
    except S3SmallJudgmentAtomProjectionError as exc:
        return _terminalize(
            **terminal_args,
            status="failed",
            phase="contract_validation",
            code=exc.code,
            output=output,
            projection=None,
            successor_program=None,
        )
    except Exception as exc:
        return _terminalize(
            **terminal_args,
            status="failed",
            phase="successor_projection",
            code="s3_small_atom_live_projection_failed:" + type(exc).__name__,
            output=output,
            projection=None,
            successor_program=None,
        )
    successor = dict(projected["successor_program"])
    projection = {
        key: deepcopy(value)
        for key, value in projected.items()
        if key != "successor_program"
    }
    _atomic_json(root / "validated/small_judgment_output.json", output)
    _atomic_json(root / "validated/projection.json", projection)
    _atomic_json(root / "validated/successor_program.json", successor)
    return _terminalize(
        **terminal_args,
        status="completed",
        phase="complete",
        code="s3_small_atom_live_pass",
        output=output,
        projection=projection,
        successor_program=successor,
    )


__all__ = [
    "LIVE_EXECUTION_AUTHORITY_SCHEMA",
    "LIVE_SCOPE",
    "S3SmallJudgmentAtomLiveError",
    "build_no_retry_provider_call",
    "credential_presence_only",
    "execute_successor_live_canary",
    "issue_successor_live_admission",
    "validate_successor_execution_authority",
    "validate_successor_live_issuance",
]
