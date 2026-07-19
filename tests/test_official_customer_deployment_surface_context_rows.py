from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_official_customer_deployment_surface_context_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_official_customer_deployment_surface_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_discover_candidate_links_keeps_official_customer_and_partner_links(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "arm_product.html").write_text(
        """
        <html><body>
          <a href="/company/success-library/made-possible/meta">Featured partner: Meta</a>
          <a href="https://spam.example.com/customer-story">Customer story</a>
          <a href="/privacy">Privacy</a>
        </body></html>
        """,
        encoding="utf-8",
    )
    surface_rows = [{"ticker": "ARM", "source_url": "https://www.arm.com/products"}]

    candidates = MODULE.discover_candidate_links(
        ticker="ARM",
        surface_rows=surface_rows,
        raw_product_page_dir=raw_dir,
        official_hosts={"arm.com"},
        max_candidates=5,
    )

    assert len(candidates) == 1
    assert candidates[0]["url"] == "https://www.arm.com/company/success-library/made-possible/meta"
    assert candidates[0]["label"] == "Featured partner: Meta"


def test_discover_candidate_links_rejects_low_value_careers_and_business_pages(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "asml_product.html").write_text(
        """
        <html><body>
          <a href="/en/careers/working-at-asml/netherlands">The Netherlands Read more ASML is amid a thriving ecosystem</a>
          <a href="/about/businesses/aepenergypartners">AEP Energy Partners</a>
          <a href="/terms-conditions">T&Cs - Suppliers/Customers</a>
          <a href="/hydrogen-technologies">Hydrogen Technologies Advanced technologies to accelerate hydrogen deployment</a>
          <a href="/en/company/customer-stories/meta">Customer story: Meta</a>
        </body></html>
        """,
        encoding="utf-8",
    )
    surface_rows = [{"ticker": "ASML", "source_url": "https://www.asml.com/en/products"}]

    candidates = MODULE.discover_candidate_links(
        ticker="ASML",
        surface_rows=surface_rows,
        raw_product_page_dir=raw_dir,
        official_hosts={"asml.com"},
        max_candidates=5,
    )

    assert [candidate["url"] for candidate in candidates] == ["https://www.asml.com/en/company/customer-stories/meta"]


def test_discover_candidate_links_adds_official_path_probes_when_product_page_has_no_links(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "nxpi_product.html").write_text("<html><body><a href='/privacy'>Privacy</a></body></html>", encoding="utf-8")
    surface_rows = [{"ticker": "NXPI", "source_url": "https://www.nxp.com/products/processors-and-microcontrollers"}]

    candidates = MODULE.discover_candidate_links(
        ticker="NXPI",
        surface_rows=surface_rows,
        raw_product_page_dir=raw_dir,
        official_hosts={"nxp.com"},
        max_candidates=3,
    )

    assert [candidate["url"] for candidate in candidates] == [
        "https://www.nxp.com/case-studies",
        "https://www.nxp.com/customer-stories",
        "https://www.nxp.com/success-stories",
    ]


def test_discover_candidate_links_uses_verified_manual_customer_deployment_seed(tmp_path: Path) -> None:
    candidates = MODULE.discover_candidate_links(
        ticker="300750.SZ",
        surface_rows=[{"ticker": "300750.SZ", "source_url": "https://www.catl.com/en/solution/"}],
        raw_product_page_dir=tmp_path,
        official_hosts={"catl.com"},
        max_candidates=2,
    )

    assert [candidate["url"] for candidate in candidates] == [
        "https://www.catl.com/en/news/6328.html",
        "https://www.catl.com/en/news/6497.html",
    ]
    assert all(candidate["raw_product_page"] == "" for candidate in candidates)


def test_discover_candidate_links_rejects_manual_seed_when_official_host_does_not_match(tmp_path: Path) -> None:
    candidates = MODULE.discover_candidate_links(
        ticker="000660.KS",
        surface_rows=[{"ticker": "000660.KS", "source_url": "https://www.not-skhynix.example/products"}],
        raw_product_page_dir=tmp_path,
        official_hosts={"not-skhynix.example"},
        max_candidates=2,
    )

    assert "https://news.skhynix.com/multi-year-tech-partnership-with-nvidia/" not in {
        candidate["url"] for candidate in candidates
    }
    assert all(candidate["url"].startswith("https://www.not-skhynix.example/") for candidate in candidates)


def test_path_probe_does_not_materialize_when_only_generated_label_has_signal(tmp_path: Path, monkeypatch) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "nxpi_product.html").write_text("<html><body><a href='/privacy'>Privacy</a></body></html>", encoding="utf-8")

    def fake_fetch(url: str, *, timeout_s: float) -> tuple[str, str, str]:
        return "<html><title>Homepage</title><body>Welcome to the product website.</body></html>", "fetched", ""

    monkeypatch.setattr(MODULE, "_fetch_candidate", fake_fetch)
    result = MODULE.build_official_customer_deployment_surface_context_rows(
        gap_action_rows=[],
        official_product_surface_rows=[{"ticker": "NXPI", "source_url": "https://www.nxp.com/products"}],
        raw_product_page_dir=raw_dir,
        raw_output_dir=tmp_path / "out",
        generated_at="2026-06-25T00:00:00Z",
        max_candidates_per_ticker=2,
        workers=1,
        timeout_s=1,
        sleep_s=0,
    )

    assert result["rows"] == []
    assert {attempt["status"] for attempt in result["attempts"]} == {"fetched_no_customer_or_partner_signal"}


def test_unverified_host_seed_is_not_promoted_from_raw_links(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "bby_product.html").write_text(
        "<html><body><a href='https://best.com/customers'>Customers</a></body></html>",
        encoding="utf-8",
    )

    result = MODULE.build_official_customer_deployment_surface_context_rows(
        gap_action_rows=[],
        official_product_surface_rows=[{"ticker": "BBY", "company": "Best Buy"}],
        raw_product_page_dir=raw_dir,
        raw_output_dir=tmp_path / "out",
        generated_at="2026-06-25T00:00:00Z",
        max_candidates_per_ticker=2,
        workers=1,
        timeout_s=1,
        sleep_s=0,
    )

    assert result["rows"] == []
    assert result["attempts"] == [
        {
            "schema_version": MODULE.ATTEMPT_SCHEMA_VERSION,
            "ticker": "BBY",
            "status": "no_verified_official_host_seed",
            "reason": "Official product surface rows do not expose a verified source_url/snapshot_url/url host, or only map to guess-only domains; refusing unbound raw-link promotion.",
            "candidate_url": "",
            "raw_path": "",
        }
    ]


def test_guess_only_domain_cache_blocks_apparently_bound_source_url(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "bby_product.html").write_text(
        "<html><body><a href='https://best.com/customers'>Customers</a></body></html>",
        encoding="utf-8",
    )

    result = MODULE.build_official_customer_deployment_surface_context_rows(
        gap_action_rows=[],
        official_product_surface_rows=[{"ticker": "BBY", "company": "Best Buy", "source_url": "https://best.com/solutions"}],
        domain_cache={
            "BBY": {
                "domains": ["best.com"],
                "resolver_sources": {"company_name_domain_guess": ["best.com"]},
            }
        },
        raw_product_page_dir=raw_dir,
        raw_output_dir=tmp_path / "out",
        generated_at="2026-06-25T00:00:00Z",
        max_candidates_per_ticker=2,
        workers=1,
        timeout_s=1,
        sleep_s=0,
    )

    assert result["rows"] == []
    assert result["attempts"][0]["status"] == "no_verified_official_host_seed"


def test_context_row_is_bounded_and_never_exact_authority(tmp_path: Path) -> None:
    row = MODULE._context_row(
        ticker="ARM",
        company_name="Arm Holdings plc",
        candidate={
            "url": "https://www.arm.com/company/success-library/made-possible/meta",
            "label": "Featured partner: Meta",
            "source_product_url": "https://www.arm.com/products",
            "raw_product_page": str(tmp_path / "arm.html"),
        },
        raw_path=tmp_path / "meta.html",
        body="<html><h1>Meta success story</h1></html>",
        text="Meta uses Arm technology in an official success story.",
        generated_at="2026-06-25T00:00:00Z",
    )

    assert row["source_role"] in {"official_customer_order_or_deployment_event", "supply_chain_official_relationship"}
    assert row["runtime_ready_context"] is True
    assert row["exact_value_authority"] is False
    assert row["can_support_company_exact_fact"] is False
    assert "order_value" in row["forbidden_claims"]
    assert row["counterparty"] == "Meta"


def test_extract_counterparty_from_official_news_labels() -> None:
    assert MODULE._extract_counterparty("SK hynix and NVIDIA multi-year technology partnership") == "NVIDIA"
    assert (
        MODULE._extract_counterparty("CATL and Stellantis large-scale LFP battery plant joint venture")
        == "Stellantis"
    )
    assert MODULE._extract_counterparty("CATL embedded manufacturing and local supply for AITO models") == "AITO"


def test_dedupe_rows_prefers_more_complete_counterparty_binding() -> None:
    rows = MODULE._dedupe_rows(
        [
            {
                "ticker": "300750.SZ",
                "source_url": "https://www.catl.com/en/news/6328.html",
                "structured_context_type": "official_customer_deployment_surface",
                "counterparty": "",
                "counterparty_binding_status": "not_bound",
            },
            {
                "ticker": "300750.SZ",
                "source_url": "https://www.catl.com/en/news/6328.html",
                "structured_context_type": "official_customer_deployment_surface",
                "counterparty": "Stellantis",
                "counterparty_binding_status": "counterparty_mentioned_in_snapshot",
            },
        ]
    )

    assert len(rows) == 1
    assert rows[0]["counterparty"] == "Stellantis"
