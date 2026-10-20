from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from retrieval.qwen_api import RetrievalResponse
from retrieval.query_embeddings import QueryEmbeddingSource


class Api:
    embedding_model = 'text-embedding-v4'
    rerank_model = 'unused'

    def __init__(self):
        self.calls = 0
        self.error = None

    def embed(self, texts):
        self.calls += 1
        if self.error:
            raise self.error
        return RetrievalResponse([[1.] + [0.] * 1023], {'total_tokens': 12}, 'receipt', self.embedding_model)


def request(source, **overrides):
    args = dict(scope='organization-A', index_digest='a' * 64,
                model='text-embedding-v4', dimensions=1024)
    args.update(overrides)
    return source.embed('How did operating cash flow change?', **args)


def test_success_survives_restart_and_different_scope_or_index_cannot_hit(tmp_path):
    api = Api()
    source = QueryEmbeddingSource(tmp_path, api, model=api.embedding_model)
    first, metadata = request(source)
    assert metadata['provider_calls'] == 1 and not metadata['cache_hit']
    assert metadata['newly_reported_usage'] == {'total_tokens': 12}
    restored = QueryEmbeddingSource(tmp_path, api, model=api.embedding_model)
    again, metadata = request(restored)
    assert again == first and metadata['cache_hit'] and metadata['provider_calls'] == 0
    assert metadata['usage'] == {'total_tokens': 12}
    assert metadata['newly_reported_usage'] == {}
    request(restored, scope='organization-B')
    request(restored, index_digest='b' * 64)
    assert api.calls == 3


def test_unknown_failure_persists_without_automatic_resubmission(tmp_path):
    api = Api()
    api.error = TimeoutError('provider result unknown')
    source = QueryEmbeddingSource(tmp_path, api, model=api.embedding_model)
    with pytest.raises(TimeoutError):
        request(source)
    api.error = None
    restored = QueryEmbeddingSource(tmp_path, api, model=api.embedding_model)
    with pytest.raises(RuntimeError, match='未自动重发'):
        request(restored)
    assert api.calls == 1


@pytest.mark.parametrize('override', [
    {'model': 'qwen3.7-text-embedding'}, {'dimensions': 768},
    {'index_digest': 'latest'}, {'scope': ''},
])
def test_index_or_scope_mismatch_never_calls_provider(tmp_path, override):
    api = Api()
    with pytest.raises(ValueError):
        request(QueryEmbeddingSource(tmp_path, api, model=api.embedding_model), **override)
    assert api.calls == 0


def test_query_limits_do_not_silently_truncate(tmp_path):
    api = Api()
    source = QueryEmbeddingSource(tmp_path, api, model=api.embedding_model, max_query_bytes=4)
    for query in ('', ' \n', '五个字', '12345'):
        with pytest.raises(ValueError, match='input_limit'):
            source.embed(query, scope='A', index_digest='a' * 64, model=api.embedding_model, dimensions=1024)
    assert api.calls == 0


def test_concurrent_same_query_has_one_billable_request(tmp_path):
    entered, release = Event(), Event()
    api = Api()
    original = api.embed
    def blocking(texts):
        entered.set()
        assert release.wait(timeout=10)
        return original(texts)
    api.embed = blocking
    source = QueryEmbeddingSource(tmp_path, api, model=api.embedding_model)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(request, source)
        assert entered.wait(timeout=10)
        try:
            with pytest.raises(RuntimeError):
                request(source)
        finally:
            release.set()
        assert first.result(timeout=10)[1]['provider_calls'] == 1
    assert request(source)[1]['cache_hit'] and api.calls == 1


def test_waiting_followers_reuse_one_receipt_without_dispatching_again(tmp_path):
    import time
    api = Api()
    original = api.embed
    def slow(texts):
        time.sleep(.2)
        return original(texts)
    api.embed = slow
    source = QueryEmbeddingSource(tmp_path, api, model=api.embedding_model, wait_inflight_seconds=2)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: request(source), range(8)))
    assert api.calls == 1
    assert sum(r[1]['provider_calls'] for r in results) == 1
    assert sum(bool(r[1]['cache_hit']) for r in results) == 7


def test_waiting_follower_does_not_resubmit_failed_or_orphaned_request(tmp_path):
    api = Api()
    source = QueryEmbeddingSource(tmp_path, api, model=api.embedding_model, wait_inflight_seconds=.1)
    api.error = TimeoutError()
    with pytest.raises(TimeoutError):
        request(source)
    api.error = None
    with pytest.raises(RuntimeError):
        request(source)
    assert api.calls == 1
