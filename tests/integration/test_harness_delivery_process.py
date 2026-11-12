"""Pinned upstream MCP conclusion, no external provider or paid inference."""
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from sec_agent.agent_runtime.conversation_agent import GrantedTool
from sec_agent.agent_runtime.harness_acp_session import admitted_acp_session
from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
from sec_agent.agent_runtime.harness_local_services import harness_local_services
from sec_agent.agent_runtime.harness_profile import profile_overlay
from sec_agent.agent_runtime.harness_storage import process_environment
from sec_agent.agent_runtime.harness_provider_transport import HarnessProviderTransport
from sec_agent.agent_runtime.harness_dispatch_host import HarnessDispatchHost
from test_harness_dispatch_host import Store, Prices


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
@pytest.mark.skipif(not os.getenv('FIN_TEST_DSH_BINARY'), reason='explicit pinned binary required')
async def test_native_delivery_finishes_without_another_provider_or_summary(tmp_path):
    task_id, run_id = str(uuid4()), str(uuid4())
    @tool
    def deliver_current_report(version: int):
        """Deliver a synthetic previously saved artifact."""
        return {'execution_status': 'submitted', 'artifact_kind': 'report',
                'artifact_version': version, 'artifact_digest': 'fixture-digest'}
    grants = [GrantedTool(deliver_current_report, 'task_artifact_write', 'fixture')]
    requests = []
    async def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        assert len(requests) == 1, 'delivery must not trigger another model or compaction request'
        name = next(t['name'] for t in body['tools'] if t['name'].endswith('deliver_current_report'))
        events = [
            {'type': 'message_start', 'message': {'id': 'fixture', 'role': 'assistant', 'type': 'message',
                'model': body['model'], 'content': [], 'usage': {'input_tokens': 100, 'output_tokens': 0}}},
            {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'tool_use', 'id': 'call_1', 'name': name, 'input': {}}},
            {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'input_json_delta', 'partial_json': '{"version": 10}'}},
            {'type': 'content_block_stop', 'index': 0},
            {'type': 'message_delta', 'delta': {'stop_reason': 'tool_use'}, 'usage': {'output_tokens': 30}},
            {'type': 'message_stop'}]
        return httpx.Response(200, content=''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events),
                              headers={'Content-Type': 'text/event-stream'})
    basis = dict(node_role='lead', node_purpose='Offline native delivery qualification',
        input_scale='synthetic tool result', required_outputs=['native turn completion'],
        schema_burden='one tool', materiality_quality_risk='no financial conclusion',
        comparable_run_evidence='native business fixture', reasoning_profile='agentic_message_history_thinking_enabled',
        max_input_characters=100000, max_output_tokens=2048, timeout_seconds=90,
        max_transport_attempts=1, retry_policy='none', truncation_stop_behavior='fail_closed_no_partial_promotion',
        input_ceiling_behavior='fail_before_transport')
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'business.sqlite')) as saver:
        bridge = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id=task_id, check=lambda: None)
        await bridge.initialize({'question': 'Fixture delivery', 'messages': []})
        grant = dict(execution_id=task_id, authorized_run_id=run_id, manifest_digest='sha256:'+'a'*64)
        host = HarnessDispatchHost(store=Store(), owner='fixture', budget='fixture', execution_id=task_id,
            run_id=run_id, manifest_digest=grant['manifest_digest'], authority=lambda: grant, prices=Prices(),
            basis=basis, provider='deepseek-official', reservation_micros=1000, reservation_basis='fixture',
            receipts=tmp_path/'wire', wire_usage=lambda _: None)
        token = 'x'*40
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            transport = HarnessProviderTransport(host, protocol='deepseek_messages', endpoint='https://fixture.invalid/messages',
                provider_headers={}, token=token, client=client)
            host.wire_usage = transport.meter
            async with harness_local_services(business=bridge, dispatch=host, transport=transport, token=token) as endpoint:
                patch = profile_overlay(model='fixture-model', protocol='deepseek_messages', endpoint=endpoint,
                    prompt='Synthetic delivery test.', context_window=64000, output_tokens=2048,
                    summary_tokens=2048, reasoning='high', dispatch_plugin=Path(__file__).resolve().parents[2]/'integrations/deepseek-harness/dispatch.mjs',
                    business_mcp={'Authorization': 'Bearer '+token})
                next(p['config'] for p in patch if p.get('id') == 'compaction-basic').update(headroomTokens=2048, retainTokens=256)
                patch_path = tmp_path/'profile.json'
                patch_path.write_text(json.dumps(patch), encoding='utf8')
                storage = {k: os.environ[k] for k in ['FINSIGHT_HARNESS_NATIVE_STORAGE_ROOT'] if k in os.environ}
                env = process_environment(storage, tmp_path/'session', token)
                async with admitted_acp_session(binary=os.environ['FIN_TEST_DSH_BINARY'],
                        arguments=['--profile', 'sdk-minimal', '--patch', str(patch_path)], environment=env,
                        directory=tmp_path/'session', binding={'task': task_id}, run_id=run_id,
                        authority=lambda: grant, stop=bridge.stop, mcp_servers=[]) as active:
                    result = await asyncio.wait_for(active.prompt('Deliver version 10.'), 90)
                    assert result['status'] == 'completed'
                    assert len(requests) == 1
                    receipts = [m for m in (await bridge.state())['messages'] if m.type == 'tool']
                    assert len(receipts) == 1 and receipts[0].status == 'success'
