"""Independent post-terminal M2-A1 oracle evaluator.

This module receives an immutable actual projection, the reviewer oracle and a
frozen scenario record.  It never imports the runner or executes compiler,
serializer, shadow, store or transport code.
"""

from __future__ import annotations

from typing import Any, Mapping

from .m2_a1_audit_result import M2A1ImmutableActualResult
from .models import StrictModel, canonical_digest


class M2A1OracleEvaluationError(ValueError):
    pass


class M2A1OracleEvaluation(StrictModel):
    scenario_id: str
    case_id: str
    actual_result_digest: str
    oracle_case_id: str
    status: str
    errors: tuple[str, ...] = ()
    checked_dimensions: tuple[str, ...] = ()
    evaluation_digest: str


_SCENARIO_COUNT_ASSERTIONS = {
    "oracle_access_canary_path_resolution_attempt_count_equals_1": ("oracle_path_resolution_attempt_count", 1),
    "oracle_access_canary_hash_attempt_count_equals_1": ("oracle_hash_attempt_count", 1),
    "store_open_attempt_count_equals_1": ("store_open_attempt_count", 1),
    "store_read_open_count_equals_0": ("store_read_open_count", 0),
    "store_write_open_count_equals_0": ("store_write_open_count", 0),
    "ambient_resolution_attempt_count_equals_1": ("ambient_resolution_attempt_count", 1),
    "provider_constructor_attempt_count_equals_1": ("provider_constructor_attempt_count", 1),
    "transport_constructor_attempt_count_equals_0": ("transport_constructor_attempt_count", 0),
    "transport_constructor_attempt_count_equals_1": ("transport_constructor_attempt_count", 1),
    "socket_connect_attempt_count_equals_1": ("socket_connect_attempt_count", 1),
    "http_connect_attempt_count_equals_1": ("http_connect_attempt_count", 1),
    "network_request_attempt_count_equals_1": ("network_request_attempt_count", 1),
    "network_request_success_count_equals_0": ("network_request_success_count", 0),
    "network_transport_constructor_attempt_count_equals_0": ("network_transport_constructor_attempt_count", 0),
    "model_constructor_attempt_count_equals_0": ("model_constructor_attempt_count", 0),
    "network_or_tool_transport_constructor_attempt_count_equals_1": ("network_transport_constructor_attempt_count", 1),
    "network_requests_equals_0": ("network_request_success_count", 0),
    "external_tool_calls_equals_0": ("tool_transport_constructor_attempt_count", 0),
}


def _mapping(value: Any, *, error: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise M2A1OracleEvaluationError(error)
    return value


def _scenario_assertions(scenario: Mapping[str, Any]) -> tuple[str, ...]:
    raw = scenario.get("actual_assertions") or ()
    if not isinstance(raw, (tuple, list)) or not all(isinstance(value, str) for value in raw):
        raise M2A1OracleEvaluationError("scenario_actual_assertions_invalid")
    return tuple(raw)


def _baseline_errors(result: M2A1ImmutableActualResult, oracle_case: Mapping[str, Any], scenario: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if result.actual_status != "succeeded":
        errors.append("baseline_actual_not_succeeded")
        return errors
    expected_selection = _mapping(oracle_case.get("expected_selection"), error="oracle_expected_selection_missing")
    selected = set(result.pack_lineage.selected_pack_version_ids)
    required_packs = set(expected_selection.get("required_pack_version_ids") or ())
    forbidden_packs = set(expected_selection.get("forbidden_pack_version_ids") or ())
    if not required_packs.issubset(selected):
        errors.append("required_pack_version_missing")
    if forbidden_packs & selected:
        errors.append("forbidden_pack_version_selected")
    if not result.pack_lineage.selection_digest or not result.pack_lineage.resolution_digest or not result.pack_lineage.registry_snapshot_digest:
        errors.append("pack_lineage_incomplete")
    actual_cells = {cell.cell_key: cell for cell in result.cells}
    required_cells = oracle_case.get("required_cells") or ()
    for expected in required_cells:
        expected_cell = _mapping(expected, error="oracle_required_cell_invalid")
        cell_key = str(expected_cell.get("cell_key") or "")
        actual = actual_cells.get(cell_key)
        if actual is None:
            errors.append(f"required_cell_missing:{cell_key}")
            continue
        if actual.owner_role != expected_cell.get("owner_role"):
            errors.append(f"cell_owner_mismatch:{cell_key}")
        if not set(expected_cell.get("required_evidence_roles") or ()).issubset(set(actual.evidence_roles)):
            errors.append(f"cell_required_evidence_role_missing:{cell_key}")
        if set(expected_cell.get("forbidden_evidence_roles") or ()) & set(actual.evidence_roles):
            errors.append(f"cell_forbidden_evidence_role_present:{cell_key}")
    forbidden_cells = set(oracle_case.get("forbidden_cells") or ())
    if forbidden_cells & set(actual_cells):
        errors.append("forbidden_cell_present")
    range_spec = _mapping(oracle_case.get("cell_count_range"), error="oracle_cell_count_range_missing")
    if not int(range_spec["minimum"]) <= len(result.cells) <= int(range_spec["maximum"]):
        errors.append("cell_count_out_of_range")
    semantic_by_id = {row.legacy_required_item_id: row for row in result.semantic_loss}
    for expected in oracle_case.get("legacy_semantic_loss_expectations") or ():
        expectation = _mapping(expected, error="oracle_semantic_loss_expectation_invalid")
        item_id = str(expectation.get("legacy_required_item_id") or "")
        actual = semantic_by_id.get(item_id)
        if actual is None:
            errors.append(f"semantic_loss_missing:{item_id}")
            continue
        if actual.action not in set(expectation.get("allowed_actions") or ()):
            errors.append(f"semantic_loss_action_mismatch:{item_id}")
        if not set(expectation.get("required_information_loss_tags") or ()).issubset(set(actual.information_loss_tags)):
            errors.append(f"semantic_loss_tag_missing:{item_id}")
    if set(oracle_case.get("must_not_assert") or ()) & set(result.asserted_claims):
        errors.append("forbidden_assertion_present")
    if str(scenario.get("scenario_id") or "").startswith("p02-"):
        if not result.artifact_replay.envelope_digest or not result.artifact_replay.replay_digest:
            errors.append("artifact_envelope_or_replay_digest_missing")
    return errors


def _negative_errors(result: M2A1ImmutableActualResult, scenario: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_stop = str(scenario.get("expected_typed_stop") or "")
    if result.actual_status != "typed_stop":
        errors.append("negative_actual_not_typed_stop")
    if result.typed_stop != expected_stop:
        errors.append("typed_stop_mismatch")
    counts = _mapping(result.canary_snapshot.get("counts"), error="actual_canary_counts_missing")
    for assertion in _scenario_assertions(scenario):
        expected = _SCENARIO_COUNT_ASSERTIONS.get(assertion)
        if expected is None:
            continue
        key, value = expected
        if int(counts.get(key, -1)) != value:
            errors.append(f"canary_count_mismatch:{key}")
    if str(scenario.get("scenario_id") or "").startswith("p03-"):
        for key in ("store_open_success_count", "store_read_open_count", "store_write_open_count", "network_request_success_count"):
            if int(counts.get(key, 0)) != 0:
                errors.append(f"blocked_p03_success_count_nonzero:{key}")
    return errors


def evaluate_independent_oracle(
    immutable_actual: M2A1ImmutableActualResult,
    oracle_case: Mapping[str, Any],
    scenario: Mapping[str, Any],
) -> M2A1OracleEvaluation:
    """Score a digest-verified terminal result against exact scenario semantics."""

    if not immutable_actual.verify_immutable_digest():
        raise M2A1OracleEvaluationError("immutable_actual_result_digest_invalid")
    oracle = _mapping(oracle_case, error="oracle_case_invalid")
    frozen_scenario = _mapping(scenario, error="scenario_invalid")
    scenario_id = str(frozen_scenario.get("scenario_id") or "")
    if scenario_id != immutable_actual.scenario_id:
        raise M2A1OracleEvaluationError("scenario_actual_mismatch")
    if str(oracle.get("input_case_ref") or "") != immutable_actual.case_id:
        raise M2A1OracleEvaluationError("oracle_actual_case_mismatch")
    expected_stop = str(frozen_scenario.get("expected_typed_stop") or "none")
    if expected_stop == "none":
        errors = _baseline_errors(immutable_actual, oracle, frozen_scenario)
        status = "pass" if not errors else "mismatch"
        dimensions = ("pack", "cells", "owner", "evidence", "semantic_loss", "must_not_assert", "lineage_replay")
    else:
        errors = _negative_errors(immutable_actual, frozen_scenario)
        status = "exact_expected_typed_stop_match" if not errors else "mismatch"
        dimensions = ("typed_stop", "scenario_canary", "blocked_success_counts")
    payload = {
        "scenario_id": scenario_id,
        "case_id": immutable_actual.case_id,
        "actual_result_digest": immutable_actual.actual_result_digest,
        "oracle_case_id": str(oracle.get("oracle_case_id") or ""),
        "status": status,
        "errors": tuple(sorted(set(errors))),
        "checked_dimensions": dimensions,
    }
    return M2A1OracleEvaluation(**payload, evaluation_digest=canonical_digest(payload))
