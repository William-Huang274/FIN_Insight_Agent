from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from sec_agent.agent_contracts import MODEL_PROFILES, OPERATOR_TOOL_ALLOWLIST, RETRIEVAL_TOOL_NAMES
from sec_agent.mcp_contracts import list_mcp_tool_contracts
from sec_agent.research_skills import SKILL_FILES


SCHEMA_VERSION = "sec_agent_agent_registry_v0.1"

TOOL_PERMISSIONS = {
    "none",
    "inspect_only",
    "request_only",
    "bounded_execute",
    "orchestrate_subgraph",
}

DATA_VIEWS = {
    "summary_only",
    "artifact_ref",
    "bounded_rows",
    "database_query",
    "source_inventory",
    "relationship_graph_summary",
    "relationship_summary",
    "verified_summary",
    "coverage_summary",
    "tool_trace_summary",
}

ROUTE_AUTHORITIES = {
    "none",
    "suggest_business_need",
    "compile_physical_route",
    "adjust_budget",
    "execute_route",
}

SOURCE_FAMILIES = {
    "primary_sec_filing",
    "company_authored_unaudited_sec_filing",
    "market_snapshot",
    "industry_snapshot",
    "run_artifact",
    "relationship_graph",
}

EVIDENCE_OPERATOR_IDS = set(OPERATOR_TOOL_ALLOWLIST)


def list_agent_registry() -> list[dict[str, Any]]:
    return deepcopy(_AGENT_REGISTRY)


def agent_registry_by_id() -> dict[str, dict[str, Any]]:
    return {entry["agent_id"]: entry for entry in list_agent_registry()}


def get_agent_contract(agent_id: str) -> dict[str, Any]:
    for entry in _AGENT_REGISTRY:
        if entry["agent_id"] == agent_id:
            return deepcopy(entry)
    raise KeyError(f"unknown agent contract: {agent_id}")


def known_agent_ids() -> set[str]:
    return {entry["agent_id"] for entry in _AGENT_REGISTRY}


def allowed_source_families() -> set[str]:
    families: set[str] = set()
    for entry in _AGENT_REGISTRY:
        families.update(str(item) for item in entry.get("source_families") or [])
    return families


def export_agent_registry(path: str | Path | None = None) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "contract_boundary": (
            "These are static multi-agent orchestration contracts. They define "
            "agent permissions, data views, route authority, model profiles, and skill ids; "
            "they do not contain credentials or private data paths."
        ),
        "agents": list_agent_registry(),
    }
    validate_agent_registry(payload["agents"])
    if path is not None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def validate_agent_registry(entries: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    registry = list(entries or _AGENT_REGISTRY)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen: set[str] = set()
    mcp_tool_names = {contract["name"] for contract in list_mcp_tool_contracts()}

    for entry in registry:
        agent_id = str(entry.get("agent_id") or "").strip()
        if not agent_id:
            errors.append({"type": "agent_id_required"})
            continue
        if agent_id in seen:
            errors.append({"type": "duplicate_agent_id", "agent_id": agent_id})
        seen.add(agent_id)
        if not _is_safe_id(agent_id):
            errors.append({"type": "unsafe_agent_id", "agent_id": agent_id})
        _validate_required_fields(entry, agent_id, errors)
        _validate_enum_field(entry, agent_id, "tool_permission", TOOL_PERMISSIONS, errors)
        _validate_enum_field(entry, agent_id, "route_authority", ROUTE_AUTHORITIES, errors)
        _validate_enum_field(entry, agent_id, "model_profile", MODEL_PROFILES, errors)
        _validate_allowed_tools(entry, agent_id, mcp_tool_names, errors)
        _validate_future_tools(entry, agent_id, errors)
        _validate_data_views(entry, agent_id, errors)
        _validate_source_families(entry, agent_id, errors)
        _validate_max_tool_calls(entry, agent_id, errors)
        _validate_skill_ids(entry, agent_id, errors)
        _validate_hard_permission_rules(entry, agent_id, errors)
        _validate_non_private_contract(entry, agent_id, warnings)

    return {
        "status": "fail" if errors else "pass",
        "schema_version": SCHEMA_VERSION,
        "agent_count": len(registry),
        "errors": errors,
        "warnings": warnings,
    }


def _agent(
    *,
    agent_id: str,
    role: str,
    description: str,
    tool_permission: str,
    allowed_tools: list[str],
    allowed_data_views: list[str],
    route_authority: str,
    model_profile: str,
    max_tool_calls: int,
    skill_ids: list[str],
    input_schema: str,
    output_schema: str,
    source_families: list[str],
    future_tools: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "agent_id": agent_id,
        "role": role,
        "description": description,
        "tool_permission": tool_permission,
        "allowed_tools": allowed_tools,
        "allowed_data_views": allowed_data_views,
        "route_authority": route_authority,
        "model_profile": model_profile,
        "max_tool_calls": max_tool_calls,
        "skill_ids": skill_ids,
        "input_schema": input_schema,
        "output_schema": output_schema,
        "source_families": source_families,
        "future_tools": future_tools or [],
    }


def _validate_required_fields(entry: Mapping[str, Any], agent_id: str, errors: list[dict[str, Any]]) -> None:
    for field in (
        "role",
        "description",
        "tool_permission",
        "allowed_tools",
        "allowed_data_views",
        "route_authority",
        "model_profile",
        "max_tool_calls",
        "skill_ids",
        "input_schema",
        "output_schema",
        "source_families",
    ):
        if field not in entry:
            errors.append({"type": "required_field_missing", "agent_id": agent_id, "field": field})


def _validate_enum_field(
    entry: Mapping[str, Any],
    agent_id: str,
    field: str,
    allowed: set[str],
    errors: list[dict[str, Any]],
) -> None:
    value = str(entry.get(field) or "").strip()
    if value not in allowed:
        errors.append({"type": f"invalid_{field}", "agent_id": agent_id, "value": value})


def _validate_allowed_tools(
    entry: Mapping[str, Any],
    agent_id: str,
    mcp_tool_names: set[str],
    errors: list[dict[str, Any]],
) -> None:
    tools = _string_list(entry.get("allowed_tools"))
    invalid = [tool for tool in tools if tool not in mcp_tool_names]
    if invalid:
        errors.append({"type": "unknown_allowed_tool", "agent_id": agent_id, "tools": sorted(invalid)})
    if str(entry.get("tool_permission") or "") == "none" and tools:
        errors.append({"type": "none_permission_agent_has_tools", "agent_id": agent_id, "tools": sorted(tools)})


def _validate_future_tools(entry: Mapping[str, Any], agent_id: str, errors: list[dict[str, Any]]) -> None:
    for tool in entry.get("future_tools") or []:
        if not isinstance(tool, Mapping):
            errors.append({"type": "invalid_future_tool", "agent_id": agent_id})
            continue
        name = str(tool.get("name") or "").strip()
        status = str(tool.get("status") or "").strip()
        if not _is_safe_id(name):
            errors.append({"type": "unsafe_future_tool_name", "agent_id": agent_id, "tool": name})
        if status not in {"future", "disabled"}:
            errors.append({"type": "invalid_future_tool_status", "agent_id": agent_id, "tool": name, "status": status})


def _validate_data_views(entry: Mapping[str, Any], agent_id: str, errors: list[dict[str, Any]]) -> None:
    data_views = set(_string_list(entry.get("allowed_data_views")))
    invalid = sorted(data_views - DATA_VIEWS)
    if invalid:
        errors.append({"type": "invalid_data_view", "agent_id": agent_id, "data_views": invalid})
    if "raw_source_read" in data_views:
        errors.append({"type": "raw_source_read_forbidden", "agent_id": agent_id})


def _validate_source_families(entry: Mapping[str, Any], agent_id: str, errors: list[dict[str, Any]]) -> None:
    source_families = set(_string_list(entry.get("source_families")))
    invalid = sorted(source_families - SOURCE_FAMILIES)
    if invalid:
        errors.append({"type": "invalid_source_family", "agent_id": agent_id, "source_families": invalid})


def _validate_max_tool_calls(entry: Mapping[str, Any], agent_id: str, errors: list[dict[str, Any]]) -> None:
    try:
        value = int(entry.get("max_tool_calls"))
    except (TypeError, ValueError):
        errors.append({"type": "invalid_max_tool_calls", "agent_id": agent_id, "value": entry.get("max_tool_calls")})
        return
    if value < 0:
        errors.append({"type": "negative_max_tool_calls", "agent_id": agent_id, "value": value})


def _validate_skill_ids(entry: Mapping[str, Any], agent_id: str, errors: list[dict[str, Any]]) -> None:
    skill_ids = _string_list(entry.get("skill_ids"))
    if not skill_ids:
        errors.append({"type": "skill_ids_required", "agent_id": agent_id})
        return
    invalid = [skill_id for skill_id in skill_ids if not _is_safe_id(skill_id)]
    if invalid:
        errors.append({"type": "unsafe_skill_id", "agent_id": agent_id, "skill_ids": sorted(invalid)})
    unknown = [skill_id for skill_id in skill_ids if skill_id not in SKILL_FILES]
    if unknown:
        errors.append({"type": "unknown_skill_id", "agent_id": agent_id, "skill_ids": sorted(unknown)})


def _validate_hard_permission_rules(entry: Mapping[str, Any], agent_id: str, errors: list[dict[str, Any]]) -> None:
    tools = set(_string_list(entry.get("allowed_tools")))
    tool_permission = str(entry.get("tool_permission") or "").strip()
    route_authority = str(entry.get("route_authority") or "").strip()
    data_views = set(_string_list(entry.get("allowed_data_views")))

    if agent_id == "memo_writer" and tools:
        errors.append({"type": "memo_writer_tools_forbidden", "tools": sorted(tools)})
    if agent_id == "renderer" and tools:
        errors.append({"type": "renderer_tools_forbidden", "tools": sorted(tools)})
    if agent_id == "verifier":
        if tool_permission != "inspect_only":
            errors.append({"type": "verifier_must_be_inspect_only", "tool_permission": tool_permission})
        retrieval_tools = sorted(tools & RETRIEVAL_TOOL_NAMES)
        if retrieval_tools:
            errors.append({"type": "verifier_retrieval_tools_forbidden", "tools": retrieval_tools})
    if agent_id == "research_lead":
        if tool_permission != "request_only":
            errors.append({"type": "research_lead_must_be_request_only", "tool_permission": tool_permission})
        retrieval_tools = sorted(tools & RETRIEVAL_TOOL_NAMES)
        if retrieval_tools:
            errors.append({"type": "research_lead_retrieval_tools_forbidden", "tools": retrieval_tools})
    if route_authority == "execute_route" and agent_id not in EVIDENCE_OPERATOR_IDS:
        errors.append({"type": "execute_route_reserved_for_operator", "agent_id": agent_id})
    operator_tools = OPERATOR_TOOL_ALLOWLIST.get(agent_id)
    if operator_tools is not None:
        invalid = sorted(tools - operator_tools)
        if invalid:
            errors.append({"type": "operator_tool_not_allowed", "agent_id": agent_id, "tools": invalid})
        if route_authority != "execute_route":
            errors.append({"type": "operator_must_execute_route", "agent_id": agent_id, "route_authority": route_authority})
        if tool_permission != "bounded_execute":
            errors.append({"type": "operator_must_be_bounded_execute", "agent_id": agent_id, "tool_permission": tool_permission})
    if "raw_source_read" in data_views:
        errors.append({"type": "raw_source_read_forbidden", "agent_id": agent_id})


def _validate_non_private_contract(entry: Mapping[str, Any], agent_id: str, warnings: list[dict[str, Any]]) -> None:
    text = json.dumps(entry, ensure_ascii=False)
    for marker in ("data/raw_private", "data/processed_private", "data/indexes", ".env", "BEGIN PRIVATE KEY"):
        if marker in text:
            warnings.append({"type": "private_path_or_secret_marker", "agent_id": agent_id, "marker": marker})


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _is_safe_id(value: str) -> bool:
    return bool(value) and all(ch.islower() or ch.isdigit() or ch == "_" for ch in value)


_AGENT_REGISTRY: list[dict[str, Any]] = [
    _agent(
        agent_id="research_lead",
        role="Research Lead Agent",
        description="Classifies investment intent, scopes the task, and emits an activation plan and business evidence needs.",
        tool_permission="request_only",
        allowed_tools=["run_inspect_artifacts"],
        allowed_data_views=["summary_only", "source_inventory", "artifact_ref"],
        route_authority="suggest_business_need",
        model_profile="balanced",
        max_tool_calls=0,
        skill_ids=["shared_evidence_boundary", "research_lead_planning"],
        input_schema="ResearchLeadInputV0",
        output_schema="AgentActivationPlanV0",
        source_families=["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot", "industry_snapshot", "run_artifact"],
    ),
    _agent(
        agent_id="universe_relationship",
        role="Universe / Relationship Agent",
        description="Expands peer, supply-chain, customer, supplier, and sector relationship scope for research requirements.",
        tool_permission="request_only",
        allowed_tools=["relationship_graph_lookup"],
        allowed_data_views=["summary_only", "source_inventory", "relationship_graph_summary"],
        route_authority="suggest_business_need",
        model_profile="balanced",
        max_tool_calls=1,
        skill_ids=["shared_evidence_boundary", "relationship_universe"],
        input_schema="UniverseRelationshipInputV0",
        output_schema="UniverseRelationshipPlanV0",
        source_families=["relationship_graph"],
        future_tools=[
            {"name": "company_universe_inventory", "status": "future"},
            {"name": "sector_pack_metadata", "status": "future"},
        ],
    ),
    _agent(
        agent_id="sec_operator",
        role="SEC Operator",
        description="Executes bounded SEC filing and exact-value ledger retrieval through MCP registry.",
        tool_permission="bounded_execute",
        allowed_tools=["sec_search_filings", "sec_query_exact_value_ledger"],
        allowed_data_views=["database_query", "artifact_ref"],
        route_authority="execute_route",
        model_profile="none",
        max_tool_calls=4,
        skill_ids=["shared_evidence_boundary", "evidence_operator_tool_use"],
        input_schema="EvidenceOperatorInputV0",
        output_schema="EvidenceOperatorObservationV0",
        source_families=["primary_sec_filing"],
    ),
    _agent(
        agent_id="eight_k_operator",
        role="8-K Operator",
        description="Executes bounded 8-K earnings-release commentary retrieval through MCP registry.",
        tool_permission="bounded_execute",
        allowed_tools=["sec_search_filings"],
        allowed_data_views=["database_query", "artifact_ref"],
        route_authority="execute_route",
        model_profile="none",
        max_tool_calls=4,
        skill_ids=["shared_evidence_boundary", "evidence_operator_tool_use"],
        input_schema="EvidenceOperatorInputV0",
        output_schema="EvidenceOperatorObservationV0",
        source_families=["company_authored_unaudited_sec_filing"],
    ),
    _agent(
        agent_id="market_operator",
        role="Market Operator",
        description="Executes bounded market snapshot retrieval for returns, valuation context, and event windows.",
        tool_permission="bounded_execute",
        allowed_tools=["market_get_snapshot"],
        allowed_data_views=["database_query", "artifact_ref"],
        route_authority="execute_route",
        model_profile="none",
        max_tool_calls=4,
        skill_ids=["shared_evidence_boundary", "evidence_operator_tool_use"],
        input_schema="EvidenceOperatorInputV0",
        output_schema="MarketOperatorObservationV0",
        source_families=["market_snapshot"],
    ),
    _agent(
        agent_id="industry_operator",
        role="Industry Operator",
        description="Executes bounded industry snapshot retrieval for macro, sector, commodity, and regulatory context.",
        tool_permission="bounded_execute",
        allowed_tools=["industry_get_snapshot"],
        allowed_data_views=["database_query", "artifact_ref"],
        route_authority="execute_route",
        model_profile="none",
        max_tool_calls=4,
        skill_ids=["shared_evidence_boundary", "evidence_operator_tool_use"],
        input_schema="EvidenceOperatorInputV0",
        output_schema="IndustryOperatorObservationV0",
        source_families=["industry_snapshot"],
    ),
    _agent(
        agent_id="coverage_reflection",
        role="Coverage / Reflection Agent",
        description="Assesses sufficiency, source gaps, second-pass needs, bounded-answer eligibility, and loop breaks.",
        tool_permission="orchestrate_subgraph",
        allowed_tools=["run_inspect_artifacts"],
        allowed_data_views=["bounded_rows", "coverage_summary", "artifact_ref", "tool_trace_summary"],
        route_authority="suggest_business_need",
        model_profile="balanced",
        max_tool_calls=1,
        skill_ids=["shared_evidence_boundary", "coverage_reflection"],
        input_schema="CoverageReflectionInputV0",
        output_schema="CoverageReflectionReportV0",
        source_families=["run_artifact"],
    ),
    _agent(
        agent_id="fundamental_analyst",
        role="Fundamental Analyst",
        description="Forms local, evidence-bounded fundamental observations from ledger and filing summaries.",
        tool_permission="inspect_only",
        allowed_tools=[],
        allowed_data_views=["bounded_rows"],
        route_authority="none",
        model_profile="balanced",
        max_tool_calls=0,
        skill_ids=["shared_evidence_boundary", "fundamental_analysis"],
        input_schema="SpecialistAnalystInputV0",
        output_schema="SpecialistAnalystMemoletV0",
        source_families=["primary_sec_filing", "company_authored_unaudited_sec_filing"],
    ),
    _agent(
        agent_id="industry_supply_chain_analyst",
        role="Industry / Supply Chain Analyst",
        description="Forms bounded industry, supply-chain, relationship, and readthrough observations from summaries.",
        tool_permission="inspect_only",
        allowed_tools=[],
        allowed_data_views=["bounded_rows", "relationship_graph_summary", "coverage_summary"],
        route_authority="none",
        model_profile="balanced",
        max_tool_calls=0,
        skill_ids=["shared_evidence_boundary", "industry_supply_chain_analysis"],
        input_schema="SpecialistAnalystInputV0",
        output_schema="SpecialistAnalystMemoletV0",
        source_families=["industry_snapshot", "relationship_graph", "primary_sec_filing", "company_authored_unaudited_sec_filing"],
    ),
    _agent(
        agent_id="market_valuation_analyst",
        role="Market / Valuation Analyst",
        description="Forms local market-reaction and valuation-context observations from bounded market summaries.",
        tool_permission="inspect_only",
        allowed_tools=[],
        allowed_data_views=["bounded_rows"],
        route_authority="none",
        model_profile="balanced",
        max_tool_calls=0,
        skill_ids=["shared_evidence_boundary", "market_valuation_analysis"],
        input_schema="SpecialistAnalystInputV0",
        output_schema="SpecialistAnalystMemoletV0",
        source_families=["market_snapshot"],
    ),
    _agent(
        agent_id="risk_counterevidence_analyst",
        role="Risk / Counterevidence Analyst",
        description="Identifies evidence conflicts, risks, and unsupported claims from bounded summaries and source gaps.",
        tool_permission="inspect_only",
        allowed_tools=[],
        allowed_data_views=["bounded_rows", "coverage_summary"],
        route_authority="none",
        model_profile="balanced",
        max_tool_calls=0,
        skill_ids=["shared_evidence_boundary", "risk_counterevidence"],
        input_schema="SpecialistAnalystInputV0",
        output_schema="SpecialistAnalystMemoletV0",
        source_families=["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot", "industry_snapshot"],
    ),
    _agent(
        agent_id="judgment_plan_aggregator",
        role="Judgment Plan Aggregator",
        description="Aggregates specialist memolets, conflicts, evidence boundaries, and verifier constraints into a judgment plan.",
        tool_permission="inspect_only",
        allowed_tools=["run_inspect_artifacts"],
        allowed_data_views=["bounded_rows", "coverage_summary", "artifact_ref"],
        route_authority="none",
        model_profile="fast",
        max_tool_calls=1,
        skill_ids=["shared_evidence_boundary", "judgment_plan_aggregation"],
        input_schema="JudgmentPlanAggregatorInputV0",
        output_schema="JudgmentPlanV0",
        source_families=["run_artifact"],
    ),
    _agent(
        agent_id="memo_writer",
        role="Memo Writer Agent",
        description="Writes the user-facing memo from verified judgment plan and bounded evidence summaries only.",
        tool_permission="none",
        allowed_tools=[],
        allowed_data_views=["verified_summary"],
        route_authority="none",
        model_profile="strong",
        max_tool_calls=0,
        skill_ids=["shared_evidence_boundary", "memo_writer"],
        input_schema="MemoWriterInputV0",
        output_schema="MemoDraftV0",
        source_families=["run_artifact"],
    ),
    _agent(
        agent_id="verifier",
        role="Verifier Agent",
        description="Checks claim support, source boundary, numbers, period roles, and unsupported named facts without adding new views.",
        tool_permission="inspect_only",
        allowed_tools=["run_inspect_artifacts"],
        allowed_data_views=["bounded_rows", "coverage_summary", "artifact_ref"],
        route_authority="none",
        model_profile="strong",
        max_tool_calls=1,
        skill_ids=["shared_evidence_boundary", "verification"],
        input_schema="VerifierInputV0",
        output_schema="VerificationReportV0",
        source_families=["run_artifact"],
    ),
    _agent(
        agent_id="renderer",
        role="Renderer",
        description="Formats final memo, source boundaries, dates, and evidence strength for the user.",
        tool_permission="none",
        allowed_tools=[],
        allowed_data_views=["verified_summary"],
        route_authority="none",
        model_profile="none",
        max_tool_calls=0,
        skill_ids=["shared_evidence_boundary", "renderer"],
        input_schema="RendererInputV0",
        output_schema="RenderedAnswerV0",
        source_families=["run_artifact"],
    ),
]
