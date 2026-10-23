from collections import Counter
import random

import numpy as np
import pytest
from rank_bm25 import BM25Okapi

from retrieval.lexical_postings import PostingBuilder
from retrieval.query_bm25 import LexicalStatisticsCache, TokenCounts, lexical_scores


def unavailable():
    raise AssertionError('verified posting hit must not unpack document vocabularies')
    yield


def test_verified_postings_match_upstream_random_queries_without_consuming_corpus():
    rng = random.Random(6721)
    for _ in range(20):
        corpus = [[str(rng.randrange(40)) for _ in range(rng.randrange(1, 80))]
                  for _ in range(rng.randrange(2, 60))]
        cache = LexicalStatisticsCache(postings_limit=1024*1024)
        cache.scores(iter(corpus), ['warmup'], corpus_key='scope', verified_population=True)
        assert cache.postings is not None and cache.postings_bytes <= cache.postings_limit
        for _ in range(5):
            query = [str(rng.randrange(50)) for _ in range(10)]
            scores, overlap, _ = cache.scores(unavailable(), query, corpus_key='scope', verified_population=True)
            np.testing.assert_array_equal(scores, BM25Okapi(corpus).get_scores(query))
            assert overlap == [i for i, doc in enumerate(corpus) if set(doc).intersection(query)]
            assert cache.postings_hit


@pytest.mark.parametrize('corpus', [[], [[]], [[], []], [['cash'], ['flow']],
    [['cash', 'rare-a'], ['cash', 'rare-b'], ['cash', 'rare-c']],
    [['现金流', '收入', '收入'], ['收入'], []]])
def test_postings_keep_empty_overlap_negative_zero_idf_and_repeated_query_terms(corpus):
    cache = LexicalStatisticsCache(postings_limit=1024*1024)
    cache.scores(corpus, ['first'], corpus_key='scope', verified_population=True)
    for query in (['cash'], ['cash', 'cash'], ['收入'], ['absent'], []):
        actual = cache.scores(unavailable(), query, corpus_key='scope', verified_population=True)
        expected = lexical_scores(iter(corpus), query)
        np.testing.assert_array_equal(actual[0], expected[0])
        assert actual[1:] == expected[1:] and cache.postings_hit


def test_postings_require_verified_scope_and_reset_on_order_or_scope_change():
    cache = LexicalStatisticsCache(postings_limit=1024*1024)
    corpus = [['cash', 'a'], ['cash', 'b'], ['other']*20]
    for key, rows in [('full', corpus), ('partial', corpus[:2]), ('reverse', corpus[::-1]), ('full', corpus)]:
        actual = cache.scores(rows, ['cash'], corpus_key=key, verified_population=True)
        np.testing.assert_array_equal(actual[0], BM25Okapi(rows).get_scores(['cash']))
        assert not cache.postings_hit
    # The generic caller cannot bypass current corpus validation.
    with pytest.raises(ValueError, match='corpus_mismatch'):
        cache.scores([['changed']], ['cash'], corpus_key='full')
    assert not cache.postings_hit
    cache.clear()
    assert cache.entry is None and cache.postings is None and cache.postings_bytes == 0


@pytest.mark.parametrize('limit,raw_limit,count', [(1, 100000, 2), (100000, 0, 2), (100000, 100000, 65536)])
def test_posting_admission_limits_keep_exact_uncached_path(monkeypatch, limit, raw_limit, count):
    monkeypatch.setattr(PostingBuilder, 'MAX_RAW', raw_limit)
    cache = LexicalStatisticsCache(postings_limit=limit)
    corpus = [TokenCounts(count, {'cash':count}), TokenCounts(1, {'flow':1})]
    for query in (['cash'], ['flow']):
        actual = cache.scores(iter(corpus), query, corpus_key='scope', verified_population=True)
        expected = lexical_scores(iter(corpus), query)
        np.testing.assert_array_equal(actual[0], expected[0])
        assert actual[1:] == expected[1:]
        assert cache.postings is None and cache.postings_bytes == 0 and not cache.postings_hit


def test_builder_rejects_position_overflow_without_wrapping():
    builder = PostingBuilder(1024)
    builder.add(2**32, Counter(['cash']))
    assert builder.finish() == (None, 0)


def test_no_statistics_admission_does_not_retain_postings():
    cache = LexicalStatisticsCache(limit=0, postings_limit=1024*1024)
    cache.scores([['cash']], ['cash'], corpus_key='scope', verified_population=True)
    assert cache.entry is None and cache.postings is None
