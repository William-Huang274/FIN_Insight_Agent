import json
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sec_agent.adapters.model_dispatch_store import DispatchBlocked
from sec_agent.agent_runtime.harness_provider_transport import HarnessProviderTransport
from test_harness_dispatch_host import setup, finish


def wire_fixture(setup, protocol='qwen_chat', failure=None):
    host, args, grant, meters, request = setup
    calls = []
    def respond(req):
        calls.append(req)
        assert req.headers['authorization'] == 'Bearer provider-secret'
        if failure == 'connect':
            raise httpx.ConnectError('sensitive proxy detail must not escape')
        if failure == 'http':
            return httpx.Response(402, json={'error': 'fixture insufficient balance'})
        if protocol == 'qwen_chat':
            events = [{'choices': [{'finish_reason': 'stop'}], 'usage': {
                'prompt_tokens': 100, 'completion_tokens': 20,
                'prompt_tokens_details': {'cached_tokens': 50}}}, '[DONE]']
        elif protocol == 'openai_responses':
            events = [{'type':'response.created','response':{'id':'r'}},
                {'type':'response.completed','response':{'id':'r','status':'completed','usage':{
                    'input_tokens':100,'input_tokens_details':{'cached_tokens':50},'output_tokens':20}}}]
        else:
            events = [{'type': 'message_start', 'message': {'id': 'fixture-response', 'usage': {
                'input_tokens': 50, 'cache_read_input_tokens': 50}}},
                {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 20}},
                {'type': 'message_stop'}]
        if failure == 'missing_terminal':
            events.pop()
        if failure == 'missing_usage':
            for e in events:
                if isinstance(e, dict):
                    e.pop('usage', None)
                    e.get('response',{}).pop('usage',None)
        data = ''.join('data: ' + (e if isinstance(e, str) else json.dumps(e)) + '\r\n\r\n' for e in events)
        return httpx.Response(200, content=data, headers={'Content-Type': 'text/event-stream'})
    transport = HarnessProviderTransport(host, protocol=protocol, endpoint='https://provider.invalid/test',
        provider_headers={'authorization': 'Bearer provider-secret'}, token='x'*32,
        client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    host.wire_usage = transport.meter
    app = FastAPI()
    app.include_router(transport.router())
    client = TestClient(app)
    path = {'deepseek_messages':'/v1/messages','qwen_chat':'/v1/chat/completions','openai_responses':'/v1/responses'}[protocol]
    headers = {'Authorization': 'Bearer ' + 'x'*32}
    body = {'model': request['model'], 'max_tokens': request['maxTokens'], 'stream': True,
            'messages': [{'role': 'user', 'content': 'fixed evidence'}]}
    if protocol == 'openai_responses':
        body['max_output_tokens']=body.pop('max_tokens')
        body['input']=body.pop('messages')
    return host, request, client, path, headers, body, calls, transport


@pytest.mark.parametrize('protocol', ['qwen_chat', 'deepseek_messages','openai_responses'])
def test_protocol_wire_usage_bound_to_reserved_request_and_not_retried(setup, protocol):
    host, request, client, path, headers, body, calls, transport = wire_fixture(setup, protocol)
    assert client.post(path, json=body).status_code == 401
    assert client.post(path, json=body, headers=headers).status_code == 409
    rid = str(uuid4())
    host.reserve(rid, request)
    assert client.post(path, json=body, headers=headers).status_code == 200
    assert transport.meter(rid).reported().cost_micros(host.prices) == 95
    assert client.post(path, json=body, headers=headers).status_code == 409
    assert len(calls) == 1
    assert host.settle(rid, finish(), 'stop')['stopRequired'] is False
    assert list(host.receipts.glob(rid + '.wire_usage.*.json'))
    wire = json.loads(next(host.receipts.glob(rid + '.wire_request.*.json')).read_text())
    assert wire == body
    assert 'provider-secret' not in ''.join(p.read_text() for p in host.receipts.iterdir())


@pytest.mark.parametrize('failure', ['http', 'missing_terminal', 'missing_usage'])
@pytest.mark.parametrize('protocol',['qwen_chat','openai_responses'])
def test_failure_records_unknown_and_stops_next_call(setup, failure,protocol):
    host, request, client, path, headers, body, calls, transport = wire_fixture(setup, protocol, failure=failure)
    rid = str(uuid4())
    host.reserve(rid, request)
    response = client.post(path, json=body, headers=headers)
    assert response.status_code == (402 if failure == 'http' else 200)
    assert host.settle(rid, finish(), 'stop')['stopRequired'] is True
    with pytest.raises(DispatchBlocked):
        host.reserve(str(uuid4()), request)
    assert len(calls) == 1


def test_revocation_and_changed_model_prevent_provider_io(setup):
    host, request, client, path, headers, body, calls, transport = wire_fixture(setup)
    host.reserve(str(uuid4()), request)
    assert client.post(path, json={**body, 'model': 'another'}, headers=headers).status_code == 409
    setup[2]['authorized_run_id'] = str(uuid4())
    assert client.post(path, json=body, headers=headers).status_code == 409
    assert not calls


def test_adapter_cannot_silently_reduce_output_to_one_token(setup):
    host, request, client, path, headers, body, calls, transport = wire_fixture(setup)
    rid = str(uuid4())
    host.reserve(rid, request)
    assert client.post(path, json={**body, 'max_tokens': 1}, headers=headers).status_code == 409
    rejected = json.loads(next(host.receipts.glob(rid + '.wire_rejected.*')).read_text())
    assert rejected['body']['max_tokens'] == 1
    assert not calls


def test_claim_receipt_prevents_replay_after_host_reconstruction(setup):
    host, request, client, path, headers, body, calls, transport = wire_fixture(setup)
    rid = str(uuid4())
    host.reserve(rid, request)
    host.claim_wire(body)
    host._wire_pending = (rid, request)  # even an erroneous re-arm cannot resend
    with pytest.raises(DispatchBlocked, match='already_dispatched'):
        host.claim_wire(body)


def test_connection_failure_is_not_upstream_500_and_keeps_unknown_hold(setup):
    host, request, client, path, headers, body, calls, transport = wire_fixture(setup, 'openai_responses', 'connect')
    rid = str(uuid4())
    host.reserve(rid, request)
    response = client.post(path, json=body, headers=headers)
    assert response.status_code == 502
    assert response.json()['error'] == {'code': 'provider_transport_failed', 'type': 'ConnectError',
        'upstream_response_received': False, 'usage_known': False, 'retry_performed': False}
    assert transport.meter(rid).receipt()['usage'] is None
    assert host.settle(rid, finish(), 'error')['stopRequired'] is True
    assert len(calls) == 1
    assert 'sensitive proxy' not in response.text


def test_native_proxy_route_preserves_migrated_openai_configuration(setup, monkeypatch):
    from sec_agent.agent_runtime.harness_provider_transport import model_provider_proxy
    legacy = {'FINSIGHT_REVIEW_HTTPS_PROXY': 'http://proxy.invalid:8080'}
    assert model_provider_proxy(legacy, 'openai_responses') == legacy['FINSIGHT_REVIEW_HTTPS_PROXY']
    assert model_provider_proxy(legacy, 'deepseek_messages') is None
    configured = {**legacy, 'FINSIGHT_MODEL_HTTPS_PROXY': 'http://other.invalid:8080'}
    assert model_provider_proxy(configured, 'openai_responses') == configured['FINSIGHT_MODEL_HTTPS_PROXY']
    seen = {}
    monkeypatch.setattr(httpx, 'AsyncHTTPTransport', lambda **kw: seen.update(kw) or object())
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: seen.update(kw) or object())
    transport = HarnessProviderTransport(setup[0], protocol='openai_responses', endpoint='https://provider.invalid/test',
        provider_headers={}, token='x'*32, proxy=model_provider_proxy(legacy, 'openai_responses'))
    transport.provider_client()
    assert seen['proxy'] == legacy['FINSIGHT_REVIEW_HTTPS_PROXY'] and seen['retries'] == 0
    assert seen['trust_env'] is False and seen['follow_redirects'] is False


def test_disk_failure_prevents_transport(setup, monkeypatch):
    host, request, client, path, headers, body, calls, transport = wire_fixture(setup)
    host.reserve(str(uuid4()), request)
    monkeypatch.setattr(host, '_persist', lambda *a: (_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError):
        client.post(path, json=body, headers=headers)
    assert not calls
