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
    migrated_questions: list[str] = Field(default_factory=list, max_length=24,
        description="One-time mapping from exact legacy open questions. Historical identity, NOT current unread/pending status. Omit when updating an existing task to retain its old migrations unchanged; never paraphrase the keys. Split their entire scope into children, including unfinished parts.")


class ResearchWorkingState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_subtask: str = Field(min_length=1, max_length=2000)
    phase_status: Literal["working", "completed"]
    findings: list[ObservedFinding] = Field(default_factory=list, max_length=32)
    rejected_interpretations: list[str] = Field(default_factory=list, max_length=24,
        description="Rejected author interpretations, not evidence. At explicit checkpoints the host retains all prior entries verbatim and reports inherited entries; omission or rephrasing cannot erase an old constraint. Reuse exact entries to avoid duplicates.")
    open_questions: list[str] = Field(default_factory=list, max_length=24,
        description="New or still-open questions. The host also retains any prior question not explicitly resolved or migrated, and reports inherited entries. Omission does not resolve a question; old unread wording remains pending author review, not a new factual assertion.")
    resolved_questions: list[ResolvedResearchQuestion] = Field(default_factory=list, max_length=24)
    subtasks: list[ResearchSubtask] = Field(default_factory=list, max_length=64,
        description="Changed/new subtask records only; host upserts by task_id and returns the full current list. Omitted tasks stay unchanged. Split progressively using parent_id and status=split; update progress yourself after meaningful research. No new worker, scope or budget.")
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
    "At explicit checkpoints prior rejected interpretations are retained by the host even if omitted or "
    "rephrased; the accepted result reports inherited entries. This does not resolve open questions or "
    "validate interpretations. Prefer a small set of stable-ID subtasks within the existing assignment. "
    "Split a broad task progressively only when needed: update the parent to split and add children with parent_id. "
    "After reading, calculation or analysis, update the SAME child to partial/completed/blocked with actual result, "
    "source_ids and only the remaining next_step. Do not call unread work completed, keep obsolete 'not read' claims "
    "beside new findings, or append a paraphrased duplicate task. Completed means your scoped work is done, not "
    "independent verification. Submit only changed subtask records; the host preserves unchanged ones and returns "
    "the merged list. No need to write a note after every tool call, and planning is not new evidence. "
    "Migrate legacy compound open_questions once: attach their exact text to migrated_questions on a parent/task, "
    "represent all their scope in the task/children, then remove them from open_questions. This mapping preserves "
    "history without claiming the whole question resolved; do not carry obsolete unread wording as a live task. "
    "For legacy questions not migrated or explicitly resolved, the host preserves their exact text and reports "
    "inherited_open_questions; you need not re-copy all of them at every checkpoint. This is a pending-review "
    "carryover, not confirmation that an old unread statement remains true. Update the relevant subtask and "
    "explicitly migrate or resolve stale questions after reading; do not rewrite the entire note just to copy them. "
    "After an accepted checkpoint the latest working state supersedes older notes in the request, while "
    "the native history remains intact. Saved observation recovery routes return the exact recorded result "
    "without a new source query. Follow the supplied arguments when that original is needed; a partial "
    "catalog projection is not the full search result and cannot prove that another source is absent. "
    "Updating a note does not prove progress or reset runtime warnings. "
    "If warned about repeated reads, inspect actual results and next-block/search options, explain a changed "
    "approach or truthful blockage; do not repeat a past intention as though the source confirmed it."
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
    known_questions = set(prior.get("open_questions", [])) | {
        q for t in tasks.values() for q in t.get("migrated_questions", [])}
    for update in updates:
        task = deepcopy(update)
        old = tasks.get(task["task_id"], {})
        unknown = set(task["migrated_questions"]) - known_questions
        if unknown:
            raise ValueError("Migration must identify existing open questions exactly: " + str(sorted(unknown))
                + f". Task {task['task_id']!r} already retains these exact migrations: "
                + str(old.get('migrated_questions', []))
                + ". For an existing task, omit migrated_questions to retain those migrations unchanged; "
                "update its result/next_step instead of paraphrasing migration keys. "
                "No part of this update was applied; the previous accepted state remains current.")
        task["migrated_questions"] = list(dict.fromkeys([
            *old.get("migrated_questions", []), *task["migrated_questions"]]))
        tasks[task["task_id"]] = task
    if len(tasks) > 64:
        raise ValueError("At most 64 subtasks per working state; update existing IDs rather than append duplicates.")
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
