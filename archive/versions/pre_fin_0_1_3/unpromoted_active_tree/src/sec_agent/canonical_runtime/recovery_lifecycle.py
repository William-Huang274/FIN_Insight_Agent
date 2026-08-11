from __future__ import annotations

from typing import Any, Mapping

from .durable_scheduler import DurableSchedulerService
from .facade import IllegalStateTransition, MissingDependency, RuntimeFacade
from .models import AttemptState, CommandEnvelope, ResultEnvelope, WorkUnitState, canonical_digest


class RecoveryLifecycleService:
    """M5.2 recovery control plane composed over the M5.1 scheduler.

    The service is deliberately deterministic and store-backed.  It does not
    create checkpoint content (M5.3), execute a worker, invoke a model/provider
    or change legacy/business-case authority.
    """

    def __init__(self, facade: RuntimeFacade, *, scheduler: DurableSchedulerService | None = None):
        self.facade = facade
        self.scheduler = scheduler or DurableSchedulerService(facade)

    def build_replay_plan(self, *, case_id: str, work_unit_id: str) -> dict[str, Any]:
        """Return a digestible, read-only reconstruction plan for one WorkUnit."""
        work_unit = self.facade.store.get_latest("canonical_work_units", work_unit_id)
        if not work_unit or work_unit.get("case_id") != case_id:
            raise MissingDependency("recovery_work_unit_not_found", details={"case_id": case_id, "work_unit_id": work_unit_id})
        attempts = sorted(
            (
                row
                for row in self.facade.store.list_latest("canonical_attempts", case_id=case_id)
                if row.get("work_unit_id") == work_unit_id
            ),
            key=lambda row: (int(row.get("attempt_no") or 0), str(row.get("attempt_id") or "")),
        )
        related_ids = {str(row["attempt_id"]) for row in attempts}
        events = [
            {
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "sequence_no": event["sequence_no"],
                "attempt_id": event.get("attempt_id"),
                "payload_digest": event["payload_digest"],
            }
            for event in self.facade.store.list_events()
            if event.get("work_unit_id") == work_unit_id or event.get("attempt_id") in related_ids
        ]
        state = str(work_unit.get("state") or "")
        next_action = {
            WorkUnitState.RETRYABLE_FAILED.value: "retry_or_resume",
            WorkUnitState.FAILED.value: "inspect_or_dead_letter",
            WorkUnitState.DEAD_LETTERED.value: "terminal_inspection_only",
            WorkUnitState.PENDING.value: "claim_or_cancel",
            WorkUnitState.RUNNING.value: "wait_or_reclaim_lease",
            WorkUnitState.PAUSED.value: "await_hitl_approval",
            WorkUnitState.SUCCEEDED.value: "terminal_inspection_only",
            WorkUnitState.CANCELLED.value: "terminal_inspection_only",
        }.get(state, "fail_closed_unknown_state")
        plan = {
            "plan_version": "finsight_point01_m5_2_replay_plan_v1_0",
            "scope": "Point01_M5_2_recovery_lifecycle_control_plane_only",
            "case_id": case_id,
            "work_unit_id": work_unit_id,
            "work_unit_state": state,
            "work_unit_state_version": int(work_unit.get("state_version") or 0),
            "input_head_digest": work_unit.get("input_head_digest"),
            "attempts": [
                {
                    "attempt_id": row["attempt_id"],
                    "attempt_no": row["attempt_no"],
                    "state": row["state"],
                    "failure_type": row.get("failure_type"),
                    "retryable": row.get("retryable"),
                    "input_head_digest": row.get("input_head_digest"),
                    "recovery_mode": row.get("recovery_mode"),
                    "recovery_parent_attempt_id": row.get("recovery_parent_attempt_id"),
                    "resume_checkpoint_ref": row.get("resume_checkpoint_ref"),
                }
                for row in attempts
            ],
            "event_trace": events,
            "next_action": next_action,
            "worker_started": False,
            "model_call_count": 0,
            "external_call_count": 0,
        }
        return {**plan, "replay_plan_digest": canonical_digest(plan)}

    def retry(self, command: CommandEnvelope) -> ResultEnvelope:
        return self._schedule_recovery(command, recovery_mode="retry")

    def resume(self, command: CommandEnvelope) -> ResultEnvelope:
        if not str(command.payload.get("resume_checkpoint_ref") or ""):
            raise MissingDependency("recovery_checkpoint_ref_required")
        return self._schedule_recovery(command, recovery_mode="resume")

    def fork(self, command: CommandEnvelope) -> ResultEnvelope:
        return self.facade.fork_recovery_work_unit(command)

    def dead_letter(self, command: CommandEnvelope) -> ResultEnvelope:
        return self.facade.dead_letter_work_unit(command)

    def dead_letter_view(self, *, case_id: str) -> dict[str, Any]:
        records = [
            {
                "work_unit_id": row["work_unit_id"],
                "state_version": row["state_version"],
                "dead_letter_reason": row.get("dead_letter_reason"),
                "dead_lettered_at": row.get("dead_lettered_at"),
                "forked_from_work_unit_id": row.get("forked_from_work_unit_id"),
                "forked_from_attempt_id": row.get("forked_from_attempt_id"),
                "recovery_checkpoint_ref": row.get("recovery_checkpoint_ref"),
            }
            for row in self.facade.store.list_latest("canonical_work_units", case_id=case_id)
            if row.get("state") == WorkUnitState.DEAD_LETTERED.value
        ]
        records.sort(key=lambda row: (str(row.get("dead_lettered_at") or ""), row["work_unit_id"]))
        return {
            "scope": "Point01_M5_2_recovery_lifecycle_control_plane_only",
            "case_id": case_id,
            "dead_letter_count": len(records),
            "records": records,
            "worker_started": False,
            "model_call_count": 0,
            "external_call_count": 0,
        }

    def _schedule_recovery(self, command: CommandEnvelope, *, recovery_mode: str) -> ResultEnvelope:
        case_id = str(command.case_id or "")
        work_unit_id = str(command.payload.get("work_unit_id") or "")
        if not case_id or not work_unit_id:
            raise MissingDependency("recovery_case_and_work_unit_required")
        plan = self.build_replay_plan(case_id=case_id, work_unit_id=work_unit_id)
        if plan["work_unit_state"] != WorkUnitState.RETRYABLE_FAILED.value:
            raise IllegalStateTransition("recovery_requires_retryable_failed_work_unit")
        if int(plan["work_unit_state_version"]) != command.expected_state_version:
            raise IllegalStateTransition("recovery_plan_state_version_mismatch")
        failed = [row for row in plan["attempts"] if row["state"] == AttemptState.FAILED.value]
        if not failed:
            raise MissingDependency("recovery_failed_parent_attempt_not_found")
        parent_attempt_id = str(failed[-1]["attempt_id"])
        payload: dict[str, Any] = {
            **dict(command.payload),
            "recovery_mode": recovery_mode,
            "recovery_parent_attempt_id": parent_attempt_id,
            "replay_plan_digest": plan["replay_plan_digest"],
        }
        if recovery_mode == "retry":
            payload.pop("resume_checkpoint_ref", None)
        recovered_command = command.model_copy(update={"payload": payload})
        return self.scheduler.claim_next(recovered_command)
