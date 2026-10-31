import copy
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'/'engineering'))
from native_document_capture import capture_native
from native_document_adaptation import adapt
from finalize_structure_prechunks import classify


def test_markdown_tokens_drive_chapters_tables_and_lossless_source_partition():
    pytest.importorskip('mdit_py_plugins')
    raw = b'---\nlicense: apache\n---\n\nTitle\n=====\n\n## Detail\n\nComplete sentence. Next sentence.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n'
    native = capture_native(raw, 'markdown'); before = copy.deepcopy(native)
    doc = adapt(native)
    assert [c['title'] for c in doc['chapter_tree']] == ['Title', 'Detail']
    assert doc['chapter_tree'][1]['parent_id'] == doc['chapter_tree'][0]['id']
    table = next(b for b in doc['blocks'] if b['kind'] == 'table')
    assert table['rows'][0][1]['text'] == '2'
    assert ''.join(b.get('raw_text', b['text']) for b in doc['blocks']).encode() == raw
    records = classify(doc)['records']
    assert all(r['role'] == 'retained_structure' for r in records if r['block'] == 0)
    assert native == before


def test_markdown_nested_list_heading_and_code_are_not_document_chapters():
    pytest.importorskip('mdit_py_plugins')
    raw = b'# Main\n\n- item\n  ## Inside list\n\n```md\n# Example\n```\n'
    doc = adapt(capture_native(raw, 'markdown'))
    assert [n['title'] for n in doc['chapter_tree']] == ['Main']
    assert ''.join(b.get('raw_text', b['text']) for b in doc['blocks']).encode() == raw
    assert any(r['role']=='code_candidate' for r in classify(doc)['records'])


def test_markdown_html_is_retained_as_pending_content_not_discardable_furniture():
    pytest.importorskip('mdit_py_plugins')
    raw=b'# Results\n\n<table><tr><td>Cash</td><td>100</td></tr></table>\n'
    doc=adapt(capture_native(raw,'markdown'))
    assert ''.join(b.get('raw_text', b['text']) for b in doc['blocks']).encode()==raw
    assert any(r['role']=='html_structure_pending' for r in classify(doc)['records'])


def sec_fixture():
    def node(ref, kind, children=(), text=''):
        return dict(ref=ref, rendered_text=text, fields=dict(type={'name':kind},children=[{'$node':c} for c in children],content=text))
    nodes=[node('r','DOCUMENT',['a','b','c']),node('a','HEADING',text='Cover'),
           node('b','HEADING',text='Item 1'),node('c','PARAGRAPH',text='Body.'),node('s','SECTION',['b','c'])]
    capture=dict(schema='fin_native_document_v1',route='edgartools',source_sha256='source',
                 native=dict(root={'$node':'r'},nodes=nodes,sections={'item1':{'fields':dict(node={'$node':'s'},title='Item 1',validated=False,confidence=.7,part=None)}}))
    blocks=[dict(kind='heading',text='Cover',native_container_id='0/0',chapter_ids=['chapter:0']),
            dict(kind='heading',text='Item 1',native_container_id='0/1',chapter_ids=['chapter:1']),
            dict(kind='text',text='Body.',native_container_id='0/2',chapter_ids=['chapter:1'])]
    tree=[dict(id=f'chapter:{i}',block=i,title=b['text'],level=1,parent_id=None,basis='old') for i,b in enumerate(blocks[:2])]
    return capture,dict(route='edgartools',blocks=blocks,chapter_tree=tree,source_containers=[])


def test_sec_consumes_membership_without_rewriting_text_or_hiding_unscoped_headings():
    native, old=sec_fixture(); before=copy.deepcopy(old)
    doc=adapt(native,old)
    assert [b['text'] for b in doc['blocks']] == [b['text'] for b in old['blocks']]
    assert doc['blocks'][0]['chapter_ids'] == []
    assert doc['unscoped_chapter_tree'][0]['title'] == 'Cover'
    assert doc['blocks'][2]['chapter_ids'] == ['native-section:item1']
    assert doc['chapter_tree'][0]['native_section']['validated'] is False
    assert old == before


def test_sec_path_match_does_not_authorize_changed_or_ambiguous_text():
    native, old=sec_fixture(); old['blocks'][2]['text']='Expanded body spanning another section.'
    doc=adapt(native,old)
    assert doc['blocks'][2]['native_section_binding']['status']=='unresolved_native_membership'
    assert doc['blocks'][2]['chapter_ids']==[]
    native, old=sec_fixture()
    native['native']['sections']['another']=copy.deepcopy(native['native']['sections']['item1'])
    doc=adapt(native,old)
    assert doc['blocks'][2]['native_section_binding']['status']=='ambiguous_native_membership'
    assert doc['native_tree_status']=='existing_tree_retained_no_native_scope'
    assert doc['blocks'][2]['chapter_ids']==['chapter:1']


def test_toc_boundaries_use_whole_original_containers_and_reject_duplicate_anchors():
    from hashlib import sha256
    native, old = sec_fixture()
    html='<html><body><h1>Cover</h1><a id="start"></a><p>Body.</p><a id="end"></a><p>Next.</p></body></html>'
    digest=sha256(html.encode()).hexdigest(); sid=digest+':/html/body/p[1]'
    native['source_sha256']=digest
    native['native']['metadata']={'fields':{'original_html':html}}
    native['native']['nodes'][-1]['fields']['children']=[]
    native['native']['toc_boundaries']={'item1':dict(fields=dict(anchor_id='start',end_element_id='end'),element_paths={})}
    old['source_containers']=[dict(id=sid,text='Body.',text_sha256=sha256(b'Body.').hexdigest(),parent_id=None,table_id=None)]
    old['blocks'][2].update(source_container_id=sid,source_location_status='unique_complete_container')
    doc=adapt(native,old)
    binding=doc['blocks'][2]['native_section_binding']
    assert binding['basis']=='native_toc_boundary_complete_original_container'
    assert binding['candidates']==['item1']
    native['native']['metadata']['fields']['original_html']=html.replace('<h1>', '<a id="start"></a><h1>')
    doc=adapt(native,old)
    assert doc['native_tree_status']=='existing_tree_retained_no_native_scope'
