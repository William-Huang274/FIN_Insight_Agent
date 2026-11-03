from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sys

import pytest
from lxml import html

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts/engineering'))
from source_item_title_evidence import item_identity, repair, verify


def fixture(raw, number, specs):
    root = html.fromstring(raw); tree = root.getroottree(); h = sha256(raw).hexdigest()
    blocks = []; sources = []
    for path, member in specs:
        element = tree.xpath(path)[0]; text = ''.join(element.itertext()); sid = h + ':' + path
        block = dict(kind='table' if element.tag == 'table' else 'text', text=text,
                     source_container_id=sid, source_location_status='unique_complete_container',
                     native_section_binding=dict(candidates=['old_key'] if member else []), chapter_ids=['old_key'])
        if element.tag == 'table':
            block['rows'] = [[dict(text=''.join(c.itertext())) for c in r.xpath('./td|./th')]
                             for r in element.xpath('./tr|./tbody/tr')]
        blocks.append(block); sources.append(dict(id=sid, text=text))
    first = next(i for i, (_, member) in enumerate(specs) if member)
    return dict(source_sha256=h, blocks=blocks, source_containers=sources, pre_chunks=[],
                chapter_tree=[dict(id='old_key', block=first, title='Native short label',
                    native_section_key='old_key', native_section=dict(item=number),
                    title_binding=dict(status='heading_not_bound'))],
                outline=[dict(block=first, title='Native short label')])


def test_original_decimal_item_overrides_display_but_preserves_native_identity():
    raw = b'<html><body><a href="#i">ITEM 5.02. Officers</a><p id="i"><b>ITEM 5.02. Officers</b></p><p>Appointed an officer.</p></body></html>'
    d = fixture(raw, '5', [('/html/body/p[1]', False), ('/html/body/p[2]', True)])
    updated, proofs, _ = repair(d, raw)
    assert len(proofs) == 1 and proofs[0]['native_item_disagrees']
    assert updated['chapter_tree'][0]['native_section'] == d['chapter_tree'][0]['native_section']
    assert updated['chapter_tree'][0]['id'] == 'old_key'
    assert updated['blocks'] == d['blocks']
    assert updated['chapter_tree'][0]['title'] == 'ITEM 5.02. Officers'
    verify(updated, raw)


def test_truncated_native_number_needs_exact_original_toc_not_company_exception():
    raw = b'<html><body><p><b>Item 8.01. Events</b></p><p>Body.</p></body></html>'
    d = fixture(raw, '8', [('/html/body/p[1]', False), ('/html/body/p[2]', True)])
    assert not repair(d, raw)[1]


def test_parenthesized_item_clause_is_part_of_original_title():
    raw = b'<html><body><p><b>Item 5.02(b). Officers</b></p><p>Body.</p></body></html>'
    d = fixture(raw, '502', [('/html/body/p[1]', True), ('/html/body/p[2]', True)])
    updated, proofs, _ = repair(d, raw)
    assert len(proofs) == 1 and item_identity(proofs[0]['title']) == '502'
    assert '(b)' in updated['chapter_tree'][0]['title']
    verify(updated, raw)


def test_table_title_covers_one_row_and_never_removes_other_rows():
    raw = b'<html><body><table><tr><td><b>Item 5.02(d)</b></td><td><b>Officers</b></td></tr><tr><td>Cash</td><td>100</td></tr></table></body></html>'
    d = fixture(raw, '502', [('/html/body/table', True)])
    updated, proofs, _ = repair(d, raw)
    assert len(proofs) == 1 and proofs[0]['table_row']['parsed_row'] == 0
    assert updated['blocks'] == d['blocks'] and updated['pre_chunks'] == d['pre_chunks']
    verify(updated, raw)


def test_visible_gap_and_wrong_toc_cannot_authorize_a_title():
    raw = b'<html><body><a href="#i">Item 5.02. Different</a><p id="i"><b>Item 5.02. Officers</b></p><p>Body.</p></body></html>'
    d = fixture(raw, '5', [('/html/body/p[1]', False), ('/html/body/p[2]', True)])
    assert not repair(d, raw)[1]
    raw = b'<html><body><p><b>Item 3. Risk</b></p>Unrecorded intervening text<p>Body.</p></body></html>'
    d = fixture(raw, '3', [('/html/body/p[1]', False), ('/html/body/p[2]', True)])
    assert not repair(d, raw)[1]


def test_source_and_proof_drift_are_rejected():
    raw = b'<html><body><p><b>Item 3. Risk</b></p><p>Body.</p></body></html>'
    d = fixture(raw, '3', [('/html/body/p[1]', False), ('/html/body/p[2]', True)])
    with pytest.raises(ValueError):
        repair(d, raw + b' ')
    updated, _, _ = repair(d, raw)
    bad = deepcopy(updated); bad['source_item_title_repairs'][0]['original_item'] = '4'
    with pytest.raises(ValueError):
        verify(bad, raw)


def test_empty_original_sibling_target_requires_empty_gap_and_unique_anchor():
    raw = b'<html><body><a href="#i">Item 8.01. Events</a><div id="i"></div><p><b>Item 8.01. Events</b></p><p>Body.</p></body></html>'
    d = fixture(raw, '8', [('/html/body/p[1]', False), ('/html/body/p[2]', True)])
    updated, proofs, _ = repair(d, raw)
    assert len(proofs) == 1 and proofs[0]['original_toc']['anchor'] == 'i'
    verify(updated, raw)
    for changed in (raw.replace(b'</div><p>', b'</div>Intervening<p>'),
                    raw.replace(b'<div id="i">', b'<div id="i"></div><div id="i">')):
        d = fixture(changed, '8', [('/html/body/p[1]', False), ('/html/body/p[2]', True)])
        assert not repair(d, changed)[1]


def test_source_proven_standalone_navigation_can_separate_target_from_title():
    raw = b'<html><body><a id="toc" href="#i">Item 8.01. Events</a><div id="i"></div><p><a href="#toc">Back to contents</a></p><p><b>Item 8.01. Events</b></p><p>Body.</p></body></html>'
    d = fixture(raw, '8', [('/html/body/p[1]', False), ('/html/body/p[2]', False), ('/html/body/p[3]', True)])
    d['source_containers'][0]['internal_link_only'] = True
    updated, proofs, _ = repair(d, raw)
    assert len(proofs) == 1 and proofs[0]['original_toc']['navigation_gap_source_ids']
    verify(updated, raw)
    changed = raw.replace(b'<p><a href="#toc">', b'Unmarked content<p><a href="#toc">')
    d = fixture(changed, '8', [('/html/body/p[1]', False), ('/html/body/p[2]', False), ('/html/body/p[3]', True)])
    d['source_containers'][0]['internal_link_only'] = True
    assert not repair(d, changed)[1]


def test_toc_row_cannot_become_a_body_item_title():
    raw = b'<html><body><table><tr><td><b><a href="#body">Item 5.02.</a></b></td><td><b>Officers</b></td><td>3</td></tr></table><div id="body">Actual body.</div></body></html>'
    d = fixture(raw, '502', [('/html/body/table', True)])
    assert not repair(d, raw)[1]


def test_real_prechunk_consumer_marks_prose_titles_but_keeps_full_table():
    from finalize_structure_prechunks import classify
    raw = b'<html><body><p><b>Item 3. Risk</b></p><p>Full body.</p></body></html>'
    d = fixture(raw, '3', [('/html/body/p[1]', False), ('/html/body/p[2]', True)])
    d['pre_chunks']=[dict(block=i,kind='prose',start=0,end=len(b['text']),heading_path=[]) for i,b in enumerate(d['blocks'])]
    updated, _, _=repair(d,raw); result=classify(updated)
    assert [r['role'] for r in result['records']]==['retained_structure','prose_candidate']
    assert result['prose_groups'][0]['atomic_record_indices']==[1]
    raw=b'<html><body><table><tr><td><b>Item 3.</b></td><td><b>Risk</b></td></tr><tr><td>Cash</td><td>100</td></tr></table></body></html>'
    d=fixture(raw,'3',[('/html/body/table',True)]);d['pre_chunks']=[dict(block=0,kind='table',heading_path=[])]
    updated, _, _=repair(d,raw);record=classify(updated)['records'][0]
    assert record['role']=='table_candidate' and record['original_item_title_rows'][0]['table_row']['parsed_row']==0
    assert updated['blocks'][0]['rows'][-1][1]['text']=='100'
