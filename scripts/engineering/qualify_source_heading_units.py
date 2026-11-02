"""Apply original-container headings to a frozen selection, retaining all evidence.

Workers are serial and recycled after ten documents. Failed directories are not
retried implicitly. Receipts cover unchanged documents as well as changed ones.
"""
import argparse
from collections import Counter
import gc
import gzip
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
import time

HERE=Path(__file__).resolve().parent


def digest(path):
    h=sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')


def compare(old,new):
    if old['source_sha256']!=new['source_sha256'] or old['source_containers']!=new['source_containers']:
        raise ValueError('original_identity_or_containers_changed')
    if len(old['blocks'])!=len(new['blocks']):raise ValueError('physical_block_count_changed')
    units={i:p for p in new['source_heading_units'] for i in p['blocks']};counts=Counter()
    sources={r['id']:r for r in old['source_containers']}
    for i,(a,b) in enumerate(zip(old['blocks'],new['blocks'])):
        for key in ('text','headers','rows','footer','raw_text','source_lines','native_xml','native_container_id','native_section_binding'):
            if a.get(key)!=b.get(key):raise ValueError('preserved_field_changed:'+key)
        if i not in units:
            for key in ('kind','structural_role','source_container_id','source_location_status'):
                if a.get(key)!=b.get(key):raise ValueError('unproved_role_or_location_change:'+key)
        elif a.get('source_container_id') and a.get('source_container_id')!=b.get('source_container_id'):
            s=sources[a['source_container_id']]
            if not(s.get('table_id') or s.get('internal_link_only') or s.get('excluded_navigation')):
                raise ValueError('body_source_replaced')
            counts['corrected_navigation_locations']+=1
        if a.get('chapter_ids',[]) and not b.get('chapter_ids',[]):raise ValueError('existing_chapter_cleared')
        if a.get('effective_scope',{}).get('kind')=='source_signature_scope' and a.get('chapter_ids')!=b.get('chapter_ids'):
            raise ValueError('signature_scope_changed')
        counts['changed_chapter_paths']+=a.get('chapter_ids',[])!=b.get('chapter_ids',[])
    for key in ('source_scope_repairs','native_sequence_alignments'):
        if old.get(key)!=new.get(key):raise ValueError('prior_repair_proof_changed:'+key)
    current={n['id']:n for n in new['chapter_tree']}
    for n in old['chapter_tree']:
        if n.get('basis')=='source_signature_and_adjacent_attestation' and current[n['id']]!=n:
            raise ValueError('signature_node_changed')
    counts.update(heading_units=len(new['source_heading_units']),
                  split_heading_units=sum(len(p['blocks'])>1 for p in new['source_heading_units']),
                  plain_heading_units=sum(p['previous_blocks'][0]['kind']=='text' for p in new['source_heading_units']),
                  shared_ranges=len(new['shared_native_range_groups']),
                  scope_deferrals=len(new.get('source_heading_scope_deferrals',[])))
    return dict(counts)


def worker(a,rows):
    import psutil
    from native_document_capture import read_capture
    from source_heading_units import repair
    from finalize_structure_prechunks import classify
    for row in rows[a.worker*10:(a.worker+1)*10]:
        oid=row['original_id'];out=a.output/oid
        if (out/'receipt.json').exists():continue
        if out.exists():raise ValueError('incomplete_attempt_requires_review:'+oid)
        available=psutil.virtual_memory().available//1024**2
        if available<1024 or shutil.disk_usage(a.output).free<2*1024**3:
            print(json.dumps(dict(resource_pause=True,id=oid,available_mib=available)),flush=True);return 75
        out.mkdir();started=time.monotonic()
        if digest(row['selected_artifact'])!=row['input_sha256']:raise ValueError('input_changed')
        capdir=a.captures/oid;capreceipt=json.loads((capdir/'receipt.json').read_bytes())
        capture=read_capture(capdir/'native.json.gz',expected_sha256=capreceipt['native_sha256'],expected_source_sha256=oid)
        old=json.loads(gzip.decompress(Path(row['selected_artifact']).read_bytes()))
        result=repair(old,capture);counts=compare(old,result);chunks=classify(result)
        for name,value in [('document',result),('prechunks',chunks)]:
            (out/(name+'.json.gz')).write_bytes(gzip.compress(json.dumps(value,ensure_ascii=False).encode(),compresslevel=3,mtime=0))
        old_unbound=set(old.get('native_section_coverage',{}).get('unbound_sections',[]))
        report=dict(id=oid,input_path=row['selected_artifact'],input_sha256=row['input_sha256'],
                    native_sha256=capreceipt['native_sha256'],counts=counts,
                    units=result['source_heading_units'],findings=result['source_heading_findings'],
                    shared_ranges=result['shared_native_range_groups'],
                    legacy_unbound_sections=sorted(old_unbound),
                    source_scoped_sections=sorted(p['section'] for p in result['source_heading_units']),
                    source_location_counts=dict(Counter(b.get('source_location_status','unset') for b in result['blocks'])),
                    no_native_sections=not capture['native'].get('sections'),
                    artifact_sha256=digest(out/'document.json.gz'),prechunks_sha256=digest(out/'prechunks.json.gz'),
                    seconds=round(time.monotonic()-started,3),engineering_pass=True,quality_pass=False,provider_calls=0)
        save(out/'receipt.json',report)
        print(json.dumps(dict(id=oid,counts=counts,seconds=report['seconds'])),flush=True)
        del capture,old,result,chunks,report;gc.collect()
    return 0


def run(a):
    rows=list(map(json.loads,a.plan.read_text(encoding='utf8').splitlines()))
    if len({r['original_id'] for r in rows})!=len(rows):raise ValueError('duplicate_id')
    if a.worker is not None:return worker(a,rows)
    files=['source_heading_units.py',Path(__file__).name,'source_structure_contract.py',
           'native_document_capture.py','native_document_adaptation.py','finalize_structure_prechunks.py',
           'validate_source_structure_audit.py']
    identity=dict(plan_sha256=digest(a.plan),code={n:digest(HERE/n) for n in files},
                  narrative_sha256=digest(HERE.parents[1]/'src/retrieval/narrative_chunks.py'),
                  structural_sha256=digest(HERE.parents[1]/'src/retrieval/structural_surface.py'),
                  python=sys.executable,quality_pass=False,provider_calls=0)
    a.output.mkdir(exist_ok=True,parents=True);stamp=a.output/'identity.json'
    if stamp.exists() and json.loads(stamp.read_bytes())!=identity:raise ValueError('frozen_identity_changed')
    save(stamp,identity);stop=None
    from run_native_structure_qualification import run_child
    for batch in range((len(rows)+9)//10):
        group=rows[batch*10:(batch+1)*10]
        if all((a.output/r['original_id']/'receipt.json').exists() for r in group):continue
        # Each ten-document worker has the same bounded 600s watchdog. Logs from
        # resource pauses use a new suffix and failed attempts remain untouched.
        log=a.output/f'batch-{batch:03d}-{time.time_ns()}.log'
        code=run_child([sys.executable,str(Path(__file__)), '--plan',str(a.plan),'--captures',str(a.captures),
                        '--output',str(a.output),'--worker',str(batch)],log,600)
        done=sum((a.output/r['original_id']/'receipt.json').exists() for r in rows)
        print(json.dumps(dict(completed=done,planned=len(rows),batch=batch,exit_code=code)),flush=True)
        save(a.output/'progress.json',dict(completed=done,planned=len(rows),batch=batch,exit_code=code))
        if code:stop=dict(batch=batch,exit_code=code,log=str(log));break
    totals=Counter();reports=[];findings=[]
    for row in rows:
        folder=a.output/row['original_id'];path=folder/'receipt.json'
        if not path.exists():continue
        r=json.loads(path.read_bytes())
        for file,key in [('document.json.gz','artifact_sha256'),('prechunks.json.gz','prechunks_sha256')]:
            if digest(folder/file)!=r[key]:findings.append(dict(id=row['original_id'],kind='output_digest_changed'))
        if digest(row['selected_artifact'])!=row['input_sha256'] or r['input_sha256']!=row['input_sha256']:
            findings.append(dict(id=row['original_id'],kind='input_changed'))
        if digest(a.captures/row['original_id']/'native.json.gz')!=r['native_sha256']:
            findings.append(dict(id=row['original_id'],kind='native_changed'))
        totals.update(r['counts']);reports.append(dict(id=r['id'],counts=r['counts'],no_native_sections=r['no_native_sections']))
    changed=[n for n,h in identity['code'].items() if digest(HERE/n)!=h]
    if digest(HERE.parents[1]/'src/retrieval/narrative_chunks.py')!=identity['narrative_sha256']:changed.append('narrative_chunks')
    if digest(HERE.parents[1]/'src/retrieval/structural_surface.py')!=identity['structural_sha256']:changed.append('structural_surface')
    result=dict(planned=len(rows),processed=len(reports),counts=dict(totals),rows=reports,stop=stop,
                findings=findings,changed_code=changed,engineering_pass=len(rows)==len(reports) and not stop and not findings and not changed,
                quality_pass=False,published=False,provider_calls=0)
    save(a.output/'summary.json',result);print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)
    return 0 if result['engineering_pass'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','captures','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--worker',type=int)
    raise SystemExit(run(p.parse_args()))
