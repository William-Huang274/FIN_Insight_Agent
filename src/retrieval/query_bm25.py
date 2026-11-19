"""Query-local storage adapter for rank_bm25; no scoring formula is replaced.

Consume tokenized documents once, retaining document frequencies for the whole
vocabulary (including non-query terms, needed by Okapi's epsilon floor), but
only query-term counts per document. Never reuse this object for another query.
"""
from collections import Counter
from dataclasses import dataclass
import json
import zlib

from rank_bm25 import BM25Okapi


@dataclass(frozen=True)
class TokenCounts:
    """Exact token length and counts in first-occurrence vocabulary order."""
    length: int
    counts: dict[str, int]


def lexical_document(row):
    prepared = getattr(row, 'lexical_counts', None)
    if prepared is not None:
        return prepared()
    from .text import tokenize
    return tokenize(str(row.get('model_text') or row.get('content') or ''))


class _QueryBM25(BM25Okapi):
    def __init__(self, corpus, query, statistics=None, posting_builder=None):
        self.query_terms = frozenset(query)
        self.statistics = statistics
        self.posting_builder = posting_builder
        super().__init__(corpus)

    def _initialize(self, corpus):
        document_frequencies = {}
        total_length = 0
        for document in corpus:
            length = document.length if isinstance(document, TokenCounts) else len(document)
            self.doc_len.append(length)
            total_length += length
            counts = document.counts if isinstance(document, TokenCounts) else Counter(document)
            if self.posting_builder is not None:
                self.posting_builder.add(self.corpus_size, counts)
            # Preserve first-occurrence vocabulary order: the upstream IDF
            # average uses floating-point accumulation in this order.
            if self.statistics is None:
                for term in counts:
                    document_frequencies[term] = document_frequencies.get(term, 0) + 1
            self.doc_freqs.append({term: counts[term] for term in self.query_terms if term in counts})
            self.corpus_size += 1
        self.avgdl = total_length / self.corpus_size if self.corpus_size else 0
        return document_frequencies

    def _calc_idf(self, document_frequencies):
        if self.statistics is not None:
            lengths, idf, average_idf, avgdl = self.statistics
            if lengths != self.doc_len or avgdl != self.avgdl:
                raise ValueError('bm25_statistics_corpus_mismatch')
            self.idf, self.average_idf = idf, average_idf
        elif document_frequencies:
            super()._calc_idf(document_frequencies)


def lexical_scores(corpus, query):
    """Return upstream scores, lexical-overlap positions and vocabulary presence.

    Corpus may be a single-use iterator. Query token repetitions are preserved
    in scoring. Zero/negative IDF matches remain eligible, as in navigation.
    """
    query = tuple(query)
    index = _QueryBM25(corpus, query)
    return _scores(index, query)


def _scores(index, query):
    overlap = [i for i, counts in enumerate(index.doc_freqs) if counts]
    if not index.idf:
        return (), overlap, False
    return index.get_scores(query), overlap, True


class LexicalStatisticsCache:
    """One compressed population, owned by an already verified source generation.

    The caller must bind corpus_key to the exact ordered, immutable input scope
    and reset this cache when its authorization/storage generation changes.
    By default counts come from verified projections on every query. Optional
    postings may be reused only when the caller verifies the full population
    before each call. No positive permission decisions are retained here.
    """
    MAX_RAW = 32 * 1024 * 1024

    def __init__(self, limit=8 * 1024 * 1024, *, postings_limit=0):
        self.limit = limit
        self.postings_limit = postings_limit
        self.clear()

    def clear(self):
        self.entry = None
        self.hit = False
        self.postings = None
        self.postings_bytes = 0
        self.postings_hit = False

    def scores(self, corpus, query, *, corpus_key, verified_population=False):
        query = tuple(query)
        self.hit = self.entry is not None and self.entry[0] == corpus_key
        statistics = json.loads(zlib.decompress(self.entry[1])) if self.hit else None
        # A key change drops the previous population even if the new one is
        # too large to admit. Never use global IDF for a document-only search.
        if not self.hit:
            self.clear()
        self.postings_hit = bool(verified_population and self.hit and self.postings is not None)
        builder = None
        if self.postings_hit:
            from .lexical_postings import query_counts
            corpus = query_counts(self.postings, query, statistics[0])
        elif verified_population and self.postings_limit and not self.hit:
            from .lexical_postings import PostingBuilder
            builder = PostingBuilder(self.postings_limit)
        index = _QueryBM25(corpus, query, statistics, builder)
        result = _scores(index, query)
        if not self.hit:
            raw = json.dumps([index.doc_len, index.idf,
                getattr(index, 'average_idf', 0), index.avgdl],
                ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
            if len(raw) <= self.MAX_RAW:
                packed = zlib.compress(raw, level=1)
                if len(packed) <= self.limit:
                    self.entry = corpus_key, packed
                    if builder is not None:
                        self.postings, self.postings_bytes = builder.finish()
        return result
