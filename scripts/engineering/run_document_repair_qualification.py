"""Qualify source repairs over all selected frozen artifacts, retaining failures."""
import argparse
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path
import time

from document_structure_repairs import repair_sec_signatures, repair_markdown_html
from document_role_repairs import repair_context_roles
from native_web_adaptation import restore_original_bindings
from native_document_adaptation import finish
from finalize_structure_prechunks import classify
from validate_source_structure_audit import validate


def run(inventory, output):
    output.mkdir(parents=True,exist_ok=False)
    rows=[json.loads(s) for s in inventory.read_text(encoding='utf8').splitlines()]
    selected=[r for r in rows if r['lane'] in {'sec','web','markdown'}]
    scripts=['document_structure_repairs.py','document_role_repairs.py','native_web_adaptation.py','native_document_adaptation.py',
             'finalize_structure_prechunks.py','source_structure_contract.py','validate_source_structure_audit.py',Path(__file__).name]
    identity=dict(inventory_sha256=sha256(inventory.read_bytes()).hexdigest(),planned=len(selected),
                  code={n:sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in scripts},provider_calls=0,published=False)
    (output/'identity.json').write_text(json.dumps(identity,indent=2),encoding='utf8')
    totals=Counter(); receipts=[]; summaries={}
    for position,row in enumerate(selected):
        started=time.monotonic();oid=row['original_id'];lane=row['lane']
        receipt=dict(id=oid,lane=lane,title=row['title'],family=row['family'])
        try:
            directory=Path(row['evidence_directory'])
            if str(directory) not in summaries:summaries[str(directory)]={r['source_sha256']:r for r in json.loads((directory/'summary.json').read_bytes())['rows']}
            oldrow=summaries[str(directory)][oid]
            path=directory/'adapted'/oid/'document.json.gz';raw=path.read_bytes()
            if sha256(raw).hexdigest()!=oldrow['receipt']['artifact_sha256']:raise ValueError('parent_digest_mismatch')
            previous=json.loads(gzip.decompress(raw));receipt.update(parent_path=str(path),parent_sha256=sha256(raw).hexdigest())
            if lane=='sec':
                result=repair_sec_signatures(previous)
                changes=len(result['source_scope_repairs']);totals['source_signature_scopes']+=changes
                totals['signature_reparented']+=sum(c['previous_parent_id'] is not None for c in result['source_scope_repairs'])
                result=repair_context_roles(result)
                changes+=len(result['source_role_repairs']);totals['context_role_repairs']+=len(result['source_role_repairs'])
                # No-op metadata does not require another full document copy.
                changed=bool(changes)
            elif lane=='web':
                baseline_raw=Path(row['existing_baseline']).read_bytes()
                if sha256(baseline_raw).hexdigest()!=row['existing_baseline_sha256']:raise ValueError('baseline_digest_mismatch')
                result=finish(restore_original_bindings(json.loads(gzip.decompress(raw)),json.loads(gzip.decompress(baseline_raw))))
                changes=1;changed=True
                totals['restored_verified_web_titles']+=result['document_title']['status']=='verified_original_heading'
                totals['mapped_web_blocks']+=sum(b.get('source_location_status')=='unique_complete_container' for b in result['blocks'])
            else:
                result=repair_markdown_html(previous);changes=len(result['embedded_html_repairs']);changed=bool(changes)
                totals['parsed_markdown_html_blocks']+=changes
                totals['markdown_html_failures']+=sum('embedded_html_failure' in b for b in result['blocks'])
            if [b['text'] for b in previous['blocks']] != [b['text'] for b in result['blocks']]:raise ValueError('block_text_changed')
            role_changes={c['block'] for c in result.get('source_role_repairs',[])}
            for index,(old,new) in enumerate(zip(previous['blocks'],result['blocks'])):
                for key in ('kind','headers','rows','footer','raw_text','source_lines','native_xml'):
                    if key=='kind' and index in role_changes and old[key]=='heading' and new[key]=='text':continue
                    if old.get(key)!=new.get(key):raise ValueError('content_or_table_field_changed:'+key)
            errors=validate(result)
            if errors:raise ValueError('structure_invalid:'+str(errors))
            final=classify(result)
            if changed:
                target=output/'adapted'/oid;target.mkdir(parents=True)
                packed=gzip.compress(json.dumps(result,ensure_ascii=False).encode(),mtime=0)
                (target/'document.json.gz').write_bytes(packed)
                (target/'prechunks.json.gz').write_bytes(gzip.compress(json.dumps(final,ensure_ascii=False).encode(),mtime=0))
                receipt.update(artifact_path=str(target/'document.json.gz'),artifact_sha256=sha256(packed).hexdigest())
            else:receipt.update(artifact_path=str(path),artifact_sha256=sha256(raw).hexdigest())
            receipt.update(status='repaired' if changed else 'parent_retained',changes=changes,content_conserved=True,
                           structure_references_valid=True,quality_pass=False)
        except Exception as exc:
            receipt.update(status='failed',error=type(exc).__name__,detail=str(exc))
        receipt['elapsed_seconds']=round(time.monotonic()-started,3)
        receipts.append(receipt);totals[receipt['status']]+=1
        (output/'receipts').mkdir(exist_ok=True)
        (output/'receipts'/f'{oid}.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
        summary=dict(planned=len(selected),processed=len(receipts),counts=dict(totals),rows=receipts,quality_pass=False,provider_calls=0)
        (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False),encoding='utf8')
        if (position+1)%25==0 or receipt['status']=='failed':print(json.dumps(dict(processed=position+1,counts=dict(totals))),flush=True)
    changed_code=[n for n,digest in identity['code'].items() if sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()!=digest]
    report=dict(planned=len(selected),processed=len(receipts),counts=dict(totals),code_changed=changed_code,
                engineering_pass=not totals['failed'] and not changed_code,quality_pass=False,provider_calls=0)
    (output/'final-audit.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report),flush=True)
    return 0 if report['engineering_pass'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inventory',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();raise SystemExit(run(a.inventory,a.output))
