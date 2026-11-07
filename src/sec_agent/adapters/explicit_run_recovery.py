"""Host-issued permission to continue after a terminal, unpriced request.

This is not a usage settlement or retry loop. Original receipts and financial
holds remain unchanged. The normal command path still checks the latest run,
current access, checkpoint, Java admission and the next request's budget.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
from uuid import UUID


KIND = 'explicit_unknown_usage_recovery.v1'
PREPARATION_KIND = 'verified_preparation_failure_recovery.v1'


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf8')


def _paths(root, thread, run):
    root = Path(root).resolve()
    thread, run = str(UUID(str(thread))), str(UUID(str(run)))
    audit = (root / thread / run / 'model-call-events.jsonl').resolve()
    permit = (root / 'operational-recovery-authorizations' / thread / (run + '.json')).resolve()
    if not audit.is_relative_to(root) or not permit.is_relative_to(root):
        raise ValueError('recovery_path_outside_audit_root')
    return audit, permit


def _unknown_failures(events, usage):
    if not usage or usage.get('partial_audit') or not usage.get('recorded_requests'):
        raise ValueError('recovery_requires_complete_audit')
    rows = [e for e in events if e.get('kind') == 'model' and e.get('call_id')]
    ids = {e['call_id'] for e in rows}
    outcomes = {e['call_id']: e for e in rows if e.get('event') == 'outcome'}
    unknown = []
    for call_id in ids:
        outcome = outcomes.get(call_id, {})
        if outcome.get('provider_call_attempted') is False or type(outcome.get('total_tokens')) is int:
            continue
        if outcome.get('status') != 'provider_failed' or outcome.get('usage_reported') is not False:
            raise ValueError('recovery_cannot_authorize_pending_request')
        unknown.append(str(UUID(call_id)))
    if not unknown or len(unknown) != usage.get('unknown_or_pending_requests'):
        raise ValueError('recovery_unknown_request_set_mismatch')
    return sorted(unknown)


def _signature(value, secret):
    if not isinstance(secret, str) or len(secret.encode()) < 32:
        raise ValueError('recovery_host_secret_required')
    return hmac.new(secret.encode(), KIND.encode() + b'\0' + _bytes(value), sha256).hexdigest()


def issue_recovery_authorization(root, thread, run, events, usage, *, secret,
                                 authorization_id, authorization_ref, now=None):
    """Operator CLI only; never exposed as a model or browser tool."""
    if not isinstance(authorization_ref, str) or not authorization_ref.strip():
        raise ValueError('recovery_authorization_reference_required')
    audit, path = _paths(root, thread, run)
    scope = {'kind': KIND, 'thread_id': str(UUID(str(thread))), 'previous_run_id': str(UUID(str(run))),
        'unknown_call_ids': _unknown_failures(events, usage),
        'audit_sha256': sha256(audit.read_bytes()).hexdigest(),
        'authorization_id': str(UUID(str(authorization_id))), 'authorization_ref': authorization_ref}
    if path.exists():
        existing = json.loads(path.read_text(encoding='utf8'))
        verified_recovery_authorization(root, thread, run, events, usage, secret=secret, now=now)
        if any(existing.get(k) != v for k, v in scope.items()):
            raise ValueError('recovery_authorization_redefinition_forbidden')
        return existing
    now = now or datetime.now(timezone.utc)
    value = {**scope, 'issued_at': now.isoformat(), 'expires_at': (now + timedelta(hours=24)).isoformat()}
    value['signature'] = _signature(value, secret)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(_bytes(value)); stream.flush(); os.fsync(stream.fileno())
    return value


def verified_recovery_authorization(root, thread, run, events, usage, *, secret, now=None):
    signed = verified_permit(root, thread, run, secret=secret, now=now)
    if signed and signed['unknown_call_ids'] != _unknown_failures(events, usage):
        raise ValueError('recovery_authorization_scope_changed')
    return signed


def verified_permit(root, thread, run, *, secret, now=None):
    audit, path = _paths(root, thread, run)
    if not path.is_file():
        return None
    signed = json.loads(path.read_text(encoding='utf8'))
    value = dict(signed); signature = value.pop('signature', '')
    if not isinstance(signature, str) or not hmac.compare_digest(signature, _signature(value, secret)):
        raise ValueError('recovery_authorization_signature_invalid')
    if (value.get('kind') != KIND or value.get('thread_id') != str(UUID(str(thread)))
            or value.get('previous_run_id') != str(UUID(str(run)))
            or value.get('audit_sha256') != sha256(audit.read_bytes()).hexdigest()):
        raise ValueError('recovery_authorization_scope_changed')
    now = now or datetime.now(timezone.utc)
    issued = datetime.fromisoformat(value['issued_at']); expires = datetime.fromisoformat(value['expires_at'])
    if not issued <= now <= expires or expires - issued > timedelta(hours=24):
        raise ValueError('recovery_authorization_expired_or_invalid')
    return signed


def _preparation_audit_digest(audit):
    if not audit.exists():
        return None
    data = audit.read_bytes()
    rows = [json.loads(line) for line in data.decode('utf8').splitlines() if line.strip()]
    if not rows or any(r.get('provider_call_attempted') is not False
                       or r.get('event') != 'outcome'
                       or r.get('status') != 'saved_response_replayed' for r in rows):
        raise ValueError('preparation_recovery_cannot_replace_model_audit')
    return sha256(data).hexdigest()


def issue_preparation_recovery(root, thread, run, *, store, owner, budget,
                               terminal_run, preparation_evidence, secret,
                               authorization_ref, now=None):
    """Privileged operations only: attest a checked failure before dispatch.

    Missing model audit alone is NEVER evidence of no dispatch. The operator
    must locate the preparation failure and check the authoritative dispatch
    ledger. This receipt changes admission only, not usage or run outcomes.
    """
    audit, base = _paths(root, thread, run)
    path = base.with_suffix('.preparation.json')
    tid, rid = str(UUID(str(thread))), str(UUID(str(run)))
    if (terminal_run.get('run_id') != rid or terminal_run.get('status') not in {'error','interrupted'}
            or not authorization_ref or not preparation_evidence):
        raise ValueError('preparation_recovery_requires_terminal_failure_evidence')
    replay_digest = _preparation_audit_digest(audit)
    scope = tid + ':' + rid
    with store.connection() as db:
        count = db.execute('''SELECT COUNT(*) AS count FROM fin_model_dispatch
            WHERE owner_id=%s AND budget_id=%s AND
            (basis->>'harness_execution_scope'=%s OR call_key LIKE %s)''',
            (owner, budget, scope, scope + ':%')).fetchone()['count']
    if count != 0:
        raise ValueError('preparation_recovery_dispatch_already_recorded')
    value = {'kind': PREPARATION_KIND, 'thread_id': tid, 'previous_run_id': rid,
             'owner_id': owner, 'budget_id': budget, 'dispatch_rows': count,
             'terminal_run': terminal_run, 'preparation_evidence': preparation_evidence,
             'authorization_ref': authorization_ref}
    if replay_digest:
        value['replayed_response_audit_sha256'] = replay_digest
    if path.exists():
        prior = verified_preparation_recovery(root, tid, rid, secret=secret, now=now)
        if not prior or any(prior.get(k) != v for k, v in value.items()):
            raise ValueError('preparation_recovery_redefinition_forbidden')
        return prior
    now = now or datetime.now(timezone.utc)
    value.update(issued_at=now.isoformat(), expires_at=(now + timedelta(hours=24)).isoformat())
    value['signature'] = _signature(value, secret)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(_bytes(value)); stream.flush(); os.fsync(stream.fileno())
    return value


def verified_preparation_recovery(root, thread, run, *, secret, now=None):
    audit, base = _paths(root, thread, run)
    path = base.with_suffix('.preparation.json')
    if not path.exists():
        return None
    signed = json.loads(path.read_text(encoding='utf8'))
    value = dict(signed); signature = value.pop('signature', '')
    if not isinstance(signature, str) or not hmac.compare_digest(signature, _signature(value, secret)):
        raise ValueError('preparation_recovery_signature_invalid')
    if (_preparation_audit_digest(audit) != value.get('replayed_response_audit_sha256')
            or value.get('kind') != PREPARATION_KIND
            or value.get('thread_id') != str(UUID(str(thread)))
            or value.get('previous_run_id') != str(UUID(str(run)))
            or value.get('dispatch_rows') != 0):
        raise ValueError('preparation_recovery_scope_changed')
    now = now or datetime.now(timezone.utc)
    issued = datetime.fromisoformat(value['issued_at']); expires = datetime.fromisoformat(value['expires_at'])
    if not issued <= now <= expires or expires - issued > timedelta(hours=24):
        raise ValueError('preparation_recovery_expired')
    return signed
