"""Organization custody and BFF authorization; real SQLite, no model calls."""
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from apps.workbench.backend.api.v1.asset_workspace import build_asset_workspace_router
from apps.workbench.backend.business_transport import build_business_gateway
from apps.workbench.backend.space_assets import SpaceAssets
from sec_agent.research_foundation.asset_workspace import AssetWorkspace, AssetConflict
from sec_agent.research_foundation.asset_backup import backup_assets, restore_assets
from test_project_library import app_at, index, PROJECT, WRITE
from test_project_source_captures import setup, selections, save, reference, source_library


def source_at(root):
    source = AssetWorkspace(root)
    source.library.save('alice', 0, {k:v for k,v in index().items() if k != 'revision'})
    source.library.documents.add(source.library.scope('alice', PROJECT), 'Original.md', b'Pinned original evidence.')
    return source, source.catalog('alice', PROJECT)['items'][0]['current']['ref']


def test_publication_is_independent_organization_copy_and_receipt_survives_reopen(tmp_path):
    source, ref = source_at(tmp_path/'original')
    org, space, resource = [str(uuid4()) for _ in range(3)]
    shared = SpaceAssets(tmp_path/'custody')
    binding = shared.publish(source, 'alice', resource, org, space, ref)
    assert binding['source_ref'] == ref and binding['resource_type'] == 'files'
    assert binding == SpaceAssets(tmp_path/'custody').publish(source, 'alice', resource, org, space, ref)
    assert len(shared.workspace.catalog('organization:'+org, space)['items']) == 1
    with pytest.raises((KeyError, ValueError)):
        shared.workspace.read('alice', binding['ref'])
    with pytest.raises(AssetConflict):
        shared.publish(source, 'alice', resource, org, str(uuid4()), ref)
    other_space = str(uuid4())
    other = shared.publish(source, 'alice', str(uuid4()), org, other_space, ref)
    assert shared.workspace.library.index('organization:'+org)['revision'] == 2
    assert other['ref']['project_id'] == other_space
    assert other['ref']['version_id'] != binding['ref']['version_id']
    assert shared.read(other)['text'] == 'Pinned original evidence.'
    source.library.documents.add(source.library.scope('alice', PROJECT), 'Original.md', b'Changed text.',
        revision={'parent': ref['version_id'], 'change_kind':'correction', 'note':'Updated original'})
    source.library.set_access('alice', PROJECT, 'document', ref['version_id'], True)
    # Explicit publication is independent of original withdrawal; Java controls it.
    result = SpaceAssets(tmp_path/'custody').read(binding)
    assert result['text'] == 'Pinned original evidence.' and result['editable'] is False
    assert result['publication']['organization_id'] == org
    with pytest.raises(ValueError):
        shared.publish(source, 'alice', str(uuid4()), org, space, ref)
    backup_assets(tmp_path/'custody', tmp_path/'backup')
    restore_assets(tmp_path/'backup', tmp_path/'restored')
    assert SpaceAssets(tmp_path/'restored').read(binding)['text'] == result['text']


def test_report_publication_keeps_lineage_without_copying_live_private_acl(tmp_path):
    source, ref = source_at(tmp_path/'original')
    scope = source.library.scope('alice', PROJECT)
    dependency = {'project_id': PROJECT, 'document_id': ref['version_id'], 'raw_body_sha256':ref['digest'], 'source_scope':scope}
    origin = {'thread_id':str(uuid4()),'report_version':1,'report_digest':'a'*64,'phase':'human_completed',
              'human_edit_count':1,'source_dependencies':[dependency]}
    saved = source.library.documents.add(scope, 'Report.md', b'Synthetic research conclusion, not verified fact.', research_origin=origin)
    report = next(a['current']['ref'] for a in source.catalog('alice', PROJECT)['items'] if a['current']['ref']['version_id'] == saved['document_id'])
    shared = SpaceAssets(tmp_path/'custody')
    binding = shared.publish(source,'alice',str(uuid4()),str(uuid4()),str(uuid4()),report)
    assert binding['source_provenance']['research_origin'] == origin
    source.library.set_access('alice',PROJECT,'document',ref['version_id'],True)
    with pytest.raises(ValueError): source.read('alice',report)
    result = shared.read(binding)
    assert result['version']['role'] == 'report'
    assert result['text'] == 'Synthetic research conclusion, not verified fact.'


def test_knowledge_and_decimal_financial_selection_keep_source_identity(tmp_path, source_library):
    client, provider, _, _, _, _, source, project = setup(tmp_path, source_library)
    shared = SpaceAssets(tmp_path/'organization-custody')
    org, space = str(uuid4()), str(uuid4())
    for selected, kind in zip(selections(provider), ['knowledge', 'database']):
        original = save(client, project, selected)
        ref = reference(source, project, original)
        binding = shared.publish(source, 'local-pilot', str(uuid4()), org, space, ref)
        assert binding['resource_type'] == kind
        before, after = source.read('local-pilot', ref), shared.read(binding)
        assert after['text'] == before['text']
        assert after['capture'] == before['capture']
        assert binding['source_ref'] == ref
        if kind == 'database':
            row = after['capture']['rows'][0]
            assert row['value_decimal'] == '100' and row['unit'] == 'USD'
            assert row['period_end'] == '2025-06-30' and row['filed_at'] == '2025-09-01'


def test_bff_checks_current_authority_and_hides_internal_bindings(tmp_path, monkeypatch):
    import apps.workbench.backend.business_transport as transport
    source, ref = source_at(tmp_path)
    org, space, resource = [str(uuid4()) for _ in range(3)]
    state = {'active': True, 'binding': None, 'reads': 0, 'mismatch': False}
    async def authority(actor, method, path, body=None):
        assert actor in ('alice','bob') and method == 'POST'
        if path == f'spaces/{space}/access':
            if actor != 'alice': raise HTTPException(403, 'reader cannot publish')
            return {'id':space,'organization_id':org}
        if path == 'resources':
            state['binding'] = body['binding']; return {'id':resource,'revision':1}
        assert path == f'resources/{resource}/access'
        state['reads'] += 1
        if not state['active']: raise HTTPException(404, 'revoked')
        return {'id':str(uuid4()) if state['mismatch'] else resource,'revision':1,'binding':state['binding']}
    monkeypatch.setattr(transport, 'space_business_request', authority)
    monkeypatch.setenv('FINSIGHT_RESOURCE_SPACES_ENABLED','1')
    monkeypatch.setenv('FINSIGHT_BUSINESS_API_URL','http://127.0.0.1:9')
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET','synthetic-test-secret-with-at-least-32-bytes')
    app = app_at(tmp_path,monkeypatch)
    app.include_router(build_asset_workspace_router(tmp_path),prefix='/api/v1')
    app.include_router(build_business_gateway(),prefix='/api/v1')
    body = {'id':resource,'space_id':space,'ref':ref}
    bob = {**WRITE,'Authorization':'Bearer bob'}
    with TestClient(app) as client:
        endpoint = '/api/v1/asset-workspace/spaces/publish'
        assert client.post(endpoint,headers={**WRITE,'Origin':'https://foreign.invalid'},json=body).status_code == 403
        assert client.post(endpoint,headers=bob,json=body).status_code == 403
        assert client.post(endpoint,headers=WRITE,json={**body,'owner':'alice'}).status_code == 422
        assert client.post(endpoint,headers=WRITE,json=body).status_code == 200
        read = f'/api/v1/asset-workspace/spaces/resources/{resource}'
        result = client.get(read,headers=bob)
        assert result.status_code == 200, result.text
        assert result.headers['cache-control'] == 'no-store'
        assert result.json()['text'] == 'Pinned original evidence.'
        assert client.post('/api/v1/asset-workspace/read',headers=bob,json=state['binding']['ref']).status_code == 404
        for path in ['resources',f'spaces/{space}/access',f'resources/{resource}/access']:
            assert client.post('/api/v1/business/workspaces/'+path,headers=WRITE,json={}).status_code == 404
        state['mismatch'] = True
        assert client.get(read,headers=bob).status_code == 502
        state['active'] = False
        assert client.get(read,headers=bob).status_code == 404
        assert state['reads'] == 3


def test_resource_spaces_fail_closed_without_individual_login(monkeypatch):
    import asyncio
    from apps.workbench.backend.business_transport import resource_spaces_enabled, space_business_request
    monkeypatch.setenv('FINSIGHT_RESOURCE_SPACES_ENABLED','1')
    monkeypatch.setenv('FINSIGHT_BUSINESS_API_URL','http://127.0.0.1:9')
    monkeypatch.setenv('FINSIGHT_AUTH_MODE','local_pilot')
    assert not resource_spaces_enabled()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(space_business_request('local-pilot','GET',''))
    assert exc.value.status_code == 503


def test_organization_project_gateway_requires_enabled_individual_login(tmp_path, monkeypatch):
    monkeypatch.setenv('FINSIGHT_BUSINESS_API_URL','http://127.0.0.1:9')
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET','synthetic-test-secret-with-at-least-32-bytes')
    app = app_at(tmp_path,monkeypatch)
    app.include_router(build_business_gateway(),prefix='/api/v1')
    # Never reach the transport when the deployment/identity gate is off.
    with TestClient(app) as client:
        for mode, enabled in [('oidc_product','0'), ('local_pilot','1')]:
            monkeypatch.setenv('FINSIGHT_AUTH_MODE',mode)
            monkeypatch.setenv('FINSIGHT_RESOURCE_SPACES_ENABLED',enabled)
            assert client.get('/api/v1/business/config',headers=WRITE).json()['organization_projects'] is False
            assert client.get('/api/v1/business/workspaces/projects',headers=WRITE).status_code==404
            assert client.post('/api/v1/business/workspaces/projects',headers=WRITE,json={}).status_code==404
