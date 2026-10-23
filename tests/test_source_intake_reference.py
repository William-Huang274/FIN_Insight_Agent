import sqlite3
import pytest

from test_organization_candidate_index import prepared, query
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from tests.integration.source_intake_reference import OriginalRow, original_reference


@pytest.mark.parametrize('changes', [{}, {'query':'missing query','offset':3,'limit':2}])
def test_disk_reference_equals_original_path_without_reading_published_candidates(tmp_path, monkeypatch, changes):
    nav, reader, _, directory, _ = prepared(tmp_path, monkeypatch)
    expected = nav._navigate(query(**changes))
    with sqlite3.connect(directory/'rank-cache.sqlite') as db:
        db.execute('DELETE FROM ranks')
    import retrieval.published_lexical_index as lexical
    import sec_agent.research_foundation.organization_candidate_index as candidates
    def forbidden(*args, **kwargs):
        raise AssertionError('reference must not consume published candidate or lexical scores')
    monkeypatch.setattr(lexical,'scores',forbidden)
    monkeypatch.setattr(lexical,'scores_from_identities',forbidden)
    monkeypatch.setattr(candidates.VerifiedCandidateIndex,'materialize',forbidden)
    calls=[]
    read=reader._read_storage
    def counted(*args):
        calls.append(args[0]);return read(*args)
    monkeypatch.setattr(reader,'_read_storage',counted)
    reference=OrganizationSourceNavigation(reader,workbench_url='http://localhost',retrieval_root=tmp_path/'indices')
    actual=original_reference(reference,query(**changes),tmp_path/'reference.sqlite')
    assert actual == expected
    assert len(calls)==len(set(calls))==2
    assert not actual.items[0]['retrieval']['cache_hit']


def test_revocation_during_original_scan_cannot_return_reference(tmp_path, monkeypatch):
    nav,reader,state,_,_=prepared(tmp_path,monkeypatch)
    read=reader._read_storage
    def revoke(*args):
        result=read(*args);state['status']=404;return result
    monkeypatch.setattr(reader,'_read_storage',revoke)
    with pytest.raises(OrganizationExecutionUnavailable):
        original_reference(nav,query(),tmp_path/'reference.sqlite')


def test_reference_rows_do_not_retain_source_body_or_metadata(tmp_path):
    import weakref,json,zlib
    class Row(dict): pass
    row=Row(node_id='n',node_kind='text',parent_document_id='d',content_sha256='hash',
            embedding_input_sha256='embedding',content='unique original body',title='original title')
    reference=weakref.ref(row)
    with sqlite3.connect(tmp_path/'scratch.sqlite') as db:
        db.execute('CREATE TABLE originals(position INTEGER PRIMARY KEY,payload BLOB)')
        db.execute('INSERT INTO originals VALUES(0,?)',(zlib.compress(json.dumps(row).encode()),))
        lazy=OriginalRow(db,0,row)
        del row
        assert reference() is None
        assert 'content' not in lazy.identity and 'title' not in lazy.identity
        assert lazy['content']=='unique original body' and lazy['title']=='original title'
        assert lazy.lexical_counts().length==3


def test_reference_rejects_filtered_scope_before_storage_or_creating_file(tmp_path, monkeypatch):
    nav,_,_,_,grant=prepared(tmp_path,monkeypatch)
    path=tmp_path/'must-not-exist.sqlite'
    with pytest.raises(ValueError,match='full_organization_search'):
        original_reference(nav,query(document_id=nav._identity(grant['manifest']['inputs'][0])),path)
    assert not path.exists()
