from __future__ import annotations

import json
from pathlib import Path

from sec_agent.entity_master import (
    ENTITY_SECURITY_MASTER_SCHEMA_VERSION,
    build_entity_security_master,
    resolve_entity_reference,
)
from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph, make_multi_agent_smoke_state
from sec_agent.project_inventory import build_project_inventory
from sec_agent.source_capability_router import SOURCE_CAPABILITY_ROUTER_SCHEMA_VERSION, build_source_capability_router


def test_entity_security_master_uses_inventory_identifiers_and_aliases() -> None:
    inventory = build_project_inventory(
        [
            {
                "ticker": "MSFT",
                "company": "Microsoft Corporation",
                "cik": "789019",
                "lei": "INR2EJN1ERAN0W5ZP974",
                "figi": "BBG000BPH459",
                "aliases": ["Microsoft Corp."],
                "fiscal_year": 2025,
                "form_type": "10-K",
                "source_tier": "primary_sec_filing",
            }
        ],
        manifest_path="data/manifests/sec.jsonl",
        bm25_index_dir="data/indexes/bm25/sec",
        object_bm25_index_dir="data/indexes/sqlite_fts/sec_objects",
        bge_model="BAAI/bge-reranker-v2-m3",
    )

    master = build_entity_security_master(
        {
            "project_inventory": inventory,
            "query_contract": {"companies": ["Microsoft Corp"], "focus_tickers": ["MSFT"]},
        }
    )
    entity = master["entities"][0]
    resolved = resolve_entity_reference("Microsoft Corp", master)

    assert master["schema_version"] == ENTITY_SECURITY_MASTER_SCHEMA_VERSION
    assert master["validation"]["status"] == "pass"
    assert entity["entity_id"] == "sec_cik:0000789019"
    assert entity["ticker"] == "MSFT"
    assert entity["cik"] == "0000789019"
    assert entity["lei"] == "INR2EJN1ERAN0W5ZP974"
    assert entity["figi"] == "BBG000BPH459"
    assert entity["resolution_confidence"] == "high"
    assert master["summary"]["external_identifier_count"] == 1
    assert resolved["status"] == "resolved"
    assert resolved["ticker"] == "MSFT"


def test_entity_security_master_preserves_brand_subsidiary_product_owner_and_share_links() -> None:
    master = build_entity_security_master(
        {
            "project_inventory": {
                "companies": [
                    {
                        "ticker": "SONY",
                        "company": "Sony Group Corporation",
                        "lei": "549300F6K2GFK4Q2ZF34",
                        "exchange": "NYSE",
                        "country": "JP",
                        "company_domain": "sony.com",
                        "ir_domain": "sony.com/en/SonyInfo/IR",
                        "security_type": "ADR",
                        "ordinary_share_ticker": "6758.T",
                        "adr_ticker": "SONY",
                        "brands": ["PlayStation"],
                        "subsidiaries": ["Sony Interactive Entertainment"],
                        "product_aliases": ["PlayStation 5", "PS5"],
                    }
                ]
            },
            "query_contract": {"companies": ["PlayStation"]},
        }
    )
    entity = master["entities"][0]
    resolved = resolve_entity_reference("PS5", master)

    assert master["validation"]["status"] == "pass"
    assert entity["brands"] == ["PlayStation"]
    assert entity["subsidiaries"] == ["Sony Interactive Entertainment"]
    assert "PS5" in entity["product_aliases"]
    assert entity["ordinary_share_ticker"] == "6758.T"
    assert entity["adr_ticker"] == "SONY"
    assert master["summary"]["brand_alias_count"] == 1
    assert master["summary"]["product_alias_count"] == 2
    assert master["summary"]["adr_or_common_share_link_count"] == 1
    assert resolved["status"] == "resolved"
    assert resolved["ticker"] == "SONY"


def test_source_capability_router_marks_context_blocked_and_gap_routes() -> None:
    router = build_source_capability_router(
        {
            "project_inventory": {
                "available_source_families": ["primary_sec_filing", "market_snapshot"],
                "source_family_availability": {
                    "primary_sec_filing": {"available": True, "status": "available"},
                    "market_snapshot": {"available": True, "status": "available"},
                    "milvus_semantic": {"available": False, "status": "unavailable"},
                },
            },
            "agent_activation_plan": {"allowed_source_families": ["primary_sec_filing", "market_snapshot", "milvus_semantic"]},
            "retrieval_plan": {
                "routes": [
                    {"route_id": "task::ledger_first", "task_id": "task", "retrieval_route": "ledger_first"},
                    {"route_id": "task::market_snapshot", "task_id": "task", "retrieval_route": "market_snapshot"},
                    {"route_id": "task::industry_snapshot", "task_id": "task", "retrieval_route": "industry_snapshot"},
                    {"route_id": "task::milvus_semantic", "task_id": "task", "retrieval_route": "milvus_semantic"},
                ]
            },
        }
    )
    decisions = {row["retrieval_route"]: row for row in router["route_decisions"]}

    assert router["schema_version"] == SOURCE_CAPABILITY_ROUTER_SCHEMA_VERSION
    assert router["validation"]["status"] == "pass"
    assert decisions["ledger_first"]["decision_status"] == "allowed"
    assert decisions["ledger_first"]["claim_authority"] == "exact_authority"
    assert decisions["market_snapshot"]["decision_status"] == "allowed"
    assert decisions["market_snapshot"]["context_only"] is True
    assert decisions["industry_snapshot"]["decision_status"] == "blocked"
    assert decisions["industry_snapshot"]["gap_type"] == "source_boundary_blocked"
    assert decisions["milvus_semantic"]["decision_status"] == "gap"
    assert decisions["milvus_semantic"]["gap_type"] == "coverage_gap"


def test_source_capability_router_applies_minimal_kg_source_boundaries() -> None:
    router = build_source_capability_router(
        {
            "project_inventory": {
                "available_source_families": ["primary_sec_filing", "public_source_context"],
            },
            "query_contract": {
                "intent": "standard_memo",
                "industry_schema": "consumer_electronics",
                "metric_families": ["shipments"],
                "claim_type": "company_disclosed_product_kpi",
                "required_authority": "exact_company_fact",
            },
            "agent_activation_plan": {
                "allowed_source_families": ["primary_sec_filing", "public_source_context", "commercial_market_tracker"],
            },
            "retrieval_plan": {
                "routes": [
                    {
                        "route_id": "task::public_context",
                        "task_id": "task",
                        "retrieval_route": "public_source_context",
                        "source_family": "public_source_context",
                    },
                    {
                        "route_id": "task::commercial_tracker",
                        "task_id": "task",
                        "retrieval_route": "commercial_market_tracker",
                        "source_family": "commercial_market_tracker",
                    },
                ]
            },
        }
    )
    decisions = {row["source_family"]: row for row in router["route_decisions"]}

    assert router["registry_schema_version"] == "fin_agent_kg_minimal_p0_k1_k2_k3_registry_v0.1"
    assert router["registry_validation_status"] == "pass"
    assert decisions["public_source_context"]["decision_status"] == "blocked"
    assert decisions["public_source_context"]["reason"] == "context_only_source_cannot_satisfy_exact_company_fact_authority"
    assert "company_sales" in decisions["public_source_context"]["boundary_forbidden_claims"]
    assert decisions["commercial_market_tracker"]["decision_status"] == "gap"
    assert decisions["commercial_market_tracker"]["gap_type"] == "commercial_gap"
    assert router["summary"]["commercial_gap_decision_count"] == 1


def test_source_capability_router_accepts_full_kg_matrix_registry_path() -> None:
    router = build_source_capability_router(
        {
            "kg_matrix_registry_path": "configs/kg_matrix_registry_v0_1.yaml",
            "project_inventory": {
                "available_source_families": ["live_public_web_context", "commercial_market_tracker"],
            },
            "query_contract": {
                "intent": "deep_research",
                "industry_schema": "consumer_electronics",
                "metric_families": ["sell_through"],
                "claim_type": "company_sales",
                "required_authority": "exact_company_fact",
            },
            "agent_activation_plan": {
                "allowed_source_families": ["live_public_web_context", "commercial_market_tracker"],
            },
            "retrieval_plan": {
                "routes": [
                    {
                        "route_id": "task::web",
                        "task_id": "task",
                        "retrieval_route": "live_public_web_context",
                        "source_family": "live_public_web_context",
                    },
                    {
                        "route_id": "task::commercial_tracker",
                        "task_id": "task",
                        "retrieval_route": "commercial_market_tracker",
                        "source_family": "commercial_market_tracker",
                    },
                ]
            },
        }
    )
    decisions = {row["source_family"]: row for row in router["route_decisions"]}

    assert router["registry_schema_version"] == "fin_agent_kg_minimal_p0_k1_k2_k3_registry_v0.1"
    assert router["registry_validation_status"] == "pass"
    assert decisions["live_public_web_context"]["decision_status"] == "blocked"
    assert decisions["live_public_web_context"]["reason"] == "context_only_source_cannot_satisfy_exact_company_fact_authority"
    assert "channel_offer_as_sell_through" in decisions["live_public_web_context"]["boundary_forbidden_claims"]
    assert decisions["commercial_market_tracker"]["decision_status"] == "gap"
    assert decisions["commercial_market_tracker"]["gap_type"] == "commercial_gap"


def test_graph_persists_entity_master_and_source_capability_router(tmp_path: Path) -> None:
    graph = build_multi_agent_orchestration_graph()
    initial = make_multi_agent_smoke_state(
        user_query="写一段 MSFT 基本面和市场上下文 memo。",
        output_dir=tmp_path,
        query_contract={
            "companies": ["MSFT"],
            "focus_tickers": ["MSFT"],
            "search_scope_tickers": ["MSFT"],
            "years": [2025],
            "source_tiers": ["primary_sec_filing", "market_snapshot"],
            "intent": "standard_memo",
        },
        focus_tickers=["MSFT"],
        search_scope_tickers=["MSFT"],
    )
    initial["project_inventory"] = build_project_inventory(
        [
            {
                "ticker": "MSFT",
                "company": "Microsoft Corporation",
                "cik": "789019",
                "fiscal_year": 2025,
                "form_type": "10-K",
                "source_tier": "primary_sec_filing",
            }
        ],
        manifest_path="data/manifests/sec.jsonl",
        bm25_index_dir="data/indexes/bm25/sec",
        object_bm25_index_dir="data/indexes/sqlite_fts/sec_objects",
        bge_model="BAAI/bge-reranker-v2-m3",
    )

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-d3-d8-artifacts"}})
    summary = json.loads((tmp_path / "multi_agent_summary.json").read_text(encoding="utf-8"))
    entity_artifact = json.loads((tmp_path / "entity_security_master.json").read_text(encoding="utf-8"))
    router_artifact = json.loads((tmp_path / "source_capability_router.json").read_text(encoding="utf-8"))

    assert result["entity_security_master"]["schema_version"] == ENTITY_SECURITY_MASTER_SCHEMA_VERSION
    assert result["source_capability_router"]["schema_version"] == SOURCE_CAPABILITY_ROUTER_SCHEMA_VERSION
    assert result["artifact_refs"]["entity_security_master"].endswith("entity_security_master.json")
    assert result["artifact_refs"]["source_capability_router"].endswith("source_capability_router.json")
    assert entity_artifact["entity_count"] >= 1
    assert entity_artifact["validation"]["status"] == "pass"
    assert router_artifact["validation"]["status"] == "pass"
    assert summary["entity_security_master"]["schema_version"] == ENTITY_SECURITY_MASTER_SCHEMA_VERSION
    assert summary["source_capability_router"]["schema_version"] == SOURCE_CAPABILITY_ROUTER_SCHEMA_VERSION
