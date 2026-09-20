"""Historical citation downloads preserve bytes, ownership and revocation."""
import asyncio
from contextlib import closing
from hashlib import sha256
import sqlite3
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from apps.workbench.backend.attachment_archive import AttachmentArchive
from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
from test_research_session_bff import _app


def legacy_store(root, thread):
    root.mkdir()
    path = root / 'attachments.sqlite'
    body = b'%PDF-1.7\narchived-original'
    document = 'UPLOAD::' + uuid4().hex
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('CREATE TABLE attachments(thread TEXT,id TEXT PRIMARY KEY,name TEXT,kind TEXT,body BLOB,pages TEXT,digest TEXT)')
        db.execute('INSERT INTO attachments VALUES(?,?,?,?,?,?,?)',
                   (thread, document, 'original.pdf', 'pdf', body, '[]', sha256(body).hexdigest()))
    return path, document, body


def revoke(store, thread, document):
    with store.connect() as db:
        db.execute('CREATE TABLE project_asset_access(scope TEXT,kind TEXT,asset TEXT,revoked INTEGER)')
        db.execute('INSERT INTO project_asset_access VALUES(?,?,?,1)', (thread, 'document', document))


def test_legacy_download_is_read_only_and_does_not_expand_inputs(tmp_path):
    app, service, calls, thread = _app()
    path, document, body = legacy_store(tmp_path / 'archive', thread)
    before = path.read_bytes()
    service.attachment_store = TaskAttachmentStore(tmp_path / 'active')
    service.attachment_archives = (AttachmentArchive(path.parent),)
    route = f'/api/v1/research-sessions/{thread}/attachments'
    with TestClient(app) as client:
        response = client.get(route + '/' + document)
        assert response.status_code == 200 and response.content == body
        assert response.headers['cache-control'] == 'no-store'
        assert "original.pdf" in response.headers['content-disposition']
        assert client.get(route).json() == []
        assert client.get(f'/api/v1/research-sessions/{uuid4()}/attachments/{document}').status_code == 404
        assert client.get(route + '/UPLOAD::' + uuid4().hex).status_code == 404
        async def other_owner(_):
            return {'metadata': {'surface': 'research_workbench', 'owner_id': 'someone-else'}}
        service.sdk.threads.get = other_owner
        assert client.get(route + '/' + document).status_code == 404
    assert path.read_bytes() == before
    assert not calls
    asyncio.run(service.http.aclose())


@pytest.mark.parametrize('failure', ['archive_revoked', 'active_revoked', 'active_corrupt', 'archive_corrupt', 'archive_offline'])
def test_download_never_bypasses_revocation_or_integrity_failures(tmp_path, failure):
    app, service, _, thread = _app()
    path, document, body = legacy_store(tmp_path / 'archive', thread)
    store = service.attachment_store = TaskAttachmentStore(tmp_path / 'active')
    service.attachment_archives = (AttachmentArchive(path.parent),)
    if failure == 'active_revoked':
        revoke(store, thread, document)  # Tombstone, even without a local body.
    elif failure == 'archive_revoked':
        # Mutate the fixture, never the adapter being tested.
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('CREATE TABLE project_asset_access(scope TEXT,kind TEXT,asset TEXT,revoked INTEGER)')
            db.execute('INSERT INTO project_asset_access VALUES(?,?,?,1)', (thread, 'document', document))
    elif failure == 'active_corrupt':
        with store.connect() as db:
            db.execute('INSERT INTO attachments(thread,id,name,kind,body,pages,digest) VALUES(?,?,?,?,?,?,?)',
                       (thread, document, 'original.pdf', 'pdf', b'broken', '[]', sha256(body).hexdigest()))
    elif failure == 'archive_corrupt':
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('UPDATE attachments SET body=?', (b'broken',))
    else:
        path.rename(path.with_suffix('.offline'))
    with TestClient(app) as client:
        response = client.get(f'/api/v1/research-sessions/{thread}/attachments/{document}')
        assert response.status_code == 409
        assert str(tmp_path) not in response.text
    asyncio.run(service.http.aclose())
