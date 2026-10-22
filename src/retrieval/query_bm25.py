"""Query-local storage adapter for rank_bm25; no scoring formula is replaced.

Consume tokenized documents once, retaining document frequencies for the whole
vocabulary (including non-query terms, needed by Okapi's epsilon floor), but
only query-term counts per document. Never reuse this object for another query.
"""
from collections import Counter

from rank_bm25 import BM25Okapi


class _QueryBM25(BM25Okapi):
    def __init__(self, corpus, query):
        self.query_terms = frozenset(query)
        super().__init__(corpus)

    def _initialize(self, corpus):
        document_frequencies = {}
        total_length = 0
        for document in corpus:
            length = len(document)
            self.doc_len.append(length)
            total_length += length
            counts = Counter(document)
            # Preserve first-occurrence vocabulary order: the upstream IDF
            # average uses floating-point accumulation in this order.
            for term in counts:
                document_frequencies[term] = document_frequencies.get(term, 0) + 1
            self.doc_freqs.append({term: count for term, count in counts.items()
                                   if term in self.query_terms})
            self.corpus_size += 1
        self.avgdl = total_length / self.corpus_size if self.corpus_size else 0
        return document_frequencies

    def _calc_idf(self, document_frequencies):
        if document_frequencies:
            super()._calc_idf(document_frequencies)


def lexical_scores(corpus, query):
    """Return upstream scores, lexical-overlap positions and vocabulary presence.

    Corpus may be a single-use iterator. Query token repetitions are preserved
    in scoring. Zero/negative IDF matches remain eligible, as in navigation.
    """
    query = tuple(query)
    index = _QueryBM25(corpus, query)
    overlap = [i for i, counts in enumerate(index.doc_freqs) if counts]
    if not index.idf:
        return (), overlap, False
    return index.get_scores(query), overlap, True
