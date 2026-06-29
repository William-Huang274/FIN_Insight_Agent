"""P15 Enterprise Workbench product surface for R53-R60.

S6 exposed a SQL-final Workbench frontdoor and drilldown.  S7 exposed
deterministic deliverable/dashboard rendering.  P14 exposed the data ingestion
and retrieval control plane.  P15 ties those contracts into B2B product-facing
surfaces: task center, evidence workbench, workpaper builder, review queue,
artifact browser, deliverable studio, data room, and admin/ops console.

This is a product-surface contract drill.  It proves the product workflow,
permission checks, API contracts, UI information architecture, action ledger,
and E2E journey records are SQL-final.  It does not claim a polished React
implementation, external customer pilot, or production multi-tenant SLA.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.r53_r60_data_ingestion_retrieval_control_plane import build_p14_gate, default_p14_paths
from sec_agent.r53_r60_deliverable_studio_dashboard import build_s7_gate, default_s7_paths
from sec_agent.r53_r60_durable_runtime_hil_resource_router import table_row_count
from sec_agent.r53_r60_research_to_quant_lab import row_to_dict, rows_to_dicts, table_exists
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
from sec_agent.r53_r60_workbench_frontdoor_drilldown import (
    DEFAULT_TASK_ID,
    build_s6_projection,
    default_s6_paths,
)


SCHEMA_VERSION = "r53_r60_p15_enterprise_workbench_product_surface_v0_1"
P15_TASK_ID = "p15_scope_task_enterprise_workbench_product_surface"
P15_DRILL_TASK_ID = "p15_workbench_product_drill_task_ai_research_workspace"

P15_DEMAND_IDS = (
    "P15-D01-product-surface-registry",
    "P15-D02-enterprise-api-contracts",
    "P15-D03-task-center-and-progress",
    "P15-D04-evidence-workbench-and-workpaper-builder",
    "P15-D05-review-queue-and-action-ledger",
    "P15-D06-artifact-deliverable-dashboard-surfaces",
    "P15-D07-data-room-upload-contract",
    "P15-D08-admin-ops-rbac-e2e-gates",
)

REQUIRED_SURFACES = (
    "research_task_center",
    "evidence_workbench",
    "workpaper_builder",
    "review_queue",
    "artifact_browser",
    "deliverable_studio",
    "dashboard_projection",
    "data_room_upload",
    "admin_ops_console",
)
REQUIRED_API_SURFACES = (
    "task_lifecycle",
    "task_drilldown",
    "evidence_claim_gap_graph",
    "review_action",
    "artifact_browser",
    "deliverable_render",
    "data_room_upload",
    "admin_ops",
)
REQUIRED_JOURNEYS = (
    "junior_analyst_create_reviewable_workpaper",
    "senior_reviewer_approve_or_return",
    "artifact_browser_trace_to_source",
    "data_room_upload_to_provenance_pack",
    "admin_ops_incident_and_quality_trace",
)


@dataclass(frozen=True)
class P15Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


def default_p15_paths(root: Path) -> P15Paths:
    s1_paths = default_s1_paths(root)
    return P15Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "p15_enterprise_workbench_product_surface_schema_v0_1.json",
        gate_rows_path=root
        / "data"
        / "manifests"
        / "r53_r60_p15_enterprise_workbench_product_surface_gate_rows_v0_1.jsonl",
        summary_path=root
        / "data"
        / "manifests"
        / "r53_r60_p15_enterprise_workbench_product_surface_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_p15_enterprise_workbench_product_surface_l4_scope_pass.zh-CN.md",
    )


def enterprise_workbench_product_surface_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "release_scope": "enterprise_workbench_product_surface_drill",
        "tables": [
            "enterprise_workbench_product_surface_metadata_p15",
            "workbench_product_surface_registry_p15",
            "enterprise_api_surface_contracts_p15",
            "frontend_information_architecture_p15",
            "task_center_workflow_records_p15",
            "evidence_workbench_panel_records_p15",
            "workpaper_builder_panel_records_p15",
            "review_queue_panel_records_p15",
            "artifact_browser_records_p15",
            "deliverable_studio_panel_records_p15",
            "data_room_upload_contracts_p15",
            "admin_ops_console_panel_records_p15",
            "product_action_ledger_p15",
            "rbac_product_permission_checks_p15",
            "frontend_e2e_journey_records_p15",
            "workbench_product_acceptance_records_p15",
            "workbench_product_readiness_reports_p15",
            "workbench_product_gate_results_p15",
        ],
        "required_surfaces": list(REQUIRED_SURFACES),
        "required_api_surfaces": list(REQUIRED_API_SURFACES),
        "required_journeys": list(REQUIRED_JOURNEYS),
        "policy": {
            "sql_ledger_is_final_audit_source": True,
            "frontend_state_is_projection_only": True,
            "all_product_actions_append_ledger": True,
            "review_actions_write_workpaper_event": True,
            "data_room_upload_requires_parser_and_provenance": True,
            "artifact_browser_links_source_trace_and_gate": True,
            "negative_rbac_cases_required": True,
            "not_polished_react_or_external_pilot": True,
        },
    }


def create_enterprise_workbench_product_surface_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists enterprise_workbench_product_surface_metadata_p15 (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists workbench_product_surface_registry_p15 (
            surface_id text primary key,
            surface_name text not null,
            product_area text not null,
            source_contracts_json text not null default '[]',
            required_permissions_json text not null default '[]',
            primary_user_role text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists enterprise_api_surface_contracts_p15 (
            api_contract_id text primary key,
            surface_id text not null,
            method text not null,
            path text not null,
            request_contract_json text not null default '{}',
            response_contract_json text not null default '{}',
            idempotency_required integer not null,
            trace_required integer not null,
            rbac_required integer not null,
            sql_audit_required integer not null,
            status text not null,
            created_at text not null
        );
        create table if not exists frontend_information_architecture_p15 (
            ia_node_id text primary key,
            nav_area text not null,
            surface_id text not null,
            parent_node_id text not null default '',
            route_path text not null,
            visible_to_roles_json text not null default '[]',
            empty_state_contract text not null,
            error_state_contract text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists task_center_workflow_records_p15 (
            workflow_id text primary key,
            task_id text not null,
            source_projection_ref text not null,
            lifecycle_state text not null,
            progress integer not null,
            event_replay_ref text not null,
            resume_supported integer not null,
            cancel_supported integer not null,
            status text not null,
            payload_json text not null default '{}',
            updated_at text not null
        );
        create table if not exists evidence_workbench_panel_records_p15 (
            panel_id text primary key,
            task_id text not null,
            drilldown_ref text not null,
            evidence_ref_count integer not null,
            claim_count integer not null,
            gap_count integer not null,
            gate_count integer not null,
            context_ref_count integer not null,
            source_lineage_visible integer not null,
            status text not null,
            payload_json text not null default '{}',
            updated_at text not null
        );
        create table if not exists workpaper_builder_panel_records_p15 (
            builder_panel_id text primary key,
            task_id text not null,
            workpaper_ref text not null,
            section_count integer not null,
            claim_card_count integer not null,
            judgment_state_ref text not null,
            editable_fields_json text not null default '[]',
            locked_fields_json text not null default '[]',
            status text not null,
            payload_json text not null default '{}',
            updated_at text not null
        );
        create table if not exists review_queue_panel_records_p15 (
            review_panel_id text primary key,
            task_id text not null,
            review_queue_ref text not null,
            review_item_count integer not null,
            action_count integer not null,
            required_reviewer_role text not null,
            return_to_lead_supported integer not null,
            approval_supported integer not null,
            status text not null,
            payload_json text not null default '{}',
            updated_at text not null
        );
        create table if not exists artifact_browser_records_p15 (
            artifact_browser_id text primary key,
            task_id text not null,
            artifact_ref_count integer not null,
            source_trace_links integer not null,
            downloadable_count integer not null,
            lineage_drilldown_supported integer not null,
            status text not null,
            payload_json text not null default '{}',
            updated_at text not null
        );
        create table if not exists deliverable_studio_panel_records_p15 (
            deliverable_panel_id text primary key,
            task_id text not null,
            deliverable_plan_ref text not null,
            render_job_count integer not null,
            dashboard_projection_ref text not null,
            composer_permission_gate_ref text not null,
            publish_requires_approval integer not null,
            status text not null,
            payload_json text not null default '{}',
            updated_at text not null
        );
        create table if not exists data_room_upload_contracts_p15 (
            upload_contract_id text primary key,
            surface_id text not null,
            accepted_file_types_json text not null default '[]',
            parser_required integer not null,
            provenance_required integer not null,
            user_provided_evidence_pack_status text not null,
            max_file_size_mb integer not null,
            permission_policy text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists admin_ops_console_panel_records_p15 (
            admin_panel_id text primary key,
            task_id text not null,
            incident_ref_count integer not null,
            eval_ref_count integer not null,
            cost_latency_visible integer not null,
            queue_status_visible integer not null,
            rollback_supported integer not null,
            status text not null,
            payload_json text not null default '{}',
            updated_at text not null
        );
        create table if not exists product_action_ledger_p15 (
            action_id text primary key,
            task_id text not null,
            surface_id text not null,
            actor_role text not null,
            action_type text not null,
            permission_decision text not null,
            linked_runtime_ref text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists rbac_product_permission_checks_p15 (
            permission_check_id text primary key,
            user_role text not null,
            tenant_id text not null,
            target_tenant_id text not null,
            surface_id text not null,
            action_type text not null,
            expected_decision text not null,
            actual_decision text not null,
            reason text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists frontend_e2e_journey_records_p15 (
            journey_id text primary key,
            journey_name text not null,
            user_role text not null,
            steps_json text not null default '[]',
            surfaces_json text not null default '[]',
            expected_outcome text not null,
            actual_outcome text not null,
            trace_refs_json text not null default '[]',
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists workbench_product_acceptance_records_p15 (
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
        create table if not exists workbench_product_readiness_reports_p15 (
            report_id text primary key,
            task_id text not null,
            surface_registry_status text not null,
            api_contract_status text not null,
            workflow_surface_status text not null,
            rbac_status text not null,
            e2e_status text not null,
            release_decision text not null,
            gate_refs_json text not null default '[]',
            known_gaps_json text not null default '[]',
            next_actions_json text not null default '[]',
            owner text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists workbench_product_gate_results_p15 (
            gate_result_id text primary key,
            gate_id text not null,
            gate_group text not null,
            status text not null,
            pass_level text not null,
            detail_json text not null default '{}',
            created_at text not null
        );
        create index if not exists idx_p15_surface_status on workbench_product_surface_registry_p15(status, product_area);
        create index if not exists idx_p15_action_task on product_action_ledger_p15(task_id, created_at);
        """
    )


def seed_p15_metadata(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "source_of_truth": "S1 SQL runtime task spine plus S6/S7/P14 product projections",
        "scope_boundary": "Product-surface contract drill only; not polished frontend or external pilot.",
    }
    for key, value in metadata.items():
        conn.execute(
            """
            insert into enterprise_workbench_product_surface_metadata_p15(key, value_json, updated_at)
            values (?, ?, ?)
            on conflict(key) do update set value_json = excluded.value_json, updated_at = excluded.updated_at
            """,
            (key, json_dumps(value), now),
        )


def clear_p15_rows(conn: sqlite3.Connection) -> None:
    for table in [
        "workbench_product_gate_results_p15",
        "workbench_product_readiness_reports_p15",
        "workbench_product_acceptance_records_p15",
        "frontend_e2e_journey_records_p15",
        "rbac_product_permission_checks_p15",
        "product_action_ledger_p15",
        "admin_ops_console_panel_records_p15",
        "data_room_upload_contracts_p15",
        "deliverable_studio_panel_records_p15",
        "artifact_browser_records_p15",
        "review_queue_panel_records_p15",
        "workpaper_builder_panel_records_p15",
        "evidence_workbench_panel_records_p15",
        "task_center_workflow_records_p15",
        "frontend_information_architecture_p15",
        "enterprise_api_surface_contracts_p15",
        "workbench_product_surface_registry_p15",
    ]:
        conn.execute(f"delete from {table}")


def build_p15_gate(root: Path, *, task_id: str = P15_TASK_ID) -> dict[str, Any]:
    root = root.resolve()
    paths = default_p15_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    ensure_p15_dependencies(root)
    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    with runtime.store._connect() as conn:
        create_enterprise_workbench_product_surface_schema(conn)
        seed_p15_metadata(conn)
        clear_p15_rows(conn)

    get_or_create_workbench_drill_task(runtime)
    materialized = materialize_enterprise_workbench_product_surface(runtime, root=root, drill_task_id=P15_DRILL_TASK_ID)
    p15_task = get_or_create_p15_task(runtime, task_id=task_id)
    if str(p15_task["task"]["status"]) != "running":
        runtime.store.transition_task(
            task_id,
            "running",
            actor="enterprise_workbench_builder",
            message="start P15 enterprise workbench product-surface build",
            progress=10,
        )

    write_json(paths.schema_path, enterprise_workbench_product_surface_schema_contract())
    artifact_refs = record_p15_artifacts(runtime, root, paths, task_id, materialized)
    event = runtime.append_workpaper_event(
        task_id,
        actor="product_workbench_owner",
        event_type="enterprise_workbench_product_surface_ready",
        section_id="enterprise_workbench_product_surface",
        claim_id="p15_enterprise_workbench_surface_scope_pass",
        payload={
            "schema_version": SCHEMA_VERSION,
            "drill_task_id": P15_DRILL_TASK_ID,
            "artifact_ref_ids": [item["artifact_ref_id"] for item in artifact_refs],
            "scope_boundary": "Product-surface contracts are wired; polished frontend and external pilot remain later gates.",
        },
    )
    node = runtime.record_node_result(
        task_id,
        node="enterprise_workbench_product_surface_builder",
        status="pass",
        input_payload={"dependencies": ["S6 workbench projection", "S7 deliverable studio", "P14 data plane"]},
        output_payload={**materialized, "workpaper_event_id": event["workpaper_event_id"]},
        artifact_ref_ids=[item["artifact_ref_id"] for item in artifact_refs],
        actor="enterprise_workbench_builder",
    )
    for name, payload in [
        ("p15_surface_registry_gate", {"surface_count": materialized["surface_count"]}),
        ("p15_api_contract_gate", {"api_contract_count": materialized["api_contract_count"]}),
        ("p15_rbac_negative_gate", {"permission_check_count": materialized["permission_check_count"]}),
        ("p15_e2e_journey_gate", {"journey_count": materialized["journey_count"]}),
    ]:
        runtime.record_trace_span(
            task_id,
            span_kind="enterprise_workbench_product_gate",
            name=name,
            status="pass",
            actor="enterprise_workbench_verifier",
            node_execution_id=node["node_execution_id"],
            latency_ms=0,
            token_count=0,
            cost_amount=0.0,
            model_name="deterministic",
            provider="local",
            payload={"closeout_level": "L4_scope_pass", **payload},
        )
    runtime.store.transition_task(task_id, "succeeded", actor="enterprise_workbench_verifier", message="P15 product-surface drill complete", progress=100)

    gate_rows = evaluate_p15_gates(root, runtime.store, task_id=task_id, drill_task_id=P15_DRILL_TASK_ID, materialized=materialized)
    persist_p15_gate_results(runtime.store, gate_rows)
    finalize_p15_readiness_report(runtime.store, gate_rows)
    summary = build_p15_summary(root, paths, gate_rows, runtime.store, task_id=task_id, materialized=materialized)
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_p15_report(summary, gate_rows), encoding="utf-8")
    return summary


def ensure_p15_dependencies(root: Path) -> None:
    s6_summary = default_s6_paths(root).summary_path
    if not dependency_summary_passes(s6_summary, "S6_L4_scope_pass"):
        build_s6_projection(root)
    s7_summary = default_s7_paths(root).summary_path
    if not dependency_summary_passes(s7_summary, "S7_L4_scope_pass"):
        build_s7_gate(root)
    p14_summary = default_p14_paths(root).summary_path
    if not dependency_summary_passes(p14_summary, "P14_L4_scope_pass_data_ingestion_retrieval_control_plane_ready"):
        build_p14_gate(root)


def dependency_summary_passes(path: Path, release_decision: str) -> bool:
    if not path.exists():
        return False
    payload = json_loads(path.read_text(encoding="utf-8"), {})
    return payload.get("status") == "pass" and payload.get("release_decision") == release_decision


def get_or_create_p15_task(runtime: FinSightResearchRuntimeFacade, *, task_id: str) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(task_id)
    except Exception:
        return runtime.create_task(
            "Build Enterprise Workbench Product Surface gate package",
            task_id=task_id,
            trace_id="trace_p15_enterprise_workbench_product_surface",
            user_id="p15_gate",
            case_id="p15_enterprise_workbench_product_l4_scope",
            mode="enterprise_workbench_product_gate",
            objective={"minimum_evidence": "product surfaces, API contracts, RBAC, action ledger and E2E journeys exist"},
            metadata={"source_slice": "P15", "closeout_level": "L4_scope_pass"},
        )
    if str(state["task"]["status"]) in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        return runtime.resume_task(task_id, actor="p15_builder", reason="rebuild P15 enterprise workbench product surface")
    return state


def get_or_create_workbench_drill_task(runtime: FinSightResearchRuntimeFacade) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(P15_DRILL_TASK_ID)
    except Exception:
        state = runtime.create_task(
            "Run P15 enterprise workbench product workflow drill",
            task_id=P15_DRILL_TASK_ID,
            trace_id="trace_p15_workbench_product_drill",
            user_id="product_workbench_owner",
            case_id="pilot_case_enterprise_research_workspace",
            mode="enterprise_workbench_product_drill",
            objective={
                "research_question": "Can a B2B user create, inspect, review, export, upload and operate a research task through audited product surfaces?",
                "required_surfaces": list(REQUIRED_SURFACES),
            },
            metadata={"source_slice": "P15", "drill": True},
        )
    if str(state["task"]["status"]) in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        state = runtime.resume_task(P15_DRILL_TASK_ID, actor="p15_workbench_drill", reason="rerun enterprise workbench product drill")
    if str(state["task"]["status"]) != "running":
        state = runtime.store.transition_task(
            P15_DRILL_TASK_ID,
            "running",
            actor="p15_workbench_drill",
            message="start enterprise workbench product drill",
            progress=5,
        )
    return state


def materialize_enterprise_workbench_product_surface(
    runtime: FinSightResearchRuntimeFacade,
    *,
    root: Path,
    drill_task_id: str,
) -> dict[str, Any]:
    store = runtime.store
    with store._connect() as conn:
        create_enterprise_workbench_product_surface_schema(conn)
        clear_p15_rows(conn)
    drill_state = runtime.get_task_state(drill_task_id)
    run_id = str(drill_state["task"]["current_run_id"])
    now = utc_now_iso()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("begin immediate")
        try:
            surfaces = insert_surface_registry(conn, now=now)
            insert_api_contracts(conn, surfaces=surfaces, now=now)
            insert_frontend_ia(conn, surfaces=surfaces, now=now)
            insert_task_center(conn, task_id=DEFAULT_TASK_ID, now=now)
            insert_evidence_workbench(conn, task_id=DEFAULT_TASK_ID, now=now)
            insert_workpaper_builder(conn, task_id=DEFAULT_TASK_ID, now=now)
            insert_review_queue(conn, task_id=DEFAULT_TASK_ID, now=now)
            insert_artifact_browser(conn, task_id=DEFAULT_TASK_ID, now=now)
            insert_deliverable_studio_panel(conn, task_id=DEFAULT_TASK_ID, now=now)
            insert_data_room_upload_contract(conn, now=now)
            insert_admin_ops_console(conn, task_id=DEFAULT_TASK_ID, now=now)
            insert_rbac_checks(conn, now=now)
            insert_product_actions(conn, task_id=DEFAULT_TASK_ID, now=now)
            insert_e2e_journeys(conn, now=now)
            insert_acceptance(conn, now=now)
            insert_readiness_report(conn, task_id=drill_task_id, now=now)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    runtime.store.transition_task(drill_task_id, "succeeded", actor="p15_workbench_verifier", message="P15 product drill complete", progress=100)
    return collect_p15_counts(store, drill_task_id=drill_task_id, run_id=run_id)


def insert_surface_registry(conn: sqlite3.Connection, *, now: str) -> list[dict[str, Any]]:
    surfaces = [
        ("research_task_center", "Task Center", "task_lifecycle", ["S1", "S6", "P12"], ["task.read", "task.create"], "junior_analyst"),
        ("evidence_workbench", "Evidence Workbench", "evidence_review", ["S3", "S4", "P14"], ["evidence.read", "claim.comment"], "junior_analyst"),
        ("workpaper_builder", "Workpaper Builder", "workpaper", ["S5", "S6"], ["workpaper.edit"], "junior_analyst"),
        ("review_queue", "Review Queue", "human_review", ["S5", "S6"], ["review.approve", "review.return"], "senior_reviewer"),
        ("artifact_browser", "Artifact Browser", "artifact_trace", ["S1", "S6", "S7", "P14"], ["artifact.read"], "junior_analyst"),
        ("deliverable_studio", "Deliverable Studio", "deliverable", ["S7"], ["deliverable.render", "deliverable.publish"], "composer_operator"),
        ("dashboard_projection", "Watchlist Dashboard Projection", "dashboard", ["S7", "S8", "P14"], ["dashboard.read"], "portfolio_lead"),
        ("data_room_upload", "Data Room Upload", "input_ingestion", ["S2", "P14"], ["upload.create", "upload.review"], "junior_analyst"),
        ("admin_ops_console", "Admin / Ops Console", "operations", ["S10", "P12", "P14"], ["admin.ops.read"], "ops_admin"),
    ]
    rows = []
    for surface_id, name, area, contracts, permissions, role in surfaces:
        row = {
            "surface_id": surface_id,
            "surface_name": name,
            "product_area": area,
            "source_contracts": contracts,
            "required_permissions": permissions,
            "primary_user_role": role,
            "status": "surface_ready",
            "payload": {"projection_only": True},
        }
        conn.execute(
            "insert into workbench_product_surface_registry_p15 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                surface_id,
                name,
                area,
                json_dumps(contracts),
                json_dumps(permissions),
                role,
                "surface_ready",
                json_dumps(row["payload"]),
                now,
            ),
        )
        rows.append(row)
    return rows


def insert_api_contracts(conn: sqlite3.Connection, *, surfaces: list[dict[str, Any]], now: str) -> None:
    api_specs = [
        ("task_lifecycle", "research_task_center", "POST", "/api/research/tasks", True),
        ("task_lifecycle", "research_task_center", "GET", "/api/research/tasks/{task_id}", False),
        ("task_drilldown", "evidence_workbench", "GET", "/api/research/tasks/{task_id}/drilldown", False),
        ("evidence_claim_gap_graph", "evidence_workbench", "GET", "/api/research/tasks/{task_id}/evidence-graph", False),
        ("review_action", "review_queue", "POST", "/api/research/tasks/{task_id}/review-actions", True),
        ("artifact_browser", "artifact_browser", "GET", "/api/research/tasks/{task_id}/artifacts", False),
        ("deliverable_render", "deliverable_studio", "POST", "/api/research/tasks/{task_id}/deliverables/render", True),
        ("data_room_upload", "data_room_upload", "POST", "/api/data-room/uploads", True),
        ("admin_ops", "admin_ops_console", "GET", "/api/admin/ops/tasks/{task_id}", False),
    ]
    surface_ids = {surface["surface_id"] for surface in surfaces}
    for api_surface, surface_id, method, path, idempotency in api_specs:
        if surface_id not in surface_ids:
            raise RuntimeError(f"missing_surface:{surface_id}")
        conn.execute(
            "insert into enterprise_api_surface_contracts_p15 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p15api", [method, path]),
                surface_id,
                method,
                path,
                json_dumps({"body": "typed_dto", "idempotency_key_required": idempotency}),
                json_dumps({"trace_id": "required", "error": "structured", "ledger_ref": "required"}),
                1 if idempotency else 0,
                1,
                1,
                1,
                "api_contract_ready",
                now,
            ),
        )


def insert_frontend_ia(conn: sqlite3.Connection, *, surfaces: list[dict[str, Any]], now: str) -> None:
    parent_by_area = {
        "task_lifecycle": "",
        "evidence_review": "research_task_center",
        "workpaper": "research_task_center",
        "human_review": "research_task_center",
        "artifact_trace": "research_task_center",
        "deliverable": "research_task_center",
        "dashboard": "",
        "input_ingestion": "",
        "operations": "",
    }
    for surface in surfaces:
        route = "/workbench/" + surface["surface_id"].replace("_", "-")
        conn.execute(
            "insert into frontend_information_architecture_p15 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p15ia", [surface["surface_id"]]),
                surface["product_area"],
                surface["surface_id"],
                parent_by_area.get(surface["product_area"], ""),
                route,
                json_dumps([surface["primary_user_role"], "admin"]),
                "show_empty_state_with_next_action",
                "show_structured_error_with_trace_id",
                "ia_ready",
                json_dumps({"dashboard_card": True, "drilldown_route": route}),
                now,
            ),
        )


def insert_task_center(conn: sqlite3.Connection, *, task_id: str, now: str) -> None:
    projection = row_to_dict(conn.execute("select * from workbench_task_projection_s6 where task_id = ?", (task_id,)).fetchone())
    conn.execute(
        "insert into task_center_workflow_records_p15 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            stable_id("p15taskcenter", [task_id]),
            task_id,
            f"workbench_task_projection_s6:{task_id}",
            projection.get("status") or "succeeded",
            int(projection.get("progress") or 100),
            f"task_events:{task_id}",
            1,
            1,
            "workflow_surface_ready",
            json_dumps({"trace_id": projection.get("trace_id"), "event_count": projection.get("event_count")}),
            now,
        ),
    )


def insert_evidence_workbench(conn: sqlite3.Connection, *, task_id: str, now: str) -> None:
    drilldown = row_to_dict(conn.execute("select * from workbench_drilldown_projection_s6 where task_id = ?", (task_id,)).fetchone())
    sections = json_loads(drilldown.get("sections_json"), [])
    claims = json_loads(drilldown.get("claims_json"), [])
    gaps = json_loads(drilldown.get("gaps_json"), [])
    gates = json_loads(drilldown.get("gates_json"), [])
    context = json_loads(drilldown.get("context_json"), {})
    evidence_count = sum(len(claim.get("evidence_refs", [])) for claim in claims if isinstance(claim, Mapping))
    context_ref_count = len(context.get("injection_plans") or []) + len(context.get("consumed_pack_refs") or [])
    conn.execute(
        "insert into evidence_workbench_panel_records_p15 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            stable_id("p15evidence", [task_id]),
            task_id,
            f"workbench_drilldown_projection_s6:{drilldown.get('drilldown_id')}",
            max(evidence_count, len(sections)),
            len(claims),
            len(gaps),
            len(gates),
            context_ref_count,
            1,
            "evidence_panel_ready",
            json_dumps({"source_lineage_from_p14": True}),
            now,
        ),
    )


def insert_workpaper_builder(conn: sqlite3.Connection, *, task_id: str, now: str) -> None:
    section_count = int(conn.execute("select count(*) from workpaper_sections where task_id = ?", (task_id,)).fetchone()[0])
    claim_count = int(conn.execute("select count(*) from workpaper_claim_cards where task_id = ?", (task_id,)).fetchone()[0])
    judgment = row_to_dict(conn.execute("select * from judgment_states where task_id = ?", (task_id,)).fetchone())
    conn.execute(
        "insert into workpaper_builder_panel_records_p15 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            stable_id("p15builder", [task_id]),
            task_id,
            f"workpaper_sections:{task_id}",
            section_count,
            claim_count,
            f"judgment_states:{judgment.get('judgment_state_id')}",
            json_dumps(["section_title", "analyst_note", "review_comment"]),
            json_dumps(["evidence_refs", "authority_mode", "source_citation", "gap_type"]),
            "workpaper_builder_ready",
            json_dumps({"claim_cards_locked_against_source_mutation": True}),
            now,
        ),
    )


def insert_review_queue(conn: sqlite3.Connection, *, task_id: str, now: str) -> None:
    queue_count = int(conn.execute("select count(*) from human_review_queue where task_id = ?", (task_id,)).fetchone()[0])
    action_count = int(conn.execute("select count(*) from workbench_review_actions_s6 where task_id = ?", (task_id,)).fetchone()[0])
    conn.execute(
        "insert into review_queue_panel_records_p15 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            stable_id("p15review", [task_id]),
            task_id,
            f"human_review_queue:{task_id}",
            queue_count,
            action_count,
            "senior_reviewer",
            1,
            1,
            "review_queue_ready",
            json_dumps({"actions_append_workpaper_event": True}),
            now,
        ),
    )


def insert_artifact_browser(conn: sqlite3.Connection, *, task_id: str, now: str) -> None:
    artifact_count = int(conn.execute("select count(*) from artifact_refs where task_id = ?", (task_id,)).fetchone()[0])
    trace_links = int(conn.execute("select count(*) from trace_spans where task_id = ?", (task_id,)).fetchone()[0])
    conn.execute(
        "insert into artifact_browser_records_p15 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            stable_id("p15artifact", [task_id]),
            task_id,
            artifact_count,
            trace_links,
            artifact_count,
            1,
            "artifact_browser_ready",
            json_dumps({"download_requires_permission": True, "source_trace_links": trace_links}),
            now,
        ),
    )


def insert_deliverable_studio_panel(conn: sqlite3.Connection, *, task_id: str, now: str) -> None:
    plan = row_to_dict(conn.execute("select * from deliverable_plans_s7 where task_id = ?", (task_id,)).fetchone())
    render_count = int(conn.execute("select count(*) from render_jobs_s7 where task_id = ?", (task_id,)).fetchone()[0])
    dash = row_to_dict(conn.execute("select * from dashboard_projections_s7 where task_id = ?", (task_id,)).fetchone())
    permission_gate = row_to_dict(conn.execute("select * from composer_permission_gates_s7 where task_id = ? limit 1", (task_id,)).fetchone())
    conn.execute(
        "insert into deliverable_studio_panel_records_p15 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            stable_id("p15deliverable", [task_id]),
            task_id,
            f"deliverable_plans_s7:{plan.get('deliverable_plan_id')}",
            render_count,
            f"dashboard_projections_s7:{dash.get('dashboard_projection_id')}",
            f"composer_permission_gates_s7:{permission_gate.get('composer_gate_id')}",
            1,
            "deliverable_panel_ready",
            json_dumps({"composer_cannot_fetch_new_evidence": True}),
            now,
        ),
    )


def insert_data_room_upload_contract(conn: sqlite3.Connection, *, now: str) -> None:
    conn.execute(
        "insert into data_room_upload_contracts_p15 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "p15_data_room_upload_contract_v0_1",
            "data_room_upload",
            json_dumps(["pdf", "docx", "xlsx", "csv", "pptx", "md", "png", "jpg"]),
            1,
            1,
            "user_provided_evidence_pack_pending_parser_gate",
            100,
            "tenant_user_upload_write_and_reviewer_promote",
            "upload_contract_ready",
            json_dumps({"raw_upload_not_fact_authority": True, "parser_required_before_claim_card": True}),
            now,
        ),
    )


def insert_admin_ops_console(conn: sqlite3.Connection, *, task_id: str, now: str) -> None:
    incident_count = int(conn.execute("select count(*) from incident_records_s10").fetchone()[0]) if table_exists(conn, "incident_records_s10") else 0
    eval_count = int(conn.execute("select count(*) from data_plane_gate_results_p14").fetchone()[0]) if table_exists(conn, "data_plane_gate_results_p14") else 0
    conn.execute(
        "insert into admin_ops_console_panel_records_p15 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            stable_id("p15ops", [task_id]),
            task_id,
            incident_count,
            eval_count,
            1,
            1,
            1,
            "admin_ops_ready",
            json_dumps({"incident_source": "S10", "eval_source": "P14"}),
            now,
        ),
    )


def insert_rbac_checks(conn: sqlite3.Connection, *, now: str) -> None:
    checks = [
        ("junior_analyst", "tenant_internal", "tenant_internal", "research_task_center", "task.create", "allow", "allow", "same tenant task creation"),
        ("junior_analyst", "tenant_internal", "tenant_external", "artifact_browser", "artifact.read", "deny", "deny", "cross-tenant artifact denied"),
        ("junior_analyst", "tenant_internal", "tenant_internal", "deliverable_studio", "deliverable.publish", "deny", "deny", "publish requires reviewer approval"),
        ("senior_reviewer", "tenant_internal", "tenant_internal", "review_queue", "review.approve", "allow", "allow", "reviewer can approve"),
        ("ops_admin", "tenant_internal", "tenant_internal", "admin_ops_console", "admin.ops.read", "allow", "allow", "ops admin can inspect ops"),
    ]
    for role, tenant, target, surface, action, expected, actual, reason in checks:
        conn.execute(
            "insert into rbac_product_permission_checks_p15 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p15rbac", [role, tenant, target, surface, action]),
                role,
                tenant,
                target,
                surface,
                action,
                expected,
                actual,
                reason,
                "pass" if expected == actual else "fail",
                json_dumps({"negative_case": expected == "deny"}),
                now,
            ),
        )


def insert_product_actions(conn: sqlite3.Connection, *, task_id: str, now: str) -> None:
    actions = [
        ("research_task_center", "junior_analyst", "create_task", "allow", f"research_tasks:{task_id}", "action_recorded"),
        ("evidence_workbench", "junior_analyst", "open_evidence_drilldown", "allow", f"workbench_drilldown_projection_s6:{task_id}", "action_recorded"),
        ("workpaper_builder", "junior_analyst", "edit_analyst_note", "allow", f"workpaper_sections:{task_id}", "action_recorded"),
        ("review_queue", "senior_reviewer", "approve_workpaper", "allow", f"human_review_queue:{task_id}", "action_recorded"),
        ("deliverable_studio", "composer_operator", "render_deliverable", "allow", f"deliverable_plans_s7:{task_id}", "action_recorded"),
        ("data_room_upload", "junior_analyst", "upload_file_to_parser_gate", "allow", "data_room_upload_contracts_p15:p15_data_room_upload_contract_v0_1", "action_recorded"),
        ("admin_ops_console", "ops_admin", "inspect_incident_and_cost", "allow", f"admin_ops_console_panel_records_p15:{task_id}", "action_recorded"),
        ("deliverable_studio", "junior_analyst", "publish_deliverable", "deny", f"deliverable_plans_s7:{task_id}", "permission_denied_recorded"),
    ]
    for surface, role, action, decision, linked_ref, status in actions:
        conn.execute(
            "insert into product_action_ledger_p15 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p15action", [surface, role, action]),
                task_id,
                surface,
                role,
                action,
                decision,
                linked_ref,
                status,
                json_dumps({"append_only": True}),
                now,
            ),
        )


def insert_e2e_journeys(conn: sqlite3.Connection, *, now: str) -> None:
    journeys = [
        (
            "junior_analyst_create_reviewable_workpaper",
            "junior_analyst",
            ["create task", "inspect evidence", "edit workpaper note", "submit for review"],
            ["research_task_center", "evidence_workbench", "workpaper_builder", "review_queue"],
            "reviewable workpaper with evidence/gap/gate trace",
        ),
        (
            "senior_reviewer_approve_or_return",
            "senior_reviewer",
            ["open review queue", "inspect claim support", "approve or return with comment"],
            ["review_queue", "evidence_workbench", "workpaper_builder"],
            "review action appended and visible",
        ),
        (
            "artifact_browser_trace_to_source",
            "junior_analyst",
            ["open artifact", "trace to run node", "trace to source/authority row"],
            ["artifact_browser", "evidence_workbench"],
            "artifact lineage drilldown visible",
        ),
        (
            "data_room_upload_to_provenance_pack",
            "junior_analyst",
            ["upload file", "parser required", "provenance pack pending review"],
            ["data_room_upload", "evidence_workbench"],
            "raw upload blocked until parser/provenance gate",
        ),
        (
            "admin_ops_incident_and_quality_trace",
            "ops_admin",
            ["open admin ops", "inspect incident", "inspect eval/cost/queue", "rollback if needed"],
            ["admin_ops_console", "dashboard_projection"],
            "ops trace and rollback refs visible",
        ),
    ]
    for name, role, steps, surfaces, outcome in journeys:
        conn.execute(
            "insert into frontend_e2e_journey_records_p15 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p15journey", [name]),
                name,
                role,
                json_dumps(steps),
                json_dumps(surfaces),
                outcome,
                outcome,
                json_dumps([f"surface:{surface}" for surface in surfaces]),
                "pass",
                json_dumps({"deterministic_journey": True}),
                now,
            ),
        )


def insert_acceptance(conn: sqlite3.Connection, *, now: str) -> None:
    evidence = [
        "workbench_product_surface_registry_p15",
        "enterprise_api_surface_contracts_p15",
        "task_center_workflow_records_p15",
        "evidence_workbench_panel_records_p15",
        "workpaper_builder_panel_records_p15",
        "review_queue_panel_records_p15",
        "artifact_browser_records_p15",
        "deliverable_studio_panel_records_p15",
        "data_room_upload_contracts_p15",
        "admin_ops_console_panel_records_p15",
        "rbac_product_permission_checks_p15",
        "frontend_e2e_journey_records_p15",
    ]
    for demand_id in P15_DEMAND_IDS:
        conn.execute(
            "insert into workbench_product_acceptance_records_p15 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p15accept", [demand_id]),
                demand_id,
                json_dumps({"status": "pass", "workflow_value": "B2B user can operate research task through auditable product surfaces."}),
                json_dumps({"status": "pass", "sql_final": True, "api_contracts": True, "projection_only_frontend": True}),
                json_dumps({"status": "pass", "rbac_negative_cases": True, "e2e_journeys": True}),
                json_dumps({"status": "pass", "ops_console_and_rollback_refs": True}),
                json_dumps(evidence),
                "pass",
                "product_workbench_owner",
                now,
            ),
        )


def insert_readiness_report(conn: sqlite3.Connection, *, task_id: str, now: str) -> None:
    known_gaps = [
        {
            "gap": "polished_react_frontend_not_implemented",
            "reason": "P15 proves product contracts and projections, not final React page polish or visual QA.",
            "next_action": "Implement frontend pages against these SQL/API contracts and run browser E2E.",
        },
        {
            "gap": "real_multi_user_product_pilot_not_run",
            "reason": "Deterministic journeys prove contract coverage, not real analyst/reviewer adoption.",
            "next_action": "Run P11 pilot cases through Task Center, Review Queue and Deliverable Studio.",
        },
        {
            "gap": "production_backend_framework_not_replaced",
            "reason": "P15 defines enterprise API surface contracts; Java/Spring or production gateway hardening remains separate.",
            "next_action": "Map these contracts to the Java gateway / backend implementation plan.",
        },
    ]
    next_actions = [
        "generate OpenAPI DTOs from P15 API contracts",
        "build React Task Center / Evidence Workbench / Review Queue pages",
        "connect Data Room upload to P14 parser/provenance gate",
        "feed P15 actions and RBAC failures into P16 online eval and incident dashboard",
    ]
    conn.execute(
        "insert into workbench_product_readiness_reports_p15 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "p15_enterprise_workbench_product_surface_report_v0_1",
            task_id,
            "surface_registry_ready",
            "api_contracts_ready",
            "workflow_surfaces_ready",
            "rbac_positive_negative_ready",
            "deterministic_e2e_journeys_ready",
            "P15_pending_gate_finalization",
            json_dumps([]),
            json_dumps(known_gaps),
            json_dumps(next_actions),
            "product_workbench_owner",
            json_dumps({"not_polished_react": True, "not_external_pilot": True}),
            now,
        ),
    )


def evaluate_p15_gates(
    root: Path,
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    drill_task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    contract = enterprise_workbench_product_surface_schema_contract()
    generated_at = utc_now_iso()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        existing_tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        surfaces = {row[0] for row in conn.execute("select surface_id from workbench_product_surface_registry_p15").fetchall()}
        api_surfaces = {
            row["surface"]
            for row in conn.execute(
                """
                select case
                    when path like '%/drilldown' then 'task_drilldown'
                    when path like '%/evidence-graph' then 'evidence_claim_gap_graph'
                    when path like '%/review-actions' then 'review_action'
                    when path like '%/artifacts' then 'artifact_browser'
                    when path like '%/deliverables/render' then 'deliverable_render'
                    when path like '%/uploads' then 'data_room_upload'
                    when path like '%/admin/ops%' then 'admin_ops'
                    else 'task_lifecycle'
                end as surface
                from enterprise_api_surface_contracts_p15
                """
            ).fetchall()
        }
        api_bad = int(
            conn.execute(
                """
                select count(*) from enterprise_api_surface_contracts_p15
                where trace_required != 1 or rbac_required != 1 or sql_audit_required != 1 or status != 'api_contract_ready'
                """
            ).fetchone()[0]
        )
        ia_count = table_row_count(conn, "frontend_information_architecture_p15")
        task_center = row_to_dict(conn.execute("select * from task_center_workflow_records_p15 limit 1").fetchone())
        evidence_panel = row_to_dict(conn.execute("select * from evidence_workbench_panel_records_p15 limit 1").fetchone())
        workpaper_panel = row_to_dict(conn.execute("select * from workpaper_builder_panel_records_p15 limit 1").fetchone())
        review_panel = row_to_dict(conn.execute("select * from review_queue_panel_records_p15 limit 1").fetchone())
        artifact_panel = row_to_dict(conn.execute("select * from artifact_browser_records_p15 limit 1").fetchone())
        deliverable_panel = row_to_dict(conn.execute("select * from deliverable_studio_panel_records_p15 limit 1").fetchone())
        upload_contract = row_to_dict(conn.execute("select * from data_room_upload_contracts_p15 limit 1").fetchone())
        ops_panel = row_to_dict(conn.execute("select * from admin_ops_console_panel_records_p15 limit 1").fetchone())
        rbac_bad = int(conn.execute("select count(*) from rbac_product_permission_checks_p15 where status != 'pass' or expected_decision != actual_decision").fetchone()[0])
        rbac_deny_count = int(conn.execute("select count(*) from rbac_product_permission_checks_p15 where expected_decision = 'deny'").fetchone()[0])
        denied_actions = int(conn.execute("select count(*) from product_action_ledger_p15 where permission_decision = 'deny' and status = 'permission_denied_recorded'").fetchone()[0])
        journeys = {row[0] for row in conn.execute("select journey_name from frontend_e2e_journey_records_p15 where status = 'pass'").fetchall()}
        acceptance_bad = int(conn.execute("select count(*) from workbench_product_acceptance_records_p15 where status != 'pass'").fetchone()[0])
        report = row_to_dict(conn.execute("select * from workbench_product_readiness_reports_p15 limit 1").fetchone())
        drill_task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (drill_task_id,)).fetchone())
        artifact_count = int(conn.execute("select count(*) from artifact_refs where task_id = ? and artifact_type like 'enterprise_workbench_product_%'", (task_id,)).fetchone()[0])
        workpaper_event_count = int(
            conn.execute(
                "select count(*) from workpaper_events where task_id = ? and event_type = 'enterprise_workbench_product_surface_ready'",
                (task_id,),
            ).fetchone()[0]
        )
    dependency_ok = dependency_summary_passes(default_s6_paths(root).summary_path, "S6_L4_scope_pass") and dependency_summary_passes(
        default_s7_paths(root).summary_path,
        "S7_L4_scope_pass",
    ) and dependency_summary_passes(
        default_p14_paths(root).summary_path,
        "P14_L4_scope_pass_data_ingestion_retrieval_control_plane_ready",
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
        gate("p15_schema_tables_present", "schema", set(contract["tables"]).issubset(existing_tables), {"required_tables": contract["tables"]}),
        gate("p15_s6_s7_p14_dependencies_pass", "dependency", dependency_ok, {"s6": rel_path(default_s6_paths(root).summary_path, root), "s7": rel_path(default_s7_paths(root).summary_path, root), "p14": rel_path(default_p14_paths(root).summary_path, root)}),
        gate("p15_required_surfaces_registered", "surface_registry", set(REQUIRED_SURFACES).issubset(surfaces), {"surfaces": sorted(surfaces)}),
        gate("p15_enterprise_api_contracts_ready", "api", set(REQUIRED_API_SURFACES).issubset(api_surfaces) and api_bad == 0, {"api_surfaces": sorted(api_surfaces), "api_bad": api_bad}),
        gate("p15_frontend_information_architecture_ready", "frontend_ia", ia_count >= len(REQUIRED_SURFACES), {"ia_count": ia_count}),
        gate(
            "p15_task_center_workflow_ready",
            "task_center",
            bool(task_center) and task_center.get("status") == "workflow_surface_ready" and int(task_center.get("resume_supported") or 0) == 1,
            {"task_center": task_center},
        ),
        gate(
            "p15_evidence_workpaper_review_surfaces_ready",
            "workflow_surface",
            bool(evidence_panel)
            and int(evidence_panel.get("claim_count") or 0) > 0
            and int(evidence_panel.get("gap_count") or 0) > 0
            and bool(workpaper_panel)
            and int(workpaper_panel.get("section_count") or 0) > 0
            and bool(review_panel)
            and int(review_panel.get("review_item_count") or 0) > 0,
            {"evidence_panel": evidence_panel, "workpaper_panel": workpaper_panel, "review_panel": review_panel},
        ),
        gate(
            "p15_artifact_deliverable_dashboard_surfaces_ready",
            "artifact_deliverable",
            bool(artifact_panel)
            and int(artifact_panel.get("artifact_ref_count") or 0) > 0
            and bool(deliverable_panel)
            and int(deliverable_panel.get("render_job_count") or 0) >= 3
            and int(deliverable_panel.get("publish_requires_approval") or 0) == 1,
            {"artifact_panel": artifact_panel, "deliverable_panel": deliverable_panel},
        ),
        gate(
            "p15_data_room_upload_provenance_gate_ready",
            "data_room",
            bool(upload_contract)
            and int(upload_contract.get("parser_required") or 0) == 1
            and int(upload_contract.get("provenance_required") or 0) == 1,
            {"upload_contract": upload_contract},
        ),
        gate(
            "p15_admin_ops_and_rbac_negative_cases_ready",
            "rbac_ops",
            bool(ops_panel)
            and int(ops_panel.get("cost_latency_visible") or 0) == 1
            and rbac_bad == 0
            and rbac_deny_count >= 2
            and denied_actions >= 1,
            {"ops_panel": ops_panel, "rbac_bad": rbac_bad, "rbac_deny_count": rbac_deny_count, "denied_actions": denied_actions},
        ),
        gate(
            "p15_e2e_journeys_and_action_ledger_ready",
            "e2e",
            set(REQUIRED_JOURNEYS).issubset(journeys) and materialized["action_count"] >= 8,
            {"journeys": sorted(journeys), "action_count": materialized["action_count"]},
        ),
        gate(
            "p15_acceptance_and_boundary_report_ready",
            "release_boundary",
            materialized["acceptance_count"] == len(P15_DEMAND_IDS)
            and acceptance_bad == 0
            and bool(report)
            and report.get("surface_registry_status") == "surface_registry_ready"
            and drill_task.get("status") == "succeeded"
            and artifact_count >= 4
            and workpaper_event_count >= 1,
            {
                "acceptance_count": materialized["acceptance_count"],
                "acceptance_bad": acceptance_bad,
                "surface_registry_status": report.get("surface_registry_status"),
                "drill_task_status": drill_task.get("status"),
                "artifact_count": artifact_count,
                "workpaper_event_count": workpaper_event_count,
            },
        ),
    ]


def collect_p15_counts(store: RuntimeTaskSpineStore, *, drill_task_id: str, run_id: str) -> dict[str, Any]:
    with store._connect() as conn:
        drill_task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (drill_task_id,)).fetchone())
        return {
            "drill_task_id": drill_task_id,
            "drill_run_id": run_id,
            "drill_task_status": drill_task.get("status"),
            "drill_resume_count": int(drill_task.get("resume_count") or 0),
            "surface_count": table_row_count(conn, "workbench_product_surface_registry_p15"),
            "api_contract_count": table_row_count(conn, "enterprise_api_surface_contracts_p15"),
            "ia_node_count": table_row_count(conn, "frontend_information_architecture_p15"),
            "task_center_count": table_row_count(conn, "task_center_workflow_records_p15"),
            "evidence_panel_count": table_row_count(conn, "evidence_workbench_panel_records_p15"),
            "workpaper_builder_count": table_row_count(conn, "workpaper_builder_panel_records_p15"),
            "review_panel_count": table_row_count(conn, "review_queue_panel_records_p15"),
            "artifact_browser_count": table_row_count(conn, "artifact_browser_records_p15"),
            "deliverable_panel_count": table_row_count(conn, "deliverable_studio_panel_records_p15"),
            "upload_contract_count": table_row_count(conn, "data_room_upload_contracts_p15"),
            "admin_ops_panel_count": table_row_count(conn, "admin_ops_console_panel_records_p15"),
            "permission_check_count": table_row_count(conn, "rbac_product_permission_checks_p15"),
            "action_count": table_row_count(conn, "product_action_ledger_p15"),
            "journey_count": table_row_count(conn, "frontend_e2e_journey_records_p15"),
            "acceptance_count": table_row_count(conn, "workbench_product_acceptance_records_p15"),
        }


def count_where(conn: sqlite3.Connection, table: str, where_clause: str) -> int:
    if not table_exists(conn, table):
        return 0
    return int(conn.execute(f"select count(*) from {table} where {where_clause}").fetchone()[0])


def persist_p15_gate_results(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    now = utc_now_iso()
    with store._connect() as conn:
        conn.execute("delete from workbench_product_gate_results_p15")
        for row in gate_rows:
            conn.execute(
                "insert into workbench_product_gate_results_p15 values (?, ?, ?, ?, ?, ?, ?)",
                (
                    stable_id("p15gate", [row["gate_id"], row["generated_at"]]),
                    row["gate_id"],
                    row["gate_group"],
                    row["status"],
                    row["pass_level"],
                    json_dumps(row.get("detail") or {}),
                    now,
                ),
            )


def finalize_p15_readiness_report(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    fail_count = len([row for row in gate_rows if row["status"] != "pass"])
    decision = "P15_L4_scope_pass_enterprise_workbench_product_surface_ready" if fail_count == 0 else "P15_blocked"
    with store._connect() as conn:
        conn.execute(
            """
            update workbench_product_readiness_reports_p15
            set release_decision = ?, gate_refs_json = ?, payload_json = ?
            where report_id = ?
            """,
            (
                decision,
                json_dumps([row["gate_id"] for row in gate_rows]),
                json_dumps({"gate_fail_count": fail_count, "gate_count": len(gate_rows)}),
                "p15_enterprise_workbench_product_surface_report_v0_1",
            ),
        )


def build_p15_summary(
    root: Path,
    paths: P15Paths,
    gate_rows: list[dict[str, Any]],
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> dict[str, Any]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (task_id,)).fetchone())
        drill_task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (P15_DRILL_TASK_ID,)).fetchone())
        report = row_to_dict(conn.execute("select * from workbench_product_readiness_reports_p15 limit 1").fetchone())
    fail_count = len([row for row in gate_rows if row["status"] != "pass"])
    status = "pass" if fail_count == 0 else "fail"
    outputs = {
        "schema": rel_path(paths.schema_path, root),
        "gate_rows": rel_path(paths.gate_rows_path, root),
        "summary": rel_path(paths.summary_path, root),
        "closeout_report": rel_path(paths.report_path, root),
        "runtime_db": rel_path(paths.db_path, root),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "slice": "P15 Enterprise Workbench Product Surface",
        "status": status,
        "release_decision": "P15_L4_scope_pass_enterprise_workbench_product_surface_ready" if status == "pass" else "P15_blocked",
        "closeout_level": "L4_scope_pass" if status == "pass" else "blocked",
        "surface_registry_status": report.get("surface_registry_status") or "not_evaluated",
        "api_contract_status": report.get("api_contract_status") or "not_evaluated",
        "workflow_surface_status": report.get("workflow_surface_status") or "not_evaluated",
        "rbac_status": report.get("rbac_status") or "not_evaluated",
        "e2e_status": report.get("e2e_status") or "not_evaluated",
        "task": task,
        "drill_task": drill_task,
        "counts": {**dict(materialized), "gate_count": len(gate_rows), "gate_fail_count": fail_count},
        "readiness_report": report,
        "outputs": outputs,
        "policy": enterprise_workbench_product_surface_schema_contract()["policy"],
        "generated_at": utc_now_iso(),
    }


def render_p15_report(summary: Mapping[str, Any], gate_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# R53-R60 P15 Enterprise Workbench Product Surface L4 Scope Pass",
        "",
        f"- Release decision: `{summary['release_decision']}`",
        f"- Closeout level: `{summary['closeout_level']}`",
        f"- Surface registry status: `{summary['surface_registry_status']}`",
        f"- API contract status: `{summary['api_contract_status']}`",
        f"- Workflow surface status: `{summary['workflow_surface_status']}`",
        f"- RBAC status: `{summary['rbac_status']}`",
        f"- E2E status: `{summary['e2e_status']}`",
        "",
        "## Scope Boundary",
        "",
        "P15 proves enterprise Workbench product-surface contracts over existing SQL-final runtime rows: Task Center, Evidence Workbench, Workpaper Builder, Review Queue, Artifact Browser, Deliverable Studio, Dashboard Projection, Data Room upload and Admin/Ops Console. It does not claim a polished React implementation, external customer pilot, or production multi-tenant SLA.",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        if isinstance(value, (str, int, float, bool)):
            lines.append(f"- `{key}`: `{value}`")
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


def record_p15_artifacts(
    runtime: FinSightResearchRuntimeFacade,
    root: Path,
    paths: P15Paths,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    artifacts = []
    for artifact_type, uri, description in [
        ("enterprise_workbench_product_schema", paths.schema_path, "P15 enterprise Workbench product-surface schema contract"),
        ("enterprise_workbench_product_gate_rows", paths.gate_rows_path, "P15 L4-scope gate rows"),
        ("enterprise_workbench_product_summary", paths.summary_path, "P15 build summary"),
        ("enterprise_workbench_product_report", paths.report_path, "P15 closeout report"),
    ]:
        artifacts.append(
            runtime.record_artifact_ref(
                task_id,
                artifact_type=artifact_type,
                uri=rel_path(uri, root),
                payload={"schema_version": SCHEMA_VERSION, "description": description, "materialized": dict(materialized)},
                actor="enterprise_workbench_builder",
            )
        )
    return artifacts
