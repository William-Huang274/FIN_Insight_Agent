"""Thin PostgreSQL mapping between FIN and Agent Server identities.

Agent Server remains the sole owner of execution, queueing, checkpoints, and
streaming. This module stores only FIN-owned identity bindings in the
independent ``fin_runtime`` schema. It never reads Agent Server internal tables
and it does not create a pool, worker, scheduler, or retry mechanism.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from importlib.resources import files
from hashlib import sha256
import json
import re
from typing import Any, Literal, Protocol
from uuid import UUID

from sec_agent.canonical_runtime.contracts_v1_2 import (
    ActionAttempt,
    AgentSessionV1_2,
    RecoveryDisposition,
    ResearchRun,
    RunInvocation,
    canonical_json_sha256,
)

from .dell_agent_server_recovery import (
    DellAgentServerRecoveryCase,
    DellAgentServerRecoveryError,
    create_recovery_case,
    create_recovery_required_research_run,
    create_interrupted_source_invocation,
    create_run_create_action_ambiguous,
    create_run_create_action_applied,
    create_run_create_action_dispatched,
    create_run_create_action_failed_before_dispatch,
    create_run_create_action_intent,
    validate_operator_disposition,
)


FIN_RUNTIME_SCHEMA = "fin_runtime"
IDENTITY_SCHEMA_RESOURCE = "sql/001_dell_agent_server_identity_v1_0.sql"
IDENTITY_SCHEMA_SHA256 = (
    "8102f5ab615bd616f64bd83f610b2e3c3206a9de023d7e27a48069f39e864209"
)
REMOTE_CREATE_LIFECYCLE_SCHEMA_RESOURCE = (
    "sql/002_dell_agent_server_remote_create_lifecycle_v1_1.sql"
)
REMOTE_CREATE_LIFECYCLE_SCHEMA_SHA256 = (
    "9e9f1e324c07bd767f71c8e870d736d44892b7b5614a4e0ffb1d557491218d25"
)
DELL_AGENT_SERVER_ASSISTANT_ID = "dell_reference_vertical"
_RUN_INVOCATION_LOCK_SEED = 20260903
_RUN_CREATE_LIFECYCLE_LOCK_SEED = 20260904
_ALLOWED_SERVER_RUN_STATUSES = frozenset(
    {"pending", "running", "error", "success", "timeout", "interrupted"}
)

RunCreateLifecycleState = Literal[
    "PENDING", "DISPATCHED", "ORPHAN", "RECONCILED"
]

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TOP_LEVEL_TRANSACTION_CONTROL_RE = re.compile(
    r"(?im)^\s*(?:begin(?:\s+(?:work|transaction))?"
    r"|commit(?:\s+work)?|rollback(?:\s+work)?)\s*;"
)


class DellAgentServerIdentityStoreError(RuntimeError):
    """Secret-free, machine-readable identity-store failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DellAgentServerIdentityConflict(DellAgentServerIdentityStoreError):
    """One side of a durable identity binding already has another peer."""


class CursorLike(Protocol):
    def fetchone(self) -> Sequence[Any] | None: ...

    def fetchall(self) -> Sequence[Sequence[Any]]: ...


class TransactionContextLike(Protocol):
    def __enter__(self) -> Any: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> bool | None: ...


class ConnectionContextLike(Protocol):
    def __enter__(self) -> "ConnectionLike": ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> bool | None: ...


class ConnectionLike(Protocol):
    """The small psycopg-compatible surface required by the repository."""

    def execute(
        self,
        query: str,
        params: Sequence[Any] | None = None,
    ) -> CursorLike: ...

    def transaction(self) -> TransactionContextLike: ...


class ConnectionPoolLike(Protocol):
    """Subset implemented by ``psycopg_pool.ConnectionPool``."""

    def connection(self) -> ConnectionContextLike: ...


ConnectionFactory = Callable[[], ConnectionContextLike]


@dataclass(frozen=True, slots=True)
class PersistedAgentSessionBinding:
    agent_session_id: str
    fin_thread_id: str
    server_thread_id: str
    assistant_id: str
    session_identity_digest: str
    bound_at: datetime


@dataclass(frozen=True, slots=True)
class PersistedResearchRunIdentity:
    research_run_id: str
    agent_session_id: str
    parent_research_run_id: str | None
    run_identity_digest: str
    first_bound_at: datetime


@dataclass(frozen=True, slots=True)
class PersistedRunInvocationBinding:
    run_invocation_id: str
    research_run_id: str
    agent_session_id: str
    invocation_ordinal: int
    canonical_invocation_kind: str
    server_invocation_kind: Literal["start", "resume"]
    server_thread_id: str
    server_run_id: str
    assistant_id: str
    invocation_identity_digest: str
    first_server_status: str
    bound_at: datetime


@dataclass(frozen=True, slots=True)
class PersistedRunCreateLifecycleEvent:
    """One immutable FIN-side observation of a remote create attempt."""

    run_invocation_id: str
    lifecycle_ordinal: int
    lifecycle_state: RunCreateLifecycleState
    research_run_id: str
    agent_session_id: str
    invocation_ordinal: int
    canonical_invocation_kind: str
    server_invocation_kind: Literal["start", "resume"]
    server_thread_id: str
    assistant_id: str
    server_assistant_id: str
    execution_profile: str
    session_identity_digest: str
    research_run_identity_digest: str
    run_invocation_identity_digest: str
    launch_request_digest: str
    server_metadata_digest: str
    bound_run_invocation_id: str | None
    server_run_id: str | None
    server_run_status: str | None
    recovery_reason_code: str | None
    server_observation_digest: str | None
    final_binding_digest: str | None
    lifecycle_event_digest: str
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class PersistedRunCreateLifecycle:
    """Projection over PENDING/DISPATCHED/ORPHAN*/RECONCILED."""

    pending: PersistedRunCreateLifecycleEvent
    orphan: PersistedRunCreateLifecycleEvent | None
    reconciled: PersistedRunCreateLifecycleEvent | None
    dispatched: PersistedRunCreateLifecycleEvent | None = None
    orphan_observations: tuple[PersistedRunCreateLifecycleEvent, ...] = ()

    @property
    def state(self) -> RunCreateLifecycleState:
        if self.reconciled is not None:
            return "RECONCILED"
        if self.orphan is not None:
            return "ORPHAN"
        if self.dispatched is not None:
            return "DISPATCHED"
        return "PENDING"


@dataclass(frozen=True, slots=True)
class PersistedRunCreateRegistration:
    lifecycle: PersistedRunCreateLifecycle
    created_now: bool


@dataclass(frozen=True, slots=True)
class PersistedExecutableRunBinding:
    """One transaction-consistent final binding and lifecycle projection."""

    binding: PersistedRunInvocationBinding
    lifecycle: PersistedRunCreateLifecycle | None


@dataclass(frozen=True, slots=True)
class PersistedResearchRunAggregate:
    """One FIN ResearchRun and its ordered one-to-many server runs."""

    research_run: PersistedResearchRunIdentity
    invocations: tuple[PersistedRunInvocationBinding, ...]

    @property
    def server_run_ids(self) -> tuple[str, ...]:
        return tuple(item.server_run_id for item in self.invocations)


class DellAgentServerIdentityRepository(Protocol):
    """Durable identity port consumed by the official Agent Server client."""

    def get_agent_session(
        self,
        *,
        agent_session_id: str,
    ) -> PersistedAgentSessionBinding | None: ...

    def bind_agent_session(
        self,
        *,
        agent_session: AgentSessionV1_2,
        server_thread_id: str,
        assistant_id: str = DELL_AGENT_SERVER_ASSISTANT_ID,
    ) -> PersistedAgentSessionBinding: ...

    def get_run_invocation(
        self,
        *,
        run_invocation_id: str,
    ) -> PersistedRunInvocationBinding | None: ...

    def get_run_create_lifecycle(
        self,
        *,
        run_invocation_id: str,
    ) -> PersistedRunCreateLifecycle | None: ...

    def get_execution_binding_with_lifecycle(
        self,
        *,
        run_invocation_id: str,
    ) -> PersistedExecutableRunBinding | None: ...

    def begin_run_create(
        self,
        *,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        server_thread_id: str,
        server_invocation_kind: Literal["start", "resume"],
        server_assistant_id: str,
        execution_profile: str,
        launch_request_digest: str,
        server_metadata_digest: str,
        assistant_id: str = DELL_AGENT_SERVER_ASSISTANT_ID,
    ) -> PersistedRunCreateRegistration: ...

    def get_run_create_action_attempt(
        self,
        *,
        run_invocation_id: str,
        action_state: str | None = None,
    ) -> ActionAttempt | None: ...

    def mark_run_create_dispatched(
        self,
        *,
        run_invocation_id: str,
        pending_event_digest: str,
    ) -> PersistedRunCreateLifecycle: ...

    def mark_run_create_failed_before_dispatch(
        self,
        *,
        run_invocation_id: str,
        pending_event_digest: str,
    ) -> ActionAttempt: ...

    def record_run_create_orphan(
        self,
        *,
        run_invocation_id: str,
        pending_event_digest: str,
        recovery_reason_code: str,
        server_observation_digest: str,
        server_run_id: str | None = None,
        server_run_status: str | None = None,
    ) -> PersistedRunCreateLifecycle: ...

    def mark_run_create_recovery_required(
        self,
        *,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        pending_event_digest: str,
        recovery_reason_code: str,
        server_observation_digest: str,
        server_run_id: str | None = None,
        server_run_status: str | None = None,
    ) -> DellAgentServerRecoveryCase: ...

    def get_run_create_recovery_case(
        self,
        *,
        run_invocation_id: str,
    ) -> DellAgentServerRecoveryCase | None: ...

    def get_run_create_recovery_disposition(
        self,
        *,
        run_invocation_id: str,
    ) -> RecoveryDisposition | None: ...

    def bind_run_invocation(
        self,
        *,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        server_thread_id: str,
        server_run_id: str,
        server_invocation_kind: Literal["start", "resume"],
        first_server_status: str,
        pending_event_digest: str,
        server_observation_digest: str,
        reconciliation_reason_code: str,
        assistant_id: str = DELL_AGENT_SERVER_ASSISTANT_ID,
    ) -> PersistedRunInvocationBinding: ...

    def get_research_run_aggregate(
        self,
        *,
        research_run_id: str,
    ) -> PersistedResearchRunAggregate | None: ...


def load_identity_schema_sql() -> str:
    """Load only the reviewed packaged migration and verify its content hash."""

    value = (
        files("sec_agent.agent_runtime")
        .joinpath(*IDENTITY_SCHEMA_RESOURCE.split("/"))
        .read_text(encoding="utf-8")
    )
    normalized = value.replace("\r\n", "\n")
    if sha256(normalized.encode("utf-8")).hexdigest() != IDENTITY_SCHEMA_SHA256:
        raise DellAgentServerIdentityStoreError(
            "identity_schema_digest_mismatch"
        )
    return normalized


def load_remote_create_lifecycle_schema_sql() -> str:
    """Load the reviewed append-only remote-create migration by exact digest."""

    value = (
        files("sec_agent.agent_runtime")
        .joinpath(*REMOTE_CREATE_LIFECYCLE_SCHEMA_RESOURCE.split("/"))
        .read_text(encoding="utf-8")
    )
    normalized = value.replace("\r\n", "\n")
    if (
        sha256(normalized.encode("utf-8")).hexdigest()
        != REMOTE_CREATE_LIFECYCLE_SCHEMA_SHA256
    ):
        raise DellAgentServerIdentityStoreError(
            "remote_create_lifecycle_schema_digest_mismatch"
        )
    return normalized


def validate_agent_session(value: AgentSessionV1_2) -> AgentSessionV1_2:
    try:
        return AgentSessionV1_2.model_validate(value)
    except Exception:
        raise DellAgentServerIdentityStoreError(
            "fin_agent_session_contract_invalid"
        ) from None


def validate_research_run(value: ResearchRun) -> ResearchRun:
    try:
        return ResearchRun.model_validate(value)
    except Exception:
        raise DellAgentServerIdentityStoreError(
            "fin_research_run_contract_invalid"
        ) from None


def validate_run_invocation(value: RunInvocation) -> RunInvocation:
    try:
        return RunInvocation.model_validate(value)
    except Exception:
        raise DellAgentServerIdentityStoreError(
            "fin_run_invocation_contract_invalid"
        ) from None


def agent_session_identity_digest(value: AgentSessionV1_2) -> str:
    """Digest immutable session identity/scope, excluding lifecycle state."""

    session = validate_agent_session(value)
    return canonical_json_sha256(
        {
            "schema_version": session.schema_version,
            "session_id": session.session_id,
            "thread_id": session.thread_id,
            "case_id": session.case_id,
            "case_version": session.case_version,
            "as_of_date": session.as_of_date,
            "objective_ref": session.objective_ref,
            "objective_digest": session.objective_digest,
            "data_snapshot_ref": session.data_snapshot_ref,
            "data_snapshot_digest": session.data_snapshot_digest,
            "runtime_policy_ref": session.runtime_policy_ref,
            "runtime_policy_digest": session.runtime_policy_digest,
            "authority_refs": session.authority_refs,
            "created_at": session.created_at,
        }
    )


def research_run_identity_digest(value: ResearchRun) -> str:
    """Digest stable ResearchRun lineage, excluding lifecycle progress."""

    run = validate_research_run(value)
    return canonical_json_sha256(
        {
            "schema_version": run.schema_version,
            "run_id": run.run_id,
            "session_id": run.session_id,
            "parent_run_id": run.parent_run_id,
            "origin_kind": run.origin_kind,
            "legacy_paid_full_chain_execution_label": (
                run.legacy_paid_full_chain_execution_label
            ),
            "base_plan_ref": run.base_plan_ref,
            "base_plan_digest": run.base_plan_digest,
            "created_at": run.created_at,
        }
    )


def run_invocation_identity_digest(value: RunInvocation) -> str:
    """Digest stable invocation lineage, excluding progress and lease state."""

    invocation = validate_run_invocation(value)
    return canonical_json_sha256(
        {
            "schema_version": invocation.schema_version,
            "invocation_id": invocation.invocation_id,
            "session_id": invocation.session_id,
            "run_id": invocation.run_id,
            "ordinal": invocation.ordinal,
            "invocation_kind": invocation.invocation_kind,
            "trigger_ref": invocation.trigger_ref,
            "started_at": invocation.started_at,
        }
    )


def persisted_run_binding_digest(value: PersistedRunInvocationBinding) -> str:
    """Digest the immutable FIN-to-server final binding, excluding time."""

    if not isinstance(value, PersistedRunInvocationBinding):
        raise DellAgentServerIdentityStoreError(
            "identity_invocation_binding_invalid"
        )
    return canonical_json_sha256(
        {
            "run_invocation_id": value.run_invocation_id,
            "research_run_id": value.research_run_id,
            "agent_session_id": value.agent_session_id,
            "invocation_ordinal": value.invocation_ordinal,
            "canonical_invocation_kind": value.canonical_invocation_kind,
            "server_invocation_kind": value.server_invocation_kind,
            "server_thread_id": value.server_thread_id,
            "server_run_id": value.server_run_id,
            "assistant_id": value.assistant_id,
            "invocation_identity_digest": value.invocation_identity_digest,
            "first_server_status": value.first_server_status,
        }
    )


def _run_create_event_digest(
    *,
    run_invocation_id: str,
    lifecycle_ordinal: int,
    lifecycle_state: RunCreateLifecycleState,
    research_run_id: str,
    agent_session_id: str,
    invocation_ordinal: int,
    canonical_invocation_kind: str,
    server_invocation_kind: str,
    server_thread_id: str,
    assistant_id: str,
    server_assistant_id: str,
    execution_profile: str,
    session_identity_digest: str,
    research_run_identity_digest: str,
    run_invocation_identity_digest: str,
    launch_request_digest: str,
    server_metadata_digest: str,
    bound_run_invocation_id: str | None,
    server_run_id: str | None,
    server_run_status: str | None,
    recovery_reason_code: str | None,
    server_observation_digest: str | None,
    final_binding_digest: str | None,
) -> str:
    return canonical_json_sha256(
        {
            "run_invocation_id": run_invocation_id,
            "lifecycle_ordinal": lifecycle_ordinal,
            "lifecycle_state": lifecycle_state,
            "research_run_id": research_run_id,
            "agent_session_id": agent_session_id,
            "invocation_ordinal": invocation_ordinal,
            "canonical_invocation_kind": canonical_invocation_kind,
            "server_invocation_kind": server_invocation_kind,
            "server_thread_id": server_thread_id,
            "assistant_id": assistant_id,
            "server_assistant_id": server_assistant_id,
            "execution_profile": execution_profile,
            "session_identity_digest": session_identity_digest,
            "research_run_identity_digest": research_run_identity_digest,
            "run_invocation_identity_digest": run_invocation_identity_digest,
            "launch_request_digest": launch_request_digest,
            "server_metadata_digest": server_metadata_digest,
            "bound_run_invocation_id": bound_run_invocation_id,
            "server_run_id": server_run_id,
            "server_run_status": server_run_status,
            "recovery_reason_code": recovery_reason_code,
            "server_observation_digest": server_observation_digest,
            "final_binding_digest": final_binding_digest,
        }
    )


class PostgresDellAgentServerIdentityRepository:
    """Append-only mapping over fresh connections checked out per operation."""

    def __init__(
        self,
        connection_source: ConnectionPoolLike | ConnectionFactory,
    ) -> None:
        checkout = getattr(connection_source, "connection", None)
        if not callable(checkout) and not callable(connection_source):
            raise DellAgentServerIdentityStoreError(
                "identity_store_connection_source_required"
            )
        self._connection_source = connection_source

    @contextmanager
    def _transaction(
        self,
        *,
        failure_code: str,
    ) -> Iterator[ConnectionLike]:
        try:
            pool_checkout = getattr(self._connection_source, "connection", None)
            connection_context = (
                pool_checkout()
                if callable(pool_checkout)
                else self._connection_source()
            )
            with connection_context as connection:
                _require_idle_connection(connection)
                with connection.transaction():
                    yield connection
                _require_idle_connection(connection)
        except DellAgentServerIdentityStoreError:
            raise
        except Exception:
            raise DellAgentServerIdentityStoreError(failure_code) from None

    def install_schema(self) -> None:
        """Reject the former repository-level migration bypass.

        Product schema changes are installed only by the checked-in container
        migration entrypoint, which verifies predecessor and successor catalog
        fingerprints before Agent Server becomes healthy.  A runtime repository
        must never be able to install DDL against an arbitrary database merely
        because the packaged SQL text has a matching source digest.
        """

        raise DellAgentServerIdentityStoreError(
            "identity_schema_repository_install_unsupported"
        )

    def get_agent_session(
        self,
        *,
        agent_session_id: str,
    ) -> PersistedAgentSessionBinding | None:
        session_id = _required_identifier(
            agent_session_id,
            code="fin_agent_session_id_invalid",
        )
        with self._transaction(
            failure_code="identity_session_read_failed"
        ) as connection:
            row = connection.execute(
                _SESSION_SELECT + " WHERE agent_session_id = %s",
                (session_id,),
            ).fetchone()
            return None if row is None else _session_from_row(row)

    def bind_agent_session(
        self,
        *,
        agent_session: AgentSessionV1_2,
        server_thread_id: str,
        assistant_id: str = DELL_AGENT_SERVER_ASSISTANT_ID,
    ) -> PersistedAgentSessionBinding:
        session = validate_agent_session(agent_session)
        thread_uuid = _server_uuid(
            server_thread_id,
            code="agent_server_thread_id_invalid",
        )
        assistant = _assistant_id(assistant_id)
        identity_digest = agent_session_identity_digest(session)
        with self._transaction(
            failure_code="identity_session_bind_failed"
        ) as connection:
            connection.execute(
                """
                INSERT INTO fin_runtime.research_sessions (
                    agent_session_id,
                    fin_thread_id,
                    server_thread_id,
                    assistant_id,
                    session_identity_digest
                )
                VALUES (%s, %s, %s::uuid, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    session.session_id,
                    session.thread_id,
                    thread_uuid,
                    assistant,
                    identity_digest,
                ),
            )
            rows = connection.execute(
                _SESSION_SELECT
                + """
                  WHERE agent_session_id = %s
                     OR fin_thread_id = %s
                     OR server_thread_id = %s::uuid
                  ORDER BY agent_session_id
                """,
                (session.session_id, session.thread_id, thread_uuid),
            ).fetchall()
            if len(rows) != 1:
                raise DellAgentServerIdentityConflict(
                    "agent_session_server_thread_cardinality_conflict"
                )
            persisted = _session_from_row(rows[0])
            if (
                persisted.agent_session_id != session.session_id
                or persisted.fin_thread_id != session.thread_id
                or persisted.server_thread_id != thread_uuid
                or persisted.assistant_id != assistant
                or persisted.session_identity_digest != identity_digest
            ):
                raise DellAgentServerIdentityConflict(
                    "agent_session_server_thread_binding_conflict"
                )
            return persisted

    def get_run_invocation(
        self,
        *,
        run_invocation_id: str,
    ) -> PersistedRunInvocationBinding | None:
        invocation_id = _required_identifier(
            run_invocation_id,
            code="fin_run_invocation_id_invalid",
        )
        with self._transaction(
            failure_code="identity_invocation_read_failed"
        ) as connection:
            row = connection.execute(
                _INVOCATION_SELECT + " WHERE run_invocation_id = %s",
                (invocation_id,),
            ).fetchone()
            return None if row is None else _invocation_from_row(row)

    def get_run_create_lifecycle(
        self,
        *,
        run_invocation_id: str,
    ) -> PersistedRunCreateLifecycle | None:
        invocation_id = _required_identifier(
            run_invocation_id,
            code="fin_run_invocation_id_invalid",
        )
        with self._transaction(
            failure_code="run_create_lifecycle_read_failed"
        ) as connection:
            rows = connection.execute(
                _RUN_CREATE_LIFECYCLE_SELECT
                + " WHERE run_invocation_id = %s ORDER BY lifecycle_ordinal",
                (invocation_id,),
            ).fetchall()
            return _run_create_lifecycle_from_rows(rows)

    def get_execution_binding_with_lifecycle(
        self,
        *,
        run_invocation_id: str,
    ) -> PersistedExecutableRunBinding | None:
        """Read the final binding and lifecycle inside one transaction boundary."""

        invocation_id = _required_identifier(
            run_invocation_id,
            code="fin_run_invocation_id_invalid",
        )
        with self._transaction(
            failure_code="identity_execution_binding_read_failed"
        ) as connection:
            binding_row = connection.execute(
                _INVOCATION_SELECT + " WHERE run_invocation_id = %s",
                (invocation_id,),
            ).fetchone()
            if binding_row is None:
                return None
            lifecycle_rows = connection.execute(
                _RUN_CREATE_LIFECYCLE_SELECT
                + " WHERE run_invocation_id = %s ORDER BY lifecycle_ordinal",
                (invocation_id,),
            ).fetchall()
            return PersistedExecutableRunBinding(
                binding=_invocation_from_row(binding_row),
                lifecycle=_run_create_lifecycle_from_rows(lifecycle_rows),
            )

    def begin_run_create(
        self,
        *,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        server_thread_id: str,
        server_invocation_kind: Literal["start", "resume"],
        server_assistant_id: str,
        execution_profile: str,
        launch_request_digest: str,
        server_metadata_digest: str,
        assistant_id: str = DELL_AGENT_SERVER_ASSISTANT_ID,
    ) -> PersistedRunCreateRegistration:
        run = validate_research_run(research_run)
        invocation = validate_run_invocation(run_invocation)
        if invocation.session_id != run.session_id:
            raise DellAgentServerIdentityStoreError(
                "run_invocation_session_mismatch"
            )
        if invocation.run_id != run.run_id:
            raise DellAgentServerIdentityStoreError("run_invocation_run_mismatch")
        transport_kind = _server_invocation_kind(server_invocation_kind)
        expected_transport_kind = (
            "start" if invocation.invocation_kind == "START" else "resume"
        )
        if transport_kind != expected_transport_kind:
            raise DellAgentServerIdentityStoreError(
                "run_invocation_transport_kind_mismatch"
            )
        if (
            invocation.invocation_kind == "START" and invocation.ordinal != 1
        ) or (
            invocation.invocation_kind in {"RESUME", "RECOVERY"}
            and invocation.ordinal <= 1
        ):
            raise DellAgentServerIdentityStoreError(
                "run_invocation_ordinal_kind_mismatch"
            )
        thread_uuid = _server_uuid(
            server_thread_id,
            code="agent_server_thread_id_invalid",
        )
        assistant = _assistant_id(assistant_id)
        concrete_assistant = _server_uuid(
            server_assistant_id,
            code="agent_server_concrete_assistant_id_invalid",
        )
        profile = _execution_profile(execution_profile)
        launch_digest = _digest(
            launch_request_digest,
            code="agent_server_launch_request_digest_invalid",
        )
        metadata_digest = _digest(
            server_metadata_digest,
            code="agent_server_metadata_digest_invalid",
        )
        run_identity = research_run_identity_digest(run)
        invocation_identity = run_invocation_identity_digest(invocation)
        try:
            action_intent = create_run_create_action_intent(
                research_run=run,
                source_invocation=invocation,
                launch_request_digest=launch_digest,
            )
        except DellAgentServerRecoveryError as exc:
            raise DellAgentServerIdentityStoreError(exc.code) from None

        with self._transaction(
            failure_code="run_create_pending_write_failed"
        ) as connection:
            session_row = connection.execute(
                _SESSION_SELECT + " WHERE agent_session_id = %s",
                (run.session_id,),
            ).fetchone()
            if session_row is None:
                raise DellAgentServerIdentityStoreError(
                    "agent_session_mapping_not_found"
                )
            session = _session_from_row(session_row)
            if (
                session.server_thread_id != thread_uuid
                or session.assistant_id != assistant
            ):
                raise DellAgentServerIdentityConflict(
                    "run_create_session_thread_conflict"
                )
            connection.execute(
                """
                SELECT pg_catalog.pg_advisory_xact_lock(
                    pg_catalog.hashtextextended(
                        'fin_runtime:run_create:' || %s,
                        %s
                    )
                )
                """,
                (run.run_id, _RUN_CREATE_LIFECYCLE_LOCK_SEED),
            )
            rows = connection.execute(
                _RUN_CREATE_LIFECYCLE_SELECT
                + """
                  WHERE run_invocation_id = %s
                     OR (research_run_id = %s AND invocation_ordinal = %s)
                  ORDER BY run_invocation_id, lifecycle_ordinal
                """,
                (invocation.invocation_id, run.run_id, invocation.ordinal),
            ).fetchall()
            if rows and {
                _required_identifier(
                    row[0], code="run_create_lifecycle_invocation_id_invalid"
                )
                for row in rows
            } != {invocation.invocation_id}:
                raise DellAgentServerIdentityConflict(
                    "run_create_research_run_ordinal_conflict"
                )
            created_now = not rows
            if created_now:
                event_digest = _run_create_event_digest(
                    run_invocation_id=invocation.invocation_id,
                    lifecycle_ordinal=1,
                    lifecycle_state="PENDING",
                    research_run_id=run.run_id,
                    agent_session_id=run.session_id,
                    invocation_ordinal=invocation.ordinal,
                    canonical_invocation_kind=invocation.invocation_kind,
                    server_invocation_kind=transport_kind,
                    server_thread_id=thread_uuid,
                    assistant_id=assistant,
                    server_assistant_id=concrete_assistant,
                    execution_profile=profile,
                    session_identity_digest=session.session_identity_digest,
                    research_run_identity_digest=run_identity,
                    run_invocation_identity_digest=invocation_identity,
                    launch_request_digest=launch_digest,
                    server_metadata_digest=metadata_digest,
                    bound_run_invocation_id=None,
                    server_run_id=None,
                    server_run_status=None,
                    recovery_reason_code=None,
                    server_observation_digest=None,
                    final_binding_digest=None,
                )
                connection.execute(
                    """
                    INSERT INTO fin_runtime.agent_server_run_create_lifecycle (
                        run_invocation_id, lifecycle_ordinal, lifecycle_state,
                        research_run_id, agent_session_id, invocation_ordinal,
                        canonical_invocation_kind, server_invocation_kind,
                        server_thread_id, assistant_id, server_assistant_id,
                        execution_profile, session_identity_digest,
                        research_run_identity_digest,
                        run_invocation_identity_digest, launch_request_digest,
                        server_metadata_digest, bound_run_invocation_id,
                        server_run_id, server_run_status, recovery_reason_code,
                        server_observation_digest, final_binding_digest,
                        lifecycle_event_digest
                    )
                    VALUES (
                        %s, 1, 'PENDING', %s, %s, %s, %s, %s, %s::uuid,
                        %s, %s::uuid, %s, %s, %s, %s, %s, %s,
                        NULL, NULL, NULL, NULL, NULL, NULL, %s
                    )
                    """,
                    (
                        invocation.invocation_id,
                        run.run_id,
                        run.session_id,
                        invocation.ordinal,
                        invocation.invocation_kind,
                        transport_kind,
                        thread_uuid,
                        assistant,
                        concrete_assistant,
                        profile,
                        session.session_identity_digest,
                        run_identity,
                        invocation_identity,
                        launch_digest,
                        metadata_digest,
                        event_digest,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO fin_runtime.agent_server_action_attempt_snapshots (
                        run_invocation_id, snapshot_ordinal, action_state,
                        action_outcome, action_attempt_id,
                        action_attempt_digest, canonical_action_attempt
                    )
                    VALUES (
                        %s, 1, 'INTENT_COMMITTED', NULL, %s, %s, %s::jsonb
                    )
                    """,
                    (
                        invocation.invocation_id,
                        action_intent.action_attempt_id,
                        action_intent.action_attempt_digest,
                        _canonical_model_json(action_intent),
                    ),
                )
                rows = connection.execute(
                    _RUN_CREATE_LIFECYCLE_SELECT
                    + " WHERE run_invocation_id = %s ORDER BY lifecycle_ordinal",
                    (invocation.invocation_id,),
                ).fetchall()
            lifecycle = _run_create_lifecycle_from_rows(rows)
            if lifecycle is None or not _pending_event_matches(
                lifecycle.pending,
                research_run=run,
                run_invocation=invocation,
                server_thread_id=thread_uuid,
                server_invocation_kind=transport_kind,
                assistant_id=assistant,
                server_assistant_id=concrete_assistant,
                execution_profile=profile,
                session_identity_digest=session.session_identity_digest,
                launch_request_digest=launch_digest,
                server_metadata_digest=metadata_digest,
            ):
                raise DellAgentServerIdentityConflict(
                    "run_create_pending_identity_conflict"
                )
            intent_row = connection.execute(
                _ACTION_ATTEMPT_SELECT
                + " WHERE run_invocation_id = %s AND action_state = 'INTENT_COMMITTED'",
                (invocation.invocation_id,),
            ).fetchone()
            if intent_row is None:
                raise DellAgentServerIdentityStoreError(
                    "run_create_action_intent_missing"
                )
            persisted_intent = _action_attempt_from_row(intent_row)
            if persisted_intent != action_intent:
                raise DellAgentServerIdentityConflict(
                    "run_create_action_intent_conflict"
                )
            return PersistedRunCreateRegistration(
                lifecycle=lifecycle,
                created_now=created_now,
            )

    def get_run_create_action_attempt(
        self,
        *,
        run_invocation_id: str,
        action_state: str | None = None,
    ) -> ActionAttempt | None:
        invocation_id = _required_identifier(
            run_invocation_id,
            code="fin_run_invocation_id_invalid",
        )
        if action_state is not None and action_state not in {
            "INTENT_COMMITTED",
            "DISPATCHED",
            "TERMINAL",
        }:
            raise DellAgentServerIdentityStoreError(
                "run_create_action_state_invalid"
            )
        with self._transaction(
            failure_code="run_create_action_read_failed"
        ) as connection:
            query = _ACTION_ATTEMPT_SELECT + " WHERE run_invocation_id = %s"
            params: tuple[Any, ...] = (invocation_id,)
            if action_state is not None:
                query += " AND action_state = %s"
                params = (invocation_id, action_state)
            query += " ORDER BY snapshot_ordinal DESC LIMIT 1"
            row = connection.execute(query, params).fetchone()
            return None if row is None else _action_attempt_from_row(row)

    def mark_run_create_dispatched(
        self,
        *,
        run_invocation_id: str,
        pending_event_digest: str,
    ) -> PersistedRunCreateLifecycle:
        invocation_id = _required_identifier(
            run_invocation_id,
            code="fin_run_invocation_id_invalid",
        )
        pending_digest = _digest(
            pending_event_digest,
            code="run_create_pending_digest_invalid",
        )
        with self._transaction(
            failure_code="run_create_dispatched_write_failed"
        ) as connection:
            lifecycle = _locked_run_create_lifecycle(
                connection,
                run_invocation_id=invocation_id,
            )
            if lifecycle.pending.lifecycle_event_digest != pending_digest:
                raise DellAgentServerIdentityConflict(
                    "run_create_pending_digest_conflict"
                )
            terminal_row = connection.execute(
                _ACTION_ATTEMPT_SELECT
                + " WHERE run_invocation_id = %s AND action_state = 'TERMINAL'",
                (invocation_id,),
            ).fetchone()
            if terminal_row is not None:
                raise DellAgentServerIdentityConflict(
                    "run_create_action_already_terminal"
                )
            intent_row = connection.execute(
                _ACTION_ATTEMPT_SELECT
                + " WHERE run_invocation_id = %s AND action_state = 'INTENT_COMMITTED'",
                (invocation_id,),
            ).fetchone()
            if intent_row is None:
                raise DellAgentServerIdentityStoreError(
                    "run_create_action_intent_missing"
                )
            intent = _action_attempt_from_row(intent_row)
            if lifecycle.dispatched is not None:
                dispatched_row = connection.execute(
                    _ACTION_ATTEMPT_SELECT
                    + " WHERE run_invocation_id = %s AND action_state = 'DISPATCHED'",
                    (invocation_id,),
                ).fetchone()
                if dispatched_row is None:
                    raise DellAgentServerIdentityStoreError(
                        "run_create_action_dispatched_missing"
                    )
                expected = create_run_create_action_dispatched(intent)
                if _action_attempt_from_row(dispatched_row) != expected:
                    raise DellAgentServerIdentityConflict(
                        "run_create_action_dispatched_conflict"
                    )
                return lifecycle
            if lifecycle.state != "PENDING":
                raise DellAgentServerIdentityConflict(
                    "run_create_dispatch_transition_invalid"
                )
            try:
                dispatched_action = create_run_create_action_dispatched(intent)
            except DellAgentServerRecoveryError as exc:
                raise DellAgentServerIdentityStoreError(exc.code) from None
            pending = lifecycle.pending
            event_digest = _run_create_event_digest(
                run_invocation_id=pending.run_invocation_id,
                lifecycle_ordinal=2,
                lifecycle_state="DISPATCHED",
                research_run_id=pending.research_run_id,
                agent_session_id=pending.agent_session_id,
                invocation_ordinal=pending.invocation_ordinal,
                canonical_invocation_kind=pending.canonical_invocation_kind,
                server_invocation_kind=pending.server_invocation_kind,
                server_thread_id=pending.server_thread_id,
                assistant_id=pending.assistant_id,
                server_assistant_id=pending.server_assistant_id,
                execution_profile=pending.execution_profile,
                session_identity_digest=pending.session_identity_digest,
                research_run_identity_digest=pending.research_run_identity_digest,
                run_invocation_identity_digest=pending.run_invocation_identity_digest,
                launch_request_digest=pending.launch_request_digest,
                server_metadata_digest=pending.server_metadata_digest,
                bound_run_invocation_id=None,
                server_run_id=None,
                server_run_status=None,
                recovery_reason_code=None,
                server_observation_digest=None,
                final_binding_digest=None,
            )
            _insert_run_create_lifecycle_event(
                connection,
                pending=pending,
                lifecycle_ordinal=2,
                lifecycle_state="DISPATCHED",
                lifecycle_event_digest=event_digest,
            )
            _insert_action_attempt_snapshot(
                connection,
                run_invocation_id=invocation_id,
                snapshot_ordinal=2,
                action=dispatched_action,
            )
            return _required_run_create_lifecycle(
                connection,
                run_invocation_id=invocation_id,
            )

    def mark_run_create_failed_before_dispatch(
        self,
        *,
        run_invocation_id: str,
        pending_event_digest: str,
    ) -> ActionAttempt:
        invocation_id = _required_identifier(
            run_invocation_id,
            code="fin_run_invocation_id_invalid",
        )
        pending_digest = _digest(
            pending_event_digest,
            code="run_create_pending_digest_invalid",
        )
        with self._transaction(
            failure_code="run_create_before_dispatch_terminal_write_failed"
        ) as connection:
            lifecycle = _locked_run_create_lifecycle(
                connection,
                run_invocation_id=invocation_id,
            )
            if lifecycle.pending.lifecycle_event_digest != pending_digest:
                raise DellAgentServerIdentityConflict(
                    "run_create_pending_digest_conflict"
                )
            if lifecycle.state != "PENDING":
                raise DellAgentServerIdentityConflict(
                    "run_create_before_dispatch_terminal_transition_invalid"
                )
            terminal_row = connection.execute(
                _ACTION_ATTEMPT_SELECT
                + " WHERE run_invocation_id = %s AND action_state = 'TERMINAL'",
                (invocation_id,),
            ).fetchone()
            if terminal_row is not None:
                terminal = _action_attempt_from_row(terminal_row)
                if terminal.outcome != "FAILED_BEFORE_DISPATCH":
                    raise DellAgentServerIdentityConflict(
                        "run_create_action_terminal_conflict"
                    )
                return terminal
            intent_row = connection.execute(
                _ACTION_ATTEMPT_SELECT
                + " WHERE run_invocation_id = %s AND action_state = 'INTENT_COMMITTED'",
                (invocation_id,),
            ).fetchone()
            if intent_row is None:
                raise DellAgentServerIdentityStoreError(
                    "run_create_action_intent_missing"
                )
            try:
                terminal = create_run_create_action_failed_before_dispatch(
                    _action_attempt_from_row(intent_row)
                )
            except DellAgentServerRecoveryError as exc:
                raise DellAgentServerIdentityStoreError(exc.code) from None
            _insert_action_attempt_snapshot(
                connection,
                run_invocation_id=invocation_id,
                snapshot_ordinal=2,
                action=terminal,
            )
            return terminal

    def record_run_create_orphan(
        self,
        *,
        run_invocation_id: str,
        pending_event_digest: str,
        recovery_reason_code: str,
        server_observation_digest: str,
        server_run_id: str | None = None,
        server_run_status: str | None = None,
    ) -> PersistedRunCreateLifecycle:
        invocation_id = _required_identifier(
            run_invocation_id,
            code="fin_run_invocation_id_invalid",
        )
        pending_digest = _digest(
            pending_event_digest,
            code="run_create_pending_digest_invalid",
        )
        reason = _required_identifier(
            recovery_reason_code,
            code="run_create_recovery_reason_invalid",
            maximum=120,
        )
        observation_digest = _digest(
            server_observation_digest,
            code="run_create_observation_digest_invalid",
        )
        run_uuid = (
            None
            if server_run_id is None
            else _server_uuid(server_run_id, code="agent_server_run_id_invalid")
        )
        status = (
            None
            if server_run_status is None
            else _required_identifier(
                server_run_status,
                code="agent_server_run_status_invalid",
                maximum=80,
            )
        )
        if status is not None and run_uuid is None:
            raise DellAgentServerIdentityStoreError(
                "run_create_orphan_remote_identity_incomplete"
            )

        with self._transaction(
            failure_code="run_create_orphan_write_failed"
        ) as connection:
            lifecycle = _locked_run_create_lifecycle(
                connection,
                run_invocation_id=invocation_id,
            )
            if lifecycle.pending.lifecycle_event_digest != pending_digest:
                raise DellAgentServerIdentityConflict(
                    "run_create_pending_digest_conflict"
                )
            return _append_orphan_observation(
                connection,
                lifecycle=lifecycle,
                recovery_reason_code=reason,
                server_observation_digest=observation_digest,
                server_run_id=run_uuid,
                server_run_status=status,
            )

    def mark_run_create_recovery_required(
        self,
        *,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        pending_event_digest: str,
        recovery_reason_code: str,
        server_observation_digest: str,
        server_run_id: str | None = None,
        server_run_status: str | None = None,
    ) -> DellAgentServerRecoveryCase:
        run = validate_research_run(research_run)
        invocation = validate_run_invocation(run_invocation)
        if invocation.session_id != run.session_id or invocation.run_id != run.run_id:
            raise DellAgentServerIdentityStoreError(
                "run_create_recovery_lineage_invalid"
            )
        pending_digest = _digest(
            pending_event_digest,
            code="run_create_pending_digest_invalid",
        )
        reason = _required_identifier(
            recovery_reason_code,
            code="run_create_recovery_reason_invalid",
            maximum=120,
        )
        observation_digest = _digest(
            server_observation_digest,
            code="run_create_observation_digest_invalid",
        )
        run_uuid = (
            None
            if server_run_id is None
            else _server_uuid(server_run_id, code="agent_server_run_id_invalid")
        )
        status = (
            None
            if server_run_status is None
            else _server_run_status(server_run_status)
        )
        if status is not None and run_uuid is None:
            raise DellAgentServerIdentityStoreError(
                "run_create_orphan_remote_identity_incomplete"
            )
        with self._transaction(
            failure_code="run_create_recovery_required_write_failed"
        ) as connection:
            lifecycle = _locked_run_create_lifecycle(
                connection,
                run_invocation_id=invocation.invocation_id,
            )
            if lifecycle.pending.lifecycle_event_digest != pending_digest:
                raise DellAgentServerIdentityConflict(
                    "run_create_pending_digest_conflict"
                )
            if lifecycle.dispatched is None or lifecycle.reconciled is not None:
                raise DellAgentServerIdentityConflict(
                    "run_create_recovery_transition_invalid"
                )
            persisted_case_row = connection.execute(
                _RECOVERY_CASE_SELECT + " WHERE run_invocation_id = %s",
                (invocation.invocation_id,),
            ).fetchone()
            if persisted_case_row is not None:
                persisted_case = _recovery_case_from_row(persisted_case_row)
                if (
                    persisted_case.research_run.run_id != run.run_id
                    or run_invocation_identity_digest(
                        persisted_case.source_invocation
                    ) != run_invocation_identity_digest(invocation)
                ):
                    raise DellAgentServerIdentityConflict(
                        "run_create_recovery_case_conflict"
                    )
                return persisted_case
            lifecycle = _append_orphan_observation(
                connection,
                lifecycle=lifecycle,
                recovery_reason_code=reason,
                server_observation_digest=observation_digest,
                server_run_id=run_uuid,
                server_run_status=status,
            )
            dispatched_row = connection.execute(
                _ACTION_ATTEMPT_SELECT
                + " WHERE run_invocation_id = %s AND action_state = 'DISPATCHED'",
                (invocation.invocation_id,),
            ).fetchone()
            if dispatched_row is None:
                raise DellAgentServerIdentityStoreError(
                    "run_create_action_dispatched_missing"
                )
            try:
                ambiguous = create_run_create_action_ambiguous(
                    _action_attempt_from_row(dispatched_row)
                )
                recovery_run = create_recovery_required_research_run(run)
                source_invocation = create_interrupted_source_invocation(
                    invocation,
                    finished_at=ambiguous.terminal_at,
                )
                recovery_case = create_recovery_case(
                    recovery_run=recovery_run,
                    source_invocation=source_invocation,
                    ambiguous_action=ambiguous,
                    lifecycle_event_digest=(
                        lifecycle.orphan.lifecycle_event_digest
                    ),
                    recovery_reason_code=reason,
                    server_run_id=run_uuid,
                    server_run_status=status,
                    opened_at=ambiguous.terminal_at,
                )
            except DellAgentServerRecoveryError as exc:
                raise DellAgentServerIdentityStoreError(exc.code) from None
            _insert_action_attempt_snapshot(
                connection,
                run_invocation_id=invocation.invocation_id,
                snapshot_ordinal=3,
                action=ambiguous,
            )
            connection.execute(
                """
                INSERT INTO fin_runtime.agent_server_recovery_cases (
                    recovery_case_id, run_invocation_id, research_run_id,
                    agent_session_id, recovery_research_run_digest,
                    source_run_invocation_digest,
                    ambiguous_action_attempt_id,
                    ambiguous_action_attempt_digest, lifecycle_event_digest,
                    recovery_reason_code, server_run_id, server_run_status,
                    canonical_recovery_research_run,
                    canonical_source_run_invocation,
                    canonical_ambiguous_action_attempt, opened_at,
                    recovery_case_digest
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::uuid, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                    %s, %s
                )
                """,
                (
                    recovery_case.recovery_case_id,
                    invocation.invocation_id,
                    run.run_id,
                    run.session_id,
                    recovery_run.run_digest,
                    source_invocation.invocation_digest,
                    ambiguous.action_attempt_id,
                    ambiguous.action_attempt_digest,
                    recovery_case.lifecycle_event_digest,
                    reason,
                    run_uuid,
                    status,
                    _canonical_model_json(recovery_run),
                    _canonical_model_json(source_invocation),
                    _canonical_model_json(ambiguous),
                    recovery_case.opened_at,
                    recovery_case.recovery_case_digest,
                ),
            )
            persisted_row = connection.execute(
                _RECOVERY_CASE_SELECT + " WHERE run_invocation_id = %s",
                (invocation.invocation_id,),
            ).fetchone()
            if persisted_row is None:
                raise DellAgentServerIdentityStoreError(
                    "run_create_recovery_case_not_persisted"
                )
            persisted = _recovery_case_from_row(persisted_row)
            if persisted != recovery_case:
                raise DellAgentServerIdentityConflict(
                    "run_create_recovery_case_conflict"
                )
            return persisted

    def get_run_create_recovery_case(
        self,
        *,
        run_invocation_id: str,
    ) -> DellAgentServerRecoveryCase | None:
        invocation_id = _required_identifier(
            run_invocation_id,
            code="fin_run_invocation_id_invalid",
        )
        with self._transaction(
            failure_code="run_create_recovery_case_read_failed"
        ) as connection:
            row = connection.execute(
                _RECOVERY_CASE_SELECT + " WHERE run_invocation_id = %s",
                (invocation_id,),
            ).fetchone()
            return None if row is None else _recovery_case_from_row(row)

    def get_run_create_recovery_disposition(
        self,
        *,
        run_invocation_id: str,
    ) -> RecoveryDisposition | None:
        invocation_id = _required_identifier(
            run_invocation_id,
            code="fin_run_invocation_id_invalid",
        )
        with self._transaction(
            failure_code="run_create_recovery_disposition_read_failed"
        ) as connection:
            row = connection.execute(
                _RECOVERY_DISPOSITION_SELECT + " WHERE run_invocation_id = %s",
                (invocation_id,),
            ).fetchone()
            return None if row is None else _recovery_disposition_from_row(row)

    def bind_run_invocation(
        self,
        *,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        server_thread_id: str,
        server_run_id: str,
        server_invocation_kind: Literal["start", "resume"],
        first_server_status: str,
        pending_event_digest: str,
        server_observation_digest: str,
        reconciliation_reason_code: str,
        assistant_id: str = DELL_AGENT_SERVER_ASSISTANT_ID,
    ) -> PersistedRunInvocationBinding:
        run = validate_research_run(research_run)
        invocation = validate_run_invocation(run_invocation)
        if invocation.session_id != run.session_id:
            raise DellAgentServerIdentityStoreError(
                "run_invocation_session_mismatch"
            )
        if invocation.run_id != run.run_id:
            raise DellAgentServerIdentityStoreError("run_invocation_run_mismatch")
        if (
            invocation.invocation_kind == "START"
            and invocation.ordinal != 1
        ) or (
            invocation.invocation_kind in {"RESUME", "RECOVERY"}
            and invocation.ordinal <= 1
        ):
            raise DellAgentServerIdentityStoreError(
                "run_invocation_ordinal_kind_mismatch"
            )
        transport_kind = _server_invocation_kind(server_invocation_kind)
        expected_transport_kind = (
            "start" if invocation.invocation_kind == "START" else "resume"
        )
        if transport_kind != expected_transport_kind:
            raise DellAgentServerIdentityStoreError(
                "run_invocation_transport_kind_mismatch"
            )
        thread_uuid = _server_uuid(
            server_thread_id,
            code="agent_server_thread_id_invalid",
        )
        run_uuid = _server_uuid(server_run_id, code="agent_server_run_id_invalid")
        assistant = _assistant_id(assistant_id)
        server_status = _server_run_status(first_server_status)
        pending_digest = _digest(
            pending_event_digest,
            code="run_create_pending_digest_invalid",
        )
        observation_digest = _digest(
            server_observation_digest,
            code="run_create_observation_digest_invalid",
        )
        reconciliation_reason = _required_identifier(
            reconciliation_reason_code,
            code="run_create_reconciliation_reason_invalid",
            maximum=120,
        )
        run_identity = research_run_identity_digest(run)
        invocation_identity = run_invocation_identity_digest(invocation)

        with self._transaction(
            failure_code="identity_invocation_bind_failed"
        ) as connection:
            session_row = connection.execute(
                _SESSION_SELECT + " WHERE agent_session_id = %s",
                (run.session_id,),
            ).fetchone()
            if session_row is None:
                raise DellAgentServerIdentityStoreError(
                    "agent_session_mapping_not_found"
                )
            session = _session_from_row(session_row)
            if (
                session.server_thread_id != thread_uuid
                or session.assistant_id != assistant
            ):
                raise DellAgentServerIdentityConflict(
                    "run_invocation_session_thread_conflict"
                )

            # All lifecycle mutation paths acquire this lock first.  The
            # older per-ResearchRun invocation-sequence lock is deliberately
            # acquired second below, giving every writer one stable lock order.
            connection.execute(
                """
                SELECT pg_catalog.pg_advisory_xact_lock(
                    pg_catalog.hashtextextended(
                        'fin_runtime:run_create:' || %s,
                        %s
                    )
                )
                """,
                (run.run_id, _RUN_CREATE_LIFECYCLE_LOCK_SEED),
            )
            lifecycle_rows = connection.execute(
                _RUN_CREATE_LIFECYCLE_SELECT
                + " WHERE run_invocation_id = %s ORDER BY lifecycle_ordinal",
                (invocation.invocation_id,),
            ).fetchall()
            lifecycle = _run_create_lifecycle_from_rows(lifecycle_rows)
            if lifecycle is None:
                raise DellAgentServerIdentityStoreError(
                    "run_create_pending_missing"
                )
            pending = lifecycle.pending
            if pending.lifecycle_event_digest != pending_digest:
                raise DellAgentServerIdentityConflict(
                    "run_create_pending_digest_conflict"
                )
            if lifecycle.dispatched is None:
                raise DellAgentServerIdentityConflict(
                    "run_create_dispatched_missing"
                )
            if (
                pending.research_run_id != run.run_id
                or pending.agent_session_id != run.session_id
                or pending.invocation_ordinal != invocation.ordinal
                or pending.canonical_invocation_kind != invocation.invocation_kind
                or pending.server_invocation_kind != transport_kind
                or pending.server_thread_id != thread_uuid
                or pending.assistant_id != assistant
                or pending.session_identity_digest
                != session.session_identity_digest
                or pending.research_run_identity_digest != run_identity
                or pending.run_invocation_identity_digest != invocation_identity
            ):
                raise DellAgentServerIdentityConflict(
                    "run_create_pending_identity_conflict"
                )
            if any(
                observation.server_run_id is not None
                and observation.server_run_id != run_uuid
                for observation in lifecycle.orphan_observations
            ):
                raise DellAgentServerIdentityConflict(
                    "run_create_orphan_server_run_conflict"
                )
            if lifecycle.reconciled is not None:
                reconciled = lifecycle.reconciled
                binding_row = connection.execute(
                    _INVOCATION_SELECT + " WHERE run_invocation_id = %s",
                    (invocation.invocation_id,),
                ).fetchone()
                if binding_row is None:
                    raise DellAgentServerIdentityStoreError(
                        "run_create_reconciled_binding_missing"
                    )
                existing_binding = _invocation_from_row(binding_row)
                if (
                    reconciled.server_run_id != run_uuid
                    or reconciled.server_run_status != server_status
                    or reconciled.recovery_reason_code != reconciliation_reason
                    or reconciled.server_observation_digest != observation_digest
                    or reconciled.final_binding_digest
                    != persisted_run_binding_digest(existing_binding)
                    or existing_binding.run_invocation_id
                    != invocation.invocation_id
                    or existing_binding.research_run_id != run.run_id
                    or existing_binding.agent_session_id != run.session_id
                    or existing_binding.invocation_ordinal != invocation.ordinal
                    or existing_binding.canonical_invocation_kind
                    != invocation.invocation_kind
                    or existing_binding.server_invocation_kind != transport_kind
                    or existing_binding.server_thread_id != thread_uuid
                    or existing_binding.server_run_id != run_uuid
                    or existing_binding.assistant_id != assistant
                    or existing_binding.invocation_identity_digest
                    != invocation_identity
                    or existing_binding.first_server_status != server_status
                ):
                    raise DellAgentServerIdentityConflict(
                        "run_create_reconciled_binding_conflict"
                    )
                return existing_binding

            terminal_row = connection.execute(
                _ACTION_ATTEMPT_SELECT
                + " WHERE run_invocation_id = %s AND action_state = 'TERMINAL'",
                (invocation.invocation_id,),
            ).fetchone()
            terminal_action = (
                None if terminal_row is None else _action_attempt_from_row(terminal_row)
            )
            recovery_case_row = connection.execute(
                _RECOVERY_CASE_SELECT + " WHERE run_invocation_id = %s",
                (invocation.invocation_id,),
            ).fetchone()
            recovery_case = (
                None
                if recovery_case_row is None
                else _recovery_case_from_row(recovery_case_row)
            )
            if terminal_action is not None:
                if (
                    terminal_action.outcome != "AMBIGUOUS_AFTER_DISPATCH"
                    or recovery_case is None
                    or recovery_case.ambiguous_action != terminal_action
                ):
                    raise DellAgentServerIdentityConflict(
                        "run_create_action_terminal_conflict"
                    )
                disposition_row = connection.execute(
                    _RECOVERY_DISPOSITION_SELECT + " WHERE run_invocation_id = %s",
                    (invocation.invocation_id,),
                ).fetchone()
                if disposition_row is None:
                    raise DellAgentServerIdentityStoreError(
                        "run_create_recovery_disposition_required"
                    )
                disposition = _recovery_disposition_from_row(disposition_row)
                try:
                    validate_operator_disposition(
                        disposition,
                        recovery_case=recovery_case,
                    )
                except DellAgentServerRecoveryError as exc:
                    raise DellAgentServerIdentityStoreError(exc.code) from None
                if disposition.decision != "DO_NOT_RETRY":
                    raise DellAgentServerIdentityStoreError(
                        "run_create_recovery_disposition_not_bindable"
                    )
                known_recovery_run_ids = {
                    observation.server_run_id
                    for observation in lifecycle.orphan_observations
                    if observation.server_run_id is not None
                    and observation.server_run_status is not None
                }
                if known_recovery_run_ids != {run_uuid}:
                    raise DellAgentServerIdentityConflict(
                        "run_create_recovery_server_run_conflict"
                    )
                if not any(
                    observation.server_run_id == run_uuid
                    and observation.server_run_status == server_status
                    and observation.server_observation_digest
                    == observation_digest
                    for observation in lifecycle.orphan_observations
                ):
                    raise DellAgentServerIdentityConflict(
                        "run_create_recovery_observation_conflict"
                    )
            elif recovery_case is not None:
                raise DellAgentServerIdentityStoreError(
                    "run_create_recovery_terminal_action_missing"
                )

            # The runtime role is deliberately append-only and therefore has
            # no UPDATE privilege.  PostgreSQL row-locking clauses such as
            # SELECT ... FOR UPDATE also require UPDATE privilege.  A
            # transaction-scoped advisory lock gives the same per-run
            # serialization boundary without weakening the table grants.  A
            # hash collision can only serialize two unrelated runs; it cannot
            # merge their identities or change correctness.
            connection.execute(
                """
                SELECT pg_catalog.pg_advisory_xact_lock(
                    pg_catalog.hashtextextended(
                        'fin_runtime:research_run:' || %s,
                        %s
                    )
                )
                """,
                (run.run_id, _RUN_INVOCATION_LOCK_SEED),
            )

            connection.execute(
                """
                INSERT INTO fin_runtime.research_runs (
                    research_run_id,
                    agent_session_id,
                    parent_research_run_id,
                    run_identity_digest
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    run.run_id,
                    run.session_id,
                    run.parent_run_id,
                    run_identity,
                ),
            )
            run_row = connection.execute(
                _RUN_SELECT + " WHERE research_run_id = %s",
                (run.run_id,),
            ).fetchone()
            if run_row is None:
                raise DellAgentServerIdentityStoreError(
                    "research_run_identity_not_persisted"
                )
            persisted_run = _run_from_row(run_row)
            if (
                persisted_run.agent_session_id != run.session_id
                or persisted_run.parent_research_run_id != run.parent_run_id
                or persisted_run.run_identity_digest != run_identity
            ):
                raise DellAgentServerIdentityConflict(
                    "research_run_identity_conflict"
                )

            sequence_row = connection.execute(
                """
                SELECT
                    COALESCE(MAX(invocation_ordinal), 0),
                    COUNT(*)
                FROM fin_runtime.research_run_invocations
                WHERE research_run_id = %s
                """,
                (run.run_id,),
            ).fetchone()
            if sequence_row is None or len(sequence_row) != 2:
                raise DellAgentServerIdentityStoreError(
                    "research_run_invocation_sequence_read_failed"
                )
            maximum_ordinal = _nonnegative_int(
                sequence_row[0],
                code="research_run_invocation_sequence_invalid",
            )
            invocation_count = _nonnegative_int(
                sequence_row[1],
                code="research_run_invocation_sequence_invalid",
            )
            if invocation_count != maximum_ordinal:
                raise DellAgentServerIdentityConflict(
                    "research_run_invocation_sequence_gap"
                )
            if invocation.ordinal > maximum_ordinal + 1:
                raise DellAgentServerIdentityConflict(
                    "research_run_invocation_sequence_gap"
                )

            connection.execute(
                """
                INSERT INTO fin_runtime.research_run_invocations (
                    run_invocation_id,
                    research_run_id,
                    agent_session_id,
                    invocation_ordinal,
                    canonical_invocation_kind,
                    server_invocation_kind,
                    server_thread_id,
                    server_run_id,
                    assistant_id,
                    invocation_identity_digest,
                    first_server_status
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s::uuid, %s::uuid,
                    %s, %s, %s
                )
                ON CONFLICT DO NOTHING
                """,
                (
                    invocation.invocation_id,
                    run.run_id,
                    run.session_id,
                    invocation.ordinal,
                    invocation.invocation_kind,
                    transport_kind,
                    thread_uuid,
                    run_uuid,
                    assistant,
                    invocation_identity,
                    server_status,
                ),
            )
            rows = connection.execute(
                _INVOCATION_SELECT
                + """
                  WHERE run_invocation_id = %s
                     OR server_run_id = %s::uuid
                     OR (research_run_id = %s AND invocation_ordinal = %s)
                  ORDER BY run_invocation_id
                """,
                (
                    invocation.invocation_id,
                    run_uuid,
                    run.run_id,
                    invocation.ordinal,
                ),
            ).fetchall()
            if len(rows) != 1:
                raise DellAgentServerIdentityConflict(
                    "run_invocation_server_run_cardinality_conflict"
                )
            persisted = _invocation_from_row(rows[0])
            if (
                persisted.run_invocation_id != invocation.invocation_id
                or persisted.research_run_id != run.run_id
                or persisted.agent_session_id != run.session_id
                or persisted.invocation_ordinal != invocation.ordinal
                or persisted.canonical_invocation_kind
                != invocation.invocation_kind
                or persisted.server_invocation_kind != transport_kind
                or persisted.server_thread_id != thread_uuid
                or persisted.server_run_id != run_uuid
                or persisted.assistant_id != assistant
                or persisted.invocation_identity_digest != invocation_identity
                or persisted.first_server_status != server_status
            ):
                raise DellAgentServerIdentityConflict(
                    "run_invocation_server_run_binding_conflict"
                )
            if terminal_action is None:
                dispatched_row = connection.execute(
                    _ACTION_ATTEMPT_SELECT
                    + " WHERE run_invocation_id = %s AND action_state = 'DISPATCHED'",
                    (invocation.invocation_id,),
                ).fetchone()
                if dispatched_row is None:
                    raise DellAgentServerIdentityStoreError(
                        "run_create_action_dispatched_missing"
                    )
                try:
                    applied_action = create_run_create_action_applied(
                        _action_attempt_from_row(dispatched_row),
                        server_run_id=run_uuid,
                        server_observation_digest=observation_digest,
                    )
                except DellAgentServerRecoveryError as exc:
                    raise DellAgentServerIdentityStoreError(exc.code) from None
                _insert_action_attempt_snapshot(
                    connection,
                    run_invocation_id=invocation.invocation_id,
                    snapshot_ordinal=3,
                    action=applied_action,
                )
            final_binding_digest = persisted_run_binding_digest(persisted)
            lifecycle_ordinal = 3 + len(lifecycle.orphan_observations)
            reconciled_event_digest = _run_create_event_digest(
                run_invocation_id=pending.run_invocation_id,
                lifecycle_ordinal=lifecycle_ordinal,
                lifecycle_state="RECONCILED",
                research_run_id=pending.research_run_id,
                agent_session_id=pending.agent_session_id,
                invocation_ordinal=pending.invocation_ordinal,
                canonical_invocation_kind=pending.canonical_invocation_kind,
                server_invocation_kind=pending.server_invocation_kind,
                server_thread_id=pending.server_thread_id,
                assistant_id=pending.assistant_id,
                server_assistant_id=pending.server_assistant_id,
                execution_profile=pending.execution_profile,
                session_identity_digest=pending.session_identity_digest,
                research_run_identity_digest=pending.research_run_identity_digest,
                run_invocation_identity_digest=(
                    pending.run_invocation_identity_digest
                ),
                launch_request_digest=pending.launch_request_digest,
                server_metadata_digest=pending.server_metadata_digest,
                bound_run_invocation_id=pending.run_invocation_id,
                server_run_id=run_uuid,
                server_run_status=server_status,
                recovery_reason_code=reconciliation_reason,
                server_observation_digest=observation_digest,
                final_binding_digest=final_binding_digest,
            )
            connection.execute(
                """
                INSERT INTO fin_runtime.agent_server_run_create_lifecycle (
                    run_invocation_id, lifecycle_ordinal, lifecycle_state,
                    research_run_id, agent_session_id, invocation_ordinal,
                    canonical_invocation_kind, server_invocation_kind,
                    server_thread_id, assistant_id, server_assistant_id,
                    execution_profile, session_identity_digest,
                    research_run_identity_digest,
                    run_invocation_identity_digest, launch_request_digest,
                    server_metadata_digest, bound_run_invocation_id,
                    server_run_id, server_run_status, recovery_reason_code,
                    server_observation_digest, final_binding_digest,
                    lifecycle_event_digest
                )
                VALUES (
                    %s, %s, 'RECONCILED', %s, %s, %s, %s, %s, %s::uuid,
                    %s, %s::uuid, %s, %s, %s, %s, %s, %s,
                    %s, %s::uuid, %s, %s, %s, %s, %s
                )
                """,
                (
                    pending.run_invocation_id,
                    lifecycle_ordinal,
                    pending.research_run_id,
                    pending.agent_session_id,
                    pending.invocation_ordinal,
                    pending.canonical_invocation_kind,
                    pending.server_invocation_kind,
                    pending.server_thread_id,
                    pending.assistant_id,
                    pending.server_assistant_id,
                    pending.execution_profile,
                    pending.session_identity_digest,
                    pending.research_run_identity_digest,
                    pending.run_invocation_identity_digest,
                    pending.launch_request_digest,
                    pending.server_metadata_digest,
                    pending.run_invocation_id,
                    run_uuid,
                    server_status,
                    reconciliation_reason,
                    observation_digest,
                    final_binding_digest,
                    reconciled_event_digest,
                ),
            )
            persisted_lifecycle_rows = connection.execute(
                _RUN_CREATE_LIFECYCLE_SELECT
                + " WHERE run_invocation_id = %s ORDER BY lifecycle_ordinal",
                (invocation.invocation_id,),
            ).fetchall()
            persisted_lifecycle = _run_create_lifecycle_from_rows(
                persisted_lifecycle_rows
            )
            if (
                persisted_lifecycle is None
                or persisted_lifecycle.reconciled is None
                or persisted_lifecycle.reconciled.lifecycle_event_digest
                != reconciled_event_digest
                or persisted_lifecycle.reconciled.final_binding_digest
                != final_binding_digest
            ):
                raise DellAgentServerIdentityStoreError(
                    "run_create_reconciled_not_persisted"
                )
            return persisted

    def get_research_run_aggregate(
        self,
        *,
        research_run_id: str,
    ) -> PersistedResearchRunAggregate | None:
        run_id = _required_identifier(
            research_run_id,
            code="fin_research_run_id_invalid",
        )
        with self._transaction(
            failure_code="identity_run_aggregate_read_failed"
        ) as connection:
            run_row = connection.execute(
                _RUN_SELECT + " WHERE research_run_id = %s",
                (run_id,),
            ).fetchone()
            if run_row is None:
                return None
            run = _run_from_row(run_row)
            invocation_rows = connection.execute(
                _INVOCATION_SELECT
                + """
                  WHERE research_run_id = %s
                  ORDER BY invocation_ordinal, run_invocation_id
                """,
                (run_id,),
            ).fetchall()
            invocations = tuple(
                _invocation_from_row(row) for row in invocation_rows
            )
            if not invocations:
                raise DellAgentServerIdentityStoreError(
                    "research_run_server_run_aggregate_empty"
                )
            if any(
                item.research_run_id != run.research_run_id
                or item.agent_session_id != run.agent_session_id
                for item in invocations
            ):
                raise DellAgentServerIdentityStoreError(
                    "research_run_server_run_aggregate_corrupt"
                )
            ordinals = tuple(item.invocation_ordinal for item in invocations)
            if ordinals != tuple(range(1, len(ordinals) + 1)):
                raise DellAgentServerIdentityStoreError(
                    "research_run_invocation_sequence_not_contiguous"
                )
            return PersistedResearchRunAggregate(run, invocations)


class PostgresDellAgentServerRecoveryOperatorRepository:
    """Independent host-local authority for canonical recovery decisions only."""

    def __init__(
        self,
        connection_source: ConnectionPoolLike | ConnectionFactory,
    ) -> None:
        checkout = getattr(connection_source, "connection", None)
        if not callable(checkout) and not callable(connection_source):
            raise DellAgentServerIdentityStoreError(
                "recovery_operator_connection_source_required"
            )
        self._connection_source = connection_source

    @contextmanager
    def _transaction(self) -> Iterator[ConnectionLike]:
        try:
            pool_checkout = getattr(self._connection_source, "connection", None)
            connection_context = (
                pool_checkout()
                if callable(pool_checkout)
                else self._connection_source()
            )
            with connection_context as connection:
                _require_idle_connection(connection)
                with connection.transaction():
                    yield connection
                _require_idle_connection(connection)
        except DellAgentServerIdentityStoreError:
            raise
        except Exception:
            raise DellAgentServerIdentityStoreError(
                "recovery_operator_store_failed"
            ) from None

    def list_open_recovery_cases(
        self,
        *,
        limit: int = 100,
    ) -> tuple[DellAgentServerRecoveryCase, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise DellAgentServerIdentityStoreError(
                "recovery_operator_list_limit_invalid"
            )
        with self._transaction() as connection:
            rows = connection.execute(
                _RECOVERY_CASE_SELECT
                + """
                  AS recovery
                  LEFT JOIN fin_runtime.agent_server_recovery_dispositions AS disposition
                    ON disposition.recovery_case_id = recovery.recovery_case_id
                  WHERE disposition.recovery_case_id IS NULL
                  ORDER BY recovery.opened_at, recovery.recovery_case_id
                  LIMIT %s
                """,
                (limit,),
            ).fetchall()
            return tuple(_recovery_case_from_row(row) for row in rows)

    def get_recovery_case(
        self,
        *,
        recovery_case_id: str,
    ) -> DellAgentServerRecoveryCase | None:
        case_id = _required_identifier(
            recovery_case_id,
            code="run_create_recovery_case_id_invalid",
        )
        with self._transaction() as connection:
            row = connection.execute(
                _RECOVERY_CASE_SELECT + " WHERE recovery_case_id = %s",
                (case_id,),
            ).fetchone()
            return None if row is None else _recovery_case_from_row(row)

    def record_recovery_disposition(
        self,
        *,
        recovery_case_id: str,
        disposition: RecoveryDisposition,
        next_invocation: RunInvocation | None = None,
        replacement_action: ActionAttempt | None = None,
    ) -> RecoveryDisposition:
        case_id = _required_identifier(
            recovery_case_id,
            code="run_create_recovery_case_id_invalid",
        )
        with self._transaction() as connection:
            connection.execute(
                """
                SELECT pg_catalog.pg_advisory_xact_lock(
                    pg_catalog.hashtextextended(
                        'fin_runtime:recovery_case:' || %s,
                        %s
                    )
                )
                """,
                (case_id, _RUN_CREATE_LIFECYCLE_LOCK_SEED),
            )
            case_row = connection.execute(
                _RECOVERY_CASE_SELECT + " WHERE recovery_case_id = %s",
                (case_id,),
            ).fetchone()
            if case_row is None:
                raise DellAgentServerIdentityStoreError(
                    "run_create_recovery_case_missing"
                )
            recovery_case = _recovery_case_from_row(case_row)
            if disposition.decision not in {"DO_NOT_RETRY", "ABANDON_RUN"}:
                raise DellAgentServerIdentityStoreError(
                    "run_create_recovery_disposition_decision_unsupported"
                )
            if next_invocation is not None or replacement_action is not None:
                raise DellAgentServerIdentityStoreError(
                    "run_create_recovery_disposition_continuation_unsupported"
                )
            if disposition.decision == "DO_NOT_RETRY":
                lifecycle = _required_run_create_lifecycle(
                    connection,
                    run_invocation_id=(
                        recovery_case.source_invocation.invocation_id
                    ),
                )
                exact_observations = tuple(
                    observation
                    for observation in lifecycle.orphan_observations
                    if observation.server_run_id is not None
                    and observation.server_run_status is not None
                )
                if (
                    len({item.server_run_id for item in exact_observations}) != 1
                    or not exact_observations
                    or not any(
                        item.recorded_at <= disposition.created_at
                        for item in exact_observations
                    )
                ):
                    raise DellAgentServerIdentityStoreError(
                        "run_create_recovery_exact_observation_required"
                    )
            try:
                validated = validate_operator_disposition(
                    disposition,
                    recovery_case=recovery_case,
                    next_invocation=next_invocation,
                    replacement_action=replacement_action,
                )
            except DellAgentServerRecoveryError as exc:
                raise DellAgentServerIdentityStoreError(exc.code) from None
            existing_row = connection.execute(
                _RECOVERY_DISPOSITION_SELECT
                + " WHERE recovery_case_id = %s OR run_invocation_id = %s",
                (case_id, recovery_case.source_invocation.invocation_id),
            ).fetchone()
            if existing_row is not None:
                existing = _recovery_disposition_from_row(existing_row)
                if existing != validated:
                    raise DellAgentServerIdentityConflict(
                        "run_create_recovery_disposition_conflict"
                    )
                return existing
            append_row = connection.execute(
                """
                SELECT fin_runtime.append_recovery_disposition(
                    %s, %s::jsonb
                )
                """,
                (case_id, _canonical_model_json(validated)),
            ).fetchone()
            if (
                append_row is None
                or len(append_row) != 1
                or append_row[0] != validated.recovery_disposition_digest
            ):
                raise DellAgentServerIdentityStoreError(
                    "run_create_recovery_disposition_append_failed"
                )
            persisted_row = connection.execute(
                _RECOVERY_DISPOSITION_SELECT
                + " WHERE recovery_case_id = %s",
                (case_id,),
            ).fetchone()
            if persisted_row is None:
                raise DellAgentServerIdentityStoreError(
                    "run_create_recovery_disposition_not_persisted"
                )
            persisted = _recovery_disposition_from_row(persisted_row)
            if persisted != validated:
                raise DellAgentServerIdentityConflict(
                    "run_create_recovery_disposition_conflict"
                )
            return persisted


def _canonical_model_json(value: Any) -> str:
    return json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _insert_action_attempt_snapshot(
    connection: ConnectionLike,
    *,
    run_invocation_id: str,
    snapshot_ordinal: int,
    action: ActionAttempt,
) -> None:
    connection.execute(
        """
        INSERT INTO fin_runtime.agent_server_action_attempt_snapshots (
            run_invocation_id, snapshot_ordinal, action_state,
            action_outcome, action_attempt_id, action_attempt_digest,
            canonical_action_attempt
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            run_invocation_id,
            snapshot_ordinal,
            action.state,
            action.outcome,
            action.action_attempt_id,
            action.action_attempt_digest,
            _canonical_model_json(action),
        ),
    )


def _insert_run_create_lifecycle_event(
    connection: ConnectionLike,
    *,
    pending: PersistedRunCreateLifecycleEvent,
    lifecycle_ordinal: int,
    lifecycle_state: RunCreateLifecycleState,
    lifecycle_event_digest: str,
    server_run_id: str | None = None,
    server_run_status: str | None = None,
    recovery_reason_code: str | None = None,
    server_observation_digest: str | None = None,
    bound_run_invocation_id: str | None = None,
    final_binding_digest: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO fin_runtime.agent_server_run_create_lifecycle (
            run_invocation_id, lifecycle_ordinal, lifecycle_state,
            research_run_id, agent_session_id, invocation_ordinal,
            canonical_invocation_kind, server_invocation_kind,
            server_thread_id, assistant_id, server_assistant_id,
            execution_profile, session_identity_digest,
            research_run_identity_digest, run_invocation_identity_digest,
            launch_request_digest, server_metadata_digest,
            bound_run_invocation_id, server_run_id, server_run_status,
            recovery_reason_code, server_observation_digest,
            final_binding_digest, lifecycle_event_digest
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid, %s, %s::uuid,
            %s, %s, %s, %s, %s, %s, %s, %s::uuid, %s, %s, %s, %s, %s
        )
        """,
        (
            pending.run_invocation_id,
            lifecycle_ordinal,
            lifecycle_state,
            pending.research_run_id,
            pending.agent_session_id,
            pending.invocation_ordinal,
            pending.canonical_invocation_kind,
            pending.server_invocation_kind,
            pending.server_thread_id,
            pending.assistant_id,
            pending.server_assistant_id,
            pending.execution_profile,
            pending.session_identity_digest,
            pending.research_run_identity_digest,
            pending.run_invocation_identity_digest,
            pending.launch_request_digest,
            pending.server_metadata_digest,
            bound_run_invocation_id,
            server_run_id,
            server_run_status,
            recovery_reason_code,
            server_observation_digest,
            final_binding_digest,
            lifecycle_event_digest,
        ),
    )


def _required_run_create_lifecycle(
    connection: ConnectionLike,
    *,
    run_invocation_id: str,
) -> PersistedRunCreateLifecycle:
    rows = connection.execute(
        _RUN_CREATE_LIFECYCLE_SELECT
        + " WHERE run_invocation_id = %s ORDER BY lifecycle_ordinal",
        (run_invocation_id,),
    ).fetchall()
    lifecycle = _run_create_lifecycle_from_rows(rows)
    if lifecycle is None:
        raise DellAgentServerIdentityStoreError("run_create_pending_missing")
    return lifecycle


def _locked_run_create_lifecycle(
    connection: ConnectionLike,
    *,
    run_invocation_id: str,
) -> PersistedRunCreateLifecycle:
    initial = _required_run_create_lifecycle(
        connection,
        run_invocation_id=run_invocation_id,
    )
    connection.execute(
        """
        SELECT pg_catalog.pg_advisory_xact_lock(
            pg_catalog.hashtextextended(
                'fin_runtime:run_create:' || %s,
                %s
            )
        )
        """,
        (initial.pending.research_run_id, _RUN_CREATE_LIFECYCLE_LOCK_SEED),
    )
    return _required_run_create_lifecycle(
        connection,
        run_invocation_id=run_invocation_id,
    )


def _append_orphan_observation(
    connection: ConnectionLike,
    *,
    lifecycle: PersistedRunCreateLifecycle,
    recovery_reason_code: str,
    server_observation_digest: str,
    server_run_id: str | None,
    server_run_status: str | None,
) -> PersistedRunCreateLifecycle:
    if lifecycle.dispatched is None:
        raise DellAgentServerIdentityConflict("run_create_dispatched_missing")
    for observation in lifecycle.orphan_observations:
        if observation.server_observation_digest == server_observation_digest:
            if (
                observation.server_run_id != server_run_id
                or observation.server_run_status != server_run_status
                or observation.recovery_reason_code != recovery_reason_code
            ):
                raise DellAgentServerIdentityConflict(
                    "run_create_orphan_observation_conflict"
                )
            return lifecycle
    if lifecycle.reconciled is not None:
        raise DellAgentServerIdentityConflict(
            "run_create_orphan_after_reconciled"
        )
    known_ids = {
        observation.server_run_id
        for observation in lifecycle.orphan_observations
        if observation.server_run_id is not None
    }
    if server_run_id is not None and known_ids and known_ids != {server_run_id}:
        raise DellAgentServerIdentityConflict(
            "run_create_orphan_server_run_conflict"
        )
    pending = lifecycle.pending
    ordinal = 3 + len(lifecycle.orphan_observations)
    event_digest = _run_create_event_digest(
        run_invocation_id=pending.run_invocation_id,
        lifecycle_ordinal=ordinal,
        lifecycle_state="ORPHAN",
        research_run_id=pending.research_run_id,
        agent_session_id=pending.agent_session_id,
        invocation_ordinal=pending.invocation_ordinal,
        canonical_invocation_kind=pending.canonical_invocation_kind,
        server_invocation_kind=pending.server_invocation_kind,
        server_thread_id=pending.server_thread_id,
        assistant_id=pending.assistant_id,
        server_assistant_id=pending.server_assistant_id,
        execution_profile=pending.execution_profile,
        session_identity_digest=pending.session_identity_digest,
        research_run_identity_digest=pending.research_run_identity_digest,
        run_invocation_identity_digest=pending.run_invocation_identity_digest,
        launch_request_digest=pending.launch_request_digest,
        server_metadata_digest=pending.server_metadata_digest,
        bound_run_invocation_id=None,
        server_run_id=server_run_id,
        server_run_status=server_run_status,
        recovery_reason_code=recovery_reason_code,
        server_observation_digest=server_observation_digest,
        final_binding_digest=None,
    )
    _insert_run_create_lifecycle_event(
        connection,
        pending=pending,
        lifecycle_ordinal=ordinal,
        lifecycle_state="ORPHAN",
        lifecycle_event_digest=event_digest,
        server_run_id=server_run_id,
        server_run_status=server_run_status,
        recovery_reason_code=recovery_reason_code,
        server_observation_digest=server_observation_digest,
    )
    return _required_run_create_lifecycle(
        connection,
        run_invocation_id=pending.run_invocation_id,
    )


_SESSION_SELECT = """
    SELECT
        agent_session_id,
        fin_thread_id,
        server_thread_id::text,
        assistant_id,
        session_identity_digest,
        bound_at
    FROM fin_runtime.research_sessions
"""

_RUN_SELECT = """
    SELECT
        research_run_id,
        agent_session_id,
        parent_research_run_id,
        run_identity_digest,
        first_bound_at
    FROM fin_runtime.research_runs
"""

_INVOCATION_SELECT = """
    SELECT
        run_invocation_id,
        research_run_id,
        agent_session_id,
        invocation_ordinal,
        canonical_invocation_kind,
        server_invocation_kind,
        server_thread_id::text,
        server_run_id::text,
        assistant_id,
        invocation_identity_digest,
        first_server_status,
        bound_at
    FROM fin_runtime.research_run_invocations
"""

_RUN_CREATE_LIFECYCLE_SELECT = """
    SELECT
        run_invocation_id,
        lifecycle_ordinal,
        lifecycle_state,
        research_run_id,
        agent_session_id,
        invocation_ordinal,
        canonical_invocation_kind,
        server_invocation_kind,
        server_thread_id::text,
        assistant_id,
        server_assistant_id::text,
        execution_profile,
        session_identity_digest,
        research_run_identity_digest,
        run_invocation_identity_digest,
        launch_request_digest,
        server_metadata_digest,
        bound_run_invocation_id,
        server_run_id::text,
        server_run_status,
        recovery_reason_code,
        server_observation_digest,
        final_binding_digest,
        lifecycle_event_digest,
        recorded_at
    FROM fin_runtime.agent_server_run_create_lifecycle
"""

_ACTION_ATTEMPT_SELECT = """
    SELECT
        run_invocation_id,
        snapshot_ordinal,
        action_state,
        action_outcome,
        action_attempt_id,
        action_attempt_digest,
        canonical_action_attempt,
        recorded_at
    FROM fin_runtime.agent_server_action_attempt_snapshots
"""

_RECOVERY_CASE_SELECT = """
    SELECT
        recovery_case_id,
        run_invocation_id,
        research_run_id,
        agent_session_id,
        recovery_research_run_digest,
        source_run_invocation_digest,
        ambiguous_action_attempt_id,
        ambiguous_action_attempt_digest,
        lifecycle_event_digest,
        recovery_reason_code,
        server_run_id::text,
        server_run_status,
        canonical_recovery_research_run,
        canonical_source_run_invocation,
        canonical_ambiguous_action_attempt,
        opened_at,
        recovery_case_digest
    FROM fin_runtime.agent_server_recovery_cases
"""

_RECOVERY_DISPOSITION_SELECT = """
    SELECT
        recovery_disposition_id,
        recovery_case_id,
        run_invocation_id,
        recovery_decision,
        recovery_disposition_digest,
        canonical_recovery_disposition,
        recorded_at
    FROM fin_runtime.agent_server_recovery_dispositions
"""


def _json_object(value: Any, *, code: str) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            raise DellAgentServerIdentityStoreError(code) from None
    if not isinstance(value, dict):
        raise DellAgentServerIdentityStoreError(code)
    return value


def _action_attempt_from_row(row: Sequence[Any]) -> ActionAttempt:
    if len(row) != 8:
        raise DellAgentServerIdentityStoreError(
            "run_create_action_snapshot_row_invalid"
        )
    invocation_id = _required_identifier(
        row[0], code="fin_run_invocation_id_invalid"
    )
    snapshot_ordinal = _positive_int(
        row[1], code="run_create_action_snapshot_ordinal_invalid"
    )
    state = row[2]
    outcome = row[3]
    try:
        action = ActionAttempt.model_validate_json(
            json.dumps(
                _json_object(
                    row[6], code="run_create_action_snapshot_invalid"
                )
            )
        )
    except DellAgentServerIdentityStoreError:
        raise
    except Exception:
        raise DellAgentServerIdentityStoreError(
            "run_create_action_snapshot_invalid"
        ) from None
    expected_ordinal = {
        "INTENT_COMMITTED": 1,
        "DISPATCHED": 2,
        "TERMINAL": 2 if action.outcome == "FAILED_BEFORE_DISPATCH" else 3,
    }.get(action.state)
    if (
        state != action.state
        or outcome != action.outcome
        or row[4] != action.action_attempt_id
        or row[5] != action.action_attempt_digest
        or action.run_invocation_id != invocation_id
        or snapshot_ordinal != expected_ordinal
    ):
        raise DellAgentServerIdentityStoreError(
            "run_create_action_snapshot_column_mismatch"
        )
    _aware_datetime(row[7], code="run_create_action_snapshot_time_invalid")
    return action


def _recovery_case_from_row(row: Sequence[Any]) -> DellAgentServerRecoveryCase:
    if len(row) != 17:
        raise DellAgentServerIdentityStoreError(
            "run_create_recovery_case_row_invalid"
        )
    try:
        recovery_run = ResearchRun.model_validate_json(
            json.dumps(
                _json_object(row[12], code="run_create_recovery_run_invalid")
            )
        )
        source_invocation = RunInvocation.model_validate_json(
            json.dumps(
                _json_object(
                    row[13], code="run_create_recovery_invocation_invalid"
                )
            )
        )
        ambiguous_action = ActionAttempt.model_validate_json(
            json.dumps(
                _json_object(row[14], code="run_create_recovery_action_invalid")
            )
        )
        recovery_case = DellAgentServerRecoveryCase(
            recovery_case_id=_required_identifier(
                row[0], code="run_create_recovery_case_id_invalid"
            ),
            research_run=recovery_run,
            source_invocation=source_invocation,
            ambiguous_action=ambiguous_action,
            lifecycle_event_digest=_digest(
                row[8], code="run_create_recovery_lifecycle_digest_invalid"
            ),
            recovery_reason_code=_required_identifier(
                row[9],
                code="run_create_recovery_reason_invalid",
                maximum=120,
            ),
            server_run_id=(
                None
                if row[10] is None
                else _server_uuid(row[10], code="agent_server_run_id_invalid")
            ),
            server_run_status=(
                None if row[11] is None else _server_run_status(row[11])
            ),
            opened_at=_aware_datetime(
                row[15], code="run_create_recovery_opened_at_invalid"
            ),
            recovery_case_digest=_digest(
                row[16], code="run_create_recovery_case_digest_invalid"
            ),
        )
    except DellAgentServerIdentityStoreError:
        raise
    except DellAgentServerRecoveryError as exc:
        raise DellAgentServerIdentityStoreError(exc.code) from None
    except Exception:
        raise DellAgentServerIdentityStoreError(
            "run_create_recovery_case_invalid"
        ) from None
    if (
        row[1] != source_invocation.invocation_id
        or row[2] != recovery_run.run_id
        or row[3] != recovery_run.session_id
        or row[4] != recovery_run.run_digest
        or row[5] != source_invocation.invocation_digest
        or row[6] != ambiguous_action.action_attempt_id
        or row[7] != ambiguous_action.action_attempt_digest
    ):
        raise DellAgentServerIdentityStoreError(
            "run_create_recovery_case_column_mismatch"
        )
    return recovery_case


def _recovery_disposition_from_row(row: Sequence[Any]) -> RecoveryDisposition:
    if len(row) != 7:
        raise DellAgentServerIdentityStoreError(
            "run_create_recovery_disposition_row_invalid"
        )
    try:
        disposition = RecoveryDisposition.model_validate_json(
            json.dumps(
                _json_object(
                    row[5], code="run_create_recovery_disposition_invalid"
                )
            )
        )
    except DellAgentServerIdentityStoreError:
        raise
    except Exception:
        raise DellAgentServerIdentityStoreError(
            "run_create_recovery_disposition_invalid"
        ) from None
    if (
        row[0] != disposition.recovery_disposition_id
        or row[3] != disposition.decision
        or row[4] != disposition.recovery_disposition_digest
        or row[2] != disposition.source_run_invocation_id
    ):
        raise DellAgentServerIdentityStoreError(
            "run_create_recovery_disposition_column_mismatch"
        )
    _required_identifier(row[1], code="run_create_recovery_case_id_invalid")
    _aware_datetime(
        row[6], code="run_create_recovery_disposition_recorded_at_invalid"
    )
    return disposition


def _session_from_row(row: Sequence[Any]) -> PersistedAgentSessionBinding:
    if len(row) != 6:
        raise DellAgentServerIdentityStoreError("identity_session_row_invalid")
    return PersistedAgentSessionBinding(
        agent_session_id=_required_identifier(
            row[0], code="identity_session_id_invalid"
        ),
        fin_thread_id=_required_identifier(
            row[1], code="identity_fin_thread_id_invalid"
        ),
        server_thread_id=_server_uuid(
            row[2], code="identity_session_server_thread_invalid"
        ),
        assistant_id=_assistant_id(row[3]),
        session_identity_digest=_digest(
            row[4], code="identity_session_digest_invalid"
        ),
        bound_at=_aware_datetime(row[5], code="identity_session_bound_at_invalid"),
    )


def _run_from_row(row: Sequence[Any]) -> PersistedResearchRunIdentity:
    if len(row) != 5:
        raise DellAgentServerIdentityStoreError("identity_run_row_invalid")
    return PersistedResearchRunIdentity(
        research_run_id=_required_identifier(
            row[0], code="identity_research_run_id_invalid"
        ),
        agent_session_id=_required_identifier(
            row[1], code="identity_run_session_id_invalid"
        ),
        parent_research_run_id=(
            None
            if row[2] is None
            else _required_identifier(
                row[2], code="identity_parent_research_run_id_invalid"
            )
        ),
        run_identity_digest=_digest(row[3], code="identity_run_digest_invalid"),
        first_bound_at=_aware_datetime(
            row[4], code="identity_run_bound_at_invalid"
        ),
    )


def _invocation_from_row(row: Sequence[Any]) -> PersistedRunInvocationBinding:
    if len(row) != 12:
        raise DellAgentServerIdentityStoreError("identity_invocation_row_invalid")
    canonical_kind = row[4]
    if canonical_kind not in {"START", "RESUME", "RECOVERY"}:
        raise DellAgentServerIdentityStoreError(
            "identity_invocation_kind_invalid"
        )
    server_kind = _server_invocation_kind(row[5])
    expected_server_kind = "start" if canonical_kind == "START" else "resume"
    if server_kind != expected_server_kind:
        raise DellAgentServerIdentityStoreError(
            "identity_invocation_transport_kind_corrupt"
        )
    return PersistedRunInvocationBinding(
        run_invocation_id=_required_identifier(
            row[0], code="identity_run_invocation_id_invalid"
        ),
        research_run_id=_required_identifier(
            row[1], code="identity_invocation_run_id_invalid"
        ),
        agent_session_id=_required_identifier(
            row[2], code="identity_invocation_session_id_invalid"
        ),
        invocation_ordinal=_positive_int(
            row[3], code="identity_invocation_ordinal_invalid"
        ),
        canonical_invocation_kind=canonical_kind,
        server_invocation_kind=server_kind,
        server_thread_id=_server_uuid(
            row[6], code="identity_invocation_thread_invalid"
        ),
        server_run_id=_server_uuid(
            row[7], code="identity_invocation_run_uuid_invalid"
        ),
        assistant_id=_assistant_id(row[8]),
        invocation_identity_digest=_digest(
            row[9], code="identity_invocation_digest_invalid"
        ),
        first_server_status=_required_identifier(
            row[10],
            code="identity_invocation_server_status_invalid",
            maximum=80,
        ),
        bound_at=_aware_datetime(
            row[11], code="identity_invocation_bound_at_invalid"
        ),
    )


def _run_create_event_from_row(
    row: Sequence[Any],
) -> PersistedRunCreateLifecycleEvent:
    if len(row) != 25:
        raise DellAgentServerIdentityStoreError(
            "run_create_lifecycle_row_invalid"
        )
    state = row[2]
    if state not in {"PENDING", "DISPATCHED", "ORPHAN", "RECONCILED"}:
        raise DellAgentServerIdentityStoreError(
            "run_create_lifecycle_state_invalid"
        )
    canonical_kind = row[6]
    if canonical_kind not in {"START", "RESUME", "RECOVERY"}:
        raise DellAgentServerIdentityStoreError(
            "run_create_lifecycle_invocation_kind_invalid"
        )
    server_kind = _server_invocation_kind(row[7])
    expected_server_kind = "start" if canonical_kind == "START" else "resume"
    if server_kind != expected_server_kind:
        raise DellAgentServerIdentityStoreError(
            "run_create_lifecycle_transport_kind_corrupt"
        )
    event = PersistedRunCreateLifecycleEvent(
        run_invocation_id=_required_identifier(
            row[0], code="run_create_lifecycle_invocation_id_invalid"
        ),
        lifecycle_ordinal=_positive_int(
            row[1], code="run_create_lifecycle_ordinal_invalid"
        ),
        lifecycle_state=state,
        research_run_id=_required_identifier(
            row[3], code="run_create_lifecycle_run_id_invalid"
        ),
        agent_session_id=_required_identifier(
            row[4], code="run_create_lifecycle_session_id_invalid"
        ),
        invocation_ordinal=_positive_int(
            row[5], code="run_create_lifecycle_invocation_ordinal_invalid"
        ),
        canonical_invocation_kind=canonical_kind,
        server_invocation_kind=server_kind,
        server_thread_id=_server_uuid(
            row[8], code="run_create_lifecycle_thread_id_invalid"
        ),
        assistant_id=_assistant_id(row[9]),
        server_assistant_id=_server_uuid(
            row[10], code="run_create_lifecycle_server_assistant_id_invalid"
        ),
        execution_profile=_execution_profile(row[11]),
        session_identity_digest=_digest(
            row[12], code="run_create_lifecycle_session_digest_invalid"
        ),
        research_run_identity_digest=_digest(
            row[13], code="run_create_lifecycle_run_digest_invalid"
        ),
        run_invocation_identity_digest=_digest(
            row[14], code="run_create_lifecycle_invocation_digest_invalid"
        ),
        launch_request_digest=_digest(
            row[15], code="run_create_lifecycle_launch_digest_invalid"
        ),
        server_metadata_digest=_digest(
            row[16], code="run_create_lifecycle_metadata_digest_invalid"
        ),
        bound_run_invocation_id=(
            None
            if row[17] is None
            else _required_identifier(
                row[17], code="run_create_lifecycle_bound_invocation_invalid"
            )
        ),
        server_run_id=(
            None
            if row[18] is None
            else _server_uuid(
                row[18], code="run_create_lifecycle_server_run_id_invalid"
            )
        ),
        server_run_status=(
            None
            if row[19] is None
            else _required_identifier(
                row[19],
                code="run_create_lifecycle_server_status_invalid",
                maximum=80,
            )
        ),
        recovery_reason_code=(
            None
            if row[20] is None
            else _required_identifier(
                row[20],
                code="run_create_lifecycle_recovery_reason_invalid",
                maximum=120,
            )
        ),
        server_observation_digest=(
            None
            if row[21] is None
            else _digest(
                row[21], code="run_create_lifecycle_observation_digest_invalid"
            )
        ),
        final_binding_digest=(
            None
            if row[22] is None
            else _digest(
                row[22], code="run_create_lifecycle_final_digest_invalid"
            )
        ),
        lifecycle_event_digest=_digest(
            row[23], code="run_create_lifecycle_event_digest_invalid"
        ),
        recorded_at=_aware_datetime(
            row[24], code="run_create_lifecycle_recorded_at_invalid"
        ),
    )
    if event.server_run_status is not None and event.server_run_id is None:
        raise DellAgentServerIdentityStoreError(
            "run_create_lifecycle_remote_identity_incomplete"
        )
    if state == "PENDING":
        valid_shape = (
            event.lifecycle_ordinal == 1
            and event.bound_run_invocation_id is None
            and event.server_run_id is None
            and event.server_run_status is None
            and event.recovery_reason_code is None
            and event.server_observation_digest is None
            and event.final_binding_digest is None
        )
    elif state == "DISPATCHED":
        valid_shape = (
            event.lifecycle_ordinal == 2
            and event.bound_run_invocation_id is None
            and event.server_run_id is None
            and event.server_run_status is None
            and event.recovery_reason_code is None
            and event.server_observation_digest is None
            and event.final_binding_digest is None
        )
    elif state == "ORPHAN":
        valid_shape = (
            event.lifecycle_ordinal >= 3
            and event.bound_run_invocation_id is None
            and event.recovery_reason_code is not None
            and event.server_observation_digest is not None
            and event.final_binding_digest is None
        )
    else:
        valid_shape = (
            event.lifecycle_ordinal >= 3
            and event.bound_run_invocation_id == event.run_invocation_id
            and event.server_run_id is not None
            and event.server_run_status is not None
            and event.recovery_reason_code is not None
            and event.server_observation_digest is not None
            and event.final_binding_digest is not None
        )
    if not valid_shape:
        raise DellAgentServerIdentityStoreError(
            "run_create_lifecycle_transition_shape_invalid"
        )
    expected_digest = _run_create_event_digest(
        run_invocation_id=event.run_invocation_id,
        lifecycle_ordinal=event.lifecycle_ordinal,
        lifecycle_state=event.lifecycle_state,
        research_run_id=event.research_run_id,
        agent_session_id=event.agent_session_id,
        invocation_ordinal=event.invocation_ordinal,
        canonical_invocation_kind=event.canonical_invocation_kind,
        server_invocation_kind=event.server_invocation_kind,
        server_thread_id=event.server_thread_id,
        assistant_id=event.assistant_id,
        server_assistant_id=event.server_assistant_id,
        execution_profile=event.execution_profile,
        session_identity_digest=event.session_identity_digest,
        research_run_identity_digest=event.research_run_identity_digest,
        run_invocation_identity_digest=event.run_invocation_identity_digest,
        launch_request_digest=event.launch_request_digest,
        server_metadata_digest=event.server_metadata_digest,
        bound_run_invocation_id=event.bound_run_invocation_id,
        server_run_id=event.server_run_id,
        server_run_status=event.server_run_status,
        recovery_reason_code=event.recovery_reason_code,
        server_observation_digest=event.server_observation_digest,
        final_binding_digest=event.final_binding_digest,
    )
    if event.lifecycle_event_digest != expected_digest:
        raise DellAgentServerIdentityStoreError(
            "run_create_lifecycle_event_digest_mismatch"
        )
    return event


def _run_create_lifecycle_from_rows(
    rows: Sequence[Sequence[Any]],
) -> PersistedRunCreateLifecycle | None:
    if not rows:
        return None
    events = tuple(_run_create_event_from_row(row) for row in rows)
    states = tuple(event.lifecycle_state for event in events)
    if (
        not states
        or states[0] != "PENDING"
        or states.count("PENDING") != 1
        or states.count("DISPATCHED") > 1
        or states.count("RECONCILED") > 1
        or any(state not in {"PENDING", "DISPATCHED", "ORPHAN", "RECONCILED"} for state in states)
        or ("DISPATCHED" in states and states[1] != "DISPATCHED")
        or ("ORPHAN" in states and "DISPATCHED" not in states)
        or ("RECONCILED" in states and "DISPATCHED" not in states)
        or ("RECONCILED" in states and states[-1] != "RECONCILED")
    ):
        raise DellAgentServerIdentityStoreError(
            "run_create_lifecycle_sequence_invalid"
        )
    if tuple(event.lifecycle_ordinal for event in events) != tuple(
        range(1, len(events) + 1)
    ):
        raise DellAgentServerIdentityStoreError(
            "run_create_lifecycle_ordinal_sequence_invalid"
        )
    pending = events[0]
    common_fields = (
        "run_invocation_id",
        "research_run_id",
        "agent_session_id",
        "invocation_ordinal",
        "canonical_invocation_kind",
        "server_invocation_kind",
        "server_thread_id",
        "assistant_id",
        "server_assistant_id",
        "execution_profile",
        "session_identity_digest",
        "research_run_identity_digest",
        "run_invocation_identity_digest",
        "launch_request_digest",
        "server_metadata_digest",
    )
    if any(
        any(getattr(event, field) != getattr(pending, field) for field in common_fields)
        for event in events[1:]
    ):
        raise DellAgentServerIdentityStoreError(
            "run_create_lifecycle_identity_drift"
        )
    dispatched = next(
        (event for event in events if event.lifecycle_state == "DISPATCHED"),
        None,
    )
    orphans = tuple(
        event for event in events if event.lifecycle_state == "ORPHAN"
    )
    orphan = orphans[-1] if orphans else None
    reconciled = next(
        (event for event in events if event.lifecycle_state == "RECONCILED"),
        None,
    )
    if (
        any(item.server_run_id is not None for item in orphans)
        and reconciled is not None
        and any(
            item.server_run_id != reconciled.server_run_id
            for item in orphans
            if item.server_run_id is not None
        )
    ):
        raise DellAgentServerIdentityStoreError(
            "run_create_lifecycle_server_run_drift"
        )
    return PersistedRunCreateLifecycle(
        pending=pending,
        orphan=orphan,
        reconciled=reconciled,
        dispatched=dispatched,
        orphan_observations=orphans,
    )


def _pending_event_matches(
    event: PersistedRunCreateLifecycleEvent,
    *,
    research_run: ResearchRun,
    run_invocation: RunInvocation,
    server_thread_id: str,
    server_invocation_kind: Literal["start", "resume"],
    assistant_id: str,
    server_assistant_id: str,
    execution_profile: str,
    session_identity_digest: str,
    launch_request_digest: str,
    server_metadata_digest: str,
) -> bool:
    return (
        event.lifecycle_state == "PENDING"
        and event.run_invocation_id == run_invocation.invocation_id
        and event.research_run_id == research_run.run_id
        and event.agent_session_id == research_run.session_id
        and event.agent_session_id == run_invocation.session_id
        and event.invocation_ordinal == run_invocation.ordinal
        and event.canonical_invocation_kind == run_invocation.invocation_kind
        and event.server_invocation_kind == server_invocation_kind
        and event.server_thread_id == server_thread_id
        and event.assistant_id == assistant_id
        and event.server_assistant_id == server_assistant_id
        and event.execution_profile == execution_profile
        and event.session_identity_digest == session_identity_digest
        and event.research_run_identity_digest
        == research_run_identity_digest(research_run)
        and event.run_invocation_identity_digest
        == run_invocation_identity_digest(run_invocation)
        and event.launch_request_digest == launch_request_digest
        and event.server_metadata_digest == server_metadata_digest
    )


def _required_identifier(
    value: Any,
    *,
    code: str,
    maximum: int = 180,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
    ):
        raise DellAgentServerIdentityStoreError(code)
    return value


def _server_uuid(value: Any, *, code: str) -> str:
    identifier = _required_identifier(value, code=code, maximum=36)
    try:
        parsed = UUID(identifier)
    except (TypeError, ValueError, AttributeError):
        raise DellAgentServerIdentityStoreError(code) from None
    if str(parsed) != identifier.lower():
        raise DellAgentServerIdentityStoreError(code)
    return str(parsed)


def _assistant_id(value: Any) -> str:
    assistant = _required_identifier(
        value,
        code="agent_server_assistant_id_invalid",
    )
    if assistant != DELL_AGENT_SERVER_ASSISTANT_ID:
        raise DellAgentServerIdentityStoreError(
            "agent_server_assistant_id_invalid"
        )
    return assistant


def _server_invocation_kind(value: Any) -> Literal["start", "resume"]:
    if value not in {"start", "resume"}:
        raise DellAgentServerIdentityStoreError(
            "agent_server_invocation_kind_invalid"
        )
    return value


def _server_run_status(value: Any) -> str:
    status = _required_identifier(
        value,
        code="agent_server_run_status_invalid",
        maximum=80,
    )
    if status not in _ALLOWED_SERVER_RUN_STATUSES:
        raise DellAgentServerIdentityStoreError(
            "agent_server_run_status_invalid"
        )
    return status


def _execution_profile(value: Any) -> str:
    profile = _required_identifier(
        value,
        code="agent_server_execution_profile_invalid",
        maximum=80,
    )
    if profile not in {"product", "zero_model_control_plane_v1"}:
        raise DellAgentServerIdentityStoreError(
            "agent_server_execution_profile_invalid"
        )
    return profile


def _digest(value: Any, *, code: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise DellAgentServerIdentityStoreError(code)
    return value


def _positive_int(value: Any, *, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DellAgentServerIdentityStoreError(code)
    return value


def _nonnegative_int(value: Any, *, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DellAgentServerIdentityStoreError(code)
    return value


def _require_idle_connection(connection: ConnectionLike) -> None:
    status = getattr(getattr(connection, "info", None), "transaction_status", None)
    if status != 0 and getattr(status, "name", None) != "IDLE":
        raise DellAgentServerIdentityStoreError(
            "identity_store_connection_not_idle"
        )


def _aware_datetime(value: Any, *, code: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise DellAgentServerIdentityStoreError(code)
    return value


__all__ = [
    "ConnectionFactory",
    "ConnectionLike",
    "ConnectionPoolLike",
    "DELL_AGENT_SERVER_ASSISTANT_ID",
    "DellAgentServerIdentityConflict",
    "DellAgentServerIdentityRepository",
    "DellAgentServerIdentityStoreError",
    "FIN_RUNTIME_SCHEMA",
    "IDENTITY_SCHEMA_RESOURCE",
    "IDENTITY_SCHEMA_SHA256",
    "PersistedAgentSessionBinding",
    "PersistedExecutableRunBinding",
    "PersistedResearchRunAggregate",
    "PersistedResearchRunIdentity",
    "PersistedRunCreateLifecycle",
    "PersistedRunCreateLifecycleEvent",
    "PersistedRunCreateRegistration",
    "PersistedRunInvocationBinding",
    "PostgresDellAgentServerIdentityRepository",
    "REMOTE_CREATE_LIFECYCLE_SCHEMA_RESOURCE",
    "REMOTE_CREATE_LIFECYCLE_SCHEMA_SHA256",
    "RunCreateLifecycleState",
    "agent_session_identity_digest",
    "load_identity_schema_sql",
    "load_remote_create_lifecycle_schema_sql",
    "persisted_run_binding_digest",
    "research_run_identity_digest",
    "run_invocation_identity_digest",
    "validate_agent_session",
    "validate_research_run",
    "validate_run_invocation",
]
