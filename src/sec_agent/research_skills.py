from __future__ import annotations

from functools import lru_cache
from pathlib import Path


SKILL_SCHEMA_VERSION = "sec_agent_research_skills_v0.1"

PROMPT_ROOT = Path(__file__).resolve().parent / "prompts" / "skills"

SKILL_FILES: dict[str, str] = {
    "investment_research_workflow": "investment_research_workflow_skill_v0_1.md",
    "evidence_requirement_and_sufficiency": "evidence_requirement_and_sufficiency_skill_v0_1.md",
}

ROLE_SKILLS: dict[str, tuple[str, ...]] = {
    "planner": ("evidence_requirement_and_sufficiency", "investment_research_workflow"),
    "reflection": ("evidence_requirement_and_sufficiency",),
    "synthesis": ("investment_research_workflow",),
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
