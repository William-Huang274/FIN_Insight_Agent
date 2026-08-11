from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sec_agent.canonical_runtime.checkpoint_artifacts import CheckpointArtifactService
from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.facade import RuntimeFacade, RuntimeFacadeError
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import CommandEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.recovery_lifecycle import RecoveryLifecycleService
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore, StaleStateVersion


pytestmark = pytest.mark.fast_contract

BASE_TIME = datetime(2026, 7, 12, 14, 30, tzinfo=timezone.utc)


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
        tenant_id="tenant-m5-3",
        project_id="project-m5-3",
        case_id="case-m5-3",
        actor_snapshot_ref="actor-m5-3",
        permission_snapshot_ref="permission-m5-3",
        policy_config_refs=("policy-m5-3",),
        idempotency_key=idem,
        expected_state_version=expected,
        correlation_id="correlation-m5-3",
        requested_at=at,
        payload=payload,
    )


def _runtime(tmp_path) -> tuple[RuntimeFacade, DurableSchedulerService, CheckpointArtifactService]:
    facade = RuntimeFacade(
        SQLiteCanonicalStore(tmp_path / "canonical.sqlite"),
        FileCanonicalObjectStore(tmp_path / "objects"),
        _flags(),
        mode="shadow",
        grants={"point01.shadow.write"},
    )
    facade.create_research_case(
        _command("CREATE_RESEARCH_CASE", {"query": "M5.3 checkpoint fixture", "accountable_owner_ref": "lead-m5-3"}, idem="case")
    )
    scheduler = DurableSchedulerService(facade)
    scheduler.enqueue(
        _command(
            "CREATE_WORK_UNIT",
            {
                "work_unit_id": "wu-checkpoint",
                "work_unit_type": "decision_surface_compile",
                "input_version_refs": ["summary-v1"],
                "queue_name": "checkpoint-shadow",
                "max_attempts": 2,
                "retry_budget": 1,
                "retry_policy_ref": "retry:bounded",
                "retryable_failure_types": ["transient"],
            },
            idem="enqueue",
        )
    )
    scheduler.claim_next(
        _command(
            "SCHEDULER_CLAIM_NEXT",
            {
                "queue_name": "checkpoint-shadow",
                "work_unit_id": "wu-checkpoint",
                "worker_ref": "worker-checkpoint",
                "attempt_id": "attempt-checkpoint-1",
                "lease_duration_seconds": 60,
            },
            idem="claim",
        )
    )
    return facade, scheduler, CheckpointArtifactService(facade)


def _checkpoint_command(
    *,
    snapshot: dict,
    expected_checkpoint_version: int,
    supersedes_version_id: str | None,
    idem: str,
    at: datetime = BASE_TIME + timedelta(seconds=1),
) -> CommandEnvelope:
    return _command(
        "CREATE_CHECKPOINT_VERSION",
        {
            "work_unit_id": "wu-checkpoint",
            "attempt_id": "attempt-checkpoint-1",
            "worker_ref": "worker-checkpoint",
            "lease_fencing_token": 1,
            "checkpoint_id": "checkpoint-runtime",
            "expected_checkpoint_version": expected_checkpoint_version,
            "supersedes_version_id": supersedes_version_id,
            "checkpoint_schema_ref": "checkpoint-schema-v1",
            "snapshot": snapshot,
        },
        expected=1,
        idem=idem,
        at=at,
    )


def test_checkpoint_record_event_atomicity_idempotency_and_replay(tmp_path) -> None:
    facade, _, checkpoints = _runtime(tmp_path)
    command = _checkpoint_command(snapshot={"cursor": "phase-1", "accepted_refs": ["summary-v1"]}, expected_checkpoint_version=0, supersedes_version_id=None, idem="checkpoint-v1")
    result = checkpoints.write(command)
    repeated = checkpoints.write(command)

    assert result.artifact_refs == ("checkpoint-runtime:v1",)
    assert (result.state_version_before, result.state_version_after) == (0, 1)
    assert repeated.reused_idempotent_result is True
    checkpoint_rows = [row for row in facade.store.list_versions("canonical_artifact_versions", case_id="case-m5-3") if row["artifact_type"] == "runtime_checkpoint"]
    checkpoint_events = [event for event in facade.store.list_events() if event["event_type"] == "CHECKPOINT_VERSION_CREATED"]
    assert len(checkpoint_rows) == len(checkpoint_events) == 1
    exact = checkpoints.read_exact(case_id="case-m5-3", checkpoint_ref="checkpoint-runtime:v1")
    assert exact["snapshot"] == {"cursor": "phase-1", "accepted_refs": ["summary-v1"]}
    replay = facade.replay_projection()
    assert replay == facade.replay_projection()
    assert replay["artifacts"]["checkpoint-runtime:v1"]["artifact_type"] == "runtime_checkpoint"


def test_checkpoint_supersession_preserves_history_and_rejects_stale_writer(tmp_path) -> None:
    _, _, checkpoints = _runtime(tmp_path)
    checkpoints.write(_checkpoint_command(snapshot={"cursor": "phase-1"}, expected_checkpoint_version=0, supersedes_version_id=None, idem="checkpoint-v1"))
    second = checkpoints.write(
        _checkpoint_command(
            snapshot={"cursor": "phase-2", "repair": "targeted"},
            expected_checkpoint_version=1,
            supersedes_version_id="checkpoint-runtime:v1",
            idem="checkpoint-v2",
            at=BASE_TIME + timedelta(seconds=2),
        )
    )
    assert (second.state_version_before, second.state_version_after) == (1, 2)
    with pytest.raises(StaleStateVersion, match="stale_checkpoint_version"):
        checkpoints.write(
            _checkpoint_command(
                snapshot={"cursor": "stale"},
                expected_checkpoint_version=1,
                supersedes_version_id="checkpoint-runtime:v1",
                idem="checkpoint-stale",
                at=BASE_TIME + timedelta(seconds=3),
            )
        )
    assert checkpoints.read_exact(case_id="case-m5-3", checkpoint_ref="checkpoint-runtime:v1")["snapshot"]["cursor"] == "phase-1"
    v2 = checkpoints.read_exact(case_id="case-m5-3", checkpoint_ref="checkpoint-runtime:v2")
    assert v2["artifact"]["supersedes_version_id"] == "checkpoint-runtime:v1"
    view = checkpoints.recovery_view(case_id="case-m5-3")
    assert view["checkpoint_count"] == 2
    assert [row["is_latest"] for row in view["records"]] == [False, True]


def test_checkpoint_object_failure_publishes_no_canonical_record_or_event(tmp_path) -> None:
    facade, _, checkpoints = _runtime(tmp_path)

    class FailingObjectStore:
        def put_json(self, payload, *, namespace, artifact_type):
            raise OSError("checkpoint_object_store_failure")

        def get_json(self, object_key, *, expected_digest=None):
            raise AssertionError("not_called")

    facade.object_store = FailingObjectStore()
    with pytest.raises(OSError, match="checkpoint_object_store_failure"):
        checkpoints.write(
            _checkpoint_command(snapshot={"cursor": "never-persisted"}, expected_checkpoint_version=0, supersedes_version_id=None, idem="checkpoint-fail")
        )
    assert not [row for row in facade.store.list_versions("canonical_artifact_versions", case_id="case-m5-3") if row["artifact_type"] == "runtime_checkpoint"]
    assert not [event for event in facade.store.list_events() if event["event_type"] == "CHECKPOINT_VERSION_CREATED"]


def test_checkpoint_rejects_unbounded_snapshot_before_object_or_canonical_write(tmp_path) -> None:
    facade, _, checkpoints = _runtime(tmp_path)
    with pytest.raises(RuntimeFacadeError, match="checkpoint_snapshot_too_large"):
        checkpoints.write(
            _checkpoint_command(
                snapshot={"unbounded_context": "x" * 262_145},
                expected_checkpoint_version=0,
                supersedes_version_id=None,
                idem="checkpoint-too-large",
            )
        )
    assert not [row for row in facade.store.list_versions("canonical_artifact_versions", case_id="case-m5-3") if row["artifact_type"] == "runtime_checkpoint"]
    assert not [event for event in facade.store.list_events() if event["event_type"] == "CHECKPOINT_VERSION_CREATED"]


def test_checkpoint_restarts_with_exact_snapshot_and_is_accepted_by_m5_2_resume(tmp_path) -> None:
    facade, scheduler, checkpoints = _runtime(tmp_path)
    checkpoints.write(_checkpoint_command(snapshot={"cursor": "phase-1", "repair_queue": ["cell-7"]}, expected_checkpoint_version=0, supersedes_version_id=None, idem="checkpoint-v1"))

    restarted_facade = RuntimeFacade(
        SQLiteCanonicalStore(tmp_path / "canonical.sqlite"),
        FileCanonicalObjectStore(tmp_path / "objects"),
        _flags(),
        mode="shadow",
        grants={"point01.shadow.write"},
    )
    restarted_checkpoint = CheckpointArtifactService(restarted_facade).require_exact_checkpoint(
        case_id="case-m5-3", checkpoint_ref="checkpoint-runtime:v1"
    )
    assert restarted_checkpoint["snapshot"]["repair_queue"] == ["cell-7"]

    facade.fail_attempt(
        _command(
            "FAIL_ATTEMPT",
            {
                "work_unit_id": "wu-checkpoint",
                "attempt_id": "attempt-checkpoint-1",
                "worker_ref": "worker-checkpoint",
                "lease_fencing_token": 1,
                "failure_type": "transient",
                "retryable": True,
            },
            expected=1,
            idem="fail-checkpoint-attempt",
            at=BASE_TIME + timedelta(seconds=4),
        )
    )
    resume = RecoveryLifecycleService(facade, scheduler=scheduler).resume(
        _command(
            "RECOVERY_RESUME",
            {
                "work_unit_id": "wu-checkpoint",
                "queue_name": "checkpoint-shadow",
                "worker_ref": "worker-recovery",
                "attempt_id": "attempt-checkpoint-2",
                "resume_checkpoint_ref": "checkpoint-runtime:v1",
            },
            expected=2,
            idem="resume-from-checkpoint",
            at=BASE_TIME + timedelta(seconds=5),
        )
    )
    assert resume.projection_refs == ("wu-checkpoint", "attempt-checkpoint-2")
    assert facade.store.get_latest("canonical_attempts", "attempt-checkpoint-2")["resume_checkpoint_ref"] == "checkpoint-runtime:v1"
