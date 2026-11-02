"""Qualify original Part evidence across a complete frozen SEC selection."""
import argparse
from collections import Counter
import gc
import gzip
import json
from pathlib import Path
import shutil

from qualify_source_heading_units import digest, save, compare
from source_part_hierarchy import repair


def run(root, output):
    import psutil
    from finalize_structure_prechunks import classify
    from validate_source_structure_audit import validate
    prior = json.loads((root/'summary.json').read_bytes())
    if not prior['engineering_pass']: raise ValueError('incomplete_input_scope')
    here=Path(__file__).resolve().parent
    files=[here/n for n in ('source_part_hierarchy.py','qualify_source_part_hierarchy.py',
        'qualify_source_heading_units.py','native_document_adaptation.py','source_structure_contract.py',
        'finalize_structure_prechunks.py','validate_source_structure_audit.py')]
    files.extend(here.parents[1]/'src/retrieval'/n for n in ('narrative_chunks.py','structural_surface.py'))
    identity=dict(parent_summary_sha256=digest(root/'summary.json'),parent_identity_sha256=digest(root/'identity.json'),
                  scope=len(prior['rows']),code={str(p):digest(p) for p in files})
    output.mkdir(parents=True,exist_ok=True);stamp=output/'identity.json'
    if stamp.exists() and json.loads(stamp.read_bytes())!=identity: raise ValueError('resume_identity_changed')
    save(stamp,identity);rows=[];totals=Counter();stop=None
    for entry in prior['rows']:
        oid=entry['id'];previous=root/oid/'receipt.json';r=json.loads(previous.read_bytes())
        path=Path(r['artifact_path']);pre=Path(r['prechunks_path'])
        if digest(path)!=r['artifact_sha256'] or digest(pre)!=r['prechunks_sha256']: raise ValueError('input_changed')
        folder=output/oid;receipt=folder/'receipt.json'
        if receipt.exists():
            record=json.loads(receipt.read_bytes())
            if (record['previous_stage_receipt_sha256']!=digest(previous)
                or record['input_sha256']!=digest(path)
                or digest(record['artifact_path'])!=record['artifact_sha256']
                or digest(record['prechunks_path'])!=record['prechunks_sha256']): raise ValueError('resume_evidence_changed')
        else:
            if folder.exists(): raise ValueError('incomplete_attempt_requires_review:'+oid)
            available=psutil.virtual_memory().available//1024**2
            if available<1024 or shutil.disk_usage(output).free<2*1024**3:
                stop=dict(reason='resource_pause',id=oid,available_mib=available);break
            folder.mkdir()
            try:
                old=json.loads(gzip.decompress(path.read_bytes()))
                if old['source_sha256']!=oid: raise ValueError('source_identity_changed')
                new,proofs=repair(old)
                compare(old,new)
                errors=validate(new)
                if errors: raise ValueError('structure_contract:'+str(errors))
                changed=sum(bool(p.get('changed')) for p in proofs)
                counts=Counter(part_proposals=len(proofs),verified_part=sum(bool(p['selected_part']) for p in proofs),
                    changed_parents=changed,remaining_parent_conflicts=len(new.get('heading_parent_conflicts',[])),
                    shared_ranges=len(new.get('shared_range_reviews',[])))
                counts.update('part_status:'+p['status'] for p in proofs)
                # Persist proof annotations even on an unchanged chapter tree.
                for name,value in [('document',new),('prechunks',classify(new))]:
                    (folder/(name+'.json.gz')).write_bytes(gzip.compress(json.dumps(value,ensure_ascii=False).encode(),compresslevel=3,mtime=0))
                record=dict(id=oid,input_path=str(path),input_sha256=digest(path),
                    previous_stage_receipt=str(previous),previous_stage_receipt_sha256=digest(previous),
                    artifact_path=str(folder/'document.json.gz'),artifact_sha256=digest(folder/'document.json.gz'),
                    prechunks_path=str(folder/'prechunks.json.gz'),prechunks_sha256=digest(folder/'prechunks.json.gz'),
                    counts=dict(counts),part_proofs=proofs,engineering_pass=True,quality_pass=False)
                save(receipt,record);del old,new;gc.collect()
            except Exception as exc:
                save(folder/'failure.json',dict(id=oid,error=repr(exc)))
                stop=dict(reason='document_failure',id=oid,error=repr(exc));break
        totals.update(record['counts']);rows.append(dict(id=oid,counts=record['counts']))
        if len(rows)%50==0:
            save(output/'progress.json',dict(processed=len(rows),counts=dict(totals)))
            print(json.dumps(dict(processed=len(rows),counts=dict(totals))),flush=True)
    changed_code=[str(p) for p in files if digest(p)!=identity['code'][str(p)]]
    report=dict(planned=len(prior['rows']),processed=len(rows),rows=rows,counts=dict(totals),stop=stop,
        changed_code=changed_code,engineering_pass=not changed_code and not stop and len(rows)==len(prior['rows']),
        quality_pass=False,published=False,provider_calls=0)
    save(output/'summary.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}),flush=True)
    return 0 if report['engineering_pass'] else 75 if stop and stop['reason']=='resource_pause' else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();raise SystemExit(run(a.root,a.output))
