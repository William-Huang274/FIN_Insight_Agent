from __future__ import annotations

import json
from pathlib import Path

from sec_agent.financial_statement_analysis import (
    FUNDAMENTAL_STATEMENT_PACK_SCHEMA_VERSION,
    build_fundamental_statement_pack,
)
from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph, make_multi_agent_smoke_state
from sec_agent.multi_agent_runtime import build_agent_data_view
from sec_agent.specialist_llm import build_specialist_request_from_state


def test_fundamental_statement_pack_builds_three_statement_peer_and_period_views() -> None:
    state = _fundamental_pack_state()
    pack = build_fundamental_statement_pack(state)

    assert pack["schema_version"] == FUNDAMENTAL_STATEMENT_PACK_SCHEMA_VERSION
    assert pack["validation"]["status"] == "pass"
    assert pack["summary"]["line_item_count"] >= 8
    assert {"income_statement", "balance_sheet", "cash_flow_statement"} <= set(pack["summary"]["statement_type_counts"])
    assert any(row["canonical_metric_id"] == "financial_metric:revenue" for row in pack["statement_line_items"])
    assert any(row["canonical_metric_id"] == "financial_metric:capex" for row in pack["statement_line_items"])
    assert any(row["canonical_metric_id"] == "financial_metric:cash" for row in pack["statement_line_items"])
    assert any(row["canonical_metric_id"] == "financial_metric:revenue" for row in pack["period_changes"])
    assert any(row["canonical_metric_id"] == "financial_metric:revenue" for row in pack["peer_comparisons"])
    assert pack["industry_focus_policy"]["industry_id"] == "software_saas"
    assert pack["analysis_gaps"] or pack["peer_comparisons"]


def test_fundamental_agent_data_view_exposes_pack_and_structured_claim_slots() -> None:
    state = _fundamental_pack_state()
    view = build_agent_data_view("fundamental_analyst", state)
    request = build_specialist_request_from_state("fundamental_analyst", state)
    slot_ids = {slot["slot_id"] for slot in view["required_claim_slots"]}

    assert view["status"] == "pass"
    assert "fundamental_statement_pack_ref" in view
    assert "fundamentals_three_statement_quality" in slot_ids
    assert "fundamentals_peer_comparison" in slot_ids
    assert "fundamentals_industry_focus_metric" in slot_ids
    assert request["fundamental_statement_pack"]["summary"]["line_item_count"] >= 1
    assert "msft-rev25" in request["known_evidence_refs"]


def test_graph_persists_fundamental_statement_pack_and_judgment_state(tmp_path: Path) -> None:
    def injected_execute(state: dict) -> dict:
        return {
            "tool_observations": [],
            "tool_call_ledger": state.get("tool_call_ledger") or {},
            "runtime_ledger_rows": _fundamental_pack_state()["runtime_ledger_rows"],
        }

    graph = build_multi_agent_orchestration_graph(execute_evidence_operators=injected_execute)
    initial = make_multi_agent_smoke_state(
        user_query="从三表、同行和云业务角度分析 MSFT 基本面质量。",
        output_dir=tmp_path,
        query_contract={
            "companies": ["MSFT", "AMZN"],
            "focus_tickers": ["MSFT"],
            "search_scope_tickers": ["MSFT", "AMZN"],
            "source_tiers": ["primary_sec_filing"],
            "intent": "standard_memo",
        },
        focus_tickers=["MSFT"],
        search_scope_tickers=["MSFT", "AMZN"],
    )

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-fundamental-pack-artifacts"}})
    pack = json.loads((tmp_path / "fundamental_statement_pack.json").read_text(encoding="utf-8"))
    judgment_state = json.loads((tmp_path / "judgment_state.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "multi_agent_summary.json").read_text(encoding="utf-8"))

    assert result["fundamental_statement_pack"]["schema_version"] == FUNDAMENTAL_STATEMENT_PACK_SCHEMA_VERSION
    assert result["artifact_refs"]["fundamental_statement_pack"].endswith("fundamental_statement_pack.json")
    assert pack["validation"]["status"] == "pass"
    assert judgment_state["schema_version"] == "sec_agent_judgment_state_v0.1"
    assert "fundamental_statement_pack" in summary
    assert summary["fundamental_statement_pack"]["line_item_count"] == pack["summary"]["line_item_count"]
    assert summary["judgment_plan"]["judgment_state"]["present"] is True


def _fundamental_pack_state() -> dict:
    return {
        "run_id": "unit-financial-pack",
        "user_query": "Compare MSFT cloud software fundamentals with AMZN peers.",
        "query_contract": {
            "focus_tickers": ["MSFT"],
            "search_scope_tickers": ["MSFT", "AMZN"],
            "sector": "cloud software SaaS",
            "source_tiers": ["primary_sec_filing"],
        },
        "agent_activation_plan": {
            "execution_mode": "deep_research",
            "focus_tickers": ["MSFT"],
            "search_scope_tickers": ["MSFT", "AMZN"],
            "agent_priorities": {"fundamental_analyst": "primary"},
        },
        "runtime_ledger_rows": [
            _row("MSFT", "msft-rev25", "msft-src-rev25", "revenue", "100", 2025),
            _row("MSFT", "msft-rev24", "msft-src-rev24", "revenue", "80", 2024),
            _row("MSFT", "msft-gp25", "msft-src-gp25", "gross profit", "42", 2025),
            _row("MSFT", "msft-ocf25", "msft-src-ocf25", "operating cash flow", "48", 2025),
            _row("MSFT", "msft-capex25", "msft-src-capex25", "capex", "20", 2025),
            _row("MSFT", "msft-cash25", "msft-src-cash25", "cash", "30", 2025),
            _row("MSFT", "msft-debt25", "msft-src-debt25", "debt", "45", 2025),
            _row("MSFT", "msft-inv25", "msft-src-inv25", "inventory", "6", 2025),
            _row("AMZN", "amzn-rev25", "amzn-src-rev25", "revenue", "160", 2025),
            _row("AMZN", "amzn-gp25", "amzn-src-gp25", "gross profit", "70", 2025),
        ],
        "product_evidence_rows": [
            {
                "evidence_ref": "msft-cloud-product-rev25",
                "source_id": "msft-cloud-product-rev25",
                "ticker": "MSFT",
                "metric_family": "product revenue",
                "product_or_segment": "Cloud",
                "value": "60",
                "unit": "USD",
                "fiscal_year": 2025,
                "fiscal_period": "FY",
                "source_family": "company_product_evidence_graph",
                "promotion_status": "runtime_fact_allowed",
            }
        ],
    }


def _row(ticker: str, evidence_ref: str, source_id: str, metric_family: str, value: str, fiscal_year: int) -> dict:
    return {
        "evidence_ref": evidence_ref,
        "source_id": source_id,
        "ticker": ticker,
        "metric_family": metric_family,
        "value": value,
        "unit": "USD",
        "fiscal_year": fiscal_year,
        "fiscal_period": "FY",
        "source_family": "primary_sec_filing",
    }
