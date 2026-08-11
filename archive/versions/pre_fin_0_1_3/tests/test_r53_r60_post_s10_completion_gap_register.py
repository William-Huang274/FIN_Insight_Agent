from __future__ import annotations

import json
import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "engineering"
    / "audit_r53_r60_post_s10_completion_gaps.py"
)
SPEC = importlib.util.spec_from_file_location("audit_r53_r60_post_s10_completion_gaps", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build_register = MODULE.build_register
write_outputs = MODULE.write_outputs


def seed_summary(path: Path, decision: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "pass",
                "release_decision": decision,
                "closeout_level": "L4_scope_pass",
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def seed_all_summaries(root: Path) -> None:
    manifest_dir = root / "data" / "manifests"
    for file_name, decision in [
        ("r53_r60_unified_backlog_summary_v0_1.json", "S0_L4_scope_pass"),
        ("r53_r60_s1_runtime_task_spine_summary_v0_1.json", "S1_L4_scope_pass"),
        ("r53_r60_s2_tool_sandbox_trace_summary_v0_1.json", "S2_L4_scope_pass"),
        ("r53_r60_s3_retrieval_evidence_spine_summary_v0_1.json", "S3_L4_scope_pass"),
        ("r53_r60_s4_context_graph_skill_registry_summary_v0_1.json", "S4_L4_scope_pass"),
        ("r53_r60_s5_workpaper_lead_review_workflow_summary_v0_1.json", "S5_L4_scope_pass"),
        ("r53_r60_s6_workbench_frontdoor_drilldown_summary_v0_1.json", "S6_L4_scope_pass"),
        ("r53_r60_s7_deliverable_studio_dashboard_summary_v0_1.json", "S7_L4_scope_pass"),
        ("r53_r60_s8_secondary_market_capital_feedback_summary_v0_1.json", "S8_L4_scope_pass"),
        ("r53_r60_s9_research_to_quant_lab_summary_v0_1.json", "S9_L4_scope_pass"),
        ("r53_r60_s10_enterprise_release_candidate_summary_v0_1.json", "S10_L4_scope_pass_release_candidate_ready"),
    ]:
        seed_summary(manifest_dir / file_name, decision)


def test_post_s10_register_requires_all_dependency_summaries(tmp_path: Path) -> None:
    seed_all_summaries(tmp_path)

    register = build_register(tmp_path)

    assert register["status"] == "pass"
    assert register["dependency_pass_count"] == 11
    assert register["dependency_count"] == 11
    assert len(register["completed_scope_items"]) >= 10
    assert len(register["production_gaps"]) >= 7
    assert len(register["next_release_slices"]) >= 6


def test_post_s10_register_keeps_production_gap_boundary(tmp_path: Path) -> None:
    seed_all_summaries(tmp_path)

    register = build_register(tmp_path)
    gap_ids = {row["gap_id"] for row in register["production_gaps"]}
    gap_text = json.dumps(register, ensure_ascii=False)

    assert "P-S10-001" in gap_ids
    assert "P-R60-001" in gap_ids
    assert "not claim full production" in register["decision"]
    assert "L4_production" in gap_text
    assert "full production" in gap_text


def test_post_s10_register_writes_json_and_markdown(tmp_path: Path) -> None:
    seed_all_summaries(tmp_path)
    register = build_register(tmp_path)

    outputs = write_outputs(tmp_path, register)

    summary_path = tmp_path / outputs["summary"]
    report_path = tmp_path / outputs["report"]
    assert summary_path.exists()
    assert report_path.exists()
    assert json.loads(summary_path.read_text(encoding="utf-8"))["status"] == "pass"
    report = report_path.read_text(encoding="utf-8")
    assert "Remaining Production Gaps" in report
    assert "Suggested Next Release Slices" in report
