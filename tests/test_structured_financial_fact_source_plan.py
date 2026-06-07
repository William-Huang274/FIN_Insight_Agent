from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_structured_financial_fact_source_plan.py"
SPEC = importlib.util.spec_from_file_location("build_structured_financial_fact_source_plan", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_structured_fact_plan_builds_sec_companyfacts_and_submissions_rows() -> None:
    rows, issues = MODULE.build_structured_financial_fact_source_plan(
        manifest_rows=[
            {
                "ticker": "MSFT",
                "issuer_id": "0000789019",
                "cik": "0000789019",
                "company_name": "Microsoft Corporation",
                "sec_download_eligible": True,
            }
        ],
        config={
            "sources": {
                "sec_companyfacts": {
                    "integration_mode": "new_sec_api_download",
                    "source_family": "sec_companyfacts_structured_fact",
                    "endpoint_template": "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json",
                },
                "sec_submissions": {
                    "integration_mode": "new_sec_api_download",
                    "source_family": "sec_submissions_metadata",
                    "endpoint_template": "https://data.sec.gov/submissions/CIK{cik10}.json",
                },
            }
        },
        years=[2024],
    )

    assert issues == []
    assert len(rows) == 2
    assert {row["fact_source"] for row in rows} == {"sec_companyfacts", "sec_submissions"}
    assert all(row["cik10"] == "0000789019" for row in rows)
    assert any(row["source_url"].endswith("/CIK0000789019.json") for row in rows)


def test_structured_fact_plan_builds_non_us_derived_report_rows() -> None:
    rows, issues = MODULE.build_structured_financial_fact_source_plan(
        manifest_rows=[
            {
                "ticker": "005930.KS",
                "issuer_id": "KR-005930",
                "company_name": "Samsung Electronics Co., Ltd.",
                "global_public_download_eligible": True,
                "disclosure_profile": "kr_dart_business_report",
            }
        ],
        config={
            "sources": {
                "global_public_financial_statement_tables": {
                    "integration_mode": "derive_from_downloaded_official_disclosure",
                    "source_family": "global_public_structured_financial_fact",
                    "dependency": "global_public_official_report_document",
                    "promotion_blocker_until": ["global_public_parser_profile_pass"],
                }
            }
        },
        years=[2023, 2024],
    )

    assert issues == []
    assert len(rows) == 2
    assert {row["fiscal_year"] for row in rows} == {2023, 2024}
    assert all(row["fact_source"] == "global_public_financial_statement_tables" for row in rows)
    assert all(row["document_status"] == "blocked_until_official_report_parser_pass" for row in rows)
    assert all("global_public_parser_profile_pass" in row["promotion_blocker_until"] for row in rows)


def test_structured_fact_plan_reports_sec_company_missing_cik() -> None:
    rows, issues = MODULE.build_structured_financial_fact_source_plan(
        manifest_rows=[{"ticker": "BAD", "company_name": "Bad CIK Inc.", "sec_download_eligible": True}],
        config={"sources": {}},
        years=[2024],
    )

    assert rows == []
    assert issues == [{"type": "missing_cik_for_sec_structured_fact", "ticker": "BAD", "company_name": "Bad CIK Inc."}]
