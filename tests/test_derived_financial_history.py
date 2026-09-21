import json
from decimal import Decimal

import pytest
from test_industry_foundation import foundation, publish
from test_financial_navigation import fact
from sec_agent.research_foundation import derived_financials as derived
from sec_agent.research_foundation.industry_data import data_page
from sec_agent.research_foundation.reporting_periods import rebuild
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from sec_agent.research_foundation.valuation_history import FX_SCHEMA


def test_history_filters_revision_and_real_runtime(foundation):
    path,w,sid=foundation
    fact(w,sid,'gross-now','GrossProfit',40)
    fact(w,sid,'rev-old','Revenue',80,start='2025-01-01',end='2025-06-30')
    fact(w,sid,'gross-old','GrossProfit',24,start='2025-01-01',end='2025-06-30')
    import sqlite3
    with sqlite3.connect(path) as db:
        db.row_factory=sqlite3.Row;rebuild(db)
    derived.materialize(path,'2026-09-21')
    history=data_page(path,'NVIDIA',kind='derived',query='gross_margin',derived_view='history')
    assert [Decimal(r['value']) for r in history['items']]==[40,30]
    assert data_page(path,'NVIDIA',kind='derived',query='gross_margin')['total']==1
    assert data_page(path,'NVIDIA',kind='derived',query='gross_margin',derived_view='history',date_end='2025-12-31')['items'][0]['period_end']=='2025-06-30'
    library=publish(path,w)
    request=SourceDocumentRequest(source_space='library',operation='data',entity_id='NVIDIA',data_kind='derived',derived_view='history',fiscal_period='H1',date_end='2025-12-31',query='gross_margin')
    result=library.navigate(request,'2026-09-21')
    assert len(result.items)==1 and Decimal(result.items[0]['value'])==30
    with pytest.raises(ValueError):SourceDocumentRequest(source_space='library',operation='data',data_kind='derived',date_start='2026-01-01',date_end='2025-01-01')


def test_average_balance_and_negative_comparison(foundation):
    path,w,sid=foundation
    fact(w,sid,'income','NetIncomeLoss',20)
    fact(w,sid,'assets-start','Assets',100,start=None,end='2025-12-31')
    fact(w,sid,'assets-end','Assets',200,start=None)
    fact(w,sid,'loss-prior','NetIncomeLoss',-10,start='2025-01-01',end='2025-06-30')
    derived.materialize(path,'2026-09-21')
    rows=data_page(path,'NVIDIA',kind='derived')['items']
    roa=next(r for r in rows if r['metric']=='roa_period')
    assert abs(Decimal(roa['value'])-Decimal(20)/150*100)<Decimal('1e-20')
    assert len(roa['inputs'])==3 and roa['detail']['annualized'] is False
    growth=next(r for r in rows if r['metric']=='profit_growth_yoy')
    assert growth['value'] is None and growth['status']=='nonpositive_comparison_base'


def test_adr_fx_and_no_future_financial_inputs(foundation):
    path,w,sid=foundation
    meta=json.loads(w.sql('SELECT metadata FROM sources WHERE id=?',(sid,))[0]['metadata'])
    meta['captured_at']='2026-09-18';w.sql('UPDATE sources SET metadata=? WHERE id=?',(json.dumps(meta),sid))
    fact(w,sid,'eps','EarningsPerShareDiluted',10,unit='CNY/shares',start='2025-01-01',end='2025-12-31',filed='2026-02-01',form='20-F')
    fact(w,sid,'future-eps','EarningsPerShareDiluted',100,unit='CNY/shares',start='2025-01-01',end='2025-12-31',filed='2026-09-19',form='20-F')
    fact(w,sid,'actual-shares','CommonStockSharesOutstanding',800,unit='shares',start=None,end='2026-08-01',filed='2026-08-10')
    card=json.loads(w.sql('SELECT payload FROM company_cards')[0]['payload'])
    card['valuation_security_basis']={'status':'reviewed_ordinary_equivalent','ticker':'TEST','source_id':sid,'known_at':'2026-09-21','price_basis_reviewed_through':'2026-09-18','ordinary_shares_per_security':8}
    w.sql('UPDATE company_cards SET payload=?',(json.dumps(card),))
    w.sql('INSERT INTO market_prices VALUES(?,?,?,?,?,?,?,?,?,?,?)',('NVIDIA','TEST','2026-09-18',20,20,20,20,20,100,'USD',sid))
    w.sql(FX_SCHEMA)
    w.sql('INSERT INTO valuation_fx VALUES(?,?,?,?,?,?)',(sid,'2026-09-18','USD','CNY','8','2026-09-21'))
    derived.materialize(path,'2026-09-21')
    rows=data_page(path,'NVIDIA',kind='derived')['items']
    pe=next(r for r in rows if r['metric']=='pe_fy_diluted')
    assert Decimal(pe['value'])==2
    assert pe['inputs'][1]['id']=='eps' and pe['inputs'][2]['role']=='fx'
    assert pe['available_at']=='2026-09-21'
    assert Decimal(next(r for r in rows if r['metric']=='market_cap_reported_shares')['value'])==2000
    assert data_page(path,'NVIDIA',kind='derived',as_of='2026-09-20')['total']==0


def test_stale_latest_shares_do_not_fall_back_to_older_valuation(foundation):
    path,w,sid=foundation
    meta=json.loads(w.sql('SELECT metadata FROM sources WHERE id=?',(sid,))[0]['metadata'])
    meta['captured_at']='2026-09-18';w.sql('UPDATE sources SET metadata=? WHERE id=?',(json.dumps(meta),sid))
    fact(w,sid,'actual','CommonStockSharesOutstanding',10,unit='shares',start=None,end='2026-05-18',filed='2026-05-20')
    fact(w,sid,'annual-revenue','Revenues',100,start='2025-01-01',end='2025-12-31',filed='2026-02-01')
    card=json.loads(w.sql('SELECT payload FROM company_cards')[0]['payload'])
    card['valuation_security_basis']={'status':'reviewed_single_common_share','ticker':'TEST','source_id':sid,'known_at':'2026-09-21','price_basis_reviewed_through':'2026-09-18'}
    w.sql('UPDATE company_cards SET payload=?',(json.dumps(card),))
    for day in ['2026-09-10','2026-09-18']:
        w.sql('INSERT INTO market_prices VALUES(?,?,?,?,?,?,?,?,?,?,?)',('NVIDIA','TEST',day,20,20,20,20,20,100,'USD',sid))
    derived.materialize(path,'2026-09-21')
    current=data_page(path,'NVIDIA',kind='derived',query='metric:ps_fy')['items'][0]
    assert current['valuation_date']=='2026-09-18' and current['value'] is None
    assert current['status']=='stale_or_invalid_share_count'
    history=data_page(path,'NVIDIA',kind='derived',query='metric:ps_fy',derived_view='history')['items']
    assert Decimal(history[1]['value'])==2


def test_total_revenue_not_contract_subtotal_and_classified_balances(foundation):
    path,w,sid=foundation
    fact(w,sid,'total-revenue','Revenues',80)
    fact(w,sid,'contract-subtotal','RevenueFromContractWithCustomerExcludingAssessedTax',100)
    fact(w,sid,'profit','NetIncomeLoss',8)
    for end,amount in [('2025-12-31',40),('2026-06-30',60)]:
        fact(w,sid,'ca'+end,'AssetsCurrent',amount,start=None,end=end)
        fact(w,sid,'na'+end,'AssetsNoncurrent',amount,start=None,end=end)
    derived.materialize(path,'2026-09-21')
    rows=data_page(path,'NVIDIA',kind='derived')['items']
    assert Decimal(next(r for r in rows if r['metric']=='net_margin')['value'])==10
    roa=next(r for r in rows if r['metric']=='roa_period')
    assert Decimal(roa['value'])==8 and len(roa['inputs'][1]['components'])==2


def test_dart_main_statement_eps_and_capture_timestamp(foundation):
    path,w,sid=foundation
    fact(w,sid,'dart-income','ifrs-full_ProfitLoss:CIS',20,unit='KRW')
    fact(w,sid,'dart-revenue','ifrs-full_Revenue:CIS',100,unit='KRW')
    fact(w,sid,'equity-movement','ifrs-full_ProfitLoss:SCE',999,unit='KRW')
    w.sql("UPDATE financial_points SET taxonomy='DART-IFRS' WHERE id LIKE 'dart-%' OR id='equity-movement'")
    meta=json.loads(w.sql('SELECT metadata FROM sources WHERE id=?',(sid,))[0]['metadata'])
    meta['known_at']='2027-01-01';w.sql('UPDATE sources SET metadata=? WHERE id=?',(json.dumps(meta),sid))
    derived.materialize(path,'2026-09-21')
    row=data_page(path,'NVIDIA',kind='derived',query='metric:net_margin')['items'][0]
    assert Decimal(row['value'])==20
    assert row['available_at']=='2026-08-26'
