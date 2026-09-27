"""Progressive author decomposition over native working-state updates, no API calls."""
from copy import deepcopy
import json

import pytest

from sec_agent.agent_runtime.research_working_state import (
    ResearchSubtask, ResearchWorkingState, merge_research_subtasks, UpdateResearchStateAction)
from sec_agent.agent_runtime.specialist_graph import (
    SpecialistAgenticDependencies, build_specialist_agentic_state_graph)
from test_specialist_graph import _input, _ToolPorts, _evidence_action
from test_specialist_tool_batch import _handoff, _batch
from test_research_working_state import working_note, source_messages
from test_research_context_checkpoint import checkpoint_message


def task(key, **updates):
    return ResearchSubtask(task_id=key, objective=key, status="pending", **updates).model_dump(mode="json")


def update(request, note):
    return {"action": "native_tool_batch", "context_digest": request["context_digest"], "tool_calls": [{
        "name": "UpdateResearchStateAction", "id": f"note-{request['notebook']['model_turn_count']}",
        "args": {"action": "update_research_state", "context_digest": request["context_digest"],
            "reason_summary": "Update actual research progress within the original assignment.",
            "checkpoint": True, "working_state": note}}]}


def test_native_partial_migration_split_and_recovery_preserve_progress_without_copying_old_questions():
    ports = _ToolPorts(); requests = []
    legacy = "Revenue, backlog and cancellation conditions have not been read."
    base = working_note(phase_status="working", findings=[], retain_source_ids=[], open_questions=[legacy])
    migrated = {**base, "open_questions": [], "subtasks": [
        {**task("issuer"), "status": "split", "migrated_questions": [legacy]},
        {**task("numbers", parent_id="issuer"), "status": "completed", "result": "Quarterly numbers read; not a deployment measure.", "source_ids": ["E:DELL:Q1"]},
        {**task("terms", parent_id="issuer"), "status": "partial", "result": "Backlog observed; definition and cancellation conditions remain.",
            "source_ids": ["E:DELL:Q1"], "next_step": "Read definition and cancellation clause."}]}
    split = {**base, "open_questions": [], "subtasks": [
        {**task("terms", parent_id="issuer"), "status": "split"},
        {**task("definition", parent_id="terms"), "status": "completed", "result": "Definition found in the fixture.", "source_ids": ["E:DELL:Q1"]},
        task("cancellation", parent_id="terms", next_step="Read the cancellation clause.")]}
    notes = [base, migrated, split]
    def turn(request):
        requests.append(request)
        if len(requests) == 1:
            return _batch(request, [_evidence_action()(request)])
        if len(requests) <= 4:
            return update(request, notes[len(requests)-2])
        return _handoff(request)
    def graph(model, recovery=None):
        return build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
            model_turn=model, evidence_tool=ports.evidence, finance_tool=ports.finance,
            working_state_enabled=True), recovery_state=recovery).compile()
    original_input = {**_input(), "max_model_turns": 10, "max_tool_actions": 15}
    first = graph(turn).invoke(original_input)
    state = first["research_working_state"]
    assert state["open_questions"] == [] and len(state["subtasks"]) == 5
    assert state["subtasks"][1]["status"] == "completed"  # Omitted during split, not forgotten.
    assert state["subtasks"][-1]["status"] == "pending"
    assert first["notebook"]["tool_action_count"] == 4  # One read + three notes, no delegated work.
    assert "migrated_questions" in requests[-1]["task_context"]["working_state_guidance"]
    assert requests[-1]["task_context"]["research_working_state"] == state
    assert notes[0]["open_questions"] == [legacy] and len(notes[2]["subtasks"]) == 3
    saved = deepcopy(first); continued = []
    def resume(request):
        continued.append(request)
        if len(continued) == 1:
            return update(request, {**base, "open_questions": [], "phase_status": "completed", "subtasks": [
                {**task("cancellation", parent_id="terms"), "status": "completed",
                    "result": "Clause read; conditional orders remain conditional.", "source_ids": ["E:DELL:Q1"]}]})
        return _handoff(request)
    final = graph(resume, first).invoke({**original_input, "run_invocation_id": "subtask-resume"})
    assert first == saved and len(ports.calls) == 1
    assert final["notebook"]["tool_action_count"] == first["notebook"]["tool_action_count"] + 1
    assert final["notebook"]["model_turn_count"] == first["notebook"]["model_turn_count"] + 2
    assert len(final["research_working_state"]["subtasks"]) == 5
    assert all(t["status"] in {"completed", "split"} for t in final["research_working_state"]["subtasks"])
    assert final["final_submission"] is None  # Completed checklist is not a workpaper.


@pytest.mark.parametrize("mode", ["duplicate", "cycle", "missing_parent", "split_without_children", "completion_without_sources", "invented_migration"])
def test_invalid_subtask_changes_are_atomic(mode):
    prior = {"open_questions": ["Existing question"], "subtasks": [task("saved")]}
    original = deepcopy(prior)
    updates = {
        "duplicate": [task("x"), task("x")],
        "cycle": [task("x", parent_id="y"), task("y", parent_id="x")],
        "missing_parent": [task("x", parent_id="missing")],
        "split_without_children": [{**task("x"), "status": "split"}],
        "completion_without_sources": [{**task("x"), "status": "completed", "result": "Finished"}],
        "invented_migration": [task("x", migrated_questions=["Invented question"])],
    }[mode]
    with pytest.raises(ValueError):
        merge_research_subtasks(prior, updates)
    assert prior == original


@pytest.mark.parametrize("mode,code", [("unknown", "working_state_unknown_source"), ("unfinished", "working_state_subtasks_unfinished")])
def test_native_rejects_unknown_subtask_sources_or_premature_phase_completion(mode, code):
    ports = _ToolPorts(); requests = []
    base = working_note(phase_status="working", findings=[], retain_source_ids=[], open_questions=[])
    def turn(request):
        requests.append(request)
        if len(requests) == 1:
            return update(request, {**base, "subtasks": [task("remaining")]})
        if len(requests) == 2:
            return update(request, {**base,
                "phase_status": "completed" if mode == "unfinished" else "working",
                "subtasks": [] if mode == "unfinished" else [task("remaining", source_ids=["UNKNOWN"])]})
        return _handoff(request)
    result = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=turn, evidence_tool=ports.evidence, finance_tool=ports.finance,
        working_state_enabled=True)).compile().invoke(_input())
    assert result["research_working_state"]["subtasks"] == [task("remaining")]
    assert code in json.dumps(requests[-1]["tool_results"])


def test_legacy_notes_and_native_schema_and_subtask_original_retention():
    from sec_agent.agent_runtime.deepseek_structured_agents import _native_function_schema
    from sec_agent.agent_runtime.model_context import task_boundary_history
    legacy = working_note(); legacy.pop("subtasks")
    assert ResearchWorkingState.model_validate(legacy).subtasks == []
    schema = json.dumps(_native_function_schema(UpdateResearchStateAction, runtime_context_binding=True))
    assert all(key in schema for key in ["subtasks", "parent_id", "migrated_questions", "partial", "split"])
    note = working_note(phase_status="working", findings=[], retain_source_ids=[], subtasks=[
        {**task("checked"), "status": "completed", "result": "Original checked", "source_ids": ["PIN"]}])
    rows = [*source_messages("PIN"), *source_messages("LATEST"), *checkpoint_message(note)]
    assert task_boundary_history(rows)[1] == rows[1]
