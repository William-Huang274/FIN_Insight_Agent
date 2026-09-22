import copy
import sqlite3
import pytest
from test_industry_foundation import foundation
from test_industry_metrics import pack
from sec_agent.research_foundation.industry_metrics import import_pack
from sec_agent.research_foundation.metric_reviews import import_reviews
from sec_agent.research_foundation.metric_workspace import query_metrics


def review():
    return dict(entity_id='NVIDIA',field='comparable_history',outcome='definition_boundary',
                reason='Scope changed',next_action='Await an issuer restatement',
                comparison_rule='Do not join periods across the change',
                reviewed_materials=[dict(title='Results',url='https://example.test/results',sections=['segment note'])],
                affected_metrics=['industry.cloud_revenue'],series_rules=[dict(metrics=['industry.cloud_revenue'],
                action='points_only',reason='Scope changed',date_start='2026-01-01')])


def test_reviews_shared_between_catalog_history_card_and_time_cutoff(foundation):
    path,_,_=foundation
    import_pack(path,pack())
    with sqlite3.connect(path) as db:before=db.execute('SELECT payload FROM industry_metric_observations').fetchone()[0]
    import_reviews(path,[review()],reviewed_at='2026-09-22')
    import_reviews(path,[review()],reviewed_at='2026-09-22')
    result=query_metrics(path,['NVIDIA'],section='history',as_of='2026-09-22')
    assert result['items'][0]['chart_policy']=='points_only'
    assert len(result['industry_reviews'])==1
    rid=result['items'][0]['id']
    card=query_metrics(path,['NVIDIA'],section='card',record_id=rid,as_of='2026-09-22')
    assert card['industry_reviews']==result['industry_reviews']
    assert query_metrics(path,['NVIDIA'],section='catalog')['industry_reviews']==result['industry_reviews']
    earlier=query_metrics(path,['NVIDIA'],section='history',as_of='2026-09-21')
    assert earlier['industry_reviews']==[] and 'chart_policy' not in earlier['items'][0]
    with sqlite3.connect(path) as db:assert db.execute('SELECT payload FROM industry_metric_observations').fetchone()[0]==before


def test_review_validation_atomic_and_no_fake_resolution(foundation):
    path,_,_=foundation
    import_pack(path,pack())
    bad=review();bad['outcome']='resolved'
    with pytest.raises(ValueError,match='requires_observations'):import_reviews(path,[review(),bad],reviewed_at='2026-09-22')
    assert query_metrics(path,['NVIDIA'])['industry_reviews']==[]
    bad=review();bad['reviewed_materials'][0]['source_id']='absent'
    with pytest.raises(ValueError,match='source_not_found'):import_reviews(path,[bad],reviewed_at='2026-09-22')
    bad=review();bad['series_rules'][0]['metric_name_guess']='Cloud'
    with pytest.raises(ValueError,match='unknown_metric_rule_selector'):import_reviews(path,[bad],reviewed_at='2026-09-22')


def test_scope_partition_selectors_do_not_join_existing_products(foundation):
    path,_,_=foundation
    p=pack();second=copy.deepcopy(p['observations'][0]);second['business_scope']='Other cloud product'
    p['observations'].append(second);import_pack(path,p)
    r=review();r['series_rules']=[dict(metrics=['industry.cloud_revenue'],action='separate_series',reason='Period end versus average',series_key='average',scope_contains='Cloud segment')]
    import_reviews(path,[r],reviewed_at='2026-09-22')
    rows=query_metrics(path,['NVIDIA'],section='history')['items']
    assert next(x for x in rows if x['business_scope']=='Cloud segment')['series_scope']=='Cloud segment | average'
    assert 'series_scope' not in next(x for x in rows if x['business_scope']=='Other cloud product')
