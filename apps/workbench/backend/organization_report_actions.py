"""Java-authorized report actions. Uncertain SDK dispatches are never retried."""
from hashlib import sha256
import json
import os
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .authentication import service_owner
from .business_transport import space_business_request
from .organization_research_inputs import verify_storage
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.organization_execution_access import validate_execution_grant, OrganizationExecutionUnavailable
from sec_agent.agent_runtime.organization_report_action_contract import (
    validate_action, validate_baseline, action_request, action_receipt,
)


async def action_authority(service, project_id, execution_id, *, command_id, raw_body=None, operation_id=None, root_action=False):
    project_id, execution_id, command_id = map(str, (project_id, execution_id, command_id))
    grant = await space_business_request(service_owner(), 'GET',
        f'projects/{project_id}/execution-bindings/{execution_id}/' + ('task-commands' if root_action else 'report-commands') + f'/{command_id}/access')
    try:
        validate_execution_grant(grant, execution_id, grant['manifest_digest'])
        validate_action(grant)
        from sec_agent.agent_runtime.organization_native_contract import on_demand
        if on_demand(grant) != root_action:
            raise ValueError('action_route_contract_mismatch')
        if (grant['project_id'] != project_id or grant['report_command_id'] != command_id
                or (raw_body is not None and (
                    grant['report_action_request_digest'] != 'sha256:' + sha256(raw_body).hexdigest()
                    or grant['report_action_request'] != json.loads(raw_body)
                    or grant['report_action_operation_id'] != operation_id))):
            raise ValueError('request_binding')
    except (KeyError, ValueError, TypeError, OrganizationExecutionUnavailable):
        raise HTTPException(409, '报告操作授权与固定命令不匹配') from None
    return grant


async def reauthorize(service, grant):
    from sec_agent.agent_runtime.organization_native_contract import on_demand
    if await action_authority(service, grant['project_id'], grant['execution_id'],
                              command_id=grant['report_command_id'], root_action=on_demand(grant)) != grant:
        raise HTTPException(409, '报告操作授权已变化')


async def completed_predecessor(service, thread, previous_run_id):
    """All rounds count; no guessed latest run and no two-run truncation."""
    runs = await service.all_runs(thread['thread_id'])
    if thread.get('status') not in {'idle', 'interrupted'}:
        raise HTTPException(409, '当前运行尚未结束或存在失败，请先核对原操作')
    previous = [r for r in runs if r['run_id'] == previous_run_id]
    if len(previous) != 1 or previous[0]['status'] != 'success' or any(r['status'] in {'pending', 'running'} for r in runs):
        raise HTTPException(409, '前序运行尚未完成，请先核对原操作')
    # Created timestamps are server-owned. Caller checkpoint must also equal
    # the latest state; a matching historic predecessor is never sufficient.
    later = [r for r in runs if r['run_id'] != previous_run_id
             and r.get('created_at', '') > previous[0].get('created_at', '')]
    if later:
        raise HTTPException(409, '存在后续运行，请刷新后核对最新操作')
    from .api.v1.report_sessions import public_run_usage
    _, usage = public_run_usage(service.audit_root, thread['thread_id'], previous_run_id)
    if not usage or not usage['recorded_requests'] or usage['unknown_or_pending_requests'] or usage['partial_audit']:
        raise HTTPException(409, '前序用量未知或审计不完整，请先核对原运行')


def checked_receipt(run, thread, grant):
    try:
        return action_receipt(run, thread, grant)
    except (ValueError, KeyError, TypeError):
        raise HTTPException(409, '原生运行与报告操作不匹配') from None


def install_organization_report_action_routes(router, service):
    prefix = '/internal-research/organization'

    @router.post(prefix + '/report-actions')
    @router.post(prefix + '/root-actions')
    async def submit(request: Request):
        if os.getenv('FINSIGHT_ORGANIZATION_REPORT_ACTIONS_ENABLED') != '1':
            raise HTTPException(503, '组织报告交互尚未启用')
        grant = request.scope.get('finsight_organization_report_action')
        if not grant:
            raise HTTPException(401, '缺少报告操作委托')
        from sec_agent.agent_runtime.organization_native_contract import on_demand
        if on_demand(grant) and os.getenv('FINSIGHT_ON_DEMAND_ENABLED') != '1':
            raise HTTPException(503, '按需研究入口尚未启用')
        tid = grant['execution_id']
        thread = await service.sdk.threads.get(tid)
        await completed_predecessor(service, thread, grant['report_action_request']['previous_run_id'])
        saved = await service.sdk.threads.get_state(tid)
        try:
            validate_baseline(saved, grant)
            arguments = action_request(thread, grant)
        except (ValueError, KeyError, TypeError):
            raise HTTPException(409, '报告基线或审阅检查点已变化，请刷新后重新核对') from None
        shared = SimpleNamespace(workspace=AssetWorkspace(service.attachment_store.root.parent / 'project-library' / 'organization-assets'))
        manifest = json.loads(grant['manifest_text'])
        await run_in_threadpool(verify_storage, shared, grant['organization_id'], grant['inputs'],
                                manifest['research_as_of'], manifest.get('retrieval_index'))
        await reauthorize(service, grant)
        # Any exception after this point retains SubmissionReceipts' uncertain
        # claim. Java reconciles by operation ID; there is no transport retry.
        mark_dispatch = request.scope.get('finsight_mark_dispatch')
        if mark_dispatch is None:
            raise HTTPException(503, '报告操作缺少持久派发边界，未创建运行')
        await mark_dispatch()
        run = await service.sdk.runs.create(tid, 'research_session', **arguments,
            multitask_strategy='reject', stream_mode='custom', stream_subgraphs=True, stream_resumable=True)
        try:
            result = checked_receipt(run, thread, grant)
            await reauthorize(service, grant)
        except HTTPException:
            return JSONResponse({'submission_status': 'unknown', 'detail': '报告操作已派发，须核对原命令；不会自动重发。'}, status_code=409)
        return result

    @router.get(prefix + '/executions/{execution_id}/report-actions/{command_id}')
    @router.get(prefix + '/executions/{execution_id}/root-actions/{command_id}')
    async def reconcile(execution_id: UUID, command_id: UUID, project_id: UUID, request: Request):
        grant = await action_authority(service, project_id, execution_id, command_id=command_id,
                                       root_action='/root-actions/' in request.url.path)
        thread = await service.sdk.threads.get(str(execution_id))
        runs = await service.all_runs(execution_id)
        candidates = [r for r in runs if (r.get('metadata', {}).get('organization_report_action') or {}).get(
            'report_action_operation_id') == grant['report_action_operation_id']]
        if not candidates:
            from .submission_receipts import SubmissionReceipts
            if await run_in_threadpool(SubmissionReceipts.abandoned_preflight,
                    service.intake_receipts_root, service_owner(), grant['report_action_operation_id']):
                await reauthorize(service, grant)
                return JSONResponse({'submission_status': 'not_dispatched',
                    'detail': '原操作在原生派发前中断，未创建运行；原命令保留为未执行，可重新发起操作。'}, status_code=409)
        if len(candidates) != 1:
            raise HTTPException(409, '无法唯一核对报告操作，保留原命令')
        result = checked_receipt(candidates[0], thread, grant)
        await reauthorize(service, grant)
        return result
