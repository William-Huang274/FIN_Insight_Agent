from __future__ import annotations

import importlib.util
from datetime import timedelta
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.bounded_sec_metadata_execution import SingleCallSecSubmissionsClient
from sec_agent.canonical_runtime.m6_pilot_global_approval import (
    M6GlobalOneShotApprovalError,
    M6GlobalOneShotApprovalReceipt,
    M6GlobalOneShotApprovalService,
    build_m6_pilot_scope,
)
from sec_agent.canonical_runtime.m6_pilot_package import compute_m6_pilot_package
from sec_agent.canonical_runtime.models import utc_now
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
M6_2_TEST_PATH = ROOT / "tests/contract/test_point01_m6_2_real_bounded_sec_metadata_execution.py"
PACKAGE_MANIFEST_PATH = ROOT / "configs/engineering_handoff/point01_m6_2_global_one_shot_package_manifest_v1_0.json"

SPEC = importlib.util.spec_from_file_location("point01_m6_2_global_one_shot_helpers", M6_2_TEST_PATH)
assert SPEC and SPEC.loader
M6_2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M6_2)


def _scope_and_package():
    command = M6_2._command(
        "EXECUTE_M6_2_REAL_BOUNDED_SEC_METADATA",
        {
            "work_unit_id": "wu-m6-2-live",
            "attempt_id": "attempt-m6-2-live-1",
            "worker_ref": "worker-m6-2-live",
            "lease_fencing_token": 1,
        },
        idem="global-one-shot",
        expected=1,
    )
    request = M6_2._request()
    plan = M6_2._plan(request)
    policy = M6_2._policy()
    return (
        build_m6_pilot_scope(
            command=command,
            request=request,
            plan=plan,
            approval_ref=policy.approval_ref,
            approved_execution_scope=policy.approved_execution_scope,
            tool_id=policy.tool_id,
            route_id=policy.route_id,
            network_host=policy.allowed_network_host,
            target_cik=policy.allowed_cik,
        ),
        compute_m6_pilot_package(root=ROOT, manifest_path=PACKAGE_MANIFEST_PATH),
    )


def _register_active_receipt(tmp_path: Path, *, approval_id: str = "approval-test-global-once"):
    store = SQLiteCanonicalStore(tmp_path / "fixed-approval-authority" / "canonical.sqlite")
    service = M6GlobalOneShotApprovalService(store=store)
    scope, package = _scope_and_package()
    receipt = M6GlobalOneShotApprovalReceipt.create(
        tenant_id="tenant-global-approval-test",
        project_id="project-global-approval-test",
        actor_snapshot_ref="human:william:003",
        permission_snapshot_ref="human-review:test",
        policy_config_refs=("point01-m6-2-global-one-shot-authority-policy-v1",),
        correlation_id="correlation-global-one-shot-test",
        current_status="active",
        approval_id=approval_id,
        approval_version=1,
        state_version=1,
        approval_state="active",
        approval_nonce="global-one-shot-test-nonce-0001",
        scope_digest=scope.scope_digest,
        package_ref=package.package_ref,
        package_digest=package.package_digest,
        package_manifest_digest=package.manifest_digest,
        reviewer_name="william",
        reviewer_employee_id="003",
        reviewer_role="total_reviewer",
        expires_at=utc_now() + timedelta(hours=1),
        authority_store_identity=store.store_identity(),
    )
    service.register_authoritative_receipt(receipt)
    return service, scope, package


def test_global_receipt_is_atomically_consumed_across_distinct_local_stores(tmp_path: Path) -> None:
    service, scope, package = _register_active_receipt(tmp_path)
    consumed = service.consume(
        scope=scope,
        package_ref=package.package_ref,
        package_digest=package.package_digest,
        package_manifest_digest=package.manifest_digest,
        approval_id="approval-test-global-once",
        invocation_id="invocation-local-store-a",
        local_store_identity="a" * 64,
    )
    assert consumed.approval_state == "consumed"
    assert consumed.consumed_local_store_identity == "a" * 64
    with pytest.raises(M6GlobalOneShotApprovalError, match="global_approval_not_active:consumed"):
        service.consume(
            scope=scope,
            package_ref=package.package_ref,
            package_digest=package.package_digest,
            package_manifest_digest=package.manifest_digest,
            approval_id="approval-test-global-once",
            invocation_id="invocation-local-store-b",
            local_store_identity="b" * 64,
        )
    rows = [
        row
        for row in service.store.list_versions(service.table)
        if row["approval_id"] == "approval-test-global-once"
    ]
    assert [row["approval_state"] for row in rows] == ["active", "consumed"]
    assert [row["approval_version"] for row in rows] == [1, 2]


def test_global_receipt_rejects_wrong_package_before_consumption(tmp_path: Path) -> None:
    service, scope, package = _register_active_receipt(tmp_path)
    with pytest.raises(M6GlobalOneShotApprovalError, match="global_approval_package_digest_mismatch"):
        service.consume(
            scope=scope,
            package_ref=package.package_ref,
            package_digest="0" * 64,
            package_manifest_digest=package.manifest_digest,
            approval_id="approval-test-global-once",
            invocation_id="invocation-wrong-package",
            local_store_identity="c" * 64,
        )
    latest = service.store.get_latest(service.table, "approval-test-global-once")
    assert latest and latest["approval_state"] == "active"


def test_global_receipt_rejects_expired_or_digest_tampered_authority(tmp_path: Path) -> None:
    service, _, _ = _register_active_receipt(tmp_path, approval_id="approval-test-global-expired")
    active = M6GlobalOneShotApprovalReceipt.model_validate(
        service.store.get_latest(service.table, "approval-test-global-expired")
    )
    expired = active.model_copy(update={"expires_at": utc_now() - timedelta(seconds=1)})
    with pytest.raises(M6GlobalOneShotApprovalError, match="global_approval_receipt_content_digest_mismatch"):
        service.register_authoritative_receipt(expired)
    fresh_store = SQLiteCanonicalStore(tmp_path / "separate-fixed-approval-authority" / "canonical.sqlite")
    fresh_service = M6GlobalOneShotApprovalService(store=fresh_store)
    truly_expired = M6GlobalOneShotApprovalReceipt.create(
        **{
            **active.model_dump(mode="python"),
            "approval_id": "approval-test-truly-expired",
            "expires_at": utc_now() - timedelta(seconds=1),
            "authority_store_identity": fresh_store.store_identity(),
        }
    )
    with pytest.raises(M6GlobalOneShotApprovalError, match="global_approval_initial_receipt_expired"):
        fresh_service.register_authoritative_receipt(truly_expired)


@pytest.mark.parametrize(
    ("user_agent", "reason"),
    [
        ("x", "sec_user_agent_too_short"),
        ("Placeholder-App/1.0 contact@example.com", "sec_user_agent_placeholder_contact_forbidden"),
        ("NoContactApplication/1.0 support", "sec_user_agent_contact_required"),
    ],
)
def test_sec_user_agent_requires_application_and_non_placeholder_contact(user_agent: str, reason: str) -> None:
    with pytest.raises(RuntimeError, match=reason):
        SingleCallSecSubmissionsClient(user_agent=user_agent, timeout_seconds=20)


def test_sec_user_agent_exposes_only_redacted_fingerprint() -> None:
    client = SingleCallSecSubmissionsClient(
        user_agent="FINInsight-Agent/1.0 compliance@finsight.test",
        timeout_seconds=20,
    )
    assert len(client.user_agent_fingerprint) == 64
    assert "@" not in client.user_agent_fingerprint
    assert "compliance" not in client.user_agent_fingerprint
