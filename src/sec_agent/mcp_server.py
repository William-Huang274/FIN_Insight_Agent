from __future__ import annotations

from typing import Any

from sec_agent.mcp_operational import McpToolProcessSupervisor
from sec_agent.mcp_tool_registry import list_registered_tools


MCP_SERVER_BUSINESS_TOOL_NAMES = {
    "sec_search_filings",
    "sec_milvus_semantic_search",
    "sec_query_exact_value_ledger",
    "market_get_snapshot",
    "industry_get_snapshot",
    "relationship_graph_lookup",
    "web_evidence_snapshot",
    "run_inspect_artifacts",
    "run_read_artifact",
}


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
    supervisor = McpToolProcessSupervisor()

    def call_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return supervisor.invoke(tool_name, arguments)

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
        timeout_s: float = 90,
    ) -> dict[str, Any]:
        """Retrieve SEC filing context through the existing agent retrieval adapter."""
        return call_tool(
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
                "timeout_s": timeout_s,
            },
        )

    @server.tool()
    def sec_milvus_semantic_search(
        query: str,
        vector_kinds: list[str],
        tickers: list[str] | None = None,
        years: list[int] | None = None,
        filing_types: list[str] | None = None,
        source_tiers: list[str] | None = None,
        metric_families: list[str] | None = None,
        period_roles: list[str] | None = None,
        typed_filter_required: bool = True,
        milvus_db_path: str = "",
        milvus_collection_name: str = "",
        embedding_model: str = "",
        milvus_top_k: int = 20,
        milvus_search_policy: dict[str, Any] | None = None,
        timeout_s: float = 45,
    ) -> dict[str, Any]:
        """Run bounded typed semantic recall when the local Milvus resources are available."""
        return call_tool(
            "sec_milvus_semantic_search",
            {
                "query": query,
                "vector_kinds": vector_kinds,
                "tickers": tickers or [],
                "years": years or [],
                "filing_types": filing_types or [],
                "source_tiers": source_tiers or [],
                "metric_families": metric_families or [],
                "period_roles": period_roles or [],
                "typed_filter_required": typed_filter_required,
                "milvus_db_path": milvus_db_path,
                "milvus_collection_name": milvus_collection_name,
                "embedding_model": embedding_model,
                "milvus_top_k": milvus_top_k,
                "milvus_search_policy": milvus_search_policy or {},
                "timeout_s": timeout_s,
            },
        )

    @server.tool()
    def sec_query_exact_value_ledger(
        ledger_store_path: str = "",
        case_id: str = "__mcp__",
        tickers: list[str] | None = None,
        years: list[int] | None = None,
        filing_types: list[str] | None = None,
        source_tiers: list[str] | None = None,
        metric_families: list[str] | None = None,
        period_roles: list[str] | None = None,
        object_ids: list[str] | None = None,
        limit: int = 5000,
        timeout_s: float = 30,
    ) -> dict[str, Any]:
        """Query the Exact-Value Ledger store."""
        return call_tool(
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
                "timeout_s": timeout_s,
            },
        )

    @server.tool()
    def market_get_snapshot(
        market_evidence_path: str = "",
        tickers: list[str] | None = None,
        snapshot_id: str = "",
        as_of_date: str = "",
        fields: list[str] | None = None,
        limit: int = 1000,
        timeout_s: float = 15,
    ) -> dict[str, Any]:
        """Read non-real-time market snapshot evidence rows."""
        return call_tool(
            "market_get_snapshot",
            {
                "market_evidence_path": market_evidence_path,
                "tickers": tickers or [],
                "snapshot_id": snapshot_id,
                "as_of_date": as_of_date,
                "fields": fields or [],
                "limit": limit,
                "timeout_s": timeout_s,
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
        timeout_s: float = 30,
    ) -> dict[str, Any]:
        """Query industry source-family evidence and observations."""
        return call_tool(
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
                "timeout_s": timeout_s,
            },
        )

    @server.tool()
    def relationship_graph_lookup(
        focus_tickers: list[str],
        search_scope_tickers: list[str] | None = None,
        allowed_universe_tickers: list[str] | None = None,
        user_query: str = "",
        relationship_graph_path: str = "",
        sector_depth_pack_path: str = "",
        max_relationships: int = 24,
        max_expanded_tickers: int = 12,
        include_sector_depth: bool = True,
        timeout_s: float = 20,
    ) -> dict[str, Any]:
        """Lookup bounded relationship graph rows and typed source gaps."""
        return call_tool(
            "relationship_graph_lookup",
            {
                "focus_tickers": focus_tickers,
                "search_scope_tickers": search_scope_tickers or [],
                "allowed_universe_tickers": allowed_universe_tickers or [],
                "user_query": user_query,
                "relationship_graph_path": relationship_graph_path,
                "sector_depth_pack_path": sector_depth_pack_path,
                "max_relationships": max_relationships,
                "max_expanded_tickers": max_expanded_tickers,
                "include_sector_depth": include_sector_depth,
                "timeout_s": timeout_s,
            },
        )

    @server.tool()
    def web_evidence_snapshot(
        url: str,
        source_class: str,
        web_scope_policy_ids: list[str],
        query: str = "",
        domain: str = "",
        claim_types: list[str] | None = None,
        snapshot_id: str = "",
        snapshot_url: str = "",
        source_title: str = "",
        company_domain_verified: bool = False,
        company_domains: list[str] | None = None,
        web_scope_allowed_domains: list[str] | None = None,
        limit: int = 1,
        timeout_s: float = 20,
    ) -> dict[str, Any]:
        """Create a bounded allowlisted web snapshot request receipt."""
        return call_tool(
            "web_evidence_snapshot",
            {
                "url": url,
                "source_class": source_class,
                "web_scope_policy_ids": web_scope_policy_ids,
                "query": query,
                "domain": domain,
                "claim_types": claim_types or [],
                "snapshot_id": snapshot_id,
                "snapshot_url": snapshot_url,
                "source_title": source_title,
                "company_domain_verified": company_domain_verified,
                "company_domains": company_domains or [],
                "web_scope_allowed_domains": web_scope_allowed_domains or [],
                "limit": limit,
                "timeout_s": timeout_s,
            },
        )

    @server.tool()
    def run_inspect_artifacts(run_dir: str, timeout_s: float = 15) -> dict[str, Any]:
        """Inspect saved run artifacts."""
        return call_tool("run_inspect_artifacts", {"run_dir": run_dir, "timeout_s": timeout_s})

    @server.tool()
    def run_read_artifact(
        run_dir: str,
        artifact_id: str = "",
        rel_path: str = "",
        max_bytes: int = 200_000,
        parse_json: bool = False,
        timeout_s: float = 15,
    ) -> dict[str, Any]:
        """Read a bounded saved run artifact."""
        return call_tool(
            "run_read_artifact",
            {
                "run_dir": run_dir,
                "artifact_id": artifact_id,
                "rel_path": rel_path,
                "max_bytes": max_bytes,
                "parse_json": parse_json,
                "timeout_s": timeout_s,
            },
        )

    return server


def run_stdio_server() -> None:
    server = create_mcp_server()
    server.run()
