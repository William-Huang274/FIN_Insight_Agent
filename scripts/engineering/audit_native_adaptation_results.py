"""Audit native-to-FIN conservation over every row in a frozen qualification.

These are complete-scope engineering checks, not chapter precision/recall.
"""
import argparse
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path


def audit(directory):
    summary=json.loads((directory/'summary.json').read_bytes())
    counts=Counter(); findings=[]; families={}; fingerprints={}
    for row in summary['rows']:
        sid=row['source_sha256']; status=row['status']
        families.setdefault(row['family'],Counter())[status]+=1
        if status!='adapted_requires_quality_review':continue
        capture=Path(row.get('capture_directory',directory/'captures'/sid)); adapted=directory/'adapted'/sid
        receipt=json.loads((capture/'receipt.json').read_bytes()); record=row['receipt']
        native_raw=(capture/'native.json.gz').read_bytes(); output_raw=(adapted/'document.json.gz').read_bytes()
        if sha256(native_raw).hexdigest()!=receipt['native_sha256'] or sha256(output_raw).hexdigest()!=record['artifact_sha256']:
            findings.append(dict(id=sid,problem='artifact_digest_mismatch'));continue
        native=json.loads(gzip.decompress(native_raw)); document=json.loads(gzip.decompress(output_raw))
        for module,digest in native['loaded_parser_module_sha256'].items():
            if module in fingerprints and fingerprints[module]!=digest:
                findings.append(dict(id=sid,problem='mixed_parser_module_versions',module=module))
            fingerprints[module]=digest
        from validate_source_structure_audit import validate
        errors=validate(document)
        if errors:findings.append(dict(id=sid,problem='structural_contract',errors=errors))
        if row['route']=='edgartools':
            previous_raw=Path(record['parent_fin_path']).read_bytes()
            if sha256(previous_raw).hexdigest()!=record['parent_fin_sha256']:
                findings.append(dict(id=sid,problem='previous_artifact_digest_mismatch'));continue
            previous=json.loads(gzip.decompress(previous_raw))
            keys=['kind','text','rows','headers','footer','source_container_id','source_container_candidates',
                  'source_location_status','source_role','native_container_id','native_parent_id']
            if [{k:b.get(k) for k in keys} for b in previous['blocks']] != [{k:b.get(k) for k in keys} for b in document['blocks']]:
                findings.append(dict(id=sid,problem='existing_content_or_position_changed'))
            else:counts['sec_content_and_position_conserved']+=1
            if previous.get('source_containers')!=document.get('source_containers'):
                findings.append(dict(id=sid,problem='original_container_ledger_changed'))
            coverage=document['native_section_coverage']
            counts['native_sections']+=coverage['total_sections']
            counts['native_sections_with_bound_blocks']+=coverage['sections_with_bound_blocks']
            counts['native_bound_blocks']+=coverage['bound_blocks']
            counts['sec_total_blocks']+=coverage['total_blocks']
            counts['unscoped_heading_records']+=len(document.get('unscoped_chapter_tree',[]))
            counts['documents_using_prior_tree_without_native_scope']+=document.get('native_tree_status')=='existing_tree_retained_no_native_scope'
        elif row['route']=='markdown':
            text=''.join(b.get('raw_text',b['text']) for b in document['blocks'])
            if text!=native['native']['source_text']:
                findings.append(dict(id=sid,problem='markdown_original_not_conserved'))
            else:counts['markdown_source_partition_conserved']+=1
            counts['markdown_tables']+=sum(b['kind']=='table' for b in document['blocks'])
        counts['adapted_originals']+=1
    return dict(planned_originals=summary['planned_originals'],processed_rows=summary['processed_rows'],
                all_plan_rows_accounted=summary['processed_rows']==summary['planned_originals'],
                counts=dict(counts),findings=findings,families={k:dict(v) for k,v in families.items()},
                engineering_integrity_pass=not findings and summary['processed_rows']==summary['planned_originals']
                    and not any(s in summary['statuses'] for s in ('adaptation_failed','native_capture_failed')),
                structural_accuracy_pass=False,independent_holdout=False,
                chapter_precision=None,chapter_recall=None,provider_calls=0)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.directory)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
