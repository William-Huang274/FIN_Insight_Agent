from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

from scripts.engineering.rerank_receipt_audit import summarize
from sec_agent.adapters.local_records import LocalRecords
from test_scoped_reranking import fixture


def test_missing_receipts_do_not_create_storage(tmp_path):
    missing = tmp_path/'absent'
    result = summarize(missing)
    assert not missing.exists()
    assert result['confirmed_submissions'] == result['submission_status_unknown'] == 0


def test_timeout_is_a_confirmed_attempt_with_unknown_usage_and_no_retry(tmp_path):
    source, rows, calls = fixture(tmp_path)
    def fail(*args, **kwargs):
        calls.append(1)
        raise TimeoutError('unknown response')
    source.api.rerank = fail
    args = dict(scope='test', index_digest='a'*64, check_access=lambda:None)
    with pytest.raises(TimeoutError):
        source.rank('sales', rows, **args)
    path = tmp_path/'records-v1.sqlite'
    before = sha256(path.read_bytes()).hexdigest()
    result = summarize(tmp_path)
    assert result['confirmed_submissions'] == result['failed_usage_unknown'] == 1
    assert result['completed_responses'] == result['submission_status_unknown'] == 0
    assert sha256(path.read_bytes()).hexdigest() == before
    with pytest.raises(RuntimeError, match='no_resubmission'):
        source.rank('sales', rows, **args)
    assert len(calls) == 1


def test_completed_response_survives_denied_product_return_and_cache_reuse(tmp_path):
    source, rows, calls = fixture(tmp_path)
    checks = []
    def check():
        checks.append(1)
        if len(checks) == 3:
            raise PermissionError('revoked')
    args = dict(scope='test', index_digest='a'*64, check_access=check)
    with pytest.raises(PermissionError):
        source.rank('sales', rows, **args)
    assert summarize(tmp_path)['completed_responses'] == 1
    source.rank('sales', rows, **{**args,'check_access':lambda:None})
    assert summarize(tmp_path)['confirmed_submissions'] == len(calls) == 1


def test_crashed_started_record_is_not_assumed_unsent_or_successful(tmp_path):
    with LocalRecords(tmp_path) as records:
        for status in ('started', 'not_submitted'):
            records[status] = {'status':status, 'identity':{'format':'scoped-rerank.v1'}}
    result = summarize(tmp_path)
    assert result['submission_status_unknown'] == result['not_submitted'] == 1
    assert result['confirmed_submissions'] == result['completed_responses'] == 0


def test_unrecognized_status_does_not_report_zero_calls(tmp_path):
    with LocalRecords(tmp_path) as records:
        records['unrecognized'] = {'status':'future_status', 'identity':{'format':'scoped-rerank.v1'}}
    with pytest.raises(ValueError, match='unknown_status'):
        summarize(tmp_path)


def test_driver_failure_summary_uses_receipts_even_without_a_rank_return(tmp_path, monkeypatch):
    from scripts.engineering import qualify_unit_rerank as driver
    from retrieval import qwen_api
    from retrieval.scoped_reranking import scoring_documents
    source, rows, calls = fixture(tmp_path/'fixture')
    def fail(*args, **kwargs):
        calls.append(1)
        raise TimeoutError('simulated transport failure')
    source.api.rerank = fail
    source.api.close = lambda:None
    monkeypatch.setattr(qwen_api, 'QwenRetrieval', lambda *a, **k:source.api)
    monkeypatch.setenv('QWEN_API_KEY', 'fixture-not-a-real-key')
    monkeypatch.setattr(driver.psutil, 'virtual_memory', lambda:SimpleNamespace(available=2*2**30))
    job = {'id':'q', 'query':'sales', 'candidates':rows,
           'provider_input_sha256':[sha256(t.encode()).hexdigest() for t in scoring_documents(rows)]}
    (tmp_path/'q.input.json').write_text(json.dumps(job), encoding='utf8')
    plan = {'inputs':{}, 'code_sha256':{}, 'index_digest':'a'*64,
            'jobs':[{'id':'q', 'input_sha256':driver.digest(tmp_path/'q.input.json')}]}
    (tmp_path/'plan.json').write_text(json.dumps(plan), encoding='utf8')
    with pytest.raises(TimeoutError):
        driver.run(tmp_path)
    result = json.loads((tmp_path/'result.json').read_bytes())
    assert result['status'] == 'stopped' and result['samples'] == []
    assert result['provider_calls'] == 0
    assert result['provider_receipts']['confirmed_submissions'] == 1
    assert result['provider_receipts']['failed_usage_unknown'] == 1
    assert len(calls) == 1
