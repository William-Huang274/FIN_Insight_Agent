"""Verify native XML conservation separately from original-page extraction quality."""
import argparse
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path
from lxml import etree
from validate_source_structure_audit import validate


def audit(directory):
    summary=json.loads((directory/'summary.json').read_bytes()); counts=Counter(); findings=[]
    for row in summary['rows']:
        sid=row['source_sha256']
        if row['status']!='adapted_requires_quality_review':
            findings.append(dict(id=sid,problem=row['status']));continue
        receipt=row['receipt'];native_raw=(Path(row['capture_directory'])/'native.json.gz').read_bytes()
        packed=(directory/'adapted'/sid/'document.json.gz').read_bytes()
        if sha256(native_raw).hexdigest()!=receipt['native_sha256'] or sha256(packed).hexdigest()!=receipt['artifact_sha256']:
            findings.append(dict(id=sid,problem='artifact_digest_mismatch'));continue
        if sha256(Path(receipt['parent_fin_path']).read_bytes()).hexdigest()!=receipt['parent_fin_sha256']:
            findings.append(dict(id=sid,problem='prior_repaired_baseline_changed'));continue
        native=json.loads(gzip.decompress(native_raw))['native']['document']
        doc=json.loads(gzip.decompress(packed));xml=native['body']['$xml']
        root=etree.fromstring(xml.encode(),etree.XMLParser(resolve_entities=False,no_network=True))
        if doc['native_body_xml']!=xml or ''.join(b['text'] for b in doc['blocks'])!=''.join(root.itertext()):
            findings.append(dict(id=sid,problem='native_body_not_conserved'))
        if doc['native_comments']!=native.get('commentsbody'):
            findings.append(dict(id=sid,problem='native_comments_not_retained'))
        errors=validate(doc)
        if errors:findings.append(dict(id=sid,problem='structural_contract',details=errors))
        counts['adapted_originals']+=1
        counts['native_headings']+=sum(b['kind']=='heading' for b in doc['blocks'])
        counts['native_tables']+=sum(b['kind']=='table' for b in doc['blocks'])
    complete=summary['processed_rows']==summary['planned_originals']
    return dict(planned_originals=summary['planned_originals'],processed_rows=summary['processed_rows'],
                all_plan_rows_accounted=complete,counts=dict(counts),findings=findings,
                engineering_integrity_pass=complete and not findings,
                original_body_coverage_verified=False,structural_accuracy_pass=False,provider_calls=0)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=audit(a.directory)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))
