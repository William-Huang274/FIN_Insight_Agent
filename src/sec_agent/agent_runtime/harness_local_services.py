"""Execution-private HTTP composition for ACP MCP and metered model routes."""
import asyncio
from contextlib import asynccontextmanager
import hmac
import logging
import socket
import time

from fastapi import FastAPI
from starlette.responses import Response
import uvicorn

logger = logging.getLogger(__name__)


async def verify_business_endpoint(endpoint, token, expected):
    """Exercise MCP initialization and discovery before starting a model process."""
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client
    async with httpx2.AsyncClient(headers={'Authorization': 'Bearer ' + token},
                                  timeout=30, trust_env=False) as http:
        async with Client(streamable_http_client(endpoint + '/business/', http_client=http),
                          read_timeout_seconds=30) as client:
            result = await client.list_tools()
            actual = {tool.name for tool in result.tools}
            if actual != set(expected):
                raise RuntimeError('harness_business_tool_discovery_mismatch')

from .harness_dispatch_host import dispatch_router


@asynccontextmanager
async def harness_local_services(*, business, dispatch, transport, token, readiness=None):
    if len(token.encode()) < 32:
        raise ValueError('harness_local_credential_requires_32_bytes')
    mcp = business.server.streamable_http_app(streamable_http_path='/', json_response=True,
                                             stateless_http=True)
    app = FastAPI()
    @app.middleware('http')
    async def authorize(request, call_next):
        credential = request.headers.get('authorization', '')
        api_key = request.headers.get('x-api-key', '')
        if not (hmac.compare_digest(credential, 'Bearer ' + token) or hmac.compare_digest(api_key, token)):
            return Response(status_code=401)
        # Record transport stages, never credentials, tool arguments or evidence.
        # Python discovery and the native client's connection are independent.
        rpc = None
        if request.url.path.startswith('/business') and request.method == 'POST':
            try:
                body = await request.json()
                candidate = body.get('method') if isinstance(body, dict) else None
                if candidate in {'initialize', 'notifications/initialized', 'tools/list', 'tools/call'}:
                    rpc = candidate
            except ValueError:
                pass
        started = time.monotonic()
        if rpc:
            logger.info('harness_mcp_request_started', extra={'rpc_method': rpc})
        try:
            response = await call_next(request)
        except BaseException:
            if rpc:
                logger.info('harness_mcp_request_failed', extra={'rpc_method': rpc,
                    'elapsed_ms': round((time.monotonic() - started) * 1000, 2)})
            raise
        if rpc:
            logger.info('harness_mcp_request_finished', extra={'rpc_method': rpc,
                'http_status': response.status_code,
                'elapsed_ms': round((time.monotonic() - started) * 1000, 2)})
        return response
    app.mount('/business', mcp)
    app.include_router(dispatch_router(dispatch, token=token, readiness=readiness))
    app.include_router(transport.router())
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
    # An embedded per-run server must not replace the process signal handlers
    # owned by Agent Server. Cancellation comes from the native run task.
    from contextlib import nullcontext
    server.capture_signals = nullcontext
    task = None
    try:
        async with business.server.session_manager.run():
            task = asyncio.create_task(server.serve(sockets=[sock]))
            async with asyncio.timeout(15):
                while not server.started:
                    if task.done():
                        await task
                        raise RuntimeError('harness_private_service_did_not_start')
                    await asyncio.sleep(.02)
            endpoint = 'http://127.0.0.1:' + str(sock.getsockname()[1])
            await verify_business_endpoint(endpoint, token, business.tools)
            yield endpoint
    finally:
        business.stop()
        server.should_exit = True
        if task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(task), 10)
            except (TimeoutError, asyncio.CancelledError):
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        sock.close()
        await transport.aclose()
