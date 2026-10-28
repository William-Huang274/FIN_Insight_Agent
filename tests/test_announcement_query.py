import pytest
from retrieval.announcement_query import event_requirements


@pytest.mark.parametrize('query',[
    '有人把发布日期当作业绩所对应的季度末，称新闻稿在附件104，核对财报季度和附件编号。',
    'A summary treats the release date as the financial quarter end. Find the press release and reporting quarter.',
    'Find the press release reporting earnings, not a financing release.',
    '找业绩新闻稿，不要融资公告。',
    'Find earnings 8-K and its exhibit.',
])
def test_announcement_question_and_counterclaim_keep_financial_event(query):
    assert event_requirements(query)==['earnings_release']


@pytest.mark.parametrize('query',[
    'Find the press release announcing the credit facility.',
    '找融资新闻稿及附件。',
])
def test_financing_announcement_stays_distinct(query):
    assert event_requirements(query)==['financing']


@pytest.mark.parametrize('query',[
    'Compare the earnings release and financing announcement.',
    'Find the press release about financing during that financial quarter.',
    'Find the press release and date.',
    'Find cash at the financial quarter end.',
    '找新闻稿，同时比较业绩和融资情况。',
])
def test_ambiguous_or_missing_subject_does_not_guess_event(query):
    assert event_requirements(query)==[]


def test_event_plan_and_lexical_needs_share_positive_announcement_intent():
    from retrieval.evidence_scope import plan_scope
    from retrieval.organization_search_needs import compile_needs, lexical_surfaces
    query='有人把发布日期当作业绩所对应的季度末，称新闻稿在附件104，核对财报季度和附件编号。'
    assert plan_scope(query)['event_type']==['earnings_release']
    needs=compile_needs(query,{'policy':'conservative.v5'})
    assert 'earnings_release' in needs['financial_concepts']
    assert any('earnings' in route for n in needs['needs'] for route in n['lexical_routes'])
    routes,_=lexical_surfaces(query)
    assert {'press','release','exhibit','reporting','quarter'} <= set(routes[0])


def test_mixed_announcement_query_preserves_both_events_as_unknown():
    from retrieval.evidence_scope import plan_scope
    result=plan_scope('Compare the financing press release with the earnings release')
    assert not (result or {}).get('event_type')
