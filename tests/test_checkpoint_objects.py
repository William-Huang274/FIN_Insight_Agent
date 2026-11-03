import json
import os
import sqlite3
from decimal import Decimal

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from sec_agent.agent_runtime.checkpoint_objects import ObjectSerializer, business_checkpointer
from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
from sec_agent.agent_runtime.conversation_agent import GrantedTool
from sec_agent.agent_runtime.conversation_tools import conversation_tools


@pytest.fixture
def anyio_backend():
    return 'asyncio'


def test_exact_values_legacy_and_changed_objects(tmp_path):
    store = ObjectSerializer(tmp_path / 'objects.sqlite')
    value = {'source': 'PASSAGE::long', 'period': ('2025-01-01', '2025-12-31'),
             'amount': Decimal('120.000'), 'raw': b'\x00\xff', 3: {1, 2},
             'messages': [ToolMessage(content='source body' * 2000, artifact={'unit': 'USD'}, tool_call_id='same')],
             'unknown_usage': None, 'failed': True}
    old = store.base.dumps_typed(value)
    encoded = store.dumps_typed(value)
    assert len(encoded[1]) == 64
    assert store.loads_typed(encoded) == value
    assert store.loads_typed(old) == store.base.loads_typed(old)
    before = store.conn.execute('SELECT count(*) FROM objects').fetchone()[0]
    assert store.dumps_typed(value) == encoded
    assert store.conn.execute('SELECT count(*) FROM objects').fetchone()[0] == before
    store.close()
    store = ObjectSerializer(tmp_path / 'objects.sqlite')
    assert store.loads_typed(encoded) == value
    store.conn.execute('DELETE FROM objects WHERE digest=?', (encoded[1].decode(),)); store.conn.commit()
    with pytest.raises(ValueError, match='checkpoint_object_missing'):
        store.loads_typed(encoded)
    store.close()


def test_growth_and_replay_share_unchanged_payloads(tmp_path):
    store = ObjectSerializer(tmp_path / 'objects.sqlite')
    messages = []
    original_bytes = 0
    for i in range(40):
        messages.append(ToolMessage(content=os.urandom(16000).hex(), tool_call_id=str(i)))
        state = {'messages': messages, 'source_id': 'PASSAGE::test'}
        original_bytes += len(store.base.dumps_typed(state)[1])
        store.dumps_typed(state)
    stored = store.conn.execute('SELECT sum(length(payload)) FROM objects').fetchone()[0]
    assert stored < original_bytes / 8
    count = store.conn.execute('SELECT count(*) FROM objects').fetchone()[0]
    store.close()
    branch = ObjectSerializer(tmp_path / 'objects.sqlite')
    branch.dumps_typed(state)
    assert branch.conn.execute('SELECT count(*) FROM objects').fetchone()[0] == count
    branch.close()


@pytest.mark.anyio
async def test_actual_tools_restart_calculation_and_saved_readback(tmp_path):
    source = {'numeric_fact_id': 'NUMFACT::test', 'result_state': 'numeric_fact',
              'numeric_fact_authority': True, 'value_decimal': '120', 'unit': 'USD million',
              'ticker': 'TEST', 'period_start': '2025-01-01', 'period_end': '2025-12-31'}
    calls = []
    @tool(response_format='content_and_artifact')
    def query_financial_data():
        """Read the synthetic source."""
        calls.append(1)
        body = {'authority_state': 's2_numeric_fact_query_result', 'results': [{'status': 'resolved', 'facts': [source]}]}
        return json.dumps(body), body
    grants = [GrantedTool(query_financial_data, 'read', 'fixture')]
    grants += [g for g in conversation_tools(thread_id='fixture') if g.tool.name in {'calculate_research_metric', 'read_saved_result'}]
    path, objects = tmp_path/'checkpoint.sqlite', tmp_path/'objects.sqlite'
    async with business_checkpointer(path, object_path=objects) as saver:
        bridge = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='fixture', check=lambda:None)
        await bridge.initialize({'question': 'original', 'report_version': 7, 'messages': []})
        result = await bridge.execute('query_financial_data', {})
    async with business_checkpointer(path, object_path=objects) as saver:
        bridge = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='fixture', check=lambda:None)
        await bridge.initialize({'question':'must not replace'}, recovering=True)
        assert (await bridge.state())['report_version'] == 7
        metric = await bridge.execute('calculate_research_metric', {'request': {'expression':'revenue / 2',
            'operands':{'revenue':{'source_id':'NUMFACT::test'}}, 'result_unit':'USD million', 'rationale':'fixture'}})
        assert metric.status == 'success', metric.content
        assert metric.artifact['value_decimal'] == '60'
        read = await bridge.execute('read_saved_result', {'tool_call_id':result.tool_call_id})
        assert '120' in read.content
        assert calls == [1]


@pytest.mark.anyio
async def test_pending_write_recovery_is_not_silently_completed(tmp_path):
    @tool
    def write_object():
        """Write object fixture."""
        raise RuntimeError('interrupted')
    path, objects = tmp_path/'checkpoint.sqlite', tmp_path/'objects.sqlite'
    grants = [GrantedTool(write_object, 'task_artifact_write', 'fixture')]
    async with business_checkpointer(path, object_path=objects) as saver:
        bridge = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='fixture', check=lambda:None)
        await bridge.initialize({'question':'original', 'messages':[]})
        with pytest.raises(RuntimeError):
            await bridge.execute('write_object', {})
    async with business_checkpointer(path, object_path=objects) as saver:
        bridge = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='fixture', check=lambda:None)
        with pytest.raises(RuntimeError, match='reconcile_before_resume'):
            await bridge.initialize({}, recovering=True)


@pytest.mark.anyio
async def test_plain_checkpoint_migration_and_branch(tmp_path):
    from scripts.engineering.compact_business_checkpoints import compact
    from langgraph.graph import StateGraph, START, END
    from typing import TypedDict
    class State(TypedDict):
        body: str
        version: int
    graph = StateGraph(State)
    graph.add_node('work', lambda s: {'version':s['version']+1})
    graph.add_edge(START, 'work'); graph.add_edge('work', END)
    config = {'configurable':{'thread_id':'fixture'}}
    old, new, objects = tmp_path/'old.sqlite', tmp_path/'new.sqlite', tmp_path/'objects.sqlite'
    async with AsyncSqliteSaver.from_conn_string(str(old)) as saver:
        native = graph.compile(checkpointer=saver)
        await native.ainvoke({'body':'source'*10000,'version':0},config)
        snapshots = [s async for s in native.aget_state_history(config)]
    result = compact(old,new,objects)
    assert result['rows']['checkpoints'] > 0
    async with business_checkpointer(new,object_path=objects) as saver:
        migrated=graph.compile(checkpointer=saver)
        restored=[s async for s in migrated.aget_state_history(config)]
        assert [(s.values,s.next,s.config) for s in restored] == [(s.values,s.next,s.config) for s in snapshots]
        assert (await migrated.ainvoke({'version':3},config))['version'] == 4
