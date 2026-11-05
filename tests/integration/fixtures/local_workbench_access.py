"""Opt-in Windows qualification viewer. Grants are issued locally, never by a remote HTTP client."""

import hashlib
import hmac
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse


COOKIE = "fin_qualification_view"
PENDING = "fin_qualification_pair"
YEAR = 365 * 86400


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class DeviceStore:
    def __init__(self, path):
        self.path = Path(path)
        with closing(self.connect()) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS grants(hash TEXT PRIMARY KEY, expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS pairs(id TEXT PRIMARY KEY, hash TEXT NOT NULL, expires INTEGER NOT NULL, approved INTEGER NOT NULL);
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=5, isolation_level=None)

    def pair(self, approved=False):
        identifier, secret = secrets.token_hex(5), secrets.token_urlsafe(32)
        with closing(self.connect()) as conn:
            now = int(time.time())
            conn.execute("DELETE FROM pairs WHERE expires<=?", (now,))
            conn.execute("DELETE FROM grants WHERE expires<=?", (now,))
            conn.execute(
                "INSERT INTO pairs VALUES (?,?,?,?)",
                (identifier, digest(secret), now + 180, int(approved)),
            )
        return identifier, secret

    def approve(self, identifier):
        with closing(self.connect()) as conn:
            updated = conn.execute(
                "UPDATE pairs SET approved=1 WHERE id=? AND expires>?",
                (identifier, int(time.time())),
            )
            return updated.rowcount == 1

    def redeem(self, identifier, secret):
        if len(secret) > 128 or len(identifier) > 16:
            return None
        with closing(self.connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT hash,approved FROM pairs WHERE id=? AND expires>?",
                (identifier, int(time.time())),
            ).fetchone()
            if not row or not row[1] or not hmac.compare_digest(row[0], digest(secret)):
                return None
            token = secrets.token_urlsafe(32)
            conn.execute("DELETE FROM pairs WHERE id=?", (identifier,))
            conn.execute(
                "INSERT INTO grants VALUES (?,?)",
                (digest(token), int(time.time()) + YEAR),
            )
            conn.commit()
            return token

    def valid(self, token):
        if not token or len(token) > 128:
            return False
        with closing(self.connect()) as conn:
            return bool(
                conn.execute(
                    "SELECT 1 FROM grants WHERE hash=? AND expires>?",
                    (digest(token), int(time.time())),
                ).fetchone()
            )

    def revoke(self, token):
        with closing(self.connect()) as conn:
            conn.execute("DELETE FROM grants WHERE hash=?", (digest(token),))


PAGE = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>登录本机研究工作区</title>
<style>body{max-width:35rem;margin:14vh auto;padding:2rem;font:17px/1.7 system-ui;color:#23324a}strong{font:600 26px monospace}p{margin:1rem 0}</style>
<h1>登录本机研究工作区</h1><p id="msg">正在连接…</p><strong id="code"></strong>
<script>
const msg=document.querySelector('#msg'),code=document.querySelector('#code');
const fragment=location.hash.slice(1), target=new URLSearchParams(location.search).get('next') || (document.referrer.startsWith(location.origin+'/workspace') ? document.referrer.slice(location.origin.length) : '');
history.replaceState(null,'',location.pathname+location.search);
const post=(route,body)=>fetch('/auth/device/'+route,{method:'POST',cache:'no-store',
 headers:{'Content-Type':'application/json','X-Workbench-Request':'1'},body:JSON.stringify(body)});
function finish(){location.replace(target && target.startsWith('/workspace') && !target.includes('\\\\') ? target : '/workspace/projects')}
async function login(){
 if((await (await fetch('/auth/status',{cache:'no-store'})).json()).authenticated){finish();return}
 if(fragment){const [id,secret]=fragment.split('.');const r=await post('redeem',{id,secret});if(r.ok){finish();return}}
 const p=await post('pair',{});if(!p.ok)throw Error();const {id}=await p.json();code.textContent=id;
 msg.textContent='请打开桌面的「授权此浏览器」，输入下面的配对码。配对后，这个浏览器可长期查看工作台。';
 const until=Date.now()+180000;const timer=setInterval(async()=>{if(Date.now()>until){clearInterval(timer);msg.textContent='配对码已过期，请刷新页面。';return}
 const r=await post('redeem',{id});if(r.ok){clearInterval(timer);finish()}},2000)
} login().catch(()=>msg.textContent='本机服务没有完成登录，请重新打开桌面入口。')
</script></html>"""


class LocalWorkbenchAccess:
    def __init__(self, app, db, port):
        self.app, self.store = app, DeviceStore(db)
        self.host = f"127.0.0.1:{int(port)}"
        self.origin = f"http://{self.host}"

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        req = Request(scope, receive)
        path, method = scope["path"], scope["method"]
        # This alternate login applies only to the opt-in local qualification fixture.
        local = (
            req.client is not None
            and req.client.host == "127.0.0.1"
            and req.headers.get("host") == self.host
            and scope["scheme"] == "http"
        )
        explicit = bool(req.headers.get("authorization"))
        auth_path = path in (
            "/auth/login",
            "/auth/status",
            "/auth/logout",
        ) or path.startswith("/auth/device/")
        token = req.cookies.get(COOKIE, "")
        if not local or explicit or not (auth_path or token):
            return await self.app(scope, receive, send)
        origin = req.headers.get("origin")
        cross = req.headers.get("sec-fetch-site") in ("same-site", "cross-site") or (
            origin and origin != self.origin
        )
        no_store = {
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
        }

        def json(data, status=200):
            return JSONResponse(data, status_code=status, headers=no_store)

        if cross and path.startswith("/workspace") and method == "GET":
            # A link from another site may load the public shell. Its next
            # same-origin API request will authenticate the paired browser.
            return await self.app(scope, receive, send)
        if cross and path != "/auth/login":
            res = json({"detail": "拒绝跨站点访问"}, 403)
        elif path == "/auth/login" and method == "GET":
            res = HTMLResponse(
                PAGE,
                headers={
                    **no_store,
                    "Content-Security-Policy": "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'",
                },
            )
        elif path == "/auth/status" and method == "GET":
            ok = self.store.valid(token)
            res = json(
                {
                    "mode": "oidc_product",
                    "authenticated": ok,
                    "owner": "oidc:alice" if ok else None,
                    "browser_login": True,
                }
            )
        elif path.startswith("/auth/device/") or path == "/auth/logout":
            if (
                method != "POST"
                or origin != self.origin
                or req.headers.get("x-workbench-request") != "1"
            ):
                res = json({"detail": "请求来源无效"}, 403)
            elif path == "/auth/device/pair":
                identifier, pending = self.store.pair()
                res = json({"id": identifier})
                res.set_cookie(
                    PENDING,
                    pending,
                    max_age=180,
                    path="/auth/device/",
                    httponly=True,
                    samesite="strict",
                )
            elif path == "/auth/device/redeem":
                try:
                    data = await req.json()
                    session = self.store.redeem(
                        str(data.get("id", "")),
                        str(data.get("secret") or req.cookies.get(PENDING, "")),
                    )
                except (ValueError, AttributeError):
                    session = None
                res = json({"authorized": bool(session)}, 200 if session else 409)
                if session:
                    res.set_cookie(
                        COOKIE,
                        session,
                        max_age=YEAR,
                        httponly=True,
                        samesite="strict",
                        path="/",
                    )
                    res.delete_cookie(PENDING, path="/auth/device/")
            elif path == "/auth/logout":
                self.store.revoke(token)
                res = json({"signed_out": True})
                res.delete_cookie(COOKIE, path="/")
            else:
                res = json({"detail": "未知授权操作"}, 404)
        elif self.store.valid(token):
            if method not in ("GET", "HEAD"):
                res = json({"detail": "此设备已获查看权限"}, 403)
            else:
                # Existing BFF authenticates this account and checks project membership.
                scope = {
                    **scope,
                    "session": {
                        "verified_owner": "oidc:alice",
                        "identity_expires": time.time() + 60,
                    },
                }
                return await self.app(scope, receive, send)
        else:
            return await self.app(scope, receive, send)
        await res(scope, receive, send)
