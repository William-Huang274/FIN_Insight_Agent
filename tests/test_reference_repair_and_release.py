from copy import deepcopy
import json
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from sec_agent.agent_runtime.reference_repair import repair_working_references, resolve_reference
from sec_agent.agent_runtime.model_context import project_tool_history
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
from test_specialist_graph import _input, _ToolPorts, _evidence_action
from test_specialist_tool_batch import _batch, _handoff
from test_research_working_state import working_note
from test_research_subtasks import update

ID = 'PASSAGE::CHUNK::56eb44475152bcaf7908f3e1a7ff4c8fa0befca7'
TYPO = ID.replace('7ff4c', '7ffc')


def test_unique_observed_spelling_repair_preserves_prose_and_reports_paths():
    note = working_note(findings=[{'finding': 'Original author assessment', 'source_ids': [TYPO], 'limitations': 'USD Q2 actual'}],
        retain_source_ids=[ID[:-3]], resolved_questions=[], subtasks=[])
    original = deepcopy(note)
    fixed, repairs, issues = repair_working_references(note, {ID})
    assert fixed['findings'][0]['source_ids'] == [ID] and fixed['retain_source_ids'] == [ID]
    assert fixed['findings'][0]['finding'] == note['findings'][0]['finding']
    assert not issues and len(repairs) == 2 and note == original
    assert repair_working_references(fixed, {ID})[1:] == ([], [])


def test_ambiguous_wrong_namespace_short_and_unobserved_are_not_invented():
    for submitted, observed in [(ID[:-1], {ID, ID[:-1]+'9'}), ('SOURCE-A', {'SOURCE-B'}),
            (TYPO, {ID.replace('PASSAGE::', '')}), (TYPO, set())]:
        value, receipt = resolve_reference(submitted, observed)
        assert value == submitted and receipt['status'] in {'ambiguous', 'unresolved'}


def test_native_unknown_reference_is_saved_and_flagged_not_a_failed_tool():
    requests = []; ports = _ToolPorts()
    def turn(req):
        requests.append(req)
        if len(requests) == 1: return update(req, working_note(phase_status='working', retain_source_ids=[], findings=[{
            'finding': 'Still investigating', 'source_ids': ['UNKNOWN'], 'limitations': 'Unverified reference'}]))
        receipt = json.loads(req['tool_results'][0]['content'])
        assert receipt['accepted'] and receipt['reference_issues'][0]['status'] == 'unresolved'
        assert req['tool_results'][0]['status'] != 'error'
        return _handoff(req)
    state = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=turn,
        evidence_tool=ports.evidence, finance_tool=ports.finance, working_state_enabled=True)).compile().invoke(_input())
    assert state['pending_working_state_update'] is None
    assert state['research_working_state']['findings'][0]['source_ids'] == ['UNKNOWN']
    assert state['research_working_state']['reference_issues']


def read_messages(key='read1', *, status='success'):
    row = {'result_state': 'source_bound_passage', 'document_id': 'DOC', 'passage_id': ID,
        'passage': 'Long exact original USD million FY2027. '*2000}
    return [AIMessage(content='', tool_calls=[{'id': key, 'name': 'RequestSourceAction', 'args': {
        'action': 'request_source', 'selection': {'operation': 'read', 'document_id': 'DOC'}}}]),
        ToolMessage(name='RequestSourceAction', tool_call_id=key, status=status,
            content=json.dumps({'result': {'observations': [{'kind': 'evidence', 'status': status,
                'references': [{'ref_id': ID}], 'content': [row]}]}}))]


def release_message():
    return ToolMessage(name='UpdateResearchStateAction', tool_call_id='release',
        content=json.dumps({'context_release': {'source_ids': ['DOC'], 'through_model_turn': 2}}))


def test_explicit_release_is_request_only_and_later_reread_is_visible():
    rows = [*read_messages(), release_message(), *read_messages('reread')]
    original = deepcopy(rows)
    projected = project_tool_history(rows, policy='task_boundary')
    assert rows == original
    old = json.loads(projected[1].content)['result']['observations'][0]['content'][0]
    assert old['result_state'] == 'released_navigation'
    assert old['recovery']['arguments']['selection']['document_id'] == 'DOC'
    assert old['recovery']['original_tool_call_id'] == 'read1'
    assert projected[-1].content == rows[-1].content
    assert projected[0].tool_calls == rows[0].tool_calls
    assert project_tool_history(projected, policy='task_boundary') == projected
    failed = [*read_messages(status='error'), release_message()]
    assert project_tool_history(failed, policy='task_boundary')[1].content == failed[1].content


def test_restored_release_uses_original_turn_and_preserves_failures_and_no_reader():
    def obs(turn, **kw):
        return {'kind': 'evidence', 'status': 'success', 'content': [{'result_state': 'source_bound_passage',
            'document_id': 'DOC', 'passage_id': ID, 'passage': 'exact original'}],
            'recovery': {'read_tool': 'RequestSourceAction', 'saved_observation_id': f'saved-{turn}',
                'arguments': {'selection': {'document_id': 'DOC'}}, 'batch_turn': turn}, **kw}
    body = {'task_context': {'context_releases': [{'source_ids': ['DOC'], 'through_model_turn': 2}]},
        'progress': {'observations': [obs(1), obs(3), obs(1, status='error'), obs(1, recovery={})]}}
    rows = [HumanMessage(content=json.dumps(body))]
    out = json.loads(project_tool_history(rows, policy='task_boundary')[0].content)['progress']['observations']
    assert out[0]['content'][0]['result_state'] == 'released_navigation'
    assert [o['content'][0]['passage'] for o in out[1:]] == ['exact original']*3


def test_release_only_native_action_does_not_require_a_note_or_change_originals():
    requests=[]; ports=_ToolPorts()
    def turn(req):
        requests.append(req)
        if len(requests)==1:return _batch(req, [_evidence_action()(req)])
        if len(requests)==2:
            ref=req['notebook']['observations'][0]['references'][0]['ref_id']
            return {'action':'native_tool_batch','context_digest':req['context_digest'],'tool_calls':[{
                'name':'UpdateResearchStateAction','id':'release','type':'tool_call','args':{
                    'action':'update_research_state','context_digest':req['context_digest'],
                    'reason_summary':'Finished reading; release this result.', 'release_source_ids':[ref]}}]}
        return _handoff(req)
    graph=build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=turn,
        evidence_tool=ports.evidence,finance_tool=ports.finance,working_state_enabled=True)).compile()
    result=graph.invoke(_input())
    assert result['context_releases'][0]['source_ids']
    assert not result.get('research_working_state')
    assert result['notebook']['observations'] == requests[1]['notebook']['observations']
    assert requests[-1]['task_context']['context_releases'] == result['context_releases']


def test_explicit_calculation_release_keeps_exact_request_and_reread_identity():
    args = {'action': 'request_calculation', 'selection': {'metric_id': 'METRIC'}}
    messages = [AIMessage(content='', tool_calls=[{'id': 'calc', 'name': 'RequestCalculationAction', 'args': args}]),
        ToolMessage(name='RequestCalculationAction', tool_call_id='calc', content=json.dumps({'result': {
            'observations': [{'kind': 'finance', 'status': 'success', 'content': [
                {'result_state': 'numeric_fact', 'numeric_fact_id': 'DOC', 'value': 42, 'unit': 'USD'}]}]}})),
        release_message()]
    projected = project_tool_history(messages, policy='task_boundary')
    row = json.loads(projected[1].content)['result']['observations'][0]['content'][0]
    assert row['result_state'] == 'released_navigation'
    assert row['recovery']['arguments'] == args
    assert row['recovery']['read_tool'] == 'RequestCalculationAction'


def test_one_dismissed_file_does_not_remove_the_rest_of_company_menu():
    messages = read_messages()
    body = json.loads(messages[1].content)
    body['result']['observations'][0]['content'] = [{'result_state': 'retrieval_candidate',
        'company_section': 'sources', 'entity_id': 'COMPANY', 'sources': [
            {'id': 'DOC', 'title': 'Old report'}, {'id': 'OTHER', 'title': 'New report'}]}]
    messages[1].content = json.dumps(body)
    projected = project_tool_history([*messages, release_message()], policy='task_boundary')
    sources = json.loads(projected[1].content)['result']['observations'][0]['content'][0]['sources']
    assert sources[0]['result_state'] == 'released_navigation'
    assert sources[1]['title'] == 'New report'


def test_legacy_action_serialization_does_not_add_new_fields_to_old_digests():
    from sec_agent.agent_runtime.research_working_state import ResearchWorkingState, UpdateResearchStateAction
    note = ResearchWorkingState.model_validate(working_note()).model_dump(mode='json')
    assert 'reference_issues' not in note
    payload = {'action': 'update_research_state', 'context_digest': 'a' * 64,
        'reason_summary': 'Save current understanding.', 'working_state': note}
    action = UpdateResearchStateAction.model_validate(payload).model_dump(mode='json')
    assert 'release_source_ids' not in action
    assert 'reference_issues' not in action['working_state']
