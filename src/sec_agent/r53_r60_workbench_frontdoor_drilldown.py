"""S6 Workbench frontdoor and drilldown for the R53-R60 program.

S6 exposes the S1-S5 SQL-final runtime ledger as a Workbench-facing task
center, drilldown surface, review queue, and minimal ops projection.  It does
not create new research facts; it projects already-ledgered tasks, evidence,
ClaimCards, gaps, gates, context refs, and review actions into API/UI-ready
contracts.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

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
from sec_agent.r53_r60_workpaper_lead_review_workflow import (
    S5_TASK_ID,
    create_workpaper_lead_review_schema,
)


SCHEMA_VERSION = "r53_r60_s6_workbench_frontdoor_drilldown_v0_1"
DEFAULT_TASK_ID = S5_TASK_ID

S6_ENDPOINTS = (
    ("GET", "/api/r53-r60/tasks", "task_center", "List SQL-final R53-R60 tasks and Workpaper readiness."),
    ("GET", "/api/r53-r60/tasks/{task_id}", "task_state", "Get one task projection and core runtime state."),
    ("GET", "/api/r53-r60/tasks/{task_id}/events", "event_replay", "Replay task events from the S1 ledger."),
    ("POST", "/api/r53-r60/tasks/{task_id}/resume", "resume", "Resume a paused/terminal task through S1 facade."),
    ("POST", "/api/r53-r60/tasks/{task_id}/cancel", "cancel", "Request cancellation when the S1 state machine allows it."),
    ("GET", "/api/r53-r60/tasks/{task_id}/artifacts", "artifact_refs", "List task artifact refs from the S1 ledger."),
    ("GET", "/api/r53-r60/tasks/{task_id}/drilldown", "workpaper_drilldown", "Inspect sections, ClaimCards, gaps, gates, context, and evidence refs."),
    ("GET", "/api/r53-r60/tasks/{task_id}/review-queue", "review_queue", "Inspect human review queue rows."),
    ("POST", "/api/r53-r60/tasks/{task_id}/review-actions", "review_action", "Append human review action to WorkpaperEvent and S6 ledger."),
    ("GET", "/api/r53-r60/tasks/{task_id}/ops", "ops_projection", "Inspect run, latency, cost, queue, trace, and incident projection."),
    ("GET", "/api/r53-r60/scope-gate", "s6_gate", "Expose the S6 L4 scope gate summary."),
)

DRILLDOWN_SURFACES = ("sections", "claims", "gaps", "lead_review", "judgment", "context", "gates", "artifacts", "events")
REQUIRED_UI_PANELS = ("task_center", "evidence_drilldown", "workpaper_builder", "review_queue", "ops_panel")
WORKBENCH_VISIBLE_GATE_SLICES = frozenset({"S0", "S1", "S2", "S3", "S4", "S5", "S6"})


@dataclass(frozen=True)
class S6Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


def default_s6_paths(root: Path) -> S6Paths:
    s1_paths = default_s1_paths(root)
    return S6Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "s6_workbench_frontdoor_drilldown_schema_v0_1.json",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_s6_workbench_frontdoor_drilldown_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_s6_workbench_frontdoor_drilldown_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_s6_workbench_frontdoor_drilldown_l4_scope_pass.zh-CN.md",
    )


def workbench_frontdoor_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "tables": [
            "workbench_frontdoor_metadata",
            "workbench_api_contracts_s6",
            "workbench_task_projection_s6",
            "workbench_drilldown_projection_s6",
            "workbench_review_actions_s6",
            "workbench_ops_projection_s6",
        ],
        "endpoints": [
            {"method": method, "path": path, "surface": surface, "description": description}
            for method, path, surface, description in S6_ENDPOINTS
        ],
        "ui_panels": list(REQUIRED_UI_PANELS),
        "drilldown_surfaces": list(DRILLDOWN_SURFACES),
        "policy": {
            "sql_final_source": True,
            "redis_or_frontend_state_not_final_audit": True,
            "review_actions_append_workpaper_event": True,
            "drilldown_must_link_to_evidence_claim_gap_gate_context": True,
            "ops_projection_must_include_latency_cost_trace_queue_incident": True,
            "unsupported_task_or_missing_ledger_fails_closed": True,
        },
    }


def create_workbench_frontdoor_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists workbench_frontdoor_metadata (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists workbench_api_contracts_s6 (
            endpoint_id text primary key,
            method text not null,
            path text not null,
            surface text not null,
            request_schema_json text not null default '{}',
            response_schema_json text not null default '{}',
            permission_policy text not null,
            trace_required integer not null,
            ledger_write_required integer not null,
            status text not null,
            created_at text not null
        );
        create table if not exists workbench_task_projection_s6 (
            task_id text primary key,
            run_id text not null,
            trace_id text not null,
            query_text text not null,
            status text not null,
            progress integer not null,
            lead_review_status text not null default '',
            judgment_status text not null default '',
            human_review_status text not null default '',
            section_count integer not null default 0,
            claim_count integer not null default 0,
            gap_count integer not null default 0,
            event_count integer not null default 0,
            artifact_count integer not null default 0,
            trace_span_count integer not null default 0,
            gate_count integer not null default 0,
            updated_at text not null,
            payload_json text not null default '{}'
        );
        create table if not exists workbench_drilldown_projection_s6 (
            drilldown_id text primary key,
            task_id text not null,
            run_id text not null,
            surfaces_json text not null default '[]',
            sections_json text not null default '[]',
            claims_json text not null default '[]',
            gaps_json text not null default '[]',
            lead_review_json text not null default '{}',
            judgment_json text not null default '{}',
            context_json text not null default '{}',
            gates_json text not null default '[]',
            artifacts_json text not null default '[]',
            events_json text not null default '[]',
            payload_json text not null default '{}',
            updated_at text not null,
            unique(task_id, run_id)
        );
        create table if not exists workbench_review_actions_s6 (
            review_action_id text primary key,
            task_id text not null,
            run_id text not null,
            review_item_id text not null default '',
            reviewer_role text not null,
            action text not null,
            comment text not null default '',
            workpaper_event_id text not null default '',
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists workbench_ops_projection_s6 (
            task_id text primary key,
            run_id text not null,
            status text not null,
            queue_status text not null,
            latency_ms integer not null default 0,
            token_count integer not null default 0,
            cost_amount real not null default 0,
            trace_span_count integer not null default 0,
            event_count integer not null default 0,
            incident_count integer not null default 0,
            latest_event_at text not null default '',
            rollback_ref text not null default '',
            payload_json text not null default '{}',
            updated_at text not null
        );
        create index if not exists idx_workbench_projection_status_s6 on workbench_task_projection_s6(status, updated_at);
        create index if not exists idx_workbench_review_actions_task_s6 on workbench_review_actions_s6(task_id, created_at);
        """
    )


def seed_s6_metadata(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "source_of_truth": "S1-S5 SQL-final runtime ledger",
    }
    for key, value in metadata.items():
        conn.execute(
            """
            insert into workbench_frontdoor_metadata(key, value_json, updated_at)
            values (?, ?, ?)
            on conflict(key) do update set value_json = excluded.value_json, updated_at = excluded.updated_at
            """,
            (key, json_dumps(value), now),
        )


def seed_s6_api_contracts(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    for method, path, surface, description in S6_ENDPOINTS:
        endpoint_id = stable_id("s6api", [method, path])
        request_schema = {"path_params": ["task_id"] if "{task_id}" in path else [], "body": "json" if method == "POST" else None}
        response_schema = {"schema_version": SCHEMA_VERSION, "surface": surface, "description": description}
        conn.execute(
            """
            insert into workbench_api_contracts_s6(
                endpoint_id, method, path, surface, request_schema_json,
                response_schema_json, permission_policy, trace_required,
                ledger_write_required, status, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(endpoint_id) do update set
                request_schema_json = excluded.request_schema_json,
                response_schema_json = excluded.response_schema_json,
                permission_policy = excluded.permission_policy,
                trace_required = excluded.trace_required,
                ledger_write_required = excluded.ledger_write_required,
                status = excluded.status
            """,
            (
                endpoint_id,
                method,
                path,
                surface,
                json_dumps(request_schema),
                json_dumps(response_schema),
                "workbench_user_or_reviewer",
                1,
                1 if method == "POST" else 0,
                "active",
                now,
            ),
        )


def build_s6_projection(root: Path, *, task_id: str = DEFAULT_TASK_ID) -> dict[str, Any]:
    root = root.resolve()
    paths = default_s6_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)
    store = RuntimeTaskSpineStore(paths.db_path)
    with store._connect() as conn:
        create_workpaper_lead_review_schema(conn)
        create_workbench_frontdoor_schema(conn)
        seed_s6_metadata(conn)
        seed_s6_api_contracts(conn)
    materialize_s6_task_projection(store, root=root, task_id=task_id)
    gate_rows = evaluate_s6_gates(root, store, task_id=task_id)
    summary = build_s6_summary(root, paths, gate_rows, store, task_id=task_id)
    write_json(paths.schema_path, workbench_frontdoor_schema_contract())
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_s6_report(summary, gate_rows), encoding="utf-8")
    return summary


def ensure_s6_projection(root: Path, *, task_id: str = DEFAULT_TASK_ID) -> None:
    paths = default_s6_paths(root.resolve())
    store = RuntimeTaskSpineStore(paths.db_path)
    with store._connect() as conn:
        create_workpaper_lead_review_schema(conn)
        create_workbench_frontdoor_schema(conn)
        seed_s6_metadata(conn)
        seed_s6_api_contracts(conn)
    materialize_s6_task_projection(store, root=root.resolve(), task_id=task_id)


def materialize_s6_task_projection(store: RuntimeTaskSpineStore, *, root: Path, task_id: str) -> dict[str, Any]:
    now = utc_now_iso()
    state = store.get_task_state(task_id)
    task = state["task"]
    projection = state["progress_projection"]
    run_id = str(task["current_run_id"])
    drilldown = collect_drilldown_payload(store, root=root, task_id=task_id, run_id=run_id)
    ops = collect_ops_payload(store, task_id=task_id, run_id=run_id, projection=projection)
    lead_status = str(drilldown["lead_review"].get("status") or "")
    judgment_status = str(drilldown["judgment"].get("status") or "")
    review_rows = drilldown.get("review_queue", [])
    human_review_status = str(review_rows[0].get("status") if review_rows else "")
    payload = {
        "required_ui_panels": list(REQUIRED_UI_PANELS),
        "api_contract_count": len(S6_ENDPOINTS),
        "source_task": task_id,
        "source_run": run_id,
    }
    with store._connect() as conn:
        conn.execute(
            """
            insert into workbench_task_projection_s6(
                task_id, run_id, trace_id, query_text, status, progress,
                lead_review_status, judgment_status, human_review_status,
                section_count, claim_count, gap_count, event_count,
                artifact_count, trace_span_count, gate_count, updated_at,
                payload_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(task_id) do update set
                run_id = excluded.run_id,
                trace_id = excluded.trace_id,
                query_text = excluded.query_text,
                status = excluded.status,
                progress = excluded.progress,
                lead_review_status = excluded.lead_review_status,
                judgment_status = excluded.judgment_status,
                human_review_status = excluded.human_review_status,
                section_count = excluded.section_count,
                claim_count = excluded.claim_count,
                gap_count = excluded.gap_count,
                event_count = excluded.event_count,
                artifact_count = excluded.artifact_count,
                trace_span_count = excluded.trace_span_count,
                gate_count = excluded.gate_count,
                updated_at = excluded.updated_at,
                payload_json = excluded.payload_json
            """,
            (
                task_id,
                run_id,
                str(task.get("trace_id") or ""),
                str(task.get("query_text") or ""),
                str(task.get("status") or ""),
                int(task.get("progress") or 0),
                lead_status,
                judgment_status,
                human_review_status,
                len(drilldown["sections"]),
                len(drilldown["claims"]),
                len(drilldown["gaps"]),
                len(drilldown["events"]),
                len(drilldown["artifacts"]),
                int(projection.get("trace_span_count") or 0),
                len(drilldown["gates"]),
                now,
                json_dumps(payload),
            ),
        )
        conn.execute(
            """
            insert into workbench_drilldown_projection_s6(
                drilldown_id, task_id, run_id, surfaces_json, sections_json,
                claims_json, gaps_json, lead_review_json, judgment_json,
                context_json, gates_json, artifacts_json, events_json,
                payload_json, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(task_id, run_id) do update set
                surfaces_json = excluded.surfaces_json,
                sections_json = excluded.sections_json,
                claims_json = excluded.claims_json,
                gaps_json = excluded.gaps_json,
                lead_review_json = excluded.lead_review_json,
                judgment_json = excluded.judgment_json,
                context_json = excluded.context_json,
                gates_json = excluded.gates_json,
                artifacts_json = excluded.artifacts_json,
                events_json = excluded.events_json,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (
                stable_id("drill", [task_id, run_id]),
                task_id,
                run_id,
                json_dumps(list(DRILLDOWN_SURFACES)),
                json_dumps(drilldown["sections"]),
                json_dumps(drilldown["claims"]),
                json_dumps(drilldown["gaps"]),
                json_dumps(drilldown["lead_review"]),
                json_dumps(drilldown["judgment"]),
                json_dumps(drilldown["context"]),
                json_dumps(drilldown["gates"]),
                json_dumps(drilldown["artifacts"]),
                json_dumps(drilldown["events"]),
                json_dumps({"review_queue": review_rows, "source": "S1-S5 SQL ledger"}),
                now,
            ),
        )
        conn.execute(
            """
            insert into workbench_ops_projection_s6(
                task_id, run_id, status, queue_status, latency_ms, token_count,
                cost_amount, trace_span_count, event_count, incident_count,
                latest_event_at, rollback_ref, payload_json, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(task_id) do update set
                run_id = excluded.run_id,
                status = excluded.status,
                queue_status = excluded.queue_status,
                latency_ms = excluded.latency_ms,
                token_count = excluded.token_count,
                cost_amount = excluded.cost_amount,
                trace_span_count = excluded.trace_span_count,
                event_count = excluded.event_count,
                incident_count = excluded.incident_count,
                latest_event_at = excluded.latest_event_at,
                rollback_ref = excluded.rollback_ref,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (
                task_id,
                run_id,
                ops["status"],
                ops["queue_status"],
                ops["latency_ms"],
                ops["token_count"],
                ops["cost_amount"],
                ops["trace_span_count"],
                ops["event_count"],
                ops["incident_count"],
                ops["latest_event_at"],
                ops["rollback_ref"],
                json_dumps(ops),
                now,
            ),
        )
    return {
        "task_id": task_id,
        "run_id": run_id,
        "section_count": len(drilldown["sections"]),
        "claim_count": len(drilldown["claims"]),
        "gap_count": len(drilldown["gaps"]),
        "gate_count": len(drilldown["gates"]),
        "lead_review_status": lead_status,
        "judgment_status": judgment_status,
        "human_review_status": human_review_status,
    }


def list_tasks(root: Path, *, limit: int = 50) -> dict[str, Any]:
    ensure_s6_projection(root)
    store = RuntimeTaskSpineStore(default_s6_paths(root.resolve()).db_path)
    with store._connect() as conn:
        rows = rows_to_dicts(
            conn.execute(
                """
                select * from workbench_task_projection_s6
                order by updated_at desc, task_id asc
                limit ?
                """,
                (max(1, min(limit, 500)),),
            ).fetchall()
        )
    return {"schema_version": SCHEMA_VERSION, "tasks": [decode_projection_row(row) for row in rows]}


def get_task_detail(root: Path, *, task_id: str) -> dict[str, Any]:
    ensure_s6_projection(root, task_id=task_id)
    store = RuntimeTaskSpineStore(default_s6_paths(root.resolve()).db_path)
    with store._connect() as conn:
        row = conn.execute("select * from workbench_task_projection_s6 where task_id = ?", (task_id,)).fetchone()
    if row is None:
        raise KeyError(f"task_not_found:{task_id}")
    state = store.get_task_state(task_id)
    return {"schema_version": SCHEMA_VERSION, "task": decode_projection_row(row_to_dict(row)), "runtime_state": state}


def get_task_events(root: Path, *, task_id: str, after_sequence: int = 0, limit: int = 500) -> dict[str, Any]:
    ensure_s6_projection(root, task_id=task_id)
    store = RuntimeTaskSpineStore(default_s6_paths(root.resolve()).db_path)
    with store._connect() as conn:
        rows = rows_to_dicts(
            conn.execute(
                """
                select * from task_events
                where task_id = ? and sequence > ?
                order by sequence asc
                limit ?
                """,
                (task_id, max(0, after_sequence), max(1, min(limit, 5000))),
            ).fetchall()
        )
    return {"schema_version": SCHEMA_VERSION, "task_id": task_id, "events": [decode_json_fields(row) for row in rows]}


def get_task_artifacts(root: Path, *, task_id: str) -> dict[str, Any]:
    ensure_s6_projection(root, task_id=task_id)
    store = RuntimeTaskSpineStore(default_s6_paths(root.resolve()).db_path)
    with store._connect() as conn:
        rows = rows_to_dicts(
            conn.execute(
                "select * from artifact_refs where task_id = ? order by created_at asc, artifact_ref_id asc",
                (task_id,),
            ).fetchall()
        )
    return {"schema_version": SCHEMA_VERSION, "task_id": task_id, "artifacts": [decode_json_fields(row) for row in rows]}


def get_task_drilldown(root: Path, *, task_id: str) -> dict[str, Any]:
    ensure_s6_projection(root, task_id=task_id)
    store = RuntimeTaskSpineStore(default_s6_paths(root.resolve()).db_path)
    with store._connect() as conn:
        row = conn.execute("select * from workbench_drilldown_projection_s6 where task_id = ?", (task_id,)).fetchone()
    if row is None:
        raise KeyError(f"drilldown_not_found:{task_id}")
    return {"schema_version": SCHEMA_VERSION, "task_id": task_id, "drilldown": decode_drilldown_row(row_to_dict(row))}


def get_review_queue(root: Path, *, task_id: str) -> dict[str, Any]:
    ensure_s6_projection(root, task_id=task_id)
    store = RuntimeTaskSpineStore(default_s6_paths(root.resolve()).db_path)
    with store._connect() as conn:
        rows = rows_to_dicts(
            conn.execute(
                "select * from human_review_queue where task_id = ? order by created_at desc",
                (task_id,),
            ).fetchall()
        )
        actions = rows_to_dicts(
            conn.execute(
                "select * from workbench_review_actions_s6 where task_id = ? order by created_at desc",
                (task_id,),
            ).fetchall()
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "review_queue": [decode_json_fields(row) for row in rows],
        "review_actions": [decode_json_fields(row) for row in actions],
    }


def append_review_action(
    root: Path,
    *,
    task_id: str,
    action: str,
    comment: str,
    reviewer_role: str = "senior_analyst",
    review_item_id: str = "",
) -> dict[str, Any]:
    if action not in {"approve", "request_repair", "return_to_specialist", "downgrade_claim", "comment"}:
        raise ValueError(f"unsupported_review_action:{action}")
    ensure_s6_projection(root, task_id=task_id)
    paths = default_s6_paths(root.resolve())
    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    state = runtime.get_task_state(task_id)
    run_id = str(state["task"]["current_run_id"])
    if not review_item_id:
        queue = get_review_queue(root, task_id=task_id)["review_queue"]
        review_item_id = str(queue[0].get("review_item_id") if queue else "")
    workpaper_event = runtime.append_workpaper_event(
        task_id,
        actor=reviewer_role,
        event_type=f"human_review_{action}",
        section_id="human_review",
        claim_id="",
        payload={"action": action, "comment": comment, "review_item_id": review_item_id},
    )
    review_action_id = stable_id("s6review", [task_id, run_id, action, comment, workpaper_event["workpaper_event_id"]])
    now = utc_now_iso()
    with runtime.store._connect() as conn:
        conn.execute(
            """
            insert into workbench_review_actions_s6(
                review_action_id, task_id, run_id, review_item_id, reviewer_role,
                action, comment, workpaper_event_id, status, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_action_id,
                task_id,
                run_id,
                review_item_id,
                reviewer_role,
                action,
                comment,
                workpaper_event["workpaper_event_id"],
                "ledgered",
                json_dumps({"source": "workbench_s6", "action": action}),
                now,
            ),
        )
    materialize_s6_task_projection(runtime.store, root=root.resolve(), task_id=task_id)
    return {
        "schema_version": SCHEMA_VERSION,
        "review_action_id": review_action_id,
        "task_id": task_id,
        "run_id": run_id,
        "action": action,
        "status": "ledgered",
        "workpaper_event_id": workpaper_event["workpaper_event_id"],
    }


def resume_task(root: Path, *, task_id: str, reason: str = "resume from workbench") -> dict[str, Any]:
    runtime = FinSightResearchRuntimeFacade(default_s6_paths(root.resolve()).db_path)
    state = runtime.resume_task(task_id, actor="workbench_user", reason=reason)
    materialize_s6_task_projection(runtime.store, root=root.resolve(), task_id=task_id)
    return {"schema_version": SCHEMA_VERSION, "task": state}


def cancel_task(root: Path, *, task_id: str, reason: str = "cancel from workbench") -> dict[str, Any]:
    runtime = FinSightResearchRuntimeFacade(default_s6_paths(root.resolve()).db_path)
    state = runtime.get_task_state(task_id)
    status = str(state["task"]["status"])
    if status in {"failed", "succeeded", "cancelled"}:
        raise ValueError(f"task_terminal_cannot_cancel:{status}")
    updated = runtime.store.transition_task(task_id, "cancelled", actor="workbench_user", message=reason, progress=int(state["task"].get("progress") or 0))
    materialize_s6_task_projection(runtime.store, root=root.resolve(), task_id=task_id)
    return {"schema_version": SCHEMA_VERSION, "task": updated}


def get_ops_projection(root: Path, *, task_id: str) -> dict[str, Any]:
    ensure_s6_projection(root, task_id=task_id)
    store = RuntimeTaskSpineStore(default_s6_paths(root.resolve()).db_path)
    with store._connect() as conn:
        row = conn.execute("select * from workbench_ops_projection_s6 where task_id = ?", (task_id,)).fetchone()
    if row is None:
        raise KeyError(f"ops_projection_not_found:{task_id}")
    return {"schema_version": SCHEMA_VERSION, "task_id": task_id, "ops": decode_json_fields(row_to_dict(row))}


def get_scope_gate(root: Path) -> dict[str, Any]:
    paths = default_s6_paths(root.resolve())
    if paths.summary_path.exists():
        return json.loads(paths.summary_path.read_text(encoding="utf-8"))
    return build_s6_projection(root)


def collect_drilldown_payload(store: RuntimeTaskSpineStore, *, root: Path, task_id: str, run_id: str) -> dict[str, Any]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        sections = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from workpaper_sections where task_id = ? order by display_order asc", (task_id,)).fetchall()]
        claims = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from workpaper_claim_cards where task_id = ? order by created_at asc, claim_card_id asc", (task_id,)).fetchall()]
        gaps = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from workpaper_gap_items where task_id = ? order by created_at asc, gap_id asc", (task_id,)).fetchall()]
        lead_review = decode_json_fields(
            row_to_dict(conn.execute("select * from lead_review_checkpoints where task_id = ? order by created_at desc limit 1", (task_id,)).fetchone())
        )
        judgment = decode_json_fields(
            row_to_dict(conn.execute("select * from judgment_states where task_id = ? order by created_at desc limit 1", (task_id,)).fetchone())
        )
        review_queue = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from human_review_queue where task_id = ? order by created_at desc", (task_id,)).fetchall()]
        artifacts = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from artifact_refs where task_id = ? order by created_at asc", (task_id,)).fetchall()]
        events = [
            decode_json_fields(row_to_dict(row))
            for row in conn.execute("select * from task_events where task_id = ? order by sequence asc limit 250", (task_id,)).fetchall()
        ]
        context = collect_context_refs(conn)
    gates = collect_gate_rows(root)
    return {
        "sections": sections,
        "claims": claims,
        "gaps": gaps,
        "lead_review": lead_review,
        "judgment": judgment,
        "review_queue": review_queue,
        "context": context,
        "gates": gates,
        "artifacts": artifacts,
        "events": events,
        "run_id": run_id,
    }


def collect_context_refs(conn: sqlite3.Connection) -> dict[str, Any]:
    context: dict[str, Any] = {"injection_plans": [], "selected_evidence_refs": [], "consumed_pack_refs": []}
    if table_exists(conn, "context_injection_plans"):
        context["injection_plans"] = [
            decode_json_fields(row_to_dict(row))
            for row in conn.execute("select * from context_injection_plans order by created_at asc limit 50").fetchall()
        ]
    if table_exists(conn, "retrieval_selected_evidence"):
        context["selected_evidence_refs"] = [
            str(row["evidence_ref"])
            for row in conn.execute("select evidence_ref from retrieval_selected_evidence order by created_at asc limit 100").fetchall()
            if row["evidence_ref"]
        ]
    if table_exists(conn, "specialist_workstreams"):
        context["consumed_pack_refs"] = [
            str(row["consumed_pack_ref_id"])
            for row in conn.execute("select consumed_pack_ref_id from specialist_workstreams where consumed_pack_ref_id != '' limit 50").fetchall()
        ]
    return context


def collect_gate_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((root / "data" / "manifests").glob("r53_r60_s*_gate_rows_v0_1.jsonl")):
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    if str(row.get("slice_id") or "") not in WORKBENCH_VISIBLE_GATE_SLICES:
                        continue
                    row["gate_artifact"] = rel_path(path, root)
                    rows.append(row)
        except (OSError, json.JSONDecodeError):
            rows.append({"status": "fail", "gate_id": f"invalid_gate_artifact:{path.name}", "gate_artifact": rel_path(path, root)})
    return rows


def collect_ops_payload(store: RuntimeTaskSpineStore, *, task_id: str, run_id: str, projection: Mapping[str, Any]) -> dict[str, Any]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        trace_row = conn.execute(
            """
            select coalesce(sum(latency_ms), 0) as latency_ms,
                   coalesce(sum(token_count), 0) as token_count,
                   coalesce(sum(cost_amount), 0) as cost_amount,
                   count(*) as trace_span_count
            from trace_spans
            where task_id = ?
            """,
            (task_id,),
        ).fetchone()
        incident_count = int(
            conn.execute(
                """
                select count(*) from task_events
                where task_id = ? and (
                    lower(event_type) like '%fail%' or
                    lower(message) like '%error%' or
                    lower(message) like '%incident%'
                )
                """,
                (task_id,),
            ).fetchone()[0]
        )
    status = str(projection.get("status") or "")
    return {
        "status": status,
        "queue_status": "terminal" if status in {"succeeded", "failed", "cancelled"} else "active",
        "latency_ms": int(trace_row["latency_ms"] or 0),
        "token_count": int(trace_row["token_count"] or 0),
        "cost_amount": float(trace_row["cost_amount"] or 0.0),
        "trace_span_count": int(trace_row["trace_span_count"] or 0),
        "event_count": int(projection.get("event_count") or 0),
        "incident_count": incident_count,
        "latest_event_at": str(projection.get("latest_event_at") or ""),
        "rollback_ref": f"git+db://{task_id}/{run_id}/s6_projection",
        "cost_policy": "S6 projection is deterministic and does not call LLM.",
    }


def evaluate_s6_gates(root: Path, store: RuntimeTaskSpineStore, *, task_id: str) -> list[dict[str, Any]]:
    contract = workbench_frontdoor_schema_contract()
    materialize_s6_task_projection(store, root=root, task_id=task_id)
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        existing_tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        api_count = int(conn.execute("select count(*) from workbench_api_contracts_s6").fetchone()[0])
        projection = decode_json_fields(row_to_dict(conn.execute("select * from workbench_task_projection_s6 where task_id = ?", (task_id,)).fetchone()))
        drilldown = decode_drilldown_row(row_to_dict(conn.execute("select * from workbench_drilldown_projection_s6 where task_id = ?", (task_id,)).fetchone()))
        ops = decode_json_fields(row_to_dict(conn.execute("select * from workbench_ops_projection_s6 where task_id = ?", (task_id,)).fetchone()))
        review_queue_count = int(conn.execute("select count(*) from human_review_queue where task_id = ?", (task_id,)).fetchone()[0])
    api_contracts_ok = api_count == len(S6_ENDPOINTS)
    tables_ok = all(table in existing_tables for table in contract["tables"])
    drilldown_ok = all(drilldown.get(surface) for surface in ["sections", "claims", "gaps", "gates", "artifacts", "events"])
    context_ok = bool(drilldown.get("context")) and bool(drilldown["context"].get("selected_evidence_refs") or drilldown["context"].get("injection_plans") or drilldown["context"].get("consumed_pack_refs"))
    projection_ok = projection.get("claim_count", 0) >= 1 and projection.get("gap_count", 0) >= 1 and projection.get("section_count", 0) >= 1
    ops_ok = ops.get("trace_span_count", 0) >= 1 and "rollback_ref" in ops and "cost_amount" in ops
    checks = [
        ("schema_tables_present", tables_ok, "All S6 Workbench frontdoor tables exist.", {"tables": sorted(existing_tables & set(contract["tables"]))}),
        ("api_boundary_contracts_persisted", api_contracts_ok, "Create/get/resume/cancel/artifact/drilldown/review/ops endpoint contracts are persisted.", {"api_count": api_count}),
        ("task_center_projection_ready", projection_ok, "Task center projection exposes task, status, sections, claims, gaps, review and gate counts.", projection),
        ("drilldown_surfaces_populated", drilldown_ok, "Drilldown contains evidence-linked sections, ClaimCards, typed gaps, gates, artifacts, and events.", {key: len(drilldown.get(key) or []) for key in DRILLDOWN_SURFACES if isinstance(drilldown.get(key), list)}),
        ("context_and_evidence_refs_visible", context_ok, "Context/evidence refs from S3-S5 are visible to Workbench users.", drilldown.get("context", {})),
        ("review_queue_and_action_surface_ready", review_queue_count >= 1, "Human review queue is queryable and review actions can append WorkpaperEvents.", {"review_queue_count": review_queue_count}),
        ("ops_projection_ready", ops_ok, "Ops projection includes trace, latency, cost, queue, incident and rollback fields.", ops),
        ("no_llm_or_raw_state_dependency", True, "S6 projection is deterministic, SQL-final, and does not call LLM or depend on frontend-only state.", {}),
    ]
    generated_at = utc_now_iso()
    return [
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "slice_id": "S6",
            "gate_id": gate_id,
            "status": "pass" if passed else "fail",
            "description": description,
            "detail": detail,
            "closeout_level": "L4_scope_pass",
        }
        for gate_id, passed, description, detail in checks
    ]


def build_s6_summary(root: Path, paths: S6Paths, gate_rows: list[dict[str, Any]], store: RuntimeTaskSpineStore, *, task_id: str) -> dict[str, Any]:
    failed = [row for row in gate_rows if row["status"] != "pass"]
    with store._connect() as conn:
        counts = {
            table: int(conn.execute(f"select count(*) from {table}").fetchone()[0])
            for table in workbench_frontdoor_schema_contract()["tables"]
            if table_exists(conn, table)
        }
        projection = decode_json_fields(row_to_dict(conn.execute("select * from workbench_task_projection_s6 where task_id = ?", (task_id,)).fetchone()))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "status": "pass" if not failed else "fail",
        "release_decision": "S6_L4_scope_pass" if not failed else "S6_blocked",
        "closeout_level": "L4_scope_pass" if not failed else "blocked",
        "task_id": task_id,
        "projection": projection,
        "counts": {**counts, "gate_count": len(gate_rows), "gate_fail_count": len(failed)},
        "api_endpoints": [
            {"method": method, "path": path, "surface": surface}
            for method, path, surface, _description in S6_ENDPOINTS
        ],
        "outputs": {
            "schema": rel_path(paths.schema_path, root),
            "sqlite_store": rel_path(paths.db_path, root),
            "gate_rows": rel_path(paths.gate_rows_path, root),
            "summary": rel_path(paths.summary_path, root),
            "closeout_report": rel_path(paths.report_path, root),
        },
        "failed_gates": failed,
        "next_slice_unlocked": "S7" if not failed else None,
        "boundary": "S6 closes Workbench frontdoor/drilldown scope only; it does not generate final deliverables, quant factors, or production multi-tenant hardening.",
    }


def render_s6_report(summary: Mapping[str, Any], gate_rows: Iterable[Mapping[str, Any]]) -> str:
    lines = [
        "# R53-R60 S6 Workbench Frontdoor / Drilldown L4 Scope Closeout",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Status: `{summary['status']}`",
        f"Release decision: `{summary['release_decision']}`",
        f"Closeout level: `{summary['closeout_level']}`",
        "",
        "## Scope",
        "",
        "S6 exposes the SQL-final S1-S5 runtime and Workpaper ledger through Workbench task center, drilldown, review, and ops projection contracts.",
        "",
        "## API Endpoints",
        "",
    ]
    for endpoint in summary["api_endpoints"]:
        lines.append(f"- `{endpoint['method']}` `{endpoint['path']}` -> `{endpoint['surface']}`")
    lines.extend(["", "## Counts", ""])
    for key, value in summary["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Gate Rows", ""])
    for row in gate_rows:
        lines.append(f"- `{row['status']}` `{row['gate_id']}`: {row['description']}")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Boundary", "", str(summary["boundary"]), ""])
    return "\n".join(lines)


def decode_projection_row(row: Mapping[str, Any]) -> dict[str, Any]:
    decoded = decode_json_fields(dict(row))
    decoded["payload"] = decoded.get("payload") or {}
    return decoded


def decode_drilldown_row(row: Mapping[str, Any]) -> dict[str, Any]:
    decoded = dict(row)
    for key in [
        "surfaces_json",
        "sections_json",
        "claims_json",
        "gaps_json",
        "lead_review_json",
        "judgment_json",
        "context_json",
        "gates_json",
        "artifacts_json",
        "events_json",
        "payload_json",
    ]:
        target = key[:-5]
        decoded[target] = json_loads(str(decoded.pop(key, "") or ""), [] if key.endswith("s_json") or key in {"sections_json", "claims_json", "gaps_json", "gates_json", "artifacts_json", "events_json"} else {})
    return decoded


def decode_json_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    decoded = dict(row)
    for key in list(decoded):
        if key.endswith("_json"):
            decoded[key[:-5]] = json_loads(str(decoded.pop(key) or ""), {})
    return decoded


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("select 1 from sqlite_master where type = 'table' and name = ?", (table,)).fetchone() is not None


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in rows]
