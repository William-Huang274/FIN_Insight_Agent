from __future__ import annotations

from typing import Any

from sec_agent.mcp_tool_registry import invoke_mcp_tool, list_registered_tools


def create_mcp_server() -> Any:
    """Create a FastMCP server when the optional MCP SDK is installed."""
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on optional runtime package
        raise RuntimeError(
            "The optional 'mcp' package is not installed. Install project requirements "
            "with MCP support before running the stdio server."
        ) from exc

    server = FastMCP("finsight-agent")

    @server.tool()
    def list_sec_agent_tools() -> dict[str, Any]:
        """List FinSight-Agent MCP-facing tool contracts."""
        return {"status": "ok", "tools": list_registered_tools()}

    @server.tool()
    def sec_search_filings(
        query: str,
        tickers: list[str] | None = None,
        years: list[int] | None = None,
        filing_types: list[str] | None = None,
        source_tiers: list[str] | None = None,
        metric_families: list[str] | None = None,
        period_roles: list[str] | None = None,
        retrieval_route: str = "",
        manifest_path: str = "",
        bm25_index_dir: str = "",
        object_bm25_index_dir: str = "",
        ledger_store_path: str = "",
        output_dir: str = "",
        query_planner: str = "heuristic",
        candidate_budget: int = 0,
        rerank_budget: int = 0,
        limit: int = 120,
    ) -> dict[str, Any]:
        """Retrieve SEC filing context through the existing agent retrieval adapter."""
        return invoke_mcp_tool(
            "sec_search_filings",
            {
                "query": query,
                "tickers": tickers or [],
                "years": years or [],
                "filing_types": filing_types or [],
                "source_tiers": source_tiers or [],
                "metric_families": metric_families or [],
                "period_roles": period_roles or [],
                "retrieval_route": retrieval_route,
                "manifest_path": manifest_path,
                "bm25_index_dir": bm25_index_dir,
                "object_bm25_index_dir": object_bm25_index_dir,
                "ledger_store_path": ledger_store_path,
                "output_dir": output_dir,
                "query_planner": query_planner,
                "candidate_budget": candidate_budget,
                "rerank_budget": rerank_budget,
                "limit": limit,
            },
        )

    @server.tool()
    def sec_query_exact_value_ledger(
        ledger_store_path: str,
        case_id: str = "__mcp__",
        tickers: list[str] | None = None,
        years: list[int] | None = None,
        filing_types: list[str] | None = None,
        source_tiers: list[str] | None = None,
        metric_families: list[str] | None = None,
        period_roles: list[str] | None = None,
        object_ids: list[str] | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        """Query the Exact-Value Ledger store."""
        return invoke_mcp_tool(
            "sec_query_exact_value_ledger",
            {
                "ledger_store_path": ledger_store_path,
                "case_id": case_id,
                "tickers": tickers or [],
                "years": years or [],
                "filing_types": filing_types or [],
                "source_tiers": source_tiers or [],
                "metric_families": metric_families or [],
                "period_roles": period_roles or [],
                "object_ids": object_ids or [],
                "limit": limit,
            },
        )

    @server.tool()
    def market_get_snapshot(
        market_evidence_path: str,
        tickers: list[str] | None = None,
        snapshot_id: str = "",
        as_of_date: str = "",
        fields: list[str] | None = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        """Read non-real-time market snapshot evidence rows."""
        return invoke_mcp_tool(
            "market_get_snapshot",
            {
                "market_evidence_path": market_evidence_path,
                "tickers": tickers or [],
                "snapshot_id": snapshot_id,
                "as_of_date": as_of_date,
                "fields": fields or [],
                "limit": limit,
            },
        )

    @server.tool()
    def industry_get_snapshot(
        industry_snapshot_db_path: str = "",
        industry_evidence_path: str = "",
        source_families: list[str] | None = None,
        providers: list[str] | None = None,
        datasets: list[str] | None = None,
        series_ids: list[str] | None = None,
        facets: dict[str, Any] | None = None,
        start_date: str = "",
        end_date: str = "",
        latest_only: bool = False,
        limit: int = 500,
    ) -> dict[str, Any]:
        """Query industry source-family evidence and observations."""
        return invoke_mcp_tool(
            "industry_get_snapshot",
            {
                "industry_snapshot_db_path": industry_snapshot_db_path,
                "industry_evidence_path": industry_evidence_path,
                "source_families": source_families or [],
                "providers": providers or [],
                "datasets": datasets or [],
                "series_ids": series_ids or [],
                "facets": facets or {},
                "start_date": start_date,
                "end_date": end_date,
                "latest_only": latest_only,
                "limit": limit,
            },
        )

    @server.tool()
    def run_inspect_artifacts(run_dir: str) -> dict[str, Any]:
        """Inspect saved run artifacts."""
        return invoke_mcp_tool("run_inspect_artifacts", {"run_dir": run_dir})

    @server.tool()
    def run_read_artifact(
        run_dir: str,
        artifact_id: str = "",
        rel_path: str = "",
        max_bytes: int = 200_000,
        parse_json: bool = False,
    ) -> dict[str, Any]:
        """Read a bounded saved run artifact."""
        return invoke_mcp_tool(
            "run_read_artifact",
            {
                "run_dir": run_dir,
                "artifact_id": artifact_id,
                "rel_path": rel_path,
                "max_bytes": max_bytes,
                "parse_json": parse_json,
            },
        )

    return server


def run_stdio_server() -> None:
    server = create_mcp_server()
    server.run()
