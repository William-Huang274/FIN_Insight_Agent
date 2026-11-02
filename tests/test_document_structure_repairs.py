from copy import deepcopy
from hashlib import sha256
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts/engineering'))
from document_structure_repairs import repair_sec_signatures, repair_markdown_html


def fixture():
    texts=['Item 6. Exhibits','SIGNATURES','Pursuant to the requirements of the Securities Exchange Act of 1934, the registrants have duly caused this report to be signed on their behalf by the undersigned thereunto duly authorized.','Date: July 23, 2025','Signers','EXHIBIT INDEX','Later body.']
    kinds=['heading','heading','text','heading','text','heading','text']
    blocks=[]; sources=[]
    for i,(t,k) in enumerate(zip(texts,kinds)):
        sid=f'source:/p[{i}]';sources.append(dict(id=sid,text=t,text_sha256=sha256(t.encode()).hexdigest(),parent_id=None,table_id=None))
        blocks.append(dict(text=t,kind=k,source_container_id=sid,source_location_status='unique_complete_container',chapter_ids=['item']+(['signature'] if 1<=i<5 else []),chapter_blocks=[0]+([1] if 1<=i<5 else [])))
    tree=[dict(id='item',block=0,title=texts[0],level=1,parent_id=None,basis='old'),dict(id='signature',block=1,title=texts[1],level=2,parent_id='item',basis='old'),dict(id='date',block=3,title=texts[3],level=3,parent_id='signature',basis='old'),dict(id='index',block=5,title=texts[5],level=1,parent_id=None,basis='old')]
    return dict(blocks=blocks,source_containers=sources,chapter_tree=tree)


def test_plural_attestation_repairs_scope_but_stops_before_next_heading():
    d=fixture();before=deepcopy(d);r=repair_sec_signatures(d)
    assert r['chapter_tree'][1]['parent_id'] is None
    assert r['blocks'][2]['chapter_ids']==['signature']
    assert r['blocks'][5]==before['blocks'][5]
    assert [b['text'] for b in r['blocks']]==[b['text'] for b in before['blocks']]
    assert d==before


def test_navigation_or_remote_attestation_does_not_create_boundary():
    d=fixture();d['source_containers'][1]['internal_link_only']=True
    assert not repair_sec_signatures(d)['source_scope_repairs']
    d=fixture();d['blocks'].insert(2,dict(kind='text',text='Other content.',chapter_ids=[],chapter_blocks=[]))
    assert not repair_sec_signatures(d)['source_scope_repairs']


def test_markdown_fragment_retains_raw_and_does_not_mix_html_into_prose():
    from native_document_adaptation import adapt
    from native_document_capture import capture_native
    from finalize_structure_prechunks import classify
    raw=b'# Main\n\n<div><h2>Results</h2><table><tr><th colspan="2">USD</th></tr><tr><td>Cash</td><td>12</td></tr></table><img src="chart.png" alt="Chart"/></div>\n'
    old=adapt(capture_native(raw,'markdown'));new=repair_markdown_html(old)
    b=next(b for b in new['blocks'] if 'embedded_html_structure' in b)
    assert b['embedded_html_structure']['headings'][0]['title']=='Results'
    assert b['embedded_html_structure']['tables'][0]['rows'][0][0]['colspan']=='2'
    assert ''.join(b.get('raw_text',b['text']) for b in new['blocks']).encode()==raw
    grouped={i for g in classify(new)['prose_groups'] for i in g['atomic_record_indices']}
    assert all(i not in grouped for i,r in enumerate(classify(new)['records']) if r['role']=='html_structure_candidate')
