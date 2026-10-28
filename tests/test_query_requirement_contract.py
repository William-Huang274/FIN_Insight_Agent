"""Company-independent regression for polarity, owner topics and source identity."""
import pytest
from retrieval.query_requirements import positive_view
from retrieval.organization_search_needs import compile_needs
from retrieval.evidence_scope import plan_scope
from sec_agent.research_foundation.organization_query_plan import plan_query, select_planned
from sec_agent.research_foundation.organization_source_filter import OrganizationSourceFilter, select_documents


def catalog(first='North Harbor', second='Silver Lake'):
    return {'annual':{'issuer_id':'I::first','company_name':first+' Inc.','form':'10-K'},
            'event':{'issuer_id':'I::first','company_name':first+' Inc.','form':'8-K'},
            'other':{'issuer_id':'I::second','company_name':second+' Inc.','form':'10-K'}}


@pytest.mark.parametrize('a,b',[('North Harbor','Silver Lake'),('Amber Works','Cedar Systems')])
@pytest.mark.parametrize('suffix',['earnings release, not its 10-K', '业绩公告，不要10-K'])
def test_negated_form_does_not_invert_scope(a,b,suffix):
    data=catalog(a,b);p=plan_query(a+' '+suffix,data,policy='conservative.v5')
    assert 'form' not in p['constraint']
    assert p['constraint']['excluded_forms']==['10-K']
    assert select_planned(data,p)[0]=={'event'}


def test_positive_constraints_survive_excluded_subsidiary():
    q='North Harbor consolidated balance sheet cash, not subsidiary cash'
    p=plan_query(q,catalog(),policy='conservative.v5')
    scope=plan_scope(q,p)
    assert scope['statement_type']==['balance_sheet']
    assert scope['consolidation']==['consolidated']
    assert scope['reporting_entity']==['North Harbor Inc.']


@pytest.mark.parametrize('q',[
    'North Harbor cash equivalents excluding restricted cash',
    'North Harbor 现金及现金等价物，不包括受限现金'])
def test_excluded_concept_is_not_a_positive_coverage_requirement(q):
    p=plan_query(q,catalog(),policy='conservative.v5');n=compile_needs(q,p)
    assert n['financial_concepts']==['cash_equivalents']
    assert n['excluded_requirements']
    assert all(q==need['text'] for need in n['needs'])  # Original question remains available.


def test_questions_about_exclusions_and_not_only_are_not_exclusion_commands():
    for q in ['Does the reported cash not include restricted cash?',
              'Not only cash equivalents but also restricted cash',
              '现金及现金等价物中排除了多少受限现金？']:
        assert positive_view(q)[0]==q


@pytest.mark.parametrize('topic,expected',[('revenue','revenue'),('widget throughput',None)])
def test_owner_with_unknown_topic_cannot_inherit_other_company_fact(topic,expected):
    q=f'Compare North Harbor cash equivalents with Silver Lake {topic}.'
    n=compile_needs(q,plan_query(q,catalog(),policy='conservative.v5'))
    assert [(r['owner']['issuer_id'],r.get('concept')) for r in n['needs']]==[
        ('I::first','cash_equivalents'),('I::second',expected)]
    if expected is None:assert 'widget' in n['needs'][1]['lexical_routes'][0]


def test_multiple_known_measures_are_independent_and_shared_topic_remains_shared():
    q='North Harbor operating income and capital expenditures'
    n=compile_needs(q,plan_query(q,catalog(),policy='conservative.v5'))
    assert n['financial_concepts']==['capital_expenditures','operating_income']
    q='Compare North Harbor and Silver Lake cash equivalents'
    n=compile_needs(q,plan_query(q,catalog(),policy='conservative.v5'))
    assert len(n['needs'])==2 and all(r['concept']=='cash_equivalents' for r in n['needs'])


def test_known_measure_does_not_erase_an_unknown_independent_topic():
    q='North Harbor cash and cash equivalents and widget throughput'
    n=compile_needs(q,plan_query(q,catalog(),policy='conservative.v5'))
    assert len(n['needs'])==2
    assert n['needs'][0]['concept']=='cash_equivalents'
    assert n['needs'][1]['concept'] is None
    assert n['needs'][1]['text']=='widget throughput'


def test_report_year_word_order_is_equivalent_without_fact_period_guess():
    for q in ['North Harbor 2023 10-K cash','North Harbor 10-K 2023 cash',
              'North Harbor annual report for fiscal year 2023 cash']:
        p=plan_query(q,catalog(),policy='conservative.v5')
        assert p['constraint']['annual_report_year']=='2023'
        assert 'period_end' not in p['constraint']


def test_company_specific_dates_do_not_form_a_cross_product_of_requirements():
    q='Compare North Harbor cash equivalents as of 2024-12-31 with Silver Lake cash equivalents as of 2025-12-31'
    n=compile_needs(q,plan_query(q,catalog(),policy='conservative.v5'))
    assert [(r['owner']['issuer_id'],r['period_target']) for r in n['needs']]==[
        ('I::first',{'kind':'date','value':'2024-12-31'}),
        ('I::second',{'kind':'date','value':'2025-12-31'})]


def test_explicit_name_filter_uses_verified_legal_names_without_merging_ids():
    data={'a':{'issuer_id':'I::first','company_name':None,'verified_company_names':['North Harbor Inc.']},
          'b':{'issuer_id':'I::second','company_name':'North Harbor Systems Inc.'},'unknown':{}}
    selected,receipt=select_documents(data,OrganizationSourceFilter(company_name='North Harbor'))
    assert selected=={'a'} and receipt['unknown_sources']==1
    selected,_=select_documents(data,OrganizationSourceFilter(company_name='North Harbor',issuer_id='I::second'))
    assert not selected
