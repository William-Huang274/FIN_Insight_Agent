"""Offline score reuse must bind the full request, never just candidate IDs."""
import importlib.util
import json
from hashlib import sha256
from pathlib import Path
import pytest


def module():
    path = Path(__file__).resolve().parents[1] / 'scripts/engineering/rerank_parser_ablation.py'
    spec = importlib.util.spec_from_file_location('parser_rerank_probe', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize('mutation,reused', [
    ('serialization', True), ('query', False), ('body', False), ('identity', False),
])
def test_completed_scores_reused_only_for_identical_provider_request(tmp_path, mutation, reused):
    probe = module()
    old = tmp_path / 'old'; old.mkdir()
    trace = tmp_path / 'trace'; trace.mkdir()
    data = {'query': 'Acme cash', 'candidates': [
        {'node_id': 'a', 'content': 'Cash is 10 million.', 'embedding_context': 'Acme annual report'}]}
    data['candidates'][0]['content_sha256'] = sha256(data['candidates'][0]['content'].encode()).hexdigest()
    previous = old / 'request.json'
    previous.write_text(json.dumps(data), encoding='utf8')
    job = {'id': 'q', 'arm': 'parsed', 'path': str(previous),
           'sha256': sha256(previous.read_bytes()).hexdigest()}
    (old / 'plan.json').write_text(json.dumps({'jobs': [job], 'instruction': probe.TEXT}), encoding='utf8')
    (old / 'result.json').write_text(json.dumps({'status': 'completed', 'samples': [
        {'id': 'q', 'arm': 'parsed', 'ranked_ids': ['a'], 'receipt': {'provider_calls': 1}}]}), encoding='utf8')
    if mutation == 'query': data['query'] = 'Acme debt'
    elif mutation == 'body': data['candidates'][0]['content'] = 'Cash is 100 million.'
    elif mutation == 'identity': data['candidates'][0]['node_id'] = 'different-source'
    data['candidates'][0]['content_sha256'] = sha256(data['candidates'][0]['content'].encode()).hexdigest()
    (trace / 'q.parsed.json').write_text(json.dumps(data, indent=2), encoding='utf8')
    (trace / 'summary.json').write_text(json.dumps({'status': 'completed', 'samples': [
        {'id': 'q', 'arm': 'parsed'}]}), encoding='utf8')
    output = tmp_path / 'next'
    probe.prepare(trace, output, old)
    plan = json.loads((output / 'plan.json').read_bytes())
    assert bool(plan['jobs'][0]['reuse_sample']) is reused
    assert plan['TokenBudgetBasis']['input_scale']['requests'] == int(not reused)
