"""Security, upgrade compatibility and cross-process receipt admission."""
from concurrent.futures import ProcessPoolExecutor
import hashlib
import multiprocessing
import pickle
import sqlite3
import time

import pytest

from sec_agent.adapters.local_records import LocalRecords


def legacy_database(root, entries):
    """DiskCache 5.6.3 storage columns, no dependency on vulnerable package."""
    with sqlite3.connect(root / 'cache.db') as db:
        db.execute('CREATE TABLE Cache (key BLOB, raw INTEGER, expire_time REAL, mode INTEGER, filename TEXT, value BLOB)')
        db.executemany('INSERT INTO Cache VALUES (?, 1, ?, ?, ?, ?)', entries)


def test_import_preserves_bytes_vectors_json_and_expiry_without_modifying_original(tmp_path):
    receipt = {'fingerprint': 'original', 'status': 'received', 'http_status': 201,
               'body': b'{"id":"old-run"}'}
    (tmp_path / 'vector.val').write_bytes(pickle.dumps([1.0, 0.25]))
    legacy_database(tmp_path, [
        ('receipt', None, 4, None, pickle.dumps(receipt)),
        ('vector', None, 4, 'vector.val', None),
        ('capture', time.time() + 300, 1, None, '{"status":"captured"}'),
        ('expired', time.time() - 10, 1, None, 'old'),
        ('unknown', None, 4, None, pickle.dumps({'status': 'failed_usage_unknown'})),
    ])
    original = hashlib.sha256((tmp_path / 'cache.db').read_bytes()).hexdigest()
    for _ in range(2):
        with LocalRecords(tmp_path) as records:
            assert records['receipt'] == receipt
            assert records['vector'] == [1.0, 0.25]
            assert records['capture'] == '{"status":"captured"}'
            assert records.get('expired') is None
            assert not records.add('unknown', {'status': 'started'})
    assert hashlib.sha256((tmp_path / 'cache.db').read_bytes()).hexdigest() == original


@pytest.mark.parametrize('payload', [
    b'cbuiltins\neval\n(V1+1\ntR.',  # GLOBAL / REDUCE
    b'\x80\x04\x82\x01.',  # EXT1 must not use an extension registry
    b'\x80\x04Pexternal\n.',  # persistent reference
])
def test_unsafe_legacy_payload_rolls_back_whole_import_and_blocks_admission(tmp_path, payload):
    legacy_database(tmp_path, [('valid', None, 1, None, 'keep'),
                               ('unsafe', None, 4, None, payload)])
    for _ in range(2):
        with pytest.raises(ValueError, match='forbidden'):
            LocalRecords(tmp_path)
    with sqlite3.connect(tmp_path / 'records-v1.sqlite') as db:
        assert db.execute('SELECT count(*) FROM records').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM metadata').fetchone()[0] == 0


def test_legacy_external_value_cannot_escape_cache_directory(tmp_path):
    outside = tmp_path.parent / (tmp_path.name + '-outside.val')
    outside.write_bytes(pickle.dumps('not owned'))
    legacy_database(tmp_path, [('bad', None, 4, str(outside), None)])
    with pytest.raises(ValueError, match='path_or_size'):
        LocalRecords(tmp_path)


def _claim(directory):
    with LocalRecords(directory) as records:
        return records.add('same-submission', {'status': 'dispatching'})


def test_sqlite_admits_exactly_one_claim_across_processes(tmp_path):
    with ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context('spawn')) as pool:
        assert sum(pool.map(_claim, [str(tmp_path)] * 12)) == 1
    with LocalRecords(tmp_path) as records:
        assert records['same-submission']['status'] == 'dispatching'


def test_source_cache_ttl_size_bound_and_json_roundtrip(tmp_path, monkeypatch):
    with LocalRecords(tmp_path, size_limit=160) as records:
        monkeypatch.setattr('sec_agent.adapters.local_records.time.time', lambda: 100)
        records.set('first', 'a' * 80, expire=2)
        records.set('second', 'b' * 80, expire=3)
        assert records.get('first') is None
        assert records['second'] == 'b' * 80
        monkeypatch.setattr('sec_agent.adapters.local_records.time.time', lambda: 104)
        assert records.get('second') is None
        value = {'__fin_bytes__': 'ordinary text', 'body': b'\x00\xff', 'nested': [True, None, 1.5]}
        records.size_limit = None
        records['roundtrip'] = value
        assert records['roundtrip'] == value


def test_legacy_completed_and_unknown_provider_calls_never_reach_provider(tmp_path):
    from retrieval.source_hybrid import CachedRetrieval
    class NoCalls:
        embedding_model = 'test-embed'
        rerank_model = 'test-rerank'
        def embed(self, _):
            pytest.fail('legacy call must not be sent again')
    client = CachedRetrieval(None, NoCalls(), 'scope')
    key = client.key('embedding', ['known'])
    unknown = client.key('embedding', ['unknown'])
    legacy_database(tmp_path, [
        (key, None, 4, None, pickle.dumps({'status': 'completed', 'result': {'values': [[1.0, 0.0]]}})),
        (unknown, None, 4, None, pickle.dumps({'status': 'failed_usage_unknown'})),
    ])
    with LocalRecords(tmp_path) as records:
        client.cache = records
        assert client.embed_query('known') == [1.0, 0.0]
        with pytest.raises(RuntimeError, match='未自动重发'):
            client.embed_query('unknown')
