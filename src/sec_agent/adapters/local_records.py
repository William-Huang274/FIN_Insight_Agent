"""Thin SQLite adapter for local submission/provider records and source reuse.

SQLite owns transactions and locking; JSON owns the new data format. Legacy
DiskCache is imported once, atomically, without importing that package or allowing
pickle object construction. Stop old writers before upgrading or rolling back.
Original cache.db and external values are retained; failed imports admit no work.
"""
from __future__ import annotations

import base64
import io
import json
import math
from pathlib import Path
import pickle
import pickletools
import sqlite3
import time


MAX_VALUE_BYTES = 64 * 1024 * 1024


def _pack(value):
    if value is None or type(value) in (str, bool, int):
        return ["scalar", value]
    if type(value) is float and math.isfinite(value):
        return ["scalar", value]
    if type(value) is bytes:
        return ["bytes", base64.b64encode(value).decode("ascii")]
    if type(value) is list:
        return ["list", [_pack(item) for item in value]]
    if type(value) is dict and all(type(key) is str for key in value):
        return ["dict", {key: _pack(item) for key, item in value.items()}]
    raise ValueError("unsupported_local_record_type")


def _unpack(value):
    kind, body = value
    if kind == "scalar":
        return body
    if kind == "bytes":
        return base64.b64decode(body, validate=True)
    if kind == "list":
        return [_unpack(item) for item in body]
    if kind == "dict":
        return {key: _unpack(item) for key, item in body.items()}
    raise ValueError("invalid_local_record_type")


class _PrimitiveUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        raise ValueError("legacy_object_construction_forbidden")

    def persistent_load(self, pid):
        raise ValueError("legacy_persistent_reference_forbidden")


def _legacy_value(root, mode, filename, value):
    if filename is not None:
        path = (root / filename).resolve()
        if not path.is_relative_to(root) or path.stat().st_size > MAX_VALUE_BYTES:
            raise ValueError("legacy_value_path_or_size_invalid")
        value = path.read_bytes()
    if isinstance(value, (bytes, str)) and len(value) > MAX_VALUE_BYTES:
        raise ValueError("legacy_value_too_large")
    if mode == 4:
        forbidden = {"GLOBAL", "STACK_GLOBAL", "REDUCE", "BUILD", "INST", "OBJ",
                     "NEWOBJ", "NEWOBJ_EX", "EXT1", "EXT2", "EXT4", "PERSID", "BINPERSID"}
        if any(op.name in forbidden for op, _, _ in pickletools.genops(value)):
            raise ValueError("legacy_object_construction_forbidden")
        stream = io.BytesIO(value)
        value = _PrimitiveUnpickler(stream).load()
        if stream.read():
            raise ValueError("legacy_trailing_payload")
    elif mode == 3:
        value = value.decode("utf-8")
    elif mode not in (1, 2):
        raise ValueError("legacy_storage_mode_invalid")
    return value


class LocalRecords:
    def __init__(self, directory, *, size_limit=None):
        self.root = Path(directory).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.size_limit = size_limit
        self.db = sqlite3.connect(self.root / "records-v1.sqlite", timeout=60)
        try:
            self.db.execute("PRAGMA trusted_schema=OFF")
            self.db.execute("CREATE TABLE IF NOT EXISTS records (key TEXT PRIMARY KEY, value TEXT NOT NULL, expires REAL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            self._import_legacy()
        except BaseException:
            self.db.close()
            raise

    def _import_legacy(self):
        self.db.execute("BEGIN IMMEDIATE")
        legacy = None
        try:
            if self.db.execute("SELECT 1 FROM metadata WHERE key='legacy_import'").fetchone():
                self.db.commit()
                return
            old = self.root / "cache.db"
            if old.exists():
                # mode=rw prevents accidentally creating an empty legacy DB.
                legacy = sqlite3.connect(old.as_uri() + "?mode=rw", uri=True, timeout=60)
                legacy.execute("PRAGMA trusted_schema=OFF")
                legacy.execute("BEGIN IMMEDIATE")
                for key, raw, expires, mode, filename, value in legacy.execute(
                    "SELECT key, raw, expire_time, mode, filename, value FROM Cache"
                ):
                    if raw != 1 or type(key) is not str:
                        raise ValueError("legacy_key_invalid")
                    encoded = json.dumps(_pack(_legacy_value(self.root, mode, filename, value)),
                                         ensure_ascii=False, allow_nan=False)
                    self.db.execute("INSERT INTO records VALUES (?, ?, ?)", (key, encoded, expires))
            self.db.execute("INSERT INTO metadata VALUES ('legacy_import', 'complete')")
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        finally:
            if legacy is not None:
                legacy.rollback()
                legacy.close()

    def get(self, key, default=None):
        row = self.db.execute("SELECT value FROM records WHERE key=? AND (expires IS NULL OR expires>?)",
                              (key, time.time())).fetchone()
        return _unpack(json.loads(row[0])) if row else default

    def __getitem__(self, key):
        missing = object()
        value = self.get(key, missing)
        if value is missing:
            raise KeyError(key)
        return value

    def _write(self, key, value, expire, *, add):
        encoded = json.dumps(_pack(value), ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > MAX_VALUE_BYTES:
            raise ValueError("local_record_too_large")
        now = time.time()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("DELETE FROM records WHERE expires<=?", (now,))
            sql = "INSERT OR IGNORE" if add else "INSERT OR REPLACE"
            changed = self.db.execute(sql + " INTO records VALUES (?, ?, ?)",
                                      (key, encoded, now + expire if expire else None)).rowcount > 0
            # Only disposable source text receives a size bound. Never evict
            # submission receipts, unknown provider calls, or paid vectors.
            if self.size_limit is not None:
                while self.db.execute("SELECT coalesce(sum(length(CAST(value AS BLOB))),0) FROM records").fetchone()[0] > self.size_limit:
                    self.db.execute("DELETE FROM records WHERE key=(SELECT key FROM records ORDER BY expires, rowid LIMIT 1)")
            self.db.commit()
            return changed
        except BaseException:
            self.db.rollback()
            raise

    def add(self, key, value):
        return self._write(key, value, None, add=True)

    def set(self, key, value, *, expire=None):
        return self._write(key, value, expire, add=False)

    def __setitem__(self, key, value):
        self.set(key, value)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.db.close()
