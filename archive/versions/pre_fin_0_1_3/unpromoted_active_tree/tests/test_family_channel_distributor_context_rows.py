from __future__ import annotations

import importlib.util
from pathlib import Path

from sec_agent.exact_slot_contracts import build_exact_slot_rows


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_family_channel_distributor_context_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_family_channel_distributor_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_family_channel_distributor_locator_from_official_seed(tmp_path: Path) -> None:
    targets = MODULE.build_targets(
        docket_rows=[
            {
                "ticker": "DE",
                "company_name": "Deere & Company",
                "primary_lane_id": "V7",
                "requirement_id": "channel_offer_proxy",
                "family_ids": ["industrial_equipment"],
                "family_names": ["Industrial Equipment"],
            }
        ],
        family_assignment_rows=[],
    )

    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        assert timeout_s == 2
        if url == "https://www.deere.com/":
            return (
                200,
                "text/html",
                '<html><head><title>John Deere</title></head><body>'
                '<a href="/dealer-locator">Find a Dealer</a>'
                "</body></html>",
            )
        if url.endswith("/dealer-locator"):
            return 200, "text/html", "<html><title>Find a Dealer</title></html>"
        return 404, "text/html", ""

    rows, attempts = MODULE.build_family_channel_distributor_context_rows(
        targets=targets,
        official_surface_rows=[{"ticker": "DE", "url": "https://www.deere.com/", "domain": "deere.com"}],
        domain_cache={"DE": {"domains": ["deere.com"]}},
        raw_dir=tmp_path,
        generated_at="2026-06-19T00:00:00Z",
        timeout_s=2,
        max_seeds_per_ticker=1,
        max_links_per_seed=2,
        workers=1,
        fetch=fake_fetch,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["ticker"] == "DE"
    assert row["source_id"] == MODULE.SOURCE_ID
    assert row["channel_locator_type"] == "dealer_locator"
    assert row["source_url"] == "https://www.deere.com/dealer-locator"
    assert row["can_support_company_exact_fact"] is False
    assert any(attempt["status"] == "materialized" for attempt in attempts)

    payload = build_exact_slot_rows(rows, generated_at="2026-06-19T00:00:00Z")
    assert payload["exact_slot_row_count"] == 1
    assert payload["exact_rows"][0]["requirement_id"] == "channel_offer_proxy"


def test_family_channel_distributor_ignores_unbound_official_surface_domain() -> None:
    targets = MODULE.build_targets(
        docket_rows=[
            {
                "ticker": "BBY",
                "company_name": "Best Buy",
                "primary_lane_id": "V8",
                "requirement_id": "channel_offer_proxy",
                "family_ids": ["consumer_electronics_retail"],
                "family_names": ["Consumer Electronics Retail"],
            }
        ],
        family_assignment_rows=[],
    )

    seeds = MODULE.build_seed_urls(
        targets=targets,
        official_surface_rows=[{"ticker": "BBY", "url": "https://best.com/solutions"}],
        domain_cache={"BBY": {"domains": ["bestbuy.com"]}},
        max_seeds_per_ticker=4,
    )

    urls = [seed["url"] for seed in seeds["BBY"]]
    assert "https://best.com/solutions" not in urls
    assert any("bestbuy.com" in url for url in urls)


def test_explicit_ticker_builds_channel_target_without_existing_requirement() -> None:
    targets = MODULE.build_targets(
        docket_rows=[],
        company_source_matrix_rows=[
            {
                "ticker": "MKC",
                "company_name": "McCormick & Company",
                "primary_lane_id": "V8",
                "source_role_matrix": [{"requirement_id": "official_product_surface"}],
            }
        ],
        family_assignment_rows=[
            {
                "ticker": "MKC",
                "family_id": "consumer_brands_cpg",
                "family_name": "Consumer Brands / CPG",
                "query_terms": ["spices", "seasoning"],
            }
        ],
        tickers=["MKC"],
    )

    assert len(targets) == 1
    assert targets[0]["ticker"] == "MKC"
    assert targets[0]["docket_id"] == "explicit_ticker_channel_probe"
    assert targets[0]["family_ids"] == ["consumer_brands_cpg"]
    assert "spices" in targets[0]["query_terms"]


def test_extract_locator_links_filters_noise() -> None:
    links = MODULE.extract_locator_links(
        """
        <a href="/privacy">Privacy</a>
        <a href="/where-to-buy">Where to Buy</a>
        <a href="/careers">Careers</a>
        """,
        base_url="https://example.com/",
    )

    assert links == [
        {
            "url": "https://example.com/where-to-buy",
            "text": "Where to Buy",
            "locator_kind": "distributor_locator",
        }
    ]


def test_direct_locator_path_requires_locator_context_body(tmp_path: Path) -> None:
    targets = MODULE.build_targets(
        docket_rows=[
            {
                "ticker": "TEST",
                "company_name": "Monolithic Power Systems",
                "primary_lane_id": "V7",
                "requirement_id": "channel_offer_proxy",
                "family_ids": ["power_semiconductor_components"],
                "family_names": ["Power Semiconductor Components"],
            }
        ],
        family_assignment_rows=[],
    )

    rows, attempts = MODULE.build_family_channel_distributor_context_rows(
        targets=targets,
        official_surface_rows=[],
        domain_cache={"TEST": {"domains": ["monolithicpower.com"]}},
        raw_dir=tmp_path,
        generated_at="2026-06-19T00:00:00Z",
        timeout_s=2,
        max_seeds_per_ticker=1,
        workers=1,
        fetch=lambda url, timeout_s: (
            200,
            "text/html",
            "<html><title>MPS | Monolithic Power Systems</title><body>Power modules and regulators.</body></html>",
        ),
    )

    assert rows == []
    assert any(attempt["status"] == "no_locator_link_found" for attempt in attempts)


def test_manual_verified_direct_locator_seed_can_materialize_without_body_keyword(tmp_path: Path) -> None:
    targets = MODULE.build_targets(
        docket_rows=[
            {
                "ticker": "BBY",
                "company_name": "Best Buy",
                "primary_lane_id": "V8",
                "requirement_id": "channel_offer_proxy",
                "family_ids": ["consumer_electronics_retail"],
                "family_names": ["Consumer Electronics Retail"],
            }
        ],
        family_assignment_rows=[],
    )

    rows, attempts = MODULE.build_family_channel_distributor_context_rows(
        targets=targets,
        official_surface_rows=[],
        domain_cache={},
        raw_dir=tmp_path,
        generated_at="2026-06-19T00:00:00Z",
        timeout_s=2,
        max_seeds_per_ticker=1,
        workers=1,
        fetch=lambda url, timeout_s: (
            200,
            "text/html",
            "<html><title>Best Buy Store Directory</title><body>Search by state.</body></html>",
        ),
    )

    assert len(rows) == 1
    assert rows[0]["ticker"] == "BBY"
    assert rows[0]["channel_locator_type"] == "store_locator"
    assert any(attempt["status"] == "materialized" for attempt in attempts)


def test_blocked_fetch_uses_same_url_cached_official_body_without_overwrite(tmp_path: Path) -> None:
    targets = MODULE.build_targets(
        docket_rows=[
            {
                "ticker": "LCID",
                "company_name": "Lucid Group",
                "primary_lane_id": "V5",
                "requirement_id": "channel_offer_proxy",
                "family_ids": ["ev_oem"],
                "family_names": ["EV OEM"],
            }
        ],
        family_assignment_rows=[],
    )
    url = "https://lucidmotors.com/locations"
    raw_path = tmp_path / f"lcid_{MODULE._stable_digest(url)}.html"
    raw_path.write_text(
        "<html><title>Studios & Service Centers | Lucid Motors</title><body>Official locations.</body></html>",
        encoding="utf-8",
    )

    rows, attempts = MODULE.build_family_channel_distributor_context_rows(
        targets=targets,
        official_surface_rows=[],
        domain_cache={},
        raw_dir=tmp_path,
        generated_at="2026-06-19T00:00:00Z",
        timeout_s=2,
        max_seeds_per_ticker=1,
        workers=1,
        fetch=lambda url, timeout_s: (403, "text/html", "<html><title>Access Denied</title></html>"),
    )

    assert len(rows) == 1
    assert rows[0]["ticker"] == "LCID"
    assert rows[0]["source_url"] == url
    assert raw_path.read_text(encoding="utf-8").startswith("<html><title>Studios")
    assert any(attempt["status"] == "materialized_from_cached_official_body" for attempt in attempts)


def test_manual_partner_and_space_locator_seeds_are_materialized(tmp_path: Path) -> None:
    targets = MODULE.build_targets(
        docket_rows=[
            {
                "ticker": "ROK",
                "company_name": "Rockwell Automation",
                "primary_lane_id": "V7",
                "requirement_id": "channel_offer_proxy",
                "family_ids": ["industrial_automation"],
                "family_names": ["Industrial Automation"],
            },
            {
                "ticker": "RIVN",
                "company_name": "Rivian Automotive",
                "primary_lane_id": "V5",
                "requirement_id": "channel_offer_proxy",
                "family_ids": ["ev_oem"],
                "family_names": ["EV OEM"],
            },
        ],
        family_assignment_rows=[],
    )

    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        if "partner-locator" in url:
            return 200, "text/html", "<html><title>Partner Locator</title><body>Find a partner locator near you.</body></html>"
        if "rivian.com/spaces" in url:
            return 200, "text/html", "<html><title>Rivian Spaces</title><body>Retail spaces and service centers.</body></html>"
        return 404, "text/html", ""

    rows, attempts = MODULE.build_family_channel_distributor_context_rows(
        targets=targets,
        official_surface_rows=[],
        domain_cache={},
        raw_dir=tmp_path,
        generated_at="2026-06-19T00:00:00Z",
        timeout_s=2,
        max_seeds_per_ticker=1,
        workers=1,
        fetch=fake_fetch,
    )

    by_ticker = {row["ticker"]: row for row in rows}
    assert by_ticker["ROK"]["channel_locator_type"] == "partner_locator"
    assert by_ticker["RIVN"]["channel_locator_type"] == "store_locator"
    assert {attempt["ticker"] for attempt in attempts if attempt["status"] == "materialized"} == {"ROK", "RIVN"}


def test_manual_sales_title_seed_materializes_sales_office_locator(tmp_path: Path) -> None:
    targets = MODULE.build_targets(
        docket_rows=[
            {
                "ticker": "MRVL",
                "company_name": "Marvell Technology",
                "primary_lane_id": "V1",
                "requirement_id": "channel_offer_proxy",
                "family_ids": ["networking_connectivity"],
                "family_names": ["Networking Connectivity"],
            }
        ],
        family_assignment_rows=[],
    )

    rows, attempts = MODULE.build_family_channel_distributor_context_rows(
        targets=targets,
        official_surface_rows=[],
        domain_cache={},
        raw_dir=tmp_path,
        generated_at="2026-06-20T00:00:00Z",
        timeout_s=2,
        max_seeds_per_ticker=1,
        workers=1,
        fetch=lambda url, timeout_s: (
            200,
            "text/html",
            "<html><title>Marvell Sales Offices</title><body>Search below for representatives and distributors.</body></html>",
        ),
    )

    assert len(rows) == 1
    assert rows[0]["channel_locator_type"] == "sales_office_locator"
    assert any(attempt["status"] == "materialized" for attempt in attempts)


def test_non_us_and_brand_manual_channel_seeds_are_allowed_by_overrides() -> None:
    targets = MODULE.build_targets(
        docket_rows=[
            {"ticker": "1211.HK", "company_name": "BYD Company Limited", "requirement_id": "channel_offer_proxy"},
            {"ticker": "LI", "company_name": "Li Auto Inc.", "requirement_id": "channel_offer_proxy"},
            {"ticker": "ITW", "company_name": "Illinois Tool Works", "requirement_id": "channel_offer_proxy"},
            {"ticker": "DECK", "company_name": "Deckers Outdoor", "requirement_id": "channel_offer_proxy"},
            {"ticker": "MDLZ", "company_name": "Mondelez International", "requirement_id": "channel_offer_proxy"},
            {"ticker": "SJM", "company_name": "J.M. Smucker", "requirement_id": "channel_offer_proxy"},
            {"ticker": "XOM", "company_name": "ExxonMobil", "requirement_id": "channel_offer_proxy"},
        ],
        family_assignment_rows=[],
    )

    seeds = MODULE.build_seed_urls(
        targets=targets,
        official_surface_rows=[
            {"ticker": "DECK", "url": "https://www.teva.com/storelocator", "domain": "teva.com"}
        ],
        domain_cache={},
        max_seeds_per_ticker=3,
    )

    assert "https://www.byd.com/eu/find-store" in [seed["url"] for seed in seeds["1211.HK"]]
    assert "https://www.liauto.com/support/aftersale" in [seed["url"] for seed in seeds["LI"]]
    assert "https://www.millerwelds.com/where-to-buy" in [seed["url"] for seed in seeds["ITW"]]
    assert "https://www.hoka.com/en/us/store-locator/" in [seed["url"] for seed in seeds["DECK"]]
    assert "https://www.teva.com/storelocator" in [seed["url"] for seed in seeds["DECK"]]
    assert "https://www.mondelezawayfromhome.com/where-to-buy/" in [seed["url"] for seed in seeds["MDLZ"]]
    assert "https://www.smuckers.com/where-to-buy" in [seed["url"] for seed in seeds["SJM"]]
    assert "https://www.exxon.com/en/find-station" in [seed["url"] for seed in seeds["XOM"]]


def test_manual_contact_page_with_sales_email_materializes_sales_locator(tmp_path: Path) -> None:
    targets = MODULE.build_targets(
        docket_rows=[
            {
                "ticker": "CRDO",
                "company_name": "Credo Technology Group",
                "primary_lane_id": "V1",
                "requirement_id": "channel_offer_proxy",
                "family_ids": ["networking_connectivity"],
                "family_names": ["Networking Connectivity"],
            }
        ],
        family_assignment_rows=[],
    )

    rows, attempts = MODULE.build_family_channel_distributor_context_rows(
        targets=targets,
        official_surface_rows=[],
        domain_cache={},
        raw_dir=tmp_path,
        generated_at="2026-06-20T00:00:00Z",
        timeout_s=2,
        max_seeds_per_ticker=1,
        workers=1,
        fetch=lambda url, timeout_s: (
            200,
            "text/html",
            "<html><title>Contact Us - Credo</title><body>Email our team Sales sales@credosemi.com</body></html>",
        ),
    )

    assert len(rows) == 1
    assert rows[0]["channel_locator_type"] == "sales_office_locator"
    assert any(attempt["status"] == "materialized" for attempt in attempts)


def test_manual_verified_seed_can_use_browser_fallback_for_rendered_locator(tmp_path: Path) -> None:
    targets = MODULE.build_targets(
        docket_rows=[
            {
                "ticker": "LI",
                "company_name": "Li Auto Inc.",
                "primary_lane_id": "V5",
                "requirement_id": "channel_offer_proxy",
                "family_ids": ["ev_oem"],
                "family_names": ["EV OEM"],
            }
        ],
        family_assignment_rows=[],
    )

    rows, attempts = MODULE.build_family_channel_distributor_context_rows(
        targets=targets,
        official_surface_rows=[],
        domain_cache={},
        raw_dir=tmp_path,
        generated_at="2026-06-20T00:00:00Z",
        timeout_s=2,
        max_seeds_per_ticker=1,
        workers=1,
        fetch=lambda url, timeout_s: (
            200,
            "text/html",
            "<html><title>Li Auto</title><body><div id='root'></div><script src='app.js'></script></body></html>",
        ),
        browser_fallback=True,
        browser_fetch=lambda url, timeout_s: (
            200,
            "text/html; rendered=playwright",
            "<html><title>Li Auto</title><body>View all stores in China Li Auto Official Retail Center Service Center</body></html>",
        ),
    )

    assert len(rows) == 1
    assert rows[0]["channel_locator_type"] == "store_locator"
    assert any(attempt["response_source"] == "live_browser_fetch" for attempt in attempts)


def test_manual_verified_seed_uses_browser_fallback_after_unusable_response(tmp_path: Path) -> None:
    targets = MODULE.build_targets(
        docket_rows=[
            {
                "ticker": "AZO",
                "company_name": "AutoZone",
                "primary_lane_id": "V8",
                "requirement_id": "channel_offer_proxy",
                "family_ids": ["auto_parts_retail"],
                "family_names": ["Auto Parts Retail"],
            }
        ],
        family_assignment_rows=[],
    )

    rows, attempts = MODULE.build_family_channel_distributor_context_rows(
        targets=targets,
        official_surface_rows=[],
        domain_cache={},
        raw_dir=tmp_path,
        generated_at="2026-06-23T00:00:00Z",
        timeout_s=2,
        max_seeds_per_ticker=1,
        workers=1,
        fetch=lambda url, timeout_s: (403, "text/html", "<html><title>Access Denied</title></html>"),
        browser_fallback=True,
        browser_fetch=lambda url, timeout_s: (
            200,
            "text/html; rendered=playwright",
            "<html><title>AutoZone Locations</title><body>Find an AutoZone store near you.</body></html>",
        ),
    )

    assert len(rows) == 1
    assert rows[0]["ticker"] == "AZO"
    assert rows[0]["channel_locator_type"] == "store_locator"
    assert any(attempt["status"] == "materialized" for attempt in attempts)
    assert any(attempt["response_source"] == "live_browser_fetch" for attempt in attempts)


def test_blocked_detector_does_not_reject_normal_page_with_404_text() -> None:
    body = "<html><title>Sales Offices</title><body>Call 404-555-1212 for distributor support.</body></html>"

    assert MODULE._looks_blocked(body) is False


def test_blocked_detector_allows_recaptcha_script_on_normal_sales_page() -> None:
    body = (
        "<html><title>Sales Offices</title><body>Search below for distributors.</body>"
        "<script src=\"https://www.recaptcha.net/recaptcha/api.js\"></script></html>"
    )

    assert MODULE._looks_blocked(body) is False


def test_output_row_filter_rejects_cached_404_error_title() -> None:
    row = {
        "ticker": "PH",
        "source_url": "https://www.parker.com/distributors",
        "channel_link_text": "404 Error | Parker US",
    }

    assert MODULE._output_row_usable(row) is False


def test_manual_verified_seed_can_infer_locator_kind_from_deep_body_text(tmp_path: Path) -> None:
    targets = MODULE.build_targets(
        docket_rows=[
            {
                "ticker": "WAB",
                "company_name": "Wabtec",
                "primary_lane_id": "V7",
                "requirement_id": "channel_offer_proxy",
                "family_ids": ["rail_equipment"],
                "family_names": ["Rail Equipment"],
            }
        ],
        family_assignment_rows=[],
    )
    filler = " ".join(["style"] * 3000)
    body = (
        f"<html><title>Parts and Service</title><body>{filler}"
        "Genuine OEM spare parts available from our Wabtec Partner Network. "
        "Find your local Wabtec Partner.</body></html>"
    )

    rows, attempts = MODULE.build_family_channel_distributor_context_rows(
        targets=targets,
        official_surface_rows=[],
        domain_cache={},
        raw_dir=tmp_path,
        generated_at="2026-06-20T00:00:00Z",
        timeout_s=2,
        max_seeds_per_ticker=1,
        workers=1,
        fetch=lambda url, timeout_s: (200, "text/html", body),
    )

    assert len(rows) == 1
    assert rows[0]["channel_locator_type"] == "partner_locator"
    assert any(attempt["status"] == "materialized" for attempt in attempts)


def test_trusted_distributor_seed_requires_issuer_binding(tmp_path: Path) -> None:
    targets = MODULE.build_targets(
        docket_rows=[
            {
                "ticker": "MPWR",
                "company_name": "Monolithic Power Systems",
                "primary_lane_id": "V1",
                "requirement_id": "channel_offer_proxy",
                "family_ids": ["power_semiconductor_components"],
                "family_names": ["Power Semiconductor Components"],
            }
        ],
        family_assignment_rows=[],
    )

    rows, attempts = MODULE.build_family_channel_distributor_context_rows(
        targets=targets,
        official_surface_rows=[],
        domain_cache={},
        raw_dir=tmp_path,
        generated_at="2026-06-20T00:00:00Z",
        timeout_s=2,
        max_seeds_per_ticker=1,
        workers=1,
        fetch=lambda url, timeout_s: (
            200,
            "text/html",
            "<html><title>Monolithic Power Systems</title><body>Arrow is an authorized distributor for Monolithic Power Systems product categories.</body></html>",
        ),
    )

    assert len(rows) == 1
    assert rows[0]["source_url"] == "https://www.arrow.com/en/manufacturers/m/monolithic-power-systems.html"
    assert rows[0]["channel_locator_type"] == "distributor_locator"

    mismatch_rows, mismatch_attempts = MODULE.build_family_channel_distributor_context_rows(
        targets=targets,
        official_surface_rows=[],
        domain_cache={},
        raw_dir=tmp_path / "mismatch",
        generated_at="2026-06-20T00:00:00Z",
        timeout_s=2,
        max_seeds_per_ticker=1,
        workers=1,
        fetch=lambda url, timeout_s: (
            200,
            "text/html",
            "<html><title>Texas Instruments</title><body>Arrow is an authorized distributor for Texas Instruments.</body></html>",
        ),
    )

    assert mismatch_rows == []
    assert any(attempt["status"] == "trusted_distributor_seed_binding_gap" for attempt in mismatch_attempts)
