import json
from hashlib import sha256
from types import SimpleNamespace
import pytest
from retrieval.semantic_unit_catalog import build
from retrieval.unit_embedding_preparation import UnitEmbeddingPreparation
from retrieval.qwen_api import RetrievalResponse
from scripts.engineering.prepare_retrieval_unit_vectors import prepare
from test_semantic_units import row


def previous(folder,text,failed=False):
    folder.mkdir()
    def embed(texts,dimensions):
        if failed:raise TimeoutError('unknown_usage')
        return RetrievalResponse([[1.]+[0.]*1023],{'total_tokens':4},'receipt','qwen3.7-text-embedding')
    client=UnitEmbeddingPreparation(folder/'receipts',SimpleNamespace(embedding_model='qwen3.7-text-embedding',embed=embed),
                                   snapshot='a'*64,budget={'purpose':'synthetic'})
    if failed:
        with pytest.raises(TimeoutError):client.embed([text])
    else:client.embed([text])
    jobs=(json.dumps({'number':0,'units':[{'id':'old-unit','input_sha256':sha256(text.encode()).hexdigest()}]})+'\n').encode()
    (folder/'jobs.jsonl').write_bytes(jobs)
    (folder/'plan.json').write_text(json.dumps({'snapshot_digest':'a'*64,'jobs_sha256':sha256(jobs).hexdigest()}))


def setup(tmp_path):
    a=row('Already embedded');b=row('New original passage');b['node_id']='second'
    # Force explicit receipts rather than parent-vector reuse in this fixture.
    a['embedding_input_sha256']=b['embedding_input_sha256']='f'*64
    catalog=tmp_path/'units.sqlite';build(catalog,[(a,0),(b,1)])
    scope=tmp_path/'scope.json';scope.write_text(json.dumps({'snapshot_digest':'a'*64,'parent_node_ids':['parent','second']}))
    return catalog,scope


def test_repacking_skips_completed_exact_inputs_without_provider_or_receipt_mutation(tmp_path):
    catalog,scope=setup(tmp_path);old=tmp_path/'old';previous(old,'original context\nAlready embedded')
    before=(old/'receipts/records-v1.sqlite').read_bytes()
    result=prepare(catalog,scope,tmp_path/'new',[old])
    assert result['TokenBudgetBasis']['input_scale']['reused_completed_inputs']==1
    assert result['TokenBudgetBasis']['input_scale']['unique_new_vectors']==1
    jobs=[json.loads(s) for s in (tmp_path/'new/jobs.jsonl').read_text().splitlines()]
    assert len(jobs)==1 and len(jobs[0]['units'])==1
    assert jobs[0]['units'][0]['input_sha256']==sha256(b'original context\nNew original passage').hexdigest()
    assert before==(old/'receipts/records-v1.sqlite').read_bytes()


def test_unknown_previous_request_cannot_be_repacked_and_resubmitted(tmp_path):
    catalog,scope=setup(tmp_path);old=tmp_path/'old';previous(old,'original context\nAlready embedded',True)
    with pytest.raises(ValueError,match='incomplete_no_provider_fallback'):
        prepare(catalog,scope,tmp_path/'new',[old])
    assert not (tmp_path/'new/jobs.jsonl').exists()
