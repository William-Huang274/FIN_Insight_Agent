"""Opt-in OIDC conversation pilot using Starlette and PyJWT.

An external identity provider owns login and token issuance. Agent Server must
remain private to the BFF. Other product APIs are not yet tenant-qualified and
fail closed in this pilot; this is not a multi-tenant production deployment.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from urllib.parse import urlsplit

from fastapi import HTTPException
from starlette.authentication import AuthenticationBackend, AuthenticationError, AuthCredentials, SimpleUser
from starlette.concurrency import run_in_threadpool
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.responses import JSONResponse


@dataclass(frozen=True)
class OIDCSettings:
    issuer: str
    audience: str
    jwks_url: str

    def __post_init__(self):
        for value in (self.issuer, self.jwks_url):
            parsed = urlsplit(value)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
                raise ValueError("oidc_requires_trusted_https_issuer_and_jwks")
        if not self.audience.strip():
            raise ValueError("oidc_audience_required")


class OIDCBackend(AuthenticationBackend):
    def __init__(self, settings: OIDCSettings, *, jwks_client=None):
        import jwt
        self.settings = settings
        self.jwks = jwks_client or jwt.PyJWKClient(settings.jwks_url, timeout=5, lifespan=300)

    def verify(self, token):
        import jwt
        key = self.jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=["RS256"], issuer=self.settings.issuer,
            audience=self.settings.audience, options={"require": ["iss", "aud", "sub", "exp", "iat"]})
        if not isinstance(claims["sub"], str) or not claims["sub"].strip():
            raise AuthenticationError("invalid_access_token")
        identity = json.dumps([claims["iss"], claims["sub"]], separators=(",", ":"))
        return "oidc:" + sha256(identity.encode()).hexdigest()

    async def authenticate(self, conn):
        header = conn.headers.get("authorization")
        if header is None:
            return None
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token or len(token) > 16384:
            raise AuthenticationError("invalid_access_token")
        try:
            identity = await run_in_threadpool(self.verify, token)
        except Exception:
            raise AuthenticationError("invalid_access_token") from None
        return AuthCredentials(["authenticated"]), SimpleUser(identity)


def current_owner(request):
    if not getattr(request.app.state, "oidc_conversation_pilot", False):
        return "local-pilot"
    user = request.scope.get("user")
    if user is None or not user.is_authenticated:
        raise HTTPException(401, "请先登录", headers={"WWW-Authenticate": "Bearer"})
    # SimpleUser stores the verified opaque ID as display_name; its inherited
    # BaseUser.identity property is deliberately unimplemented in Starlette.
    return user.display_name


class ConversationPilotBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/api/v1/"):
            path, user = scope["path"], scope.get("user")
            if user is None or not user.is_authenticated:
                response = JSONResponse({"detail": "请先登录"}, status_code=401,
                                        headers={"WWW-Authenticate": "Bearer"})
            elif path != "/api/v1/conversations" and not path.startswith("/api/v1/conversations/"):
                response = JSONResponse({"detail": "当前身份隔离试点仅开放通用对话；此接口尚未完成隔离验收"}, status_code=503)
            else:
                response = None
            if response is not None:
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def install_conversation_auth(app, *, backend=None):
    mode = os.environ.get("FINSIGHT_AUTH_MODE", "local")
    if mode not in {"local", "oidc_conversation_pilot"}:
        raise ValueError("unsupported_finsight_auth_mode")
    if mode == "local" and backend is None:
        return
    backend = backend or OIDCBackend(OIDCSettings(
        issuer=os.environ["FINSIGHT_OIDC_ISSUER"], audience=os.environ["FINSIGHT_OIDC_AUDIENCE"],
        jwks_url=os.environ["FINSIGHT_OIDC_JWKS_URL"]))
    app.state.oidc_conversation_pilot = True
    app.add_middleware(ConversationPilotBoundary)
    app.add_middleware(AuthenticationMiddleware, backend=backend,
        on_error=lambda conn, exc: JSONResponse({"detail": "身份凭证无效或已过期"}, status_code=401,
                                              headers={"WWW-Authenticate": "Bearer"}))
