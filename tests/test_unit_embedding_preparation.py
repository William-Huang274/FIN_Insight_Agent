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


def test_authorized_retry_preserves_unknown_attempt_and_cannot_be_replayed(tmp_path):
    from sec_agent.adapters.local_records import LocalRecords
    from retrieval.unit_embedding_preparation import receipt_digest
    calls=[]
    def embed(texts,dimensions):
        calls.append(texts)
        if len(calls)==1:raise TimeoutError('usage unknown')
        return RetrievalResponse([[1.]+[0.]*1023],{'total_tokens':3},'recovered','qwen3.7-text-embedding')
    api=SimpleNamespace(embedding_model='qwen3.7-text-embedding',embed=embed)
    client=UnitEmbeddingPreparation(tmp_path,api,snapshot='a'*64,budget={'purpose':'fixture'})
    with pytest.raises(TimeoutError):client.embed(['body'])
    with LocalRecords(tmp_path) as records:failed=records[client.key(['body'])]
    auth={'id':'human-confirmed-1','reason':'Billing restored; retry this failed request once',
          'failed_receipt_sha256':receipt_digest(failed)}
    with pytest.raises(RuntimeError,match='exact_failed'):client.embed(['body'],retry_authorization={**auth,'failed_receipt_sha256':'0'*64})
    _,receipt=client.embed(['body'],retry_authorization=auth)
    assert receipt['request_id']=='recovered' and len(calls)==2
    with LocalRecords(tmp_path) as records:
        saved=records[client.key(['body'])]
        assert saved['previous_attempts']==[failed]
        assert saved['previous_attempts'][0]['provider_receipt']['usage']=='unknown'
        assert saved['retry_authorization']==auth
    with pytest.raises(RuntimeError,match='exact_failed'):client.embed(['body'],retry_authorization=auth)
    client.embed(['body'])
    assert len(calls)==2


def test_second_failure_requires_new_authorization_and_exact_new_receipt(tmp_path):
    from sec_agent.adapters.local_records import LocalRecords
    from retrieval.unit_embedding_preparation import receipt_digest
    calls=[]
    def failed(*args,**kwargs):calls.append(1);raise TimeoutError('unknown')
    api=SimpleNamespace(embedding_model='qwen3.7-text-embedding',embed=failed)
    client=UnitEmbeddingPreparation(tmp_path,api,snapshot='a'*64,budget={'purpose':'fixture'})
    with pytest.raises(TimeoutError):client.embed(['body'])
    with LocalRecords(tmp_path) as records:first=records[client.key(['body'])]
    auth={'id':'approval-1','reason':'explicit retry','failed_receipt_sha256':receipt_digest(first)}
    with pytest.raises(TimeoutError):client.embed(['body'],retry_authorization=auth)
    with LocalRecords(tmp_path) as records:second=records[client.key(['body'])]
    assert second['previous_attempts']==[first]
    with pytest.raises(RuntimeError,match='exact_failed'):client.embed(['body'],retry_authorization=auth)
    with pytest.raises(RuntimeError,match='already_used'):
        client.embed(['body'],retry_authorization={**auth,'failed_receipt_sha256':receipt_digest(second)})
    with pytest.raises(RuntimeError,match='no_resubmission'):client.embed(['body'])
    assert len(calls)==2


def test_pending_call_cannot_be_retried_even_with_authorization(tmp_path):
    from sec_agent.adapters.local_records import LocalRecords
    from retrieval.unit_embedding_preparation import receipt_digest
    api=SimpleNamespace(embedding_model='qwen3.7-text-embedding')
    client=UnitEmbeddingPreparation(tmp_path,api,snapshot='a'*64,budget={'purpose':'fixture'})
    saved={'status':'started','TokenBudgetBasis':{'purpose':'fixture'}}
    with LocalRecords(tmp_path) as records:records[client.key(['body'])]=saved
    with pytest.raises(RuntimeError,match='exact_failed'):
        client.embed(['body'],retry_authorization={'id':'approval','reason':'retry','failed_receipt_sha256':receipt_digest(saved)})


def test_receipt_compare_and_set_does_not_overwrite_concurrent_change(tmp_path):
    from sec_agent.adapters.local_records import LocalRecords
    with LocalRecords(tmp_path) as first,LocalRecords(tmp_path) as second:
        first['key']={'status':'failed'}
        assert second.compare_and_set('key',{'status':'failed'},{'status':'started'})
        assert not first.compare_and_set('key',{'status':'failed'},{'status':'different_started'})
        assert first['key']=={'status':'started'}
