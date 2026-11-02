from copy import deepcopy
import pytest

from test_source_heading_units import fixture
from source_heading_units import repair
from qualify_source_heading_units import compare
from audit_library_structure_selection import text_observations,issue_record


def test_issue_title_is_separate_from_document_title():
    r=issue_record('doc','sec','Annual report',dict(kind='unresolved_native_title',title='Item 6'))
    assert r['document_title']=='Annual report' and r['title']=='Item 6'


def test_selected_conflicting_part_cannot_pass_whole_library_audit():
    d,c=fixture();r=repair(d,c);r['parser_sections']={'item6':dict(part='III')}
    r['source_heading_units'][0]['part']='II'
    with pytest.raises(ValueError,match='parent_conflicts'):text_observations(r)


def test_audit_keeps_source_repair_distinct_from_native_binding():
    d,c=fixture();d['parser_sections']={'item6':dict(item='6')}
    result=repair(d,c);counts,issues=text_observations(result)
    assert counts['native_sections_without_unique_blocks']==1
    assert counts['formerly_unbound_with_source_heading']==1
    assert counts['sections_without_native_blocks_or_source_heading']==0
    assert counts['source_heading_units']==1
    assert compare(d,result)['split_heading_units']==1


def test_audit_rejects_hidden_complete_title_and_fragment_leak():
    d,c=fixture();r=repair(d,c)
    r['chapter_tree'][0]['navigation_status']='compatibility_only'
    with pytest.raises(ValueError,match='not_consumed'):text_observations(r)
    r=repair(d,c);r['blocks'][2]['structural_only']=False
    with pytest.raises(ValueError,match='leaks'):text_observations(r)


def test_conservation_gate_rejects_changed_content_and_old_proofs():
    d,c=fixture();r=repair(d,c)
    r['blocks'][0]['text']='Lost original'
    with pytest.raises(ValueError,match='preserved_field'):compare(d,r)
    r=repair(d,c);r['source_scope_repairs']=[dict(fake=True)]
    with pytest.raises(ValueError,match='prior_repair'):compare(d,r)


def test_signature_boundary_remains_outside_item_scope():
    d,c=fixture();d['blocks'][1].update(effective_scope=dict(kind='source_signature_scope'),chapter_ids=['signed'],chapter_blocks=[1])
    d['chapter_tree']=[dict(id='signed',block=1,title='Signature',level=1,parent_id=None,basis='source_signature_and_adjacent_attestation')]
    # Deliberately contradictory input must be caught by compatibility gate,
    # never reported as a successful repair of both boundaries.
    r=repair(d,c)
    with pytest.raises(ValueError,match='signature'):compare(d,r)
