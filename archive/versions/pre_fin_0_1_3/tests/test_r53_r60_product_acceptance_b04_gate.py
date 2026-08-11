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
    append_real_reviewer_acceptance_evidence,
    build_p24_product_acceptance_gate,
    default_p24_paths,
    get_product_acceptance_evidence_status,
    p24_schema_contract,
    validate_real_reviewer_acceptance_evidence,
)
from sec_agent.r53_r60_product_dogfood_frontend_e2e import build_p23_product_dogfood_frontend_e2e
from test_r53_r60_product_dogfood_frontend_e2e import seed_p23_fixture


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


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
        ("p24_browser_api_product_acceptance_evidence", "browser_fetch", "product_acceptance_evidence"),
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


def _write_real_reviewer_acceptance_evidence(root: Path) -> None:
    paths = default_p24_paths(root)
    defect_rows = [
        json.loads(line)
        for line in paths.defect_closeout_rows_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    source_ids = [row["source_id"] for row in defect_rows]
    rows = [
        {
            "evidence_id": "real_review_session_001",
            "evidence_type": "reviewer_session",
            "action_source": "real_human",
            "reviewer_role": "lead_analyst",
            "session_id": "session_real_001",
            "task_id": "task_real_acceptance_001",
            "case_id": "case_real_acceptance_001",
            "status": "complete",
            "started_at": "2026-06-30T00:00:00Z",
            "ended_at": "2026-06-30T00:10:00Z",
        },
        {
            "evidence_id": "real_review_deliverable_001",
            "evidence_type": "deliverable_acceptance",
            "action_source": "real_human",
            "reviewer_role": "lead_analyst",
            "session_id": "session_real_001",
            "decision_status": "accepted",
            "deliverable_ref": "artifact:workpaper_real_acceptance_001",
            "artifact_ref_id": "artifact_ref_real_acceptance_001",
            "review_comment": "Reader-facing workpaper is acceptable for B04 pilot acceptance.",
            "status": "complete",
        },
        {
            "evidence_id": "real_review_defect_closeout_001",
            "evidence_type": "defect_closeout",
            "action_source": "real_human",
            "reviewer_role": "lead_analyst",
            "session_id": "session_real_001",
            "closeout_status": "typed_gap_accepted",
            "covered_source_ids": source_ids,
            "status": "closed",
        },
        {
            "evidence_id": "real_review_visual_001",
            "evidence_type": "visual_acceptance",
            "action_source": "real_human",
            "reviewer_role": "lead_analyst",
            "session_id": "session_real_001",
            "status": "complete",
            "visual_decision": "accepted",
            "browser_screenshot_refs": ["reports/p24/desktop.png", "reports/p24/mobile.png"],
        },
        {
            "evidence_id": "real_review_trace_001",
            "evidence_type": "audit_replay",
            "action_source": "real_human",
            "reviewer_role": "lead_analyst",
            "session_id": "session_real_001",
            "task_id": "task_real_acceptance_001",
            "artifact_ref_ids": ["artifact_ref_real_acceptance_001"],
            "trace_ref": "trace_real_acceptance_001",
            "status": "complete",
        },
    ]
    for row in rows:
        append_real_reviewer_acceptance_evidence(root, row)


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
    build_p24_product_acceptance_gate(tmp_path, browser_rows_override=_browser_rows())
    _write_real_reviewer_acceptance_evidence(tmp_path)
    p24_summary = build_p24_product_acceptance_gate(tmp_path, browser_rows_override=_browser_rows())

    assert p24_summary["status"] == "pass"
    assert p24_summary["release_decision"] == "P24_b04_real_human_product_acceptance_complete"
    assert p24_summary["product_acceptance_status"] == "accepted_by_real_human_review"
    assert p24_summary["b04_status_after_p24"] == "closed_by_real_human_product_acceptance"
    assert p24_summary["counts"]["human_evidence_pending_count"] == 0
    assert p24_summary["counts"]["defect_closeout_pending_count"] == 0
    assert p24_summary["counts"]["accepted_decision_count"] == 1

    summary = build_p21_pre_full_chain_blocker_gate(tmp_path)
    blockers = [
        json.loads(line)
        for line in (tmp_path / summary["outputs"]["blockers"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    b04 = next(row for row in blockers if row["blocker_id"] == "B04-prd-product-acceptance-not-met")

    assert b04["status"] == "closed_by_p24_real_human_product_acceptance"
    assert b04["observed_evidence"]["p24_manifest_acceptance"]["valid"] is True


def test_p24_reviewer_evidence_append_rejects_automation_and_incomplete_rows(tmp_path: Path) -> None:
    valid = validate_real_reviewer_acceptance_evidence(
        {
            "evidence_type": "reviewer_session",
            "action_source": "real_human",
            "reviewer_role": "lead_analyst",
            "session_id": "session_real_001",
            "task_id": "task_real_acceptance_001",
            "case_id": "case_real_acceptance_001",
        }
    )
    assert valid["action_source"] == "real_human"
    assert valid["evidence_id"].startswith("p24_real_reviewer_evidence_")

    try:
        validate_real_reviewer_acceptance_evidence(
            {
                "evidence_type": "reviewer_session",
                "action_source": "automation_e2e",
                "reviewer_role": "lead_analyst",
                "session_id": "session_real_001",
                "task_id": "task_real_acceptance_001",
                "case_id": "case_real_acceptance_001",
            }
        )
    except ValueError as exc:
        assert str(exc) == "action_source_must_be_real_human"
    else:
        raise AssertionError("automation evidence should be rejected")

    try:
        validate_real_reviewer_acceptance_evidence(
            {
                "evidence_type": "deliverable_acceptance",
                "action_source": "real_human",
                "reviewer_role": "lead_analyst",
                "session_id": "session_real_001",
                "decision_status": "accepted",
            }
        )
    except ValueError as exc:
        assert str(exc) == "deliverable_ref_required"
    else:
        raise AssertionError("incomplete deliverable evidence should be rejected")


def test_p24_session_readiness_explains_incomplete_real_reviewer_session(tmp_path: Path) -> None:
    seed_p23_fixture(tmp_path)
    build_p23_product_dogfood_frontend_e2e(tmp_path)
    build_p24_product_acceptance_gate(tmp_path, browser_rows_override=_browser_rows())

    append_real_reviewer_acceptance_evidence(
        tmp_path,
        {
            "evidence_type": "reviewer_session",
            "action_source": "real_human",
            "reviewer_role": "lead_analyst",
            "session_id": "session_incomplete_001",
            "task_id": "task_incomplete_001",
            "case_id": "case_incomplete_001",
            "status": "complete",
        },
    )
    status = get_product_acceptance_evidence_status(tmp_path)

    assert status["counts"]["session_count"] == 1
    assert status["counts"]["ready_session_count"] == 0
    session = status["session_readiness"]["sessions"][0]
    assert session["closeout_status"] == "pending_real_reviewer_completion"
    assert "deliverable_acceptance" in session["missing_evidence_types"]
    assert "defect_closeout" in session["missing_evidence_types"]
    assert status["pending"]["human_requirement_ids"]
    assert isinstance(status["pending"]["human_requirements"][0], dict)


def test_p24_session_readiness_marks_complete_session_ready_for_manifest_rerun(tmp_path: Path) -> None:
    seed_p23_fixture(tmp_path)
    build_p23_product_dogfood_frontend_e2e(tmp_path)
    build_p24_product_acceptance_gate(tmp_path, browser_rows_override=_browser_rows())
    _write_real_reviewer_acceptance_evidence(tmp_path)

    status = get_product_acceptance_evidence_status(tmp_path)
    sessions = status["session_readiness"]["sessions"]

    assert status["counts"]["ready_session_count"] == 1
    assert status["session_readiness"]["status"] == "ready_for_p24_p21_rerun"
    assert sessions[0]["closeout_status"] == "ready_for_p24_p21_rerun"
    assert sessions[0]["missing_evidence_types"] == []
    assert sessions[0]["missing_defect_source_count"] == 0
    assert "rerun P24 and P21" in sessions[0]["next_actions"][-1]


def test_p24_does_not_close_b04_from_cross_session_evidence_mix(tmp_path: Path) -> None:
    seed_p23_fixture(tmp_path)
    build_p23_product_dogfood_frontend_e2e(tmp_path)
    build_p24_product_acceptance_gate(tmp_path, browser_rows_override=_browser_rows())
    paths = default_p24_paths(tmp_path)
    defect_rows = [
        json.loads(line)
        for line in paths.defect_closeout_rows_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    source_ids = [row["source_id"] for row in defect_rows]
    mixed_rows = [
        {
            "evidence_type": "reviewer_session",
            "action_source": "real_human",
            "reviewer_role": "lead_analyst",
            "session_id": "session_mix_a",
            "task_id": "task_mix_a",
            "case_id": "case_mix_a",
            "status": "complete",
        },
        {
            "evidence_type": "deliverable_acceptance",
            "action_source": "real_human",
            "reviewer_role": "lead_analyst",
            "session_id": "session_mix_b",
            "decision_status": "accepted",
            "deliverable_ref": "artifact:mix_b",
            "artifact_ref_id": "artifact_ref_mix_b",
            "review_comment": "This row is valid but belongs to a different incomplete session.",
            "status": "complete",
        },
        {
            "evidence_type": "defect_closeout",
            "action_source": "real_human",
            "reviewer_role": "lead_analyst",
            "session_id": "session_mix_c",
            "closeout_status": "typed_gap_accepted",
            "covered_source_ids": source_ids,
            "status": "closed",
        },
        {
            "evidence_type": "visual_acceptance",
            "action_source": "real_human",
            "reviewer_role": "lead_analyst",
            "session_id": "session_mix_d",
            "status": "complete",
            "visual_decision": "accepted",
        },
        {
            "evidence_type": "audit_replay",
            "action_source": "real_human",
            "reviewer_role": "lead_analyst",
            "session_id": "session_mix_e",
            "task_id": "task_mix_e",
            "artifact_ref_ids": ["artifact_ref_mix_b"],
            "trace_ref": "trace_mix_e",
            "status": "complete",
        },
    ]
    for row in mixed_rows:
        append_real_reviewer_acceptance_evidence(tmp_path, row)

    p24_summary = build_p24_product_acceptance_gate(tmp_path, browser_rows_override=_browser_rows())
    p21_summary = build_p21_pre_full_chain_blocker_gate(tmp_path)
    blockers = [
        json.loads(line)
        for line in (tmp_path / p21_summary["outputs"]["blockers"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    b04 = next(row for row in blockers if row["blocker_id"] == "B04-prd-product-acceptance-not-met")

    assert p24_summary["product_acceptance_status"] == "pending_real_human_acceptance"
    assert p24_summary["b04_status_after_p24"] == "open_product_acceptance_required"
    assert p24_summary["counts"]["accepted_decision_count"] == 0
    assert b04["status"] == "open_product_acceptance_required"
    assert b04["observed_evidence"]["p24_manifest_acceptance"]["valid"] is False


def test_p21_does_not_close_b04_from_summary_only_without_manifest_rows(tmp_path: Path) -> None:
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

    assert b04["status"] == "open_product_acceptance_required"
    assert b04["observed_evidence"]["p24_manifest_acceptance"]["valid"] is False
