from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping
import sys


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
from apps.workbench.backend.application.fin_0_1_2_s4_t05_current_case_agent_exact_execution import (  # noqa: E402
    INPUT_CAPACITY_CONTRACT_REF,
    MAXIMUM_INPUT_TOKENS,
    prepare_current_case_agent_execution,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_three_case_transfer import (  # noqa: E402
    validate_transfer_evidence_pack,
)
from scripts.releases.prepare_and_issue_fin_ia_0_1_2_s4_t05_d_nvda_post_transfer_agent_fresh_exact_admission import (  # noqa: E402
    ADMISSION_REF,
    AGENT_INPUT_REF,
    CASE_KEY,
    DECISION_REF,
    EVIDENCE_PACK_REF,
    EXECUTION_IDENTITY,
    ISSUANCE_REF,
)
from scripts.releases.run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live import (  # noqa: E402
    _default_completion,
    _principal,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


DEFAULT_RUNTIME_ROOT = ROOT / (
    ".codex_runtime/fin012-s4-t05d-nvda-post-transfer-agent-exact-live-r1"
)


def _load(ref: Path) -> dict[str, Any]:
    value = json.loads((ROOT / ref).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("s4_t05_d_nvda_agent_json_object_required")
    return value


def _sha256(ref: str) -> str:
    return hashlib.sha256((ROOT / ref).read_bytes()).hexdigest()


def prepare_target():
    decision = _load(DECISION_REF)
    issuance = _load(ISSUANCE_REF)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(_load(ADMISSION_REF))
    input_pack = S3ThreeCellBoundedAgentInputPack.model_validate(_load(AGENT_INPUT_REF))
    evidence = validate_transfer_evidence_pack(
        _load(EVIDENCE_PACK_REF), case_key=CASE_KEY
    )
    if decision["decision_digest"] != canonical_digest(
        {key: value for key, value in decision.items() if key != "decision_digest"}
    ):
        raise ValueError("s4_t05_d_nvda_agent_decision_digest_mismatch")
    for binding in decision["immutable_bindings"]:
        if _sha256(binding["ref"]) != binding["sha256"]:
            raise ValueError(
                f"s4_t05_d_nvda_agent_binding_drift:{binding['ref']}"
            )
    if (
        issuance["issuance_digest"]
        != canonical_digest(
            {
                key: value
                for key, value in issuance.items()
                if key != "issuance_digest"
            }
        )
        or issuance["issued_admission"]["admission_digest"]
        != canonical_digest(admission.digest_payload())
        or issuance["issued_admission"]["execution_identity"]
        != EXECUTION_IDENTITY
        or issuance["issued_admission"]["consumed"] is not False
        or admission.company != CASE_KEY
        or admission.input_digest != input_pack.input_digest
        or admission.max_provider_calls != 9
        or admission.retry_budget != 0
        or issuance["execution_envelope"]["input_capacity_contract"][
            "contract_ref"
        ]
        != INPUT_CAPACITY_CONTRACT_REF
        or issuance["execution_envelope"]["hard_budget"]["maximum_input_tokens"]
        != MAXIMUM_INPUT_TOKENS
        or evidence["evidence_pack_digest"]
        != input_pack.lineage["T04_financial_pack"]["digest"]
    ):
        raise ValueError("s4_t05_d_nvda_agent_exact_target_drift")
    prepared = prepare_current_case_agent_execution(
        input_pack,
        evidence,
        case_key=CASE_KEY,
        principal=_principal(),
        execution_identity=EXECUTION_IDENTITY,
    )
    expected = decision["exact_binding"]
    observed = {
        "case_id": prepared.case_id,
        "case_version": prepared.case_version,
        "as_of": prepared.input_pack.as_of,
        "complete_input_digest": prepared.input_digest,
        "preparation_digest": prepared.preparation_digest,
        "predicted_work_unit_id": prepared.work_unit_id,
        "predicted_attempt_id": prepared.attempt_id,
        "predicted_research_run_id": prepared.research_run_id,
        "evidence_pack_digest": evidence["evidence_pack_digest"],
        "t03_terminal_digest": evidence["t03_terminal_digest"],
    }
    if observed != expected:
        raise ValueError("s4_t05_d_nvda_agent_exact_rehydrate_drift")
    return admission, issuance, prepared


def zero_call_preflight() -> dict[str, Any]:
    admission, issuance, prepared = prepare_target()
    calls = 0

    def forbidden(**_: Any) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        raise AssertionError("s4_t05_d_nvda_provider_forbidden_in_preflight")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=forbidden
    )
    capacity = issuance["execution_envelope"]["input_capacity_contract"]
    return {
        "status": "pass_exact_input_admission_transport_wiring_zero_call",
        "execution_identity": prepared.execution_identity,
        "input_digest": prepared.input_digest,
        "admission_digest": canonical_digest(admission.digest_payload()),
        "aggregate_estimated_input_tokens": capacity[
            "aggregate_estimated_input_tokens"
        ],
        "input_token_headroom": capacity["input_token_headroom"],
        "provider_callback_calls": calls,
        "credential_present": bool(os.environ.get(admission.api_key_env or "")),
        "credential_value_output_or_persisted": False,
    }


def execute(runtime_root: Path) -> dict[str, Any]:
    admission, issuance, prepared = prepare_target()
    if runtime_root.exists():
        raise ValueError("s4_t05_d_nvda_agent_runtime_identity_already_exists")
    if not os.environ.get(admission.api_key_env or ""):
        raise ValueError("s4_t05_d_nvda_agent_provider_credential_missing")
    if os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") != "0":
        raise ValueError("s4_t05_d_nvda_agent_transport_retries_not_zero")
    return execute_bound_s3_t03(
        runtime_root=runtime_root,
        prepared=prepared,
        admission=admission,
        execution_envelope=issuance["execution_envelope"],
        completion=_default_completion,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preflight", "execute", "inspect"))
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    args = parser.parse_args()
    if args.mode == "preflight":
        result = zero_call_preflight()
    elif args.mode == "execute":
        result = execute(args.runtime_root.resolve())
    else:
        result = json.loads(
            (args.runtime_root.resolve() / "execution-result.json").read_text(
                encoding="utf-8"
            )
        )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result.get("status") in {
        "success",
        "pass_exact_input_admission_transport_wiring_zero_call",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
