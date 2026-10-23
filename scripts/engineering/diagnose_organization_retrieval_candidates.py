"""Offline frozen-corpus candidate diagnosis; never a live authorization test.

Reads immutable published artifacts and successful query receipts. No services,
provider calls, rank-cache writes, original-DB restore, or generated answers.
The standalone matrix option permits a verified retained copy without copying
it into another release. Inputs, known labels and scope are preserved in output.
"""
import argparse
import gc
from hashlib import file_digest, sha256
import json
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import numpy as np
import psutil

from retrieval.published_lexical_index import scores_from_identities
from retrieval.rank_fusion import reciprocal_rank_fusion
from retrieval.source_hybrid import CachedRetrieval
from retrieval.text import tokenize
from scripts.data_retrieval.replay_cached_library_scenarios import ReadOnlyReceipts
from scripts.engineering.organization_recall_evaluation import bind_labels, summarize, validate_questions
from scripts.engineering.qualify_retrieval_recall import ranking_metrics
from sec_agent.research_foundation.organization_graph_index import candidates
from sec_agent.research_foundation.organization_hybrid_retrieval import vector
from sec_agent.research_foundation.organization_vector_math import cosine_scores
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from tests.integration.source_intake_diagnostics import SourceBundles


def digest(path):
    with path.open('rb') as handle:
        return file_digest(handle, 'sha256').hexdigest()


def frozen_cosine_scores(path, positions, query, count):
    """Do not retain mapped corpus pages between diagnostic requests.

    cosine_scores returns its own small array and keeps no matrix views. The
    local mapping therefore becomes unreachable when this call returns; the
    next request's collection/guard runs before another mapping is opened.
    """
    matrix = np.load(path, mmap_mode='r', allow_pickle=False)
    if matrix.shape != (count, 1024) or matrix.dtype != np.float32:
        raise ValueError('offline_matrix_shape_mismatch')
    return cosine_scores(matrix, positions, query)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('intake', 'dataset', 'index-directory', 'matrix', 'publication-checkpoint', 'query-cache', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--split', choices=('development', 'heldout', 'all'), required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False, parents=True)
    memory = []
    def save(name, value):
        (args.output/(name+'.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    def guard(phase):
        gc.collect()
        available = psutil.virtual_memory().available
        memory.append({'phase': phase, 'available_bytes': available, 'rss_bytes': psutil.Process().memory_info().rss})
        save('memory', memory)
        if available < 800 * 2**20:
            raise RuntimeError('offline_memory_guard')
    report = {'scope': 'offline full frozen corpus; no current Java grant or service query',
              'provider_calls': 0, 'status': 'preflight', 'samples': [], 'S2_passed': False}
    save('result', report)
    try:
        guard('start')
        dataset = json.loads(args.dataset.read_text(encoding='utf8'))
        if args.split == 'all' and dataset['evaluation_role'] != 'historical_regression':
            raise ValueError('independent_evaluation_requires_one_explicit_split')
        intake = json.loads((args.intake/'result.json').read_text(encoding='utf8'))
        if intake['status'] != 'verified' or dataset['library_sha256'] != intake['library_sha256']:
            raise ValueError('offline_source_snapshot_mismatch')
        bundles = SourceBundles((r['source_id'], args.intake/r['directory']/'source.json') for r in intake['sources'])
        validate_questions(dataset, bundles)
        rows = [r for r in dataset['questions'] if args.split == 'all' or r['split'] == args.split]
        if not rows:
            raise ValueError('empty_evaluation_split')
        directory = args.index_directory
        index = json.loads((directory/'index.json').read_text(encoding='utf8'))
        if (index['provenance']['source_intake_sha256'] != digest(args.intake/'result.json')
                or index['model'] != intake['source_index']['embedding_model'] or index['dimensions'] != 1024
                or len(index['records']) != sum(r['chunks'] for r in intake['sources'])):
            raise ValueError('offline_index_scope_mismatch')
        files = {args.matrix: index['matrix_sha256']}
        for name, key in (('lexical.sqlite', 'lexical_index'), ('navigation.sqlite', 'navigation_index'), ('graph.sqlite', 'graph_index')):
            files[directory/name] = index[key]['sha256']
            if any((directory/(name+suffix)).exists() for suffix in ('-wal', '-journal')):
                raise ValueError('offline_index_unsealed')
        for path, expected in files.items():
            if digest(path) != expected:
                raise ValueError('offline_index_integrity_failure')
        publication = json.loads((args.publication_checkpoint/'manifest.json').read_text(encoding='utf8'))['publication']
        if set(publication['resources']) != set(bundles):
            raise ValueError('offline_publication_scope_mismatch')
        # Historical identity reconstruction, NOT a current permission grant.
        cutoff = {r['as_of'] for r in rows}
        if len(cutoff) != 1:
            raise ValueError('offline_batch_requires_one_research_cutoff')
        manifest = {'research_as_of': next(iter(cutoff)), 'inputs': [
            {'resource_id': g['id'], 'ref': g['binding']['ref']} for g in publication['grants'].values()]}
        labels = bind_labels(rows, manifest, publication['resources'], index)
        records = index['records']
        if len({r['document_id'] for r in records}) != len(bundles):
            raise ValueError('offline_index_document_scope_mismatch')
        candidate_rows = [dict(node_id=r['node_id'], parent_document_id=r['document_id'],
            content_sha256=r['content_sha256']) for r in records] if any(r.get('entity_id') for r in rows) else None
        positions = [r['vector_index'] for r in records]
        if sorted(positions) != list(range(len(records))):
            raise ValueError('offline_matrix_positions_mismatch')
        del publication, manifest
        namespace = sha256(json.dumps(['index-query.v1', 'public-recall-qualification',
            intake['source_index']['matrix_sha256'], index['model'], 1024], separators=(',', ':')).encode()).hexdigest()
        report.update(status='running', evaluation_role=dataset['evaluation_role'], split=args.split,
            candidate_sources=len(bundles), candidate_chunks=len(records), expected_questions=len(rows),
            dataset_sha256=digest(args.dataset), index_sha256=digest(directory/'index.json'),
            matrix_sha256=index['matrix_sha256'], source_intake_sha256=digest(args.intake/'result.json'),
            limits='Known evidence only; candidate ranks, not tool-return/readback or online latency/capacity')
        save('result', report)
        with ReadOnlyReceipts(args.query_cache) as cache:
            client = CachedRetrieval(cache, SimpleNamespace(embedding_model=index['model'], rerank_model='qwen3-rerank'), namespace)
            for row in rows:
                guard('before:'+row['id'])
                sample = {k: row[k] for k in ('id', 'family', 'split')}
                start = perf_counter()
                try:
                    saved = cache.get(client.key('embedding', [row['query']]))
                    if not saved or saved['status'] != 'completed' or saved['result']['model'] != index['model']:
                        raise ValueError('offline_successful_query_receipt_required')
                    query = vector(saved['result']['values'][0], 1024)
                    scores, overlap, _ = scores_from_identities(directory/'lexical.sqlite',
                        ((r['node_id'], r['content_sha256'], r['lexical_input_sha256']) for r in records), tokenize(row['query']))
                    lexical_positions = sorted(overlap, key=lambda i: (-float(scores[i]), records[i]['node_id']))
                    lexical = [records[i]['node_id'] for i in lexical_positions[:12]]
                    scores = frozen_cosine_scores(args.matrix, positions, query, len(records))
                    dense = [records[i]['node_id'] for i in sorted(range(len(records)),
                        key=lambda i: (-float(scores[i]), records[i]['node_id']))[:24]]
                    ranked = {'dense_candidates': dense, 'lexical_candidates': lexical,
                              'fused_candidates': reciprocal_rank_fusion([dense, lexical])}
                    if row.get('entity_id'):
                        request = SourceDocumentRequest(source_space='organization', operation='search',
                            query=row['query'], entity_id=row['entity_id'], limit=20)
                        graph, evidence = candidates(directory/'graph.sqlite', candidate_rows, request, row['as_of'],
                                                     [candidate_rows[i] for i in lexical_positions])
                        ranked.update(graph_candidates=graph, graph_fused_candidates=reciprocal_rank_fusion([dense, lexical, graph]))
                        sample['graph_evidence'] = evidence
                    sample.update(status='completed', gold=labels[row['id']], rankings=ranked,
                        metrics={k: ranking_metrics(v, labels[row['id']]) for k, v in ranked.items()})
                    del scores, overlap, lexical_positions
                except Exception as exc:
                    sample.update(status='failed', error_type=type(exc).__name__)
                    raise
                finally:
                    sample['offline_elapsed_seconds'] = perf_counter()-start
                    report['samples'].append(sample)
                    save('result', report)
                if len(report['samples']) % 10 == 0:
                    print(json.dumps({'completed': len(report['samples']), 'expected': len(rows)}), flush=True)
        for path, expected in files.items():
            if digest(path) != expected:
                raise ValueError('offline_index_changed_during_evaluation')
        report.update(status='completed', summary=summarize(report['samples'], [r['id'] for r in rows]))
        save('result', report)
        guard('finished')
        print(json.dumps({'status': report['status'], 'questions': len(rows), 'families': report['summary']['families']}))
    except Exception as exc:
        report.update(status='failed', error_type=type(exc).__name__)
        save('result', report)
        raise


if __name__ == '__main__':
    main()
