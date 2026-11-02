from audit_shared_section_ranges import classify


def test_same_item_across_parts_is_identity_conflict_not_new_boundary():
    r=classify(dict(sections=['a','b'],canonical_section=None),{'a':dict(item='5',part='I'),'b':dict(item='5',part='II')},[dict(item='5')])
    assert r['classification']=='same_item_multiple_native_identities'
    assert r['canonical_section'] is None


def test_missing_and_repeated_headings_stay_unresolved():
    group=dict(sections=['a','b']);sections={'a':dict(item='1'),'b':dict(item='2')}
    assert classify(group,sections,[dict(item='1')])['missing_item_sections']==['b']
    assert classify(group,sections,[dict(item='1'),dict(item='1'),dict(item='2')])['classification']=='repeated_item_containers_need_disambiguation'


def test_distinct_candidates_are_not_automatic_scope_approval():
    r=classify(dict(sections=['a','b']),{'a':dict(item='1'),'b':dict(item='2')},[dict(item='1'),dict(item='2')])
    assert r['classification']=='distinct_item_containers_possible_subranges'
    assert r['canonical_section'] is None and r['disposition'].startswith('requires_')


def test_toc_only_identity_is_recorded_without_inventing_native_section():
    r=classify(dict(sections=['a','ghost']),{'a':dict(item='1')},[dict(item='1')])
    assert r['classification']=='toc_identity_absent_from_native_sections'
    assert r['missing_native_sections']==['ghost']
