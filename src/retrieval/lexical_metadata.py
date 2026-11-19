"""Small derived SQLite projection for immutable published lexical files.

The release remains read-only. Large per-document counts stay there; this
projection contains only positional identities and lengths. The verified
release owner prepares it before serving queries. It never stores permissions.
"""
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from filelock import FileLock


def file_identity(path):
    path = Path(path).resolve()
    stat = path.stat()
    # DELETE-journal SQLite commits update this header immediately; Windows
    # file timestamps may stay unchanged while another connection is open.
    # Read 100 bytes, never hash/scan the complete release at query time.
    with path.open('rb') as stream:
        header = stream.read(100).hex()
    return (str(path), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, header)


class LexicalMetadata:
    def __init__(self, source, path):
        self.source, self.path = Path(source), Path(path)
        self.source_identity = file_identity(source)
        self.projection_identity = file_identity(path)

    def check(self):
        if (file_identity(self.source) != self.source_identity
                or file_identity(self.path) != self.projection_identity):
            raise ValueError('published_lexical_metadata_changed')


def prepare(source, cache_root):
    """Reuse a file-identity-bound projection; build only on a new release.

    Atomic publication plus an OS lock avoids partial readers and duplicate
    builds. Release integrity/current access are separately checked by owner.
    """
    source = Path(source).resolve()
    identity = file_identity(source)
    encoded = json.dumps(identity, separators=(',', ':'))
    root = Path(cache_root) / 'lexical-metadata'
    root.mkdir(parents=True, exist_ok=True)
    path = root / (sha256(encoded.encode()).hexdigest() + '.sqlite')
    with FileLock(str(path) + '.lock', timeout=60):
        if not path.exists():
            fd, temporary = tempfile.mkstemp(prefix=path.stem + '.', suffix='.tmp', dir=root)
            os.close(fd)
            try:
                with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original, closing(sqlite3.connect(temporary)) as target, target:
                    target.execute('CREATE TABLE identity(value TEXT NOT NULL)')
                    target.execute('INSERT INTO identity VALUES (?)', (encoded,))
                    target.execute('CREATE TABLE nodes(position INTEGER PRIMARY KEY,node_id TEXT UNIQUE NOT NULL,content_digest TEXT NOT NULL,lexical_digest TEXT NOT NULL,length INTEGER NOT NULL)')
                    target.executemany('INSERT INTO nodes VALUES (?,?,?,?,?)', original.execute(
                        'SELECT position,node_id,content_digest,lexical_digest,length FROM nodes ORDER BY position'))
                if file_identity(source) != identity:
                    raise ValueError('published_lexical_changed_during_metadata_build')
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
            if db.execute('SELECT value FROM identity').fetchone() != (encoded,):
                raise ValueError('published_lexical_metadata_identity_mismatch')
    result = LexicalMetadata(source, path)
    if result.source_identity != identity:
        raise ValueError('published_lexical_changed_during_metadata_prepare')
    return result
