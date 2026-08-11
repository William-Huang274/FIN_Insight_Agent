from __future__ import annotations

from typing import Any

from pydantic import Field

from .facade import RuntimeFacade
from .models import CommandEnvelope, ResultEnvelope, StrictModel, canonical_digest


class BudgetPolicy(StrictModel):
    policy_id: str
    case_token_units: int = Field(ge=0)
    work_unit_token_units: int = Field(ge=0)
    attempt_token_units: int = Field(ge=0)
    case_tool_calls: int = Field(ge=0)
    work_unit_tool_calls: int = Field(ge=0)
    attempt_tool_calls: int = Field(ge=0)
    case_time_seconds: int = Field(ge=0)
    work_unit_time_seconds: int = Field(ge=0)
    attempt_time_seconds: int = Field(ge=0)


class BudgetReservationRequest(StrictModel):
    reservation_id: str
    work_unit_id: str
    attempt_id: str
    token_units: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    time_seconds: int = Field(ge=0)
    is_fallback: bool = False


class BudgetLedgerEntry(StrictModel):
    entry_id: str
    reservation_id: str
    action: str
    work_unit_id: str
    attempt_id: str
    token_units: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    time_seconds: int = Field(ge=0)
    reason: str | None = None


class BudgetStop(StrictModel):
    stop_id: str
    code: str
    work_unit_id: str
    attempt_id: str
    exhausted_scope: str
    requested_digest: str


class BudgetExceededError(RuntimeError):
    def __init__(self, stop: BudgetStop):
        self.stop = stop
        super().__init__(stop.code)


class BudgetControlService:
    """M5.5 deterministic hierarchical reservation/refund/typed-stop control plane."""

    def __init__(self, facade: RuntimeFacade, *, policy: BudgetPolicy):
        self.facade = facade
        self.policy = policy

    def reserve(self, request: BudgetReservationRequest) -> BudgetLedgerEntry:
        return self._reserve(request)

    def begin_checkpoint_operation(
        self,
        command: CommandEnvelope,
        reservation: BudgetReservationRequest,
    ) -> BudgetLedgerEntry:
        """Persist a recoverable checkpoint reservation before an external restart.

        The normal caller uses :meth:`execute_checkpoint_write`, which consumes
        this reservation in the checkpoint transaction.  This explicit entry
        point exists for recovery orchestration: after a process failure,
        ``reconcile_pending_operation`` resolves the durable intent from the
        actual canonical artifact rather than an in-memory callback.
        """
        return self._reserve(reservation, checkpoint_command=command)

    def _reserve(
        self,
        request: BudgetReservationRequest,
        *,
        checkpoint_command: CommandEnvelope | None = None,
    ) -> BudgetLedgerEntry:
        requested = (request.token_units, request.tool_calls, request.time_seconds)
        if not any(requested):
            raise ValueError("budget_reservation_must_request_resource")
        checkpoint_id: str | None = None
        if checkpoint_command is not None:
            checkpoint_id = self._validate_checkpoint_operation_command(checkpoint_command, request)
        terminal_stop: BudgetStop | None = None
        entry: BudgetLedgerEntry | None = None
        with self.facade.store.transaction() as tx:
            scope = self._scope(tx, request)
            if tx.get_latest("canonical_budget_reservation_versions", request.reservation_id):
                raise ValueError("budget_reservation_id_already_exists")
            exhausted = self._first_exhausted_scope(tx, request, case_id=str(scope["case_id"]))
            if exhausted:
                stop_digest = canonical_digest({"request": request, "scope": exhausted})
                stop = BudgetStop(stop_id=f"budget_stop_{stop_digest[:24]}", code="budget_exhausted", work_unit_id=request.work_unit_id, attempt_id=request.attempt_id, exhausted_scope=exhausted, requested_digest=canonical_digest(request))
                if not tx.get_latest("canonical_budget_stop_versions", stop.stop_id):
                    stop_row = {**scope, **stop.model_dump(mode="json"), "state_version": 1, "current_status": "budget_exhausted"}
                    tx.insert("canonical_budget_stop_versions", stop.stop_id, 1, self._with_content_digest(stop_row))
                    self._append_entry(tx, scope, request, "terminal_stop", reason=f"budget_exhausted:{exhausted}")
                terminal_stop = stop
            else:
                row = {**scope, "reservation_id": request.reservation_id, "reservation_version": 1, "state_version": 1, "request": request.model_dump(mode="json"), "remaining_token_units": request.token_units, "remaining_tool_calls": request.tool_calls, "remaining_time_seconds": request.time_seconds, "reservation_state": "reserved", "protected_operation_state": "checkpoint_pending" if checkpoint_command is not None else "reserved", "checkpoint_id": checkpoint_id, "checkpoint_command_digest": canonical_digest(checkpoint_command) if checkpoint_command is not None else None, "checkpoint_ref": None, "current_status": "checkpoint_pending" if checkpoint_command is not None else "reserved"}
                tx.insert("canonical_budget_reservation_versions", request.reservation_id, 1, self._with_content_digest(row))
                entry = self._append_entry(tx, scope, request, "reserved", reason="fallback" if request.is_fallback else "primary")
        if terminal_stop:
            # The audit record must be durable before the typed stop reaches the caller.
            raise BudgetExceededError(terminal_stop)
        if entry is None:  # pragma: no cover - defensive invariant.
            raise RuntimeError("budget_reservation_entry_missing")
        return entry

    def refund(
        self,
        reservation_id: str,
        *,
        token_units: int = 0,
        tool_calls: int = 0,
        time_seconds: int = 0,
        reason: str = "unused_reservation",
    ) -> BudgetLedgerEntry:
        if any(value < 0 for value in (token_units, tool_calls, time_seconds)):
            raise ValueError("budget_refund_must_be_nonnegative")
        with self.facade.store.transaction() as tx:
            reservation = tx.get_latest("canonical_budget_reservation_versions", reservation_id)
            if not reservation:
                raise ValueError("budget_reservation_not_found")
            if reservation.get("reservation_state") != "reserved":
                raise ValueError("budget_reservation_not_refundable")
            if reservation.get("protected_operation_state") == "checkpoint_pending":
                raise ValueError("budget_reservation_checkpoint_operation_pending")
            if token_units > reservation["remaining_token_units"] or tool_calls > reservation["remaining_tool_calls"] or time_seconds > reservation["remaining_time_seconds"]:
                raise ValueError("budget_refund_exceeds_remaining_reservation")
            request = BudgetReservationRequest.model_validate(reservation["request"])
            remaining = (int(reservation["remaining_token_units"]) - token_units, int(reservation["remaining_tool_calls"]) - tool_calls, int(reservation["remaining_time_seconds"]) - time_seconds)
            updated = {**reservation, "state_version": int(reservation["state_version"]) + 1, "remaining_token_units": remaining[0], "remaining_tool_calls": remaining[1], "remaining_time_seconds": remaining[2], "reservation_state": "released" if not any(remaining) else "reserved", "current_status": "released" if not any(remaining) else "reserved"}
            tx.insert("canonical_budget_reservation_versions", reservation_id, int(reservation["reservation_version"]), self._with_content_digest(updated))
            return self._append_entry(tx, self._scope(tx, request), request, "refunded", token_units=token_units, tool_calls=tool_calls, time_seconds=time_seconds, reason=reason)

    def consume(self, reservation_id: str, *, reason: str) -> BudgetLedgerEntry:
        """Durably consume a non-checkpoint reservation exactly once.

        External operations cannot share an ACID transaction with a network
        request.  Their executor therefore reserves before send and consumes
        after any send attempt, including an outcome whose remote effect is
        unknown.  Checkpoint operations retain their stricter dedicated path.
        """
        if not reason.strip():
            raise ValueError("budget_consume_reason_required")
        with self.facade.store.transaction() as tx:
            reservation = tx.get_latest("canonical_budget_reservation_versions", reservation_id)
            if not reservation:
                raise ValueError("budget_reservation_not_found")
            if reservation.get("reservation_state") != "reserved":
                raise ValueError("budget_reservation_not_consumable")
            if reservation.get("protected_operation_state") == "checkpoint_pending":
                raise ValueError("budget_reservation_checkpoint_operation_pending")
            request = BudgetReservationRequest.model_validate(reservation["request"])
            updated = {
                **reservation,
                "state_version": int(reservation["state_version"]) + 1,
                "reservation_state": "consumed",
                "protected_operation_state": "consumed_external_operation",
                "current_status": "consumed",
            }
            tx.insert(
                "canonical_budget_reservation_versions",
                reservation_id,
                int(reservation["reservation_version"]),
                self._with_content_digest(updated),
            )
            return self._append_entry(tx, self._scope(tx, request), request, "consumed", reason=reason)

    def execute_checkpoint_write(self, command: CommandEnvelope, reservation: BudgetReservationRequest) -> ResultEnvelope:
        self._reserve(reservation, checkpoint_command=command)
        try:
            result = self.facade.create_checkpoint_version(
                command,
                checkpoint_mutation_finalizer=lambda tx, checkpoint_ref: self._consume_checkpoint_operation(
                    tx, reservation, checkpoint_ref
                ),
            )
        except Exception:
            self.reconcile_pending_operation(reservation.reservation_id)
            raise
        return result

    def reconcile_pending_operation(self, reservation_id: str) -> str:
        """Close a crash-interrupted checkpoint reservation from durable store facts.

        A committed canonical checkpoint consumes the reservation.  No committed
        checkpoint means the pending reservation is released exactly once.  This
        also handles a hard process exit after reservation commit but before the
        checkpoint transaction begins.
        """
        with self.facade.store.transaction() as tx:
            state = tx.get_latest("canonical_budget_reservation_versions", reservation_id)
            if not state:
                raise ValueError("budget_reservation_not_found")
            operation_state = str(state.get("protected_operation_state") or "")
            if operation_state != "checkpoint_pending":
                return operation_state or str(state.get("reservation_state") or "unknown")
            request = BudgetReservationRequest.model_validate(state["request"])
            checkpoint_id = str(state.get("checkpoint_id") or "")
            artifact = tx.get_latest("canonical_artifact_versions", checkpoint_id) if checkpoint_id else None
            scope = self._scope(tx, request)
            if artifact and artifact.get("artifact_type") == "runtime_checkpoint" and artifact.get("case_id") == state.get("case_id") and artifact.get("producer_attempt_id") == request.attempt_id:
                checkpoint_ref = str(artifact["artifact_version_id"])
                self._consume_checkpoint_operation(tx, request, checkpoint_ref, recovery=True)
                return "reconciled_consumed"
            released = {
                **state,
                "state_version": int(state["state_version"]) + 1,
                "remaining_token_units": 0,
                "remaining_tool_calls": 0,
                "remaining_time_seconds": 0,
                "reservation_state": "released",
                "protected_operation_state": "reconciled_released",
                "current_status": "reconciled_released",
            }
            tx.insert("canonical_budget_reservation_versions", reservation_id, int(state["reservation_version"]), self._with_content_digest(released))
            self._append_entry(
                tx,
                scope,
                request,
                "reconciled_refund",
                token_units=int(state["remaining_token_units"]),
                tool_calls=int(state["remaining_tool_calls"]),
                time_seconds=int(state["remaining_time_seconds"]),
                reason="checkpoint_operation_not_committed",
            )
            return "reconciled_released"

    def apply_terminal_stop(self, command: CommandEnvelope, error: BudgetExceededError) -> ResultEnvelope:
        stop = error.stop
        if str(command.payload.get("work_unit_id") or "") != stop.work_unit_id or str(command.payload.get("attempt_id") or "") != stop.attempt_id:
            raise ValueError("budget_stop_execution_scope_mismatch")
        failure_command = command.model_copy(
            update={
                "command_type": "FAIL_ATTEMPT",
                "payload": {
                    **command.payload,
                    "failure_type": "budget_exhausted",
                    "retryable": False,
                    "terminal_reason": f"budget_exhausted:{stop.exhausted_scope}",
                },
            }
        )
        return self.facade.fail_attempt(failure_command)

    def ledger_view(self) -> dict[str, Any]:
        return {
            "scope": "Point01_M5_5_budget_stop_control_plane_only",
            "policy_id": self.policy.policy_id,
            "ledger": [{key: row[key] for key in BudgetLedgerEntry.model_fields} for row in self.facade.store.list_versions("canonical_budget_ledger_versions")],
            "stops": [{key: row[key] for key in BudgetStop.model_fields} for row in self.facade.store.list_versions("canonical_budget_stop_versions")],
            "slo_observation": {
                "reserved_count": sum(1 for entry in self.facade.store.list_versions("canonical_budget_ledger_versions") if entry["action"] == "reserved"),
                "consumed_count": sum(1 for entry in self.facade.store.list_versions("canonical_budget_ledger_versions") if entry["action"] == "consumed"),
                "refund_count": sum(1 for entry in self.facade.store.list_versions("canonical_budget_ledger_versions") if entry["action"] == "refunded"),
                "terminal_stop_count": len(self.facade.store.list_versions("canonical_budget_stop_versions")),
                "provider_execution_count": 0,
                "external_tool_execution_count": 0,
            },
        }

    def _first_exhausted_scope(self, tx: Any, request: BudgetReservationRequest, *, case_id: str) -> str | None:
        dimensions = (
            ("token_units", request.token_units, self.policy.case_token_units, self.policy.work_unit_token_units, self.policy.attempt_token_units),
            ("tool_calls", request.tool_calls, self.policy.case_tool_calls, self.policy.work_unit_tool_calls, self.policy.attempt_tool_calls),
            ("time_seconds", request.time_seconds, self.policy.case_time_seconds, self.policy.work_unit_time_seconds, self.policy.attempt_time_seconds),
        )
        for dimension, requested, case_limit, work_unit_limit, attempt_limit in dimensions:
            if self._used(tx, dimension, case_id=case_id) + requested > case_limit:
                return f"case:{dimension}"
            if self._used(tx, dimension, case_id=case_id, work_unit_id=request.work_unit_id) + requested > work_unit_limit:
                return f"work_unit:{dimension}"
            if self._used(tx, dimension, case_id=case_id, work_unit_id=request.work_unit_id, attempt_id=request.attempt_id) + requested > attempt_limit:
                return f"attempt:{dimension}"
        return None

    def _used(self, tx: Any, dimension: str, *, case_id: str, work_unit_id: str | None = None, attempt_id: str | None = None) -> int:
        remaining_key = f"remaining_{dimension}"
        total = 0
        for reservation in tx.list_latest("canonical_budget_reservation_versions"):
            request = BudgetReservationRequest.model_validate(reservation["request"])
            if reservation.get("case_id") != case_id:
                continue
            if reservation["reservation_state"] == "released":
                continue
            if work_unit_id is not None and request.work_unit_id != work_unit_id:
                continue
            if attempt_id is not None and request.attempt_id != attempt_id:
                continue
            total += int(reservation[remaining_key])
        return total

    def _append_entry(self, tx: Any, scope: dict[str, Any], request: BudgetReservationRequest, action: str, *, token_units: int | None = None, tool_calls: int | None = None, time_seconds: int | None = None, reason: str | None = None) -> BudgetLedgerEntry:
        entry_digest = canonical_digest({"reservation_id": request.reservation_id, "action": action, "count": len(tx.list_latest("canonical_budget_ledger_versions")), "reason": reason})
        entry = BudgetLedgerEntry(
            entry_id=f"budget_{entry_digest[:24]}",
            reservation_id=request.reservation_id,
            action=action,
            work_unit_id=request.work_unit_id,
            attempt_id=request.attempt_id,
            token_units=request.token_units if token_units is None else token_units,
            tool_calls=request.tool_calls if tool_calls is None else tool_calls,
            time_seconds=request.time_seconds if time_seconds is None else time_seconds,
            reason=reason,
        )
        row = {**scope, **entry.model_dump(mode="json"), "state_version": 1, "current_status": action}
        tx.insert("canonical_budget_ledger_versions", entry.entry_id, 1, self._with_content_digest(row))
        return entry

    def _consume_checkpoint_operation(
        self,
        tx: Any,
        request: BudgetReservationRequest,
        checkpoint_ref: str,
        *,
        recovery: bool = False,
    ) -> None:
        state = tx.get_latest("canonical_budget_reservation_versions", request.reservation_id)
        if not state:
            raise ValueError("budget_reservation_not_found")
        if state.get("reservation_state") != "reserved" or state.get("protected_operation_state") != "checkpoint_pending":
            raise ValueError("budget_reservation_checkpoint_operation_not_pending")
        if str(state.get("checkpoint_id") or "") != checkpoint_ref.split(":v", 1)[0]:
            raise ValueError("budget_reservation_checkpoint_identity_mismatch")
        updated = {
            **state,
            "state_version": int(state["state_version"]) + 1,
            "reservation_state": "consumed",
            "protected_operation_state": "reconciled_consumed" if recovery else "consumed",
            "checkpoint_ref": checkpoint_ref,
            "current_status": "reconciled_consumed" if recovery else "consumed",
        }
        tx.insert("canonical_budget_reservation_versions", request.reservation_id, int(state["reservation_version"]), self._with_content_digest(updated))
        self._append_entry(tx, self._scope(tx, request), request, "reconciled_consumed" if recovery else "consumed", reason="checkpoint.write")

    @staticmethod
    def _validate_checkpoint_operation_command(command: CommandEnvelope, request: BudgetReservationRequest) -> str:
        if str(command.payload.get("work_unit_id") or "") != request.work_unit_id or str(command.payload.get("attempt_id") or "") != request.attempt_id:
            raise ValueError("budget_checkpoint_operation_execution_scope_mismatch")
        checkpoint_id = str(command.payload.get("checkpoint_id") or "")
        if not checkpoint_id:
            raise ValueError("budget_checkpoint_operation_checkpoint_id_required")
        return checkpoint_id

    def _scope(self, tx: Any, request: BudgetReservationRequest) -> dict[str, Any]:
        work_unit = tx.get_latest("canonical_work_units", request.work_unit_id)
        attempt = tx.get_latest("canonical_attempts", request.attempt_id)
        if not work_unit or not attempt or attempt.get("work_unit_id") != request.work_unit_id:
            raise ValueError("budget_reservation_execution_not_found")
        return {"tenant_id": work_unit["tenant_id"], "project_id": work_unit["project_id"], "case_id": work_unit["case_id"], "actor_snapshot_ref": work_unit["actor_snapshot_ref"], "permission_snapshot_ref": work_unit["permission_snapshot_ref"], "policy_config_refs": tuple(work_unit.get("policy_config_refs") or ()), "correlation_id": work_unit["correlation_id"]}

    def _reservation_state(self, reservation_id: str) -> dict[str, Any]:
        row = self.facade.store.get_latest("canonical_budget_reservation_versions", reservation_id)
        if not row:
            raise ValueError("budget_reservation_not_found")
        return row

    @staticmethod
    def _with_content_digest(row: dict[str, Any]) -> dict[str, Any]:
        return {**row, "content_digest": canonical_digest({key: value for key, value in row.items() if key != "content_digest"})}


BUDGET_CONTROL_MODELS = (BudgetPolicy, BudgetReservationRequest, BudgetLedgerEntry, BudgetStop)
