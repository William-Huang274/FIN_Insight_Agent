"""Immutable payload sharing through LangGraph's serializer extension point.

The upstream saver still owns checkpoint order, pending writes and recovery.
Objects commit before a checkpoint can reference them. An interrupted write may
leave an unreferenced object, never a committed pointer to uncommitted content.
No automatic garbage collection: other replay databases may share these objects.
"""
from contextlib import asynccontextmanager
from hashlib import sha256
from pathlib import Path
import sqlite3
import threading
import zlib

import aiosqlite
import ormsgpack
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


class ObjectSerializer:
    kind = 'fin.checkpoint.objects.v1'

    def __init__(self, path, *, inline_bytes=2048):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('PRAGMA synchronous=FULL')
        self.conn.execute('CREATE TABLE IF NOT EXISTS objects (digest TEXT PRIMARY KEY, payload BLOB NOT NULL)')
        self.conn.commit()
        self.lock = threading.RLock()
        self.base = JsonPlusSerializer()
        self.inline_bytes = inline_bytes

    def close(self):
        with self.lock:
            self.conn.close()

    def _put(self, node, *, force=False):
        raw = ormsgpack.packb(node)
        if not force and len(raw) < self.inline_bytes:
            return node
        digest = sha256(raw).hexdigest()
        if self.conn.execute('SELECT 1 FROM objects WHERE digest=?', (digest,)).fetchone() is None:
            self.conn.execute('INSERT OR IGNORE INTO objects VALUES (?, ?)', (digest, zlib.compress(raw)))
        return ['ref', digest]

    def _freeze(self, value):
        # Keep business identity/content untouched. Native serialization remains
        # responsible for messages, decimals, dataclasses and all other leaves.
        if type(value) is dict:
            node = ['dict', [[self._freeze(k), self._freeze(v)] for k, v in value.items()]]
        elif type(value) in (list, tuple):
            node = ['tuple' if type(value) is tuple else 'list', [self._freeze(v) for v in value]]
        else:
            kind, data = self.base.dumps_typed(value)
            node = ['leaf', kind, data]
        return self._put(node)

    def dumps_typed(self, value):
        with self.lock, self.conn:
            root = self._put(self._freeze(value), force=True)
        return self.kind, root[1].encode('ascii')

    def _thaw(self, node):
        tag = node[0]
        if tag == 'ref':
            row = self.conn.execute('SELECT payload FROM objects WHERE digest=?', (node[1],)).fetchone()
            if row is None:
                raise ValueError('checkpoint_object_missing:' + node[1])
            raw = zlib.decompress(row[0])
            if sha256(raw).hexdigest() != node[1]:
                raise ValueError('checkpoint_object_digest_mismatch:' + node[1])
            return self._thaw(ormsgpack.unpackb(raw))
        if tag == 'leaf':
            return self.base.loads_typed((node[1], node[2]))
        if tag == 'dict':
            return {self._thaw(k): self._thaw(v) for k, v in node[1]}
        if tag in ('list', 'tuple'):
            values = [self._thaw(v) for v in node[1]]
            return tuple(values) if tag == 'tuple' else values
        raise ValueError('checkpoint_object_format_invalid')

    def loads_typed(self, value):
        if value[0] != self.kind:
            # Existing rows keep their native format and are not rewritten on
            # startup. Explicit offline migration is separate from recovery.
            return self.base.loads_typed(value)
        with self.lock:
            return self._thaw(['ref', value[1].decode('ascii')])


@asynccontextmanager
async def business_checkpointer(path, *, object_path):
    serializer = ObjectSerializer(object_path)
    try:
        async with aiosqlite.connect(str(path)) as conn:
            yield AsyncSqliteSaver(conn, serde=serializer)
    finally:
        serializer.close()
