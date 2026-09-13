import asyncio
from uuid import uuid4
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse
from apps.workbench.backend.submission_receipts import SubmissionReceipts
from apps.workbench.backend.authentication import _request_owner


def application(root, effects, *, fail=False):
    app = FastAPI()
    @app.post('/api/v1/dispatch')
    async def dispatch():
        effects.append('executed')
        await asyncio.sleep(.02)
        if fail:
            return JSONResponse({'detail':'unknown upstream result'},status_code=502)
        return {'run_id': 'native-issued-id'}
    app.add_middleware(SubmissionReceipts,directory=root)
    return app


def headers():
    return {'Idempotency-Key':str(uuid4()),'X-Workbench-Request':'1'}


def test_response_replay_survives_app_reopen_and_rejects_changed_payload(tmp_path):
    calls=[];h=headers()
    with TestClient(application(tmp_path,calls)) as c:
        r=c.post('/api/v1/dispatch',headers=h,json={'message':'one'})
        assert r.status_code==200
    with TestClient(application(tmp_path,calls)) as c:
        r=c.post('/api/v1/dispatch',headers=h,json={'message':'one'})
        assert r.headers['Idempotent-Replayed']=='true' and r.json()['run_id']=='native-issued-id'
        assert c.post('/api/v1/dispatch',headers=h,json={'message':'different'}).status_code==422
    assert calls==['executed']


def test_uncertain_dispatch_never_expires_into_automatic_retry(tmp_path):
    calls=[];h=headers()
    with TestClient(application(tmp_path,calls,fail=True)) as c:
        assert c.post('/api/v1/dispatch',headers=h,json={}).status_code==502
    with TestClient(application(tmp_path,calls)) as c:
        assert c.post('/api/v1/dispatch',headers=h,json={}).status_code==409
    assert len(calls)==1


def test_receipts_are_per_verified_owner_not_per_guessed_uuid(tmp_path):
    calls=[];h=headers()
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application(tmp_path,calls)),base_url='http://test') as c:
            for user in ['alice','bob','alice']:
                token=_request_owner.set(user)
                try:
                    r=await c.post('/api/v1/dispatch',headers=h,json={})
                    assert r.status_code==200
                finally:
                    _request_owner.reset(token)
    asyncio.run(run())
    assert len(calls)==2


def test_two_process_equivalent_ingresses_share_atomic_claim(tmp_path):
    calls=[];h=headers()
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application(tmp_path,calls)),base_url='http://a') as a, httpx.AsyncClient(transport=httpx.ASGITransport(app=application(tmp_path,calls)),base_url='http://b') as b:
            results=await asyncio.gather(a.post('/api/v1/dispatch',headers=h,json={}),b.post('/api/v1/dispatch',headers=h,json={}))
            assert sorted(r.status_code for r in results)==[200,409]
    asyncio.run(run())
    assert len(calls)==1


def test_replay_still_requires_browser_write_marker(tmp_path):
    calls=[];h=headers()
    with TestClient(application(tmp_path,calls)) as c:
        c.post('/api/v1/dispatch',headers=h,json={})
        del h['X-Workbench-Request']
        assert c.post('/api/v1/dispatch',headers=h,json={}).status_code==403
    assert len(calls)==1


def test_legacy_http_receipts_replay_or_hold_without_dispatch(tmp_path):
    from hashlib import sha256
    import json
    import pickle
    import sqlite3
    from apps.workbench.backend.authentication import service_owner
    calls = []
    completed, uncertain = headers(), headers()
    fingerprint = sha256(b'POST/api/v1/dispatch{}').hexdigest()
    body = b'{"run_id":"legacy-native-id"}'
    with sqlite3.connect(tmp_path / 'cache.db') as db:
        db.execute('CREATE TABLE Cache (key BLOB, raw INTEGER, expire_time REAL, mode INTEGER, filename TEXT, value BLOB)')
        for h, receipt in [
            (completed, {'fingerprint': fingerprint, 'status': 'received', 'http_status': 201, 'body': body}),
            (uncertain, {'fingerprint': fingerprint, 'status': 'dispatching'}),
        ]:
            key = sha256(json.dumps([service_owner(), h['Idempotency-Key']]).encode()).hexdigest()
            db.execute('INSERT INTO Cache VALUES (?,1,NULL,4,NULL,?)', (key, pickle.dumps(receipt)))
    with TestClient(application(tmp_path, calls)) as client:
        response = client.post('/api/v1/dispatch', headers=completed, json={})
        assert response.status_code == 201 and response.content == body
        assert response.headers['Idempotent-Replayed'] == 'true'
        assert client.post('/api/v1/dispatch', headers=uncertain, json={}).status_code == 409
    assert calls == []
