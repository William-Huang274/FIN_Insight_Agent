"""Freeze selected historical node sets; never concatenate them into full text."""
import argparse
from collections import defaultdict
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from retrieval.library_node_recovery import CATALOG, RECEIPT, SURVEY_RECEIPT, validate_nodes, survey_nodes
from retrieval.library_vectors import digest


def prepare(library, node_file, node_file_sha256, source_ids, output, extra_node_files=(), survey_file=None, survey_file_sha256=None):
    library,node_file,output=map(lambda p:Path(p).resolve(),(library,node_file,output))
    if not source_ids or len(source_ids)!=len(set(source_ids)):
        raise ValueError('explicit_unique_source_selection_required')
    inputs=[(node_file,node_file_sha256)]+[(Path(p).resolve(),h) for p,h in extra_node_files]
    if bool(survey_file)!=bool(survey_file_sha256):raise ValueError('survey_input_and_digest_required')
    survey_file=Path(survey_file).resolve() if survey_file else None
    all_inputs=inputs+([(survey_file,survey_file_sha256)] if survey_file else [])
    if output.is_relative_to(library.parent) or any(output.is_relative_to(p.parent) for p,_ in all_inputs):
        raise ValueError('node_output_must_be_independent')
    output.mkdir(parents=True,exist_ok=False)
    manifest=dict(format=CATALOG,status='incomplete',library_sha256=digest(library),sources={},
                  original_node_file_sha256=node_file_sha256,provider_calls=0,
                  scope='complete imported node sets; not complete original documents')
    def save():
        (output/'catalog.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    save()
    try:
        selected=set(source_ids);by_source=defaultdict(list);origins={};surveys={}
        for original,checksum in inputs:
            if digest(original)!=checksum:raise ValueError('original_node_file_digest_mismatch')
            with original.open(encoding='utf8') as stream:
                for line in stream:
                    node=json.loads(line);sid=node['parent_document_id']
                    if sid in selected:
                        if sid in origins and origins[sid]!=checksum:raise ValueError('source_node_multiple_snapshots')
                        origins[sid]=checksum;by_source[sid].append(node)
        if survey_file:
            if digest(survey_file)!=survey_file_sha256:raise ValueError('survey_input_file_digest_mismatch')
            for envelope in json.loads(survey_file.read_text(encoding='utf8'))['reads']:
                sid='SURVEY:'+sha256(envelope['source']['url'].encode()).hexdigest()[:16]
                if sid in selected:
                    if sid in surveys or sid in by_source:raise ValueError('duplicate_survey_source')
                    surveys[sid]=envelope
        with closing(sqlite3.connect(library.as_uri()+'?mode=ro',uri=True)) as db:
            db.row_factory=sqlite3.Row;db.execute('BEGIN')
            for sid in source_ids:
                source=dict(db.execute('SELECT * FROM sources WHERE id=?',(sid,)).fetchone())
                parents=[dict(p) for p in db.execute('SELECT * FROM passages WHERE source_id=?',(sid,))]
                nodes=survey_nodes(source,surveys[sid]) if sid in surveys else by_source[sid]
                validate_nodes(source,parents,nodes)
                receipt=dict(format=SURVEY_RECEIPT if sid in surveys else RECEIPT,source_id=sid,source_digest=source['digest'],
                             library_sha256=manifest['library_sha256'],nodes=nodes)
                if sid in surveys:receipt.update(original_read_envelope=surveys[sid],original_read_file_sha256=survey_file_sha256)
                else:receipt['original_node_file_sha256']=origins[sid]
                raw=json.dumps(receipt,ensure_ascii=False,indent=2).encode('utf8');checksum=sha256(raw).hexdigest()
                (output/(checksum+'.json')).write_bytes(raw)
                manifest['sources'][sid]=dict(sha256=checksum,nodes=len(nodes),source_digest=source['digest'],url=source['url'])
                save()
        if any(digest(p)!=h for p,h in all_inputs) or digest(library)!=manifest['library_sha256']:
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
    p.add_argument('--extra-node-file',type=Path,action='append',default=[])
    p.add_argument('--extra-node-sha256',action='append',default=[])
    p.add_argument('--survey-file',type=Path)
    p.add_argument('--survey-sha256')
    a=p.parse_args()
    if len(a.extra_node_file)!=len(a.extra_node_sha256):p.error('extra node files require matching ordered SHA256 values')
    r=prepare(a.library,a.node_file,a.node_file_sha256,a.source_id,a.output,
              list(zip(a.extra_node_file,a.extra_node_sha256)),a.survey_file,a.survey_sha256)
    print(json.dumps(dict(status=r['status'],sources=len(r['sources']),catalog_sha256=digest(a.output/'catalog.json'))))


if __name__=='__main__':main()
