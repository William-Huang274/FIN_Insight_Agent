"""Explicit, once-only promotion from completed orientation to full research."""
from hashlib import sha256
import json
import os
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from types import SimpleNamespace
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from .organization_research_inputs import verify_storage

from .authentication import service_owner
from .business_transport import space_business_request
from sec_agent.agent_runtime.organization_continuation_contract import (
    validate_continuation, validate_baseline, continuation_request, continuation_receipt,
)
from sec_agent.research_foundation.organization_execution_access import validate_execution_grant, OrganizationExecutionUnavailable


async def continuation_authority(service, project_id, execution_id, *, raw_body=None, operation_id=None):
    project_id, execution_id = str(project_id), str(execution_id)
    grant = await space_business_request(service_owner(), 'GET',
        f'projects/{project_id}/execution-bindings/{execution_id}/continuation-access')
    try:
        validate_execution_grant(grant, execution_id, grant['manifest_digest'])
        validate_continuation(grant)
        if grant['project_id'] != project_id or (raw_body is not None and (
                grant['continuation_request_digest'] != 'sha256:' + sha256(raw_body).hexdigest()
                or grant['continuation_request'] != json.loads(raw_body) or grant['continuation_operation_id'] != operation_id)):
            raise ValueError('request_binding')
    except (KeyError, ValueError, TypeError, OrganizationExecutionUnavailable):
        raise HTTPException(409, '接续授权与固定命令不匹配') from None
    return grant


async def reauthorize(service, grant):
    if await continuation_authority(service, grant['project_id'], grant['execution_id']) != grant:
        raise HTTPException(409, '接续授权已变化')


def checked_receipt(run, thread, grant):
    try:
        return continuation_receipt(run, thread, grant)
    except (KeyError, ValueError, TypeError):
        raise HTTPException(409, '原生运行与接续命令不匹配') from None


def install_organization_continuation_routes(router, service):
    prefix = '/internal-research/organization'

    @router.post(prefix + '/continue')
    async def begin(request: Request):
        if os.environ.get('FINSIGHT_ORGANIZATION_START_ENABLED') != '1':
            raise HTTPException(503, '组织运行尚未启用')
        grant = request.scope.get('finsight_organization_continuation')
        if not grant:
            raise HTTPException(401, '缺少独立接续委托')
        tid = grant['execution_id']
        thread = await service.sdk.threads.get(tid)
        saved = await service.sdk.threads.get_state(tid)
        runs = await service.sdk.runs.list(tid, limit=2)
        if (thread.get('status') == 'busy' or len(runs) != 1
                or runs[0]['run_id'] != grant['continuation_request']['previous_run_id']
                or runs[0]['status'] != 'success'):
            raise HTTPException(409, '前序运行尚未完成或存在其他运行，须先核对')
        try:
            validate_baseline(saved, grant)
            arguments = continuation_request(thread, grant)
        except (KeyError, ValueError, TypeError):
            raise HTTPException(409, '预研究快照已变化或不满足接续条件') from None
        from .api.v1.report_sessions import public_run_usage
        _, usage = public_run_usage(service.audit_root, tid, runs[0]['run_id'])
        if usage is None or not usage['recorded_requests'] or usage['unknown_or_pending_requests'] or usage['partial_audit']:
            raise HTTPException(409, '前序用量未知或审计不完整，先核对原运行')
        shared = SimpleNamespace(workspace=AssetWorkspace(service.attachment_store.root.parent / 'project-library' / 'organization-assets'))
        await run_in_threadpool(verify_storage, shared, grant['organization_id'], grant['inputs'],
                                json.loads(grant['manifest_text'])['research_as_of'],
                                json.loads(grant['manifest_text']).get('retrieval_index'))
        await reauthorize(service, grant)
        run = await service.sdk.runs.create(tid, 'research_session', **arguments,
            multitask_strategy='reject', stream_mode='custom', stream_subgraphs=True, stream_resumable=True)
        try:
            result = checked_receipt(run, thread, grant)
            await reauthorize(service, grant)
        except HTTPException:
            return JSONResponse({'submission_status': 'unknown', 'detail': '已派发接续，须核对原命令；不会自动重发。'}, status_code=409)
        return result

    @router.get(prefix + '/executions/{execution_id}/continuation-state')
    async def state(execution_id: UUID, project_id: UUID):
        grant = await continuation_authority(service, project_id, execution_id)
        thread = await service.sdk.threads.get(str(execution_id))
        # This contract permits exactly the original orientation and one promotion.
        runs = await service.sdk.runs.list(str(execution_id), limit=3)
        candidates = [r for r in runs if r.get('metadata', {}).get('organization_continuation', {}).get(
            'continuation_operation_id') == grant['continuation_operation_id']]
        if len(runs) != 2 or len(candidates) != 1 or not any(r['run_id'] == grant['continuation_request']['previous_run_id'] for r in runs):
            raise HTTPException(409, '无法唯一核对接续运行')
        result = checked_receipt(candidates[0], thread, grant)
        await reauthorize(service, grant)
        return result
