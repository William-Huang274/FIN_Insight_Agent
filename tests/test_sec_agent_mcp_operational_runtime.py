from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from sec_agent.mcp_contracts import list_mcp_tool_contracts
from sec_agent.mcp_operational import McpRuntimeProfile, McpToolProcessSupervisor, bind_mcp_resources
from sec_agent.mcp_server import MCP_SERVER_BUSINESS_TOOL_NAMES
from sec_agent.mcp_tool_registry import _interactive_args_for_sec_search
from sec_agent.mcp_tool_registry import invoke_mcp_tool


def _runtime_profile(tmp_path: Path, *, market_path: Path) -> Path:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("{}\n", encoding="utf-8")
    bm25 = tmp_path / "bm25"
    object_bm25 = tmp_path / "object_bm25"
    bm25.mkdir()
    object_bm25.mkdir()
    ledger = tmp_path / "ledger.duckdb"
    ledger.write_bytes(b"fixture")
    profile = tmp_path / "mcp_profile.json"
    profile.write_text(
        json.dumps(
            {
                "profile_id": "test_mcp_profile",
                "resources": {
                    "manifest_path": str(manifest),
                    "bm25_index_dir": str(bm25),
                    "object_bm25_index_dir": str(object_bm25),
                    "ledger_store_path": str(ledger),
                    "market_evidence_path": str(market_path),
                },
                "default_timeout_s": 2,
                "tool_timeouts_s": {"market_get_snapshot": 2},
            }
        ),
        encoding="utf-8",
    )
    return profile


def test_server_business_tool_surface_matches_registry_contracts() -> None:
    contract_names = {str(row["name"]) for row in list_mcp_tool_contracts()}
    assert MCP_SERVER_BUSINESS_TOOL_NAMES == contract_names
    assert len(contract_names) == 9


def test_sec_search_zero_rerank_binds_explicit_bm25_only_mode(tmp_path: Path) -> None:
    market = tmp_path / "market.jsonl"
    market.write_text("", encoding="utf-8")
    profile = McpRuntimeProfile.load(_runtime_profile(tmp_path, market_path=market))

    bound, receipt = bind_mcp_resources(
        "sec_search_filings",
        {"query": "NVDA revenue", "rerank_budget": 0},
        profile,
    )

    assert receipt["status"] == "pass"
    assert bound["context_reranker"] == "none"
    assert bound["allow_bm25_only_pipeline"] is True
    runtime_args = _interactive_args_for_sec_search(bound)
    assert runtime_args.context_reranker == "none"
    assert runtime_args.allow_bm25_only_pipeline is True


def test_sec_search_bge_mode_fails_binding_when_reranker_is_not_configured(tmp_path: Path) -> None:
    market = tmp_path / "market.jsonl"
    market.write_text("", encoding="utf-8")
    profile = McpRuntimeProfile.load(_runtime_profile(tmp_path, market_path=market))

    _bound, receipt = bind_mcp_resources(
        "sec_search_filings",
        {"query": "NVDA revenue", "rerank_budget": 8},
        profile,
    )

    assert receipt["status"] == "fail"
    assert receipt["missing"] == [
        {
            "resource": "bge_model",
            "reason_code": "canonical_reranker_not_configured",
        }
    ]


def test_sec_search_zero_rerank_is_preserved_in_compiled_requirement(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "ticker": "NVDA",
                "fiscal_year": 2025,
                "form_type": "10-K",
                "source_tier": "primary_sec_filing",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def build_query_plan_for_graph(_runtime_args, _query):
        return {
            "query_contract": {
                "search_scope_tickers": ["NVDA"],
                "years": [2025],
                "filing_types": ["10-K"],
                "source_tiers": ["primary_sec_filing"],
            },
            "selected_tickers": ["NVDA"],
            "selected_years": [2025],
        }

    def retrieve_context_for_graph(_runtime_args, graph_state):
        assert graph_state["query_contract"]["evidence_requirements"][0]["rerank_budget"] == 0
        return {
            "context_rows": [{"evidence_id": "NVDA_2025_10K"}],
            "retrieval_trace": {
                "context_summary": {"context_row_count": 1},
                "context_policy": {"candidate_row_count_pre_rerank": 1, "candidate_sent_to_bge": 0},
            },
            "context_runtime": {"context_reranker": "none"},
            "artifact_refs": {},
        }

    monkeypatch.setattr(
        "sec_agent.mcp_tool_registry._load_interactive_module",
        lambda: SimpleNamespace(
            build_query_plan_for_graph=build_query_plan_for_graph,
            retrieve_context_for_graph=retrieve_context_for_graph,
        ),
    )
    result = invoke_mcp_tool(
        "sec_search_filings",
        {
            "query": "NVDA revenue",
            "tickers": ["NVDA"],
            "years": [2025],
            "filing_types": ["10-K"],
            "source_tiers": ["primary_sec_filing"],
            "manifest_path": str(manifest),
            "rerank_budget": 0,
        },
    )
    assert result["status"] == "ok"


def test_process_supervisor_reuses_warm_worker_and_emits_phase_receipts(tmp_path: Path) -> None:
    market = tmp_path / "market.jsonl"
    market.write_text(
        json.dumps({"ticker": "NVDA", "snapshot_id": "S1", "as_of_date": "2026-05-29"}) + "\n",
        encoding="utf-8",
    )
    supervisor = McpToolProcessSupervisor(
        profile_path=_runtime_profile(tmp_path, market_path=market),
    )
    try:
        first = supervisor.invoke("market_get_snapshot", {"tickers": ["NVDA"], "limit": 1})
        second = supervisor.invoke("market_get_snapshot", {"tickers": ["NVDA"], "limit": 1})
        assert first["status"] == "ok"
        assert second["status"] == "ok"
        assert first["operational"]["start_kind"] == "cold"
        assert second["operational"]["start_kind"] == "warm"
        assert first["operational"]["worker_pid"] == second["operational"]["worker_pid"]
        assert [row["phase"] for row in second["operational"]["phases"]] == [
            "resource_binding",
            "worker_start",
            "handler_execution",
        ]
        assert second["operational"]["terminal_status"] == "pass"
    finally:
        supervisor.close()
    assert supervisor.worker_alive is False


def test_process_supervisor_timeout_terminates_worker_without_orphan(tmp_path: Path) -> None:
    market = tmp_path / "market.jsonl"
    market.write_text(
        json.dumps({"ticker": "NVDA", "snapshot_id": "S1", "as_of_date": "2026-05-29"}) + "\n",
        encoding="utf-8",
    )
    supervisor = McpToolProcessSupervisor(
        profile_path=_runtime_profile(tmp_path, market_path=market),
        _test_request_delay_s=0.5,
    )
    try:
        result = supervisor.invoke(
            "market_get_snapshot",
            {"tickers": ["NVDA"], "limit": 1, "timeout_s": 0.05},
        )
        assert result["status"] == "error"
        assert result["error"] == "mcp_tool_timeout"
        assert result["operational"]["phases"][-1]["status"] == "timeout"
        assert supervisor.worker_alive is False
        assert supervisor.last_terminated_exitcode is not None
    finally:
        supervisor.close()


def test_process_supervisor_cancel_terminates_worker_and_next_call_is_cold(tmp_path: Path) -> None:
    market = tmp_path / "market.jsonl"
    market.write_text(
        json.dumps({"ticker": "NVDA", "snapshot_id": "S1", "as_of_date": "2026-05-29"}) + "\n",
        encoding="utf-8",
    )
    supervisor = McpToolProcessSupervisor(
        profile_path=_runtime_profile(tmp_path, market_path=market),
    )
    try:
        first = supervisor.invoke("market_get_snapshot", {"tickers": ["NVDA"], "limit": 1})
        assert first["status"] == "ok"
        supervisor.cancel()
        assert supervisor.worker_alive is False
        second = supervisor.invoke("market_get_snapshot", {"tickers": ["NVDA"], "limit": 1})
        assert second["status"] == "ok"
        assert second["operational"]["start_kind"] == "cold"
        assert second["operational"]["worker_pid"] != first["operational"]["worker_pid"]
    finally:
        supervisor.close()
