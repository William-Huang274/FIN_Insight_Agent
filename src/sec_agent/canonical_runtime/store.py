from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from .models import EventEnvelope, canonical_digest, utc_now


SCHEMA_MIGRATION = "fin01_s1_t02_001"

OBJECT_TABLES = (
    "canonical_research_cases",
    "canonical_case_control_versions",
    "canonical_task_run_bindings",
    "canonical_work_units",
    "canonical_attempts",
    "canonical_research_run_versions",
    "canonical_actor_snapshots",
    "canonical_artifact_versions",
    "canonical_decision_surface_contract_versions",
    "canonical_decision_surface_cell_versions",
    "canonical_evidence_slot_versions",
    "canonical_planning_checkpoint_versions",
    "canonical_compile_gap_versions",
    "canonical_evidence_workbench_projection_versions",
    "canonical_evidence_review_action_versions",
    "canonical_evidence_repair_outcome_versions",
    "canonical_numeric_workbench_projection_versions",
    "canonical_workpaper_projection_versions",
    "canonical_lead_review_decision_versions",
    "canonical_deliverable_projection_versions",
    "canonical_deliverable_review_action_versions",
    "canonical_artifact_provenance_manifest_versions",
    "canonical_shadow_comparisons",
    "canonical_lane_cutover_decisions",
    "canonical_legacy_identity_map",
    "canonical_hitl_approval_versions",
    "canonical_parallel_snapshot_versions",
    "canonical_parallel_impact_decisions",
    "canonical_trace_span_versions",
    "canonical_operations_alert_versions",
    "canonical_hitl_registry_versions",
    "canonical_budget_reservation_versions",
    "canonical_budget_ledger_versions",
    "canonical_budget_stop_versions",
    "canonical_capability_grant_versions",
    "canonical_security_admission_versions",
    "canonical_tool_invocation_receipt_versions",
    "canonical_candidate_bundle_versions",
    "canonical_repair_ticket_versions",
    "canonical_parser_numeric_stop_versions",
    "canonical_m6_global_one_shot_approval_versions",
    "canonical_sec_document_invocation_receipt_versions",
    "canonical_sec_document_candidate_versions",
    "canonical_sec_document_parser_versions",
    "canonical_sec_document_numeric_fact_versions",
    "canonical_sec_document_numeric_trace_versions",
    "canonical_sec_document_terminal_stop_versions",
)


class CanonicalStoreError(RuntimeError):
    pass


class StaleStateVersion(CanonicalStoreError):
    pass


class IdempotencyConflict(CanonicalStoreError):
    pass


class KillSwitchEnabled(CanonicalStoreError):
    pass


class TransactionConflict(CanonicalStoreError):
    """A backend lock/busy conflict that callers may safely retry."""


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


class SQLiteCanonicalTransaction:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def insert(self, table: str, logical_id: str, version: int, payload: Mapping[str, Any]) -> None:
        if table not in OBJECT_TABLES:
            raise ValueError(f"unknown_canonical_table:{table}")
        row = dict(payload)
        state_version = int(row.get("state_version", 0))
        self.connection.execute(
            f"""
            insert into {table} (
                logical_id, version_no, state_version, tenant_id, project_id, case_id,
                current_status, content_digest, payload_json, recorded_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                logical_id,
                version,
                state_version,
                str(row.get("tenant_id") or ""),
                str(row.get("project_id") or ""),
                row.get("case_id"),
                str(row.get("current_status") or row.get("state") or ""),
                str(row.get("content_digest") or canonical_digest(row)),
                _json(row),
                str(row.get("recorded_at") or utc_now().isoformat()),
            ),
        )

    def append_event(self, event: EventEnvelope) -> None:
        row = event.model_dump(mode="json")
        self.connection.execute(
            """
            insert into canonical_events (
                event_id, event_type, task_run_id, work_unit_id, attempt_id, sequence_no,
                actor_snapshot_ref, correlation_id, payload_digest, payload_json, recorded_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.event_type,
                event.task_run_id,
                event.work_unit_id,
                event.attempt_id,
                event.sequence_no,
                event.actor_snapshot_ref,
                event.correlation_id,
                event.payload_digest,
                _json(row),
                event.recorded_at.isoformat(),
            ),
        )
        self.connection.execute(
            "insert into canonical_outbox (event_id, delivery_status, attempt_count, created_at) values (?, 'pending', 0, ?)",
            (event.event_id, event.recorded_at.isoformat()),
        )

    def next_event_sequence(self, task_run_id: str | None) -> int:
        scope = task_run_id or "__case_scope__"
        row = self.connection.execute(
            "select coalesce(max(sequence_no), 0) + 1 from canonical_events where coalesce(task_run_id, '__case_scope__') = ?",
            (scope,),
        ).fetchone()
        return int(row[0])

    def get_idempotency(self, scope_key: str) -> Mapping[str, Any] | None:
        row = self.connection.execute(
            "select payload_digest, result_json from canonical_idempotency where scope_key = ?", (scope_key,)
        ).fetchone()
        if not row:
            return None
        return {"payload_digest": row[0], "result": json.loads(row[1])}

    def get_latest(self, table: str, logical_id: str) -> Mapping[str, Any] | None:
        if table not in OBJECT_TABLES:
            raise ValueError(f"unknown_canonical_table:{table}")
        row = self.connection.execute(
            f"select payload_json from {table} where logical_id = ? order by version_no desc, state_version desc limit 1",
            (logical_id,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def get_version(self, table: str, logical_id: str, version: int) -> Mapping[str, Any] | None:
        if table not in OBJECT_TABLES:
            raise ValueError(f"unknown_canonical_table:{table}")
        row = self.connection.execute(
            f"select payload_json from {table} where logical_id = ? and version_no = ? "
            "order by state_version desc limit 1",
            (logical_id, version),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def list_latest(self, table: str, *, case_id: str | None = None) -> list[Mapping[str, Any]]:
        if table not in OBJECT_TABLES:
            raise ValueError(f"unknown_canonical_table:{table}")
        query = f"select logical_id, payload_json from {table}"
        params: tuple[Any, ...] = ()
        if case_id is not None:
            query += " where case_id = ?"
            params = (case_id,)
        query += " order by row_id"
        rows = self.connection.execute(query, params).fetchall()
        latest: dict[str, Mapping[str, Any]] = {}
        for row in rows:
            latest[str(row[0])] = json.loads(row[1])
        return list(latest.values())

    def list_versions(self, table: str, *, case_id: str | None = None) -> list[Mapping[str, Any]]:
        if table not in OBJECT_TABLES:
            raise ValueError(f"unknown_canonical_table:{table}")
        query = f"select payload_json from {table}"
        params: tuple[Any, ...] = ()
        if case_id is not None:
            query += " where case_id = ?"
            params = (case_id,)
        query += " order by row_id"
        rows = self.connection.execute(query, params).fetchall()
        return [json.loads(row[0]) for row in rows]

    def put_idempotency(self, scope_key: str, payload_digest: str, result: Mapping[str, Any]) -> None:
        self.connection.execute(
            "insert into canonical_idempotency (scope_key, payload_digest, result_json, created_at) values (?, ?, ?, ?)",
            (scope_key, payload_digest, _json(result), utc_now().isoformat()),
        )

    def assert_expected_state(self, table: str, logical_id: str, expected: int) -> None:
        if table not in OBJECT_TABLES:
            raise ValueError(f"unknown_canonical_table:{table}")
        row = self.connection.execute(
            f"select max(state_version) from {table} where logical_id = ?", (logical_id,)
        ).fetchone()
        actual = int(row[0] or 0)
        if actual != expected:
            raise StaleStateVersion(f"stale_state_version:expected={expected}:actual={actual}")


class SQLiteCanonicalStore:
    def __init__(self, db_path: str | Path, *, busy_timeout_ms: int = 5000):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.busy_timeout_ms = busy_timeout_ms
        self.migrate()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=self.busy_timeout_ms / 1000, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma foreign_keys = on")
        connection.execute(f"pragma busy_timeout = {self.busy_timeout_ms}")
        return connection

    def migrate(self) -> None:
        with self._connect() as connection:
            connection.execute("pragma journal_mode = wal")
            connection.executescript(_ddl())
            connection.execute(
                "insert or ignore into canonical_schema_migrations (migration_id, migration_hash, applied_at) values (?, ?, ?)",
                (SCHEMA_MIGRATION, canonical_digest(_ddl()), utc_now().isoformat()),
            )
            connection.execute(
                "insert or ignore into canonical_metadata (metadata_key, metadata_value) values ('kill_switch', '0')"
            )

    @contextmanager
    def transaction(self, *, rollback_control: bool = False) -> Iterator[SQLiteCanonicalTransaction]:
        connection = self._connect()
        try:
            connection.execute("begin immediate")
            if self._kill_switch_in(connection) and not rollback_control:
                raise KillSwitchEnabled("canonical_kill_switch_enabled")
            tx = SQLiteCanonicalTransaction(connection)
            yield tx
            connection.commit()
        except sqlite3.OperationalError as exc:
            if connection.in_transaction:
                connection.rollback()
            if any(token in str(exc).lower() for token in ("locked", "busy")):
                raise TransactionConflict(f"transaction_conflict:{exc}") from exc
            raise
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def get_latest(self, table: str, logical_id: str) -> Mapping[str, Any] | None:
        if table not in OBJECT_TABLES:
            raise ValueError(f"unknown_canonical_table:{table}")
        with self._connect() as connection:
            row = connection.execute(
                f"select payload_json from {table} where logical_id = ? order by version_no desc, state_version desc limit 1",
                (logical_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def get_version(self, table: str, logical_id: str, version: int) -> Mapping[str, Any] | None:
        if table not in OBJECT_TABLES:
            raise ValueError(f"unknown_canonical_table:{table}")
        with self._connect() as connection:
            row = connection.execute(
                f"select payload_json from {table} where logical_id = ? and version_no = ? "
                "order by state_version desc limit 1",
                (logical_id, version),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def list_latest(self, table: str, *, case_id: str | None = None) -> list[Mapping[str, Any]]:
        if table not in OBJECT_TABLES:
            raise ValueError(f"unknown_canonical_table:{table}")
        query = f"select logical_id, payload_json from {table}"
        params: tuple[Any, ...] = ()
        if case_id is not None:
            query += " where case_id = ?"
            params = (case_id,)
        query += " order by row_id"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        latest: dict[str, Mapping[str, Any]] = {}
        for row in rows:
            latest[str(row[0])] = json.loads(row[1])
        return list(latest.values())

    def list_versions(self, table: str, *, case_id: str | None = None, version: int | None = None) -> list[Mapping[str, Any]]:
        if table not in OBJECT_TABLES:
            raise ValueError(f"unknown_canonical_table:{table}")
        query = f"select payload_json from {table}"
        clauses: list[str] = []
        params: list[Any] = []
        if case_id is not None:
            clauses.append("case_id = ?")
            params.append(case_id)
        if version is not None:
            clauses.append("version_no = ?")
            params.append(version)
        if clauses:
            query += " where " + " and ".join(clauses)
        query += " order by row_id"
        with self._connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def list_events(self, task_run_id: str | None = None) -> list[Mapping[str, Any]]:
        with self._connect() as connection:
            if task_run_id is None:
                rows = connection.execute("select payload_json from canonical_events order by row_id").fetchall()
            else:
                rows = connection.execute(
                    "select payload_json from canonical_events where task_run_id = ? order by sequence_no", (task_run_id,)
                ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def set_kill_switch(self, enabled: bool) -> None:
        with self._connect() as connection:
            connection.execute(
                "update canonical_metadata set metadata_value = ? where metadata_key = 'kill_switch'",
                ("1" if enabled else "0",),
            )

    def kill_switch_enabled(self) -> bool:
        with self._connect() as connection:
            return self._kill_switch_in(connection)

    def recovery_check(self) -> Mapping[str, Any]:
        """Verify the local durable boundary before a read/replay recovery."""
        with self._connect() as connection:
            integrity = connection.execute("pragma integrity_check").fetchone()[0]
            missing_outbox = connection.execute(
                "select count(*) from canonical_events event left join canonical_outbox outbox "
                "on outbox.event_id = event.event_id where outbox.event_id is null"
            ).fetchone()[0]
            orphan_outbox = connection.execute(
                "select count(*) from canonical_outbox outbox left join canonical_events event "
                "on event.event_id = outbox.event_id where event.event_id is null"
            ).fetchone()[0]
        return {
            "database_integrity": str(integrity),
            "missing_outbox_count": int(missing_outbox),
            "orphan_outbox_count": int(orphan_outbox),
            "status": "pass" if integrity == "ok" and not missing_outbox and not orphan_outbox else "fail",
        }

    def store_identity(self) -> str:
        """Stable backend identity for cutover approvals; it is not a content hash."""
        return canonical_digest(
            {
                "backend": "sqlite",
                "schema_migration": SCHEMA_MIGRATION,
                "resolved_path": str(self.db_path.resolve()).replace("\\", "/"),
            }
        )

    def content_fingerprint(self) -> str:
        """Digest durable contents without incorporating the physical store path.

        `store_identity()` deliberately includes the resolved path because it is an
        approval boundary.  A restore drill needs the inverse property: the source
        and a newly restored database live at different paths but must have exactly
        the same append-only contents.  This fingerprint therefore covers every
        versioned object, every event and the kill-switch state, in stable order.
        """
        return canonical_digest(
            {
                "schema_migration": SCHEMA_MIGRATION,
                "objects": {table: self.list_versions(table) for table in OBJECT_TABLES},
                "events": self.list_events(),
                "kill_switch_enabled": self.kill_switch_enabled(),
            }
        )

    @staticmethod
    def _kill_switch_in(connection: sqlite3.Connection) -> bool:
        row = connection.execute(
            "select metadata_value from canonical_metadata where metadata_key = 'kill_switch'"
        ).fetchone()
        return bool(row and row[0] == "1")


def _ddl() -> str:
    object_tables = "\n".join(
        f"""
        create table if not exists {table} (
            row_id integer primary key,
            logical_id text not null,
            version_no integer not null check(version_no >= 1),
            state_version integer not null default 0 check(state_version >= 0),
            tenant_id text not null,
            project_id text not null,
            case_id text,
            current_status text not null,
            content_digest text not null,
            payload_json text not null check(json_valid(payload_json)),
            recorded_at text not null,
            unique(logical_id, version_no, state_version)
        );
        create trigger if not exists {table}_no_update before update on {table}
        begin select raise(abort, 'append_only_table'); end;
        create trigger if not exists {table}_no_delete before delete on {table}
        begin select raise(abort, 'append_only_table'); end;
        """
        for table in OBJECT_TABLES
    )
    case_bound_tables = (
        "canonical_case_control_versions",
        "canonical_task_run_bindings",
        "canonical_work_units",
        "canonical_attempts",
        "canonical_research_run_versions",
        "canonical_artifact_versions",
        "canonical_decision_surface_contract_versions",
        "canonical_decision_surface_cell_versions",
        "canonical_evidence_slot_versions",
        "canonical_planning_checkpoint_versions",
        "canonical_compile_gap_versions",
        "canonical_evidence_workbench_projection_versions",
        "canonical_evidence_review_action_versions",
        "canonical_evidence_repair_outcome_versions",
        "canonical_numeric_workbench_projection_versions",
        "canonical_workpaper_projection_versions",
        "canonical_lead_review_decision_versions",
        "canonical_deliverable_projection_versions",
        "canonical_deliverable_review_action_versions",
        "canonical_artifact_provenance_manifest_versions",
        "canonical_shadow_comparisons",
        "canonical_lane_cutover_decisions",
        "canonical_hitl_approval_versions",
        "canonical_parallel_snapshot_versions",
        "canonical_parallel_impact_decisions",
        "canonical_trace_span_versions",
        "canonical_operations_alert_versions",
        "canonical_hitl_registry_versions",
        "canonical_budget_reservation_versions",
        "canonical_budget_ledger_versions",
        "canonical_budget_stop_versions",
        "canonical_capability_grant_versions",
        "canonical_security_admission_versions",
        "canonical_tool_invocation_receipt_versions",
        "canonical_candidate_bundle_versions",
        "canonical_repair_ticket_versions",
        "canonical_parser_numeric_stop_versions",
        "canonical_legacy_identity_map",
        "canonical_sec_document_invocation_receipt_versions",
        "canonical_sec_document_candidate_versions",
        "canonical_sec_document_parser_versions",
        "canonical_sec_document_numeric_fact_versions",
        "canonical_sec_document_numeric_trace_versions",
        "canonical_sec_document_terminal_stop_versions",
    )
    case_scope_triggers = "\n".join(
        f"""
        create trigger if not exists {table}_case_scope before insert on {table}
        when new.case_id is not null and not exists (
            select 1 from canonical_research_cases parent
            where parent.logical_id = new.case_id
              and parent.tenant_id = new.tenant_id
              and parent.project_id = new.project_id
        )
        begin select raise(abort, 'canonical_case_scope_violation'); end;
        """
        for table in case_bound_tables
    )
    relation_triggers = """
    create table if not exists canonical_active_legacy_bindings (
        normalized_identity_digest text primary key,
        binding_id text not null
    );

    create trigger if not exists canonical_task_run_bindings_active_identity before insert on canonical_task_run_bindings
    when new.current_status = 'active' and exists (
        select 1 from canonical_active_legacy_bindings active
        where active.normalized_identity_digest = json_extract(new.payload_json, '$.normalized_identity_digest')
          and active.binding_id != json_extract(new.payload_json, '$.binding_id')
    )
    begin select raise(abort, 'active_legacy_binding_identity_conflict'); end;

    create trigger if not exists canonical_task_run_bindings_register_active after insert on canonical_task_run_bindings
    when new.current_status = 'active'
    begin
        insert or ignore into canonical_active_legacy_bindings (normalized_identity_digest, binding_id)
        values (json_extract(new.payload_json, '$.normalized_identity_digest'), json_extract(new.payload_json, '$.binding_id'));
    end;

    create trigger if not exists canonical_attempts_work_unit_parent before insert on canonical_attempts
    when not exists (
        select 1 from canonical_work_units parent
        where parent.logical_id = json_extract(new.payload_json, '$.work_unit_id')
          and parent.version_no = cast(json_extract(new.payload_json, '$.work_unit_version') as integer)
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'attempt_work_unit_parent_missing'); end;

    create trigger if not exists canonical_research_run_versions_attempt_parent before insert on canonical_research_run_versions
    when not exists (
        select 1 from canonical_attempts parent
        where parent.logical_id = json_extract(new.payload_json, '$.attempt_id')
          and json_extract(parent.payload_json, '$.work_unit_id') = json_extract(new.payload_json, '$.work_unit_id')
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'research_run_attempt_parent_missing'); end;

    create trigger if not exists canonical_research_run_versions_attempt_identity before insert on canonical_research_run_versions
    when exists (
        select 1 from canonical_research_run_versions sibling
        where json_extract(sibling.payload_json, '$.attempt_id') = json_extract(new.payload_json, '$.attempt_id')
          and sibling.logical_id != new.logical_id
    )
    begin select raise(abort, 'attempt_research_run_identity_conflict'); end;

    drop trigger if exists canonical_artifact_versions_attempt_parent;
    create trigger canonical_artifact_versions_attempt_parent before insert on canonical_artifact_versions
    when not exists (
        select 1 from canonical_attempts parent
        where parent.logical_id = json_extract(new.payload_json, '$.producer_attempt_id')
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
          and (
            json_extract(parent.payload_json, '$.input_head_digest') = json_extract(new.payload_json, '$.input_refs_digest')
            or exists (
                select 1 from canonical_research_run_versions run
                where json_extract(run.payload_json, '$.attempt_id') = parent.logical_id
                  and run.case_id = new.case_id
                  and run.tenant_id = new.tenant_id
                  and run.project_id = new.project_id
                  and exists (
                      select 1 from json_each(json_extract(new.payload_json, '$.input_refs')) ref
                      where ref.value = json_extract(run.payload_json, '$.research_run_version_id')
                  )
            )
          )
    )
    begin select raise(abort, 'artifact_attempt_parent_missing'); end;

    create trigger if not exists canonical_decision_surface_cell_versions_contract_parent before insert on canonical_decision_surface_cell_versions
    when not exists (
        select 1 from canonical_decision_surface_contract_versions parent
        where json_extract(new.payload_json, '$.contract_version_id') = parent.logical_id || ':v' || parent.version_no
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'cell_contract_parent_missing'); end;

    create trigger if not exists canonical_evidence_slot_versions_cell_parent before insert on canonical_evidence_slot_versions
    when not exists (
        select 1 from canonical_decision_surface_cell_versions parent
        where json_extract(new.payload_json, '$.cell_version_id') = parent.logical_id || ':v' || parent.version_no
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'slot_cell_parent_missing'); end;

    create trigger if not exists canonical_planning_checkpoint_versions_contract_parent before insert on canonical_planning_checkpoint_versions
    when not exists (
        select 1 from canonical_decision_surface_contract_versions parent
        where json_extract(new.payload_json, '$.contract_version_id') = parent.logical_id || ':v' || parent.version_no
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'planning_checkpoint_contract_parent_missing'); end;

    create trigger if not exists canonical_compile_gap_versions_cell_parent before insert on canonical_compile_gap_versions
    when not exists (
        select 1 from canonical_decision_surface_cell_versions parent
        where json_extract(new.payload_json, '$.cell_version_id') = parent.logical_id || ':v' || parent.version_no
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'gap_cell_parent_missing'); end;

    create trigger if not exists canonical_evidence_workbench_projection_versions_single_version before insert on canonical_evidence_workbench_projection_versions
    when exists (
        select 1 from canonical_evidence_workbench_projection_versions parent
        where parent.logical_id = new.logical_id
    )
    begin select raise(abort, 'evidence_workbench_projection_immutable'); end;

    create trigger if not exists canonical_evidence_workbench_projection_versions_checkpoint_parent before insert on canonical_evidence_workbench_projection_versions
    when not exists (
        select 1 from canonical_planning_checkpoint_versions parent
        where json_extract(parent.payload_json, '$.checkpoint_version_id') = json_extract(new.payload_json, '$.checkpoint_version_id')
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'evidence_workbench_checkpoint_parent_missing'); end;

    create trigger if not exists canonical_evidence_workbench_projection_versions_work_unit_parent before insert on canonical_evidence_workbench_projection_versions
    when not exists (
        select 1 from canonical_work_units parent
        where parent.logical_id = json_extract(new.payload_json, '$.work_unit_id')
          and parent.version_no = cast(json_extract(new.payload_json, '$.work_unit_version') as integer)
          and parent.state_version = cast(json_extract(new.payload_json, '$.work_unit_state_version') as integer)
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'evidence_workbench_work_unit_parent_missing'); end;

    create trigger if not exists canonical_evidence_review_action_versions_projection_parent before insert on canonical_evidence_review_action_versions
    when not exists (
        select 1 from canonical_evidence_workbench_projection_versions parent
        where json_extract(parent.payload_json, '$.projection_version_id') = json_extract(new.payload_json, '$.workspace_projection_version_id')
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'evidence_review_projection_parent_missing'); end;

    create trigger if not exists canonical_evidence_repair_outcome_versions_projection_parent before insert on canonical_evidence_repair_outcome_versions
    when not exists (
        select 1 from canonical_evidence_workbench_projection_versions parent
        where json_extract(parent.payload_json, '$.projection_version_id') = json_extract(new.payload_json, '$.workspace_projection_version_id')
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'evidence_repair_projection_parent_missing'); end;

    create trigger if not exists canonical_evidence_repair_outcome_versions_action_parent before insert on canonical_evidence_repair_outcome_versions
    when not exists (
        select 1 from canonical_evidence_review_action_versions parent
        where json_extract(parent.payload_json, '$.review_action_id') = json_extract(new.payload_json, '$.request_review_action_id')
          and json_extract(parent.payload_json, '$.evidence_slot_id') = json_extract(new.payload_json, '$.evidence_slot_id')
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'evidence_repair_action_parent_missing'); end;

    create trigger if not exists canonical_numeric_workbench_projection_versions_evidence_parent before insert on canonical_numeric_workbench_projection_versions
    when not exists (
        select 1 from canonical_evidence_workbench_projection_versions parent
        where json_extract(parent.payload_json, '$.projection_version_id') = json_extract(new.payload_json, '$.evidence_projection_version_id')
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'numeric_workbench_evidence_parent_missing'); end;

    create trigger if not exists canonical_workpaper_projection_versions_numeric_parent before insert on canonical_workpaper_projection_versions
    when not exists (
        select 1 from canonical_numeric_workbench_projection_versions parent
        where json_extract(parent.payload_json, '$.numeric_projection_version_id') = json_extract(new.payload_json, '$.numeric_workspace_id') || ':v' || cast(json_extract(new.payload_json, '$.numeric_workspace_version') as text)
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'workpaper_numeric_parent_missing'); end;

    create trigger if not exists canonical_lead_review_decision_versions_workpaper_parent before insert on canonical_lead_review_decision_versions
    when not exists (
        select 1 from canonical_workpaper_projection_versions parent
        where json_extract(parent.payload_json, '$.workpaper_projection_version_id') = json_extract(new.payload_json, '$.workpaper_projection_version_id')
          and json_extract(parent.payload_json, '$.content_digest') = json_extract(new.payload_json, '$.workpaper_content_digest')
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'lead_review_workpaper_parent_missing'); end;

    create trigger if not exists canonical_deliverable_projection_versions_lead_review_parent before insert on canonical_deliverable_projection_versions
    when not exists (
        select 1 from canonical_lead_review_decision_versions parent
        where json_extract(parent.payload_json, '$.lead_review_id') = json_extract(new.payload_json, '$.lead_review_id')
          and json_extract(parent.payload_json, '$.workpaper_projection_version_id') = json_extract(new.payload_json, '$.workpaper_projection_version_id')
          and json_extract(parent.payload_json, '$.workpaper_content_digest') = json_extract(new.payload_json, '$.workpaper_content_digest')
          and json_extract(parent.payload_json, '$.writer_admission.writer_admission_id') = json_extract(new.payload_json, '$.writer_admission_id')
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'deliverable_lead_review_parent_missing'); end;

    create trigger if not exists canonical_deliverable_review_action_versions_artifact_parent before insert on canonical_deliverable_review_action_versions
    when not exists (
        select 1 from canonical_deliverable_projection_versions parent
        where json_extract(parent.payload_json, '$.artifact_version_id') = json_extract(new.payload_json, '$.artifact_version_id')
          and cast(json_extract(parent.payload_json, '$.artifact_version') as integer) = cast(json_extract(new.payload_json, '$.artifact_version') as integer)
          and json_extract(parent.payload_json, '$.content_digest') = json_extract(new.payload_json, '$.artifact_content_digest')
          and json_extract(parent.payload_json, '$.canonical_presentation_digest') = json_extract(new.payload_json, '$.canonical_presentation_digest')
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'deliverable_review_artifact_parent_missing'); end;

    create trigger if not exists canonical_artifact_provenance_manifest_versions_artifact_parent before insert on canonical_artifact_provenance_manifest_versions
    when not exists (
        select 1 from canonical_deliverable_projection_versions parent
        where json_extract(parent.payload_json, '$.artifact_version_id') = json_extract(new.payload_json, '$.artifact_version_id')
          and cast(json_extract(parent.payload_json, '$.artifact_version') as integer) = cast(json_extract(new.payload_json, '$.artifact_version') as integer)
          and json_extract(parent.payload_json, '$.content_digest') = json_extract(new.payload_json, '$.artifact_content_digest')
          and json_extract(parent.payload_json, '$.canonical_presentation_digest') = json_extract(new.payload_json, '$.canonical_presentation_digest')
          and parent.case_id = new.case_id
          and parent.tenant_id = new.tenant_id
          and parent.project_id = new.project_id
    )
    begin select raise(abort, 'artifact_provenance_parent_missing'); end;

    """
    event_parent_triggers = """
    create trigger if not exists canonical_events_actor_parent before insert on canonical_events
    when not exists (
        select 1 from canonical_actor_snapshots actor where actor.logical_id = new.actor_snapshot_ref
    )
    begin select raise(abort, 'event_actor_parent_missing'); end;

    create trigger if not exists canonical_events_work_unit_parent before insert on canonical_events
    when new.work_unit_id is not null and not exists (
        select 1 from canonical_work_units work_unit where work_unit.logical_id = new.work_unit_id
    )
    begin select raise(abort, 'event_work_unit_parent_missing'); end;

    create trigger if not exists canonical_events_attempt_parent before insert on canonical_events
    when new.attempt_id is not null and not exists (
        select 1 from canonical_attempts attempt where attempt.logical_id = new.attempt_id
    )
    begin select raise(abort, 'event_attempt_parent_missing'); end;
    """
    return f"""
    {object_tables}
    {case_scope_triggers}
    {relation_triggers}
    create table if not exists canonical_events (
        row_id integer primary key,
        event_id text not null unique,
        event_type text not null,
        task_run_id text,
        work_unit_id text,
        attempt_id text,
        sequence_no integer not null check(sequence_no >= 1),
        actor_snapshot_ref text not null,
        correlation_id text not null,
        payload_digest text not null,
        payload_json text not null check(json_valid(payload_json)),
        recorded_at text not null,
        unique(task_run_id, sequence_no)
    );
    create trigger if not exists canonical_events_no_update before update on canonical_events
    begin select raise(abort, 'append_only_table'); end;
    create trigger if not exists canonical_events_no_delete before delete on canonical_events
    begin select raise(abort, 'append_only_table'); end;
    {event_parent_triggers}
    create table if not exists canonical_outbox (
        outbox_id integer primary key,
        event_id text not null unique references canonical_events(event_id),
        delivery_status text not null,
        attempt_count integer not null default 0,
        created_at text not null
    );
    create table if not exists canonical_idempotency (
        scope_key text primary key,
        payload_digest text not null,
        result_json text not null check(json_valid(result_json)),
        created_at text not null
    );
    create table if not exists canonical_schema_migrations (
        migration_id text primary key,
        migration_hash text not null,
        applied_at text not null
    );
    create table if not exists canonical_metadata (
        metadata_key text primary key,
        metadata_value text not null
    );
    """
