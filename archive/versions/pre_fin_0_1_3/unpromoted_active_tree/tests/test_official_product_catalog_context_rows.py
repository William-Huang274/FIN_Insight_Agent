from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_official_product_catalog_context_rows.py"
SPEC = importlib.util.spec_from_file_location("build_official_product_catalog_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_official_product_catalog_parser_binds_consumer_device_families() -> None:
    rows = MODULE.build_official_product_catalog_context_rows(
        page_rows=[
            {
                "ticker": "AAPL",
                "company": "Apple Inc.",
                "product": "Apple",
                "source_url": "https://www.apple.com/products",
                "title": "Apple",
                "body": """
                <html><body>
                  <a href="/iphone/">iPhone</a>
                  <a href="/ipad/">iPad</a>
                  <a href="/mac/">Mac</a>
                  <a href="/watch/">Apple Watch</a>
                  <a href="/airpods/">AirPods</a>
                  <a href="/legal/privacy/">Privacy Policy</a>
                </body></html>
                """,
            }
        ],
        family_assignments=[
            {
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "family_id": "smartphones_tablets",
                "family_name": "Smartphones / Tablets",
                "query_terms": ["smartphone", "iPhone", "tablet"],
                "family_aliases": ["iphone", "ipad", "phone", "tablet"],
            },
            {
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "family_id": "pcs_peripherals",
                "family_name": "PCs / Peripherals",
                "query_terms": ["PC", "laptop"],
                "family_aliases": ["mac", "notebook", "laptop"],
            },
            {
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "family_id": "wearables_devices",
                "family_name": "Wearables / Smart Devices",
                "query_terms": ["wearable", "watch"],
                "family_aliases": ["watch", "airpods"],
            },
        ],
        generated_at="2026-06-18T00:00:00Z",
    )

    by_pair = {(row["family_id"], row["product_or_segment"]) for row in rows}
    assert ("smartphones_tablets", "iPhone") in by_pair
    assert ("smartphones_tablets", "iPad") in by_pair
    assert ("pcs_peripherals", "Mac") in by_pair
    assert ("wearables_devices", "Apple Watch") in by_pair
    assert ("wearables_devices", "AirPods") in by_pair
    assert all("privacy" not in row["product_or_segment"].lower() for row in rows)


def test_official_product_catalog_parser_binds_single_family_by_default() -> None:
    rows = MODULE.build_official_product_catalog_context_rows(
        page_rows=[
            {
                "ticker": "ADM",
                "company": "Archer Daniels Midland",
                "product": "Products and Services",
                "source_url": "https://www.adm.com/en-us/products-services",
                "title": "ADM Products and Services",
                "body": """
                <html><body>
                  <h2>Human Nutrition</h2>
                  <a href="/en-us/products-services/animal-nutrition">Animal Nutrition</a>
                  <a href="/en-us/products-services/flavors">Flavors</a>
                </body></html>
                """,
            }
        ],
        family_assignments=[
            {
                "ticker": "ADM",
                "company_name": "Archer Daniels Midland",
                "family_id": "agriculture_commodities_ingredients",
                "family_name": "Agriculture Commodities / Ingredients",
                "query_terms": ["agriculture", "ingredients", "nutrition"],
                "family_aliases": ["nutrition", "flavors"],
            }
        ],
        generated_at="2026-06-18T00:00:00Z",
    )

    names = {row["product_or_segment"] for row in rows}
    assert {"Human Nutrition", "Animal Nutrition", "Flavors"}.issubset(names)
    assert {row["family_id"] for row in rows} == {"agriculture_commodities_ingredients"}
