"""Opt-in, single-host authenticated bridge; browser identity remains in the BFF.

No generic proxy: signed delegations bind the exact method, path/query and bytes.
The receiving service must still check current resource ownership.
"""
import hashlib
import json
import os
import re
import time
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse, Response

INTERNAL = '/api/v1/internal-research/'
_PUBLIC = re.compile(r'(tasks|tasks/[0-9a-f-]{36}(?:/(?:prepare|start|reconcile))?)$')
_SPACES = re.compile(r'workspaces(?:/(?:organizations|spaces|join)|/organizations/[0-9a-f-]{36}/(?:members|invites|remove-member)|/spaces/[0-9a-f-]{36}/(?:members|resources)|/resources/[0-9a-f-]{36}/revoke)?$')


def resource_spaces_enabled():
    return (os.environ.get('FINSIGHT_RESOURCE_SPACES_ENABLED') == '1'
            and os.environ.get('FINSIGHT_AUTH_MODE') == 'oidc_product'
            and bool(os.environ.get('FINSIGHT_BUSINESS_API_URL')))


async def space_business_request(owner, method, suffix, body=None):
    """Server-owned bindings never pass through the generic browser gateway."""
    if not resource_spaces_enabled() or owner == 'local-pilot':
        raise HTTPException(503, '组织资料空间需要独立登录和已配置的业务服务')
    base = local_url(os.environ['FINSIGHT_BUSINESS_API_URL'])
    path = '/v1/workspaces/' + suffix
    data = b'' if body is None else json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15, connect=3), trust_env=False,
                transport=httpx.AsyncHTTPTransport(retries=0), follow_redirects=False) as client:
            response = await client.request(method, base + path, content=data,
                headers={'Authorization': 'Bearer ' + delegate(owner, method, path, data), 'Content-Type': 'application/json'})
        value = response.json()
        if not response.is_success:
            raise HTTPException(response.status_code, value.get('detail', '空间授权未通过'))
        return value
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, '空间服务不可用，请保留原发布标识并重新读取结果') from None


def secret():
    value = os.environ.get('FINSIGHT_BUSINESS_SHARED_SECRET', '')
    if len(value.encode()) < 32:
        raise ValueError('business_delegation_secret_requires_32_bytes')
    return value


def local_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost'}
            or parsed.username or parsed.password or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment):
        raise ValueError('business_bridge_requires_loopback_base_url')
    return value.rstrip('/')


def delegate(owner, method, path, body, *, operation_id='', audience='finsight-java', issuer='finsight-workbench'):
    import jwt
    now = int(time.time())
    return jwt.encode({'iss': issuer, 'aud': audience, 'sub': owner, 'iat': now, 'exp': now + 60,
        'method': method, 'path': path, 'operation_id': operation_id, 'body_sha256': hashlib.sha256(body).hexdigest()}, secret(), algorithm='HS256')


class InternalResearchIdentity:
    """Only private intake routes accept Java's audience; normal APIs do not."""
    def __init__(self, app, service):
        self.app = app
        self.service = service
        self.key = secret()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope['path'].startswith(INTERNAL):
            return await self.app(scope, receive, send)
        import jwt
        from .authentication import _request_owner
        try:
            request = Request(scope, receive)
            header = request.headers.get('authorization', '')
            if not header.startswith('Bearer ') or len(header) > 16384:
                raise ValueError('missing_delegation')
            claims = jwt.decode(header[7:], self.key, algorithms=['HS256'], issuer='finsight-java',
                audience='finsight-python-intake', options={'require': ['iss', 'aud', 'sub', 'iat', 'exp', 'method', 'path', 'body_sha256']})
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 65536:
                    raise ValueError('intake_body_too_large')
            path = scope['path'] + ('?' + scope['query_string'].decode('ascii') if scope.get('query_string') else '')
            if (not isinstance(claims['sub'], str) or not claims['sub'] or len(claims['sub']) > 160
                    or claims['exp'] - claims['iat'] not in range(1, 61)
                    or claims['method'] != scope['method'] or claims['path'] != path
                    or claims.get('operation_id') != request.headers.get('idempotency-key', '')
                    or claims['body_sha256'] != hashlib.sha256(body).hexdigest()):
                raise ValueError('delegation_binding_mismatch')
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            return await JSONResponse({'detail': '无效的内部委托凭证'}, status_code=401)(scope, receive, send)
        scope['_finsight_delegated_owner'] = claims['sub']
        token = _request_owner.set(claims['sub'])
        sent = False
        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()
        try:
            # Recheck current project access BEFORE any cached receipt replay.
            if scope['method'] == 'POST':
                from uuid import UUID
                from .research_intake import require_project
                try:
                    UUID(request.headers.get('idempotency-key', ''))
                    project_id = UUID(json.loads(body)['project_id'])
                except (ValueError, KeyError, TypeError):
                    return await JSONResponse({'detail': '缺少有效项目或操作凭证'}, status_code=422)(scope, replay, send)
                try:
                    await require_project(self.service, project_id)
                except HTTPException as exc:
                    return await JSONResponse({'detail': exc.detail}, status_code=exc.status_code)(scope, replay, send)
            await self.app(scope, replay, send)
        finally:
            _request_owner.reset(token)


def build_business_gateway():
    router = APIRouter(prefix='/business')
    base = os.environ.get('FINSIGHT_BUSINESS_API_URL', '')
    if base:
        base = local_url(base)
        secret()

    @router.get('/config')
    async def config(request: Request):
        from .authentication import current_owner
        current_owner(request)
        return {'enabled': bool(base), 'stage': 'personal_research_intake', 'team_collaboration': False,
                'resource_spaces': resource_spaces_enabled()}

    @router.api_route('/{path:path}', methods=['GET', 'POST'])
    async def forward(path: str, request: Request):
        from .authentication import current_owner
        owner = current_owner(request)
        if not base:
            raise HTTPException(503, '本部署尚未接入研究业务服务')
        if not _PUBLIC.fullmatch(path) and not (_SPACES.fullmatch(path) and resource_spaces_enabled()):
            raise HTTPException(404)
        if request.method == 'POST':
            if request.headers.get('x-workbench-request') != '1':
                raise HTTPException(403, '缺少工作台请求标识')
            origin = request.headers.get('origin')
            if origin and origin not in {str(request.base_url).rstrip('/'), 'http://localhost:5173', 'http://127.0.0.1:5173'}:
                raise HTTPException(403, '拒绝跨站点写入')
        chunks = bytearray()
        async for part in request.stream():
            chunks.extend(part)
            if len(chunks) > 65536:
                raise HTTPException(413, '研究提交过大')
        body = bytes(chunks)
        target = '/v1/' + path + ('?' + request.url.query if request.url.query else '')
        headers = {'Authorization': 'Bearer ' + delegate(owner, request.method, target, body, operation_id=request.headers.get('idempotency-key', '')), 'Content-Type': 'application/json'}
        if key := request.headers.get('idempotency-key'):
            headers['Idempotency-Key'] = key
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(35, connect=3), trust_env=False,
                    transport=httpx.AsyncHTTPTransport(retries=0), follow_redirects=False) as client:
                response = await client.request(request.method, base + target, content=body, headers=headers)
            return Response(response.content, status_code=response.status_code, media_type='application/json', headers={'Cache-Control': 'no-store'})
        except httpx.HTTPError:
            raise HTTPException(503, '业务服务暂不可用或提交结果待核对；请返回任务列表核对原提交，不要新建重复研究。') from None
    return router
