"""B0.2 dispatch and expired-unconsumed lifecycle regressions; no M2 scenario."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.m2_a1_execution_receipt import (
    M2A1ExecutionReceipt,
    M2A1ExternalPackageAdmission,
    M2A1ReceiptAuthorityError,
    M2A1ReceiptLedger,
    V2_4_ADMISSION_SCHEMA,
    V2_4_RECEIPT_SCHEMA,
)


ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_v2_5.py"


def _run_parent(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(PARENT), *args], cwd=ROOT, text=True, capture_output=True, check=False)


def test_parent_separator_normalization_and_parent_help_are_distinct() -> None:
    parent_help = _run_parent("--help")
    assert parent_help.returncode == 0
    assert "parent supervisor" in parent_help.stdout
    separated = _run_parent("--", "--help")
    direct = _run_parent("--help-child")
    assert separated.returncode == 0
    assert "clean Python child" in separated.stdout
    assert direct.returncode == 2
    assert json.loads(direct.stdout)["status"] == "m2_a1_parent_child_command_invalid"


def test_parent_forwards_exact_execute_vector_and_rejects_separator_or_value_errors() -> None:
    # Child argument validation happens before any package, authority, or
    # runtime access.  The command itself must arrive unchanged at the child.
    exact = ("--execute-admitted", "--admission", "D:/missing.json", "--receipt-id", "receipt-1", "--scenario-id", "p01-baseline-separated-input")
    forwarded = _run_parent("--", *exact)
    assert forwarded.returncode == 2
    assert json.loads(forwarded.stdout)["status"] == "m2_a1_json_input_unreadable"
    for values in (("--", "--", "--help"), ("--execute-admitted", "--admission", "x", "--receipt-id", "r", "--scenario-id"), ("--", "--help", "extra")):
        rejected = _run_parent(*values)
        assert rejected.returncode == 2
        assert json.loads(rejected.stdout)["child_started"] is False


def test_expired_unconsumed_transition_is_append_only_and_idempotent(tmp_path: Path) -> None:
    start = datetime(2026, 7, 16, 13, 0, tzinfo=timezone.utc)
    admission = M2A1ExternalPackageAdmission.create(
        admission_ref="synthetic-expiry-only",
        admission_id="synthetic-expiry-only",
        admission_version=1,
        reviewer_identity="william/003/total_reviewer",
        package_ref="synthetic-v2-4-package",
        executable_package_digest="a" * 64,
        scope="synthetic_expiry_only",
        authority_boundary="temporary_sqlite_only",
        execution_staging_namespace_id="synthetic-expiry",
        expires_at=start + timedelta(minutes=10),
        schema_version=V2_4_ADMISSION_SCHEMA,
    )
    receipt = M2A1ExecutionReceipt.create(
        receipt_id="synthetic-expired-unconsumed",
        receipt_version=1,
        approval_id="synthetic-expiry-only",
        package_ref=admission.package_ref,
        executable_package_digest=admission.executable_package_digest,
        scope=admission.scope,
        admission_digest=admission.admission_digest,
        nonce_sha256="b" * 64,
        expires_at=start + timedelta(minutes=5),
        reviewer_identity=admission.reviewer_identity,
        execution_staging_namespace_id=admission.execution_staging_namespace_id,
        scenario_id="p01-baseline-separated-input",
        schema_version=V2_4_RECEIPT_SCHEMA,
    )
    authority_root = tmp_path / "authority"
    authority_root.mkdir()
    ledger = M2A1ReceiptLedger.create_for_registration(authority_root / "m2_a1_execution_receipts.sqlite", approved_authority_root=authority_root)
    ledger.register(
        receipt,
        admission=admission,
        package_ref=admission.package_ref,
        executable_package_digest=admission.executable_package_digest,
        scope=admission.scope,
        authority_boundary=admission.authority_boundary,
        execution_staging_namespace_id=admission.execution_staging_namespace_id,
        scenario_id=receipt.scenario_id,
        expected_admission_schema_version=V2_4_ADMISSION_SCHEMA,
        expected_receipt_schema_version=V2_4_RECEIPT_SCHEMA,
        now=start,
    )
    before = ledger.state(receipt.receipt_id)
    assert before and before["state"] == "active_unconsumed"
    with pytest.raises(M2A1ReceiptAuthorityError, match="not_yet_expired"):
        ledger.expire_unconsumed_exact(receipt.receipt_id, admission=admission, executable_package_digest=admission.executable_package_digest, scenario_id=receipt.scenario_id, now=start + timedelta(minutes=7))
    first = ledger.expire_unconsumed_exact(receipt.receipt_id, admission=admission, executable_package_digest=admission.executable_package_digest, scenario_id=receipt.scenario_id, now=start + timedelta(minutes=11))
    second = ledger.expire_unconsumed_exact(receipt.receipt_id, admission=admission, executable_package_digest=admission.executable_package_digest, scenario_id=receipt.scenario_id, now=start + timedelta(minutes=12))
    after = ledger.state(receipt.receipt_id)
    assert first["terminal_status"] == "expired_unconsumed"
    assert second["terminal_status"] == "already_expired_unconsumed_exact"
    assert first["terminal_event_digest"] == second["terminal_event_digest"]
    assert after and after["state"] == "expired_unconsumed" and after["receipt_digest"] == receipt.receipt_digest
    assert [event["event_type"] for event in ledger.events(receipt.receipt_id)] == ["REGISTERED", "EXPIRED_UNCONSUMED"]
