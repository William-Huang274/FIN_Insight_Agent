"""Audit frozen repair receipts and summarize changes, without quality inference."""
import argparse
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path


def audit(root):
    summary=json.loads((root/'summary.json').read_bytes())
    if summary['processed']!=summary['planned']:raise ValueError('run_incomplete')
    rows=summary['rows'];counts=Counter();findings=[];examples=[];ids=set()
    for row in rows:
        oid=row['id']
        if oid in ids:findings.append(dict(id=oid,error='duplicate_original'))
        ids.add(oid)
        if row['status']=='failed':findings.append(row);continue
        raw=Path(row['artifact_path']).read_bytes()
        if sha256(raw).hexdigest()!=row['artifact_sha256']:raise ValueError('artifact_changed:'+oid)
        d=json.loads(gzip.decompress(raw));counts[row['lane']]+=1
        if d.get('source_sha256',oid)!=oid:raise ValueError('source_identity_changed')
        scopes=d.get('source_scope_repairs',[]);roles=d.get('source_role_repairs',[])
        counts['source_signature_scopes']+=len(scopes)
        counts['signature_parent_changes']+=sum(r['previous_parent_id'] is not None for r in scopes)
        for r in roles:counts['role_'+r['role']]+=1
        if row['lane']=='web':
            counts['verified_web_titles']+=d.get('document_title',{}).get('status')=='verified_original_heading'
            for b in d['blocks']:
                if b['text'].strip():counts['web_'+b['source_location_status']]+=1
        if row['lane']=='markdown':
            for b in d['blocks']:
                if 'embedded_html_structure' not in b:continue
                h=b['embedded_html_structure'];counts['embedded_html_blocks']+=1
                for k in ('headings','tables','images'):counts['embedded_'+k]+=len(h[k])
        if roles or any(r['previous_parent_id'] is not None for r in scopes):
            examples.append(dict(id=oid,title=row['title'],scopes=scopes,roles=roles))
    return dict(planned=summary['planned'],unique_originals=len(ids),counts=dict(counts),findings=findings,
                evidence_pass=not findings and len(ids)==summary['planned'],quality_pass=False,examples=examples)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=audit(a.root)
    a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in r.items() if k!='examples'},ensure_ascii=False))
    raise SystemExit(0 if r['evidence_pass'] else 1)
