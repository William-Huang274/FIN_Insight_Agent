from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from sec_agent.llm_gateway import chat_completion
from sec_agent.s2_selected_evidence_numeric_cocompilation import canonical_digest
from sec_agent.s2_selected_evidence_numeric_natural_node_canary import (
    ProviderCall,
    SelectedEvidenceNumericNaturalNodeCanaryError,
    _execute_validated_canary,
    _normalized_text_sha256,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


LIVE_SCOPE = (
    "FIN_0_1_3_S2_SELECTED_EVIDENCE_NUMERIC_NATURAL_NODE_CANARY_LIVE"
)
LIVE_AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "live_authority_v1_0"
)
LIVE_ADMISSION_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "live_admission_v1_0"
)
LIVE_ISSUANCE_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "live_admission_issuance_v1_0"
)
LIVE_EXECUTION_AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "live_execution_authority_v1_0"
)

_HEX_40 = re.compile(r"^[0-9a-f]{40}$")


class SelectedEvidenceNumericNaturalNodeCanaryLiveError(RuntimeError):
    """Typed fail-closed error for live authority and admission handling."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SelectedEvidenceNumericNaturalNodeCanaryLiveError(code)


def credential_presence_only(
    *, profile: Mapping[str, Any], environ: Mapping[str, str] | None = None
) -> dict[str, Any]:
    env_name = str(profile.get("api_key_env") or "")
    _require(env_name == "DEEPSEEK_API_KEY", "live_canary_credential_env_invalid")
    source = os.environ if environ is None else environ
    present = bool(str(source.get(env_name) or "").strip())
    return {
        "credential_env_name": env_name,
        "credential_present": present,
        "credential_value_read_output_or_persisted": False,
    }


def build_no_retry_provider_call(
    *, profile: Mapping[str, Any], environ: Mapping[str, str] | None = None
) -> ProviderCall:
    credential = credential_presence_only(profile=profile, environ=environ)
    _require(
        credential["credential_present"] is True,
        "live_canary_credential_missing",
    )
    _require(
        profile.get("provider") == "deepseek"
        and profile.get("model") == "deepseek-v4-pro"
        and profile.get("base_url") == "https://api.deepseek.com/beta"
        and profile.get("chat_completions_path") == "/chat/completions"
        and int(profile.get("max_transport_attempts", -1)) == 1,
        "live_canary_provider_profile_invalid",
    )

    def call(request: Mapping[str, Any]) -> dict[str, Any]:
        return chat_completion(
            llm_backend=str(profile["provider"]),
            base_url=str(profile["base_url"]),
            chat_completions_path=str(profile["chat_completions_path"]),
            model=str(profile["model"]),
            messages=list(request["messages"]),
            response_format=dict(request["response_format"]),
            api_key_env=str(profile["api_key_env"]),
            temperature=float(request["temperature"]),
            max_tokens=int(request["max_tokens"]),
            timeout_s=int(profile["timeout_seconds_per_call"]),
            stream=bool(request["stream"]),
            enable_thinking=bool(request["enable_thinking"]),
            role=str(request["node_type"]),
            profile=str(profile["profile_ref"]),
            trace_tags={
                "case_key": str(request["case_key"]),
                "node_key": str(request["node_key"]),
                "compiled_input_digest": str(request["compiled_input_digest"]),
                "experiment": "selected_evidence_numeric_natural_node_canary",
            },
            max_transport_attempts=1,
        )

    return call


def _validate_source_bindings(
    *, source_bindings: Sequence[Mapping[str, Any]], repo_root: Path
) -> None:
    refs: list[str] = []
    for row in source_bindings:
        ref = str(row.get("ref") or "")
        digest = str(row.get("normalized_text_sha256") or "")
        _require(bool(ref) and bool(digest), "live_canary_source_binding_invalid")
        path = (repo_root / ref).resolve()
        _require(path.is_file(), "live_canary_source_binding_missing")
        _require(
            _normalized_text_sha256(path) == digest,
            "live_canary_source_binding_sha256_drift",
        )
        refs.append(ref)
    _require(
        len(refs) == len(set(refs)) and len(refs) >= 7,
        "live_canary_source_binding_set_invalid",
    )


def _parse_time(value: Any, code: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise SelectedEvidenceNumericNaturalNodeCanaryLiveError(code) from exc
    _require(parsed.tzinfo is not None, code)
    return parsed


def issue_live_canary_admission(
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
    decision_body = {
        key: value for key, value in decision.items() if key != "decision_digest"
    }
    _require(
        decision.get("decision_digest") == canonical_digest(decision_body)
        and decision.get("status")
        == "decision_complete_authorize_live_runner_and_one_fresh_admission_issuance_execution_not_authorized_by_this_record"
        and dict(decision.get("authorized_next_implementation") or {}).get(
            "register_live_scope"
        )
        == LIVE_SCOPE,
        "live_canary_decision_invalid",
    )
    _require(
        clean_proof.get("result_digest")
        == dict(decision.get("immutable_basis") or {})
        .get("clean_proof", {})
        .get("expected_result_digest")
        and dict(clean_proof.get("stage_acceptance") or {}).get(
            "canary_clean_proof"
        )
        is True,
        "live_canary_clean_proof_invalid",
    )
    _require(
        bool(_HEX_40.fullmatch(implementation_commit)),
        "live_canary_implementation_commit_invalid",
    )
    _require(
        project_os_preflight.get("status") == "pass"
        and project_os_preflight.get("run_scope") == LIVE_SCOPE,
        "live_canary_project_os_preflight_invalid",
    )
    _require(
        credential_preflight
        == {
            "credential_env_name": "DEEPSEEK_API_KEY",
            "credential_present": True,
            "credential_value_read_output_or_persisted": False,
        },
        "live_canary_credential_preflight_invalid",
    )
    _require(
        bool(run_nonce.strip()) and len(run_nonce.strip()) >= 16,
        "live_canary_run_nonce_invalid",
    )
    _require(
        _parse_time(expires_at, "live_canary_expiry_invalid")
        > _parse_time(issued_at, "live_canary_issued_at_invalid"),
        "live_canary_expiry_not_after_issuance",
    )
    _require(bool(user_authority.strip()), "live_canary_user_authority_missing")
    compiled = dict(material["compiled_input"])
    request = dict(material["provider_request"])
    profile = dict(material["profile"])
    future_budget = dict(decision["future_live_budget_if_separately_executed"])
    _require(
        future_budget.get("provider_calls_maximum") == 1
        and future_budget.get("model_calls_maximum") == 1
        and future_budget.get("maximum_output_tokens") == 1800
        and future_budget.get("retries") == 0
        and future_budget.get("fallbacks") == 0
        and future_budget.get("source_calls") == 0
        and future_budget.get("network_tool_calls") == 0
        and future_budget.get("business_artifact_promotion") is False,
        "live_canary_future_budget_invalid",
    )
    normalized_bindings = sorted(
        [deepcopy(dict(row)) for row in source_bindings],
        key=lambda row: str(row.get("ref") or ""),
    )
    authority_body = {
        "schema_version": LIVE_AUTHORITY_SCHEMA,
        "status": "one_fresh_admission_issuance_authorized_execution_requires_separate_authority",
        "run_scope": LIVE_SCOPE,
        "operation_class": "agentic_research",
        "decision_digest": decision["decision_digest"],
        "clean_proof_digest": clean_proof["result_digest"],
        "implementation_commit": implementation_commit,
        "source_bindings": normalized_bindings,
        "project_os_preflight_snapshot": deepcopy(dict(project_os_preflight)),
        "project_os_preflight_digest": canonical_digest(project_os_preflight),
        "compiled_input_digest": compiled["compiled_input_digest"],
        "request_digest": request["request_digest"],
        "profile_ref": profile["profile_ref"],
        "provider": profile["provider"],
        "model": profile["model"],
        "budget": {
            "provider_calls_maximum": 1,
            "model_calls_maximum": 1,
            "maximum_output_tokens": 1800,
            "maximum_estimated_usd": 0.02,
            "source_calls": 0,
            "network_tool_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "business_artifact_promotion": False,
        },
        "credential_preflight": deepcopy(dict(credential_preflight)),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "user_authority": user_authority,
        "execution_authorized_by_this_authority": False,
    }
    authority = {
        **authority_body,
        "authority_digest": canonical_digest(authority_body),
    }
    nonce = run_nonce.strip().casefold()
    run_id = f"fin013_s2_numeric_view_natural_canary_{nonce[:20]}"
    attempt_id = f"attempt_{run_id}_r1"
    admission_body = {
        "schema_version": LIVE_ADMISSION_SCHEMA,
        "admission_id": f"admission_{run_id}",
        "authority_kind": "fresh_live_canary_admission_bound_to_issuance_authority",
        "authority_digest": authority["authority_digest"],
        "execution_mode": "live_single_node_no_retry",
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
        "live_authority": True,
        "business_artifact_promotion": False,
        "execution_enabled_by_issuance": False,
        "separate_execution_authority_required": True,
        "consumed": False,
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
        "issuance_boundary": {
            "admission_issued": True,
            "admission_consumed": False,
            "execution_started": False,
            "provider_call_started": False,
            "model_call_started": False,
            "business_artifact_promotion": False,
        },
        "observed_counts": {
            "new_admissions": 1,
            "admission_consumptions": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "network_calls": 0,
            "source_calls": 0,
            "retries": 0,
            "fallbacks": 0,
        },
        "known_boundary": (
            "Issuance is not execution authorization, admission consumption, "
            "natural DeepSeek evidence, a corrected Dell report, Owner acceptance "
            "or release."
        ),
        "current_next": (
            "SEPARATE_ZERO_CALL_SINGLE_LIVE_CANARY_EXECUTION_AUTHORITY_DECISION"
        ),
    }
    return {
        **issuance_body,
        "issuance_digest": canonical_digest(issuance_body),
    }


def validate_live_canary_issuance(
    issuance: Mapping[str, Any],
    *,
    decision: Mapping[str, Any],
    clean_proof: Mapping[str, Any],
    material: Mapping[str, Any],
    project_os_preflight: Mapping[str, Any],
    repo_root: str | Path,
) -> None:
    issuance_body = {
        key: value for key, value in issuance.items() if key != "issuance_digest"
    }
    _require(
        issuance.get("schema_version") == LIVE_ISSUANCE_SCHEMA
        and issuance.get("issuance_digest") == canonical_digest(issuance_body)
        and issuance.get("status") == "issued_unconsumed_execution_not_authorized",
        "live_canary_issuance_identity_invalid",
    )
    authority = dict(issuance.get("authority") or {})
    authority_body = {
        key: value for key, value in authority.items() if key != "authority_digest"
    }
    _require(
        authority.get("schema_version") == LIVE_AUTHORITY_SCHEMA
        and authority.get("authority_digest") == canonical_digest(authority_body)
        and authority.get("execution_authorized_by_this_authority") is False,
        "live_canary_authority_identity_invalid",
    )
    _require(
        authority.get("decision_digest") == decision.get("decision_digest")
        and authority.get("clean_proof_digest") == clean_proof.get("result_digest")
        and authority.get("project_os_preflight_digest")
        == canonical_digest(
            dict(authority.get("project_os_preflight_snapshot") or {})
        )
        and dict(authority.get("project_os_preflight_snapshot") or {}).get(
            "status"
        )
        == "pass"
        and dict(authority.get("project_os_preflight_snapshot") or {}).get(
            "run_scope"
        )
        == LIVE_SCOPE
        and project_os_preflight.get("status") == "pass"
        and project_os_preflight.get("run_scope") == LIVE_SCOPE,
        "live_canary_authority_basis_invalid",
    )
    root = Path(repo_root).resolve()
    _validate_source_bindings(
        source_bindings=list(authority.get("source_bindings") or ()),
        repo_root=root,
    )
    compiled = dict(material["compiled_input"])
    request = dict(material["provider_request"])
    profile = dict(material["profile"])
    admission = dict(issuance.get("admission") or {})
    admission_body = {
        key: value for key, value in admission.items() if key != "admission_digest"
    }
    _require(
        admission.get("schema_version") == LIVE_ADMISSION_SCHEMA
        and admission.get("admission_digest") == canonical_digest(admission_body)
        and admission.get("authority_digest") == authority.get("authority_digest")
        and admission.get("authority_kind")
        == "fresh_live_canary_admission_bound_to_issuance_authority"
        and admission.get("execution_mode") == "live_single_node_no_retry"
        and admission.get("run_scope") == LIVE_SCOPE
        and admission.get("live_authority") is True
        and admission.get("business_artifact_promotion") is False
        and admission.get("execution_enabled_by_issuance") is False
        and admission.get("separate_execution_authority_required") is True
        and admission.get("consumed") is False,
        "live_canary_admission_identity_invalid",
    )
    _require(
        admission.get("case_key") == compiled.get("case_key")
        and admission.get("node_id") == compiled.get("node_id")
        and admission.get("compiled_input_digest")
        == compiled.get("compiled_input_digest")
        and admission.get("request_digest") == request.get("request_digest")
        and admission.get("profile_ref") == profile.get("profile_ref")
        and admission.get("provider") == profile.get("provider")
        and admission.get("model") == profile.get("model")
        and admission.get("provider_calls_maximum") == 1
        and admission.get("model_calls_maximum") == 1
        and all(
            int(admission.get(key, -1)) == 0
            for key in ("source_calls", "network_tool_calls", "retries", "fallbacks")
        ),
        "live_canary_admission_binding_invalid",
    )
    _require(
        _parse_time(admission.get("expires_at"), "live_canary_admission_expiry_invalid")
        > _parse_time(admission.get("issued_at"), "live_canary_admission_issued_at_invalid"),
        "live_canary_admission_expiry_not_after_issuance",
    )
    _require(
        issuance.get("issuance_boundary")
        == {
            "admission_issued": True,
            "admission_consumed": False,
            "execution_started": False,
            "provider_call_started": False,
            "model_call_started": False,
            "business_artifact_promotion": False,
        }
        and issuance.get("observed_counts")
        == {
            "new_admissions": 1,
            "admission_consumptions": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "network_calls": 0,
            "source_calls": 0,
            "retries": 0,
            "fallbacks": 0,
        },
        "live_canary_issuance_boundary_invalid",
    )


def validate_live_execution_authority(
    execution_authority: Mapping[str, Any], *, issuance: Mapping[str, Any]
) -> None:
    body = {
        key: value
        for key, value in execution_authority.items()
        if key != "execution_authority_digest"
    }
    admission = dict(issuance.get("admission") or {})
    _require(
        execution_authority.get("schema_version")
        == LIVE_EXECUTION_AUTHORITY_SCHEMA
        and execution_authority.get("execution_authority_digest")
        == canonical_digest(body)
        and execution_authority.get("status")
        == "authorized_single_exact_once_live_canary_execution"
        and execution_authority.get("issuance_digest")
        == issuance.get("issuance_digest")
        and execution_authority.get("admission_digest")
        == admission.get("admission_digest")
        and execution_authority.get("execute_provider_call") is True
        and execution_authority.get("provider_calls_maximum") == 1
        and execution_authority.get("model_calls_maximum") == 1
        and execution_authority.get("retries") == 0
        and execution_authority.get("fallbacks") == 0
        and execution_authority.get("business_artifact_promotion") is False,
        "live_canary_execution_authority_invalid",
    )


def execute_live_canary(
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
    validate_live_canary_issuance(
        issuance,
        decision=decision,
        clean_proof=clean_proof,
        material=material,
        project_os_preflight=project_os_preflight,
        repo_root=repo_root,
    )
    validate_live_execution_authority(execution_authority, issuance=issuance)
    admission = dict(issuance["admission"])
    # The immutable admission digest remains the exact-once ledger identity.  The
    # separately signed execution authority is validated above and is not folded
    # back into the signed admission body.
    return _execute_validated_canary(
        admission=admission,
        material=material,
        provider_call=provider_call,
        runtime_root=runtime_root,
        shared_ledger=shared_ledger,
        observed_at=observed_at,
    )


__all__ = [
    "LIVE_ADMISSION_SCHEMA",
    "LIVE_AUTHORITY_SCHEMA",
    "LIVE_EXECUTION_AUTHORITY_SCHEMA",
    "LIVE_ISSUANCE_SCHEMA",
    "LIVE_SCOPE",
    "SelectedEvidenceNumericNaturalNodeCanaryLiveError",
    "build_no_retry_provider_call",
    "credential_presence_only",
    "execute_live_canary",
    "issue_live_canary_admission",
    "validate_live_canary_issuance",
    "validate_live_execution_authority",
]
