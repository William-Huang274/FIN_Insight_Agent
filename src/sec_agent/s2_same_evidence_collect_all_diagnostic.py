from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s2_same_evidence_experiment_runtime import (
    SECTION_IDS,
    S2SameEvidenceExperimentError,
    _case_identity,
    _captured_call_rows,
    _compile_specialist_context,
    _evidence_index,
    _normalize_numeric,
    _NUMERIC,
    _perform_node_call,
    _usage_summary,
    _validate_lead,
    _validate_specialist,
    _validate_synthesis,
    _validate_verifier,
    _validate_writer,
    _write_exclusive,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


DIAGNOSTIC_SCOPE = "FIN_0_1_3_S2_05_DELL_R1_QUARANTINED_COLLECT_ALL"
ADMISSION_SCHEMA = "fin_ia_0_1_3_s2_05_dell_r1_collect_all_admission_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s2_05_dell_r1_collect_all_result_v1_0"


def issue_diagnostic_admission(
    *,
    execution_git_commit: str,
    runtime_sha256: str,
    policy_sha256: str,
    original_admission_digest: str,
    original_lead_capture_sha256: str,
    original_lead_capture_digest: str,
    issued_at: str,
    expires_at: str,
    nonce: str,
) -> dict[str, Any]:
    run_id = "fin013_s2_05_dell_r1_collect_all_" + canonical_digest(
        {"git": execution_git_commit, "nonce": nonce, "source": original_lead_capture_digest}
    )[:20]
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "admission_id": "admission::" + run_id,
        "scope": DIAGNOSTIC_SCOPE,
        "case_key": "DELL",
        "run_id": run_id,
        "attempt_id": run_id + "::attempt_1",
        "runtime_identity": run_id + "::runtime_1",
        "execution_git_commit": execution_git_commit,
        "runtime_sha256": runtime_sha256,
        "policy_sha256": policy_sha256,
        "original_admission_digest": original_admission_digest,
        "original_lead_capture_sha256": original_lead_capture_sha256,
        "original_lead_capture_digest": original_lead_capture_digest,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce_digest": canonical_digest(nonce),
        "maximum_new_provider_calls": 9,
        "retry_count": 0,
        "fallback_count": 0,
        "state": "issued_unconsumed",
        "quarantined_non_promotable": True,
    }
    return {**body, "admission_digest": canonical_digest(body)}


def execute_quarantined_collect_all(
    *,
    admission: Mapping[str, Any],
    original_lead_capture: Path,
    case_input: Mapping[str, Any],
    policy: Mapping[str, Any],
    execution_git_commit: str,
    runtime_sha256: str,
    policy_sha256: str,
    runtime_root: Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    provider_call: Callable[..., Mapping[str, Any]],
    observed_at: str,
) -> dict[str, Any]:
    _validate_admission(
        admission,
        original_lead_capture=original_lead_capture,
        execution_git_commit=execution_git_commit,
        runtime_sha256=runtime_sha256,
        policy_sha256=policy_sha256,
        observed_at=observed_at,
    )
    root = runtime_root.resolve()
    if root.exists():
        raise S2SameEvidenceExperimentError("collect_all_runtime_root_exists")
    if shared_ledger.path.resolve() == root or root in shared_ledger.path.resolve().parents:
        raise S2SameEvidenceExperimentError("collect_all_shared_ledger_inside_runtime_root")
    captures_dir = root / "raw_model_only" / "captures"
    captures_dir.mkdir(parents=True)
    _write_exclusive(
        root / "QUARANTINED_NON_PROMOTABLE.json",
        {
            "schema_version": "fin_ia_0_1_3_quarantined_marker_v1_0",
            "business_promotable": False,
            "hidden_scoring_eligible": False,
            "formal_raw_candidate": False,
            "reason": "R1 Lead failed formal validation; downstream calls are collect-all diagnostics.",
        },
    )
    reservation = shared_ledger.reserve(
        admission_digest=str(admission["admission_digest"]),
        admission_id=str(admission["admission_id"]),
        scope=str(admission["scope"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        runtime_identity=str(admission["runtime_identity"]),
        reserved_at=observed_at,
    )

    source_capture = json.loads(original_lead_capture.read_text(encoding="utf-8"))
    lead = json.loads(str(source_capture["gateway_result"]["content"]))
    findings: list[dict[str, Any]] = []
    outputs: dict[str, Any] = {"lead": lead, "specialists": []}
    _audit(
        findings,
        phase="lead_planning",
        node_id="lead",
        output=lead,
        case_input=case_input,
        validator=lambda: _validate_lead(lead, case_input=case_input, policy=policy),
        continuation="reuse_immutable_raw_lead_as_diagnostic_plan_only",
    )

    call_index = 2
    for unit in lead.get("research_units", []):
        node_id = str(unit.get("unit_id") or f"missing_unit_{call_index}")
        specialist = _call_or_placeholder(
            findings=findings,
            node_type="specialist_judgment",
            node_id=node_id,
            context=_compile_specialist_context(case_input, unit),
            case_input=case_input,
            admission=admission,
            policy=policy,
            provider_call=provider_call,
            captures_dir=captures_dir,
            call_index=call_index,
            placeholder=_specialist_placeholder(case_input, unit),
        )
        _audit(
            findings,
            phase="specialist_judgment",
            node_id=node_id,
            output=specialist,
            case_input=case_input,
            validator=lambda specialist=specialist, unit=unit: _validate_specialist(
                specialist, case_input=case_input, unit=unit, policy=policy
            ),
            continuation="pass_raw_specialist_to_downstream_quarantine_context",
        )
        outputs["specialists"].append(specialist)
        call_index += 1

    synthesis_context = {
        "case_identity": _case_identity(case_input),
        "evidence_index": _evidence_index(case_input),
        "derived_numeric": deepcopy(case_input["derived_numeric"]),
        "explicit_gaps": deepcopy(case_input["explicit_gaps"]),
        "lead_plan": lead,
        "specialist_outputs": outputs["specialists"],
    }
    synthesis = _call_or_placeholder(
        findings=findings,
        node_type="cross_cell_synthesis",
        node_id="synthesis",
        context=synthesis_context,
        case_input=case_input,
        admission=admission,
        policy=policy,
        provider_call=provider_call,
        captures_dir=captures_dir,
        call_index=call_index,
        placeholder=_synthesis_placeholder(case_input, outputs["specialists"]),
    )
    _audit(
        findings,
        phase="cross_cell_synthesis",
        node_id="synthesis",
        output=synthesis,
        case_input=case_input,
        validator=lambda: _validate_synthesis(
            synthesis, case_input=case_input, specialists=outputs["specialists"]
        ),
        continuation="pass_raw_synthesis_to_downstream_quarantine_context",
    )
    outputs["synthesis"] = synthesis
    call_index += 1

    writer_context = {
        "case_identity": _case_identity(case_input),
        "evidence_index": _evidence_index(case_input),
        "derived_numeric": deepcopy(case_input["derived_numeric"]),
        "explicit_gaps": deepcopy(case_input["explicit_gaps"]),
        "specialist_outputs": outputs["specialists"],
        "synthesis": synthesis,
        "required_section_ids": list(SECTION_IDS),
    }
    writer = _call_or_placeholder(
        findings=findings,
        node_type="writer",
        node_id="writer",
        context=writer_context,
        case_input=case_input,
        admission=admission,
        policy=policy,
        provider_call=provider_call,
        captures_dir=captures_dir,
        call_index=call_index,
        placeholder=_writer_placeholder(case_input, outputs["specialists"]),
    )
    _audit(
        findings,
        phase="writer",
        node_id="writer",
        output=writer,
        case_input=case_input,
        validator=lambda: _validate_writer(
            writer, case_input=case_input, specialists=outputs["specialists"]
        ),
        continuation="pass_raw_writer_to_verifier_quarantine_context",
    )
    outputs["writer"] = writer
    call_index += 1

    verifier_context = {
        **synthesis_context,
        "synthesis": synthesis,
        "writer": writer,
        "verifier_scope": "quarantined collect-all diagnostic; hidden gold unavailable",
    }
    verifier = _call_or_placeholder(
        findings=findings,
        node_type="verifier",
        node_id="verifier",
        context=verifier_context,
        case_input=case_input,
        admission=admission,
        policy=policy,
        provider_call=provider_call,
        captures_dir=captures_dir,
        call_index=call_index,
        placeholder=_verifier_placeholder(case_input, outputs["specialists"], writer),
    )
    _audit(
        findings,
        phase="verifier",
        node_id="verifier",
        output=verifier,
        case_input=case_input,
        validator=lambda: _validate_verifier(
            verifier,
            case_input=case_input,
            specialists=outputs["specialists"],
            writer=writer,
        ),
        continuation="terminalize_quarantine_without_business_promotion",
    )
    outputs["verifier"] = verifier

    call_rows = _captured_call_rows(captures_dir)
    usage = _usage_summary(call_rows, policy)
    if len(call_rows) != 9:
        findings.append(
            {
                "phase": "diagnostic_terminal",
                "node_id": "collect_all",
                "formal_code": "collect_all_expected_nine_new_captures",
                "numeric_findings": [],
                "continuation": "none",
            }
        )
    result_body = {
        "schema_version": RESULT_SCHEMA,
        "status": "quarantined_collect_all_complete",
        "business_promotable": False,
        "formal_raw_candidate": False,
        "hidden_scoring_eligible": False,
        "case_key": "DELL",
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "admission_digest": admission["admission_digest"],
        "source_R1_lead_capture": {
            "sha256": admission["original_lead_capture_sha256"],
            "capture_digest": admission["original_lead_capture_digest"],
            "formal_status": "failed_experiment_a_unbound_numeric_surface",
        },
        "new_provider_calls": len(call_rows),
        "full_logical_chain_calls_including_reused_lead": len(call_rows) + 1,
        "call_results": call_rows,
        "usage_new_calls": usage,
        "finding_count": len(findings),
        "findings": findings,
        "raw_output_digests": {
            "lead": canonical_digest(lead),
            "specialists": [canonical_digest(row) for row in outputs["specialists"]],
            "synthesis": canonical_digest(synthesis),
            "writer": canonical_digest(writer),
            "verifier": canonical_digest(verifier),
        },
        "retry_count": 0,
        "fallback_count": 0,
        "business_artifact_promotions": 0,
        "supervisor_corrections": 0,
        "observed_at": observed_at,
        "reservation_digest": reservation.reservation_digest,
    }
    result = {**result_body, "result_digest": canonical_digest(result_body)}
    _write_exclusive(root / "quarantined_collect_all_result.json", result)
    receipt = shared_ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status="quarantined_collect_all_complete",
        terminal_phase="diagnostic_complete",
        terminal_code="collect_all_completed_with_findings",
        terminal_result_digest=str(result["result_digest"]),
        finalized_at=observed_at,
    )
    return {**result, "shared_admission_receipt": receipt.as_dict()}


def _call_or_placeholder(
    *,
    findings: list[dict[str, Any]],
    placeholder: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        _, output = _perform_node_call(**kwargs)
        return output
    except S2SameEvidenceExperimentError as exc:
        findings.append(
            {
                "phase": str(kwargs["node_type"]),
                "node_id": str(kwargs["node_id"]),
                "formal_code": exc.code,
                "numeric_findings": [],
                "continuation": "typed_local_placeholder_after_unusable_raw_output",
            }
        )
        return placeholder


def _audit(
    findings: list[dict[str, Any]],
    *,
    phase: str,
    node_id: str,
    output: Mapping[str, Any],
    case_input: Mapping[str, Any],
    validator: Callable[[], None],
    continuation: str,
) -> None:
    formal_code = "pass"
    try:
        validator()
    except S2SameEvidenceExperimentError as exc:
        formal_code = exc.code
    numeric = _numeric_findings(output, case_input)
    if formal_code != "pass" or numeric:
        findings.append(
            {
                "phase": phase,
                "node_id": node_id,
                "formal_code": formal_code,
                "numeric_findings": numeric,
                "raw_output_digest": canonical_digest(output),
                "continuation": continuation,
            }
        )


def _numeric_findings(value: Any, case_input: Mapping[str, Any], path: str = "$") -> list[dict[str, Any]]:
    allowed = {
        _normalize_numeric(token)
        for token in _NUMERIC.findall(json.dumps(case_input, ensure_ascii=False))
    }
    rows: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            rows.extend(_numeric_findings(item, case_input, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_numeric_findings(item, case_input, f"{path}[{index}]"))
    elif isinstance(value, str):
        observed = sorted({_normalize_numeric(token) for token in _NUMERIC.findall(value)})
        unbound = [token for token in observed if token not in allowed]
        if unbound:
            rows.append({"path": path, "unbound_tokens": unbound})
    return rows


def _validate_admission(
    admission: Mapping[str, Any],
    *,
    original_lead_capture: Path,
    execution_git_commit: str,
    runtime_sha256: str,
    policy_sha256: str,
    observed_at: str,
) -> None:
    body = {key: deepcopy(value) for key, value in admission.items() if key != "admission_digest"}
    if (
        admission.get("schema_version") != ADMISSION_SCHEMA
        or admission.get("scope") != DIAGNOSTIC_SCOPE
        or admission.get("state") != "issued_unconsumed"
        or admission.get("quarantined_non_promotable") is not True
        or admission.get("admission_digest") != canonical_digest(body)
        or admission.get("execution_git_commit") != execution_git_commit
        or admission.get("runtime_sha256") != runtime_sha256
        or admission.get("policy_sha256") != policy_sha256
        or admission.get("original_lead_capture_sha256") != _sha256(original_lead_capture)
        or _time(observed_at) > _time(str(admission.get("expires_at") or ""))
    ):
        raise S2SameEvidenceExperimentError("collect_all_admission_invalid")


def _specialist_placeholder(case: Mapping[str, Any], unit: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_key": case["case_key"], "as_of": case["as_of"], "unit_id": unit["unit_id"],
        "epistemic_state": "cannot_infer", "judgment": "Diagnostic placeholder after unusable raw output.",
        "mechanism": "Cannot infer.", "financial_or_valuation_link": "Cannot infer.",
        "evidence_ids": [], "counterevidence_ids": [], "gap_ids": list(unit["gap_ids"]),
        "what_would_change": "A valid case-local specialist output is required.",
    }


def _synthesis_placeholder(case: Mapping[str, Any], specialists: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "case_key": case["case_key"], "as_of": case["as_of"], "thesis": "Cannot infer.",
        "confidence": "Cannot infer.", "unit_ids": [str(row["unit_id"]) for row in specialists],
        "dependencies": [], "conflicts": [],
        "material_gap_ids": [str(row["gap_id"]) for row in case["explicit_gaps"]],
        "counter_thesis": "Cannot infer.", "what_would_change": "Valid specialist outputs are required.",
    }


def _writer_placeholder(case: Mapping[str, Any], specialists: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    units = [str(row["unit_id"]) for row in specialists]
    gaps = [str(row["gap_id"]) for row in case["explicit_gaps"]]
    return {
        "case_key": case["case_key"], "as_of": case["as_of"], "title": "Quarantined diagnostic placeholder",
        "sections": [
            {"section_id": section, "heading": section, "narrative": "Cannot infer.",
             "evidence_ids": [], "unit_ids": units, "gap_ids": gaps}
            for section in SECTION_IDS
        ],
        "overall_boundary": "Not a research candidate.",
    }


def _verifier_placeholder(
    case: Mapping[str, Any], specialists: Sequence[Mapping[str, Any]], writer: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "case_key": case["case_key"], "as_of": case["as_of"],
        "decision": "return_material_failure", "material_failure": True,
        "findings": [{"severity": "L1", "code": "diagnostic_unusable_raw_output",
                      "node_refs": [], "evidence_ids": [],
                      "explanation": "A raw node output was unusable."}],
        "checked_unit_ids": [str(row["unit_id"]) for row in specialists],
        "checked_section_ids": [str(row["section_id"]) for row in writer["sections"]],
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
