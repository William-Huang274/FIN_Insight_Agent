"""Frozen public-corpus replay before channel truncation; zero provider calls."""
import argparse
import gc
from hashlib import sha256, file_digest
import json
from pathlib import Path
import sqlite3
import zlib
import numpy as np
import psutil
from retrieval.organization_search_needs import compile_needs, lexical_candidates
from retrieval.published_lexical_index import PublishedLexicalStatistics
from retrieval.candidate_pipeline import fuse_channels, expand_population
from retrieval.evidence_scope import plan_scope, select_scoped
from sec_agent.research_foundation.organization_query_plan import plan_query, select_planned
from sec_agent.research_foundation.organization_hybrid_retrieval import vector
from scripts.engineering.diagnose_organization_retrieval_candidates import frozen_cosine_scores


def run(index_path,metadata_path,scope_path,queries_path,output):
    raw=index_path.read_bytes();index=json.loads(raw);index_hash=sha256(raw).hexdigest();del raw
    records=index['records']; directory=index_path.parent
    metadata=json.loads(metadata_path.read_bytes());scopes={}
    from retrieval.filing_document_identity import with_document_issuer_aliases
    metadata=with_document_issuer_aliases(metadata)
    for line in scope_path.read_text(encoding='utf8').splitlines():
        s=json.loads(line);scopes[s['node_id']]=s
    queries=json.loads(queries_path.read_bytes())['questions']
    if set(r['document_id'] for r in records)-metadata.keys():raise ValueError('trace_missing_catalog')
    with (directory/'vectors.npy').open('rb') as stream:
        if file_digest(stream,'sha256').hexdigest()!=index['matrix_sha256']:raise ValueError('trace_changed_matrix')
    # Verify immutable published navigation before restoring the same original
    # coordinate adjacency used by the real service. Never infer neighbors
    # from chunk IDs or omit this candidate stage in offline quality tests.
    from contextlib import closing
    from retrieval.source_window_candidates import adjacent_nodes
    expected={r['node_id']:r for r in records};locations=[]
    with closing(sqlite3.connect((directory/'navigation.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.execute('PRAGMA cache_size=-2048')
        for node, packed in db.execute('SELECT node_id,payload FROM nodes'):
            raw=zlib.decompress(packed)
            if node not in expected or sha256(raw).hexdigest()!=expected[node]['navigation_sha256']:
                raise ValueError('trace_changed_navigation')
            row=json.loads(raw);origin=row['original_source'];document=row['parent_document_id']
            start=origin.get('source_char_start',origin.get('char_start'))
            end=origin.get('source_char_end',origin.get('char_end'))
            space=origin.get('original_node_id') if 'source_char_start' not in origin else document
            if type(start) is int and type(end) is int and space and 0<=start<end:
                locations.append((space,start,end,node))
    neighbors=adjacent_nodes(locations)
    del locations, expected
    output.mkdir(parents=True,exist_ok=False)
    inputs={str(p):sha256(p.read_bytes()).hexdigest() for p in (metadata_path,scope_path,queries_path)}
    root=Path(__file__).resolve().parents[2]
    code={str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest()
          for folder in ('src/retrieval','src/sec_agent/research_foundation','scripts/engineering')
          for p in (root/folder).glob('*.py')}
    summary={'status':'running','role':'exposed_regression_channel_diagnostic','provider_calls':0,
        'input_sha256':inputs,'code_sha256':code,
        'live_authorization_tested':False,'index_sha256':index_hash,'samples':[]}
    statistics=PublishedLexicalStatistics()
    for number,q in enumerate(queries,1):
        gc.collect()
        if psutil.virtual_memory().available<800*2**20:raise RuntimeError('trace_memory_guard')
        selected,plan=select_planned(metadata,plan_query(q['query'],metadata,policy='conservative.v5'))
        rows=[{**r,'parent_document_id':r['document_id'],
               'evidence_scopes':scopes.get(r['node_id'],{}).get('evidence_scopes',[]),
               'source_interval':scopes.get(r['node_id'],{}).get('source_interval'),
               'evidence_scope_complete':scopes.get(r['node_id'],{}).get('evidence_scope_complete',False)}
              for r in records if r['document_id'] in selected]
        wanted=plan_scope(q['query'],plan);scope_receipt=None
        if wanted:rows,scope_receipt=select_scoped(rows,wanted)
        needs=compile_needs(q['query'],plan)
        def trace_sink(need,route,samples):
            name=f'{q["id"]}.{need}.route-{route}.bm25.jsonl'
            path=output/name;count=0;digest=sha256()
            with path.open('xb') as stream:
                for sample in samples:
                    raw=(json.dumps(sample,ensure_ascii=False)+'\n').encode()
                    stream.write(raw);digest.update(raw);count+=1
            return {'file':name,'sha256':digest.hexdigest(),'count':count,'complete_matched_population':True}
        lexical,lanes=lexical_candidates(directory/'lexical.sqlite',rows,needs,metadata,
                                         population_cache=statistics,capture_trace=True,trace_sink=trace_sink)
        scores=frozen_cosine_scores(directory/'vectors.npy',[r['vector_index'] for r in rows],
            vector(q['vector'],index['dimensions']),len(records)) if rows else np.array([])
        entry,order,limits=fuse_channels(rows,scores,lexical,policy='needs_window.v4',lexical_policy=needs['policy'])
        dense=entry['dense'];union=entry['ordered']
        expanded,expansion=expand_population(union,dense,rows,neighbors,policy='needs_window.v4')
        # All dense scores, including the tail, are preserved outside the
        # tool response. Arrays align with the saved scope_ids order.
        np.savez_compressed(output/(q['id']+'.dense.npz'),scores=scores)
        result={'id':q['id'],'query':q['query'],'plan':plan,'evidence_scope':scope_receipt,
            'scope_ids':[r['node_id'] for r in rows],'dense_pre_quota':[
                {'node_id':rows[i]['node_id'],'rank':rank+1,'score':float(scores[i])}
                for rank,i in enumerate(order[:96])], 'lexical_routes':lanes,
            'dense_candidates':dense,'lexical_candidates':lexical[:limits['lexical']],
            'fused_candidates':union,'candidate_node_ids':expanded,'source_window':expansion,
            'limits':limits,'query_request_id':q['request_id'],
            'scope_chunks':len(rows),'source_count':len({r['document_id'] for r in rows})}
        (output/(q['id']+'.json')).write_text(json.dumps(result,ensure_ascii=False),encoding='utf8')
        summary['samples'].append({k:result[k] for k in ('id','scope_chunks','source_count')})
        (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'completed':number,'total':len(queries),'id':q['id'],'scope':len(rows)}),flush=True)
    summary['status']='completed'
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('index','metadata','scopes','queries','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();run(a.index,a.metadata,a.scopes,a.queries,a.output)
