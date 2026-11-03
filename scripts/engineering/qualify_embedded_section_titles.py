"""Serial full-ledger qualification of original embedded SEC title rows."""
import argparse
from collections import Counter
import gc
import gzip
import json
from pathlib import Path
import zlib

from audit_source_binding_lineage import digest, read_lines, readonly
from embedded_section_titles import repair, verify
from validate_source_structure_audit import validate


def original(source):
    if source.get('path'):
        raw=Path(source['path']).read_bytes()
    else:
        with readonly(source['database']) as db:
            value=db.execute('SELECT body_zlib FROM raw_captures WHERE url=? AND digest=?',
                             (source['url'],source['current_sha256'])).fetchone()
        if value is None:raise ValueError('original_missing')
        raw=zlib.decompress(value[0])
    if digest(raw)!=source['current_sha256']:raise ValueError('original_changed')
    return raw


def run(ledger,output,kind='embedded'):
    if kind=='source':
        from source_section_title_links import repair as apply,verify as verify_titles
    elif kind=='equivalent':
        from equivalent_section_titles import repair as equivalent_repair, verify as verify_titles
        def apply(document,raw):
            updated,proofs=equivalent_repair(document,raw)
            return updated,proofs,[]
    else:
        apply=repair;verify_titles=verify
    rows=read_lines(ledger);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__).with_name(n) for n in ('qualify_embedded_section_titles.py','embedded_section_titles.py',
           'equivalent_section_titles.py','source_section_title_links.py','document_structure_repairs.py','source_heading_units.py',
           'native_document_adaptation.py','source_structure_contract.py','validate_source_structure_audit.py')]
    identity=dict(input_sha256=digest(Path(ledger).read_bytes()),code={str(p):digest(p.read_bytes()) for p in files})
    selected={};counts=Counter();receipts=[]
    with (out/'receipts.jsonl').open('w',encoding='utf8') as stream:
        for row in rows:
            a=row.get('current_parser_artifact') or {}
            if a.get('lane')!='sec':continue
            path=a['path']
            if path not in selected:
                payload=Path(path).read_bytes()
                if digest(payload)!=a['sha256']:raise ValueError('parent_changed')
                old=json.loads(gzip.decompress(payload))
                pending=[n for n in old['chapter_tree'] if n.get('title_binding',{}).get('status') in {'heading_not_bound','ambiguous_heading'}]
                proofs=[];findings=[];selected[path]=a
                if pending:
                    raw=original(row['current_source']);new,proofs,findings=apply(old,raw)
                    if proofs:
                        verify_titles(new,raw)
                        if validate(new):raise ValueError('structure_contract_failed')
                        # This slice changes title metadata only; physical
                        # content, all old scopes and prechunk records must stay.
                        for before,after in zip(old['blocks'],new['blocks']):
                            restored=dict(after)
                            if kind=='embedded':
                                if 'embedded_section_titles' in before:restored['embedded_section_titles']=before['embedded_section_titles']
                                else:restored.pop('embedded_section_titles',None)
                            if restored!=before:raise ValueError('physical_block_or_scope_changed')
                        if old['pre_chunks']!=new['pre_chunks']:raise ValueError('prechunks_changed')
                        target=out/(old['source_sha256']+'.document.json.gz')
                        target.write_bytes(gzip.compress(json.dumps(new,ensure_ascii=False).encode(),compresslevel=3,mtime=0))
                        selected[path]=dict(path=str(target),sha256=digest(target.read_bytes()),lane='sec',version=out.name,quality_pass=False)
                    del new,raw
                receipt=dict(parent_path=path,parent_sha256=a['sha256'],source_sha256=old['source_sha256'],
                    pending=len(pending),proofs=proofs,findings=findings,artifact=selected[path])
                stream.write(json.dumps(receipt,ensure_ascii=False)+'\n');stream.flush();receipts.append(receipt)
                counts['sec_artifacts']+=1;counts['pending_titles']+=len(pending)
                counts['bound_'+kind+'_titles']+=len(proofs);counts['changed_artifacts']+=bool(proofs)
                counts.update('finding:'+f['status'] for f in findings)
                del old,payload;gc.collect()
                if counts['sec_artifacts']%50==0:print(json.dumps(dict(counts)),flush=True)
            if selected[path]!=a:counts['changed_bindings']+=1
            row['current_parser_artifact']=selected[path]
            row['processing']['current_parser_artifact']=selected[path]
    assert len(rows)==len({r['document_id'] for r in rows})
    assert identity['input_sha256']==digest(Path(ledger).read_bytes())
    assert all(digest(Path(p).read_bytes())==v for p,v in identity['code'].items())
    (out/'library-bindings.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf8')
    (out/'identity.json').write_text(json.dumps(identity,indent=2),encoding='utf8')
    (out/'summary.json').write_text(json.dumps(dict(bindings=len(rows),counts=dict(counts),quality_pass=False,provider_calls=0),indent=2),encoding='utf8')
    print(json.dumps(dict(counts)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ledger',required=True);p.add_argument('--output',required=True)
    p.add_argument('--kind',choices=['embedded','equivalent','source'],default='embedded')
    a=p.parse_args();run(a.ledger,a.output,a.kind)
