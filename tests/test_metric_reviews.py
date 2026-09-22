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


def test_export_reimport_is_idempotent_and_same_day_revision_remains_latest(foundation):
    path,_,_=foundation
    import_pack(path,pack())
    import_reviews(path,[review()],reviewed_at='2026-09-22')
    exported=query_metrics(path,['NVIDIA'])['industry_reviews'][0]
    import_reviews(path,[exported],reviewed_at='2026-09-22')
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM industry_metric_reviews').fetchone()[0]==1
    updated=copy.deepcopy(exported)
    updated['reason']='New primary source verified; old scope still preserved'
    import_reviews(path,[updated],reviewed_at='2026-09-22')
    latest=query_metrics(path,['NVIDIA'])['industry_reviews'][0]
    assert latest['reason']==updated['reason'] and latest['id']!=exported['id']
    import_reviews(path,[latest],reviewed_at='2026-09-22')
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM industry_metric_reviews').fetchone()[0]==2


def test_review_cannot_link_a_different_original_to_a_valid_source_id(foundation):
    path,_,_=foundation
    import_pack(path,pack())
    source=query_metrics(path,['NVIDIA'],section='history')['items'][0]['source_id']
    r=review();r['reviewed_materials'][0]['source_id']=source
    r['reviewed_materials'][0]['url']='https://example.test/unrelated-report'
    with pytest.raises(ValueError,match='review_source_url_mismatch'):
        import_reviews(path,[r],reviewed_at='2026-09-22')
    assert query_metrics(path,['NVIDIA'])['industry_reviews']==[]


def test_reviewed_series_uses_only_explicit_compatible_records(foundation):
    path,_,_=foundation
    p=pack();a=p['observations'][0]
    b=copy.deepcopy(a);b.update(period_start='2025-04-01',period_end='2025-06-30',observation_date='2025-06-30',fiscal_year=2025,business_scope='Earlier wording')
    other=copy.deepcopy(a);other['business_scope']='Different product'
    p['observations'] += [b,other];import_pack(path,p)
    rows=query_metrics(path,['NVIDIA'],section='history')['items']
    ids=[x['id'] for x in rows if x['business_scope']!='Different product']
    r=review();r['series_rules']=[dict(metrics=['industry.cloud_revenue'],action='canonical_series',reason='Issuer comparative table confirms identical measurement',series_key='cloud_q2_average',series_label='云业务 Q2 同期比较',cadence='annual_same_quarter',record_ids=ids)]
    import_reviews(path,[r],reviewed_at='2026-09-22')
    rows=query_metrics(path,['NVIDIA'],section='history')['items']
    matched=[x for x in rows if x['id'] in ids]
    assert {x['series_scope'] for x in matched}=={'reviewed:cloud_q2_average'}
    assert {x['business_scope'] for x in matched}=={'Cloud segment','Earlier wording'}
    assert all(x['series_cadence']=='annual_same_quarter' for x in matched)
    assert 'series_scope' not in next(x for x in rows if x['id'] not in ids)
    assert 'series_scope' not in query_metrics(path,['NVIDIA'],section='history',as_of='2026-09-21')['items'][0]
    bad=copy.deepcopy(r);bad['series_rules'][0]['record_ids']=['missing',ids[0]]
    with pytest.raises(ValueError,match='record_not_found'):import_reviews(path,[bad],reviewed_at='2026-09-22')
    # A point-in-time balance cannot be joined into a quarterly flow series.
    instant=copy.deepcopy(a);instant.update(period_kind='instant',period_start=None,business_scope='Period end')
    p['observations']=[instant];import_pack(path,p)
    instant_id=next(x['id'] for x in query_metrics(path,['NVIDIA'],section='history')['items'] if x['period_kind']=='instant')
    bad=copy.deepcopy(r);bad['series_rules'][0]['record_ids']=[ids[0],instant_id]
    with pytest.raises(ValueError,match='incompatible_measurements'):import_reviews(path,[bad],reviewed_at='2026-09-22')


def test_evidenced_count_unit_repair_preserves_stored_record_and_cutoff(foundation):
    path,_,_=foundation
    p=pack();p['observations'][0]['unit']='persons';import_pack(path,p)
    row=query_metrics(path,['NVIDIA'],section='history')['items'][0]
    correction=dict(record_id=row['id'],from_unit='persons',to_unit='subscriptions',
                    evidence_quote=row['evidence_quote'],reason='Issuer table measures subscriptions, not unique people')
    r=review();r['series_rules']=[];r['unit_corrections']=[correction]
    invalid=copy.deepcopy(r);invalid['unit_corrections'][0]['to_unit']='USD'
    with pytest.raises(ValueError,match='unsupported_unit_correction'):
        import_reviews(path,[invalid],reviewed_at='2026-09-22')
    invalid=copy.deepcopy(r);invalid['unit_corrections'][0]['evidence_quote']='invented passage'
    with pytest.raises(ValueError,match='unsupported_unit_correction'):
        import_reviews(path,[invalid],reviewed_at='2026-09-22')
    import_reviews(path,[r],reviewed_at='2026-09-22')
    fixed=query_metrics(path,['NVIDIA'],section='card',record_id=row['id'])['items'][0]
    assert fixed['unit']=='subscriptions' and fixed['stored_unit']=='persons'
    assert fixed['value']==row['value'] and fixed['unit_correction']==correction
    assert query_metrics(path,['NVIDIA'],section='history',as_of='2026-09-21')['items'][0]['unit']=='persons'
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT unit FROM industry_metric_observations WHERE id=?',(row['id'],)).fetchone()[0]=='persons'
