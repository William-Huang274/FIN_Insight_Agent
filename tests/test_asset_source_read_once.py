"""Reuse one verified capture per call, never a cross-request authority cache."""
import json

import pytest

from test_organization_complete_sources import complete_fixture
from sec_agent.research_foundation.asset_workspace import AssetConflict
from sec_agent.research_foundation import project_source_captures as captures


def test_complete_source_reads_and_validates_capture_once_per_call(tmp_path, monkeypatch):
    source, ref, _, _, _, _, bundle, text = complete_fixture(tmp_path, monkeypatch)
    reads, checks = [], []
    get = source.library.documents.get
    validate = captures.read_capture

    def counted_get(*args, **kwargs):
        reads.append(args)
        return get(*args, **kwargs)

    def counted_validate(*args):
        checks.append(args[1]['id'])
        return validate(*args)

    monkeypatch.setattr(source.library.documents, 'get', counted_get)
    monkeypatch.setattr(captures, 'read_capture', counted_validate)
    full = source.read_source('alice', ref)
    assert len(reads) == len(checks) == 1
    assert full['text'] == text and not full['truncated']
    assert full['source_bundle']['source'] == bundle['source']
    assert full['source_bundle']['chunks'] == bundle['chunks']
    preview = source.read('alice', ref)
    assert len(reads) == len(checks) == 2
    assert preview['text'] == text[:100000] and preview['truncated']
    assert 'source_bundle' not in preview
    assert full['version'] == preview['version']
    assert full['capture'] == preview['capture']
    version, row = source.resolve('alice', ref)
    assert version == full['version'] and row['id'] == ref['version_id']
    assert len(reads) == len(checks) == 3


@pytest.mark.parametrize('fault', ['body', 'snapshot', 'note', 'missing_capture', 'local_revoke', 'owner'])
def test_next_call_must_revalidate_original_capture_and_scope(tmp_path, monkeypatch, fault):
    source, ref, _, _, _, _, _, _ = complete_fixture(tmp_path, monkeypatch, repeats=80)
    source.read_source('alice', ref)
    owner = 'alice'
    if fault == 'owner':
        owner = 'someone-else'
    elif fault == 'local_revoke':
        source.library.set_access(owner, ref['project_id'], 'document', ref['version_id'], True)
    else:
        with source.library.documents.connect() as db:
            if fault == 'body':
                db.execute('UPDATE attachments SET body=? WHERE id=?', (b'changed', ref['version_id']))
            elif fault == 'missing_capture':
                db.execute('DELETE FROM attachment_captures WHERE object_id=?', (ref['version_id'],))
            elif fault == 'note':
                db.execute('UPDATE attachment_captures SET note=? WHERE object_id=?', ('changed', ref['version_id']))
            else:
                row = db.execute('SELECT snapshot FROM attachment_captures WHERE object_id=?', (ref['version_id'],)).fetchone()
                snapshot = json.loads(row[0])
                snapshot['bundle']['text'] += 'changed'
                db.execute('UPDATE attachment_captures SET snapshot=? WHERE object_id=?', (json.dumps(snapshot), ref['version_id']))
    for method in (source.read_source, source.read, source.resolve):
        with pytest.raises((AssetConflict, KeyError, ValueError)):
            method(owner, ref)


def test_local_revocation_during_capture_validation_denies_complete_read(tmp_path, monkeypatch):
    source, ref, _, _, _, _, _, _ = complete_fixture(tmp_path, monkeypatch, repeats=80)
    validate = captures.read_capture

    def revoke(*args):
        result = validate(*args)
        source.library.set_access('alice', ref['project_id'], 'document', ref['version_id'], True)
        return result

    monkeypatch.setattr(captures, 'read_capture', revoke)
    with pytest.raises((AssetConflict, KeyError, ValueError)):
        source.read_source('alice', ref)
