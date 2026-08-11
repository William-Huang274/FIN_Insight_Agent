from __future__ import annotations

from pathlib import Path

from sec_agent.p35_ai_infra_supervisor_dogfood import (
    build_ai_infra_decision_surface_framework,
    build_current_system_gap_audit,
    summarize_workbuddy_samples,
)


def test_decision_surface_framework_has_five_segments_and_full_cell_grid() -> None:
    framework = build_ai_infra_decision_surface_framework()

    assert framework["schema_version"] == "fin_insight_p35_ai_infra_decision_surface_framework_v0_1"
    assert [row["segment_id"] for row in framework["chain_segments"]] == [
        "accelerator",
        "server_oem",
        "foundry_packaging",
        "hbm",
        "semicap",
    ]
    assert len(framework["decision_dimensions"]) >= 10
    assert len(framework["decision_surface_cells"]) == (
        len(framework["chain_segments"]) * len(framework["decision_dimensions"])
    )
    assert any(row["dimension_id"] == "source_grade" for row in framework["decision_dimensions"])
    assert any(row["dimension_id"] == "numeric_sanity" for row in framework["decision_dimensions"])


def test_gap_audit_flags_current_p34_scope_mismatch() -> None:
    framework = build_ai_infra_decision_surface_framework()
    audit = build_current_system_gap_audit(framework=framework)

    assert audit["schema_version"] == "fin_insight_p35_ai_infra_current_system_gap_audit_v0_1"
    assert audit["scope"]["paid_llm_run"] is False
    assert audit["scope"]["full_chain_run"] is False
    assert audit["missing_decision_surface_cells"]
    root_cause_ids = {row["root_cause_id"] for row in audit["root_causes"]}
    assert "p35_case_scope_mismatch" in root_cause_ids
    assert "p35_source_hunter_loop_absent" in root_cause_ids


def test_workbuddy_sample_summary_parses_html_without_external_dependencies(tmp_path: Path) -> None:
    folder = tmp_path / "2026-07-09-00-00-00"
    folder.mkdir()
    (folder / "sample.html").write_text(
        """
        <html>
          <head><title>Sample Report</title></head>
          <body>
            <h1>AI Infra</h1>
            <h2>核心结论</h2>
            <h2>风险矩阵</h2>
            <table><tr><td>official 来源 估算</td></tr></table>
            <script>echarts.init(document.createElement('div'))</script>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    samples = summarize_workbuddy_samples(tmp_path)

    assert len(samples) == 1
    assert samples[0]["title"] == "Sample Report"
    assert samples[0]["h1"] == ["AI Infra"]
    assert samples[0]["table_count"] == 1
    assert samples[0]["echarts_count"] == 1
    assert samples[0]["contains_tldr"] is True
    assert samples[0]["contains_risk_matrix"] is True
    assert samples[0]["contains_source_boundary"] is True
