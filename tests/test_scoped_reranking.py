from hashlib import sha256
from types import SimpleNamespace

import pytest
from retrieval.qwen_api import RetrievalResponse
from retrieval.scoped_reranking import ScopedReranker


def fixture(tmp_path):
    calls=[]
    def provider(query,docs,**kw):
        calls.append((query,docs))
        return RetrievalResponse([{'index':1,'relevance_score':.9},{'index':0,'relevance_score':.1}],
                                 {'total_tokens':12},'test-request','qwen3-rerank')
    api=SimpleNamespace(rerank_model='qwen3-rerank',rerank=provider)
    rows=[{'node_id':str(i),'content':text,'content_sha256':sha256(text.encode()).hexdigest(),
           'embedding_context':'Acme FY2024 10-K'} for i,text in enumerate(['risk disclosure','sales USD 12'])]
    return ScopedReranker(tmp_path,api),rows,calls


def test_scope_restart_and_current_checks(tmp_path):
    source,rows,calls=fixture(tmp_path)
    checks=[]
    args=dict(scope='organization:A',index_digest='a'*64,check_access=lambda:checks.append(1))
    result,receipt=source.rank('sales',rows,**args)
    assert [r['node_id'] for r in result]==['1','0'] and receipt['provider_calls']==1
    assert len(checks)==3
    restarted=ScopedReranker(tmp_path,source.api)
    assert restarted.rank('sales',rows,**args)[1]['newly_reported_usage']=={}
    assert len(calls)==1
    restarted.rank('sales',rows,**{**args,'scope':'organization:B'})
    assert len(calls)==2
    def denied():raise PermissionError('revoked')
    with pytest.raises(PermissionError):
        restarted.rank('sales',rows,**{**args,'check_access':denied})
    assert len(calls)==2


def test_failed_unknown_request_never_resubmitted(tmp_path):
    source,rows,calls=fixture(tmp_path)
    def fail(*args,**kw):
        calls.append(1); raise TimeoutError('provider unknown')
    source.api.rerank=fail
    args=dict(scope='test',index_digest='a'*64,check_access=lambda:None)
    with pytest.raises(TimeoutError):source.rank('sales',rows,**args)
    with pytest.raises(RuntimeError,match='no_resubmission'):
        ScopedReranker(tmp_path,source.api).rank('sales',rows,**args)
    assert len(calls)==1


def test_mid_call_revocation_keeps_paid_receipt_but_returns_nothing(tmp_path):
    source,rows,calls=fixture(tmp_path)
    checks=[]
    def check():
        checks.append(1)
        if len(checks)==3:raise PermissionError('revoked during provider')
    args=dict(scope='test',index_digest='a'*64,check_access=check)
    with pytest.raises(PermissionError):source.rank('sales',rows,**args)
    assert source.rank('sales',rows,**{**args,'check_access':lambda:None})[1]['provider_calls']==0
    assert len(calls)==1


def test_instruction_identity_preserves_legacy_and_separates_variants(tmp_path):
    source,rows,calls=fixture(tmp_path)
    original=source.api.rerank;instructions=[]
    def provider(*args,**kwargs):
        instructions.append(kwargs.get('instruct'))
        return original(*args,**kwargs)
    source.api.rerank=provider
    args=dict(scope='test',index_digest='a'*64,check_access=lambda:None)
    legacy=source.rank('sales',rows,**args)[1]
    first=source.rank('sales',rows,**args,instruct='Rank answer evidence.')[1]
    other=source.rank('sales',rows,**args,instruct='Rank disclosure dates.')[1]
    assert len({r['request_key'] for r in (legacy,first,other)})==3
    assert source.rank('sales',rows,**args)[1]['provider_calls']==0
    assert source.rank('sales',rows,**args,instruct='Rank answer evidence.')[1]['provider_calls']==0
    assert instructions==[None,'Rank answer evidence.','Rank disclosure dates.']
    def denied():raise PermissionError('revoked')
    with pytest.raises(PermissionError):
        source.rank('sales',rows,**{**args,'check_access':denied},instruct='Rank answer evidence.')
    assert len(calls)==3


def test_instruction_failure_is_not_retried(tmp_path):
    source,rows,calls=fixture(tmp_path)
    def fail(*args,**kwargs):calls.append(kwargs);raise TimeoutError()
    source.api.rerank=fail
    args=dict(scope='test',index_digest='a'*64,check_access=lambda:None,instruct='Rank evidence.')
    with pytest.raises(TimeoutError):source.rank('sales',rows,**args)
    with pytest.raises(RuntimeError,match='no_resubmission'):source.rank('sales',rows,**args)
    assert len(calls)==1


def test_model_version_uses_independent_cache_identity(tmp_path):
    source,rows,calls=fixture(tmp_path)
    args=dict(scope='test',index_digest='a'*64,check_access=lambda:None)
    old=source.rank('sales',rows,**args)[1]
    source.api.rerank_model='qwen3.7-text-rerank'
    def provider(*a,**kw):
        calls.append(1)
        return RetrievalResponse([{'index':0,'relevance_score':.9},{'index':1,'relevance_score':.1}],
            {'total_tokens':12},'new-model-test','qwen3.7-text-rerank')
    source.api.rerank=provider
    ranked,new=source.rank('sales',rows,**args)
    assert old['request_key']!=new['request_key'] and new['provider_calls']==1
    assert [r['node_id'] for r in ranked]==['0','1']
    assert source.rank('sales',rows,**args)[1]['provider_calls']==0
    assert len(calls)==2


@pytest.mark.parametrize('fault',['digest','duplicate','oversized','invalid_response'])
def test_malformed_input_and_response_cannot_be_silently_ranked(tmp_path,fault):
    source,rows,calls=fixture(tmp_path)
    if fault=='digest':rows[0]['content']='changed'
    if fault=='duplicate':rows[1]=rows[0]
    if fault=='oversized':rows[0]['embedding_context']='x'*32769
    if fault=='invalid_response':
        source.api.rerank=lambda *a,**k:RetrievalResponse([{'index':0,'relevance_score':.3}]*2,{},None,'qwen3-rerank')
    with pytest.raises(ValueError):
        source.rank('sales',rows,scope='test',index_digest='a'*64,check_access=lambda:None)
