import random

import numpy as np
import pytest
from rank_bm25 import BM25Okapi

from retrieval.query_bm25 import lexical_scores
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


@pytest.mark.parametrize('corpus', [[], [[]], [[], []]])
def test_no_vocabulary_has_no_scores_or_overlap(corpus):
    assert lexical_scores(iter(corpus), ['cash']) == ((), [], False)


def test_nonquery_vocabulary_still_affects_epsilon_floor():
    corpus = [['cash', 'rare-a'], ['cash', 'rare-b'], ['cash', 'rare-c']]
    scores, _, _ = lexical_scores(iter(corpus), ['cash'])
    np.testing.assert_array_equal(scores, BM25Okapi(corpus).get_scores(['cash']))
    assert not np.array_equal(scores, BM25Okapi([['cash']] * 3).get_scores(['cash']))
