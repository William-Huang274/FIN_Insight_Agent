from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


def test_market_industry_manifest_builder_preserves_non_us_provider_symbols(tmp_path: Path) -> None:
    universe = tmp_path / "universe.jsonl"
    families = tmp_path / "families.yaml"
    output_dir = tmp_path / "out"
    universe_rows = [
        {
            "ticker": "NVDA",
            "company_name": "NVIDIA Corporation",
            "sector": "Information Technology",
            "category": "semiconductors",
            "universe_tier": "tier1",
            "sec_download_eligible": True,
            "source_sets": ["sp500_constituent"],
        },
        {
            "ticker": "005930.KS",
            "company_name": "Samsung Electronics Co., Ltd.",
            "sector": "Information Technology",
            "category": "memory_foundry_electronics",
            "universe_tier": "tier2",
            "country": "South Korea",
            "listing_exchange": "KRX",
            "reporting_currency": "KRW",
            "global_public_download_eligible": True,
            "source_sets": ["tier2_supply_chain_supplement"],
        },
        {
            "ticker": "JPM",
            "company_name": "JPMorgan Chase & Co.",
            "sector": "Financials",
            "category": "banking",
            "universe_tier": "tier1",
            "sec_download_eligible": True,
            "source_sets": ["sp500_constituent"],
        },
    ]
    universe.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in universe_rows),
        encoding="utf-8",
    )
    families.write_text(
        """
source_families:
  - source_family: industry_macro_rates_credit
    target_industries: [financials]
  - source_family: industry_industrial_macro
    target_industries: [information_technology]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python",
            "scripts/data_expansion/build_market_industry_expansion_manifests.py",
            "--universe-manifest",
            str(universe),
            "--industry-source-families",
            str(families),
            "--output-dir",
            str(output_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        text=True,
        capture_output=True,
    )
    summary = json.loads(result.stdout)

    market_csv = Path(summary["outputs"]["market_universe_csv"])
    ticker_yaml = Path(summary["outputs"]["market_yahoo_tickers_yaml"])
    industry_jsonl = Path(summary["outputs"]["industry_source_family_map"])
    with market_csv.open("r", encoding="utf-8", newline="") as handle:
        market_rows = list(csv.DictReader(handle))
    by_ticker = {row["ticker"]: row for row in market_rows}
    industry_rows = [json.loads(line) for line in industry_jsonl.read_text(encoding="utf-8").splitlines()]
    industry_by_ticker = {row["ticker"]: row for row in industry_rows}

    assert by_ticker["005930.KS"]["provider_symbol"] == "005930.KS"
    assert by_ticker["005930.KS"]["market_region"] == "non_us_local_listing"
    assert by_ticker["005930.KS"]["reporting_currency"] == "KRW"
    assert "  - ticker: 005930.KS" in ticker_yaml.read_text(encoding="utf-8")
    assert "industry_industrial_macro" in industry_by_ticker["NVDA"]["source_families"]
    assert "industry_macro_rates_credit" in industry_by_ticker["JPM"]["source_families"]
    assert summary["market"]["market_row_count"] == 3
