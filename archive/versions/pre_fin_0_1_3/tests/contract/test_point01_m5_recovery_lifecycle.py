from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.facade import IllegalStateTransition, MissingDependency, RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import ArtifactVersionEnvelope, CommandEnvelope, canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.recovery_lifecycle import RecoveryLifecycleService
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


pytestmark = pytest.mark.fast_contract

BASE_TIME = datetime(2026, 7, 12, 14, 0, tzinfo=timezone.utc)


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


def _runtime(tmp_path) -> tuple[RuntimeFacade, DurableSchedulerService, RecoveryLifecycleService]:
    facade = RuntimeFacade(
        SQLiteCanonicalStore(tmp_path / "canonical.sqlite"),
        FileCanonicalObjectStore(tmp_path / "objects"),
        _flags(),
        mode="shadow",
        grants={"point01.shadow.write"},
    )
    facade.create_research_case(
        _command("CREATE_RESEARCH_CASE", {"query": "M5.2 recovery fixture", "accountable_owner_ref": "lead-m5-2"}, idem="case")
    )
    scheduler = DurableSchedulerService(facade)
    return facade, scheduler, RecoveryLifecycleService(facade, scheduler=scheduler)


def _command(
    command_type: str,
    payload: dict,
    *,
    expected: int = 0,
    idem: str,
    at: datetime = BASE_TIME,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=f"cmd-{idem}",
        command_type=command_type,
        tenant_id="tenant-m5-2",
        project_id="project-m5-2",
        case_id="case-m5-2",
        actor_snapshot_ref="actor-m5-2",
        permission_snapshot_ref="permission-m5-2",
        policy_config_refs=("policy-m5-2",),
        idempotency_key=idem,
        expected_state_version=expected,
        correlation_id="correlation-m5-2",
        requested_at=at,
        payload=payload,
    )


def _enqueue(
    scheduler: DurableSchedulerService,
    work_unit_id: str,
    *,
    max_attempts: int = 3,
    retry_budget: int = 2,
    retryable_failure_types: tuple[str, ...] = ("transient",),
    poison_failure_types: tuple[str, ...] = ("poison",),
) -> None:
    scheduler.enqueue(
        _command(
            "CREATE_WORK_UNIT",
            {
                "work_unit_id": work_unit_id,
                "work_unit_type": "decision_surface_compile",
                "input_version_refs": ["summary-v1"],
                "queue_name": "recovery-shadow",
                "max_attempts": max_attempts,
                "retry_budget": retry_budget,
                "retry_policy_ref": "retry:bounded",
                "retryable_failure_types": list(retryable_failure_types),
                "poison_failure_types": list(poison_failure_types),
            },
            idem=f"enqueue-{work_unit_id}",
        )
    )


def _claim_and_fail(
    facade: RuntimeFacade,
    scheduler: DurableSchedulerService,
    work_unit_id: str,
    attempt_id: str,
    *,
    failure_type: str = "transient",
    at: datetime = BASE_TIME,
) -> None:
    scheduler.claim_next(
        _command(
            "SCHEDULER_CLAIM_NEXT",
            {
                "queue_name": "recovery-shadow",
                "work_unit_id": work_unit_id,
                "worker_ref": "worker-m5-2",
                "attempt_id": attempt_id,
                "lease_duration_seconds": 60,
            },
            idem=f"claim-{attempt_id}",
            at=at,
        )
    )
    facade.fail_attempt(
        _command(
            "FAIL_ATTEMPT",
            {
                "work_unit_id": work_unit_id,
                "attempt_id": attempt_id,
                "worker_ref": "worker-m5-2",
                "lease_fencing_token": 1,
                "failure_type": failure_type,
                "retryable": True,
            },
            expected=1,
            idem=f"fail-{attempt_id}",
            at=at + timedelta(seconds=1),
        )
    )


def _checkpoint(facade: RuntimeFacade, *, artifact_id: str, producer_attempt_id: str) -> str:
    snapshot = {"checkpoint": artifact_id, "producer_attempt_id": producer_attempt_id}
    checkpoint_state_digest = canonical_digest(snapshot)
    checkpoint_payload = {
        "checkpoint_schema_ref": "checkpoint-schema-v1",
        "checkpoint_id": artifact_id,
        "checkpoint_version": 1,
        "checkpoint_version_id": f"{artifact_id}:v1",
        "producer_attempt_id": producer_attempt_id,
        "input_head_digest": canonical_digest(("summary-v1",)),
        "checkpoint_state_digest": checkpoint_state_digest,
        "snapshot": snapshot,
    }
    object_ref = facade.object_store.put_json(
        checkpoint_payload,
        namespace="point01/recovery-checkpoint-fixture",
        artifact_type="runtime_checkpoint",
    )
    artifact = ArtifactVersionEnvelope(
        tenant_id="tenant-m5-2",
        project_id="project-m5-2",
        case_id="case-m5-2",
        actor_snapshot_ref="actor-m5-2",
        permission_snapshot_ref="permission-m5-2",
        policy_config_refs=("policy-m5-2",),
        correlation_id="correlation-m5-2",
        created_at=BASE_TIME,
        recorded_at=BASE_TIME,
        current_status="checkpoint_available",
        artifact_id=artifact_id,
        artifact_version_id=f"{artifact_id}:v1",
        artifact_version=1,
        artifact_type="runtime_checkpoint",
        payload_business_owner="recovery_lifecycle_owner",
        producer_attempt_id=producer_attempt_id,
        input_refs=("summary-v1",),
        input_refs_digest=canonical_digest(("summary-v1",)),
        object_key=object_ref["object_key"],
        object_digest=object_ref["digest"],
        byte_size=object_ref["byte_size"],
        media_type=object_ref["media_type"],
        checkpoint_schema_ref="checkpoint-schema-v1",
        checkpoint_state_digest=checkpoint_state_digest,
        checkpoint_sequence_no=1,
    )
    with facade.store.transaction() as tx:
        tx.insert("canonical_artifact_versions", artifact_id, 1, artifact.model_dump(mode="json"))
    return artifact.artifact_version_id


def test_retry_is_store_backed_and_preserves_immutable_attempt_history(tmp_path) -> None:
    facade, scheduler, recovery = _runtime(tmp_path)
    _enqueue(scheduler, "wu-retry")
    _claim_and_fail(facade, scheduler, "wu-retry", "attempt-retry-1")

    retry = recovery.retry(
        _command(
            "RECOVERY_RETRY",
            {"work_unit_id": "wu-retry", "queue_name": "recovery-shadow", "worker_ref": "worker-recovery", "attempt_id": "attempt-retry-2"},
            expected=2,
            idem="retry-2",
            at=BASE_TIME + timedelta(seconds=2),
        )
    )
    assert retry.projection_refs == ("wu-retry", "attempt-retry-2")
    attempt = facade.store.get_latest("canonical_attempts", "attempt-retry-2")
    assert attempt["recovery_mode"] == "retry"
    assert attempt["recovery_parent_attempt_id"] == "attempt-retry-1"
    assert attempt["replay_plan_digest"]
    assert len([row for row in facade.store.list_latest("canonical_attempts", case_id="case-m5-2") if row["work_unit_id"] == "wu-retry"]) == 2
    assert [event["event_type"] for event in facade.store.list_events()][-1] == "RECOVERY_RETRY_SCHEDULED"
    assert recovery.build_replay_plan(case_id="case-m5-2", work_unit_id="wu-retry") == recovery.build_replay_plan(case_id="case-m5-2", work_unit_id="wu-retry")


def test_poison_work_cannot_retry_and_is_inspectable_dead_letter(tmp_path) -> None:
    facade, scheduler, recovery = _runtime(tmp_path)
    _enqueue(scheduler, "wu-poison", poison_failure_types=("poison_payload",))
    _claim_and_fail(facade, scheduler, "wu-poison", "attempt-poison-1", failure_type="poison_payload")
    assert facade.store.get_latest("canonical_work_units", "wu-poison")["state"] == "failed"
    with pytest.raises(IllegalStateTransition, match="recovery_requires_retryable_failed_work_unit"):
        recovery.retry(
            _command(
                "RECOVERY_RETRY",
                {"work_unit_id": "wu-poison", "queue_name": "recovery-shadow", "worker_ref": "worker-recovery"},
                expected=2,
                idem="poison-retry",
            )
        )
    recovery.dead_letter(
        _command(
            "RECOVERY_DEAD_LETTER",
            {"work_unit_id": "wu-poison", "source_attempt_id": "attempt-poison-1", "dead_letter_reason": "poison_payload"},
            expected=2,
            idem="poison-dead-letter",
            at=BASE_TIME + timedelta(seconds=2),
        )
    )
    view = recovery.dead_letter_view(case_id="case-m5-2")
    assert view["dead_letter_count"] == 1
    assert view["records"][0]["dead_letter_reason"] == "poison_payload"
    assert scheduler.queue_view(case_id="case-m5-2", queue_name="recovery-shadow")["counts"]["terminal"] == 1


def test_resume_requires_exact_checkpoint_and_fork_keeps_checkpoint_lineage(tmp_path) -> None:
    facade, scheduler, recovery = _runtime(tmp_path)
    _enqueue(scheduler, "wu-resume")
    _claim_and_fail(facade, scheduler, "wu-resume", "attempt-resume-1")
    checkpoint_ref = _checkpoint(facade, artifact_id="checkpoint-resume", producer_attempt_id="attempt-resume-1")
    with pytest.raises(MissingDependency, match="recovery_checkpoint_exact_version_required"):
        recovery.resume(
            _command(
                "RECOVERY_RESUME",
                {"work_unit_id": "wu-resume", "queue_name": "recovery-shadow", "worker_ref": "worker-recovery", "resume_checkpoint_ref": "checkpoint-resume"},
                expected=2,
                idem="resume-inexact",
            )
        )
    recovery.resume(
        _command(
            "RECOVERY_RESUME",
            {"work_unit_id": "wu-resume", "queue_name": "recovery-shadow", "worker_ref": "worker-recovery", "attempt_id": "attempt-resume-2", "resume_checkpoint_ref": checkpoint_ref},
            expected=2,
            idem="resume-exact",
            at=BASE_TIME + timedelta(seconds=2),
        )
    )
    resumed = facade.store.get_latest("canonical_attempts", "attempt-resume-2")
    assert resumed["recovery_mode"] == "resume"
    assert resumed["resume_checkpoint_ref"] == checkpoint_ref

    _enqueue(scheduler, "wu-fork")
    _claim_and_fail(facade, scheduler, "wu-fork", "attempt-fork-1", at=BASE_TIME + timedelta(seconds=10))
    fork_checkpoint_ref = _checkpoint(facade, artifact_id="checkpoint-fork", producer_attempt_id="attempt-fork-1")
    with pytest.raises(MissingDependency, match="recovery_checkpoint_parent_attempt_mismatch"):
        recovery.fork(
            _command(
                "RECOVERY_FORK",
                {"source_work_unit_id": "wu-fork", "source_attempt_id": "attempt-fork-1", "checkpoint_ref": checkpoint_ref, "work_unit_id": "wu-fork-wrong-checkpoint"},
                expected=2,
                idem="fork-wrong-checkpoint",
                at=BASE_TIME + timedelta(seconds=11),
            )
        )
    recovery.fork(
        _command(
            "RECOVERY_FORK",
            {"source_work_unit_id": "wu-fork", "source_attempt_id": "attempt-fork-1", "checkpoint_ref": fork_checkpoint_ref, "work_unit_id": "wu-fork-child"},
            expected=2,
            idem="fork-child",
            at=BASE_TIME + timedelta(seconds=12),
        )
    )
    child = facade.store.get_latest("canonical_work_units", "wu-fork-child")
    assert child["state"] == "pending"
    assert child["forked_from_work_unit_id"] == "wu-fork"
    assert child["forked_from_attempt_id"] == "attempt-fork-1"
    assert child["recovery_checkpoint_ref"] == fork_checkpoint_ref
    assert fork_checkpoint_ref in child["input_version_refs"]
    assert facade.store.get_latest("canonical_work_units", "wu-fork")["state_version"] == 2
    replay = facade.replay_projection()
    assert replay == facade.replay_projection()
    assert replay["work_units"]["wu-fork-child"]["forked_from_attempt_id"] == "attempt-fork-1"


def test_retry_budget_terminates_before_dead_letter(tmp_path) -> None:
    facade, scheduler, recovery = _runtime(tmp_path)
    _enqueue(scheduler, "wu-budget", max_attempts=2, retry_budget=1)
    _claim_and_fail(facade, scheduler, "wu-budget", "attempt-budget-1")
    recovery.retry(
        _command(
            "RECOVERY_RETRY",
            {"work_unit_id": "wu-budget", "queue_name": "recovery-shadow", "worker_ref": "worker-recovery", "attempt_id": "attempt-budget-2"},
            expected=2,
            idem="budget-retry",
            at=BASE_TIME + timedelta(seconds=2),
        )
    )
    facade.fail_attempt(
        _command(
            "FAIL_ATTEMPT",
            {"work_unit_id": "wu-budget", "attempt_id": "attempt-budget-2", "worker_ref": "worker-recovery", "lease_fencing_token": 2, "failure_type": "transient", "retryable": True},
            expected=3,
            idem="budget-fail-2",
            at=BASE_TIME + timedelta(seconds=3),
        )
    )
    assert facade.store.get_latest("canonical_work_units", "wu-budget")["state"] == "failed"
    with pytest.raises(IllegalStateTransition, match="recovery_requires_retryable_failed_work_unit"):
        recovery.retry(
            _command(
                "RECOVERY_RETRY",
                {"work_unit_id": "wu-budget", "queue_name": "recovery-shadow", "worker_ref": "worker-recovery"},
                expected=4,
                idem="budget-retry-exhausted",
            )
        )
