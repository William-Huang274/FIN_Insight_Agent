"""Real SQLite/HTTP and native pre-transport boundaries, zero provider calls."""
import asyncio
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from test_project_library import app_at, index, WRITE as AUTH_WRITE, PROJECT
from test_project_research_materials import prepared, WRITE
from test_project_financial_facts import mapped_task, query
from test_model_dispatch_guard import boundary, response
from test_project_report_assets import prepared as report_prepared, save as save_report
from sec_agent.research_foundation.project_asset_access import (
    ProjectAssetUnavailable, require_task_assets, task_source_dependencies,
)
from sec_agent.research_foundation.project_library import ProjectLibrary
from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest


def test_access_endpoint_owner_csrf_tombstone_and_restore(tmp_path, monkeypatch):
    client = TestClient(app_at(tmp_path, monkeypatch))
    assert client.put('/api/v1/projects', headers=AUTH_WRITE, json=index()).status_code == 200
    doc = client.post(f'/api/v1/projects/{PROJECT}/documents', headers={**AUTH_WRITE, 'X-File-Name': 'private.txt'}, content=b'confidential-body').json()
    base = f"/api/v1/projects/{PROJECT}/documents/{doc['document_id']}"
    access = f"/api/v1/projects/{PROJECT}/assets/document/{doc['document_id']}/access"
    bob = {**AUTH_WRITE, 'Authorization': 'Bearer bob'}
    client.put('/api/v1/projects', headers=bob, json=index())
    assert client.put(access, headers=bob, json={'revoked': True}).status_code == 404
    assert client.put(access, headers={**AUTH_WRITE, 'Origin': 'https://foreign.invalid'}, json={'revoked': True}).status_code == 403
    assert client.put(access, headers=AUTH_WRITE, json={'revoked': True, 'owner': 'bob'}).status_code == 422
    assert client.put(access, headers=AUTH_WRITE, json={'revoked': True}).json()['access_status'] == 'revoked'
    assert client.get(base, headers=AUTH_WRITE).status_code == 409
    assert client.get(base+'/download', headers=AUTH_WRITE).status_code == 409
    rows = client.get(f'/api/v1/projects/{PROJECT}/documents', headers=AUTH_WRITE).json()['items']
    assert rows[0]['excerpt'] == '' and rows[0]['access_status'] == 'revoked'
    assert client.get(f'/api/v1/projects/{PROJECT}/documents?query=confidential-body', headers=AUTH_WRITE).json()['items'] == []
    assert client.put(access, headers=AUTH_WRITE, json={'revoked': False}).status_code == 200
    assert client.get(base+'/download', headers=AUTH_WRITE).content == b'confidential-body'
    library = ProjectLibrary(tmp_path)
    with library.documents.connect() as db:
        assert [r[0] for r in db.execute('SELECT revoked FROM project_asset_access ORDER BY rowid')] == [1, 0]


def test_existing_task_copy_catalog_download_start_and_legacy_origin_are_guarded(tmp_path):
    app, service, calls, tid, library, project, doc, body = prepared(tmp_path)
    client = TestClient(app)
    assert client.post('/api/v1/research-sessions', headers=WRITE, json=body).status_code == 200
    copied = service.attachment_store.list(tid)[0]['document_id']
    reader = TaskAttachmentStore(service.attachment_store.root)
    original = reader.get(tid, copied)['body']
    # Same objects remain alive while a separate DB instance changes authority.
    library.set_access('local-pilot', project, 'document', doc['document_id'], True)
    assert reader.list(tid)[0]['access_status'] == 'revoked'
    for request in [SourceDocumentRequest(source_space='uploads', operation='catalog', document_id=None),
                    SourceDocumentRequest(source_space='uploads', operation='read', document_id=copied)]:
        with pytest.raises(ProjectAssetUnavailable):
            asyncio.run(reader.read(thread_id=tid, request=request))
    assert client.get(f'/api/v1/research-sessions/{tid}/attachments/{copied}').status_code != 200
    assert client.post(f'/api/v1/research-sessions/{tid}/start', headers=WRITE).status_code == 409
    assert client.get(f'/api/v1/research-sessions/{tid}').json()['project_access_error']
    assert not any(c[0] == 'run' for c in calls)
    # Additive migration: old document origins can resolve the globally unique ID.
    with reader.connect() as db:
        origin = json.loads(db.execute('SELECT origin FROM attachment_origins WHERE object_id=?', (copied,)).fetchone()[0])
        origin.pop('source_scope')
        db.execute('UPDATE attachment_origins SET origin=? WHERE object_id=?', (json.dumps(origin), copied))
        db.execute('DROP TABLE task_project_stores')
    with pytest.raises(ProjectAssetUnavailable): reader.get(tid, copied)
    library.set_access('local-pilot', project, 'document', doc['document_id'], False)
    assert reader.get(tid, copied)['body'] == original
    # Permission-store outages must not be reported as public non-disclosure.
    old = library.documents.path
    offline = old.with_suffix('.offline')
    old.rename(offline)
    try:
        with pytest.raises(ProjectAssetUnavailable): reader.get(tid, copied)
        assert not old.exists()
    finally:
        offline.rename(old)


def test_financial_copy_and_task_start_follow_sec_revocation(mapped_task):
    client, service, calls, tid, sec, project, version, request = mapped_task
    assert client.post('/api/v1/research-sessions', headers=WRITE, json=request).status_code == 200
    url = f'/api/v1/research-sessions/{tid}/financial-facts'
    assert client.post(url, headers=WRITE, json=query()).status_code == 200
    sec.library.set_access('local-pilot', project, 'sec', version, True)
    assert sec.versions('local-pilot', project)['items'][0]['access_status'] == 'revoked'
    with pytest.raises(ProjectAssetUnavailable): sec.raw('local-pilot', project, version, 'sec_companyfacts')
    assert client.post(url, headers=WRITE, json=query()).status_code == 409
    assert client.post(f'/api/v1/research-sessions/{tid}/start', headers=WRITE).status_code == 409
    sec.library.set_access('local-pilot', project, 'sec', version, False)
    assert client.post(url, headers=WRITE, json=query()).status_code == 200
    assert not any(c[0] == 'run' for c in calls)


def test_existing_native_audit_blocks_cached_context_before_reservation(tmp_path, boundary):
    app, service, calls, tid, library, project, doc, body = prepared(tmp_path)
    assert TestClient(app).post('/api/v1/research-sessions', headers=WRITE, json=body).status_code == 200
    audit = boundary.audit
    audit.source_access_check = lambda: require_task_assets(service.attachment_store, tid)
    transmitted = []
    async def handler(request):
        transmitted.append(True)
        return response()
    asyncio.run(audit.awrap_model_call(boundary.request, handler))
    prior = boundary.store.reserve.call_count
    library.set_access('local-pilot', project, 'document', doc['document_id'], True)
    with pytest.raises(ProjectAssetUnavailable):
        asyncio.run(audit.awrap_model_call(boundary.request, handler))
    assert len(transmitted) == 1 and boundary.store.reserve.call_count == prior
    assert boundary.public[-1]['provider_call_attempted'] is False


def test_saved_report_dependencies_cannot_launder_revoked_source(tmp_path):
    app, service, calls, tid, library, project, doc, body = prepared(tmp_path)
    assert TestClient(app).post('/api/v1/research-sessions', headers=WRITE, json=body).status_code == 200
    origin = {'thread_id': tid, 'report_version': 1, 'report_digest': 'a'*64,
              'phase': 'human_completed', 'human_edit_count': 1,
              'source_dependencies': task_source_dependencies(service.attachment_store, tid)}
    scope = library.scope('local-pilot', project)
    report = library.documents.add(scope, 'report.md', b'Saved research based on selected source', research_origin=origin)
    next_task = str(uuid4())
    copied = service.attachment_store.copy_project_materials(next_task, project, [library.documents.get(scope, report['document_id'])])[0]
    library.set_access('local-pilot', project, 'document', doc['document_id'], True)
    with pytest.raises(ProjectAssetUnavailable): library.documents.get(scope, report['document_id'])
    with pytest.raises(ProjectAssetUnavailable): service.attachment_store.get(next_task, copied['document_id'])
    assert library.search('local-pilot', project, 'Saved research')['items'] == []
    library.set_access('local-pilot', project, 'document', doc['document_id'], False)
    assert service.attachment_store.get(next_task, copied['document_id'])['body'] == b'Saved research based on selected source'


def test_sync_model_adapter_rechecks_existing_object(tmp_path):
    from test_deepseek_structured_agents import _config, _models, _planner_request
    from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentAdapter
    app, service, calls, tid, library, project, doc, body = prepared(tmp_path)
    assert TestClient(app).post('/api/v1/research-sessions', headers=WRITE, json=body).status_code == 200
    models = _models()
    events = []
    adapter = DeepSeekStructuredAgentAdapter(config=_config(), chat_models=models, audit_sink=events.append,
        source_access_check=lambda: require_task_assets(service.attachment_store, tid))
    adapter.planner(_planner_request())
    assert models['planner'].calls == 1
    library.set_access('local-pilot', project, 'document', doc['document_id'], True)
    with pytest.raises(ProjectAssetUnavailable): adapter.planner(_planner_request())
    assert models['planner'].calls == 1
    outcomes = {e['call_id']: e for e in events if e['event'] == 'outcome'}
    assert len(outcomes) == 2  # Blocking a repeated request must not erase its prior billed outcome.
    assert sum(e.get('total_tokens', 0) for e in outcomes.values()) == 138
    assert sum(e.get('provider_call_attempted') is False for e in outcomes.values()) == 1


def test_report_save_api_records_host_dependencies_and_refuses_new_export_after_revocation(report_prepared):
    from test_project_library import THREAD
    client, state, library = report_prepared
    scope = library.scope('alice', PROJECT)
    source = library.documents.add(scope, 'source.txt', b'selected source for report')
    store = TaskAttachmentStore(library.documents.root/'attachments')
    store.copy_project_materials(THREAD, PROJECT, [library.documents.get(scope, source['document_id'])])
    saved = save_report(client, state)
    assert saved.status_code == 200, saved.text
    origin = saved.json()['project_origin']['research_origin']
    assert origin['source_dependencies'][0]['document_id'] == source['document_id']
    assert '_source_store' not in saved.text and 'task_project_stores' not in saved.text
    library.set_access('alice', PROJECT, 'document', source['document_id'], True)
    assert save_report(client, state).status_code == 409
    with pytest.raises(ProjectAssetUnavailable): library.documents.get(scope, saved.json()['document_id'])


@pytest.mark.local_data_integration
def test_open_mcp_connection_rechecks_sec_version_and_rejects_cached_source_tools(mapped_task):
    from mcp import Client
    from local_research_resources import RUNTIME_ENVIRONMENT, _assert_assets
    from sec_agent.agent_runtime.agent_server_data_composition import open_approved_data_composition, APPROVED_DATA_SNAPSHOT_ID
    _assert_assets()
    client, service, calls, tid, sec, project, version, request = mapped_task
    assert client.post('/api/v1/research-sessions', headers=WRITE, json=request).status_code == 200
    environment = {**RUNTIME_ENVIRONMENT, 'FINSIGHT_TASK_ATTACHMENTS_ROOT': str(service.attachment_store.root), 'FINSIGHT_TASK_THREAD_ID': tid}
    with open_approved_data_composition(run_invocation_id='revocation-'+tid, environment=environment, source_read_enabled=True) as composition:
        async def exercise():
            async with Client(composition.mcp_server, raise_exceptions=False) as mcp:
                binding = await mcp.call_tool('get_dell_research_method', {'branch_ids': ['Q1_ISSUER_TRUTH'],
                    'research_as_of': '2026-09-02T00:00:00Z', 'data_snapshot_id': APPROVED_DATA_SNAPSHOT_ID, 'execution_attempt_id': 'revocation-'+tid})
                assert not binding.is_error
                arguments = {**query(), 'branch_id': 'Q1_ISSUER_TRUTH', 'run_scope': binding.structured_content['run_scope']}
                before = await mcp.call_tool('query_company_financial_facts', arguments)
                assert not before.is_error, before
                sec.library.set_access('local-pilot', project, 'sec', version, True)
                blocked = await mcp.call_tool('query_company_financial_facts', arguments)
                assert blocked.is_error and '撤销' in str(blocked.content)
                # Middleware precedes argument validation/cache access, including source calculators.
                tools = await mcp.list_tools()
                cached_tool = next(t.name for t in tools.tools if 'calculate' in t.name)
                cached = await mcp.call_tool(cached_tool, {})
                assert cached.is_error and '撤销' in str(cached.content)
                sec.library.set_access('local-pilot', project, 'sec', version, False)
                after = await mcp.call_tool('query_company_financial_facts', arguments)
                assert not after.is_error and before.structured_content == after.structured_content
        asyncio.run(exercise())
