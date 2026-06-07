from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


SCHEMA_VERSION = "sec_agent_agent_activation_plan_v0.1"

EXECUTION_MODES = {
    "deterministic_lookup",
    "focused_answer",
    "standard_memo",
    "deep_research",
}

MODEL_PROFILES = {"none", "fast", "balanced", "strong"}
AGENT_PRIORITY_LEVELS = {"primary", "supporting", "conditional", "low"}

DEFAULT_AGENT_IDS = {
    "research_lead",
    "universe_relationship",
    "sec_operator",
    "eight_k_operator",
    "market_operator",
    "industry_operator",
    "coverage_reflection",
    "fundamental_analyst",
    "industry_supply_chain_analyst",
    "market_valuation_analyst",
    "risk_counterevidence_analyst",
    "judgment_plan_aggregator",
    "memo_writer",
    "verifier",
    "renderer",
}

DEFAULT_SOURCE_FAMILIES = {
    "primary_sec_filing",
    "company_authored_unaudited_sec_filing",
    "market_snapshot",
    "industry_snapshot",
    "run_artifact",
}

DEFAULT_GLOBAL_LIMITS = {
    "max_tool_calls_total": 12,
    "max_second_pass_rounds": 2,
    "max_repair_rounds": 2,
}

MODE_REQUIRED_AGENTS = {
    "deterministic_lookup": {"renderer"},
    "focused_answer": {"research_lead", "coverage_reflection", "memo_writer", "verifier", "renderer"},
    "standard_memo": {"research_lead", "coverage_reflection", "memo_writer", "verifier", "renderer"},
    "deep_research": {
        "research_lead",
        "universe_relationship",
        "coverage_reflection",
        "memo_writer",
        "verifier",
        "renderer",
    },
}

MODE_DISALLOWED_AGENTS = {
    "deterministic_lookup": {
        "universe_relationship",
        "fundamental_analyst",
        "industry_supply_chain_analyst",
        "market_valuation_analyst",
        "risk_counterevidence_analyst",
        "judgment_plan_aggregator",
        "memo_writer",
    },
    "focused_answer": {
        "universe_relationship",
        "fundamental_analyst",
        "industry_supply_chain_analyst",
        "market_valuation_analyst",
        "risk_counterevidence_analyst",
        "judgment_plan_aggregator",
    },
}

RETRIEVAL_TOOL_NAMES = {
    "sec_search_filings",
    "sec_milvus_semantic_search",
    "sec_query_exact_value_ledger",
    "market_get_snapshot",
    "industry_get_snapshot",
}

OPERATOR_TOOL_ALLOWLIST = {
    "sec_operator": {"sec_search_filings", "sec_milvus_semantic_search", "sec_query_exact_value_ledger"},
    "eight_k_operator": {"sec_search_filings"},
    "market_operator": {"market_get_snapshot"},
    "industry_operator": {"industry_get_snapshot"},
}


@dataclass
class SkippedAgent:
    agent_id: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"agent_id": self.agent_id, "reason": self.reason}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SkippedAgent":
        return cls(
            agent_id=str(payload.get("agent_id") or payload.get("agent") or "").strip(),
            reason=str(payload.get("reason") or "").strip(),
        )


@dataclass
class AgentActivationPlan:
    execution_mode: str
    activate_agents: list[str]
    skip_agents: list[SkippedAgent] = field(default_factory=list)
    allowed_source_families: list[str] = field(default_factory=list)
    model_policy_hint: dict[str, str] = field(default_factory=dict)
    agent_priorities: dict[str, str] = field(default_factory=dict)
    max_tool_calls_total: int = 6
    max_second_pass_rounds: int = 1
    max_repair_rounds: int = 1
    reasoning_summary: str = ""
    schema_version: str = SCHEMA_VERSION
    scope_mode: str = ""
    focus_tickers: list[str] = field(default_factory=list)
    search_scope_tickers: list[str] = field(default_factory=list)
    relationship_scope_rationale: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["skip_agents"] = [item.to_dict() for item in self.skip_agents]
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AgentActivationPlan":
        return normalize_agent_activation_plan(payload)


def normalize_agent_activation_plan(payload: Mapping[str, Any] | AgentActivationPlan) -> AgentActivationPlan:
    if isinstance(payload, AgentActivationPlan):
        return payload
    return AgentActivationPlan(
        schema_version=str(payload.get("schema_version") or SCHEMA_VERSION).strip(),
        execution_mode=str(payload.get("execution_mode") or "").strip(),
        activate_agents=_unique_strings(payload.get("activate_agents")),
        skip_agents=_skipped_agents(payload.get("skip_agents")),
        allowed_source_families=_unique_strings(payload.get("allowed_source_families")),
        model_policy_hint={
            str(agent_id).strip(): str(profile).strip()
            for agent_id, profile in dict(payload.get("model_policy_hint") or {}).items()
            if str(agent_id).strip()
        },
        agent_priorities={
            str(agent_id).strip(): str(priority).strip()
            for agent_id, priority in dict(payload.get("agent_priorities") or {}).items()
            if str(agent_id).strip()
        },
        max_tool_calls_total=_int_value(payload.get("max_tool_calls_total"), default=6),
        max_second_pass_rounds=_int_value(payload.get("max_second_pass_rounds"), default=1),
        max_repair_rounds=_int_value(payload.get("max_repair_rounds"), default=1),
        reasoning_summary=str(payload.get("reasoning_summary") or "").strip(),
        scope_mode=str(payload.get("scope_mode") or "").strip(),
        focus_tickers=_unique_upper(payload.get("focus_tickers")),
        search_scope_tickers=_unique_upper(payload.get("search_scope_tickers")),
        relationship_scope_rationale=str(payload.get("relationship_scope_rationale") or "").strip(),
        metadata=dict(payload.get("metadata") or {}),
    )


def validate_agent_activation_plan(
    payload: Mapping[str, Any] | AgentActivationPlan,
    *,
    known_agent_ids: set[str] | None = None,
    source_inventory: Mapping[str, Any] | None = None,
    allowed_source_families: set[str] | None = None,
    global_limits: Mapping[str, int] | None = None,
    agent_registry: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    plan = normalize_agent_activation_plan(payload)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    agent_ids = set(known_agent_ids or DEFAULT_AGENT_IDS) | set(agent_registry or {})
    source_families = set(allowed_source_families or _source_families_from_inventory(source_inventory) or DEFAULT_SOURCE_FAMILIES)
    limits = {**DEFAULT_GLOBAL_LIMITS, **{key: int(value) for key, value in dict(global_limits or {}).items()}}

    _validate_schema_version(plan, warnings)
    _validate_execution_mode(plan, errors)
    _validate_agent_ids(plan, agent_ids, errors)
    _validate_mode_agents(plan, errors)
    _validate_source_families(plan, source_families, errors)
    _validate_model_policy(plan, agent_ids, errors)
    _validate_agent_priorities(plan, agent_ids, errors)
    _validate_budgets(plan, limits, errors)
    _validate_scope_drift(plan, errors, warnings)
    _validate_role_specific_scope(plan, errors)
    _validate_agent_registry_permissions(plan, agent_registry or {}, errors)

    return {
        "status": "fail" if errors else "pass",
        "schema_version": SCHEMA_VERSION,
        "plan": plan.to_dict(),
        "errors": errors,
        "warnings": warnings,
    }


def assert_valid_agent_activation_plan(
    payload: Mapping[str, Any] | AgentActivationPlan,
    **kwargs: Any,
) -> AgentActivationPlan:
    result = validate_agent_activation_plan(payload, **kwargs)
    if result["status"] != "pass":
        error_types = ", ".join(error["type"] for error in result["errors"])
        raise ValueError(f"invalid agent activation plan: {error_types}")
    return normalize_agent_activation_plan(result["plan"])


def _validate_schema_version(plan: AgentActivationPlan, warnings: list[dict[str, Any]]) -> None:
    if plan.schema_version != SCHEMA_VERSION:
        warnings.append({"type": "schema_version_normalized", "value": plan.schema_version})


def _validate_execution_mode(plan: AgentActivationPlan, errors: list[dict[str, Any]]) -> None:
    if plan.execution_mode not in EXECUTION_MODES:
        errors.append({"type": "invalid_execution_mode", "value": plan.execution_mode})


def _validate_agent_ids(plan: AgentActivationPlan, agent_ids: set[str], errors: list[dict[str, Any]]) -> None:
    active = set(plan.activate_agents)
    skipped = {item.agent_id for item in plan.skip_agents}
    for agent_id in sorted(active | skipped):
        if agent_id not in agent_ids:
            errors.append({"type": "unknown_agent", "agent_id": agent_id})
    for item in plan.skip_agents:
        if not item.reason:
            errors.append({"type": "skip_agent_reason_required", "agent_id": item.agent_id})
    overlap = sorted(active & skipped)
    if overlap:
        errors.append({"type": "agent_active_and_skipped", "agent_ids": overlap})


def _validate_mode_agents(plan: AgentActivationPlan, errors: list[dict[str, Any]]) -> None:
    if plan.execution_mode not in EXECUTION_MODES:
        return
    active = set(plan.activate_agents)
    missing = sorted(MODE_REQUIRED_AGENTS.get(plan.execution_mode, set()) - active)
    if missing:
        errors.append({"type": "required_agent_missing", "execution_mode": plan.execution_mode, "agent_ids": missing})
    disallowed = sorted(MODE_DISALLOWED_AGENTS.get(plan.execution_mode, set()) & active)
    if disallowed:
        errors.append({"type": "agent_not_allowed_for_execution_mode", "execution_mode": plan.execution_mode, "agent_ids": disallowed})


def _validate_source_families(
    plan: AgentActivationPlan,
    source_families: set[str],
    errors: list[dict[str, Any]],
) -> None:
    if not plan.allowed_source_families:
        errors.append({"type": "allowed_source_families_required"})
        return
    invalid = sorted(set(plan.allowed_source_families) - source_families)
    if invalid:
        errors.append({"type": "unknown_source_family", "source_families": invalid})


def _validate_model_policy(plan: AgentActivationPlan, agent_ids: set[str], errors: list[dict[str, Any]]) -> None:
    for agent_id, profile in sorted(plan.model_policy_hint.items()):
        if agent_id not in agent_ids:
            errors.append({"type": "model_policy_unknown_agent", "agent_id": agent_id})
        if profile not in MODEL_PROFILES:
            errors.append({"type": "invalid_model_profile", "agent_id": agent_id, "profile": profile})


def _validate_agent_priorities(plan: AgentActivationPlan, agent_ids: set[str], errors: list[dict[str, Any]]) -> None:
    active = set(plan.activate_agents)
    for agent_id, priority in sorted(plan.agent_priorities.items()):
        if agent_id not in agent_ids:
            errors.append({"type": "agent_priority_unknown_agent", "agent_id": agent_id})
            continue
        if agent_id not in active:
            errors.append({"type": "agent_priority_for_inactive_agent", "agent_id": agent_id})
        if priority not in AGENT_PRIORITY_LEVELS:
            errors.append({"type": "invalid_agent_priority", "agent_id": agent_id, "priority": priority})


def _validate_budgets(
    plan: AgentActivationPlan,
    limits: Mapping[str, int],
    errors: list[dict[str, Any]],
) -> None:
    values = {
        "max_tool_calls_total": plan.max_tool_calls_total,
        "max_second_pass_rounds": plan.max_second_pass_rounds,
        "max_repair_rounds": plan.max_repair_rounds,
    }
    for field_name, value in values.items():
        if value < 0:
            errors.append({"type": "negative_budget", "field": field_name, "value": value})
            continue
        limit = int(limits[field_name])
        if value > limit:
            errors.append({"type": "budget_exceeds_global_limit", "field": field_name, "value": value, "limit": limit})


def _validate_scope_drift(
    plan: AgentActivationPlan,
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    if not plan.scope_mode:
        return
    if plan.execution_mode == "deterministic_lookup" and plan.scope_mode in {"sector_representative", "full_universe"}:
        errors.append({"type": "deterministic_lookup_scope_expansion", "scope_mode": plan.scope_mode})
    if plan.execution_mode == "focused_answer":
        expanded = plan.scope_mode == "full_universe" or (
            plan.focus_tickers
            and plan.search_scope_tickers
            and len(set(plan.search_scope_tickers) - set(plan.focus_tickers)) >= 4
        )
        if expanded and not plan.relationship_scope_rationale:
            errors.append({"type": "focused_scope_expansion_without_rationale", "scope_mode": plan.scope_mode})
        elif expanded:
            warnings.append({"type": "focused_scope_expansion_requires_review", "scope_mode": plan.scope_mode})
    if plan.execution_mode == "deep_research" and "universe_relationship" in plan.activate_agents and not plan.relationship_scope_rationale:
        errors.append({"type": "relationship_scope_rationale_required"})


def _validate_role_specific_scope(plan: AgentActivationPlan, errors: list[dict[str, Any]]) -> None:
    active = set(plan.activate_agents)
    if "industry_supply_chain_analyst" not in active:
        return
    scope_sources = set(plan.allowed_source_families) & {"industry_snapshot", "relationship_graph"}
    scope_agents = active & {"industry_operator", "universe_relationship"}
    if not scope_sources and not scope_agents:
        errors.append(
            {
                "type": "industry_supply_chain_agent_requires_industry_or_relationship_scope",
                "agent_id": "industry_supply_chain_analyst",
            }
        )


def _validate_agent_registry_permissions(
    plan: AgentActivationPlan,
    agent_registry: Mapping[str, Mapping[str, Any]],
    errors: list[dict[str, Any]],
) -> None:
    for agent_id in plan.activate_agents:
        entry = dict(agent_registry.get(agent_id) or {})
        if not entry:
            continue
        allowed_tools = set(_unique_strings(entry.get("allowed_tools")))
        tool_permission = str(entry.get("tool_permission") or "").strip()
        if agent_id in {"memo_writer", "renderer"} and allowed_tools:
            errors.append({"type": "agent_must_not_have_tools", "agent_id": agent_id, "tools": sorted(allowed_tools)})
        if agent_id == "verifier":
            if tool_permission and tool_permission != "inspect_only":
                errors.append({"type": "verifier_must_be_inspect_only", "tool_permission": tool_permission})
            retrieval_tools = sorted(allowed_tools & RETRIEVAL_TOOL_NAMES)
            if retrieval_tools:
                errors.append({"type": "verifier_retrieval_tools_forbidden", "tools": retrieval_tools})
        if agent_id == "research_lead":
            retrieval_tools = sorted(allowed_tools & RETRIEVAL_TOOL_NAMES)
            if retrieval_tools:
                errors.append({"type": "research_lead_retrieval_tools_forbidden", "tools": retrieval_tools})
        operator_tools = OPERATOR_TOOL_ALLOWLIST.get(agent_id)
        if operator_tools is not None:
            invalid_tools = sorted(allowed_tools - operator_tools)
            if invalid_tools:
                errors.append({"type": "operator_tool_not_allowed", "agent_id": agent_id, "tools": invalid_tools})


def _source_families_from_inventory(source_inventory: Mapping[str, Any] | None) -> set[str]:
    if not source_inventory:
        return set()
    values: list[Any] = []
    for key in ("source_families", "source_tiers", "allowed_source_families", "available_source_families"):
        raw = source_inventory.get(key)
        if isinstance(raw, dict):
            values.extend(raw.keys())
        else:
            values.extend(_list_value(raw))
    return set(_unique_strings(values))


def _skipped_agents(value: Any) -> list[SkippedAgent]:
    result: list[SkippedAgent] = []
    for item in _list_value(value):
        if isinstance(item, Mapping):
            result.append(SkippedAgent.from_dict(item))
        elif str(item).strip():
            result.append(SkippedAgent(agent_id=str(item).strip(), reason=""))
    return result


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [value]


def _unique_strings(value: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in _list_value(value):
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _unique_upper(value: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in _list_value(value):
        text = str(item or "").upper().strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _int_value(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
