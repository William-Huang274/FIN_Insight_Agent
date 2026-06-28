from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.gold_fact_signal_mart import (
    GOLD_FACT_SIGNAL_MART_SCHEMA_VERSION,
    build_gold_fact_signal_mart,
    write_gold_fact_signal_mart_sqlite,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_rd3_unifies_exact_and_bounded_rows_with_authority_modes(tmp_path: Path) -> None:
    repo = tmp_path
    financial_path = repo / "data/manifests/sec_financial_statement_metric_runtime_rows_v0_1.jsonl"
    product_path = repo / "data/manifests/official_product_spec_context_rows_v0_1.jsonl"
    _write_jsonl(
        financial_path,
        [
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "evidence_id": "fs:nvda:revenue",
                "canonical_metric_id": "financial_metric:revenue",
                "metric_family": "revenue",
                "value": 130497000000,
                "unit": "USD",
                "period": "FY2026",
                "exact_value_authority": True,
                "can_support_company_exact_fact": True,
                "runtime_ready_context": True,
                "source_layer": "L1",
                "source_id": "sec_companyfacts_api",
                "claim_boundary": "consolidated financial fact only",
                "citation": {"url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json"},
            }
        ],
    )
    _write_jsonl(
        product_path,
        [
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "evidence_id": "spec:nvda:h100",
                "source_role": "technical_product_spec",
                "metric_name": "cuda_cores",
                "spec_value": "16896",
                "spec_unit": "cores",
                "product_family": "GPU / Accelerator",
                "product_or_segment": "H100",
                "bounded_structured_context": True,
                "runtime_ready_context": True,
                "exact_value_authority": False,
                "can_support_company_exact_fact": False,
                "source_layer": "L2",
                "claim_boundary": "technical spec only",
                "citation": {"url": "https://www.nvidia.com/en-us/data-center/h100/"},
            }
        ],
    )

    result = build_gold_fact_signal_mart(
        repo,
        generated_at="2026-06-27T00:00:00+00:00",
        source_rowsets=[
            "data/manifests/sec_financial_statement_metric_runtime_rows_v0_1.jsonl",
            "data/manifests/official_product_spec_context_rows_v0_1.jsonl",
        ],
    )

    assert result["summary"]["status"] == "pass"
    rows_by_ref = {row["source_row_id"]: row for row in result["rows"]}
    financial = rows_by_ref["fs:nvda:revenue"]
    assert financial["schema_version"] == GOLD_FACT_SIGNAL_MART_SCHEMA_VERSION
    assert financial["fact_domain"] == "financial_statement_fact"
    assert financial["authority_mode"] == "exact_company_fact_authority"
    assert financial["can_enter_evidence_bundle"] is True
    product = rows_by_ref["spec:nvda:h100"]
    assert product["fact_domain"] == "product_profile_or_spec_fact"
    assert product["authority_mode"] == "bounded_thesis_driver_authority"
    assert product["value"] == "16896"


def test_rd3_keeps_source_authority_gap_only_out_of_evidence_bundle(tmp_path: Path) -> None:
    repo = tmp_path
    authority_path = repo / "data/manifests/r18_source_authority_data_mart_rows_v0_1.jsonl"
    _write_jsonl(
        authority_path,
        [
            {
                "ticker": "CRDO",
                "ledger_id": "authority:crdo:public-order-gap",
                "authority_mode": "attempt_backed_public_boundary",
                "can_enter_evidence_bundle": False,
                "source_role": "public_order_proxy",
                "source_id": "public_tenders_contracts_orders",
                "support_surface": "public_order_supply_chain_proxy",
                "claim_boundary": "gap only",
            }
        ],
    )

    result = build_gold_fact_signal_mart(
        repo,
        generated_at="2026-06-27T00:00:00+00:00",
        source_rowsets=["data/manifests/r18_source_authority_data_mart_rows_v0_1.jsonl"],
    )

    row = result["rows"][0]
    assert row["fact_domain"] == "source_authority"
    assert row["authority_mode"] == "planning_or_gap_only"
    assert row["can_enter_evidence_bundle"] is False
    assert result["summary"]["planning_or_gap_only_count"] == 1


def test_rd3_sqlite_row_count_matches_jsonl_rows(tmp_path: Path) -> None:
    repo = tmp_path
    rows_path = repo / "data/manifests/market_liquidity_driver_context_rows_v0_1.jsonl"
    _write_jsonl(
        rows_path,
        [
            {
                "ticker": "MSFT",
                "evidence_id": "market:msft",
                "metric_family": "market_reaction",
                "runtime_ready_context": True,
                "bounded_structured_context": True,
                "source_layer_id": "L3",
                "source_role": "market_liquidity_driver",
                "citation": {"url": "https://query1.finance.yahoo.com/v8/finance/chart/MSFT"},
            }
        ],
    )
    result = build_gold_fact_signal_mart(
        repo,
        generated_at="2026-06-27T00:00:00+00:00",
        source_rowsets=["data/manifests/market_liquidity_driver_context_rows_v0_1.jsonl"],
    )
    sqlite_path = repo / "data/workbench_private/research_data/gold.sqlite"
    count = write_gold_fact_signal_mart_sqlite(sqlite_path, result["rows"])

    with sqlite3.connect(str(sqlite_path)) as conn:
        stored = conn.execute("select ticker, fact_domain from gold_fact_signal_mart").fetchone()

    assert count == 1
    assert stored == ("MSFT", "market_liquidity_signal")
