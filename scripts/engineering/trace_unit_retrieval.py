"""Replay the published unit ranker with full pre-quota channel score evidence.

Uses fixed query vectors, no provider calls. This isolates candidate selection;
it cannot replace live current-authorization and final-page qualification.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from retrieval.semantic_unit_index import rank,validate
from retrieval.organization_search_needs import compile_needs
from retrieval.evidence_scope import plan_scope,select_scoped
from retrieval.published_lexical_index import PublishedLexicalStatistics
from sec_agent.research_foundation.organization_query_plan import plan_query,select_planned


def run(index_path,overlay,metadata_path,scopes_path,queries_path,output):
    from sec_agent.research_foundation.organization_index_release import canonical_digest
    index=json.loads(index_path.read_bytes());published=json.loads((overlay/'overlay.json').read_bytes())
    if canonical_digest(index)!=published['snapshot_digest']:raise ValueError('unit_trace_original_snapshot_changed')
    allowed=set(published['parent_scope']);parents=[r for r in index['records'] if r['node_id'] in allowed]
    validate(overlay,published['descriptor'],parents,index['model'])
    metadata=json.loads(metadata_path.read_bytes());scopes={}
    with scopes_path.open(encoding='utf8') as stream:
        for line in stream:
            row=json.loads(line);scopes[row['node_id']]=row
    queries=json.loads(queries_path.read_bytes())['questions'];statistics=PublishedLexicalStatistics()
    output.mkdir(parents=True,exist_ok=False)
    summary={'status':'running','scope':'candidate_stage_exposed_regression','provider_calls':0,'samples':[],
        'inputs':{str(p):sha256(p.read_bytes()).hexdigest() for p in (index_path,overlay/'overlay.json',metadata_path,scopes_path,queries_path)}}
    for q in queries:
        documents,plan=select_planned(metadata,plan_query(q['query'],metadata,policy='conservative.v5'))
        # A narrower indexed diagnostic population must never silently exclude
        # newly selected documents after a planner correction.
        required={r['node_id'] for r in index['records'] if r['document_id'] in documents}
        if required-allowed:raise ValueError('unit_trace_selected_scope_not_fully_published')
        rows=[{**r,'parent_document_id':r['document_id'],
               'evidence_scopes':scopes.get(r['node_id'],{}).get('evidence_scopes',[]),
               'source_interval':scopes.get(r['node_id'],{}).get('source_interval'),
               'evidence_scope_complete':scopes.get(r['node_id'],{}).get('evidence_scope_complete',False)}
              for r in parents if r['document_id'] in documents]
        wanted=plan_scope(q['query'],plan);scope_receipt=None
        if wanted:rows,scope_receipt=select_scoped(rows,wanted)
        needs=compile_needs(q['query'],plan)
        def trace(need,route,samples):
            path=output/f'{q["id"]}.{need}.{route}.jsonl';digest=sha256();count=0
            with path.open('xb') as stream:
                for sample in samples:
                    raw=(json.dumps(sample,ensure_ascii=False)+'\n').encode();stream.write(raw);digest.update(raw);count+=1
            return {'file':path.name,'sha256':digest.hexdigest(),'count':count,'complete_population':True}
        candidates,receipt=rank(overlay,rows,q['vector'],needs,metadata,wanted,policy='needs_units.v1',
            population_cache=statistics,capture_trace=True,trace_sink=trace)
        receipt.pop('_eligible_parent_ids',None)
        result={'id':q['id'],'query':q['query'],'plan':plan,'needs':needs,'evidence_scope':scope_receipt,
            'channels':candidates,'receipt':receipt,'documents':sorted(documents),'parent_population':len(rows)}
        (output/f'{q["id"]}.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf8')
        summary['samples'].append({'id':q['id'],'parents':len(rows),'candidates':len(candidates['ordered'])})
        (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
        print(json.dumps({'completed':len(summary['samples']),'total':len(queries),'id':q['id']}),flush=True)
    summary['status']='completed';(output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('index','overlay','metadata','scopes','queries','output'):parser.add_argument('--'+key,type=Path,required=True)
    a=parser.parse_args();run(a.index,a.overlay,a.metadata,a.scopes,a.queries,a.output)
