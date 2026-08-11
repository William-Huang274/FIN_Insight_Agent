from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_supply_chain_supplement_manifest.py"
SPEC = importlib.util.spec_from_file_location("build_supply_chain_supplement_manifest", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_supply_chain_supplement_rows_skips_base_and_resolves_cik() -> None:
    base = [{"ticker": "NVDA", "cik": "0001045810"}]
    config = {
        "companies": [
            {"ticker": "NVDA", "sector": "Information Technology"},
            {"ticker": "TSM", "sector": "Information Technology", "industry_group": "semiconductors", "supply_chain_role": "foundry", "priority": "p0", "target_forms": ["20-F"]},
            {"ticker": "MISSING", "sector": "Materials"},
        ],
        "global_public_disclosure_companies": [
            {
                "ticker": "005930.KS",
                "issuer_id": "KR-005930",
                "company_name": "Samsung Electronics Co., Ltd.",
                "sector": "Information Technology",
                "industry_group": "memory_semiconductors",
                "supply_chain_role": "memory_foundry",
                "priority": "p0",
                "source_family": "global_public_annual_report",
                "disclosure_profile": "kr_dart_business_report",
                "country": "South Korea",
                "listing_exchange": "KRX",
                "official_sources": [{"kind": "regulator", "url": "https://englishdart.fss.or.kr/"}],
            },
            {
                "ticker": "BAD.NONSEC",
                "issuer_id": "NO-SOURCE",
                "company_name": "No Source Public Co.",
                "sector": "Information Technology",
            },
        ],
    }
    sec_reference = {
        "TSM": {"cik": "0001046179", "company_name": "TAIWAN SEMICONDUCTOR MANUFACTURING CO LTD"}
    }

    rows, skipped = MODULE.build_supply_chain_supplement_rows(
        base_rows=base,
        supplement_config=config,
        sec_reference=sec_reference,
        source_config_ref="config.yaml",
    )

    assert len(rows) == 2
    by_ticker = {row["ticker"]: row for row in rows}
    assert by_ticker["TSM"]["cik"] == "0001046179"
    assert by_ticker["TSM"]["sec_download_eligible"] is True
    assert by_ticker["TSM"]["global_public_download_eligible"] is False
    assert by_ticker["TSM"]["supply_chain_role"] == "foundry"
    assert by_ticker["005930.KS"]["cik"] == ""
    assert by_ticker["005930.KS"]["sec_download_eligible"] is False
    assert by_ticker["005930.KS"]["global_public_download_eligible"] is True
    assert by_ticker["005930.KS"]["source_gap"] == ""
    assert by_ticker["005930.KS"]["official_sources"][0]["url"] == "https://englishdart.fss.or.kr/"
    assert {item["reason"] for item in skipped} == {"already_in_base_tier", "missing_cik_mapping", "missing_official_sources"}
