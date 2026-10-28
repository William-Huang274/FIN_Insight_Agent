"""Recover complete production structure from frozen source captures, read-only.

Writes a new local diagnostic context database. No live grant is inferred from
these originals. Production authorization must be tested separately over HTTP.
"""
from contextlib import closing
from collections import defaultdict
from hashlib import sha256
import argparse
import json
from pathlib import Path
import sqlite3
import zlib


def prepare(index_path,captures_path,scope_path,output):
    from retrieval.library_source_bundle import expand_source_bundle
    from retrieval.source_structure import organization_structure
    from sec_agent.research_foundation.organization_source_filter import source_metadata
    from sec_agent.research_foundation.organization_source_projection import source_nodes
    from sec_agent.research_foundation.organization_candidate_index import encoded
    from sec_agent.research_foundation.prepared_source_metadata import prepare as pack
    from sec_agent.research_foundation.organization_index_release import canonical_digest
    from sec_agent.research_foundation.source_verification_cache import implementation_digest
    code_digest=implementation_digest()
    index_path=Path(index_path).resolve();index=json.loads(index_path.read_bytes())
    scope=json.loads(Path(scope_path).read_bytes());selected=set(scope['parent_node_ids'])
    if canonical_digest(index)!=scope['snapshot_digest']:raise ValueError('context_scope_snapshot_mismatch')
    records={r['node_id']:r for r in index['records'] if r['node_id'] in selected}
    if len(records)!=len(selected):raise ValueError('context_scope_node_missing')
    grouped=defaultdict(list)
    for r in records.values():grouped[r['document_id']].append(r)
    for r in index['records']:
        if r['document_id'] in grouped and r['node_id'] not in selected:raise ValueError('context_requires_whole_documents')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    needed=defaultdict(list);finished=set();bindings=[]
    with closing(sqlite3.connect((index_path.parent/'navigation.sqlite').as_uri()+'?mode=ro',uri=True)) as nav:
        for doc,rs in grouped.items():
            raw=zlib.decompress(nav.execute('SELECT payload FROM nodes WHERE node_id=?',(rs[0]['node_id'],)).fetchone()[0])
            if sha256(raw).hexdigest()!=rs[0]['navigation_sha256']:raise ValueError('context_navigation_changed')
            row=json.loads(raw);origin=row['original_source']
            needed[(origin['source_id'],origin['source_digest'],origin['library_sha256'])].append((doc,row))
    with closing(sqlite3.connect(Path(captures_path).resolve().as_uri()+'?mode=ro',uri=True)) as captures,closing(sqlite3.connect(output/'contexts.sqlite')) as db,db:
        db.executescript('PRAGMA journal_mode=DELETE; PRAGMA cache_size=-2048; CREATE TABLE documents(id TEXT PRIMARY KEY,payload BLOB NOT NULL); CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);')
        for object_id,raw in captures.execute('SELECT object_id,snapshot FROM attachment_captures'):
            snapshot=json.loads(raw);compact=snapshot.get('bundle')
            if not compact:continue
            key=(compact['source']['id'],compact['source']['digest'],compact['library_sha256'])
            targets=[(doc,row) for doc,row in needed.get(key,[]) if doc not in finished]
            if not targets:continue
            bundle=expand_source_bundle(compact)
            for doc,first in targets:
                structures=organization_structure(bundle,doc);nodes=[];locations=[]
                for row in source_nodes(bundle,doc,{'title':first['title'],'ref':{'digest':first['raw_body_sha256']}},'offline://not-a-product-link'):
                    if row['node_kind']!='text':continue
                    record=records.get(row['node_id'])
                    if record is None or sha256(encoded(row)).hexdigest()!=record['navigation_sha256']:
                        raise ValueError('context_current_projection_differs_from_frozen_original')
                    nodes.append(row['node_id']);origin=row['original_source']
                    if 'source_char_start' in origin:space,a,b=doc,origin['source_char_start'],origin['source_char_end']
                    else:space,a,b=origin['original_node_id'],origin['char_start'],origin['char_end']
                    locations.append([space,a,b,row['node_id']])
                if set(nodes)!={r['node_id'] for r in grouped[doc]}:raise ValueError('context_source_population_mismatch')
                value=pack({'metadata':source_metadata(bundle),'nodes':nodes,'locations':locations,'structures':structures})
                packed=zlib.compress(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode(),1)
                db.execute('INSERT INTO documents VALUES (?,?)',(doc,packed));finished.add(doc)
                bindings.append({'document_id':doc,'capture_object_id':object_id,'capture_sha256':sha256(raw.encode()).hexdigest(),
                    'source_id':key[0],'source_digest':key[1],'library_sha256':key[2],'context_sha256':sha256(packed).hexdigest()})
                print(json.dumps({'documents':len(finished),'total':len(grouped)}),flush=True)
        if finished!=set(grouped):raise ValueError('context_original_captures_missing')
        db.execute('INSERT INTO metadata VALUES (?,?)',('sealed','frozen-production-structure.v1'))
    if implementation_digest()!=code_digest:raise ValueError('context_implementation_changed_during_preparation')
    result={'status':'complete','documents':len(finished),'nodes':len(records),'bindings':bindings,
        'structure_implementation_sha256':code_digest,
        'snapshot_digest':scope['snapshot_digest'],'provider_calls':0,'live_authorization_tested':False}
    (output/'context.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return {k:v for k,v in result.items() if k!='bindings'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('index','captures','scope','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.index,a.captures,a.scope,a.output)))
