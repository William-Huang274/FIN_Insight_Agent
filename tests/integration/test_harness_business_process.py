"""Opt-in pinned binary + real MCP/ToolNode/save/resume, zero paid inference."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from acp.schema import HttpMcpServer, HttpHeader
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from sec_agent.agent_runtime.conversation_agent import GrantedTool
from sec_agent.agent_runtime.conversation_tools import conversation_tools
from sec_agent.agent_runtime.harness_acp_session import admitted_acp_session
from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
from sec_agent.agent_runtime.harness_local_services import harness_local_services
from sec_agent.agent_runtime.harness_profile import profile_overlay
from sec_agent.agent_runtime.harness_provider_transport import HarnessProviderTransport
from sec_agent.agent_runtime.harness_dispatch_host import HarnessDispatchHost
from sec_agent.agent_runtime.working_memory_tools import native_memory_scope, working_memory_tools
from sec_agent.agent_runtime.working_memory import WorkingMemory
from test_harness_dispatch_host import Store, Prices


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
@pytest.mark.skipif(not os.getenv('FIN_TEST_DSH_BINARY'), reason='explicit pinned local binary required')
async def test_real_process_tools_restart_compaction_and_cancel(tmp_path, monkeypatch):
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH', str(tmp_path / 'notes.sqlite'))
    task_id = str(uuid4())
    source = {'numeric_fact_id': 'NUMFACT::fixture', 'numeric_fact_authority': True,
              'value_decimal': '120', 'unit': 'USD million', 'ticker': 'TEST',
              'period_start': '2025-01-01', 'period_end': '2025-12-31'}
    @tool(response_format='content_and_artifact')
    def query_financial_data():
        """Read synthetic original."""
        value = {'authority_state': 's2_numeric_fact_query_result',
                 'results': [{'status': 'resolved', 'facts': [source]}]}
        return json.dumps(value), value
    grants = [GrantedTool(query_financial_data, 'read', 'fixture')]
    grants += [g for g in conversation_tools(thread_id=task_id)
               if g.tool.name in {'calculate_research_metric', 'read_saved_result'}]
    grants += [GrantedTool(t, 'working_note_write' if t.name == 'WriteWorkingNote' else 'read', 'fixture')
               for t in working_memory_tools('lead', owner='fixture', workspace=task_id)]
    store = Store()
    requests = []
    progress = {'step': 0, 'summaries': 0, 'hold': False}
    entered = asyncio.Event()
    memory = WorkingMemory(tmp_path / 'notes.sqlite', owner='fixture', workspace=task_id, actor='lead')
    basis = dict(node_role='lead', node_purpose='Synthetic native business-tool lifecycle qualification',
        input_scale='Synthetic original and stress text', required_outputs=['saved note and readback'],
        schema_burden='MCP financial tools', materiality_quality_risk='No real research quality claimed',
        comparable_run_evidence='Prior protocol fixture', reasoning_profile='agentic_message_history_thinking_enabled',
        max_input_characters=1_000_000, max_output_tokens=2048, timeout_seconds=90,
        max_transport_attempts=1, retry_policy='none', truncation_stop_behavior='fail_closed_no_partial_promotion',
        input_ceiling_behavior='fail_before_transport')

    async def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        if progress['hold']:
            entered.set()
            await asyncio.Event().wait()
        compacting = 'acting as a compaction engine' in json.dumps(body.get('messages', [])[-1:])
        name, args = None, None
        if compacting:
            progress['summaries'] += 1
            text = 'Fixture checkpoint: read source, calculated 60, saved note. Read the note next.'
        else:
            step = progress['step']
            progress['step'] += 1
            if step == 0:
                name, args = 'query_financial_data', {}
            elif step == 1:
                name, args = 'calculate_research_metric', {'request': {'expression': 'v / 2',
                    'operands': {'v': {'source_id': 'NUMFACT::fixture'}}, 'result_unit': 'USD million', 'rationale': 'fixture'}}
            elif step == 2:
                name, args = 'WriteWorkingNote', {'title': 'Fixture note', 'body': 'Calculated 60 USD million.', 'base_version': 0}
            elif step == 4:
                notes = memory.search('')
                note_id = notes['items'][0]['id']
                name, args = 'ReadWorkingNote', {'note_id': note_id}
            text = 'Fixture completed.'
        if name:
            full_name = next(t['name'] for t in body['tools'] if t['name'].endswith(name))
            block = {'type': 'tool_use', 'id': 'call_' + str(len(requests)), 'name': full_name, 'input': {}}
            delta = {'type': 'input_json_delta', 'partial_json': json.dumps(args)}
        else:
            block = {'type': 'text', 'text': ''}
            delta = {'type': 'text_delta', 'text': text}
        events = [
            {'type': 'message_start', 'message': {'id': 'response', 'role': 'assistant', 'type': 'message',
                'model': body['model'], 'content': [], 'usage': {'input_tokens': 100, 'output_tokens': 0}}},
            {'type': 'content_block_start', 'index': 0, 'content_block': block},
            {'type': 'content_block_delta', 'index': 0, 'delta': delta},
            {'type': 'content_block_stop', 'index': 0},
            {'type': 'message_delta', 'delta': {'stop_reason': 'tool_use' if name else 'end_turn'}, 'usage': {'output_tokens': 30}},
            {'type': 'message_stop'}]
        wire = ''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events)
        return httpx.Response(200, content=wire, headers={'Content-Type': 'text/event-stream'})

    @asynccontextmanager
    async def session(saver):
        run_id = str(uuid4())
        bridge = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id=task_id, check=lambda: None,
            scope=lambda: native_memory_scope('fixture', task_id, access_check=lambda: None))
        await bridge.initialize({'question': 'Fixture arithmetic task', 'messages': []})
        grant = dict(execution_id=task_id, authorized_run_id=run_id, manifest_digest='sha256:'+'a'*64)
        def authority():
            bridge.access()
            return grant
        host = HarnessDispatchHost(store=store, owner='fixture', budget='fixture', execution_id=task_id,
            run_id=run_id, manifest_digest=grant['manifest_digest'], authority=authority, prices=Prices(), basis=basis,
            provider='deepseek-official', reservation_micros=1000, reservation_basis='fixture',
            receipts=tmp_path / run_id / 'wire', wire_usage=lambda _: None)
        token = 'x'*40
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            transport = HarnessProviderTransport(host, protocol='deepseek_messages', endpoint='https://fixture.invalid/messages',
                provider_headers={}, token=token, client=client)
            host.wire_usage = transport.meter
            async with harness_local_services(business=bridge, dispatch=host, transport=transport, token=token) as endpoint:
                patch = profile_overlay(model='fixture-model', protocol='deepseek_messages', endpoint=endpoint,
                    prompt='Synthetic financial test. Use the provided tools.', context_window=64000,
                    output_tokens=2048, summary_tokens=2048, reasoning='high', compaction_threshold=.2,
                    dispatch_plugin=Path(__file__).resolve().parents[2] / 'integrations/deepseek-harness/dispatch.mjs')
                next(p['config'] for p in patch if p.get('id') == 'compaction-basic').update(headroomTokens=2048, retainTokens=256)
                patch_path = tmp_path / run_id / 'profile.json'
                patch_path.write_text(json.dumps(patch), encoding='utf8')
                env = {'DSH_HOME': str(tmp_path / 'dsh-home'), 'FIN_HARNESS_LOCAL_TOKEN': token,
                       'HOME': str(tmp_path), 'USERPROFILE': str(tmp_path)}
                mcp = [HttpMcpServer(type='http', name='financial', url=endpoint+'/business/',
                       headers=[HttpHeader(name='Authorization', value='Bearer '+token)])]
                async with admitted_acp_session(binary=os.environ['FIN_TEST_DSH_BINARY'],
                        arguments=['--profile', 'sdk-minimal', '--patch', str(patch_path)], environment=env,
                        directory=tmp_path / 'session', binding={'task': task_id}, run_id=run_id,
                        authority=authority, stop=bridge.stop, mcp_servers=mcp) as active:
                    yield active, bridge
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'business.sqlite')) as saver:
        async with session(saver) as (active, bridge):
            result = await asyncio.wait_for(active.prompt('Read, calculate and save the fixture.'), 60)
            assert result['status'] == 'completed'
            assert len([m for m in (await bridge.state())['messages'] if m.type == 'tool']) == 3
        async with session(saver) as (active, bridge):
            result = await asyncio.wait_for(active.prompt('fixture history ' * 6000 + '\nRead the saved note.'), 60)
            assert result['status'] == 'completed'
            tools = [m for m in (await bridge.state())['messages'] if m.type == 'tool']
            assert [m.name for m in tools] == ['query_financial_data', 'calculate_research_metric', 'WriteWorkingNote', 'ReadWorkingNote']
            assert all(m.status == 'success' for m in tools)
        async with session(saver) as (active, bridge):
            progress['hold'] = True
            task = asyncio.create_task(active.prompt('Cancellation fixture.'))
            await asyncio.wait_for(entered.wait(), 30)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            with pytest.raises(RuntimeError, match='stopped'):
                bridge.access()
    assert progress['summaries'] > 0
    assert len(memory.search('')['items']) == 1
    (tmp_path / 'result.json').write_text(json.dumps({'provider_requests': len(requests),
        'summaries': progress['summaries'], 'tools': len(tools), 'paid_calls': 0}), encoding='utf8')
