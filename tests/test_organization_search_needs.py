from hashlib import sha256
import pytest
from retrieval.organization_search_needs import compile_needs, lexical_surfaces, lexical_candidates, select_coverage
from sec_agent.research_foundation.organization_query_plan import plan_query, select_planned


def test_comparison_union_is_not_alias_ambiguity_or_counterparty():
    data = {'a':{'issuer_id':'ORG::alpha','company_name':'Alpha'},
            'b':{'issuer_id':'ORG::beta','company_name':'Beta'},
            'c':{'issuer_id':'ORG::gamma','company_name':'Gamma'}, 'u':{}}
    plan = plan_query('Compare Alpha and Beta annual reports', data, policy='conservative.v2')
    assert select_planned(data, plan)[0] == {'a','b','u'}
    assert select_planned(data, plan_query('Compare Alpha and Beta annual reports', data))[0] == set(data)
    owner = plan_query("In Alpha's annual report, compare payments to Beta", data, policy='conservative.v2')
    # Counterparty phrasing is deliberately not claimed to mean two report owners.
    assert owner['constraint'].get('issuer_union') is None
    data['c']['company_name']='Alpha'
    ambiguous=plan_query('Compare Alpha and Beta annual reports', data, policy='conservative.v2')
    assert 'issuer_union' not in ambiguous['constraint']


def test_translation_is_separate_candidate_route_not_claim_equivalence():
    routes, matches = lexical_surfaces('Alpha 经营现金流与债务到期情况')
    assert {'operating','cash','flow','debt','maturity'} <= set(routes[0])
    assert '经营' in routes[-1] or '经营现金流' in routes[-1]
    assert all(term not in routes[0] for term in ('revenue','receivable'))
    assert lexical_surfaces('unrecognized zh 量子纠缠')[1] == []


def test_each_explicit_need_has_a_route_and_a_separate_selected_candidate(tmp_path):
    from retrieval.published_lexical_index import build, lexical_digest
    bodies=['Natural gas generation fleet overview: acquired 100 MW.',
            'Orion transaction acquired 120 MW of natural gas capacity.',
            'Orion transaction acquired 120 MW of natural gas capacity. More details.']
    rows=[dict(node_id=str(i),parent_document_id='doc',content=b,content_sha256=sha256(b.encode()).hexdigest())
          for i,b in enumerate(bodies)]
    for r in rows:r['lexical_input_sha256']=lexical_digest(r)
    path=tmp_path/'lexical.sqlite';build(path,rows)
    needs=compile_needs('请同时找出机组发展概述的收购燃气容量和 Orion 交易单独披露的容量，保留口径。', {})
    assert len(needs['needs'])==2
    ids, lanes=lexical_candidates(path,rows,needs,{})
    selected, receipt=select_coverage([rows[1],rows[2],rows[0]],needs,lanes,{})
    # Either duplicate transaction excerpt covers the second retrieval need.
    assert selected[0]['node_id']=='0' and selected[1]['node_id'] in {'1','2'}
    assert len(selected)==3 and all(r['state']=='candidate_selected_requires_readback' for r in receipt)
    missing, receipt=select_coverage([],needs,lanes,{})
    assert missing==[] and all(r['state']=='uncovered' for r in receipt)


def test_single_query_does_not_override_model_order():
    rows=[{'node_id':'a'}, {'node_id':'b'}]
    assert select_coverage(rows,compile_needs('revenue',{}),[],{})==(rows,[])


def test_source_specific_need_cannot_fill_from_other_owner():
    plan={'constraint':{'issuer_union':[{'issuer_id':'A','company_names':['Alpha']},
                                       {'issuer_id':'B','company_names':['Beta']}]}}
    needs=compile_needs('Compare Alpha and Beta revenue',plan)
    rows=[dict(node_id='a',parent_document_id='doc',content='Alpha revenue increased')]
    selected, coverage=select_coverage(rows,needs,[{'candidate_ids':['a']},{'candidate_ids':['a']}],{'doc':{'issuer_id':'A'}})
    assert len(selected)==1 and coverage[1]['state']=='uncovered'


def test_split_clauses_inherit_subject_and_unknown_owner_cannot_fill_slot():
    needs=compile_needs('In Alpha, find both acquired gas capacity and Orion transaction capacity.',
                        {'constraint':{'issuer_id':'A','company_names':['Alpha']}})
    assert all(n['owner']['issuer_id']=='A' for n in needs['needs'])
    rows=[dict(node_id='unknown',parent_document_id='u',content='acquired gas capacity Orion transaction'),
          dict(node_id='right',parent_document_id='a',content='acquired gas capacity Orion transaction')]
    selected, coverage=select_coverage(rows,needs,
        [{'candidate_ids':['unknown','right']},{'candidate_ids':['unknown','right']}],
        {'u':{},'a':{'issuer_id':'A'}})
    assert [r['selected_id'] for r in coverage]==['right','right']
    assert [r['node_id'] for r in selected]==['right','unknown']


def test_bare_report_year_is_soft_verified_preference_not_inferred_fiscal_filter():
    data={'target':{'issuer_id':'COMPANY::alpha','calendar_annual_year':'2024'},
          'later':{'issuer_id':'COMPANY::alpha','period_end':'2025-06-30','form':'10-Q'},
          'unknown':{'issuer_id':'COMPANY::alpha'}}
    query="For Alpha's 2024 report, find both fleet summary and Orion transaction capacity."
    plan=plan_query(query,data,policy='conservative.v2')
    assert 'form' not in plan['constraint'] and 'period_end' not in plan['constraint']
    assert select_planned(data,plan)[0]==set(data)
    needs=compile_needs(query,plan)
    rows=[dict(node_id=n,parent_document_id=n,content='fleet summary Orion transaction capacity')
          for n in ('later','unknown','target')]
    lanes=[{'candidate_ids':['later','unknown','target']}]*2
    selected, coverage=select_coverage(rows,needs,lanes,data)
    assert selected[0]['node_id']=='target' and len(selected)==3
    assert coverage[0]['selected_id']=='target'
    for text in ('Alpha 2024 investment', 'Alpha 2024 and 2025 reports', 'Alpha FY2024 revenue'):
        assert 'preferences' not in plan_query(text,data,policy='conservative.v2')


def test_context_keeps_original_identity_and_requires_verified_same_document():
    from retrieval.fragment_context import needs_context, attach_context
    body='Capital expenditures are approximate.'
    row=dict(node_id='a',parent_document_id='doc',content=body,content_sha256=sha256(body.encode()).hexdigest())
    neighbor={**row,'node_id':'table'}
    contextual=attach_context(row,[neighbor])
    assert needs_context(body) and contextual['content']==body and contextual['content_sha256']==row['content_sha256']
    assert contextual['context_readbacks'][0]['readback']['node_id']=='table'
    with pytest.raises(ValueError,match='cross_document'):attach_context(row,[{**neighbor,'parent_document_id':'other'}])
    with pytest.raises(ValueError,match='body_mismatch'):attach_context(row,[{**neighbor,'content':'tampered'}])
    assert attach_context(row,[])['context_status']=='context_unresolved'


def test_v2_real_navigation_cache_context_readback_and_revoke(tmp_path, monkeypatch):
    from test_organization_source_filter import scoped_fixture, query
    text='Compare Acme and Beta annual reports disclosure'
    nav, reader, state, _, _=scoped_fixture(tmp_path,monkeypatch,queries=[text])
    request=query(query=text,organization_query_planning='conservative.v2')
    first=nav.navigate(request)
    receipt=first.items[0]['retrieval']
    assert len(receipt['search_needs']['needs'])==2
    assert len(receipt['need_coverage'])==2
    assert first.organization_query_plan['constraint']['issuer_union']
    for item in first.items:
        for link in item.get('context_readbacks',[]):
            assert link['document_id']==item['document_id']
            read=nav.navigate(link['readback'])
            assert read.items[0]['content_sha256']==link['content_sha256']
    cached=nav.navigate(request)
    assert cached.items[0]['retrieval']['response_cache_hit']
    def denied(*a,**kw):raise RuntimeError('current_authority_denied')
    monkeypatch.setattr(reader,'_grant',denied)
    with pytest.raises(RuntimeError,match='current_authority_denied'):nav.navigate(request)


def test_complete_source_context_can_read_adjacent_without_mutating_vectors(tmp_path, monkeypatch):
    from test_organization_candidate_index import prepared, query
    nav, reader, state, _, grant=prepared(tmp_path,monkeypatch)
    first=nav.navigate(query(organization_query_planning='conservative.v2'))
    contextual=[r for r in first.items if r.get('context_readbacks')]
    assert contextual
    for item in contextual:
        for context in item['context_readbacks']:
            assert context['document_id']==item['document_id']
            read=nav.navigate(context['readback'])
            assert read.items[0]['content_sha256']==context['content_sha256']
    # A new navigator may reuse verification proofs including source offsets.
    from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
    again=OrganizationSourceNavigation(reader,workbench_url='http://localhost',retrieval_root=tmp_path/'indices')
    result=again.navigate(query(organization_query_planning='conservative.v2'))
    assert [i.get('context_readbacks') for i in result.items]==[i.get('context_readbacks') for i in first.items]
