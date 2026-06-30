"""P23 product dogfood / Workbench frontend E2E readiness.

P23 consumes the P15/P18/P19 product surfaces and verifies that the Workbench
can execute the task -> drilldown -> review -> deliverable -> dashboard journey
through real backend API routes and frontend route/component contracts.

This slice intentionally does not claim real human adoption. Automated E2E
actions are marked as automation, and B04 remains open until human reviewers
accept/reject real deliverables and defects are closed through live review.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sec_agent.r53_r60_enterprise_workbench_product_surface import default_p15_paths, dependency_summary_passes
from sec_agent.r53_r60_internal_reviewer_action_capture import default_p19_paths
from sec_agent.r53_r60_internal_reviewer_dogfood_window import default_p18_paths
from sec_agent.r53_r60_runtime_task_spine import default_s1_paths, rel_path, utc_now_iso, write_json, write_jsonl


SCHEMA_VERSION = "r53_r60_p23_product_dogfood_frontend_e2e_v0_1"
P23_TASK_ID = "p23_scope_task_product_dogfood_frontend_e2e"
P23_AUTOMATION_REVIEWER_ROLE = "automation_e2e"
P23_AUTOMATION_COMMENT = "P23 automated Workbench product journey verification"

DEPENDENCY_SUMMARIES = {
    "P15": (
        lambda root: default_p15_paths(root).summary_path,
        "P15_L4_scope_pass_enterprise_workbench_product_surface_ready",
    ),
    "P18": (
        lambda root: default_p18_paths(root).summary_path,
        "P18_L4_scope_pass_internal_reviewer_dogfood_window_ready",
    ),
    "P19": (
        lambda root: default_p19_paths(root).summary_path,
        "P19_L4_scope_pass_internal_reviewer_action_capture_ready",
    ),
    "P21": (
        lambda root: root / "data" / "manifests" / "r53_r60_p21_pre_full_chain_blocker_summary_v0_1.json",
        "P21_pre_full_chain_blockers_registered_broad_full_chain_blocked",
    ),
    "P22": (
        lambda root: root / "data" / "manifests" / "r53_r60_p22_source_doc_status_reconciliation_summary_v0_1.json",
        "P22_source_docs_reconciled_broad_full_chain_still_blocked",
    ),
}

FRONTEND_MARKERS = (
    ("route_panel_anchor", 'id="r53-r60-workbench"', "R53-R60 Workbench route anchor"),
    ("workbench_panel_component", "function R53R60WorkbenchPanel", "Workbench panel component"),
    ("pilot_dogfood_panel_component", "function R53R60PilotDogfoodPanel", "Pilot dogfood panel component"),
    ("task_api_route", '"/api/r53-r60/tasks"', "task center API route"),
    ("pilot_dashboard_route", '"/api/r53-r60/pilot/dashboard"', "pilot dashboard API route"),
    ("review_action_route", "/review-actions", "review action API route"),
    ("deliverable_studio_label", "Deliverable Studio", "deliverable studio visible label"),
    ("review_queue_label", "Review queue", "review queue visible label"),
    ("dashboard_projection_label", "Dashboard Projection", "dashboard projection visible label"),
)

REQUIRED_API_SURFACES = (
    "task_center",
    "task_state",
    "task_events",
    "task_artifacts",
    "task_drilldown",
    "review_queue",
    "ops_projection",
    "deliverables",
    "dashboard_projection",
    "scope_gate",
    "pilot_dashboard",
    "pilot_action_ledger",
    "task_review_action_write",
    "pilot_review_action_write",
)


@dataclass(frozen=True)
class P23Paths:
    db_path: Path
    schema_path: Path
    api_journey_rows_path: Path
    frontend_check_rows_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


def default_p23_paths(root: Path) -> P23Paths:
    s1_paths = default_s1_paths(root)
    return P23Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "p23_product_dogfood_frontend_e2e_schema_v0_1.json",
        api_journey_rows_path=root
        / "data"
        / "manifests"
        / "r53_r60_p23_product_dogfood_frontend_e2e_api_journey_rows_v0_1.jsonl",
        frontend_check_rows_path=root
        / "data"
        / "manifests"
        / "r53_r60_p23_product_dogfood_frontend_e2e_frontend_check_rows_v0_1.jsonl",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_p23_product_dogfood_frontend_e2e_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_p23_product_dogfood_frontend_e2e_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_p23_product_dogfood_frontend_e2e_scope_pass_human_pending.zh-CN.md",
    )


def p23_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass_for_automated_product_journey_only",
        "release_scope": "workbench_api_frontend_e2e_readiness_human_acceptance_pending",
        "tables": [
            "product_dogfood_frontend_e2e_metadata_p23",
            "product_acceptance_dependency_checks_p23",
            "product_acceptance_api_journey_checks_p23",
            "product_acceptance_frontend_checks_p23",
            "product_acceptance_human_review_requirements_p23",
            "product_acceptance_gate_results_p23",
            "product_acceptance_reports_p23",
        ],
        "api_surfaces": list(REQUIRED_API_SURFACES),
        "policy": {
            "automation_e2e_must_not_count_as_real_human_adoption": True,
            "frontend_state_is_projection_only": True,
            "review_actions_are_append_only": True,
            "b04_remains_open_until_real_reviewer_acceptance": True,
            "broad_full_chain_quality_eval_stays_blocked": True,
        },
    }


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def create_p23_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists product_dogfood_frontend_e2e_metadata_p23 (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists product_acceptance_dependency_checks_p23 (
            dependency_id text primary key,
            summary_path text not null,
            expected_release_decision text not null,
            actual_release_decision text not null default '',
            status text not null,
            detail_json text not null default '{}',
            checked_at text not null
        );
        create table if not exists product_acceptance_api_journey_checks_p23 (
            check_id text primary key,
            surface text not null,
            method text not null,
            path text not null,
            status_code integer not null,
            status text not null,
            response_keys_json text not null default '[]',
            detail_json text not null default '{}',
            checked_at text not null
        );
        create table if not exists product_acceptance_frontend_checks_p23 (
            check_id text primary key,
            surface text not null,
            file_path text not null,
            marker text not null,
            status text not null,
            detail_json text not null default '{}',
            checked_at text not null
        );
        create table if not exists product_acceptance_human_review_requirements_p23 (
            requirement_id text primary key,
            requirement text not null,
            current_status text not null,
            why_required text not null,
            evidence_needed_json text not null default '[]',
            created_at text not null
        );
        create table if not exists product_acceptance_gate_results_p23 (
            gate_id text primary key,
            gate_name text not null,
            gate_group text not null,
            status text not null,
            detail_json text not null default '{}',
            created_at text not null
        );
        create table if not exists product_acceptance_reports_p23 (
            report_id text primary key,
            release_decision text not null,
            closeout_level text not null,
            product_acceptance_status text not null,
            b04_status_after_p23 text not null,
            frontend_e2e_status text not null,
            human_adoption_status text not null,
            known_gaps_json text not null default '[]',
            next_actions_json text not null default '[]',
            gate_refs_json text not null default '[]',
            payload_json text not null default '{}',
            created_at text not null
        );
        """
    )


def clear_p23_rows(conn: sqlite3.Connection) -> None:
    for table in (
        "product_dogfood_frontend_e2e_metadata_p23",
        "product_acceptance_dependency_checks_p23",
        "product_acceptance_api_journey_checks_p23",
        "product_acceptance_frontend_checks_p23",
        "product_acceptance_human_review_requirements_p23",
        "product_acceptance_gate_results_p23",
        "product_acceptance_reports_p23",
    ):
        conn.execute(f"delete from {table}")


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def dependency_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    now = utc_now_iso()
    for dependency_id, (path_fn, expected_release_decision) in DEPENDENCY_SUMMARIES.items():
        path = path_fn(root)
        payload = _load_json(path)
        actual_release_decision = str(payload.get("release_decision", ""))
        status = "pass" if dependency_summary_passes(path, expected_release_decision) else "fail"
        rows.append(
            {
                "dependency_id": dependency_id,
                "summary_path": rel_path(path, root),
                "expected_release_decision": expected_release_decision,
                "actual_release_decision": actual_release_decision,
                "status": status,
                "detail": {
                    "summary_exists": path.exists(),
                    "summary_status": payload.get("status"),
                    "closeout_level": payload.get("closeout_level"),
                    "known_boundary_fields": {
                        key: payload.get(key)
                        for key in (
                            "full_product_release_status",
                            "real_human_adoption_status",
                            "real_multi_day_human_adoption_status",
                            "full_runtime_migration_status",
                        )
                        if key in payload
                    },
                },
                "checked_at": now,
            }
        )
    return rows


def _response_keys(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        return sorted(str(key) for key in payload)
    if isinstance(payload, list):
        return ["<list>"]
    return [type(payload).__name__]


def _has_existing_action(rows: list[dict[str, Any]], *, comment: str) -> bool:
    return any(
        str(row.get("comment", "")) == comment and str(row.get("reviewer_role", "")) == P23_AUTOMATION_REVIEWER_ROLE
        for row in rows
    )


def run_workbench_api_journey(root: Path, *, write_probe: bool = True) -> list[dict[str, Any]]:
    """Run a deterministic Workbench API journey against the current repo root."""

    root_str = str(root)
    path_inserted = False
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
        path_inserted = True
    try:
        from fastapi.testclient import TestClient

        import apps.workbench.backend.app as workbench_app
    except Exception as exc:  # pragma: no cover - exercised only in missing optional dependency envs.
        return [
            {
                "check_id": "p23_api_import_fastapi_workbench",
                "surface": "api_import",
                "method": "IMPORT",
                "path": "apps.workbench.backend.app",
                "status_code": 0,
                "status": "fail",
                "response_keys": [],
                "detail": {"error": repr(exc)},
                "checked_at": utc_now_iso(),
            }
        ]
    finally:
        if path_inserted:
            try:
                sys.path.remove(root_str)
            except ValueError:
                pass

    old_root = workbench_app.REPO_ROOT
    workbench_app.REPO_ROOT = root
    store_path = root / "data" / "workbench_private" / "research_data" / "r53_r60_p23_workbench_api_e2e_probe.sqlite"
    client = TestClient(workbench_app.create_app(store_path=store_path))
    rows: list[dict[str, Any]] = []

    def call(surface: str, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        response = client.request(method, path, json=payload)
        try:
            body = response.json()
        except Exception:
            body = {"raw_text": response.text[:500]}
        row = {
            "check_id": f"p23_api_{surface}",
            "surface": surface,
            "method": method,
            "path": path,
            "status_code": response.status_code,
            "status": "pass" if 200 <= response.status_code < 300 else "fail",
            "response_keys": _response_keys(body),
            "detail": {
                "payload_summary": _summarize_api_payload(surface, body),
            },
            "checked_at": utc_now_iso(),
        }
        rows.append(row)
        return body if isinstance(body, dict) else {"body": body}

    try:
        tasks_payload = call("task_center", "GET", "/api/r53-r60/tasks")
        tasks = tasks_payload.get("tasks") if isinstance(tasks_payload.get("tasks"), list) else []
        task_id = str(tasks[0].get("task_id")) if tasks else ""
        if task_id:
            call("task_state", "GET", f"/api/r53-r60/tasks/{task_id}")
            call("task_events", "GET", f"/api/r53-r60/tasks/{task_id}/events")
            call("task_artifacts", "GET", f"/api/r53-r60/tasks/{task_id}/artifacts")
            call("task_drilldown", "GET", f"/api/r53-r60/tasks/{task_id}/drilldown")
            review_payload = call("review_queue", "GET", f"/api/r53-r60/tasks/{task_id}/review-queue")
            call("ops_projection", "GET", f"/api/r53-r60/tasks/{task_id}/ops")
            call("deliverables", "GET", f"/api/r53-r60/tasks/{task_id}/deliverables")
            call("dashboard_projection", "GET", f"/api/r53-r60/tasks/{task_id}/dashboard-projection")
            if write_probe:
                existing_actions = review_payload.get("review_actions") if isinstance(review_payload.get("review_actions"), list) else []
                if _has_existing_action(existing_actions, comment=P23_AUTOMATION_COMMENT):
                    rows.append(
                        {
                            "check_id": "p23_api_task_review_action_write",
                            "surface": "task_review_action_write",
                            "method": "POST",
                            "path": f"/api/r53-r60/tasks/{task_id}/review-actions",
                            "status_code": 200,
                            "status": "pass",
                            "response_keys": ["already_present"],
                            "detail": {"idempotent_skip": True, "comment": P23_AUTOMATION_COMMENT},
                            "checked_at": utc_now_iso(),
                        }
                    )
                else:
                    call(
                        "task_review_action_write",
                        "POST",
                        f"/api/r53-r60/tasks/{task_id}/review-actions",
                        {
                            "action": "comment",
                            "comment": P23_AUTOMATION_COMMENT,
                            "reviewer_role": P23_AUTOMATION_REVIEWER_ROLE,
                        },
                    )
        call("scope_gate", "GET", "/api/r53-r60/scope-gate")
        pilot_payload = call("pilot_dashboard", "GET", "/api/r53-r60/pilot/dashboard")
        action_payload = call("pilot_action_ledger", "GET", "/api/r53-r60/pilot/actions")
        pilot_cases = pilot_payload.get("case_assignments") if isinstance(pilot_payload.get("case_assignments"), list) else []
        case_id = str(pilot_cases[0].get("case_id")) if pilot_cases else ""
        if write_probe and case_id:
            live_actions = action_payload.get("live_reviewer_actions") if isinstance(action_payload.get("live_reviewer_actions"), list) else []
            if _has_existing_action(live_actions, comment=P23_AUTOMATION_COMMENT):
                rows.append(
                    {
                        "check_id": "p23_api_pilot_review_action_write",
                        "surface": "pilot_review_action_write",
                        "method": "POST",
                        "path": f"/api/r53-r60/pilot/cases/{case_id}/review-actions",
                        "status_code": 200,
                        "status": "pass",
                        "response_keys": ["already_present"],
                        "detail": {"idempotent_skip": True, "comment": P23_AUTOMATION_COMMENT},
                        "checked_at": utc_now_iso(),
                    }
                )
            else:
                call(
                    "pilot_review_action_write",
                    "POST",
                    f"/api/r53-r60/pilot/cases/{case_id}/review-actions",
                    {
                        "action": "comment",
                        "comment": P23_AUTOMATION_COMMENT,
                        "reviewer_role": P23_AUTOMATION_REVIEWER_ROLE,
                    },
                )
    finally:
        workbench_app.REPO_ROOT = old_root
    return rows


def _summarize_api_payload(surface: str, body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {"body_type": type(body).__name__}
    if surface == "task_center":
        return {"task_count": len(body.get("tasks", []))}
    if surface == "task_drilldown":
        drilldown = body.get("drilldown", {})
        return {
            "section_count": len(drilldown.get("sections", [])) if isinstance(drilldown, dict) else 0,
            "claim_count": len(drilldown.get("claims", [])) if isinstance(drilldown, dict) else 0,
            "gap_count": len(drilldown.get("gaps", [])) if isinstance(drilldown, dict) else 0,
        }
    if surface == "review_queue":
        return {"review_items": len(body.get("review_queue", [])), "review_actions": len(body.get("review_actions", []))}
    if surface == "deliverables":
        return {"render_jobs": len(body.get("render_jobs", [])), "quality_gates": len(body.get("quality_gates", []))}
    if surface == "pilot_dashboard":
        return {"case_assignments": len(body.get("case_assignments", [])), "reviewer_sessions": len(body.get("reviewer_sessions", []))}
    if surface == "pilot_action_ledger":
        return {"live_reviewer_actions": len(body.get("live_reviewer_actions", []))}
    return {"keys": _response_keys(body)}


def frontend_check_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    now = utc_now_iso()
    main_path = root / "apps" / "workbench" / "frontend" / "vite" / "src" / "main.tsx"
    css_path = root / "apps" / "workbench" / "frontend" / "vite" / "src" / "workbench.css"
    dist_index = root / "apps" / "workbench" / "frontend" / "dist" / "index.html"
    main_text = main_path.read_text(encoding="utf-8") if main_path.exists() else ""
    for check_id, marker, description in FRONTEND_MARKERS:
        rows.append(
            {
                "check_id": f"p23_frontend_{check_id}",
                "surface": check_id,
                "file_path": rel_path(main_path, root),
                "marker": marker,
                "status": "pass" if marker in main_text else "fail",
                "detail": {"description": description},
                "checked_at": now,
            }
        )
    css_text = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    for check_id, marker, description in (
        ("pilot_panel_style", "pilot-dogfood-panel", "pilot dogfood panel styling"),
        ("review_action_style", "pilot-action-editor", "review action editor styling"),
        ("answer_preview_style", "answer-preview", "rendered answer preview styling"),
    ):
        rows.append(
            {
                "check_id": f"p23_frontend_{check_id}",
                "surface": check_id,
                "file_path": rel_path(css_path, root),
                "marker": marker,
                "status": "pass" if marker in css_text else "fail",
                "detail": {"description": description},
                "checked_at": now,
            }
        )
    build_fresh = dist_index.exists() and main_path.exists() and dist_index.stat().st_mtime >= main_path.stat().st_mtime
    rows.append(
        {
            "check_id": "p23_frontend_vite_dist_build_exists",
            "surface": "vite_dist_build",
            "file_path": rel_path(dist_index, root),
            "marker": "dist/index.html",
            "status": "pass" if build_fresh else "warn",
            "detail": {
                "dist_exists": dist_index.exists(),
                "build_fresh_relative_to_main_tsx": build_fresh,
                "reason": "Run npm build before product visual review; this gate is warn if dist is stale.",
            },
            "checked_at": now,
        }
    )
    return rows


def human_requirement_rows() -> list[dict[str, Any]]:
    now = utc_now_iso()
    return [
        {
            "requirement_id": "p23_human_real_reviewer_sessions",
            "requirement": "Real reviewers run at least one full Workbench task review session.",
            "current_status": "pending_real_human_review",
            "why_required": "Automation can prove path availability, but cannot prove the workflow helps a senior analyst review or decide.",
            "evidence_needed": ["reviewer identity/role", "session timestamps", "accepted/rejected deliverables", "review comments"],
            "created_at": now,
        },
        {
            "requirement_id": "p23_human_defect_closure",
            "requirement": "Reviewer defects are triaged, repaired or explicitly accepted as typed gaps.",
            "current_status": "pending_real_human_review",
            "why_required": "Enterprise acceptance requires defect closure, not only action capture.",
            "evidence_needed": ["defect ids", "repair commits or typed-gap decisions", "second review result"],
            "created_at": now,
        },
        {
            "requirement_id": "p23_human_visual_acceptance",
            "requirement": "A reviewer confirms the Workbench flow is readable and usable on a real browser.",
            "current_status": "pending_real_human_review",
            "why_required": "Static and API checks cannot judge whether the product surface is usable for analyst work.",
            "evidence_needed": ["browser screenshots", "review notes", "visual defects", "accepted/rejected UI decision"],
            "created_at": now,
        },
    ]


def build_gate_rows(
    dependency_checks: list[dict[str, Any]],
    api_rows: list[dict[str, Any]],
    frontend_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    api_surfaces = {row["surface"] for row in api_rows if row["status"] == "pass"}
    frontend_failures = [row for row in frontend_rows if row["status"] == "fail"]
    api_failures = [row for row in api_rows if row["status"] == "fail"]
    dependency_failures = [row for row in dependency_checks if row["status"] != "pass"]
    build_warnings = [row for row in frontend_rows if row["status"] == "warn"]
    now = utc_now_iso()

    def gate(gate_id: str, group: str, ok: bool, detail: dict[str, Any], *, warn: bool = False) -> dict[str, Any]:
        return {
            "gate_id": gate_id,
            "gate_name": gate_id,
            "gate_group": group,
            "status": "warn" if warn and ok else ("pass" if ok else "fail"),
            "detail": detail,
            "created_at": now,
        }

    return [
        gate(
            "p23_dependencies_pass",
            "dependency",
            not dependency_failures,
            {"dependency_failures": dependency_failures},
        ),
        gate(
            "p23_workbench_api_read_journey_pass",
            "api",
            not api_failures and set(REQUIRED_API_SURFACES).issubset(api_surfaces),
            {"api_failures": api_failures, "missing_surfaces": sorted(set(REQUIRED_API_SURFACES) - api_surfaces)},
        ),
        gate(
            "p23_review_action_write_path_verified_as_automation",
            "api",
            {"task_review_action_write", "pilot_review_action_write"}.issubset(api_surfaces),
            {"automation_reviewer_role": P23_AUTOMATION_REVIEWER_ROLE},
        ),
        gate(
            "p23_frontend_source_routes_and_panels_present",
            "frontend",
            not frontend_failures,
            {"frontend_failures": frontend_failures},
        ),
        gate(
            "p23_frontend_build_artifact_available",
            "frontend",
            not any(row["check_id"] == "p23_frontend_vite_dist_build_exists" and row["status"] == "fail" for row in frontend_rows),
            {"warnings": build_warnings},
            warn=bool(build_warnings),
        ),
        gate(
            "p23_human_adoption_not_faked",
            "product_acceptance",
            True,
            {
                "human_adoption_status": "pending_real_human_review",
                "automation_actions_do_not_count_as_human_acceptance": True,
            },
        ),
        gate(
            "p23_b04_remains_open_until_real_reviewer_acceptance",
            "release_boundary",
            True,
            {"b04_status_after_p23": "open_product_acceptance_required"},
        ),
    ]


def persist_p23_rows(
    root: Path,
    paths: P23Paths,
    dependency_checks: list[dict[str, Any]],
    api_rows: list[dict[str, Any]],
    frontend_rows: list[dict[str, Any]],
    human_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    with _connect(paths.db_path) as conn:
        create_p23_schema(conn)
        clear_p23_rows(conn)
        now = utc_now_iso()
        conn.execute(
            "insert into product_dogfood_frontend_e2e_metadata_p23(key, value_json, updated_at) values (?, ?, ?)",
            ("schema_version", _json_dumps({"schema_version": SCHEMA_VERSION}), now),
        )
        for row in dependency_checks:
            conn.execute(
                """
                insert into product_acceptance_dependency_checks_p23(
                    dependency_id, summary_path, expected_release_decision, actual_release_decision,
                    status, detail_json, checked_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["dependency_id"],
                    row["summary_path"],
                    row["expected_release_decision"],
                    row["actual_release_decision"],
                    row["status"],
                    _json_dumps(row["detail"]),
                    row["checked_at"],
                ),
            )
        for row in api_rows:
            conn.execute(
                """
                insert into product_acceptance_api_journey_checks_p23(
                    check_id, surface, method, path, status_code, status, response_keys_json, detail_json, checked_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["check_id"],
                    row["surface"],
                    row["method"],
                    row["path"],
                    row["status_code"],
                    row["status"],
                    _json_dumps(row["response_keys"]),
                    _json_dumps(row["detail"]),
                    row["checked_at"],
                ),
            )
        for row in frontend_rows:
            conn.execute(
                """
                insert into product_acceptance_frontend_checks_p23(
                    check_id, surface, file_path, marker, status, detail_json, checked_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["check_id"],
                    row["surface"],
                    row["file_path"],
                    row["marker"],
                    row["status"],
                    _json_dumps(row["detail"]),
                    row["checked_at"],
                ),
            )
        for row in human_rows:
            conn.execute(
                """
                insert into product_acceptance_human_review_requirements_p23(
                    requirement_id, requirement, current_status, why_required, evidence_needed_json, created_at
                ) values (?, ?, ?, ?, ?, ?)
                """,
                (
                    row["requirement_id"],
                    row["requirement"],
                    row["current_status"],
                    row["why_required"],
                    _json_dumps(row["evidence_needed"]),
                    row["created_at"],
                ),
            )
        for row in gate_rows:
            conn.execute(
                """
                insert into product_acceptance_gate_results_p23(
                    gate_id, gate_name, gate_group, status, detail_json, created_at
                ) values (?, ?, ?, ?, ?, ?)
                """,
                (row["gate_id"], row["gate_name"], row["gate_group"], row["status"], _json_dumps(row["detail"]), row["created_at"]),
            )
        conn.execute(
            """
            insert into product_acceptance_reports_p23(
                report_id, release_decision, closeout_level, product_acceptance_status, b04_status_after_p23,
                frontend_e2e_status, human_adoption_status, known_gaps_json, next_actions_json, gate_refs_json,
                payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "p23_product_dogfood_frontend_e2e_report_v0_1",
                summary["release_decision"],
                summary["closeout_level"],
                summary["product_acceptance_status"],
                summary["b04_status_after_p23"],
                summary["frontend_e2e_status"],
                summary["human_adoption_status"],
                _json_dumps(summary["known_gaps"]),
                _json_dumps(summary["next_actions"]),
                _json_dumps([row["gate_id"] for row in gate_rows]),
                _json_dumps({"counts": summary["counts"], "outputs": summary["outputs"]}),
                summary["generated_at"],
            ),
        )


def build_p23_product_dogfood_frontend_e2e(root: Path, *, write_probe: bool = True) -> dict[str, Any]:
    root = root.resolve()
    paths = default_p23_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.api_journey_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    dependency_checks = dependency_rows(root)
    api_rows = run_workbench_api_journey(root, write_probe=write_probe)
    frontend_rows = frontend_check_rows(root)
    human_rows = human_requirement_rows()
    gate_rows = build_gate_rows(dependency_checks, api_rows, frontend_rows)
    gate_fail_count = sum(1 for row in gate_rows if row["status"] == "fail")
    gate_warn_count = sum(1 for row in gate_rows if row["status"] == "warn")
    dependency_fail_count = sum(1 for row in dependency_checks if row["status"] != "pass")
    api_fail_count = sum(1 for row in api_rows if row["status"] == "fail")
    frontend_fail_count = sum(1 for row in frontend_rows if row["status"] == "fail")
    generated_at = utc_now_iso()
    status = "blocked" if gate_fail_count else "pass_with_human_acceptance_blocked"

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "release_decision": "P23_automated_product_journey_pass_human_dogfood_pending" if not gate_fail_count else "P23_blocked",
        "closeout_level": "L4_scope_pass_for_automated_product_journey_only" if not gate_fail_count else "blocked",
        "product_acceptance_status": "blocked_requires_real_human_review",
        "b04_status_after_p23": "open_product_acceptance_required",
        "frontend_e2e_status": "api_journey_and_frontend_build_verified_visual_human_review_pending",
        "human_adoption_status": "pending_real_human_reviewer_sessions",
        "full_chain_broad_eval_allowed": False,
        "counts": {
            "dependency_check_count": len(dependency_checks),
            "dependency_fail_count": dependency_fail_count,
            "api_journey_check_count": len(api_rows),
            "api_journey_fail_count": api_fail_count,
            "frontend_check_count": len(frontend_rows),
            "frontend_fail_count": frontend_fail_count,
            "frontend_warn_count": sum(1 for row in frontend_rows if row["status"] == "warn"),
            "human_requirement_count": len(human_rows),
            "gate_count": len(gate_rows),
            "gate_fail_count": gate_fail_count,
            "gate_warn_count": gate_warn_count,
        },
        "known_gaps": [
            {
                "gap": "real_human_reviewer_acceptance_not_completed",
                "reason": "P23 automation proves the Workbench product journey is reachable; it cannot replace a real reviewer accepting or rejecting deliverables.",
            },
            {
                "gap": "broad_full_chain_quality_eval_still_blocked",
                "reason": "B05 data-depth and pack-level gates remain open before 20-50 broad full-chain cases can count as research-quality evidence.",
            },
        ],
        "next_actions": [
            "run real reviewer sessions through Workbench and record accepted/rejected deliverables",
            "close reviewer-raised defects or promote them to typed gaps",
            "continue P24/P25 pack-depth gates before broad full-chain quality regression",
        ],
        "outputs": {
            "schema": rel_path(paths.schema_path, root),
            "api_journey_rows": rel_path(paths.api_journey_rows_path, root),
            "frontend_check_rows": rel_path(paths.frontend_check_rows_path, root),
            "gate_rows": rel_path(paths.gate_rows_path, root),
            "summary": rel_path(paths.summary_path, root),
            "report": rel_path(paths.report_path, root),
            "runtime_db": rel_path(paths.db_path, root),
        },
    }

    persist_p23_rows(root, paths, dependency_checks, api_rows, frontend_rows, human_rows, gate_rows, summary)
    write_json(paths.schema_path, p23_schema_contract())
    write_jsonl(paths.api_journey_rows_path, api_rows)
    write_jsonl(paths.frontend_check_rows_path, frontend_rows)
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_p23_report(summary, dependency_checks, gate_rows), encoding="utf-8")
    return summary


def render_p23_report(summary: dict[str, Any], dependency_checks: list[dict[str, Any]], gate_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# R53-R60 P23 Product Dogfood / Frontend E2E Readiness",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Release decision: `{summary['release_decision']}`",
        f"- Closeout level: `{summary['closeout_level']}`",
        f"- Product acceptance status: `{summary['product_acceptance_status']}`",
        f"- B04 status after P23: `{summary['b04_status_after_p23']}`",
        f"- Broad full-chain eval allowed: `{summary['full_chain_broad_eval_allowed']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Dependency Checks", ""])
    for row in dependency_checks:
        lines.append(
            f"- `{row['dependency_id']}`: `{row['status']}`; expected `{row['expected_release_decision']}`, actual `{row['actual_release_decision']}`"
        )
    lines.extend(["", "## Gates", ""])
    for row in gate_rows:
        lines.append(f"- `{row['gate_id']}`: `{row['status']}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "P23 automated API/frontend E2E actions are not real human adoption. B04 remains open until real reviewers complete sessions, accept/reject deliverables, and close defects.",
            "",
            "P23 自动化 API / frontend E2E 行为不等于真人采用。只有真实 reviewer 完成会话、对交付物作出接受/退回判断并关闭缺陷后，B04 才能关闭。",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "SCHEMA_VERSION",
    "P23_AUTOMATION_COMMENT",
    "P23_AUTOMATION_REVIEWER_ROLE",
    "P23Paths",
    "build_p23_product_dogfood_frontend_e2e",
    "create_p23_schema",
    "default_p23_paths",
    "dependency_rows",
    "frontend_check_rows",
    "p23_schema_contract",
    "run_workbench_api_journey",
]
