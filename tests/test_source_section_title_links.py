from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sys
import pytest
from lxml import html

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts/engineering'))
from source_section_title_links import repair,verify


def document(raw,specs,key='summary',item=None):
    digest=sha256(raw).hexdigest();dom=html.fromstring(raw);tree=dom.getroottree()
    sources=[];blocks=[]
    for path,member in specs:
        e=tree.xpath(path)[0];text=''.join(e.itertext());sid=digest+':'+path
        sources.append(dict(id=sid,text=text))
        blocks.append(dict(kind='text',text=text,source_container_id=sid,source_location_status='unique_complete_container',
            native_section_binding=dict(candidates=[key] if member else []),chapter_ids=['old'],chapter_blocks=[0]))
    return dict(source_sha256=digest,source_containers=sources,blocks=blocks,pre_chunks=[],
        chapter_tree=[dict(id='section',block=next(i for i,s in enumerate(specs) if s[1]),title='Section',
                          native_section_key=key,native_section=dict(item=item),title_binding=dict(status='heading_not_bound'))],
        outline=[dict(block=next(i for i,s in enumerate(specs) if s[1]),title='Section')])


def test_toc_target_restores_multiline_title_without_using_internal_key():
    raw=b'<html><body><a href="#p">PROPOSAL 1: ELECTION OF DIRECTORS</a><div><p id="p">PROPOSAL 1:</p><p>ELECTION OF DIRECTORS</p><p>Ordinary body.</p></div></body></html>'
    d=document(raw,[('/html/body/div/p[1]',True),('/html/body/div/p[2]',True),('/html/body/div/p[3]',True)])
    new,proofs,_=repair(d,raw)
    assert len(proofs)==1 and proofs[0]['blocks']==[0,1]
    assert new['chapter_tree'][0]['title']=='PROPOSAL 1: ELECTION OF DIRECTORS'
    assert new['blocks']==d['blocks'] and new['pre_chunks']==d['pre_chunks']
    verify(new,raw);assert repair(new,raw)[0]==new


def test_signature_body_proves_ambiguous_source_occurrence():
    raw=b'<html><body><a href="#s">SIGNATURES</a><p id="s">SIGNATURES</p><p>Pursuant to the requirements of the Securities Exchange Act of 1934, the registrant has duly caused this report to be signed on its behalf by the undersigned, duly authorized.</p></body></html>'
    d=document(raw,[('/html/body/p[1]',False),('/html/body/p[2]',True)],key='signatures')
    b=d['blocks'][0];sid=b.pop('source_container_id');b['source_container_candidates']=[d['source_sha256']+':/html/body/a',sid];b['source_location_status']='ambiguous'
    d['source_containers'].append(dict(id=d['source_sha256']+':/html/body/a',text='SIGNATURES',internal_link_only=True))
    new,proofs,_=repair(d,raw)
    assert len(proofs)==1 and proofs[0]['source_ids']==[sid]
    assert new['blocks']==d['blocks'];verify(new,raw)


def test_item_before_native_body_requires_original_adjacency():
    raw=b'<html><body><p><b>Item 3. Market Risk</b></p><p>Body</p></body></html>'
    d=document(raw,[('/html/body/p[1]',False),('/html/body/p[2]',True)],key='item_3',item='3')
    assert len(repair(d,raw)[1])==1
    raw2=raw.replace(b'</p><p>Body',b'</p><p>Intervening content</p><p>Body')
    d2=document(raw2,[('/html/body/p[1]',False),('/html/body/p[3]',True)],key='item_3',item='3')
    assert not repair(d2,raw2)[1]


def test_ordinary_leading_prose_and_duplicate_anchor_are_not_headings():
    raw=b'<html><body><p><b>A plausible but unsupported sentence.</b></p></body></html>'
    d=document(raw,[('/html/body/p',True)])
    assert not repair(d,raw)[1]
    raw=b'<html><body><a href="#s">Summary</a><p id="s">Summary</p><p id="s">Other</p></body></html>'
    d=document(raw,[('/html/body/p[1]',True),('/html/body/p[2]',True)])
    assert not repair(d,raw)[1]


def test_original_drift_and_modified_proof_are_rejected():
    raw=b'<html><body><a href="#s">Summary</a><p id="s">Summary</p></body></html>'
    d=document(raw,[('/html/body/p',True)])
    with pytest.raises(ValueError):repair(d,raw+b' ')
    new,_,_=repair(d,raw);bad=deepcopy(new);bad['source_section_title_links'][0]['title']='Wrong'
    with pytest.raises(ValueError):verify(bad,raw)


def test_comments_inside_heading_preserve_visible_tail_and_adjacency():
    raw=b'<html><body><a href="#s">Summary</a><p id="s"><!--Anchor-->Summary</p><p>Body</p></body></html>'
    d=document(raw,[('/html/body/p[1]',True),('/html/body/p[2]',True)])
    updated,proofs,_=repair(d,raw)
    assert len(proofs)==1;verify(updated,raw)
    raw=b'<html><body><p><b>Item 3. Market Risk</b></p><!--anchor-->Intervening content<p>Body</p></body></html>'
    d=document(raw,[('/html/body/p[1]',False),('/html/body/p[2]',True)],key='item_3',item='3')
    assert not repair(d,raw)[1]


def test_ambiguous_native_membership_never_proves_section_start():
    raw=b'<html><body><a href="#s">Summary</a><p id="s">Summary</p></body></html>'
    d=document(raw,[('/html/body/p',True)])
    d['blocks'][0]['native_section_binding']['candidates'].append('other')
    assert not repair(d,raw)[1]


def test_prechunk_consumer_keeps_title_as_structure_and_retains_body_and_tables():
    from finalize_structure_prechunks import classify
    raw=b'<html><body><a href="#s">Summary</a><p id="s">Summary</p><p>Operating body.</p></body></html>'
    d=document(raw,[('/html/body/p[1]',True),('/html/body/p[2]',True)])
    for i,b in enumerate(d['blocks']):
        d['pre_chunks'].append(dict(kind='prose',block=i,start=0,end=len(b['text']),heading_path=[]))
    d['blocks'].append(dict(kind='table',text='Cash | 100'))
    d['pre_chunks'].append(dict(kind='table',block=2,heading_path=[]))
    updated,_,_=repair(d,raw);chunks=classify(updated)
    assert [r['role'] for r in chunks['records']]==['retained_structure','prose_candidate','table_candidate']
    assert chunks['records'][0]['source_title_chapter_ids']==['section']
    assert chunks['prose_groups'][0]['atomic_record_indices']==[1]
