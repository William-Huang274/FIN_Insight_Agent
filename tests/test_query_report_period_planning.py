import pytest
from sec_agent.research_foundation.organization_query_plan import plan_query, select_planned


def catalog():
    return {'current': {'issuer_id':'COMPANY::acme', 'form':'10-Q', 'period_end':'2025-03-31'},
            'prior': {'issuer_id':'COMPANY::acme', 'form':'10-Q', 'period_end':'2024-12-31'},
            'other': {'issuer_id':'COMPANY::other', 'form':'10-Q', 'period_end':'2025-03-31'},
            'unknown': {}}


@pytest.mark.parametrize('query', [
    'Acme截至2025年3月31日的10-Q中，现金多少？',
    "Acme's 10-Q for March 31, 2025 cash versus prior quarter",
    'Acme截至2025年3月31日的季度披露中，受限现金是多少？对比2024年12月31日的余额',
    'Acme截至2025年3月31日的10-Q中，流动和非流动部分各自是多少？',
])
def test_v5_explicit_report_and_temporal_comparison_preserve_owner(query):
    data=catalog();plan=plan_query(query,data,policy='conservative.v5')
    assert plan['constraint']['issuer_id']=='COMPANY::acme'
    assert plan['constraint']['period_end']=='2025-03-31'
    assert select_planned(data,plan)[0]=={'current','unknown'}


def test_v5_english_tokens_next_to_chinese_keep_ascii_word_boundaries():
    data=catalog()
    plan=plan_query('Acme的10-Q中现金是多少？',data,policy='conservative.v5')
    assert plan['constraint']['issuer_id']=='COMPANY::acme'
    assert plan['constraint']['form']=='10-Q'
    assert 'issuer_id' not in plan_query('MetaAcme的现金',data,policy='conservative.v5')['constraint']
    assert 'form' not in plan_query('Acme X10-Qvalue',data,policy='conservative.v5')['constraint']


def test_v5_unrecognized_second_company_and_filing_date_still_abstain():
    data=catalog()
    plan=plan_query('Compare Unknown and Acme 10-Q filed on March 31, 2025',data,policy='conservative.v5')
    assert 'issuer_id' not in plan['constraint']
    assert 'period_end' not in plan['constraint']


def test_older_policy_behavior_not_reinterpreted():
    for policy in ['conservative.v1','conservative.v2','conservative.v3','conservative.v4']:
        plan=plan_query("Acme's 10-Q for March 31, 2025 cash",catalog(),policy=policy)
        assert 'period_end' not in plan['constraint']


def test_dated_report_owner_does_not_treat_balance_comparison_as_two_companies():
    plan=plan_query("In Acme's March 31, 2025 10-Q compare cash with December 31, 2024",catalog(),policy='conservative.v5')
    assert plan['constraint']['issuer_id']=='COMPANY::acme'
    # Adjacent date names the report, but is not enough to distinguish a filing
    # date from period end. Only the owner, not the period, is narrowed.
    assert 'period_end' not in plan['constraint']


def test_explicit_dated_report_owner_beats_a_later_short_counterparty_name():
    data={'long':{'issuer_id':'COMPANY::acmeservices'},'short':{'issuer_id':'COMPANY::acme'}}
    plan=plan_query("In Acme Services' June 30, 2024 10-Q can Acme use these assets?",data,policy='conservative.v5')
    assert plan['constraint']['issuer_id']=='COMPANY::acmeservices'
