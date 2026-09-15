"""Saved repair intent, native execution scope and false completion regressions."""
from copy import deepcopy
import json

import httpx
import pytest

from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentAdapter
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
from sec_agent.agent_runtime.workpaper_revision_state import revision_state, revision_progress
from test_specialist_graph import _input, _ToolPorts, _evidence_action, _finance_action
from test_specialist_tool_batch import _batch, _handoff
from test_workpaper_partial_edits import paper, edit_action, text_edit, assessment


def test_old_native_batch_wire_identity_is_unchanged_and_new_scope_is_bound():
    from sec_agent.agent_runtime.specialist_graph import SpecialistNativeToolBatch
    from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
    legacy = {'action': 'native_tool_batch', 'context_digest': 'a' * 64, 'tool_calls': [
        {'id': 'saved', 'name': 'RequestEvidenceAction', 'type': 'tool_call', 'args': {}}]}
    restored = SpecialistNativeToolBatch.model_validate_json(json.dumps(legacy)).model_dump(mode='json')
    assert restored == legacy and canonical_sha256(restored) == canonical_sha256(legacy)
    scoped = SpecialistNativeToolBatch.model_validate_json(json.dumps({**legacy, 'runtime_tool_scope': ['RequestHumanReviewAction'],
        'context_checkpoint_required': True})).model_dump(mode='json')
    assert canonical_sha256(scoped) != canonical_sha256(legacy)
    assert scoped['runtime_tool_scope'] == ['RequestHumanReviewAction']


def test_legacy_recovery_uses_recorded_old_values_never_proposed_answers():
    candidate = paper()
    calls = [{'name': 'ReviseWorkpaperAction', 'id': 'old-failed', 'args': {'edits': [
        {'path': '/narrative_markdown', 'old_value': 'Expense table absent.', 'new_value': 'DO NOT INJECT THIS'},
        {'path': '/thesis', 'old_value': 'no longer in candidate', 'new_value': 'invented'},
        {'path': '/missing', 'old_value': 'unknown', 'new_value': 'invented'},
    ]}}, {'name': 'ReviseWorkpaperAction', 'id': 'bad-shape', 'args': {'edits': None}},
        {'name': 'ReviseWorkpaperAction', 'id': 'bad-json', 'type': 'invalid_tool_call',
        'args': '{"edits": [{"path": "/thesis"'}]
    state = {'last_submission_attempt': {'arguments': candidate}, 'notebook': {'model_turn_records': [
        {'turn_index': 4, 'action': {'action': 'native_tool_batch', 'tool_calls': calls}}]}}
    original = deepcopy(state)
    restored = revision_state(state)
    assert list(restored['revision_targets']) == ['/narrative_markdown']
    assert restored['revision_target_origins']['/narrative_markdown']['turn_index'] == 4
    assert 'DO NOT INJECT THIS' not in json.dumps(restored)
    assert state == original
    assert revision_progress({**state, **restored}, candidate)[0]['status'] == 'unchanged_since_revision_requested'
    changed = {**candidate, 'narrative_markdown': candidate['narrative_markdown'].replace('Expense table absent.', 'Provided.')}
    assert revision_progress({**state, **restored}, changed)[0]['status'] == 'changed_not_semantically_verified'


@pytest.mark.parametrize('full_submission', [False, True])
def test_completed_notes_and_fresh_submission_cannot_clear_unchanged_repair(full_submission):
    ports, requests = _ToolPorts(), []
    def turn(request):
        requests.append(request)
        n = len(requests)
        if n == 1: return _batch(request, [_evidence_action()({}), _finance_action()({})])
        if n == 2:
            value = paper(); value['claims'][0]['evidence_ids'] = ['E:unobserved']
            return _batch(request, [value])
        target = request['submission_to_repair']; candidate = target['candidate']
        if n == 3:
            return _batch(request, [edit_action(candidate, [{'path': '/narrative_markdown',
                'old_value': 'Expense table absent.', 'new_value': 'Provided.'}]).model_dump(mode='json')])
        if n == 4:
            # All old reference failures fixed. Completion note alone must not
            # close the recorded body repair, even via a full Submit alternative.
            edits = [{'path': '/claims/0/evidence_ids', 'old_value': ['E:unobserved'], 'new_value': ['E:DELL:Q1']},
                {'op': 'upsert_coverage', 'assessment': assessment('all corrected')}]
            action = edit_action(candidate, edits)
            if full_submission:
                from sec_agent.agent_runtime.specialist_graph import apply_workpaper_edits
                return _batch(request, [apply_workpaper_edits(candidate, action)])
            return _batch(request, [action.model_dump(mode='json')])
        if n == 5:
            result = json.loads(request['tool_results'][0]['content'])
            assert result['accepted'] is False
            assert any(i['type'] == 'requested_revision_not_applied' and i['path'] == '/narrative_markdown'
                for i in result['validation_issues'])
            assert candidate['claims'][0]['evidence_ids'] == ['E:DELL:Q1']
            return _batch(request, [edit_action(candidate, [text_edit()]).model_dump(mode='json')])
        pytest.fail('no extra retry should be needed')
    graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=turn,
        evidence_tool=ports.evidence, finance_tool=ports.finance, allow_workpaper_field_edits=True)).compile()
    result = graph.invoke(_input(), {'recursion_limit': 40})
    assert len(requests) == 5 and result['phase'] == 'specialist_submission_accepted'
    assert 'Expense table absent.' not in result['final_submission']['narrative_markdown']


@pytest.mark.parametrize('name', ['ReviseWorkpaperAction', 'SubmitWorkpaperAction', 'RequestEvidenceAction', 'UpdateResearchStateAction'])
def test_actual_sdk_checkpoint_rejects_unoffered_actions_and_stops_after_two(name):
    from test_deepseek_structured_agents import _config, _models
    from test_research_context_checkpoint import model
    requests, wires, ports = [], [], _ToolPorts()
    def serve(request):
        body = json.loads(request.content); wires.append(body)
        assert {t['function']['name'] for t in body['tools']} == {'UpdateResearchStateAction', 'RequestHumanReviewAction'}
        if len(wires) == 2:
            feedback = json.loads(body['messages'][-1]['content'])['result']
            assert feedback['error'] == 'native_tool_not_allowed_this_turn'
            assert feedback['batch_dispatched'] is False
            assert feedback['context_checkpoint_required'] is True
        return httpx.Response(200, json={'id': 'offline', 'object': 'chat.completion', 'created': 1, 'model': 'deepseek-v4-pro',
            'choices': [{'index': 0, 'finish_reason': 'tool_calls', 'message': {'role': 'assistant', 'content': '', 'tool_calls': [
                {'id': f'call-{len(wires)}', 'type': 'function', 'function': {'name': name, 'arguments': '{}'}}]}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 10, 'total_tokens': 110}})
    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        models = _models(); models['specialist'] = model(http_client=client, research_checkpoint_tokens=1)
        adapter = DeepSeekStructuredAgentAdapter(config=_config().model_copy(update={
            'agentic_message_history': True, 'runtime_context_binding': True}), chat_models=models)
        def turn(request):
            requests.append(request)
            return adapter.specialist_model_turn(request)
        graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=turn,
            turn_source='provider_model', evidence_tool=ports.evidence, finance_tool=ports.finance,
            working_state_enabled=True, allow_workpaper_field_edits=True)).compile()
        result = graph.invoke(_input(), {'recursion_limit': 25})
    assert len(wires) == 2 and result['notebook']['model_turn_count'] == 2
    assert result['review_reason'] == 'research_context_checkpoint_unresolved'
    assert not ports.calls and result.get('last_submission_attempt') is None
    assert result['final_submission'] is None


def test_one_disallowed_call_blocks_entire_batch_before_ports_or_memory():
    ports, requests = _ToolPorts(), []
    def turn(request):
        requests.append(request)
        if len(requests) == 1:
            batch = _batch(request, [_evidence_action()({}), _finance_action()({})])
            return {**batch, 'runtime_tool_scope': ['RequestEvidenceAction']}
        assert all(json.loads(r['content'])['batch_dispatched'] is False for r in request['tool_results'])
        return _handoff(request)
    graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=turn,
        evidence_tool=ports.evidence, finance_tool=ports.finance)).compile()
    result = graph.invoke(_input())
    assert not ports.calls and result['notebook']['tool_action_count'] == 0


def test_checkpoint_deduplicates_identical_runtime_snapshots_without_losing_revisions_or_errors():
    from langchain_core.messages import HumanMessage, ToolMessage
    from sec_agent.agent_runtime.model_context import task_boundary_history
    from test_research_context_checkpoint import checkpoint_message
    from test_research_working_state import working_note
    context = {'task_context': {'assignment': 'Original user scope and exact 2025 Q1 unit/period.',
        'user_revision': 'Keep the full claim and source identity.'},
        'submission_to_repair': {'candidate': paper()}}
    rows = [HumanMessage(content='Original user request stays verbatim.')]
    for i in range(3):
        rows.append(ToolMessage(name='ReviseWorkpaperAction', tool_call_id=f'edit-{i}', status='error',
            content=json.dumps({'result': {'error': 'field_mismatch', 'edit_index': i}, 'current_context': context})))
    different = deepcopy(context); different['submission_to_repair']['candidate']['thesis'] = 'Distinct earlier revision.'
    rows.append(ToolMessage(name='ReviseWorkpaperAction', tool_call_id='distinct', content=json.dumps({'current_context': different})))
    original = deepcopy(rows)
    # Duplicate runtime copies can normalize before a checkpoint; the unique
    # contents and all original tool results remain available in the request.
    initial = task_boundary_history(rows)
    assert rows == original
    assert json.loads(initial[2].content)['result'] == json.loads(rows[2].content)['result']
    assert json.loads(initial[1].content)['current_context'] == context
    assert initial[-1].content == rows[-1].content
    rows.extend(checkpoint_message(working_note(findings=[], retain_source_ids=[], phase_status='working')))
    latest = json.loads(rows[-1].content); latest['current_context'] = context
    rows[-1] = rows[-1].model_copy(update={'content': json.dumps(latest)})
    projected = task_boundary_history(rows)
    assert rows[:len(original)] == original
    first = json.loads(projected[1].content)
    assert first['current_context'] == context
    second = json.loads(projected[2].content)
    assert second['result'] == {'error': 'field_mismatch', 'edit_index': 1}
    assert second['current_context']['submission_to_repair']['identical_snapshot_retained_at_tool_call_id'] == 'edit-0'
    assert json.loads(projected[4].content)['current_context']['submission_to_repair'] == different['submission_to_repair']
    assert json.loads(projected[-1].content)['current_context'] == context


def test_lead_also_enforces_adapter_turn_scope_before_scheduling():
    from test_lead_research_graph import _graph, _call, _task, _stop
    requests = []
    def model(request):
        requests.append(request)
        if len(requests) == 1:
            response = _call(request, 'DelegateResearchTasksAction', tasks=[_task()])
            response['action']['runtime_tool_scope'] = ['SubmitResearchHandoffAction']
            return response
        assert 'native_tool_not_allowed_this_turn' in str(request['tool_results'])
        return _stop(request)
    graph, value = _graph(model, lambda *_: pytest.fail('unoffered delegate must never run'))
    graph.invoke(value.model_dump(mode='json'))
    assert len(requests) == 2
