from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.releases.materialize_fin_ia_0_1_2_s4_t06_workbench_current_product_projection_entry_and_dependency_decision import (  # noqa: E402
    DEFAULT_OUTPUT,
    S4T06WorkbenchEntryDecisionError,
    materialize,
    validate_entry_decision,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


def _load() -> dict:
    return json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))


def _redigest(value: dict) -> dict:
    value["decision_digest"] = canonical_digest(
        {key: row for key, row in value.items() if key != "decision_digest"}
    )
    return value


def test_entry_inventory_binds_three_current_owner_accepted_cases() -> None:
    decision = materialize()
    assert decision == _load()
    assert [row["ticker"] for row in decision["current_three_case_assets"]] == [
        "DELL",
        "MU",
        "NVDA",
    ]
    assert all(row["R2"] is True for row in decision["current_three_case_assets"])
    assert all(
        row["evidence_numeric_typed_gap"] == [15, 3, 3]
        for row in decision["current_three_case_assets"]
    )
    assert all(
        row["provider_capture_artifact"] == [9, 9, 9]
        for row in decision["current_three_case_assets"]
    )


def test_entry_records_real_workbench_binding_blocker_and_bounded_sequence() -> None:
    decision = _load()
    assert decision["earliest_owned_blocker"]["issue"] == "RC-P36-126"
    assert decision["earliest_owned_blocker"]["model_or_provider_fault"] is False
    assert [row["task"] for row in decision["bounded_T06_sequence"]] == [
        "T06-A",
        "T06-B",
        "T06-C",
    ]
    assert decision["bounded_T06_sequence"][0]["status"] == (
        "authorized_next_not_started"
    )
    assert decision["acceptance_boundary"]["S4_T06_entry"] == "pass"
    assert decision["acceptance_boundary"]["S4_T06_engineering"] == "not_started"
    regression = decision["historical_workbench_regression_audit"]
    assert regression["issue"] == "RC-P36-127"
    assert regression["observed_selected_regression"] == {
        "total": 54,
        "passed": 44,
        "failed": 10,
        "common_failure": "exactly_one_pending_evidence_fixture_work_unit_required",
    }
    assert regression["root_cause_proof"]["default_create_app_evidence_compile_status"] == 409
    assert regression["root_cause_proof"]["explicit_no_runtime_evidence_compile_status"] == 202
    assert regression["T05_current_asset_failure"] is False


def test_graph_absence_is_typed_empty_and_not_fabricated() -> None:
    decision = _load()
    assert decision["observed_counts"]["approved_graph_evidence"] == 0
    assert all(
        row["graph_product_state"]
        == "typed_empty_no_approved_current_graph_evidence"
        for row in decision["current_three_case_assets"]
    )
    assert "invent Graph edges when approved graph evidence is absent" in (
        decision["scope_disposition"]["not_allowed"]
    )


def test_entry_cannot_claim_implementation_or_T06_product_pass() -> None:
    changed = deepcopy(_load())
    changed["authority"]["implementation_authorized"] = True
    changed["acceptance_boundary"]["S4_T06_engineering"] = "pass"
    changed["acceptance_boundary"]["S4_T06_product_projection"] = "pass"
    _redigest(changed)
    with pytest.raises(
        S4T06WorkbenchEntryDecisionError,
        match="s4_t06_entry_authority_or_blocker_invalid|s4_t06_entry_sequence_or_boundary_invalid",
    ):
        validate_entry_decision(changed)


def test_current_asset_inventory_mutation_fails_closed() -> None:
    changed = deepcopy(_load())
    changed["observed_counts"]["evidence_rows"] = 44
    _redigest(changed)
    with pytest.raises(
        S4T06WorkbenchEntryDecisionError,
        match="s4_t06_entry_current_asset_inventory_invalid",
    ):
        validate_entry_decision(changed)


def test_zero_call_or_decision_digest_mutation_fails_closed() -> None:
    changed = deepcopy(_load())
    changed["observed_counts"]["new_model_calls"] = 1
    _redigest(changed)
    with pytest.raises(
        S4T06WorkbenchEntryDecisionError,
        match="s4_t06_entry_zero_call_boundary_invalid",
    ):
        validate_entry_decision(changed)

    changed = deepcopy(_load())
    changed["recommended_next"] = "mutated"
    with pytest.raises(
        S4T06WorkbenchEntryDecisionError,
        match="s4_t06_entry_decision_digest_mismatch",
    ):
        validate_entry_decision(changed)
