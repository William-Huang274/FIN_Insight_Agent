"""Frozen retrieval acceptance gate. Synthetic tests validate scoring, not quality.

Counts independent families, preserves failed samples and separates candidate
coverage from visible evidence. Existing exposed questions cannot pass as a
new independent evaluation. A quality pass does not certify service capacity.
"""
from collections import defaultdict
from hashlib import sha256
import argparse
import json
from pathlib import Path
import random

SLICES=('numeric_unit','actual_guidance_period','deal_revision','multi_issuer',
        'relationship_evidence','multiple_evidence')


def macro(rows,field):
    families=defaultdict(list)
    for row in rows:families[row['family']].append(row[field])
    return sum(sum(v)/len(v) for v in families.values())/len(families) if families else 0.


def interval(rows,field):
    groups=defaultdict(list)
    for row in rows:groups[row['family']].append(row[field])
    values=[sum(v)/len(v) for v in groups.values()]
    if not values:return [0.,0.]
    rng=random.Random(260026)
    samples=sorted(sum(rng.choices(values,k=len(values)))/len(values) for _ in range(2000))
    return [samples[49],samples[1949]]


def score(candidates,returned,groups):
    if not groups or any(not group for group in groups):raise ValueError('required_evidence_groups_missing')
    positions={n:i for i,n in enumerate(returned[:10],1)}
    covered=[bool(set(g)&set(candidates)) for g in groups]
    ranks=[min((positions[n] for n in group if n in positions),default=0) for group in groups]
    visible=sum(bool(r) for r in ranks)/len(groups)
    return {'candidate_recall48':sum(covered)/len(groups),'recall10':visible,
            'mrr10':1/min(r for r in ranks if r) if any(ranks) else 0.,
            'all_required10':float(all(ranks))}


def evaluate(dataset,report,*,dataset_digest):
    failures=[]
    def require(value,reason):
        if not value and reason not in failures:failures.append(reason)
    questions=dataset.get('questions',[])
    positive=[q for q in questions if q.get('answerability','answerable')=='answerable']
    negative=[q for q in questions if q.get('answerability') in ('absent_in_frozen_scope','clarification_required')]
    families={q['family'] for q in positive}
    dev={q['family'] for q in positive if q['split']=='development'}
    final={q['family'] for q in positive if q['split']=='heldout'}
    require(dataset.get('evaluation_role')=='independent_source_first','independent_dataset_required')
    require(dataset.get('freeze',{}).get('status')=='frozen','dataset_not_frozen')
    require(dataset.get('freeze',{}).get('prior_results_exposed') is False,'independent_status_unconfirmed')
    require(report.get('dataset_sha256')==dataset_digest,'dataset_digest_mismatch')
    require(bool(dataset.get('index_digest')) and report.get('index_digest')==dataset.get('index_digest'),
            'frozen_index_mismatch')
    require(bool(dataset.get('freeze',{}).get('ranking_policy_sha256')) and
            report.get('ranking_policy_sha256')==dataset.get('freeze',{}).get('ranking_policy_sha256'),
            'frozen_ranking_policy_mismatch')
    require(len(positive)>=120 and len(families)>=60 and len(dev)>=20 and len(final)>=40,'positive_scope_incomplete')
    require(len(negative)>=20,'no_answer_or_ambiguity_scope_incomplete')
    require(len({e for q in positive for e in q.get('business_entities',[])})>=20,'entity_coverage_incomplete')
    require(not dev&final,'family_crosses_split')
    require(len({q['id'] for q in questions})==len(questions),'duplicate_question')
    groups=defaultdict(set)
    for q in positive:
        require(q.get('label_review',{}).get('status')=='reviewed','label_review_incomplete')
        require(q.get('topic') in SLICES,'unrecognized_business_slice')
        require(bool(q.get('source_groups')),'source_equivalence_group_missing')
        for source in q.get('source_groups',[]):groups[source].add(q['split'])
    require(all(len(s)==1 for s in groups.values()),'equivalent_source_crosses_split')
    for family in families:
        require({'en','zh'}<={q.get('language') for q in positive if q['family']==family},'family_language_coverage_incomplete')
    samples=report.get('samples',[])
    require(len({s['id'] for s in samples})==len(samples),'duplicate_result')
    by_id={s['id']:s for s in samples}
    expected=[q for q in questions if q['split']=='heldout']
    require(set(by_id)=={q['id'] for q in expected},'final_result_population_mismatch')
    require(report.get('status')=='completed','execution_not_completed')
    scored=[]; abstentions=[]
    for q in expected:
        sample=by_id.get(q['id'],{})
        complete=sample.get('status')=='completed'
        require(complete,'failed_or_missing_sample')
        require(sample.get('unauthorized_items')==0,'authorization_not_verified_clean')
        require(sample.get('invalid_identity_items')==0,'issuer_period_revision_not_verified_clean')
        if q in negative:
            require(q.get('scope_review',{}).get('status')=='reviewed','negative_scope_review_incomplete')
            wanted='clarify' if q['answerability']=='clarification_required' else 'insufficient_evidence'
            abstentions.append(complete and sample.get('decision')==wanted)
            continue
        rankings=sample.get('rankings',{})
        candidates=rankings.get('candidate_union',[]); returned=rankings.get('returned',[])
        valid=(len(candidates)<=48 and len(candidates)==len(set(candidates))
               and len(returned)==len(set(returned)) and set(returned)<=set(candidates))
        require(valid,'candidate_or_returned_identity_invalid')
        if complete and valid:
            require(sample.get('gold_groups')==q.get('expected_groups'),'result_labels_differ_from_frozen_labels')
            try:metrics=score(candidates,returned,q.get('expected_groups',[]))
            except ValueError:
                require(False,'required_evidence_groups_missing');metrics={k:0. for k in ('candidate_recall48','recall10','mrr10','all_required10')}
        else:metrics={k:0. for k in ('candidate_recall48','recall10','mrr10','all_required10')}
        scored.append({'id':q['id'],'family':q['family'],'language':q['language'],'topic':q['topic'],**metrics})
    measures={key:{'family_macro':macro(scored,key),'family_bootstrap_95ci':interval(scored,key)}
              for key in ('candidate_recall48','recall10','mrr10','all_required10')}
    for key,target in [('candidate_recall48',.95),('recall10',.90),('mrr10',.75)]:
        require(measures[key]['family_macro']>=target,'below_target_'+key)
    slices={}
    for axis,values in [('language',('en','zh')),('topic',SLICES)]:
        for value in values:
            rows=[s for s in scored if s[axis]==value]
            slices[value]={'questions':len(rows),'families':len({r['family'] for r in rows}),'recall10':macro(rows,'recall10')}
            require(bool(rows) and slices[value]['recall10']>=.8,'slice_below_target_'+value)
    require(bool(abstentions) and all(abstentions),'no_answer_or_ambiguity_gate_not_passed')
    return {'quality_gate_passed':not failures,'S2_passed':False,'failures':failures,'metrics':measures,
        'slices':slices,'samples':scored,'negative_correct':sum(abstentions),'negative_total':len(abstentions),
        'scope':{'questions':len(positive),'families':len(families),'development_families':len(dev),
                 'heldout_families':len(final),'evaluated_positive_questions':len(scored)},
        'limits':'Known required evidence only; service, performance and Agent research benefit are separate gates.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('dataset','report','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args(); raw=args.dataset.read_bytes()
    result=evaluate(json.loads(raw),json.loads(args.report.read_text(encoding='utf8')),dataset_digest=sha256(raw).hexdigest())
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:result[k] for k in ('quality_gate_passed','failures','scope')}))


if __name__=='__main__':main()
