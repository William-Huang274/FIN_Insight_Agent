"""No provider: wire protocol, bounded segments, and accepted-prefix retention."""
import asyncio
from copy import deepcopy
import json

import pytest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda

from sec_agent.agent_runtime.model_context import RequestSummaryMiddleware, project_tool_history
from sec_agent.agent_runtime.continuous_context_surface import expand_provenance


def rows():
    result = [HumanMessage(id='task', content='Explain growth; keep FY2025 versus FY2026 and USD.')]
    for i in range(9):
        result += [AIMessage(id=f'a{i}', content='', additional_kwargs={'reasoning_content': 'private draft'*100},
            tool_calls=[{'id': f'c{i}', 'name': 'read', 'args': {'id': i}, 'type': 'tool_call'}]),
            ToolMessage(id=f't{i}', tool_call_id=f'c{i}', name='read', content=json.dumps({
                'items': [{'passage_id': f'PASSAGE::{i}', 'text': 'Necessary source condition. '*200}]}))]
    return result


def middleware(respond, **kwargs):
    return RequestSummaryMiddleware(model=FakeListChatModel(responses=['unused']),
        audited_model=RunnableLambda(respond), context_policy='continuous_surface',
        trigger_tokens=2000, keep_tokens=500, segment_tokens=6000, segment_characters=15000,
        max_summaries=2, **kwargs)


def check_pairs(messages):
    pending = set()
    for message in messages:
        if isinstance(message, AIMessage):
            assert not pending
            pending.update(c['id'] for c in message.tool_calls)
        elif isinstance(message, ToolMessage):
            assert message.tool_call_id in pending
            pending.remove(message.tool_call_id)
        else:
            assert not pending
    assert not pending


def test_segments_keep_roles_tasks_pairs_receipts_and_strict_allowance():
    async def run():
        calls = []
        def answer(value):
            calls.append(value)
            return AIMessage(content='OFFLINE STUB. Sources remain available; next action pending.')
        agent = middleware(answer)
        agent.bind_context('Stable system instructions', [])
        history = rows(); original = deepcopy(history)
        update = await agent.abefore_model({'messages': history}, None)
        assert len(calls) == 2 and update['request_summary']['count'] == 2
        assert len(calls[0]) < len(history)
        for sent in calls:
            check_pairs(sent)
            assert sent[0].type == 'system' and sent[1] == history[0]
            assert 'checkpoint' in sent[-1].content and 'private draft' not in str(sent)
            assert len(json.dumps([m.model_dump(mode='json', exclude={'artifact','response_metadata','usage_metadata'})
                                   for m in sent], ensure_ascii=False)) <= 15000
        state = {'messages': history, **update}
        assert await agent.abefore_model(state, None) is None
        assert agent.projected_messages(state)[-2:] == history[-2:]
        assert agent.projected_messages(deepcopy(state)) == agent.projected_messages(state)
        assert history == original
    asyncio.run(run())


@pytest.mark.parametrize('failure', ['provider', 'budget'])
def test_later_failure_keeps_first_accepted_segment_without_retry(failure):
    async def run():
        calls=[]
        def answer(value):
            calls.append(value)
            if len(calls) == 2:
                if failure == 'budget':
                    from sec_agent.adapters.model_dispatch_store import DispatchBlocked
                    raise DispatchBlocked('scope_exhausted')
                raise TimeoutError('provider fixture')
            return AIMessage(content='OFFLINE FIRST SEGMENT STUB')
        agent = middleware(answer); history = rows(); original = deepcopy(history)
        update = await agent.abefore_model({'messages': history}, None)
        assert update['request_summary']['count'] == 1
        assert update['request_summary_failure']['automatic_retry'] is False
        assert history == original and len(calls) == 2
        assert await agent.abefore_model({'messages': history, **update}, None) is None
        assert len(calls) == 2
    asyncio.run(run())


def test_oversized_indivisible_batch_stops_before_provider():
    async def run():
        calls=[]; agent=middleware(lambda value: calls.append(value))
        history=rows();history[2].content='large '*12000
        update=await agent.abefore_model({'messages':history},None)
        assert not calls and update['request_summary_failure']['provider_call_attempted'] is False
        assert update['request_summary_failure']['reason']=='summary_segment_exceeds_input_budget'
    asyncio.run(run())


def test_calculation_metadata_and_notices_roundtrip_without_merging_values():
    history=[]
    provenance={'source_id':'PASSAGE::same','period':'FY2026','unit':'USD','notice':'Original conditions. '*40}
    for i in range(3):
        body={'calculation_id':f'CALC::{i}','operands':{'a':{'value_decimal':str(i),
            'period':'FY2026','source_provenance':provenance}},'value_decimal':str(i),
            'authority_note':'Arithmetic is not financial inference. '*12}
        history.append(ToolMessage(content=json.dumps(body),name='calculate',tool_call_id=str(i)))
    before=deepcopy(history)
    view=project_tool_history(history, policy='continuous_surface',trigger_tokens=None)
    assert len(str(view)) < len(str(history))
    assert [json.loads(m.content) for m in expand_provenance(view)] == [json.loads(m.content) for m in before]
    assert view==project_tool_history(view, policy='continuous_surface',trigger_tokens=None)
    assert history==before


def test_segment_does_not_leave_exact_read_reference_outside_request():
    from sec_agent.agent_runtime.checkpoint_compaction import CheckpointCompaction
    native=CheckpointCompaction(model=FakeListChatModel(responses=['unused']),
        trigger=('tokens',2000),keep=('tokens',500),segment_characters=15000,segment_tokens=6000)
    history=rows()[1:]
    original=history[-1].content
    history[1]=history[1].model_copy(update={'content':json.dumps({'duplicate_of_tool_call_id':'c8'})})
    cutoff=native._determine_cutoff_index(history)
    assert cutoff < len(history)
    sent=native.request_messages(history[:cutoff])
    assert next(m for m in sent if isinstance(m,ToolMessage) and m.tool_call_id=='c0').content==original


def test_actual_builder_summary_audit_and_sdk_share_system_and_tool_contract():
    import httpx
    from pathlib import Path
    from types import SimpleNamespace
    from pydantic import SecretStr
    from langchain_core.tools import tool
    from langgraph.checkpoint.memory import InMemorySaver
    from sec_agent.agent_runtime.case_review_agent import CaseModelAudit, case_chat_model
    from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
    from sec_agent.agent_runtime.conversation_agent import build_conversation_agent, GrantedTool
    from tests.test_conversation_agent import ScriptedTools

    spec=json.loads((Path(__file__).resolve().parents[1]/'configs/research/runtime/continuous_context_baseline.json').read_text())['summary']
    profile=DeepSeekModelProfile.model_validate(spec['profile'])
    basis=TokenBudgetBasis.model_validate_json(json.dumps(spec['budget']))
    sent=[];public=[];private=[]
    def transport(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200,json={'id':'offline','object':'chat.completion','created':0,
            'model':'deepseek-flash','choices':[{'index':0,'finish_reason':'stop',
                'message':{'role':'assistant','content':'OFFLINE checkpoint fixture.'}}],
            'usage':{'prompt_tokens':100,'completion_tokens':10,'total_tokens':110}})
    @tool('read')
    def read_fixture(id: int):
        """Read only the granted synthetic source."""
        pytest.fail('summary must not execute a tool')
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            model=case_chat_model(profile,basis,SimpleNamespace(base_url='https://api.deepseek.com'),SecretStr('offline'),
                context_editing={'policy':'continuous_surface','trigger_tokens':None})
            model=type(model)(**{**model.model_dump(exclude={'client','async_client','root_client','root_async_client'}),
                'api_key':SecretStr('offline'),'http_async_client':client})
            audit=CaseModelAudit(actor='conversation_summary',profile=profile,basis=basis,
                public_sink=public.append,private_sink=private.append)
            audit.working_note_context=lambda:''
            compact=middleware(lambda _:None, audited_model_factory=lambda tools:audit.model_runnable(model,tools=tools))
            compact.max_summaries=1
            build_conversation_agent(model=ScriptedTools(responses=[]),grants=[GrantedTool(read_fixture,'read','fixture')],
                permission_mode='request_standard',checkpointer=InMemorySaver(),middleware=[compact])
            update=await compact.abefore_model({'messages':rows()},None)
            assert update['request_summary']['count']==1
    asyncio.run(run())
    assert len(sent)==1 and sent[0]['messages'][0]['role']=='system'
    assert sent[0]['messages'][0]['content'].startswith('You are FinSight.')
    assert sent[0]['tools'][0]['function']['name']=='read'
    assert sent[0]['messages'][-1]['role']=='user' and 'checkpoint' in sent[0]['messages'][-1]['content']
    assert sent[0]['max_tokens']==12000 and sent[0]['reasoning_effort']=='high'
    assert any(r.get('event')=='request' for r in private)
