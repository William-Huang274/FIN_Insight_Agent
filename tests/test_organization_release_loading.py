import json

import pytest

from sec_agent.research_foundation import organization_index_release as releases
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from test_organization_index_release import prepared
from test_organization_search_cache import setup


def test_only_first_load_hashes_entire_release_and_expected_contract_never_changes(tmp_path, monkeypatch):
    _, _, org, _, _, contract = prepared(tmp_path)
    calls = []
    original = releases._load_release
    def counted(*args):
        calls.append(True)
        return original(*args)
    monkeypatch.setattr(releases, '_load_release', counted)
    cache = releases.ReleaseLoadCache()
    for _ in range(3):
        releases.load_release(tmp_path/'indices', org, contract['release_id'], contract, cache=cache)
        cache.check()
    assert len(calls) == 1
    with pytest.raises(ValueError, match='frozen_version'):
        releases.load_release(tmp_path/'indices', org, contract['release_id'],
                              {**contract, 'index_digest':'0'*64}, cache=cache)
    assert len(calls) == 2


@pytest.mark.parametrize('name', ['vectors.npy', 'index.json', 'lexical.sqlite'])
def test_changed_or_removed_artifact_invalidates_loaded_release(tmp_path, name):
    _, _, org, _, directory, contract = prepared(tmp_path)
    cache = releases.ReleaseLoadCache()
    releases.load_release(tmp_path/'indices', org, contract['release_id'], contract, cache=cache)
    path = directory/name
    with path.open('r+b') as stream:
        stream.seek(-1, 2)
        old = stream.read(1)
        stream.seek(-1, 2)
        stream.write(bytes([old[0] ^ 1]))
    with pytest.raises(ValueError, match='changed_after_load'):
        releases.load_release(tmp_path/'indices', org, contract['release_id'], contract, cache=cache)
    with pytest.raises(ValueError):
        releases.load_release(tmp_path/'indices', org, contract['release_id'], contract, cache=cache)


def test_warm_load_checks_revocation_and_lexical_integrity_before_provider(tmp_path, monkeypatch):
    nav, _, state, directory, request, _, _, api = setup(tmp_path, monkeypatch)
    assert json.loads((directory/'index.json').read_text(encoding='utf8'))['lexical_index']
    calls = api.calls
    state['status'] = 404
    with pytest.raises(OrganizationExecutionUnavailable):
        nav.navigate({**request, 'query':'never authorize from loaded release'})
    assert api.calls == calls


def test_new_query_uses_published_postings_without_query_time_preparation(tmp_path, monkeypatch):
    reader, _, _, _, _, _ = prepared(tmp_path)
    from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
    from retrieval.query_embeddings import QueryEmbeddingSource
    from test_organization_index_release import Api, MODEL
    nav = OrganizationSourceNavigation(reader, workbench_url='http://localhost', retrieval_root=tmp_path/'indices')
    nav.hybrid.query_source = QueryEmbeddingSource(tmp_path/'query-cache', Api(), model=MODEL)
    def unexpected(*args, **kwargs):
        raise AssertionError('queries cannot build/tokenize BM25 or populate duplicate term caches')
    monkeypatch.setattr('sec_agent.research_foundation.organization_projection_cache.pack_terms', unexpected)
    monkeypatch.setattr('retrieval.query_bm25.LexicalStatisticsCache.scores', unexpected)
    monkeypatch.setattr('retrieval.text.tokenize', unexpected)
    for question in ('revenue', 'new revenue question'):
        result = nav.navigate({'source_space':'organization', 'operation':'search', 'query':question})
        assert result.items[0]['retrieval']['lexical_source'] == 'published_release'


def test_mutation_during_initial_hash_and_sidecar_are_rejected(tmp_path, monkeypatch):
    _, _, org, _, directory, contract = prepared(tmp_path)
    original = releases._load_release
    def race(*args):
        result = original(*args)
        (directory/'index.json').write_bytes(b'changed during load')
        return result
    monkeypatch.setattr(releases, '_load_release', race)
    cache = releases.ReleaseLoadCache()
    with pytest.raises(ValueError, match='changed_during_load'):
        releases.load_release(tmp_path/'indices', org, contract['release_id'], contract, cache=cache)
    with pytest.raises(ValueError, match='not_loaded'):
        cache.check()
    (directory/'lexical.sqlite-wal').write_bytes(b'')
    with pytest.raises(ValueError, match='unsealed'):
        releases.load_release(tmp_path/'indices', org, contract['release_id'], contract, cache=cache)


def test_registration_load_rejects_unsealed_lexical_database(tmp_path):
    _, _, org, _, directory, contract = prepared(tmp_path)
    (directory/'lexical.sqlite-wal').write_bytes(b'')
    with pytest.raises(ValueError, match='unsealed'):
        releases.load_release(tmp_path/'indices', org, contract['release_id'], contract)


def test_concurrent_first_load_validates_once_and_new_loader_revalidates(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    _, _, org, _, _, contract = prepared(tmp_path)
    calls = []
    original = releases._load_release
    def counted(*args):
        calls.append(True)
        return original(*args)
    monkeypatch.setattr(releases, '_load_release', counted)
    cache = releases.ReleaseLoadCache()
    def load(_):
        return releases.load_release(tmp_path/'indices', org, contract['release_id'], contract, cache=cache)[3]
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(load, range(8))) == [contract] * 8
    assert len(calls) == 1
    releases.load_release(tmp_path/'indices', org, contract['release_id'], contract,
                          cache=releases.ReleaseLoadCache())
    assert len(calls) == 2


def test_explicit_warmup_checks_rights_without_query_or_original_reads(tmp_path, monkeypatch):
    reader, state, _, _, _, contract = prepared(tmp_path)
    from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
    nav = OrganizationSourceNavigation(reader, workbench_url='http://localhost', retrieval_root=tmp_path/'indices')
    def unexpected(*args):
        raise AssertionError('index warmup cannot read originals or request embeddings')
    monkeypatch.setattr(reader, '_read_storage', unexpected)
    monkeypatch.setattr('sec_agent.research_foundation.organization_index_release.ConfiguredQuerySource.embed', unexpected)
    assert nav.warm_release() == contract
    state['status'] = 404
    with pytest.raises(OrganizationExecutionUnavailable):
        nav.warm_release()


def test_failed_lexical_publication_never_becomes_a_valid_release(tmp_path, monkeypatch):
    from uuid import uuid4
    from sec_agent.research_foundation.organization_hybrid_retrieval import publish_prepared_index
    _, _, org, nodes, _, _ = prepared(tmp_path)
    release = str(uuid4())
    def failed(path, rows):
        path.write_bytes(b'partial build')
        raise RuntimeError('injected publication failure')
    monkeypatch.setattr('retrieval.published_lexical_index.build', failed)
    with pytest.raises(RuntimeError, match='injected'):
        publish_prepared_index(tmp_path/'indices', org, nodes, [[1.] + [0.]*1023 for _ in nodes], {},
            model='qwen3.7-text-embedding', provenance={'fixture':True}, release_id=release)
    directory = tmp_path/'indices'/org/'releases'/release
    assert not (directory/'index.json').exists()
    assert (directory/'lexical.sqlite').read_bytes() == b'partial build'
    with pytest.raises(ValueError, match='unavailable'):
        releases.load_release(tmp_path/'indices', org, release)
