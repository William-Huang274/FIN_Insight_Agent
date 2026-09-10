"""Original-source hybrid development qualification; no hidden/holdout labels."""
import argparse
import json
import os
from pathlib import Path
from retrieval.source_hybrid import prepare_source_index,rank_sources
from retrieval.qwen_api import QwenRetrieval
from sec_agent.research_foundation.source_document_navigation import navigate_source_nodes,SourceDocumentRequest


def main():
    p=argparse.ArgumentParser();p.add_argument('--nodes',type=Path,required=True);p.add_argument('--cache',required=True)
    p.add_argument('--queries',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--prepare',action='store_true');args=p.parse_args()
    if args.output.exists():raise ValueError('attempt_output_already_exists')
    from scripts.deployment.dell_report_workbench import configured_key
    api=QwenRetrieval(configured_key('QWEN_API_KEY'))
    data=json.loads(args.nodes.read_text(encoding='utf-8'));rows=data['nodes'];snapshot=data['snapshot']
    os.environ['FINSIGHT_SOURCE_HYBRID']='0'
    result={'qualification':'open development sample, not blind evaluation','snapshot':snapshot,'results':[]}
    try:
        if args.prepare:
            result['index']=prepare_source_index(rows,snapshot,args.cache,api)
            args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        if args.queries:
            for q in json.loads(args.queries.read_text(encoding='utf-8')):
                request=SourceDocumentRequest(operation='search',query=q['query'],limit=20)
                lexical=navigate_source_nodes(rows,request,snapshot=snapshot)
                by_id={r['node_id']:r for r in rows}
                dense,receipt=rank_sources([r for r in rows if r['node_kind']!='section'],q['query'],snapshot,
                    [by_id[r['node_id']] for r in lexical.items],path=args.cache,api=api)
                gold=set(q['relevant_node_ids'])
                def scores(ids):
                    return {'recall_at_5':len(gold.intersection(ids[:5]))/len(gold),
                        'mrr_at_20':next((1/(i+1) for i,key in enumerate(ids[:20]) if key in gold),0),
                        'top5':ids[:5]}
                result['results'].append({'query':q['query'],'bm25':scores([r['node_id'] for r in lexical.items]),
                    'hybrid':scores([r['node_id'] for r in dense]),'receipt':receipt})
                args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='results'}))
    finally:api.close()


if __name__=='__main__':main()
