import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sec_agent.adapters.explicit_run_recovery import (
    issue_preparation_recovery, verified_preparation_recovery,
)
from apps.workbench.backend.organization_report_actions import completed_predecessor

SECRET = 'preparation-test-secret-' * 3


class Store:
    count = 0
    @contextmanager
    def connection(self):
        yield self
    def execute(self, sql, args):
        assert 'harness_execution_scope' in sql and len(args) == 4
        return self
    def fetchone(self):
        return {'count': self.count}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_RUNTIME_SECRET', SECRET)
    tid, rid = str(uuid4()), str(uuid4())
    run = {'run_id': rid, 'status': 'error', 'created_at': '2026-01-01T00:00:00Z'}
    store = Store()
    def issue(**kw):
        return issue_preparation_recovery(tmp_path, tid, rid, store=store,
            owner='owner', budget='budget', terminal_run=run,
            preparation_evidence={'phase': 'host_construction', 'error': 'invalid_config'},
            secret=SECRET, authorization_ref='operator-reviewed-no-dispatch', **kw)
    runs = [run]
    async def all_runs(_): return runs
    svc = SimpleNamespace(audit_root=tmp_path, all_runs=all_runs)
    def check():
        return asyncio.run(completed_predecessor(svc, {'thread_id': tid, 'status': 'error'}, rid, recover=True))
    return SimpleNamespace(root=tmp_path, tid=tid, rid=rid, run=run, runs=runs, store=store, issue=issue, check=check)


def test_no_audit_requires_explicit_evidence_and_preserves_failure(setup):
    s = setup
    with pytest.raises(HTTPException): s.check()
    proof = s.issue()
    assert s.issue() == proof
    s.check()
    assert s.run['status'] == 'error'
    assert not (s.root / s.tid / s.rid / 'model-call-events.jsonl').exists()
    assert 'total_tokens' not in proof and 'actual_micros' not in proof
    s.runs.append({'run_id': str(uuid4()), 'status': 'success', 'created_at': '2026-01-02T00:00:00Z'})
    with pytest.raises(HTTPException): s.check()


@pytest.mark.parametrize('fault', ['dispatch', 'active', 'audit'])
def test_issuance_rejects_uncertain_execution(setup, fault):
    s = setup
    if fault == 'dispatch': s.store.count = 1
    elif fault == 'active': s.run['status'] = 'running'
    else:
        path = s.root / s.tid / s.rid / 'model-call-events.jsonl'
        path.parent.mkdir(parents=True); path.write_text('broken')
    with pytest.raises(ValueError): s.issue()


@pytest.mark.parametrize('fault', ['tamper', 'audit', 'expired'])
def test_proof_cannot_hide_new_or_changed_information(setup, fault):
    s = setup; now = datetime.now(timezone.utc); s.issue(now=now)
    if fault == 'tamper':
        path = s.root / 'operational-recovery-authorizations' / s.tid / (s.rid + '.preparation.json')
        data = json.loads(path.read_text()); data['dispatch_rows'] = 2; path.write_text(json.dumps(data))
    elif fault == 'audit':
        path = s.root / s.tid / s.rid / 'model-call-events.jsonl'
        path.parent.mkdir(parents=True); path.write_text('{}')
    with pytest.raises(ValueError):
        verified_preparation_recovery(s.root, s.tid, s.rid, secret=SECRET,
            now=now + timedelta(days=2) if fault == 'expired' else now)
