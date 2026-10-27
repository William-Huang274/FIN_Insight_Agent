from copy import deepcopy
import pytest
from retrieval.source_structure_selection import select_structure_companions
from retrieval.source_window_selection import select_context_companions
from retrieval.source_window_candidates import POLICY


def fixture():
    rows=[{'node_id':str(i),'parent_document_id':'d','original_source':{'source_char_start':0,'source_char_end':100},
           'source_structure':{'status':'verified_original_coordinates','tables':[],'footnotes':[]}} for i in range(30)]
    table={'source_char_start':10,'source_char_end':50,'content_sha256':'a'*64}
    rows[0]['source_structure']['tables']=[table]
    rows[20]['source_structure']['footnotes']=[{'table':deepcopy(table),'marker':'1','source_char_start':51,
          'source_char_end':70,'binding':'explicit_post_table_marker'}]
    proof={'policy':POLICY,'links':[{'seed':'0','neighbor':'1'},{'seed':'0','neighbor':'20'}]}
    return rows,proof


def test_explicit_note_completes_table_even_when_best_adjacent_block_is_already_core():
    rows,proof=fixture()
    assert not select_context_companions(rows,proof)[1]['promotions']
    selected,receipt=select_structure_companions(rows,proof)
    assert [r['node_id'] for r in selected[:3]]==['0','20','1']
    assert receipt['promotions'][0]['basis']=='explicit_post_table_marker'
    assert set(str(i) for i in range(8)) <= {r['node_id'] for r in selected[:10]}
    assert all(next(r for r in selected if r['node_id']==old['node_id']) is old for old in rows)


def test_explicit_relationship_does_not_require_a_dense_seed_or_new_fetch():
    rows,proof=fixture();proof['links']=[]
    assert select_structure_companions(rows,proof)[0][1]['node_id']=='20'
    rows=[r for r in rows if r['node_id']!='20']
    assert select_structure_companions(rows,proof)[0]==rows


def test_cross_document_and_changed_table_hash_never_bind():
    rows,proof=fixture();proof['links']=[]
    rows[20]['parent_document_id']='other-version'
    assert not select_structure_companions(rows,proof)[1]['promotions']
    rows[20]['parent_document_id']='d'
    rows[20]['source_structure']['footnotes'][0]['table']['content_sha256']='b'*64
    assert not select_structure_companions(rows,proof)[1]['promotions']


@pytest.mark.parametrize('part',['note','table'])
def test_forged_original_coordinates_fail_closed(part):
    rows,proof=fixture()
    rows[20 if part=='note' else 0]['original_source']={'source_char_start':200,'source_char_end':300}
    with pytest.raises(ValueError,match='invalid_'):select_structure_companions(rows,proof)


def test_protection_and_total_promotion_budget_remain_two():
    rows,proof=fixture()
    for anchor,other in [(2,21),(3,22)]:
        rows[anchor]['source_structure']=deepcopy(rows[0]['source_structure'])
        rows[other]['source_structure']=deepcopy(rows[20]['source_structure'])
        rows[anchor]['parent_document_id']=rows[other]['parent_document_id']=str(anchor)
    selected,receipt=select_structure_companions(rows,proof)
    assert len(receipt['promotions'])==2
    assert {str(i) for i in range(8)} <= {r['node_id'] for r in selected[:10]}
    assert len({r['node_id'] for r in selected})==len(rows)


def test_unverified_structure_only_uses_existing_verified_adjacency():
    rows,proof=fixture()
    for row in rows:row['source_structure']['status']='unresolved'
    assert select_structure_companions(rows,proof)[0]==select_context_companions(rows,proof)[0]


def test_partial_note_in_core_does_not_hide_missing_original_tail():
    rows,proof=fixture()
    rows[1]['source_structure']=deepcopy(rows[20]['source_structure'])
    rows[1]['original_source']={'source_char_start':50,'source_char_end':58}
    selected,receipt=select_structure_companions(rows,proof)
    assert selected[1]['node_id']=='20' and receipt['promotions']
    rows[1]['original_source']['source_char_end']=70
    assert not select_structure_companions(rows,proof)[1]['promotions']
