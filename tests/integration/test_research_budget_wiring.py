"""Actual research factories/SDK/native graphs, synthetic data and HTTP, real PG."""
import asyncio
from contextlib import contextmanager
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import SecretStr

from test_native_server_runtime import native
from sec_agent.adapters.model_dispatch_store import ModelDispatchStore
from sec_agent.agent_runtime.model_dispatch_guard import TokenPrices
from sec_agent.agent_runtime.research_budget import ResearchBudget
from sec_agent.agent_runtime.deepseek_structured_agents import ReasoningPreservingChatDeepSeek, DeepSeekStructuredAgentAdapter

pytestmark = pytest.mark.skipif(os.getenv('FIN_NATIVE_QUALIFICATION') != '1', reason='isolated Docker opt-in')


def scope(native, name):
    store = ModelDispatchStore('postgresql://probe:' + native.env['FIN_E1_POSTGRES_PASSWORD'] + '@127.0.0.1:18416/probe')
    store.install()
    store.create_budget('alice', name, 'CNY', 20000, 2000)
    roles = {r: {'reservation_micros':600, 'reservation_basis':'Synthetic 600 micros; each SDK response costs200',
                 'delivery':r in ('writer','context_summary')} for r in ('lead','specialist','writer','quick_writer','context_summary')}
    return ResearchBudget(store, owner='alice', budget=name,
        prices={m:TokenPrices('synthetic-not-a-real-tariff',m,'CNY',1000000,0,2000000)
                for m in ('deepseek-v4-pro','deepseek-v4-flash')}, roles=roles)


def wire_response(name=None, args=None, *, finish='tool_calls'):
    message = {'role':'assistant', 'content':'' if name else 'Synthetic summary; financial quality not evaluated.',
               'reasoning_content':'synthetic private reasoning'}
    if name:
        message['tool_calls'] = [{'id':str(uuid4()),'type':'function',
            'function':{'name':name,'arguments':json.dumps(args)}}]
    return httpx.Response(200,json={'id':str(uuid4()),'object':'chat.completion','created':1,'model':'deepseek-v4-pro',
        'choices':[{'index':0,'finish_reason':finish if name else 'stop','message':message}],
        'usage':{'prompt_tokens':100,'completion_tokens':50,'total_tokens':150,'prompt_cache_hit_tokens':0}})


def test_sync_lead_specialist_share_pg_and_known_parse_failure_replays(native, monkeypatch):
    from test_deepseek_structured_agents import _config, _agentic_turn_request
    from test_lead_research_graph import _graph, _stop
    budget, events, wires, current = scope(native,'sync-wiring'), [], [], []
    monkeypatch.setenv('LANGSMITH_TRACING','false')
    def serve(request):
        payload=json.loads(request.content); wires.append(payload)
        names={t['function']['name'] for t in payload['tools']}
        if 'SubmitResearchHandoffAction' in names:
            call=_stop(current[-1])['action']['tool_calls'][0]
            return wire_response(call['name'],call['args'])
        # Known paid response but invalid tool batch: must settle, never promote.
        return wire_response()
    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        model=ReasoningPreservingChatDeepSeek(model='deepseek-v4-pro',api_key=SecretStr('fixture-not-a-secret'),
            http_client=client,max_retries=0,use_responses_api=False)
        config=_config().model_copy(update={'agentic_message_history':True})
        def adapter():
            return DeepSeekStructuredAgentAdapter(config=config,
                chat_models={r:model for r in ('planner','specialist','counter','lead')},audit_sink=events.append,
                dispatch_guards={r:budget.guard(r,config.profile_for(r)) for r in ('lead','specialist')})
        lead=adapter()
        def turn(request):
            current.append(request)
            return lead.lead_research_turn(request)
        graph,value=_graph(turn,lambda *_:pytest.fail('no child is requested by this synthetic lead'),turn_source='provider_model')
        graph.invoke(value.model_dump(mode='json'),{'configurable':{'thread_id':'sync-lead'}})
        def specialist(_):
            # Fresh adapter on replay, matching reconstruction after process loss.
            return adapter().specialist_model_turn(_agentic_turn_request())
        child=StateGraph(dict).add_node('specialist',specialist).add_edge(START,'specialist').add_edge('specialist',END).compile(checkpointer=InMemorySaver())
        cfg={'configurable':{'thread_id':'sync-specialist'}}
        with pytest.raises(Exception,match='structured_parse_failed|native_action|single_call|structured_payload'):
            child.invoke({},cfg)
        calls=len(wires)
        with pytest.raises(Exception):
            child.invoke(None,cfg)
        assert len(wires)==calls
        snapshot=budget.store.snapshot('alice','sync-wiring')
        assert snapshot['known']==200*calls and snapshot['held']==0
        assert any(r.get('event')=='replay' for r in events)
        native.save('sync_wiring',{'snapshot':snapshot,'http_calls':calls,'replay_events':sum(r.get('event')=='replay' for r in events)})


def test_real_writer_factory_delegates_child_and_summarizes_on_one_budget(native, monkeypatch):
    from sec_agent.agent_runtime import research_session_runtime as runtime
    from test_research_convergence import artifact_fixture
    budget, artifacts, events, wires = scope(native,'native-wiring'), artifact_fixture(), [], []
    profile, case = runtime.load_research_runtime_profile(Path.cwd())
    profile['context_summarization'].update(enabled=True,trigger_tokens=300,keep_tokens=50,max_summaries=1)
    profile['nodes']['writer']['limits']={'model_calls':5,'tool_calls':8}
    ref='P01:'+artifacts.read_paper('P01')['claims'][0]['claim_id']
    branch=case['branch_topics'][0]['branch_id']
    monkeypatch.setenv('LANGSMITH_TRACING','false')
    monkeypatch.setattr(runtime,'current_task_artifacts',lambda _:artifacts)
    @contextmanager
    def data(**kwargs):
        yield SimpleNamespace(foundation_binding=SimpleNamespace(case_id=artifacts.case_id,research_as_of=artifacts.research_as_of,
            snapshot_id=artifacts.snapshot_id,foundation_digest=artifacts.foundation_digest),
            decision_digest=artifacts.owner_data_gate_decision_digest,inventory_snapshot_digest=artifacts.inventory_snapshot_digest,
            source_route_catalog_digest=artifacts.source_route_catalog_digest,mcp_server=None)
    class Client:
        def __init__(self,*args,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def call_tool(self,*args,**kwargs): return SimpleNamespace(is_error=False,structured_content={'run_scope':{}})
    monkeypatch.setattr(runtime,'open_approved_data_composition',data)
    monkeypatch.setattr(runtime,'Client',Client)
    monkeypatch.setattr(runtime,'case_mcp_tools',AsyncMock(return_value=[]))
    delegated=False
    def serve(request):
        nonlocal delegated
        payload=json.loads(request.content); wires.append(payload)
        names={t['function']['name'] for t in payload.get('tools',[])}
        if not names:
            return wire_response()
        if 'consult_research_specialist' in names and not delegated:
            delegated=True
            return wire_response('consult_research_specialist',{'branch_id':branch,'objective':'Inspect this synthetic scoped source-bound question.'})
        return wire_response('submit_case_answer',{'answer_markdown':f'Synthetic source-bound answer; not financial acceptance. [{ref}]'})
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            def model(profile,basis,*args,**kwargs):
                return ReasoningPreservingChatDeepSeek(model=profile.model,api_key=SecretStr('fixture-not-a-secret'),
                    http_async_client=client,max_retries=0,use_responses_api=False)
            monkeypatch.setattr(runtime,'case_chat_model',model)
            phases=runtime.create_research_phase_runnables(root=Path.cwd(),settings={'audit_root':str(native.output)},
                profile=profile,case=case,run_id='synthetic-run',thread_id='native-wiring',api_key=SecretStr('fixture-not-a-secret'),
                environment={},public_sink=events.append,private_sink=lambda _:None,budget_scope=budget)
            graph=StateGraph(dict).add_node('writer',phases['writer']).add_edge(START,'writer').add_edge('writer',END).compile(checkpointer=InMemorySaver())
            messages=[HumanMessage(content='Inspect the synthetic question.',id='original')]
            for i in range(4):
                messages.extend([HumanMessage(content='Historical synthetic question. '*120,id=f'q{i}'),
                                 AIMessage(content='Historical synthetic discussion. '*120,id=f'a{i}')])
            messages.append(HumanMessage(content='Answer this synthetic question with a scoped source.',id='latest'))
            return await graph.ainvoke({'messages':messages,'question':'Synthetic research', 'report':{},'revisions':{},
                'human_edits':[],'conversation':[],'request_action':'ask'}, {'configurable':{'thread_id':'native-wiring'},'recursion_limit':80})
    result=asyncio.run(exercise())
    assert result['output']['kind']=='answer' and delegated
    actors={e['actor'] for e in events if e.get('event')=='started' and e.get('provider_call_attempted')}
    assert {'writer',branch,'context_summary:writer'} <= actors
    snapshot=budget.store.snapshot('alice','native-wiring')
    assert snapshot['known']==200*len(wires) and snapshot['held']==0
    assert sum(not p.get('tools') for p in wires)==1
    native.save('native_factory_wiring',{'snapshot':snapshot,'http_calls':len(wires),'actors':sorted(actors),
                                       'financial_quality_evaluated':False})
