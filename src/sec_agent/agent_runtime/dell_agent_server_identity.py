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
import re
from typing import Any, Literal, Protocol
from uuid import UUID

from sec_agent.canonical_runtime.contracts_v1_2 import (
    AgentSessionV1_2,
    ResearchRun,
    RunInvocation,
    canonical_json_sha256,
)


FIN_RUNTIME_SCHEMA = "fin_runtime"
IDENTITY_SCHEMA_RESOURCE = "sql/001_dell_agent_server_identity_v1_0.sql"
IDENTITY_SCHEMA_SHA256 = (
    "8102f5ab615bd616f64bd83f610b2e3c3206a9de023d7e27a48069f39e864209"
)
DELL_AGENT_SERVER_ASSISTANT_ID = "dell_reference_vertical"
_RUN_INVOCATION_LOCK_SEED = 20260903

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

    def bind_run_invocation(
        self,
        *,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        server_thread_id: str,
        server_run_id: str,
        server_invocation_kind: Literal["start", "resume"],
        first_server_status: str,
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
        """Install the idempotent DDL in one caller-connection transaction."""

        sql = load_identity_schema_sql()
        if _TOP_LEVEL_TRANSACTION_CONTROL_RE.search(sql):
            raise DellAgentServerIdentityStoreError(
                "identity_schema_embeds_transaction_control"
            )
        with self._transaction(
            failure_code="identity_schema_install_failed"
        ) as connection:
            connection.execute(sql)

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

    def bind_run_invocation(
        self,
        *,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        server_thread_id: str,
        server_run_id: str,
        server_invocation_kind: Literal["start", "resume"],
        first_server_status: str,
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
        server_status = _required_identifier(
            first_server_status,
            code="agent_server_run_status_invalid",
            maximum=80,
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
            ):
                raise DellAgentServerIdentityConflict(
                    "run_invocation_server_run_binding_conflict"
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
    "PersistedResearchRunAggregate",
    "PersistedResearchRunIdentity",
    "PersistedRunInvocationBinding",
    "PostgresDellAgentServerIdentityRepository",
    "agent_session_identity_digest",
    "load_identity_schema_sql",
    "research_run_identity_digest",
    "run_invocation_identity_digest",
    "validate_agent_session",
    "validate_research_run",
    "validate_run_invocation",
]
