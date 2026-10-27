from hashlib import sha256
import json
from uuid import uuid4

import pytest

from tests.integration.source_intake_http_resume import load_seal


def test_retained_index_requires_complete_exact_files_and_input_scope(tmp_path):
    org, release = str(uuid4()), str(uuid4())
    root = tmp_path/'indices'
    directory = root/org/'releases'/release
    directory.mkdir(parents=True)
    files = {}
    for name in ('index.json', 'vectors.npy', 'lexical.sqlite', 'navigation.sqlite', 'graph.sqlite'):
        body = ('synthetic '+name).encode()
        (directory/name).write_bytes(body)
        files[name] = sha256(body).hexdigest()
    seal = dict(schema='retained-http-index.v1', index_root=str(root), organization_id=org,
        contract={'release_id': release}, intake_sha256='intake', geometry_sha256='geometry', files=files)
    path = tmp_path/'seal.json'
    path.write_text(json.dumps(seal))
    assert load_seal(path, intake_sha256='intake', geometry_sha256='geometry') == seal
    with pytest.raises(ValueError, match='scope_changed'):
        load_seal(path, intake_sha256='other', geometry_sha256='geometry')
    (directory/'vectors.npy').write_bytes(b'changed')
    with pytest.raises(ValueError, match='file_changed'):
        load_seal(path, intake_sha256='intake', geometry_sha256='geometry')
    del seal['files']['vectors.npy']
    path.write_text(json.dumps(seal))
    with pytest.raises(ValueError, match='files_incomplete'):
        load_seal(path, intake_sha256='intake', geometry_sha256='geometry')
