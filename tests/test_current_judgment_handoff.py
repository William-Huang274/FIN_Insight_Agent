"""Current evidence navigation must not turn uncertainty into either approval or erasure."""
import json
from copy import deepcopy

from langchain_core.messages import AIMessage, ToolMessage

from sec_agent.agent_runtime.context_records import browse_checkpoint
from sec_agent.agent_runtime.research_actions import research_action_view, synthesis_working_view, research_working_view
from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
from sec_agent.agent_runtime.source_acquisition_view import acquisition_snapshot
from sec_agent.agent_runtime.working_memory_tools import execute_memory_tool


def observation(key, args, result, status='success'):
    return [AIMessage(content='', tool_calls=[{'id': key, 'name': 'read_public_source', 'args': args}]),
            ToolMessage(tool_call_id=key, name='read_public_source', status=status,
                        content=json.dumps(result))]


def test_current_understanding_uses_matching_lead_decision_without_erasing_proposal():
    original = ToolMessage(name='read_research_agent_result', tool_call_id='original', content=json.dumps({
        'status': 'completed', 'task_id': 'study', 'result_digest': 'v1', 'purpose': 'investigate',
        'assessment': {'finding': 'Rejected calculation', 'scope_explanation': 'Original scope'}}))
    decision = {'decision_recorded': True, 'task_id': 'study', 'result_digest': 'v1',
        'disposition': 'needs_work', 'finding': 'Current conditional interpretation',
        'scope_and_conditions': 'Customer approval required', 'counterevidence': 'Possible delay',
        'unresolved': 'Magnitude still material', 'evidence_receipt_ids': ['source']}
    saved = ToolMessage(name='assess_research_result', tool_call_id='decision', content=json.dumps(decision))
    state = {'messages': [original, saved]}
    before = original.content
    entry = research_working_view(state)['investigations'][0]
    assert entry['lead_decision'] == decision
    assert entry['readback']['arguments']['tool_call_id'] == 'original'
    assert entry['decision_readback']['arguments']['tool_call_id'] == 'decision'
    assert 'Rejected calculation' not in json.dumps(entry)
    assert original.content == before
    # A different result version or an unsuccessful decision cannot retire this proposal.
    saved.content = json.dumps({**decision, 'result_digest': 'v2'})
    assert research_working_view(state)['investigations'][0]['finding'] == 'Rejected calculation'
    saved.content = json.dumps(decision)
    saved.status = 'error'
    assert 'lead_decision' not in research_working_view(state)['investigations'][0]
    # Reopening carries the open condition, never an accepted certification.
    saved.status = 'success'
    saved.content = json.dumps({**decision, 'disposition': 'reopened'})
    assert research_working_view(state)['investigations'][0]['lead_decision']['disposition'] == 'reopened'


def test_no_url_search_failure_survives_handoff_and_candidate_is_not_a_read():
    args = {'operation': 'search', 'query': 'official quarterly capacity', 'end_published_date': '2026-06-30'}
    messages = observation('failed', args, {'operation': 'search', 'items': [],
        'execution_receipt': {'status': 'tool_failure'}})
    snapshot = synthesis_working_view({'messages': messages})['acquisition']
    assert snapshot['queries_without_usable_result'] == 1
    assert snapshot['source_urls'] == 0
    page = browse_checkpoint(messages, 'acquisition')
    assert page['items'][0]['event']['readback']['arguments'] == {'tool_call_id': 'failed'}
    assert page['items'][0]['event']['stage'] == 'search_execution_failed'
    # Successful candidate on the same request clears only its no-result observation.
    messages += observation('candidate', args, {'operation': 'search', 'items': [{
        'source_url': 'https://issuer.test/quarter', 'result_state': 'retrieval_candidate'}]})
    assert acquisition_snapshot(messages)['queries_without_usable_result'] == 0
    assert not any(row['has_read_passage'] for row in browse_checkpoint(messages, 'acquisition')['items'])
    assert any(row['event']['receipt_id'] == 'failed' for row in browse_checkpoint(messages, 'acquisition')['items'])
    # A changed cutoff is a separate research request; no cross-period clearance.
    messages += observation('later', {**args, 'end_published_date': '2026-09-30'}, {'operation': 'search', 'items': []})
    assert acquisition_snapshot(messages)['queries_without_usable_result'] == 1
    assert acquisition_snapshot(messages)['research_coverage'] == 'not_established_by_runtime'


def test_native_wrapping_and_partial_access_keep_exact_failure_readback():
    body = {'operation': 'search', 'items': [], 'execution_receipt': {'status': 'tool_failure'},
            'unresolved_originals': [{'url': 'https://agency.test/order', 'reason': 'origin_403'}]}
    direct = observation('receipt', {'operation': 'search', 'query': 'order'}, body)
    wrapped = observation('receipt', {'operation': 'search', 'query': 'order'},
                          {'receipt_id': 'receipt', 'status': 'success', 'result': body})
    assert acquisition_snapshot(direct) == acquisition_snapshot(wrapped)
    assert acquisition_snapshot(wrapped)['sources_with_obstacle_after_last_read'] == 1
    assert len(browse_checkpoint(wrapped, 'acquisition')['items']) == 2


def test_resolved_audit_prose_moves_to_readback_but_reactivates_on_changed_report():
    report = {'title': 'Current view', 'narrative_markdown': 'Conditional outlook.'}
    action = {'action_id': 'old:1', 'material': True, 'gap': 'OLD AUDIT DEBATE',
              'question_or_claim': 'Prior claim', 'consequence': 'Changes choice', 'next_action': 'Investigate'}
    old = ToolMessage(name='read_research_agent_result', tool_call_id='old', content=json.dumps({
        'task_id': 'old', 'status': 'completed', 'assessment': {'actions': [action]}}))
    checked = ToolMessage(name='read_research_agent_result', tool_call_id='new', content=json.dumps({
        'task_id': 'new', 'status': 'completed', 'reviewed_report_digest': canonical_sha256(report),
        'assessment': {'actions': [], 'resolved_action_ids': ['old:1']}}))
    state = {'report': report, 'report_version': 2, 'messages': [old, checked]}
    original = deepcopy(state)
    current = synthesis_working_view(state)['research_actions']
    assert current['actions'] == []
    assert current['resolved_actions'][0]['action_id'] == 'old:1'
    assert research_action_view(state)['actions'][0]['gap'] == 'OLD AUDIT DEBATE'
    assert state == original
    state['report'] = {**report, 'narrative_markdown': 'Stronger replacement outlook.'}
    reopened = synthesis_working_view(state)['research_actions']
    assert reopened['actions'][0]['gap'] == 'OLD AUDIT DEBATE'
    assert reopened['resolved_actions'] == []
    assert reopened['pending_material'] == ['old:1']


def test_note_replacement_has_history_navigation_without_copying_audit_into_current(tmp_path, monkeypatch):
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH', str(tmp_path / 'notes.sqlite'))
    config = {'configurable': {'thread_id': 'task'}}
    def call(name, args):
        return execute_memory_tool(name, args, config, 'author', owner='alice')
    saved = call('WriteWorkingNote', {'title': 'Decision', 'body': 'Old claim SOURCE::one'})
    added = call('WriteWorkingNote', {'title': 'Decision', 'body': 'Correction debate', 'mode': 'append', 'base_version': 1})
    assert added['saved'] and added['write_mode'] == 'append'
    assert 'does not retire old assertions' in added['synthesis_notice']
    revised = call('WriteWorkingNote', {'title': 'Decision', 'body': 'Current conditional judgment SOURCE::one', 'base_version': 2})
    assert revised['saved'] and revised['write_mode'] == 'replace'
    current = call('ReadWorkingNote', revised['current_readback']['arguments'])
    previous = call('ReadWorkingNote', revised['previous_version_readback']['arguments'])
    assert current['body'] == 'Current conditional judgment SOURCE::one'
    assert previous['body'] == 'Old claim SOURCE::one\n\nCorrection debate'
    stale = call('WriteWorkingNote', {'title': 'Decision', 'body': 'Late edit', 'base_version': 1})
    assert not stale['saved'] and 'current_readback' not in stale
    assert saved['note_id'] == revised['note_id']


def test_method_entry_exposes_choice_without_requiring_unjustified_certainty():
    from sec_agent.research_foundation.research_methods import get_research_method, METHOD_TOOL_GUIDANCE, BASIC_RESEARCH_GUIDANCE
    section = '选择基准与改判条件'
    resource = get_research_method('scenario_sensitivity', section)
    assert section in METHOD_TOOL_GUIDANCE and section in BASIC_RESEARCH_GUIDANCE
    assert '21—23' in resource['content'] and resource['selection'] == section
    assert '不能把未查写成未来无法确定' in resource['content']
    assert '不能因为未来可能反转' in BASIC_RESEARCH_GUIDANCE
