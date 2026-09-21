import copy
import sqlite3
import pytest
from test_industry_foundation import foundation
from sec_agent.research_foundation.industry_metrics import import_pack, calculate_ratio
from sec_agent.research_foundation.metric_workspace import query_metrics, materialize_contract


def pack():
    return dict(as_of='2026-09-22',companies=['NVIDIA'],
        sources=[dict(ref='s',url='https://example.test/results',title='Results',published_at='2026-08-01',body='Q2 2026 cloud revenue was 123 million USD.',scope='quoted results section')],
        definitions=[dict(metric='industry.cloud_revenue',label='云收入',unit='USD',business_definition='Cloud segment')],
        observations=[dict(entity_id='NVIDIA',metric='industry.cloud_revenue',label='云收入',value='123000000',unit='USD',period_start='2026-04-01',period_end='2026-06-30',observation_date='2026-06-30',fiscal_year=2026,fiscal_period='Q2',period_kind='quarter',value_state='actual',source_ref='s',evidence_quote='Q2 2026 cloud revenue was 123 million USD.',evidence_locator='Results',value_in_source='123',scale='1000000',comparator='eq',business_scope='Cloud segment',qualifiers=[])],
        coverage=[dict(entity_id='NVIDIA',reviewed_sources=['s'],periods_reviewed=['2026Q2'],completed_fields=['industry.cloud_revenue'],gaps=[])])


def test_import_idempotent_provenance_and_asof(foundation):
    path,_,_=foundation
    import_pack(path,pack());import_pack(path,pack())
    result=query_metrics(path,['NVIDIA'],section='history')
    assert result['total']==1
    r=result['items'][0]
    assert r['value']=='123000000' and r['financial_basis']['fiscal_period']=='Q2'
    card=query_metrics(path,['NVIDIA'],section='card',record_id=r['id'])['items'][0]
    assert card['evidence_quote']==pack()['sources'][0]['body']
    assert card['sources'][0]['url']=='https://example.test/results'
    assert query_metrics(path,['NVIDIA'],section='history',as_of='2026-07-31')['total']==0
    assert materialize_contract(path)==1
    with sqlite3.connect(path) as db:
        stored=db.execute('SELECT record_id,observation_date,fiscal_period FROM metric_observation_index').fetchone()
        assert stored==(r['id'],'2026-06-30','Q2')


def test_explicit_loss_requires_evidence_and_positive_scale(foundation):
    path,_,_=foundation
    p=pack();p['sources'][0]['body']='Operating income was a loss of 123 million USD.'
    p['observations'][0].update(evidence_quote=p['sources'][0]['body'],sign='negative',value='-123000000')
    import_pack(path,p)
    assert query_metrics(path,['NVIDIA'],section='history')['items'][0]['value']=='-123000000'
    p['observations'][0]['scale']='-1000000'
    with pytest.raises(ValueError,match='scale_must_be_positive'):import_pack(path,p)


def test_word_threshold_preserves_literal_and_operator(foundation):
    path,_,_=foundation
    p=pack();p['sources'][0]['body']='More than one billion weekly active users.'
    p['observations'][0].update(evidence_quote=p['sources'][0]['body'],value='1000000000',value_in_source='one billion',scale='1',source_number_basis='english_number_words_v1',comparator='gt')
    import_pack(path,p)
    r=query_metrics(path,['NVIDIA'],section='history')['items'][0]
    assert (r['value'],r['comparator'],r['value_in_source'])==('1000000000','gt','one billion')


@pytest.mark.parametrize('field,value,error',[
    ('value','123','scale_mismatch'),('evidence_quote','not there','quote_not_in_source'),
    ('period_end','2027-06-30','future_actual'),('comparator','guessed','invalid_comparator')])
def test_reject_bad_pack_before_writes(foundation,field,value,error):
    path,_,_=foundation
    bad=pack();bad['observations'][0][field]=value
    with pytest.raises(ValueError,match=error):import_pack(path,bad)
    with sqlite3.connect(path) as db:
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='industry_metric_observations'").fetchone()


def test_null_text_and_threshold_are_not_zero(foundation):
    path,_,_=foundation
    p=pack();p['sources'][0]['body']='More than 123 million USD; growth was strong.'
    p['observations'][0].update(comparator='gt',evidence_quote=p['sources'][0]['body'])
    second=copy.deepcopy(p['observations'][0]);second.update(metric='industry.growth_text',value=None,text_value='growth was strong',comparator='text')
    p['observations'].append(second);p['definitions'].append(dict(metric='industry.growth_text',label='增长描述',unit='text'))
    import_pack(path,p)
    rows=query_metrics(path,['NVIDIA'],section='history')['items']
    assert {r['comparator'] for r in rows}=={'gt','text'}
    assert next(r for r in rows if r['comparator']=='text')['value'] is None


def test_reviewed_ratio_retains_operands_and_refuses_scope_mismatch(foundation):
    path,_,_=foundation
    p=pack();second=copy.deepcopy(p['observations'][0]);second.update(metric='industry.cloud_profit')
    p['observations'].append(second);p['definitions'].append(dict(metric='industry.cloud_profit',label='云利润',unit='USD'))
    import_pack(path,p)
    rows=query_metrics(path,['NVIDIA'],section='history')['items']
    ratio=calculate_ratio(path,numerator_id=rows[0]['id'],denominator_id=rows[1]['id'],metric='industry.test_margin',label='测试利润率',reviewed_scope='same segment, same period, same basis')
    assert ratio['value']=='100' and len(ratio['inputs'])==2
    card=query_metrics(path,['NVIDIA'],section='card',record_id=ratio['id'])['items'][0]
    assert card['record_type']=='calculated' and card['sources']
    bad=copy.deepcopy(p);bad['observations']=bad['observations'][:1];bad['observations'][0]['unit']='CNY'
    import_pack(path,bad)
    wrong=next(r for r in query_metrics(path,['NVIDIA'],section='history')['items'] if r['unit']=='CNY')
    with pytest.raises(ValueError,match='mismatch'):calculate_ratio(path,numerator_id=rows[0]['id'],denominator_id=wrong['id'],metric='x',label='x',reviewed_scope='must reject mixed currency')
