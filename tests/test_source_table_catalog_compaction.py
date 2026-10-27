import json
import pytest
from scripts.engineering.compact_source_table_catalog import compact_catalog
from retrieval.source_table_storage import unpack
from retrieval.source_table_periods import digest


def fixture(tmp_path):
    root=tmp_path/'original';root.mkdir()
    value={'format':'source-table-periods.v1','tables':[{'text':'原文','cells':['repeat']*100}]}
    payload=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()
    (root/'source.json').write_bytes(payload)
    catalog={'format':'source-table-period-catalog.v1','library_sha256':'library','sources':{
        'source':{'source_digest':'fixed-original','file':'source.json','sha256':digest(payload)}}}
    path=root/'catalog.json';path.write_text(json.dumps(catalog),encoding='utf8')
    return path,value,payload


def test_compaction_preserves_original_bytes_and_identity(tmp_path):
    source,value,raw=fixture(tmp_path);out=tmp_path/'compact'
    before=source.read_bytes();audit=compact_catalog(source,out)
    catalog=json.loads((out/'catalog.json').read_bytes());entry=catalog['sources']['source']
    assert catalog['format']=='source-table-period-catalog.v2'
    assert entry['source_digest']=='fixed-original' and entry['original_file_sha256']==digest(raw)
    assert unpack(json.loads((out/entry['file']).read_bytes()))==value
    assert (source.parent/'source.json').read_bytes()==raw and source.read_bytes()==before
    assert audit['status']=='completed' and audit['provider_calls']==0
    with pytest.raises(FileExistsError):compact_catalog(source,out)


def test_changed_source_does_not_publish_new_catalog(tmp_path):
    source,_,_=fixture(tmp_path);out=tmp_path/'compact'
    (source.parent/'source.json').write_text('{}')
    with pytest.raises(ValueError,match='original_changed'):compact_catalog(source,out)
    assert not (out/'catalog.json').exists()
