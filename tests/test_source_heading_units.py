from copy import deepcopy
from hashlib import sha256

import pytest
from source_heading_units import matching_sequences, propose, repair


def fixture(split=True):
    html='<html><body><p>Before.</p><p id="h">Item 6. [Reserved]</p><p id="end">After.</p></body></html>'
    texts=['Before.','Item 6. [Reserved]','After.']
    sources=[dict(id=f'x:/html/body/p[{i+1}]',text=t,text_sha256=sha256(t.encode()).hexdigest(),
                  role='paragraph',referenced_anchor=i==1) for i,t in enumerate(texts)]
    raw=['Before.','Item 6. [R','eserved]','After.'] if split else texts
    blocks=[dict(kind='text',text=t,chapter_ids=[],chapter_blocks=[]) for t in raw]
    for b,s in [(blocks[0],sources[0]),(blocks[-1],sources[-1])]:
        b.update(source_container_id=s['id'],source_location_status='unique_complete_container')
    blocks[1]['native_parent_id']='a'
    if split:blocks[2]['native_parent_id']='b'
    document=dict(source_sha256='x',blocks=blocks,source_containers=sources,chapter_tree=[],pre_chunks=[])
    native=dict(metadata=dict(fields=dict(original_html=html)),sections={'item6':dict(fields=dict(item='6'))},
                toc_boundaries={'item6':dict(fields=dict(anchor_id='h',end_element_id='end'))})
    return document,dict(source_sha256='x',native=native)


@pytest.mark.parametrize('split',[True,False])
def test_complete_source_container_consumed_without_rewriting_physical_blocks(split):
    document,capture=fixture(split);old=deepcopy(document)
    result=repair(document,capture)
    assert document==old
    assert [b['text'] for b in result['blocks']]==[b['text'] for b in old['blocks']]
    assert len(result['source_heading_units'])==1
    assert result['outline'][0]['title']=='Item 6. [Reserved]'
    assert result['chapter_tree'][0]['title_binding']['status']=='source_heading_unit'
    if split:
        assert result['blocks'][2]['source_location_status']=='verified_heading_unit_component'
        from finalize_structure_prechunks import classify
        chunks=classify(result)
        assert next(r for r in chunks['records'] if r['block']==2)['role']=='retained_structure'


def test_partial_match_and_missing_scope_do_not_promote():
    d,c=fixture();d['blocks'][2]['text']='eserved] extra'
    assert repair(d,c)['source_heading_units']==[]
    d,c=fixture();c['native']['toc_boundaries']={}
    assert repair(d,c)['source_heading_units']==[]


def test_two_matching_parser_occurrences_remain_unresolved():
    d,c=fixture();d['blocks'][3:3]=deepcopy(d['blocks'][1:3])
    assert repair(d,c)['source_heading_units']==[]


def test_conflicting_body_location_does_not_get_replaced():
    d,c=fixture();d['blocks'][1].update(source_container_id=d['source_containers'][0]['id'],source_location_status='unique_complete_container')
    assert repair(d,c)['source_heading_units']==[]


def test_table_and_navigation_candidates_remain_excluded():
    for field in ['table_id','excluded_navigation','internal_link_only']:
        d,c=fixture();d['source_containers'][1][field]=d['source_containers'][0]['id'] if field=='table_id' else True
        assert repair(d,c)['source_heading_units']==[]


def test_same_range_remains_explicit_not_silently_assigned():
    d,c=fixture();c['native']['sections']['alias']=dict(fields=dict(item='7'))
    c['native']['toc_boundaries']['alias']=deepcopy(c['native']['toc_boundaries']['item6'])
    result=repair(d,c)
    assert result['shared_native_range_groups'][0]['canonical_section'] is None
    assert result['blocks'][0]['chapter_ids']==[]


def test_proved_toc_only_alias_does_not_block_unique_body_scope():
    d,c=fixture(False)
    c['native']['metadata']['fields']['original_html']=c['native']['metadata']['fields']['original_html'].replace('<p id="end">','<p>Body.</p><p id="end">')
    d['source_containers'][-1]['id']='x:/html/body/p[4]'
    d['blocks'][-1]['source_container_id']='x:/html/body/p[4]'
    body_source=dict(id='x:/html/body/p[3]',text='Body.',text_sha256=sha256(b'Body.').hexdigest(),role='paragraph')
    d['source_containers'].insert(2,body_source)
    d['blocks'].insert(2,dict(kind='text',text='Body.',chapter_ids=[],chapter_blocks=[],source_container_id=body_source['id'],source_location_status='unique_complete_container'))
    c['native']['toc_boundaries']['item6r']=deepcopy(c['native']['toc_boundaries']['item6'])
    result=repair(d,c)
    assert result['native_toc_identity_aliases'][0]['alias']=='item6r'
    assert len(result['native_toc_raw_shared_ranges'])==1
    assert result['shared_native_range_groups']==[]
    assert result['blocks'][2]['chapter_ids']==[result['source_heading_units'][0]['chapter_id']]
    assert [b['text'] for b in result['blocks']]==[b['text'] for b in d['blocks']]


def test_wrong_source_identity_is_rejected():
    d,c=fixture();c['source_sha256']='other'
    with pytest.raises(ValueError,match='identity'):repair(d,c)


def test_reused_original_heading_does_not_choose_one_section_alias():
    d,c=fixture();c['native']['sections']['alias']=deepcopy(c['native']['sections']['item6'])
    c['native']['toc_boundaries']['alias']=deepcopy(c['native']['toc_boundaries']['item6'])
    result=repair(d,c)
    assert result['source_heading_units']==[]
    assert {f['kind'] for f in result['source_heading_findings']}=={'same_heading_multiple_section_identities'}


def test_open_ended_item_cannot_absorb_following_attachment_or_unlocated_subheading():
    d,c=fixture(False)
    c['native']['toc_boundaries']['item6']['fields']['end_element_id']=None
    d['chapter_tree']=[dict(id='native-section:attachment',block=2,title='Attachment',level=1,parent_id=None,basis='native'),
                       dict(id='chapter:contents',block=2,title='Contents',level=2,parent_id='native-section:attachment',basis='parser')]
    d['blocks'][2].update(chapter_ids=['native-section:attachment','chapter:contents'],chapter_blocks=[2,2],
                          native_section_binding=dict(status='unique_native_membership',candidates=['attachment']))
    old=deepcopy(d);r=repair(d,c)
    assert r['blocks'][2]['chapter_ids']==old['blocks'][2]['chapter_ids']
    assert r['chapter_tree'][:2]==old['chapter_tree']
    assert r['source_heading_scope_deferrals'][0]['conflicting_native_sections']==['attachment']


def test_word_join_does_not_globally_remove_whitespace():
    assert matching_sequences([dict(kind='text',text='Item 6. [R'),dict(kind='text',text='eserved]')],[0],'Item 6. [Reserved]')==[[0,1]]
    assert not matching_sequences([dict(kind='text',text='Item 6. Res er ved')],[0],'Item 6. Reserved')
