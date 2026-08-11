from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "src"),
    str(ROOT / "tests" / "contract"),
]

from apps.workbench.backend.application.bounded_agent_contract_policies import (  # noqa: E402
    FIN_0_1_2_S4_T05_DELL_CURRENT_EVIDENCE_PROFILE_REF,
    estimate_provider_input_tokens,
)
from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentInputPack,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.fin_0_1_2_s3_t03_exact_live_runner import (  # noqa: E402
    execute_bound_s3_t03,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_b_agent_exact_execution import (  # noqa: E402
    COST_DERIVED_ABSOLUTE_MAXIMUM_INPUT_TOKENS,
    INPUT_CAPACITY_CONTRACT_REF,
    MAXIMUM_INPUT_TOKENS,
    compile_t05_b_dell_agent_execution_envelope,
    prepare_t05_b_dell_agent_execution,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_three_case_transfer import (  # noqa: E402
    validate_transfer_evidence_pack,
)
from scripts.releases.run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live import (  # noqa: E402
    _principal,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from test_fin_0_1_2_s3_t02_production_runtime_integration import (  # noqa: E402
    _CurrentS3ProductionFake,
)
from test_fin_0_1_2_s4_t05_three_case_current_evidence_transfer import (  # noqa: E402
    _CurrentVerifierCompiledAtomFake,
)


DECISION_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_agent_fresh_zero_call_"
    "proof_and_admission_authority_decision_v1_0.json"
)
ADMISSION_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_agent_fresh_exact_"
    "admission_r1.json"
)
ISSUANCE_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_agent_fresh_exact_"
    "admission_issuance_v1_0.json"
)
EVIDENCE_PACK_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_current_evidence_pack_v1_0.json"
)
AGENT_INPUT_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_agent_exact_input_v1_0.json"
)
MATERIALIZATION_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_current_evidence_and_"
    "agent_exact_input_zero_call_materialization_v1_0.json"
)
TEMPLATE_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t04_nvda_current_evidence_capacity_"
    "reproof_fresh_exact_admission_r3.json"
)
RUNNER_REF = Path(
    "scripts/releases/run_fin_ia_0_1_2_s4_t05_b_dell_agent_exact_live.py"
)
EXECUTION_MODULE_REF = Path(
    "apps/workbench/backend/application/"
    "fin_0_1_2_s4_t05_b_agent_exact_execution.py"
)
EXACT_RUNNER_REF = Path(
    "apps/workbench/backend/application/fin_0_1_2_s3_t03_exact_live_runner.py"
)
BOUNDED_EXECUTOR_REF = Path(
    "apps/workbench/backend/application/bounded_agent_executor.py"
)
EXECUTION_IDENTITY = "fin012-s4-t05b-dell-agent-exact-live-r1"
ADMISSION_ID = "fin012-s4-t05b-dell-agent-fresh-exact-admission-r1"
EXECUTION_MODE = "exact_live_fin_0_1_2_s4_t05_b_dell_current_agent_r1"
NEXT_ACTION = (
    "FIN-0.1.2-S4-T05-B-DELL-AGENT-EXACT-LIVE-EXECUTION-AND-TERMINAL-"
    "MATERIALIZATION"
)


class T05BAgentAdmissionError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T05BAgentAdmissionError(code)


def _load(ref: Path) -> dict[str, Any]:
    value = json.loads((ROOT / ref).read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "s4_t05_b_agent_json_object_required")
    return value


def _sha256(ref: Path) -> str:
    return hashlib.sha256((ROOT / ref).read_bytes()).hexdigest()


def _fake():
    return _CurrentVerifierCompiledAtomFake(
        _CurrentS3ProductionFake(safe_lead=True)
    )


def _formal_admission(
    input_pack: S3ThreeCellBoundedAgentInputPack,
) -> S3ThreeCellBoundedAgentAdmission:
    template = S3ThreeCellBoundedAgentAdmission.model_validate(_load(TEMPLATE_REF))
    admission = template.model_copy(
        update={
            "admission_id": ADMISSION_ID,
            "execution_mode": EXECUTION_MODE,
            "research_profile_ref": (
                FIN_0_1_2_S4_T05_DELL_CURRENT_EVIDENCE_PROFILE_REF
            ),
            "company": "DELL",
            "case_id": input_pack.case_id,
            "case_version": input_pack.case_version,
            "as_of": input_pack.as_of,
            "input_digest": input_pack.input_digest,
        }
    )
    admission.assert_profile_admissible()
    _require(
        admission.model == "deepseek-v4-pro"
        and admission.transport_ref.endswith(":v9")
        and admission.research_lead_transport_ref.endswith(":v8")
        and admission.local_fact_interaction_contract_ref is not None
        and admission.max_provider_calls == 9
        and admission.max_semantic_model_calls == 9
        and admission.max_network_calls == 9
        and admission.max_transport_attempts_per_call == 1
        and admission.retry_budget == 0
        and admission.max_total_cost_usd == 0.06
        and not admission.source_network_calls_allowed
        and not admission.external_tool_calls_allowed
        and not admission.live_business_case_head_writes_allowed,
        "s4_t05_b_agent_admission_runtime_or_budget_drift",
    )
    return admission


def _capacity_projection(
    input_pack: S3ThreeCellBoundedAgentInputPack,
    admission: S3ThreeCellBoundedAgentAdmission,
) -> tuple[tuple[int, ...], dict[str, Any]]:
    fake = _fake()
    output = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=fake
    ).execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": "fresh-proof-capacity-run",
            "attempt_id": "fresh-proof-capacity-attempt",
        },
    )
    projected = tuple(
        estimate_provider_input_tokens(
            json.dumps(
                row["kwargs"]["messages"],
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        for row in fake.calls
    )
    _require(
        len(projected) == 9
        and len(output.provider_output_captures) == 9
        and len(output.execution_observation.get("local_fact_receipts") or ()) == 3
        and len(output.artifacts) == 9
        and sum(projected) <= MAXIMUM_INPUT_TOKENS,
        "s4_t05_b_agent_capacity_fake_topology_or_budget_invalid",
    )
    return projected, {
        "per_interaction_estimated_input_tokens": list(projected),
        "aggregate_estimated_input_tokens": sum(projected),
        "maximum_single_interaction_estimated_input_tokens": max(projected),
        "input_token_headroom": MAXIMUM_INPUT_TOKENS - sum(projected),
        "provider_callbacks": len(fake.calls),
        "local_fact_receipts": len(
            output.execution_observation.get("local_fact_receipts") or ()
        ),
        "artifacts": len(output.artifacts),
    }


def _normalized(value: Any, replacements: Mapping[str, str]) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _normalized(row, replacements)
            for key, row in value.items()
            if key not in {"capture_objects", "envelope_digest", "terminal_object"}
        }
    if isinstance(value, (list, tuple)):
        return [_normalized(row, replacements) for row in value]
    if isinstance(value, str):
        result = value
        for old, new in replacements.items():
            result = result.replace(old, new)
        return result
    return value


def _run_fake_proof(
    *,
    root: Path,
    label: str,
    input_pack: S3ThreeCellBoundedAgentInputPack,
    evidence_pack: Mapping[str, Any],
    admission: S3ThreeCellBoundedAgentAdmission,
    projected: tuple[int, ...],
) -> tuple[dict[str, Any], dict[str, str], list[dict[str, Any]]]:
    identity = f"fin012-s4-t05b-dell-agent-fresh-proof-{label}"
    prepared = prepare_t05_b_dell_agent_execution(
        input_pack,
        evidence_pack,
        principal=_principal(),
        execution_identity=identity,
    )
    envelope = compile_t05_b_dell_agent_execution_envelope(
        prepared,
        evidence_pack,
        admission_ref=ADMISSION_REF.as_posix(),
        projected_per_call_input_tokens=projected,
    )
    result = execute_bound_s3_t03(
        runtime_root=root,
        prepared=prepared,
        admission=admission,
        execution_envelope=envelope,
        completion=_fake(),
    )
    _require(
        result["status"] == "success"
        and len(result["capture_objects"]) == 9
        and len(result["terminal"]["local_fact_receipts"]) == 3
        and len(result["artifacts"]) == 9
        and result["business_promotable"] is True,
        "s4_t05_b_agent_fresh_fake_chain_failed",
    )
    replacements = {
        identity: "__execution_identity__",
        prepared.work_unit_id: "__work_unit_id__",
        prepared.attempt_id: "__attempt_id__",
        prepared.research_run_id: "__research_run_id__",
        envelope["envelope_digest"]: "__envelope_digest__",
    }
    capture_payloads = [
        json.loads(
            (
                root
                / "restricted-audit-objects"
                / capture["object_key"]
            ).read_text(encoding="utf-8")
        )
        for capture in result["capture_objects"]
    ]
    return result, replacements, capture_payloads


def build_proof(*, recorded_at: str) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    input_pack = S3ThreeCellBoundedAgentInputPack.model_validate(
        _load(AGENT_INPUT_REF)
    )
    evidence_pack = validate_transfer_evidence_pack(
        _load(EVIDENCE_PACK_REF), case_key="DELL"
    )
    materialization = _load(MATERIALIZATION_REF)
    _require(
        materialization["compiled_outputs"]["agent_input_digest"]
        == input_pack.input_digest
        and materialization["compiled_outputs"]["evidence_pack_digest"]
        == evidence_pack["evidence_pack_digest"],
        "s4_t05_b_agent_materialization_binding_drift",
    )
    admission = _formal_admission(input_pack)
    previous_retry = os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES")
    os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = "0"
    try:
        projected, capacity = _capacity_projection(input_pack, admission)
        with tempfile.TemporaryDirectory(
            prefix="fin012-s4-t05b-dell-agent-proof-"
        ) as temporary:
            proof_root = Path(temporary)
            first, first_replacements, first_captures = _run_fake_proof(
                root=proof_root / "a",
                label="a",
                input_pack=input_pack,
                evidence_pack=evidence_pack,
                admission=admission,
                projected=projected,
            )
            second, second_replacements, second_captures = _run_fake_proof(
                root=proof_root / "b",
                label="b",
                input_pack=input_pack,
                evidence_pack=evidence_pack,
                admission=admission,
                projected=projected,
            )
            _require(
                _normalized(first, first_replacements)
                == _normalized(second, second_replacements),
                "s4_t05_b_agent_independent_fresh_proofs_differ",
            )
            _require(
                _normalized(first_captures, first_replacements)
                == _normalized(second_captures, second_replacements),
                "s4_t05_b_agent_independent_capture_payloads_differ",
            )
    finally:
        if previous_retry is None:
            os.environ.pop("LLM_GATEWAY_TRANSPORT_RETRIES", None)
        else:
            os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = previous_retry

    formal_prepared = prepare_t05_b_dell_agent_execution(
        input_pack,
        evidence_pack,
        principal=_principal(),
        execution_identity=EXECUTION_IDENTITY,
    )
    envelope = compile_t05_b_dell_agent_execution_envelope(
        formal_prepared,
        evidence_pack,
        admission_ref=ADMISSION_REF.as_posix(),
        projected_per_call_input_tokens=projected,
    )
    bindings = [
        {"ref": ref.as_posix(), "sha256": _sha256(ref)}
        for ref in (
            EVIDENCE_PACK_REF,
            AGENT_INPUT_REF,
            MATERIALIZATION_REF,
            TEMPLATE_REF,
            EXECUTION_MODULE_REF,
            EXACT_RUNNER_REF,
            BOUNDED_EXECUTOR_REF,
            RUNNER_REF,
            Path(__file__).resolve().relative_to(ROOT),
        )
    ]
    decision_body = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t05_b_dell_agent_fresh_zero_call_proof_and_"
            "admission_authority_decision_v1_0"
        ),
        "decision_id": (
            "FIN-0.1.2-S4-T05-B-DELL-AGENT-FRESH-PROOF-CAPACITY-AND-"
            "ADMISSION-AUTHORITY"
        ),
        "recorded_at": recorded_at,
        "status": "pass_fresh_zero_call_proof_capacity_and_admission_authority",
        "immutable_bindings": bindings,
        "exact_binding": {
            "case_id": formal_prepared.case_id,
            "case_version": formal_prepared.case_version,
            "as_of": formal_prepared.input_pack.as_of,
            "complete_input_digest": formal_prepared.input_digest,
            "preparation_digest": formal_prepared.preparation_digest,
            "predicted_work_unit_id": formal_prepared.work_unit_id,
            "predicted_attempt_id": formal_prepared.attempt_id,
            "predicted_research_run_id": formal_prepared.research_run_id,
            "execution_identity": EXECUTION_IDENTITY,
            "evidence_pack_digest": evidence_pack["evidence_pack_digest"],
            "t03_terminal_digest": evidence_pack["t03_terminal_digest"],
        },
        "runtime_contract": {
            "provider": "deepseek",
            "model": admission.model,
            "transport_ref": admission.transport_ref,
            "research_lead_transport_ref": admission.research_lead_transport_ref,
            "local_fact_interaction_contract_ref": (
                admission.local_fact_interaction_contract_ref
            ),
            "provider_calls": 9,
            "local_fact_receipts": 3,
            "captures": 9,
            "business_artifacts_on_success": 9,
            "retry_budget": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
        },
        "capacity_proof": {
            **capacity,
            "contract_ref": INPUT_CAPACITY_CONTRACT_REF,
            "maximum_input_tokens": MAXIMUM_INPUT_TOKENS,
            "cost_derived_absolute_maximum_input_tokens": (
                COST_DERIVED_ABSOLUTE_MAXIMUM_INPUT_TOKENS
            ),
            "maximum_output_tokens": 10000,
            "maximum_total_cost_usd": 0.06,
        },
        "fresh_proof": {
            "independent_disposable_roots": 2,
            "distinct_execution_identities": True,
            "normalized_outputs_equal": True,
            "topology_each": [9, 3, 9],
            "credential_value_read_or_persisted": False,
            "external_model_provider_network_calls": [0, 0, 0],
        },
        "authority_boundary": {
            "user_authorized_issue_and_execute_if_proof_passes": True,
            "admission_issuance_authorized": True,
            "exact_live_execution_authorized_after_clean_synced_preflight": True,
            "automatic_retry_or_second_live": False,
            "paired_or_owner_auto_authorized": False,
        },
        "stage_truth": {
            "S4_T05_B_DELL_Agent_fresh_proof": "pass_zero_call",
            "S4_T05_B_DELL_Agent_live": "not_started",
            "DELL_current_R2": False,
        },
        "next_action": NEXT_ACTION,
    }
    decision = {
        **decision_body,
        "decision_digest": canonical_digest(decision_body),
    }
    admission_payload = admission.model_dump(mode="json")
    admission_digest = canonical_digest(admission.digest_payload())
    issuance_body = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t05_b_dell_agent_fresh_exact_admission_"
            "issuance_v1_0"
        ),
        "status": "issued_unconsumed_zero_call_preflight_pass",
        "issued_admission": {
            "admission_id": admission.admission_id,
            "admission_digest": admission_digest,
            "admission_ref": ADMISSION_REF.as_posix(),
            "execution_identity": EXECUTION_IDENTITY,
            "consumed": False,
            "execution_started": False,
        },
        "exact_binding": {
            key: value
            for key, value in decision["exact_binding"].items()
            if key != "execution_identity"
        },
        "execution_envelope": envelope,
        "authority_decision_ref": DECISION_REF.as_posix(),
        "authority_decision_digest": decision["decision_digest"],
        "observed_counts": {
            "credential_value_reads_or_probes": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "business_artifacts": 0,
        },
        "authority_boundary": decision["authority_boundary"],
    }
    issuance = {
        **issuance_body,
        "issuance_digest": canonical_digest(issuance_body),
    }
    return decision, admission_payload, issuance


def _write_exact_or_reuse(ref: Path, payload: Mapping[str, Any]) -> str:
    path = ROOT / ref
    rendered = json.dumps(
        payload, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"
    if path.exists():
        _require(
            path.read_text(encoding="utf-8") == rendered,
            f"s4_t05_b_agent_existing_output_mismatch:{ref.as_posix()}",
        )
        return "exact_existing_reused"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(rendered, encoding="utf-8")
    os.replace(temporary, path)
    return "created"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("proof", "issue"))
    parser.add_argument("--recorded-at", required=True)
    args = parser.parse_args()
    decision, admission, issuance = build_proof(recorded_at=args.recorded_at)
    if args.mode == "proof":
        result = {
            "status": decision["status"],
            "decision_digest": decision["decision_digest"],
            "capacity_proof": decision["capacity_proof"],
            "fresh_proof": decision["fresh_proof"],
            "admission_issued": False,
            "next_action": "admission_issuance",
        }
    else:
        result = {
            "status": "pass_proof_and_admission_issued_unconsumed",
            "write_statuses": {
                "decision": _write_exact_or_reuse(DECISION_REF, decision),
                "admission": _write_exact_or_reuse(ADMISSION_REF, admission),
                "issuance": _write_exact_or_reuse(ISSUANCE_REF, issuance),
            },
            "decision_digest": decision["decision_digest"],
            "admission_digest": issuance["issued_admission"][
                "admission_digest"
            ],
            "issuance_digest": issuance["issuance_digest"],
            "execution_identity": EXECUTION_IDENTITY,
            "consumed": False,
            "next_action": NEXT_ACTION,
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
