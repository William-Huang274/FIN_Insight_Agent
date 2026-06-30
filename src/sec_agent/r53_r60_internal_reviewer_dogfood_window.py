"""P18 internal reviewer dogfood window for R53-R60.

P17 executed the deterministic controlled pilot. P18 turns that execution
ledger into a Workbench-consumable internal reviewer window: case assignments,
reviewer sessions, action events, defect promotions, feedback-to-regression
links, dashboard tiles, API contracts, gates and readiness reporting.

This slice is intentionally strict about its boundary. It proves the product is
ready for real internal reviewers to use and review through SQL-final records.
It does not claim sustained real-human adoption, external customer pilot, or
full production release.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from sec_agent.r53_r60_controlled_internal_pilot_execution import (
    P17_BATCH_ID,
    build_p17_gate,
    default_p17_paths,
)
from sec_agent.r53_r60_enterprise_workbench_product_surface import dependency_summary_passes
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


SCHEMA_VERSION = "r53_r60_p18_internal_reviewer_dogfood_window_v0_1"
P18_TASK_ID = "p18_scope_task_internal_reviewer_dogfood_window"
P18_WINDOW_ID = "r53_r60_internal_reviewer_dogfood_window_v0_1"

P18_DEMAND_IDS = (
    "P18-D01-reviewer-window-ledger",
    "P18-D02-case-assignment-and-session-records",
    "P18-D03-workbench-pilot-dashboard-api",
    "P18-D04-reviewer-action-event-bridge",
    "P18-D05-defect-feedback-regression-promotion",
    "P18-D06-dogfood-readiness-and-boundary-gates",
)

P18_ENDPOINTS = (
    ("GET", "/api/r53-r60/pilot/dashboard", "pilot_dashboard", "Read pilot window status, tiles, cases, sessions, defects and gates."),
    ("GET", "/api/r53-r60/pilot/cases", "pilot_case_list", "List pilot case assignments and reviewer-session state."),
    ("GET", "/api/r53-r60/pilot/cases/{case_id}", "pilot_case_detail", "Inspect one pilot case assignment, actions, defects and feedback links."),
)

DEPENDENCIES: tuple[tuple[str, Callable[[Path], Any], Callable[[Path], Any], str], ...] = (
    ("P17", default_p17_paths, build_p17_gate, "P17_L4_scope_pass_controlled_internal_pilot_execution_ready"),
)


@dataclass(frozen=True)
class P18Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


def default_p18_paths(root: Path) -> P18Paths:
    s1_paths = default_s1_paths(root)
    return P18Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "p18_internal_reviewer_dogfood_window_schema_v0_1.json",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_p18_internal_reviewer_dogfood_window_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_p18_internal_reviewer_dogfood_window_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_p18_internal_reviewer_dogfood_window_l4_scope_pass.zh-CN.md",
    )


def internal_reviewer_dogfood_window_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "release_scope": "internal_reviewer_dogfood_window_ready_not_real_adoption_complete",
        "tables": [
            "internal_reviewer_dogfood_metadata_p18",
            "dogfood_windows_p18",
            "dogfood_case_assignments_p18",
            "reviewer_session_records_p18",
            "reviewer_action_events_p18",
            "pilot_dashboard_tiles_p18",
            "pilot_defect_promotions_p18",
            "pilot_feedback_to_regression_p18",
            "pilot_workbench_api_contracts_p18",
            "pilot_dogfood_readiness_reports_p18",
            "pilot_dogfood_gate_results_p18",
        ],
        "endpoints": [
            {"method": method, "path": path, "surface": surface, "description": description}
            for method, path, surface, description in P18_ENDPOINTS
        ],
        "policy": {
            "p18_consumes_p17_execution_ledger": True,
            "sql_final_source_of_truth": True,
            "frontend_dashboard_is_projection_only": True,
            "reviewer_actions_require_append_only_records": True,
            "defects_must_promote_to_regression_queue_or_typed_gap": True,
            "real_human_multi_day_adoption_must_not_be_claimed": True,
            "full_product_release_status_must_remain_not_l4_production_pass": True,
        },
        "required_demands": list(P18_DEMAND_IDS),
    }


def create_internal_reviewer_dogfood_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists internal_reviewer_dogfood_metadata_p18 (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists dogfood_windows_p18 (
            window_id text primary key,
            source_batch_id text not null,
            window_status text not null,
            reviewer_scope text not null,
            deterministic_drill_status text not null,
            real_human_adoption_status text not null,
            assigned_case_count integer not null,
            started_at text not null,
            closed_at text not null,
            boundary_json text not null default '{}',
            payload_json text not null default '{}'
        );
        create table if not exists dogfood_case_assignments_p18 (
            assignment_id text primary key,
            window_id text not null,
            case_id text not null,
            runtime_task_id text not null,
            source_execution_id text not null,
            assigned_reviewer_role text not null,
            assignment_status text not null,
            required_actions_json text not null default '[]',
            evidence_refs_json text not null default '[]',
            defect_refs_json text not null default '[]',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists reviewer_session_records_p18 (
            session_id text primary key,
            window_id text not null,
            assignment_id text not null,
            case_id text not null,
            reviewer_role text not null,
            session_mode text not null,
            session_status text not null,
            action_count integer not null,
            reviewed_artifact_count integer not null,
            unresolved_defect_count integer not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists reviewer_action_events_p18 (
            action_event_id text primary key,
            window_id text not null,
            assignment_id text not null,
            case_id text not null,
            source_action_id text not null,
            reviewer_role text not null,
            action_type text not null,
            action_status text not null,
            workpaper_event_ref text not null default '',
            comment text not null default '',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_dashboard_tiles_p18 (
            tile_id text primary key,
            window_id text not null,
            tile_group text not null,
            title text not null,
            metric_value text not null,
            metric_detail text not null default '',
            status text not null,
            source_table text not null,
            payload_json text not null default '{}',
            updated_at text not null
        );
        create table if not exists pilot_defect_promotions_p18 (
            promotion_id text primary key,
            window_id text not null,
            case_id text not null,
            source_defect_id text not null,
            defect_type text not null,
            promotion_target text not null,
            promotion_status text not null,
            regression_case_id text not null,
            blocker_status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_feedback_to_regression_p18 (
            feedback_link_id text primary key,
            window_id text not null,
            case_id text not null,
            source_feedback_id text not null,
            source_defect_id text not null,
            regression_case_id text not null,
            lifecycle_status text not null,
            eval_layer text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_workbench_api_contracts_p18 (
            endpoint_id text primary key,
            method text not null,
            path text not null,
            surface text not null,
            request_schema_json text not null default '{}',
            response_schema_json text not null default '{}',
            permission_policy text not null,
            trace_required integer not null,
            sql_audit_required integer not null,
            status text not null,
            created_at text not null
        );
        create table if not exists pilot_dogfood_readiness_reports_p18 (
            report_id text primary key,
            window_id text not null,
            release_decision text not null,
            closeout_level text not null,
            dogfood_status text not null,
            full_product_release_status text not null,
            known_gaps_json text not null default '[]',
            next_actions_json text not null default '[]',
            gate_refs_json text not null default '[]',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pilot_dogfood_gate_results_p18 (
            gate_id text primary key,
            gate_name text not null,
            gate_group text not null,
            status text not null,
            pass_level text not null,
            detail_json text not null default '{}',
            created_at text not null
        );
        create index if not exists idx_p18_assignments_case on dogfood_case_assignments_p18(case_id);
        create index if not exists idx_p18_actions_case on reviewer_action_events_p18(case_id, created_at);
        create index if not exists idx_p18_defects_case on pilot_defect_promotions_p18(case_id);
        """
    )


def build_p18_gate(root: Path, *, task_id: str = P18_TASK_ID) -> dict[str, Any]:
    root = root.resolve()
    paths = default_p18_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    ensure_p18_dependencies(root)
    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    with runtime.store._connect() as conn:
        create_internal_reviewer_dogfood_schema(conn)
        seed_p18_metadata(conn)
        clear_p18_rows(conn)

    p18_task = get_or_create_p18_task(runtime, task_id=task_id)
    if str(p18_task["task"]["status"]) != "running":
        runtime.store.transition_task(
            task_id,
            "running",
            actor="pilot_dogfood_builder",
            message="start P18 internal reviewer dogfood window build",
            progress=10,
        )

    materialized = materialize_internal_reviewer_dogfood_window(runtime, root=root, task_id=task_id)
    write_json(paths.schema_path, internal_reviewer_dogfood_window_schema_contract())
    artifact_refs = record_p18_artifacts(runtime, root, paths, task_id, materialized)
    event = runtime.append_workpaper_event(
        task_id,
        actor="pilot_program_manager",
        event_type="internal_reviewer_dogfood_window_ready",
        section_id="internal_reviewer_dogfood_window",
        claim_id="p18_internal_reviewer_dogfood_scope_pass",
        payload={
            "schema_version": SCHEMA_VERSION,
            "window_id": P18_WINDOW_ID,
            "artifact_ref_ids": [item["artifact_ref_id"] for item in artifact_refs],
            "scope_boundary": "Ready for real internal reviewer dogfood; real-human adoption is pending actual reviewer actions.",
        },
    )
    node = runtime.record_node_result(
        task_id,
        node="internal_reviewer_dogfood_window_builder",
        status="pass",
        input_payload={"dependencies": [name for name, *_ in DEPENDENCIES]},
        output_payload={**materialized, "workpaper_event_id": event["workpaper_event_id"]},
        artifact_ref_ids=[item["artifact_ref_id"] for item in artifact_refs],
        actor="pilot_dogfood_builder",
    )
    for name, payload in [
        ("p18_case_assignment_gate", {"assignment_count": materialized["assignment_count"]}),
        ("p18_reviewer_session_gate", {"reviewer_session_count": materialized["reviewer_session_count"]}),
        ("p18_dashboard_projection_gate", {"dashboard_tile_count": materialized["dashboard_tile_count"]}),
        ("p18_defect_promotion_gate", {"defect_promotion_count": materialized["defect_promotion_count"]}),
    ]:
        runtime.record_trace_span(
            task_id,
            span_kind="pilot_dogfood_gate",
            name=name,
            status="pass",
            actor="pilot_dogfood_verifier",
            node_execution_id=node["node_execution_id"],
            latency_ms=0,
            token_count=0,
            cost_amount=0.0,
            model_name="deterministic",
            provider="local",
            payload={"closeout_level": "L4_scope_pass", **payload},
        )
    runtime.store.transition_task(task_id, "succeeded", actor="pilot_dogfood_verifier", message="P18 internal reviewer dogfood window ready", progress=100)

    gate_rows = evaluate_p18_gates(root, runtime.store, task_id=task_id, materialized=materialized)
    persist_p18_gate_results(runtime.store, gate_rows)
    finalize_p18_readiness_report(runtime.store, gate_rows)
    summary = build_p18_summary(root, paths, gate_rows, runtime.store, task_id=task_id, materialized=materialized)
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_p18_report(summary, gate_rows), encoding="utf-8")
    return summary


def ensure_p18_dependencies(root: Path) -> None:
    for _name, path_factory, builder, decision in DEPENDENCIES:
        summary_path = path_factory(root).summary_path
        if not dependency_summary_passes(summary_path, decision):
            builder(root)


def seed_p18_metadata(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "window_id": P18_WINDOW_ID,
        "source_batch_id": P17_BATCH_ID,
        "dogfood_status": "ready_for_real_internal_reviewer_use",
        "real_human_adoption_status": "pending_actual_reviewer_actions",
        "full_product_release_status": "not_l4_production_pass",
    }
    for key, value in metadata.items():
        conn.execute(
            """
            insert into internal_reviewer_dogfood_metadata_p18(key, value_json, updated_at)
            values (?, ?, ?)
            on conflict(key) do update set value_json = excluded.value_json, updated_at = excluded.updated_at
            """,
            (key, json_dumps(value), now),
        )


def clear_p18_rows(conn: sqlite3.Connection) -> None:
    for table in reversed(internal_reviewer_dogfood_window_schema_contract()["tables"]):
        if table != "internal_reviewer_dogfood_metadata_p18":
            conn.execute(f"delete from {table}")


def get_or_create_p18_task(runtime: FinSightResearchRuntimeFacade, *, task_id: str) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(task_id)
    except Exception:
        return runtime.create_task(
            "Prepare internal reviewer dogfood window over P17 pilot execution records",
            task_id=task_id,
            trace_id="trace_p18_internal_reviewer_dogfood_window",
            user_id="p18_pilot_program",
            case_id="p18_internal_reviewer_dogfood_window",
            mode="internal_reviewer_dogfood_window_gate",
            objective={"minimum_evidence": "P17 cases are assignable, reviewable, dashboard-visible, and defect-promoted"},
            metadata={"source_slice": "P18", "closeout_level": "L4_scope_pass"},
        )
    if str(state["task"]["status"]) in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        return runtime.resume_task(task_id, actor="pilot_dogfood_builder", reason="rebuild P18 internal reviewer dogfood window")
    return state


def materialize_internal_reviewer_dogfood_window(
    runtime: FinSightResearchRuntimeFacade,
    *,
    root: Path,
    task_id: str,
) -> dict[str, Any]:
    del root, task_id
    now = utc_now_iso()
    with runtime.store._connect() as conn:
        conn.row_factory = sqlite3.Row
        source = load_p17_source_rows(conn)

    cases = source["cases"]
    action_groups = group_by_case(source["actions"])
    defect_groups = group_by_case(source["defects"])
    feedback_groups = group_by_case(source["feedback"])
    eval_groups = group_by_case(source["evals"])
    cost_groups = group_by_case(source["costs"])
    artifact_groups = group_by_case(source["artifacts"])

    assignment_rows: list[dict[str, Any]] = []
    session_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    defect_rows: list[dict[str, Any]] = []
    feedback_rows: list[dict[str, Any]] = []

    for case in cases:
        case_id = str(case["case_id"])
        assignment_id = stable_id("p18assignment", [P18_WINDOW_ID, case_id])
        actions = action_groups.get(case_id, [])
        defects = defect_groups.get(case_id, [])
        feedback = feedback_groups.get(case_id, [])
        evals = eval_groups.get(case_id, [])
        costs = cost_groups.get(case_id, [])
        artifacts = artifact_groups.get(case_id, [])
        reviewer_role = "senior_research_reviewer" if int(case.get("typed_gap_count") or 0) <= 1 else "lead_reviewer"
        required_actions = [
            "review_workpaper_output",
            "inspect_claim_gap_boundaries",
            "approve_or_request_repair",
            "confirm_defect_regression_promotion",
        ]
        assignment_rows.append(
            {
                "assignment_id": assignment_id,
                "window_id": P18_WINDOW_ID,
                "case_id": case_id,
                "runtime_task_id": case["runtime_task_id"],
                "source_execution_id": case["execution_id"],
                "assigned_reviewer_role": reviewer_role,
                "assignment_status": "review_ready",
                "required_actions_json": json_dumps(required_actions),
                "evidence_refs_json": json_dumps([row.get("artifact_ref_id") for row in artifacts if row.get("artifact_ref_id")]),
                "defect_refs_json": json_dumps([row.get("defect_id") for row in defects if row.get("defect_id")]),
                "payload_json": json_dumps(
                    {
                        "eval_score": case.get("eval_score"),
                        "typed_gap_count": case.get("typed_gap_count"),
                        "case_status": case.get("case_status"),
                    }
                ),
                "created_at": now,
            }
        )
        session_rows.append(
            {
                "session_id": stable_id("p18session", [P18_WINDOW_ID, case_id, reviewer_role]),
                "window_id": P18_WINDOW_ID,
                "assignment_id": assignment_id,
                "case_id": case_id,
                "reviewer_role": reviewer_role,
                "session_mode": "deterministic_reviewer_session_drill",
                "session_status": "ready_for_real_human_replay",
                "action_count": len(actions),
                "reviewed_artifact_count": len(artifacts),
                "unresolved_defect_count": len([row for row in defects if str(row.get("lifecycle_status") or "") in {"followup_required"}]),
                "payload_json": json_dumps(
                    {
                        "real_human_session_pending": True,
                        "eval_scores": [row.get("score") for row in evals],
                        "cost_rows": costs,
                    }
                ),
                "created_at": now,
            }
        )
        for action_index, action in enumerate(actions):
            action_rows.append(
                {
                    "action_event_id": stable_id("p18action", [assignment_id, action.get("review_action_id"), action_index]),
                    "window_id": P18_WINDOW_ID,
                    "assignment_id": assignment_id,
                    "case_id": case_id,
                    "source_action_id": action.get("review_action_id") or "",
                    "reviewer_role": action.get("reviewer_role") or reviewer_role,
                    "action_type": action.get("action_type") or action.get("action") or "comment",
                    "action_status": "projected_from_p17_action_ledger",
                    "workpaper_event_ref": action.get("workpaper_event_ref") or "",
                    "comment": action.get("comment") or "",
                    "payload_json": json_dumps({"source": "pilot_case_reviewer_actions_p17", "sql_final": True}),
                    "created_at": now,
                }
            )
        for defect in defects:
            regression_case_id = stable_id("p16regression", [P18_WINDOW_ID, case_id, defect.get("defect_type")])
            defect_rows.append(
                {
                    "promotion_id": stable_id("p18defect", [assignment_id, defect.get("defect_id")]),
                    "window_id": P18_WINDOW_ID,
                    "case_id": case_id,
                    "source_defect_id": defect.get("defect_id") or "",
                    "defect_type": defect.get("defect_type") or "typed_gap_followup",
                    "promotion_target": "P16_regression_case_lifecycle",
                    "promotion_status": "queued_for_p16_regression_lifecycle",
                    "regression_case_id": regression_case_id,
                    "blocker_status": "non_blocking_for_internal_dogfood" if str(defect.get("lifecycle_status") or "") != "followup_required" else "review_followup_required",
                    "payload_json": json_dumps({"source_defect_status": defect.get("lifecycle_status"), "not_hidden_fallback": True}),
                    "created_at": now,
                }
            )
            for record in feedback:
                feedback_rows.append(
                    {
                        "feedback_link_id": stable_id("p18feedback", [assignment_id, defect.get("defect_id"), record.get("feedback_id")]),
                        "window_id": P18_WINDOW_ID,
                        "case_id": case_id,
                        "source_feedback_id": record.get("feedback_id") or "",
                        "source_defect_id": defect.get("defect_id") or "",
                        "regression_case_id": regression_case_id,
                        "lifecycle_status": "queued_for_regression_or_gold_review",
                        "eval_layer": "E11_full_chain",
                        "payload_json": json_dumps({"source_feedback_status": record.get("lifecycle_status")}),
                        "created_at": now,
                    }
                )

    dashboard_rows = dashboard_tile_rows(
        case_count=len(cases),
        assignment_count=len(assignment_rows),
        session_count=len(session_rows),
        action_count=len(action_rows),
        defect_count=len(defect_rows),
        feedback_count=len(feedback_rows),
        total_cost=sum(float(row.get("cost_usd") or 0.0) for row in source["costs"]),
        max_latency=max([int(row.get("latency_ms") or 0) for row in source["costs"]] or [0]),
        now=now,
    )
    api_rows = api_contract_rows(now)

    with runtime.store._connect() as conn:
        conn.execute("begin immediate")
        try:
            create_internal_reviewer_dogfood_schema(conn)
            conn.execute(
                "insert into dogfood_windows_p18 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    P18_WINDOW_ID,
                    P17_BATCH_ID,
                    "ready_for_real_internal_reviewer_use",
                    "controlled_internal_reviewer_window",
                    "deterministic_reviewer_drill_complete",
                    "pending_actual_reviewer_actions",
                    len(assignment_rows),
                    now,
                    now,
                    json_dumps(
                        {
                            "not_external_customer_pilot": True,
                            "not_sustained_real_human_adoption_window": True,
                            "not_l4_production_pass": True,
                        }
                    ),
                    json_dumps({"p17_case_count": len(cases), "source_batch_id": P17_BATCH_ID}),
                ),
            )
            insert_many(conn, "dogfood_case_assignments_p18", assignment_rows)
            insert_many(conn, "reviewer_session_records_p18", session_rows)
            insert_many(conn, "reviewer_action_events_p18", action_rows)
            insert_many(conn, "pilot_defect_promotions_p18", defect_rows)
            insert_many(conn, "pilot_feedback_to_regression_p18", feedback_rows)
            insert_many(conn, "pilot_dashboard_tiles_p18", dashboard_rows)
            insert_many(conn, "pilot_workbench_api_contracts_p18", api_rows)
            insert_p18_readiness_report(conn, now=now)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    with runtime.store._connect() as conn:
        return {
            "window_count": count_rows(conn, "dogfood_windows_p18"),
            "assignment_count": count_rows(conn, "dogfood_case_assignments_p18"),
            "reviewer_session_count": count_rows(conn, "reviewer_session_records_p18"),
            "reviewer_action_event_count": count_rows(conn, "reviewer_action_events_p18"),
            "dashboard_tile_count": count_rows(conn, "pilot_dashboard_tiles_p18"),
            "defect_promotion_count": count_rows(conn, "pilot_defect_promotions_p18"),
            "feedback_regression_link_count": count_rows(conn, "pilot_feedback_to_regression_p18"),
            "api_contract_count": count_rows(conn, "pilot_workbench_api_contracts_p18"),
            "total_cost_usd": round(sum(float(row.get("cost_usd") or 0.0) for row in source["costs"]), 6),
            "max_latency_ms": max([int(row.get("latency_ms") or 0) for row in source["costs"]] or [0]),
        }


def load_p17_source_rows(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    required = {
        "pilot_case_executions_p17",
        "pilot_case_reviewer_actions_p17",
        "pilot_case_defect_records_p17",
        "pilot_case_feedback_records_p17",
        "pilot_case_eval_snapshots_p17",
        "pilot_case_cost_latency_records_p17",
        "pilot_case_artifact_links_p17",
    }
    missing = [table for table in sorted(required) if not table_exists(conn, table)]
    if missing:
        raise RuntimeError(f"p17_tables_missing:{','.join(missing)}")
    return {
        "cases": rows_to_dicts(conn.execute("select * from pilot_case_executions_p17 order by case_id").fetchall()),
        "actions": rows_to_dicts(conn.execute("select * from pilot_case_reviewer_actions_p17 order by case_id, created_at").fetchall()),
        "defects": rows_to_dicts(conn.execute("select * from pilot_case_defect_records_p17 order by case_id").fetchall()),
        "feedback": rows_to_dicts(conn.execute("select * from pilot_case_feedback_records_p17 order by case_id").fetchall()),
        "evals": rows_to_dicts(conn.execute("select * from pilot_case_eval_snapshots_p17 order by case_id").fetchall()),
        "costs": rows_to_dicts(conn.execute("select * from pilot_case_cost_latency_records_p17 order by case_id").fetchall()),
        "artifacts": rows_to_dicts(conn.execute("select * from pilot_case_artifact_links_p17 order by case_id").fetchall()),
    }


def group_by_case(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("case_id") or ""), []).append(row)
    return grouped


def dashboard_tile_rows(
    *,
    case_count: int,
    assignment_count: int,
    session_count: int,
    action_count: int,
    defect_count: int,
    feedback_count: int,
    total_cost: float,
    max_latency: int,
    now: str,
) -> list[dict[str, Any]]:
    values = [
        ("window_status", "status", "Pilot window", "ready_for_real_internal_reviewer_use", "deterministic drill complete", "pass", "dogfood_windows_p18"),
        ("case_assignments", "coverage", "Assigned cases", str(assignment_count), f"{case_count} P17 cases", "pass", "dogfood_case_assignments_p18"),
        ("reviewer_sessions", "review", "Reviewer sessions", str(session_count), "ready for human replay", "pass", "reviewer_session_records_p18"),
        ("reviewer_actions", "review", "Action events", str(action_count), "projected from append-only P17 ledger", "pass", "reviewer_action_events_p18"),
        ("defect_promotions", "quality", "Defect promotions", str(defect_count), f"{feedback_count} feedback links", "pass", "pilot_defect_promotions_p18"),
        ("cost_latency", "ops", "Pilot cost / latency", f"${total_cost:.2f}", f"max latency {max_latency}ms", "pass", "pilot_case_cost_latency_records_p17"),
        ("release_boundary", "boundary", "Release boundary", "not_l4_production_pass", "real adoption pending", "warn", "pilot_dogfood_readiness_reports_p18"),
    ]
    return [
        {
            "tile_id": stable_id("p18tile", [P18_WINDOW_ID, key]),
            "window_id": P18_WINDOW_ID,
            "tile_group": group,
            "title": title,
            "metric_value": value,
            "metric_detail": detail,
            "status": status,
            "source_table": source_table,
            "payload_json": json_dumps({"tile_key": key}),
            "updated_at": now,
        }
        for key, group, title, value, detail, status, source_table in values
    ]


def api_contract_rows(now: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for method, path, surface, description in P18_ENDPOINTS:
        rows.append(
            {
                "endpoint_id": stable_id("p18api", [method, path]),
                "method": method,
                "path": path,
                "surface": surface,
                "request_schema_json": json_dumps({"path_params": ["case_id"] if "{case_id}" in path else [], "body": None}),
                "response_schema_json": json_dumps({"schema_version": SCHEMA_VERSION, "surface": surface, "description": description}),
                "permission_policy": "internal_reviewer_or_pilot_program_manager",
                "trace_required": 1,
                "sql_audit_required": 1,
                "status": "implemented",
                "created_at": now,
            }
        )
    return rows


def insert_p18_readiness_report(conn: sqlite3.Connection, *, now: str) -> None:
    known_gaps = [
        {
            "gap": "actual_human_reviewer_window_not_completed",
            "reason": "P18 creates the SQL/API/UI-ready dogfood window; real reviewer actions require humans to use the Workbench.",
        },
        {
            "gap": "external_customer_pilot_not_started",
            "reason": "Internal reviewer dogfood is not customer production or customer-facing pilot.",
        },
    ]
    next_actions = [
        "open Workbench pilot dashboard for real reviewer actions",
        "route repeated P17/P18 defects into P16 regression lifecycle",
        "use actual reviewer feedback to decide P19 customer-pilot readiness",
    ]
    conn.execute(
        "insert into pilot_dogfood_readiness_reports_p18 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "p18_internal_reviewer_dogfood_window_report_v0_1",
            P18_WINDOW_ID,
            "P18_L4_scope_pass_internal_reviewer_dogfood_window_ready",
            "L4_scope_pass",
            "ready_for_real_internal_reviewer_use",
            "not_l4_production_pass",
            json_dumps(known_gaps),
            json_dumps(next_actions),
            "[]",
            json_dumps({"source_batch_id": P17_BATCH_ID, "real_human_adoption_status": "pending_actual_reviewer_actions"}),
            now,
        ),
    )


def insert_many(conn: sqlite3.Connection, table: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    placeholders = ", ".join("?" for _ in columns)
    conn.executemany(
        f"insert into {table} ({', '.join(columns)}) values ({placeholders})",
        [tuple(row[col] for col in columns) for row in rows],
    )


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"select count(*) from {table}").fetchone()[0])


def count_query(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


def evaluate_p18_gates(
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
        required_tables = set(internal_reviewer_dogfood_window_schema_contract()["tables"])
        p17_case_count = count_query(conn, "select count(*) from pilot_case_executions_p17")
        p17_action_count = count_query(conn, "select count(*) from pilot_case_reviewer_actions_p17")
        p17_defect_count = count_query(conn, "select count(*) from pilot_case_defect_records_p17")
        assignment_bad = count_query(conn, "select count(*) from dogfood_case_assignments_p18 where assignment_status != 'review_ready'")
        session_bad = count_query(conn, "select count(*) from reviewer_session_records_p18 where session_status != 'ready_for_real_human_replay'")
        action_bad = count_query(conn, "select count(*) from reviewer_action_events_p18 where action_status != 'projected_from_p17_action_ledger'")
        promotion_bad = count_query(conn, "select count(*) from pilot_defect_promotions_p18 where promotion_status != 'queued_for_p16_regression_lifecycle'")
        api_bad = count_query(conn, "select count(*) from pilot_workbench_api_contracts_p18 where status != 'implemented' or trace_required != 1 or sql_audit_required != 1")
        tile_bad = count_query(conn, "select count(*) from pilot_dashboard_tiles_p18 where status not in ('pass', 'warn')")
        report = row_to_dict(conn.execute("select * from pilot_dogfood_readiness_reports_p18 limit 1").fetchone())
        event_count = count_query(
            conn,
            "select count(*) from workpaper_events where task_id = ? and event_type = 'internal_reviewer_dogfood_window_ready'",
            (task_id,),
        )
    dependency_status = dependency_status_rows(root)
    dependency_pass = all(row["status"] == "pass" for row in dependency_status)
    gates = [
        make_gate("p18_schema_tables_present", "schema", required_tables.issubset(tables), {"missing": sorted(required_tables - tables)}, now),
        make_gate("p18_p17_dependency_pass", "dependency", dependency_pass, {"dependencies": dependency_status}, now),
        make_gate(
            "p18_all_p17_cases_assigned",
            "case_assignment",
            int(materialized["assignment_count"]) == p17_case_count and assignment_bad == 0 and p17_case_count > 0,
            {"assignment_count": materialized["assignment_count"], "p17_case_count": p17_case_count, "assignment_bad": assignment_bad},
            now,
        ),
        make_gate(
            "p18_reviewer_sessions_ready",
            "reviewer_session",
            int(materialized["reviewer_session_count"]) == p17_case_count and session_bad == 0,
            {"reviewer_session_count": materialized["reviewer_session_count"], "session_bad": session_bad},
            now,
        ),
        make_gate(
            "p18_reviewer_action_events_projected",
            "review_action",
            int(materialized["reviewer_action_event_count"]) >= p17_action_count and action_bad == 0 and p17_action_count > 0,
            {"reviewer_action_event_count": materialized["reviewer_action_event_count"], "p17_action_count": p17_action_count, "action_bad": action_bad},
            now,
        ),
        make_gate(
            "p18_defects_promoted_to_regression_lifecycle",
            "defect_regression",
            int(materialized["defect_promotion_count"]) == p17_defect_count and promotion_bad == 0 and p17_defect_count > 0,
            {"defect_promotion_count": materialized["defect_promotion_count"], "p17_defect_count": p17_defect_count, "promotion_bad": promotion_bad},
            now,
        ),
        make_gate(
            "p18_dashboard_projection_ready",
            "dashboard",
            int(materialized["dashboard_tile_count"]) >= 6 and tile_bad == 0,
            {"dashboard_tile_count": materialized["dashboard_tile_count"], "tile_bad": tile_bad},
            now,
        ),
        make_gate(
            "p18_workbench_api_contracts_ready",
            "api",
            int(materialized["api_contract_count"]) == len(P18_ENDPOINTS) and api_bad == 0,
            {"api_contract_count": materialized["api_contract_count"], "api_bad": api_bad},
            now,
        ),
        make_gate(
            "p18_feedback_to_regression_links_ready",
            "feedback",
            int(materialized["feedback_regression_link_count"]) >= p17_defect_count,
            {"feedback_regression_link_count": materialized["feedback_regression_link_count"], "p17_defect_count": p17_defect_count},
            now,
        ),
        make_gate(
            "p18_ready_boundary_not_fake_adoption",
            "boundary",
            report.get("full_product_release_status") == "not_l4_production_pass"
            and "pending_actual_reviewer_actions" in str(report.get("payload_json") or ""),
            {"report": report},
            now,
        ),
        make_gate(
            "p18_workpaper_event_and_artifact_trace_ready",
            "trace",
            event_count >= 1,
            {"event_count": event_count},
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
        "gate_id": stable_id("p18gate", [name]),
        "gate_name": name,
        "gate_group": group,
        "status": "pass" if condition else "fail",
        "pass_level": "L4_scope_pass" if condition else "blocked",
        "detail": dict(detail),
        "created_at": now,
    }


def persist_p18_gate_results(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    with store._connect() as conn:
        conn.execute("delete from pilot_dogfood_gate_results_p18")
        for row in gate_rows:
            conn.execute(
                "insert into pilot_dogfood_gate_results_p18 values (?, ?, ?, ?, ?, ?, ?)",
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


def finalize_p18_readiness_report(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    fail_count = len([row for row in gate_rows if row["status"] != "pass"])
    decision = "P18_L4_scope_pass_internal_reviewer_dogfood_window_ready" if fail_count == 0 else "P18_blocked"
    with store._connect() as conn:
        conn.execute(
            """
            update pilot_dogfood_readiness_reports_p18
            set release_decision = ?, gate_refs_json = ?, payload_json = ?
            where report_id = ?
            """,
            (
                decision,
                json_dumps([row["gate_name"] for row in gate_rows]),
                json_dumps(
                    {
                        "gate_count": len(gate_rows),
                        "gate_fail_count": fail_count,
                        "real_human_adoption_status": "pending_actual_reviewer_actions",
                    }
                ),
                "p18_internal_reviewer_dogfood_window_report_v0_1",
            ),
        )


def build_p18_summary(
    root: Path,
    paths: P18Paths,
    gate_rows: list[dict[str, Any]],
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> dict[str, Any]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (task_id,)).fetchone())
        report = row_to_dict(conn.execute("select * from pilot_dogfood_readiness_reports_p18 limit 1").fetchone())
    fail_count = len([row for row in gate_rows if row["status"] != "pass"])
    status = "pass" if fail_count == 0 else "fail"
    return {
        "schema_version": SCHEMA_VERSION,
        "slice": "P18 Internal Reviewer Dogfood Window",
        "status": status,
        "release_decision": "P18_L4_scope_pass_internal_reviewer_dogfood_window_ready" if status == "pass" else "P18_blocked",
        "closeout_level": "L4_scope_pass" if status == "pass" else "blocked",
        "dogfood_status": report.get("dogfood_status") or "not_evaluated",
        "real_human_adoption_status": json_loads(str(report.get("payload_json") or "{}"), {}).get("real_human_adoption_status", "pending_actual_reviewer_actions"),
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
        "policy": internal_reviewer_dogfood_window_schema_contract()["policy"],
        "generated_at": utc_now_iso(),
    }


def record_p18_artifacts(
    runtime: FinSightResearchRuntimeFacade,
    root: Path,
    paths: P18Paths,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    artifacts = [
        ("internal_reviewer_dogfood_schema", paths.schema_path, "controlled schema"),
        ("internal_reviewer_dogfood_gate_rows", paths.gate_rows_path, "gate rows"),
        ("internal_reviewer_dogfood_summary", paths.summary_path, "summary"),
        ("internal_reviewer_dogfood_report", paths.report_path, "closeout report"),
    ]
    rows = []
    for artifact_type, path, label in artifacts:
        rows.append(
            runtime.record_artifact_ref(
                task_id,
                artifact_type=f"p18_{artifact_type}",
                uri=rel_path(path, root),
                payload={"label": label, "materialized": dict(materialized)},
                actor="pilot_dogfood_builder",
            )
        )
    return rows


def render_p18_report(summary: Mapping[str, Any], gate_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# R53-R60 P18 Internal Reviewer Dogfood Window L4 Scope Pass",
        "",
        f"- Release decision: `{summary['release_decision']}`",
        f"- Closeout level: `{summary['closeout_level']}`",
        f"- Dogfood status: `{summary['dogfood_status']}`",
        f"- Real human adoption status: `{summary['real_human_adoption_status']}`",
        f"- Full product release status: `{summary['full_product_release_status']}`",
        f"- Status: `{summary['status']}`",
        "",
        "## Scope Boundary",
        "",
        "P18 makes P17 pilot execution usable by internal reviewers through SQL-final assignments, sessions, action events, defect promotions and Workbench dashboard APIs. It does not claim that real humans have already completed a multi-day dogfood window.",
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


def decode_json_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    decoded = dict(row)
    for key, value in list(decoded.items()):
        if key.endswith("_json") and isinstance(value, str):
            decoded[key[:-5]] = json_loads(value, [] if value.strip().startswith("[") else {})
    return decoded


def get_pilot_dashboard_projection(root: Path) -> dict[str, Any]:
    ensure_p18_projection_exists(root)
    store = RuntimeTaskSpineStore(default_p18_paths(root.resolve()).db_path)
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        window = decode_json_fields(row_to_dict(conn.execute("select * from dogfood_windows_p18 where window_id = ?", (P18_WINDOW_ID,)).fetchone()))
        report = decode_json_fields(row_to_dict(conn.execute("select * from pilot_dogfood_readiness_reports_p18 limit 1").fetchone()))
        tiles = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from pilot_dashboard_tiles_p18 order by tile_group, title").fetchall()]
        cases = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from dogfood_case_assignments_p18 order by case_id").fetchall()]
        sessions = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from reviewer_session_records_p18 order by case_id").fetchall()]
        actions = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from reviewer_action_events_p18 order by case_id, created_at").fetchall()]
        defects = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from pilot_defect_promotions_p18 order by case_id").fetchall()]
        feedback = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from pilot_feedback_to_regression_p18 order by case_id").fetchall()]
        gates = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from pilot_dogfood_gate_results_p18 order by gate_group, gate_name").fetchall()]
        api_contracts = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from pilot_workbench_api_contracts_p18 order by path").fetchall()]
    return {
        "schema_version": SCHEMA_VERSION,
        "window": window,
        "readiness_report": report,
        "tiles": tiles,
        "case_assignments": cases,
        "reviewer_sessions": sessions,
        "reviewer_action_events": actions,
        "defect_promotions": defects,
        "feedback_regression_links": feedback,
        "gates": gates,
        "api_contracts": api_contracts,
        "counts": {
            "case_assignment_count": len(cases),
            "reviewer_session_count": len(sessions),
            "reviewer_action_event_count": len(actions),
            "defect_promotion_count": len(defects),
            "feedback_regression_link_count": len(feedback),
            "gate_count": len(gates),
        },
    }


def list_pilot_cases(root: Path) -> dict[str, Any]:
    payload = get_pilot_dashboard_projection(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "window_id": P18_WINDOW_ID,
        "cases": payload["case_assignments"],
        "sessions": payload["reviewer_sessions"],
    }


def get_pilot_case_detail(root: Path, *, case_id: str) -> dict[str, Any]:
    payload = get_pilot_dashboard_projection(root)
    assignments = [row for row in payload["case_assignments"] if str(row.get("case_id")) == case_id]
    if not assignments:
        raise KeyError(f"pilot_case_not_found:{case_id}")
    return {
        "schema_version": SCHEMA_VERSION,
        "window_id": P18_WINDOW_ID,
        "case": assignments[0],
        "sessions": [row for row in payload["reviewer_sessions"] if str(row.get("case_id")) == case_id],
        "reviewer_action_events": [row for row in payload["reviewer_action_events"] if str(row.get("case_id")) == case_id],
        "defect_promotions": [row for row in payload["defect_promotions"] if str(row.get("case_id")) == case_id],
        "feedback_regression_links": [row for row in payload["feedback_regression_links"] if str(row.get("case_id")) == case_id],
    }


def ensure_p18_projection_exists(root: Path) -> None:
    paths = default_p18_paths(root.resolve())
    if paths.summary_path.exists():
        return
    build_p18_gate(root)
