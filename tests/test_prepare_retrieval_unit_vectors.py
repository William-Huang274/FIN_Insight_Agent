import json
from types import SimpleNamespace
from unittest.mock import Mock
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
