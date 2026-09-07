"""Canonical recovery bridge for an ambiguous Agent Server run create.

This module deliberately does not implement a workflow engine or a retry
service.  It only constructs and validates the existing canonical v1.2
``ActionAttempt``, ``ResearchRun`` and ``RecoveryDisposition`` objects needed
at the one non-transactional boundary between FIN PostgreSQL and Agent Server.
The PostgreSQL adapter persists those immutable snapshots; an independent
operator authority may append a disposition, while the runtime is read-only
for that decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Literal
from uuid import UUID

from sec_agent.canonical_runtime.contracts_v1_2 import (
    ActionAttempt,
    RecoveryDisposition,
    ResearchRun,
    RunInvocation,
    canonical_json_sha256,
    create_action_attempt,
    create_research_run,
    create_run_invocation,
    validate_recovery_disposition_v1_2,
)


RUN_CREATE_ACTOR_ID = "runtime://fin-agent-server-client"
RUN_CREATE_ACTION_NAME = "langgraph_agent_server.runs.create"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_SERVER_RUN_STATUSES = frozenset(
    {"pending", "running", "error", "success", "timeout", "interrupted"}
)
SUPPORTED_RUNTIME_RECOVERY_DECISIONS = frozenset(
    {"DO_NOT_RETRY", "ABANDON_RUN"}
)


class DellAgentServerRecoveryError(RuntimeError):
    """Secret-free, machine-readable canonical recovery failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DellAgentServerRecoveryCase:
    """One immutable owner-visible request for a recovery decision."""

    recovery_case_id: str
    research_run: ResearchRun
    source_invocation: RunInvocation
    ambiguous_action: ActionAttempt
    lifecycle_event_digest: str
    recovery_reason_code: str
    server_run_id: str | None
    server_run_status: str | None
    opened_at: datetime
    recovery_case_digest: str

    def __post_init__(self) -> None:
        try:
            rebuilt_run = ResearchRun.model_validate(
                self.research_run.model_dump(mode="python")
            )
            rebuilt_invocation = RunInvocation.model_validate(
                self.source_invocation.model_dump(mode="python")
            )
            rebuilt_action = ActionAttempt.model_validate(
                self.ambiguous_action.model_dump(mode="python")
            )
        except Exception:
            raise DellAgentServerRecoveryError(
                "recovery_case_canonical_snapshot_invalid"
            ) from None
        if (
            rebuilt_run != self.research_run
            or rebuilt_invocation != self.source_invocation
            or rebuilt_action != self.ambiguous_action
        ):
            raise DellAgentServerRecoveryError(
                "recovery_case_canonical_snapshot_invalid"
            )
        if (
            not self.recovery_case_id
            or self.recovery_case_id != self.recovery_case_id.strip()
            or len(self.recovery_case_id) > 240
        ):
            raise DellAgentServerRecoveryError("recovery_case_id_invalid")
        if self.research_run.status != "RECOVERY_REQUIRED":
            raise DellAgentServerRecoveryError("recovery_case_run_state_invalid")
        if (
            self.research_run.run_id != self.source_invocation.run_id
            or self.research_run.session_id != self.source_invocation.session_id
            or self.ambiguous_action.run_id != self.research_run.run_id
            or self.ambiguous_action.session_id != self.research_run.session_id
            or self.ambiguous_action.run_invocation_id
            != self.source_invocation.invocation_id
            or self.source_invocation.status != "INTERRUPTED"
            or self.source_invocation.finished_at is None
            or self.ambiguous_action.state != "TERMINAL"
            or self.ambiguous_action.outcome != "AMBIGUOUS_AFTER_DISPATCH"
        ):
            raise DellAgentServerRecoveryError("recovery_case_identity_invalid")
        if self.source_invocation.finished_at < self.ambiguous_action.terminal_at:
            raise DellAgentServerRecoveryError("recovery_case_time_invalid")
        if self.opened_at.tzinfo is None or self.opened_at.utcoffset() is None:
            raise DellAgentServerRecoveryError("recovery_case_time_invalid")
        if (
            self.ambiguous_action.terminal_at is None
            or self.opened_at < self.ambiguous_action.terminal_at
            or self.opened_at < self.source_invocation.finished_at
        ):
            raise DellAgentServerRecoveryError("recovery_case_time_invalid")
        if (
            not _SHA256_RE.fullmatch(self.lifecycle_event_digest)
            or not self.recovery_reason_code
            or self.recovery_reason_code != self.recovery_reason_code.strip()
            or len(self.recovery_reason_code) > 120
        ):
            raise DellAgentServerRecoveryError(
                "recovery_case_boundary_fields_invalid"
            )
        if self.server_run_id is not None:
            try:
                parsed_run_id = UUID(self.server_run_id)
            except (TypeError, ValueError, AttributeError):
                raise DellAgentServerRecoveryError(
                    "recovery_case_server_run_id_invalid"
                ) from None
            if str(parsed_run_id) != self.server_run_id.lower():
                raise DellAgentServerRecoveryError(
                    "recovery_case_server_run_id_invalid"
                )
        if self.server_run_status is not None and self.server_run_id is None:
            raise DellAgentServerRecoveryError(
                "recovery_case_remote_identity_incomplete"
            )
        if (
            self.server_run_status is not None
            and self.server_run_status not in _ALLOWED_SERVER_RUN_STATUSES
        ):
            raise DellAgentServerRecoveryError(
                "recovery_case_server_run_status_invalid"
            )
        if self.recovery_case_digest != recovery_case_digest(self):
            raise DellAgentServerRecoveryError("recovery_case_digest_invalid")


def run_create_action_attempt_id(invocation_id: str) -> str:
    if not isinstance(invocation_id, str) or not invocation_id.strip():
        raise DellAgentServerRecoveryError("run_create_invocation_id_invalid")
    return f"ACTION::AGENT_SERVER_RUN_CREATE::{invocation_id}"


def run_create_request_ref(invocation_id: str) -> str:
    if not isinstance(invocation_id, str) or not invocation_id.strip():
        raise DellAgentServerRecoveryError("run_create_invocation_id_invalid")
    return f"fin-runtime://agent-server/run-create/{invocation_id}"


def create_run_create_action_intent(
    *,
    research_run: ResearchRun,
    source_invocation: RunInvocation,
    launch_request_digest: str,
) -> ActionAttempt:
    """Create the canonical INTENT snapshot persisted with PENDING."""

    try:
        run = ResearchRun.model_validate(research_run.model_dump(mode="python"))
        invocation = RunInvocation.model_validate(
            source_invocation.model_dump(mode="python")
        )
    except Exception:
        raise DellAgentServerRecoveryError(
            "run_create_canonical_identity_invalid"
        ) from None
    if (
        invocation.session_id != run.session_id
        or invocation.run_id != run.run_id
        or (invocation.ordinal == 1) != (invocation.invocation_kind == "START")
    ):
        raise DellAgentServerRecoveryError(
            "run_create_canonical_lineage_invalid"
        )
    return create_action_attempt(
        action_attempt_id=run_create_action_attempt_id(
            invocation.invocation_id
        ),
        session_id=run.session_id,
        run_id=run.run_id,
        run_invocation_id=invocation.invocation_id,
        actor_id=RUN_CREATE_ACTOR_ID,
        action_kind="TOOL",
        action_name=RUN_CREATE_ACTION_NAME,
        request_ref=run_create_request_ref(invocation.invocation_id),
        request_digest=launch_request_digest,
        state="INTENT_COMMITTED",
        outcome=None,
        was_dispatched=False,
        potentially_chargeable=False,
        receipt_kind=None,
        receipt_ref=None,
        receipt_digest=None,
        failure_code=None,
        parent_action_attempt_id=None,
        created_at=invocation.started_at,
        terminal_at=None,
    )


def create_run_create_action_dispatched(intent: ActionAttempt) -> ActionAttempt:
    """Create the append-only DISPATCHED snapshot immediately before SDK I/O."""

    if intent.state != "INTENT_COMMITTED" or intent.was_dispatched:
        raise DellAgentServerRecoveryError("run_create_action_intent_invalid")
    return create_action_attempt(
        **{
            **intent.model_dump(
                exclude={"schema_version", "action_attempt_digest"}
            ),
            "state": "DISPATCHED",
            "was_dispatched": True,
            "potentially_chargeable": True,
        }
    )


def create_run_create_action_failed_before_dispatch(
    intent: ActionAttempt,
    *,
    terminal_at: datetime | None = None,
) -> ActionAttempt:
    """Close a durable intent when local dispatch can no longer occur."""

    if intent.state != "INTENT_COMMITTED" or intent.was_dispatched:
        raise DellAgentServerRecoveryError("run_create_action_intent_invalid")
    finished_at = terminal_at or datetime.now(timezone.utc)
    return create_action_attempt(
        **{
            **intent.model_dump(
                exclude={"schema_version", "action_attempt_digest"}
            ),
            "state": "TERMINAL",
            "outcome": "FAILED_BEFORE_DISPATCH",
            "was_dispatched": False,
            "potentially_chargeable": False,
            "receipt_kind": None,
            "receipt_ref": None,
            "receipt_digest": None,
            "failure_code": None,
            "terminal_at": finished_at,
        }
    )


def create_run_create_action_applied(
    dispatched: ActionAttempt,
    *,
    server_run_id: str,
    server_observation_digest: str,
    terminal_at: datetime | None = None,
) -> ActionAttempt:
    """Create the terminal APPLIED snapshot bound to the exact run receipt."""

    _require_dispatched(dispatched)
    finished_at = terminal_at or datetime.now(timezone.utc)
    return create_action_attempt(
        **{
            **dispatched.model_dump(
                exclude={"schema_version", "action_attempt_digest"}
            ),
            "state": "TERMINAL",
            "outcome": "APPLIED",
            "receipt_kind": "SUCCESS",
            "receipt_ref": f"agent-server://runs/{server_run_id}",
            "receipt_digest": server_observation_digest,
            "terminal_at": finished_at,
        }
    )


def create_run_create_action_ambiguous(
    dispatched: ActionAttempt,
    *,
    terminal_at: datetime | None = None,
) -> ActionAttempt:
    """Create a terminal ambiguous snapshot without inventing a receipt."""

    _require_dispatched(dispatched)
    finished_at = terminal_at or datetime.now(timezone.utc)
    return create_action_attempt(
        **{
            **dispatched.model_dump(
                exclude={"schema_version", "action_attempt_digest"}
            ),
            "state": "TERMINAL",
            "outcome": "AMBIGUOUS_AFTER_DISPATCH",
            "receipt_kind": None,
            "receipt_ref": None,
            "receipt_digest": None,
            "failure_code": None,
            "terminal_at": finished_at,
        }
    )


def create_recovery_required_research_run(run: ResearchRun) -> ResearchRun:
    """Create the canonical RECOVERY_REQUIRED snapshot for the same run."""

    return create_research_run(
        **{
            **run.model_dump(exclude={"schema_version", "run_digest"}),
            "status": "RECOVERY_REQUIRED",
            "terminal_at": None,
        }
    )


def create_interrupted_source_invocation(
    invocation: RunInvocation,
    *,
    finished_at: datetime,
) -> RunInvocation:
    """Project the source invocation to its immutable ambiguous terminal state."""

    return create_run_invocation(
        **{
            **invocation.model_dump(
                exclude={"schema_version", "invocation_digest"}
            ),
            "status": "INTERRUPTED",
            "finished_at": finished_at,
        }
    )


def create_recovery_case(
    *,
    recovery_run: ResearchRun,
    source_invocation: RunInvocation,
    ambiguous_action: ActionAttempt,
    lifecycle_event_digest: str,
    recovery_reason_code: str,
    server_run_id: str | None,
    server_run_status: str | None,
    opened_at: datetime | None = None,
) -> DellAgentServerRecoveryCase:
    actual_opened_at = opened_at or datetime.now(timezone.utc)
    unsigned = {
        "schema_version": "fin_ia_dell_agent_server_recovery_case_v1_0",
        "recovery_case_id": (
            f"RECOVERY-CASE::AGENT_SERVER_RUN_CREATE::"
            f"{source_invocation.invocation_id}"
        ),
        "research_run": recovery_run.model_dump(mode="json"),
        "source_invocation": source_invocation.model_dump(mode="json"),
        "ambiguous_action": ambiguous_action.model_dump(mode="json"),
        "lifecycle_event_digest": lifecycle_event_digest,
        "recovery_reason_code": recovery_reason_code,
        "server_run_id": server_run_id,
        "server_run_status": server_run_status,
        "opened_at": actual_opened_at,
    }
    return DellAgentServerRecoveryCase(
        recovery_case_id=unsigned["recovery_case_id"],
        research_run=recovery_run,
        source_invocation=source_invocation,
        ambiguous_action=ambiguous_action,
        lifecycle_event_digest=lifecycle_event_digest,
        recovery_reason_code=recovery_reason_code,
        server_run_id=server_run_id,
        server_run_status=server_run_status,
        opened_at=actual_opened_at,
        recovery_case_digest=canonical_json_sha256(unsigned),
    )


def recovery_case_digest(value: DellAgentServerRecoveryCase) -> str:
    return canonical_json_sha256(
        {
            "schema_version": "fin_ia_dell_agent_server_recovery_case_v1_0",
            "recovery_case_id": value.recovery_case_id,
            "research_run": value.research_run.model_dump(mode="json"),
            "source_invocation": value.source_invocation.model_dump(mode="json"),
            "ambiguous_action": value.ambiguous_action.model_dump(mode="json"),
            "lifecycle_event_digest": value.lifecycle_event_digest,
            "recovery_reason_code": value.recovery_reason_code,
            "server_run_id": value.server_run_id,
            "server_run_status": value.server_run_status,
            "opened_at": value.opened_at,
        }
    )


def validate_operator_disposition(
    disposition: RecoveryDisposition,
    *,
    recovery_case: DellAgentServerRecoveryCase,
    next_invocation: RunInvocation | None = None,
    replacement_action: ActionAttempt | None = None,
) -> RecoveryDisposition:
    """Validate an operator decision against the exact immutable case."""

    try:
        return validate_recovery_disposition_v1_2(
            disposition,
            ambiguous_action=recovery_case.ambiguous_action,
            run=recovery_case.research_run,
            source_invocation=recovery_case.source_invocation,
            next_invocation=next_invocation,
            replacement_action=replacement_action,
        )
    except Exception:
        raise DellAgentServerRecoveryError(
            "recovery_disposition_invalid"
        ) from None


def require_runtime_supported_disposition(
    disposition: RecoveryDisposition,
    *,
    recovery_case: DellAgentServerRecoveryCase,
) -> Literal["DO_NOT_RETRY", "ABANDON_RUN"]:
    validated = validate_operator_disposition(
        disposition,
        recovery_case=recovery_case,
    )
    if validated.decision not in SUPPORTED_RUNTIME_RECOVERY_DECISIONS:
        raise DellAgentServerRecoveryError(
            "recovery_disposition_not_runtime_supported"
        )
    return validated.decision


def _require_dispatched(value: ActionAttempt) -> None:
    if value.state != "DISPATCHED" or not value.was_dispatched:
        raise DellAgentServerRecoveryError(
            "run_create_action_dispatched_invalid"
        )
