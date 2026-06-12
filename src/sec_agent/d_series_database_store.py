from __future__ import annotations

import json
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


D_SERIES_GOVERNANCE_STORE_SCHEMA_VERSION = "sec_agent_d_series_governance_store_v0.2"
D12_1_MATERIALIZED_LAYER_KEYS = ("claim_evidence_ledger", "typed_gap_ledger", "gate_registry_eval_matrix")
D_SERIES_MATERIALIZED_LAYER_KEYS = (
    "claim_evidence_ledger",
    "typed_gap_ledger",
    "entity_security_master",
    "raw_source_provenance_store",
    "asof_vintage_layer",
    "reconciliation_ledger",
    "metric_product_ontology_snapshot",
    "source_capability_router",
    "gate_registry_eval_matrix",
    "derived_metric_layer",
    "analyst_view_research_memory",
)
D_SERIES_LAYER_DATABASE_PLANS = {
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
    "entity_security_master": {
        "schema_objects": ["entity_master", "security_identifier_map", "entity_alias_history", "unresolved_entity_references"],
        "migration_id": "d003_entity_security_master_resolver",
        "backfill_job": "backfill_entity_security_master_from_inventory",
        "parity_test": "test_entity_security_master_artifact_database_parity",
    },
    "raw_source_provenance_store": {
        "schema_objects": ["raw_source_documents", "raw_source_checksums", "raw_source_parser_runs", "source_license_robots_policy"],
        "migration_id": "d004_raw_source_provenance_store",
        "backfill_job": "backfill_raw_source_provenance_from_run_artifacts",
        "parity_test": "test_raw_source_provenance_artifact_database_parity",
    },
    "asof_vintage_layer": {
        "schema_objects": ["asof_vintage_records", "macro_vintage_observations", "market_snapshot_asof", "filing_amendment_lineage"],
        "migration_id": "d005_asof_vintage_temporal_store",
        "backfill_job": "backfill_asof_vintage_from_run_artifacts",
        "parity_test": "test_asof_vintage_artifact_database_parity",
    },
    "reconciliation_ledger": {
        "schema_objects": ["reconciliation_candidates", "reconciliation_groups", "reconciliation_conflict_gaps"],
        "migration_id": "d006_reconciliation_ledger_store",
        "backfill_job": "backfill_reconciliation_ledger_from_run_artifacts",
        "parity_test": "test_reconciliation_ledger_artifact_database_parity",
    },
    "metric_product_ontology_snapshot": {
        "schema_objects": ["metric_product_ontology_metrics", "metric_product_alias_registry", "metric_product_manual_review_queue"],
        "migration_id": "d007_metric_product_ontology_registry",
        "backfill_job": "backfill_metric_product_ontology_from_snapshots",
        "parity_test": "test_metric_product_ontology_artifact_database_parity",
    },
    "source_capability_router": {
        "schema_objects": ["source_capability_policy", "source_route_decisions", "commercial_gap_policy"],
        "migration_id": "d008_source_capability_router_policy_store",
        "backfill_job": "backfill_source_capability_router_from_run_artifacts",
        "parity_test": "test_source_capability_router_artifact_database_parity",
    },
    "gate_registry_eval_matrix": {
        "schema_objects": ["gate_registry", "gate_history", "gate_eval_matrix"],
        "migration_id": "d009_gate_registry_history_store",
        "backfill_job": "backfill_gate_history_from_run_artifacts",
        "parity_test": "test_gate_registry_artifact_database_parity",
    },
    "derived_metric_layer": {
        "schema_objects": ["derived_metric_formula_registry", "derived_metric_outputs", "derived_metric_input_lineage"],
        "migration_id": "d010_derived_metric_formula_store",
        "backfill_job": "backfill_derived_metric_layer_from_run_artifacts",
        "parity_test": "test_derived_metric_artifact_database_parity",
    },
    "analyst_view_research_memory": {
        "schema_objects": ["analyst_research_memory_entries", "analyst_view_index", "thesis_tracker"],
        "migration_id": "d011_analyst_view_memory_store",
        "backfill_job": "backfill_analyst_view_memory_from_run_artifacts",
        "parity_test": "test_analyst_view_memory_artifact_database_parity",
    },
}


def migrate_d_series_governance_store(db_path: str | Path) -> dict[str, Any]:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        _create_schema(conn)
        _set_metadata(conn, "schema_version", D_SERIES_GOVERNANCE_STORE_SCHEMA_VERSION)
        _set_metadata(conn, "schema_migration_id", "d12_1b_all_d_series_governance_sqlite_store")
    return {
        "schema_version": D_SERIES_GOVERNANCE_STORE_SCHEMA_VERSION,
        "db_path": str(path.resolve()),
        "schema_migration_status": "applied",
        "migration_id": "d12_1b_all_d_series_governance_sqlite_store",
        "schema_objects": _all_schema_objects(),
    }


def backfill_d1_d2_d9_governance_artifacts(db_path: str | Path, artifacts: Mapping[str, Any]) -> dict[str, Any]:
    return _backfill_layers(db_path, artifacts, layer_keys=D12_1_MATERIALIZED_LAYER_KEYS)


def backfill_d_series_governance_artifacts(db_path: str | Path, artifacts: Mapping[str, Any]) -> dict[str, Any]:
    return _backfill_layers(db_path, artifacts, layer_keys=D_SERIES_MATERIALIZED_LAYER_KEYS)


def parity_check_d1_d2_d9_governance_artifacts(db_path: str | Path, artifacts: Mapping[str, Any]) -> dict[str, Any]:
    return _parity_check_layers(db_path, artifacts, layer_keys=D12_1_MATERIALIZED_LAYER_KEYS)


def parity_check_d_series_governance_artifacts(db_path: str | Path, artifacts: Mapping[str, Any]) -> dict[str, Any]:
    return _parity_check_layers(db_path, artifacts, layer_keys=D_SERIES_MATERIALIZED_LAYER_KEYS)


def materialize_d1_d2_d9_governance_store(db_path: str | Path, artifacts: Mapping[str, Any]) -> dict[str, Any]:
    return _materialize_layers(db_path, artifacts, layer_keys=D12_1_MATERIALIZED_LAYER_KEYS)


def materialize_d_series_governance_store(db_path: str | Path, artifacts: Mapping[str, Any]) -> dict[str, Any]:
    return _materialize_layers(db_path, artifacts, layer_keys=D_SERIES_MATERIALIZED_LAYER_KEYS)


def d_series_materialization_state_from_report(report: Mapping[str, Any]) -> dict[str, Any]:
    layers = report.get("layers") if isinstance(report.get("layers"), Mapping) else {}
    return {
        layer_key: dict(layer)
        for layer_key, layer in layers.items()
        if layer_key in D_SERIES_MATERIALIZED_LAYER_KEYS and isinstance(layer, Mapping)
    }


def read_d1_d2_d9_governance_counts(db_path: str | Path, *, run_id: str = "") -> dict[str, int]:
    tables = [table for layer_key in D12_1_MATERIALIZED_LAYER_KEYS for table in D_SERIES_LAYER_DATABASE_PLANS[layer_key]["schema_objects"]]
    return read_d_series_governance_counts(db_path, run_id=run_id, tables=tables)


def read_d_series_governance_counts(
    db_path: str | Path,
    *,
    run_id: str = "",
    tables: Sequence[str] | None = None,
) -> dict[str, int]:
    with _connect(Path(db_path)) as conn:
        table_names = list(tables or _all_schema_objects())
        if run_id:
            return {table: _count_where_run(conn, table, run_id) for table in table_names}
        return _row_counts(conn, tables=table_names)


def read_claim_gap_gate_research_context(
    db_path: str | Path,
    *,
    tickers: Sequence[str] | None = None,
    run_id: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    ticker_filter = [str(item).upper().strip() for item in tickers or [] if str(item or "").strip()]
    with _connect(Path(db_path)) as conn:
        claims = _select_payload_rows(
            conn,
            "claim_evidence_claims",
            run_id=run_id,
            ticker_filter=ticker_filter,
            order_by="inserted_at desc, claim_id",
            limit=limit,
        )
        gaps = _select_payload_rows(
            conn,
            "typed_gap_events",
            run_id=run_id,
            ticker_filter=ticker_filter,
            order_by="inserted_at desc, gap_id",
            limit=limit,
        )
        gate_history = _select_payload_rows(
            conn,
            "gate_history",
            run_id=run_id,
            ticker_filter=[],
            order_by="inserted_at desc, gate_result_id",
            limit=limit,
        )
    return {
        "schema_version": "sec_agent_d_series_claim_gap_gate_reader_v0.1",
        "db_path": str(Path(db_path).resolve()),
        "reader_default_status": "database_default",
        "run_id": run_id,
        "tickers": ticker_filter,
        "claims": claims,
        "typed_gaps": gaps,
        "gate_history": gate_history,
        "summary": {
            "claim_count": len(claims),
            "typed_gap_count": len(gaps),
            "gate_history_count": len(gate_history),
            "source": "d_series_governance_sqlite_store",
        },
    }


def _backfill_layers(db_path: str | Path, artifacts: Mapping[str, Any], *, layer_keys: Sequence[str]) -> dict[str, Any]:
    path = Path(db_path)
    migrate = migrate_d_series_governance_store(path)
    run_id = _run_id_from_artifacts(artifacts)
    with _connect(path) as conn:
        if "claim_evidence_ledger" in layer_keys:
            _backfill_claim_evidence_ledger(conn, _artifact(artifacts, "claim_evidence_ledger"), run_id=run_id)
        if "typed_gap_ledger" in layer_keys:
            _backfill_typed_gap_ledger(conn, _artifact(artifacts, "typed_gap_ledger"), run_id=run_id)
        if "entity_security_master" in layer_keys:
            _backfill_entity_security_master(conn, _artifact(artifacts, "entity_security_master"), run_id=run_id)
        if "raw_source_provenance_store" in layer_keys:
            _backfill_raw_source_provenance_store(conn, _artifact(artifacts, "raw_source_provenance_store"), run_id=run_id)
        if "asof_vintage_layer" in layer_keys:
            _backfill_asof_vintage_layer(conn, _artifact(artifacts, "asof_vintage_layer"), run_id=run_id)
        if "reconciliation_ledger" in layer_keys:
            _backfill_reconciliation_ledger(conn, _artifact(artifacts, "reconciliation_ledger"), run_id=run_id)
        if "metric_product_ontology_snapshot" in layer_keys:
            _backfill_metric_product_ontology_snapshot(conn, _artifact(artifacts, "metric_product_ontology_snapshot"), run_id=run_id)
        if "source_capability_router" in layer_keys:
            _backfill_source_capability_router(conn, _artifact(artifacts, "source_capability_router"), run_id=run_id)
        if "gate_registry_eval_matrix" in layer_keys:
            _backfill_gate_registry_eval_matrix(conn, _artifact(artifacts, "gate_registry_eval_matrix"), run_id=run_id)
        if "derived_metric_layer" in layer_keys:
            _backfill_derived_metric_layer(conn, _artifact(artifacts, "derived_metric_layer"), run_id=run_id)
        if "analyst_view_research_memory" in layer_keys:
            _backfill_analyst_view_research_memory(conn, _artifact(artifacts, "analyst_view_research_memory"), run_id=run_id)
        counts = _row_counts(conn)
    return {
        **migrate,
        "backfill_status": "complete",
        "backfill_job": "backfill_d_series_governance_artifacts",
        "run_id": run_id,
        "row_counts": counts,
    }


def _parity_check_layers(db_path: str | Path, artifacts: Mapping[str, Any], *, layer_keys: Sequence[str]) -> dict[str, Any]:
    path = Path(db_path)
    run_id = _run_id_from_artifacts(artifacts)
    expected = _expected_parity_counts(artifacts, layer_keys=layer_keys)
    with _connect(path) as conn:
        observed = {table: _count_where_run(conn, table, run_id) for table in expected}
    mismatches = [
        {"table": table, "expected": expected_count, "observed": observed.get(table, 0)}
        for table, expected_count in expected.items()
        if observed.get(table, 0) != expected_count
    ]
    return {
        "schema_version": "sec_agent_d_series_governance_store_parity_v0.2",
        "db_path": str(path.resolve()),
        "run_id": run_id,
        "parity_status": "pass" if not mismatches else "fail",
        "expected_counts": expected,
        "observed_counts": observed,
        "mismatches": mismatches,
    }


def _materialize_layers(db_path: str | Path, artifacts: Mapping[str, Any], *, layer_keys: Sequence[str]) -> dict[str, Any]:
    backfill = _backfill_layers(db_path, artifacts, layer_keys=layer_keys)
    parity = _parity_check_layers(db_path, artifacts, layer_keys=layer_keys)
    layers: dict[str, dict[str, Any]] = {}
    for layer_key in layer_keys:
        plan = D_SERIES_LAYER_DATABASE_PLANS[layer_key]
        layer_tables = list(plan["schema_objects"])
        layer_mismatches = [row for row in parity.get("mismatches") or [] if row.get("table") in layer_tables]
        layer_status = "pass" if not layer_mismatches else "fail"
        layer_counts = {
            table: (backfill.get("row_counts") or {}).get(table, 0)
            for table in layer_tables
        }
        layers[layer_key] = {
            **dict(plan),
            "schema_migration_status": backfill.get("schema_migration_status"),
            "backfill_status": backfill.get("backfill_status"),
            "parity_status": layer_status,
            "reader_default_status": "database_default" if layer_status == "pass" else "artifact_default",
            "db_path": backfill.get("db_path"),
            "store_migration_id": backfill.get("migration_id"),
            "row_counts": layer_counts,
            "parity": {
                **parity,
                "layer_mismatches": layer_mismatches,
                "layer_expected_counts": {
                    table: (parity.get("expected_counts") or {}).get(table, 0)
                    for table in layer_tables
                },
                "layer_observed_counts": {
                    table: (parity.get("observed_counts") or {}).get(table, 0)
                    for table in layer_tables
                },
            },
        }
    return {
        "schema_version": "sec_agent_d_series_database_materialization_v0.2",
        "db_path": backfill.get("db_path"),
        "run_id": backfill.get("run_id") or parity.get("run_id") or "",
        "layers": layers,
    }


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
        create table if not exists entity_master (
            run_id text not null,
            entity_id text not null,
            ticker text not null,
            cik text not null,
            canonical_name text not null,
            resolution_confidence text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, entity_id)
        );
        create table if not exists security_identifier_map (
            run_id text not null,
            entity_id text not null,
            identifier_type text not null,
            identifier_value text not null,
            primary key (run_id, entity_id, identifier_type, identifier_value)
        );
        create table if not exists entity_alias_history (
            run_id text not null,
            entity_id text not null,
            alias text not null,
            normalized_alias text not null,
            source_ref text not null,
            ordinal integer not null,
            primary key (run_id, entity_id, alias, ordinal)
        );
        create table if not exists unresolved_entity_references (
            run_id text not null,
            unresolved_reference_id text not null,
            raw_name text not null,
            status text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, unresolved_reference_id)
        );
        create table if not exists raw_source_documents (
            run_id text not null,
            source_id text not null,
            source_family text not null,
            record_type text not null,
            ticker text not null,
            evidence_ref text not null,
            raw_url text not null,
            local_path text not null,
            document_id text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, source_id)
        );
        create table if not exists raw_source_checksums (
            run_id text not null,
            source_id text not null,
            checksum text not null,
            file_type text not null,
            primary key (run_id, source_id)
        );
        create table if not exists raw_source_parser_runs (
            run_id text not null,
            source_id text not null,
            parser_run_id text not null,
            parser_version text not null,
            retrieved_at text not null,
            primary key (run_id, source_id)
        );
        create table if not exists source_license_robots_policy (
            run_id text not null,
            source_id text not null,
            license_policy text not null,
            robots_policy text not null,
            access_method text not null,
            primary key (run_id, source_id)
        );
        create table if not exists asof_vintage_records (
            run_id text not null,
            vintage_id text not null,
            source_id text not null,
            evidence_ref text not null,
            source_family text not null,
            ticker text not null,
            time_basis text not null,
            fiscal_period_end text not null,
            market_as_of_date text not null,
            macro_vintage_date text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, vintage_id)
        );
        create table if not exists macro_vintage_observations (
            run_id text not null,
            vintage_id text not null,
            observation_date text not null,
            macro_vintage_date text not null,
            payload_json text not null,
            primary key (run_id, vintage_id)
        );
        create table if not exists market_snapshot_asof (
            run_id text not null,
            vintage_id text not null,
            market_as_of_date text not null,
            payload_json text not null,
            primary key (run_id, vintage_id)
        );
        create table if not exists filing_amendment_lineage (
            run_id text not null,
            vintage_id text not null,
            document_id text not null,
            filing_date text not null,
            accepted_date text not null,
            payload_json text not null,
            primary key (run_id, vintage_id)
        );
        create table if not exists reconciliation_candidates (
            run_id text not null,
            candidate_id text not null,
            candidate_status text not null,
            ticker text not null,
            canonical_metric_id text not null,
            period_key text not null,
            value text not null,
            unit text not null,
            source_family text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, candidate_id)
        );
        create table if not exists reconciliation_groups (
            run_id text not null,
            group_id text not null,
            ticker text not null,
            canonical_metric_id text not null,
            resolution_status text not null,
            preferred_value_json text not null,
            candidate_ids_json text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, group_id)
        );
        create table if not exists reconciliation_conflict_gaps (
            run_id text not null,
            gap_id text not null,
            ticker text not null,
            metric text not null,
            conflict_types_json text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, gap_id)
        );
        create table if not exists metric_product_ontology_metrics (
            run_id text not null,
            canonical_metric_id text not null,
            metric_type text not null,
            display_name text not null,
            unit_family text not null,
            period_rule text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, canonical_metric_id)
        );
        create table if not exists metric_product_alias_registry (
            run_id text not null,
            alias text not null,
            canonical_metric_id text not null,
            metric_type text not null,
            alias_status text not null,
            primary key (run_id, alias, canonical_metric_id, alias_status)
        );
        create table if not exists metric_product_manual_review_queue (
            run_id text not null,
            review_id text not null,
            raw_metric_text text not null,
            match_status text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, review_id)
        );
        create table if not exists source_capability_policy (
            run_id text not null,
            source_family text not null,
            available integer not null,
            allowed_by_activation integer not null,
            claim_authority text not null,
            context_only integer not null,
            gap_policy text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, source_family)
        );
        create table if not exists source_route_decisions (
            run_id text not null,
            route_id text not null,
            retrieval_route text not null,
            source_family text not null,
            decision_status text not null,
            reason text not null,
            gap_type text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, route_id)
        );
        create table if not exists commercial_gap_policy (
            run_id text not null,
            source_family text not null,
            gap_policy text not null,
            claim_authority text not null,
            primary key (run_id, source_family)
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
        create table if not exists derived_metric_formula_registry (
            run_id text not null,
            formula_id text not null,
            formula text not null,
            calculation_version text not null,
            derived_metric_family text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, formula_id)
        );
        create table if not exists derived_metric_outputs (
            run_id text not null,
            derived_metric_id text not null,
            ticker text not null,
            derived_metric_family text not null,
            value text not null,
            unit text not null,
            gate_status text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, derived_metric_id)
        );
        create table if not exists derived_metric_input_lineage (
            run_id text not null,
            derived_metric_id text not null,
            input_fact_id text not null,
            ordinal integer not null,
            primary key (run_id, derived_metric_id, input_fact_id, ordinal)
        );
        create table if not exists analyst_research_memory_entries (
            run_id text not null,
            memory_entry_id text not null,
            view_id text not null,
            view_type text not null,
            ticker text not null,
            retrieval_policy text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, memory_entry_id)
        );
        create table if not exists analyst_view_index (
            run_id text not null,
            view_id text not null,
            view_type text not null,
            ticker text not null,
            product_or_segment text not null,
            view_status text not null,
            source_layers_json text not null,
            drilldown_refs_json text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, view_id)
        );
        create table if not exists thesis_tracker (
            run_id text not null,
            view_id text not null,
            ticker text not null,
            claim_ids_json text not null,
            gap_ids_json text not null,
            derived_metric_ids_json text not null,
            payload_json text not null,
            inserted_at text not null,
            primary key (run_id, view_id)
        );
        create index if not exists idx_claim_evidence_claims_ticker on claim_evidence_claims(ticker);
        create index if not exists idx_typed_gap_events_ticker_metric on typed_gap_events(ticker, metric);
        create index if not exists idx_gate_history_gate_status on gate_history(gate_id, status);
        create index if not exists idx_entity_master_ticker on entity_master(ticker);
        create index if not exists idx_reconciliation_groups_ticker_metric on reconciliation_groups(ticker, canonical_metric_id);
        create index if not exists idx_analyst_view_index_ticker_type on analyst_view_index(ticker, view_type);
        """
    )


def _backfill_claim_evidence_ledger(conn: sqlite3.Connection, ledger: Mapping[str, Any], *, run_id: str) -> None:
    _delete_run_tables(conn, run_id, D_SERIES_LAYER_DATABASE_PLANS["claim_evidence_ledger"]["schema_objects"])
    timestamp = _utc_now()
    for claim in _mapping_rows(ledger.get("claims")):
        claim_id = _first_text(claim, "claim_id")
        conn.execute(
            """
            insert or replace into claim_evidence_claims (
                run_id, claim_id, claim_status, claim_type, ticker, agent_id, memo_slot,
                claim_text, source_strength, confidence, as_of_date, metric_scope_json,
                materiality, direction, limitations_json, claim_boundary, payload_json, inserted_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                claim_id,
                _first_text(claim, "claim_status"),
                _first_text(claim, "claim_type"),
                _first_text(claim, "ticker").upper(),
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
        for ref_type, refs in (
            ("supporting", _string_list(claim.get("supporting_evidence_ids"))),
            ("contradicting", _string_list(claim.get("contradicting_evidence_ids"))),
        ):
            for ordinal, ref_id in enumerate(refs):
                conn.execute(
                    "insert or replace into claim_evidence_support_refs (run_id, claim_id, ref_type, ref_id, ordinal) values (?, ?, ?, ?, ?)",
                    (run_id, claim_id, ref_type, ref_id, ordinal),
                )
        for ordinal, gap_id in enumerate(_string_list(claim.get("gap_ids"))):
            conn.execute(
                "insert or replace into claim_evidence_gap_refs (run_id, claim_id, gap_id, ordinal) values (?, ?, ?, ?)",
                (run_id, claim_id, gap_id, ordinal),
            )
        for ordinal, gate_result_id in enumerate(_string_list(claim.get("required_gate_results"))):
            conn.execute(
                "insert or replace into claim_evidence_gate_refs (run_id, claim_id, gate_result_id, ordinal) values (?, ?, ?, ?)",
                (run_id, claim_id, gate_result_id, ordinal),
            )


def _backfill_typed_gap_ledger(conn: sqlite3.Connection, ledger: Mapping[str, Any], *, run_id: str) -> None:
    _delete_run_tables(conn, run_id, D_SERIES_LAYER_DATABASE_PLANS["typed_gap_ledger"]["schema_objects"])
    timestamp = _utc_now()
    for gap in _mapping_rows(ledger.get("gaps")):
        gap_id = _first_text(gap, "gap_id")
        conn.execute(
            """
            insert or replace into typed_gap_events (
                run_id, gap_id, raw_gap_type, gap_type, status, ticker, metric,
                product_or_segment, source_family, repairability, treatment_action,
                reason, as_of_date, claim_boundary, payload_json, inserted_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                gap_id,
                _first_text(gap, "raw_gap_type"),
                _first_text(gap, "gap_type"),
                _first_text(gap, "status"),
                _first_text(gap, "ticker").upper(),
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
        for ordinal, attempt in enumerate(_string_list(gap.get("source_attempts"))):
            conn.execute(
                "insert or replace into typed_gap_source_attempts (run_id, gap_id, source_attempt, ordinal) values (?, ?, ?, ?)",
                (run_id, gap_id, attempt, ordinal),
            )
        for ordinal, source in enumerate(_string_list(gap.get("commercial_sources_needed"))):
            conn.execute(
                "insert or replace into typed_gap_commercial_requirements (run_id, gap_id, commercial_source, ordinal) values (?, ?, ?, ?)",
                (run_id, gap_id, source, ordinal),
            )


def _backfill_entity_security_master(conn: sqlite3.Connection, master: Mapping[str, Any], *, run_id: str) -> None:
    _delete_run_tables(conn, run_id, D_SERIES_LAYER_DATABASE_PLANS["entity_security_master"]["schema_objects"])
    timestamp = _utc_now()
    for row in _mapping_rows(master.get("entities")):
        entity_id = _first_text(row, "entity_id")
        conn.execute(
            "insert or replace into entity_master values (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                entity_id,
                _first_text(row, "ticker").upper(),
                _first_text(row, "cik"),
                _first_text(row, "canonical_name", "issuer_name"),
                _first_text(row, "resolution_confidence"),
                _json_text(row),
                timestamp,
            ),
        )
        for identifier_type in ("cik", "lei", "figi", "isin", "cusip", "sedol", "issuer_id"):
            value = _first_text(row, identifier_type)
            if value:
                conn.execute(
                    "insert or replace into security_identifier_map values (?, ?, ?, ?)",
                    (run_id, entity_id, identifier_type, value),
                )
        aliases = _string_list(row.get("aliases"))
        normalized = _string_list(row.get("normalized_aliases"))
        source_refs = _string_list(row.get("source_refs"))
        for ordinal, alias in enumerate(aliases):
            conn.execute(
                "insert or replace into entity_alias_history values (?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    entity_id,
                    alias,
                    normalized[ordinal] if ordinal < len(normalized) else "",
                    source_refs[0] if source_refs else "",
                    ordinal,
                ),
            )
    for index, row in enumerate(_mapping_rows(master.get("unresolved_references"))):
        raw_name = _first_text(row, "raw_name", "query", "name")
        unresolved_id = _first_text(row, "unresolved_reference_id") or _stable_id("unresolved_entity", raw_name, index)
        conn.execute(
            "insert or replace into unresolved_entity_references values (?, ?, ?, ?, ?, ?)",
            (run_id, unresolved_id, raw_name, _first_text(row, "status"), _json_text(row), timestamp),
        )


def _backfill_raw_source_provenance_store(conn: sqlite3.Connection, store: Mapping[str, Any], *, run_id: str) -> None:
    _delete_run_tables(conn, run_id, D_SERIES_LAYER_DATABASE_PLANS["raw_source_provenance_store"]["schema_objects"])
    timestamp = _utc_now()
    for row in _mapping_rows(store.get("records")):
        source_id = _first_text(row, "source_id")
        conn.execute(
            "insert or replace into raw_source_documents values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                source_id,
                _first_text(row, "source_family"),
                _first_text(row, "record_type"),
                _first_text(row, "ticker").upper(),
                _first_text(row, "evidence_ref"),
                _first_text(row, "raw_url"),
                _first_text(row, "local_path"),
                _first_text(row, "document_id"),
                _json_text(row),
                timestamp,
            ),
        )
        conn.execute(
            "insert or replace into raw_source_checksums values (?, ?, ?, ?)",
            (run_id, source_id, _first_text(row, "checksum"), _first_text(row, "file_type")),
        )
        conn.execute(
            "insert or replace into raw_source_parser_runs values (?, ?, ?, ?, ?)",
            (
                run_id,
                source_id,
                _first_text(row, "parser_run_id"),
                _first_text(row, "parser_version"),
                _first_text(row, "retrieved_at"),
            ),
        )
        conn.execute(
            "insert or replace into source_license_robots_policy values (?, ?, ?, ?, ?)",
            (
                run_id,
                source_id,
                _first_text(row, "license_policy"),
                _first_text(row, "robots_policy"),
                _first_text(row, "access_method"),
            ),
        )


def _backfill_asof_vintage_layer(conn: sqlite3.Connection, layer: Mapping[str, Any], *, run_id: str) -> None:
    _delete_run_tables(conn, run_id, D_SERIES_LAYER_DATABASE_PLANS["asof_vintage_layer"]["schema_objects"])
    timestamp = _utc_now()
    for row in _mapping_rows(layer.get("records")):
        vintage_id = _first_text(row, "vintage_id")
        source_family = _first_text(row, "source_family")
        conn.execute(
            "insert or replace into asof_vintage_records values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                vintage_id,
                _first_text(row, "source_id"),
                _first_text(row, "evidence_ref"),
                source_family,
                _first_text(row, "ticker").upper(),
                _first_text(row, "time_basis"),
                _first_text(row, "fiscal_period_end"),
                _first_text(row, "market_as_of_date"),
                _first_text(row, "macro_vintage_date"),
                _json_text(row),
                timestamp,
            ),
        )
        if source_family == "industry_snapshot" or _first_text(row, "macro_vintage_date"):
            conn.execute(
                "insert or replace into macro_vintage_observations values (?, ?, ?, ?, ?)",
                (run_id, vintage_id, _first_text(row, "observation_date"), _first_text(row, "macro_vintage_date"), _json_text(row)),
            )
        if source_family == "market_snapshot" or _first_text(row, "market_as_of_date"):
            conn.execute(
                "insert or replace into market_snapshot_asof values (?, ?, ?, ?)",
                (run_id, vintage_id, _first_text(row, "market_as_of_date"), _json_text(row)),
            )
        if source_family in {"primary_sec_filing", "company_authored_unaudited_sec_filing"} or _first_text(row, "document_id", "filing_date", "accepted_date"):
            conn.execute(
                "insert or replace into filing_amendment_lineage values (?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    vintage_id,
                    _first_text(row, "document_id", "source_id"),
                    _first_text(row, "filing_date"),
                    _first_text(row, "accepted_date"),
                    _json_text(row),
                ),
            )


def _backfill_reconciliation_ledger(conn: sqlite3.Connection, ledger: Mapping[str, Any], *, run_id: str) -> None:
    _delete_run_tables(conn, run_id, D_SERIES_LAYER_DATABASE_PLANS["reconciliation_ledger"]["schema_objects"])
    timestamp = _utc_now()
    for row in _mapping_rows(ledger.get("candidates")):
        conn.execute(
            "insert or replace into reconciliation_candidates values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                _first_text(row, "candidate_id"),
                _first_text(row, "candidate_status"),
                _first_text(row, "ticker").upper(),
                _first_text(row, "canonical_metric_id"),
                _first_text(row, "period_key"),
                _first_text(row, "value"),
                _first_text(row, "unit"),
                _first_text(row, "source_family"),
                _json_text(row),
                timestamp,
            ),
        )
    for row in _mapping_rows(ledger.get("reconciliation_groups")):
        conn.execute(
            "insert or replace into reconciliation_groups values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                _first_text(row, "group_id"),
                _first_text(row, "ticker").upper(),
                _first_text(row, "canonical_metric_id"),
                _first_text(row, "resolution_status"),
                _json_text(row.get("preferred_value") or {}),
                _json_text(row.get("candidate_ids") or []),
                _json_text(row),
                timestamp,
            ),
        )
    for row in _mapping_rows(ledger.get("conflict_gaps")):
        conn.execute(
            "insert or replace into reconciliation_conflict_gaps values (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                _first_text(row, "gap_id"),
                _first_text(row, "ticker").upper(),
                _first_text(row, "metric"),
                _json_text(row.get("conflict_types") or []),
                _json_text(row),
                timestamp,
            ),
        )


def _backfill_metric_product_ontology_snapshot(conn: sqlite3.Connection, ontology: Mapping[str, Any], *, run_id: str) -> None:
    _delete_run_tables(conn, run_id, D_SERIES_LAYER_DATABASE_PLANS["metric_product_ontology_snapshot"]["schema_objects"])
    timestamp = _utc_now()
    for row in _mapping_rows(ontology.get("metrics")):
        conn.execute(
            "insert or replace into metric_product_ontology_metrics values (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                _first_text(row, "canonical_metric_id"),
                _first_text(row, "metric_type"),
                _first_text(row, "display_name", "name"),
                _first_text(row, "unit_family"),
                _first_text(row, "period_rule"),
                _json_text(row),
                timestamp,
            ),
        )
    alias_index = ontology.get("alias_index") if isinstance(ontology.get("alias_index"), Mapping) else {}
    for alias, row in sorted(alias_index.items()):
        if isinstance(row, Mapping):
            conn.execute(
                "insert or replace into metric_product_alias_registry values (?, ?, ?, ?, ?)",
                (
                    run_id,
                    str(alias),
                    _first_text(row, "canonical_metric_id"),
                    _first_text(row, "metric_type"),
                    _first_text(row, "alias_status") or "accepted",
                ),
            )
    for index, row in enumerate(_mapping_rows(ontology.get("observed_metric_mappings"))):
        if _first_text(row, "match_status") in {"mapped"}:
            continue
        review_id = _first_text(row, "review_id") or _stable_id("metric_manual_review", row.get("raw_metric_text"), row.get("canonical_metric_id"), index)
        conn.execute(
            "insert or replace into metric_product_manual_review_queue values (?, ?, ?, ?, ?, ?)",
            (
                run_id,
                review_id,
                _first_text(row, "raw_metric_text"),
                _first_text(row, "match_status"),
                _json_text(row),
                timestamp,
            ),
        )


def _backfill_source_capability_router(conn: sqlite3.Connection, router: Mapping[str, Any], *, run_id: str) -> None:
    _delete_run_tables(conn, run_id, D_SERIES_LAYER_DATABASE_PLANS["source_capability_router"]["schema_objects"])
    timestamp = _utc_now()
    for row in _mapping_rows(router.get("source_capabilities")):
        source_family = _first_text(row, "source_family")
        conn.execute(
            "insert or replace into source_capability_policy values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                source_family,
                1 if row.get("available") else 0,
                1 if row.get("allowed_by_activation") else 0,
                _first_text(row, "claim_authority"),
                1 if row.get("context_only") else 0,
                _first_text(row, "gap_policy"),
                _json_text(row),
                timestamp,
            ),
        )
        conn.execute(
            "insert or replace into commercial_gap_policy values (?, ?, ?, ?)",
            (run_id, source_family, _first_text(row, "gap_policy"), _first_text(row, "claim_authority")),
        )
    for index, row in enumerate(_mapping_rows(router.get("route_decisions"))):
        route_id = _first_text(row, "route_id") or _stable_id("route_decision", row.get("retrieval_route"), row.get("source_family"), index)
        conn.execute(
            "insert or replace into source_route_decisions values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                route_id,
                _first_text(row, "retrieval_route"),
                _first_text(row, "source_family"),
                _first_text(row, "decision_status"),
                _first_text(row, "reason"),
                _first_text(row, "gap_type"),
                _json_text(row),
                timestamp,
            ),
        )


def _backfill_gate_registry_eval_matrix(conn: sqlite3.Connection, gate_matrix: Mapping[str, Any], *, run_id: str) -> None:
    _delete_run_tables(conn, run_id, D_SERIES_LAYER_DATABASE_PLANS["gate_registry_eval_matrix"]["schema_objects"])
    timestamp = _utc_now()
    for gate in _mapping_rows(gate_matrix.get("gate_registry")):
        conn.execute(
            "insert or replace into gate_registry values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            "insert or replace into gate_history values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            "insert or replace into gate_eval_matrix values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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


def _backfill_derived_metric_layer(conn: sqlite3.Connection, layer: Mapping[str, Any], *, run_id: str) -> None:
    _delete_run_tables(conn, run_id, D_SERIES_LAYER_DATABASE_PLANS["derived_metric_layer"]["schema_objects"])
    timestamp = _utc_now()
    formulas: dict[str, Mapping[str, Any]] = {}
    for row in _mapping_rows(layer.get("derived_metrics")):
        formula_id = _first_text(row, "formula_id")
        if formula_id:
            formulas[formula_id] = row
        derived_id = _first_text(row, "derived_metric_id")
        conn.execute(
            "insert or replace into derived_metric_outputs values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                derived_id,
                _first_text(row, "ticker").upper(),
                _first_text(row, "derived_metric_family"),
                _first_text(row, "value"),
                _first_text(row, "unit"),
                _first_text(row, "gate_status"),
                _json_text(row),
                timestamp,
            ),
        )
        for ordinal, fact_id in enumerate(_string_list(row.get("input_fact_ids"))):
            conn.execute(
                "insert or replace into derived_metric_input_lineage values (?, ?, ?, ?)",
                (run_id, derived_id, fact_id, ordinal),
            )
    for row in _mapping_rows(layer.get("skipped_derivations")):
        formula_id = _first_text(row, "formula_id")
        if formula_id and formula_id not in formulas:
            formulas[formula_id] = row
    for formula_id, row in sorted(formulas.items()):
        conn.execute(
            "insert or replace into derived_metric_formula_registry values (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                formula_id,
                _first_text(row, "formula"),
                _first_text(row, "calculation_version") or _first_text(layer, "calculation_version"),
                _first_text(row, "derived_metric_family"),
                _json_text(row),
                timestamp,
            ),
        )


def _backfill_analyst_view_research_memory(conn: sqlite3.Connection, layer: Mapping[str, Any], *, run_id: str) -> None:
    _delete_run_tables(conn, run_id, D_SERIES_LAYER_DATABASE_PLANS["analyst_view_research_memory"]["schema_objects"])
    timestamp = _utc_now()
    for row in _mapping_rows(layer.get("analyst_views")):
        view_id = _first_text(row, "view_id")
        conn.execute(
            "insert or replace into analyst_view_index values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                view_id,
                _first_text(row, "view_type"),
                _first_text(row, "ticker").upper(),
                _first_text(row, "product_or_segment"),
                _first_text(row, "view_status"),
                _json_text(row.get("source_layers") or []),
                _json_text(row.get("drilldown_refs") or {}),
                _json_text(row),
                timestamp,
            ),
        )
        if _first_text(row, "view_type") == "thesis_tracker":
            conn.execute(
                "insert or replace into thesis_tracker values (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    view_id,
                    _first_text(row, "ticker").upper(),
                    _json_text(row.get("claim_ids") or []),
                    _json_text(row.get("gap_ids") or []),
                    _json_text(row.get("derived_metric_ids") or []),
                    _json_text(row),
                    timestamp,
                ),
            )
    for row in _mapping_rows(layer.get("research_memory_entries")):
        conn.execute(
            "insert or replace into analyst_research_memory_entries values (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                _first_text(row, "memory_entry_id"),
                _first_text(row, "view_id"),
                _first_text(row, "view_type"),
                _first_text(row, "ticker").upper(),
                _first_text(row, "retrieval_policy"),
                _json_text(row),
                timestamp,
            ),
        )


def _expected_parity_counts(artifacts: Mapping[str, Any], *, layer_keys: Sequence[str]) -> dict[str, int]:
    expected: dict[str, int] = {}
    if "claim_evidence_ledger" in layer_keys:
        claims = _mapping_rows(_artifact(artifacts, "claim_evidence_ledger").get("claims"))
        expected.update(
            {
                "claim_evidence_claims": len(claims),
                "claim_evidence_support_refs": sum(
                    len(_string_list(claim.get("supporting_evidence_ids")))
                    + len(_string_list(claim.get("contradicting_evidence_ids")))
                    for claim in claims
                ),
                "claim_evidence_gap_refs": sum(len(_string_list(claim.get("gap_ids"))) for claim in claims),
                "claim_evidence_gate_refs": sum(len(_string_list(claim.get("required_gate_results"))) for claim in claims),
            }
        )
    if "typed_gap_ledger" in layer_keys:
        gaps = _mapping_rows(_artifact(artifacts, "typed_gap_ledger").get("gaps"))
        expected.update(
            {
                "typed_gap_events": len(gaps),
                "typed_gap_source_attempts": sum(len(_string_list(gap.get("source_attempts"))) for gap in gaps),
                "typed_gap_commercial_requirements": sum(len(_string_list(gap.get("commercial_sources_needed"))) for gap in gaps),
            }
        )
    if "entity_security_master" in layer_keys:
        master = _artifact(artifacts, "entity_security_master")
        entities = _mapping_rows(master.get("entities"))
        expected.update(
            {
                "entity_master": len(entities),
                "security_identifier_map": sum(
                    len([field for field in ("cik", "lei", "figi", "isin", "cusip", "sedol", "issuer_id") if _first_text(row, field)])
                    for row in entities
                ),
                "entity_alias_history": sum(len(_string_list(row.get("aliases"))) for row in entities),
                "unresolved_entity_references": len(_mapping_rows(master.get("unresolved_references"))),
            }
        )
    if "raw_source_provenance_store" in layer_keys:
        records = _mapping_rows(_artifact(artifacts, "raw_source_provenance_store").get("records"))
        expected.update({table: len(records) for table in D_SERIES_LAYER_DATABASE_PLANS["raw_source_provenance_store"]["schema_objects"]})
    if "asof_vintage_layer" in layer_keys:
        records = _mapping_rows(_artifact(artifacts, "asof_vintage_layer").get("records"))
        expected.update(
            {
                "asof_vintage_records": len(records),
                "macro_vintage_observations": len([row for row in records if _first_text(row, "source_family") == "industry_snapshot" or _first_text(row, "macro_vintage_date")]),
                "market_snapshot_asof": len([row for row in records if _first_text(row, "source_family") == "market_snapshot" or _first_text(row, "market_as_of_date")]),
                "filing_amendment_lineage": len(
                    [
                        row
                        for row in records
                        if _first_text(row, "source_family") in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}
                        or _first_text(row, "document_id", "filing_date", "accepted_date")
                    ]
                ),
            }
        )
    if "reconciliation_ledger" in layer_keys:
        ledger = _artifact(artifacts, "reconciliation_ledger")
        expected.update(
            {
                "reconciliation_candidates": len(_mapping_rows(ledger.get("candidates"))),
                "reconciliation_groups": len(_mapping_rows(ledger.get("reconciliation_groups"))),
                "reconciliation_conflict_gaps": len(_mapping_rows(ledger.get("conflict_gaps"))),
            }
        )
    if "metric_product_ontology_snapshot" in layer_keys:
        ontology = _artifact(artifacts, "metric_product_ontology_snapshot")
        alias_index = ontology.get("alias_index") if isinstance(ontology.get("alias_index"), Mapping) else {}
        observed = _mapping_rows(ontology.get("observed_metric_mappings"))
        expected.update(
            {
                "metric_product_ontology_metrics": len(_mapping_rows(ontology.get("metrics"))),
                "metric_product_alias_registry": len(alias_index),
                "metric_product_manual_review_queue": len([row for row in observed if _first_text(row, "match_status") != "mapped"]),
            }
        )
    if "source_capability_router" in layer_keys:
        router = _artifact(artifacts, "source_capability_router")
        capabilities = _mapping_rows(router.get("source_capabilities"))
        expected.update(
            {
                "source_capability_policy": len(capabilities),
                "source_route_decisions": len(_mapping_rows(router.get("route_decisions"))),
                "commercial_gap_policy": len(capabilities),
            }
        )
    if "gate_registry_eval_matrix" in layer_keys:
        gate_matrix = _artifact(artifacts, "gate_registry_eval_matrix")
        expected.update(
            {
                "gate_registry": len(_mapping_rows(gate_matrix.get("gate_registry"))),
                "gate_history": len(_mapping_rows(gate_matrix.get("gate_history"))),
                "gate_eval_matrix": len(_mapping_rows(gate_matrix.get("eval_matrix"))),
            }
        )
    if "derived_metric_layer" in layer_keys:
        layer = _artifact(artifacts, "derived_metric_layer")
        derived = _mapping_rows(layer.get("derived_metrics"))
        skipped = _mapping_rows(layer.get("skipped_derivations"))
        formulas = {_first_text(row, "formula_id") for row in [*derived, *skipped] if _first_text(row, "formula_id")}
        expected.update(
            {
                "derived_metric_formula_registry": len(formulas),
                "derived_metric_outputs": len(derived),
                "derived_metric_input_lineage": sum(len(_string_list(row.get("input_fact_ids"))) for row in derived),
            }
        )
    if "analyst_view_research_memory" in layer_keys:
        layer = _artifact(artifacts, "analyst_view_research_memory")
        views = _mapping_rows(layer.get("analyst_views"))
        expected.update(
            {
                "analyst_research_memory_entries": len(_mapping_rows(layer.get("research_memory_entries"))),
                "analyst_view_index": len(views),
                "thesis_tracker": len([row for row in views if _first_text(row, "view_type") == "thesis_tracker"]),
            }
        )
    return expected


def _select_payload_rows(
    conn: sqlite3.Connection,
    table: str,
    *,
    run_id: str,
    ticker_filter: Sequence[str],
    order_by: str,
    limit: int,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if run_id:
        clauses.append("run_id = ?")
        params.append(run_id)
    if ticker_filter:
        placeholders = ", ".join("?" for _ in ticker_filter)
        clauses.append(f"upper(ticker) in ({placeholders})")
        params.extend(ticker_filter)
    where = f"where {' and '.join(clauses)}" if clauses else ""
    query = f"select payload_json from {table} {where} order by {order_by} limit ?"
    rows = conn.execute(query, (*params, max(1, int(limit or 100)))).fetchall()
    return [_json_loads(row["payload_json"]) for row in rows]


def _delete_run_tables(conn: sqlite3.Connection, run_id: str, tables: Sequence[str]) -> None:
    for table in tables:
        conn.execute(f"delete from {table} where run_id = ?", (run_id,))


def _set_metadata(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        """
        insert into d_series_store_metadata (key, value_json, updated_at)
        values (?, ?, ?)
        on conflict(key) do update set value_json = excluded.value_json, updated_at = excluded.updated_at
        """,
        (key, _json_text(value), _utc_now()),
    )


def _row_counts(conn: sqlite3.Connection, *, tables: Sequence[str] | None = None) -> dict[str, int]:
    table_names = list(tables or _all_schema_objects())
    return {table: int(conn.execute(f"select count(*) as count from {table}").fetchone()["count"]) for table in table_names}


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


def _all_schema_objects() -> list[str]:
    return [
        table
        for layer_key in D_SERIES_MATERIALIZED_LAYER_KEYS
        for table in D_SERIES_LAYER_DATABASE_PLANS[layer_key]["schema_objects"]
    ]


def _artifact(artifacts: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = artifacts.get(key)
    return value if isinstance(value, Mapping) else {}


def _run_id_from_artifacts(artifacts: Mapping[str, Any]) -> str:
    for key in D_SERIES_MATERIALIZED_LAYER_KEYS:
        artifact = _artifact(artifacts, key)
        text = _first_text(artifact, "run_id")
        if text:
            return text
    return str(artifacts.get("run_id") or "")


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


def _json_loads(value: Any) -> dict[str, Any]:
    try:
        loaded = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return dict(loaded) if isinstance(loaded, Mapping) else {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = "|".join(str(part or "") for part in parts)
    return f"{prefix}:{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:16]}"


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
