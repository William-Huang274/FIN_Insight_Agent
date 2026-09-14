"""Actual BFF composition, isolated local state, native research list stub only."""
import os
from types import SimpleNamespace
from apps.workbench.backend.api.v1 import report_sessions
from apps.workbench.backend.app import create_report_session_app

if not os.environ.get('FINSIGHT_LOCAL_STATE_ROOT'):
    raise RuntimeError('isolated_state_root_required')
os.environ['FINSIGHT_AUTH_MODE']='local'
os.environ['FINSIGHT_REPORT_SESSION_API_URL']='http://127.0.0.1:19999'
os.environ.pop('FINSIGHT_REPORT_SESSION_SETTINGS',None)

class EmptyThreads:
    async def search(self, **kwargs): return []

OriginalService=report_sessions.ReportSessionService
class FixtureService(OriginalService):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs,sdk=SimpleNamespace(threads=EmptyThreads(),assistants=EmptyThreads()))

report_sessions.ReportSessionService=FixtureService
app=create_report_session_app()
