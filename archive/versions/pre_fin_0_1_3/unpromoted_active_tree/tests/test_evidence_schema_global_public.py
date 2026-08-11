from __future__ import annotations

from evidence.schema import EvidenceObject


def test_evidence_schema_accepts_global_public_primary_disclosure() -> None:
    evidence = EvidenceObject(
        evidence_id="IFX_2024_ANNUAL_REPORT_ITEM1_CHUNK_0001",
        source_type="annual_report",
        source_tier="primary_global_public_disclosure",
        ticker="IFX.DE",
        company="Infineon Technologies AG",
        fiscal_year=2024,
        period_type="annual",
        evidence_type="business_description",
        text="Infineon annual report disclosure text.",
        metadata={"source_family": "global_public_annual_report", "disclosure_profile": "eu_regulated_annual_report"},
    )

    assert evidence.source_type == "annual_report"
    assert evidence.source_tier == "primary_global_public_disclosure"
    assert evidence.metadata["source_family"] == "global_public_annual_report"


def test_evidence_schema_accepts_foreign_sec_annual_forms() -> None:
    evidence = EvidenceObject(
        evidence_id="TSM_2024_20F_ITEM7_CHUNK_0001",
        source_type="20-F",
        source_tier="primary_sec_filing",
        ticker="TSM",
        company="Taiwan Semiconductor Manufacturing Company Limited",
        fiscal_year=2024,
        evidence_type="management_discussion",
        text="Form 20-F operating and financial review disclosure text.",
        metadata={"form_type": "20-F", "item_code": "7"},
    )

    assert evidence.source_type == "20-F"
    assert evidence.metadata["form_type"] == "20-F"


def test_evidence_schema_accepts_company_earnings_materials() -> None:
    evidence = EvidenceObject(
        evidence_id="SAMSUNG_2024_Q4_EARNINGS_RELEASE_0001",
        source_type="earnings_release",
        source_tier="company_authored_earnings_material",
        ticker="005930.KS",
        company="Samsung Electronics Co., Ltd.",
        fiscal_year=2024,
        fiscal_period="Q4",
        evidence_type="management_commentary",
        text="Samsung company-authored results release text.",
        metadata={"source_family": "company_earnings_release", "source_boundary": "unaudited_company_material"},
    )

    assert evidence.source_type == "earnings_release"
    assert evidence.source_tier == "company_authored_earnings_material"
    assert evidence.metadata["source_family"] == "company_earnings_release"


def test_evidence_schema_accepts_structured_financial_fact_boundary() -> None:
    evidence = EvidenceObject(
        evidence_id="MSFT_COMPANYFACTS_REVENUE_2025",
        source_type="financial_fact",
        source_tier="company_reported_structured_fact",
        ticker="MSFT",
        company="Microsoft Corporation",
        fiscal_year=2025,
        period_type="annual",
        evidence_type="structured_financial_fact",
        text="Revenue fact from SEC CompanyFacts JSON.",
        metadata={
            "source_family": "sec_companyfacts_structured_fact",
            "taxonomy": "us-gaap",
            "concept": "Revenues",
            "unit": "USD",
        },
    )

    assert evidence.source_type == "financial_fact"
    assert evidence.source_tier == "company_reported_structured_fact"
    assert evidence.metadata["concept"] == "Revenues"
