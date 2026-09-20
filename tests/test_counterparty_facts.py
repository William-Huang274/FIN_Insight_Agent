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


@pytest.mark.parametrize('relationship,predicate', [('supplier','supplies'),('indirect_customer','indirect_customer_of'),('direct_customer','direct_customer_of'),('beneficial_owner','disclosed_shareholder_of')])
def test_undated_named_fact_projects_without_changing_role(foundation,relationship,predicate):
    path,w,sid,pack=setup(foundation)
    w.sql('INSERT INTO entities VALUES(?,?,?)',('SUPPLIER','company','Supplier Co'))
    w.sql('UPDATE sources SET published_at=NULL,vintage=?,metadata=? WHERE id=?',
          ('known_as_of',json.dumps({'known_at':'2026-09-21T03:00:00Z'}),sid))
    f=pack['facts'][0]
    f.update(category='suppliers' if relationship=='supplier' else 'shareholders' if relationship=='beneficial_owner' else 'customers',
             identity_kind='named',counterparty_name='Supplier Co',counterparty_entity_id='SUPPLIER',relationship=relationship,
             measurement_basis='qualitative',count=None,measures=[])
    imported(path,pack); imported(path,pack)
    lib=publish(path,w)
    graph=lib.graph_search('NVIDIA','2026-09-21')
    matching=[e for e in graph['edges'] if e['predicate']==predicate]
    assert len(matching)==1
    edge=matching[0]
    assert (edge['subject'],edge['object'])==('SUPPLIER','NVIDIA')
    assert edge['qualifiers']['relationship']==relationship
    assert edge['qualifiers']['published_at'] is None
    assert edge['qualifiers']['known_as_of']=='2026-09-21'
    assert not [e for e in lib.graph_search('NVIDIA','2026-09-20')['edges'] if e['predicate']==predicate]


def test_approximate_disclosure_retains_operator(foundation):
    path,w,sid,pack=setup(foundation)
    pack['facts'][0]['measures'][0]['operator']='approximately'
    imported(path,pack)
    rows=data_page(path,'NVIDIA',kind='disclosures',query='customers')['items']
    assert rows[0]['structured_facts'][0]['measures'][0]['operator']=='approximately'


def test_import_is_atomic_when_late_row_fails(foundation):
    path,_,_,pack=setup(foundation)
    bad=copy.deepcopy(pack['facts'][0]);bad['measures'][0]['value']='33';pack['facts'].append(bad)
    with pytest.raises(ValueError):imported(path,pack)
    with sqlite3.connect(path) as db:
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='counterparty_facts'").fetchone()


def test_undated_reviewed_fact_available_only_after_capture(foundation):
    path,w,sid,pack=setup(foundation)
    w.sql('DELETE FROM company_disclosures')
    w.sql('UPDATE sources SET published_at=NULL,vintage=?,metadata=? WHERE id=?',
          ('known_as_of',json.dumps({'known_at':'2026-09-21T03:00:00Z'}),sid))
    imported(path,pack)
    assert data_page(path,'NVIDIA',kind='disclosures',as_of='2026-09-20')['total']==0
    item=data_page(path,'NVIDIA',kind='disclosures',as_of='2026-09-21')['items'][0]
    assert item['published_at'] is None and item['known_as_of']=='2026-09-21'
    lib=publish(path,w)
    result=lib.navigate(SourceDocumentRequest(source_space='library',operation='data',data_kind='disclosures',entity_id='NVIDIA'),'2026-09-21')
    fact=result.items[0]
    assert fact['measures'][0]['value']=='11' and fact['date_basis']=='known_as_of'
    assert fact['published_at'] is None
    assert lib.navigate(SourceDocumentRequest(**fact['evidence'][0]['readback']),'2026-09-21').items


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


@pytest.mark.parametrize('text,value,valid',[
    ('Anonymous customer | 10.0%','10',True),
    ('Anonymous customer | 110.0%','10',False),
    ('Anonymous customer | 11 | 12%','1112',False),
    ('Anonymous customer | 11,12%','1112',False),
    ('Anonymous customer | 10.5%','10',False),
])
def test_numeric_presence_uses_decimal_tokens(foundation,text,value,valid):
    path,w,_,pack=setup(foundation)
    sid=w.source('NVIDIA','https://example.org/decimal','Decimal table','filing',text,published='2026-08-26')
    pid=w.sql('SELECT id FROM passages WHERE source_id=?',(sid,))[0]['id']
    fact=pack['facts'][0]
    fact.update(source_id=sid,evidence=[dict(passage_id=pid,start=0,end=len(text),quote=text)])
    fact['measures'][0]['value']=value
    if valid:imported(path,pack)
    else:
        with pytest.raises(ValueError):imported(path,pack)


def test_customer_revenue_amount_keeps_thousands_and_is_not_arr(foundation):
    path,w,_,pack=setup(foundation)
    text='Year ended 2025 | USD thousand\nCustomer A | 9,868'
    sid=w.source('NVIDIA','https://example.org/customer-amount','Customer revenue','filing',text,published='2026-08-26')
    pid=w.sql('SELECT id FROM passages WHERE source_id=?',(sid,))[0]['id']
    fact=pack['facts'][0]
    fact.update(source_id=sid,evidence=[dict(passage_id=pid,start=0,end=len(text),quote=text)])
    fact['measures']=[dict(metric='revenue_amount',value='9868',unit='USD',scale='1000',operator='=',denominator='FY2025 revenue from Customer A')]
    imported(path,pack)
    with sqlite3.connect(path) as db:
        payload=json.loads(db.execute('SELECT payload FROM counterparty_facts').fetchone()[0])
    assert payload['measures'][0]['metric']=='revenue_amount'
    assert payload['measures'][0]['value']=='9868' and payload['measures'][0]['scale']=='1000'
    bad=copy.deepcopy(pack)
    bad['facts'][0]['measures'][0]['unit']='percent'
    with pytest.raises(ValueError):imported(path,bad)


@pytest.mark.parametrize('category,relationship,metric,unit,value,scale',[
    ('suppliers','supplier','procurement_amount','USD','295','1000000'),
    ('shareholders','beneficial_owner','voting_power_share','percent','85.1','1'),
])
def test_procurement_and_voting_keep_distinct_semantics(foundation,category,relationship,metric,unit,value,scale):
    path,w,_,pack=setup(foundation)
    text='FY2026: purchased USD 295 million. Voting power: 85.1%.'
    sid=w.source('NVIDIA','https://example.org/distinct-measures','Transaction terms','filing',text,published='2026-08-26')
    pid=w.sql('SELECT id FROM passages WHERE source_id=?',(sid,))[0]['id']
    fact=pack['facts'][0]
    fact.update(source_id=sid,category=category,relationship=relationship,evidence=[dict(passage_id=pid,start=0,end=len(text),quote=text)])
    fact['measures']=[dict(metric=metric,value=value,unit=unit,scale=scale,operator='=',denominator='Original disclosed basis')]
    imported(path,pack)
    with sqlite3.connect(path) as db:
        saved=json.loads(db.execute('SELECT payload FROM counterparty_facts').fetchone()[0])
    assert saved['measures'][0]['metric']==metric and saved['measures'][0].get('scale','1')==scale
    bad=copy.deepcopy(pack);bad['facts'][0].update(category='customers',relationship='customer')
    with pytest.raises(ValueError,match='metric_category_mismatch'):imported(path,bad)


@pytest.mark.parametrize('category,relationship,metric',[
    ('customers','customer','receivables_share'),
    ('suppliers','supplier','cost_of_sales_share'),
])
def test_balance_and_cost_concentrations_are_not_labeled_sales(foundation,category,relationship,metric):
    path,_,_,pack=setup(foundation)
    fact=pack['facts'][0]
    fact.update(category=category,relationship=relationship)
    fact['measures'][0]['metric']=metric
    imported(path,pack)
    with sqlite3.connect(path) as db:
        saved=json.loads(db.execute('SELECT payload FROM counterparty_facts').fetchone()[0])
    assert saved['measures'][0]['metric']==metric
    bad=copy.deepcopy(pack)
    bad['facts'][0].update(category='shareholders',relationship='beneficial_owner')
    with pytest.raises(ValueError,match='metric_category_mismatch'):imported(path,bad)
