"""Real SEC capture adapter over fake HTTP; project isolation and version semantics."""
import json
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
import requests

from test_project_library import app_at, index, PROJECT, WRITE
from test_sec_companyfacts_snapshot import FakeSession, FakeResponse, _companyfacts, _submissions, _urls, _raw, TEST_CONTACT
from financial_facts.sec_snapshot import capture_sec_companyfacts_snapshot
from sec_agent.research_foundation import project_sec_sources as module
from sec_agent.research_foundation.project_library import ProjectLibrary


@pytest.fixture
def captured(tmp_path, monkeypatch):
    facts=_companyfacts()
    facts['facts']={'us-gaap':{'Revenue':{'label':'Revenue','units':{'USD':[
        {'start':'2025-01-01','end':'2025-03-31','val':9007199254740993,'filed':'2025-05-01','accn':'a','form':'10-Q'},
        {'start':'2025-01-01','end':'2025-03-31','val':9007199254740994,'filed':'2025-08-01','accn':'b','form':'10-Q'},
    ]}}}}
    submissions={**_submissions(),'tickers':['DELL']}
    session=FakeSession([FakeResponse(_urls()[0],_raw(facts)),FakeResponse(_urls()[1],_raw(submissions))])
    def capture(manifest, **kwargs):
        kwargs['environment']={'FINSIGHT_SEC_CONTACT_EMAIL':TEST_CONTACT}
        return capture_sec_companyfacts_snapshot(manifest,**kwargs,session=session,sleep=lambda _:None)
    monkeypatch.setattr(module,'capture_sec_companyfacts_snapshot',capture)
    client=TestClient(app_at(tmp_path,monkeypatch))
    assert client.put('/api/v1/projects',headers=WRITE,json=index()).status_code==200
    body={'version':str(uuid4()),'ticker':'DELL','cik':'0001571996'}
    return client,body,session,tmp_path


def test_saved_sec_observations_keep_versions_units_exact_values_and_owner(captured,monkeypatch):
    client,body,session,root=captured;base=f'/api/v1/projects/{PROJECT}/sec'
    first=client.post(base,headers=WRITE,json=body)
    assert first.status_code==200 and first.json()['status']=='complete'
    assert len(session.calls)==2
    assert client.post(base,headers=WRITE,json=body).json()==first.json() and len(session.calls)==2
    other={**WRITE,'Authorization':'Bearer bob'}
    assert client.get(base,headers=other).status_code==404
    assert client.put('/api/v1/projects',headers=other,json=index()).status_code==200
    assert client.get(base+'/'+body['version'],headers=other).status_code==404
    reopened=TestClient(app_at(root,monkeypatch))
    assert reopened.get(base,headers=WRITE).json()['items'][0]['version']==body['version']
    path=base+'/'+body['version']; params={'taxonomy':'us-gaap','tag':'Revenue','as_of':'2025-05-31'}
    data=reopened.get(path,headers=WRITE,params=params).json()
    assert data['total']==1 and data['items'][0]['val']=='9007199254740993'
    assert data['items'][0]['unit']=='USD' and data['items'][0]['locator']['observation_index']==0
    assert data['numeric_fact_authority'] is False
    assert reopened.get(path,headers=WRITE,params={**params,'as_of':'2025-08-31'}).json()['total']==2
    raw=reopened.get(path+'/download/sec_companyfacts',headers=WRITE)
    assert raw.status_code==200 and json.loads(raw.content)['cik']==1571996
    assert TEST_CONTACT not in json.dumps(first.json())
    # A new failed refresh remains visible without erasing the prior snapshot.
    session.responses.append(requests.Timeout())
    failed=reopened.post(base,headers=WRITE,json={**body,'version':str(uuid4())}).json()
    assert failed['status']=='failed' and failed['failure_code']=='sec_snapshot_transport_timeout'
    assert reopened.get(path,headers=WRITE,params=params).json()['total']==1
    assert len(reopened.get(base,headers=WRITE).json()['items'])==2


def test_sec_refuses_identity_drift_cross_site_and_corrupt_saved_source(captured):
    client,body,session,root=captured;base=f'/api/v1/projects/{PROJECT}/sec'
    assert client.post(base,headers={**WRITE,'Origin':'https://outside.invalid'},json=body).status_code==403
    assert not session.calls
    assert client.post(base,headers=WRITE,json={**body,'cik':'../../etc'}).status_code==422
    assert not session.calls
    assert client.post(base,headers=WRITE,json=body).json()['status']=='complete'
    assert client.post(base,headers=WRITE,json={**body,'ticker':'OTHER'}).status_code==409
    library=ProjectLibrary(root);scope=library.scope('alice',PROJECT)
    raw=root/'sec-snapshots'/scope/body['version']/'raw/DELL/sec_companyfacts.json'
    raw.write_text('{}')
    assert client.get(base+'/'+body['version'],headers=WRITE).status_code==409
    assert client.get(base+'/'+body['version']+'/download/sec_companyfacts',headers=WRITE).status_code==409


def test_sec_ticker_must_match_official_cik(captured):
    client,body,session,root=captured;base=f'/api/v1/projects/{PROJECT}/sec'
    result=client.post(base,headers=WRITE,json={**body,'ticker':'MSFT'}).json()
    assert result['status']=='failed' and result['failure_code']=='ticker_cik_mismatch'
    assert client.get(base+'/'+body['version'],headers=WRITE).status_code==409
