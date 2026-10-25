from copy import deepcopy
from hashlib import sha256
import random
import sqlite3
import zlib

import numpy as np
import pytest

from retrieval import published_lexical_index as published
from retrieval.query_bm25 import lexical_document, lexical_scores


def nodes(texts):
    return [dict(node_id=f'node-{i}', content=text, content_sha256=sha256(text.encode()).hexdigest())
            for i, text in enumerate(texts)]


@pytest.mark.parametrize('texts', [[], ['', '[]'], ['cash', 'cash flow', 'rare'],
    ['经营现金流 收入 收入', '现金流', ''], ['cash a', 'cash b', 'cash c']])
def test_exact_scores_for_whole_filtered_and_reordered_populations(tmp_path, texts, monkeypatch):
    rows = nodes(texts)
    path = tmp_path/'lexical.sqlite'
    # Exercise shards crossing within a single document, without truncation.
    monkeypatch.setattr(published, 'SHARD_BYTES', 16)
    assert published.build(path, rows) == len(rows)
    for selection in (rows, rows[:1], rows[::-1], rows[::2]):
        for query in (['cash'], ['cash', 'cash'], ['收入'], ['absent'], []):
            expected = lexical_scores((lexical_document(row) for row in selection), query)
            actual = published.scores(path, selection, query)
            np.testing.assert_array_equal(actual[0], expected[0])
            assert actual[1:] == expected[1:]


def test_randomized_queries_preserve_upstream_scores_and_do_not_tokenize(tmp_path, monkeypatch):
    rng = random.Random(1409)
    rows = nodes([' '.join(str(rng.randrange(30)) for _ in range(rng.randrange(1, 80))) for _ in range(70)])
    path = tmp_path/'lexical.sqlite'
    published.build(path, rows)
    cases = []
    for _ in range(30):
        selection = rows if rng.random() < .5 else rng.sample(rows, rng.randrange(1, len(rows)))
        query = [str(rng.randrange(40)) for _ in range(10)]
        cases.append((selection, query, lexical_scores((lexical_document(row) for row in selection), query)))
    def unexpected(*args):
        raise AssertionError('published queries must not tokenize originals')
    monkeypatch.setattr('retrieval.text.tokenize', unexpected)
    for selection, query, expected in cases:
        actual = published.scores(path, selection, query)
        np.testing.assert_array_equal(actual[0], expected[0])
        assert actual[1:] == expected[1:]


def test_model_text_identity_duplicate_and_missing_population_rejected(tmp_path):
    rows = nodes(['original body'])
    rows[0]['model_text'] = 'index these terms'
    path = tmp_path/'lexical.sqlite'
    published.build(path, rows)
    changed = deepcopy(rows)
    changed[0]['model_text'] = 'poisoned terms'
    with pytest.raises(ValueError, match='source_mismatch'):
        published.scores(path, changed, ['terms'])
    with pytest.raises(ValueError, match='duplicate'):
        published.scores(path, rows * 2, ['terms'])
    with pytest.raises(ValueError, match='source_mismatch'):
        published.scores(path, nodes(['wrong original']), ['terms'])
    with pytest.raises(FileExistsError):
        published.build(path, rows)


def test_full_population_reads_postings_not_per_document_counts(tmp_path):
    rows = nodes(['cash a', 'cash b', 'flow'])
    path = tmp_path/'lexical.sqlite'
    published.build(path, rows)
    expected = published.scores(path, rows, ['cash'])
    # Internal storage probe: release-integrity checking is tested separately.
    with sqlite3.connect(path) as db:
        db.execute('UPDATE nodes SET counts=?', (b'must not decode',))
    actual = published.scores(path, rows, ['cash'])
    np.testing.assert_array_equal(actual[0], expected[0])
    assert actual[1:] == expected[1:]


def test_filtered_population_fetches_only_selected_identities_in_bounded_batches(tmp_path, monkeypatch):
    rows = nodes(['cash '+str(i) for i in range(100)])
    path = tmp_path/'lexical.sqlite'
    published.build(path, rows)
    connect = sqlite3.connect
    statements = []
    def traced(*args, **kwargs):
        db = connect(*args, **kwargs)
        db.set_trace_callback(statements.append)
        return db
    monkeypatch.setattr(published.sqlite3, 'connect', traced)
    monkeypatch.setattr(published, 'IDENTITY_BATCH', 2)
    monkeypatch.setattr(published, 'COUNTS_BATCH', 2)
    selected = [rows[99], rows[3], rows[60]]
    actual = published.scores(path, selected, ['cash','60'])
    expected = lexical_scores((lexical_document(row) for row in selected), ['cash','60'])
    np.testing.assert_array_equal(actual[0], expected[0])
    reads = [sql for sql in statements if sql.startswith('SELECT position,node_id')]
    assert len(reads) == 2 and all('WHERE node_id IN' in sql for sql in reads)
    assert all('ORDER BY position' not in sql for sql in reads)
    count_reads = [sql for sql in statements if sql.startswith('SELECT position,length,counts')]
    assert len(count_reads)==2 and all('WHERE position IN' in sql for sql in count_reads)
    # A wrong digest in a small scope still fails before any scoring.
    broken = deepcopy(selected); broken[0]['content_sha256'] = 'wrong'
    with pytest.raises(ValueError, match='source_mismatch'):
        published.scores(path, broken, ['cash'])


def test_subset_statistics_reuse_reads_postings_and_keeps_scope_order(tmp_path, monkeypatch):
    rows = nodes(['cash equity equity','cash debt','rare cash','cash']*5)
    path = tmp_path/'lexical.sqlite'
    published.build(path, rows)
    selected = [rows[19],rows[1],rows[2]]
    cache = published.PublishedLexicalStatistics()
    identities = lambda selection: [(r['node_id'],r['content_sha256'],published.lexical_digest(r)) for r in selection]
    statements = []
    connect = sqlite3.connect
    def traced(*args, **kwargs):
        db = connect(*args, **kwargs); db.set_trace_callback(statements.append); return db
    monkeypatch.setattr(published.sqlite3,'connect',traced)
    for i, query in enumerate((['cash'],['rare','rare'],['absent'],['debt'])):
        statements.clear()
        actual = published.scores_from_identities(path,identities(selected),query,population_cache=cache)
        expected = lexical_scores((lexical_document(row) for row in selected),query)
        np.testing.assert_array_equal(actual[0],expected[0]); assert actual[1:] == expected[1:]
        assert cache.hit == bool(i)
        assert any('SELECT position,length,counts' in sql for sql in statements) == (i==0)
    for other in (selected[::-1],selected[:1],rows):
        actual = published.scores_from_identities(path,identities(other),['cash'],population_cache=cache)
        expected = lexical_scores((lexical_document(row) for row in other),['cash'])
        np.testing.assert_array_equal(actual[0],expected[0]); assert not cache.hit


def test_subset_cache_invalidates_on_file_change_and_respects_memory_bound(tmp_path):
    rows = nodes(['cash equity','cash debt','rare'])
    path = tmp_path/'lexical.sqlite'; published.build(path,rows)
    selected = [(r['node_id'],r['content_sha256'],published.lexical_digest(r)) for r in rows[:2]]
    cache = published.PublishedLexicalStatistics()
    published.scores_from_identities(path,selected,['cash'],population_cache=cache)
    assert cache.entry
    with sqlite3.connect(path) as db:
        db.execute('UPDATE nodes SET counts=? WHERE position=0',(b'invalid',))
    with pytest.raises(zlib.error):
        published.scores_from_identities(path,selected,['cash'],population_cache=cache)
    assert not cache.hit
    other = tmp_path/'other.sqlite'; published.build(other,rows)
    tiny = published.PublishedLexicalStatistics(limit=1)
    published.scores_from_identities(other,selected,['cash'],population_cache=tiny)
    assert tiny.entry is None
