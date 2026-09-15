"""Lead issue dispositions; native convergence remains the only scheduler."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class IssueDisposition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finding_id: str
    paper_id: str
    disposition: Literal["repair", "disagree_with_sources", "unresolved"]
    rationale: str = Field(min_length=20, max_length=3000)
    requested_change: str = Field(default="", max_length=3000)
    expected_progress: str = Field(min_length=10, max_length=2000)
    citation_ids: list[str] = Field(default_factory=list, max_length=16)


class LeadIssueDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=20, max_length=4000)
    action: Literal["repair", "synthesize", "stop"]
    dispositions: list[IssueDisposition] = Field(default_factory=list, max_length=64)
    new_findings: list[IssueDisposition] = Field(default_factory=list, max_length=16,
        description="Material issues discovered by Lead in current papers, not duplicates of supplied findings. Use a new finding_id, responsible paper, exact problematic quote in rationale, targeted repair and expected progress; or unresolved and stop.")


def decision_errors(decision, feedback, paper_ids):
    expected = {(pid, f["finding_id"]) for pid, rows in feedback.items() for f in rows}
    actual = [(row.paper_id, row.finding_id) for row in decision.dispositions]
    errors = []
    if len(actual) != len(set(actual)) or set(actual) != expected:
        errors.append("Each original paper/finding pair must have exactly one disposition.")
    if any(row.paper_id not in paper_ids for row in decision.dispositions):
        errors.append("Unknown responsible paper.")
    discovered = [(row.paper_id, row.finding_id) for row in decision.new_findings]
    if len(discovered) != len(set(discovered)) or set(discovered) & expected:
        errors.append("New findings must be unique and distinct from supplied findings.")
    if any(row.paper_id not in paper_ids or row.disposition == "disagree_with_sources" for row in decision.new_findings):
        errors.append("A new issue must name an existing paper and require repair or remain unresolved.")
    rows = [*decision.dispositions, *decision.new_findings]
    repairs = any(row.disposition == "repair" for row in rows)
    unresolved = any(row.disposition == "unresolved" for row in rows)
    if any(row.disposition == "disagree_with_sources" and not row.citation_ids for row in rows):
        errors.append("A disagreement requires actual source citations; reviewer assertions are not authority.")
    if any(row.disposition == "repair" and not row.requested_change.strip() for row in rows):
        errors.append("Each repair needs a targeted change and expected progress.")
    if unresolved and decision.action != "stop" or repairs and decision.action == "synthesize":
        errors.append("Unresolved or pending repair work cannot be silently promoted to synthesis.")
    if decision.action == "repair" and not repairs:
        errors.append("Repair action needs at least one actual repair.")
    return errors
