import sqlite3

import pytest

from scripts.data_retrieval.replay_cached_library_scenarios import ReadOnlyReceipts
from sec_agent.adapters.local_records import LocalRecords
from retrieval.source_hybrid import CachedRetrieval


def test_replay_cache_hit_and_miss_never_write_or_call_provider(tmp_path):
    class API:
        embedding_model = 'test'
        rerank_model = 'test'
        def embed(self, *args):
            pytest.fail('offline replay must not invoke provider')
    with LocalRecords(tmp_path) as records:
        client = CachedRetrieval(records, API(), 'scope')
        key = client.key('embedding', ['known'])
        records[key] = {'result': {'values': [[1., 0.]]}}
    before = (tmp_path/'records-v1.sqlite').read_bytes()
    with ReadOnlyReceipts(tmp_path) as records:
        client = CachedRetrieval(records, API(), 'scope')
        assert client.embed_query('known') == [1., 0.]
        with pytest.raises(RuntimeError, match='no_paid_fallback'):
            client.embed_query('unknown')
        assert client.calls == 0 and client.hits == 1
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            records.db.execute('DELETE FROM records')
    assert (tmp_path/'records-v1.sqlite').read_bytes() == before


def test_missing_receipt_database_is_not_created(tmp_path):
    with pytest.raises(sqlite3.OperationalError):
        ReadOnlyReceipts(tmp_path)
    assert not list(tmp_path.iterdir())
