from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Sequence

import pytest

from sec_agent.agent_runtime import dell_agent_server_identity as identity
from sec_agent.agent_runtime.dell_agent_server_identity import (
    DellAgentServerIdentityConflict,
    DellAgentServerIdentityStoreError,
    PostgresDellAgentServerIdentityRepository,
    agent_session_identity_digest,
    load_identity_schema_sql,
    research_run_identity_digest,
    run_invocation_identity_digest,
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
    connection = _ScriptedConnection(
        results=[
            [_session_row(session)],
            [],
            [],
            [_run_row(run)],
            [(0, 0)],
            [],
            [_invocation_row(invocation)],
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
    )

    assert persisted.run_invocation_id == invocation.invocation_id
    assert persisted.server_run_id == START_RUN_ID
    assert connection.transaction_entries == 1
    assert connection.transaction_commits == 1
    assert len(connection.executed) == 7
    assert "pg_advisory_xact_lock" in connection.executed[1][0].casefold()
    assert "hashtextextended" in connection.executed[1][0].casefold()
    assert "for update" not in connection.executed[3][0].casefold()
    assert "max(invocation_ordinal)" in connection.executed[4][0].casefold()
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
    connection = _ScriptedConnection(
        results=[
            [_session_row(session)],
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
        )

    assert connection.transaction_rollbacks == 1
    assert len(connection.executed) == 5
    assert "pg_advisory_xact_lock" in connection.executed[1][0].casefold()
    assert "for update" not in connection.executed[3][0].casefold()
    assert "max(invocation_ordinal)" in connection.executed[4][0].casefold()


def test_invocation_collision_or_noncontiguous_aggregate_fails_closed() -> None:
    session = _session()
    run = _run(session)
    invocation = _invocation(session, run)
    collision = _invocation(
        session,
        run,
        invocation_id="INVOCATION::DELL::COLLISION",
    )
    connection = _ScriptedConnection(
        results=[
            [_session_row(session)],
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


def test_schema_installer_uses_only_digest_pinned_packaged_sql() -> None:
    connection = _ScriptedConnection()
    repository = _repository(connection)
    sql = load_identity_schema_sql()

    assert sha256(sql.encode("utf-8")).hexdigest() == identity.IDENTITY_SCHEMA_SHA256
    repository.install_schema()
    assert connection.executed == [(sql, None)]
    assert connection.transaction_commits == 1


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
