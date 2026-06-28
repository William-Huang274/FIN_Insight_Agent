from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.research_graph_store import build_research_graph_store, write_research_graph_sqlite


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_rd4_builds_gold_mart_graph_edges_with_support_rows(tmp_path: Path) -> None:
    repo = tmp_path
    _write_jsonl(repo / "data/manifests/product_relationship_graph_nodes_v0_1.jsonl", [])
    _write_jsonl(repo / "data/manifests/product_relationship_graph_edges_v0_1.jsonl", [])
    _write_jsonl(
        repo / "data/manifests/gold_fact_signal_mart_rows_v0_1.jsonl",
        [
            {
                "gold_row_id": "gold:nvda:h100",
                "source_row_id": "spec:nvda:h100",
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "fact_domain": "product_profile_or_spec_fact",
                "fact_type": "technical_product_spec",
                "support_surface": "product_spec_and_capability",
                "authority_mode": "bounded_thesis_driver_authority",
                "can_enter_evidence_bundle": True,
                "source_layer": "L2",
                "source_role": "technical_product_spec",
                "product_family": "GPU / Accelerator",
                "product_or_segment": "H100",
                "evidence_ref": "spec:nvda:h100",
                "citation_url": "https://www.nvidia.com/en-us/data-center/h100/",
                "claim_boundary": "technical spec only",
                "forbidden_claims_json": "[\"product_revenue\"]",
            }
        ],
    )

    result = build_research_graph_store(repo, generated_at="2026-06-27T00:00:00+00:00")

    assert result["summary"]["status"] == "pass"
    assert result["summary"]["edge_count"] == 1
    assert result["summary"]["evidence_support_row_count"] == 1
    edge = result["edges"][0]
    assert edge["edge_type"] == "HAS_PRODUCT_PROFILE_OR_SPEC"
    assert edge["authority_mode"] == "bounded_thesis_driver_authority"
    support = result["support_rows"][0]
    assert support["support_status"] == "gold_mart_row"
    assert support["gold_row_id"] == "gold:nvda:h100"


def test_rd4_product_graph_edge_keeps_source_evidence_ref_only_support(tmp_path: Path) -> None:
    repo = tmp_path
    _write_jsonl(
        repo / "data/manifests/product_relationship_graph_nodes_v0_1.jsonl",
        [
            {"node_id": "company:NVDA", "node_type": "company", "label": "NVIDIA", "payload": {}},
            {"node_id": "product_family:gpu", "node_type": "product_family", "label": "GPU", "payload": {}},
        ],
    )
    _write_jsonl(
        repo / "data/manifests/product_relationship_graph_edges_v0_1.jsonl",
        [
            {
                "edge_id": "edge:nvda:gpu",
                "from_node_id": "company:NVDA",
                "to_node_id": "product_family:gpu",
                "relationship_type": "HAS_PRODUCT_FAMILY",
                "confidence": 0.9,
                "evidence_refs": ["company_product_family_assignment:nvda"],
                "claim_boundary": "taxonomy only",
            }
        ],
    )
    _write_jsonl(repo / "data/manifests/gold_fact_signal_mart_rows_v0_1.jsonl", [])

    result = build_research_graph_store(repo, generated_at="2026-06-27T00:00:00+00:00")

    assert result["summary"]["status"] == "pass"
    assert result["summary"]["support_status_counts"]["source_evidence_ref_only"] == 1
    assert result["edges"][0]["edge_type"] == "HAS_PRODUCT_FAMILY"


def test_rd4_sqlite_counts_match_graph_outputs(tmp_path: Path) -> None:
    repo = tmp_path
    _write_jsonl(repo / "data/manifests/product_relationship_graph_nodes_v0_1.jsonl", [])
    _write_jsonl(repo / "data/manifests/product_relationship_graph_edges_v0_1.jsonl", [])
    _write_jsonl(
        repo / "data/manifests/gold_fact_signal_mart_rows_v0_1.jsonl",
        [
            {
                "gold_row_id": "gold:msft:market",
                "source_row_id": "market:msft",
                "ticker": "MSFT",
                "company_name": "Microsoft",
                "fact_domain": "market_liquidity_signal",
                "fact_type": "market_reaction",
                "authority_mode": "bounded_thesis_driver_authority",
                "can_enter_evidence_bundle": True,
                "source_layer": "L3",
                "source_role": "market_liquidity_driver",
                "evidence_ref": "market:msft",
            }
        ],
    )
    result = build_research_graph_store(repo, generated_at="2026-06-27T00:00:00+00:00")
    sqlite_path = repo / "data/workbench_private/research_data/graph.sqlite"
    counts = write_research_graph_sqlite(
        sqlite_path,
        nodes=result["nodes"],
        edges=result["edges"],
        support_rows=result["support_rows"],
    )

    with sqlite3.connect(str(sqlite_path)) as conn:
        edge_type = conn.execute("select edge_type from research_graph_edges").fetchone()[0]

    assert counts["node_count"] == len(result["nodes"])
    assert counts["edge_count"] == len(result["edges"])
    assert counts["support_count"] == len(result["support_rows"])
    assert edge_type == "HAS_MARKET_LIQUIDITY_SIGNAL"
