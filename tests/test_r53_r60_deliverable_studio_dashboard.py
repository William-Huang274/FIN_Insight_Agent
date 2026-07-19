from __future__ import annotations

import sqlite3
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

import apps.workbench.backend.app as workbench_app
from sec_agent.r53_r60_deliverable_studio_dashboard import (
    DEFAULT_TASK_ID,
    REQUIRED_FORMATS,
    build_s7_gate,
    default_s7_paths,
    deliverable_studio_schema_contract,
)
from test_r53_r60_workbench_frontdoor_drilldown import seed_s6_fixture


def test_build_s7_gate_outputs_l4_scope_pass_and_artifacts(tmp_path: Path) -> None:
    seed_s6_fixture(tmp_path)

    summary = build_s7_gate(tmp_path)

    assert summary["release_decision"] == "S7_L4_scope_pass"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["counts"]["gate_count"] == 11
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["customer_ready_editorial_quality_pass"] is True
    assert summary["editorial_acceptance_status"] == "deterministic_customer_ready_pass"
    assert summary["counts"]["render_jobs_s7"] == len(REQUIRED_FORMATS)
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()
    output_root = tmp_path / summary["outputs"]["output_root"]
    assert (output_root / "workpaper_review.md").exists()
    assert (output_root / "workpaper_review.docx").exists()
    assert (output_root / "evidence_appendix.xlsx").exists()
    assert (output_root / "dashboard_projection.json").exists()

    with zipfile.ZipFile(output_root / "workpaper_review.docx") as archive:
        assert "word/document.xml" in archive.namelist()
    with zipfile.ZipFile(output_root / "evidence_appendix.xlsx") as archive:
        assert "xl/worksheets/sheet1.xml" in archive.namelist()
    markdown = (output_root / "workpaper_review.md").read_text(encoding="utf-8")
    assert "## Core Judgment" in markdown
    assert "## Evidence Boundary Appendix" in markdown
    assert "## ClaimCards" not in markdown
    assert "section_intent" not in markdown
    assert "writer_boundary" not in markdown
    assert "claim_card_id" not in markdown


def test_s7_sql_contract_links_plan_surfaces_render_jobs_dashboard_and_artifacts(tmp_path: Path) -> None:
    seed_s6_fixture(tmp_path)
    build_s7_gate(tmp_path)
    db_path = default_s7_paths(tmp_path).db_path
    contract = deliverable_studio_schema_contract()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        plan = conn.execute("select * from deliverable_plans_s7 where task_id = ?", (DEFAULT_TASK_ID,)).fetchone()
        surface_count = conn.execute("select count(*) from narrative_surface_contracts_s7").fetchone()[0]
        render_formats = {
            row["output_format"]
            for row in conn.execute("select output_format from render_jobs_s7 where task_id = ?", (DEFAULT_TASK_ID,)).fetchall()
        }
        dashboard = conn.execute("select * from dashboard_projections_s7 where task_id = ?", (DEFAULT_TASK_ID,)).fetchone()
        composer = conn.execute("select * from composer_permission_gates_s7 where task_id = ?", (DEFAULT_TASK_ID,)).fetchone()
        artifact_ref_count = conn.execute(
            """
            select count(*) from artifact_refs
            where task_id = ?
              and artifact_type in (
                'deliverable_markdown',
                'deliverable_docx',
                'deliverable_excel_appendix',
                'dashboard_projection_json'
              )
            """,
            (DEFAULT_TASK_ID,),
        ).fetchone()[0]
        rendered_event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'deliverable_plan_rendered'",
            (DEFAULT_TASK_ID,),
        ).fetchone()[0]

    assert set(contract["tables"]).issubset(tables)
    assert plan is not None
    assert plan["status"] == "rendered_review_ready"
    assert surface_count == 4
    assert set(REQUIRED_FORMATS).issubset(render_formats)
    assert dashboard is not None and dashboard["status"] == "ready"
    assert composer["status"] == "pass"
    assert int(composer["attempted_forbidden_tool_count"]) == 0
    assert artifact_ref_count == len(REQUIRED_FORMATS)
    assert rendered_event_count == 1


def test_s7_rerun_keeps_current_projection_stable_and_appends_workpaper_event(tmp_path: Path) -> None:
    seed_s6_fixture(tmp_path)
    first = build_s7_gate(tmp_path)
    second = build_s7_gate(tmp_path)
    db_path = default_s7_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        render_count = conn.execute("select count(*) from render_jobs_s7 where task_id = ?", (DEFAULT_TASK_ID,)).fetchone()[0]
        dashboard_count = conn.execute("select count(*) from dashboard_projections_s7 where task_id = ?", (DEFAULT_TASK_ID,)).fetchone()[0]
        rendered_event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'deliverable_plan_rendered'",
            (DEFAULT_TASK_ID,),
        ).fetchone()[0]

    assert first["release_decision"] == "S7_L4_scope_pass"
    assert second["release_decision"] == "S7_L4_scope_pass"
    assert render_count == len(REQUIRED_FORMATS)
    assert dashboard_count == 1
    assert rendered_event_count == 2


def test_s7_backend_api_exposes_deliverables_dashboard_and_render(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_s6_fixture(tmp_path)
    build_s7_gate(tmp_path)
    monkeypatch.setattr(workbench_app, "REPO_ROOT", tmp_path)
    client = TestClient(workbench_app.create_app(store_path=tmp_path / "workbench_api.sqlite"))

    deliverables = client.get(f"/api/r53-r60/tasks/{DEFAULT_TASK_ID}/deliverables")
    assert deliverables.status_code == 200
    assert len(deliverables.json()["render_jobs"]) == len(REQUIRED_FORMATS)

    dashboard = client.get(f"/api/r53-r60/tasks/{DEFAULT_TASK_ID}/dashboard-projection")
    assert dashboard.status_code == 200
    assert dashboard.json()["dashboard_projection"]["status"] == "ready"

    rerender = client.post(f"/api/r53-r60/tasks/{DEFAULT_TASK_ID}/render-deliverables")
    assert rerender.status_code == 200
    assert rerender.json()["release_decision"] == "S7_L4_scope_pass"
