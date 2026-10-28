import sqlite3
import pytest
from test_semantic_units import row
from retrieval.semantic_unit_catalog import build,iter_units


def test_unit_plan_reuses_only_exact_inputs_and_records_billed_input_scale(tmp_path):
    original=row('A complete statement.')
    mixed=row('A\n[TABLE:1]\nCash | 20\n[/TABLE]\nB')
    mixed['node_id']='second'
    path=tmp_path/'units.sqlite'
    receipt=build(path,[(original,2),(mixed,3)])
    values=list(iter_units(path));new=list(iter_units(path,require_new_vector=True))
    assert receipt['parents']==2 and receipt['partitioned_parents']==1
    assert receipt['reused_vectors']==1 and values[0][2]==2
    assert receipt['new_vectors_required']==len(new)==3
    assert receipt['new_embedding_utf8_bytes']==sum(len((u['embedding_context']+'\n'+u['content']).encode()) for _,u,_ in new)
    assert receipt['provider_calls']==0 and len(receipt['catalog_sha256'])==64
    with pytest.raises(FileExistsError):build(path,[(original,2)])


def test_failed_plan_cannot_be_used_as_a_sealed_catalog(tmp_path):
    source=row('text');path=tmp_path/'units.sqlite'
    with pytest.raises(sqlite3.IntegrityError):build(path,[(source,0),(source,1)])
    with pytest.raises(ValueError,match='not_sealed'):list(iter_units(path))


def test_selected_catalog_keeps_every_unit_and_original_vector_position(tmp_path):
    from retrieval.semantic_unit_catalog import select_parents
    a=row('unchanged');b=row('prose\n[TABLE:1]\nCash | 20\n[/TABLE]\ntail');b['node_id']='second'
    source=tmp_path/'all.sqlite';build(source,[(a,4),(b,9)])
    target=tmp_path/'selected.sqlite'
    receipt=select_parents(source,target,['second'])
    original=[(u,reuse) for _,u,reuse in iter_units(source) if u['parent_node_id']=='second']
    selected=list(iter_units(target))
    assert [n for n,_,_ in selected]==list(range(len(original)))
    assert [(u,reuse) for _,u,reuse in selected]==original
    assert receipt['parents']==1 and receipt['retrievable_units']==len(original)
    with pytest.raises(ValueError,match='parent_missing'):
        select_parents(source,tmp_path/'missing.sqlite',['does-not-exist'])
    with pytest.raises(ValueError,match='not_sealed'):list(iter_units(tmp_path/'missing.sqlite'))
