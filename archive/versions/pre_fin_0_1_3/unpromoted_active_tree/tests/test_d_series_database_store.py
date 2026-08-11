from __future__ import annotations

import json
from pathlib import Path

from sec_agent.claim_evidence_ledger import build_evidence_governance_ledgers
from sec_agent.d_series_database_closeout import build_d_series_database_closeout_gate
from sec_agent.d_series_database_store import (
    D12_1_MATERIALIZED_LAYER_KEYS,
    D_SERIES_MATERIALIZED_LAYER_KEYS,
    d_series_materialization_state_from_report,
    materialize_d_series_governance_store,
    materialize_d1_d2_d9_governance_store,
    parity_check_d1_d2_d9_governance_artifacts,
    parity_check_d_series_governance_artifacts,
    read_claim_gap_gate_research_context,
    read_d1_d2_d9_governance_counts,
    read_d_series_governance_counts,
    read_d_series_research_context,
)
from sec_agent.d_series_fact_selection import (
    apply_pre_memo_fact_selection_to_judgment,
    build_pre_memo_fact_selection,
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

    assert report["schema_version"] == "sec_agent_d_series_database_materialization_v0.2"
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


def test_reader_returns_claim_gap_gate_context_across_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "cross_run_governance.sqlite"
    materialize_d1_d2_d9_governance_store(db_path, _sample_governance_artifacts(run_id="unit-d12-1-a"))
    materialize_d1_d2_d9_governance_store(db_path, _sample_governance_artifacts(run_id="unit-d12-1-b"))

    context = read_claim_gap_gate_research_context(db_path, tickers=["MSFT"], limit=20)

    assert context["reader_default_status"] == "database_default"
    assert context["summary"]["source"] == "d_series_governance_sqlite_store"
    assert context["summary"]["claim_count"] >= 2
    assert context["summary"]["typed_gap_count"] >= 2
    assert context["summary"]["gate_history_count"] >= 1
    assert {row["ticker"] for row in context["claims"]} == {"MSFT"}
    assert any(row["gap_id"] == "gap_commercial_shipments" for row in context["typed_gaps"])


def test_full_d_series_reader_returns_cross_layer_context_and_supersession(tmp_path: Path) -> None:
    db_path = tmp_path / "full_reader_governance.sqlite"
    materialize_d_series_governance_store(db_path, _sample_governance_artifacts(run_id="unit-d12-1-reader-a"))
    materialize_d_series_governance_store(db_path, _sample_governance_artifacts(run_id="unit-d12-1-reader-b"))

    context = read_d_series_research_context(db_path, tickers=["MSFT"], limit=50)

    assert context["reader_default_status"] == "database_default"
    assert context["summary"]["context_group_count"] == 8
    assert context["summary"]["row_count"] > 0
    assert context["contexts"]["entity_security"]["entities"]
    assert context["contexts"]["source_provenance"]["raw_documents"]
    assert context["contexts"]["asof_vintage"]["vintage_records"]
    assert context["contexts"]["reconciliation"]["unresolved_groups"]
    assert context["contexts"]["metric_product_ontology"]["metrics"]
    assert context["contexts"]["source_policy"]["source_capabilities"]
    assert "outputs" in context["contexts"]["derived_metrics"]
    assert context["contexts"]["analyst_memory"]["views"]
    assert context["summary"]["stale_or_superseded_row_count"] >= 1
    assert context["staleness_policy"]["policy"] == "latest_inserted_at_per_context_stable_key_v0_1"


def test_pre_memo_fact_selection_blocks_unresolved_conflict_claims() -> None:
    artifacts = _sample_governance_artifacts(run_id="unit-d12-1-pre-memo")
    selection = build_pre_memo_fact_selection(artifacts)
    selected = apply_pre_memo_fact_selection_to_judgment(artifacts["verified_judgment_plan"], selection)

    assert selection["schema_version"] == "sec_agent_pre_memo_fact_selection_v0.1"
    assert selection["summary"]["rejected_fact_count"] >= 1
    assert "rev_usd" in selection["blocked_evidence_refs"]
    assert selected["pre_memo_fact_selection"]["summary"]["rejected_fact_count"] >= 1
    assert not any(claim.get("claim_id") == "cl_msft_revenue" for claim in selected["supported_claims"])
    assert any(row.get("reason") == "blocked_by_pre_memo_fact_selection" for row in selected["unsupported_claims"])
    assert selected["memo_writer_allowed"] is False


def test_materializes_full_d_series_artifacts_to_sqlite_with_parity(tmp_path: Path) -> None:
    artifacts = _sample_governance_artifacts(run_id="unit-d12-1-full")
    db_path = tmp_path / "full_d_series_governance.sqlite"

    report = materialize_d_series_governance_store(db_path, artifacts)
    counts = read_d_series_governance_counts(db_path, run_id="unit-d12-1-full")
    parity = parity_check_d_series_governance_artifacts(db_path, artifacts)
    closeout = build_d_series_database_closeout_gate(
        {
            **artifacts,
            "d_series_database_materialization": d_series_materialization_state_from_report(report),
        }
    )

    assert set(report["layers"]) == set(D_SERIES_MATERIALIZED_LAYER_KEYS)
    assert all(layer["parity_status"] == "pass" for layer in report["layers"].values())
    assert all(layer["reader_default_status"] == "database_default" for layer in report["layers"].values())
    assert counts["entity_master"] == artifacts["entity_security_master"]["entity_count"]
    assert counts["raw_source_documents"] == artifacts["raw_source_provenance_store"]["record_count"]
    assert counts["asof_vintage_records"] == artifacts["asof_vintage_layer"]["record_count"]
    assert counts["reconciliation_groups"] == artifacts["reconciliation_ledger"]["group_count"]
    assert counts["metric_product_ontology_metrics"] == artifacts["metric_product_ontology_snapshot"]["metric_count"]
    assert counts["source_capability_policy"] == artifacts["source_capability_router"]["capability_count"]
    assert counts["derived_metric_outputs"] == artifacts["derived_metric_layer"]["derived_metric_count"]
    assert counts["analyst_view_index"] == artifacts["analyst_view_research_memory"]["view_count"]
    assert parity["parity_status"] == "pass"
    assert closeout["database_ready_layer_count"] == 11
    assert closeout["pending_required_database_layer_count"] == 0
    assert closeout["d_series_closeout_allowed"] is True


def test_graph_materializes_full_d_series_when_db_path_is_explicit(tmp_path: Path) -> None:
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
    db_path = tmp_path / "graph_governance.sqlite"
    initial["d_series_governance_db_path"] = str(db_path)

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-d12-1-graph"}})
    report = json.loads((tmp_path / "d_series_database_materialization_report.json").read_text(encoding="utf-8"))
    closeout = json.loads((tmp_path / "d_series_database_closeout_gate.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "multi_agent_summary.json").read_text(encoding="utf-8"))
    checkpoint = json.loads((tmp_path / "langgraph_node_checkpoints.json").read_text(encoding="utf-8"))

    assert Path(str(result["d_series_database_materialization_report"]["db_path"])).exists()
    assert result["d_series_database_closeout_gate"]["database_ready_layer_count"] == 11
    assert result["d_series_database_closeout_gate"]["pending_required_database_layer_count"] == 0
    assert result["d_series_database_closeout_gate"]["d_series_closeout_allowed"] is True
    assert result["artifact_refs"]["d_series_database_materialization_report"].endswith(
        "d_series_database_materialization_report.json"
    )
    assert report["layers"]["claim_evidence_ledger"]["parity_status"] == "pass"
    assert report["layers"]["analyst_view_research_memory"]["parity_status"] == "pass"
    assert closeout["database_ready_layer_count"] == 11
    assert summary["d_series_database_materialization"]["materialized_layer_count"] == 11
    assert summary["d_series_database_materialization"]["all_materialized_layers_parity_pass"] is True
    assert checkpoint["recoverable_state_summary"]["d_series_materialized_database_layer_count"] == 11

    second_output = tmp_path / "second"
    initial_second = make_multi_agent_smoke_state(
        user_query="继续写一段 MSFT revenue 和 shipments 证据边界 memo。",
        output_dir=second_output,
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
    initial_second["d_series_governance_db_path"] = str(db_path)

    second_result = graph.invoke(initial_second, config={"configurable": {"thread_id": "unit-d12-1-graph-second"}})
    second_summary = json.loads((second_output / "multi_agent_summary.json").read_text(encoding="utf-8"))
    second_checkpoint = json.loads((second_output / "langgraph_node_checkpoints.json").read_text(encoding="utf-8"))

    assert second_result["d_series_claim_gap_gate_reader_context"]["reader_default_status"] == "database_default"
    assert second_result["d_series_research_context"]["reader_default_status"] == "database_default"
    assert second_summary["d_series_claim_gap_gate_reader"]["typed_gap_count"] >= 1
    assert second_summary["d_series_research_context_reader"]["row_count"] >= 1
    assert second_summary["pre_memo_fact_selection"]["approved_fact_count"] >= 1
    assert second_summary["d_series_claim_gap_gate_reader"]["gate_history_count"] >= 1
    assert second_checkpoint["recoverable_state_summary"]["d_series_claim_gap_gate_reader_status"] == "database_default"
    assert second_checkpoint["recoverable_state_summary"]["d_series_research_context_reader_status"] == "database_default"
    assert second_checkpoint["recoverable_state_summary"]["pre_memo_approved_fact_count"] >= 1


def _sample_governance_artifacts(run_id: str = "unit-d12-1") -> dict:
    state = {
        "run_id": run_id,
        "project_inventory": {
            "companies": [
                {
                    "ticker": "MSFT",
                    "company": "Microsoft Corporation",
                    "cik": "789019",
                    "lei": "INR2EJN1ERAN0W5ZP974",
                    "filings": [
                        {
                            "form_type": "10-K",
                            "year": 2025,
                            "source_tier": "primary_sec_filing",
                            "accession_number": "0000950170-26-000000",
                            "filing_date": "2025-07-30",
                            "period_end": "2025-06-30",
                        }
                    ],
                }
            ]
        },
        "agent_activation_plan": {"allowed_source_families": ["primary_sec_filing", "public_source_context", "live_public_web_context"]},
        "retrieval_plan": {
            "routes": [
                {"route_id": "route_sec", "task_id": "task", "retrieval_route": "ledger_first"},
                {"route_id": "route_public_proxy_blocked", "task_id": "task", "retrieval_route": "live_public_web_context"},
            ]
        },
        "evidence_requirement_plan": {
            "requirements": [
                {"requirement_id": "req_sec", "source_families": ["primary_sec_filing"]},
                {"requirement_id": "req_public", "source_families": ["live_public_web_context"]},
            ]
        },
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
                "source_url": "https://www.sec.gov/Archives/edgar/data/789019/msft-2025.htm",
                "accession_number": "0000950170-26-000000",
                "filing_date": "2025-07-30",
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
                "source_url": "https://www.sec.gov/Archives/edgar/data/789019/msft-2025.htm",
                "accession_number": "0000950170-26-000000",
                "filing_date": "2025-07-30",
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
    from sec_agent.entity_master import build_entity_security_master
    from sec_agent.provenance_vintage import build_provenance_vintage_layers
    from sec_agent.source_capability_router import build_source_capability_router

    entity_master = build_entity_security_master(state)
    source_router = build_source_capability_router(state)
    provenance_vintage = build_provenance_vintage_layers({**state, "entity_security_master": entity_master, "source_capability_router": source_router})
    ontology = build_metric_product_ontology_snapshot({**state, **ledgers})
    reconciliation = build_reconciliation_ledger({**state, **ledgers, **provenance_vintage, "metric_product_ontology_snapshot": ontology})
    gate_matrix = build_gate_registry_eval_matrix(
        {
            **state,
            **ledgers,
            **provenance_vintage,
            "entity_security_master": entity_master,
            "source_capability_router": source_router,
            "metric_product_ontology_snapshot": ontology,
            "reconciliation_ledger": reconciliation,
        }
    )
    from sec_agent.derived_metric_layer import build_derived_metric_layer
    from sec_agent.analyst_view_layer import build_analyst_view_research_memory_layer

    derived_layer = build_derived_metric_layer(
        {
            **state,
            **ledgers,
            **provenance_vintage,
            "metric_product_ontology_snapshot": ontology,
            "reconciliation_ledger": reconciliation,
            "gate_registry_eval_matrix": gate_matrix,
        }
    )
    analyst_views = build_analyst_view_research_memory_layer(
        {**state, **ledgers, "derived_metric_layer": derived_layer}
    )
    return {
        **state,
        **ledgers,
        **provenance_vintage,
        "entity_security_master": entity_master,
        "source_capability_router": source_router,
        "metric_product_ontology_snapshot": ontology,
        "reconciliation_ledger": reconciliation,
        "gate_registry_eval_matrix": gate_matrix,
        "derived_metric_layer": derived_layer,
        "analyst_view_research_memory": analyst_views,
    }
