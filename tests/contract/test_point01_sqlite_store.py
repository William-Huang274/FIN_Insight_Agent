from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from sec_agent.canonical_runtime.models import ActorSnapshot, EventEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.store import (
    OBJECT_TABLES,
    KillSwitchEnabled,
    SQLiteCanonicalStore,
    TransactionConflict,
)


pytestmark = pytest.mark.fast_contract


def _actor() -> ActorSnapshot:
    now = datetime.now(timezone.utc)
    return ActorSnapshot(
        tenant_id="tenant-test",
        project_id="project-test",
        created_at=now,
        recorded_at=now,
        actor_snapshot_ref="actor-1",
        permission_snapshot_ref="permission-1",
        correlation_id="correlation-1",
        current_status="active",
        actor_snapshot_id="actor-1",
        snapshot_version=1,
        actor_id="user-1",
        actor_type="human",
        display_name="Test User",
    )


def test_store_creates_all_logical_tables_and_enforces_append_only(tmp_path) -> None:
    store = SQLiteCanonicalStore(tmp_path / "canonical.sqlite")
    with sqlite3.connect(store.db_path) as connection:
        names = {row[0] for row in connection.execute("select name from sqlite_master where type = 'table'")}
    assert set(OBJECT_TABLES).issubset(names)
    assert {"canonical_events", "canonical_outbox", "canonical_schema_migrations"}.issubset(names)

    actor = _actor()
    with store.transaction() as tx:
        tx.insert("canonical_actor_snapshots", actor.actor_snapshot_id, 1, actor.model_dump(mode="json"))
    with sqlite3.connect(store.db_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append_only_table"):
            connection.execute("update canonical_actor_snapshots set current_status = 'changed'")


def test_object_store_uses_portable_key_and_checks_digest(tmp_path) -> None:
    store = FileCanonicalObjectStore(tmp_path / "objects")
    ref = store.put_json({"b": 2, "a": 1}, namespace="point01/test", artifact_type="fixture")
    assert not ref["object_key"].startswith(str(tmp_path))
    assert ":" not in ref["object_key"]
    assert store.get_json(ref["object_key"], expected_digest=ref["digest"]) == {"a": 1, "b": 2}


def test_kill_switch_fails_closed_without_deleting_history(tmp_path) -> None:
    store = SQLiteCanonicalStore(tmp_path / "canonical.sqlite")
    actor = _actor()
    with store.transaction() as tx:
        tx.insert("canonical_actor_snapshots", actor.actor_snapshot_id, 1, actor.model_dump(mode="json"))
    store.set_kill_switch(True)
    with pytest.raises(KillSwitchEnabled):
        with store.transaction():
            pass
    assert store.get_latest("canonical_actor_snapshots", "actor-1") is not None


def test_sqlite_lock_timeout_is_typed_transaction_conflict(tmp_path) -> None:
    store = SQLiteCanonicalStore(tmp_path / "canonical.sqlite", busy_timeout_ms=10)
    blocker = sqlite3.connect(store.db_path, isolation_level=None)
    try:
        blocker.execute("begin immediate")
        with pytest.raises(TransactionConflict, match="transaction_conflict"):
            with store.transaction():
                pass
    finally:
        blocker.rollback()
        blocker.close()


def test_failed_transaction_rolls_back_and_reopens_with_append_only_history(tmp_path) -> None:
    store = SQLiteCanonicalStore(tmp_path / "canonical.sqlite")
    actor = _actor()
    with pytest.raises(RuntimeError, match="fixture_abort"):
        with store.transaction() as tx:
            tx.insert("canonical_actor_snapshots", actor.actor_snapshot_id, 1, actor.model_dump(mode="json"))
            raise RuntimeError("fixture_abort")
    reopened = SQLiteCanonicalStore(store.db_path)
    assert reopened.get_latest("canonical_actor_snapshots", actor.actor_snapshot_id) is None
    assert reopened.recovery_check() == {
        "database_integrity": "ok",
        "missing_outbox_count": 0,
        "orphan_outbox_count": 0,
        "status": "pass",
    }


def test_store_rejects_case_scope_and_attempt_parent_violations(tmp_path) -> None:
    store = SQLiteCanonicalStore(tmp_path / "canonical.sqlite")
    case_row = {
        "tenant_id": "tenant-test",
        "project_id": "project-test",
        "case_id": "case-1",
        "current_status": "shadow_created",
    }
    with store.transaction() as tx:
        tx.insert("canonical_research_cases", "case-1", 1, case_row)
    with pytest.raises(sqlite3.IntegrityError, match="canonical_case_scope_violation"):
        with store.transaction() as tx:
            tx.insert(
                "canonical_work_units",
                "wu-missing-case",
                1,
                {**case_row, "case_id": "case-missing", "current_status": "pending"},
            )
    with pytest.raises(sqlite3.IntegrityError, match="attempt_work_unit_parent_missing"):
        with store.transaction() as tx:
            tx.insert(
                "canonical_attempts",
                "attempt-missing-work-unit",
                1,
                {
                    **case_row,
                    "current_status": "running",
                    "work_unit_id": "wu-missing",
                    "work_unit_version": 1,
                },
            )


def test_store_rejects_duplicate_active_binding_and_event_parent_violations(tmp_path) -> None:
    store = SQLiteCanonicalStore(tmp_path / "canonical.sqlite")
    case_row = {"tenant_id": "tenant-test", "project_id": "project-test", "case_id": "case-1", "current_status": "shadow_created"}
    binding_row = {**case_row, "current_status": "active", "normalized_identity_digest": "identity-1", "binding_id": "binding-1"}
    with store.transaction() as tx:
        tx.insert("canonical_research_cases", "case-1", 1, case_row)
        tx.insert("canonical_task_run_bindings", "binding-1", 1, binding_row)
        actor = _actor()
        tx.insert("canonical_actor_snapshots", actor.actor_snapshot_id, 1, actor.model_dump(mode="json"))
        tx.insert("canonical_work_units", "wu-1", 1, {**case_row, "current_status": "running"})
        tx.insert(
            "canonical_attempts",
            "attempt-1",
            1,
            {**case_row, "current_status": "running", "work_unit_id": "wu-1", "work_unit_version": 1, "input_head_digest": "head-1"},
        )
    with pytest.raises(sqlite3.IntegrityError, match="active_legacy_binding_identity_conflict"):
        with store.transaction() as tx:
            tx.insert("canonical_task_run_bindings", "binding-2", 1, {**binding_row, "binding_id": "binding-2"})
    with pytest.raises(sqlite3.IntegrityError, match="event_work_unit_parent_missing"):
        with store.transaction() as tx:
            tx.append_event(
                EventEnvelope(
                    event_id="event-missing-work-unit",
                    event_type="WORK_UNIT_STARTED",
                    work_unit_id="wu-missing",
                    sequence_no=1,
                    occurred_at=datetime.now(timezone.utc),
                    recorded_at=datetime.now(timezone.utc),
                    actor_snapshot_ref="actor-1",
                    correlation_id="correlation-1",
                    state_version_before=0,
                    state_version_after=1,
                    payload_digest="fixture",
                )
            )
    with pytest.raises(sqlite3.IntegrityError, match="event_actor_parent_missing"):
        with store.transaction() as tx:
            tx.append_event(
                EventEnvelope(
                    event_id="event-missing-actor",
                    event_type="RESEARCH_CASE_CREATED",
                    sequence_no=1,
                    occurred_at=datetime.now(timezone.utc),
                    recorded_at=datetime.now(timezone.utc),
                    actor_snapshot_ref="actor-missing",
                    correlation_id="correlation-1",
                    state_version_before=0,
                    state_version_after=1,
                    payload_digest="fixture",
                )
            )
    with pytest.raises(sqlite3.IntegrityError, match="artifact_attempt_parent_missing"):
        with store.transaction() as tx:
            tx.insert(
                "canonical_artifact_versions",
                "artifact-missing-parent",
                1,
                {**case_row, "current_status": "shadow_current", "producer_attempt_id": "attempt-missing", "input_refs_digest": "head-1"},
            )
