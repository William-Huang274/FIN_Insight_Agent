from copy import deepcopy
from hashlib import sha256
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts/engineering'))
from embedded_section_titles import repair, verify


def fixture(bold=True, link=False, duplicate=False):
    label='<b>Financial Statements and Exhibits.</b>' if bold else 'Financial Statements and Exhibits.'
    if link:label='<a href="#body">'+label+'</a>'
    raw=('<html><body><table><tr><td><b>Item 9.01.</b></td><td>'+label+'</td></tr>'
         '<tr><td colspan="2">(d) Exhibits and retained body.</td></tr></table></body></html>').encode()
    digest=sha256(raw).hexdigest();sid=digest+':/html/body/table'
    b=dict(kind='table',text='Item 9.01. | Financial Statements and Exhibits.\n(d) Exhibits and retained body.',
           source_container_id=sid,source_location_status='unique_complete_container',
           native_section_binding=dict(candidates=['item_901']),chapter_ids=['section'],
           rows=[[dict(text='Item 9.01.'),dict(text='Financial Statements and Exhibits.')],
                 [dict(text='(d) Exhibits and retained body.')]])
    d=dict(source_sha256=digest,source_containers=[dict(id=sid)],blocks=[b],pre_chunks=[dict(block=0,kind='table')],
           outline=[dict(block=0,title='Fallback')],chapter_tree=[dict(id='section',block=0,title='Fallback',
           native_section_key='item_901',native_section=dict(item='901'),title_binding=dict(status='heading_not_bound'))])
    if duplicate:d['blocks'].append(deepcopy(b))
    return d,raw


def test_binds_only_embedded_title_preserving_body_and_ranges():
    old,raw=fixture(); new,proofs,_=repair(old,raw)
    assert len(proofs)==1
    assert new['chapter_tree'][0]['title']=='Item 9.01. Financial Statements and Exhibits.'
    assert new['chapter_tree'][0]['title_binding']['parsed_row']==0
    b=deepcopy(new['blocks'][0]);b.pop('embedded_section_titles')
    assert b==old['blocks'][0]
    assert new['pre_chunks']==old['pre_chunks']
    assert 'structural_heading' not in new['blocks'][0]
    assert repair(new,raw)[0]==new
    verify(new,raw)


def test_saved_proof_is_reproved_against_original():
    import pytest
    old,raw=fixture();new,_,_=repair(old,raw)
    new['embedded_section_title_repairs'][0]['parsed_row']=1
    with pytest.raises(ValueError):verify(new,raw)


def test_navigation_unstyled_and_duplicate_are_not_bound():
    for options in [dict(bold=False),dict(link=True),dict(duplicate=True)]:
        old,raw=fixture(**options)
        assert repair(old,raw)[0]==old


def test_wrong_item_or_ambiguous_membership_is_not_bound():
    old,raw=fixture();old['chapter_tree'][0]['native_section']['item']='202'
    assert not repair(old,raw)[1]
    old,raw=fixture();old['blocks'][0]['native_section_binding']['candidates'].append('other')
    assert not repair(old,raw)[1]


def test_source_drift_rejected():
    import pytest
    old,raw=fixture()
    with pytest.raises(ValueError,match='original_digest_changed'):repair(old,raw+b' ')
