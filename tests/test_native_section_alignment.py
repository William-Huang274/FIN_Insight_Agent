from copy import deepcopy
import pytest
from native_section_alignment import complete_section_sequences


def fixture():
    sources={sid:dict(text=text) for sid,text in [('toc','Item 3. Defaults'),('h','Item 3. Defaults'),('n','None.'),('other','None.')]}
    blocks=[dict(kind='heading',text='Item 3. Defaults',source_container_candidates=['toc','h']),
            dict(kind='text',text='None.',source_container_candidates=['n','other']),dict(kind='heading',text='Item 4')]
    membership={'h':{'item3'},'n':{'item3'},'other':{'item4'}}
    spans={'h':(10,11),'n':(12,13),'other':(15,16)}
    sections={'item3':dict(fields=dict(item='3'),native_text='Item 3. Defaults\nNone.')}
    return blocks,sources,membership,spans,sections


def test_complete_source_range_resolves_repeated_text_without_first_match():
    args=fixture();original=deepcopy(args)
    result=complete_section_sequences(*args)
    assert [r['source_id'] for r in result[0]['bindings']]==['h','n']
    assert args==original


def test_partial_text_or_second_original_candidate_is_not_promoted():
    args=fixture();args[-1]['item3']['native_text']+=' Missing final paragraph.'
    assert not complete_section_sequences(*args)
    args=fixture();args[2]['other']={'item3'}
    assert not complete_section_sequences(*args)


def test_overlapping_or_reversed_original_containers_remain_unresolved():
    args=fixture();args[3]['n']=(9,10)
    assert not complete_section_sequences(*args)
    args=fixture();args[2]['h'].add('other-section')
    assert not complete_section_sequences(*args)


def test_duplicate_heading_and_table_content_do_not_create_scope():
    args=fixture();args[0].append(deepcopy(args[0][0]))
    assert not complete_section_sequences(*args)
    assert not complete_section_sequences(*fixture(),native_membership={1:{'conflicting-section'}})
    args=fixture();args[0][1]['kind']='table'
    assert not complete_section_sequences(*args)


@pytest.mark.parametrize(('heading','item'), [('ITEM 9B. Other Information','9B'), ('Item 3.03. Modification of Rights','303')])
def test_item_identity_supports_alpha_and_decimal_existing_wire_forms(heading,item):
    args=fixture()
    args[0][0]['text']=heading
    args[1]['h']['text']=heading
    args[-1]['item3']=dict(fields=dict(item=item),native_text=heading+'\nNone.')
    assert complete_section_sequences(*args)
    args[-1]['item3']['fields']['item']='30'
    assert not complete_section_sequences(*args)


def test_navigation_or_incomplete_source_container_is_not_used():
    args=fixture();args[1]['n']['excluded_navigation']=True
    assert not complete_section_sequences(*args)
    args=fixture();args[1]['n']['text']='None. More original content.'
    assert not complete_section_sequences(*args)
