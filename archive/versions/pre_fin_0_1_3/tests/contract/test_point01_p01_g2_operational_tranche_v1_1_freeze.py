"""Static regressions for repaired P01-G2.0 authority and coverage freeze."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.p01_g2_operational_tranche_v1_1 import (
    P01_G2_TRANCHE_GATE_SCHEMA,
    P01_G2_TRANCHE_SCHEMA,
    tranche_payload,
    validate_p01_g2_operational_tranche,
)


ROOT = Path(__file__).resolve().parents[2]
TRANCHE_PATH = ROOT / "data/manifests/point01_p01_g2_operational_tranche_manifest_v1_1.json"
GATE_PATH = ROOT / "data/manifests/point01_p01_g2_operational_tranche_gate_v1_1.json"
MATRIX_PATH = ROOT / "configs/engineering_handoff/point01_m2_a1_execution_ready_scenario_matrix_v2_1.json"
FAMILY_PATHS = {
    "package": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_10.json",
    "package_gate": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_10.json",
    "plan": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof.json",
    "plan_gate": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof_gate.json",
    "blueprint": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof.json",
    "blueprint_gate": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof_gate.json",
}


def _mapping(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(tranche: dict[str, object]) -> dict[str, object]:
    family = {name: _mapping(path) for name, path in FAMILY_PATHS.items()}
    return validate_p01_g2_operational_tranche(
        tranche,
        source_matrix=_mapping(MATRIX_PATH),
        v2_10_package=family["package"],
        v2_10_package_gate=family["package_gate"],
        v2_10_plan=family["plan"],
        v2_10_plan_gate=family["plan_gate"],
        v2_10_blueprint=family["blueprint"],
        v2_10_blueprint_gate=family["blueprint_gate"],
    )


def _redigest(tranche: dict[str, object]) -> dict[str, object]:
    tranche["tranche_digest"] = canonical_digest(tranche_payload(tranche))
    return tranche


def test_p01_g2_v1_1_exact_tranche_and_gate_are_freeze_only_pass() -> None:
    tranche, gate = _mapping(TRANCHE_PATH), _mapping(GATE_PATH)
    assert tranche["schema_version"] == P01_G2_TRANCHE_SCHEMA
    assert gate["schema_version"] == P01_G2_TRANCHE_GATE_SCHEMA
    assert _validate(tranche)["status"] == "pass"
    assert gate["status"] == "pass"
    assert gate["tranche_digest"] == tranche["tranche_digest"]
    assert all(value == 0 for value in gate["execution_counts"].values())


def test_p01_g2_v1_1_reconciles_three_original_selected_thirteen_deferred_and_one_supplemental() -> None:
    tranche = _mapping(TRANCHE_PATH)
    coverage = tranche["original_matrix_coverage"]
    assert coverage["selected_original_source_matrix_ids"] == [
        "p01-baseline-separated-input",
        "p02-stale-or-superseded-pack",
        "p03-network-tool-transport",
    ]
    assert len(coverage["deferred_original_source_matrix_ids"]) == 13
    assert "p01-oracle-path-access" in coverage["deferred_original_source_matrix_ids"]
    assert coverage["supplemental_case_ids"] == ["g2-wrong-package-or-approval"]
    supplemental = next(case for case in tranche["selected_cases"] if case["case_id"] == "g2-wrong-package-or-approval")
    assert supplemental["source_matrix_scenario_id"] is None
    assert supplemental["coverage_class"] == "supplemental_pre_authority_probe"


def test_p01_g2_v1_1_rejects_any_negative_authority_receipt_namespace_or_runtime_count() -> None:
    tranche = copy.deepcopy(_mapping(TRANCHE_PATH))
    stale = next(case for case in tranche["selected_cases"] if case["case_id"] == "g2-stale-input-version-drift")
    stale["expected_post_counts"]["valid_authority_issue_count"] = 1
    stale["expected_post_counts"]["formal_namespace_count"] = 1
    result = _validate(_redigest(tranche))
    assert result["status"] == "fail_closed"
    assert "negative_case_authority_or_runtime_invalid" in result["errors"]


def test_p01_g2_v1_1_rejects_oracle_path_backlog_omission() -> None:
    tranche = copy.deepcopy(_mapping(TRANCHE_PATH))
    tranche["deferred_original_regression_backlog"] = [
        item for item in tranche["deferred_original_regression_backlog"]
        if item["scenario_id"] != "p01-oracle-path-access"
    ]
    tranche["original_matrix_coverage"]["deferred_original_source_matrix_ids"] = [
        item for item in tranche["original_matrix_coverage"]["deferred_original_source_matrix_ids"]
        if item != "p01-oracle-path-access"
    ]
    result = _validate(_redigest(tranche))
    assert result["status"] == "fail_closed"
    assert "original_matrix_coverage_invalid" in result["errors"]


def test_p01_g2_v1_1_rejects_supplemental_case_impersonating_original_matrix_id() -> None:
    tranche = copy.deepcopy(_mapping(TRANCHE_PATH))
    supplemental = next(case for case in tranche["selected_cases"] if case["case_id"] == "g2-wrong-package-or-approval")
    supplemental["source_matrix_scenario_id"] = "p01-oracle-path-access"
    result = _validate(_redigest(tranche))
    assert result["status"] == "fail_closed"
    assert "supplemental_case_contract_invalid" in result["errors"]


def test_p01_g2_v1_1_rejects_v2_10_family_drift_even_when_redigested() -> None:
    tranche = copy.deepcopy(_mapping(TRANCHE_PATH))
    tranche["v2_10_family"]["package_digest"] = "a" * 64
    result = _validate(_redigest(tranche))
    assert result["status"] == "fail_closed"
    assert "v2_10_family_binding_invalid" in result["errors"]


def test_p01_g2_v1_1_rejects_active_baseline_receipt_shape_or_freeze_counter() -> None:
    tranche = copy.deepcopy(_mapping(TRANCHE_PATH))
    tranche["proposed_baseline_reviewer_decision_receipt"]["receipt_digest"] = "b" * 64
    tranche["freeze_execution_counts"]["receipt"] = 1
    result = _validate(_redigest(tranche))
    assert result["status"] == "fail_closed"
    assert {"reviewer_receipt_template_invalid", "freeze_execution_counts_nonzero"}.issubset(set(result["errors"]))
