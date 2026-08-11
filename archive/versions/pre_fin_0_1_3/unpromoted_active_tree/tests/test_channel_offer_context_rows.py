from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_channel_offer_context_rows.py"
SPEC = importlib.util.spec_from_file_location("build_channel_offer_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _cdw_product_html(
    *,
    product_name: str = "HP EliteBook 8 G1a 16in Touchscreen Copilot+ PC Notebook",
    brand: str = "HP Inc",
    price: str = "2129.99",
    stock: str = "In Stock",
    rating: str = "4.3",
    review_count: str = "6",
) -> str:
    return f"""
    <html><head>
      <title>{product_name} - CDW.com</title>
      <script>
        window.cdwTagManagementData = {{
          'page_type':'PRODUCT',
          'product_id':'8361975',
          'product_name':'{product_name}',
          'product_price':'{price}',
          'product_stock_status':'{stock}',
          'product_brand_name':'HP Smart Buy Notebooks',
          'product_root_brand_name':'{brand}',
          'product_category':'Computers',
          'total_review_count':'{review_count}',
          'average_overall_rating':'{rating}',
          'product_has_review':'True'
        }};
      </script>
    </head>
    <body>
      <h1 itemprop="name">{product_name}</h1>
      <span itemprop="sku">8361975</span>
      <span itemprop="mpn">B12ABC</span>
      <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
        <meta itemprop="availability" content="https://schema.org/InStock" />
        <meta itemprop="priceCurrency" content="USD" />
        <meta itemprop="price" content="{price}" />
      </div>
    </body></html>
    """


def test_build_channel_offer_context_rows_with_cdw_fixture_fetch(tmp_path: Path) -> None:
    search_url = MODULE.cdw_search_url("hp elitebook cdw")
    product_url = "https://www.cdw.com/product/hp-elitebook-8-g1a-16-touchscreen-copilot-pc-notebook/8361975"

    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        assert timeout_s == 3
        if url == search_url:
            return 200, "text/html", f'<a href="/product/hp-elitebook-8-g1a-16-touchscreen-copilot-pc-notebook/8361975">HP</a>'
        if url == product_url:
            return 200, "text/html", _cdw_product_html()
        raise AssertionError(f"unexpected url: {url}")

    result = MODULE.build_channel_offer_context_rows(
        probes=[
            {
                "ticker": "HPQ",
                "company_name": "HP Inc",
                "company_names": ["HP", "HP Inc"],
                "product_terms": ["EliteBook", "Copilot PC"],
                "search_query": "hp elitebook cdw",
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=3,
        fetch=fake_fetch,
    )

    rows = result["rows"]
    assert {row["structured_context_type"] for row in rows} == {
        "channel_offer_context",
        "platform_review_ranking_context",
    }
    channel = next(row for row in rows if row["structured_context_type"] == "channel_offer_context")
    review = next(row for row in rows if row["structured_context_type"] == "platform_review_ranking_context")
    assert channel["source_id"] == MODULE.CHANNEL_SOURCE_ID
    assert review["source_id"] == MODULE.REVIEW_SOURCE_ID
    assert channel["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert channel["product_binding_status"] == "product_mentioned_in_snapshot"
    assert review["product_binding_status"] == "product_mentioned_in_snapshot"
    assert channel["exact_value_authority"] is False
    assert "sell-through" in channel["structured_context_summary"]
    assert Path(channel["raw_path"]).exists()


def test_channel_offer_coverage_gate_passes_with_channel_and_review_rows(tmp_path: Path) -> None:
    product_url = "https://www.cdw.com/product/hp-elitebook-8-g1a-16-touchscreen-copilot-pc-notebook/8361975"
    result = MODULE.build_channel_offer_context_rows(
        probes=[
            {
                "ticker": "HPQ",
                "company_name": "HP Inc",
                "company_names": ["HP", "HP Inc"],
                "product_terms": ["EliteBook", "Copilot PC"],
                "urls": [product_url],
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        fetch=lambda url, timeout_s: (200, "text/html", _cdw_product_html()),
    )
    source_rows = [
        {
            "source_id": MODULE.CHANNEL_SOURCE_ID,
            "layer_id": "L3",
            "evidence_graph_status": "runtime_ready_context",
            "can_crawl_or_download": True,
            "can_structure": True,
            "runtime_ready_context": True,
            "exact_value_authority_ready": False,
            "can_support_company_exact_fact": False,
        },
        {
            "source_id": MODULE.REVIEW_SOURCE_ID,
            "layer_id": "L3",
            "evidence_graph_status": "runtime_ready_context",
            "can_crawl_or_download": True,
            "can_structure": True,
            "runtime_ready_context": True,
            "exact_value_authority_ready": False,
            "can_support_company_exact_fact": False,
        },
    ]

    coverage = MODULE.build_channel_offer_coverage_gate(
        context_rows=result["rows"],
        source_layer_rows=source_rows,
        generated_at="2026-06-17T00:00:00Z",
    )
    statuses = {row["requirement_id"]: row["status"] for row in coverage["requirements"]}
    assert statuses["channel_offer_proxy"] == "pass"
    assert statuses["platform_review_proxy"] == "pass"


def test_channel_offer_backfill_skips_product_mismatch(tmp_path: Path) -> None:
    result = MODULE.build_channel_offer_context_rows(
        probes=[
            {
                "ticker": "DELL",
                "company_name": "Dell Technologies",
                "company_names": ["Dell"],
                "product_terms": ["PowerEdge"],
                "urls": ["https://www.cdw.com/product/kingston-memory/5843897"],
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        fetch=lambda url, timeout_s: (
            200,
            "text/html",
            _cdw_product_html(product_name="Kingston DDR4 Memory", brand="Kingston", price="536.99", stock="4-6+ Weeks", rating="0", review_count="0"),
        ),
    )

    assert result["rows"] == []
    assert result["attempts"][0]["status"] == "skipped_product_mismatch"


def test_channel_offer_backfill_does_not_match_broad_category_only(tmp_path: Path) -> None:
    result = MODULE.build_channel_offer_context_rows(
        probes=[
            {
                "ticker": "DELL",
                "company_name": "Dell Technologies",
                "company_names": ["Dell"],
                "product_terms": ["PowerEdge", "server", "rack-mountable"],
                "urls": ["https://www.cdw.com/product/dell-memory-upgrade/8243484"],
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        fetch=lambda url, timeout_s: (
            200,
            "text/html",
            _cdw_product_html(product_name="Dell Memory Upgrade - 16 GB DDR5 RDIMM", brand="Dell", price="1565.99", stock="4-6+ Weeks", rating="0", review_count="0"),
        ),
    )

    assert result["rows"] == []
    assert result["attempts"][0]["status"] == "skipped_product_mismatch"


def test_channel_offer_backfill_allows_brand_only_for_broad_batch_probe(tmp_path: Path) -> None:
    result = MODULE.build_channel_offer_context_rows(
        probes=[
            {
                "ticker": "AVGO",
                "company_name": "Broadcom",
                "company_names": ["Broadcom", "AVGO"],
                "product_terms": ["datacenter networking", "Ethernet switch"],
                "allow_brand_only_match": True,
                "urls": ["https://www.cdw.com/product/broadcom-network-adapter/8035678"],
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        fetch=lambda url, timeout_s: (
            200,
            "text/html",
            _cdw_product_html(
                product_name="Broadcom P1400GD - network adapter - PCIe 5.0 x16",
                brand="Broadcom",
                price="899.99",
                stock="In Stock",
                rating="0",
                review_count="0",
            ),
        ),
    )

    assert any(row["structured_context_type"] == "channel_offer_context" for row in result["rows"])
    assert result["attempts"][0]["status"] == "materialized"


def test_channel_offer_backfill_does_not_bind_compatible_third_party_title(tmp_path: Path) -> None:
    result = MODULE.build_channel_offer_context_rows(
        probes=[
            {
                "ticker": "DELL",
                "company_name": "Dell Technologies",
                "company_names": ["Dell"],
                "product_terms": ["PowerEdge", "server", "rack-mountable"],
                "urls": ["https://www.cdw.com/product/total-micro-memory-dell-poweredge/2968104"],
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        fetch=lambda url, timeout_s: (
            200,
            "text/html",
            _cdw_product_html(
                product_name="Total Micro Memory, Dell PowerEdge M820, R620, R820, T620 - 16GB",
                brand="Total Micro",
                price="53.99",
                stock="In Stock",
                rating="4.7",
                review_count="3",
            ),
        ),
    )

    assert result["rows"] == []
    assert result["attempts"][0]["status"] == "skipped_product_mismatch"
