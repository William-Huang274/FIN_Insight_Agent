from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    compile_fin_0_1_2_s3_production_admission,
)
from apps.workbench.backend.application.fin_0_1_2_s3_runtime_contract_binding import (  # noqa: E402
    load_fin_0_1_2_s3_runtime_contract_binding,
)
from apps.workbench.backend.application.fin_0_1_2_s3_t03_exact_live_runner import (  # noqa: E402
    compile_fresh_identity_execution_envelope,
    load_bound_s3_t03_execution_envelope,
)
from apps.workbench.backend.application.research_runtime import (  # noqa: E402
    prepare_s3_three_cell_bounded_agent_exact_input,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


CONTROL_AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_replacement_fresh_"
    "admission_authority_decision_v1_0.json"
)
PRIMARY_BUDGET_AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_exact_live_"
    "execution_authority_decision_v1_0.json"
)
FRESH_ADMISSION_AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_replacement_fresh_"
    "admission_authority_decision_v2_0.json"
)
ENVELOPE = ROOT / (
    "configs/runtime/fin_ia_0_1_2_s3_t03_nvda_replacement_fresh_identity_"
    "execution_envelope_v1_0.json"
)
PROFILE = ROOT / (
    "configs/runtime/fin_ia_0_1_2_s3_t03_nvda_replacement_control_binding_"
    "profile_v1_0.json"
)
ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_replacement_fresh_exact_"
    "admission_r2.json"
)
ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_replacement_fresh_exact_"
    "admission_issuance_v1_0.json"
)
EXACT_INPUT_MANIFEST = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_nvda_exact_product_input_v1_0.json"
)
RUNTIME_ROOT = ROOT / ".codex_runtime/fin012-s3-t03-nvda-replacement-r2"
SUPERVISION_ROOT = ROOT / (
    ".codex_runtime/fin012-s3-t03-nvda-replacement-r2-supervision"
)
EXECUTION_IDENTITY = "fin012-s3-t03-nvda-replacement-r2"
TRACKED_IDENTITY = "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
SUPERVISION_CONTRACT_REF = (
    "fin_0_1_2.s3_t03.replacement_exact_live_supervision:v1"
)
SCHEMA = "fin_ia_0_1_2_s3_t03_replacement_control_binding_profile_v1_0"


class ReplacementControlError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ReplacementControlError(code)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "replacement_json_object_required")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _atomic_create(path: Path, payload: Mapping[str, Any]) -> None:
    _require(not path.exists(), f"replacement_target_already_exists:{_relative(path)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(_canonical_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _compile_admission(envelope: Mapping[str, Any]) -> S3ThreeCellBoundedAgentAdmission:
    source = S3ThreeCellBoundedAgentAdmission(
        admission_id="fin012-s3-t03-nvda-replacement-exact-admission-r2",
        execution_mode="exact_live_fin_0_1_2_s3_t03_current_nvda_replacement_r2",
        execution_enabled=True,
        case_id=str(envelope["stable_business_input"]["case_id"]),
        case_version=int(envelope["stable_business_input"]["case_version"]),
        as_of="2026-07-21T00:00:00Z",
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
    compiled = compile_fin_0_1_2_s3_production_admission(source)
    compiled.assert_profile_admissible()
    return compiled


def compile_control_bundle(preparation_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    from scripts.releases.run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live import (
        _principal,
        rehydrate_exact_input_services,
    )

    control = _load(CONTROL_AUTHORITY)
    _require(
        control.get("status")
        == "blocked_no_replacement_admission_issuance_authority_controlled_successor_missing",
        "replacement_control_authority_state_drift",
    )
    local, evidence, case, accepted = rehydrate_exact_input_services(preparation_root)
    tracked = prepare_s3_three_cell_bounded_agent_exact_input(
        local,
        evidence,
        str(case["case_id"]),
        _principal(),
        decision_surface_contract_ref=str(accepted["contract_version_id"]),
        execution_identity=TRACKED_IDENTITY,
    )
    fresh = prepare_s3_three_cell_bounded_agent_exact_input(
        local,
        evidence,
        str(case["case_id"]),
        _principal(),
        decision_surface_contract_ref=str(accepted["contract_version_id"]),
        execution_identity=EXECUTION_IDENTITY,
    )
    budget_authority = _load(PRIMARY_BUDGET_AUTHORITY)
    binding = load_fin_0_1_2_s3_runtime_contract_binding()
    envelope = compile_fresh_identity_execution_envelope(
        tracked_t02=tracked,
        fresh_t03=fresh,
        authority_ref=_relative(CONTROL_AUTHORITY),
        authority_sha256=_sha256(CONTROL_AUTHORITY),
        runtime_contract_binding_ref=binding.binding_ref,
        runtime_contract_source_digest=binding.source_digest,
        hard_budget=budget_authority["hard_budget"],
    )
    admission = _compile_admission(envelope)
    admission_payload = admission.model_dump(mode="json")
    admission_digest = canonical_digest(admission.digest_payload())
    profile_body = {
        "schema_version": SCHEMA,
        "profile_id": "FIN-0.1.2-S3-T03-NVDA-REPLACEMENT-R2",
        "execution_identity": EXECUTION_IDENTITY,
        "admission_ref": _relative(ADMISSION),
        "issuance_ref": _relative(ISSUANCE),
        "execution_envelope_ref": _relative(ENVELOPE),
        "exact_input_manifest_ref": _relative(EXACT_INPUT_MANIFEST),
        "runtime_root_ref": _relative(RUNTIME_ROOT),
        "supervision_root_ref": _relative(SUPERVISION_ROOT),
        "supervision_contract_ref": SUPERVISION_CONTRACT_REF,
        "expected_admission_digest": admission_digest,
        "expected_admission_sha256": hashlib.sha256(
            _canonical_bytes(admission_payload)
        ).hexdigest(),
        "expected_envelope_digest": envelope["envelope_digest"],
        "expected_envelope_sha256": hashlib.sha256(
            _canonical_bytes(envelope)
        ).hexdigest(),
        "fresh_admission_authority_ref": _relative(FRESH_ADMISSION_AUTHORITY),
        "execution_authority_must_bind_actual_profile_issuance_envelope_and_code_hashes": True,
        "automatic_retry_or_third_exact_authorized": False,
    }
    profile = {
        **profile_body,
        "profile_digest": canonical_digest(profile_body),
    }
    return envelope, admission_payload, profile


def prospective_preflight(output: Path | None = None) -> dict[str, Any]:
    _require(not ADMISSION.exists() and not ISSUANCE.exists(), "replacement_issuance_started_early")
    _require(not RUNTIME_ROOT.exists() and not SUPERVISION_ROOT.exists(), "replacement_identity_not_fresh")
    with tempfile.TemporaryDirectory(prefix="fin012-s3-t03-replacement-prospective-") as temp:
        envelope, admission_payload, profile = compile_control_bundle(Path(temp) / "compile")
        admission = S3ThreeCellBoundedAgentAdmission.model_validate(admission_payload)
        provider_calls = 0

        def forbidden_provider(**_: Any) -> Mapping[str, Any]:
            nonlocal provider_calls
            provider_calls += 1
            raise AssertionError("replacement_prospective_preflight_provider_forbidden")

        build_s3_three_cell_bounded_agent_executor_for_admission(
            admission, chat_completion_fn=forbidden_provider
        )
        child_output = Path(temp) / "child-result.json"
        environment = {
            key: value
            for key, value in os.environ.items()
            if not any(marker in key.upper() for marker in ("API_KEY", "AUTHORIZATION", "COOKIE"))
        }
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "prospective-child-preflight", "--output", str(child_output)],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        _require(completed.returncode == 0 and child_output.is_file(), "replacement_child_preflight_failed")
        child = _load(child_output)
        result = {
            "schema_version": "fin_ia_0_1_2_s3_t03_replacement_controlled_successor_zero_call_preflight_v1_0",
            "status": "pass_fresh_envelope_frozen_admission_atomic_issuer_and_real_child_zero_call_preflight",
            "execution_identity": EXECUTION_IDENTITY,
            "envelope_digest": envelope["envelope_digest"],
            "complete_input_digest": envelope["fresh_t03"]["input_digest"],
            "stable_business_input_digest": envelope["stable_business_input"]["digest"],
            "predicted_work_unit_id": envelope["fresh_t03"]["work_unit_id"],
            "predicted_attempt_id": envelope["fresh_t03"]["attempt_id"],
            "predicted_research_run_id": envelope["fresh_t03"]["research_run_id"],
            "admission_digest": profile["expected_admission_digest"],
            "profile_digest": profile["profile_digest"],
            "child_result_digest": canonical_digest(child),
            "child_process_count": 1,
            "provider_callback_calls": provider_calls,
            "credential_environment_scrubbed_in_child": True,
            "model_provider_network_calls": [0, 0, 0],
            "admission_or_issuance_materialized": False,
            "primary_runtime_or_failure_mutated": False,
        }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(_canonical_bytes(result))
    return result


def prospective_child_preflight(output: Path) -> dict[str, Any]:
    _require(not any("API_KEY" in key.upper() for key in os.environ), "replacement_child_credential_not_scrubbed")
    with tempfile.TemporaryDirectory(prefix="fin012-s3-t03-replacement-child-") as temp:
        envelope, admission_payload, profile = compile_control_bundle(Path(temp) / "compile")
    result = {
        "status": "pass_child_rederived_control_bundle_without_provider",
        "envelope_digest": envelope["envelope_digest"],
        "admission_digest": profile["expected_admission_digest"],
        "profile_digest": profile["profile_digest"],
        "provider_calls": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical_bytes(result))
    return result


def materialize_control() -> dict[str, Any]:
    _require(not ENVELOPE.exists() and not PROFILE.exists(), "replacement_control_already_materialized")
    with tempfile.TemporaryDirectory(prefix="fin012-s3-t03-replacement-materialize-") as temp:
        envelope, _, profile = compile_control_bundle(Path(temp))
    _atomic_create(ENVELOPE, envelope)
    try:
        _atomic_create(PROFILE, profile)
    except Exception:
        ENVELOPE.unlink(missing_ok=True)
        raise
    return {
        "status": "materialized_control_only_no_admission_or_execution",
        "envelope_ref": _relative(ENVELOPE),
        "envelope_sha256": _sha256(ENVELOPE),
        "profile_ref": _relative(PROFILE),
        "profile_sha256": _sha256(PROFILE),
        "admission_absent": not ADMISSION.exists(),
        "issuance_absent": not ISSUANCE.exists(),
    }


def issue() -> dict[str, Any]:
    _require(ENVELOPE.exists() and PROFILE.exists(), "replacement_control_missing")
    _require(not ADMISSION.exists() and not ISSUANCE.exists(), "replacement_already_issued")
    _require(not RUNTIME_ROOT.exists() and not SUPERVISION_ROOT.exists(), "replacement_identity_already_used")
    authority = _load(FRESH_ADMISSION_AUTHORITY)
    _require(
        authority.get("status") == "authorized_replacement_fresh_admission_issuance_not_started"
        and (authority.get("authority") or {}).get("replacement_admission_issuance_authorized") is True
        and (authority.get("authority") or {}).get("replacement_execution_authorized") is False,
        "replacement_fresh_admission_authority_invalid",
    )
    profile = _load(PROFILE)
    with tempfile.TemporaryDirectory(prefix="fin012-s3-t03-replacement-issue-") as temp:
        envelope, admission_payload, reproduced_profile = compile_control_bundle(Path(temp))
    _require(_load(ENVELOPE) == envelope and profile == reproduced_profile, "replacement_control_reproduction_drift")
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(admission_payload)
    provider_calls = 0

    def forbidden_provider(**_: Any) -> Mapping[str, Any]:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("replacement_issuance_provider_forbidden")

    build_s3_three_cell_bounded_agent_executor_for_admission(admission, chat_completion_fn=forbidden_provider)
    issuance = {
        "schema_version": "fin_ia_0_1_2_s3_t03_nvda_replacement_fresh_exact_admission_issuance_v1_0",
        "issuance_id": "FIN-0.1.2-S3-T03-NVDA-REPLACEMENT-FRESH-EXACT-ADMISSION-R2",
        "issued_at": authority["recorded_at"],
        "status": "issued_unconsumed_zero_call_preflight_pass",
        "authority": {
            "replacement_fresh_admission_issuance_authorized": True,
            "admission_consumption_or_exact_live_execution_authorized": False,
            "automatic_retry_fallback_patch_or_third_exact_authorized": False,
        },
        "source_bindings": [
            {"ref": _relative(FRESH_ADMISSION_AUTHORITY), "sha256": _sha256(FRESH_ADMISSION_AUTHORITY), "role": "replacement_fresh_admission_authority"},
            {"ref": _relative(PROFILE), "sha256": _sha256(PROFILE), "role": "controlled_successor_binding_profile"},
            {"ref": _relative(ENVELOPE), "sha256": _sha256(ENVELOPE), "role": "replacement_execution_envelope"},
        ],
        "binding_profile": {"ref": _relative(PROFILE), "sha256": _sha256(PROFILE), "digest": profile["profile_digest"]},
        "issued_admission": {
            "admission_ref": _relative(ADMISSION),
            "admission_id": admission.admission_id,
            "admission_digest": profile["expected_admission_digest"],
            "runtime_root": _relative(RUNTIME_ROOT),
            "execution_identity": EXECUTION_IDENTITY,
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
            "input_head_digest": envelope["stable_business_input"]["input_head_digest"],
            "stable_business_input_digest": envelope["stable_business_input"]["digest"],
            "complete_input_digest": admission.input_digest,
            "preparation_digest": envelope["fresh_t03"]["preparation_digest"],
            "predicted_work_unit_id": envelope["fresh_t03"]["work_unit_id"],
            "predicted_attempt_id": envelope["fresh_t03"]["attempt_id"],
            "predicted_research_run_id": envelope["fresh_t03"]["research_run_id"],
            "provider": admission.provider,
            "model": admission.model,
            "model_ref": admission.model_ref,
            "base_url": admission.base_url,
            "credential_env_name": admission.api_key_env,
        },
        "execution_envelope": {
            "envelope_digest": envelope["envelope_digest"],
            "maximum_semantic_model_calls": 9,
            "maximum_provider_calls": 9,
            "maximum_network_calls": 9,
            "maximum_transport_attempts_per_call": 1,
            "retry_budget": 0,
            "maximum_input_tokens": 60000,
            "maximum_output_tokens_total": 10000,
            "maximum_total_cost_usd": 0.06,
            "maximum_wall_clock_seconds": 900,
        },
        "zero_call_preflight": {"provider_callback_invoked": False, "provider_calls": provider_calls},
        "observed_counts": {"new_admissions": 1, "admission_consumptions": 0, "model_calls": 0, "provider_calls": provider_calls},
    }
    _atomic_create(ADMISSION, admission_payload)
    try:
        _atomic_create(ISSUANCE, issuance)
    except Exception:
        ADMISSION.unlink(missing_ok=True)
        raise
    return issuance


def _activate_issued_binding() -> Any:
    _require(PROFILE.exists() and ENVELOPE.exists() and ADMISSION.exists() and ISSUANCE.exists(), "replacement_issued_binding_incomplete")
    profile = _load(PROFILE)
    _require(profile.get("schema_version") == SCHEMA, "replacement_profile_schema_mismatch")
    _require(profile.get("profile_digest") == canonical_digest({k: v for k, v in profile.items() if k != "profile_digest"}), "replacement_profile_digest_mismatch")
    _require(_sha256(ADMISSION) == profile["expected_admission_sha256"], "replacement_admission_file_drift")
    _require(_sha256(ENVELOPE) == profile["expected_envelope_sha256"], "replacement_envelope_file_drift")
    issuance = _load(ISSUANCE)
    binding = issuance.get("binding_profile") or {}
    _require(binding.get("sha256") == _sha256(PROFILE) and binding.get("digest") == profile["profile_digest"], "replacement_issuance_profile_mismatch")

    from scripts.releases import run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live as base

    base.ADMISSION = ADMISSION
    base.ISSUANCE = ISSUANCE
    base.EXACT_INPUT_MANIFEST = EXACT_INPUT_MANIFEST
    base.EXPECTED_ADMISSION_SHA256 = profile["expected_admission_sha256"]
    base.EXPECTED_ISSUANCE_SHA256 = _sha256(ISSUANCE)
    base.EXPECTED_ADMISSION_DIGEST = profile["expected_admission_digest"]
    base.SUPERVISION_CONTRACT_REF = SUPERVISION_CONTRACT_REF
    original_loader = load_bound_s3_t03_execution_envelope

    def replacement_loader(repository_root: str | Path | None = None) -> dict[str, Any]:
        return original_loader(repository_root, envelope_ref=profile["execution_envelope_ref"])

    base.load_bound_s3_t03_execution_envelope = replacement_loader
    os.environ["FIN_IA_0_1_2_S3_T03_SUPERVISOR_ENTRYPOINT"] = str(Path(__file__).resolve())
    return base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode")
    parser.add_argument("--output", type=Path)
    args, passthrough = parser.parse_known_args()
    if args.mode == "prospective-preflight":
        print(json.dumps(prospective_preflight(args.output), ensure_ascii=False, indent=2))
        return 0
    if args.mode == "prospective-child-preflight":
        _require(args.output is not None, "replacement_child_output_required")
        prospective_child_preflight(args.output)
        return 0
    if args.mode == "materialize-control":
        print(json.dumps(materialize_control(), ensure_ascii=False, indent=2))
        return 0
    if args.mode == "issue":
        print(json.dumps(issue(), ensure_ascii=False, indent=2))
        return 0
    base = _activate_issued_binding()
    sys.argv = [sys.argv[0], args.mode, *passthrough]
    return base._entrypoint()


if __name__ == "__main__":
    raise SystemExit(main())
