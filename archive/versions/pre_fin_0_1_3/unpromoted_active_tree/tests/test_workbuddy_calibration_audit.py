from __future__ import annotations

import json
from pathlib import Path

from sec_agent.workbuddy_calibration_audit import build_audit, validate_config


def _config(task_dir: str) -> dict:
    case = {
        "task_dir": task_dir,
        "html_file": "report.html",
        "sector": "test_sector",
        "mechanism": "test_mechanism",
        "report_type": "company_comparison",
        "required_surfaces": ["decision_surface"],
    }
    return {
        "schema_version": "finsight_workbuddy_multisector_calibration_cases_v0_1",
        "audit_id": "test",
        "universal_required_surfaces": ["sources", "data_gap", "risk_or_counterevidence", "what_would_change"],
        "surface_patterns": {
            "sources": ["来源"], "data_gap": ["数据缺口"], "risk_or_counterevidence": ["风险"],
            "what_would_change": ["what would change"], "decision_surface": ["decision surface"],
        },
        "cases": [{"case_id": f"WB-S{i:02d}", **case} for i in range(1, 13)],
        "duplicate_or_incomplete_runs": [],
        "spot_checks": [],
    }


def test_validate_config_requires_twelve_unique_cases() -> None:
    payload = _config("task")
    assert validate_config(payload) == []
    payload["cases"][1]["case_id"] = payload["cases"][0]["case_id"]
    assert "workbuddy_case_ids_invalid" in validate_config(payload)


def test_build_audit_reads_html_and_aggregate_trace_without_reasoning(tmp_path: Path) -> None:
    workbuddy = tmp_path / "WorkBuddy"
    state = tmp_path / ".workbuddy"
    payload = _config("task")
    for row in payload["cases"]:
        task = workbuddy / row["task_dir"]
        task.mkdir(parents=True, exist_ok=True)
        (task / "report.html").write_text(
            "<h1>Decision Surface</h1><p>来源 数据缺口 风险 What Would Change</p>"
            "<table></table><a href='https://www.sec.gov/example'>source</a>", encoding="utf-8"
        )
    (state / "sessions").mkdir(parents=True)
    (state / "traces" / "10").mkdir(parents=True)
    (state / "sessions" / "10.json").write_text(
        json.dumps({"pid": 10, "cwd": str(workbuddy / "task")}), encoding="utf-8"
    )
    trace = {
        "trace": {"status": "ok", "duration": 10, "modelInfo": {"callCount": 4, "totalInputTokens": 100, "totalOutputTokens": 20, "totalCachedTokens": 80}},
        "spans": [{"type": "function", "name": "WebSearch", "status": "ok"}] * 4,
    }
    (state / "traces" / "10" / "trace.json").write_text(
        json.dumps(trace) + " " * 100_000, encoding="utf-8"
    )

    audit = build_audit(workbuddy, state, payload)

    assert audit["status"] == "pass"
    assert audit["case_count"] == 12
    assert audit["trace_available_count"] == 12
    assert audit["agentic_loop_observed_count"] == 12
    assert audit["claim_level_lineage_machine_readable_count"] == 0
    assert audit["research_quality_status"] == "not_assessed_comprehensively"
    assert audit["model_boundary"]["maturity_inference_allowed"] is False
    assert audit["pattern_default_disposition"] == "requires_improvement_or_rejection_review"
    assert "complete_claim_correctness_and_claim_to_source_entailment" in audit["audit_coverage"]["not_assessed"]
    assert all(row["trajectory"]["raw_reasoning_ingested"] is False for row in audit["cases"])
