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

organization_probe = os.environ.get('FIN_ORGANIZATION_NATIVE_QUALIFICATION') == '1'
if organization_probe:
    from apps.workbench.backend import authentication
    from starlette.authentication import AuthenticationError
    os.environ['FINSIGHT_AUTH_MODE'] = 'oidc_product'
    os.environ['FINSIGHT_RESOURCE_SPACES_ENABLED'] = '1'
    os.environ.pop('FINSIGHT_OIDC_CLIENT_ID', None)
    class SyntheticIdentity(authentication.OIDCBackend):
        def verify(self, token):
            if os.environ.get('FIN_COMPLETE_SOURCE_HTTP_QUALITY') == '1':
                import re
                if re.fullmatch(r'qualification-viewer-[a-f0-9]{32}', token):
                    return 'oidc:' + token.removeprefix('qualification-')
            if os.environ.get('FIN_ORGANIZATION_CAPACITY_QUALIFICATION') == '1':
                import re
                match = re.fullmatch(r'qualification-user-(\d{1,2})', token)
                if match and 0 <= int(match[1]) < 32:
                    return 'oidc:load-user-' + str(int(match[1]))
            if token not in ('qualification-alice', 'qualification-viewer'):
                raise AuthenticationError('qualification_identity_required')
            return 'oidc:alice' if token == 'qualification-alice' else 'oidc:viewer'
    install_auth = authentication.install_conversation_auth
    def install_qualification_auth(app):
        install_auth(app, backend=SyntheticIdentity(authentication.OIDCSettings(
            issuer='https://qualification.invalid', audience='qualification',
            jwks_url='https://qualification.invalid/keys')))
    authentication.install_conversation_auth = install_qualification_auth

from apps.workbench.backend.api.v1 import report_sessions
from apps.workbench.backend import research_intake
from apps.workbench.backend.app import create_report_session_app

original = report_sessions.ReportSessionService


class QualificationService(original):
    def __init__(self, *args, **kwargs):
        kwargs['research_profile'] = {'title': 'Synthetic native lifecycle', 'default_question': 'Synthetic only',
            'branch_topics': [], 'research_as_of': '2025-12-31T00:00:00+00:00'}
        super().__init__(*args, **kwargs)  # Real LangGraphClient and native persistence.
        if organization_probe:
            import json
            from pathlib import Path
            import httpx
            create = self.sdk.threads.create
            async def create_with_lost_reply(**options):
                # Persist through the real SDK, then inject loss of its response.
                result = await create(**options)
                with (Path(os.environ['FINSIGHT_LOCAL_STATE_ROOT']) / 'native-create-observations.jsonl').open('a', encoding='utf-8') as out:
                    out.write(json.dumps({'thread_id': result['thread_id']}) + '\n')
                if options['metadata']['title'] == 'Synthetic lost organization reply':
                    raise httpx.ReadTimeout('qualification: native persisted before reply loss')
                return result
            self.sdk.threads.create = create_with_lost_reply
            run_create = self.sdk.runs.create
            async def run_with_lost_reply(thread_id, assistant_id, **options):
                result = await run_create(thread_id, assistant_id, **options)
                with (Path(os.environ['FINSIGHT_LOCAL_STATE_ROOT']) / 'native-start-observations.jsonl').open('a', encoding='utf-8') as out:
                    out.write(json.dumps({'thread_id':thread_id,'run_id':result['run_id']})+'\n')
                thread = await self.sdk.threads.get(thread_id)
                lost_action = (os.environ.get('FIN_ORGANIZATION_REPORT_ACTIONS_QUALIFICATION') == '1'
                    and options.get('command', {}).get('resume', {}).get('message') == 'Static lost action')
                if thread['metadata']['title'] == 'Synthetic lost organization reply' or lost_action:
                    raise httpx.ReadTimeout('qualification: native run persisted before reply loss')
                return result
            self.sdk.runs.create = run_with_lost_reply


report_sessions.ReportSessionService = QualificationService


async def synthetic_binding(service):
    return {'snapshot_ref': 'sha256:' + 'a' * 64, 'research_as_of': service.research_profile['research_as_of']}


research_intake.current_binding = synthetic_binding
if os.environ.get('FIN_COMPLETE_SOURCE_HTTP_QUALITY') == '1':
    from tests.integration.source_intake_http import install_provider_budget
    install_provider_budget()
    if os.environ.get('FIN_COMPLETE_SOURCE_HTTP_PROFILE') == '1':
        from pathlib import Path
        from tests.integration.source_intake_profile import install
        install(Path(os.environ['FIN_COMPLETE_SOURCE_HTTP_EVIDENCE_ROOT'])/'request-profiles')
logging.getLogger('apps.workbench.backend.research_intake').setLevel(logging.INFO)
logging.getLogger('apps.workbench.backend.research_intake').addHandler(logging.StreamHandler())
app = create_report_session_app()
