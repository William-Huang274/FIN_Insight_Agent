"""Offline qualification of the fixture itself; not native server evidence."""
import asyncio
import importlib
import json
import socket
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command


def test_deterministic_fixture_has_no_network_and_preserves_execution(monkeypatch, tmp_path):
    monkeypatch.setenv('FIN_INTAKE_NATIVE_QUALIFICATION', '1')
    monkeypatch.setenv('FIN_PROBE_EVIDENCE', str(tmp_path))
    monkeypatch.setenv('FIN_PROBE_AUDIT', str(tmp_path / 'calls'))
    module = importlib.import_module('tests.integration.fixtures.intake_native_graph')
    def forbidden(*args, **kwargs):
        raise AssertionError('fixture attempted network transport')
    async def run():
        # Windows creates its loop wakeup socket pair before graph execution.
        monkeypatch.setattr(socket.socket, 'connect', forbidden)
        monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)
        tid, first, second = str(uuid4()), str(uuid4()), str(uuid4())
        execution = {'mode': 'auto', 'model': 'default', 'branch_ids': [], 'continuation_scope': 'original_plan'}
        config = {'configurable': {'thread_id': tid, 'run_id': first, 'finsight_execution': execution}}
        graph = module.builder.compile(checkpointer=InMemorySaver())
        await graph.ainvoke({'question': 'Synthetic offline test'}, config)
        paused = await graph.aget_state(config)
        assert paused.next == ('handoff',) and paused.values['prepared']
        await graph.ainvoke(Command(resume={'action': 'continue_remaining'}),
            {'configurable': {**config['configurable'], 'run_id': second}})
        result = await graph.aget_state(config)
        assert result.next == ('human_review',)
        assert result.values['report_version'] == 1
        assert result.values['execution_seen'] == execution
        assert (await graph.aget_state(paused.config)).values == paused.values
        rows = [json.loads(line) for line in (tmp_path / 'graph-events.jsonl').read_text().splitlines()]
        assert sum(r['phase'] == 'prepared' for r in rows) == 1
        assert all(r['provider_calls'] == 0 for r in rows)
        assert {r['run_id'] for r in rows} == {first, second}
        for rid in (first, second):
            audit = [json.loads(line) for line in (tmp_path / 'calls' / tid / rid / 'model-call-events.jsonl').read_text().splitlines()]
            assert all(r['provider_call_attempted'] is False and 'total_tokens' not in r for r in audit)
    asyncio.run(run())
