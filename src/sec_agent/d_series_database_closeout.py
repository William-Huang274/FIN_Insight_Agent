from __future__ import annotations

from collections import Counter
from typing import Any, Mapping


D_SERIES_DATABASE_CLOSEOUT_SCHEMA_VERSION = "sec_agent_d_series_database_closeout_gate_v0.1"


def build_d_series_database_closeout_gate(state: Mapping[str, Any]) -> dict[str, Any]:
    registry = default_d_series_database_registry()
    materialization = (
        state.get("d_series_database_materialization")
        if isinstance(state.get("d_series_database_materialization"), Mapping)
        else {}
    )
    rows = [
        _closeout_row(entry, state=state, materialization=materialization)
        for entry in registry
    ]
    migration_plan = [_migration_plan_row(row) for row in rows]
    required_rows = [row for row in rows if row.get("database_required")]
    ready_rows = [row for row in required_rows if row.get("closeout_status") == "database_ready"]
    pending_required = [row for row in required_rows if row.get("closeout_status") != "database_ready"]
    payload = {
        "schema_version": D_SERIES_DATABASE_CLOSEOUT_SCHEMA_VERSION,
        "policy": "d_series_cannot_close_until_required_db_layers_have_schema_backfill_parity_v0_1",
        "run_id": str(state.get("run_id") or ""),
        "layer_count": len(rows),
        "required_database_layer_count": len(required_rows),
        "database_ready_layer_count": len(ready_rows),
        "pending_required_database_layer_count": len(pending_required),
        "d_series_closeout_allowed": not pending_required,
        "gate_status": "pass" if not pending_required else "blocked",
        "layer_closeout_rows": rows,
        "migration_backfill_parity_plan": migration_plan,
        "summary": {
            "by_closeout_status": dict(sorted(Counter(row.get("closeout_status") or "unknown" for row in rows).items())),
            "by_store_kind": dict(sorted(Counter(row.get("store_kind") or "unknown" for row in rows).items())),
            "artifact_present_count": len([row for row in rows if row.get("artifact_present")]),
            "required_artifact_missing_count": len(
                [row for row in required_rows if not row.get("artifact_present")]
            ),
            "pending_required_layers": [row.get("layer_key") for row in pending_required],
            "ready_required_layers": [row.get("layer_key") for row in ready_rows],
        },
    }
    payload["validation"] = validate_d_series_database_closeout_gate(payload)
    return _jsonable(payload)


def validate_d_series_database_closeout_gate(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    rows = [row for row in payload.get("layer_closeout_rows") or [] if isinstance(row, Mapping)]
    seen: set[str] = set()
    for index, row in enumerate(rows):
        layer_key = str(row.get("layer_key") or "").strip()
        if not layer_key:
            errors.append({"type": "layer_key_required", "index": index})
        elif layer_key in seen:
            errors.append({"type": "duplicate_layer_key", "layer_key": layer_key})
        seen.add(layer_key)
        if row.get("database_required"):
            for field in ("schema_objects", "migration_id", "backfill_job", "parity_test", "reader_default_policy"):
                if field == "schema_objects":
                    if not row.get(field):
                        errors.append({"type": "required_database_layer_missing_field", "layer_key": layer_key, "field": field})
                elif not str(row.get(field) or "").strip():
                    errors.append({"type": "required_database_layer_missing_field", "layer_key": layer_key, "field": field})
            if not row.get("artifact_present"):
                warnings.append({"type": "required_database_layer_artifact_missing_in_current_run", "layer_key": layer_key})
        if str(row.get("closeout_status") or "") == "database_ready" and row.get("database_required"):
            materialization = row.get("database_materialization") if isinstance(row.get("database_materialization"), Mapping) else {}
            required_status = {
                "schema_migration_status": "applied",
                "backfill_status": "complete",
                "parity_status": "pass",
                "reader_default_status": "database_default",
            }
            for field, expected in required_status.items():
                if materialization.get(field) != expected:
                    errors.append(
                        {
                            "type": "database_ready_layer_missing_materialization_status",
                            "layer_key": layer_key,
                            "field": field,
                            "expected": expected,
                            "actual": materialization.get(field),
                        }
                    )
    if payload.get("d_series_closeout_allowed") and payload.get("pending_required_database_layer_count"):
        errors.append({"type": "closeout_allowed_with_pending_required_layers"})
    return {
        "schema_version": "sec_agent_d_series_database_closeout_gate_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def default_d_series_database_registry() -> list[dict[str, Any]]:
    return [
        _entry(
            "D1",
            "claim_evidence_ledger",
            "claim_evidence_ledger",
            "sql_append_only",
            [
                "claim_evidence_claims",
                "claim_evidence_support_refs",
                "claim_evidence_gap_refs",
                "claim_evidence_gate_refs",
            ],
            "d001_claim_evidence_ledger_append_only",
            "backfill_claim_evidence_ledger_from_run_artifacts",
            "test_claim_evidence_ledger_artifact_database_parity",
            "cross_run_claim_lookup_default_database",
        ),
        _entry(
            "D2",
            "typed_gap_ledger",
            "typed_gap_ledger",
            "sql_append_only",
            ["typed_gap_events", "typed_gap_source_attempts", "typed_gap_commercial_requirements"],
            "d002_typed_gap_ledger_append_only",
            "backfill_typed_gap_ledger_from_run_artifacts",
            "test_typed_gap_ledger_artifact_database_parity",
            "cross_run_gap_lookup_default_database",
        ),
        _entry(
            "D3",
            "entity_security_master",
            "entity_security_master",
            "sql_resolver",
            ["entity_master", "security_identifier_map", "entity_alias_history", "unresolved_entity_references"],
            "d003_entity_security_master_resolver",
            "backfill_entity_security_master_from_inventory",
            "test_entity_security_master_artifact_database_parity",
            "entity_resolution_default_database",
        ),
        _entry(
            "D4",
            "raw_source_provenance_store",
            "raw_source_provenance_store",
            "sql_plus_object_store",
            ["raw_source_documents", "raw_source_checksums", "raw_source_parser_runs", "source_license_robots_policy"],
            "d004_raw_source_provenance_store",
            "backfill_raw_source_provenance_from_run_artifacts",
            "test_raw_source_provenance_artifact_database_parity",
            "source_lineage_default_database",
        ),
        _entry(
            "D5",
            "asof_vintage_layer",
            "asof_vintage_layer",
            "sql_temporal",
            ["asof_vintage_records", "macro_vintage_observations", "market_snapshot_asof", "filing_amendment_lineage"],
            "d005_asof_vintage_temporal_store",
            "backfill_asof_vintage_from_run_artifacts",
            "test_asof_vintage_artifact_database_parity",
            "temporal_lookup_default_database",
        ),
        _entry(
            "D6",
            "reconciliation_ledger",
            "reconciliation_ledger",
            "sql_append_only",
            ["reconciliation_candidates", "reconciliation_groups", "reconciliation_conflict_gaps"],
            "d006_reconciliation_ledger_store",
            "backfill_reconciliation_ledger_from_run_artifacts",
            "test_reconciliation_ledger_artifact_database_parity",
            "preferred_fact_lookup_default_database",
        ),
        _entry(
            "D7",
            "metric_product_ontology_snapshot",
            "metric_product_ontology_snapshot",
            "sql_registry",
            ["metric_product_ontology_metrics", "metric_product_alias_registry", "metric_product_manual_review_queue"],
            "d007_metric_product_ontology_registry",
            "backfill_metric_product_ontology_from_snapshots",
            "test_metric_product_ontology_artifact_database_parity",
            "metric_mapping_default_registry_database",
        ),
        _entry(
            "D8",
            "source_capability_router",
            "source_capability_router",
            "sql_policy_registry",
            ["source_capability_policy", "source_route_decisions", "commercial_gap_policy"],
            "d008_source_capability_router_policy_store",
            "backfill_source_capability_router_from_run_artifacts",
            "test_source_capability_router_artifact_database_parity",
            "source_policy_default_database",
        ),
        _entry(
            "D9",
            "gate_registry_eval_matrix",
            "gate_registry_eval_matrix",
            "sql_append_only",
            ["gate_registry", "gate_history", "gate_eval_matrix"],
            "d009_gate_registry_history_store",
            "backfill_gate_history_from_run_artifacts",
            "test_gate_registry_artifact_database_parity",
            "gate_history_default_database",
        ),
        _entry(
            "D10",
            "derived_metric_layer",
            "derived_metric_layer",
            "sql_formula_registry",
            ["derived_metric_formula_registry", "derived_metric_outputs", "derived_metric_input_lineage"],
            "d010_derived_metric_formula_store",
            "backfill_derived_metric_layer_from_run_artifacts",
            "test_derived_metric_artifact_database_parity",
            "derived_metric_lookup_default_database",
        ),
        _entry(
            "D11",
            "analyst_view_research_memory",
            "analyst_view_research_memory",
            "sql_vector_graph_memory",
            ["analyst_views", "research_memory_entries", "research_memory_drilldown_refs", "research_memory_supersession"],
            "d011_analyst_view_research_memory_store",
            "backfill_analyst_view_memory_from_run_artifacts",
            "test_analyst_view_memory_artifact_database_parity",
            "research_memory_default_database",
        ),
    ]


def _entry(
    d_item: str,
    layer_key: str,
    artifact_key: str,
    store_kind: str,
    schema_objects: list[str],
    migration_id: str,
    backfill_job: str,
    parity_test: str,
    reader_default_policy: str,
) -> dict[str, Any]:
    return {
        "d_item": d_item,
        "layer_key": layer_key,
        "artifact_key": artifact_key,
        "database_required": True,
        "store_kind": store_kind,
        "schema_objects": schema_objects,
        "migration_id": migration_id,
        "backfill_job": backfill_job,
        "parity_test": parity_test,
        "reader_default_policy": reader_default_policy,
    }


def _closeout_row(
    entry: Mapping[str, Any],
    *,
    state: Mapping[str, Any],
    materialization: Mapping[str, Any],
) -> dict[str, Any]:
    layer_key = str(entry.get("layer_key") or "")
    artifact = state.get(layer_key) if isinstance(state.get(layer_key), Mapping) else {}
    artifact_refs = state.get("artifact_refs") if isinstance(state.get("artifact_refs"), Mapping) else {}
    materialized = materialization.get(layer_key) if isinstance(materialization.get(layer_key), Mapping) else {}
    ready = _database_ready(materialized)
    closeout_status = "database_ready" if ready else "pending_database_implementation"
    return {
        **dict(entry),
        "artifact_present": bool(artifact),
        "artifact_schema_version": str(artifact.get("schema_version") or "") if isinstance(artifact, Mapping) else "",
        "artifact_ref": str(artifact_refs.get(layer_key) or ""),
        "schema_plan_present": bool(entry.get("schema_objects")),
        "migration_plan_present": bool(entry.get("migration_id")),
        "backfill_plan_present": bool(entry.get("backfill_job")),
        "parity_test_plan_present": bool(entry.get("parity_test")),
        "reader_default_plan_present": bool(entry.get("reader_default_policy")),
        "database_materialization": dict(materialized),
        "closeout_status": closeout_status,
        "closeout_required_actions": []
        if ready
        else [
            "apply_schema_migration",
            "run_artifact_to_database_backfill",
            "run_artifact_database_parity_test",
            "switch_agent_reads_to_database_default",
        ],
    }


def _database_ready(materialized: Mapping[str, Any]) -> bool:
    return (
        materialized.get("schema_migration_status") == "applied"
        and materialized.get("backfill_status") == "complete"
        and materialized.get("parity_status") == "pass"
        and materialized.get("reader_default_status") == "database_default"
    )


def _migration_plan_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "layer_key": row.get("layer_key") or "",
        "migration_id": row.get("migration_id") or "",
        "schema_objects": list(row.get("schema_objects") or []),
        "backfill_job": row.get("backfill_job") or "",
        "parity_test": row.get("parity_test") or "",
        "reader_default_policy": row.get("reader_default_policy") or "",
        "required_before_d_series_closeout": bool(row.get("database_required")),
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value
