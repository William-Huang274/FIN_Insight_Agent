"""Complete sources use the same custody, authority, index and readback path."""
from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_library_source_bundle import database, bundle_at, vectors_for
from test_organization_execution_access import runtime_at, runtime_grant
from test_organization_research_inputs import fixture
from sec_agent.research_foundation.asset_workspace import AssetWorkspace, AssetConflict
from sec_agent.research_foundation.project_source_captures import CaptureRequest, save_capture
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from sec_agent.research_foundation.organization_hybrid_retrieval import preparation_nodes, publish_prepared_index
from sec_agent.research_foundation.organization_index_release import load_release, verify_release_inputs
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.research_foundation.organization_source_projection import PROJECTION
from sec_agent.research_foundation.organization_source_projection import validate_source_cutoff


def complete_fixture(root, monkeypatch, repeats=2600):
    text = ('Historical disclosure paragraph. 单位 USD millions.\r\n' * repeats) + '\nTAIL_EVIDENCE_ZYX final source paragraph.'
    path = root/'library.sqlite'
    sid = database(path, text)
    bundle = bundle_at(path, sid)
    import sec_agent.research_foundation.research_library as library_module
    monkeypatch.setattr(library_module, 'open_library', lambda _: SimpleNamespace(path=path, manifest={'sha256':bundle['library_sha256']}))
    source = AssetWorkspace(root/'private')
    project = str(uuid4())
    source.library.save('alice', 0, {'projects':[{'id':project,'name':'Original'}],'assignments':{},'pinned':[]})
    request = CaptureRequest(project_id=project, title='Complete original', selection={
        'kind':'library_source','document_id':sid,'snapshot':bundle['library_sha256']})
    saved = save_capture(source, 'alice', request, None, None, path)
    ref = next(v['ref'] for a in source.catalog('alice',project)['items'] for v in a['versions'] if v['ref']['version_id']==saved['document_id'])
    shared, grant = fixture(root/'base')
    org, space, rid = grant['organization_id'], grant['manifest']['inputs'][0]['space_id'], str(uuid4())
    binding = shared.publish(source, 'alice', rid, org, space, ref)
    grant['manifest']['inputs'] = [{**grant['manifest']['inputs'][0], 'resource_id':rid,'ref':binding['ref'],'resource_type':'knowledge'}]
    grant['inputs'] = [{'resource_id':rid,'binding':binding}]
    reader, state = runtime_at(shared, runtime_grant(grant))
    return source, ref, shared, grant, reader, state, bundle, text


def test_complete_source_tail_and_raw_chunk_readback_with_current_authority(tmp_path, monkeypatch):
    source, ref, shared, grant, reader, state, bundle, text = complete_fixture(tmp_path, monkeypatch)
    assert len(text) > 100000 and source.read('alice',ref)['truncated']
    assert source.read_source('alice',ref)['text'] == text
    rid = grant['manifest']['inputs'][0]['resource_id']
    tail = reader.read_text(rid, len(text)-100, 100)
    assert tail['text']==text[-100:] and not tail['source_truncated'] and tail['next_offset'] is None
    nav = OrganizationSourceNavigation(reader,workbench_url='http://localhost')
    found = nav.navigate({'source_space':'organization','operation':'search','query':'TAIL_EVIDENCE_ZYX'})
    candidate = next(row for row in found.items if 'TAIL_EVIDENCE_ZYX' in row.get('preview','') or row['original_source']['source_char_end']==len(text))
    read = nav.navigate(candidate['readback']).items[0]
    origin = read['original_source']
    assert read['passage']==text[origin['source_char_start']:origin['source_char_end']]
    assert 'TAIL_EVIDENCE_ZYX' in read['passage']
    assert read['writer_citable'] and not read['numeric_fact_authority']
    assert origin['source_id']==bundle['source']['id']
    restored=OrganizationSourceNavigation(reader,workbench_url='http://localhost')
    restored.restore([{'status':'success','content':[read]}])
    assert restored.source(read['passage_id'])==read
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable): nav.navigate(candidate['readback'])
    with pytest.raises(OrganizationExecutionUnavailable): reader.read_text(rid, len(text)-100,100)


def test_complete_read_rechecks_authority_after_storage(tmp_path, monkeypatch):
    _, _, shared, grant, reader, state, _, _ = complete_fixture(tmp_path, monkeypatch)
    read=shared.workspace.read_source
    def revoke(*args):
        result=read(*args)
        state['status']=404
        return result
    monkeypatch.setattr(shared.workspace,'read_source',revoke)
    with pytest.raises(OrganizationExecutionUnavailable): reader.read_text(grant['manifest']['inputs'][0]['resource_id'])


def test_complete_projection_frozen_release_hashes_cache_and_legacy_rejection(tmp_path, monkeypatch):
    _, _, shared, grant, reader, state, bundle, text = complete_fixture(tmp_path, monkeypatch)
    org, nodes = preparation_nodes(reader,workbench_url='http://localhost')
    _, matrix, _ = vectors_for(bundle,tmp_path/'old-vectors')
    by_id = {row['id']:i for i,row in enumerate(bundle['chunks'])}
    vectors = [matrix[by_id[row['original_source']['id']]] for row in nodes]
    tail = next(row for row in nodes if 'TAIL_EVIDENCE_ZYX' in row['content'])
    query = 'TAIL_EVIDENCE_ZYX'
    release = str(uuid4())
    with pytest.raises(ValueError,match='embedding_projection'):
        publish_prepared_index(tmp_path/'bad',org,nodes,vectors,{},model='qwen3.7-text-embedding',
                               provenance={'fixture':True},release_id=str(uuid4()))
    publish_prepared_index(tmp_path/'indices',org,nodes,vectors,{query:vectors[nodes.index(tail)]},
        model='qwen3.7-text-embedding',provenance={'fixture':True},release_id=release,projection=PROJECTION)
    _, _, _, contract = load_release(tmp_path/'indices',org,release)
    verify_release_inputs(shared.workspace,org,grant['inputs'],contract,tmp_path/'indices','2026-10-12')
    grant['manifest']['retrieval_index']=contract
    reader,state=runtime_at(shared,runtime_grant(grant))
    nav=OrganizationSourceNavigation(reader,workbench_url='http://localhost',retrieval_root=tmp_path/'indices')
    first=nav.navigate({'source_space':'organization','operation':'search','query':query})
    second=nav.navigate({'source_space':'organization','operation':'search','query':query})
    assert first.items[0]['node_id']==tail['node_id']
    assert second.items[0]['retrieval']['cache_hit']
    assert nav.navigate(second.items[0]['readback']).items[0]['passage']==tail['content']
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable): nav.navigate(second.items[0]['readback'])
    with pytest.raises(OrganizationExecutionUnavailable): nav.navigate({'source_space':'organization','operation':'search','query':query})


def test_statistics_population_tracks_real_organization_document_filter(tmp_path, monkeypatch):
    source, ref, shared, grant, _, _, _, _ = complete_fixture(tmp_path, monkeypatch, repeats=80)
    resource = str(uuid4())
    first_input = grant['manifest']['inputs'][0]
    binding = shared.publish(source, 'alice', resource, grant['organization_id'], first_input['space_id'], ref)
    grant['manifest']['inputs'].append({**first_input, 'resource_id':resource, 'ref':binding['ref']})
    grant['inputs'].append({'resource_id':resource, 'binding':binding})
    reader, _ = runtime_at(shared, runtime_grant(grant))
    org, nodes = preparation_nodes(reader, workbench_url='http://localhost')
    release = str(uuid4())
    vector = [1.] + [0.] * 1023  # Deterministic fixture, no provider request.
    publish_prepared_index(tmp_path/'indices', org, nodes, [vector]*len(nodes),
        {'disclosure':vector}, model='qwen3.7-text-embedding', provenance={'synthetic_fixture':True},
        release_id=release, projection=PROJECTION, publish_lexical=False)
    grant['manifest']['retrieval_index'] = load_release(tmp_path/'indices', org, release)[3]
    reader, _ = runtime_at(shared, runtime_grant(grant))
    nav = OrganizationSourceNavigation(reader, workbench_url='http://localhost', retrieval_root=tmp_path/'indices')
    query = {'source_space':'organization', 'operation':'search', 'query':'disclosure'}
    first = nav.navigate(query)
    statistics = nav._projection_cache.lexical_statistics
    global_key = statistics.entry[0]
    scoped = {**query, 'document_id':first.items[0]['document_id']}
    result = nav.navigate(scoped)
    assert result.items and not statistics.hit and statistics.entry[0] != global_key
    nav.navigate({**scoped, 'limit':1})
    assert statistics.hit
    again = nav.navigate(query)
    assert not statistics.hit and statistics.entry[0] == global_key
    assert again.items[0]['retrieval']['lexical_node_ids'] == first.items[0]['retrieval']['lexical_node_ids']


def test_split_embedding_input_keeps_release_bytes_and_rejects_changed_context(tmp_path, monkeypatch):
    _, _, _, _, reader, _, bundle, _ = complete_fixture(tmp_path, monkeypatch, repeats=80)
    org, nodes = preparation_nodes(reader, workbench_url='http://localhost')
    chunks = {row['id']: row for row in bundle['chunks']}
    legacy = []
    for row in nodes:
        chunk = chunks[row['original_source']['id']]
        assert 'embedding_content' not in row
        assert row['embedding_context'] == chunk['context']
        assert row['content'] == chunk['body']
        old = {key: value for key, value in row.items() if key != 'embedding_context'}
        old['embedding_content'] = chunk['context'] + '\n' + chunk['body']
        legacy.append(old)
    vectors = [[1.] + [0.] * 1023 for _ in nodes]
    release = str(uuid4())
    options = dict(model='qwen3.7-text-embedding', provenance={'fixture': True},
                   release_id=release, projection=PROJECTION)
    for name, values in [('compact', nodes), ('legacy', legacy)]:
        publish_prepared_index(tmp_path/name, org, values, vectors, {}, **options)
    for name in ['index.json', 'vectors.npy']:
        assert (tmp_path/'compact'/org/'releases'/release/name).read_bytes() == (
            tmp_path/'legacy'/org/'releases'/release/name).read_bytes()
    for name, replacement in [('changed', {'embedding_context': 'different context'}),
                              ('ambiguous', {'embedding_content': 'different combined input'})]:
        bad = [dict(row) for row in nodes]
        bad[-1].update(replacement)
        with pytest.raises(ValueError, match='embedding_projection'):
            publish_prepared_index(tmp_path/name, org, bad, vectors, {}, **options)
        assert not (tmp_path/name/org/'releases'/release/'index.json').exists()


def test_compact_nodes_preserve_unicode_offsets_and_public_wire_shape(tmp_path):
    from sec_agent.research_foundation.organization_source_projection import source_nodes
    from sec_agent.research_foundation.source_document_navigation import navigate_source_nodes, SourceDocumentRequest
    text = 'Revenue 123.40 USD.\r\n中文 e\u0301 é 🧾\n' * 300
    path = tmp_path/'library.sqlite'
    sid = database(path, text)
    bundle = bundle_at(path, sid)
    bundle['source']['metadata'] = json.dumps({'entity_id': 'COMPANY::unicode', 'fiscal_period': '2025'})
    nodes = source_nodes(bundle, 'ORGDOC::unicode',
        {'title': 'Unicode original', 'ref': {'digest': 'a'*64}}, 'http://localhost')
    plain = [dict(row) for row in nodes]
    assert len(nodes) > 2
    assert all(row['company'] == 'COMPANY::unicode' and row['fiscal_period'] == '2025' for row in nodes)
    for row in nodes:
        assert row.get('absent') is None
        assert len(row) == len(set(row)) == len(dict(row))
        with pytest.raises(TypeError):
            row['content'] = 'changed'
    requests = [SourceDocumentRequest(source_space='organization', operation=op, document_id='ORGDOC::unicode',
                **({'query': 'Revenue'} if op == 'search' else {})) for op in ('catalog','outline','search')]
    requests.append(SourceDocumentRequest(source_space='organization', operation='read',
        document_id='ORGDOC::unicode', node_id=nodes[0]['node_id'], character_offset=23, max_characters=2000))
    for request in requests:
        expected = navigate_source_nodes(plain, request, snapshot='fixed', allowed_space='organization', hybrid_enabled=False)
        actual = navigate_source_nodes(nodes, request, snapshot='fixed', allowed_space='organization', hybrid_enabled=False)
        assert actual.model_dump(mode='json') == expected.model_dump(mode='json')
    assert actual.items[0]['passage'] == nodes[0]['content'][23:2023]


def test_new_capture_rejects_stale_snapshot_and_future_source(tmp_path, monkeypatch):
    source, ref, shared, grant, reader, state, bundle, text = complete_fixture(tmp_path, monkeypatch)
    request=CaptureRequest(project_id=ref['project_id'],title='Bad version',selection={
        'kind':'library_source','document_id':bundle['source']['id'],'snapshot':'0'*64})
    with pytest.raises(AssetConflict): save_capture(source,'alice',request,None,None,tmp_path/'library.sqlite')
    grant['manifest']['research_as_of']='2024-01-01'
    reader,_=runtime_at(shared,runtime_grant(grant))
    with pytest.raises(OrganizationExecutionUnavailable): reader.read_text(grant['manifest']['inputs'][0]['resource_id'])


def test_stored_complete_snapshot_corruption_is_not_trusted(tmp_path, monkeypatch):
    source, ref, _, _, _, _, _, _=complete_fixture(tmp_path, monkeypatch)
    with source.library.documents.connect() as db:
        saved=db.execute('SELECT snapshot FROM attachment_captures WHERE object_id=?',(ref['version_id'],)).fetchone()
        data=json.loads(saved[0]);data['bundle']['text']+='tampered'
        db.execute('UPDATE attachment_captures SET snapshot=? WHERE object_id=?',(json.dumps(data),ref['version_id']))
    with pytest.raises(AssetConflict): source.read_source('alice',ref)


@pytest.mark.parametrize('vintage,published,known,accepted',[
    ('dated_original','2025-02-01T12:30:00Z',None,True),
    ('known_as_of','2024-01-01','2026-01-01',False),
    ('known_as_of','2024-01-01','2025-01-31T08:00:00Z',True),
    ('unknown','2024-01-01',None,False),
    ('current_revised','2024-01-01','2024-01-02',False),
    ('dated_original',None,'2024-01-01',False)])
def test_complete_source_time_policy_matches_strict_library(vintage,published,known,accepted):
    bundle={'source':{'vintage':vintage,'published_at':published,'metadata':json.dumps({'known_at':known})}}
    if accepted: validate_source_cutoff(bundle,'2025-02-01')
    else:
        with pytest.raises(ValueError,match='complete_source_not_available_at_research_cutoff'):
            validate_source_cutoff(bundle,'2025-02-01')


def test_large_preparsed_capture_keeps_ordinary_upload_limit_and_exact_tail(tmp_path,monkeypatch):
    from sec_agent.research_foundation.task_attachments import parse_document, MAX_TEXT
    source,ref,_,grant,reader,state,bundle,text=complete_fixture(tmp_path,monkeypatch,repeats=45000)
    assert len(text)>MAX_TEXT
    with pytest.raises(ValueError,match='document_empty_or_extracted_text_limit'):
        parse_document('ordinary.md',text.encode())
    with source.library.documents.connect() as db:
        saved=db.execute('SELECT snapshot FROM attachment_captures WHERE object_id=?',(ref['version_id'],)).fetchone()
        snapshot=json.loads(saved[0])
    assert snapshot['schema_version']=='project_library_source_snapshot.v2'
    assert all('body' not in p for p in snapshot['bundle']['parents'])
    assert source.read_source('alice',ref)['source_bundle']==bundle
    rid=grant['manifest']['inputs'][0]['resource_id']
    tail=reader.read_text(rid,len(text)-100,100)
    assert tail['text']==text[-100:] and tail['next_offset'] is None and not tail['source_truncated']
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):reader.read_text(rid,len(text)-100,100)


def test_existing_v1_capture_is_read_without_rewriting_snapshot(tmp_path,monkeypatch):
    from sec_agent.research_foundation.project_source_captures import render_capture
    source,ref,_,_,_,_,bundle,text=complete_fixture(tmp_path,monkeypatch)
    snapshot={'schema_version':'project_library_source_snapshot.v1','kind':'library_source',
              'selection_mode':'complete_parsed_source','bundle':bundle}
    scope=source.library.scope('alice',ref['project_id'])
    saved=source.library.documents.add(scope,'legacy.md',render_capture(snapshot,'Old note').encode(),
        source_capture={'snapshot':snapshot,'note':'Old note'})
    oldref=next(v['ref'] for a in source.catalog('alice',ref['project_id'])['items'] for v in a['versions']
                if v['ref']['version_id']==saved['document_id'])
    with source.library.documents.connect() as db:
        before=db.execute('SELECT snapshot FROM attachment_captures WHERE object_id=?',(saved['document_id'],)).fetchone()[0]
    assert source.read_source('alice',oldref)['source_bundle']==bundle
    assert source.read_source('alice',oldref)['text']==text
    with source.library.documents.connect() as db:
        assert db.execute('SELECT snapshot FROM attachment_captures WHERE object_id=?',(saved['document_id'],)).fetchone()[0]==before
