"""Generate clearly synthetic delivery fixtures; no model calls or real case answers.

Run with --output-directory pointing to an unused qualification directory.
Browser/API and visual QA consume these ordinary files. Not a job runner.
"""
import argparse
import json
from pathlib import Path

from apps.workbench.backend.application.report_delivery import chart_png, export_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_directory.resolve()
    output.mkdir(parents=True, exist_ok=False)
    chart = {"title": "合成图表测试 · 非真实公司数据", "kind": "bar", "unit": "test units",
        "interpretation": "用于视觉识别和导出验收的合成测试，不能引用到Dell报告或当作真实财务数据。",
        "points": [{"label": "2025 Q1", "series": "Test revenue", "value": 100, "source_id": "fixture-a", "provenance": {}},
                   {"label": "2026 Q1", "series": "Test revenue", "value": 120, "source_id": "fixture-b", "provenance": {}}]}
    report = {"title": "交付能力测试 · 合成材料非研究报告", "narrative_markdown":
        "## 测试说明\n\n这是导出和视觉识别测试，数字100和120不是Dell数据，不注入新研究题目。[P01:C1]\n\n"
        "## 表格测试\n\n| 测试指标 | 2025 Q1 | 2026 Q1 |\n|---|---:|---:|\n| Test revenue | 100 | 120 |\n| Test profit | 12 | 13 |\n",
        "citations": {"P01:C1": {"sources": [{"title": "Synthetic QA fixture", "source_url": "https://example.com/synthetic-qa"}]}}, "charts": [chart]}
    (output / "synthetic-chart.png").write_bytes(chart_png(chart))
    (output / "synthetic-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for kind in ("md", "pdf", "docx", "pptx"):
        body, _ = export_report(report, kind, review_status="合成测试，不是财务结论")
        (output / f"synthetic-report.{kind}").write_bytes(body)
    print(json.dumps({"output_directory": str(output), "model_calls": 0, "real_company_data": False}))


if __name__ == "__main__":
    main()
