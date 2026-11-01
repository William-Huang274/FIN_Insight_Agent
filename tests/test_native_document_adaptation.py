import copy
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'/'engineering'))
from native_document_capture import capture_native
from native_document_adaptation import adapt
from finalize_structure_prechunks import classify


def test_title_audit_distinguishes_identifiers_from_unresolved_internal_keys():
    from audit_native_chapter_compatibility import internal_key_displayed
    def node(title, status='heading_not_bound'):
        return dict(title=title, native_section_key=title, title_binding=dict(status=status))
    assert internal_key_displayed(node('part_i_item_1'))
    assert not internal_key_displayed(node('Item 5'))
    assert not internal_key_displayed(node('Item 3.03'))
    assert not internal_key_displayed(node('SIGNATURES', 'bound_heading'))
    assert internal_key_displayed(node('Item 5_unverified_internal'))


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


def test_no_native_scope_preserves_unknown_level_without_inventing_one():
    native, previous = sec_fixture()
    native['native']['sections'] = {}
    previous['chapter_tree'][0]['level'] = None
    before = copy.deepcopy(previous)
    result = adapt(native, previous)
    assert result['outline'][0]['level'] is None
    assert result['chapter_tree'][0]['level'] is None
    assert previous == before


def test_hidden_parent_does_not_turn_unknown_level_into_guessed_depth():
    from native_document_adaptation import finish
    _, previous = sec_fixture()
    previous['chapter_tree'][0]['navigation_status'] = 'compatibility_only'
    previous['chapter_tree'][1].update(level=None, parent_id='chapter:0')
    result = finish(previous)
    assert result['outline'][0]['level'] is None
    assert result['outline'][0]['parent_block'] is None


def test_sec_consumes_membership_without_rewriting_text_or_hiding_unscoped_headings():
    native, old=sec_fixture(); before=copy.deepcopy(old)
    doc=adapt(native,old)
    assert [b['text'] for b in doc['blocks']] == [b['text'] for b in old['blocks']]
    assert doc['blocks'][0]['chapter_ids'] == ['chapter:0']
    assert doc['blocks'][0]['chapter_binding_status'] == 'prior_scope_unverified'
    assert all(n['title'] != 'Cover' for n in doc['outline'])
    assert doc['unscoped_chapter_tree'][0]['title'] == 'Cover'
    assert doc['blocks'][2]['chapter_ids'] == ['native-section:item1']
    assert next(n for n in doc['chapter_tree'] if n['id']=='native-section:item1')['native_section']['validated'] is False
    assert old == before


def test_sec_path_match_does_not_authorize_changed_or_ambiguous_text():
    native, old=sec_fixture(); old['blocks'][2]['text']='Expanded body spanning another section.'
    doc=adapt(native,old)
    assert doc['blocks'][2]['native_section_binding']['status']=='unresolved_native_membership'
    assert doc['blocks'][2]['chapter_ids']==['native-section:item1']
    assert doc['blocks'][2]['chapter_binding_status']=='prior_scope_unverified'
    native, old=sec_fixture()
    native['native']['sections']['another']=copy.deepcopy(native['native']['sections']['item1'])
    doc=adapt(native,old)
    assert doc['blocks'][2]['native_section_binding']['status']=='ambiguous_native_membership'
    assert doc['native_tree_status']=='existing_tree_retained_no_native_scope'
    assert doc['blocks'][2]['chapter_ids']==['chapter:1']


def test_partial_membership_preserves_table_and_subheading_with_explicit_prior_status():
    native, old = sec_fixture()
    old['blocks'].extend([
        dict(kind='heading',text='Equity',chapter_ids=['chapter:1','chapter:3']),
        dict(kind='table',text='100',rows=[[{'text':'100'}]],chapter_ids=['chapter:1','chapter:3'],embedded_chapter_ids=['chapter:3']),
    ])
    old['chapter_tree'].append(dict(id='chapter:3',block=3,title='Equity',level=2,parent_id='chapter:1',basis='source_heading'))
    before=copy.deepcopy(old)
    doc=adapt(native,old)
    assert doc['blocks'][4]['chapter_ids']==['native-section:item1','chapter:3']
    assert doc['blocks'][4]['embedded_chapter_ids']==['chapter:3']
    assert doc['blocks'][4]['native_section_binding']['status']=='unresolved_native_membership'
    assert doc['blocks'][4]['chapter_binding_status']=='prior_scope_unverified'
    assert next(n for n in doc['chapter_tree'] if n['id']=='chapter:3')['parent_id']=='native-section:item1'
    assert next(c for c in doc['pre_chunks'] if c['block']==4)['chapter_ids']==doc['blocks'][4]['chapter_ids']
    assert old==before


def test_navigation_skips_unverified_ancestor_but_preserves_full_evidence_path():
    native,old=sec_fixture()
    native['native']['nodes'].append(dict(ref='d',rendered_text='Detail',fields={'type':{'name':'HEADING'},'children':[]}))
    native['native']['nodes'][0]['fields']['children'].append({'$node':'d'})
    native['native']['nodes'][-2]['fields']['children'].append({'$node':'d'})
    old['blocks'].extend([
        dict(kind='heading',text='Unmapped heading',chapter_ids=['chapter:1','chapter:3']),
        dict(kind='heading',text='Detail',native_container_id='0/3',chapter_ids=['chapter:1','chapter:3','chapter:4'])])
    old['chapter_tree'].extend([
        dict(id='chapter:3',block=3,title='Unmapped heading',level=2,parent_id='chapter:1',basis='old'),
        dict(id='chapter:4',block=4,title='Detail',level=3,parent_id='chapter:3',basis='old')])
    doc=adapt(native,old)
    assert doc['blocks'][4]['chapter_ids']==['native-section:item1','chapter:3','chapter:4']
    row=next(n for n in doc['outline'] if n['block']==4)
    assert row['parent_block']==1
    assert row['level']==2


def test_internal_section_key_uses_bound_title_and_keeps_original_key():
    native,old=sec_fixture()
    native['native']['sections']['item1']['fields'].update(title='part_i_item_1',name='part_i_item_1',item='1')
    native['native']['nodes'][2]['rendered_text']='Item 1. Business'
    old['blocks'][1]['text']='Item 1. Business';old['chapter_tree'][1]['title']='Item 1. Business'
    doc=adapt(native,old);node=next(n for n in doc['chapter_tree'] if n['id']=='native-section:item1')
    assert node['title']=='Item 1. Business'
    assert node['title_binding']['status']=='bound_heading'
    assert node['native_section']['title']=='part_i_item_1'


def test_decimal_item_identity_and_part_caption_are_compatible_without_duplicates():
    native,old=sec_fixture()
    native['native']['sections']['item1']['fields'].update(title='item_303',name='item_303',item='303',part='II')
    native['native']['nodes'][2]['rendered_text']='Item 3.03 Material Modification to Rights.'
    old['blocks'][1]['text']='Item 3.03 Material Modification to Rights.'
    old['chapter_tree'][1].update(title=old['blocks'][1]['text'],parent_id='chapter:0',level=2)
    old['chapter_tree'][0]['title']='PART II – OTHER INFORMATION'
    old['blocks'][0]['text']='PART II – OTHER INFORMATION'
    old['blocks'][2]['text']='Unmapped expanded text.'
    old['blocks'][2]['chapter_ids']=['chapter:0','chapter:1']
    doc=adapt(native,old)
    assert doc['blocks'][2]['chapter_ids']==['native-part:II','native-section:item1']
    assert next(n for n in doc['chapter_tree'] if n['id']=='native-section:item1')['title']==old['blocks'][1]['text']


def test_unbound_title_does_not_promote_first_body_or_erase_its_old_heading():
    native,old=sec_fixture()
    native['native']['sections']['item1']['fields'].update(title='item1',name='item1',item='1')
    native['native']['nodes'][-1]['fields']['children']=[{'$node':'c'}]
    old['blocks'][2].update(kind='heading',text='Body.',chapter_ids=['chapter:1','chapter:2'])
    old['chapter_tree'].append(dict(id='chapter:2',block=2,title='Body.',level=2,parent_id='chapter:1',basis='old'))
    doc=adapt(native,old);nodes={n['id']:n for n in doc['chapter_tree']}
    assert nodes['native-section:item1']['title']=='Item 1'
    assert nodes['native-section:item1']['title_binding']['status']=='heading_not_bound'
    assert 'chapter:2' in nodes
    assert doc['blocks'][2]['chapter_ids']==['native-section:item1','chapter:2']


def test_bound_body_does_not_inherit_a_different_native_section_from_old_tree():
    native,old=sec_fixture()
    native['native']['nodes'].extend([
        dict(ref='d',rendered_text='Item 2',fields={'type':{'name':'HEADING'},'children':[]}),
        dict(ref='s2',fields={'type':{'name':'SECTION'},'children':[{'$node':'d'}]}),
    ])
    native['native']['nodes'][0]['fields']['children'].append({'$node':'d'})
    native['native']['sections']['item2']={'fields':dict(node={'$node':'s2'},title='Item 2')}
    old['blocks'].append(dict(kind='heading',text='Item 2',native_container_id='0/3',chapter_ids=['chapter:3']))
    old['chapter_tree'].append(dict(id='chapter:3',block=3,title='Item 2',level=1,parent_id=None,basis='old'))
    old['blocks'][2]['chapter_ids']=['chapter:3']
    doc=adapt(native,old)
    assert doc['blocks'][2]['chapter_ids']==['native-section:item1']


@pytest.mark.parametrize('heading_table', [True, False])
@pytest.mark.parametrize('other_boundary', [True, False])
def test_toc_cell_anchor_only_expands_to_verified_whole_heading_table(heading_table, other_boundary):
    from hashlib import sha256
    native, old = sec_fixture()
    raw='<html><body><table><tr><td id="start">Item 6</td><td>Reserved</td></tr></table><a id="end"></a></body></html>'
    digest=sha256(raw.encode()).hexdigest(); sid=digest+':/html/body/table'
    native['source_sha256']=digest
    native['native']['metadata']={'fields':{'original_html':raw}}
    native['native']['nodes'][-1]['fields']['children']=[]
    native['native']['toc_boundaries']={'item1':dict(fields=dict(anchor_id='start',end_element_id='end'),element_paths={})}
    if other_boundary:
        native['native']['toc_boundaries']['other']=copy.deepcopy(native['native']['toc_boundaries']['item1'])
    old['source_containers']=[dict(id=sid,text='Item 6 Reserved',text_sha256=sha256(b'Item 6 Reserved').hexdigest(),parent_id=None,table_id=None)]
    old['blocks']=[dict(kind='table',text='Item 6 | Reserved',source_container_id=sid,
                        source_location_status='unique_complete_container',chapter_ids=[],
                        structural_heading='Item 6 Reserved' if heading_table else None,
                        source_table_role='section_heading_container' if heading_table else 'data_table')]
    old['chapter_tree']=[]
    doc=adapt(native,old,native_paths_verified=False)
    expected=heading_table and not other_boundary
    assert bool(doc['native_boundary_adjustments']) is expected
    assert (doc['blocks'][0]['native_section_binding']['candidates']==['item1']) is expected


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
