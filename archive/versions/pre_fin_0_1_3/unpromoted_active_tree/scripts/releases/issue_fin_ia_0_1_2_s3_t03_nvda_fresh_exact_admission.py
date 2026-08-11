from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    compile_fin_0_1_2_s3_production_admission,
)
from apps.workbench.backend.application.fin_0_1_2_s3_t03_exact_live_runner import (  # noqa: E402
    BOUND_ENVELOPE_REF,
    load_bound_s3_t03_execution_envelope,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_exact_live_"
    "execution_authority_decision_v1_0.json"
)
PREFLIGHT_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_fresh_identity_bound_"
    "runner_atomic_capture_zero_call_preflight_implementation_v1_0.json"
)
ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_fresh_exact_"
    "admission_r1.json"
)
ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_fresh_exact_"
    "admission_issuance_v1_0.json"
)
RUNTIME_ROOT = ROOT / ".codex_runtime/fin012-s3-t03-nvda-primary-r1"
ISSUED_AT = "2026-08-03T23:30:00+08:00"
EXPECTED_AUTHORITY_SHA256 = (
    "18acd58696fbd0ef8934b036024fa1ba6eedf213b7e37c6080d88c7afc433c87"
)
EXPECTED_PREFLIGHT_SHA256 = (
    "2c59aaef468e5f3c8e8ef85d8f9537532431d4e97dc5adb4d1105c9ab925363e"
)
EXPECTED_ENVELOPE_DIGEST = (
    "5f04852451a96c670e539eb79ced472c31615f79d4d491e9bfae57bf55ea37f7"
)
EXPECTED_ADMISSION_DIGEST = (
    "eed177b1124c8db930193196f71eb653b85a2b24d9c92a192251984def4fd1c8"
)
NEXT_ACTION = (
    "FIN-0.1.2-S3-T03-NVDA-EXACT-LIVE-EXECUTION-AUTHORITY-DECISION"
)
CODE_BINDING_PATHS = (
    Path("apps/workbench/backend/application/bounded_agent_executor.py"),
    Path(
        "apps/workbench/backend/application/"
        "fin_0_1_2_s3_t03_exact_live_runner.py"
    ),
    Path(
        "apps/workbench/backend/application/"
        "fin_0_1_2_s3_runtime_contract_binding.py"
    ),
    Path(
        "scripts/releases/"
        "issue_fin_ia_0_1_2_s3_t03_nvda_fresh_exact_admission.py"
    ),
)


class Fin012S3T03AdmissionIssuanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Fin012S3T03AdmissionIssuanceError(code)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "s3_t03_issuance_json_object_required")
    return value


def _compile_admission(
    envelope: Mapping[str, Any], authority: Mapping[str, Any]
) -> S3ThreeCellBoundedAgentAdmission:
    source = S3ThreeCellBoundedAgentAdmission(
        admission_id="fin012-s3-t03-nvda-primary-exact-admission-r1",
        execution_mode=(
            "exact_live_fin_0_1_2_s3_t03_current_nvda_primary_r1"
        ),
        execution_enabled=True,
        case_id=str(envelope["stable_business_input"]["case_id"]),
        case_version=int(envelope["stable_business_input"]["case_version"]),
        as_of=str(authority["exact_product_target"]["as_of"]),
        input_digest=str(envelope["fresh_t03"]["input_digest"]),
        provider="deepseek",
        model="deepseek-v4-pro",
        model_ref="deepseek:deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com/beta",
        max_semantic_model_calls=6,
        max_provider_calls=6,
        max_network_calls=6,
        max_total_cost_usd=0.10,
        specialist_max_output_tokens=1400,
        lead_max_output_tokens=1200,
        writer_max_output_tokens=1400,
        verifier_max_output_tokens=1000,
        max_transport_attempts_per_call=1,
        retry_budget=0,
        source_network_calls_allowed=False,
        external_tool_calls_allowed=False,
        live_business_case_head_writes_allowed=False,
    )
    return compile_fin_0_1_2_s3_production_admission(source)


def render_issuance() -> tuple[dict[str, Any], dict[str, Any]]:
    _require(not ADMISSION.exists(), "s3_t03_admission_already_exists")
    _require(not ISSUANCE.exists(), "s3_t03_issuance_already_exists")
    _require(not RUNTIME_ROOT.exists(), "s3_t03_execution_identity_already_claimed")
    _require(
        _sha256(AUTHORITY) == EXPECTED_AUTHORITY_SHA256,
        "s3_t03_authority_digest_drift",
    )
    _require(
        _sha256(PREFLIGHT_IMPLEMENTATION) == EXPECTED_PREFLIGHT_SHA256,
        "s3_t03_preflight_implementation_digest_drift",
    )
    authority = _load(AUTHORITY)
    preflight = _load(PREFLIGHT_IMPLEMENTATION)
    envelope_path = ROOT / BOUND_ENVELOPE_REF
    envelope_bytes = envelope_path.read_bytes()
    envelope = load_bound_s3_t03_execution_envelope(ROOT)
    _require(
        envelope["envelope_digest"] == EXPECTED_ENVELOPE_DIGEST,
        "s3_t03_execution_envelope_identity_drift",
    )
    _require(
        envelope["admission"]
        == {"issued": False, "persisted": False, "execution_enabled": False},
        "s3_t03_historical_envelope_admission_boundary_drift",
    )
    _require(
        preflight["status"].startswith("pass_zero_call_")
        and preflight["issue_disposition"]["status"].startswith("closed_by_"),
        "s3_t03_preflight_not_issuable",
    )
    _require(
        authority["authority"][
            "future_one_primary_NVDA_exact_live_authorized"
        ]
        and authority["authority"][
            "authorization_effective_only_after_fresh_identity_input_boundary_bound_runner_atomic_capture_and_zero_call_preflight_pass"
        ],
        "s3_t03_conditional_authority_missing",
    )

    admission = _compile_admission(envelope, authority)
    admission.assert_profile_admissible()
    payload = admission.model_dump(mode="json")
    digest = canonical_digest(admission.digest_payload())
    _require(
        digest == EXPECTED_ADMISSION_DIGEST,
        "s3_t03_admission_digest_mismatch",
    )
    maximum_output_tokens = (
        3 * admission.specialist_max_output_tokens
        + admission.lead_max_output_tokens
        + admission.writer_max_output_tokens
        + admission.verifier_max_output_tokens
    )
    _require(
        admission.company == "NVDA"
        and admission.case_id == envelope["stable_business_input"]["case_id"]
        and admission.case_version
        == envelope["stable_business_input"]["case_version"]
        and admission.input_digest == envelope["fresh_t03"]["input_digest"]
        and admission.runtime_contract_family_binding_ref
        == envelope["runtime_contract"]["binding_ref"]
        and admission.runtime_contract_family_source_digest
        == envelope["runtime_contract"]["source_digest"]
        and admission.max_provider_calls
        == envelope["hard_budget"]["provider_calls"]
        and maximum_output_tokens
        == envelope["hard_budget"]["maximum_output_tokens"]
        and admission.max_total_cost_usd
        == envelope["hard_budget"]["maximum_total_cost_usd"]
        and admission.max_transport_attempts_per_call == 1
        and admission.retry_budget == 0,
        "s3_t03_admission_envelope_binding_mismatch",
    )

    provider_callback_calls = 0

    def _must_not_call_provider(**_: Any) -> dict[str, Any]:
        nonlocal provider_callback_calls
        provider_callback_calls += 1
        raise AssertionError("provider_callback_forbidden_during_s3_t03_issuance")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    _require(
        provider_callback_calls == 0,
        "s3_t03_provider_called_during_issuance",
    )
    _require(
        envelope_path.read_bytes() == envelope_bytes,
        "s3_t03_execution_envelope_changed_during_issuance",
    )

    code_bindings = {
        path.as_posix(): _sha256(ROOT / path) for path in CODE_BINDING_PATHS
    }
    issuance = {
        "schema_version": (
            "fin_ia_0_1_2_s3_t03_nvda_fresh_exact_admission_issuance_v1_0"
        ),
        "issuance_id": (
            "FIN-0.1.2-S3-T03-NVDA-FRESH-EXACT-ADMISSION-ISSUANCE-R1"
        ),
        "issued_at": ISSUED_AT,
        "status": "issued_unconsumed_zero_call_preflight_pass",
        "authority": {
            "user_instruction": "继续",
            "fresh_exact_admission_issuance_authorized": True,
            "admission_consumption_or_exact_live_execution_authorized": False,
            "automatic_retry_fallback_patch_or_rerun_authorized": False,
            "paired_assessment_or_owner_acceptance_authorized": False,
            "S3_T04_or_later_authorized": False,
        },
        "source_bindings": [
            {
                "ref": _relative(AUTHORITY),
                "sha256": _sha256(AUTHORITY),
                "role": "conditional_single_primary_exact_live_authority",
            },
            {
                "ref": _relative(PREFLIGHT_IMPLEMENTATION),
                "sha256": _sha256(PREFLIGHT_IMPLEMENTATION),
                "role": "runner_and_fresh_identity_preflight_pass",
            },
            {
                "ref": BOUND_ENVELOPE_REF,
                "sha256": _sha256(envelope_path),
                "role": "fresh_identity_execution_envelope",
            },
        ],
        "issued_admission": {
            "admission_ref": _relative(ADMISSION),
            "admission_id": admission.admission_id,
            "admission_digest": digest,
            "runtime_root": _relative(RUNTIME_ROOT),
            "execution_identity": envelope["fresh_t03"]["execution_identity"],
            "fresh_identity": True,
            "execution_enabled": True,
            "issued": True,
            "consumed": False,
            "execution_started": False,
        },
        "exact_binding": {
            "case_id": admission.case_id,
            "case_version": admission.case_version,
            "as_of": admission.as_of,
            "input_head_digest": envelope["stable_business_input"][
                "input_head_digest"
            ],
            "stable_business_input_digest": envelope[
                "stable_business_input"
            ]["digest"],
            "complete_input_digest": admission.input_digest,
            "preparation_digest": envelope["fresh_t03"]["preparation_digest"],
            "predicted_work_unit_id": envelope["fresh_t03"]["work_unit_id"],
            "predicted_attempt_id": envelope["fresh_t03"]["attempt_id"],
            "predicted_research_run_id": envelope["fresh_t03"][
                "research_run_id"
            ],
            "runtime_contract_binding_ref": (
                admission.runtime_contract_family_binding_ref
            ),
            "runtime_contract_source_digest": (
                admission.runtime_contract_family_source_digest
            ),
            "provider": admission.provider,
            "model": admission.model,
            "model_ref": admission.model_ref,
            "base_url": admission.base_url,
            "credential_env_name": admission.api_key_env,
        },
        "execution_envelope": {
            "envelope_digest": envelope["envelope_digest"],
            "maximum_semantic_model_calls": admission.max_semantic_model_calls,
            "maximum_provider_calls": admission.max_provider_calls,
            "maximum_network_calls": admission.max_network_calls,
            "maximum_transport_attempts_per_call": (
                admission.max_transport_attempts_per_call
            ),
            "retry_budget": admission.retry_budget,
            "maximum_input_tokens": envelope["hard_budget"][
                "maximum_input_tokens"
            ],
            "maximum_output_tokens_total": maximum_output_tokens,
            "maximum_total_cost_usd": admission.max_total_cost_usd,
            "maximum_wall_clock_seconds": envelope["hard_budget"][
                "maximum_wall_clock_seconds"
            ],
            "source_network_calls_allowed": False,
            "external_tool_calls_allowed": False,
            "live_business_case_head_writes_allowed": False,
            "automatic_retry_repair_fallback_or_rerun_allowed": False,
            "first_credible_failure": "typed_terminal_fail_closed_stop",
        },
        "zero_call_preflight": {
            "executor_constructed": True,
            "provider_callback_invoked": False,
            "credential_presence_checked": False,
            "credential_value_read_output_or_persisted": False,
            "runtime_root_absent": True,
            "execution_identity_unclaimed": True,
            "exact_code_bindings": code_bindings,
            "exact_code_binding_count": len(code_bindings),
        },
        "issuance_boundary": {
            "admission_issued": True,
            "admission_consumed": False,
            "execution_identity_claimed": False,
            "execution_started": False,
            "supervisor_launched": False,
            "model_or_provider_call_started": False,
            "business_Run_or_Artifact_materialization_performed": False,
            "paired_assessment_performed": False,
            "owner_acceptance_performed": False,
        },
        "observed_counts": {
            "new_admissions": 1,
            "admission_consumptions": 0,
            "work_units_created": 0,
            "attempts_created": 0,
            "research_runs_created": 0,
            "artifacts_created": 0,
            "model_calls": 0,
            "provider_calls": provider_callback_calls,
            "execution_network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
        },
        "known_boundary": (
            "Issuance is not credential qualification, admission consumption, "
            "exact-live execution, natural DeepSeek evidence, current NVDA R2, "
            "paired gain, Owner acceptance, release or production."
        ),
        "next_action": NEXT_ACTION,
    }
    return payload, issuance


def _write_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(_canonical_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
        _require(not path.exists(), "s3_t03_issuance_target_already_exists")
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def issue() -> tuple[dict[str, Any], dict[str, Any]]:
    payload, issuance = render_issuance()
    _write_atomic(ADMISSION, payload)
    try:
        _write_atomic(ISSUANCE, issuance)
    except Exception:
        ADMISSION.unlink(missing_ok=True)
        raise
    admitted = S3ThreeCellBoundedAgentAdmission.model_validate(_load(ADMISSION))
    _require(
        canonical_digest(admitted.digest_payload()) == EXPECTED_ADMISSION_DIGEST,
        "s3_t03_materialized_admission_digest_mismatch",
    )
    _require(
        _load(ISSUANCE) == issuance,
        "s3_t03_materialized_issuance_mismatch",
    )
    _require(
        not RUNTIME_ROOT.exists(),
        "s3_t03_issuance_claimed_execution_identity",
    )
    return payload, issuance


def main() -> int:
    _, issuance = issue()
    print(json.dumps(issuance, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
