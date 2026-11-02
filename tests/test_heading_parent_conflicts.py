from copy import deepcopy
from heading_parent_conflicts import reconcile


def fixture():
    return dict(source_sha256='x',source_containers=[],parser_sections={'item19':dict(part='III')},
                source_heading_units=[dict(id='unit',section='item19',chapter_id='item',part='II',part_source_id='part-source')],
                chapter_tree=[dict(id='part',block=0,title='PART II',level=1,parent_id=None,basis='candidate'),
                              dict(id='item',block=1,title='Item 19',level=2,parent_id='part',basis='source'),
                              dict(id='sub',block=2,title='Exhibits',level=3,parent_id='item',basis='parser')],
                blocks=[dict(kind='heading',text='PART II',chapter_ids=['part'],chapter_blocks=[0]),
                        dict(kind='heading',text='Item 19',chapter_ids=['part','item'],chapter_blocks=[0,1]),
                        dict(kind='text',text='Exhibit list.',chapter_ids=['part','item','sub'],chapter_blocks=[0,1,2])])


def test_contradictory_parent_is_unselected_without_inventing_native_parent():
    d=fixture();old=deepcopy(d);r,c=reconcile(d)
    assert d==old and len(c)==1
    assert r['source_heading_units'][0]['part'] is None
    assert r['chapter_tree'][1]['parent_id'] is None
    assert r['chapter_tree'][2]['level'] is None
    assert r['blocks'][2]['chapter_ids']==['item','sub']
    assert [b['text'] for b in r['blocks']]==[b['text'] for b in d['blocks']]
    assert r['pre_chunks'][0]['chapter_ids']==['item','sub']


def test_agreeing_or_absent_part_is_not_rewritten():
    d=fixture();d['source_heading_units'][0]['part']='III'
    r,c=reconcile(d);assert r is d and not c
    d['source_heading_units'][0]['part']=None
    r,c=reconcile(d);assert r is d and not c


def test_resume_refuses_changed_parent_bytes(tmp_path,monkeypatch):
    import gzip,json
    from types import SimpleNamespace
    import psutil,pytest
    from heading_parent_conflicts import run,digest
    monkeypatch.setattr(psutil,'virtual_memory',lambda:SimpleNamespace(available=2*1024**3))
    root=tmp_path/'parent';folder=root/'x';folder.mkdir(parents=True)
    d=fixture();d['source_heading_units'][0]['part']='III'
    path=folder/'document.json.gz';path.write_bytes(gzip.compress(json.dumps(d).encode()))
    (folder/'prechunks.json.gz').write_bytes(gzip.compress(b'{}'))
    (folder/'receipt.json').write_text(json.dumps(dict(id='x',artifact_sha256=digest(path),counts={})))
    (root/'summary.json').write_text(json.dumps(dict(engineering_pass=True,rows=[dict(id='x')])))
    (root/'identity.json').write_text('{"code":{}}');output=tmp_path/'result'
    assert run(root,output)==0
    assert run(root,output)==0
    path.write_bytes(b'corrupted')
    with pytest.raises(ValueError,match='parent_artifact_changed'):run(root,output)
