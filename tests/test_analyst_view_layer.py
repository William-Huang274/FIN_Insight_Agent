from __future__ import annotations

import json
from pathlib import Path

from sec_agent.analyst_view_layer import (
    ANALYST_VIEW_LAYER_SCHEMA_VERSION,
    build_analyst_view_research_memory_layer,
    validate_analyst_view_research_memory_layer,
)
from sec_agent.claim_evidence_ledger import build_evidence_governance_ledgers
from sec_agent.derived_metric_layer import build_derived_metric_layer
from sec_agent.gate_registry import build_gate_registry_eval_matrix
from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph, make_multi_agent_smoke_state
from sec_agent.metric_product_ontology import build_metric_product_ontology_snapshot
from sec_agent.reconciliation_ledger import build_reconciliation_ledger


def test_analyst_view_layer_indexes_claims_gaps_and_derived_metrics_without_raw_refs() -> None:
    state = _d11_state()
    ledgers, derived_layer = _build_ledgers_and_derived(state)
    layer = build_analyst_view_research_memory_layer({**state, **ledgers, "derived_metric_layer": derived_layer})
    by_type = {row["view_type"]: row for row in layer["analyst_views"]}

    assert layer["schema_version"] == ANALYST_VIEW_LAYER_SCHEMA_VERSION
    assert layer["validation"]["status"] == "pass"
    assert {"company_profile_view", "earnings_change_view", "product_kpi_view", "risk_factor_view", "bull_bear_debate_view", "thesis_tracker"} <= set(by_type)
    assert layer["summary"]["claim_ref_count"] == 2
    assert layer["summary"]["gap_ref_count"] == 1
    assert layer["summary"]["derived_metric_ref_count"] >= 1
    for view in layer["analyst_views"]:
        assert set(view["source_layers"]) <= {"claim_evidence_ledger", "typed_gap_ledger", "derived_metric_layer"}
        assert view["evidence_policy"] == "view_is_not_source_must_drill_down_to_ledgers"
        assert "supporting_evidence_ids" not in view
        assert "input_source_ids" not in view
    for entry in layer["research_memory_entries"]:
        assert entry["memory_status"] == "run_scoped_candidate"
        assert entry["retrieval_policy"] == "retrieve_view_then_drill_down_to_claim_gap_derived_refs"
        assert entry["view_id"] in {view["view_id"] for view in layer["analyst_views"]}


def test_analyst_view_validation_rejects_raw_source_refs() -> None:
    payload = {
        "analyst_views": [
            {
                "view_id": "bad-view",
                "view_type": "company_profile_view",
                "source_layers": ["claim_evidence_ledger"],
                "claim_ids": ["claim-1"],
                "gap_ids": [],
                "derived_metric_ids": [],
                "supporting_evidence_ids": ["raw-evidence-ref"],
                "evidence_policy": "view_is_not_source_must_drill_down_to_ledgers",
            }
        ],
        "research_memory_entries": [
            {
                "memory_entry_id": "memory-1",
                "view_id": "bad-view",
                "memory_status": "run_scoped_candidate",
                "retrieval_policy": "retrieve_view_then_drill_down_to_claim_gap_derived_refs",
                "claim_ids": ["claim-1"],
            }
        ],
    }
    validation = validate_analyst_view_research_memory_layer(payload)

    assert validation["status"] == "fail"
    assert any(error["type"] == "view_contains_raw_source_reference" for error in validation["errors"])


def test_graph_persists_analyst_view_research_memory(tmp_path: Path) -> None:
    def injected_execute(state: dict) -> dict:
        return {
            "tool_observations": [],
            "tool_call_ledger": state.get("tool_call_ledger") or {},
            "runtime_ledger_rows": [
                _row("rev25", "sec-msft-rev25", "revenue", "100", 2025),
                _row("rev24", "sec-msft-rev24", "revenue", "80", 2024),
                _row("gp25", "sec-msft-gp25", "gross profit", "40", 2025),
            ],
            "source_gaps": [
                {
                    "gap_id": "gap_msft_shipments",
                    "gap_type": "commercial_tracker_gap",
                    "ticker": "MSFT",
                    "metric": "shipments",
                    "reason": "Commercial tracker required; weak proxy blocked.",
                }
            ],
        }

    graph = build_multi_agent_orchestration_graph(execute_evidence_operators=injected_execute)
    initial = make_multi_agent_smoke_state(
        user_query="写一段 MSFT revenue、gross margin 和 shipments 证据边界 memo。",
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

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-d11-artifacts"}})
    artifact = json.loads((tmp_path / "analyst_view_research_memory.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "multi_agent_summary.json").read_text(encoding="utf-8"))
    checkpoint_artifact = json.loads((tmp_path / "langgraph_node_checkpoints.json").read_text(encoding="utf-8"))
    recoverable_summary = checkpoint_artifact["recoverable_state_summary"]

    assert result["analyst_view_research_memory"]["schema_version"] == ANALYST_VIEW_LAYER_SCHEMA_VERSION
    assert result["artifact_refs"]["analyst_view_research_memory"].endswith("analyst_view_research_memory.json")
    assert artifact["validation"]["status"] == "pass"
    assert artifact["view_count"] >= 1
    assert artifact["memory_entry_count"] == artifact["view_count"]
    assert summary["analyst_view_research_memory"]["schema_version"] == ANALYST_VIEW_LAYER_SCHEMA_VERSION
    assert summary["analyst_view_research_memory"]["view_count"] == artifact["view_count"]
    assert recoverable_summary["analyst_view_count"] == artifact["view_count"]
    assert recoverable_summary["analyst_view_validation_status"] == "pass"


def _build_ledgers_and_derived(state: dict) -> tuple[dict, dict]:
    ontology = build_metric_product_ontology_snapshot(state)
    reconciliation = build_reconciliation_ledger({**state, "metric_product_ontology_snapshot": ontology})
    gates = build_gate_registry_eval_matrix(
        {**state, "metric_product_ontology_snapshot": ontology, "reconciliation_ledger": reconciliation}
    )
    derived_layer = build_derived_metric_layer(
        {
            **state,
            "metric_product_ontology_snapshot": ontology,
            "reconciliation_ledger": reconciliation,
            "gate_registry_eval_matrix": gates,
        }
    )
    return build_evidence_governance_ledgers(state), derived_layer


def _d11_state() -> dict:
    return {
        "run_id": "unit-d11",
        "runtime_ledger_rows": [
            _row("rev25", "sec-rev25", "revenue", "100", 2025),
            _row("rev24", "sec-rev24", "revenue", "80", 2024),
            _row("gp25", "sec-gp25", "gross profit", "40", 2025),
        ],
        "verified_judgment_plan": {
            "supported_claims": [
                {
                    "claim": "MSFT revenue and gross profit are supported.",
                    "ticker": "MSFT",
                    "evidence_refs": ["rev25", "gp25"],
                    "source_families": ["primary_sec_filing"],
                    "confidence": "high",
                    "claim_type": "fundamental",
                }
            ],
            "unsupported_claims": [
                {
                    "claim": "MSFT exact product shipments are missing.",
                    "ticker": "MSFT",
                    "metric": "shipments",
                    "claim_type": "product_kpi",
                }
            ],
        },
        "source_gaps": [
            {
                "gap_id": "gap_shipments",
                "gap_type": "commercial_tracker_gap",
                "ticker": "MSFT",
                "metric": "shipments",
                "reason": "Commercial tracker required; public proxy blocked.",
            }
        ],
    }


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
