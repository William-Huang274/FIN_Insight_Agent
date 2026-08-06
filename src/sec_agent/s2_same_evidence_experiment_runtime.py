from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s2_same_evidence_layered_evaluation import (
    NUMERIC_TOKEN,
    allowed_numeric_surfaces,
    compile_output_contract,
    evaluate_raw_chain,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


POLICY_REF = (
    "configs/runtime/"
    "fin_ia_0_1_3_s2_05_experiment_a_runtime_policy_v1_0.json"
)
ADMISSION_SCHEMA = "fin_ia_0_1_3_s2_05_experiment_a_case_admission_v1_0"
CAPTURE_SCHEMA = "fin_ia_0_1_3_s2_05_experiment_a_raw_capture_v1_0"
TERMINAL_SCHEMA = "fin_ia_0_1_3_s2_05_experiment_a_terminal_v1_0"
LAYERED_TERMINAL_SCHEMA = "fin_ia_0_1_3_s2_05_experiment_a_layered_terminal_v1_0"
SCOPE = "FIN_0_1_3_S2_05_EXPERIMENT_A_ONE_CASE_RAW_EXACT_ONCE"
CASE_ORDER = ("DELL", "MU", "NVDA")
SECTION_IDS = (
    "executive_summary",
    "demand_product_and_competition",
    "financial_transmission",
    "capital_market_boundary",
    "counter_thesis_and_risks",
    "what_would_change_and_evidence_gaps",
)

ProviderCall = Callable[..., Mapping[str, Any]]
_DIGEST = re.compile(r"[0-9a-f]{64}")
_GIT_ID = re.compile(r"[0-9a-f]{40}")
_NUMERIC = NUMERIC_TOKEN


class S2SameEvidenceExperimentError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_runtime_policy(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    policy_path = (root / POLICY_REF).resolve()
    if policy_path.parent != (root / "configs" / "runtime").resolve():
        raise S2SameEvidenceExperimentError("experiment_a_policy_path_invalid")
    policy = _read_json(policy_path, "experiment_a_policy_json_invalid")
    _validate_policy(policy)
    return policy


def load_frozen_blind_inputs(
    repo_root: Path,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    root = repo_root.resolve()
    frozen = _mapping(policy.get("frozen_input"), "experiment_a_frozen_input_policy_invalid")
    relative = str(frozen.get("ref") or "")
    if relative != (
        "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/"
        "experiment_a_blind_inputs_v1.json"
    ):
        raise S2SameEvidenceExperimentError("experiment_a_input_allowlist_invalid")
    path = (root / relative).resolve()
    expected_parent = (
        root
        / "eval_sets"
        / "fin_0_1_3_same_evidence_v1"
        / "model_visible"
    ).resolve()
    if path.parent != expected_parent or "evaluator_only" in path.parts:
        raise S2SameEvidenceExperimentError("experiment_a_hidden_or_parent_read_forbidden")
    if _sha256(path) != frozen.get("sha256"):
        raise S2SameEvidenceExperimentError("experiment_a_input_sha256_mismatch")
    blind = _read_json(path, "experiment_a_input_json_invalid")
    body = {key: deepcopy(value) for key, value in blind.items() if key != "blind_input_digest"}
    if (
        blind.get("blind_input_digest") != canonical_digest(body)
        or blind.get("blind_input_digest") != frozen.get("canonical_digest")
    ):
        raise S2SameEvidenceExperimentError("experiment_a_input_digest_mismatch")
    cases = blind.get("cases")
    if not isinstance(cases, list) or [row.get("case_key") for row in cases] != list(CASE_ORDER):
        raise S2SameEvidenceExperimentError("experiment_a_case_order_invalid")
    for case in cases:
        _validate_case_input(case)
    return blind


def issue_case_admission(
    *,
    case_input: Mapping[str, Any],
    policy: Mapping[str, Any],
    execution_git_commit: str,
    runner_sha256: str,
    policy_sha256: str,
    issued_at: str,
    expires_at: str,
    run_nonce: str,
    credential_present: bool,
) -> dict[str, Any]:
    """Compile one case admission.

    Calling this function does not itself create authority. A release decision
    must still authorize and persist the returned payload before execution.
    """

    _validate_policy(policy)
    _validate_case_input(case_input)
    if not _GIT_ID.fullmatch(str(execution_git_commit or "")):
        raise S2SameEvidenceExperimentError("experiment_a_admission_git_invalid")
    if not _DIGEST.fullmatch(str(runner_sha256 or "")) or not _DIGEST.fullmatch(
        str(policy_sha256 or "")
    ):
        raise S2SameEvidenceExperimentError("experiment_a_admission_runtime_binding_invalid")
    if credential_present is not True:
        raise S2SameEvidenceExperimentError("experiment_a_admission_credential_missing")
    if _time(expires_at) <= _time(issued_at):
        raise S2SameEvidenceExperimentError("experiment_a_admission_expiry_invalid")
    case_key = str(case_input["case_key"])
    run_id = "fin013_s2_05_exp_a_" + case_key.lower() + "_" + canonical_digest(
        {"nonce": run_nonce, "git": execution_git_commit, "case": case_key}
    )[:20]
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "admission_id": "admission::" + run_id,
        "scope": SCOPE,
        "case_key": case_key,
        "case_input_digest": case_input["model_visible_digest"],
        "frozen_blind_input_digest": policy["frozen_input"]["canonical_digest"],
        "execution_git_commit": execution_git_commit,
        "runner_sha256": runner_sha256,
        "policy_sha256": policy_sha256,
        "run_id": run_id,
        "attempt_id": run_id + "::attempt_1",
        "runtime_identity": run_id + "::runtime_1",
        "provider": deepcopy(policy["provider"]),
        "capacity": deepcopy(policy["capacity"]),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "run_nonce_digest": canonical_digest(run_nonce),
        "credential_present": True,
        "state": "issued_unconsumed",
    }
    return {**body, "admission_digest": canonical_digest(body)}


def validate_case_admission(
    admission: Mapping[str, Any],
    *,
    case_input: Mapping[str, Any],
    policy: Mapping[str, Any],
    execution_git_commit: str,
    runner_sha256: str,
    policy_sha256: str,
    observed_at: str,
) -> None:
    body = {key: deepcopy(value) for key, value in admission.items() if key != "admission_digest"}
    if (
        admission.get("schema_version") != ADMISSION_SCHEMA
        or admission.get("scope") != SCOPE
        or admission.get("state") != "issued_unconsumed"
        or admission.get("admission_digest") != canonical_digest(body)
    ):
        raise S2SameEvidenceExperimentError("experiment_a_admission_digest_or_state_invalid")
    expected = (
        case_input.get("case_key"),
        case_input.get("model_visible_digest"),
        policy["frozen_input"]["canonical_digest"],
        execution_git_commit,
        runner_sha256,
        policy_sha256,
    )
    actual = tuple(
        admission.get(key)
        for key in (
            "case_key",
            "case_input_digest",
            "frozen_blind_input_digest",
            "execution_git_commit",
            "runner_sha256",
            "policy_sha256",
        )
    )
    if actual != expected:
        raise S2SameEvidenceExperimentError("experiment_a_admission_execution_binding_invalid")
    if admission.get("provider") != policy.get("provider") or admission.get("capacity") != policy.get("capacity"):
        raise S2SameEvidenceExperimentError("experiment_a_admission_provider_or_capacity_invalid")
    if admission.get("credential_present") is not True:
        raise S2SameEvidenceExperimentError("experiment_a_admission_credential_missing")
    if _time(observed_at) > _time(str(admission.get("expires_at") or "")):
        raise S2SameEvidenceExperimentError("experiment_a_admission_expired")


def execute_case(
    *,
    admission: Mapping[str, Any],
    case_input: Mapping[str, Any],
    policy: Mapping[str, Any],
    execution_git_commit: str,
    runner_sha256: str,
    policy_sha256: str,
    runtime_root: Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    provider_call: ProviderCall,
    observed_at: str,
) -> dict[str, Any]:
    validate_case_admission(
        admission,
        case_input=case_input,
        policy=policy,
        execution_git_commit=execution_git_commit,
        runner_sha256=runner_sha256,
        policy_sha256=policy_sha256,
        observed_at=observed_at,
    )
    root = runtime_root.resolve()
    ledger_path = shared_ledger.path.resolve()
    if ledger_path == root or root in ledger_path.parents:
        raise S2SameEvidenceExperimentError("experiment_a_shared_ledger_inside_runtime_root")
    root.mkdir(parents=True, exist_ok=False)
    captures_dir = root / "raw_model_only" / "captures"
    captures_dir.mkdir(parents=True)
    receipt = shared_ledger.reserve(
        admission_digest=str(admission["admission_digest"]),
        admission_id=str(admission["admission_id"]),
        scope=str(admission["scope"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        runtime_identity=str(admission["runtime_identity"]),
        reserved_at=observed_at,
    )

    calls: list[dict[str, Any]] = []
    validated: dict[str, Any] = {"specialists": []}
    failure_code: str | None = None
    terminal_phase = "lead_planning"
    try:
        lead_context = {"case_input": deepcopy(dict(case_input))}
        lead_row, lead = _perform_node_call(
            node_type="lead_planning",
            node_id="lead",
            context=lead_context,
            case_input=case_input,
            admission=admission,
            policy=policy,
            provider_call=provider_call,
            captures_dir=captures_dir,
            call_index=1,
        )
        _append_checked(calls, lead_row, policy)
        _validate_lead(lead, case_input=case_input, policy=policy)
        validated["lead"] = lead

        for unit in lead["research_units"]:
            terminal_phase = "specialist_judgment"
            specialist_context = _compile_specialist_context(case_input, unit)
            row, specialist = _perform_node_call(
                node_type="specialist_judgment",
                node_id=str(unit["unit_id"]),
                context=specialist_context,
                case_input=case_input,
                admission=admission,
                policy=policy,
                provider_call=provider_call,
                captures_dir=captures_dir,
                call_index=len(calls) + 1,
            )
            _append_checked(calls, row, policy)
            _validate_specialist(
                specialist,
                case_input=case_input,
                unit=unit,
                policy=policy,
            )
            validated["specialists"].append(specialist)

        terminal_phase = "cross_cell_synthesis"
        synthesis_context = {
            "case_identity": _case_identity(case_input),
            "evidence_index": _evidence_index(case_input),
            "derived_numeric": deepcopy(case_input["derived_numeric"]),
            "explicit_gaps": deepcopy(case_input["explicit_gaps"]),
            "lead_plan": lead,
            "specialist_outputs": validated["specialists"],
        }
        row, synthesis = _perform_node_call(
            node_type="cross_cell_synthesis",
            node_id="synthesis",
            context=synthesis_context,
            case_input=case_input,
            admission=admission,
            policy=policy,
            provider_call=provider_call,
            captures_dir=captures_dir,
            call_index=len(calls) + 1,
        )
        _append_checked(calls, row, policy)
        _validate_synthesis(
            synthesis,
            case_input=case_input,
            specialists=validated["specialists"],
        )
        validated["synthesis"] = synthesis

        terminal_phase = "writer"
        writer_context = {
            "case_identity": _case_identity(case_input),
            "evidence_index": _evidence_index(case_input),
            "derived_numeric": deepcopy(case_input["derived_numeric"]),
            "explicit_gaps": deepcopy(case_input["explicit_gaps"]),
            "specialist_outputs": validated["specialists"],
            "synthesis": synthesis,
            "required_section_ids": list(SECTION_IDS),
        }
        row, writer = _perform_node_call(
            node_type="writer",
            node_id="writer",
            context=writer_context,
            case_input=case_input,
            admission=admission,
            policy=policy,
            provider_call=provider_call,
            captures_dir=captures_dir,
            call_index=len(calls) + 1,
        )
        _append_checked(calls, row, policy)
        _validate_writer(writer, case_input=case_input, specialists=validated["specialists"])
        validated["writer"] = writer

        terminal_phase = "verifier"
        verifier_context = {
            "case_identity": _case_identity(case_input),
            "evidence_index": _evidence_index(case_input),
            "derived_numeric": deepcopy(case_input["derived_numeric"]),
            "explicit_gaps": deepcopy(case_input["explicit_gaps"]),
            "lead_plan": lead,
            "specialist_outputs": validated["specialists"],
            "synthesis": synthesis,
            "writer": writer,
            "verifier_scope": "raw candidate substance and evidence binding only; hidden gold unavailable",
        }
        row, verifier = _perform_node_call(
            node_type="verifier",
            node_id="verifier",
            context=verifier_context,
            case_input=case_input,
            admission=admission,
            policy=policy,
            provider_call=provider_call,
            captures_dir=captures_dir,
            call_index=len(calls) + 1,
        )
        _append_checked(calls, row, policy)
        _validate_verifier(
            verifier,
            case_input=case_input,
            specialists=validated["specialists"],
            writer=writer,
        )
        validated["verifier"] = verifier
        if verifier["material_failure"] is True or verifier["decision"] != "accept_raw_candidate":
            failure_code = "experiment_a_verifier_material_failure"
    except S2SameEvidenceExperimentError as exc:
        failure_code = exc.code

    expected_calls = (
        len(validated.get("lead", {}).get("research_units", [])) + 4
        if validated.get("lead")
        else None
    )
    succeeded = failure_code is None and expected_calls is not None and len(calls) == expected_calls
    status = "terminal_succeeded_raw_candidate" if succeeded else "terminal_failed_no_retry"
    captured_rows = _captured_call_rows(captures_dir)
    usage = _usage_summary(captured_rows, policy)
    terminal_body = {
        "schema_version": TERMINAL_SCHEMA,
        "admission_digest": admission["admission_digest"],
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "case_key": case_input["case_key"],
        "status": status,
        "terminal_phase": "case_complete" if succeeded else terminal_phase,
        "terminal_code": "experiment_a_raw_candidate_pass" if succeeded else failure_code,
        "completed_calls": len(captured_rows),
        "expected_calls": expected_calls,
        "call_results": captured_rows,
        "usage": usage,
        "validated_raw_output_digests": {
            key: canonical_digest(value)
            for key, value in validated.items()
            if key != "specialists"
        },
        "validated_specialist_output_digests": [
            canonical_digest(value) for value in validated["specialists"]
        ],
        "retry_count": 0,
        "fallback_count": 0,
        "business_artifact_promotions": 0,
        "correction_track_writes": 0,
        "corrected_candidate_track_writes": 0,
        "evaluator_track_reads_or_writes": 0,
        "observed_at": observed_at,
        "reservation_digest": receipt.reservation_digest,
    }
    terminal = {**terminal_body, "terminal_result_digest": canonical_digest(terminal_body)}
    terminal_path = root / "raw_model_only" / "terminal_result.json"
    _write_exclusive(terminal_path, terminal)
    final_receipt = shared_ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status=status,
        terminal_phase=str(terminal["terminal_phase"]),
        terminal_code=str(terminal["terminal_code"]),
        terminal_result_digest=str(terminal["terminal_result_digest"]),
        finalized_at=observed_at,
    )
    return {**terminal, "shared_admission_receipt": final_receipt.as_dict()}


def execute_case_layered(
    *,
    admission: Mapping[str, Any],
    case_input: Mapping[str, Any],
    policy: Mapping[str, Any],
    execution_git_commit: str,
    runner_sha256: str,
    policy_sha256: str,
    runtime_root: Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    provider_call: ProviderCall,
    observed_at: str,
) -> dict[str, Any]:
    """Run a fresh raw experiment to completion and evaluate findings once.

    Transport, parse, capacity, unusable Lead topology and unsafe Lead ID
    failures still stop immediately.  Node content/schema findings after the
    usable Lead are retained through Verifier and block promotion, but do not
    erase the complete raw candidate needed for hidden scoring.
    """

    validate_case_admission(
        admission,
        case_input=case_input,
        policy=policy,
        execution_git_commit=execution_git_commit,
        runner_sha256=runner_sha256,
        policy_sha256=policy_sha256,
        observed_at=observed_at,
    )
    root = runtime_root.resolve()
    ledger_path = shared_ledger.path.resolve()
    if ledger_path == root or root in ledger_path.parents:
        raise S2SameEvidenceExperimentError("experiment_a_shared_ledger_inside_runtime_root")
    root.mkdir(parents=True, exist_ok=False)
    captures_dir = root / "raw_model_only" / "captures"
    captures_dir.mkdir(parents=True)
    receipt = shared_ledger.reserve(
        admission_digest=str(admission["admission_digest"]),
        admission_id=str(admission["admission_id"]),
        scope=str(admission["scope"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        runtime_identity=str(admission["runtime_identity"]),
        reserved_at=observed_at,
    )
    calls: list[dict[str, Any]] = []
    outputs: dict[str, Any] = {"specialists": []}
    failure_code: str | None = None
    terminal_phase = "lead_planning"
    evaluation: dict[str, Any] | None = None
    try:
        row, lead = _perform_node_call(
            node_type="lead_planning", node_id="lead",
            context={"case_input": deepcopy(dict(case_input))},
            case_input=case_input, admission=admission, policy=policy,
            provider_call=provider_call, captures_dir=captures_dir, call_index=1,
        )
        _append_checked(calls, row, policy)
        # A usable and case-local Lead topology is required to create the
        # dynamic fan-out.  Numeric planning thresholds no longer fail here.
        _validate_lead(lead, case_input=case_input, policy=policy)
        outputs["lead"] = lead
        for unit in lead["research_units"]:
            terminal_phase = "specialist_judgment"
            row, specialist = _perform_node_call(
                node_type="specialist_judgment", node_id=str(unit["unit_id"]),
                context=_compile_specialist_context(case_input, unit),
                case_input=case_input, admission=admission, policy=policy,
                provider_call=provider_call, captures_dir=captures_dir,
                call_index=len(calls) + 1,
            )
            _append_checked(calls, row, policy)
            outputs["specialists"].append(specialist)

        terminal_phase = "cross_cell_synthesis"
        synthesis_context = {
            "case_identity": _case_identity(case_input),
            "evidence_index": _evidence_index(case_input),
            "derived_numeric": deepcopy(case_input["derived_numeric"]),
            "explicit_gaps": deepcopy(case_input["explicit_gaps"]),
            "lead_plan": outputs["lead"],
            "specialist_outputs": outputs["specialists"],
        }
        row, synthesis = _perform_node_call(
            node_type="cross_cell_synthesis", node_id="synthesis",
            context=synthesis_context, case_input=case_input, admission=admission,
            policy=policy, provider_call=provider_call, captures_dir=captures_dir,
            call_index=len(calls) + 1,
        )
        _append_checked(calls, row, policy)
        outputs["synthesis"] = synthesis

        terminal_phase = "writer"
        writer_context = {
            "case_identity": _case_identity(case_input),
            "evidence_index": _evidence_index(case_input),
            "derived_numeric": deepcopy(case_input["derived_numeric"]),
            "explicit_gaps": deepcopy(case_input["explicit_gaps"]),
            "specialist_outputs": outputs["specialists"],
            "synthesis": synthesis,
            "required_section_ids": list(SECTION_IDS),
        }
        row, writer = _perform_node_call(
            node_type="writer", node_id="writer", context=writer_context,
            case_input=case_input, admission=admission, policy=policy,
            provider_call=provider_call, captures_dir=captures_dir,
            call_index=len(calls) + 1,
        )
        _append_checked(calls, row, policy)
        outputs["writer"] = writer

        terminal_phase = "verifier"
        verifier_context = {
            **synthesis_context,
            "synthesis": synthesis,
            "writer": writer,
            "verifier_scope": "raw candidate substance and evidence binding only; hidden gold unavailable",
        }
        row, verifier = _perform_node_call(
            node_type="verifier", node_id="verifier", context=verifier_context,
            case_input=case_input, admission=admission, policy=policy,
            provider_call=provider_call, captures_dir=captures_dir,
            call_index=len(calls) + 1,
        )
        _append_checked(calls, row, policy)
        outputs["verifier"] = verifier
        evaluation = evaluate_raw_chain(
            outputs, case_input=case_input, policy=policy, section_ids=SECTION_IDS
        )
    except S2SameEvidenceExperimentError as exc:
        failure_code = exc.code

    captured_rows = _captured_call_rows(captures_dir)
    complete = evaluation is not None and evaluation["raw_chain_complete"] is True
    status = "terminal_completed_layered_raw_evaluation" if complete else "terminal_failed_no_retry"
    if complete:
        terminal_code = (
            "experiment_a_layered_raw_candidate_with_material_findings"
            if evaluation["material_failure"]
            else "experiment_a_layered_raw_candidate_pass"
        )
        terminal_phase = "case_complete"
    else:
        terminal_code = failure_code or "experiment_a_layered_raw_chain_incomplete"
    terminal_body = {
        "schema_version": LAYERED_TERMINAL_SCHEMA,
        "admission_digest": admission["admission_digest"],
        "run_id": admission["run_id"], "attempt_id": admission["attempt_id"],
        "case_key": case_input["case_key"], "status": status,
        "terminal_phase": terminal_phase, "terminal_code": terminal_code,
        "completed_calls": len(captured_rows),
        "expected_calls": len(outputs.get("lead", {}).get("research_units", [])) + 4 if outputs.get("lead") else None,
        "call_results": captured_rows, "usage": _usage_summary(captured_rows, policy),
        "raw_output_digests": {
            "lead": canonical_digest(outputs["lead"]) if outputs.get("lead") else None,
            "specialists": [canonical_digest(row) for row in outputs["specialists"]],
            "synthesis": canonical_digest(outputs["synthesis"]) if outputs.get("synthesis") else None,
            "writer": canonical_digest(outputs["writer"]) if outputs.get("writer") else None,
            "verifier": canonical_digest(outputs["verifier"]) if outputs.get("verifier") else None,
        },
        "layered_evaluation": {
            key: deepcopy(evaluation[key])
            for key in (
                "status", "raw_chain_complete", "raw_experiment_candidate",
                "hidden_scoring_eligible", "business_promotion_gate_pass",
                "business_promotable", "material_failure", "finding_count", "findings",
            )
        } if evaluation else None,
        "retry_count": 0, "fallback_count": 0,
        "business_artifact_promotions": 0, "supervisor_corrections": 0,
        "observed_at": observed_at, "reservation_digest": receipt.reservation_digest,
    }
    terminal = {**terminal_body, "terminal_result_digest": canonical_digest(terminal_body)}
    _write_exclusive(root / "raw_model_only" / "layered_terminal_result.json", terminal)
    final_receipt = shared_ledger.finalize(
        admission_digest=str(admission["admission_digest"]), run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]), terminal_status=status,
        terminal_phase=str(terminal_phase), terminal_code=str(terminal_code),
        terminal_result_digest=str(terminal["terminal_result_digest"]), finalized_at=observed_at,
    )
    return {**terminal, "shared_admission_receipt": final_receipt.as_dict()}


def execute_campaign(
    jobs: Sequence[Mapping[str, Any]],
    *,
    provider_call: ProviderCall,
) -> list[dict[str, Any]]:
    if len(jobs) > 3:
        raise S2SameEvidenceExperimentError("experiment_a_campaign_case_count_exceeded")
    if [str(job["case_input"]["case_key"]) for job in jobs] != list(CASE_ORDER[: len(jobs)]):
        raise S2SameEvidenceExperimentError("experiment_a_campaign_case_order_invalid")
    results: list[dict[str, Any]] = []
    for job in jobs:
        result = execute_case(provider_call=provider_call, **dict(job))
        results.append(result)
        if result["status"] != "terminal_succeeded_raw_candidate":
            break
    return results


def _perform_node_call(
    *,
    node_type: str,
    node_id: str,
    context: Mapping[str, Any],
    case_input: Mapping[str, Any],
    admission: Mapping[str, Any],
    policy: Mapping[str, Any],
    provider_call: ProviderCall,
    captures_dir: Path,
    call_index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    kwargs = _provider_kwargs(
        node_type=node_type,
        node_id=node_id,
        context=context,
        case_input=case_input,
        admission=admission,
        policy=policy,
    )
    request_chars = len(str(kwargs["messages"][1]["content"]))
    if request_chars > int(policy["capacity"]["maximum_input_characters_per_call"]):
        raise S2SameEvidenceExperimentError("experiment_a_node_input_capacity_exceeded")
    try:
        result = deepcopy(dict(provider_call(**kwargs)))
    except Exception as exc:
        result = {
            "status": "gateway_exception",
            "content": "",
            "finish_reason": "",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "transport_attempt_count": 1,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)[:1000],
        }
    capture = {
        "schema_version": CAPTURE_SCHEMA,
        "case_key": case_input["case_key"],
        "call_index": call_index,
        "node_type": node_type,
        "node_id": node_id,
        "provider_visible_request": {
            key: deepcopy(value)
            for key, value in kwargs.items()
            if key != "api_key_env"
        },
        "gateway_result": result,
    }
    capture_digest = canonical_digest(capture)
    capture_ref = f"raw_model_only/captures/{call_index:02d}_{node_type}_{capture_digest}.json"
    _write_exclusive(captures_dir / Path(capture_ref).name, capture)
    row = {
        "call_index": call_index,
        "node_type": node_type,
        "node_id": node_id,
        "capture_ref": capture_ref,
        "capture_digest": capture_digest,
        "gateway_status": result.get("status"),
        "finish_reason": result.get("finish_reason"),
        "usage": {
            "input_tokens": int(result.get("input_tokens") or 0),
            "output_tokens": int(result.get("output_tokens") or 0),
            "total_tokens": int(result.get("total_tokens") or 0),
            "transport_attempt_count": int(result.get("transport_attempt_count") or 0),
        },
    }
    if result.get("status") != "ok" or result.get("finish_reason") not in {"stop", None}:
        raise S2SameEvidenceExperimentError(
            "experiment_a_provider_transport_or_finish_failure"
        )
    try:
        parsed = json.loads(str(result.get("content") or ""))
    except json.JSONDecodeError as exc:
        raise S2SameEvidenceExperimentError("experiment_a_node_output_json_invalid") from exc
    if not isinstance(parsed, dict):
        raise S2SameEvidenceExperimentError("experiment_a_node_output_not_object")
    row["raw_output_digest"] = canonical_digest(parsed)
    return row, parsed


def _captured_call_rows(captures_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(captures_dir.glob("*.json")):
        capture = _read_json(path, "experiment_a_capture_json_invalid")
        result = _mapping(
            capture.get("gateway_result"), "experiment_a_capture_result_invalid"
        )
        body = {key: deepcopy(value) for key, value in capture.items()}
        rows.append(
            {
                "call_index": capture["call_index"],
                "node_type": capture["node_type"],
                "node_id": capture["node_id"],
                "capture_ref": "raw_model_only/captures/" + path.name,
                "capture_digest": canonical_digest(body),
                "gateway_status": result.get("status"),
                "finish_reason": result.get("finish_reason"),
                "usage": {
                    "input_tokens": int(result.get("input_tokens") or 0),
                    "output_tokens": int(result.get("output_tokens") or 0),
                    "total_tokens": int(result.get("total_tokens") or 0),
                    "transport_attempt_count": int(
                        result.get("transport_attempt_count") or 0
                    ),
                },
            }
        )
    return rows


def _append_checked(
    calls: list[dict[str, Any]],
    row: dict[str, Any],
    policy: Mapping[str, Any],
) -> None:
    calls.append(row)
    usage = _usage_summary(calls, policy)
    capacity = policy["capacity"]
    if (
        usage["input_tokens"] > capacity["maximum_input_tokens_per_case"]
        or usage["output_tokens"] > capacity["maximum_output_tokens_per_case"]
        or usage["total_tokens"] > capacity["maximum_total_tokens_per_case"]
        or usage["estimated_cost_usd"]
        > capacity["cost_ceiling"]["maximum_estimated_usd_per_case"]
    ):
        raise S2SameEvidenceExperimentError("experiment_a_case_token_or_cost_capacity_exceeded")


def _usage_summary(
    rows: Sequence[Mapping[str, Any]], policy: Mapping[str, Any]
) -> dict[str, Any]:
    input_tokens = 0
    output_tokens = 0
    for row in rows:
        usage = _mapping(row.get("usage"), "experiment_a_usage_shape_invalid")
        observed_input = usage.get("input_tokens")
        observed_output = usage.get("output_tokens")
        if (
            type(observed_input) is not int
            or type(observed_output) is not int
            or observed_input < 0
            or observed_output < 0
        ):
            raise S2SameEvidenceExperimentError("experiment_a_usage_value_invalid")
        input_tokens += observed_input
        output_tokens += observed_output
    cost = policy["capacity"]["cost_ceiling"]
    estimated = (
        input_tokens * float(cost["input_usd_per_million_tokens"])
        + output_tokens * float(cost["output_usd_per_million_tokens"])
    ) / 1_000_000
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "estimated_cost_usd": round(estimated, 8),
        "cost_method": "policy_ceiling_rates_not_provider_invoice",
    }


def _provider_kwargs(
    *,
    node_type: str,
    node_id: str,
    context: Mapping[str, Any],
    case_input: Mapping[str, Any],
    admission: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    provider = policy["provider"]
    output_caps = policy["capacity"]["maximum_output_tokens"]
    system = (
        "You are one node in a blinded same-evidence financial research experiment. "
        "Return exactly one JSON object and no markdown. Use only facts, numbers, dates, "
        "identities, evidence IDs and gap IDs present in the supplied case-local context. "
        "Do not use tools or external knowledge. Cite material judgments. Preserve "
        "counterevidence and uncertainty. This is a raw candidate: do not simulate hidden "
        "evaluation, supervisor correction, or product acceptance. Node type: " + node_type
    )
    return {
        "llm_backend": provider["backend"],
        "base_url": provider["base_url"],
        "chat_completions_path": provider["chat_completions_path"],
        "model": provider["model"],
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "node_type": node_type,
                        "node_id": node_id,
                        "case_key": case_input["case_key"],
                        "as_of": case_input["as_of"],
                        "required_output_contract": _output_contract(node_type, policy),
                        "context": deepcopy(dict(context)),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
        ],
        "response_format": {"type": "json_object"},
        "api_key_env": provider["api_key_env"],
        "temperature": float(provider["temperature"]),
        "max_tokens": int(output_caps[node_type]),
        "timeout_s": int(policy["capacity"]["timeout_seconds_per_call"]),
        "stream": False,
        "enable_thinking": False,
        "role": "fin013_s2_05_experiment_a_" + node_type,
        "profile": str(case_input["case_key"]) + "::" + node_id,
        "trace_tags": {
            "run_id": admission["run_id"],
            "case_key": case_input["case_key"],
            "node_type": node_type,
            "node_id": node_id,
        },
        "max_transport_attempts": 1,
    }


def _output_contract(node_type: str, policy: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return compile_output_contract(node_type, policy, SECTION_IDS)
    except ValueError as exc:
        raise S2SameEvidenceExperimentError(str(exc)) from exc


def _validate_lead(
    output: Mapping[str, Any],
    *,
    case_input: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> None:
    _assert_exact_keys(output, {"case_key", "as_of", "research_units"}, "lead")
    _assert_identity(output, case_input)
    units = output.get("research_units")
    if not isinstance(units, list) or not 6 <= len(units) <= 8:
        raise S2SameEvidenceExperimentError("experiment_a_lead_unit_count_invalid")
    seen_ids: set[str] = set()
    families: set[str] = set()
    covered_evidence: set[str] = set()
    covered_gaps: set[str] = set()
    evidence_ids, gap_ids = _case_ids(case_input)
    for unit in units:
        _assert_exact_keys(
            unit,
            {"unit_id", "family", "question", "why_material", "evidence_ids", "gap_ids", "stop_condition"},
            "lead_unit",
        )
        unit_id = _text(unit.get("unit_id"), "experiment_a_lead_unit_id_invalid")
        if unit_id in seen_ids:
            raise S2SameEvidenceExperimentError("experiment_a_lead_unit_id_duplicate")
        seen_ids.add(unit_id)
        family = _text(unit.get("family"), "experiment_a_lead_family_invalid")
        if family not in policy["mandatory_research_families"]:
            raise S2SameEvidenceExperimentError("experiment_a_lead_family_invalid")
        families.add(family)
        assigned = _string_list(unit.get("evidence_ids"), "experiment_a_lead_evidence_ids_invalid")
        gaps = _string_list(unit.get("gap_ids"), "experiment_a_lead_gap_ids_invalid", allow_empty=True)
        if not assigned or not set(assigned) <= evidence_ids or not set(gaps) <= gap_ids:
            raise S2SameEvidenceExperimentError("experiment_a_lead_cross_case_or_unknown_id")
        covered_evidence.update(assigned)
        covered_gaps.update(gaps)
        for field in ("question", "why_material"):
            _text(unit.get(field), "experiment_a_lead_narrative_invalid")
            _assert_numeric_surface(str(unit[field]), case_input)
        _text(unit.get("stop_condition"), "experiment_a_lead_narrative_invalid")
        _assert_numeric_surface(str(unit["stop_condition"]), case_input, allow_hypothetical=True)
    if families != set(policy["mandatory_research_families"]):
        raise S2SameEvidenceExperimentError("experiment_a_lead_mandatory_family_missing")
    if covered_evidence != evidence_ids or covered_gaps != gap_ids:
        raise S2SameEvidenceExperimentError("experiment_a_lead_pack_coverage_incomplete")


def _validate_specialist(
    output: Mapping[str, Any],
    *,
    case_input: Mapping[str, Any],
    unit: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> None:
    _assert_exact_keys(
        output,
        {
            "case_key", "as_of", "unit_id", "epistemic_state", "judgment",
            "mechanism", "financial_or_valuation_link", "evidence_ids",
            "counterevidence_ids", "gap_ids", "what_would_change",
        },
        "specialist",
    )
    _assert_identity(output, case_input)
    if output.get("unit_id") != unit.get("unit_id"):
        raise S2SameEvidenceExperimentError("experiment_a_specialist_unit_binding_invalid")
    if output.get("epistemic_state") not in policy["epistemic_states"]:
        raise S2SameEvidenceExperimentError("experiment_a_specialist_epistemic_state_invalid")
    allowed_evidence = set(unit["evidence_ids"])
    allowed_gaps = set(unit["gap_ids"])
    selected = _string_list(output.get("evidence_ids"), "experiment_a_specialist_evidence_ids_invalid", allow_empty=True)
    counter = _string_list(output.get("counterevidence_ids"), "experiment_a_specialist_counterevidence_ids_invalid", allow_empty=True)
    gaps = _string_list(output.get("gap_ids"), "experiment_a_specialist_gap_ids_invalid", allow_empty=True)
    if not set(selected + counter) <= allowed_evidence or not set(gaps) <= allowed_gaps:
        raise S2SameEvidenceExperimentError("experiment_a_specialist_cross_case_or_unassigned_id")
    if set(selected + counter) != allowed_evidence or set(gaps) != allowed_gaps:
        raise S2SameEvidenceExperimentError("experiment_a_specialist_assigned_pack_coverage_incomplete")
    if not selected and not gaps:
        raise S2SameEvidenceExperimentError("experiment_a_specialist_citation_missing")
    for field in ("judgment", "mechanism", "financial_or_valuation_link"):
        value = _text(output.get(field), "experiment_a_specialist_narrative_invalid")
        _assert_numeric_surface(value, case_input)
    value = _text(output.get("what_would_change"), "experiment_a_specialist_narrative_invalid")
    _assert_numeric_surface(value, case_input, allow_hypothetical=True)


def _validate_synthesis(
    output: Mapping[str, Any],
    *,
    case_input: Mapping[str, Any],
    specialists: Sequence[Mapping[str, Any]],
) -> None:
    _assert_exact_keys(
        output,
        {
            "case_key", "as_of", "thesis", "confidence", "unit_ids",
            "dependencies", "conflicts", "material_gap_ids", "counter_thesis",
            "what_would_change",
        },
        "synthesis",
    )
    _assert_identity(output, case_input)
    unit_ids = {str(row["unit_id"]) for row in specialists}
    selected_units = _string_list(output.get("unit_ids"), "experiment_a_synthesis_unit_ids_invalid")
    if set(selected_units) != unit_ids:
        raise S2SameEvidenceExperimentError("experiment_a_synthesis_unit_coverage_invalid")
    _, gap_ids = _case_ids(case_input)
    gaps = _string_list(output.get("material_gap_ids"), "experiment_a_synthesis_gap_ids_invalid", allow_empty=True)
    if not set(gaps) <= gap_ids:
        raise S2SameEvidenceExperimentError("experiment_a_synthesis_unknown_gap")
    if set(gaps) != gap_ids:
        raise S2SameEvidenceExperimentError("experiment_a_synthesis_gap_coverage_incomplete")
    for field in ("thesis", "confidence", "counter_thesis"):
        value = _text(output.get(field), "experiment_a_synthesis_narrative_invalid")
        _assert_numeric_surface(value, case_input)
    value = _text(output.get("what_would_change"), "experiment_a_synthesis_narrative_invalid")
    _assert_numeric_surface(value, case_input, allow_hypothetical=True)
    _validate_relationship_rows(output.get("dependencies"), unit_ids, "dependency")
    _validate_conflict_rows(output.get("conflicts"), unit_ids)


def _validate_writer(
    output: Mapping[str, Any],
    *,
    case_input: Mapping[str, Any],
    specialists: Sequence[Mapping[str, Any]],
) -> None:
    _assert_exact_keys(output, {"case_key", "as_of", "title", "sections", "overall_boundary"}, "writer")
    _assert_identity(output, case_input)
    _text(output.get("title"), "experiment_a_writer_title_invalid")
    _assert_numeric_surface(str(output["title"]), case_input)
    _text(output.get("overall_boundary"), "experiment_a_writer_boundary_invalid")
    _assert_numeric_surface(str(output["overall_boundary"]), case_input)
    sections = output.get("sections")
    if not isinstance(sections, list) or [row.get("section_id") for row in sections] != list(SECTION_IDS):
        raise S2SameEvidenceExperimentError("experiment_a_writer_sections_invalid")
    evidence_ids, gap_ids = _case_ids(case_input)
    unit_ids = {str(row["unit_id"]) for row in specialists}
    covered_evidence: set[str] = set()
    covered_gaps: set[str] = set()
    for section in sections:
        _assert_exact_keys(
            section,
            {"section_id", "heading", "narrative", "evidence_ids", "unit_ids", "gap_ids"},
            "writer_section",
        )
        _text(section.get("heading"), "experiment_a_writer_heading_invalid")
        narrative = _text(section.get("narrative"), "experiment_a_writer_narrative_invalid")
        cited = _string_list(section.get("evidence_ids"), "experiment_a_writer_evidence_ids_invalid", allow_empty=True)
        units = _string_list(section.get("unit_ids"), "experiment_a_writer_unit_ids_invalid", allow_empty=True)
        gaps = _string_list(section.get("gap_ids"), "experiment_a_writer_gap_ids_invalid", allow_empty=True)
        if not set(cited) <= evidence_ids or not set(units) <= unit_ids or not set(gaps) <= gap_ids:
            raise S2SameEvidenceExperimentError("experiment_a_writer_cross_case_or_unknown_id")
        if not cited and not gaps:
            raise S2SameEvidenceExperimentError("experiment_a_writer_section_citation_missing")
        covered_evidence.update(cited)
        covered_gaps.update(gaps)
        _assert_numeric_surface(narrative, case_input)
    if covered_evidence != evidence_ids or covered_gaps != gap_ids:
        raise S2SameEvidenceExperimentError("experiment_a_writer_pack_coverage_incomplete")


def _validate_verifier(
    output: Mapping[str, Any],
    *,
    case_input: Mapping[str, Any],
    specialists: Sequence[Mapping[str, Any]],
    writer: Mapping[str, Any],
) -> None:
    _assert_exact_keys(
        output,
        {"case_key", "as_of", "decision", "material_failure", "findings", "checked_unit_ids", "checked_section_ids"},
        "verifier",
    )
    _assert_identity(output, case_input)
    if output.get("decision") not in {"accept_raw_candidate", "return_material_failure"} or not isinstance(
        output.get("material_failure"), bool
    ):
        raise S2SameEvidenceExperimentError("experiment_a_verifier_decision_invalid")
    if (output["decision"] == "accept_raw_candidate") == output["material_failure"]:
        raise S2SameEvidenceExperimentError("experiment_a_verifier_decision_inconsistent")
    unit_ids = {str(row["unit_id"]) for row in specialists}
    section_ids = {str(row["section_id"]) for row in writer["sections"]}
    if set(_string_list(output.get("checked_unit_ids"), "experiment_a_verifier_unit_ids_invalid")) != unit_ids:
        raise S2SameEvidenceExperimentError("experiment_a_verifier_unit_coverage_invalid")
    if set(_string_list(output.get("checked_section_ids"), "experiment_a_verifier_section_ids_invalid")) != section_ids:
        raise S2SameEvidenceExperimentError("experiment_a_verifier_section_coverage_invalid")
    evidence_ids, _ = _case_ids(case_input)
    findings = output.get("findings")
    if not isinstance(findings, list):
        raise S2SameEvidenceExperimentError("experiment_a_verifier_findings_invalid")
    material_finding = False
    for finding in findings:
        _assert_exact_keys(finding, {"severity", "code", "node_refs", "evidence_ids", "explanation"}, "verifier_finding")
        if finding.get("severity") not in {"L1", "L2", "L3", "L4"}:
            raise S2SameEvidenceExperimentError("experiment_a_verifier_severity_invalid")
        if finding["severity"] == "L1":
            material_finding = True
        _text(finding.get("code"), "experiment_a_verifier_code_invalid")
        _string_list(finding.get("node_refs"), "experiment_a_verifier_node_refs_invalid", allow_empty=True)
        cited = _string_list(finding.get("evidence_ids"), "experiment_a_verifier_evidence_ids_invalid", allow_empty=True)
        if not set(cited) <= evidence_ids:
            raise S2SameEvidenceExperimentError("experiment_a_verifier_unknown_evidence")
        explanation = _text(finding.get("explanation"), "experiment_a_verifier_explanation_invalid")
        _assert_numeric_surface(explanation, case_input)
    if material_finding != output["material_failure"]:
        raise S2SameEvidenceExperimentError("experiment_a_verifier_material_finding_inconsistent")


def _validate_relationship_rows(value: Any, unit_ids: set[str], label: str) -> None:
    if not isinstance(value, list):
        raise S2SameEvidenceExperimentError(f"experiment_a_synthesis_{label}s_invalid")
    for row in value:
        _assert_exact_keys(row, {"from_unit_id", "to_unit_id", "relationship"}, label)
        if row.get("from_unit_id") not in unit_ids or row.get("to_unit_id") not in unit_ids:
            raise S2SameEvidenceExperimentError(f"experiment_a_synthesis_{label}_unit_invalid")
        _text(row.get("relationship"), f"experiment_a_synthesis_{label}_narrative_invalid")


def _validate_conflict_rows(value: Any, unit_ids: set[str]) -> None:
    if not isinstance(value, list):
        raise S2SameEvidenceExperimentError("experiment_a_synthesis_conflicts_invalid")
    for row in value:
        _assert_exact_keys(row, {"unit_ids", "resolution"}, "conflict")
        ids = _string_list(row.get("unit_ids"), "experiment_a_synthesis_conflict_units_invalid")
        if len(ids) < 2 or not set(ids) <= unit_ids:
            raise S2SameEvidenceExperimentError("experiment_a_synthesis_conflict_unit_invalid")
        _text(row.get("resolution"), "experiment_a_synthesis_conflict_resolution_invalid")


def _compile_specialist_context(case_input: Mapping[str, Any], unit: Mapping[str, Any]) -> dict[str, Any]:
    evidence_ids = set(unit["evidence_ids"])
    gap_ids = set(unit["gap_ids"])
    return {
        "case_identity": _case_identity(case_input),
        "research_unit": deepcopy(dict(unit)),
        "assigned_evidence": [
            deepcopy(row) for row in case_input["evidence_items"] if row["evidence_id"] in evidence_ids
        ],
        "derived_numeric": deepcopy(case_input["derived_numeric"]),
        "assigned_gaps": [
            deepcopy(row) for row in case_input["explicit_gaps"] if row["gap_id"] in gap_ids
        ],
    }


def _case_identity(case_input: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_key": case_input["case_key"],
        "issuer": deepcopy(case_input["issuer"]),
        "as_of": case_input["as_of"],
        "research_objective": case_input["research_objective"],
    }


def _evidence_index(case_input: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": row["evidence_id"],
            "statement": row["statement"],
            "source_id": row["source_id"],
            "observed_period": row["observed_period"],
            "numeric_facts": deepcopy(row["numeric_facts"]),
        }
        for row in case_input["evidence_items"]
    ]


def _validate_policy(policy: Mapping[str, Any]) -> None:
    if policy.get("schema_version") != "fin_ia_0_1_3_s2_05_experiment_a_runtime_policy_v1_0":
        raise S2SameEvidenceExperimentError("experiment_a_policy_schema_invalid")
    frozen = _mapping(policy.get("frozen_input"), "experiment_a_frozen_input_policy_invalid")
    if frozen.get("case_order") != list(CASE_ORDER) or frozen.get("external_tools_forbidden") is not True:
        raise S2SameEvidenceExperimentError("experiment_a_policy_input_boundary_invalid")
    provider = _mapping(policy.get("provider"), "experiment_a_provider_policy_invalid")
    if provider != {
        "backend": "deepseek",
        "model": "deepseek-v4-pro",
        "base_url": "https://api.deepseek.com/beta",
        "chat_completions_path": "/chat/completions",
        "api_key_env": "DEEPSEEK_API_KEY",
        "temperature": 0.0,
        "stream": False,
        "enable_thinking": False,
        "max_transport_attempts": 1,
    }:
        raise S2SameEvidenceExperimentError("experiment_a_provider_policy_invalid")
    capacity = _mapping(policy.get("capacity"), "experiment_a_capacity_policy_invalid")
    if (
        capacity.get("specialist_units_per_case") != {"minimum": 6, "maximum": 8}
        or capacity.get("provider_calls_per_case") != {"minimum": 10, "maximum": 12}
        or capacity.get("provider_calls_campaign_maximum") != 36
        or capacity.get("retry_count") != 0
        or capacity.get("fallback_count") != 0
    ):
        raise S2SameEvidenceExperimentError("experiment_a_capacity_policy_invalid")
    outputs = capacity.get("maximum_output_tokens")
    if not isinstance(outputs, dict) or set(outputs) != {
        "lead_planning", "specialist_judgment", "cross_cell_synthesis", "writer", "verifier"
    } or any(type(value) is not int or value <= 0 for value in outputs.values()):
        raise S2SameEvidenceExperimentError("experiment_a_output_capacity_invalid")
    if capacity.get("maximum_output_tokens_per_case") != (
        outputs["lead_planning"]
        + outputs["specialist_judgment"] * 8
        + outputs["cross_cell_synthesis"]
        + outputs["writer"]
        + outputs["verifier"]
    ):
        raise S2SameEvidenceExperimentError("experiment_a_case_output_capacity_math_invalid")
    if capacity.get("maximum_output_tokens_campaign") != capacity["maximum_output_tokens_per_case"] * 3:
        raise S2SameEvidenceExperimentError("experiment_a_campaign_output_capacity_math_invalid")
    if (
        capacity.get("maximum_total_tokens_per_case")
        != capacity.get("maximum_input_tokens_per_case")
        + capacity["maximum_output_tokens_per_case"]
        or capacity.get("maximum_total_tokens_campaign")
        != capacity["maximum_total_tokens_per_case"] * 3
    ):
        raise S2SameEvidenceExperimentError("experiment_a_total_token_capacity_math_invalid")
    cost = _mapping(capacity.get("cost_ceiling"), "experiment_a_cost_capacity_invalid")
    if (
        cost.get("input_usd_per_million_tokens") != 0.6
        or cost.get("output_usd_per_million_tokens") != 1.7
        or cost.get("maximum_estimated_usd_per_case") != 0.18
        or cost.get("maximum_estimated_usd_campaign") != 0.54
    ):
        raise S2SameEvidenceExperimentError("experiment_a_cost_capacity_invalid")
    persistence = _mapping(policy.get("persistence"), "experiment_a_persistence_policy_invalid")
    if (
        persistence.get("writable_track") != "raw_model_only"
        or persistence.get("capture_before_parse_or_validation") is not True
        or persistence.get("forbidden_write_tracks")
        != ["supervisor_corrections", "corrected_candidates", "evaluator_only"]
    ):
        raise S2SameEvidenceExperimentError("experiment_a_persistence_policy_invalid")


def _validate_case_input(case: Mapping[str, Any]) -> None:
    required = {
        "as_of", "case_key", "derived_numeric", "evidence_items", "explicit_gaps",
        "instructions", "issuer", "model_visible_digest", "research_objective",
        "rubric_ref", "tool_access",
    }
    _assert_exact_keys(case, required, "case_input")
    body = {key: deepcopy(value) for key, value in case.items() if key != "model_visible_digest"}
    if case.get("model_visible_digest") != canonical_digest(body):
        raise S2SameEvidenceExperimentError("experiment_a_case_input_digest_invalid")
    case_key = str(case.get("case_key") or "")
    if case_key not in CASE_ORDER or _mapping(case.get("issuer"), "experiment_a_case_issuer_invalid").get("ticker") != case_key:
        raise S2SameEvidenceExperimentError("experiment_a_case_identity_invalid")
    if case.get("tool_access") != "none_experiment_A_same_evidence_only":
        raise S2SameEvidenceExperimentError("experiment_a_case_tool_access_invalid")
    evidence = case.get("evidence_items")
    gaps = case.get("explicit_gaps")
    if not isinstance(evidence, list) or not evidence or not isinstance(gaps, list) or not gaps:
        raise S2SameEvidenceExperimentError("experiment_a_case_evidence_shape_invalid")
    evidence_ids = [str(row.get("evidence_id") or "") for row in evidence]
    gap_ids = [str(row.get("gap_id") or "") for row in gaps]
    if len(evidence_ids) != len(set(evidence_ids)) or len(gap_ids) != len(set(gap_ids)):
        raise S2SameEvidenceExperimentError("experiment_a_case_id_duplicate")
    if any(not value.startswith(case_key + "_") for value in evidence_ids + gap_ids):
        raise S2SameEvidenceExperimentError("experiment_a_case_cross_case_id")


def _assert_identity(output: Mapping[str, Any], case_input: Mapping[str, Any]) -> None:
    if output.get("case_key") != case_input.get("case_key") or output.get("as_of") != case_input.get("as_of"):
        raise S2SameEvidenceExperimentError("experiment_a_node_identity_or_as_of_invalid")


def _assert_numeric_surface(
    text: str,
    case_input: Mapping[str, Any],
    *,
    allow_hypothetical: bool = False,
) -> None:
    allowed = allowed_numeric_surfaces(case_input)
    observed = {_normalize_numeric(value) for value in _NUMERIC.findall(text)}
    if not observed <= allowed and not allow_hypothetical:
        raise S2SameEvidenceExperimentError("experiment_a_unbound_numeric_surface")


def _normalize_numeric(value: str) -> str:
    return value.replace(",", "").lstrip("+").lower()


def _case_ids(case_input: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    return (
        {str(row["evidence_id"]) for row in case_input["evidence_items"]},
        {str(row["gap_id"]) for row in case_input["explicit_gaps"]},
    )


def _assert_exact_keys(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise S2SameEvidenceExperimentError(f"experiment_a_{label}_schema_invalid")


def _mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise S2SameEvidenceExperimentError(code)
    return value


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise S2SameEvidenceExperimentError(code)
    return value.strip()


def _string_list(value: Any, code: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ) or len(value) != len(set(value)):
        raise S2SameEvidenceExperimentError(code)
    return [item.strip() for item in value]


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise S2SameEvidenceExperimentError(code) from exc
    if not isinstance(value, dict):
        raise S2SameEvidenceExperimentError(code)
    return value


def _write_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except OSError as exc:
        raise S2SameEvidenceExperimentError("experiment_a_capture_or_terminal_persistence_failure") from exc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise S2SameEvidenceExperimentError("experiment_a_admission_timestamp_invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
