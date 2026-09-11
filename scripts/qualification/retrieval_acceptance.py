"""Measured production BM25/vector/union-rerank on frozen scoped originals.

Labels are open, source-anchored development/validation, not a blind benchmark.
Returned candidates for an unanswerable question never count as an answer.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import time

from diskcache import Cache
from retrieval.source_hybrid import prepare_source_index, rank_sources, source_chunks
from retrieval.qwen_api import QwenRetrieval
from sec_agent.research_foundation.source_document_navigation import navigate_source_nodes, SourceDocumentRequest


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    data = json.loads(args.nodes.read_text(encoding='utf-8'))
    queries = json.loads(args.queries.read_text(encoding='utf-8'))
    rows, snapshot = data['nodes'], data['snapshot']
    assert len({r['node_id'] for r in rows}) == len(rows)
    queries = [q for q in queries if q['split'] == args.split]
    by_id = {r['node_id']: r for r in rows}
    assert 1 <= len(queries) <= 16
    assert all(set(q['relevant_node_ids']).issubset(by_id) for q in queries)
    chunks = source_chunks(rows)
    basis = {'purpose': 'Source retrieval acceptance, production adapters and fixed corpus',
        'input_scale': {'chunks': len(chunks), 'characters': sum(len(c['text']) for c in chunks), 'queries': len(queries)},
        'required_outputs': 'BM25, dense, union+Qwen rerank ranked source locators; exact repeat uses cache',
        'schema_burden': 'Provider vectors/rank indices; no generated report',
        'risk': 'A retrieved passage does not establish financial claim truth or answerability',
        'comparable_evidence': '207 HPE six-query open development qualification',
        'reasoning_profile': 'none; retrieval models only', 'retry': 'none; unknown calls not resent',
        'corpus_digest': sha256(args.nodes.read_bytes()).hexdigest(), 'query_digest': sha256(args.queries.read_bytes()).hexdigest(),
        'split': args.split, 'labels': 'Open source anchors; validation frozen before rankings, not blind',
        'price': 'Record tokens only; official price and free credit accounting evaluated separately'}
    (args.output/'basis.json').write_text(json.dumps(basis, ensure_ascii=False, indent=2), encoding='utf-8')
    if not args.execute:
        print('Prepared; zero provider calls.'); return
    if basis['input_scale']['characters'] > 1800000:
        raise ValueError('qualification_corpus_ceiling')
    from scripts.deployment.dell_report_workbench import configured_key
    api = QwenRetrieval(configured_key('QWEN_API_KEY'))
    os.environ['FINSIGHT_SOURCE_HYBRID'] = '0'
    result = {'basis': basis, 'results': []}
    def save():
        (args.output/'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        result['preparation'] = prepare_source_index(rows, snapshot, args.cache, api)
        save()
        for q in queries:
            started = time.perf_counter()
            lexical = navigate_source_nodes(rows, SourceDocumentRequest(operation='search', query=q['query'], limit=20), snapshot=snapshot)
            literal = [by_id[r['node_id']] for r in lexical.items]
            ranked, receipt = rank_sources(rows, q['query'], snapshot, literal, path=args.cache, api=api, diagnostics=True)
            gold = set(q['relevant_node_ids'])
            def score(ids):
                return {'top5': ids[:5], 'hit_at_5': bool(gold.intersection(ids[:5])) if gold else None,
                    'anchor_recall_at_5': len(gold.intersection(ids[:5]))/len(gold) if gold else None,
                    'mrr_at_20': next((1/(i+1) for i,key in enumerate(ids[:20]) if key in gold), 0) if gold else None}
            result['results'].append({'id': q['id'], 'query': q['query'], 'answerable': bool(gold),
                'bm25': score([r['node_id'] for r in literal]), 'dense': score(receipt['dense_node_ids']),
                'hybrid': score([r['node_id'] for r in ranked]), 'candidate_anchor_recall': len(gold.intersection(receipt['candidate_node_ids']))/len(gold) if gold else None,
                'receipt': receipt, 'seconds': time.perf_counter()-started})
            save()
            # Exactly one repeated production search: must make zero new calls.
            repeated, reuse = rank_sources(rows, q['query'], snapshot, literal, path=args.cache, api=api)
            assert reuse['calls'] == 0 and [r['node_id'] for r in repeated] == [r['node_id'] for r in ranked]
            result['results'][-1]['repeat_provider_calls'] = reuse['calls']; save()
            print(json.dumps({'query': q['id'], 'new_provider_calls': receipt['calls'], 'cache_repeat_calls': reuse['calls']}), flush=True)
        positive = [r for r in result['results'] if r['answerable']]
        result['summary'] = {arm: {metric: sum(r[arm][metric] for r in positive)/len(positive)
            for metric in ('hit_at_5', 'anchor_recall_at_5', 'mrr_at_20')} for arm in ('bm25','dense','hybrid')}
        result['unanswerable_queries'] = len(queries)-len(positive)
        result['negative_scope'] = 'Return is candidates only; no generation or assertion of non-disclosure. End-to-end abstention tested separately.'
        save()
    finally:
        api.close()


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('nodes','queries','output'): p.add_argument('--'+key, type=Path, required=True)
    p.add_argument('--cache', required=True)
    p.add_argument('--split', choices=['development','validation'], required=True)
    p.add_argument('--execute', action='store_true')
    run(p.parse_args())
