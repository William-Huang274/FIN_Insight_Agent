from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.product_intelligence_graph import (
    build_product_intelligence_graph,
    write_product_intelligence_sqlite,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _seed_product_intelligence_inputs(repo: Path) -> None:
    _write_jsonl(
        repo / "data/manifests/company_product_slots_v0_1.jsonl",
        [
            {
                "product_slot_id": "product_slot:nvda_blackwell",
                "ticker": "NVDA",
                "company_name": "NVIDIA Corporation",
                "family_id": "gpu_accelerator",
                "family_name": "GPU / Accelerator",
                "product_slot_name": "Blackwell GPU",
                "slot_status": "official_surface_slot",
                "claim_boundary": "Official product surface slot only.",
                "sample_urls": ["https://www.nvidia.com/en-us/data-center/blackwell/"],
            },
            {
                "product_slot_id": "product_slot:amd_instinct",
                "ticker": "AMD",
                "company_name": "Advanced Micro Devices, Inc.",
                "family_id": "gpu_accelerator",
                "family_name": "GPU / Accelerator",
                "product_slot_name": "Instinct GPU",
                "slot_status": "official_surface_slot",
                "claim_boundary": "Official product surface slot only.",
                "sample_urls": ["https://www.amd.com/en/products/accelerators/instinct.html"],
            },
        ],
    )
    _write_jsonl(
        repo / "data/manifests/product_relationship_graph_nodes_v0_1.jsonl",
        [
            {"node_id": "company:NVDA", "node_type": "company", "label": "NVIDIA Corporation", "payload": {}},
            {"node_id": "company:AMD", "node_type": "company", "label": "Advanced Micro Devices, Inc.", "payload": {}},
            {"node_id": "product_family:gpu_accelerator", "node_type": "product_family", "label": "GPU / Accelerator", "payload": {}},
            {
                "node_id": "company_product_family:NVDA:gpu_accelerator",
                "node_type": "company_product_family",
                "label": "NVDA GPU / Accelerator",
                "payload": {},
            },
            {
                "node_id": "company_product_family:AMD:gpu_accelerator",
                "node_type": "company_product_family",
                "label": "AMD GPU / Accelerator",
                "payload": {},
            },
        ],
    )
    _write_jsonl(
        repo / "data/manifests/product_relationship_graph_edges_v0_1.jsonl",
        [
            {
                "edge_id": "edge:competes:nvda:amd",
                "from_node_id": "company_product_family:NVDA:gpu_accelerator",
                "to_node_id": "company_product_family:AMD:gpu_accelerator",
                "relationship_type": "COMPETES_WITH",
                "promotion_status": "candidate_company_family_comparable_edge",
                "source_layer": "derived_company_family_comparable",
                "confidence": 0.65,
                "claim_boundary": "Same product family comparable candidate only.",
                "forbidden_claims": ["market_share", "win_loss"],
                "evidence_refs": ["assignment:nvda", "assignment:amd"],
            },
            {
                "edge_id": "edge:template:foundry",
                "from_node_id": "company_product_family:NVDA:gpu_accelerator",
                "to_node_id": "company_product_family:AMD:gpu_accelerator",
                "relationship_type": "MANUFACTURING_DEPENDENCY_FOR",
                "promotion_status": "candidate_taxonomy_relationship_edge",
                "source_layer": "derived_lane_template",
                "confidence": 0.35,
                "claim_boundary": "Template context only.",
                "forbidden_claims": ["allocation", "revenue"],
                "evidence_refs": [],
            },
        ],
    )
    _write_jsonl(
        repo / "data/manifests/gold_fact_signal_mart_rows_v0_1.jsonl",
        [
            {
                "gold_row_id": "gold:nvda:blackwell_spec",
                "source_row_id": "spec:nvda:blackwell",
                "ticker": "NVDA",
                "company_name": "NVIDIA Corporation",
                "fact_domain": "product_profile_or_spec_fact",
                "fact_type": "technical_product_spec",
                "authority_mode": "bounded_thesis_driver_authority",
                "can_enter_evidence_bundle": True,
                "source_layer": "L2",
                "source_role": "technical_product_spec",
                "product_family": "GPU Accelerator",
                "product_or_segment": "Blackwell GPU",
                "metric_name": "memory bandwidth",
                "value": "8",
                "unit": "TB/s",
                "claim_boundary": "Official technical product specification only.",
                "citation_url": "https://www.nvidia.com/en-us/data-center/blackwell/",
            },
            {
                "gold_row_id": "gold:nvda:dc_revenue",
                "source_row_id": "kpi:nvda:dc_revenue",
                "ticker": "NVDA",
                "company_name": "NVIDIA Corporation",
                "fact_domain": "product_kpi_fact",
                "fact_type": "product_kpi:product_revenue",
                "authority_mode": "exact_company_fact_authority",
                "can_enter_evidence_bundle": True,
                "source_layer": "L1",
                "source_role": "primary_company_disclosure",
                "product_family": "Data Center",
                "product_or_segment": "Data Center",
                "metric_name": "revenue",
                "value": "47500000000",
                "unit": "USD",
                "period": "FY2025",
                "claim_boundary": "Company-disclosed product/business revenue only.",
                "citation_url": "https://www.sec.gov/example",
            },
            {
                "gold_row_id": "gold:nvda:deployment",
                "source_row_id": "deployment:nvda:cloud",
                "ticker": "NVDA",
                "company_name": "NVIDIA Corporation",
                "fact_domain": "customer_deployment_or_order_signal",
                "fact_type": "official_customer_order_or_deployment_event",
                "authority_mode": "bounded_thesis_driver_authority",
                "can_enter_evidence_bundle": True,
                "source_layer": "L2",
                "source_role": "official_customer_order_or_deployment_event",
                "product_family": "GPU Accelerator",
                "product_or_segment": "Blackwell GPU",
                "metric_name": "cloud deployment",
                "claim_boundary": "Deployment signal only; no revenue/order/backlog promotion.",
                "citation_url": "https://nvidianews.nvidia.com/example",
            },
            {
                "gold_row_id": "gold:amd:profile",
                "source_row_id": "profile:amd:instinct",
                "ticker": "AMD",
                "company_name": "Advanced Micro Devices, Inc.",
                "fact_domain": "product_profile_or_spec_fact",
                "fact_type": "ProductProfileSlot",
                "authority_mode": "bounded_thesis_driver_authority",
                "can_enter_evidence_bundle": True,
                "source_layer": "L2",
                "source_role": "official_product_profile_spec",
                "product_family": "GPU Accelerator",
                "product_or_segment": "Instinct GPU",
                "metric_name": "product profile",
                "claim_boundary": "Product profile only.",
                "citation_url": "https://www.amd.com/example",
            },
        ],
    )


def test_product_intelligence_graph_builds_authority_separated_packs(tmp_path: Path) -> None:
    repo = tmp_path
    _seed_product_intelligence_inputs(repo)

    result = build_product_intelligence_graph(repo, generated_at="2026-06-27T00:00:00Z")

    assert result["summary"]["status"] == "pass"
    assert result["summary"]["dangling_edge_count"] == 0
    assert result["summary"]["invalid_evidence_edge_count"] == 0
    nvda_pack = next(row for row in result["company_packs"] if row["ticker"] == "NVDA")
    assert nvda_pack["product_kpi_exact_count"] == 1
    assert nvda_pack["technical_spec_count"] == 1
    assert nvda_pack["customer_deployment_signal_count"] == 1
    amd_pack = next(row for row in result["company_packs"] if row["ticker"] == "AMD")
    assert amd_pack["status"] == "pass_with_gaps"
    assert any(row["ticker"] == "AMD" and row["gap_reason"] == "product_kpi_or_operating_metric_absent" for row in result["gap_rows"])


def test_product_intelligence_authority_blocks_template_edges_from_evidence_bundle(tmp_path: Path) -> None:
    repo = tmp_path
    _seed_product_intelligence_inputs(repo)

    result = build_product_intelligence_graph(repo, generated_at="2026-06-27T00:00:00Z")

    template_edges = [row for row in result["edges"] if row["authority_type"] == "template_context_edge"]
    assert template_edges
    assert all(not row["can_enter_evidence_bundle"] for row in template_edges)
    spec_edges = [row for row in result["edges"] if row["authority_type"] == "technical_fact_authority"]
    assert spec_edges
    assert "product_revenue" in json.loads(spec_edges[0]["forbidden_claims_json"])


def test_product_intelligence_sqlite_counts_match_outputs(tmp_path: Path) -> None:
    repo = tmp_path
    _seed_product_intelligence_inputs(repo)
    result = build_product_intelligence_graph(repo, generated_at="2026-06-27T00:00:00Z")
    sqlite_path = repo / "data/workbench_private/research_data/pig.sqlite"

    counts = write_product_intelligence_sqlite(
        sqlite_path,
        nodes=result["nodes"],
        edges=result["edges"],
        packs=result["company_packs"],
        gaps=result["gap_rows"],
    )

    assert counts["node_count"] == len(result["nodes"])
    assert counts["edge_count"] == len(result["edges"])
    assert counts["pack_count"] == len(result["company_packs"])
    assert counts["gap_count"] == len(result["gap_rows"])
    conn = sqlite3.connect(sqlite_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM product_intelligence_company_packs").fetchone()[0] == len(result["company_packs"])
    finally:
        conn.close()
