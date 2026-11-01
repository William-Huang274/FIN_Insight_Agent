import hashlib
import sqlite3
import numpy as np
import pytest

from retrieval import published_lexical_index as published
from retrieval.lexical_metadata import prepare
from test_published_lexical_index import nodes


def test_projection_reuses_without_release_mutation_and_keeps_scores(tmp_path, monkeypatch):
    rows = nodes(['cash equity equity', 'cash debt', 'rare cash', 'cash'])
    path = tmp_path / 'release.sqlite'
    published.build(path, rows)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    projection = prepare(path, tmp_path / 'cache')
    identity = projection.projection_identity
    assert prepare(path, tmp_path / 'cache').projection_identity == identity
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    statements = []
    connect = sqlite3.connect
    def traced(*args, **kwargs):
        db = connect(*args, **kwargs); db.set_trace_callback(statements.append); return db
    monkeypatch.setattr(published.sqlite3, 'connect', traced)
    cache = published.PublishedLexicalStatistics()
    cache.metadata = projection
    for selected in (rows, rows[::-1], rows[::2], rows[::2]):
        ids = [(r['node_id'], r['content_sha256'], published.lexical_digest(r)) for r in selected]
        expected = published.scores_from_identities(path, ids, ['cash', 'rare'])
        statements.clear()
        actual = published.scores_from_identities(path, ids, ['cash', 'rare'], population_cache=cache)
        np.testing.assert_array_equal(actual[0], expected[0])
        assert actual[1:] == expected[1:]
        reads = [s for s in statements if s.startswith('SELECT position,node_id')]
        assert reads and all('FROM meta.nodes' in s for s in reads)
    bad = [list(ids[0])]; bad[0][1] = 'wrong'
    with pytest.raises(ValueError, match='source_mismatch'):
        published.scores_from_identities(path, bad, ['cash'], metadata_index=projection)
    with sqlite3.connect(path) as db:
        db.execute('UPDATE nodes SET length=length+1 WHERE position=0')
    with pytest.raises(ValueError, match='metadata_changed'):
        published.scores_from_identities(path, ids, ['cash'], metadata_index=projection)


def test_projection_rejects_other_source_or_changed_projection(tmp_path):
    first, other = tmp_path / 'one.sqlite', tmp_path / 'two.sqlite'
    rows = nodes(['cash'])
    published.build(first, rows); published.build(other, rows)
    projection = prepare(first, tmp_path / 'cache')
    with pytest.raises(ValueError, match='wrong_source'):
        published.scores_from_identities(other, [], [], metadata_index=projection)
    with sqlite3.connect(projection.path) as db:
        db.execute('UPDATE nodes SET length=999')
    with pytest.raises(ValueError, match='metadata_changed'):
        published.scores_from_identities(first, [], [], metadata_index=projection)
