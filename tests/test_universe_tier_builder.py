from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_universe_tiers.py"
SPEC = importlib.util.spec_from_file_location("build_universe_tiers", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_dedupe_rows_by_cik_preserves_current_ticker_and_alternates() -> None:
    rows = [
        {
            "ticker": "GOOG",
            "cik": "0001652044",
            "company_name": "Alphabet Inc. Class C",
            "source_sets": ["sp500_constituent"],
        },
        {
            "ticker": "GOOGL",
            "cik": "0001652044",
            "company_name": "Alphabet Inc. Class A",
            "source_sets": ["current_full238"],
        },
    ]

    result = MODULE._dedupe_rows(rows, tier="tier1_sp500_plus_current", dedupe_by_cik=True)

    assert len(result) == 1
    assert result[0]["ticker"] == "GOOGL"
    assert result[0]["alternate_tickers"] == ["GOOG"]
    assert set(result[0]["source_sets"]) == {"sp500_constituent", "current_full238"}
