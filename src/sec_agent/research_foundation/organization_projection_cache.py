"""Bounded disposable projections for new queries in one authorized session.

Only in-memory digests confer validity on these temporary files. No cache can
survive a navigation instance or a storage/grant generation change. SQLite's
live generation observer and current Java authority are owned by the caller.
"""
from base64 import b64encode, b64decode
from collections.abc import Mapping
from hashlib import sha256
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from types import MappingProxyType
import zlib


class _PackedNode(Mapping):
    def __init__(self, metadata, body, compressed):
        self.metadata, self.body, self.compressed = metadata, body, compressed

    def __getitem__(self, key):
        if key == 'content':
            return (zlib.decompress(self.body) if self.compressed else self.body).decode('utf8')
        return self.metadata[key]

    def __iter__(self):
        yield from self.metadata
        yield 'content'

    def __len__(self):
        return len(self.metadata) + 1


def encode_projection(value):
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
        key = (body, compressed)
        position = positions.get(key)
        if position is None:
            position = len(bodies)
            positions[key] = position
            bodies.append([b64encode(body).decode('ascii'), compressed])
        # Compact section/leaf pairs share the same metadata and bytes. Retain
        # that layout instead of rebuilding a corpus-sized decoded string heap.
        if (kind == 'text' and records and records[-1][0] == 'section'
                and records[-1][1] == metadata and records[-1][2] == position):
            records[-1][0] = 'pair'
        else:
            records.append([kind, metadata, position])
    raw = json.dumps([document, records, origin, originals, bodies], ensure_ascii=False,
                     separators=(',', ':')).encode('utf8')
    return zlib.compress(raw, 1), len(raw)


def decode_projection(encoded):
    from .organization_source_projection import _SourceNode
    document, records, origin, originals, bodies = json.loads(zlib.decompress(encoded))
    bodies = [(b64decode(body, validate=True), compressed) for body, compressed in bodies]
    nodes = []
    for kind, metadata, position in records:
        body, compressed = bodies[position]
        metadata = MappingProxyType(metadata)
        if kind == 'plain':
            nodes.append(_PackedNode(metadata, body, compressed))
        else:
            for part in (('section', 'text') if kind == 'pair' else (kind,)):
                nodes.append(_SourceNode(metadata, body, compressed, part))
    return document, nodes, origin, originals


class OrganizationProjectionCache:
    LIMIT = 256 * 1024 * 1024
    MAX_ITEM = 32 * 1024 * 1024
    MAX_DECODED_ITEM = 128 * 1024 * 1024

    def __init__(self, root, *, limit=LIMIT):
        self.root, self.limit = Path(root), limit
        self.directory = None
        self.generation = None
        self.entries = {}
        self.size = 0
        self.hits = 0
        self.admission_disabled = False

    def reset(self, generation):
        if self.generation != generation:
            if self.directory is not None:
                self.directory.cleanup()
            self.directory, self.entries, self.size = None, {}, 0
            self.generation = generation
            self.admission_disabled = False
        self.hits = 0

    def get(self, resource_id):
        record = self.entries.get(resource_id)
        if record is None:
            return None
        filename, expected, size = record
        path = Path(self.directory.name)/filename
        try:
            if path.stat().st_size != size:
                raise ValueError('organization_projection_cache_integrity_failure')
            encoded = path.read_bytes()
        except FileNotFoundError:
            self.entries.pop(resource_id)
            self.size -= size
            return None
        if sha256(encoded).hexdigest() != expected:
            raise ValueError('organization_projection_cache_integrity_failure')
        result = decode_projection(encoded)
        self.hits += 1
        return result

    def put(self, resource_id, value):
        if self.admission_disabled or resource_id in self.entries or self.size >= self.limit:
            return
        encoded, raw_size = encode_projection(value)
        if (len(encoded) > self.MAX_ITEM or raw_size > self.MAX_DECODED_ITEM
                or self.size + len(encoded) > self.limit):
            return  # Oversized sources use ordinary authorized storage reads.
        try:
            if self.directory is None:
                self.root.mkdir(parents=True, exist_ok=True)
                self.directory = TemporaryDirectory(prefix='projection-', dir=self.root)
            # A disposable optimization must not exhaust the original store's
            # disk. Admission can stop; uncached sources keep the normal path.
            if shutil.disk_usage(self.root).free < len(encoded) + 128 * 1024 * 1024:
                self.admission_disabled = True
                return
            filename = sha256(resource_id.encode()).hexdigest() + '.json.z'
            path = Path(self.directory.name)/filename
            path.write_bytes(encoded)
        except OSError:
            # No entry/digest is published for a failed or partial write.
            self.admission_disabled = True
            return
        self.entries[resource_id] = filename, sha256(encoded).hexdigest(), len(encoded)
        self.size += len(encoded)
