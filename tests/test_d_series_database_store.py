from __future__ import annotations

import json
from pathlib import Path

from sec_agent.claim_evidence_ledger import build_evidence_governance_ledgers
from sec_agent.d_series_database_closeout import build_d_series_database_closeout_gate
from sec_agent.d_series_database_store import (
    D12_1_MATERIALIZED_LAYER_KEYS,
    d_series_materialization_state_from_report,
    materialize_d1_d2_d9_governance_store,
    parity_check_d1_d2_d9_governance_artifacts,
    read_d1_d2_d9_governance_counts,
)
from sec_agent.gate_registry import build_gate_registry_eval_matrix
from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph, make_multi_agent_smoke_state
from sec_agent.metric_product_ontology import build_metric_product_ontology_snapshot
from sec_agent.reconciliation_ledger import build_reconciliation_ledger


def test_materializes_d1_d2_d9_artifacts_to_sqlite_with_parity(tmp_path: Path) -> None:
    artifacts = _sample_governance_artifacts()
    db_path = tmp_path / "d_series_governance.sqlite"

    report = materialize_d1_d2_d9_governance_store(db_path, artifacts)
    counts = read_d1_d2_d9_governance_counts(db_path, run_id="unit-d12-1")
    parity = parity_check_d1_d2_d9_governance_artifacts(db_path, artifacts)
    closeout = build_d_series_database_closeout_gate(
        {
            **artifacts,
            "d_series_database_materialization": d_series_materialization_state_from_report(report),
        }
    )

    assert report["schema_version"] == "sec_agent_d_series_database_materialization_v0.1"
    assert set(report["layers"]) == set(D12_1_MATERIALIZED_LAYER_KEYS)
    for layer in report["layers"].values():
        assert layer["schema_migration_status"] == "applied"
        assert layer["backfill_status"] == "complete"
        assert layer["parity_status"] == "pass"
        assert layer["reader_default_status"] == "database_default"
        assert layer["schema_objects"]
        assert layer["migration_id"].startswith("d00")
    assert counts["claim_evidence_claims"] == artifacts["claim_evidence_ledger"]["claim_count"]
    assert counts["typed_gap_events"] == artifacts["typed_gap_ledger"]["gap_count"]
    assert counts["gate_registry"] == artifacts["gate_registry_eval_matrix"]["gate_count"]
    assert counts["gate_eval_matrix"] == artifacts["gate_registry_eval_matrix"]["gate_count"]
    assert parity["parity_status"] == "pass"
    assert not parity["mismatches"]
    assert closeout["database_ready_layer_count"] == 3
    assert closeout["pending_required_database_layer_count"] == 8
    assert closeout["d_series_closeout_allowed"] is False
    assert closeout["summary"]["ready_required_layers"] == list(D12_1_MATERIALIZED_LAYER_KEYS)


def test_graph_materializes_d1_d2_d9_when_db_path_is_explicit(tmp_path: Path) -> None:
    def injected_execute(state: dict) -> dict:
        return {
            "tool_observations": [],
            "tool_call_ledger": state.get("tool_call_ledger") or {},
            "runtime_ledger_rows": [
                {
                    "evidence_ref": "msft-revenue-usd",
                    "source_id": "sec-msft-revenue-usd",
                    "source_family": "primary_sec_filing",
                    "ticker": "MSFT",
                    "metric_family": "revenue",
                    "value": "100",
                    "unit": "USD",
                    "fiscal_year": 2025,
                    "fiscal_period": "FY",
                    "source_url": "https://www.sec.gov/Archives/edgar/data/789019/msft-2025.htm",
                }
            ],
            "source_gaps": [
                {
                    "gap_id": "gap_msft_shipments",
                    "gap_type": "commercial_tracker_gap",
                    "ticker": "MSFT",
                    "metric": "shipments",
                    "source_family": "public_source_context",
                    "reason": "Commercial tracker required; weak proxy blocked.",
                    "source_attempts": ["SEC", "company_product_page"],
                    "commercial_sources_needed": ["IDC", "Counterpoint"],
                }
            ],
        }

    graph = build_multi_agent_orchestration_graph(execute_evidence_operators=injected_execute)
    initial = make_multi_agent_smoke_state(
        user_query="写一段 MSFT revenue 和 shipments 证据边界 memo。",
        output_dir=tmp_path,
        query_contract={
            "companies": ["MSFT"],
            "focus_tickers": ["MSFT"],
            "search_scope_tickers": ["MSFT"],
            "source_tiers": ["primary_sec_filing", "public_source_context"],
            "intent": "standard_memo",
        },
        focus_tickers=["MSFT"],
        search_scope_tickers=["MSFT"],
    )
    initial["d_series_governance_db_path"] = str(tmp_path / "graph_governance.sqlite")

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-d12-1-graph"}})
    report = json.loads((tmp_path / "d_series_database_materialization_report.json").read_text(encoding="utf-8"))
    closeout = json.loads((tmp_path / "d_series_database_closeout_gate.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "multi_agent_summary.json").read_text(encoding="utf-8"))
    checkpoint = json.loads((tmp_path / "langgraph_node_checkpoints.json").read_text(encoding="utf-8"))

    assert Path(str(result["d_series_database_materialization_report"]["db_path"])).exists()
    assert result["d_series_database_closeout_gate"]["database_ready_layer_count"] == 3
    assert result["d_series_database_closeout_gate"]["pending_required_database_layer_count"] == 8
    assert result["artifact_refs"]["d_series_database_materialization_report"].endswith(
        "d_series_database_materialization_report.json"
    )
    assert report["layers"]["claim_evidence_ledger"]["parity_status"] == "pass"
    assert closeout["database_ready_layer_count"] == 3
    assert summary["d_series_database_materialization"]["materialized_layer_count"] == 3
    assert summary["d_series_database_materialization"]["all_materialized_layers_parity_pass"] is True
    assert checkpoint["recoverable_state_summary"]["d_series_materialized_database_layer_count"] == 3


def _sample_governance_artifacts() -> dict:
    state = {
        "run_id": "unit-d12-1",
        "source_capability_router": {
            "route_decisions": [
                {
                    "route_id": "route_public_proxy_blocked",
                    "retrieval_route": "live_public_web_context",
                    "decision_status": "blocked",
                    "reason": "context-only public proxy cannot fill commercial tracker",
                    "context_only": True,
                    "exact_value_authority": False,
                }
            ]
        },
        "runtime_ledger_rows": [
            {
                "evidence_ref": "rev_usd",
                "source_id": "sec-rev-usd",
                "ticker": "MSFT",
                "metric_family": "revenue",
                "value": "100",
                "unit": "USD",
                "fiscal_year": 2025,
                "fiscal_period": "FY",
                "source_family": "primary_sec_filing",
            },
            {
                "evidence_ref": "rev_shares",
                "source_id": "sec-rev-shares",
                "ticker": "MSFT",
                "metric_family": "revenue",
                "value": "100",
                "unit": "shares",
                "fiscal_year": 2025,
                "fiscal_period": "FY",
                "source_family": "primary_sec_filing",
            },
        ],
        "source_gaps": [
            {
                "gap_id": "gap_commercial_shipments",
                "gap_type": "commercial_tracker_gap",
                "ticker": "MSFT",
                "metric": "shipments",
                "source_family": "public_source_context",
                "reason": "Commercial tracker required; weak proxy cannot fill shipments.",
                "source_attempts": ["SEC", "company_product_page"],
                "commercial_sources_needed": ["IDC", "Counterpoint"],
            }
        ],
        "verified_judgment_plan": {
            "supported_claims": [
                {
                    "claim_id": "cl_msft_revenue",
                    "agent_id": "fundamental_analyst",
                    "claim": "MSFT revenue is disclosed by SEC filing evidence.",
                    "claim_type": "company_reported_financial_fact",
                    "ticker_scope": ["MSFT"],
                    "metric_scope": ["revenue"],
                    "evidence_refs": ["rev_usd"],
                    "source_families": ["primary_sec_filing"],
                    "confidence": "high",
                }
            ],
            "conflicts": [
                {
                    "claim_id": "cl_msft_unit_conflict",
                    "claim": "Revenue share units conflict with revenue USD.",
                    "evidence_refs": ["rev_shares"],
                    "ticker": "MSFT",
                    "metric": "revenue",
                }
            ],
            "unsupported_claims": [
                {
                    "claim_id": "cl_msft_shipments_gap",
                    "claim": "MSFT product shipment share is exactly disclosed in public sources.",
                    "reason": "Commercial tracker required.",
                    "ticker": "MSFT",
                    "metric": "shipments",
                    "gap_ids": ["gap_commercial_shipments"],
                }
            ],
        },
    }
    ledgers = build_evidence_governance_ledgers(state)
    ontology = build_metric_product_ontology_snapshot({**state, **ledgers})
    reconciliation = build_reconciliation_ledger({**state, **ledgers, "metric_product_ontology_snapshot": ontology})
    gate_matrix = build_gate_registry_eval_matrix(
        {
            **state,
            **ledgers,
            "metric_product_ontology_snapshot": ontology,
            "reconciliation_ledger": reconciliation,
        }
    )
    return {
        **state,
        **ledgers,
        "metric_product_ontology_snapshot": ontology,
        "reconciliation_ledger": reconciliation,
        "gate_registry_eval_matrix": gate_matrix,
    }
