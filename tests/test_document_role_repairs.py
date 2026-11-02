import sys
from pathlib import Path
from hashlib import sha256
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts/engineering'))
from document_role_repairs import repair_context_roles


def doc(label):
    sid='source:/p';s=dict(id=sid,text=label,text_sha256=sha256(label.encode()).hexdigest(),parent_id=None,table_id=None)
    return dict(blocks=[dict(kind='heading',text=label,source_container_id=sid,source_location_status='unique_complete_container',chapter_ids=['unit'],chapter_blocks=[0]),dict(kind='text',text='Data follows.',chapter_ids=['unit'],chapter_blocks=[0])],source_containers=[s],chapter_tree=[dict(id='unit',title=label,block=0,parent_id=None,level=1,basis='parser')])


def test_unit_label_is_preserved_as_context_and_not_parent_of_following_content():
    original=doc('(in millions of U.S. dollars)');d=repair_context_roles(original)
    assert d['blocks'][0]['text']==original['blocks'][0]['text']
    assert d['blocks'][0]['candidate_role']=='attached_context_candidate'
    assert not d['blocks'][1]['chapter_ids']
    assert not d['outline']


def test_financial_heading_containing_units_is_not_demoted():
    assert not repair_context_roles(doc('Revenue in millions'))['source_role_repairs']


def test_cover_month_requires_original_form_container():
    d=doc('For the month of August 2026')
    assert not repair_context_roles(d)['source_role_repairs']
    d['source_containers'][0]['parent_id']='source:/cover'
    d['source_containers'].extend([
        dict(id='source:/cover',text='',text_sha256=sha256(b'').hexdigest(),parent_id=None),
        dict(id='source:/form',text='Form 6-K',text_sha256=sha256(b'Form 6-K').hexdigest(),parent_id='source:/cover')])
    repaired=repair_context_roles(d)
    assert repaired['blocks'][0]['structural_role']=='filing_cover_period'
    d['source_containers'][-1]['parent_id']='source:/other'
    assert not repair_context_roles(d)['source_role_repairs']


def test_unproved_or_navigation_unit_is_not_demoted():
    d=doc('(in millions)')
    d['source_containers'][0]['text']='Different original text'
    assert not repair_context_roles(d)['source_role_repairs']
    d=doc('(in millions)')
    d['source_containers'][0]['internal_link_only']=True
    assert not repair_context_roles(d)['source_role_repairs']
