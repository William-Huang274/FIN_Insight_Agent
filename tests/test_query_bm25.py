import random

import numpy as np
import pytest
from rank_bm25 import BM25Okapi

from retrieval.query_bm25 import lexical_scores, TokenCounts, LexicalStatisticsCache
from collections import Counter
from retrieval.text import tokenize


@pytest.mark.parametrize('corpus,query', [
    ([['cash'], ['cash'], ['cash', 'flow']], ['cash', 'cash']),
    ([[], ['cash'], ['flow']], ['cash']),
    ([['cash'], ['flow']], ['cash']),  # zero IDF must remain a match
    ([['cash'], ['flow']], ['unknown']),
    ([['cash'], ['flow']], []),
    ([tokenize('经营现金流与股票薪酬'), tokenize('收入与现金流'), []], tokenize('现金流')),
])
def test_exact_upstream_scores_and_overlap(corpus, query):
    expected = BM25Okapi(corpus).get_scores(query)
    actual, overlap, has_terms = lexical_scores(iter(corpus), query)
    np.testing.assert_array_equal(actual, expected)
    assert overlap == [i for i, tokens in enumerate(corpus) if set(tokens).intersection(query)]
    assert has_terms


def test_randomized_corpus_and_queries_match_upstream_exactly():
    randomizer = random.Random(612)
    for _ in range(40):
        corpus = [[str(randomizer.randrange(50)) for _ in range(randomizer.randrange(90))]
                  for _ in range(randomizer.randrange(1, 80))]
        if not any(corpus):
            corpus.append(['one'])
        query = [str(randomizer.randrange(60)) for _ in range(12)]
        actual, overlap, has_terms = lexical_scores(iter(corpus), iter(query))
        np.testing.assert_array_equal(actual, BM25Okapi(corpus).get_scores(query))
        assert overlap == [i for i, tokens in enumerate(corpus) if set(tokens).intersection(query)]
        assert has_terms
        prepared = [TokenCounts(len(tokens), Counter(tokens)) for tokens in corpus]
        prepared_scores, prepared_overlap, prepared_terms = lexical_scores(iter(prepared), query)
        np.testing.assert_array_equal(prepared_scores, actual)
        assert prepared_overlap == overlap and prepared_terms


@pytest.mark.parametrize('corpus', [[], [[]], [[], []]])
def test_no_vocabulary_has_no_scores_or_overlap(corpus):
    assert lexical_scores(iter(corpus), ['cash']) == ((), [], False)


def test_nonquery_vocabulary_still_affects_epsilon_floor():
    corpus = [['cash', 'rare-a'], ['cash', 'rare-b'], ['cash', 'rare-c']]
    scores, _, _ = lexical_scores(iter(corpus), ['cash'])
    np.testing.assert_array_equal(scores, BM25Okapi(corpus).get_scores(['cash']))
    assert not np.array_equal(scores, BM25Okapi([['cash']] * 3).get_scores(['cash']))


def test_cached_population_scores_match_fresh_upstream_for_random_queries():
    rng = random.Random(781)
    cache = LexicalStatisticsCache()
    for population in range(20):
        corpus = [[str(rng.randrange(40)) for _ in range(rng.randrange(1, 80))]
                  for _ in range(rng.randrange(2, 60))]
        prepared = [TokenCounts(len(doc), Counter(doc)) for doc in corpus]
        reference = BM25Okapi(corpus)
        for number in range(5):
            query = [str(rng.randrange(50)) for _ in range(10)]
            actual, overlap, has_terms = cache.scores(iter(prepared), iter(query), corpus_key=population)
            np.testing.assert_array_equal(actual, reference.get_scores(query))
            assert overlap == [i for i, doc in enumerate(corpus) if set(doc).intersection(query)]
            assert has_terms and cache.hit == (number > 0)


@pytest.mark.parametrize('corpus', [[], [[]], [[], []], [['cash'], ['flow']],
    [['cash', 'rare-a'], ['cash', 'rare-b'], ['cash', 'rare-c']],
    [tokenize('经营现金流与股票薪酬'), tokenize('收入与现金流'), []]])
def test_cached_population_empty_zero_negative_idf_and_repeated_terms(corpus):
    cache = LexicalStatisticsCache()
    for query in (['cash'], ['cash', 'cash'], tokenize('现金流'), ['absent'], []):
        actual = cache.scores(iter(corpus), query, corpus_key='same')
        expected = lexical_scores(iter(corpus), query)
        np.testing.assert_array_equal(actual[0], expected[0])
        assert actual[1:] == expected[1:]


def test_scope_and_order_change_rebuild_population_and_do_not_reuse_global_idf():
    cache = LexicalStatisticsCache()
    corpus = [['cash', 'rare-a'], ['cash', 'rare-b'], ['cash', 'rare-c'], ['other'] * 20]
    for key, scoped in [('global', corpus), ('scoped', corpus[:2]), ('reversed', corpus[::-1]), ('global', corpus)]:
        actual = cache.scores(iter(scoped), ['cash'], corpus_key=key)
        assert not cache.hit
        np.testing.assert_array_equal(actual[0], BM25Okapi(scoped).get_scores(['cash']))


def test_cached_population_rejects_wrong_document_lengths():
    cache = LexicalStatisticsCache()
    cache.scores([['cash'], ['flow']], ['cash'], corpus_key='scope')
    with pytest.raises(ValueError, match='corpus_mismatch'):
        cache.scores([['cash', 'cash'], ['flow']], ['cash'], corpus_key='scope')


def test_statistics_hit_does_not_recalculate_idf(monkeypatch):
    cache = LexicalStatisticsCache()
    corpus = [['cash', 'rare-a'], ['cash', 'rare-b'], ['flow']]
    expected = BM25Okapi(corpus).get_scores(['flow'])
    cache.scores(iter(corpus), ['cash'], corpus_key='scope')
    def unexpected_idf(*args):
        raise AssertionError('statistics hit must not recompute vocabulary IDF')
    monkeypatch.setattr(BM25Okapi, '_calc_idf', unexpected_idf)
    actual = cache.scores(iter(corpus), ['flow'], corpus_key='scope')
    np.testing.assert_array_equal(actual[0], expected)
    assert cache.hit


@pytest.mark.parametrize('limit,raw_limit', [(0, 100000), (100000, 0)])
def test_statistics_size_limit_uses_fresh_scoring_without_retaining_population(limit, raw_limit):
    cache = LexicalStatisticsCache(limit=limit)
    cache.MAX_RAW = raw_limit
    corpus = [['cash', 'rare-a'], ['cash', 'rare-b'], ['flow']]
    for query in (['cash'], ['flow']):
        actual = cache.scores(iter(corpus), query, corpus_key='scope')
        np.testing.assert_array_equal(actual[0], BM25Okapi(corpus).get_scores(query))
        assert cache.entry is None and not cache.hit
