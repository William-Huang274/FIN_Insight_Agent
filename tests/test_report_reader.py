from copy import deepcopy
import io

from bs4 import BeautifulSoup
from pypdf import PdfReader

from apps.workbench.backend.application.report_delivery import export_report
from tests.test_report_delivery import sample


def test_html_offline_reader_preserves_content_and_resolves_every_citation():
    report = sample()
    report["narrative_markdown"] += "\n\n1. **判断**：增长有条件。[P01:C1]\n"
    before = deepcopy(report)
    data, mime = export_report(report, "html")
    soup = BeautifulSoup(data, "html.parser")
    assert mime == "text/html; charset=utf-8"
    assert soup.find("nav", attrs={"aria-label": "报告目录"})
    assert soup.select("article ol li strong")[0].text == "判断"
    assert soup.select_one("article table")
    assert "[P01:C1]" not in soup.select_one("article").text
    for link in soup.select('a[href^="#"]'):
        assert soup.find(id=link["href"][1:])
    assert soup.select_one("figure img")["src"].startswith("data:image/png;base64,")
    assert soup.select_one("#ref-1 a")["href"] == "https://example.com/financials"
    assert report == before


def test_html_untrusted_markdown_metadata_and_urls_cannot_execute():
    report = sample()
    report["title"] = '<img src=x onerror="alert(1)">'
    report["narrative_markdown"] += '\n<script>alert(1)</script>\n[x](javascript:alert(1))'
    report["citations"]["P01:C1"]["sources"][0]["source_url"] = 'javascript:alert(1)'
    report["citations"]["P01:C1"]["sources"][0]["title"] = '</div><script>alert(2)</script>'
    data, _ = export_report(report, "html")
    soup = BeautifulSoup(data, "html.parser")
    assert not soup.find("script")
    assert not soup.select('[onerror],a[href^="javascript:"]')
    assert soup.find("meta", attrs={"http-equiv": "Content-Security-Policy"})


def test_organization_excerpt_is_escaped_and_keeps_saved_period_unit():
    report = {"title": "Saved organization report", "narrative_markdown": "Finding [C1]",
        "citations": {"C1": {"sources": [{"source_id": "ORG:1", "period": "FY2025", "unit": "USD",
            "text": '<script>saved excerpt</script>', "organization_source": {"execution_id": "saved"}}]}}}
    before = deepcopy(report)
    data, _ = export_report(report, "html")
    soup = BeautifulSoup(data, "html.parser")
    assert soup.select_one("#ref-1 .quote").text == '<script>saved excerpt</script>'
    assert not soup.find("script")
    assert "FY2025" in soup.select_one("#ref-1").text and "USD" in soup.select_one("#ref-1").text
    assert report == before


def test_pdf_keeps_lists_headings_and_readable_source_without_mutating_report():
    report = sample()
    report["narrative_markdown"] += "\n\n1. **第一项**\n2. 第二项\n"
    before = deepcopy(report)
    data, _ = export_report(report, "pdf")
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)
    assert "第一项" in text and "第二项" in text
    assert "测试财务来源" in text and "https://example.com/financials" in text
    assert "[P01:C1]" not in text
    assert report == before


def test_chart_sources_and_safe_downloads_are_independent_of_body_citations():
    report = sample()
    report["charts"][0]["points"][0]["provenance"]["source_url"] = "https://example.com/chart-original"
    data, _ = export_report(report, "html", download_links={
        "下载": "report.pdf", "外部": "https://example.com/report.pdf",
        "不安全": "javascript:alert(1)", "越界": "../secret.pdf"})
    soup = BeautifulSoup(data, "html.parser")
    assert soup.select_one('figure a[href="https://example.com/chart-original"]')
    assert [a["href"] for a in soup.select(".downloads a")] == ["report.pdf", "https://example.com/report.pdf"]
    pdf, _ = export_report(report, "pdf")
    assert "https://example.com/chart-original" in "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)


def test_pdf_retains_flat_calculations_and_unsourced_boundary():
    report = sample()
    report["citations"] = {
        "CALC::flat": {"sources": [{"result_state": "non_authoritative_metric", "arithmetic_verified": True,
            "expression": "a - b", "value_decimal": "25", "result_unit": "USD",
            "operands": {}, "rationale": "两期差额，不是预测。"}]},
        "P01:C2": {"claim": {"statement": "未取得客户利用率数据。"}, "sources": []}}
    data, _ = export_report(report, "pdf")
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)
    assert "a - b = 25 USD" in text and "不是预测" in text and "未取得客户利用率数据" in text
