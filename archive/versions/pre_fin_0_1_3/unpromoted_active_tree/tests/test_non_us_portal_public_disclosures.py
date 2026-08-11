from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "download_non_us_portal_public_disclosures.py"
SPEC = importlib.util.spec_from_file_location("download_non_us_portal_public_disclosures", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_parse_hkex_jsonp_stock_info() -> None:
    payload = MODULE.parse_jsonp('callback({"stockInfo":[{"stockId":2696,"code":"01211","name":"BYD COMPANY"}]});')

    assert payload["stockInfo"][0]["stockId"] == 2696
    assert payload["stockInfo"][0]["code"] == "01211"


def test_select_hkex_annual_report_rejects_interim() -> None:
    selected = MODULE.select_hkex_annual_report(
        [
            {"TITLE": "2024 Interim Report", "SHORT_TEXT": "Financial Statements/ESG Information - [Interim Report]", "DATE_TIME": "01/09/2024 12:00"},
            {"TITLE": "Annual Report 2024 (Printed version)", "SHORT_TEXT": "Financial Statements/ESG Information - [Annual Report]", "DATE_TIME": "30/04/2025 12:00"},
            {"TITLE": "2024 Annual Report", "SHORT_TEXT": "Financial Statements/ESG Information - [Annual Report]", "DATE_TIME": "28/03/2025 21:00"},
        ],
        fiscal_year=2024,
    )

    assert selected is not None
    assert selected["TITLE"] == "2024 Annual Report"


def test_select_cninfo_annual_report_rejects_summary() -> None:
    selected = MODULE.select_cninfo_annual_report(
        [
            {"announcementTitle": "2024年年度报告摘要", "announcementTime": 1741968000000},
            {"announcementTitle": "2024年年度报告", "announcementTime": 1741968000000},
        ],
        fiscal_year=2024,
    )

    assert selected is not None
    assert selected["announcementTitle"] == "2024年年度报告"


def test_select_mops_annual_report_filename_prefers_f04_matching_fiscal_year() -> None:
    selected = MODULE.select_mops_annual_report_filename(
        [
            "2024_2308_20250529F04.pdf",
            "2024_2308_20250529F01.pdf",
            "2023_2308_20240530F04.pdf",
        ],
        stock_code="2308",
        fiscal_year=2024,
    )

    assert selected == "2024_2308_20250529F04.pdf"


def test_extract_mops_pdf_href_from_step9_response() -> None:
    href = MODULE.extract_pdf_href("<html><a href='/pdf/2024_2308_20250529F04_20260611_123456.pdf'>download</a></html>")

    assert href == "/pdf/2024_2308_20250529F04_20260611_123456.pdf"


def test_base_task_row_remaps_cache_root(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    processed_root = tmp_path / "processed"
    MODULE.base.configure_disclosure_storage(cache_root=raw_root, processed_root=processed_root)
    try:
        row = MODULE.base_task_row(
            {
                "plan_id": "GLOBALDISC::1211_HK::HKEX::2024::ANNUAL_REPORT",
                "ticker": "1211.HK",
                "company_name": "BYD Company Limited",
                "disclosure_profile": "hkex_annual_report",
                "fiscal_year": 2024,
                "report_type": "annual_report",
                "source_locator_urls": ["https://www.hkexnews.hk/"],
                "cache_dir": "data/raw_private/global_public_disclosures/hkex/1211_HK/2024/ANNUAL_REPORT",
            }
        )

        assert Path(row["cache_dir"]) == raw_root / "hkex" / "1211_HK" / "2024" / "ANNUAL_REPORT"
    finally:
        MODULE.base.configure_disclosure_storage(cache_root=None, processed_root=None)
