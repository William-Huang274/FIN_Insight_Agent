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


def test_project_inventory_registers_product_graph_and_public_source_context(tmp_path: Path) -> None:
    product_summary = tmp_path / "product_graph_summary.json"
    product_summary.write_text(
        json.dumps(
            {
                "company_count": 603,
                "companies_with_sec_verified_product_kpi": 186,
                "evidence_node_count": 5873,
                "gap_count": 2979,
                "node_promotion_counts": {
                    "runtime_fact_allowed": 186,
                    "context_or_lead_available": 5009,
                    "review_queue_not_runtime_fact": 112,
                },
                "gap_type_counts": {"commercial_market_tracker_gap_after_public_source_check": 2562},
                "outputs": {
                    "graph": "Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_final_public_repair_v0_1/company_product_evidence_graph_v0_1.jsonl",
                    "nodes": "Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_final_public_repair_v0_1/company_product_evidence_nodes_v0_1.jsonl",
                    "gaps": "Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_final_public_repair_v0_1/company_product_evidence_gaps_v0_1.jsonl",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    public_summary = tmp_path / "public_inventory_summary.json"
    public_summary.write_text(
        json.dumps(
            {
                "promoted_inventory_row_count": 1103,
                "bounded_evidence_eligible_row_count": 3,
                "exact_value_authority_row_count": 0,
                "promotion_counts_by_source_family": {"macro_industry_indicator": 3},
                "outputs": {"public_source_inventory_rows": "data/processed_private/public_sources/rows.jsonl"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    normalized_summary = tmp_path / "normalized_summary.json"
    normalized_summary.write_text(
        json.dumps(
            {
                "normalized_record_count": 404,
                "evidence_row_count": 22,
                "successful_source_count": 22,
                "successful_sources": ["fred_api", "openfda_api"],
                "source_family_counts": {"macro_industry_indicator": 243, "official_product_status": 18},
                "claim_boundary": ["Public rows are context only."],
                "outputs": {"evidence_rows": "Z:/FIN_Insight_Agent_data/public/evidence_rows.jsonl"},
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
        product_evidence_graph_summary_path=str(product_summary),
        product_evidence_facts_path="Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_final_public_repair_v0_1.jsonl",
        public_source_inventory_summary_path=str(public_summary),
        public_source_normalized_snapshot_summary_path=str(normalized_summary),
    )

    assert {"company_product_evidence_graph", "public_source_context"} <= set(inventory["available_source_families"])
    assert inventory["product_evidence_graph"]["runtime_fact_company_count"] == 186
    assert inventory["product_evidence_graph"]["claim_boundary"]["runtime_fact_allowed"].startswith("company-disclosed")
    assert inventory["public_source_context"]["context_only"] is True
    assert inventory["public_source_context"]["bounded_evidence_eligible_row_count"] == 3
    assert inventory["source_boundaries"]["company_product_evidence_graph"]["feature_flag_required"] is True
    assert inventory["source_boundaries"]["public_source_context"]["context_only"] is True

    brief = inventory_brief(inventory)
    assert brief["schema_version"] == "project_inventory_brief_v0.2"
    assert brief["product_evidence_graph"]["gap_count"] == 2979
    assert brief["public_source_context"]["normalized_record_count"] == 404
    assert brief["source_family_authority"]["public_source_context"]["exact_value_authority"] is False

    prompt = inventory_prompt(inventory, selected_tickers=["NVDA"], selected_years=[2025])
    assert "company_product_evidence_graph | status=available" in prompt
    assert "public_source_context | status=available" in prompt
    assert "runtime_fact_allowed" in prompt
    assert "cannot prove company-reported product sales" in prompt


def test_inventory_brief_v02_exposes_milvus_web_and_playbook_without_private_paths(tmp_path: Path) -> None:
    milvus_summary = tmp_path / "milvus_summary.json"
    milvus_summary.write_text(
        json.dumps(
            {
                "status": "cloud_available",
                "location": "cloud",
                "collection": "typed_sec_evidence_v0",
                "vector_kinds": ["narrative_chunk", "relationship_context"],
                "vector_count": 12345,
                "materialized_at": "2026-06-12",
                "schema_digest": "milvus_schema_digest_1",
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
        manifest_path="data/raw_private/sec_manifest.jsonl",
        bm25_index_dir="data/indexes/bm25/sec",
        object_bm25_index_dir="data/indexes/sqlite_fts/sec_objects",
        bge_model="BAAI/bge-reranker-v2-m3",
        milvus_summary_path=str(milvus_summary),
        live_public_web_policy_ids=["major_financial_news", "company_official_product_surface"],
    )

    brief = inventory_brief(inventory)
    payload = json.dumps(brief, ensure_ascii=False)

    assert brief["schema_version"] == "project_inventory_brief_v0.2"
    assert "milvus_semantic" in brief["available_source_families"]
    assert brief["milvus_runtime"]["status"] == "cloud_available"
    assert brief["milvus_runtime"]["exact_value_authority"] is False
    assert brief["milvus_runtime"]["vector_count"] == 12345
    assert brief["milvus_runtime"]["schema_digest"] == "milvus_schema_digest_1"
    assert brief["milvus_runtime"]["fallback_routes"] == ["bm25", "object_bm25", "exact_value_ledger"]
    assert brief["milvus_runtime"]["claim_boundary"] == "semantic_recall_supplement_not_exact_value_authority"
    assert brief["source_family_availability"]["milvus_semantic"]["location"] == "cloud"
    assert brief["live_public_web_context"]["status"] == "policy_available"
    assert brief["source_family_availability"]["live_public_web_context"]["web_scope_policy_ids"] == [
        "major_financial_news",
        "company_official_product_surface",
    ]
    assert brief["playbook_candidates"][0]["playbook_id"] == "semiconductors"
    assert "company_product_evidence_graph" in brief["playbook_candidates"][0]["default_source_families"]
    assert brief["playbook_candidates"][0]["specialist_routing"]["product_technology_analyst"] == "high"
    assert "playbooks" in brief["playbook_registry"]
    assert "data/raw_private" not in payload
    assert "data/indexes" not in payload
    assert str(milvus_summary) not in payload


def test_project_inventory_uses_generic_playbook_for_uncovered_industry() -> None:
    inventory = build_project_inventory(
        [
            {
                "ticker": "XYZ",
                "company": "XYZ CORP",
                "fiscal_year": 2025,
                "category": "miscellaneous services",
                "form_type": "10-K",
                "source_type": "10-K",
                "source_tier": "primary_sec_filing",
            }
        ],
        manifest_path="manifest.jsonl",
        bm25_index_dir="bm25",
        object_bm25_index_dir="objects",
        bge_model="BAAI/bge-reranker-v2-m3",
    )

    brief = inventory_brief(inventory)

    assert brief["playbook_candidates"][0]["playbook_id"] == "generic_public_research"
    assert brief["playbook_candidates"][0]["coverage_gap"]["gap_type"] == "industry_playbook_not_matched"
