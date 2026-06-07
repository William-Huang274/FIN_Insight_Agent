from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_sec_full_source_expansion_configs.py"
SPEC = importlib.util.spec_from_file_location("build_sec_full_source_expansion_configs", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_sec_full_source_configs_splits_tier1_and_tier2_forms() -> None:
    configs = MODULE.build_sec_full_source_configs(
        tier1_rows=[
            {
                "ticker": "AAA",
                "cik": "1234",
                "company_name": "AAA Corp",
                "sector": "Technology",
                "category": "Technology",
                "sec_download_eligible": True,
                "universe_tier": "tier1_sp500_plus_current",
            }
        ],
        tier2_rows=[
            {
                "ticker": "US2",
                "cik": "5678",
                "company_name": "US Tier2",
                "sector": "Technology",
                "category": "Technology",
                "sec_download_eligible": True,
                "universe_tier": "tier2_supply_chain_supplement",
                "target_forms": ["10-K", "10-Q", "8-K"],
            },
            {
                "ticker": "FPI",
                "cik": "9999",
                "company_name": "Foreign Issuer",
                "sector": "Technology",
                "category": "Technology",
                "sec_download_eligible": True,
                "universe_tier": "tier2_supply_chain_supplement",
                "target_forms": ["20-F", "6-K"],
            },
        ],
        interim_years=[2026],
        event_years=[2026],
    )

    assert configs["tier1_sp500_us_interim_10q_fy2026_2027"]["companies"][0]["ticker"] == "AAA"
    assert configs["tier1_sp500_us_8k_earnings_2026_2027"]["companies"][0]["source_sets"] == []
    assert configs["tier2_supply_chain_sec_interim_10q_fy2026_2027"]["companies"][0]["ticker"] == "US2"
    assert configs["tier2_supply_chain_sec_8k_earnings_2026_2027"]["companies"][0]["ticker"] == "US2"
    assert configs["tier2_supply_chain_sec_6k_2026_2027"]["status"] == "reserved_parser_gap"
    assert configs["tier2_supply_chain_sec_6k_2026_2027"]["companies"][0]["ticker"] == "FPI"


def test_summarize_configs_counts_expected_tasks(tmp_path: Path) -> None:
    configs = {
        "unit": {
            "dataset_id": "unit",
            "status": "active",
            "years": [2026, 2027],
            "form_types": ["10-Q"],
            "companies": [{"ticker": "AAA", "target_forms": ["10-Q"]}, {"ticker": "BBB", "target_forms": ["10-Q"]}],
        }
    }

    summary = MODULE.summarize_configs(configs, outputs={"unit": "unit.yaml"}, summary_path=tmp_path / "summary.json")

    assert summary["status"] == "pass"
    assert summary["configs"]["unit"]["expected_tasks"] == 4
    assert summary["covered_company_count"] == 2
