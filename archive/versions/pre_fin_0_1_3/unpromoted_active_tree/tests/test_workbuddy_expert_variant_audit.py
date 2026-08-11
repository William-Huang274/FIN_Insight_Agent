from __future__ import annotations

import json
from pathlib import Path

from sec_agent.workbuddy_expert_variant_audit import build_audit, validate_config


DIMENSIONS = [
    "sector_mechanism", "decision_cell_semantics", "evidence_binding", "numeric_integrity",
    "counterevidence_and_gaps", "valuation_or_scenario_method", "artifact_usability",
    "trajectory_planning", "tool_grounding", "repair_reflection", "context_efficiency", "repeatability",
]


def _config() -> dict:
    return {
        "schema_version": "finsight_workbuddy_expert_variant_review_config_v0_1",
        "audit_id": "test",
        "score_dimensions": DIMENSIONS,
        "variants": [{
            "variant_id": "WB-X01B", "base_case_id": "WB-X01", "disposition": "redesign",
            "scores": {value: 2 for value in DIMENSIONS},
            "base": {"task_dir": "base", "html_file": "report.html", "trace_file": "1/trace.json"},
            "variant": {"task_dir": "variant", "html_file": "report.html", "trace_file": "2/trace.json"},
            "ui_configuration": {
                "selected_skill_labels": ["US Stock Analysis", "Unused Skill"],
                "skill_label_aliases": {"US Stock Analysis": "us-stock-analysis"},
            },
        }],
    }


def _write_trace(path: Path, *, skills: list[str], web_count: int) -> None:
    functions = [
        {"type": "function", "name": "Skill", "status": "ok", "toolInput": json.dumps({"skill": skill})}
        for skill in skills
    ]
    functions.extend(
        {"type": "function", "name": "WebSearch", "status": "ok", "toolInput": json.dumps({"query": f"q{index}"})}
        for index in range(web_count)
    )
    functions.append({"type": "function", "name": "Write", "status": "ok", "toolInput": "report.html"})
    payload = {
        "trace": {"status": "ok", "modelInfo": {"callCount": 3, "totalInputTokens": 100, "totalCachedTokens": 50, "totalOutputTokens": 20}},
        "spans": [{"type": "agent", "name": "cli", "status": "ok"}, *functions],
    }
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_validate_config_requires_complete_scores() -> None:
    config = _config()
    assert validate_config(config) == []
    config["variants"][0]["scores"].pop("numeric_integrity")
    assert "expert_variant_scores_missing:WB-X01B" in validate_config(config)


def test_build_audit_keeps_base_and_variant_separate(tmp_path: Path) -> None:
    workbuddy = tmp_path / "WorkBuddy"
    state = tmp_path / ".workbuddy"
    for task, cells in (("base", 1), ("variant", 2)):
        path = workbuddy / task / "report.html"
        path.parent.mkdir(parents=True)
        path.write_text(
            "<h1>Decision</h1><table>" + "".join("<tr><td>$10B</td></tr>" for _ in range(cells)) + "</table>",
            encoding="utf-8",
        )
    _write_trace(state / "traces" / "1" / "trace.json", skills=[], web_count=1)
    _write_trace(state / "traces" / "2" / "trace.json", skills=["us-stock-analysis"], web_count=2)

    audit = build_audit(workbuddy, state, _config())

    assert audit["status"] == "pass"
    assert audit["variant_count"] == 1
    row = audit["variants"][0]
    assert row["base"]["numeric_table_cell_count"] == 1
    assert row["variant"]["numeric_table_cell_count"] == 2
    assert row["delta"]["web_search_count"] == 1
    assert row["direct_pack_promotion_allowed"] is False
    assert "Unused Skill" in row["selected_skill_labels_without_observable_invocation"]
