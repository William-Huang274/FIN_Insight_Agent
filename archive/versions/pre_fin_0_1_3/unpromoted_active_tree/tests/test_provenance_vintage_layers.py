from __future__ import annotations

import json
from pathlib import Path

from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph, make_multi_agent_smoke_state
from sec_agent.provenance_vintage import (
    ASOF_VINTAGE_LAYER_SCHEMA_VERSION,
    RAW_SOURCE_PROVENANCE_STORE_SCHEMA_VERSION,
    build_asof_vintage_layer,
    build_raw_source_provenance_store,
)


def test_raw_source_provenance_store_preserves_source_locator_and_artifact_refs(tmp_path: Path) -> None:
    local_html = tmp_path / "msft-2025-10k.htm"
    local_html.write_text("<html>Revenue by product line.</html>\n", encoding="utf-8")
    claim_artifact = tmp_path / "claim_evidence_ledger.json"
    claim_artifact.write_text('{"claims":[]}\n', encoding="utf-8")
    state = {
        "run_id": "unit-d4",
        "runtime_ledger_rows": [
            {
                "source_id": "sec-msft-2025-10k",
                "evidence_ref": "msft-product-revenue",
                "source_family": "primary_sec_filing",
                "ticker": "MSFT",
                "source_url": "https://www.sec.gov/Archives/edgar/data/789019/000095017026000000/msft-20250630.htm",
                "local_path": str(local_html),
                "accession_number": "0000950170-26-000000",
                "parser_version": "sec_product_kpi_parser_v0.4",
                "retrieved_at": "2026-06-12T00:00:00Z",
                "source_as_of_date": "2025-06-30",
                "section": "Item 7",
                "start_char": 10,
                "end_char": 90,
                "quote": "Revenue by product line.",
            }
        ],
        "artifact_refs": {"claim_evidence_ledger": str(claim_artifact)},
        "project_inventory": {
            "companies": [
                {
                    "ticker": "MSFT",
                    "filings": [
                        {
                            "form_type": "10-K",
                            "year": 2025,
                            "source_tier": "primary_sec_filing",
                            "accession_number": "0000950170-26-000000",
                            "filing_date": "2025-07-30",
                            "period_end": "2025-06-30",
                        }
                    ],
                }
            ]
        },
    }

    store = build_raw_source_provenance_store(state)
    sec_record = next(row for row in store["records"] if row["source_id"] == "sec-msft-2025-10k")
    artifact_record = next(row for row in store["records"] if row["record_type"] == "artifact_ref")

    assert store["schema_version"] == RAW_SOURCE_PROVENANCE_STORE_SCHEMA_VERSION
    assert store["validation"]["status"] == "pass"
    assert sec_record["document_id"] == "0000950170-26-000000"
    assert sec_record["file_type"] == "html"
    assert sec_record["checksum"].startswith("sha256:")
    assert sec_record["checksum_materialized"] is True
    assert sec_record["citation_span"]["section"] == "Item 7"
    assert sec_record["access_method"] == "http"
    assert artifact_record["source_family"] == "run_artifact"
    assert store["summary"]["document_id_count"] >= 2
    assert artifact_record["checksum"].startswith("sha256:")
    assert store["summary"]["checksum_count"] >= 2
    assert store["summary"]["materialized_checksum_count"] >= 2
    assert store["summary"]["parser_lineage_record_count"] >= 1


def test_asof_vintage_layer_keeps_fiscal_market_and_macro_time_basis() -> None:
    state = {
        "run_id": "unit-d5",
        "runtime_ledger_rows": [
            {
                "source_id": "sec-msft-2025-10k",
                "evidence_ref": "msft-revenue",
                "source_family": "primary_sec_filing",
                "ticker": "MSFT",
                "fiscal_year": 2025,
                "fiscal_period": "FY",
                "fiscal_period_end": "2025-06-30",
                "filing_date": "2025-07-30",
                "accepted_date": "2025-07-30T20:00:00Z",
                "parser_run_at": "2026-06-12T02:00:00Z",
            }
        ],
        "market_snapshot_rows": [
            {
                "source_id": "market-msft-2026-06-12",
                "evidence_ref": "msft-price",
                "source_family": "market_snapshot",
                "ticker": "MSFT",
                "as_of_date": "2026-06-12",
                "retrieved_at": "2026-06-12T02:00:00Z",
            }
        ],
        "industry_snapshot_rows": [
            {
                "source_id": "fred-ai-2026-06-12",
                "evidence_ref": "software-demand",
                "source_family": "industry_snapshot",
                "ticker": "MSFT",
                "vintage_date": "2026-06-01",
                "observation_date": "2026-05-01",
            }
        ],
    }

    layer = build_asof_vintage_layer(state)
    by_ref = {row["evidence_ref"]: row for row in layer["records"]}

    assert layer["schema_version"] == ASOF_VINTAGE_LAYER_SCHEMA_VERSION
    assert layer["validation"]["status"] == "pass"
    assert by_ref["msft-revenue"]["time_basis"] == "fiscal_period"
    assert by_ref["msft-price"]["time_basis"] == "market_as_of"
    assert by_ref["software-demand"]["time_basis"] == "macro_vintage"
    assert layer["summary"]["fiscal_period_record_count"] == 1
    assert layer["summary"]["market_as_of_record_count"] == 1
    assert layer["summary"]["macro_vintage_record_count"] == 1


def test_graph_persists_raw_source_provenance_and_asof_vintage_layers(tmp_path: Path) -> None:
    def injected_execute(state: dict) -> dict:
        return {
            "tool_observations": [],
            "tool_call_ledger": state.get("tool_call_ledger") or {},
            "runtime_ledger_rows": [
                {
                    "source_id": "sec-msft-2025-10k",
                    "evidence_ref": "msft-revenue",
                    "source_family": "primary_sec_filing",
                    "ticker": "MSFT",
                    "metric_family": "revenue",
                    "value": "100",
                    "source_url": "https://www.sec.gov/Archives/edgar/data/789019/000095017026000000/msft-20250630.htm",
                    "accession_number": "0000950170-26-000000",
                    "fiscal_period_end": "2025-06-30",
                    "filing_date": "2025-07-30",
                    "retrieved_at": "2026-06-12T00:00:00Z",
                    "parser_version": "unit_parser_v0.1",
                }
            ],
            "market_snapshot_rows": [
                {
                    "source_id": "market-msft-2026-06-12",
                    "evidence_ref": "msft-price",
                    "source_family": "market_snapshot",
                    "ticker": "MSFT",
                    "as_of_date": "2026-06-12",
                }
            ],
            "industry_snapshot_rows": [
                {
                    "source_id": "fred-software-2026-06-01",
                    "evidence_ref": "software-demand",
                    "source_family": "industry_snapshot",
                    "ticker": "MSFT",
                    "vintage_date": "2026-06-01",
                }
            ],
        }

    graph = build_multi_agent_orchestration_graph(execute_evidence_operators=injected_execute)
    initial = make_multi_agent_smoke_state(
        user_query="写一段 MSFT 基本面、市场和行业上下文 memo。",
        output_dir=tmp_path,
        query_contract={
            "companies": ["MSFT"],
            "focus_tickers": ["MSFT"],
            "search_scope_tickers": ["MSFT"],
            "source_tiers": ["primary_sec_filing", "market_snapshot", "industry_snapshot"],
            "intent": "standard_memo",
        },
        focus_tickers=["MSFT"],
        search_scope_tickers=["MSFT"],
    )

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-d4-d5-artifacts"}})
    summary = json.loads((tmp_path / "multi_agent_summary.json").read_text(encoding="utf-8"))
    provenance_artifact = json.loads((tmp_path / "raw_source_provenance_store.json").read_text(encoding="utf-8"))
    vintage_artifact = json.loads((tmp_path / "asof_vintage_layer.json").read_text(encoding="utf-8"))
    checkpoint_artifact = json.loads((tmp_path / "langgraph_node_checkpoints.json").read_text(encoding="utf-8"))
    recoverable_summary = checkpoint_artifact["recoverable_state_summary"]

    assert result["raw_source_provenance_store"]["schema_version"] == RAW_SOURCE_PROVENANCE_STORE_SCHEMA_VERSION
    assert result["asof_vintage_layer"]["schema_version"] == ASOF_VINTAGE_LAYER_SCHEMA_VERSION
    assert result["artifact_refs"]["raw_source_provenance_store"].endswith("raw_source_provenance_store.json")
    assert result["artifact_refs"]["asof_vintage_layer"].endswith("asof_vintage_layer.json")
    assert provenance_artifact["validation"]["status"] == "pass"
    assert vintage_artifact["validation"]["status"] == "pass"
    assert any(row["record_type"] == "artifact_ref" for row in provenance_artifact["records"])
    assert summary["raw_source_provenance_store"]["schema_version"] == RAW_SOURCE_PROVENANCE_STORE_SCHEMA_VERSION
    assert summary["asof_vintage_layer"]["schema_version"] == ASOF_VINTAGE_LAYER_SCHEMA_VERSION
    assert summary["asof_vintage_layer"]["by_time_basis"]["market_as_of"] == 1
    assert recoverable_summary["raw_source_provenance_record_count"] == provenance_artifact["record_count"]
    assert recoverable_summary["asof_vintage_record_count"] == vintage_artifact["record_count"]
