from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

from tests.integration.source_intake_quality import (
    PaidCallBudget, provider_network, load_frozen_quality, score_original_spans, run_quality,
)


def bundle():
    text = 'principal 100; maturity 2030'
    return {'source': {'id': 's', 'digest': sha256(text.encode()).hexdigest()}, 'text': text,
            'chunks': [{'id': str(i), 'body': text[lo:hi],
                        'digest': sha256(text[lo:hi].encode()).hexdigest(),
                        'source_char_start': lo, 'source_char_end': hi}
                       for i, (lo, hi) in enumerate([(0, 14), (14, len(text))])]}


def fixture(tmp_path):
    b = bundle()
    q = {'id': 'split-evidence', 'query': 'principal and maturity', 'family': 's',
         'question_kind': 'positive_fact_request', 'reviewed_spans': [
             {'source_id': 's', 'source_digest': b['source']['digest'], 'start': 0, 'end': len(b['text'])}]}
    data = {'questions': [q], 'freeze': {'status': 'frozen', 'ranking_policy': {
        'candidate_policy': 'needs_window.v4', 'query_planning': 'conservative.v5',
        'metadata_policy': 'sec_cover.v2', 'reranker': 'qwen3.7-text-rerank', 'returned_limit': 20}}}
    raw = json.dumps(data).encode()
    digest = sha256(raw).hexdigest()
    (tmp_path/'dataset.json').write_bytes(raw)
    (tmp_path/'plan.json').write_text(json.dumps({'dataset_sha256': digest, 'sources': 1}))
    (tmp_path/'summary.json').write_text(json.dumps({'batch_quality_passed': True,
        'execution_status': 'completed', 'executed': 1, 'expected': 1, 'rows': [{'id': q['id']}]}))
    return data, b, digest


def test_frozen_scope_and_original_span_validation(tmp_path):
    _, b, digest = fixture(tmp_path)
    data, binding = load_frozen_quality(tmp_path, digest, {'s': b})
    assert data['questions'][0]['id'] == 'split-evidence'
    assert binding['dataset_sha256'] == digest
    with pytest.raises(ValueError, match='dataset_digest'):
        load_frozen_quality(tmp_path, '0'*64, {'s': b})
    with pytest.raises(ValueError, match='incomplete_source_scope'):
        load_frozen_quality(tmp_path, digest, {'s': b, 'other': b})
    with pytest.raises(ValueError, match='source_version'):
        load_frozen_quality(tmp_path, digest, {'s': {**b, 'source': {'id': 's', 'digest': 'bad'}}})


def test_incomplete_offline_batch_cannot_authorize_service_replay(tmp_path):
    _, b, digest = fixture(tmp_path)
    p = tmp_path/'summary.json'
    summary = json.loads(p.read_text())
    summary['batch_quality_passed'] = False
    p.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match='completed_frozen_batch'):
        load_frozen_quality(tmp_path, digest, {'s': b})


def test_split_evidence_requires_both_verified_originals(tmp_path):
    data, b, _ = fixture(tmp_path)
    items = [{'original_source': {'source_id': 's', 'source_digest': b['source']['digest'], 'id': c['id']},
              'content_sha256': c['digest']} for c in b['chunks']]
    q = data['questions'][0]
    assert score_original_spans(q, items, {'s': b})['complete10']
    assert not score_original_spans(q, items[:1], {'s': b})['complete10']
    items[0]['content_sha256'] = 'wrong'
    with pytest.raises(ValueError, match='chunk_mismatch'):
        score_original_spans(q, items, {'s': b})


def test_network_permit_exists_only_during_counted_provider_call():
    records = []
    budget = PaidCallBudget(1, lambda name, value: records.append(value))
    def provider():
        assert provider_network.get()
        return 'actual response'
    wrapped = budget.wrap('embedding', provider)
    assert not provider_network.get()
    assert wrapped() == 'actual response'
    assert not provider_network.get()
    with pytest.raises(RuntimeError, match='budget_or_failed'):
        wrapped()
    assert budget.calls == {'embedding': 1, 'rerank': 0}
    assert records[0]['status'] == 'submitted' and records[-1]['status'] == 'completed'


def test_unknown_failure_stops_all_later_calls_and_restores_guard():
    budget = PaidCallBudget(3, lambda *_: None)
    def failed():
        assert provider_network.get()
        raise TimeoutError('unknown billed result')
    with pytest.raises(TimeoutError):
        budget.wrap('rerank', failed)()
    assert not provider_network.get()
    assert budget.record('inspect')['failed']
    with pytest.raises(RuntimeError, match='budget_or_failed'):
        budget.wrap('embedding', lambda: pytest.fail('must not submit'))()
    assert budget.calls == {'embedding': 0, 'rerank': 1}


@pytest.mark.parametrize('wrong_readback', [False, True])
def test_driver_reads_every_top_original_and_preserves_execution_failure(tmp_path, wrong_readback):
    data, b, _ = fixture(tmp_path)
    data['questions'][0]['as_of'] = '2026-09-23'
    data['freeze']['acceptance'] = {'positive_complete_evidence_at10': .9,
        'counterclaim_corrective_evidence_at10': .9, 'known_group_recall_at10': .95}
    originals = [{'original_source': {'source_id': 's', 'source_digest': b['source']['digest'], 'id': c['id']},
        'content_sha256': c['digest'], 'document_id': 'd', 'node_id': c['id'],
        'result_state': 'source_bound_passage', 'truncated': False} for c in b['chunks']]
    receipt = {'candidate_policy': 'needs_window.v4', 'rerank': 'qwen3.7-text-rerank', 'index_digest': 'abc'}
    searches = [{k: v for k, v in item.items() if k != 'content_sha256'} | {'retrieval': receipt}
                for item in originals]
    records, requests = {}, []
    def save(name, value):
        records[name] = json.loads(json.dumps(value))
    class Nav:
        reader = SimpleNamespace(_grant=lambda: ({}, {'research_as_of': '2026-09-23',
            'retrieval_index': {'index_digest': 'abc'}}, None), _after=lambda _: None)
        def navigate(self, request):
            requests.append(request)
            if request['operation'] == 'search':
                return SimpleNamespace(items=searches, model_dump=lambda **_: {'items': searches})
            item = dict(originals[int(request['node_id'])])
            if wrong_readback:
                item['original_source'] = {**item['original_source'], 'source_digest': 'changed'}
            return SimpleNamespace(items=[item])
    budget = PaidCallBudget(1, save)
    if wrong_readback:
        with pytest.raises(ValueError, match='readback_mismatch'):
            run_quality(data, {}, nav=Nav(), bundles={'s': b}, save=save, budget=budget)
        assert records['service-quality']['status'] == 'failed'
        assert not records['service-quality']['rows']
    else:
        result = run_quality(data, {}, nav=Nav(), bundles={'s': b}, save=save, budget=budget)
        assert len(result) == 1 and records['service-quality']['batch_quality_passed']
        assert [r['node_id'] for r in requests if r['operation'] == 'read'] == ['0', '1']
        assert not records['service-quality']['S2_passed']
        assert 'source_id' not in requests[0] and 'document_id' not in requests[0]
