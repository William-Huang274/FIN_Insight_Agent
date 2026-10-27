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
import os
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import numpy as np
import psutil

from retrieval.published_lexical_index import scores_from_identities
from retrieval.rank_fusion import reciprocal_rank_fusion
from retrieval.candidate_policy import POLICIES, candidate_limits
from retrieval.source_hybrid import CachedRetrieval
from retrieval.text import tokenize
from scripts.data_retrieval.replay_cached_library_scenarios import ReadOnlyReceipts
from scripts.engineering.organization_recall_evaluation import bind_labels, summarize, validate_questions
from scripts.engineering.retrieval_evaluation_freeze import validate_heldout_freeze
from scripts.engineering.retrieval_label_review import validate_heldout_label_reviews
from scripts.engineering.qualify_retrieval_recall import ranking_metrics
from sec_agent.research_foundation.organization_graph_index import candidates
from sec_agent.research_foundation.organization_hybrid_retrieval import vector
from sec_agent.research_foundation.organization_vector_math import cosine_scores
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from sec_agent.research_foundation.organization_query_plan import plan_query, select_planned
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


def rank_scope(records, directory, matrix, total_count, query_vector, row, *, candidate_policy='balanced.v1', needs=None, metadata=None):
    """Use production score/fusion functions on an explicit, label-free scope."""
    ranked = {'dense_candidates': [], 'lexical_candidates': [], 'fused_candidates': []}
    evidence = []
    limits = candidate_limits(candidate_policy, has_graph=bool(row.get('entity_id')),
                              lexical_policy=(needs or {}).get('policy'))
    if row.get('entity_id'):
        ranked.update(graph_candidates=[], graph_fused_candidates=[])
    if not records:
        return ranked, evidence
    scores, overlap, _ = scores_from_identities(directory/'lexical.sqlite',
        ((r['node_id'], r['content_sha256'], r['lexical_input_sha256']) for r in records), tokenize(row['query']))
    lexical_positions = sorted(overlap, key=lambda i: (-float(scores[i]), records[i]['node_id']))
    lexical = [records[i]['node_id'] for i in lexical_positions[:limits['lexical']]]
    if needs:
        from retrieval.organization_search_needs import lexical_candidates
        prepared = [dict(r, parent_document_id=r['document_id']) for r in records]
        ids, lanes = lexical_candidates(directory/'lexical.sqlite', prepared, needs, metadata)
        lexical = ids[:limits['lexical']]
        positions={r['node_id']:i for i,r in enumerate(records)}
        lexical_positions=[positions[n] for n in ids]
        evidence.append({'search_needs':needs, 'lexical_needs':lanes})
    scores = frozen_cosine_scores(matrix, [r['vector_index'] for r in records], query_vector, total_count)
    dense = [records[i]['node_id'] for i in sorted(range(len(records)),
        key=lambda i: (-float(scores[i]), records[i]['node_id']))[:limits['dense']]]
    ranked.update(dense_candidates=dense, lexical_candidates=lexical,
                  fused_candidates=reciprocal_rank_fusion([dense, lexical]))
    if row.get('entity_id'):
        candidate_rows = [dict(node_id=r['node_id'], parent_document_id=r['document_id'],
                              content_sha256=r['content_sha256']) for r in records]
        request = SourceDocumentRequest(source_space='organization', operation='search',
            query=row['query'], entity_id=row['entity_id'], limit=20)
        graph, graph_evidence = candidates(directory/'graph.sqlite', candidate_rows, request, row['as_of'],
                                     [candidate_rows[i] for i in lexical_positions])
        evidence.extend(graph_evidence)
        ranked.update(graph_candidates=graph, graph_fused_candidates=reciprocal_rank_fusion([dense, lexical, graph]))
    return ranked, evidence


def planned_records(records, metadata, query, *, policy='conservative.v1'):
    """Same conservative planner as serving, never supplied known answer IDs."""
    documents, receipt = select_planned(metadata, plan_query(query, metadata, policy=policy))
    return [record for record in records if record['document_id'] in documents], receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('intake', 'dataset', 'index-directory', 'matrix', 'publication-checkpoint', 'query-cache', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--split', choices=('development', 'heldout', 'all'), required=True)
    parser.add_argument('--source-filter-plan', type=Path, help='Development-only manual constraints; never automatic query routing')
    parser.add_argument('--query-planning', choices=['conservative.v1', 'conservative.v2', 'conservative.v3', 'conservative.v4', 'conservative.v5'])
    parser.add_argument('--candidate-policy', choices=POLICIES, default='balanced.v1')
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
              'provider_calls': 0, 'status': 'preflight', 'samples': [], 'S2_passed': False,
              'numerical_thread_configuration': {name:os.environ.get(name) for name in
                  ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')}}
    from retrieval import organization_search_needs
    implementation_files=[Path(__file__),Path(organization_search_needs.__file__),
        Path(__import__('sec_agent.research_foundation.organization_query_plan',fromlist=['plan_query']).__file__)]
    implementation_before={str(p):digest(p) for p in implementation_files}
    report['diagnostic_implementation_sha256']=implementation_before
    save('result', report)
    try:
        guard('start')
        dataset = json.loads(args.dataset.read_text(encoding='utf8'))
        validate_heldout_freeze(dataset, args.split, candidate_policy=args.candidate_policy,
            query_planning=args.query_planning, check_runtime=True,
            metadata_policy='sec_cover.v2' if args.query_planning else 'original.v1',
            manual_plan=args.source_filter_plan is not None)
        validate_heldout_label_reviews(dataset,args.split)
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
        filters = None
        if args.query_planning and args.source_filter_plan:
            raise ValueError('automatic_and_manual_plans_are_separate_experiments')
        if args.source_filter_plan is not None:
            from scripts.engineering.organization_filter_diagnosis import validate_plan, metadata_maps, scope_records
            filters = validate_plan(json.loads(args.source_filter_plan.read_text(encoding='utf8')), rows)
            report['filter_plan_sha256'] = digest(args.source_filter_plan)
        directory = args.index_directory
        if args.split == 'heldout' and dataset['evaluation_role'] == 'independent_source_first':
            if digest(directory/'index.json') != dataset['index_file_sha256']:
                raise ValueError('heldout_frozen_index_mismatch')
        index = json.loads((directory/'index.json').read_text(encoding='utf8'))
        from sec_agent.research_foundation.organization_index_release import canonical_digest
        contract_digest = canonical_digest(index)
        if args.split == 'heldout' and dataset['evaluation_role'] == 'independent_source_first':
            if contract_digest != dataset['index_digest']:
                raise ValueError('heldout_frozen_contract_mismatch')
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
        if filters is not None or args.query_planning:
            from scripts.engineering.organization_filter_diagnosis import metadata_maps
            raw_metadata, resolved_metadata, proofs = metadata_maps(args.intake, intake, publication, manifest, guard)
            save('source-metadata', {'raw': raw_metadata, 'resolved': resolved_metadata, 'proofs': proofs})
            report['source_metadata_sha256'] = digest(args.output/'source-metadata.json')
        records = index['records']
        if len({r['document_id'] for r in records}) != len(bundles):
            raise ValueError('offline_index_document_scope_mismatch')
        positions = [r['vector_index'] for r in records]
        if sorted(positions) != list(range(len(records))):
            raise ValueError('offline_matrix_positions_mismatch')
        del publication, manifest
        namespace = sha256(json.dumps(['index-query.v1', 'public-recall-qualification',
            intake['source_index']['matrix_sha256'], index['model'], 1024], separators=(',', ':')).encode()).hexdigest()
        report.update(status='running', evaluation_role=dataset['evaluation_role'], split=args.split,
            candidate_sources=len(bundles), candidate_chunks=len(records), expected_questions=len(rows),
            dataset_sha256=digest(args.dataset), index_sha256=digest(directory/'index.json'),
            index_digest=contract_digest,
            matrix_sha256=index['matrix_sha256'], source_intake_sha256=digest(args.intake/'result.json'),
            query_planning=args.query_planning,
            candidate_policy=args.candidate_policy,
            implementation_sha256={name:digest(Path(module.__file__)) for name,module in [
                ('query_planner', __import__('sec_agent.research_foundation.organization_query_plan',fromlist=['plan_query'])),
                ('candidate_policy', __import__('retrieval.candidate_policy',fromlist=['candidate_limits']))]},
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
                    scoped = records
                    if args.query_planning:
                        scoped, receipt = planned_records(records, resolved_metadata, row['query'], policy=args.query_planning)
                        population = {r['node_id'] for r in scoped}
                        sample['query_plan'] = receipt
                        sample['known_evidence_excluded'] = [n for n in labels[row['id']] if n not in population]
                        del population
                    needs = None
                    if args.query_planning in {'conservative.v2', 'conservative.v3', 'conservative.v4', 'conservative.v5'}:
                        from retrieval.organization_search_needs import compile_needs
                        needs = compile_needs(row['query'], receipt)
                    ranked, evidence = rank_scope(scoped, directory, args.matrix, len(records), query, row,
                                                  candidate_policy=args.candidate_policy, needs=needs,
                                                  metadata=resolved_metadata if needs else None)
                    if needs:
                        sample['search_needs'] = evidence[0]
                    del scoped
                    if row.get('entity_id'):
                        sample['graph_evidence'] = evidence
                    sample.update(status='completed', gold=labels[row['id']], rankings=ranked,
                        metrics={k: ranking_metrics(v, labels[row['id']]) for k, v in ranked.items()})
                    if filters is not None:
                        sample['filter_diagnostics'] = []
                        for variant in filters[row['id']]['variants']:
                            for policy, metadata in (('raw_metadata', raw_metadata), ('sec_cover_resolved', resolved_metadata)):
                                guard('filter:'+row['id']+':'+variant['name']+':'+policy)
                                scoped, receipt = scope_records(records, metadata, variant['constraint'])
                                ranks, proof = rank_scope(scoped, directory, args.matrix, len(records), query, row,
                                                         candidate_policy=args.candidate_policy)
                                population = {r['node_id'] for r in scoped}
                                sample['filter_diagnostics'].append({**variant, 'metadata_policy': policy,
                                    'coverage': receipt, 'candidate_chunks': len(scoped),
                                    'known_evidence_excluded': [n for n in labels[row['id']] if n not in population],
                                    'rankings': ranks, 'graph_evidence': proof,
                                    'metrics': {k: ranking_metrics(v, labels[row['id']]) for k, v in ranks.items()}})
                                del scoped, population
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
        if implementation_before!={str(p):digest(p) for p in implementation_files}:
            raise ValueError('offline_implementation_changed_during_evaluation')
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
