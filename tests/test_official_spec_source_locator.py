from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_official_spec_source_locator.py"
)
SPEC = importlib.util.spec_from_file_location("build_official_spec_source_locator", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_locator_accepts_same_domain_spec_links_and_rejects_off_domain(tmp_path: Path) -> None:
    raw = tmp_path / "nvda.html"
    raw.write_text(
        """
        <html><body>
          <a href="/en-us/data-center/h100/specifications/">H100 specifications</a>
          <a href="https://example.com/h100-datasheet">third party datasheet</a>
          <a href="/en-us/privacy/">Privacy</a>
        </body></html>
        """,
        encoding="utf-8",
    )
    rows, diagnostics = MODULE.build_official_spec_source_locator_candidates(
        product_pages=[
            {
                "ticker": "NVDA",
                "company": "NVIDIA Corporation",
                "product": "GPU / accelerator",
                "source_url": "https://www.nvidia.com/en-us/data-center/h100/",
                "raw_path": str(raw),
            }
        ],
        route_plan_rows=[
            {
                "ticker": "NVDA",
                "route_id": "technical_product_spec",
                "route_status": "not_materialized",
                "family_id": "gpu_accelerator",
                "family_name": "GPU / Accelerator",
                "query_terms": ["GPU", "H100"],
            }
        ],
        generated_at="2026-06-25T00:00:00Z",
    )
    assert diagnostics["link_count"] == 3
    assert len(rows) == 1
    assert rows[0]["candidate_url"] == "https://www.nvidia.com/en-us/data-center/h100/specifications/"
    assert rows[0]["source_role"] == "technical_product_spec"
    assert rows[0]["materialization_status"] == "candidate_not_fetched"
    assert "off_domain" in diagnostics["rejection_reasons"]


def test_locator_finds_v7_business_asset_profile_links(tmp_path: Path) -> None:
    raw = tmp_path / "utility.html"
    raw.write_text(
        """
        <html><body>
          <a href="/projects/solar-fleet-capacity">Solar fleet capacity projects</a>
          <a href="/investors/events">Investor events</a>
        </body></html>
        """,
        encoding="utf-8",
    )
    rows, _ = MODULE.build_official_spec_source_locator_candidates(
        product_pages=[
            {
                "ticker": "NEE",
                "company": "NextEra Energy",
                "product": "Renewable Power / Solar / Hydrogen",
                "source_url": "https://www.nexteraenergy.com/renewables/",
                "raw_path": str(raw),
            }
        ],
        route_plan_rows=[
            {
                "ticker": "NEE",
                "route_id": "business_asset_profile_spec",
                "route_status": "not_materialized",
                "family_id": "renewable_power_solar_hydrogen",
                "family_name": "Renewable Power / Solar / Hydrogen",
                "query_terms": ["renewable", "solar", "fleet"],
            }
        ],
        generated_at="2026-06-25T00:00:00Z",
    )
    assert len(rows) == 1
    assert rows[0]["source_id"] == "official_project_pages"
    assert rows[0]["source_role"] == "business_asset_profile_spec"
