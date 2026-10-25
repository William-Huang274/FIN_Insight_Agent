"""Replay successful development reranks without any provider calls or label edits."""
import argparse
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import zlib

from retrieval.evidence_ordering import order_evidence
from scripts.engineering.qualify_retrieval_recall import ranking_metrics


def compare(result_path, plan_path, dataset_path, index_path):
    raw=result_path.read_bytes(); result=json.loads(raw)
    plan_raw=plan_path.read_bytes(); plan=json.loads(plan_raw)
    data_raw=dataset_path.read_bytes(); dataset=json.loads(data_raw)
    index_raw=index_path.read_bytes(); index=json.loads(index_raw)
    if (result.get('status')!='completed' or result.get('evaluation_role')!='development_fixed_candidates'
        or result['plan_sha256']!=sha256(plan_raw).hexdigest()
        or plan['dataset_sha256']!=sha256(data_raw).hexdigest()
        or plan['index_sha256']!=sha256(index_raw).hexdigest()):
        raise ValueError('ordering_requires_completed_original_development_inputs')
    questions={q['id']:q for q in dataset['questions'] if q['split']=='development'}
    records={r['node_id']:r for r in index['records']}
    if {s['id'] for s in result['samples']} != set(questions):
        raise ValueError('ordering_complete_development_population_required')
    planned={(s['id'],s['channel']):s['candidate_ids'] for s in plan['samples']}
    samples=[]
    with closing(sqlite3.connect(index_path.parent.joinpath('navigation.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        for sample in result['samples']:
            ids=sample['ranked_ids']
            if len(ids)!=len(set(ids)) or set(ids)!=set(planned[(sample['id'],sample['channel'])]):
                raise ValueError('ordering_candidate_identity_changed')
            rows=[]
            for node in ids:
                raw_payload=zlib.decompress(db.execute('SELECT payload FROM nodes WHERE node_id=?',(node,)).fetchone()[0])
                if sha256(raw_payload).hexdigest()!=records[node]['navigation_sha256']:
                    raise ValueError('ordering_candidate_payload_changed')
                row=json.loads(raw_payload)
                if row['node_id']!=node or sha256(row['content'].encode()).hexdigest()!=records[node]['content_sha256']:
                    raise ValueError('ordering_candidate_body_changed')
                rows.append(row)
            ordered, receipt=order_evidence(questions[sample['id']]['query'],rows)
            samples.append({'id':sample['id'],'family':sample['family'],'channel':sample['channel'],
                'gold':sample['gold'],'original_ranked_ids':ids,'ranked_ids':[r['node_id'] for r in ordered],
                'receipt':receipt,'before':ranking_metrics(ids,sample['gold']),
                'after':ranking_metrics([r['node_id'] for r in ordered],sample['gold'])})
    metrics={key:{side:sum(s[side][key] for s in samples)/len(samples) for side in ('before','after')}
             for key in ('known_hit@10','known_recall@10','mrr@40')}
    return {'status':'completed','evaluation_role':'development_fixed_candidates','S2_passed':False,
        'provider_calls':0,'dataset_sha256':sha256(data_raw).hexdigest(),'result_sha256':sha256(raw).hexdigest(),
        'index_sha256':sha256(index_raw).hexdigest(),'metrics':metrics,'samples':samples,
        'limits':'Post-order experiment only; original strict anchors unchanged; no current authorization or heldout quality claim'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('result','plan','dataset','index','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('ordering_output_already_exists')
    result=compare(args.result,args.plan,args.dataset,args.index)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result['metrics']))


if __name__=='__main__':main()
