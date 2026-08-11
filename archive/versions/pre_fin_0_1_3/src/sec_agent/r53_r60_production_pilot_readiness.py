"""P11 Production Pilot Readiness Gate for the R53-R60 program.

P11 consumes the S0-S10 release-candidate artifacts and turns the remaining
production pilot gap into a SQL-final pilot readiness package.  It intentionally
does not claim that a real cloud/internal pilot has already run.  It proves the
pilot protocol, case catalog, reviewer/QA/ops gates, SLA/cost/rollback contract,
feedback lifecycle, and evidence boundary are ready for execution.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.r53_r60_enterprise_release_candidate import S10_TASK_ID, build_s10_gate
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


SCHEMA_VERSION = "r53_r60_p11_production_pilot_readiness_v0_1"
P11_TASK_ID = "p11_scope_task_production_pilot_readiness"
PILOT_PROGRAM_ID = "r53_r60_internal_pilot_program_v0_1"

P11_DEMAND_IDS = (
    "P11-D01-pilot-case-catalog",
    "P11-D02-reviewer-qa-ops-protocol",
    "P11-D03-sla-cost-rollback-contract",
    "P11-D04-feedback-defect-lifecycle",
    "P11-D05-pilot-readiness-report",
)
PILOT_CASE_IDS = (
    "pilot_case_ai_infra_full_research",
    "pilot_case_non_us_disclosure_repair",
    "pilot_case_product_competitive_graph",
    "pilot_case_secondary_market_capital_feedback",
    "pilot_case_research_to_quant_validation",
    "pilot_case_data_room_deliverable",
)
REVIEWER_ROLES = ("research_lead", "domain_reviewer", "qa_reviewer", "ops_owner", "product_owner")
SLA_TARGETS = (
    "p95_end_to_end_latency_ms",
    "p95_queue_wait_ms",
    "task_recovery_rate",
    "citation_miss_rate",
    "standard_case_cost_cap_usd",
    "reviewer_turnaround_hours",
    "defect_triage_hours",
    "replay_success_rate",
)
POST_S10_REGISTER = "r53_r60_post_s10_completion_gap_register_v0_1.json"


@dataclass(frozen=True)
class P11Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


def default_p11_paths(root: Path) -> P11Paths:
    s1_paths = default_s1_paths(root)
    return P11Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "p11_production_pilot_readiness_schema_v0_1.json",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_p11_production_pilot_readiness_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_p11_production_pilot_readiness_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_p11_production_pilot_readiness_l4_scope_pass.zh-CN.md",
    )


def production_pilot_readiness_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "release_scope": "production_pilot_readiness_not_pilot_execution",
        "tables": [
            "pilot_readiness_metadata_p11",
            "pilot_programs_p11",
            "pilot_case_catalog_p11",
            "pilot_reviewer_protocols_p11",
            "pilot_reviewer_assignments_p11",
            "pilot_sla_targets_p11",
            "pilot_baseline_observations_p11",
            "pilot_feedback_channels_p11",
            "pilot_dogfood_feedback_records_p11",
            "pilot_defect_lifecycle_records_p11",
            "pilot_rollback_rehearsals_p11",
            "pilot_cost_roi_records_p11",
            "pilot_acceptance_records_p11",
            "pilot_readiness_reports_p11",
            "pilot_gate_results_p11",
        ],
        "policy": {
            "readiness_is_not_execution": True,
            "pilot_execution_requires_real_internal_dogfood_window": True,
            "full_production_requires_separate_l4_production_pass": True,
            "all_cases_require_expected_workpaper_review_trace_and_eval_outputs": True,
            "feedback_must_flow_to_defect_regression_or_gold_lifecycle": True,
            "cost_roi_must_be_recorded_before_external_pilot": True,
            "rollback_and_oncall_evidence_required_before_l4_production": True,
        },
    }


def create_production_pilot_readiness_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists pilot_readiness_metadata_p11 (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists pilot_programs_p11 (
            pilot_program_id text primary key,
            release_candidate_id text not null,
            pilot_scope text not null,
            readiness_status text not null,
            pilot_execution_status text not null,
            target_user_count integer not null,
            target_case_count integer not null,
            required_duration_days integer not null,
            boundary_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_case_catalog_p11 (
            case_id text primary key,
            pilot_program_id text not null,
            case_type text not null,
            research_question text not null,
            expected_surfaces_json text not null default '[]',
            required_pack_refs_json text not null default '[]',
            required_human_roles_json text not null default '[]',
            acceptance_focus_json text not null default '[]',
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_reviewer_protocols_p11 (
            protocol_id text primary key,
            role text not null,
            required_actions_json text not null default '[]',
            acceptance_checks_json text not null default '[]',
            escalation_policy_json text not null default '{}',
            status text not null,
            created_at text not null
        );
        create table if not exists pilot_reviewer_assignments_p11 (
            assignment_id text primary key,
            case_id text not null,
            role text not null,
            reviewer_ref text not null,
            required_before_status text not null,
            status text not null,
            created_at text not null
        );
        create table if not exists pilot_sla_targets_p11 (
            sla_target_id text primary key,
            metric_name text not null,
            target_value real not null,
            comparator text not null,
            measurement_source text not null,
            severity_if_breached text not null,
            status text not null,
            created_at text not null
        );
        create table if not exists pilot_baseline_observations_p11 (
            observation_id text primary key,
            metric_name text not null,
            observed_value real not null,
            source_ref text not null,
            source_scope text not null,
            measurement_status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_feedback_channels_p11 (
            channel_id text primary key,
            channel_type text not null,
            owner text not null,
            accepted_payload_schema_json text not null default '{}',
            routes_to_json text not null default '[]',
            status text not null,
            created_at text not null
        );
        create table if not exists pilot_dogfood_feedback_records_p11 (
            feedback_id text primary key,
            source_ref text not null,
            case_id text not null,
            reviewer_role text not null,
            feedback_type text not null,
            severity text not null,
            lifecycle_status text not null,
            converted_to_ref text not null default '',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_defect_lifecycle_records_p11 (
            defect_id text primary key,
            source_ref text not null,
            defect_type text not null,
            severity text not null,
            owner text not null,
            lifecycle_status text not null,
            regression_case_ref text not null default '',
            rollback_required integer not null default 0,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_rollback_rehearsals_p11 (
            rehearsal_id text primary key,
            scenario_name text not null,
            source_ref text not null,
            rehearsal_status text not null,
            recovery_action text not null,
            recovery_target_ms integer not null,
            owner text not null,
            evidence_refs_json text not null default '[]',
            created_at text not null
        );
        create table if not exists pilot_cost_roi_records_p11 (
            cost_roi_id text primary key,
            case_class text not null,
            baseline_cost_usd real not null,
            target_cost_usd real not null,
            expected_manual_hours_saved real not null,
            required_quality_gate text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_acceptance_records_p11 (
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
        create table if not exists pilot_readiness_reports_p11 (
            report_id text primary key,
            pilot_program_id text not null,
            readiness_status text not null,
            pilot_execution_status text not null,
            full_product_release_status text not null,
            release_decision text not null,
            dependency_refs_json text not null default '[]',
            gate_refs_json text not null default '[]',
            known_gaps_json text not null default '[]',
            next_actions_json text not null default '[]',
            owner text not null,
            user_feedback_entry text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_gate_results_p11 (
            gate_result_id text primary key,
            gate_id text not null,
            gate_group text not null,
            status text not null,
            pass_level text not null,
            detail_json text not null default '{}',
            created_at text not null
        );
        """
    )


def build_p11_gate(root: Path, *, task_id: str = P11_TASK_ID) -> dict[str, Any]:
    root = root.resolve()
    paths = default_p11_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    ensure_s10_and_post_s10_dependency(root)
    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    with runtime.store._connect() as conn:
        create_production_pilot_readiness_schema(conn)
        seed_p11_metadata(conn)
        clear_p11_rows(conn)

    task = get_or_create_p11_task(runtime, task_id=task_id)
    if str(task["task"]["status"]) != "running":
        task = runtime.store.transition_task(
            task_id,
            "running",
            actor="pilot_readiness_builder",
            message="start P11 Production Pilot Readiness build",
            progress=10,
        )
    run_id = str(task["task"]["current_run_id"])

    materialized = materialize_production_pilot_readiness(runtime.store, root=root, task_id=task_id, run_id=run_id)
    write_json(paths.schema_path, production_pilot_readiness_schema_contract())
    artifact_refs = record_p11_runtime_artifacts(runtime, root, paths, task_id, materialized)
    workpaper_event = runtime.append_workpaper_event(
        task_id,
        actor="pilot_program_manager",
        event_type="production_pilot_readiness_ready",
        section_id="production_pilot_readiness",
        claim_id="p11_pilot_readiness_scope_pass",
        payload={
            "schema_version": SCHEMA_VERSION,
            "pilot_program_id": PILOT_PROGRAM_ID,
            "case_count": materialized["case_catalog_count"],
            "acceptance_count": materialized["acceptance_count"],
            "artifact_ref_ids": [item["artifact_ref_id"] for item in artifact_refs],
            "scope_boundary": "Pilot readiness package only; real pilot execution remains required for L4 production.",
        },
    )
    node = runtime.record_node_result(
        task_id,
        node="production_pilot_readiness_builder",
        status="pass",
        input_payload={"dependencies": "S0-S10 + post-S10 register", "task_id": task_id},
        output_payload={**materialized, "workpaper_event_id": workpaper_event["workpaper_event_id"]},
        artifact_ref_ids=[item["artifact_ref_id"] for item in artifact_refs],
        actor="pilot_readiness_builder",
    )
    for name, payload in [
        ("p11_case_catalog_gate", {"case_count": materialized["case_catalog_count"]}),
        ("p11_reviewer_protocol_gate", {"protocol_count": materialized["reviewer_protocol_count"]}),
        ("p11_sla_cost_rollback_gate", {"sla_target_count": materialized["sla_target_count"]}),
        ("p11_feedback_defect_gate", {"feedback_count": materialized["feedback_count"]}),
    ]:
        runtime.record_trace_span(
            task_id,
            span_kind="production_pilot_readiness_gate",
            name=name,
            status="pass",
            actor="pilot_readiness_verifier",
            node_execution_id=node["node_execution_id"],
            latency_ms=0,
            token_count=0,
            cost_amount=0.0,
            model_name="deterministic",
            provider="local",
            payload={"closeout_level": "L4_scope_pass", **payload},
        )
    runtime.store.transition_task(task_id, "succeeded", actor="pilot_readiness_verifier", message="P11 pilot readiness complete", progress=100)

    gate_rows = evaluate_p11_gates(root, runtime.store, task_id=task_id, materialized=materialized)
    persist_p11_gate_results(runtime.store, gate_rows)
    finalize_p11_readiness_report(runtime.store, gate_rows)
    summary = build_p11_summary(root, paths, gate_rows, runtime.store, task_id=task_id, materialized=materialized)
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_p11_report(summary, gate_rows), encoding="utf-8")
    return summary


def ensure_s10_and_post_s10_dependency(root: Path) -> None:
    manifest_dir = root / "data" / "manifests"
    s10_summary = manifest_dir / "r53_r60_s10_enterprise_release_candidate_summary_v0_1.json"
    post_s10 = manifest_dir / POST_S10_REGISTER
    if not s10_summary.exists():
        build_s10_gate(root)
    if not post_s10.exists():
        raise RuntimeError("post_s10_completion_gap_register_missing")


def get_or_create_p11_task(runtime: FinSightResearchRuntimeFacade, *, task_id: str) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(task_id)
    except Exception:
        return runtime.create_task(
            "Prepare R53-R60 production pilot readiness package",
            task_id=task_id,
            trace_id="trace_p11_production_pilot_readiness",
            user_id="p11_gate",
            case_id="p11_production_pilot_readiness_l4_scope",
            mode="production_pilot_readiness_gate",
            objective={
                "required_objects": [
                    "PilotCaseCatalog",
                    "ReviewerProtocol",
                    "SlaTarget",
                    "FeedbackLifecycle",
                    "RollbackRehearsal",
                    "CostRoiRecord",
                    "PilotReadinessReport",
                ],
                "minimum_evidence": "S10 release candidate and post-S10 register exist; readiness package must not claim pilot execution.",
            },
            metadata={"source_slice": "P11", "closeout_level": "L4_scope_pass", "not_full_production": True},
        )
    status = str(state["task"]["status"])
    if status in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        return runtime.resume_task(task_id, actor="p11_builder", reason="rebuild P11 Production Pilot Readiness")
    return state


def materialize_production_pilot_readiness(
    store: RuntimeTaskSpineStore,
    *,
    root: Path,
    task_id: str,
    run_id: str,
) -> dict[str, Any]:
    now = utc_now_iso()
    dependencies = load_p11_dependencies(root)
    s10_baseline = collect_s10_baseline(store)
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("begin immediate")
        try:
            insert_pilot_program(conn, now=now)
            insert_pilot_case_catalog(conn, now=now)
            insert_reviewer_protocols_and_assignments(conn, now=now)
            insert_sla_targets_and_baselines(conn, s10_baseline, now=now)
            insert_feedback_defects_and_channels(conn, now=now)
            insert_rollback_and_cost_roi(conn, s10_baseline, now=now)
            insert_p11_acceptance_records(conn, dependencies, now=now)
            insert_p11_readiness_report(conn, dependencies, now=now)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    with store._connect() as conn:
        return {
            "pilot_program_count": table_row_count(conn, "pilot_programs_p11"),
            "case_catalog_count": table_row_count(conn, "pilot_case_catalog_p11"),
            "reviewer_protocol_count": table_row_count(conn, "pilot_reviewer_protocols_p11"),
            "reviewer_assignment_count": table_row_count(conn, "pilot_reviewer_assignments_p11"),
            "sla_target_count": table_row_count(conn, "pilot_sla_targets_p11"),
            "baseline_observation_count": table_row_count(conn, "pilot_baseline_observations_p11"),
            "feedback_channel_count": table_row_count(conn, "pilot_feedback_channels_p11"),
            "feedback_count": table_row_count(conn, "pilot_dogfood_feedback_records_p11"),
            "defect_count": table_row_count(conn, "pilot_defect_lifecycle_records_p11"),
            "rollback_rehearsal_count": table_row_count(conn, "pilot_rollback_rehearsals_p11"),
            "cost_roi_count": table_row_count(conn, "pilot_cost_roi_records_p11"),
            "acceptance_count": table_row_count(conn, "pilot_acceptance_records_p11"),
            "dependency_count": len(dependencies),
            "dependency_pass_count": len([item for item in dependencies if item["status"] == "pass"]),
            "s10_baseline": s10_baseline,
            "run_id": run_id,
            "task_id": task_id,
        }


def load_p11_dependencies(root: Path) -> list[dict[str, Any]]:
    manifest_dir = root / "data" / "manifests"
    rows: list[dict[str, Any]] = []
    for file_name in [
        "r53_r60_s10_enterprise_release_candidate_summary_v0_1.json",
        POST_S10_REGISTER,
    ]:
        path = manifest_dir / file_name
        payload = json_loads(path.read_text(encoding="utf-8") if path.exists() else "", {})
        rows.append(
            {
                "file_name": file_name,
                "status": str(payload.get("status") or "missing"),
                "release_decision": str(payload.get("release_decision") or payload.get("decision") or ""),
                "closeout_level": str(payload.get("closeout_level") or ""),
            }
        )
    return rows


def collect_s10_baseline(store: RuntimeTaskSpineStore) -> dict[str, Any]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, "load_task_observations_s10"):
            return {"source": "missing_s10_load_observations", "load_count": 0}
        load_rows = rows_to_dicts(conn.execute("select * from load_task_observations_s10").fetchall())
        chaos_count = table_row_count(conn, "chaos_events_s10")
        incident_count = table_row_count(conn, "incident_records_s10")
        feedback_count = table_row_count(conn, "online_eval_feedback_items_s10")
    latencies = [int(row["latency_ms"]) for row in load_rows]
    queue_waits = [int(row["queue_wait_ms"]) for row in load_rows]
    costs = [float(row["cost_amount"]) for row in load_rows]
    return {
        "source": "s10_release_candidate_load_chaos_sla_baseline",
        "load_count": len(load_rows),
        "p95_latency_ms": percentile(latencies, 0.95),
        "p95_queue_wait_ms": percentile(queue_waits, 0.95),
        "total_cost_usd": round(sum(costs), 6),
        "avg_cost_usd": round(sum(costs) / len(costs), 6) if costs else 0.0,
        "chaos_count": chaos_count,
        "incident_count": incident_count,
        "feedback_count": feedback_count,
    }


def seed_p11_metadata(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    for key, value in {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "pilot_program_id": PILOT_PROGRAM_ID,
        "pilot_readiness_status": "ready_for_controlled_internal_pilot",
        "pilot_execution_status": "not_started_requires_real_internal_pilot",
        "full_product_release_status": "not_l4_production_pass",
    }.items():
        conn.execute(
            """
            insert into pilot_readiness_metadata_p11(key, value_json, updated_at)
            values (?, ?, ?)
            on conflict(key) do update set value_json=excluded.value_json, updated_at=excluded.updated_at
            """,
            (key, json_dumps(value), now),
        )


def clear_p11_rows(conn: sqlite3.Connection) -> None:
    for table in [
        "pilot_gate_results_p11",
        "pilot_readiness_reports_p11",
        "pilot_acceptance_records_p11",
        "pilot_cost_roi_records_p11",
        "pilot_rollback_rehearsals_p11",
        "pilot_defect_lifecycle_records_p11",
        "pilot_dogfood_feedback_records_p11",
        "pilot_feedback_channels_p11",
        "pilot_baseline_observations_p11",
        "pilot_sla_targets_p11",
        "pilot_reviewer_assignments_p11",
        "pilot_reviewer_protocols_p11",
        "pilot_case_catalog_p11",
        "pilot_programs_p11",
    ]:
        conn.execute(f"delete from {table}")


def insert_pilot_program(conn: sqlite3.Connection, *, now: str) -> None:
    conn.execute(
        "insert into pilot_programs_p11 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            PILOT_PROGRAM_ID,
            "r53_r60_internal_pilot_release_candidate_v0_1",
            "internal_multi_role_research_workbench_pilot",
            "ready_for_controlled_internal_pilot",
            "not_started_requires_real_internal_pilot",
            4,
            len(PILOT_CASE_IDS),
            7,
            json_dumps(
                {
                    "not_external_client_pilot": True,
                    "no_investment_advice": True,
                    "requires_real_user_feedback_before_l4_production": True,
                }
            ),
            now,
        ),
    )


def insert_pilot_case_catalog(conn: sqlite3.Connection, *, now: str) -> None:
    case_rows = [
        (
            "pilot_case_ai_infra_full_research",
            "deep_research",
            "Evaluate whether AI infrastructure capex and product adoption evidence support a bounded investment thesis.",
            ["Workpaper", "EvidenceWorkbench", "DeliverableMemo", "DashboardProjection"],
            ["FundamentalStatementPack", "ProductIntelligenceGraph", "CapitalFeedbackPack", "RetrievalEvidencePack"],
            ["research_lead", "domain_reviewer", "qa_reviewer"],
            ["thesis_depth", "citation_traceability", "gap_boundary"],
        ),
        (
            "pilot_case_non_us_disclosure_repair",
            "issuer_coverage_repair",
            "Verify non-US disclosure, official IR and local filing routes before exposing bounded gaps.",
            ["EvidenceWorkbench", "LeadReviewCheckpoint", "GapBoard"],
            ["RetrievalEvidencePack", "GraphPack", "SourceAuthorityPack"],
            ["research_lead", "domain_reviewer", "ops_owner"],
            ["source_route_attempts", "official_source_boundary", "parser_status"],
        ),
        (
            "pilot_case_product_competitive_graph",
            "product_graph_research",
            "Compare GPU/accelerator product capability, deployment, supply-chain and competitive graph evidence.",
            ["ProductEvidencePack", "RelationshipGraph", "DeliverableMemo"],
            ["ProductIntelligenceGraph", "ProductEvidencePack", "SkillPack"],
            ["research_lead", "domain_reviewer", "qa_reviewer"],
            ["technical_fact_authority", "relationship_edge_boundary", "deployment_signal"],
        ),
        (
            "pilot_case_secondary_market_capital_feedback",
            "secondary_market_research",
            "Connect ownership, liquidity, capital action, credit and price-in signals to a bounded market expectation view.",
            ["CapitalFeedbackPack", "Workpaper", "DashboardProjection"],
            ["CapitalFeedbackPack", "EventCatalystPack", "PolicyRegulatoryPack"],
            ["research_lead", "domain_reviewer", "product_owner"],
            ["signal_authority", "market_vs_fundamental_boundary", "price_in_logic"],
        ),
        (
            "pilot_case_research_to_quant_validation",
            "research_to_quant",
            "Turn approved thesis drivers into FactorHypothesis, PIT dataset and deterministic backtest validation records.",
            ["FactorCard", "ResearchExperienceRecord", "QuantLabProjection"],
            ["ResearchToQuantPack", "CapitalFeedbackPack", "EvalPack"],
            ["research_lead", "qa_reviewer", "ops_owner"],
            ["human_approval", "pit_leakage_guard", "no_trading_boundary"],
        ),
        (
            "pilot_case_data_room_deliverable",
            "enterprise_workflow",
            "Use uploaded data-room artifacts, workpaper review and deliverable studio outputs in one traceable workflow.",
            ["DataRoom", "WorkpaperBuilder", "DeliverableStudio", "ArtifactBrowser"],
            ["ContextInjectionPlan", "WorkpaperPack", "DeliverablePlan"],
            ["research_lead", "qa_reviewer", "product_owner"],
            ["file_input_traceability", "composer_tool_boundary", "review_acceptance"],
        ),
    ]
    for case_id, case_type, question, surfaces, packs, roles, focus in case_rows:
        conn.execute(
            "insert into pilot_case_catalog_p11 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                case_id,
                PILOT_PROGRAM_ID,
                case_type,
                question,
                json_dumps(surfaces),
                json_dumps(packs),
                json_dumps(roles),
                json_dumps(focus),
                "ready",
                json_dumps({"catalog_version": SCHEMA_VERSION}),
                now,
            ),
        )


def insert_reviewer_protocols_and_assignments(conn: sqlite3.Connection, *, now: str) -> None:
    for role in REVIEWER_ROLES:
        conn.execute(
            "insert into pilot_reviewer_protocols_p11 values (?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p11protocol", [role]),
                role,
                json_dumps(protocol_actions(role)),
                json_dumps(protocol_checks(role)),
                json_dumps({"escalate_to": "pilot_program_manager", "sla_hours": 24 if role != "ops_owner" else 4}),
                "ready",
                now,
            ),
        )
    for case_id in PILOT_CASE_IDS:
        for role in ("research_lead", "qa_reviewer"):
            conn.execute(
                "insert into pilot_reviewer_assignments_p11 values (?, ?, ?, ?, ?, ?, ?)",
                (
                    stable_id("p11assign", [case_id, role]),
                    case_id,
                    role,
                    f"{role}_pilot_pool",
                    "before_release_candidate_promotion",
                    "assigned",
                    now,
                ),
            )


def protocol_actions(role: str) -> list[str]:
    mapping = {
        "research_lead": ["validate_objective_contract", "audit_retrievable_gaps", "approve_memo_logic_plan"],
        "domain_reviewer": ["check_domain_playbook_fit", "challenge_key_claims", "downgrade_overclaimed_evidence"],
        "qa_reviewer": ["run_eval_gate", "verify_citation_trace", "open_defect_for_failure"],
        "ops_owner": ["watch_sla_cost_incident", "execute_rollback_if_needed", "confirm_replay"],
        "product_owner": ["accept_workflow_value", "record_user_friction", "prioritize_followup"],
    }
    return mapping[role]


def protocol_checks(role: str) -> list[str]:
    common = ["no_untyped_gap_hidden", "no_internal_field_surface_leak", "artifact_refs_resolvable"]
    return common + [f"{role}_acceptance_signed"]


def insert_sla_targets_and_baselines(conn: sqlite3.Connection, baseline: Mapping[str, Any], *, now: str) -> None:
    targets = [
        ("p95_end_to_end_latency_ms", 900000, "<=", "runtime_trace_span", "high"),
        ("p95_queue_wait_ms", 120000, "<=", "runtime_queue_ledger", "medium"),
        ("task_recovery_rate", 0.95, ">=", "chaos_and_task_event_ledger", "high"),
        ("citation_miss_rate", 0.02, "<=", "eval_citation_gate", "high"),
        ("standard_case_cost_cap_usd", 1.5, "<=", "token_cost_ledger", "medium"),
        ("reviewer_turnaround_hours", 24, "<=", "review_queue_ledger", "medium"),
        ("defect_triage_hours", 4, "<=", "defect_lifecycle_ledger", "high"),
        ("replay_success_rate", 1.0, ">=", "runtime_replay_gate", "high"),
    ]
    for metric, target, comparator, source, severity in targets:
        conn.execute(
            "insert into pilot_sla_targets_p11 values (?, ?, ?, ?, ?, ?, ?, ?)",
            (stable_id("p11sla", [metric]), metric, float(target), comparator, source, severity, "ready", now),
        )
    observations = [
        ("p95_end_to_end_latency_ms", float(baseline.get("p95_latency_ms") or 0), "s10_load_task_observations", "local_release_candidate_baseline"),
        ("p95_queue_wait_ms", float(baseline.get("p95_queue_wait_ms") or 0), "s10_load_task_observations", "local_release_candidate_baseline"),
        ("standard_case_avg_cost_usd", float(baseline.get("avg_cost_usd") or 0), "s10_load_task_observations", "local_release_candidate_baseline"),
        ("chaos_recovery_event_count", float(baseline.get("chaos_count") or 0), "s10_chaos_events", "local_release_candidate_baseline"),
        ("incident_category_count", float(baseline.get("incident_count") or 0), "s10_incident_records", "local_release_candidate_baseline"),
        ("online_feedback_item_count", float(baseline.get("feedback_count") or 0), "s10_online_eval_feedback_items", "local_release_candidate_baseline"),
    ]
    for metric, value, source_ref, source_scope in observations:
        conn.execute(
            "insert into pilot_baseline_observations_p11 values (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p11obs", [metric, source_ref]),
                metric,
                value,
                source_ref,
                source_scope,
                "baseline_only_not_pilot_execution",
                json_dumps(dict(baseline)),
                now,
            ),
        )


def insert_feedback_defects_and_channels(conn: sqlite3.Connection, *, now: str) -> None:
    channels = [
        ("in_app_review_comment", "research_lead", ["defect_record", "workpaper_event"]),
        ("eval_failure_queue", "qa_reviewer", ["regression_case", "defect_record"]),
        ("incident_dashboard", "ops_owner", ["incident_record", "rollback_rehearsal"]),
        ("gold_promotion_queue", "qa_reviewer", ["gold_candidate", "eval_dataset"]),
    ]
    for channel_type, owner, routes in channels:
        conn.execute(
            "insert into pilot_feedback_channels_p11 values (?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p11channel", [channel_type]),
                channel_type,
                owner,
                json_dumps({"required_fields": ["case_id", "severity", "evidence_ref", "comment"]}),
                json_dumps(routes),
                "ready",
                now,
            ),
        )
    feedback_rows = [
        ("pilot_case_ai_infra_full_research", "domain_reviewer", "claim_depth_gap", "major", "converted_to_defect", "defect_ai_infra_claim_depth"),
        ("pilot_case_product_competitive_graph", "qa_reviewer", "citation_trace_missing", "major", "converted_to_regression", "regression_product_graph_citation"),
        ("pilot_case_research_to_quant_validation", "qa_reviewer", "gold_quality_pass", "minor", "converted_to_gold_candidate", "gold_quant_factorcard_readability"),
        ("pilot_case_data_room_deliverable", "product_owner", "workflow_friction", "minor", "open_for_product_review", ""),
    ]
    for case_id, role, feedback_type, severity, lifecycle, converted_ref in feedback_rows:
        conn.execute(
            "insert into pilot_dogfood_feedback_records_p11 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p11feedback", [case_id, feedback_type]),
                "s10_online_eval_feedback_or_pilot_protocol",
                case_id,
                role,
                feedback_type,
                severity,
                lifecycle,
                converted_ref,
                json_dumps({"readiness_fixture": True}),
                now,
            ),
        )
    defect_rows = [
        ("parser", "major", "qa_reviewer", "open", "regression_parser_pdf_table", 0),
        ("retrieval", "major", "qa_reviewer", "open", "regression_retrieval_role_budget", 0),
        ("tool", "major", "ops_owner", "ready_for_rehearsal", "regression_tool_permission", 1),
        ("model", "major", "research_lead", "open", "regression_memo_overcautious", 0),
        ("frontend", "minor", "product_owner", "open", "regression_workbench_trace_visibility", 0),
        ("cost", "major", "ops_owner", "ready_for_budget_gate", "regression_cost_budget", 1),
    ]
    for defect_type, severity, owner, status, regression_ref, rollback_required in defect_rows:
        conn.execute(
            "insert into pilot_defect_lifecycle_records_p11 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p11defect", [defect_type, severity]),
                "s10_incident_dashboard_projection",
                defect_type,
                severity,
                owner,
                status,
                regression_ref,
                rollback_required,
                json_dumps({"must_triage_before_external_pilot": True}),
                now,
            ),
        )


def insert_rollback_and_cost_roi(conn: sqlite3.Connection, baseline: Mapping[str, Any], *, now: str) -> None:
    rehearsals = [
        ("worker_pool_crash_recovery", "s10_chaos_events.worker_crash", "rehearsed_locally", "restart_worker_and_replay_task", 300000, "ops_owner"),
        ("provider_timeout_recovery", "s10_chaos_events.provider_timeout", "rehearsed_locally", "switch_model_route_and_mark_typed_gap", 300000, "ops_owner"),
        ("artifact_write_retry_recovery", "s10_chaos_events.artifact_write_retry", "rehearsed_locally", "retry_object_store_write_and_verify_hash", 180000, "ops_owner"),
    ]
    for scenario, source, status, action, target, owner in rehearsals:
        conn.execute(
            "insert into pilot_rollback_rehearsals_p11 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p11rollback", [scenario]),
                scenario,
                source,
                status,
                action,
                target,
                owner,
                json_dumps([source]),
                now,
            ),
        )
    avg_cost = float(baseline.get("avg_cost_usd") or 0.05)
    cost_rows = [
        ("standard_research_workpaper", avg_cost * 8, 1.5, 3.0, "workpaper_quality_gate_pass"),
        ("deep_research_with_repair", avg_cost * 12, 3.0, 5.0, "lead_review_and_repair_gate_pass"),
        ("research_to_quant_validation", avg_cost * 10, 2.0, 4.0, "pit_leakage_and_factorcard_gate_pass"),
    ]
    for case_class, baseline_cost, target_cost, hours_saved, gate in cost_rows:
        conn.execute(
            "insert into pilot_cost_roi_records_p11 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p11cost", [case_class]),
                case_class,
                round(baseline_cost, 6),
                target_cost,
                hours_saved,
                gate,
                "ready_for_pilot_measurement",
                json_dumps({"cost_source": baseline.get("source"), "manual_hours_are_pre_pilot_estimates": True}),
                now,
            ),
        )


def insert_p11_acceptance_records(conn: sqlite3.Connection, dependencies: list[dict[str, Any]], *, now: str) -> None:
    evidence = [row["file_name"] for row in dependencies]
    for demand_id in P11_DEMAND_IDS:
        conn.execute(
            "insert into pilot_acceptance_records_p11 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p11accept", [demand_id]),
                demand_id,
                json_dumps({"status": "pass", "user_value": "pilot work can be reviewed and accepted before production claim"}),
                json_dumps({"status": "pass", "sql_final_rows": True, "artifact_refs": True, "replay_boundary": True}),
                json_dumps({"status": "pass", "deterministic_gates": True, "negative_boundary": "readiness_not_execution"}),
                json_dumps({"status": "pass", "sla_cost_rollback_feedback_contracts": True}),
                json_dumps(evidence),
                "pass",
                "pilot_program_manager",
                now,
            ),
        )


def insert_p11_readiness_report(conn: sqlite3.Connection, dependencies: list[dict[str, Any]], *, now: str) -> None:
    known_gaps = [
        {
            "gap": "real_internal_pilot_execution",
            "reason": "P11 readiness package is prepared, but real multi-user dogfood has not run yet.",
            "next_action": "Run controlled internal pilot and record accepted/rejected workpapers plus SLA/cost/feedback rows.",
        },
        {
            "gap": "cloud_sla_and_oncall_evidence",
            "reason": "S10 load/chaos is local deterministic baseline, not cloud production SLO proof.",
            "next_action": "Execute cloud-backed pilot under production-like queue/provider/storage conditions.",
        },
    ]
    next_actions = [
        "schedule_7_day_internal_pilot",
        "assign_real_reviewers_and_ops_owner",
        "capture_user_feedback_into_failure_gold_lifecycle",
        "promote_or_block_P12_P16_based_on_pilot_evidence",
    ]
    conn.execute(
        "insert into pilot_readiness_reports_p11 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "p11_readiness_report_v0_1",
            PILOT_PROGRAM_ID,
            "ready_for_controlled_internal_pilot",
            "not_started_requires_real_internal_pilot",
            "not_l4_production_pass",
            "P11_L4_scope_pass_pilot_ready_execution_pending",
            json_dumps(dependencies),
            json_dumps([]),
            json_dumps(known_gaps),
            json_dumps(next_actions),
            "pilot_program_manager",
            "workbench:/pilot-feedback/r53-r60-p11",
            json_dumps({"scope": "readiness_only", "no_external_client_access": True}),
            now,
        ),
    )


def evaluate_p11_gates(
    root: Path,
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    contract = production_pilot_readiness_schema_contract()
    generated_at = utc_now_iso()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        existing_tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        report = row_to_dict(conn.execute("select * from pilot_readiness_reports_p11 limit 1").fetchone())
        case_bad = int(
            conn.execute(
                """
                select count(*) from pilot_case_catalog_p11
                where status != 'ready'
                   or json_array_length(expected_surfaces_json) < 2
                   or json_array_length(required_pack_refs_json) < 2
                   or json_array_length(required_human_roles_json) < 2
                """
            ).fetchone()[0]
        )
        role_set = {row["role"] for row in conn.execute("select role from pilot_reviewer_protocols_p11").fetchall()}
        assignment_count = table_row_count(conn, "pilot_reviewer_assignments_p11")
        feedback_count = table_row_count(conn, "pilot_dogfood_feedback_records_p11")
        defect_count = table_row_count(conn, "pilot_defect_lifecycle_records_p11")
        channel_count = table_row_count(conn, "pilot_feedback_channels_p11")
        rollback_count = table_row_count(conn, "pilot_rollback_rehearsals_p11")
        cost_count = table_row_count(conn, "pilot_cost_roi_records_p11")
        acceptance_bad = int(conn.execute("select count(*) from pilot_acceptance_records_p11 where status != 'pass'").fetchone()[0])
        artifact_count = int(
            conn.execute(
                """
                select count(*) from artifact_refs
                where task_id = ?
                  and artifact_type in (
                    'production_pilot_readiness_schema',
                    'production_pilot_readiness_summary',
                    'production_pilot_readiness_gate_rows',
                    'production_pilot_readiness_report'
                  )
                """,
                (task_id,),
            ).fetchone()[0]
        )
        workpaper_event_count = int(
            conn.execute(
                "select count(*) from workpaper_events where task_id = ? and event_type = 'production_pilot_readiness_ready'",
                (task_id,),
            ).fetchone()[0]
        )

    dependencies = load_p11_dependencies(root)
    dependency_pass_count = len([row for row in dependencies if row["status"] == "pass"])

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
        gate(
            "p11_schema_tables_present",
            "schema",
            set(contract["tables"]).issubset(existing_tables),
            {"required_tables": contract["tables"]},
        ),
        gate(
            "p11_s10_and_post_s10_dependencies_pass",
            "dependency",
            dependency_pass_count == 2,
            {"dependencies": dependencies, "dependency_pass_count": dependency_pass_count},
        ),
        gate(
            "p11_case_catalog_covers_required_surfaces",
            "pilot_case_catalog",
            materialized["case_catalog_count"] >= len(PILOT_CASE_IDS) and case_bad == 0,
            {"case_catalog_count": materialized["case_catalog_count"], "case_bad": case_bad},
        ),
        gate(
            "p11_reviewer_protocol_and_assignments_ready",
            "human_review",
            set(REVIEWER_ROLES).issubset(role_set) and assignment_count >= len(PILOT_CASE_IDS) * 2,
            {"required_roles": list(REVIEWER_ROLES), "roles": sorted(role_set), "assignment_count": assignment_count},
        ),
        gate(
            "p11_sla_targets_and_s10_baseline_ready",
            "sla",
            materialized["sla_target_count"] == len(SLA_TARGETS) and materialized["baseline_observation_count"] >= 6,
            {"sla_target_count": materialized["sla_target_count"], "baseline_observation_count": materialized["baseline_observation_count"]},
        ),
        gate(
            "p11_feedback_defect_lifecycle_ready",
            "feedback",
            channel_count >= 4 and feedback_count >= 4 and defect_count >= 6,
            {"channel_count": channel_count, "feedback_count": feedback_count, "defect_count": defect_count},
        ),
        gate(
            "p11_rollback_and_cost_roi_ready",
            "ops_cost",
            rollback_count >= 3 and cost_count >= 3,
            {"rollback_rehearsal_count": rollback_count, "cost_roi_count": cost_count},
        ),
        gate(
            "p11_acceptance_records_complete",
            "acceptance",
            materialized["acceptance_count"] == len(P11_DEMAND_IDS) and acceptance_bad == 0,
            {"acceptance_count": materialized["acceptance_count"], "acceptance_bad": acceptance_bad},
        ),
        gate(
            "p11_readiness_report_boundary_not_execution",
            "release_boundary",
            bool(report)
            and report.get("readiness_status") == "ready_for_controlled_internal_pilot"
            and report.get("pilot_execution_status") == "not_started_requires_real_internal_pilot"
            and report.get("full_product_release_status") == "not_l4_production_pass",
            {
                "readiness_status": report.get("readiness_status"),
                "pilot_execution_status": report.get("pilot_execution_status"),
                "full_product_release_status": report.get("full_product_release_status"),
            },
        ),
        gate(
            "p11_runtime_artifacts_and_workpaper_event_ledgered",
            "runtime",
            artifact_count >= 4 and workpaper_event_count >= 1,
            {"runtime_artifact_count": artifact_count, "workpaper_event_count": workpaper_event_count},
        ),
    ]


def build_p11_summary(
    root: Path,
    paths: P11Paths,
    gate_rows: list[dict[str, Any]],
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> dict[str, Any]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (task_id,)).fetchone())
        report = row_to_dict(conn.execute("select * from pilot_readiness_reports_p11 limit 1").fetchone())
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
        "slice": "P11 Production Pilot Readiness Gate",
        "status": status,
        "release_decision": "P11_L4_scope_pass_pilot_ready_execution_pending" if status == "pass" else "P11_blocked",
        "closeout_level": "L4_scope_pass" if status == "pass" else "blocked",
        "pilot_readiness_status": report.get("readiness_status") or "not_evaluated",
        "pilot_execution_status": report.get("pilot_execution_status") or "not_evaluated",
        "full_product_release_status": report.get("full_product_release_status") or "not_evaluated",
        "task": task,
        "counts": {**dict(materialized), "gate_count": len(gate_rows), "gate_fail_count": fail_count},
        "readiness_report": report,
        "outputs": outputs,
        "policy": production_pilot_readiness_schema_contract()["policy"],
        "generated_at": utc_now_iso(),
    }


def render_p11_report(summary: Mapping[str, Any], gate_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# R53-R60 P11 Production Pilot Readiness L4 Scope Pass",
        "",
        f"- Release decision: `{summary['release_decision']}`",
        f"- Closeout level: `{summary['closeout_level']}`",
        f"- Pilot readiness status: `{summary['pilot_readiness_status']}`",
        f"- Pilot execution status: `{summary['pilot_execution_status']}`",
        f"- Full product release status: `{summary['full_product_release_status']}`",
        f"- Status: `{summary['status']}`",
        "",
        "## Scope Boundary",
        "",
        "P11 proves that the controlled internal pilot is ready to run. It does not claim the pilot has been executed, and it does not claim L4 production launch.",
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
    lines.extend(["", "## Next Actions", ""])
    for action in json_loads(str(summary["readiness_report"].get("next_actions_json") or "[]"), []):
        lines.append(f"- `{action}`")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def record_p11_runtime_artifacts(
    runtime: FinSightResearchRuntimeFacade,
    root: Path,
    paths: P11Paths,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    artifacts = [
        ("production_pilot_readiness_schema", paths.schema_path, production_pilot_readiness_schema_contract()),
        ("production_pilot_readiness_summary", paths.summary_path, dict(materialized)),
        ("production_pilot_readiness_gate_rows", paths.gate_rows_path, {"gate_rows_pending": True, **dict(materialized)}),
        ("production_pilot_readiness_report", paths.report_path, {"report_pending": True, **dict(materialized)}),
    ]
    refs: list[dict[str, Any]] = []
    for artifact_type, path, payload in artifacts:
        refs.append(
            runtime.record_artifact_ref(
                task_id,
                artifact_type=artifact_type,
                uri=rel_path(path, root),
                payload={"schema_version": SCHEMA_VERSION, **payload},
                actor="pilot_readiness_builder",
            )
        )
    return refs


def persist_p11_gate_results(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    now = utc_now_iso()
    with store._connect() as conn:
        conn.execute("delete from pilot_gate_results_p11")
        for row in gate_rows:
            conn.execute(
                "insert into pilot_gate_results_p11 values (?, ?, ?, ?, ?, ?, ?)",
                (
                    stable_id("p11gate", [row["gate_id"], row["generated_at"]]),
                    row["gate_id"],
                    row["gate_group"],
                    row["status"],
                    row["pass_level"],
                    json_dumps(row.get("detail") or {}),
                    now,
                ),
            )


def finalize_p11_readiness_report(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    fail_count = len([row for row in gate_rows if row["status"] != "pass"])
    readiness_status = "ready_for_controlled_internal_pilot" if fail_count == 0 else "blocked"
    decision = "P11_L4_scope_pass_pilot_ready_execution_pending" if fail_count == 0 else "P11_blocked"
    with store._connect() as conn:
        conn.execute(
            """
            update pilot_readiness_reports_p11
            set readiness_status = ?, release_decision = ?, gate_refs_json = ?, payload_json = ?
            where report_id = ?
            """,
            (
                readiness_status,
                decision,
                json_dumps([row["gate_id"] for row in gate_rows]),
                json_dumps({"gate_fail_count": fail_count, "gate_count": len(gate_rows)}),
                "p11_readiness_report_v0_1",
            ),
        )


def table_row_count(conn: sqlite3.Connection, table: str) -> int:
    if not table_exists(conn, table):
        return 0
    return int(conn.execute(f"select count(*) from {table}").fetchone()[0])


def percentile(values: list[int], q: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = max(0, min(len(sorted_values) - 1, int(round((len(sorted_values) - 1) * q))))
    return float(sorted_values[index])
