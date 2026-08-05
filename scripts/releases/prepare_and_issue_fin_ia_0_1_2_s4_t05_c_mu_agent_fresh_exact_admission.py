from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests" / "contract")]

from apps.workbench.backend.application.bounded_agent_contract_policies import (  # noqa: E402
    FIN_0_1_2_S4_T05_MU_CURRENT_EVIDENCE_PROFILE_REF,
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
from apps.workbench.backend.application.fin_0_1_2_s4_t05_current_case_agent_exact_execution import (  # noqa: E402
    COST_DERIVED_ABSOLUTE_MAXIMUM_INPUT_TOKENS,
    INPUT_CAPACITY_CONTRACT_REF,
    MAXIMUM_INPUT_TOKENS,
    compile_current_case_agent_execution_envelope,
    prepare_current_case_agent_execution,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_three_case_transfer import (  # noqa: E402
    validate_transfer_evidence_pack,
)
from scripts.releases.run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live import _principal  # noqa: E402
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from test_fin_0_1_2_s3_t02_production_runtime_integration import _CurrentS3ProductionFake  # noqa: E402
from test_fin_0_1_2_s4_t05_three_case_current_evidence_transfer import _CurrentVerifierCompiledAtomFake  # noqa: E402


CASE_KEY = "MU"
DECISION_REF = Path("configs/releases/fin_ia_0_1_2_s4_t05_c_mu_agent_fresh_zero_call_proof_and_admission_authority_decision_v1_0.json")
ADMISSION_REF = Path("configs/releases/fin_ia_0_1_2_s4_t05_c_mu_agent_fresh_exact_admission_r1.json")
ISSUANCE_REF = Path("configs/releases/fin_ia_0_1_2_s4_t05_c_mu_agent_fresh_exact_admission_issuance_v1_0.json")
EVIDENCE_PACK_REF = Path("configs/releases/fin_ia_0_1_2_s4_t05_c_mu_current_evidence_pack_v1_0.json")
AGENT_INPUT_REF = Path("configs/releases/fin_ia_0_1_2_s4_t05_c_mu_agent_exact_input_v1_0.json")
MATERIALIZATION_REF = Path("configs/releases/fin_ia_0_1_2_s4_t05_c_mu_current_evidence_and_agent_exact_input_zero_call_materialization_v1_0.json")
TEMPLATE_REF = Path("configs/releases/fin_ia_0_1_2_s4_t04_nvda_current_evidence_capacity_reproof_fresh_exact_admission_r3.json")
EXECUTION_IDENTITY = "fin012-s4-t05c-mu-agent-exact-live-r1"
ADMISSION_ID = "fin012-s4-t05c-mu-agent-fresh-exact-admission-r1"
EXECUTION_MODE = "exact_live_fin_0_1_2_s4_t05_c_mu_current_agent_r1"


class T05CMUAgentAdmissionError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T05CMUAgentAdmissionError(code)


def _load(ref: Path) -> dict[str, Any]:
    value = json.loads((ROOT / ref).read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "s4_t05_c_mu_agent_json_object_required")
    return value


def _sha256(ref: Path) -> str:
    return hashlib.sha256((ROOT / ref).read_bytes()).hexdigest()


def _fake():
    return _CurrentVerifierCompiledAtomFake(_CurrentS3ProductionFake(safe_lead=True))


def _admission(input_pack: S3ThreeCellBoundedAgentInputPack) -> S3ThreeCellBoundedAgentAdmission:
    template = S3ThreeCellBoundedAgentAdmission.model_validate(_load(TEMPLATE_REF))
    admission = template.model_copy(update={
        "admission_id": ADMISSION_ID,
        "execution_mode": EXECUTION_MODE,
        "research_profile_ref": FIN_0_1_2_S4_T05_MU_CURRENT_EVIDENCE_PROFILE_REF,
        "company": CASE_KEY,
        "case_id": input_pack.case_id,
        "case_version": input_pack.case_version,
        "as_of": input_pack.as_of,
        "input_digest": input_pack.input_digest,
    })
    admission.assert_profile_admissible()
    _require(
        admission.model == "deepseek-v4-pro"
        and admission.max_provider_calls == 9
        and admission.retry_budget == 0
        and admission.max_total_cost_usd == 0.06
        and not admission.source_network_calls_allowed
        and not admission.external_tool_calls_allowed
        and not admission.live_business_case_head_writes_allowed,
        "s4_t05_c_mu_agent_admission_contract_invalid",
    )
    return admission


def _project_capacity(input_pack: S3ThreeCellBoundedAgentInputPack, admission: S3ThreeCellBoundedAgentAdmission) -> tuple[tuple[int, ...], dict[str, Any]]:
    fake = _fake()
    output = build_s3_three_cell_bounded_agent_executor_for_admission(admission, chat_completion_fn=fake).execute(
        input_pack,
        admission,
        run_identity={"research_run_id": "mu-capacity-run", "attempt_id": "mu-capacity-attempt"},
    )
    projected = tuple(
        estimate_provider_input_tokens(json.dumps(row["kwargs"]["messages"], ensure_ascii=False, separators=(",", ":")))
        for row in fake.calls
    )
    _require(
        len(projected) == 9
        and len(output.provider_output_captures) == 9
        and len(output.execution_observation["local_fact_receipts"]) == 3
        and len(output.artifacts) == 9
        and sum(projected) <= MAXIMUM_INPUT_TOKENS,
        "s4_t05_c_mu_agent_capacity_invalid",
    )
    return projected, {
        "per_interaction_estimated_input_tokens": list(projected),
        "aggregate_estimated_input_tokens": sum(projected),
        "maximum_single_interaction_estimated_input_tokens": max(projected),
        "input_token_headroom": MAXIMUM_INPUT_TOKENS - sum(projected),
    }


def _normalize(value: Any, replacements: Mapping[str, str]) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _normalize(v, replacements) for k, v in value.items() if k not in {"capture_objects", "terminal_object", "envelope_digest"}}
    if isinstance(value, (list, tuple)):
        return [_normalize(row, replacements) for row in value]
    if isinstance(value, str):
        for old, new in replacements.items():
            value = value.replace(old, new)
    return value


def _fake_chain(root: Path, label: str, input_pack: S3ThreeCellBoundedAgentInputPack, evidence: Mapping[str, Any], admission: S3ThreeCellBoundedAgentAdmission, projected: tuple[int, ...]) -> tuple[dict[str, Any], Mapping[str, str]]:
    identity = f"fin012-s4-t05c-mu-agent-fresh-proof-{label}"
    prepared = prepare_current_case_agent_execution(
        input_pack, evidence, case_key=CASE_KEY, principal=_principal(), execution_identity=identity
    )
    envelope = compile_current_case_agent_execution_envelope(
        prepared, evidence, case_key=CASE_KEY, admission_ref=ADMISSION_REF.as_posix(), projected_per_call_input_tokens=projected
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
        and len(result["artifacts"]) == 9,
        "s4_t05_c_mu_agent_fresh_fake_chain_failed",
    )
    return result, {
        identity: "__execution_identity__",
        prepared.work_unit_id: "__work_unit_id__",
        prepared.attempt_id: "__attempt_id__",
        prepared.research_run_id: "__research_run_id__",
        envelope["envelope_digest"]: "__envelope_digest__",
    }


def build(*, recorded_at: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    input_pack = S3ThreeCellBoundedAgentInputPack.model_validate(_load(AGENT_INPUT_REF))
    evidence = validate_transfer_evidence_pack(_load(EVIDENCE_PACK_REF), case_key=CASE_KEY)
    materialization = _load(MATERIALIZATION_REF)
    _require(
        materialization["compiled_outputs"]["agent_input_digest"] == input_pack.input_digest
        and materialization["compiled_outputs"]["evidence_pack_digest"] == evidence["evidence_pack_digest"],
        "s4_t05_c_mu_materialization_binding_invalid",
    )
    admission = _admission(input_pack)
    previous = os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES")
    os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = "0"
    try:
        projected, capacity = _project_capacity(input_pack, admission)
        with tempfile.TemporaryDirectory(prefix="fin012-s4-t05c-mu-agent-proof-") as raw:
            root = Path(raw)
            first, first_replacements = _fake_chain(root / "a", "a", input_pack, evidence, admission, projected)
            second, second_replacements = _fake_chain(root / "b", "b", input_pack, evidence, admission, projected)
            _require(
                _normalize(first, first_replacements) == _normalize(second, second_replacements),
                "s4_t05_c_mu_agent_fresh_proofs_differ",
            )
    finally:
        if previous is None:
            os.environ.pop("LLM_GATEWAY_TRANSPORT_RETRIES", None)
        else:
            os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = previous
    prepared = prepare_current_case_agent_execution(
        input_pack, evidence, case_key=CASE_KEY, principal=_principal(), execution_identity=EXECUTION_IDENTITY
    )
    envelope = compile_current_case_agent_execution_envelope(
        prepared, evidence, case_key=CASE_KEY, admission_ref=ADMISSION_REF.as_posix(), projected_per_call_input_tokens=projected
    )
    binding_refs = [
        EVIDENCE_PACK_REF,
        AGENT_INPUT_REF,
        MATERIALIZATION_REF,
        TEMPLATE_REF,
        Path("apps/workbench/backend/application/fin_0_1_2_s4_t05_current_case_agent_exact_execution.py"),
        Path("apps/workbench/backend/application/fin_0_1_2_s3_t03_exact_live_runner.py"),
        Path(__file__).resolve().relative_to(ROOT),
        Path("scripts/releases/run_fin_ia_0_1_2_s4_t05_c_mu_agent_exact_live.py"),
    ]
    exact_binding = {
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
    body = {
        "schema_version": "fin_ia_0_1_2_s4_t05_c_mu_agent_fresh_zero_call_proof_and_admission_authority_decision_v1_0",
        "recorded_at": recorded_at,
        "status": "pass_fresh_zero_call_proof_capacity_and_admission_authority",
        "immutable_bindings": [{"ref": ref.as_posix(), "sha256": _sha256(ref)} for ref in binding_refs],
        "exact_binding": exact_binding,
        "runtime_contract": {
            "provider": "deepseek", "model": admission.model, "provider_calls": 9,
            "local_fact_receipts": 3, "captures": 9, "business_artifacts_on_success": 9,
            "retry_budget": 0, "source_network_calls": 0, "external_tool_calls": 0,
        },
        "capacity_proof": {
            **capacity,
            "contract_ref": INPUT_CAPACITY_CONTRACT_REF,
            "maximum_input_tokens": MAXIMUM_INPUT_TOKENS,
            "cost_derived_absolute_maximum_input_tokens": COST_DERIVED_ABSOLUTE_MAXIMUM_INPUT_TOKENS,
            "maximum_output_tokens": 10000,
            "maximum_total_cost_usd": 0.06,
        },
        "fresh_proof": {
            "independent_disposable_roots": 2,
            "normalized_outputs_equal": True,
            "topology_each": [9, 3, 9, 9],
            "model_provider_network_calls": [0, 0, 0],
        },
        "authority_boundary": {
            "user_authorized_sequence_steps_1_to_5": True,
            "admission_issuance_and_one_exact_live_authorized": True,
            "automatic_retry_or_second_live": False,
            "paired_or_owner_auto_authorized": False,
        },
        "next_action": "FIN-0.1.2-S4-T05-C-MU-AGENT-EXACT-LIVE-EXECUTION",
    }
    decision = {**body, "decision_digest": canonical_digest(body)}
    issuance_body = {
        "schema_version": "fin_ia_0_1_2_s4_t05_c_mu_agent_fresh_exact_admission_issuance_v1_0",
        "recorded_at": recorded_at,
        "status": "issued_unconsumed_zero_call_preflight_pass",
        "issued_admission": {
            "admission_id": admission.admission_id,
            "admission_digest": canonical_digest(admission.digest_payload()),
            "admission_ref": ADMISSION_REF.as_posix(),
            "execution_identity": EXECUTION_IDENTITY,
            "consumed": False,
            "execution_started": False,
        },
        "exact_binding": exact_binding,
        "execution_envelope": envelope,
        "authority_decision_ref": DECISION_REF.as_posix(),
        "authority_decision_digest": decision["decision_digest"],
        "observed_counts": {"model_calls": 0, "provider_calls": 0, "network_calls": 0, "business_artifacts": 0},
    }
    issuance = {**issuance_body, "issuance_digest": canonical_digest(issuance_body)}
    return decision, admission.model_dump(mode="json"), issuance


def _write(ref: Path, payload: Mapping[str, Any]) -> str:
    path = ROOT / ref
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        _require(path.read_text(encoding="utf-8") == rendered, f"s4_t05_c_mu_agent_existing_output_mismatch:{ref}")
        return "exact_existing_reused"
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(rendered, encoding="utf-8")
    os.replace(temp, path)
    return "created"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("proof", "issue"))
    parser.add_argument("--recorded-at", required=True)
    args = parser.parse_args()
    decision, admission, issuance = build(recorded_at=args.recorded_at)
    result = {
        "status": decision["status"],
        "capacity_proof": decision["capacity_proof"],
        "fresh_proof": decision["fresh_proof"],
        "admission_issued": False,
    }
    if args.mode == "issue":
        result.update({
            "status": "pass_proof_and_admission_issued_unconsumed",
            "write_statuses": {
                "decision": _write(DECISION_REF, decision),
                "admission": _write(ADMISSION_REF, admission),
                "issuance": _write(ISSUANCE_REF, issuance),
            },
            "admission_digest": issuance["issued_admission"]["admission_digest"],
            "issuance_digest": issuance["issuance_digest"],
            "execution_identity": EXECUTION_IDENTITY,
        })
    result["next_action"] = decision["next_action"]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
