from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "materialize_family_official_product_surface_pages.py"
SPEC = importlib.util.spec_from_file_location("materialize_family_official_product_surface_pages", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_product_kpi_exact_slot_without_official_page_still_targets_family_surface() -> None:
    profiles, report = MODULE.build_family_product_surface_profiles(
        slots=[
            {
                "ticker": "ADM",
                "company_name": "Archer Daniels Midland",
                "family_id": "agriculture_commodities_ingredients",
                "family_name": "Agriculture Commodities / Ingredients",
                "product_slot_name": "Nutrition",
                "slot_status": "product_kpi_exact_slot",
                "sample_urls": ["https://www.sec.gov/Archives/edgar/data/7084/example.htm"],
            }
        ],
        existing_rows=[{"ticker": "ADM", "source_url": "https://www.adm.com/"}],
        domain_cache={"ADM": {"domains": ["adm.co", "adm.com"]}},
    )

    assert report["target_ticker_count"] == 1
    assert profiles["ADM"]["company_domains"][0] == "adm.com"
    assert any(url == "https://www.adm.com/en-us/products-services" for url in profiles["ADM"]["official_product_urls"])


def test_official_surface_slot_with_company_url_is_not_retargeted() -> None:
    profiles, report = MODULE.build_family_product_surface_profiles(
        slots=[
            {
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "family_id": "smartphones_tablets",
                "product_slot_name": "iPhone",
                "slot_status": "official_surface_slot",
                "sample_urls": ["https://www.apple.com/iphone/"],
            }
        ],
        existing_rows=[],
        domain_cache={"AAPL": {"domains": ["apple.com"]}},
    )

    assert report["target_ticker_count"] == 0
    assert profiles == {}


def test_empty_domain_cache_retries_later_resolvers(monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "_clearbit_domains", lambda company_name: [])
    monkeypatch.setattr(MODULE, "_bing_official_domains", lambda *, company_name, ticker: ["bunge.com"])
    cache = {"BNG": {"ticker": "BNG", "company_name": "Bunge Global", "domains": []}}

    profiles, report = MODULE.build_family_product_surface_profiles(
        slots=[
            {
                "ticker": "BNG",
                "company_name": "Bunge Global",
                "family_id": "agriculture_commodities_ingredients",
                "family_name": "Agriculture Commodities / Ingredients",
                "product_slot_name": "Agriculture Commodities / Ingredients",
                "slot_status": "seed_needs_locator",
                "sample_urls": [],
            }
        ],
        existing_rows=[],
        domain_cache=cache,
    )

    assert report["profile_count"] == 1
    assert profiles["BNG"]["company_domains"] == ["bunge.com"]
    assert cache["BNG"]["domains"] == ["bunge.com"]
    assert "bing_official_website_locator" in cache["BNG"]["resolver_sources"]


def test_domain_override_supersedes_bad_cached_locator() -> None:
    profiles, report = MODULE.build_family_product_surface_profiles(
        slots=[
            {
                "ticker": "ACLS",
                "company_name": "AXCELIS TECHNOLOGIES INC",
                "family_id": "semicap_equipment",
                "family_name": "Semicap Equipment",
                "product_slot_name": "Semicap Equipment",
                "slot_status": "seed_needs_locator",
                "sample_urls": [],
            }
        ],
        existing_rows=[],
        domain_cache={"ACLS": {"ticker": "ACLS", "company_name": "AXCELIS TECHNOLOGIES INC", "domains": ["apple.com"]}},
    )

    assert report["profile_count"] == 1
    assert profiles["ACLS"]["company_domains"] == ["axcelis.com"]


def test_existing_external_route_urls_do_not_become_official_domains() -> None:
    profiles, report = MODULE.build_family_product_surface_profiles(
        slots=[
            {
                "ticker": "DELL",
                "company_name": "Dell Technologies",
                "family_id": "server_oem",
                "family_name": "AI Server / Rack OEM",
                "product_slot_name": "AI Server / Rack OEM",
                "slot_status": "company_route_needs_family_binding",
                "sample_urls": ["https://www.semiconductors.org/"],
            }
        ],
        existing_rows=[],
        domain_cache={},
    )

    assert report["profile_count"] == 1
    assert profiles["DELL"]["company_domains"] == ["dell.com"]
    assert all("semiconductors.org" not in url for url in profiles["DELL"]["official_product_urls"])


def test_weak_company_name_overlap_domains_are_rejected() -> None:
    domains = MODULE._filter_company_domains(
        ticker="AEP",
        company_name="American Electric Power",
        domains=["americanexpress.com", "aep.com"],
    )

    assert domains == ["aep.com"]


def test_first_token_only_weak_domain_is_rejected_for_multi_token_issuer() -> None:
    domains = MODULE._filter_company_domains(
        ticker="AJG",
        company_name="Arthur J. Gallagher & Co.",
        domains=["arthur.jp", "ajg.com"],
    )

    assert domains == ["ajg.com"]


def test_override_prunes_bad_existing_materialized_domains() -> None:
    rows = MODULE._filter_existing_materialized_rows_by_domain(
        existing_rows=[
            {"ticker": "UHS", "source_url": "https://www.uhs.com.np/products"},
            {"ticker": "UHS", "source_url": "https://www.uhs.com/products"},
        ],
        slots=[{"ticker": "UHS", "company_name": "Universal Health Services, Inc."}],
    )

    assert [row["source_url"] for row in rows] == ["https://www.uhs.com/products"]


def test_candidate_urls_interleave_domains_before_truncation() -> None:
    urls = MODULE._candidate_urls(
        domains=["lilly.com", "lillyoncologypipeline.com", "medical.lilly.com"],
        slots=[{"ticker": "LLY", "family_id": "oncology_immunology"}],
    )

    assert any("lillyoncologypipeline.com" in url for url in urls[:5])
    assert "https://medical.lilly.com/us/products/medical-information/oncology" in urls
    assert all("www.medical.lilly.com" not in url for url in urls)


def test_ticker_exact_match_rejects_multi_label_country_domain() -> None:
    domains = MODULE._filter_company_domains(
        ticker="UHS",
        company_name="Universal Health Services, Inc.",
        domains=["uhs.com.np"],
    )

    assert domains == []
