import asyncio
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
import pytest

from apps.workbench.backend.api.v1.report_sessions import public_run_usage
from apps.workbench.backend.organization_report_actions import completed_predecessor
from sec_agent.adapters.explicit_run_recovery import (
    issue_recovery_authorization, verified_recovery_authorization,
)


SECRET = 'isolated-recovery-test-secret-' * 2


@pytest.fixture
def recorded(tmp_path):
    tid, rid, cid = [str(uuid4()) for _ in range(3)]
    path = tmp_path / tid / rid / 'model-call-events.jsonl'
    path.parent.mkdir(parents=True)
    rows = [{'event': 'started', 'call_id': cid, 'provider_call_attempted': True},
            {'event': 'outcome', 'call_id': cid, 'status': 'provider_failed',
             'provider_call_attempted': True, 'usage_reported': False}]
    path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n', encoding='utf8')
    events, usage = public_run_usage(tmp_path, tid, rid)
    return SimpleNamespace(root=tmp_path, tid=tid, rid=rid, cid=cid, path=path,
                           events=events, usage=usage, aid=str(uuid4()))


def issue(s, **kwargs):
    return issue_recovery_authorization(s.root, s.tid, s.rid, s.events, s.usage,
        secret=SECRET, authorization_id=s.aid, authorization_ref='user-approved-one-resubmission', **kwargs)


def verify(s, **kwargs):
    return verified_recovery_authorization(s.root, s.tid, s.rid, s.events, s.usage,
                                          secret=SECRET, **kwargs)


def test_explicit_idempotent_permission_preserves_unknown_usage_and_raw_audit(recorded):
    s = recorded
    before = s.path.read_bytes()
    assert verify(s) is None
    value = issue(s)
    assert issue(s) == verify(s) == value
    assert value['unknown_call_ids'] == [s.cid]
    assert s.path.read_bytes() == before
    assert public_run_usage(s.root, s.tid, s.rid) == (s.events, s.usage)
    assert s.usage['unknown_or_pending_requests'] == 1
    assert 'actual_micros' not in value and 'total_tokens' not in value
    s.aid = str(uuid4())
    with pytest.raises(ValueError, match='redefinition'):
        issue(s)


@pytest.mark.parametrize('fault', ['tamper', 'wrong_secret', 'changed_audit', 'new_unknown', 'expired'])
def test_permission_is_bound_to_exact_terminal_failure(recorded, fault):
    s = recorded
    now = datetime.now(timezone.utc)
    issue(s, now=now)
    if fault == 'tamper':
        path = s.root / 'operational-recovery-authorizations' / s.tid / (s.rid + '.json')
        value = json.loads(path.read_text()); value['authorization_ref'] = 'changed'
        path.write_text(json.dumps(value))
    elif fault == 'changed_audit':
        with s.path.open('a') as stream: stream.write('\n')
    elif fault == 'new_unknown':
        s.events.append({**s.events[-1], 'call_id': str(uuid4())})
        s.usage['unknown_or_pending_requests'] = 2
    with pytest.raises(ValueError):
        if fault == 'wrong_secret':
            verified_recovery_authorization(s.root, s.tid, s.rid, s.events, s.usage, secret='wrong' * 10)
        else:
            verify(s, now=now + timedelta(hours=25) if fault == 'expired' else now)


@pytest.mark.parametrize('fault', ['pending', 'partial', 'missing', 'known'])
def test_operator_cannot_authorize_missing_or_active_audit(recorded, fault):
    s = recorded
    if fault == 'pending': s.events = s.events[:1]
    elif fault == 'partial': s.usage['partial_audit'] = True
    elif fault == 'missing': s.usage = None
    else:
        s.events[-1]['total_tokens'] = 0
        s.usage['unknown_or_pending_requests'] = 0
    with pytest.raises(ValueError): issue(s)


def test_wrong_execution_does_not_inherit_permission(recorded):
    s = recorded; issue(s)
    assert verified_recovery_authorization(s.root, str(uuid4()), s.rid,
        s.events, s.usage, secret=SECRET) is None


def test_actual_predecessor_gate_accepts_only_latest_explicit_recovery(recorded, monkeypatch):
    s = recorded
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_RUNTIME_SECRET', SECRET)
    runs = [{'run_id': s.rid, 'status': 'error', 'created_at': '2026-01-01T00:00:00Z'}]
    async def all_runs(tid):
        assert tid == s.tid
        return runs
    service = SimpleNamespace(audit_root=s.root, all_runs=all_runs)
    thread = {'thread_id': s.tid, 'status': 'error'}
    def check(recover=True):
        return asyncio.run(completed_predecessor(service, thread, s.rid, recover=recover))
    with pytest.raises(HTTPException): check()
    issue(s)
    check()  # same function is used by preview and actual internal dispatch
    with pytest.raises(HTTPException): check(False)
    thread['status'] = 'busy'
    with pytest.raises(HTTPException): check()
    thread['status'] = 'error'
    runs.append({'run_id': str(uuid4()), 'status': 'error', 'created_at': '2026-01-02T00:00:00Z'})
    with pytest.raises(HTTPException): check()  # no second successor after a new failure
