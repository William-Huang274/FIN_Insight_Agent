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
    FIN_0_1_2_S4_T05_NVDA_CURRENT_EVIDENCE_PROFILE_REF,
    estimate_provider_input_tokens,
)
from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.fin_0_1_2_s3_t03_exact_live_runner import (  # noqa: E402
    execute_bound_s3_t03,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_b_current_product_identity import (  # noqa: E402
    compile_t05_b_current_product_agent_input,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_current_case_agent_exact_execution import (  # noqa: E402
    MAXIMUM_INPUT_TOKENS,
    compile_current_case_agent_execution_envelope,
    prepare_current_case_agent_execution,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_three_case_transfer import (  # noqa: E402
    load_transfer_profile_contract,
    validate_transfer_evidence_pack,
)
from apps.workbench.backend.application.research_runtime import (  # noqa: E402
    prepare_s3_three_cell_bounded_agent_exact_input,
)
from scripts.releases.run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live import (  # noqa: E402
    _principal,
    rehydrate_exact_input_services,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from test_fin_0_1_2_s3_t02_production_runtime_integration import (  # noqa: E402
    _CurrentS3ProductionFake,
)
from test_fin_0_1_2_s4_t05_three_case_current_evidence_transfer import (  # noqa: E402
    _CurrentVerifierCompiledAtomFake,
)


CASE_KEY = "NVDA"
SEARCH_RESULT_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t03_nvda_current_search_canary_"
    "exact_live_result_and_acceptance_v1_0.json"
)
EVIDENCE_PACK_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t04_nvda_current_evidence_pack_v1_0.json"
)
T04_EXACT_RESULT_RECORD_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t04_nvda_current_evidence_capacity_"
    "reproof_exact_live_r3_result_and_independent_assessment_v1_0.json"
)
T04_OWNER_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t04_nvda_current_evidence_r2_"
    "product_owner_acceptance_and_t05_entry_v1_0.json"
)
T05_A_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_three_case_current_evidence_"
    "transfer_package_zero_call_implementation_v1_0.json"
)
T05_C_OWNER_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_c_mu_owner_acceptance_and_"
    "closeout_v1_0.json"
)
ADMISSION_TEMPLATE_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t04_nvda_current_evidence_capacity_"
    "reproof_fresh_exact_admission_r3.json"
)
AGENT_INPUT_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_d_nvda_post_transfer_agent_"
    "exact_input_v1_0.json"
)
DECISION_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_d_post_transfer_nvda_entry_"
    "and_dependency_decision_v1_0.json"
)
PROOF_ADMISSION_ID = "fin012-s4-t05d-nvda-post-transfer-zero-call-proof"
NEXT_ACTION = (
    "FIN-0.1.2-S4-T05-D-POST-TRANSFER-NVDA-FRESH-AGENT-PROOF-"
    "CAPACITY-AND-ADMISSION-AUTHORITY-DECISION"
)


class T05DNVDAEntryAuditError(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T05DNVDAEntryAuditError(code)


def _load(ref: Path) -> dict[str, Any]:
    try:
        value = json.loads((ROOT / ref).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T05DNVDAEntryAuditError(f"s4_t05_d_json_unreadable:{ref}") from exc
    _require(isinstance(value, dict), f"s4_t05_d_json_object_required:{ref}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _write_atomic(path: Path, value: Mapping[str, Any]) -> str:
    raw = _canonical_bytes(value)
    if path.exists():
        _require(path.read_bytes() == raw, f"s4_t05_d_existing_output_mismatch:{path}")
        return "exact_existing_reused"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return "created"


def _validate_search_and_evidence() -> tuple[dict[str, Any], dict[str, Any], Path]:
    search = _load(SEARCH_RESULT_REF)
    evidence = validate_transfer_evidence_pack(_load(EVIDENCE_PACK_REF), case_key=CASE_KEY)
    execution = search.get("execution_binding") or {}
    terminal_record = search.get("terminal") or {}
    terminal_ref = (
        Path(str(execution.get("runtime_ref") or ""))
        / "objects"
        / str(terminal_record.get("object_key") or "")
    )
    terminal_path = ROOT / terminal_ref
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    _require(
        search.get("status")
        == "pass_closed_live_current_evidence_candidate_pack_ready_T04_pending"
        and terminal.get("status") == "success"
        and terminal.get("case_key") == CASE_KEY
        and terminal.get("code") == "three_request_current_evidence_candidate_pack_ready"
        and _sha256(terminal_path) == terminal_record.get("digest")
        and evidence["t03_terminal_digest"] == terminal_record.get("digest")
        and evidence["case_key"] == CASE_KEY
        and evidence["as_of"] == "2026-07-21T00:00:00Z"
        and [
            len(evidence["evidence_rows"]),
            len(evidence["numeric_rows"]),
            len(evidence["typed_gaps"]),
        ]
        == [15, 3, 3],
        "s4_t05_d_search_evidence_binding_invalid",
    )
    objects_root = terminal_path.parents[4]
    _require(
        all(
            (objects_root / row["object_key"]).is_file()
            and _sha256(objects_root / row["object_key"]) == row["digest"]
            for row in terminal.get("capture_objects", ())
        ),
        "s4_t05_d_search_capture_binding_invalid",
    )
    return search, evidence, terminal_ref


def _compile_agent_input(evidence: Mapping[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="fin012-s4-t05d-nvda-rehydrate-") as name:
        local, evidence_service, case, accepted = rehydrate_exact_input_services(
            Path(name)
        )
        baseline = prepare_s3_three_cell_bounded_agent_exact_input(
            local,
            evidence_service,
            str(case["case_id"]),
            _principal(),
            decision_surface_contract_ref=str(accepted["contract_version_id"]),
            execution_identity="fin012-s4-t05d-nvda-zero-call-rehydrate",
        ).input_pack
    compiled = compile_t05_b_current_product_agent_input(
        baseline,
        evidence,
        case_key=CASE_KEY,
    )
    value = compiled.model_dump(mode="json")
    _require(
        value["company"] == CASE_KEY
        and value["case_id"].startswith("fin012-s4-t05-nvda-current-evidence-")
        and "oracle" not in value["case_id"]
        and value["decision_surface_contract_ref"]
        == "fin_0_1_2.S4.T05.three_case_current_evidence_transfer:v1"
        and value["lineage"]["T04_financial_pack"]["digest"]
        == evidence["evidence_pack_digest"]
        and value["input_digest"]
        == canonical_digest({key: row for key, row in value.items() if key != "input_digest"}),
        "s4_t05_d_agent_input_binding_invalid",
    )
    return value


def _fake() -> _CurrentVerifierCompiledAtomFake:
    return _CurrentVerifierCompiledAtomFake(_CurrentS3ProductionFake(safe_lead=True))


def _proof_admission(agent_input: Mapping[str, Any]) -> S3ThreeCellBoundedAgentAdmission:
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(ADMISSION_TEMPLATE_REF)
    ).model_copy(
        update={
            "admission_id": PROOF_ADMISSION_ID,
            "execution_mode": "zero_call_fin_0_1_2_s4_t05_d_nvda_post_transfer_proof",
            "research_profile_ref": FIN_0_1_2_S4_T05_NVDA_CURRENT_EVIDENCE_PROFILE_REF,
            "company": CASE_KEY,
            "case_id": agent_input["case_id"],
            "case_version": agent_input["case_version"],
            "as_of": agent_input["as_of"],
            "input_digest": agent_input["input_digest"],
        }
    )
    admission.assert_profile_admissible()
    _require(
        admission.model == "deepseek-v4-pro"
        and admission.max_provider_calls == 9
        and admission.max_semantic_model_calls == 9
        and admission.retry_budget == 0
        and admission.max_total_cost_usd == 0.06
        and not admission.source_network_calls_allowed
        and not admission.external_tool_calls_allowed
        and not admission.live_business_case_head_writes_allowed,
        "s4_t05_d_proof_admission_invalid",
    )
    return admission


def _normalize(value: Any, replacements: Mapping[str, str]) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _normalize(row, replacements)
            for key, row in value.items()
            if key not in {"capture_objects", "terminal_object", "envelope_digest"}
        }
    if isinstance(value, (list, tuple)):
        return [_normalize(row, replacements) for row in value]
    if isinstance(value, str):
        for old, new in replacements.items():
            value = value.replace(old, new)
    return value


def _run_fake_chain(
    root: Path,
    *,
    label: str,
    agent_input: Mapping[str, Any],
    evidence: Mapping[str, Any],
    admission: S3ThreeCellBoundedAgentAdmission,
    projected: tuple[int, ...],
) -> dict[str, Any]:
    from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: PLC0415
        S3ThreeCellBoundedAgentInputPack,
    )

    input_pack = S3ThreeCellBoundedAgentInputPack.model_validate(agent_input)
    identity = f"fin012-s4-t05d-nvda-fresh-proof-{label}"
    prepared = prepare_current_case_agent_execution(
        input_pack,
        evidence,
        case_key=CASE_KEY,
        principal=_principal(),
        execution_identity=identity,
    )
    envelope = compile_current_case_agent_execution_envelope(
        prepared,
        evidence,
        case_key=CASE_KEY,
        admission_ref="prospective-only-not-issued",
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
        result.get("status") == "success"
        and len(result.get("capture_objects") or ()) == 9
        and len((result.get("terminal") or {}).get("local_fact_receipts") or ()) == 3
        and len(result.get("artifacts") or ()) == 9
        and result.get("business_promotable") is True,
        "s4_t05_d_zero_call_fake_chain_invalid",
    )
    replacements = {
        identity: "__execution_identity__",
        prepared.work_unit_id: "__work_unit_id__",
        prepared.attempt_id: "__attempt_id__",
        prepared.research_run_id: "__research_run_id__",
        envelope["envelope_digest"]: "__envelope_digest__",
    }
    return _normalize(result, replacements)


def _prove_current_chain(
    agent_input: Mapping[str, Any], evidence: Mapping[str, Any]
) -> dict[str, Any]:
    from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: PLC0415
        S3ThreeCellBoundedAgentInputPack,
    )

    input_pack = S3ThreeCellBoundedAgentInputPack.model_validate(agent_input)
    admission = _proof_admission(agent_input)
    fake = _fake()
    prior_retries = os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES")
    os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = "0"
    try:
        output = build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=fake,
        ).execute(
            input_pack,
            admission,
            run_identity={
                "research_run_id": "capacity-run",
                "attempt_id": "capacity-attempt",
            },
        )
    finally:
        if prior_retries is None:
            os.environ.pop("LLM_GATEWAY_TRANSPORT_RETRIES", None)
        else:
            os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = prior_retries
    projected = tuple(
        estimate_provider_input_tokens(
            json.dumps(row["kwargs"]["messages"], ensure_ascii=False, separators=(",", ":"))
        )
        for row in fake.calls
    )
    _require(
        len(projected) == 9
        and len(output.provider_output_captures) == 9
        and len(output.execution_observation.get("local_fact_receipts") or ()) == 3
        and len(output.artifacts) == 9
        and sum(projected) <= MAXIMUM_INPUT_TOKENS,
        "s4_t05_d_capacity_or_topology_invalid",
    )
    prior_retries = os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES")
    os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = "0"
    try:
        with tempfile.TemporaryDirectory(
            prefix="fin012-s4-t05d-proof-a-"
        ) as a_name, tempfile.TemporaryDirectory(
            prefix="fin012-s4-t05d-proof-b-"
        ) as b_name:
            first = _run_fake_chain(
                Path(a_name),
                label="a",
                agent_input=agent_input,
                evidence=evidence,
                admission=admission,
                projected=projected,
            )
            second = _run_fake_chain(
                Path(b_name),
                label="b",
                agent_input=agent_input,
                evidence=evidence,
                admission=admission,
                projected=projected,
            )
    finally:
        if prior_retries is None:
            os.environ.pop("LLM_GATEWAY_TRANSPORT_RETRIES", None)
        else:
            os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = prior_retries
    _require(first == second, "s4_t05_d_two_fresh_roots_not_deterministic")
    return {
        "fresh_runtime_roots": 2,
        "normalized_results_equal": True,
        "provider_callbacks": 9,
        "compiled_interactions": 9,
        "local_fact_receipts": 3,
        "provider_output_captures": 9,
        "formal_artifacts": 9,
        "aggregate_estimated_input_tokens": sum(projected),
        "maximum_single_interaction_estimated_input_tokens": max(projected),
        "maximum_input_tokens": MAXIMUM_INPUT_TOKENS,
        "input_token_headroom": MAXIMUM_INPUT_TOKENS - sum(projected),
    }


def build_decision(*, recorded_at: str) -> tuple[dict[str, Any], dict[str, Any]]:
    search, evidence, terminal_ref = _validate_search_and_evidence()
    profile = load_transfer_profile_contract(ROOT)
    nvda_profile = next(row for row in profile["cases"] if row["case_key"] == CASE_KEY)
    _require(
        nvda_profile["regression_oracle_ref"] == EVIDENCE_PACK_REF.as_posix()
        and nvda_profile["regression_oracle_sha256"] == _sha256(ROOT / EVIDENCE_PACK_REF)
        and nvda_profile["as_of"] == evidence["as_of"]
        and nvda_profile["pre_transfer_product_status"] == "R2_owner_accepted",
        "s4_t05_d_profile_evidence_freshness_binding_invalid",
    )
    agent_input = _compile_agent_input(evidence)
    proof = _prove_current_chain(agent_input, evidence)
    bindings = []
    for ref, role in (
        (SEARCH_RESULT_REF, "accepted_current_search_and_terminal_anchor"),
        (EVIDENCE_PACK_REF, "accepted_current_evidence_snapshot_reused_without_refresh"),
        (T04_EXACT_RESULT_RECORD_REF, "pre_transfer_exact_live_comparison_anchor_only"),
        (T04_OWNER_REF, "pre_transfer_current_NVDA_R2_owner_acceptance_anchor"),
        (T05_A_REF, "three_case_shared_runtime_engineering_proof"),
        (T05_C_OWNER_REF, "DELL_MU_current_R2_precondition_complete"),
    ):
        bindings.append({"ref": ref.as_posix(), "sha256": _sha256(ROOT / ref), "role": role})
    body = {
        "schema_version": "fin_ia_0_1_2_s4_t05_d_post_transfer_nvda_entry_and_dependency_decision_v1_0",
        "decision_id": "FIN-0.1.2-S4-T05-D-POST-TRANSFER-NVDA-ENTRY-AND-DEPENDENCY-DECISION-R1",
        "recorded_at": recorded_at,
        "status": "pass_search_reuse_and_zero_call_post_transfer_chain_proven_fresh_live_not_authorized",
        "entry_preconditions": {
            "DELL_current_R2": True,
            "MU_current_R2": True,
            "pre_transfer_current_NVDA_R2": True,
            "post_transfer_NVDA_R2": False,
        },
        "immutable_bindings": bindings,
        "search_and_evidence_reuse_decision": {
            "decision": "reuse_exact_current_NVDA_T03_terminal_and_T04_Evidence_pack",
            "as_of": evidence["as_of"],
            "terminal_ref": terminal_ref.as_posix(),
            "terminal_digest": evidence["t03_terminal_digest"],
            "evidence_pack_digest": evidence["evidence_pack_digest"],
            "source_capture_count": len(search["terminal"]) and search["observed_counts"]["capture_objects"],
            "evidence_numeric_gap_counts": [15, 3, 3],
            "second_search_or_source_refresh_required_now": False,
            "reason": "The frozen T05 profile retains the same as-of and exact content digests; every raw capture and terminal object is still readable and content-addressed.",
        },
        "owned_compatibility_repair": {
            "finding": "current exact-execution wrapper assumed only the DELL/MU S4_T04_source_grounded_input lineage slot",
            "impact_before_repair": "NVDA post-transfer preparation would fail before any Provider call despite T05-A Agent fake success",
            "resolution": "select the frozen lineage slot by case family and continue requiring the exact current Evidence digest",
            "financial_authority_or_validation_relaxed": False,
            "model_or_provider_fault": False,
        },
        "compiled_post_transfer_input": {
            "ref": AGENT_INPUT_REF.as_posix(),
            "sha256": hashlib.sha256(_canonical_bytes(agent_input)).hexdigest(),
            "input_digest": agent_input["input_digest"],
            "input_head_digest": agent_input["input_head_digest"],
            "case_id": agent_input["case_id"],
            "lineage_family": "legacy_six_slot_with_current_T04_financial_pack_digest",
        },
        "zero_call_full_chain_reproof": proof,
        "dependency_classification": {
            "reusable_without_reexecution": [
                "T03 raw source captures and terminal result",
                "T04 current Evidence Pack",
                "T04 pre-transfer exact result as comparison anchor only",
                "T04 owner acceptance as pre-transfer product history only",
                "T05 shared renderer and deterministic paired baseline implementation",
            ],
            "reproven_in_this_decision": [
                "current T05 NVDA Agent exact input compilation",
                "legacy NVDA lineage to shared exact-execution wrapper binding",
                "two fresh zero-call full chains",
                "9-call capacity and 9-Artifact topology",
            ],
            "fresh_live_required": [
                "one new post-transfer NVDA DeepSeek Agent exact-live",
                "verified final product surface from that immutable result",
                "same-input distinct-run paired L1-L4 assessment",
                "explicit Product Owner acceptance",
            ],
            "not_T05_D_scope": [
                "new current Search without freshness or digest drift",
                "generic WWC quality calibration RC-P36-119",
                "MU cross-cell synthesis quality RC-P36-122",
                "qualified Human Review or NVDA R3",
                "Workbench dogfood, S5, release or production qualification",
            ],
        },
        "authority_boundary": {
            "new_source_network_calls": 0,
            "new_model_calls": 0,
            "new_provider_calls": 0,
            "new_admissions": 0,
            "new_exact_live_runs": 0,
            "business_artifacts": 0,
            "fresh_live_authorized": False,
            "post_transfer_NVDA_R2": False,
        },
        "next_action": NEXT_ACTION,
    }
    return agent_input, {**body, "decision_digest": canonical_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recorded-at", required=True)
    parser.add_argument("--agent-input-output", type=Path, default=ROOT / AGENT_INPUT_REF)
    parser.add_argument("--decision-output", type=Path, default=ROOT / DECISION_REF)
    args = parser.parse_args()
    agent_input, decision = build_decision(recorded_at=args.recorded_at)
    statuses = {
        "agent_input": _write_atomic(args.agent_input_output.resolve(), agent_input),
        "decision": _write_atomic(args.decision_output.resolve(), decision),
    }
    print(
        json.dumps(
            {
                "status": decision["status"],
                "write_statuses": statuses,
                "input_digest": agent_input["input_digest"],
                "proof": decision["zero_call_full_chain_reproof"],
                "next_action": decision["next_action"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
