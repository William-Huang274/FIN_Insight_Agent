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

from .query_bm25 import TokenCounts, _QueryBM25, _scores, lexical_document, lexical_scores


FORMAT = 'published-bm25-postings.v1'
PAIR = struct.Struct('<QQ')
SHARD_BYTES = 8 * 1024 * 1024


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


def scores_from_identities(path, identities, query):
    """Score already verified (node ID, body SHA, lexical input SHA) identities.

    This lower-level entry does not prove originals or permissions. Published
    artifact integrity and the supplied scope must be verified by its caller.
    """
    query = tuple(query)
    uri = Path(path).resolve().as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True)) as db:
        if db.execute("SELECT value FROM metadata WHERE key='format'").fetchone() != (FORMAT.encode(),):
            raise ValueError('published_lexical_format_mismatch')
        entries = db.execute('SELECT position,node_id,content_digest,lexical_digest,length FROM nodes ORDER BY position').fetchall()
        by_id = {entry[1]: entry for entry in entries}
        selected = []
        for node_id, content_digest, input_digest in identities:
            entry = by_id.get(node_id)
            if entry is None or entry[2] != content_digest or entry[3] != input_digest:
                raise ValueError('published_lexical_source_mismatch')
            selected.append(entry[0])
        if len(selected) != len(set(selected)):
            raise ValueError('published_lexical_duplicate_population')
        if selected != list(range(len(entries))):
            # Unusual document/node filters retain exact scope semantics. They
            # decode only that population's saved counts, not full originals.
            def corpus():
                for position in selected:
                    length, value = db.execute('SELECT length,counts FROM nodes WHERE position=?', (position,)).fetchone()
                    yield TokenCounts(length, _unpack(value))
            return lexical_scores(corpus(), query)
        statistics = _unpack(db.execute("SELECT value FROM metadata WHERE key='statistics'").fetchone()[0])
        matched = {}
        for term in dict.fromkeys(query):
            for (packed,) in db.execute('SELECT value FROM postings WHERE term=? ORDER BY shard', (term,)):
                for position, count in PAIR.iter_unpack(zlib.decompress(packed)):
                    if position >= len(entries) or count < 1 or term in matched.get(position, {}):
                        raise ValueError('published_lexical_invalid_posting')
                    matched.setdefault(position, {})[term] = count
        corpus = (TokenCounts(entry[4], matched.get(entry[0], {})) for entry in entries)
        return _scores(_QueryBM25(corpus, query, statistics), query)
