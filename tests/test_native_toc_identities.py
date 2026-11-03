from copy import deepcopy
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts/engineering'))
from native_toc_identities import prove,effective_ranges


def fixture():
    canonical='part_i_item_2';alias='part_i_item_2m'
    boundary=dict(fields=dict(name=canonical,anchor_id='item2',end_element_id='item3'),element_paths={})
    native=dict(sections={canonical:dict(fields=dict(item='2',part='I'))},toc_boundaries={
        canonical:boundary,alias:dict(fields=dict(boundary['fields'],name=alias),element_paths={})})
    sources=[dict(id='source-title',text='Item 2. Management Discussion',role='heading')]
    ranges={canonical:(2,10),alias:(2,10)};spans={'source-title':(3,4)}
    return native,sources,ranges,spans,canonical,alias


def test_same_endpoint_identity_needs_actual_original_item():
    native,sources,ranges,spans,key,alias=fixture()
    proofs=prove(native,sources,ranges,spans)
    assert len(proofs)==1 and proofs[0]['canonical']==key and proofs[0]['alias']==alias
    assert effective_ranges(ranges,proofs)=={key:(2,10)}
    assert len(ranges)==2 and len(native['toc_boundaries'])==2


def test_real_native_sections_and_actual_alphabetic_items_are_not_aliases():
    native,sources,ranges,spans,key,alias=fixture()
    native['sections'][alias]=dict(fields=dict(item='2M',part='I'))
    assert not prove(native,sources,ranges,spans)
    native['sections'].pop(alias);sources[0]['text']='Item 2M. Real Heading'
    assert not prove(native,sources,ranges,spans)
    sources.append(dict(id='real',text='Item 2. Actual',role='heading'));spans['real']=(2,3)
    assert not prove(native,sources,ranges,spans)


def test_different_anchors_or_navigation_only_cannot_prove_alias():
    native,sources,ranges,spans,key,alias=fixture()
    native['toc_boundaries'][alias]['fields']['anchor_id']='different'
    assert not prove(native,sources,ranges,spans)
    native['toc_boundaries'][alias]['fields']['anchor_id']='item2';sources[0]['internal_link_only']=True
    assert not prove(native,sources,ranges,spans)


def test_extra_title_letter_is_not_a_company_or_title_word_rule():
    native,sources,ranges,spans,key,alias=fixture()
    sources[0]['text']='Item 2. [Reserved]'
    assert prove(native,sources,ranges,spans)[0]['alias']==alias
    native['toc_boundaries'][alias]['element_paths']={'start_element':'/other'}
    assert not prove(native,sources,ranges,spans)


def test_alphabetic_item_in_table_is_also_preserved():
    native,sources,ranges,spans,key,alias=fixture()
    sources.append(dict(id='table-title',text='Item 2M. Real Heading',role='paragraph',table_id='table'))
    spans['table-title']=(5,6)
    assert not prove(native,sources,ranges,spans)
