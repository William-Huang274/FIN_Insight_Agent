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
    FIN_0_1_2_S4_T05_NVDA_CURRENT_EVIDENCE_PROFILE_REF,
    estimate_provider_input_tokens,
)
from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentInputPack,
    build_s3_three_cell_bounded_agent_executor_for_admission,
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
from scripts.releases.audit_fin_ia_0_1_2_s4_t05_d_post_transfer_nvda_entry_and_dependency import (  # noqa: E402
    _fake,
    _normalize,
    _principal,
    _run_fake_chain,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402


CASE_KEY = "NVDA"
ENTRY_DECISION_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_d_post_transfer_nvda_entry_"
    "and_dependency_decision_v1_0.json"
)
EVIDENCE_PACK_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t04_nvda_current_evidence_pack_v1_0.json"
)
AGENT_INPUT_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_d_nvda_post_transfer_agent_"
    "exact_input_v1_0.json"
)
TEMPLATE_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t04_nvda_current_evidence_capacity_"
    "reproof_fresh_exact_admission_r3.json"
)
DECISION_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_d_nvda_agent_fresh_zero_call_"
    "proof_and_admission_authority_decision_v1_0.json"
)
ADMISSION_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_d_nvda_agent_fresh_exact_"
    "admission_r1.json"
)
ISSUANCE_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_d_nvda_agent_fresh_exact_"
    "admission_issuance_v1_0.json"
)
RUNNER_REF = Path(
    "scripts/releases/run_fin_ia_0_1_2_s4_t05_d_nvda_post_transfer_agent_"
    "exact_live.py"
)
EXECUTION_MODULE_REF = Path(
    "apps/workbench/backend/application/"
    "fin_0_1_2_s4_t05_current_case_agent_exact_execution.py"
)
EXACT_RUNNER_REF = Path(
    "apps/workbench/backend/application/fin_0_1_2_s3_t03_exact_live_runner.py"
)
EXECUTION_IDENTITY = "fin012-s4-t05d-nvda-post-transfer-agent-exact-live-r1"
ADMISSION_ID = "fin012-s4-t05d-nvda-post-transfer-agent-fresh-exact-admission-r1"
EXECUTION_MODE = "exact_live_fin_0_1_2_s4_t05_d_nvda_post_transfer_agent_r1"
RUN_SCOPE = (
    "FIN-0.1.2-S4-T05-D-POST-TRANSFER-NVDA-AGENT-EXACT-LIVE-EXECUTION"
)
NEXT_ACTION = RUN_SCOPE


class T05DNVDAAdmissionError(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T05DNVDAAdmissionError(code)


def _load(ref: Path) -> dict[str, Any]:
    value = json.loads((ROOT / ref).read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"s4_t05_d_nvda_json_object_required:{ref}")
    return value


def _sha256(ref: Path) -> str:
    return hashlib.sha256((ROOT / ref).read_bytes()).hexdigest()


def _admission(
    input_pack: S3ThreeCellBoundedAgentInputPack,
) -> S3ThreeCellBoundedAgentAdmission:
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(TEMPLATE_REF)
    ).model_copy(
        update={
            "admission_id": ADMISSION_ID,
            "execution_mode": EXECUTION_MODE,
            "research_profile_ref": (
                FIN_0_1_2_S4_T05_NVDA_CURRENT_EVIDENCE_PROFILE_REF
            ),
            "company": CASE_KEY,
            "case_id": input_pack.case_id,
            "case_version": input_pack.case_version,
            "as_of": input_pack.as_of,
            "input_digest": input_pack.input_digest,
        }
    )
    admission.assert_profile_admissible()
    _require(
        admission.model == "deepseek-v4-pro"
        and admission.max_provider_calls == 9
        and admission.max_semantic_model_calls == 9
        and admission.max_network_calls == 9
        and admission.max_transport_attempts_per_call == 1
        and admission.retry_budget == 0
        and admission.max_total_cost_usd == 0.06
        and not admission.source_network_calls_allowed
        and not admission.external_tool_calls_allowed
        and not admission.live_business_case_head_writes_allowed,
        "s4_t05_d_nvda_admission_contract_invalid",
    )
    return admission


def _capacity(
    input_pack: S3ThreeCellBoundedAgentInputPack,
    admission: S3ThreeCellBoundedAgentAdmission,
) -> tuple[tuple[int, ...], dict[str, Any]]:
    fake = _fake()
    output = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    ).execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": "t05d-nvda-capacity-run",
            "attempt_id": "t05d-nvda-capacity-attempt",
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
        "s4_t05_d_nvda_capacity_or_topology_invalid",
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


def build(
    *, recorded_at: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    entry = _load(ENTRY_DECISION_REF)
    evidence = validate_transfer_evidence_pack(
        _load(EVIDENCE_PACK_REF), case_key=CASE_KEY
    )
    input_pack = S3ThreeCellBoundedAgentInputPack.model_validate(
        _load(AGENT_INPUT_REF)
    )
    _require(
        entry["decision_digest"]
        == canonical_digest(
            {key: value for key, value in entry.items() if key != "decision_digest"}
        )
        and entry["compiled_post_transfer_input"]["input_digest"]
        == input_pack.input_digest
        and entry["search_and_evidence_reuse_decision"]["evidence_pack_digest"]
        == evidence["evidence_pack_digest"]
        and input_pack.lineage["T04_financial_pack"]["digest"]
        == evidence["evidence_pack_digest"],
        "s4_t05_d_nvda_entry_input_evidence_binding_invalid",
    )
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    _require(
        preflight.get("status") == "pass"
        and preflight.get("open_full_chain_blockers") == [],
        "s4_t05_d_nvda_project_os_preflight_failed",
    )
    admission = _admission(input_pack)
    previous = os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES")
    os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = "0"
    try:
        projected, capacity = _capacity(input_pack, admission)
        with tempfile.TemporaryDirectory(
            prefix="fin012-s4-t05d-nvda-formal-proof-"
        ) as name:
            root = Path(name)
            first = _run_fake_chain(
                root / "a",
                label="formal-a",
                agent_input=input_pack.model_dump(mode="json"),
                evidence=evidence,
                admission=admission,
                projected=projected,
            )
            second = _run_fake_chain(
                root / "b",
                label="formal-b",
                agent_input=input_pack.model_dump(mode="json"),
                evidence=evidence,
                admission=admission,
                projected=projected,
            )
        _require(
            _normalize(first, {}) == _normalize(second, {}),
            "s4_t05_d_nvda_fresh_proofs_differ",
        )
    finally:
        if previous is None:
            os.environ.pop("LLM_GATEWAY_TRANSPORT_RETRIES", None)
        else:
            os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = previous
    prepared = prepare_current_case_agent_execution(
        input_pack,
        evidence,
        case_key=CASE_KEY,
        principal=_principal(),
        execution_identity=EXECUTION_IDENTITY,
    )
    envelope = compile_current_case_agent_execution_envelope(
        prepared,
        evidence,
        case_key=CASE_KEY,
        admission_ref=ADMISSION_REF.as_posix(),
        projected_per_call_input_tokens=projected,
    )
    runtime_root = ROOT / (
        ".codex_runtime/fin012-s4-t05d-nvda-post-transfer-agent-exact-live-r1"
    )
    _require(
        not runtime_root.exists(),
        "s4_t05_d_nvda_target_runtime_identity_not_fresh",
    )
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
    bindings = (
        ENTRY_DECISION_REF,
        EVIDENCE_PACK_REF,
        AGENT_INPUT_REF,
        TEMPLATE_REF,
        EXECUTION_MODULE_REF,
        EXACT_RUNNER_REF,
        Path(__file__).resolve().relative_to(ROOT),
        RUNNER_REF,
    )
    body = {
        "schema_version": "fin_ia_0_1_2_s4_t05_d_nvda_agent_fresh_zero_call_proof_and_admission_authority_decision_v1_0",
        "recorded_at": recorded_at,
        "status": "pass_fresh_zero_call_proof_capacity_and_admission_authority",
        "immutable_bindings": [
            {"ref": ref.as_posix(), "sha256": _sha256(ref)} for ref in bindings
        ],
        "project_os_preflight": {
            "status": preflight["status"],
            "run_scope": preflight["run_scope"],
            "open_full_chain_blocker_count": len(
                preflight["open_full_chain_blockers"]
            ),
        },
        "exact_binding": exact_binding,
        "runtime_contract": {
            "provider": "deepseek",
            "model": admission.model,
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
            "normalized_outputs_equal": True,
            "topology_each": [9, 3, 9, 9],
            "model_provider_network_calls": [0, 0, 0],
            "target_runtime_root_absent": True,
        },
        "authority_boundary": {
            "user_authorized_continuous_sequence": True,
            "admission_issuance_and_one_exact_live_authorized": True,
            "automatic_retry_or_second_live": False,
            "paired_or_owner_auto_authorized": False,
        },
        "next_action": NEXT_ACTION,
    }
    decision = {**body, "decision_digest": canonical_digest(body)}
    issuance_body = {
        "schema_version": "fin_ia_0_1_2_s4_t05_d_nvda_agent_fresh_exact_admission_issuance_v1_0",
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
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "business_artifacts": 0,
        },
    }
    issuance = {
        **issuance_body,
        "issuance_digest": canonical_digest(issuance_body),
    }
    return decision, admission.model_dump(mode="json"), issuance


def _write(ref: Path, payload: Mapping[str, Any]) -> str:
    path = ROOT / ref
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        _require(
            path.read_text(encoding="utf-8") == rendered,
            f"s4_t05_d_nvda_existing_output_mismatch:{ref}",
        )
        return "exact_existing_reused"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return "created"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("proof", "issue"))
    parser.add_argument("--recorded-at", required=True)
    args = parser.parse_args()
    decision, admission, issuance = build(recorded_at=args.recorded_at)
    result: dict[str, Any] = {
        "status": decision["status"],
        "capacity_proof": decision["capacity_proof"],
        "fresh_proof": decision["fresh_proof"],
        "admission_issued": False,
    }
    if args.mode == "issue":
        result.update(
            {
                "status": "pass_proof_and_admission_issued_unconsumed",
                "admission_issued": True,
                "write_statuses": {
                    "decision": _write(DECISION_REF, decision),
                    "admission": _write(ADMISSION_REF, admission),
                    "issuance": _write(ISSUANCE_REF, issuance),
                },
                "admission_digest": issuance["issued_admission"][
                    "admission_digest"
                ],
                "issuance_digest": issuance["issuance_digest"],
                "execution_identity": EXECUTION_IDENTITY,
            }
        )
    result["next_action"] = decision["next_action"]
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
