"""Audit the whole library selection; count unresolved structure, not accuracy.

Keeps native hypotheses and source-evidenced repairs separate. Each route uses
its own immutable evidence version; missing originals remain in the denominator.
"""
import argparse
from collections import Counter,defaultdict
import gc
import gzip
import json
from pathlib import Path

from qualify_source_heading_units import digest,save
from validate_source_structure_audit import validate
from source_heading_units import matching_sequences


def text_observations(d):
    blocks=d['blocks'];nodes=d['chapter_tree'];counts=Counter(blocks=len(blocks),chapters=len(nodes))
    issues=[];units=d.get('source_heading_units',[])
    sources={s['id']:s for s in d.get('source_containers',[])}
    if 'source_part_proofs' in d:
        from source_part_hierarchy import proposals
        reproved={p['unit']:p for p in proposals(d)}
        for proof in d['source_part_proofs']:
            counts['source_part_status:'+proof['status']]+=1
            if not proof.get('changed'):continue
            fresh=reproved.get(proof['unit'],{})
            if any(fresh.get(k)!=proof.get(k) for k in ('selected_part','source_id','block','status')):
                raise ValueError('source_part_evidence_not_reproducible')
            node=next(n for n in nodes if n['id']==proof['chapter'])
            parent=next((n for n in nodes if n['id']==node.get('parent_id')),None)
            if not parent or parent.get('source_container_id')!=proof['source_id'] or parent['block']!=proof['block']:
                raise ValueError('source_part_proof_not_consumed')
            counts['source_part_parents_repaired']+=1
    for unit in units:
        native_part=d.get('parser_sections',{}).get(unit['section'],{}).get('part')
        if native_part and unit.get('part') and str(native_part).upper()!=unit['part'].upper():
            raise ValueError('selected_heading_parent_conflicts_with_native_evidence')
        if native_part and not unit.get('part'):
            counts['heading_units_without_verified_part']+=1
            issues.append(dict(kind='unverified_heading_part',chapter=unit['chapter_id'],section=unit['section'],native_part_proposal=native_part))
        if unit['blocks'] not in matching_sequences(blocks,[unit['blocks'][0]],unit['title']):
            raise ValueError('heading_unit_content_not_exact')
        if sources[unit['source_id']]['text']!=unit['title']:
            from source_structure_contract import normalized
            if normalized(sources[unit['source_id']]['text'])!=unit['title']:raise ValueError('heading_source_text_differs')
        node=next(n for n in nodes if n['id']==unit['chapter_id'])
        if node['title']!=unit['title'] or node.get('navigation_status')=='compatibility_only':
            raise ValueError('complete_heading_not_consumed')
        if any(not blocks[i].get('structural_only') for i in unit['blocks']):raise ValueError('heading_fragment_leaks_to_prose')
    counts['source_heading_units']=len(units)
    counts['source_signature_scopes']=len(d.get('source_scope_repairs',[]))
    counts['source_role_repairs']=len(d.get('source_role_repairs',[]))
    for i,b in enumerate(blocks):
        counts['block_kind:'+b['kind']]+=1
        if b.get('text','').strip():
            counts['nonblank_blocks']+=1
            counts['location:'+b.get('source_location_status','not_recorded')]+=1
        if len(b.get('native_section_binding',{}).get('candidates',[]))>1:counts['multiple_native_membership_blocks']+=1
    for n in nodes:
        hidden=n.get('navigation_status')=='compatibility_only'
        counts['compatibility_only_chapters']+=hidden
        counts['visible_unknown_levels']+=not hidden and n.get('level') is None
        if not hidden and n.get('level') is None:
            scope='embedded_container' if n.get('embedded_in_table') and n.get('scope')=='physical_container_only' else 'document_hierarchy'
            counts['unknown_level_scope:'+scope]+=1
        status=n.get('title_binding',{}).get('status')
        if status:counts['title_binding:'+status]+=1
        if status in {'heading_not_bound','ambiguous_heading'}:
            issues.append(dict(kind='unresolved_native_title',chapter=n['id'],block=n['block'],status=status,title=n['title']))
    sections=set(d.get('parser_sections',{}))
    native_bound={k for b in blocks if b.get('native_section_binding',{}).get('status')=='unique_native_membership'
                  for k in b['native_section_binding']['candidates']}
    repaired={p['section'] for p in units}
    counts['native_sections']=len(sections);counts['no_native_sections_documents']=not bool(sections)
    counts['native_sections_without_unique_blocks']=len(sections-native_bound)
    counts['formerly_unbound_with_source_heading']=len((sections-native_bound)&repaired)
    unresolved=sections-native_bound-repaired
    counts['sections_without_native_blocks_or_source_heading']=len(unresolved)
    for key in sorted(unresolved):issues.append(dict(kind='section_without_native_blocks_or_source_heading',section=key,metadata=d['parser_sections'][key]))
    for group in d.get('shared_native_range_groups',[]):
        issues.append(dict(kind='shared_original_range',**group));counts['shared_original_ranges']+=1
        counts['sections_in_shared_original_ranges']+=len(group['sections'])
    for f in d.get('source_heading_findings',[]):
        issues.append(dict(kind='heading_proof_unresolved',detail=f));counts['heading_finding:'+f['kind']]+=1
    for f in d.get('source_heading_scope_deferrals',[]):
        issues.append(dict(kind='source_scope_boundary_deferred',detail=f));counts['scope_boundary_deferred_blocks']+=1
    for f in d.get('heading_parent_conflicts',[]):
        issues.append(dict(kind='conflicting_heading_parent_evidence',detail=f));counts['conflicting_parent_evidence']+=1
    counts['verified_web_title']=d.get('document_title',{}).get('status')=='verified_original_heading'
    counts['embedded_html_blocks']=len(d.get('embedded_html_repairs',[]))
    counts['embedded_html_tables']=sum(len(b.get('embedded_html_structure',{}).get('tables',[])) for b in blocks)
    counts['embedded_html_images']=sum(len(b.get('embedded_html_structure',{}).get('images',[])) for b in blocks)
    return counts,issues


def coverage_gaps(lane,counts):
    """These are unsatisfied review dimensions, not invented defect labels."""
    result=[]
    if lane in {'sec','web','markdown'}:
        result.append(dict(kind='original_based_role_hierarchy_quality_not_accepted',p_ids=['P04','P06','P25','P27'],status='quality_evidence_gap'))
        if counts.get('block_kind:table'):
            result.append(dict(kind='logical_table_header_footnote_quality_not_accepted',p_ids=['P12','P13','P24'],
                               physical_tables=counts['block_kind:table'],status='quality_evidence_gap'))
    if lane=='sec' and counts['no_native_sections_documents']:
        result.append(dict(kind='no_native_sections_format_route',p_ids=['P02','P11'],status='requires_format_specific_adaptation'))
    if lane=='web':
        result.append(dict(kind='web_purpose_and_original_coverage_not_accepted',p_ids=['P14','P15','P16'],status='quality_evidence_gap'))
    if lane=='markdown':
        result.append(dict(kind='markdown_rendered_html_table_quality_not_accepted',p_ids=['P17','P18'],status='quality_evidence_gap'))
    return result


def issue_record(oid,lane,document_title,issue):
    return dict(original_id=oid,lane=lane,document_title=document_title,**issue)


def audit(a):
    prior=list(map(json.loads,a.selection.read_text(encoding='utf8').splitlines()))
    inventory={r['original_id']:r for r in map(json.loads,a.inventory.read_text(encoding='utf8').splitlines())}
    scope=json.loads(a.scope.read_bytes());ids=[r['original_id'] for r in prior]
    if len(set(ids))!=len(ids) or set(ids)!=set(inventory):raise ValueError('full_library_identity_mismatch')
    binding_ids=[b for r in prior for b in r['bindings']]
    if len(binding_ids)!=len(set(binding_ids)) or len(binding_ids)!=scope['available_original_bindings']:
        raise ValueError('binding_identity_mismatch')
    binding_rows=list(map(json.loads,a.bindings.read_text(encoding='utf8').splitlines()))
    all_bindings={r['document_id']:r for r in binding_rows}
    if len(all_bindings)!=len(binding_rows) or len(all_bindings)!=scope['library_bindings']:
        raise ValueError('whole_binding_inventory_mismatch')
    missing=[r for r in binding_rows if not r.get('original_id')]
    if len(missing)!=scope['missing_original_bindings'] or set(binding_ids)!={r['document_id'] for r in binding_rows if r.get('original_id')}:
        raise ValueError('missing_original_denominator_mismatch')
    for r in prior:
        if any(all_bindings[b]['original_id']!=r['original_id'] for b in r['bindings']):raise ValueError('binding_original_disagrees')
    if a.sec:
        sec_summary=json.loads((a.sec/'summary.json').read_bytes())
        if not sec_summary['engineering_pass'] or {r['id'] for r in sec_summary['rows']}!={r['original_id'] for r in prior if r['lane']=='sec'}:
            raise ValueError('sec_scope_incomplete')
    proofs={}
    for lane,path in [('pdf',a.root/'pdf-r2-continuation-r1/receipt-audit.json'),('structured',a.root/'structured-r1/receipt-audit.json')]:
        report=json.loads(path.read_bytes())
        if not report['evidence_pass']:raise ValueError('prior_evidence_failed:'+lane)
        proofs[lane]={p['id']:p for p in report['proofs']}
    a.output.mkdir(exist_ok=False,parents=True)
    totals=defaultdict(Counter);rows=[];failures=[];versions=Counter()
    with (a.output/'issues.jsonl').open('w',encoding='utf8') as problems:
        for r in missing:problems.write(json.dumps(dict(kind='missing_verified_original',**r),ensure_ascii=False)+'\n')
        for index,r in enumerate(prior):
            oid=r['original_id'];lane=r['lane'];path=Path(r['selected_artifact']);version=r['version']
            try:
                if lane=='sec' and a.sec:
                    path=a.sec/oid/'document.json.gz';version=a.sec.name
                    receipt=json.loads((path.parent/'receipt.json').read_bytes());expected=receipt['artifact_sha256']
                    path=Path(receipt.get('artifact_path',path))
                    if receipt.get('previous_stage_receipt') and digest(receipt['previous_stage_receipt'])!=receipt['previous_stage_receipt_sha256']:
                        raise ValueError('previous_stage_receipt_changed')
                elif lane in {'sec','web','markdown'}:
                    receipt_path=path.parent/'receipt.json'
                    if not receipt_path.exists():receipt_path=a.root/'structure-r2/receipts'/f'{oid}.json'
                    receipt=json.loads(receipt_path.read_bytes());expected=receipt['artifact_sha256']
                else:expected=proofs[lane][oid]['sha256']
                if digest(path)!=expected:raise ValueError('selected_artifact_changed')
                d=json.loads(gzip.decompress(path.read_bytes())) if path.suffix=='.gz' else json.loads(path.read_bytes())
                if d['source_sha256']!=oid:raise ValueError('original_identity_mismatch')
                counts=Counter(documents=1);issues=[]
                if lane in {'sec','web','markdown'}:
                    errors=validate(d)
                    if errors:raise ValueError('structure_contract:'+str(errors))
                    extra,issues=text_observations(d);counts.update(extra)
                    issues.extend(coverage_gaps(lane,counts))
                elif lane=='pdf':
                    if not d['engineering_pass'] or [p['page'] for p in d['pages']]!=list(range(1,d['planned_pages']+1)):
                        raise ValueError('pdf_page_scope')
                    for p in d['pages']:
                        pagepath=path.parent/'pages'/f"{p['page']:05d}.json.gz"
                        if digest(pagepath)!=p['artifact_sha256']:raise ValueError('pdf_page_digest')
                        page=json.loads(gzip.decompress(pagepath.read_bytes()))
                        if page['errors'] or page.get('table_layout_model_enabled') is not False:raise ValueError('pdf_page_contract')
                    counts.update(d['counts']);counts['pages']=d['planned_pages']
                    issues=[dict(kind='pdf_layout_quality_not_independently_accepted',pages=d['planned_pages'],p_ids=['P19','P20','P21','P22','P27'],status='quality_evidence_gap')]
                else:
                    if not d['source_object_conserved']:raise ValueError('record_conservation_not_proved')
                    counts['record_kind:'+d['kind']]+=1
                    issues=[dict(kind='record_consumer_semantics_not_accepted',record_kind=d['kind'],p_ids=['P23','P24'],status='consumer_contract_gap')]
                for issue in issues:problems.write(json.dumps(issue_record(oid,lane,inventory[oid]['title'],issue),ensure_ascii=False)+'\n')
                totals[lane].update(counts);versions[version]+=1
                rows.append(dict(r,selected_artifact=str(path),selected_sha256=expected,version=version,
                                 observations=dict(counts),quality_pass=False,published=False))
                del d;gc.collect()
            except Exception as exc:failures.append(dict(id=oid,lane=lane,error=repr(exc)))
            if (index+1)%100==0:
                progress=dict(checked=index+1,failures=len(failures),first_failures=failures[:2])
                save(a.output/'progress.json',progress);print(json.dumps(progress),flush=True)
    (a.output/'selection.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf8')
    result=dict(originals=len(prior),verified=len(rows),available_bindings=len(binding_ids),
                missing_original_bindings=scope['missing_original_bindings'],total_bindings=scope['library_bindings'],
                counts={k:dict(v) for k,v in totals.items()},versions=dict(versions),failures=failures,
                engineering_pass=not failures and len(rows)==len(prior),quality_pass=False,published=False,
                single_version_full_library_pass=False,provider_calls=0,
                input_sha256=dict(selection=digest(a.selection),inventory=digest(a.inventory),bindings=digest(a.bindings),scope=digest(a.scope),sec_summary=digest(a.sec/'summary.json') if a.sec else None))
    if result['available_bindings']+result['missing_original_bindings']!=result['total_bindings']:raise ValueError('total_denominator_mismatch')
    save(a.output/'summary.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in {'counts','failures'}}),flush=True)
    return 0 if result['engineering_pass'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('selection','inventory','bindings','scope','root','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--sec',type=Path)
    raise SystemExit(audit(p.parse_args()))
