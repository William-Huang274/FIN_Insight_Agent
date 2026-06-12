from __future__ import annotations

import json
from pathlib import Path

from sec_agent.derived_metric_layer import DERIVED_METRIC_LAYER_SCHEMA_VERSION, build_derived_metric_layer
from sec_agent.gate_registry import build_gate_registry_eval_matrix
from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph, make_multi_agent_smoke_state
from sec_agent.metric_product_ontology import build_metric_product_ontology_snapshot
from sec_agent.reconciliation_ledger import build_reconciliation_ledger


def _d10_formula_state() -> dict:
    return {
        "run_id": "unit-d10",
        "runtime_ledger_rows": [
            _row("rev25", "sec-rev25", "revenue", "100", 2025),
            _row("rev24", "sec-rev24", "revenue", "80", 2024),
            _row("gp25", "sec-gp25", "gross profit", "40", 2025),
            _row("op25", "sec-op25", "operating income", "30", 2025),
            _row("ocf25", "sec-ocf25", "operating cash flow", "50", 2025),
            _row("capex25", "sec-capex25", "capex", "10", 2025),
            _row("debt25", "sec-debt25", "debt", "70", 2025),
            _row("cash25", "sec-cash25", "cash", "20", 2025),
        ],
        "product_evidence_rows": [
            {
                "evidence_ref": "prod-rev25",
                "source_id": "prod-rev25",
                "ticker": "MSFT",
                "metric_family": "product revenue",
                "product_or_segment": "Cloud",
                "value": "120",
                "unit": "USD",
                "fiscal_year": 2025,
                "fiscal_period": "FY",
                "source_family": "company_product_evidence_graph",
                "promotion_status": "runtime_fact_allowed",
            },
            {
                "evidence_ref": "deliveries25",
                "source_id": "deliveries25",
                "ticker": "MSFT",
                "metric_family": "deliveries",
                "product_or_segment": "Cloud",
                "value": "12",
                "unit": "units",
                "fiscal_year": 2025,
                "fiscal_period": "FY",
                "source_family": "company_product_evidence_graph",
                "promotion_status": "runtime_fact_allowed",
            },
        ],
    }


def test_derived_metric_layer_calculates_only_from_reconciled_inputs() -> None:
    state = _d10_formula_state()
    ontology = build_metric_product_ontology_snapshot(state)
    reconciliation = build_reconciliation_ledger({**state, "metric_product_ontology_snapshot": ontology})
    gates = build_gate_registry_eval_matrix(
        {**state, "metric_product_ontology_snapshot": ontology, "reconciliation_ledger": reconciliation}
    )
    layer = build_derived_metric_layer(
        {
            **state,
            "metric_product_ontology_snapshot": ontology,
            "reconciliation_ledger": reconciliation,
            "gate_registry_eval_matrix": gates,
        }
    )
    by_family = {row["derived_metric_family"]: row for row in layer["derived_metrics"]}

    assert layer["schema_version"] == DERIVED_METRIC_LAYER_SCHEMA_VERSION
    assert layer["validation"]["status"] == "pass"
    assert by_family["gross_margin"]["value"] == "40"
    assert by_family["operating_margin"]["value"] == "30"
    assert by_family["free_cash_flow"]["value"] == "40"
    assert by_family["free_cash_flow_margin"]["value"] == "40"
    assert by_family["net_debt"]["value"] == "50"
    assert by_family["asp"]["value"] == "10"
    assert by_family["yoy_growth"]["value"] == "25"
    for row in layer["derived_metrics"]:
        assert row["formula"]
        assert row["calculation_version"]
        assert row["input_fact_ids"]
        assert row["gate_status"] == "pass"
        assert row["explainability_trace"]


def test_derived_metric_layer_blocks_formula_when_input_gate_fails() -> None:
    state = {
        "run_id": "unit-d10-blocked",
        "runtime_ledger_rows": [
            _row("rev25", "sec-rev25", "revenue", "100", 2025),
            _row("gp25", "sec-gp25", "gross profit", "40", 2025),
        ],
        "raw_source_provenance_store": {
            "records": [
                {
                    "source_id": "sec-gp25",
                    "evidence_ref": "gp25",
                    "source_family": "primary_sec_filing",
                }
            ]
        },
    }
    ontology = build_metric_product_ontology_snapshot(state)
    reconciliation = build_reconciliation_ledger({**state, "metric_product_ontology_snapshot": ontology})
    gates = build_gate_registry_eval_matrix(
        {**state, "metric_product_ontology_snapshot": ontology, "reconciliation_ledger": reconciliation}
    )
    layer = build_derived_metric_layer(
        {
            **state,
            "metric_product_ontology_snapshot": ontology,
            "reconciliation_ledger": reconciliation,
            "gate_registry_eval_matrix": gates,
        }
    )

    assert "gross_margin" not in {row["derived_metric_family"] for row in layer["derived_metrics"]}
    blocked = [row for row in layer["skipped_derivations"] if row["skip_reason"] == "input_gate_blocked"]
    assert blocked
    assert blocked[0]["blocking_gate_result_ids"]
    assert layer["summary"]["blocked_derivation_count"] >= 1
    assert layer["validation"]["status"] == "pass"


def test_graph_persists_derived_metric_layer(tmp_path: Path) -> None:
    def injected_execute(state: dict) -> dict:
        return {
            "tool_observations": [],
            "tool_call_ledger": state.get("tool_call_ledger") or {},
            "runtime_ledger_rows": [
                {**_row("rev25", "sec-msft-rev25", "revenue", "100", 2025), "source_url": "https://www.sec.gov/msft-2025.htm"},
                {**_row("rev24", "sec-msft-rev24", "revenue", "80", 2024), "source_url": "https://www.sec.gov/msft-2024.htm"},
                {**_row("gp25", "sec-msft-gp25", "gross profit", "40", 2025), "source_url": "https://www.sec.gov/msft-2025.htm"},
            ],
        }

    graph = build_multi_agent_orchestration_graph(execute_evidence_operators=injected_execute)
    initial = make_multi_agent_smoke_state(
        user_query="写一段 MSFT revenue 和 gross margin 证据 memo。",
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
    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-d10-artifacts"}})
    artifact = json.loads((tmp_path / "derived_metric_layer.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "multi_agent_summary.json").read_text(encoding="utf-8"))
    checkpoint_artifact = json.loads((tmp_path / "langgraph_node_checkpoints.json").read_text(encoding="utf-8"))
    recoverable_summary = checkpoint_artifact["recoverable_state_summary"]

    assert result["derived_metric_layer"]["schema_version"] == DERIVED_METRIC_LAYER_SCHEMA_VERSION
    assert result["artifact_refs"]["derived_metric_layer"].endswith("derived_metric_layer.json")
    assert artifact["validation"]["status"] == "pass"
    assert artifact["derived_metric_count"] >= 2
    assert summary["derived_metric_layer"]["schema_version"] == DERIVED_METRIC_LAYER_SCHEMA_VERSION
    assert summary["derived_metric_layer"]["derived_metric_count"] == artifact["derived_metric_count"]
    assert recoverable_summary["derived_metric_count"] == artifact["derived_metric_count"]
    assert recoverable_summary["derived_metric_validation_status"] == "pass"


def _row(evidence_ref: str, source_id: str, metric_family: str, value: str, fiscal_year: int) -> dict:
    return {
        "evidence_ref": evidence_ref,
        "source_id": source_id,
        "ticker": "MSFT",
        "metric_family": metric_family,
        "value": value,
        "unit": "USD",
        "fiscal_year": fiscal_year,
        "fiscal_period": "FY",
        "source_family": "primary_sec_filing",
    }
