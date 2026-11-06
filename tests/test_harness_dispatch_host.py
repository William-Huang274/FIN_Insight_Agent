from copy import deepcopy
from dataclasses import dataclass
import json
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from sec_agent.adapters.model_dispatch_store import DispatchBlocked
from sec_agent.agent_runtime.harness_dispatch_host import HarnessDispatchHost, dispatch_router
from sec_agent.agent_runtime.harness_usage import WireUsage


@dataclass(frozen=True)
class Prices:
    version: str = 'synthetic'
    model: str = 'fixture-model'
    currency: str = 'USD'
    input_miss: int = 1_000_000
    input_hit: int = 100_000
    output: int = 2_000_000


class Store:
    """Protocol fixture, not evidence of PostgreSQL deployment."""
    def __init__(self):
        self.rows = {}

    def require_runtime_role(self):
        pass

    def lookup(self, owner, budget, key):
        return self.rows.get((owner, budget, key))

    def reserve(self, owner, budget, key, fingerprint, reserved, basis, **kw):
        prior = self.lookup(owner, budget, key)
        if prior:
            if prior['fingerprint'] != fingerprint or prior['status'] != 'received':
                raise DispatchBlocked('prior_dispatch_unresolved_no_retry')
            return prior
        for (o, b, _), row in self.rows.items():
            if (o, b) == (owner, budget) and row['basis']['harness_execution_scope'] == kw['execution_scope']:
                if row['status'] != 'received' or row['actual'] is None or row['response']['stop_required']:
                    raise DispatchBlocked('harness_execution_has_unresolved_or_failed_call')
        row = dict(status='dispatched', call_id=uuid4(), fingerprint=fingerprint, basis=basis)
        self.rows[(owner, budget, key)] = row
        return row

    def received(self, owner, budget, key, response, actual):
        row = self.lookup(owner, budget, key)
        assert row['status'] == 'dispatched'
        row.update(status='received', response=deepcopy(response), actual=actual)


@pytest.fixture
def setup(tmp_path):
    grant = dict(execution_id=str(uuid4()), authorized_run_id=str(uuid4()), manifest_digest='sha256:'+'a'*64)
    meters = {}
    basis = dict(node_role='lead', node_purpose='Research and checkpoint existing evidence',
        input_scale='Known saved evidence and current research task', required_outputs=['research progress or checkpoint'],
        schema_burden='Public harness tool protocol', materiality_quality_risk='Preserve attribution and current intent',
        comparable_run_evidence='Offline fixture only', reasoning_profile='agentic_message_history_thinking_enabled',
        max_input_characters=1_000_000, max_output_tokens=None, timeout_seconds=600,
        max_transport_attempts=1, retry_policy='none', truncation_stop_behavior='fail_closed_no_partial_promotion',
        input_ceiling_behavior='fail_before_transport')
    args = dict(store=Store(), owner='alice', budget='budget', execution_id=grant['execution_id'],
        run_id=grant['authorized_run_id'], manifest_digest=grant['manifest_digest'], authority=lambda: dict(grant),
        prices=Prices(), basis=basis, provider='fixture-provider', reservation_micros=1000,
        reservation_basis='Fixture upper cost bound', receipts=tmp_path, wire_usage=meters.get)
    host = HarnessDispatchHost(**args)
    request = dict(provider='fixture-provider', model='fixture-model', maxTokens=32000,
                   messages=[{'role':'user','content':'synthetic study'}])
    return host, args, grant, meters, request


def meter():
    m = WireUsage('qwen_chat')
    m.observe({'choices':[{'finish_reason':'stop'}], 'usage':{
        'prompt_tokens':100, 'completion_tokens':20, 'prompt_tokens_details':{'cached_tokens':50}}})
    m.done()
    return m


def finish(reason='stop'):
    return [{'type':'text-delta','text':'unchanged output'}, {'type':'finish','reason':{'kind':reason}}]


def test_dispatch_lane_is_host_policy_not_model_argument(setup):
    host, args, grant, meters, request = setup
    host = HarnessDispatchHost(**args, dispatch_lane='author')
    request['harness_dispatch_lane'] = 'pretend-child'
    host.reserve(str(uuid4()), request)
    row = next(iter(args['store'].rows.values()))
    assert row['basis']['harness_dispatch_lane'] == 'author'


def test_real_router_auth_reserve_wire_settle_and_idempotent_ack(setup):
    host, args, grant, meters, request = setup
    public = []
    host.public_sink = public.append
    app = FastAPI()
    app.include_router(dispatch_router(host, token='x'*32))
    client = TestClient(app)
    rid = str(uuid4())
    body = dict(requestId=rid, request=request)
    assert client.post('/calls/reserve', json=body).status_code == 401
    assert not args['store'].rows
    headers = {'Authorization':'Bearer '+'x'*32}
    assert client.post('/calls/reserve', json=body, headers=headers).json()['status'] == 'reserved'
    meters[rid] = meter()
    result = dict(requestId=rid, chunks=finish(), terminal='stop', stopRequired=False)
    assert client.post('/calls/settle', json=result, headers=headers).json() == {'status':'saved','stopRequired':False}
    assert client.post('/calls/settle', json=result, headers=headers).status_code == 200
    outcomes = [event for event in public if event['event'] == 'outcome']
    assert len(outcomes) == 1
    assert outcomes[0]['input_tokens'] == 100 and outcomes[0]['cache_hit_tokens'] == 50
    row = next(iter(args['store'].rows.values()))
    assert row['actual'] == 95
    assert json.loads(open(row['response']['receipt']['path'], encoding='utf8').read())['chunks'] == finish()
    assert client.post('/calls/reserve', json=body, headers=headers).status_code == 409
    result['chunks'][0]['text'] = 'changed'
    assert client.post('/calls/settle', json=result, headers=headers).status_code == 409


@pytest.mark.parametrize('failure', ['usage_missing','truncated','unknown','bad_terminal','wire_truncated'])
def test_failure_survives_host_restart_without_releasing_cost_or_resending(setup, failure):
    host, args, grant, meters, request = setup
    rid = str(uuid4())
    host.reserve(rid, request)
    if failure != 'usage_missing':
        meters[rid] = meter()
    if failure == 'wire_truncated':
        meters[rid].finish_reason = 'length'
    reason = 'max-tokens' if failure == 'truncated' else 'stop'
    chunks = finish(reason)
    if failure == 'bad_terminal':
        chunks.pop()
    result = host.settle(rid, chunks, reason, unknown=failure == 'unknown')
    assert result['stopRequired']
    row = next(iter(args['store'].rows.values()))
    if failure == 'usage_missing':
        assert row['actual'] is None
    else:
        assert row['actual'] == 95  # Still preserve known spend on failure.
    restored = HarnessDispatchHost(**args)
    with pytest.raises(DispatchBlocked, match='unresolved_or_failed'):
        restored.reserve(str(uuid4()), request)


def test_revoke_before_next_dispatch_but_receive_inflight_output(setup):
    host, args, grant, meters, request = setup
    rid = str(uuid4())
    host.reserve(rid, request)
    meters[rid] = meter()
    grant['authorized_run_id'] = str(uuid4())
    assert not host.settle(rid, finish(), 'stop')['stopRequired']
    with pytest.raises(DispatchBlocked, match='java_run_binding'):
        host.reserve(str(uuid4()), request)


def test_storage_failure_stops_before_reserve_and_does_not_claim_settlement(setup, monkeypatch):
    host, args, grant, meters, request = setup
    rid = str(uuid4())
    original = host._persist
    def fail(*a):
        raise OSError('disk full')
    monkeypatch.setattr(host, '_persist', fail)
    with pytest.raises(OSError): host.reserve(rid, request)
    assert not args['store'].rows
    monkeypatch.setattr(host, '_persist', original)
    host.reserve(rid, request)
    monkeypatch.setattr(host, '_persist', fail)
    with pytest.raises(OSError): host.settle(rid, finish(), 'stop')
    assert next(iter(args['store'].rows.values()))['status'] == 'dispatched'


def test_many_calls_and_compactions_have_no_two_summary_or_small_call_limit(setup):
    host, args, grant, meters, request = setup
    for i in range(12):
        rid = str(uuid4())
        host.reserve(rid, {**request, 'messages':[{'role':'user','content':f'checkpoint {i}'}]})
        meters[rid] = meter()
        assert not host.settle(rid, finish(), 'stop')['stopRequired']
    assert len(args['store'].rows) == 12


def test_declared_model_and_limits_cannot_be_changed_by_request(setup):
    host, args, grant, meters, request = setup
    for bad in [{**request, 'model':'unpriced'}, {**request, 'messages':['x'*1_000_001]}]:
        with pytest.raises(DispatchBlocked): host.reserve(str(uuid4()), bad)
    assert not args['store'].rows


def test_host_capacity_above_legacy_ceiling_still_enforces_admission(setup):
    _, args, _, _, request = setup
    args['basis'] = {**args['basis'], 'max_input_characters': 8_000_000, 'max_output_tokens': 65_536}
    host = HarnessDispatchHost(**args)
    with pytest.raises(DispatchBlocked, match='output_basis'):
        host.reserve(str(uuid4()), {**request, 'maxTokens': 65_537})
    with pytest.raises(DispatchBlocked, match='input_basis'):
        host.reserve(str(uuid4()), {**request, 'maxTokens': 65_536, 'messages': ['x'*8_000_001]})
    assert not args['store'].rows
    assert host.reserve(str(uuid4()), {**request, 'maxTokens': 65_536,
        'messages': ['x'*1_000_001]})['status'] == 'reserved'
