from __future__ import annotations

from functools import lru_cache
from pathlib import Path


SKILL_SCHEMA_VERSION = "sec_agent_research_skills_v0.5"

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
    "fundamental_analyst": ("shared_evidence_boundary", "fundamental_analysis"),
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
