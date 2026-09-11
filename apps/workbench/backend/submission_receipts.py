"""Local BFF response receipts over DiskCache's atomic, persistent add.

Not a run scheduler: Agent Server still creates/executes every run. An uncertain
dispatch is never expired/retried automatically. Deployments on different hosts
must share a qualified transactional receipt store before enabling ingress there.
"""
from hashlib import sha256
import json
from uuid import UUID

from diskcache import Cache
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool


class SubmissionReceipts:
    def __init__(self, app, directory):
        self.app, self.directory = app, str(directory)

    def claim(self, key, fingerprint):
        with Cache(self.directory, eviction_policy='none') as cache:
            if cache.add(key, {'fingerprint': fingerprint, 'status': 'dispatching'}):
                return None
            return cache[key]

    def complete(self, key, fingerprint, status, body):
        with Cache(self.directory, eviction_policy='none') as cache:
            cache[key] = {'fingerprint': fingerprint, 'status': 'received', 'http_status': status, 'body': body}

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in {'POST', 'PUT', 'PATCH'} or not scope['path'].startswith('/api/v1/'):
            return await self.app(scope, receive, send)
        request = Request(scope, receive)
        supplied = request.headers.get('idempotency-key')
        if not supplied:
            return await self.app(scope, receive, send)
        try:
            identifier = str(UUID(supplied))
        except ValueError:
            return await JSONResponse({'detail': '提交凭证格式无效'}, status_code=422)(scope, receive, send)
        # Authentication and browser-write guards must run before receipt replay.
        if request.headers.get('x-workbench-request') != '1':
            return await JSONResponse({'detail': '缺少工作台请求标识'}, status_code=403)(scope, receive, send)
        if 'application/json' not in request.headers.get('content-type', ''):
            return await JSONResponse({'detail': '提交凭证仅支持有界 JSON 请求'}, status_code=422)(scope, receive, send)
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > 2_000_000:
                return await JSONResponse({'detail': '提交内容过大'}, status_code=413)(scope, receive, send)
            chunks.append(chunk)
        body = b''.join(chunks)
        from .authentication import service_owner
        key = sha256(json.dumps([service_owner(), identifier]).encode()).hexdigest()
        fingerprint = sha256(scope['method'].encode()+scope['path'].encode()+scope['query_string']+body).hexdigest()
        prior = await run_in_threadpool(self.claim, key, fingerprint)
        if prior:
            if prior['fingerprint'] != fingerprint:
                response = JSONResponse({'detail': '同一提交凭证不能用于不同内容'}, status_code=422)
            elif prior['status'] == 'received':
                response = Response(prior['body'], status_code=prior['http_status'], media_type='application/json',
                    headers={'Idempotent-Replayed': 'true'})
            else:
                response = JSONResponse({'detail': '此请求已提交或结果尚待核对；请刷新运行记录，不会再次执行。'}, status_code=409)
            return await response(scope, receive, send)
        sent_body = False
        async def replay_body():
            nonlocal sent_body
            if not sent_body:
                sent_body = True
                return {'type': 'http.request', 'body': body, 'more_body': False}
            return await receive()
        start, pieces = None, []
        async def capture(message):
            nonlocal start
            if message['type'] == 'http.response.start':
                start = message
            elif message['type'] == 'http.response.body':
                pieces.append(message.get('body', b''))
                if sum(map(len, pieces)) > 2_000_000:
                    raise RuntimeError('submission_receipt_response_too_large')
                if not message.get('more_body', False):
                    content = b''.join(pieces)
                    # Persist before socket delivery. Lost response replays; an
                    # upstream 5xx retains the original uncertain dispatch lock.
                    if start and start['status'] < 500:
                        await run_in_threadpool(self.complete, key, fingerprint, start['status'], content)
                    if start:
                        await send(start)
                    await send({'type': 'http.response.body', 'body': content})
        await self.app(scope, replay_body, capture)
