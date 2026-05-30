from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import duckdb

from sec_agent.industry_snapshot import query_industry_snapshot
from sec_agent.mcp_tool_registry import invoke_mcp_tool, list_registered_tools


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
