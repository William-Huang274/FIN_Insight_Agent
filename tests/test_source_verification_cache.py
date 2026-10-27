"""Real SQLite receipts; current Java authority is an explicit test double."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from test_organization_candidate_index import prepared, query
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.research_foundation.source_verification_cache import trigger_definitions


def test_restart_reuses_proofs_but_rechecks_current_authority(tmp_path, monkeypatch):
    nav, reader, state, directory, grant = prepared(tmp_path, monkeypatch)
    nav.warm_release()
    payload = tmp_path/'restart.json'
    payload.write_text(json.dumps({'root':str(reader.workspace.library.documents.root),
        'indices':str(tmp_path/'indices'), 'grant':state['grant']}))
    script = '''
import json, sys
from types import SimpleNamespace
from test_organization_execution_access import runtime_at
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
p=json.load(open(sys.argv[1]))
reader,state=runtime_at(SimpleNamespace(workspace=AssetWorkspace(p['root'])),p['grant'])
def no_originals(*args): raise AssertionError('restart reread original')
reader._read_storage=no_originals
nav=OrganizationSourceNavigation(reader,workbench_url='http://new-host',retrieval_root=p['indices'])
nav.warm_release()
assert nav._candidate_index.verification_hits==2
assert state['calls']>=2
state['status']=404
try: nav.warm_release()
except Exception: pass
else: raise AssertionError('revoked restart allowed')
print('cross_process_receipts_and_fresh_authority_passed')
'''
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'}
    root = Path(__file__).resolve().parents[1]
    env['PYTHONPATH'] = os.pathsep.join([*map(str, (root/'src', root/'tests', root)), os.environ.get('PYTHONPATH','')])
    child = subprocess.run([sys.executable, '-c', script, str(payload)], env=env,
                           capture_output=True, text=True, timeout=45)
    assert child.returncode == 0, child.stderr
    assert 'cross_process_receipts' in child.stdout


@pytest.mark.parametrize('table,column', [('attachments','id'), ('attachment_origins','object_id'),
                                         ('attachment_captures','object_id')])
def test_only_modified_source_revalidated_even_identical_write(tmp_path, monkeypatch, table, column):
    from test_organization_source_filter import scoped_fixture
    nav, reader, _, _, grant = scoped_fixture(tmp_path, monkeypatch)
    nav.warm_release()
    target = grant['manifest']['inputs'][1]
    field = {'attachments':'body', 'attachment_origins':'origin', 'attachment_captures':'note'}[table]
    with sqlite3.connect(reader.workspace.library.documents.path) as db:
        db.execute(f'UPDATE {table} SET {field}={field} WHERE {column}=?', (target['ref']['version_id'],))
    calls = []
    original = reader._read_storage
    def counted(*args):
        calls.append(args[0]); return original(*args)
    monkeypatch.setattr(reader, '_read_storage', counted)
    nav.navigate(query())
    assert calls == [target['resource_id']]
    assert nav._candidate_index.verification_hits == 3


def test_missing_trigger_forces_full_validation_and_catches_unjournaled_corruption(tmp_path, monkeypatch):
    nav, reader, _, _, grant = prepared(tmp_path, monkeypatch)
    nav.warm_release()
    with sqlite3.connect(reader.workspace.library.documents.path) as db:
        db.execute('DROP TRIGGER source_revision_attachments_update')
        db.execute('UPDATE attachments SET body=? WHERE id=?', (b'corrupt', grant['manifest']['inputs'][1]['ref']['version_id']))
    with pytest.raises(ValueError):
        nav.navigate(query())


def test_failed_transaction_does_not_invalidate_proof(tmp_path, monkeypatch):
    nav, reader, _, _, _ = prepared(tmp_path, monkeypatch)
    nav.warm_release()
    with sqlite3.connect(reader.workspace.library.documents.path) as db:
        db.execute('UPDATE attachments SET body=?', (b'rolled back',))
        db.rollback()
    new = OrganizationSourceNavigation(reader,workbench_url='http://localhost',retrieval_root=tmp_path/'indices')
    new.warm_release()
    assert new._candidate_index.original_reads == 0


def test_reinstalling_lost_change_tracking_never_restores_old_proofs(tmp_path, monkeypatch):
    from sec_agent.research_foundation.source_verification_cache import install
    nav, reader, _, _, grant = prepared(tmp_path, monkeypatch)
    nav.warm_release()
    with sqlite3.connect(reader.workspace.library.documents.path) as db:
        db.execute('DROP TRIGGER source_revision_attachments_update')
        db.execute('UPDATE attachments SET body=? WHERE id=?', (b'untracked corruption', grant['manifest']['inputs'][0]['ref']['version_id']))
        install(db)
    with pytest.raises(ValueError):nav.navigate(query())


def test_new_loader_reuses_file_hashes_but_mutation_is_rejected(tmp_path, monkeypatch):
    from sec_agent.research_foundation.organization_index_release import ReleaseLoadCache
    import hashlib
    nav, reader, _, directory, grant = prepared(tmp_path, monkeypatch)
    manifest = grant['manifest']; pinned=manifest['retrieval_index']
    nav.warm_release()
    original = hashlib.file_digest
    seen=[]
    def count(stream, *args, **kwargs):
        seen.append(stream.name); return original(stream,*args,**kwargs)
    monkeypatch.setattr(hashlib, 'file_digest', count)
    ReleaseLoadCache().load(tmp_path/'indices',manifest['organization_id'],pinned['release_id'],pinned)
    assert not seen
    with (directory/'vectors.npy').open('r+b') as stream:
        stream.seek(-4,2); stream.write(b'xxxx')
    with pytest.raises(ValueError,match='matrix_integrity'):
        ReleaseLoadCache().load(tmp_path/'indices',manifest['organization_id'],pinned['release_id'],pinned)
    assert seen


def test_parallel_run_warmups_validate_once_and_keep_execution_state_private(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    nav, reader, _, _, _ = prepared(tmp_path, monkeypatch)
    other=OrganizationSourceNavigation(reader,workbench_url='http://localhost',retrieval_root=tmp_path/'indices')
    calls=[]; original=reader._read_storage
    def count(*args):calls.append(args[0]); return original(*args)
    monkeypatch.setattr(reader,'_read_storage',count)
    start=Barrier(2)
    def warm(n):start.wait(); return n.warm_release()
    with ThreadPoolExecutor(max_workers=2) as executor:
        contracts=list(executor.map(warm,[nav,other]))
    assert contracts[0]==contracts[1]
    assert len(calls)==2  # one cold verification for the two bindings
    assert sorted(n._candidate_index.verification_hits for n in (nav,other))==[0,2]
    assert nav.observed is not other.observed and nav._candidate_index is not other._candidate_index


def test_receipt_capacity_eviction_only_forgets_optimization(tmp_path):
    from sec_agent.research_foundation.source_verification_cache import SourceVerificationCache
    cache=SourceVerificationCache(tmp_path)
    with sqlite3.connect(cache.path) as db:
        db.executemany('INSERT INTO receipts VALUES(?,?,?)',[(str(i),'{}','unused') for i in range(8192)])
    cache.put('new',{'verified':'fixture'})
    assert cache.get('0') is None and cache.get('new')=={'verified':'fixture'}
    with sqlite3.connect(cache.path) as db:
        assert db.execute('SELECT count(*) FROM receipts').fetchone()[0]==8192


def test_compressed_receipts_keep_legacy_reads_and_integrity(tmp_path):
    from hashlib import sha256
    from sec_agent.research_foundation.source_verification_cache import SourceVerificationCache
    cache = SourceVerificationCache(tmp_path)
    value = {'structures': [{'unit': 'USD millions', 'columns': [2025, 2024]}] * 1000}
    cache.put('new', value)
    legacy = json.dumps({'legacy': True})
    with sqlite3.connect(cache.path) as db:
        blob, = db.execute("SELECT payload FROM receipts WHERE key='new'").fetchone()
        assert isinstance(blob, bytes) and len(blob) < len(json.dumps(value))/10
        db.execute('INSERT INTO receipts VALUES(?,?,?)', ('legacy', legacy, sha256(legacy.encode()).hexdigest()))
    assert cache.get('new') == value and cache.get('legacy') == {'legacy': True}
    with sqlite3.connect(cache.path) as db:
        db.execute("UPDATE receipts SET digest='invalid' WHERE key='new'")
    with pytest.raises(ValueError, match='receipt_corrupt'):
        cache.get('new')


def test_pending_spool_does_not_retain_mutable_receipts_and_closes_on_failure():
    from sec_agent.research_foundation.source_verification_cache import PendingSourceReceipts
    with pytest.raises(RuntimeError):
        with PendingSourceReceipts() as pending:
            value = {'structures': [{'unit': 'USD'}]}
            pending.append(('key', value))
            value['structures'][0]['unit'] = 'changed after staging'
            assert list(pending) == [['key', {'structures': [{'unit': 'USD'}]}]]
            assert set(vars(pending)) == {'stream'}
            raise RuntimeError('cancelled before final authorization')
    assert pending.stream.closed


def test_late_revocation_discards_spooled_receipts(tmp_path, monkeypatch):
    from sec_agent.research_foundation.source_verification_cache import SourceVerificationCache
    nav, reader, state, _, _ = prepared(tmp_path, monkeypatch)
    original = reader._read_storage
    count = []
    def revoke_after_original(*args):
        result = original(*args)
        count.append(args[0])
        if len(count) == 2:
            state['status'] = 404
        return result
    monkeypatch.setattr(reader, '_read_storage', revoke_after_original)
    with pytest.raises(Exception):
        nav.warm_release()
    assert nav._candidate_index.generation is None
    with sqlite3.connect(SourceVerificationCache(tmp_path/'indices').path) as db:
        assert db.execute('SELECT count(*) FROM receipts').fetchone()[0] == 0
