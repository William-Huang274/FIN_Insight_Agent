"""Real BFF for cross-language qualification. Native SDK is a disk-backed fake.

This module cannot contact an Agent Server or model provider. Never deploy it.
"""
import json
import asyncio
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import httpx

if os.environ.get('FINSIGHT_INTAKE_QUALIFICATION') != '1':
    raise RuntimeError('synthetic_qualification_only')
root = Path(os.environ['FINSIGHT_LOCAL_STATE_ROOT'])
root.mkdir(parents=True, exist_ok=True)
os.environ['FINSIGHT_AUTH_MODE'] = 'local'
os.environ['FINSIGHT_REPORT_SESSION_API_URL'] = 'http://127.0.0.1:19999'
os.environ.pop('FINSIGHT_REPORT_SESSION_SETTINGS', None)
os.environ.pop('FINSIGHT_RESEARCH_SESSION_ENABLED', None)
from apps.workbench.backend.api.v1 import report_sessions
from apps.workbench.backend import research_intake
from apps.workbench.backend.app import create_report_session_app
state_path = root/'synthetic-native.json'
state = json.loads(state_path.read_text()) if state_path.exists() else {'threads': {}, 'runs': {}}
logging.getLogger('apps.workbench.backend.research_intake').setLevel(logging.INFO)
logging.getLogger('apps.workbench.backend.research_intake').addHandler(logging.StreamHandler())

def save():
    temporary = state_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state), encoding='utf-8')
    temporary.replace(state_path)

async def barrier(point):
    """Fault controls exist only in this explicitly guarded test module."""
    control = root/'fault-control.json'
    if not control.exists(): return
    setting = json.loads(control.read_text())
    marker = root/('entered-'+setting['case'])
    release = root/('release-'+setting['case'])
    if setting['point'] != point or marker.exists(): return
    marker.write_text(point)
    for _ in range(600):
        if release.exists(): return
        await asyncio.sleep(.1)
    raise RuntimeError('synthetic_fault_barrier_timeout')

class Threads:
    async def search(self, **kwargs): return list(state['threads'].values())
    async def create(self, *, metadata, thread_id=None):
        tid = str(thread_id or uuid4())
        if tid in state['threads']: raise RuntimeError('duplicate_native_thread')
        row = {'thread_id': tid, 'status': 'idle', 'metadata': metadata, 'created_at': '2026-09-23T00:00:00Z'}
        state['threads'][tid] = row; save(); return row
    async def get(self, tid):
        if str(tid) not in state['threads']:
            raise httpx.HTTPStatusError('missing', request=httpx.Request('GET', 'http://unused/'), response=httpx.Response(404))
        return state['threads'][str(tid)]
    async def update(self, tid, *, metadata):
        state['threads'][str(tid)]['metadata'].update(metadata); save()
    async def get_state(self, tid): return {'values': {}, 'tasks': [], 'checkpoint': {'checkpoint_id': str(uuid4())}}

class Runs:
    async def list(self, tid, **kwargs): return state['runs'].get(str(tid), [])[kwargs.get('offset', 0):][:kwargs.get('limit', 100)]
    async def create(self, tid, graph, **kwargs):
        await barrier('before_native_start')
        tid = str(tid)
        row = {'run_id': str(uuid4()), 'status': 'success', 'metadata': kwargs['metadata']}
        state['runs'].setdefault(tid, []).append(row); save()
        await barrier('after_native_start')
        if state['threads'][tid]['metadata']['title'] == 'Synthetic lost response':
            raise httpx.ReadTimeout('synthetic response lost after persistence')
        return row

original = report_sessions.ReportSessionService
class SyntheticService(original):
    def __init__(self, *args, **kwargs):
        kwargs['research_profile'] = {'title': 'Synthetic only', 'default_question': 'Synthetic qualification question', 'branch_topics': [], 'research_as_of': '2025-12-31T00:00:00+00:00'}
        super().__init__(*args, **kwargs, sdk=SimpleNamespace(threads=Threads(), runs=Runs()))
report_sessions.ReportSessionService = SyntheticService
async def synthetic_binding(service):
    await barrier('before_binding_reply')
    return {'snapshot_ref': 'sha256:'+'a'*64, 'research_as_of': service.research_profile['research_as_of']}
research_intake.current_binding = synthetic_binding
application = create_report_session_app()

async def app(scope, receive, send):
    async def after_receipt(message):
        if scope.get('path') == '/api/v1/internal-research/start' and message['type'] == 'http.response.start':
            await barrier('after_receipt_save')
        await send(message)
    await application(scope, receive, after_receipt)
