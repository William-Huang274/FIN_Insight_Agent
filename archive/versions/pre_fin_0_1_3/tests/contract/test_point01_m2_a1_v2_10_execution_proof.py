"""B0.7 regressions: resolved provenance and one shared v2.10 lifecycle graph."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.m2_a1_execution_receipt import (
    M2A1ExecutionPreflightError,
    M2A1ReceiptAuthorityError,
    M2A1ReceiptLedger,
    ProductionHumanJITWindowApprovalV2_10,
    ProductionReviewerDecisionReceiptV2_10,
    SyntheticNonhumanAuthorityV2_10,
    ValidatedAuthorityContext,
    event_append_only_trigger_ddl_digest,
    preflight_exact_execution,
    validate_production_human_jit_window_approval_v2_10,
)
from sec_agent.canonical_runtime.m2_a1_v2_10_execution_proof import execute_synthetic_nonhuman_v2_10_fixture
from sec_agent.canonical_runtime.models import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_v2_10.py"
ENTRY = ROOT / "scripts/engineering/run_point01_m2_a1_v2_10_frozen_jit_window.py"
PACKAGE_PATH = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_10.json"
PACKAGE_GATE_PATH = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_10.json"
PLAN_PATH = ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof.json"
PLAN_GATE_PATH = ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof_gate.json"
BLUEPRINT_PATH = ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof.json"
BLUEPRINT_GATE_PATH = ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof_gate.json"
PACKAGE_DIGEST = "f" * 64


def _mapping(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _artifacts() -> tuple[dict[str, object], ...]:
    return tuple(_mapping(path) for path in (PACKAGE_PATH, PACKAGE_GATE_PATH, PLAN_PATH, PLAN_GATE_PATH, BLUEPRINT_PATH, BLUEPRINT_GATE_PATH))


def _valid_review_receipt_and_approval() -> tuple[ProductionReviewerDecisionReceiptV2_10, ProductionHumanJITWindowApprovalV2_10, tuple[dict[str, object], ...]]:
    package, package_gate, plan, plan_gate, blueprint, blueprint_gate = _artifacts()
    now = datetime.now(timezone.utc)
    binding = blueprint["exact_binding"]
    receipt = ProductionReviewerDecisionReceiptV2_10.create(
        receipt_id="point01-m2-a1-v2-10-total-reviewer-decision-test-fixture",
        receipt_version=1,
        actor_id="003",
        reviewer_identity="william/003/total_reviewer",
        decision="approved_single_jit_window",
        decision_source="total_reviewer_recorded_decision",
        package_ref=package["package_ref"], package_digest=package["package_digest"], package_gate_digest=package_gate["gate_digest"],
        plan_digest=plan["plan_digest"], plan_gate_digest=plan_gate["gate_digest"], blueprint_digest=blueprint["blueprint_digest"], blueprint_gate_digest=blueprint_gate["gate_digest"],
        scenario_id=binding["scenario_id"], scope=package["scope"], authority_boundary=package["authority_boundary"], execution_staging_namespace_id=binding["execution_staging_namespace_id"],
        issued_at=now - timedelta(minutes=1), expires_at=now + timedelta(minutes=20),
    )
    approval = ProductionHumanJITWindowApprovalV2_10.create(
        approval_ref="point01-m2-a1-total-reviewer-jit-window-approval",
        approval_id="point01-m2-a1-v2-10-test-jit-approval",
        approval_version=1,
        reviewer_identity="william/003/total_reviewer",
        decision="approved_single_jit_window",
        actor_id="003",
        review_receipt_id=receipt.receipt_id,
        review_receipt_digest=receipt.receipt_digest,
        issued_at=now,
        expires_at=now + timedelta(minutes=15),
        package_ref=package["package_ref"], package_digest=package["package_digest"], package_gate_digest=package_gate["gate_digest"],
        plan_digest=plan["plan_digest"], plan_gate_digest=plan_gate["gate_digest"], blueprint_digest=blueprint["blueprint_digest"], blueprint_gate_digest=blueprint_gate["gate_digest"],
        phase_a_digests=package["phase_a_digests"], incident_digest=package["incident_evidence"]["incident_digest"], expired_terminal_digest=package["incident_evidence"]["expired_terminal_digest"],
        scenario_id=binding["scenario_id"], input_ref=binding["input_ref"], mutation=binding["mutation"], authority_boundary=package["authority_boundary"], execution_staging_namespace_id=binding["execution_staging_namespace_id"],
        admission_ttl_minutes=30, receipt_ttl_minutes=15, single_use=True, no_retry_replay_or_renewal=True,
    )
    return receipt, approval, (package, package_gate, plan, plan_gate, blueprint, blueprint_gate)


def test_v2_10_synthetic_authority_is_a_different_schema_and_cannot_be_production_context() -> None:
    fixture = SyntheticNonhumanAuthorityV2_10.create(package_digest=PACKAGE_DIGEST, scenario_id="p01-synthetic-v2-10-execution-proof")
    assert fixture.authority_class == "synthetic_nonhuman_fixture" and fixture.verify_digest()
    with pytest.raises(M2A1ReceiptAuthorityError, match="production_validated_human_authority_required"):
        ValidatedAuthorityContext("synthetic_nonhuman_fixture", fixture.fixture_digest, "synthetic/nonhuman-fixture", fixture.scenario_id, fixture.fixture_id, False).require_production()


def test_v2_10_production_model_rejects_test_ref_before_receipt_resolution() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="test_or_synthetic_approval_ref_forbidden"):
        ProductionHumanJITWindowApprovalV2_10.create(approval_ref="test_only_external_authority_fixture", approval_id="test", approval_version=1, reviewer_identity="william/003/total_reviewer", decision="approved_single_jit_window", actor_id="003", review_receipt_id="review", review_receipt_digest="a" * 64, issued_at=now, expires_at=now + timedelta(minutes=5), package_ref="package", package_digest="b" * 64, package_gate_digest="c" * 64, plan_digest="d" * 64, plan_gate_digest="e" * 64, blueprint_digest="f" * 64, blueprint_gate_digest="1" * 64, phase_a_digests={"classification": "2" * 64}, incident_digest="3" * 64, expired_terminal_digest="4" * 64, scenario_id="p01-baseline-separated-input", input_ref="m2-a1-ai-semis-input", mutation="none", authority_boundary="boundary", execution_staging_namespace_id="namespace", admission_ttl_minutes=30, receipt_ttl_minutes=15, single_use=True, no_retry_replay_or_renewal=True)


def test_v2_10_reviewer_receipt_resolution_rejects_missing_drift_actor_and_package() -> None:
    receipt, approval, artifacts = _valid_review_receipt_and_approval()
    package, package_gate, plan, plan_gate, blueprint, blueprint_gate = artifacts
    no_context, no_check = validate_production_human_jit_window_approval_v2_10(approval, reviewer_receipt=None, package=package, package_gate=package_gate, plan=plan, plan_gate=plan_gate, blueprint=blueprint, blueprint_gate=blueprint_gate)
    assert no_context is None and "approval_reviewer_decision_receipt_required" in no_check["errors"]
    for mutated in (receipt.model_copy(update={"receipt_digest": "a" * 64}), receipt.model_copy(update={"actor_id": "wrong"}), receipt.model_copy(update={"package_digest": "b" * 64})):
        context, check = validate_production_human_jit_window_approval_v2_10(approval, reviewer_receipt=mutated, package=package, package_gate=package_gate, plan=plan, plan_gate=plan_gate, blueprint=blueprint, blueprint_gate=blueprint_gate)
        assert context is None and check["status"] == "production_human_jit_window_approval_binding_mismatch"


def test_v2_10_resolved_reviewer_receipt_constructs_only_production_context() -> None:
    receipt, approval, artifacts = _valid_review_receipt_and_approval()
    package, package_gate, plan, plan_gate, blueprint, blueprint_gate = artifacts
    context, check = validate_production_human_jit_window_approval_v2_10(approval, reviewer_receipt=receipt, package=package, package_gate=package_gate, plan=plan, plan_gate=plan_gate, blueprint=blueprint, blueprint_gate=blueprint_gate)
    assert check["status"] == "pass" and context is not None and context.production is True


def test_v2_10_historical_package_preflight_fails_closed_after_r1_runtime_repair(tmp_path: Path) -> None:
    receipt, approval, _artifacts_value = _valid_review_receipt_and_approval()
    approval_path, receipt_path = tmp_path / "approval.json", tmp_path / "reviewer-decision-receipt.json"
    approval_path.write_text(json.dumps(approval.model_dump(mode="json")), encoding="utf-8")
    receipt_path.write_text(json.dumps(receipt.model_dump(mode="json")), encoding="utf-8")
    result = subprocess.run([sys.executable, str(ENTRY), "--dry-run-approved-window", "--approval", str(approval_path), "--reviewer-decision-receipt", str(receipt_path)], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "m2_a1_v2_10_approval_preflight_fail_closed"
    assert payload["new_admission"] == payload["new_receipt"] == payload["namespace"] == 0


def test_v2_10_production_cli_rejects_synthetic_json_before_any_artifact_or_path(tmp_path: Path) -> None:
    fixture = SyntheticNonhumanAuthorityV2_10.create(package_digest=PACKAGE_DIGEST, scenario_id="p01-synthetic-v2-10-execution-proof")
    approval = tmp_path / "synthetic-authority.json"
    approval.write_text(json.dumps(fixture.model_dump(mode="json")), encoding="utf-8")
    result = subprocess.run([sys.executable, str(ENTRY), "--dry-run-approved-window", "--approval", str(approval), "--reviewer-decision-receipt", str(tmp_path / "not-read.json")], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 2 and "fail_closed" in result.stdout


def _assert_outcome_unknown(result: object) -> None:
    assert getattr(result, "state") == "outcome_unknown"
    ledger_path, receipt, admission, grant = (getattr(result, item) for item in ("ledger_path", "receipt", "admission", "grant"))
    ledger = M2A1ReceiptLedger.open_existing(ledger_path, approved_authority_root=ledger_path.parent)
    terminal = ledger.verify_terminal_event(receipt.receipt_id, expected_human_approval_digest=receipt.human_approval_digest)
    assert terminal["terminal_status"] == "outcome_unknown"
    with pytest.raises(M2A1ReceiptAuthorityError):
        ledger.consume_before_run(receipt.receipt_id, admission=admission, package_ref=admission.package_ref, executable_package_digest=PACKAGE_DIGEST, scope=admission.scope, authority_boundary=admission.authority_boundary, preflight_digest=grant.preflight_digest, run_root=ledger_path.parent.parent, execution_staging_namespace_id=admission.execution_staging_namespace_id, scenario_id=receipt.scenario_id, expected_admission_schema_version="finsight_point01_m2_a1_external_package_admission_v2_10", expected_receipt_schema_version="finsight_point01_m2_a1_single_use_execution_receipt_v2_10", expected_human_approval_digest=receipt.human_approval_digest)


def test_v2_10_shared_kernel_happy_path_uses_parent_clean_child_and_writes_preterminal_artifacts(tmp_path: Path) -> None:
    result = execute_synthetic_nonhuman_v2_10_fixture(temporary_root=tmp_path, parent=PARENT, package_digest=PACKAGE_DIGEST)
    assert result.state == "succeeded" and result.actual and result.oracle and result.reviewer
    assert {"REGISTERED", "CONSUMED_BEFORE_RUN", "parent_clean_child_leaf_completed", "actual_validated", "oracle_artifact_verified", "reviewer_artifact_verified", "TERMINAL_succeeded"}.issubset(set(result.route_trace))
    ledger = M2A1ReceiptLedger.open_existing(result.ledger_path, approved_authority_root=result.ledger_path.parent)
    assert [event["event_type"] for event in ledger.events(result.receipt_id)] == ["REGISTERED", "CONSUMED_BEFORE_RUN", "TERMINAL"]
    output = result.ledger_path.parent.parent / "output"
    assert all((output / name).is_file() for name in ("actual.json", "oracle_evaluation.json", "reviewer_gate.json"))


@pytest.mark.parametrize("branch", ["corrupt_actual", "reviewer_fail", "exit_after_consume", "missing_oracle"])
def test_v2_10_shared_kernel_failure_branches_reopen_known_authority_root_and_deny_replay(tmp_path: Path, branch: str) -> None:
    result = execute_synthetic_nonhuman_v2_10_fixture(temporary_root=tmp_path, parent=PARENT, package_digest=PACKAGE_DIGEST, branch=branch)
    _assert_outcome_unknown(result)
    assert "reopen_known_authority_root_outcome_unknown" in result.route_trace


def test_v2_10_oracle_write_oserror_cannot_leave_succeeded_terminal(tmp_path: Path) -> None:
    def failing_writer(_path: Path, _value: object, _digest: str, _field: str) -> str:
        raise OSError("injected_oracle_write_failure")

    _assert_outcome_unknown(execute_synthetic_nonhuman_v2_10_fixture(temporary_root=tmp_path, parent=PARENT, package_digest=PACKAGE_DIGEST, branch="oracle_write_oserror", artifact_writer=failing_writer))


def test_v2_10_post_consume_first_ledger_reopen_failure_recovers_by_known_authority_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = M2A1ReceiptLedger.open_existing.__func__
    calls = 0

    def fail_once(cls: type[M2A1ReceiptLedger], db_path: Path, *, approved_authority_root: Path) -> M2A1ReceiptLedger:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise M2A1ReceiptAuthorityError("injected_first_reopen_failure")
        return original(cls, db_path, approved_authority_root=approved_authority_root)

    monkeypatch.setattr(M2A1ReceiptLedger, "open_existing", classmethod(fail_once))
    result = execute_synthetic_nonhuman_v2_10_fixture(temporary_root=tmp_path, parent=PARENT, package_digest=PACKAGE_DIGEST)
    _assert_outcome_unknown(result)
    assert calls >= 2 and "reopen_known_authority_root_outcome_unknown" in result.route_trace


def test_v2_10_trigger_ddl_digest_is_stable_and_nonempty() -> None:
    assert event_append_only_trigger_ddl_digest() == canonical_digest({"point01_m2_a1_execution_receipt_events_no_update": "create trigger point01_m2_a1_execution_receipt_events_no_update before update on point01_m2_a1_execution_receipt_events begin select raise(abort, 'point01_m2_a1_execution_receipt_events_append_only_update_denied'); end", "point01_m2_a1_execution_receipt_events_no_delete": "create trigger point01_m2_a1_execution_receipt_events_no_delete before delete on point01_m2_a1_execution_receipt_events begin select raise(abort, 'point01_m2_a1_execution_receipt_events_append_only_delete_denied'); end"})


def test_v2_10_historical_package_cannot_authorize_repaired_runtime() -> None:
    package = _mapping(PACKAGE_PATH)
    entries = package["executable_authority_contract"]["entries"]
    bindings = package["transport_isolation"]["runtime_hash_bindings"]
    assert {name: binding for name, binding in bindings.items() if name != "canary"} == entries
    assert all("v2_10" in binding["relative_path"] for binding in entries.values())
    assert package["trigger_ddl_contract"]["normalized_ddl_digest"] == event_append_only_trigger_ddl_digest()
    with pytest.raises(M2A1ExecutionPreflightError, match="execution_(git_index_hash_mismatch|working_index_drift)"):
        preflight_exact_execution(package, None, repository_root=ROOT, receipt_id="v2-10-test-no-receipt", scenario_id="p01-baseline-separated-input", human_approval_digest="0" * 64)
