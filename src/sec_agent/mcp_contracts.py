from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "sec_agent_mcp_tool_contracts_v0.1"

ROLE_RESEARCH_PLANNER = "research_planner"
ROLE_EVIDENCE_OPERATOR = "evidence_operator"
ROLE_COVERAGE_REFLECTOR = "coverage_reflector"
ROLE_VERIFIER = "verifier"
ROLE_MEMO_WRITER = "memo_writer"

SOURCE_PRIMARY_SEC = "primary_sec_filing"
SOURCE_COMPANY_AUTHORED = "company_authored_unaudited_sec_filing"
SOURCE_MARKET = "market_snapshot"
SOURCE_INDUSTRY = "industry_snapshot"
SOURCE_RUN_ARTIFACT = "run_artifact"
SOURCE_RELATIONSHIP = "relationship_graph"


def list_mcp_tool_contracts() -> list[dict[str, Any]]:
    """Return stable MCP-facing tool contracts for agent orchestration."""
    return deepcopy(_TOOL_CONTRACTS)


def get_mcp_tool_contract(name: str) -> dict[str, Any]:
    for contract in _TOOL_CONTRACTS:
        if contract["name"] == name:
            return deepcopy(contract)
    raise KeyError(f"unknown MCP tool contract: {name}")


def export_mcp_tool_contracts(path: str | Path | None = None) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "contract_boundary": (
            "These are MCP-facing tool contracts. They standardize inputs, outputs, "
            "source boundaries, and handler ownership, but do not expose secrets or private data."
        ),
        "tools": list_mcp_tool_contracts(),
    }
    validate_mcp_tool_contracts(payload["tools"])
    if path is not None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def validate_mcp_tool_contracts(contracts: list[dict[str, Any]] | None = None) -> None:
    seen: set[str] = set()
    for contract in contracts or _TOOL_CONTRACTS:
        name = str(contract.get("name") or "")
        if not name:
            raise ValueError("tool contract missing name")
        if name in seen:
            raise ValueError(f"duplicate MCP tool contract: {name}")
        seen.add(name)
        if not _is_safe_tool_name(name):
            raise ValueError(f"unsafe MCP tool name: {name}")
        for field in ("description", "input_schema", "output_schema", "source_boundaries", "handler"):
            if field not in contract:
                raise ValueError(f"{name} missing {field}")
        if contract["input_schema"].get("type") != "object":
            raise ValueError(f"{name} input_schema must be an object schema")
        if contract["output_schema"].get("type") != "object":
            raise ValueError(f"{name} output_schema must be an object schema")
        boundaries = contract.get("source_boundaries") or {}
        if not isinstance(boundaries.get("allowed_claim_types"), list):
            raise ValueError(f"{name} source_boundaries.allowed_claim_types must be a list")
        if not isinstance(boundaries.get("prohibited_claims"), list):
            raise ValueError(f"{name} source_boundaries.prohibited_claims must be a list")


def _is_safe_tool_name(name: str) -> bool:
    return bool(name) and all(ch.islower() or ch.isdigit() or ch == "_" for ch in name)


def _tool(
    *,
    name: str,
    namespace: str,
    title: str,
    description: str,
    roles: list[str],
    source_tiers: list[str],
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
    allowed_claim_types: list[str],
    prohibited_claims: list[str],
    handler_module: str,
    handler_name: str,
    status: str = "contract",
) -> dict[str, Any]:
    return {
        "name": name,
        "namespace": namespace,
        "title": title,
        "description": description,
        "status": status,
        "agent_roles": roles,
        "source_tiers": source_tiers,
        "input_schema": input_schema,
        "output_schema": output_schema,
        "source_boundaries": {
            "allowed_claim_types": allowed_claim_types,
            "prohibited_claims": prohibited_claims,
        },
        "handler": {
            "module": handler_module,
            "name": handler_name,
        },
    }


def _object_schema(
    properties: dict[str, Any],
    *,
    required: list[str] | None = None,
    additional_properties: bool = False,
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": additional_properties,
    }


def _array(items: dict[str, Any], description: str = "") -> dict[str, Any]:
    schema = {"type": "array", "items": items}
    if description:
        schema["description"] = description
    return schema


def _string_enum(values: list[str], description: str = "") -> dict[str, Any]:
    schema = {"type": "string", "enum": values}
    if description:
        schema["description"] = description
    return schema


def _artifact_ref_schema() -> dict[str, Any]:
    return _object_schema(
        {
            "artifact_id": {"type": "string"},
            "path": {"type": "string"},
            "digest": {"type": "string"},
            "row_count": {"type": "integer"},
        },
        additional_properties=False,
    )


_COMMON_SCOPE_PROPERTIES = {
    "tickers": _array({"type": "string"}, "Uppercase ticker symbols."),
    "years": _array({"type": "integer"}, "Fiscal years to query."),
    "filing_types": _array({"type": "string", "enum": ["10-K", "10-Q", "8-K", "20-F", "40-F", "6-K"]}),
    "source_tiers": _array(
        {
            "type": "string",
            "enum": [SOURCE_PRIMARY_SEC, SOURCE_COMPANY_AUTHORED, SOURCE_MARKET, SOURCE_INDUSTRY],
        }
    ),
    "evidence_requirement_id": {"type": "string"},
}


_TOOL_CONTRACTS: list[dict[str, Any]] = [
    _tool(
        name="sec_search_filings",
        namespace="sec",
        title="Search SEC filing evidence",
        description=(
            "Retrieve SEC filing text and structured object evidence within an explicit "
            "ticker/year/form/source scope. Text routes may use BM25/ObjectBM25/BGE, "
            "but financial facts remain downstream ledger-grounded."
        ),
        roles=[ROLE_EVIDENCE_OPERATOR],
        source_tiers=[SOURCE_PRIMARY_SEC, SOURCE_COMPANY_AUTHORED],
        input_schema=_object_schema(
            {
                "query": {"type": "string"},
                **_COMMON_SCOPE_PROPERTIES,
                "source_tiers": _array(
                    {
                        "type": "string",
                        "enum": [SOURCE_PRIMARY_SEC, SOURCE_COMPANY_AUTHORED],
                    }
                ),
                "sections": _array({"type": "string"}),
                "metric_families": _array({"type": "string"}),
                "period_roles": _array({"type": "string", "enum": ["ANNUAL", "QTD", "YTD", "TTM", "INSTANT"]}),
                "retrieval_route": _string_enum(["filing_text", "8k_commentary", "risk_text"], "Physical retrieval route."),
                "candidate_budget": {"type": "integer", "minimum": 1, "maximum": 2000},
                "rerank_budget": {"type": "integer", "minimum": 0, "maximum": 500},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            },
            required=["query"],
        ),
        output_schema=_object_schema(
            {
                "status": {"type": "string", "enum": ["ok", "partial", "error"]},
                "context_rows": _array({"type": "object"}),
                "row_count": {"type": "integer"},
                "query_contract": {"type": "object"},
                "selected_tickers": _array({"type": "string"}),
                "selected_years": _array({"type": "integer"}),
                "retrieval_trace": {"type": "object"},
                "context_runtime": {"type": "object"},
                "candidate_counts": {"type": "object"},
                "artifact_refs": _array(_artifact_ref_schema()),
                "source_gaps": _array({"type": "object"}),
            }
        ),
        allowed_claim_types=[
            "company_disclosed_business_description",
            "company_disclosed_management_discussion",
            "company_authored_unaudited_commentary",
            "risk_factor",
        ],
        prohibited_claims=[
            "Do not use filing text as a source for exact financial values when ledger rows are available.",
            "Do not treat 8-K earnings release text as audited 10-K/10-Q facts.",
        ],
        handler_module="scripts.cloud.sec_agent_interactive",
        handler_name="retrieve_context_for_graph",
    ),
    _tool(
        name="sec_milvus_semantic_search",
        namespace="sec",
        title="Search Milvus typed semantic evidence",
        description=(
            "Run typed semantic recall over a Milvus collection built from SEC evidence vectors. "
            "This is a recall supplement for bounded filing evidence, not an exact-value authority."
        ),
        roles=[ROLE_EVIDENCE_OPERATOR],
        source_tiers=[SOURCE_PRIMARY_SEC, SOURCE_COMPANY_AUTHORED],
        input_schema=_object_schema(
            {
                "query": {"type": "string"},
                **_COMMON_SCOPE_PROPERTIES,
                "source_tiers": _array(
                    {
                        "type": "string",
                        "enum": [SOURCE_PRIMARY_SEC, SOURCE_COMPANY_AUTHORED],
                    }
                ),
                "metric_families": _array({"type": "string"}),
                "period_roles": _array({"type": "string", "enum": ["ANNUAL", "QTD", "YTD", "TTM", "INSTANT"]}),
                "vector_kinds": _array(
                    {
                        "type": "string",
                        "enum": [
                            "narrative_chunk",
                            "table_chunk",
                            "metric_row",
                            "table_row",
                            "claim_row",
                            "relationship_context",
                            "paraphrase_context",
                        ],
                    }
                ),
                "typed_filter_required": {"type": "boolean"},
                "milvus_db_path": {"type": "string"},
                "milvus_collection_name": {"type": "string"},
                "embedding_model": {"type": "string"},
                "milvus_top_k": {"type": "integer", "minimum": 1, "maximum": 200},
                "milvus_search_policy": {"type": "object"},
            },
            required=["query", "vector_kinds"],
            additional_properties=True,
        ),
        output_schema=_object_schema(
            {
                "status": {"type": "string", "enum": ["ok", "partial", "error", "dry_run"]},
                "context_rows": _array({"type": "object"}),
                "row_count": {"type": "integer"},
                "vector_kind_counts": {"type": "object"},
                "collection_name": {"type": "string"},
                "typed_filter_required": {"type": "boolean"},
                "semantic_route_role": {"type": "string"},
                "artifact_refs": _array(_artifact_ref_schema()),
                "source_gaps": _array({"type": "object"}),
            }
        ),
        allowed_claim_types=[
            "company_disclosed_business_description",
            "company_disclosed_management_discussion",
            "risk_factor",
            "semantic_recall_context",
        ],
        prohibited_claims=[
            "Do not use Milvus semantic hits as exact financial values.",
            "Do not run Milvus semantic search without a typed vector_kind filter.",
            "Do not treat semantic recall as a source family outside bounded SEC evidence.",
        ],
        handler_module="sec_agent.mcp_tool_registry",
        handler_name="_invoke_milvus_semantic",
    ),
    _tool(
        name="sec_query_exact_value_ledger",
        namespace="sec",
        title="Query Exact-Value Ledger",
        description=(
            "Query normalized reported financial facts by ticker, fiscal year, filing type, "
            "metric family, period role, and source tier. This is the authority for exact values."
        ),
        roles=[ROLE_EVIDENCE_OPERATOR, ROLE_VERIFIER],
        source_tiers=[SOURCE_PRIMARY_SEC],
        input_schema=_object_schema(
            {
                **_COMMON_SCOPE_PROPERTIES,
                "metric_families": _array({"type": "string"}),
                "period_roles": _array({"type": "string", "enum": ["ANNUAL", "QTD", "YTD", "TTM", "INSTANT"]}),
                "object_ids": _array({"type": "string"}),
                "ledger_store_path": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10000},
            }
        ),
        output_schema=_object_schema(
            {
                "status": {"type": "string", "enum": ["ok", "partial", "error"]},
                "ledger_rows": _array({"type": "object"}),
                "row_count": {"type": "integer"},
                "missing_dimensions": _array({"type": "object"}),
                "artifact_refs": _array(_artifact_ref_schema()),
            }
        ),
        allowed_claim_types=[
            "reported_financial_fact",
            "period_role_comparison",
            "metric_family_comparison",
        ],
        prohibited_claims=[
            "Do not infer missing values from adjacent table text or model memory.",
            "Do not compare ANNUAL, QTD, YTD, TTM, and INSTANT values without explicit period_role handling.",
        ],
        handler_module="sec_agent.ledger_store",
        handler_name="query_ledger_facts",
    ),
    _tool(
        name="market_get_snapshot",
        namespace="market",
        title="Get market snapshot evidence",
        description=(
            "Fetch non-real-time market snapshot evidence such as price, return, relative return, "
            "drawdown, valuation fields, and event-window analytics."
        ),
        roles=[ROLE_EVIDENCE_OPERATOR, ROLE_COVERAGE_REFLECTOR],
        source_tiers=[SOURCE_MARKET],
        input_schema=_object_schema(
            {
                "tickers": _array({"type": "string"}),
                "snapshot_id": {"type": "string"},
                "as_of_date": {"type": "string"},
                "window": {"type": "string", "enum": ["3M", "6M", "YTD", "1Y"]},
                "fields": _array({"type": "string"}),
                "analysis_tools": _array({"type": "string"}),
                "market_evidence_path": {"type": "string"},
                "market_catalog_path": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
            },
            required=["tickers"],
        ),
        output_schema=_object_schema(
            {
                "status": {"type": "string", "enum": ["ok", "partial", "error"]},
                "market_rows": _array({"type": "object"}),
                "snapshot_id": {"type": "string"},
                "as_of_date": {"type": "string"},
                "field_gaps": _array({"type": "object"}),
                "artifact_refs": _array(_artifact_ref_schema()),
            }
        ),
        allowed_claim_types=[
            "non_real_time_market_reaction",
            "relative_return_context",
            "valuation_context",
            "event_window_context",
        ],
        prohibited_claims=[
            "Do not present market_snapshot values as real-time market data.",
            "Do not use market_snapshot values to overwrite SEC reported financial facts.",
            "Do not infer unavailable valuation fields from model memory.",
        ],
        handler_module="scripts.cloud.sec_agent_interactive",
        handler_name="attach_market_snapshot_for_graph",
    ),
    _tool(
        name="industry_get_snapshot",
        namespace="industry",
        title="Get industry snapshot evidence",
        description=(
            "Fetch industry source-family evidence and observations for macro, sector, commodity, "
            "housing, healthcare, energy, utility, or regulatory context."
        ),
        roles=[ROLE_EVIDENCE_OPERATOR, ROLE_COVERAGE_REFLECTOR],
        source_tiers=[SOURCE_INDUSTRY],
        input_schema=_object_schema(
            {
                "source_families": _array({"type": "string"}),
                "providers": _array({"type": "string"}),
                "datasets": _array({"type": "string"}),
                "facets": {"type": "object"},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "latest_only": {"type": "boolean"},
                "industry_evidence_path": {"type": "string"},
                "industry_snapshot_db_path": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10000},
            },
            required=["source_families"],
            additional_properties=True,
        ),
        output_schema=_object_schema(
            {
                "status": {"type": "string", "enum": ["ok", "partial", "error"]},
                "industry_rows": _array({"type": "object"}),
                "observations": _array({"type": "object"}),
                "source_family_gaps": _array({"type": "object"}),
                "artifact_refs": _array(_artifact_ref_schema()),
            }
        ),
        allowed_claim_types=[
            "industry_context",
            "macro_context",
            "commodity_context",
            "power_demand_context",
            "regulatory_context",
        ],
        prohibited_claims=[
            "Do not use industry_snapshot observations as company-reported revenue, margin, cash flow, or guidance.",
            "Do not treat industry_snapshot observations as real-time prices, news, or analyst estimates.",
        ],
        handler_module="sec_agent.industry_snapshot",
        handler_name="query_industry_snapshot",
    ),
    _tool(
        name="relationship_graph_lookup",
        namespace="relationship",
        title="Lookup relationship graph scope evidence",
        description=(
            "Lookup bounded company relationship graph and sector-depth metadata rows for "
            "peer, customer, supplier, sector, and macro-sensitive research-scope expansion. "
            "The output supports hypotheses and evidence requirements only."
        ),
        roles=[ROLE_RESEARCH_PLANNER],
        source_tiers=[SOURCE_RELATIONSHIP],
        input_schema=_object_schema(
            {
                "focus_tickers": _array({"type": "string"}),
                "search_scope_tickers": _array({"type": "string"}),
                "user_query": {"type": "string"},
                "relationship_graph_path": {"type": "string"},
                "sector_depth_pack_path": {"type": "string"},
                "max_relationships": {"type": "integer", "minimum": 1, "maximum": 100},
                "max_expanded_tickers": {"type": "integer", "minimum": 1, "maximum": 50},
                "include_sector_depth": {"type": "boolean"},
            },
            required=["focus_tickers"],
        ),
        output_schema=_object_schema(
            {
                "status": {"type": "string", "enum": ["ok", "partial", "error"]},
                "relationships": _array({"type": "object"}),
                "relationship_rows": _array({"type": "object"}),
                "focus_tickers": _array({"type": "string"}),
                "expanded_tickers": _array({"type": "string"}),
                "included_tickers": _array({"type": "string"}),
                "source_gaps": _array({"type": "object"}),
                "summary": {"type": "object"},
                "artifact_refs": _array(_artifact_ref_schema()),
            }
        ),
        allowed_claim_types=[
            "research_scope_hypothesis",
            "peer_relationship_hypothesis",
            "customer_supplier_hypothesis",
            "sector_readthrough_hypothesis",
        ],
        prohibited_claims=[
            "Do not use relationship graph rows as reported revenue, margin, cash flow, capex, or balance-sheet facts.",
            "Do not expand to unbounded full-market scope without relationship evidence and budget guard.",
        ],
        handler_module="sec_agent.relationship_graph",
        handler_name="query_relationship_graph",
    ),
    _tool(
        name="run_inspect_artifacts",
        namespace="run_artifact",
        title="Inspect run artifacts",
        description=(
            "Inspect a saved agent run directory and summarize graph state, query contract, "
            "coverage matrix, ledger, judgment plan, gates, checkpoints, rendered answer, "
            "and performance telemetry."
        ),
        roles=[ROLE_COVERAGE_REFLECTOR, ROLE_VERIFIER],
        source_tiers=[SOURCE_RUN_ARTIFACT],
        input_schema=_object_schema(
            {
                "run_dir": {"type": "string"},
                "artifact_ids": _array({"type": "string"}),
                "include_preview": {"type": "boolean"},
            },
            required=["run_dir"],
        ),
        output_schema=_object_schema(
            {
                "status": {"type": "string", "enum": ["pass", "warn", "fail"]},
                "run_dir": {"type": "string"},
                "artifacts": _array({"type": "object"}),
                "missing_required": _array({"type": "string"}),
                "state_summary": {"type": "object"},
                "gate_summary": {"type": "object"},
                "performance_summary": {"type": "object"},
            }
        ),
        allowed_claim_types=[
            "run_state",
            "artifact_completeness",
            "gate_status",
            "performance_observation",
        ],
        prohibited_claims=[
            "Do not infer investment conclusions from run metadata alone.",
            "Do not expose private paths or secret-containing artifact content to untrusted clients.",
        ],
        handler_module="sec_agent.workbench.artifacts",
        handler_name="inspect_run_artifacts",
    ),
    _tool(
        name="run_read_artifact",
        namespace="run_artifact",
        title="Read bounded run artifact",
        description=(
            "Read a bounded saved artifact by id or relative path. Intended for audit, resume, "
            "and UI inspection, not for bypassing source-tier gates."
        ),
        roles=[ROLE_COVERAGE_REFLECTOR, ROLE_VERIFIER, ROLE_MEMO_WRITER],
        source_tiers=[SOURCE_RUN_ARTIFACT],
        input_schema=_object_schema(
            {
                "run_dir": {"type": "string"},
                "artifact_id": {"type": "string"},
                "rel_path": {"type": "string"},
                "max_bytes": {"type": "integer", "minimum": 1, "maximum": 2000000},
                "parse_json": {"type": "boolean"},
            },
            required=["run_dir"],
        ),
        output_schema=_object_schema(
            {
                "status": {"type": "string", "enum": ["ok", "truncated", "error"]},
                "artifact_id": {"type": "string"},
                "rel_path": {"type": "string"},
                "digest": {"type": "string"},
                "content": {"type": "string"},
                "json": {"type": "object"},
                "truncated": {"type": "boolean"},
            }
        ),
        allowed_claim_types=[
            "artifact_content",
            "resume_boundary",
            "debug_observation",
        ],
        prohibited_claims=[
            "Do not treat artifact text as a new source tier unless it is mapped back to its source artifact.",
            "Do not return unbounded large artifacts through MCP.",
        ],
        handler_module="sec_agent.mcp_runtime",
        handler_name="read_bounded_artifact",
    ),
]
