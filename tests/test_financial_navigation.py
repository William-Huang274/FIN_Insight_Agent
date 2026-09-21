import json
from decimal import Decimal

import pytest
from test_industry_foundation import foundation, publish
from sec_agent.research_foundation import derived_financials as derived
from sec_agent.research_foundation.financial_accounts import account_path
from sec_agent.research_foundation.industry_data import data_page, company_detail
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest


def fact(worker,sid,id,concept,value,unit='USD',start='2026-01-01',end='2026-06-30',filed='2026-08-26',form='10-Q',acc='acc'):
    worker.sql('INSERT INTO financial_points VALUES('+','.join('?'*16)+')',
        (id,'NVIDIA','us-gaap',concept,concept,str(value),unit,start,end,filed,2026,'Q2',form,acc,sid,'{}'))


def test_account_paths_do_not_guess_extensions_and_filter_parents(foundation):
    path,w,sid=foundation
    fact(w,sid,'cash','CashAndCashEquivalentsAtCarryingValue',25,start=None)
    fact(w,sid,'ppe','PropertyPlantAndEquipmentNet',50,start=None)
    assert account_path('company-extension','AssetsCurrent')=='unclassified'
    assert {r['id'] for r in data_page(path,'NVIDIA',account='balance/assets')['items']}=={'cash','ppe'}
    assert [r['id'] for r in data_page(path,'NVIDIA',account='balance/assets/current')['items']]==['cash']
    assert any(r['path']=='balance/assets/current' for r in company_detail(path,'NVIDIA')['account_tree'])
    with pytest.raises(ValueError):data_page(path,'NVIDIA',account='invented')
    assert account_path('dei','EntityCommonStockSharesOutstanding')=='balance/equity/capital'
    assert account_path('us-gaap','LongTermDebtAndCapitalLeaseObligations')=='unclassified'


def test_listing_review_does_not_conflate_listing_and_incorporation():
    from sec_agent.research_foundation.industry_taxonomy import listing_profile
    c={'registration_country':'KY','listing_review':{'status':'listed','markets':['HK'],'source_url':'https://example.org/exchange'}}
    assert listing_profile(c)['registration_country']=='KY'
    assert listing_profile(c)['markets']==['HK']
    assert listing_profile({'ticker':'FAKE.US','listing_status':'to_verify'})['status']=='unknown'


def test_relation_without_publication_uses_explicit_capture_basis(foundation):
    from scripts.data_retrieval.organize_industry_foundation import apply_reviews
    _,w,_=foundation
    sid=w.source('NVIDIA','https://example.org/models','Platform','product_platform','Model A supports vendor B.')
    w.sql('INSERT INTO entities VALUES(?,?,?)',('OTHER','company','Other'))
    apply_reviews(w.path,{'reviewed_at':'2026-09-20','relations':[dict(subject='NVIDIA',object='OTHER',predicate='supports_platform',source_id=sid,evidence_quote='Model A supports vendor B.',status='confirmed',review_reason='Reviewed technical compatibility only')]})
    row=w.sql("SELECT * FROM edges WHERE predicate='supports_platform'")[0]
    q=json.loads(row['qualifiers'])
    assert q['source_published_at'] is None and q['date_basis']=='known_at_capture_not_publication'


def test_ratios_never_join_different_period_currency_or_revision(foundation):
    path,w,sid=foundation
    fact(w,sid,'other-currency','GrossProfit',40,unit='EUR')
    fact(w,sid,'other-period','OperatingIncomeLoss',30,start='2026-04-01')
    fact(w,sid,'other-revision','NetIncomeLoss',20,acc='different')
    assert derived.materialize(path,'2026-09-20')['generated_rows']==0
    fact(w,sid,'gross','GrossProfit',40)
    derived.materialize(path,'2026-09-20')
    result=data_page(path,'NVIDIA',kind='derived')['items']
    assert len(result)==1 and Decimal(result[0]['value'])==40
    assert result[0]['inputs'][0]['source_id']==sid
    assert result[0]['period_start']=='2026-01-01'
    derived.materialize(path,'2026-09-20')
    assert w.sql('SELECT count(*) AS n FROM derived_financials')[0]['n']==1


def test_pe_requires_review_and_marks_losses_not_negative_pe(foundation):
    path,w,sid=foundation
    # Collector captures the wall-clock date; this historical valuation fixture
    # must be available at its fixed cutoff regardless of the test execution day.
    source_meta=json.loads(w.sql('SELECT metadata FROM sources WHERE id=?',(sid,))[0]['metadata'])
    source_meta['captured_at']='2026-09-18T16:00:00+00:00'
    w.sql('UPDATE sources SET metadata=? WHERE id=?',(json.dumps(source_meta),sid))
    fact(w,sid,'eps','EarningsPerShareDiluted',-2,unit='USD/shares',start='2025-01-01',end='2025-12-31',filed='2026-02-01',form='10-K')
    w.sql('INSERT INTO market_prices VALUES(?,?,?,?,?,?,?,?,?,?,?)',('NVIDIA','NVDA','2026-09-18',10,10,10,10,8,100,'USD',sid))
    derived.materialize(path,'2026-09-20')
    assert all(r['status']=='missing_inputs' for r in data_page(path,'NVIDIA',kind='derived')['items'])
    c=json.loads(w.sql('SELECT payload FROM company_cards')[0]['payload'])
    c['valuation_security_basis']={'status':'reviewed_single_common_share','ticker':'NVDA','source_id':sid,'known_at':'2026-09-20','price_basis_reviewed_through':'2026-09-18'}
    w.sql('UPDATE company_cards SET payload=?',(json.dumps(c),))
    derived.materialize(path,'2026-09-20')
    # Query storage to inspect the new version; no patching model conclusions.
    row=w.sql("SELECT * FROM derived_financials WHERE metric='pe_fy_diluted' AND status='not_meaningful_nonpositive_earnings'")[0]
    assert row['value'] is None and row['available_at']=='2026-09-20'
    assert next(r for r in data_page(path,'NVIDIA',kind='derived')['items'] if r['metric']=='pe_fy_diluted')['status']=='not_meaningful_nonpositive_earnings'
    assert json.loads(row['inputs'])[0]['value']=='10.0'
    assert 'not_ttm' in row['detail']


def test_conflicting_eps_is_not_cherry_picked(foundation):
    _,w,sid=foundation
    rows=[{'id':'a','value':'1','period_end':'2025-12-31','filed_at':'2026-02-01'},
          {'id':'b','value':'2','period_end':'2025-12-31','filed_at':'2026-02-01'}]
    assert derived.latest_unambiguous(rows) is None
    rows.append({'id':'c','value':'3','period_end':'2025-12-31','filed_at':'2026-03-01'})
    assert derived.latest_unambiguous(rows)['id']=='c'


def test_data_default_respects_company_and_manager_role():
    from sec_agent.research_foundation.industry_data import data_channels
    detail={'profile':{'type':'company'},'positions_count':8,'sources':[],
            'data_counts':{'financial_points':30,'market_prices':3,'filing_catalog':2}}
    assert data_channels(detail)[0]['kind']=='financial'
    detail['profile']['type']='investment_institution'
    assert data_channels(detail)[0]['kind']=='positions'


def test_materialized_values_and_account_filters_reach_formal_runtime(foundation):
    path,w,sid=foundation
    fact(w,sid,'gross','GrossProfit',40)
    derived.materialize(path,'2026-09-20')
    library=publish(path,w)
    result=library.navigate(SourceDocumentRequest(source_space='library',operation='data',entity_id='NVIDIA',data_kind='derived'),'2026-09-20')
    assert result.items[0]['formula_version']==derived.VERSION
    assert Decimal(result.items[0]['value'])==40
    result=library.navigate(SourceDocumentRequest(source_space='library',operation='data',entity_id='NVIDIA',account_path='income/revenue',query='no match'),'2026-09-20')
    assert result.items[0]['retry_arguments']['account_path']=='income/revenue'
    assert 'account_path' not in SourceDocumentRequest(operation='catalog').model_dump()
    with pytest.raises(ValueError,match='immutable'):derived.materialize(path,'2026-09-20')
