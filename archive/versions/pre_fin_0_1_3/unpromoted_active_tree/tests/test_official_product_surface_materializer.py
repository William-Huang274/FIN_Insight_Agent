from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "materialize_official_product_surface_pages.py"
SPEC = importlib.util.spec_from_file_location("materialize_official_product_surface_pages", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_materialize_official_product_surface_pages_fetches_allowed_company_domain(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    clean_dir = tmp_path / "clean"

    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        assert timeout_s == 3
        return (
            200,
            "text/html",
            """
            <html>
              <head><title>Alpha Product Portfolio</title><script>ignore()</script></head>
              <body><h1>Alpha Accelerator</h1><p>Alpha Accelerator has 192GB memory and rack-scale networking.</p></body>
            </html>
            """,
        )

    result = MODULE.materialize_official_product_surface_pages(
        profiles={
            "ALP": {
                "ticker": "ALP",
                "company_name": "Alpha Corp.",
                "company_domains": ["alpha.example"],
                "official_product_urls": ["https://www.alpha.example/products"],
                "official_product_surfaces": ["Alpha Accelerator"],
            }
        },
        existing_rows=[],
        tickers=["ALP"],
        raw_dir=raw_dir,
        clean_dir=clean_dir,
        generated_at="2026-06-16T00:00:00Z",
        timeout_s=3,
        min_clean_text_chars=20,
        fetch=fake_fetch,
    )

    summary = result["summary"]
    rows = result["rows"]
    assert summary["new_materialized_count"] == 1
    assert summary["failed_count"] == 0
    assert rows[0]["ticker"] == "ALP"
    assert rows[0]["product"] == "Alpha Accelerator"
    assert Path(rows[0]["raw_path"]).exists()
    assert Path(rows[0]["clean_text_path"]).read_text(encoding="utf-8")
    assert "ignore()" not in Path(rows[0]["clean_text_path"]).read_text(encoding="utf-8")


def test_materialize_official_product_surface_pages_blocks_non_company_domain(tmp_path: Path) -> None:
    called = False

    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        nonlocal called
        called = True
        return 200, "text/html", "<html></html>"

    result = MODULE.materialize_official_product_surface_pages(
        profiles={
            "ALP": {
                "ticker": "ALP",
                "company_name": "Alpha Corp.",
                "company_domains": ["alpha.example"],
                "official_product_urls": ["https://untrusted.example/products"],
            }
        },
        existing_rows=[],
        raw_dir=tmp_path / "raw",
        clean_dir=tmp_path / "clean",
        generated_at="2026-06-16T00:00:00Z",
        fetch=fake_fetch,
    )

    assert called is False
    assert result["summary"]["blocked_count"] == 1
    assert result["rows"] == []


def test_materialize_official_product_surface_pages_rejects_blocked_or_too_short_pages(tmp_path: Path) -> None:
    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        return 200, "text/html", "<html><title>Your request has been blocked.</title><body>blocked</body></html>"

    result = MODULE.materialize_official_product_surface_pages(
        profiles={
            "ALP": {
                "ticker": "ALP",
                "company_name": "Alpha Corp.",
                "company_domains": ["alpha.example"],
                "official_product_urls": ["https://www.alpha.example/products"],
            }
        },
        existing_rows=[],
        raw_dir=tmp_path / "raw",
        clean_dir=tmp_path / "clean",
        generated_at="2026-06-16T00:00:00Z",
        fetch=fake_fetch,
    )

    assert result["summary"]["failed_count"] == 1
    assert result["summary"]["attempts"][0]["reason"] == "blocked_or_non_content_page"
    assert result["rows"] == []


def test_materialize_official_product_surface_pages_skip_existing(tmp_path: Path) -> None:
    existing = {
        "ticker": "ALP",
        "company": "Alpha Corp.",
        "product": "Alpha Accelerator",
        "source_url": "https://www.alpha.example/products",
        "raw_path": str(tmp_path / "old.html"),
        "clean_text_path": str(tmp_path / "old.txt"),
    }
    called = False

    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        nonlocal called
        called = True
        return 200, "text/html", "<html></html>"

    result = MODULE.materialize_official_product_surface_pages(
        profiles={
            "ALP": {
                "ticker": "ALP",
                "company_name": "Alpha Corp.",
                "company_domains": ["alpha.example"],
                "official_product_urls": ["https://www.alpha.example/products"],
            }
        },
        existing_rows=[existing],
        raw_dir=tmp_path / "raw",
        clean_dir=tmp_path / "clean",
        generated_at="2026-06-16T00:00:00Z",
        skip_existing=True,
        fetch=fake_fetch,
    )

    assert called is False
    assert result["summary"]["skipped_existing_count"] == 1
    assert result["rows"] == [existing]
