from __future__ import annotations

from datetime import datetime
from typing import Any

from .facade import RuntimeFacade
from .models import CommandEnvelope, ResultEnvelope, utc_now


class DurableSchedulerService:
    """M5.1 deterministic scheduler control plane; it never starts a worker process or provider call."""

    def __init__(self, facade: RuntimeFacade):
        self.facade = facade

    def enqueue(self, command: CommandEnvelope) -> ResultEnvelope:
        """Create a queue-addressable WorkUnit through the canonical append-only facade."""
        return self.facade.create_work_unit(command)

    def claim_next(self, command: CommandEnvelope) -> ResultEnvelope:
        return self.facade.claim_next_scheduled_attempt(command)

    def heartbeat(self, command: CommandEnvelope) -> ResultEnvelope:
        return self.facade.heartbeat_scheduled_attempt_lease(command)

    def reclaim_expired(self, command: CommandEnvelope) -> ResultEnvelope:
        return self.facade.reclaim_expired_scheduled_attempt_lease(command)

    def cancel(self, command: CommandEnvelope) -> ResultEnvelope:
        return self.facade.cancel_work_unit(command)

    def queue_view(
        self,
        *,
        case_id: str,
        queue_name: str = "point01.default",
        observed_at: datetime | None = None,
    ) -> dict[str, Any]:
        now = observed_at or utc_now()
        work_units = [
            row
            for row in self.facade.store.list_latest("canonical_work_units", case_id=case_id)
            if row.get("queue_name", "point01.default") == queue_name
        ]
        attempts = {
            str(row["attempt_id"]): row
            for row in self.facade.store.list_latest("canonical_attempts", case_id=case_id)
            if row.get("scheduler_managed")
        }
        rows: list[dict[str, Any]] = []
        counts = {"queued": 0, "leased": 0, "lease_expired": 0, "retryable_failed": 0, "cancelled": 0, "terminal": 0}
        for work_unit in sorted(
            work_units,
            key=lambda row: (-int(row.get("queue_priority") or 0), str(row.get("queued_at") or row.get("created_at") or ""), str(row["work_unit_id"])),
        ):
            related = [row for row in attempts.values() if row.get("work_unit_id") == work_unit.get("work_unit_id")]
            active = next((row for row in related if row.get("state") == "running"), None)
            work_unit_state = str(work_unit.get("state") or "")
            if work_unit_state == "pending":
                scheduler_state = "queued"
            elif work_unit_state == "retryable_failed":
                scheduler_state = "retryable_failed"
            elif work_unit_state == "cancelled":
                scheduler_state = "cancelled"
            elif work_unit_state in {"succeeded", "failed", "dead_lettered"}:
                scheduler_state = "terminal"
            elif active:
                expires_at = self._as_datetime(active.get("lease_expires_at"))
                scheduler_state = "lease_expired" if expires_at and expires_at <= now else "leased"
            else:
                scheduler_state = "leased"
            counts[scheduler_state] += 1
            rows.append(
                {
                    "work_unit_id": work_unit["work_unit_id"],
                    "queue_priority": int(work_unit.get("queue_priority") or 0),
                    "work_unit_state": work_unit_state,
                    "scheduler_state": scheduler_state,
                    "attempt_id": active.get("attempt_id") if active else None,
                    "lease_owner_ref": active.get("lease_owner_ref") if active else None,
                    "lease_fencing_token": active.get("lease_fencing_token") if active else None,
                    "lease_expires_at": active.get("lease_expires_at") if active else None,
                }
            )
        return {
            "scope": "M5.1_durable_scheduler_control_plane_only",
            "case_id": case_id,
            "queue_name": queue_name,
            "observed_at": now.isoformat(),
            "counts": counts,
            "entries": rows,
            "worker_started": False,
            "model_call_count": 0,
            "external_call_count": 0,
        }

    @staticmethod
    def _as_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if value is None:
            return None
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
