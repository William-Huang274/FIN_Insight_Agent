"""Hold contradictory Part evidence without undoing a proved Item heading.

This final compatibility stage is separate from the frozen heading recovery
stage. All inputs are checked; unchanged artifacts are referenced, not copied.
"""
from collections import Counter
from copy import deepcopy
import gc
import gzip
import json
from pathlib import Path

from qualify_source_heading_units import digest,save,compare


def reconcile(document):
    conflicts=[]
    for u in document.get('source_heading_units',[]):
        native=document.get('parser_sections',{}).get(u['section'],{}).get('part')
        if native and u.get('part') and str(native).upper()!=u['part'].upper():
            conflicts.append(dict(unit=u['id'],section=u['section'],chapter=u['chapter_id'],
                                  source_part_proposal=u['part'],native_part_proposal=native,
                                  source_part_container=u.get('part_source_id'),selected_part=None,
                                  status='conflicting_parent_evidence_requires_original_review'))
    if not conflicts:return document,[]
    d=deepcopy(document);nodes={n['id']:n for n in d['chapter_tree']};roots={c['chapter'] for c in conflicts}
    for c in conflicts:
        node=nodes[c['chapter']]
        node['previous_parent_before_conflict_gate']=node.get('parent_id')
        node.update(parent_id=None,parent_resolution=c['status'])
        unit=next(u for u in d['source_heading_units'] if u['id']==c['unit'])
        unit['part_proposal_before_conflict_gate']=unit['part']
        unit['part_source_proposal_before_conflict_gate']=unit.get('part_source_id')
        unit.update(part=None,part_source_id=None,parent_resolution=c['status'])
    def ancestry(cid):
        path=[];seen=set()
        while cid:
            if cid in seen:raise ValueError('parent_conflict_cycle')
            seen.add(cid);path.append(cid);cid=nodes[cid].get('parent_id')
        return list(reversed(path))
    for node in nodes.values():
        if roots.intersection(ancestry(node['id'])):
            node['level_before_parent_conflict_gate']=node.get('level');node['level']=None
    for b in d['blocks']:
        old=b.get('chapter_ids',[])
        if not roots.intersection(old):continue
        b['chapter_ids_before_parent_conflict_gate']=list(old)
        b['chapter_ids']=ancestry(old[-1]);b['chapter_blocks']=[nodes[c]['block'] for c in b['chapter_ids']]
    d['heading_parent_conflicts']=conflicts
    from native_document_adaptation import finish
    return finish(d),conflicts


def run(root,output):
    import psutil
    prior=json.loads((root/'summary.json').read_bytes())
    if not prior['engineering_pass']:raise ValueError('incomplete_parent_batch')
    frozen=json.loads((root/'identity.json').read_bytes());here=Path(__file__).resolve().parent
    for name,value in frozen['code'].items():
        if digest(here/name)!=value:raise ValueError('upstream_implementation_changed:'+name)
    for name,relative in [('narrative_sha256','src/retrieval/narrative_chunks.py'),('structural_sha256','src/retrieval/structural_surface.py')]:
        if name in frozen and digest(here.parents[1]/relative)!=frozen[name]:raise ValueError('upstream_dependency_changed:'+name)
    files=[Path(__file__),Path(__file__).with_name('qualify_source_heading_units.py'),
           Path(__file__).with_name('native_document_adaptation.py')]
    identity=dict(input_summary_sha256=digest(root/'summary.json'),input_identity_sha256=digest(root/'identity.json'),
                  code={str(p):digest(p) for p in files},scope=len(prior['rows']))
    output.mkdir(exist_ok=True,parents=True)
    stamp=output/'identity.json'
    if stamp.exists() and json.loads(stamp.read_bytes())!=identity:raise ValueError('parent_gate_resume_identity_changed')
    save(stamp,identity)
    totals=Counter();rows=[];all_conflicts=[];stop=None
    for entry in prior['rows']:
        oid=entry['id'];path=root/oid/'document.json.gz';receipt_path=root/oid/'receipt.json'
        receipt=json.loads(receipt_path.read_bytes())
        if digest(path)!=receipt['artifact_sha256']:raise ValueError('parent_artifact_changed')
        completed=output/oid/'receipt.json'
        if completed.exists():
            r=json.loads(completed.read_bytes())
            if (r['input_sha256']!=digest(path) or r['previous_stage_receipt_sha256']!=digest(receipt_path)
                    or digest(r['artifact_path'])!=r['artifact_sha256'] or digest(r['prechunks_path'])!=r['prechunks_sha256']):
                raise ValueError('parent_gate_resume_evidence_changed')
            totals.update(r['counts']);rows.append(dict(id=oid,counts=r['counts']))
            all_conflicts.extend(dict(id=oid,**c) for c in r['parent_conflicts']);continue
        if (output/oid).exists():raise ValueError('incomplete_parent_gate_attempt_requires_review')
        available=psutil.virtual_memory().available//1024**2
        if available<1024:
            stop=dict(reason='resource_pause',available_mib=available,id=oid);break
        d=json.loads(gzip.decompress(path.read_bytes()));result,conflicts=reconcile(d)
        if conflicts:
            compare(d,result)
            from finalize_structure_prechunks import classify
            folder=output/oid;folder.mkdir()
            for name,data in [('document',result),('prechunks',classify(result))]:
                (folder/(name+'.json.gz')).write_bytes(gzip.compress(json.dumps(data,ensure_ascii=False).encode(),compresslevel=3,mtime=0))
            selected=folder/'document.json.gz';pre=folder/'prechunks.json.gz'
        else:
            (output/oid).mkdir();selected=path;pre=root/oid/'prechunks.json.gz'
        receipt.update(input_path=str(path),input_sha256=digest(path),
                       previous_stage_receipt=str(receipt_path),previous_stage_receipt_sha256=digest(receipt_path),
                       artifact_path=str(selected),artifact_sha256=digest(selected),prechunks_path=str(pre),prechunks_sha256=digest(pre),
                       units=result.get('source_heading_units',[]),parent_conflicts=conflicts)
        receipt['counts']['parent_conflicts_deferred']=len(conflicts)
        save(output/oid/'receipt.json',receipt);totals.update(receipt['counts'])
        rows.append(dict(id=oid,counts=receipt['counts']));all_conflicts.extend(dict(id=oid,**c) for c in conflicts)
        del d,result,receipt;gc.collect()
        if len(rows)%100==0:print(json.dumps(dict(processed=len(rows),parent_conflicts=len(all_conflicts))),flush=True)
    changed=[str(p) for p in files if digest(p)!=identity['code'][str(p)]]
    report=dict(planned=len(prior['rows']),processed=len(rows),rows=rows,counts=dict(totals),parent_conflicts=all_conflicts,
                engineering_pass=not changed and not stop and len(rows)==len(prior['rows']),changed_code=changed,stop=stop,quality_pass=False,published=False,provider_calls=0,
                parent_identity=identity)
    save(output/'summary.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in {'rows','parent_identity'}}),flush=True)
    return 0 if report['engineering_pass'] else 1


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();raise SystemExit(run(a.root,a.output))
