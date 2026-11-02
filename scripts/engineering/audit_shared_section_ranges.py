"""Classify every shared SEC source range without guessing unique ownership."""
import argparse
from collections import Counter
import gc
import gzip
import json
from pathlib import Path

from qualify_source_heading_units import digest,save
from source_heading_units import geometry,number
from source_part_hierarchy import body_source
from native_document_capture import read_capture


def classify(group,sections,headings):
    absent=[key for key in group['sections'] if key not in sections]
    expected={key:str(sections.get(key,{}).get('item') or '').replace('.','').casefold() for key in group['sections']}
    numbers=[h['item'] for h in headings]
    missing=[key for key,n in expected.items() if not n or n not in numbers]
    repeated=[n for n in set(numbers) if numbers.count(n)>1]
    if absent:
        kind='toc_identity_absent_from_native_sections'
    elif len(set(expected.values()))<len(expected):
        kind='same_item_multiple_native_identities'
    elif missing:
        kind='native_items_not_all_evidenced_in_shared_range'
    elif repeated:
        kind='repeated_item_containers_need_disambiguation'
    else:
        kind='distinct_item_containers_possible_subranges'
    return dict(group,classification=kind,expected_items=expected,missing_native_sections=absent,missing_item_sections=missing,
                repeated_items=sorted(repeated),original_heading_candidates=headings,
                disposition='requires_original_boundary_or_reference_review',canonical_section=None)


def run(root,captures,output):
    summary=json.loads((root/'summary.json').read_bytes())
    if not summary['engineering_pass']:raise ValueError('incomplete_sec_scope')
    output.mkdir(exist_ok=False,parents=True);records=[];counts=Counter();checked=0
    here=Path(__file__).resolve().parent
    files=[here/n for n in ('audit_shared_section_ranges.py','source_heading_units.py','source_part_hierarchy.py','native_document_capture.py')]
    identity=dict(input_summary_sha256=digest(root/'summary.json'),code={str(p):digest(p) for p in files})
    save(output/'identity.json',identity)
    with (output/'ranges.jsonl').open('w',encoding='utf8') as out:
        for entry in summary['rows']:
            oid=entry['id'];receipt=root/oid/'receipt.json';r=json.loads(receipt.read_bytes())
            path=Path(r['artifact_path'])
            if digest(path)!=r['artifact_sha256']:raise ValueError('input_artifact_changed')
            d=json.loads(gzip.decompress(path.read_bytes()));groups=d.get('shared_native_range_groups',[])
            checked+=1
            if groups:
                capdir=captures/oid;cr=json.loads((capdir/'receipt.json').read_bytes())
                c=read_capture(capdir/'native.json.gz',expected_sha256=cr['native_sha256'],expected_source_sha256=oid)
                ranges,spans=geometry(c['native'],d['source_containers'])
                for group in groups:
                    bounds=tuple(group['original_range'])
                    if any(ranges.get(k)!=bounds for k in group['sections']):raise ValueError('shared_range_original_changed')
                    a,z=bounds
                    candidates=[dict(source_id=s['id'],text=s['text'],item=number(s['text']),role=s['role'],order=spans[s['id']][0])
                        for s in d['source_containers'] if body_source(s) and s['id'] in spans
                        and number(s['text']) and len(s['text'])<=240 and a<=spans[s['id']][0] and spans[s['id']][1]<z]
                    result=classify(group,d['parser_sections'],sorted(candidates,key=lambda r:r['order']))
                    result.update(original_id=oid,input_sha256=digest(path),capture_sha256=cr['native_sha256'])
                    out.write(json.dumps(result,ensure_ascii=False)+'\n');counts[result['classification']]+=1
                del c
            records.append(dict(id=oid,artifact_sha256=r['artifact_sha256'],shared_ranges=len(groups)))
            del d;gc.collect()
            if checked%100==0:print(json.dumps(dict(checked=checked,ranges=sum(counts.values()))),flush=True)
    save(output/'summary.json',dict(checked=checked,planned=len(summary['rows']),rows=records,counts=dict(counts),
        ranges=sum(counts.values()),input_summary_sha256=digest(root/'summary.json'),
        engineering_pass=checked==len(summary['rows']) and all(digest(p)==identity['code'][str(p)] for p in files),quality_pass=False,provider_calls=0,
        note='Candidate containers are original text observations, not independently accepted section boundaries.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('root','captures','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.root,a.captures,a.output)
