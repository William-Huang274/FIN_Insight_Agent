from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sec_agent.r53_r60_enterprise_workbench_product_surface import build_p15_gate
from sec_agent.r53_r60_internal_reviewer_action_capture import build_p19_gate
from sec_agent.r53_r60_pre_full_chain_blocker_gate import build_p21_pre_full_chain_blocker_gate
from sec_agent.r53_r60_product_dogfood_frontend_e2e import (
    P23_AUTOMATION_COMMENT,
    P23_AUTOMATION_REVIEWER_ROLE,
    build_p23_product_dogfood_frontend_e2e,
    default_p23_paths,
    p23_schema_contract,
)
from test_r53_r60_enterprise_workbench_product_surface import seed_p15_fixture
from test_r53_r60_internal_reviewer_action_capture import seed_p19_fixture


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _write_frontend_fixture(root: Path) -> None:
    main_path = root / "apps" / "workbench" / "frontend" / "vite" / "src" / "main.tsx"
    css_path = root / "apps" / "workbench" / "frontend" / "vite" / "src" / "workbench.css"
    dist_path = root / "apps" / "workbench" / "frontend" / "dist" / "index.html"
    main_path.parent.mkdir(parents=True, exist_ok=True)
    css_path.parent.mkdir(parents=True, exist_ok=True)
    dist_path.parent.mkdir(parents=True, exist_ok=True)
    main_path.write_text(
        """
        function R53R60WorkbenchPanel() {
          return <section id="r53-r60-workbench">Deliverable Studio Review queue Dashboard Projection Product acceptance evidence</section>;
        }
        function R53R60PilotDogfoodPanel() { return null; }
        const taskRoute = "/api/r53-r60/tasks";
        const pilotRoute = "/api/r53-r60/pilot/dashboard";
        const reviewActionRoute = "/review-actions";
        """,
        encoding="utf-8",
    )
    css_path.write_text(
        """
        .pilot-dogfood-panel {}
        .pilot-action-editor {}
        .answer-preview {}
        """,
        encoding="utf-8",
    )
    dist_path.write_text("<!doctype html><div id=\"root\"></div>", encoding="utf-8")


def seed_p23_fixture(root: Path) -> None:
    _write_frontend_fixture(root)
    seed_p15_fixture(root)
    assert build_p15_gate(root)["release_decision"] == "P15_L4_scope_pass_enterprise_workbench_product_surface_ready"
    seed_p19_fixture(root)
    assert build_p19_gate(root)["release_decision"] == "P19_L4_scope_pass_internal_reviewer_action_capture_ready"
    manifest_dir = root / "data" / "manifests"
    _write_json(
        manifest_dir / "r53_r60_p21_pre_full_chain_blocker_summary_v0_1.json",
        {
            "status": "pass",
            "closeout_level": "L4_scope_pass_for_blocker_registration_only",
            "release_decision": "P21_pre_full_chain_blockers_registered_broad_full_chain_blocked",
        },
    )
    _write_json(
        manifest_dir / "r53_r60_p22_source_doc_status_reconciliation_summary_v0_1.json",
        {
            "status": "pass",
            "closeout_level": "L4_scope_pass_for_source_doc_reconciliation_only",
            "release_decision": "P22_source_docs_reconciled_broad_full_chain_still_blocked",
            "source_doc_status": "reconciled",
            "open_source_doc_status_rows": 0,
        },
    )


def test_p23_builds_product_journey_e2e_artifacts_without_claiming_human_acceptance(tmp_path: Path) -> None:
    seed_p23_fixture(tmp_path)

    summary = build_p23_product_dogfood_frontend_e2e(tmp_path)

    assert summary["status"] == "pass_with_human_acceptance_blocked"
    assert summary["release_decision"] == "P23_automated_product_journey_pass_human_dogfood_pending"
    assert summary["closeout_level"] == "L4_scope_pass_for_automated_product_journey_only"
    assert summary["product_acceptance_status"] == "blocked_requires_real_human_review"
    assert summary["b04_status_after_p23"] == "open_product_acceptance_required"
    assert summary["full_chain_broad_eval_allowed"] is False
    assert summary["counts"]["dependency_fail_count"] == 0
    assert summary["counts"]["api_journey_fail_count"] == 0
    assert summary["counts"]["frontend_fail_count"] == 0
    assert summary["counts"]["gate_fail_count"] == 0
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["api_journey_rows"]).exists()
    assert (tmp_path / summary["outputs"]["frontend_check_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["report"]).exists()


def test_p23_sql_rows_capture_api_frontend_and_pending_human_requirements(tmp_path: Path) -> None:
    seed_p23_fixture(tmp_path)
    build_p23_product_dogfood_frontend_e2e(tmp_path)
    paths = default_p23_paths(tmp_path)

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        api_surfaces = {
            row["surface"]
            for row in conn.execute("select surface from product_acceptance_api_journey_checks_p23 where status = 'pass'").fetchall()
        }
        human_statuses = {
            row["current_status"] for row in conn.execute("select current_status from product_acceptance_human_review_requirements_p23").fetchall()
        }
        report = conn.execute("select * from product_acceptance_reports_p23").fetchone()

    assert set(p23_schema_contract()["tables"]).issubset(tables)
    assert {"task_review_action_write", "pilot_review_action_write"}.issubset(api_surfaces)
    assert human_statuses == {"pending_real_human_review"}
    assert report["product_acceptance_status"] == "blocked_requires_real_human_review"
    assert report["b04_status_after_p23"] == "open_product_acceptance_required"


def test_p23_automation_review_actions_are_marked_and_idempotent(tmp_path: Path) -> None:
    seed_p23_fixture(tmp_path)
    first = build_p23_product_dogfood_frontend_e2e(tmp_path)
    second = build_p23_product_dogfood_frontend_e2e(tmp_path)
    paths = default_p23_paths(tmp_path)

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        task_action_count = conn.execute(
            """
            select count(*) from workbench_review_actions_s6
            where reviewer_role = ? and comment = ?
            """,
            (P23_AUTOMATION_REVIEWER_ROLE, P23_AUTOMATION_COMMENT),
        ).fetchone()[0]
        pilot_action_count = conn.execute(
            """
            select count(*) from live_reviewer_actions_p19
            where reviewer_role = ? and comment = ?
            """,
            (P23_AUTOMATION_REVIEWER_ROLE, P23_AUTOMATION_COMMENT),
        ).fetchone()[0]
        api_probe_surfaces = {
            row["surface"]
            for row in conn.execute("select surface from product_acceptance_api_journey_checks_p23 where status = 'pass'").fetchall()
        }

    assert first["counts"]["api_journey_fail_count"] == 0
    assert second["counts"]["api_journey_fail_count"] == 0
    assert task_action_count == 1
    assert pilot_action_count == 1
    assert {"task_review_action_write", "pilot_review_action_write"}.issubset(api_probe_surfaces)


def test_p21_reads_p23_summary_but_keeps_product_acceptance_blocker_open(tmp_path: Path) -> None:
    seed_p23_fixture(tmp_path)
    build_p23_product_dogfood_frontend_e2e(tmp_path)

    summary = build_p21_pre_full_chain_blocker_gate(tmp_path)
    blockers = [
        json.loads(line)
        for line in (tmp_path / summary["outputs"]["blockers"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    b04 = next(row for row in blockers if row["blocker_id"] == "B04-prd-product-acceptance-not-met")

    assert summary["full_chain_broad_eval_allowed"] is False
    assert b04["status"] == "open_product_acceptance_required"
    assert b04["observed_evidence"]["p23_product_acceptance_summary"]["exists"] is True
    assert (
        b04["observed_evidence"]["p23_product_acceptance_summary"]["product_acceptance_status"]
        == "blocked_requires_real_human_review"
    )
