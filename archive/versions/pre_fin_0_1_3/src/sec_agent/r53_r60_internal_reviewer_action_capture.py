"""P19 internal reviewer action capture for R53-R60.

P18 makes the pilot dogfood window readable. P19 makes it actionable: internal
reviewers can submit case-scoped actions through Workbench, and repair-oriented
actions are written into the P16 failure/regression lifecycle. This slice proves
the action-capture contract and API path; it does not claim sustained multi-day
human adoption or external customer production use.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from sec_agent.r53_r60_enterprise_workbench_product_surface import dependency_summary_passes
from sec_agent.r53_r60_internal_reviewer_dogfood_window import (
    P18_WINDOW_ID,
    build_p18_gate,
    default_p18_paths,
    get_pilot_case_detail,
)
from sec_agent.r53_r60_quality_engineering_online_eval import (
    P16_DATASET_ID,
    P16_EVAL_RUN_ID,
    build_p16_gate,
    default_p16_paths,
)
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


SCHEMA_VERSION = "r53_r60_p19_internal_reviewer_action_capture_v0_1"
P19_TASK_ID = "p19_scope_task_internal_reviewer_action_capture"
P19_WINDOW_ID = "r53_r60_internal_reviewer_action_capture_window_v0_1"

P19_DEMAND_IDS = (
    "P19-D01-live-reviewer-action-contract",
    "P19-D02-workbench-post-action-api",
    "P19-D03-defect-triage-to-p16-regression",
    "P19-D04-gold-candidate-and-accepted-case-feedback",
    "P19-D05-action-dashboard-and-case-status",
    "P19-D06-boundary-gates-no-fake-adoption",
)

SUPPORTED_REVIEW_ACTIONS = {"approve", "request_repair", "return_to_specialist", "downgrade_claim", "comment"}
REPAIR_ACTIONS = {"request_repair", "return_to_specialist", "downgrade_claim"}

P19_ENDPOINTS = (
    ("GET", "/api/r53-r60/pilot/actions", "pilot_action_ledger", "List live pilot reviewer actions and case status."),
    (
        "GET",
        "/api/r53-r60/pilot/cases/{case_id}/actions",
        "pilot_case_action_ledger",
        "Read case-scoped live reviewer actions, feedback, defect triage and regression links.",
    ),
    (
        "POST",
        "/api/r53-r60/pilot/cases/{case_id}/review-actions",
        "pilot_case_review_action_capture",
        "Append one internal reviewer action and update feedback/defect/regression lifecycle rows.",
    ),
)

DEPENDENCIES: tuple[tuple[str, Callable[[Path], Any], Callable[[Path], Any], str], ...] = (
    ("P16", default_p16_paths, build_p16_gate, "P16_L4_scope_pass_quality_engineering_online_eval_ready"),
    ("P18", default_p18_paths, build_p18_gate, "P18_L4_scope_pass_internal_reviewer_dogfood_window_ready"),
)


@dataclass(frozen=True)
class P19Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


def default_p19_paths(root: Path) -> P19Paths:
    s1_paths = default_s1_paths(root)
    return P19Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "p19_internal_reviewer_action_capture_schema_v0_1.json",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_p19_internal_reviewer_action_capture_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_p19_internal_reviewer_action_capture_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_p19_internal_reviewer_action_capture_l4_scope_pass.zh-CN.md",
    )


def internal_reviewer_action_capture_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "release_scope": "internal_reviewer_action_capture_ready_not_multi_day_human_adoption_complete",
        "tables": [
            "internal_reviewer_action_capture_metadata_p19",
            "live_reviewer_action_windows_p19",
            "live_reviewer_actions_p19",
            "live_reviewer_feedback_records_p19",
            "live_defect_triage_records_p19",
            "live_regression_promotions_p19",
            "live_gold_candidate_promotions_p19",
            "live_pilot_case_status_p19",
            "live_reviewer_workbench_api_contracts_p19",
            "live_reviewer_action_reports_p19",
            "live_reviewer_gate_results_p19",
        ],
        "endpoints": [
            {"method": method, "path": path, "surface": surface, "description": description}
            for method, path, surface, description in P19_ENDPOINTS
        ],
        "policy": {
            "p19_consumes_p18_dogfood_window": True,
            "reviewer_actions_are_append_only": True,
            "repair_actions_must_create_p16_failure_and_regression_rows": True,
            "approval_actions_may_create_gold_candidate_not_final_gold_without_second_review": True,
            "dashboard_is_projection_not_source_of_truth": True,
            "deterministic_drill_is_not_real_multi_day_human_adoption": True,
            "full_product_release_status_must_remain_not_l4_production_pass": True,
        },
        "required_demands": list(P19_DEMAND_IDS),
    }


def create_internal_reviewer_action_capture_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists internal_reviewer_action_capture_metadata_p19 (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists live_reviewer_action_windows_p19 (
            window_id text primary key,
            source_window_id text not null,
            window_status text not null,
            action_capture_status text not null,
            deterministic_input_drill_status text not null,
            real_multi_day_human_adoption_status text not null,
            assigned_case_count integer not null,
            live_action_count integer not null,
            started_at text not null,
            closed_at text not null,
            boundary_json text not null default '{}',
            payload_json text not null default '{}'
        );
        create table if not exists live_reviewer_actions_p19 (
            live_action_id text primary key,
            window_id text not null,
            source_window_id text not null,
            case_id text not null,
            assignment_id text not null,
            runtime_task_id text not null,
            reviewer_role text not null,
            action_type text not null,
            action_source text not null,
            action_status text not null,
            comment text not null default '',
            workpaper_event_id text not null,
            p16_failure_event_id text not null default '',
            p16_regression_case_id text not null default '',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists live_reviewer_feedback_records_p19 (
            feedback_id text primary key,
            live_action_id text not null,
            case_id text not null,
            feedback_type text not null,
            feedback_status text not null,
            target_lifecycle text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists live_defect_triage_records_p19 (
            triage_id text primary key,
            live_action_id text not null,
            case_id text not null,
            source_p18_promotion_id text not null default '',
            triage_decision text not null,
            severity text not null,
            owner text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists live_regression_promotions_p19 (
            live_regression_id text primary key,
            live_action_id text not null,
            case_id text not null,
            p16_failure_event_id text not null,
            p16_regression_case_id text not null,
            promotion_status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists live_gold_candidate_promotions_p19 (
            gold_candidate_id text primary key,
            live_action_id text not null,
            case_id text not null,
            candidate_status text not null,
            second_review_required integer not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists live_pilot_case_status_p19 (
            case_id text primary key,
            window_id text not null,
            assignment_id text not null,
            live_action_count integer not null,
            last_action_type text not null,
            case_review_status text not null,
            unresolved_defect_count integer not null,
            p16_regression_count integer not null,
            gold_candidate_count integer not null,
            updated_at text not null,
            payload_json text not null default '{}'
        );
        create table if not exists live_reviewer_workbench_api_contracts_p19 (
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
        create table if not exists live_reviewer_action_reports_p19 (
            report_id text primary key,
            window_id text not null,
            release_decision text not null,
            closeout_level text not null,
            action_capture_status text not null,
            full_product_release_status text not null,
            known_gaps_json text not null default '[]',
            next_actions_json text not null default '[]',
            gate_refs_json text not null default '[]',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists live_reviewer_gate_results_p19 (
            gate_id text primary key,
            gate_name text not null,
            gate_group text not null,
            status text not null,
            pass_level text not null,
            detail_json text not null default '{}',
            created_at text not null
        );
        create index if not exists idx_p19_live_actions_case on live_reviewer_actions_p19(case_id);
        create index if not exists idx_p19_feedback_case on live_reviewer_feedback_records_p19(case_id);
        create index if not exists idx_p19_regressions_case on live_regression_promotions_p19(case_id);
        """
    )


def ensure_p19_dependencies(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, path_factory, builder, decision in DEPENDENCIES:
        summary_path = path_factory(root).summary_path
        payload = json_loads(summary_path.read_text(encoding="utf-8") if summary_path.exists() else "", {})
        if not dependency_summary_passes(summary_path, decision):
            payload = builder(root)
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


def reset_p19_tables(conn: sqlite3.Connection) -> None:
    if table_exists(conn, "regression_case_records_p16"):
        conn.execute("delete from regression_case_records_p16 where source_failure_event_id like 'p19_failure_%'")
    if table_exists(conn, "failure_events_p16"):
        conn.execute("delete from failure_events_p16 where source_ref like 'p19_live_action:%'")
    for table in reversed(internal_reviewer_action_capture_schema_contract()["tables"]):
        conn.execute(f"delete from {table}")


def build_p19_gate(root: Path, *, task_id: str = P19_TASK_ID) -> dict[str, Any]:
    root = root.resolve()
    paths = default_p19_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.summary_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    dependencies = ensure_p19_dependencies(root)
    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    p19_task = get_or_create_p19_task(runtime, task_id=task_id)
    if str(p19_task["task"]["status"]) != "running":
        runtime.store.transition_task(task_id, "running", actor="pilot_program_manager", message="start P19 reviewer action capture build", progress=10)

    with runtime.store._connect() as conn:
        create_internal_reviewer_action_capture_schema(conn)
        reset_p19_tables(conn)
        insert_p19_window_and_api_contracts(conn, root=root, dependencies=dependencies)

    seeded = seed_deterministic_reviewer_input_drill(root, runtime=runtime)
    gate_rows = evaluate_p19_gates(root, runtime.store, materialized=seeded)
    persist_p19_gate_results(runtime.store, gate_rows)
    finalize_p19_report(runtime.store, gate_rows)
    summary = build_p19_summary(root, paths, gate_rows, runtime.store, materialized=seeded, dependencies=dependencies)

    write_json(paths.schema_path, internal_reviewer_action_capture_schema_contract())
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_p19_report(summary, gate_rows), encoding="utf-8")
    record_p19_artifacts(runtime, root, paths, task_id, seeded)
    runtime.append_workpaper_event(
        task_id,
        actor="quality_lead",
        event_type="internal_reviewer_action_capture_ready",
        section_id="p19_closeout",
        claim_id="",
        payload={"summary": rel_path(paths.summary_path, root), "status": summary["status"]},
    )
    runtime.store.transition_task(
        task_id,
        "succeeded" if summary["status"] == "pass" else "failed",
        actor="quality_lead",
        message=summary["release_decision"],
        progress=100,
    )
    return summary


def get_or_create_p19_task(runtime: FinSightResearchRuntimeFacade, *, task_id: str) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(task_id)
    except Exception:
        return runtime.create_task(
            "Capture internal reviewer actions from the P18 pilot window and promote repair feedback into P16 regression lifecycle",
            task_id=task_id,
            trace_id="trace_p19_internal_reviewer_action_capture",
            user_id="p19_pilot_program",
            case_id="p19_internal_reviewer_action_capture",
            mode="internal_reviewer_action_capture_gate",
            objective={"minimum_evidence": "P18 pilot cases accept reviewer actions and repair feedback creates P16 regression rows"},
            metadata={"source_slice": "P19", "closeout_level": "L4_scope_pass", "demands": list(P19_DEMAND_IDS)},
        )
    if str(state["task"]["status"]) in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        return runtime.resume_task(task_id, actor="pilot_program_manager", reason="rebuild P19 internal reviewer action capture")
    return state


def insert_p19_window_and_api_contracts(conn: sqlite3.Connection, *, root: Path, dependencies: list[dict[str, Any]]) -> None:
    now = utc_now_iso()
    p18_cases = rows_to_dicts(conn.execute("select * from dogfood_case_assignments_p18 order by case_id").fetchall())
    conn.execute(
        "insert into live_reviewer_action_windows_p19 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            P19_WINDOW_ID,
            P18_WINDOW_ID,
            "ready_for_reviewer_action_capture",
            "api_sql_capture_ready",
            "pending_deterministic_input_drill",
            "pending_multi_day_human_dogfood",
            len(p18_cases),
            0,
            now,
            now,
            json_dumps(
                {
                    "not_external_customer_pilot": True,
                    "deterministic_seed_actions_do_not_count_as_multi_day_adoption": True,
                    "not_l4_production_pass": True,
                }
            ),
            json_dumps({"dependencies": dependencies}),
        ),
    )
    for method, path, surface, description in P19_ENDPOINTS:
        conn.execute(
            "insert into live_reviewer_workbench_api_contracts_p19 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p19api", [method, path]),
                method,
                path,
                surface,
                json_dumps(
                    {
                        "path_params": ["case_id"] if "{case_id}" in path else [],
                        "body": {
                            "action": sorted(SUPPORTED_REVIEW_ACTIONS),
                            "comment": "string",
                            "reviewer_role": "string",
                        }
                        if method == "POST"
                        else None,
                    }
                ),
                json_dumps({"schema_version": SCHEMA_VERSION, "surface": surface, "description": description}),
                "internal_reviewer_or_pilot_program_manager",
                1,
                1,
                "implemented",
                now,
            ),
        )
    conn.execute(
        "insert into live_reviewer_action_reports_p19 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "p19_internal_reviewer_action_capture_report_v0_1",
            P19_WINDOW_ID,
            "P19_pending_gate_evaluation",
            "pending",
            "api_sql_capture_ready",
            "not_l4_production_pass",
            json_dumps(
                [
                    {
                        "gap": "real_multi_day_human_dogfood_not_completed",
                        "reason": "P19 proves the API/SQL capture path and deterministic input drill; sustained human adoption still requires real reviewer usage.",
                    }
                ]
            ),
            json_dumps(["use Workbench POST action API with real reviewers", "review P16 regression cases promoted from actual reviewer actions"]),
            "[]",
            json_dumps({"source_window_id": P18_WINDOW_ID, "root": rel_path(root, root)}),
            now,
        ),
    )


def seed_deterministic_reviewer_input_drill(root: Path, *, runtime: FinSightResearchRuntimeFacade) -> dict[str, Any]:
    with runtime.store._connect() as conn:
        conn.row_factory = sqlite3.Row
        cases = rows_to_dicts(conn.execute("select * from dogfood_case_assignments_p18 order by case_id").fetchall())
    action_cycle = ["approve", "request_repair", "comment", "return_to_specialist", "downgrade_claim", "approve"]
    for index, case in enumerate(cases):
        action = action_cycle[index % len(action_cycle)]
        append_live_reviewer_action(
            root,
            case_id=str(case["case_id"]),
            action=action,
            comment=f"P19 deterministic reviewer input drill: {action}",
            reviewer_role="internal_reviewer",
            action_source="deterministic_input_drill",
            rebuild_if_missing=False,
        )
    with runtime.store._connect() as conn:
        conn.execute(
            """
            update live_reviewer_action_windows_p19
            set deterministic_input_drill_status = 'deterministic_input_drill_complete',
                live_action_count = (select count(*) from live_reviewer_actions_p19),
                closed_at = ?
            where window_id = ?
            """,
            (utc_now_iso(), P19_WINDOW_ID),
        )
        return {
            "case_count": count_rows(conn, "dogfood_case_assignments_p18"),
            "live_action_count": count_rows(conn, "live_reviewer_actions_p19"),
            "feedback_count": count_rows(conn, "live_reviewer_feedback_records_p19"),
            "defect_triage_count": count_rows(conn, "live_defect_triage_records_p19"),
            "regression_promotion_count": count_rows(conn, "live_regression_promotions_p19"),
            "gold_candidate_count": count_rows(conn, "live_gold_candidate_promotions_p19"),
            "case_status_count": count_rows(conn, "live_pilot_case_status_p19"),
            "api_contract_count": count_rows(conn, "live_reviewer_workbench_api_contracts_p19"),
            "p16_live_failure_count": count_query(conn, "select count(*) from failure_events_p16 where source_ref like 'p19_live_action:%'"),
            "p16_live_regression_count": count_query(conn, "select count(*) from regression_case_records_p16 where source_failure_event_id like 'p19_failure_%'"),
        }


def append_live_reviewer_action(
    root: Path,
    *,
    case_id: str,
    action: str,
    comment: str,
    reviewer_role: str = "senior_analyst",
    action_source: str = "workbench_api",
    rebuild_if_missing: bool = True,
) -> dict[str, Any]:
    if action not in SUPPORTED_REVIEW_ACTIONS:
        raise ValueError(f"unsupported_pilot_review_action:{action}")
    if rebuild_if_missing:
        ensure_p19_projection_exists(root)
    paths = default_p19_paths(root.resolve())
    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    with runtime.store._connect() as conn:
        conn.row_factory = sqlite3.Row
        create_internal_reviewer_action_capture_schema(conn)
        assignment = conn.execute(
            "select * from dogfood_case_assignments_p18 where case_id = ?",
            (case_id,),
        ).fetchone()
        if assignment is None:
            raise KeyError(f"pilot_case_not_found:{case_id}")
        assignment_row = row_to_dict(assignment)
        source_promotion = conn.execute(
            "select * from pilot_defect_promotions_p18 where case_id = ? order by created_at limit 1",
            (case_id,),
        ).fetchone()
        source_promotion_row = row_to_dict(source_promotion) if source_promotion is not None else {}

    task_id = str(assignment_row.get("runtime_task_id") or P19_TASK_ID)
    workpaper_event = runtime.append_workpaper_event(
        task_id,
        actor=reviewer_role,
        event_type=f"pilot_reviewer_{action}",
        section_id="pilot_reviewer_action",
        claim_id=case_id,
        payload={"case_id": case_id, "action": action, "comment": comment, "source": action_source},
    )
    now = utc_now_iso()
    live_action_id = stable_id("p19action", [case_id, action, reviewer_role, comment, workpaper_event["workpaper_event_id"]])
    feedback_id = stable_id("p19feedback", [live_action_id])
    triage_id = stable_id("p19triage", [live_action_id])
    p16_failure_id = ""
    p16_regression_id = ""
    triage_decision = "accepted_no_blocker" if action == "approve" else "comment_only"
    severity = "none"
    if action in REPAIR_ACTIONS:
        p16_failure_id = stable_id("p19_failure", [live_action_id])
        p16_regression_id = stable_id("p19_regression", [live_action_id])
        triage_decision = "confirmed_defect_requires_regression"
        severity = "high" if action == "downgrade_claim" else "medium"

    with runtime.store._connect() as conn:
        conn.execute("begin immediate")
        try:
            create_internal_reviewer_action_capture_schema(conn)
            conn.execute(
                "insert into live_reviewer_actions_p19 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    live_action_id,
                    P19_WINDOW_ID,
                    P18_WINDOW_ID,
                    case_id,
                    assignment_row["assignment_id"],
                    assignment_row["runtime_task_id"],
                    reviewer_role,
                    action,
                    action_source,
                    "ledgered",
                    comment,
                    workpaper_event["workpaper_event_id"],
                    p16_failure_id,
                    p16_regression_id,
                    json_dumps({"assignment_status": assignment_row.get("assignment_status"), "source_promotion": source_promotion_row}),
                    now,
                ),
            )
            conn.execute(
                "insert into live_reviewer_feedback_records_p19 values (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    feedback_id,
                    live_action_id,
                    case_id,
                    "approval" if action == "approve" else "repair_feedback" if action in REPAIR_ACTIONS else "comment",
                    "ledgered",
                    "p16_regression" if action in REPAIR_ACTIONS else "case_review_record",
                    json_dumps({"comment": comment, "action": action}),
                    now,
                ),
            )
            conn.execute(
                "insert into live_defect_triage_records_p19 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    triage_id,
                    live_action_id,
                    case_id,
                    source_promotion_row.get("promotion_id") or "",
                    triage_decision,
                    severity,
                    "quality_lead" if action in REPAIR_ACTIONS else reviewer_role,
                    "open_regression" if action in REPAIR_ACTIONS else "closed_no_blocker",
                    json_dumps({"comment": comment}),
                    now,
                ),
            )
            if action in REPAIR_ACTIONS:
                insert_p16_failure_and_regression(conn, case_id=case_id, live_action_id=live_action_id, failure_id=p16_failure_id, regression_id=p16_regression_id, severity=severity, now=now)
                conn.execute(
                    "insert into live_regression_promotions_p19 values (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        stable_id("p19live_regression", [live_action_id]),
                        live_action_id,
                        case_id,
                        p16_failure_id,
                        p16_regression_id,
                        "inserted_into_p16_regression_case_records",
                        json_dumps({"action": action, "source": action_source}),
                        now,
                    ),
                )
            if action == "approve":
                conn.execute(
                    "insert into live_gold_candidate_promotions_p19 values (?, ?, ?, ?, ?, ?, ?)",
                    (
                        stable_id("p19gold_candidate", [live_action_id]),
                        live_action_id,
                        case_id,
                        "candidate_pending_second_review",
                        1,
                        json_dumps({"reason": "single reviewer approval is not enough for final gold promotion"}),
                        now,
                    ),
                )
            upsert_case_status(conn, case_id=case_id, assignment_id=str(assignment_row["assignment_id"]), now=now)
            conn.execute(
                """
                update live_reviewer_action_windows_p19
                set live_action_count = (select count(*) from live_reviewer_actions_p19),
                    closed_at = ?
                where window_id = ?
                """,
                (now, P19_WINDOW_ID),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {
        "schema_version": SCHEMA_VERSION,
        "live_action_id": live_action_id,
        "case_id": case_id,
        "action": action,
        "status": "ledgered",
        "workpaper_event_id": workpaper_event["workpaper_event_id"],
        "p16_failure_event_id": p16_failure_id,
        "p16_regression_case_id": p16_regression_id,
    }


def insert_p16_failure_and_regression(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    live_action_id: str,
    failure_id: str,
    regression_id: str,
    severity: str,
    now: str,
) -> None:
    conn.execute(
        """
        insert into failure_events_p16(
            failure_event_id, eval_run_id, failure_taxonomy, severity, source_ref,
            owner, status, resolution_status, regression_case_id, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            failure_id,
            P16_EVAL_RUN_ID,
            "pilot_reviewer_reported_gap",
            severity,
            f"p19_live_action:{live_action_id}",
            "quality_lead",
            "open_regression",
            "regression_added_from_reviewer_feedback",
            regression_id,
            json_dumps({"case_id": case_id, "source_slice": "P19"}),
            now,
        ),
    )
    conn.execute(
        """
        insert into regression_case_records_p16(
            regression_case_id, eval_run_id, source_failure_event_id, case_id,
            dataset_id, status, owner, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            regression_id,
            P16_EVAL_RUN_ID,
            failure_id,
            case_id,
            P16_DATASET_ID,
            "active_from_p19_reviewer_feedback",
            "qa_owner",
            json_dumps({"promotion_policy": "pilot_reviewer_action_to_regression", "source_slice": "P19"}),
            now,
        ),
    )


def upsert_case_status(conn: sqlite3.Connection, *, case_id: str, assignment_id: str, now: str) -> None:
    counts = row_to_dict(
        conn.execute(
            """
            select
              count(*) as live_action_count,
              sum(case when action_type in ('request_repair', 'return_to_specialist', 'downgrade_claim') then 1 else 0 end) as unresolved_defect_count,
              sum(case when p16_regression_case_id != '' then 1 else 0 end) as p16_regression_count
            from live_reviewer_actions_p19
            where case_id = ?
            """,
            (case_id,),
        ).fetchone()
    )
    gold_count = count_query(conn, "select count(*) from live_gold_candidate_promotions_p19 where case_id = ?", (case_id,))
    last_action = row_to_dict(
        conn.execute(
            "select * from live_reviewer_actions_p19 where case_id = ? order by created_at desc limit 1",
            (case_id,),
        ).fetchone()
    )
    status = "needs_repair" if int(counts.get("unresolved_defect_count") or 0) > 0 else "accepted_or_comment_only"
    conn.execute(
        """
        insert into live_pilot_case_status_p19 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(case_id) do update set
            live_action_count=excluded.live_action_count,
            last_action_type=excluded.last_action_type,
            case_review_status=excluded.case_review_status,
            unresolved_defect_count=excluded.unresolved_defect_count,
            p16_regression_count=excluded.p16_regression_count,
            gold_candidate_count=excluded.gold_candidate_count,
            updated_at=excluded.updated_at,
            payload_json=excluded.payload_json
        """,
        (
            case_id,
            P19_WINDOW_ID,
            assignment_id,
            int(counts.get("live_action_count") or 0),
            last_action.get("action_type") or "",
            status,
            int(counts.get("unresolved_defect_count") or 0),
            int(counts.get("p16_regression_count") or 0),
            gold_count,
            now,
            json_dumps({"last_action_id": last_action.get("live_action_id") or ""}),
        ),
    )


def evaluate_p19_gates(root: Path, store: RuntimeTaskSpineStore, *, materialized: Mapping[str, Any]) -> list[dict[str, Any]]:
    now = utc_now_iso()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        required_tables = set(internal_reviewer_action_capture_schema_contract()["tables"])
        p18_case_count = count_query(conn, "select count(*) from dogfood_case_assignments_p18")
        bad_api = count_query(conn, "select count(*) from live_reviewer_workbench_api_contracts_p19 where status != 'implemented' or trace_required != 1 or sql_audit_required != 1")
        bad_action = count_query(conn, "select count(*) from live_reviewer_actions_p19 where action_status != 'ledgered' or workpaper_event_id = ''")
        repair_action_count = count_query(conn, "select count(*) from live_reviewer_actions_p19 where action_type in ('request_repair', 'return_to_specialist', 'downgrade_claim')")
        p16_promotion_count = count_query(conn, "select count(*) from live_regression_promotions_p19 where promotion_status = 'inserted_into_p16_regression_case_records'")
        gold_second_review_bad = count_query(conn, "select count(*) from live_gold_candidate_promotions_p19 where second_review_required != 1")
        window = row_to_dict(conn.execute("select * from live_reviewer_action_windows_p19 limit 1").fetchone())
        workpaper_event_count = count_query(
            conn,
            "select count(*) from workpaper_events where event_type like 'pilot_reviewer_%'",
        )
    dependencies = dependency_status_rows(root)
    dependency_pass = all(row["status"] == "pass" for row in dependencies)
    gates = [
        make_gate("p19_schema_tables_present", "schema", required_tables.issubset(tables), {"missing": sorted(required_tables - tables)}, now),
        make_gate("p19_p16_p18_dependencies_pass", "dependency", dependency_pass, {"dependencies": dependencies}, now),
        make_gate(
            "p19_all_p18_cases_have_status",
            "case_status",
            int(materialized["case_status_count"]) == p18_case_count and p18_case_count > 0,
            {"case_status_count": materialized["case_status_count"], "p18_case_count": p18_case_count},
            now,
        ),
        make_gate(
            "p19_live_actions_ledgered",
            "action_capture",
            int(materialized["live_action_count"]) >= p18_case_count and bad_action == 0,
            {"live_action_count": materialized["live_action_count"], "bad_action": bad_action},
            now,
        ),
        make_gate(
            "p19_feedback_record_per_action",
            "feedback",
            int(materialized["feedback_count"]) >= int(materialized["live_action_count"]),
            {"feedback_count": materialized["feedback_count"], "live_action_count": materialized["live_action_count"]},
            now,
        ),
        make_gate(
            "p19_repair_actions_promote_to_p16_regression",
            "regression",
            repair_action_count > 0 and p16_promotion_count == repair_action_count,
            {"repair_action_count": repair_action_count, "p16_promotion_count": p16_promotion_count},
            now,
        ),
        make_gate(
            "p19_p16_failure_regression_rows_inserted",
            "p16_lifecycle",
            int(materialized["p16_live_failure_count"]) == repair_action_count
            and int(materialized["p16_live_regression_count"]) == repair_action_count,
            {"p16_live_failure_count": materialized["p16_live_failure_count"], "p16_live_regression_count": materialized["p16_live_regression_count"]},
            now,
        ),
        make_gate(
            "p19_gold_candidate_requires_second_review",
            "gold_lifecycle",
            int(materialized["gold_candidate_count"]) >= 1
            and gold_second_review_bad == 0,
            {"gold_candidate_count": materialized["gold_candidate_count"], "gold_second_review_bad": gold_second_review_bad},
            now,
        ),
        make_gate(
            "p19_workbench_api_contracts_ready",
            "api",
            int(materialized["api_contract_count"]) == len(P19_ENDPOINTS) and bad_api == 0,
            {"api_contract_count": materialized["api_contract_count"], "bad_api": bad_api},
            now,
        ),
        make_gate(
            "p19_workpaper_events_for_actions",
            "trace",
            workpaper_event_count >= int(materialized["live_action_count"]),
            {"workpaper_event_count": workpaper_event_count, "live_action_count": materialized["live_action_count"]},
            now,
        ),
        make_gate(
            "p19_boundary_not_fake_adoption_or_production",
            "boundary",
            window.get("real_multi_day_human_adoption_status") == "pending_multi_day_human_dogfood",
            {"window": window},
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
        "gate_id": stable_id("p19gate", [name]),
        "gate_name": name,
        "gate_group": group,
        "status": "pass" if condition else "fail",
        "pass_level": "L4_scope_pass" if condition else "blocked",
        "detail": dict(detail),
        "created_at": now,
    }


def persist_p19_gate_results(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    with store._connect() as conn:
        conn.execute("delete from live_reviewer_gate_results_p19")
        for row in gate_rows:
            conn.execute(
                "insert into live_reviewer_gate_results_p19 values (?, ?, ?, ?, ?, ?, ?)",
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


def finalize_p19_report(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    fail_count = len([row for row in gate_rows if row["status"] != "pass"])
    decision = "P19_L4_scope_pass_internal_reviewer_action_capture_ready" if fail_count == 0 else "P19_blocked"
    with store._connect() as conn:
        conn.execute(
            """
            update live_reviewer_action_reports_p19
            set release_decision = ?, closeout_level = ?, gate_refs_json = ?, payload_json = ?
            where report_id = ?
            """,
            (
                decision,
                "L4_scope_pass" if fail_count == 0 else "blocked",
                json_dumps([row["gate_name"] for row in gate_rows]),
                json_dumps(
                    {
                        "gate_count": len(gate_rows),
                        "gate_fail_count": fail_count,
                        "real_multi_day_human_adoption_status": "pending_multi_day_human_dogfood",
                    }
                ),
                "p19_internal_reviewer_action_capture_report_v0_1",
            ),
        )


def build_p19_summary(
    root: Path,
    paths: P19Paths,
    gate_rows: list[dict[str, Any]],
    store: RuntimeTaskSpineStore,
    *,
    materialized: Mapping[str, Any],
    dependencies: list[dict[str, Any]],
) -> dict[str, Any]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        report = row_to_dict(conn.execute("select * from live_reviewer_action_reports_p19 limit 1").fetchone())
        window = row_to_dict(conn.execute("select * from live_reviewer_action_windows_p19 limit 1").fetchone())
    fail_count = len([row for row in gate_rows if row["status"] != "pass"])
    status = "pass" if fail_count == 0 else "fail"
    return {
        "schema_version": SCHEMA_VERSION,
        "slice": "P19 Internal Reviewer Action Capture",
        "status": status,
        "release_decision": "P19_L4_scope_pass_internal_reviewer_action_capture_ready" if status == "pass" else "P19_blocked",
        "closeout_level": "L4_scope_pass" if status == "pass" else "blocked",
        "action_capture_status": report.get("action_capture_status") or "",
        "real_multi_day_human_adoption_status": window.get("real_multi_day_human_adoption_status") or "pending_multi_day_human_dogfood",
        "full_product_release_status": report.get("full_product_release_status") or "not_l4_production_pass",
        "counts": {**dict(materialized), "gate_count": len(gate_rows), "gate_fail_count": fail_count},
        "dependency_status": dependencies,
        "outputs": {
            "schema": rel_path(paths.schema_path, root),
            "gate_rows": rel_path(paths.gate_rows_path, root),
            "summary": rel_path(paths.summary_path, root),
            "closeout_report": rel_path(paths.report_path, root),
            "runtime_db": rel_path(paths.db_path, root),
        },
        "policy": internal_reviewer_action_capture_schema_contract()["policy"],
        "generated_at": utc_now_iso(),
    }


def record_p19_artifacts(
    runtime: FinSightResearchRuntimeFacade,
    root: Path,
    paths: P19Paths,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    artifacts = [
        ("internal_reviewer_action_schema", paths.schema_path, "controlled schema"),
        ("internal_reviewer_action_gate_rows", paths.gate_rows_path, "gate rows"),
        ("internal_reviewer_action_summary", paths.summary_path, "summary"),
        ("internal_reviewer_action_report", paths.report_path, "closeout report"),
    ]
    rows = []
    for artifact_type, path, label in artifacts:
        rows.append(
            runtime.record_artifact_ref(
                task_id,
                artifact_type=f"p19_{artifact_type}",
                uri=rel_path(path, root),
                payload={"label": label, "materialized": dict(materialized)},
                actor="pilot_action_capture_builder",
            )
        )
    return rows


def render_p19_report(summary: Mapping[str, Any], gate_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# R53-R60 P19 Internal Reviewer Action Capture L4 Scope Pass",
        "",
        f"- Release decision: `{summary['release_decision']}`",
        f"- Closeout level: `{summary['closeout_level']}`",
        f"- Action capture status: `{summary['action_capture_status']}`",
        f"- Real multi-day human adoption status: `{summary['real_multi_day_human_adoption_status']}`",
        f"- Full product release status: `{summary['full_product_release_status']}`",
        f"- Status: `{summary['status']}`",
        "",
        "## Scope Boundary",
        "",
        "P19 makes P18 reviewer cases actionable through append-only Workbench actions and P16 regression promotion. Deterministic input drill rows prove the capture path; they do not prove sustained real-human adoption.",
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


def get_pilot_action_ledger(root: Path) -> dict[str, Any]:
    ensure_p19_projection_exists(root)
    store = RuntimeTaskSpineStore(default_p19_paths(root.resolve()).db_path)
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        window = decode_json_fields(row_to_dict(conn.execute("select * from live_reviewer_action_windows_p19 limit 1").fetchone()))
        report = decode_json_fields(row_to_dict(conn.execute("select * from live_reviewer_action_reports_p19 limit 1").fetchone()))
        actions = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from live_reviewer_actions_p19 order by created_at desc").fetchall()]
        statuses = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from live_pilot_case_status_p19 order by case_id").fetchall()]
        feedback = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from live_reviewer_feedback_records_p19 order by created_at desc").fetchall()]
        triage = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from live_defect_triage_records_p19 order by created_at desc").fetchall()]
        regressions = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from live_regression_promotions_p19 order by created_at desc").fetchall()]
        gold = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from live_gold_candidate_promotions_p19 order by created_at desc").fetchall()]
        gates = [decode_json_fields(row_to_dict(row)) for row in conn.execute("select * from live_reviewer_gate_results_p19 order by gate_group, gate_name").fetchall()]
    return {
        "schema_version": SCHEMA_VERSION,
        "window": window,
        "report": report,
        "live_reviewer_actions": actions,
        "case_status": statuses,
        "feedback_records": feedback,
        "defect_triage_records": triage,
        "regression_promotions": regressions,
        "gold_candidate_promotions": gold,
        "gates": gates,
        "counts": {
            "live_action_count": len(actions),
            "case_status_count": len(statuses),
            "feedback_count": len(feedback),
            "regression_promotion_count": len(regressions),
            "gold_candidate_count": len(gold),
            "gate_count": len(gates),
        },
    }


def get_pilot_case_action_ledger(root: Path, *, case_id: str) -> dict[str, Any]:
    get_pilot_case_detail(root, case_id=case_id)
    payload = get_pilot_action_ledger(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "case_status": [row for row in payload["case_status"] if str(row.get("case_id")) == case_id],
        "live_reviewer_actions": [row for row in payload["live_reviewer_actions"] if str(row.get("case_id")) == case_id],
        "feedback_records": [row for row in payload["feedback_records"] if str(row.get("case_id")) == case_id],
        "defect_triage_records": [row for row in payload["defect_triage_records"] if str(row.get("case_id")) == case_id],
        "regression_promotions": [row for row in payload["regression_promotions"] if str(row.get("case_id")) == case_id],
        "gold_candidate_promotions": [row for row in payload["gold_candidate_promotions"] if str(row.get("case_id")) == case_id],
    }


def ensure_p19_projection_exists(root: Path) -> None:
    paths = default_p19_paths(root.resolve())
    if paths.summary_path.exists():
        return
    build_p19_gate(root)


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"select count(*) from {table}").fetchone()[0])


def count_query(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    return int(conn.execute(sql, params).fetchone()[0])
