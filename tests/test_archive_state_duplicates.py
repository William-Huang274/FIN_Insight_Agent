import hashlib
import json
import zipfile
import pytest
from scripts.engineering.archive_state_duplicates import build, verify, restore, bounded


def test_archive_restore_exact_old_paths_and_changed_file_guard(tmp_path):
    root=tmp_path/'case'; root.mkdir()
    body=b'{"failed":true,"unknown_usage":null,"source":"PASSAGE::abc"}'*100
    a,b=root/'original.json',root/'offline'/'state.json'; b.parent.mkdir()
    a.write_bytes(body); b.write_bytes(body)
    digest=hashlib.sha256(body).hexdigest()
    plan=tmp_path/'groups.json'
    plan.write_text(json.dumps({'groups':[{'retained_original':str(a),'sha256':digest,'bytes':len(body),
         'members':[{'path':str(a)},{'path':str(b)}]}]}))
    archive=tmp_path/'archive.zip'
    build(root,plan,archive)
    assert verify(archive,check_originals=True)['retire_candidates']==1
    assert a.read_bytes()==b.read_bytes()==body
    dest=tmp_path/'restored'
    assert restore(archive,'offline/state.json',target_root=dest)==str(dest/'offline'/'state.json')
    assert (dest/'offline'/'state.json').read_bytes()==body
    restore(archive,'offline/state.json',target_root=dest)  # idempotent
    (dest/'offline'/'state.json').write_bytes(b'new version')
    with pytest.raises(ValueError,match='refuses_changed'):
        restore(archive,'offline/state.json',target_root=dest)
    with pytest.raises(ValueError): bounded(dest,'../escape')
    with pytest.raises(ValueError): bounded(dest,'C:/escape')
    b.write_bytes(b'changed after archive')
    with pytest.raises(ValueError,match='original_changed'):
        verify(archive,check_originals=True)
    b.unlink()
    with pytest.raises(FileNotFoundError):
        verify(archive,check_originals=True)
    result=verify(archive,check_originals=True,allow_missing_originals=True)
    assert result['missing_originals']==['offline/state.json']
