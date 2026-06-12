from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


D_SERIES_GOVERNANCE_STORE_SCHEMA_VERSION = "sec_agent_d_series_governance_store_v0.1"
D12_1_MATERIALIZED_LAYER_KEYS = ("claim_evidence_ledger", "typed_gap_ledger", "gate_registry_eval_matrix")
D12_1_LAYER_DATABASE_PLANS = {
    "claim_evidence_ledger": {
        "schema_objects": [
            "claim_evidence_claims",
            "claim_evidence_support_refs",
            "claim_evidence_gap_refs",
            "claim_evidence_gate_refs",
        ],
        "migration_id": "d001_claim_evidence_ledger_append_only",
        "backfill_job": "backfill_claim_evidence_ledger_from_run_artifacts",
        "parity_test": "test_claim_evidence_ledger_artifact_database_parity",
    },
    "typed_gap_ledger": {
        "schema_objects": [
            "typed_gap_events",
            "typed_gap_source_attempts",
            "typed_gap_commercial_requirements",
        ],
        "migration_id": "d002_typed_gap_ledger_append_only",
        "backfill_job": "backfill_typed_gap_ledger_from_run_artifacts",
        "parity_test": "test_typed_gap_ledger_artifact_database_parity",
    },
    "gate_registry_eval_matrix": {
        "schema_objects": ["gate_registry", "gate_history", "gate_eval_matrix"],
        "migration_id": "d009_gate_registry_history_store",
        "backfill_job": "backfill_gate_history_from_run_artifacts",
        "parity_test": "test_gate_registry_artifact_database_parity",
    },
}


def migrate_d_series_governance_store(db_path: str | Path) -> dict[str, Any]:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        _create_schema(conn)
        _set_metadata(conn, "schema_version", D_SERIES_GOVERNANCE_STORE_SCHEMA_VERSION)
        _set_metadata(conn, "schema_migration_id", "d12_1_claim_gap_gate_history_sqlite_store")
    return {
        "schema_version": D_SERIES_GOVERNANCE_STORE_SCHEMA_VERSION,
        "db_path": str(path.resolve()),
        "schema_migration_status": "applied",
        "migration_id": "d12_1_claim_gap_gate_history_sqlite_store",
        "schema_objects": [
            "claim_evidence_claims",
            "claim_evidence_support_refs",
            "claim_evidence_gap_refs",
            "claim_evidence_gate_refs",
            "typed_gap_events",
            "typed_gap_source_attempts",
            "typed_gap_commercial_requirements",
            "gate_registry",
            "gate_history",
            "gate_eval_matrix",
        ],
    }


def backfill_d1_d2_d9_governance_artifacts(db_path: str | Path, artifacts: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(db_path)
    migrate = migrate_d_series_governance_store(path)
    claim_ledger = artifacts.get("claim_evidence_ledger") if isinstance(artifacts.get("claim_evidence_ledger"), Mapping) else {}
    gap_ledger = artifacts.get("typed_gap_ledger") if isinstance(artifacts.get("typed_gap_ledger"), Mapping) else {}
    gate_matrix = artifacts.get("gate_registry_eval_matrix") if isinstance(artifacts.get("gate_registry_eval_matrix"), Mapping) else {}
    run_id = _first_text(claim_ledger, "run_id") or _first_text(gate_matrix, "run_id") or str(artifacts.get("run_id") or "")
    with _connect(path) as conn:
        _backfill_claim_evidence_ledger(conn, claim_ledger, run_id=run_id)
        _backfill_typed_gap_ledger(conn, gap_ledger, run_id=run_id)
        _backfill_gate_registry_eval_matrix(conn, gate_matrix, run_id=run_id)
        counts = _row_counts(conn)
    return {
        **migrate,
        "backfill_status": "complete",
        "backfill_job": "backfill_d1_d2_d9_governance_artifacts",
        "run_id": run_id,
        "row_counts": counts,
    }


def parity_check_d1_d2_d9_governance_artifacts(db_path: str | Path, artifacts: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(db_path)
    claim_ledger = artifacts.get("claim_evidence_ledger") if isinstance(artifacts.get("claim_evidence_ledger"), Mapping) else {}
    gap_ledger = artifacts.get("typed_gap_ledger") if isinstance(artifacts.get("typed_gap_ledger"), Mapping) else {}
    gate_matrix = artifacts.get("gate_registry_eval_matrix") if isinstance(artifacts.get("gate_registry_eval_matrix"), Mapping) else {}
    run_id = _first_text(claim_ledger, "run_id") or _first_text(gate_matrix, "run_id") or str(artifacts.get("run_id") or "")
    expected = _expected_parity_counts(claim_ledger=claim_ledger, gap_ledger=gap_ledger, gate_matrix=gate_matrix)
    with _connect(path) as conn:
        observed = {table: _count_where_run(conn, table, run_id) for table in expected}
    mismatches = [
        {"table": table, "expected": expected_count, "observed": observed.get(table, 0)}
        for table, expected_count in expected.items()
        if observed.get(table, 0) != expected_count
    ]
    return {
        "schema_version": "sec_agent_d_series_governance_store_parity_v0.1",
        "db_path": str(path.resolve()),
        "run_id": run_id,
        "parity_status": "pass" if not mismatches else "fail",
        "expected_counts": expected,
        "observed_counts": observed,
        "mismatches": mismatches,
    }


def materialize_d1_d2_d9_governance_store(db_path: str | Path, artifacts: Mapping[str, Any]) -> dict[str, Any]:
    backfill = backfill_d1_d2_d9_governance_artifacts(db_path, artifacts)
    parity = parity_check_d1_d2_d9_governance_artifacts(db_path, artifacts)
    base = {
        "schema_migration_status": backfill.get("schema_migration_status"),
        "backfill_status": backfill.get("backfill_status"),
        "parity_status": parity.get("parity_status"),
        "reader_default_status": "database_default" if parity.get("parity_status") == "pass" else "artifact_default",
        "db_path": backfill.get("db_path"),
        "row_counts": backfill.get("row_counts") or {},
        "parity": parity,
    }
    layers = {
        layer_key: {
            **dict(base),
            **dict(D12_1_LAYER_DATABASE_PLANS.get(layer_key, {})),
            "store_migration_id": backfill.get("migration_id"),
        }
        for layer_key in D12_1_MATERIALIZED_LAYER_KEYS
    }
    return {
        "schema_version": "sec_agent_d_series_database_materialization_v0.1",
        "db_path": backfill.get("db_path"),
        "run_id": backfill.get("run_id") or parity.get("run_id") or "",
        "layers": layers,
    }


def d_series_materialization_state_from_report(report: Mapping[str, Any]) -> dict[str, Any]:
    layers = report.get("layers") if isinstance(report.get("layers"), Mapping) else {}
    return {
        layer_key: dict(layer)
        for layer_key, layer in layers.items()
        if layer_key in D12_1_MATERIALIZED_LAYER_KEYS and isinstance(layer, Mapping)
    }


def read_d1_d2_d9_governance_counts(db_path: str | Path, *, run_id: str = "") -> dict[str, int]:
    with _connect(Path(db_path)) as conn:
        if run_id:
            return {
                "claim_evidence_claims": _count_where_run(conn, "claim_evidence_claims", run_id),
                "typed_gap_events": _count_where_run(conn, "typed_gap_events", run_id),
                "gate_registry": _count_where_run(conn, "gate_registry", run_id),
                "gate_history": _count_where_run(conn, "gate_history", run_id),
                "gate_eval_matrix": _count_where_run(conn, "gate_eval_matrix", run_id),
            }
        return _row_counts(conn)


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists d_series_store_metadata (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists claim_evidence_claims (
            run_id text not null,
            claim_id text not null,
            claim_status text not null,
            claim_type text not null,
            ticker text not null,
            agent_id text not null,
            memo_slot text not null,
            claim_text text not null,
            source_strength text not null,
            confidence text not null,
            as_of_date text not null,
            metric_scope_json text not null,
            materiality text not null,
            direction text not null,
            limitations_json text not null,
            claim_boundary text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, claim_id)
        );
        create table if not exists claim_evidence_support_refs (
            run_id text not null,
            claim_id text not null,
            ref_type text not null,
            ref_id text not null,
            ordinal integer not null,
            primary key (run_id, claim_id, ref_type, ref_id, ordinal)
        );
        create table if not exists claim_evidence_gap_refs (
            run_id text not null,
            claim_id text not null,
            gap_id text not null,
            ordinal integer not null,
            primary key (run_id, claim_id, gap_id, ordinal)
        );
        create table if not exists claim_evidence_gate_refs (
            run_id text not null,
            claim_id text not null,
            gate_result_id text not null,
            ordinal integer not null,
            primary key (run_id, claim_id, gate_result_id, ordinal)
        );
        create table if not exists typed_gap_events (
            run_id text not null,
            gap_id text not null,
            raw_gap_type text not null,
            gap_type text not null,
            status text not null,
            ticker text not null,
            metric text not null,
            product_or_segment text not null,
            source_family text not null,
            repairability text not null,
            treatment_action text not null,
            reason text not null,
            as_of_date text not null,
            claim_boundary text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, gap_id, gap_type, ticker, metric)
        );
        create table if not exists typed_gap_source_attempts (
            run_id text not null,
            gap_id text not null,
            source_attempt text not null,
            ordinal integer not null,
            primary key (run_id, gap_id, source_attempt, ordinal)
        );
        create table if not exists typed_gap_commercial_requirements (
            run_id text not null,
            gap_id text not null,
            commercial_source text not null,
            ordinal integer not null,
            primary key (run_id, gap_id, commercial_source, ordinal)
        );
        create table if not exists gate_registry (
            run_id text not null,
            gate_id text not null,
            category text not null,
            severity text not null,
            target_types_json text not null,
            blocks_claim_fact_layer integer not null,
            required_fields_json text not null,
            repair_action text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, gate_id)
        );
        create table if not exists gate_history (
            run_id text not null,
            gate_result_id text not null,
            gate_id text not null,
            gate_category text not null,
            target_type text not null,
            target_object_id text not null,
            status text not null,
            score real not null,
            reason text not null,
            repair_action text not null,
            source_artifact text not null,
            evidence_refs_json text not null,
            blocks_claim_fact_layer integer not null,
            before_value_json text not null,
            after_value_json text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, gate_result_id)
        );
        create table if not exists gate_eval_matrix (
            run_id text not null,
            gate_id text not null,
            category text not null,
            severity text not null,
            matrix_status text not null,
            result_count integer not null,
            pass_count integer not null,
            warn_count integer not null,
            fail_count integer not null,
            not_applicable_count integer not null,
            blocking_fail_count integer not null,
            sample_target_object_ids_json text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, gate_id)
        );
        create index if not exists idx_claim_evidence_claims_ticker on claim_evidence_claims(ticker);
        create index if not exists idx_typed_gap_events_ticker_metric on typed_gap_events(ticker, metric);
        create index if not exists idx_gate_history_gate_status on gate_history(gate_id, status);
        """
    )


def _expected_parity_counts(
    *,
    claim_ledger: Mapping[str, Any],
    gap_ledger: Mapping[str, Any],
    gate_matrix: Mapping[str, Any],
) -> dict[str, int]:
    claims = _mapping_rows(claim_ledger.get("claims"))
    gaps = _mapping_rows(gap_ledger.get("gaps"))
    return {
        "claim_evidence_claims": len(claims),
        "claim_evidence_support_refs": sum(
            len(_string_list(claim.get("supporting_evidence_ids")))
            + len(_string_list(claim.get("contradicting_evidence_ids")))
            for claim in claims
        ),
        "claim_evidence_gap_refs": sum(len(_string_list(claim.get("gap_ids"))) for claim in claims),
        "claim_evidence_gate_refs": sum(len(_string_list(claim.get("required_gate_results"))) for claim in claims),
        "typed_gap_events": len(gaps),
        "typed_gap_source_attempts": sum(len(_string_list(gap.get("source_attempts"))) for gap in gaps),
        "typed_gap_commercial_requirements": sum(
            len(_string_list(gap.get("commercial_sources_needed"))) for gap in gaps
        ),
        "gate_registry": len(_mapping_rows(gate_matrix.get("gate_registry"))),
        "gate_history": len(_mapping_rows(gate_matrix.get("gate_history"))),
        "gate_eval_matrix": len(_mapping_rows(gate_matrix.get("eval_matrix"))),
    }


def _backfill_claim_evidence_ledger(conn: sqlite3.Connection, ledger: Mapping[str, Any], *, run_id: str) -> None:
    timestamp = _utc_now()
    rows = _mapping_rows(ledger.get("claims"))
    for claim in rows:
        claim_id = _first_text(claim, "claim_id")
        conn.execute(
            """
            insert into claim_evidence_claims (
                run_id, claim_id, claim_status, claim_type, ticker, agent_id, memo_slot,
                claim_text, source_strength, confidence, as_of_date, metric_scope_json,
                materiality, direction, limitations_json, claim_boundary, payload_json, inserted_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(run_id, claim_id) do update set
                claim_status = excluded.claim_status,
                claim_type = excluded.claim_type,
                ticker = excluded.ticker,
                agent_id = excluded.agent_id,
                memo_slot = excluded.memo_slot,
                claim_text = excluded.claim_text,
                source_strength = excluded.source_strength,
                confidence = excluded.confidence,
                as_of_date = excluded.as_of_date,
                metric_scope_json = excluded.metric_scope_json,
                materiality = excluded.materiality,
                direction = excluded.direction,
                limitations_json = excluded.limitations_json,
                claim_boundary = excluded.claim_boundary,
                payload_json = excluded.payload_json,
                inserted_at = excluded.inserted_at
            """,
            (
                run_id,
                claim_id,
                _first_text(claim, "claim_status"),
                _first_text(claim, "claim_type"),
                _first_text(claim, "ticker"),
                _first_text(claim, "agent_id"),
                _first_text(claim, "memo_slot"),
                _first_text(claim, "claim_text"),
                _first_text(claim, "source_strength"),
                _first_text(claim, "confidence"),
                _first_text(claim, "as_of_date"),
                _json_text(claim.get("metric_scope") or []),
                _first_text(claim, "materiality"),
                _first_text(claim, "direction"),
                _json_text(claim.get("limitations") or []),
                _first_text(claim, "claim_boundary"),
                _json_text(claim),
                timestamp,
            ),
        )
        _replace_claim_refs(conn, run_id=run_id, claim_id=claim_id, claim=claim)


def _replace_claim_refs(conn: sqlite3.Connection, *, run_id: str, claim_id: str, claim: Mapping[str, Any]) -> None:
    conn.execute("delete from claim_evidence_support_refs where run_id = ? and claim_id = ?", (run_id, claim_id))
    conn.execute("delete from claim_evidence_gap_refs where run_id = ? and claim_id = ?", (run_id, claim_id))
    conn.execute("delete from claim_evidence_gate_refs where run_id = ? and claim_id = ?", (run_id, claim_id))
    for ref_type, refs in (
        ("supporting", _string_list(claim.get("supporting_evidence_ids"))),
        ("contradicting", _string_list(claim.get("contradicting_evidence_ids"))),
    ):
        for ordinal, ref_id in enumerate(refs):
            conn.execute(
                """
                insert or replace into claim_evidence_support_refs (run_id, claim_id, ref_type, ref_id, ordinal)
                values (?, ?, ?, ?, ?)
                """,
                (run_id, claim_id, ref_type, ref_id, ordinal),
            )
    for ordinal, gap_id in enumerate(_string_list(claim.get("gap_ids"))):
        conn.execute(
            "insert or replace into claim_evidence_gap_refs (run_id, claim_id, gap_id, ordinal) values (?, ?, ?, ?)",
            (run_id, claim_id, gap_id, ordinal),
        )
    for ordinal, gate_result_id in enumerate(_string_list(claim.get("required_gate_results"))):
        conn.execute(
            """
            insert or replace into claim_evidence_gate_refs (run_id, claim_id, gate_result_id, ordinal)
            values (?, ?, ?, ?)
            """,
            (run_id, claim_id, gate_result_id, ordinal),
        )


def _backfill_typed_gap_ledger(conn: sqlite3.Connection, ledger: Mapping[str, Any], *, run_id: str) -> None:
    timestamp = _utc_now()
    for gap in _mapping_rows(ledger.get("gaps")):
        gap_id = _first_text(gap, "gap_id")
        conn.execute(
            """
            insert into typed_gap_events (
                run_id, gap_id, raw_gap_type, gap_type, status, ticker, metric,
                product_or_segment, source_family, repairability, treatment_action,
                reason, as_of_date, claim_boundary, payload_json, inserted_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(run_id, gap_id, gap_type, ticker, metric) do update set
                raw_gap_type = excluded.raw_gap_type,
                status = excluded.status,
                product_or_segment = excluded.product_or_segment,
                source_family = excluded.source_family,
                repairability = excluded.repairability,
                treatment_action = excluded.treatment_action,
                reason = excluded.reason,
                as_of_date = excluded.as_of_date,
                claim_boundary = excluded.claim_boundary,
                payload_json = excluded.payload_json,
                inserted_at = excluded.inserted_at
            """,
            (
                run_id,
                gap_id,
                _first_text(gap, "raw_gap_type"),
                _first_text(gap, "gap_type"),
                _first_text(gap, "status"),
                _first_text(gap, "ticker"),
                _first_text(gap, "metric"),
                _first_text(gap, "product_or_segment"),
                _first_text(gap, "source_family"),
                _first_text(gap, "repairability"),
                _first_text(gap, "treatment_action"),
                _first_text(gap, "reason"),
                _first_text(gap, "as_of_date"),
                _first_text(gap, "claim_boundary"),
                _json_text(gap),
                timestamp,
            ),
        )
        conn.execute("delete from typed_gap_source_attempts where run_id = ? and gap_id = ?", (run_id, gap_id))
        conn.execute("delete from typed_gap_commercial_requirements where run_id = ? and gap_id = ?", (run_id, gap_id))
        for ordinal, attempt in enumerate(_string_list(gap.get("source_attempts"))):
            conn.execute(
                """
                insert or replace into typed_gap_source_attempts (run_id, gap_id, source_attempt, ordinal)
                values (?, ?, ?, ?)
                """,
                (run_id, gap_id, attempt, ordinal),
            )
        for ordinal, source in enumerate(_string_list(gap.get("commercial_sources_needed"))):
            conn.execute(
                """
                insert or replace into typed_gap_commercial_requirements (run_id, gap_id, commercial_source, ordinal)
                values (?, ?, ?, ?)
                """,
                (run_id, gap_id, source, ordinal),
            )


def _backfill_gate_registry_eval_matrix(conn: sqlite3.Connection, gate_matrix: Mapping[str, Any], *, run_id: str) -> None:
    timestamp = _utc_now()
    for gate in _mapping_rows(gate_matrix.get("gate_registry")):
        conn.execute(
            """
            insert into gate_registry (
                run_id, gate_id, category, severity, target_types_json,
                blocks_claim_fact_layer, required_fields_json, repair_action,
                payload_json, inserted_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(run_id, gate_id) do update set
                category = excluded.category,
                severity = excluded.severity,
                target_types_json = excluded.target_types_json,
                blocks_claim_fact_layer = excluded.blocks_claim_fact_layer,
                required_fields_json = excluded.required_fields_json,
                repair_action = excluded.repair_action,
                payload_json = excluded.payload_json,
                inserted_at = excluded.inserted_at
            """,
            (
                run_id,
                _first_text(gate, "gate_id"),
                _first_text(gate, "category"),
                _first_text(gate, "severity"),
                _json_text(gate.get("target_types") or []),
                1 if gate.get("blocks_claim_fact_layer") else 0,
                _json_text(gate.get("required_fields") or []),
                _first_text(gate, "repair_action"),
                _json_text(gate),
                timestamp,
            ),
        )
    for result in _mapping_rows(gate_matrix.get("gate_history")):
        conn.execute(
            """
            insert into gate_history (
                run_id, gate_result_id, gate_id, gate_category, target_type,
                target_object_id, status, score, reason, repair_action,
                source_artifact, evidence_refs_json, blocks_claim_fact_layer,
                before_value_json, after_value_json, payload_json, inserted_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(run_id, gate_result_id) do update set
                gate_id = excluded.gate_id,
                gate_category = excluded.gate_category,
                target_type = excluded.target_type,
                target_object_id = excluded.target_object_id,
                status = excluded.status,
                score = excluded.score,
                reason = excluded.reason,
                repair_action = excluded.repair_action,
                source_artifact = excluded.source_artifact,
                evidence_refs_json = excluded.evidence_refs_json,
                blocks_claim_fact_layer = excluded.blocks_claim_fact_layer,
                before_value_json = excluded.before_value_json,
                after_value_json = excluded.after_value_json,
                payload_json = excluded.payload_json,
                inserted_at = excluded.inserted_at
            """,
            (
                run_id,
                _first_text(result, "gate_result_id"),
                _first_text(result, "gate_id"),
                _first_text(result, "gate_category"),
                _first_text(result, "target_type"),
                _first_text(result, "target_object_id"),
                _first_text(result, "status"),
                _float_value(result.get("score")),
                _first_text(result, "reason"),
                _first_text(result, "repair_action"),
                _first_text(result, "source_artifact"),
                _json_text(result.get("evidence_refs") or []),
                1 if result.get("blocks_claim_fact_layer") else 0,
                _json_text(result.get("before_value")),
                _json_text(result.get("after_value")),
                _json_text(result),
                timestamp,
            ),
        )
    for row in _mapping_rows(gate_matrix.get("eval_matrix")):
        conn.execute(
            """
            insert into gate_eval_matrix (
                run_id, gate_id, category, severity, matrix_status, result_count,
                pass_count, warn_count, fail_count, not_applicable_count,
                blocking_fail_count, sample_target_object_ids_json, payload_json, inserted_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(run_id, gate_id) do update set
                category = excluded.category,
                severity = excluded.severity,
                matrix_status = excluded.matrix_status,
                result_count = excluded.result_count,
                pass_count = excluded.pass_count,
                warn_count = excluded.warn_count,
                fail_count = excluded.fail_count,
                not_applicable_count = excluded.not_applicable_count,
                blocking_fail_count = excluded.blocking_fail_count,
                sample_target_object_ids_json = excluded.sample_target_object_ids_json,
                payload_json = excluded.payload_json,
                inserted_at = excluded.inserted_at
            """,
            (
                run_id,
                _first_text(row, "gate_id"),
                _first_text(row, "category"),
                _first_text(row, "severity"),
                _first_text(row, "matrix_status"),
                _int_value(row.get("result_count")),
                _int_value(row.get("pass_count")),
                _int_value(row.get("warn_count")),
                _int_value(row.get("fail_count")),
                _int_value(row.get("not_applicable_count")),
                _int_value(row.get("blocking_fail_count")),
                _json_text(row.get("sample_target_object_ids") or []),
                _json_text(row),
                timestamp,
            ),
        )


def _set_metadata(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        """
        insert into d_series_store_metadata (key, value_json, updated_at)
        values (?, ?, ?)
        on conflict(key) do update set value_json = excluded.value_json, updated_at = excluded.updated_at
        """,
        (key, _json_text(value), _utc_now()),
    )


def _row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = [
        "claim_evidence_claims",
        "claim_evidence_support_refs",
        "claim_evidence_gap_refs",
        "claim_evidence_gate_refs",
        "typed_gap_events",
        "typed_gap_source_attempts",
        "typed_gap_commercial_requirements",
        "gate_registry",
        "gate_history",
        "gate_eval_matrix",
    ]
    return {table: int(conn.execute(f"select count(*) as count from {table}").fetchone()["count"]) for table in tables}


def _count_where_run(conn: sqlite3.Connection, table: str, run_id: str) -> int:
    row = conn.execute(f"select count(*) as count from {table} where run_id = ?", (run_id,)).fetchone()
    return int(row["count"] if row else 0)


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    conn.execute("pragma journal_mode = wal")
    return conn


def _mapping_rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, Mapping):
        return [str(value).strip()] if str(value).strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    return [str(value).strip()] if str(value).strip() else []


def _first_text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            value = next((item for item in value if str(item or "").strip()), "")
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
