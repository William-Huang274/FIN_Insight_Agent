import copy
import json
import sqlite3
import pytest

from test_industry_foundation import foundation, publish
from sec_agent.research_foundation import counterparty_facts as facts, disclosure_register
from sec_agent.research_foundation.industry_data import data_page, company_detail
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest


def setup(foundation):
    path,w,_=foundation
    text='FY2026: two anonymous direct customers each represent 11% of total revenue. Supplier Co provides memory.'
    sid=w.source('NVIDIA','https://example.org/counterparties','Issuer report','filing',text,published='2026-08-26')
    pid=w.sql('SELECT id FROM passages WHERE source_id=?',(sid,))[0]['id']
    fact=dict(entity_id='NVIDIA',category='customers',source_id=sid,counterparty_name='two anonymous customers',
              identity_kind='aggregate',relationship='direct_customer',role='purchase',fiscal_year=2026,count=2,
              measurement_basis='each',measures=[dict(metric='revenue_share',value='11',unit='percent',operator='=',denominator='total revenue')],
              scope_note='Each customer, not a combined share; identities unknown.',
              evidence=[dict(passage_id=pid,start=0,end=len(text),quote=text)])
    pack=dict(version='counterparty_facts.v1',reviewed_by='synthetic-test-review',review_note='Synthetic evidence only',facts=[fact])
    with sqlite3.connect(path) as db:
        db.executescript(disclosure_register.SCHEMA)
        for key in ['first','duplicate']:
            db.execute('INSERT INTO company_disclosures VALUES(?,?,?,?,?,?,?,?,?,?)',(key,'NVIDIA','customers','Issuer report',sid,'2026-08-26',key,text,'original_disclosure_section','{}'))
    return path,w,sid,pack


def imported(path,pack):
    with sqlite3.connect(path) as db:
        db.row_factory=sqlite3.Row
        return facts.import_reviewed(db,pack)


def test_materialized_each_semantics_and_duplicate_sections(foundation):
    path,w,sid,pack=setup(foundation)
    imported(path,pack);imported(path,pack)
    result=data_page(path,'NVIDIA',kind='disclosures',query='customers')
    assert result['total']==1
    row=result['items'][0]
    assert 'body' not in row and row['extraction_status']=='reviewed_facts_available'
    f=row['structured_facts'][0]
    assert f['count']==2 and f['measurement_basis']=='each' and f['measures'][0]['value']=='11'
    assert f['counterparty_entity_id'] is None
    assert data_page(path,'NVIDIA',kind='disclosures',as_of='2026-08-25')['total']==0
    result=publish(path,w).navigate(SourceDocumentRequest(source_space='library',operation='data',entity_id='NVIDIA',data_kind='disclosures',query='customers'),'2026-09-20')
    encoded=json.dumps(result.model_dump(mode='json'))
    assert 'measurement_basis' in encoded and 'Each customer' in encoded
    assert 'FY2026: two anonymous' not in encoded


@pytest.mark.parametrize('change', ['quote','value','anonymous_link','unit','period'])
def test_bad_extraction_never_becomes_fact(foundation,change):
    path,_,_,pack=setup(foundation)
    row=pack['facts'][0]
    if change=='quote':row['evidence'][0]['quote']='wrong evidence'
    if change=='value':row['measures'][0]['value']='22'
    if change=='anonymous_link':row['counterparty_entity_id']='NVIDIA'
    if change=='unit':row['measures'][0]['unit']='shares'
    if change=='period':row.pop('fiscal_year')
    with pytest.raises(ValueError):imported(path,pack)
    assert data_page(path,'NVIDIA',kind='disclosures')['items'][0]['extraction_status']=='extraction_pending'


def test_named_supplier_reaches_reverse_graph_and_missing_locator_category(foundation):
    path,w,sid,pack=setup(foundation)
    w.sql('INSERT INTO entities VALUES(?,?,?)',('SUPPLIER','company','Supplier Co'))
    row=pack['facts'][0]
    row.update(category='suppliers',identity_kind='named',counterparty_name='Supplier Co',counterparty_entity_id='SUPPLIER',relationship='supplier',role='memory',measurement_basis='qualitative',count=None,measures=[])
    imported(path,pack)
    data=data_page(path,'NVIDIA',kind='disclosures',query='suppliers')
    assert data['total']==1 and data['items'][0]['structured_facts'][0]['role']=='memory'
    lib=publish(path,w)
    for entity in ['NVIDIA','SUPPLIER']:
        graph=lib.graph_search(entity,'2026-09-20')
        edge=next(e for e in graph['edges'] if e['predicate']=='supplies')
        assert (edge['subject'],edge['object'])==('SUPPLIER','NVIDIA')
        assert edge['evidence'] and edge['qualifiers']['roles']==['memory']


def test_import_is_atomic_when_late_row_fails(foundation):
    path,_,_,pack=setup(foundation)
    bad=copy.deepcopy(pack['facts'][0]);bad['measures'][0]['value']='33';pack['facts'].append(bad)
    with pytest.raises(ValueError):imported(path,pack)
    with sqlite3.connect(path) as db:
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='counterparty_facts'").fetchone()


def test_table_cells_stay_separate_and_model_paginates_facts(foundation):
    path,w,_,pack=setup(foundation)
    text='Owner | 123 | 8.8%\nAs of 2026-03-19. Shares and percent of common stock.'
    sid=w.source('NVIDIA','https://example.org/owners','Owners','filing',text,published='2026-08-26')
    pid=w.sql('SELECT id FROM passages WHERE source_id=?',(sid,))[0]['id']
    fact=dict(entity_id='NVIDIA',category='shareholders',source_id=sid,counterparty_name='Owner',identity_kind='named',relationship='beneficial_owner',role='owner',observation_date='2026-03-19',measurement_basis='single',scope_note='Synthetic table',
        measures=[dict(metric='beneficial_shares',value='123',unit='shares',operator='=',denominator='common shares'),dict(metric='ownership_share',value='8.8',unit='percent',operator='=',denominator='common stock')],
        evidence=[dict(passage_id=pid,start=0,end=len(text),quote=text)])
    pack['facts'].append(fact);imported(path,pack)
    lib=publish(path,w)
    a=lib.navigate(SourceDocumentRequest(source_space='library',operation='data',data_kind='disclosures',entity_id='NVIDIA',limit=1),'2026-09-20')
    assert len(a.items)==1 and a.total_matches==2 and a.next_offset==1
    b=lib.navigate(SourceDocumentRequest(source_space='library',operation='data',data_kind='disclosures',entity_id='NVIDIA',limit=1,offset=1),'2026-09-20')
    assert b.next_offset is None and a.items[0]['id']!=b.items[0]['id']
    readback=b.items[0]['evidence'][0]['readback']
    assert lib.navigate(SourceDocumentRequest(**readback),'2026-09-20').items
