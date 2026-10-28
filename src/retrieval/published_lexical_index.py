"""Published SQLite postings; rank_bm25 remains the scoring implementation.

Build once from exact ordered source nodes. Query reads only requested term
columns. A filtered population recomputes its own IDF from saved counts, never
from global statistics or original text. Authorization belongs to the caller.
"""
from collections import Counter
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import struct
import zlib

from .query_bm25 import TokenCounts, _QueryBM25, _scores, lexical_document


FORMAT = 'published-bm25-postings.v1'
PAIR = struct.Struct('<QQ')
SHARD_BYTES = 8 * 1024 * 1024
IDENTITY_BATCH = 256
COUNTS_BATCH = 256


class PublishedLexicalStatistics:
    """One bounded subset's statistics, no text, grants or query result cache.

    The caller serializes access. File identity and the exact ordered content
    identities bind reuse; current authorization is still checked by serving.
    """
    def __init__(self, limit=2 * 1024 * 1024):
        self.limit = limit
        self.entry = None
        self.hit = False

    def get(self, key):
        self.hit = self.entry is not None and self.entry[0] == key
        if not self.hit:
            self.entry = None
            return None
        return _unpack(self.entry[1])

    def put(self, key, index):
        raw = json.dumps([index.doc_len, index.idf, getattr(index, 'average_idf', 0), index.avgdl],
                         ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
        if len(raw) <= 32 * 1024 * 1024:
            packed = zlib.compress(raw, 1)
            if len(packed) <= self.limit:
                self.entry = key, packed


def _population_key(path, identities):
    resolved = Path(path).resolve()
    stat = resolved.stat()
    hasher = sha256(repr((str(resolved), stat.st_dev, stat.st_ino, stat.st_size,
                         stat.st_mtime_ns, stat.st_ctime_ns)).encode())
    for identity in identities:
        hasher.update(json.dumps(identity, separators=(',', ':'), ensure_ascii=False).encode())
        hasher.update(b'\n')
    return hasher.hexdigest()


def _pack(value):
    return zlib.compress(json.dumps(value, ensure_ascii=False, separators=(',', ':'),
                                    allow_nan=False).encode(), 1)


def _unpack(value):
    return json.loads(zlib.decompress(value))


def lexical_digest(row):
    return sha256(str(row.get('model_text') or row.get('content') or '').encode()).hexdigest()


def build(path, nodes):
    """A failure leaves an unpublished file, never a usable publication marker."""
    path = Path(path)
    # Exclusive reservation, including when a caller accidentally reuses a path.
    with path.open('xb'):
        pass
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript('''
            PRAGMA journal_mode=DELETE;
            PRAGMA cache_size=-8192;
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value BLOB NOT NULL);
            CREATE TABLE nodes (position INTEGER PRIMARY KEY, node_id TEXT UNIQUE NOT NULL,
                content_digest TEXT NOT NULL, lexical_digest TEXT NOT NULL,
                length INTEGER NOT NULL, counts BLOB NOT NULL);
            CREATE TABLE postings (term TEXT NOT NULL, shard INTEGER NOT NULL, value BLOB NOT NULL,
                PRIMARY KEY(term, shard)) WITHOUT ROWID;
        ''')
        columns, used, shard = {}, 0, 0

        def flush():
            nonlocal used, shard
            db.executemany('INSERT INTO postings VALUES (?,?,?)',
                           ((term, shard, zlib.compress(values, 1)) for term, values in columns.items()))
            columns.clear()
            used = 0
            shard += 1

        def corpus():
            nonlocal used
            for position, row in enumerate(nodes):
                prepared = lexical_document(row)
                counts = prepared.counts if isinstance(prepared, TokenCounts) else Counter(prepared)
                length = prepared.length if isinstance(prepared, TokenCounts) else len(prepared)
                db.execute('INSERT INTO nodes VALUES (?,?,?,?,?,?)', (position, row['node_id'],
                    row['content_sha256'], lexical_digest(row), length, _pack(counts)))
                for term, count in counts.items():
                    if not isinstance(term, str) or type(count) is not int or count <= 0:
                        raise ValueError('published_lexical_invalid_counts')
                    columns.setdefault(term, bytearray()).extend(PAIR.pack(position, count))
                    used += PAIR.size
                    if used >= SHARD_BYTES:
                        flush()
                yield TokenCounts(length, counts)

        index = _QueryBM25(corpus(), ())
        flush()
        db.execute('INSERT INTO metadata VALUES (?,?)', ('format', FORMAT.encode()))
        db.execute('INSERT INTO metadata VALUES (?,?)', ('statistics', _pack([
            index.doc_len, index.idf, getattr(index, 'average_idf', 0), index.avgdl])))
        return index.corpus_size


def scores(path, rows, query):
    """Caller has checked release integrity and current source/permission scope.

    Check the exact ordered IDs and lexical input digests. No caller can reuse
    full-population IDF for a different subset or reordered population.
    """
    return scores_from_identities(path, ((row['node_id'], row['content_sha256'], lexical_digest(row))
                                        for row in rows), query)


def scores_from_identities(path, identities, query, *, population_cache=None):
    """Score already verified (node ID, body SHA, lexical input SHA) identities.

    This lower-level entry does not prove originals or permissions. Published
    artifact integrity and the supplied scope must be verified by its caller.
    """
    query = tuple(query)
    identities = list(identities)
    if population_cache is not None:
        population_cache.hit = False
    key = _population_key(path, identities) if population_cache is not None else None
    uri = Path(path).resolve().as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True)) as db:
        if db.execute("SELECT value FROM metadata WHERE key='format'").fetchone() != (FORMAT.encode(),):
            raise ValueError('published_lexical_format_mismatch')
        total = db.execute('SELECT COUNT(*) FROM nodes').fetchone()[0]
        columns = 'position,node_id,content_digest,lexical_digest,length'
        if len(identities) >= total:
            entries = db.execute(f'SELECT {columns} FROM nodes ORDER BY position').fetchall()
        else:
            # Use the node_id index for every proper subset. A local SQLite
            # batch is not a network round trip: loading the entire release
            # here repeatedly penalizes each filtered financial query lane.
            # Restore caller order below; SQL IN order is not ranking order.
            entries = []
            for start in range(0, len(identities), IDENTITY_BATCH):
                ids = [row[0] for row in identities[start:start+IDENTITY_BATCH]]
                placeholders = ','.join('?' for _ in ids)
                entries.extend(db.execute(f'SELECT {columns} FROM nodes WHERE node_id IN ({placeholders})', ids))
        by_id = {entry[1]: entry for entry in entries}
        selected = []
        for node_id, content_digest, input_digest in identities:
            entry = by_id.get(node_id)
            if entry is None or entry[2] != content_digest or entry[3] != input_digest:
                raise ValueError('published_lexical_source_mismatch')
            selected.append(entry[0])
        if len(selected) != len(set(selected)):
            raise ValueError('published_lexical_duplicate_population')
        if selected != list(range(total)):
            # Unusual document/node filters retain exact scope semantics. They
            # decode only that population's saved counts, not full originals.
            def corpus():
                for start in range(0,len(selected),COUNTS_BATCH):
                    positions = selected[start:start+COUNTS_BATCH]
                    placeholders = ','.join('?' for _ in positions)
                    saved = {position:(length,value) for position,length,value in db.execute(
                        f'SELECT position,length,counts FROM nodes WHERE position IN ({placeholders})',positions)}
                    if len(saved)!=len(positions):
                        raise ValueError('published_lexical_population_changed')
                    for position in positions:
                        length,value = saved[position]
                        yield TokenCounts(length,_unpack(value))
            statistics = population_cache.get(key) if population_cache is not None else None
            if statistics is None:
                index = _QueryBM25(corpus(), query)
                if population_cache is not None:
                    if key != _population_key(path, identities):
                        raise ValueError('published_lexical_changed_during_query')
                    population_cache.put(key, index)
                return _scores(index, query)
        else:
            statistics = _unpack(db.execute("SELECT value FROM metadata WHERE key='statistics'").fetchone()[0])
        # For a warmed subset use the same global term postings, selecting only
        # its positions and retaining subset IDF. Never substitute global IDF.
        positions = set(selected)
        matched = {}
        for term in dict.fromkeys(query):
            for (packed,) in db.execute('SELECT value FROM postings WHERE term=? ORDER BY shard', (term,)):
                for position, count in PAIR.iter_unpack(zlib.decompress(packed)):
                    if position >= total or count < 1 or term in matched.get(position, {}):
                        raise ValueError('published_lexical_invalid_posting')
                    if position in positions:
                        matched.setdefault(position, {})[term] = count
        lengths = {entry[0]:entry[4] for entry in entries}
        corpus = (TokenCounts(lengths[position], matched.get(position, {})) for position in selected)
        result = _scores(_QueryBM25(corpus, query, statistics), query)
        if population_cache is not None and key != _population_key(path, identities):
            raise ValueError('published_lexical_changed_during_query')
        return result
