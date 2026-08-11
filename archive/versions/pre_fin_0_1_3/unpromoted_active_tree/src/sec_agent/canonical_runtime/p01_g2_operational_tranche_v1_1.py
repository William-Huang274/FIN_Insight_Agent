"""Static validator for the repaired P01-G2.0 authority and coverage model.

The module freezes a future baseline authority boundary plus three *pre-authority*
negative probes.  It deliberately has no compiler, transport, ledger, or store
imports: validating a tranche must not acquire execution capability.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .models import canonical_digest


P01_G2_TRANCHE_SCHEMA = "finsight_point01_p01_g2_operational_tranche_manifest_v1_1"
P01_G2_TRANCHE_GATE_SCHEMA = "finsight_point01_p01_g2_operational_tranche_gate_v1_1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ZERO_COUNTS = {
    "active_approval": 0,
    "admission": 0,
    "receipt": 0,
    "formal_namespace": 0,
    "runtime": 0,
    "baseline": 0,
    "external": 0,
    "network_success": 0,
    "tool_success": 0,
    "model": 0,
    "provider": 0,
    "fixed_store_write": 0,
    "legacy_authority_change": 0,
}
_SELECTED_ORIGINAL_SOURCE_IDS = (
    "p01-baseline-separated-input",
    "p02-stale-or-superseded-pack",
    "p03-network-tool-transport",
)
_SUPPLEMENTAL_CASE_ID = "g2-wrong-package-or-approval"


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def tranche_payload(tranche: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in tranche.items() if key != "tranche_digest"}


def _expected_family(
    *,
    package: Mapping[str, Any],
    package_gate: Mapping[str, Any],
    plan: Mapping[str, Any],
    plan_gate: Mapping[str, Any],
    blueprint: Mapping[str, Any],
    blueprint_gate: Mapping[str, Any],
) -> dict[str, object]:
    trigger = package.get("trigger_ddl_contract")
    stores = package.get("fixed_store_fingerprints")
    fixed = stores.get("fixed_approval_store") if isinstance(stores, Mapping) else None
    return {
        "package_digest": package.get("package_digest"),
        "package_gate_digest": package_gate.get("gate_digest"),
        "plan_digest": plan.get("plan_digest"),
        "plan_gate_digest": plan_gate.get("gate_digest"),
        "blueprint_digest": blueprint.get("blueprint_digest"),
        "blueprint_gate_digest": blueprint_gate.get("gate_digest"),
        "trigger_ddl_digest": trigger.get("normalized_ddl_digest") if isinstance(trigger, Mapping) else None,
        "fixed_store_sha256": fixed.get("sha256") if isinstance(fixed, Mapping) else None,
    }


def _baseline_post_counts() -> dict[str, int | str]:
    return {
        "valid_authority_issue_count": 1,
        "receipt_registration_count": 1,
        "receipt_consume_count": 1,
        "formal_namespace_count": 1,
        "runtime_materialization_count": 1,
        "terminal_lifecycle_write_count": 1,
        "baseline_execution_count": 1,
        "network_success": 0,
        "tool_success": 0,
        "model_success": 0,
        "provider_success": 0,
        "fixed_store_write": 0,
        "legacy_authority_change": 0,
        "terminal": "succeeded",
    }


def _negative_post_counts(*, terminal: str, probe_count_key: str) -> dict[str, int | str]:
    return {
        "valid_authority_issue_count": 0,
        "receipt_registration_count": 0,
        "receipt_consume_count": 0,
        "formal_namespace_count": 0,
        "runtime_materialization_count": 0,
        "terminal_lifecycle_write_count": 0,
        "baseline_execution_count": 0,
        "network_success": 0,
        "tool_success": 0,
        "model_success": 0,
        "provider_success": 0,
        "fixed_store_write": 0,
        "legacy_authority_change": 0,
        probe_count_key: 1,
        "terminal": terminal,
    }


def _negative_counts_are_pre_authority(counts: Mapping[str, Any]) -> bool:
    required_zero = {
        "valid_authority_issue_count",
        "receipt_registration_count",
        "receipt_consume_count",
        "formal_namespace_count",
        "runtime_materialization_count",
        "terminal_lifecycle_write_count",
        "baseline_execution_count",
        "network_success",
        "tool_success",
        "model_success",
        "provider_success",
        "fixed_store_write",
        "legacy_authority_change",
    }
    return all(counts.get(key) == 0 for key in required_zero)


def _has_forbidden_future_artifact_ref(refs: object) -> bool:
    """Allow a *pre-authority admission preflight* observation, not authority artifacts."""

    forbidden_fragments = ("future_admission", "external_admission", "receipt", "runtime", "namespace", "ledger")
    if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)):
        return True
    return any(any(fragment in str(ref).lower() for fragment in forbidden_fragments) for ref in refs)


def validate_p01_g2_operational_tranche(
    tranche: Mapping[str, Any],
    *,
    source_matrix: Mapping[str, Any],
    v2_10_package: Mapping[str, Any],
    v2_10_package_gate: Mapping[str, Any],
    v2_10_plan: Mapping[str, Any],
    v2_10_plan_gate: Mapping[str, Any],
    v2_10_blueprint: Mapping[str, Any],
    v2_10_blueprint_gate: Mapping[str, Any],
) -> dict[str, object]:
    """Return a deterministic, freeze-only disposition without running a case."""

    errors: list[str] = []
    if tranche.get("schema_version") != P01_G2_TRANCHE_SCHEMA:
        errors.append("tranche_schema_invalid")
    if tranche.get("status") != "P01_G2_0_TRANCHE_FROZEN_PENDING_INDEPENDENT_EXECUTION_AUTHORITY":
        errors.append("tranche_status_invalid")
    if tranche.get("tranche_digest") != canonical_digest(tranche_payload(tranche)):
        errors.append("tranche_digest_mismatch")

    expected_family = _expected_family(
        package=v2_10_package,
        package_gate=v2_10_package_gate,
        plan=v2_10_plan,
        plan_gate=v2_10_plan_gate,
        blueprint=v2_10_blueprint,
        blueprint_gate=v2_10_blueprint_gate,
    )
    if tranche.get("v2_10_family") != expected_family or any(not _is_sha256(value) for value in expected_family.values()):
        errors.append("v2_10_family_binding_invalid")

    package_hashes = v2_10_package.get("input_file_sha256")
    input_binding = tranche.get("v2_10_staged_input_binding")
    if not isinstance(package_hashes, Mapping) or not isinstance(input_binding, Mapping):
        errors.append("v2_10_staged_input_binding_missing")
    elif (
        input_binding.get("input_hash_count") != 79
        or input_binding.get("input_file_sha256") != package_hashes
        or input_binding.get("input_hashes_digest") != canonical_digest(package_hashes)
    ):
        errors.append("v2_10_staged_input_binding_invalid")

    boundary = tranche.get("authority_boundary")
    if not isinstance(boundary, Mapping) or (
        boundary.get("legacy_authority") != "retained"
        or boundary.get("production_readiness") != "not_admitted"
        or boundary.get("active_authority_forbidden") is not True
        or boundary.get("operational_execution_authorized") is not False
    ):
        errors.append("authority_boundary_invalid")

    blueprint_exact = v2_10_blueprint.get("exact_binding")
    blueprint_other = v2_10_blueprint.get("all_other_scenarios")
    blueprint_contract = tranche.get("blueprint_authority_contract")
    expected_blueprint_contract = {
        "authorized_baseline_scenario_id": blueprint_exact.get("scenario_id") if isinstance(blueprint_exact, Mapping) else None,
        "authorized_baseline_input_ref": blueprint_exact.get("input_ref") if isinstance(blueprint_exact, Mapping) else None,
        "authorized_baseline_mutation": blueprint_exact.get("mutation") if isinstance(blueprint_exact, Mapping) else None,
        "all_other_scenarios_authority_issue_forbidden": blueprint_other.get("authority_issue_forbidden") if isinstance(blueprint_other, Mapping) else None,
        "all_other_scenarios_count": blueprint_other.get("count") if isinstance(blueprint_other, Mapping) else None,
    }
    if blueprint_contract != expected_blueprint_contract or expected_blueprint_contract["authorized_baseline_scenario_id"] != _SELECTED_ORIGINAL_SOURCE_IDS[0] or expected_blueprint_contract["all_other_scenarios_authority_issue_forbidden"] is not True or expected_blueprint_contract["all_other_scenarios_count"] != 15:
        errors.append("blueprint_authority_scope_invalid")

    source_scenarios = source_matrix.get("scenarios")
    source_ids = {str(item.get("scenario_id")) for item in source_scenarios if isinstance(item, Mapping)} if isinstance(source_scenarios, Sequence) else set()
    if len(source_ids) != 16:
        errors.append("source_matrix_cardinality_invalid")

    cases = tranche.get("selected_cases")
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)) or len(cases) != 4:
        errors.append("selected_case_count_invalid")
        cases = ()
    by_case = {str(case.get("case_id")): case for case in cases if isinstance(case, Mapping)}
    if set(by_case) != {"g2-baseline", _SUPPLEMENTAL_CASE_ID, "g2-stale-input-version-drift", "g2-unauthorized-transport"}:
        errors.append("selected_case_identity_invalid")

    baseline = by_case.get("g2-baseline")
    if not isinstance(baseline, Mapping) or (
        baseline.get("coverage_class") != "selected_original_matrix_scenario"
        or baseline.get("source_matrix_scenario_id") != _SELECTED_ORIGINAL_SOURCE_IDS[0]
        or baseline.get("future_authority_mode") != "baseline_only_future_single_use_authority_allowed"
        or baseline.get("expected_terminal") != "succeeded"
        or baseline.get("expected_post_counts") != _baseline_post_counts()
        or baseline.get("stop_rule") != "fail_fast_stop_all_remaining_cases"
    ):
        errors.append("baseline_authority_contract_invalid")

    supplemental = by_case.get(_SUPPLEMENTAL_CASE_ID)
    if not isinstance(supplemental, Mapping) or (
        supplemental.get("coverage_class") != "supplemental_pre_authority_probe"
        or supplemental.get("source_matrix_scenario_id") is not None
        or supplemental.get("supplemental_case_id") != _SUPPLEMENTAL_CASE_ID
        or supplemental.get("future_authority_mode") != "pre_authority_only_no_admission_receipt_namespace_or_runtime"
        or supplemental.get("expected_terminal") != "pre_authority_typed_deny:package_or_approval_mismatch"
        or not isinstance(supplemental.get("expected_post_counts"), Mapping)
        or not _negative_counts_are_pre_authority(supplemental["expected_post_counts"])
    ):
        errors.append("supplemental_case_contract_invalid")
    elif _has_forbidden_future_artifact_ref(supplemental.get("artifact_refs", ())):
        errors.append("supplemental_case_artifact_scope_invalid")

    for case_id, source_id, terminal in (
        ("g2-stale-input-version-drift", _SELECTED_ORIGINAL_SOURCE_IDS[1], "typed_stop:superseded_pack_version_or_pack_not_fresh"),
        ("g2-unauthorized-transport", _SELECTED_ORIGINAL_SOURCE_IDS[2], "typed_stop:shadow_scope_violation"),
    ):
        case = by_case.get(case_id)
        if not isinstance(case, Mapping) or (
            case.get("coverage_class") != "selected_original_matrix_scenario"
            or case.get("source_matrix_scenario_id") != source_id
            or case.get("future_authority_mode") != "pre_authority_only_no_admission_receipt_namespace_or_runtime"
            or case.get("expected_terminal") != terminal
            or not isinstance(case.get("expected_post_counts"), Mapping)
            or not _negative_counts_are_pre_authority(case["expected_post_counts"])
        ):
            errors.append("negative_case_authority_or_runtime_invalid")
            break
        if _has_forbidden_future_artifact_ref(case.get("artifact_refs", ())):
            errors.append("negative_case_artifact_scope_invalid")
            break
    transport = by_case.get("g2-unauthorized-transport")
    if not isinstance(transport, Mapping) or transport.get("expected_post_counts", {}).get("network_success") != 0 or transport.get("expected_post_counts", {}).get("tool_success") != 0:
        errors.append("transport_success_boundary_invalid")

    coverage = tranche.get("original_matrix_coverage")
    deferred = tranche.get("deferred_original_regression_backlog")
    deferred_ids = tuple(str(item.get("scenario_id")) for item in deferred if isinstance(item, Mapping)) if isinstance(deferred, Sequence) and not isinstance(deferred, (str, bytes)) else ()
    expected_deferred = tuple(sorted(source_ids.difference(_SELECTED_ORIGINAL_SOURCE_IDS)))
    if not isinstance(coverage, Mapping) or (
        tuple(coverage.get("selected_original_source_matrix_ids", ())) != _SELECTED_ORIGINAL_SOURCE_IDS
        or tuple(sorted(coverage.get("deferred_original_source_matrix_ids", ()))) != expected_deferred
        or tuple(coverage.get("supplemental_case_ids", ())) != (_SUPPLEMENTAL_CASE_ID,)
        or coverage.get("original_matrix_count") != 16
        or len(deferred_ids) != 13
        or tuple(sorted(deferred_ids)) != expected_deferred
        or len(set(deferred_ids)) != 13
        or set(_SELECTED_ORIGINAL_SOURCE_IDS).intersection(deferred_ids)
        or set(_SELECTED_ORIGINAL_SOURCE_IDS).union(deferred_ids) != source_ids
        or "p01-oracle-path-access" not in deferred_ids
    ):
        errors.append("original_matrix_coverage_invalid")

    receipt = tranche.get("proposed_baseline_reviewer_decision_receipt")
    forbidden_active = {"receipt_id", "receipt_digest", "issued_at", "expires_at", "nonce", "active"}
    if not isinstance(receipt, Mapping) or (
        receipt.get("state") != "unresolved_not_active"
        or receipt.get("schema_version") != "finsight_point01_p01_g2_proposed_baseline_reviewer_decision_receipt_v1_1"
        or receipt.get("eligible_case_id") != "g2-baseline"
        or not isinstance(receipt.get("canonical_digest_inputs"), Mapping)
        or any(key in receipt for key in forbidden_active)
    ):
        errors.append("reviewer_receipt_template_invalid")

    if tranche.get("freeze_execution_counts") != _ZERO_COUNTS:
        errors.append("freeze_execution_counts_nonzero")
    return {
        "status": "pass" if not errors else "fail_closed",
        "errors": tuple(sorted(set(errors))),
        "tranche_digest": tranche.get("tranche_digest"),
        "selected_original_count": len(_SELECTED_ORIGINAL_SOURCE_IDS),
        "deferred_original_count": len(deferred_ids),
        "supplemental_case_count": 1,
        "execution_counts": dict(_ZERO_COUNTS),
    }


def gate_payload(*, tranche: Mapping[str, Any], verification: Mapping[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": P01_G2_TRANCHE_GATE_SCHEMA,
        "status": verification["status"],
        "tranche_id": tranche.get("tranche_id"),
        "tranche_digest": tranche.get("tranche_digest"),
        "verification": dict(verification),
        "execution_counts": dict(_ZERO_COUNTS),
        "next_step": "independent_execution_authority_review_required_baseline_only_no_negative_case_authority",
    }
    return {**payload, "gate_digest": canonical_digest(payload)}
