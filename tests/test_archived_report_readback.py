"""Retired native graph remains readable but cannot silently resume paid work."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from sec_agent.agent_runtime.dell_report_session import archived_report_session_graph
from test_research_session_bff import _app, GRAPH


def test_archive_schema_is_available_without_loading_model_or_old_materials():
    async def run():
        async with archived_report_session_graph({}, SimpleNamespace(execution_runtime=None)) as graph:
            assert 'report' in graph.channels
            assert 'human_review' in graph.nodes
        with pytest.raises(RuntimeError, match='archived_report_is_read_only'):
            async with archived_report_session_graph({}, SimpleNamespace(execution_runtime=object())):
                pytest.fail('retired executor was re-enabled')
    asyncio.run(run())


def test_archive_readback_disables_writes_before_creating_a_run():
    app, service, calls, tid = _app(graph_id=GRAPH)
    service.artifacts = None
    owned = service.owned_thread
    async def thread(t):
        value = await owned(t)
        value['metadata']['graph_id'] = GRAPH
        return value
    service.owned_thread = thread
    with TestClient(app) as client:
        response = client.get(f'/api/v1/research-sessions/{tid}')
        assert response.status_code == 200
        state = response.json()
        assert state['archive_notice'] and not state['can_respond']
        assert not state['can_accept'] and not state['can_manual_complete']
        for suffix, body in [('actions', {'action': 'ask', 'message': 'Continue'}),
                             ('abandon-question', {}), ('remember', {})]:
            result = client.post(f'/api/v1/research-sessions/{tid}/{suffix}', json=body,
                                 headers={'x-workbench-request': '1'})
            assert result.status_code == 409
        assert not calls
