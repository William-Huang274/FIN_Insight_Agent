"""One frozen heldout reranking evaluation, never a model-selection ablation.

The upstream candidate run must cover the complete frozen positive split.
This evaluates known evidence in public qualification artifacts. Current ACL,
negative answerability, service latency and financial quality remain separate.
"""
import argparse
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import time
import zlib

from retrieval.rank_fusion import reciprocal_rank_fusion
from retrieval.organization_search_needs import select_coverage
from scripts.engineering.organization_recall_evaluation import bind_labels, bind_label_groups, evidence_group_metrics
from scripts.engineering.qualify_retrieval_recall import ranking_metrics
from scripts.engineering.retrieval_evaluation_freeze import validate_heldout_freeze
from scripts.engineering.retrieval_label_review import validate_heldout_label_reviews


def validate_population(dataset, saved, index, gold):
    """Reject partial populations and tuned/mixed policies before any provider."""
    if dataset.get('evaluation_role') != 'independent_source_first':
        raise ValueError('heldout_independent_dataset_required')
    policy = dataset['policy']
    validate_heldout_freeze(dataset, 'heldout', candidate_policy=saved.get('candidate_policy'),
        query_planning=saved.get('query_planning'), metadata_policy='sec_cover.v2', check_runtime=True)
    validate_heldout_label_reviews(dataset, 'heldout')
    if policy['reranker'] != 'qwen3.7-text-rerank':
        raise ValueError('heldout_reranker_not_frozen_candidate')
    questions = {q['id']: q for q in dataset['questions'] if q['split'] == 'heldout'}
    if len(questions) != sum(q['split'] == 'heldout' for q in dataset['questions']):
        raise ValueError('heldout_duplicate_question_identity')
    samples = saved.get('samples', [])
    if (saved.get('status') != 'completed' or saved.get('split') != 'heldout'
            or saved.get('evaluation_role') != 'independent_source_first'
            or saved.get('expected_questions') != len(questions)
            or [s['id'] for s in samples] != list(questions)):
        raise ValueError('heldout_complete_ordered_population_required')
    records = {r['node_id']: r for r in index['records']}
    if (len(records) != len(index['records']) or len(records) != saved['candidate_chunks']
            or len({r['document_id'] for r in records.values()}) != saved['candidate_sources']):
        raise ValueError('heldout_candidate_universe_mismatch')
    for sample in samples:
        q = questions[sample['id']]
        if (sample.get('status') != 'completed' or sample.get('split') != 'heldout'
                or sample['family'] != q['family'] or sample['gold'] != gold[q['id']]):
            raise ValueError('heldout_sample_or_original_label_mismatch')
        ranks = sample['rankings']
        channels = [ranks['dense_candidates'], ranks['lexical_candidates']]
        if 'graph_candidates' in ranks:
            channels.append(ranks['graph_candidates'])
        for ids in channels:
            if len(ids) != len(set(ids)) or any(n not in records for n in ids):
                raise ValueError('heldout_candidate_identity_mismatch')
        key = 'graph_fused_candidates' if len(channels) == 3 else 'fused_candidates'
        if ranks[key] != reciprocal_rank_fusion(channels) or not 1 <= len(ranks[key]) <= 48:
            raise ValueError('heldout_frozen_candidate_union_mismatch')
    return questions, records


def prepare(dataset_path, result_path, index_path, publication_path):
    paths = {'dataset': dataset_path, 'candidate_result': result_path, 'index': index_path,
             'publication': publication_path, 'metadata': result_path.parent/'source-metadata.json'}
    raw = {name: path.read_bytes() for name, path in paths.items()}
    data = {name: json.loads(value) for name, value in raw.items()}
    dataset, saved, index = data['dataset'], data['candidate_result'], data['index']
    from sec_agent.research_foundation.organization_index_release import canonical_digest
    if (sha256(raw['dataset']).hexdigest() != saved['dataset_sha256']
            or sha256(raw['index']).hexdigest() != saved['index_sha256']
            or saved['index_sha256'] != dataset['index_file_sha256']
            or canonical_digest(index) != dataset['index_digest']
            or saved['index_digest'] != dataset['index_digest']
            or sha256(raw['metadata']).hexdigest() != saved.get('source_metadata_sha256')):
        raise ValueError('heldout_frozen_input_mismatch')
    publication = data['publication']['publication']
    rows = [q for q in dataset['questions'] if q['split'] == 'heldout']
    cutoff = {q['as_of'] for q in rows}
    if len(cutoff) != 1:
        raise ValueError('heldout_one_cutoff_required')
    manifest = {'research_as_of': next(iter(cutoff)), 'inputs': [
        {'resource_id': g['id'], 'ref': g['binding']['ref']} for g in publication['grants'].values()]}
    gold = bind_labels(rows, manifest, publication['resources'], index)
    gold_groups = bind_label_groups(rows, manifest, publication['resources'], index)
    questions, records = validate_population(dataset, saved, index, gold)
    metadata = data['metadata']['resolved']
    navigation = index_path.parent/'navigation.sqlite'
    jobs = []
    with closing(sqlite3.connect(navigation.resolve().as_uri()+'?mode=ro', uri=True)) as db:
        for sample in saved['samples']:
            key = 'graph_fused_candidates' if 'graph_candidates' in sample['rankings'] else 'fused_candidates'
            candidates = []
            for node in sample['rankings'][key]:
                found = db.execute('SELECT payload FROM nodes WHERE node_id=?', (node,)).fetchone()
                if not found:
                    raise ValueError('heldout_missing_candidate_body')
                payload = zlib.decompress(found[0])
                if sha256(payload).hexdigest() != records[node]['navigation_sha256']:
                    raise ValueError('heldout_candidate_body_mismatch')
                candidate = json.loads(payload)
                if candidate['node_id'] != node:
                    raise ValueError('heldout_candidate_payload_identity_mismatch')
                candidates.append(candidate)
            jobs.append({'id': sample['id'], 'family': sample['family'],
                'query': questions[sample['id']]['query'], 'candidates': candidates,
                'gold': gold[sample['id']], 'gold_groups': gold_groups[sample['id']],
                'search_needs': sample.get('search_needs')})
    from retrieval import qwen_api, scoped_reranking, organization_search_needs
    code = [Path(__file__), Path(qwen_api.__file__), Path(scoped_reranking.__file__),
            Path(organization_search_needs.__file__)]
    plan = {'evaluation_role': 'independent_source_first', 'split': 'heldout',
        'input_sha256': {name: sha256(value).hexdigest() for name, value in raw.items()},
        'input_paths': {name: str(path) for name, path in paths.items()},
        'implementation_sha256': {str(p): sha256(p.read_bytes()).hexdigest() for p in code},
        'ranking_policy': dataset['policy'], 'instruction': None,
        'TokenBudgetBasis': {
            'purpose': 'Frozen independent positive known-evidence ranking; no model selection',
            'input_scale': {'queries': len(jobs), 'candidate_occurrences': sum(len(j['candidates']) for j in jobs),
                'candidate_utf8_bytes': sum(len((c.get('embedding_context', '')+'\n'+c['content']).encode())
                    for j in jobs for c in j['candidates'])},
            'required_output': 'Full ranking and usage receipts; strict known-evidence hit/recall and clause coverage',
            'quality_risk': 'Assistant source review; non-exhaustive labels; bilingual questions are correlated; no current ACL or answerability claim',
            'reasoning_profile': dataset['policy']['reranker']+'; original query/body, no extra instruction or generation',
            'limits': {'requests': len(jobs), 'candidates_per_request': 48, 'concurrency': 1, 'automatic_retries': 0},
            'stop_behavior': 'Stop on first error, retain unknown/failed usage, never resubmit; no policy tuning on this set'}}
    return jobs, metadata, plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('dataset', 'result', 'index', 'publication', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    jobs, metadata, plan = prepare(args.dataset, args.result, args.index, args.publication)
    args.output.mkdir(parents=True, exist_ok=True)
    plan_path = args.output/'plan.json'
    if plan_path.exists() and json.loads(plan_path.read_bytes()) != plan:
        raise ValueError('heldout_plan_changed')
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf8')
    if not args.execute:
        print(json.dumps(plan['TokenBudgetBasis'])); return
    if (args.output/'result.json').exists():
        raise ValueError('heldout_execution_already_started_no_automatic_resubmission')
    from retrieval.qwen_api import QwenRetrieval
    from retrieval.scoped_reranking import ScopedReranker
    key = os.environ.get('QWEN_API_KEY')
    if not key:
        raise ValueError('configured_qwen_key_unavailable')
    api = QwenRetrieval(key, rerank_model=plan['ranking_policy']['reranker'])
    source = ScopedReranker(args.output/'provider-records', api)
    report = {'status': 'running', 'S2_passed': False, 'evaluation_role': 'independent_source_first',
        'split': 'heldout', 'expected_questions': len(jobs), 'samples': [],
        'plan_sha256': sha256(plan_path.read_bytes()).hexdigest(),
        'limits': 'Frozen positive known-evidence ranking only; not Precision, answerability, online ACL or capacity'}
    def save():
        (args.output/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    save()
    try:
        for job in jobs:
            start = time.perf_counter()
            ranked, receipt = source.rank(job['query'], job['candidates'],
                scope='qualification:independent-positive-heldout',
                index_digest=plan['input_sha256']['index'], check_access=lambda: None)
            selected = ranked[:plan['ranking_policy']['returned_limit']]
            coverage = None
            if job['search_needs']:
                needs = job['search_needs']
                selected, coverage = select_coverage(ranked, needs['search_needs'], needs['lexical_needs'], metadata)
                selected = selected[:plan['ranking_policy']['returned_limit']]
            rankings = {'candidate_union': [c['node_id'] for c in job['candidates']],
                'reranked': [c['node_id'] for c in ranked], 'selected': [c['node_id'] for c in selected]}
            report['samples'].append({'id': job['id'], 'family': job['family'], 'gold': job['gold'],
                'gold_groups': job['gold_groups'],
                'status': 'completed', 'rankings': rankings, 'receipt': receipt,
                'metrics': {name: ranking_metrics(ids, job['gold']) for name, ids in rankings.items()},
                'equivalent_metrics': {name: evidence_group_metrics(ids, job['gold_groups']) for name, ids in rankings.items()},
                'need_coverage': coverage, 'offline_seconds': time.perf_counter()-start})
            save()
            if len(report['samples']) % 10 == 0:
                print(json.dumps({'completed': len(report['samples']), 'expected': len(jobs)}), flush=True)
        for path, expected in plan['implementation_sha256'].items():
            if sha256(Path(path).read_bytes()).hexdigest() != expected:
                raise ValueError('heldout_implementation_changed')
        for name, path in plan['input_paths'].items():
            if sha256(Path(path).read_bytes()).hexdigest() != plan['input_sha256'][name]:
                raise ValueError('heldout_input_changed')
        report['status'] = 'completed'
    except Exception as exc:
        report.update(status='failed', error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        api.close(); save()
    print(json.dumps({'status': report['status'], 'questions': len(report['samples'])}))


if __name__ == '__main__':
    main()
