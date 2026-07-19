from __future__ import annotations

import importlib.util
from datetime import timedelta
from pathlib import Path

from sec_agent.canonical_runtime.m6_pilot_global_approval import M6GlobalOneShotApprovalReceipt, M6GlobalOneShotApprovalService
from sec_agent.canonical_runtime.models import utc_now
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts/engineering/run_point01_m6_3_5_positive_sec_document_receipt_preflight.py"
SPEC = importlib.util.spec_from_file_location("point01_m6_3_5_receipt_preflight", SCRIPT_PATH)
assert SPEC and SPEC.loader
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


def _register_exact_receipt(store: SQLiteCanonicalStore) -> None:
    freeze = PREFLIGHT._freeze()
    scope, authority = PREFLIGHT._scope()
    package = freeze["approval_package"]
    reviewer = authority["required_reviewer"]
    receipt = M6GlobalOneShotApprovalReceipt.create(
        tenant_id="global",
        project_id="point01",
        case_id=None,
        actor_snapshot_ref="human-total-reviewer-william-003",
        permission_snapshot_ref="human-review-snapshot-point01-m6-3-5",
        policy_config_refs=(authority["policy_ref"],),
        correlation_id="test-point01-m6-3-5-receipt-preflight",
        current_status="active",
        approval_id=str(authority["approval_id"]),
        approval_version=1,
        state_version=1,
        approval_state="active",
        approval_nonce="test-receipt-preflight-nonce-0123456789",
        scope_digest=scope.scope_digest,
        package_ref=str(package["package_ref"]),
        package_digest=str(package["package_digest"]),
        package_manifest_digest=str(package["manifest_digest"]),
        reviewer_name=str(reviewer["name"]),
        reviewer_employee_id=str(reviewer["employee_id"]),
        reviewer_role=str(reviewer["role"]),
        expires_at=utc_now() + timedelta(minutes=10),
        authority_store_identity=store.store_identity(),
    )
    M6GlobalOneShotApprovalService(
        store=store,
        required_reviewer_name=str(reviewer["name"]),
        required_reviewer_employee_id=str(reviewer["employee_id"]),
        required_reviewer_role=str(reviewer["role"]),
    ).register_authoritative_receipt(receipt)


def test_exact_active_receipt_preflight_is_read_only_and_keeps_package_stable(tmp_path: Path) -> None:
    store = SQLiteCanonicalStore(tmp_path / "canonical.sqlite")
    _register_exact_receipt(store)

    result = PREFLIGHT.build_result(store=store)

    assert result["status"] == "pass"
    assert result["external_call_count"] == 0
    assert result["network_request_count"] == 0
    assert result["store_write_count"] == 0
    assert result["digest_stability"] is True
    assert result["one_shot_unconsumed"] is True
    assert len(result["receipt"]["nonce_sha256"]) == 64
    assert "approval_nonce" not in result["receipt"]


def test_missing_receipt_fails_closed_without_network_or_store_write(tmp_path: Path) -> None:
    store = SQLiteCanonicalStore(tmp_path / "canonical.sqlite")

    result = PREFLIGHT.build_result(store=store)

    assert result["status"] == "fail_closed"
    assert result["reason"] == "global_approval_receipt_not_registered"
    assert result["external_call_count"] == 0
    assert result["network_request_count"] == 0
    assert result["store_write_count"] == 0
