"""Current Lead schemas and source-feedback consumption over the native SDK.

Scripted HTTP decisions qualify wiring/self-correction paths, not model quality.
"""
import json

import httpx
import pytest
from pydantic import SecretStr

from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentAdapter, ReasoningPreservingChatDeepSeek
from sec_agent.agent_runtime.lead_research_graph import build_lead_research_graph, lead_tool_models
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticInput
from langgraph.checkpoint.memory import InMemorySaver
from test_deepseek_structured_agents import _config
from test_lead_research_graph import BRANCHES, CATALOG, _call, _task
from test_specialist_graph import _input


PLAN = {"depth": "integrated", "rationale": "Two independent papers need source review, writing and final verification.",
        "omitted_steps_reason": "No distinct synthesis step is currently justified; required review is retained.",
        "escalation_conditions": "Add synthesis only if actual cross-paper conflicts require distinct analysis."}


@pytest.mark.parametrize("space", ["uploads", "web"])
def test_native_lead_repairs_schema_then_queries_current_source_before_delegation(space, tmp_path, monkeypatch):
    from sec_agent.agent_runtime.working_memory import WorkingMemory
    from sec_agent.agent_runtime.working_memory_tools import native_memory_scope
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH',str(tmp_path/'notes.sqlite'))
    memory=WorkingMemory(tmp_path/'notes.sqlite',owner='alice',workspace='native-planning',actor='lead')
    note=memory.save('Current working assumption','Original')
    memory.save('Current working assumption','Human revision body must be read on demand.',1,user_edit=True)
    requests, wires, reads = [], [], []
    body = _input()
    body['l0_context']['capability_summaries'].append({
        'capability_ref': 'capability:dell:source-document-read', 'source_spaces': [space]})
    value = SpecialistAgenticInput.model_validate_json(json.dumps(body))

    def read(selection):
        reads.append(selection.model_dump(mode='json'))
        return {'runtime_receipt': {'receipt_id': 'HOST_ONLY_RECEIPT_SENTINEL'},
                'items': [{'document_id': 'DOC::current', 'current_status': 'AVAILABLE_AFTER_REFRESH',
                           'mcp_receipt_chain': [{'request_digest': 'HOST_ONLY_DIGEST_SENTINEL'}],
                           'passage': 'Synthetic current-source observation; no financial authority.'}],
                'public_information_gap_proved': False}

    def transport(request):
        wire = json.loads(request.content)
        wires.append(wire)
        functions = {t['function']['name']: t['function']['parameters'] for t in wire['tools']}
        assert 'execution_plan' in functions['DelegateResearchTasksAction']['required']
        assert 'question_coverage' in functions['SubmitResearchHandoffAction']['required']
        assert 'RequestSourceAction' in functions
        current = requests[-1]
        turn = len(wires)
        system=wire['messages'][0]['content']
        assert note['note_id'] in system and system.count('用户曾直接修改') == 1
        assert f'"version": {2 if turn==1 else 3}' in system
        assert 'Human revision body' not in system
        if turn == 1:
            memory.save('Current working assumption','New human revision between model turns.',2,user_edit=True)
            action = _call(current, 'DelegateResearchTasksAction', tasks=[_task('a'), _task('b')])
        elif turn == 2:
            assert 'execution_plan' in wire['messages'][-1]['content']
            action = _call(current, 'RequestSourceAction', action='request_source',
                           selection={'source_space': space, 'operation': 'search', 'query': 'current source availability'})
        elif turn == 3:
            assert 'AVAILABLE_AFTER_REFRESH' in wire['messages'][-1]['content']
            assert 'HOST_ONLY_RECEIPT_SENTINEL' not in json.dumps(wire)
            assert 'HOST_ONLY_DIGEST_SENTINEL' not in json.dumps(wire)
            assert 'DOC::current' in wire['messages'][-1]['content']
            action = _call(current, 'RequestSourceAction', action='request_source',
                           selection={'source_space': space, 'operation': 'read', 'document_id': 'DOC::current'})
        else:
            assert turn == 4 and 'Synthetic current-source observation' in wire['messages'][-1]['content']
            action = _call(current, 'DelegateResearchTasksAction', tasks=[_task('a'), _task('b')], execution_plan=PLAN)
        call = action['action']['tool_calls'][0]
        return httpx.Response(200, json={'id': f'scripted-{turn}', 'object': 'chat.completion', 'created': 1,
            'model': 'deepseek-v4-pro', 'choices': [{'index': 0, 'finish_reason': 'tool_calls', 'message': {
                'role': 'assistant', 'content': '', 'tool_calls': [{'id': call['id'], 'type': 'function',
                'function': {'name': call['name'], 'arguments': json.dumps(call['args'])}}]}}],
            'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        model = ReasoningPreservingChatDeepSeek(model='deepseek-v4-pro', api_key=SecretStr('offline-test'),
            http_client=client, max_retries=0, use_responses_api=False)
        adapter = DeepSeekStructuredAgentAdapter(config=_config().model_copy(update={'agentic_message_history': True}),
            chat_models={role: model for role in ('planner', 'specialist', 'counter', 'lead')})
        def turn(request):
            requests.append(request)
            return adapter.lead_research_turn(request)
        graph = build_lead_research_graph(expected_input=value, research_question='Inspect current source availability before planning.',
            branch_catalog=CATALOG, allowed_branch_ids=BRANCHES, seed_workpapers={}, model_turn=turn,
            run_child=lambda *_: pytest.fail('Stop before specialist execution'), source_reader=read,
            require_all_branches=False, require_execution_plan=True, turn_source='provider_model').compile(
                checkpointer=InMemorySaver(), interrupt_after=['lead_tools'])
        config = {'configurable': {'thread_id': 'native-planning'}}
        with native_memory_scope('alice','native-planning'):
            graph.invoke(value.model_dump(mode='json'), config)
        for _ in range(3):
            assert graph.get_state(config).next == ('lead',)
            with native_memory_scope('alice','native-planning'):
                graph.invoke(None, config)
        state = graph.get_state(config)
        assert state.next == ('specialist', 'specialist') and len(reads) == 2
        assert len(state.values['planning_observations']) == 2
        assert state.values['planning_observations'][0]['result']['runtime_receipt']['receipt_id'] == 'HOST_ONLY_RECEIPT_SENTINEL'


def test_legacy_schema_stays_readable_and_unauthorized_source_tool_absent():
    old = lead_tool_models()
    assert 'execution_plan' not in old['DelegateResearchTasksAction'].model_json_schema()['required']
    assert 'RequestSourceAction' not in old


@pytest.mark.parametrize('mixed', [False, True])
def test_read_batch_preserves_each_observation_and_cannot_mix_with_mutations(mixed):
    body = _input()
    body['l0_context']['capability_summaries'].append({
        'capability_ref': 'capability:dell:source-document-read', 'source_spaces': ['uploads']})
    value = SpecialistAgenticInput.model_validate_json(json.dumps(body))
    reads = []
    def turn(request):
        first = _call(request, 'RequestSourceAction', action='request_source',
            selection={'source_space': 'uploads', 'operation': 'catalog'})
        second = (_call(request, 'DelegateResearchTasksAction', tasks=[_task()], execution_plan=PLAN) if mixed else
            _call(request, 'RequestSourceAction', action='request_source',
                selection={'source_space': 'uploads', 'operation': 'search', 'query': 'current data'}))
        second['action']['tool_calls'][0]['id'] += '-second'
        first['action']['tool_calls'].extend(second['action']['tool_calls'])
        return first
    def read(selection):
        reads.append(selection.operation)
        return {'selection_executed': selection.operation}
    graph = build_lead_research_graph(expected_input=value, research_question='Batch source qualification.',
        branch_catalog=CATALOG, allowed_branch_ids=BRANCHES, seed_workpapers={}, model_turn=turn,
        run_child=lambda *_: pytest.fail('No worker execution'), source_reader=read,
        require_all_branches=False, require_execution_plan=True).compile(
            checkpointer=InMemorySaver(), interrupt_after=['lead_tools'])
    config = {'configurable': {'thread_id': 'read-batch'}}
    graph.invoke(value.model_dump(mode='json'), config)
    state = graph.get_state(config).values
    assert not state['tasks'] and len(state['tool_results']) == 2
    if mixed:
        assert not reads and not state['planning_observations']
        assert all('one_planning_mutation' in row['content'] for row in state['tool_results'])
    else:
        assert reads == ['catalog', 'search'] and len(state['planning_observations']) == 2
        assert [json.loads(row['content'])['result']['selection_executed'] for row in state['tool_results']] == reads


def test_query_capability_limits_are_not_advertised_as_source_disclosure_limits():
    from sec_agent.agent_runtime.lead_research_graph import lead_capability_catalog
    row = lead_capability_catalog([{'capability_ref': 'finance', 'known_non_capabilities': ['units']}])[0]
    assert row['known_non_capabilities'] == ['units']
    assert 'query interface only' in row['capability_limit_scope']


def test_human_note_and_source_reads_share_one_readonly_batch(tmp_path,monkeypatch):
    from sec_agent.agent_runtime.working_memory import WorkingMemory
    from sec_agent.agent_runtime.working_memory_tools import native_memory_scope
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH',str(tmp_path/'notes.sqlite'))
    memory=WorkingMemory(tmp_path/'notes.sqlite',owner='alice',workspace='mixed-read',actor='lead')
    note=memory.save('Scope','Human edited scope',user_edit=True)
    body=_input();body['l0_context']['capability_summaries'].append({'capability_ref':'read','source_spaces':['uploads']})
    value=SpecialistAgenticInput.model_validate_json(json.dumps(body));reads=[]
    def turn(request):
        batch=_call(request,'RequestSourceAction',action='request_source',selection={'source_space':'uploads','operation':'catalog'})
        batch['action']['tool_calls'].insert(0,{'id':'read-current-note','type':'tool_call','name':'ReadWorkingNote','args':{'note_id':note['note_id']}})
        return batch
    def read(selection):reads.append(selection.operation);return {'source':'available'}
    graph=build_lead_research_graph(expected_input=value,research_question='Read current notes and sources.',
        branch_catalog=CATALOG,allowed_branch_ids=BRANCHES,seed_workpapers={},model_turn=turn,
        run_child=lambda *_:pytest.fail('No worker'),source_reader=read,require_all_branches=False,
        require_execution_plan=True).compile(checkpointer=InMemorySaver(),interrupt_after=['lead_tools'])
    config={'configurable':{'thread_id':'mixed-read'}}
    with native_memory_scope('alice','mixed-read'):graph.invoke(value.model_dump(mode='json'),config)
    state=graph.get_state(config).values
    assert reads==['catalog'] and len(state['planning_observations'])==1
    assert len(state['tool_results'])==2 and not state['tasks']
    parsed=[json.loads(r['content']) for r in state['tool_results']]
    contents=[r.get('result',r) for r in parsed]
    assert any(r.get('found') and r.get('body')=='Human edited scope' for r in contents)
    assert not any('error' in r for r in contents)


def test_lead_cannot_invent_web_authority_or_delegate_without_source_check():
    body = _input()
    body['l0_context']['capability_summaries'].append({
        'capability_ref': 'capability:dell:source-document-read', 'source_spaces': ['uploads']})
    value = SpecialistAgenticInput.model_validate_json(json.dumps(body))
    def turn(request):
        if request['progress']['turn_index'] == 1:
            return _call(request, 'DelegateResearchTasksAction', tasks=[_task()], execution_plan=PLAN)
        assert 'planning_source_check_required' in str(request['tool_results'])
        return _call(request, 'RequestSourceAction', action='request_source',
            selection={'source_space': 'web', 'operation': 'search', 'query': 'unauthorized'})
    graph = build_lead_research_graph(expected_input=value, research_question='Permission test.',
        branch_catalog=CATALOG, allowed_branch_ids=BRANCHES, seed_workpapers={}, model_turn=turn,
        run_child=lambda *_: pytest.fail('No worker authority'), source_reader=lambda *_: pytest.fail('No web authority'),
        require_all_branches=False, require_execution_plan=True, max_lead_turns=2).compile()
    result = graph.invoke(value.model_dump(mode='json'))
    assert not result['tasks'] and not result['planning_observations']
    assert 'source_scope_not_authorized' in str(result['tool_results'])
