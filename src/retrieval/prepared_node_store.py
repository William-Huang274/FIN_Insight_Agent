"""Bounded-memory staging of complete, authorized index input rows."""
from collections.abc import Sequence
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import zlib


class PreparedNodeStore(Sequence):
    """New SQLite store, readable only after the producer's final grant check."""
    def __init__(self, path):
        self.path = Path(path)
        with self.path.open('xb'):
            pass
        self.db = sqlite3.connect(self.path)
        self.db.execute('PRAGMA cache_size=-2048')
        self.db.execute('CREATE TABLE nodes(position INTEGER PRIMARY KEY, node_id TEXT UNIQUE NOT NULL, payload BLOB NOT NULL, digest TEXT NOT NULL)')
        self.count, self.sealed = 0, False

    def extend(self, rows):
        if self.sealed:
            raise ValueError('prepared_node_store_already_sealed')
        for row in rows:
            raw = json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
            self.db.execute('INSERT INTO nodes VALUES (?,?,?,?)',
                (self.count, row['node_id'], zlib.compress(raw, 1), sha256(raw).hexdigest()))
            self.count += 1

    def seal(self):
        self.db.commit()
        self.sealed = True

    def __len__(self):
        return self.count

    @staticmethod
    def _decode(row):
        raw = zlib.decompress(row[0])
        if sha256(raw).hexdigest() != row[1]:
            raise ValueError('prepared_node_store_row_changed')
        return json.loads(raw)

    def __iter__(self):
        if not self.sealed:
            raise ValueError('prepared_node_store_not_sealed')
        cursor = self.db.execute('SELECT payload,digest FROM nodes ORDER BY position')
        try:
            for row in cursor:
                yield self._decode(row)
        finally:
            cursor.close()

    def __getitem__(self, position):
        if not self.sealed:
            raise ValueError('prepared_node_store_not_sealed')
        if isinstance(position, slice):
            return [self[i] for i in range(*position.indices(self.count))]
        if position < 0:
            position += self.count
        if not 0 <= position < self.count:
            raise IndexError(position)
        row = self.db.execute('SELECT payload,digest FROM nodes WHERE position=?', (position,)).fetchone()
        if row is None:
            raise ValueError('prepared_node_store_row_missing')
        return self._decode(row)

    def close(self):
        self.db.close()
