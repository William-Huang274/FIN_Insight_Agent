"""Retired pre-lifecycle PostgreSQL identity qualifier.

This historical entrypoint predates the mandatory PENDING/ORPHAN/RECONCILED
remote-create lifecycle.  It remains readable as historical implementation
evidence, but its ``main`` function fails before reading credentials or writing
PostgreSQL so it cannot be mistaken for the current RC-S3-107 qualification.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import json
import os
from threading import Barrier
from typing import Any, Callable
from uuid import uuid4

import psycopg
from psycopg_pool import ConnectionPool

from sec_agent.agent_runtime.dell_agent_server_identity import (
    DELL_AGENT_SERVER_ASSISTANT_ID,
    IDENTITY_SCHEMA_SHA256,
    DellAgentServerIdentityConflict,
    PostgresDellAgentServerIdentityRepository,
)
from sec_agent.canonical_runtime.contracts_v1_2 import (
    AgentSessionV1_2,
    ResearchRun,
    RunInvocation,
    create_agent_session_v1_2,
    create_research_run,
    create_run_invocation,
)


RUNTIME_URI_ENV = "FIN_RUNTIME_POSTGRES_URI"
MIGRATION_URI_ENV = "FIN_RUNTIME_MIGRATION_POSTGRES_URI"
EXPECTED_TRIGGER_NAMES = {
    "research_sessions_reject_mutation",
    "research_sessions_reject_truncate",
    "research_runs_reject_mutation",
    "research_runs_reject_truncate",
    "research_run_invocations_reject_mutation",
    "research_run_invocations_reject_truncate",
}

LEGACY_IDENTITY_QUALIFIER_RETIREMENT_CODE = (
    "dell_pre_lifecycle_identity_qualifier_retired_rc_s3_107_required"
)


def _required_secret_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value or value != value.strip():
        raise RuntimeError(f"{name.casefold()}_missing")
    return value


def _session(token: str, now: datetime) -> AgentSessionV1_2:
    return create_agent_session_v1_2(
        session_id=f"SESSION::DELL::PG-QUAL::{token}",
        thread_id=f"THREAD::DELL::PG-QUAL::{token}",
        case_id="DELL_AI_INFRA_REFERENCE_VERTICAL",
        case_version="FIN_0_1_3",
        as_of_date=date(2026, 9, 3),
        objective_ref="objective://dell/postgres-identity-qualification",
        objective_digest="a" * 64,
        data_snapshot_ref="snapshot://dell/owner-data-gate-accepted",
        data_snapshot_digest="b" * 64,
        runtime_policy_ref="policy://dell/agent-server/zero-model-v1",
        runtime_policy_digest="c" * 64,
        authority_refs=("authority://owner/data-gate/2026-09-03",),
        active_plan_ref="plan://dell/postgres-identity-qualification/v1",
        active_plan_digest="d" * 64,
        status="ACTIVE",
        created_at=now,
        updated_at=now,
    )


def _run(session: AgentSessionV1_2, token: str, now: datetime) -> ResearchRun:
    return create_research_run(
        run_id=f"RUN::DELL::PG-QUAL::{token}",
        session_id=session.session_id,
        parent_run_id=None,
        origin_kind="INITIAL",
        legacy_paid_full_chain_execution_label=None,
        status="RUNNING",
        base_plan_ref=session.active_plan_ref,
        base_plan_digest=session.active_plan_digest,
        current_plan_ref=session.active_plan_ref,
        current_plan_digest=session.active_plan_digest,
        last_session_sequence=0,
        created_at=now,
        terminal_at=None,
    )


def _invocation(
    session: AgentSessionV1_2,
    run: ResearchRun,
    token: str,
    ordinal: int,
    now: datetime,
    *,
    contender: str = "main",
) -> RunInvocation:
    return create_run_invocation(
        invocation_id=(
            f"INVOCATION::DELL::PG-QUAL::{token}::{ordinal}::{contender}"
        ),
        session_id=session.session_id,
        run_id=run.run_id,
        ordinal=ordinal,
        invocation_kind="START" if ordinal == 1 else "RESUME",
        status="RUNNING",
        trigger_ref=(
            f"command://postgres-qualification/{token}/{ordinal}/{contender}"
        ),
        lease_ref=f"lease://agent-server/{token}/{ordinal}/{contender}",
        started_at=now + timedelta(seconds=ordinal),
        finished_at=None,
    )


def _expect_sql_rejection(
    conninfo: str,
    statement: str,
    params: tuple[Any, ...] = (),
) -> str:
    try:
        with psycopg.connect(conninfo) as connection:
            with connection.transaction():
                connection.execute(statement, params)
    except psycopg.Error as exc:
        if not exc.sqlstate:
            raise RuntimeError("postgres_rejection_without_sqlstate") from None
        return exc.sqlstate
    raise RuntimeError("postgres_forbidden_statement_was_accepted")


def _admin_snapshot(conninfo: str) -> dict[str, Any]:
    with psycopg.connect(conninfo) as connection:
        role_rows = connection.execute(
            """
            SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolcanlogin
            FROM pg_catalog.pg_roles
            WHERE rolname IN (
                'langgraph_runtime',
                'fin_runtime_app',
                'fin_runtime_migrator'
            )
            ORDER BY rolname
            """
        ).fetchall()
        schema_owner = connection.execute(
            """
            SELECT owner.rolname
            FROM pg_catalog.pg_namespace namespace
            JOIN pg_catalog.pg_roles owner
              ON owner.oid = namespace.nspowner
            WHERE namespace.nspname = 'fin_runtime'
            """
        ).fetchone()
        trigger_rows = connection.execute(
            """
            SELECT relation.relname, trigger.tgname, trigger.tgenabled,
                   pg_catalog.pg_get_triggerdef(trigger.oid)
            FROM pg_catalog.pg_trigger trigger
            JOIN pg_catalog.pg_class relation
              ON relation.oid = trigger.tgrelid
            JOIN pg_catalog.pg_namespace namespace
              ON namespace.oid = relation.relnamespace
            WHERE namespace.nspname = 'fin_runtime'
              AND NOT trigger.tgisinternal
            ORDER BY relation.relname, trigger.tgname
            """
        ).fetchall()
        privilege_rows = connection.execute(
            """
            SELECT table_name, privilege_type
            FROM information_schema.role_table_grants
            WHERE grantee = 'fin_runtime_app'
              AND table_schema = 'fin_runtime'
            ORDER BY table_name, privilege_type
            """
        ).fetchall()

    roles = {
        str(row[0]): {
            "superuser": bool(row[1]),
            "create_database": bool(row[2]),
            "create_role": bool(row[3]),
            "login": bool(row[4]),
        }
        for row in role_rows
    }
    expected_roles = {
        "fin_runtime_app": {
            "superuser": False,
            "create_database": False,
            "create_role": False,
            "login": True,
        },
        "fin_runtime_migrator": {
            "superuser": False,
            "create_database": False,
            "create_role": False,
            "login": False,
        },
        "langgraph_runtime": {
            "superuser": False,
            "create_database": False,
            "create_role": False,
            "login": True,
        },
    }
    if roles != expected_roles:
        raise RuntimeError("postgres_runtime_role_profile_mismatch")
    if schema_owner is None or schema_owner[0] != "fin_runtime_migrator":
        raise RuntimeError("fin_runtime_schema_owner_mismatch")
    trigger_names = {str(row[1]) for row in trigger_rows}
    if trigger_names != EXPECTED_TRIGGER_NAMES:
        raise RuntimeError("fin_runtime_trigger_set_mismatch")
    if any(str(row[2]) != "O" for row in trigger_rows):
        raise RuntimeError("fin_runtime_trigger_not_enabled")
    privileges = {(str(row[0]), str(row[1])) for row in privilege_rows}
    expected_privileges = {
        (table, privilege)
        for table in (
            "research_sessions",
            "research_runs",
            "research_run_invocations",
        )
        for privilege in ("INSERT", "SELECT")
    }
    if privileges != expected_privileges:
        raise RuntimeError("fin_runtime_app_table_privilege_mismatch")
    return {
        "roles": roles,
        "schema_owner": str(schema_owner[0]),
        "trigger_count": len(trigger_rows),
        "runtime_table_privileges": sorted(
            f"{table}:{privilege}" for table, privilege in privileges
        ),
    }


def _migrator_trigger_rejection(
    migration_uri: str,
    session_id: str,
) -> str:
    try:
        with psycopg.connect(migration_uri) as connection:
            with connection.transaction():
                connection.execute("SET LOCAL ROLE fin_runtime_migrator")
                connection.execute(
                    """
                    UPDATE fin_runtime.research_sessions
                    SET assistant_id = assistant_id
                    WHERE agent_session_id = %s
                    """,
                    (session_id,),
                )
    except psycopg.Error as exc:
        if exc.sqlstate != "55000":
            raise RuntimeError(
                "fin_runtime_append_only_trigger_sqlstate_mismatch"
            ) from None
        return exc.sqlstate
    raise RuntimeError("fin_runtime_append_only_trigger_did_not_reject")


def main() -> None:
    raise RuntimeError(LEGACY_IDENTITY_QUALIFIER_RETIREMENT_CODE)

    # Historical implementation below is deliberately unreachable.  Keeping
    # it in-place preserves the exact old qualification logic for audit while
    # the typed guard above prevents its direct final-binding writes.
    runtime_uri = _required_secret_environment(RUNTIME_URI_ENV)
    migration_uri = _required_secret_environment(MIGRATION_URI_ENV)
    token = uuid4().hex[:12]
    now = datetime.now(timezone.utc).replace(microsecond=0)
    session = _session(token, now)
    run = _run(session, token, now)
    server_thread_id = str(uuid4())
    start = _invocation(session, run, token, 1, now)
    resume = _invocation(session, run, token, 2, now)
    premature_third = _invocation(
        session, run, token, 3, now, contender="premature"
    )

    with ConnectionPool(
        runtime_uri,
        min_size=1,
        max_size=4,
        open=True,
        timeout=10,
    ) as pool:
        pool.wait(timeout=10)
        repository = PostgresDellAgentServerIdentityRepository(pool)
        bound_session = repository.bind_agent_session(
            agent_session=session,
            server_thread_id=server_thread_id,
        )
        if bound_session.assistant_id != DELL_AGENT_SERVER_ASSISTANT_ID:
            raise RuntimeError("qualified_session_assistant_mismatch")
        start_binding = repository.bind_run_invocation(
            research_run=run,
            run_invocation=start,
            server_thread_id=server_thread_id,
            server_run_id=str(uuid4()),
            server_invocation_kind="start",
            first_server_status="pending",
        )
        try:
            repository.bind_run_invocation(
                research_run=run,
                run_invocation=premature_third,
                server_thread_id=server_thread_id,
                server_run_id=str(uuid4()),
                server_invocation_kind="resume",
                first_server_status="pending",
            )
        except DellAgentServerIdentityConflict as exc:
            if exc.code != "research_run_invocation_sequence_gap":
                raise RuntimeError("sequence_gap_rejection_code_mismatch") from None
        else:
            raise RuntimeError("sequence_gap_was_accepted")

        resume_binding = repository.bind_run_invocation(
            research_run=run,
            run_invocation=resume,
            server_thread_id=server_thread_id,
            server_run_id=str(uuid4()),
            server_invocation_kind="resume",
            first_server_status="pending",
        )

        barrier = Barrier(2)

        def bind_contender(label: str) -> tuple[str, str, str]:
            invocation = _invocation(
                session, run, token, 3, now, contender=label
            )
            server_run_id = str(uuid4())
            barrier.wait(timeout=10)
            try:
                persisted = repository.bind_run_invocation(
                    research_run=run,
                    run_invocation=invocation,
                    server_thread_id=server_thread_id,
                    server_run_id=server_run_id,
                    server_invocation_kind="resume",
                    first_server_status="pending",
                )
            except DellAgentServerIdentityConflict as exc:
                return "conflict", label, exc.code
            return "bound", label, persisted.run_invocation_id

        with ThreadPoolExecutor(max_workers=2) as executor:
            contender_results = list(
                executor.map(bind_contender, ("alpha", "beta"))
            )
        outcomes = sorted(result[0] for result in contender_results)
        if outcomes != ["bound", "conflict"]:
            raise RuntimeError("concurrent_ordinal_single_winner_not_enforced")
        winner = next(result for result in contender_results if result[0] == "bound")
        winner_label = winner[1]
        winner_invocation = _invocation(
            session, run, token, 3, now, contender=winner_label
        )
        winner_binding = repository.get_run_invocation(
            run_invocation_id=winner_invocation.invocation_id
        )
        if winner_binding is None:
            raise RuntimeError("concurrent_winner_not_durable")
        duplicate = repository.bind_run_invocation(
            research_run=run,
            run_invocation=winner_invocation,
            server_thread_id=server_thread_id,
            server_run_id=winner_binding.server_run_id,
            server_invocation_kind="resume",
            first_server_status="pending",
        )
        if duplicate != winner_binding:
            raise RuntimeError("identity_exact_replay_not_idempotent")

        aggregate_before_reconnect = repository.get_research_run_aggregate(
            research_run_id=run.run_id
        )
        if aggregate_before_reconnect is None:
            raise RuntimeError("qualified_aggregate_missing")
        if tuple(
            item.invocation_ordinal
            for item in aggregate_before_reconnect.invocations
        ) != (1, 2, 3):
            raise RuntimeError("qualified_aggregate_sequence_invalid")

    with ConnectionPool(
        runtime_uri,
        min_size=1,
        max_size=2,
        open=True,
        timeout=10,
    ) as reopened_pool:
        reopened_pool.wait(timeout=10)
        reopened_repository = PostgresDellAgentServerIdentityRepository(
            reopened_pool
        )
        durable_session = reopened_repository.get_agent_session(
            agent_session_id=session.session_id
        )
        durable_aggregate = reopened_repository.get_research_run_aggregate(
            research_run_id=run.run_id
        )
        if durable_session is None or durable_aggregate is None:
            raise RuntimeError("identity_not_durable_after_pool_reconnect")
        if len(durable_aggregate.invocations) != 3:
            raise RuntimeError("identity_invocation_count_changed_after_reconnect")

    rejection_sqlstates = {
        "runtime_update": _expect_sql_rejection(
            runtime_uri,
            """
            UPDATE fin_runtime.research_sessions
            SET assistant_id = assistant_id
            WHERE agent_session_id = %s
            """,
            (session.session_id,),
        ),
        "runtime_delete": _expect_sql_rejection(
            runtime_uri,
            "DELETE FROM fin_runtime.research_sessions WHERE agent_session_id = %s",
            (session.session_id,),
        ),
        "runtime_truncate": _expect_sql_rejection(
            runtime_uri,
            "TRUNCATE fin_runtime.research_run_invocations",
        ),
        "runtime_alter": _expect_sql_rejection(
            runtime_uri,
            "ALTER TABLE fin_runtime.research_sessions ADD COLUMN forbidden text",
        ),
        "runtime_drop_trigger": _expect_sql_rejection(
            runtime_uri,
            """
            DROP TRIGGER research_sessions_reject_mutation
            ON fin_runtime.research_sessions
            """,
        ),
        "migrator_trigger": _migrator_trigger_rejection(
            migration_uri,
            session.session_id,
        ),
    }

    admin_snapshot = _admin_snapshot(migration_uri)
    with psycopg.connect(runtime_uri) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM fin_runtime.research_sessions
                 WHERE agent_session_id = %s),
                (SELECT COUNT(*) FROM fin_runtime.research_runs
                 WHERE research_run_id = %s),
                (SELECT COUNT(*) FROM fin_runtime.research_run_invocations
                 WHERE research_run_id = %s)
            """,
            (session.session_id, run.run_id, run.run_id),
        ).fetchone()
    if counts != (1, 1, 3):
        raise RuntimeError("identity_rollback_or_cardinality_check_failed")

    receipt = {
        "schema_version": "fin_ia_dell_agent_server_postgres_qualification_v1_0",
        "status": "pass",
        "identity_schema_sha256": IDENTITY_SCHEMA_SHA256,
        "model_calls": 0,
        "external_network_calls": 0,
        "session_binding": "one_to_one",
        "run_invocation_ordinals": [1, 2, 3],
        "concurrent_ordinal_three": {
            "winner_count": 1,
            "conflict_count": 1,
        },
        "exact_replay_idempotent": True,
        "pool_reconnect_persistence": True,
        "rollback_cardinality": {
            "sessions": int(counts[0]),
            "runs": int(counts[1]),
            "invocations": int(counts[2]),
        },
        "rejection_sqlstates": rejection_sqlstates,
        "database_contract": admin_snapshot,
        "secret_values_emitted": False,
    }
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
