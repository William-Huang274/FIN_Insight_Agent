"""Current viewer read delivery, post-I/O revocation and no personal fallback."""
from copy import deepcopy
import asyncio
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from test_java_research_intake import intake
from test_organization_native_drafts import organization, prepare


@pytest.mark.parametrize('changed',['reader','project_id','execution_id','thread_id','run_id','read_contract'])
def test_authority_response_cannot_substitute_viewer_or_scope(monkeypatch,changed):
    from apps.workbench.backend import organization_research_reads as reads
    project,execution=str(uuid4()),str(uuid4())
    grant={'reader':'oidc:viewer','project_id':project,'execution_id':execution,'thread_id':execution,
           'run_id':str(uuid4()),'read_contract':'organization_research_read.v1'}
    async def authority(actor,method,path):
        assert actor=='oidc:viewer' and method=='GET'
        assert path==f'projects/{project}/execution-bindings/{execution}/read-access'
        return deepcopy(grant)
    monkeypatch.setattr(reads,'space_business_request',authority)
    monkeypatch.setattr(reads,'service_owner',lambda:'oidc:viewer')
    assert asyncio.run(reads.read_authority(project,execution))==grant
    grant[changed]='wrong'
    with pytest.raises(HTTPException) as failure:asyncio.run(reads.read_authority(project,execution))
    assert failure.value.status_code==502


@pytest.fixture
def reading(organization, monkeypatch):
    s=organization
    with TestClient(s.intake.app()) as client:
        assert prepare(client,s).status_code==200
    tid=s.grant['execution_id']
    s.grant.update(read_contract='organization_research_read.v1',reader='oidc:viewer',run_id=str(uuid4()),
                   configuration_digest=s.intake.threads[tid]['metadata']['configuration_digest'])
    s.root=f"/api/v1/organization-projects/{s.grant['project_id']}/research/{tid}"
    s.headers={'Authorization':'Bearer synthetic'}
    s.calls=[]
    s.values={'phase':'human_review','report_version':1,'report':{'title':'Synthetic report','narrative_markdown':'Static organization report [C1]',
        'citations':{'C1':{'sources':[{'source_id':'ORG:S1','text':'Pinned citation text','period':'FY2025','unit':'USD'}]}}}}
    async def authority(project,execution):
        s.calls.append('authority')
        assert str(project)==s.grant['project_id'] and str(execution)==tid
        if s.state['status']!=200:raise HTTPException(s.state['status'],'revoked')
        return deepcopy(s.grant)
    monkeypatch.setattr('apps.workbench.backend.organization_research_reads.read_authority',authority)
    monkeypatch.setattr('apps.workbench.backend.authentication.OIDCBackend.verify',lambda self,token:'oidc:viewer')
    async def state(thread_id,**kwargs):
        assert thread_id==tid
        s.calls.append('state')
        if s.state.get('revoke_in_state'):s.state['status']=404
        return {'values':deepcopy(s.values)}
    s.intake.service.sdk.threads.get_state=state
    async def stream(thread_id,run_id,**kwargs):
        assert thread_id==tid and run_id==s.grant['run_id'] and kwargs['last_event_id']=='7-0'
        yield SimpleNamespace(event='messages',id='8-0',data={'secret':'private messages'})
        yield SimpleNamespace(event='custom',id='9-0',data={'kind':'stage','actor':'lead','event':'outcome','objective':'visible progress'})
        s.state['status']=404
        yield SimpleNamespace(event='custom',id='10-0',data={'kind':'stage','actor':'lead','event':'outcome','objective':'denied progress'})
    s.intake.service.sdk.runs.join_stream=stream
    return s


def test_viewer_snapshot_report_citation_keep_private_routes_closed(reading):
    s=reading
    with TestClient(s.intake.app()) as c:
        response=c.get(s.root,headers=s.headers)
        assert response.status_code==200,response.text
        assert response.headers['cache-control']=='no-store'
        assert response.json()['read_only'] is True
        assert not any(v for k,v in response.json().items() if k.startswith('can_'))
        assert c.get(s.root+'/report',headers=s.headers).json()['report']==s.values['report']
        source=c.get(s.root+'/source',params={'source_id':'ORG:S1','offset':7},headers=s.headers).json()
        assert source['text']=='citation text' and source['period']=='FY2025' and source['unit']=='USD'
        assert source['content_scope']=='saved_citation_snapshot'
        assert c.get(s.root+'/source',params={'source_id':'other'},headers=s.headers).status_code==404
        assert c.get(f"/api/v1/research-sessions/{s.grant['execution_id']}",headers=s.headers).status_code==404
        assert c.post(f"/api/v1/research-sessions/{s.grant['execution_id']}/start",headers=s.headers).status_code==404
        assert c.get(s.root).status_code in (401,403)
    assert not s.intake.runs


@pytest.mark.parametrize('route',['','/report','/source?source_id=ORG:S1','/report/export/md'])
def test_revocation_during_state_read_never_delivers_result(reading,route):
    s=reading;s.state['revoke_in_state']=True
    with TestClient(s.intake.app()) as c:
        result=c.get(s.root+route,headers=s.headers)
        assert result.status_code==404 and 'Static organization' not in result.text


def test_export_rechecks_after_render_and_never_dispatches(reading,monkeypatch):
    s=reading
    def export(*args,**kwargs):
        s.state['status']=404
        return b'SENSITIVE EXPORT','text/plain'
    monkeypatch.setattr('apps.workbench.backend.application.report_delivery.export_report',export)
    with TestClient(s.intake.app()) as c:
        result=c.get(s.root+'/report/export/md',headers=s.headers)
        assert result.status_code==404 and 'SENSITIVE' not in result.text
    assert not s.intake.runs


@pytest.mark.parametrize('format,magic',[('md',b'# Synthetic'),('pdf',b'%PDF'),('docx',b'PK'),('pptx',b'PK')])
def test_authorized_static_report_export_uses_real_renderer(reading,format,magic):
    s=reading
    with TestClient(s.intake.app()) as c:
        result=c.get(s.root+'/report/export/'+format,headers=s.headers)
        assert result.status_code==200,result.text[:300]
        assert result.content.startswith(magic) and result.headers['cache-control']=='no-store'
    assert not s.intake.runs


def test_historical_report_keeps_current_acl_and_ambiguous_citation_is_rejected(reading):
    s=reading
    s.values['synthesis']=deepcopy(s.values['report'])
    s.values['synthesis']['citations']['C1']['sources'][0]['text']='Different version'
    with TestClient(s.intake.app()) as c:
        assert c.get(s.root+'/source?source_id=ORG:S1',headers=s.headers).status_code==409
        assert c.get(s.root+'/report?checkpoint_id='+str(uuid4()),headers=s.headers).status_code==200
        s.state['status']=404
        assert c.get(s.root+'/report?checkpoint_id='+str(uuid4()),headers=s.headers).status_code==404


def test_stream_only_registered_run_and_stops_on_revocation(reading):
    s=reading
    with TestClient(s.intake.app()) as c:
        assert c.get(s.root+f'/runs/{uuid4()}/events',headers=s.headers).status_code==404
        response=c.get(s.root+f"/runs/{s.grant['run_id']}/events",headers={**s.headers,'last-event-id':'7-0'})
        assert response.status_code==200
        assert 'visible progress' in response.text and 'denied progress' not in response.text
        assert 'private messages' not in response.text and 'id: 9-0' in response.text
    assert not s.intake.runs


def test_frozen_config_mismatch_fails_before_state(reading):
    s=reading;s.grant['configuration_digest']='sha256:'+'b'*64
    with TestClient(s.intake.app()) as c:
        assert c.get(s.root,headers=s.headers).status_code==409
    assert 'state' not in s.calls
