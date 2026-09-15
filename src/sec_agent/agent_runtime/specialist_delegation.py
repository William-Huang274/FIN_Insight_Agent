"""Bounded specialist delegation contracts over native graphs and artifacts."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ResearchSubtask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subtask_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,60}$")
    objective: str = Field(min_length=20, max_length=4000)
    success_criteria: list[str] = Field(min_length=1, max_length=12)
    relieved_work: str = Field(min_length=20, max_length=2000,
        description="Specific work the parent will stop doing itself. Never transfer the entire parent assignment unchanged.")
    retained_parent_work: str = Field(min_length=20, max_length=2000,
        description="Integration, competing explanations and decisions retained by the parent after this helper returns.")
    source_hints: list[str] = Field(default_factory=list, max_length=16,
        description="Actual available document/source IDs or explicit search questions, not fabricated evidence or full source bodies.")


class DelegateSubtasksAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["delegate_subtasks"]
    context_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason_summary: str = Field(min_length=1, max_length=1000)
    tasks: list[ResearchSubtask] = Field(min_length=1, max_length=4,
        description="Independent, bounded subquestions. Helpers have separate contexts and cannot delegate further. Avoid redundant investigations.")


class ReadDelegatedWorkAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["read_delegated_work"]
    context_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason_summary: str = Field(min_length=1, max_length=1000)
    subtask_id: str
    section: Literal["workpaper", "source"] = "workpaper"
    source_observation_ref: str | None = Field(default=None,
        description="For source, copy an observation digest from the saved workpaper source catalog. Original receipt and source identity are retained.")


DELEGATION_GUIDANCE = (
    "You own this domain's research judgment and integration. Delegate only bounded subquestions whose independent "
    "context reduces duplicated work; specify what you stop doing and retain. Helpers self-check and return artifacts, "
    "not private conversations. Use ReadDelegatedWorkAction to read needed papers and original source observations "
    "before citing; helper prose is not evidence. Do not redo all helper reads/calculations routinely. Inspect task "
    "coverage, counterevidence and cross-paper period/subject/unit/denominator consistency. Before final submission "
    "self-check ALL numeric claims, calculations and associated headings/prose, report unresolved issues in task_note. "
    "A corrected citation alone is not a corrected conclusion. Never split the entire task into a renamed clone."
)
