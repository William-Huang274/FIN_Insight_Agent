from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.fin_0_1_2_s3_t03_exact_live_runner import (  # noqa: E402
    execute_bound_s3_t03,
)
from apps.workbench.backend.application.fin_0_1_2_s4_natural_case_entry import (  # noqa: E402
    load_current_fin_0_1_2_s4_t01_case_entry,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t04_current_evidence_research import (  # noqa: E402
    prepare_current_nvda_agent_execution,
    validate_current_nvda_evidence_pack,
)
from apps.workbench.backend.application.research_runtime import (  # noqa: E402
    S3ThreeCellPreparedExecution,
    prepare_s3_three_cell_bounded_agent_exact_input,
)
from scripts.releases.issue_fin_ia_0_1_2_s4_t04_nvda_current_evidence_fresh_exact_admission import (  # noqa: E402
    ADMISSION_REF,
    EXECUTION_IDENTITY,
    PACK,
)
from scripts.releases.run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live import (  # noqa: E402
    _default_completion,
    _principal,
    rehydrate_exact_input_services,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


ADMISSION = ROOT / ADMISSION_REF
ISSUANCE = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t04_nvda_current_evidence_fresh_exact_admission_"
    "issuance_v1_0.json"
)
DEFAULT_RUNTIME_ROOT = ROOT / (
    ".codex_runtime/fin012-s4-t04-nvda-current-evidence-exact-live-r1"
)
EXPECTED_ADMISSION_DIGEST = (
    "55ac6d9299efa1ca91fa680095818d63e2a1a5c67eda5d4d27e49b5d575f7812"
)
EXPECTED_ISSUANCE_DIGEST = (
    "85f6c32b50071e0b96dfd51ae952b3be5b9e9e78f44d647bcd029443283f224c"
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("s4_t04_exact_live_json_object_required")
    return value


def load_exact_target_for(
    *,
    admission_path: Path,
    issuance_path: Path,
    expected_admission_digest: str,
    expected_issuance_digest: str,
    execution_identity: str,
) -> tuple[S3ThreeCellBoundedAgentAdmission, dict[str, Any]]:
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(admission_path)
    )
    issuance = _load(issuance_path)
    admission.assert_profile_admissible()
    if (
        canonical_digest(admission.digest_payload()) != expected_admission_digest
        or issuance.get("issuance_digest") != expected_issuance_digest
        or issuance.get("issuance_digest")
        != canonical_digest(
            {key: value for key, value in issuance.items() if key != "issuance_digest"}
        )
        or issuance.get("status") != "issued_unconsumed_zero_call_preflight_pass"
        or issuance["issued_admission"]["admission_digest"]
        != expected_admission_digest
        or issuance["issued_admission"]["execution_identity"]
        != execution_identity
        or issuance["issued_admission"]["consumed"] is not False
        or admission.input_digest != issuance["exact_binding"]["complete_input_digest"]
    ):
        raise ValueError("s4_t04_exact_live_admission_or_issuance_drift")
    return admission, issuance


def load_exact_target() -> tuple[S3ThreeCellBoundedAgentAdmission, dict[str, Any]]:
    return load_exact_target_for(
        admission_path=ADMISSION,
        issuance_path=ISSUANCE,
        expected_admission_digest=EXPECTED_ADMISSION_DIGEST,
        expected_issuance_digest=EXPECTED_ISSUANCE_DIGEST,
        execution_identity=EXECUTION_IDENTITY,
    )


def prepare_exact_current_input(
    preparation_root: Path,
    admission: S3ThreeCellBoundedAgentAdmission,
    issuance: Mapping[str, Any],
    *,
    execution_identity: str = EXECUTION_IDENTITY,
) -> S3ThreeCellPreparedExecution:
    local, evidence, case, accepted = rehydrate_exact_input_services(preparation_root)
    baseline = prepare_s3_three_cell_bounded_agent_exact_input(
        local,
        evidence,
        str(case["case_id"]),
        _principal(),
        decision_surface_contract_ref=str(accepted["contract_version_id"]),
        execution_identity=execution_identity,
    )
    pack = validate_current_nvda_evidence_pack(_load(PACK))
    prepared = prepare_current_nvda_agent_execution(
        baseline,
        pack,
        t01_entry=load_current_fin_0_1_2_s4_t01_case_entry("NVDA"),
        principal=_principal(),
        execution_identity=execution_identity,
        verifier_input_contract_ref=str(
            issuance["exact_binding"].get(
                "verifier_input_contract_ref",
                "fin01.s3.owner_grade_verifier_input:v2",
            )
        ),
    )
    expected = issuance["exact_binding"]
    observed = {
        "case_id": prepared.case_id,
        "case_version": prepared.case_version,
        "as_of": prepared.input_pack.as_of,
        "complete_input_digest": prepared.input_digest,
        "preparation_digest": prepared.preparation_digest,
        "predicted_work_unit_id": prepared.work_unit_id,
        "predicted_attempt_id": prepared.attempt_id,
        "predicted_research_run_id": prepared.research_run_id,
        "evidence_pack_digest": pack["evidence_pack_digest"],
        "t03_terminal_digest": pack["t03_terminal_digest"],
        **(
            {
                "verifier_input_contract_ref": expected[
                    "verifier_input_contract_ref"
                ]
            }
            if "verifier_input_contract_ref" in expected
            else {}
        ),
    }
    if observed != expected or admission.input_digest != prepared.input_digest:
        raise ValueError("s4_t04_exact_live_input_rehydrate_drift")
    return prepared


def zero_call_preflight() -> dict[str, Any]:
    admission, issuance = load_exact_target()
    with tempfile.TemporaryDirectory(prefix="fin012-s4-t04-preflight-") as temporary:
        prepared = prepare_exact_current_input(Path(temporary), admission, issuance)
    calls = 0

    def forbidden(**_: Any) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        raise AssertionError("s4_t04_preflight_provider_call_forbidden")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=forbidden
    )
    return {
        "schema_version": "fin_ia_0_1_2_s4_t04_exact_live_zero_call_preflight_v1_0",
        "status": "pass_exact_input_admission_transport_wiring_zero_call",
        "execution_identity": prepared.execution_identity,
        "input_digest": prepared.input_digest,
        "admission_digest": EXPECTED_ADMISSION_DIGEST,
        "envelope_digest": issuance["execution_envelope"]["envelope_digest"],
        "provider_callback_calls": calls,
        "model_provider_network_calls": [0, 0, 0],
        "credential_present": bool(os.environ.get(admission.api_key_env)),
        "credential_value_output_or_persisted": False,
        "provider_health_probe_performed": False,
    }


def zero_call_preflight_for(
    *,
    admission_path: Path,
    issuance_path: Path,
    expected_admission_digest: str,
    expected_issuance_digest: str,
    execution_identity: str,
) -> dict[str, Any]:
    admission, issuance = load_exact_target_for(
        admission_path=admission_path,
        issuance_path=issuance_path,
        expected_admission_digest=expected_admission_digest,
        expected_issuance_digest=expected_issuance_digest,
        execution_identity=execution_identity,
    )
    with tempfile.TemporaryDirectory(prefix="fin012-s4-t04-r2-preflight-") as temporary:
        prepared = prepare_exact_current_input(
            Path(temporary),
            admission,
            issuance,
            execution_identity=execution_identity,
        )
    calls = 0

    def forbidden(**_: Any) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        raise AssertionError("s4_t04_preflight_provider_call_forbidden")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=forbidden
    )
    return {
        "schema_version": "fin_ia_0_1_2_s4_t04_exact_live_zero_call_preflight_v1_0",
        "status": "pass_exact_input_admission_transport_wiring_zero_call",
        "execution_identity": prepared.execution_identity,
        "input_digest": prepared.input_digest,
        "admission_digest": expected_admission_digest,
        "envelope_digest": issuance["execution_envelope"]["envelope_digest"],
        "provider_callback_calls": calls,
        "model_provider_network_calls": [0, 0, 0],
        "credential_present": bool(os.environ.get(admission.api_key_env)),
        "credential_value_output_or_persisted": False,
        "provider_health_probe_performed": False,
    }


def execute_exact_once(
    runtime_root: Path,
    *,
    completion: Callable[..., Mapping[str, Any]] = _default_completion,
) -> dict[str, Any]:
    admission, issuance = load_exact_target()
    if runtime_root.exists():
        raise ValueError("s4_t04_exact_live_runtime_identity_already_exists")
    if not os.environ.get(admission.api_key_env):
        raise ValueError("s4_t04_provider_credential_missing")
    if os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") != "0":
        raise ValueError("s4_t04_transport_retries_not_zero")
    with tempfile.TemporaryDirectory(prefix="fin012-s4-t04-exact-") as temporary:
        prepared = prepare_exact_current_input(Path(temporary), admission, issuance)
        return execute_bound_s3_t03(
            runtime_root=runtime_root,
            prepared=prepared,
            admission=admission,
            execution_envelope=issuance["execution_envelope"],
            completion=completion,
        )


def execute_exact_once_for(
    runtime_root: Path,
    *,
    admission_path: Path,
    issuance_path: Path,
    expected_admission_digest: str,
    expected_issuance_digest: str,
    execution_identity: str,
    completion: Callable[..., Mapping[str, Any]] = _default_completion,
) -> dict[str, Any]:
    admission, issuance = load_exact_target_for(
        admission_path=admission_path,
        issuance_path=issuance_path,
        expected_admission_digest=expected_admission_digest,
        expected_issuance_digest=expected_issuance_digest,
        execution_identity=execution_identity,
    )
    if runtime_root.exists():
        raise ValueError("s4_t04_exact_live_runtime_identity_already_exists")
    if not os.environ.get(admission.api_key_env):
        raise ValueError("s4_t04_provider_credential_missing")
    if os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") != "0":
        raise ValueError("s4_t04_transport_retries_not_zero")
    with tempfile.TemporaryDirectory(prefix="fin012-s4-t04-r2-exact-") as temporary:
        prepared = prepare_exact_current_input(
            Path(temporary),
            admission,
            issuance,
            execution_identity=execution_identity,
        )
        return execute_bound_s3_t03(
            runtime_root=runtime_root,
            prepared=prepared,
            admission=admission,
            execution_envelope=issuance["execution_envelope"],
            completion=completion,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preflight", "execute", "inspect"))
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    args = parser.parse_args()
    if args.mode == "preflight":
        result = zero_call_preflight()
    elif args.mode == "execute":
        result = execute_exact_once(args.runtime_root.resolve())
    else:
        result = _load(args.runtime_root.resolve() / "execution-result.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"success", "pass_exact_input_admission_transport_wiring_zero_call"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
