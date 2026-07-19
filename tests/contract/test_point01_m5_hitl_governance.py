from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.facade import LeaseValidationError, RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.hitl_governance import ApprovalRegistryRecord, HITLApprovalError, HITLGovernanceService
from sec_agent.canonical_runtime.models import CommandEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


pytestmark = pytest.mark.fast_contract

BASE_TIME = datetime(2026, 7, 12, 16, 0, tzinfo=timezone.utc)


def _flags() -> FeatureFlagRegistry:
    return FeatureFlagRegistry({"default_deny": True, "flags": [{"flag_id": "decision_surface_shadow_v0_1", "default_mode": "off", "allowed_modes": ["off", "shadow"], "required_capability_grants": ["point01.shadow.write"], "allowed_consumers": ["point01_shadow_compiler"], "forbidden_consumers": ["memo_writer", "evidence_runtime"]}]})


def _command(command_type: str, payload: dict, *, idem: str, expected: int = 0, at: datetime = BASE_TIME) -> CommandEnvelope:
    return CommandEnvelope(command_id=f"cmd-{idem}", command_type=command_type, tenant_id="tenant-m5-6", project_id="project-m5-6", case_id="case-m5-6", actor_snapshot_ref="actor-m5-6", permission_snapshot_ref="permission-m5-6", policy_config_refs=("policy-m5-6",), idempotency_key=idem, expected_state_version=expected, correlation_id="correlation-m5-6", requested_at=at, payload=payload)


def _runtime(tmp_path) -> RuntimeFacade:
    facade = RuntimeFacade(SQLiteCanonicalStore(tmp_path / "canonical.sqlite"), FileCanonicalObjectStore(tmp_path / "objects"), _flags(), mode="shadow", grants={"point01.shadow.write"})
    facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "M5.6 fixture", "accountable_owner_ref": "lead-m5-6"}, idem="case"))
    scheduler = DurableSchedulerService(facade)
    scheduler.enqueue(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-hitl", "input_version_refs": ["summary-v1"], "queue_name": "hitl-shadow", "max_attempts": 2, "retry_budget": 1, "retry_policy_ref": "retry:bounded", "retryable_failure_types": ["transient"]}, idem="enqueue"))
    scheduler.claim_next(_command("SCHEDULER_CLAIM_NEXT", {"queue_name": "hitl-shadow", "work_unit_id": "wu-hitl", "worker_ref": "worker-hitl", "attempt_id": "attempt-hitl-1", "lease_duration_seconds": 120}, idem="claim"))
    facade.create_checkpoint_version(_command("CREATE_CHECKPOINT_VERSION", {"work_unit_id": "wu-hitl", "attempt_id": "attempt-hitl-1", "worker_ref": "worker-hitl", "lease_fencing_token": 1, "checkpoint_id": "checkpoint-hitl", "expected_checkpoint_version": 0, "supersedes_version_id": None, "checkpoint_schema_ref": "checkpoint-schema-v1", "snapshot": {"cursor": "pause"}}, expected=1, idem="checkpoint", at=BASE_TIME + timedelta(seconds=1)))
    return facade


def _pause_command(*, scope_digest: str, approval_id: str = "approval-hitl", at: datetime = BASE_TIME + timedelta(seconds=2)) -> CommandEnvelope:
    return _command("HITL_PAUSE", {"approval_id": approval_id, "work_unit_id": "wu-hitl", "attempt_id": "attempt-hitl-1", "checkpoint_ref": "checkpoint-hitl:v1", "scope_digest": scope_digest, "worker_ref": "worker-hitl", "lease_fencing_token": 1}, expected=1, idem=f"pause-{approval_id}", at=at)


def _registry(scope_digest: str, *, approval_id: str = "approval-hitl", state: str = "active", expires_at: datetime = BASE_TIME + timedelta(minutes=10)) -> dict[str, ApprovalRegistryRecord]:
    return {approval_id: ApprovalRegistryRecord(approval_id=approval_id, approval_registry_ref="registry:hitl-fixture", scope_digest=scope_digest, approval_state=state, expires_at=expires_at)}


def _pause(facade: RuntimeFacade, *, approval_id: str = "approval-hitl") -> tuple[HITLGovernanceService, str]:
    draft = _pause_command(scope_digest="draft", approval_id=approval_id)
    scope_digest = HITLGovernanceService._scope_digest(draft, work_unit_id="wu-hitl", attempt_id="attempt-hitl-1", checkpoint_ref="checkpoint-hitl:v1")
    service = HITLGovernanceService(facade, approval_registry=_registry(scope_digest, approval_id=approval_id))
    service.pause(_pause_command(scope_digest=scope_digest, approval_id=approval_id))
    return service, scope_digest


def test_pause_survives_restart_and_resume_releases_old_fencing_token(tmp_path) -> None:
    facade = _runtime(tmp_path)
    service, scope_digest = _pause(facade)
    assert facade.store.get_latest("canonical_work_units", "wu-hitl")["state"] == "paused"
    assert facade.store.get_latest("canonical_attempts", "attempt-hitl-1")["state"] == "paused"

    restarted = RuntimeFacade(SQLiteCanonicalStore(tmp_path / "canonical.sqlite"), FileCanonicalObjectStore(tmp_path / "objects"), _flags(), mode="shadow", grants={"point01.shadow.write"})
    resumed = HITLGovernanceService(restarted, approval_registry=_registry(scope_digest))
    queue = resumed.review_queue(case_id="case-m5-6", at=BASE_TIME + timedelta(seconds=3))
    assert queue["paused_count"] == 1
    assert queue["review_queue"][0]["eligible_to_resume"] is True

    result = resumed.resume(_command("HITL_RESUME", {"approval_id": "approval-hitl", "work_unit_id": "wu-hitl", "attempt_id": "attempt-hitl-1", "scope_digest": scope_digest, "worker_ref": "worker-resumed", "lease_duration_seconds": 60}, expected=2, idem="resume", at=BASE_TIME + timedelta(seconds=4)))
    assert result.state_version_after == 3
    attempt = restarted.store.get_latest("canonical_attempts", "attempt-hitl-1")
    assert attempt["state"] == "running"
    assert attempt["lease_fencing_token"] == 2

    with pytest.raises(LeaseValidationError, match="lease_fencing_token_mismatch"):
        restarted.complete_attempt(_command("COMPLETE_ATTEMPT", {"work_unit_id": "wu-hitl", "attempt_id": "attempt-hitl-1", "worker_ref": "worker-resumed", "lease_fencing_token": 1, "output_artifact_refs": []}, expected=3, idem="stale-worker", at=BASE_TIME + timedelta(seconds=5)))


def test_revoked_or_expired_registry_fails_closed_before_resume(tmp_path) -> None:
    facade = _runtime(tmp_path)
    service, scope_digest = _pause(facade)
    service.replace_approval_registry(_registry(scope_digest, state="revoked"))
    service.invalidate(_command("HITL_INVALIDATE", {"approval_id": "approval-hitl", "reason": "reviewer_revoked"}, expected=1, idem="invalidate", at=BASE_TIME + timedelta(seconds=3)))
    assert facade.store.get_latest("canonical_hitl_approval_versions", "approval-hitl")["approval_status"] == "revoked"
    with pytest.raises(HITLApprovalError, match="hitl_approval_not_active"):
        service.resume(_command("HITL_RESUME", {"approval_id": "approval-hitl", "work_unit_id": "wu-hitl", "attempt_id": "attempt-hitl-1", "scope_digest": scope_digest, "worker_ref": "worker-resumed", "lease_duration_seconds": 60}, expected=2, idem="resume-revoked", at=BASE_TIME + timedelta(seconds=4)))

    second = _runtime(tmp_path / "expired")
    draft = _pause_command(scope_digest="draft", approval_id="approval-expired")
    expired_scope = HITLGovernanceService._scope_digest(draft, work_unit_id="wu-hitl", attempt_id="attempt-hitl-1", checkpoint_ref="checkpoint-hitl:v1")
    expired = HITLGovernanceService(second, approval_registry=_registry(expired_scope, approval_id="approval-expired", expires_at=BASE_TIME + timedelta(seconds=4)))
    expired.pause(_pause_command(scope_digest=expired_scope, approval_id="approval-expired"))
    with pytest.raises(HITLApprovalError, match="hitl_approval_expired"):
        expired.resume(_command("HITL_RESUME", {"approval_id": "approval-expired", "work_unit_id": "wu-hitl", "attempt_id": "attempt-hitl-1", "scope_digest": expired_scope, "worker_ref": "worker-resumed", "lease_duration_seconds": 60}, expected=2, idem="resume-expired", at=BASE_TIME + timedelta(seconds=5)))


def test_scope_or_registry_identity_tampering_fails_before_pause_mutation(tmp_path) -> None:
    facade = _runtime(tmp_path)
    draft = _pause_command(scope_digest="wrong")
    expected_scope = HITLGovernanceService._scope_digest(draft, work_unit_id="wu-hitl", attempt_id="attempt-hitl-1", checkpoint_ref="checkpoint-hitl:v1")
    service = HITLGovernanceService(facade, approval_registry=_registry(expected_scope))
    with pytest.raises(HITLApprovalError, match="hitl_scope_digest_mismatch"):
        service.pause(draft)
    assert facade.store.get_latest("canonical_work_units", "wu-hitl")["state"] == "running"


def test_persisted_registry_authority_survives_restart_without_constructor_mapping(tmp_path) -> None:
    facade = _runtime(tmp_path)
    draft = _pause_command(scope_digest="draft")
    scope_digest = HITLGovernanceService._scope_digest(draft, work_unit_id="wu-hitl", attempt_id="attempt-hitl-1", checkpoint_ref="checkpoint-hitl:v1")
    writer = HITLGovernanceService(facade, approval_registry={})
    writer.register_authority(_command("HITL_REGISTRY_RECORD", {}, idem="registry-active"), _registry(scope_digest)["approval-hitl"])
    restarted = RuntimeFacade(SQLiteCanonicalStore(tmp_path / "canonical.sqlite"), FileCanonicalObjectStore(tmp_path / "objects"), _flags(), mode="shadow", grants={"point01.shadow.write"})
    reader = HITLGovernanceService(restarted, approval_registry={})
    reader.pause(_pause_command(scope_digest=scope_digest))
    assert restarted.store.get_latest("canonical_work_units", "wu-hitl")["state"] == "paused"
    assert reader.review_queue(case_id="case-m5-6", at=BASE_TIME + timedelta(seconds=2))["paused_count"] == 1
    reader.register_authority(_command("HITL_REGISTRY_RECORD", {}, expected=0, idem="registry-revoked", at=BASE_TIME + timedelta(seconds=3)), _registry(scope_digest, state="revoked")["approval-hitl"])
    reader.invalidate(_command("HITL_INVALIDATE", {"approval_id": "approval-hitl", "reason": "persisted_registry_revocation"}, expected=1, idem="invalidate", at=BASE_TIME + timedelta(seconds=4)))
    assert restarted.store.get_latest("canonical_hitl_approval_versions", "approval-hitl")["approval_status"] == "revoked"
