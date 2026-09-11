from dataclasses import dataclass
import pytest
from retrieval.source_hybrid import prepare_source_index,rank_sources
from retrieval.qwen_api import RetrievalResponse


class API:
    embedding_model='test-embed';rerank_model='test-rerank'
    def __init__(self):self.calls=[]
    def embed(self,texts):
        self.calls.append(('embedding',texts))
        return RetrievalResponse([[1.,0.] if ('现金' in t or 'cash' in t) else [0.,1.] for t in texts],{},None,self.embedding_model)
    def rerank(self,q,docs):
        self.calls.append(('rerank',docs))
        return RetrievalResponse([{'index':i,'relevance_score':1. if 'cash' in d else 0.} for i,d in sorted(enumerate(docs),key=lambda p:'cash' not in p[1])],{},None,self.rerank_model)


def test_hybrid_cache_and_scoped_candidates(tmp_path):
    api=API();rows=[{'node_id':'cash','content':'Operating cash declined','node_kind':'text'},
        {'node_id':'sales','content':'Revenue increased','node_kind':'text'}]
    prepare_source_index(rows,'snapshot',str(tmp_path),api)
    ranked,r=rank_sources(rows,'现金','snapshot',[],path=str(tmp_path),api=api)
    assert ranked[0]['node_id']=='cash' and r['calls']==2
    prior=len(api.calls)
    assert rank_sources(rows,'现金','snapshot',[],path=str(tmp_path),api=api)[1]['calls']==0
    assert len(api.calls)==prior
    # A document filter applies before candidate construction, including dense.
    ranked,_=rank_sources(rows[1:],'现金','snapshot',[],path=str(tmp_path),api=api)
    assert [r['node_id'] for r in ranked]==['sales']
    with pytest.raises(RuntimeError,match='尚有'):
        rank_sources(rows,'现金','other_snapshot',[],path=str(tmp_path),api=api)


def test_failed_call_is_not_retried(tmp_path):
    from diskcache import Cache
    from retrieval.source_hybrid import CachedRetrieval
    api=API()
    def fail(text):api.calls.append(('failed',text));raise TimeoutError()
    api.embed=fail
    with Cache(str(tmp_path)) as cache:
        client=CachedRetrieval(cache,api,'scope')
        with pytest.raises(TimeoutError):client.embed_query('query')
        with pytest.raises(RuntimeError,match='未自动重发'):client.embed_query('query')
    assert len(api.calls)==1


def test_expansion_reuses_only_identical_text_with_same_provider_config(tmp_path):
    api=API();old=[{'node_id':'old','content':'Operating cash','node_kind':'text'}]
    prepare_source_index(old,'old',str(tmp_path),api)
    api.calls.clear()
    expanded=[*old,{'node_id':'new','content':'HBM supply','node_kind':'text'}]
    result=prepare_source_index(expanded,'new',str(tmp_path),api,reuse_snapshot='old')
    assert result['reused_vectors']==1 and result['calls']==1
    assert len(api.calls[0][1])==1 and 'HBM supply' in api.calls[0][1][0]
    api.embedding_model='changed-model';api.calls.clear()
    result=prepare_source_index(old,'changed',str(tmp_path),api,reuse_snapshot='old')
    assert result['reused_vectors']==0 and result['calls']==1
