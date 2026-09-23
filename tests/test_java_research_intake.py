"""Real BFF routes, signed delegation and SQLite receipts; fake native SDK only.

No model calls, corpus reads or claims about financial answer quality.
"""
import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.workbench.backend.authentication import OIDCBackend, OIDCSettings, install_conversation_auth
from apps.workbench.backend.business_transport import InternalResearchIdentity, delegate, build_business_gateway
from apps.workbench.backend.api.v1.report_sessions import ReportSessionService, build_report_sessions_router, NewSession
from apps.workbench.backend.submission_receipts import SubmissionReceipts
from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
from sec_agent.research_foundation.project_library import ProjectLibrary


@pytest.fixture
def intake(tmp_path, monkeypatch):
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET', 'synthetic-test-only-delegation-key-32-bytes')
    monkeypatch.setenv('FINSIGHT_AUTH_MODE', 'oidc_product')
    monkeypatch.delenv('FINSIGHT_OIDC_CLIENT_ID', raising=False)
    threads, runs = {}, {}
    async def create(metadata, thread_id=None):
        tid = thread_id or str(uuid4())
        assert tid not in threads
        threads[tid] = {'thread_id': tid, 'metadata': deepcopy(metadata), 'status': 'idle'}
        return deepcopy(threads[tid])
    async def get(tid):
        if str(tid) not in threads:
            raise httpx.HTTPStatusError('missing', request=httpx.Request('GET', 'http://test/'), response=httpx.Response(404))
        return deepcopy(threads[str(tid)])
    async def update(tid, metadata):
        threads[str(tid)]['metadata'].update(metadata)
    async def list_runs(tid, **kw):
        return deepcopy(runs.get(str(tid), []))[kw.get('offset', 0):][:kw.get('limit', 100)]
    async def run(tid, graph, **kw):
        item = {'run_id': str(uuid4()), 'status': 'pending', 'metadata': kw['metadata'], 'config': kw['config']}
        runs.setdefault(str(tid), []).append(item)
        return deepcopy(item)
    sdk = SimpleNamespace(threads=SimpleNamespace(create=create, get=get, update=update), runs=SimpleNamespace(create=run, list=list_runs))
    service = ReportSessionService('http://127.0.0.1:9999', None, sdk=sdk,
        research_profile={'default_question': 'synthetic research question', 'branch_topics': []}, attachment_store=TaskAttachmentStore(tmp_path/'attachments'))
    service.intake_enabled = True
    service.intake_receipts_root = tmp_path/'receipts'
    binding = {'snapshot_ref': 'sha256:' + 'a'*64, 'research_as_of': '2025-12-31T00:00:00+00:00'}
    async def current(_): return deepcopy(binding)
    monkeypatch.setattr('apps.workbench.backend.research_intake.current_binding', current)
    library = ProjectLibrary(tmp_path/'project-library')
    project = str(uuid4())
    library.save('oidc:alice', 0, {'projects': [{'id': project, 'name': 'synthetic'}], 'assignments': {}, 'pinned': []})
    def application():
        app = FastAPI()
        app.add_middleware(SubmissionReceipts, directory=service.intake_receipts_root)
        install_conversation_auth(app, backend=OIDCBackend(OIDCSettings('https://unused.example', 'unused', 'https://unused.example/keys')))
        app.add_middleware(InternalResearchIdentity, service=service)
        app.include_router(build_report_sessions_router(service), prefix='/api/v1')
        return app
    yield SimpleNamespace(app=application, service=service, project=project, library=library, threads=threads, runs=runs, binding=binding)


def request(client, path, body=None, operation=None, owner='oidc:alice', **jwt_options):
    method = 'GET' if body is None else 'POST'
    path = '/api/v1/internal-research/' + path
    data = b'' if body is None else json.dumps(body, separators=(',', ':')).encode()
    operation = operation or (str(uuid4()) if body is not None else '')
    token = delegate(owner, method, path, data, operation_id=operation,
        audience='finsight-python-intake', issuer='finsight-java', **jwt_options)
    headers = {'Authorization': 'Bearer ' + token, 'X-Workbench-Request': '1', 'Content-Type': 'application/json'}
    if operation: headers['Idempotency-Key'] = operation
    return client.request(method, path, content=data, headers=headers)


def payload(s):
    return {'contract_version': 'research_intake.v1', 'task_id': str(uuid4()), 'project_id': s.project,
        'binding': deepcopy(s.binding), 'session': {'title': 'Synthetic', 'question': 'A deterministic synthetic question', 'mode': 'research', 'defer_start': True}}


def test_prepare_start_reopen_receipt_and_exact_native_association(intake):
    body = payload(intake); operation = str(uuid4()); tid = body['task_id']
    with TestClient(intake.app()) as c:
        prepared = request(c, 'prepare', body, operation)
        assert prepared.status_code == 200, prepared.text
        assert prepared.json()['thread_id'] == tid and not intake.runs
        assert intake.threads[tid]['metadata']['research_as_of'] == intake.binding['research_as_of']
        assert intake.library.index('oidc:alice')['assignments'][tid] == intake.project
    with TestClient(intake.app()) as c:
        replay = request(c, 'prepare', body, operation)
        assert replay.status_code == 200 and replay.headers['Idempotent-Replayed'] == 'true'
        start = {'task_id': tid, 'thread_id': tid, 'project_id': intake.project}
        start_op = str(uuid4())
        started = request(c, 'start', start, start_op)
        assert started.status_code == 200, started.text
        assert request(c, 'start', start, start_op).json() == started.json()
        assert len(intake.runs[tid]) == 1
        state = request(c, f'tasks/{tid}/state?project_id={intake.project}').json()
        assert state['prepare_operation_id'] == operation and state['prepared']
        assert state['runs'][0]['operation_id'] == start_op
        receipt = request(c, f'receipts/{start_op}?project_id={intake.project}&task_id={tid}').json()
        assert receipt['body']['run_id'] == started.json()['run_id']


def test_current_project_acl_runs_before_receipt_replay_and_wrong_identity(intake, monkeypatch):
    body = payload(intake); operation = str(uuid4())
    with TestClient(intake.app()) as c:
        assert request(c, 'prepare', body, operation).status_code == 200
        assert request(c, 'prepare', body, operation, owner='oidc:bob').status_code == 404
        # Simulated current access revocation, without changing immutable receipt.
        monkeypatch.setattr(ProjectLibrary, 'scope', lambda *a: (_ for _ in ()).throw(KeyError('revoked')))
        assert request(c, 'prepare', body, operation).status_code == 404
        assert request(c, f"tasks/{body['task_id']}/state?project_id={intake.project}").status_code == 404


def test_version_change_never_substitutes_latest_or_starts(intake):
    body = payload(intake)
    with TestClient(intake.app()) as c:
        assert request(c, 'prepare', body).status_code == 200
        intake.binding['snapshot_ref'] = 'sha256:' + 'b'*64
        response = request(c, 'start', {'task_id': body['task_id'], 'thread_id': body['task_id'], 'project_id': intake.project})
        assert response.status_code == 409 and not intake.runs
    # A local pilot must still be able to STOP its original native run even
    # when current publication differs. This guard must never trap paid work.
    tid = body['task_id']
    intake.threads[tid]['metadata']['owner_id'] = 'local-pilot'
    stopped = []
    async def cancel(thread_id, run_id, **kwargs): stopped.append((thread_id, run_id))
    intake.service.sdk.runs.cancel = cancel
    local = FastAPI(); local.include_router(build_report_sessions_router(intake.service), prefix='/api/v1')
    with TestClient(local) as c:
        run_id = str(uuid4())
        response = c.post(f'/api/v1/research-sessions/{tid}/runs/{run_id}/cancel', headers={'X-Workbench-Request': '1'})
        assert response.status_code == 200 and stopped == [(tid, run_id)]


def test_payload_tampering_missing_key_and_public_schema_are_rejected(intake):
    body = payload(intake); data = json.dumps(body).encode(); path = '/api/v1/internal-research/prepare'; op = str(uuid4())
    token = delegate('oidc:alice', 'POST', path, data, operation_id=op, audience='finsight-python-intake', issuer='finsight-java')
    with TestClient(intake.app()) as c:
        headers = {'Authorization': 'Bearer '+token, 'Idempotency-Key': op, 'Content-Type': 'application/json', 'X-Workbench-Request': '1'}
        assert c.post(path, content=data+b' ', headers=headers).status_code == 401
        assert c.post(path, content=data, headers={**headers, 'Idempotency-Key': str(uuid4())}).status_code == 401
        assert c.post(path, json=body).status_code == 401
        assert not intake.threads
    with pytest.raises(ValueError): NewSession.model_validate({**body['session'], 'owner_id': 'forged'})
    with pytest.raises(ValueError): NewSession.model_validate({**body['session'], 'binding': body['binding']})


def test_gateway_disabled_by_default_and_no_catchall_proxy(monkeypatch):
    monkeypatch.delenv('FINSIGHT_BUSINESS_API_URL', raising=False)
    app = FastAPI(); app.include_router(build_business_gateway(), prefix='/api/v1')
    with TestClient(app) as c:
        assert c.get('/api/v1/business/config').json()['enabled'] is False
        assert c.get('/api/v1/business/tasks').status_code == 503
