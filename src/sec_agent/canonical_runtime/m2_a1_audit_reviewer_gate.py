"""Reviewer closeout gate for a future, exact-admitted M2-A1 audit run."""

from __future__ import annotations

from typing import Any, Mapping

from .m2_a1_audit_oracle import M2A1OracleEvaluation
from .m2_a1_audit_result import M2A1ImmutableActualResult
from .m2_a1_execution_receipt import M2A1ExecutionReceipt, M2A1ExternalPackageAdmission, validate_external_admission
from .models import StrictModel, canonical_digest


class M2A1ReviewerGateResult(StrictModel):
    status: str
    package_digest: str
    scenario_ids: tuple[str, ...]
    actual_result_digests: tuple[str, ...]
    oracle_evaluation_digests: tuple[str, ...]
    receipt_status: str
    errors: tuple[str, ...] = ()
    gate_digest: str


def review_future_actual(
    *,
    package: Mapping[str, Any],
    actual_results: tuple[M2A1ImmutableActualResult, ...],
    oracle_evaluations: tuple[M2A1OracleEvaluation, ...],
    expected_scenario_ids: tuple[str, ...],
    admission: M2A1ExternalPackageAdmission | None,
    consumed_receipt: M2A1ExecutionReceipt | None,
    receipt_ledger_state: Mapping[str, Any] | None,
    receipt_terminal_event_digest: str | None,
    require_terminal_event: bool = True,
    expected_human_approval_digest: str | None = None,
) -> M2A1ReviewerGateResult:
    """Require exact scenario coverage and scored oracle outcomes; no truthy shortcuts."""

    package_ref = str(package.get("package_ref") or "")
    package_digest = str(package.get("package_digest") or "")
    scope = str(package.get("scope") or "")
    authority_boundary = str(package.get("authority_boundary") or "")
    errors: list[str] = []
    if package.get("execution_mode") != "external_admission_gated":
        errors.append("package_execution_mode_invalid")
    effective_human_approval_digest = expected_human_approval_digest or (admission.human_approval_digest if admission is not None else None)
    admission_check = validate_external_admission(
        admission,
        package_ref=package_ref,
        executable_package_digest=package_digest,
        scope=scope,
        authority_boundary=authority_boundary,
        expected_human_approval_digest=effective_human_approval_digest,
    )
    if admission_check["status"] != "pass":
        errors.append(str(admission_check["status"]))
    if consumed_receipt is None or admission is None:
        errors.append("consumed_receipt_missing")
        receipt_status = "consumed_receipt_missing"
    else:
        receipt_errors = []
        if not consumed_receipt.verify_digest():
            receipt_errors.append("consumed_receipt_digest_invalid")
        if consumed_receipt.state != "consumed_before_run":
            receipt_errors.append("receipt_not_consumed_before_run")
        if consumed_receipt.package_ref != package_ref or consumed_receipt.executable_package_digest != package_digest or consumed_receipt.scope != scope:
            receipt_errors.append("consumed_receipt_package_binding_mismatch")
        if consumed_receipt.admission_digest != admission.admission_digest or consumed_receipt.reviewer_identity != admission.reviewer_identity:
            receipt_errors.append("consumed_receipt_admission_binding_mismatch")
        if consumed_receipt.human_approval_digest != effective_human_approval_digest:
            receipt_errors.append("consumed_receipt_human_approval_binding_mismatch")
        if receipt_ledger_state is None or receipt_ledger_state.get("state") != "consumed_before_run":
            receipt_errors.append("receipt_ledger_consumption_missing")
        if require_terminal_event and not receipt_terminal_event_digest:
            receipt_errors.append("receipt_terminal_event_missing")
        errors.extend(receipt_errors)
        receipt_status = "pass" if not receipt_errors else "receipt_binding_mismatch"

    actual_by_scenario = {result.scenario_id: result for result in actual_results}
    evaluation_by_scenario = {evaluation.scenario_id: evaluation for evaluation in oracle_evaluations}
    expected = tuple(sorted(expected_scenario_ids))
    if len(set(expected)) != len(expected):
        errors.append("expected_scenario_ids_not_unique")
    if tuple(sorted(actual_by_scenario)) != expected:
        errors.append("actual_scenario_coverage_mismatch")
    if tuple(sorted(evaluation_by_scenario)) != expected:
        errors.append("oracle_scenario_coverage_mismatch")
    allowed_oracle_statuses = {"pass", "exact_expected_typed_stop_match"}
    for scenario_id in expected:
        actual = actual_by_scenario.get(scenario_id)
        evaluation = evaluation_by_scenario.get(scenario_id)
        if actual is None or evaluation is None:
            continue
        if not actual.verify_immutable_digest():
            errors.append(f"actual_digest_invalid:{scenario_id}")
        if actual.executable_package_digest != package_digest:
            errors.append(f"actual_package_digest_mismatch:{scenario_id}")
        if evaluation.actual_result_digest != actual.actual_result_digest:
            errors.append(f"oracle_actual_digest_mismatch:{scenario_id}")
        if evaluation.status not in allowed_oracle_statuses:
            errors.append(f"oracle_status_not_accepted:{scenario_id}:{evaluation.status}")
        if evaluation.errors:
            errors.append(f"oracle_errors_present:{scenario_id}")
        counts = actual.canary_snapshot.get("counts") if isinstance(actual.canary_snapshot, Mapping) else None
        if not isinstance(counts, Mapping):
            errors.append(f"actual_canary_snapshot_invalid:{scenario_id}")
        elif int(counts.get("network_request_success_count", 0)) != 0:
            errors.append(f"network_request_success_nonzero:{scenario_id}")

    payload = {
        "status": "pass" if not errors else "fail_closed",
        "package_digest": package_digest,
        "scenario_ids": expected,
        "actual_result_digests": tuple(sorted(result.actual_result_digest for result in actual_results)),
        "oracle_evaluation_digests": tuple(sorted(evaluation.evaluation_digest for evaluation in oracle_evaluations)),
        "receipt_status": receipt_status,
        "errors": tuple(sorted(set(errors))),
    }
    return M2A1ReviewerGateResult(**payload, gate_digest=canonical_digest(payload))
