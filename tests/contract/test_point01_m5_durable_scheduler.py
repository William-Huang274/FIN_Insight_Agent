from __future__ import annotations

from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

import pytest

from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.facade import LeaseValidationError, RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import CommandEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


pytestmark = pytest.mark.fast_contract


BASE_TIME = datetime(2026, 7, 12, 13, 30, tzinfo=timezone.utc)


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


def _scheduler(tmp_path) -> DurableSchedulerService:
    facade = RuntimeFacade(
        SQLiteCanonicalStore(tmp_path / "canonical.sqlite"),
        FileCanonicalObjectStore(tmp_path / "objects"),
        _flags(),
        mode="shadow",
        grants={"point01.shadow.write"},
    )
    facade.create_research_case(
        _command(
            "CREATE_RESEARCH_CASE",
            {"query": "Scheduler control-plane fixture.", "accountable_owner_ref": "lead-1"},
            idem="case",
        )
    )
    return DurableSchedulerService(facade)


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
        tenant_id="tenant-test",
        project_id="project-test",
        case_id="case-1",
        actor_snapshot_ref="actor-1",
        permission_snapshot_ref="permission-1",
        policy_config_refs=("policy-point01",),
        idempotency_key=idem,
        expected_state_version=expected,
        correlation_id="correlation-m5-scheduler",
        requested_at=at,
        payload=payload,
    )


def _enqueue(scheduler: DurableSchedulerService, work_unit_id: str, *, priority: int = 0, at: datetime = BASE_TIME) -> None:
    scheduler.enqueue(
        _command(
            "CREATE_WORK_UNIT",
            {
                "work_unit_id": work_unit_id,
                "work_unit_type": "decision_surface_compile",
                "input_version_refs": ["summary-v1"],
                "queue_name": "planning-shadow",
                "queue_priority": priority,
            },
            idem=f"enqueue-{work_unit_id}",
            at=at,
        )
    )


def test_scheduler_claims_highest_priority_and_fences_duplicate_claim(tmp_path) -> None:
    scheduler = _scheduler(tmp_path)
    _enqueue(scheduler, "wu-low", priority=1)
    _enqueue(scheduler, "wu-high", priority=9)

    claim = scheduler.claim_next(
        _command(
            "SCHEDULER_CLAIM_NEXT",
            {"queue_name": "planning-shadow", "worker_ref": "worker-a", "attempt_id": "attempt-high", "lease_duration_seconds": 30},
            idem="claim-high",
        )
    )
    assert claim.projection_refs == ("wu-high", "attempt-high")
    attempt = scheduler.facade.store.get_latest("canonical_attempts", "attempt-high")
    assert attempt["scheduler_managed"] is True
    assert attempt["lease_fencing_token"] == 1
    with pytest.raises(LeaseValidationError, match="scheduler_lease_already_active"):
        scheduler.claim_next(
            _command(
                "SCHEDULER_CLAIM_NEXT",
                {"queue_name": "planning-shadow", "work_unit_id": "wu-high", "worker_ref": "worker-b"},
                expected=1,
                idem="duplicate-claim",
            )
        )
    view = scheduler.queue_view(case_id="case-1", queue_name="planning-shadow", observed_at=BASE_TIME)
    assert [row["work_unit_id"] for row in view["entries"]] == ["wu-high", "wu-low"]
    assert view["counts"] == {"queued": 1, "leased": 1, "lease_expired": 0, "retryable_failed": 0, "cancelled": 0, "terminal": 0}


def test_scheduler_concurrent_targeted_claim_has_one_winner_and_one_fenced_loser(tmp_path) -> None:
    scheduler = _scheduler(tmp_path)
    _enqueue(scheduler, "wu-race")

    def claim(worker_ref: str) -> str:
        try:
            scheduler.claim_next(
                _command(
                    "SCHEDULER_CLAIM_NEXT",
                    {"queue_name": "planning-shadow", "work_unit_id": "wu-race", "worker_ref": worker_ref},
                    idem=f"claim-race-{worker_ref}",
                )
            )
            return "claimed"
        except LeaseValidationError as exc:
            assert "scheduler_lease_already_active" in str(exc)
            return "fenced"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(claim, ("worker-a", "worker-b"))) == ["claimed", "fenced"]
    attempts = [row for row in scheduler.facade.store.list_latest("canonical_attempts", case_id="case-1") if row["work_unit_id"] == "wu-race"]
    assert len(attempts) == 1


def test_scheduler_heartbeat_renews_only_current_fenced_owner(tmp_path) -> None:
    scheduler = _scheduler(tmp_path)
    _enqueue(scheduler, "wu-heartbeat")
    scheduler.claim_next(
        _command(
            "SCHEDULER_CLAIM_NEXT",
            {"queue_name": "planning-shadow", "worker_ref": "worker-a", "attempt_id": "attempt-heartbeat", "lease_duration_seconds": 10},
            idem="claim-heartbeat",
        )
    )
    heartbeat_at = BASE_TIME + timedelta(seconds=5)
    result = scheduler.heartbeat(
        _command(
            "SCHEDULER_HEARTBEAT",
            {
                "work_unit_id": "wu-heartbeat",
                "attempt_id": "attempt-heartbeat",
                "worker_ref": "worker-a",
                "lease_fencing_token": 1,
                "lease_duration_seconds": 10,
            },
            expected=1,
            idem="heartbeat-current",
            at=heartbeat_at,
        )
    )
    assert (result.state_version_before, result.state_version_after) == (0, 1)
    attempt = scheduler.facade.store.get_latest("canonical_attempts", "attempt-heartbeat")
    assert datetime.fromisoformat(attempt["lease_expires_at"].replace("Z", "+00:00")) == heartbeat_at + timedelta(seconds=10)
    with pytest.raises(LeaseValidationError, match="lease_fencing_token_mismatch"):
        scheduler.heartbeat(
            _command(
                "SCHEDULER_HEARTBEAT",
                {
                    "work_unit_id": "wu-heartbeat",
                    "attempt_id": "attempt-heartbeat",
                    "worker_ref": "worker-a",
                    "lease_fencing_token": 9,
                },
                expected=1,
                idem="heartbeat-stale-token",
                at=heartbeat_at + timedelta(seconds=1),
            )
        )


def test_scheduler_reclaims_expired_lease_and_rejects_stale_fencing_token(tmp_path) -> None:
    scheduler = _scheduler(tmp_path)
    _enqueue(scheduler, "wu-reclaim")
    scheduler.claim_next(
        _command(
            "SCHEDULER_CLAIM_NEXT",
            {"queue_name": "planning-shadow", "worker_ref": "worker-a", "attempt_id": "attempt-reclaim", "lease_duration_seconds": 2},
            idem="claim-reclaim",
        )
    )
    reclaimed_at = BASE_TIME + timedelta(seconds=3)
    reclaim = scheduler.reclaim_expired(
        _command(
            "SCHEDULER_RECLAIM_EXPIRED_LEASE",
            {"work_unit_id": "wu-reclaim", "attempt_id": "attempt-reclaim", "worker_ref": "worker-b", "lease_duration_seconds": 20},
            expected=1,
            idem="reclaim",
            at=reclaimed_at,
        )
    )
    assert (reclaim.state_version_before, reclaim.state_version_after) == (1, 2)
    attempt = scheduler.facade.store.get_latest("canonical_attempts", "attempt-reclaim")
    assert attempt["lease_owner_ref"] == "worker-b"
    assert attempt["lease_fencing_token"] == 2
    assert len(scheduler.facade.store.list_versions("canonical_attempts", case_id="case-1")) == 2
    with pytest.raises(LeaseValidationError, match="lease_fencing_token_mismatch"):
        scheduler.facade.complete_attempt(
            _command(
                "COMPLETE_ATTEMPT",
                {"work_unit_id": "wu-reclaim", "attempt_id": "attempt-reclaim", "worker_ref": "worker-b", "lease_fencing_token": 1},
                expected=2,
                idem="stale-complete",
                at=reclaimed_at + timedelta(seconds=1),
            )
        )
    scheduler.facade.complete_attempt(
        _command(
            "COMPLETE_ATTEMPT",
            {"work_unit_id": "wu-reclaim", "attempt_id": "attempt-reclaim", "worker_ref": "worker-b", "lease_fencing_token": 2},
            expected=2,
            idem="current-complete",
            at=reclaimed_at + timedelta(seconds=1),
        )
    )
    assert scheduler.facade.store.get_latest("canonical_work_units", "wu-reclaim")["state"] == "succeeded"


def test_scheduler_cancellation_reaches_queued_and_active_work(tmp_path) -> None:
    scheduler = _scheduler(tmp_path)
    _enqueue(scheduler, "wu-queued")
    scheduler.cancel(_command("CANCEL_WORK_UNIT", {"work_unit_id": "wu-queued"}, idem="cancel-queued"))
    assert scheduler.facade.store.get_latest("canonical_work_units", "wu-queued")["state"] == "cancelled"
    assert not [row for row in scheduler.facade.store.list_latest("canonical_attempts", case_id="case-1") if row["work_unit_id"] == "wu-queued"]

    _enqueue(scheduler, "wu-active")
    scheduler.claim_next(
        _command(
            "SCHEDULER_CLAIM_NEXT",
            {"queue_name": "planning-shadow", "work_unit_id": "wu-active", "worker_ref": "worker-a", "attempt_id": "attempt-active"},
            idem="claim-active",
        )
    )
    scheduler.cancel(_command("CANCEL_WORK_UNIT", {"work_unit_id": "wu-active"}, expected=1, idem="cancel-active"))
    assert scheduler.facade.store.get_latest("canonical_attempts", "attempt-active")["state"] == "cancelled"
    view = scheduler.queue_view(case_id="case-1", queue_name="planning-shadow", observed_at=BASE_TIME)
    assert view["counts"]["cancelled"] == 2


def test_scheduler_queue_view_exposes_worker_loss_and_replay_is_deterministic(tmp_path) -> None:
    scheduler = _scheduler(tmp_path)
    _enqueue(scheduler, "wu-worker-loss")
    scheduler.claim_next(
        _command(
            "SCHEDULER_CLAIM_NEXT",
            {"queue_name": "planning-shadow", "worker_ref": "worker-a", "attempt_id": "attempt-worker-loss", "lease_duration_seconds": 1},
            idem="claim-worker-loss",
        )
    )
    view = scheduler.queue_view(
        case_id="case-1", queue_name="planning-shadow", observed_at=BASE_TIME + timedelta(seconds=2)
    )
    assert view["counts"]["lease_expired"] == 1
    scheduler.reclaim_expired(
        _command(
            "SCHEDULER_RECLAIM_EXPIRED_LEASE",
            {"work_unit_id": "wu-worker-loss", "attempt_id": "attempt-worker-loss", "worker_ref": "worker-b"},
            expected=1,
            idem="reclaim-worker-loss",
            at=BASE_TIME + timedelta(seconds=2),
        )
    )
    replay = scheduler.facade.replay_projection()
    assert replay == scheduler.facade.replay_projection()
    assert replay["attempts"]["attempt-worker-loss"]["lease_fencing_token"] == 2
