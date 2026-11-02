import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts/engineering'))
from consume_verified_structure_markers import repair


def fixture():
    return {'blocks':[{'kind':'text','text':'PART II'}], 'source_containers':[{'id':'s','text':'PART II'}],
      'chapter_tree':[{'id':'p','block':0,'source_container_id':'s','basis':'original_part_container_and_item_order'}],
      'source_part_proofs':[{'selected_part':'II','status':'verified_original_part_and_item_order','block':0,'source_id':'s'}]}


def test_proven_label_retained_but_excluded_from_prose():
    old=fixture();new,changes=repair(old)
    assert changes and new['blocks'][0]['structural_only']
    assert new['blocks'][0]['text']==old['blocks'][0]['text']
    assert new['chapter_tree']==old['chapter_tree'] and 'structural_only' not in old['blocks'][0]


def test_no_promotion_on_label_alone_or_in_signature_scope():
    old=fixture();old['source_part_proofs']=[]
    assert not repair(old)[1]
    old=fixture();old['blocks'][0]['effective_scope']={'kind':'source_signature_scope'}
    assert not repair(old)[1]


def test_mismatch_keeps_uncertainty():
    old=fixture();old['source_containers'][0]['text']='PART I'
    assert not repair(old)[1]


def test_idempotent_consumption():
    first,_=repair(fixture());second,changes=repair(first)
    assert not changes and second['blocks']==first['blocks']


def test_multiple_items_share_one_part_marker_repair():
    old=fixture();old['source_part_proofs']*=3
    new,changes=repair(old)
    assert len(changes)==1 and new['blocks'][0]['structural_only']
