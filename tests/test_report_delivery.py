import io
import zipfile

import pytest

from apps.workbench.backend.application.report_delivery import export_report, chart_png, markdown_blocks, readable_report
from sec_agent.research_foundation.report_charts import ReportChart, bind_report_charts


def sample():
    charts = bind_report_charts([ReportChart.model_validate({"title": "已实现收入对比", "unit": "USD million",
        "points": [{"label": "2025 Q1", "source": {"source_id": "a"}}, {"label": "2026 Q1", "source": {"source_id": "b"}}],
        "interpretation": "同一公司相同季度口径的收入对比，收入增长不代表利润同步增长。"})],
        lambda ref: {"result_state": "numeric_fact", "numeric_fact_authority": True, "value_decimal": "100" if ref == "a" else "120", "unit": "USD million"})
    return {"title": "企业增长质量研究", "narrative_markdown": "## 研究结论\n\n收入增长，需要结合利润与现金流判断其质量。[P01:C1]\n\n## 财务比较\n\n| 指标 | 前期 | 本期 |\n|---|---:|---:|\n| 收入 | 100 | 120 |\n| 利润 | 12 | 13 |\n\n不能把订单直接等同于客户实际使用。\n",
        "citations": {"P01:C1": {"claim": {}, "sources": [{"title": "测试财务来源", "source_url": "https://example.com/financials"}]}}, "charts": charts}


@pytest.mark.parametrize("format", ["md", "pdf", "docx", "pptx"])
def test_four_formats_keep_sources_and_data(format):
    report = sample()
    data, mime = export_report(report, format)
    assert len(data) > 300
    if format == "md":
        assert "https://example.com/financials" in data.decode() and "[P01:C1]" not in data.decode()
    elif format == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        text = "".join(page.extract_text() for page in reader.pages)
        assert "企业增长质量" in text and "120" in text
        assert text.index("研究结论") < text.index("图表与出处")
    else:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if format == "docx":
                text = archive.read("word/document.xml").decode()
                assert "财务比较" in text and "<w:tbl>" in text and "https://example.com/financials" in text
                assert text.index("研究结论") < text.index("<w:drawing>")
            else:
                assert any("ppt/charts/chart" in name for name in archive.namelist())
                assert any("ppt/notesSlides/notesSlide" in name for name in archive.namelist())
                chart_xml = archive.read("ppt/charts/chart1.xml").decode()
                assert 'formatCode="#,##0.##" sourceLinked="0"' in chart_xml
    assert report == sample()  # exports never mutate the original report


def test_plot_is_png_and_markdown_tables_use_mature_parser():
    assert chart_png(sample()["charts"][0]).startswith(b"\x89PNG")
    assert any(kind == "table" for kind, _ in markdown_blocks(sample()["narrative_markdown"]))


def test_scaled_source_values_have_scaled_display_units_without_mutating_authority():
    from apps.workbench.backend.application.report_delivery import chart_display_unit
    from copy import deepcopy
    report = sample()
    report["charts"] = bind_report_charts([ReportChart(title="缩放比较", unit="USD", scale_divisor=1000000,
        points=[{"label": key, "source": {"source_id": key}} for key in ("a", "b")],
        interpretation="来源美元数值展示为百万美元；不重新计算金融指标。")],
        lambda key: {"result_state": "numeric_fact", "numeric_fact_authority": True, "unit": "USD", "value_decimal": "2000000"})
    original = deepcopy(report)
    assert chart_display_unit(report["charts"][0]) == "1,000,000 USD"
    body, _ = export_report(report, "md")
    assert "单位：1,000,000 USD" in body.decode() and "| a |  | 2 |" in body.decode()
    assert report == original


def test_chart_citations_and_task_links_follow_export_surface_without_mutating_report():
    from copy import deepcopy
    report = sample()
    report["charts"][0]["interpretation"] += "依据 [P01:C1]。"
    report["citations"]["P01:C1"]["sources"][0]["source_url"] = "http://localhost:8766/api/v1/research-sessions/11111111-1111-4111-8111-111111111111/attachments/UPLOAD::" + "a"*32
    original = deepcopy(report)
    body, _ = export_report(report, "md", public_base_url="http://127.0.0.1:18795/")
    text = body.decode()
    assert "依据 [1]" in text and "localhost:8766" not in text and "127.0.0.1:18795" in text
    assert report == original


def test_pdf_math_symbols_survive_font_fallback():
    from pypdf import PdfReader
    report = sample()
    report["narrative_markdown"] += "\n收入增长 ⇒ 利润仍需核验；变化 ≈ 20%。"
    body, _ = export_report(report, "pdf")
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(body)).pages)
    assert "⇒" in text and "≈" in text


def test_chart_only_edit_keeps_values_and_rejects_unknown_chart_citations():
    from copy import deepcopy
    from types import SimpleNamespace
    from sec_agent.agent_runtime.report_synthesis_agent import apply_report_edits, ReportTextEdit, report_citations
    report = sample()
    report["narrative_markdown"] += "\n这是合成资格样例，仅用于检查修订是否保留正文和来源绑定。收入比较使用同一公司、相同期间与单位，不能把算术变化解释为已经证明的经营因果。修订图表说明时，既有数据点和原始来源必须保持不变。\n"
    report["charts"][0]["interpretation"] += " 来源 [P01:wrong_alias]。"
    original = deepcopy(report)
    current = apply_report_edits(report, [ReportTextEdit(chart_index=0,old_str="[P01:wrong_alias]",new_str="[P01:C1]")])
    assert current.narrative_markdown == report["narrative_markdown"]
    assert current.charts[0].points[0].source.source_id == "a" and report == original
    artifacts = SimpleNamespace(catalog=lambda:{"papers":[{"paper_id":"P01"}]},
        read_paper=lambda *_:[{"claim_id":"C1","source_ids":[]}], citation_source=lambda *_:None)
    assert set(report_citations(current, artifacts)) == {"P01:C1"}
    broken = current.model_copy(update={"charts":[current.charts[0].model_copy(update={"interpretation":"Source [P01:wrong_alias]"})]})
    with pytest.raises(ValueError,match="wrong_alias"):
        report_citations(broken, artifacts)
    body,_=export_report(report,"md")
    assert "未解析引用：P01:wrong_alias" in body.decode()


@pytest.mark.parametrize("kind", ["bar", "line"])
def test_editable_chart_axis_ids_are_valid_ooxml_and_keep_values(kind):
    from lxml import etree
    report = sample()
    report["charts"][0]["kind"] = kind
    data, _ = export_report(report, "pptx")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        chart = etree.fromstring(archive.read("ppt/charts/chart1.xml"))
    ns = {"c": "http://schemas.openxmlformats.org/drawingml/2006/chart"}
    ids = chart.xpath(".//c:axId/@val | .//c:crossAx/@val", namespaces=ns)
    assert ids and all(0 <= int(value) <= 2**32 - 1 for value in ids)
    definitions = set(chart.xpath(".//c:catAx/c:axId/@val | .//c:valAx/c:axId/@val", namespaces=ns))
    assert len(definitions) == 2 and set(ids) == definitions
    assert chart.xpath(".//c:val//c:numCache/c:pt/c:v/text()", namespaces=ns) == ["100.0", "120.0"]


def test_calculation_and_unsourced_boundary_remain_readable_in_delivery():
    from copy import deepcopy
    report = sample()
    report["narrative_markdown"] += "隐含下半年要求。[P01:C2] 披露边界。[P01:C3]"
    report["citations"].update({
        "P01:C2": {"claim": {"kind": "calculation"}, "sources": [{"source_id": "P01:S2", "calculation": {
            "expression": "annual - first_half", "value_decimal": "120", "result_unit": "USD million",
            "rationale": "达到全年指引所需，不是预测。", "operands": {
                "annual": {"value_decimal": "200", "source_id": "P01:S3", "source_provenance": {
                    "title": "全年指引", "fiscal_period": "FY2027", "source_url": "https://example.com/guidance"}},
                "first_half": {"value_decimal": "80", "source_id": "P01:S4", "source_provenance": {
                    "title": "半年实际", "fiscal_period": "FY2027_H1", "source_url": "https://example.com/actual"}}}}}]},
        "P01:C3": {"claim": {"kind": "boundary", "statement": "未取得客户利用率数据。"}, "sources": []}})
    original = deepcopy(report)
    text, references = readable_report(report)
    joined = "\n".join(references)
    for expected in ("annual - first_half = 120 USD million", "annual = 200", "first_half = 80",
                     "FY2027_H1", "https://example.com/actual", "https://example.com/guidance",
                     "不是预测", "算术验证不等于金融口径验证", "未绑定外部来源", "未取得客户利用率数据"):
        assert expected in joined
    assert "[P01:C2]" not in text
    assert report == original


def test_unassessed_financial_semantics_is_not_a_failed_validation():
    report = sample()
    report["citations"]["P01:C1"]["sources"][0]["calculation"] = {
        "expression": "a / b", "value_decimal": "1", "result_unit": "ratio",
        "arithmetic_verified": True, "financial_semantics_verified": False,
        "operands": {},
    }
    _, references = readable_report(report)
    text = "\n".join(references)
    assert "未验证（计算工具不判断金融口径）" in text
    assert "金融口径校验：未通过" not in text


def test_conversation_flat_calculation_and_derived_fact_keep_readable_provenance():
    report = sample()
    report["citations"] = {
        "NUMFACT::derived": {"sources": [{"ticker": "EXAMPLE", "metric_id": "revenue_yoy_growth", "value_decimal": "25", "unit": "percent", "period_start": "2025-01-01", "period_end": "2025-12-31",
            "formula_trace": {"metric_title": "收入同比变化率", "definition_version": 1, "formula": "(current / prior - 1) * 100", "inputs": [
                {"metric_id": "revenue", "value_decimal": "100", "unit": "USD", "period_start": "2024-01-01", "period_end": "2024-12-31"}]}}]},
        "CALC::flat": {"sources": [{"result_state": "non_authoritative_metric", "arithmetic_verified": True, "expression": "a - b", "value_decimal": "25", "result_unit": "USD", "operands": {}, "rationale": "Synthetic difference."}]}}
    _, references = readable_report(report)
    joined = "\n".join(references)
    assert "收入同比变化率" in joined and "输入 revenue：100 USD" in joined
    assert "a - b = 25 USD" in joined


def test_chart_cannot_invent_values_or_bind_search_preview():
    spec = {"title": "不可伪造图表", "unit": "USD", "points": [{"label": x, "source": {"source_id": x, "literal": "100", "quote": "100"}} for x in ["a", "b"]],
        "interpretation": "不允许拿检索预览当作实际观察来源。"}
    with pytest.raises(ValueError):
        bind_report_charts([ReportChart.model_validate(spec)], lambda _: {"result_state": "retrieval_candidate"})
    with pytest.raises(ValueError, match="differs"):
        bind_report_charts([ReportChart.model_validate(spec)], lambda _: {"result_state": "numeric_fact", "numeric_fact_authority": True, "value_decimal": "50"})


@pytest.mark.parametrize("format", ["md", "pdf", "docx"])
def test_partial_calculation_receipt_does_not_block_report_delivery(format):
    from copy import deepcopy
    report = sample()
    report["citations"]["P01:C1"]["sources"][0].update({
        "result_state": "non_authoritative_metric", "arithmetic_verified": True,
        "value_decimal": "986", "result_unit": "USD million",
    })
    original = deepcopy(report)
    _, references = readable_report(report)
    joined = "\n".join(references)
    assert "计算回执摘要" in joined and "986" in joined
    assert "未包含完整公式与操作数" in joined
    assert "a - b =" not in joined
    data, _ = export_report(report, format)
    assert data and report == original
