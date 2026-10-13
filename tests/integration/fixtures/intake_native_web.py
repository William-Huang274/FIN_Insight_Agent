"""Real BFF/SDK with synthetic binding/profile; connects only to the test API."""
import logging
import os
from urllib.parse import urlsplit

if os.environ.get('FIN_INTAKE_NATIVE_QUALIFICATION') != '1':
    raise RuntimeError('isolated_native_qualification_only')
endpoint = urlsplit(os.environ['FINSIGHT_REPORT_SESSION_API_URL'])
if endpoint.hostname != '127.0.0.1' or endpoint.port != int(os.environ['FIN_PROBE_API_PORT']):
    raise RuntimeError('qualification_endpoint_mismatch')
if endpoint.port in (18165, 18765):
    raise RuntimeError('production_port_forbidden')
os.environ['FINSIGHT_AUTH_MODE'] = 'local'
os.environ.pop('FINSIGHT_REPORT_SESSION_SETTINGS', None)
os.environ.pop('FINSIGHT_RESEARCH_SESSION_ENABLED', None)

from apps.workbench.backend.api.v1 import report_sessions
from apps.workbench.backend import research_intake
from apps.workbench.backend.app import create_report_session_app

original = report_sessions.ReportSessionService


class QualificationService(original):
    def __init__(self, *args, **kwargs):
        kwargs['research_profile'] = {'title': 'Synthetic native lifecycle', 'default_question': 'Synthetic only',
            'branch_topics': [], 'research_as_of': '2025-12-31T00:00:00+00:00'}
        super().__init__(*args, **kwargs)  # Real LangGraphClient; no SDK method replaced.


report_sessions.ReportSessionService = QualificationService


async def synthetic_binding(service):
    return {'snapshot_ref': 'sha256:' + 'a' * 64, 'research_as_of': service.research_profile['research_as_of']}


research_intake.current_binding = synthetic_binding
logging.getLogger('apps.workbench.backend.research_intake').setLevel(logging.INFO)
logging.getLogger('apps.workbench.backend.research_intake').addHandler(logging.StreamHandler())
app = create_report_session_app()
