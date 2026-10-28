from copy import deepcopy
import sqlite3
from uuid import uuid4

import pytest

from test_organization_complete_sources import complete_fixture
from test_organization_execution_access import runtime_at, runtime_grant
from sec_agent.research_foundation.organization_hybrid_retrieval import preparation_nodes, publish_prepared_index
from sec_agent.research_foundation.organization_index_release import load_release
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.research_foundation.organization_source_projection import PROJECTION
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable


def prepared(tmp_path, monkeypatch):
    source, ref, shared, grant, reader, _, _, _ = complete_fixture(tmp_path, monkeypatch, repeats=1000)
    first = grant['manifest']['inputs'][0]
    resource = str(uuid4())
    binding = shared.publish(source, 'alice', resource, grant['organization_id'], first['space_id'], ref)
    grant['manifest']['inputs'].append({**first, 'resource_id':resource, 'ref':binding['ref']})
    grant['inputs'].append({'resource_id':resource, 'binding':binding})
    reader, _ = runtime_at(shared, runtime_grant(grant))
    org, nodes = preparation_nodes(reader, workbench_url='http://preparation.example.test')
    release = str(uuid4())
    vector = [1.] + [0.]*1023
    publish_prepared_index(tmp_path/'indices', org, nodes, [vector]*len(nodes),
        {'disclosure':vector, 'USD millions':vector, 'missing query':vector},
        model='qwen3.7-text-embedding', provenance={'fixture':True}, release_id=release, projection=PROJECTION)
    directory, _, _, contract = load_release(tmp_path/'indices', org, release)
    grant['manifest']['retrieval_index'] = contract
    reader, state = runtime_at(shared, runtime_grant(grant))
    nav = OrganizationSourceNavigation(reader, workbench_url='http://localhost', retrieval_root=tmp_path/'indices')
    return nav, reader, state, directory, grant


def query(**changes):
    return {'source_space':'organization', 'operation':'search', 'query':'disclosure', **changes}


def test_verified_source_owner_survives_cold_and_receipt_restoration(tmp_path,monkeypatch):
    from sec_agent.research_foundation import organization_source_filter
    original=organization_source_filter.source_metadata
    identifiers=[{'identifier':'123','scheme':'http://www.sec.gov/CIK'}]
    def metadata(bundle):
        return {**original(bundle),'verified_company_names':['Cedar Inc.'],
                'fact_entity_identifiers':identifiers}
    monkeypatch.setattr(organization_source_filter,'source_metadata',metadata)
    nav,reader,_,_,_=prepared(tmp_path,monkeypatch)
    nav.warm_release()
    expected={'company_names':['Cedar Inc.'],'fact_entity_identifiers':identifiers}
    assert all(r['fact_owner']==expected for r in nav._candidate_index.rows.values())
    monkeypatch.setattr(reader,'_read_storage',lambda *_:pytest.fail('valid receipt must avoid original reload'))
    restored=OrganizationSourceNavigation(reader,workbench_url='http://localhost',retrieval_root=tmp_path/'indices')
    restored.warm_release()
    assert all(r['fact_owner']==expected for r in restored._candidate_index.rows.values())


def test_optional_completion_preserves_result_order_and_warm_authorization(tmp_path, monkeypatch):
    nav,reader,state,_,_=prepared(tmp_path,monkeypatch)
    old=nav.navigate(query())
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_TABLE_COMPLETION','bounded.v1')
    enhanced=OrganizationSourceNavigation(reader,workbench_url='http://localhost',retrieval_root=tmp_path/'indices')
    actual=enhanced.navigate(query())
    assert [r['node_id'] for r in old.items]==[r['node_id'] for r in actual.items]
    assert all('table_completion' in r for r in actual.items)
    monkeypatch.setattr(reader,'_read_storage',lambda *_:pytest.fail('warm search must not rescan originals'))
    cached=enhanced.navigate(query())
    assert cached.items[0]['retrieval']['response_cache_hit']
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):enhanced.navigate(query())


def items(result):
    return [{k:v for k,v in row.items() if k != 'retrieval'} for row in result.items]


def test_new_queries_only_read_candidates_and_match_independent_original_ranking(tmp_path, monkeypatch):
    nav, reader, _, directory, _ = prepared(tmp_path, monkeypatch)
    reads = []
    original = reader._read_storage
    def counted(*args):
        reads.append(args[0])
        return original(*args)
    monkeypatch.setattr(reader, '_read_storage', counted)
    first = nav.navigate(query())
    assert len(reads) == 2 and nav._projection_cache is None
    assert len(nav._candidate_index.rows) > 36
    assert 0 < first.items[0]['retrieval']['candidate_body_reads'] <= 36
    for request in (query(query='USD millions'), query(document_id=first.items[0]['document_id']),
                    query(query='missing query',offset=3,limit=2)):
        reads.clear()
        actual = nav.navigate(request)
        receipt = actual.items[0]['retrieval']
        assert not reads and receipt['source_generation_original_reads'] == 0
        assert receipt['candidate_only'] and receipt['candidate_body_reads'] <= 36
        with sqlite3.connect(directory/'rank-cache.sqlite') as db:
            db.execute('DELETE FROM ranks')
        reference = OrganizationSourceNavigation(reader, workbench_url='http://localhost',retrieval_root=tmp_path/'indices')
        expected = reference._navigate(request)
        assert reads and items(actual) == items(expected)
        assert actual.total_matches == expected.total_matches and actual.next_offset == expected.next_offset
        for key in ('dense_node_ids','lexical_node_ids','candidate_node_ids'):
            assert receipt[key] == expected.items[0]['retrieval'][key]
    reads.clear()
    cached = nav.navigate(request)
    assert not reads
    assert cached.items[0]['retrieval']['candidate_body_reads'] == 0
    assert cached.items[0]['retrieval']['source_generation_original_reads'] == 0
    nav.navigate(first.items[0]['readback'])
    assert reads  # Original citation reads remain live.


@pytest.mark.parametrize('fault', ['java_revoke','local_revoke','body','delete'])
def test_non_candidate_source_changes_deny_filtered_query(tmp_path, monkeypatch, fault):
    nav, reader, state, _, grant = prepared(tmp_path, monkeypatch)
    document = nav._identity(grant['manifest']['inputs'][0])
    request = query(document_id=document)
    nav.navigate(request)
    if fault == 'java_revoke':
        state['status'] = 404
    elif fault == 'local_revoke':
        second = grant['manifest']['inputs'][1]
        reader.workspace.library.set_access('organization:'+grant['organization_id'], second['space_id'],
                                            'document',second['ref']['version_id'],True)
    else:
        second = grant['manifest']['inputs'][1]
        with sqlite3.connect(reader.workspace.library.documents.path) as db:
            if fault == 'delete':
                db.execute('DELETE FROM attachments WHERE id=?',(second['ref']['version_id'],))
            else:
                db.execute('UPDATE attachments SET body=? WHERE id=?',(b'corrupt',second['ref']['version_id']))
    with pytest.raises((OrganizationExecutionUnavailable,KeyError)):
        nav.navigate({**request,'query':'USD millions'})


def test_unrelated_write_rechecks_scope_without_reloading_originals(tmp_path, monkeypatch):
    nav, reader, _, _, grant = prepared(tmp_path, monkeypatch)
    nav.warm_release()
    assert nav._candidate_index.original_reads == 2
    def unexpected(*args):
        raise AssertionError('unchanged warm generation must not read original bodies')
    original = reader._read_storage
    monkeypatch.setattr(reader,'_read_storage',unexpected)
    nav.navigate(query())
    with sqlite3.connect(reader.workspace.library.documents.path) as db:
        db.execute('CREATE TABLE unrelated_committed_change (value INTEGER)')
    result = nav.navigate(query(query='USD millions'))
    assert result.items[0]['retrieval']['source_generation_original_reads'] == 0
    assert nav._candidate_index.verification_hits == len(grant['inputs'])


@pytest.mark.parametrize('fault', ['file','body_race','revoke_race'])
def test_published_body_corruption_and_races_cannot_return_candidates(tmp_path, monkeypatch, fault):
    nav, reader, state, directory, _ = prepared(tmp_path,monkeypatch)
    nav.warm_release()
    if fault == 'file':
        with sqlite3.connect(directory/'navigation.sqlite') as db:
            db.execute('UPDATE nodes SET payload=?',(b'corrupt',))
    else:
        materialize = nav._candidate_index.materialize
        def race(*args):
            result = materialize(*args)
            if fault == 'revoke_race':
                state['status'] = 404
            else:
                with sqlite3.connect(reader.workspace.library.documents.path) as db:
                    db.execute('UPDATE attachments SET body=?',(b'changed after read',))
            return result
        monkeypatch.setattr(nav._candidate_index,'materialize',race)
    with pytest.raises((ValueError,OrganizationExecutionUnavailable)):
        nav.navigate(query())


def test_unverified_or_copied_rows_cannot_skip_original_identity_checks(tmp_path,monkeypatch):
    nav, reader, _, _, _ = prepared(tmp_path,monkeypatch)
    nav.warm_release()
    proof = nav._candidate_index
    rows = [deepcopy(next(iter(proof.rows.values())))]
    with pytest.raises(OrganizationExecutionUnavailable,match='unverified_population'):
        nav.hybrid.rank(rows,'disclosure',reader.authority.manifest_digest[7:],[],source_verifier=proof)
    with pytest.raises(OrganizationExecutionUnavailable,match='invalid_verifier'):
        nav.hybrid.rank(rows,'disclosure',reader.authority.manifest_digest[7:],[],source_verifier=True)


@pytest.mark.parametrize('fault',['no_hybrid','no_navigation'])
def test_completion_cannot_silently_fall_back_without_verified_navigation(tmp_path,monkeypatch,fault):
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_TABLE_COMPLETION','bounded.v1')
    nav,_,_,_,_=prepared(tmp_path,monkeypatch)
    if fault=='no_hybrid':
        nav.hybrid=None
    else:
        load=nav.hybrid.load_frozen
        def without_navigation(*args):
            directory,index,other,contract=load(*args)
            return directory,{k:v for k,v in index.items() if k!='navigation_index'},other,contract
        monkeypatch.setattr(nav.hybrid,'load_frozen',without_navigation)
    with pytest.raises(ValueError,match='requires_verified_navigation'):
        nav.navigate(query())
