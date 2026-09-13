"""Authlib OIDC authorization-code/PKCE login; no tokens exposed to JavaScript.

The signed HttpOnly session contains only an opaque verified owner and at most
five minutes of authority. Authlib owns OAuth state, nonce and code exchange.
"""
import os
import time
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse


def install_browser_login(app, backend):
    from authlib.integrations.starlette_client import OAuth
    from starlette.middleware.sessions import SessionMiddleware
    origin = os.environ['FINSIGHT_PUBLIC_ORIGIN'].rstrip('/')
    parts = urlsplit(origin)
    if parts.scheme != 'https' or not parts.hostname or parts.path or parts.query or parts.fragment or parts.username:
        raise ValueError('oidc_browser_requires_https_public_origin')
    secret = os.environ['FINSIGHT_SESSION_SECRET']
    if len(secret) < 32:
        raise ValueError('oidc_session_secret_too_short')
    oauth = OAuth()
    provider = oauth.register(name='identity', client_id=os.environ['FINSIGHT_OIDC_CLIENT_ID'],
        client_secret=os.environ.get('FINSIGHT_OIDC_CLIENT_SECRET'),
        server_metadata_url=backend.settings.issuer.rstrip('/')+'/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid', 'code_challenge_method': 'S256'})
    app.add_middleware(SessionMiddleware, secret_key=secret, session_cookie='finsight_session',
        same_site='lax', https_only=True, max_age=300)

    @app.get('/auth/login')
    async def login(request: Request):
        request.session.clear()
        return await provider.authorize_redirect(request, origin+'/auth/callback')

    @app.get('/auth/callback')
    async def callback(request: Request):
        try:
            token = await provider.authorize_access_token(request)
            from starlette.concurrency import run_in_threadpool
            owner = await run_in_threadpool(backend.verify, token['access_token'])
            ttl = min(300, max(0, int(token.get('expires_in', 0))))
            if ttl <= 0:
                raise ValueError('expired_identity')
            request.session.clear()
            request.session.update(verified_owner=owner, identity_expires=time.time()+ttl)
        except Exception:
            request.session.clear()
            raise HTTPException(401, '登录未完成，请重新登录') from None
        return RedirectResponse('/workspace', status_code=303)

    @app.post('/auth/logout')
    async def logout(request: Request):
        if request.headers.get('x-workbench-request') != '1' or request.headers.get('origin') != origin:
            raise HTTPException(403, '拒绝跨站点退出请求')
        request.session.clear()
        return {'signed_out': True}


def install_identity_status(app):
    @app.get('/auth/status')
    async def status(request: Request):
        mode = os.environ.get('FINSIGHT_AUTH_MODE', 'local')
        user = request.scope.get('user')
        signed_in = bool(user and user.is_authenticated)
        return {'mode': mode, 'authenticated': mode == 'local' or signed_in,
            'browser_login': mode == 'oidc_product' and bool(os.environ.get('FINSIGHT_OIDC_CLIENT_ID')),
            'owner': user.display_name if signed_in else None}
