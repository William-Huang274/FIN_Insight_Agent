from hashlib import sha256
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts/engineering'))
from source_location_alignment import repair,verify
from source_visibility import hidden_display,visibility_map


def fixture(raw,texts,block):
    h=sha256(raw).hexdigest()
    sources=[dict(id=h+':/html/body/p'+(f'[{i+1}]' if len(texts)>1 else ''),text=t,text_sha256=sha256(t.encode()).hexdigest(),role='paragraph') for i,t in enumerate(texts)]
    return dict(source_sha256=h,source_containers=sources,blocks=[dict(kind='text',text=block,source_location_status='unresolved',chapter_ids=['old'])],pre_chunks=[],outline=[])


def test_complete_token_sequence_preserves_numbers_and_words():
    raw=b'<html><body><p>Revenue: $12.2 billion.</p></body></html>'
    d=fixture(raw,['Revenue: $12.2 billion.'],'Revenue: $ 12.2 billion .')
    d['pre_chunks']=[dict(block=0,kind='prose',start=0,end=len(d['blocks'][0]['text']),heading_path=[],chapter_ids=['old'])]
    updated,changes=repair(d,raw)
    assert len(changes)==1 and updated['blocks'][0]['text']==d['blocks'][0]['text']
    assert updated['blocks'][0]['chapter_ids']==['old'];verify(updated,raw)
    assert updated['pre_chunks'][0]['source_container_id']==updated['blocks'][0]['source_container_id']
    from finalize_structure_prechunks import classify
    c=classify(updated)['records'][0]
    assert c['original_location']['offset_namespace']=='parsed_block_offsets_not_original_dom_char_offsets'
    for text in ('Revenue: $12.3 billion.','Revenue: $12.2 million.','Revenue: $-12.2 billion.'):
        d['blocks'][0]['text']=text;assert not repair(d,raw)[1]


def test_word_join_is_not_whitespace_equivalence():
    raw=b'<html><body><p>cashflow</p></body></html>'
    assert not repair(fixture(raw,['cashflow'],'cash flow'),raw)[1]


def test_hidden_duplicate_is_retained_as_metadata_and_visible_target_selected():
    raw=b'<html><body><p>Revenue: 100</p><p hidden>Revenue: 100</p></body></html>'
    d=fixture(raw,['Revenue: 100','Revenue: 100'],'Revenue: 100');d['blocks'][0]['source_location_status']='ambiguous'
    updated,changes=repair(d,raw)
    assert len(changes)==1 and updated['blocks'][0]['source_container_id'].endswith('p[1]')
    assert updated['source_containers'][1]['text']=='Revenue: 100'
    assert updated['source_containers'][1]['source_visibility']['status']=='non_display_metadata'
    verify(updated,raw)


def test_two_visible_occurrences_remain_ambiguous():
    raw=b'<html><body><p>Revenue: 100</p><p>Revenue: 100</p></body></html>'
    d=fixture(raw,['Revenue: 100','Revenue: 100'],'Revenue: 100')
    updated,changes=repair(d,raw)
    assert not changes and updated['blocks'][0]['source_location_status']=='ambiguous'
    assert not updated['blocks'][0]['source_container_id']
    assert len(updated['source_equivalent_occurrence_proofs'][0]['source_ids'])==2
    verify(updated,raw)


def test_inline_style_cascade_and_quoted_content_are_not_guessed():
    assert hidden_display('display:none')
    assert not hidden_display('display:none;display:block')
    assert hidden_display('display:none!important;display:block')
    assert not hidden_display("content:';display:none;';display:block")
    raw=b'<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body><ix:hidden><p>Metadata</p></ix:hidden></body></html>'
    assert visibility_map(raw)['/html/body/ix:hidden/p']['basis']=='inline_xbrl_hidden'


def test_source_drift_is_rejected():
    raw=b'<html><body><p>A</p></body></html>';d=fixture(raw,['A'],'A')
    with pytest.raises(ValueError):repair(d,raw+b' ')


def test_source_catalog_keeps_hidden_values_but_excludes_body_matching():
    from source_structure_contract import source_containers
    raw=b'<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body><p>Cash</p><ix:hidden><p>Cash</p></ix:hidden><ix:continuation><p>Visible continuation</p></ix:continuation></body></html>'
    rows=source_containers(raw)
    hidden=next(r for r in rows if r['xpath'].endswith('ix:hidden/p'))
    continuation=next(r for r in rows if r['xpath'].endswith('ix:continuation/p'))
    assert hidden['text']=='Cash' and hidden['excluded_navigation']
    assert not continuation['excluded_navigation']


def test_memory_budget_scales_with_input_size(tmp_path):
    import gzip
    from qualify_source_locations import memory_requirement
    path=tmp_path/'document.json.gz';path.write_bytes(gzip.compress(b'A'*100))
    job=dict(artifact=dict(path=str(path)),source=dict(bytes=100))
    small=memory_requirement(job)
    assert small>=320*2**20
    job['source']['bytes']=50*2**20
    assert memory_requirement(job)>small
    job['source'].clear()
    assert memory_requirement(job)>=800*2**20


def test_hidden_text_does_not_change_visible_heading_font_baseline():
    from source_structure_contract import source_containers
    raw=('<html><body><p style="font-size:10pt">'+('Visible body. '*20)+'</p>'
         '<p hidden style="font-size:40pt">'+('Metadata body. '*20)+'</p>'
         '<p style="font-size:12pt;font-weight:bold">Real title</p><p>Short.</p></body></html>').encode()
    heading=next(r for r in source_containers(raw) if r['text']=='Real title')
    assert heading['heading_eligible'] and heading['role_basis']=='whole_container_bold_larger_font'
