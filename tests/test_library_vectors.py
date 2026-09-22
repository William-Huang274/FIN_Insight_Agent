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


def test_old_retry_approval_cannot_replay_a_new_failed_attempt(tmp_path,monkeypatch):
    class Fail(API):
        calls=0
        def embed(self,*args,**kwargs):type(self).calls+=1;raise TimeoutError()
    root=tmp_path/'cache'
    monkeypatch.setattr(vectors,'QwenRetrieval',Fail)
    with vectors.open_cache(root) as db:
        db.execute('INSERT INTO requests VALUES(?,?,?)',('original','failed_usage_unknown','{}'))
        db.execute('INSERT INTO request_items VALUES(?,?)',('original',vectors.vector_key('Cash income')))
    with pytest.raises(RuntimeError,match='usage_retained'):
        vectors.prepare(Library(),root,'unused',tmp_path/'a',execute=True,retry_request_ids=['original'])
    with pytest.raises(RuntimeError,match='require_review'):
        vectors.prepare(Library(),root,'unused',tmp_path/'b',execute=True,retry_request_ids=['original'])
    assert Fail.calls==1


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


def test_model_migration_never_reuses_other_model_vectors(tmp_path,monkeypatch):
    class NewAPI(API):
        def __init__(self,*args,embedding_model,**kwargs):self.model=embedding_model
        def embed(self,texts,dimensions):
            r=super().embed(texts,dimensions)
            return RetrievalResponse(r.values,r.usage,r.request_id,self.model)
    monkeypatch.setattr(vectors,'QwenRetrieval',NewAPI)
    root=tmp_path/'old';new=tmp_path/'new';model='qwen3.7-text-embedding'
    vectors.prepare(Library(),root,'unused',tmp_path/'a',execute=True)
    assert vectors.plan(Library(),root,model=model)[2]['input_scale']['missing_vectors']==2
    with pytest.raises(ValueError,match='model_mismatch'):
        vectors.prepare(Library(),root,'unused',tmp_path/'b',execute=True,model=model)
    result=vectors.prepare(Library(),new,'unused',tmp_path/'c',execute=True,model=model)
    assert result['embedding_model']==model and vectors.ready_index(new,'snapshot')[0]==result
    assert vectors.vector_key('Cash income')!=vectors.vector_key('Cash income',model)


def test_stop_file_drains_inflight_and_retains_completed_cache(tmp_path,monkeypatch):
    stop=tmp_path/'stop';root=tmp_path/'cache'
    class Many(Library):
        def _query(self,q):return [dict(id=str(i),source_id='A',text='Cash '+str(i)) for i in range(50)]
    class Pause(API):
        def embed(self,texts,dimensions):
            stop.touch()
            return super().embed(texts,dimensions)
    monkeypatch.setattr(vectors,'QwenRetrieval',Pause)
    result=vectors.prepare(Many(),root,'unused',tmp_path/'audit',execute=True,stop_file=stop)
    assert result['status']=='paused_after_inflight_drained'
    assert not (root/'chunk-vector-manifest.json').exists()
    with vectors.open_cache(root) as db:
        assert db.execute("select count(*) from requests where status!='completed'").fetchone()[0]==0
        assert 0<db.execute('select count(*) from vectors').fetchone()[0]<50


def test_token_pacer_smooths_volume_and_accounts_actual_usage(monkeypatch):
    now=[0.]
    monkeypatch.setattr(vectors.time,'monotonic',lambda:now[0])
    monkeypatch.setattr(vectors.time,'sleep',lambda duration:now.__setitem__(0,now[0]+duration))
    pacer=vectors.EmbeddingPacer(tokens_per_minute=100,minimum_interval=0)
    assert pacer.reserve('a',['x'*100])
    pacer.observe('a',80)
    assert pacer.ratio==pytest.approx(.96)
    assert pacer.reserve('b',['y'*50])
    assert now[0]>=60  # Actual80 + next48 exceeds the rolling100-token ceiling.
