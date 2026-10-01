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


def test_existing_fields_survive_omission_and_explicit_replacement_is_allowed():
    question = 'Definition unread (old retrieval failed).'
    prior = {'open_questions': [], 'subtasks': [task('terms', migrated_questions=[question])]}
    changed = {'task_id': 'terms', 'next_step': 'Read the newly located clause.'}
    assert merge_research_subtasks(prior, [changed])[0]['migrated_questions'] == [question]
    assert merge_research_subtasks(prior, prior['subtasks']) == prior['subtasks']
    assert merge_research_subtasks(prior, [{**changed, 'migrated_questions': []}])[0]['migrated_questions'] == []
    assert prior['subtasks'][0]['next_step'] == ''


def test_source_menu_and_readback_ids_are_navigation_not_prose_inference():
    from sec_agent.agent_runtime.research_working_state import observed_sources
    notebook = {"observations": [{"references": [], "content": [
        {"result_state": "source_bound_passage", "passage_id": "PASSAGE::a",
         "passage": "source_id: invented", "context_readbacks": [{"node_id": "CHUNK::next"}],
         "parent_readback": {"document_id": "DOC::parent"}},
        {"result_state": "retrieval_candidate", "company_section": "sources", "sources": [
            {"id": "SRC::menu", "preview": "SRC::not_observed"}]},
        {"result_state": "retrieval_candidate", "sources": [{"id": "SRC::untyped"}]}
    ]}]}
    assert observed_sources(notebook) == {"PASSAGE::a", "CHUNK::next", "DOC::parent", "SRC::menu"}


def update(request, note):
    return {"action": "native_tool_batch", "context_digest": request["context_digest"], "tool_calls": [{
        "name": "UpdateResearchStateAction", "id": f"note-{request['notebook']['model_turn_count']}",
        "args": {"action": "update_research_state", "context_digest": request["context_digest"],
            "reason_summary": "Update actual research progress within the original assignment.",
            "checkpoint": True, "working_state": note}}]}


@pytest.mark.parametrize("finish", ["resolve", "migrate", "capacity", "unknown"])
def test_current_questions_replace_old_wording_across_multiple_updates(finish):
    ports = _ToolPorts(); requests = []
    original = "Revenue and cancellation conditions have not yet been read."
    base = working_note(phase_status="working", findings=[], retain_source_ids=[],
        open_questions=[original], resolved_questions=[])
    partial = {**base, "open_questions": [], "subtasks": [
        {**task("issuer"), "status": "partial", "result": "Revenue read; terms remain.",
         "source_ids": ["E:DELL:Q1"], "next_step": "Read cancellation terms."}]}
    final = {**base, "open_questions": [], "subtasks": []}
    if finish == "resolve":
        final["resolved_questions"] = [{"question": original,
            "resolution": "Revenue read; cancellation terms remain an explicit limitation of this bounded investigation.",
            "source_ids": ["E:DELL:Q1"]}]
    elif finish == "migrate":
        final["subtasks"] = [{**partial["subtasks"][0], "migrated_questions": [original]}]
    elif finish == "capacity":
        final["open_questions"] = [f"new question {i}" for i in range(24)]
    else:
        final["resolved_questions"] = [{"question": original, "resolution": "Claimed read.",
            "source_ids": ["UNKNOWN"]}]
    notes = [base, partial, {**partial, "subtasks": []}, final]
    def turn(request):
        requests.append(request)
        if len(requests) == 1: return _batch(request, [_evidence_action()(request)])
        if len(requests) <= 5: return update(request, notes[len(requests)-2])
        return _handoff(request)
    result = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=turn, evidence_tool=ports.evidence, finance_tool=ports.finance,
        working_state_enabled=True)).compile().invoke({**_input(), "max_model_turns": 8, "max_tool_actions": 10})
    for index in (3, 4):
        assert requests[index]["task_context"]["research_working_state"]["open_questions"] == []
    current = result["research_working_state"]
    assert current["subtasks"][0]["status"] == "partial"
    assert current["open_questions"] == (final['open_questions'] if finish == 'capacity' else [])
    assert result["notebook"]["tool_action_count"] == 5
    assert base["open_questions"] == [original] and partial["open_questions"] == []
    if finish == 'unknown':
        assert current['reference_issues'][0]['submitted_id'] == 'UNKNOWN'


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


@pytest.mark.parametrize("mode", ["duplicate", "cycle", "missing_parent", "split_without_children", "completion_without_sources"])
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


@pytest.mark.parametrize("mode,code", [("unknown", "reference_issues"), ("unfinished", "working_state_subtasks_unfinished")])
def test_native_flags_unknown_subtask_sources_but_rejects_premature_phase_completion(mode, code):
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
    assert code in json.dumps(requests[-1]["tool_results"])
    if mode == 'unknown':
        assert result['research_working_state']['subtasks'][0]['source_ids'] == ['UNKNOWN']
        assert result['research_working_state']['reference_issues'][0]['status'] == 'unresolved'
        assert json.loads(requests[-1]['tool_results'][0]['content'])['accepted']
        return
    assert result["research_working_state"]["subtasks"] == [task("remaining")]
    receipt = json.loads(requests[-1]['tool_results'][0]['content'])['working_state_update']
    assert receipt['accepted'] is False and receipt['batch_applied'] is False
    assert receipt['state_unchanged'] is True
    assert receipt['pending_update_digest']
    assert 'edits' in receipt['next_action']


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
    assert '"node_id":"PIN"' in task_boundary_history(rows)[1].content
    note['retain_source_ids'] = ['PIN']
    assert task_boundary_history([*rows[:-2], *checkpoint_message(note)])[1] == rows[1]


def test_rejected_parent_update_keeps_migrations_atomic_before_followup_read():
    ports = _ToolPorts(); requests = []
    question = 'Review the remaining delivery evidence.'
    base = working_note(phase_status='working', findings=[], retain_source_ids=[],
        open_questions=[question], resolved_questions=[], subtasks=[])
    parent = {**task('parent'), 'status': 'in_progress', 'migrated_questions': [question]}
    child = task('child', parent_id='parent')
    rejected = {**base, 'open_questions': [], 'subtasks': [parent, child]}
    corrected = {**rejected, 'subtasks': [{**parent, 'status': 'split'}, child]}
    def turn(request):
        requests.append(request)
        if len(requests) == 1: return update(request, base)
        if len(requests) == 2: return update(request, rejected)
        if len(requests) == 3:
            receipt = json.loads(request['tool_results'][0]['content'])
            assert receipt['working_state_update']['batch_applied'] is False
            assert "'parent'" in receipt['feedback'][0]['message']
            assert "'child'" in receipt['feedback'][0]['message']
            current = request['task_context']['research_working_state']
            assert current['subtasks'] == [] and current['open_questions'] == [question]
            return update(request, corrected)
        if len(requests) == 4:
            current = request['task_context']['research_working_state']
            assert current['open_questions'] == []
            assert len(current['subtasks']) == 2
            return _batch(request, [_evidence_action()(request)])
        return _handoff(request)
    result = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=turn, evidence_tool=ports.evidence, finance_tool=ports.finance,
        working_state_enabled=True)).compile().invoke({**_input(), 'max_model_turns': 6})
    assert len(result['notebook']['observations']) == 1
    assert len(result['research_working_state']['subtasks']) == 2
    assert rejected['subtasks'][0]['status'] == 'in_progress'
