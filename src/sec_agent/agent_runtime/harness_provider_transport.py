"""One execution's metered provider transport, not an agent or retry loop.

Use maintained HTTP/SSE parsers. The upstream profile uses this loopback URL
and an opaque local credential; only this host holds the actual provider key.
Raw event payloads are saved before they are forwarded. A complete usage receipt
is durable before the terminal event can release the upstream finish chunk.
"""
import hmac
import json
import os
from urllib.parse import urlsplit

import httpx
from httpx_sse import EventSource
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import StreamingResponse, Response, JSONResponse

from sec_agent.adapters.model_dispatch_store import DispatchBlocked
from .harness_usage import WireUsage


def model_provider_proxy(environment, protocol):
    """Host-only network route; reuse the admitted OpenAI review proxy on migration."""
    return environment.get('FINSIGHT_MODEL_HTTPS_PROXY') or (
        environment.get('FINSIGHT_REVIEW_HTTPS_PROXY') if protocol == 'openai_responses' else None)


class HarnessProviderTransport:
    def __init__(self, host, *, protocol, endpoint, provider_headers, token,
                 client=None, allow_loopback_fixture=False, proxy=None):
        parsed = urlsplit(endpoint)
        if (parsed.username or parsed.password or parsed.query or parsed.fragment
                or not parsed.hostname or not (parsed.scheme == 'https' or
                    (allow_loopback_fixture and parsed.scheme == 'http'
                     and parsed.hostname in {'127.0.0.1', 'localhost', '::1'}))):
            raise ValueError('harness_provider_endpoint_invalid')
        if len(token.encode()) < 32:
            raise ValueError('harness_provider_token_requires_32_bytes')
        WireUsage(protocol)  # validate before serving
        self.host, self.protocol, self.endpoint = host, protocol, endpoint
        self.headers, self.token, self.client = dict(provider_headers), token, client
        self.proxy = proxy
        self.meters = {}
        self._owned_client = None

    def provider_client(self):
        return httpx.AsyncClient(trust_env=False, follow_redirects=False,
            timeout=httpx.Timeout(self.host.basis['timeout_seconds'], connect=15),
            transport=httpx.AsyncHTTPTransport(retries=0, proxy=self.proxy,
                limits=httpx.Limits(max_connections=4, max_keepalive_connections=2,
                                    keepalive_expiry=60)))

    def request_client(self):
        if self.client is not None:
            return self.client
        if self._owned_client is None:
            self._owned_client = self.provider_client()
        return self._owned_client

    async def aclose(self):
        # Pool lifetime is one admitted run, never shared across credentials.
        client, self._owned_client = self._owned_client, None
        if client is not None:
            await client.aclose()

    def meter(self, request_id):
        # Only closed/durably recorded wire observations may settle a bill.
        return self.meters.get(request_id)

    def router(self):
        router = APIRouter()
        path = {'deepseek_messages': '/v1/messages', 'qwen_chat': '/v1/chat/completions',
                'openai_responses': '/v1/responses'}[self.protocol]

        @router.post(path)
        async def forward(request: Request):
            bearer = request.headers.get('authorization', '')
            api_key = request.headers.get('x-api-key', '')
            if not (hmac.compare_digest(bearer, 'Bearer ' + self.token)
                    or hmac.compare_digest(api_key, self.token)):
                raise HTTPException(401, 'harness_provider_unauthorized')
            try:
                body = await request.json()
                if not isinstance(body, dict):
                    raise ValueError()
                request_id = self.host.claim_wire(body)
            except DispatchBlocked as exc:
                raise HTTPException(409, str(exc)) from None
            except (ValueError, TypeError):
                raise HTTPException(422, 'harness_provider_invalid_body') from None
            headers = {'content-type': 'application/json', 'accept': 'text/event-stream', **self.headers}
            for name in ('anthropic-version', 'anthropic-beta'):
                if name in request.headers:
                    headers[name] = request.headers[name]
            # Fail storage admission before constructing/opening a connection.
            stream = (self.host.receipts / (request_id + '.wire-events.jsonl')).open('xb')
            client = self.request_client()
            meter = WireUsage(self.protocol, body['model'])
            response = None

            def record(value):
                stream.write((json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n').encode('utf8'))
                stream.flush()

            def finalize():
                os.fsync(stream.fileno())
                self.host._persist(request_id, 'wire_usage', meter.receipt())
                self.meters[request_id] = meter

            try:
                record({'phase': 'dispatch_started', 'protocol': self.protocol})
                os.fsync(stream.fileno())
                response = await client.send(client.build_request('POST', self.endpoint,
                    json=body, headers=headers), stream=True)
                record({'phase': 'response', 'status': response.status_code})
                if response.status_code != 200:
                    content = await response.aread()
                    record({'error_body': content.decode('utf8', errors='replace')})
                    meter.error = {'http_status': response.status_code}
                    finalize()
                    await response.aclose()
                    stream.close()
                    return Response(content, status_code=response.status_code,
                                    media_type='application/json')
            except BaseException as exc:
                meter.error = {'transport_error_type': type(exc).__name__}
                causes, cause = [], exc.__cause__
                while cause is not None and len(causes) < 5:
                    causes.append(type(cause).__name__)
                    cause = cause.__cause__
                if causes:
                    meter.error['cause_types'] = causes
                try:
                    finalize()
                finally:
                    stream.close()
                    if response is not None:
                        await response.aclose()
                    await self.aclose()
                if isinstance(exc, httpx.TransportError):
                    # Do not expose exception text (it can contain proxy credentials),
                    # invent usage, or retry. The native host still stops this run.
                    return JSONResponse({'error': {'code': 'provider_transport_failed',
                        'type': type(exc).__name__, 'upstream_response_received': response is not None,
                        'usage_known': False, 'retry_performed': False}}, status_code=502)
                raise

            async def events():
                try:
                    async for event in EventSource(response).aiter_sse():
                        record({'event': event.event, 'data': event.data, 'id': event.id})
                        if event.data == '[DONE]':
                            meter.done()
                        elif event.data:
                            value = json.loads(event.data)
                            if not isinstance(value, dict):
                                raise ValueError('harness_provider_event_not_object')
                            meter.observe(value)
                        if meter.terminal:
                            finalize()
                        # Reframe, preserving every SSE data line and event type.
                        payload = 'event: ' + event.event + '\n'
                        payload += ''.join('data: ' + line + '\n' for line in event.data.split('\n'))
                        yield (payload + '\n').encode('utf8')
                        if meter.terminal:
                            return
                    meter.error = {'transport_error_type': 'MissingTerminal'}
                    finalize()
                except BaseException as exc:
                    if not meter.terminal:
                        meter.error = {'transport_error_type': type(exc).__name__}
                        finalize()
                    raise
                finally:
                    stream.close()
                    await response.aclose()
            return StreamingResponse(events(), media_type='text/event-stream')
        return router
