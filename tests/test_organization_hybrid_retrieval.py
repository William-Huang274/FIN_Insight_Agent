"""Current authority before/after dense ranking and cache hits; no providers."""
from copy import deepcopy
from hashlib import sha256
import json
import sqlite3
from uuid import uuid4
from io import BytesIO

import numpy as np
import pytest

from sec_agent.research_foundation.organization_hybrid_retrieval import (
    preparation_nodes, publish_prepared_index, OrganizationHybridRetrieval)
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from test_organization_research_inputs import fixture
from test_organization_execution_access import runtime_at, runtime_grant
from test_organization_data_composition import organization, specialist


def setup(root):
    shared, preparation = fixture(root, body=b'Authorized original: revenue 123.40 USD.')
    reader, state = runtime_at(shared, runtime_grant(preparation))
    org, nodes = preparation_nodes(reader, workbench_url='http://localhost')
    return reader, state, org, nodes


def prepare(root, org, nodes, *, other=True):
    values = [deepcopy(row) for row in nodes]
    if other:
        # This is a real vector row, strongest match, outside the frozen inputs.
        values.append({**nodes[0], 'node_id':'SECRET-NODE', 'parent_document_id':'SECRET-DOCUMENT',
            'content':'Hidden acquisition secret', 'content_sha256':sha256(b'Hidden acquisition secret').hexdigest()})
    publish_prepared_index(root, org, values, [[.6,.8]]*len(nodes)+([[1.,0.]] if other else []),
        {'revenue':[1.,0.], 'semantic only':[1.,0.]}, model='synthetic-2d', provenance={'kind':'synthetic engineering only'})


def search(nav, query='revenue', **extra):
    return nav.navigate({'source_space':'organization', 'operation':'search', 'query':query, **extra})


def test_streamed_publication_preserves_exact_matrix_and_late_failure_is_unpublished(tmp_path):
    from sec_agent.research_foundation.organization_hybrid_retrieval import vector
    org=str(uuid4())
    nodes=[{'node_id':str(i),'parent_document_id':'doc','node_kind':'text',
            'content':'body','content_sha256':sha256(b'body').hexdigest()} for i in range(3)]
    raw=[[.6,.8],[1.,2.],[-3.,4.]]
    expected=BytesIO()
    np.save(expected,np.stack([vector(row,2) for row in raw]),allow_pickle=False)
    class LazyVectors:
        def __len__(self):return len(raw)
        def __getitem__(self,index):return raw[index]
        def __iter__(self):raise AssertionError('must not materialize all vectors')
    publish_prepared_index(tmp_path/'good',org,nodes,LazyVectors(),{'query':[1.,0.]},
        model='synthetic',provenance={'scope':'deterministic vectors'})
    matrix=tmp_path/'good'/org/'vectors.npy'
    assert matrix.read_bytes()==expected.getvalue()
    manifest=json.loads((matrix.parent/'index.json').read_text(encoding='utf8'))
    assert manifest['matrix_sha256']==sha256(expected.getvalue()).hexdigest()
    raw[-1]=[float('nan'),1.]
    with pytest.raises(ValueError,match='invalid_vector'):
        publish_prepared_index(tmp_path/'failed',org,nodes,LazyVectors(),{'query':[1.,0.]},
            model='synthetic',provenance={'scope':'late invalid vector'})
    assert (tmp_path/'failed'/org/'vectors.npy').exists()
    assert not (tmp_path/'failed'/org/'index.json').exists()
    raw[-1]=[-3.,4.]
    with pytest.raises(FileExistsError):
        publish_prepared_index(tmp_path/'failed',org,nodes,LazyVectors(),{'query':[1.,0.]},
            model='synthetic',provenance={'scope':'cannot overwrite failed attempt'})


def test_dense_prefilter_preview_readback_and_cache_hit_reauthorize(tmp_path):
    reader, state, org, nodes = setup(tmp_path/'source')
    prepare(tmp_path/'index', org, nodes)
    nav = OrganizationSourceNavigation(reader, workbench_url='http://localhost', retrieval_root=tmp_path/'index')
    first = search(nav, 'semantic only')
    assert first.items and not first.items[0]['retrieval']['lexical_node_ids']
    assert first.items[0]['retrieval']['dense_node_ids'] == [nodes[0]['node_id']]
    assert 'SECRET' not in json.dumps(first.model_dump()) and not first.items[0]['writer_citable']
    calls = state['calls']
    again = search(nav, 'semantic only')
    assert again.items[0]['retrieval']['cache_hit'] and state['calls'] > calls
    read = nav.navigate(again.items[0]['readback']).items[0]
    assert read['passage'] == nodes[0]['content'] and read['writer_citable']
    state['status'] = 404
    with pytest.raises(OrganizationExecutionUnavailable): search(nav, 'semantic only')
    with pytest.raises(OrganizationExecutionUnavailable): nav.source(read['passage_id'])
    with sqlite3.connect(tmp_path/'index'/org/'rank-cache.sqlite') as db:
        payload = db.execute('SELECT value FROM ranks').fetchone()[0]
    assert 'Authorized original' not in payload and 'SECRET' not in payload


def test_same_query_other_execution_and_other_org_do_not_share_rank_cache(tmp_path):
    reader, state, org, nodes = setup(tmp_path/'source')
    prepare(tmp_path/'index', org, nodes)
    nav = OrganizationSourceNavigation(reader, workbench_url='http://localhost', retrieval_root=tmp_path/'index')
    assert not search(nav).items[0]['retrieval']['cache_hit']
    # A separately issued valid execution over identical data must have its own cache key.
    grant = deepcopy(state['grant']); grant['execution_id'] = grant['thread_id'] = str(uuid4())
    from types import SimpleNamespace
    second, _ = runtime_at(SimpleNamespace(workspace=reader.workspace), grant)
    other = OrganizationSourceNavigation(second, workbench_url='http://localhost', retrieval_root=tmp_path/'index')
    assert not search(other).items[0]['retrieval']['cache_hit']
    foreign_reader, _, foreign_org, foreign_nodes = setup(tmp_path/'foreign')
    prepare(tmp_path/'index', foreign_org, foreign_nodes)
    foreign = OrganizationSourceNavigation(foreign_reader, workbench_url='http://localhost', retrieval_root=tmp_path/'index')
    result = search(foreign)
    assert not result.items[0]['retrieval']['cache_hit']
    assert nodes[0]['node_id'] not in json.dumps(result.model_dump())


@pytest.mark.parametrize('fault', ['missing_index','missing_query','wrong_org','stale_content','corrupt_matrix','poison_cache'])
def test_index_or_cache_mismatch_fails_without_lexical_or_provider_fallback(tmp_path, fault):
    reader, state, org, nodes = setup(tmp_path/'source')
    root = tmp_path/'index'
    if fault != 'missing_index': prepare(root, org, nodes)
    nav = OrganizationSourceNavigation(reader, workbench_url='http://localhost', retrieval_root=root)
    if fault == 'poison_cache':
        search(nav)
        with sqlite3.connect(root/org/'rank-cache.sqlite') as db:
            db.execute('UPDATE ranks SET value=?', (json.dumps({'ordered':['SECRET-NODE'], 'dense':['SECRET-NODE'], 'lexical':[]}),))
    if fault in {'wrong_org','stale_content'}:
        path = root/org/'index.json'; spec = json.loads(path.read_text())
        if fault == 'wrong_org': spec['organization_id'] = str(uuid4())
        else: spec['records'][0]['content_sha256'] = '0'*64
        path.write_text(json.dumps(spec))
    if fault == 'corrupt_matrix': (root/org/'vectors.npy').write_bytes(b'corrupt')
    with pytest.raises((ValueError, OrganizationExecutionUnavailable)):
        search(nav, 'uncached new query' if fault == 'missing_query' else 'revenue')


@pytest.mark.parametrize('warm', [False, True])
def test_revocation_during_ranking_or_cache_hit_returns_no_preview(tmp_path, monkeypatch, warm):
    reader, state, org, nodes = setup(tmp_path/'source')
    prepare(tmp_path/'index', org, nodes)
    ranker = OrganizationHybridRetrieval(reader, tmp_path/'index')
    if warm:
        ranker.rank(nodes, 'revenue', reader.authority.manifest_digest[7:], nodes)
    check = reader._after
    count = []
    def revoke_after_entry(before):
        count.append(True)
        if len(count) == 2: state['status'] = 404
        check(before)
    monkeypatch.setattr(reader, '_after', revoke_after_entry)
    with pytest.raises(OrganizationExecutionUnavailable):
        ranker.rank(nodes, 'revenue', reader.authority.manifest_digest[7:], nodes)
    with sqlite3.connect(tmp_path/'index'/org/'rank-cache.sqlite') as db:
        assert db.execute('SELECT COUNT(*) FROM ranks').fetchone()[0] == int(warm)


def test_real_specialist_composition_consumes_explicit_scoped_hybrid(organization, tmp_path, monkeypatch):
    factory, authority = organization
    org, nodes = preparation_nodes(factory.reader, workbench_url=factory.workbench_url)
    prepare(tmp_path/'index', org, nodes)
    factory.retrieval_root = tmp_path/'index'
    monkeypatch.setenv('FINSIGHT_SOURCE_HYBRID','1')
    monkeypatch.setenv('FINSIGHT_SOURCE_RAG_CACHE_PATH',str(tmp_path/'must-not-open'))
    from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
    with specialist(factory) as opened:
        result = opened.source_reader(SourceDocumentRequest(source_space='organization',operation='search',query='semantic only'))
        assert result['status']=='success' and result['items'][0]['retrieval']['provider_calls']==0
        assert result['items'][0]['retrieval']['dense_node_ids']==[nodes[0]['node_id']]
        authority['status']=404
        with pytest.raises(OrganizationExecutionUnavailable):
            opened.source_reader(SourceDocumentRequest(source_space='organization',operation='search',query='semantic only'))
    assert not (tmp_path/'must-not-open').exists()


def test_new_publication_identity_requires_preparation_and_cannot_use_old_cached_ids(tmp_path):
    reader, state, org, nodes = setup(tmp_path/'source')
    prepare(tmp_path/'index', org, nodes)
    ranker = OrganizationHybridRetrieval(reader,tmp_path/'index')
    ranker.rank(nodes,'revenue',reader.authority.manifest_digest[7:],nodes)
    newer = deepcopy(state['grant'])
    manifest = json.loads(newer['manifest_text'])
    manifest['inputs'][0]['ref']['version_id']='UPLOAD::'+uuid4().hex
    newer['inputs'][0]['binding']['ref']=deepcopy(manifest['inputs'][0]['ref'])
    newer['manifest_text']=json.dumps(manifest,separators=(',',':'))
    newer['manifest_digest']='sha256:'+sha256(newer['manifest_text'].encode()).hexdigest()
    from types import SimpleNamespace
    other,_=runtime_at(SimpleNamespace(workspace=reader.workspace),newer)
    document=OrganizationSourceNavigation._identity(manifest['inputs'][0])
    changed=[{**nodes[0],'parent_document_id':document,'node_id':document.replace('ORGDOC::','ORGSECTION::')+':0:leaf'}]
    with pytest.raises(ValueError,match='version_not_prepared'):
        OrganizationHybridRetrieval(other,tmp_path/'index').rank(changed,'revenue',other.authority.manifest_digest[7:],changed)
