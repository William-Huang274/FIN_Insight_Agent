"""Explicit original metadata scopes all retrieval channels, never permission."""
from datetime import date
from hashlib import sha256
import json
import sqlite3
from uuid import uuid4

import pytest

from test_organization_complete_sources import complete_fixture
from test_organization_candidate_index import prepared, query
from test_organization_execution_access import runtime_at, runtime_grant
from sec_agent.research_foundation.organization_source_filter import (
    OrganizationSourceFilter, source_metadata, select_documents,
)
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.research_foundation.organization_hybrid_retrieval import preparation_nodes, publish_prepared_index
from sec_agent.research_foundation.organization_graph_index import preparation_graph
from sec_agent.research_foundation.organization_index_release import load_release
from sec_agent.research_foundation.organization_source_projection import PROJECTION


def descriptor(**metadata):
    return source_metadata({'source': {'metadata': json.dumps(metadata),
                                      'title': 'ACME FY2024 10-K', 'published_at': '2025-02-01'}})


def test_discovery_role_survives_descriptor_without_title_based_inference():
    from sec_agent.research_foundation.organization_source_filter import original_source_metadata
    marked = descriptor(entity_id='ISSUER::acme', evidence_role='discovery_metadata_only')
    assert marked['evidence_role'] == 'discovery_metadata_only'
    # Legacy exact metadata filters keep their four-field wire contract.
    assert 'evidence_role' not in original_source_metadata({'source': {
        'metadata': json.dumps({'evidence_role': 'discovery_metadata_only'})}})
    assert 'evidence_role' not in descriptor(category='news_discovery')
    assert 'evidence_role' not in descriptor(evidence_role='original_document_requires_reading')


def test_original_fields_only_and_explicit_unknown_coverage():
    missing = descriptor(parent_form='10-K', fiscal_year=2024, report_date='2024-12-31')
    assert all(value is None for value in missing.values())
    assert descriptor(period_end='2024-02-30')['period_end'] is None
    assert descriptor(period_end='2024-W01-1')['period_end'] is None
    actual = descriptor(entity_id='ENTITY::issuer', company=' Acme ', form='10-k', period_end='2024-12-31')
    assert actual == dict(issuer_id='ENTITY::issuer', company_name='Acme', form='10-K', period_end='2024-12-31')
    matches, receipt = select_documents({'a': actual, 'b': missing,
        'c': {**actual, 'form': '10-K/A'}}, OrganizationSourceFilter(company_name='acme', form='10-k'))
    assert matches == {'a'}
    assert (receipt['matched_sources'], receipt['unknown_sources'], receipt['mismatched_sources']) == (1, 1, 1)
    assert receipt['metadata_missing_is_not_source_absence']
    # Publication year and amended/parent form never satisfy an exact original period/form.
    assert not select_documents({'a': actual}, OrganizationSourceFilter(period_end='2025-02-01'))[0]
    assert not select_documents({'a': actual}, OrganizationSourceFilter(issuer_id='ENTITY::other'))[0]


@pytest.mark.parametrize('constraint', [{}, {'form': ' '}, {'period_end': 1735603200},
    {'period_end': '2024-12-31T00:00:00'}, {'period_end': '2024-02-30'}, {'fiscal_year': 2024}])
def test_invalid_filters_rejected(constraint):
    with pytest.raises(ValueError):
        SourceDocumentRequest.model_validate(query(organization_filter=constraint))


def test_request_compatibility_and_scope():
    original = SourceDocumentRequest.model_validate(query())
    assert 'organization_filter' not in original.model_dump(mode='json')
    parsed = SourceDocumentRequest.model_validate(query(organization_filter={'period_end': '2024-12-31'}))
    assert parsed.organization_filter.period_end == date(2024, 12, 31)
    assert parsed.model_dump(mode='json')['organization_filter']['period_end'] == '2024-12-31'
    for changes in ({'source_space': 'library'}, {'source_space': 'local'},
                    {'operation': 'read', 'document_id': 'doc'}):
        with pytest.raises(ValueError, match='organization_filter_requires'):
            SourceDocumentRequest.model_validate(query(organization_filter={'form': '10-K'}, **changes))


def scoped_fixture(root, monkeypatch, *, queries=None, variants=None):
    """Real custody/index files, synthetic sources and vector values; no provider."""
    import test_organization_complete_sources as fixtures
    original_database = fixtures.database
    variants = variants if variants is not None else [dict(entity_id='ISSUER::A', company='Acme', form='10-K', period_end='2024-12-31'),
                dict(entity_id='ISSUER::A', company='Acme', form='10-Q', period_end='2024-09-30'),
                dict(entity_id='ISSUER::B', company='Beta', form='10-K', period_end='2024-12-31'),
                dict(company='Acme')]
    current = {}
    def database(path, text):
        sid = original_database(path, text)
        with sqlite3.connect(path) as db:
            db.execute('UPDATE sources SET metadata=?', (json.dumps(current),))
            for name in ('subject', 'object', 'predicate', 'published_at', 'valid_from', 'valid_to'):
                db.execute('ALTER TABLE edges ADD COLUMN ' + name + ' TEXT')
            db.execute("UPDATE edges SET subject='COUNTERPARTY::X',object='Y',predicate='supplies',published_at='2025-02-01'")
        return sid
    monkeypatch.setattr(fixtures, 'database', database)
    shared = grant = None
    for number, metadata in enumerate(variants):
        current = metadata
        folder = root/str(number)
        folder.mkdir()
        source, ref, own_shared, own_grant, *_ = complete_fixture(folder, monkeypatch, repeats=12)
        if shared is None:
            shared, grant = own_shared, own_grant
        else:
            first = grant['manifest']['inputs'][0]
            resource = str(uuid4())
            binding = shared.publish(source, 'alice', resource, grant['organization_id'], first['space_id'], ref)
            grant['manifest']['inputs'].append({**first, 'resource_id': resource, 'ref': binding['ref']})
            grant['inputs'].append({'resource_id': resource, 'binding': binding})
    reader, _ = runtime_at(shared, runtime_grant(grant))
    org, nodes = preparation_nodes(reader, workbench_url='http://localhost')
    graphs = preparation_graph(reader)
    vector = [1.] + [0.]*1023
    release = str(uuid4())
    publish_prepared_index(root/'indices', org, nodes, [vector]*len(nodes),
        {text: vector for text in (queries or ['disclosure'])},
        model='qwen3.7-text-embedding', provenance={'synthetic_fixture': True}, release_id=release,
        projection=PROJECTION, graph_sources=graphs)
    directory, _, _, contract = load_release(root/'indices', org, release)
    grant['manifest']['retrieval_index'] = contract
    reader, state = runtime_at(shared, runtime_grant(grant))
    nav = OrganizationSourceNavigation(reader, workbench_url='http://localhost', retrieval_root=root/'indices')
    return nav, reader, state, directory, grant


def test_report_role_is_consumed_before_all_channels_and_does_not_cache_access(tmp_path, monkeypatch):
    report, general = 'Acme annual report disclosure', 'Acme news disclosure'
    nav, reader, state, _, _ = scoped_fixture(tmp_path, monkeypatch, queries=[report, general], variants=[
        dict(entity_id='ISSUER::A', company='Acme', form='10-K'),
        dict(entity_id='ISSUER::A', company='Acme', form='10-K', evidence_role='discovery_metadata_only'),
        dict(entity_id='ISSUER::A', company='Acme'),
    ])
    nav.warm_release()
    metadata = nav._candidate_index.source_metadata
    discovery = next(doc for doc, row in metadata.items() if row.get('evidence_role')=='discovery_metadata_only')
    allowed = set(metadata)-{discovery}
    def no_originals(*args):
        raise AssertionError('role planning must consume verified descriptors without rereading originals')
    monkeypatch.setattr(reader, '_read_storage', no_originals)
    request = query(query=report, organization_query_planning='conservative.v1',
                    organization_metadata_policy='sec_cover.v2', entity_id='COUNTERPARTY::X', limit=20)
    found = nav.navigate(request)
    assert found.items and {r['document_id'] for r in found.items}==allowed
    receipt = found.items[0]['retrieval']
    for channel in ('dense_node_ids','lexical_node_ids','graph_node_ids','candidate_node_ids'):
        assert receipt[channel]
        assert all(nav._candidate_index.rows[node]['parent_document_id'] in allowed for node in receipt[channel])
    assert nav.navigate(request).items[0]['retrieval']['response_cache_hit']
    general_request = {**request, 'query': general}
    assert discovery in {r['document_id'] for r in nav.navigate(general_request).items}
    assert found.organization_query_plan['unknown_sources_retained']==1
    state['status']=404
    for denied in (request, general_request):
        with pytest.raises(OrganizationExecutionUnavailable):
            nav.navigate(denied)


def test_filter_precedes_dense_lexical_graph_and_preserves_release_and_readback(tmp_path, monkeypatch):
    nav, reader, state, directory, grant = scoped_fixture(tmp_path, monkeypatch)
    nav.warm_release()  # Explicit fixture publication preparation, never a catalog request.
    from sec_agent.research_foundation.organization_document_catalog import publish_from_receipts
    publish_from_receipts(reader, nav.hybrid.root)
    # All queries share content and vectors; metadata, not relevance labels, selects the issuer.
    files = {p.name: sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file()}
    catalog = nav.navigate({'source_space': 'organization', 'operation': 'catalog'})
    assert len(catalog.items) == 4
    assert 'organization_filter_receipt' not in catalog.model_dump(mode='json')
    target = next(row for row in catalog.items if row['organization_metadata']['issuer_id'] == 'ISSUER::A'
                  and row['organization_metadata']['form'] == '10-K')
    constraint = {k: v for k, v in target['organization_metadata'].items() if v is not None}
    request = query(organization_filter=constraint, entity_id='COUNTERPARTY::X')
    nav.warm_release()
    def no_originals(*args):
        raise AssertionError('metadata filtering must use the verified descriptor, not reload originals')
    read_storage = reader._read_storage
    monkeypatch.setattr(reader, '_read_storage', no_originals)
    result = nav.navigate(request)
    assert result.items and {r['document_id'] for r in result.items} == {target['document_id']}
    receipt = result.items[0]['retrieval']
    for channel in ('dense_node_ids', 'lexical_node_ids', 'graph_node_ids', 'candidate_node_ids'):
        assert receipt[channel]
        assert all(nav._candidate_index.rows[n]['parent_document_id'] == target['document_id'] for n in receipt[channel])
    assert {e['document'] for e in receipt['graph_evidence']} == {target['document_id']}
    assert '"matched_sources": 1' in result.notice and '"unknown_sources": 1' in result.notice
    assert result.organization_filter_receipt.matched_sources == 1
    cached = nav.navigate(request)
    assert cached.items[0]['retrieval']['response_cache_hit']
    assert cached.organization_filter_receipt == result.organization_filter_receipt
    all_results = nav.navigate(query(entity_id='COUNTERPARTY::X', limit=20))
    assert len({r['document_id'] for r in all_results.items}) == 4
    assert nav.navigate(request).items[0]['document_id'] == target['document_id']
    monkeypatch.setattr(reader, '_read_storage', read_storage)
    read = nav.navigate(result.items[0]['readback']).items[0]
    assert read['original_source']['source_id'] == 'SRC::fixture'
    assert read['passage'] and read['writer_citable']
    selected = nav.navigate({'source_space': 'organization', 'operation': 'catalog', 'organization_filter': constraint})
    assert [r['document_id'] for r in selected.items] == [target['document_id']]
    assert not nav.navigate({'source_space': 'organization', 'operation': 'catalog',
        'document_id': target['document_id'], 'organization_filter': {'form': '8-K'}}).items
    for name, digest in files.items():
        assert sha256((directory/name).read_bytes()).hexdigest() == digest
    state['status'] = 404
    for denied in (request, result.items[0]['readback'], query(organization_filter={'form': '8-K'})):
        with pytest.raises(OrganizationExecutionUnavailable):
            nav.navigate(denied)


@pytest.mark.parametrize('fault', ['java', 'local', 'body'])
def test_empty_filter_cache_and_nonmatching_source_still_require_authority(tmp_path, monkeypatch, fault):
    nav, reader, state, _, grant = prepared(tmp_path, monkeypatch)
    nav.warm_release()
    def no_rank(*args, **kwargs):
        raise AssertionError('empty metadata scope must not request an embedding or rank other sources')
    monkeypatch.setattr(nav.hybrid, 'rank', no_rank)
    request = query(organization_filter={'issuer_id': 'UNKNOWN'})
    result = nav.navigate(request)
    assert not result.items and '"unknown_sources": 2' in result.notice
    assert result.organization_filter_receipt.unknown_sources == 2
    assert not nav.navigate(request).items
    if fault == 'java':
        state['status'] = 404
    elif fault == 'local':
        second = grant['manifest']['inputs'][1]
        reader.workspace.library.set_access('organization:'+grant['organization_id'], second['space_id'],
                                            'document', second['ref']['version_id'], True)
    else:
        with sqlite3.connect(reader.workspace.library.documents.path) as db:
            db.execute('UPDATE attachments SET body=?', (b'changed',))
    with pytest.raises((OrganizationExecutionUnavailable, KeyError, ValueError)):
        nav.navigate(request)


def test_different_query_reuses_subset_statistics_but_never_revoked_scope(tmp_path, monkeypatch):
    nav, reader, state, _, grant = scoped_fixture(tmp_path, monkeypatch, queries=['disclosure','disclosure cash'])
    constraint = {'issuer_id':'ISSUER::A','form':'10-K'}
    first = nav.navigate(query(organization_filter=constraint))
    assert not first.items[0]['retrieval']['lexical_subset_statistics_hit']
    second = nav.navigate(query(query='disclosure cash',organization_filter=constraint))
    assert second.items[0]['retrieval']['lexical_subset_statistics_hit']
    assert not second.items[0]['retrieval'].get('response_cache_hit',False)
    # A non-selected resource revocation still blocks the frozen input grant.
    other = grant['manifest']['inputs'][2]
    reader.workspace.library.set_access('organization:'+grant['organization_id'], other['space_id'],
                                        'document', other['ref']['version_id'], True)
    with pytest.raises(OrganizationExecutionUnavailable):
        nav.navigate(query(organization_filter=constraint))


def test_unsupported_legacy_search_and_graph_do_not_silently_ignore_filter(tmp_path, monkeypatch):
    nav, reader, *_ = prepared(tmp_path, monkeypatch)
    legacy = OrganizationSourceNavigation(reader, workbench_url='http://localhost')
    with pytest.raises(ValueError, match='requires_prepared_candidate_index'):
        legacy.navigate(query(organization_filter={'form': '10-K'}))
    with pytest.raises(ValueError, match='graph_not_published'):
        nav.navigate(query(organization_filter={'form': '10-K'}, entity_id='ENTITY::A'))
