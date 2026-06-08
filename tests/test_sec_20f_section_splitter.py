from __future__ import annotations

from ingestion.section_splitter import find_10k_sections, find_20f_sections, find_40f_sections


def test_find_20f_sections_maps_foreign_annual_items_to_existing_evidence_items() -> None:
    preface = "\n".join(["table of contents"] * 900)
    text = f"""
{preface}
ITEM 3. | KEY INFORMATION | 1
ITEM 4. | INFORMATION ON THE COMPANY | 10
ITEM 5. | OPERATING AND FINANCIAL REVIEW AND PROSPECTS | 25
ITEM 18. | FINANCIAL STATEMENTS | 80

D. Risk Factors
Risk Factors
{"risk disclosure " * 80}

Item 4. Information on the Company
B. Business Overview
{"business overview " * 80}

Item 5. Operating and Financial Review and Prospects
Operating Results
{"operating review " * 80}

Item 11. Quantitative and Qualitative Disclosures About Market Risk
{"market risk " * 80}

Item 18. Financial Statements
Report of Independent Registered Public Accounting Firm
{"financial statements " * 80}

SIGNATURES
""".strip()

    sections = find_20f_sections(text)

    assert [section.item_code for section in sections] == ["1A", "1", "7", "7A", "8"]
    assert sections[0].section == "Form 20-F Item 3.D. Risk Factors"
    assert sections[1].section == "Form 20-F Item 4. Information on the Company"


def test_find_10k_sections_recovers_item_split_as_m_line_prefix() -> None:
    text = f"""
TABLE OF CONTENTS
ITEM 1. | BUSINESS | 1
ITEM 1A. | RISK FACTORS | 11
ITEM 7. | MANAGEMENT'S DISCUSSION AND ANALYSIS | 31
ITEM 8. | FINANCIAL STATEMENTS | 40

P
ART I

Ite
m 1. Business.
{"business disclosure " * 80}

m 1A. Risk Factors.
{"risk disclosure " * 80}

m 7. Management's Discussion and Analysis of Financial Condition and Results of Operations.
{"management discussion " * 80}

m 8. Financial Statements and Supplementary Data.
{"financial statement " * 80}
""".strip()

    sections = find_10k_sections(text, min_start_span_chars=100)

    assert [section.item_code for section in sections] == ["1", "1A", "7", "8"]


def test_find_40f_sections_maps_canadian_annual_package_to_existing_evidence_items() -> None:
    text = f"""
FIN 40-F Annual Package

FIN 40-F Annual Information Form
Description of the Business
{"business description " * 80}

Risk Factors
{"risk factors " * 80}

FIN 40-F Financial Statements
Consolidated Financial Statements
{"financial statements " * 80}

FIN 40-F Mda
Management's Discussion and Analysis
{"management discussion " * 80}

Financial Instruments
{"market risk " * 80}

Signatures
""".strip()

    sections = find_40f_sections(text)

    assert [section.item_code for section in sections] == ["1", "1A", "8", "7"]
    assert sections[0].section == "Form 40-F Annual Information Form - Business"
    assert sections[2].section == "Form 40-F Audited Financial Statements"

    with_market_risk = find_40f_sections(text, output_items=("1", "1A", "7", "7A", "8"))
    assert [section.item_code for section in with_market_risk] == ["1", "1A", "8", "7", "7A"]
