from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_secondary_market_public_context_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_secondary_market_public_context_rows", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_secondary_market_public_context_rows_builds_valuation_credit_and_vix_rows() -> None:
    rows = MODULE.build_secondary_market_public_context_rows(
        market_rows=[
            {
                "ticker": "MSFT",
                "value": "400",
                "period": "2026-06-30",
                "as_of_date": "2026-06-30",
                "source_url": "https://query1.finance.yahoo.com/v8/finance/chart/MSFT",
                "evidence_ref": "market-msft",
            }
        ],
        sec_financial_rows=[
            {
                "ticker": "MSFT",
                "canonical_metric_id": "financial_metric:shares_outstanding",
                "value": "1000000000",
                "unit": "shares",
                "period": "2026-FY",
                "filing_date": "2026-02-01",
                "evidence_ref": "shares-msft",
            }
        ],
        fred_latest={
            "VIXCLS": {"series_id": "VIXCLS", "label": "VIX", "date": "2026-06-30", "value": 18.2, "unit": "index_level", "source_url": "https://fred.test/VIXCLS"},
            "BAMLC0A0CM": {"series_id": "BAMLC0A0CM", "label": "IG OAS", "date": "2026-06-30", "value": 1.1, "unit": "percent", "source_url": "https://fred.test/IG"},
            "BAMLH0A0HYM2": {"series_id": "BAMLH0A0HYM2", "label": "HY OAS", "date": "2026-06-30", "value": 3.5, "unit": "percent", "source_url": "https://fred.test/HY"},
        },
        generated_at="2026-07-01T00:00:00Z",
    )

    roles = {row["pack_role"] for row in rows}
    assert roles == {"valuation_price_in", "derivatives_market_signal", "credit_funding"}
    valuation = next(row for row in rows if row["pack_role"] == "valuation_price_in")
    assert valuation["value"] == 400_000_000_000
    assert valuation["valuation_context"]["shares_source_ref"] == "shares-msft"
    assert "target-price" in valuation["claim_boundary"]
    assert "investment_recommendation" in valuation["forbidden_claims"]


def test_secondary_market_public_context_rows_uses_sec_supplemental_valuation_facts() -> None:
    rows = MODULE.build_secondary_market_public_context_rows(
        market_rows=[
            {"ticker": "ABNB", "close_price": 145.0, "as_of_date": "2026-06-30", "source_url": "https://query1.finance.yahoo.com/v8/finance/chart/ABNB"},
            {"ticker": "APP", "close_price": 320.0, "as_of_date": "2026-06-30", "source_url": "https://query1.finance.yahoo.com/v8/finance/chart/APP"},
            {"ticker": "IFX.DE", "close_price": 33.0, "as_of_date": "2026-06-30", "source_url": "https://query1.finance.yahoo.com/v8/finance/chart/IFX.DE"},
        ],
        sec_financial_rows=[],
        fred_latest={},
        supplemental_valuation_facts={
            "ABNB": {
                "fact_type": "public_float",
                "evidence_ref": "sec-float-abnb",
                "value": 75_000_000_000,
                "unit": "USD",
                "period_end": "2025-06-30",
                "filing_date": "2026-02-12",
                "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001559720.json",
                "concept": "EntityPublicFloat",
            },
            "APP": {
                "fact_type": "shares_outstanding",
                "evidence_ref": "sec-shares-app",
                "value": 340_000_000,
                "unit": "shares",
                "period_end": "2025-12-31",
                "filing_date": "2026-02-19",
                "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001751008.json",
                "concept": "CommonStockSharesOutstanding",
            },
            "IFX.DE": {
                "fact_type": "market_cap",
                "evidence_ref": "yahoo-market-cap-ifx",
                "metric_name": "trailingMarketCap",
                "value": 43_000_000_000,
                "unit": "EUR",
                "period": "2026-06-30",
                "source_url": "https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/IFX.DE",
            },
        },
        generated_at="2026-07-01T00:00:00Z",
    )

    by_ticker = {row["ticker"]: row for row in rows}
    assert by_ticker["ABNB"]["source_id"] == "sec_entity_public_float"
    assert by_ticker["ABNB"]["signal_type"] == "sec_entity_public_float_context"
    assert "complete market capitalization" in by_ticker["ABNB"]["claim_boundary"]
    assert by_ticker["APP"]["source_id"] == "public_price_x_sec_shares_market_cap"
    assert by_ticker["APP"]["value"] == 108_800_000_000
    assert by_ticker["IFX.DE"]["source_id"] == "yahoo_fundamentals_timeseries_market_cap"
    assert by_ticker["IFX.DE"]["signal_type"] == "yahoo_fundamentals_market_cap_context"
    assert "real-time flow" in by_ticker["IFX.DE"]["claim_boundary"]
