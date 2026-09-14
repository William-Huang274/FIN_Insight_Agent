"""Actual BFF/SQLite; native draft metadata stub, no model/run dispatch capability."""
import os
from types import SimpleNamespace
from uuid import uuid4
from apps.workbench.backend.api.v1 import report_sessions
from apps.workbench.backend.app import create_report_session_app

if not os.environ.get('FINSIGHT_LOCAL_STATE_ROOT'):
    raise RuntimeError('isolated_state_root_required')
os.environ['FINSIGHT_AUTH_MODE']='local'
os.environ['FINSIGHT_REPORT_SESSION_API_URL']='http://127.0.0.1:19999'
os.environ.pop('FINSIGHT_REPORT_SESSION_SETTINGS',None)

class EmptyThreads:
    async def search(self, **kwargs): return []

class DraftThreads:
    def __init__(self): self.rows = {}
    async def search(self, *, metadata=None, **kwargs):
        return [r for r in self.rows.values() if all(r['metadata'].get(k) == v for k, v in (metadata or {}).items())]
    async def create(self, *, metadata):
        tid = str(uuid4())
        self.rows[tid] = {'thread_id': tid, 'status': 'idle', 'metadata': metadata,
                          'created_at': '2026-09-14T00:00:00Z', 'updated_at': '2026-09-14T00:00:00Z'}
        return self.rows[tid]
    async def get(self, tid): return self.rows[tid]
    async def update(self, tid, *, metadata):
        self.rows[tid]['metadata'].update(metadata)
        return self.rows[tid]
    async def get_state(self, tid): return {'values': {}, 'tasks': []}

class NoRuns:
    async def list(self, *args, **kwargs): return []
    async def create(self, *args, **kwargs): raise RuntimeError('This fixture cannot dispatch research or paid model calls')

OriginalService=report_sessions.ReportSessionService
class FixtureService(OriginalService):
    def __init__(self,*args,**kwargs):
        kwargs['research_profile'] = {'title': 'Synthetic draft qualification', 'default_question': 'Read a synthetic project document.', 'branch_topics': []}
        super().__init__(*args,**kwargs,sdk=SimpleNamespace(threads=DraftThreads(),assistants=EmptyThreads(),runs=NoRuns()))

report_sessions.ReportSessionService=FixtureService
app=create_report_session_app()
