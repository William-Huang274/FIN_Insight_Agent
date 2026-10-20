"""Source-first, frozen known-evidence evaluation; embedding only, no retries.

Dataset, qrels, query cache and results are local artifacts outside Git. Labels
are not assumed exhaustive. Paraphrases are reported separately from families.
"""
import argparse
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import time

from retrieval.library_vectors import ready_index, dense_search
from retrieval.query_embeddings import QueryEmbeddingSource
from retrieval.qwen_api import QwenRetrieval
from retrieval.rank_fusion import reciprocal_rank_fusion
from sec_agent.research_foundation.research_library import ResearchLibrary


def ranking_metrics(ranked, relevant, ks=(5, 10, 20, 40)):
    relevant = set(relevant)
    if not relevant:
        raise ValueError('positive_qrels_required')
    ranks = [i for i, identifier in enumerate(dict.fromkeys(ranked), 1) if identifier in relevant]
    return {**{f'known_recall@{k}': sum(i <= k for i in ranks)/len(relevant) for k in ks},
            **{f'known_hit@{k}': float(any(i <= k for i in ranks)) for k in ks},
            **{f'all_known_hit@{k}': float(sum(i <= k for i in ranks) == len(relevant)) for k in ks},
            'mrr@40': 1/min(ranks) if ranks and min(ranks) <= 40 else 0.}


def rrf(channels, limit=40):
    return reciprocal_rank_fusion(channels, limit=limit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('dataset', 'library', 'index', 'output'):
        parser.add_argument('--'+option, required=True, type=Path)
    parser.add_argument('--split', required=True, choices=['development', 'heldout'])
    parser.add_argument('--scope', choices=['corpus', 'selected_document'], default='corpus')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    raw = args.dataset.read_bytes()
    dataset = json.loads(raw)
    rows = [r for r in dataset['questions'] if r['split'] == args.split]
    assert rows and len(rows) <= 200
    assert len({r['id'] for r in rows}) == len(rows)
    assert all(0 < len(r['query'].encode()) <= 8192 for r in rows)
    library = ResearchLibrary(args.library, retrieval_environment={})
    assert library.manifest['sha256'] == dataset['library_sha256']
    index, _, _ = ready_index(args.index, dataset['library_sha256'])
    # Validate frozen labels against actual originals before any provider call.
    for row in rows:
        for evidence in row['evidence']:
            found = library.chunks_by_ids([evidence['chunk_id']])
            assert len(found) == 1
            chunk = found[0]
            assert chunk['source_id'] == evidence['source_id']
            assert sha256(chunk['body'].encode()).hexdigest() == evidence['body_sha256']
            assert evidence['quote'] in chunk['body']
        if args.scope == 'selected_document':
            # Supplied by the scenario, never inferred from ranked candidates.
            assert row.get('selected_document_ids') or row.get('selected_document_id')
    args.output.mkdir(parents=True, exist_ok=True)
    basis = {'purpose': 'Frozen source-first known-evidence retrieval evaluation',
        'input_scale': {'queries': len(rows), 'utf8_bytes': sum(len(r['query'].encode()) for r in rows)},
        'required_output': 'One 1024-dimensional query vector and provider receipt per unique query',
        'quality_risk': 'Incomplete qrels and correlated paraphrases; no financial answer generation',
        'reasoning_profile': 'Embedding only; no generation or rerank',
        'limits': {'max_requests': len(rows), 'concurrency': 1, 'sdk_retries': 0, 'timeout_seconds': 45},
        'stop_behavior': 'Stop at first failure, retain failed/unknown receipt; never retry that query automatically',
        'dataset_sha256': sha256(raw).hexdigest(), 'index': index, 'split': args.split,
        'retrieval_scope': args.scope,
        'fusion_policy': 'organization-cosine-bm25-rrf.v1: dense24 + lexical12, k=60; public corpus lexical channel is SQLite FTS5'}
    prefix = args.output/(args.split if args.scope == 'corpus' else args.split+'-'+args.scope)
    prefix.with_suffix('.TokenBudgetBasis.json').write_text(json.dumps(basis, indent=2), encoding='utf8')
    if not args.execute:
        print(json.dumps(basis))
        return
    samples = []
    def persist():
        prefix.with_suffix('.samples.json').write_text(json.dumps(samples, indent=2), encoding='utf8')
    with closing(QwenRetrieval(os.environ['QWEN_API_KEY'],
                              embedding_model=index['embedding_model'], timeout=45)) as api:
        source = QueryEmbeddingSource(args.output/'query-cache', api, model=index['embedding_model'])
        for row in rows:
            sample = {'id': row['id'], 'family': row['family'], 'language': row['language'],
                      'topic': row['topic'], 'source_id': row['evidence'][0]['source_id']}
            started = time.perf_counter()
            try:
                vector, receipt = source.embed(row['query'], scope='public-recall-qualification',
                    index_digest=index['matrix_sha256'], model=index['embedding_model'], dimensions=1024)
                sample['embedding_ms'] = (time.perf_counter()-started)*1000
                sample['receipt'] = receipt
                eligible = {s['id'] for s in library.catalog(row['as_of']) if s['eligible']}
                selected = (row.get('selected_document_ids') or [row['selected_document_id']]) if args.scope == 'selected_document' else []
                if selected:
                    eligible &= set(selected)
                assert all(e['source_id'] in eligible for e in row['evidence'])
                started = time.perf_counter()
                lexical = [c['id'] for c in library.search(row['query'].split(), row['as_of'],
                                                          source_ids=selected, limit=40)]
                sample['lexical_ms'] = (time.perf_counter()-started)*1000
                started = time.perf_counter()
                dense = dense_search(args.index, index['library_sha256'], vector, eligible, k=40)
                sample['dense_ms'] = (time.perf_counter()-started)*1000
                sample['rankings'] = {'lexical': lexical, 'dense': dense, 'rrf': rrf([dense[:24], lexical[:12]])}
                gold = [e['chunk_id'] for e in row['evidence']]
                sample['metrics'] = {name: ranking_metrics(ids, gold) for name, ids in sample['rankings'].items()}
                sample['status'] = 'completed'
            except Exception as exc:
                sample.update(status='failed', error_type=type(exc).__name__)
                samples.append(sample)
                persist()
                raise
            samples.append(sample)
            persist()
            if len(samples) % 10 == 0:
                print(json.dumps({'split': args.split, 'completed': len(samples), 'total': len(rows)}), flush=True)
    summary = {'dataset_sha256': basis['dataset_sha256'], 'split': args.split, 'retrieval_scope': args.scope,
        'questions': len(samples), 'families': len({r['family'] for r in samples}),
        'sources': len({e['source_id'] for r in rows for e in r['evidence']}),
        'paid_calls': sum(r['receipt']['provider_calls'] for r in samples),
        'newly_reported_total_tokens': sum(r['receipt']['newly_reported_usage'].get('total_tokens', 0) for r in samples),
        'metrics': {channel: {metric: sum(r['metrics'][channel][metric] for r in samples)/len(samples)
            for metric in samples[0]['metrics'][channel]} for channel in ('lexical', 'dense', 'rrf')},
        'limits': 'Known labelled evidence only. Correlated paraphrases are not independent questions. Public corpus; not authorization evaluation.'}
    prefix.with_suffix('.summary.json').write_text(json.dumps(summary, indent=2), encoding='utf8')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
