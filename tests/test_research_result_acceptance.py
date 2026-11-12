import json
from types import SimpleNamespace
from contextlib import nullcontext

import pytest
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from sec_agent.agent_runtime.harness_consultations import HarnessConsultations
from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
from sec_agent.agent_runtime.research_result_acceptance import result_version


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
async def test_acceptance_exact_version_restore_reopen_and_original_readback(tmp_path):
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'state.sqlite')) as saver:
        service = HarnessConsultations(directory=tmp_path/'jobs', saver=saver, grants=[], tid='t', rid='r',
            check=lambda:None, scope=nullcontext, budget=object(), environment={}, model='fixture',
            basis={}, as_of='2026-11-12', public_sink=lambda x:None)
        bridge = HarnessBusinessTools(grants=service.tools(), checkpointer=saver, thread_id='t', check=lambda:None)
        service.parent = bridge
        key = 'a'*64
        record = {'request': {'purpose':'investigate', 'report':None}, 'status':'completed',
                  'opinion':'Full retained evidence '*1000}
        path = service.directory/(key+'.json')
        path.write_text(json.dumps(record), encoding='utf8')
        await bridge.initialize({'question':'Decision', 'messages':[]})
        args = dict(task_id=key, result_digest=result_version(record), disposition='accepted',
            finding='A conditional positive finding.', scope_and_conditions='2027; MW; assumed half-year ramp.',
            counterevidence='Customer cancellations could weaken it.', unresolved='Utilization not disclosed.',
            evidence_receipt_ids=['missing'])
        assert not json.loads((await bridge.execute('assess_research_result', args)).content)['decision_recorded']
        original = await bridge.execute('read_research_agent_result', {'task_id':key})
        args['evidence_receipt_ids'] = [original.tool_call_id]
        before = await service.context_projection([{'receipt_id':original.tool_call_id}])
        assert before == {'replacements':[]}
        await bridge.execute('assess_research_result', args)
        projection = await service.context_projection([{'receipt_id':original.tool_call_id}])
        compact = projection['replacements'][0]['receipt']
        assert compact['result']['acceptance']['unresolved'] == 'Utilization not disclosed.'
        assert compact['original_readback']['arguments']['tool_call_id'] == original.tool_call_id
        assert 'Full retained evidence' not in json.dumps(compact)
        # New reader/process uses durable checkpoint decisions, not an in-memory flag.
        service.parent = HarnessBusinessTools(grants=service.tools(), checkpointer=saver, thread_id='t', check=lambda:None)
        assert await service.context_projection([{'receipt_id':original.tool_call_id}]) == projection
        unchanged = next(m for m in (await bridge.state())['messages'] if isinstance(m, ToolMessage) and m.tool_call_id == original.tool_call_id)
        assert unchanged.content == original.content
        # Failed reassessment cannot revoke a valid decision.
        bad = await bridge.execute('assess_research_result', {**args, 'result_digest':'wrong'})
        assert not json.loads(bad.content)['decision_recorded']
        assert await service.context_projection([{'receipt_id':original.tool_call_id}]) == projection
        await bridge.execute('assess_research_result', {**args, 'disposition':'reopened'})
        restored = await service.context_projection([{'receipt_id':original.tool_call_id, 'retired':True}])
        assert restored['replacements'][0]['receipt']['result']['opinion'] == record['opinion']
        await bridge.execute('assess_research_result', args)
        record['opinion'] += ' materially changed'
        path.write_text(json.dumps(record), encoding='utf8')
        stale = await service.context_projection([{'receipt_id':original.tool_call_id, 'retired':True}])
        assert 'no longer current' in stale['replacements'][0]['receipt']['context_notice']
        assert not (await service.context_projection([{'receipt_id':'forged'}]))['replacements']
        with pytest.raises(RuntimeError, match='original_receipt_missing'):
            await service.context_projection([{'receipt_id':'missing', 'retired':True}])
