from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_global_public_disclosure_source_plan.py"
SPEC = importlib.util.spec_from_file_location("build_global_public_disclosure_source_plan", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_source_plan_uses_only_global_public_rows_and_annual_like_reports() -> None:
    manifest_rows = [
        {
            "ticker": "005930.KS",
            "issuer_id": "KR-005930",
            "exchange_symbol": "005930",
            "company_name": "Samsung Electronics Co., Ltd.",
            "country": "South Korea",
            "listing_exchange": "KRX",
            "sector": "Information Technology",
            "category": "memory",
            "supply_chain_role": "memory_foundry",
            "priority": "p0",
            "source_family": "global_public_annual_report",
            "disclosure_profile": "kr_dart_business_report",
            "reporting_currency": "KRW",
            "global_public_download_eligible": True,
            "official_sources": [{"kind": "regulator", "url": "https://englishdart.fss.or.kr/"}],
        },
        {
            "ticker": "TSM",
            "company_name": "TAIWAN SEMICONDUCTOR MANUFACTURING CO LTD",
            "global_public_download_eligible": False,
            "disclosure_profile": "sec_edgar_company_filing",
        },
    ]
    profiles = {
        "default_years": [2024],
        "annual_like_report_types": ["annual_report", "business_report"],
        "interim_report_types": ["quarterly_report"],
        "profiles": {
            "kr_dart_business_report": {
                "source_tier": "primary_company_disclosure",
                "source_family": "global_public_annual_report",
                "cache_namespace": "kr_dart",
                "parser_profile": "kr_dart_business_report_v0_1",
                "preferred_source_kinds": ["regulator", "company_ir"],
                "annual_report_types": ["business_report", "annual_report"],
                "interim_report_types": ["quarterly_report"],
                "locator_strategy": "official_locator_then_disclosure_search",
            }
        },
    }

    rows, issues = MODULE.build_global_public_disclosure_source_plan(
        manifest_rows=manifest_rows,
        profiles_config=profiles,
        years=[2024],
        include_interim=False,
    )

    assert issues == []
    assert len(rows) == 2
    assert {row["ticker"] for row in rows} == {"005930.KS"}
    assert {row["report_type"] for row in rows} == {"annual_report", "business_report"}
    assert all(row["source_tier"] == "primary_company_disclosure" for row in rows)
    assert all(row["relationship_edge_candidate_allowed"] is True for row in rows)
    assert rows[0]["source_locator_urls"] == ["https://englishdart.fss.or.kr/"]
    assert "data/raw_private/global_public_disclosures/kr_dart/005930_KS/2024" in rows[0]["cache_dir"].replace("\\", "/")


def test_source_plan_can_include_interim_reports() -> None:
    manifest_rows = [
        {
            "ticker": "1211.HK",
            "issuer_id": "HK-01211",
            "company_name": "BYD Company Limited",
            "country": "China",
            "source_family": "global_public_annual_report",
            "disclosure_profile": "hkex_annual_report",
            "global_public_download_eligible": True,
            "official_sources": [{"kind": "exchange", "url": "https://www.hkexnews.hk/"}],
        }
    ]
    profiles = {
        "annual_like_report_types": ["annual_report"],
        "interim_report_types": ["interim_report"],
        "profiles": {
            "hkex_annual_report": {
                "source_tier": "primary_company_disclosure",
                "source_family": "global_public_annual_report",
                "cache_namespace": "hkex",
                "preferred_source_kinds": ["exchange", "company_ir"],
                "annual_report_types": ["annual_report"],
                "interim_report_types": ["interim_report"],
            }
        },
    }

    rows, issues = MODULE.build_global_public_disclosure_source_plan(
        manifest_rows=manifest_rows,
        profiles_config=profiles,
        years=[2024],
        include_interim=True,
    )

    assert issues == []
    assert {row["report_type"] for row in rows} == {"annual_report", "interim_report"}


def test_source_plan_reports_missing_profile() -> None:
    rows, issues = MODULE.build_global_public_disclosure_source_plan(
        manifest_rows=[
            {
                "ticker": "UNKNOWN.KS",
                "company_name": "Unknown",
                "global_public_download_eligible": True,
                "disclosure_profile": "missing_profile",
                "official_sources": [{"kind": "regulator", "url": "https://example.com/"}],
            }
        ],
        profiles_config={"profiles": {}, "annual_like_report_types": ["annual_report"]},
        years=[2024],
    )

    assert rows == []
    assert issues == [{"type": "missing_profile", "ticker": "UNKNOWN.KS", "disclosure_profile": "missing_profile"}]


def test_source_plan_rejects_deprecated_company_level_target_reports() -> None:
    rows, issues = MODULE.build_global_public_disclosure_source_plan(
        manifest_rows=[
            {
                "ticker": "005930.KS",
                "company_name": "Samsung Electronics Co., Ltd.",
                "global_public_download_eligible": True,
                "disclosure_profile": "kr_dart_business_report",
                "target_reports": ["annual_report"],
                "official_sources": [{"kind": "regulator", "url": "https://englishdart.fss.or.kr/"}],
            }
        ],
        profiles_config={
            "annual_like_report_types": ["annual_report"],
            "profiles": {
                "kr_dart_business_report": {
                    "source_tier": "primary_company_disclosure",
                    "source_family": "global_public_annual_report",
                    "cache_namespace": "kr_dart",
                    "preferred_source_kinds": ["regulator"],
                    "annual_report_types": ["annual_report"],
                }
            },
        },
        years=[2024],
    )

    assert rows == []
    assert issues == [{"type": "deprecated_company_level_target_reports", "ticker": "005930.KS", "disclosure_profile": "kr_dart_business_report"}]
