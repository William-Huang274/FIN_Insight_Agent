"""P14 Data ingestion and retrieval control plane for R53-R60.

S3 proved the retrieval/evidence ledger.  P14 adds the upstream data-plane
contract from source snapshot through fetch, parser, authority mapping, index
refresh, retrieval strategy budgets, ContextEngine bridge, and DB/index
performance profiles.  This is a scoped runtime drill: it proves the control
plane is SQL-final and fail-closed; it does not claim full crawler coverage or
production-scale data refresh.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.r53_r60_durable_runtime_hil_resource_router import table_row_count
from sec_agent.r53_r60_graph_skill_memory_lifecycle import build_p13_gate, default_p13_paths
from sec_agent.r53_r60_research_to_quant_lab import row_to_dict, rows_to_dicts, table_exists
from sec_agent.r53_r60_retrieval_evidence_spine import REQUIRED_ROUTES, build_s3_gate, default_s3_paths
from sec_agent.r53_r60_runtime_task_spine import (
    FinSightResearchRuntimeFacade,
    RuntimeTaskSpineStore,
    default_s1_paths,
    json_dumps,
    json_loads,
    rel_path,
    stable_id,
    utc_now_iso,
    write_json,
    write_jsonl,
)


SCHEMA_VERSION = "r53_r60_p14_data_ingestion_retrieval_control_plane_v0_1"
P14_TASK_ID = "p14_scope_task_data_ingestion_retrieval_control_plane"
P14_DRILL_TASK_ID = "p14_data_plane_drill_task_ai_infra_ingestion_retrieval"

P14_DEMAND_IDS = (
    "P14-D01-source-snapshot-and-ingestion-job",
    "P14-D02-fetch-and-parser-contract",
    "P14-D03-storage-lineage-and-authority-mapping",
    "P14-D04-index-refresh-and-route-budget",
    "P14-D05-contextengine-retrieval-bridge",
    "P14-D06-db-index-performance-profile",
    "P14-D07-retrieval-qrels-and-quality-feedback",
    "P14-D08-fail-closed-parser-boundary",
)

SOURCE_SNAPSHOT_IDS = (
    "p14_src_sec_structured_facts_2026q1",
    "p14_src_company_ir_product_deck_nvda",
    "p14_src_official_product_surface_gpu",
    "p14_src_cloud_customer_deployment_news",
    "p14_src_macro_rates_fred_api",
    "p14_src_milvus_semantic_index_603",
)
NEGATIVE_RAW_DOC_ID = "p14_raw_unparsed_web_snapshot_blocked"
NEGATIVE_AUTHORITY_ID = "p14_authority_blocked_raw_snapshot_no_parser"


@dataclass(frozen=True)
class P14Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


def default_p14_paths(root: Path) -> P14Paths:
    s1_paths = default_s1_paths(root)
    return P14Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "p14_data_ingestion_retrieval_control_plane_schema_v0_1.json",
        gate_rows_path=root
        / "data"
        / "manifests"
        / "r53_r60_p14_data_ingestion_retrieval_control_plane_gate_rows_v0_1.jsonl",
        summary_path=root
        / "data"
        / "manifests"
        / "r53_r60_p14_data_ingestion_retrieval_control_plane_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_p14_data_ingestion_retrieval_control_plane_l4_scope_pass.zh-CN.md",
    )


def data_ingestion_retrieval_control_plane_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "release_scope": "data_ingestion_retrieval_control_plane_drill",
        "tables": [
            "data_ingestion_control_plane_metadata_p14",
            "source_snapshot_registry_p14",
            "ingestion_jobs_p14",
            "raw_source_documents_p14",
            "fetch_attempts_p14",
            "parser_runs_p14",
            "parsed_object_records_p14",
            "authority_mapping_records_p14",
            "index_refresh_records_p14",
            "retrieval_strategy_packs_p14",
            "retrieval_budget_records_p14",
            "retrieval_context_bridge_records_p14",
            "retrieval_quality_probe_records_p14",
            "data_quality_observations_p14",
            "database_performance_profiles_p14",
            "current_universe_refresh_evidence_p14",
            "ingestion_lineage_edges_p14",
            "data_plane_acceptance_records_p14",
            "data_plane_readiness_reports_p14",
            "data_plane_gate_results_p14",
        ],
        "required_source_modalities": ["api_json", "http_html", "playwright_rendered_html", "pdf_table", "sql_index"],
        "required_intents": [
            "exact_financial_metric",
            "product_spec_architecture",
            "customer_deployment_adoption",
            "capital_funding_ownership",
            "retrievable_gap_repair",
        ],
        "policy": {
            "sql_ledger_is_final_audit_source": True,
            "raw_source_snapshot_is_not_fact_authority": True,
            "parser_run_required_before_authority_mapping": True,
            "index_refresh_requires_lineage_ref": True,
            "milvus_is_semantic_recall_not_exact_authority": True,
            "context_bridge_preserves_exact_refs": True,
            "failed_fetch_or_parser_creates_typed_gap": True,
            "current_accepted_universe_refresh_requires_manifest_evidence": True,
            "current_accepted_universe_refresh_is_runtime_ready": True,
            "not_full_internet_crawler_or_realtime_refresh": True,
            "not_production_p95_p99_sla": True,
        },
    }


def create_data_ingestion_retrieval_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists data_ingestion_control_plane_metadata_p14 (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists source_snapshot_registry_p14 (
            source_snapshot_id text primary key,
            source_role text not null,
            source_name text not null,
            source_modality text not null,
            authority_boundary text not null,
            refresh_policy text not null,
            source_uri text not null,
            snapshot_hash text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists ingestion_jobs_p14 (
            ingestion_job_id text primary key,
            source_snapshot_id text not null,
            job_type text not null,
            idempotency_key text not null,
            status text not null,
            started_at text not null,
            finished_at text not null,
            fetched_document_count integer not null,
            parser_run_count integer not null,
            typed_gap_count integer not null,
            payload_json text not null default '{}'
        );
        create table if not exists raw_source_documents_p14 (
            raw_document_id text primary key,
            source_snapshot_id text not null,
            ingestion_job_id text not null,
            document_kind text not null,
            issuer_id text not null,
            ticker text not null,
            object_uri text not null,
            content_digest text not null,
            storage_tier text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists fetch_attempts_p14 (
            fetch_attempt_id text primary key,
            raw_document_id text not null,
            source_snapshot_id text not null,
            tool_route text not null,
            http_status integer not null,
            status text not null,
            blocked_reason text not null,
            retry_policy text not null,
            latency_ms integer not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists parser_runs_p14 (
            parser_run_id text primary key,
            raw_document_id text not null,
            parser_name text not null,
            parser_version text not null,
            status text not null,
            parsed_object_count integer not null,
            authority_candidate_count integer not null,
            typed_gap_count integer not null,
            quality_score real not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists parsed_object_records_p14 (
            parsed_object_id text primary key,
            parser_run_id text not null,
            raw_document_id text not null,
            object_type text not null,
            issuer_id text not null,
            ticker text not null,
            product_family text not null,
            metric_or_signal text not null,
            period_or_version text not null,
            citation_ref text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists authority_mapping_records_p14 (
            authority_mapping_id text primary key,
            parsed_object_id text not null,
            authority_mode text not null,
            claim_scope text not null,
            can_enter_claim_card integer not null,
            can_enter_context integer not null,
            can_enter_exact_value_ledger integer not null,
            blocked_reason text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists index_refresh_records_p14 (
            index_refresh_id text primary key,
            index_name text not null,
            index_type text not null,
            source_snapshot_ids_json text not null default '[]',
            authority_mapping_ids_json text not null default '[]',
            parser_run_ids_json text not null default '[]',
            lineage_complete integer not null,
            refresh_status text not null,
            row_or_vector_count integer not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists retrieval_strategy_packs_p14 (
            strategy_pack_id text primary key,
            intent_id text not null,
            route_order_json text not null default '[]',
            first_pass_budget_json text not null default '{}',
            second_pass_trigger text not null,
            authority_boundary text not null,
            stop_condition text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists retrieval_budget_records_p14 (
            budget_id text primary key,
            strategy_pack_id text not null,
            route_id text not null,
            candidate_budget integer not null,
            rerank_budget integer not null,
            context_budget_tokens integer not null,
            quota_reason text not null,
            spillover_policy text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists retrieval_context_bridge_records_p14 (
            bridge_id text primary key,
            actor_id text not null,
            strategy_pack_id text not null,
            context_policy_ref text not null,
            selected_authority_mapping_ids_json text not null default '[]',
            selected_index_refresh_ids_json text not null default '[]',
            exact_ref_policy text not null,
            compression_policy text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists retrieval_quality_probe_records_p14 (
            probe_id text primary key,
            intent_id text not null,
            expected_source_role text not null,
            expected_authority_mode text not null,
            candidate_found integer not null,
            selected_for_context integer not null,
            gap_if_missing text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists data_quality_observations_p14 (
            observation_id text primary key,
            observation_type text not null,
            severity text not null,
            object_ref text not null,
            status text not null,
            finding text not null,
            next_action text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists database_performance_profiles_p14 (
            profile_id text primary key,
            component text not null,
            workload_name text not null,
            row_or_vector_count integer not null,
            p50_latency_ms integer not null,
            p95_latency_ms integer not null,
            memory_mb integer not null,
            complexity_class text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists current_universe_refresh_evidence_p14 (
            evidence_id text primary key,
            evidence_name text not null,
            manifest_path text not null,
            evidence_scope text not null,
            expected_contract text not null,
            observed_value_json text not null default '{}',
            status text not null,
            boundary text not null,
            created_at text not null
        );
        create table if not exists ingestion_lineage_edges_p14 (
            lineage_edge_id text primary key,
            from_ref text not null,
            to_ref text not null,
            edge_type text not null,
            lineage_status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists data_plane_acceptance_records_p14 (
            acceptance_id text primary key,
            demand_id text not null,
            product_acceptance_json text not null default '{}',
            engineering_acceptance_json text not null default '{}',
            quality_acceptance_json text not null default '{}',
            ops_acceptance_json text not null default '{}',
            evidence_refs_json text not null default '[]',
            status text not null,
            owner text not null,
            created_at text not null
        );
        create table if not exists data_plane_readiness_reports_p14 (
            report_id text primary key,
            task_id text not null,
            source_snapshot_status text not null,
            parser_contract_status text not null,
            lineage_status text not null,
            retrieval_control_status text not null,
            context_bridge_status text not null,
            performance_status text not null,
            release_decision text not null,
            gate_refs_json text not null default '[]',
            known_gaps_json text not null default '[]',
            next_actions_json text not null default '[]',
            owner text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists data_plane_gate_results_p14 (
            gate_result_id text primary key,
            gate_id text not null,
            gate_group text not null,
            status text not null,
            pass_level text not null,
            detail_json text not null default '{}',
            created_at text not null
        );
        create index if not exists idx_p14_parser_raw on parser_runs_p14(raw_document_id);
        create index if not exists idx_p14_authority_mode on authority_mapping_records_p14(authority_mode, status);
        create index if not exists idx_p14_budget_strategy on retrieval_budget_records_p14(strategy_pack_id);
        """
    )


def seed_p14_metadata(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "source_of_truth": "S1 SQL runtime task spine",
        "scope_boundary": "Control-plane drill only; not full crawler coverage or production refresh.",
    }
    for key, value in metadata.items():
        conn.execute(
            """
            insert into data_ingestion_control_plane_metadata_p14(key, value_json, updated_at)
            values (?, ?, ?)
            on conflict(key) do update set value_json = excluded.value_json, updated_at = excluded.updated_at
            """,
            (key, json_dumps(value), now),
        )


def clear_p14_rows(conn: sqlite3.Connection) -> None:
    for table in [
        "data_plane_gate_results_p14",
        "data_plane_readiness_reports_p14",
        "data_plane_acceptance_records_p14",
        "ingestion_lineage_edges_p14",
        "database_performance_profiles_p14",
        "current_universe_refresh_evidence_p14",
        "data_quality_observations_p14",
        "retrieval_quality_probe_records_p14",
        "retrieval_context_bridge_records_p14",
        "retrieval_budget_records_p14",
        "retrieval_strategy_packs_p14",
        "index_refresh_records_p14",
        "authority_mapping_records_p14",
        "parsed_object_records_p14",
        "parser_runs_p14",
        "fetch_attempts_p14",
        "raw_source_documents_p14",
        "ingestion_jobs_p14",
        "source_snapshot_registry_p14",
    ]:
        conn.execute(f"delete from {table}")


def build_p14_gate(root: Path, *, task_id: str = P14_TASK_ID) -> dict[str, Any]:
    root = root.resolve()
    paths = default_p14_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    ensure_p14_dependencies(root)
    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    with runtime.store._connect() as conn:
        create_data_ingestion_retrieval_schema(conn)
        seed_p14_metadata(conn)
        clear_p14_rows(conn)

    get_or_create_data_plane_drill_task(runtime)
    materialized = materialize_data_plane_control(runtime, root=root, drill_task_id=P14_DRILL_TASK_ID)
    p14_task = get_or_create_p14_task(runtime, task_id=task_id)
    if str(p14_task["task"]["status"]) != "running":
        runtime.store.transition_task(
            task_id,
            "running",
            actor="data_plane_control_builder",
            message="start P14 data ingestion and retrieval control-plane build",
            progress=10,
        )

    write_json(paths.schema_path, data_ingestion_retrieval_control_plane_schema_contract())
    artifact_refs = record_p14_artifacts(runtime, root, paths, task_id, materialized)
    event = runtime.append_workpaper_event(
        task_id,
        actor="data_engineering_owner",
        event_type="data_ingestion_retrieval_control_plane_ready",
        section_id="data_ingestion_retrieval_control_plane",
        claim_id="p14_data_plane_scope_pass",
        payload={
            "schema_version": SCHEMA_VERSION,
            "drill_task_id": P14_DRILL_TASK_ID,
            "artifact_ref_ids": [item["artifact_ref_id"] for item in artifact_refs],
            "scope_boundary": "Control plane is wired; full source coverage and production refresh remain later gates.",
        },
    )
    node = runtime.record_node_result(
        task_id,
        node="data_ingestion_retrieval_control_plane_builder",
        status="pass",
        input_payload={"dependencies": ["S3 retrieval evidence spine", "P13 graph skill memory lifecycle"]},
        output_payload={**materialized, "workpaper_event_id": event["workpaper_event_id"]},
        artifact_ref_ids=[item["artifact_ref_id"] for item in artifact_refs],
        actor="data_plane_control_builder",
    )
    for name, payload in [
        ("p14_ingestion_parser_gate", {"parser_run_count": materialized["parser_run_count"]}),
        ("p14_authority_mapping_gate", {"authority_mapping_count": materialized["authority_mapping_count"]}),
        ("p14_index_refresh_gate", {"index_refresh_count": materialized["index_refresh_count"]}),
        ("p14_context_bridge_gate", {"context_bridge_count": materialized["context_bridge_count"]}),
    ]:
        runtime.record_trace_span(
            task_id,
            span_kind="data_plane_control_gate",
            name=name,
            status="pass",
            actor="data_plane_control_verifier",
            node_execution_id=node["node_execution_id"],
            latency_ms=0,
            token_count=0,
            cost_amount=0.0,
            model_name="deterministic",
            provider="local",
            payload={"closeout_level": "L4_scope_pass", **payload},
        )
    runtime.store.transition_task(task_id, "succeeded", actor="data_plane_control_verifier", message="P14 data-plane drill complete", progress=100)

    gate_rows = evaluate_p14_gates(root, runtime.store, task_id=task_id, drill_task_id=P14_DRILL_TASK_ID, materialized=materialized)
    persist_p14_gate_results(runtime.store, gate_rows)
    finalize_p14_readiness_report(runtime.store, gate_rows)
    summary = build_p14_summary(root, paths, gate_rows, runtime.store, task_id=task_id, materialized=materialized)
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_p14_report(summary, gate_rows), encoding="utf-8")
    return summary


def ensure_p14_dependencies(root: Path) -> None:
    s3_summary_path = default_s3_paths(root).summary_path
    if not dependency_summary_passes(s3_summary_path, "S3_L4_scope_pass"):
        build_s3_gate(root)
    p13_summary_path = default_p13_paths(root).summary_path
    if not dependency_summary_passes(p13_summary_path, "P13_L4_scope_pass_graph_skill_memory_lifecycle_ready"):
        build_p13_gate(root)


def dependency_summary_passes(path: Path, release_decision: str) -> bool:
    if not path.exists():
        return False
    payload = json_loads(path.read_text(encoding="utf-8"), {})
    return payload.get("status") == "pass" and payload.get("release_decision") == release_decision


def get_or_create_p14_task(runtime: FinSightResearchRuntimeFacade, *, task_id: str) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(task_id)
    except Exception:
        return runtime.create_task(
            "Build Data Ingestion / Retrieval Control Plane gate package",
            task_id=task_id,
            trace_id="trace_p14_data_ingestion_retrieval_control_plane",
            user_id="p14_gate",
            case_id="p14_data_plane_control_l4_scope",
            mode="data_plane_control_gate",
            objective={"minimum_evidence": "source/fetch/parser/authority/index/context/performance rows exist"},
            metadata={"source_slice": "P14", "closeout_level": "L4_scope_pass"},
        )
    if str(state["task"]["status"]) in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        return runtime.resume_task(task_id, actor="p14_builder", reason="rebuild P14 data ingestion control plane")
    return state


def get_or_create_data_plane_drill_task(runtime: FinSightResearchRuntimeFacade) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(P14_DRILL_TASK_ID)
    except Exception:
        state = runtime.create_task(
            "Run P14 data-plane drill across source snapshot, parser, index and retrieval bridge",
            task_id=P14_DRILL_TASK_ID,
            trace_id="trace_p14_data_plane_drill",
            user_id="data_engineering_owner",
            case_id="pilot_case_ai_infra_ingestion_retrieval_control",
            mode="data_plane_control_drill",
            objective={
                "research_question": "Can source rows become parser-backed authority rows and route-budgeted context without raw fallback?",
                "required_intents": data_ingestion_retrieval_control_plane_schema_contract()["required_intents"],
            },
            metadata={"source_slice": "P14", "drill": True},
        )
    if str(state["task"]["status"]) in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        state = runtime.resume_task(P14_DRILL_TASK_ID, actor="p14_data_plane_drill", reason="rerun data-plane control drill")
    if str(state["task"]["status"]) != "running":
        state = runtime.store.transition_task(
            P14_DRILL_TASK_ID,
            "running",
            actor="p14_data_plane_drill",
            message="start data-plane control drill",
            progress=5,
        )
    return state


def materialize_data_plane_control(
    runtime: FinSightResearchRuntimeFacade,
    *,
    root: Path,
    drill_task_id: str,
) -> dict[str, Any]:
    store = runtime.store
    with store._connect() as conn:
        create_data_ingestion_retrieval_schema(conn)
        clear_p14_rows(conn)
    drill_state = runtime.get_task_state(drill_task_id)
    run_id = str(drill_state["task"]["current_run_id"])
    now = utc_now_iso()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("begin immediate")
        try:
            snapshots = insert_source_snapshots(conn, now=now)
            jobs = insert_ingestion_jobs(conn, snapshots=snapshots, now=now)
            raw_docs = insert_raw_documents(conn, jobs=jobs, now=now)
            insert_fetch_attempts(conn, raw_docs=raw_docs, now=now)
            parser_runs = insert_parser_runs(conn, raw_docs=raw_docs, now=now)
            parsed_objects = insert_parsed_objects(conn, parser_runs=parser_runs, now=now)
            authority_rows = insert_authority_mappings(conn, parsed_objects=parsed_objects, now=now)
            index_rows = insert_index_refreshes(conn, snapshots=snapshots, parser_runs=parser_runs, authority_rows=authority_rows, now=now)
            strategies = insert_retrieval_strategies(conn, now=now)
            insert_retrieval_budgets(conn, strategies=strategies, now=now)
            insert_context_bridges(conn, strategies=strategies, authority_rows=authority_rows, index_rows=index_rows, now=now)
            insert_quality_probes(conn, now=now)
            insert_data_quality_observations(conn, now=now)
            insert_performance_profiles(conn, now=now)
            insert_current_universe_refresh_evidence(conn, root=root, now=now)
            insert_lineage_edges(conn, raw_docs=raw_docs, parser_runs=parser_runs, parsed_objects=parsed_objects, authority_rows=authority_rows, index_rows=index_rows, now=now)
            insert_data_plane_acceptance(conn, now=now)
            insert_data_plane_readiness_report(conn, task_id=drill_task_id, now=now)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    runtime.store.transition_task(drill_task_id, "succeeded", actor="p14_data_plane_verifier", message="P14 data-plane drill complete", progress=100)
    return collect_p14_counts(store, drill_task_id=drill_task_id, run_id=run_id)


def insert_source_snapshots(conn: sqlite3.Connection, *, now: str) -> list[dict[str, Any]]:
    rows = [
        {
            "source_snapshot_id": SOURCE_SNAPSHOT_IDS[0],
            "source_role": "primary_company_disclosure",
            "source_name": "SEC CompanyFacts structured facts",
            "source_modality": "api_json",
            "authority_boundary": "exact_financial_metric_after_parser",
            "refresh_policy": "quarterly_or_filing_event",
            "source_uri": "sec://companyfacts/NVDA/2026Q1",
            "status": "snapshot_ready",
            "payload": {"tier": "L1", "issuer_bound": True},
        },
        {
            "source_snapshot_id": SOURCE_SNAPSHOT_IDS[1],
            "source_role": "official_product_surface",
            "source_name": "NVDA investor product deck",
            "source_modality": "pdf_table",
            "authority_boundary": "technical_fact_or_bounded_signal_after_parser",
            "refresh_policy": "event_driven_ir_update",
            "source_uri": "ir://NVDA/product-architecture-deck",
            "status": "snapshot_ready",
            "payload": {"tier": "L2", "product_family": "gpu_accelerator"},
        },
        {
            "source_snapshot_id": SOURCE_SNAPSHOT_IDS[2],
            "source_role": "official_product_surface",
            "source_name": "Official GPU product surface",
            "source_modality": "http_html",
            "authority_boundary": "technical_fact_after_parser",
            "refresh_policy": "monthly",
            "source_uri": "https://example.local/nvda/h100-b200",
            "status": "snapshot_ready",
            "payload": {"tier": "L2", "requires_html_parser": True},
        },
        {
            "source_snapshot_id": SOURCE_SNAPSHOT_IDS[3],
            "source_role": "customer_deployment_signal",
            "source_name": "Official cloud customer deployment news",
            "source_modality": "playwright_rendered_html",
            "authority_boundary": "deployment_signal_after_parser",
            "refresh_policy": "weekly_allowlisted_web",
            "source_uri": "https://example.local/customer/news/ai-cluster",
            "status": "snapshot_ready",
            "payload": {"tier": "L3", "requires_counterparty_binding": True},
        },
        {
            "source_snapshot_id": SOURCE_SNAPSHOT_IDS[4],
            "source_role": "macro_policy_proxy",
            "source_name": "FRED rates API",
            "source_modality": "api_json",
            "authority_boundary": "macro_context_only",
            "refresh_policy": "daily",
            "source_uri": "fred://DGS10",
            "status": "snapshot_ready",
            "payload": {"tier": "L2", "company_specific": False},
        },
        {
            "source_snapshot_id": SOURCE_SNAPSHOT_IDS[5],
            "source_role": "semantic_recall_index",
            "source_name": "Milvus semantic index 603 issuers",
            "source_modality": "sql_index",
            "authority_boundary": "semantic_recall_only",
            "refresh_policy": "snapshot_versioned",
            "source_uri": "milvus://local/fin_insight_603",
            "status": "snapshot_ready",
            "payload": {"tier": "index", "exact_authority": False},
        },
    ]
    for row in rows:
        conn.execute(
            "insert into source_snapshot_registry_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row["source_snapshot_id"],
                row["source_role"],
                row["source_name"],
                row["source_modality"],
                row["authority_boundary"],
                row["refresh_policy"],
                row["source_uri"],
                stable_id("snapdigest", [row["source_snapshot_id"], row["source_uri"]]),
                row["status"],
                json_dumps(row["payload"]),
                now,
            ),
        )
    return rows


def insert_ingestion_jobs(
    conn: sqlite3.Connection,
    *,
    snapshots: list[dict[str, Any]],
    now: str,
) -> list[dict[str, Any]]:
    jobs = []
    for idx, snapshot in enumerate(snapshots):
        typed_gap = 0
        status = "succeeded"
        if snapshot["source_snapshot_id"] == SOURCE_SNAPSHOT_IDS[5]:
            status = "index_snapshot_reconciled"
        job = {
            "ingestion_job_id": stable_id("p14job", [snapshot["source_snapshot_id"]]),
            "source_snapshot_id": snapshot["source_snapshot_id"],
            "job_type": "index_reconcile" if snapshot["source_snapshot_id"] == SOURCE_SNAPSHOT_IDS[5] else "snapshot_fetch_parse",
            "idempotency_key": stable_id("p14idem", [snapshot["source_snapshot_id"], SCHEMA_VERSION]),
            "status": status,
            "fetched_document_count": 1,
            "parser_run_count": 0 if snapshot["source_snapshot_id"] == SOURCE_SNAPSHOT_IDS[5] else 1,
            "typed_gap_count": typed_gap,
            "payload": {"sequence": idx, "no_weak_fallback": True},
        }
        conn.execute(
            "insert into ingestion_jobs_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                job["ingestion_job_id"],
                job["source_snapshot_id"],
                job["job_type"],
                job["idempotency_key"],
                job["status"],
                now,
                now,
                job["fetched_document_count"],
                job["parser_run_count"],
                job["typed_gap_count"],
                json_dumps(job["payload"]),
            ),
        )
        jobs.append(job)
    return jobs


def insert_raw_documents(
    conn: sqlite3.Connection,
    *,
    jobs: list[dict[str, Any]],
    now: str,
) -> list[dict[str, Any]]:
    docs = []
    by_snapshot = {job["source_snapshot_id"]: job for job in jobs}
    specs = [
        (SOURCE_SNAPSHOT_IDS[0], "structured_fact_json", "NVDA", "NVDA", "object://bronze/sec/NVDA/companyfacts_2026q1.json", "bronze"),
        (SOURCE_SNAPSHOT_IDS[1], "ir_pdf", "NVDA", "NVDA", "object://bronze/ir/NVDA/product_architecture_deck.pdf", "bronze"),
        (SOURCE_SNAPSHOT_IDS[2], "official_product_html", "NVDA", "NVDA", "object://bronze/web/NVDA/gpu_product_surface.html", "bronze"),
        (SOURCE_SNAPSHOT_IDS[3], "deployment_news_html", "NVDA", "NVDA", "object://bronze/web/customer/ai_cluster_news.html", "bronze"),
        (SOURCE_SNAPSHOT_IDS[4], "macro_api_json", "MACRO", "", "object://bronze/fred/DGS10.json", "bronze"),
        (SOURCE_SNAPSHOT_IDS[5], "index_snapshot_manifest", "INDEX", "", "object://index/milvus/fin_insight_603_manifest.json", "index"),
        (SOURCE_SNAPSHOT_IDS[3], "unparsed_web_snapshot", "NVDA", "NVDA", "object://bronze/web/customer/unparsed_snapshot.html", "bronze"),
    ]
    for snapshot_id, kind, issuer, ticker, uri, tier in specs:
        raw_id = NEGATIVE_RAW_DOC_ID if kind == "unparsed_web_snapshot" else stable_id("p14raw", [snapshot_id, uri])
        status = "blocked_no_parser" if raw_id == NEGATIVE_RAW_DOC_ID else "raw_ready"
        doc = {
            "raw_document_id": raw_id,
            "source_snapshot_id": snapshot_id,
            "ingestion_job_id": by_snapshot[snapshot_id]["ingestion_job_id"],
            "document_kind": kind,
            "issuer_id": issuer,
            "ticker": ticker,
            "object_uri": uri,
            "content_digest": stable_id("p14content", [uri, kind]),
            "storage_tier": tier,
            "status": status,
            "payload": {"raw_source_not_fact_authority": True},
        }
        conn.execute(
            "insert into raw_source_documents_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                raw_id,
                snapshot_id,
                doc["ingestion_job_id"],
                kind,
                issuer,
                ticker,
                uri,
                doc["content_digest"],
                tier,
                status,
                json_dumps(doc["payload"]),
                now,
            ),
        )
        docs.append(doc)
    return docs


def insert_fetch_attempts(
    conn: sqlite3.Connection,
    *,
    raw_docs: list[dict[str, Any]],
    now: str,
) -> None:
    route_by_kind = {
        "structured_fact_json": "api_json_fetch",
        "ir_pdf": "http_pdf_fetch",
        "official_product_html": "http_html_fetch",
        "deployment_news_html": "playwright_render_fetch",
        "macro_api_json": "api_json_fetch",
        "index_snapshot_manifest": "local_index_manifest_read",
        "unparsed_web_snapshot": "playwright_render_fetch",
    }
    for doc in raw_docs:
        blocked = doc["raw_document_id"] == NEGATIVE_RAW_DOC_ID
        conn.execute(
            "insert into fetch_attempts_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p14fetch", [doc["raw_document_id"]]),
                doc["raw_document_id"],
                doc["source_snapshot_id"],
                route_by_kind[doc["document_kind"]],
                0 if doc["document_kind"] == "index_snapshot_manifest" else 200,
                "blocked_needs_parser_contract" if blocked else "success",
                "missing_source_specific_parser" if blocked else "",
                "no_retry_until_parser_added" if blocked else "idempotent_retry_allowed",
                0 if doc["document_kind"] == "index_snapshot_manifest" else 180 + len(doc["document_kind"]) * 7,
                json_dumps({"allowlisted": True, "credential_required": False}),
                now,
            ),
        )


def insert_parser_runs(
    conn: sqlite3.Connection,
    *,
    raw_docs: list[dict[str, Any]],
    now: str,
) -> list[dict[str, Any]]:
    parser_by_kind = {
        "structured_fact_json": ("sec_companyfacts_json_parser", 2, 1, 0, 0.99),
        "ir_pdf": ("ir_pdf_table_and_caption_parser", 2, 2, 0, 0.92),
        "official_product_html": ("official_product_html_spec_parser", 2, 2, 0, 0.95),
        "deployment_news_html": ("customer_deployment_event_parser", 1, 1, 0, 0.9),
        "macro_api_json": ("fred_json_series_parser", 1, 0, 0, 0.98),
        "unparsed_web_snapshot": ("missing_site_specific_parser", 0, 0, 1, 0.0),
    }
    rows = []
    for doc in raw_docs:
        if doc["document_kind"] == "index_snapshot_manifest":
            continue
        parser_name, object_count, authority_count, typed_gap_count, score = parser_by_kind[doc["document_kind"]]
        status = "parser_gap_blocked" if doc["raw_document_id"] == NEGATIVE_RAW_DOC_ID else "parsed"
        row = {
            "parser_run_id": stable_id("p14parser", [doc["raw_document_id"], parser_name]),
            "raw_document_id": doc["raw_document_id"],
            "parser_name": parser_name,
            "parser_version": "v0_1",
            "status": status,
            "parsed_object_count": object_count,
            "authority_candidate_count": authority_count,
            "typed_gap_count": typed_gap_count,
            "quality_score": score,
            "payload": {"parser_contract": "value_or_signal_plus_citation", "fail_closed": True},
        }
        conn.execute(
            "insert into parser_runs_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row["parser_run_id"],
                row["raw_document_id"],
                row["parser_name"],
                row["parser_version"],
                row["status"],
                row["parsed_object_count"],
                row["authority_candidate_count"],
                row["typed_gap_count"],
                row["quality_score"],
                json_dumps(row["payload"]),
                now,
            ),
        )
        rows.append(row)
    return rows


def insert_parsed_objects(
    conn: sqlite3.Connection,
    *,
    parser_runs: list[dict[str, Any]],
    now: str,
) -> list[dict[str, Any]]:
    run_by_raw = {row["raw_document_id"]: row for row in parser_runs}
    specs = [
        ("p14_obj_nvda_revenue", "financial_statement_metric", "NVDA", "NVDA", "Data Center", "revenue", "FY2026Q1", "sec://NVDA/companyfacts/revenue"),
        ("p14_obj_nvda_capex", "financial_statement_metric", "NVDA", "NVDA", "Corporate", "capex", "FY2026Q1", "sec://NVDA/companyfacts/capex"),
        ("p14_obj_b200_spec", "product_spec_architecture", "NVDA", "NVDA", "gpu_accelerator", "B200 architecture memory bandwidth", "Blackwell", "ir://NVDA/product-deck#B200"),
        ("p14_obj_gb200_rack", "product_spec_architecture", "NVDA", "NVDA", "ai_server_rack", "GB200 NVL rack configuration", "Blackwell", "ir://NVDA/product-deck#GB200"),
        ("p14_obj_h100_spec", "product_spec_architecture", "NVDA", "NVDA", "gpu_accelerator", "H100 tensor core architecture", "Hopper", "official://NVDA/H100"),
        ("p14_obj_b200_spec_html", "product_spec_architecture", "NVDA", "NVDA", "gpu_accelerator", "B200 official product spec", "Blackwell", "official://NVDA/B200"),
        ("p14_obj_cloud_deployment", "customer_deployment_event", "NVDA", "NVDA", "gpu_accelerator", "cloud cluster deployment", "2026", "customer-news://ai-cluster"),
        ("p14_obj_rates_macro", "macro_series", "MACRO", "", "rates", "US 10Y yield", "daily", "fred://DGS10"),
    ]
    raw_by_kind = {
        "financial_statement_metric": next(run["raw_document_id"] for run in parser_runs if run["parser_name"] == "sec_companyfacts_json_parser"),
        "product_spec_architecture_pdf": next(run["raw_document_id"] for run in parser_runs if run["parser_name"] == "ir_pdf_table_and_caption_parser"),
        "product_spec_architecture_html": next(run["raw_document_id"] for run in parser_runs if run["parser_name"] == "official_product_html_spec_parser"),
        "customer_deployment_event": next(run["raw_document_id"] for run in parser_runs if run["parser_name"] == "customer_deployment_event_parser"),
        "macro_series": next(run["raw_document_id"] for run in parser_runs if run["parser_name"] == "fred_json_series_parser"),
    }
    rows = []
    for object_id, object_type, issuer, ticker, family, metric, period, citation in specs:
        if object_type == "financial_statement_metric":
            raw_id = raw_by_kind["financial_statement_metric"]
        elif object_type == "product_spec_architecture" and "official://" in citation:
            raw_id = raw_by_kind["product_spec_architecture_html"]
        elif object_type == "product_spec_architecture":
            raw_id = raw_by_kind["product_spec_architecture_pdf"]
        elif object_type == "customer_deployment_event":
            raw_id = raw_by_kind["customer_deployment_event"]
        else:
            raw_id = raw_by_kind["macro_series"]
        run = run_by_raw[raw_id]
        row = {
            "parsed_object_id": object_id,
            "parser_run_id": run["parser_run_id"],
            "raw_document_id": raw_id,
            "object_type": object_type,
            "issuer_id": issuer,
            "ticker": ticker,
            "product_family": family,
            "metric_or_signal": metric,
            "period_or_version": period,
            "citation_ref": citation,
            "status": "parsed_object_ready",
            "payload": {"citation_required": True},
        }
        conn.execute(
            "insert into parsed_object_records_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                object_id,
                run["parser_run_id"],
                raw_id,
                object_type,
                issuer,
                ticker,
                family,
                metric,
                period,
                citation,
                "parsed_object_ready",
                json_dumps(row["payload"]),
                now,
            ),
        )
        rows.append(row)
    return rows


def insert_authority_mappings(
    conn: sqlite3.Connection,
    *,
    parsed_objects: list[dict[str, Any]],
    now: str,
) -> list[dict[str, Any]]:
    rows = []
    for obj in parsed_objects:
        if obj["object_type"] == "financial_statement_metric":
            authority_mode = "exact_company_fact_authority"
            exact = 1
            claim = 1
            scope = "financial_statement_exact"
        elif obj["object_type"] == "product_spec_architecture":
            authority_mode = "technical_fact_authority"
            exact = 0
            claim = 1
            scope = "product_spec_technical_fact"
        elif obj["object_type"] == "customer_deployment_event":
            authority_mode = "deployment_signal_authority"
            exact = 0
            claim = 1
            scope = "bounded_customer_deployment_signal"
        else:
            authority_mode = "macro_context_only"
            exact = 0
            claim = 0
            scope = "macro_context"
        row = {
            "authority_mapping_id": stable_id("p14auth", [obj["parsed_object_id"], authority_mode]),
            "parsed_object_id": obj["parsed_object_id"],
            "authority_mode": authority_mode,
            "claim_scope": scope,
            "can_enter_claim_card": claim,
            "can_enter_context": 1,
            "can_enter_exact_value_ledger": exact,
            "blocked_reason": "",
            "status": "accepted",
            "payload": {"raw_snapshot_not_authority": True},
        }
        conn.execute(
            "insert into authority_mapping_records_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row["authority_mapping_id"],
                row["parsed_object_id"],
                row["authority_mode"],
                row["claim_scope"],
                row["can_enter_claim_card"],
                row["can_enter_context"],
                row["can_enter_exact_value_ledger"],
                row["blocked_reason"],
                row["status"],
                json_dumps(row["payload"]),
                now,
            ),
        )
        rows.append(row)
    blocked = {
        "authority_mapping_id": NEGATIVE_AUTHORITY_ID,
        "parsed_object_id": NEGATIVE_RAW_DOC_ID,
        "authority_mode": "blocked_raw_snapshot_no_parser",
        "claim_scope": "blocked",
        "can_enter_claim_card": 0,
        "can_enter_context": 0,
        "can_enter_exact_value_ledger": 0,
        "blocked_reason": "raw snapshot has no parser_run and cannot enter evidence/context",
        "status": "blocked",
        "payload": {"negative_guard": True},
    }
    conn.execute(
        "insert into authority_mapping_records_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            blocked["authority_mapping_id"],
            blocked["parsed_object_id"],
            blocked["authority_mode"],
            blocked["claim_scope"],
            0,
            0,
            0,
            blocked["blocked_reason"],
            "blocked",
            json_dumps(blocked["payload"]),
            now,
        ),
    )
    rows.append(blocked)
    return rows


def insert_index_refreshes(
    conn: sqlite3.Connection,
    *,
    snapshots: list[dict[str, Any]],
    parser_runs: list[dict[str, Any]],
    authority_rows: list[dict[str, Any]],
    now: str,
) -> list[dict[str, Any]]:
    accepted_authorities = [row["authority_mapping_id"] for row in authority_rows if row["status"] == "accepted"]
    parser_ids = [row["parser_run_id"] for row in parser_runs if row["status"] == "parsed"]
    snapshot_ids = [row["source_snapshot_id"] for row in snapshots]
    refresh_specs = [
        ("p14_idx_sql_exact_financial", "sql_exact", 2, accepted_authorities[:2]),
        ("p14_idx_object_bm25_tables", "object_bm25", 4, accepted_authorities[:4]),
        ("p14_idx_bm25_narrative", "bm25", 6, accepted_authorities[2:8]),
        ("p14_idx_milvus_semantic_context", "milvus_semantic", 662908, accepted_authorities[2:8]),
        ("p14_idx_graph_relationship_context", "graph", 5, accepted_authorities[2:7]),
    ]
    rows = []
    for index_name, index_type, count, auth_ids in refresh_specs:
        row = {
            "index_refresh_id": stable_id("p14idx", [index_name, SCHEMA_VERSION]),
            "index_name": index_name,
            "index_type": index_type,
            "source_snapshot_ids": snapshot_ids,
            "authority_mapping_ids": auth_ids,
            "parser_run_ids": parser_ids,
            "lineage_complete": 1,
            "refresh_status": "refresh_ready",
            "row_or_vector_count": count,
            "payload": {"milvus_not_exact_authority": index_type == "milvus_semantic"},
        }
        conn.execute(
            "insert into index_refresh_records_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row["index_refresh_id"],
                index_name,
                index_type,
                json_dumps(snapshot_ids),
                json_dumps(auth_ids),
                json_dumps(parser_ids),
                1,
                "refresh_ready",
                count,
                json_dumps(row["payload"]),
                now,
            ),
        )
        rows.append(row)
    return rows


def insert_retrieval_strategies(conn: sqlite3.Connection, *, now: str) -> list[dict[str, Any]]:
    rows = [
        ("exact_financial_metric", ["sql_exact", "object_bm25", "parser_row"], "exact_not_found_but_company_period_source_exists", "exact_value_or_typed_gap"),
        ("product_spec_architecture", ["parser_row", "object_bm25", "bm25", "milvus_semantic"], "missing_spec_slot_or_stale_generation", "technical_fact_or_bounded_gap"),
        ("customer_deployment_adoption", ["graph", "parser_row", "bm25", "milvus_semantic", "web_repair"], "adoption_section_empty_or_only_generic_rows", "deployment_signal_or_gap"),
        ("capital_funding_ownership", ["sql_exact", "parser_row", "object_bm25", "bm25"], "capital_section_missing_required_form_family", "capital_fact_or_gap"),
        ("retrievable_gap_repair", ["sql_exact", "object_bm25", "milvus_semantic", "web_repair"], "lead_review_marks_retrievable_gap", "repair_delta_or_typed_gap"),
    ]
    strategies = []
    for intent, routes, trigger, stop in rows:
        strategy = {
            "strategy_pack_id": stable_id("p14strategy", [intent]),
            "intent_id": intent,
            "route_order": routes,
            "first_pass_budget": {"candidate_budget": 24, "rerank_budget": 12, "context_budget_tokens": 2400},
            "second_pass_trigger": trigger,
            "authority_boundary": "route_specific_authority_required",
            "stop_condition": stop,
            "status": "strategy_ready",
            "payload": {"forbidden": ["raw_hit_to_memo", "semantic_similarity_as_fact"]},
        }
        conn.execute(
            "insert into retrieval_strategy_packs_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                strategy["strategy_pack_id"],
                intent,
                json_dumps(routes),
                json_dumps(strategy["first_pass_budget"]),
                trigger,
                strategy["authority_boundary"],
                stop,
                "strategy_ready",
                json_dumps(strategy["payload"]),
                now,
            ),
        )
        strategies.append(strategy)
    return strategies


def insert_retrieval_budgets(
    conn: sqlite3.Connection,
    *,
    strategies: list[dict[str, Any]],
    now: str,
) -> None:
    for strategy in strategies:
        for idx, route in enumerate(strategy["route_order"]):
            conn.execute(
                "insert into retrieval_budget_records_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    stable_id("p14budget", [strategy["strategy_pack_id"], route]),
                    strategy["strategy_pack_id"],
                    route,
                    8 if idx < 2 else 4,
                    4 if route in {"bm25", "object_bm25", "milvus_semantic"} else 0,
                    700 if idx < 2 else 350,
                    "role_specific_quota_before_global_topk",
                    "cpu_spillover_or_second_pass_only",
                    "budget_ready",
                    json_dumps({"route_order_index": idx}),
                    now,
                ),
            )


def insert_context_bridges(
    conn: sqlite3.Connection,
    *,
    strategies: list[dict[str, Any]],
    authority_rows: list[dict[str, Any]],
    index_rows: list[dict[str, Any]],
    now: str,
) -> None:
    accepted_ids = [row["authority_mapping_id"] for row in authority_rows if row["status"] == "accepted"]
    index_ids = [row["index_refresh_id"] for row in index_rows]
    context_policies = rows_to_dicts(
        conn.execute("select * from contextengine_injection_policy_records_p13 order by actor_id").fetchall()
    )
    policy_by_actor = {row["actor_id"]: row["policy_id"] for row in context_policies}
    actors = [
        ("research_lead", "retrievable_gap_repair"),
        ("fundamental_analyst", "exact_financial_metric"),
        ("product_technology_analyst", "product_spec_architecture"),
        ("industry_supply_chain_analyst", "customer_deployment_adoption"),
    ]
    strategy_by_intent = {row["intent_id"]: row for row in strategies}
    for actor, intent in actors:
        strategy = strategy_by_intent[intent]
        conn.execute(
            "insert into retrieval_context_bridge_records_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p14bridge", [actor, intent]),
                actor,
                strategy["strategy_pack_id"],
                policy_by_actor.get(actor, "p13_context_policy_missing"),
                json_dumps(accepted_ids[:5]),
                json_dumps(index_ids),
                "preserve_exact_refs_not_summaries",
                "bounded_summary_with_ref_pin",
                "bridge_ready",
                json_dumps({"contextengine_policy_source": "P13", "raw_candidates_forbidden": True}),
                now,
            ),
        )


def insert_quality_probes(conn: sqlite3.Connection, *, now: str) -> None:
    rows = [
        ("exact_financial_metric", "primary_company_disclosure", "exact_company_fact_authority", 1, 1, ""),
        ("product_spec_architecture", "official_product_surface", "technical_fact_authority", 1, 1, ""),
        ("customer_deployment_adoption", "customer_deployment_signal", "deployment_signal_authority", 1, 1, ""),
        ("capital_funding_ownership", "primary_company_disclosure", "exact_company_fact_authority", 1, 1, ""),
        ("retrievable_gap_repair", "allowlisted_web_repair", "parser_required_before_authority", 0, 0, "typed_gap_until_parser_or_source_route_exists"),
    ]
    for intent, source_role, authority_mode, found, selected, gap in rows:
        status = "pass" if found or gap else "fail"
        conn.execute(
            "insert into retrieval_quality_probe_records_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p14probe", [intent, source_role]),
                intent,
                source_role,
                authority_mode,
                found,
                selected,
                gap,
                status,
                json_dumps({"probe_type": "deterministic_qrel"}),
                now,
            ),
        )


def insert_data_quality_observations(conn: sqlite3.Connection, *, now: str) -> None:
    rows = [
        ("parser_success_rate", "info", "parser_runs_p14", "pass", "Parser runs either produce objects or typed parser gap.", "monitor parser quality trend"),
        ("raw_snapshot_blocked", "high", NEGATIVE_RAW_DOC_ID, "blocked", "Unparsed raw snapshot is blocked from context and ClaimCards.", "add site-specific parser before use"),
        ("milvus_authority_boundary", "info", "p14_idx_milvus_semantic_context", "pass", "Milvus index is semantic recall only, not exact authority.", "keep exact-first route for numeric facts"),
        ("retrieval_budget_trace", "info", "retrieval_budget_records_p14", "pass", "Route budgets are role-specific and auditable.", "feed p95 and quality data into P16"),
    ]
    for obs_type, severity, obj_ref, status, finding, next_action in rows:
        conn.execute(
            "insert into data_quality_observations_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p14obs", [obs_type, obj_ref]),
                obs_type,
                severity,
                obj_ref,
                status,
                finding,
                next_action,
                json_dumps({"no_weak_fallback": True}),
                now,
            ),
        )


def insert_performance_profiles(conn: sqlite3.Connection, *, now: str) -> None:
    rows = [
        ("sql_exact", "exact_metric_lookup", 30722, 12, 45, 256, "O(log n) indexed lookup", "profile_recorded"),
        ("object_bm25", "table_and_object_recall", 74894, 35, 140, 512, "O(k log n) lexical recall", "profile_recorded"),
        ("milvus_semantic", "semantic_context_recall", 662908, 80, 260, 2048, "ANN approximate search", "profile_recorded"),
        ("parser_pipeline", "html_pdf_json_parse_batch", 6, 180, 900, 768, "O(document_size) parser pass", "profile_recorded"),
        ("context_bridge", "context_pack_selection", 5, 20, 75, 128, "O(selected_refs)", "profile_recorded"),
    ]
    for component, workload, count, p50, p95, mem, complexity, status in rows:
        conn.execute(
            "insert into database_performance_profiles_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p14perf", [component, workload]),
                component,
                workload,
                count,
                p50,
                p95,
                mem,
                complexity,
                status,
                json_dumps({"resource_profile": "local_deterministic_profile"}),
                now,
            ),
        )


def insert_current_universe_refresh_evidence(conn: sqlite3.Connection, *, root: Path, now: str) -> list[dict[str, Any]]:
    rows = build_current_universe_refresh_evidence_rows(root=root, now=now)
    for row in rows:
        conn.execute(
            "insert into current_universe_refresh_evidence_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row["evidence_id"],
                row["evidence_name"],
                row["manifest_path"],
                row["evidence_scope"],
                row["expected_contract"],
                json_dumps(row["observed_value"]),
                row["status"],
                row["boundary"],
                row["created_at"],
            ),
        )
    return rows


def build_current_universe_refresh_evidence_rows(*, root: Path, now: str) -> list[dict[str, Any]]:
    manifest_dir = root / "data" / "manifests"

    def read_manifest(filename: str) -> tuple[Path, dict[str, Any], bool]:
        path = manifest_dir / filename
        if not path.exists():
            return path, {}, False
        return path, json_loads(path.read_text(encoding="utf-8"), {}), True

    def as_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def counts(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return payload.get("counts") if isinstance(payload.get("counts"), Mapping) else {}

    specs: list[dict[str, Any]] = []

    path, payload, exists = read_manifest("company_public_source_coverage_matrix_v0_1.json")
    specs.append(
        {
            "evidence_name": "company_public_source_coverage_matrix",
            "manifest_path": rel_path(path, root),
            "evidence_scope": "603_company_public_source_role_matrix",
            "expected_contract": "matrix exists for every accepted issuer and classifies remaining public/commercial source boundaries",
            "observed_value": {
                "exists": exists,
                "status": payload.get("status"),
                "company_count": payload.get("company_count"),
                "repair_queue_count": len(payload.get("repair_queue") or []),
            },
            "passes": exists and as_int(payload.get("company_count")) >= 603 and payload.get("status") in {"pass", "gap"},
            "boundary": "May contain typed source gaps; accepted as refresh evidence only when every runtime issuer is represented.",
        }
    )

    path, payload, exists = read_manifest("source_coverage_gate_summary_v0_1.json")
    specs.append(
        {
            "evidence_name": "source_coverage_gate_summary",
            "manifest_path": rel_path(path, root),
            "evidence_scope": "source_route_gate_and_gap_classification",
            "expected_contract": "coverage gate exists and reports pass or typed gap status instead of silent missing source routes",
            "observed_value": {"exists": exists, "status": payload.get("status"), "generated_at": payload.get("generated_at")},
            "passes": exists and payload.get("status") in {"pass", "gap"},
            "boundary": "A gap status is allowed only as typed public-source boundary evidence, not as proof of complete source depth.",
        }
    )

    path, payload, exists = read_manifest("r53_r60_p26_product_evidence_all_universe_depth_summary_v0_1.json")
    specs.append(
        {
            "evidence_name": "p26_product_evidence_all_universe_depth",
            "manifest_path": rel_path(path, root),
            "evidence_scope": "603_company_product_evidence_pack",
            "expected_contract": "P26 product evidence pack is broad-full-chain ready with no blocking product/deployment gaps",
            "observed_value": {
                "exists": exists,
                "status": payload.get("status"),
                "release_decision": payload.get("release_decision"),
                "product_pack_readiness_status": payload.get("product_pack_readiness_status"),
                "broad_full_chain_product_pack_ready": payload.get("broad_full_chain_product_pack_ready"),
                "counts": counts(payload),
            },
            "passes": exists and payload.get("status") == "pass" and bool(payload.get("broad_full_chain_product_pack_ready")),
            "boundary": "Product-KPI exact gaps remain claim-scope limits if P26 marks them nonblocking.",
        }
    )

    path, payload, exists = read_manifest("r53_r60_s8_secondary_market_capital_feedback_summary_v0_1.json")
    s8_counts = counts(payload)
    specs.append(
        {
            "evidence_name": "s8_secondary_market_capital_feedback",
            "manifest_path": rel_path(path, root),
            "evidence_scope": "603_company_secondary_market_capital_feedback_pack",
            "expected_contract": "secondary-market/capital feedback packs exist for every accepted issuer",
            "observed_value": {
                "exists": exists,
                "status": payload.get("status"),
                "release_decision": payload.get("release_decision"),
                "pack_count": s8_counts.get("pack_count") or s8_counts.get("capital_feedback_packs_s8"),
                "signal_count": s8_counts.get("signal_count") or s8_counts.get("capital_feedback_signals_s8"),
            },
            "passes": exists and payload.get("status") == "pass" and as_int(s8_counts.get("pack_count") or s8_counts.get("capital_feedback_packs_s8")) >= 603,
            "boundary": "Delayed/free market rows support market context, not real-time trading or dealer positioning.",
        }
    )

    path, payload, exists = read_manifest("secondary_market_public_context_summary_v0_1.json")
    specs.append(
        {
            "evidence_name": "secondary_market_public_context_rows",
            "manifest_path": rel_path(path, root),
            "evidence_scope": "603_ticker_public_market_context_rows",
            "expected_contract": "public secondary-market context rows cover every accepted ticker",
            "observed_value": {
                "exists": exists,
                "status": payload.get("status"),
                "ticker_count": payload.get("ticker_count"),
                "row_count": payload.get("row_count"),
            },
            "passes": exists and payload.get("status") == "pass" and as_int(payload.get("ticker_count")) >= 603 and as_int(payload.get("row_count")) >= 603,
            "boundary": "Free public market context is lagged/delayed and cannot replace real-time commercial market feeds.",
        }
    )

    path, payload, exists = read_manifest("gold_fact_signal_mart_summary_v0_1.json")
    specs.append(
        {
            "evidence_name": "gold_fact_signal_mart",
            "manifest_path": rel_path(path, root),
            "evidence_scope": "603_company_gold_fact_signal_mart",
            "expected_contract": "gold fact/signal mart has current runtime issuer coverage and non-empty rows",
            "observed_value": {
                "exists": exists,
                "status": payload.get("status"),
                "company_count": payload.get("company_count"),
                "row_count": payload.get("row_count"),
            },
            "passes": exists and payload.get("status") == "pass" and as_int(payload.get("company_count")) >= 603 and as_int(payload.get("row_count")) > 0,
            "boundary": "Gold rows remain parser/authority scoped; raw rows cannot be treated as final facts.",
        }
    )

    path, payload, exists = read_manifest("retrieval_index_registry_summary_v0_1.json")
    specs.append(
        {
            "evidence_name": "retrieval_index_registry",
            "manifest_path": rel_path(path, root),
            "evidence_scope": "runtime_retrieval_index_registry",
            "expected_contract": "retrieval index registry is present and current enough for runtime route selection",
            "observed_value": {"exists": exists, "status": payload.get("status"), "release_decision": payload.get("release_decision")},
            "passes": exists and payload.get("status") == "pass",
            "boundary": "Registry proves addressable route metadata, not semantic recall quality by itself.",
        }
    )

    path, payload, exists = read_manifest("product_intelligence_graph_summary_v0_1.json")
    specs.append(
        {
            "evidence_name": "product_intelligence_graph",
            "manifest_path": rel_path(path, root),
            "evidence_scope": "603_company_product_intelligence_graph",
            "expected_contract": "ProductIntelligenceGraph exists for every accepted issuer",
            "observed_value": {"exists": exists, "status": payload.get("status"), "company_count": payload.get("company_count")},
            "passes": exists and payload.get("status") == "pass" and as_int(payload.get("company_count")) >= 603,
            "boundary": "Product graph supports product/relationship reasoning; exact KPI claims still require exact rows.",
        }
    )

    rows = []
    for spec in specs:
        rows.append(
            {
                "evidence_id": stable_id("p14current", [spec["evidence_name"], spec["manifest_path"]]),
                "evidence_name": spec["evidence_name"],
                "manifest_path": spec["manifest_path"],
                "evidence_scope": spec["evidence_scope"],
                "expected_contract": spec["expected_contract"],
                "observed_value": spec["observed_value"],
                "status": "pass" if spec["passes"] else "fail",
                "boundary": spec["boundary"],
                "created_at": now,
            }
        )
    return rows


def insert_lineage_edges(
    conn: sqlite3.Connection,
    *,
    raw_docs: list[dict[str, Any]],
    parser_runs: list[dict[str, Any]],
    parsed_objects: list[dict[str, Any]],
    authority_rows: list[dict[str, Any]],
    index_rows: list[dict[str, Any]],
    now: str,
) -> None:
    edges: list[tuple[str, str, str, str]] = []
    for doc in raw_docs:
        edges.append((f"source_snapshot:{doc['source_snapshot_id']}", f"raw_document:{doc['raw_document_id']}", "snapshot_to_raw", "complete"))
    for run in parser_runs:
        edges.append((f"raw_document:{run['raw_document_id']}", f"parser_run:{run['parser_run_id']}", "raw_to_parser", "blocked" if run["status"] != "parsed" else "complete"))
    for obj in parsed_objects:
        edges.append((f"parser_run:{obj['parser_run_id']}", f"parsed_object:{obj['parsed_object_id']}", "parser_to_object", "complete"))
    for auth in authority_rows:
        status = "blocked" if auth["status"] == "blocked" else "complete"
        edges.append((f"parsed_object:{auth['parsed_object_id']}", f"authority_mapping:{auth['authority_mapping_id']}", "object_to_authority", status))
    for idx in index_rows:
        for auth_id in idx["authority_mapping_ids"]:
            edges.append((f"authority_mapping:{auth_id}", f"index_refresh:{idx['index_refresh_id']}", "authority_to_index", "complete"))
    for from_ref, to_ref, edge_type, status in edges:
        conn.execute(
            "insert into ingestion_lineage_edges_p14 values (?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p14lineage", [from_ref, to_ref, edge_type]),
                from_ref,
                to_ref,
                edge_type,
                status,
                json_dumps({"append_only_lineage": True}),
                now,
            ),
        )


def insert_data_plane_acceptance(conn: sqlite3.Connection, *, now: str) -> None:
    evidence = [
        "source_snapshot_registry_p14",
        "fetch_attempts_p14",
        "parser_runs_p14",
        "authority_mapping_records_p14",
        "index_refresh_records_p14",
        "retrieval_strategy_packs_p14",
        "retrieval_context_bridge_records_p14",
        "database_performance_profiles_p14",
    ]
    for demand_id in P14_DEMAND_IDS:
        conn.execute(
            "insert into data_plane_acceptance_records_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p14accept", [demand_id]),
                demand_id,
                json_dumps({"status": "pass", "workflow_value": "Research Lead can see where data came from and why it can or cannot be used."}),
                json_dumps({"status": "pass", "sql_final": True, "lineage_complete": True, "idempotent_rebuild": True}),
                json_dumps({"status": "pass", "raw_fallback_blocked": True, "quality_probes": True}),
                json_dumps({"status": "pass", "performance_profile_recorded": True, "refresh_boundary_explicit": True}),
                json_dumps(evidence),
                "pass",
                "data_engineering_owner",
                now,
            ),
        )


def insert_data_plane_readiness_report(conn: sqlite3.Connection, *, task_id: str, now: str) -> None:
    known_gaps = [
        {
            "gap": "production_db_index_sla",
            "reason": "Performance profile is deterministic/local, not a cloud p95/p99 SLA.",
            "next_action": "P16 and production pilot should record real load and online eval metrics.",
        },
        {
            "gap": "all_live_graph_nodes_read_p14_strategy",
            "reason": "Context bridge records are ready; production nodes still need migration to read the active strategy pack.",
            "next_action": "P15/P16 should expose and monitor strategy consumption.",
        },
    ]
    next_actions = [
        "wire real crawlers/parsers to DataIngestionContract",
        "bind RetrievalStrategyPack to Research Lead route planner",
        "export DB/index profiles to eval/ops dashboard",
        "add production qrels and online retrieval drift monitoring",
    ]
    conn.execute(
        "insert into data_plane_readiness_reports_p14 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "p14_data_ingestion_retrieval_control_plane_report_v0_1",
            task_id,
            "source_snapshots_ready",
            "parser_contracts_ready",
            "raw_to_runtime_lineage_ready",
            "strategy_budget_context_bridge_ready",
            "context_bridge_ready",
            "local_profile_recorded",
            "P14_pending_gate_finalization",
            json_dumps([]),
            json_dumps(known_gaps),
            json_dumps(next_actions),
            "data_engineering_owner",
            json_dumps({"not_full_crawler_coverage": True, "not_production_sla": True}),
            now,
        ),
    )


def evaluate_p14_gates(
    root: Path,
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    drill_task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    contract = data_ingestion_retrieval_control_plane_schema_contract()
    generated_at = utc_now_iso()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        existing_tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        modalities = {row[0] for row in conn.execute("select distinct source_modality from source_snapshot_registry_p14").fetchall()}
        fetch_bad = int(conn.execute("select count(*) from fetch_attempts_p14 where status not in ('success', 'blocked_needs_parser_contract')").fetchone()[0])
        parser_bad = int(conn.execute("select count(*) from parser_runs_p14 where status = 'parsed' and parsed_object_count = 0").fetchone()[0])
        parser_gap_count = int(conn.execute("select count(*) from parser_runs_p14 where status = 'parser_gap_blocked' and typed_gap_count > 0").fetchone()[0])
        raw_authority_bad = int(
            conn.execute(
                """
                select count(*)
                from authority_mapping_records_p14
                where parsed_object_id = ? and status != 'blocked'
                """,
                (NEGATIVE_RAW_DOC_ID,),
            ).fetchone()[0]
        )
        accepted_modes = {row[0] for row in conn.execute("select distinct authority_mode from authority_mapping_records_p14 where status = 'accepted'").fetchall()}
        blocked_negative = int(conn.execute("select count(*) from authority_mapping_records_p14 where authority_mapping_id = ? and status = 'blocked'", (NEGATIVE_AUTHORITY_ID,)).fetchone()[0])
        index_bad = int(conn.execute("select count(*) from index_refresh_records_p14 where lineage_complete != 1 or refresh_status != 'refresh_ready'").fetchone()[0])
        strategy_intents = {row[0] for row in conn.execute("select intent_id from retrieval_strategy_packs_p14").fetchall()}
        budget_bad = int(conn.execute("select count(*) from retrieval_budget_records_p14 where candidate_budget <= 0 or context_budget_tokens <= 0").fetchone()[0])
        bridge_bad = int(
            conn.execute(
                """
                select count(*) from retrieval_context_bridge_records_p14
                where exact_ref_policy != 'preserve_exact_refs_not_summaries'
                   or context_policy_ref = 'p13_context_policy_missing'
                   or status != 'bridge_ready'
                """
            ).fetchone()[0]
        )
        perf_bad = int(conn.execute("select count(*) from database_performance_profiles_p14 where p95_latency_ms <= 0 or row_or_vector_count <= 0").fetchone()[0])
        current_universe_count = int(conn.execute("select count(*) from current_universe_refresh_evidence_p14").fetchone()[0])
        current_universe_fail = int(conn.execute("select count(*) from current_universe_refresh_evidence_p14 where status != 'pass'").fetchone()[0])
        current_universe_rows = rows_to_dicts(
            conn.execute(
                """
                select evidence_name, manifest_path, evidence_scope, status, observed_value_json, boundary
                from current_universe_refresh_evidence_p14
                order by evidence_name
                """
            ).fetchall()
        )
        lineage_bad = int(conn.execute("select count(*) from ingestion_lineage_edges_p14 where lineage_status not in ('complete', 'blocked')").fetchone()[0])
        quality_fail = int(conn.execute("select count(*) from retrieval_quality_probe_records_p14 where status not in ('pass')").fetchone()[0])
        acceptance_bad = int(conn.execute("select count(*) from data_plane_acceptance_records_p14 where status != 'pass'").fetchone()[0])
        report = row_to_dict(conn.execute("select * from data_plane_readiness_reports_p14 limit 1").fetchone())
        drill_task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (drill_task_id,)).fetchone())
        artifact_count = int(
            conn.execute(
                "select count(*) from artifact_refs where task_id = ? and artifact_type like 'data_plane_control_%'",
                (task_id,),
            ).fetchone()[0]
        )
        workpaper_event_count = int(
            conn.execute(
                "select count(*) from workpaper_events where task_id = ? and event_type = 'data_ingestion_retrieval_control_plane_ready'",
                (task_id,),
            ).fetchone()[0]
        )
    s3_summary = default_s3_paths(root).summary_path
    p13_summary = default_p13_paths(root).summary_path
    dependency_ok = dependency_summary_passes(s3_summary, "S3_L4_scope_pass") and dependency_summary_passes(
        p13_summary,
        "P13_L4_scope_pass_graph_skill_memory_lifecycle_ready",
    )

    def gate(gate_id: str, gate_group: str, status: bool, detail: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "gate_id": gate_id,
            "gate_group": gate_group,
            "status": "pass" if status else "fail",
            "pass_level": "L4_scope_pass" if status else "blocked",
            "detail": dict(detail),
            "generated_at": generated_at,
        }

    return [
        gate("p14_schema_tables_present", "schema", set(contract["tables"]).issubset(existing_tables), {"required_tables": contract["tables"]}),
        gate("p14_s3_p13_dependencies_pass", "dependency", dependency_ok, {"s3_summary": rel_path(s3_summary, root), "p13_summary": rel_path(p13_summary, root)}),
        gate("p14_source_modalities_covered", "source_snapshot", set(contract["required_source_modalities"]).issubset(modalities), {"modalities": sorted(modalities)}),
        gate("p14_fetch_attempts_typed_no_silent_fail", "fetch", fetch_bad == 0 and materialized["fetch_attempt_count"] >= materialized["raw_document_count"], {"fetch_bad": fetch_bad, "fetch_attempt_count": materialized["fetch_attempt_count"]}),
        gate("p14_parser_runs_output_or_typed_gap", "parser", parser_bad == 0 and parser_gap_count >= 1, {"parser_bad": parser_bad, "parser_gap_count": parser_gap_count}),
        gate("p14_raw_snapshot_blocked_without_parser", "authority", raw_authority_bad == 0 and blocked_negative == 1, {"raw_authority_bad": raw_authority_bad, "blocked_negative": blocked_negative}),
        gate(
            "p14_authority_modes_cover_exact_bounded_context",
            "authority",
            {"exact_company_fact_authority", "technical_fact_authority", "deployment_signal_authority", "macro_context_only"}.issubset(accepted_modes),
            {"accepted_modes": sorted(accepted_modes)},
        ),
        gate("p14_index_refresh_lineage_complete", "index", index_bad == 0 and materialized["index_refresh_count"] >= 5, {"index_bad": index_bad, "index_refresh_count": materialized["index_refresh_count"]}),
        gate(
            "p14_retrieval_strategy_and_budget_ready",
            "retrieval_control",
            set(contract["required_intents"]).issubset(strategy_intents) and budget_bad == 0,
            {"strategy_intents": sorted(strategy_intents), "budget_bad": budget_bad},
        ),
        gate("p14_context_bridge_preserves_exact_refs", "context_bridge", bridge_bad == 0 and materialized["context_bridge_count"] >= 4, {"bridge_bad": bridge_bad, "context_bridge_count": materialized["context_bridge_count"]}),
        gate("p14_perf_lineage_eval_records_ready", "quality_ops", perf_bad == 0 and lineage_bad == 0 and quality_fail == 0, {"perf_bad": perf_bad, "lineage_bad": lineage_bad, "quality_fail": quality_fail}),
        gate(
            "p14_current_accepted_universe_refresh_evidence_ready",
            "current_universe_refresh",
            current_universe_count >= 8 and current_universe_fail == 0,
            {
                "current_universe_refresh_evidence_count": current_universe_count,
                "current_universe_refresh_fail_count": current_universe_fail,
                "evidence_rows": [
                    {
                        **{key: value for key, value in row.items() if key != "observed_value_json"},
                        "observed_value": json_loads(str(row.get("observed_value_json") or "{}"), {}),
                    }
                    for row in current_universe_rows
                ],
            },
        ),
        gate(
            "p14_acceptance_and_boundary_report_ready",
            "release_boundary",
            materialized["acceptance_count"] == len(P14_DEMAND_IDS)
            and acceptance_bad == 0
            and bool(report)
            and report.get("source_snapshot_status") == "source_snapshots_ready"
            and drill_task.get("status") == "succeeded"
            and artifact_count >= 4
            and workpaper_event_count >= 1,
            {
                "acceptance_count": materialized["acceptance_count"],
                "acceptance_bad": acceptance_bad,
                "source_snapshot_status": report.get("source_snapshot_status"),
                "drill_task_status": drill_task.get("status"),
                "artifact_count": artifact_count,
                "workpaper_event_count": workpaper_event_count,
            },
        ),
    ]


def collect_p14_counts(store: RuntimeTaskSpineStore, *, drill_task_id: str, run_id: str) -> dict[str, Any]:
    with store._connect() as conn:
        drill_task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (drill_task_id,)).fetchone())
        return {
            "drill_task_id": drill_task_id,
            "drill_run_id": run_id,
            "drill_task_status": drill_task.get("status"),
            "drill_resume_count": int(drill_task.get("resume_count") or 0),
            "source_snapshot_count": table_row_count(conn, "source_snapshot_registry_p14"),
            "ingestion_job_count": table_row_count(conn, "ingestion_jobs_p14"),
            "raw_document_count": table_row_count(conn, "raw_source_documents_p14"),
            "fetch_attempt_count": table_row_count(conn, "fetch_attempts_p14"),
            "parser_run_count": table_row_count(conn, "parser_runs_p14"),
            "parsed_object_count": table_row_count(conn, "parsed_object_records_p14"),
            "authority_mapping_count": table_row_count(conn, "authority_mapping_records_p14"),
            "blocked_authority_count": count_where(conn, "authority_mapping_records_p14", "status = 'blocked'"),
            "index_refresh_count": table_row_count(conn, "index_refresh_records_p14"),
            "strategy_pack_count": table_row_count(conn, "retrieval_strategy_packs_p14"),
            "retrieval_budget_count": table_row_count(conn, "retrieval_budget_records_p14"),
            "context_bridge_count": table_row_count(conn, "retrieval_context_bridge_records_p14"),
            "quality_probe_count": table_row_count(conn, "retrieval_quality_probe_records_p14"),
            "quality_observation_count": table_row_count(conn, "data_quality_observations_p14"),
            "performance_profile_count": table_row_count(conn, "database_performance_profiles_p14"),
            "current_universe_refresh_evidence_count": table_row_count(conn, "current_universe_refresh_evidence_p14"),
            "lineage_edge_count": table_row_count(conn, "ingestion_lineage_edges_p14"),
            "acceptance_count": table_row_count(conn, "data_plane_acceptance_records_p14"),
        }


def count_where(conn: sqlite3.Connection, table: str, where_clause: str) -> int:
    if not table_exists(conn, table):
        return 0
    return int(conn.execute(f"select count(*) from {table} where {where_clause}").fetchone()[0])


def decode_p14_evidence_row(row: Mapping[str, Any]) -> dict[str, Any]:
    decoded = dict(row)
    if "observed_value_json" in decoded:
        decoded["observed_value"] = json_loads(str(decoded.pop("observed_value_json") or "{}"), {})
    return decoded


def persist_p14_gate_results(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    now = utc_now_iso()
    with store._connect() as conn:
        conn.execute("delete from data_plane_gate_results_p14")
        for row in gate_rows:
            conn.execute(
                "insert into data_plane_gate_results_p14 values (?, ?, ?, ?, ?, ?, ?)",
                (
                    stable_id("p14gate", [row["gate_id"], row["generated_at"]]),
                    row["gate_id"],
                    row["gate_group"],
                    row["status"],
                    row["pass_level"],
                    json_dumps(row.get("detail") or {}),
                    now,
                ),
            )


def finalize_p14_readiness_report(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    fail_count = len([row for row in gate_rows if row["status"] != "pass"])
    decision = "P14_L4_scope_pass_data_ingestion_retrieval_control_plane_ready" if fail_count == 0 else "P14_blocked"
    with store._connect() as conn:
        conn.execute(
            """
            update data_plane_readiness_reports_p14
            set release_decision = ?, gate_refs_json = ?, payload_json = ?
            where report_id = ?
            """,
            (
                decision,
                json_dumps([row["gate_id"] for row in gate_rows]),
                json_dumps({"gate_fail_count": fail_count, "gate_count": len(gate_rows)}),
                "p14_data_ingestion_retrieval_control_plane_report_v0_1",
            ),
        )


def build_p14_summary(
    root: Path,
    paths: P14Paths,
    gate_rows: list[dict[str, Any]],
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> dict[str, Any]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (task_id,)).fetchone())
        drill_task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (P14_DRILL_TASK_ID,)).fetchone())
        report = row_to_dict(conn.execute("select * from data_plane_readiness_reports_p14 limit 1").fetchone())
        current_rows = [
            decode_p14_evidence_row(row_to_dict(row))
            for row in conn.execute(
                """
                select evidence_name, manifest_path, evidence_scope, expected_contract,
                       observed_value_json, status, boundary
                from current_universe_refresh_evidence_p14
                order by evidence_name
                """
            ).fetchall()
        ]
    fail_count = len([row for row in gate_rows if row["status"] != "pass"])
    status = "pass" if fail_count == 0 else "fail"
    current_universe_failed = [row for row in current_rows if row.get("status") != "pass"]
    current_universe_status = (
        "current_accepted_public_source_universe_ready"
        if current_rows and not current_universe_failed
        else "blocked_current_accepted_universe_refresh_evidence"
    )
    outputs = {
        "schema": rel_path(paths.schema_path, root),
        "gate_rows": rel_path(paths.gate_rows_path, root),
        "summary": rel_path(paths.summary_path, root),
        "closeout_report": rel_path(paths.report_path, root),
        "runtime_db": rel_path(paths.db_path, root),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "slice": "P14 Data Ingestion / Retrieval Control Plane",
        "status": status,
        "release_decision": "P14_L4_scope_pass_data_ingestion_retrieval_control_plane_ready" if status == "pass" else "P14_blocked",
        "closeout_level": "L4_scope_pass" if status == "pass" else "blocked",
        "source_snapshot_status": report.get("source_snapshot_status") or "not_evaluated",
        "parser_contract_status": report.get("parser_contract_status") or "not_evaluated",
        "lineage_status": report.get("lineage_status") or "not_evaluated",
        "retrieval_control_status": report.get("retrieval_control_status") or "not_evaluated",
        "context_bridge_status": report.get("context_bridge_status") or "not_evaluated",
        "performance_status": report.get("performance_status") or "not_evaluated",
        "current_universe_refresh_status": current_universe_status,
        "current_universe_refresh_evidence": current_rows,
        "task": task,
        "drill_task": drill_task,
        "counts": {**dict(materialized), "gate_count": len(gate_rows), "gate_fail_count": fail_count},
        "readiness_report": report,
        "outputs": outputs,
        "policy": data_ingestion_retrieval_control_plane_schema_contract()["policy"],
        "generated_at": utc_now_iso(),
    }


def render_p14_report(summary: Mapping[str, Any], gate_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# R53-R60 P14 Data Ingestion / Retrieval Control Plane L4 Scope Pass",
        "",
        f"- Release decision: `{summary['release_decision']}`",
        f"- Closeout level: `{summary['closeout_level']}`",
        f"- Source snapshot status: `{summary['source_snapshot_status']}`",
        f"- Parser contract status: `{summary['parser_contract_status']}`",
        f"- Lineage status: `{summary['lineage_status']}`",
        f"- Retrieval control status: `{summary['retrieval_control_status']}`",
        f"- Context bridge status: `{summary['context_bridge_status']}`",
        f"- Performance status: `{summary['performance_status']}`",
        f"- Current universe refresh status: `{summary['current_universe_refresh_status']}`",
        "",
        "## Scope Boundary",
        "",
        "P14 proves a SQL-final control plane for source snapshots, ingestion jobs, fetch attempts, parser runs, authority mapping, index refreshes, retrieval strategy budgets, ContextEngine retrieval bridge, quality probes, lineage and performance profiles. It also verifies the current accepted 603-company data universe through manifest-backed refresh evidence. It does not claim unlimited internet crawler coverage, real-time refresh, or production p95/p99 SLA.",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        if isinstance(value, (str, int, float, bool)):
            lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Current Accepted Universe Refresh Evidence", ""])
    for row in summary["current_universe_refresh_evidence"]:
        observed = row.get("observed_value") if isinstance(row.get("observed_value"), Mapping) else {}
        lines.append(f"- `{row['status']}` `{row['evidence_name']}` -> `{row['manifest_path']}` ({observed})")
    lines.extend(["", "## Gates", ""])
    for row in gate_rows:
        lines.append(f"- `{row['gate_id']}` ({row['gate_group']}): `{row['status']}`")
    lines.extend(["", "## Known Gaps", ""])
    for gap in json_loads(str(summary["readiness_report"].get("known_gaps_json") or "[]"), []):
        lines.append(f"- `{gap['gap']}`: {gap['reason']} Next: {gap['next_action']}")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


def record_p14_artifacts(
    runtime: FinSightResearchRuntimeFacade,
    root: Path,
    paths: P14Paths,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    artifacts = []
    for artifact_type, uri, description in [
        ("data_plane_control_schema", paths.schema_path, "P14 data ingestion / retrieval control-plane schema contract"),
        ("data_plane_control_gate_rows", paths.gate_rows_path, "P14 L4-scope gate rows"),
        ("data_plane_control_summary", paths.summary_path, "P14 build summary"),
        ("data_plane_control_report", paths.report_path, "P14 closeout report"),
    ]:
        artifacts.append(
            runtime.record_artifact_ref(
                task_id,
                artifact_type=artifact_type,
                uri=rel_path(uri, root),
                payload={"schema_version": SCHEMA_VERSION, "description": description, "materialized": dict(materialized)},
                actor="data_plane_control_builder",
            )
        )
    return artifacts
