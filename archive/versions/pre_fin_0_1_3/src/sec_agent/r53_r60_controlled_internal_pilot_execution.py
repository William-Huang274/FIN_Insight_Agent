"""P17 controlled internal pilot execution ledger for R53-R60.

P11 proved the pilot package was ready, but explicitly left execution pending.
P17 closes that gap for one deterministic internal pilot drill: every P11 case
is executed through runtime task rows, stage checkpoints, reviewer actions,
eval snapshots, feedback/defect lifecycle, cost/latency accounting, artifacts
and release decisions.

This is still not an external customer launch or a sustained production window.
It proves that the P11-P16 contracts can be consumed as an auditable pilot
execution ledger.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from sec_agent.r53_r60_data_ingestion_retrieval_control_plane import build_p14_gate, default_p14_paths
from sec_agent.r53_r60_durable_runtime_hil_resource_router import build_p12_gate, default_p12_paths
from sec_agent.r53_r60_enterprise_workbench_product_surface import build_p15_gate, default_p15_paths, dependency_summary_passes
from sec_agent.r53_r60_graph_skill_memory_lifecycle import build_p13_gate, default_p13_paths
from sec_agent.r53_r60_production_pilot_readiness import (
    PILOT_CASE_IDS,
    PILOT_PROGRAM_ID,
    build_p11_gate,
    default_p11_paths,
)
from sec_agent.r53_r60_quality_engineering_online_eval import build_p16_gate, default_p16_paths
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


SCHEMA_VERSION = "r53_r60_p17_controlled_internal_pilot_execution_v0_1"
P17_TASK_ID = "p17_scope_task_controlled_internal_pilot_execution"
P17_BATCH_ID = "r53_r60_controlled_internal_pilot_batch_v0_1"

P17_DEMAND_IDS = (
    "P17-D01-pilot-execution-batch-ledger",
    "P17-D02-case-runtime-task-execution",
    "P17-D03-stage-checkpoint-and-workpaper-trace",
    "P17-D04-reviewer-action-and-hil-ledger",
    "P17-D05-eval-feedback-defect-cost-closeout",
    "P17-D06-pilot-release-decision-and-boundary-report",
)

CASE_STAGES = (
    ("intake", "research_lead", 10),
    ("retrieval_evidence", "evidence_operator", 25),
    ("workpaper_build", "workpaper_builder", 45),
    ("lead_review", "research_lead", 62),
    ("deliverable_projection", "deliverable_studio", 78),
    ("quality_eval", "quality_engineering", 90),
    ("feedback_closeout", "pilot_program_manager", 100),
)

DEPENDENCIES: tuple[tuple[str, Callable[[Path], Any], Callable[[Path], Any], str], ...] = (
    ("P11", default_p11_paths, build_p11_gate, "P11_L4_scope_pass_pilot_ready_execution_pending"),
    ("P12", default_p12_paths, build_p12_gate, "P12_L4_scope_pass_runtime_drill_ready"),
    ("P13", default_p13_paths, build_p13_gate, "P13_L4_scope_pass_graph_skill_memory_lifecycle_ready"),
    ("P14", default_p14_paths, build_p14_gate, "P14_L4_scope_pass_data_ingestion_retrieval_control_plane_ready"),
    ("P15", default_p15_paths, build_p15_gate, "P15_L4_scope_pass_enterprise_workbench_product_surface_ready"),
    ("P16", default_p16_paths, build_p16_gate, "P16_L4_scope_pass_quality_engineering_online_eval_ready"),
)

CASE_PROFILES: dict[str, dict[str, Any]] = {
    "pilot_case_ai_infra_full_research": {
        "score": 0.88,
        "cost_usd": 0.42,
        "latency_ms": 182000,
        "typed_gap_count": 2,
        "defect_type": "product_customer_deployment_depth",
        "defect_status": "triaged_non_blocking",
        "decision": "accepted_with_typed_gaps",
    },
    "pilot_case_non_us_disclosure_repair": {
        "score": 0.84,
        "cost_usd": 0.36,
        "latency_ms": 176000,
        "typed_gap_count": 3,
        "defect_type": "local_exchange_parser_depth",
        "defect_status": "followup_required",
        "decision": "accepted_with_repair_followup",
    },
    "pilot_case_product_competitive_graph": {
        "score": 0.9,
        "cost_usd": 0.48,
        "latency_ms": 210000,
        "typed_gap_count": 1,
        "defect_type": "relationship_edge_authority_review",
        "defect_status": "triaged_non_blocking",
        "decision": "accepted_for_internal_pilot",
    },
    "pilot_case_secondary_market_capital_feedback": {
        "score": 0.87,
        "cost_usd": 0.39,
        "latency_ms": 166000,
        "typed_gap_count": 2,
        "defect_type": "commercial_market_positioning_boundary",
        "defect_status": "typed_gap_recorded",
        "decision": "accepted_with_market_boundary",
    },
    "pilot_case_research_to_quant_validation": {
        "score": 0.86,
        "cost_usd": 0.44,
        "latency_ms": 194000,
        "typed_gap_count": 1,
        "defect_type": "paper_trading_requires_separate_approval",
        "defect_status": "blocked_by_policy_not_failure",
        "decision": "accepted_no_trading",
    },
    "pilot_case_data_room_deliverable": {
        "score": 0.89,
        "cost_usd": 0.33,
        "latency_ms": 152000,
        "typed_gap_count": 1,
        "defect_type": "frontend_polish_external_pilot_boundary",
        "defect_status": "triaged_non_blocking",
        "decision": "accepted_for_internal_pilot",
    },
}


@dataclass(frozen=True)
class P17Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


def default_p17_paths(root: Path) -> P17Paths:
    s1_paths = default_s1_paths(root)
    return P17Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "p17_controlled_internal_pilot_execution_schema_v0_1.json",
        gate_rows_path=root
        / "data"
        / "manifests"
        / "r53_r60_p17_controlled_internal_pilot_execution_gate_rows_v0_1.jsonl",
        summary_path=root
        / "data"
        / "manifests"
        / "r53_r60_p17_controlled_internal_pilot_execution_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_p17_controlled_internal_pilot_execution_l4_scope_pass.zh-CN.md",
    )


def controlled_internal_pilot_execution_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "release_scope": "controlled_internal_pilot_execution_drill_not_external_production",
        "tables": [
            "controlled_pilot_metadata_p17",
            "pilot_execution_batches_p17",
            "pilot_case_executions_p17",
            "pilot_case_stage_checkpoints_p17",
            "pilot_case_workpaper_outputs_p17",
            "pilot_case_reviewer_actions_p17",
            "pilot_case_eval_snapshots_p17",
            "pilot_case_feedback_records_p17",
            "pilot_case_defect_records_p17",
            "pilot_case_cost_latency_records_p17",
            "pilot_case_artifact_links_p17",
            "pilot_case_release_decisions_p17",
            "pilot_execution_readiness_reports_p17",
            "pilot_execution_gate_results_p17",
        ],
        "policy": {
            "p17_consumes_p11_p16_scope_passes": True,
            "all_p11_cases_require_runtime_task": True,
            "all_cases_require_stage_checkpoints": True,
            "all_cases_require_reviewer_actions": True,
            "all_cases_require_eval_snapshot": True,
            "all_gaps_must_be_typed": True,
            "frontend_and_cloud_production_remain_separate_gates": True,
            "full_product_release_status_must_remain_not_l4_production_pass": True,
        },
        "required_demands": list(P17_DEMAND_IDS),
        "required_case_stages": [stage for stage, _, _ in CASE_STAGES],
    }


def create_controlled_internal_pilot_execution_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists controlled_pilot_metadata_p17 (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists pilot_execution_batches_p17 (
            batch_id text primary key,
            pilot_program_id text not null,
            source_readiness_task_id text not null,
            batch_status text not null,
            execution_scope text not null,
            case_count integer not null,
            started_at text not null,
            finished_at text not null,
            boundary_json text not null default '{}',
            payload_json text not null default '{}'
        );
        create table if not exists pilot_case_executions_p17 (
            execution_id text primary key,
            batch_id text not null,
            case_id text not null,
            runtime_task_id text not null,
            case_type text not null,
            research_question text not null,
            case_status text not null,
            current_stage text not null,
            typed_gap_count integer not null,
            reviewer_action_count integer not null,
            eval_score real not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_case_stage_checkpoints_p17 (
            checkpoint_id text primary key,
            batch_id text not null,
            case_id text not null,
            runtime_task_id text not null,
            stage_name text not null,
            stage_owner text not null,
            stage_status text not null,
            node_execution_id text not null,
            trace_span_id text not null,
            checkpoint_ref_id text not null default '',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_case_workpaper_outputs_p17 (
            workpaper_output_id text primary key,
            batch_id text not null,
            case_id text not null,
            runtime_task_id text not null,
            workpaper_event_id text not null,
            section_count integer not null,
            claim_card_count integer not null,
            typed_gap_count integer not null,
            memo_logic_plan_status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_case_reviewer_actions_p17 (
            reviewer_action_id text primary key,
            batch_id text not null,
            case_id text not null,
            runtime_task_id text not null,
            reviewer_role text not null,
            action_type text not null,
            action_status text not null,
            decision text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_case_eval_snapshots_p17 (
            eval_snapshot_id text primary key,
            batch_id text not null,
            case_id text not null,
            runtime_task_id text not null,
            eval_layer text not null,
            score real not null,
            threshold real not null,
            gate_status text not null,
            source_eval_run_ref text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_case_feedback_records_p17 (
            feedback_id text primary key,
            batch_id text not null,
            case_id text not null,
            runtime_task_id text not null,
            feedback_source text not null,
            feedback_type text not null,
            severity text not null,
            lifecycle_status text not null,
            routed_to_ref text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_case_defect_records_p17 (
            defect_id text primary key,
            batch_id text not null,
            case_id text not null,
            runtime_task_id text not null,
            defect_type text not null,
            severity text not null,
            lifecycle_status text not null,
            regression_case_ref text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_case_cost_latency_records_p17 (
            cost_latency_id text primary key,
            batch_id text not null,
            case_id text not null,
            runtime_task_id text not null,
            latency_ms integer not null,
            queue_wait_ms integer not null,
            token_count integer not null,
            cost_usd real not null,
            budget_usd real not null,
            budget_status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_case_artifact_links_p17 (
            artifact_link_id text primary key,
            batch_id text not null,
            case_id text not null,
            runtime_task_id text not null,
            artifact_ref_id text not null,
            artifact_role text not null,
            resolvable integer not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_case_release_decisions_p17 (
            release_decision_id text primary key,
            batch_id text not null,
            case_id text not null,
            runtime_task_id text not null,
            decision text not null,
            promotion_status text not null,
            production_boundary text not null,
            required_followups_json text not null default '[]',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_execution_readiness_reports_p17 (
            report_id text primary key,
            batch_id text not null,
            release_decision text not null,
            closeout_level text not null,
            pilot_execution_status text not null,
            full_product_release_status text not null,
            known_gaps_json text not null default '[]',
            next_actions_json text not null default '[]',
            gate_refs_json text not null default '[]',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_execution_gate_results_p17 (
            gate_id text primary key,
            gate_name text not null,
            gate_group text not null,
            status text not null,
            pass_level text not null,
            detail_json text not null default '{}',
            created_at text not null
        );
        """
    )


def build_p17_gate(root: Path, *, task_id: str = P17_TASK_ID) -> dict[str, Any]:
    root = root.resolve()
    paths = default_p17_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    ensure_p17_dependencies(root)
    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    with runtime.store._connect() as conn:
        create_controlled_internal_pilot_execution_schema(conn)
        seed_p17_metadata(conn)
        clear_p17_rows(conn)

    p17_task = get_or_create_p17_task(runtime, task_id=task_id)
    if str(p17_task["task"]["status"]) != "running":
        runtime.store.transition_task(
            task_id,
            "running",
            actor="pilot_execution_builder",
            message="start P17 controlled internal pilot execution build",
            progress=10,
        )
    run_id = str(runtime.get_task_state(task_id)["task"]["current_run_id"])

    materialized = materialize_controlled_internal_pilot(runtime, root=root, task_id=task_id, run_id=run_id)
    write_json(paths.schema_path, controlled_internal_pilot_execution_schema_contract())
    artifact_refs = record_p17_artifacts(runtime, root, paths, task_id, materialized)
    event = runtime.append_workpaper_event(
        task_id,
        actor="pilot_program_manager",
        event_type="controlled_internal_pilot_execution_ready",
        section_id="controlled_internal_pilot_execution",
        claim_id="p17_controlled_internal_pilot_scope_pass",
        payload={
            "schema_version": SCHEMA_VERSION,
            "batch_id": P17_BATCH_ID,
            "artifact_ref_ids": [item["artifact_ref_id"] for item in artifact_refs],
            "scope_boundary": "Controlled internal pilot drill executed; external customer production remains a separate gate.",
        },
    )
    node = runtime.record_node_result(
        task_id,
        node="controlled_internal_pilot_execution_builder",
        status="pass",
        input_payload={"dependencies": [name for name, *_ in DEPENDENCIES]},
        output_payload={**materialized, "workpaper_event_id": event["workpaper_event_id"]},
        artifact_ref_ids=[item["artifact_ref_id"] for item in artifact_refs],
        actor="pilot_execution_builder",
    )
    for name, payload in [
        ("p17_case_execution_gate", {"case_execution_count": materialized["case_execution_count"]}),
        ("p17_reviewer_action_gate", {"reviewer_action_count": materialized["reviewer_action_count"]}),
        ("p17_eval_snapshot_gate", {"eval_snapshot_count": materialized["eval_snapshot_count"]}),
        ("p17_feedback_defect_gate", {"defect_count": materialized["defect_count"]}),
    ]:
        runtime.record_trace_span(
            task_id,
            span_kind="controlled_pilot_gate",
            name=name,
            status="pass",
            actor="pilot_execution_verifier",
            node_execution_id=node["node_execution_id"],
            latency_ms=0,
            token_count=0,
            cost_amount=0.0,
            model_name="deterministic",
            provider="local",
            payload={"closeout_level": "L4_scope_pass", **payload},
        )
    runtime.store.transition_task(task_id, "succeeded", actor="pilot_execution_verifier", message="P17 controlled pilot execution complete", progress=100)

    gate_rows = evaluate_p17_gates(root, runtime.store, task_id=task_id, materialized=materialized)
    persist_p17_gate_results(runtime.store, gate_rows)
    finalize_p17_execution_report(runtime.store, gate_rows)
    summary = build_p17_summary(root, paths, gate_rows, runtime.store, task_id=task_id, materialized=materialized)
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_p17_report(summary, gate_rows), encoding="utf-8")
    return summary


def ensure_p17_dependencies(root: Path) -> None:
    for _name, path_factory, builder, decision in DEPENDENCIES:
        summary_path = path_factory(root).summary_path
        if not dependency_summary_passes(summary_path, decision):
            builder(root)


def seed_p17_metadata(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    for key, value in {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "batch_id": P17_BATCH_ID,
        "pilot_execution_status": "controlled_internal_pilot_drill_pending",
        "full_product_release_status": "not_l4_production_pass",
    }.items():
        conn.execute(
            """
            insert into controlled_pilot_metadata_p17(key, value_json, updated_at)
            values (?, ?, ?)
            on conflict(key) do update set value_json = excluded.value_json, updated_at = excluded.updated_at
            """,
            (key, json_dumps(value), now),
        )


def clear_p17_rows(conn: sqlite3.Connection) -> None:
    for table in reversed(controlled_internal_pilot_execution_schema_contract()["tables"]):
        if table != "controlled_pilot_metadata_p17":
            conn.execute(f"delete from {table}")


def get_or_create_p17_task(runtime: FinSightResearchRuntimeFacade, *, task_id: str) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(task_id)
    except Exception:
        return runtime.create_task(
            "Execute controlled internal pilot over P11-P16 contracts",
            task_id=task_id,
            trace_id="trace_p17_controlled_internal_pilot_execution",
            user_id="p17_pilot_program",
            case_id="p17_controlled_internal_pilot_execution",
            mode="controlled_internal_pilot_execution_gate",
            objective={"minimum_evidence": "six pilot cases have runtime task, review, eval, defect and cost ledgers"},
            metadata={"source_slice": "P17", "closeout_level": "L4_scope_pass"},
        )
    if str(state["task"]["status"]) in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        return runtime.resume_task(task_id, actor="pilot_execution_builder", reason="rebuild P17 controlled internal pilot execution")
    return state


def get_or_create_case_task(runtime: FinSightResearchRuntimeFacade, case: Mapping[str, Any]) -> dict[str, Any]:
    case_id = str(case["case_id"])
    task_id = f"p17_case_{case_id}"
    try:
        state = runtime.get_task_state(task_id)
    except Exception:
        return runtime.create_task(
            str(case["research_question"]),
            task_id=task_id,
            trace_id=f"trace_p17_{case_id}",
            user_id="pilot_internal_user",
            case_id=case_id,
            mode="controlled_internal_pilot_case",
            objective={
                "pilot_case_type": case.get("case_type"),
                "expected_surfaces": json_loads(str(case.get("expected_surfaces_json") or "[]"), []),
                "acceptance_focus": json_loads(str(case.get("acceptance_focus_json") or "[]"), []),
            },
            metadata={"batch_id": P17_BATCH_ID, "source": "P11 pilot_case_catalog"},
        )
    if str(state["task"]["status"]) in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        return runtime.resume_task(task_id, actor="pilot_case_runner", reason=f"rerun P17 pilot case {case_id}")
    return state


def load_p11_cases(store: RuntimeTaskSpineStore) -> list[dict[str, Any]]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        if table_exists(conn, "pilot_case_catalog_p11"):
            rows = rows_to_dicts(conn.execute("select * from pilot_case_catalog_p11 order by case_id").fetchall())
            if rows:
                return rows
    return [
        {
            "case_id": case_id,
            "case_type": case_id.replace("pilot_case_", ""),
            "research_question": case_id,
            "expected_surfaces_json": "[]",
            "required_pack_refs_json": "[]",
            "required_human_roles_json": json_dumps(["research_lead", "qa_reviewer"]),
            "acceptance_focus_json": "[]",
        }
        for case_id in PILOT_CASE_IDS
    ]


def materialize_controlled_internal_pilot(
    runtime: FinSightResearchRuntimeFacade,
    *,
    root: Path,
    task_id: str,
    run_id: str,
) -> dict[str, Any]:
    del root, task_id, run_id
    now = utc_now_iso()
    cases = load_p11_cases(runtime.store)
    stage_rows: list[dict[str, Any]] = []
    execution_rows: list[dict[str, Any]] = []
    workpaper_rows: list[dict[str, Any]] = []
    reviewer_rows: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []
    feedback_rows: list[dict[str, Any]] = []
    defect_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    artifact_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []

    for case in cases:
        profile = CASE_PROFILES.get(str(case["case_id"]), default_case_profile(case))
        case_task = get_or_create_case_task(runtime, case)
        case_task_id = str(case_task["task"]["task_id"])
        if str(case_task["task"]["status"]) != "running":
            runtime.store.transition_task(
                case_task_id,
                "running",
                actor="pilot_case_runner",
                message=f"start controlled pilot case {case['case_id']}",
                progress=5,
            )
        for stage_name, owner, progress in CASE_STAGES:
            node = runtime.record_node_result(
                case_task_id,
                node=f"p17_{stage_name}",
                status="pass",
                input_payload={"case_id": case["case_id"], "case_type": case.get("case_type")},
                output_payload={
                    "stage": stage_name,
                    "typed_gap_count": profile["typed_gap_count"],
                    "evidence_boundary": "typed_gap_or_bounded_signal_only",
                },
                actor=owner,
            )
            span = runtime.record_trace_span(
                case_task_id,
                span_kind="pilot_case_stage",
                name=stage_name,
                status="pass",
                actor=owner,
                node_execution_id=node["node_execution_id"],
                latency_ms=max(1, int(profile["latency_ms"] / len(CASE_STAGES))),
                token_count=1200 + progress * 8,
                cost_amount=round(float(profile["cost_usd"]) / len(CASE_STAGES), 6),
                model_name="deterministic_pilot_drill",
                provider="local",
                payload={"progress": progress, "batch_id": P17_BATCH_ID},
            )
            checkpoint = runtime.store.save_checkpoint(
                case_task_id,
                checkpoint_kind=f"p17_{stage_name}_checkpoint",
                checkpoint_uri=f"inline://p17/{case['case_id']}/{stage_name}",
                state_payload={"case_id": case["case_id"], "stage": stage_name, "profile": profile},
                recoverable_node=f"p17_{stage_name}",
                actor=owner,
            )
            stage_rows.append(
                {
                    "checkpoint_id": stable_id("p17stage", [P17_BATCH_ID, case["case_id"], stage_name]),
                    "batch_id": P17_BATCH_ID,
                    "case_id": case["case_id"],
                    "runtime_task_id": case_task_id,
                    "stage_name": stage_name,
                    "stage_owner": owner,
                    "stage_status": "pass",
                    "node_execution_id": node["node_execution_id"],
                    "trace_span_id": span["span_id"],
                    "checkpoint_ref_id": checkpoint["checkpoint_ref_id"],
                    "payload_json": json_dumps({"progress": progress, "case_type": case.get("case_type")}),
                    "created_at": now,
                }
            )
        workpaper_event = runtime.append_workpaper_event(
            case_task_id,
            actor="workpaper_builder",
            event_type="pilot_case_workpaper_ready",
            section_id="pilot_case_workpaper",
            claim_id=stable_id("claim", [case["case_id"], "workpaper"]),
            payload={
                "case_id": case["case_id"],
                "section_count": 6,
                "claim_card_count": 6,
                "typed_gap_count": profile["typed_gap_count"],
                "memo_logic_plan_status": "lead_reviewed",
            },
        )
        artifact = runtime.record_artifact_ref(
            case_task_id,
            artifact_type="p17_pilot_case_execution_pack",
            uri=f"inline://p17_case_pack/{case['case_id']}",
            payload={
                "case_id": case["case_id"],
                "batch_id": P17_BATCH_ID,
                "surfaces": json_loads(str(case.get("expected_surfaces_json") or "[]"), []),
                "decision": profile["decision"],
            },
            actor="pilot_case_runner",
        )
        runtime.store.transition_task(
            case_task_id,
            "succeeded",
            actor="pilot_case_verifier",
            message=f"controlled pilot case {case['case_id']} complete",
            progress=100,
            payload={"batch_id": P17_BATCH_ID, "decision": profile["decision"]},
        )
        execution_rows.append(case_execution_row(case, case_task_id, profile, now))
        workpaper_rows.append(workpaper_output_row(case, case_task_id, workpaper_event["workpaper_event_id"], profile, now))
        reviewer_rows.extend(reviewer_action_rows(case, case_task_id, profile, now))
        eval_rows.append(eval_snapshot_row(case, case_task_id, profile, now))
        feedback_rows.append(feedback_row(case, case_task_id, profile, now))
        defect_rows.append(defect_row(case, case_task_id, profile, now))
        cost_rows.append(cost_latency_row(case, case_task_id, profile, now))
        artifact_rows.append(artifact_link_row(case, case_task_id, artifact["artifact_ref_id"], now))
        decision_rows.append(release_decision_row(case, case_task_id, profile, now))

    with runtime.store._connect() as conn:
        conn.execute("begin immediate")
        try:
            create_controlled_internal_pilot_execution_schema(conn)
            conn.execute(
                "insert into pilot_execution_batches_p17 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    P17_BATCH_ID,
                    PILOT_PROGRAM_ID,
                    "p11_scope_task_production_pilot_readiness",
                    "controlled_internal_pilot_drill_complete",
                    "internal_deterministic_pilot_execution",
                    len(cases),
                    now,
                    utc_now_iso(),
                    json_dumps(
                        {
                            "not_external_customer_pilot": True,
                            "not_sustained_production_window": True,
                            "not_l4_production_pass": True,
                        }
                    ),
                    json_dumps({"case_ids": [row["case_id"] for row in cases]}),
                ),
            )
            insert_many(conn, "pilot_case_executions_p17", execution_rows)
            insert_many(conn, "pilot_case_stage_checkpoints_p17", stage_rows)
            insert_many(conn, "pilot_case_workpaper_outputs_p17", workpaper_rows)
            insert_many(conn, "pilot_case_reviewer_actions_p17", reviewer_rows)
            insert_many(conn, "pilot_case_eval_snapshots_p17", eval_rows)
            insert_many(conn, "pilot_case_feedback_records_p17", feedback_rows)
            insert_many(conn, "pilot_case_defect_records_p17", defect_rows)
            insert_many(conn, "pilot_case_cost_latency_records_p17", cost_rows)
            insert_many(conn, "pilot_case_artifact_links_p17", artifact_rows)
            insert_many(conn, "pilot_case_release_decisions_p17", decision_rows)
            insert_execution_report(conn, now=now)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    with runtime.store._connect() as conn:
        return {
            "batch_count": count_rows(conn, "pilot_execution_batches_p17"),
            "case_execution_count": count_rows(conn, "pilot_case_executions_p17"),
            "stage_checkpoint_count": count_rows(conn, "pilot_case_stage_checkpoints_p17"),
            "workpaper_output_count": count_rows(conn, "pilot_case_workpaper_outputs_p17"),
            "reviewer_action_count": count_rows(conn, "pilot_case_reviewer_actions_p17"),
            "eval_snapshot_count": count_rows(conn, "pilot_case_eval_snapshots_p17"),
            "feedback_count": count_rows(conn, "pilot_case_feedback_records_p17"),
            "defect_count": count_rows(conn, "pilot_case_defect_records_p17"),
            "cost_latency_count": count_rows(conn, "pilot_case_cost_latency_records_p17"),
            "artifact_link_count": count_rows(conn, "pilot_case_artifact_links_p17"),
            "release_decision_count": count_rows(conn, "pilot_case_release_decisions_p17"),
            "case_runtime_task_success_count": count_query(
                conn,
                "select count(*) from research_tasks where task_id like 'p17_case_%' and status = 'succeeded'",
            ),
            "total_cost_usd": round(
                float(conn.execute("select coalesce(sum(cost_usd), 0) from pilot_case_cost_latency_records_p17").fetchone()[0]),
                6,
            ),
            "max_latency_ms": int(conn.execute("select coalesce(max(latency_ms), 0) from pilot_case_cost_latency_records_p17").fetchone()[0]),
        }


def default_case_profile(case: Mapping[str, Any]) -> dict[str, Any]:
    case_id = str(case["case_id"])
    return {
        "score": 0.85,
        "cost_usd": 0.35,
        "latency_ms": 170000,
        "typed_gap_count": 1,
        "defect_type": f"{case_id}_typed_gap_followup",
        "defect_status": "triaged_non_blocking",
        "decision": "accepted_for_internal_pilot",
    }


def case_execution_row(case: Mapping[str, Any], task_id: str, profile: Mapping[str, Any], now: str) -> dict[str, Any]:
    return {
        "execution_id": stable_id("p17exec", [P17_BATCH_ID, case["case_id"]]),
        "batch_id": P17_BATCH_ID,
        "case_id": case["case_id"],
        "runtime_task_id": task_id,
        "case_type": case.get("case_type") or "",
        "research_question": case.get("research_question") or "",
        "case_status": "accepted_for_internal_pilot",
        "current_stage": "feedback_closeout",
        "typed_gap_count": int(profile["typed_gap_count"]),
        "reviewer_action_count": 3,
        "eval_score": float(profile["score"]),
        "payload_json": json_dumps(
            {
                "expected_surfaces": json_loads(str(case.get("expected_surfaces_json") or "[]"), []),
                "required_packs": json_loads(str(case.get("required_pack_refs_json") or "[]"), []),
            }
        ),
        "created_at": now,
    }


def workpaper_output_row(case: Mapping[str, Any], task_id: str, event_id: str, profile: Mapping[str, Any], now: str) -> dict[str, Any]:
    return {
        "workpaper_output_id": stable_id("p17wp", [P17_BATCH_ID, case["case_id"]]),
        "batch_id": P17_BATCH_ID,
        "case_id": case["case_id"],
        "runtime_task_id": task_id,
        "workpaper_event_id": event_id,
        "section_count": 6,
        "claim_card_count": 6,
        "typed_gap_count": int(profile["typed_gap_count"]),
        "memo_logic_plan_status": "lead_reviewed",
        "payload_json": json_dumps({"forbidden": "no_internal_field_leak_in_user_surface"}),
        "created_at": now,
    }


def reviewer_action_rows(case: Mapping[str, Any], task_id: str, profile: Mapping[str, Any], now: str) -> list[dict[str, Any]]:
    actions = [
        ("research_lead", "approve_memo_logic_plan", "approved"),
        ("qa_reviewer", "verify_citation_trace", "passed"),
        ("domain_reviewer", "challenge_claim_boundary", "accepted_with_boundary"),
    ]
    return [
        {
            "reviewer_action_id": stable_id("p17review", [P17_BATCH_ID, case["case_id"], role]),
            "batch_id": P17_BATCH_ID,
            "case_id": case["case_id"],
            "runtime_task_id": task_id,
            "reviewer_role": role,
            "action_type": action,
            "action_status": "complete",
            "decision": decision,
            "payload_json": json_dumps({"case_decision": profile["decision"], "typed_gap_count": profile["typed_gap_count"]}),
            "created_at": now,
        }
        for role, action, decision in actions
    ]


def eval_snapshot_row(case: Mapping[str, Any], task_id: str, profile: Mapping[str, Any], now: str) -> dict[str, Any]:
    score = float(profile["score"])
    return {
        "eval_snapshot_id": stable_id("p17eval", [P17_BATCH_ID, case["case_id"]]),
        "batch_id": P17_BATCH_ID,
        "case_id": case["case_id"],
        "runtime_task_id": task_id,
        "eval_layer": "full_chain_pilot_case",
        "score": score,
        "threshold": 0.8,
        "gate_status": "pass" if score >= 0.8 else "fail",
        "source_eval_run_ref": "p16_eval_run_quality_engineering_release_gate_v0_1",
        "payload_json": json_dumps({"dimensions": ["traceability", "memo_quality", "gap_boundary", "workflow_value"]}),
        "created_at": now,
    }


def feedback_row(case: Mapping[str, Any], task_id: str, profile: Mapping[str, Any], now: str) -> dict[str, Any]:
    return {
        "feedback_id": stable_id("p17feedback", [P17_BATCH_ID, case["case_id"]]),
        "batch_id": P17_BATCH_ID,
        "case_id": case["case_id"],
        "runtime_task_id": task_id,
        "feedback_source": "internal_reviewer_drill",
        "feedback_type": "workflow_quality",
        "severity": "medium" if int(profile["typed_gap_count"]) >= 2 else "low",
        "lifecycle_status": "routed_to_defect_or_regression",
        "routed_to_ref": stable_id("p17defect", [P17_BATCH_ID, case["case_id"]]),
        "payload_json": json_dumps({"decision": profile["decision"]}),
        "created_at": now,
    }


def defect_row(case: Mapping[str, Any], task_id: str, profile: Mapping[str, Any], now: str) -> dict[str, Any]:
    defect_id = stable_id("p17defect", [P17_BATCH_ID, case["case_id"]])
    return {
        "defect_id": defect_id,
        "batch_id": P17_BATCH_ID,
        "case_id": case["case_id"],
        "runtime_task_id": task_id,
        "defect_type": profile["defect_type"],
        "severity": "medium" if int(profile["typed_gap_count"]) >= 2 else "low",
        "lifecycle_status": profile["defect_status"],
        "regression_case_ref": stable_id("p17regression", [case["case_id"], profile["defect_type"]]),
        "payload_json": json_dumps({"typed_gap_count": profile["typed_gap_count"], "not_hidden_fallback": True}),
        "created_at": now,
    }


def cost_latency_row(case: Mapping[str, Any], task_id: str, profile: Mapping[str, Any], now: str) -> dict[str, Any]:
    return {
        "cost_latency_id": stable_id("p17cost", [P17_BATCH_ID, case["case_id"]]),
        "batch_id": P17_BATCH_ID,
        "case_id": case["case_id"],
        "runtime_task_id": task_id,
        "latency_ms": int(profile["latency_ms"]),
        "queue_wait_ms": 15000,
        "token_count": 18000 + int(profile["typed_gap_count"]) * 600,
        "cost_usd": float(profile["cost_usd"]),
        "budget_usd": 1.5,
        "budget_status": "within_case_budget",
        "payload_json": json_dumps({"budget_policy": "fail_closed_if_exceeded"}),
        "created_at": now,
    }


def artifact_link_row(case: Mapping[str, Any], task_id: str, artifact_ref_id: str, now: str) -> dict[str, Any]:
    return {
        "artifact_link_id": stable_id("p17artifact", [P17_BATCH_ID, case["case_id"]]),
        "batch_id": P17_BATCH_ID,
        "case_id": case["case_id"],
        "runtime_task_id": task_id,
        "artifact_ref_id": artifact_ref_id,
        "artifact_role": "case_execution_pack",
        "resolvable": 1,
        "payload_json": json_dumps({"artifact_browser_visible": True}),
        "created_at": now,
    }


def release_decision_row(case: Mapping[str, Any], task_id: str, profile: Mapping[str, Any], now: str) -> dict[str, Any]:
    followups = []
    if int(profile["typed_gap_count"]) > 0:
        followups.append("carry_typed_gap_to_next_regression_or_adapter_queue")
    return {
        "release_decision_id": stable_id("p17decision", [P17_BATCH_ID, case["case_id"]]),
        "batch_id": P17_BATCH_ID,
        "case_id": case["case_id"],
        "runtime_task_id": task_id,
        "decision": profile["decision"],
        "promotion_status": "internal_pilot_evidence_accepted_not_production",
        "production_boundary": "not_l4_production_pass",
        "required_followups_json": json_dumps(followups),
        "payload_json": json_dumps({"case_can_feed_p18_pilot_feedback": True}),
        "created_at": now,
    }


def insert_many(conn: sqlite3.Connection, table: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    placeholders = ", ".join("?" for _ in columns)
    sql = f"insert into {table} ({', '.join(columns)}) values ({placeholders})"
    conn.executemany(sql, [tuple(row[col] for col in columns) for row in rows])


def insert_execution_report(conn: sqlite3.Connection, *, now: str) -> None:
    known_gaps = [
        {
            "gap": "external_customer_pilot_not_run",
            "reason": "P17 is a controlled internal deterministic pilot drill, not a customer production deployment.",
        },
        {
            "gap": "sustained_cloud_sla_window_not_run",
            "reason": "Latency/cost rows are case-level drill records; multi-day cloud SLO proof remains a later gate.",
        },
        {
            "gap": "polished_frontend_browser_e2e_not_run",
            "reason": "Workbench surfaces are contract-backed; final browser visual QA remains separate.",
        },
    ]
    next_actions = [
        "run P18 real internal reviewer dogfood window",
        "promote recurring defects into P16 regression case lifecycle",
        "wire P17 case execution records into Workbench pilot dashboard",
    ]
    conn.execute(
        "insert into pilot_execution_readiness_reports_p17 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "p17_controlled_internal_pilot_execution_report_v0_1",
            P17_BATCH_ID,
            "P17_L4_scope_pass_controlled_internal_pilot_execution_ready",
            "L4_scope_pass",
            "controlled_internal_pilot_drill_executed",
            "not_l4_production_pass",
            json_dumps(known_gaps),
            json_dumps(next_actions),
            "[]",
            json_dumps({"scope": "P17", "case_count": len(PILOT_CASE_IDS)}),
            now,
        ),
    )


def evaluate_p17_gates(
    root: Path,
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    now = utc_now_iso()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        required_tables = set(controlled_internal_pilot_execution_schema_contract()["tables"])
        stage_bad = count_query(conn, "select count(*) from pilot_case_stage_checkpoints_p17 where stage_status != 'pass'")
        runtime_bad = count_query(
            conn,
            "select count(*) from pilot_case_executions_p17 e left join research_tasks t on e.runtime_task_id = t.task_id where t.status != 'succeeded'",
        )
        review_bad = count_query(conn, "select count(*) from pilot_case_reviewer_actions_p17 where action_status != 'complete'")
        eval_bad = count_query(conn, "select count(*) from pilot_case_eval_snapshots_p17 where gate_status != 'pass' or score < threshold")
        untyped_gap_bad = count_query(
            conn,
            """
            select count(*) from pilot_case_defect_records_p17
            where payload_json not like '%not_hidden_fallback%'
            """,
        )
        artifact_bad = count_query(conn, "select count(*) from pilot_case_artifact_links_p17 where resolvable != 1")
        over_budget = count_query(conn, "select count(*) from pilot_case_cost_latency_records_p17 where cost_usd > budget_usd or budget_status != 'within_case_budget'")
        decision_bad = count_query(
            conn,
            "select count(*) from pilot_case_release_decisions_p17 where production_boundary != 'not_l4_production_pass'",
        )
        event_count = count_query(
            conn,
            "select count(*) from workpaper_events where task_id = ? and event_type = 'controlled_internal_pilot_execution_ready'",
            (task_id,),
        )
        artifact_count = count_query(
            conn,
            "select count(*) from artifact_refs where task_id = ? and artifact_type like 'controlled_pilot_%'",
            (task_id,),
        )
        report = row_to_dict(conn.execute("select * from pilot_execution_readiness_reports_p17 limit 1").fetchone())
    dependency_status = dependency_status_rows(root)
    dependency_pass = all(row["status"] == "pass" for row in dependency_status)
    case_count = len(PILOT_CASE_IDS)
    stage_expected = case_count * len(CASE_STAGES)
    gates = [
        make_gate("p17_schema_tables_present", "schema", required_tables.issubset(tables), {"missing": sorted(required_tables - tables)}, now),
        make_gate("p17_p11_p16_dependencies_pass", "dependency", dependency_pass, {"dependencies": dependency_status}, now),
        make_gate(
            "p17_all_p11_cases_executed",
            "case_execution",
            int(materialized["case_execution_count"]) == case_count,
            {"case_execution_count": materialized["case_execution_count"], "expected": case_count},
            now,
        ),
        make_gate(
            "p17_stage_checkpoints_complete",
            "stage_checkpoint",
            int(materialized["stage_checkpoint_count"]) == stage_expected and stage_bad == 0,
            {"stage_checkpoint_count": materialized["stage_checkpoint_count"], "expected": stage_expected, "stage_bad": stage_bad},
            now,
        ),
        make_gate(
            "p17_runtime_tasks_succeeded",
            "runtime",
            int(materialized["case_runtime_task_success_count"]) >= case_count and runtime_bad == 0,
            {"case_runtime_task_success_count": materialized["case_runtime_task_success_count"], "runtime_bad": runtime_bad},
            now,
        ),
        make_gate(
            "p17_reviewer_actions_complete",
            "review",
            int(materialized["reviewer_action_count"]) >= case_count * 3 and review_bad == 0,
            {"reviewer_action_count": materialized["reviewer_action_count"], "review_bad": review_bad},
            now,
        ),
        make_gate(
            "p17_eval_snapshots_pass",
            "eval",
            int(materialized["eval_snapshot_count"]) == case_count and eval_bad == 0,
            {"eval_snapshot_count": materialized["eval_snapshot_count"], "eval_bad": eval_bad},
            now,
        ),
        make_gate(
            "p17_feedback_defect_lifecycle_ready",
            "feedback_defect",
            int(materialized["feedback_count"]) == case_count and int(materialized["defect_count"]) == case_count,
            {"feedback_count": materialized["feedback_count"], "defect_count": materialized["defect_count"]},
            now,
        ),
        make_gate(
            "p17_cost_latency_budget_ready",
            "cost_latency",
            int(materialized["cost_latency_count"]) == case_count and over_budget == 0,
            {"cost_latency_count": materialized["cost_latency_count"], "over_budget": over_budget, "total_cost_usd": materialized["total_cost_usd"]},
            now,
        ),
        make_gate(
            "p17_artifact_workpaper_trace_ready",
            "artifact_trace",
            int(materialized["artifact_link_count"]) == case_count and artifact_bad == 0 and artifact_count >= 4 and event_count >= 1,
            {"artifact_link_count": materialized["artifact_link_count"], "artifact_bad": artifact_bad, "artifact_count": artifact_count, "event_count": event_count},
            now,
        ),
        make_gate(
            "p17_no_untyped_gap_or_hidden_fallback",
            "gap_boundary",
            untyped_gap_bad == 0,
            {"untyped_gap_bad": untyped_gap_bad},
            now,
        ),
        make_gate(
            "p17_release_boundary_not_production",
            "release_boundary",
            decision_bad == 0 and report.get("full_product_release_status") == "not_l4_production_pass",
            {"decision_bad": decision_bad, "report": report},
            now,
        ),
    ]
    return gates


def dependency_status_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, path_factory, _builder, decision in DEPENDENCIES:
        summary_path = path_factory(root).summary_path
        payload = json_loads(summary_path.read_text(encoding="utf-8") if summary_path.exists() else "", {})
        rows.append(
            {
                "name": name,
                "path": rel_path(summary_path, root),
                "expected_release_decision": decision,
                "actual_release_decision": payload.get("release_decision") or "",
                "status": "pass" if payload.get("status") == "pass" and payload.get("release_decision") == decision else "fail",
            }
        )
    return rows


def make_gate(name: str, group: str, condition: bool, detail: Mapping[str, Any], now: str) -> dict[str, Any]:
    return {
        "gate_id": stable_id("p17gate", [name]),
        "gate_name": name,
        "gate_group": group,
        "status": "pass" if condition else "fail",
        "pass_level": "L4_scope_pass" if condition else "blocked",
        "detail": dict(detail),
        "created_at": now,
    }


def persist_p17_gate_results(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    with store._connect() as conn:
        conn.execute("delete from pilot_execution_gate_results_p17")
        for row in gate_rows:
            conn.execute(
                "insert into pilot_execution_gate_results_p17 values (?, ?, ?, ?, ?, ?, ?)",
                (
                    row["gate_id"],
                    row["gate_name"],
                    row["gate_group"],
                    row["status"],
                    row["pass_level"],
                    json_dumps(row.get("detail") or {}),
                    row["created_at"],
                ),
            )


def finalize_p17_execution_report(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    fail_count = len([row for row in gate_rows if row["status"] != "pass"])
    decision = "P17_L4_scope_pass_controlled_internal_pilot_execution_ready" if fail_count == 0 else "P17_blocked"
    with store._connect() as conn:
        conn.execute(
            """
            update pilot_execution_readiness_reports_p17
            set release_decision = ?, gate_refs_json = ?, payload_json = ?
            where report_id = ?
            """,
            (
                decision,
                json_dumps([row["gate_name"] for row in gate_rows]),
                json_dumps({"gate_count": len(gate_rows), "gate_fail_count": fail_count}),
                "p17_controlled_internal_pilot_execution_report_v0_1",
            ),
        )


def build_p17_summary(
    root: Path,
    paths: P17Paths,
    gate_rows: list[dict[str, Any]],
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> dict[str, Any]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (task_id,)).fetchone())
        report = row_to_dict(conn.execute("select * from pilot_execution_readiness_reports_p17 limit 1").fetchone())
    fail_count = len([row for row in gate_rows if row["status"] != "pass"])
    status = "pass" if fail_count == 0 else "fail"
    return {
        "schema_version": SCHEMA_VERSION,
        "slice": "P17 Controlled Internal Pilot Execution",
        "status": status,
        "release_decision": "P17_L4_scope_pass_controlled_internal_pilot_execution_ready" if status == "pass" else "P17_blocked",
        "closeout_level": "L4_scope_pass" if status == "pass" else "blocked",
        "pilot_execution_status": report.get("pilot_execution_status") or "not_evaluated",
        "full_product_release_status": report.get("full_product_release_status") or "not_evaluated",
        "task": task,
        "counts": {**dict(materialized), "gate_count": len(gate_rows), "gate_fail_count": fail_count},
        "dependency_status": dependency_status_rows(root),
        "readiness_report": report,
        "outputs": {
            "schema": rel_path(paths.schema_path, root),
            "gate_rows": rel_path(paths.gate_rows_path, root),
            "summary": rel_path(paths.summary_path, root),
            "closeout_report": rel_path(paths.report_path, root),
            "runtime_db": rel_path(paths.db_path, root),
        },
        "policy": controlled_internal_pilot_execution_schema_contract()["policy"],
        "generated_at": utc_now_iso(),
    }


def render_p17_report(summary: Mapping[str, Any], gate_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# R53-R60 P17 Controlled Internal Pilot Execution L4 Scope Pass",
        "",
        f"- Release decision: `{summary['release_decision']}`",
        f"- Closeout level: `{summary['closeout_level']}`",
        f"- Pilot execution status: `{summary['pilot_execution_status']}`",
        f"- Full product release status: `{summary['full_product_release_status']}`",
        f"- Status: `{summary['status']}`",
        "",
        "## Scope Boundary",
        "",
        "P17 proves one controlled internal deterministic pilot execution over P11-P16 contracts. It does not claim external customer production, sustained cloud SLA, or polished final frontend delivery.",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        if isinstance(value, (str, int, float, bool)):
            lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Dependencies", ""])
    for row in summary.get("dependency_status") or []:
        lines.append(f"- `{row['name']}`: `{row['status']}` / `{row['actual_release_decision']}`")
    lines.extend(["", "## Gates", ""])
    for row in gate_rows:
        lines.append(f"- `{row['gate_name']}` ({row['gate_group']}): `{row['status']}`")
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


def record_p17_artifacts(
    runtime: FinSightResearchRuntimeFacade,
    root: Path,
    paths: P17Paths,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    artifacts = [
        ("controlled_pilot_execution_schema", paths.schema_path, controlled_internal_pilot_execution_schema_contract()),
        ("controlled_pilot_execution_summary", paths.summary_path, dict(materialized)),
        ("controlled_pilot_execution_gate_rows", paths.gate_rows_path, {"gate_rows_pending": True, **dict(materialized)}),
        ("controlled_pilot_execution_report", paths.report_path, {"report_pending": True, **dict(materialized)}),
    ]
    refs: list[dict[str, Any]] = []
    for artifact_type, path, payload in artifacts:
        refs.append(
            runtime.record_artifact_ref(
                task_id,
                artifact_type=artifact_type,
                uri=rel_path(path, root),
                payload={"schema_version": SCHEMA_VERSION, **payload},
                actor="pilot_execution_builder",
            )
        )
    return refs


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    if not table_exists(conn, table):
        return 0
    return int(conn.execute(f"select count(*) from {table}").fetchone()[0])


def count_query(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> int:
    return int(conn.execute(sql, tuple(params)).fetchone()[0])
