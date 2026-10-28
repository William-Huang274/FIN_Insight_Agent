"""Authorized initial organization run. No retry, continuation or browser exposure."""
from hashlib import sha256
import json
import os
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from sec_agent.agent_runtime.organization_native_contract import validate_start, run_request, run_receipt
from sec_agent.research_foundation.organization_execution_access import validate_execution_grant, OrganizationExecutionUnavailable
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from .authentication import service_owner
from .organization_native_drafts import validate_thread
from .organization_research_inputs import verify_storage


async def start_authority(service, project_id, execution_id, *, raw_body=None, operation_id=None):
    from .business_transport import space_business_request
    project_id, execution_id = str(UUID(str(project_id))), str(UUID(str(execution_id)))
    grant = await space_business_request(service_owner(), 'GET',
        f'projects/{project_id}/execution-bindings/{execution_id}/start-access')
    try:
        validate_execution_grant(grant, execution_id, grant['manifest_digest'])
        validate_start(grant)
        if grant['project_id'] != project_id:
            raise ValueError('project')
        if raw_body is not None and (grant['start_request_digest'] != 'sha256:' + sha256(raw_body).hexdigest()
                or grant['start_request'] != json.loads(raw_body) or grant['start_operation_id'] != operation_id):
            raise ValueError('request_binding')
    except (KeyError, ValueError, TypeError, OrganizationExecutionUnavailable):
        raise HTTPException(409, '组织启动授权与固定请求不匹配') from None
    if not service.attachment_store or not service.research_profile:
        raise HTTPException(503, '组织启动需要原件存储和研究配置')
    return grant


async def reauthorize(service, grant):
    if await start_authority(service, grant['project_id'], grant['execution_id']) != grant:
        raise HTTPException(409, '组织启动授权发生变化')


def checked_receipt(run, thread, grant):
    try:
        return run_receipt(run, thread, grant)
    except (KeyError, ValueError, TypeError):
        raise HTTPException(409, '原生运行与固定启动命令不匹配') from None


def install_organization_start_routes(router, service):
    prefix = '/internal-research/organization'

    @router.post(prefix + '/start')
    async def start(request: Request):
        if os.environ.get('FINSIGHT_ORGANIZATION_START_ENABLED') != '1':
            raise HTTPException(503, '组织原生启动尚未启用')
        grant = request.scope.get('finsight_organization_start')
        if not grant:
            raise HTTPException(401, '缺少组织启动委托')
        from sec_agent.agent_runtime.organization_native_contract import on_demand
        if on_demand(grant) and os.getenv('FINSIGHT_ON_DEMAND_ENABLED') != '1':
            raise HTTPException(503, '按需研究入口尚未启用')
        thread = await service.sdk.threads.get(grant['execution_id'])
        validate_thread(thread, grant)
        try:
            arguments = run_request(thread, grant)
        except (KeyError, ValueError, TypeError):
            raise HTTPException(409, '准备配置与启动命令不匹配') from None
        if await service.sdk.runs.list(grant['execution_id'], limit=1):
            raise HTTPException(409, '原生草稿已有运行；请核对原记录')
        from types import SimpleNamespace
        shared = SimpleNamespace(workspace=AssetWorkspace(service.attachment_store.root.parent / 'project-library' / 'organization-assets'))
        await run_in_threadpool(verify_storage, shared, grant['organization_id'], grant['inputs'],
                                json.loads(grant['manifest_text'])['research_as_of'],
                                json.loads(grant['manifest_text']).get('retrieval_index'))
        await reauthorize(service, grant)
        run = await service.sdk.runs.create(grant['execution_id'], 'research_session', **arguments,
            multitask_strategy='reject', stream_mode='custom', stream_subgraphs=True, stream_resumable=True)
        try:
            result = checked_receipt(run, thread, grant)
            await reauthorize(service, grant)
        except HTTPException:
            return JSONResponse({'submission_status':'unknown', 'detail':'已派发，须核对原运行；不会自动重发。'}, status_code=409)
        return result

    @router.get(prefix + '/executions/{execution_id}/start-state')
    async def state(execution_id: UUID, project_id: UUID):
        grant = await start_authority(service, project_id, execution_id)
        thread = await service.sdk.threads.get(str(execution_id))
        validate_thread(thread, grant)
        runs = await service.sdk.runs.list(str(execution_id), limit=2)
        if len(runs) != 1:
            raise HTTPException(409, '无法唯一核对首次运行')
        result = checked_receipt(runs[0], thread, grant)
        await reauthorize(service, grant)
        return result
