from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence


SKILL_SCHEMA_VERSION = "sec_agent_research_skills_v0.3"
SKILL_DEFINITION_VERSION_SCHEMA = "sec_agent_skill_definition_version_v0.1"
SKILL_PACK_VERSION_SCHEMA = "sec_agent_skill_pack_version_v0.1"
S3_GRAPH_PROJECTION_SKILL_CONTRACT_REF = (
    "fin01.s3.graph_projection_skill_contracts:v1"
)

PROMPT_ROOT = Path(__file__).resolve().parent / "prompts" / "skills"

SKILL_FILES: dict[str, str] = {
    "investment_research_workflow": "investment_research_workflow_skill_v0_1.md",
    "evidence_requirement_and_sufficiency": "evidence_requirement_and_sufficiency_skill_v0_1.md",
    "shared_evidence_boundary": "shared_evidence_boundary_skill_v0_1.md",
    "research_lead_planning": "research_lead_planning_skill_v0_1.md",
    "coverage_reflection": "coverage_reflection_skill_v0_1.md",
    "memo_writer": "memo_writer_skill_v0_1.md",
    "verification": "verification_skill_v0_1.md",
    "fundamental_analysis": "fundamental_analysis_skill_v0_2.md",
    "product_technology_analysis": "product_technology_analysis_skill_v0_1.md",
    "industry_supply_chain_analysis": "industry_supply_chain_analysis_skill_v0_2.md",
    "market_valuation_analysis": "market_valuation_analysis_skill_v0_2.md",
    "risk_counterevidence": "risk_counterevidence_skill_v0_2.md",
    "relationship_universe": "relationship_universe_skill_v0_1.md",
    "evidence_operator_tool_use": "evidence_operator_tool_use_skill_v0_1.md",
    "judgment_plan_aggregation": "judgment_plan_aggregation_skill_v0_1.md",
    "renderer": "renderer_skill_v0_1.md",
}

ROLE_SKILLS: dict[str, tuple[str, ...]] = {
    "planner": ("evidence_requirement_and_sufficiency", "investment_research_workflow"),
    "reflection": ("evidence_requirement_and_sufficiency",),
    "synthesis": ("investment_research_workflow",),
    "research_lead": ("shared_evidence_boundary", "research_lead_planning"),
    "coverage_reflection": ("shared_evidence_boundary", "coverage_reflection"),
    "memo_writer": ("shared_evidence_boundary", "memo_writer"),
    "verifier": ("shared_evidence_boundary", "verification"),
    "universe_relationship": ("shared_evidence_boundary", "relationship_universe"),
    "sec_operator": ("shared_evidence_boundary", "evidence_operator_tool_use"),
    "eight_k_operator": ("shared_evidence_boundary", "evidence_operator_tool_use"),
    "market_operator": ("shared_evidence_boundary", "evidence_operator_tool_use"),
    "industry_operator": ("shared_evidence_boundary", "evidence_operator_tool_use"),
    "web_evidence_operator": ("shared_evidence_boundary", "evidence_operator_tool_use"),
    "fundamental_analyst": ("shared_evidence_boundary", "fundamental_analysis"),
    "product_technology_analyst": ("shared_evidence_boundary", "product_technology_analysis"),
    "industry_supply_chain_analyst": ("shared_evidence_boundary", "industry_supply_chain_analysis"),
    "market_valuation_analyst": ("shared_evidence_boundary", "market_valuation_analysis"),
    "risk_counterevidence_analyst": ("shared_evidence_boundary", "risk_counterevidence"),
    "judgment_plan_aggregator": ("shared_evidence_boundary", "judgment_plan_aggregation"),
    "renderer": ("shared_evidence_boundary", "renderer"),
}


@lru_cache(maxsize=16)
def load_research_skill(skill_name: str) -> str:
    filename = SKILL_FILES.get(str(skill_name or ""))
    if not filename:
        raise KeyError(f"unknown research skill: {skill_name}")
    path = PROMPT_ROOT / filename
    return path.read_text(encoding="utf-8").strip()


def research_skill_prompt(role: str, *, max_chars: int = 4000) -> str:
    skill_names = ROLE_SKILLS.get(str(role or ""), ())
    if not skill_names:
        raise KeyError(f"unknown research skill role: {role}")
    chunks = [load_research_skill(name) for name in skill_names]
    text = "\n\n".join(chunks).strip()
    if max_chars and len(text) > max_chars:
        return text[: max(0, max_chars)].rstrip() + "\n[skill truncated by runtime budget]"
    return text


def list_research_skills() -> dict[str, object]:
    return {
        "schema_version": SKILL_SCHEMA_VERSION,
        "skill_files": dict(SKILL_FILES),
        "role_skills": {role: list(names) for role, names in ROLE_SKILLS.items()},
    }


def skill_definition_version(skill_name: str) -> dict[str, Any]:
    """Return a content-addressed version of one existing reviewed Skill.

    The version is descriptive only.  It never grants tool, model, network, or
    canonical-write authority.
    """

    skill_id = str(skill_name or "").strip()
    filename = SKILL_FILES.get(skill_id)
    if not filename:
        raise KeyError(f"unknown research skill: {skill_id}")
    content = load_research_skill(skill_id)
    content_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    definition = {
        "schema_version": SKILL_DEFINITION_VERSION_SCHEMA,
        "skill_id": skill_id,
        "source_file": filename,
        "source_registry_schema_version": SKILL_SCHEMA_VERSION,
        "content_digest": content_digest,
        "applicability": "selected_by_versioned_agent_contract_and_runtime_observation",
        "preconditions": [
            "execution_profile_is_explicitly_allowlisted",
            "agent_contract_lists_skill_id",
        ],
        "output_fields": ["method_instructions", "boundary_instructions"],
        "authority_grants": [],
    }
    digest = _version_digest(definition)
    return {
        **definition,
        "canonical_digest": digest,
        "skill_definition_version_ref": f"skill:{skill_id}:{digest[:16]}",
    }


def select_skill_pack_version(
    *,
    agent_id: str,
    registered_skill_ids: Sequence[str],
    execution_profile_version_ref: str,
    allowed_execution_profile_refs: Sequence[str],
    optional_skill_observation_keys: Mapping[str, str] | None = None,
    observations: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Select a deterministic, content-addressed SkillPack from the existing registry."""

    profile_ref = str(execution_profile_version_ref or "").strip()
    allowed_profiles = tuple(str(value) for value in allowed_execution_profile_refs)
    if not profile_ref or profile_ref not in allowed_profiles:
        raise PermissionError("execution_profile_not_allowed_for_skill_pack")
    optional_rules = dict(optional_skill_observation_keys or {})
    observation_values = dict(observations or {})
    registered = tuple(dict.fromkeys(str(value) for value in registered_skill_ids if str(value)))
    unknown_optional = sorted(set(optional_rules) - set(registered))
    if unknown_optional:
        raise ValueError(f"optional_skill_not_registered:{','.join(unknown_optional)}")
    selected_ids: list[str] = []
    skipped: list[dict[str, str]] = []
    for skill_id in registered:
        observation_key = optional_rules.get(skill_id)
        if observation_key and not bool(observation_values.get(observation_key)):
            skipped.append(
                {
                    "skill_id": skill_id,
                    "reason": f"optional_observation_false:{observation_key}",
                }
            )
            continue
        selected_ids.append(skill_id)
    definitions = [skill_definition_version(skill_id) for skill_id in selected_ids]
    definition_refs = [row["skill_definition_version_ref"] for row in definitions]
    pack_identity = {
        "schema_version": SKILL_PACK_VERSION_SCHEMA,
        "agent_id": str(agent_id),
        "execution_profile_version_ref": profile_ref,
        "skill_definition_version_refs": definition_refs,
        "skipped_optional_skills": skipped,
        "authority_grants": [],
    }
    digest = _version_digest(pack_identity)
    return {
        **pack_identity,
        "skill_pack_version_ref": f"skill-pack:{agent_id}:{digest[:16]}",
        "canonical_digest": digest,
        "skill_definitions": definitions,
    }


def s3_graph_projection_skill_contracts() -> tuple[dict[str, Any], ...]:
    """Return T05 method/role contracts without granting execution authority."""

    rows = (
        {
            "program_cell_id": "demand_authenticity_and_sustainability",
            "role_ids": (
                "product_technology_analyst",
                "industry_supply_chain_analyst",
            ),
            "method_ids": (
                "product_to_financial_bridge",
                "customer_supplier_readthrough",
            ),
            "allowed_output": "bounded_product_deployment_and_relationship_context",
            "forbidden_output": (
                "durable_demand_fact_without_promoted_source",
                "customer_capex_as_NVDA_revenue",
            ),
        },
        {
            "program_cell_id": "value_and_profit_capture",
            "role_ids": (
                "product_technology_analyst",
                "market_valuation_analyst",
            ),
            "method_ids": (
                "product_to_financial_bridge",
                "p32_product_architecture_competitive_bridge",
            ),
            "allowed_output": "bounded_product_to_company_total_profitability_bridge",
            "forbidden_output": (
                "product_or_segment_profit_allocation",
                "market_price_in_fact_without_same_as_of_market_source",
            ),
        },
        {
            "program_cell_id": (
                "bottleneck_counterevidence_and_what_would_change"
            ),
            "role_ids": (
                "industry_supply_chain_analyst",
                "market_valuation_analyst",
                "risk_counterevidence_analyst",
            ),
            "method_ids": (
                "customer_supplier_readthrough",
                "p32_semis_cycle_value_chain_playbook",
            ),
            "allowed_output": "bounded_mechanism_risk_and_source_followup_context",
            "forbidden_output": (
                "relationship_path_as_current_bottleneck_fact",
                "probability_or_financial_impact_without_numeric_authority",
            ),
        },
    )
    contracts: list[dict[str, Any]] = []
    for row in rows:
        definitions = tuple(
            skill_definition_version(skill_id)
            for role_id in row["role_ids"]
            for skill_id in ROLE_SKILLS[role_id]
        )
        payload = {
            "contract_ref": S3_GRAPH_PROJECTION_SKILL_CONTRACT_REF,
            **row,
            "skill_definition_version_refs": tuple(
                definition["skill_definition_version_ref"]
                for definition in definitions
            ),
            "authority_grants": (),
            "model_execution_authorized": False,
            "network_execution_authorized": False,
            "business_write_authorized": False,
        }
        digest = _version_digest(payload)
        contracts.append(
            {
                **payload,
                "contract_version_ref": f"s3-graph-skill:{digest[:16]}",
                "contract_digest": digest,
            }
        )
    return tuple(contracts)


def _version_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()
