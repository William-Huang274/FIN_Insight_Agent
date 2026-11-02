"""Audit current full-library bindings, applying proven marker consumption once.

One denominator includes prior parses, recovered sources, new original receipts,
and scoped derivatives. Engineering checks and quality gaps remain distinct.
"""
import argparse
from collections import Counter,defaultdict
import gc
import gzip
from hashlib import file_digest
import json
import zlib
from pathlib import Path

from audit_source_binding_lineage import digest,read_json,read_lines,readonly


def read_artifact(path,expected):
    data=Path(path).read_bytes()
    if digest(data)!=expected:raise ValueError('artifact_digest_changed')
    return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)


def audit_derived(document,source_id):
    """Validate preserved material without upgrading it to an original."""
    from validate_source_structure_audit import validate
    if 'blocks' in document:
        errors=validate(document)
        if errors:raise ValueError('derived_structure_contract:'+str(errors))
        texts=[b.get('text','') for b in document['blocks']]
        observations=dict(blocks=len(texts),chapters=len(document.get('chapter_tree',[])))
    else:
        nodes=document['nodes'];texts=[n['content'] for n in nodes]
        if len({n['node_id'] for n in nodes})!=len(nodes):raise ValueError('derived_duplicate_nodes')
        for n in nodes:
            if n.get('parent_document_id')!=source_id:raise ValueError('derived_source_identity')
            if n.get('content_sha256')!=digest(n['content'].encode()):raise ValueError('derived_node_digest')
            if n.get('numeric_authority') or n.get('citation_eligible'):raise ValueError('unproved_derived_authority')
        spans=defaultdict(list)
        for c in document['pre_chunks']:
            index=c['node_index']
            if not 0<=index<len(nodes):raise ValueError('derived_unknown_node')
            spans[index].append((c['start'],c['end']))
        for index,parts in spans.items():
            end=0
            for start,stop in parts:
                if start!=end or stop<start or stop>len(texts[index]):raise ValueError('derived_span_gap')
                end=stop
            if end!=len(texts[index]):raise ValueError('derived_span_incomplete')
        observations=dict(nodes=len(nodes),chunked_nodes=len(spans))
    observations['replacement_characters']=sum(t.count('\ufffd') for t in texts)
    return observations


def run(args):
    from validate_source_structure_audit import validate
    from audit_library_structure_selection import text_observations,coverage_gaps
    from consume_verified_structure_markers import repair
    from finalize_structure_prechunks import classify
    from structured_source_contract import describe
    code_files=list(Path(__file__).parent.glob('*.py'))+[Path(__file__).parents[2]/'src/retrieval/structural_surface.py']
    implementation={str(p):digest(p.read_bytes()) for p in code_files}
    rows=read_lines(args.ledger);out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    input_identity=dict(ledger_sha256=digest(Path(args.ledger).read_bytes()),
                       originals_summary_sha256=digest((Path(args.originals)/'summary.json').read_bytes()))
    new_summary=read_json(Path(args.originals)/'summary.json')
    new={r['document_id']:r for r in new_summary['rows']}
    backlog={r['document_id'] for r in rows if r['processing']['stage']=='parse_current_original'}
    assert len(new)==len(new_summary['rows']) and set(new)<=backlog
    assert new_summary['planned']==len(backlog)
    cache={};source_checks={};issues=[];results=[];counts=Counter();versions=Counter()
    for i,old in enumerate(rows):
        row=dict(old);bid=row['document_id'];artifact=row.get('current_parser_artifact')
        source=row.get('current_source')
        if source:
            source_key=(source.get('path'),source.get('database'),source.get('url'),source['current_sha256'])
            if source_key not in source_checks:
                check=dict(expected=source['current_sha256'])
                try:
                    if source.get('path'):
                        with Path(source['path']).open('rb') as stream:actual=file_digest(stream,'sha256').hexdigest()
                        size=Path(source['path']).stat().st_size
                    else:
                        with readonly(source['database']) as db:
                            data=db.execute('SELECT body_zlib FROM raw_captures WHERE url=? AND digest=?',
                                            (source['url'],source['current_sha256'])).fetchone()
                        if not data:raise ValueError('current_raw_capture_missing')
                        raw=zlib.decompress(data[0])
                        actual=digest(raw);size=len(raw);del raw
                    check.update(actual=actual,bytes=size)
                    check['pass']=check['actual']==check['expected']
                except Exception as exc:check.update(pass_=False,error=repr(exc))
                source_checks[source_key]=check
            row['source_recheck']=source_checks[source_key]
            if not row['source_recheck'].get('pass'):
                issues.append(dict(document_id=bid,kind='current_source_changed_or_unavailable',detail=row['source_recheck']))
                row['recognition_audit']={'state':'source_rebaseline_required'};results.append(row);counts['source_recheck_failures']+=1;continue
        if bid in backlog and bid not in new:
            issues.append(dict(document_id=bid,kind='current_original_not_yet_parsed',status='execution_gap'))
            row['recognition_audit']={'state':'pending_parse'};results.append(row);counts['pending_parse_bindings']+=1;continue
        if row['processing']['stage']=='derived_content_processing':
            derived_state='limited_derived_scope'
            if artifact:
                path=artifact.get('selected_artifact') or artifact.get('path')
                expected=artifact.get('selected_sha256') or artifact.get('sha256')
                try:
                    observations=audit_derived(read_artifact(path,expected),row.get('source_id'))
                    row['derived_observations']=observations
                    if observations['replacement_characters']:
                        issues.append(dict(document_id=bid,kind='encoding_loss_requires_original',count=observations['replacement_characters'],status='requires_original_comparison'))
                except Exception as exc:
                    issues.append(dict(document_id=bid,kind='derived_integrity_failure',error=repr(exc)))
                    derived_state='derived_audit_failed';counts['derived_audit_failures']+=1
            issues.append(dict(document_id=bid,kind='scoped_derived_content_not_full_original',status='scope_limit',source=row['url']))
            row['recognition_audit']={'state':derived_state};results.append(row);counts['limited_derived_bindings']+=1;continue
        if bid in new:
            receipt=new[bid]
            if receipt['status']=='failed':
                issues.append(dict(document_id=bid,kind='new_original_parse_failure',detail=receipt))
                row['recognition_audit']={'state':'parse_failure'};results.append(row);counts['parse_failures']+=1;continue
            lane=receipt['lane']
            if lane=='pdf':
                path=receipt['receipt'];artifact=dict(path=path,sha256=digest(Path(path).read_bytes()),lane='pdf',version=receipt.get('qualification_version','current-originals-r1'))
            else:artifact=dict(**receipt['document'],lane=lane,version=receipt.get('qualification_version','current-originals-r1'),receipt=receipt)
        if not artifact:
            issues.append(dict(document_id=bid,kind='scoped_derived_content_not_full_original',status='scope_limit',source=row['url']))
            row['recognition_audit']={'state':'limited_derived_scope'};results.append(row);counts['limited_derived_bindings']+=1;continue
        path=artifact.get('selected_artifact') or artifact.get('path')
        expected=artifact.get('selected_sha256') or artifact.get('sha256')
        lane=artifact.get('lane') or ('structured' if artifact.get('route')=='structured_json' else 'markdown')
        key=(path,expected)
        if key not in cache:
            record=dict(path=path,sha256=expected,lane=lane,issues=[],changes=[],observations={},quality_pass=False)
            try:
                d=read_artifact(path,expected)
                record['source_sha256']=d.get('source_sha256')
                if lane in ('sec','web','markdown'):
                    errors=validate(d)
                    if errors:raise ValueError('structure_contract:'+str(errors))
                    updated,changes=repair(d)
                    if changes:
                        errors=validate(updated)
                        if errors:raise ValueError('repaired_structure_contract:'+str(errors))
                        chunks=classify(updated)
                        previous_chunks=classify(d)
                        role_changes=[dict(block=new['block'],previous=old['role'],current=new['role'])
                                      for old,new in zip(previous_chunks['records'],chunks['records'],strict=True)
                                      if old['role']!=new['role']]
                        marker_blocks={c['block'] for c in changes}
                        if any(r['role']!='retained_structure' for r in chunks['records'] if r['block'] in marker_blocks):
                            raise ValueError('proven_marker_still_in_prose')
                        folder=out/'adapted'/digest(path.encode());folder.mkdir(parents=True)
                        packed=gzip.compress(json.dumps(updated,ensure_ascii=False).encode(),compresslevel=3,mtime=0)
                        target=folder/'document.json.gz';target.write_bytes(packed)
                        chunk_data=gzip.compress(json.dumps(chunks,ensure_ascii=False).encode(),compresslevel=3,mtime=0)
                        chunk_path=folder/'prechunks.json.gz';chunk_path.write_bytes(chunk_data)
                        record.update(path=str(target),sha256=digest(packed),changes=changes,parent_path=path,parent_sha256=expected,
                                      prechunk_role_changes=role_changes,prechunks=dict(path=str(chunk_path),sha256=digest(chunk_data)))
                        del previous_chunks,chunks
                    observations,found=text_observations(updated)
                    record.update(observations=dict(observations),issues=found+coverage_gaps(lane,observations))
                    for field in ('visible_unknown_levels','compatibility_only_chapters','location:unresolved','location:ambiguous'):
                        if observations[field]:
                            record['issues'].append(dict(kind='structure_evidence_review',field=field,count=observations[field],status='quality_evidence_gap'))
                    if updated.get('unmatched_explicit_headings'):
                        record['issues'].append(dict(kind='explicit_heading_coverage_review',count=len(updated['unmatched_explicit_headings']),status='requires_original_comparison'))
                    replacement_characters=sum(b.get('text','').count('\ufffd') for b in updated['blocks'])
                    if replacement_characters:record['issues'].append(dict(kind='encoding_loss_requires_original',count=replacement_characters,status='requires_original_comparison'))
                    # A zero-heading result is a review target, not a defect solely by count.
                    if not observations['chapters']:
                        record['issues'].append(dict(kind='zero_chapters_requires_source_review',status='quality_evidence_gap'))
                    del updated
                elif lane=='pdf':
                    pages=d['pages']
                    total=d.get('planned_pages',d.get('page_count'))
                    if [p['page'] for p in pages]!=list(range(1,total+1)):raise ValueError('pdf_page_scope')
                    for p in pages:
                        pagepath=p.get('path') or str(Path(path).parent/'pages'/f"{p['page']:05d}.json.gz")
                        page=read_artifact(pagepath,p.get('sha256') or p['artifact_sha256'])
                        if page['errors'] or page.get('table_layout_model_enabled') is not False:raise ValueError('pdf_page_contract')
                    record['observations']={'pages':total}
                    record['issues']=[dict(kind='pdf_layout_quality_not_independently_accepted',pages=total,status='quality_evidence_gap')]
                elif lane=='structured':
                    if 'structured_object' in d or 'structured_xml' in d:
                        contract=describe(d)
                    else:
                        if not d.get('source_object_conserved'):raise ValueError('record_conservation_not_proved')
                        contract=d
                    record['observations']={'record_kind:'+contract['kind']:1}
                    if contract['kind'].startswith('unknown_'):
                        record['issues'].append(dict(kind='unrecognized_record_schema',record_kind=contract['kind']))
                    record['issues'].append(dict(kind='record_consumer_semantics_not_accepted',record_kind=contract['kind'],status='consumer_contract_gap'))
                else:raise ValueError('unsupported_parser_lane:'+lane)
                record['state']='engineering_checked_quality_pending'
                del d;gc.collect()
            except Exception as exc:
                record.update(state='audit_failed',error=repr(exc))
                record['issues'].append(dict(kind='engineering_audit_failure',error=repr(exc)))
            cache[key]=record
            counts['unique_artifacts']+=1
            counts['repaired_artifacts']+=bool(record['changes']);counts['repaired_markers']+=len(record['changes'])
            counts['reclassified_prechunks']+=len(record.get('prechunk_role_changes',[]))
            counts['audit_failed_artifacts']+=record['state']=='audit_failed'
        record=cache[key]
        if source and record.get('source_sha256') and record['source_sha256']!=source['current_sha256']:
            issues.append(dict(document_id=bid,kind='parser_source_identity_mismatch',actual=record['source_sha256'],expected=source['current_sha256']))
            row['recognition_audit']={'state':'source_rebaseline_required'};results.append(row);counts['source_recheck_failures']+=1;continue
        row['current_parser_artifact']=dict(path=record['path'],sha256=record['sha256'],lane=lane,
            version='whole-library-recognition-review-20261103' if record['changes'] else artifact.get('version','recorded_receipt_version'),quality_pass=False)
        if record.get('prechunks'):row['current_parser_artifact']['prechunks']=record['prechunks']
        row['recognition_audit']=dict(state=record['state'],observations=record['observations'],marker_repairs=record['changes'])
        row['processing'].update(stage='continue_structure_quality',current_parser_artifact=row['current_parser_artifact'],state=record['state'])
        for issue in record['issues']:issues.append(dict(document_id=bid,source_sha256=row.get('current_source',{}).get('current_sha256') if row.get('current_source') else None,lane=lane,**issue))
        results.append(row);counts['audited_bindings']+=1;versions[row['current_parser_artifact']['version']]+=1
        if (i+1)%100==0:print(json.dumps({'bindings':i+1,'unique_artifacts':len(cache),'failures':counts['audit_failed_artifacts']}),flush=True)
    assert len(results)==len(rows)==len({r['document_id'] for r in results})
    assert all(digest(Path(p).read_bytes())==value for p,value in implementation.items()),'implementation_changed_during_audit'
    assert input_identity['ledger_sha256']==digest(Path(args.ledger).read_bytes()),'ledger_changed_during_audit'
    assert input_identity['originals_summary_sha256']==digest((Path(args.originals)/'summary.json').read_bytes()),'receipts_changed_during_audit'
    (out/'identity.json').write_text(json.dumps(dict(inputs=input_identity,implementation=implementation),indent=2),encoding='utf8')
    for name,values in [('library-bindings.jsonl',results),('issues.jsonl',issues),('artifact-audits.jsonl',list(cache.values())),('source-rechecks.jsonl',list(source_checks.values()))]:
        (out/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in values),encoding='utf8')
    summary=dict(total_bindings=len(results),counts=dict(counts),issue_counts=dict(Counter(r['kind'] for r in issues)),
        unique_artifact_issue_counts=dict(Counter(i['kind'] for r in cache.values() for i in r['issues'])),
        versions=dict(versions),quality_pass=False,single_version_full_quality_pass=False,provider_calls=0,
        full_current_original_execution_complete=len(new)==len(backlog) and all(r['status']!='failed' for r in new.values()),
        source_rechecks=len(source_checks),source_rechecks_pass=all(r.get('pass') for r in source_checks.values()),
        ledger_sha256=digest(Path(args.ledger).read_bytes()),new_originals_summary_sha256=digest((Path(args.originals)/'summary.json').read_bytes()))
    summary['lane_bindings']=dict(Counter((r.get('current_parser_artifact') or {}).get('lane','limited_or_pending') for r in results))
    summary['unique_artifact_observations']=dict(sum((Counter(r['observations']) for r in cache.values()),Counter()))
    summary['issue_binding_counts']={kind:len({r['document_id'] for r in issues if r['kind']==kind}) for kind in summary['issue_counts']}
    summary['engineering_pass']=not any(counts[k] for k in ('pending_parse_bindings','parse_failures','audit_failed_artifacts','source_recheck_failures','derived_audit_failures'))
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('ledger','originals','output'):p.add_argument('--'+name,required=True)
    run(p.parse_args())
