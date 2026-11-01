"""Execution-private HTTP composition for ACP MCP and metered model routes."""
import asyncio
from contextlib import asynccontextmanager
import hmac
import socket

from fastapi import FastAPI
from starlette.responses import Response
import uvicorn

from .harness_dispatch_host import dispatch_router


@asynccontextmanager
async def harness_local_services(*, business, dispatch, transport, token):
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
        return await call_next(request)
    app.mount('/business', mcp)
    app.include_router(dispatch_router(dispatch, token=token))
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
            yield 'http://127.0.0.1:' + str(sock.getsockname()[1])
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
