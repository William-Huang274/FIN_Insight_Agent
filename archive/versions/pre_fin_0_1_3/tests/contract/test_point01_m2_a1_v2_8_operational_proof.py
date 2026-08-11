"""B0.5 SQLite event-source and frozen lifecycle operational proof."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.m2_a1_execution_receipt import (
    M2A1ExecutionReceipt,
    M2A1ExternalPackageAdmission,
    M2A1ReceiptAuthorityError,
    M2A1ReceiptLedger,
    V2_8_ADMISSION_SCHEMA,
    V2_8_RECEIPT_SCHEMA,
)
from sec_agent.canonical_runtime.m2_a1_v2_8_operational_proof import (
    execute_v2_8_frozen_lifecycle_core,
    reconcile_synthetic_nonhuman_fixture,
)


ROOT = Path(__file__).resolve().parents[2]
CHILD = ROOT / "scripts/engineering/run_point01_m2_a1_v2_8_synthetic_operational_child.py"
PACKAGE_DIGEST = "f" * 64


def _authority(now: datetime) -> tuple[M2A1ExternalPackageAdmission, M2A1ExecutionReceipt, str]:
    human = "a" * 64
    admission = M2A1ExternalPackageAdmission.create(
        admission_ref="synthetic_nonhuman_fixture_only",
        admission_id="v2-8-ledger-admission",
        admission_version=1,
        reviewer_identity="synthetic/nonhuman-fixture",
        package_ref="v2-8-ledger-package",
        executable_package_digest=PACKAGE_DIGEST,
        scope="synthetic_temporary_only",
        authority_boundary="no_network_no_fixed_store_no_business_case",
        execution_staging_namespace_id="v2-8-ledger-namespace",
        expires_at=now + timedelta(minutes=10),
        schema_version=V2_8_ADMISSION_SCHEMA,
        human_approval_digest=human,
    )
    receipt = M2A1ExecutionReceipt.create(
        receipt_id="v2-8-ledger-receipt",
        receipt_version=1,
        approval_id="synthetic_nonhuman_fixture_only",
        package_ref=admission.package_ref,
        executable_package_digest=PACKAGE_DIGEST,
        scope=admission.scope,
        admission_digest=admission.admission_digest,
        nonce_sha256="b" * 64,
        expires_at=now + timedelta(minutes=5),
        reviewer_identity=admission.reviewer_identity,
        execution_staging_namespace_id=admission.execution_staging_namespace_id,
        scenario_id="v2-8-ledger-scenario",
        schema_version=V2_8_RECEIPT_SCHEMA,
        human_approval_digest=human,
    )
    return admission, receipt, human


def _registered_ledger(tmp_path: Path) -> tuple[M2A1ReceiptLedger, M2A1ExternalPackageAdmission, M2A1ExecutionReceipt, str]:
    admission, receipt, human = _authority(datetime.now(timezone.utc))
    root = tmp_path / "run"
    authority = root / "authority"
    authority.mkdir(parents=True)
    ledger = M2A1ReceiptLedger.create_for_registration(authority / "m2_a1_execution_receipts.sqlite", approved_authority_root=authority)
    ledger.register(
        receipt,
        admission=admission,
        package_ref=admission.package_ref,
        executable_package_digest=PACKAGE_DIGEST,
        scope=admission.scope,
        authority_boundary=admission.authority_boundary,
        execution_staging_namespace_id=admission.execution_staging_namespace_id,
        scenario_id=receipt.scenario_id,
        expected_admission_schema_version=V2_8_ADMISSION_SCHEMA,
        expected_receipt_schema_version=V2_8_RECEIPT_SCHEMA,
        expected_human_approval_digest=human,
    )
    return ledger, admission, receipt, human


def test_event_table_rejects_update_and_delete_at_sqlite_boundary(tmp_path: Path) -> None:
    ledger, _admission, receipt, _human = _registered_ledger(tmp_path)
    with sqlite3.connect(ledger.db_path) as connection, pytest.raises(sqlite3.DatabaseError, match="append_only_update_denied"):
        connection.execute("update point01_m2_a1_execution_receipt_events set payload_json = ? where receipt_id = ?", ("{}", receipt.receipt_id))
    with sqlite3.connect(ledger.db_path) as connection, pytest.raises(sqlite3.DatabaseError, match="append_only_delete_denied"):
        connection.execute("delete from point01_m2_a1_execution_receipt_events where receipt_id = ?", (receipt.receipt_id,))
    assert [row["event_type"] for row in ledger.events(receipt.receipt_id)] == ["REGISTERED"]


@pytest.mark.parametrize(
    ("trigger_name", "replacement"),
    [
        ("point01_m2_a1_execution_receipt_events_no_update", "create trigger point01_m2_a1_execution_receipt_events_no_update before update on point01_m2_a1_execution_receipt_events when 0 begin select raise(abort, 'point01_m2_a1_execution_receipt_events_append_only_update_denied'); end;"),
        ("point01_m2_a1_execution_receipt_events_no_update", "create trigger point01_m2_a1_execution_receipt_events_no_update before update on point01_m2_a1_execution_receipt_events begin select raise(abort, 'wrong_abort_message'); end;"),
        ("point01_m2_a1_execution_receipt_events_no_update", "create trigger point01_m2_a1_execution_receipt_events_no_update before delete on point01_m2_a1_execution_receipt_events begin select raise(abort, 'point01_m2_a1_execution_receipt_events_append_only_update_denied'); end;"),
        ("point01_m2_a1_execution_receipt_events_no_update", "create trigger point01_m2_a1_execution_receipt_events_no_update before update on point01_m2_a1_execution_receipts begin select raise(abort, 'point01_m2_a1_execution_receipt_events_append_only_update_denied'); end;"),
    ],
)
def test_open_existing_rejects_conditional_or_wrong_append_only_trigger_ddl(tmp_path: Path, trigger_name: str, replacement: str) -> None:
    ledger, _admission, _receipt, _human = _registered_ledger(tmp_path)
    with sqlite3.connect(ledger.db_path) as connection:
        connection.execute(f"drop trigger {trigger_name}")
        connection.execute(replacement)
    with pytest.raises(M2A1ReceiptAuthorityError, match="receipt_ledger_event_append_only_trigger_invalid"):
        M2A1ReceiptLedger.open_existing(ledger.db_path, approved_authority_root=ledger.approved_authority_root)


def test_open_existing_rejects_missing_append_only_trigger_before_lifecycle_access(tmp_path: Path) -> None:
    ledger, _admission, _receipt, _human = _registered_ledger(tmp_path)
    with sqlite3.connect(ledger.db_path) as connection:
        connection.execute("drop trigger point01_m2_a1_execution_receipt_events_no_delete")
    with pytest.raises(M2A1ReceiptAuthorityError, match="receipt_ledger_event_append_only_triggers_missing"):
        M2A1ReceiptLedger.open_existing(ledger.db_path, approved_authority_root=ledger.approved_authority_root)


def test_tampered_clone_payload_or_digest_fails_closed_on_event_read(tmp_path: Path) -> None:
    ledger, _admission, receipt, _human = _registered_ledger(tmp_path)
    clone_root = tmp_path / "clone" / "authority"
    clone_root.mkdir(parents=True)
    clone_path = clone_root / "m2_a1_execution_receipts.sqlite"
    shutil.copy2(ledger.db_path, clone_path)
    # Simulate a legacy/offline tamper copy: remove enforcement, alter one
    # field, then restore the exact trigger names.  Opening passes schema
    # presence checks, while the event read must still reject its digest drift.
    with sqlite3.connect(clone_path) as connection:
        connection.execute("drop trigger point01_m2_a1_execution_receipt_events_no_update")
        connection.execute("drop trigger point01_m2_a1_execution_receipt_events_no_delete")
        connection.execute("update point01_m2_a1_execution_receipt_events set payload_json = ? where receipt_id = ?", (json.dumps({"receipt_digest": "0" * 64}), receipt.receipt_id))
        connection.executescript(
            """
            create trigger point01_m2_a1_execution_receipt_events_no_update before update on point01_m2_a1_execution_receipt_events begin select raise(abort, 'point01_m2_a1_execution_receipt_events_append_only_update_denied'); end;
            create trigger point01_m2_a1_execution_receipt_events_no_delete before delete on point01_m2_a1_execution_receipt_events begin select raise(abort, 'point01_m2_a1_execution_receipt_events_append_only_delete_denied'); end;
            """
        )
    clone = M2A1ReceiptLedger.open_existing(clone_path, approved_authority_root=clone_root)
    with pytest.raises(M2A1ReceiptAuthorityError, match="payload_digest_mismatch"):
        clone.events(receipt.receipt_id)


def test_v2_8_frozen_subprocess_happy_path_uses_real_oracle_and_reviewer(tmp_path: Path) -> None:
    result = execute_v2_8_frozen_lifecycle_core(synthetic_nonhuman_fixture=True, temporary_root=tmp_path, child=CHILD, package_digest=PACKAGE_DIGEST)
    assert result.state == "succeeded"
    assert result.actual is not None and result.oracle is not None and result.reviewer is not None
    assert result.oracle.status == "pass" and result.reviewer.status == "pass"
    ledger = M2A1ReceiptLedger.open_existing(result.ledger_path, approved_authority_root=result.ledger_path.parent)
    events = ledger.events(result.receipt_id)
    assert [event["event_type"] for event in events] == ["REGISTERED", "CONSUMED_BEFORE_RUN", "TERMINAL"]
    terminal = ledger.verify_terminal_event(
        result.receipt_id,
        expected_human_approval_digest=result.receipt.human_approval_digest,
        expected_actual_result_digest=result.actual.actual_result_digest,
        expected_oracle_evaluation_digest=result.oracle.evaluation_digest,
        expected_reviewer_gate_digest=result.reviewer.gate_digest,
    )
    assert terminal["terminal_status"] == "succeeded"


@pytest.mark.parametrize("mode", ["corrupt", "reviewer_fail"])
def test_v2_8_corrupt_actual_or_real_reviewer_failure_only_records_outcome_unknown(tmp_path: Path, mode: str) -> None:
    result = execute_v2_8_frozen_lifecycle_core(synthetic_nonhuman_fixture=True, temporary_root=tmp_path, child=CHILD, package_digest=PACKAGE_DIGEST, mode=mode)
    assert result.state == "outcome_unknown" and result.terminal_digest
    ledger = M2A1ReceiptLedger.open_existing(result.ledger_path, approved_authority_root=result.ledger_path.parent)
    terminal = ledger.verify_terminal_event(result.receipt_id, expected_human_approval_digest=result.receipt.human_approval_digest)
    assert terminal["terminal_status"] == "outcome_unknown"


def test_v2_8_child_exit_reopens_reconciles_outcome_unknown_and_denies_replay(tmp_path: Path) -> None:
    result = execute_v2_8_frozen_lifecycle_core(
        synthetic_nonhuman_fixture=True,
        temporary_root=tmp_path,
        child=CHILD,
        package_digest=PACKAGE_DIGEST,
        mode="exit_after_consume",
        leave_consumed_for_restart=True,
    )
    assert result.state == "consumed_pending_restart_reconciliation"
    terminal = reconcile_synthetic_nonhuman_fixture(result)
    ledger = M2A1ReceiptLedger.open_existing(result.ledger_path, approved_authority_root=result.ledger_path.parent)
    assert terminal
    assert ledger.verify_terminal_event(result.receipt_id, expected_human_approval_digest=result.receipt.human_approval_digest)["terminal_status"] == "outcome_unknown"
    with pytest.raises(M2A1ReceiptAuthorityError):
        ledger.consume_before_run(
            result.receipt_id,
            admission=result.admission,
            package_ref=result.admission.package_ref,
            executable_package_digest=PACKAGE_DIGEST,
            scope=result.admission.scope,
            authority_boundary=result.admission.authority_boundary,
            preflight_digest=result.grant.preflight_digest,
            run_root=result.ledger_path.parent.parent,
            execution_staging_namespace_id=result.admission.execution_staging_namespace_id,
            scenario_id=result.receipt.scenario_id,
            expected_admission_schema_version=V2_8_ADMISSION_SCHEMA,
            expected_receipt_schema_version=V2_8_RECEIPT_SCHEMA,
            expected_human_approval_digest=result.receipt.human_approval_digest,
        )
