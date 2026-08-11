"""Immutable P01-G2.1-R1 forensic-repair contract helpers.

This module never opens the historical authority root or receipt ledger.  It
only makes a package-external reconciliation projection that preserves the
pre-R1 observability gap without rewriting the consumed receipt or terminal.
"""

from __future__ import annotations

from typing import Any, Mapping

from .models import canonical_digest


R1_INCIDENT_INPUT_SCHEMA = "finsight_point01_p01_g2_1_r1_incident_input_v1_0"
R1_RECONCILIATION_SCHEMA = "finsight_point01_p01_g2_1_r1_historical_incident_reconciliation_v1_0"
R1_PACKAGE_SCHEMA = "finsight_point01_p01_g2_1_r1_forensic_repair_package_v1_0"
R1_GATE_SCHEMA = "finsight_point01_p01_g2_1_r1_forensic_repair_gate_v1_0"
R1_1_RECONCILIATION_SCHEMA = "finsight_point01_p01_g2_1_r1_1_sanitization_reconciliation_v1_0"
R1_1_PACKAGE_SCHEMA = "finsight_point01_p01_g2_1_r1_1_sanitization_repair_package_v1_0"
R1_1_GATE_SCHEMA = "finsight_point01_p01_g2_1_r1_1_sanitization_repair_gate_v1_0"


def without_digest(value: Mapping[str, Any], digest_field: str) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != digest_field}


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def validate_incident_input(value: Mapping[str, Any], *, policy: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    historical = policy.get("historical_incident")
    if value.get("schema_version") != R1_INCIDENT_INPUT_SCHEMA:
        errors.append("incident_input_schema_invalid")
    if value.get("incident_input_digest") != canonical_digest(without_digest(value, "incident_input_digest")):
        errors.append("incident_input_digest_invalid")
    if not isinstance(historical, Mapping):
        errors.append("policy_historical_incident_invalid")
        return tuple(errors)
    for field in (
        "execution_package_digest",
        "execution_gate_digest",
        "baseline_result_digest",
        "terminal_digest",
        "fixed_approval_store_sha256",
    ):
        if value.get(field) != historical.get(field) or not _is_sha256(value.get(field)):
            errors.append(f"incident_input_{field}_mismatch")
    if value.get("ledger_sequence") != historical.get("ledger_sequence"):
        errors.append("incident_input_ledger_sequence_mismatch")
    if value.get("restricted_authority_root_ref") != historical.get("restricted_authority_root_ref"):
        errors.append("incident_input_authority_root_ref_mismatch")
    if value.get("historical_capture_status") != "not_persisted_pre_r1":
        errors.append("incident_input_capture_status_invalid")
    return tuple(sorted(errors))


def build_historical_reconciliation(*, incident_input: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    errors = validate_incident_input(incident_input, policy=policy)
    if errors:
        raise ValueError("p01_g2_1_r1_incident_input_invalid:" + ",".join(errors))
    counts = dict(policy["required_counts"])
    payload = {
        "schema_version": R1_RECONCILIATION_SCHEMA,
        "status": "historical_terminal_immutable_reconciled_pending_independent_review",
        "historical_terminal_digest": incident_input["terminal_digest"],
        "historical_result_digest": incident_input["baseline_result_digest"],
        "historical_ledger_sequence": incident_input["ledger_sequence"],
        "incident_link_method": "independent_immutable_reconciliation_artifact",
        "why_terminal_not_rewritten": "the prior append-only TERMINAL(outcome_unknown) predates R1 and the consumed receipt must remain immutable",
        "historical_child_execution_observation": {
            "schema_version": "finsight_point01_child_execution_incident_observation_v1_0",
            "capture_status": "not_persisted_pre_r1",
            "stage": "production_actual_clean_child",
            "returncode": None,
            "stdout": {"capture_status": "not_captured_pre_r1", "digest": None, "excerpt": ""},
            "stderr": {"capture_status": "not_captured_pre_r1", "digest": None, "excerpt": ""},
            "root_cause_status": "not_determined_no_historical_stream_envelope",
            "source_attempt_ref": "g2-baseline",
            "source_receipt_state": "consumed_non_replayable",
        },
        "historical_counts": counts,
        "remaining_rule": policy["root_cause_rule"],
    }
    observation = payload["historical_child_execution_observation"]
    observation["observation_digest"] = canonical_digest(observation)
    return {**payload, "reconciliation_digest": canonical_digest(payload)}


def validate_reconciliation(value: Mapping[str, Any], *, incident_input: Mapping[str, Any], policy: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if value.get("schema_version") != R1_RECONCILIATION_SCHEMA:
        errors.append("reconciliation_schema_invalid")
    if value.get("reconciliation_digest") != canonical_digest(without_digest(value, "reconciliation_digest")):
        errors.append("reconciliation_digest_invalid")
    if value.get("historical_terminal_digest") != incident_input.get("terminal_digest"):
        errors.append("reconciliation_terminal_binding_mismatch")
    if value.get("historical_counts") != policy.get("required_counts"):
        errors.append("reconciliation_counts_mismatch")
    observation = value.get("historical_child_execution_observation")
    if not isinstance(observation, Mapping) or observation.get("observation_digest") != canonical_digest(without_digest(observation, "observation_digest")):
        errors.append("reconciliation_observation_digest_invalid")
    if not isinstance(observation, Mapping) or observation.get("capture_status") != "not_persisted_pre_r1":
        errors.append("reconciliation_historical_capture_status_invalid")
    return tuple(sorted(errors))


def validate_repair_package(value: Mapping[str, Any], *, policy: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if value.get("schema_version") != R1_PACKAGE_SCHEMA:
        errors.append("repair_package_schema_invalid")
    if value.get("repair_package_digest") != canonical_digest(without_digest(value, "repair_package_digest")):
        errors.append("repair_package_digest_invalid")
    if value.get("scope") != policy.get("scope"):
        errors.append("repair_package_scope_invalid")
    if value.get("execution_counts") != {"operational_authority": 0, "receipt": 0, "baseline": 0, "negative_case": 0, "network": 0, "tool": 0, "model": 0, "provider": 0, "fixed_store_write": 0}:
        errors.append("repair_package_execution_counts_invalid")
    return tuple(sorted(errors))


def build_sanitization_reconciliation(
    *, incident_input: Mapping[str, Any], rejected_r1_reconciliation: Mapping[str, Any], policy: Mapping[str, Any]
) -> dict[str, Any]:
    """Supersede only the R1 sanitization contract, never historical evidence."""

    errors = validate_incident_input(incident_input, policy=policy)
    if errors:
        raise ValueError("p01_g2_1_r1_1_incident_input_invalid:" + ",".join(errors))
    if rejected_r1_reconciliation.get("reconciliation_digest") != policy.get("supersedes", {}).get("r1_reconciliation_digest"):
        raise ValueError("p01_g2_1_r1_1_rejected_reconciliation_binding_invalid")
    payload = {
        "schema_version": R1_1_RECONCILIATION_SCHEMA,
        "status": "historical_terminal_immutable_reconciled_r1_1_sanitization_pending_independent_review",
        "supersedes": {
            "r1_repair_package_digest": policy["supersedes"]["r1_repair_package_digest"],
            "r1_gate_digest": policy["supersedes"]["r1_gate_digest"],
            "r1_reconciliation_digest": policy["supersedes"]["r1_reconciliation_digest"],
            "reason": "r1_sanitization_contract_rejected_before_closeout",
        },
        "historical_terminal_digest": incident_input["terminal_digest"],
        "historical_result_digest": incident_input["baseline_result_digest"],
        "historical_ledger_sequence": incident_input["ledger_sequence"],
        "incident_link_method": "independent_immutable_reconciliation_artifact",
        "historical_capture_status": "not_persisted_pre_r1",
        "historical_counts": dict(policy["required_counts"]),
        "sanitization_contract": dict(policy["sanitization_contract"]),
        "root_cause_status": "not_determined_no_historical_stream_envelope",
    }
    return {**payload, "reconciliation_digest": canonical_digest(payload)}


def validate_sanitization_reconciliation(
    value: Mapping[str, Any], *, incident_input: Mapping[str, Any], policy: Mapping[str, Any]
) -> tuple[str, ...]:
    errors: list[str] = []
    if value.get("schema_version") != R1_1_RECONCILIATION_SCHEMA:
        errors.append("r1_1_reconciliation_schema_invalid")
    if value.get("reconciliation_digest") != canonical_digest(without_digest(value, "reconciliation_digest")):
        errors.append("r1_1_reconciliation_digest_invalid")
    if value.get("historical_terminal_digest") != incident_input.get("terminal_digest"):
        errors.append("r1_1_reconciliation_terminal_mismatch")
    supersedes = value.get("supersedes")
    if not isinstance(supersedes, Mapping) or any(supersedes.get(key) != policy["supersedes"].get(key) for key in ("r1_repair_package_digest", "r1_gate_digest", "r1_reconciliation_digest")):
        errors.append("r1_1_reconciliation_supersession_invalid")
    if value.get("historical_counts") != policy.get("required_counts"):
        errors.append("r1_1_reconciliation_counts_invalid")
    return tuple(sorted(errors))


def validate_sanitization_repair_package(value: Mapping[str, Any], *, policy: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if value.get("schema_version") != R1_1_PACKAGE_SCHEMA:
        errors.append("r1_1_repair_package_schema_invalid")
    if value.get("repair_package_digest") != canonical_digest(without_digest(value, "repair_package_digest")):
        errors.append("r1_1_repair_package_digest_invalid")
    if value.get("scope") != policy.get("scope"):
        errors.append("r1_1_repair_package_scope_invalid")
    if value.get("execution_counts") != {"operational_authority": 0, "receipt": 0, "baseline": 0, "negative_case": 0, "network": 0, "tool": 0, "model": 0, "provider": 0, "fixed_store_write": 0}:
        errors.append("r1_1_repair_package_execution_counts_invalid")
    return tuple(sorted(errors))
