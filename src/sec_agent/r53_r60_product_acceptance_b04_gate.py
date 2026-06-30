"""P24 / B04 product acceptance gate.

P23 proves that the Workbench API/product journey is reachable. P24 adds the
next acceptance layer: real-browser E2E evidence, reviewer acceptance protocol,
defect closeout requirements and a machine-readable boundary that prevents
automation from being promoted into real human product acceptance.
"""

from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sec_agent.r53_r60_product_dogfood_frontend_e2e import default_p23_paths
from sec_agent.r53_r60_runtime_task_spine import default_s1_paths, rel_path, utc_now_iso, write_json, write_jsonl


SCHEMA_VERSION = "r53_r60_p24_b04_product_acceptance_gate_v0_1"
P24_TASK_ID = "p24_scope_task_b04_product_acceptance_gate"
P24_REPORT_ID = "p24_b04_product_acceptance_gate_report_v0_1"

EXPECTED_P23_RELEASE_DECISION = "P23_automated_product_journey_pass_human_dogfood_pending"

P24_REQUIRED_BROWSER_LABELS = (
    "R53-R60 工作台",
    "Pilot dogfood window",
    "任务中心",
    "Review queue",
    "Deliverable Studio",
    "Dashboard Projection",
)

P24_REQUIRED_BROWSER_APIS = (
    ("/api/health", "health"),
    ("/api/r53-r60/tasks", "task_center"),
    ("/api/r53-r60/scope-gate", "scope_gate"),
    ("/api/r53-r60/pilot/dashboard", "pilot_dashboard"),
    ("/api/r53-r60/pilot/actions", "pilot_action_ledger"),
)

P24_REAL_HUMAN_REVIEWER_ROLES = {
    "lead_analyst",
    "portfolio_manager",
    "senior_research_reviewer",
    "product_owner",
}


@dataclass(frozen=True)
class P24Paths:
    db_path: Path
    schema_path: Path
    protocol_rows_path: Path
    browser_e2e_rows_path: Path
    human_evidence_rows_path: Path
    defect_closeout_rows_path: Path
    decision_rows_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path
    screenshot_dir: Path


def default_p24_paths(root: Path) -> P24Paths:
    s1_paths = default_s1_paths(root)
    return P24Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "p24_b04_product_acceptance_gate_schema_v0_1.json",
        protocol_rows_path=root / "data" / "manifests" / "r53_r60_p24_b04_product_acceptance_protocol_rows_v0_1.jsonl",
        browser_e2e_rows_path=root / "data" / "manifests" / "r53_r60_p24_b04_browser_e2e_rows_v0_1.jsonl",
        human_evidence_rows_path=root
        / "data"
        / "manifests"
        / "r53_r60_p24_b04_human_evidence_requirements_v0_1.jsonl",
        defect_closeout_rows_path=root
        / "data"
        / "manifests"
        / "r53_r60_p24_b04_defect_closeout_requirements_v0_1.jsonl",
        decision_rows_path=root / "data" / "manifests" / "r53_r60_p24_b04_acceptance_decision_rows_v0_1.jsonl",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_p24_b04_product_acceptance_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_p24_b04_product_acceptance_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_p24_b04_product_acceptance_gate_human_pending.zh-CN.md",
        screenshot_dir=root / "reports" / "r53_r60_p24_b04_product_acceptance_browser_e2e",
    )


def p24_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass_for_product_acceptance_infrastructure_only",
        "release_scope": "b04_product_acceptance_protocol_browser_e2e_human_review_pending",
        "tables": [
            "product_acceptance_protocol_p24",
            "product_acceptance_browser_e2e_p24",
            "product_acceptance_human_evidence_requirements_p24",
            "product_acceptance_defect_closeout_requirements_p24",
            "product_acceptance_decision_records_p24",
            "product_acceptance_gate_results_p24",
            "product_acceptance_reports_p24",
        ],
        "policy": {
            "browser_e2e_must_use_real_http_server": True,
            "automation_must_not_count_as_human_acceptance": True,
            "real_human_acceptance_requires_named_reviewer_role": sorted(P24_REAL_HUMAN_REVIEWER_ROLES),
            "accepted_or_rejected_deliverable_decision_required": True,
            "defect_closeout_or_typed_gap_required": True,
            "b04_cannot_close_with_pending_human_evidence": True,
        },
        "required_browser_labels": list(P24_REQUIRED_BROWSER_LABELS),
        "required_browser_apis": [{"path": path, "surface": surface} for path, surface in P24_REQUIRED_BROWSER_APIS],
    }


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("select 1 from sqlite_master where type='table' and name = ?", (table,)).fetchone()
    return bool(row)


def create_p24_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists product_acceptance_protocol_p24 (
            protocol_id text primary key,
            protocol_group text not null,
            requirement text not null,
            pass_condition text not null,
            evidence_needed_json text not null default '[]',
            status text not null,
            created_at text not null
        );
        create table if not exists product_acceptance_browser_e2e_p24 (
            check_id text primary key,
            viewport text not null,
            surface text not null,
            url text not null,
            status text not null,
            screenshot_path text not null default '',
            detail_json text not null default '{}',
            checked_at text not null
        );
        create table if not exists product_acceptance_human_evidence_requirements_p24 (
            requirement_id text primary key,
            evidence_type text not null,
            requirement text not null,
            current_status text not null,
            required_for_b04_close integer not null,
            evidence_needed_json text not null default '[]',
            created_at text not null
        );
        create table if not exists product_acceptance_defect_closeout_requirements_p24 (
            closeout_id text primary key,
            source_table text not null,
            source_id text not null,
            case_id text not null default '',
            defect_type text not null default '',
            source_status text not null default '',
            required_closeout text not null,
            current_status text not null,
            detail_json text not null default '{}',
            created_at text not null
        );
        create table if not exists product_acceptance_decision_records_p24 (
            decision_id text primary key,
            reviewer_role text not null,
            decision_scope text not null,
            decision_status text not null,
            deliverable_ref text not null default '',
            defect_closeout_status text not null,
            evidence_json text not null default '{}',
            created_at text not null
        );
        create table if not exists product_acceptance_gate_results_p24 (
            gate_id text primary key,
            gate_name text not null,
            gate_group text not null,
            status text not null,
            detail_json text not null default '{}',
            created_at text not null
        );
        create table if not exists product_acceptance_reports_p24 (
            report_id text primary key,
            release_decision text not null,
            closeout_level text not null,
            product_acceptance_status text not null,
            b04_status_after_p24 text not null,
            browser_e2e_status text not null,
            human_adoption_status text not null,
            known_gaps_json text not null default '[]',
            next_actions_json text not null default '[]',
            gate_refs_json text not null default '[]',
            payload_json text not null default '{}',
            created_at text not null
        );
        """
    )


def clear_p24_rows(conn: sqlite3.Connection) -> None:
    for table in p24_schema_contract()["tables"]:
        conn.execute(f"delete from {table}")


def dependency_rows(root: Path) -> list[dict[str, Any]]:
    now = utc_now_iso()
    p23_path = default_p23_paths(root).summary_path
    p23_payload = _read_json(p23_path)
    actual_decision = str(p23_payload.get("release_decision", ""))
    return [
        {
            "dependency_id": "P23",
            "summary_path": rel_path(p23_path, root),
            "expected_release_decision": EXPECTED_P23_RELEASE_DECISION,
            "actual_release_decision": actual_decision,
            "status": "pass" if p23_path.exists() and actual_decision == EXPECTED_P23_RELEASE_DECISION else "fail",
            "detail": {
                "summary_exists": p23_path.exists(),
                "p23_product_acceptance_status": p23_payload.get("product_acceptance_status"),
                "p23_b04_status": p23_payload.get("b04_status_after_p23"),
            },
            "checked_at": now,
        }
    ]


def protocol_rows() -> list[dict[str, Any]]:
    now = utc_now_iso()
    return [
        {
            "protocol_id": "p24_protocol_real_reviewer_identity",
            "protocol_group": "human_reviewer",
            "requirement": "Every acceptance action must include a named real reviewer role.",
            "pass_condition": "reviewer_role is one of the approved human roles and action_source is not automation.",
            "evidence_needed": ["reviewer_role", "action_source", "session_id", "timestamp"],
            "status": "active",
            "created_at": now,
        },
        {
            "protocol_id": "p24_protocol_deliverable_accept_reject",
            "protocol_group": "deliverable_decision",
            "requirement": "At least one deliverable must be accepted or rejected with rationale.",
            "pass_condition": "decision_status is accepted or rejected and references deliverable/artifact ids.",
            "evidence_needed": ["decision_status", "deliverable_ref", "review_comment", "artifact_ref_id"],
            "status": "active",
            "created_at": now,
        },
        {
            "protocol_id": "p24_protocol_defect_closeout",
            "protocol_group": "defect_closure",
            "requirement": "Reviewer-raised defects must be repaired, reproduced as regression cases, or converted to typed gaps.",
            "pass_condition": "every defect row has closeout status repaired, regression_covered, or typed_gap_accepted.",
            "evidence_needed": ["defect_id", "owner", "repair_ref", "regression_case_id", "typed_gap_id"],
            "status": "active",
            "created_at": now,
        },
        {
            "protocol_id": "p24_protocol_browser_visual_acceptance",
            "protocol_group": "browser_e2e",
            "requirement": "Workbench must be opened in a real browser and screenshot evidence must be retained.",
            "pass_condition": "desktop and mobile screenshots exist and key workflow labels are visible.",
            "evidence_needed": ["desktop_screenshot", "mobile_screenshot", "browser_api_rows"],
            "status": "active",
            "created_at": now,
        },
        {
            "protocol_id": "p24_protocol_no_automation_promotion",
            "protocol_group": "release_boundary",
            "requirement": "Automation probes may prove routing but must not close B04.",
            "pass_condition": "automation reviewer_role is excluded from accepted human evidence.",
            "evidence_needed": ["reviewer_role_policy", "P21_B04_status"],
            "status": "active",
            "created_at": now,
        },
    ]


def human_evidence_requirement_rows() -> list[dict[str, Any]]:
    now = utc_now_iso()
    return [
        {
            "requirement_id": "p24_human_session_trace",
            "evidence_type": "reviewer_session",
            "requirement": "A real reviewer completes a Workbench task review session.",
            "current_status": "pending_real_human_review",
            "required_for_b04_close": 1,
            "evidence_needed": ["session_id", "reviewer_role", "started_at", "ended_at", "task_id", "case_id"],
            "created_at": now,
        },
        {
            "requirement_id": "p24_human_deliverable_decision",
            "evidence_type": "deliverable_acceptance",
            "requirement": "A deliverable is accepted or rejected with a reason.",
            "current_status": "pending_real_human_review",
            "required_for_b04_close": 1,
            "evidence_needed": ["decision_status", "deliverable_ref", "review_comment", "artifact_ref_id"],
            "created_at": now,
        },
        {
            "requirement_id": "p24_human_defect_closeout",
            "evidence_type": "defect_closeout",
            "requirement": "All reviewer defects are closed by repair, regression coverage, or typed-gap acceptance.",
            "current_status": "pending_real_human_review",
            "required_for_b04_close": 1,
            "evidence_needed": ["defect_id", "closeout_status", "repair_ref_or_regression_ref"],
            "created_at": now,
        },
        {
            "requirement_id": "p24_human_visual_acceptance",
            "evidence_type": "visual_acceptance",
            "requirement": "A reviewer confirms browser readability/usability after automated screenshots.",
            "current_status": "pending_real_human_review",
            "required_for_b04_close": 1,
            "evidence_needed": ["browser_screenshot_refs", "reviewer_decision", "visual_defect_rows"],
            "created_at": now,
        },
        {
            "requirement_id": "p24_human_trace_replay",
            "evidence_type": "audit_replay",
            "requirement": "Reviewer can trace final answer back to Workpaper, ClaimCards, gaps and artifacts.",
            "current_status": "pending_real_human_review",
            "required_for_b04_close": 1,
            "evidence_needed": ["task_id", "artifact_ref_ids", "trace_or_sql_refs", "reviewer_confirmation"],
            "created_at": now,
        },
    ]


def defect_closeout_requirement_rows(root: Path) -> list[dict[str, Any]]:
    paths = default_p24_paths(root)
    rows: list[dict[str, Any]] = []
    now = utc_now_iso()
    if not paths.db_path.exists():
        return rows
    with _connect(paths.db_path) as conn:
        if _table_exists(conn, "live_defect_triage_records_p19"):
            for row in conn.execute(
                """
                select triage_id, case_id, triage_decision, severity, owner, status, payload_json
                from live_defect_triage_records_p19
                order by triage_id
                """
            ).fetchall():
                rows.append(
                    {
                        "closeout_id": f"p24_closeout_{row['triage_id']}",
                        "source_table": "live_defect_triage_records_p19",
                        "source_id": row["triage_id"],
                        "case_id": row["case_id"],
                        "defect_type": row["triage_decision"],
                        "source_status": row["status"],
                        "required_closeout": "repair_ref_or_regression_case_or_typed_gap_decision",
                        "current_status": "pending_real_human_closeout",
                        "detail": {"severity": row["severity"], "owner": row["owner"], "payload_json": row["payload_json"]},
                        "created_at": now,
                    }
                )
        if not rows and _table_exists(conn, "pilot_defect_promotions_p18"):
            for row in conn.execute(
                """
                select promotion_id, case_id, defect_type, promotion_status, regression_case_id, blocker_status, payload_json
                from pilot_defect_promotions_p18
                order by promotion_id
                """
            ).fetchall():
                rows.append(
                    {
                        "closeout_id": f"p24_closeout_{row['promotion_id']}",
                        "source_table": "pilot_defect_promotions_p18",
                        "source_id": row["promotion_id"],
                        "case_id": row["case_id"],
                        "defect_type": row["defect_type"],
                        "source_status": row["promotion_status"],
                        "required_closeout": "real_reviewer_accepts_regression_or_typed_gap",
                        "current_status": "pending_real_human_closeout",
                        "detail": {
                            "regression_case_id": row["regression_case_id"],
                            "blocker_status": row["blocker_status"],
                            "payload_json": row["payload_json"],
                        },
                        "created_at": now,
                    }
                )
    return rows


def acceptance_decision_rows() -> list[dict[str, Any]]:
    return [
        {
            "decision_id": "p24_real_human_acceptance_decision_required",
            "reviewer_role": "pending_real_human_reviewer",
            "decision_scope": "workbench_product_acceptance",
            "decision_status": "pending_real_human_review",
            "deliverable_ref": "",
            "defect_closeout_status": "pending_real_human_closeout",
            "evidence": {
                "accepted_human_roles": sorted(P24_REAL_HUMAN_REVIEWER_ROLES),
                "automation_roles_excluded": ["automation_e2e"],
            },
            "created_at": utc_now_iso(),
        }
    ]


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http_json(url: str, timeout: float = 2.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = response.read().decode("utf-8", errors="replace")
        return json.loads(payload)


def _wait_for_health(base_url: str, timeout_s: float = 30.0) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last_error = ""
    while time.time() < deadline:
        try:
            payload = _http_json(f"{base_url}/api/health", timeout=2.0)
            if payload.get("status") == "ok":
                return payload
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = repr(exc)
        time.sleep(0.5)
    raise TimeoutError(f"Workbench backend did not become healthy: {last_error}")


def _workbench_api_probe_rows(base_url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path, surface in P24_REQUIRED_BROWSER_APIS:
        http_timeout_s = 15 if surface == "pilot_action_ledger" else 8
        try:
            start = time.time()
            with urllib.request.urlopen(f"{base_url}{path}", timeout=http_timeout_s) as response:
                status_code = response.status
                raw_body = response.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw_body)
            except Exception as exc:
                body = {"error": repr(exc), "raw_text": raw_body[:500]}
            payload = {
                "status": status_code,
                "keys": sorted(str(key) for key in body) if isinstance(body, dict) else [type(body).__name__],
                "body": body,
                "elapsed_ms": int((time.time() - start) * 1000),
            }
        except Exception as exc:
            payload = {"status": 0, "keys": ["error"], "body": {"error": repr(exc)}}
        rows.append(
            {
                "check_id": f"p24_browser_api_{surface}",
                "viewport": "server_http_pre_browser",
                "surface": surface,
                "url": f"{base_url}{path}",
                "status": "pass" if 200 <= int(payload.get("status", 0)) < 300 else "fail",
                "screenshot_path": "",
                "detail": {
                    "status_code": payload.get("status"),
                    "elapsed_ms": payload.get("elapsed_ms"),
                    "response_keys": payload.get("keys", []),
                    "error": payload.get("body", {}).get("error") if isinstance(payload.get("body"), dict) else "",
                    "payload_summary": _summarize_browser_api_payload(surface, payload.get("body", {})),
                    "probe_mode": "server_http_pre_browser_visual",
                },
                "checked_at": utc_now_iso(),
            }
        )
    return rows


def _browser_fail_rows(surface: str, detail: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "check_id": f"p24_browser_{surface}_failed",
            "viewport": "n/a",
            "surface": surface,
            "url": "",
            "status": "fail",
            "screenshot_path": "",
            "detail": detail,
            "checked_at": utc_now_iso(),
        }
    ]


def _resolve_browser_executable(playwright: Any) -> str | None:
    candidates = [
        Path(playwright.chromium.executable_path),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _wait_for_body_labels(page: Any, labels: tuple[str, ...], *, timeout_s: float = 18.0) -> str:
    deadline = time.time() + timeout_s
    body_text = ""
    while time.time() < deadline:
        try:
            body_text = page.locator("body").inner_text(timeout=2000)
            if all(label in body_text for label in labels):
                return body_text
        except Exception:
            body_text = ""
        page.wait_for_timeout(500)
    return body_text


def run_workbench_browser_e2e(root: Path, *, screenshot_dir: Path | None = None, timeout_s: float = 45.0) -> list[dict[str, Any]]:
    """Run a real Playwright browser E2E against the Workbench backend."""

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - depends on optional environment.
        return _browser_fail_rows("playwright_import", {"error": repr(exc)})

    frontend_index = root / "apps" / "workbench" / "frontend" / "dist" / "index.html"
    fallback_index = root / "apps" / "workbench" / "frontend" / "index.html"
    if not frontend_index.exists() and not fallback_index.exists():
        return _browser_fail_rows(
            "frontend_index",
            {
                "dist_index": rel_path(frontend_index, root),
                "fallback_index": rel_path(fallback_index, root),
                "reason": "Workbench cannot be visually tested before a frontend index exists.",
            },
        )

    screenshot_dir = screenshot_dir or default_p24_paths(root).screenshot_dir
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["FINSIGHT_WORKBENCH_REPO_ROOT"] = str(root)
    python_path_parts = [str(root / "src"), str(root)]
    if env.get("PYTHONPATH"):
        python_path_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_path_parts)
    command = [
        sys.executable,
        "-c",
        (
            "import sys, uvicorn; "
            f"sys.path.insert(0, {str(root / 'src')!r}); "
            f"sys.path.insert(0, {str(root)!r}); "
            "uvicorn.run('apps.workbench.backend.app:app', host='127.0.0.1', "
            f"port={port}, log_level='warning')"
        ),
    ]
    process = subprocess.Popen(
        command,
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    rows: list[dict[str, Any]] = []
    console_errors: list[str] = []
    try:
        health = _wait_for_health(base_url, timeout_s=timeout_s)
        rows.append(
            {
                "check_id": "p24_browser_backend_health",
                "viewport": "server",
                "surface": "backend_health",
                "url": f"{base_url}/api/health",
                "status": "pass",
                "screenshot_path": "",
                "detail": {"health": health},
                "checked_at": utc_now_iso(),
            }
        )
        rows.extend(_workbench_api_probe_rows(base_url))
        with sync_playwright() as playwright:
            browser_executable = _resolve_browser_executable(playwright)
            if not browser_executable:
                rows.extend(
                    _browser_fail_rows(
                        "browser_executable",
                        {"reason": "No Playwright Chromium, Chrome, or Edge executable was found."},
                    )
                )
                return rows
            browser = playwright.chromium.launch(headless=True, executable_path=browser_executable)
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 1100})
                page.set_default_timeout(10000)
                page.set_default_navigation_timeout(15000)
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                page.on("pageerror", lambda exc: console_errors.append(str(exc)))
                page.goto(base_url, wait_until="domcontentloaded", timeout=int(timeout_s * 1000))
                page.locator("body").wait_for(timeout=int(timeout_s * 1000))
                for viewport_name, viewport in (
                    ("desktop", {"width": 1440, "height": 1100}),
                    ("mobile", {"width": 390, "height": 900}),
                ):
                    page.set_viewport_size(viewport)
                    page.locator("#r53-r60-workbench").scroll_into_view_if_needed(timeout=int(timeout_s * 1000))
                    body_text = _wait_for_body_labels(page, P24_REQUIRED_BROWSER_LABELS)
                    screenshot_path = screenshot_dir / f"p24_b04_workbench_{viewport_name}.png"
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    missing_labels = [label for label in P24_REQUIRED_BROWSER_LABELS if label not in body_text]
                    rows.append(
                        {
                            "check_id": f"p24_browser_{viewport_name}_page_labels",
                            "viewport": viewport_name,
                            "surface": "workbench_visual_labels",
                            "url": base_url,
                            "status": "pass" if not missing_labels else "fail",
                            "screenshot_path": rel_path(screenshot_path, root),
                            "detail": {
                                "missing_labels": missing_labels,
                                "viewport": viewport,
                                "body_text_length": len(body_text),
                            },
                            "checked_at": utc_now_iso(),
                        }
                    )
                page.close()
            finally:
                browser.close()
        rows.append(
            {
                "check_id": "p24_browser_console_errors",
                "viewport": "all",
                "surface": "browser_console",
                "url": base_url,
                "status": "pass" if not console_errors else "fail",
                "screenshot_path": "",
                "detail": {"console_errors": console_errors[:20]},
                "checked_at": utc_now_iso(),
            }
        )
    except Exception as exc:
        rows.extend(_browser_fail_rows("browser_runtime", {"error": repr(exc), "base_url": base_url}))
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=8)
        stdout_tail = ""
        stderr_tail = ""
        try:
            stdout_tail = (process.stdout.read() if process.stdout else "")[-2000:]
            stderr_tail = (process.stderr.read() if process.stderr else "")[-2000:]
        except Exception:
            pass
        if process.returncode not in (0, None) and not rows:
            rows.extend(_browser_fail_rows("backend_process", {"returncode": process.returncode, "stderr_tail": stderr_tail}))
        elif rows:
            rows[0].setdefault("detail", {})
            if isinstance(rows[0]["detail"], dict):
                rows[0]["detail"].update({"server_returncode": process.returncode, "stdout_tail": stdout_tail, "stderr_tail": stderr_tail})
    return rows


def _summarize_browser_api_payload(surface: str, body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {"body_type": type(body).__name__}
    if surface == "task_center":
        return {"task_count": len(body.get("tasks", []))}
    if surface == "pilot_dashboard":
        return {"case_assignment_count": len(body.get("case_assignments", []))}
    if surface == "pilot_action_ledger":
        return {"live_action_count": len(body.get("live_reviewer_actions", []))}
    if surface == "scope_gate":
        return {"release_decision": body.get("release_decision"), "closeout_level": body.get("closeout_level")}
    return {"keys": sorted(str(key) for key in body)}


def build_gate_rows(
    dep_rows: list[dict[str, Any]],
    browser_rows: list[dict[str, Any]],
    human_rows: list[dict[str, Any]],
    defect_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    now = utc_now_iso()
    dependency_failures = [row for row in dep_rows if row["status"] != "pass"]
    browser_failures = [row for row in browser_rows if row["status"] != "pass"]
    browser_surfaces = {row["surface"] for row in browser_rows if row["status"] == "pass"}
    pending_human = [row for row in human_rows if row["current_status"] != "complete"]
    pending_defects = [row for row in defect_rows if row["current_status"] != "closed"]

    def gate(gate_id: str, group: str, status: str, detail: dict[str, Any]) -> dict[str, Any]:
        return {
            "gate_id": gate_id,
            "gate_name": gate_id,
            "gate_group": group,
            "status": status,
            "detail": detail,
            "created_at": now,
        }

    return [
        gate("p24_p23_dependency_pass", "dependency", "pass" if not dependency_failures else "fail", {"failures": dependency_failures}),
        gate(
            "p24_real_browser_e2e_pass",
            "browser_e2e",
            "pass" if not browser_failures and {"workbench_visual_labels", "backend_health"}.issubset(browser_surfaces) else "fail",
            {"browser_failures": browser_failures, "browser_surfaces": sorted(browser_surfaces)},
        ),
        gate(
            "p24_human_acceptance_evidence_registered",
            "human_acceptance",
            "blocked" if pending_human else "pass",
            {"pending_requirement_count": len(pending_human), "pending_requirements": [row["requirement_id"] for row in pending_human]},
        ),
        gate(
            "p24_defect_closeout_evidence_registered",
            "defect_closeout",
            "blocked" if pending_defects else "pass",
            {"pending_defect_count": len(pending_defects), "source_tables": sorted({row["source_table"] for row in pending_defects})},
        ),
        gate(
            "p24_automation_not_promoted_to_human_acceptance",
            "release_boundary",
            "pass",
            {"automation_roles_excluded": ["automation_e2e"], "accepted_human_roles": sorted(P24_REAL_HUMAN_REVIEWER_ROLES)},
        ),
        gate(
            "p24_b04_remains_open_until_real_acceptance",
            "release_boundary",
            "pass",
            {"b04_status_after_p24": "open_product_acceptance_required"},
        ),
    ]


def persist_p24_rows(
    paths: P24Paths,
    protocol: list[dict[str, Any]],
    browser_rows: list[dict[str, Any]],
    human_rows: list[dict[str, Any]],
    defect_rows: list[dict[str, Any]],
    decision_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    with _connect(paths.db_path) as conn:
        create_p24_schema(conn)
        clear_p24_rows(conn)
        for row in protocol:
            conn.execute(
                """
                insert into product_acceptance_protocol_p24(
                    protocol_id, protocol_group, requirement, pass_condition, evidence_needed_json, status, created_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["protocol_id"],
                    row["protocol_group"],
                    row["requirement"],
                    row["pass_condition"],
                    _json_dumps(row["evidence_needed"]),
                    row["status"],
                    row["created_at"],
                ),
            )
        for row in browser_rows:
            conn.execute(
                """
                insert into product_acceptance_browser_e2e_p24(
                    check_id, viewport, surface, url, status, screenshot_path, detail_json, checked_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["check_id"],
                    row["viewport"],
                    row["surface"],
                    row["url"],
                    row["status"],
                    row.get("screenshot_path", ""),
                    _json_dumps(row.get("detail", {})),
                    row["checked_at"],
                ),
            )
        for row in human_rows:
            conn.execute(
                """
                insert into product_acceptance_human_evidence_requirements_p24(
                    requirement_id, evidence_type, requirement, current_status, required_for_b04_close,
                    evidence_needed_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["requirement_id"],
                    row["evidence_type"],
                    row["requirement"],
                    row["current_status"],
                    int(row["required_for_b04_close"]),
                    _json_dumps(row["evidence_needed"]),
                    row["created_at"],
                ),
            )
        for row in defect_rows:
            conn.execute(
                """
                insert into product_acceptance_defect_closeout_requirements_p24(
                    closeout_id, source_table, source_id, case_id, defect_type, source_status,
                    required_closeout, current_status, detail_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["closeout_id"],
                    row["source_table"],
                    row["source_id"],
                    row["case_id"],
                    row["defect_type"],
                    row["source_status"],
                    row["required_closeout"],
                    row["current_status"],
                    _json_dumps(row["detail"]),
                    row["created_at"],
                ),
            )
        for row in decision_rows:
            conn.execute(
                """
                insert into product_acceptance_decision_records_p24(
                    decision_id, reviewer_role, decision_scope, decision_status, deliverable_ref,
                    defect_closeout_status, evidence_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["decision_id"],
                    row["reviewer_role"],
                    row["decision_scope"],
                    row["decision_status"],
                    row["deliverable_ref"],
                    row["defect_closeout_status"],
                    _json_dumps(row["evidence"]),
                    row["created_at"],
                ),
            )
        for row in gate_rows:
            conn.execute(
                """
                insert into product_acceptance_gate_results_p24(
                    gate_id, gate_name, gate_group, status, detail_json, created_at
                ) values (?, ?, ?, ?, ?, ?)
                """,
                (row["gate_id"], row["gate_name"], row["gate_group"], row["status"], _json_dumps(row["detail"]), row["created_at"]),
            )
        conn.execute(
            """
            insert into product_acceptance_reports_p24(
                report_id, release_decision, closeout_level, product_acceptance_status, b04_status_after_p24,
                browser_e2e_status, human_adoption_status, known_gaps_json, next_actions_json, gate_refs_json,
                payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                P24_REPORT_ID,
                summary["release_decision"],
                summary["closeout_level"],
                summary["product_acceptance_status"],
                summary["b04_status_after_p24"],
                summary["browser_e2e_status"],
                summary["human_adoption_status"],
                _json_dumps(summary["known_gaps"]),
                _json_dumps(summary["next_actions"]),
                _json_dumps([row["gate_id"] for row in gate_rows]),
                _json_dumps({"counts": summary["counts"], "outputs": summary["outputs"]}),
                summary["generated_at"],
            ),
        )


def build_p24_product_acceptance_gate(
    root: Path,
    *,
    browser_rows_override: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    paths = default_p24_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.protocol_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    dep_rows = dependency_rows(root)
    protocol = protocol_rows()
    browser_rows = browser_rows_override if browser_rows_override is not None else run_workbench_browser_e2e(root, screenshot_dir=paths.screenshot_dir)
    human_rows = human_evidence_requirement_rows()
    defect_rows = defect_closeout_requirement_rows(root)
    decision_rows = acceptance_decision_rows()
    gate_rows = build_gate_rows(dep_rows, browser_rows, human_rows, defect_rows)

    dependency_fail_count = sum(1 for row in dep_rows if row["status"] != "pass")
    browser_fail_count = sum(1 for row in browser_rows if row["status"] != "pass")
    gate_fail_count = sum(1 for row in gate_rows if row["status"] == "fail")
    gate_blocked_count = sum(1 for row in gate_rows if row["status"] == "blocked")
    human_pending_count = sum(1 for row in human_rows if row["current_status"] != "complete")
    defect_pending_count = sum(1 for row in defect_rows if row["current_status"] != "closed")
    generated_at = utc_now_iso()
    hard_blocked = dependency_fail_count > 0 or browser_fail_count > 0 or gate_fail_count > 0

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "blocked" if hard_blocked else "pass_with_real_human_acceptance_blocked",
        "release_decision": "P24_b04_product_acceptance_infrastructure_ready_human_review_pending"
        if not hard_blocked
        else "P24_b04_product_acceptance_blocked",
        "closeout_level": "L4_scope_pass_for_product_acceptance_infrastructure_only" if not hard_blocked else "blocked",
        "product_acceptance_status": "pending_real_human_acceptance",
        "b04_status_after_p24": "open_product_acceptance_required",
        "browser_e2e_status": "pass" if browser_fail_count == 0 else "fail",
        "human_adoption_status": "pending_real_human_reviewer_acceptance",
        "full_chain_broad_eval_allowed": False,
        "counts": {
            "dependency_count": len(dep_rows),
            "dependency_fail_count": dependency_fail_count,
            "protocol_count": len(protocol),
            "browser_e2e_count": len(browser_rows),
            "browser_e2e_fail_count": browser_fail_count,
            "human_evidence_requirement_count": len(human_rows),
            "human_evidence_pending_count": human_pending_count,
            "defect_closeout_requirement_count": len(defect_rows),
            "defect_closeout_pending_count": defect_pending_count,
            "decision_record_count": len(decision_rows),
            "gate_count": len(gate_rows),
            "gate_fail_count": gate_fail_count,
            "gate_blocked_count": gate_blocked_count,
        },
        "known_gaps": [
            {
                "gap": "real_human_product_acceptance_not_completed",
                "reason": "B04 requires a real reviewer to accept or reject deliverables and close defects; automation cannot supply this evidence.",
            },
            {
                "gap": "defect_closeout_pending_real_reviewer_decision",
                "reason": "Existing P18/P19 defect/action rows are queued as closeout requirements, not treated as already accepted.",
            },
        ],
        "next_actions": [
            "run at least one real analyst reviewer session through the Workbench browser flow",
            "record accepted/rejected deliverable decisions with reviewer role and artifact refs",
            "close every P24 defect requirement via repair, regression coverage, or typed-gap acceptance",
            "rerun P21; B04 may close only if P24 summary records accepted_by_real_human_review",
        ],
        "outputs": {
            "schema": rel_path(paths.schema_path, root),
            "protocol_rows": rel_path(paths.protocol_rows_path, root),
            "browser_e2e_rows": rel_path(paths.browser_e2e_rows_path, root),
            "human_evidence_rows": rel_path(paths.human_evidence_rows_path, root),
            "defect_closeout_rows": rel_path(paths.defect_closeout_rows_path, root),
            "decision_rows": rel_path(paths.decision_rows_path, root),
            "gate_rows": rel_path(paths.gate_rows_path, root),
            "summary": rel_path(paths.summary_path, root),
            "report": rel_path(paths.report_path, root),
            "runtime_db": rel_path(paths.db_path, root),
            "screenshot_dir": rel_path(paths.screenshot_dir, root),
        },
    }

    persist_p24_rows(paths, protocol, browser_rows, human_rows, defect_rows, decision_rows, gate_rows, summary)
    write_json(paths.schema_path, p24_schema_contract())
    write_jsonl(paths.protocol_rows_path, protocol)
    write_jsonl(paths.browser_e2e_rows_path, browser_rows)
    write_jsonl(paths.human_evidence_rows_path, human_rows)
    write_jsonl(paths.defect_closeout_rows_path, defect_rows)
    write_jsonl(paths.decision_rows_path, decision_rows)
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_p24_report(summary, dep_rows, gate_rows), encoding="utf-8")
    return summary


def render_p24_report(summary: dict[str, Any], dep_rows: list[dict[str, Any]], gate_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# R53-R60 P24 / B04 Product Acceptance Gate",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Release decision: `{summary['release_decision']}`",
        f"- Closeout level: `{summary['closeout_level']}`",
        f"- Product acceptance status: `{summary['product_acceptance_status']}`",
        f"- B04 status after P24: `{summary['b04_status_after_p24']}`",
        f"- Browser E2E status: `{summary['browser_e2e_status']}`",
        f"- Human adoption status: `{summary['human_adoption_status']}`",
        f"- Broad full-chain eval allowed: `{summary['full_chain_broad_eval_allowed']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Dependency Checks", ""])
    for row in dep_rows:
        lines.append(f"- `{row['dependency_id']}`: `{row['status']}`; actual `{row['actual_release_decision']}`")
    lines.extend(["", "## Gates", ""])
    for row in gate_rows:
        lines.append(f"- `{row['gate_id']}`: `{row['status']}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "P24 proves product-acceptance infrastructure and browser E2E readiness. It does not close B04 because no real human reviewer has accepted/rejected deliverables or closed defects.",
            "",
            "P24 证明产品验收底座和浏览器 E2E 路径已具备，但没有真实 reviewer 接受/退回交付物并关闭缺陷前，B04 仍保持打开。",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "SCHEMA_VERSION",
    "P24Paths",
    "build_p24_product_acceptance_gate",
    "create_p24_schema",
    "default_p24_paths",
    "defect_closeout_requirement_rows",
    "p24_schema_contract",
    "run_workbench_browser_e2e",
]
