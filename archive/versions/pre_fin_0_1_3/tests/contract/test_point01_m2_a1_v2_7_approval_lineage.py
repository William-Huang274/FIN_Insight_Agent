"""B0.4 authority-lineage and preterminal-order regressions; no active approval."""

from __future__ import annotations

import json
import importlib.util
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.m2_a1_audit_result import M2A1ImmutableActualResult
from sec_agent.canonical_runtime.m2_a1_execution_receipt import (
    M2A1ExecutionReceipt,
    M2A1ExternalPackageAdmission,
    M2A1ReceiptAuthorityError,
    M2A1ReceiptLedger,
    V2_7_ADMISSION_SCHEMA,
    V2_7_RECEIPT_SCHEMA,
    preflight_exact_execution,
)
from sec_agent.canonical_runtime.models import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
CHILD = ROOT / "scripts/engineering/run_point01_m2_a1_v2_7_synthetic_terminal_child.py"
REFREEZE = ROOT / "scripts/engineering/run_point01_m2_a1_operational_qualification_v2_7_refreeze.py"
JIT = ROOT / "scripts/engineering/run_point01_m2_a1_v2_7_frozen_jit_window.py"
PACKAGE_DIGEST = "1" * 64
HUMAN_APPROVAL_DIGEST = "2" * 64
PREFLIGHT_DIGEST = "3" * 64


def test_v2_7_refrozen_package_uses_production_preflight_without_materialization() -> None:
    spec = importlib.util.spec_from_file_location("m2_a1_v2_7_refreeze", REFREEZE)
    assert spec and spec.loader
    freeze = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(freeze)
    artifacts = freeze.build_artifacts()
    package = artifacts["package"]
    now = datetime.now(timezone.utc)
    admission = M2A1ExternalPackageAdmission.create(admission_ref="synthetic-v2-7-preflight", admission_id="synthetic-v2-7-preflight", admission_version=1, reviewer_identity="fixture/reviewer", package_ref=package["package_ref"], executable_package_digest=package["package_digest"], scope=package["scope"], authority_boundary=package["authority_boundary"], execution_staging_namespace_id=package["execution_preflight"]["execution_staging_namespace_id"], expires_at=now + timedelta(minutes=10), schema_version=V2_7_ADMISSION_SCHEMA, human_approval_digest=HUMAN_APPROVAL_DIGEST)
    preflight = preflight_exact_execution(package, admission, repository_root=ROOT, receipt_id="synthetic-v2-7-preflight", scenario_id="p01-baseline-separated-input", human_approval_digest=HUMAN_APPROVAL_DIGEST)
    assert preflight.human_approval_digest == HUMAN_APPROVAL_DIGEST
    assert not preflight.execution_staging_namespace.exists()


def _authority(now: datetime) -> tuple[M2A1ExternalPackageAdmission, M2A1ExecutionReceipt]:
    admission = M2A1ExternalPackageAdmission.create(
        admission_ref="synthetic-nonhuman-fixture",
        admission_id="synthetic-v2-7-admission",
        admission_version=1,
        reviewer_identity="fixture/reviewer",
        package_ref="synthetic-v2-7-package",
        executable_package_digest=PACKAGE_DIGEST,
        scope="synthetic_temporary_only",
        authority_boundary="no_network_no_fixed_store_no_business_case",
        execution_staging_namespace_id="synthetic-v2-7-namespace",
        expires_at=now + timedelta(minutes=20),
        schema_version=V2_7_ADMISSION_SCHEMA,
        human_approval_digest=HUMAN_APPROVAL_DIGEST,
    )
    receipt = M2A1ExecutionReceipt.create(
        receipt_id="synthetic-v2-7-receipt",
        receipt_version=1,
        approval_id="synthetic-nonhuman-fixture",
        package_ref=admission.package_ref,
        executable_package_digest=PACKAGE_DIGEST,
        scope=admission.scope,
        admission_digest=admission.admission_digest,
        nonce_sha256="4" * 64,
        expires_at=now + timedelta(minutes=10),
        reviewer_identity=admission.reviewer_identity,
        execution_staging_namespace_id=admission.execution_staging_namespace_id,
        scenario_id="synthetic-terminal-scenario",
        schema_version=V2_7_RECEIPT_SCHEMA,
        human_approval_digest=HUMAN_APPROVAL_DIGEST,
    )
    return admission, receipt


def _register_and_consume(tmp_path: Path) -> tuple[M2A1ReceiptLedger, M2A1ExternalPackageAdmission, M2A1ExecutionReceipt, object]:
    now = datetime.now(timezone.utc)
    admission, receipt = _authority(now)
    authority_root = tmp_path / "synthetic-run" / "authority"
    authority_root.mkdir(parents=True)
    ledger = M2A1ReceiptLedger.create_for_registration(authority_root / "m2_a1_execution_receipts.sqlite", approved_authority_root=authority_root)
    common = dict(package_ref=admission.package_ref, executable_package_digest=PACKAGE_DIGEST, scope=admission.scope, authority_boundary=admission.authority_boundary, execution_staging_namespace_id=admission.execution_staging_namespace_id, scenario_id=receipt.scenario_id, expected_admission_schema_version=V2_7_ADMISSION_SCHEMA, expected_receipt_schema_version=V2_7_RECEIPT_SCHEMA, expected_human_approval_digest=HUMAN_APPROVAL_DIGEST)
    ledger.register(receipt, admission=admission, **common)
    grant = ledger.consume_before_run(receipt.receipt_id, admission=admission, preflight_digest=PREFLIGHT_DIGEST, run_root=authority_root.parent, **common)
    return ledger, admission, receipt, grant


def test_v2_7_synthetic_subprocess_chain_binds_human_digest_before_terminal(tmp_path: Path) -> None:
    ledger, admission, receipt, grant = _register_and_consume(tmp_path)
    consumed = ledger.verify_consumption_grant(grant, admission=admission, package_ref=admission.package_ref, executable_package_digest=PACKAGE_DIGEST, scope=admission.scope, authority_boundary=admission.authority_boundary, execution_staging_namespace_id=admission.execution_staging_namespace_id, scenario_id=receipt.scenario_id, run_root=ledger.approved_authority_root.parent, preflight_digest=PREFLIGHT_DIGEST, expected_admission_schema_version=V2_7_ADMISSION_SCHEMA, expected_receipt_schema_version=V2_7_RECEIPT_SCHEMA, expected_human_approval_digest=HUMAN_APPROVAL_DIGEST)
    output = tmp_path / "synthetic-run" / "actual.json"
    child = subprocess.run([sys.executable, str(CHILD), "--output", str(output), "--package-digest", PACKAGE_DIGEST, "--admission-digest", admission.admission_digest, "--receipt-digest", consumed.receipt_digest, "--scenario-id", receipt.scenario_id], cwd=ROOT, capture_output=True, text=True, check=False)
    assert child.returncode == 0, child.stderr
    actual = M2A1ImmutableActualResult.model_validate(json.loads(output.read_text(encoding="utf-8")))
    assert actual.verify_immutable_digest()
    assert actual.executable_package_digest == PACKAGE_DIGEST and actual.scenario_id == receipt.scenario_id
    oracle_digest = canonical_digest({"synthetic": "independent-oracle", "actual": actual.actual_result_digest})
    reviewer_digest = canonical_digest({"synthetic": "preterminal-reviewer", "oracle": oracle_digest})
    terminal = ledger.record_terminal_event(receipt.receipt_id, terminal_status="succeeded", actual_result_digest=actual.actual_result_digest, oracle_evaluation_digest=oracle_digest, reviewer_gate_digest=reviewer_digest, expected_human_approval_digest=HUMAN_APPROVAL_DIGEST)
    events = ledger.events(receipt.receipt_id)
    assert [event["event_type"] for event in events] == ["REGISTERED", "CONSUMED_BEFORE_RUN", "TERMINAL"]
    payloads = [json.loads(event["payload_json"]) for event in events]
    assert all(payload.get("human_approval_digest") == HUMAN_APPROVAL_DIGEST for payload in payloads)
    assert payloads[-1]["actual_result_digest"] == actual.actual_result_digest
    assert terminal == events[-1]["payload_digest"]
    with pytest.raises(M2A1ReceiptAuthorityError):
        ledger.consume_before_run(receipt.receipt_id, admission=admission, package_ref=admission.package_ref, executable_package_digest=PACKAGE_DIGEST, scope=admission.scope, authority_boundary=admission.authority_boundary, preflight_digest=PREFLIGHT_DIGEST, run_root=ledger.approved_authority_root.parent, execution_staging_namespace_id=admission.execution_staging_namespace_id, scenario_id=receipt.scenario_id, expected_admission_schema_version=V2_7_ADMISSION_SCHEMA, expected_receipt_schema_version=V2_7_RECEIPT_SCHEMA, expected_human_approval_digest=HUMAN_APPROVAL_DIGEST)


def test_v2_7_missing_wrong_and_tampered_human_digest_fail_before_success(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    admission, receipt = _authority(now)
    authority_root = tmp_path / "authority"
    authority_root.mkdir()
    ledger = M2A1ReceiptLedger.create_for_registration(authority_root / "m2_a1_execution_receipts.sqlite", approved_authority_root=authority_root)
    common = dict(package_ref=admission.package_ref, executable_package_digest=PACKAGE_DIGEST, scope=admission.scope, authority_boundary=admission.authority_boundary, execution_staging_namespace_id=admission.execution_staging_namespace_id, scenario_id=receipt.scenario_id, expected_admission_schema_version=V2_7_ADMISSION_SCHEMA, expected_receipt_schema_version=V2_7_RECEIPT_SCHEMA)
    with pytest.raises(M2A1ReceiptAuthorityError, match="human_approval"):
        ledger.register(receipt, admission=admission, **common)
    with pytest.raises(M2A1ReceiptAuthorityError, match="human_approval"):
        ledger.register(receipt, admission=admission, expected_human_approval_digest="f" * 64, **common)
    ledger.register(receipt, admission=admission, expected_human_approval_digest=HUMAN_APPROVAL_DIGEST, **common)
    # B0.5 makes events database-enforced append-only: a direct tamper never
    # reaches the consume path in a healthy ledger.
    with sqlite3.connect(ledger.db_path) as connection, pytest.raises(sqlite3.DatabaseError, match="append_only_update_denied"):
        connection.execute("update point01_m2_a1_execution_receipt_events set payload_json = ? where receipt_id = ? and event_type = ?", (json.dumps({"human_approval_digest": "0" * 64}), receipt.receipt_id, "REGISTERED"))
    assert [event["event_type"] for event in ledger.events(receipt.receipt_id)] == ["REGISTERED"]


def test_v2_7_invalid_actual_or_reviewer_failure_records_only_outcome_unknown(tmp_path: Path) -> None:
    ledger, _admission, receipt, _grant = _register_and_consume(tmp_path)
    with pytest.raises(Exception):
        M2A1ImmutableActualResult.model_validate({"scenario_id": receipt.scenario_id})
    terminal = ledger.recover_consumed_without_terminal(receipt.receipt_id)
    events = ledger.events(receipt.receipt_id)
    payload = json.loads(events[-1]["payload_json"])
    assert payload["terminal_status"] == "outcome_unknown"
    assert payload["human_approval_digest"] == HUMAN_APPROVAL_DIGEST
    assert terminal == events[-1]["payload_digest"]
    with pytest.raises(M2A1ReceiptAuthorityError, match="already_recorded"):
        ledger.record_terminal_event(receipt.receipt_id, terminal_status="succeeded", actual_result_digest="8" * 64, oracle_evaluation_digest="9" * 64, reviewer_gate_digest="a" * 64, expected_human_approval_digest=HUMAN_APPROVAL_DIGEST)


def test_v2_7_jit_validates_actual_oracle_and_reviewer_before_terminal_append(tmp_path: Path) -> None:
    """The frozen active path may never append success from a raw child file."""

    source = JIT.read_text(encoding="utf-8")
    actual_index = source.index("M2A1ImmutableActualResult.model_validate")
    oracle_index = source.index("oracle = evaluate_independent_oracle")
    reviewer_index = source.index("reviewer = review_future_actual")
    terminal_index = source.index("terminal = ledger.record_terminal_event")
    assert actual_index < oracle_index < reviewer_index < terminal_index
    assert source.index("if reviewer.status != \"pass\":") < terminal_index
    assert source.index("ledger.recover_consumed_without_terminal(receipt.receipt_id)") < terminal_index
    # Model a reviewer rejection after consumption: no success append is
    # allowed; the only durable terminal is outcome_unknown.
    ledger, _admission, receipt, _grant = _register_and_consume(tmp_path)
    terminal = ledger.recover_consumed_without_terminal(receipt.receipt_id)
    payload = json.loads(ledger.events(receipt.receipt_id)[-1]["payload_json"])
    assert payload["terminal_status"] == "outcome_unknown"
    assert terminal != "" and payload.get("reviewer_gate_digest") is None
