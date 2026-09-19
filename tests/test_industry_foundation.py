import json
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sec_agent.research_foundation.research_snapshot import build_snapshot
from sec_agent.research_foundation.research_library import ResearchLibrary, digest_file
from sec_agent.research_foundation.industry_data import companies, company_detail, data_page
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from scripts.data_retrieval.build_industry_foundation import initialize, Collector


@pytest.fixture
def foundation(tmp_path):
    base=tmp_path/'base.sqlite'
    build_snapshot(base,[dict(id='OLD',title='Old source',url='https://example.org/old',published_at='2025-01-01',vintage='dated_original',access_state='readable',digest='a'*64)],
                   [dict(id='PASSAGE::old',source_id='OLD',locator='original',body='Original material preserved.')],entities=[dict(id='NVIDIA',kind='company',name='NVIDIA')])
    path=tmp_path/'new.sqlite'
    plan={'as_of':'2026-09-20','recent_since':'2026-06-20','filings_since':'2023-09-20','companies':[
        dict(slug='nvidia',name='NVIDIA',sector='chips',ticker='NVDA',cik='1045810',website='https://example.org',products=['GPU'],depth=1)]}
    initialize(path,base,plan)
    worker=Collector(path,plan)
    sid=worker.source('NVIDIA','https://example.org/current','Current source','financial_api','Current source text.',published='2026-08-26')
    worker.sql('INSERT INTO financial_points VALUES('+','.join('?'*16)+')',('point1','NVIDIA','us-gaap','Revenue','Revenue','100','USD','2026-01-01','2026-06-30','2026-08-26',2026,'Q2','10-Q','acc',sid,'{}'))
    worker.gap('NVIDIA','news','tool_failure',{'public_information_gap':False})
    return path,worker,sid


def publish(path,worker):
    worker.sql("UPDATE snapshot_metadata SET value='published_public_library.v1' WHERE key='state'")
    path.with_suffix('.sqlite.manifest.json').write_text(json.dumps({'version':'research_library.v1','access_scope':'public','sha256':digest_file(path)}),encoding='utf-8')
    return ResearchLibrary(path)


def test_import_preserves_identity_and_old_original(foundation):
    path,worker,sid=foundation
    assert companies(path)['items'][0]['entity_id']=='NVIDIA'
    assert worker.sql('SELECT body FROM passages WHERE id=?',('PASSAGE::old',))[0]['body']=='Original material preserved.'
    assert company_detail(path,'NVIDIA')['gaps'][0]['status']=='tool_failure'


def test_runtime_uses_card_and_financial_data_with_asof(foundation):
    path,worker,sid=foundation;library=publish(path,worker)
    request=SourceDocumentRequest(source_space='library',operation='data',entity_id='NVIDIA',data_kind='financial')
    assert library.navigate(request,'2026-08-25').total_matches==0
    result=library.navigate(request,'2026-09-20')
    assert result.items[0]['source_id']==sid
    assert result.items[0]['unit']=='USD'
    assert all(item['result_state']=='retrieval_candidate' for item in result.items)
    card=library.navigate(SourceDocumentRequest(source_space='library',operation='company',entity_id='NVIDIA'),'2026-09-20')
    assert card.items[0]['card']['authority']=='navigation_metadata_not_investment_judgment'
    assert card.items[0]['sources'][0]['id']==sid
    assert card.items[0]['result_state']=='retrieval_candidate'
    catalog=library.navigate(SourceDocumentRequest(source_space='library',operation='catalog',query='NVIDIA',limit=1),'2026-09-20')
    assert catalog.items[0]['entity_id']=='NVIDIA'


def test_current_capture_is_not_visible_before_known_date(foundation):
    path,worker,sid=foundation
    current=worker.source('NVIDIA','https://example.org/live','Current profile','company_profile','Current live page')
    assert current not in {s['id'] for s in company_detail(path,'NVIDIA',as_of='2026-09-19')['sources']}
    assert current in {s['id'] for s in company_detail(path,'NVIDIA',as_of='2026-09-20')['sources']}


def test_sec_exhibit_fallback_preserves_rows_and_marks_compatibility(foundation,monkeypatch):
    path,worker,sid=foundation
    html=('<html><body><p>'+('Management statement. '*8)+'</p><table><tr><th>USD millions</th><th>2026 Q2</th></tr><tr><td>Revenue</td><td>100</td></tr></table></body></html>').encode()
    monkeypatch.setattr(worker,'get',lambda url:(html,'text/html'))
    monkeypatch.setattr('scripts.data_retrieval.build_industry_foundation.trafilatura.extract',lambda *a,**kw:None)
    sid=worker.document('NVIDIA','https://example.org/ex99','filing_exhibit',published='2026-09-01')
    text=worker.sql('SELECT body FROM passages WHERE source_id=?',(sid,))[0]['body']
    assert 'USD millions | 2026 Q2' in text and 'Revenue | 100' in text
    meta=json.loads(worker.sql('SELECT metadata FROM sources WHERE id=?',(sid,))[0]['metadata'])
    assert meta['runtime_compatibility_parse']['raw_html_retained'] is True


def test_inline_xbrl_values_survive_article_extraction(foundation,monkeypatch):
    path,worker,sid=foundation
    html=('<html><body><h1>Quarterly financial results</h1><p>'+('Management explains operating results. '*15)+'</p><table><tr><td>Revenue</td><td><ix:nonfraction name="us-gaap:Revenue">12,345</ix:nonfraction></td></tr><tr><td>Income tax expense</td><td><ix:nonfraction>2,345</ix:nonfraction></td></tr></table></body></html>').encode()
    monkeypatch.setattr(worker,'get',lambda url:(html,'text/html'))
    # An article extractor may return only prose, omitting the entire appendix.
    monkeypatch.setattr('scripts.data_retrieval.build_industry_foundation.trafilatura.extract',lambda *a,**kw:'Management explains operating results. '*15)
    sid=worker.document('NVIDIA','https://example.org/inline-xbrl','filing',published='2026-09-01')
    text='\n'.join(p['body'] for p in worker.sql('SELECT body FROM passages WHERE source_id=?',(sid,)))
    assert '12,345' in text and '2,345' in text
    meta=json.loads(worker.sql('SELECT metadata FROM sources WHERE id=?',(sid,))[0]['metadata'])
    assert meta['runtime_compatibility_parse']['inline_xbrl_unwrapped'] is True
    assert meta['runtime_compatibility_parse']['full_visible_report'] is True


def test_dart_half_year_income_current_amount_is_quarter_and_ytd_is_separate():
    from scripts.data_retrieval.international_industry_sources import dart_point_rows
    row={'rcept_no':'20260814000000','sj_div':'IS','account_id':'Revenue','account_nm':'Revenue','currency':'KRW','thstrm_amount':'120','thstrm_add_amount':'230'}
    points=dart_point_rows('company','source',row,2026,'11012','2026-09-20')
    assert [(p[5],p[7],p[8],p[11]) for p in points]==[('120','2026-04-01','2026-06-30','Q2'),('230','2026-01-01','2026-06-30','H1')]
    balance=dart_point_rows('company','source',{**row,'sj_div':'BS'},2026,'11012','2026-09-20')
    assert len(balance)==1 and balance[0][7] is None


def test_unknown_data_kind_and_nonlibrary_operation_rejected(foundation):
    with pytest.raises(ValueError):data_page(foundation[0],'NVIDIA',kind='raw_captures')
    with pytest.raises(ValueError):SourceDocumentRequest(source_space='local',operation='company',entity_id='NVIDIA')
    with pytest.raises(ValueError):SourceDocumentRequest(source_space='library',operation='data')


def test_facts_preserve_units_and_vintages_filter_future(foundation,monkeypatch):
    path,worker,sid=foundation
    payload={'cik':1045810,'entityName':'NVIDIA','facts':{'us-gaap':{'Revenue':{'label':'Revenue','units':{'USD':[
        {'val':100,'start':'2026-01-01','end':'2026-06-30','filed':'2026-08-26','form':'10-Q','accn':'a'},
        {'val':110,'start':'2026-01-01','end':'2026-06-30','filed':'2026-09-10','form':'10-Q/A','accn':'b'},
        {'val':999,'end':'2026-06-30','filed':'2026-10-01','form':'10-Q/A','accn':'c'}]}}}}}
    monkeypatch.setattr(worker,'get',lambda url:(json.dumps(payload).encode(),'application/json'))
    worker.facts(dict(entity_id='NVIDIA',cik='1045810',name='NVIDIA'))
    rows=worker.sql("SELECT value,unit,accession FROM financial_points WHERE id!='point1' ORDER BY filed_at")
    assert rows==[{'value':'100','unit':'USD','accession':'a'},{'value':'110','unit':'USD','accession':'b'}]


def test_api_reads_same_library_not_preview_fixture(foundation,tmp_path):
    from apps.workbench.backend.api.v1.data_library import build_data_library_router
    path,worker,sid=foundation;publish(path,worker)
    app=FastAPI();app.include_router(build_data_library_router(tmp_path,research_library=path))
    client=TestClient(app)
    assert client.get('/data-library/companies').json()['total']==1
    r=client.get('/data-library/companies/NVIDIA/data?kind=financial').json()
    assert r['items'][0]['source_id']==sid
    assert client.get('/data-library/companies/missing').status_code==404
    assert client.get('/data-library/research-sources/'+sid).json()['items'][0]['body']=='Current source text.'
    assert client.get('/data-library/research-sources/'+sid).json()['total']==1


def test_latest_observation_first_when_capture_date_ties(foundation):
    path,worker,sid=foundation
    worker.sql('INSERT INTO financial_points VALUES('+','.join('?'*16)+')',('point2','NVIDIA','us-gaap','Revenue','Revenue','120','USD','2026-04-01','2026-07-31','2026-08-26',2026,'Q2','10-Q','acc',sid,'{}'))
    page=data_page(path,'NVIDIA',kind='financial',limit=1)
    assert page['items'][0]['period_end']=='2026-07-31'
    assert page['total']==2 and page['next_offset']==1


def test_holder_crosswalk_preserves_option_class_and_reporting_date(foundation):
    path,worker,sid=foundation
    worker.sql('INSERT INTO entities VALUES(?,?,?)',('MANAGER','institution','Fund manager'))
    worker.sql('INSERT INTO institution_positions VALUES('+','.join('?'*14)+')',('position','MANAGER','NVIDIA','CUSIP','COM','50','USD','2','SH','Call','2026-06-30','2026-08-12',sid,'{}'))
    worker.sql('INSERT INTO position_issuers VALUES(?,?,?)',('position','NVIDIA','reviewed issuer name'))
    assert data_page(path,'NVIDIA',kind='holders',as_of='2026-08-11')['total']==0
    row=data_page(path,'NVIDIA',kind='holders')['items'][0]
    assert row['put_call']=='Call' and row['period_end']=='2026-06-30'
    assert row['manager_name']=='Fund manager'


def test_wrong_identity_and_literal_filter_provide_recovery_not_nondisclosure(foundation):
    path,worker,sid=foundation;library=publish(path,worker)
    result=library.navigate(SourceDocumentRequest(source_space='library',operation='company',entity_id='nvidia'),'2026-09-20')
    assert result.items[0]['entity_id']=='NVIDIA'
    result=library.navigate(SourceDocumentRequest(source_space='library',operation='data',entity_id='NVIDIA',query='recent revenue quarter'),'2026-09-20')
    assert result.items[0]['public_information_gap_proved'] is False
    assert result.items[0]['retry_arguments']['query']==''
    data_identity=library.navigate(SourceDocumentRequest(source_space='library',operation='data',entity_id='nvidia'),'2026-09-20')
    assert data_identity.items[0]['entity_id']=='NVIDIA'


def test_library_hybrid_requires_prepared_vectors_and_filters_scope(foundation,tmp_path):
    from retrieval.library_hybrid import document_cards,prepare,rank
    from retrieval.qwen_api import RetrievalResponse
    class API:
        embedding_model='fixture-embed';rerank_model='fixture-rerank'
        def __init__(self):self.calls=[]
        def embed(self,texts):
            self.calls.append(('embed',len(texts)))
            return RetrievalResponse([[1.,0.] for _ in texts],{},None,self.embedding_model)
        def rerank(self,query,docs):
            self.calls.append(('rerank',len(docs)))
            return RetrievalResponse([{'index':i,'relevance_score':1.} for i in range(len(docs))],{},None,self.rerank_model)
    path,worker,sid=foundation
    excluded=worker.source('NVIDIA','https://example.org/excluded','Incidental match','policy_regulation','Unrelated incidental material.',published='2026-09-01')
    worker.sql("UPDATE sources SET access_state='scope_excluded' WHERE id=?",(excluded,))
    library=publish(path,worker);api=API();cache=str(tmp_path/'vectors')
    assert excluded not in {c['id'] for c in document_cards(library)}
    with pytest.raises(RuntimeError,match='尚有'):
        rank(library,'cash','2026-09-20',[],path=cache,api=api)
    assert api.calls==[]  # ordinary retrieval cannot start a corpus-paid job
    prepare(library,cache,api);api.calls.clear()
    rows,receipt=rank(library,'cash','2026-09-20',[],path=cache,document_id=sid,api=api)
    assert rows and {r['source_id'] for r in rows}=={sid}
    assert receipt['calls']==2
    rank(library,'cash','2026-09-20',[],path=cache,document_id=sid,api=api)
    assert len(api.calls)==2
