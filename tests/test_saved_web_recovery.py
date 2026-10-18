from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
from sec_agent.agent_runtime.tool_recovery import recheck_failed_saved_web_read, project_recovery_receipts
from test_specialist_graph import _input, _ToolPorts
from test_saved_web_navigation import original


def setup():
    def model(r):
        return {'action': 'native_tool_batch', 'context_digest': r['context_digest'], 'tool_calls': [{
            'id': 'failed-read', 'name': 'RequestSourceAction', 'type': 'tool_call', 'args': {
                'action': 'request_source', 'selection': {'source_space': 'web', 'operation': 'read',
                    'document_id': 'WEB::doc', 'offset': 20000, 'max_characters': 8000},
                'context_digest': r['context_digest'], 'reason_summary': 'Read the saved original.'}}]}
    def evidence(_): raise ValueError('web_document_not_discovered_in_this_scope_search_first')
    data = _input(); data['l0_context']['source_read_enabled'] = True
    graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=model, evidence_tool=evidence, finance_tool=_ToolPorts().finance))
    events = graph.compile().stream(data, stream_mode='values')
    for state in events:
        if state.get('tool_results'): break
    events.close()
    state = deepcopy(state)
    artifacts = SimpleNamespace(**{k: state['task'][k] for k in
        ('case_id', 'snapshot_id', 'research_as_of', 'foundation_digest')},
        source_snapshot=lambda: {'source': original()})
    return state, artifacts


def test_saved_source_recovery_preserves_state_and_projects_real_check():
    from langchain_core.messages import ToolMessage
    s, art = setup(); before = deepcopy(s)
    restored = recheck_failed_saved_web_read(s, 'failed-read', art)
    assert s == before and restored['tool_results'] == s['tool_results']
    assert restored['notebook']['observations'][:-1] == s['notebook']['observations']
    for key in ('model_turn_records', 'model_turn_count', 'tool_action_count'):
        assert restored['notebook'][key] == s['notebook'][key]
    assert restored['max_model_turns'] == s['max_model_turns']
    assert restored['notebook']['observations'][-1]['content'] == [original()]
    assert recheck_failed_saved_web_read(restored, 'failed-read', art) == restored
    call = s['notebook']['model_turn_records'][-1]['action']['tool_calls'][0]
    msg = ToolMessage(tool_call_id='failed-read', status='error', content=json.dumps({'result': {'error': 'old'}}))
    project_recovery_receipts([msg], restored, {'failed-read': (None, call)})
    body = json.loads(msg.content)['result']
    assert msg.status == 'error' and body['historical_failure'] == {'error': 'old'}
    assert body['current_execution_check']['status'] == 'success'


def test_source_recovery_does_not_invent_success_or_cross_scopes():
    s, art = setup()
    art.source_snapshot = lambda: {}
    result = recheck_failed_saved_web_read(s, 'failed-read', art)
    assert result['notebook'] == s['notebook']
    assert result['task_context']['tool_recovery_checks'][-1]['outcome']['status'] == 'failure'
    art.case_id = 'unrelated'
    with pytest.raises(ValueError, match='source_scope_mismatch'):
        recheck_failed_saved_web_read(s, 'failed-read', art)
