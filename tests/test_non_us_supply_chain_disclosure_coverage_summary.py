from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_non_us_supply_chain_disclosure_coverage_summary.py"
SPEC = importlib.util.spec_from_file_location("build_non_us_supply_chain_disclosure_coverage_summary", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_non_us_coverage_rows_merge_downloaded_rows_and_gaps() -> None:
    source_plan = [
        {
            "plan_id": "GLOBALDISC::005930::KR::2025::BUSINESS_REPORT",
            "ticker": "005930.KS",
            "company_name": "Samsung Electronics Co., Ltd.",
            "country": "South Korea",
            "listing_exchange": "KRX",
            "exchange_symbol": "005930",
            "disclosure_profile": "kr_dart_business_report",
            "fiscal_year": 2025,
            "report_type": "business_report",
            "source_family": "global_public_annual_report",
            "source_tier": "primary_company_disclosure",
            "source_boundary": "primary_company_disclosure_not_news_lead",
            "relationship_edge_candidate_allowed": True,
        },
        {
            "plan_id": "GLOBALDISC::8035::EDINET::2025::ANNUAL_SECURITIES_REPORT",
            "ticker": "8035.T",
            "company_name": "Tokyo Electron Limited",
            "country": "Japan",
            "listing_exchange": "TSE",
            "exchange_symbol": "8035",
            "disclosure_profile": "jp_edinet_annual_securities_report",
            "fiscal_year": 2025,
            "report_type": "annual_securities_report",
            "source_family": "global_public_annual_report",
            "source_tier": "primary_company_disclosure",
            "source_boundary": "primary_company_disclosure_not_news_lead",
            "relationship_edge_candidate_allowed": True,
        },
    ]
    profiles = {
        "profiles": {
            "kr_dart_business_report": {
                "locator_strategy": "official_locator_then_disclosure_search",
                "download_implementation_status": "implemented_dart_openapi_document_download",
                "parser_implementation_status": "implemented_cleaned_text_staging_table_parser_pending",
            },
            "jp_edinet_annual_securities_report": {
                "locator_strategy": "edinet_document_search",
                "download_implementation_status": "blocked_requires_official_api_key",
                "download_blocker": "EDINET API key required.",
                "api_key_env": "EDINET_API_KEY",
                "parser_implementation_status": "blocked_until_profile_downloader_pass",
            },
        }
    }
    downloads = [
        {
            "plan_id": "GLOBALDISC::005930::KR::2025::BUSINESS_REPORT",
            "document_downloaded": True,
            "document_path": "data/raw_private/global_public_disclosures/kr_dart/005930/2025.zip",
            "document_url": "https://opendart.fss.or.kr/api/document.xml?crtfc_key=REDACTED",
            "download_status": "document_downloaded_cleaned",
            "downloaded_bytes": 123,
            "sha256": "abc",
            "cleaned_text_path": "data/processed_private/public_sources/global_public_disclosures/kr_dart/005930/2025.txt",
            "cleaned_text_char_count": 456,
            "cleaned_text_status": "cleaned_text_written",
            "parser_status": "cleaned_text_staged_table_parser_pending",
        }
    ]

    rows = MODULE.build_coverage_rows(source_plan=source_plan, profiles_config=profiles, download_rows=downloads)
    summary = MODULE.summarize_coverage_rows(
        coverage_rows=rows,
        output=Path("coverage.jsonl"),
        summary_output=Path("summary.json"),
        download_paths=[Path("downloads.jsonl")],
    )

    assert [row["coverage_status"] for row in rows] == ["downloaded_cleaned", "gap"]
    assert rows[0]["cleaned_text_char_count"] == 456
    assert rows[1]["gap_type"] == "edinet_api_key_invalid_or_key_backed_smoke_failed"
    assert summary["status"] == "pass_with_gaps"
    assert summary["downloaded_row_count"] == 1
    assert summary["gap_row_count"] == 1
    assert summary["gap_type_counts"] == {"edinet_api_key_invalid_or_key_backed_smoke_failed": 1}


def test_infer_gap_for_portal_profile_pending() -> None:
    gap_type, detail = MODULE.infer_gap(
        profile_name="tw_mops_annual_report",
        profile={"download_implementation_status": "profile_specific_scaffold_pending", "download_blocker": "MOPS params pending."},
    )

    assert gap_type == "profile_specific_portal_downloader_pending"
    assert detail == "MOPS params pending."
