from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_sec_annual_download_config.py"
SPEC = importlib.util.spec_from_file_location("build_sec_annual_download_config", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_sec_annual_download_config_filters_to_sec_tier_rows() -> None:
    config, skipped = MODULE.build_sec_annual_download_config(
        [
            {
                "ticker": "AAA",
                "cik": "1234",
                "company_name": "AAA Corp",
                "sector": "Information Technology",
                "category": "Information Technology",
                "source_sets": ["sp500_constituent"],
                "sec_download_eligible": True,
                "universe_tier": "tier1_sp500_plus_current",
            },
            {
                "ticker": "NONUS.KS",
                "cik": "",
                "company_name": "Non-US Co",
                "sec_download_eligible": False,
                "universe_tier": "tier1_sp500_plus_current",
            },
            {
                "ticker": "TIER2",
                "cik": "5678",
                "company_name": "Tier2 Corp",
                "sec_download_eligible": True,
                "universe_tier": "tier2_supply_chain_supplement",
            },
        ],
        years=[2023, 2024],
        form_types=["10-K"],
        dataset_id="unit_dataset",
        universe_tier="tier1_sp500_plus_current",
    )

    assert config["dataset_id"] == "unit_dataset"
    assert config["source_family"] == "sec_primary_filing"
    assert config["source_tier"] == "primary_sec_filing"
    assert config["years"] == [2023, 2024]
    assert len(config["companies"]) == 1
    assert config["companies"][0]["ticker"] == "AAA"
    assert config["companies"][0]["cik"] == "0000001234"
    assert config["companies"][0]["category_slug"] == "information_technology"
    assert {row["reason"] for row in skipped} == {"not_sec_download_eligible", "outside_universe_tier"}


def test_summarize_config_reports_expected_task_count(tmp_path: Path) -> None:
    summary = MODULE.summarize_config(
        config={
            "dataset_id": "unit_dataset",
            "source_family": "sec_primary_filing",
            "source_tier": "primary_sec_filing",
            "universe_tier": "tier1",
            "years": [2023, 2024, 2025],
            "form_types": ["10-K"],
            "companies": [{"ticker": "AAA"}, {"ticker": "BBB"}],
        },
        skipped=[],
        output_path=tmp_path / "config.yaml",
        summary_path=tmp_path / "summary.json",
    )

    assert summary["status"] == "pass"
    assert summary["company_count"] == 2
    assert summary["expected_filing_tasks"] == 6


def test_build_sec_annual_download_config_respects_company_target_forms() -> None:
    config, skipped = MODULE.build_sec_annual_download_config(
        [
            {
                "ticker": "USCO",
                "cik": "1111",
                "company_name": "US Co",
                "sector": "Technology",
                "category": "Technology",
                "sec_download_eligible": True,
                "universe_tier": "tier2_supply_chain_supplement",
                "target_forms": ["10-K", "10-Q", "8-K"],
            },
            {
                "ticker": "FPI",
                "cik": "2222",
                "company_name": "Foreign Private Issuer",
                "sector": "Technology",
                "category": "Technology",
                "sec_download_eligible": True,
                "universe_tier": "tier2_supply_chain_supplement",
                "target_forms": ["20-F", "6-K"],
            },
            {
                "ticker": "INTERIM",
                "cik": "3333",
                "company_name": "Interim Only",
                "sector": "Technology",
                "category": "Technology",
                "sec_download_eligible": True,
                "universe_tier": "tier2_supply_chain_supplement",
                "target_forms": ["6-K"],
            },
        ],
        years=[2023, 2024, 2025],
        form_types=["10-K", "20-F", "40-F"],
        dataset_id="tier2_sec_annual",
        universe_tier="tier2_supply_chain_supplement",
    )

    forms_by_ticker = {row["ticker"]: row["form_types"] for row in config["companies"]}
    assert forms_by_ticker == {"USCO": ["10-K"], "FPI": ["20-F"]}
    assert {"ticker": "INTERIM", "reason": "no_annual_sec_form_type"} in skipped
    summary = MODULE.summarize_config(
        config=config,
        skipped=skipped,
        output_path=Path("config.yaml"),
        summary_path=Path("summary.json"),
    )
    assert summary["expected_filing_tasks"] == 6
