from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_company_disclosed_product_profile_context_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_company_disclosed_product_profile_context_rows", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_projects_specific_official_catalog_product_to_product_profile_slot() -> None:
    rows, diagnostics = MODULE.build_company_disclosed_product_profile_context_rows(
        product_profile_rows=[
            {
                "_source_file": "official_product_catalog_context_rows_v0_1.jsonl",
                "ticker": "NVDA",
                "company": "NVIDIA Corporation",
                "issuer_binding_status": "company_domain_bound",
                "product_binding_status": "product_mentioned_in_snapshot",
                "parser_status": "official_product_catalog_parser_pass",
                "source_url": "https://www.nvidia.com/en-us/data-center/h100/",
                "product_or_segment": "H100 SXM",
                "product_family": "GPU / Accelerator",
                "evidence_ref": "catalog:nvda:h100",
            }
        ],
        operating_profile_rows=[],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert diagnostics["product_profile_candidate_count"] == 1
    assert len(rows) == 1
    assert rows[0]["runtime_contract"] == "ProductProfileSlot"
    assert rows[0]["source_role"] == "official_product_profile_spec"
    assert rows[0]["exact_value_authority"] is False
    assert "market_share" in rows[0]["forbidden_claims"]


def test_rejects_catalog_navigation_and_generic_family_names() -> None:
    rows, diagnostics = MODULE.build_company_disclosed_product_profile_context_rows(
        product_profile_rows=[
            {
                "_source_file": "official_product_catalog_context_rows_v0_1.jsonl",
                "ticker": "000660.KS",
                "company": "SK hynix Inc.",
                "issuer_binding_status": "company_domain_bound",
                "parser_status": "official_product_catalog_parser_pass",
                "source_url": "https://www.skhynix.com/",
                "product_or_segment": "Products & Solutions 새창",
                "product_family": "Memory / Storage Semiconductors",
            },
            {
                "_source_file": "official_product_catalog_context_rows_v0_1.jsonl",
                "ticker": "AAPL",
                "company": "Apple Inc.",
                "issuer_binding_status": "company_domain_bound",
                "parser_status": "official_product_catalog_parser_pass",
                "source_url": "https://www.apple.com/",
                "product_or_segment": "General Consumer Hardware",
                "product_family": "Consumer Hardware",
            },
        ],
        operating_profile_rows=[],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert rows == []
    assert diagnostics["rejection_reasons"]["weak_or_navigation_product_profile_name"] == 2


def test_projects_strong_official_surface_category_to_product_profile_slot() -> None:
    rows, diagnostics = MODULE.build_company_disclosed_product_profile_context_rows(
        product_profile_rows=[
            {
                "_source_file": "official_product_surface_context_rows_v0_1.jsonl",
                "ticker": "005930.KS",
                "company": "Samsung Electronics Co., Ltd.",
                "issuer_binding_status": "company_domain_bound",
                "product_binding_status": "product_mentioned_in_snapshot",
                "parser_status": "source_specific_context_parser_pass",
                "source_url": "https://www.samsung.com/us/business/semiconductor/",
                "product_or_segment": "Foundry / Wafer Fabrication",
                "product_family": "Foundry / Wafer Fabrication",
                "evidence_ref": "surface:samsung:foundry",
            }
        ],
        operating_profile_rows=[],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert diagnostics["product_profile_candidate_count"] == 1
    assert rows[0]["profile_type"] == "official_product_surface_category_profile"
    assert rows[0]["runtime_contract"] == "ProductProfileSlot"


def test_projects_sec_filings_taxonomy_to_product_profile_slot() -> None:
    rows, diagnostics = MODULE.build_company_disclosed_product_profile_context_rows(
        product_profile_rows=[
            {
                "_source_file": "sec_product_taxonomy_context_rows_v0_1.jsonl",
                "ticker": "AFL",
                "company": "Aflac Incorporated",
                "issuer_binding_status": "issuer_mentioned_in_snapshot",
                "product_binding_status": "product_mentioned_in_snapshot",
                "parser_status": "source_specific_context_parser_pass",
                "source_url": "https://www.sec.gov/Archives/example/afl.htm",
                "product_or_segment": "Cancer Insurance",
                "product_family": "Insurance Products",
                "evidence_ref": "sec_taxonomy:afl:cancer_insurance",
            }
        ],
        operating_profile_rows=[],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert diagnostics["product_profile_candidate_count"] == 1
    assert rows[0]["profile_type"] == "sec_filings_product_taxonomy_profile"
    assert rows[0]["source_role"] == "official_product_profile_spec"
    assert "product_revenue" in rows[0]["forbidden_claims"]


def test_keeps_solution_and_semiconductor_terms_when_they_are_domain_profiles() -> None:
    rows, diagnostics = MODULE.build_company_disclosed_product_profile_context_rows(
        product_profile_rows=[
            {
                "_source_file": "sec_product_taxonomy_context_rows_v0_1.jsonl",
                "ticker": "MRVL",
                "company": "Marvell Technology, Inc.",
                "issuer_binding_status": "issuer_mentioned_in_snapshot",
                "product_binding_status": "product_mentioned_in_snapshot",
                "parser_status": "source_specific_context_parser_pass",
                "source_url": "https://www.sec.gov/Archives/example/mrvl.htm",
                "product_or_segment": "Ethernet Solutions",
                "product_family": "Datacenter Networking / Connectivity",
            },
            {
                "_source_file": "official_product_surface_context_rows_v0_1.jsonl",
                "ticker": "TSM",
                "company": "Taiwan Semiconductor Manufacturing Company Limited",
                "issuer_binding_status": "company_domain_bound",
                "parser_status": "source_specific_context_parser_pass",
                "source_url": "https://tsmc.com/english/dedicatedFoundry/manufacturing",
                "product_or_segment": "semiconductor",
                "product_family": "semiconductor",
            },
        ],
        operating_profile_rows=[],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert diagnostics["product_profile_candidate_count"] == 2
    assert {row["ticker"] for row in rows} == {"MRVL", "TSM"}


def test_projects_utility_taxonomy_candidate_snippet_to_service_profile() -> None:
    rows, diagnostics = MODULE.build_company_disclosed_product_profile_context_rows(
        product_profile_rows=[
            {
                "_source_file": "company_product_taxonomy_candidates_v0_1.jsonl",
                "ticker": "XEL",
                "company": "XCEL ENERGY INC",
                "issuer_binding_status": "issuer_mentioned_in_snapshot",
                "parser_status": "source_specific_context_parser_pass",
                "source_id": "company_product_taxonomy_candidates",
                "source_url": "https://www.sec.gov/Archives/example/xel.htm",
                "taxonomy_label": "Utility Subsidiary Overview",
                "evidence_snippet": (
                    "Utility Subsidiary Overview Electric customers 3.9 million Natural gas customers 2.2 million "
                    "Electric generating capacity (owned) 20,426 MW Natural gas storage capacity 53.3 Bcf."
                ),
            },
            {
                "_source_file": "company_product_taxonomy_candidates_v0_1.jsonl",
                "ticker": "XEL",
                "company": "XCEL ENERGY INC",
                "issuer_binding_status": "issuer_mentioned_in_snapshot",
                "parser_status": "source_specific_context_parser_pass",
                "source_id": "company_product_taxonomy_candidates",
                "source_url": "https://www.sec.gov/Archives/example/xel.htm",
                "taxonomy_label": "Definitions of Abbreviations",
                "evidence_snippet": "Definitions of Abbreviations and filing metadata.",
            },
        ],
        operating_profile_rows=[],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert diagnostics["product_profile_candidate_count"] == 1
    assert rows[0]["ticker"] == "XEL"
    assert rows[0]["product_or_segment"] == "Electric & Gas utility service"
    assert rows[0]["product_family"] == "Regulated Utility / Power"


def test_rejects_official_surface_third_party_script_or_generic_family_noise() -> None:
    rows, diagnostics = MODULE.build_company_disclosed_product_profile_context_rows(
        product_profile_rows=[
            {
                "_source_file": "official_product_surface_context_rows_v0_1.jsonl",
                "ticker": "005930.KS",
                "company": "Samsung Electronics Co., Ltd.",
                "issuer_binding_status": "company_domain_bound",
                "parser_status": "source_specific_context_parser_pass",
                "source_url": "https://www.samsung.com/us/business/semiconductor/",
                "product_or_segment": "Google",
                "product_family": "",
            },
            {
                "_source_file": "official_product_surface_context_rows_v0_1.jsonl",
                "ticker": "AAPL",
                "company": "Apple Inc.",
                "issuer_binding_status": "company_domain_bound",
                "parser_status": "source_specific_context_parser_pass",
                "source_url": "https://www.apple.com/",
                "product_or_segment": "General Consumer Hardware",
                "product_family": "General Consumer Hardware",
            },
        ],
        operating_profile_rows=[],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert rows == []
    assert sum(diagnostics["rejection_reasons"].values()) == 2
    assert diagnostics["rejection_reasons"]["unsupported_product_profile_source"] >= 1


def test_projects_regulated_vehicle_identity_to_product_profile_slot() -> None:
    rows, diagnostics = MODULE.build_company_disclosed_product_profile_context_rows(
        product_profile_rows=[
            {
                "_source_file": "targeted_regulated_auto_official_api_context_rows_v0_1.jsonl",
                "ticker": "F",
                "company": "Ford Motor Company",
                "issuer_binding_status": "issuer_mentioned_in_snapshot",
                "product_binding_status": "product_mentioned_in_snapshot",
                "parser_status": "source_specific_context_parser_pass",
                "source_url": "https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/Ford?format=json",
                "requirement_id": "auto_product_identity_context",
                "source_id": "nhtsa_vpic_api",
                "model": "F-150 Lightning",
                "product_or_segment": "F-150 Lightning",
            }
        ],
        operating_profile_rows=[],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert diagnostics["product_profile_candidate_count"] == 1
    assert rows[0]["profile_type"] == "regulated_vehicle_model_profile"
    assert rows[0]["source_role"] == "official_product_profile_spec"


def test_projects_non_revenue_operating_metric_to_business_profile_slot() -> None:
    rows, diagnostics = MODULE.build_company_disclosed_product_profile_context_rows(
        product_profile_rows=[],
        operating_profile_rows=[
            {
                "_source_file": "industry_operating_metric_slot_rows_v0_1.jsonl",
                "ticker": "BLK",
                "company": "BlackRock, Inc.",
                "parser_status": "industry_operating_metric_slot_parser_pass",
                "source_url": "https://www.sec.gov/Archives/example/blk.htm",
                "metric_family": "aum",
                "metric_name": "AUM",
                "product_or_segment": "Assets under management",
                "period": "FY2024",
                "unit": "USD",
                "value": 11000000000000,
                "citation_span": "row=Assets under management | value=11000000000000 | unit=USD",
            }
        ],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert diagnostics["operating_profile_candidate_count"] == 1
    assert rows[0]["runtime_contract"] == "BusinessProfileSlot"
    assert rows[0]["source_role"] == "business_service_profile_spec"
    assert rows[0]["exact_value_authority"] is False
    assert "product_revenue" in rows[0]["forbidden_claims"]


def test_projects_product_metric_row_label_to_profile_without_value_authority() -> None:
    rows, diagnostics = MODULE.build_company_disclosed_product_profile_context_rows(
        product_profile_rows=[],
        operating_profile_rows=[
            {
                "ticker": "DOW",
                "company": "Dow Inc.",
                "parser_status": "industry_operating_metric_slot_parser_pass",
                "source_url": "https://www.sec.gov/Archives/example/dow.htm",
                "metric_family": "product_revenue",
                "metric_name": "product revenue",
                "product_or_segment": "PACKAGING and SPECIALTY PLASTICS",
                "period": "FY2024",
                "unit": "USD",
                "value": 100,
            }
        ],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert diagnostics["operating_profile_candidate_count"] == 1
    assert rows[0]["profile_type"] == "company_disclosed_product_or_segment_metric_profile"
    assert rows[0]["source_role"] == "official_product_profile_spec"
    assert rows[0]["exact_value_authority"] is False
    assert "product_revenue" in rows[0]["forbidden_claims"]


def test_rejects_region_backlog_and_same_store_metric_as_profile_slot() -> None:
    rows, diagnostics = MODULE.build_company_disclosed_product_profile_context_rows(
        product_profile_rows=[],
        operating_profile_rows=[
            {
                "ticker": "LEN",
                "parser_status": "industry_operating_metric_slot_parser_pass",
                "source_url": "https://www.sec.gov/Archives/example/len.htm",
                "metric_family": "product_revenue",
                "metric_name": "product revenue",
                "product_or_segment": "East",
                "period": "FY2024",
                "unit": "USD",
                "value": 100,
            },
            {
                "ticker": "AZO",
                "parser_status": "industry_operating_metric_slot_parser_pass",
                "source_url": "https://www.sec.gov/Archives/example/azo.htm",
                "metric_family": "same_store_sales_growth",
                "metric_name": "same store sales",
                "product_or_segment": "Domestic stores",
                "period": "FY2024",
                "unit": "percent",
                "value": 3.1,
            },
            {
                "ticker": "BA",
                "parser_status": "industry_operating_metric_slot_parser_pass",
                "source_url": "https://www.sec.gov/Archives/example/ba.htm",
                "metric_family": "backlog_or_orders",
                "metric_name": "backlog",
                "product_or_segment": "Commercial airplanes",
                "period": "FY2024",
                "unit": "USD",
                "value": 100,
            },
        ],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert rows == []
    assert diagnostics["rejection_reasons"]["region_or_aggregate_product_metric_profile_name"] == 1
    assert diagnostics["rejection_reasons"]["metric_family_is_kpi_or_revenue_not_profile"] == 2
