"""Task handoff facts, public projection and native Lead consumption; no paid calls."""
from copy import deepcopy
import json

from langgraph.checkpoint.memory import InMemorySaver
from sec_agent.agent_runtime.task_outcome import task_outcome
from sec_agent.agent_runtime.specialist_graph import SubmitWorkpaperAction
from apps.workbench.backend.api.v1.report_sessions import public_event, public_state
from test_lead_research_graph import _graph, _task, _worker_result, _call, _stop
from test_workpaper_review_graph import _seed


def result_fixture():
    assignment = _task()
    state = _worker_result(assignment, _seed())
    state['run_invocation_id'] = 'attempt:original'
    claim = state['final_submission']['claims'][0]['claim_id']
    state['final_submission']['task_note'] = {'summary': 'Author reports partial research, awaiting period verification.',
        'coverage': [{'criterion': assignment['success_criteria'][0], 'status': 'partial',
            'explanation': 'Original sources read, but period interpretation remains open.', 'claim_ids': [claim], 'fields': ['narrative_markdown']}],
        'issues': [{'issue_id': 'scope-1', 'description': 'Check period scope in the associated paragraph.',
            'claim_ids': [claim], 'fields': ['narrative_markdown'], 'next_action': 'Recheck the original period before editing.',
            'suggested_owner': 'author'}], 'changes': 'No revised financial conclusion claimed.'}
    return state, assignment


def test_submitted_partial_and_failure_are_distinct_and_private_state_is_not_exposed():
    state, assignment = result_fixture()
    note = task_outcome(state, assignment=assignment)
    assert note['execution_status'] == 'submitted'
    assert note['author_note']['coverage'][0]['status'] == 'partial'
    assert note['review_status'] == 'not_assessed_in_this_record'
    SubmitWorkpaperAction.model_validate_json(json.dumps(state['final_submission']))
    rejected = deepcopy(state)
    rejected.update(phase='specialist_human_review_handoff_emitted', review_reason='validation_failed',
        final_submission=None, last_submission_attempt={'arguments': state['final_submission'],
            'validation_issues': [{'location': ['claims', 0, 'citation_quotes'], 'private': 'PRIVATE'}]},
        messages=[{'reasoning_content': 'PRIVATE'}])
    rejected['last_submission_attempt']['arguments']['task_note']['coverage'][0]['status'] = 'completed'
    failure = task_outcome(rejected, assignment=assignment)
    assert failure['execution_status'] == 'needs_attention' and failure['artifact_status'] == 'candidate'
    assert failure['validation_locations'] == [['claims', 0, 'citation_quotes']]
    event = public_event({'kind': 'task', 'task_id': assignment['task_id'], 'task_outcome': failure})
    assert event['task_outcome'] == failure and 'PRIVATE' not in json.dumps(event)
    polluted = {**failure, 'private_reasoning': 'PRIVATE'}
    assert 'task_outcome' not in public_event({'kind': 'task', 'task_id': assignment['task_id'], 'task_outcome': polluted})
    assert 'task_outcome' not in public_event({'kind': 'task', 'task_id': 'wrong-task', 'task_outcome': failure})


def test_revision_changes_binding_retains_original_and_reports_invalid_navigation():
    state, assignment = result_fixture()
    original = task_outcome(state, assignment=assignment)
    revised = deepcopy(state)
    revised['run_invocation_id'] = 'attempt:revision'
    revised['final_submission']['narrative_markdown'] += '\nSynthetic revised paragraph.'
    revised['final_submission']['task_note']['issues'][0]['claim_ids'] = ['nonexistent']
    changed = task_outcome(revised, assignment=assignment)
    assert changed['artifact_digest'] != original['artifact_digest']
    assert changed['attempt_id'] != original['attempt_id']
    assert 'unknown_claim_id:nonexistent' in changed['navigation_issues']
    assert task_outcome(state, assignment=assignment) == original
    history = public_state({'values': {'research_attempt_history': [
        {'run_id': 'first', 'outcomes': [{'task_id': assignment['task_id'], 'task_outcome': original}]},
        {'run_id': 'second', 'outcomes': [{'task_id': assignment['task_id'], 'task_outcome': changed}]}]}})['task_outcome_history']
    assert [r['task_outcome'] for r in history] == [original, changed]


def test_error_cancelled_and_legacy_do_not_invent_author_completion():
    state, assignment = result_fixture()
    del state['final_submission']['task_note']
    assert task_outcome(state, assignment=assignment)['author_note_status'] == 'missing'
    for cancelled, status in [(False, 'error'), (True, 'cancelled')]:
        row = task_outcome({}, assignment=assignment, error_type='RuntimeError', cancelled=cancelled)
        assert row['execution_status'] == status and row['artifact_status'] == 'none'
        assert row['author_note'] is None and row['cost_status'] == 'see_run_usage_ledger'


def test_malformed_rejected_artifact_cannot_break_runtime_failure_summary():
    state, assignment = result_fixture()
    candidate = state['final_submission']
    candidate['claims'] = None
    candidate['open_gaps'] = 42
    state.update(phase='specialist_human_review_handoff_emitted', final_submission=None,
        last_submission_attempt={'arguments': candidate, 'validation_issues': [{'location': ['claims', {}]}]})
    outcome = task_outcome(state, assignment=assignment)
    assert outcome['execution_status'] == 'needs_attention'
    assert outcome['navigation_issues'] and outcome['open_gaps'] == []
    assert outcome['validation_locations'] == []


def test_explicit_partial_handoff_preserves_author_note_without_inventing_artifact():
    state, assignment = result_fixture()
    note = state['final_submission']['task_note']
    state.update(phase='specialist_human_review_handoff_emitted', final_submission=None, last_submission_attempt=None,
        review_trigger='model_request')
    state['notebook']['model_turn_records'] = [{'action': {'action': 'request_human_review', 'task_note': note}}]
    result = task_outcome(state, assignment=assignment)
    assert result['author_note']['coverage'][0]['status'] == 'partial'
    assert result['artifact_status'] == 'none' and 'target_artifact_missing' in result['navigation_issues']


def test_native_lead_receives_same_outcome_saved_in_checkpoint():
    state, assignment = result_fixture()
    requests = []
    def model(request):
        requests.append(request)
        if len(requests) == 1:
            return _call(request, 'DelegateResearchTasksAction', tasks=[assignment])
        returned = json.loads(request['tool_results'][0]['content'])['task_results'][0]
        assert 'task_note' not in returned['workpaper']  # no duplicate long author note in Lead input
        assert returned['task_outcome'] == task_outcome(state, assignment=assignment)
        assert returned['task_outcome']['author_note']['issues'][0]['issue_id'] == 'scope-1'
        return _stop(request, ready=True)
    graph, value = _graph(model, lambda *_: deepcopy(state), require_all_branches=False)
    graph = graph.builder.compile(checkpointer=InMemorySaver())
    config = {'configurable': {'thread_id': 'task-outcome-native'}}
    result = graph.invoke(value.model_dump(mode='json'), config)
    assert len(requests) == 2
    assert graph.get_state(config).values['task_results'][0]['task_outcome'] == result['task_results'][0]['task_outcome']


def test_native_specialist_partial_handoff_returns_note_without_extra_model_turn():
    from test_specialist_tool_batch import _batch, _handoff
    from test_specialist_graph import _input, _ToolPorts
    from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
    state, assignment = result_fixture()
    note = state['final_submission']['task_note']
    calls = []
    def model(request):
        calls.append(request)
        return _batch(request, [{**_handoff(request), 'task_note': note}])
    ports = _ToolPorts()
    graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=model, evidence_tool=ports.evidence, finance_tool=ports.finance)).compile()
    result = graph.invoke(_input(), {'recursion_limit': 12})
    outcome = task_outcome(result, assignment=assignment)
    assert len(calls) == 1 and not ports.calls
    assert outcome['execution_status'] == 'needs_attention' and outcome['author_note'] == note
