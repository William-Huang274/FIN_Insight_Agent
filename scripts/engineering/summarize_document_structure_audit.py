"""Describe full-scope structure findings without calling execution accuracy."""
import argparse
from collections import Counter,defaultdict
import gzip
from hashlib import sha256
import json
from pathlib import Path
import re


def validate_chunks(document):
    issues=[];chunks=defaultdict(list)
    for c in document['pre_chunks']:chunks[c['block']].append(c)
    for i,b in enumerate(document['blocks']):
        if b['kind'] in {'heading','table'}:continue
        cursor=0
        for c in chunks[i]:
            if c['kind']!='prose' or c['start']!=cursor or not c['start']<=c['end']<=len(b['text']):
                issues.append({'kind':'prechunk_gap_or_overlap','block':i});break
            cursor=c['end']
        if cursor!=len(b['text']):issues.append({'kind':'prechunk_not_full_block','block':i})
    return issues


def summarize(manifest,directory,output):
    frozen=json.loads(manifest.read_bytes());rows=[];issues=Counter();routes=Counter();families=defaultdict(Counter)
    for job in frozen['jobs']:
        receipt=directory/'receipts'/f"{job['id']}.json"
        row={'id':job['id'],'title':job['title'],'url':job['url'],'bindings':job['bindings']}
        if not receipt.exists():row['status']='pending';rows.append(row);continue
        r=json.loads(receipt.read_bytes());row.update(r)
        if r['status']!='inspected':rows.append(row);continue
        path=directory/'documents'/f"{job['id']}.json.gz"
        if sha256(path.read_bytes()).hexdigest()!=r['artifact_sha256']:raise ValueError('audit_artifact_changed')
        with gzip.open(path,'rt',encoding='utf8') as f:d=json.load(f)
        own=validate_chunks(d);section=d.get('parser_sections',{})
        row.update(sections=len(section),section_methods=dict(Counter(s['method'] for s in section.values())),
                   form_resolution=d.get('form_resolution'),prechunk_conservation_issues=list(own),
                   heading_examples=d['outline'][:12])
        if section and any(s['end']<=s['start'] for s in section.values()):
            own.append({'kind':'section_offsets_not_usable_as_original_text_coordinates'})
        part=None
        for h in d['outline']:
            text=' '.join(h['title'].split()).upper()
            if re.match(r'^PART\s+[IVX]+\b',text):part=h
            elif part and re.match(r'ITEM\s+\d',text) and h['level'] and part['level'] and h['level']<=part['level']:
                own.append({'kind':'item_heading_not_nested_below_preceding_part','block':h['block']})
        row['additional_diagnostic_issues']=own
        for p in d['issues']+own:issues[p['kind']]+=1
        routes[d['route']]+=1
        row['structural_pass_claim']=False;rows.append(row)
    by_id={r['id']:r for r in rows}
    job_for_binding={b:j['id'] for j in frozen['jobs'] for b in j['bindings']}
    for s in frozen['sources']:
        id=job_for_binding.get(s['document_id']);status=by_id[id]['status'] if id else 'original_unresolved'
        families[s.get('provisional_family','unknown')][status]+=1
    result={'source_bindings':len(frozen['sources']),'unique_originals':len(rows),
            'diagnostic_implementation_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
            'manifest_sha256':sha256(manifest.read_bytes()).hexdigest(),
            'status':dict(Counter(r['status'] for r in rows)),'routes':dict(routes),
            'family_binding_status':{k:dict(v) for k,v in families.items()},
            'issue_occurrences_not_gold_errors':dict(issues),'documents':rows,
            'complete_execution':not any(r['status']=='pending' for r in rows),
            'all_structures_correct':False,'provider_calls':0}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'documents','family_binding_status'}},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['manifest','directory','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();summarize(a.manifest,a.directory,a.output)
