from __future__ import annotations

import importlib.util
from pathlib import Path

from connectors import SecFilingManifestRecord


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_builder_module():
    path = REPO_ROOT / "scripts" / "build_sec_mixed_latest_manifest.py"
    spec = importlib.util.spec_from_file_location("build_sec_mixed_latest_manifest_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_manifest_module():
    path = REPO_ROOT / "scripts" / "build_sec_manifest.py"
    spec = importlib.util.spec_from_file_location("build_sec_manifest_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _record(
    ticker: str,
    fiscal_year: int,
    form_type: str,
    fiscal_period: str = "FY",
    period_end: str | None = None,
) -> SecFilingManifestRecord:
    return SecFilingManifestRecord(
        ticker=ticker,
        fiscal_year=fiscal_year,
        category="test",
        category_slug="test",
        form_type=form_type,
        source_type=form_type,
        source_tier="primary_sec_filing",
        filing_date=period_end,
        report_date=period_end,
        period_end=period_end,
        period_type="annual" if form_type == "10-K" else "quarterly",
        duration_months=12 if form_type == "10-K" else 3,
        fiscal_period=fiscal_period,
        fiscal_year_source="document_fiscal_year_focus",
        fiscal_period_source="document_fiscal_period_focus" if form_type == "10-Q" else "form_type",
        html_path=f"/tmp/{ticker}_{fiscal_year}_{form_type}.html",
        metadata_path=f"/tmp/{ticker}_{fiscal_year}_{form_type}.metadata.json",
    )


def test_selects_latest_10q_after_each_tickers_latest_selected_10k() -> None:
    builder = _load_builder_module()
    annual = [
        _record("MSFT", 2024, "10-K"),
        _record("MSFT", 2025, "10-K"),
        _record("NVDA", 2025, "10-K"),
        _record("NVDA", 2026, "10-K"),
        _record("SNOW", 2026, "10-K"),
    ]
    interim = [
        _record("MSFT", 2026, "10-Q", "Q1", "2025-09-30"),
        _record("MSFT", 2026, "10-Q", "Q3", "2026-03-31"),
        _record("NVDA", 2026, "10-Q", "Q3", "2025-10-26"),
        _record("NVDA", 2027, "10-Q", "Q1", "2026-04-26"),
    ]

    selected, summary = builder.select_mixed_records(annual, interim, {2024, 2025, 2026})

    selected_interim = [record for record in selected if record.form_type == "10-Q"]
    assert [(record.ticker, record.fiscal_year, record.fiscal_period) for record in selected_interim] == [
        ("MSFT", 2026, "Q3"),
        ("NVDA", 2027, "Q1"),
    ]
    assert summary["form_counts"] == {"10-K": 5, "10-Q": 2}
    assert summary["interim_gaps"] == [
        {
            "ticker": "SNOW",
            "latest_annual_fiscal_year": 2026,
            "reason": "no_10q_after_latest_selected_10k",
        }
    ]


def test_manifest_dedupe_prefers_cache_path_matching_document_fiscal_year() -> None:
    manifest = _load_manifest_module()
    stale = _record("GOOGL", 2025, "10-K", "FY", "2025-12-31")
    stale.html_path = "/repo/data/raw_private/sec/2026/search_ads_cloud/GOOGL/10-K.html"
    current = _record("GOOGL", 2025, "10-K", "FY", "2025-12-31")
    current.html_path = "/repo/data/raw_private/sec/2025/search_ads_cloud/GOOGL/10-K.html"
    stale.accession_number = current.accession_number = "0001652044-26-000018"

    deduped = manifest._dedupe_manifest_records([stale, current])

    assert len(deduped) == 1
    assert deduped[0].html_path == current.html_path
