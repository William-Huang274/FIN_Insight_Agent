"""Research working state and factual progress signals over native notebooks."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_serializer


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


class ResearchSubtask(BaseModel):
    """Author-maintained progress within the existing assignment, not delegation."""
    model_config = ConfigDict(extra="forbid")
    task_id: str = Field(min_length=1, max_length=80, description="Stable local ID. Reuse it to update this task.")
    parent_id: str | None = Field(default=None, max_length=80)
    objective: str = Field(min_length=1, max_length=1000)
    status: Literal["pending", "in_progress", "partial", "completed", "blocked", "split"]
    result: str = Field(default="", max_length=2000,
        description="What actually finished, or the concrete blockage; retain period/unit/scope limits. Author assessment, not verified evidence.")
    next_step: str = Field(default="", max_length=1000, description="Only remaining work. Do not repeat already completed reading.")
    source_ids: list[str] = Field(default_factory=list, max_length=32,
        description="Required and nonempty when status=completed: copy the exact observed IDs supporting this task's result, even if also listed in findings. Otherwise include the sources already read; navigation IDs do not prove the source was read.")
    migrated_questions: list[str] = Field(default_factory=list,
        description="Optional legacy question history, not current pending status. Omit to keep the existing value; current remaining work belongs in result/next_step.")


class ResearchSubtaskUpdate(ResearchSubtask):
    objective: str | None = Field(default=None, min_length=1, max_length=1000)
    status: Literal["pending", "in_progress", "partial", "completed", "blocked", "split"] | None = None


class ResearchWorkingState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_subtask: str = Field(min_length=1, max_length=2000)
    phase_status: Literal["working", "completed"]
    findings: list[ObservedFinding] = Field(default_factory=list)
    rejected_interpretations: list[str] = Field(default_factory=list,
        description="Current author judgments; replaces the prior list. Merge or revise obsolete judgments yourself. History stays archived, not appended here.")
    open_questions: list[str] = Field(default_factory=list,
        description="Current unresolved questions; replaces the prior list. Preserve meaningful remaining work, not stale unread wording.")
    resolved_questions: list[ResolvedResearchQuestion] = Field(default_factory=list)
    subtasks: list[ResearchSubtaskUpdate] = Field(default_factory=list,
        description="Changed/new subtask records only; host upserts by task_id and returns the full current list. Omitted tasks stay unchanged. Split progressively using parent_id and status=split; update progress yourself after meaningful research. No new worker, scope or budget.")
    next_step: str = Field(min_length=1, max_length=2000)
    last_task_detail: str = Field(min_length=1, max_length=4000,
        description="What was just investigated, actual outcome, unresolved issues and the precise continuation; not hidden reasoning.")
    retain_source_ids: list[str] = Field(default_factory=list,
        description="Exact observed source IDs whose original context must remain together for current comparisons. Findings and completed tasks do not permanently pin their originals.")
    reference_issues: list[dict[str, Any]] = Field(default_factory=list,
        description="Runtime-recomputed unresolved citation markers. Saving author progress does not verify these references.")

    @model_serializer(mode='wrap')
    def preserve_archived_note(self, handler):
        body = handler(self)
        if 'reference_issues' not in self.model_fields_set:
            body.pop('reference_issues', None)
        return body


class ResearchStateEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(pattern=r"^/", description="JSON Pointer to a field in the saved pending working_state, e.g. /subtasks/0/parent_id. Existing values are replaced; an omitted object field may be supplied.")
    value: Any


class UpdateResearchStateAction(BaseModel):
    """Replace current working state or repair a saved rejected draft. Alone in a tool batch. Older versions and recoverable results remain archived; this is not research completion."""
    model_config = ConfigDict(extra="forbid")
    action: Literal["update_research_state"]
    context_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason_summary: str = Field(min_length=1, max_length=1000)
    working_state: ResearchWorkingState | None = None
    pending_update_digest: str | None = Field(default=None, description="To repair a rejected draft, copy its returned digest, omit working_state and provide edits. All checks run again.")
    edits: list[ResearchStateEdit] = Field(default_factory=list)
    release_source_ids: list[str] = Field(default_factory=list, description="Optional: remove already-read document/paragraph/company results from the next working context, retaining request history and exact recovery. May be sent alone without working_state or edits. Copy observed IDs. Later reads are visible again; archives are never deleted.")
    checkpoint: bool = Field(default=False, description="Mark a useful compaction boundary. Accepted current state supersedes old notes; current pinned sources and latest reads stay visible, older recoverable results become archive entries. No task or budget reset.")

    @model_serializer(mode='wrap')
    def preserve_archived_action(self, handler):
        body = handler(self)
        if 'release_source_ids' not in self.model_fields_set:
            body.pop('release_source_ids', None)
        return body


WORKING_STATE_GUIDANCE = (
    "Maintain one current working state after meaningful research, not after every tool call. "
    "State your findings and current interpretation, decisive remaining questions and next action. "
    "A new working_state replaces the previous narrative and lists; consolidate or revise obsolete wording. "
    "Originals and prior versions stay in the native archive. Notes are author assessments, not evidence. "
    "Use stable-ID subtasks when helpful; submit changed records only. Omitted fields of existing tasks "
    "remain unchanged; explicit null clears an optional field. migrated_questions is optional legacy history. "
    "Pin only sources currently needed together in retain_source_ids; other originals have exact recovery "
    "routes and must be recovered when necessary to verify a quote or calculation. Preserve source, period, "
    "unit and scope in findings. "
    "Use release_source_ids alone to dismiss no-longer-needed results without rewriting a note. "
    "Unique observed identifier typos are repaired with a receipt; ambiguous or unknown references are marked "
    "in reference_issues without rejecting the note. These markers are not valid evidence. "
    "At a useful research boundary or a context-size reminder, set checkpoint=true "
    "to archive completed history, keeping phase_status=working if unfinished. A rejected update returns a "
    "pending_update_digest: repair only affected fields with edits or submit a replacement draft. "
    "Saving a note does not complete research or reset budget. Continue investigating what can change the answer."
)


def accepted_context_checkpoint(state):
    """Host state or an exact legacy success receipt, never a model proposal."""
    import json
    accepted = state.get("research_context_checkpoint_accepted", False)
    for result in state.get("tool_results", []):
        if result.get("name") != "UpdateResearchStateAction" or result.get("status") == "error":
            continue
        try:
            receipt = json.loads(result.get("content", ""))
        except (ValueError, TypeError):
            continue
        if isinstance(receipt, dict) and receipt.get("accepted") and receipt.get("working_state") == state.get("research_working_state"):
            accepted = receipt.get("checkpoint") is True
    return accepted


def merge_research_subtasks(prior, updates):
    """Deterministic upsert only. The author owns decomposition and conclusions."""
    from copy import deepcopy
    tasks = {t["task_id"]: deepcopy(t) for t in prior.get("subtasks", [])}
    if len({t["task_id"] for t in updates}) != len(updates):
        raise ValueError("Duplicate subtask IDs in one update; submit each changed task once.")
    for update in updates:
        old = tasks.get(update["task_id"], {})
        task = {**deepcopy(old), **deepcopy(update)}
        task = ResearchSubtask.model_validate(task).model_dump(mode="json")
        tasks[task["task_id"]] = task
    for task in tasks.values():
        seen = {task["task_id"]}
        parent = task["parent_id"]
        while parent is not None:
            if parent not in tasks or parent in seen:
                raise ValueError("Subtask parent must exist and the hierarchy must be acyclic.")
            seen.add(parent)
            parent = tasks[parent]["parent_id"]
        children = [t for t in tasks.values() if t["parent_id"] == task["task_id"]]
        if bool(children) != (task["status"] == "split"):
            raise ValueError(f"Subtask {task['task_id']!r} has status {task['status']!r} and children "
                f"{[t['task_id'] for t in children]!r}. A split task needs children; "
                "a task with children must be marked split. The entire update was rejected.")
        if task["status"] == "completed" and (not task["result"].strip() or not task["source_ids"]):
            raise ValueError(f"Completed subtask {task['task_id']!r} needs a nonempty result and source_ids supporting that result; copy the observed IDs even if already in findings. Status is not verification.")
    return list(tasks.values())


def observed_sources(notebook):
    """Working notes may retain actual navigation IDs, without citation authority.

    Only structured result metadata counts, never IDs embedded in source prose.
    Final claims continue to use the separate evidence-reference validator.
    """
    import json
    refs = {r["ref_id"] for o in notebook.get("observations", []) for r in o.get("references", [])}
    def collect(row):
        if isinstance(row, dict):
            refs.update(row[k] for k in ('document_id', 'parent_document_id', 'node_id',
                'parent_section_id', 'source_id', 'entity_id', 'candidate_id', 'passage_id', 'numeric_fact_id')
                if isinstance(row.get(k), str) and row[k])
    for observation in notebook.get('observations', []):
        for item in observation.get('content', []):
            if not isinstance(item, dict):
                continue
            if item.get('result_state') in {'retrieval_candidate', 'source_bound_passage'}:
                collect(item)
                # Published reader routes and company source menus are observed
                # navigation too; source prose itself is never searched for IDs.
                collect(item.get('parent_readback'))
                for route in item.get('context_readbacks', []):
                    collect(route)
                if item.get('company_section') == 'sources':
                    for source in item.get('sources', []):
                        if isinstance(source, dict) and isinstance(source.get('id'), str):
                            refs.add(source['id'])
                metadata = item.get('metadata', {})
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except (ValueError, TypeError):
                        metadata = {}
                collect(metadata)
            if item.get('result_state') == 'numeric_fact':
                collect(item)
                for operand in (item.get('formula_trace') or {}).get('inputs', []):
                    collect(operand)
    return refs


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
