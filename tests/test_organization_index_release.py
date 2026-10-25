from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from retrieval.query_embeddings import QueryEmbeddingSource
from retrieval.qwen_api import RetrievalResponse
from sec_agent.research_foundation.organization_hybrid_retrieval import publish_prepared_index, OrganizationHybridRetrieval
from sec_agent.research_foundation.organization_index_release import load_release, verify_release_inputs
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from test_organization_hybrid_retrieval import setup
from test_organization_execution_access import runtime_at


MODEL = 'qwen3.7-text-embedding'


class Api:
    embedding_model = MODEL
    rerank_model = 'unused'

    def __init__(self):
        self.calls = 0
        self.before = lambda: None

    def embed(self, texts):
        self.calls += 1
        self.before()
        return RetrievalResponse([[1.] + [0.] * 1023], {'total_tokens': 10}, 'synthetic-receipt', MODEL)


def prepared(root, *, publish_lexical=True):
    reader, _, org, nodes = setup(root/'source')
    release = str(uuid4())
    publish_prepared_index(root/'indices', org, nodes, [[1.] + [0.] * 1023 for _ in nodes], {},
        model=MODEL, provenance={'kind':'synthetic embedding fixture'}, release_id=release,
        publish_lexical=publish_lexical)
    directory, _, _, contract = load_release(root/'indices', org, release)
    grant = deepcopy(reader.authority())
    manifest = json.loads(grant['manifest_text'])
    manifest['retrieval_index'] = contract
    grant['manifest_text'] = json.dumps(manifest, separators=(',', ':'))
    grant['manifest_digest'] = 'sha256:'+sha256(grant['manifest_text'].encode()).hexdigest()
    reader, state = runtime_at(SimpleNamespace(workspace=reader.workspace), grant)
    return reader, state, org, nodes, directory, contract


def test_new_query_durable_source_uses_frozen_release_after_new_publication(tmp_path):
    reader, state, org, nodes, directory, contract = prepared(tmp_path)
    api = Api()
    source = QueryEmbeddingSource(tmp_path/'query-cache', api, model=MODEL)
    ranker = OrganizationHybridRetrieval(reader, tmp_path/'indices', query_source=source)
    snapshot = reader.authority.manifest_digest[7:]
    ranked, first = ranker.rank(nodes, 'new semantic query', snapshot, [])
    assert ranked == nodes and first['provider_calls'] == 1
    assert first['index_digest'] == contract['index_digest']
    publish_prepared_index(tmp_path/'indices', org, nodes, [[0., 1.] + [0.]*1022 for _ in nodes], {},
        model=MODEL, provenance={'kind':'new publication'}, release_id=str(uuid4()))
    _, second = ranker.rank(nodes, 'new semantic query', snapshot, [])
    assert second['index_digest'] == first['index_digest'] and second['cache_hit']
    assert second['provider_calls'] == 0 and api.calls == 1
    state['status'] = 404
    with pytest.raises(OrganizationExecutionUnavailable):
        ranker.rank(nodes, 'new semantic query', snapshot, [])
    assert api.calls == 1


def test_missing_or_wrong_release_does_not_call_provider_or_follow_latest(tmp_path):
    reader, _, org, nodes, directory, contract = prepared(tmp_path)
    api = Api()
    ranker = OrganizationHybridRetrieval(reader, tmp_path/'indices',
        query_source=QueryEmbeddingSource(tmp_path/'cache', api, model=MODEL))
    (directory/'vectors.npy').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='integrity'):
        ranker.rank(nodes, 'new query', reader.authority.manifest_digest[7:], [])
    assert api.calls == 0
    with pytest.raises(ValueError):
        load_release(tmp_path/'indices', str(uuid4()), contract['release_id'], contract)


def test_revocation_while_embedding_discards_result_and_rank_cache(tmp_path):
    reader, state, _, nodes, directory, _ = prepared(tmp_path)
    api = Api()
    api.before = lambda: state.update(status=404)
    ranker = OrganizationHybridRetrieval(reader, tmp_path/'indices',
        query_source=QueryEmbeddingSource(tmp_path/'cache', api, model=MODEL))
    with pytest.raises(OrganizationExecutionUnavailable):
        ranker.rank(nodes, 'new query', reader.authority.manifest_digest[7:], [])
    assert api.calls == 1 and not (directory/'rank-cache.sqlite').exists()


def test_preparation_checks_full_projection_and_missing_host_configuration(tmp_path):
    reader, _, org, nodes, _, contract = prepared(tmp_path)
    before, manifest, _ = reader._grant()
    verify_release_inputs(reader.workspace, org, before['inputs'], contract,
        tmp_path/'indices', manifest['research_as_of'])
    with pytest.raises(ValueError, match='configured_storage'):
        OrganizationSourceNavigation(reader, workbench_url='http://localhost').navigate(
            {'source_space':'organization','operation':'search','query':'new query'})
    wrong = {**contract, 'index_digest':'0'*64}
    with pytest.raises(ValueError, match='frozen_version'):
        verify_release_inputs(reader.workspace, org, before['inputs'], wrong,
            tmp_path/'indices', manifest['research_as_of'])


def test_unconfigured_query_source_never_falls_back_to_lexical(tmp_path, monkeypatch):
    reader, _, _, nodes, _, _ = prepared(tmp_path)
    monkeypatch.delenv('FINSIGHT_ORGANIZATION_QUERY_EMBEDDING', raising=False)
    with pytest.raises(ValueError, match='not_configured'):
        OrganizationHybridRetrieval(reader, tmp_path/'indices').rank(
            nodes, 'a query absent from the release', reader.authority.manifest_digest[7:], nodes)


def test_frozen_validation_once_across_queries_instances_and_current_revocation(tmp_path, monkeypatch):
    import sec_agent.research_foundation.organization_vector_math as math
    reader, state, _, nodes, directory, _ = prepared(tmp_path)
    original=math.unit_vectors; validations=[]
    def counted(matrix, positions=None):
        validations.append(len(matrix))
        return original(matrix,positions)
    monkeypatch.setattr(math,'unit_vectors',counted)
    def unexpected(*args):
        raise AssertionError('frozen scoring must not renormalize the whole population')
    monkeypatch.setattr(math,'cosine_scores',unexpected)
    api=Api(); source=QueryEmbeddingSource(tmp_path/'cache',api,model=MODEL)
    for i in range(2):
        ranker=OrganizationHybridRetrieval(reader,tmp_path/'indices',query_source=source)
        for query in ('query one','query two','query one'):
            _, receipt=ranker.rank(nodes,query,reader.authority.manifest_digest[7:],[])
            assert receipt['vector_validation']=='immutable_release_receipt'
    assert validations==[len(nodes)] and api.calls==2
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):
        ranker.rank(nodes,'query one',reader.authority.manifest_digest[7:],[])
    assert validations==[len(nodes)]
    state['status']=200
    # Ordinary file mutation is still rejected even when rank/query receipts exist.
    with (directory/'vectors.npy').open('ab') as stream:stream.write(b'changed')
    with pytest.raises(ValueError,match='changed_after_load'):
        ranker.rank(nodes,'query one',reader.authority.manifest_digest[7:],[])
    assert api.calls==2


@pytest.mark.parametrize('bad',[0.,float('nan'),float('inf'),2.])
def test_matching_file_digest_cannot_certify_invalid_vector_values(tmp_path,bad):
    import numpy as np
    from sec_agent.research_foundation.organization_index_release import canonical_digest, ReleaseLoadCache
    _,_,org,_,directory,contract=prepared(tmp_path)
    values=np.load(directory/'vectors.npy',allow_pickle=False)
    values[-1,0]=bad
    np.save(directory/'vectors.npy',values,allow_pickle=False)
    index=json.loads((directory/'index.json').read_bytes())
    index['matrix_sha256']=sha256((directory/'vectors.npy').read_bytes()).hexdigest()
    (directory/'index.json').write_text(json.dumps(index),encoding='utf8')
    expected={**contract,'matrix_sha256':index['matrix_sha256'],'index_digest':canonical_digest(index)}
    with pytest.raises(ValueError,match='invalid_prepared_vectors'):
        load_release(tmp_path/'indices',org,contract['release_id'],expected,cache=ReleaseLoadCache())
