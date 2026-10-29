"""Audited paired reranking after parser ablation, never a live ACL test."""
import argparse
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import psutil
from retrieval.scoped_reranking import ScopedReranker, scoring_documents
from retrieval.relevance_instruction import TEXT
from retrieval.qwen_api import QwenRetrieval


def prepare(trace, output, reuse=None):
    summary = json.loads((trace / 'summary.json').read_bytes())
    if summary['status'] != 'completed':
        raise ValueError('incomplete_pair_trace')
    output.mkdir(parents=True, exist_ok=False)
    jobs, size = [], 0
    old_jobs, old_results = {}, {}
    if reuse:
        old_plan = json.loads((reuse / 'plan.json').read_bytes())
        old_result = json.loads((reuse / 'result.json').read_bytes())
        if old_result['status'] != 'completed' or old_plan['instruction'] != TEXT:
            raise ValueError('rerank_reuse_requires_completed_identical_instruction')
        old_jobs = {(j['id'], j['arm']): j for j in old_plan['jobs']}
        old_results = {(j['id'], j['arm']): j for j in old_result['samples']}
    for row in summary['samples']:
        path = trace / (row['id'] + '.' + row['arm'] + '.json')
        raw = path.read_bytes(); data = json.loads(raw)
        texts = scoring_documents(data['candidates'])
        prior = old_jobs.get((row['id'], row['arm']))
        reuse_sample = None
        if prior:
            prior_bytes = Path(prior['path']).read_bytes()
            if sha256(prior_bytes).hexdigest() != prior['sha256']:
                raise ValueError('prior_scoring_file_changed')
            old_data = json.loads(prior_bytes)
            exact_request = (
                old_data['query'] == data['query']
                and [c['node_id'] for c in old_data['candidates']] == [c['node_id'] for c in data['candidates']]
                and scoring_documents(old_data['candidates']) == texts
            )
            if exact_request:
                reuse_sample = old_results.get((row['id'], row['arm']))
        if reuse_sample is None:
            size += sum(len(t.encode()) for t in texts)
        jobs.append({'path': str(path.resolve()), 'sha256': sha256(raw).hexdigest(),
                     'id': row['id'], 'arm': row['arm'], 'input_sha256': [sha256(t.encode()).hexdigest() for t in texts],
                     'reuse_sample': reuse_sample})
    if len(jobs) > 88 or size > 20_000_000:
        raise ValueError('paired_rerank_requires_replanning')
    basis = {'purpose': 'Compare old and source-structured candidates under identical reranker and instructions',
             'input_scale': {'requests': sum(j['reuse_sample'] is None for j in jobs), 'utf8_bytes': size,
                             'reused_exact_requests': sum(j['reuse_sample'] is not None for j in jobs)},
             'required_output': 'All 48 candidate scores, order and durable usage receipt per request',
             'quality_risk': 'Exposed regression; semantics unresolved; scores are not probabilities; not live serving',
             'reasoning_profile': 'qwen3.7-text-rerank, financial-evidence.v1, no Agent generation',
             'limits': {'requests': len(jobs), 'concurrency': 1, 'automatic_retries': 0},
             'stop_behavior': 'Stop on first failure/unknown usage or available memory below 800 MiB; preserve receipts'}
    plan = {'jobs': jobs, 'TokenBudgetBasis': basis, 'instruction': TEXT,
            'reuse_proofs': {str((reuse / name).resolve()): sha256((reuse / name).read_bytes()).hexdigest()
                            for name in ('plan.json', 'result.json')} if reuse else {},
            'driver_sha256': sha256(Path(__file__).read_bytes()).hexdigest()}
    (output / 'plan.json').write_text(json.dumps(plan), encoding='utf8')
    print(json.dumps(basis), flush=True)


def run(output):
    raw = (output / 'plan.json').read_bytes(); plan = json.loads(raw); digest = sha256(raw).hexdigest()
    if sha256(Path(__file__).read_bytes()).hexdigest() != plan['driver_sha256']:
        raise ValueError('rerank_driver_changed')
    for path, expected in plan.get('reuse_proofs', {}).items():
        if sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError('rerank_reuse_proof_changed')
    result = {'status': 'running', 'samples': [], 'provider_calls': 0, 'reported_tokens': 0,
              'live_authorization_tested': False, 'plan_sha256': digest}
    try:
        with closing(QwenRetrieval(os.environ['QWEN_API_KEY'], rerank_model='qwen3.7-text-rerank')) as api:
            ranker = ScopedReranker(output / 'receipts', api)
            for job in plan['jobs']:
                path = Path(job['path'])
                def check():
                    if sha256(path.read_bytes()).hexdigest() != job['sha256']:
                        raise ValueError('frozen_candidate_input_changed')
                    if psutil.virtual_memory().available < 800 * 2**20:
                        raise RuntimeError('ablation_memory_guard')
                check(); data = json.loads(path.read_bytes())
                if [sha256(t.encode()).hexdigest() for t in scoring_documents(data['candidates'])] != job['input_sha256']:
                    raise ValueError('scorer_input_changed')
                if job.get('reuse_sample'):
                    previous = job['reuse_sample']
                    result['samples'].append({**previous, 'receipt': {**previous['receipt'],
                        'provider_calls': 0, 'cache_hit': True, 'newly_reported_usage': {},
                        'reused_exact_candidate_file_sha256': job['sha256']}})
                    continue
                ranked, receipt = ranker.rank(data['query'], data['candidates'],
                    scope='offline-parser-ablation:'+digest, index_digest=digest,
                    check_access=check, instruct=plan['instruction'])
                result['samples'].append({'id': job['id'], 'arm': job['arm'],
                                          'ranked_ids': [r['node_id'] for r in ranked], 'receipt': receipt})
                result['provider_calls'] += receipt['provider_calls']
                usage = receipt.get('newly_reported_usage', {})
                result['reported_tokens'] += usage.get('total_tokens', usage.get('input_tokens', 0))
                (output / 'result.json').write_text(json.dumps(result), encoding='utf8')
                print(json.dumps({'completed': len(result['samples']), 'requests': len(plan['jobs']),
                                  'reported_tokens': result['reported_tokens']}), flush=True)
        result['status'] = 'completed'
    except Exception as error:
        result.update(status='stopped', error=type(error).__name__, failed_usage='inspect_receipts_not_zero')
        raise
    finally:
        (output / 'result.json').write_text(json.dumps(result), encoding='utf8')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trace', type=Path); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--execute', action='store_true'); a = p.parse_args()
    if a.execute: run(a.output)
    else: prepare(a.trace, a.output)
