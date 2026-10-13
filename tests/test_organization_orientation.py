"""Organization pre-research through actual phase/Lead/tools, with static model I/O."""
import json
from copy import deepcopy
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from sec_agent.agent_runtime import research_session_runtime as runtime
from sec_agent.agent_runtime.research_orientation import (
    OrientationOrganizationReadAction, orientation_public_handoff,
)
from sec_agent.agent_runtime.research_feedback import ResearchFeedbackStore
from sec_agent.agent_runtime.execution_options import ExecutionOptions
from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentAdapter, ReasoningPreservingChatDeepSeek
from test_organization_data_composition import organization
from test_organization_phase_factory import phases_for, invoke, replay, forbid_host_data
from test_research_orientation import call, submission, blocked_submission


def stopped():
    return {**blocked_submission(), 'graph_skip_reason':'No relationship graph is authorized for this fixed-input question.',
        'recency_skip_reason':'Only pinned originals are authorized; current publication coverage is unknown.'}


def orientation_phase(factory, tmp_path, monkeypatch, model):
    monkeypatch.setattr(runtime.DeepSeekStructuredAgentAdapter, 'from_config', lambda **k:
        SimpleNamespace(lead_research_turn=model, specialist_model_turn=lambda _:pytest.fail('unexpected expert')))
    return phases_for(factory, tmp_path, execution=ExecutionOptions(mode='auto'))


def run(phases):
    return invoke(phases, 'research', {'question':'Check the selected original before proposing research.', 'research_stage':'orientation'})


def static_orientation(request, requests):
    requests.append(deepcopy(request))
    context = request['orientation_context']
    assert context['source_space'] == 'organization' and not context['complete_through_date_certified']
    assert all(c['source_spaces'] == ['organization'] for c in request['capabilities'])
    turn = len(requests)
    if turn == 1:
        action = call(request, 'RequestSourceAction', {'action':'request_source', 'reason_summary':'List fixed originals.',
            'selection':{'source_space':'organization','operation':'catalog'}})
    elif turn == 2:
        result = json.loads(request['tool_results'][0]['content'])['result']
        document = next(r['document_id'] for r in result['items'] if r.get('document_id'))
        action = call(request, 'RequestSourceAction', {'action':'request_source', 'reason_summary':'Read exact original.',
            'selection':{'source_space':'organization','operation':'read','document_id':document}})
    elif turn == 3:
        action = call(request, 'ReportResearchIssuesAction', {'issues':[{'issue_id':'scope', 'kind':'external_evidence',
            'summary':'Current coverage beyond selected original remains unknown.', 'read_refs':['O2'],
            'impact':'no_current_impact','next_check':'Ask for an authorized updated source if current coverage is required.'}]})
    else:
        assert len(context['feedback_updates']) == 1
        receipt = json.loads(requests[2]['tool_results'][0]['content'])
        passage = next(r for r in receipt['result']['items'] if r.get('result_state') == 'source_bound_passage')
        args = submission('O2')
        args.update(graph_skip_reason=stopped()['graph_skip_reason'], recency_skip_reason=stopped()['recency_skip_reason'])
        args['findings'][0].update(judgment='The static original contains a source sentence, not a financial conclusion.',
            evidence_spans=[{'read_ref':'O2','passage_id':passage['passage_id'],'quote':passage['passage'][:600]}])
        action = call(request, 'SubmitResearchOrientationAction', args)
    return replay(action['action'], request)


def test_actual_phase_reads_fixed_sources_preserves_identity_and_scopes_feedback(organization, tmp_path, monkeypatch):
    factory, _ = organization
    requests = []
    result = run(orientation_phase(factory, tmp_path, monkeypatch, lambda r:static_orientation(r, requests)))
    assert len(requests) == 4 and result['phase'] == 'research_orientation_submitted'
    assert not result['tasks'] and not result['task_results']
    orientation = result['research_orientation']
    assert orientation['semantic_acceptance'] == 'not_assessed' and not orientation['delegation_executed']
    handoff = orientation_public_handoff(orientation)
    source = handoff['source_readbacks']['O2']['passages'][0]['organization_source']
    assert source['execution_id'] == factory.grant['execution_id']
    assert source['manifest_digest'] == factory.grant['manifest_digest']
    store = ResearchFeedbackStore(tmp_path / 'research-feedback.sqlite')
    owner, thread = 'organization:' + factory.grant['organization_id'], factory.grant['execution_id']
    assert len(store.list(owner, thread, 'static-organization-phase')) == 1
    assert store.list('alice', thread, 'static-organization-phase') == []
    assert store.list(owner, 'other-execution', 'static-organization-phase') == []


@pytest.mark.parametrize('selection', [
    {'source_space':'library','operation':'catalog'}, {'source_space':'uploads','operation':'read'},
    {'source_space':'organization','operation':'related'}, {'source_space':'organization','operation':'company'},
])
def test_organization_orientation_schema_excludes_host_navigation(selection):
    with pytest.raises(ValueError):
        OrientationOrganizationReadAction.model_validate({'context_digest':'a'*64,'action':'request_source',
            'reason_summary':'Scope test.', 'selection':selection})


@pytest.mark.parametrize('moment', ['source','feedback_read','feedback_write'])
def test_revocation_stops_tool_path_without_model_repair(organization, tmp_path, monkeypatch, moment):
    factory, authority = organization
    requests = []
    if moment == 'source':
        from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
        original = OrganizationSourceNavigation.navigate
        def read(*args, **kwargs):
            result = original(*args, **kwargs)
            authority['status'] = 404
            return result
        monkeypatch.setattr(OrganizationSourceNavigation, 'navigate', read)
    else:
        method = 'list' if moment == 'feedback_read' else 'save'
        original = getattr(ResearchFeedbackStore, method)
        def record(*args, **kwargs):
            result = original(*args, **kwargs)
            authority['status'] = 404
            return result
        monkeypatch.setattr(ResearchFeedbackStore, method, record)
    with pytest.raises(Exception) as denied:
        run(orientation_phase(factory, tmp_path, monkeypatch, lambda r:static_orientation(r, requests)))
    import traceback
    assert 'OrganizationExecutionUnavailable' in ''.join(traceback.format_exception(denied.value))
    assert len(requests) == {'source':1,'feedback_read':0,'feedback_write':3}[moment]


def test_native_adapter_receives_org_schema_and_prompt_without_external_transport(organization, tmp_path, monkeypatch):
    factory, _ = organization
    wires = []
    def transport(request):
        wire = json.loads(request.content); wires.append(wire)
        prompt = wire['messages'][0]['content']
        assert 'source_space=organization exclusively' in prompt
        assert 'source_space=library exclusively' not in prompt
        schema = next(t['function']['parameters'] for t in wire['tools'] if t['function']['name'] == 'RequestSourceAction')
        assert schema['properties']['selection']['properties']['source_space']['const'] == 'organization'
        assert set(schema['properties']['selection']['properties']['operation']['enum']) == {'catalog','outline','search','read'}
        # Production profile binds the digest on the host, not in model args.
        args = stopped()
        return httpx.Response(200, json={'id':'offline','object':'chat.completion','created':1,'model':'deepseek-v4-pro',
            'choices':[{'index':0,'finish_reason':'tool_calls','message':{'role':'assistant','content':'',
                'reasoning_content':'offline fixture','tool_calls':[{'id':'stop','type':'function',
                    'function':{'name':'SubmitResearchOrientationAction','arguments':json.dumps(args)}}]}}],
            'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}})
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        model = ReasoningPreservingChatDeepSeek(model='deepseek-v4-pro',api_key=SecretStr('offline'),
            http_client=client,max_retries=0,use_responses_api=False)
        def adapter(**kwargs):
            return DeepSeekStructuredAgentAdapter(config=kwargs['config'],chat_models={r:model for r in ('planner','specialist','counter','lead')},
                source_access_check=kwargs['source_access_check'])
        monkeypatch.setattr(runtime.DeepSeekStructuredAgentAdapter, 'from_config', adapter)
        result = run(phases_for(factory, tmp_path, execution=ExecutionOptions(mode='auto')))
    assert result['phase'] == 'research_orientation_submitted' and len(wires) == 1
    assert result['research_orientation']['disposition'] == 'needs_attention'


def test_invented_excerpt_cannot_be_submitted_through_actual_org_phase(organization, tmp_path, monkeypatch):
    factory, _ = organization
    requests = []
    def model(request):
        if len(requests) < 4:
            value = static_orientation(request, requests)
            if len(requests) == 4:
                action = deepcopy(value['action'])
                action['tool_calls'][0]['args']['findings'][0]['evidence_spans'][0]['quote'] = 'An invented financial claim absent from originals.'
                value = replay(action, request)
            return value
        requests.append(request)
        assert 'orientation_excerpt_not_in_cited_window' in str(request['tool_results'])
        return replay(call(request, 'SubmitResearchOrientationAction', stopped())['action'], request)
    result = run(orientation_phase(factory, tmp_path, monkeypatch, model))
    assert len(requests) == 5
    assert result['research_orientation']['findings'] == []
    assert result['research_orientation']['disposition'] == 'needs_attention'
