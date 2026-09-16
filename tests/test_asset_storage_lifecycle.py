"""Persistent capacity, bounded directory reads, and recoverable cross-store identity."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import sqlite3
from uuid import uuid4

import pytest

from sec_agent.research_foundation.project_library import ProjectLibrary
from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
from sec_agent.research_foundation.project_asset_versions import document_versions
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.asset_set_backup import backup_asset_set, restore_asset_set
from sec_agent.research_foundation.project_asset_access import ProjectAssetUnavailable
from sec_agent.research_foundation.project_financial_facts import task_financial_snapshot
from test_project_financial_facts import mapped_task


def project_at(root):
    library=ProjectLibrary(root);project=str(uuid4())
    library.save('alice',0,{'projects':[{'id':project,'name':'Long-lived project'}],'assignments':{},'pinned':[]})
    return library,project,library.scope('alice',project)


def test_repeated_edits_quota_and_task_limit_are_separate(tmp_path,monkeypatch):
    monkeypatch.setenv('FINSIGHT_PROJECT_MAX_VERSIONS','32')
    library,project,scope=project_at(tmp_path/'project')
    old=library.documents.add(scope,'Note.md','原始内容'.encode());latest=old
    for i in range(30):
        latest=library.documents.add(scope,'Note.md',f'更新 {i}'.encode(),
            revision={'parent':latest['document_id'],'change_kind':'correction','note':''})
    assert document_versions(library.documents,scope)[-1]['version_info']['sequence']==31
    def insert(i):
        try:library.documents.add(scope,f'{i}.txt',b'concurrent');return True
        except ValueError:return False
    with ThreadPoolExecutor(4) as pool:assert sum(pool.map(insert,range(4)))==1
    assert library.usage('alice',project)['versions']==32
    assert library.documents.get(scope,old['document_id'])['body']=='原始内容'.encode()
    tasks=TaskAttachmentStore(tmp_path/'tasks');thread=str(uuid4())
    for i in range(12):tasks.add(thread,f'{i}.txt',b'content')
    with pytest.raises(ValueError,match='task_upload_limit'):tasks.add(thread,'13.txt',b'content')


def test_migration_light_directory_pagination_unicode_and_revocation(tmp_path,monkeypatch):
    library,project,scope=project_at(tmp_path/'project')
    for i in range(63):library.documents.add(scope,f'Note{i}.md',f'正文 {i} 留存率 STRAßE'.encode())
    # Simulate a pre-summary schema: migration must retain existing IDs and text.
    with library.documents.connect() as db:
        db.execute('DROP TRIGGER attachment_summary_insert');db.execute('DROP TABLE attachment_summaries')
        db.execute('DROP TABLE project_text_index');db.execute('DROP TABLE project_text_indexed')
    library=ProjectLibrary(tmp_path/'project')
    original_connect=library.documents.connect;queries=[]
    @contextmanager
    def traced():
        with original_connect() as db:
            db.set_trace_callback(queries.append);yield db
    monkeypatch.setattr(library.documents,'connect',traced)
    first=library.search('alice',project,limit=30)
    assert len(first['items'])==30 and first['next_offset']==30 and first['total']==63
    # Query trace proves browsing doesn't select source body or parsed pages.
    assert not any('pages' in q.lower() or 'length(body)' in q.lower() or 'select * from attachments' in q.lower() for q in queries)
    second=library.search('alice',project,offset=30,limit=30)
    assert set(r['document_id'] for r in first['items']).isdisjoint(r['document_id'] for r in second['items'])
    assert library.search('alice',project,offset=60,limit=30)['next_offset'] is None
    assert library.search('alice',project,'STRASSE')['total']==63
    assert library.search('alice',project,'留存率')['search_index']=='sqlite_fts5_trigram'
    assert library.search('alice',project,'留存')['total']==63
    assert library.search('alice',project,'" OR *')['total']==0
    revoked=first['items'][0]['document_id'];library.set_access('alice',project,'document',revoked,True)
    assert library.search('alice',project,'留存率')['total']==62
    listed=library.search('alice',project)['items'][0]
    assert listed['excerpt']=='' and listed['access_status']=='revoked'
    with pytest.raises(KeyError):library.search('bob',project)


def test_backup_rebinds_task_sources_and_recovered_revocation(tmp_path):
    library,project,scope=project_at(tmp_path/'source'/'project-library')
    doc=library.documents.add(scope,'Original.md',b'Original source')
    tasks=TaskAttachmentStore(tmp_path/'source'/'attachments');thread=str(uuid4())
    copied=tasks.copy_project_materials(thread,project,[library.documents.get(scope,doc['document_id'])])[0]
    backup=tmp_path/'backup';restored=tmp_path/'restored'
    public=tmp_path/'public.jsonl';public.write_text('{"original":"preserved"}\n')
    mart=tmp_path/'facts.sqlite'
    with sqlite3.connect(mart) as db:
        db.execute('CREATE TABLE observations(value TEXT)');db.execute("INSERT INTO observations VALUES('123.456')")
    manifest=backup_asset_set(library.documents.root,tasks.root,backup,public_library=public,financial_mart=mart)
    assert manifest['native_threads_included'] is False
    assert restore_asset_set(backup,restored)['automatic_resume'] is False
    assert (restored/'attachments'/'public-library'/'retrieval_nodes.jsonl').read_bytes()==public.read_bytes()
    with sqlite3.connect(restored/'library'/'financial-facts.sqlite') as db:
        assert db.execute('SELECT value FROM observations').fetchone()[0]=='123.456'
    # Original store no longer exists at its old path: restored task must stand alone.
    library.documents.root.rename(tmp_path/'original-project-offline')
    reopened=TaskAttachmentStore(restored/'attachments')
    assert reopened.get(thread,copied['document_id'])['body']==b'Original source'
    ProjectLibrary(restored/'project-library').set_access('alice',project,'document',doc['document_id'],True)
    with pytest.raises(ProjectAssetUnavailable):reopened.get(thread,copied['document_id'])
    with pytest.raises(FileExistsError):restore_asset_set(backup,restored)
    (backup/'attachments'/'attachments.sqlite').write_bytes(b'bad')
    with pytest.raises(ValueError,match='integrity'):restore_asset_set(backup,tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


def test_backup_restores_real_sec_mapping_and_rejects_missing_file(mapped_task,tmp_path):
    client,service,calls,tid,sec,project,version,request=mapped_task
    assert client.post('/api/v1/research-sessions',headers={'X-Workbench-Request':'1'},json=request).status_code==200
    expected=task_financial_snapshot(service.attachment_store.root,tid)[1]
    backup=tmp_path/'set';restore=tmp_path/'restored'
    backup_asset_set(sec.library.documents.root,service.attachment_store.root,backup)
    restore_asset_set(backup,restore)
    sec.library.documents.root.rename(tmp_path/'old-project')
    actual=task_financial_snapshot(restore/'attachments',tid)
    assert actual[1]==expected and actual[0].is_relative_to(restore)
    assert not any(c[0]=='run' for c in calls)
    manifest=json.loads((backup/'manifest.json').read_text())
    del manifest['files'][f'attachments/financial-snapshots/{tid}/facts.sqlite']
    (backup/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='task_file_missing'):restore_asset_set(backup,tmp_path/'missing')
    assert not (tmp_path/'missing').exists()


def test_corrupt_original_or_wrong_project_binding_cannot_publish_backup(tmp_path):
    library,project,scope=project_at(tmp_path/'project')
    doc=library.documents.add(scope,'Original.txt',b'original')
    tasks=TaskAttachmentStore(tmp_path/'tasks');thread=str(uuid4())
    tasks.copy_project_materials(thread,project,[library.documents.get(scope,doc['document_id'])])
    with library.documents.connect() as db:
        db.execute('UPDATE attachments SET body=? WHERE id=?',(b'changed',doc['document_id']))
    with pytest.raises(ValueError,match='original_integrity'):
        backup_asset_set(library.documents.root,tasks.root,tmp_path/'corrupt')
    assert not (tmp_path/'corrupt'/'manifest.json').exists()
    with tasks.connect() as db:db.execute('UPDATE task_project_stores SET path=?',(str(tmp_path/'unknown.sqlite'),))
    with pytest.raises(ValueError,match='external_project_binding'):
        backup_asset_set(library.documents.root,tasks.root,tmp_path/'wrong-binding')
    assert not (tmp_path/'wrong-binding'/'manifest.json').exists()
