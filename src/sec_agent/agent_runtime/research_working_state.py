"""Research working state and factual progress signals over native notebooks."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ObservedFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finding: str = Field(min_length=1, max_length=3000)
    source_ids: list[str] = Field(min_length=1, max_length=32)
    limitations: str = Field(min_length=1, max_length=1500,
        description="Preserve subject, period, unit, denominator, revision and actual/guidance limits; do not generalize beyond the source.")


class ResolvedResearchQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, description="Copy the previous open question exactly.")
    resolution: str = Field(min_length=1, description="Actual disposition including remaining limits; not independent verification.")
    source_ids: list[str] = Field(min_length=1, max_length=32)


class ResearchWorkingState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_subtask: str = Field(min_length=1, max_length=2000)
    phase_status: Literal["working", "completed"]
    findings: list[ObservedFinding] = Field(default_factory=list, max_length=32)
    rejected_interpretations: list[str] = Field(default_factory=list, max_length=24)
    open_questions: list[str] = Field(default_factory=list, max_length=24)
    resolved_questions: list[ResolvedResearchQuestion] = Field(default_factory=list, max_length=24)
    next_step: str = Field(min_length=1, max_length=2000)
    last_task_detail: str = Field(min_length=1, max_length=4000,
        description="What was just investigated, actual outcome, unresolved issues and the precise continuation; not hidden reasoning.")
    retain_source_ids: list[str] = Field(default_factory=list, max_length=128,
        description="Exact observed source IDs whose original context must remain together for current comparisons. All findings' sources are also retained automatically.")


class UpdateResearchStateAction(BaseModel):
    """Record current evidence/invalidated interpretations/gaps and next work. Alone in a tool batch. A completed phase permits deterministic clearing of unneeded older source bodies only; original records remain readable."""
    model_config = ConfigDict(extra="forbid")
    action: Literal["update_research_state"]
    context_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason_summary: str = Field(min_length=1, max_length=1000)
    working_state: ResearchWorkingState
    checkpoint: bool = Field(default=False, description="Self-compress the current research state at runtime's context threshold. Keep phase_status working if unfinished. Original cited evidence, current comparison sources and latest read batch remain exact; only older recoverable source bodies may leave the request.")


WORKING_STATE_GUIDANCE = (
    "Maintain the current research state with UpdateResearchStateAction after meaningful findings, a rejected "
    "interpretation or completing a subquestion. Preserve observed findings and their exact source/period/unit/"
    "denominator limits, rejected interpretations, remaining evidence, next step and last task detail. "
    "This is a public working note, not hidden reasoning or evidence. Keep sources needed together in "
    "retain_source_ids. New source bodies stay visible during the active phase; only a completed phase can "
    "release older non-retained bodies, except an explicit within-phase checkpoint requested by runtime. "
    "At that checkpoint, keep phase_status working for unfinished work and set checkpoint=true. Preserve the "
    "overall research logic, every used numerical/metric claim with its source and qualifiers, rejected "
    "interpretations, all unresolved issues, latest task details and exact next action. Do not resolve an issue "
    "just to shorten the note. Original recorded findings and calculations remain protected independently. "
    "Updating a note does not prove progress or reset runtime warnings. "
    "If warned about repeated reads, inspect actual results and next-block/search options, explain a changed "
    "approach or truthful blockage; do not repeat a past intention as though the source confirmed it."
)


def observed_sources(notebook):
    return {r["ref_id"] for o in notebook.get("observations", []) for r in o.get("references", [])}


def progress_after_tools(before, after, previous, *, has_reads):
    """New native observations, not a model's claim of progress or altered prose."""
    if not has_reads:
        return dict(previous or {})
    import json
    def signatures(notebook):
        return {json.dumps({k: o.get(k) for k in ("kind", "references", "content")}, sort_keys=True, ensure_ascii=False)
            for o in notebook.get("observations", []) if o.get("status") == "success"}
    old = signatures(before)
    new = signatures(after) - old
    repeated = 0 if new else (previous or {}).get("consecutive_no_new_observations", 0) + 1
    return {"consecutive_no_new_observations": repeated, "new_observation_count": len(new),
        "status": "warn" if repeated >= 2 else "observing",
        "notice": ("Repeated reads produced no new observations. This is an execution signal, not proof your analysis is wrong. "
            "Use retained results, follow actual navigation or change the search/analysis. Update what remains missing. "
            "Continued non-progress will consult the Research Lead without increasing your budget or resetting counts."
            if repeated >= 2 else "Observation novelty is not financial correctness; maintain your actual research state.")}
