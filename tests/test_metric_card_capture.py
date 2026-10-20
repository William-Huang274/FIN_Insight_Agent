"""The browser submits card identity; the server pins full, exact source records."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from test_industry_foundation import foundation, publish
from test_financial_navigation import fact
from test_project_research_materials import prepared, WRITE
from apps.workbench.backend.api.v1.asset_workspace import build_asset_workspace_router
from apps.workbench.backend.api.v1.data_library import build_data_library_router
from sec_agent.research_foundation import derived_financials
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.metric_workspace import query_metrics
from sec_agent.research_foundation.reporting_periods import rebuild


@pytest.fixture
def capture_app(tmp_path, foundation):
    path, worker, sid = foundation
    fact(worker, sid, 'assets', 'Assets', 200, start=None)
    fact(worker, sid, 'liabilities', 'Liabilities', 40, start=None)
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        rebuild(db)
    derived_financials.materialize(path, '2026-09-21')
    publish(path, worker)
    app, service, calls, tid, library, project, _, _ = prepared(tmp_path/'runtime')
    app.include_router(build_data_library_router(tmp_path, research_library=path), prefix='/api/v1')
    app.include_router(build_asset_workspace_router(library.documents.root,
        attachments_root=tmp_path, research_library=path), prefix='/api/v1')
    record = query_metrics(path, ['NVIDIA'], section='history', metric='liabilities_to_assets')['items'][0]['id']
    with TestClient(app) as client:
        result = client.post('/api/v1/data-library/metrics/query', headers=WRITE,
            json={'entity_ids':['NVIDIA'], 'section':'card', 'record_id':record, 'as_of':'2026-09-21'})
        assert result.status_code == 200, result.text
        yield client, AssetWorkspace(library.documents.root), project, result.json(), path, worker
    assert not any(c[0] == 'run' for c in calls)


def test_full_card_save_replay_and_original_protection(capture_app):
    client, workspace, project, card, _, _ = capture_app
    body = {'project_id':project, 'title':'Exact historical ratio', 'selection':card['capture_selection']}
    response = client.post('/api/v1/asset-workspace/captures', headers=WRITE, json=body)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert client.post('/api/v1/asset-workspace/captures', headers=WRITE, json=body).json()['document_id'] == saved['document_id']
    ref = next(a['current']['ref'] for a in workspace.catalog('local-pilot', project)['items']
               if a['current']['ref']['version_id'] == saved['document_id'])
    capture = workspace.read('local-pilot', ref)['capture']
    assert capture['rows'] == card['items']
    assert len(capture['rows'][0]['inputs']) == 2
    assert capture['rows'][0]['value'] == '20.0'
    assert client.post('/api/v1/asset-workspace/documents', headers=WRITE,
        json={'project_id':project, 'base_ref':ref, 'title':'Forged', 'text':'value=90'}).status_code == 409
    with pytest.raises(KeyError):
        workspace.read('other-user', ref)


@pytest.mark.parametrize('change', [
    {'snapshot':'0'*64}, {'entity_id':'OTHER'}, {'record_id':'unknown'},
    {'as_of':'2020-01-01'}, {'value':'999'}, {'as_of':'bad-date'},
])
def test_tampered_or_unavailable_cards_never_save(capture_app, change):
    client, workspace, project, card, _, _ = capture_app
    before = workspace.catalog('local-pilot', project)
    response = client.post('/api/v1/asset-workspace/captures', headers=WRITE, json={
        'project_id':project, 'title':'Attempt', 'selection':{**card['capture_selection'], **change}})
    assert response.status_code in (409, 422), response.text
    assert workspace.catalog('local-pilot', project) == before


def test_release_change_requires_explicit_reselection(capture_app):
    client, workspace, project, card, path, worker = capture_app
    before = workspace.catalog('local-pilot', project)
    worker.sql("UPDATE snapshot_metadata SET value='changed' WHERE key='as_of'")
    # Re-publish a different valid release, keeping the selected numeric row identical.
    worker.sql("INSERT OR REPLACE INTO snapshot_metadata VALUES('capture_test_revision','2')")
    publish(path, worker)
    response = client.post('/api/v1/asset-workspace/captures', headers=WRITE, json={
        'project_id':project, 'title':'Stale browser', 'selection':card['capture_selection']})
    assert response.status_code == 409, response.text
    assert workspace.catalog('local-pilot', project) == before
