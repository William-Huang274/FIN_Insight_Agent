"""Replay explicitly reviewed source spans against stored graph assertions.

The supplied expectations are independent annotations, not generated from edges.
This audit never extracts, inserts, embeds, or promotes a relationship.
"""
import argparse
import json
from pathlib import Path

from sec_agent.research_foundation.research_library import open_library


def contains(actual, expected):
    if isinstance(expected,dict):
        return isinstance(actual,dict) and all(k in actual and contains(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):
        return isinstance(actual,list) and all(any(contains(a,e) for a in actual) for e in expected)
    return actual==expected


def audit(library, annotations):
    if annotations['library_sha256']!=library.manifest['sha256']:
        raise ValueError('annotation_library_version_mismatch')
    outcomes=[];reviewed=[]
    for sample in annotations['samples']:
        parent=library._query('SELECT * FROM passages WHERE id=? AND source_id=?',
                             (sample['parent_id'],sample['source_id']))
        if not parent or parent[0]['body'][sample['start']:sample['end']]!=sample['quote']:
            raise ValueError('annotation_source_span_mismatch:'+sample['id'])
        allowed=list(dict.fromkeys([sample['source_id'],*sample.get('reviewed_equivalent_sources',[])]))
        rows=library._query('SELECT * FROM edges WHERE source_id IN ('+','.join('?' for _ in allowed)+')',allowed)
        for row in rows:row['qualifiers']=json.loads(row['qualifiers'])
        for expected in sample['expected_edges']:
            identities=[r for r in rows if r['subject']==expected['subject'] and r['object']==expected['object']
                        and r['predicate'] in expected['predicates'] and r['status']!='needs_semantic_review']
            complete=[r for r in identities if (not expected.get('statuses') or r['status'] in expected['statuses'])
                      and contains(r['qualifiers'],expected.get('qualifiers',{}))]
            outcomes.append({'sample_id':sample['id'],'expectation_id':expected['id'],
                'matched_edge_ids':[r['id'] for r in complete],
                'identity_edge_ids':[r['id'] for r in identities],
                'state':'matched' if complete else 'qualifier_or_status_gap' if identities else 'not_in_reviewed_graph',
                'source_span':{k:sample[k] for k in ('source_id','parent_id','start','end')}})
        by_id={r['id']:r for r in rows}
        for judgement in sample.get('reviewed_edges',[]):
            if judgement['edge_id'] not in by_id or type(judgement['supported']) is not bool:
                raise ValueError('invalid_edge_adjudication:'+sample['id'])
            reviewed.append({'sample_id':sample['id'],**judgement})
    found=sum(r['state']=='matched' for r in outcomes)
    return {'library_sha256':library.manifest['sha256'],'paid_calls':0,'source_samples':len(annotations['samples']),
            'expected_relations':len(outcomes),'matched_relations':found,
            'sample_recall':found/len(outcomes) if outcomes else None,
            'adjudicated_edges':len(reviewed),'sample_precision':sum(r['supported'] for r in reviewed)/len(reviewed) if reviewed else None,
            'scope':'Only supplied reviewed spans and explicitly adjudicated edges; not corpus recall or answer accuracy.',
            'outcomes':outcomes,'edge_adjudications':reviewed}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--annotations',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit(open_library(args.library),json.loads(args.annotations.read_text(encoding='utf8')))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'outcomes','edge_adjudications'}},ensure_ascii=False))


if __name__=='__main__':main()
