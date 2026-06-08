from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import duckdb

import sec_agent.mcp_tool_registry as mcp_registry
from sec_agent.industry_snapshot import query_industry_snapshot
from sec_agent.mcp_tool_registry import invoke_mcp_tool, list_registered_tools


def test_mcp_registry_forwards_high_cost_tool_to_resident_worker(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or "0")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            captured.update(payload)
            body = json.dumps(
                {
                    "status": "ok",
                    "tool_name": payload["tool_name"],
                    "context_rows": [{"evidence_ref": "row-1", "vector_kind": "paraphrase_context"}],
                    "row_count": 1,
                    "resident_worker": {"pid": 123, "server_elapsed_ms": 4},
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("SEC_AGENT_MCP_RESIDENT_URL", f"http://127.0.0.1:{server.server_port}")
        result = invoke_mcp_tool("sec_milvus_semantic_search", {"query": "NVDA fundamentals", "tickers": ["NVDA"]})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert captured["tool_name"] == "sec_milvus_semantic_search"
    assert captured["arguments"] == {"query": "NVDA fundamentals", "tickers": ["NVDA"]}
    assert result["status"] == "ok"
    assert result["row_count"] == 1
    assert result["resident_worker"]["pid"] == 123
    assert "client_elapsed_ms" in result["resident_worker"]


def test_mcp_sec_search_context_runner_aliases_use_in_process() -> None:
    args = mcp_registry._interactive_args_for_sec_search({"query": "NVDA", "context_runner": "interactive"})

    assert args.context_runner == "in_process"


def _build_industry_duckdb(path: Path) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute(
            """
            CREATE TABLE industry_observations (
                source_family VARCHAR,
                provider VARCHAR,
                dataset_id VARCHAR,
                series_id VARCHAR,
                observation_date DATE,
                as_of_date DATE,
                frequency VARCHAR,
                value DOUBLE,
                unit VARCHAR,
                revision_status VARCHAR,
                fetched_at TIMESTAMP,
                route_type VARCHAR,
                api_route VARCHAR,
                facet_json VARCHAR,
                allowed_claim_types_json VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE TABLE industry_evidence_rows (
                evidence_id VARCHAR,
                source_family VARCHAR,
                provider VARCHAR,
                dataset_id VARCHAR,
                series_id VARCHAR,
                as_of_date DATE,
                allowed_claim_types_json VARCHAR,
                summary VARCHAR,
                caveats_json VARCHAR,
                latest_observation_date DATE,
                latest_value DOUBLE,
                unit VARCHAR,
                frequency VARCHAR,
                fetched_at TIMESTAMP,
                route_type VARCHAR,
                api_route VARCHAR,
                facet_json VARCHAR,
                payload_top_level_type VARCHAR
            )
            """
        )
        con.execute(
            "INSERT INTO industry_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "industry_utilities_power_demand",
                "EIA",
                "eia/electricity/retail-sales",
                "EIA_RETAIL_SALES::US::ALL::sales",
                "2026-03-01",
                "2026-05-30",
                "monthly",
                314308.2,
                "million kWh",
                "latest_provider_api",
                "2026-05-30 00:00:00",
                "eia_v2_json",
                "https://api.eia.gov/v2/electricity/retail-sales/data/?api_key=<redacted>",
                json.dumps({"stateid": "US", "sectorid": "ALL"}, sort_keys=True),
                json.dumps(["power_demand_context"]),
            ],
        )
        con.execute(
            "INSERT INTO industry_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "industry_utilities_power_demand",
                "EIA",
                "eia/electricity/retail-sales",
                "EIA_RETAIL_SALES::US::RES::sales",
                "2026-03-01",
                "2026-05-30",
                "monthly",
                130000.0,
                "million kWh",
                "latest_provider_api",
                "2026-05-30 00:00:00",
                "eia_v2_json",
                "https://api.eia.gov/v2/electricity/retail-sales/data/?api_key=<redacted>",
                json.dumps({"stateid": "US", "sectorid": "RES"}, sort_keys=True),
                json.dumps(["power_demand_context"]),
            ],
        )
        con.execute(
            "INSERT INTO industry_evidence_rows VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "INDUSTRY::industry_utilities_power_demand::eia/electricity/retail-sales::2026-05-30",
                "industry_utilities_power_demand",
                "EIA",
                "eia/electricity/retail-sales",
                "",
                "2026-05-30",
                json.dumps(["power_demand_context"]),
                "EIA retail-sales has normalized monthly observations.",
                json.dumps(["Industry data provides context only."]),
                "2026-03-01",
                314308.2,
                "million kWh",
                "monthly",
                "2026-05-30 00:00:00",
                "eia_v2_json",
                "https://api.eia.gov/v2/electricity/retail-sales/data/?api_key=<redacted>",
                json.dumps({"stateid": "US"}, sort_keys=True),
                "dict",
            ],
        )
    finally:
        con.close()


def test_industry_snapshot_queries_duckdb_observations_with_facets(tmp_path: Path) -> None:
    db_path = tmp_path / "industry_snapshot.duckdb"
    _build_industry_duckdb(db_path)

    result = query_industry_snapshot(
        source_families=["industry_utilities_power_demand"],
        providers=["EIA"],
        facets={"sectorid": "ALL"},
        latest_only=True,
        industry_snapshot_db_path=db_path,
        limit=10,
    )

    assert result["status"] == "ok"
    assert result["summary"]["evidence_row_count"] == 1
    assert result["summary"]["observation_count"] == 1
    assert result["observations"][0]["series_id"] == "EIA_RETAIL_SALES::US::ALL::sales"
    assert result["observations"][0]["facet"]["sectorid"] == "ALL"
    assert result["industry_rows"][0]["allowed_claim_types"] == ["power_demand_context"]


def test_mcp_registry_invokes_industry_tool(tmp_path: Path) -> None:
    db_path = tmp_path / "industry_snapshot.duckdb"
    _build_industry_duckdb(db_path)

    tools = {tool["name"] for tool in list_registered_tools()}
    assert "industry_get_snapshot" in tools

    result = invoke_mcp_tool(
        "industry_get_snapshot",
        {
            "industry_snapshot_db_path": str(db_path),
            "source_families": ["industry_utilities_power_demand"],
            "providers": ["EIA"],
            "latest_only": True,
            "limit": 5,
        },
    )

    assert result["status"] == "ok"
    assert result["observations"]


def test_mcp_registry_invokes_market_tool(tmp_path: Path) -> None:
    path = tmp_path / "market_evidence.jsonl"
    path.write_text(
        json.dumps(
            {
                "source_tier": "market_snapshot",
                "ticker": "NVDA",
                "snapshot_id": "snapshot_v1",
                "as_of_date": "2026-05-22",
                "return_3m": 0.12,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke_mcp_tool(
        "market_get_snapshot",
        {
            "market_evidence_path": str(path),
            "tickers": ["NVDA"],
            "snapshot_id": "snapshot_v1",
            "fields": ["return_3m", "ev_sales_ttm"],
        },
    )

    assert result["status"] == "ok"
    assert result["market_rows"][0]["ticker"] == "NVDA"
    assert result["field_gaps"] == [{"ticker": "NVDA", "field": "ev_sales_ttm", "reason": "missing_or_null"}]


def test_mcp_registry_invokes_sec_search_filings_through_graph_adapter(tmp_path: Path, monkeypatch) -> None:
    trace_path = tmp_path / "trace_logs.jsonl"

    def fake_build_query_plan_for_graph(runtime_args, query):
        assert query == "Compare AMD and NVDA data center revenue"
        assert runtime_args.manifest_path == "unit_manifest.jsonl"
        assert runtime_args.tickers == "AMD,NVDA"
        assert runtime_args.years == "2026"
        assert runtime_args.max_context_rows == 3
        return {
            "query_contract": {
                "task_type": "company_comparison",
                "search_scope_tickers": ["AMD", "NVDA"],
                "focus_tickers": ["AMD", "NVDA"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["revenue"],
                "decomposed_tasks": [
                    {
                        "task_id": "compare_revenue",
                        "question_zh": "Compare data center revenue.",
                        "priority": "primary",
                        "required_tickers": ["AMD", "NVDA"],
                        "required_metric_families": ["revenue"],
                    }
                ],
            },
            "selected_tickers": ["AMD", "NVDA"],
            "selected_years": [2026],
        }

    def fake_retrieve_context_for_graph(runtime_args, graph_state):
        assert runtime_args.reranker_candidate_limit == 25
        assert runtime_args.reranker_top_k == 2
        assert graph_state["output_dir"] == str(tmp_path.resolve())
        requirement = graph_state["query_contract"]["evidence_requirements"][0]
        assert requirement["evidence_routes"] == ["filing_text"]
        assert requirement["metric_families"] == ["data_center_revenue"]
        return {
            "context_rows": [
                {
                    "evidence_id": "NVDA_2026_10Q_DATA_CENTER",
                    "ticker": "NVDA",
                    "fiscal_year": 2026,
                    "form_type": "10-Q",
                    "source_tier": "primary_sec_filing",
                    "text": "Data center revenue evidence.",
                }
            ],
            "retrieval_trace": {
                "context_summary": {"context_row_count": 1},
                "context_policy": {
                    "candidate_row_count_pre_rerank": 9,
                    "candidate_sent_to_bge": 2,
                    "route_candidate_stats": [{"route_id": "compare_revenue::filing_text", "candidate_count": 9}],
                },
            },
            "context_runtime": {"context_runner": "fake"},
            "artifact_refs": {"retrieved_context": str(trace_path)},
        }

    fake_interactive = SimpleNamespace(
        build_query_plan_for_graph=fake_build_query_plan_for_graph,
        retrieve_context_for_graph=fake_retrieve_context_for_graph,
    )
    monkeypatch.setattr("sec_agent.mcp_tool_registry._load_interactive_module", lambda: fake_interactive)

    result = invoke_mcp_tool(
        "sec_search_filings",
        {
            "query": "Compare AMD and NVDA data center revenue",
            "tickers": ["AMD", "NVDA"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing"],
            "metric_families": ["data_center_revenue"],
            "period_roles": ["QTD", "YTD"],
            "retrieval_route": "filing_text",
            "manifest_path": "unit_manifest.jsonl",
            "output_dir": str(tmp_path),
            "candidate_budget": 25,
            "rerank_budget": 2,
            "limit": 3,
        },
    )

    assert result["status"] == "ok"
    assert result["context_rows"][0]["evidence_id"] == "NVDA_2026_10Q_DATA_CENTER"
    assert result["query_contract"]["metric_families"] == ["data_center_revenue"]
    assert result["candidate_counts"]["candidate_row_count_pre_rerank"] == 9
    assert result["candidate_counts"]["candidate_sent_to_bge"] == 2
    assert result["artifact_refs"] == [
        {"artifact_id": "retrieved_context", "path": str(trace_path), "digest": "", "row_count": 1}
    ]


def test_mcp_sec_search_result_cache_ignores_run_artifact_paths(tmp_path: Path, monkeypatch) -> None:
    calls = {"retrieve": 0}
    mcp_registry._SEC_SEARCH_RESULT_CACHE.clear()
    monkeypatch.delenv("SEC_AGENT_MCP_RESIDENT_URL", raising=False)
    monkeypatch.setenv("SEC_AGENT_MCP_SEC_SEARCH_RESULT_CACHE", "1")

    def fake_build_query_plan_for_graph(runtime_args, query):
        return {
            "query_contract": {
                "search_scope_tickers": ["NVDA"],
                "focus_tickers": ["NVDA"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["revenue"],
            },
            "selected_tickers": ["NVDA"],
            "selected_years": [2026],
        }

    def fake_retrieve_context_for_graph(runtime_args, graph_state):
        calls["retrieve"] += 1
        return {
            "context_rows": [
                {
                    "evidence_id": f"NVDA_ROW_{calls['retrieve']}",
                    "ticker": "NVDA",
                    "fiscal_year": 2026,
                    "form_type": "10-Q",
                    "source_tier": "primary_sec_filing",
                    "text": "Revenue evidence.",
                }
            ],
            "retrieval_trace": {"context_summary": {"context_row_count": 1}, "context_policy": {}},
            "context_runtime": {"context_runner": "fake"},
            "artifact_refs": {},
        }

    fake_interactive = SimpleNamespace(
        build_query_plan_for_graph=fake_build_query_plan_for_graph,
        retrieve_context_for_graph=fake_retrieve_context_for_graph,
    )
    monkeypatch.setattr("sec_agent.mcp_tool_registry._load_interactive_module", lambda: fake_interactive)
    args = {
        "query": "NVIDIA revenue evidence",
        "tickers": ["NVDA"],
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["revenue"],
        "retrieval_route": "filing_text",
        "limit": 3,
    }

    first = invoke_mcp_tool(
        "sec_search_filings",
        {**args, "run_id": "run_a", "output_dir": str(tmp_path / "a"), "route_selection_reason": "first reason"},
    )
    second = invoke_mcp_tool(
        "sec_search_filings",
        {**args, "run_id": "run_b", "output_dir": str(tmp_path / "b"), "route_selection_reason": "second reason"},
    )

    assert calls["retrieve"] == 1
    assert first["mcp_result_cache"]["hit"] is False
    assert second["mcp_result_cache"]["hit"] is True
    assert second["context_rows"][0]["evidence_id"] == "NVDA_ROW_1"


def test_mcp_registry_compiles_mixed_sec_scope_to_available_route_requirements(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_rows = [
        {"ticker": "NVDA", "fiscal_year": 2025, "form_type": "10-K", "source_tier": "primary_sec_filing"},
        {"ticker": "AMD", "fiscal_year": 2025, "form_type": "10-K", "source_tier": "primary_sec_filing"},
        {"ticker": "NVDA", "fiscal_year": 2026, "form_type": "8-K", "source_tier": "company_authored_unaudited_sec_filing"},
        {"ticker": "AMD", "fiscal_year": 2026, "form_type": "8-K", "source_tier": "company_authored_unaudited_sec_filing"},
    ]
    manifest_path.write_text("".join(json.dumps(row) + "\n" for row in manifest_rows), encoding="utf-8")

    def fake_build_query_plan_for_graph(runtime_args, query):
        return {
            "query_contract": {
                "task_type": "company_comparison",
                "search_scope_tickers": ["AMD", "NVDA"],
                "focus_tickers": ["AMD", "NVDA"],
                "years": [2025, 2026],
                "filing_types": ["10-K", "8-K"],
                "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
                "metric_families": ["revenue"],
            },
            "selected_tickers": ["AMD", "NVDA"],
            "selected_years": [2025, 2026],
        }

    def fake_retrieve_context_for_graph(runtime_args, graph_state):
        requirements = graph_state["query_contract"]["evidence_requirements"]
        route_scopes = {
            tuple(req["evidence_routes"]): (req["years"], req["filing_types"], req["source_tiers"], req["tickers"])
            for req in requirements
        }
        assert route_scopes[("filing_text",)] == (
            [2025],
            ["10-K"],
            ["primary_sec_filing"],
            ["AMD", "NVDA"],
        )
        assert route_scopes[("8k_commentary",)] == (
            [2026],
            ["8-K"],
            ["company_authored_unaudited_sec_filing"],
            ["AMD", "NVDA"],
        )
        assert graph_state["query_contract"]["source_coverage_gaps"]
        return {
            "context_rows": [{"evidence_id": "NVDA_2026_8K", "ticker": "NVDA"}],
            "retrieval_trace": {
                "context_summary": {"context_row_count": 1},
                "context_policy": {"candidate_row_count_pre_rerank": 2, "candidate_sent_to_bge": 1},
            },
            "context_runtime": {"context_runner": "fake"},
            "artifact_refs": {"retrieved_context": str(tmp_path / "trace.jsonl")},
        }

    fake_interactive = SimpleNamespace(
        build_query_plan_for_graph=fake_build_query_plan_for_graph,
        retrieve_context_for_graph=fake_retrieve_context_for_graph,
    )
    monkeypatch.setattr("sec_agent.mcp_tool_registry._load_interactive_module", lambda: fake_interactive)

    result = invoke_mcp_tool(
        "sec_search_filings",
        {
            "query": "Compare FY2025 10-K fundamentals and FY2026 8-K management commentary",
            "tickers": ["NVDA", "AMD"],
            "years": [2025, 2026],
            "filing_types": ["10-K", "8-K"],
            "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
            "metric_families": ["revenue"],
            "manifest_path": str(manifest_path),
            "output_dir": str(tmp_path),
            "candidate_budget": 25,
            "rerank_budget": 2,
        },
    )

    assert result["status"] == "ok"
    assert result["query_contract"]["source_coverage_gaps"]
    assert result["source_gaps"] == result["query_contract"]["source_coverage_gaps"]


def test_mcp_registry_infers_available_scope_from_evidence_ids_without_form_type(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "evidence.jsonl"
    manifest_rows = [
        {
            "ticker": "AMZN",
            "fiscal_year": 2025,
            "source_tier": "primary_sec_filing",
            "evidence_id": "AMZN_2025_10K_ITEM7_BLOCK_0001_CHUNK_0001",
        },
        {
            "ticker": "AMZN",
            "fiscal_year": 2026,
            "source_tier": "company_authored_unaudited_sec_filing",
            "evidence_id": "AMZN_2026_8K_ITEM2_02_BLOCK_0001_CHUNK_0001",
        },
    ]
    manifest_path.write_text("".join(json.dumps(row) + "\n" for row in manifest_rows), encoding="utf-8")

    def fake_build_query_plan_for_graph(runtime_args, query):
        return {
            "query_contract": {
                "task_type": "company_analysis",
                "search_scope_tickers": ["AMZN"],
                "focus_tickers": ["AMZN"],
                "years": [2025, 2026],
                "filing_types": ["10-K", "8-K"],
                "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
                "metric_families": ["margin"],
            },
            "selected_tickers": ["AMZN"],
            "selected_years": [2025, 2026],
        }

    def fake_retrieve_context_for_graph(runtime_args, graph_state):
        requirements = graph_state["query_contract"]["evidence_requirements"]
        route_scopes = {
            tuple(req["evidence_routes"]): (req["years"], req["filing_types"], req["source_tiers"], req["tickers"])
            for req in requirements
        }
        assert route_scopes[("filing_text",)] == ([2025], ["10-K"], ["primary_sec_filing"], ["AMZN"])
        assert route_scopes[("8k_commentary",)] == (
            [2026],
            ["8-K"],
            ["company_authored_unaudited_sec_filing"],
            ["AMZN"],
        )
        return {
            "context_rows": [{"evidence_id": "AMZN_2026_8K_ITEM2_02_BLOCK_0001_CHUNK_0001", "ticker": "AMZN"}],
            "retrieval_trace": {
                "context_summary": {"context_row_count": 1},
                "context_policy": {"candidate_row_count_pre_rerank": 2, "candidate_sent_to_bge": 1},
            },
            "context_runtime": {"context_runner": "fake"},
            "artifact_refs": {"retrieved_context": str(tmp_path / "trace.jsonl")},
        }

    fake_interactive = SimpleNamespace(
        build_query_plan_for_graph=fake_build_query_plan_for_graph,
        retrieve_context_for_graph=fake_retrieve_context_for_graph,
    )
    monkeypatch.setattr("sec_agent.mcp_tool_registry._load_interactive_module", lambda: fake_interactive)

    result = invoke_mcp_tool(
        "sec_search_filings",
        {
            "query": "Compare AMZN FY2025 10-K margin context with FY2026 8-K commentary",
            "tickers": ["AMZN"],
            "years": [2025, 2026],
            "filing_types": ["10-K", "8-K"],
            "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
            "metric_families": ["margin"],
            "manifest_path": str(manifest_path),
            "output_dir": str(tmp_path),
            "candidate_budget": 25,
            "rerank_budget": 2,
        },
    )

    assert result["status"] == "ok"
    assert result["context_rows"][0]["evidence_id"].startswith("AMZN_2026_8K")


def test_mcp_sec_search_overlay_refreshes_explicit_banking_metric_scope(tmp_path: Path, monkeypatch) -> None:
    def fake_build_query_plan_for_graph(runtime_args, query):
        return {
            "query_contract": {
                "task_type": "risk_summary",
                "search_scope_tickers": ["JPM", "C", "GS"],
                "focus_tickers": ["JPM"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["net_interest_income"],
                "ledger_rules": {
                    "allowed_metric_families": ["net_interest_income"],
                    "banking_metric_tickers": ["JPM"],
                },
            },
            "selected_tickers": ["JPM", "C", "GS"],
            "selected_years": [2026],
        }

    def fake_retrieve_context_for_graph(runtime_args, graph_state):
        assert graph_state["query_contract"]["ledger_rules"]["banking_metric_tickers"] == ["JPM", "C", "GS"]
        return {
            "context_rows": [{"evidence_id": "C_2026_10Q_NII", "ticker": "C"}],
            "retrieval_trace": {
                "context_summary": {"context_row_count": 1},
                "context_policy": {"candidate_row_count_pre_rerank": 1, "candidate_sent_to_bge": 1},
            },
            "context_runtime": {"context_runner": "fake"},
            "artifact_refs": {"retrieved_context": str(tmp_path / "trace.jsonl")},
        }

    fake_interactive = SimpleNamespace(
        build_query_plan_for_graph=fake_build_query_plan_for_graph,
        retrieve_context_for_graph=fake_retrieve_context_for_graph,
    )
    monkeypatch.setattr("sec_agent.mcp_tool_registry._load_interactive_module", lambda: fake_interactive)

    result = invoke_mcp_tool(
        "sec_search_filings",
        {
            "query": "Compare banking net interest income across JPM C GS",
            "tickers": ["JPM", "C", "GS"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing"],
            "metric_families": ["net_interest_income"],
            "retrieval_route": "filing_text",
            "output_dir": str(tmp_path),
        },
    )

    assert result["status"] == "ok"
    assert result["query_contract"]["ledger_rules"]["banking_metric_tickers"] == ["JPM", "C", "GS"]


def test_mcp_registry_rejects_non_sec_source_tier_for_sec_search() -> None:
    result = invoke_mcp_tool(
        "sec_search_filings",
        {
            "query": "Compare AMD and NVDA",
            "source_tiers": ["market_snapshot"],
        },
    )

    assert result["status"] == "error"
    assert result["error"] == "invalid_sec_search_source_tiers:market_snapshot"


def test_mcp_milvus_semantic_search_returns_typed_bounded_rows(monkeypatch) -> None:
    class FakeEmbedding:
        def __init__(self, value: float = 0.1) -> None:
            self.value = value

        def tolist(self) -> list[float]:
            return [self.value, 0.2, 0.3]

    class FakeModel:
        encoded_queries: list[str] = []

        def encode(self, queries, **kwargs):
            self.encoded_queries = list(queries)
            return [FakeEmbedding(0.1 + index / 10) for index, _query in enumerate(queries)]

    class FakeMilvusClient:
        calls: list[dict[str, object]] = []

        def __init__(self, uri: str) -> None:
            self.uri = uri

        def load_collection(self, collection_name: str) -> None:
            self.collection_name = collection_name

        def search(self, **kwargs):
            self.calls.append(kwargs)
            assert len(kwargs["data"]) == 3
            return [
                [
                    {
                        "distance": 0.91,
                        "entity": {
                            "vector_id": "NVDA_2026_10Q_RISK::paraphrase_context",
                            "evidence_id": "NVDA_2026_10Q_RISK",
                            "ticker": "NVDA",
                            "fiscal_year": 2026,
                            "form_type": "10-Q",
                            "source_tier": "primary_sec_filing",
                            "item_code": "7",
                            "category_slug": "mda",
                            "period_type": "quarterly",
                            "contains_table": False,
                            "vector_kind": "paraphrase_context",
                            "vector_role": "plain_language_context",
                            "semantic_scope": "paraphrase",
                            "intent_tags": "ai|infrastructure",
                            "relationship_role": "",
                            "object_type": "",
                            "preview": "NVIDIA describes demand for accelerated computing infrastructure.",
                        },
                    }
                ],
                [
                    {
                        "distance": 0.89,
                        "entity": {
                            "vector_id": "NVDA_2026_10Q_SUPPLY::relationship_context",
                            "evidence_id": "NVDA_2026_10Q_SUPPLY",
                            "ticker": "NVDA",
                            "fiscal_year": 2026,
                            "form_type": "10-Q",
                            "source_tier": "primary_sec_filing",
                            "item_code": "7",
                            "category_slug": "mda",
                            "period_type": "quarterly",
                            "contains_table": False,
                            "vector_kind": "relationship_context",
                            "vector_role": "economic_linkage_context",
                            "semantic_scope": "relationship",
                            "intent_tags": "supply_chain|ai",
                            "relationship_role": "upstream_supplier",
                            "object_type": "",
                            "preview": "NVIDIA supply chain capacity and customer demand context.",
                        },
                    }
                ],
                [
                    {
                        "distance": 0.88,
                        "entity": {
                            "vector_id": "NVDA_2026_10Q_RISK::paraphrase_context::risk",
                            "evidence_id": "NVDA_2026_10Q_RISK",
                            "ticker": "NVDA",
                            "fiscal_year": 2026,
                            "form_type": "10-Q",
                            "source_tier": "primary_sec_filing",
                            "item_code": "7",
                            "category_slug": "risk_factors",
                            "period_type": "quarterly",
                            "contains_table": False,
                            "vector_kind": "paraphrase_context",
                            "vector_role": "plain_language_context",
                            "semantic_scope": "paraphrase",
                            "intent_tags": "export_control|risk",
                            "relationship_role": "",
                            "object_type": "",
                            "preview": "Export control risk could constrain AI accelerator sales.",
                        },
                    }
                ]
            ]

        def close(self) -> None:
            self.closed = True

    monkeypatch.setitem(sys.modules, "pymilvus", SimpleNamespace(MilvusClient=FakeMilvusClient))
    monkeypatch.setattr(mcp_registry, "_milvus_embedding_model", lambda model_ref, device: FakeModel())
    mcp_registry._MILVUS_CLIENT_CACHE.clear()

    result = invoke_mcp_tool(
        "sec_milvus_semantic_search",
        {
            "query": "NVIDIA AI infrastructure demand",
            "tickers": ["NVDA"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing"],
            "vector_kinds": ["paraphrase_context", "relationship_context"],
            "query_probes": [
                "NVIDIA HBM foundry supply chain",
                "NVIDIA export control risk",
            ],
            "milvus_db_path": "/tmp/fake_milvus.db",
            "milvus_collection_name": "fake_collection",
            "embedding_model": "/tmp/fake_bge_m3",
            "milvus_top_k": 5,
            "final_top_k": 2,
        },
    )

    assert result["status"] == "ok"
    assert result["row_count"] == 2
    assert result["query_probe_count"] == 3
    assert result["milvus_batch_search"]["enabled"] is True
    assert result["vector_kind_counts"] == {"paraphrase_context": 1, "relationship_context": 1}
    row = result["context_rows"][0]
    assert row["retrieval_route"] == "milvus_semantic"
    assert row["semantic_route_role"] == "semantic_recall_supplement"
    assert row["source_family"] == "primary_sec_filing"
    assert row["matched_query_indices"]
    assert row["matched_queries"]
    call = FakeMilvusClient.calls[0]
    assert call["collection_name"] == "fake_collection"
    assert len(call["data"]) == 3
    assert "ticker in [\"NVDA\"]" in call["filter"]
    assert "vector_kind in [\"paraphrase_context\", \"relationship_context\"]" in call["filter"]
