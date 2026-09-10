from dataclasses import dataclass
from sec_agent.agent_runtime.working_memory import WorkingMemory
from sec_agent.agent_runtime.working_memory_search import WorkingPaperSearch, search_working_papers
from retrieval.qwen_api import RetrievalResponse


class API:
    embedding_model='test'; rerank_model='test'
    def __init__(self): self.inputs=[]
    def embed(self,texts):
        self.inputs.extend(texts)
        return RetrievalResponse([[1.,0.,0.] if 'cash' in t.lower() else [0.,1.,0.] for t in texts],{'total_tokens':len(texts)},'test','test')
    def rerank(self,q,docs):
        return RetrievalResponse([{'index':i,'relevance_score':1.0} for i in range(len(docs))],{'total_tokens':len(docs)},'test','test')


def test_semantic_scope_current_versions_cache_and_restart(tmp_path):
    a=WorkingMemory(tmp_path/'db',owner='a',workspace='t',actor='one')
    b=WorkingMemory(tmp_path/'db',owner='b',workspace='t',actor='one')
    note=a.save('Cash paper','Cash realization needs source confirmation.')
    b.save('Private cash','Never send this private text.')
    api=API()
    first=WorkingPaperSearch(a,api).search('money collection')
    assert first['items'][0]['id']==note['note_id']
    assert not any('private' in t for t in api.inputs)
    second=WorkingPaperSearch(a,api).search('money collection')
    assert second['remote_calls']==0
    a.save('Cash paper','Cash explanation removed by user.',base_version=1)
    third=WorkingPaperSearch(a,api).search('money collection')
    assert all(r['version']==2 for r in third['items'])
    assert 'removed' in third['items'][0]['preview']
    assert a.read(note['note_id'],version=1)['found']


def test_semantic_failure_leaves_literal_and_exact_read(tmp_path,monkeypatch):
    a=WorkingMemory(tmp_path/'db',owner='a',workspace='t',actor='one')
    note=a.save('cash','cash retained')
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_SEMANTIC','1')
    monkeypatch.delenv('QWEN_API_KEY',raising=False)
    result=search_working_papers(a,'cash')
    assert result['semantic_available'] is False and result['items']
    assert a.read(note['note_id'])['body']=='cash retained'


def test_failed_remote_call_cooldown_no_repeated_charge(tmp_path):
    a=WorkingMemory(tmp_path/'db',owner='a',workspace='t',actor='one');a.save('cash','cash retained')
    class Broken(API):
        def embed(self,texts):
            self.inputs.extend(texts);raise TimeoutError()
    import pytest
    api=Broken()
    with pytest.raises(TimeoutError): WorkingPaperSearch(a,api).search('cash')
    with pytest.raises(RuntimeError,match='cooldown'): WorkingPaperSearch(a,api).search('cash')
    assert len(api.inputs)==1
    with a.connection() as db:
        assert db.execute('SELECT status FROM working_retrieval_calls').fetchone()[0]=='failed_usage_unknown'
