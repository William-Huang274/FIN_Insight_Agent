"""Reprove TOC aliases on a full current ledger without rebuilding bodies."""
import argparse
from collections import Counter
import gc
import gzip
import json
from pathlib import Path

from audit_source_binding_lineage import digest,read_lines
from native_document_capture import read_capture
from native_toc_identities import repair,verify
from validate_source_structure_audit import validate


def run(ledger,captures,output):
    rows=read_lines(ledger);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    frozen={str(p):digest(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')}
    ledger_hash=digest(Path(ledger).read_bytes());selected={};counts=Counter()
    with (out/'receipts.jsonl').open('w',encoding='utf8') as stream:
        for row in rows:
            a=row.get('current_parser_artifact') or {}
            if a.get('lane')!='sec':continue
            path=a['path']
            if path not in selected:
                payload=Path(path).read_bytes()
                if digest(payload)!=a['sha256']:raise ValueError('parent_changed')
                d=json.loads(gzip.decompress(payload));selected[path]=a
                groups=len(d.get('shared_native_range_groups',[]));proofs=[]
                if groups:
                    folder=Path(captures)/d['source_sha256'];reference=json.loads((folder/'receipt.json').read_bytes())
                    captured=read_capture(folder/'native.json.gz',expected_sha256=reference['native_sha256'],expected_source_sha256=d['source_sha256'])
                    new,proofs=repair(d,captured)
                    if proofs:
                        new['native_toc_alias_capture']=dict(path=str(folder/'native.json.gz'),sha256=reference['native_sha256'])
                        verify(new,captured)
                        if validate(new):raise ValueError('structure_contract_failed')
                        for field in ('blocks','chapter_tree','outline','pre_chunks','source_containers','source_scope_repairs','source_heading_units','source_heading_scope_deferrals','source_role_repairs'):
                            if d.get(field)!=new.get(field):raise ValueError('prior_content_or_repairs_changed:'+field)
                        target=out/(d['source_sha256']+'.document.json.gz')
                        target.write_bytes(gzip.compress(json.dumps(new,ensure_ascii=False).encode(),compresslevel=3,mtime=0))
                        selected[path]=dict(a,path=str(target),sha256=digest(target.read_bytes()),version=out.name)
                    counts['active_shared_ranges']+=len(new.get('shared_native_range_groups',[]))
                    del new,captured
                counts['raw_shared_ranges']+=groups;counts['aliases']+=len(proofs)
                counts['sec_artifacts']+=1;counts['changed_artifacts']+=bool(proofs)
                record=dict(source_sha256=d['source_sha256'],parent=a,artifact=selected[path],raw_groups=groups,proofs=proofs)
                stream.write(json.dumps(record,ensure_ascii=False)+'\n');stream.flush()
                del d,payload;gc.collect()
                if counts['sec_artifacts']%100==0:print(json.dumps(dict(counts)),flush=True)
            counts['changed_bindings']+=selected[path]!=a
            row['current_parser_artifact']=selected[path];row['processing']['current_parser_artifact']=selected[path]
    assert len(rows)==len({r['document_id'] for r in rows})==1742
    assert all(digest(Path(p).read_bytes())==h for p,h in frozen.items()) and ledger_hash==digest(Path(ledger).read_bytes())
    (out/'library-bindings.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf8')
    (out/'identity.json').write_text(json.dumps(dict(code=frozen,input_sha256=ledger_hash),indent=2),encoding='utf8')
    (out/'summary.json').write_text(json.dumps(dict(bindings=len(rows),counts=dict(counts),provider_calls=0,quality_pass=False),indent=2),encoding='utf8')
    print(json.dumps(dict(counts)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('ledger','captures','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();run(a.ledger,a.captures,a.output)
