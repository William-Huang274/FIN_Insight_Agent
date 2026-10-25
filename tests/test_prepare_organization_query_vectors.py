import json
import sys

import pytest

from scripts.engineering import prepare_organization_query_vectors as preparation
from test_organization_offline_recall import setup
from retrieval.qwen_api import RetrievalResponse


def configure(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch, True)
    args = ['prepare', '--intake', str(tmp_path/'intake'), '--dataset', str(tmp_path/'questions.json'),
            '--output', str(tmp_path/'prepared'), '--split', 'development']
    monkeypatch.setattr(sys, 'argv', args)
    monkeypatch.setenv('QWEN_API_KEY', 'fixture-only')
    return args


class FakeApi:
    calls = 0
    failure = False
    embedding_model = 'qwen3.7-text-embedding'
    rerank_model = 'unused'

    def __init__(self, *args, **kwargs):
        pass

    def embed(self, texts):
        type(self).calls += 1
        if self.failure:
            raise TimeoutError('fixture unknown provider outcome')
        return RetrievalResponse([[1.] + [0.]*1023], {'total_tokens':5}, 'fixture', self.embedding_model)

    def close(self):
        pass


def test_plan_does_not_open_client_and_execute_reuses_durable_receipt(tmp_path, monkeypatch):
    args = configure(tmp_path, monkeypatch)
    def forbidden(*args, **kwargs):
        raise AssertionError('plan must not create provider')
    monkeypatch.setattr(preparation, 'QwenRetrieval', forbidden)
    preparation.main()
    basis = json.loads((tmp_path/'prepared/TokenBudgetBasis.json').read_text())
    assert basis['limits']['requests_max'] == 1
    FakeApi.calls = 0
    monkeypatch.setattr(preparation, 'QwenRetrieval', FakeApi)
    monkeypatch.setattr(sys, 'argv', [*args, '--execute'])
    preparation.main()
    preparation.main()
    report = json.loads((tmp_path/'prepared/result.json').read_text())
    assert FakeApi.calls == 1 and report['status'] == 'completed'
    assert report['samples'][0]['receipt']['provider_calls'] == 0


def test_unknown_paid_outcome_stays_blocked_after_restart(tmp_path, monkeypatch):
    args = configure(tmp_path, monkeypatch)
    FakeApi.calls = 0
    monkeypatch.setattr(FakeApi, 'failure', True)
    monkeypatch.setattr(preparation, 'QwenRetrieval', FakeApi)
    monkeypatch.setattr(sys, 'argv', [*args, '--execute'])
    with pytest.raises(TimeoutError):
        preparation.main()
    with pytest.raises(RuntimeError):
        preparation.main()
    assert FakeApi.calls == 1
    report = json.loads((tmp_path/'prepared/result.json').read_text())
    assert report['status'] == 'failed' and not report['samples']


def test_changed_snapshot_and_unfrozen_heldout_stop_before_provider(tmp_path, monkeypatch):
    args = configure(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, 'argv', [*args[:-1], 'heldout', '--execute'])
    with pytest.raises(ValueError, match='heldout_requires_frozen'):
        preparation.main()
    path = tmp_path/'questions.json'
    dataset = json.loads(path.read_text()); dataset['library_sha256'] = 'other'
    path.write_text(json.dumps(dataset))
    with pytest.raises(ValueError, match='source_snapshot_mismatch'):
        preparation.main()
