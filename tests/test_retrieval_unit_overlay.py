import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
import pytest
from test_semantic_units import row
from retrieval.semantic_unit_catalog import build as plan
from scripts.engineering.build_retrieval_unit_overlay import build
from scripts.engineering.prepare_retrieval_unit_vectors import prepare,execute
from retrieval.qwen_api import RetrievalResponse


def test_overlay_publishes_exact_scope_from_receipts_without_new_provider_calls(tmp_path,monkeypatch):
    from sec_agent.research_foundation.organization_candidate_index import build as navigation,encoded
    from sec_agent.research_foundation.organization_index_release import canonical_digest
    import retrieval.qwen_api as provider
    import psutil,shutil
    source=row('A\n[TABLE:1]\nCash | 10\n[/TABLE]\nB')
    directory=tmp_path/'release';directory.mkdir()
    navigation(directory/'navigation.sqlite',[source])
    np.save(directory/'vectors.npy',np.array([[1.]+[0.]*1023],dtype=np.float32))
    index={'model':'qwen3.7-text-embedding',
        'matrix_sha256':sha256((directory/'vectors.npy').read_bytes()).hexdigest(),
        'navigation_index':{'sha256':sha256((directory/'navigation.sqlite').read_bytes()).hexdigest()},
        'records':[{'node_id':source['node_id'],'document_id':source['parent_document_id'],
                    'content_sha256':source['content_sha256'],'embedding_input_sha256':source['embedding_input_sha256'],
                    'vector_index':0,'navigation_sha256':sha256(encoded(source)).hexdigest()}]}
    index_path=directory/'index.json';index_path.write_text(json.dumps(index),encoding='utf8')
    catalog=tmp_path/'catalog.sqlite';plan(catalog,[(source,0)])
    scope=tmp_path/'scope.json';scope.write_text(json.dumps({'parent_node_ids':[source['node_id']],
        'snapshot_digest':canonical_digest(index)}),encoding='utf8')
    api=SimpleNamespace(embedding_model='qwen3.7-text-embedding',close=lambda:None,
        embed=Mock(side_effect=lambda texts,dimensions:RetrievalResponse(
            [[1.]+[0.]*1023 for _ in texts],{'total_tokens':12},'request','qwen3.7-text-embedding')))
    monkeypatch.setattr(provider,'QwenRetrieval',lambda *a,**k:api)
    monkeypatch.setenv('QWEN_API_KEY','fixture-no-transport')
    monkeypatch.setattr(psutil,'virtual_memory',lambda:SimpleNamespace(available=3*2**30))
    monkeypatch.setattr(shutil,'disk_usage',lambda *_:SimpleNamespace(free=3*2**30))
    receipts=tmp_path/'receipts';prepare(catalog,scope,receipts);execute(receipts)
    result=build(index_path,catalog,scope,[receipts],tmp_path/'overlay')
    assert result['provider_calls']==0 and api.embed.call_count==1
    assert result['descriptor']['units']==3
    assert result['index_file_sha256']==sha256(index_path.read_bytes()).hexdigest()
    with (directory/'vectors.npy').open('ab') as stream:stream.write(b'changed')
    with pytest.raises(ValueError,match='original_file_changed'):
        build(index_path,catalog,scope,[receipts],tmp_path/'bad')
