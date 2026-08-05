from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentInputPack,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.fin_0_1_2_s3_t03_exact_live_runner import (  # noqa: E402
    execute_bound_s3_t03,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_b_agent_exact_execution import (  # noqa: E402
    INPUT_CAPACITY_CONTRACT_REF,
    MAXIMUM_INPUT_TOKENS,
    prepare_t05_b_dell_agent_execution,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_three_case_transfer import (  # noqa: E402
    validate_transfer_evidence_pack,
)
from scripts.releases.run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live import (  # noqa: E402
    _default_completion,
    _principal,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_agent_fresh_zero_call_"
    "proof_and_admission_authority_decision_v1_0.json"
)
ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_agent_fresh_exact_"
    "admission_r1.json"
)
ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_agent_fresh_exact_"
    "admission_issuance_v1_0.json"
)
EVIDENCE_PACK = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_current_evidence_pack_v1_0.json"
)
AGENT_INPUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_agent_exact_input_v1_0.json"
)
EXECUTION_IDENTITY = "fin012-s4-t05b-dell-agent-exact-live-r1"
DEFAULT_RUNTIME_ROOT = ROOT / (
    ".codex_runtime/fin012-s4-t05b-dell-agent-exact-live-r1"
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("s4_t05_b_agent_json_object_required")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_exact_target() -> tuple[
    S3ThreeCellBoundedAgentAdmission,
    dict[str, Any],
    S3ThreeCellBoundedAgentInputPack,
    dict[str, Any],
]:
    decision = _load(DECISION)
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(_load(ADMISSION))
    input_pack = S3ThreeCellBoundedAgentInputPack.model_validate(_load(AGENT_INPUT))
    evidence_pack = validate_transfer_evidence_pack(
        _load(EVIDENCE_PACK), case_key="DELL"
    )
    if decision.get("decision_digest") != canonical_digest(
        {key: value for key, value in decision.items() if key != "decision_digest"}
    ):
        raise ValueError("s4_t05_b_agent_decision_digest_mismatch")
    for binding in decision["immutable_bindings"]:
        if _sha256(ROOT / binding["ref"]) != binding["sha256"]:
            raise ValueError(
                f"s4_t05_b_agent_code_or_input_drift:{binding['ref']}"
            )
    admission.assert_profile_admissible()
    admission_digest = canonical_digest(admission.digest_payload())
    if (
        decision.get("status")
        != "pass_fresh_zero_call_proof_capacity_and_admission_authority"
        or issuance.get("status") != "issued_unconsumed_zero_call_preflight_pass"
        or issuance.get("issuance_digest")
        != canonical_digest(
            {key: value for key, value in issuance.items() if key != "issuance_digest"}
        )
        or issuance["issued_admission"]["admission_digest"] != admission_digest
        or issuance["issued_admission"]["execution_identity"]
        != EXECUTION_IDENTITY
        or issuance["issued_admission"]["consumed"] is not False
        or issuance["issued_admission"]["execution_started"] is not False
        or admission.input_digest != input_pack.input_digest
        or admission.case_id != input_pack.case_id
        or admission.company != "DELL"
        or admission.max_provider_calls != 9
        or admission.retry_budget != 0
        or admission.max_total_cost_usd != 0.06
        or issuance["execution_envelope"]["input_capacity_contract"][
            "contract_ref"
        ]
        != INPUT_CAPACITY_CONTRACT_REF
        or issuance["execution_envelope"]["hard_budget"][
            "maximum_input_tokens"
        ]
        != MAXIMUM_INPUT_TOKENS
        or evidence_pack["evidence_pack_digest"]
        != input_pack.lineage["S4_T04_source_grounded_input"]["digest"]
    ):
        raise ValueError("s4_t05_b_agent_exact_target_drift")
    return admission, issuance, input_pack, evidence_pack


def prepare_exact_target():
    admission, issuance, input_pack, evidence_pack = load_exact_target()
    prepared = prepare_t05_b_dell_agent_execution(
        input_pack,
        evidence_pack,
        principal=_principal(),
        execution_identity=EXECUTION_IDENTITY,
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
        "evidence_pack_digest": evidence_pack["evidence_pack_digest"],
        "t03_terminal_digest": evidence_pack["t03_terminal_digest"],
    }
    if observed != expected:
        raise ValueError("s4_t05_b_agent_exact_input_rehydrate_drift")
    return admission, issuance, prepared


def zero_call_preflight() -> dict[str, Any]:
    admission, issuance, prepared = prepare_exact_target()
    calls = 0

    def forbidden(**_: Any) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        raise AssertionError("s4_t05_b_agent_preflight_provider_forbidden")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=forbidden
    )
    capacity = issuance["execution_envelope"]["input_capacity_contract"]
    return {
        "schema_version": (
            "fin_ia_0_1_2_s4_t05_b_dell_agent_exact_live_preflight_v1_0"
        ),
        "status": "pass_exact_input_admission_transport_wiring_zero_call",
        "execution_identity": prepared.execution_identity,
        "input_digest": prepared.input_digest,
        "admission_digest": canonical_digest(admission.digest_payload()),
        "envelope_digest": issuance["execution_envelope"]["envelope_digest"],
        "aggregate_estimated_input_tokens": capacity[
            "aggregate_estimated_input_tokens"
        ],
        "maximum_input_tokens": capacity["maximum_input_tokens"],
        "input_token_headroom": capacity["input_token_headroom"],
        "provider_callback_calls": calls,
        "model_provider_network_calls": [0, 0, 0],
        "credential_present": bool(os.environ.get(admission.api_key_env or "")),
        "credential_value_output_or_persisted": False,
        "provider_health_probe_performed": False,
    }


def execute_exact_once(
    runtime_root: Path,
    *,
    completion: Callable[..., Mapping[str, Any]] = _default_completion,
) -> dict[str, Any]:
    admission, issuance, prepared = prepare_exact_target()
    if runtime_root.exists():
        raise ValueError("s4_t05_b_agent_runtime_identity_already_exists")
    if not os.environ.get(admission.api_key_env or ""):
        raise ValueError("s4_t05_b_agent_provider_credential_missing")
    if os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") != "0":
        raise ValueError("s4_t05_b_agent_transport_retries_not_zero")
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
    return 0 if result.get("status") in {
        "success",
        "pass_exact_input_admission_transport_wiring_zero_call",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
