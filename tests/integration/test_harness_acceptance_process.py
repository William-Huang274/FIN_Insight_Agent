"""Real pinned native surface/restore/compaction with a local deterministic provider."""
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4
from contextlib import nullcontext

import httpx
import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from sec_agent.agent_runtime.harness_acp_session import admitted_acp_session
from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
from sec_agent.agent_runtime.harness_consultations import HarnessConsultations
from sec_agent.agent_runtime.harness_local_services import harness_local_services
from sec_agent.agent_runtime.harness_profile import profile_overlay
from sec_agent.agent_runtime.harness_storage import process_environment
from sec_agent.agent_runtime.harness_provider_transport import HarnessProviderTransport
from sec_agent.agent_runtime.harness_dispatch_host import HarnessDispatchHost
from sec_agent.agent_runtime.research_result_acceptance import result_version
from test_harness_dispatch_host import Store, Prices


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
@pytest.mark.skipif(not os.getenv('FIN_TEST_DSH_BINARY'), reason='explicit pinned binary required')
@pytest.mark.parametrize('compact', [False, True])
async def test_native_acceptance_surface_and_restored_readback(tmp_path, compact):
    task_id, run_id = str(uuid4()), str(uuid4())
    key = 'b'*64
    record = {'request': {'purpose':'investigate', 'report':None}, 'status':'completed',
              'opinion':'UNIQUE_FULL_CHILD_DETAIL '*1500}
    requests = []
    phase = 0
    summaries = 0
    bridge = None
    async def respond(request):
        nonlocal phase, summaries
        body = json.loads(request.content)
        requests.append(body)
        serialized = json.dumps(body['messages'])
        is_summary = 'acting as a compaction engine' in json.dumps(body['messages'][-1])
        if is_summary:
            summaries += 1
            assert 'UNIQUE_FULL_CHILD_DETAIL' not in serialized
            assert 'Utilization unknown' in serialized
            name, args = None, {}
        else:
            phase += 1
        if is_summary:
            pass
        elif phase == 1:
            name, args = 'read_research_agent_result', {'task_id':key}
        elif phase == 2:
            assert 'UNIQUE_FULL_CHILD_DETAIL' in serialized
            messages = (await bridge.state())['messages']
            receipt = next(m for m in messages if m.type=='tool' and m.name=='read_research_agent_result')
            name, args = 'assess_research_result', dict(task_id=key, result_digest=result_version(record),
                disposition='accepted', finding='Conditional positive finding', scope_and_conditions='2027 MW ramp assumed',
                counterevidence='Customer cancellations', unresolved='Utilization unknown', evidence_receipt_ids=[receipt.tool_call_id])
        else:
            assert 'UNIQUE_FULL_CHILD_DETAIL' not in serialized, 'accepted detail must leave native input'
            assert 'Utilization unknown' in serialized
            assert 'accepted_result_summary' in serialized
            name, args = None, {}
        if name:
            name = next(t['name'] for t in body['tools'] if t['name'].endswith(name))
            block = {'type':'tool_use', 'id':'call_'+str(phase), 'name':name, 'input':{}}
            delta = {'type':'input_json_delta', 'partial_json':json.dumps(args)}
        else:
            block, delta = {'type':'text','text':''}, {'type':'text_delta','text':
                'Accepted bounded result: accepted_result_summary; 2027 MW ramp assumed; Customer cancellations; Utilization unknown. '
                'Original result remains available via read_research_agent_result task_id='+key if is_summary else 'Fixture complete.'}
        events = [
            {'type':'message_start','message':{'id':'fixture','role':'assistant','type':'message', 'model':body['model'],
                'content':[],'usage':{'input_tokens':100,'output_tokens':0}}},
            {'type':'content_block_start','index':0,'content_block':block},
            {'type':'content_block_delta','index':0,'delta':delta},
            {'type':'content_block_stop','index':0},
            {'type':'message_delta','delta':{'stop_reason':'tool_use' if name else 'end_turn'},'usage':{'output_tokens':30}},
            {'type':'message_stop'}]
        return httpx.Response(200,content=''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events),
                              headers={'Content-Type':'text/event-stream'})
    basis = dict(node_role='lead',node_purpose='Offline accepted-result native qualification',input_scale='synthetic child result',
        required_outputs=['native replacement and restored summary'],schema_burden='consultation tools',
        materiality_quality_risk='no financial conclusion',comparable_run_evidence='native business fixture',
        reasoning_profile='agentic_message_history_thinking_enabled',max_input_characters=1000000,
        max_output_tokens=2048,timeout_seconds=90,max_transport_attempts=1,retry_policy='none',
        truncation_stop_behavior='fail_closed_no_partial_promotion',input_ceiling_behavior='fail_before_transport')
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'business.sqlite')) as saver:
        service = HarnessConsultations(directory=tmp_path/'jobs',saver=saver,grants=[],tid=task_id,rid=run_id,
            check=lambda:None,scope=nullcontext,budget=object(),environment={},model='fixture',basis=basis,
            as_of='2026-11-12',public_sink=lambda x:None)
        (service.directory/(key+'.json')).write_text(json.dumps(record),encoding='utf8')
        bridge = HarnessBusinessTools(grants=service.tools(),checkpointer=saver,thread_id=task_id,check=lambda:None)
        service.parent = bridge
        await bridge.initialize({'question':'Fixture acceptance','messages':[]})
        grant = dict(execution_id=task_id,authorized_run_id=run_id,manifest_digest='sha256:'+'a'*64)
        host = HarnessDispatchHost(store=Store(),owner='fixture',budget='fixture',execution_id=task_id,
            run_id=run_id,manifest_digest=grant['manifest_digest'],authority=lambda:grant,prices=Prices(),
            basis=basis,provider='deepseek-official',reservation_micros=1000,reservation_basis='fixture',
            receipts=tmp_path/'wire',wire_usage=lambda _:None)
        token='x'*40
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            transport=HarnessProviderTransport(host,protocol='deepseek_messages',endpoint='https://fixture.invalid/messages',
                provider_headers={},token=token,client=client)
            host.wire_usage=transport.meter
            async with harness_local_services(business=bridge,dispatch=host,transport=transport,token=token,
                    context_projection=service.context_projection) as endpoint:
                patch=profile_overlay(model='fixture-model',protocol='deepseek_messages',endpoint=endpoint,
                    prompt='Synthetic acceptance test.',context_window=64000,output_tokens=2048,summary_tokens=2048,
                    reasoning='high',dispatch_plugin=Path(__file__).resolve().parents[2]/'integrations/deepseek-harness/dispatch.mjs',
                    business_mcp={'Authorization':'Bearer '+token},wait_for_consultations=True)
                patch_path=tmp_path/'profile.json'
                patch_path.write_text(json.dumps(patch),encoding='utf8')
                storage={k:os.environ[k] for k in ['FINSIGHT_HARNESS_NATIVE_STORAGE_ROOT'] if k in os.environ}
                env=process_environment(storage,tmp_path/'session',token)
                # Two independently started native processes resume the same immutable log.
                for index, prompt in enumerate(['Read and accept the fixture result.'+(' Earlier neutral context.'*9000 if compact else ''),
                                               'Continue from accepted understanding.']):
                    if compact and index == 1:
                        next(p['config'] for p in patch if p.get('id')=='compaction-basic').update(
                            thresholdRatio=.15, headroomTokens=2048, retainTokens=256)
                        patch_path.write_text(json.dumps(patch),encoding='utf8')
                    async with admitted_acp_session(binary=os.environ['FIN_TEST_DSH_BINARY'],
                            arguments=['--profile','sdk-minimal','--patch',str(patch_path)],environment=env,
                            directory=tmp_path/'session',binding={'task':task_id},run_id=str(uuid4()),
                            authority=lambda:grant,stop=lambda:None,mcp_servers=[]) as active:
                        result=await asyncio.wait_for(active.prompt(prompt),90)
                        assert result['status']=='completed'
                assert phase==4
                assert bool(summaries) == compact
                messages=(await bridge.state())['messages']
                original=next(m for m in messages if m.type=='tool' and m.name=='read_research_agent_result')
                assert 'UNIQUE_FULL_CHILD_DETAIL' in original.content
