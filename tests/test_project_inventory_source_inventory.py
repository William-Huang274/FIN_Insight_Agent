import json
from pathlib import Path

from sec_agent.project_inventory import build_project_inventory, inventory_brief, inventory_prompt


def test_project_inventory_registers_market_industry_context_only_artifacts(tmp_path: Path) -> None:
    summary_path = tmp_path / "market_industry_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "market": {
                    "company_count": 603,
                    "market_row_count": 603,
                    "provider_symbol_count": 603,
                    "non_us_provider_symbol_count": 15,
                    "currency_counts": {"USD": 588, "JPY": 5},
                    "known_limitations": ["Yahoo chart is market_snapshot context only."],
                },
                "industry": {
                    "company_count": 603,
                    "mapped_company_count": 603,
                    "source_family_company_counts": {
                        "industry_macro_rates_credit": 203,
                        "industry_utilities_power_demand": 164,
                    },
                    "known_limitations": ["Industry rows cannot prove company-level facts."],
                },
                "outputs": {
                    "market_universe_csv": "data/manifests/tier1_tier2_market_universe_v0_1.csv",
                    "industry_source_family_map": "data/manifests/tier1_tier2_industry_source_family_map_v0_1.jsonl",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    inventory = build_project_inventory(
        [
            {
                "ticker": "NVDA",
                "company": "NVIDIA CORP",
                "fiscal_year": 2025,
                "category": "semiconductors",
                "form_type": "10-K",
                "source_type": "10-K",
                "source_tier": "primary_sec_filing",
            }
        ],
        manifest_path="data/manifests/sec.jsonl",
        bm25_index_dir="data/indexes/bm25/sec",
        object_bm25_index_dir="data/indexes/sqlite_fts/sec_objects",
        bge_model="BAAI/bge-reranker-v2-m3",
        market_evidence_path="data/processed_private/market/evidence_packs/market_v1.jsonl",
        market_catalog_path="data/processed_private/market/catalog.duckdb",
        market_snapshot_id="market_v1",
        market_as_of_date="2026-06-06",
        industry_evidence_path="data/processed_private/industry/industry_evidence_rows.jsonl",
        industry_snapshot_db_path="data/processed_private/industry/industry_snapshot.duckdb",
        industry_snapshot_id="industry_v1",
        industry_as_of_date="2026-06-06",
        market_industry_manifest_summary_path=str(summary_path),
    )

    assert {"primary_sec_filing", "market_snapshot", "industry_snapshot"} <= set(inventory["available_source_families"])
    assert inventory["market_snapshot"]["context_only"] is True
    assert inventory["market_snapshot"]["status"] == "available"
    assert inventory["market_snapshot"]["evidence_path"].endswith("market_v1.jsonl")
    assert inventory["market_snapshot"]["catalog_path"].endswith("catalog.duckdb")
    assert inventory["industry_snapshot"]["context_only"] is True
    assert inventory["industry_snapshot"]["snapshot_db_path"].endswith("industry_snapshot.duckdb")
    assert inventory["source_boundaries"]["market_snapshot"]["allowed_claim_scope"] == "market_or_valuation_context_only"
    assert inventory["source_boundaries"]["industry_snapshot"]["allowed_claim_scope"] == "industry_context_only"

    brief = inventory_brief(inventory)
    assert "market_snapshot" in brief["available_source_families"]
    assert brief["market_snapshot"]["company_count"] == 603
    assert brief["industry_snapshot"]["source_family_company_counts"]["industry_macro_rates_credit"] == 203

    prompt = inventory_prompt(inventory, selected_tickers=["NVDA"], selected_years=[2025])
    assert "CONTEXT-ONLY SOURCE FAMILIES" in prompt
    assert "market_snapshot | status=available" in prompt
    assert "industry_snapshot | status=available" in prompt
    assert "market_snapshot is context-only market or valuation evidence" in prompt
    assert "industry_snapshot is context-only industry, macro, regulatory, or demand evidence" in prompt
    assert "cannot prove company-reported fundamentals" in prompt


def test_project_inventory_infers_sec_form_type_from_evidence_id_when_form_type_is_missing() -> None:
    inventory = build_project_inventory(
        [
            {
                "ticker": "AMZN",
                "company": "AMAZON.COM INC",
                "fiscal_year": 2025,
                "source_tier": "primary_sec_filing",
                "evidence_id": "AMZN_2025_10K_ITEM7_BLOCK_0001_CHUNK_0001",
            },
            {
                "ticker": "AMZN",
                "company": "AMAZON.COM INC",
                "fiscal_year": 2026,
                "evidence_id": "AMZN_2026_8K_ITEM2_02_BLOCK_0001_CHUNK_0001",
            },
        ],
        manifest_path="data/evidence/sec.jsonl",
        bm25_index_dir="data/indexes/bm25/sec",
        object_bm25_index_dir="data/indexes/sqlite_fts/sec_objects",
        bge_model="BAAI/bge-reranker-v2-m3",
    )

    assert inventory["form_types"] == {"10-K": 1, "8-K": 1}
    company = inventory["companies"][0]
    assert company["form_types"] == ["10-K", "8-K"]
    assert company["source_tiers"] == ["company_authored_unaudited_sec_filing", "primary_sec_filing"]
    assert {(filing["year"], filing["form_type"], filing["source_tier"]) for filing in company["filings"]} == {
        (2025, "10-K", "primary_sec_filing"),
        (2026, "8-K", "company_authored_unaudited_sec_filing"),
    }
