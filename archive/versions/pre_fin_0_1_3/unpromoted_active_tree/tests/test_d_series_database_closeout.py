from __future__ import annotations

import json
from pathlib import Path

from sec_agent.d_series_database_closeout import (
    D_SERIES_DATABASE_CLOSEOUT_SCHEMA_VERSION,
    build_d_series_database_closeout_gate,
    default_d_series_database_registry,
)
from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph, make_multi_agent_smoke_state


def test_d_series_closeout_gate_blocks_until_required_database_layers_are_ready() -> None:
    state = {entry["layer_key"]: {"schema_version": f"{entry['layer_key']}_schema"} for entry in default_d_series_database_registry()}
    gate = build_d_series_database_closeout_gate({"run_id": "unit-d12", **state})

    assert gate["schema_version"] == D_SERIES_DATABASE_CLOSEOUT_SCHEMA_VERSION
    assert gate["validation"]["status"] == "pass"
    assert gate["layer_count"] == 11
    assert gate["required_database_layer_count"] == 11
    assert gate["database_ready_layer_count"] == 0
    assert gate["pending_required_database_layer_count"] == 11
    assert gate["d_series_closeout_allowed"] is False
    assert gate["gate_status"] == "blocked"
    assert gate["summary"]["artifact_present_count"] == 11
    for row in gate["layer_closeout_rows"]:
        assert row["schema_objects"]
        assert row["migration_id"]
        assert row["backfill_job"]
        assert row["parity_test"]
        assert row["reader_default_policy"]


def test_d_series_closeout_gate_allows_closeout_when_materialization_statuses_pass() -> None:
    artifacts = {entry["layer_key"]: {"schema_version": f"{entry['layer_key']}_schema"} for entry in default_d_series_database_registry()}
    materialization = {
        entry["layer_key"]: {
            "schema_migration_status": "applied",
            "backfill_status": "complete",
            "parity_status": "pass",
            "reader_default_status": "database_default",
        }
        for entry in default_d_series_database_registry()
    }
    gate = build_d_series_database_closeout_gate(
        {
            "run_id": "unit-d12-ready",
            **artifacts,
            "d_series_database_materialization": materialization,
        }
    )

    assert gate["validation"]["status"] == "pass"
    assert gate["database_ready_layer_count"] == 11
    assert gate["pending_required_database_layer_count"] == 0
    assert gate["d_series_closeout_allowed"] is True
    assert gate["gate_status"] == "pass"


def test_graph_persists_d_series_database_closeout_gate(tmp_path: Path) -> None:
    def injected_execute(state: dict) -> dict:
        return {
            "tool_observations": [],
            "tool_call_ledger": state.get("tool_call_ledger") or {},
            "runtime_ledger_rows": [
                {
                    "evidence_ref": "rev25",
                    "source_id": "sec-msft-rev25",
                    "ticker": "MSFT",
                    "metric_family": "revenue",
                    "value": "100",
                    "unit": "USD",
                    "fiscal_year": 2025,
                    "fiscal_period": "FY",
                    "source_family": "primary_sec_filing",
                }
            ],
        }

    graph = build_multi_agent_orchestration_graph(execute_evidence_operators=injected_execute)
    initial = make_multi_agent_smoke_state(
        user_query="写一段 MSFT revenue 证据 memo。",
        output_dir=tmp_path,
        query_contract={
            "companies": ["MSFT"],
            "focus_tickers": ["MSFT"],
            "search_scope_tickers": ["MSFT"],
            "source_tiers": ["primary_sec_filing"],
            "intent": "standard_memo",
        },
        focus_tickers=["MSFT"],
        search_scope_tickers=["MSFT"],
    )
    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-d12-artifacts"}})
    artifact = json.loads((tmp_path / "d_series_database_closeout_gate.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "multi_agent_summary.json").read_text(encoding="utf-8"))
    checkpoint_artifact = json.loads((tmp_path / "langgraph_node_checkpoints.json").read_text(encoding="utf-8"))
    recoverable_summary = checkpoint_artifact["recoverable_state_summary"]

    assert result["d_series_database_closeout_gate"]["schema_version"] == D_SERIES_DATABASE_CLOSEOUT_SCHEMA_VERSION
    assert result["artifact_refs"]["d_series_database_closeout_gate"].endswith("d_series_database_closeout_gate.json")
    assert artifact["validation"]["status"] == "pass"
    assert artifact["gate_status"] == "blocked"
    assert artifact["d_series_closeout_allowed"] is False
    assert artifact["pending_required_database_layer_count"] == 11
    assert summary["d_series_database_closeout_gate"]["schema_version"] == D_SERIES_DATABASE_CLOSEOUT_SCHEMA_VERSION
    assert summary["d_series_database_closeout_gate"]["pending_required_database_layer_count"] == 11
    assert recoverable_summary["d_series_database_closeout_gate_status"] == "blocked"
    assert recoverable_summary["d_series_closeout_allowed"] is False
