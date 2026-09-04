"""Thin, secret-free RC-S3-107 qualification against a prestarted PostgreSQL.

This script writes append-only qualification controls to the supplied isolated
database. It never manages Docker, accesses HTTP/model providers, prints a
DSN, or cleans the target database.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4


APP_DSN_ENV = "FIN_RUNTIME_POSTGRES_URI"
OPERATOR_DSN_ENV = "FIN_RUNTIME_OPERATOR_POSTGRES_URI"
APP_ROLE = "fin_runtime_app"
OPERATOR_ROLE = "fin_runtime_operator"
EXECUTION_PROFILE = "zero_model_control_plane_v1"
_ATTEMPT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")


class QualificationFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class Contracts:
    run: Any
    invocation: Any


@dataclass(frozen=True, slots=True)
class CaseFixture:
    contracts: Contracts
    case: Any


def _digest(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise QualificationFailure(f"{name.lower()}_missing")
    return value


def _expect_rejected(
    pool: Any,
    check_id: str,
    expected_sqlstate: str,
    operation: Callable[[Any], None],
    *,
    expected_constraint: str | None = None,
    expected_message: str | None = None,
) -> dict[str, str]:
    """Run one negative mutation and roll it back in all cases."""

    with pool.connection() as connection:
        try:
            operation(connection)
        except Exception as exc:
            sqlstate = getattr(exc, "sqlstate", None)
            diagnostics = getattr(exc, "diag", None)
            constraint = getattr(diagnostics, "constraint_name", None)
            message = getattr(diagnostics, "message_primary", None)
            connection.rollback()
            if sqlstate != expected_sqlstate:
                safe_state = sqlstate if isinstance(sqlstate, str) else "none"
                raise QualificationFailure(
                    f"{check_id}_unexpected_sqlstate_{safe_state}"
                ) from None
            if expected_constraint is not None and constraint != expected_constraint:
                raise QualificationFailure(
                    f"{check_id}_unexpected_constraint"
                ) from None
            if expected_message is not None and message != expected_message:
                raise QualificationFailure(f"{check_id}_unexpected_message") from None
            guard = expected_constraint or expected_message or "sqlstate"
            return {
                "check_id": check_id,
                "sqlstate": sqlstate,
                "guard": guard,
            }
        connection.rollback()
    raise QualificationFailure(f"{check_id}_unexpectedly_accepted")


def _require_role(pool: Any, expected: str, code: str) -> None:
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT session_user::text, current_user::text"
        ).fetchone()
        connection.rollback()
    if row is None or tuple(row) != (expected, expected):
        raise QualificationFailure(code)


def _make_session(attempt_id: str) -> Any:
    from sec_agent.canonical_runtime.contracts_v1_2 import (
        create_agent_session_v1_2,
    )

    now = datetime.now(timezone.utc)
    a, b, c = (_digest(attempt_id, suffix) for suffix in ("a", "b", "c"))
    return create_agent_session_v1_2(
        session_id=f"SESSION::RC-S3-107-PG::{attempt_id}",
        thread_id=f"THREAD::RC-S3-107-PG::{attempt_id}",
        case_id="DELL_AI_INFRA_REFERENCE_VERTICAL",
        case_version="FIN_0_1_3",
        as_of_date=now.date(),
        objective_ref="objective://dell/rc-s3-107-postgres-qualification",
        objective_digest=a,
        data_snapshot_ref="snapshot://dell/rc-s3-107-postgres-qualification",
        data_snapshot_digest=b,
        runtime_policy_ref="policy://dell/rc-s3-107-postgres-v1-1",
        runtime_policy_digest=c,
        authority_refs=("authority://owner/rc-s3-107-qualification",),
        active_plan_ref="plan://dell/rc-s3-107-postgres-qualification",
        active_plan_digest=a,
        status="ACTIVE",
        created_at=now,
        updated_at=now,
    )


def _make_contracts(session: Any, attempt_id: str, suffix: str) -> Contracts:
    from sec_agent.canonical_runtime.contracts_v1_2 import (
        create_research_run,
        create_run_invocation,
    )

    now = datetime.now(timezone.utc)
    run_id = f"RUN::RC-S3-107-PG::{attempt_id}::{suffix}"
    invocation_id = f"INVOCATION::RC-S3-107-PG::{attempt_id}::{suffix}"
    run = create_research_run(
        run_id=run_id,
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
    invocation = create_run_invocation(
        invocation_id=invocation_id,
        session_id=session.session_id,
        run_id=run_id,
        ordinal=1,
        invocation_kind="START",
        status="RUNNING",
        trigger_ref=f"qualification://rc-s3-107/{attempt_id}/{suffix}/start",
        lease_ref=f"qualification://rc-s3-107/{attempt_id}/{suffix}/lease",
        started_at=now,
        finished_at=None,
    )
    return Contracts(run, invocation)


def _begin_dispatch(
    repository: Any,
    session: Any,
    attempt_id: str,
    suffix: str,
    server_thread_id: str,
    server_assistant_id: str,
) -> tuple[Contracts, Any]:
    contracts = _make_contracts(session, attempt_id, suffix)
    registration = repository.begin_run_create(
        research_run=contracts.run,
        run_invocation=contracts.invocation,
        server_thread_id=server_thread_id,
        server_invocation_kind="start",
        server_assistant_id=server_assistant_id,
        execution_profile=EXECUTION_PROFILE,
        launch_request_digest=_digest(attempt_id, suffix, "launch"),
        server_metadata_digest=_digest(attempt_id, suffix, "metadata"),
    )
    if not registration.created_now or registration.lifecycle.state != "PENDING":
        raise QualificationFailure("production_pending_control_invalid")
    lifecycle = repository.mark_run_create_dispatched(
        run_invocation_id=contracts.invocation.invocation_id,
        pending_event_digest=(
            registration.lifecycle.pending.lifecycle_event_digest
        ),
    )
    if lifecycle.state != "DISPATCHED" or lifecycle.dispatched is None:
        raise QualificationFailure("production_dispatched_control_invalid")
    return contracts, lifecycle


def _action_body(value: Any) -> dict[str, Any]:
    return dict(value.model_dump(mode="json"))


def _insert_action(
    connection: Any,
    invocation_id: str,
    row: tuple[Any, ...],
) -> None:
    ordinal, state, outcome, body = row
    connection.execute(
        """
        INSERT INTO fin_runtime.agent_server_action_attempt_snapshots (
            run_invocation_id, snapshot_ordinal, action_state, action_outcome,
            action_attempt_id, action_attempt_digest, canonical_action_attempt
        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            invocation_id,
            ordinal,
            state,
            outcome,
            body["action_attempt_id"],
            body["action_attempt_digest"],
            _json(body),
        ),
    )


def _insert_actions(
    connection: Any,
    invocation_id: str,
    rows: Sequence[tuple[Any, ...]],
) -> None:
    for row in rows:
        _insert_action(connection, invocation_id, row)


def _local_actions(
    session: Any,
    attempt_id: str,
    suffix: str,
) -> tuple[Any, ...]:
    from sec_agent.agent_runtime.dell_agent_server_recovery import (
        create_run_create_action_ambiguous,
        create_run_create_action_applied,
        create_run_create_action_dispatched,
        create_run_create_action_intent,
    )

    contracts = _make_contracts(session, attempt_id, suffix)
    intent = create_run_create_action_intent(
        research_run=contracts.run,
        source_invocation=contracts.invocation,
        launch_request_digest=_digest(attempt_id, suffix, "launch"),
    )
    dispatched = create_run_create_action_dispatched(intent)
    terminal_at = contracts.invocation.started_at + timedelta(seconds=1)
    applied = create_run_create_action_applied(
        dispatched,
        server_run_id=str(uuid4()),
        server_observation_digest=_digest(attempt_id, suffix, "receipt"),
        terminal_at=terminal_at,
    )
    ambiguous = create_run_create_action_ambiguous(
        dispatched,
        terminal_at=terminal_at,
    )
    return contracts, intent, dispatched, applied, ambiguous


def _action_checks(
    app_pool: Any,
    repository: Any,
    session: Any,
    attempt_id: str,
    server_thread_id: str,
    server_assistant_id: str,
) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    names = (
        "action_state_payload_mismatch",
        "action_boolean_string_rejected",
        "action_dispatched_boolean_profile",
        "action_ambiguous_receipt_forbidden",
        "action_applied_receipt_required",
        "action_immutable_lineage_drift",
        "action_dispatched_lifecycle_closure_required",
    )
    for index, check_id in enumerate(names):
        contracts, _, dispatched, applied, ambiguous = _local_actions(
            session,
            attempt_id,
            f"action-{index}",
        )
        registration = repository.begin_run_create(
            research_run=contracts.run,
            run_invocation=contracts.invocation,
            server_thread_id=server_thread_id,
            server_invocation_kind="start",
            server_assistant_id=server_assistant_id,
            execution_profile=EXECUTION_PROFILE,
            launch_request_digest=_digest(
                attempt_id,
                f"action-{index}",
                "launch",
            ),
            server_metadata_digest=_digest(
                attempt_id,
                f"action-{index}",
                "metadata",
            ),
        )
        if not registration.created_now or registration.lifecycle.state != "PENDING":
            raise QualificationFailure("action_pending_scaffold_invalid")
        dispatch_body = _action_body(dispatched)
        if index == 0:
            bad = deepcopy(dispatch_body)
            bad["state"] = "INTENT_COMMITTED"
            rows = [(2, "DISPATCHED", None, bad)]
        elif index == 1:
            bad = deepcopy(dispatch_body)
            bad["was_dispatched"] = "true"
            rows = [(2, "DISPATCHED", None, bad)]
        elif index == 2:
            bad = deepcopy(dispatch_body)
            bad["potentially_chargeable"] = False
            rows = [(2, "DISPATCHED", None, bad)]
        elif index == 3:
            bad = _action_body(ambiguous)
            bad.update(
                receipt_kind="SUCCESS",
                receipt_ref=f"agent-server://runs/{uuid4()}",
                receipt_digest=_digest(attempt_id, "forbidden-receipt"),
            )
            rows = [
                (2, "DISPATCHED", None, dispatch_body),
                (3, "TERMINAL", "AMBIGUOUS_AFTER_DISPATCH", bad),
            ]
        elif index == 4:
            bad = _action_body(applied)
            bad.update(
                receipt_kind=None,
                receipt_ref=None,
                receipt_digest=None,
            )
            rows = [
                (2, "DISPATCHED", None, dispatch_body),
                (3, "TERMINAL", "APPLIED", bad),
            ]
        elif index == 5:
            bad = deepcopy(dispatch_body)
            bad["created_at"] = (
                contracts.invocation.started_at + timedelta(seconds=1)
            ).isoformat()
            rows = [(2, "DISPATCHED", None, bad)]
        else:
            rows = [(2, "DISPATCHED", None, dispatch_body)]

        def operation(
            connection: Any,
            invocation_id: str = contracts.invocation.invocation_id,
            action_rows: tuple[tuple[Any, ...], ...] = tuple(rows),
            force_deferred: bool = index == 6,
        ) -> None:
            _insert_actions(connection, invocation_id, action_rows)
            if force_deferred:
                connection.execute(
                    "SET CONSTRAINTS "
                    "fin_runtime."
                    "agent_server_action_attempt_require_lifecycle_closure "
                    "IMMEDIATE"
                )

        target_constraint = (
            "agent_server_action_attempt_snapshots_digest_valid"
            if index == 0
            else "agent_server_action_attempt_snapshots_profile_valid"
            if index in {1, 2, 3, 4}
            else None
        )
        target_message = (
            "fin_runtime_run_create_action_intent_lineage_required"
            if index == 5
            else "fin_runtime_run_create_action_lifecycle_closure_required"
            if index == 6
            else None
        )
        checks.append(
            _expect_rejected(
                app_pool,
                check_id,
                "23514",
                operation,
                expected_constraint=target_constraint,
                expected_message=target_message,
            )
        )

    timestamp_mutants = (
        ("action_extra_key_rejected", "qualification_extra", True, False),
        ("action_created_at_invalid", "created_at", "not-a-timestamp", False),
        (
            "action_created_at_timezone_naive",
            "created_at",
            "2026-09-04T12:00:00",
            False,
        ),
        ("action_created_at_infinity", "created_at", "infinity", False),
        ("action_terminal_at_invalid", "terminal_at", "not-a-timestamp", True),
        ("action_terminal_at_infinity", "terminal_at", "infinity", True),
    )
    for index, (check_id, field, value, terminal) in enumerate(
        timestamp_mutants,
        start=len(names),
    ):
        contracts, _, dispatched, _, ambiguous = _local_actions(
            session,
            attempt_id,
            f"action-{index}",
        )
        registration = repository.begin_run_create(
            research_run=contracts.run,
            run_invocation=contracts.invocation,
            server_thread_id=server_thread_id,
            server_invocation_kind="start",
            server_assistant_id=server_assistant_id,
            execution_profile=EXECUTION_PROFILE,
            launch_request_digest=_digest(
                attempt_id,
                f"action-{index}",
                "launch",
            ),
            server_metadata_digest=_digest(
                attempt_id,
                f"action-{index}",
                "metadata",
            ),
        )
        if not registration.created_now or registration.lifecycle.state != "PENDING":
            raise QualificationFailure("action_pending_scaffold_invalid")
        if terminal:
            bad = _action_body(ambiguous)
            bad[field] = value
            rows = (
                (2, "DISPATCHED", None, _action_body(dispatched)),
                (3, "TERMINAL", "AMBIGUOUS_AFTER_DISPATCH", bad),
            )
        else:
            bad = _action_body(dispatched)
            bad[field] = value
            rows = ((2, "DISPATCHED", None, bad),)
        checks.append(
            _expect_rejected(
                app_pool,
                check_id,
                "23514",
                lambda connection,
                invocation_id=contracts.invocation.invocation_id,
                rows=rows: _insert_actions(connection, invocation_id, rows),
                expected_constraint=(
                    "agent_server_action_attempt_snapshots_profile_valid"
                    if terminal
                    else "agent_server_action_attempt_snapshots_digest_valid"
                ),
            )
        )
    return checks


def _pending_ordinal_unique_check(
    app_pool: Any,
    pending: Any,
    attempt_id: str,
) -> dict[str, str]:
    second_invocation_id = (
        f"INVOCATION::RC-S3-107-PG::{attempt_id}::ordinal-collision"
    )

    def operation(connection: Any) -> None:
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
            ) VALUES (
                %s, 1, 'PENDING', %s, %s, %s, %s, %s, %s::uuid,
                %s, %s::uuid, %s, %s, %s, %s, %s, %s,
                NULL, NULL, NULL, NULL, NULL, NULL, %s
            )
            """,
            (
                second_invocation_id,
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
                _digest(attempt_id, "ordinal-collision", "invocation"),
                _digest(attempt_id, "ordinal-collision", "launch"),
                _digest(attempt_id, "ordinal-collision", "metadata"),
                _digest(attempt_id, "ordinal-collision", "event"),
            ),
        )

    return _expect_rejected(
        app_pool,
        "lifecycle_run_ordinal_pending_unique",
        "23505",
        operation,
        expected_constraint=(
            "agent_server_run_create_lifecycle_run_ordinal_pending_unique"
        ),
    )


def _prepare_case_fixture(
    app_pool: Any,
    repository: Any,
    session: Any,
    attempt_id: str,
    server_thread_id: str,
    server_assistant_id: str,
) -> CaseFixture:
    from sec_agent.agent_runtime.dell_agent_server_recovery import (
        create_interrupted_source_invocation,
        create_recovery_case,
        create_recovery_required_research_run,
        create_run_create_action_ambiguous,
    )

    contracts, lifecycle = _begin_dispatch(
        repository,
        session,
        attempt_id,
        "case-mutants",
        server_thread_id,
        server_assistant_id,
    )
    server_run_id = str(uuid4())
    lifecycle = repository.record_run_create_orphan(
        run_invocation_id=contracts.invocation.invocation_id,
        pending_event_digest=lifecycle.pending.lifecycle_event_digest,
        recovery_reason_code="qualification_payload_mutation",
        server_observation_digest=_digest(
            attempt_id,
            "case-mutants",
            "observation",
        ),
        server_run_id=server_run_id,
        server_run_status="pending",
    )
    dispatched = repository.get_run_create_action_attempt(
        run_invocation_id=contracts.invocation.invocation_id,
        action_state="DISPATCHED",
    )
    if dispatched is None or lifecycle.orphan is None:
        raise QualificationFailure("recovery_case_scaffold_invalid")
    terminal_at = max(
        datetime.now(timezone.utc),
        contracts.invocation.started_at + timedelta(microseconds=1),
    )
    ambiguous = create_run_create_action_ambiguous(
        dispatched,
        terminal_at=terminal_at,
    )
    source = create_interrupted_source_invocation(
        contracts.invocation,
        finished_at=terminal_at,
    )
    case = create_recovery_case(
        recovery_run=create_recovery_required_research_run(contracts.run),
        source_invocation=source,
        ambiguous_action=ambiguous,
        lifecycle_event_digest=lifecycle.orphan.lifecycle_event_digest,
        recovery_reason_code="qualification_payload_mutation",
        server_run_id=server_run_id,
        server_run_status="pending",
        opened_at=terminal_at,
    )
    return CaseFixture(contracts, case)


def _insert_case(
    connection: Any,
    fixture: CaseFixture,
    bodies: tuple[
        Mapping[str, Any],
        Mapping[str, Any],
        Mapping[str, Any],
    ],
) -> None:
    case = fixture.case
    run_body, invocation_body, action_body = bodies
    connection.execute(
        """
        INSERT INTO fin_runtime.agent_server_recovery_cases (
            recovery_case_id, run_invocation_id, research_run_id,
            agent_session_id, recovery_research_run_digest,
            source_run_invocation_digest, ambiguous_action_attempt_id,
            ambiguous_action_attempt_digest, lifecycle_event_digest,
            recovery_reason_code, server_run_id, server_run_status,
            canonical_recovery_research_run, canonical_source_run_invocation,
            canonical_ambiguous_action_attempt, opened_at, recovery_case_digest
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s::uuid, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s
        )
        """,
        (
            case.recovery_case_id,
            case.source_invocation.invocation_id,
            case.research_run.run_id,
            case.research_run.session_id,
            case.research_run.run_digest,
            case.source_invocation.invocation_digest,
            case.ambiguous_action.action_attempt_id,
            case.ambiguous_action.action_attempt_digest,
            case.lifecycle_event_digest,
            case.recovery_reason_code,
            case.server_run_id,
            case.server_run_status,
            _json(run_body),
            _json(invocation_body),
            _json(action_body),
            case.opened_at,
            case.recovery_case_digest,
        ),
    )


def _case_checks(
    app_pool: Any,
    fixture: CaseFixture,
) -> list[dict[str, str]]:
    case = fixture.case
    base = (
        dict(case.research_run.model_dump(mode="json")),
        dict(case.source_invocation.model_dump(mode="json")),
        dict(case.ambiguous_action.model_dump(mode="json")),
    )
    names = (
        "recovery_run_numeric_type_required",
        "recovery_run_explicit_null_required",
        "recovery_source_numeric_ordinal_required",
        "recovery_ambiguous_boolean_required",
        "recovery_ambiguous_exact_copy_required",
    )
    mutants: list[tuple[str, tuple[dict[str, Any], ...]]] = []
    for index, check_id in enumerate(names):
        bodies = tuple(deepcopy(item) for item in base)
        run, invocation, action = bodies
        if index == 0:
            run["last_session_sequence"] = "0"
        elif index == 1:
            run.pop("terminal_at", None)
        elif index == 2:
            invocation["ordinal"] = "1"
        elif index == 3:
            action["was_dispatched"] = "true"
        else:
            action["actor_id"] = "runtime://qualification-tamper"
        mutants.append((check_id, bodies))

    extra_mutants = (
        ("recovery_run_extra_key_rejected", 0, "qualification_extra", True, False),
        ("recovery_run_required_field_missing", 0, "base_plan_ref", None, True),
        (
            "recovery_invocation_required_field_missing",
            1,
            "trigger_ref",
            None,
            True,
        ),
        ("recovery_run_created_at_invalid", 0, "created_at", "not-a-timestamp", False),
        ("recovery_run_created_at_infinity", 0, "created_at", "infinity", False),
        (
            "recovery_invocation_started_at_invalid",
            1,
            "started_at",
            "not-a-timestamp",
            False,
        ),
        (
            "recovery_invocation_started_at_infinity",
            1,
            "started_at",
            "infinity",
            False,
        ),
        (
            "recovery_action_created_at_invalid",
            2,
            "created_at",
            "not-a-timestamp",
            False,
        ),
        (
            "recovery_action_created_at_infinity",
            2,
            "created_at",
            "infinity",
            False,
        ),
        (
            "recovery_action_terminal_at_invalid",
            2,
            "terminal_at",
            "not-a-timestamp",
            False,
        ),
        (
            "recovery_action_terminal_at_infinity",
            2,
            "terminal_at",
            "infinity",
            False,
        ),
    )
    for check_id, body_index, field, value, remove in extra_mutants:
        bodies = tuple(deepcopy(item) for item in base)
        if remove:
            bodies[body_index].pop(field, None)
        else:
            bodies[body_index][field] = value
        mutants.append((check_id, bodies))
    bodies = tuple(deepcopy(item) for item in base)
    bodies[1]["ordinal"] = 2
    bodies[1]["invocation_kind"] = "RESUME"
    mutants.append(("recovery_source_lifecycle_lineage_required", bodies))

    checks: list[dict[str, str]] = []
    for check_id, bodies in mutants:
        trigger_message = (
            "fin_runtime_recovery_case_ambiguous_action_invalid"
            if check_id == "recovery_ambiguous_exact_copy_required"
            else "fin_runtime_recovery_case_orphan_binding_invalid"
            if check_id == "recovery_source_lifecycle_lineage_required"
            else None
        )
        def operation(
            connection: Any,
            bodies: tuple[dict[str, Any], ...] = bodies,
        ) -> None:
            _insert_action(
                connection,
                fixture.contracts.invocation.invocation_id,
                (
                    3,
                    "TERMINAL",
                    "AMBIGUOUS_AFTER_DISPATCH",
                    _action_body(fixture.case.ambiguous_action),
                ),
            )
            _insert_case(connection, fixture, bodies)

        checks.append(
            _expect_rejected(
                app_pool,
                check_id,
                "23514",
                operation,
                expected_constraint=(
                    None
                    if trigger_message
                    else "agent_server_recovery_cases_payload_valid"
                ),
                expected_message=trigger_message,
            )
        )
    return checks


def _append_disposition(
    connection: Any,
    case_id: str,
    body: Mapping[str, Any],
) -> None:
    connection.execute(
        "SELECT fin_runtime.append_recovery_disposition(%s, %s::jsonb)",
        (case_id, _json(body)),
    ).fetchone()


def _insert_disposition(
    connection: Any,
    case_id: str,
    body: Mapping[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO fin_runtime.agent_server_recovery_dispositions (
            recovery_disposition_id, recovery_case_id, run_invocation_id,
            agent_session_id, research_run_id, research_run_digest,
            ambiguous_action_attempt_id, ambiguous_action_attempt_digest,
            source_run_invocation_id, source_run_invocation_digest,
            recovery_decision, decision_authority_ref,
            recovery_disposition_digest, canonical_recovery_disposition
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s::jsonb
        )
        """,
        (
            body["recovery_disposition_id"],
            case_id,
            body["source_run_invocation_id"],
            body["session_id"],
            body["run_id"],
            body["research_run_digest"],
            body["ambiguous_action_attempt_id"],
            body["ambiguous_action_attempt_digest"],
            body["source_run_invocation_id"],
            body["source_run_invocation_digest"],
            body["decision"],
            body["decision_authority_ref"],
            body["recovery_disposition_digest"],
            _json(body),
        ),
    )


def _disposition_checks(
    app_pool: Any,
    operator_pool: Any,
    app_repository: Any,
    operator_repository: Any,
    case: Any,
    attempt_id: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]], Any]:
    from sec_agent.canonical_runtime.contracts_v1_2 import (
        create_recovery_disposition,
    )

    disposition = create_recovery_disposition(
        recovery_disposition_id=(
            f"RECOVERY-DISPOSITION::RC-S3-107-PG::{attempt_id}"
        ),
        session_id=case.research_run.session_id,
        run_id=case.research_run.run_id,
        research_run_digest=case.research_run.run_digest,
        ambiguous_action_attempt_id=case.ambiguous_action.action_attempt_id,
        ambiguous_action_attempt_digest=(
            case.ambiguous_action.action_attempt_digest
        ),
        source_run_invocation_id=case.source_invocation.invocation_id,
        source_run_invocation_digest=case.source_invocation.invocation_digest,
        investigation_receipt_refs=(
            f"qualification://rc-s3-107/{attempt_id}/operator-review",
        ),
        potentially_duplicate_cost=True,
        decision="DO_NOT_RETRY",
        decision_authority_ref="authority://rc-s3-107/recovery-operator",
        next_run_invocation_id=None,
        next_run_invocation_digest=None,
        replacement_action_attempt_id=None,
        replacement_action_attempt_digest=None,
        created_at=max(datetime.now(timezone.utc), case.opened_at),
    )
    body = dict(disposition.model_dump(mode="json"))
    permissions = [
        _expect_rejected(
            app_pool,
            "app_operator_function_forbidden",
            "42501",
            lambda connection: _append_disposition(
                connection,
                case.recovery_case_id,
                body,
            ),
        ),
        _expect_rejected(
            operator_pool,
            "operator_direct_insert_forbidden",
            "42501",
            lambda connection: _insert_disposition(
                connection,
                case.recovery_case_id,
                body,
            ),
        ),
    ]
    continuation = (
        "next_run_invocation_id",
        "next_run_invocation_digest",
        "replacement_action_attempt_id",
        "replacement_action_attempt_digest",
    )
    mutants: list[tuple[str, dict[str, Any]]] = []
    for field in continuation:
        bad = deepcopy(body)
        bad.pop(field, None)
        mutants.append((f"disposition_missing_{field}", bad))
    for check_id, field, value in (
        (
            "disposition_extra_key_rejected",
            "qualification_extra",
            True,
        ),
        (
            "disposition_boolean_string_rejected",
            "potentially_duplicate_cost",
            "true",
        ),
        (
            "disposition_duplicate_cost_false_rejected",
            "potentially_duplicate_cost",
            False,
        ),
        (
            "disposition_non_null_continuation_rejected",
            "next_run_invocation_id",
            f"INVOCATION::RC-S3-107-PG::{attempt_id}::forbidden",
        ),
    ):
        bad = deepcopy(body)
        bad[field] = value
        mutants.append((check_id, bad))
    for check_id, value in (
        ("disposition_created_at_invalid", "not-a-timestamp"),
        ("disposition_created_at_postgres_relative", "today"),
        ("disposition_created_at_infinity", "infinity"),
    ):
        bad = deepcopy(body)
        bad["created_at"] = value
        mutants.append((check_id, bad))
    negatives: list[dict[str, str]] = []
    for check_id, bad in mutants:
        is_time_check = check_id.startswith("disposition_created_at_")
        negatives.append(
            _expect_rejected(
                operator_pool,
                check_id,
                "23514",
                lambda connection, bad=bad: _append_disposition(
                    connection,
                    case.recovery_case_id,
                    bad,
                ),
                expected_constraint=(
                    None
                    if is_time_check
                    else "agent_server_recovery_dispositions_payload_valid"
                ),
                expected_message=(
                    "fin_runtime_recovery_disposition_time_invalid"
                    if is_time_check
                    else None
                ),
            )
        )
    persisted = operator_repository.record_recovery_disposition(
        recovery_case_id=case.recovery_case_id,
        disposition=disposition,
    )
    readback = app_repository.get_run_create_recovery_disposition(
        run_invocation_id=case.source_invocation.invocation_id
    )
    persisted_body = persisted.model_dump(mode="json")
    if (
        readback != persisted
        or persisted.decision != "DO_NOT_RETRY"
        or any(
            field not in persisted_body or persisted_body[field] is not None
            for field in continuation
        )
    ):
        raise QualificationFailure("valid_explicit_null_disposition_invalid")
    return permissions, negatives, persisted


def qualify(attempt_id: str, timeout: int) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / "src"))
    try:
        from psycopg_pool import ConnectionPool

        from sec_agent.agent_runtime.dell_agent_server_identity import (
            PostgresDellAgentServerIdentityRepository,
            PostgresDellAgentServerRecoveryOperatorRepository,
        )
    except Exception:
        raise QualificationFailure("qualification_import_failed") from None

    session = _make_session(attempt_id)
    thread_id, assistant_id = str(uuid4()), str(uuid4())
    try:
        with ConnectionPool(
            _required_env(APP_DSN_ENV),
            min_size=1,
            max_size=2,
            open=True,
            timeout=timeout,
        ) as app_pool, ConnectionPool(
            _required_env(OPERATOR_DSN_ENV),
            min_size=1,
            max_size=1,
            open=True,
            timeout=timeout,
        ) as operator_pool:
            app_pool.wait(timeout=timeout)
            operator_pool.wait(timeout=timeout)
            _require_role(app_pool, APP_ROLE, "app_session_role_invalid")
            _require_role(
                operator_pool,
                OPERATOR_ROLE,
                "operator_session_role_invalid",
            )
            repository = PostgresDellAgentServerIdentityRepository(app_pool)
            operator_repository = (
                PostgresDellAgentServerRecoveryOperatorRepository(operator_pool)
            )
            binding = repository.bind_agent_session(
                agent_session=session,
                server_thread_id=thread_id,
            )
            if binding.agent_session_id != session.session_id:
                raise QualificationFailure("production_session_control_invalid")

            contracts, lifecycle = _begin_dispatch(
                repository,
                session,
                attempt_id,
                "valid-control",
                thread_id,
                assistant_id,
            )
            case = repository.mark_run_create_recovery_required(
                research_run=contracts.run,
                run_invocation=contracts.invocation,
                pending_event_digest=lifecycle.pending.lifecycle_event_digest,
                recovery_reason_code="remote_create_outcome_unknown",
                server_observation_digest=_digest(
                    attempt_id,
                    "exact-observation",
                ),
                server_run_id=str(uuid4()),
                server_run_status="pending",
            )
            durable = repository.get_run_create_lifecycle(
                run_invocation_id=contracts.invocation.invocation_id
            )
            if (
                durable is None
                or durable.state != "ORPHAN"
                or durable.pending.lifecycle_ordinal != 1
                or durable.dispatched is None
                or durable.dispatched.lifecycle_ordinal != 2
                or durable.orphan is None
                or durable.orphan.lifecycle_ordinal != 3
                or repository.get_run_create_recovery_case(
                    run_invocation_id=contracts.invocation.invocation_id
                )
                != case
            ):
                raise QualificationFailure("production_orphan_control_invalid")

            lifecycle = _pending_ordinal_unique_check(
                app_pool,
                durable.pending,
                attempt_id,
            )
            action = _action_checks(
                app_pool,
                repository,
                session,
                attempt_id,
                thread_id,
                assistant_id,
            )
            fixture = _prepare_case_fixture(
                app_pool,
                repository,
                session,
                attempt_id,
                thread_id,
                assistant_id,
            )
            recovery_case = _case_checks(app_pool, fixture)
            permissions, disposition, persisted = _disposition_checks(
                app_pool,
                operator_pool,
                repository,
                operator_repository,
                case,
                attempt_id,
            )
    except QualificationFailure:
        raise
    except Exception as exc:
        raise QualificationFailure(
            f"postgres_qualification_unexpected_{type(exc).__name__.lower()}"
        ) from None

    return {
        "schema_version": "fin.rc_s3_107.postgres_lifecycle_qualification.v1",
        "attempt_id": attempt_id,
        "status": "pass",
        "target": "prestarted_isolated_postgresql",
        "roles": {"application": APP_ROLE, "operator": OPERATOR_ROLE},
        "production_control": {
            "lifecycle_states": ["PENDING", "DISPATCHED", "ORPHAN"],
            "recovery_case_persisted": True,
            "operator_decision": persisted.decision,
            "explicit_null_continuation_persisted": True,
        },
        "negative_checks": {
            "lifecycle": [lifecycle],
            "action_attempt": action,
            "recovery_case": recovery_case,
            "recovery_disposition": disposition,
            "permissions": permissions,
        },
        "counts": {
            "lifecycle_negative": 1,
            "action_attempt_negative": len(action),
            "recovery_case_negative": len(recovery_case),
            "recovery_disposition_negative": len(disposition),
            "permission_negative": len(permissions),
        },
        "external_effects": {
            "docker_management_calls": 0,
            "model_provider_calls": 0,
            "http_calls": 0,
            "external_research_calls": 0,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Qualify lifecycle v1.1 on an already-running isolated PostgreSQL; "
            f"read DSNs from {APP_DSN_ENV} and {OPERATOR_DSN_ENV}."
        )
    )
    parser.add_argument("--attempt-id", default=None)
    parser.add_argument("--connect-timeout", type=int, default=10)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    attempt_id = args.attempt_id or f"rc-s3-107-pg-{uuid4().hex[:12]}"
    if not _ATTEMPT_RE.fullmatch(attempt_id):
        raise QualificationFailure("attempt_id_invalid")
    if not 1 <= args.connect_timeout <= 120:
        raise QualificationFailure("connect_timeout_invalid")
    print(_json(qualify(attempt_id, args.connect_timeout)))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QualificationFailure as exc:
        print(
            _json(
                {
                    "schema_version": (
                        "fin.rc_s3_107.postgres_lifecycle_qualification.v1"
                    ),
                    "status": "fail",
                    "failure_code": exc.code,
                }
            ),
            file=sys.stderr,
        )
        raise SystemExit(2) from None
