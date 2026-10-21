"""Freeze selected historical node sets; never concatenate them into full text."""
import argparse
from collections import defaultdict
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from retrieval.library_node_recovery import CATALOG, RECEIPT, validate_nodes
from retrieval.library_vectors import digest


def prepare(library, node_file, node_file_sha256, source_ids, output):
    library,node_file,output=map(lambda p:Path(p).resolve(),(library,node_file,output))
    if not source_ids or len(source_ids)!=len(set(source_ids)):
        raise ValueError('explicit_unique_source_selection_required')
    if output.is_relative_to(library.parent) or output.is_relative_to(node_file.parent):
        raise ValueError('node_output_must_be_independent')
    output.mkdir(parents=True,exist_ok=False)
    manifest=dict(format=CATALOG,status='incomplete',library_sha256=digest(library),sources={},
                  original_node_file_sha256=node_file_sha256,provider_calls=0,
                  scope='complete imported node sets; not complete original documents')
    def save():
        (output/'catalog.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    save()
    try:
        if digest(node_file)!=node_file_sha256:raise ValueError('original_node_file_digest_mismatch')
        selected=set(source_ids);by_source=defaultdict(list)
        with node_file.open(encoding='utf8') as stream:
            for line in stream:
                node=json.loads(line)
                if node['parent_document_id'] in selected:by_source[node['parent_document_id']].append(node)
        with closing(sqlite3.connect(library.as_uri()+'?mode=ro',uri=True)) as db:
            db.row_factory=sqlite3.Row;db.execute('BEGIN')
            for sid in source_ids:
                source=dict(db.execute('SELECT * FROM sources WHERE id=?',(sid,)).fetchone())
                parents=[dict(p) for p in db.execute('SELECT * FROM passages WHERE source_id=?',(sid,))]
                nodes=by_source[sid]
                validate_nodes(source,parents,nodes)
                receipt=dict(format=RECEIPT,source_id=sid,source_digest=source['digest'],
                             library_sha256=manifest['library_sha256'],nodes=nodes,
                             original_node_file_sha256=node_file_sha256)
                raw=json.dumps(receipt,ensure_ascii=False,indent=2).encode('utf8');checksum=sha256(raw).hexdigest()
                (output/(checksum+'.json')).write_bytes(raw)
                manifest['sources'][sid]=dict(sha256=checksum,nodes=len(nodes),source_digest=source['digest'],url=source['url'])
                save()
        if digest(node_file)!=node_file_sha256 or digest(library)!=manifest['library_sha256']:
            raise ValueError('node_source_changed_during_export')
        aliases=defaultdict(list)
        for sid,r in manifest['sources'].items():aliases[(r['url'],r['source_digest'])].append(sid)
        manifest['same_url_and_original_digest_groups']=[ids for ids in aliases.values() if len(ids)>1]
        manifest['status']='verified'
    except Exception as exc:
        manifest.update(status='failed',error_type=type(exc).__name__,error=str(exc));save();raise
    save();return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library',type=Path,required=True)
    p.add_argument('--node-file',type=Path,required=True)
    p.add_argument('--node-file-sha256',required=True)
    p.add_argument('--source-id',action='append',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=prepare(a.library,a.node_file,a.node_file_sha256,a.source_id,a.output)
    print(json.dumps(dict(status=r['status'],sources=len(r['sources']),catalog_sha256=digest(a.output/'catalog.json'))))


if __name__=='__main__':main()
