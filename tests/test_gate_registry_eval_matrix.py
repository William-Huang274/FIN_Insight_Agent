from __future__ import annotations

import json
from pathlib import Path

from sec_agent.gate_registry import GATE_REGISTRY_EVAL_MATRIX_SCHEMA_VERSION, build_gate_registry_eval_matrix
from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph, make_multi_agent_smoke_state
from sec_agent.metric_product_ontology import build_metric_product_ontology_snapshot
from sec_agent.provenance_vintage import build_asof_vintage_layer
from sec_agent.reconciliation_ledger import build_reconciliation_ledger


def test_gate_registry_eval_matrix_collects_boundary_conflict_and_claim_gates() -> None:
    state = {
        "run_id": "unit-d9",
        "source_capability_router": {
            "route_decisions": [
                {
                    "route_id": "route_blocked_public_proxy",
                    "retrieval_route": "live_public_web_context",
                    "decision_status": "blocked",
                    "reason": "source_family_not_allowed_by_activation",
                    "context_only": True,
                    "exact_value_authority": False,
                }
            ]
        },
        "source_gaps": [
            {
                "gap_id": "gap_commercial_shipments",
                "gap_type": "commercial_tracker_gap",
                "ticker": "MSFT",
                "metric": "shipments",
                "source_family": "public_source_context",
                "reason": "weak proxy cannot fill commercial tracker",
            }
        ],
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
            {
                "evidence_ref": "metric_unmapped",
                "source_id": "sec-unmapped",
                "ticker": "MSFT",
                "metric_family": "unmapped operating metric",
                "value": "1",
                "unit": "units",
                "fiscal_year": 2025,
                "fiscal_period": "FY",
                "source_family": "primary_sec_filing",
            },
        ],
        "verified_judgment_plan": {
            "supported_claims": [
                {
                    "claim": "MSFT revenue is disclosed.",
                    "evidence_refs": ["rev_usd"],
                    "source_families": ["primary_sec_filing"],
                    "confidence": "high",
                }
            ],
            "conflicts": [
                {
                    "claim": "MSFT product shipments are disclosed.",
                    "evidence_refs": ["gap_commercial_shipments"],
                    "ticker": "MSFT",
                    "metric": "shipments",
                }
            ],
        },
    }
    ontology = build_metric_product_ontology_snapshot(state)
    reconciliation = build_reconciliation_ledger({**state, "metric_product_ontology_snapshot": ontology})
    matrix = build_gate_registry_eval_matrix(
        {**state, "metric_product_ontology_snapshot": ontology, "reconciliation_ledger": reconciliation}
    )
    by_gate = {row["gate_id"]: row for row in matrix["eval_matrix"]}

    assert matrix["schema_version"] == GATE_REGISTRY_EVAL_MATRIX_SCHEMA_VERSION
    assert matrix["validation"]["status"] == "pass"
    assert matrix["gate_count"] == 12
    assert matrix["summary"]["source_boundary_violation_covered"] is True
    assert matrix["summary"]["weak_proxy_fallback_covered"] is True
    assert by_gate["source_boundary_gate"]["fail_count"] >= 1
    assert by_gate["commercial_gap_gate"]["fail_count"] == 1
    assert by_gate["unit_normalization_gate"]["fail_count"] >= 1
    assert by_gate["metric_mapping_gate"]["fail_count"] >= 1
    assert by_gate["claim_support_gate"]["pass_count"] >= 1
    assert by_gate["contradiction_gate"]["fail_count"] >= 1
    assert matrix["summary"]["blocking_fail_count"] >= 4


def test_gate_registry_marks_market_snapshot_fiscal_time_basis_mismatch() -> None:
    vintage_layer = build_asof_vintage_layer(
        {
            "run_id": "unit-d5-time-mismatch",
            "market_snapshot_rows": [
                {
                    "source_id": "market-msft-2026-06-12",
                    "evidence_ref": "msft-market-share-proxy",
                    "source_family": "market_snapshot",
                    "ticker": "MSFT",
                    "fiscal_year": 2025,
                    "fiscal_period_end": "2025-06-30",
                    "market_as_of_date": "2026-06-12",
                    "retrieved_at": "2026-06-12T02:00:00Z",
                }
            ],
        }
    )

    matrix = build_gate_registry_eval_matrix({"run_id": "unit-d5-time-mismatch", "asof_vintage_layer": vintage_layer})
    period_results = [row for row in matrix["gate_history"] if row["gate_id"] == "period_alignment_gate"]

    assert matrix["validation"]["status"] == "pass"
    assert len(period_results) == 1
    assert period_results[0]["status"] == "warn"
    assert period_results[0]["reason"] == "time_basis_mismatch"
    assert period_results[0]["after_value"]["time_mismatch"] is True


def test_graph_persists_gate_registry_eval_matrix(tmp_path: Path) -> None:
    def injected_execute(state: dict) -> dict:
        return {
            "tool_observations": [],
            "tool_call_ledger": state.get("tool_call_ledger") or {},
            "runtime_ledger_rows": [
                {
                    "source_id": "sec-msft-revenue-usd",
                    "evidence_ref": "msft-revenue-usd",
                    "source_family": "primary_sec_filing",
                    "ticker": "MSFT",
                    "metric_family": "revenue",
                    "value": "100",
                    "unit": "USD",
                    "fiscal_year": 2025,
                    "fiscal_period": "FY",
                    "fiscal_period_end": "2025-06-30",
                    "source_url": "https://www.sec.gov/Archives/edgar/data/789019/msft-2025.htm",
                },
                {
                    "source_id": "sec-msft-revenue-shares",
                    "evidence_ref": "msft-revenue-shares",
                    "source_family": "primary_sec_filing",
                    "ticker": "MSFT",
                    "metric_family": "revenue",
                    "value": "100",
                    "unit": "shares",
                    "fiscal_year": 2025,
                    "fiscal_period": "FY",
                    "fiscal_period_end": "2025-06-30",
                    "source_url": "https://www.sec.gov/Archives/edgar/data/789019/msft-2025.htm",
                },
            ],
            "source_gaps": [
                {
                    "gap_id": "gap_msft_shipments",
                    "gap_type": "commercial_tracker_gap",
                    "ticker": "MSFT",
                    "metric": "shipments",
                    "source_family": "public_source_context",
                    "reason": "Commercial tracker required; weak proxy blocked.",
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

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-d9-artifacts"}})
    artifact = json.loads((tmp_path / "gate_registry_eval_matrix.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "multi_agent_summary.json").read_text(encoding="utf-8"))
    checkpoint_artifact = json.loads((tmp_path / "langgraph_node_checkpoints.json").read_text(encoding="utf-8"))
    recoverable_summary = checkpoint_artifact["recoverable_state_summary"]

    assert result["gate_registry_eval_matrix"]["schema_version"] == GATE_REGISTRY_EVAL_MATRIX_SCHEMA_VERSION
    assert result["artifact_refs"]["gate_registry_eval_matrix"].endswith("gate_registry_eval_matrix.json")
    assert artifact["validation"]["status"] == "pass"
    assert artifact["gate_count"] == 12
    assert artifact["summary"]["blocking_fail_count"] >= 1
    assert summary["gate_registry_eval_matrix"]["schema_version"] == GATE_REGISTRY_EVAL_MATRIX_SCHEMA_VERSION
    assert summary["gate_registry_eval_matrix"]["blocking_fail_count"] == artifact["summary"]["blocking_fail_count"]
    assert recoverable_summary["gate_registry_gate_result_count"] == artifact["gate_result_count"]
    assert recoverable_summary["gate_registry_validation_status"] == "pass"
