from hashlib import sha256
import pytest
from retrieval.organization_search_needs import compile_needs, lexical_candidates, select_coverage
from sec_agent.research_foundation.organization_query_plan import plan_query


def needs(query):
    return compile_needs(query, {'policy':'conservative.v4'})


def test_financial_variants_preserve_distinct_evidence_needs():
    result=needs('现金及现金等价物中排除了多少受限现金？')
    assert result['financial_concepts']==['cash_equivalents','restricted_cash']
    assert len(result['needs'])==2
    for n in result['needs']:
        assert 'revenue' not in n['concept_terms']
    result=needs('unused share-repurchase authorization and financing option')
    assert set(result['financial_concepts'])=={'repurchase_authorization','financing'}
    assert 'repurchases' in result['needs'][0]['concept_terms']
    assert 'indebtedness' in result['needs'][1]['concept_terms']


def test_earnings_event_route_does_not_only_match_release_boilerplate(tmp_path):
    from retrieval.published_lexical_index import build, lexical_digest
    bodies=['On August 10 the company issued a press release announcing a financing facility. Exhibit 99.1.']*12
    bodies+=['The company announced earnings results in a release for the quarter.']
    rows=[dict(node_id=str(i),parent_document_id='d',content=b,content_sha256=sha256(b.encode()).hexdigest()) for i,b in enumerate(bodies)]
    for r in rows:r['lexical_input_sha256']=lexical_digest(r)
    path=tmp_path/'lexical.sqlite';build(path,rows)
    for query in ['Alpha earnings release date and exhibit', 'Alpha业绩公告发布日期和附件']:
        result=compile_needs(query,{'policy':'conservative.v5'})
        assert result['financial_concepts']==['earnings_release']
        ids,lanes=lexical_candidates(path,rows,result,{})
        assert ids[0]=='12'
        assert len(lanes[0]['route_ids'])==2  # Literal query preserved.
    result=compile_needs('Not an earnings release, find the financing announcement',{'policy':'conservative.v5'})
    assert 'earnings_release' not in result['financial_concepts']


def test_expiration_context_not_blind_translation_or_fiscal_period_inference():
    auth=needs('回购授权到期时间')
    assert 'authorization_expiration' in auth['financial_concepts']
    assert 'maturity' not in {t for n in auth['needs'] for t in n['concept_terms']}
    debt=needs('债务到期时间')
    assert debt['financial_concepts']==['debt_maturity']
    assert needs('FY2025 未知概念')['financial_concepts']==[]


def test_convertible_maturity_forms_have_typed_bilingual_lexical_routes(tmp_path):
    from retrieval.published_lexical_index import build, lexical_digest
    for query in ['可转债的到期日是什么', '可转换债券何时到期',
                  'When do the notes mature?', 'The bond matured last year', 'loan maturity']:
        result=needs(query)
        assert result['financial_concepts']==['debt_maturity']
        assert 'mature' in result['needs'][0]['concept_terms']
    assert needs('The product reaches maturity')['financial_concepts']==[]
    assert set(needs('回购授权到期时间')['financial_concepts'])=={'repurchase_authorization','authorization_expiration'}
    bodies=['Customer receivables mature next year.']*12+[
        'The convertible notes will mature in December and bear interest per year.']
    rows=[dict(node_id=str(i),parent_document_id='d',content=b,content_sha256=sha256(b.encode()).hexdigest()) for i,b in enumerate(bodies)]
    for r in rows:r['lexical_input_sha256']=lexical_digest(r)
    path=tmp_path/'lexical.sqlite';build(path,rows)
    ids,_=lexical_candidates(path,rows,needs('可转债的到期日是什么'),{})
    assert ids[0]=='12'


def test_owner_spans_assign_different_measures_and_shared_topics_remain_shared():
    metadata={'a':{'issuer_id':'I::alpha'},'b':{'issuer_id':'I::beta'}}
    query="Compare Alpha's equity commitments and investment capacity with Beta's capital expenditures."
    result=compile_needs(query,plan_query(query,metadata,policy='conservative.v4'))
    assert [(n['owner']['issuer_id'],n['concept']) for n in result['needs']]==[
        ('I::alpha','equity_commitments'),('I::alpha','investment_capacity'),('I::beta','capital_expenditures')]
    query='Compare Alpha and Beta capital expenditures'
    result=compile_needs(query,plan_query(query,metadata,policy='conservative.v4'))
    assert len(result['needs'])==2 and all(n['concept']=='capital_expenditures' for n in result['needs'])


def test_real_postings_need_allocation_preserves_second_fact_and_old_policy(tmp_path):
    from retrieval.published_lexical_index import build, lexical_digest
    bodies=['equity commitments fund equity commitment']*15+['total investment capacity support']
    bodies += ['support support capacity capacity capacity']*15
    rows=[dict(node_id=str(i),parent_document_id='d',content=b,content_sha256=sha256(b.encode()).hexdigest()) for i,b in enumerate(bodies)]
    for r in rows:r['lexical_input_sha256']=lexical_digest(r)
    path=tmp_path/'lexical.sqlite';build(path,rows)
    query='股权出资承诺可支持多少总投资？'
    result=needs(query); ids,lanes=lexical_candidates(path,rows,result,{})
    assert '15' in ids[:2]
    ordered,coverage=select_coverage(rows,result,lanes,{})
    assert '15' in [r['node_id'] for r in ordered[:2]]
    assert all(r['state']=='candidate_selected_requires_readback' for r in coverage)
    assert compile_needs(query,{'policy':'conservative.v3'})['policy']=='organization-search-needs.v1'


def test_v4_serving_consumes_financial_needs_and_cache_revocation(tmp_path,monkeypatch):
    from test_organization_source_filter import scoped_fixture,query
    text='Acme cash and cash equivalents and restricted cash'
    nav,reader,state,_,_=scoped_fixture(tmp_path,monkeypatch,queries=[text])
    request=query(query=text,organization_query_planning='conservative.v4')
    result=nav.navigate(request)
    assert result.items[0]['retrieval']['search_needs']['policy']=='organization-financial-needs.v2'
    assert nav.navigate(request).items[0]['retrieval']['response_cache_hit']
    def deny(*a,**kw):raise RuntimeError('current_authority_denied')
    monkeypatch.setattr(reader,'_grant',deny)
    with pytest.raises(RuntimeError,match='current_authority_denied'):nav.navigate(request)
