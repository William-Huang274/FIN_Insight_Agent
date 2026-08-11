from __future__ import annotations

import sqlite3
from pathlib import Path

from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph, make_multi_agent_smoke_state
from sec_agent.run_audit_store import materialize_run_audit_store, read_run_audit_counts


def _sample_state(tmp_path: Path) -> dict:
    return {
        "run_id": "unit_run_audit_case",
        "case_id": "case",
        "user_query": "写一段测试 memo。",
        "status": "completed",
        "output_dir": str(tmp_path),
        "query_contract": {"focus_tickers": ["NVDA"], "data_snapshot_id": "unit_snapshot"},
        "node_checkpoints": [
            {
                "node": "research_lead_plan",
                "index": 1,
                "checkpoint_id": "checkpoint_1",
                "finished_at": "2026-06-13T00:00:00Z",
                "elapsed_ms": 10,
                "state_summary": {"status": "running"},
            },
            {
                "node": "verify_claims",
                "index": 2,
                "checkpoint_id": "checkpoint_2",
                "previous_checkpoint_id": "checkpoint_1",
                "finished_at": "2026-06-13T00:00:01Z",
                "elapsed_ms": 20,
                "state_summary": {"status": "completed"},
            },
        ],
        "artifact_refs": {"memo_answer": str(tmp_path / "memo_answer.json")},
        "context_rows": [{"evidence_ref": "ctx_ref", "source_family": "primary_sec_filing", "ticker": "NVDA"}],
        "verified_judgment_plan": {
            "supported_claims": [
                {
                    "claim_id": "claim_1",
                    "claim": "Supported claim.",
                    "claim_type": "company_reported_financial_fact",
                    "analysis_dimension": "fundamentals",
                    "evidence_refs": ["ctx_ref"],
                    "source_families": ["primary_sec_filing"],
                }
            ],
            "unsupported_claims": [{"claim": "Unsupported claim.", "reason": "missing evidence"}],
        },
        "source_gaps": [{"gap_id": "gap_1", "gap_type": "commercial_tracker_gap"}],
        "specialist_verification": {"status": "pass"},
        "claim_verification": {"status": "pass", "analyst_depth_gate": {"status": "pass"}},
        "research_lead_model_diagnostics": {"calls": [{"model": "unit-model", "total_tokens": 7, "finish_reason": "stop"}]},
    }


def test_run_audit_store_materializes_required_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "run_audit.sqlite"
    report = materialize_run_audit_store(db_path, _sample_state(tmp_path))
    counts = read_run_audit_counts(db_path, run_id="unit_run_audit_case")

    assert report["status"] == "pass"
    assert counts["run"] == 1
    assert counts["node_execution"] == 2
    assert counts["artifact_ref"] == 1
    assert counts["evidence_row"] == 1
    assert counts["claim_card"] == 1
    assert counts["gap"] >= 1
    assert counts["gate_result"] >= 2
    assert counts["model_call"] == 1

    with sqlite3.connect(db_path) as conn:
        for table in ("run", "node_execution", "artifact_ref", "evidence_row", "claim_card", "gap", "gate_result", "model_call"):
            columns = {row[1] for row in conn.execute(f'pragma table_info("{table}")')}
            assert {
                "run_id",
                "case_id",
                "node",
                "input_digest",
                "output_digest",
                "code_commit",
                "data_snapshot_id",
                "artifact_uri",
            } <= columns


def test_graph_persist_materializes_run_audit_store(tmp_path: Path) -> None:
    db_path = tmp_path / "graph_run_audit.sqlite"
    state = make_multi_agent_smoke_state(
        user_query="写一段测试 memo。",
        output_dir=tmp_path / "run",
        query_contract={"focus_tickers": ["NVDA"]},
        focus_tickers=["NVDA"],
        search_scope_tickers=["NVDA"],
    )
    state["case_id"] = "unit_graph_case"
    state["run_audit_db_path"] = str(db_path)
    graph = build_multi_agent_orchestration_graph(use_checkpointer=False)

    result = graph.invoke(state)
    counts = read_run_audit_counts(db_path, run_id=str(result["run_id"]))

    assert result["run_audit_materialization_report"]["status"] == "pass"
    assert result["run_audit_materialization_report"]["case_id"] == "unit_graph_case"
    assert result["artifact_refs"]["run_audit_db"] == str(db_path.resolve())
    assert (tmp_path / "run" / "run_audit_materialization_report.json").exists()
    assert counts["run"] == 1
    assert counts["node_execution"] >= 1
