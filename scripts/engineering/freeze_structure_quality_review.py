"""Freeze a screening sample without declaring parser quality or independent gold."""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def family(job, route):
    if route != 'edgartools':
        return route, 'parser_route'
    form = (job.get('form') or '').upper().removesuffix('/A')
    if form in {'10-K','10-Q','8-K'}:
        return 'SEC_'+form, 'catalog_form'
    if form:
        return 'SEC_other', 'catalog_other_form'
    found = re.findall(r'(?<![A-Z0-9])(10-K|10-Q|8-K)(?:/A)?(?![A-Z0-9])',job.get('title','').upper())
    if len(set(found)) == 1:
        return 'SEC_'+found[0], 'title_hint_requires_review'
    return 'SEC_other', 'unresolved_sec_form'


def select(records, seed, per_stratum):
    groups=defaultdict(list)
    for row in records:
        groups[(row['family'],row['diagnostic_stratum'])].append(row)
    chosen=[]; selected=set(); strata=[]
    for key, group in sorted(groups.items()):
        ranked=sorted(group,key=lambda r:(sha256((seed+'|'+r['original_id']).encode()).hexdigest(),r['original_id']))
        picks=ranked[:per_stratum]
        strata.append({'family':key[0],'diagnostic_stratum':key[1],'population':len(group),'selected':len(picks)})
        for row in picks:
            chosen.append({**row,'selection':'seeded_stratified_screening',
                           'stratum_population':len(group),'stratum_sample_size':len(picks)})
            selected.add(row['original_id'])
    for kind in sorted({r['family'] for r in records}):
        remaining=[r for r in records if r['family']==kind and r['original_id'] not in selected]
        if remaining:
            row=sorted(remaining,key=lambda r:(-r['catalog_text_length_hint'],r['original_id']))[0]
            chosen.append({**row,'selection':'directed_catalog_length_hint','population_inference_allowed':False})
            selected.add(row['original_id'])
    return chosen,strata


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','ledger','protocol','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--seed',required=True)
    p.add_argument('--per-stratum',type=int,default=4)
    a=p.parse_args()
    if a.per_stratum != 4:raise ValueError('protocol_v1_requires_four_per_stratum')
    m=json.loads(a.manifest.read_bytes())
    rows=[json.loads(s) for s in a.ledger.read_text(encoding='utf8').splitlines()]
    sources={s['document_id']:s for s in m['sources']}; by_binding={r['document_id']:r for r in rows}
    if len(rows)!=m['source_bindings'] or len(by_binding)!=len(rows) or set(by_binding)!=set(sources):
        raise ValueError('binding_scope_changed')
    records=[]; bound=set()
    for job in m['jobs']:
        bindings=[by_binding[b] for b in job['bindings']]
        first=bindings[0]
        if any(r.get('original_id')!=job['id'] or r['artifact_sha256']!=first['artifact_sha256']
               or r['artifact_path']!=first['artifact_path'] for r in bindings):
            raise ValueError('conflicting_original_binding')
        if bound.intersection(job['bindings']):raise ValueError('duplicate_binding')
        bound.update(job['bindings'])
        kind,basis=family(job,first['route'])
        records.append({'original_id':job['id'],'title':job['title'],'url':job['url'],
                        'family':kind,'family_basis':basis,'route':first['route'],
                        'bindings':job['bindings'],'artifact_path':first['artifact_path'],
                        'artifact_sha256':first['artifact_sha256'],'issues':first.get('issues',{}),
                        'diagnostic_stratum':'flagged' if first.get('issues') else 'no_current_flags',
                        'catalog_text_length_hint':max(sources[b].get('text_length',0) or 0 for b in job['bindings']),
                        'original_locator':{'database':m['database'],'capture_digest':job['id']},
                        'review_state':'not_reviewed','quality_state':'insufficient_evidence',
                        'prior_exposure':'included_in_full_library_diagnostics_and_repairs',
                        'independent_holdout':False,'company_and_year_verification':'pending_original_review'})
    if any(r.get('original_id') for b,r in by_binding.items() if b not in bound):
        raise ValueError('unmapped_original_binding')
    selected,strata=select(records,a.seed,a.per_stratum)
    identity={'schema_version':'document_structure_quality_review_v1','purpose':'screening_not_type_qualification',
              'manifest_sha256':digest(a.manifest),'ledger_sha256':digest(a.ledger),
              'protocol_sha256':digest(a.protocol),'script_sha256':digest(Path(__file__)),
              'seed':a.seed,'per_stratum':a.per_stratum,'provider_calls':0}
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'identity.json').write_text(json.dumps(identity,indent=2),encoding='utf8')
    for name,items in [('originals',records),('review-plan',selected),('unresolved-bindings',
        [{'document_id':b,'title':r['title'],'quality_state':'insufficient_evidence',
          'reason':'original_unavailable_in_frozen_manifest'} for b,r in by_binding.items() if b not in bound])]:
        (a.output/(name+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in items),encoding='utf8')
    summary={'bindings':len(rows),'unique_originals':len(records),'unresolved_bindings':len(rows)-len(bound),
             'sample_documents':len(selected),'sample_selection':dict(Counter(r['selection'] for r in selected)),
             'sample_strata':dict(Counter(r['diagnostic_stratum'] for r in selected)),
             'sample_families':dict(Counter(r['family'] for r in selected)),
             'strata':strata,'reviews_completed':0,'quality_metrics':None,
             'independent_holdout':False,'plan_sha256':digest(a.output/'review-plan.jsonl')}
    (a.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k!='strata'},ensure_ascii=False))


if __name__=='__main__':main()
