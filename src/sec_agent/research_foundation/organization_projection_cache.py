"""Bounded disposable projections for new queries in one authorized session.

Only in-memory digests confer validity on these temporary files. No cache can
survive a navigation instance or a storage/grant generation change. SQLite's
live generation observer and current Java authority are owned by the caller.
"""
from collections.abc import Mapping
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3
import struct
from tempfile import TemporaryDirectory
from types import MappingProxyType
import weakref
import zlib


# Disposable, process-local format: JSON identities followed by binary bodies.
# Keep one outer compression stream so repeated metadata/body fragments still
# compress together. The cache verifies the entire encoded payload before decode.
_FRAME = struct.Struct('>5sI')
_MAGIC = b'OPRJ1'


def _metadata_from_json(encoded):
    # JSON memoizes object keys, but repeated document/source *values* become
    # separate strings for every chunk. Restore immutable sharing within this
    # one projection only; never intern globally or share mutable mappings.
    values = {}

    def share(row):
        for key, value in row.items():
            if isinstance(value, str):
                if len(values) < 4096:
                    row[key] = values.setdefault(value, value)
                else:
                    row[key] = values.get(value, value)
        return row

    return json.loads(encoded, object_hook=share)


def pack_terms(text):
    from collections import Counter
    from retrieval.text import tokenize
    tokens = tokenize(text)
    return zlib.compress(json.dumps([len(tokens), Counter(tokens)], ensure_ascii=False,
                                    separators=(',', ':')).encode('utf8'), 1)


def unpack_terms(encoded):
    from retrieval.query_bm25 import TokenCounts
    length, counts = json.loads(zlib.decompress(encoded))
    return TokenCounts(length, counts)


class _PackedNode(Mapping):
    def __init__(self, metadata, body, compressed, terms):
        self.metadata, self.body, self.compressed = metadata, body, compressed
        self._terms = terms

    def lexical_counts(self):
        if not self._terms:
            from collections import Counter
            from retrieval.query_bm25 import TokenCounts
            from retrieval.text import tokenize
            tokens = tokenize(str(self.get('model_text') or self['content'] or ''))
            return TokenCounts(len(tokens), Counter(tokens))
        return unpack_terms(self._terms)

    def __getitem__(self, key):
        if key == 'content':
            return (zlib.decompress(self.body) if self.compressed else self.body).decode('utf8')
        return self.metadata[key]

    def __iter__(self):
        yield from self.metadata
        yield 'content'

    def __len__(self):
        return len(self.metadata) + 1


def encode_projection(value, *, include_terms=True):
    from .organization_source_projection import _SourceNode
    document, nodes, origin, originals = value
    records, bodies, positions = [], [], {}
    for row in nodes:
        if isinstance(row, _SourceNode):
            metadata, body, compressed = dict(row._metadata), row._body, row._compressed
            kind = row._kind
        else:
            metadata = {k: v for k, v in row.items() if k != 'content'}
            body, compressed, kind = zlib.compress(row['content'].encode('utf8'), 1), True, 'plain'
        model_text = metadata.get('model_text')
        key = (body, compressed, model_text)
        position = positions.get(key)
        if position is None:
            position = len(bodies)
            positions[key] = position
            terms = pack_terms(str(model_text or row['content'] or '')) if include_terms else b''
            bodies.append((body, compressed, terms))
        else:
            terms = bodies[position][2]
        if isinstance(row, _SourceNode):
            row._terms = terms or None
        # Compact section/leaf pairs share the same metadata and bytes. Retain
        # that layout instead of rebuilding a corpus-sized decoded string heap.
        if (kind == 'text' and records and records[-1][0] == 'section'
                and records[-1][1] == metadata and records[-1][2] == position):
            records[-1][0] = 'pair'
        else:
            records.append([kind, metadata, position])
    # Complete sources repeat each node's original_source in a separate lookup.
    # Store only exceptional entries; reconstruct the exact lookup from nodes.
    reconstructed = {row['node_id']: row['original_source'] for row in nodes
                     if 'original_source' in row}
    remaining = {key: value for key, value in originals.items()
                 if key not in reconstructed or reconstructed[key] != value}
    original_keys = list(originals)
    descriptors = [(len(body), compressed, len(terms)) for body, compressed, terms in bodies]
    metadata = json.dumps([document, records, origin, remaining, descriptors, original_keys],
                          ensure_ascii=False, separators=(',', ':')).encode('utf8')
    raw = b''.join([_FRAME.pack(_MAGIC, len(metadata)), metadata,
                    *(part for body, _, terms in bodies for part in (body, terms))])
    return zlib.compress(raw, 1), len(raw)


def decode_projection(encoded):
    from .organization_source_projection import _SourceNode
    raw = zlib.decompress(encoded)
    if len(raw) < _FRAME.size:
        raise ValueError('organization_projection_cache_invalid_frame')
    magic, length = _FRAME.unpack_from(raw)
    offset = _FRAME.size + length
    if magic != _MAGIC or offset > len(raw):
        raise ValueError('organization_projection_cache_invalid_frame')
    document, records, origin, remaining, descriptors, original_keys = _metadata_from_json(raw[_FRAME.size:offset])
    bodies = []
    for body_size, compressed, terms_size in descriptors:
        if (type(body_size) is not int or type(terms_size) is not int
                or type(compressed) is not bool or min(body_size, terms_size) < 0
                or offset + body_size + terms_size > len(raw)):
            raise ValueError('organization_projection_cache_invalid_frame')
        body_end = offset + body_size
        end = body_end + terms_size
        bodies.append((raw[offset:body_end], compressed, raw[body_end:end]))
        offset = end
    if offset != len(raw):
        raise ValueError('organization_projection_cache_invalid_frame')
    nodes = []
    for kind, metadata, position in records:
        if type(position) is not int or not 0 <= position < len(bodies):
            raise ValueError('organization_projection_cache_invalid_frame')
        body, compressed, terms = bodies[position]
        metadata = MappingProxyType(metadata)
        if kind == 'plain':
            nodes.append(_PackedNode(metadata, body, compressed, terms))
        else:
            for part in (('section', 'text') if kind == 'pair' else (kind,)):
                nodes.append(_SourceNode(metadata, body, compressed, part, terms or None))
    reconstructed = {row['node_id']: row['original_source'] for row in nodes
                     if 'original_source' in row}
    originals = {key: remaining[key] if key in remaining else reconstructed[key] for key in original_keys}
    return document, nodes, origin, originals


def _close_store(db, directory):
    try:
        db.close()
    finally:
        directory.cleanup()


class OrganizationProjectionCache:
    LIMIT = 256 * 1024 * 1024
    MAX_ITEM = 32 * 1024 * 1024
    MAX_DECODED_ITEM = 128 * 1024 * 1024

    def __init__(self, root, *, limit=LIMIT, include_terms=True):
        self.include_terms = include_terms
        self.root, self.limit = Path(root), limit
        self.directory = None
        self.generation = None
        self.entries = {}
        self.size = 0
        self.hits = 0
        self.admission_disabled = False
        self.db = None
        self._cleanup = None
        from retrieval.query_bm25 import LexicalStatisticsCache
        self.lexical_statistics = LexicalStatisticsCache(postings_limit=64 * 1024 * 1024)

    @property
    def path(self):
        return Path(self.directory.name)/'projection.sqlite' if self.directory else None

    def reset(self, generation):
        if self.generation != generation:
            if self._cleanup is not None:
                self._cleanup()
            elif self.directory is not None:
                self.directory.cleanup()
            self.db = self._cleanup = None
            self.directory, self.entries, self.size = None, {}, 0
            self.generation = generation
            self.admission_disabled = False
            self.lexical_statistics.clear()
        self.hits = 0

    def get(self, resource_id):
        record = self.entries.get(resource_id)
        if record is None:
            return None
        key, expected, size = record
        try:
            row = self.db.execute(
                'SELECT CASE WHEN length(payload)=? THEN payload ELSE NULL END '
                'FROM projections WHERE resource_id=?', (size, key)).fetchone()
        except sqlite3.Error as exc:
            raise ValueError('organization_projection_cache_integrity_failure') from exc
        if row is None:
            self.entries.pop(resource_id)
            self.size -= size
            return None
        encoded = row[0]
        if not isinstance(encoded, bytes) or len(encoded) != size or sha256(encoded).hexdigest() != expected:
            raise ValueError('organization_projection_cache_integrity_failure')
        result = decode_projection(encoded)
        self.hits += 1
        return result

    def put(self, resource_id, value):
        if self.admission_disabled or resource_id in self.entries or self.size >= self.limit:
            return
        encoded, raw_size = encode_projection(value, include_terms=self.include_terms)
        if (len(encoded) > self.MAX_ITEM or raw_size > self.MAX_DECODED_ITEM
                or self.size + len(encoded) > self.limit):
            return  # Oversized sources use ordinary authorized storage reads.
        try:
            if self.directory is None:
                self.root.mkdir(parents=True, exist_ok=True)
                self.directory = TemporaryDirectory(prefix='projection-', dir=self.root)
                self.db = sqlite3.connect(self.path, timeout=3, check_same_thread=False)
                self._cleanup = weakref.finalize(self, _close_store, self.db, self.directory)
                # Bounded SQLite page cache, no memory mapping of the corpus.
                # This is a disposable per-instance store, never a business DB.
                self.db.execute('PRAGMA cache_size=-2048')
                self.db.execute('PRAGMA mmap_size=0')
                self.db.execute('CREATE TABLE projections(resource_id TEXT PRIMARY KEY, payload BLOB NOT NULL)')
            # A disposable optimization must not exhaust the original store's
            # disk. Admission can stop; uncached sources keep the normal path.
            if shutil.disk_usage(self.root).free < len(encoded) + 128 * 1024 * 1024:
                self.admission_disabled = True
                return
            with self.db:
                self.db.execute('INSERT INTO projections VALUES (?,?)', (resource_id, encoded))
        except (OSError, sqlite3.Error):
            # No entry/digest is published for a failed or partial write.
            self.admission_disabled = True
            return
        self.entries[resource_id] = resource_id, sha256(encoded).hexdigest(), len(encoded)
        self.size += len(encoded)
