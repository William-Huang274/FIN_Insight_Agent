import sqlite3

import pytest
from fastapi import HTTPException

from test_organization_research_inputs import fixture
from apps.workbench.backend import organization_research_inputs as api


def test_repeated_admission_reuses_bytes_but_not_local_access(tmp_path, monkeypatch):
    shared, grant = fixture(tmp_path)
    args = shared, grant['organization_id'], grant['inputs'], '2026-10-12'
    expected = api.verify_storage(*args)
    monkeypatch.setattr(shared.workspace, 'resolve', lambda *a: pytest.fail('unnecessary body read'))
    assert api.verify_storage(*args) == expected
    batch = shared.workspace.document_version_batch
    def denied(*a):
        rows = batch(*a)
        for row in rows.values(): row['access_status'] = 'revoked'
        return rows
    monkeypatch.setattr(shared.workspace, 'document_version_batch', denied)
    with pytest.raises(HTTPException): api.verify_storage(*args)


@pytest.mark.parametrize('change', ['body', 'trigger', 'cutoff'])
def test_changed_source_instrumentation_or_cutoff_forces_full_check(tmp_path, monkeypatch, change):
    shared, grant = fixture(tmp_path)
    args = shared, grant['organization_id'], grant['inputs'], '2026-10-12'
    api.verify_storage(*args)
    calls = []
    resolve = shared.workspace.resolve
    def counted(*a): calls.append(1); return resolve(*a)
    monkeypatch.setattr(shared.workspace, 'resolve', counted)
    with sqlite3.connect(shared.workspace.library.documents.path) as db:
        if change == 'body': db.execute('UPDATE attachments SET body=body')
        if change == 'trigger': db.execute('DROP TRIGGER source_revision_attachments_update')
    if change == 'cutoff': args = (*args[:-1], '2026-10-13')
    api.verify_storage(*args)
    assert calls


def test_mutation_during_verification_does_not_publish_proof(tmp_path, monkeypatch):
    shared, grant = fixture(tmp_path)
    args = shared, grant['organization_id'], grant['inputs']
    resolve = shared.workspace.resolve
    def changed(*a):
        result = resolve(*a)
        with sqlite3.connect(shared.workspace.library.documents.path) as db:
            db.execute('UPDATE attachments SET body=body')
        return result
    monkeypatch.setattr(shared.workspace, 'resolve', changed)
    with pytest.raises(HTTPException): api.verify_storage(*args)
    monkeypatch.setattr(shared.workspace, 'resolve', resolve)
    assert api.verify_storage(*args)


def test_frozen_release_mutation_invalidates_admission_receipt(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from test_organization_candidate_index import prepared
    _, reader, _, directory, grant = prepared(tmp_path, monkeypatch)
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_RETRIEVAL_ROOT', str(tmp_path/'indices'))
    args = (SimpleNamespace(workspace=reader.workspace), grant['organization_id'], grant['inputs'],
            grant['manifest']['research_as_of'], grant['manifest']['retrieval_index'])
    api.verify_storage(*args)
    original = reader.workspace.read_source
    monkeypatch.setattr(reader.workspace, 'read_source', lambda *a: pytest.fail('warm source projection reread'))
    assert api.verify_storage(*args)
    monkeypatch.setattr(reader.workspace, 'read_source', original)
    with (directory/'index.json').open('ab') as out: out.write(b'corruption')
    with pytest.raises(HTTPException): api.verify_storage(*args)


def test_receipt_batch_rolls_back_on_interrupted_publication(tmp_path):
    from sec_agent.research_foundation.source_verification_cache import SourceVerificationCache
    cache = SourceVerificationCache(tmp_path)
    def interrupted():
        yield 'one', {'value':1}
        raise RuntimeError('cancelled')
    with pytest.raises(RuntimeError): cache.put_many(interrupted())
    assert cache.get('one') is None
    cache.put_many([('one', {'value':1}), ('two', {'value':2})])
    assert list(cache.iter_get(['one', 'absent', 'two'])) == [('one', {'value':1}), ('absent', None), ('two', {'value':2})]
