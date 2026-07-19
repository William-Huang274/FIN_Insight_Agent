from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sec_agent.canonical_runtime.capability_security import (
    CapabilityGrant,
    CapabilitySecurityError,
    CapabilitySecurityService,
    SandboxAdmissionRequest,
    ToolManifest,
)
from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import CommandEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


pytestmark = pytest.mark.fast_contract

BASE_TIME = datetime(2026, 7, 12, 15, 0, tzinfo=timezone.utc)


def _flags() -> FeatureFlagRegistry:
    return FeatureFlagRegistry(
        {
            "default_deny": True,
            "flags": [
                {
                    "flag_id": "decision_surface_shadow_v0_1",
                    "default_mode": "off",
                    "allowed_modes": ["off", "shadow"],
                    "required_capability_grants": ["point01.shadow.write"],
                    "allowed_consumers": ["point01_shadow_compiler"],
                    "forbidden_consumers": ["memo_writer", "evidence_runtime"],
                }
            ],
        }
    )


def _command(command_type: str, payload: dict, *, idem: str, expected: int = 0, at: datetime = BASE_TIME) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=f"cmd-{idem}",
        command_type=command_type,
        tenant_id="tenant-m5-4",
        project_id="project-m5-4",
        case_id="case-m5-4",
        actor_snapshot_ref="actor-m5-4",
        permission_snapshot_ref="permission-m5-4",
        policy_config_refs=("policy-m5-4",),
        idempotency_key=idem,
        expected_state_version=expected,
        correlation_id="correlation-m5-4",
        requested_at=at,
        payload=payload,
    )


def _runtime(tmp_path) -> tuple[RuntimeFacade, DurableSchedulerService]:
    facade = RuntimeFacade(
        SQLiteCanonicalStore(tmp_path / "canonical.sqlite"),
        FileCanonicalObjectStore(tmp_path / "objects"),
        _flags(),
        mode="shadow",
        grants={"point01.shadow.write"},
    )
    facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "M5.4 fixture", "accountable_owner_ref": "lead-m5-4"}, idem="case"))
    scheduler = DurableSchedulerService(facade)
    scheduler.enqueue(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-secure", "input_version_refs": ["summary-v1"], "queue_name": "security-shadow"}, idem="enqueue"))
    scheduler.claim_next(
        _command(
            "SCHEDULER_CLAIM_NEXT",
            {"queue_name": "security-shadow", "work_unit_id": "wu-secure", "worker_ref": "worker-security", "attempt_id": "attempt-security-1", "lease_duration_seconds": 60},
            idem="claim",
        )
    )
    return facade, scheduler


def _grant(*, expires_at: datetime = BASE_TIME + timedelta(hours=1), revoked_at: datetime | None = None) -> CapabilityGrant:
    return CapabilityGrant(
        grant_id="grant-checkpoint",
        tenant_id="tenant-m5-4",
        project_id="project-m5-4",
        case_id="case-m5-4",
        permission_snapshot_ref="permission-m5-4",
        capabilities=("checkpoint.write",),
        allowed_tool_ids=("canonical_checkpoint_store",),
        allowed_network_hosts=("checkpoint-safe.example",),
        allowed_path_prefixes=("artifact_store/point01",),
        allowed_data_classifications=("internal",),
        issued_at=BASE_TIME - timedelta(minutes=1),
        expires_at=expires_at,
        revoked_at=revoked_at,
    )


def _manifest() -> ToolManifest:
    return ToolManifest(
        tool_id="canonical_checkpoint_store",
        capabilities=("checkpoint.write",),
        allowed_network_hosts=("checkpoint-safe.example",),
        allowed_path_prefixes=("artifact_store/point01",),
        allowed_data_classifications=("internal",),
    )


def _security(facade: RuntimeFacade, *, grant: CapabilityGrant | None = None) -> CapabilitySecurityService:
    authority = grant or _grant()
    security = CapabilitySecurityService(facade, grants=(authority,), tool_manifests=(_manifest(),))
    security.register_authority(_command("CAPABILITY_GRANT_RECORDED", {}, idem=f"grant-{authority.grant_id}"), authority)
    return security


def _request(**updates) -> SandboxAdmissionRequest:
    request = SandboxAdmissionRequest(
        capability_grant_id="grant-checkpoint",
        capability="checkpoint.write",
        tool_id="canonical_checkpoint_store",
        target_tenant_id="tenant-m5-4",
        target_project_id="project-m5-4",
        target_case_id="case-m5-4",
        data_classification="internal",
        path="artifact_store/point01/checkpoints",
    )
    return request.model_copy(update=updates)


def _checkpoint_command(*, idem: str, at: datetime = BASE_TIME + timedelta(seconds=1)) -> CommandEnvelope:
    return _command(
        "CREATE_CHECKPOINT_VERSION",
        {
            "work_unit_id": "wu-secure",
            "attempt_id": "attempt-security-1",
            "worker_ref": "worker-security",
            "lease_fencing_token": 1,
            "checkpoint_id": "checkpoint-secure",
            "expected_checkpoint_version": 0,
            "supersedes_version_id": None,
            "checkpoint_schema_ref": "checkpoint-schema-v1",
            "snapshot": {"cursor": "secure-phase"},
        },
        expected=1,
        idem=idem,
        at=at,
    )


def test_grant_binds_permission_snapshot_and_protects_checkpoint_write(tmp_path) -> None:
    facade, _ = _runtime(tmp_path)
    security = _security(facade)
    result = security.execute_checkpoint_write(_checkpoint_command(idem="secure-write"), _request())
    assert result.artifact_refs == ("checkpoint-secure:v1",)
    audit = security.audit_view()
    assert audit["allowed_count"] == 1
    decision = audit["decisions"][0]
    assert decision["permission_snapshot_ref"] == "permission-m5-4"
    assert decision["denial_code"] is None
    assert decision["external_call_count"] == 0


@pytest.mark.parametrize(
    ("updates", "denial_code"),
    [
        ({"capability": "unknown.capability"}, "unknown_capability"),
        ({"target_tenant_id": "tenant-other"}, "tenant_cross_read_denied"),
        ({"data_classification": "restricted"}, "privacy_classification_denied"),
        ({"network_host": "evil.example"}, "network_scope_denied"),
        ({"path": "workspace/private"}, "path_scope_denied"),
        ({"tool_id": "unknown-tool"}, "unknown_tool"),
    ],
)
def test_security_denies_unknown_cross_tenant_privacy_network_path_and_tool_scope(tmp_path, updates, denial_code) -> None:
    facade, _ = _runtime(tmp_path)
    decision = _security(facade).admit(_checkpoint_command(idem=f"deny-{denial_code}"), _request(**updates))
    assert decision.allowed is False
    assert decision.denial_code == denial_code
    assert decision.trace[-1] == f"denied:{denial_code}"


def test_permission_snapshot_mismatch_is_denied(tmp_path) -> None:
    facade, _ = _runtime(tmp_path)
    wrong_snapshot_command = _checkpoint_command(idem="snapshot-mismatch").model_copy(update={"permission_snapshot_ref": "permission-other"})
    decision = _security(facade).admit(wrong_snapshot_command, _request())
    assert decision.allowed is False
    assert decision.denial_code == "permission_snapshot_mismatch"


@pytest.mark.parametrize(
    ("grant", "expected_code"),
    [
        (_grant(expires_at=BASE_TIME), "capability_grant_expired"),
        (_grant(revoked_at=BASE_TIME), "capability_grant_revoked"),
    ],
)
def test_expired_or_revoked_grant_blocks_checkpoint_mutation(tmp_path, grant, expected_code) -> None:
    facade, _ = _runtime(tmp_path)
    security = _security(facade, grant=grant)
    with pytest.raises(CapabilitySecurityError, match=expected_code):
        security.execute_checkpoint_write(_checkpoint_command(idem=f"blocked-{expected_code}"), _request())
    assert not [row for row in facade.store.list_versions("canonical_artifact_versions", case_id="case-m5-4") if row["artifact_type"] == "runtime_checkpoint"]
    assert security.audit_view()["denied_count"] == 1


def test_persisted_grant_and_security_audit_survive_restart_without_seed_mapping(tmp_path) -> None:
    facade, _ = _runtime(tmp_path)
    security = _security(facade)
    allowed = security.admit(_checkpoint_command(idem="persisted-allowed"), _request())
    assert allowed.allowed is True

    restarted = RuntimeFacade(
        SQLiteCanonicalStore(tmp_path / "canonical.sqlite"),
        FileCanonicalObjectStore(tmp_path / "objects"),
        _flags(),
        mode="shadow",
        grants={"point01.shadow.write"},
    )
    recovered = CapabilitySecurityService(restarted, grants=(), tool_manifests=(_manifest(),))
    denied = recovered.admit(_checkpoint_command(idem="persisted-denied"), _request(path="workspace/private"))
    audit = recovered.audit_view()
    assert denied.denial_code == "path_scope_denied"
    assert [decision["allowed"] for decision in audit["decisions"]] == [True, False]
    assert restarted.store.get_latest("canonical_capability_grant_versions", "grant-checkpoint")["grant_state"] == "active"


def test_checkpoint_mutation_rechecks_persisted_grant_in_its_own_transaction(tmp_path) -> None:
    facade, _ = _runtime(tmp_path)
    security = _security(facade)
    prior = security.admit(_checkpoint_command(idem="prior-admit"), _request())
    assert prior.allowed is True and prior.grant_version == 1
    revoked = _grant(revoked_at=BASE_TIME + timedelta(seconds=2))
    security.register_authority(_command("CAPABILITY_GRANT_RECORDED", {}, idem="grant-revoked", at=BASE_TIME + timedelta(seconds=2)), revoked)
    with pytest.raises(CapabilitySecurityError, match="capability_grant_revoked"):
        security.execute_checkpoint_write(_checkpoint_command(idem="write-after-revocation", at=BASE_TIME + timedelta(seconds=3)), _request())
    assert not [row for row in facade.store.list_versions("canonical_artifact_versions", case_id="case-m5-4") if row["artifact_type"] == "runtime_checkpoint"]
