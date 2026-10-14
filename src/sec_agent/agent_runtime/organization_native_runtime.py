"""Native admission of one Java-authorized orientation run before host resources."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
from uuid import UUID

from langchain_core.runnables import RunnableLambda
from pydantic import SecretStr

from sec_agent.research_foundation.organization_execution_access import (
    OrganizationExecutionAuthority, OrganizationExecutionReader, OrganizationExecutionUnavailable, validate_execution_grant,
)
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from .organization_native_contract import validate_start, validate_thread, run_request, run_receipt
from .organization_continuation_contract import validate_continuation, validate_baseline, continuation_request, continuation_receipt


class OrganizationStartAuthority:
    def __init__(self, resources, *, run_id, context):
        self.resources, self.run_id, self.context = resources, str(UUID(run_id)), dict(context)

    def __call__(self):
        c = self.context
        grant = self.resources.request(f'/v1/runtime/organization-executions/{self.resources.execution_id}/admit-start',
            {'thread_id':self.resources.execution_id, 'run_id':self.run_id, 'operation_id':c['start_operation_id'],
             'manifest_digest':self.resources.manifest_digest, 'configuration_digest':c['configuration_digest'],
             'start_request_digest':c['start_request_digest']})
        try:
            validate_execution_grant(grant, self.resources.execution_id, self.resources.manifest_digest)
            validate_start(grant)
            if grant['authorized_run_id'] != self.run_id or any(grant[key] != value for key, value in c.items()):
                raise ValueError('scope')
        except (KeyError, ValueError, TypeError):
            raise OrganizationExecutionUnavailable('组织原生运行启动授权不匹配。') from None
        return grant


class OrganizationContinuationAuthority(OrganizationStartAuthority):
    def __call__(self):
        c = self.context
        grant = self.resources.request(f'/v1/runtime/organization-executions/{self.resources.execution_id}/admit-continuation',
            {'thread_id': self.resources.execution_id, 'run_id': self.run_id, 'operation_id': c['continuation_operation_id'],
             'manifest_digest': self.resources.manifest_digest, 'configuration_digest': c['configuration_digest'],
             'continuation_request_digest': c['continuation_request_digest']})
        try:
            validate_execution_grant(grant, self.resources.execution_id, self.resources.manifest_digest)
            validate_continuation(grant)
            if grant['authorized_run_id'] != self.run_id or any(grant[key] != value for key, value in c.items()):
                raise ValueError('scope')
        except (KeyError, ValueError, TypeError):
            raise OrganizationExecutionUnavailable('组织接续运行授权不匹配。') from None
        return grant


async def admit(native, config, thread, authority):
    """Do not trust thread flags or caller config as permission to dispatch models."""
    grant = await asyncio.to_thread(authority)
    validate_thread(thread, grant)
    run = await native.runs.get(grant['execution_id'], authority.run_id)
    if run.get('run_id') != authority.run_id:
        raise ValueError('organization_native_run_identity_mismatch')
    continuing = 'continuation_request' in grant
    (continuation_receipt if continuing else run_receipt)(run, thread, grant)
    expected = (continuation_request if continuing else run_request)(thread, grant)['config']['configurable']
    actual = config['configurable']
    if (any(actual.get(key) != value for key, value in expected.items())
            or any(key.startswith('finsight_') and key not in expected for key in actual)):
        raise ValueError('organization_runtime_configuration_mismatch')
    saved = await native.threads.get_state(grant['execution_id'])
    if continuing:
        validate_baseline(saved, grant)
        previous = await native.runs.get(grant['execution_id'], grant['continuation_request']['previous_run_id'])
        if previous['status'] != 'success' or previous['run_id'] != grant['continuation_request']['previous_run_id']:
            raise ValueError('organization_continuation_predecessor_not_complete')
    elif saved.get('values'):
        raise ValueError('organization_initial_run_requires_empty_state')
    return grant


@asynccontextmanager
async def organization_graph(config, native, thread):
    """Opt-in first orientation. Continuation and human-review actions stay closed."""
    from . import research_session_runtime as host
    from .current_research_contract import current_foundation
    from .organization_data_composition import OrganizationDataFactory
    from .research_budget import budget_from_host
    from sec_agent.research_foundation.contracts import load_research_graph_foundation
    ids = config['configurable']
    thread_id, run_id = str(UUID(str(ids['thread_id']))), str(UUID(str(ids['run_id'])))
    resources = OrganizationExecutionAuthority(base_url=os.environ['FINSIGHT_BUSINESS_API_URL'],
        network_profile=os.getenv('FINSIGHT_ORGANIZATION_AUTHORITY_NETWORK', 'loopback'),
        secret=os.environ['FINSIGHT_ORGANIZATION_RUNTIME_SECRET'], execution_id=thread_id,
        manifest_digest=thread['metadata']['organization_execution']['manifest_digest'])
    continuing = 'finsight_organization_continuation' in ids
    if continuing and ids.get('finsight_organization_start') is not None:
        raise ValueError('organization_run_has_conflicting_commands')
    authority = (OrganizationContinuationAuthority if continuing else OrganizationStartAuthority)(resources,
        run_id=run_id, context=ids['finsight_organization_continuation' if continuing else 'finsight_organization_start'])
    grant = await admit(native, config, thread, authority)
    def check():
        if authority() != grant:
            raise OrganizationExecutionUnavailable('组织启动授权发生变化。')
    # Host paths, budget, memory and model configuration are opened only after admission.
    root = Path(os.environ['FIN_REPO_ROOT'])
    settings = json.loads(Path(os.environ['FINSIGHT_REPORT_SESSION_SETTINGS']).read_text(encoding='utf-8'))
    profile, case = host.load_research_runtime_profile(root)
    studio, execution = host.configuration_from_native(config), host.execution_from_config(config)
    cutoff = grant['continuation_request' if continuing else 'start_request']['research_as_of']
    foundation = current_foundation(load_research_graph_foundation(), thread_id=thread_id,
        profile=studio.apply_case(case) if studio else case, research_as_of=cutoff)
    workspace = AssetWorkspace(Path(os.environ['FINSIGHT_ORGANIZATION_ASSETS_ROOT']))
    reader = OrganizationExecutionReader(workspace, resources)
    organization = OrganizationDataFactory(reader, foundation=foundation, research_as_of=cutoff,
        workbench_url=settings['workbench_url'])
    public, private = host.session_audit_sinks(Path(settings['audit_root']) / thread_id / run_id)
    budget = await asyncio.to_thread(budget_from_host, settings, thread_id=thread_id,
        metadata=thread['metadata'], environment=os.environ)
    phases = host.create_research_phase_runnables(root=root, settings=settings, profile=profile, case=case,
        thread_id=thread_id, run_id=run_id, api_key=SecretStr(os.environ['DEEPSEEK_API_KEY']),
        public_sink=public, private_sink=private, studio=studio, execution=execution,
        budget_scope=budget, organization_data_factory=organization, run_access_check=check,
        environment={**os.environ, 'FINSIGHT_RESEARCH_AS_OF':cutoff})
    expected = (continuation_request if continuing else run_request)(thread, grant)['input']
    async def input_guard(value):
        await asyncio.to_thread(check)
        if value != expected:
            raise ValueError('organization_start_input_mismatch')
        return value
    def unavailable(_):
        raise ValueError('organization_continuation_not_enabled')
    phases = {key:(phase if key == 'hierarchical' else RunnableLambda(input_guard) | phase if key == 'research' else phase if continuing else RunnableLambda(unavailable))
              for key, phase in phases.items()}
    yield host.build_research_session_graph(**phases, promote_orientation=continuing).compile(name='research_session').with_config({'recursion_limit':280})
