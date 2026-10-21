from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import HTTPException
from test_organization_research_inputs import fixture
from test_organization_execution_access import runtime_grant
from apps.workbench.backend.organization_research_inputs import validate_grant
from sec_agent.research_foundation.organization_input_selection import validate_input_selection
from sec_agent.research_foundation.organization_execution_access import validate_execution_grant, OrganizationExecutionUnavailable


def scoped(tmp_path):
    _, grant = fixture(tmp_path)
    for _ in range(18):
        rid = str(uuid4())
        grant['manifest']['inputs'].append({**grant['manifest']['inputs'][0], 'resource_id':rid})
        grant['inputs'].append({**grant['inputs'][0], 'resource_id':rid})
    ids = [i['resource_id'] for i in grant['inputs']]
    grant['manifest']['input_selection'] = dict(contract_version='organization_input_selection.v1',
        selected_resource_ids=ids[:2], retrieval_resource_ids=ids)
    return grant


def test_material_and_runtime_share_separate_scope_validation(tmp_path):
    grant = scoped(tmp_path)
    assert len(validate_grant(grant, grant['project_id'], grant['id'])[1]) == 19
    runtime = runtime_grant(grant)
    manifest, inputs = validate_execution_grant(runtime, runtime['execution_id'], runtime['manifest_digest'])
    assert len(inputs) == 19 and len(validate_input_selection(manifest)) == 2


@pytest.mark.parametrize('fault', ['legacy_overflow','null','extra_key','missing_candidate','extra_candidate',
    'duplicate','selected_outside','too_many_selected','bad_version'])
def test_scope_cannot_expand_or_hide_authorized_dependencies(tmp_path, fault):
    grant = scoped(tmp_path); selection = grant['manifest']['input_selection']
    if fault=='legacy_overflow':del grant['manifest']['input_selection']
    if fault=='null':grant['manifest']['input_selection']=None
    if fault=='extra_key':selection['grant_all']=True
    if fault=='missing_candidate':selection['retrieval_resource_ids'].pop()
    if fault=='extra_candidate':selection['retrieval_resource_ids'].append(str(uuid4()))
    if fault=='duplicate':selection['selected_resource_ids']*=2
    if fault=='selected_outside':selection['selected_resource_ids']=[str(uuid4())]
    if fault=='too_many_selected':selection['selected_resource_ids']=selection['retrieval_resource_ids'][:13]
    if fault=='bad_version':selection['contract_version']='latest'
    with pytest.raises(HTTPException):validate_grant(grant,grant['project_id'],grant['id'])
    runtime=runtime_grant(grant)
    with pytest.raises(OrganizationExecutionUnavailable):
        validate_execution_grant(runtime,runtime['execution_id'],runtime['manifest_digest'])


def test_legacy_manifest_unchanged_and_scope_bound():
    manifest={'inputs':[{'resource_id':str(uuid4())} for _ in range(12)]}
    before=deepcopy(manifest)
    assert len(validate_input_selection(manifest))==12 and manifest==before
    ids=[str(uuid4()) for _ in range(2049)]
    manifest={'inputs':[{'resource_id':i} for i in ids], 'input_selection':dict(
        contract_version='organization_input_selection.v1',selected_resource_ids=ids[:1],retrieval_resource_ids=ids)}
    with pytest.raises(ValueError):validate_input_selection(manifest)


def test_gateway_large_scope_bound_is_specific_to_draft_creation(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from types import SimpleNamespace
    import apps.workbench.backend.business_transport as transport
    monkeypatch.setenv('FINSIGHT_BUSINESS_API_URL','http://127.0.0.1:9')
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET','synthetic-scope-bridge-secret-at-least-32-bytes')
    monkeypatch.setattr(transport,'resource_spaces_enabled',lambda:True)
    monkeypatch.setattr('apps.workbench.backend.authentication.current_owner',lambda _: 'alice')
    sent=[]
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def request(self,method,url,content,headers):
            sent.append((url,len(content)))
            return SimpleNamespace(content=b'{}',status_code=200)
    monkeypatch.setattr(transport.httpx,'AsyncClient',Client)
    app=FastAPI();app.include_router(transport.build_business_gateway(),prefix='/api/v1')
    path=f'/api/v1/business/workspaces/projects/{uuid4()}/research-drafts'
    with TestClient(app) as client:
        headers={'x-workbench-request':'1'}
        assert client.post(path,content=b'x'*80000,headers=headers).status_code==200
        assert sent[0][1]==80000
        assert client.post(path,content=b'x'*262145,headers=headers).status_code==413
        assert client.post('/api/v1/business/tasks',content=b'x'*80000,headers=headers).status_code==413
        assert len(sent)==1
