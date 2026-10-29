import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from retrieval.semantic_unit_catalog import build
from retrieval.qwen_api import RetrievalResponse
from test_semantic_units import row
from scripts.engineering.prepare_retrieval_unit_vectors import prepare,execute


def test_frozen_plan_executes_only_own_exact_inputs_and_resumes_completed_receipts(tmp_path,monkeypatch):
    import retrieval.qwen_api as provider
    import psutil,shutil
    source=row('A\n[TABLE:1]\nCash | 10\n[/TABLE]\nB')
    catalog=tmp_path/'units.sqlite';build(catalog,[(source,0)])
    scope=tmp_path/'scope.json'
    scope.write_text(json.dumps({'parent_node_ids':['parent'],'snapshot_digest':'a'*64}),encoding='utf8')
    output=tmp_path/'job';plan=prepare(catalog,scope,output)
    assert plan['TokenBudgetBasis']['input_scale']['unique_new_vectors']==3
    api=SimpleNamespace(embedding_model='qwen3.7-text-embedding',close=lambda:None,
        embed=Mock(side_effect=lambda texts,dimensions:RetrievalResponse(
            [[1.]+[0.]*1023 for _ in texts],{'total_tokens':12},'request','qwen3.7-text-embedding')))
    monkeypatch.setattr(provider,'QwenRetrieval',lambda *args,**kwargs:api)
    monkeypatch.setenv('QWEN_API_KEY','fixture-no-transport')
    monkeypatch.setattr(psutil,'virtual_memory',lambda:SimpleNamespace(available=3*2**30))
    monkeypatch.setattr(shutil,'disk_usage',lambda *_:SimpleNamespace(free=3*2**30))
    execute(output);execute(output)
    assert api.embed.call_count==1
    assert json.loads((output/'result.json').read_text())['provider_calls']==0
    from retrieval.unit_embedding_receipts import UnitEmbeddingReceiptReader
    from retrieval.semantic_unit_catalog import iter_units
    reader=UnitEmbeddingReceiptReader([output])
    try:
        for _,unit,_ in iter_units(catalog,require_new_vector=True):
            result=reader(unit)
            assert result['input_sha256']==unit['embedding_input_sha256']
            assert result['vector'][0]==1 and result['provider_calls']==0
        assert reader.completed_batches==1 and reader.incomplete_batches==0
    finally:reader.close()
    assert api.embed.call_count==1


def test_unsubmitted_reuse_never_accepts_failed_or_pending_receipts(tmp_path):
    from retrieval.unit_embedding_receipts import UnitEmbeddingReceiptReader
    from sec_agent.adapters.local_records import LocalRecords
    source=row('A\n[TABLE:1]\nCash | 10\n[/TABLE]\nB')
    catalog=tmp_path/'units.sqlite';build(catalog,[(source,0)])
    scope=tmp_path/'scope.json'
    scope.write_text(json.dumps({'parent_node_ids':['parent'],'snapshot_digest':'a'*64}),encoding='utf8')
    output=tmp_path/'job';prepare(catalog,scope,output)
    with LocalRecords(output/'receipts'):pass
    reader=UnitEmbeddingReceiptReader([output],allow_unsubmitted=True)
    assert reader.completed_batches==0 and reader.incomplete_batches==1
    reader.close()
    job=json.loads((output/'jobs.jsonl').read_text().splitlines()[0])
    from hashlib import sha256
    key=sha256(json.dumps(['unit-embedding-batch.v1','a'*64,'qwen3.7-text-embedding',1024,
        [u['input_sha256'] for u in job['units']]],separators=(',',':')).encode()).hexdigest()
    for status in ('started','failed_usage_unknown'):
        with LocalRecords(output/'receipts') as records:records[key]={'status':status}
        with pytest.raises(ValueError,match='incomplete'):
            UnitEmbeddingReceiptReader([output],allow_unsubmitted=True)


def test_failed_provider_attempt_is_counted_without_inventing_usage(tmp_path,monkeypatch):
    import retrieval.qwen_api as provider
    import psutil,shutil
    catalog=tmp_path/'units.sqlite';build(catalog,[(row('A\n[TABLE:1]\nCash | 10\n[/TABLE]\nB'),0)])
    scope=tmp_path/'scope.json';scope.write_text(json.dumps({'parent_node_ids':['parent'],'snapshot_digest':'a'*64}))
    output=tmp_path/'job';prepare(catalog,scope,output)
    api=SimpleNamespace(embedding_model='qwen3.7-text-embedding',close=lambda:None,embed=Mock(side_effect=TimeoutError('unknown')))
    monkeypatch.setattr(provider,'QwenRetrieval',lambda *args,**kwargs:api)
    monkeypatch.setenv('QWEN_API_KEY','fixture-no-transport')
    monkeypatch.setattr(psutil,'virtual_memory',lambda:SimpleNamespace(available=3*2**30))
    monkeypatch.setattr(shutil,'disk_usage',lambda *_:SimpleNamespace(free=3*2**30))
    with pytest.raises(TimeoutError):execute(output)
    result=json.loads((output/'result.json').read_text())
    assert result['provider_attempts']==result['failed_attempts_usage_unknown']==1
    assert result['provider_calls']==0 and result['reported_new_tokens']==0
    with pytest.raises(RuntimeError,match='no_resubmission'):execute(output)
    assert api.embed.call_count==1
