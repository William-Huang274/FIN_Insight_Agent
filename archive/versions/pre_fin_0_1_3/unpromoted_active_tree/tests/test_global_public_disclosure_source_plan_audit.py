from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "audit_global_public_disclosure_source_plan.py"
SPEC = importlib.util.spec_from_file_location("audit_global_public_disclosure_source_plan", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _profiles() -> dict:
    return {
        "profiles": {
            "kr_dart_business_report": {
                "source_tier": "primary_company_disclosure",
                "parser_profile": "kr_dart_business_report_v0_1",
                "annual_report_types": ["annual_report", "business_report"],
                "interim_report_types": ["quarterly_report"],
            }
        }
    }


def _plan_row(**overrides: object) -> dict:
    row = {
        "plan_id": "GLOBALDISC::005930_KS::KR_DART_BUSINESS_REPORT::2024::ANNUAL_REPORT",
        "ticker": "005930.KS",
        "issuer_id": "KR-005930",
        "company_name": "Samsung Electronics Co., Ltd.",
        "source_family": "global_public_annual_report",
        "source_tier": "primary_company_disclosure",
        "disclosure_profile": "kr_dart_business_report",
        "fiscal_year": 2024,
        "report_type": "annual_report",
        "report_type_rule_source": "disclosure_profile",
        "source_locator_urls": ["https://englishdart.fss.or.kr/"],
        "cache_dir": "data/raw_private/global_public_disclosures/kr_dart/005930_KS/2024/ANNUAL_REPORT",
        "parser_profile": "kr_dart_business_report_v0_1",
    }
    row.update(overrides)
    return row


def test_global_public_disclosure_source_plan_audit_passes_valid_profile_contract() -> None:
    summary = MODULE.audit_global_public_disclosure_source_plan(
        plan_rows=[_plan_row()],
        profiles_config=_profiles(),
        manifest_rows=[{"ticker": "005930.KS", "global_public_download_eligible": True}],
        expected_count=1,
    )

    assert summary["status"] == "pass"
    assert summary["errors"] == []


def test_global_public_disclosure_source_plan_audit_rejects_company_level_target_reports() -> None:
    summary = MODULE.audit_global_public_disclosure_source_plan(
        plan_rows=[_plan_row()],
        profiles_config=_profiles(),
        manifest_rows=[{"ticker": "005930.KS", "global_public_download_eligible": True, "target_reports": ["annual_report"]}],
    )

    assert summary["status"] == "fail"
    assert summary["errors"][0]["type"] == "company_level_target_reports_not_allowed"


def test_global_public_disclosure_source_plan_audit_rejects_report_not_allowed_by_profile() -> None:
    summary = MODULE.audit_global_public_disclosure_source_plan(
        plan_rows=[_plan_row(report_type="special_company_report")],
        profiles_config=_profiles(),
    )

    assert summary["status"] == "fail"
    assert any(error["type"] == "report_type_not_allowed_by_profile" for error in summary["errors"])
