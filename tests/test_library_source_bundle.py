"""Recovery failures must precede organization publication or any paid work."""
from contextlib import closing
from copy import deepcopy
import json
import sqlite3

import numpy as np
import pytest

from retrieval.library_chunks import split_parent
from retrieval.library_source_bundle import build_source_bundle, recover_source, reusable_vectors, text_digest, VectorReuseVerifier
from retrieval.library_source_bundle import compact_source_bundle, expand_source_bundle
from retrieval.library_vectors import DIM, digest, vector_key
from scripts.data_retrieval.prepare_library_source_bundles import prepare


def source_rows(text):
    source = dict(id='SRC::fixture', title='Example 2024 年报', url='https://example.test/report',
                  access_state='readable', digest=text_digest(text), published_at='2025-02-01',
                  vintage='dated_original', metadata=json.dumps(dict(period_end='2024-12-31',
                      unit='USD millions', parse_revision={'supersedes': 'SRC::old'},
                      document_coverage={'complete_document': False})))
    parents = [dict(id=f'PASSAGE::{i}', source_id=source['id'], locator=f'text-part:{i}',
                    body=text[max(0, start-250):start+5200],
                    digest=text_digest(text[max(0, start-250):start+5200]))
               for i, start in enumerate(range(0, len(text), 5200))]
    return source, parents


def database(path, text):
    source, parents = source_rows(text)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('CREATE TABLE sources(id,title,url,access_state,digest,published_at,vintage,metadata)')
        db.execute('INSERT INTO sources VALUES(:id,:title,:url,:access_state,:digest,:published_at,:vintage,:metadata)', source)
        db.execute('CREATE TABLE passages(id,source_id,locator,body,digest)')
        db.executemany('INSERT INTO passages VALUES(:id,:source_id,:locator,:body,:digest)', parents)
        db.execute('CREATE TABLE retrieval_chunks(id,source_id,parent_id,ordinal,char_start,char_end,body,digest,locator,context,kind,flags)')
        chunks = [chunk for parent in parents for chunk in split_parent(parent, source['title'])]
        db.executemany('INSERT INTO retrieval_chunks VALUES(:id,:source_id,:parent_id,:ordinal,:char_start,:char_end,:body,:digest,:locator,:context,:kind,:flags)', chunks)
        db.execute('CREATE TABLE edges(id,source_id,status,qualifiers)')
        db.execute('INSERT INTO edges VALUES(?,?,?,?)', ('edge', source['id'], 'announced', '{"unit":"MW"}'))
        db.execute('CREATE TABLE edge_chunk_links(edge_id,chunk_id,binding,evidence_index,span_start,span_end)')
        db.execute('INSERT INTO edge_chunk_links VALUES(?,?,?,?,?,?)', ('edge', chunks[0]['id'], 'exact_quote', 0, 0, 5))
        db.execute('CREATE TABLE edge_chunk_coverage(edge_id,status,payload)')
        db.execute('INSERT INTO edge_chunk_coverage VALUES(?,?,?)', ('edge', 'quote_bound', '{"issues":[]}'))
    return source['id']


def bundle_at(path, sid):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        return build_source_bundle(db, sid, digest(path))


def vectors_for(bundle, root):
    root.mkdir()
    model = 'qwen3.7-text-embedding'
    vectors, mapping = [], []
    with closing(sqlite3.connect(root/'chunk-embeddings.sqlite')) as db, db:
        db.executescript('CREATE TABLE vectors(key,vector); CREATE TABLE requests(id,status); CREATE TABLE request_items(request_id,key);')
        db.execute('INSERT INTO requests VALUES(?,?)', ('receipt', 'completed'))
        for i, chunk in enumerate(bundle['chunks']):
            vector = np.random.default_rng(i).normal(size=DIM).astype(np.float32)
            key = vector_key(chunk['context']+'\n'+chunk['body'], model)
            db.execute('INSERT INTO vectors VALUES(?,?)', (key, vector.tobytes()))
            db.execute('INSERT INTO request_items VALUES(?,?)', ('receipt', key))
            vectors.append(vector / np.linalg.norm(vector))
            mapping.append(dict(id=chunk['id'], source_id=chunk['source_id'], vector_index=i))
    matrix = np.asarray(vectors, dtype=np.float32)
    np.save(root/'chunk-vectors.npy', matrix)
    (root/'chunk-vector-map.json').write_text(json.dumps(mapping))
    manifest = dict(version='library-chunks.v1', library_sha256=bundle['library_sha256'],
                    embedding_model=model, dimensions=DIM, chunks=len(mapping), unique_vectors=len(matrix),
                    matrix_sha256=digest(root/'chunk-vectors.npy'), mapping_sha256=digest(root/'chunk-vector-map.json'))
    (root/'chunk-vector-manifest.json').write_text(json.dumps(manifest))
    return manifest, matrix, mapping


def test_long_unicode_source_preserves_text_positions_metadata_and_graph(tmp_path):
    text = ('单位 百万美元；收入 $10.25。😀\r\n原始换行\n' * 4200) + '原始最后一行'
    assert len(text) > 100000
    path = tmp_path/'library.sqlite'
    sid = database(path, text)
    before = digest(path)
    bundle = bundle_at(path, sid)
    assert bundle['text'] == text
    assert len(bundle['chunks']) > 20
    assert bundle['source']['digest'] == text_digest(text)
    metadata = json.loads(bundle['source']['metadata'])
    assert metadata['period_end'] == '2024-12-31' and metadata['unit'] == 'USD millions'
    assert metadata['parse_revision']['supersedes'] == 'SRC::old'
    assert not metadata['document_coverage']['complete_document']
    for chunk in bundle['chunks']:
        assert text[chunk['source_char_start']:chunk['source_char_end']] == chunk['body']
    assert bundle['edge_chunk_links'][0]['chunk_id'] == bundle['chunks'][0]['id']
    assert bundle['edges'][0]['qualifiers'] == '{"unit":"MW"}'
    assert not bundle['organization_authorization'] and not bundle['numeric_fact_authority']
    assert digest(path) == before


@pytest.mark.parametrize('length', [1, 5200, 5201, 10400, 10401])
def test_boundary_lengths_and_unordered_storage(length):
    source, parents = source_rows('数' * length)
    assert recover_source(source, list(reversed(parents)))[0] == '数' * length


def raw_rows():
    text = '{"单位":"USD million","value":"12.3400"}\r\n' * 200
    source, _ = source_rows(text)
    parents = [dict(id=f'RAW:{i}',source_id=source['id'],locator=f'raw text chars {i}-{min(i+3500,len(text))}',
                    body=text[i:i+3500],digest=text_digest(text[i:i+3500])) for i in range(0,len(text),3500)]
    return text, source, parents


def test_raw_text_exact_offsets_and_original_digest():
    text, source, parents = raw_rows()
    actual, ordered = recover_source(source,list(reversed(parents)))
    assert actual == text
    for p in ordered:
        assert actual[p['source_char_start']:p['source_char_end']] == p['body']


@pytest.mark.parametrize('mutation,error',[
    ('gap','parent_sequence_gap_or_overlap'),('tail','recovered_source_digest_mismatch'),
    ('duplicate','parent_identity_mismatch'),('span','parent_window_length_mismatch'),
    ('content','parent_digest_mismatch'),('source','parent_identity_mismatch'),
    ('binary','recovered_source_digest_mismatch'),('html','unsupported_parent_projection')])
def test_raw_text_rejects_missing_or_different_original(mutation,error):
    _, source, parents = raw_rows()
    if mutation == 'gap': parents.pop(0)
    elif mutation == 'tail': parents.pop()
    elif mutation == 'duplicate': parents.append(deepcopy(parents[0]))
    elif mutation == 'span': parents[0]['locator']='raw text chars 0-3501'
    elif mutation == 'content': parents[0]['body']='X'+parents[0]['body'][1:]
    elif mutation == 'source': parents[0]['source_id']='other'
    elif mutation == 'binary': source['digest']=text_digest('original HTML bytes')
    elif mutation == 'html':
        for p in parents: p['locator']=p['locator'].replace('raw text','HTML text')
    with pytest.raises(ValueError,match=error): recover_source(source,parents)


@pytest.mark.parametrize('mutation,error', [
    ('gap', 'parent_sequence_gap'), ('tail', 'recovered_source_digest_mismatch'),
    ('duplicate', 'parent_identity_mismatch'), ('source', 'parent_identity_mismatch'),
    ('locator', 'unsupported_parent_projection'), ('digest', 'parent_digest_mismatch'),
    ('overlap', 'parent_overlap_mismatch'), ('newline', 'recovered_source_digest_mismatch'),
])
def test_corrupt_recovery_fails_without_guessing(mutation, error):
    source, parents = source_rows(('原文😀\r\n' * 3000))
    if mutation == 'gap': parents.pop(1)
    elif mutation == 'tail': parents.pop()
    elif mutation == 'duplicate': parents.append(deepcopy(parents[0]))
    elif mutation == 'source': parents[0]['source_id'] = 'other'
    elif mutation == 'locator': parents[0]['locator'] = 'page:1'
    elif mutation == 'digest': parents[0]['digest'] = '0'*64
    elif mutation == 'overlap':
        parents[1]['body'] = 'X' + parents[1]['body'][1:]
        parents[1]['digest'] = text_digest(parents[1]['body'])
    elif mutation == 'newline': source['digest'] = text_digest(('原文😀\r\n' * 3000).replace('\r\n', '\n'))
    with pytest.raises(ValueError, match=error): recover_source(source, parents)


@pytest.mark.parametrize('statement,error', [
    ("DELETE FROM retrieval_chunks", 'chunk_coverage_tail_missing'),
    ("DELETE FROM retrieval_chunks WHERE char_start=0", 'chunk_coverage_gap'),
    ("UPDATE retrieval_chunks SET char_start=-1", 'chunk_parent_or_content_mismatch'),
    ("UPDATE edge_chunk_links SET chunk_id='other-source-chunk'", 'edge_chunk_source_mismatch'),
    ("UPDATE edge_chunk_links SET span_end=1000000", 'edge_chunk_span_mismatch'),
    ("DELETE FROM edge_chunk_coverage", 'edge_coverage_record_missing'),
])
def test_missing_or_cross_source_evidence_is_rejected(tmp_path, statement, error):
    path = tmp_path/'library.sqlite'
    sid = database(path, 'Annual report. ' * 800)
    with closing(sqlite3.connect(path)) as db, db: db.execute(statement)
    with pytest.raises(ValueError, match=error): bundle_at(path, sid)


def test_exact_embedding_reuse_and_wrong_row_context_receipt_rejected(tmp_path):
    path = tmp_path/'library.sqlite'
    sid = database(path, 'Annual report. ' * 800)
    bundle = bundle_at(path, sid)
    root = tmp_path/'index'
    manifest, matrix, mapping = vectors_for(bundle, root)
    with closing(sqlite3.connect(root/'chunk-embeddings.sqlite')) as cache:
        records, actual = reusable_vectors(bundle, manifest, matrix, mapping, cache)
        assert np.array_equal(actual, matrix) and len(records) == len(bundle['chunks'])
        wrong = deepcopy(mapping)
        wrong[0]['vector_index'] = 1
        with pytest.raises(ValueError, match='cached_vector_matrix_mismatch'):
            reusable_vectors(bundle, manifest, matrix, wrong, cache)
        changed = deepcopy(bundle)
        changed['chunks'][0]['context'] += ' revised'
        with pytest.raises(ValueError, match='exact_embedding_input_receipt_missing'):
            reusable_vectors(changed, manifest, matrix, mapping, cache)
        with pytest.raises(ValueError, match='duplicate_vector_mapping'):
            reusable_vectors(bundle, manifest, matrix, mapping + mapping[:1], cache)
        cache.execute("UPDATE requests SET status='failed_usage_unknown'")
        with pytest.raises(ValueError, match='exact_embedding_input_receipt_missing'):
            reusable_vectors(bundle, manifest, matrix, mapping, cache)


@pytest.mark.parametrize('value', [0.0, float('nan'), float('inf'), 1e38])
def test_invalid_cached_vectors_cannot_be_reused(tmp_path, value):
    path = tmp_path/'library.sqlite'
    sid = database(path, 'Annual report. ' * 800)
    bundle = bundle_at(path, sid)
    root = tmp_path/'index'
    manifest, matrix, mapping = vectors_for(bundle, root)
    vector = np.full(DIM, value, dtype=np.float32)
    with closing(sqlite3.connect(root/'chunk-embeddings.sqlite')) as cache:
        cache.execute('UPDATE vectors SET vector=?', (vector.tobytes(),))
        with np.errstate(over='ignore', invalid='ignore'), pytest.raises(ValueError, match='cached_vector_matrix_mismatch'):
            reusable_vectors(bundle, manifest, matrix, mapping, cache)


def test_offline_export_is_readonly_failures_retained_no_overwrite(tmp_path, monkeypatch):
    import socket
    def deny(*args, **kwargs): raise AssertionError('unexpected_network')
    monkeypatch.setattr(socket.socket, 'connect', deny)
    source_dir = tmp_path/'sources'
    source_dir.mkdir()
    path = source_dir/'library.sqlite'
    sid = database(path, 'Annual report. ' * 800)
    bundle = bundle_at(path, sid)
    root = tmp_path/'index'
    vectors_for(bundle, root)
    before = {p: digest(p) for p in [path, *root.iterdir()]}
    out = tmp_path/'out'
    result = prepare(path, root, [sid], out)
    assert result['status'] == 'verified' and result['provider_calls'] == 0
    assert not result['organization_published']
    assert before == {p: digest(p) for p in before}
    with pytest.raises(FileExistsError): prepare(path, root, [sid], out)
    with pytest.raises(ValueError, match='output_must_not_modify_source_directory'):
        prepare(path, root, [sid], root/'nested')
    result = prepare(path, root, [sid, 'missing'], tmp_path/'failed')
    assert result['status'] == 'failed'
    assert [r['status'] for r in result['sources']] == ['verified', 'failed']
    assert result['sources'][1]['error'] == 'source_missing'


def test_scope_inventory_preserves_failed_and_excluded_sources(tmp_path):
    from scripts.data_retrieval.audit_library_source_intake import audit
    folder=tmp_path/'source'
    folder.mkdir()
    path=folder/'library.sqlite'
    database(path,'Original source. '*800)
    with closing(sqlite3.connect(path)) as db, db:
        row=db.execute('SELECT * FROM sources').fetchone()
        db.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?,?)',('broken',*row[1:]))
        excluded=list(row);excluded[0]='old';excluded[3]='superseded_parse'
        db.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?,?)',excluded)
    before=digest(path)
    report=audit(path,tmp_path/'inventory.json')
    assert report['source_count']==3
    assert report['intake_statuses']=={'parsed_text_recoverable':1,'requires_adapter_or_source_repair':1,'source_not_currently_readable':1}
    assert report['repair_reasons']=={'source_not_readable_or_empty':1}
    assert report['access_states']=={'readable':2,'superseded_parse':1}
    assert not report['full_scope_retrieval_accepted'] and digest(path)==before


def test_full_scope_vector_inventory_keeps_failure_denominator(tmp_path):
    from scripts.data_retrieval.audit_library_source_intake import audit
    folder=tmp_path/'source'; folder.mkdir()
    path=folder/'library.sqlite'
    sid=database(path,'Original source. '*800)
    with closing(sqlite3.connect(path)) as db, db:
        row=db.execute('SELECT * FROM sources').fetchone()
        db.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?,?)',('missing',*row[1:]))
    index=tmp_path/'index';vectors_for(bundle_at(path,sid),index)
    report=audit(path,tmp_path/'inventory.json',index)
    assert report['source_count']==2 and report['verified_vector_sources']==1
    assert report['verified_vectors']>1 and not report['full_scope_retrieval_accepted']
    assert report['repair_reasons']=={'source_not_readable_or_empty':1}
    with closing(sqlite3.connect(index/'chunk-embeddings.sqlite')) as db, db:
        db.execute("UPDATE requests SET status='failed_usage_unknown'")
    report=audit(path,tmp_path/'failed.json',index)
    assert report['verified_vector_sources']==0
    assert report['verification_failures']=={'exact_embedding_input_receipt_missing':1,'parent_identity_mismatch':1}
    with pytest.raises(ValueError,match='audit_output_must_not_change_index_directory'):
        audit(path,index/'forbidden.json',index)


def test_batch_receipts_do_not_hide_cross_source_mapping_or_cache_drift(tmp_path):
    path=tmp_path/'library.sqlite'
    sid=database(path,'Annual source. '*800)
    bundle=bundle_at(path,sid)
    index=tmp_path/'index';manifest,matrix,mapping=vectors_for(bundle,index)
    with closing(sqlite3.connect(index/'chunk-embeddings.sqlite')) as cache:
        statements=[];cache.set_trace_callback(statements.append)
        verifier=VectorReuseVerifier(manifest,matrix,mapping,cache)
        verifier.verify(bundle);verifier.verify(bundle)
        assert sum('JOIN requests' in s for s in statements)==1
        wrong=deepcopy(mapping);wrong[0]['source_id']='other'
        with pytest.raises(ValueError,match='vector_mapping_identity_mismatch'):
            VectorReuseVerifier(manifest,matrix,wrong,cache).verify(bundle)
        # Receipt batching never replaces exact value checks at use time.
        cache.execute('DELETE FROM vectors')
        with pytest.raises(ValueError,match='exact_embedding_input_receipt_missing'):
            verifier.verify(bundle)


@pytest.mark.parametrize('origin,expected',[
    ({'origin':'existing_library'},'hierarchical_indexed_nodes'),
    ({'import_origin':'existing_public_library','coverage':'indexed_nodes_only'},'hierarchical_indexed_nodes'),
    ({'import_origin':'094 frozen public survey originals'},'survey_read_envelope')])
def test_inventory_names_original_digest_contract_without_claiming_text(origin,expected):
    from scripts.data_retrieval.audit_library_source_intake import source_protocol
    source={'metadata':json.dumps(origin)}
    protocol,basis=source_protocol(source,[{'locator':"['Section'] / 1"}])
    assert protocol==expected and basis!='parsed_utf8_text'


def test_unrecovered_document_can_verify_stored_vectors_without_becoming_complete(tmp_path):
    from scripts.data_retrieval.audit_library_source_intake import audit
    from retrieval.library_source_bundle import validated_stored_chunks
    folder=tmp_path/'source';folder.mkdir();path=folder/'library.sqlite'
    sid=database(path,'Original source. '*800)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("UPDATE passages SET locator='original indexed section'")
        db.execute("UPDATE sources SET digest=?,metadata=?",(text_digest('raw HTML bytes'),json.dumps({'origin':'existing_library'})))
    with closing(sqlite3.connect(path)) as db:
        db.row_factory=sqlite3.Row
        parents=[dict(p) for p in db.execute('SELECT * FROM passages')]
        chunks=validated_stored_chunks(db,sid,parents)
        assert all('source_char_start' not in c for c in chunks)
        bundle={'source':dict(db.execute('SELECT * FROM sources').fetchone()),'chunks':chunks,'library_sha256':digest(path)}
    index=tmp_path/'index';vectors_for(bundle,index)
    report=audit(path,tmp_path/'inventory.json',index,'2025-03-01')
    assert report['verified_vector_sources']==1 and report['vector_compatibility_verified']
    assert report['repair_reasons']=={'unsupported_parent_projection':1}
    row=report['sources'][0]
    assert 'capture_size_within_limit' not in row and 'organization_time_eligible' not in row
    assert not report['organization_publication_verified'] and not report['full_scope_retrieval_accepted']


def test_compact_source_roundtrip_and_offset_tampering(tmp_path):
    path=tmp_path/'library.sqlite'
    sid=database(path,('Original 中文 😀\r\n'*800))
    bundle=bundle_at(path,sid)
    compact=compact_source_bundle(bundle)
    assert expand_source_bundle(compact)==bundle
    assert all('body' not in r for r in compact['parents']+compact['chunks'])
    assert len(json.dumps(compact)) < len(json.dumps(bundle))
    assert expand_source_bundle(bundle) is bundle
    for table in ('parents','chunks'):
        wrong=deepcopy(compact);wrong[table][0]['source_char_start']+=1
        with pytest.raises(ValueError,match='source_bundle_offset_content_mismatch'):expand_source_bundle(wrong)
    wrong=deepcopy(compact);wrong['text']+='changed'
    with pytest.raises(ValueError,match='recovered_source_digest_mismatch'):expand_source_bundle(wrong)


def test_new_geometry_storage_preserves_legacy_and_original_identity(tmp_path):
    path=tmp_path/'library.sqlite';sid=database(path,'Original disclosure. '*600)
    original=bundle_at(path,sid)
    legacy=compact_source_bundle(original)
    assert legacy['format']=='library-source-offset-bundle.v1'
    enriched={**original,'table_period_context':{'format':'source-table-periods.v1',
        'tables':[{'text':'原文', 'cells':['repeated field']*100}]}}
    compressed=compact_source_bundle(enriched)
    assert compressed['format']=='library-source-offset-bundle.v2'
    assert 'table_period_context' not in compressed
    assert expand_source_bundle(compressed)==enriched
    assert compressed['text']==original['text'] and compressed['source']==original['source']
    assert expand_source_bundle(legacy)==original
    wrong=deepcopy(compressed);wrong['table_period_context_storage']['sha256']='0'*64
    with pytest.raises(ValueError,match='source_table_storage'):expand_source_bundle(wrong)
    wrong=deepcopy(compressed);wrong['format']=legacy['format']
    with pytest.raises(ValueError,match='storage_version_invalid'):expand_source_bundle(wrong)
    wrong=deepcopy(compressed);wrong['table_period_context']={}
    with pytest.raises(ValueError,match='structure_storage_invalid'):expand_source_bundle(wrong)
