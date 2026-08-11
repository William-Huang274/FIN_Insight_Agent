"""Static regressions for the P01-G2.0 operational-tranche freeze only."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.p01_g2_operational_tranche import (
    P01_G2_TRANCHE_GATE_SCHEMA,
    P01_G2_TRANCHE_SCHEMA,
    tranche_payload,
    validate_p01_g2_operational_tranche,
)


ROOT = Path(__file__).resolve().parents[2]
TRANCHE_PATH = ROOT / "data/manifests/point01_p01_g2_operational_tranche_manifest_v1_0.json"
GATE_PATH = ROOT / "data/manifests/point01_p01_g2_operational_tranche_gate_v1_0.json"
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


def _family() -> dict[str, dict[str, object]]:
    return {name: _mapping(path) for name, path in FAMILY_PATHS.items()}


def _validate(tranche: dict[str, object]) -> dict[str, object]:
    family = _family()
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


def test_p01_g2_exact_tranche_and_gate_are_freeze_only_pass() -> None:
    tranche, gate = _mapping(TRANCHE_PATH), _mapping(GATE_PATH)
    assert tranche["schema_version"] == P01_G2_TRANCHE_SCHEMA
    assert gate["schema_version"] == P01_G2_TRANCHE_GATE_SCHEMA
    assert _validate(tranche)["status"] == "pass"
    assert gate["status"] == "pass"
    assert gate["tranche_digest"] == tranche["tranche_digest"]
    assert tranche["freeze_execution_counts"] == gate["execution_counts"]
    assert all(value == 0 for value in gate["execution_counts"].values())


def test_p01_g2_selects_four_cases_and_defers_exactly_twelve_named_regressions() -> None:
    tranche = _mapping(TRANCHE_PATH)
    selected = tranche["selected_cases"]
    deferred = tranche["deferred_operational_regression_backlog"]
    assert [item["case_id"] for item in selected] == ["g2-baseline", "g2-wrong-package-or-approval", "g2-stale-input-version-drift", "g2-unauthorized-transport"]
    assert len(deferred) == 12 and len({item["scenario_id"] for item in deferred}) == 12
    assert selected[0]["expected_terminal"] == "succeeded"
    assert selected[1]["valid_authority_must_not_issue"] is True
    assert selected[2]["expected_terminal"] == "typed_stop:superseded_pack_version_or_pack_not_fresh"
    assert selected[3]["expected_post_counts"]["network_success"] == selected[3]["expected_post_counts"]["tool_success"] == 0


def test_p01_g2_rejects_v2_10_family_drift_even_when_tranche_is_redigested() -> None:
    tranche = copy.deepcopy(_mapping(TRANCHE_PATH))
    tranche["v2_10_family"]["package_digest"] = "a" * 64
    result = _validate(_redigest(tranche))
    assert result["status"] == "fail_closed"
    assert "v2_10_family_binding_invalid" in result["errors"]


def test_p01_g2_rejects_staged_input_and_backlog_drift() -> None:
    tranche = copy.deepcopy(_mapping(TRANCHE_PATH))
    tranche["v2_10_staged_input_binding"]["input_hash_count"] = 78
    tranche["deferred_operational_regression_backlog"] = tranche["deferred_operational_regression_backlog"][:-1]
    result = _validate(_redigest(tranche))
    assert result["status"] == "fail_closed"
    assert {"v2_10_staged_input_binding_invalid", "deferred_backlog_invalid"}.issubset(set(result["errors"]))


def test_p01_g2_rejects_active_reviewer_receipt_shape_and_any_freeze_execution_count() -> None:
    tranche = copy.deepcopy(_mapping(TRANCHE_PATH))
    tranche["proposed_reviewer_decision_receipt"]["receipt_digest"] = "b" * 64
    tranche["freeze_execution_counts"]["receipt"] = 1
    result = _validate(_redigest(tranche))
    assert result["status"] == "fail_closed"
    assert {"reviewer_receipt_template_invalid", "freeze_execution_counts_nonzero"}.issubset(set(result["errors"]))
