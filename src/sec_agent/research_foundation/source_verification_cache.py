"""Host-owned verification receipts for immutable source projections.

SQLite triggers record changes to original bytes, parsed pages and capture
metadata in the writer's transaction. Receipts contain no grant, execution ID,
URL or document body. Java and local access are checked by each caller.
Missing/modified instrumentation disables reuse; it never licenses stale data.
"""
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import zlib


FORMAT = 'organization-source-verification.v1'
TABLES = {'attachments': 'id', 'attachment_origins': 'object_id',
          'attachment_captures': 'object_id'}


def trigger_definitions():
    result = {}
    for table, column in TABLES.items():
        for event in ('INSERT', 'UPDATE', 'DELETE'):
            name = f'source_revision_{table}_{event.lower()}'
            refs = ['NEW'] if event == 'INSERT' else ['OLD'] if event == 'DELETE' else ['OLD', 'NEW']
            statements = ' '.join(
                f'INSERT INTO source_content_revisions VALUES({ref}.{column},lower(hex(randomblob(16)))) '
                'ON CONFLICT(object_id) DO UPDATE SET token=excluded.token;' for ref in refs)
            result[name] = f'CREATE TRIGGER {name} AFTER {event} ON {table} BEGIN {statements} END'
    return result


def install(db):
    # Runs inside the normal store migration transaction, before any writes.
    previous = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'"))
    db.execute('CREATE TABLE IF NOT EXISTS attachment_captures(object_id TEXT PRIMARY KEY,snapshot TEXT NOT NULL,note TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS source_content_revisions(object_id TEXT PRIMARY KEY,token TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS source_store_identity(singleton INTEGER PRIMARY KEY CHECK(singleton=1),identity TEXT NOT NULL)')
    db.execute('INSERT OR IGNORE INTO source_store_identity VALUES(1,lower(hex(randomblob(16))))')
    if any(previous.get(name) != sql for name, sql in trigger_definitions().items()):
        # Reinstalling lost instrumentation cannot make old tokens trustworthy.
        db.execute('UPDATE source_store_identity SET identity=lower(hex(randomblob(16))) WHERE singleton=1')
    for sql in trigger_definitions().values():
        db.execute(sql.replace('CREATE TRIGGER ', 'CREATE TRIGGER IF NOT EXISTS ', 1))
    db.execute('INSERT OR IGNORE INTO source_content_revisions SELECT id,lower(hex(randomblob(16))) FROM attachments')


def versions(observer):
    """One consistent read snapshot, small tokens only. None means full verify."""
    db = observer.db
    db.execute('BEGIN')
    try:
        actual = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'"))
        if any(actual.get(name) != sql for name, sql in trigger_definitions().items()):
            return None
        identity = db.execute('SELECT identity FROM source_store_identity WHERE singleton=1').fetchone()
        if not identity:
            return None
        stat = observer.path.stat()
        return {'store': [str(observer.path), stat.st_dev, stat.st_ino, identity[0]],
                'tokens': dict(db.execute('SELECT object_id,token FROM source_content_revisions'))}
    except sqlite3.Error:
        return None
    finally:
        db.execute('ROLLBACK')


def implementation_digest():
    # A stale receipt cannot bypass changed projection/cutoff/metadata rules.
    root = Path(__file__).parent
    files = [root/name for name in ('source_verification_cache.py', 'organization_candidate_index.py',
        'organization_source_projection.py', 'organization_source_filter.py', 'sec_cover_metadata.py', 'organization_graph_index.py',
        'organization_execution_access.py', 'project_source_captures.py', 'asset_workspace.py',
        'task_attachments.py', 'project_asset_versions.py', 'project_asset_access.py', 'prepared_source_metadata.py')]
    files.append(root.parents[1]/'retrieval'/'library_source_bundle.py')
    files.append(root.parents[1]/'retrieval'/'source_structure.py')
    files.append(root.parents[1]/'retrieval'/'source_coordinates.py')
    files.append(root.parents[1]/'retrieval'/'table_dependencies.py')
    files.append(root.parents[1]/'retrieval'/'table_captions.py')
    files.append(root.parents[1]/'retrieval'/'table_completion.py')
    files.append(root.parents[1]/'retrieval'/'source_table_periods.py')
    files.append(root.parents[1]/'retrieval'/'source_table_storage.py')
    files.append(root.parents[1]/'retrieval'/'fact_period_matching.py')
    files.append(root.parents[1]/'retrieval'/'financial_query_needs.py')
    files.append(root.parents[1]/'retrieval'/'filing_document_identity.py')
    files.append(root.parents[1]/'retrieval'/'source_window_candidates.py')
    files.append(root.parents[1]/'retrieval'/'source_window_selection.py')
    files.append(root.parents[1]/'retrieval'/'source_structure_selection.py')
    files.append(root.parents[1]/'retrieval'/'rerank_document_context.py')
    files.append(root.parents[1]/'retrieval'/'evidence_scope.py')
    files.append(root.parents[1]/'retrieval'/'business_scope_attributes.py')
    files.append(root.parents[1]/'retrieval'/'catalog_company_identity.py')
    return sha256(b''.join(path.read_bytes() for path in files)).hexdigest()


class SourceVerificationCache:
    def __init__(self, root):
        self.path = Path(root)/'source-verification.sqlite'
        self.code = implementation_digest()
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS receipts(key TEXT PRIMARY KEY,payload TEXT NOT NULL,digest TEXT NOT NULL)')

    def key(self, version, item, manifest):
        from .organization_hybrid_retrieval import digest
        token = version['tokens'].get(item['ref']['version_id']) if version else None
        if token is None:
            return None
        return digest({'format': FORMAT, 'code': self.code, 'store': version['store'], 'token': token,
                       'item': item, 'organization_id': manifest['organization_id'],
                       'research_as_of': manifest['research_as_of'], 'index': manifest['retrieval_index']})

    def get(self, key):
        if key is None:
            return None
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            row = db.execute('SELECT payload,digest FROM receipts WHERE key=?', (key,)).fetchone()
        if row is None:
            return None
        raw = zlib.decompress(row[0]) if isinstance(row[0], bytes) else row[0].encode()
        if sha256(raw).hexdigest() != row[1]:
            raise ValueError('organization_source_receipt_corrupt')
        return json.loads(raw)

    def put(self, key, value):
        if key is None:
            return
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute('INSERT OR IGNORE INTO receipts VALUES(?,?,?)', (key, zlib.compress(raw, 1), sha256(raw).hexdigest()))
            # Bounded FIFO metadata cache. Eviction only loses an optimization:
            # an evicted source must pass full validation before reuse.
            db.execute('DELETE FROM receipts WHERE rowid IN '
                       '(SELECT rowid FROM receipts ORDER BY rowid DESC LIMIT -1 OFFSET 8192)')


class PendingSourceReceipts:
    """Disk spool, never a readable verification cache before the final checks.

    Retain at most one expanded source receipt. TemporaryFile removes abandoned
    spools on close/process exit; neither a cancelled nor revoked generation can
    reuse this data as a proof. Persistent receipts remain digest-checked.
    """
    def __enter__(self):
        self.stream = tempfile.TemporaryFile(mode='w+b')
        return self

    def append(self, entry):
        if entry[0] is None:
            return
        raw = json.dumps(entry, ensure_ascii=False, separators=(',', ':')).encode()
        blob = zlib.compress(raw, 1)
        self.stream.write(struct.pack('<Q', len(blob)))
        self.stream.write(blob)

    def __iter__(self):
        self.stream.seek(0)
        while header := self.stream.read(8):
            if len(header) != 8:
                raise ValueError('source_receipt_spool_truncated')
            size, = struct.unpack('<Q', header)
            blob = self.stream.read(size)
            if len(blob) != size:
                raise ValueError('source_receipt_spool_truncated')
            yield json.loads(zlib.decompress(blob))

    def __exit__(self, *_):
        self.stream.close()
