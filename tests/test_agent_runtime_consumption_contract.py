from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.agent_runtime_consumption_contract import (
    build_agent_runtime_consumption_contract,
    write_agent_runtime_consumption_sqlite,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _seed_common_summaries(repo: Path) -> None:
    _write_json(repo / "data/manifests/retrieval_index_registry_summary_v0_1.json", {"status": "pass", "index_snapshot_count": 2})
    _write_json(repo / "data/manifests/parser_quality_summary_v0_1.json", {"status": "pass", "parser_run_count": 1})
    _write_json(repo / "data/manifests/raw_source_provenance_summary_v0_1.json", {"status": "pass", "runtime_lineage_count": 1})
    _write_json(repo / "data/manifests/research_graph_summary_v0_1.json", {"status": "pass", "edge_count": 1})


def test_rd6_builds_company_brief_and_role_specific_packs(tmp_path: Path) -> None:
    repo = tmp_path
    _seed_common_summaries(repo)
    _write_jsonl(
        repo / "data/manifests/gold_fact_signal_mart_rows_v0_1.jsonl",
        [
            {
                "gold_row_id": "gold:nvda:revenue",
                "source_row_id": "fs:nvda:revenue",
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "fact_domain": "financial_statement_fact",
                "fact_type": "revenue",
                "authority_mode": "exact_company_fact_authority",
                "can_enter_evidence_bundle": True,
                "source_layer": "L1",
                "source_role": "sec_companyfacts_api",
                "citation_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json",
            },
            {
                "gold_row_id": "gold:nvda:h100",
                "source_row_id": "spec:nvda:h100",
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "fact_domain": "product_profile_or_spec_fact",
                "fact_type": "technical_product_spec",
                "authority_mode": "bounded_thesis_driver_authority",
                "can_enter_evidence_bundle": True,
                "source_layer": "L2",
                "source_role": "technical_product_spec",
                "product_family": "GPU / Accelerator",
                "product_or_segment": "H100",
                "citation_url": "https://www.nvidia.com/en-us/data-center/h100/",
            },
        ],
    )
    _write_jsonl(
        repo / "data/manifests/research_graph_edges_v0_1.jsonl",
        [
            {
                "edge_id": "edge:nvda:h100",
                "from_node_id": "company:NVDA",
                "to_node_id": "product:H100",
                "edge_type": "HAS_PRODUCT_PROFILE_OR_SPEC",
            }
        ],
    )

    result = build_agent_runtime_consumption_contract(repo, generated_at="2026-06-27T00:00:00+00:00")

    assert result["summary"]["status"] == "pass"
    assert result["summary"]["company_brief_count"] == 1
    assert result["summary"]["role_evidence_pack_count"] == 6
    brief = result["briefs"][0]
    assert brief["ticker"] == "NVDA"
    assert brief["exact_fact_count"] == 1
    assert brief["bounded_signal_count"] == 1
    product_pack = next(pack for pack in result["packs"] if pack["role"] == "product_technology_analyst")
    assert product_pack["status"] == "pass"
    selected = json.loads(product_pack["selected_evidence_refs_json"])
    assert selected[0]["gold_row_id"] == "gold:nvda:h100"


def test_rd6_never_selects_planning_gap_rows_as_evidence(tmp_path: Path) -> None:
    repo = tmp_path
    _seed_common_summaries(repo)
    _write_jsonl(
        repo / "data/manifests/gold_fact_signal_mart_rows_v0_1.jsonl",
        [
            {
                "gold_row_id": "gold:crdo:gap",
                "source_row_id": "authority:crdo:gap",
                "ticker": "CRDO",
                "company_name": "Credo",
                "fact_domain": "source_authority",
                "fact_type": "public_order_gap",
                "authority_mode": "planning_or_gap_only",
                "can_enter_evidence_bundle": False,
                "source_layer": "L3",
                "source_role": "public_order_proxy",
                "claim_boundary": "gap only",
            },
            {
                "gold_row_id": "gold:crdo:market",
                "source_row_id": "market:crdo",
                "ticker": "CRDO",
                "company_name": "Credo",
                "fact_domain": "market_liquidity_signal",
                "fact_type": "market_snapshot",
                "authority_mode": "bounded_thesis_driver_authority",
                "can_enter_evidence_bundle": True,
                "source_layer": "L3",
                "source_role": "market_liquidity_driver",
            },
        ],
    )
    _write_jsonl(repo / "data/manifests/research_graph_edges_v0_1.jsonl", [])

    result = build_agent_runtime_consumption_contract(repo, generated_at="2026-06-27T00:00:00+00:00")

    assert result["summary"]["invalid_selected_gap_row_count"] == 0
    risk_pack = next(pack for pack in result["packs"] if pack["role"] == "risk_counterevidence_analyst")
    assert risk_pack["selected_count"] == 0
    assert risk_pack["gap_count"] == 1
    assert json.loads(risk_pack["gap_refs_json"])[0]["gold_row_id"] == "gold:crdo:gap"


def test_rd6_sqlite_counts_match_outputs(tmp_path: Path) -> None:
    repo = tmp_path
    _seed_common_summaries(repo)
    _write_jsonl(
        repo / "data/manifests/gold_fact_signal_mart_rows_v0_1.jsonl",
        [
            {
                "gold_row_id": "gold:msft:cash",
                "source_row_id": "fs:msft:cash",
                "ticker": "MSFT",
                "company_name": "Microsoft",
                "fact_domain": "financial_statement_fact",
                "fact_type": "cash",
                "authority_mode": "exact_company_fact_authority",
                "can_enter_evidence_bundle": True,
                "source_layer": "L1",
                "source_role": "sec_companyfacts_api",
            }
        ],
    )
    _write_jsonl(repo / "data/manifests/research_graph_edges_v0_1.jsonl", [])
    result = build_agent_runtime_consumption_contract(repo, generated_at="2026-06-27T00:00:00+00:00")
    sqlite_path = repo / "data/workbench_private/research_data/rd6.sqlite"
    counts = write_agent_runtime_consumption_sqlite(sqlite_path, briefs=result["briefs"], packs=result["packs"])

    with sqlite3.connect(str(sqlite_path)) as conn:
        role_count = conn.execute("select count(*) from role_evidence_packs where ticker='MSFT'").fetchone()[0]
        exact_count = conn.execute("select exact_fact_count from agent_data_briefs where ticker='MSFT'").fetchone()[0]

    assert counts == {"brief_count": 1, "pack_count": 6}
    assert role_count == 6
    assert exact_count == 1
