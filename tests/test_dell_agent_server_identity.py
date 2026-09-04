from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Sequence

import pytest

from scripts.research import qualify_dell_agent_server_identity_postgres_v1
from sec_agent.agent_runtime import dell_agent_server_identity as identity
from sec_agent.agent_runtime.dell_agent_server_identity import (
    DellAgentServerIdentityConflict,
    DellAgentServerIdentityStoreError,
    PostgresDellAgentServerIdentityRepository,
    agent_session_identity_digest,
    load_identity_schema_sql,
    load_remote_create_lifecycle_schema_sql,
    persisted_run_binding_digest,
    research_run_identity_digest,
    run_invocation_identity_digest,
)
from sec_agent.agent_runtime.dell_agent_server_recovery import (
    create_run_create_action_dispatched,
    create_run_create_action_intent,
)
from sec_agent.canonical_runtime.contracts_v1_2 import (
    AgentSessionV1_2,
    ResearchRun,
    RunInvocation,
    create_agent_session_v1_2,
    create_research_run,
    create_run_invocation,
)


NOW = datetime(2026, 9, 3, 2, 0, tzinfo=timezone.utc)
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64
THREAD_ID = "01a065aa-23ec-72f3-bf4e-09cf92ac08c7"
START_RUN_ID = "01a065aa-7091-7a93-8153-7956fb32f946"
RESUME_RUN_ID = "01a065aa-7311-7e62-b147-93aca9a4ee82"
SERVER_ASSISTANT_ID = "01a065aa-34a7-7c62-a4ef-e8ce75a0ac3f"
LAUNCH_DIGEST = "d" * 64
METADATA_DIGEST = "e" * 64
OBSERVATION_DIGEST = "f" * 64


class _Cursor:
    def __init__(self, rows: Sequence[Sequence[Any]]) -> None:
        self._rows = list(rows)

    def fetchone(self) -> Sequence[Any] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[Sequence[Any]]:
        return list(self._rows)


class _Transaction(AbstractContextManager[None]):
    def __init__(self, connection: "_ScriptedConnection") -> None:
        self._connection = connection

    def __enter__(self) -> None:
        self._connection.transaction_entries += 1
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        if exc_type is None:
            self._connection.transaction_commits += 1
        else:
            self._connection.transaction_rollbacks += 1
        return None


class _ScriptedConnection:
    def __init__(self, results: Sequence[Sequence[Sequence[Any]]] = ()) -> None:
        self._results = [list(rows) for rows in results]
        self.executed: list[tuple[str, tuple[Any, ...] | None]] = []
        self.transaction_entries = 0
        self.transaction_commits = 0
        self.transaction_rollbacks = 0
        self.info = type("ConnectionInfo", (), {"transaction_status": 0})()

    def execute(
        self,
        query: str,
        params: Sequence[Any] | None = None,
    ) -> _Cursor:
        self.executed.append(
            (query, None if params is None else tuple(params))
        )
        rows = self._results.pop(0) if self._results else []
        return _Cursor(rows)

    def transaction(self) -> _Transaction:
        return _Transaction(self)


class _ConnectionCheckout(AbstractContextManager[_ScriptedConnection]):
    def __init__(self, pool: "_ScriptedPool") -> None:
        self._pool = pool

    def __enter__(self) -> _ScriptedConnection:
        self._pool.checkout_count += 1
        return self._pool.connection_value

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        return None


class _ScriptedPool:
    def __init__(self, connection: _ScriptedConnection) -> None:
        self.connection_value = connection
        self.checkout_count = 0

    def connection(self) -> _ConnectionCheckout:
        return _ConnectionCheckout(self)


def _repository(
    connection: _ScriptedConnection,
) -> PostgresDellAgentServerIdentityRepository:
    return PostgresDellAgentServerIdentityRepository(_ScriptedPool(connection))


def _session(**overrides: Any) -> AgentSessionV1_2:
    fields = {
        "session_id": "SESSION::DELL::DURABLE-001",
        "thread_id": "THREAD::DELL::DURABLE-001",
        "case_id": "DELL_AI_INFRA_REFERENCE_VERTICAL",
        "case_version": "FIN_0_1_3",
        "as_of_date": date(2026, 9, 3),
        "objective_ref": "objective://dell/durable-identity",
        "objective_digest": DIGEST_A,
        "data_snapshot_ref": "snapshot://dell/owner-accepted",
        "data_snapshot_digest": DIGEST_B,
        "runtime_policy_ref": "policy://dell/runtime/v1",
        "runtime_policy_digest": DIGEST_C,
        "authority_refs": ("authority://owner/data-gate",),
        "active_plan_ref": "plan://dell/1",
        "active_plan_digest": DIGEST_A,
        "status": "ACTIVE",
        "created_at": NOW,
        "updated_at": NOW,
    }
    fields.update(overrides)
    return create_agent_session_v1_2(**fields)


def _run(session: AgentSessionV1_2 | None = None, **overrides: Any) -> ResearchRun:
    session = session or _session()
    fields = {
        "run_id": "RUN::DELL::DURABLE-001",
        "session_id": session.session_id,
        "parent_run_id": None,
        "origin_kind": "INITIAL",
        "legacy_paid_full_chain_execution_label": None,
        "status": "RUNNING",
        "base_plan_ref": session.active_plan_ref,
        "base_plan_digest": session.active_plan_digest,
        "current_plan_ref": session.active_plan_ref,
        "current_plan_digest": session.active_plan_digest,
        "last_session_sequence": 0,
        "created_at": NOW,
        "terminal_at": None,
    }
    fields.update(overrides)
    return create_research_run(**fields)


def _invocation(
    session: AgentSessionV1_2 | None = None,
    run: ResearchRun | None = None,
    *,
    resume: bool = False,
    **overrides: Any,
) -> RunInvocation:
    session = session or _session()
    run = run or _run(session)
    fields = {
        "invocation_id": (
            "INVOCATION::DELL::DURABLE-002"
            if resume
            else "INVOCATION::DELL::DURABLE-001"
        ),
        "session_id": session.session_id,
        "run_id": run.run_id,
        "ordinal": 2 if resume else 1,
        "invocation_kind": "RESUME" if resume else "START",
        "status": "RUNNING",
        "trigger_ref": "command://resume/2" if resume else "command://start/1",
        "lease_ref": "lease://agent-server/2" if resume else "lease://agent-server/1",
        "started_at": NOW + (timedelta(minutes=1) if resume else timedelta()),
        "finished_at": None,
    }
    fields.update(overrides)
    return create_run_invocation(**fields)


def _session_row(
    session: AgentSessionV1_2 | None = None,
    *,
    server_thread_id: str = THREAD_ID,
) -> tuple[Any, ...]:
    session = session or _session()
    stable_digest = agent_session_identity_digest(session)
    return (
        session.session_id,
        session.thread_id,
        server_thread_id,
        identity.DELL_AGENT_SERVER_ASSISTANT_ID,
        stable_digest,
        NOW,
    )


def _run_row(run: ResearchRun | None = None) -> tuple[Any, ...]:
    run = run or _run()
    return (
        run.run_id,
        run.session_id,
        run.parent_run_id,
        research_run_identity_digest(run),
        NOW,
    )


def _invocation_row(
    invocation: RunInvocation | None = None,
    *,
    server_thread_id: str = THREAD_ID,
    server_run_id: str = START_RUN_ID,
    server_kind: str = "start",
) -> tuple[Any, ...]:
    invocation = invocation or _invocation()
    stable_digest = run_invocation_identity_digest(invocation)
    return (
        invocation.invocation_id,
        invocation.run_id,
        invocation.session_id,
        invocation.ordinal,
        invocation.invocation_kind,
        server_kind,
        server_thread_id,
        server_run_id,
        identity.DELL_AGENT_SERVER_ASSISTANT_ID,
        stable_digest,
        "pending",
        NOW,
    )


def _lifecycle_row(
    *,
    session: AgentSessionV1_2 | None = None,
    run: ResearchRun | None = None,
    invocation: RunInvocation | None = None,
    lifecycle_state: str = "PENDING",
    lifecycle_ordinal: int = 1,
    server_thread_id: str = THREAD_ID,
    server_assistant_id: str = SERVER_ASSISTANT_ID,
    server_run_id: str | None = None,
    server_run_status: str | None = None,
    recovery_reason_code: str | None = None,
    server_observation_digest: str | None = None,
    final_binding_digest: str | None = None,
) -> tuple[Any, ...]:
    session = session or _session()
    run = run or _run(session)
    invocation = invocation or _invocation(session, run)
    server_kind = "start" if invocation.invocation_kind == "START" else "resume"
    bound_invocation_id = (
        invocation.invocation_id if lifecycle_state == "RECONCILED" else None
    )
    event_digest = identity._run_create_event_digest(
        run_invocation_id=invocation.invocation_id,
        lifecycle_ordinal=lifecycle_ordinal,
        lifecycle_state=lifecycle_state,
        research_run_id=run.run_id,
        agent_session_id=session.session_id,
        invocation_ordinal=invocation.ordinal,
        canonical_invocation_kind=invocation.invocation_kind,
        server_invocation_kind=server_kind,
        server_thread_id=server_thread_id,
        assistant_id=identity.DELL_AGENT_SERVER_ASSISTANT_ID,
        server_assistant_id=server_assistant_id,
        execution_profile="zero_model_control_plane_v1",
        session_identity_digest=agent_session_identity_digest(session),
        research_run_identity_digest=research_run_identity_digest(run),
        run_invocation_identity_digest=run_invocation_identity_digest(invocation),
        launch_request_digest=LAUNCH_DIGEST,
        server_metadata_digest=METADATA_DIGEST,
        bound_run_invocation_id=bound_invocation_id,
        server_run_id=server_run_id,
        server_run_status=server_run_status,
        recovery_reason_code=recovery_reason_code,
        server_observation_digest=server_observation_digest,
        final_binding_digest=final_binding_digest,
    )
    return (
        invocation.invocation_id,
        lifecycle_ordinal,
        lifecycle_state,
        run.run_id,
        session.session_id,
        invocation.ordinal,
        invocation.invocation_kind,
        server_kind,
        server_thread_id,
        identity.DELL_AGENT_SERVER_ASSISTANT_ID,
        server_assistant_id,
        "zero_model_control_plane_v1",
        agent_session_identity_digest(session),
        research_run_identity_digest(run),
        run_invocation_identity_digest(invocation),
        LAUNCH_DIGEST,
        METADATA_DIGEST,
        bound_invocation_id,
        server_run_id,
        server_run_status,
        recovery_reason_code,
        server_observation_digest,
        final_binding_digest,
        event_digest,
        NOW,
    )


def _action_rows(
    *,
    session: AgentSessionV1_2 | None = None,
    run: ResearchRun | None = None,
    invocation: RunInvocation | None = None,
) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    session = session or _session()
    run = run or _run(session)
    invocation = invocation or _invocation(session, run)
    intent = create_run_create_action_intent(
        research_run=run,
        source_invocation=invocation,
        launch_request_digest=LAUNCH_DIGEST,
    )
    dispatched = create_run_create_action_dispatched(intent)

    def row(snapshot_ordinal: int, action: Any) -> tuple[Any, ...]:
        return (
            invocation.invocation_id,
            snapshot_ordinal,
            action.state,
            action.outcome,
            action.action_attempt_id,
            action.action_attempt_digest,
            action.model_dump(mode="json"),
            NOW,
        )

    return row(1, intent), row(2, dispatched)


def test_schema_declares_fin_owned_cardinality_and_append_only_boundaries() -> None:
    sql = load_identity_schema_sql()
    lowered = sql.casefold()

    assert "create schema if not exists fin_runtime" in lowered
    assert "fin_runtime.research_sessions" in lowered
    assert "fin_runtime.research_runs" in lowered
    assert "fin_runtime.research_run_invocations" in lowered
    assert "server_thread_id uuid not null unique" in lowered
    assert "server_run_id uuid not null unique" in lowered
    assert "unique (research_run_id, invocation_ordinal)" in lowered
    assert "foreign key (agent_session_id, server_thread_id)" in lowered
    assert "foreign key (research_run_id, agent_session_id)" in lowered
    assert "before update or delete" in lowered
    assert lowered.count("before truncate") == 3
    assert "set local role fin_runtime_migrator" in lowered
    assert "grant select, insert on all tables" in lowered
    assert "grant usage, select on all sequences" in lowered
    assert "revoke update, delete, truncate" in lowered
    assert "fin_runtime_durable_identity_is_append_only" in lowered
    assert "action_attempt" not in lowered
    assert not identity._TOP_LEVEL_TRANSACTION_CONTROL_RE.search(sql)


def test_lifecycle_schema_declares_atomic_append_only_authority() -> None:
    sql = load_remote_create_lifecycle_schema_sql()
    lowered = sql.casefold()

    assert "fin_runtime.agent_server_run_create_lifecycle" in lowered
    assert "pending" in lowered
    assert "orphan" in lowered
    assert "reconciled" in lowered
    assert "research_run_invocations_require_reconciled_create" in lowered
    assert "agent_server_run_create_lifecycle_require_valid_event" in lowered
    assert "deferrable initially deferred" in lowered
    assert "pending.server_assistant_id = new.server_assistant_id" in lowered
    assert "pending.execution_profile = new.execution_profile" in lowered
    assert "pending.launch_request_digest = new.launch_request_digest" in lowered
    assert "fin_runtime_run_create_final_binding_preexists" in lowered
    assert "bound.research_run_id = new.research_run_id" in lowered
    assert "bound.invocation_ordinal = new.invocation_ordinal" in lowered
    assert "lifecycle_state = 'dispatched'" in lowered
    assert "failed_before_dispatch" in lowered
    assert "canonical_created_at" in lowered
    assert "observed.server_run_status = new.server_run_status" in lowered
    assert "observed.server_observation_digest =" in lowered
    assert lowered.count(") is true)") >= 3
    assert "before update or delete" in lowered
    assert "before truncate" in lowered
    assert "revoke update, delete, truncate" in lowered
    assert "schema_version=1.1" in lowered
    assert not identity._TOP_LEVEL_TRANSACTION_CONTROL_RE.search(sql)


def test_begin_run_create_persists_one_pending_and_exact_replay_cannot_create() -> None:
    session = _session()
    run = _run(session)
    invocation = _invocation(session, run)
    pending_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=invocation,
    )
    intent_row, _dispatched_action_row = _action_rows(
        session=session,
        run=run,
        invocation=invocation,
    )
    first_connection = _ScriptedConnection(
        results=[
            [_session_row(session)],
            [],
            [],
            [],
            [],
            [pending_row],
            [intent_row],
        ]
    )

    first = _repository(first_connection).begin_run_create(
        research_run=run,
        run_invocation=invocation,
        server_thread_id=THREAD_ID,
        server_invocation_kind="start",
        server_assistant_id=SERVER_ASSISTANT_ID,
        execution_profile="zero_model_control_plane_v1",
        launch_request_digest=LAUNCH_DIGEST,
        server_metadata_digest=METADATA_DIGEST,
    )

    assert first.created_now is True
    assert first.lifecycle.state == "PENDING"
    assert len(first_connection.executed) == 7
    assert "'pending'" in first_connection.executed[3][0].casefold()
    assert "'intent_committed'" in first_connection.executed[4][0].casefold()

    replay_connection = _ScriptedConnection(
        results=[[_session_row(session)], [], [pending_row], [intent_row]]
    )
    replay = _repository(replay_connection).begin_run_create(
        research_run=run,
        run_invocation=invocation,
        server_thread_id=THREAD_ID,
        server_invocation_kind="start",
        server_assistant_id=SERVER_ASSISTANT_ID,
        execution_profile="zero_model_control_plane_v1",
        launch_request_digest=LAUNCH_DIGEST,
        server_metadata_digest=METADATA_DIGEST,
    )
    assert replay.created_now is False
    assert replay.lifecycle.pending.lifecycle_event_digest == pending_row[23]
    assert len(replay_connection.executed) == 4


def test_begin_run_create_rejects_same_run_ordinal_for_another_invocation() -> None:
    session = _session()
    run = _run(session)
    invocation = _invocation(session, run)
    other = _invocation(
        session,
        run,
        invocation_id="INVOCATION::DELL::DURABLE-CONFLICT",
    )
    other_pending = _lifecycle_row(
        session=session,
        run=run,
        invocation=other,
    )
    connection = _ScriptedConnection(
        results=[[_session_row(session)], [], [other_pending]]
    )

    with pytest.raises(
        DellAgentServerIdentityConflict,
        match="run_create_research_run_ordinal_conflict",
    ):
        _repository(connection).begin_run_create(
            research_run=run,
            run_invocation=invocation,
            server_thread_id=THREAD_ID,
            server_invocation_kind="start",
            server_assistant_id=SERVER_ASSISTANT_ID,
            execution_profile="zero_model_control_plane_v1",
            launch_request_digest=LAUNCH_DIGEST,
            server_metadata_digest=METADATA_DIGEST,
        )
    assert connection.transaction_rollbacks == 1


def test_orphan_event_is_append_only_and_replay_must_be_exact() -> None:
    session = _session()
    run = _run(session)
    invocation = _invocation(session, run)
    pending_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=invocation,
    )
    dispatched_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=invocation,
        lifecycle_state="DISPATCHED",
        lifecycle_ordinal=2,
    )
    orphan_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=invocation,
        lifecycle_state="ORPHAN",
        lifecycle_ordinal=3,
        server_run_id=START_RUN_ID,
        recovery_reason_code="REMOTE_CREATE_HEADER_OBSERVED",
        server_observation_digest=OBSERVATION_DIGEST,
    )
    connection = _ScriptedConnection(
        results=[
            [pending_row, dispatched_row],
            [],
            [pending_row, dispatched_row],
            [],
            [pending_row, dispatched_row, orphan_row],
        ]
    )
    persisted = _repository(connection).record_run_create_orphan(
        run_invocation_id=invocation.invocation_id,
        pending_event_digest=pending_row[23],
        recovery_reason_code="REMOTE_CREATE_HEADER_OBSERVED",
        server_observation_digest=OBSERVATION_DIGEST,
        server_run_id=START_RUN_ID,
    )
    assert persisted.state == "ORPHAN"
    assert persisted.orphan is not None
    assert persisted.orphan.server_run_id == START_RUN_ID

    replay_connection = _ScriptedConnection(
        results=[
            [pending_row, dispatched_row, orphan_row],
            [],
            [pending_row, dispatched_row, orphan_row],
        ]
    )
    replay = _repository(replay_connection).record_run_create_orphan(
        run_invocation_id=invocation.invocation_id,
        pending_event_digest=pending_row[23],
        recovery_reason_code="REMOTE_CREATE_HEADER_OBSERVED",
        server_observation_digest=OBSERVATION_DIGEST,
        server_run_id=START_RUN_ID,
    )
    assert replay == persisted

    conflict_connection = _ScriptedConnection(
        results=[
            [pending_row, dispatched_row, orphan_row],
            [],
            [pending_row, dispatched_row, orphan_row],
        ]
    )
    with pytest.raises(
        DellAgentServerIdentityConflict,
        match="run_create_orphan_observation_conflict",
    ):
        _repository(conflict_connection).record_run_create_orphan(
            run_invocation_id=invocation.invocation_id,
            pending_event_digest=pending_row[23],
            recovery_reason_code="REMOTE_SCAN_EMPTY",
            server_observation_digest=OBSERVATION_DIGEST,
            server_run_id=START_RUN_ID,
        )


def test_lifecycle_projection_rejects_digest_or_identity_drift() -> None:
    pending_row = _lifecycle_row()
    corrupt = list(pending_row)
    corrupt[23] = "0" * 64
    with pytest.raises(
        DellAgentServerIdentityStoreError,
        match="run_create_lifecycle_event_digest_mismatch",
    ):
        identity._run_create_lifecycle_from_rows([tuple(corrupt)])


def test_execution_projection_reads_final_binding_and_lifecycle_together() -> None:
    session = _session()
    run = _run(session)
    invocation = _invocation(session, run)
    binding_row = _invocation_row(invocation)
    pending_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=invocation,
    )
    dispatched_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=invocation,
        lifecycle_state="DISPATCHED",
        lifecycle_ordinal=2,
    )
    reconciled_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=invocation,
        lifecycle_state="RECONCILED",
        lifecycle_ordinal=3,
        server_run_id=START_RUN_ID,
        server_run_status="pending",
        recovery_reason_code="REMOTE_RESPONSE_EXACT",
        server_observation_digest=OBSERVATION_DIGEST,
        final_binding_digest=persisted_run_binding_digest(
            identity._invocation_from_row(binding_row)
        ),
    )
    connection = _ScriptedConnection(
        results=[[binding_row], [pending_row, dispatched_row, reconciled_row]]
    )

    projection = _repository(
        connection
    ).get_execution_binding_with_lifecycle(
        run_invocation_id=invocation.invocation_id
    )

    assert projection is not None
    assert projection.binding.server_run_id == START_RUN_ID
    assert projection.lifecycle is not None
    assert projection.lifecycle.state == "RECONCILED"
    assert len(connection.executed) == 2


def test_reconciled_bind_replay_is_exact_and_does_not_append() -> None:
    session = _session()
    run = _run(session)
    invocation = _invocation(session, run)
    binding_row = _invocation_row(invocation)
    persisted_binding = identity._invocation_from_row(binding_row)
    pending_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=invocation,
    )
    dispatched_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=invocation,
        lifecycle_state="DISPATCHED",
        lifecycle_ordinal=2,
    )
    reconciled_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=invocation,
        lifecycle_state="RECONCILED",
        lifecycle_ordinal=3,
        server_run_id=START_RUN_ID,
        server_run_status="pending",
        recovery_reason_code="REMOTE_RESPONSE_EXACT",
        server_observation_digest=OBSERVATION_DIGEST,
        final_binding_digest=persisted_run_binding_digest(persisted_binding),
    )
    exact_connection = _ScriptedConnection(
        results=[
            [_session_row(session)],
            [],
            [pending_row, dispatched_row, reconciled_row],
            [binding_row],
        ]
    )
    replay = _repository(exact_connection).bind_run_invocation(
        research_run=run,
        run_invocation=invocation,
        server_thread_id=THREAD_ID,
        server_run_id=START_RUN_ID,
        server_invocation_kind="start",
        first_server_status="pending",
        pending_event_digest=pending_row[23],
        server_observation_digest=OBSERVATION_DIGEST,
        reconciliation_reason_code="REMOTE_RESPONSE_EXACT",
    )
    assert replay == persisted_binding
    assert len(exact_connection.executed) == 4

    conflict_connection = _ScriptedConnection(
        results=[
            [_session_row(session)],
            [],
            [pending_row, dispatched_row, reconciled_row],
            [binding_row],
        ]
    )
    with pytest.raises(
        DellAgentServerIdentityConflict,
        match="run_create_reconciled_binding_conflict",
    ):
        _repository(conflict_connection).bind_run_invocation(
            research_run=run,
            run_invocation=invocation,
            server_thread_id=THREAD_ID,
            server_run_id=START_RUN_ID,
            server_invocation_kind="start",
            first_server_status="pending",
            pending_event_digest=pending_row[23],
            server_observation_digest="3" * 64,
            reconciliation_reason_code="REMOTE_RESPONSE_EXACT",
        )


def test_session_binding_is_parameterized_transactional_and_idempotent() -> None:
    session = _session()
    connection = _ScriptedConnection(results=[[], [_session_row(session)]])
    repository = _repository(connection)

    first = repository.bind_agent_session(
        agent_session=session,
        server_thread_id=THREAD_ID,
    )

    assert first.agent_session_id == session.session_id
    assert first.server_thread_id == THREAD_ID
    assert connection.transaction_entries == 1
    assert connection.transaction_commits == 1
    assert connection.transaction_rollbacks == 0
    insert_sql, insert_params = connection.executed[0]
    assert "on conflict do nothing" in insert_sql.casefold()
    assert session.session_id not in insert_sql
    assert insert_params is not None and insert_params[0] == session.session_id

    replay_connection = _ScriptedConnection(results=[[], [_session_row(session)]])
    replay = _repository(replay_connection).bind_agent_session(
        agent_session=session,
        server_thread_id=THREAD_ID,
    )
    assert replay == first


def test_session_cardinality_conflict_rolls_back_fail_closed() -> None:
    connection = _ScriptedConnection(
        results=[[], [_session_row(server_thread_id=RESUME_RUN_ID)]]
    )
    repository = _repository(connection)

    with pytest.raises(
        DellAgentServerIdentityConflict,
        match="agent_session_server_thread_binding_conflict",
    ):
        repository.bind_agent_session(
            agent_session=_session(),
            server_thread_id=THREAD_ID,
        )

    assert connection.transaction_commits == 0
    assert connection.transaction_rollbacks == 1


def test_run_binding_is_one_transaction_and_builds_one_to_many_aggregate() -> None:
    session = _session()
    run = _run(session)
    invocation = _invocation(session, run)
    pending_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=invocation,
    )
    dispatched_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=invocation,
        lifecycle_state="DISPATCHED",
        lifecycle_ordinal=2,
    )
    _intent_action_row, dispatched_action_row = _action_rows(
        session=session,
        run=run,
        invocation=invocation,
    )
    binding_row = _invocation_row(invocation)
    final_digest = persisted_run_binding_digest(
        identity._invocation_from_row(binding_row)
    )
    reconciled_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=invocation,
        lifecycle_state="RECONCILED",
        lifecycle_ordinal=3,
        server_run_id=START_RUN_ID,
        server_run_status="pending",
        recovery_reason_code="REMOTE_RESPONSE_EXACT",
        server_observation_digest=OBSERVATION_DIGEST,
        final_binding_digest=final_digest,
    )
    connection = _ScriptedConnection(
        results=[
            [_session_row(session)],
            [],
            [pending_row, dispatched_row],
            [],
            [],
            [],
            [],
            [_run_row(run)],
            [(0, 0)],
            [],
            [binding_row],
            [dispatched_action_row],
            [],
            [],
            [pending_row, dispatched_row, reconciled_row],
        ]
    )
    repository = _repository(connection)

    persisted = repository.bind_run_invocation(
        research_run=run,
        run_invocation=invocation,
        server_thread_id=THREAD_ID,
        server_run_id=START_RUN_ID,
        server_invocation_kind="start",
        first_server_status="pending",
        pending_event_digest=pending_row[23],
        server_observation_digest=OBSERVATION_DIGEST,
        reconciliation_reason_code="REMOTE_RESPONSE_EXACT",
    )

    assert persisted.run_invocation_id == invocation.invocation_id
    assert persisted.server_run_id == START_RUN_ID
    assert connection.transaction_entries == 1
    assert connection.transaction_commits == 1
    assert len(connection.executed) == 15
    assert "pg_advisory_xact_lock" in connection.executed[1][0].casefold()
    assert "hashtextextended" in connection.executed[1][0].casefold()
    assert "pg_advisory_xact_lock" in connection.executed[5][0].casefold()
    assert "for update" not in connection.executed[7][0].casefold()
    assert "max(invocation_ordinal)" in connection.executed[8][0].casefold()
    assert "'reconciled'" in connection.executed[13][0].casefold()
    assert all(
        "fin_runtime." in statement
        or "pg_advisory_xact_lock" in statement.casefold()
        for statement, _params in connection.executed
    )

    resumed = _invocation(session, run, resume=True)
    fresh_process_connection = _ScriptedConnection(
        results=[
            [_run_row(run)],
            [
                _invocation_row(invocation),
                _invocation_row(
                    resumed,
                    server_run_id=RESUME_RUN_ID,
                    server_kind="resume",
                ),
            ],
        ]
    )
    fresh_repository = _repository(fresh_process_connection)
    aggregate = fresh_repository.get_research_run_aggregate(
        research_run_id=run.run_id
    )

    assert aggregate is not None
    assert aggregate.research_run.research_run_id == run.run_id
    assert aggregate.server_run_ids == (START_RUN_ID, RESUME_RUN_ID)
    assert fresh_process_connection.transaction_commits == 1
    assert fresh_process_connection.executed[0][0].casefold().count(
        "fin_runtime.research_runs"
    ) == 1
    assert "fin_runtime.research_run_invocations" in (
        fresh_process_connection.executed[1][0].casefold()
    )


def test_resume_binding_requires_durable_preceding_ordinal() -> None:
    session = _session()
    run = _run(session)
    resume = _invocation(session, run, resume=True)
    pending_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=resume,
    )
    dispatched_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=resume,
        lifecycle_state="DISPATCHED",
        lifecycle_ordinal=2,
    )
    connection = _ScriptedConnection(
        results=[
            [_session_row(session)],
            [],
            [pending_row, dispatched_row],
            [],
            [],
            [],
            [],
            [_run_row(run)],
            [(0, 0)],
        ]
    )

    with pytest.raises(
        DellAgentServerIdentityConflict,
        match="research_run_invocation_sequence_gap",
    ):
        _repository(connection).bind_run_invocation(
            research_run=run,
            run_invocation=resume,
            server_thread_id=THREAD_ID,
            server_run_id=RESUME_RUN_ID,
            server_invocation_kind="resume",
            first_server_status="pending",
            pending_event_digest=pending_row[23],
            server_observation_digest=OBSERVATION_DIGEST,
            reconciliation_reason_code="REMOTE_RESPONSE_EXACT",
        )

    assert connection.transaction_rollbacks == 1
    assert len(connection.executed) == 9
    assert "pg_advisory_xact_lock" in connection.executed[1][0].casefold()
    assert "pg_advisory_xact_lock" in connection.executed[5][0].casefold()
    assert "for update" not in connection.executed[7][0].casefold()
    assert "max(invocation_ordinal)" in connection.executed[8][0].casefold()


def test_invocation_collision_or_noncontiguous_aggregate_fails_closed() -> None:
    session = _session()
    run = _run(session)
    invocation = _invocation(session, run)
    collision = _invocation(
        session,
        run,
        invocation_id="INVOCATION::DELL::COLLISION",
    )
    pending_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=invocation,
    )
    dispatched_row = _lifecycle_row(
        session=session,
        run=run,
        invocation=invocation,
        lifecycle_state="DISPATCHED",
        lifecycle_ordinal=2,
    )
    connection = _ScriptedConnection(
        results=[
            [_session_row(session)],
            [],
            [pending_row, dispatched_row],
            [],
            [],
            [],
            [],
            [_run_row(run)],
            [(0, 0)],
            [],
            [
                _invocation_row(invocation),
                _invocation_row(collision, server_run_id=RESUME_RUN_ID),
            ],
        ]
    )

    with pytest.raises(
        DellAgentServerIdentityConflict,
        match="run_invocation_server_run_cardinality_conflict",
    ):
        _repository(connection).bind_run_invocation(
            research_run=run,
            run_invocation=invocation,
            server_thread_id=THREAD_ID,
            server_run_id=START_RUN_ID,
            server_invocation_kind="start",
            first_server_status="pending",
            pending_event_digest=pending_row[23],
            server_observation_digest=OBSERVATION_DIGEST,
            reconciliation_reason_code="REMOTE_RESPONSE_EXACT",
        )
    assert connection.transaction_rollbacks == 1

    third = _invocation(
        session,
        run,
        resume=True,
        invocation_id="INVOCATION::DELL::DURABLE-003",
        ordinal=3,
    )
    corrupt_read_connection = _ScriptedConnection(
        results=[
            [_run_row(run)],
            [
                _invocation_row(invocation),
                _invocation_row(
                    third,
                    server_run_id=RESUME_RUN_ID,
                    server_kind="resume",
                ),
            ],
        ]
    )
    with pytest.raises(
        DellAgentServerIdentityStoreError,
        match="research_run_invocation_sequence_not_contiguous",
    ):
        _repository(corrupt_read_connection).get_research_run_aggregate(
            research_run_id=run.run_id
        )


def test_stable_identity_digests_do_not_treat_state_progress_as_new_identity() -> None:
    session = _session()
    paused_session = _session(
        status="PAUSED",
        active_plan_ref="plan://dell/2",
        active_plan_digest=DIGEST_B,
        updated_at=NOW + timedelta(minutes=3),
    )
    assert session.session_digest != paused_session.session_digest
    assert agent_session_identity_digest(session) == agent_session_identity_digest(
        paused_session
    )

    run = _run(session)
    paused_run = _run(
        session,
        status="PAUSED",
        current_plan_ref="plan://dell/2",
        current_plan_digest=DIGEST_B,
        last_session_sequence=3,
    )
    assert run.run_digest != paused_run.run_digest
    assert research_run_identity_digest(run) == research_run_identity_digest(
        paused_run
    )

    invocation = _invocation(session, run)
    terminal_invocation = _invocation(
        session,
        run,
        status="SUCCEEDED",
        finished_at=NOW + timedelta(minutes=1),
        lease_ref="lease://agent-server/final",
    )
    assert invocation.invocation_digest != terminal_invocation.invocation_digest
    assert run_invocation_identity_digest(
        invocation
    ) == run_invocation_identity_digest(terminal_invocation)


def test_invalid_identity_digest_is_rejected_on_fresh_read() -> None:
    row = list(_session_row())
    row[4] = "not-a-sha256"
    connection = _ScriptedConnection(results=[[tuple(row)]])

    with pytest.raises(
        DellAgentServerIdentityStoreError,
        match="identity_session_digest_invalid",
    ):
        _repository(connection).get_agent_session(
            agent_session_id=_session().session_id
        )


def test_schema_sources_are_digest_pinned_but_repository_install_is_retired() -> None:
    connection = _ScriptedConnection()
    repository = _repository(connection)
    sql = load_identity_schema_sql()
    lifecycle_sql = load_remote_create_lifecycle_schema_sql()

    assert sha256(sql.encode("utf-8")).hexdigest() == identity.IDENTITY_SCHEMA_SHA256
    assert (
        sha256(lifecycle_sql.encode("utf-8")).hexdigest()
        == identity.REMOTE_CREATE_LIFECYCLE_SCHEMA_SHA256
    )
    with pytest.raises(
        DellAgentServerIdentityStoreError,
        match="identity_schema_repository_install_unsupported",
    ):
        repository.install_schema()
    assert connection.executed == []
    assert connection.transaction_commits == 0


def test_pre_lifecycle_postgres_qualifier_is_a_typed_tombstone() -> None:
    with pytest.raises(
        RuntimeError,
        match=(
            qualify_dell_agent_server_identity_postgres_v1
            .LEGACY_IDENTITY_QUALIFIER_RETIREMENT_CODE
        ),
    ):
        qualify_dell_agent_server_identity_postgres_v1.main()


def test_repository_requires_pool_checkout_and_rejects_active_connection() -> None:
    bare_connection = _ScriptedConnection()
    with pytest.raises(
        DellAgentServerIdentityStoreError,
        match="identity_store_connection_source_required",
    ):
        PostgresDellAgentServerIdentityRepository(bare_connection)  # type: ignore[arg-type]

    active_connection = _ScriptedConnection()
    active_connection.info.transaction_status = 2
    pool = _ScriptedPool(active_connection)
    repository = PostgresDellAgentServerIdentityRepository(pool)
    with pytest.raises(
        DellAgentServerIdentityStoreError,
        match="identity_store_connection_not_idle",
    ):
        repository.get_agent_session(agent_session_id=_session().session_id)
    assert pool.checkout_count == 1
    assert active_connection.transaction_entries == 0

    idle_connection = _ScriptedConnection(
        results=[[_session_row()], [_session_row()]]
    )
    idle_pool = _ScriptedPool(idle_connection)
    idle_repository = PostgresDellAgentServerIdentityRepository(idle_pool)
    for _ in range(2):
        assert idle_repository.get_agent_session(
            agent_session_id=_session().session_id
        ) is not None
    assert idle_pool.checkout_count == 2
    assert idle_connection.transaction_commits == 2
