import json
import sqlite3
import pytest
from test_industry_foundation import foundation
from test_financial_navigation import fact
from sec_agent.research_foundation import derived_financials
from sec_agent.research_foundation.reporting_periods import rebuild
from sec_agent.research_foundation.metric_workspace import query_metrics, _sample, _period


def test_point_ratio_keeps_quarter_and_card_identity(foundation):
    path,w,sid=foundation
    fact(w,sid,'assets','Assets',200,start=None)
    fact(w,sid,'liabilities','Liabilities',40,start=None)
    with sqlite3.connect(path) as db:
        db.row_factory=sqlite3.Row;rebuild(db)
    derived_financials.materialize(path,'2026-09-21')
    result=query_metrics(path,['NVIDIA'],section='history',metric='liabilities_to_assets')
    row=result['items'][0]
    assert row['financial_basis']['label']=='FY2026 · Q2 期末'
    assert row['period_kind']=='instant' and row['value']=='20.0'
    assert 'inputs' not in row
    card=query_metrics(path,['NVIDIA'],section='card',record_id=row['id'])['items'][0]
    assert card['value']==row['value'] and len(card['inputs'])==2
    assert card['sources'][0]['id']==sid
    assert query_metrics(path,['NVIDIA'],section='history',fiscal_year=2025)['total']==0


def test_native_sampling_retains_invalid_last_day_and_currency():
    rows=[dict(id=str(i),entity_id='a',metric='pb',unit=unit,observation_kind='valuation',observation_date=d,value=v)
          for i,(d,v,unit) in enumerate([('2026-08-28','1','倍'),('2026-08-31',None,'倍'),('2026-09-01','2','倍')])]
    sampled=_sample(rows,'month_end')
    assert len(sampled)==2 and sampled[0]['value'] is None
    assert sampled[0]['observation_date']=='2026-08-31'


def test_unverified_calendar_year_is_not_fiscal_identity():
    r={'period_end':'2026-06-30','detail':{'fiscal_year':2026,'fiscal_period':'instant'}}
    p=_period(r,{'2026-06-30':{(2026,'Q2','provider_observation_calendar_year_period_unverified')}})
    assert p['fiscal_year'] is None and p['label'].startswith('截至年份 2026')


def test_valuation_has_trade_axis_and_financial_basis(foundation):
    path,w,sid=foundation
    with sqlite3.connect(path) as db:
        db.executescript(derived_financials.SCHEMA)
        for day in ['2026-09-17','2026-09-18']:
            db.execute('INSERT INTO derived_financials VALUES('+','.join('?'*15)+')',
               (day,'NVIDIA','pb','市净率','2','倍','available',None,'2026-06-30',day,day,'a/b',derived_financials.VERSION,'[]',json.dumps({'fiscal_year':2026,'fiscal_period':'instant'})))
    r=query_metrics(path,['NVIDIA'],section='valuation')
    assert r['total']==2 and r['items'][0]['axis_key']=='2026-09-18'
    assert r['items'][0]['financial_basis']['end']=='2026-06-30'
    with pytest.raises(ValueError,match='trade_dates'):query_metrics(path,['NVIDIA'],section='valuation',fiscal_year=2026)
    assert query_metrics(path,['NVIDIA'],section='valuation',as_of='2026-09-17')['total']==1
    with pytest.raises(ValueError,match='cutoff'):query_metrics(path,['NVIDIA'],section='card',record_id='2026-09-18',as_of='2026-09-17')


def test_comparison_keeps_missing_company_and_requires_metric(foundation):
    path,w,sid=foundation
    fact(w,sid,'g','GrossProfit',40)
    card=w.sql('SELECT payload FROM company_cards')[0]['payload']
    w.sql('INSERT INTO entities VALUES(?,?,?)',('OTHER','company','Other'))
    cols=w.sql('PRAGMA table_info(company_cards)')
    original=w.sql('SELECT * FROM company_cards')[0]
    values=[original[c['name']] if c['name']!='entity_id' else 'OTHER' for c in cols]
    w.sql('INSERT INTO company_cards VALUES('+','.join('?'*len(values))+')',tuple(values))
    derived_financials.materialize(path,'2026-09-21',entity_ids={'NVIDIA'})
    r=query_metrics(path,['NVIDIA','OTHER'],section='compare',metric='gross_margin')
    assert r['coverage'][1]['state']=='no_matching_observations'
    with pytest.raises(ValueError,match='requires_metric'):query_metrics(path,['NVIDIA'],section='compare')


def test_formal_tool_uses_same_record_and_legacy_serialization(foundation):
    from test_industry_foundation import publish
    from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
    path,w,sid=foundation
    fact(w,sid,'gross','GrossProfit',40)
    derived_financials.materialize(path,'2026-09-21')
    expected=query_metrics(path,['NVIDIA'],section='history',metric='gross_margin')['items'][0]
    library=publish(path,w)
    req=SourceDocumentRequest(source_space='library',operation='data',entity_id='NVIDIA',data_kind='metrics',metric_section='history',query='gross_margin')
    result=library.navigate(req,'2026-09-21')
    # The evidence lane accepts existing retrieval states, not a new dataset
    # state. Dataset identity must not promote these rows to numeric authority.
    from pydantic import TypeAdapter
    from sec_agent.agent_runtime.research_graph_contracts import ToolResultState
    assert TypeAdapter(ToolResultState).validate_python(result.items[0]['result_state'])=='retrieval_candidate'
    assert result.items[0]['dataset_kind']=='metric_dataset'
    assert result.items[0]['numeric_fact_authority'] is False
    observed=result.items[0]['items'][0]
    assert observed['id']==expected['id'] and observed['value']==expected['value']
    assert observed['financial_basis']==expected['financial_basis']
    card_req=req.model_copy(update={'metric_section':'card','metric_record_id':observed['id'],'query':''})
    assert len(library.navigate(card_req,'2026-09-21').items[0]['items'][0]['inputs'])==2
    legacy=SourceDocumentRequest(operation='catalog')
    assert not {'metric_section','metric_record_id','compare_entity_ids'} & legacy.model_dump().keys()
    with pytest.raises(ValueError):SourceDocumentRequest(operation='catalog',metric_section='history')


def test_card_does_not_scan_company_history_and_respects_scope(foundation,monkeypatch):
    from sec_agent.research_foundation import metric_workspace
    path,w,sid=foundation
    fact(w,sid,'assets','Assets',200,start=None)
    fact(w,sid,'liabilities','Liabilities',40,start=None)
    derived_financials.materialize(path,'2026-09-21')
    row=query_metrics(path,['NVIDIA'],section='history',metric='liabilities_to_assets')['items'][0]
    def forbidden(*args,**kwargs):raise AssertionError('card must not load history')
    monkeypatch.setattr(metric_workspace,'_rows',forbidden)
    card=query_metrics(path,['NVIDIA'],section='card',record_id=row['id'])['items'][0]
    assert card['value']==row['value'] and card['inputs']
    with pytest.raises(ValueError,match='company_not_found'):
        query_metrics(path,['unknown'],section='card',record_id=row['id'])
    with pytest.raises(ValueError,match='cutoff'):
        query_metrics(path,['NVIDIA'],section='card',record_id=row['id'],as_of='2000-01-01')
