from hashlib import sha256
from types import SimpleNamespace
import pytest
from retrieval.unit_embedding_preparation import UnitEmbeddingPreparation
from retrieval.qwen_api import RetrievalResponse


def test_completed_batch_reuses_exact_input_receipt_without_provider(tmp_path):
    calls=[]
    def embed(texts,dimensions):
        calls.append(texts)
        return RetrievalResponse([[1.]+[0.]*1023 for _ in texts],{'total_tokens':8},'request','qwen3.7-text-embedding')
    api=SimpleNamespace(embedding_model='qwen3.7-text-embedding',embed=embed)
    client=UnitEmbeddingPreparation(tmp_path,api,snapshot='a'*64,budget={'purpose':'fixture'})
    values,first=client.embed(['body','another'])
    again,second=client.embed(['body','another'])
    assert values.shape==(2,1024) and (again==values).all()
    assert first['provider_calls']==1 and second['provider_calls']==0 and len(calls)==1
    assert second['input_sha256'][0]==sha256(b'body').hexdigest()


def test_failed_paid_batch_stays_blocked_after_restart(tmp_path):
    calls=[]
    def failed(*args,**kwargs):calls.append(1);raise TimeoutError('unknown')
    api=SimpleNamespace(embedding_model='qwen3.7-text-embedding',embed=failed)
    client=UnitEmbeddingPreparation(tmp_path,api,snapshot='a'*64,budget={'purpose':'fixture'})
    with pytest.raises(TimeoutError):client.embed(['body'])
    restarted=UnitEmbeddingPreparation(tmp_path,api,snapshot='a'*64,budget={'purpose':'fixture'})
    with pytest.raises(RuntimeError,match='no_resubmission'):restarted.embed(['body'])
    assert len(calls)==1


def test_batch_budget_is_checked_before_any_transport(tmp_path):
    api=SimpleNamespace(embedding_model='qwen3.7-text-embedding')
    client=UnitEmbeddingPreparation(tmp_path,api,snapshot='a'*64,budget={'purpose':'fixture'})
    for texts in ([],['x']*21,['x'*16385]):
        with pytest.raises(ValueError,match='limits'):client.embed(texts)
