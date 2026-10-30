"""Validate all frozen structural artifacts, without claiming semantic accuracy."""
import argparse
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path


def validate(document):
    problems=[]; sources={r['id']:r for r in document.get('source_containers',[])}
    if len(sources)!=len(document.get('source_containers',[])):problems.append('duplicate_source_identity')
    for row in sources.values():
        for key in ('parent_id','table_id'):
            if row.get(key) and row[key] not in sources:problems.append('unknown_source_'+key)
        seen={row['id']};parent=row.get('parent_id')
        while parent in sources:
            if parent in seen:problems.append('source_parent_cycle');break
            seen.add(parent);parent=sources[parent].get('parent_id')
        if sha256(row['text'].encode()).hexdigest()!=row['text_sha256']:problems.append('source_text_digest')
    chapters={n['id']:n for n in document.get('chapter_tree',[])}
    if len(chapters)!=len(document.get('chapter_tree',[])):problems.append('duplicate_chapter_identity')
    for node in chapters.values():
        if node.get('parent_id') and node['parent_id'] not in chapters:problems.append('unknown_chapter_parent')
        if node.get('source_container_id') and node['source_container_id'] not in sources:problems.append('unknown_chapter_source')
        seen={node['id']};parent=node.get('parent_id')
        while parent in chapters:
            if parent in seen:problems.append('chapter_cycle');break
            seen.add(parent);parent=chapters[parent].get('parent_id')
    slices={};table_chunks=Counter()
    for chunk in document['pre_chunks']:
        b=chunk['block']
        if b<0 or b>=len(document['blocks']):problems.append('unknown_chunk_block');continue
        if chunk['kind']=='prose':slices.setdefault(b,[]).append((chunk['start'],chunk['end']))
        else:table_chunks[b]+=1
        block=document['blocks'][b]
        if chunk.get('chapter_ids',[])!=block.get('chapter_ids',[]):problems.append('chunk_chapter_disagreement')
    for i,block in enumerate(document['blocks']):
        sid=block.get('source_container_id')
        if sid and sid not in sources:problems.append('unknown_block_source')
        if sid and block.get('source_location_status')!='unique_complete_container':problems.append('unproved_source_selection')
        for candidate in block.get('source_container_candidates',[]):
            if candidate not in sources:problems.append('unknown_candidate_source')
        for cid in block.get('chapter_ids',[])+block.get('embedded_chapter_ids',[]):
            if cid not in chapters:problems.append('unknown_block_chapter')
        if block['kind']=='heading':continue
        if block['kind']=='table':
            if table_chunks[i]!=1:problems.append('table_chunk_cardinality')
            continue
        end=0
        for start,stop in slices.get(i,[]):
            if start!=end or stop<start or stop>len(block['text']):problems.append('prose_span_gap_overlap')
            end=stop
        if end!=len(block['text']):problems.append('prose_not_conserved')
    return dict(Counter(problems))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    manifest=json.loads(a.manifest.read_bytes());totals=Counter();findings=[];roles=Counter();locations=Counter()
    for job in manifest['jobs']:
        receipt=a.audit/'receipts'/f"{job['id']}.json";path=a.audit/'documents'/f"{job['id']}.json.gz"
        if not receipt.exists():findings.append({'id':job['id'],'error':'missing_receipt'});continue
        r=json.loads(receipt.read_bytes())
        if r['status']!='inspected':findings.append({'id':job['id'],'error':r.get('detail','execution_failed')});continue
        raw=path.read_bytes()
        if sha256(raw).hexdigest()!=r['artifact_sha256']:findings.append({'id':job['id'],'error':'artifact_digest_mismatch'});continue
        d=json.loads(gzip.decompress(raw));errors=validate(d)
        if errors:findings.append({'id':job['id'],'errors':errors})
        totals['validated_originals']+=1;totals['source_bindings']+=len(job['bindings'])
        totals['containers']+=len(d.get('source_containers',[]));totals['chapters']+=len(d.get('chapter_tree',[]))
        totals['verified_web_titles']+=d.get('document_title',{}).get('status')=='verified_original_heading'
        totals['repeated_heading_occurrences']+=sum(bool(b.get('chapter_occurrence_of')) for b in d['blocks'])
        roles.update(r['role'] for r in d.get('source_containers',[]))
        locations.update(b.get('source_location_status','not_html') for b in d['blocks'])
    result={'totals':dict(totals),'role_counts':dict(roles),'location_counts':dict(locations),
            'findings':findings,'all_frozen_originals_validated':not findings and totals['validated_originals']==len(manifest['jobs']),
            'structural_accuracy_claim':False,'provider_calls':0}
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='findings'},ensure_ascii=False))
    return 0 if result['all_frozen_originals_validated'] else 1


if __name__=='__main__':raise SystemExit(main())
