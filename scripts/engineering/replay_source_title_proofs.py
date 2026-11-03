"""Reprove existing title links with identical semantic locations and scope.

Only diagnostic TOC label spelling may change. All old artifacts remain intact;
the next full-library audit still must pass under the new implementation.
"""
import argparse
from copy import deepcopy
import gzip
import json
from pathlib import Path
import gc

from audit_source_binding_lineage import digest,read_lines
from qualify_embedded_section_titles import original
from source_section_title_links import repair,verify


def semantic(proofs):
    return [{k:v for k,v in p.items() if k!='toc'} for p in proofs]


def run(ledger,receipts,output):
    rows=read_lines(ledger);source_receipts=read_lines(receipts)
    targets={r['artifact']['path'] for r in source_receipts if r['proofs']}
    out=Path(output);out.mkdir(parents=True,exist_ok=False);selected={};results=[];changed=0
    frozen={str(p):digest(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')}
    ledger_hash=digest(Path(ledger).read_bytes());receipts_hash=digest(Path(receipts).read_bytes())
    for row in rows:
        a=row.get('current_parser_artifact') or {};path=a.get('path')
        if path not in targets:continue
        if path not in selected:
            raw_artifact=Path(path).read_bytes()
            if digest(raw_artifact)!=a['sha256']:raise ValueError('prior_artifact_changed')
            old=json.loads(gzip.decompress(raw_artifact));prior=deepcopy(old)
            for n in prior['chapter_tree']:
                if 'prior_source_title_binding' in n:n.update(n.pop('prior_source_title_binding'))
            previous=prior.pop('source_section_title_links')
            raw=original(row['current_source']);new,proofs,_=repair(prior,raw)
            if semantic(previous)!=semantic(proofs):raise ValueError('semantic_title_binding_changed')
            if old['blocks']!=new['blocks'] or old['pre_chunks']!=new['pre_chunks']:raise ValueError('physical_content_changed')
            verify(new,raw)
            selected[path]=a
            if old!=new:
                target=out/(old['source_sha256']+'.document.json.gz')
                target.write_bytes(gzip.compress(json.dumps(new,ensure_ascii=False).encode(),compresslevel=3,mtime=0))
                selected[path]=dict(a,path=str(target),sha256=digest(target.read_bytes()),version=out.name);changed+=1
            results.append(dict(parent=a,artifact=selected[path],proofs=len(proofs),source_sha256=old['source_sha256'],semantic_identity_pass=True))
            del old,prior,new,raw,raw_artifact;gc.collect()
        row['current_parser_artifact']=selected[path];row['processing']['current_parser_artifact']=selected[path]
    if set(selected)!=targets:raise ValueError('replay_scope_incomplete')
    assert len(rows)==len({r['document_id'] for r in rows})==1742
    assert ledger_hash==digest(Path(ledger).read_bytes()) and receipts_hash==digest(Path(receipts).read_bytes())
    assert all(digest(Path(p).read_bytes())==h for p,h in frozen.items())
    (out/'library-bindings.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf8')
    (out/'identity.json').write_text(json.dumps(dict(code=frozen,input_sha256=ledger_hash,receipts_sha256=receipts_hash),indent=2),encoding='utf8')
    summary=dict(bindings=len(rows),reproved_artifacts=len(results),proofs=sum(r['proofs'] for r in results),
                 provenance_changed_artifacts=changed,semantic_identity_pass=True,quality_pass=False,provider_calls=0,rows=results)
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('ledger','receipts','output'):p.add_argument('--'+n,required=True)
    a=p.parse_args();run(a.ledger,a.receipts,a.output)
