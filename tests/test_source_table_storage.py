from copy import deepcopy
import base64
import pytest
from retrieval.source_table_storage import pack, unpack, MAX_BYTES


def value():
    return {'format':'source-table-periods.v1', 'raw_sha256':'a'*64,
            'source_digest':'b'*64, 'tables':[{'text':'原文与单位', 'cells':[{'value':'1.20'}]*100}]}


def test_exact_roundtrip_and_significant_repeated_geometry_compression():
    original=value()
    packed=pack(original)
    assert unpack(packed)==original and original==value()
    assert len(packed['payload']) < packed['bytes']/2


@pytest.mark.parametrize('change', ['digest','size','limit','bool','base64','trailing','truncated','keys'])
def test_malformed_or_expanding_payload_cannot_be_read(change):
    packed=deepcopy(pack(value()))
    if change=='digest':packed['sha256']='0'*64
    elif change=='size':packed['bytes']-=1
    elif change=='limit':packed['bytes']=MAX_BYTES+1
    elif change=='bool':packed['bytes']=True
    elif change=='base64':packed['payload']='!'
    elif change=='trailing':packed['payload']=base64.b64encode(base64.b64decode(packed['payload'])+b'extra').decode()
    elif change=='truncated':packed['payload']=base64.b64encode(base64.b64decode(packed['payload'])[:-2]).decode()
    else:packed['unknown']='unsupported'
    with pytest.raises(ValueError,match='source_table_storage'):unpack(packed)
