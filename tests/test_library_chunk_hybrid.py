"""Retrieval plumbing/authority tests; synthetic ranking is not recall evidence."""
import json
import sqlite3

import pytest

from retrieval.library_chunks import build_chunks
from retrieval.library_hybrid import rank
from retrieval import library_vectors
from retrieval.qwen_api import RetrievalResponse
from sec_agent.research_foundation.research_library import ResearchLibrary,digest_file


@pytest.mark.parametrize('model',['text-embedding-v4','qwen3.7-text-embedding'])
def test_complete_child_reranked_and_date_document_scope_preserved(tmp_path,monkeypatch,model):
    from test_research_library import publish
    _,path,manifest=publish(tmp_path)
    body='# Customers\n'+('Regular filler. '*245)+'Capacity obligation 12 MW at end.'
    with sqlite3.connect(path) as db:db.execute('UPDATE passages SET body=?',(body,))
    build_chunks(path)
    manifest['sha256']=digest_file(path)
    path.with_suffix('.sqlite.manifest.json').write_text(json.dumps(manifest),encoding='utf8')
    lib=ResearchLibrary(path)
    class API:
        embedding_model=model;rerank_model='qwen3-rerank';constructed_models=[]
        def __init__(self,*args,**kwargs):
            self.texts=[];self.calls=0
            if 'embedding_model' in kwargs:self.constructed_models.append(kwargs['embedding_model'])
        def close(self):pass
        def embed(self,texts,dimensions=1024):
            self.calls+=1
            return RetrievalResponse([[1.]+[0.]*(dimensions-1) for _ in texts],{},'embed',self.embedding_model)
        def rerank(self,query,documents):
            self.calls+=1;self.texts=documents
            return RetrievalResponse([{'index':i,'relevance_score':1.} for i in range(len(documents))],{},'rerank',self.rerank_model)
    monkeypatch.setattr(library_vectors,'QwenRetrieval',API)
    root=tmp_path/'vectors'
    library_vectors.prepare(lib,root,'unused',tmp_path/'audit',execute=True,model=model)
    api=API()
    rows,receipt=rank(lib,'Capacity','2025-02-01',[],path=root,entity_id='A',api=api)
    assert rows and all(r['id'].startswith('CHUNK::') for r in rows)
    assert any('12 MW at end.' in t for t in api.texts)
    assert receipt['graph_chunks']==1 and receipt['embedding_scope']=='readable_child_chunks'
    assert api.calls==2
    api.embedding_model='qwen3.7-text-embedding' if model=='text-embedding-v4' else 'text-embedding-v4'
    with pytest.raises(ValueError,match='query_embedding_model_mismatch'):
        rank(lib,'Capacity','2025-02-01',[],path=root,api=api)
    api.embedding_model=model
    assert rank(lib,'Capacity','2024-01-01',[],path=root,api=api)[0]==[]
    assert rank(lib,'Capacity','2025-02-01',[],path=root,document_id='absent',api=api)[0]==[]
    assert api.calls==2
    from retrieval import library_hybrid
    monkeypatch.setattr(library_hybrid,'QwenRetrieval',API)
    monkeypatch.setenv('QWEN_API_KEY','synthetic-test-credential')
    rank(lib,'Capacity','2025-02-01',[],path=root)
    assert API.constructed_models==[model,model]


def test_no_api_construction_when_index_missing(tmp_path,monkeypatch):
    from retrieval import library_hybrid
    class Library:
        has_retrieval_chunks=True
        manifest={'sha256':'unknown'}
    def forbidden(*args,**kwargs):raise AssertionError('must check index before provider')
    monkeypatch.setattr(library_hybrid,'QwenRetrieval',forbidden)
    with pytest.raises(RuntimeError,match='not_prepared'):
        rank(Library(),'query','2026-01-01',[],path=tmp_path)
