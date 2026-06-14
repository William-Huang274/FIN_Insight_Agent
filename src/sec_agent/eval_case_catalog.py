from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


DEFAULT_RUN_AUDIT_TABLES = [
    "run",
    "node_execution",
    "artifact_ref",
    "evidence_row",
    "claim_card",
    "gap",
    "gate_result",
    "model_call",
]
DEFAULT_RUN_AUDIT_NONEMPTY_TABLES = [
    "run",
    "node_execution",
    "artifact_ref",
    "evidence_row",
    "claim_card",
    "gate_result",
    "model_call",
]
DEFAULT_OPERATOR_AGENTS = ["sec_operator", "eight_k_operator"]
DEFAULT_SPECIALIST_AGENTS = [
    "fundamental_analyst",
    "market_valuation_analyst",
    "risk_counterevidence_analyst",
]
PRODUCT_SPECIALIST = "product_technology_analyst"
INDUSTRY_SPECIALIST = "industry_supply_chain_analyst"


FAMILY_RUNTIME_PROFILES: dict[str, dict[str, Any]] = {
    "L1_basic_focused": {
        "category": "focused_answer",
        "expected_execution_mode": "focused_answer",
        "specialists": [],
        "operators": ["sec_operator", "eight_k_operator"],
        "max_tool_calls_total_lte": 8,
        "require_depth_surface": False,
    },
    "L2_standard_memo": {
        "category": "standard_memo",
        "expected_execution_mode": "standard_memo",
        "specialists": [*DEFAULT_SPECIALIST_AGENTS, PRODUCT_SPECIALIST],
        "operators": [*DEFAULT_OPERATOR_AGENTS, "market_operator"],
        "max_tool_calls_total_lte": 12,
        "require_depth_surface": True,
    },
    "L3_deep_research": {
        "category": "sector_depth",
        "expected_execution_mode": "deep_research",
        "specialists": [*DEFAULT_SPECIALIST_AGENTS, INDUSTRY_SPECIALIST, PRODUCT_SPECIALIST],
        "operators": ["universe_relationship", *DEFAULT_OPERATOR_AGENTS, "market_operator", "industry_operator"],
        "max_tool_calls_total_lte": 18,
        "require_depth_surface": True,
        "require_universe": True,
    },
    "L4_gap_boundary": {
        "category": "gap_boundary",
        "expected_execution_mode": "deep_research",
        "specialists": [*DEFAULT_SPECIALIST_AGENTS, INDUSTRY_SPECIALIST, PRODUCT_SPECIALIST],
        "operators": ["universe_relationship", *DEFAULT_OPERATOR_AGENTS, "market_operator", "industry_operator"],
        "max_tool_calls_total_lte": 18,
        "require_depth_surface": True,
        "require_universe": True,
    },
    "L5_non_us_supply_chain": {
        "category": "non_us_supply_chain",
        "expected_execution_mode": "deep_research",
        "specialists": [*DEFAULT_SPECIALIST_AGENTS, INDUSTRY_SPECIALIST, PRODUCT_SPECIALIST],
        "operators": ["universe_relationship", *DEFAULT_OPERATOR_AGENTS, "market_operator", "industry_operator"],
        "max_tool_calls_total_lte": 18,
        "require_depth_surface": True,
        "require_universe": True,
    },
    "L6_backend_runtime_stress": {
        "category": "backend_runtime_stress",
        "expected_execution_mode": "focused_answer",
        "specialists": [],
        "operators": DEFAULT_OPERATOR_AGENTS,
        "max_tool_calls_total_lte": 20,
        "require_depth_surface": False,
    },
}


PACK_BY_INDUSTRY_KEYWORD = [
    (("bank", "financial", "payment"), "financial_services_depth"),
    (("healthcare", "pharma", "glp1", "medtech"), "healthcare_life_sciences_depth"),
    (("retail", "consumer_discretionary", "home_improvement", "automotive"), "consumer_discretionary_depth"),
    (("cpg", "staples"), "consumer_staples_depth"),
    (("energy", "lng", "oil"), "energy_infrastructure_depth"),
    (("utility", "utilities", "power", "data_center_power"), "real_estate_utilities_depth"),
    (("media", "streaming", "communication"), "communication_media_depth"),
    (("semiconductor", "software", "cloud", "ai", "cyber", "technology", "hyperscaler"), "technology_ai_infrastructure_depth"),
]


def load_case_catalog(path: str | Path) -> dict[str, Any]:
    catalog_path = Path(path)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict):
        raise ValueError("case catalog must be a JSON object")
    if not isinstance(catalog.get("cases"), list):
        raise ValueError("case catalog missing cases list")
    return catalog


def expand_case_catalog(
    catalog: Mapping[str, Any],
    *,
    subset: str | None = None,
    case_family: str | None = None,
    case_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    selected = _select_catalog_cases(catalog, subset=subset, case_family=case_family, case_ids=case_ids)
    release_membership = _release_membership(catalog)
    return [
        expand_catalog_case(catalog, case, release_subsets=release_membership.get(str(case.get("case_id") or ""), []))
        for case in selected
    ]


def expand_catalog_case(
    catalog: Mapping[str, Any],
    case: Mapping[str, Any],
    *,
    release_subsets: list[str] | None = None,
) -> dict[str, Any]:
    defaults = catalog.get("case_defaults") if isinstance(catalog.get("case_defaults"), Mapping) else {}
    family = str(case.get("case_family") or "")
    profile = FAMILY_RUNTIME_PROFILES.get(family, FAMILY_RUNTIME_PROFILES["L2_standard_memo"])
    source_tiers = _list(case.get("source_tiers") or defaults.get("source_tiers"))
    required_dimensions = _list(case.get("required_dimension_ids") or defaults.get("required_dimension_ids"))
    operators = _list(case.get("expected_operator_agents") or profile.get("operators"))
    specialists = _list(case.get("expected_specialist_agents") or profile.get("specialists"))
    category = str(case.get("category") or profile["category"])
    expected_execution_mode = str(case.get("expected_execution_mode") or _stress_execution_mode(case) or profile["expected_execution_mode"])
    require_depth_surface = bool(profile.get("require_depth_surface"))

    expanded: dict[str, Any] = dict(case)
    expanded.update(
        {
            "case_id": str(case.get("case_id") or ""),
            "category": category,
            "response_language": str(case.get("response_language") or defaults.get("response_language") or "zh-CN"),
            "source_tiers": source_tiers,
            "required_dimension_ids": required_dimensions,
            "expected_execution_mode": expected_execution_mode,
            "required_agents": _required_agents(operators=operators, specialists=specialists),
            "forbidden_agents": _forbidden_agents(operators=operators, specialists=specialists),
            "expected_operator_agents": operators,
            "expected_tool_names": _expected_tool_names(source_tiers, operators),
            "expected_specialist_agents": specialists,
            "memo_status_allowed": _list(case.get("memo_status_allowed") or ["draft", "blocked_by_specialist_verification"]),
            "max_tool_calls_total_lte": int(case.get("max_tool_calls_total_lte") or profile["max_tool_calls_total_lte"]),
            "require_lead_llm_pass": True,
            "require_universe_llm_pass": bool(profile.get("require_universe")),
            "require_specialist_llm_pass": bool(specialists),
            "require_memo_llm_pass": True,
            "require_verifier_llm_pass": True,
            "require_real_retrieval_pass": True,
            "require_real_evidence_quality_pass": bool(specialists),
            "require_response_language_match": True,
            "require_rendered_memo_claims": require_depth_surface,
            "require_rendered_evidence_refs": require_depth_surface,
            "require_dimension_memo_surface": require_depth_surface,
            "require_analyst_depth_gate": require_depth_surface,
            "require_run_audit_store": True,
            "required_run_audit_tables": DEFAULT_RUN_AUDIT_TABLES,
            "required_run_audit_nonempty_tables": DEFAULT_RUN_AUDIT_NONEMPTY_TABLES,
            "require_vnext_contract": True,
            "require_milvus_runtime_contract": True,
            "accept_bounded_block": True,
            "source_inventory_companies": _list(case.get("source_inventory_companies") or case.get("search_scope_tickers")),
            "catalog_id": str(catalog.get("catalog_id") or ""),
            "catalog_schema_version": str(catalog.get("schema_version") or ""),
            "catalog_case_family": family,
            "catalog_ordinal": int(case.get("ordinal") or 0),
            "catalog_release_subsets": release_subsets or [],
        }
    )
    pack_ids = _expected_relationship_pack_ids(case)
    if pack_ids and not expanded.get("expected_relationship_pack_ids"):
        expanded["expected_relationship_pack_ids"] = pack_ids
    if "data_center_power" in str(case.get("industry_schema") or ""):
        expanded["allowed_cross_sector_relationship_pack_ids"] = ["technology_ai_infrastructure_depth"]
    return expanded


def catalog_subset_ids(catalog: Mapping[str, Any], subset: str) -> list[str]:
    release_subsets = catalog.get("release_subsets") if isinstance(catalog.get("release_subsets"), Mapping) else {}
    if subset not in release_subsets:
        raise ValueError(f"unknown_case_subset: {subset}")
    return [str(case_id) for case_id in release_subsets[subset]]


def _select_catalog_cases(
    catalog: Mapping[str, Any],
    *,
    subset: str | None,
    case_family: str | None,
    case_ids: list[str] | None,
) -> list[Mapping[str, Any]]:
    cases = [case for case in catalog.get("cases") or [] if isinstance(case, Mapping)]
    selected_ids: set[str] | None = set(catalog_subset_ids(catalog, subset)) if subset else None
    if selected_ids is not None:
        cases = [case for case in cases if str(case.get("case_id") or "") in selected_ids]
        ordered = {str(case.get("case_id") or ""): case for case in cases}
        cases = [ordered[case_id] for case_id in catalog_subset_ids(catalog, subset) if case_id in ordered]
    if case_family:
        cases = [case for case in cases if str(case.get("case_family") or "") == case_family]
    if case_ids:
        requested = {str(case_id) for case_id in case_ids}
        cases = [case for case in cases if str(case.get("case_id") or "") in requested]
    return cases


def _release_membership(catalog: Mapping[str, Any]) -> dict[str, list[str]]:
    release_subsets = catalog.get("release_subsets") if isinstance(catalog.get("release_subsets"), Mapping) else {}
    membership: dict[str, list[str]] = {}
    for subset_name, case_ids in release_subsets.items():
        for case_id in _list(case_ids):
            membership.setdefault(case_id, []).append(str(subset_name))
    return membership


def _required_agents(*, operators: list[str], specialists: list[str]) -> list[str]:
    agents = ["research_lead", *operators, "coverage_reflection", *specialists, "memo_writer", "verifier", "renderer"]
    return _dedupe(agents)


def _forbidden_agents(*, operators: list[str], specialists: list[str]) -> list[str]:
    candidates = {
        "universe_relationship",
        "market_operator",
        "industry_operator",
        "fundamental_analyst",
        "market_valuation_analyst",
        "risk_counterevidence_analyst",
        "industry_supply_chain_analyst",
        "product_technology_analyst",
    }
    allowed = set(operators) | set(specialists)
    return sorted(candidates - allowed)


def _expected_tool_names(source_tiers: list[str], operators: list[str]) -> list[str]:
    source_set = set(source_tiers)
    tool_names = ["sec_search_filings"]
    if "relationship_graph" in source_set or "universe_relationship" in set(operators):
        tool_names.append("relationship_graph_lookup")
    if "market_snapshot" in source_set or "market_operator" in set(operators):
        tool_names.append("market_get_snapshot")
    if "industry_snapshot" in source_set or "industry_operator" in set(operators):
        tool_names.append("industry_get_snapshot")
    return _dedupe(tool_names)


def _stress_execution_mode(case: Mapping[str, Any]) -> str:
    case_id = str(case.get("case_id") or "")
    if "deep_research" in case_id:
        return "deep_research"
    if "cancel_resume" in case_id:
        return "standard_memo"
    return ""


def _expected_relationship_pack_ids(case: Mapping[str, Any]) -> list[str]:
    industry = str(case.get("industry_schema") or "").lower()
    for keywords, pack_id in PACK_BY_INDUSTRY_KEYWORD:
        if any(keyword in industry for keyword in keywords):
            return [pack_id]
    return []


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            out.append(value)
            seen.add(value)
    return out
