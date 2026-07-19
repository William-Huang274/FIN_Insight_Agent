"""Static P01-G2 operational-tranche contract validator.

This module deliberately freezes authority and scenario scope only.  It must
not import a compiler, a transport, a receipt ledger, or a runtime store.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .models import canonical_digest


P01_G2_TRANCHE_SCHEMA = "finsight_point01_p01_g2_operational_tranche_manifest_v1_0"
P01_G2_TRANCHE_GATE_SCHEMA = "finsight_point01_p01_g2_operational_tranche_gate_v1_0"
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
_SELECTED_SOURCE_IDS = (
    "p01-baseline-separated-input",
    "p01-oracle-path-access",
    "p02-stale-or-superseded-pack",
    "p03-network-tool-transport",
)


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def tranche_payload(tranche: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in tranche.items() if key != "tranche_digest"}


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
    """Return a deterministic freeze-only disposition; never execute a case."""

    errors: list[str] = []
    if tranche.get("schema_version") != P01_G2_TRANCHE_SCHEMA:
        errors.append("tranche_schema_invalid")
    if tranche.get("status") != "P01_G2_0_TRANCHE_FROZEN_PENDING_INDEPENDENT_EXECUTION_AUTHORITY":
        errors.append("tranche_status_invalid")
    if tranche.get("tranche_digest") != canonical_digest(tranche_payload(tranche)):
        errors.append("tranche_digest_mismatch")

    family = tranche.get("v2_10_family")
    expected_family = {
        "package_digest": v2_10_package.get("package_digest"),
        "package_gate_digest": v2_10_package_gate.get("gate_digest"),
        "plan_digest": v2_10_plan.get("plan_digest"),
        "plan_gate_digest": v2_10_plan_gate.get("gate_digest"),
        "blueprint_digest": v2_10_blueprint.get("blueprint_digest"),
        "blueprint_gate_digest": v2_10_blueprint_gate.get("gate_digest"),
        "trigger_ddl_digest": v2_10_package.get("trigger_ddl_contract", {}).get("normalized_ddl_digest") if isinstance(v2_10_package.get("trigger_ddl_contract"), Mapping) else None,
        "fixed_store_sha256": v2_10_package.get("fixed_store_fingerprints", {}).get("fixed_approval_store", {}).get("sha256") if isinstance(v2_10_package.get("fixed_store_fingerprints"), Mapping) else None,
    }
    if not isinstance(family, Mapping) or dict(family) != expected_family or any(not _is_sha256(value) for value in expected_family.values()):
        errors.append("v2_10_family_binding_invalid")

    input_binding = tranche.get("v2_10_staged_input_binding")
    package_hashes = v2_10_package.get("input_file_sha256")
    if not isinstance(input_binding, Mapping) or not isinstance(package_hashes, Mapping):
        errors.append("v2_10_staged_input_binding_missing")
    else:
        if input_binding.get("input_hash_count") != 79 or input_binding.get("input_file_sha256") != package_hashes or input_binding.get("input_hashes_digest") != canonical_digest(package_hashes):
            errors.append("v2_10_staged_input_binding_invalid")

    boundary = tranche.get("authority_boundary")
    if not isinstance(boundary, Mapping) or boundary.get("legacy_authority") != "retained" or boundary.get("production_readiness") != "not_admitted" or boundary.get("active_authority_forbidden") is not True or boundary.get("operational_execution_authorized") is not False:
        errors.append("authority_boundary_invalid")

    cases = tranche.get("selected_cases")
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)) or len(cases) != 4:
        errors.append("selected_case_count_invalid")
    else:
        source_ids = tuple(str(case.get("source_matrix_scenario_id")) for case in cases if isinstance(case, Mapping))
        case_ids = tuple(str(case.get("case_id")) for case in cases if isinstance(case, Mapping))
        if source_ids != _SELECTED_SOURCE_IDS or len(set(case_ids)) != 4:
            errors.append("selected_case_source_or_identity_invalid")
        baseline = next((case for case in cases if isinstance(case, Mapping) and case.get("case_id") == "g2-baseline"), None)
        wrong = next((case for case in cases if isinstance(case, Mapping) and case.get("case_id") == "g2-wrong-package-or-approval"), None)
        stale = next((case for case in cases if isinstance(case, Mapping) and case.get("case_id") == "g2-stale-input-version-drift"), None)
        transport = next((case for case in cases if isinstance(case, Mapping) and case.get("case_id") == "g2-unauthorized-transport"), None)
        if not isinstance(baseline, Mapping) or baseline.get("expected_terminal") != "succeeded" or baseline.get("stop_rule") != "fail_fast_stop_all_remaining_cases":
            errors.append("baseline_contract_invalid")
        if not isinstance(wrong, Mapping) or wrong.get("expected_terminal") != "pre_authority_typed_deny:package_or_approval_mismatch" or wrong.get("valid_authority_must_not_issue") is not True:
            errors.append("wrong_authority_contract_invalid")
        if not isinstance(stale, Mapping) or stale.get("expected_terminal") != "typed_stop:superseded_pack_version_or_pack_not_fresh":
            errors.append("stale_contract_invalid")
        if not isinstance(transport, Mapping) or transport.get("expected_terminal") != "typed_stop:shadow_scope_violation" or transport.get("expected_post_counts", {}).get("network_success") != 0 or transport.get("expected_post_counts", {}).get("tool_success") != 0:
            errors.append("transport_contract_invalid")
        for case in cases:
            if not isinstance(case, Mapping) or case.get("single_use_authority_receipt") != "independent_per_case_no_shared_nonce_receipt_retry_replay_or_renewal" or case.get("expected_pre_counts") != _ZERO_COUNTS or not isinstance(case.get("artifact_refs"), Sequence) or not isinstance(case.get("rollback_cleanup"), Mapping):
                errors.append("case_contract_missing_required_boundary")
                break

    source_scenarios = source_matrix.get("scenarios")
    source_ids = {str(item.get("scenario_id")) for item in source_scenarios if isinstance(item, Mapping)} if isinstance(source_scenarios, Sequence) else set()
    deferred = tranche.get("deferred_operational_regression_backlog")
    deferred_ids = tuple(str(item.get("scenario_id")) for item in deferred if isinstance(item, Mapping)) if isinstance(deferred, Sequence) and not isinstance(deferred, (str, bytes)) else ()
    expected_deferred = tuple(sorted(source_ids.difference(_SELECTED_SOURCE_IDS)))
    if len(deferred_ids) != 12 or tuple(sorted(deferred_ids)) != expected_deferred or len(set(deferred_ids)) != 12:
        errors.append("deferred_backlog_invalid")

    receipt = tranche.get("proposed_reviewer_decision_receipt")
    forbidden_active = {"receipt_id", "receipt_digest", "issued_at", "expires_at", "nonce", "active"}
    if not isinstance(receipt, Mapping) or receipt.get("state") != "unresolved_not_active" or receipt.get("schema_version") != "finsight_point01_p01_g2_proposed_reviewer_decision_receipt_v1_0" or not isinstance(receipt.get("canonical_digest_inputs"), Mapping) or any(key in receipt for key in forbidden_active):
        errors.append("reviewer_receipt_template_invalid")

    if tranche.get("freeze_execution_counts") != _ZERO_COUNTS:
        errors.append("freeze_execution_counts_nonzero")
    return {
        "status": "pass" if not errors else "fail_closed",
        "errors": tuple(sorted(set(errors))),
        "tranche_digest": tranche.get("tranche_digest"),
        "selected_case_count": len(cases) if isinstance(cases, Sequence) and not isinstance(cases, (str, bytes)) else 0,
        "deferred_backlog_count": len(deferred_ids),
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
        "next_step": "independent_execution_authority_review_required_no_receipt_or_scenario_execution",
    }
    return {**payload, "gate_digest": canonical_digest(payload)}
