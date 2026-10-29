from hashlib import sha256
import json
import sqlite3
import zlib

import pytest
from test_semantic_units import row
from scripts.engineering.plan_retrieval_units import plan
from sec_agent.research_foundation.organization_index_release import canonical_digest


def fixture(tmp_path):
    records=[]
    with sqlite3.connect(tmp_path/'navigation.sqlite') as db:
        db.execute('CREATE TABLE nodes(node_id TEXT,payload BLOB)')
        for number,(node,document,content) in enumerate([
                ('a1','a','Cash balance 20.'),('a2','a','Unit: millions.'),('b1','b','Cash balance 30.')]):
            source=row(content,space=node);source.update(node_id=node,parent_document_id=document)
            raw=json.dumps(source).encode()
            db.execute('INSERT INTO nodes VALUES (?,?)',(node,zlib.compress(raw)))
            records.append(dict(node_id=node,document_id=document,vector_index=number,
                content_sha256=source['content_sha256'],navigation_sha256=sha256(raw).hexdigest()))
    index={'records':records,'navigation_index':{'sha256':sha256((tmp_path/'navigation.sqlite').read_bytes()).hexdigest()}}
    path=tmp_path/'index.json';path.write_text(json.dumps(index))
    return index,path


def test_declared_document_scope_preserves_all_parents_and_freezes_scope(tmp_path):
    index,path=fixture(tmp_path)
    scope=tmp_path/'scope.json';scope.write_text(json.dumps({
        'snapshot_digest':canonical_digest(index),'parent_node_ids':['a1','a2']}))
    result=plan(path,tmp_path/'plan',scope)
    assert result['parents']==2 and result['documents']==1 and result['provider_calls']==0
    assert result['declared_scope']['sha256']==sha256(scope.read_bytes()).hexdigest()
    assert 'structural_surface.py' in result['code_sha256']


@pytest.mark.parametrize('parents,error', [(['a1'],'partial_document'),
    (['a1','missing'],'parent_missing'), (['a1','a1'],'scope_invalid'),([], 'scope_invalid')])
def test_partial_or_invalid_document_scope_is_rejected_before_build(tmp_path,parents,error):
    index,path=fixture(tmp_path)
    scope=tmp_path/'scope.json';scope.write_text(json.dumps({
        'snapshot_digest':canonical_digest(index),'parent_node_ids':parents}))
    with pytest.raises(ValueError,match=error):plan(path,tmp_path/'plan',scope)
    assert not (tmp_path/'plan').exists()
