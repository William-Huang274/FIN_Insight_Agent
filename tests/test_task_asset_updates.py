"""Source revision lifecycle against real SQLite and BFF; no paid requests."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from test_asset_workspace import setup, selection, context
from test_project_research_materials import WRITE
from sec_agent.research_foundation.task_asset_updates import (
    TaskAssetUpdates, TaskAssetView, AssetUpdateRequest, asset_update_prompt,
)
from sec_agent.research_foundation.asset_workspace import AssetConflict
from sec_agent.research_foundation.project_asset_access import require_task_assets
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from apps.workbench.backend.api.v1.research_studio import run_configuration
from test_project_financial_facts import mapped_task


def task(tmp_path):
    client, service, calls, tid, workspace, project = setup(tmp_path)
    ref = selection(workspace, project)
    saved = context(client, ref)
    assert client.post('/api/v1/research-sessions', headers=WRITE, json={
        'mode': 'research', 'defer_start': True, 'asset_context_id': saved['context_id']}).status_code == 200
    thread = asyncio.run(service.sdk.threads.get(tid))
    return client, service, calls, tid, workspace, project, ref, thread


def edit(client, project, ref, text='New user assumption: revenue 150; period still needs checking.'):
    response = client.post('/api/v1/asset-workspace/documents', headers=WRITE, json={
        'project_id': project, 'base_ref': ref, 'title': 'Updated.md', 'text': text})
    assert response.status_code == 200, response.text


def current(workspace, project, ref):
    return next(a['current']['ref'] for a in workspace.catalog('local-pilot', project)['items'] if a['asset_id'] == ref['asset_id'])


def test_update_while_running_is_pinned_and_old_citations_survive(tmp_path):
    client, service, calls, tid, workspace, project, ref, thread = task(tmp_path)
    updates = TaskAssetUpdates(service.attachment_store.root)
    old_id = service.attachment_store.list(tid)[0]['document_id']
    first = str(uuid4()); updates.pin(tid, first, 0)
    old_view = TaskAssetView(updates.store.root, tid, first)
    old_bytes = old_view.get(tid, old_id)['body']
    submitted_config = asyncio.run(run_configuration(service, thread))
    edit(client, project, ref)
    new = current(workspace, project, ref)
    thread['status'] = 'busy'
    endpoint = f'/api/v1/research-sessions/{tid}/asset-updates'
    status = client.get(endpoint).json()
    assert status['items'][0]['has_newer'] and status['active_revision'] == 0
    payload = {'request_id': str(uuid4()), 'base_revision': 0, 'ref': new}
    response = client.post(endpoint, headers=WRITE, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()['revision'] == 1
    assert client.post(endpoint, headers=WRITE, json=payload).json() == response.json()
    assert client.get(endpoint).json()['pending']
    assert old_view.list(tid)[0]['document_id'] == old_id
    delayed = str(uuid4()); updates.pin(tid, delayed, submitted_config['configurable']['finsight_asset_revision'])
    assert TaskAssetView(updates.store.root, tid, delayed).get(tid, old_id)['body'] == old_bytes
    next_config = asyncio.run(run_configuration(service, thread))
    second = str(uuid4()); updates.pin(tid, second, next_config['configurable']['finsight_asset_revision'])
    view = TaskAssetView(updates.store.root, tid, second)
    assert not client.get(endpoint).json()['pending']
    active = view.list(tid)
    assert len(active) == 1 and active[0]['project_origin']['document_id'] == new['version_id']
    assert view.get(tid, old_id)['body'] == old_bytes
    read = asyncio.run(view.read(thread_id=tid, request=SourceDocumentRequest(
        source_space='uploads', operation='read', document_id=active[0]['document_id'])))
    assert '150' in read.items[0]['passage']
    assert tid in read.items[0]['source_url']
    assert '已完成复核' in asset_update_prompt(view) and new['version_id'] in asset_update_prompt(view)
    assert client.get(f'/api/v1/research-sessions/{tid}/attachments/{active[0]["document_id"]}').content == view.get(tid, active[0]['document_id'])['body']
    assert not any(c[0] == 'run' for c in calls)
    with pytest.raises(AssetConflict, match='immutable'):
        updates.pin(tid, second, 0)
    with pytest.raises(ValueError, match='current_task'):
        TaskAssetView(updates.store.root, str(uuid4())).get(str(uuid4()), active[0]['document_id'])
    workspace.library.set_access('local-pilot', project, 'document', new['version_id'], True)
    with pytest.raises(ValueError):
        require_task_assets(view, tid)
    assert old_view.get(tid, old_id)['body'] == old_bytes
    assert client.get(f'/api/v1/research-sessions/{tid}/attachments/{old_id}').content == old_bytes


def test_cas_conflicts_failed_preparation_and_unknown_request_remain_visible(tmp_path, monkeypatch):
    client, service, calls, tid, workspace, project, ref, thread = task(tmp_path)
    edit(client, project, ref)
    new = current(workspace, project, ref)
    updates = TaskAssetUpdates(service.attachment_store.root)
    payload = dict(base_revision=0, ref=new)
    def prepare(_):
        try:
            return TaskAssetUpdates(updates.store.root).prepare('local-pilot', tid, thread['metadata'],
                AssetUpdateRequest(request_id=uuid4(), **payload))['state']
        except AssetConflict:
            return 'conflict'
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(prepare, range(2))) == ['conflict', 'ready']
    edit(client, project, new, 'Third version requiring re-evaluation.')
    third = current(workspace, project, ref)
    from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
    def fail(*a, **k): raise OSError('private-path')
    monkeypatch.setattr(TaskAttachmentStore, 'copy_project_materials', fail)
    request = AssetUpdateRequest(request_id=uuid4(), base_revision=1, ref=third)
    with pytest.raises(OSError):
        updates.prepare('local-pilot', tid, thread['metadata'], request)
    assert updates.prepare('local-pilot', tid, thread['metadata'], request)['state'] == 'failed'
    assert updates.latest(tid)['revision'] == 1
    with pytest.raises(AssetConflict, match='not_ready'):
        updates.pin(tid, uuid4(), 2)
    assert not any(c[0] == 'run' for c in calls)


def test_legacy_task_backfill_and_foreign_selection_are_checked(tmp_path):
    from test_project_research_materials import prepared
    from fastapi.testclient import TestClient
    app, service, calls, tid, library, project, doc, body = prepared(tmp_path)
    client = TestClient(app)
    assert client.post('/api/v1/research-sessions', headers=WRITE, json=body).status_code == 200
    endpoint = f'/api/v1/research-sessions/{tid}/asset-updates'
    status = client.get(endpoint).json()
    assert status['supported'] and status['items'][0]['ref']['version_id'] == doc['document_id']
    forged = {**status['items'][0]['ref'], 'project_id': str(uuid4())}
    assert client.post(endpoint, headers=WRITE, json={'request_id': str(uuid4()), 'base_revision': 0, 'ref': forged}).status_code == 409
    assert client.post(endpoint, json={'request_id': str(uuid4()), 'base_revision': 0, 'ref': forged}).status_code == 403
    assert not any(c[0] == 'run' for c in calls)


def test_sec_versions_keep_old_marts_and_restore_bindings(mapped_task, tmp_path):
    import json
    import shutil
    from sec_agent.research_foundation.asset_workspace import AssetWorkspace
    from sec_agent.research_foundation.project_financial_facts import task_financial_snapshot
    from sec_agent.research_foundation.asset_set_backup import backup_asset_set, restore_asset_set
    client, service, calls, tid, sec, project, version, request = mapped_task
    assert client.post('/api/v1/research-sessions', headers=WRITE, json=request).status_code == 200
    original = task_financial_snapshot(service.attachment_store.root, tid)
    body, old_root = sec._saved('local-pilot', project, version)
    new_version = str(uuid4()); scope = sec.library.scope('local-pilot', project)
    # A second capture with identical disclosed values still has a distinct source version.
    shutil.copytree(old_root, sec.root / scope / new_version)
    body = {**body, 'version': new_version}
    with sec.library.documents.connect() as db:
        db.execute('INSERT INTO project_sec_versions VALUES(?,?,?)', (scope, new_version, json.dumps(body)))
    workspace = AssetWorkspace(sec.library.documents.root)
    new = next(v['ref'] for a in workspace.catalog('local-pilot', project)['items'] for v in a['versions'] if v['ref']['version_id'] == new_version)
    updates = TaskAssetUpdates(service.attachment_store.root)
    thread = asyncio.run(service.sdk.threads.get(tid))
    saved = updates.prepare('local-pilot', tid, thread['metadata'], AssetUpdateRequest(request_id=uuid4(), base_revision=0, ref=new))
    run = str(uuid4()); updates.pin(tid, run, saved['revision'])
    view = TaskAssetView(updates.store.root, tid, run)
    active = task_financial_snapshot(view.root, view.financial_scope)
    assert active[0] != original[0] and active[1]['project_origin']['sec_version'] == new_version
    assert task_financial_snapshot(view.root, tid)[1] == original[1]
    assert client.get(f'/api/v1/research-sessions/{tid}').json()['project_financial_data']['project_origin']['sec_version'] == new_version
    backup_asset_set(workspace.library.documents.root, view.root, tmp_path/'backup')
    restore_asset_set(tmp_path/'backup', tmp_path/'restored')
    # Original source tree unavailable: restored refs must use restored project storage.
    workspace.library.documents.root.rename(tmp_path/'original-offline')
    restored = TaskAssetView(tmp_path/'restored'/'attachments', tid, run)
    assert task_financial_snapshot(restored.root, restored.financial_scope)[1] == active[1]
    require_task_assets(restored, tid)
    assert not any(c[0] == 'run' for c in calls)


def test_bound_current_and_historical_uploads_survive_restore_and_missing_copy_fails(tmp_path):
    from sec_agent.research_foundation.asset_set_backup import backup_asset_set, restore_asset_set
    from sec_agent.research_foundation.project_asset_access import task_source_dependencies
    client, service, calls, tid, workspace, project, ref, thread = task(tmp_path)
    old = service.attachment_store.list(tid)[0]['document_id']
    edit(client, project, ref)
    updates = TaskAssetUpdates(service.attachment_store.root)
    result = updates.prepare('local-pilot', tid, thread['metadata'], AssetUpdateRequest(
        request_id=uuid4(), base_revision=0, ref=current(workspace, project, ref)))
    run = str(uuid4()); updates.pin(tid, run, 1)
    deps = task_source_dependencies(service.attachment_store, tid)
    assert {d['document_id'] for d in deps} == {ref['version_id'], result['body']['selected_ref']['version_id']}
    backup_asset_set(workspace.library.documents.root, updates.store.root, tmp_path/'backup')
    restore_asset_set(tmp_path/'backup', tmp_path/'restored')
    workspace.library.documents.root.rename(tmp_path/'original-offline')
    view = TaskAssetView(tmp_path/'restored'/'attachments', tid, run)
    assert b'150' in view.get(tid, view.list(tid)[0]['document_id'])['body']
    assert b'120' in view.get(tid, old)['body']
    with view.connect() as db:
        db.execute('DELETE FROM attachments WHERE thread=?', (view.financial_scope,))
    with pytest.raises(AssetConflict, match='incomplete'):
        TaskAssetView(view.root, tid, run)


def test_real_interactive_node_receives_update_guidance_and_current_tool_result(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from langchain_core.messages import HumanMessage
    from langchain_core.tools import tool
    from langgraph.graph import StateGraph, START, END
    from pydantic import SecretStr
    from test_report_synthesis_agent import NativeFixtureModel
    from test_case_review_agent import call
    from test_research_convergence import artifact_fixture
    from sec_agent.agent_runtime import research_session_runtime as runtime
    client, service, calls, tid, workspace, project, ref, thread = task(tmp_path)
    edit(client, project, ref)
    updates = TaskAssetUpdates(service.attachment_store.root)
    updates.prepare('local-pilot', tid, thread['metadata'], AssetUpdateRequest(
        request_id=uuid4(), base_revision=0, ref=current(workspace, project, ref)))
    run = str(uuid4()); updates.pin(tid, run, 1)
    view = TaskAssetView(updates.store.root, tid, run)
    artifacts = artifact_fixture()
    claim = 'P01:' + artifacts.read_paper('P01')['claims'][0]['claim_id']
    model = NativeFixtureModel(marker='asset-input-node', replies=[
        [call('read_current_material', {}, 'read')],
        [call('submit_case_answer', {'answer_markdown': f'Synthetic input wiring only, not financial acceptance. [{claim}]'}, 'answer')]])
    monkeypatch.setattr(runtime, 'case_chat_model', lambda *a, **k: model)
    monkeypatch.setattr(runtime, 'current_task_artifacts', lambda _: artifacts)
    @contextmanager
    def data(**kwargs):
        assert kwargs['environment']['FINSIGHT_TASK_RUN_ID'] == run
        yield SimpleNamespace(foundation_binding=SimpleNamespace(case_id=artifacts.case_id,research_as_of=artifacts.research_as_of,
            snapshot_id=artifacts.snapshot_id,foundation_digest=artifacts.foundation_digest),
            decision_digest=artifacts.owner_data_gate_decision_digest,inventory_snapshot_digest=artifacts.inventory_snapshot_digest,
            source_route_catalog_digest=artifacts.source_route_catalog_digest,mcp_server=None)
    class Client:
        def __init__(self,*a,**k): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*a): pass
        async def call_tool(self,*a,**k): return SimpleNamespace(is_error=False,structured_content={'run_scope':{}})
    @tool
    def read_current_material():
        """Read the actual pinned synthetic task source."""
        return view.get(tid, view.list(tid)[0]['document_id'])['body'].decode()
    monkeypatch.setattr(runtime, 'open_approved_data_composition', data)
    monkeypatch.setattr(runtime, 'Client', Client)
    monkeypatch.setattr(runtime, 'case_mcp_tools', AsyncMock(return_value=[read_current_material]))
    profile, case = runtime.load_research_runtime_profile(Path.cwd())
    profile['context_summarization']['enabled'] = False
    async def guidance(): return [{'message': asset_update_prompt(view)}]
    phases = runtime.create_research_phase_runnables(root=Path.cwd(), settings={'audit_root':str(tmp_path/'calls')},
        profile=profile, case=case, run_id=run, thread_id=tid, api_key=SecretStr('fixture-not-a-secret'),
        environment={'FINSIGHT_TASK_ATTACHMENTS_ROOT':str(view.root)}, public_sink=lambda _:None,
        private_sink=lambda _:None, read_guidance=guidance)
    graph = StateGraph(dict).add_node('writer', phases['quick_writer']).add_edge(START,'writer').add_edge('writer',END).compile()
    result = asyncio.run(graph.ainvoke({'messages':[HumanMessage(content='Read the updated assumption.')],
        'question':'Synthetic task', 'report':{}, 'revisions':{}, 'human_edits':[], 'conversation':[], 'request_action':'ask'}))
    assert result['output']['kind'] == 'answer'
    assert any('当前原生运行固定输入修订 r1' in str(m.content) for m in model.contexts[0])
    assert any('revenue 150' in str(m.content) for m in model.contexts[1])
    assert not any(c[0] == 'run' for c in calls)


def test_abandon_crashed_preparation_cannot_publish_late_or_block_new_choice(tmp_path, monkeypatch):
    from threading import Event
    from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
    client, service, calls, tid, workspace, project, ref, thread = task(tmp_path)
    edit(client, project, ref); new = current(workspace, project, ref)
    updates = TaskAssetUpdates(service.attachment_store.root)
    entered, released = Event(), Event()
    original = TaskAttachmentStore.copy_project_materials
    def slow(self, *a, **k):
        entered.set(); assert released.wait(10)
        return original(self, *a, **k)
    monkeypatch.setattr(TaskAttachmentStore, 'copy_project_materials', slow)
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(updates.prepare, 'local-pilot', tid, thread['metadata'], AssetUpdateRequest(request_id=uuid4(), base_revision=0, ref=new))
        assert entered.wait(10)
        try:
            response = client.post(f'/api/v1/research-sessions/{tid}/asset-updates/1/abandon', headers=WRITE)
            assert response.status_code == 200, response.text
        finally:
            released.set()
        with pytest.raises(AssetConflict, match='已放弃'):
            pending.result()
    assert updates.latest(tid) is None and updates.rows(tid)[0]['state'] == 'abandoned'
    result = updates.prepare('local-pilot', tid, thread['metadata'], AssetUpdateRequest(request_id=uuid4(), base_revision=0, ref=new))
    assert result['revision'] == 2 and result['state'] == 'ready'
    with pytest.raises(AssetConflict): updates.abandon_preparation(tid, 2)


def test_superseded_unadopted_copy_never_enters_current_or_old_run_tools(tmp_path):
    client, service, calls, tid, workspace, project, ref, thread = task(tmp_path)
    updates = TaskAssetUpdates(service.attachment_store.root)
    old_run = str(uuid4()); updates.pin(tid, old_run, 0)
    edit(client, project, ref); second = current(workspace, project, ref)
    unused = updates.prepare('local-pilot', tid, thread['metadata'], AssetUpdateRequest(request_id=uuid4(), base_revision=0, ref=second))
    unused_id = updates.store.list(unused['body']['scope'])[0]['document_id']
    edit(client, project, second, 'Third version selected before another run started.')
    updates.prepare('local-pilot', tid, thread['metadata'], AssetUpdateRequest(request_id=uuid4(), base_revision=1, ref=current(workspace, project, ref)))
    new_run = str(uuid4()); updates.pin(tid, new_run, 2)
    workspace.library.set_access('local-pilot', project, 'document', second['version_id'], True)
    view = TaskAssetView(updates.store.root, tid, new_run)
    require_task_assets(view, tid)
    with pytest.raises(ValueError, match='current_task'): view.get(tid, unused_id)
    old = TaskAssetView(updates.store.root, tid, old_run)
    with pytest.raises(ValueError, match='current_task'): old.get(tid, view.list(tid)[0]['document_id'])
