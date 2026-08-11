from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_official_business_asset_profile_context_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_official_business_asset_profile_context_rows", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_extracts_v7_official_asset_capacity_as_bounded_business_profile() -> None:
    rows, diagnostics = MODULE.build_official_business_asset_profile_context_rows(
        page_rows=[
            {
                "ticker": "VST",
                "company": "Vistra Corp.",
                "product": "General Energy / Industrials",
                "source_url": "https://vistracorp.com/",
                "title": "Home - Vistra Corp.",
                "body": "The fleet includes 2,176 MW of operating generation and additional power output.",
            }
        ],
        lane_rows=[{"ticker": "VST", "primary_lane_id": "V7"}],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert diagnostics["candidate_count"] == 1
    assert rows
    assert rows[0]["source_role"] == "business_asset_profile_spec"
    assert rows[0]["runtime_contract"] == "BusinessProfileSlot"
    assert rows[0]["exact_value_authority"] is False
    assert "backlog" in rows[0]["forbidden_claims"]


def test_rejects_non_v7_and_commercial_noise() -> None:
    rows, diagnostics = MODULE.build_official_business_asset_profile_context_rows(
        page_rows=[
            {
                "ticker": "AAPL",
                "company": "Apple Inc.",
                "product": "iPhone",
                "source_url": "https://www.apple.com/iphone/",
                "title": "iPhone",
                "body": "Get iPhone with 20W charger and monthly bill credits.",
            },
            {
                "ticker": "BKR",
                "company": "Baker Hughes",
                "product": "General Energy / Industrials",
                "source_url": "https://bakerhughes.com/",
                "title": "Baker Hughes",
                "body": "Pricing and cart details mention 100 kW power output.",
            },
        ],
        lane_rows=[{"ticker": "AAPL", "primary_lane_id": "V2"}, {"ticker": "BKR", "primary_lane_id": "V7"}],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert rows == []
    assert diagnostics["rejected_candidate_count"] >= 1


def test_extracts_v8_store_and_property_footprint_as_context_only_profile() -> None:
    rows, diagnostics = MODULE.build_official_business_asset_profile_context_rows(
        page_rows=[
            {
                "ticker": "WMT",
                "company": "Walmart Inc.",
                "product": "Mass Retail / Grocery",
                "source_url": "https://corporate.walmart.com/about",
                "title": "About Walmart",
                "body": "Walmart operates more than 10,500 stores and clubs in 19 countries.",
            },
            {
                "ticker": "HLT",
                "company": "Hilton Worldwide Holdings",
                "product": "Lodging / Resorts / Cruise",
                "source_url": "https://www.hilton.com/en/corporate/",
                "title": "Hilton Corporate",
                "body": "The portfolio includes approximately 1,250,000 rooms across hotels and resorts.",
            },
        ],
        lane_rows=[{"ticker": "WMT", "primary_lane_id": "V8"}, {"ticker": "HLT", "primary_lane_id": "V8"}],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert diagnostics["candidate_count"] == 2
    assert {row["ticker"] for row in rows} == {"WMT", "HLT"}
    assert {row["metric_name"] for row in rows} == {"store_or_location_count", "room_count"}
    assert all(row["context_only"] is True for row in rows)
    assert all(row["exact_value_authority"] is False for row in rows)


def test_rejects_loyalty_miles_as_business_asset_profile() -> None:
    rows, diagnostics = MODULE.build_official_business_asset_profile_context_rows(
        page_rows=[
            {
                "ticker": "DAL",
                "company": "Delta Air Lines",
                "product": "Travel / Loyalty",
                "source_url": "https://www.delta.com/us/en/skymiles/overview",
                "title": "SkyMiles",
                "body": "SkyMiles members can earn up to 8 miles per dollar on eligible purchases.",
            }
        ],
        lane_rows=[{"ticker": "DAL", "primary_lane_id": "V8"}],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert rows == []
    assert diagnostics["rejected_candidate_count"] >= 1
    assert "commercial_or_site_noise" in diagnostics["rejection_reasons"]


def test_rejects_year_like_property_counts_and_non_lodging_beds() -> None:
    rows, diagnostics = MODULE.build_official_business_asset_profile_context_rows(
        page_rows=[
            {
                "ticker": "O",
                "company": "Realty Income",
                "product": "Real Estate / Infrastructure REIT",
                "source_url": "https://realtyincome.com/report.pdf",
                "title": "Quarterly Results",
                "body": "Operating results for the three months ended March 31, 2026 properties portfolio update.",
            },
            {
                "ticker": "TAP",
                "company": "Molson Coors",
                "product": "Consumer Brands / CPG",
                "source_url": "https://www.molson.ca/",
                "title": "Molson",
                "body": "The promotional garden page mentions 30 beds for planting hops.",
            },
        ],
        lane_rows=[{"ticker": "O", "primary_lane_id": "V7"}, {"ticker": "TAP", "primary_lane_id": "V8"}],
        generated_at="2026-06-25T00:00:00Z",
    )

    assert rows == []
    assert "year_like_asset_count" in diagnostics["rejection_reasons"]
    assert "bed_count_requires_healthcare_facility_adapter" in diagnostics["rejection_reasons"]
