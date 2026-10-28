from retrieval.published_lexical_index import build, lexical_digest
from retrieval.organization_search_needs import lexical_candidates
from hashlib import sha256


def test_bm25_trace_is_before_route_quota_and_interleave(tmp_path):
    nodes=[{'node_id':str(i),'content':'cash '* (i+1), 'content_sha256':sha256(('cash '*(i+1)).encode()).hexdigest(),
            'parent_document_id':'a'} for i in range(110)]
    path=tmp_path/'lexical.sqlite';build(path,nodes)
    for n in nodes:n['lexical_input_sha256']=lexical_digest(n)
    needs={'policy':'organization-search-needs.v1','needs':[{'id':'n','owner':None,'lexical_routes':[['cash']]}]}
    ids,lanes=lexical_candidates(path,nodes,needs,{},capture_trace=True)
    trace=lanes[0]['route_traces'][0]
    assert len(ids)==48 and len(trace['raw_bm25'])==96 and trace['trace_truncated']
    assert trace['population_count']==110 and trace['matched_count']==110
    assert len(trace['population_sha256'])==64
    assert all(type(r['score']) is float for r in trace['raw_bm25'])
    assert trace['raw_bm25'][0]['rank']==1


def test_rerank_uses_actual_catalog_field_names_and_preserves_legacy_context():
    from retrieval.rerank_document_context import with_document_context
    row={'parent_document_id':'d'}
    assert with_document_context([row],{'d':{'issuer_id':'I','company_name':'Alpha Inc.'}})[0]['rerank_document_metadata']['issuer']=='Alpha Inc.'
    assert with_document_context([row],{'d':{'issuer':'Legacy'}})[0]['rerank_document_metadata']['issuer']=='Legacy'


def test_dense_trace_survives_cache_and_remains_inside_authorization(tmp_path,monkeypatch):
    from test_organization_candidate_index import prepared,query
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_RETRIEVAL_TRACE','bounded.v1')
    nav,reader,state,_,grant=prepared(tmp_path,monkeypatch)
    document=nav._identity(grant['manifest']['inputs'][0])
    result=nav.navigate(query(document_id=document))
    trace=result.items[0]['retrieval']['dense_trace']
    assert trace['scores'] and trace['scores'][0]['rank']==1
    assert all(nav._candidate_index.rows[r['node_id']]['parent_document_id']==document for r in trace['scores'])
    assert nav.navigate(query(document_id=document)).items[0]['retrieval']['dense_trace']==trace
