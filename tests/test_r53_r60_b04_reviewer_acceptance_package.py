from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from sec_agent.r53_r60_b04_reviewer_acceptance_package import (
    build_b04_reviewer_acceptance_package,
    default_p27_paths,
    get_b04_reviewer_acceptance_package,
)
from sec_agent.r53_r60_product_acceptance_b04_gate import default_p24_paths, validate_real_reviewer_acceptance_evidence


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def _seed_p24_inputs(root: Path) -> None:
    paths = default_p24_paths(root)
    _write_json(
        paths.summary_path,
        {
            "schema_version": "r53_r60_p24_b04_product_acceptance_gate_v0_1",
            "status": "pass_with_real_human_acceptance_blocked",
            "b04_status_after_p24": "open_product_acceptance_required",
            "full_chain_broad_eval_allowed": False,
            "counts": {
                "human_evidence_pending_count": 5,
                "defect_closeout_pending_count": 2,
                "real_reviewer_evidence_row_count": 0,
            },
        },
    )
    _write_jsonl(
        paths.human_evidence_rows_path,
        [
            {
                "requirement_id": "p24_human_session_trace",
                "evidence_type": "reviewer_session",
                "current_status": "pending_real_human_review",
                "evidence_needed": ["session_id", "reviewer_role", "task_id", "case_id"],
                "required_for_b04_close": 1,
            },
            {
                "requirement_id": "p24_human_deliverable_decision",
                "evidence_type": "deliverable_acceptance",
                "current_status": "pending_real_human_review",
                "evidence_needed": ["decision_status", "deliverable_ref", "artifact_ref_id", "review_comment"],
                "required_for_b04_close": 1,
            },
            {
                "requirement_id": "p24_human_defect_closeout",
                "evidence_type": "defect_closeout",
                "current_status": "pending_real_human_review",
                "evidence_needed": ["source_id", "closeout_status"],
                "required_for_b04_close": 1,
            },
        ],
    )
    _write_jsonl(
        paths.defect_closeout_rows_path,
        [
            {
                "closeout_id": "p24_closeout_one",
                "source_id": "p19triage_one",
                "case_id": "case_one",
                "defect_type": "confirmed_defect_requires_regression",
                "required_closeout": "repair_ref_or_regression_case_or_typed_gap_decision",
            },
            {
                "closeout_id": "p24_closeout_two",
                "source_id": "p19triage_two",
                "case_id": "case_two",
                "defect_type": "accepted_no_blocker",
                "required_closeout": "repair_ref_or_regression_case_or_typed_gap_decision",
            },
        ],
    )


def _seed_runtime_db(root: Path) -> None:
    db_path = default_p24_paths(root).db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            create table research_tasks (
                task_id text, current_run_id text, case_id text, status text, query_text text, created_at text, updated_at text
            );
            create table artifact_refs (
                artifact_ref_id text, task_id text, run_id text, artifact_type text, uri text, byte_size integer, created_at text
            );
            create table trace_spans (
                span_id text, task_id text, run_id text, actor text, span_kind text, name text, status text, latency_ms integer, created_at text
            );
            """
        )
        conn.execute(
            "insert into research_tasks values (?, ?, ?, ?, ?, ?, ?)",
            ("task_one", "run_one", "case_one", "succeeded", "review me", "2026-07-01T00:00:00Z", "2026-07-01T00:00:00Z"),
        )
        conn.execute(
            "insert into artifact_refs values (?, ?, ?, ?, ?, ?, ?)",
            ("artifact_one", "task_one", "run_one", "deliverable_markdown", "reports/demo.md", 100, "2026-07-01T00:00:00Z"),
        )
        conn.execute(
            "insert into trace_spans values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("span_one", "task_one", "run_one", "research_lead", "node", "lead_review", "pass", 12, "2026-07-01T00:00:00Z"),
        )


def test_b04_reviewer_acceptance_package_is_template_only_and_does_not_close_b04(tmp_path: Path) -> None:
    _seed_p24_inputs(tmp_path)
    _seed_runtime_db(tmp_path)

    summary = build_b04_reviewer_acceptance_package(tmp_path, workbench_url="http://127.0.0.1:18080")
    paths = default_p27_paths(tmp_path)

    assert summary["package_status"] == "ready_for_real_reviewer_execution"
    assert summary["b04_status_after_p27"] == "open_product_acceptance_required"
    assert summary["does_not_close_b04"] is True
    assert summary["full_chain_broad_eval_allowed"] is False
    assert summary["counts"]["review_step_count"] == 3
    assert summary["counts"]["evidence_template_count"] == 5
    assert summary["counts"]["reviewer_candidate_ref_count"] == 3
    runtime_package = get_b04_reviewer_acceptance_package(tmp_path)
    assert runtime_package["package_exists"] is True
    assert runtime_package["package"]["package_status"] == "ready_for_real_reviewer_execution"
    assert len(runtime_package["step_rows"]) == 3
    assert len(runtime_package["evidence_template_rows"]) == 5
    assert len(runtime_package["reviewer_candidate_rows"]) == 3
    assert paths.package_path.exists()
    assert paths.step_rows_path.exists()
    assert paths.evidence_template_rows_path.exists()
    assert paths.reviewer_candidate_rows_path.exists()
    assert paths.report_path.exists()
    assert not default_p24_paths(tmp_path).reviewer_evidence_input_path.exists()

    templates = [json.loads(line) for line in paths.evidence_template_rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert all(row["template_only"] is True for row in templates)
    assert all(row["not_reviewer_evidence"] is True for row in templates)
    with pytest.raises(ValueError):
        validate_real_reviewer_acceptance_evidence(templates[0])

    report_text = paths.report_path.read_text(encoding="utf-8")
    assert "P27 只生成真实人工验收的执行包" in report_text
    assert "B04 只有在真实 reviewer 提交完整 evidence 后" in report_text
