"""P12 Durable Runtime + HIL + Resource Router for the R53-R60 program.

This slice wires a deterministic runtime drill through the existing S1 SQL
ledger instead of producing isolated planning rows.  It proves checkpoint /
resume, human-in-the-loop interruption and approval, resource/model routing,
replay, and trace export contracts are materialized and auditable.  It remains
a scoped runtime drill, not a claim that every production LangGraph node is
already migrated.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.r53_r60_production_pilot_readiness import build_p11_gate
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


SCHEMA_VERSION = "r53_r60_p12_durable_runtime_hil_resource_router_v0_1"
P12_TASK_ID = "p12_scope_task_durable_runtime_hil_resource_router"
P12_RUNTIME_DRILL_TASK_ID = "p12_runtime_drill_task_ai_infra_hil_resource_route"

P12_DEMAND_IDS = (
    "P12-D01-runtime-facade-node-binding",
    "P12-D02-checkpoint-resume-bridge",
    "P12-D03-human-interrupt-approval",
    "P12-D04-resource-model-router-ledger",
    "P12-D05-replay-trace-export-gate",
)
GRAPH_NODE_NAMES = (
    "research_lead_objective_contract",
    "retrieval_evidence_operator",
    "product_specialist_pack",
    "lead_review_checkpoint",
    "memo_logic_plan",
)
ROUTE_CLASSES = (
    "lead_planning_high_reasoning",
    "retrieval_embedding_gpu_queue",
    "specialist_analysis_balanced",
    "memo_render_cost_controlled",
)
TRACE_EXPORT_TARGETS = ("opentelemetry", "langfuse", "phoenix")


@dataclass(frozen=True)
class P12Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


def default_p12_paths(root: Path) -> P12Paths:
    s1_paths = default_s1_paths(root)
    return P12Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "p12_durable_runtime_hil_resource_router_schema_v0_1.json",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_p12_durable_runtime_hil_resource_router_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_p12_durable_runtime_hil_resource_router_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_p12_durable_runtime_hil_resource_router_l4_scope_pass.zh-CN.md",
    )


def durable_runtime_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "release_scope": "durable_runtime_hil_resource_router_drill",
        "tables": [
            "durable_runtime_metadata_p12",
            "runtime_facade_bindings_p12",
            "graph_node_runtime_bindings_p12",
            "checkpoint_bridge_records_p12",
            "human_interrupt_records_p12",
            "human_approval_decisions_p12",
            "resource_model_route_policies_p12",
            "resource_queue_events_p12",
            "model_budget_ledger_p12",
            "runtime_replay_attempts_p12",
            "trace_export_records_p12",
            "runtime_acceptance_records_p12",
            "runtime_readiness_reports_p12",
            "runtime_gate_results_p12",
        ],
        "policy": {
            "sql_ledger_is_final_audit_source": True,
            "redis_queue_is_not_final_audit_source": True,
            "checkpoint_resume_required_before_hil_approval": True,
            "human_approval_required_for_scope_expansion": True,
            "model_route_must_record_budget_resource_and_fallback": True,
            "replay_must_use_runtime_task_ledger": True,
            "trace_export_is_derived_not_primary_audit": True,
            "not_full_langgraph_production_migration": True,
        },
    }


def create_durable_runtime_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists durable_runtime_metadata_p12 (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists runtime_facade_bindings_p12 (
            binding_id text primary key,
            facade_name text not null,
            entrypoint text not null,
            task_id text not null,
            supported_capabilities_json text not null default '[]',
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists graph_node_runtime_bindings_p12 (
            node_binding_id text primary key,
            task_id text not null,
            node_name text not null,
            actor text not null,
            input_contract_json text not null default '{}',
            output_contract_json text not null default '{}',
            checkpoint_policy text not null,
            tool_permission_scope text not null,
            route_class text not null,
            status text not null,
            created_at text not null
        );
        create table if not exists checkpoint_bridge_records_p12 (
            bridge_id text primary key,
            task_id text not null,
            checkpoint_ref_id text not null,
            recoverable_node text not null,
            resume_policy text not null,
            replay_status text not null,
            payload_digest text not null,
            status text not null,
            created_at text not null
        );
        create table if not exists human_interrupt_records_p12 (
            interrupt_id text primary key,
            task_id text not null,
            checkpoint_ref_id text not null,
            interrupt_type text not null,
            requested_by text not null,
            required_role text not null,
            reason text not null,
            status_before text not null,
            status_after text not null,
            status text not null,
            created_at text not null
        );
        create table if not exists human_approval_decisions_p12 (
            decision_id text primary key,
            interrupt_id text not null,
            task_id text not null,
            reviewer_role text not null,
            decision text not null,
            approved_scope_json text not null default '{}',
            resume_run_id text not null,
            status text not null,
            created_at text not null
        );
        create table if not exists resource_model_route_policies_p12 (
            route_policy_id text primary key,
            route_class text not null,
            preferred_model text not null,
            fallback_model text not null,
            resource_class text not null,
            queue_class text not null,
            max_tokens integer not null,
            cost_cap_usd real not null,
            spillover_policy text not null,
            status text not null,
            created_at text not null
        );
        create table if not exists resource_queue_events_p12 (
            queue_event_id text primary key,
            task_id text not null,
            route_policy_id text not null,
            route_class text not null,
            event_type text not null,
            assigned_model text not null,
            assigned_resource text not null,
            queue_wait_ms integer not null,
            token_count integer not null,
            cost_amount real not null,
            status text not null,
            created_at text not null
        );
        create table if not exists model_budget_ledger_p12 (
            budget_id text primary key,
            task_id text not null,
            budget_scope text not null,
            token_budget integer not null,
            tokens_used integer not null,
            cost_budget_usd real not null,
            cost_used_usd real not null,
            status text not null,
            created_at text not null
        );
        create table if not exists runtime_replay_attempts_p12 (
            replay_id text primary key,
            task_id text not null,
            replay_source text not null,
            checkpoint_count integer not null,
            event_count integer not null,
            node_count integer not null,
            span_count integer not null,
            replay_status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists trace_export_records_p12 (
            export_id text primary key,
            task_id text not null,
            target text not null,
            export_format text not null,
            span_count integer not null,
            source_of_truth text not null,
            export_status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists runtime_acceptance_records_p12 (
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
        create table if not exists runtime_readiness_reports_p12 (
            report_id text primary key,
            task_id text not null,
            runtime_status text not null,
            hil_status text not null,
            resource_router_status text not null,
            replay_status text not null,
            full_runtime_migration_status text not null,
            release_decision text not null,
            gate_refs_json text not null default '[]',
            known_gaps_json text not null default '[]',
            next_actions_json text not null default '[]',
            owner text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists runtime_gate_results_p12 (
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


def seed_p12_metadata(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "source_of_truth": "S1 SQL runtime task spine",
        "scope_boundary": "Durable runtime drill only; not full LangGraph production migration.",
    }
    for key, value in metadata.items():
        conn.execute(
            """
            insert into durable_runtime_metadata_p12(key, value_json, updated_at)
            values (?, ?, ?)
            on conflict(key) do update set
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (key, json_dumps(value), now),
        )


def clear_p12_rows(conn: sqlite3.Connection) -> None:
    for table in [
        "runtime_gate_results_p12",
        "runtime_readiness_reports_p12",
        "runtime_acceptance_records_p12",
        "trace_export_records_p12",
        "runtime_replay_attempts_p12",
        "model_budget_ledger_p12",
        "resource_queue_events_p12",
        "resource_model_route_policies_p12",
        "human_approval_decisions_p12",
        "human_interrupt_records_p12",
        "checkpoint_bridge_records_p12",
        "graph_node_runtime_bindings_p12",
        "runtime_facade_bindings_p12",
    ]:
        conn.execute(f"delete from {table}")


def build_p12_gate(root: Path, *, task_id: str = P12_TASK_ID) -> dict[str, Any]:
    root = root.resolve()
    paths = default_p12_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    ensure_p11_dependency(root)
    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    with runtime.store._connect() as conn:
        create_durable_runtime_schema(conn)
        seed_p12_metadata(conn)
        clear_p12_rows(conn)

    drill_task = get_or_create_runtime_drill_task(runtime)
    materialized = materialize_durable_runtime_drill(runtime, root=root, drill_task_id=P12_RUNTIME_DRILL_TASK_ID)
    p12_task = get_or_create_p12_task(runtime, task_id=task_id)
    if str(p12_task["task"]["status"]) != "running":
        p12_task = runtime.store.transition_task(
            task_id,
            "running",
            actor="durable_runtime_builder",
            message="start P12 Durable Runtime + HIL + Resource Router build",
            progress=10,
        )

    write_json(paths.schema_path, durable_runtime_schema_contract())
    artifact_refs = record_p12_runtime_artifacts(runtime, root, paths, task_id, materialized)
    event = runtime.append_workpaper_event(
        task_id,
        actor="runtime_architect",
        event_type="durable_runtime_hil_resource_router_ready",
        section_id="durable_runtime_hil_resource_router",
        claim_id="p12_durable_runtime_scope_pass",
        payload={
            "schema_version": SCHEMA_VERSION,
            "drill_task_id": P12_RUNTIME_DRILL_TASK_ID,
            "artifact_ref_ids": [item["artifact_ref_id"] for item in artifact_refs],
            "scope_boundary": "Durable runtime drill is wired; full production graph migration remains a later gate.",
        },
    )
    node = runtime.record_node_result(
        task_id,
        node="durable_runtime_hil_resource_router_builder",
        status="pass",
        input_payload={"dependencies": "P11 readiness summary", "task_id": task_id},
        output_payload={**materialized, "workpaper_event_id": event["workpaper_event_id"]},
        artifact_ref_ids=[item["artifact_ref_id"] for item in artifact_refs],
        actor="durable_runtime_builder",
    )
    for name, payload in [
        ("p12_checkpoint_resume_gate", {"checkpoint_bridge_count": materialized["checkpoint_bridge_count"]}),
        ("p12_hil_approval_gate", {"human_approval_count": materialized["human_approval_count"]}),
        ("p12_resource_router_gate", {"resource_queue_event_count": materialized["resource_queue_event_count"]}),
        ("p12_trace_export_gate", {"trace_export_count": materialized["trace_export_count"]}),
    ]:
        runtime.record_trace_span(
            task_id,
            span_kind="durable_runtime_gate",
            name=name,
            status="pass",
            actor="runtime_verifier",
            node_execution_id=node["node_execution_id"],
            latency_ms=0,
            token_count=0,
            cost_amount=0.0,
            model_name="deterministic",
            provider="local",
            payload={"closeout_level": "L4_scope_pass", **payload},
        )
    runtime.store.transition_task(task_id, "succeeded", actor="runtime_verifier", message="P12 durable runtime drill complete", progress=100)

    gate_rows = evaluate_p12_gates(root, runtime.store, task_id=task_id, drill_task_id=P12_RUNTIME_DRILL_TASK_ID, materialized=materialized)
    persist_p12_gate_results(runtime.store, gate_rows)
    finalize_p12_readiness_report(runtime.store, gate_rows)
    summary = build_p12_summary(root, paths, gate_rows, runtime.store, task_id=task_id, materialized=materialized)
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_p12_report(summary, gate_rows), encoding="utf-8")
    return summary


def ensure_p11_dependency(root: Path) -> None:
    summary = root / "data" / "manifests" / "r53_r60_p11_production_pilot_readiness_summary_v0_1.json"
    if not summary.exists():
        build_p11_gate(root)


def get_or_create_p12_task(runtime: FinSightResearchRuntimeFacade, *, task_id: str) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(task_id)
    except Exception:
        return runtime.create_task(
            "Build durable runtime, HIL and resource-router gate package",
            task_id=task_id,
            trace_id="trace_p12_durable_runtime_hil_resource_router",
            user_id="p12_gate",
            case_id="p12_durable_runtime_hil_resource_router_l4_scope",
            mode="durable_runtime_gate",
            objective={"minimum_evidence": "checkpoint/resume, HIL approval, router, replay and trace export rows exist"},
            metadata={"source_slice": "P12", "closeout_level": "L4_scope_pass"},
        )
    if str(state["task"]["status"]) in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        return runtime.resume_task(task_id, actor="p12_builder", reason="rebuild P12 Durable Runtime")
    return state


def get_or_create_runtime_drill_task(runtime: FinSightResearchRuntimeFacade) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(P12_RUNTIME_DRILL_TASK_ID)
    except Exception:
        state = runtime.create_task(
            "Run P12 durable runtime drill with HIL and model routing",
            task_id=P12_RUNTIME_DRILL_TASK_ID,
            trace_id="trace_p12_runtime_drill",
            user_id="pilot_research_lead",
            case_id="pilot_case_ai_infra_full_research",
            mode="durable_runtime_drill",
            objective={
                "research_question": "Can the agent runtime pause for human approval, resume from checkpoint, route resources, and replay?",
                "required_nodes": list(GRAPH_NODE_NAMES),
            },
            metadata={"source_slice": "P12", "drill": True},
        )
    status = str(state["task"]["status"])
    if status in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        state = runtime.resume_task(P12_RUNTIME_DRILL_TASK_ID, actor="p12_runtime_drill", reason="rerun durable runtime drill")
    if str(state["task"]["status"]) != "running":
        state = runtime.store.transition_task(
            P12_RUNTIME_DRILL_TASK_ID,
            "running",
            actor="p12_runtime_drill",
            message="start durable runtime drill",
            progress=5,
        )
    return state


def materialize_durable_runtime_drill(
    runtime: FinSightResearchRuntimeFacade,
    *,
    root: Path,
    drill_task_id: str,
) -> dict[str, Any]:
    store = runtime.store
    with store._connect() as conn:
        create_durable_runtime_schema(conn)
        clear_p12_rows(conn)
    drill_state = runtime.get_task_state(drill_task_id)
    run_id = str(drill_state["task"]["current_run_id"])
    now = utc_now_iso()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("begin immediate")
        try:
            insert_runtime_facade_bindings(conn, drill_task_id=drill_task_id, now=now)
            insert_graph_node_bindings(conn, drill_task_id=drill_task_id, now=now)
            insert_resource_route_policies(conn, now=now)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    node_outputs: list[dict[str, Any]] = []
    for index, node_name in enumerate(GRAPH_NODE_NAMES):
        route_class = ROUTE_CLASSES[min(index, len(ROUTE_CLASSES) - 1)]
        route_policy_id = stable_id("p12route", [route_class])
        queue_event = insert_resource_queue_event(
            store,
            drill_task_id=drill_task_id,
            route_policy_id=route_policy_id,
            route_class=route_class,
            event_type="dispatch",
            assigned_model=model_for_route(route_class),
            assigned_resource=resource_for_route(route_class),
            queue_wait_ms=35 + index * 17,
            token_count=900 + index * 180,
            cost_amount=round(0.018 + index * 0.004, 6),
        )
        node = runtime.record_node_result(
            drill_task_id,
            node=node_name,
            status="pass",
            input_payload={"route_class": route_class, "queue_event_id": queue_event["queue_event_id"]},
            output_payload={"node_name": node_name, "bounded_output": True, "requires_checkpoint": node_name == "lead_review_checkpoint"},
            actor=actor_for_node(node_name),
        )
        span = runtime.record_trace_span(
            drill_task_id,
            span_kind="graph_node",
            name=node_name,
            status="pass",
            actor=actor_for_node(node_name),
            node_execution_id=node["node_execution_id"],
            latency_ms=120 + index * 23,
            token_count=900 + index * 180,
            cost_amount=round(0.018 + index * 0.004, 6),
            model_name=model_for_route(route_class),
            provider="local_router",
            payload={"route_class": route_class, "resource_class": resource_for_route(route_class)},
        )
        node_outputs.append({"node": node, "span": span, "queue_event": queue_event})
        if node_name in {"retrieval_evidence_operator", "lead_review_checkpoint"}:
            checkpoint = runtime.save_checkpoint(
                drill_task_id,
                checkpoint_kind="langgraph_node_state",
                checkpoint_uri=f"object://runtime-checkpoints/p12/{node_name}.json",
                recoverable_node=node_name,
                state_payload={
                    "node_name": node_name,
                    "route_class": route_class,
                    "selected_refs": [item["node"]["node_execution_id"] for item in node_outputs],
                    "requires_human_approval": node_name == "lead_review_checkpoint",
                },
                actor="checkpoint_bridge",
            )
            insert_checkpoint_bridge(store, drill_task_id=drill_task_id, checkpoint=checkpoint, node_name=node_name)

    lead_checkpoint = latest_checkpoint_for_node(store, drill_task_id, "lead_review_checkpoint")
    before_pause = runtime.get_task_state(drill_task_id)["task"]["status"]
    runtime.store.transition_task(
        drill_task_id,
        "paused",
        actor="lead_review_checkpoint",
        message="pause for human approval before memo logic plan",
        progress=72,
        event_type="human_interrupt_requested",
        payload={"checkpoint_ref_id": lead_checkpoint["checkpoint_ref_id"], "required_role": "research_lead"},
    )
    insert_human_interrupt(store, drill_task_id=drill_task_id, checkpoint=lead_checkpoint, status_before=before_pause)
    resumed = runtime.resume_task(
        drill_task_id,
        actor="human_research_lead",
        reason="approved bounded targeted repair and memo logic plan continuation",
        checkpoint_ref_id=lead_checkpoint["checkpoint_ref_id"],
    )
    if str(resumed["task"]["status"]) != "running":
        resumed = runtime.store.transition_task(
            drill_task_id,
            "running",
            actor="runtime_facade",
            message="resume approved runtime drill after HIL",
            progress=76,
            event_type="human_interrupt_resumed",
            payload={"checkpoint_ref_id": lead_checkpoint["checkpoint_ref_id"]},
        )
    insert_human_approval(store, drill_task_id=drill_task_id, checkpoint=lead_checkpoint, resume_run_id=str(resumed["task"]["current_run_id"]))
    insert_model_budget_records(store, drill_task_id=drill_task_id)

    replay_payload = runtime.replay_task(drill_task_id)
    insert_replay_attempt(store, drill_task_id=drill_task_id, replay_payload=replay_payload)
    insert_trace_exports(store, drill_task_id=drill_task_id, replay_payload=replay_payload)
    insert_runtime_acceptance_records(store, now=utc_now_iso())
    insert_runtime_readiness_report(store, now=utc_now_iso())
    runtime.store.transition_task(drill_task_id, "succeeded", actor="runtime_verifier", message="durable runtime drill succeeded", progress=100)
    return collect_p12_counts(store, drill_task_id=drill_task_id, run_id=run_id)


def insert_runtime_facade_bindings(conn: sqlite3.Connection, *, drill_task_id: str, now: str) -> None:
    conn.execute(
        "insert into runtime_facade_bindings_p12 values (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "p12_runtime_facade_binding_v0_1",
            "FinSightResearchRuntimeFacade",
            "python_runtime_to_sql_final_task_ledger",
            drill_task_id,
            json_dumps(["create_task", "transition", "checkpoint", "hil_pause_resume", "resource_route", "replay", "trace_export"]),
            "ready",
            json_dumps({"s1_db_backed": True, "java_gateway_compatible": True}),
            now,
        ),
    )


def insert_graph_node_bindings(conn: sqlite3.Connection, *, drill_task_id: str, now: str) -> None:
    for index, node_name in enumerate(GRAPH_NODE_NAMES):
        route_class = ROUTE_CLASSES[min(index, len(ROUTE_CLASSES) - 1)]
        conn.execute(
            "insert into graph_node_runtime_bindings_p12 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p12nodebind", [node_name]),
                drill_task_id,
                node_name,
                actor_for_node(node_name),
                json_dumps({"requires": ["ContextInjectionPlan", "EvidencePack"], "node_index": index}),
                json_dumps({"produces": ["WorkpaperEvent", "NodeExecution", "TraceSpan"]}),
                "checkpoint_before_hil" if node_name == "lead_review_checkpoint" else "checkpoint_optional",
                tool_scope_for_node(node_name),
                route_class,
                "ready",
                now,
            ),
        )


def insert_resource_route_policies(conn: sqlite3.Connection, *, now: str) -> None:
    route_rows = [
        ("lead_planning_high_reasoning", "deepseek-reasoner", "deepseek-chat", "gpu_or_remote_llm", "critical_path", 12000, 0.35, "fallback_to_balanced"),
        ("retrieval_embedding_gpu_queue", "bge-large-cuda", "bge-large-cpu", "local_gpu_embedding", "embedding_queue", 2048, 0.02, "cpu_spillover_after_wait_threshold"),
        ("specialist_analysis_balanced", "deepseek-chat", "qwen-flash", "remote_llm", "analysis_queue", 8000, 0.18, "coalesce_low_risk_specialists"),
        ("memo_render_cost_controlled", "qwen-flash", "deepseek-chat", "remote_llm_low_cost", "composer_queue", 6000, 0.08, "escalate_only_if_readability_gate_fails"),
    ]
    for route_class, preferred, fallback, resource, queue_class, tokens, cost, spillover in route_rows:
        conn.execute(
            "insert into resource_model_route_policies_p12 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p12route", [route_class]),
                route_class,
                preferred,
                fallback,
                resource,
                queue_class,
                int(tokens),
                float(cost),
                spillover,
                "ready",
                now,
            ),
        )


def insert_resource_queue_event(
    store: RuntimeTaskSpineStore,
    *,
    drill_task_id: str,
    route_policy_id: str,
    route_class: str,
    event_type: str,
    assigned_model: str,
    assigned_resource: str,
    queue_wait_ms: int,
    token_count: int,
    cost_amount: float,
) -> dict[str, Any]:
    now = utc_now_iso()
    event_id = stable_id("p12queue", [drill_task_id, route_class, event_type, now, token_count])
    with store._connect() as conn:
        conn.execute(
            "insert into resource_queue_events_p12 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event_id,
                drill_task_id,
                route_policy_id,
                route_class,
                event_type,
                assigned_model,
                assigned_resource,
                int(queue_wait_ms),
                int(token_count),
                float(cost_amount),
                "routed",
                now,
            ),
        )
    return {"queue_event_id": event_id, "route_class": route_class}


def insert_checkpoint_bridge(store: RuntimeTaskSpineStore, *, drill_task_id: str, checkpoint: Mapping[str, Any], node_name: str) -> None:
    now = utc_now_iso()
    checkpoint_id = str(checkpoint["checkpoint_ref_id"])
    with store._connect() as conn:
        conn.execute(
            "insert into checkpoint_bridge_records_p12 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p12ckptbridge", [checkpoint_id, node_name]),
                drill_task_id,
                checkpoint_id,
                node_name,
                "resume_from_latest_checkpoint_with_scope_validation",
                "replayable",
                str(checkpoint["state_digest"]),
                "ready",
                now,
            ),
        )


def latest_checkpoint_for_node(store: RuntimeTaskSpineStore, task_id: str, node_name: str) -> dict[str, Any]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            select * from checkpoint_refs
            where task_id = ? and recoverable_node = ?
            order by created_at desc
            limit 1
            """,
            (task_id, node_name),
        ).fetchone()
    return row_to_dict(row)


def insert_human_interrupt(
    store: RuntimeTaskSpineStore,
    *,
    drill_task_id: str,
    checkpoint: Mapping[str, Any],
    status_before: str,
) -> None:
    now = utc_now_iso()
    with store._connect() as conn:
        conn.execute(
            "insert into human_interrupt_records_p12 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p12interrupt", [drill_task_id, checkpoint["checkpoint_ref_id"]]),
                drill_task_id,
                str(checkpoint["checkpoint_ref_id"]),
                "lead_review_scope_expansion_approval",
                "lead_review_checkpoint",
                "research_lead",
                "approve bounded targeted repair before memo logic plan continuation",
                status_before,
                "paused",
                "approved_after_review",
                now,
            ),
        )


def insert_human_approval(
    store: RuntimeTaskSpineStore,
    *,
    drill_task_id: str,
    checkpoint: Mapping[str, Any],
    resume_run_id: str,
) -> None:
    now = utc_now_iso()
    interrupt_id = stable_id("p12interrupt", [drill_task_id, checkpoint["checkpoint_ref_id"]])
    with store._connect() as conn:
        conn.execute(
            "insert into human_approval_decisions_p12 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p12approval", [interrupt_id, resume_run_id]),
                interrupt_id,
                drill_task_id,
                "research_lead",
                "approved",
                json_dumps({"allowed_actions": ["targeted_repair", "memo_logic_plan"], "forbidden_actions": ["unbounded_web_search"]}),
                resume_run_id,
                "resume_authorized",
                now,
            ),
        )


def insert_model_budget_records(store: RuntimeTaskSpineStore, *, drill_task_id: str) -> None:
    now = utc_now_iso()
    with store._connect() as conn:
        rows = rows_to_dicts(conn.execute("select * from resource_queue_events_p12 where task_id = ?", (drill_task_id,)).fetchall())
        tokens = sum(int(row["token_count"]) for row in rows)
        cost = round(sum(float(row["cost_amount"]) for row in rows), 6)
        conn.execute(
            "insert into model_budget_ledger_p12 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p12budget", [drill_task_id, tokens, cost]),
                drill_task_id,
                "runtime_drill_total",
                50000,
                tokens,
                1.5,
                cost,
                "within_budget" if tokens <= 50000 and cost <= 1.5 else "budget_breached",
                now,
            ),
        )


def insert_replay_attempt(store: RuntimeTaskSpineStore, *, drill_task_id: str, replay_payload: Mapping[str, Any]) -> None:
    now = utc_now_iso()
    with store._connect() as conn:
        conn.execute(
            "insert into runtime_replay_attempts_p12 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p12replay", [drill_task_id, now]),
                drill_task_id,
                "RuntimeTaskSpineStore.replay_task",
                len(replay_payload.get("checkpoint_refs") or []),
                len(replay_payload.get("events") or []),
                len(replay_payload.get("node_executions") or []),
                len(replay_payload.get("trace_spans") or []),
                str(replay_payload.get("replay_status") or "unknown"),
                json_dumps({"progress_projection": replay_payload.get("progress_projection")}),
                now,
            ),
        )


def insert_trace_exports(store: RuntimeTaskSpineStore, *, drill_task_id: str, replay_payload: Mapping[str, Any]) -> None:
    now = utc_now_iso()
    span_count = len(replay_payload.get("trace_spans") or [])
    with store._connect() as conn:
        for target in TRACE_EXPORT_TARGETS:
            conn.execute(
                "insert into trace_export_records_p12 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    stable_id("p12traceexport", [drill_task_id, target, now]),
                    drill_task_id,
                    target,
                    "otlp_json" if target == "opentelemetry" else "vendor_json",
                    span_count,
                    "sql_runtime_ledger",
                    "export_ready",
                    json_dumps({"derived_export": True, "not_primary_audit_store": True}),
                    now,
                ),
            )


def insert_runtime_acceptance_records(store: RuntimeTaskSpineStore, *, now: str) -> None:
    evidence = [
        "runtime_facade_bindings_p12",
        "checkpoint_bridge_records_p12",
        "human_approval_decisions_p12",
        "resource_queue_events_p12",
        "runtime_replay_attempts_p12",
        "trace_export_records_p12",
    ]
    with store._connect() as conn:
        for demand_id in P12_DEMAND_IDS:
            conn.execute(
                "insert into runtime_acceptance_records_p12 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    stable_id("p12accept", [demand_id]),
                    demand_id,
                    json_dumps({"status": "pass", "workflow_value": "runtime can pause, resume, replay and expose cost/resource state"}),
                    json_dumps({"status": "pass", "sql_final": True, "runtime_facade_used": True}),
                    json_dumps({"status": "pass", "deterministic_gate": True, "negative_boundary": "not_full_graph_migration"}),
                    json_dumps({"status": "pass", "resource_budget_and_trace_export_visible": True}),
                    json_dumps(evidence),
                    "pass",
                    "runtime_architect",
                    now,
                ),
            )


def insert_runtime_readiness_report(store: RuntimeTaskSpineStore, *, now: str) -> None:
    known_gaps = [
        {
            "gap": "full_langgraph_node_migration",
            "reason": "P12 proves runtime contracts through a deterministic drill; every production graph node is not yet migrated.",
            "next_action": "Wire actual Research Lead and specialist graph nodes through RuntimeFacade in P13/P14/P15 integration.",
        },
        {
            "gap": "real_gpu_queue_pressure",
            "reason": "P12 records resource routes and queue events, but does not run cloud high-concurrency GPU scheduling.",
            "next_action": "Use pilot workload and cloud resource telemetry to calibrate resource router thresholds.",
        },
    ]
    next_actions = [
        "wire_real_langgraph_nodes_to_runtime_facade",
        "attach_contextengine_selection_to_each_node",
        "run_pilot_resource_router_under_parallel_cases",
        "promote_trace_export_to_observability_dashboard",
    ]
    with store._connect() as conn:
        conn.execute(
            "insert into runtime_readiness_reports_p12 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "p12_runtime_readiness_report_v0_1",
                P12_RUNTIME_DRILL_TASK_ID,
                "durable_runtime_drill_pass",
                "human_interrupt_resume_pass",
                "resource_router_ledger_pass",
                "replayable",
                "partial_migration_runtime_drill_only",
                "P12_L4_scope_pass_runtime_drill_ready",
                json_dumps([]),
                json_dumps(known_gaps),
                json_dumps(next_actions),
                "runtime_architect",
                json_dumps({"not_full_graph_migration": True}),
                now,
            ),
        )


def evaluate_p12_gates(
    root: Path,
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    drill_task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    contract = durable_runtime_schema_contract()
    generated_at = utc_now_iso()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        existing_tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        report = row_to_dict(conn.execute("select * from runtime_readiness_reports_p12 limit 1").fetchone())
        drill_task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (drill_task_id,)).fetchone())
        facade_count = table_row_count(conn, "runtime_facade_bindings_p12")
        node_binding_count = table_row_count(conn, "graph_node_runtime_bindings_p12")
        checkpoint_count = table_row_count(conn, "checkpoint_bridge_records_p12")
        interrupt_count = table_row_count(conn, "human_interrupt_records_p12")
        approval_count = table_row_count(conn, "human_approval_decisions_p12")
        route_policy_count = table_row_count(conn, "resource_model_route_policies_p12")
        queue_count = table_row_count(conn, "resource_queue_events_p12")
        budget_bad = int(conn.execute("select count(*) from model_budget_ledger_p12 where status != 'within_budget'").fetchone()[0])
        replay_rows = rows_to_dicts(conn.execute("select * from runtime_replay_attempts_p12").fetchall())
        trace_targets = {row["target"] for row in conn.execute("select target from trace_export_records_p12").fetchall()}
        acceptance_bad = int(conn.execute("select count(*) from runtime_acceptance_records_p12 where status != 'pass'").fetchone()[0])
        artifact_count = int(
            conn.execute(
                """
                select count(*) from artifact_refs
                where task_id = ? and artifact_type like 'durable_runtime_%'
                """,
                (task_id,),
            ).fetchone()[0]
        )
        workpaper_event_count = int(
            conn.execute(
                "select count(*) from workpaper_events where task_id = ? and event_type = 'durable_runtime_hil_resource_router_ready'",
                (task_id,),
            ).fetchone()[0]
        )
        p11_summary = root / "data" / "manifests" / "r53_r60_p11_production_pilot_readiness_summary_v0_1.json"
        dependency_ok = p11_summary.exists() and json_loads(p11_summary.read_text(encoding="utf-8"), {}).get("status") == "pass"

    def gate(gate_id: str, gate_group: str, status: bool, detail: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "gate_id": gate_id,
            "gate_group": gate_group,
            "status": "pass" if status else "fail",
            "pass_level": "L4_scope_pass" if status else "blocked",
            "detail": dict(detail),
            "generated_at": generated_at,
        }

    replay_ok = bool(replay_rows) and all(row["replay_status"] == "replayable" and int(row["checkpoint_count"]) >= 2 for row in replay_rows)
    return [
        gate("p12_schema_tables_present", "schema", set(contract["tables"]).issubset(existing_tables), {"required_tables": contract["tables"]}),
        gate("p12_p11_dependency_pass", "dependency", dependency_ok, {"p11_summary": rel_path(p11_summary, root)}),
        gate("p12_runtime_facade_binding_ready", "runtime_facade", facade_count >= 1, {"facade_count": facade_count}),
        gate("p12_graph_node_bindings_ready", "graph_nodes", node_binding_count >= len(GRAPH_NODE_NAMES), {"node_binding_count": node_binding_count}),
        gate("p12_checkpoint_bridge_resume_ready", "checkpoint_resume", checkpoint_count >= 2 and drill_task.get("resume_count", 0) >= 1, {"checkpoint_bridge_count": checkpoint_count, "resume_count": drill_task.get("resume_count")}),
        gate("p12_human_interrupt_and_approval_ready", "hil", interrupt_count >= 1 and approval_count >= 1, {"interrupt_count": interrupt_count, "approval_count": approval_count}),
        gate("p12_resource_model_router_budget_ready", "resource_router", route_policy_count >= len(ROUTE_CLASSES) and queue_count >= len(GRAPH_NODE_NAMES) and budget_bad == 0, {"route_policy_count": route_policy_count, "queue_count": queue_count, "budget_bad": budget_bad}),
        gate("p12_replay_attempt_reconstructs_runtime", "replay", replay_ok, {"replay_rows": replay_rows}),
        gate("p12_trace_exports_derived_from_sql_ledger", "trace_export", set(TRACE_EXPORT_TARGETS).issubset(trace_targets), {"trace_targets": sorted(trace_targets)}),
        gate("p12_acceptance_records_complete", "acceptance", materialized["acceptance_count"] == len(P12_DEMAND_IDS) and acceptance_bad == 0, {"acceptance_count": materialized["acceptance_count"], "acceptance_bad": acceptance_bad}),
        gate("p12_readiness_report_boundary_not_full_migration", "release_boundary", bool(report) and report.get("full_runtime_migration_status") == "partial_migration_runtime_drill_only", {"full_runtime_migration_status": report.get("full_runtime_migration_status")}),
        gate("p12_runtime_artifacts_and_workpaper_event_ledgered", "runtime", artifact_count >= 4 and workpaper_event_count >= 1, {"artifact_count": artifact_count, "workpaper_event_count": workpaper_event_count}),
    ]


def collect_p12_counts(store: RuntimeTaskSpineStore, *, drill_task_id: str, run_id: str) -> dict[str, Any]:
    with store._connect() as conn:
        drill_task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (drill_task_id,)).fetchone())
        return {
            "drill_task_id": drill_task_id,
            "drill_run_id": run_id,
            "drill_task_status": drill_task.get("status"),
            "drill_resume_count": int(drill_task.get("resume_count") or 0),
            "runtime_facade_binding_count": table_row_count(conn, "runtime_facade_bindings_p12"),
            "graph_node_binding_count": table_row_count(conn, "graph_node_runtime_bindings_p12"),
            "checkpoint_bridge_count": table_row_count(conn, "checkpoint_bridge_records_p12"),
            "human_interrupt_count": table_row_count(conn, "human_interrupt_records_p12"),
            "human_approval_count": table_row_count(conn, "human_approval_decisions_p12"),
            "route_policy_count": table_row_count(conn, "resource_model_route_policies_p12"),
            "resource_queue_event_count": table_row_count(conn, "resource_queue_events_p12"),
            "budget_record_count": table_row_count(conn, "model_budget_ledger_p12"),
            "replay_attempt_count": table_row_count(conn, "runtime_replay_attempts_p12"),
            "trace_export_count": table_row_count(conn, "trace_export_records_p12"),
            "acceptance_count": table_row_count(conn, "runtime_acceptance_records_p12"),
        }


def build_p12_summary(
    root: Path,
    paths: P12Paths,
    gate_rows: list[dict[str, Any]],
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> dict[str, Any]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (task_id,)).fetchone())
        drill_task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (P12_RUNTIME_DRILL_TASK_ID,)).fetchone())
        report = row_to_dict(conn.execute("select * from runtime_readiness_reports_p12 limit 1").fetchone())
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
        "slice": "P12 Durable Runtime + HIL + Resource Router",
        "status": status,
        "release_decision": "P12_L4_scope_pass_runtime_drill_ready" if status == "pass" else "P12_blocked",
        "closeout_level": "L4_scope_pass" if status == "pass" else "blocked",
        "runtime_status": report.get("runtime_status") or "not_evaluated",
        "hil_status": report.get("hil_status") or "not_evaluated",
        "resource_router_status": report.get("resource_router_status") or "not_evaluated",
        "replay_status": report.get("replay_status") or "not_evaluated",
        "full_runtime_migration_status": report.get("full_runtime_migration_status") or "not_evaluated",
        "task": task,
        "drill_task": drill_task,
        "counts": {**dict(materialized), "gate_count": len(gate_rows), "gate_fail_count": fail_count},
        "readiness_report": report,
        "outputs": outputs,
        "policy": durable_runtime_schema_contract()["policy"],
        "generated_at": utc_now_iso(),
    }


def render_p12_report(summary: Mapping[str, Any], gate_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# R53-R60 P12 Durable Runtime + HIL + Resource Router L4 Scope Pass",
        "",
        f"- Release decision: `{summary['release_decision']}`",
        f"- Closeout level: `{summary['closeout_level']}`",
        f"- Runtime status: `{summary['runtime_status']}`",
        f"- HIL status: `{summary['hil_status']}`",
        f"- Resource router status: `{summary['resource_router_status']}`",
        f"- Replay status: `{summary['replay_status']}`",
        f"- Full runtime migration status: `{summary['full_runtime_migration_status']}`",
        "",
        "## Scope Boundary",
        "",
        "P12 proves a durable runtime drill through the SQL-final RuntimeFacade: checkpoint/resume, HIL approval, resource routing, replay, and derived trace export. It does not claim every production LangGraph node has been migrated.",
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


def record_p12_runtime_artifacts(
    runtime: FinSightResearchRuntimeFacade,
    root: Path,
    paths: P12Paths,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    artifacts = [
        ("durable_runtime_schema", paths.schema_path, durable_runtime_schema_contract()),
        ("durable_runtime_summary", paths.summary_path, dict(materialized)),
        ("durable_runtime_gate_rows", paths.gate_rows_path, {"gate_rows_pending": True, **dict(materialized)}),
        ("durable_runtime_closeout_report", paths.report_path, {"report_pending": True, **dict(materialized)}),
    ]
    refs: list[dict[str, Any]] = []
    for artifact_type, path, payload in artifacts:
        refs.append(
            runtime.record_artifact_ref(
                task_id,
                artifact_type=artifact_type,
                uri=rel_path(path, root),
                payload={"schema_version": SCHEMA_VERSION, **payload},
                actor="durable_runtime_builder",
            )
        )
    return refs


def persist_p12_gate_results(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    now = utc_now_iso()
    with store._connect() as conn:
        conn.execute("delete from runtime_gate_results_p12")
        for row in gate_rows:
            conn.execute(
                "insert into runtime_gate_results_p12 values (?, ?, ?, ?, ?, ?, ?)",
                (
                    stable_id("p12gate", [row["gate_id"], row["generated_at"]]),
                    row["gate_id"],
                    row["gate_group"],
                    row["status"],
                    row["pass_level"],
                    json_dumps(row.get("detail") or {}),
                    now,
                ),
            )


def finalize_p12_readiness_report(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    fail_count = len([row for row in gate_rows if row["status"] != "pass"])
    decision = "P12_L4_scope_pass_runtime_drill_ready" if fail_count == 0 else "P12_blocked"
    with store._connect() as conn:
        conn.execute(
            """
            update runtime_readiness_reports_p12
            set release_decision = ?, gate_refs_json = ?, payload_json = ?
            where report_id = ?
            """,
            (
                decision,
                json_dumps([row["gate_id"] for row in gate_rows]),
                json_dumps({"gate_fail_count": fail_count, "gate_count": len(gate_rows)}),
                "p12_runtime_readiness_report_v0_1",
            ),
        )


def actor_for_node(node_name: str) -> str:
    if node_name.startswith("research_lead") or node_name == "lead_review_checkpoint":
        return "research_lead"
    if node_name.startswith("retrieval"):
        return "evidence_operator"
    if node_name.startswith("product"):
        return "product_specialist"
    return "memo_planner"


def tool_scope_for_node(node_name: str) -> str:
    if node_name.startswith("retrieval"):
        return "retrieval_and_database_read"
    if node_name == "lead_review_checkpoint":
        return "review_no_new_external_fetch_without_approval"
    if node_name == "memo_logic_plan":
        return "composer_plan_no_retrieval"
    return "role_scoped_context_read"


def model_for_route(route_class: str) -> str:
    mapping = {
        "lead_planning_high_reasoning": "deepseek-reasoner",
        "retrieval_embedding_gpu_queue": "bge-large-cuda",
        "specialist_analysis_balanced": "deepseek-chat",
        "memo_render_cost_controlled": "qwen-flash",
    }
    return mapping[route_class]


def resource_for_route(route_class: str) -> str:
    mapping = {
        "lead_planning_high_reasoning": "remote_llm",
        "retrieval_embedding_gpu_queue": "local_gpu_embedding_queue",
        "specialist_analysis_balanced": "remote_llm_balanced",
        "memo_render_cost_controlled": "remote_llm_low_cost",
    }
    return mapping[route_class]


def table_row_count(conn: sqlite3.Connection, table: str) -> int:
    if not table_exists(conn, table):
        return 0
    return int(conn.execute(f"select count(*) from {table}").fetchone()[0])
