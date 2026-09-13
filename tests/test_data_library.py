import hashlib
import json
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from apps.workbench.backend.api.v1.data_library import build_data_library_router
from sec_agent.research_foundation.public_library import library_nodes


@pytest.fixture
def library(tmp_path):
    root = tmp_path/'public-library'; root.mkdir()
    rows=[]
    for ticker, year in [('MSFT',2024),('MSFT',2025),('HPE',2025)]:
        text=f'{ticker} operating cash flow {year}'
        rows.append(dict(parent_document_id=f'DOC::{ticker}{year}',node_id=f'S::{ticker}{year}',node_kind='section',ticker=ticker,
            company=ticker,title=f'{ticker} 10-K {year}',publication_date=f'{year}-09-01',period_end=f'{year}-06-30',
            source_role='10-K',stable_url='https://www.sec.gov/example',content=text,section_path=['Cash flows'],content_sha256=hashlib.sha256(text.encode()).hexdigest()))
    (root/'retrieval_nodes.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    mart=tmp_path/'mart.sqlite'
    with sqlite3.connect(mart) as db:
        db.execute('CREATE TABLE company_fact_observations(ticker,legal_name,metric_id,concept,value_decimal,unit,period_start,period_end,fiscal_year,fiscal_period,form,filed_at,citation_url,superseded_by_observation_id)')
        for ticker,year in [('MSFT',2024),('MSFT',2025),('HPE',2025)]:
            db.execute('INSERT INTO company_fact_observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(ticker,ticker,'operating_cash_flow','NetCashProvidedByOperatingActivities','100','USD',f'{year-1}-07-01',f'{year}-06-30',year,'FY','10-K',f'{year}-09-01','https://www.sec.gov/example',None))
    app=FastAPI(); app.include_router(build_data_library_router(tmp_path,mart),prefix='/api/v1')
    return TestClient(app),tmp_path


def test_document_coverage_and_renderable_body(library):
    client,_=library
    body=client.get('/api/v1/data-library/sources',params={'ticker':'MSFT','year':'2024'}).json()
    assert body['total']==1
    assert body['items'][0]['period_end']=='2024-06-30'
    detail=client.get('/api/v1/data-library/sources/DOC::MSFT2024').json()
    assert detail['sections'][0]['text']=='MSFT operating cash flow 2024'
    assert 'node_id' not in detail['sections'][0]


def test_unknown_document_not_arbitrary_path(library):
    client,_=library
    assert client.get('/api/v1/data-library/sources/unknown').status_code==404


def test_market_prices_are_readonly_filtered_vendor_observations(library):
    client,root=library
    from tests.test_market_price_snapshot import materialize, body, ARGS
    materialize(body(),root/'public-library/market-prices.sqlite',**ARGS)
    response=client.get('/api/v1/data-library/market-prices?ticker=MU')
    assert response.status_code==200
    assert response.json()['items'][0]['close_decimal']=='12.00'
    assert client.get('/api/v1/data-library/market-prices?as_of=2026-09-09').json()['items']==[]
    assert client.get('/api/v1/data-library/market-prices',params={'ticker':"' OR 1=1 --"}).json()['items']==[]


def test_cutoff_excludes_later_publications(library):
    client,root=library
    assert client.get('/api/v1/data-library/sources?as_of=2024-12-31').json()['total']==1
    assert len(library_nodes(root,'2024-12-31')[0])==1


def test_financial_filter_keyword_and_versions(library):
    client,_=library
    response=client.get('/api/v1/data-library/financials',params={'ticker':'MSFT','fiscal_year':2025,'query':'现金流','period':'FY'})
    assert response.status_code==200, response.text
    body=response.json(); assert body['total']==1
    assert body['items'][0]['value_decimal']=='100'
    assert body['items'][0]['unit']=='USD'
    assert client.get('/api/v1/data-library/financials?as_of=2024-12-31').json()['total']==1


@pytest.mark.parametrize('field',['ticker','metric','period','query'])
def test_filter_is_data_not_sql(library,field):
    client,_=library
    assert client.get('/api/v1/data-library/financials',params={field:"' OR 1=1 --"}).json()['total']==0
    assert client.get('/api/v1/data-library/financials').json()['total']==3


def test_bounds_and_pagination(library):
    client,_=library
    assert client.get('/api/v1/data-library/financials?limit=101').status_code==422
    assert client.get('/api/v1/data-library/sources?offset=-1').status_code==422
    body=client.get('/api/v1/data-library/financials?offset=1&limit=1').json()
    assert len(body['items'])==1 and body['total']==3


def test_identity_required_when_enabled(library):
    client,_=library
    client.app.state.oidc_conversation_pilot=True
    assert client.get('/api/v1/data-library/sources').status_code==401
    assert client.get('/api/v1/data-library/financials').status_code==401


def test_conversation_tool_preserves_citable_original_and_handoff(library):
    from types import SimpleNamespace
    from sec_agent.agent_runtime.conversation_tools import conversation_tools
    from sec_agent.agent_runtime.conversation_handoff import observed_sources
    _,root=library
    tool=next(g.tool for g in conversation_tools(thread_id='00000000-0000-4000-8000-000000000001',attachment_store=SimpleNamespace(root=root)) if g.tool.name=='read_company_library')
    result=tool.invoke({'type':'tool_call','id':'read-public-case','name':tool.name,'args':{
        'as_of':'2024-12-31','request':{'operation':'read','document_id':'DOC::MSFT2024'}}})
    assert result.artifact['items'][0]['writer_citable']
    assert result.artifact['items'][0]['passage']=='MSFT operating cash flow 2024'
    assert observed_sources({'values':{'messages':[result.model_dump(mode='json')]}})
