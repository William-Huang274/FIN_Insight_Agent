from copy import deepcopy
from hashlib import sha256
import random
import sqlite3

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
