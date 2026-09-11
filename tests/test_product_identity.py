"""Resource ownership tests; IdP signatures are tested separately and live."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest
from starlette.authentication import AuthenticationBackend, AuthCredentials, SimpleUser

from apps.workbench.backend.authentication import install_conversation_auth, service_owner
from apps.workbench.backend.api.v1.report_sessions import ReportSessionService, build_report_sessions_router


class TestIdentity(AuthenticationBackend):
    async def authenticate(self, conn):
        if conn.headers.get('authorization') in ('alice', 'bob'):
            return AuthCredentials(['authenticated']), SimpleUser(conn.headers['authorization'])


@pytest.fixture
def product(monkeypatch):
    monkeypatch.setenv('FINSIGHT_AUTH_MODE', 'oidc_product')
    monkeypatch.delenv('FINSIGHT_OIDC_CLIENT_ID', raising=False)
    threads, assistants, calls = {}, {}, []
    async def create(**kwargs):
        await asyncio.sleep(.001)
        tid = str(uuid4())
        row = {'thread_id': tid, 'metadata': kwargs['metadata'], 'updated_at': '', 'status': 'idle'}
        threads[tid] = row
        return deepcopy(row)
    async def get(tid):
        await asyncio.sleep(.001)
        return deepcopy(threads[tid])
    async def search(**kwargs): return list(threads.values())
    async def acreate(graph, **kwargs):
        aid = kwargs['assistant_id']
        assistants[aid] = {**kwargs, 'graph_id': graph, 'created_at': ''}
        return deepcopy(assistants[aid])
    async def aget(aid): return deepcopy(assistants[aid])
    async def asearch(**kwargs): return list(assistants.values())
    sdk = SimpleNamespace(threads=SimpleNamespace(create=create, get=get, search=search),
        assistants=SimpleNamespace(create=acreate, get=aget, search=asearch), runs=SimpleNamespace(create=AsyncMock()))
    service = ReportSessionService('http://127.0.0.1:18165', None, sdk=sdk,
        research_profile={'default_question': 'Read the financial disclosure.', 'branch_topics': []})
    app = FastAPI()
    app.include_router(build_report_sessions_router(service), prefix='/api/v1')
    install_conversation_auth(app, backend=TestIdentity())
    with TestClient(app) as client:
        yield client, threads, assistants, app
    asyncio.run(service.http.aclose())


def create(client, owner):
    response = client.post('/api/v1/research-sessions', headers={'Authorization': owner, 'X-Workbench-Request': '1'},
        json={'title': 'private research', 'mode': 'research', 'question': 'Compare annual revenues.', 'defer_start': True})
    assert response.status_code == 200, response.text
    return response.json()['thread_id']


@pytest.mark.parametrize('suffix', ['', '/attachments', '/report-versions', '/working-notes', '/manual-review', '/user-context'])
def test_report_resources_reject_foreign_owner_before_state_or_files(product, suffix):
    client, threads, _, _ = product
    tid = create(client, 'alice')
    response = client.get('/api/v1/research-sessions/'+tid+suffix, headers={'Authorization': 'bob'})
    assert response.status_code == 404, response.text
    assert threads[tid]['metadata']['owner_id'] == 'alice'


def test_lists_and_studio_versions_are_owned_and_legacy_is_not_claimed(product):
    from sec_agent.agent_runtime.studio_configuration import default_configuration
    client, threads, assistants, _ = product
    a, b = create(client, 'alice'), create(client, 'bob')
    assert [r['thread_id'] for r in client.get('/api/v1/research-sessions', headers={'Authorization': 'alice'}).json()] == [a]
    response = client.post('/api/v1/research-studio/configurations', headers={'Authorization': 'alice', 'X-Workbench-Request': '1'},
        json=default_configuration().model_dump(mode='json'))
    assert response.status_code == 200, response.text
    aid = response.json()['assistant_id']
    assert client.get('/api/v1/research-studio/configurations/'+aid, headers={'Authorization': 'bob'}).status_code == 404
    assert client.get('/api/v1/research-studio/configurations', headers={'Authorization': 'bob'}).json()['versions'] == []
    del threads[a]['metadata']['owner_id']
    assert client.get('/api/v1/research-sessions/'+a, headers={'Authorization': 'alice'}).status_code == 404
    assert service_owner() == 'local-pilot'


def test_concurrent_requests_do_not_mix_principals(product):
    _, threads, _, app = product
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver') as c:
            async def create_one(name):
                r = await c.post('/api/v1/research-sessions', headers={'Authorization': name, 'X-Workbench-Request': '1'},
                    json={'title': name, 'mode': 'research', 'question': 'Compare annual revenues.', 'defer_start': True})
                assert r.status_code == 200
                return r.json()['thread_id'], name
            for tid, name in await asyncio.gather(*(create_one(n) for n in ['alice', 'bob']*4)):
                assert threads[tid]['metadata']['owner_id'] == name
    asyncio.run(run())


def test_native_memory_identity_is_scoped_and_reset(tmp_path, monkeypatch):
    from sec_agent.agent_runtime.working_memory_tools import native_memory_scope, memory_for
    monkeypatch.setenv('FINSIGHT_AUTH_MODE', 'oidc_product')
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH', str(tmp_path/'notes.sqlite'))
    config = {'configurable': {'thread_id': 'task'}}
    with native_memory_scope('alice', 'task'):
        memory_for(config, 'researcher').save('private', 'alice-only')
        with pytest.raises(ValueError, match='thread_scope_mismatch'):
            memory_for({'configurable': {'thread_id': 'another'}}, 'researcher')
    with pytest.raises(ValueError, match='verified_owner'):
        memory_for(config, 'researcher')
