from dataclasses import dataclass
import json
import sqlite3
import numpy as np
import pytest

from retrieval import library_vectors as vectors
from retrieval.qwen_api import RetrievalResponse


class Library:
    manifest={'sha256':'snapshot'}
    def _query(self,query):
        return [{'id':'one','source_id':'A','text':'Cash income'},
                {'id':'two','source_id':'B','text':'Cash income'},
                {'id':'three','source_id':'C','text':'Chip supply'}]


class API:
    calls=0
    def __init__(self,*args,**kwargs):pass
    def close(self):pass
    def embed(self,texts,dimensions):
        type(self).calls+=1
        result=[]
        for text in texts:
            v=[0.]*dimensions;v[0 if 'Cash' in text else 1]=1.;result.append(v)
        return RetrievalResponse(result,{'total_tokens':len(texts)*3},'test-request',vectors.MODEL)


def test_persisted_vectors_dedup_scope_and_version(tmp_path,monkeypatch):
    monkeypatch.setattr(vectors,'QwenRetrieval',API);API.calls=0
    root=tmp_path/'cache';audit=tmp_path/'audit'
    result=vectors.prepare(Library(),root,'unused',audit,execute=True)
    assert result['unique_vectors']==2 and result['chunks']==3 and API.calls==1
    q=[1.]+[0.]*1023
    assert vectors.dense_search(root,'snapshot',q,{'A'})==['one']
    assert vectors.dense_search(root,'snapshot',q,{'B'})==['two']
    with pytest.raises(ValueError,match='version_mismatch'):vectors.dense_search(root,'other',q,{'A'})
    vectors.prepare(Library(),root,'unused',audit,execute=True)
    assert API.calls==1
    assert vectors.plan(Library(),root)[2]['input_scale']['missing_vectors']==0


def test_failed_embeddings_not_retried(tmp_path,monkeypatch):
    class Fail(API):
        calls=0
        def embed(self,*args,**kwargs):type(self).calls+=1;raise TimeoutError('not persisted')
    monkeypatch.setattr(vectors,'QwenRetrieval',Fail)
    with pytest.raises(RuntimeError,match='usage_retained'):vectors.prepare(Library(),tmp_path/'c','unused',tmp_path/'a',execute=True)
    with pytest.raises(RuntimeError,match='require_review'):vectors.prepare(Library(),tmp_path/'c','unused',tmp_path/'a',execute=True)
    assert Fail.calls==1
    with sqlite3.connect(tmp_path/'c/chunk-embeddings.sqlite') as db:
        assert db.execute('select status from requests').fetchone()[0]=='failed_usage_unknown'


def test_ready_check_rejects_unprepared_index_without_api(tmp_path):
    with pytest.raises(RuntimeError,match='not_prepared'):vectors.ready_index(tmp_path,'snapshot')


def test_unsubmitted_work_continues_without_retrying_unknown_usage(tmp_path,monkeypatch):
    root=tmp_path/'cache';API.calls=0
    monkeypatch.setattr(vectors,'QwenRetrieval',API)
    with vectors.open_cache(root) as db:
        db.execute('INSERT INTO requests VALUES(?,?,?)',('failed','failed_usage_unknown','{}'))
        db.execute('INSERT INTO request_items VALUES(?,?)',('failed',vectors.vector_key('Cash income')))
    result=vectors.prepare(Library(),root,'unused',tmp_path/'audit',execute=True,skip_blocked=True)
    assert result['withheld_keys']==1 and not result['published_index'] and API.calls==1
    assert not (root/'chunk-vector-manifest.json').exists()
    with sqlite3.connect(root/'chunk-embeddings.sqlite') as db:
        assert db.execute('SELECT count(*) FROM vectors').fetchone()[0]==1
        assert db.execute('SELECT status FROM requests WHERE id="failed"').fetchone()[0]=='failed_usage_unknown'
    vectors.prepare(Library(),root,'unused',tmp_path/'retry-audit',execute=True,retry_request_ids=['failed'])
    assert API.calls==2 and vectors.ready_index(root,'snapshot')[0]['chunks']==3
    with sqlite3.connect(root/'chunk-embeddings.sqlite') as db:
        assert db.execute('SELECT status FROM requests WHERE id="failed"').fetchone()[0]=='failed_usage_unknown'
