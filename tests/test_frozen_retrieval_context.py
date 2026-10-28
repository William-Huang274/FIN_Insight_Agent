import json
import sqlite3
import zlib
from hashlib import sha256
from contextlib import closing
import pytest

from scripts.engineering.frozen_retrieval_context import FrozenRetrievalContext


def corpus(tmp_path):
    from sec_agent.research_foundation.source_verification_cache import implementation_digest
    from sec_agent.research_foundation.organization_index_release import canonical_digest
    nav=tmp_path/'navigation.sqlite';nav.write_bytes(b'frozen-navigation')
    records=[{'node_id':n,'document_id':d} for n,d in [('n1','d1'),('n2','d2')]]
    index={'records':records,'navigation_index':{'sha256':sha256(nav.read_bytes()).hexdigest()}}
    bindings=[]
    with closing(sqlite3.connect(tmp_path/'contexts.sqlite')) as db,db:
        db.executescript('CREATE TABLE documents(id TEXT PRIMARY KEY,payload BLOB); CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);')
        db.execute('INSERT INTO metadata VALUES (?,?)',('sealed','frozen-production-structure.v1'))
        for r in records:
            value={'metadata':{'issuer_id':r['document_id'],'form':'10-K',
                   'verified_company_names':['Cedar Inc.'],
                   'fact_entity_identifiers':[{'identifier':'123','scheme':'http://www.sec.gov/CIK'}]},'nodes':[r['node_id']],
                   'source_intervals':{r['node_id']:[0,10]},'prepared_navigation':{'neighbors':{r['node_id']:[]}}}
            raw=zlib.compress(json.dumps(value).encode())
            db.execute('INSERT INTO documents VALUES (?,?)',(r['document_id'],raw))
            bindings.append({'document_id':r['document_id'],'context_sha256':sha256(raw).hexdigest()})
    (tmp_path/'context.json').write_text(json.dumps({'bindings':bindings,'snapshot_digest':canonical_digest(index),
        'structure_implementation_sha256':implementation_digest()}))
    return index


def test_bounded_structures_preserve_full_verified_catalog_and_default_population(tmp_path):
    index=corpus(tmp_path)
    with closing(FrozenRetrievalContext(tmp_path/'index.json',tmp_path,index=index,retained_documents={'d1'})) as bounded:
        assert set(bounded.rows)=={'n1'} and set(bounded.neighbors)=={'n1'}
        assert set(bounded.source_metadata)=={'d1','d2'}
        assert bounded.rows['n1']['fact_owner']=={'company_names':['Cedar Inc.'],
            'fact_entity_identifiers':[{'identifier':'123','scheme':'http://www.sec.gov/CIK'}]}
        bounded.check()
    with closing(FrozenRetrievalContext(tmp_path/'index.json',tmp_path,index=index)) as full:
        assert set(full.rows)=={'n1','n2'}


def test_catalog_outside_retained_structures_is_still_digest_checked(tmp_path):
    index=corpus(tmp_path)
    with closing(sqlite3.connect(tmp_path/'contexts.sqlite')) as db,db:
        db.execute('UPDATE documents SET payload=? WHERE id=?',(zlib.compress(b'{}'),'d2'))
    with pytest.raises(ValueError,match='document_changed'):
        FrozenRetrievalContext(tmp_path/'index.json',tmp_path,index=index,retained_documents={'d1'})


def test_unknown_retained_document_cannot_silently_shrink_scope(tmp_path):
    index=corpus(tmp_path)
    with pytest.raises(ValueError,match='retained_document_missing'):
        FrozenRetrievalContext(tmp_path/'index.json',tmp_path,index=index,retained_documents={'absent'})
