"""Bounded project-to-task mapping with actual SEC parser, SQL and HTTP routes."""
from datetime import datetime, timezone
import json
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from test_research_session_bff import _app
from test_sec_companyfacts_snapshot import FakeResponse, FakeSession, TEST_CONTACT
from financial_facts.sec_snapshot import capture_sec_companyfacts_snapshot
from sec_agent.research_foundation import project_sec_sources as module
from sec_agent.research_foundation.project_library import ProjectLibrary
from sec_agent.research_foundation.project_sec_sources import ProjectSecSources
from sec_agent.research_foundation.project_financial_facts import task_financial_snapshot
from sec_agent.research_foundation.task_attachments import TaskAttachmentStore

WRITE={'X-Workbench-Request':'1'}


@pytest.fixture
def mapped_task(tmp_path,monkeypatch):
    app,service,calls,tid=_app()
    service.attachment_store=TaskAttachmentStore(tmp_path/'attachments')
    library=ProjectLibrary(tmp_path/'project-library');project=str(uuid4());version=str(uuid4())
    library.save('local-pilot',0,{'projects':[{'id':project,'name':'Synthetic SEC'}],'assignments':{},'pinned':[]})
    facts={}
    for tag,values in [('RevenueFromContractWithCustomerExcludingAssessedTax',(100,120)),('OperatingIncomeLoss',(20,30))]:
        facts[tag]={'units':{'USD':[{'start':'2024-07-01','end':'2025-06-30','val':v,'fy':2025,'fp':'FY','form':'10-K','filed':'2025-07-30','accn':f'0000789019-25-00000{i}'} for i,v in enumerate(values)]}}
    # A source row with no captured filing identity must be counted, never admitted.
    facts['OperatingIncomeLoss']['units']['USD'].append({'start':'2024-07-01','end':'2025-06-30','val':999,'accn':'not-captured','fy':2025,'fp':'FY'})
    cf={'cik':789019,'entityName':'Synthetic Issuer','facts':{'us-gaap':facts}}
    submissions={'cik':789019,'name':'Synthetic Issuer','tickers':['MSFT'],'filings':{'recent':{
        'accessionNumber':['0000789019-25-000000','0000789019-25-000001'],
        'filingDate':['2025-07-30']*2,'acceptanceDateTime':['2025-07-30T18:00:00Z','2025-07-30T20:00:00Z'],
        'reportDate':['2025-06-30']*2,'form':['10-K']*2,'primaryDocument':['a.htm','b.htm']}}}
    session=FakeSession([FakeResponse('https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json',json.dumps(cf).encode()),
                         FakeResponse('https://data.sec.gov/submissions/CIK0000789019.json',json.dumps(submissions).encode())])
    def capture(manifest,**kwargs):
        kwargs['environment']={'FINSIGHT_SEC_CONTACT_EMAIL':TEST_CONTACT}
        return capture_sec_companyfacts_snapshot(manifest,**kwargs,session=session,sleep=lambda _:None)
    monkeypatch.setattr(module,'capture_sec_companyfacts_snapshot',capture)
    sec=ProjectSecSources(library)
    assert sec.capture('local-pilot',project,version,'MSFT','0000789019')['status']=='complete'
    async def update(thread_id,*,metadata):
        row=await service.sdk.threads.get(thread_id);row['metadata'].update(metadata);return row
    service.sdk.threads.update=update
    client=TestClient(app)
    request={'mode':'research','question':'Compare the saved income metrics with exact dates and units.', 'defer_start':True,
             'project_materials':{'project_id':project,'sec_version':version}}
    return client,service,calls,tid,sec,project,version,request


def query():
    return {'ticker':'MSFT','metric_ids':['revenue','operating_income','operating_margin'],
            'research_as_of':'2025-07-30','selection_mode':'exact_period_end','period_start':'2024-07-01',
            'period_end':'2025-06-30','granularity':'fiscal_year'}


def test_task_selection_maps_real_contract_and_clamps_direct_and_derived_as_of(mapped_task):
    client,service,calls,tid,sec,project,version,request=mapped_task
    created=client.post('/api/v1/research-sessions',headers=WRITE,json=request)
    assert created.status_code==200,created.text
    assert not any(c[0]=='run' for c in calls)
    selected=task_financial_snapshot(service.attachment_store.root,tid)
    assert selected[1]['counts']['observations']==4
    assert selected[1]['source_summary']['sources'][0]['missing_filing_identity']==1
    import asyncio
    row=asyncio.run(service.sdk.threads.get(tid))
    row['metadata']['research_as_of']='2025-07-30T19:00:00Z'
    before=client.post(f'/api/v1/research-sessions/{tid}/financial-facts',headers=WRITE,json=query())
    assert before.status_code==200,before.text
    assert [r['facts'][0]['value_decimal'] for r in before.json()['query_result']['results']]==['100','20','20']
    row['metadata']['research_as_of']='2025-07-30T16:00:00-04:00'  # Inclusive20:00UTC accepts the revision.
    after=client.post(f'/api/v1/research-sessions/{tid}/financial-facts',headers=WRITE,json=query()).json()
    assert [r['facts'][0]['value_decimal'] for r in after['query_result']['results']]==['120','30','25']
    assert before.json()['query_result']['results'][0]['fact_request_id']!=after['query_result']['results'][0]['fact_request_id']
    assert after['project_binding']['project_origin']['sec_version']==version
    # Parent project changes do not rewrite a selected task's raw/mart copies.
    _,root=sec._saved('local-pilot',project,version)
    (root/'raw/MSFT/sec_companyfacts.json').write_text('{}')
    assert task_financial_snapshot(service.attachment_store.root,tid)[1]['mart_sha256']==selected[1]['mart_sha256']
    assert task_financial_snapshot(service.attachment_store.root,str(uuid4())) is None
    selected[0].write_bytes(b'corrupt')
    assert client.post(f'/api/v1/research-sessions/{tid}/financial-facts',headers=WRITE,json=query()).status_code==409


def test_foreign_sec_version_fails_before_thread_and_failed_build_stays_blocked(mapped_task,monkeypatch):
    client,service,calls,tid,sec,project,version,request=mapped_task
    forged={**request,'project_materials':{'project_id':str(uuid4()),'sec_version':version}}
    assert client.post('/api/v1/research-sessions',headers=WRITE,json=forged).status_code==404
    assert not calls
    from sec_agent.research_foundation import project_financial_facts as financial
    def fail(*args,**kwargs):raise OSError('synthetic disk failure')
    monkeypatch.setattr(financial,'build_company_fact_mart',fail)
    assert client.post('/api/v1/research-sessions',headers=WRITE,json=request).status_code==409
    with pytest.raises(ValueError,match='not_ready'):task_financial_snapshot(service.attachment_store.root,tid)
    assert client.post(f'/api/v1/research-sessions/{tid}/start',headers=WRITE).status_code==409
    assert not any(c[0]=='run' for c in calls)


def test_unmapped_or_wrong_period_is_not_public_disclosure_gap(mapped_task):
    client,service,calls,tid,sec,project,version,request=mapped_task
    assert client.post('/api/v1/research-sessions',headers=WRITE,json=request).status_code==200
    for changes in ({'metric_ids':['net_income']},{'granularity':'quarter_discrete'}):
        response=client.post(f'/api/v1/research-sessions/{tid}/financial-facts',headers=WRITE,json={**query(),**changes})
        assert response.status_code==200,response.text
        assert all(r['status']=='typed_gap' and not r['facts'] for r in response.json()['query_result']['results'])
    assert client.post(f'/api/v1/research-sessions/{tid}/financial-facts',headers=WRITE,json={**query(),'research_as_of':'2099-01-01'}).status_code==409
