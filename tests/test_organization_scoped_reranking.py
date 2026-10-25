from types import SimpleNamespace

import pytest

from test_organization_source_filter import scoped_fixture,query
from retrieval.qwen_api import RetrievalResponse
from retrieval.scoped_reranking import ScopedReranker
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable


def setup(tmp_path,monkeypatch):
    nav,reader,state,directory,grant=scoped_fixture(tmp_path,monkeypatch)
    calls=[]
    def provider(query,documents,**kwargs):
        calls.append(documents)
        return RetrievalResponse([{'index':i,'relevance_score':i/len(documents)}
                                  for i in reversed(range(len(documents)))],{'total_tokens':17},'test','qwen3-rerank')
    api=SimpleNamespace(rerank_model='qwen3-rerank',rerank=provider)
    nav.hybrid.reranker=ScopedReranker(tmp_path/'rerank-cache',api)
    return nav,reader,state,calls,api


def test_only_current_filtered_candidates_sent_and_response_cache_no_double_usage(tmp_path,monkeypatch):
    nav,reader,state,calls,api=setup(tmp_path,monkeypatch)
    request=query(organization_filter={'company_name':'Acme','form':'10-K'},entity_id='COUNTERPARTY::X',limit=20)
    result=nav.navigate(request)
    assert 'no external rerank' not in result.notice
    assert 'inspect the retrieval receipt' in result.notice
    receipt=result.items[0]['retrieval']
    assert receipt['mode']=='organization-cosine-bm25-graph-qwen-rerank.v1'
    assert receipt['reranked_node_ids']==list(reversed(receipt['candidate_node_ids']))
    assert len(calls)==1 and receipt['rerank_response']['newly_reported_usage']=={'total_tokens':17}
    for node in receipt['candidate_node_ids']:
        meta=nav._candidate_index.source_metadata[nav._candidate_index.rows[node]['parent_document_id']]
        assert meta['company_name']=='Acme' and meta['form']=='10-K'
    cached=nav.navigate(request).items[0]['retrieval']
    assert cached['provider_calls']==0 and cached['rerank_response']['newly_reported_usage']=={}
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):nav.navigate(request)
    assert len(calls)==1


def test_revocation_during_rerank_does_not_publish_result(tmp_path,monkeypatch):
    nav,reader,state,calls,api=setup(tmp_path,monkeypatch)
    original=api.rerank
    def revoke(*a,**kw):
        result=original(*a,**kw);state['status']=404;return result
    api.rerank=revoke
    with pytest.raises(OrganizationExecutionUnavailable):nav.navigate(query())
    assert nav._search_cache.entry is None
    state['status']=200
    result=nav.navigate(query())
    assert result.items[0]['retrieval']['rerank_response']['provider_calls']==0
    assert len(calls)==1


def test_failed_rerank_not_hidden_as_rrf_or_retried(tmp_path,monkeypatch):
    nav,reader,state,calls,api=setup(tmp_path,monkeypatch)
    def fail(*args,**kwargs):calls.append(1);raise TimeoutError('unknown')
    api.rerank=fail
    with pytest.raises(TimeoutError):nav.navigate(query())
    with pytest.raises(RuntimeError,match='no_resubmission'):nav.navigate(query())
    assert nav._search_cache.entry is None and len(calls)==1
