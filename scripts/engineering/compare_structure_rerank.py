"""Planned public-development ablation, fixed candidates and no automatic retry."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import time

from scripts.engineering.organization_rerank_comparison import prepare
from scripts.engineering.qualify_retrieval_recall import ranking_metrics
from retrieval.library_source_bundle import expand_source_bundle
from retrieval.source_structure import source_structure
from retrieval.scoped_reranking import ScopedReranker

POLICY='verified-structure-scoring-view.v1'


def scoring_view(candidate, original, structure, text, *, context_scope='all'):
    if (candidate['content']!=original['body'] or candidate['content_sha256']!=original['digest']
            or candidate['embedding_input_sha256']!=original['embedding_input_sha256']):
        raise ValueError('structure_experiment_original_mismatch')
    if context_scope not in ('all', 'detached-footnotes'):
        raise ValueError('structure_experiment_unknown_context_scope')
    # Select from verified original relationships, never length, gold labels or
    # relevance scores. A note needs context when its marked table is not fully
    # contained in the candidate; ordinary prose remains byte-for-byte unchanged.
    selected_structure = structure
    if context_scope == 'detached-footnotes':
        start, end = original.get('source_char_start'), original.get('source_char_end')
        notes = [note for note in structure['footnotes']
                 if type(start) is int and type(end) is int
                 and not (start <= note['table']['source_char_start']
                          and end >= note['table']['source_char_end'])]
        selected_structure = {**structure, 'footnotes': notes, 'tables': []}
        if not notes:
            selected_structure['section'] = None
    structure = selected_structure
    additions=[]; windows=[]
    if structure['section']:
        additions.append('Original document section: '+structure['section']['heading'])
    if structure['tables']:
        additions.append('This fragment overlaps an original table; its fragment boundaries need not contain the complete table.')
    budget=4000; seen=set()
    for note in structure['footnotes']:
        additions.append('Original numbered post-table note ('+note['marker']+'); its marked table context follows when available.')
        span=note['table']; key=(span['source_char_start'],span['source_char_end'])
        if key in seen:continue
        seen.add(key)
        table=text[key[0]:key[1]]
        if sha256(table.encode()).hexdigest()!=span['content_sha256']:
            raise ValueError('structure_experiment_table_mismatch')
        excerpt=table[:budget]; budget-=len(excerpt)
        windows.append({'table':span,'excerpt_start':key[0],'excerpt_end':key[0]+len(excerpt),
                        'excerpt_sha256':sha256(excerpt.encode()).hexdigest(),'complete_table':len(excerpt)==len(table)})
        if excerpt:
            additions.append(('Complete marked table:\n' if len(excerpt)==len(table) else 'Partial marked table context (not the complete table):\n')+excerpt)
        else:additions.append('Further marked table context omitted by the declared scoring-view budget; original remains readable.')
    view=dict(candidate)
    if additions:
        view['embedding_context']=candidate.get('embedding_context','')+'\n'+'\n'.join(additions)
    # This is a scoring-only copy: original vector input and source are untouched.
    document=(view.get('embedding_context','')+'\n'+view['content']).strip()
    if len(document.encode())>32768:raise ValueError('structure_experiment_document_budget')
    return view,{'policy':POLICY,'context_scope':context_scope,'changed':bool(additions),'section':structure['section'],
                 'table_windows':windows,'document_sha256':sha256(document.encode()).hexdigest(),
                 'document_utf8_bytes':len(document.encode()),'body_sha256':candidate['content_sha256']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('result','dataset','index','intake','output','baseline','receipt-cache'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--context-scope',choices=('all','detached-footnotes'),default='all')
    p.add_argument('--execute',action='store_true');args=p.parse_args()
    jobs,plan=prepare(args.result,args.dataset,args.index)
    baseline=json.loads(args.baseline.read_bytes())
    if baseline['status']!='completed':raise ValueError('structure_baseline_incomplete')
    previous_plan_raw=(args.baseline.parent/'plan.json').read_bytes()
    if (sha256(previous_plan_raw).hexdigest()!=baseline['plan_sha256']
            or json.loads(previous_plan_raw)['result_sha256']!=plan['result_sha256']):
        raise ValueError('structure_baseline_candidate_plan_mismatch')
    previous={s['id']:s for s in baseline['samples']}
    intake_raw=(args.intake/'result.json').read_bytes();intake=json.loads(intake_raw)
    sources={s['source_id']:s for s in intake['sources']}
    grouped={}
    for job in jobs:
        for row in job['candidates']:
            grouped.setdefault(row['original_source']['source_id'],{})[row['node_id']]=row
    views={};audits={};file_hashes={}
    for sid, candidates in grouped.items():
        spec=sources[sid];path=args.intake/spec['directory']/'source.json';raw=path.read_bytes()
        digest=sha256(raw).hexdigest()
        if digest!=spec['files']['source.json']:raise ValueError('structure_intake_file_changed')
        bundle=expand_source_bundle(json.loads(raw));structure=source_structure(bundle)
        chunks={c['id']:c for c in bundle['chunks']};file_hashes[sid]=digest
        for node,row in candidates.items():
            cid=row['original_source']['id']
            views[node],audits[node]=scoring_view(row,chunks[cid],structure[cid],bundle.get('text',''),
                                                context_scope=args.context_scope)
        del bundle,structure,chunks
    for job in jobs:
        if job['gold']!=previous[job['id']]['gold']:raise ValueError('structure_baseline_labels_changed')
        job['candidates']=[views[c['node_id']] for c in job['candidates']]
        if sum(audits[r['node_id']]['document_utf8_bytes'] for r in job['candidates'])>524288:
            raise ValueError('structure_experiment_request_budget')
    from retrieval import source_structure as structure_module
    implementations={str(path):sha256(path.read_bytes()).hexdigest() for path in
        (Path(__file__),Path(structure_module.__file__))}
    plan.update(experiment=POLICY,context_scope=args.context_scope,baseline_sha256=sha256(args.baseline.read_bytes()).hexdigest(),
        intake_sha256=sha256(intake_raw).hexdigest(),source_files=file_hashes,implementation_sha256=implementations,
        scoring_view={'context_max_characters_per_candidate':4000,'scope':'all40 development questions; same candidate IDs/order, full original bodies; explicit structure only',
            'partial_context_is_labeled':True,'original_embeddings_modified':False},
        scoring_inputs=audits)
    plan['TokenBudgetBasis'].update(purpose='Paired actual Qwen test of verified original section/table context versus cached original input',
        input_scale={'requests_max':len(jobs),'candidates':sum(len(j['candidates']) for j in jobs),
            'utf8_bytes':sum(audits[c['node_id']]['document_utf8_bytes'] for j in jobs for c in j['candidates'])},
        quality_risk='Exposed development set; context can improve or hurt ranking. No new answer/gold hints. Partial table excerpts are scoring context, not sufficient evidence.')
    args.output.mkdir(parents=True,exist_ok=True);planned=args.output/'plan.json'
    if planned.exists() and json.loads(planned.read_bytes())!=plan:raise ValueError('structure_plan_changed')
    planned.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(plan['TokenBudgetBasis'],ensure_ascii=False),flush=True)
    if not args.execute:return
    from retrieval.qwen_api import QwenRetrieval
    from retrieval.organization_search_needs import select_coverage
    key=os.environ.get('QWEN_API_KEY')
    if not key:raise ValueError('configured_qwen_key_unavailable')
    api=QwenRetrieval(key,embedding_model='qwen3.7-text-embedding')
    reranker=ScopedReranker(args.receipt_cache,api)
    report={'status':'running','S2_passed':False,'policy':POLICY,'samples':[],
        'plan_sha256':sha256(planned.read_bytes()).hexdigest()}
    try:
        for job in jobs:
            t=time.perf_counter()
            ranked,receipt=reranker.rank(job['query'],job['candidates'],scope='qualification:development-rerank',
                index_digest=plan['index_sha256'],check_access=lambda:None)
            needs=job['search_needs'];selected,coverage=select_coverage(ranked,needs['search_needs'],needs['lexical_needs'],job['source_metadata'])
            report['samples'].append({'id':job['id'],'family':job['family'],'gold':job['gold'],
                'seconds':time.perf_counter()-t,'receipt':receipt,'ranked_ids':[r['node_id'] for r in ranked],
                'selected_ids':[r['node_id'] for r in selected],'need_coverage':coverage,
                'reranked':ranking_metrics([r['node_id'] for r in ranked],job['gold']),
                'selected':ranking_metrics([r['node_id'] for r in selected],job['gold']),
                'baseline_reranked':previous[job['id']]['reranked'],'baseline_selected':previous[job['id']]['selected']})
            (args.output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            if len(report['samples'])%10==0:print(json.dumps({'completed':len(report['samples']),'expected':len(jobs)}),flush=True)
        if implementations!={path:sha256(Path(path).read_bytes()).hexdigest() for path in implementations}:
            raise ValueError('structure_experiment_implementation_changed')
        report['status']='completed'
    except Exception as error:
        report.update(status='failed',error_type=type(error).__name__,error=str(error));raise
    finally:
        api.close();(args.output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'status':report['status'],'provider_calls':sum(s['receipt']['provider_calls'] for s in report['samples'])}))


if __name__=='__main__':main()
