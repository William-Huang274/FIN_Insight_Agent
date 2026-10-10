"""Bounded specialist delegation contracts over native graphs and artifacts."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_serializer
from .professional_roles import ProfessionalAssignment


class ResearchSubtask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    professional: ProfessionalAssignment | None = None

    @model_serializer(mode='wrap')
    def preserve_legacy(self, handler):
        body = handler(self)
        if 'professional' not in self.model_fields_set:
            body.pop('professional', None)
        return body
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
    """Read a helper overview, selected analysis or saved originals on demand."""
    model_config = ConfigDict(extra="forbid")
    action: Literal["read_delegated_work"]
    context_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason_summary: str = Field(min_length=1, max_length=1000)
    subtask_id: str
    section: Literal["overview", "sources", "handoff", "analysis", "assignment", "workpaper", "source"] = "overview"
    source_observation_ref: str | None = Field(default=None,
        description="For source, copy an observation digest from the saved workpaper source catalog. Original receipt and source identity are retained.")
    source_ids: list[str] | None = None
    claim_ids: list[str] | None = None
    analysis_fields: list[str] | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=4, ge=1, le=12)

    @model_serializer(mode='wrap')
    def preserve_explicit_legacy_reads(self, handler):
        body = handler(self)
        for key in ('source_ids', 'claim_ids', 'analysis_fields', 'offset', 'limit'):
            if key not in self.model_fields_set:
                body.pop(key, None)
        return body


def delegated_artifact_view(child, action):
    """Reuse the dependency/Lead reader, preserving its exact source receipts."""
    from .specialist_handoff import DependencyReader
    request = action.model_dump(mode='json')
    request['task_id'] = request.pop('subtask_id')
    payload, observations = DependencyReader({request['task_id']: child})(request)
    def navigation(value):
        if isinstance(value, list):
            return [navigation(item) for item in value]
        if not isinstance(value, dict):
            return value
        if value.get('tool') == 'ReadDependencyWorkAction':
            args = dict(value['arguments'])
            args['subtask_id'] = args.pop('task_id')
            return {**value, 'tool': 'ReadDelegatedWorkAction', 'arguments': args}
        return {key: navigation(item) for key, item in value.items()}
    return navigation(payload), observations


DELEGATION_GUIDANCE = (
    "For a bounded survey task choose professional.profile=survey_analysis and provide purpose/source_hints; "
    "runtime gives it survey methods and clean authoring context, not this parent's financial method. "
    "You own this domain's research judgment and integration. Delegate only bounded subquestions whose independent "
    "context reduces duplicated work; specify what you stop doing and retain. Helpers self-check and return artifacts, "
    "not private conversations. ReadDelegatedWorkAction defaults to overview; use sources for a paged directory, "
    "handoff with source_ids for originals, and analysis with claim_ids or analysis_fields for selected reasoning. "
    "Explicit workpaper returns the complete artifact only when necessary. Use the saved readers "
    "before citing; helper prose is not evidence. Do not redo all helper reads/calculations routinely. Inspect task "
    "coverage, counterevidence and cross-paper period/subject/unit/denominator consistency. Before final submission "
    "self-check ALL numeric claims, calculations and associated headings/prose, report unresolved issues in task_note. "
    "A corrected citation alone is not a corrected conclusion. Never split the entire task into a renamed clone. "
    "You also own this domain's workpaper synthesis, summary and final delivery, not the whole investment report. "
    "Before drafting, organize the current domain judgments, adoption/rejection reasons, evidence, conditions, "
    "counterevidence and review/open-issue state. Use relevant domain methods for this judgment work; for drafting "
    "use the writer method's specialist-workpaper guidance and the domain's essential semantic constraints. "
    "Read methods through the available method tool when needed; do not assume automatic stage loading or a new "
    "context retains earlier state. Bounded writing helpers receive the relevant current state and evidence, "
    "not a blank brief or all prior conversations; you remain responsible for the integrated workpaper. "
    "Keep readable prose and structured claims consistent, with decisive conditions attached to each reusable "
    "judgment and exact source/calculation/version references supplied by the runtime. Footnotes alone cannot "
    "carry a condition that downstream consumers would otherwise lose. Repair all affected representations; "
    "do not rely on the parent Lead to reconstruct missing professional reasoning. New substantive judgments "
    "require the relevant method/evidence and domain review; unrelated business conclusions are not required."
)
