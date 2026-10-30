"""Account for frozen bindings lacking an original in the selected capture DB.

Existing recovered nodes are inspected, never relabelled as original HTML/PDF.
Raw digest and path hints are exported for a separate original-resolution pass.
"""
import argparse
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from retrieval.narrative_chunks import sentence_groups
from document_structure_audit import inspect


def audit(manifest_path,context_path,database,output):
    manifest=json.loads(manifest_path.read_bytes());context=json.loads(context_path.read_bytes())
    bindings={r['document_id']:r for r in context['bindings']}
    output.mkdir(parents=True,exist_ok=False);rows=[]
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA cache_size=-2048')
        for source in manifest['sources']:
            if source['original_resolution']=='unique_archived_capture':continue
            binding=bindings[source['document_id']];problems=[]
            raw=db.execute('SELECT snapshot FROM attachment_captures WHERE object_id=?',(binding['capture_object_id'],)).fetchone()[0]
            if sha256(raw.encode()).hexdigest()!=binding['capture_sha256']:raise ValueError('capture_changed')
            bundle=json.loads(raw)['bundle'];metadata=bundle['source'].get('metadata',{})
            if isinstance(metadata,str):metadata=json.loads(metadata)
            recovery=bundle.get('node_recovery') or {};nodes=recovery.get('nodes',[])
            if nodes:
                blocks=[];chunks=[];all_ids={n['node_id'] for n in nodes}
                for n in nodes:
                    content=n.get('content','');path=n.get('section_path',[])
                    expected=n.get('content_sha256')
                    if expected and sha256(content.encode()).hexdigest()!=expected:
                        problems.append({'kind':'recovered_node_content_digest_mismatch','node_id':n['node_id']})
                    if not path:problems.append({'kind':'recovered_node_without_section_path','node_id':n['node_id']})
                    parent=n.get('parent_section_id')
                    if parent and parent not in all_ids:problems.append({'kind':'recovered_parent_not_present','node_id':n['node_id']})
                    if '\\n' in content and '\n' not in content:
                        problems.append({'kind':'literal_escaped_linebreaks_require_origin_review','node_id':n['node_id']})
                    i=len(blocks);blocks.append(n)
                    if n.get('node_kind') in {'section','table','table_row','table_cell'}:continue
                    for start,end,text in sentence_groups(content):
                        chunks.append({'node_index':i,'start':start,'end':end,'section_path':path})
                result={'route':'existing_recovered_nodes_only','nodes':blocks,'pre_chunks':chunks,
                        'issues':problems,'original_structure_verified':False}
            else:
                text=bundle.get('text','')
                try:
                    result=inspect(text.encode(),{'capture':{'content_type':'text/plain'},
                        'domain':source['domain'],'title':source['title'],'form':source.get('form')})
                except Exception as exc:
                    result={'route':'derived_text_parse_failed','issues':[{'kind':type(exc).__name__,'detail':str(exc)[:500]}],
                            'pre_chunks':[],'original_structure_verified':False}
                result['original_structure_verified']=False
                result['issues'].append({'kind':'derived_text_cannot_prove_original_structure'})
            result.update(document_id=source['document_id'],capture_sha256=binding['capture_sha256'])
            key=sha256(source['document_id'].encode()).hexdigest()
            with gzip.open(output/(key+'.json.gz'),'wt',encoding='utf8',compresslevel=3) as out:json.dump(result,out,ensure_ascii=False)
            row={'document_id':source['document_id'],'title':source['title'],'url':source['url'],
                 'source_digest':source['source_digest'],'route':result['route'],
                 'raw_digest_hints':sorted({n.get('raw_body_sha256','') for n in nodes}-{''}),
                 'metadata':metadata,'pre_chunks':len(result['pre_chunks']),
                 'issues':dict(Counter(p['kind'] for p in result['issues'])),
                 'artifact':key+'.json.gz','original_structure_verified':False}
            rows.append(row)
    (output/'bindings.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf8')
    issues=Counter()
    for r in rows:issues.update(r['issues'])
    report={'bindings':len(rows),'routes':dict(Counter(r['route'] for r in rows)),
            'issues':dict(issues),'pre_chunks':sum(r['pre_chunks'] for r in rows),
            'original_structure_verified':False,'provider_calls':0,
            'manifest_sha256':sha256(manifest_path.read_bytes()).hexdigest(),
            'context_sha256':sha256(context_path.read_bytes()).hexdigest()}
    (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['manifest','context','database','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();audit(a.manifest,a.context,a.database,a.output)
