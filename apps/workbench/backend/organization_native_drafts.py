"""Native thread preparation for a fixed organization binding; no run dispatch."""
from hashlib import sha256
import json
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from sec_agent.agent_runtime.execution_options import ExecutionOptions
from sec_agent.agent_runtime.studio_configuration import StudioConfiguration, default_configuration
from sec_agent.research_foundation.organization_execution_access import validate_execution_grant, OrganizationExecutionUnavailable
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from .authentication import service_owner
from .organization_research_inputs import verify_storage

SURFACE = 'organization_research_workbench'


def digest(value):
    return 'sha256:' + sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


async def preparation_authority(service, project_id, execution_id, *, raw_body=None, operation_id=None):
    from .business_transport import space_business_request
    project_id, execution_id = str(UUID(str(project_id))), str(UUID(str(execution_id)))
    grant = await space_business_request(service_owner(), 'GET',
        f'projects/{project_id}/execution-bindings/{execution_id}/preparation-access')
    try:
        if grant['project_id'] != project_id:
            raise ValueError('project')
        validate_execution_grant(grant, execution_id, grant['manifest_digest'])
        payload = grant['prepare_request']
        if (set(payload) != {'contract_version', 'execution_id', 'project_id', 'manifest_digest', 'execution'}
                or payload['contract_version'] != 'organization_native_preparation.v1'
                or payload['execution_id'] != execution_id or payload['project_id'] != project_id
                or payload['manifest_digest'] != grant['manifest_digest']):
            raise ValueError('request_scope')
        UUID(grant['prepare_operation_id'])
        if raw_body is not None and (grant['prepare_request_digest'] != 'sha256:' + sha256(raw_body).hexdigest()
                or payload != json.loads(raw_body) or grant['prepare_operation_id'] != operation_id):
            raise ValueError('request_binding')
        ExecutionOptions.model_validate(payload['execution'])
        if not isinstance(grant['title'], str) or not isinstance(grant['question'], str):
            raise ValueError('question')
    except (KeyError, ValueError, TypeError, OrganizationExecutionUnavailable):
        raise HTTPException(409, '组织草稿授权与固定准备请求不匹配') from None
    if not service.attachment_store or not service.research_profile:
        raise HTTPException(503, '组织草稿需要已配置的原件存储和研究配置')
    return grant


def context(grant):
    return {key: grant[key] for key in ('execution_id', 'thread_id', 'project_id', 'draft_id', 'organization_id',
                                       'manifest_digest', 'prepare_operation_id', 'prepare_request_digest')}


def metadata_for(grant, service):
    manifest = json.loads(grant['manifest_text'])
    options = ExecutionOptions.model_validate(grant['prepare_request']['execution']).validate_catalog(service.research_profile.get('branch_topics', []))
    config = {'configurable': {'finsight_execution': options.model_dump(),
                              'finsight_studio': default_configuration().model_dump(mode='json'),
                              'finsight_research_as_of': manifest['research_as_of'],
                              'finsight_organization_execution': context(grant)}}
    return {'surface': SURFACE, 'owner_id': 'organization:' + grant['organization_id'], 'graph': 'research_session',
            'mode': 'research', 'title': grant['title'], 'pending_question': grant['question'],
            'research_as_of': manifest['research_as_of'], 'organization_execution': context(grant),
            'organization_run_configuration': config, 'configuration_digest': digest(config),
            'organization_prepared': True, 'native_execution_enabled': False}


def validate_thread(thread, grant):
    try:
        meta = thread['metadata']
        config = meta['organization_run_configuration']
        values = config['configurable']
        if (thread['thread_id'] != grant['execution_id'] or meta['surface'] != SURFACE
                or meta['owner_id'] != 'organization:' + grant['organization_id']
                or meta['graph'] != 'research_session' or meta['organization_prepared'] is not True
                or meta['native_execution_enabled'] is not False or meta['organization_execution'] != context(grant)
                or meta['title'] != grant['title'] or meta['pending_question'] != grant['question']
                or set(config) != {'configurable'} or set(values) != {'finsight_execution', 'finsight_studio', 'finsight_research_as_of', 'finsight_organization_execution'}
                or values['finsight_execution'] != grant['prepare_request']['execution']
                or values['finsight_organization_execution'] != context(grant)
                or meta['research_as_of'] != json.loads(grant['manifest_text'])['research_as_of']
                or values['finsight_research_as_of'] != meta['research_as_of']
                or meta['configuration_digest'] != digest(config)
                or any(key in meta for key in ('asset_context', 'business_intake', 'studio_assistant_id', 'project_materials_status'))):
            raise ValueError('native_binding')
        StudioConfiguration.model_validate(values['finsight_studio'])
        return {**context(grant), 'status': 'draft', 'configuration_digest': meta['configuration_digest'],
                'native_execution_enabled': False}
    except (ValueError, KeyError, TypeError):
        raise HTTPException(409, '原生草稿身份或固定配置不匹配；不会覆盖或重新创建') from None


async def reauthorize(service, grant):
    current = await preparation_authority(service, grant['project_id'], grant['execution_id'])
    if current != grant:
        raise HTTPException(409, '组织准备授权发生变化')


def install_organization_native_routes(router, service):
    prefix = '/internal-research/organization'

    @router.post(prefix + '/prepare')
    async def prepare(request: Request):
        # InternalResearchIdentity runs current authorization BEFORE receipt replay.
        grant = request.scope.get('finsight_organization_preparation')
        if not grant:
            raise HTTPException(401, '缺少组织准备委托')
        from types import SimpleNamespace
        shared = SimpleNamespace(workspace=AssetWorkspace(service.attachment_store.root.parent / 'project-library' / 'organization-assets'))
        await run_in_threadpool(verify_storage, shared, grant['organization_id'], grant['inputs'])
        await reauthorize(service, grant)
        try:
            metadata = metadata_for(grant, service)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        # All markers/config are persisted in the single native create. No private
        # assets or memory copied, no follow-up patch that could be half-complete.
        thread = await service.sdk.threads.create(thread_id=grant['execution_id'], metadata=metadata, if_exists='raise')
        try:
            result = validate_thread(thread, grant)
            await reauthorize(service, grant)
        except HTTPException:
            # Thread may now exist: do not classify a lost authorization response as no submission.
            return JSONResponse({'submission_status': 'unknown', 'detail': '草稿已派发，结果须核对；不会自动重建。'}, status_code=409)
        return result

    @router.get(prefix + '/executions/{execution_id}/state')
    async def state(execution_id: UUID, project_id: UUID):
        grant = await preparation_authority(service, project_id, execution_id)
        thread = await service.sdk.threads.get(str(execution_id))
        result = validate_thread(thread, grant)
        if await service.sdk.runs.list(str(execution_id), limit=1):
            raise HTTPException(409, '此组织草稿存在未经本入口确认的运行，不能作为未启动草稿回执')
        await reauthorize(service, grant)
        return result
