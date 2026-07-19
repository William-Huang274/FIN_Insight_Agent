"""No-I/O unit coverage for M2-A1 canary, evaluator, receipt and reviewer seams."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.m2_a1_audit_canary import (
    M2A1AuditCanary,
    M2A1ModelAdmissionError,
    M2A1OracleLeakageError,
    M2A1StoreAccessError,
    M2A1TransportAccessError,
)
from sec_agent.canonical_runtime.m2_a1_audit_oracle import evaluate_independent_oracle
from sec_agent.canonical_runtime.m2_a1_audit_result import (
    M2A1ActualCellProjection,
    M2A1ActualDigestReference,
    M2A1ArtifactReplayProjection,
    M2A1ImmutableActualResult,
    M2A1PackLineageProjection,
    M2A1SemanticLossProjection,
)
from sec_agent.canonical_runtime.m2_a1_audit_reviewer_gate import review_future_actual
from sec_agent.canonical_runtime.m2_a1_execution_receipt import validate_unconsumed_receipt


ROOT = Path(__file__).resolve().parents[2]
ORACLE = ROOT / "configs/engineering_handoff/point01_m2_a1_independent_expected_cell_oracle_v1_1.json"


def _oracle_case(case_id: str = "m2-a1-ai-semis-input") -> dict:
    raw = json.loads(ORACLE.read_text(encoding="utf-8"))
    return next(copy.deepcopy(case) for case in raw["oracle_cases"] if case["input_case_ref"] == case_id)


def test_canaries_fail_before_any_real_store_or_transport_open(tmp_path: Path) -> None:
    canary = M2A1AuditCanary(allowed_temporary_roots=(tmp_path,), fixed_paths=(tmp_path / ".runtime_control" / "canonical.sqlite",))
    with pytest.raises(M2A1OracleLeakageError, match="oracle_leakage_detected"):
        canary.reject_oracle_hash()
    with pytest.raises(M2A1StoreAccessError, match="test_runtime_isolation_violation"):
        canary.reject_store_open(tmp_path / ".runtime_control" / "canonical.sqlite", write=False)
    with pytest.raises(M2A1StoreAccessError, match="test_runtime_isolation_violation"):
        canary.reject_ambient_store_resolution()
    with pytest.raises(M2A1TransportAccessError, match="shadow_scope_violation"):
        canary.reject_transport_constructor(kind="network")
    with pytest.raises(M2A1ModelAdmissionError, match="model_adapter_shadow_run_not_admitted"):
        canary.reject_model_constructor(feature_flag_enabled=False, admission_present=False)
    counts = canary.snapshot()["counts"]
    assert counts["oracle_hash_attempt_count"] == counts["store_open_attempt_count"] == counts["ambient_resolution_attempt_count"] == 1
    assert counts["network_transport_constructor_attempt_count"] == counts["model_constructor_attempt_count"] == 1
    assert counts["store_read_open_count"] == counts["store_write_open_count"] == 0


def test_independent_oracle_reads_only_immutable_terminal_projection() -> None:
    oracle_case = _oracle_case()
    result = M2A1ImmutableActualResult.terminalize(
        execution_scope="harness_unit_fixture_not_actual_probe",
        scenario_id="p01-baseline-separated-input",
        case_id="m2-a1-ai-semis-input",
        executable_package_digest="a" * 64,
        admission_digest="b" * 64,
        consumed_receipt_digest="c" * 64,
        actual_status="succeeded",
        pack_lineage=M2A1PackLineageProjection(
            selection_digest="selection-v1",
            resolution_digest="resolution-v1",
            registry_snapshot_digest="registry-v1",
            selected_pack_version_ids=("pack-universal-research:v1", "pack-sector-ai-semis:v3", "pack-report-initiation:v2"),
        ),
        cells=(
            M2A1ActualCellProjection(cell_key="ai-demand", owner_role="fundamental_analyst", evidence_roles=("issuer_metric",), forbidden_substitutions=(), acceptance_roles=()),
            M2A1ActualCellProjection(cell_key="ai-supply", owner_role="product_industry_analyst", evidence_roles=("issuer_metric", "relationship_signal"), forbidden_substitutions=(), acceptance_roles=()),
            M2A1ActualCellProjection(cell_key="ai-margin", owner_role="fundamental_analyst", evidence_roles=("issuer_metric",), forbidden_substitutions=(), acceptance_roles=()),
            M2A1ActualCellProjection(cell_key="ai-counterevidence", owner_role="risk_counterevidence_analyst", evidence_roles=("issuer_metric",), forbidden_substitutions=(), acceptance_roles=()),
            *tuple(M2A1ActualCellProjection(cell_key=f"ai-fixture-{index}", owner_role="fundamental_analyst", evidence_roles=("issuer_metric",), forbidden_substitutions=(), acceptance_roles=()) for index in range(1, 7)),
        ),
        semantic_loss=(
            M2A1SemanticLossProjection(legacy_required_item_id="ai-hbm", action="downgrade", target_cell_keys=("ai-supply",), information_loss_tags=("relationship_context_not_exact_issuer_fact",)),
            M2A1SemanticLossProjection(legacy_required_item_id="ai-counterevidence", action="split", target_cell_keys=("ai-counterevidence",), information_loss_tags=("counterevidence_route_preserved",)),
        ),
        artifact_replay=M2A1ArtifactReplayProjection(envelope_digest="envelope-v1", replay_digest="replay-v1", artifact_version_id="artifact-v1"),
        canary_snapshot={"counts": {}, "events": []},
    )
    scenario = {"scenario_id": "p01-baseline-separated-input", "expected_typed_stop": "none", "actual_assertions": []}
    evaluation = evaluate_independent_oracle(result, oracle_case, scenario)
    assert evaluation.status == "pass"
    before = result.actual_result_digest
    mutated_oracle = copy.deepcopy(oracle_case)
    mutated_oracle["forbidden_cells"].append("ai-demand")
    mutated = evaluate_independent_oracle(result, mutated_oracle, scenario)
    assert mutated.status == "mismatch"
    assert result.actual_result_digest == before
    assert M2A1ActualDigestReference.from_result(result).actual_result_digest == before


def test_receipt_and_reviewer_gate_fail_closed_before_actual_admission(tmp_path: Path) -> None:
    package = {"package_ref": "m2-a1-package", "package_digest": "b" * 64, "scope": "M2_A1_actual_only", "authority_boundary": "synthetic-unit-only", "execution_mode": "external_admission_gated"}
    assert validate_unconsumed_receipt(None, package_ref=package["package_ref"], executable_package_digest=package["package_digest"], scope=package["scope"], actual_probes_authorized=False)["status"] == "actual_execution_not_authorized"
    canary = M2A1AuditCanary(allowed_temporary_roots=(tmp_path,))
    gate = review_future_actual(
        package=package,
        actual_results=(),
        oracle_evaluations=(),
        expected_scenario_ids=(),
        admission=None,
        consumed_receipt=None,
        receipt_ledger_state=None,
        receipt_terminal_event_digest=None,
    )
    assert gate.status == "fail_closed"
    assert "package_admission_required" in gate.errors
    assert "consumed_receipt_missing" in gate.errors
