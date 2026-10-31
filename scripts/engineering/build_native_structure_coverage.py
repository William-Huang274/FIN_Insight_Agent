"""Account for native adaptation against every existing library binding.

Never promote candidate artifacts or remove missing originals from coverage.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


def coverage(bindings, results):
    by_id={r['source_sha256']:r for r in results['rows']}
    rows=[]
    for binding in bindings:
        row=dict(binding); result=by_id.get(row.get('original_id'))
        if not row.get('original_id'):
            state='original_unavailable_existing_representation_retained'
        elif result is None:
            state='native_adaptation_not_run'
        else:
            state=result['status']
            row['native_candidate_receipt']=result.get('receipt')
        row['native_adaptation_state']=state
        row['native_quality_pass']=False
        rows.append(row)
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bindings',type=Path,required=True)
    p.add_argument('--results',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    raw=a.bindings.read_bytes(); result_raw=a.results.read_bytes()
    bindings=[json.loads(l) for l in raw.decode('utf-8-sig').splitlines() if l.strip()]
    rows=coverage(bindings,json.loads(result_raw))
    (a.output/'bindings.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    report=dict(total_bindings=len(rows),unique_available_originals=len({r['original_id'] for r in rows if r.get('original_id')}),
                states=dict(Counter(r['native_adaptation_state'] for r in rows)),
                original_ledger_sha256=sha256(raw).hexdigest(),candidate_results_sha256=sha256(result_raw).hexdigest(),
                selected_product_artifacts_changed=False,full_library_quality_pass=False)
    (a.output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
