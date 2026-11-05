import base64
from hashlib import sha256
import json
from copy import deepcopy

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sec_agent.agent_runtime.harness_legacy_import import legacy_receipts
from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools


@pytest.fixture
def anyio_backend():
    return 'asyncio'


def exported(tmp_path):
    state = {'question': 'Original question', 'request_summary': 'Untrusted old conclusion',
        'messages': [HumanMessage(id='q',content='Original question'),
            AIMessage(id='a',content='',tool_calls=[{'id':'read1','name':'source','args':{}}]),
            ToolMessage(id='t',tool_call_id='read1',name='source',content='Exact original',artifact={'source_id':'SOURCE::1'})]}
    kind, blob = JsonPlusSerializer().dumps_typed(state)
    path=tmp_path/'export.json'
    path.write_text(json.dumps({'type':kind,'blob':base64.b64encode(blob).decode()}))
    binding={'execution_id':'task','manifest_digest':'release','path':str(path),'sha256':sha256(path.read_bytes()).hexdigest(),
        'source_checkpoint':{'checkpoint_ns':'work|parent','checkpoint_id':'old'}}
    grant={'execution_id':'task','manifest_digest':'release','question':'Original question'}
    return state,binding,grant


def test_root_checkpoint_namespace_is_explicit(tmp_path):
    _, binding, grant = exported(tmp_path)
    binding['source_checkpoint']['checkpoint_ns'] = ''
    assert legacy_receipts(binding, grant=grant)['messages']
    del binding['source_checkpoint']['checkpoint_ns']
    with pytest.raises(ValueError, match='checkpoint_required'):
        legacy_receipts(binding, grant=grant)


@pytest.mark.anyio
async def test_explicit_import_preserves_sources_once_without_old_summary(tmp_path):
    original,binding,grant=exported(tmp_path)
    imported=legacy_receipts(binding,grant=grant)
    assert 'request_summary' not in imported
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'tools.sqlite')) as saver:
        bridge=HarnessBusinessTools(grants=[],checkpointer=saver,thread_id='task',check=lambda:None)
        await bridge.initialize({'question':'Original question','messages':[original['messages'][0]]})
        await bridge.import_receipts(imported)
        await bridge.import_receipts(imported)
        saved=await bridge.state()
        assert saved['messages']==original['messages']
        assert saved['messages'][-1].artifact=={'source_id':'SOURCE::1'}
        changed={**imported,'harness_import_digest':'different'}
        with pytest.raises(ValueError,match='identity_changed'):
            await bridge.import_receipts(changed)


def test_import_rejects_wrong_identity_question_or_bytes(tmp_path):
    _,binding,grant=exported(tmp_path)
    for bad in [{**grant,'execution_id':'other'},{**grant,'question':'another question'}]:
        with pytest.raises(ValueError):legacy_receipts(binding,grant=bad)
    with pytest.raises(ValueError,match='digest'):
        legacy_receipts({**binding,'sha256':'changed'},grant=grant)
