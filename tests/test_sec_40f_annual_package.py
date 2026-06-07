from __future__ import annotations

from pathlib import Path

from connectors import SecEdgarConnector
from connectors.sec_filing_manifest import collect_sec_filing_manifest


def test_select_40f_annual_package_documents_keeps_core_exhibits() -> None:
    detail_index = {
        "directory": {
            "item": [
                {"name": "issuer-991aif.htm", "sequence": "11"},
                {"name": "issuer-992fs.htm", "sequence": "12"},
                {"name": "issuer-993mda.htm", "sequence": "13"},
                {"name": "issuer-994consent.htm", "sequence": "14"},
            ]
        }
    }
    primary_html = """
<table>
<tr><td><a href="issuer-991aif.htm">99.1</a></td><td>Annual Information Form for the fiscal year ended December 31, 2024</td></tr>
<tr><td><a href="issuer-992fs.htm">99.2</a></td><td>Consolidated Financial Statements including the auditor report</td></tr>
<tr><td><a href="issuer-993mda.htm">99.3</a></td><td>Management's Discussion and Analysis for the year ended December 31, 2024</td></tr>
<tr><td><a href="issuer-994consent.htm">99.4</a></td><td>Consent of Independent Registered Public Accounting Firm</td></tr>
</table>
"""

    selected = SecEdgarConnector._select_40f_annual_package_documents(detail_index, primary_html)

    assert [(row["name"], row["annual_package_role"]) for row in selected] == [
        ("issuer-991aif.htm", "annual_information_form"),
        ("issuer-992fs.htm", "financial_statements"),
        ("issuer-993mda.htm", "mda"),
    ]


def test_select_40f_annual_package_documents_falls_back_to_canadian_exhibit_numbers() -> None:
    detail_index = {
        "directory": {
            "item": [
                {"name": "d869009dex991.htm", "sequence": "11"},
                {"name": "d869009dex992.htm", "sequence": "12"},
                {"name": "d869009dex993.htm", "sequence": "13"},
                {"name": "d869009dex9910.htm", "sequence": "14"},
            ]
        }
    }

    selected = SecEdgarConnector._select_40f_annual_package_documents(detail_index, "")

    assert [(row["name"], row["annual_package_role"]) for row in selected] == [
        ("d869009dex991.htm", "annual_information_form"),
        ("d869009dex992.htm", "financial_statements"),
        ("d869009dex993.htm", "mda"),
    ]


def test_sec_manifest_prefers_metadata_local_html_path_for_40f_package(tmp_path: Path) -> None:
    ticker_dir = tmp_path / "2024" / "uranium" / "CCJ"
    ticker_dir.mkdir(parents=True)
    wrapper_path = ticker_dir / "40-F.html"
    package_path = ticker_dir / "40-F.annual_package.html"
    metadata_path = ticker_dir / "40-F.metadata.json"
    wrapper_path.write_text("<html><body>wrapper</body></html>", encoding="utf-8")
    package_path.write_text("<html><body>annual package</body></html>", encoding="utf-8")
    metadata_path.write_text(
        """{
  "ticker": "CCJ",
  "company": "CAMECO CORP",
  "cik": "0001009001",
  "form_type": "40-F",
  "fiscal_year": 2024,
  "report_date": "2024-12-31",
  "category": "uranium",
  "category_slug": "uranium",
  "local_html_path": "40-F.annual_package.html",
  "local_primary_path": "40-F.html",
  "annual_package_status": "materialized"
}
""",
        encoding="utf-8",
    )

    records = collect_sec_filing_manifest(
        root=tmp_path,
        years=[2024],
        tickers=["CCJ"],
        form_types=["40-F"],
    )

    assert len(records) == 1
    assert Path(records[0].html_path).name == "40-F.annual_package.html"
    assert records[0].period_type == "annual"
    assert records[0].duration_months == 12
