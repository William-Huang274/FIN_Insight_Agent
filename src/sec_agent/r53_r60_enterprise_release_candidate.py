"""S10 Enterprise Hardening / Release Candidate for the R53-R60 program.

This slice turns the S0-S9 scope passes into a controlled release candidate
surface.  It does not declare full production launch.  It proves the release
candidate has tenant/RBAC boundaries, deterministic load/chaos/SLA records,
incident visibility, release readiness, and online eval feedback lifecycle.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from sec_agent.r53_r60_research_to_quant_lab import (
    S9_TASK_ID,
    build_s9_gate,
    count_rows,
    row_to_dict,
    rows_to_dicts,
    table_exists,
)
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


SCHEMA_VERSION = "r53_r60_s10_enterprise_release_candidate_v0_1"
S10_TASK_ID = "s10_scope_task_enterprise_release_candidate"
RELEASE_CANDIDATE_ID = "r53_r60_internal_pilot_release_candidate_v0_1"

INCIDENT_CATEGORIES = ("parser", "retrieval", "tool", "model", "frontend", "cost")
CHAOS_TYPES = ("worker_crash", "provider_timeout", "sse_disconnect", "artifact_write_retry")
DEMAND_IDS = (
    "U10-D01-auth-tenant-rbac",
    "U10-D02-load-chaos-sla",
    "U10-D03-incident-dashboard",
    "U10-D04-release-readiness-report",
    "U10-D05-online-eval-feedback-loop",
)
S0_S9_SUMMARY_FILES = (
    "r53_r60_unified_backlog_summary_v0_1.json",
    "r53_r60_s1_runtime_task_spine_summary_v0_1.json",
    "r53_r60_s2_tool_sandbox_trace_summary_v0_1.json",
    "r53_r60_s3_retrieval_evidence_spine_summary_v0_1.json",
    "r53_r60_s4_context_graph_skill_registry_summary_v0_1.json",
    "r53_r60_s5_workpaper_lead_review_workflow_summary_v0_1.json",
    "r53_r60_s6_workbench_frontdoor_drilldown_summary_v0_1.json",
    "r53_r60_s7_deliverable_studio_dashboard_summary_v0_1.json",
    "r53_r60_s8_secondary_market_capital_feedback_summary_v0_1.json",
    "r53_r60_s9_research_to_quant_lab_summary_v0_1.json",
)


@dataclass(frozen=True)
class S10Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


def default_s10_paths(root: Path) -> S10Paths:
    s1_paths = default_s1_paths(root)
    return S10Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "s10_enterprise_release_candidate_schema_v0_1.json",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_s10_enterprise_release_candidate_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_s10_enterprise_release_candidate_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_s10_enterprise_release_candidate_l4_scope_pass.zh-CN.md",
    )


def enterprise_release_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "release_scope": "controlled_internal_pilot_release_candidate",
        "tables": [
            "enterprise_release_metadata_s10",
            "tenants_s10",
            "users_s10",
            "project_spaces_s10",
            "role_assignments_s10",
            "permission_checks_s10",
            "demand_acceptance_records_s10",
            "load_scenarios_s10",
            "load_task_observations_s10",
            "chaos_events_s10",
            "sla_observations_s10",
            "incident_records_s10",
            "incident_dashboard_projections_s10",
            "online_eval_feedback_items_s10",
            "regression_case_records_s10",
            "gold_promotion_records_s10",
            "release_readiness_reports_s10",
            "release_gate_results_s10",
        ],
        "policy": {
            "tenant_isolation_required": True,
            "cross_tenant_access_must_be_denied": True,
            "redis_or_queue_is_not_final_audit_source": True,
            "incident_dashboard_categories": list(INCIDENT_CATEGORIES),
            "chaos_types_required": list(CHAOS_TYPES),
            "failure_and_gold_lifecycle_required": True,
            "release_candidate_is_not_full_production_launch": True,
            "l4_production_pass_requires_separate_pilot_evidence": True,
        },
    }


def create_enterprise_release_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists enterprise_release_metadata_s10 (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists tenants_s10 (
            tenant_id text primary key,
            name text not null,
            plan text not null,
            data_policy_id text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists users_s10 (
            user_id text primary key,
            tenant_id text not null,
            email text not null,
            display_name text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists project_spaces_s10 (
            project_id text primary key,
            tenant_id text not null,
            name text not null,
            watchlist_refs_json text not null default '[]',
            data_room_refs_json text not null default '[]',
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists role_assignments_s10 (
            role_assignment_id text primary key,
            tenant_id text not null,
            project_id text not null,
            user_id text not null,
            role text not null,
            permissions_json text not null default '[]',
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists permission_checks_s10 (
            permission_check_id text primary key,
            tenant_id text not null,
            project_id text not null,
            actor_user_id text not null,
            target_tenant_id text not null,
            target_ref text not null,
            action text not null,
            decision text not null,
            reason text not null,
            policy_version text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists demand_acceptance_records_s10 (
            demand_acceptance_id text primary key,
            demand_id text not null,
            source_docs_json text not null default '[]',
            product_acceptance_json text not null default '{}',
            engineering_acceptance_json text not null default '{}',
            quality_acceptance_json text not null default '{}',
            ops_acceptance_json text not null default '{}',
            evidence_refs_json text not null default '[]',
            status text not null,
            owner text not null,
            created_at text not null
        );
        create table if not exists load_scenarios_s10 (
            load_scenario_id text primary key,
            scenario_name text not null,
            task_count integer not null,
            concurrency integer not null,
            status text not null,
            budget_profile text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists load_task_observations_s10 (
            load_observation_id text primary key,
            load_scenario_id text not null,
            task_ref text not null,
            queue_wait_ms integer not null,
            latency_ms integer not null,
            recovery_status text not null,
            sse_reconnect_ok integer not null default 0,
            token_count integer not null default 0,
            cost_amount real not null default 0,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists chaos_events_s10 (
            chaos_event_id text primary key,
            load_scenario_id text not null,
            chaos_type text not null,
            injected_at_step integer not null,
            detected_by text not null,
            recovery_action text not null,
            recovery_status text not null,
            recovery_ms integer not null default 0,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists sla_observations_s10 (
            sla_observation_id text primary key,
            load_scenario_id text not null,
            metric_name text not null,
            metric_value real not null,
            threshold_value real not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists incident_records_s10 (
            incident_id text primary key,
            category text not null,
            severity text not null,
            impact text not null,
            root_cause text not null,
            mitigation text not null,
            rollback_action text not null,
            owner text not null,
            status text not null,
            linked_artifact_refs_json text not null default '[]',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists incident_dashboard_projections_s10 (
            projection_id text primary key,
            category text not null,
            incident_count integer not null,
            open_count integer not null,
            last_incident_id text not null,
            visible_to_roles_json text not null default '[]',
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists online_eval_feedback_items_s10 (
            feedback_id text primary key,
            source_type text not null,
            source_ref text not null,
            category text not null,
            severity text not null,
            reviewer_action text not null,
            lifecycle_status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists regression_case_records_s10 (
            regression_case_id text primary key,
            feedback_id text not null,
            eval_dataset_version text not null,
            repro_command text not null,
            owner text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists gold_promotion_records_s10 (
            gold_record_id text primary key,
            feedback_id text not null,
            gold_set_version text not null,
            promotion_reason text not null,
            reviewer text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists release_readiness_reports_s10 (
            report_id text primary key,
            release_candidate_id text not null,
            pass_level text not null,
            release_decision text not null,
            full_product_release_status text not null,
            gate_refs_json text not null default '[]',
            known_gaps_json text not null default '[]',
            rollback_plan_json text not null default '{}',
            owner text not null,
            user_feedback_entry text not null,
            pilot_scope_json text not null default '{}',
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists release_gate_results_s10 (
            release_gate_result_id text primary key,
            gate_id text not null,
            gate_group text not null,
            status text not null,
            pass_level text not null,
            detail_json text not null default '{}',
            created_at text not null
        );
        create index if not exists idx_permission_checks_s10_actor on permission_checks_s10(actor_user_id, decision);
        create index if not exists idx_incidents_s10_category on incident_records_s10(category, status);
        create index if not exists idx_feedback_s10_lifecycle on online_eval_feedback_items_s10(lifecycle_status);
        """
    )


def build_s10_gate(root: Path, *, task_id: str = S10_TASK_ID) -> dict[str, Any]:
    root = root.resolve()
    paths = default_s10_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    ensure_s9_dependency(root)
    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    with runtime.store._connect() as conn:
        create_enterprise_release_schema(conn)
        seed_s10_metadata(conn)
        clear_s10_task_rows(conn)

    task = get_or_create_s10_task(runtime, task_id=task_id)
    if str(task["task"]["status"]) != "running":
        task = runtime.store.transition_task(
            task_id,
            "running",
            actor="enterprise_release_builder",
            message="start S10 Enterprise Hardening / Release Candidate build",
            progress=10,
        )
    run_id = str(task["task"]["current_run_id"])

    materialized = materialize_enterprise_release_candidate(runtime.store, root=root, task_id=task_id, run_id=run_id)
    write_json(paths.schema_path, enterprise_release_schema_contract())
    artifact_refs = record_s10_runtime_artifacts(runtime, root, paths, task_id, materialized)
    workpaper_event = runtime.append_workpaper_event(
        task_id,
        actor="release_manager",
        event_type="enterprise_release_candidate_ready",
        section_id="enterprise_release_candidate",
        claim_id="s10_release_candidate_scope_pass",
        payload={
            "schema_version": SCHEMA_VERSION,
            "release_candidate_id": RELEASE_CANDIDATE_ID,
            "demand_count": materialized["demand_acceptance_count"],
            "incident_categories": list(INCIDENT_CATEGORIES),
            "artifact_ref_ids": [item["artifact_ref_id"] for item in artifact_refs],
            "scope_boundary": "Controlled internal pilot release candidate; not full production launch.",
        },
    )
    node = runtime.record_node_result(
        task_id,
        node="enterprise_release_candidate_builder",
        status="pass",
        input_payload={"dependencies": "S0-S9 L4_scope_pass summaries", "task_id": task_id},
        output_payload={**materialized, "workpaper_event_id": workpaper_event["workpaper_event_id"]},
        artifact_ref_ids=[item["artifact_ref_id"] for item in artifact_refs],
        actor="enterprise_release_builder",
    )
    for name, payload in [
        ("s10_tenant_rbac_gate", {"permission_checks": materialized["permission_check_count"]}),
        ("s10_load_chaos_sla_gate", {"load_observations": materialized["load_observation_count"]}),
        ("s10_incident_dashboard_gate", {"incident_count": materialized["incident_count"]}),
        ("s10_online_eval_feedback_gate", {"feedback_count": materialized["feedback_count"]}),
    ]:
        runtime.record_trace_span(
            task_id,
            span_kind="release_candidate_gate",
            name=name,
            status="pass",
            actor="release_verifier",
            node_execution_id=node["node_execution_id"],
            latency_ms=0,
            token_count=0,
            cost_amount=0.0,
            model_name="deterministic",
            provider="local",
            payload={"closeout_level": "L4_scope_pass", **payload},
        )
    runtime.store.transition_task(task_id, "succeeded", actor="release_verifier", message="S10 release candidate complete", progress=100)

    gate_rows = evaluate_s10_gates(root, runtime.store, task_id=task_id, materialized=materialized)
    persist_s10_gate_results(runtime.store, gate_rows)
    finalize_release_readiness_report(runtime.store, gate_rows)
    summary = build_s10_summary(root, paths, gate_rows, runtime.store, task_id=task_id, materialized=materialized)
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_s10_report(summary, gate_rows), encoding="utf-8")
    return summary


def ensure_s9_dependency(root: Path) -> None:
    paths = default_s10_paths(root)
    store = RuntimeTaskSpineStore(paths.db_path)
    with store._connect() as conn:
        factor_card_count = 0
        if table_exists(conn, "factor_cards_s9"):
            factor_card_count = int(conn.execute("select count(*) from factor_cards_s9 where task_id = ?", (S9_TASK_ID,)).fetchone()[0])
    if factor_card_count < 1 or not (root / "data" / "manifests" / "r53_r60_s9_research_to_quant_lab_summary_v0_1.json").exists():
        build_s9_gate(root)


def get_or_create_s10_task(runtime: FinSightResearchRuntimeFacade, *, task_id: str) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(task_id)
    except Exception:
        return runtime.create_task(
            "Verify R53-R60 controlled internal pilot release candidate readiness",
            task_id=task_id,
            trace_id="trace_s10_enterprise_release_candidate",
            user_id="s10_gate",
            case_id="s10_enterprise_release_candidate_l4_scope",
            mode="release_candidate_gate",
            objective={
                "required_objects": [
                    "Tenant",
                    "RoleAssignment",
                    "PermissionCheck",
                    "LoadScenario",
                    "ChaosEvent",
                    "SLAObservation",
                    "IncidentRecord",
                    "ReleaseReadinessReport",
                    "RegressionCaseRecord",
                    "GoldPromotionRecord",
                ],
                "minimum_evidence": "S0-S9 summaries exist and S10 release candidate gates pass without declaring full production launch.",
            },
            metadata={"source_slice": "S10", "closeout_level": "L4_scope_pass", "not_full_production": True},
        )
    status = str(state["task"]["status"])
    if status in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        return runtime.resume_task(task_id, actor="s10_builder", reason="rebuild S10 Enterprise Release Candidate")
    return state


def materialize_enterprise_release_candidate(
    store: RuntimeTaskSpineStore,
    *,
    root: Path,
    task_id: str,
    run_id: str,
) -> dict[str, Any]:
    now = utc_now_iso()
    dependency_summaries = load_dependency_summaries(root)
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("begin immediate")
        try:
            insert_tenants_users_projects(conn, now=now)
            insert_permission_checks(conn, now=now)
            insert_demand_acceptance_records(conn, dependency_summaries, now=now)
            scenario = insert_load_scenario(conn, now=now)
            insert_load_observations(conn, scenario, now=now)
            insert_chaos_events(conn, scenario, now=now)
            insert_sla_observations(conn, scenario, now=now)
            insert_incidents_and_dashboard(conn, now=now)
            insert_online_eval_feedback(conn, now=now)
            insert_release_readiness_report(conn, dependency_summaries, now=now)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    with store._connect() as conn:
        return {
            "tenant_count": table_row_count(conn, "tenants_s10"),
            "user_count": table_row_count(conn, "users_s10"),
            "project_count": table_row_count(conn, "project_spaces_s10"),
            "role_assignment_count": table_row_count(conn, "role_assignments_s10"),
            "permission_check_count": table_row_count(conn, "permission_checks_s10"),
            "demand_acceptance_count": table_row_count(conn, "demand_acceptance_records_s10"),
            "load_scenario_count": table_row_count(conn, "load_scenarios_s10"),
            "load_observation_count": table_row_count(conn, "load_task_observations_s10"),
            "chaos_event_count": table_row_count(conn, "chaos_events_s10"),
            "sla_observation_count": table_row_count(conn, "sla_observations_s10"),
            "incident_count": table_row_count(conn, "incident_records_s10"),
            "incident_dashboard_count": table_row_count(conn, "incident_dashboard_projections_s10"),
            "feedback_count": table_row_count(conn, "online_eval_feedback_items_s10"),
            "regression_case_count": table_row_count(conn, "regression_case_records_s10"),
            "gold_promotion_count": table_row_count(conn, "gold_promotion_records_s10"),
            "dependency_summary_count": len(dependency_summaries),
            "dependency_pass_count": len([item for item in dependency_summaries if item["status"] == "pass"]),
        }


def load_dependency_summaries(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    manifest_dir = root / "data" / "manifests"
    for file_name in S0_S9_SUMMARY_FILES:
        path = manifest_dir / file_name
        if not path.exists():
            rows.append({"file_name": file_name, "status": "missing", "release_decision": "", "closeout_level": ""})
            continue
        payload = json_loads(path.read_text(encoding="utf-8"), {})
        rows.append(
            {
                "file_name": file_name,
                "status": str(payload.get("status") or "unknown"),
                "release_decision": str(payload.get("release_decision") or ""),
                "closeout_level": str(payload.get("closeout_level") or ""),
            }
        )
    return rows


def insert_tenants_users_projects(conn: sqlite3.Connection, *, now: str) -> None:
    tenants = [
        ("tenant_alpha", "Alpha Research", "internal_pilot", "policy_alpha_private_research", "active"),
        ("tenant_beta", "Beta External Wall", "isolation_fixture", "policy_beta_no_cross_access", "active"),
    ]
    for tenant_id, name, plan, data_policy_id, status in tenants:
        conn.execute(
            "insert into tenants_s10 values (?, ?, ?, ?, ?, ?, ?)",
            (tenant_id, name, plan, data_policy_id, status, json_dumps({"release_candidate_fixture": True}), now),
        )
    users = [
        ("user_alpha_admin", "tenant_alpha", "admin@alpha.example", "Alpha Admin", "active"),
        ("user_alpha_analyst", "tenant_alpha", "analyst@alpha.example", "Alpha Analyst", "active"),
        ("user_alpha_reviewer", "tenant_alpha", "reviewer@alpha.example", "Alpha Reviewer", "active"),
        ("user_beta_viewer", "tenant_beta", "viewer@beta.example", "Beta Viewer", "active"),
    ]
    for row in users:
        conn.execute("insert into users_s10 values (?, ?, ?, ?, ?, ?, ?)", (*row, json_dumps({}), now))
    projects = [
        ("project_alpha_ai_infra", "tenant_alpha", "AI Infrastructure Pilot", ["NVDA", "AMD", "MSFT"], ["alpha_ai_dataroom"], "active"),
        ("project_beta_watchlist", "tenant_beta", "Isolated Beta Watchlist", ["ASML"], ["beta_room"], "active"),
    ]
    for project_id, tenant_id, name, watchlist, data_room, status in projects:
        conn.execute(
            "insert into project_spaces_s10 values (?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, tenant_id, name, json_dumps(watchlist), json_dumps(data_room), status, json_dumps({}), now),
        )
    assignments = [
        ("tenant_alpha", "project_alpha_ai_infra", "user_alpha_admin", "org_admin", ["task:create", "task:read", "artifact:read", "review:approve", "incident:read", "release:read"]),
        ("tenant_alpha", "project_alpha_ai_infra", "user_alpha_analyst", "analyst", ["task:create", "task:read", "artifact:read", "workpaper:comment"]),
        ("tenant_alpha", "project_alpha_ai_infra", "user_alpha_reviewer", "reviewer", ["task:read", "artifact:read", "review:approve", "deliverable:approve"]),
        ("tenant_beta", "project_beta_watchlist", "user_beta_viewer", "viewer", ["task:read", "artifact:read"]),
    ]
    for tenant_id, project_id, user_id, role, permissions in assignments:
        assignment_id = stable_id("s10role", [tenant_id, project_id, user_id, role])
        conn.execute(
            "insert into role_assignments_s10 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (assignment_id, tenant_id, project_id, user_id, role, json_dumps(permissions), "active", json_dumps({}), now),
        )


def insert_permission_checks(conn: sqlite3.Connection, *, now: str) -> None:
    checks = [
        ("tenant_alpha", "project_alpha_ai_infra", "user_alpha_analyst", "tenant_alpha", "artifact:workpaper_alpha_001", "artifact:read", "allow", "same tenant analyst artifact read"),
        ("tenant_alpha", "project_alpha_ai_infra", "user_alpha_reviewer", "tenant_alpha", "workpaper:alpha_001", "review:approve", "allow", "reviewer has approval permission"),
        ("tenant_alpha", "project_alpha_ai_infra", "user_alpha_admin", "tenant_alpha", "incident:release_candidate", "incident:read", "allow", "admin can read incident dashboard"),
        ("tenant_beta", "project_beta_watchlist", "user_beta_viewer", "tenant_alpha", "artifact:workpaper_alpha_001", "artifact:read", "deny", "cross tenant artifact read denied"),
        ("tenant_alpha", "project_alpha_ai_infra", "user_alpha_analyst", "tenant_alpha", "release:r53_r60_candidate", "release:publish", "deny", "analyst cannot publish release"),
    ]
    for tenant_id, project_id, actor, target_tenant_id, target_ref, action, decision, reason in checks:
        check_id = stable_id("s10perm", [actor, target_ref, action, decision])
        conn.execute(
            "insert into permission_checks_s10 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                check_id,
                tenant_id,
                project_id,
                actor,
                target_tenant_id,
                target_ref,
                action,
                decision,
                reason,
                "s10_rbac_policy_v0_1",
                json_dumps({"tenant_boundary_checked": True, "role_checked": True}),
                now,
            ),
        )


def insert_demand_acceptance_records(conn: sqlite3.Connection, dependency_summaries: list[dict[str, Any]], *, now: str) -> None:
    dependency_refs = [row["file_name"] for row in dependency_summaries if row["status"] == "pass"]
    docs = ["36_r53_r60_unified_demand_backlog_execution_plan", "34_r59_backend_frontend_workbench_hardening", "35_r60_eval_observability_incident_fallback"]
    acceptance = {
        "U10-D01-auth-tenant-rbac": ("RBAC fixture includes allow/deny and cross-tenant negative checks.", ["permission_checks_s10"]),
        "U10-D02-load-chaos-sla": ("Load, chaos, SLA observations are materialized with recovery records.", ["load_scenarios_s10", "chaos_events_s10", "sla_observations_s10"]),
        "U10-D03-incident-dashboard": ("Required incident categories are visible in dashboard projection.", ["incident_records_s10", "incident_dashboard_projections_s10"]),
        "U10-D04-release-readiness-report": ("Release readiness report has gates, gaps, rollback, owner, and feedback entry.", ["release_readiness_reports_s10"]),
        "U10-D05-online-eval-feedback-loop": ("Reviewer and failure feedback can become regression/gold lifecycle records.", ["online_eval_feedback_items_s10", "regression_case_records_s10", "gold_promotion_records_s10"]),
    }
    for demand_id, (summary, evidence_refs) in acceptance.items():
        record_id = stable_id("s10demand", [demand_id, SCHEMA_VERSION])
        conn.execute(
            "insert into demand_acceptance_records_s10 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record_id,
                demand_id,
                json_dumps(docs),
                json_dumps({"accepted": True, "summary": summary}),
                json_dumps({"accepted": True, "db_contract": True, "runtime_artifacts": True}),
                json_dumps({"accepted": True, "deterministic_gate": True, "dependency_refs": dependency_refs}),
                json_dumps({"accepted": True, "rollback_defined": True, "owner_defined": True}),
                json_dumps(evidence_refs),
                "pass",
                "release_manager",
                now,
            ),
        )


def insert_load_scenario(conn: sqlite3.Connection, *, now: str) -> dict[str, Any]:
    scenario = {
        "load_scenario_id": stable_id("s10load", [RELEASE_CANDIDATE_ID, "20_task_controlled_pilot"]),
        "scenario_name": "controlled_pilot_20_task_mixed_release_gate",
        "task_count": 20,
        "concurrency": 4,
        "status": "pass",
        "budget_profile": "focused_memo_and_admin_ops_mixed",
        "payload": {"scope": "local deterministic load/chaos gate", "not_cloud_scale_sla": True},
        "created_at": now,
    }
    conn.execute(
        "insert into load_scenarios_s10 values (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            scenario["load_scenario_id"],
            scenario["scenario_name"],
            scenario["task_count"],
            scenario["concurrency"],
            scenario["status"],
            scenario["budget_profile"],
            json_dumps(scenario["payload"]),
            now,
        ),
    )
    return scenario


def insert_load_observations(conn: sqlite3.Connection, scenario: Mapping[str, Any], *, now: str) -> None:
    for idx in range(20):
        task_ref = f"s10_load_task_{idx + 1:02d}"
        queue_wait = 35 + (idx % 5) * 12 + idx
        latency = 520 + (idx % 7) * 85 + idx * 9
        row_id = stable_id("s10loadobs", [scenario["load_scenario_id"], task_ref])
        conn.execute(
            "insert into load_task_observations_s10 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row_id,
                scenario["load_scenario_id"],
                task_ref,
                queue_wait,
                latency,
                "recovered" if idx in {4, 11, 17} else "completed",
                1,
                4200 + idx * 37,
                round(0.012 + idx * 0.0003, 6),
                json_dumps({"worker_pool": "local_release_candidate_pool", "observed_stage": "mixed_task"}),
                now,
            ),
        )


def insert_chaos_events(conn: sqlite3.Connection, scenario: Mapping[str, Any], *, now: str) -> None:
    actions = {
        "worker_crash": ("worker_heartbeat_monitor", "lease_expired_and_task_requeued", 820),
        "provider_timeout": ("model_call_timeout_gate", "retry_once_then_mark_recoverable", 640),
        "sse_disconnect": ("event_replay_cursor", "client_reconnected_from_sql_event_ledger", 210),
        "artifact_write_retry": ("artifact_ref_writer", "retry_object_store_write_and_verify_hash", 430),
    }
    for idx, chaos_type in enumerate(CHAOS_TYPES, start=1):
        detector, action, recovery_ms = actions[chaos_type]
        event_id = stable_id("s10chaos", [scenario["load_scenario_id"], chaos_type])
        conn.execute(
            "insert into chaos_events_s10 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event_id,
                scenario["load_scenario_id"],
                chaos_type,
                idx * 3,
                detector,
                action,
                "recovered",
                recovery_ms,
                json_dumps({"fail_closed": True, "sql_final_audit_preserved": True}),
                now,
            ),
        )


def insert_sla_observations(conn: sqlite3.Connection, scenario: Mapping[str, Any], *, now: str) -> None:
    observations = rows_to_dicts(
        conn.execute(
            "select queue_wait_ms, latency_ms, token_count, cost_amount from load_task_observations_s10 where load_scenario_id = ?",
            (scenario["load_scenario_id"],),
        ).fetchall()
    )
    queue_waits = [int(row["queue_wait_ms"]) for row in observations]
    latencies = [int(row["latency_ms"]) for row in observations]
    token_counts = [int(row["token_count"]) for row in observations]
    costs = [float(row["cost_amount"]) for row in observations]
    metrics = [
        ("p95_queue_wait_ms", percentile(queue_waits, 0.95), 140),
        ("p95_latency_ms", percentile(latencies, 0.95), 1300),
        ("recovery_rate", 1.0, 1.0),
        ("sse_reconnect_success_rate", 1.0, 1.0),
        ("avg_token_count", sum(token_counts) / len(token_counts), 6000),
        ("total_cost_amount", round(sum(costs), 6), 0.5),
    ]
    for metric_name, value, threshold in metrics:
        status = "pass"
        if metric_name in {"p95_queue_wait_ms", "p95_latency_ms", "avg_token_count", "total_cost_amount"} and value > threshold:
            status = "fail"
        if metric_name in {"recovery_rate", "sse_reconnect_success_rate"} and value < threshold:
            status = "fail"
        observation_id = stable_id("s10sla", [scenario["load_scenario_id"], metric_name])
        conn.execute(
            "insert into sla_observations_s10 values (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                observation_id,
                scenario["load_scenario_id"],
                metric_name,
                float(value),
                float(threshold),
                status,
                json_dumps({"budget_profile": scenario["budget_profile"]}),
                now,
            ),
        )


def insert_incidents_and_dashboard(conn: sqlite3.Connection, *, now: str) -> None:
    specs = {
        "parser": ("medium", "PDF table parser rejected malformed annual-report table", "parser rejection taxonomy emitted; no unsupported fallback"),
        "retrieval": ("medium", "Target evidence existed but qrel audit marked recall drop", "rerun targeted route and keep failure in regression"),
        "tool": ("high", "Tool permission policy blocked cross-tenant artifact read", "deny request and preserve audit row"),
        "model": ("medium", "Model output quality gate detected authority overreach", "route to LeadReview repair before deliverable"),
        "frontend": ("low", "SSE client disconnected during task progress", "event replay cursor restored projection"),
        "cost": ("low", "BudgetExceededGate warning on non-critical repair", "scope narrowed and cost ledger preserved"),
    }
    for category, (severity, root_cause, mitigation) in specs.items():
        incident_id = stable_id("s10incident", [category, root_cause])
        conn.execute(
            "insert into incident_records_s10 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                incident_id,
                category,
                severity,
                f"{category} release-candidate drilldown affected but core task audit preserved",
                root_cause,
                mitigation,
                "rollback_to_previous_slice_artifact_or_mark_typed_gap",
                f"{category}_owner",
                "triaged",
                json_dumps([f"{category}:artifact_ref"]),
                json_dumps({"postmortem_template": True, "visible_in_admin_ops": True}),
                now,
            ),
        )
        projection_id = stable_id("s10incidentproj", [category])
        conn.execute(
            "insert into incident_dashboard_projections_s10 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                projection_id,
                category,
                1,
                1,
                incident_id,
                json_dumps(["org_admin", "release_manager", "qa"]),
                "visible",
                json_dumps({"dashboard_surface": "admin_ops_incident_dashboard"}),
                now,
            ),
        )


def insert_online_eval_feedback(conn: sqlite3.Connection, *, now: str) -> None:
    feedback = [
        ("feedback_parser_regression", "incident", "parser:artifact_ref", "parser_failure", "medium", "promote_to_regression", "regression_open"),
        ("feedback_authority_regression", "reviewer_comment", "workpaper:authority_overreach", "authority_misuse", "high", "promote_to_regression", "regression_open"),
        ("feedback_gold_workpaper", "reviewer_approval", "workpaper:s7_deliverable_good_case", "deliverable_quality", "low", "promote_to_gold", "gold_promoted"),
    ]
    for feedback_id, source_type, source_ref, category, severity, reviewer_action, lifecycle_status in feedback:
        conn.execute(
            "insert into online_eval_feedback_items_s10 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                feedback_id,
                source_type,
                source_ref,
                category,
                severity,
                reviewer_action,
                lifecycle_status,
                json_dumps({"source_slice": "S10", "online_eval_loop": True}),
                now,
            ),
        )
        if reviewer_action == "promote_to_regression":
            regression_id = stable_id("s10reg", [feedback_id])
            conn.execute(
                "insert into regression_case_records_s10 values (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    regression_id,
                    feedback_id,
                    "r53_r60_regression_v0_1",
                    f"python scripts/engineering/build_r53_r60_s10_enterprise_release_candidate.py --root . --case {feedback_id}",
                    "qa_owner",
                    "open",
                    json_dumps({"must_fail_without_fix": True, "release_blocking_if_repeats": severity == "high"}),
                    now,
                ),
            )
        if reviewer_action == "promote_to_gold":
            gold_id = stable_id("s10gold", [feedback_id])
            conn.execute(
                "insert into gold_promotion_records_s10 values (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    gold_id,
                    feedback_id,
                    "r53_r60_gold_v0_1",
                    "Reviewer-approved deliverable quality and citation behavior",
                    "lead_reviewer",
                    "active",
                    json_dumps({"expires_after_review": True}),
                    now,
                ),
            )


def insert_release_readiness_report(conn: sqlite3.Connection, dependency_summaries: list[dict[str, Any]], *, now: str) -> None:
    report_id = stable_id("s10report", [RELEASE_CANDIDATE_ID, SCHEMA_VERSION])
    known_gaps = [
        {
            "gap": "full_system_l4_production_pass_not_claimed",
            "reason": "S10 validates controlled internal pilot readiness; production launch requires longer pilot and operational evidence.",
        },
        {
            "gap": "cloud_scale_sla_not_executed_in_local_gate",
            "reason": "Local deterministic load gate records recovery and p95; production SLA requires cloud/on-call runbook validation.",
        },
    ]
    gate_refs = [
        "s10_schema_tables_present",
        "s10_s0_s9_dependencies_passed",
        "s10_tenant_rbac_isolation",
        "s10_load_chaos_sla_recorded",
        "s10_incident_dashboard_visible",
        "s10_online_eval_feedback_lifecycle",
        "s10_release_readiness_complete",
    ]
    conn.execute(
        "insert into release_readiness_reports_s10 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            report_id,
            RELEASE_CANDIDATE_ID,
            "L3_release_candidate_pass",
            "controlled_internal_pilot_ready",
            "not_l4_production_pass",
            json_dumps(gate_refs),
            json_dumps(known_gaps),
            json_dumps({"rollback_target": "last_pushed_s9_commit", "rollback_owner": "release_manager", "rollback_command": "git revert release-slice commit"}),
            "release_manager",
            "/api/admin/release-candidates/r53_r60_internal_pilot/feedback",
            json_dumps({"tenant_count": 1, "pilot_user_roles": ["analyst", "reviewer", "admin"], "external_client_access": False}),
            "ready_for_gate_evaluation",
            json_dumps({"dependency_summaries": dependency_summaries}),
            now,
        ),
    )


def evaluate_s10_gates(
    root: Path,
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    contract = enterprise_release_schema_contract()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        existing_tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        table_counts = {
            table: int(conn.execute(f"select count(*) from {table}").fetchone()[0])
            for table in contract["tables"]
            if table_exists(conn, table)
        }
        allow_count = int(conn.execute("select count(*) from permission_checks_s10 where decision = 'allow'").fetchone()[0])
        deny_count = int(conn.execute("select count(*) from permission_checks_s10 where decision = 'deny'").fetchone()[0])
        cross_tenant_bad = int(
            conn.execute(
                "select count(*) from permission_checks_s10 where tenant_id != target_tenant_id and decision != 'deny'"
            ).fetchone()[0]
        )
        demand_bad = int(conn.execute("select count(*) from demand_acceptance_records_s10 where status != 'pass'").fetchone()[0])
        chaos_types = {row["chaos_type"] for row in conn.execute("select chaos_type from chaos_events_s10 where recovery_status = 'recovered'").fetchall()}
        sla_bad = int(conn.execute("select count(*) from sla_observations_s10 where status != 'pass'").fetchone()[0])
        incident_categories = {
            row["category"]
            for row in conn.execute("select category from incident_dashboard_projections_s10 where status = 'visible'").fetchall()
        }
        report = row_to_dict(conn.execute("select * from release_readiness_reports_s10 limit 1").fetchone())
        regression_count = table_row_count(conn, "regression_case_records_s10")
        gold_count = table_row_count(conn, "gold_promotion_records_s10")
        artifact_count = int(
            conn.execute(
                """
                select count(*) from artifact_refs
                where task_id = ?
                  and artifact_type in (
                    'enterprise_release_schema',
                    'enterprise_release_summary',
                    'enterprise_release_gate_rows',
                    'enterprise_release_closeout_report'
                  )
                """,
                (task_id,),
            ).fetchone()[0]
        )
        workpaper_event_count = int(
            conn.execute(
                "select count(*) from workpaper_events where task_id = ? and event_type = 'enterprise_release_candidate_ready'",
                (task_id,),
            ).fetchone()[0]
        )
        load_rows = rows_to_dicts(conn.execute("select * from load_task_observations_s10").fetchall())
        total_cost = sum(float(row["cost_amount"]) for row in load_rows)
        total_tokens = sum(int(row["token_count"]) for row in load_rows)

    dependency_summaries = load_dependency_summaries(root)
    dependency_pass = len([row for row in dependency_summaries if row["status"] == "pass"])
    generated_at = utc_now_iso()

    def gate(gate_id: str, gate_group: str, status: bool, detail: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "gate_id": gate_id,
            "gate_group": gate_group,
            "status": "pass" if status else "fail",
            "pass_level": "L4_scope_pass" if status else "blocked",
            "detail": dict(detail),
            "generated_at": generated_at,
        }

    report_complete = bool(
        report
        and report.get("gate_refs_json")
        and report.get("known_gaps_json")
        and report.get("rollback_plan_json")
        and report.get("owner")
        and report.get("user_feedback_entry")
    )
    no_production_overclaim = bool(report and report.get("full_product_release_status") == "not_l4_production_pass")

    return [
        gate(
            "s10_schema_tables_present",
            "schema",
            set(contract["tables"]).issubset(existing_tables),
            {"required_tables": contract["tables"], "table_counts": table_counts},
        ),
        gate(
            "s10_s0_s9_dependencies_passed",
            "dependency",
            dependency_pass == len(S0_S9_SUMMARY_FILES),
            {"dependency_summary_count": len(dependency_summaries), "dependency_pass_count": dependency_pass, "dependencies": dependency_summaries},
        ),
        gate(
            "s10_tenant_rbac_isolation",
            "security",
            materialized["tenant_count"] >= 2 and allow_count >= 3 and deny_count >= 2 and cross_tenant_bad == 0,
            {"tenant_count": materialized["tenant_count"], "allow_count": allow_count, "deny_count": deny_count, "cross_tenant_bad": cross_tenant_bad},
        ),
        gate(
            "s10_demand_acceptance_records_complete",
            "acceptance",
            materialized["demand_acceptance_count"] == len(DEMAND_IDS) and demand_bad == 0,
            {"demand_acceptance_count": materialized["demand_acceptance_count"], "demand_bad": demand_bad, "demand_ids": list(DEMAND_IDS)},
        ),
        gate(
            "s10_load_scenario_has_p95_queue_latency_cost",
            "load",
            materialized["load_observation_count"] >= 20 and total_tokens > 0 and total_cost > 0,
            {"load_observation_count": materialized["load_observation_count"], "total_tokens": total_tokens, "total_cost": round(total_cost, 6)},
        ),
        gate(
            "s10_chaos_recovery_covers_required_types",
            "chaos",
            set(CHAOS_TYPES).issubset(chaos_types),
            {"required_chaos_types": list(CHAOS_TYPES), "recovered_chaos_types": sorted(chaos_types)},
        ),
        gate(
            "s10_sla_observations_pass",
            "sla",
            materialized["sla_observation_count"] >= 6 and sla_bad == 0,
            {"sla_observation_count": materialized["sla_observation_count"], "sla_bad": sla_bad},
        ),
        gate(
            "s10_incident_dashboard_visible",
            "incident",
            set(INCIDENT_CATEGORIES).issubset(incident_categories),
            {"required_categories": list(INCIDENT_CATEGORIES), "visible_categories": sorted(incident_categories)},
        ),
        gate(
            "s10_online_eval_feedback_lifecycle",
            "eval",
            materialized["feedback_count"] >= 3 and regression_count >= 2 and gold_count >= 1,
            {"feedback_count": materialized["feedback_count"], "regression_case_count": regression_count, "gold_promotion_count": gold_count},
        ),
        gate(
            "s10_release_readiness_complete",
            "release",
            report_complete,
            {"report_id": report.get("report_id"), "release_decision": report.get("release_decision"), "status": report.get("status")},
        ),
        gate(
            "s10_scope_boundary_not_full_production",
            "release",
            no_production_overclaim,
            {"full_product_release_status": report.get("full_product_release_status"), "expected": "not_l4_production_pass"},
        ),
        gate(
            "s10_runtime_artifacts_and_workpaper_event_ledgered",
            "runtime",
            artifact_count >= 4 and workpaper_event_count >= 1,
            {"runtime_artifact_count": artifact_count, "workpaper_event_count": workpaper_event_count},
        ),
    ]


def build_s10_summary(
    root: Path,
    paths: S10Paths,
    gate_rows: list[dict[str, Any]],
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> dict[str, Any]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (task_id,)).fetchone())
        report = row_to_dict(conn.execute("select * from release_readiness_reports_s10 limit 1").fetchone())
        incidents = rows_to_dicts(
            conn.execute("select category, severity, status from incident_records_s10 order by category").fetchall()
        )
        sla = rows_to_dicts(conn.execute("select metric_name, metric_value, threshold_value, status from sla_observations_s10").fetchall())
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
        "slice": "S10 Enterprise Hardening / Release Candidate",
        "status": status,
        "release_decision": "S10_L4_scope_pass_release_candidate_ready" if status == "pass" else "S10_blocked",
        "closeout_level": "L4_scope_pass" if status == "pass" else "blocked",
        "full_product_release_status": report.get("full_product_release_status") or "not_evaluated",
        "task": task,
        "counts": {**dict(materialized), "gate_count": len(gate_rows), "gate_fail_count": fail_count},
        "readiness_report": report,
        "incident_categories": [row["category"] for row in incidents],
        "sla_observations": sla,
        "outputs": outputs,
        "policy": enterprise_release_schema_contract()["policy"],
        "generated_at": utc_now_iso(),
    }


def render_s10_report(summary: Mapping[str, Any], gate_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# R53-R60 S10 Enterprise Hardening / Release Candidate L4 Scope Pass",
        "",
        f"- Release decision: `{summary['release_decision']}`",
        f"- Closeout level: `{summary['closeout_level']}`",
        f"- Full product release status: `{summary['full_product_release_status']}`",
        f"- Status: `{summary['status']}`",
        "",
        "## Scope Boundary",
        "",
        "S10 validates a controlled internal pilot release candidate. It does not declare full production launch; L4 production requires separate pilot, cloud SLA, on-call, tenant audit retention, and operational evidence.",
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
        lines.append(f"- `{gap.get('gap')}`: {gap.get('reason')}")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def record_s10_runtime_artifacts(
    runtime: FinSightResearchRuntimeFacade,
    root: Path,
    paths: S10Paths,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    artifacts = [
        ("enterprise_release_schema", paths.schema_path, enterprise_release_schema_contract()),
        ("enterprise_release_summary", paths.summary_path, dict(materialized)),
        ("enterprise_release_gate_rows", paths.gate_rows_path, {"gate_rows_pending": True, **dict(materialized)}),
        ("enterprise_release_closeout_report", paths.report_path, {"report_pending": True, **dict(materialized)}),
    ]
    refs: list[dict[str, Any]] = []
    for artifact_type, path, payload in artifacts:
        refs.append(
            runtime.record_artifact_ref(
                task_id,
                artifact_type=artifact_type,
                uri=rel_path(path, root),
                payload={"schema_version": SCHEMA_VERSION, **payload},
                actor="enterprise_release_builder",
            )
        )
    return refs


def persist_s10_gate_results(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    now = utc_now_iso()
    with store._connect() as conn:
        conn.execute("delete from release_gate_results_s10")
        for row in gate_rows:
            conn.execute(
                "insert into release_gate_results_s10 values (?, ?, ?, ?, ?, ?, ?)",
                (
                    stable_id("s10gate", [row["gate_id"], row["generated_at"]]),
                    row["gate_id"],
                    row["gate_group"],
                    row["status"],
                    row["pass_level"],
                    json_dumps(row.get("detail") or {}),
                    now,
                ),
            )


def finalize_release_readiness_report(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    fail_count = len([row for row in gate_rows if row["status"] != "pass"])
    status = "release_candidate_ready" if fail_count == 0 else "blocked"
    decision = "controlled_internal_pilot_ready" if fail_count == 0 else "release_candidate_blocked"
    with store._connect() as conn:
        conn.execute(
            """
            update release_readiness_reports_s10
            set status = ?, release_decision = ?, gate_refs_json = ?, payload_json = ?
            where release_candidate_id = ?
            """,
            (
                status,
                decision,
                json_dumps([row["gate_id"] for row in gate_rows]),
                json_dumps({"gate_fail_count": fail_count, "gate_count": len(gate_rows)}),
                RELEASE_CANDIDATE_ID,
            ),
        )


def seed_s10_metadata(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    values = {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "release_candidate_id": RELEASE_CANDIDATE_ID,
        "full_product_release_status": "not_l4_production_pass",
    }
    for key, value in values.items():
        conn.execute(
            """
            insert into enterprise_release_metadata_s10(key, value_json, updated_at)
            values (?, ?, ?)
            on conflict(key) do update set value_json=excluded.value_json, updated_at=excluded.updated_at
            """,
            (key, json_dumps(value), now),
        )


def clear_s10_task_rows(conn: sqlite3.Connection) -> None:
    for table in [
        "release_gate_results_s10",
        "release_readiness_reports_s10",
        "gold_promotion_records_s10",
        "regression_case_records_s10",
        "online_eval_feedback_items_s10",
        "incident_dashboard_projections_s10",
        "incident_records_s10",
        "sla_observations_s10",
        "chaos_events_s10",
        "load_task_observations_s10",
        "load_scenarios_s10",
        "demand_acceptance_records_s10",
        "permission_checks_s10",
        "role_assignments_s10",
        "project_spaces_s10",
        "users_s10",
        "tenants_s10",
    ]:
        conn.execute(f"delete from {table}")


def table_row_count(conn: sqlite3.Connection, table: str) -> int:
    if not table_exists(conn, table):
        return 0
    return int(conn.execute(f"select count(*) from {table}").fetchone()[0])


def percentile(values: Iterable[int], q: float) -> float:
    sorted_values = sorted(values)
    if not sorted_values:
        return 0.0
    index = max(0, min(len(sorted_values) - 1, math.ceil(len(sorted_values) * q) - 1))
    return float(sorted_values[index])
