from copy import deepcopy
import json
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from scripts.engineering import evaluate_organization_heldout_reranking as evaluation
from scripts.engineering.retrieval_evaluation_freeze import policy_digest


def inputs():
    policy = {'candidate_policy': 'dense_expanded.v1', 'query_planning': 'conservative.v2',
        'metadata_policy': 'sec_cover.v2', 'reranker': 'qwen3.7-text-rerank', 'returned_limit': 20}
    anchor = {'source_id': 'source', 'chunk_id': 'chunk', 'body_sha256': 'c'*64, 'quote': 'Capacity per day'}
    q = {'id': 'q', 'split': 'heldout', 'family': 'family', 'query': 'capacity?', 'evidence': [anchor],
        'label_review': {'status': 'reviewed', 'reviewer': 'fixture',
            'coverage_attestation': 'all_question_requirements_checked_against_originals',
            'requirements': [{'id': 'unit', 'description': 'Capacity time denominator', 'citations': [anchor]}]}}
    dataset = {'evaluation_role': 'independent_source_first', 'questions': [q],
        'index_digest': 'a'*64, 'index_file_sha256': 'b'*64, 'policy': policy,
        'freeze': {'status': 'frozen', 'heldout_prior_results_exposed': False,
            'ranking_policy': deepcopy(policy), 'ranking_policy_sha256': policy_digest(policy)}}
    sample = {'id': 'q', 'family': 'family', 'split': 'heldout', 'status': 'completed', 'gold': ['a'],
        'rankings': {'dense_candidates': ['a', 'b'], 'lexical_candidates': ['b'], 'fused_candidates': ['b', 'a']}}
    result = {'status': 'completed', 'split': 'heldout', 'evaluation_role': 'independent_source_first',
        'candidate_policy': 'dense_expanded.v1', 'query_planning': 'conservative.v2',
        'candidate_chunks': 2, 'candidate_sources': 1, 'expected_questions': 1, 'samples': [sample]}
    index = {'records': [{'node_id': n, 'document_id': 'document'} for n in ('a', 'b')]}
    return dataset, result, index, {'q': ['a']}


def test_only_complete_frozen_independent_population_can_reach_reranking():
    dataset, result, index, gold = inputs()
    questions, records = evaluation.validate_population(dataset, result, index, gold)
    assert list(questions) == ['q'] and set(records) == {'a', 'b'}


@pytest.mark.parametrize('change,error', [
    (lambda d,r: d.update(evaluation_role='historical_regression'), 'independent_dataset'),
    (lambda d,r: d['questions'].append(deepcopy(d['questions'][0])), 'duplicate_question'),
    (lambda d,r: r['samples'].clear(), 'population'),
    (lambda d,r: r['samples'].append(deepcopy(r['samples'][0])), 'population'),
    (lambda d,r: r.update(query_planning='conservative.v1'), 'runtime_policy'),
    (lambda d,r: r['samples'][0].update(status='failed'), 'sample_or_original'),
    (lambda d,r: r['samples'][0].update(gold=['b']), 'sample_or_original'),
    (lambda d,r: r['samples'][0]['rankings']['dense_candidates'].append('foreign'), 'identity'),
    (lambda d,r: r['samples'][0]['rankings'].update(fused_candidates=['a','b']), 'candidate_union'),
    (lambda d,r: d['questions'][0]['label_review'].update(status='pending'), 'review_incomplete'),
])
def test_no_partial_population_or_rewritten_labels_and_policy(change, error):
    dataset, result, index, gold = inputs()
    change(dataset, result)
    with pytest.raises(ValueError, match=error):
        evaluation.validate_population(dataset, result, index, gold)


def test_failed_paid_execution_is_saved_and_cannot_be_reissued(tmp_path, monkeypatch):
    from retrieval import qwen_api, scoped_reranking
    calls = []
    plan = {'ranking_policy': inputs()[0]['policy'], 'input_sha256': {'index': 'a'*64},
            'TokenBudgetBasis': {}, 'implementation_sha256': {}, 'input_paths': {}}
    monkeypatch.setattr(evaluation, 'prepare', lambda *a: ([{'query': 'q', 'candidates': []}], {}, plan))
    class Api:
        def __init__(self, *a, **kw): pass
        def close(self): pass
    class Rerank:
        def __init__(self, *a): pass
        def rank(self, *a, **kw):
            calls.append('request')
            raise TimeoutError('unknown paid outcome fixture')
    monkeypatch.setattr(qwen_api, 'QwenRetrieval', Api)
    monkeypatch.setattr(scoped_reranking, 'ScopedReranker', Rerank)
    monkeypatch.setenv('QWEN_API_KEY', 'fixture')
    args = ['heldout']
    for field in ('dataset', 'result', 'index', 'publication', 'output'):
        args.extend(['--'+field, str(tmp_path)])
    monkeypatch.setattr(sys, 'argv', args+['--execute'])
    with pytest.raises(TimeoutError): evaluation.main()
    assert json.loads((tmp_path/'result.json').read_bytes())['status'] == 'failed'
    with pytest.raises(ValueError, match='already_started'): evaluation.main()
    assert calls == ['request']


def test_real_frozen_artifacts_prepare_and_rerank_without_changing_candidate_set(tmp_path, monkeypatch):
    from test_organization_offline_recall import setup
    from scripts.engineering.diagnose_organization_retrieval_candidates import main as candidate_main
    from sec_agent.research_foundation.organization_index_release import canonical_digest
    from retrieval import qwen_api
    setup(tmp_path, monkeypatch, True)
    args = list(sys.argv)
    directory = Path(args[args.index('--index-directory')+1])
    index_bytes = (directory/'index.json').read_bytes()
    dataset = json.loads((tmp_path/'questions.json').read_bytes())
    q = dataset['questions'][0]
    q['split'] = 'heldout'
    q['label_review'] = deepcopy(inputs()[0]['questions'][0]['label_review'])
    q['label_review']['requirements'][0]['citations'] = [q['evidence'][0]]
    base = inputs()[0]
    dataset.update(evaluation_role='independent_source_first', policy=base['policy'], freeze=base['freeze'],
        index_file_sha256=sha256(index_bytes).hexdigest(), index_digest=canonical_digest(json.loads(index_bytes)))
    (tmp_path/'questions.json').write_text(json.dumps(dataset), encoding='utf8')
    args[-1] = 'heldout'
    monkeypatch.setattr(sys, 'argv', args+['--query-planning','conservative.v2','--candidate-policy','dense_expanded.v1'])
    candidate_main()
    jobs, metadata, plan = evaluation.prepare(tmp_path/'questions.json', tmp_path/'output/result.json',
        directory/'index.json', tmp_path/'checkpoint/manifest.json')
    assert len(jobs) == 1 and jobs[0]['gold'] == [c['node_id'] for c in jobs[0]['candidates']]
    assert plan['TokenBudgetBasis']['input_scale']['queries'] == 1
    called = []
    class Api:
        rerank_model = 'qwen3.7-text-rerank'
        def __init__(self, *a, **kw): assert kw['rerank_model'] == self.rerank_model
        def close(self): pass
        def rerank(self, query, documents, **kw):
            called.append((query, documents))
            return qwen_api.RetrievalResponse([{'index': 0, 'relevance_score': .9}], {'total_tokens': 5}, 'fixture', self.rerank_model)
    monkeypatch.setattr(qwen_api, 'QwenRetrieval', Api)
    monkeypatch.setenv('QWEN_API_KEY', 'fixture')
    monkeypatch.setattr(sys, 'argv', ['heldout', '--dataset',str(tmp_path/'questions.json'),
        '--result',str(tmp_path/'output/result.json'),'--index',str(directory/'index.json'),
        '--publication',str(tmp_path/'checkpoint/manifest.json'),'--output',str(tmp_path/'final'),'--execute'])
    evaluation.main()
    report = json.loads((tmp_path/'final/result.json').read_bytes())
    assert report['status'] == 'completed' and not report['S2_passed']
    assert len(called) == 1 and called[0][0] == 'Alpha cash'
    assert report['samples'][0]['rankings']['selected'] == jobs[0]['gold']
