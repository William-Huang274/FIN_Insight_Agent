import pytest
from retrieval.source_window_candidates import adjacent_nodes, expand_candidates, order_source_windows


def test_original_coordinates_cross_storage_parts_but_never_versions_or_gaps():
    links=adjacent_nodes([('v1',0,100,'a'),('v1',90,200,'b'),
                          ('v1',200,300,'c'),('v1',301,400,'gap'),('v2',90,200,'other')])
    assert links['a']==['b'] and links['b']==['a','c']
    assert links['c']==['b'] and links['gap']==[] and links['other']==[]
    with pytest.raises(ValueError,match='invalid_location'):
        adjacent_nodes([('v1',0,100,'a'),('v2',0,100,'a')])


def test_bounded_windows_preserve_leading_union_without_query_or_label_rules():
    base=[f'b{i}' for i in range(48)]
    extra=[f'n{i}' for i in range(12)]
    docs={n:'d' for n in base+extra}
    links={base[i]:extra[2*i:2*i+2] for i in range(6)}
    result,receipt=expand_candidates(base,base[:24],links,docs)
    assert result==base[:36]+extra
    assert receipt['displaced_node_ids']==base[36:]
    assert len(result)==len(set(result))==48
    unchanged,_=expand_candidates(base,base[:24],{},docs)
    assert unchanged==base


def test_filtered_neighbors_never_loaded_and_cross_document_links_fail():
    result,receipt=expand_candidates(['a'],['a'],{'a':['hidden','b']},{'a':'d','b':'d'})
    assert result==['a','b'] and receipt['added_node_ids']==['b']
    assert all('hidden' not in row.values() for row in receipt['links'])
    with pytest.raises(ValueError,match='cross_document'):
        expand_candidates(['a'],['a'],{'a':['b']},{'a':'d','b':'another'})
    with pytest.raises(ValueError,match='unverified_population'):
        expand_candidates(['a'],['hidden'],{}, {'a':'d'})


def test_offline_neighbors_verify_navigation_and_share_coordinate_contract(tmp_path):
    import json,sqlite3,zlib
    from hashlib import sha256
    from scripts.engineering.source_window_diagnostics import verified_neighbors
    records={}
    with sqlite3.connect(tmp_path/'navigation.sqlite') as db:
        db.execute('CREATE TABLE nodes(node_id TEXT PRIMARY KEY,payload BLOB)')
        for document,suffix,start,end in [('ORGDOC::v1','a',0,100),('ORGDOC::v1','b',90,200),('ORGDOC::v2','c',90,200)]:
            n='ORGSECTION::'+document[8:]+':'+suffix
            row={'node_id':n,'parent_document_id':document,'original_source':{
                'source_char_start':start,'source_char_end':end,'parent_id':'storage-part-'+suffix}}
            raw=json.dumps(row).encode()
            db.execute('INSERT INTO nodes VALUES (?,?)',(n,zlib.compress(raw)))
            records[n]={'document_id':document,'navigation_sha256':sha256(raw).hexdigest()}
    a,b='ORGSECTION::v1:a','ORGSECTION::v1:b'
    assert verified_neighbors(tmp_path,records,[a])=={a:[b],b:[a]}
    with sqlite3.connect(tmp_path/'navigation.sqlite') as db:
        db.execute('UPDATE nodes SET payload=? WHERE node_id=?',(zlib.compress(b'{}'),b))
    with pytest.raises(ValueError,match='identity_mismatch'):verified_neighbors(tmp_path,records,[a])


def test_window_order_preserves_exact_rows_and_ranks_companions_already_in_pool():
    base=['anchor',*[f'x{i}' for i in range(20)],'companion']
    docs={n:'d' for n in base}
    ids,proof=expand_candidates(base,['anchor'],{'anchor':['companion']},docs)
    assert not proof['added_node_ids']  # Already recalled, but ranked too low.
    rows=[{'node_id':n,'parent_document_id':'d','content':n,'score':1/(i+1)} for i,n in enumerate(ids)]
    selected,windows=order_source_windows(rows,proof)
    assert [r['node_id'] for r in selected[:2]]==['anchor','companion']
    assert {r['node_id'] for r in selected}==set(base)
    assert all(next(r for r in selected if r['node_id']==old['node_id']) is old for old in rows)
    assert windows==[{'anchor':'anchor','companions':['companion']}]
    rows[-1]['parent_document_id']='different-version'
    with pytest.raises(ValueError,match='unverified_companion'):order_source_windows(rows,proof)


def test_product_uses_same_window_policy_and_rechecks_revocation(tmp_path,monkeypatch):
    from test_organization_candidate_index import prepared,query
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_CANDIDATE_POLICY','needs_window.v2')
    nav,reader,state,_,grant=prepared(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='requires_verified_navigation'):
        nav.hybrid.rank([], 'new unprepared query', 'invalid', [])
    nav.warm_release()
    ci=nav._candidate_index
    document=nav._identity(grant['manifest']['inputs'][0])
    seed=next(n for n,adjacent in ci.window_neighbors.items()
              if adjacent and ci.rows[n]['parent_document_id']==document)
    neighbor=ci.window_neighbors[seed][0]
    original=nav.hybrid.rank
    def one_seed(rows,*args,**kwargs):
        _,receipt=original(rows,*args,**kwargs)
        receipt.update(dense_node_ids=[seed],candidate_node_ids=[seed])
        return [ci.rows[seed]],receipt
    monkeypatch.setattr(nav.hybrid,'rank',one_seed)
    request=query(document_id=document,organization_query_planning='conservative.v5')
    result=nav.navigate(request)
    receipt=result.items[0]['retrieval']
    assert neighbor in receipt['source_window']['added_node_ids']
    assert neighbor in receipt['candidate_node_ids']
    assert all(ci.rows[n]['parent_document_id']==document for n in receipt['candidate_node_ids'])
    assert nav.navigate(request).items[0]['retrieval']['response_cache_hit']
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):nav.navigate(request)
