import hashlib
import json

import pytest

from scripts.deployment.native_library import install, validate, volume_operation


def test_native_copy_verified_and_cannot_replace_existing_release(tmp_path):
    source=tmp_path/'source';target=tmp_path/'volume';source.mkdir()
    body=b'original immutable release';expected=hashlib.sha256(body).hexdigest()
    (source/'library.sqlite').write_bytes(body)
    (source/'library.sqlite.manifest.json').write_text(json.dumps({'sha256':expected}))
    assert install(source,target,expected)==expected
    assert install(source,target,expected)==expected
    with pytest.raises(ValueError,match='version_mismatch'):
        install(source,target,'different-version')
    assert (target/'library.sqlite').read_bytes()==body
    (target/'library.sqlite').write_bytes(b'tampered')
    with pytest.raises(ValueError,match='version_mismatch'):
        validate(target,expected)


def test_volume_verify_does_not_create_or_download(monkeypatch):
    calls=[]
    monkeypatch.setattr('scripts.deployment.native_library.subprocess.run',lambda command,**kw:calls.append(command))
    volume_operation('docker','release-r21','sha',image='local-image')
    assert calls[0]==['docker','volume','inspect','release-r21']
    assert ['--pull','never']==calls[1][3:5]
    assert 'type=volume,source=release-r21,target=/library,readonly' in calls[1]
    assert '--network' in calls[1] and 'none' in calls[1]


def test_invalid_volume_rejected_before_command(monkeypatch):
    monkeypatch.setattr('scripts.deployment.native_library.subprocess.run',lambda *a,**k:pytest.fail('must not execute'))
    with pytest.raises(ValueError,match='volume_name'):
        volume_operation('docker','release,volume-opt=bad','sha',image='local')
