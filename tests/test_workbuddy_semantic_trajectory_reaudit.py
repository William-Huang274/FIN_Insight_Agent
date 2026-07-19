from __future__ import annotations

import json
from pathlib import Path

from sec_agent.workbuddy_semantic_trajectory_reaudit import build_reaudit, validate_review_config


DIMENSIONS = [
    "sector_mechanism", "decision_cell_semantics", "evidence_binding", "numeric_integrity",
    "counterevidence_and_gaps", "valuation_or_scenario_method", "artifact_usability",
    "trajectory_planning", "tool_grounding", "repair_reflection", "context_efficiency", "repeatability",
]


def _configs() -> tuple[dict, dict]:
    source_cases = []
    review_cases = []
    for index in range(12):
        case_id = f"WB-X{index:02d}"
        source_cases.append({
            "case_id": case_id, "task_dir": case_id, "html_file": "report.html",
            "sector": "test", "report_type": "company_comparison",
        })
        review_cases.append({
            "case_id": case_id, "disposition": "redesign", "material_defect_severity": "high",
            "scores": {dimension: 2 for dimension in DIMENSIONS},
            "semantic_findings": ["finding"], "trajectory_findings": ["finding"],
            "retain_candidates": [], "improve_or_redesign_candidates": [], "reject_patterns": [],
        })
    source = {"cases": source_cases}
    review = {
        "schema_version": "finsight_workbuddy_semantic_trajectory_review_config_v0_1",
        "audit_id": "test", "required_score_dimensions": DIMENSIONS, "cases": review_cases,
        "pack_candidate_matrix": [{"candidate_id":"x","decision":"redesign_then_pack"}],
        "global_reject_patterns": ["reject"],
    }
    return source, review


def test_validate_review_config_requires_full_scores() -> None:
    _, review = _configs()
    assert validate_review_config(review) == []
    review["cases"][0]["scores"].pop("numeric_integrity")
    assert "semantic_review_scores_missing:WB-X00" in validate_review_config(review)


def test_build_reaudit_separates_structure_from_promotion(tmp_path: Path) -> None:
    source, review = _configs()
    workbuddy = tmp_path / "WorkBuddy"
    state = tmp_path / ".workbuddy"
    (state / "sessions").mkdir(parents=True)
    for index, case in enumerate(source["cases"]):
        task = workbuddy / case["task_dir"]
        task.mkdir(parents=True)
        (task / "report.html").write_text(
            "<h1>Decision</h1><table><tr><td>$10B</td></tr></table><a href='https://example.com'>source</a>",
            encoding="utf-8",
        )
        pid = 100 + index
        (state / "sessions" / f"{pid}.json").write_text(
            json.dumps({"pid": pid, "cwd": str(task)}), encoding="utf-8"
        )
        trace_dir = state / "traces" / str(pid)
        trace_dir.mkdir(parents=True)
        trace = {
            "trace": {"status":"ok","modelInfo":{"callCount":4,"totalInputTokens":100,"totalCachedTokens":80,"totalOutputTokens":10}},
            "spans": [
                {"type":"function","name":"WebSearch","status":"ok","toolInput":json.dumps({"query":"test query"}),"toolOutput":"result"},
                {"type":"function","name":"Write","status":"ok","toolInput":json.dumps({"file_path":"report.html"}),"toolOutput":"ok"},
            ],
        }
        (trace_dir / "trace.json").write_text(json.dumps(trace) + " " * 100_000, encoding="utf-8")

    audit = build_reaudit(workbuddy, state, source, review)

    assert audit["status"] == "pass"
    assert audit["case_count"] == 12
    assert audit["promotion_summary"]["direct_workbuddy_pack_promotion_count"] == 0
    assert audit["cases"][0]["report_metrics"]["direct_numeric_linkage_ratio"] == 0.0
    assert audit["cases"][0]["trajectory_metrics"]["source_open_or_fetch_count"] == 0
    assert audit["review_boundaries"]["raw_reasoning_or_generation_span_reviewed"] is False
