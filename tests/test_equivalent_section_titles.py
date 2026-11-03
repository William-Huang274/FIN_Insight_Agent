from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts/engineering'))
from equivalent_section_titles import repair,verify
from native_document_adaptation import section_display_title


def test_case_variants_share_label_but_different_titles_do_not():
    blocks=[dict(kind='heading',text=t,native_section_binding=dict(basis='native_node_membership'))
            for t in ('ITEM 1A. RISK FACTORS','Item 1A. Risk Factors')]
    assert section_display_title('item_1a',dict(item='1A'),[0,1],blocks)[2]['status']=='bound_heading'
    blocks[1]['text']='Item 1A. Different Title'
    assert section_display_title('item_1a',dict(item='1A'),[0,1],blocks)[2]['status']=='ambiguous_heading'


def test_proof_preserves_original_case_and_ownership():
    raw=b'<html><body><h1>PART I</h1></body></html>';sid=sha256(raw).hexdigest()+':/html/body/h1'
    d=dict(source_sha256=sha256(raw).hexdigest(),source_containers=[dict(id=sid)],
        blocks=[dict(kind='heading',text='PART I',source_container_id=sid,source_location_status='unique_complete_container',
                     native_section_binding=dict(candidates=['part_i'],basis='native_node_membership'))],
        chapter_tree=[dict(id='p',block=0,title='Part I',native_section_key='part_i',native_section=dict(title='Part I'),
                           title_binding=dict(status='heading_not_bound'))],outline=[dict(block=0,title='Part I')])
    updated,proofs=repair(d,raw)
    assert len(proofs)==1 and updated['chapter_tree'][0]['title']=='PART I'
    assert updated['blocks']==d['blocks']
    verify(updated,raw)
    assert repair(updated,raw)[0]==updated
    wrong=deepcopy(d);wrong['blocks'][0]['text']='Part I'
    assert not repair(wrong,raw)[1]
