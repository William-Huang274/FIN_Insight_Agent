from math import sqrt
from hashlib import sha256
import numpy as np
import pytest
from test_semantic_units import row
from retrieval.semantic_unit_catalog import build as plan
from retrieval.semantic_unit_index import build,validate,rank
from retrieval.organization_search_needs import compile_needs


def vec(score):return [score,sqrt(1-score*score)]+[0.]*1022


def fixture(tmp_path):
    text='[TABLE:1]\nCash equivalents | 300\n[/TABLE]\nUnrelated tail'
    end=100+text.index('[/TABLE]')+8
    bad=row(text,[{'source_char_start':100,'source_char_end':end,
        'attributes':{'statement_role':'supplemental'}}])
    bad['node_id']='mixed'
    good=row('Cash equivalents | 20',[{'source_char_start':100,'source_char_end':121,
        'attributes':{'statement_role':'primary'}}]);good['node_id']='correct'
    originals=[bad,good]
    parents=[{'node_id':r['node_id'],'document_id':'doc','content_sha256':r['content_sha256'],
        'embedding_input_sha256':r['embedding_input_sha256'],'vector_index':i} for i,r in enumerate(originals)]
    plan(tmp_path/'plan.sqlite',list(zip(originals,range(2))))
    def receipt(unit):
        return {'model':'qwen3.7-text-embedding','input_sha256':unit['embedding_input_sha256'],
                'vector':vec(.99 if '300' in unit['content'] else .1)}
    matrix=np.array([vec(.99),vec(.8)],dtype=np.float32)
    published=tmp_path/'published';published.mkdir()
    descriptor=build(published,tmp_path/'plan.sqlite',parents,matrix,receipt,model='qwen3.7-text-embedding',
                     original_reader=lambda p:originals[p['vector_index']])
    metadata=[{**p,'parent_document_id':'doc','evidence_scopes':r['source_structure']['evidence_scopes']}
              for p,r in zip(parents,originals)]
    return published,descriptor,parents,metadata


def test_wrong_table_vector_cannot_leak_through_unclassified_tail(tmp_path):
    directory,descriptor,parents,metadata=fixture(tmp_path)
    validate(directory,descriptor,parents,'qwen3.7-text-embedding')
    needs=compile_needs('cash equivalents',{'policy':'conservative.v5','constraint':{}})
    unfiltered,_,=rank(directory,metadata,vec(1.),needs,{'doc':{}},None,policy='needs_window.v4')
    scoped,receipt=rank(directory,metadata,vec(1.),needs,{'doc':{}},
        {'statement_role':['primary'],'unknown_policy':'retain'},policy='needs_window.v4')
    assert unfiltered['dense'][0]=='mixed'
    assert scoped['dense'][0]=='correct'
    # Mixed tail remains discoverable; its own vector is low, not .99.
    scores={r['node_id']:r['score'] for r in receipt['dense_trace']['scores']}
    assert scores['mixed']==pytest.approx(.1)
    assert scoped['lexical']==['correct']
    assert receipt['lexical_needs'][0]['unit_bindings'][0][0]['parent_node_id']=='correct'


def test_repeated_units_do_not_spend_parent_route_quota(tmp_path):
    from retrieval.published_lexical_index import build as build_lexical
    from retrieval.organization_search_needs import lexical_candidates
    records=[];groups={}
    for i in range(60):
        text='cash equivalents '+('cash '*(60-i))
        identity='u'+str(i);digest=sha256(text.encode()).hexdigest()
        records.append({'node_id':identity,'parent_document_id':'doc','content':text,
                        'content_sha256':digest,'lexical_input_sha256':digest})
        groups[identity]='one-large-parent' if i<59 else 'another-parent'
    path=tmp_path/'lexical.sqlite';build_lexical(path,records)
    needs=compile_needs('cash equivalents',{'policy':'conservative.v5','constraint':{}})
    ids,_=lexical_candidates(path,records,needs,{'doc':{}},result_groups=groups)
    assert set(ids)=={'one-large-parent','another-parent'}


def test_unit_index_rejects_mismatched_file_and_parent_scope(tmp_path):
    directory,descriptor,parents,_=fixture(tmp_path)
    with pytest.raises(ValueError,match='parent_scope'):
        validate(directory,descriptor,[{**r,'document_id':'foreign'} for r in parents],'qwen3.7-text-embedding')
    with (directory/'unit-vectors.npy').open('ab') as stream:stream.write(b'x')
    with pytest.raises(ValueError,match='file_mismatch'):
        validate(directory,descriptor,parents,'qwen3.7-text-embedding')


def test_published_units_run_through_organization_navigation_and_revoke_cached_access(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4
    from test_organization_candidate_index import prepared,query
    from test_organization_execution_access import runtime_at,runtime_grant
    from sec_agent.research_foundation.organization_hybrid_retrieval import publish_prepared_index
    from sec_agent.research_foundation.organization_index_release import load_release
    from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
    nav,reader,_,directory,grant=prepared(tmp_path,monkeypatch)
    nav.warm_release()
    _,index,matrix,_=nav.hybrid.load_frozen(grant['manifest'])
    candidates=nav._candidate_index
    identities=[candidates.rows[r['node_id']] for r in index['records']]
    originals=candidates.materialize(identities,grant['manifest'])
    contextualized=candidates.contextualize(originals,grant['manifest'])
    plan(tmp_path/'plan.sqlite',[(r,i) for i,r in enumerate(contextualized)])
    def receipt(unit):
        return {'model':'qwen3.7-text-embedding','input_sha256':unit['embedding_input_sha256'],'vector':vec(1.)}
    release=str(uuid4());org=grant['organization_id']
    publish_prepared_index(tmp_path/'indices',org,originals,matrix,{'disclosure':vec(1.)},
        model=index['model'],provenance={'synthetic_fixture':True},release_id=release,
        projection=index['projection'],semantic_catalog=tmp_path/'plan.sqlite',semantic_embedding_reader=receipt)
    _,_,_,contract=load_release(tmp_path/'indices',org,release)
    grant['manifest']['retrieval_index']=contract
    new_reader,state=runtime_at(SimpleNamespace(workspace=reader.workspace),runtime_grant(grant))
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_SEARCH_PROFILE','research.v2')
    active=OrganizationSourceNavigation(new_reader,workbench_url='http://localhost',retrieval_root=tmp_path/'indices')
    result=active.navigate(query(organization_query_planning='conservative.v5'))
    receipt=result.items[0]['retrieval']
    assert receipt['semantic_units']['unit_population']>0
    assert receipt['serving_profile']['name']=='research.v2'
    assert receipt['candidate_policy']=='needs_units.v1'
    assert '_eligible_parent_ids' not in receipt['semantic_units']
    assert receipt['provider_calls']==0
    assert active.navigate(query(organization_query_planning='conservative.v5')).items[0]['retrieval']['response_cache_hit']
    # A historical component remains readable, but the new research profile
    # cannot quietly serve it or pay for a query against its old input policy.
    original_load=active.hybrid.load_frozen
    def legacy_component(*args,**kwargs):
        directory,index,matrix,contract=original_load(*args,**kwargs)
        return directory,{**index,'semantic_units':{**index['semantic_units'],'format':'published-original-unit-index.v1'}},matrix,contract
    monkeypatch.setattr(active.hybrid,'load_frozen',legacy_component)
    def forbidden(*args,**kwargs):raise AssertionError('Must reject legacy unit input before paid query')
    active.hybrid.query_source=SimpleNamespace(embed=forbidden)
    with pytest.raises(ValueError,match='requires_identity_context_publication'):
        active.navigate(query(query='new question needs a vector',organization_query_planning='conservative.v5'))
    monkeypatch.setattr(active.hybrid,'load_frozen',original_load)
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):active.navigate(query(organization_query_planning='conservative.v5'))


def test_unit_policy_without_published_units_fails_before_query_provider(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from test_organization_candidate_index import prepared,query
    nav,*_=prepared(tmp_path,monkeypatch)
    nav.hybrid.candidate_policy='needs_units.v1'
    def forbidden(*args,**kwargs):raise AssertionError('Must not pay for an unusable publication')
    nav.hybrid.query_source=SimpleNamespace(embed=forbidden)
    with pytest.raises(ValueError,match='requires_unit_publication'):
        nav.navigate(query(query='new unpublished question',organization_query_planning='conservative.v5'))
