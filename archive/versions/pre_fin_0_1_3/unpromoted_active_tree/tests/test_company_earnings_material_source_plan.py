from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_company_earnings_material_source_plan.py"
SPEC = importlib.util.spec_from_file_location("build_company_earnings_material_source_plan", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_company_earnings_plan_reuses_sec_8k_for_us_company() -> None:
    rows, issues = MODULE.build_company_earnings_material_source_plan(
        manifest_rows=[
            {
                "ticker": "MSFT",
                "issuer_id": "0000789019",
                "cik": "0000789019",
                "company_name": "Microsoft Corporation",
                "sec_download_eligible": True,
            }
        ],
        profiles_config={
            "us_sec_reuse": {
                "integration_mode": "reuse_existing_sec_8k_earnings_pipeline",
                "source_family": "sec_8k_earnings_release",
                "source_tier": "company_authored_unaudited_sec_filing",
                "existing_scripts": ["scripts/data_sec/download_sec_8k_earnings.py"],
            },
            "non_us_company_ir": {"material_types": {}},
        },
        years=[2025],
        fiscal_periods=["FY"],
    )

    assert issues == []
    assert len(rows) == 1
    assert rows[0]["ticker"] == "MSFT"
    assert rows[0]["integration_mode"] == "reuse_existing_sec_8k_earnings_pipeline"
    assert rows[0]["source_family"] == "sec_8k_earnings_release"
    assert rows[0]["document_status"] == "reuse_existing_pipeline_ready"


def test_company_earnings_plan_builds_non_us_ir_material_locator_rows() -> None:
    rows, issues = MODULE.build_company_earnings_material_source_plan(
        manifest_rows=[
            {
                "ticker": "005930.KS",
                "issuer_id": "KR-005930",
                "company_name": "Samsung Electronics Co., Ltd.",
                "country": "South Korea",
                "global_public_download_eligible": True,
                "official_sources": [
                    {"kind": "regulator", "url": "https://englishdart.fss.or.kr/"},
                    {"kind": "company_ir", "url": "https://www.samsung.com/global/ir/reports-disclosures/business-report/"},
                ],
            }
        ],
        profiles_config={
            "non_us_company_ir": {
                "integration_mode": "new_company_ir_material_locator",
                "preferred_source_kind": "company_ir",
                "download_strategy": "company_ir_material_locator",
                "material_types": {
                    "earnings_release": {
                        "source_family": "company_earnings_release",
                        "source_type": "earnings_release",
                        "source_tier": "company_authored_earnings_material",
                    },
                    "investor_presentation": {
                        "source_family": "company_presentation",
                        "source_type": "investor_presentation",
                        "source_tier": "company_authored_presentation",
                    },
                },
            }
        },
        years=[2024],
        fiscal_periods=["Q4"],
    )

    assert issues == []
    assert len(rows) == 2
    assert {row["source_family"] for row in rows} == {"company_earnings_release", "company_presentation"}
    assert all(row["integration_mode"] == "new_company_ir_material_locator" for row in rows)
    assert all(row["document_status"] == "planned_locator_only" for row in rows)
    assert all(row["source_locator_urls"] == ["https://www.samsung.com/global/ir/reports-disclosures/business-report/"] for row in rows)


def test_company_earnings_plan_reports_non_us_missing_company_ir() -> None:
    rows, issues = MODULE.build_company_earnings_material_source_plan(
        manifest_rows=[
            {
                "ticker": "000660.KS",
                "company_name": "SK hynix Inc.",
                "global_public_download_eligible": True,
                "official_sources": [{"kind": "regulator", "url": "https://englishdart.fss.or.kr/"}],
            }
        ],
        profiles_config={
            "non_us_company_ir": {
                "preferred_source_kind": "company_ir",
                "material_types": {"earnings_release": {"source_family": "company_earnings_release"}},
            }
        },
        years=[2024],
        fiscal_periods=["FY"],
    )

    assert rows == []
    assert issues == [{"type": "missing_company_ir_locator", "ticker": "000660.KS", "company_name": "SK hynix Inc."}]
