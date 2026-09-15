"""Public task handoff projected from native state; no new execution authority."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .research_graph_contracts import canonical_sha256


class NoteModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskTarget(NoteModel):
    claim_ids: list[str] = Field(default_factory=list, max_length=64)
    fields: list[Literal["thesis", "mechanism", "narrative_markdown", "claims", "counterevidence",
                         "what_would_change", "open_gaps"]] = Field(default_factory=list, max_length=7)


class TaskCoverage(TaskTarget):
    criterion: str = Field(min_length=1, max_length=2000, description="Exact assignment success criterion or runtime required_source_checks criterion.")
    status: Literal["completed", "partial", "not_completed", "not_applicable"]
    explanation: str = Field(min_length=1, max_length=2000)


class TaskIssue(TaskTarget):
    issue_id: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    next_action: str = Field(min_length=1, max_length=2000)
    suggested_owner: Literal["author", "lead", "data_tool", "reviewer", "user"]


class AuthorTaskNote(NoteModel):
    """Explicit public assessment, not reasoning history or runtime status."""
    summary: str = Field(min_length=1, max_length=1500)
    coverage: list[TaskCoverage] = Field(default_factory=list, max_length=24)
    issues: list[TaskIssue] = Field(default_factory=list, max_length=16)
    changes: str = Field(default="", max_length=2000, description="Actual changes and remaining affected prose; no automatic approval.")
    finding_responses: list["AuthorFindingResponse"] | None = Field(default=None, exclude_if=lambda v: v is None,
        description="During assigned revision, answer every runtime finding ID once. These are author assertions, not independent closure.")


class AuthorFindingResponse(NoteModel):
    finding_id: str = Field(min_length=1, max_length=240)
    disposition: Literal["corrected", "disagreed_with_sources", "unresolved"]
    explanation: str = Field(min_length=20, max_length=2500)


AuthorTaskNote.model_rebuild()


class ChangeSpan(NoteModel):
    before: tuple[int, int]
    after: tuple[int, int]


class ChangeLocation(NoteModel):
    path: Literal["/thesis", "/mechanism", "/narrative_markdown", "/counterevidence", "/what_would_change", "/open_gaps", "/task_note"]
    before_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    after_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    spans: list[ChangeSpan] = Field(default_factory=list)


class RuntimeChange(NoteModel):
    baseline_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    current_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    changed_claim_ids: list[str]
    locations: list[ChangeLocation]
    semantic_status: Literal["not_independently_verified"]


class TaskOutcome(NoteModel):
    schema_version: Literal["task_outcome_v1"] = "task_outcome_v1"
    task_id: str
    run_id: str | None = None
    attempt_id: str | None = None
    execution_status: Literal["submitted", "needs_attention", "error", "cancelled", "incomplete"]
    phase: str
    stop_reason: str | None = None
    artifact_digest: str | None = None
    artifact_status: Literal["submitted", "candidate", "none"]
    review_status: Literal["not_assessed_in_this_record"] = "not_assessed_in_this_record"
    success_criteria: list[str] = Field(default_factory=list)
    author_note: AuthorTaskNote | None = None
    author_note_status: Literal["reported_not_verified", "missing", "invalid"]
    navigation_issues: list[str] = Field(default_factory=list)
    open_gaps: list[str] = Field(default_factory=list)
    validation_locations: list[list[str | int]] = Field(default_factory=list)
    cost_status: Literal["see_run_usage_ledger"] = "see_run_usage_ledger"
    runtime_changes: list[RuntimeChange] = Field(default_factory=list)


def task_outcome(state, *, assignment=None, error_type=None, cancelled=False):
    """Use terminal facts even when an author claims success or cannot speak."""
    assignment = assignment or (state.get("task_context") or {}).get("assignment") or {}
    phase = state.get("phase", "execution_error" if error_type else "unknown")
    status = ("cancelled" if cancelled else "error" if error_type else "submitted" if phase == "specialist_submission_accepted"
              else "needs_attention" if phase == "specialist_human_review_handoff_emitted"
              else "cancelled" if phase == "cancelled" else "incomplete")
    attempt = state.get("last_submission_attempt") or {}
    artifact = state.get("final_submission") if status == "submitted" else attempt.get("arguments")
    artifact = artifact if isinstance(artifact, dict) else None
    raw_note = artifact.get("task_note") if artifact else None
    records = state.get("notebook", {}).get("model_turn_records", [])
    last_action = records[-1].get("action", {}) if records else {}
    trigger = state.get("review_trigger") or (state.get("human_review_handoff") or {}).get("trigger")
    if status != "submitted" and trigger == "model_request":
        if last_action.get("action") == "native_tool_batch":
            last_action = next((call.get("args", {}) for call in last_action.get("tool_calls", [])
                if call.get("name") == "RequestHumanReviewAction"), {})
        if last_action.get("action") == "request_human_review":
            raw_note = last_action.get("task_note")
    note, note_status = None, "missing"
    if raw_note is not None:
        try:
            note = AuthorTaskNote.model_validate(raw_note)
            note_status = "reported_not_verified"
        except ValueError:
            note_status = "invalid"
    criteria = list(assignment.get("success_criteria", []))
    criteria.extend(c["criterion"] for c in state.get("required_source_checks", []) if c["criterion"] not in criteria)
    navigation = []
    if note:
        raw_claims = (artifact or {}).get("claims")
        claims = {c.get("claim_id") for c in raw_claims if isinstance(c, dict) and isinstance(c.get("claim_id"), str)} if isinstance(raw_claims, list) else set()
        if artifact is None and any(t.fields or t.claim_ids for t in [*note.coverage, *note.issues]):
            navigation.append("target_artifact_missing")
        for target in [*note.coverage, *note.issues]:
            navigation.extend("unknown_claim_id:" + c for c in target.claim_ids if c not in claims)
        covered = [c.criterion for c in note.coverage]
        navigation.extend("unmatched_criterion:" + c for c in covered if c not in criteria)
        navigation.extend("missing_criterion_assessment:" + c for c in criteria if c not in covered)
        if len(covered) != len(set(covered)):
            navigation.append("duplicate_criterion_assessment")
    gaps = (artifact or {}).get("open_gaps")
    return TaskOutcome(task_id=assignment.get("task_id") or state.get("task", {}).get("task_id", "unknown"),
        run_id=state.get("run_id"), attempt_id=state.get("run_invocation_id"),
        execution_status=status, phase=phase,
        stop_reason=error_type or state.get("review_reason") or (state.get("human_review_handoff") or {}).get("reason_code"),
        artifact_digest=canonical_sha256(artifact) if artifact else None,
        artifact_status="submitted" if status == "submitted" and artifact else "candidate" if artifact else "none",
        success_criteria=criteria, author_note=note, author_note_status=note_status,
        navigation_issues=navigation, open_gaps=[s for s in gaps if isinstance(s, str)] if isinstance(gaps, (list, tuple)) else [],
        runtime_changes=[{k: row[k] for k in ("baseline_digest", "current_digest", "changed_claim_ids", "locations", "semantic_status") if k in row}
                         for row in state.get("workpaper_change_history", []) if row.get("attempt_id", state.get("run_invocation_id")) == state.get("run_invocation_id")],
        validation_locations=[row["location"] for row in attempt.get("validation_issues", [])
            if isinstance(row, dict) and isinstance(row.get("location"), list)
            and all(isinstance(part, (str, int)) and not isinstance(part, bool) for part in row["location"])]).model_dump(mode="json")


def public_task_outcome(value):
    """Fail closed on unexpected nested fields, never publish a raw checkpoint."""
    try:
        return TaskOutcome.model_validate(value).model_dump(mode="json")
    except (ValueError, TypeError):
        return None
