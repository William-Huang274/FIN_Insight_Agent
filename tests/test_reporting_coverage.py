import json
import sqlite3

import pytest

from test_industry_foundation import foundation, publish
from test_financial_navigation import fact
from sec_agent.research_foundation import reporting_periods, disclosure_register
from sec_agent.research_foundation.industry_data import data_page
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from sec_agent.research_foundation.financial_accounts import account_path
from scripts.data_retrieval.import_statement_pages import extract_rows


def rebuild(path):
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        reporting_periods.rebuild(db)


def test_observation_year_not_comparative_filing_year(foundation):
    path, w, sid = foundation
    fact(w, sid, 'annual', 'Revenue', 100, start='2025-01-27', end='2026-01-25', form='10-K', acc='annual')
    w.sql("UPDATE financial_points SET fiscal_period='FY' WHERE id='annual'")
    fact(w, sid, 'comparative', 'Revenue', 100, start='2025-01-27', end='2026-01-25', form='10-K', acc='next')
    w.sql("UPDATE financial_points SET fiscal_year=2027,fiscal_period='FY' WHERE id='comparative'")
    fact(w, sid, 'next', 'Revenue', 120, start='2026-01-26', end='2027-01-31', form='10-K', acc='next')
    w.sql("UPDATE financial_points SET fiscal_year=2027,fiscal_period='FY' WHERE id='next'")
    rebuild(path)
    result = data_page(path, 'NVIDIA', fiscal_year=2026, fiscal_period='FY')
    assert {r['id'] for r in result['items']} == {'annual', 'comparative'}
    assert all(r['reporting_period']['label'] == 'FY2026 · 全年' for r in result['items'])


def test_quarter_cumulative_and_balance_are_separate(foundation):
    path,w,sid=foundation
    fact(w,sid,'quarter','Revenue',50,start='2026-04-01')
    fact(w,sid,'balance','Assets',200,start=None)
    rebuild(path)
    assert [r['id'] for r in data_page(path,'NVIDIA',fiscal_period='Q2')['items']]==['quarter']
    assert [r['id'] for r in data_page(path,'NVIDIA',fiscal_period='H1')['items']]==['point1']
    assert [r['id'] for r in data_page(path,'NVIDIA',fiscal_period='instant')['items']]==['balance']
    lib=publish(path,w)
    request=SourceDocumentRequest(source_space='library',operation='data',entity_id='NVIDIA',fiscal_year=2026,fiscal_period='H1')
    assert request.model_dump()['fiscal_period']=='H1'
    with pytest.raises(ValueError):
        with sqlite3.connect(path) as db:
            db.row_factory=sqlite3.Row
            reporting_periods.rebuild(db)


def test_period_contract_rejects_nonfinancial_filters():
    with pytest.raises(ValueError):
        SourceDocumentRequest(source_space='library',operation='data',entity_id='NVIDIA',data_kind='positions',fiscal_year=2026)
    assert 'fiscal_year' not in SourceDocumentRequest(operation='catalog').model_dump()


def test_pdf_columns_reference_currency_dashes_and_note_numbers():
    rows=extract_rows('Net sales .... 37 ¥ 7,243,752 ¥ 7,798,650 $ 48,778,146\nCost of sales (3,489,549) (3,782,511) (23,658,438)',3,'income',{})
    assert rows[0]['label']=='Net sales'
    assert rows[0]['values']==['7,243,752','7,798,650','48,778,146']
    assert rows[1]['values'][1]=='(3,782,511)'
    rows=extract_rows('Financial assets at fair value through\n other comprehensive income 17 6,224 –',2,'balance/assets/noncurrent',{})
    assert rows[0]['label']=='Financial assets at fair value through other comprehensive income'
    assert rows[0]['values']==['6,224','–']
    rows=extract_rows('MINIMAX GROUP INC. Annual Report 2025 107106\nBasic 9(a) US8.41 cents US13.50 cents\nDiluted 9(b) US8.05 cents US12.74 cents',2,'income',{})
    assert len(rows)==2
    assert rows[0]['label']=='Basic'
    assert rows[0]['values']==['8.41','13.50']
    assert rows[1]['account_path']=='income/profit/eps'


def test_original_statement_classification_does_not_assert_unknown_units():
    assert account_path('DART-IFRS','ifrs-full_Assets:BS')=='balance/assets/total'
    assert account_path('DART-IFRS','dart_PrivateExtension:CF')=='cashflow'
    assert account_path('FinMind:TaiwanStockFinancialStatements','PrivateExtension')=='income'
    assert account_path('unreviewed','Assets')=='unclassified'


def test_disclosure_absence_is_scoped_and_not_13f_equivalence(foundation):
    path,w,sid=foundation
    with sqlite3.connect(path) as db:
        db.executescript(disclosure_register.SCHEMA)
        db.execute('INSERT INTO company_disclosures VALUES(?,?,?,?,?,?,?,?,?,?)',('d','NVIDIA','customers','客户',None,None,None,'未定位','section_not_located_in_checked_sources',json.dumps({'reviewed_at':'2026-09-20','sources_checked':[sid]})))
    assert data_page(path,'NVIDIA',kind='disclosures',as_of='2026-09-19')['total']==0
    assert data_page(path,'NVIDIA',kind='disclosures')['items'][0]['status']=='section_not_located_in_checked_sources'
