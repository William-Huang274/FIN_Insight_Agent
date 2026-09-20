"""Read historical task originals without migrating or writing their stores.

Host configuration selects archives; browser requests never select filesystem
paths. This is a download adapter, not an additional research input catalog.
"""
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from uuid import UUID

from sec_agent.research_foundation.project_asset_access import (
    ProjectAssetUnavailable, access_state, origin_access, require_active,
)


class AttachmentArchive:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.path = self.root / 'attachments.sqlite'

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    def get(self, thread_id, document_id):
        scope = str(UUID(str(thread_id)))
        try:
            with self.connect() as db:
                row = db.execute('SELECT * FROM attachments WHERE thread=? AND id=?',
                                 (scope, document_id)).fetchone()
                if row is None:
                    raise ValueError('attachment_not_in_current_task')
                require_active(access_state(db, scope, 'document', document_id))
                # Original upload stores predate project provenance metadata.
                origin = db.execute('SELECT origin FROM attachment_origins WHERE object_id=?',
                                    (document_id,)).fetchone() if db.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='attachment_origins'").fetchone() else None
            provenance = json.loads(origin['origin']) if origin else None
            require_active(origin_access(self, scope, provenance))
            if sha256(row['body']).hexdigest() != row['digest']:
                raise ProjectAssetUnavailable('历史附件完整性校验失败，无法下载。')
            return dict(row)
        except (OSError, sqlite3.Error):
            raise ProjectAssetUnavailable('历史附件库暂不可读取，请检查存储连接。') from None


def read_attachment(primary_view, archives, thread_id, document_id):
    """Only a missing original may fall back; never bypass current revocation."""
    try:
        return primary_view.get(thread_id, document_id)
    except ValueError as exc:
        if str(exc) != 'attachment_not_in_current_task':
            raise
    # Current-store revocation can also be a tombstone without a retained body.
    with primary_view.connect() as db:
        require_active(access_state(db, str(thread_id), 'document', document_id))
    for archive in archives:
        try:
            return archive.get(thread_id, document_id)
        except ValueError as exc:
            if str(exc) != 'attachment_not_in_current_task':
                raise
    raise ValueError('attachment_not_in_current_task')
