"""Real JWT signatures through the BFF, with an in-memory native SDK double.

These are HTTP/resource isolation qualification, not IdP login or deployed
Agent Server multi-tenant acceptance.
"""
from copy import deepcopy
from time import time
from types import SimpleNamespace
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
import jwt
import pytest

from apps.workbench.backend.authentication import OIDCBackend, OIDCSettings, install_conversation_auth
from apps.workbench.backend.api.v1.conversations import build_conversations_router


@pytest.fixture
def pilot(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    import json
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="test-key", use="sig", alg="RS256")
    jwks = jwt.PyJWKClient("https://issuer.example/keys")
    jwks.fetch_data = lambda: {"keys": [jwk]}  # Only IdP HTTP is stubbed; native JWK selection and RSA validation run.
    backend = OIDCBackend(OIDCSettings("https://issuer.example", "finsight-api", "https://issuer.example/keys"), jwks_client=jwks)
    threads, accesses = {}, []
    checkpoint = str(uuid4())

    def token(sub="alice", **overrides):
        claims = {"iss": "https://issuer.example", "aud": "finsight-api", "sub": sub,
                  "iat": int(time()), "exp": int(time()) + 300, **overrides}
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})

    async def create(**kwargs):
        tid = str(uuid4())
        threads[tid] = {"thread_id": tid, "metadata": deepcopy(kwargs["metadata"]), "status": "idle"}
        return threads[tid]

    async def get(tid):
        return deepcopy(threads[tid])

    async def search(**kwargs):
        accesses.append(("search", kwargs))
        # Return all rows to additionally verify the BFF never discloses a
        # wrong-owner result even when an upstream result includes one.
        return list(threads.values())

    async def state(tid, **kwargs):
        accesses.append(("state", tid))
        return {"checkpoint": {"checkpoint_id": checkpoint}, "tasks": [], "values": {"messages": []}}

    async def runs(*args, **kwargs):
        accesses.append(("runs", args))
        return []

    sdk = SimpleNamespace(threads=SimpleNamespace(create=create, get=get, search=search, get_state=state),
                          runs=SimpleNamespace(list=runs))
    app = FastAPI()
    app.include_router(build_conversations_router(SimpleNamespace(sdk=sdk, audit_root=tmp_path)), prefix="/api/v1")
    install_conversation_auth(app, backend=backend)
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, token=token, threads=threads, accesses=accesses, checkpoint=checkpoint, backend=backend)


def headers(pilot, sub="alice"):
    return {"Authorization": "Bearer " + pilot.token(sub), "X-Workbench-Request": "1"}


def draft(pilot, sub="alice"):
    result = pilot.client.post("/api/v1/conversations/drafts", headers=headers(pilot, sub), json={"title": "Private"})
    assert result.status_code == 200, result.text
    return result.json()["thread_id"]


def test_real_signed_identity_and_list_read_handoff_ownership(pilot):
    alice, bob = draft(pilot), draft(pilot, "bob")
    assert pilot.threads[alice]["metadata"]["owner_id"] != pilot.threads[bob]["metadata"]["owner_id"]
    result = pilot.client.get("/api/v1/conversations", headers=headers(pilot))
    assert [r["thread_id"] for r in result.json()] == [alice]
    assert pilot.accesses[-1][1]["metadata"]["owner_id"] == pilot.threads[alice]["metadata"]["owner_id"]
    assert pilot.client.get(f"/api/v1/conversations/{alice}", headers=headers(pilot)).status_code == 200
    assert pilot.client.get(f"/api/v1/conversations/{alice}", headers=headers(pilot, "bob")).status_code == 404
    result = pilot.client.post(f"/api/v1/conversations/{alice}/handoff", headers=headers(pilot),
        json={"checkpoint_id": pilot.checkpoint, "note": "Continue here"})
    assert result.status_code == 200
    assert pilot.threads[result.json()["thread_id"]]["metadata"]["owner_id"] == pilot.threads[alice]["metadata"]["owner_id"]


@pytest.mark.parametrize("verb,suffix,body", [
    ("get", "", None), ("get", "/handoff-preview", None),
    ("post", "/attachments", None), ("post", "/messages", {"message": "run"}),
    ("post", "/stop", None),
    ("post", "/handoff", {"checkpoint_id": str(uuid4()), "note": "Read Alice"}),
    ("post", "/approvals", {"checkpoint_id": str(uuid4()), "interrupt_id": "test", "decisions": ["approve"]}),
    ("get", f"/runs/{uuid4()}/stream", None),
    ("get", f"/messages/answer/export/md?checkpoint_id={uuid4()}", None),
])
def test_foreign_id_cannot_read_execute_approve_upload_export_or_stream(pilot, verb, suffix, body):
    alice = draft(pilot)
    pilot.accesses.clear()
    response = pilot.client.request(verb, f"/api/v1/conversations/{alice}{suffix}", headers=headers(pilot, "bob"), json=body)
    assert response.status_code == 404, response.text
    assert pilot.accesses == []  # No checkpoint, run, or attachment effect past the owner gate.


@pytest.mark.parametrize("overrides", [{"exp": 1}, {"iat": int(time()) + 1000}, {"iss": "https://attacker.example"},
    {"aud": "another-api"}, {"sub": ""}])
def test_invalid_signed_claims_rejected_before_sdk(pilot, overrides):
    token = pilot.token(**overrides)
    response = pilot.client.get("/api/v1/conversations", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 401
    assert token not in response.text and not pilot.accesses


def test_no_credentials_forgery_and_unqualified_endpoints_fail_closed(pilot):
    path = "/api/v1/conversations"
    assert pilot.client.get(path, headers={"X-Owner-Id": "alice"}).status_code == 401
    forged = jwt.encode({"iss": "https://issuer.example", "sub": "alice", "aud": "finsight-api", "exp": int(time())+100},
                        "attacker-secret-that-is-long-enough", algorithm="HS256")
    assert pilot.client.get(path, headers={"Authorization": "Bearer " + forged}).status_code == 401
    assert pilot.client.get("/api/v1/research-sessions", headers=headers(pilot)).status_code == 503
    assert pilot.client.post(path + "/drafts", headers=headers(pilot), json={"title": "x", "owner_id": "bob"}).status_code == 422
    assert not pilot.threads and not pilot.accesses


def test_legacy_unowned_conversation_not_adopted_by_authenticated_user(pilot):
    tid = draft(pilot)
    del pilot.threads[tid]["metadata"]["owner_id"]
    assert pilot.client.get(f"/api/v1/conversations/{tid}", headers=headers(pilot)).status_code == 404


def test_config_refuses_untrusted_jwks_or_missing_audience():
    for issuer, audience, keys in [("http://issuer", "api", "https://issuer/keys"),
                                  ("https://issuer", "", "https://issuer/keys"),
                                  ("https://issuer", "api", "https://user:pass@issuer/keys")]:
        with pytest.raises(ValueError):
            OIDCSettings(issuer, audience, keys)


def test_missing_required_expiry_and_bad_signature_are_denied(pilot):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wrong_key_token = jwt.encode({"iss": "https://issuer.example", "sub": "alice", "aud": "finsight-api",
        "iat": int(time()), "exp": int(time()) + 300}, key, algorithm="RS256", headers={"kid": "test-key"})
    for token in (wrong_key_token, pilot.token(exp=None)):
        assert pilot.client.get("/api/v1/conversations", headers={"Authorization": "Bearer " + token}).status_code == 401
    assert not pilot.accesses


def test_authenticated_setting_cannot_silently_start_legacy_unprotected_app(monkeypatch):
    from apps.workbench.backend.app import create_app
    monkeypatch.delenv("FINSIGHT_REPORT_SESSION_API_URL", raising=False)
    monkeypatch.setenv("FINSIGHT_AUTH_MODE", "oidc_conversation_pilot")
    with pytest.raises(ValueError, match="private_native_session_api"):
        create_app()
