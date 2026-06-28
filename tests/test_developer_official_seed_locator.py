from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_developer_official_seed_locator.py"
SPEC = importlib.util.spec_from_file_location("build_developer_official_seed_locator", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_extract_seed_urls_from_official_page_filters_third_party_noise() -> None:
    target = {
        "ticker": "ACME",
        "company_name": "Acme Systems",
        "domains": ["acme.com"],
        "aliases": ["acme", "acme systems"],
        "family_names": ["Developer API"],
    }
    body = """
    <html><body>
      <a href="https://github.com/acme/acme-python-sdk">Acme Python SDK on GitHub</a>
      <a href="https://github.com/newrelic/newrelic-browser-agent/blob/main/docs/warning-codes.md">runtime warning</a>
      <a href="https://github.com/aFarkas/lazysizes#broken-image-symbol">lazy image helper</a>
    </body></html>
    """

    seeds = MODULE.extract_seed_urls_from_official_page(target=target, source_url="https://docs.acme.com/developers", body=body)

    assert seeds == ["https://github.com/acme/acme-python-sdk"]


def test_normalize_supported_seed_url_rejects_github_non_repo_paths() -> None:
    assert MODULE.normalize_supported_seed_url("https://github.com/orgs/Acme") == ""
    assert MODULE.normalize_supported_seed_url("https://github.com/solutions/industry") == ""
    assert MODULE.normalize_supported_seed_url("https://github.com/acme/acme-sdk/tree/main/examples") == ""
    assert MODULE.normalize_supported_seed_url("https://github.com/acme/acme-sdk") == "https://github.com/acme/acme-sdk"


def test_locate_developer_official_seeds_from_official_page(tmp_path: Path) -> None:
    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        assert timeout_s == 2
        if url == "https://acme.com/developers":
            return 200, "text/html", '<a href="https://github.com/acme/acme-js-sdk">Acme JS SDK</a>'
        return 404, "text/html", ""

    seeds, attempts = MODULE.locate_developer_official_seeds(
        targets=[
            {
                "ticker": "ACME",
                "company_name": "Acme Systems",
                "company_names": ["Acme Systems", "Acme"],
                "domains": ["acme.com"],
                "family_names": ["Developer API"],
                "aliases": ["acme", "acme systems"],
            }
        ],
        official_surface_rows=[{"ticker": "ACME", "url": "https://acme.com/developers"}],
        raw_dir=tmp_path,
        generated_at="2026-06-19T00:00:00Z",
        timeout_s=2,
        workers=1,
        max_source_pages_per_ticker=1,
        fetch=fake_fetch,
    )

    assert len(seeds) == 1
    assert seeds[0]["ticker"] == "ACME"
    assert seeds[0]["urls"] == ["https://github.com/acme/acme-js-sdk"]
    assert seeds[0]["seed_discovery_methods"] == ["official_domain_page_link"]
    assert any(attempt["status"] == "source_page_scanned" for attempt in attempts)


def test_locate_developer_official_seeds_from_verified_github_profile(tmp_path: Path) -> None:
    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        if url == "https://api.github.com/users/acme":
            return 200, "application/json", json.dumps({"login": "acme", "name": "Acme Systems", "blog": "https://acme.com"})
        if url.startswith("https://api.github.com/users/acme/repos"):
            return (
                200,
                "application/json",
                json.dumps(
                    [
                        {"name": "acme-python-sdk", "html_url": "https://github.com/acme/acme-python-sdk"},
                        {"name": ".github", "html_url": "https://github.com/acme/.github"},
                    ]
                ),
            )
        return 404, "text/html", ""

    seeds, attempts = MODULE.locate_developer_official_seeds(
        targets=[
            {
                "ticker": "ACME",
                "company_name": "Acme Systems",
                "company_names": ["Acme Systems", "Acme"],
                "domains": ["acme.com"],
                "family_names": ["Developer API"],
                "aliases": ["acme", "acme systems"],
            }
        ],
        official_surface_rows=[],
        raw_dir=tmp_path,
        generated_at="2026-06-19T00:00:00Z",
        timeout_s=2,
        workers=1,
        max_source_pages_per_ticker=0,
        max_seeds_per_ticker=2,
        fetch=fake_fetch,
    )

    assert len(seeds) == 1
    assert seeds[0]["urls"] == ["https://github.com/acme/acme-python-sdk"]
    assert seeds[0]["seed_discovery_methods"] == ["github_org_profile_verified_official_domain"]
    assert any(attempt["status"] == "verified_github_profile" for attempt in attempts)
    assert any(attempt["status"] == "repo_urls_materialized" for attempt in attempts)


def test_build_targets_uses_current_developer_gap_docket() -> None:
    targets = MODULE.build_targets(
        docket_rows=[
            {"ticker": "ACME", "company_name": "Acme Systems", "requirement_id": "developer_ecosystem_proxy"},
            {"ticker": "NOPE", "company_name": "Nope", "requirement_id": "channel_offer_proxy"},
        ],
        company_source_matrix_rows=[],
        domain_cache={"ACME": {"domains": ["acme.com"]}},
        family_assignment_rows=[{"ticker": "ACME", "family_name": "Developer API"}],
        existing_seed_rows=[],
    )

    assert len(targets) == 1
    assert targets[0]["ticker"] == "ACME"
    assert targets[0]["domains"] == ["acme.com"]
    assert "developer api" in targets[0]["aliases"]
