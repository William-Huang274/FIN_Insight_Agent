"""Verify complete PDF/record artifacts against frozen input identities."""
import argparse
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path

from structured_source_contract import describe


def audit(root, inventory, lane):
    rows=[r for r in map(json.loads,inventory.read_text(encoding='utf8').splitlines()) if r['lane']==lane]
    identity=json.loads((root/'identity.json').read_bytes())
    identity=identity.get('parent_identity',identity)
    if sha256(inventory.read_bytes()).hexdigest()!=identity['inventory_sha256']:raise ValueError('inventory_changed')
    final=json.loads((root/'final-audit.json').read_bytes())
    if not final['engineering_pass']:raise ValueError('batch_not_passed')
    summary=json.loads((root/'summary.json').read_bytes())
    expected={r['original_id'] for r in rows}
    actual=[r['id'] for r in summary['rows']]
    statuses={r['id']:r for r in summary['rows']}
    if len(actual)!=len(expected) or set(actual)!=expected:raise ValueError('scope_mismatch')
    counts=Counter();proofs=[];parser_versions=Counter()
    for row in rows:
        oid=row['original_id'];base=root/oid
        if lane=='pdf':
            from resume_pdf_native_qualification import verify_receipt
            if statuses[oid].get('receipt'):
                base=Path(statuses[oid]['receipt']).parent
                if base.name!=oid:raise ValueError('receipt_path_identity_mismatch')
            receipt=verify_receipt(base.parent,oid)
            if not receipt.get('parser_version'):raise ValueError('missing_parser_version')
            parser_versions[receipt['parser_version']]+=1
            counts['pages']+=receipt['planned_pages']
            for p in receipt['pages']:
                data=json.loads(gzip.decompress((base/'pages'/f"{p['page']:05d}.json.gz").read_bytes()))
                if data['page']!=p['page'] or data['errors'] or data.get('table_layout_model_enabled') is not False:
                    raise ValueError('page_contract_failure:'+oid)
            payload=base/'receipt.json'
        else:
            raw=Path(row['existing_baseline']).read_bytes()
            if sha256(raw).hexdigest()!=row['existing_baseline_sha256']:raise ValueError('parent_changed')
            expected_contract=describe(json.loads(gzip.decompress(raw)))
            expected_contract.update(source_sha256=oid,parent_sha256=sha256(raw).hexdigest(),source_object_conserved=True)
            payload=base/'records.json'
            if json.loads(payload.read_bytes())!=expected_contract:raise ValueError('record_contract_changed:'+oid)
            counts[expected_contract['kind']]+=1
        proofs.append(dict(id=oid,path=str(payload),sha256=sha256(payload.read_bytes()).hexdigest()))
    if len(parser_versions)>1:raise ValueError('mixed_pdf_parser_versions')
    return dict(planned=len(rows),verified=len(proofs),counts=dict(counts),parser_versions=dict(parser_versions),proofs=proofs,evidence_pass=True,quality_pass=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--lane',choices=['pdf','structured'],required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=audit(a.root,a.inventory,a.lane)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='proofs'}))
