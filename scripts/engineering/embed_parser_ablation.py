"""Bounded exact-input embedding probe, with durable failure/no-retry receipts."""
import argparse
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil


def prepare(base, output, document_ids, reuse=None):
    output.mkdir(parents=True, exist_ok=False)
    documents = set(document_ids)
    sources = json.loads((base / 'manifest.json').read_bytes())['samples']
    units = []
    proofs = {}
    for source in sources:
        if source['document_id'] not in documents:
            continue
        path = base / 'units' / (source['id'] + '.json')
        proofs[str(path.resolve())] = sha256(path.read_bytes()).hexdigest()
        units.extend(json.loads(path.read_bytes()))
    if {u['document_id'] for u in units} != documents:
        raise ValueError('embedding_scope_incomplete')
    unique = {u['input_sha256']: u['embedding_input'] for u in units}
    if any(sha256(t.encode()).hexdigest() != k for k, t in unique.items()):
        raise ValueError('changed_embedding_input')
    reuse_ids = set()
    if reuse is not None:
        if json.loads((reuse / 'status.json').read_bytes())['status'] != 'completed':
            raise ValueError('only_completed_vector_matrix_can_be_reused')
        reuse_ids = set(json.loads((reuse / 'identities.json').read_bytes()))
        for name in ('identities.json', 'vectors.npy', 'plan.json', 'status.json'):
            proofs[str((reuse / name).resolve())] = sha256((reuse / name).read_bytes()).hexdigest()
    fresh = {key: text for key, text in unique.items() if key not in reuse_ids}
    size = sum(len(t.encode()) for t in fresh.values())
    # The first causal probe must not silently become another whole-corpus job.
    if len(fresh) > 4000 or size > 4_000_000:
        raise ValueError('first_ablation_scope_requires_explicit_replanning')
    jobs, batch, amount = [], [], 0
    for key, text in fresh.items():
        if len(text.encode()) > 16384:
            raise ValueError('oversized_input_no_truncation')
        if batch and (len(batch) == 20 or amount + len(text.encode()) > 131072):
            jobs.append(batch); batch, amount = [], 0
        batch.append({'sha256': key, 'text': text}); amount += len(text.encode())
    if batch:
        jobs.append(batch)
    basis = {'purpose': 'Isolate upstream SEC parser/chunking effects on exposed hard retrieval questions',
             'input_scale': {'documents': len(documents), 'unique_inputs': len(fresh), 'utf8_bytes': size,
                             'reused_exact_inputs': len(set(unique) & reuse_ids)},
             'required_output': '1024-dimensional vectors with exact input identity and usage receipts',
             'quality_risk': 'Development diagnostic only; unchanged background retained; no financial-semantic correctness assumption',
             'reasoning_profile': 'qwen3.7-text-embedding; no generative Agent calls',
             'limits': {'requests': len(jobs), 'concurrency': 1, 'automatic_retries': 0,
                        'reported_tokens_stop_cap': size + 128 * len(jobs)},
             'stop_behavior': 'Stop first failed/unknown request, input drift or resource shortage; never resubmit automatically'}
    plan = {'TokenBudgetBasis': basis, 'proofs': proofs, 'documents': sorted(documents), 'jobs': jobs,
            'reuse': str(reuse.resolve()) if reuse else None, 'reused_ids': sorted(set(unique) & reuse_ids),
            'generator_sha256': sha256(Path(__file__).read_bytes()).hexdigest()}
    (output / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False), encoding='utf8')
    (output / 'units.json').write_text(json.dumps(units, ensure_ascii=False), encoding='utf8')
    print(json.dumps(basis, ensure_ascii=False))


def execute(output):
    import numpy as np
    import psutil
    from retrieval.qwen_api import QwenRetrieval
    from retrieval.unit_embedding_preparation import UnitEmbeddingPreparation
    plan_path = output / 'plan.json'
    plan_bytes = plan_path.read_bytes(); plan = json.loads(plan_bytes)
    if sha256(Path(__file__).read_bytes()).hexdigest() != plan['generator_sha256']:
        raise ValueError('embedding_driver_changed')
    for p, digest in plan['proofs'].items():
        if sha256(Path(p).read_bytes()).hexdigest() != digest:
            raise ValueError('frozen_units_changed')
    basis = plan['TokenBudgetBasis']
    summary = {'status': 'running', 'provider_calls': 0, 'reported_tokens': 0, 'failed_usage_unknown': False}
    rows, identities = [], []
    if plan.get('reuse'):
        reused_path = Path(plan['reuse'])
        original_ids = json.loads((reused_path / 'identities.json').read_bytes())
        original_positions = {key: i for i, key in enumerate(original_ids)}
        original_matrix = np.load(reused_path / 'vectors.npy', mmap_mode='r')
        for key in plan['reused_ids']:
            rows.append(original_matrix[original_positions[key]]); identities.append(key)
    try:
        with closing(QwenRetrieval(os.environ['QWEN_API_KEY'], embedding_model='qwen3.7-text-embedding')) as api:
            worker = UnitEmbeddingPreparation(output / 'receipts', api, snapshot=sha256(plan_bytes).hexdigest(), budget=basis)
            for i, batch in enumerate(plan['jobs']):
                if psutil.virtual_memory().available < 800 * 2**20 or shutil.disk_usage(output).free < 1 * 2**30:
                    raise RuntimeError('ablation_resource_guard')
                if summary['reported_tokens'] > basis['limits']['reported_tokens_stop_cap']:
                    raise RuntimeError('ablation_reported_token_guard')
                vectors, receipt = worker.embed([x['text'] for x in batch])
                rows.extend(vectors); identities.extend(x['sha256'] for x in batch)
                summary['provider_calls'] += receipt['provider_calls']
                usage = receipt.get('newly_reported_usage', {})
                summary['reported_tokens'] += usage.get('total_tokens', usage.get('input_tokens', 0))
                summary['completed_batches'] = i + 1
                (output / 'status.json').write_text(json.dumps(summary), encoding='utf8')
                print(json.dumps(summary), flush=True)
        np.save(output / 'vectors.npy', np.asarray(rows, dtype=np.float32), allow_pickle=False)
        (output / 'identities.json').write_text(json.dumps(identities), encoding='utf8')
        summary['status'] = 'completed'
    except Exception as error:
        summary.update(status='stopped', error=type(error).__name__, failed_usage_unknown='inspect durable receipts')
        raise
    finally:
        (output / 'status.json').write_text(json.dumps(summary), encoding='utf8')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--documents', type=Path); p.add_argument('--execute', action='store_true')
    p.add_argument('--reuse', type=Path)
    a = p.parse_args()
    if a.execute:
        execute(a.output)
    else:
        prepare(a.base, a.output, json.loads(a.documents.read_bytes())['document_ids'], a.reuse)
