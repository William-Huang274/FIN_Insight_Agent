"""Bounded, disposable exact term counts; scoring stays in rank_bm25.

Only use inside an independently verified immutable ordered population. This
is an in-memory optimization, not an index publication or permission cache.
"""
import struct
import sys
import zlib


PAIR = struct.Struct('<IH')


class PostingBuilder:
    MAX_RAW = 128 * 1024 * 1024

    def __init__(self, limit):
        self.limit, self.columns, self.raw_bytes = limit, {}, 0
        self.disabled = not limit

    def add(self, position, counts):
        if self.disabled:
            return
        size = len(counts) * PAIR.size
        if (self.raw_bytes + size > self.MAX_RAW or position > 0xffffffff
                or any(type(n) is not int or not 0 < n <= 0xffff for n in counts.values())):
            self.columns.clear()
            self.disabled = True
            return
        self.raw_bytes += size
        for term, count in counts.items():
            column = self.columns.get(term)
            if column is None:
                column = self.columns[term] = bytearray()
            column.extend(PAIR.pack(position, count))

    def finish(self):
        if self.disabled:
            return None, 0
        # Replace each builder buffer immediately, avoiding a second full copy.
        size = sys.getsizeof(self.columns)
        for term in self.columns:
            packed = zlib.compress(self.columns[term], 1)
            self.columns[term] = packed
            size += sys.getsizeof(term) + sys.getsizeof(packed)
            if size > self.limit:
                self.columns.clear()
                return None, 0
        return self.columns, size


def query_counts(columns, query, lengths):
    """Decode only requested term columns, preserving original document order."""
    matched = {}
    for term in dict.fromkeys(query):
        encoded = columns.get(term)
        if encoded is None:
            continue
        for position, count in PAIR.iter_unpack(zlib.decompress(encoded)):
            matched.setdefault(position, {})[term] = count
    from .query_bm25 import TokenCounts
    return (TokenCounts(length, matched.get(position, {}))
            for position, length in enumerate(lengths))
