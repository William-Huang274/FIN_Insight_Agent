"""Browser commands delegate to Java's durable commands; never dispatch the SDK here."""
import json
import os
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .authentication import service_owner
from .business_transport import space_business_request
from .organization_research_reads import OrganizationReadScope
from sec_agent.agent_runtime.execution_options import ExecutionOptions
from sec_agent.agent_runtime.organization_continuation_contract import baseline_digest, validate_baseline
from sec_agent.agent_runtime.organization_report_action_contract import ReportCommand, review_interrupts
from sec_agent.agent_runtime.targeted_revision import report_digest


class Prepare(BaseModel):
    model_config = ConfigDict(extra='forbid')
    execution_id: UUID
    manifest_digest: str = Field(pattern=r'^sha256:[a-f0-9]{64}$')
    execution: ExecutionOptions


class Continue(BaseModel):
    model_config = ConfigDict(extra='forbid')
    previous_run_id: UUID
    checkpoint_id: UUID
    state_digest: str = Field(pattern=r'^sha256:[a-f0-9]{64}$')


def install_organization_command_routes(router, service, browser_write):
    prefix = '/organization-projects/{project_id}/research/{execution_id}'

    async def java(project, execution, method, suffix, body=None):
        return await space_business_request(service_owner(), method,
            f'projects/{project}/execution-bindings/{execution}/{suffix}', body)

    def response(value):
        return JSONResponse(value, headers={'Cache-Control': 'no-store'})

    @router.get('/organization-projects/{project_id}/research-drafts/{draft_id}/executions')
    async def bindings(project_id: UUID, draft_id: UUID):
        return response(await space_business_request(service_owner(), 'GET',
            f'projects/{project_id}/research-drafts/{draft_id}/execution-bindings'))

    @router.post('/organization-projects/{project_id}/research-drafts/{draft_id}/prepare')
    async def prepare(project_id: UUID, draft_id: UUID, body: Prepare, request: Request):
        browser_write(request)
        binding = await space_business_request(service_owner(), 'POST',
            f'projects/{project_id}/research-drafts/{draft_id}/execution-bindings',
            {'id': str(body.execution_id), 'manifest_digest': body.manifest_digest})
        if binding['status'] != 'bound':
            raise HTTPException(409, '原执行已关闭，请核对项目记录')
        return response(await java(project_id, body.execution_id, 'POST', 'prepare',
            {'execution': body.execution.model_dump(mode='json', exclude_unset=True)}))

    @router.get(prefix + '/control')
    async def control(project_id: UUID, execution_id: UUID):
        # A read-only member receives no creator-only command state.
        try:
            value = await java(project_id, execution_id, 'GET', 'control')
        except HTTPException as exc:
            if exc.status_code not in (403, 404):
                raise
            scope = await OrganizationReadScope(service, project_id, execution_id).open()
            return await scope.response({'can_operate': False})
        value.pop('manifest_text', None)
        value.update(can_operate=True, enabled=os.getenv('FINSIGHT_ORGANIZATION_START_ENABLED') == '1')
        return response(value)

    @router.post(prefix + '/start')
    async def start(project_id: UUID, execution_id: UUID, request: Request):
        browser_write(request)
        grant = await java(project_id, execution_id, 'GET', 'control')
        cutoff = json.loads(grant['manifest_text'])['research_as_of']
        # Fixed date semantics, independent of browser timezone and today's date.
        return response(await java(project_id, execution_id, 'POST', 'start',
            {'research_as_of': cutoff + 'T23:59:59+00:00'}))

    @router.get(prefix + '/continuation-preview')
    async def preview(project_id: UUID, execution_id: UUID):
        controls = await java(project_id, execution_id, 'GET', 'control')
        if controls['start'] != 'received' or controls['continuation'] != 'absent':
            raise HTTPException(409, '请核对已有命令，不能生成新的接续确认')
        scope = await OrganizationReadScope(service, project_id, execution_id).open()
        state = await scope.state()
        runs = await service.sdk.runs.list(str(execution_id), limit=2)
        if scope.thread.get('status') == 'busy' or len(runs) != 1 or runs[0]['run_id'] != scope.grant['run_id'] or runs[0]['status'] != 'success':
            raise HTTPException(409, '预研究尚未成功结束或存在其他运行')
        body = {'previous_run_id': scope.grant['run_id'],
                'checkpoint_id': state.get('checkpoint', {}).get('checkpoint_id'), 'state_digest': baseline_digest(state)}
        try:
            Continue.model_validate(body)
            validate_baseline(state, {**scope.grant, 'continuation_request': body})
        except (ValueError, KeyError, TypeError):
            raise HTTPException(409, '当前预研究状态不满足接续条件') from None
        from .api.v1.report_sessions import public_run_usage
        _, usage = public_run_usage(service.audit_root, str(execution_id), scope.grant['run_id'])
        if not usage or not usage['recorded_requests'] or usage['unknown_or_pending_requests'] or usage['partial_audit']:
            raise HTTPException(409, '前序用量未知或审计不完整，请先核对原运行')
        await java(project_id, execution_id, 'GET', 'control')
        return await scope.response(body)

    @router.post(prefix + '/continue')
    async def begin(project_id: UUID, execution_id: UUID, body: Continue, request: Request):
        browser_write(request)
        return response(await java(project_id, execution_id, 'POST', 'continue', body.model_dump(mode='json')))

    @router.post(prefix + '/reconcile/{stage}')
    async def reconcile(project_id: UUID, execution_id: UUID,
                        stage: Literal['preparation', 'start', 'continuation'], request: Request):
        browser_write(request)
        suffix = {'preparation': 'reconcile', 'start': 'start-reconcile', 'continuation': 'continuation-reconcile'}[stage]
        return response(await java(project_id, execution_id, 'POST', suffix, {}))

    @router.get(prefix + '/report-commands')
    async def report_commands(project_id: UUID, execution_id: UUID):
        result = await java(project_id, execution_id, 'GET', 'report-commands')
        result['enabled'] = bool(result['enabled'] and os.getenv('FINSIGHT_ORGANIZATION_REPORT_ACTIONS_ENABLED') == '1')
        return response(result)

    @router.get(prefix + '/report-action-preview')
    async def report_preview(project_id: UUID, execution_id: UUID):
        commands = await java(project_id, execution_id, 'GET', 'report-commands')
        if not commands['enabled'] or os.getenv('FINSIGHT_ORGANIZATION_REPORT_ACTIONS_ENABLED') != '1':
            raise HTTPException(503, '组织报告交互尚未启用')
        if commands['items'] and commands['items'][0]['status'] in {'ready', 'dispatching', 'unknown'}:
            raise HTTPException(409, '请先核对上一条报告操作')
        scope = await OrganizationReadScope(service, project_id, execution_id).open()
        from .organization_report_actions import completed_predecessor
        await completed_predecessor(service, scope.thread, scope.grant['run_id'])
        state = await scope.state()
        values = state.get('values') or {}
        if not values.get('report') or not review_interrupts(state) or tuple(state.get('next') or ()) != ('human_review',):
            raise HTTPException(409, '当前没有可交互的报告审阅检查点')
        result = {'previous_run_id': scope.grant['run_id'], 'checkpoint_id': state['checkpoint']['checkpoint_id'],
                  'state_digest': baseline_digest(state), 'report_version': values['report_version'],
                  'report_digest': report_digest(values['report'])}
        await java(project_id, execution_id, 'GET', 'report-commands')
        return await scope.response(result)

    @router.post(prefix + '/report-commands')
    async def report_command(project_id: UUID, execution_id: UUID, body: ReportCommand, request: Request):
        browser_write(request)
        if os.getenv('FINSIGHT_ORGANIZATION_REPORT_ACTIONS_ENABLED') != '1':
            raise HTTPException(503, '组织报告交互尚未启用')
        return response(await java(project_id, execution_id, 'POST', 'report-commands', body.model_dump(mode='json')))

    @router.post(prefix + '/report-commands/{command_id}/reconcile')
    async def report_reconcile(project_id: UUID, execution_id: UUID, command_id: UUID, request: Request):
        browser_write(request)
        return response(await java(project_id, execution_id, 'POST', f'report-commands/{command_id}/reconcile', {}))
