from copy import deepcopy
from hashlib import sha256
from source_part_hierarchy import repair, proposals


def fixture():
    def source(sid,text,role='paragraph',**kwargs):
        return dict(id=sid,text=text,role=role,text_sha256=sha256(text.encode()).hexdigest(),**kwargs)
    rows=[source('cover','Cover paragraph'),source('toc','PART III',internal_link_only=True),
          source('part','PART III'),source('item','Item 19. Exhibits'),source('body','List of exhibits.')]
    blocks=[dict(kind='text',text='Cover paragraph',source_container_id='cover',source_location_status='unique_complete_container',chapter_ids=[]),
            dict(kind='heading',text='PART III',source_location_status='ambiguous',chapter_ids=['part']),
            dict(kind='heading',text='Item 19. Exhibits',source_container_id='item',source_location_status='unique_complete_container',chapter_ids=['item'],structural_only=True),
            dict(kind='text',text='List of exhibits.',source_container_id='body',source_location_status='unique_complete_container',chapter_ids=['item'])]
    return dict(source_sha256='x',source_containers=rows,blocks=blocks,
        parser_sections={'item19':dict(part='III')},
        source_heading_units=[dict(id='unit',section='item19',source_id='item',chapter_id='item',blocks=[2],part=None,title='Item 19. Exhibits',previous_blocks=[dict(kind='heading')])],
        shared_native_range_groups=[],
        chapter_tree=[dict(id='part',title='PART III',block=1,level=None,parent_id=None,basis='parser'),
                      dict(id='item',title='Item 19. Exhibits',block=2,level=None,parent_id=None,basis='source')],
        heading_parent_conflicts=[dict(unit='unit',source_part_proposal='II',native_part_proposal='III')])


def test_plain_part_original_and_bracketing_restore_parent_without_text_mutation():
    d=fixture();old=deepcopy(d);r,p=repair(d)
    assert d==old and p[0]['selected_part']=='III'
    assert r['chapter_tree'][1]['parent_id']=='part'
    assert r['blocks'][3]['chapter_ids']==['part','item']
    assert [b['text'] for b in r['blocks']]==[b['text'] for b in d['blocks']]
    assert r['source_containers']==d['source_containers']
    assert not r['heading_parent_conflicts'] and r['heading_parent_conflict_history']


def test_nearer_plain_conflicting_part_is_not_skipped_for_styled_parent():
    d=fixture();d['source_containers'].insert(3,dict(id='near',text='PART IV',role='paragraph'))
    p=proposals(d)[0]
    assert p['selected_part'] is None and p['status']=='nearest_original_part_disagrees'


def test_reference_sentence_and_table_label_cannot_be_parent():
    d=fixture();d['source_containers'][2]['text']='Part III of this filing contains exhibits.'
    assert proposals(d)[0]['status']=='no_complete_original_part'
    d=fixture();d['source_containers'][2]['table_id']='table'
    assert proposals(d)[0]['status']=='no_complete_original_part'


def test_same_text_wrong_original_order_does_not_bind():
    d=fixture();d['blocks'][0]['source_container_id']='body'
    d['blocks'][0]['text']='List of exhibits.'
    assert proposals(d)[0]['selected_part'] is None


def test_repeated_part_page_header_does_not_replace_existing_valid_parent():
    d=fixture();d['source_containers'].insert(3,dict(id='repeat',text='PART III',role='paragraph'))
    assert proposals(d)[0]['status']=='repeated_part_containers_require_role_review'


def test_repeated_parser_occurrence_requires_disambiguation():
    d=fixture();d['blocks'].insert(2,dict(d['blocks'][1]))
    d['source_heading_units'][0]['blocks']=[3]
    assert proposals(d)[0]['status']=='part_parser_position_not_unique'


def test_whole_library_audit_recomputes_proof_and_checks_consumption():
    import pytest
    from audit_library_structure_selection import text_observations
    d,_=repair(fixture());counts,_=text_observations(d)
    assert counts['source_part_parents_repaired']==1
    d['chapter_tree'][1]['parent_id']=None
    with pytest.raises(ValueError,match='proof_not_consumed'):text_observations(d)
    d,_=repair(fixture());d['source_part_proofs'][0]['block']=0
    with pytest.raises(ValueError,match='not_reproducible'):text_observations(d)


def test_qualification_resume_rejects_changed_input(tmp_path,monkeypatch):
    import gzip,json,pytest,psutil,shutil
    from types import SimpleNamespace
    from qualify_source_part_hierarchy import run,digest
    monkeypatch.setattr(psutil,'virtual_memory',lambda:SimpleNamespace(available=2*1024**3))
    monkeypatch.setattr(shutil,'disk_usage',lambda _:SimpleNamespace(free=4*1024**3))
    root=tmp_path/'prior';folder=root/'x';folder.mkdir(parents=True)
    path=folder/'document.json.gz';path.write_bytes(gzip.compress(json.dumps(fixture()).encode()))
    pre=folder/'prechunks.json.gz';pre.write_bytes(gzip.compress(b'{}'))
    (folder/'receipt.json').write_text(json.dumps(dict(artifact_path=str(path),artifact_sha256=digest(path),prechunks_path=str(pre),prechunks_sha256=digest(pre))))
    (root/'summary.json').write_text(json.dumps(dict(engineering_pass=True,rows=[dict(id='x')])))
    (root/'identity.json').write_text('{}')
    output=tmp_path/'result'
    assert run(root,output)==0
    assert run(root,output)==0
    path.write_bytes(b'changed')
    with pytest.raises(ValueError,match='input_changed'):run(root,output)
