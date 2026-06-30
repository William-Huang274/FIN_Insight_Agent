from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sec_agent.r53_r60_pre_full_chain_blocker_gate import build_p21_pre_full_chain_blocker_gate
from sec_agent.r53_r60_product_acceptance_b04_gate import (
    build_p24_product_acceptance_gate,
    default_p24_paths,
    p24_schema_contract,
)
from sec_agent.r53_r60_product_dogfood_frontend_e2e import build_p23_product_dogfood_frontend_e2e
from test_r53_r60_product_dogfood_frontend_e2e import seed_p23_fixture


def _browser_rows() -> list[dict]:
    rows = [
        ("p24_browser_backend_health", "server", "backend_health"),
        ("p24_browser_desktop_page_labels", "desktop", "workbench_visual_labels"),
        ("p24_browser_mobile_page_labels", "mobile", "workbench_visual_labels"),
        ("p24_browser_api_health", "browser_fetch", "health"),
        ("p24_browser_api_task_center", "browser_fetch", "task_center"),
        ("p24_browser_api_scope_gate", "browser_fetch", "scope_gate"),
        ("p24_browser_api_pilot_dashboard", "browser_fetch", "pilot_dashboard"),
        ("p24_browser_api_pilot_action_ledger", "browser_fetch", "pilot_action_ledger"),
        ("p24_browser_console_errors", "all", "browser_console"),
    ]
    return [
        {
            "check_id": check_id,
            "viewport": viewport,
            "surface": surface,
            "url": "http://127.0.0.1:1",
            "status": "pass",
            "screenshot_path": f"reports/p24/{check_id}.png" if "page_labels" in check_id else "",
            "detail": {"test_override": True},
            "checked_at": "2026-06-30T00:00:00Z",
        }
        for check_id, viewport, surface in rows
    ]


def test_p24_builds_product_acceptance_gate_without_faking_human_acceptance(tmp_path: Path) -> None:
    seed_p23_fixture(tmp_path)
    assert (
        build_p23_product_dogfood_frontend_e2e(tmp_path)["release_decision"]
        == "P23_automated_product_journey_pass_human_dogfood_pending"
    )

    summary = build_p24_product_acceptance_gate(tmp_path, browser_rows_override=_browser_rows())

    assert summary["status"] == "pass_with_real_human_acceptance_blocked"
    assert summary["release_decision"] == "P24_b04_product_acceptance_infrastructure_ready_human_review_pending"
    assert summary["closeout_level"] == "L4_scope_pass_for_product_acceptance_infrastructure_only"
    assert summary["product_acceptance_status"] == "pending_real_human_acceptance"
    assert summary["b04_status_after_p24"] == "open_product_acceptance_required"
    assert summary["browser_e2e_status"] == "pass"
    assert summary["counts"]["browser_e2e_fail_count"] == 0
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["gate_blocked_count"] == 2
    assert summary["counts"]["human_evidence_pending_count"] > 0
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["report"]).exists()


def test_p24_sql_rows_capture_protocol_browser_human_and_defect_closeout(tmp_path: Path) -> None:
    seed_p23_fixture(tmp_path)
    build_p23_product_dogfood_frontend_e2e(tmp_path)
    build_p24_product_acceptance_gate(tmp_path, browser_rows_override=_browser_rows())
    paths = default_p24_paths(tmp_path)

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        protocol_count = conn.execute("select count(*) from product_acceptance_protocol_p24 where status = 'active'").fetchone()[0]
        browser_fail_count = conn.execute("select count(*) from product_acceptance_browser_e2e_p24 where status != 'pass'").fetchone()[0]
        human_pending = conn.execute(
            "select count(*) from product_acceptance_human_evidence_requirements_p24 where current_status = 'pending_real_human_review'"
        ).fetchone()[0]
        defect_pending = conn.execute(
            "select count(*) from product_acceptance_defect_closeout_requirements_p24 where current_status = 'pending_real_human_closeout'"
        ).fetchone()[0]
        report = conn.execute("select * from product_acceptance_reports_p24").fetchone()

    assert set(p24_schema_contract()["tables"]).issubset(tables)
    assert protocol_count >= 5
    assert browser_fail_count == 0
    assert human_pending >= 5
    assert defect_pending >= 1
    assert report["product_acceptance_status"] == "pending_real_human_acceptance"
    assert report["b04_status_after_p24"] == "open_product_acceptance_required"


def test_p21_reads_p24_summary_and_keeps_b04_open_until_real_human_acceptance(tmp_path: Path) -> None:
    seed_p23_fixture(tmp_path)
    build_p23_product_dogfood_frontend_e2e(tmp_path)
    build_p24_product_acceptance_gate(tmp_path, browser_rows_override=_browser_rows())

    summary = build_p21_pre_full_chain_blocker_gate(tmp_path)
    blockers = [
        json.loads(line)
        for line in (tmp_path / summary["outputs"]["blockers"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    b04 = next(row for row in blockers if row["blocker_id"] == "B04-prd-product-acceptance-not-met")

    assert b04["status"] == "open_product_acceptance_required"
    assert b04["observed_evidence"]["p24_product_acceptance_summary"]["exists"] is True
    assert (
        b04["observed_evidence"]["p24_product_acceptance_summary"]["product_acceptance_status"]
        == "pending_real_human_acceptance"
    )


def test_p21_can_close_b04_only_when_p24_summary_records_real_human_acceptance(tmp_path: Path) -> None:
    seed_p23_fixture(tmp_path)
    build_p23_product_dogfood_frontend_e2e(tmp_path)
    p24_summary_path = tmp_path / "data" / "manifests" / "r53_r60_p24_b04_product_acceptance_summary_v0_1.json"
    p24_summary_path.parent.mkdir(parents=True, exist_ok=True)
    p24_summary_path.write_text(
        json.dumps(
            {
                "status": "pass",
                "release_decision": "P24_b04_real_human_product_acceptance_complete",
                "closeout_level": "L4_scope_pass_for_real_human_product_acceptance",
                "product_acceptance_status": "accepted_by_real_human_review",
                "b04_status_after_p24": "closed_by_real_human_product_acceptance",
                "counts": {"human_evidence_pending_count": 0, "defect_closeout_pending_count": 0},
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    summary = build_p21_pre_full_chain_blocker_gate(tmp_path)
    blockers = [
        json.loads(line)
        for line in (tmp_path / summary["outputs"]["blockers"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    b04 = next(row for row in blockers if row["blocker_id"] == "B04-prd-product-acceptance-not-met")

    assert b04["status"] == "closed_by_p24_real_human_product_acceptance"
